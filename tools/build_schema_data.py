#!/usr/bin/env python3
"""Build machine-readable SWIS schema data from the official SolarWinds OrionSDK docs.

Source of truth is the ``gh-pages`` branch of https://github.com/solarwinds/OrionSDK,
which publishes https://solarwinds.github.io/OrionSDK/ . For a given platform version
that branch contains:

  <version>/schema/<Entity>.html   docfx-rendered entity reference (properties,
                                   relationships, verbs, access control, inheritance)
  <version>/swagger.json           Swagger 2.0 description of the SWIS REST surface,
                                   including a typed request body for every verb

Neither artifact alone is enough. The HTML carries entity structure but flattens verb
parameters into prose; the Swagger carries typed verb parameters but no entity
properties or relationships. This script parses both and joins them on the verb name.

Usage:
    python tools/build_schema_data.py --source /path/to/orionsdk-gh-pages --version 2026.2

Outputs (under data/):
    schema/<version>/entities/<Namespace>.json  full entity records, one file per namespace
    schema/<version>/index.json                 compact entity index (name -> counts, summary)
    schema/<version>/verbs.json                 every verb with typed parameters
    schema/<version>/relationships.json         entity-to-entity edge list
    schema/<version>/types.json                 the shape of every type a verb returns or takes
    schema/<version>/manifest.json              provenance and counts
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from collections import defaultdict

# --------------------------------------------------------------------------------------
# HTML parsing helpers
#
# The docfx output is regular enough to parse with regexes: every section is an <h2>/<h4>
# with a stable id, and every table is a plain <table><thead><tbody> with <td> cells that
# contain at most one <a>. We deliberately avoid a heavyweight HTML dependency so the
# tool runs anywhere with a stock Python 3.
# --------------------------------------------------------------------------------------

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def text_of(fragment: str) -> str:
    """Strip tags and normalize whitespace, returning plain text."""
    return WS_RE.sub(" ", html.unescape(TAG_RE.sub(" ", fragment))).strip()


def dotnet_type(cell_html: str) -> str:
    """Return the type named by a property/relationship 'Type' cell.

    Types render either as a link (``<a href="...">System.Int32</a>`` for BCL types,
    ``<a href="Orion.Nodes.html">Orion.Nodes</a>`` for entity types) or as bare text.
    """
    return text_of(cell_html)


def parse_tables(section_html: str) -> list[list[list[str]]]:
    """Return every table in ``section_html`` as a list of rows of raw cell HTML."""
    tables = []
    for table in re.findall(r"<table>(.*?)</table>", section_html, re.S):
        rows = []
        body = re.search(r"<tbody>(.*?)</tbody>", table, re.S)
        for tr in re.findall(r"<tr>(.*?)</tr>", body.group(1) if body else table, re.S):
            cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)
            if cells:
                rows.append(cells)
        if rows:
            tables.append(rows)
    return tables


def parse_access_control(section_html: str) -> list[dict]:
    """Parse an 'Access control' table into [{operations: [...], right: str}]."""
    out = []
    tables = parse_tables(section_html)
    if not tables:
        return out
    for row in tables[0]:
        if len(row) < 2:
            continue
        ops = [o.strip() for o in text_of(row[0]).split(",") if o.strip()]
        out.append({"operations": ops, "right": text_of(row[1])})
    return out


def split_sections(article: str) -> list[tuple[int, str, str, str]]:
    """Split an article into (level, id, title, body_html) tuples in document order."""
    heads = list(re.finditer(r'<h([1-4])\s+id="([^"]+)"[^>]*>(.*?)</h\1>', article, re.S))
    sections = []
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(article)
        sections.append((int(m.group(1)), m.group(2), text_of(m.group(3)), article[m.end():end]))
    return sections


def leading_paragraphs(body: str) -> list[str]:
    """Plain-text paragraphs that appear before the first table in ``body``."""
    body = body.split("<table>", 1)[0]
    return [t for t in (text_of(p) for p in re.findall(r"<p>(.*?)</p>", body, re.S)) if t]


# --------------------------------------------------------------------------------------
# Entity page parsing
# --------------------------------------------------------------------------------------

# Summary boilerplate emitted on every page; not useful content.
BOILERPLATE_RE = re.compile(
    r"^SolarWinds Information Service\s+[\d.]+\s+Schema Documentation$", re.I
)
# docfx renders "no summary written yet" as the literal string "ToDo".
TODO_RE = re.compile(r"^ToDo\.?$", re.I)

# Flags SolarWinds writes into the entity summary prose.
READONLY_RE = re.compile(r"\bread[- ]only\b", re.I)
DEPRECATED_RE = re.compile(r"\bobsolete\b|\bdeprecated\b", re.I)
# Some property summaries state outright that the property is the key, which is the only
# place the rendered schema records it. Deliberately narrow: "key" alone matches far too
# much ("foreign key", "key name", "licence key").
KEY_SUMMARY_RE = re.compile(
    r"\b(?:is the |as the |and )?primary key\b|\bprimary key of\b|\bkey property\b", re.I
)
# A property that names or describes the key is not itself the key.
# Orion.AIIM.OccurrencesLimited.PrimaryKeyName reads "Name of the primary key."
NOT_A_KEY_RE = re.compile(r"\bname of the (?:primary )?key\b|\bprimary key name\b", re.I)


def parse_entity_page(path: str, version: str) -> dict | None:
    raw = open(path, encoding="utf-8", errors="replace").read()
    article = re.search(r"<article[^>]*>(.*?)</article>", raw, re.S)
    if not article:
        return None
    article = article.group(1)
    article = re.sub(r"<script.*?</script>", "", article, flags=re.S)
    article = re.sub(r"<style.*?</style>", "", article, flags=re.S)

    sections = split_sections(article)
    if not sections or sections[0][0] != 1:
        return None

    name = sections[0][2].strip()
    if not name:
        return None

    entity: dict = {
        "entity": name,
        "namespace": name.split(".")[0],
        "version": version,
        "summary": "",
        "flags": {},
        "inheritance": [],
        "baseEntity": None,
        "accessControl": [],
        "properties": [],
        "targetRelationships": [],
        "sourceRelationships": [],
        "verbs": [],
    }

    # Summary: paragraphs under the <h1> before the first sub-heading, minus boilerplate.
    summary_parts = [
        p
        for p in leading_paragraphs(sections[0][3])
        if not BOILERPLATE_RE.match(p) and not TODO_RE.match(p)
    ]
    entity["summary"] = " ".join(summary_parts).strip()

    current_verb: dict | None = None
    for level, sec_id, title, body in sections[1:]:
        key = sec_id.split("-")[0] if sec_id else ""

        if title.lower() == "inheritance":
            chain = [text_of(a) for a in re.findall(r"<a[^>]*>(.*?)</a>", body, re.S)]
            entity["inheritance"] = chain
            entity["baseEntity"] = chain[-1] if chain else None
            current_verb = None

        elif title.lower() == "access control":
            # An 'Access control' <h4> belongs to the verb above it when we are inside
            # the Verbs section; otherwise it is the entity's own access control.
            if current_verb is not None:
                current_verb["accessControl"] = parse_access_control(body)
            else:
                entity["accessControl"] = parse_access_control(body)

        elif title.lower() == "properties" and level == 2:
            for row in (parse_tables(body) or [[]])[0]:
                if len(row) < 2:
                    continue
                entity["properties"].append(
                    {
                        "name": text_of(row[0]),
                        "type": dotnet_type(row[1]),
                        "summary": text_of(row[2]) if len(row) > 2 else "",
                        "access": text_of(row[3]) if len(row) > 3 else "",
                    }
                )
            current_verb = None

        elif title.lower() in ("target relationships", "source relationships") and level == 2:
            bucket = (
                "targetRelationships"
                if title.lower().startswith("target")
                else "sourceRelationships"
            )
            for row in (parse_tables(body) or [[]])[0]:
                if len(row) < 2:
                    continue
                notes = text_of(row[2]) if len(row) > 2 else ""
                rel = {
                    "name": text_of(row[0]),
                    "type": dotnet_type(row[1]),
                    "notes": notes,
                }
                # Notes read: "Defined by relationship <RelName> (<RelKind>)"
                m = re.search(r"Defined by relationship\s+(\S+)\s*\(([^)]+)\)", notes)
                if m:
                    rel["relationship"] = m.group(1)
                    rel["kind"] = m.group(2)
                entity[bucket].append(rel)
            current_verb = None

        elif title.lower() == "verbs" and level == 2:
            current_verb = None

        elif level == 3:
            # Inside the Verbs section every <h3> starts a verb.
            current_verb = {
                "name": title.strip(),
                "summary": " ".join(p for p in leading_paragraphs(body) if not TODO_RE.match(p)),
                "accessControl": [],
            }
            entity["verbs"].append(current_verb)

    blob = entity["summary"]
    if READONLY_RE.search(blob):
        entity["flags"]["readOnly"] = True
    if DEPRECATED_RE.search(blob):
        entity["flags"]["deprecated"] = True

    # The rendered schema pages do not mark key properties, which is a real gap: a key is
    # what a SWIS URI is built from and what CRUD addresses. SolarWinds does say so in
    # prose on some properties ("Interface ID. Primary key."), so surface that where it
    # exists, labelled as a hint rather than as the schema saying it. The authority for a
    # given server is Metadata.Property.IsKey; see docs/swis/metadata-introspection.md.
    key_hints = [
        p["name"]
        for p in entity["properties"]
        if KEY_SUMMARY_RE.search(p["summary"]) and not NOT_A_KEY_RE.search(p["summary"])
    ]
    if key_hints:
        entity["keyHints"] = key_hints
        entity["keyHintSource"] = "property summary text"

    ops = {op for ac in entity["accessControl"] for op in ac["operations"]}
    entity["supportedOperations"] = sorted(ops)
    entity["counts"] = {
        "properties": len(entity["properties"]),
        "targetRelationships": len(entity["targetRelationships"]),
        "sourceRelationships": len(entity["sourceRelationships"]),
        "verbs": len(entity["verbs"]),
    }
    return entity


# --------------------------------------------------------------------------------------
# Swagger parsing: typed verb parameters and CRUD capability
# --------------------------------------------------------------------------------------


def resolve_schema(node, defs, depth=0, seen=None):
    """Flatten a Swagger schema node into a compact, JSON-serializable description.

    ``$ref`` chains are followed up to a bounded depth; recursion is guarded by ``seen``
    so self-referential contract types (which do occur) cannot loop forever.
    """
    if not isinstance(node, dict):
        return {"type": "unknown"}
    seen = seen or set()

    ref = node.get("$ref")
    if ref:
        key = ref.rsplit("/", 1)[-1]
        out = {"type": key}
        if depth >= 3 or key in seen:
            return out
        target = defs.get(key)
        if isinstance(target, dict):
            resolved = resolve_schema(target, defs, depth + 1, seen | {key})
            if resolved.get("properties"):
                out["properties"] = resolved["properties"]
            if resolved.get("enum"):
                out["enum"] = resolved["enum"]
            if resolved.get("required"):
                out["required"] = resolved["required"]
        return out

    out = {"type": node.get("type", "object")}
    if "enum" in node:
        out["enum"] = node["enum"]
    if "format" in node:
        out["format"] = node["format"]
    if node.get("type") == "array" and "items" in node:
        out["items"] = resolve_schema(node["items"], defs, depth, seen)
    if node.get("properties") and depth < 3:
        props = {}
        for pname, pnode in node["properties"].items():
            child = resolve_schema(pnode, defs, depth + 1, seen)
            if isinstance(pnode, dict) and pnode.get("description"):
                child["description"] = pnode["description"]
            props[pname] = child
        out["properties"] = props
        if node.get("required"):
            out["required"] = node["required"]
    return out


REF_RE = re.compile(r"#/definitions/(?P<name>.+)$")


def definition_members(node: dict, defs: dict) -> list[dict]:
    """Flatten one Swagger definition into an ordered member list.

    Only one level deep. A member whose own type is another definition records that type's
    name rather than inlining it, which keeps the file readable and lets a reader follow
    the reference themselves.
    """
    members: list[dict] = []
    required = set(node.get("required") or [])
    for name, child in (node.get("properties") or {}).items():
        entry: dict = {"name": name}
        ref = child.get("$ref")
        if ref:
            m = REF_RE.match(ref)
            entry["type"] = m.group("name") if m else ref
        elif child.get("type") == "array":
            item = child.get("items") or {}
            iref = REF_RE.match(item.get("$ref", "") or "")
            entry["type"] = "array"
            entry["items"] = iref.group("name") if iref else item.get("type", "object")
        else:
            entry["type"] = child.get("type", "object")
        if child.get("enum"):
            entry["enum"] = child["enum"]
        if child.get("description"):
            entry["description"] = child["description"].strip()
        if name in required:
            entry["required"] = True
        members.append(entry)
    return members


def collect_types(verbs_by_entity: dict, defs: dict) -> dict:
    """Definitions for every type a verb returns or takes, keyed by type name.

    The schema pages give a verb's return as a bare type name, and the extracted data used
    to stop there, so "what does this verb give me back" had no answer short of reading
    SolarWinds' Swagger by hand. 501 verbs return a type that is defined in that contract.
    """
    wanted: set[str] = set()

    def note(type_name):
        if isinstance(type_name, str) and type_name in defs:
            wanted.add(type_name)

    for entity_verbs in verbs_by_entity.values():
        for verb in entity_verbs.values():
            note(verb.get("returns"))
            note(verb.get("returnsItems"))
            for p in verb.get("parameters") or []:
                note(p.get("type"))
                items = p.get("items")
                if isinstance(items, dict):
                    note(items.get("type"))
                    ref = REF_RE.match(items.get("$ref", "") or "")
                    if ref:
                        note(ref.group("name"))

    # Follow member types too. A return shape whose member is itself a defined type, very
    # often an enum, is only half an answer without the type that member names: the
    # suppression state's SuppressionMode is where the five mode values live.
    seen: set[str] = set()
    while True:
        fresh = wanted - seen
        if not fresh:
            break
        seen |= fresh
        for name in list(fresh):
            for member in definition_members(defs[name], defs):
                note(member.get("type"))
                note(member.get("items"))

    types: dict[str, dict] = {}
    for name in sorted(wanted):
        node = defs[name]
        record = {"name": name, "kind": node.get("type", "object")}
        if node.get("enum"):
            record["enum"] = node["enum"]
        members = definition_members(node, defs)
        if members:
            record["members"] = members
        types[name] = record
    return types


def parse_swagger(path: str) -> tuple[dict, dict, dict, dict]:
    """Return (verbs_by_entity, crud_by_entity, api_surface, types) from a swagger.json."""
    with open(path, encoding="utf-8") as fh:
        spec = json.load(fh)

    defs = spec.get("definitions", {})
    verbs: dict[str, dict[str, dict]] = defaultdict(dict)
    crud: dict[str, set] = defaultdict(set)

    for route, methods in spec.get("paths", {}).items():
        if route.startswith("/Invoke/"):
            _, _, rest = route.partition("/Invoke/")
            entity, _, verb = rest.rpartition("/")
            if not entity or not verb:
                continue
            op = methods.get("post") or next(iter(methods.values()), {})

            params: list[dict] = []
            required: list[str] = []
            for p in op.get("parameters", []):
                schema = p.get("schema")
                if not schema:
                    continue
                body = resolve_schema(schema, defs)
                required = list(body.get("required") or [])
                for pname, pnode in (body.get("properties") or {}).items():
                    entry = {
                        "name": pname,
                        "type": pnode.get("type", "unknown"),
                        "required": pname in required,
                    }
                    if pnode.get("description"):
                        entry["description"] = pnode["description"]
                    if pnode.get("items"):
                        entry["items"] = pnode["items"]
                    if pnode.get("enum"):
                        entry["enum"] = pnode["enum"]
                    if pnode.get("properties"):
                        entry["properties"] = pnode["properties"]
                    params.append(entry)

            returns = "System.Void"
            returns_items = None
            resp = (op.get("responses", {}).get("200") or {}).get("schema")
            if isinstance(resp, dict):
                returns = resolve_schema(resp, defs).get("type", "System.Void")
                # An array response carries the interesting type one level down. Recording
                # only "array" loses it, and 65 verbs return one, so "what comes back" is
                # unanswerable for them without this.
                if resp.get("type") == "array":
                    ref = REF_RE.match((resp.get("items") or {}).get("$ref", "") or "")
                    if ref:
                        returns_items = ref.group("name")
                    elif (resp.get("items") or {}).get("type"):
                        returns_items = resp["items"]["type"]

            # "ToDo" is docfx's placeholder for an unwritten summary. Carrying it through
            # would fill reference tables with a word that means nothing to a reader.
            description = (op.get("description") or "").strip()
            if TODO_RE.match(description):
                description = ""

            verbs[entity][verb] = {
                "entity": entity,
                "verb": verb,
                "description": description,
                "operationId": op.get("operationId", ""),
                "parameters": params,
                "requiredParameters": required,
                "returns": returns,
                "returnsItems": returns_items,
                "restPath": route,
            }
        elif route.startswith("/Create/"):
            crud[route.partition("/Create/")[2]].add("create")

    api_surface = {
        "basePath": spec.get("basePath", ""),
        "host": spec.get("host", ""),
        "schemes": spec.get("schemes", []),
        "swaggerVersion": spec.get("swagger", ""),
        "serviceVersion": (spec.get("info") or {}).get("version", ""),
        "genericPaths": sorted(k for k in spec.get("paths", {}) if not k.startswith(("/Invoke/", "/Create/"))),
    }
    verbs_out = dict(verbs)
    return (verbs_out, {k: sorted(v) for k, v in crud.items()}, api_surface,
            collect_types(verbs_out, defs))


# --------------------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------------------


def build(source: str, version: str, out_root: str) -> dict:
    schema_dir = os.path.join(source, version, "schema")
    swagger_path = os.path.join(source, version, "swagger.json")
    if not os.path.isdir(schema_dir):
        sys.exit(f"error: no schema directory at {schema_dir}")

    verbs_by_entity, crud_by_entity, api_surface, swagger_types = (
        parse_swagger(swagger_path) if os.path.isfile(swagger_path) else ({}, {}, {}, {})
    )

    entities: list[dict] = []
    skipped = 0
    for fname in sorted(os.listdir(schema_dir)):
        if not fname.endswith(".html") or fname in ("index.html", "toc.html"):
            continue
        rec = parse_entity_page(os.path.join(schema_dir, fname), version)
        if rec is None:
            skipped += 1
            continue

        # Join Swagger's typed verb parameters onto the HTML verb records.
        swagger_verbs = verbs_by_entity.get(rec["entity"], {})
        for verb in rec["verbs"]:
            sv = swagger_verbs.get(verb["name"])
            if sv:
                verb["parameters"] = sv["parameters"]
                verb["returns"] = sv["returns"]
                if sv.get("returnsItems"):
                    verb["returnsItems"] = sv["returnsItems"]
                verb["restPath"] = sv["restPath"]
                # docfx concatenates the verb summary and every parameter summary into
                # one run-on paragraph ("Starts realtime polling on Node entityNodeID of
                # target Node..."). Swagger keeps them separate, so prefer its verb-level
                # description and retain the raw text only when it adds something.
                if sv["description"]:
                    if verb["summary"] and verb["summary"] != sv["description"]:
                        verb["summaryRaw"] = verb["summary"]
                    verb["summary"] = sv["description"]
            else:
                verb.setdefault("parameters", [])
                verb.setdefault("returns", "unknown")
                verb.setdefault("restPath", f"/Invoke/{rec['entity']}/{verb['name']}")
        # A verb can exist in Swagger but not in the rendered HTML.
        known = {v["name"] for v in rec["verbs"]}
        for vname, sv in swagger_verbs.items():
            if vname not in known:
                rec["verbs"].append(
                    {
                        "name": vname,
                        "summary": sv["description"],
                        "accessControl": [],
                        "parameters": sv["parameters"],
                        "returns": sv["returns"],
                        "restPath": sv["restPath"],
                        "sourceOnly": "swagger",
                    }
                )
        rec["counts"]["verbs"] = len(rec["verbs"])
        rec["canCreate"] = "create" in crud_by_entity.get(rec["entity"], [])
        entities.append(rec)

    os.makedirs(out_root, exist_ok=True)
    ver_root = os.path.join(out_root, version)
    ent_root = os.path.join(ver_root, "entities")
    os.makedirs(ent_root, exist_ok=True)

    by_ns: dict[str, list[dict]] = defaultdict(list)
    for rec in entities:
        by_ns[rec["namespace"]].append(rec)
    for ns, recs in sorted(by_ns.items()):
        write_json(os.path.join(ent_root, f"{ns}.json"), recs)

    index = [
        {
            "entity": r["entity"],
            "namespace": r["namespace"],
            "baseEntity": r["baseEntity"],
            "summary": r["summary"][:400],
            "operations": r["supportedOperations"],
            "canCreate": r["canCreate"],
            "keyHints": r.get("keyHints"),
            "counts": r["counts"],
            "file": f"entities/{r['namespace']}.json",
        }
        for r in sorted(entities, key=lambda r: r["entity"])
    ]
    write_json(os.path.join(ver_root, "index.json"), index)

    all_verbs = sorted(
        (
            {
                "entity": r["entity"],
                "namespace": r["namespace"],
                **{k: v for k, v in verb.items() if k != "accessControl"},
                "accessControl": verb.get("accessControl", []),
            }
            for r in entities
            for verb in r["verbs"]
        ),
        key=lambda v: (v["entity"], v["name"]),
    )

    # Verbs the contract publishes on an entity that has no rendered schema page at all.
    # The join above can only reach an entity it parsed a page for, so these were dropped
    # silently: 63 invokable verbs across five entities, several of them verb facades of
    # exactly the kind IPAM uses. The entity count stays page-derived, which is the
    # defensible reading of "how many entities does the schema document", but a verb you
    # can invoke belongs in the verb list whichever source names it.
    documented = {r["entity"] for r in entities}
    orphan_verbs = []
    for entity, entity_verbs in sorted(verbs_by_entity.items()):
        if entity in documented:
            continue
        for vname, sv in sorted(entity_verbs.items()):
            orphan_verbs.append(
                {
                    "entity": entity,
                    "namespace": entity.split(".")[0],
                    "name": vname,
                    "summary": sv["description"],
                    "parameters": sv["parameters"],
                    "returns": sv["returns"],
                    **({"returnsItems": sv["returnsItems"]} if sv.get("returnsItems") else {}),
                    "restPath": sv["restPath"],
                    "sourceOnly": "swagger",
                    "accessControl": [],
                }
            )
    all_verbs = sorted(all_verbs + orphan_verbs, key=lambda v: (v["entity"], v["name"]))
    write_json(os.path.join(ver_root, "verbs.json"), all_verbs)

    # The shape of what a verb returns. The entity pages give only a type name, so without
    # this "what do I get back" has no answer short of reading the Swagger by hand.
    write_json(os.path.join(ver_root, "types.json"), swagger_types)

    edges = []
    for r in entities:
        for rel in r["sourceRelationships"]:
            edges.append(
                {
                    "from": r["entity"],
                    "navigationProperty": rel["name"],
                    "to": rel["type"],
                    "direction": "source",
                    "relationship": rel.get("relationship"),
                    "kind": rel.get("kind"),
                }
            )
        for rel in r["targetRelationships"]:
            edges.append(
                {
                    "from": r["entity"],
                    "navigationProperty": rel["name"],
                    "to": rel["type"],
                    "direction": "target",
                    "relationship": rel.get("relationship"),
                    "kind": rel.get("kind"),
                }
            )
    write_json(os.path.join(ver_root, "relationships.json"), edges)

    manifest = {
        "version": version,
        "source": "https://github.com/solarwinds/OrionSDK (gh-pages branch)",
        "sourceDocs": f"https://solarwinds.github.io/OrionSDK/{version}/schema/index.html",
        "generatedBy": "tools/build_schema_data.py",
        "counts": {
            "entities": len(entities),
            "namespaces": len(by_ns),
            "properties": sum(r["counts"]["properties"] for r in entities),
            "verbs": len(all_verbs),
            "verbsWithTypedParameters": sum(1 for v in all_verbs if v.get("parameters")),
            "verbsFromSwaggerOnly": sum(1 for v in all_verbs if v.get("sourceOnly") == "swagger"),
            "entitiesWithoutSchemaPage": len(
                {v["entity"] for v in all_verbs if v.get("sourceOnly") == "swagger"}
                - {r["entity"] for r in entities}
            ),
            "types": len(swagger_types),
            "verbsWithKnownReturnShape": sum(
                1 for v in all_verbs if v.get("returns") in swagger_types
            ),
            "relationshipEdges": len(edges),
            "creatableEntities": sum(1 for r in entities if r["canCreate"]),
            "skippedPages": skipped,
        },
        "namespaceCounts": {ns: len(recs) for ns, recs in sorted(by_ns.items())},
        "apiSurface": api_surface,
    }
    write_json(os.path.join(ver_root, "manifest.json"), manifest)
    return manifest


def write_json(path: str, payload) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, ensure_ascii=False, sort_keys=False)
        fh.write("\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True, help="checkout of the OrionSDK gh-pages branch")
    ap.add_argument("--version", default="2026.2", help="platform version directory to build")
    ap.add_argument("--out", default="data/schema", help="output root")
    args = ap.parse_args()

    manifest = build(args.source, args.version, args.out)
    print(json.dumps(manifest["counts"], indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Generate the large reference tables in docs/reference/ from the extracted data.

These pages are complete enumerations: every entity, every verb, every NetObject
prefix, every status code. They are generated rather than written because a
hand-maintained table of 2067 rows drifts from the schema the moment anyone touches it,
and a reference that might be stale is worse than no reference at all.

    python tools/build_reference_docs.py --version 2026.2

Regenerate with `make docs-reference` after `make data`.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BANNER = (
    "<!-- GENERATED FILE. Do not edit by hand.\n"
    "     Produced by tools/build_reference_docs.py from data/schema/{version}/.\n"
    "     Regenerate with: make docs-reference -->\n"
)


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def esc(text: str) -> str:
    """Escape a value for a markdown table cell."""
    if text is None:
        return ""
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


def trim(text: str, n: int) -> str:
    text = esc(text)
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


# --------------------------------------------------------------------------------------


def entity_index(entities, manifest, version) -> str:
    out = [BANNER.format(version=version), "# Entity index\n"]
    counts = manifest["counts"]
    out.append(
        f"Every entity published in the SolarWinds Information Service schema for platform "
        f"version **{version}**: {counts['entities']} entities across "
        f"{counts['namespaces']} namespaces, holding {counts['properties']} properties.\n"
    )
    out.append(
        "The columns are worth reading carefully. **Base** is the entity this one inherits "
        "from, and inherited properties are queryable on the child even though they are not "
        "listed on its own page. **Ops** are the operations the entity declares: an entity "
        "without `create` cannot be created through CRUD no matter how the request is "
        "shaped. **P/R/V** counts properties, relationships and verbs, which is a quick way "
        "to tell a substantial entity from a thin lookup table.\n"
    )
    out.append(
        "To see any entity in full, including its properties and verb signatures:\n\n"
        "```bash\n"
        "python3 tools/schema_query.py show Orion.Nodes\n"
        "```\n"
    )

    by_ns = defaultdict(list)
    for e in entities:
        by_ns[e["namespace"]].append(e)

    out.append("## Namespaces\n")
    out.append("| Namespace | Entities | Jump |")
    out.append("| --- | ---: | --- |")
    for ns, recs in sorted(by_ns.items(), key=lambda kv: -len(kv[1])):
        out.append(f"| `{ns}` | {len(recs)} | [{ns}](#{ns.lower()}) |")
    out.append("")

    for ns, recs in sorted(by_ns.items(), key=lambda kv: -len(kv[1])):
        out.append(f"## {ns}\n")
        out.append(f"{len(recs)} entities.\n")
        out.append("| Entity | Base | Ops | P/R/V | Summary |")
        out.append("| --- | --- | --- | --- | --- |")
        for e in sorted(recs, key=lambda r: r["entity"]):
            c = e["counts"]
            rels = c["targetRelationships"] + c["sourceRelationships"]
            ops = ",".join(o[0] for o in e["operations"]) or "-"
            base = f"`{e['baseEntity']}`" if e["baseEntity"] else ""
            out.append(
                f"| `{e['entity']}` | {base} | {ops} | {c['properties']}/{rels}/{c['verbs']} "
                f"| {trim(e['summary'], 110)} |"
            )
        out.append("")

    out.append("---\n")
    out.append(
        "`Ops` abbreviates the declared operations by first letter: "
        "`c` create, `r` read, `u` update, `d` delete, `i` invoke.\n"
    )
    return "\n".join(out)


def verb_index(verbs, manifest, version) -> str:
    counts = manifest["counts"]
    out = [BANNER.format(version=version), "# Verb index\n"]
    out.append(
        f"Every invokable verb in platform version **{version}**: {counts['verbs']} verbs, of "
        f"which {counts['verbsWithTypedParameters']} carry typed, named, ordered parameters "
        f"recovered from the SWIS Swagger contract.\n"
    )
    out.append(
        "**Arguments are positional.** The names below come from the contract and from the "
        "documentation, but they never travel on the wire: both the REST body and "
        "`Invoke-SwisVerb` send an ordered array. The order in the Signature column is "
        "therefore the whole contract, and getting it wrong produces a type error at best "
        "and a silent misfire at worst.\n"
    )
    out.append(
        "For one verb in full, including parameter types, descriptions, required flags and "
        "ready-to-paste call syntax:\n\n"
        "```bash\n"
        "python3 tools/schema_query.py verb Orion.Nodes Unmanage\n"
        "```\n\n"
        "On a live server, the same answer comes from `Metadata.VerbArgument`:\n\n"
        "```sql\n"
        "SELECT Position, Name, Type, IsOptional\n"
        "FROM Metadata.VerbArgument\n"
        "WHERE EntityName = 'Orion.Nodes' AND VerbName = 'Unmanage'\n"
        "ORDER BY Position\n"
        "```\n"
    )

    by_ns = defaultdict(list)
    for v in verbs:
        by_ns[v["namespace"]].append(v)

    out.append("## Namespaces\n")
    out.append("| Namespace | Verbs |")
    out.append("| --- | ---: |")
    for ns, recs in sorted(by_ns.items(), key=lambda kv: -len(kv[1])):
        out.append(f"| [{ns}](#{ns.lower()}) | {len(recs)} |")
    out.append("")

    for ns, recs in sorted(by_ns.items(), key=lambda kv: -len(kv[1])):
        out.append(f"## {ns}\n")
        out.append("| Entity | Verb | Signature | Returns | Requires | Description |")
        out.append("| --- | --- | --- | --- | --- | --- |")
        for v in sorted(recs, key=lambda r: (r["entity"], r["name"])):
            params = v.get("parameters") or []
            sig_parts = []
            for p in params:
                mark = "" if p.get("required") else "?"
                sig_parts.append(f"{p['name']}{mark}")
            sig = f"({', '.join(sig_parts)})" if params else "()"
            rights = sorted({ac["right"] for ac in v.get("accessControl", [])})
            out.append(
                f"| `{v['entity']}` | `{v['name']}` | `{esc(sig)}` "
                f"| `{trim(v.get('returns', '?'), 44)}` "
                f"| {', '.join(f'`{r}`' for r in rights)} "
                f"| {trim(v.get('summary', ''), 96)} |"
            )
        out.append("")

    out.append("---\n")
    out.append(
        "A `?` after a parameter name marks it optional. `Requires` is the right an account "
        "must hold to invoke the verb; an empty cell means the entity's own access control "
        "applies. Verbs recovered from the Swagger contract but absent from the rendered "
        "schema pages have no access control listed.\n"
    )
    return "\n".join(out)


def netobject_table(netobjects, version) -> str:
    out = [BANNER.format(version=version), "# NetObject type reference\n"]
    out.append(
        "A NetObject string identifies one monitored object as a type prefix and an id: node "
        "42 is `N:42`, interface 7 is `I:7`. The prefix is not decorative. It appears in "
        "alert macros, in web console URLs, in report definitions, and as the `netObjectId` "
        "argument that verbs such as `Unmanage` and `PollNow` expect. Passing a bare `42` "
        "where `N:42` is required is one of the most common automation mistakes.\n"
    )
    out.append(
        "**Key properties** are the columns that form the entity's primary key, which is what "
        "a SWIS URI is built from and what CRUD operations address. **Parent** is the entity "
        "this one hangs off, which tells you where to look for the owning node.\n"
    )
    out.append(
        "This table comes from a community reference workbook that predates the current "
        "schema, so it is checked against the published entity list on every build. Rows "
        "marked in the Status column no longer exist under that name in "
        f"**{version}**; where a successor could be identified with confidence it is named.\n"
    )

    by_module = defaultdict(list)
    for rec in netobjects:
        by_module[rec.get("module") or "Other"].append(rec)

    total = len(netobjects)
    stale = sum(1 for r in netobjects if not r.get("inCurrentSchema"))
    out.append(f"{total} entries across {len(by_module)} modules; {stale} no longer resolve in {version}.\n")

    out.append("| Module | Entity | Display name | Prefix | Key properties | Parent | Status |")
    out.append("| --- | --- | --- | --- | --- | --- | --- |")
    for module, recs in sorted(by_module.items()):
        for rec in sorted(recs, key=lambda r: r["entity"]):
            keys = ", ".join(f"`{k}`" for k in rec.get("keyProperties", [])) or ""
            parents = ", ".join(f"`{p}`" for p in rec.get("parentEntities", [])) or ""
            prefix = f"`{rec['netObjectPrefix']}`" if rec.get("netObjectPrefix") else ""
            if rec.get("inCurrentSchema"):
                status = "current"
            elif rec.get("supersededBy"):
                status = f"renamed to `{rec['supersededBy']}`"
            else:
                status = "not in this version"
            out.append(
                f"| {esc(module)} | `{rec['entity']}` | {esc(rec.get('displayName'))} | {prefix} "
                f"| {keys} | {parents} | {status} |"
            )
    out.append("")
    out.append("---\n")
    out.append(
        "To confirm an entity's key properties against your own server, which is the "
        "authoritative answer for your version:\n\n"
        "```sql\n"
        "SELECT Name, Type FROM Metadata.Property\n"
        "WHERE Entity.FullName = 'Orion.Nodes' AND IsKey = true\n"
        "```\n"
    )
    return "\n".join(out)


def status_table(statuses, version) -> str:
    out = [BANNER.format(version=version), "# Status code reference\n"]
    out.append(
        "Status is stored as an integer on every monitored entity. The web console renders "
        "it as a coloured icon, but a query returns the raw number, so any report or "
        "automation has to map it back to something meaningful.\n"
    )
    out.append(
        "**Rank orders severity for rollup, and a lower rank is worse.** When a group or a "
        "parent object computes its status from its children, the child with the lowest rank "
        "wins. That is why Down (110) beats Warning (220), and why Up (500) loses to almost "
        "everything. It also explains the statuses that look odd out of context: Unknown sits "
        "at 495, just below Up, because an object that has not been polled yet should not "
        "drag a group into a red state.\n"
    )
    out.append(f"{len(statuses)} status codes.\n")
    out.append("| Status | Name | Rank | Meaning |")
    out.append("| ---: | --- | ---: | --- |")
    for s in statuses:
        out.append(
            f"| {s['status']} | **{esc(s['name'])}** | {s['rank'] if s['rank'] is not None else ''} "
            f"| {esc(s.get('description') or '')} |"
        )
    out.append("")
    out.append("## Resolving status in a query\n")
    out.append(
        "Do not hard-code these numbers into a report. `Orion.StatusInfo` is the lookup table "
        "on a live server, and joining it keeps the query correct if SolarWinds adds a status:\n"
    )
    out.append(
        "```sql\n"
        "SELECT n.Caption, n.Status, s.StatusName, s.ShortDescription\n"
        "FROM Orion.Nodes n\n"
        "JOIN Orion.StatusInfo s ON n.Status = s.StatusId\n"
        "ORDER BY s.Ranking, n.Caption\n"
        "```\n"
    )
    out.append(
        "Counting by status name, the shape most dashboards want:\n\n"
        "```sql\n"
        "SELECT s.StatusName, COUNT(n.NodeID) AS NodeCount\n"
        "FROM Orion.Nodes n\n"
        "JOIN Orion.StatusInfo s ON n.Status = s.StatusId\n"
        "GROUP BY s.StatusName\n"
        "ORDER BY COUNT(n.NodeID) DESC\n"
        "```\n"
    )
    out.append(
        "One caveat when reporting on outages: a node can be Down because it is genuinely "
        "unreachable, or Unmanaged because someone opened a maintenance window. Filter "
        "`UnManaged = FALSE` when you mean the former.\n"
    )
    return "\n".join(out)


def function_index(functions, version) -> str:
    out = [BANNER.format(version=version), "# SWQL function index\n"]
    documented = sum(1 for f in functions if f.get("documented"))
    out.append(
        f"{len(functions)} functions, of which {documented} appear in the official SolarWinds "
        "SWQL function reference. The remainder are attested only by a community workbook and "
        "are marked accordingly: they may work on your version, but verify before depending "
        "on them.\n"
    )
    out.append(
        "For the narrative version with worked examples and the date/time pitfalls, see "
        "[../swql/functions.md](../swql/functions.md) and "
        "[../swql/date-and-time.md](../swql/date-and-time.md).\n"
    )

    by_cat = defaultdict(list)
    for f in functions:
        by_cat[f["category"]].append(f)

    for cat, funcs in sorted(by_cat.items()):
        out.append(f"## {cat}\n")
        out.append("| Function | Since | Description | Example |")
        out.append("| --- | --- | --- | --- |")
        for f in sorted(funcs, key=lambda r: r["name"].lower()):
            since = f.get("availableSince") or f.get("workbookMinCoreVersion") or ""
            example = ""
            if f.get("examples"):
                example = f"`{trim(f['examples'][0]['query'], 78)}`"
            name = f"`{esc(f['signature'])}`"
            if not f.get("documented"):
                name += " ⚠️"
            out.append(f"| {name} | {since} | {trim(f.get('description', ''), 130)} | {example} |")
        out.append("")

    out.append("---\n")
    out.append(
        "⚠️ marks a function that is not in the official reference. `Since` is the earliest "
        "version the function is attested in; where the official reference and the workbook "
        "disagree, both figures are recorded in "
        "[`data/reference/reconciliation.json`](../../data/reference/reconciliation.json).\n"
    )
    return "\n".join(out)


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content.rstrip() + "\n")
    return path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", default="2026.2")
    ap.add_argument("--out", default="docs/reference")
    args = ap.parse_args()

    sroot = os.path.join(ROOT, "data", "schema", args.version)
    rroot = os.path.join(ROOT, "data", "reference")
    out = os.path.join(ROOT, args.out)

    manifest = load(os.path.join(sroot, "manifest.json"))
    index = load(os.path.join(sroot, "index.json"))
    verbs = load(os.path.join(sroot, "verbs.json"))

    written = [
        write(os.path.join(out, "entity-index.md"), entity_index(index, manifest, args.version)),
        write(os.path.join(out, "verb-index.md"), verb_index(verbs, manifest, args.version)),
    ]

    if os.path.isdir(rroot):
        written += [
            write(os.path.join(out, "netobject-types.md"), netobject_table(load(os.path.join(rroot, "netobject-types.json")), args.version)),
            write(os.path.join(out, "status-codes.md"), status_table(load(os.path.join(rroot, "status-codes.json")), args.version)),
            write(os.path.join(out, "swql-function-index.md"), function_index(load(os.path.join(rroot, "swql-functions.json")), args.version)),
        ]

    for path in written:
        size = os.path.getsize(path)
        print(f"wrote {os.path.relpath(path, ROOT)} ({size:,} bytes)")


if __name__ == "__main__":
    main()

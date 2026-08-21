#!/usr/bin/env python3
"""Check that names and simple facts stated in prose match the schema.

validate_swql.py covers what is inside a query. It does not see the sentence, the table
cell, or the bullet, and those are just as easy to get wrong and just as damaging to
trust: a reader who finds one invented name stops believing the rest.

    python tools/check_entity_references.py
    python tools/check_entity_references.py --strict     # non-zero exit on any unknown

Four things are checked, each a name or fact that looks right and fails on a live server:

  - **Entity and member names.** A token shaped like a SWIS entity name must exist, and
    ``Orion.Nodes.Foo`` must fail even though ``Orion.Nodes`` is real.
  - **Property types.** "``Cirrus.Nodes.NodeID`` is a ``System.Guid``" is checked against
    the declared type. The guides explain a whole class of silent join failure with two
    such facts, so getting one backwards would make the explanation wrong.
  - **NetObject prefixes.** A verb taking a netObjectId wants ``N:42`` rather than ``42``,
    and an invented prefix is accepted by the call and acts on nothing.
  - **Rights.** "requires the ``manageNodes`` right" is checked against the rights the
    schema actually declares, since an invented one sends a reader chasing a permission
    that does not exist.

Documentation legitimately names entities that do not exist, when warning readers off a
form they would otherwise assume, or when explaining a rename. Four things are accepted:

  - a name inside a negation, which is the usual phrasing: "there is no Orion.QoE
    namespace", "Orion.APM.Component.Node does not exist". Pass --no-negation to review
    these rather than accept them.
  - anything recorded in data/reference/reconciliation.json as a known rename
  - anything named in a schema-change report under docs/reference/
  - anything listed in tools/entity-reference-allowlist.txt

Everything else is reported. An invented name asserted as real, which is what this exists
to catch, is not phrased as a negation and still gets through to the report.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOWLIST = os.path.join(ROOT, "tools", "entity-reference-allowlist.txt")

# A SWIS entity name: a known namespace, then one or more dotted segments starting with an
# uppercase letter. Anchoring on the namespace keeps this from matching ordinary prose,
# file paths, or dotted identifiers from other languages.
def entity_token_re(namespaces: set[str]) -> re.Pattern:
    ns = "|".join(sorted((re.escape(n) for n in namespaces), key=len, reverse=True))
    # The lookbehind stops the pattern matching partway through a longer dotted name.
    # Verb argument types are written as full .NET type names such as
    # SolarWinds.Data.Providers.Orion.Verbs.Discovery-StartDiscoveryContext, and without
    # it the "Orion.Verbs.Discovery" inside one is reported as a missing entity.
    return re.compile(rf"(?<![.\w-])(?:{ns})(?:\.[A-Za-z][A-Za-z0-9_]*)+\b")


# Fragments that look like entity names but are something else.
NOISE_SUFFIXES = (
    ".json", ".md", ".html", ".py", ".ps1", ".sh", ".csv", ".xlsx", ".swql", ".yml", ".yaml",
)

# .NET base class library namespaces. PowerShell samples name these directly, as in
# [System.Collections.Generic.List[object]]::new() or a [PSCredential] parameter, and they
# are not SWIS entities. SWIS uses System.* too, but only for flat two-segment names such
# as System.Entity and System.ManagedEntity, so there is no overlap with these.
DOTNET_NAMESPACES = (
    "System.Collections.", "System.Management.", "System.Text.", "System.IO.",
    "System.Net.", "System.Threading.", "System.Reflection.", "System.Diagnostics.",
    "System.Security.", "System.Xml.", "System.Linq.", "System.Globalization.",
)
# Property references written as Entity.Property, which are not entity names themselves.
# Rather than guess, a token is accepted when stripping trailing segments yields a real
# entity, since "Orion.Nodes.Caption" is a legitimate way to write a property.
MAX_TRAILING_SEGMENTS = 3


def load_schema(version: str) -> tuple[set[str], set[str], set[str]]:
    """Return (entities, namespaces, otherKnownNames).

    otherKnownNames covers dotted names that appear in the schema but are not entities,
    and that documentation legitimately mentions: relationship names such as
    Orion.EngineHostsNodes, .NET types used as property or verb types such as
    System.DateTime, and entities referenced as a relationship target without a page of
    their own.
    """
    sroot = os.path.join(ROOT, "data", "schema", version)
    index_path = os.path.join(sroot, "index.json")
    if not os.path.isfile(index_path):
        sys.exit(f"error: no schema index at {index_path}; run make data")
    with open(index_path, encoding="utf-8") as fh:
        entities = {rec["entity"] for rec in json.load(fh)}
    namespaces = {e.split(".")[0] for e in entities}

    other: set[str] = set()
    rel_path = os.path.join(sroot, "relationships.json")
    if os.path.isfile(rel_path):
        with open(rel_path, encoding="utf-8") as fh:
            for edge in json.load(fh):
                if edge.get("relationship"):
                    other.add(edge["relationship"])
                if edge.get("to"):
                    other.add(edge["to"])
                # Relationship kinds are dotted names too: System.Hosting,
                # System.Reference, System.Reliance.
                if edge.get("kind"):
                    other.add(edge["kind"])

    ent_dir = os.path.join(sroot, "entities")
    if os.path.isdir(ent_dir):
        for fname in sorted(os.listdir(ent_dir)):
            if not fname.endswith(".json"):
                continue
            with open(os.path.join(ent_dir, fname), encoding="utf-8") as fh:
                for rec in json.load(fh):
                    other.update(p["type"] for p in rec["properties"] if p.get("type"))
                    other.update(rec.get("inheritance") or [])
                    for verb in rec.get("verbs") or []:
                        if verb.get("returns"):
                            other.add(verb["returns"])
                        for p in verb.get("parameters") or []:
                            other.update(type_names(p))
    return entities, namespaces, other


def type_names(node) -> set[str]:
    """Every type string in a parameter record, including nested element types.

    An array parameter keeps its element type one level down, in ``items.type``, and that
    is where the .NET generics live: an argument typed
    ``array<System.Collections.Generic.KeyValuePair<string, string>>`` records only
    ``array`` at the top level. Reading the top level alone means the documentation cannot
    quote a verb signature without tripping the name check.
    """
    found: set[str] = set()
    if isinstance(node, dict):
        if isinstance(node.get("type"), str):
            found.add(node["type"])
        for key in ("items", "element", "value"):
            if key in node:
                found |= type_names(node[key])
    elif isinstance(node, list):
        for item in node:
            found |= type_names(item)
    return found


def load_allowed(entities: set[str]) -> set[str]:
    allowed = set()

    recon = os.path.join(ROOT, "data", "reference", "reconciliation.json")
    if os.path.isfile(recon):
        with open(recon, encoding="utf-8") as fh:
            for note in json.load(fh):
                if note.get("entity"):
                    allowed.add(note["entity"])

    # Schema-change reports are lists of entities that were removed, so every name in them
    # is expected to be absent from the current version.
    ref_dir = os.path.join(ROOT, "docs", "reference")
    if os.path.isdir(ref_dir):
        for fname in os.listdir(ref_dir):
            if fname.startswith("schema-changes-") and fname.endswith(".md"):
                text = open(os.path.join(ref_dir, fname), encoding="utf-8", errors="replace").read()
                allowed |= set(re.findall(r"`([A-Za-z][\w.]*\.[A-Za-z][\w.]*)`", text))

    if os.path.isfile(ALLOWLIST):
        for line in open(ALLOWLIST, encoding="utf-8"):
            line = line.split("#", 1)[0].strip()
            if line:
                allowed.add(line)

    return allowed


def resolves(token: str, entities: set[str], prefixes: set[str], members=None) -> tuple[bool, str]:
    """Return (ok, reason). Reason is filled in only when the token does not resolve.

    Four shapes count as real, and all four appear constantly in the prose:

    - the entity itself, ``Orion.Nodes``
    - a namespace prefix, ``Orion.APM``, used when describing a family of entities
    - a partial name, as in "entities beginning ``Orion.NPM.CustomPoller``"
    - an entity plus member segments, ``Orion.Nodes.Interfaces.Name``

    The last one is checked properly when a member lookup is supplied: writing
    ``Orion.Nodes.Foo`` should fail even though ``Orion.Nodes`` is real, because a
    property attributed to the wrong entity is exactly as misleading as an invented one.
    """
    if token in prefixes:
        return True, ""
    if any(e.startswith(token) for e in entities):
        return True, ""

    parts = token.split(".")
    for drop in range(1, MAX_TRAILING_SEGMENTS + 1):
        if drop >= len(parts) - 1:
            break
        base = ".".join(parts[: len(parts) - drop])
        if base not in entities:
            continue
        trailing = parts[len(parts) - drop:]
        if members is None:
            return True, ""
        # Walk the member chain the same way a query would.
        current = base
        for i, seg in enumerate(trailing):
            props, navs = members(current)
            key = seg.lower()
            if key in navs:
                current = navs[key]
                continue
            if key in props:
                if i == len(trailing) - 1:
                    return True, ""
                return False, f"{current}.{seg} is a property, so .{trailing[i+1]} cannot follow it"
            return False, f"{current} has no member named '{seg}'"
        return True, ""
    return False, "not an entity, namespace, or member of one"


# "`Cirrus.Nodes.NodeID` is a `System.Guid`". Property types carry real weight in these
# guides: the reason joining NCM to Orion on the wrong id silently returns nothing is that
# one side is a GUID and the other an integer, and that whole explanation rests on the two
# types being stated correctly.
PROPERTY_TYPE_RE = re.compile(
    r"`(?P<token>[A-Z]\w*(?:\.[A-Z]\w*)+\.\w+)`\s+is\s+an?\s+`(?P<type>System\.\w+)`")


def type_claims(text: str, members) -> list[tuple[str, str, str]]:
    """Return (token, claimed, actual) for every property-type claim that disagrees.

    Only claims about a plain property are checked. A navigation property is described by
    its relationship kind rather than by a member type, so ``Orion.Nodes.Interfaces is a
    System.Hosting`` is a different sort of statement and is left alone here.
    """
    problems = []
    flat = " ".join(text.split())
    for m in PROPERTY_TYPE_RE.finditer(flat):
        token, claimed = m.group("token"), m.group("type")
        entity, _, prop = token.rpartition(".")
        try:
            props, navs = members(entity)
        except Exception:
            continue
        key = prop.lower()
        if key in navs or key not in props:
            continue
        actual = props[key]
        if actual != "verb" and actual != claimed:
            problems.append((token, claimed, actual))
    return problems


# A NetObject string as the guides write it: `N:42`, `AA:<ApplicationID>`, or the bare
# prefix `TSR:`. Verbs taking a netObjectId want one of these rather than a bare id, and an
# invented prefix is the same plausible-but-wrong failure as an invented entity name: the
# call is accepted and acts on nothing, or on the wrong kind of thing.
NETOBJECT_RE = re.compile(r"`(?P<prefix>[A-Z]{1,4}):(?:\d+|<[^`>]*>)?`")


def load_netobject_prefixes() -> dict[str, list[str]]:
    """Prefix to the entities that use it, from the reference data."""
    path = os.path.join(ROOT, "data", "reference", "netobject-types.json")
    prefixes: dict[str, list[str]] = defaultdict(list)
    if not os.path.isfile(path):
        return prefixes
    with open(path, encoding="utf-8") as fh:
        rows = json.load(fh)
    for row in rows:
        prefix = (row.get("netObjectPrefix") or "").strip().rstrip(":")
        if prefix:
            prefixes[prefix].append(row["entity"])
    return prefixes


# "requires the `manageNodes` right", "requires `admin`". Deliberately narrow: the guides
# also write "an entity-level `invoke` right", which names the operation a right governs
# rather than a right called invoke, and reporting those would be noise.
RIGHT_RE = re.compile(r"requires?\s+(?:the\s+)?`(?P<right>\w+)`(?:\s+right)?\b", re.I)


def load_rights(version: str) -> set[str]:
    """Every right name the schema declares, at entity or verb level."""
    rights: set[str] = set()
    ent_dir = os.path.join(ROOT, "data", "schema", version, "entities")
    if not os.path.isdir(ent_dir):
        return rights
    for fname in sorted(os.listdir(ent_dir)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(ent_dir, fname), encoding="utf-8") as fh:
            records = json.load(fh)
        for rec in records:
            for entry in rec.get("accessControl") or []:
                if entry.get("right"):
                    rights.add(entry["right"])
            for verb in rec.get("verbs") or []:
                for entry in verb.get("accessControl") or []:
                    if entry.get("right"):
                        rights.add(entry["right"])
    return rights


def right_claims(text: str, rights: set[str]) -> list[str]:
    """Return the rights named in the text that the schema does not declare."""
    flat = " ".join(text.split())
    lowered = {r.lower() for r in rights}
    return [m.group("right") for m in RIGHT_RE.finditer(flat)
            if m.group("right").lower() not in lowered]


def netobject_claims(text: str, prefixes: dict[str, list[str]]) -> list[str]:
    """Return the NetObject prefixes used in the text that the reference does not list."""
    unknown = []
    flat = " ".join(text.split())
    for m in NETOBJECT_RE.finditer(flat):
        if m.group("prefix") not in prefixes:
            unknown.append(m.group(0))
    return unknown


def namespace_prefixes(entities: set[str]) -> set[str]:
    """Every dotted prefix of every entity name, so 'Orion.APM' resolves."""
    prefixes = set()
    for name in entities:
        parts = name.split(".")
        for i in range(1, len(parts)):
            prefixes.add(".".join(parts[:i]))
    return prefixes


# Generated pages are enumerations of the extracted data, so by construction they cannot
# name an entity the schema does not have. They can, however, contain type names trimmed
# to fit a table column, which look like broken entity names. Skip them.
GENERATED_MARKER = "GENERATED FILE"

# Good documentation names the wrong form on purpose: "there is no Orion.QoE namespace",
# "Orion.APM.Component.Node does not exist". Those are the most useful sentences on some
# pages, and reporting them trains authors to delete the warning rather than keep it.
#
# A negation shortly before the name is a reliable signal, because a name asserted as real
# is not introduced that way. An invented name stated positively, which is what this check
# exists to catch, still gets reported.
# Before the name: "there is no Orion.QoE namespace", "use X rather than Orion.SAM".
NEGATION_BEFORE_RE = re.compile(
    r"\b(?:no|none|neither|not|never|isn't|aren't|doesn't|don't|nothing|absent|missing|"
    r"removed|renamed|wrong|mistake|obsolete|deprecated|stale|former|formerly|"
    r"previously|superseded|legacy)\b"
    r"|\b(?:instead of|rather than|used to|no longer)\b",
    re.I,
)
# After the name: "Orion.APM.Component.Node does not exist". This one has to be tighter,
# because a permissive forward pattern would accept a real error that happens to sit in a
# sentence containing "not". Only phrasings that negate the name itself count.
NEGATION_AFTER_RE = re.compile(
    r"^\W{0,4}(?:\*\*)?\s*(?:does not exist|do not exist|does not|do not|is not|are not|"
    r"no longer|does n't|doesn't|don't|was removed|were removed|is absent|is gone|"
    r"is a setting|is not an entity)\b",
    re.I,
)
BEFORE_WINDOW = 160
AFTER_WINDOW = 60


def negated_nearby(text: str, start: int, end: int) -> bool:
    """True when the surrounding sentence says the name does not exist."""
    before = text[max(0, start - BEFORE_WINDOW):start]
    # Stop at a paragraph break so a negation in a previous paragraph does not carry over.
    before = before.rsplit("\n\n", 1)[-1]
    if NEGATION_BEFORE_RE.search(before):
        return True
    after = text[end:end + AFTER_WINDOW].split("\n\n", 1)[0]
    return bool(NEGATION_AFTER_RE.search(after))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", default="2026.2")
    ap.add_argument("--root", default="docs")
    ap.add_argument("--strict", action="store_true", help="exit non-zero when anything is unknown")
    ap.add_argument(
        "--no-negation",
        action="store_true",
        help="report absent names even when the surrounding sentence says they do not exist",
    )
    args = ap.parse_args()

    entities, namespaces, other_known = load_schema(args.version)
    allowed = load_allowed(entities) | other_known
    prefixes = namespace_prefixes(entities)
    token_re = entity_token_re(namespaces)

    # docfx renders a .NET generic by escaping the angle brackets, so a verb argument type
    # arrives as array<System.Collections.Generic.KeyValuePair~System.String_System.Object~>
    # and the scanner pulls two names out of it that no entity file lists on their own.
    # Whatever the scanner finds inside a type the schema really declares is itself real,
    # so seed the known set with exactly that rather than allowlisting each page that
    # quotes a verb signature.
    for known in list(other_known):
        allowed.update(token_re.findall(known))

    # Reuse the validator's inheritance-aware member lookup so a member reference in
    # prose is held to the same standard as one inside a query.
    members = None
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from validate_swql import SchemaIndex

        index = SchemaIndex(args.version)

        # Verbs are members too. Naming one as Orion.Nodes.Unmanage is the normal way to
        # write it in prose, so the lookup has to include them or every verb reference in
        # the documentation is reported as a missing property.
        verbs_by_entity: dict[str, set[str]] = {}
        for name, rec in index.entities.items():
            chain = (rec.get("inheritance") or []) + [name]
            names = set()
            for anc in chain:
                arec = index.entities.get(anc)
                if arec:
                    names.update(v["name"].lower() for v in arec.get("verbs") or [])
            verbs_by_entity[name] = names

        def members(entity):
            props, navs = index.members(entity)
            verbs = verbs_by_entity.get(entity, set())
            return {**props, **{v: "verb" for v in verbs}}, navs

    except Exception as exc:  # pragma: no cover
        print(f"note: member checking unavailable ({exc}); names checked as entities only")

    scan_root = os.path.join(ROOT, args.root)
    files = []
    for dirpath, dirnames, filenames in os.walk(scan_root):
        dirnames[:] = [d for d in dirnames if d not in {".git", ".orionsdk", ".schema-versions"}]
        files.extend(os.path.join(dirpath, f) for f in filenames if f.endswith(".md"))
    files.sort()

    unknown: dict[str, set[str]] = defaultdict(set)
    reasons: dict[str, str] = {}
    wrong_types: list[tuple[str, str, str, str]] = []
    bad_netobjects: list[tuple[str, str]] = []
    netobject_prefixes = load_netobject_prefixes()
    bad_rights: list[tuple[str, str]] = []
    known_rights = load_rights(args.version)
    rights_checked = 0
    netobjects_checked = 0
    types_checked = 0
    checked = 0
    negated = 0

    skipped = 0
    for path in files:
        text = open(path, encoding="utf-8", errors="replace").read()
        if GENERATED_MARKER in text[:400]:
            skipped += 1
            continue
        rel = os.path.relpath(path, ROOT)
        for m in token_re.finditer(text):
            token = m.group(0).rstrip(".")
            if token.endswith(NOISE_SUFFIXES) or token.startswith(DOTNET_NAMESPACES):
                continue
            checked += 1
            if token in entities or token in allowed:
                continue
            ok, reason = resolves(token, entities, prefixes, members)
            if ok:
                continue
            if not args.no_negation and negated_nearby(text, m.start(), m.end()):
                negated += 1
                continue
            unknown[token].add(rel)
            reasons[token] = reason

        if members is not None:
            for token, claimed, actual in type_claims(text, members):
                wrong_types.append((rel, token, claimed, actual))
            types_checked += len(PROPERTY_TYPE_RE.findall(" ".join(text.split())))

        if netobject_prefixes:
            netobjects_checked += len(NETOBJECT_RE.findall(" ".join(text.split())))
            for written in netobject_claims(text, netobject_prefixes):
                bad_netobjects.append((rel, written))

        if known_rights:
            rights_checked += len(RIGHT_RE.findall(" ".join(text.split())))
            for name in right_claims(text, known_rights):
                bad_rights.append((rel, name))

    print(
        f"{len(files) - skipped} authored file(s), {checked} entity reference(s) checked "
        f"({skipped} generated file(s) skipped, {negated} absent name(s) named inside a "
        f"negation and accepted); {types_checked} property-type, "
        f"{netobjects_checked} NetObject and {rights_checked} rights claim(s) checked"
    )

    if wrong_types:
        print(f"\n{len(wrong_types)} property type(s) the schema contradicts:", file=sys.stderr)
        for rel, token, claimed, actual in wrong_types:
            print(f"  - {rel}: {token} is described as {claimed}, "
                  f"but the schema declares {actual}", file=sys.stderr)

    if bad_netobjects:
        print(f"\n{len(bad_netobjects)} NetObject prefix(es) the reference does not list:",
              file=sys.stderr)
        for rel, written in bad_netobjects:
            print(f"  - {rel}: {written}", file=sys.stderr)
        print("      Prefixes are in data/reference/netobject-types.json.", file=sys.stderr)

    if bad_rights:
        print(f"\n{len(bad_rights)} right(s) the schema does not declare:", file=sys.stderr)
        for rel, name in bad_rights:
            print(f"  - {rel}: {name}", file=sys.stderr)
        print(f"      Known rights: {', '.join(sorted(known_rights))}", file=sys.stderr)

    if not unknown:
        if not wrong_types and not bad_netobjects and not bad_rights:
            print("every entity named in the documentation exists in the schema")
            return
        if args.strict:
            sys.exit(1)
        return

    print(f"\n{len(unknown)} name(s) not found in the {args.version} schema:", file=sys.stderr)
    for token in sorted(unknown):
        where = ", ".join(sorted(unknown[token])[:3])
        detail = reasons.get(token) or ""
        near = sorted((e for e in entities if token.split(".")[-1].lower() in e.lower()), key=len)[:2]
        hint = f"  (did you mean {', '.join(near)}?)" if near else ""
        print(f"  - {token}{hint}", file=sys.stderr)
        if detail:
            print(f"      {detail}", file=sys.stderr)
        print(f"      in: {where}", file=sys.stderr)
    print(
        f"\nIf a name is deliberate (explaining a rename or a removal), add it to\n"
        f"{os.path.relpath(ALLOWLIST, ROOT)} with a comment saying why.",
        file=sys.stderr,
    )
    if args.strict:
        sys.exit(1)


if __name__ == "__main__":
    main()

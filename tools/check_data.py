#!/usr/bin/env python3
"""Consistency checks over the generated data.

Extraction is regex-based against generated HTML, so it can degrade quietly when
SolarWinds changes their docfx template: a selector stops matching, a section comes
back empty, and the output still looks like valid JSON. These assertions turn that
silent degradation into a failed build.

    python tools/check_data.py --version 2026.2
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Floors, not targets. They exist to catch a collapse (a selector that stopped matching
# returns near-zero), not to pin exact counts, which legitimately move between releases.
FLOORS = {
    "entities": 1500,
    "properties": 12000,
    "verbs": 500,
    "verbsWithTypedParameters": 400,
    "relationshipEdges": 2000,
    "creatableEntities": 100,
}

# Entities that must always exist. If one of these is missing, the extraction is broken
# rather than the schema having changed.
CORE_ENTITIES = [
    "Orion.Nodes",
    "Orion.NPM.Interfaces",
    "Orion.Volumes",
    "Orion.Engines",
    "Orion.StatusInfo",
    "Orion.AlertActive",
    "Orion.AlertObjects",
    "Orion.AlertConfigurations",
    "System.Entity",
    "System.ManagedEntity",
    "Metadata.Entity",
    "Metadata.Verb",
    "Metadata.VerbArgument",
    "Metadata.Property",
]

# (entity, verb, ordered parameter names) tuples verified by hand against the published
# Swagger contract. These pin the join between the HTML and the Swagger, which is the
# part of extraction most likely to break without anyone noticing.
CORE_VERBS = [
    ("Orion.Nodes", "Unmanage", ["netObjectId", "unmanageTime", "remanageTime", "isRelative", "allowOverlapping"]),
    ("Orion.Nodes", "Remanage", ["netObjectId"]),
    ("Orion.Nodes", "PollNow", ["netObjectId"]),
]


class Checker:
    def __init__(self):
        self.failures: list[str] = []
        self.notes: list[str] = []

    def fail(self, msg):
        self.failures.append(msg)

    def note(self, msg):
        self.notes.append(msg)

    def require(self, cond, msg):
        if not cond:
            self.fail(msg)
        return cond


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", default="2026.2")
    args = ap.parse_args()

    root = os.path.join(ROOT, "data", "schema", args.version)
    c = Checker()

    if not os.path.isdir(root):
        sys.exit(f"error: no data at {root}; run: make data VERSION={args.version}")

    manifest = load(os.path.join(root, "manifest.json"))
    index = load(os.path.join(root, "index.json"))
    verbs = load(os.path.join(root, "verbs.json"))
    edges = load(os.path.join(root, "relationships.json"))

    counts = manifest["counts"]
    for key, floor in FLOORS.items():
        c.require(counts.get(key, 0) >= floor, f"{key} is {counts.get(key, 0)}, below the floor of {floor}")

    c.require(counts.get("skippedPages", 0) == 0, f"{counts.get('skippedPages')} schema page(s) failed to parse")

    # The index and the per-namespace files must describe the same set of entities.
    entities = {}
    ent_dir = os.path.join(root, "entities")
    for fname in sorted(os.listdir(ent_dir)):
        if fname.endswith(".json"):
            for rec in load(os.path.join(ent_dir, fname)):
                entities[rec["entity"]] = rec
    c.require(
        len(entities) == len(index) == counts["entities"],
        f"count mismatch: {len(entities)} in entity files, {len(index)} in index, {counts['entities']} in manifest",
    )

    for name in CORE_ENTITIES:
        c.require(name in entities, f"core entity {name} is missing from the extract")

    # Every inheritance ancestor and every relationship target should itself be a known
    # entity. A dangling reference means a link was parsed but its page was not.
    dangling_parents = Counter()
    for rec in entities.values():
        for anc in rec["inheritance"]:
            if anc not in entities:
                dangling_parents[anc] += 1
    if dangling_parents:
        c.note(f"{len(dangling_parents)} inheritance target(s) not present as entities: {dict(dangling_parents.most_common(5))}")

    dangling_targets = Counter()
    for edge in edges:
        if edge["to"] not in entities:
            dangling_targets[edge["to"]] += 1
    if dangling_targets:
        c.note(f"{len(dangling_targets)} relationship target(s) not present as entities: {dict(dangling_targets.most_common(5))}")

    # Properties must have a name and a type.
    bad_props = [
        f"{rec['entity']}.{p['name']}"
        for rec in entities.values()
        for p in rec["properties"]
        if not p.get("name") or not p.get("type")
    ]
    c.require(not bad_props, f"{len(bad_props)} property/properties missing a name or type, e.g. {bad_props[:3]}")

    # The hand-verified verb signatures must survive the HTML-to-Swagger join.
    by_key = {(v["entity"], v["name"]): v for v in verbs}
    for entity, verb, expected in CORE_VERBS:
        rec = by_key.get((entity, verb))
        if not c.require(rec is not None, f"verb {entity}.{verb} is missing"):
            continue
        actual = [p["name"] for p in rec.get("parameters", [])]
        c.require(
            actual == expected,
            f"{entity}.{verb} parameters changed: expected {expected}, got {actual}",
        )

    typed = sum(1 for v in verbs if v.get("parameters"))
    c.require(
        typed == counts["verbsWithTypedParameters"],
        f"typed-verb count mismatch: {typed} in verbs.json, {counts['verbsWithTypedParameters']} in manifest",
    )

    # Reference data, when present.
    ref = os.path.join(ROOT, "data", "reference")
    if os.path.isdir(ref):
        funcs = load(os.path.join(ref, "swql-functions.json"))
        c.require(len(funcs) >= 55, f"only {len(funcs)} SWQL functions extracted")
        for required in ["IsNull", "GetDate", "GetUtcDate", "DateTrunc", "ToUpper", "Count", "String_Agg"]:
            c.require(
                any(f["name"].lower() == required.lower() for f in funcs),
                f"SWQL function {required} is missing from the reference",
            )

        statuses = load(os.path.join(ref, "status-codes.json"))
        by_id = {s["status"]: s["name"] for s in statuses}
        for sid, name in [(0, "Unknown"), (1, "Up"), (2, "Down"), (3, "Warning"), (9, "Unmanaged")]:
            c.require(by_id.get(sid) == name, f"status {sid} should be {name}, got {by_id.get(sid)!r}")

        netobjects = load(os.path.join(ref, "netobject-types.json"))
        c.require(len(netobjects) >= 100, f"only {len(netobjects)} NetObject type rows")
        missing = [n["entity"] for n in netobjects if not n.get("inCurrentSchema")]
        if missing:
            c.note(f"{len(missing)} workbook entity/entities absent from the {args.version} schema (expected; see reconciliation.json)")

    # Completeness of the authored reference pages against the extracted data. A function
    # reference that quietly drops a function is worse than one that never claimed to be
    # complete, because a reader takes its silence as "SWIS does not have that".
    funcs_md = os.path.join(ROOT, "docs", "swql", "functions.md")
    if os.path.isfile(funcs_md) and os.path.isdir(ref):
        text = open(funcs_md, encoding="utf-8", errors="replace").read()
        names = [f["name"] for f in load(os.path.join(ref, "swql-functions.json"))]
        missing = [n for n in names if not re.search(rf"\b{re.escape(n)}\b", text, re.I)]
        c.require(
            not missing,
            f"docs/swql/functions.md does not mention {len(missing)} function(s): "
            f"{', '.join(missing[:8])}",
        )

    for n in c.notes:
        print(f"note: {n}")
    if c.failures:
        print(f"\n{len(c.failures)} check(s) FAILED:", file=sys.stderr)
        for f in c.failures:
            print(f"  - {f}", file=sys.stderr)
        sys.exit(1)

    print(
        f"all checks passed for {args.version}: "
        f"{counts['entities']} entities, {counts['properties']} properties, "
        f"{counts['verbs']} verbs, {counts['relationshipEdges']} relationship edges"
    )


if __name__ == "__main__":
    main()

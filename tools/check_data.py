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
import glob
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

    # Entity counts quoted in the module pages. These are the claims most likely to go
    # quietly wrong: rebuilding for another platform version changes every one of them,
    # and nothing about the page looks stale afterwards.
    prefix_claim = re.compile(r"\|\s*`([A-Z][\w.]*\.)`\s*\|\s*(\d+)\s*\|")
    entity_names = [rec["entity"] for rec in index]
    claim_files = sorted(glob.glob(os.path.join(ROOT, "docs", "modules", "*.md")))
    claim_files.append(os.path.join(ROOT, "docs", "platform", "modules.md"))
    claims = wrong = 0
    for path in claim_files:
        if not os.path.isfile(path):
            continue
        text = open(path, encoding="utf-8", errors="replace").read()
        for m in prefix_claim.finditer(text):
            prefix, claimed = m.group(1), int(m.group(2))
            actual = sum(1 for n in entity_names if n.startswith(prefix))
            claims += 1
            if actual != claimed:
                wrong += 1
                c.fail(
                    f"{os.path.relpath(path, ROOT)} says {prefix} has {claimed} entities; "
                    f"the {args.version} schema has {actual}"
                )
    if claims and not wrong:
        c.note(f"{claims} namespace count(s) quoted in the module pages all match the schema")

    # SolarWinds sample scripts cited by name. Several pages say "adapt SolarWinds' own
    # X.ps1", which is only useful if X.ps1 exists. This needs the SDK checkout, so it is
    # skipped rather than failed when one is not present.
    sdk_dir = os.path.join(ROOT, ".orionsdk")
    if os.path.isdir(sdk_dir):
        sdk_files = {f for _, _, fs in os.walk(sdk_dir) for f in fs}
        own_files = {
            os.path.basename(p)
            for p in glob.glob(os.path.join(ROOT, "scripts", "**", "*"), recursive=True)
        }
        # The lookbehind keeps a hyphenated name whole: without it
        # Set-NodeMaintenanceWindow.ps1 is read as NodeMaintenanceWindow.ps1.
        script_re = re.compile(r"(?<![\w.-])([A-Za-z][\w.-]*\.ps1)\b")
        cited = 0
        for path in sorted(glob.glob(os.path.join(ROOT, "docs", "**", "*.md"), recursive=True)):
            text = open(path, encoding="utf-8", errors="replace").read()
            for name in sorted(set(script_re.findall(text))):
                cited += 1
                if name not in sdk_files and name not in own_files:
                    c.fail(
                        f"{os.path.relpath(path, ROOT)} cites {name}, which is in neither "
                        f"the OrionSDK checkout nor this repository's scripts/"
                    )
        if cited:
            c.note(f"{cited} cited sample script name(s) checked against the OrionSDK checkout")
    else:
        c.note("no .orionsdk checkout, so cited sample script names were not checked")

    # PowerShell cmdlet names. The SwisPowerShell module exports seven, and an invented
    # eighth reads exactly like the real ones. Sample scripts in this repository follow the
    # same Verb-Noun convention, so their own names are allowed by filename.
    swis_cmdlets = {
        "Connect-Swis",
        "Get-SwisData",
        "Get-SwisObject",
        "New-SwisObject",
        "Set-SwisObject",
        "Remove-SwisObject",
        "Invoke-SwisVerb",
    }
    script_names = {
        os.path.splitext(os.path.basename(p))[0]
        for p in glob.glob(os.path.join(ROOT, "scripts", "**", "*.ps1"), recursive=True)
    }
    cmdlet_re = re.compile(r"\b((?:Connect|Get|Set|New|Remove|Invoke|Export|Import|Add|Update)-Swis[A-Za-z]*)\b")
    for path in sorted(
        glob.glob(os.path.join(ROOT, "docs", "**", "*.md"), recursive=True)
        + glob.glob(os.path.join(ROOT, "scripts", "**", "*"), recursive=True)
    ):
        if not os.path.isfile(path) or "reference" in os.path.relpath(path, ROOT).split(os.sep):
            continue
        if not path.endswith((".md", ".ps1")):
            continue
        text = open(path, encoding="utf-8", errors="replace").read()
        for name in set(cmdlet_re.findall(text)):
            if name not in swis_cmdlets and name not in script_names:
                c.fail(
                    f"{os.path.relpath(path, ROOT)} uses {name}, which is neither a "
                    f"SwisPowerShell cmdlet nor a script in this repository"
                )

    # Status tables written by hand. The generated one under docs/reference cannot drift,
    # but a narrative page that reproduces the table can, and a wrong rank quietly inverts
    # what a reader believes about rollup severity.
    status_path = os.path.join(ROOT, "data", "reference", "status-codes.json")
    if os.path.isfile(status_path):
        by_status = {s["status"]: (s["name"], s["rank"]) for s in load(status_path)}
        row_re = re.compile(r"\|\s*(\d+)\s*\|\s*\*{0,2}([A-Za-z ]+?)\*{0,2}\s*\|\s*(\d+)\s*\|")
        for path in sorted(glob.glob(os.path.join(ROOT, "docs", "**", "*.md"), recursive=True)):
            if "reference" in os.path.relpath(path, ROOT).split(os.sep):
                continue  # generated
            text = open(path, encoding="utf-8", errors="replace").read()
            if "status" not in os.path.basename(path).lower():
                continue
            for m in row_re.finditer(text):
                sid, name, rank = int(m.group(1)), m.group(2).strip(), int(m.group(3))
                expected = by_status.get(sid)
                if expected and (expected[0].strip() != name or expected[1] != rank):
                    c.fail(
                        f"{os.path.relpath(path, ROOT)} says status {sid} is "
                        f"{name!r} rank {rank}; the reference says "
                        f"{expected[0]!r} rank {expected[1]}"
                    )

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

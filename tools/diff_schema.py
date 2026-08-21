#!/usr/bin/env python3
"""Compare two extracted SWIS schema versions and report what changed.

An upgrade can break an automation quietly. A property is dropped, an entity is renamed,
a verb gains a required argument, and the script that has worked for two years starts
returning nothing or failing on a type error. This produces the list of changes that
could do that, so an upgrade can be reviewed rather than discovered.

Changes are classified by the risk they carry for existing code:

  breaking      an entity, property, verb, or required argument that existed and no
                longer does, or a verb whose parameter order changed
  behavioural   a verb argument that became required, or an entity that lost an operation
  additive      new entities, properties, verbs, and optional arguments

    python tools/diff_schema.py --from 2025.4 --to 2026.2
    python tools/diff_schema.py --from 2025.4 --to 2026.2 --markdown > changes.md
    python tools/diff_schema.py --from 2025.4 --to 2026.2 --json

Both versions must already be extracted. Build one with:
    python tools/build_schema_data.py --source <gh-pages> --version 2025.4 --out <dir>
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_version(root: str, version: str) -> dict[str, dict]:
    ent_dir = os.path.join(root, version, "entities")
    if not os.path.isdir(ent_dir):
        sys.exit(
            f"error: no extracted schema for {version} at {ent_dir}\n"
            f"build it with: python tools/build_schema_data.py --source <gh-pages> "
            f"--version {version} --out {root}"
        )
    entities = {}
    for fname in sorted(os.listdir(ent_dir)):
        if fname.endswith(".json"):
            with open(os.path.join(ent_dir, fname), encoding="utf-8") as fh:
                for rec in json.load(fh):
                    entities[rec["entity"]] = rec
    return entities


def squash(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def guess_rename(missing: str, added: set[str]) -> str | None:
    """Match a removed entity to an added one that is probably the same thing.

    Renames between releases are usually a case change (Orion.VIM.LUNs to
    Orion.VIM.Luns) or a namespace move that keeps the leaf (Orion.NPM.UCSBlades to
    Orion.UCS.Blades). Both are cheap to detect and worth flagging, because they read as
    a deletion plus an unrelated addition otherwise.
    """
    target = squash(missing)
    for cand in added:
        if squash(cand) == target:
            return cand

    leaf = squash(missing.split(".")[-1])
    # A generic leaf such as "statistics" or "settings" matches half the schema, so a
    # leaf match alone is not evidence. Require the candidate to share the root namespace
    # as well, which is what separates Orion.NPM.UCSBlades -> Orion.UCS.Blades from
    # Cortex...Firewall.Statistics -> Orion.Cloud.Gcp.GkePodStatistics.
    if len(leaf) < 6:
        return None
    root = missing.split(".")[0].lower()
    hits = [
        c for c in added if squash(c).endswith(leaf) and c.split(".")[0].lower() == root
    ]
    return sorted(hits, key=len)[0] if hits else None


def diff(old: dict, new: dict) -> dict:
    old_names, new_names = set(old), set(new)
    added_names = new_names - old_names
    removed_names = old_names - new_names

    result: dict = {
        "addedEntities": sorted(added_names),
        "removedEntities": [],
        "renamedEntities": [],
        "changedEntities": [],
        "verbChanges": [],
    }

    for name in sorted(removed_names):
        rename = guess_rename(name, added_names)
        if rename:
            result["renamedEntities"].append({"from": name, "to": rename})
        else:
            result["removedEntities"].append(name)
    renamed_targets = {r["to"] for r in result["renamedEntities"]}
    result["addedEntities"] = [n for n in result["addedEntities"] if n not in renamed_targets]

    for name in sorted(old_names & new_names):
        o, n = old[name], new[name]
        entry: dict = {"entity": name}

        o_props = {p["name"] for p in o["properties"]}
        n_props = {p["name"] for p in n["properties"]}
        if o_props - n_props:
            entry["removedProperties"] = sorted(o_props - n_props)
        if n_props - o_props:
            entry["addedProperties"] = sorted(n_props - o_props)

        # A property whose type changed can break a client that binds it to a typed field.
        o_types = {p["name"]: p["type"] for p in o["properties"]}
        n_types = {p["name"]: p["type"] for p in n["properties"]}
        retyped = [
            {"property": k, "from": o_types[k], "to": n_types[k]}
            for k in sorted(o_props & n_props)
            if o_types[k] != n_types[k]
        ]
        if retyped:
            entry["retypedProperties"] = retyped

        o_navs = {r["name"] for r in o["sourceRelationships"] + o["targetRelationships"]}
        n_navs = {r["name"] for r in n["sourceRelationships"] + n["targetRelationships"]}
        if o_navs - n_navs:
            entry["removedNavigations"] = sorted(o_navs - n_navs)
        if n_navs - o_navs:
            entry["addedNavigations"] = sorted(n_navs - o_navs)

        if set(o["supportedOperations"]) != set(n["supportedOperations"]):
            entry["operations"] = {"from": o["supportedOperations"], "to": n["supportedOperations"]}

        o_verbs = {v["name"]: v for v in o["verbs"]}
        n_verbs = {v["name"]: v for v in n["verbs"]}
        if set(o_verbs) - set(n_verbs):
            entry["removedVerbs"] = sorted(set(o_verbs) - set(n_verbs))
        if set(n_verbs) - set(o_verbs):
            entry["addedVerbs"] = sorted(set(n_verbs) - set(o_verbs))

        for vname in sorted(set(o_verbs) & set(n_verbs)):
            ov, nv = o_verbs[vname], n_verbs[vname]
            op = [p["name"] for p in ov.get("parameters") or []]
            np_ = [p["name"] for p in nv.get("parameters") or []]
            if op == np_:
                continue
            change: dict = {"entity": name, "verb": vname, "from": op, "to": np_}

            # Invoke sends a positional array and the names never travel on the wire, so
            # a rename that only changes capitalisation cannot affect a caller. Treating
            # it as breaking would bury the real findings in noise.
            if [p.lower() for p in op] == [p.lower() for p in np_]:
                change["severity"] = "cosmetic"
                change["reason"] = "parameter names differ only in capitalisation; positional callers are unaffected"
                result["verbChanges"].append(change)
                continue

            # A reordered prefix silently sends the wrong value into the wrong slot. That
            # is worse than a removed argument, which at least fails loudly.
            common = min(len(op), len(np_))
            if [p.lower() for p in op[:common]] != [p.lower() for p in np_[:common]]:
                change["severity"] = "breaking"
                change["reason"] = "positional argument order changed"
            elif len(np_) < len(op):
                change["severity"] = "breaking"
                change["reason"] = "argument removed"
            else:
                newly = set(np_) - set(op)
                required_new = {
                    p["name"] for p in (nv.get("parameters") or []) if p.get("required")
                } & newly
                if required_new:
                    change["severity"] = "behavioural"
                    change["reason"] = f"new required argument: {', '.join(sorted(required_new))}"
                else:
                    change["severity"] = "additive"
                    change["reason"] = "optional argument appended"
            result["verbChanges"].append(change)

        if len(entry) > 1:
            result["changedEntities"].append(entry)

    return result


def summarize(d: dict) -> dict:
    counts = defaultdict(int)
    for c in d["verbChanges"]:
        counts[c["severity"]] += 1
    breaking, behavioural = counts["breaking"], counts["behavioural"]
    return {
        "cosmeticVerbChanges": counts["cosmetic"],
        "addedEntities": len(d["addedEntities"]),
        "removedEntities": len(d["removedEntities"]),
        "renamedEntities": len(d["renamedEntities"]),
        "changedEntities": len(d["changedEntities"]),
        "entitiesLosingProperties": sum(1 for e in d["changedEntities"] if e.get("removedProperties")),
        "entitiesLosingNavigations": sum(1 for e in d["changedEntities"] if e.get("removedNavigations")),
        "removedVerbs": sum(len(e.get("removedVerbs", [])) for e in d["changedEntities"]),
        "addedVerbs": sum(len(e.get("addedVerbs", [])) for e in d["changedEntities"]),
        "breakingVerbChanges": breaking,
        "behaviouralVerbChanges": behavioural,
    }


def render_markdown(d: dict, old_v: str, new_v: str) -> str:
    s = summarize(d)
    out = [
        "<!-- GENERATED FILE. Do not edit by hand.",
        "     Produced by tools/diff_schema.py. -->",
        "",
        f"# Schema changes: {old_v} to {new_v}",
        "",
        "What changed in the SWIS schema between these two platform versions, and which "
        "of those changes can break code that already works.",
        "",
        "Read the removals first. Additions cannot break anything you have already "
        "written; removals and reordered verb arguments can, and the second kind fails "
        "quietly because Invoke sends a positional array with no names in it.",
        "",
        "## Summary",
        "",
        "| Change | Count |",
        "| --- | ---: |",
    ]
    labels = {
        "addedEntities": "Entities added",
        "removedEntities": "Entities removed",
        "renamedEntities": "Entities renamed",
        "changedEntities": "Entities otherwise changed",
        "entitiesLosingProperties": "Entities that lost a property",
        "entitiesLosingNavigations": "Entities that lost a navigation property",
        "addedVerbs": "Verbs added",
        "removedVerbs": "Verbs removed",
        "breakingVerbChanges": "Verb signatures changed (breaking)",
        "behaviouralVerbChanges": "Verb signatures changed (new required argument)",
        "cosmeticVerbChanges": "Verb parameter names recased (no caller impact)",
    }
    for key, label in labels.items():
        out.append(f"| {label} | {s[key]} |")
    out.append("")

    if d["renamedEntities"]:
        out += [
            "## Renamed entities",
            "",
            "These read as a removal plus an unrelated addition unless you know to pair "
            "them. A query naming the old form returns an error rather than an empty "
            "result, so these surface quickly.",
            "",
            "| Was | Is now |",
            "| --- | --- |",
        ]
        for r in d["renamedEntities"]:
            out.append(f"| `{r['from']}` | `{r['to']}` |")
        out.append("")

    if d["removedEntities"]:
        out += [
            "## Removed entities",
            "",
            f"{len(d['removedEntities'])} entities present in {old_v} are absent from "
            f"{new_v}. Some are genuine removals; others belong to a module that was "
            "restructured. Check each against your own server before concluding it is gone.",
            "",
        ]
        for name in d["removedEntities"]:
            out.append(f"- `{name}`")
        out.append("")

    breaking = [c for c in d["verbChanges"] if c["severity"] == "breaking"]
    behavioural = [c for c in d["verbChanges"] if c["severity"] == "behavioural"]

    if breaking:
        out += [
            "## Verb signature changes that break callers",
            "",
            "Invoke arguments are positional. When the order of a shared prefix changes, "
            "an existing call still has the right number of arguments and sends them into "
            "the wrong slots, so it can fail with a confusing type error or, worse, "
            "succeed against the wrong values. Audit every call site for these.",
            "",
            "| Entity | Verb | Was | Is now | Why it breaks |",
            "| --- | --- | --- | --- | --- |",
        ]
        for c in breaking:
            out.append(
                f"| `{c['entity']}` | `{c['verb']}` | `({', '.join(c['from'])})` "
                f"| `({', '.join(c['to'])})` | {c['reason']} |"
            )
        out.append("")

    if behavioural:
        out += [
            "## Verbs with a new required argument",
            "",
            "Existing calls will be rejected until the new argument is supplied.",
            "",
            "| Entity | Verb | Was | Is now | New requirement |",
            "| --- | --- | --- | --- | --- |",
        ]
        for c in behavioural:
            out.append(
                f"| `{c['entity']}` | `{c['verb']}` | `({', '.join(c['from'])})` "
                f"| `({', '.join(c['to'])})` | {c['reason']} |"
            )
        out.append("")

    losers = [e for e in d["changedEntities"] if e.get("removedProperties") or e.get("removedNavigations")]
    if losers:
        out += [
            "## Entities that lost properties or navigation properties",
            "",
            "A query selecting a removed property fails outright. A query selecting a "
            "removed navigation property fails the same way, but a report built on one "
            "may simply go empty, which is easier to miss.",
            "",
            "| Entity | Removed properties | Removed navigations |",
            "| --- | --- | --- |",
        ]
        for e in losers:
            props = ", ".join(f"`{p}`" for p in e.get("removedProperties", [])) or ""
            navs = ", ".join(f"`{p}`" for p in e.get("removedNavigations", [])) or ""
            out.append(f"| `{e['entity']}` | {props} | {navs} |")
        out.append("")

    retyped = [e for e in d["changedEntities"] if e.get("retypedProperties")]
    if retyped:
        out += [
            "## Properties whose type changed",
            "",
            "These do not fail a SWQL query, but they can fail a typed client that binds "
            "the column to a field.",
            "",
            "| Entity | Property | Was | Is now |",
            "| --- | --- | --- | --- |",
        ]
        for e in retyped:
            for r in e["retypedProperties"]:
                out.append(f"| `{e['entity']}` | `{r['property']}` | `{r['from']}` | `{r['to']}` |")
        out.append("")

    added_verbs = [(e["entity"], v) for e in d["changedEntities"] for v in e.get("addedVerbs", [])]
    if added_verbs:
        out += [
            "## New verbs",
            "",
            f"{len(added_verbs)} verbs are available in {new_v} that were not in {old_v}.",
            "",
        ]
        by_ent = defaultdict(list)
        for ent, v in added_verbs:
            by_ent[ent].append(v)
        for ent, vs in sorted(by_ent.items()):
            out.append(f"- `{ent}`: {', '.join(f'`{v}`' for v in sorted(vs))}")
        out.append("")

    if d["addedEntities"]:
        out += [
            "## New entities",
            "",
            f"{len(d['addedEntities'])} entities are new in {new_v}.",
            "",
        ]
        by_ns = defaultdict(list)
        for name in d["addedEntities"]:
            by_ns[name.split(".")[0]].append(name)
        for ns, names in sorted(by_ns.items()):
            out.append(f"**{ns}** ({len(names)})")
            out.append("")
            for name in sorted(names):
                out.append(f"- `{name}`")
            out.append("")

    out += [
        "---",
        "",
        "Regenerate with:",
        "",
        "```bash",
        f"python3 tools/diff_schema.py --from {old_v} --to {new_v} --markdown",
        "```",
        "",
        "Neither version's schema is the authority for a specific server. Confirm against "
        "your own with `Metadata.Entity` and `Metadata.VerbArgument`; see "
        "[../../scripts/swql/08-schema-introspection.swql]"
        "(../../scripts/swql/08-schema-introspection.swql).",
    ]
    return "\n".join(out)


def render_text(d: dict, old_v: str, new_v: str) -> str:
    s = summarize(d)
    lines = [f"schema changes {old_v} -> {new_v}", ""]
    for k, v in s.items():
        lines.append(f"  {k:34} {v}")
    for c in d["verbChanges"]:
        if c["severity"] in ("breaking", "behavioural"):
            lines.append(
                f"\n  [{c['severity']}] {c['entity']}.{c['verb']}: {c['reason']}"
                f"\n      was ({', '.join(c['from'])})\n      now ({', '.join(c['to'])})"
            )
    for r in d["renamedEntities"]:
        lines.append(f"\n  [renamed] {r['from']} -> {r['to']}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="old", required=True, help="older version, e.g. 2025.4")
    ap.add_argument("--to", dest="new", required=True, help="newer version, e.g. 2026.2")
    ap.add_argument("--data-root", default=os.path.join(ROOT, "data", "schema"))
    ap.add_argument("--old-root", help="data root for the older version, if built elsewhere")
    ap.add_argument("--markdown", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    old = load_version(args.old_root or args.data_root, args.old)
    new = load_version(args.data_root, args.new)
    d = diff(old, new)

    if args.json:
        json.dump({"from": args.old, "to": args.new, "summary": summarize(d), **d}, sys.stdout, indent=1)
        sys.stdout.write("\n")
    elif args.markdown:
        print(render_markdown(d, args.old, args.new))
    else:
        print(render_text(d, args.old, args.new))


if __name__ == "__main__":
    main()

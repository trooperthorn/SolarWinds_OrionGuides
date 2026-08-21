#!/usr/bin/env python3
"""Explore the extracted SWIS schema without a live Orion server.

Answers the questions you actually have when writing a SWQL query or an automation:
which entity holds this data, what is this property called, which verbs can I invoke,
and how do I join from A to B.

    python tools/schema_query.py find node status         # entities/properties by keyword
    python tools/schema_query.py show Orion.Nodes         # one entity in full
    python tools/schema_query.py props Orion.Nodes --grep status
    python tools/schema_query.py verbs --grep unmanage    # verbs and their parameters
    python tools/schema_query.py verb Orion.Nodes Unmanage
    python tools/schema_query.py path Orion.Nodes Orion.APM.Application
    python tools/schema_query.py children System.ManagedEntity

Everything reads from data/schema/<version>/, so it works offline and returns the same
answers the published SolarWinds documentation would.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import deque

DEFAULT_VERSION = "2026.2"
DATA_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


class Schema:
    def __init__(self, version: str = DEFAULT_VERSION):
        self.version = version
        self.root = os.path.join(DATA_ROOT, "schema", version)
        if not os.path.isdir(self.root):
            available = []
            schema_root = os.path.join(DATA_ROOT, "schema")
            if os.path.isdir(schema_root):
                available = sorted(os.listdir(schema_root))
            sys.exit(
                f"error: no extracted schema for {version} at {self.root}\n"
                f"available: {', '.join(available) or '(none)'}\n"
                f"run tools/build_schema_data.py to generate it"
            )
        self._entities: dict[str, dict] | None = None
        self._index = self._load("index.json")

    def _load(self, name):
        with open(os.path.join(self.root, name), encoding="utf-8") as fh:
            return json.load(fh)

    @property
    def entities(self) -> dict[str, dict]:
        if self._entities is None:
            self._entities = {}
            ent_dir = os.path.join(self.root, "entities")
            for fname in sorted(os.listdir(ent_dir)):
                if fname.endswith(".json"):
                    for rec in self._load(os.path.join("entities", fname)):
                        self._entities[rec["entity"]] = rec
        return self._entities

    def get(self, name: str) -> dict:
        ents = self.entities
        if name in ents:
            return ents[name]
        matches = [k for k in ents if k.lower() == name.lower()]
        if len(matches) == 1:
            return ents[matches[0]]
        near = sorted(k for k in ents if name.lower() in k.lower())[:8]
        hint = "\n  ".join(near)
        sys.exit(f"error: unknown entity {name!r}" + (f"\ndid you mean:\n  {hint}" if near else ""))


# --------------------------------------------------------------------------------------
# Output helpers
# --------------------------------------------------------------------------------------


def emit(payload, as_json: bool, render):
    if as_json:
        json.dump(payload, sys.stdout, indent=1, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        render(payload)


def fmt_param(p: dict) -> str:
    req = "required" if p.get("required") else "optional"
    t = p.get("type", "?")
    if p.get("items"):
        t = f"array<{p['items'].get('type','?')}>"
    line = f"    {p['name']}: {t} ({req})"
    if p.get("description"):
        line += f"\n        {p['description']}"
    if p.get("enum"):
        line += f"\n        one of: {', '.join(map(str, p['enum']))}"
    if p.get("properties"):
        for sub, sp in p["properties"].items():
            line += f"\n        .{sub}: {sp.get('type','?')}"
    return line


# --------------------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------------------


def cmd_find(schema: Schema, args):
    terms = [t.lower() for t in args.terms]
    ent_hits, prop_hits = [], []

    for rec in schema.entities.values():
        hay = f"{rec['entity']} {rec['summary']}".lower()
        if all(t in hay for t in terms):
            ent_hits.append(
                {
                    "entity": rec["entity"],
                    "summary": rec["summary"][:160],
                    "properties": rec["counts"]["properties"],
                    "verbs": rec["counts"]["verbs"],
                }
            )
        if args.properties:
            for p in rec["properties"]:
                if all(t in f"{p['name']} {p['summary']}".lower() for t in terms):
                    prop_hits.append(
                        {
                            "entity": rec["entity"],
                            "property": p["name"],
                            "type": p["type"],
                            "summary": p["summary"][:120],
                        }
                    )

    ent_hits.sort(key=lambda r: (len(r["entity"]), r["entity"]))
    prop_hits.sort(key=lambda r: (r["entity"], r["property"]))
    payload = {"entities": ent_hits[: args.limit], "properties": prop_hits[: args.limit]}

    def render(p):
        print(f"entities matching {' '.join(terms)!r} ({len(ent_hits)} total)")
        for r in p["entities"]:
            print(f"  {r['entity']:<52} {r['properties']:>4}p {r['verbs']:>3}v  {r['summary']}")
        if args.properties:
            print(f"\nproperties matching {' '.join(terms)!r} ({len(prop_hits)} total)")
            for r in p["properties"]:
                print(f"  {r['entity']}.{r['property']} : {r['type']}  {r['summary']}")

    emit(payload, args.json, render)


def cmd_show(schema: Schema, args):
    rec = schema.get(args.entity)

    def render(r):
        print(f"{r['entity']}   [{schema.version}]")
        if r["summary"]:
            print(f"  {r['summary']}")
        if r["inheritance"]:
            print(f"  inherits: {' -> '.join(r['inheritance'])} -> {r['entity']}")
        print(f"  operations: {', '.join(r['supportedOperations']) or '(none declared)'}")
        for ac in r["accessControl"]:
            print(f"    {','.join(ac['operations']):<38} requires {ac['right']}")
        print(f"\n  properties ({len(r['properties'])})")
        for p in r["properties"][: args.limit]:
            s = f"  {p['summary'][:90]}" if p["summary"] else ""
            print(f"    {p['name']:<42} {p['type']:<28}{s}")
        if len(r["properties"]) > args.limit:
            print(f"    ... {len(r['properties']) - args.limit} more (use --limit)")
        # Both lists are navigable as <entity>.<name>; they differ only in which end of
        # the relationship definition this entity occupies.
        for bucket, label in (
            ("sourceRelationships", "this entity is the source; property leads to the target"),
            ("targetRelationships", "this entity is the target; property leads back to the source"),
        ):
            rels = r[bucket]
            if not rels:
                continue
            print(f"\n  {bucket} ({len(rels)}) - {label}")
            for rel in rels[: args.limit]:
                print(f"    {rel['name']:<42} -> {rel['type']:<44} {rel.get('kind','')}")
            if len(rels) > args.limit:
                print(f"    ... {len(rels) - args.limit} more (use --limit)")
        if r["verbs"]:
            print(f"\n  verbs ({len(r['verbs'])})")
            for v in r["verbs"]:
                print(f"    {v['name']:<42} {v.get('summary','')[:90]}")

    emit(rec, args.json, render)


def cmd_props(schema: Schema, args):
    rec = schema.get(args.entity)
    props = rec["properties"]
    if args.grep:
        g = args.grep.lower()
        props = [p for p in props if g in f"{p['name']} {p['summary']} {p['type']}".lower()]

    def render(_):
        print(f"{rec['entity']} properties ({len(props)} shown)")
        for p in props:
            s = f"  {p['summary']}" if p["summary"] else ""
            print(f"  {p['name']:<42} {p['type']:<28}{s}")

    emit(props, args.json, render)


def cmd_verbs(schema: Schema, args):
    verbs = json.load(open(os.path.join(schema.root, "verbs.json"), encoding="utf-8"))
    if args.entity:
        verbs = [v for v in verbs if v["entity"].lower() == args.entity.lower()]
    if args.grep:
        g = args.grep.lower()
        verbs = [v for v in verbs if g in f"{v['entity']} {v['name']} {v.get('summary','')}".lower()]

    def render(vs):
        print(f"{len(vs)} verb(s)")
        for v in vs[: args.limit]:
            params = v.get("parameters") or []
            sig = ", ".join(p["name"] for p in params)
            print(f"  {v['entity']}.{v['name']}({sig}) -> {v.get('returns','?')}")
            if v.get("summary"):
                print(f"      {v['summary'][:140]}")
        if len(vs) > args.limit:
            print(f"  ... {len(vs) - args.limit} more (use --limit)")

    emit(verbs, args.json, render)


def cmd_verb(schema: Schema, args):
    rec = schema.get(args.entity)
    matches = [v for v in rec["verbs"] if v["name"].lower() == args.verb.lower()]
    if not matches:
        names = ", ".join(v["name"] for v in rec["verbs"]) or "(none)"
        sys.exit(f"error: {rec['entity']} has no verb {args.verb!r}\navailable: {names}")
    v = matches[0]

    def render(v):
        print(f"{rec['entity']}.{v['name']}")
        if v.get("summary"):
            print(f"  {v['summary']}")
        print(f"  returns: {v.get('returns','?')}")
        print(f"  REST:    POST {v.get('restPath','')}")
        for ac in v.get("accessControl", []):
            print(f"  requires: {ac['right']}")
        params = v.get("parameters") or []
        if not params:
            print("  parameters: none")
        else:
            print(f"  parameters ({len(params)}):")
            for p in params:
                print(fmt_param(p))
        ordered = [p["name"] for p in params]
        print("\n  PowerShell:")
        arg_list = ", ".join(f"${n}" for n in ordered)
        print(f"    Invoke-SwisVerb $swis '{rec['entity']}' '{v['name']}' @({arg_list})")
        print("\n  REST body (positional array):")
        print(f"    {json.dumps([f'<{n}>' for n in ordered])}")

    emit(v, args.json, render)


def cmd_children(schema: Schema, args):
    parent = schema.get(args.entity)["entity"]
    kids = sorted(
        r["entity"] for r in schema.entities.values() if parent in r["inheritance"]
    )

    def render(k):
        print(f"{len(k)} entity/entities inherit from {parent}")
        for name in k[: args.limit]:
            print(f"  {name}")
        if len(k) > args.limit:
            print(f"  ... {len(k) - args.limit} more (use --limit)")

    emit(kids, args.json, render)


def cmd_path(schema: Schema, args):
    """Breadth-first search over navigation properties for a join path."""
    src = schema.get(args.source)["entity"]
    dst = schema.get(args.target)["entity"]
    ents = schema.entities

    # Both relationship tables list navigation properties usable *from* this entity.
    # "Source" means the entity is the source end of the relationship definition and the
    # property leads to the target; "Target" means it is the target end and the property
    # leads back to the source. Orion.Nodes.Interfaces (source) and
    # Orion.NPM.Interfaces.Node (target) are both valid SWQL, so both are navigable.
    adj: dict[str, list[tuple[str, str]]] = {}
    for name, rec in ents.items():
        adj[name] = [
            (rel["name"], rel["type"])
            for rel in rec["sourceRelationships"] + rec["targetRelationships"]
        ]

    # An entity also exposes everything its ancestors declare.
    for name, rec in ents.items():
        for anc in rec["inheritance"]:
            adj[name] = adj.get(name, []) + adj.get(anc, [])

    # Breadth-first, so shorter paths surface first. Cycles are excluded per-trail rather
    # than globally, otherwise the first path to reach an entity would hide every
    # alternate route through it. A visit budget keeps hub entities (Orion.Nodes alone
    # has 135 navigation properties) from exploding the search.
    found: list[list[tuple[str, str]]] = []
    queue = deque([(src, [], {src})])
    budget = 200_000
    best_depth = None
    while queue and budget > 0:
        node, trail, visited = queue.popleft()
        # Once the shortest depth is known, finish that level and stop: a longer route
        # to the same entity is never the answer someone wanted.
        if best_depth is not None and len(trail) >= best_depth:
            continue
        if len(trail) >= args.max_hops:
            continue
        for nav, target in adj.get(node, []):
            budget -= 1
            if budget <= 0:
                break
            step = trail + [(nav, target)]
            if target == dst:
                found.append(step)
                best_depth = min(best_depth or len(step), len(step))
                continue
            if target not in visited:
                queue.append((target, step, visited | {target}))

    # Same-length paths are ranked by the shorter, simpler navigation chain so the
    # canonical route (Component.Application.Node) beats an incidental one of equal hops.
    found.sort(key=lambda p: (len(p), len(".".join(nav for nav, _ in p)), [n for n, _ in p]))
    found = found[: args.max_paths]

    def render(_):
        if not found:
            print(f"no navigation path from {src} to {dst} within {args.max_hops} hops")
            print("join explicitly on key columns instead, e.g.")
            print(f"  SELECT ... FROM {src} a JOIN {dst} b ON a.<Key> = b.<Key>")
            return
        print(f"{len(found)} path(s) from {src} to {dst}, shortest first")
        for p in found:
            chain = ".".join(nav for nav, _ in p)
            print(f"\n  {src}.{chain}")
            cur = src
            for nav, target in p:
                print(f"    {cur} --{nav}--> {target}")
                cur = target
            print(f"\n    SELECT TOP 10 a.DisplayName, a.{chain}.DisplayName")
            print(f"    FROM {src} a")

    emit([[{"navigationProperty": n, "entity": t} for n, t in p] for p in found], args.json, render)


def cmd_stats(schema: Schema, args):
    manifest = json.load(open(os.path.join(schema.root, "manifest.json"), encoding="utf-8"))

    def render(m):
        print(f"SWIS schema {m['version']}  (source: {m['source']})")
        for k, v in m["counts"].items():
            print(f"  {k:<26} {v}")
        print("\n  entities per namespace")
        for ns, n in sorted(m["namespaceCounts"].items(), key=lambda kv: -kv[1]):
            print(f"    {ns:<18} {n}")

    emit(manifest, args.json, render)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--version", default=DEFAULT_VERSION, help="schema version to read")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of text")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("find", help="search entities (and properties) by keyword")
    p.add_argument("terms", nargs="+")
    p.add_argument("--properties", action="store_true", help="also search property names")
    p.add_argument("--limit", type=int, default=40)
    p.set_defaults(fn=cmd_find)

    p = sub.add_parser("show", help="show one entity in full")
    p.add_argument("entity")
    p.add_argument("--limit", type=int, default=60)
    p.set_defaults(fn=cmd_show)

    p = sub.add_parser("props", help="list an entity's properties")
    p.add_argument("entity")
    p.add_argument("--grep")
    p.set_defaults(fn=cmd_props)

    p = sub.add_parser("verbs", help="list verbs across the schema")
    p.add_argument("--entity")
    p.add_argument("--grep")
    p.add_argument("--limit", type=int, default=60)
    p.set_defaults(fn=cmd_verbs)

    p = sub.add_parser("verb", help="show one verb's parameters and call syntax")
    p.add_argument("entity")
    p.add_argument("verb")
    p.set_defaults(fn=cmd_verb)

    p = sub.add_parser("children", help="entities inheriting from a base entity")
    p.add_argument("entity")
    p.add_argument("--limit", type=int, default=80)
    p.set_defaults(fn=cmd_children)

    p = sub.add_parser("path", help="find a navigation path between two entities")
    p.add_argument("source")
    p.add_argument("target")
    p.add_argument("--max-hops", type=int, default=3)
    p.add_argument("--max-paths", type=int, default=5)
    p.set_defaults(fn=cmd_path)

    p = sub.add_parser("stats", help="schema counts and provenance")
    p.set_defaults(fn=cmd_stats)

    args = ap.parse_args()
    args.fn(Schema(args.version), args)


if __name__ == "__main__":
    main()

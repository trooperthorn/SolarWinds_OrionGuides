#!/usr/bin/env python3
"""Check verb signatures written in prose against the extracted contract.

Invoke arguments are positional. Names appear in SolarWinds' documentation and in their
Swagger contract but never travel on the wire, so argument order is the entire contract.
That makes a signature written into a sentence, ``Diff(configId1, configId2)``, one of the
highest-stakes claims in this repository: a reader who copies a reordered signature gets
no error, just the wrong result, and nothing about the call site looks wrong afterwards.

    python tools/check_signatures.py
    python tools/check_signatures.py --verbose     # list every confirmed signature

The rule is that the argument names shown must match the real ones, in order, starting
from the first. Prose abbreviates signatures constantly and legitimately: a paragraph
about which id space each verb takes writes ``DownloadConfig(nodeId)`` because the first
argument is the whole subject, and a paragraph about a version change writes the older
three-argument form on purpose. Neither is wrong, so a shown prefix of the real argument
list passes. What does not pass is a name that is not there, or names in the wrong order,
which are the failure modes that actually reach a reader as broken code.

Arity claims are checked separately, by ``check_counts.py``, which reads sentences like
"``Orion.Nodes.Unmanage`` takes four arguments". Between them a signature is covered for
both the names and the count.

A verb name is resolved against ``verbs.json``. When several entities publish the same
verb name, an entity named in the same paragraph picks the one meant; if that still leaves
signatures that disagree, the mention is skipped rather than guessed at.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# `Name(args)` in prose. The leading capital keeps this off SWQL function calls written
# in lower case and off ordinary parenthesised prose.
SIGNATURE_RE = re.compile(r"`(?P<name>[A-Z]\w+)\((?P<args>[^)`]*)\)`")
ENTITY_RE = re.compile(r"`(?P<ent>[A-Z]\w*(?:\.[A-Z]\w*)+)`")
ELISION_RE = re.compile(r"\.\.\.|…")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def normalise(name: str) -> str:
    """Fold an argument name for comparison.

    Array notation (``nodeId[]``), a trailing optional marker (``Reboot?``), and a type
    annotation (``componentId: number``) are all notation the prose adds around the real
    name. Case is folded too: the names never travel on the wire, so a case difference is
    cosmetic in exactly the way diff_schema.py already treats it.
    """
    name = name.split(":")[0]
    return re.sub(r"[^a-z0-9]", "", name.lower())


class Contract:
    def __init__(self, version: str) -> None:
        verbs_path = os.path.join(ROOT, "data", "schema", version, "verbs.json")
        self.verbs = json.load(open(verbs_path, encoding="utf-8"))
        self.by_name: dict[str, list[dict]] = defaultdict(list)
        for verb in self.verbs:
            self.by_name[verb["name"].lower()].append(verb)
        self.entities: set[str] = set()
        pattern = os.path.join(ROOT, "data", "schema", version, "entities", "*.json")
        for path in glob.glob(pattern):
            for record in json.load(open(path, encoding="utf-8")):
                self.entities.add(record["entity"])

    def resolve(self, name: str, nearby: list[str]) -> dict | None:
        """Pick the verb a mention means, or None when it stays ambiguous."""
        candidates = self.by_name.get(name.lower())
        if not candidates:
            return None
        narrowed = [c for c in candidates if c["entity"] in nearby]
        if narrowed:
            candidates = narrowed
        signatures = {
            tuple(normalise(p["name"]) for p in (c.get("parameters") or []))
            for c in candidates
        }
        if len(signatures) != 1:
            return None
        return candidates[0]


def shown_arguments(args: str) -> tuple[list[str], bool]:
    """Split the argument list written in prose. Returns (names, elided)."""
    elided = bool(ELISION_RE.search(args))
    names = []
    for part in args.split(","):
        part = part.strip()
        if not part or ELISION_RE.search(part):
            continue
        names.append(part)
    return names, elided


def compare(shown: list[str], actual: list[str], elided: bool) -> str | None:
    """Return a failure description, or None when the mention is consistent."""
    want = [normalise(a) for a in actual]
    got = [normalise(s) for s in shown]

    if elided:
        # An explicit elision means the shown names are a sample, so they only have to
        # appear in the real order.
        remaining = list(want)
        for name in got:
            if name not in remaining:
                return f"{name!r} is not an argument of this verb"
            remaining = remaining[remaining.index(name) + 1:]
        return None

    if len(got) > len(want):
        return f"{len(got)} arguments shown, the contract has {len(want)}"
    for index, (a, b) in enumerate(zip(got, want)):
        if a != b:
            if a in want:
                return (f"argument {index + 1} is {shown[index]!r}, but the contract has "
                        f"it at position {want.index(a) + 1}")
            return f"argument {index + 1} is {shown[index]!r}, the contract has {actual[index]!r}"
    return None


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", default="2026.2")
    ap.add_argument("--verbose", action="store_true", help="list every confirmed signature")
    args = ap.parse_args()

    contract = Contract(args.version)

    files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, "docs")):
        # docs/reference is generated from the same contract, so checking it proves nothing.
        dirnames[:] = [d for d in dirnames if d not in {"reference", ".git"}]
        files += [os.path.join(dirpath, f) for f in filenames if f.endswith(".md")]

    checked = skipped = 0
    failures: list[str] = []

    for path in sorted(files):
        rel = os.path.relpath(path, ROOT)
        text = open(path, encoding="utf-8", errors="replace").read()
        for paragraph in re.split(r"\n\s*\n", text):
            flat = " ".join(paragraph.split())
            nearby = [e for e in ENTITY_RE.findall(flat) if e in contract.entities]
            for m in SIGNATURE_RE.finditer(flat):
                verb = contract.resolve(m.group("name"), nearby)
                if verb is None:
                    skipped += 1
                    continue
                shown, elided = shown_arguments(m.group("args"))
                if not shown:
                    skipped += 1
                    continue
                actual = [p["name"] for p in (verb.get("parameters") or [])]
                problem = compare(shown, actual, elided)
                checked += 1
                if problem is None:
                    if args.verbose:
                        print(f"ok   {rel}: {verb['entity']}.{verb['name']}")
                else:
                    failures.append(
                        f"{rel}: {verb['entity']}.{verb['name']}\n"
                        f"           {problem}\n"
                        f"           shown:    {m.group(0)}\n"
                        f"           contract: {verb['name']}({', '.join(actual)})"
                    )

    print(f"{checked} verb signature(s) checked against the {args.version} contract "
          f"({skipped} mention(s) skipped as not a verb or ambiguous)")
    if failures:
        print(f"\n{len(failures)} signature(s) the contract contradicts:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        print(
            "\nArguments are positional, so a wrong name or order here becomes a call that\n"
            "fails silently. Confirm with: python3 tools/schema_query.py verb <Entity> <Verb>",
            file=sys.stderr,
        )
        sys.exit(1)
    print("every verb signature written in prose matches the extracted contract")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Check verb and SWQL function signatures written in prose against the real contracts.

Invoke arguments are positional. Names appear in SolarWinds' documentation and in their
Swagger contract but never travel on the wire, so argument order is the entire contract.
That makes a signature written into a sentence, ``Diff(configId1, configId2)``, one of the
highest-stakes claims in this repository: a reader who copies a reordered signature gets
no error, just the wrong result, and nothing about the call site looks wrong afterwards.

    python tools/check_signatures.py
    python tools/check_signatures.py --verbose     # list every confirmed signature

**Verbs** are checked by argument name and order. The names shown must match the real
ones, in order, starting from the first. Prose abbreviates signatures constantly and
legitimately: a paragraph about which id space each verb takes writes
``DownloadConfig(nodeId)`` because the first argument is the whole subject, and a paragraph
about a version change writes the older three-argument form on purpose. Neither is wrong,
so a shown prefix of the real argument list passes. What does not pass is a name that is
not there, or names in the wrong order, which are the failure modes that actually reach a
reader as broken code.

**SWQL functions** are checked by argument count instead, because the reference gives
their parameters placeholder names (``Avg(n)``) that real prose has no reason to repeat.
Calling one with the wrong number of arguments is the common mistake there, and
``Round(x)`` for a function that needs two is exactly the sort of thing that looks right
on the page.

Two conventions are respected rather than reported. Naming a function without arguments,
``Avg()``, is how prose refers to one, so a mention with no arguments is a name and not a
call. And a form named in order to warn readers off it, "``IsNull(x)`` is not a thing", is
good writing; those are detected the same way ``check_entity_references.py`` does it.

Verb arity claims written as sentences, "``Orion.Nodes.Unmanage`` takes four arguments",
are checked by ``check_counts.py``. Between the two a signature is covered for both its
names and its count.

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

# The opening of a call written inside a code span. The arguments are read with a
# balanced-paren scan rather than a regex, so a nested call such as ToLocal(GetUtcDate())
# parses instead of being cut off at the first closing paren.
CALL_OPEN_RE = re.compile(r"`(?P<name>[A-Za-z]\w*)\(")
ENTITY_RE = re.compile(r"`(?P<ent>[A-Z]\w*(?:\.[A-Z]\w*)+)`")
ELISION_RE = re.compile(r"\.\.\.|…")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
GENERATED_MARKER = "GENERATED FILE"


def is_generated(path: str) -> bool:
    """True when the file carries the banner the generators write."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        return GENERATED_MARKER in fh.read(400)


def balanced_arguments(text: str, open_index: int) -> str | None:
    """Read the argument text following the '(' at open_index, or None if unterminated.

    Stops at a backtick, since a call whose closing paren falls outside the code span is
    prose about a call rather than a written signature.
    """
    depth = 0
    for i in range(open_index, len(text)):
        char = text[i]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return text[open_index + 1:i]
        elif char == "`":
            return None
    return None


def split_arguments(args: str) -> list[str]:
    """Split on commas that are not inside nested parentheses or brackets."""
    parts: list[str] = []
    depth = 0
    current = ""
    for char in args:
        if char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        if char == "," and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += char
    parts.append(current)
    return [p.strip() for p in parts if p.strip()]


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
    names = [p for p in split_arguments(args) if not ELISION_RE.search(p)]
    return names, elided


class Functions:
    """SWQL function arities, read from the merged function reference."""

    def __init__(self) -> None:
        path = os.path.join(ROOT, "data", "reference", "swql-functions.json")
        self.by_name: dict[str, dict] = {}
        if not os.path.isfile(path):
            return
        for record in json.load(open(path, encoding="utf-8")):
            if record.get("signatureComplete"):
                self.by_name[record["name"].lower()] = record

    def arity(self, name: str) -> tuple[int, float, str] | None:
        """Return (minimum, maximum, signature). Maximum is inf for a variadic function."""
        record = self.by_name.get(name.lower())
        if not record:
            return None
        signature = record.get("signature") or ""
        open_index = signature.find("(")
        if open_index < 0:
            return None
        body = balanced_arguments(signature + "`", open_index)
        if body is None:
            return None
        body = body.strip()
        if not body:
            return (0, 0, signature)
        # A trailing "..." in the reference means the function takes any number more.
        if ELISION_RE.search(body):
            required = split_arguments(ELISION_RE.split(body)[0])
            return (len(required), float("inf"), signature)
        # Optional arguments are written in square brackets, sometimes nested.
        head = re.sub(r"\[.*", "", body)
        required = split_arguments(head)
        optional = len(re.findall(r"\[\s*,", body[len(head):]))
        if not required and "[" in body:
            return (0, len(split_arguments(re.sub(r"[\[\]]", "", body))), signature)
        return (len(required), len(required) + optional, signature)


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
    functions = Functions()

    # Naming a form in order to warn readers off it is good writing, and the prose checker
    # already knows how to spot one. Reuse that judgement rather than reinventing it.
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from check_entity_references import negated_nearby
    except Exception:  # pragma: no cover
        def negated_nearby(text, start, end):
            return False

    files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, "docs")):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        files += [os.path.join(dirpath, f) for f in filenames if f.endswith(".md")]
    # A generated page enumerates the same contract, so checking it proves nothing.
    # Skipping by banner rather than by directory keeps a hand-written page under
    # docs/reference/, such as a glossary, inside the check.
    files = [f for f in files if not is_generated(f)]

    verbs_checked = functions_checked = skipped = 0
    failures: list[str] = []

    for path in sorted(files):
        rel = os.path.relpath(path, ROOT)
        text = open(path, encoding="utf-8", errors="replace").read()
        for paragraph in re.split(r"\n\s*\n", text):
            flat = " ".join(paragraph.split())
            nearby = [e for e in ENTITY_RE.findall(flat) if e in contract.entities]
            for m in CALL_OPEN_RE.finditer(flat):
                name = m.group("name")
                body = balanced_arguments(flat, m.end() - 1)
                if body is None:
                    skipped += 1
                    continue
                written = f"`{name}({body})`"
                shown, elided = shown_arguments(body)
                # The span has to cover the whole written call, closing backtick included,
                # or a negation that follows it ("`IsNull(x)` is not a thing") is looked
                # for in the middle of the arguments and never found.
                span_end = m.end() + len(body) + 2

                verb = contract.resolve(name, nearby)
                if verb is not None and shown:
                    actual = [p["name"] for p in (verb.get("parameters") or [])]
                    problem = compare(shown, actual, elided)
                    verbs_checked += 1
                    if problem is None:
                        if args.verbose:
                            print(f"ok   {rel}: {verb['entity']}.{verb['name']}")
                    elif negated_nearby(flat, m.start(), span_end):
                        skipped += 1
                        verbs_checked -= 1
                    else:
                        failures.append(
                            f"{rel}: {verb['entity']}.{verb['name']}\n"
                            f"           {problem}\n"
                            f"           shown:    {written}\n"
                            f"           contract: {verb['name']}({', '.join(actual)})"
                        )
                    continue

                arity = functions.arity(name)
                # No arguments means the prose is naming the function, not calling it.
                if arity is None or not shown:
                    skipped += 1
                    continue
                low, high, signature = arity
                functions_checked += 1
                if low <= len(shown) <= high:
                    if args.verbose:
                        print(f"ok   {rel}: {name} with {len(shown)} argument(s)")
                elif negated_nearby(flat, m.start(), span_end):
                    skipped += 1
                    functions_checked -= 1
                else:
                    want = (f"{low}" if low == high
                            else f"{low} or more" if high == float("inf")
                            else f"{low} to {high:g}")
                    failures.append(
                        f"{rel}: SWQL function {name}\n"
                        f"           {len(shown)} argument(s) shown, the reference takes {want}\n"
                        f"           shown:     {written}\n"
                        f"           reference: {signature}"
                    )

    print(f"{verbs_checked} verb signature(s) checked against the {args.version} contract "
          f"and {functions_checked} SWQL function call(s) against the function reference "
          f"({skipped} mention(s) skipped as a bare name, not a verb, or ambiguous)")
    if failures:
        print(f"\n{len(failures)} signature(s) contradicted:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        print(
            "\nVerb arguments are positional, so a wrong name or order becomes a call that\n"
            "fails silently. Confirm with: python3 tools/schema_query.py verb <Entity> <Verb>,\n"
            "or for a function, docs/reference/swql-function-index.md",
            file=sys.stderr,
        )
        sys.exit(1)
    print("every signature written in prose matches the extracted contract")


if __name__ == "__main__":
    main()

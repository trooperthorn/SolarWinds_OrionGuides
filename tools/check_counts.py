#!/usr/bin/env python3
"""Check numeric claims about the schema against the extracted data.

The guides count things constantly, because a count is often the most useful sentence on
a page: how many entities a module ships, how many properties an entity declares, how
many verbs it publishes, how many arguments a verb takes. Every one of those numbers is
derivable from ``data/``, and every one of them goes quietly wrong the moment the data is
rebuilt for another platform version. Nothing about the sentence looks stale afterwards.

    python tools/check_counts.py
    python tools/check_counts.py --verbose     # list every confirmed claim

This checks five shapes, chosen because each makes the subject of the count unambiguous:

  - ```Orion.Nodes` declares 102 properties``, and the same for verbs and navigation
    properties, where the count spans both relationship lists because both are navigable
  - ```Orion.VIM.Luns` (7 properties)``
  - ``174 entities inherit from `System.ManagedEntity```
  - ```Orion.Nodes.Unmanage` takes four arguments``
  - a ``**Size.**`` paragraph, which the entity pages use to give a whole shape at once:
    "53 declared properties, 19 source relationships, 3 target relationships, 5 verbs".
    There the entity is the section heading, not a name in the sentence.

Precision is the whole design constraint. Prose counts subsets far more often than it
counts totals, and "two verbs on ``Cirrus.ConfigArchive``: ``Diff`` and ``CompareConfigs``"
is a true sentence about an entity with 24 verbs. A checker that reported those would be
noise, and a noisy checker gets ignored, so anything that reads as a subset is skipped
rather than guessed at. The cost of that choice is recall: many real counts are phrased in
ways this deliberately will not touch.

Counts of declared members are compared against the inherited total as well, since both
readings are legitimate and the prose does not always say which it means.

``check_data.py`` covers the namespace counts written as table rows in the module pages.
This covers the ones written in sentences, anywhere in the documentation.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

UNITS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
         "six": 6, "seven": 7, "eight": 8, "nine": 9}
TEENS = {"ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
         "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
        "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}

WORDS: dict[str, int] = dict(UNITS)
WORDS.update(TEENS)
WORDS.update(TENS)
for _tens, _tv in TENS.items():
    for _unit, _uv in UNITS.items():
        WORDS[f"{_tens}-{_unit}"] = _tv + _uv

# Longest alternative first so "twenty-five" wins over "twenty". The lookbehind keeps
# "five" from matching inside "Twenty-five", which otherwise turns a correct sentence into
# a reported error.
NUMWORD = "|".join(sorted(WORDS, key=len, reverse=True))
NUM = rf"(?<![\w-])(?P<n>\d{{1,6}}(?:,\d{{3}})*|{NUMWORD})"
ENTITY = r"[A-Z]\w*(?:\.[A-Z]\w*)+"
KIND = r"(?P<kind>properties|verbs|navigation properties)"

# Forms where the entity is the subject and the number is its total.
TOTAL_FORMS = [
    re.compile(rf"`(?P<ent>{ENTITY})`\s+(?:entity\s+)?(?:has|declares)\s+"
               rf"(?:just\s+|only\s+|exactly\s+)?{NUM}\s+(?:declared\s+)?{KIND}\b", re.I),
    re.compile(rf"`(?P<ent>{ENTITY})`\s*\({NUM}\s+{KIND}\)", re.I),
    re.compile(rf"`(?P<ent>{ENTITY})`[^.`]{{0,40}}?\bIts\s+{NUM}\s+{KIND}\b", re.I),
]

INHERIT_FORMS = [
    re.compile(rf"{NUM}\s+entit(?:y|ies)\s+(?:that\s+)?inherits?\s+from\s+`(?P<base>{ENTITY})`", re.I),
    re.compile(rf"`(?P<base>{ENTITY})`\s+is\s+the\s+base\s+type\s+for\s+{NUM}\s+entities", re.I),
]

NAMESPACE_FORMS = [
    re.compile(rf"{NUM}\s+entities\s+(?:under|in)\s+`(?P<ns>[A-Z][\w.]*?)\.?`", re.I),
    re.compile(rf"`(?P<ns>[A-Z][\w.]*?)\.?`[^.`]{{0,30}}?\bholds\s+\*{{0,2}}{NUM}\s+entities", re.I),
]

ARITY_FORM = re.compile(
    rf"`(?P<verb>{ENTITY}\.\w+)`\s+takes\s+{NUM}\s+(?:parameters|arguments)\b", re.I)

# Words that mark the number as counting part of something rather than all of it. A
# sentence carrying one of these inside the matched span is describing a subset and is
# skipped, because the total is not what it is asserting.
SUBSET_RE = re.compile(
    r"\b(?:of (?:its|the|these|those)|of their own|standard|whose|among|such as|including|"
    r"remaining|other|further|additional|new|extra|internal|deprecated|writable|readable)\b",
    re.I)

# A qualifier that narrows the count to a destination, sitting just after the phrase the
# pattern matched rather than inside it: "declares exactly two navigation properties into
# NCM" is a true sentence about an entity with 161 of them. Deliberately short, because a
# broader list would swallow ordinary continuations such as "102 properties in 2026.2".
SCOPED_RE = re.compile(
    r"^\W{0,3}(?:into|toward|towards|leading|pointing|that (?:lead|point|go|reach))\b", re.I)

SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
GENERATED_MARKER = "GENERATED FILE"

# A "**Size.**" paragraph, which is the convention the entity pages use to give an
# entity's shape in one line: "53 declared properties, 19 source relationships, 3 target
# relationships, 5 verbs". The marker is what makes the subject unambiguous, so the entity
# comes from the heading the paragraph sits under rather than from a name in the sentence.
HEADING_ENTITY_RE = re.compile(r"^#{2,6}\s+`?(?P<ent>[A-Z]\w*(?:\.[A-Z]\w*)+)`?\s*$", re.M)
SIZE_PARAGRAPH_RE = re.compile(r"\*\*Size\.\*\*\s*(?P<body>.+?)(?:\n\s*\n|\Z)", re.S)
SIZE_FIGURE_RE = re.compile(
    r"(?<![\w-])(?P<n>\d{1,6})\s+(?P<kind>declared properties|source relationships|"
    r"target relationships|verbs)\b", re.I)
NO_VERBS_RE = re.compile(r"\*{0,2}no verbs at all\*{0,2}", re.I)

SIZE_FIELDS = {
    "declared properties": "properties",
    "source relationships": "sourceRelationships",
    "target relationships": "targetRelationships",
    "verbs": "verbs",
}


def is_generated(path: str) -> bool:
    """True when the file carries the banner the generators write."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        return GENERATED_MARKER in fh.read(400)


def to_int(token: str) -> int | None:
    token = token.lower().replace(",", "")
    return int(token) if token.isdigit() else WORDS.get(token)


class Schema:
    def __init__(self, version: str) -> None:
        self.entities: dict[str, dict] = {}
        pattern = os.path.join(ROOT, "data", "schema", version, "entities", "*.json")
        for path in sorted(glob.glob(pattern)):
            with open(path, encoding="utf-8") as fh:
                for record in json.load(fh):
                    self.entities[record["entity"]] = record
        verbs_path = os.path.join(ROOT, "data", "schema", version, "verbs.json")
        with open(verbs_path, encoding="utf-8") as fh:
            self.verbs = json.load(fh)

    def member_counts(self, entity: str, kind: str) -> tuple[int, int]:
        """Return (declared, resolved). Resolved includes inherited members.

        A navigation property is not one field: the schema splits relationships into
        source and target lists and both are navigable from the declaring entity, so the
        count a reader cares about is the two together.
        """
        record = self.entities[entity]
        if kind == "navigation properties":
            fields = ("sourceRelationships", "targetRelationships")
        elif kind == "properties":
            fields = ("properties",)
        else:
            fields = ("verbs",)
        declared = sum(len(record[f]) for f in fields)
        seen = set()
        for ancestor in list(record.get("inheritance") or []) + [entity]:
            if ancestor in self.entities:
                for f in fields:
                    for member in self.entities[ancestor][f]:
                        seen.add(member["name"].lower())
        return declared, len(seen)

    def descendants(self, base: str) -> int:
        return sum(1 for r in self.entities.values() if base in (r.get("inheritance") or []))

    def in_namespace(self, namespace: str) -> int:
        prefix = namespace.rstrip(".") + "."
        return sum(1 for name in self.entities if name.startswith(prefix))

    def verb_arity(self, qualified: str) -> int | None:
        entity, _, verb = qualified.rpartition(".")
        for record in self.verbs:
            if record.get("entity") == entity and record.get("name", "").lower() == verb.lower():
                return len(record.get("parameters") or [])
        return None


def size_claims(text: str, schema: Schema):
    """Yield (label, claimed, actual, fragment, detail) for every **Size.** figure.

    The entity is taken from the nearest preceding heading, which is what the convention
    means: a Size paragraph describes the entity whose section it is in, so the numbers do
    not have to repeat the name and a name appearing in the prose is not the subject.
    """
    headings = [(m.start(), m.group("ent")) for m in HEADING_ENTITY_RE.finditer(text)]
    for m in SIZE_PARAGRAPH_RE.finditer(text):
        entity = None
        for position, name in headings:
            if position < m.start():
                entity = name
            else:
                break
        if entity not in schema.entities:
            continue
        record = schema.entities[entity]
        body = " ".join(m.group("body").split())
        for figure in SIZE_FIGURE_RE.finditer(body):
            kind = figure.group("kind").lower()
            actual = len(record[SIZE_FIELDS[kind]])
            yield (f"{entity} {kind}", int(figure.group("n")), actual, figure.group(0), "")
        if NO_VERBS_RE.search(body):
            yield (f"{entity} verbs", 0, len(record["verbs"]), "no verbs at all", "")


def claims_in(sentence: str, schema: Schema):
    """Yield (label, claimed, actual, fragment) for every checkable claim."""
    for form in TOTAL_FORMS:
        for m in form.finditer(sentence):
            entity, kind = m.group("ent"), m.group("kind").lower()
            claimed = to_int(m.group("n"))
            if entity not in schema.entities or claimed is None:
                continue
            if SUBSET_RE.search(m.group(0)) or SCOPED_RE.match(sentence[m.end():]):
                continue
            declared, resolved = schema.member_counts(entity, kind)
            actual = declared if claimed == declared else resolved
            yield (f"{entity} {kind}", claimed, actual, m.group(0),
                   f"declares {declared}, {resolved} including inherited")

    for form in INHERIT_FORMS:
        for m in form.finditer(sentence):
            base, claimed = m.group("base"), to_int(m.group("n"))
            if base not in schema.entities or claimed is None:
                continue
            actual = schema.descendants(base)
            yield (f"entities inheriting from {base}", claimed, actual, m.group(0), "")

    for form in NAMESPACE_FORMS:
        for m in form.finditer(sentence):
            namespace, claimed = m.group("ns"), to_int(m.group("n"))
            actual = schema.in_namespace(namespace)
            if claimed is None or not actual:
                continue
            yield (f"entities under {namespace}.", claimed, actual, m.group(0), "")

    for m in ARITY_FORM.finditer(sentence):
        qualified, claimed = m.group("verb"), to_int(m.group("n"))
        actual = schema.verb_arity(qualified)
        if claimed is None or actual is None:
            continue
        yield (f"{qualified} arguments", claimed, actual, m.group(0), "")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", default="2026.2")
    ap.add_argument("--verbose", action="store_true", help="list every confirmed claim")
    args = ap.parse_args()

    schema = Schema(args.version)

    files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, "docs")):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        files += [os.path.join(dirpath, f) for f in filenames if f.endswith(".md")]
    # A generated page is an enumeration of the same data, so checking it proves nothing.
    # Skipping by banner rather than by directory keeps a hand-written page under
    # docs/reference/, such as a glossary, inside the check.
    files = [f for f in files if not is_generated(f)]

    confirmed = 0
    failures: list[str] = []

    def record(rel, label, claimed, actual, fragment, detail):
        nonlocal confirmed
        if claimed == actual:
            confirmed += 1
            if args.verbose:
                print(f"ok   {rel}: {label} = {claimed}")
            return
        note = f"\n           ({detail})" if detail else ""
        failures.append(
            f"{rel}: {label}\n"
            f"           page says {claimed}, the {args.version} schema "
            f"says {actual}{note}\n"
            f"           in: {fragment[:120]}"
        )

    for path in sorted(files):
        rel = os.path.relpath(path, ROOT)
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        for claim in size_claims(text, schema):
            record(rel, *claim)
        for paragraph in re.split(r"\n\s*\n", text):
            flat = " ".join(paragraph.split())
            for sentence in SENTENCE_RE.split(flat):
                for claim in claims_in(sentence, schema):
                    record(rel, *claim)

    print(f"{confirmed + len(failures)} numeric schema claim(s) checked against data/")
    if failures:
        print(f"\n{len(failures)} claim(s) the data contradicts:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        print(
            "\nEither the sentence is stale or it means a subset. If it means a subset, "
            "say so\nin the sentence, which is clearer for a reader too.",
            file=sys.stderr,
        )
        sys.exit(1)
    print("every checkable numeric claim matches the extracted schema")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Validate SWQL queries against the extracted SWIS schema.

Catches the errors that cost the most time on a live server: an entity that does not
exist, a property that lives on a different entity, a navigation property that was
guessed, or a function SWIS does not provide. It resolves inherited members, so
``Orion.Nodes.Uri`` validates even though ``Uri`` is declared on ``System.Entity``.

    python tools/validate_swql.py scripts/swql/*.swql
    python tools/validate_swql.py --docs docs/            # every ```sql block in the docs
    echo "SELECT Caption FROM Orion.Nodes" | python tools/validate_swql.py -

Exit status is non-zero when any query fails, so this works as a CI gate.

This is a static checker, not a parser for the whole language. It deliberately reports
only what it can prove wrong from the schema, and stays quiet about constructs it cannot
resolve rather than inventing failures.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

DEFAULT_VERSION = "2026.2"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Reserved words never treated as an alias, entity, or member name.
KEYWORDS = {
    "select", "from", "where", "join", "inner", "left", "right", "full", "outer", "cross",
    "on", "as", "and", "or", "not", "in", "is", "null", "like", "between", "group", "by",
    "having", "order", "asc", "desc", "top", "distinct", "union", "all", "case", "when",
    "then", "else", "end", "with", "rows", "to", "totalrows", "schemaonly", "logs", "noplan",
    "exists", "any", "some", "true", "false",
}


class SchemaIndex:
    """Entity metadata with inheritance-aware member lookup."""

    def __init__(self, version: str = DEFAULT_VERSION):
        root = os.path.join(ROOT, "data", "schema", version)
        if not os.path.isdir(root):
            sys.exit(f"error: no extracted schema at {root}; run tools/build_schema_data.py")
        self.entities: dict[str, dict] = {}
        ent_dir = os.path.join(root, "entities")
        for fname in sorted(os.listdir(ent_dir)):
            if fname.endswith(".json"):
                with open(os.path.join(ent_dir, fname), encoding="utf-8") as fh:
                    for rec in json.load(fh):
                        self.entities[rec["entity"]] = rec
        self.by_lower = {k.lower(): k for k in self.entities}

        fpath = os.path.join(ROOT, "data", "reference", "swql-functions.json")
        self.functions = set()
        if os.path.isfile(fpath):
            with open(fpath, encoding="utf-8") as fh:
                self.functions = {f["name"].lower().replace(" ", "") for f in json.load(fh)}
        # Accepted in queries but not listed as functions in the reference.
        self.functions |= {"count", "isnull", "cast", "convert", "coalesce"}

        self._members: dict[str, tuple[dict, dict]] = {}

    def resolve(self, name: str) -> str | None:
        return self.by_lower.get(name.lower())

    def members(self, entity: str) -> tuple[dict, dict]:
        """Return (properties, navigations) including everything inherited.

        Extraction records only the members an entity declares itself, so ``Uri`` and
        ``UnManaged`` appear on System.Entity / System.ManagedEntity rather than on
        Orion.Nodes. Walking the inheritance chain is what makes them resolve.
        """
        if entity in self._members:
            return self._members[entity]
        props: dict[str, str] = {}
        navs: dict[str, str] = {}
        rec = self.entities.get(entity)
        if rec:
            # Ancestors first so a redeclaration on the entity itself wins.
            for anc in rec["inheritance"] + [entity]:
                arec = self.entities.get(anc)
                if not arec:
                    continue
                for p in arec["properties"]:
                    props[p["name"].lower()] = p["type"]
                for rel in arec["sourceRelationships"] + arec["targetRelationships"]:
                    navs[rel["name"].lower()] = rel["type"]
        self._members[entity] = (props, navs)
        return props, navs


# --------------------------------------------------------------------------------------
# Lightweight query scanning
# --------------------------------------------------------------------------------------

STRING_RE = re.compile(r"'(?:[^']|'')*'")
COMMENT_RE = re.compile(r"--[^\n]*|/\*.*?\*/", re.S)
# FROM/JOIN <Entity>[(hint=value, ...)] [AS] [alias]; entity names are dotted, aliases are
# bare words. The optional parenthesised part is a table hint, written directly against the
# entity name as Orion.Nodes(nolock=true). It appears throughout SolarWinds' community
# material, and without it here the alias that follows was read as a member of the entity
# and every column qualified by that alias was reported as unknown.
SOURCE_RE = re.compile(
    r"\b(?:from|join)\s+(?P<entity>[A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)+)"
    r"(?:\s*\((?P<hint>[^()]*)\))?"
    r"(?:\s+(?:as\s+)?(?P<alias>(?!on\b|where\b|join\b|inner\b|left\b|right\b|full\b|outer\b|cross\b|group\b|order\b|having\b|with\b|union\b)[A-Za-z_]\w*))?",
    re.I,
)
# A dotted reference: head.segment[.segment...]
DOTTED_RE = re.compile(r"\b([A-Za-z_]\w*)((?:\.[A-Za-z_]\w*)+)\b")
FUNC_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\(")


def strip_noise(q: str) -> str:
    q = COMMENT_RE.sub(" ", q)
    return STRING_RE.sub("''", q)


class Finding:
    def __init__(self, level: str, message: str, snippet: str = ""):
        self.level = level
        self.message = message
        self.snippet = snippet

    def __str__(self):
        s = f"  {self.level}: {self.message}"
        if self.snippet:
            s += f"\n      in: {self.snippet}"
        return s


def validate(query: str, schema: SchemaIndex) -> list[Finding]:
    findings: list[Finding] = []
    clean = strip_noise(query)

    if not re.search(r"\bselect\b", clean, re.I):
        return findings  # not a query; nothing to check

    # 1. Resolve the sources named by FROM/JOIN.
    aliases: dict[str, str] = {}
    sources: list[str] = []
    for m in SOURCE_RE.finditer(clean):
        raw = m.group("entity")
        resolved = schema.resolve(raw)
        if resolved is None:
            near = sorted(
                (k for k in schema.entities if raw.split(".")[-1].lower() in k.lower()), key=len
            )[:3]
            hint = f" Did you mean: {', '.join(near)}?" if near else ""
            findings.append(Finding("ERROR", f"unknown entity {raw!r}.{hint}", m.group(0).strip()))
            continue
        if resolved != raw:
            findings.append(
                Finding("WARN", f"entity {raw!r} differs in case from schema name {resolved!r}", m.group(0).strip())
            )
        sources.append(resolved)
        alias = m.group("alias")
        if alias and alias.lower() not in KEYWORDS:
            aliases[alias.lower()] = resolved
        # The bare entity name is also usable as a qualifier.
        aliases.setdefault(resolved.lower(), resolved)
        aliases.setdefault(resolved.split(".")[-1].lower(), resolved)

    if not sources:
        return findings

    # 2. Walk every dotted reference through properties and navigations.
    for m in DOTTED_RE.finditer(clean):
        head = m.group(1)
        segments = [s for s in m.group(2).split(".") if s]
        if head.lower() in KEYWORDS:
            continue

        entity = aliases.get(head.lower())
        if entity is None:
            # Could be a dotted entity name used inline (already checked) or an alias we
            # did not capture. Only complain when it looks like an entity we do not have.
            full = head + m.group(2)
            if schema.resolve(full) is None and "." in full and head[0].isupper():
                known_prefix = any(
                    full.lower().startswith(ns.lower() + ".") for ns in {e.split(".")[0] for e in schema.entities}
                )
                if known_prefix:
                    findings.append(Finding("ERROR", f"unknown entity or alias {full!r}", m.group(0)))
            continue

        cur = entity
        for i, seg in enumerate(segments):
            props, navs = schema.members(cur)
            key = seg.lower()
            last = i == len(segments) - 1
            if key in navs:
                cur = navs[key]
                if last:
                    # Selecting a navigation itself is legal (it yields the related row),
                    # so this is informational only.
                    pass
                continue
            if key in props:
                if not last:
                    findings.append(
                        Finding(
                            "ERROR",
                            f"{cur}.{seg} is a property of type {props[key]}, "
                            f"so it cannot be navigated further with .{segments[i+1]}",
                            m.group(0),
                        )
                    )
                break
            near = sorted(
                (n for n in list(props) + list(navs) if key in n or n in key), key=len
            )[:3]
            hint = f" Closest members: {', '.join(near)}." if near else ""
            findings.append(
                Finding(
                    "ERROR",
                    f"{cur} has no property or navigation property named {seg!r}.{hint}",
                    m.group(0),
                )
            )
            break

    # 3. Function names.
    for m in FUNC_RE.finditer(clean):
        fname = m.group(1)
        if fname.lower() in KEYWORDS or fname.lower() in schema.functions:
            continue
        if fname.lower() in aliases or schema.resolve(fname):
            continue
        findings.append(
            Finding("WARN", f"{fname!r} is not in the SWQL function reference; verify it exists on your version", m.group(0))
        )

    # 4. Unqualified column names, when there is exactly one source to resolve them against.
    #
    # A query with a single FROM and no joins can write its columns bare, and until this
    # existed nothing checked them: "SELECT VerbName FROM Metadata.Verb WHERE EntityName =
    # ..." named two columns that entity does not have and passed every check in this
    # repository. More than one source makes a bare name genuinely ambiguous, so those are
    # left alone rather than guessed at.
    findings.extend(_check_bare_columns(clean, sources, aliases, schema))

    return findings


# Text that is not a column reference and must be removed before the bare names are read:
# a bracket-quoted identifier, which may follow a qualifier that would otherwise be left
# stranded; a bound parameter; a numeric literal.
BRACKET_QUALIFIED_RE = re.compile(r"\b[A-Za-z_]\w*\s*\.\s*\[[^\]]*\]")
BRACKET_RE = re.compile(r"\[[^\]]*\]")
PARAM_RE = re.compile(r"@\w+")
NUMBER_RE = re.compile(r"\b\d[\w.]*\b")
AS_ALIAS_RE = re.compile(r"\bas\s+([A-Za-z_]\w*)", re.I)


def _check_bare_columns(clean, sources, aliases, schema) -> list[Finding]:
    if len(sources) != 1:
        return []
    entity = sources[0]
    props, navs = schema.members(entity)

    masked = clean
    for m in SOURCE_RE.finditer(clean):
        masked = masked.replace(m.group(0), " ")
    masked = BRACKET_QUALIFIED_RE.sub(" ", masked)
    masked = DOTTED_RE.sub(" ", masked)
    masked = BRACKET_RE.sub(" ", masked)
    masked = PARAM_RE.sub(" ", masked)
    masked = NUMBER_RE.sub(" ", masked)

    called = {m.group(1).lower() for m in FUNC_RE.finditer(masked)}
    named = {m.group(1).lower() for m in AS_ALIAS_RE.finditer(masked)}

    findings: list[Finding] = []
    reported: set[str] = set()
    for m in re.finditer(r"\b([A-Za-z_]\w*)\b", masked):
        word = m.group(1)
        key = word.lower()
        if key in KEYWORDS or key in called or key in named or key in aliases:
            continue
        if key in schema.functions or key in props or key in navs:
            continue
        if key in reported:
            continue
        reported.add(key)
        near = sorted((n for n in list(props) + list(navs) if key in n or n in key), key=len)[:3]
        hint = f" Closest members: {', '.join(near)}." if near else ""
        findings.append(
            Finding("ERROR", f"{entity} has no member named {word!r}.{hint}", word)
        )
    return findings


# --------------------------------------------------------------------------------------
# Input collection
# --------------------------------------------------------------------------------------

GENERATED_MARKER = "GENERATED FILE"
FENCE_RE = re.compile(r"```(?:sql|swql)\n(.*?)```", re.S | re.I)
ANY_FENCE_RE = re.compile(r"```.*?```", re.S)
# A whole statement written inline in a single-backtick code span, which is how the guides
# write a one-liner rather than breaking the paragraph for a fenced block. These are just
# as copyable as a fenced query and were not being checked, which is how a
# `Metadata.Property` filter on a column that entity does not have survived review.
INLINE_QUERY_RE = re.compile(r"`([^`\n]*\bSELECT\b[^`\n]*\bFROM\b[^`\n]*)`", re.I)
DELIBERATELY_INVALID_RE = re.compile(
    r"\bdeliberately invalid\b|\bintentionally invalid\b|\binvalid query\b|"
    r"\bwill fail\b|\bfails with\b|\bdoes not work\b", re.I)


def queries_from_markdown(path: str) -> list[tuple[str, str]]:
    with open(path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    out = []
    for i, block in enumerate(FENCE_RE.findall(text), 1):
        block = block.strip()
        if re.search(r"\bselect\b", block, re.I):
            out.append((f"{path}#sql-block-{i}", block))
    # Generated tables lift example queries from their sources and truncate them to fit a
    # column, so "FROM Orion.Cont" is a rendering artefact rather than a broken query.
    # Authored pages are where an inline statement is a claim someone can copy.
    if GENERATED_MARKER not in text[:400]:
        # Blank the fenced blocks first so a line inside one is not counted twice.
        outside = ANY_FENCE_RE.sub("", text)
        i = 0
        for m in INLINE_QUERY_RE.finditer(outside):
            i += 1
            # A query shown in order to demonstrate a failure is not a claim that it works.
            # The pages say so in the sentence introducing it, which is the right place for
            # a reader as well as the only place a one-line inline query can carry it.
            lead = " ".join(outside[max(0, m.start() - 200):m.start()].split())
            if DELIBERATELY_INVALID_RE.search(lead):
                continue
            out.append((f"{path}#inline-{i}", m.group(1).strip()))
    return out


def queries_from_dashboard(path: str) -> list[tuple[str, str]]:
    """Pull the SWQL out of a Modern Dashboard export.

    A dashboard file carries its queries as JSON string values nested several levels down,
    and carries each one twice (see docs/webui/modern-dashboards.md). Both copies are
    returned deliberately: if an edit updates one and misses the other, the stale copy is a
    real query the widget will run, so it deserves checking on its own.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return []
    if not isinstance(doc, dict) or "widgets" not in doc or "dashboards" not in doc:
        return []

    out: list[tuple[str, str]] = []

    def walk(node, trail: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "swql" and isinstance(value, str):
                    out.append((f"{path}#{trail}", value))
                else:
                    walk(value, f"{trail}/{key}" if trail else key)
        elif isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, f"{trail}[{i}]")

    walk(doc, "")
    return out


def queries_from_swql(path: str) -> list[tuple[str, str]]:
    """A .swql file may hold several queries separated by blank-line-delimited comments."""
    text = open(path, encoding="utf-8", errors="replace").read()
    chunks = [c.strip() for c in re.split(r"\n\s*\n(?=\s*(?:--|SELECT))", text, flags=re.I)]
    out = []
    for i, chunk in enumerate([c for c in chunks if re.search(r"\bselect\b", c, re.I)], 1):
        out.append((f"{path}#{i}", chunk))
    return out


# SWQL embedded in client scripts is exactly as capable of naming a property that does not
# exist, and nothing else checks it. These patterns cover the ways the scripts here carry
# a query: PowerShell here-strings, Python triple-quoted strings, and shell heredocs.
PS_HERESTRING_RE = re.compile(r"@[\"']\r?\n(.*?)\r?\n[\"']@", re.S)
PY_TRIPLE_RE = re.compile(r'"""(.*?)"""|\'\'\'(.*?)\'\'\'', re.S)
# Requiring a FROM is what keeps this from matching prose; the gap between SELECT and
# FROM only has to be non-empty. An earlier minimum of ten characters silently skipped
# short but perfectly ordinary queries such as "SELECT Caption FROM Orion.Nodes".
QUOTED_QUERY_RE = re.compile(
    r"""["'](\s*SELECT\b[^"']+?\bFROM\b[^"']*?)["']""", re.I | re.S
)


# A whole block counts as a query only when it *starts* with SELECT (after any leading
# SQL comments). Without this, a module docstring that merely quotes an example is
# swallowed whole and its prose is parsed as SQL.
STARTS_WITH_SELECT_RE = re.compile(r"\A(?:\s*--[^\n]*\n)*\s*SELECT\b", re.I)


def queries_from_source(path: str) -> list[tuple[str, str]]:
    """Pull embedded SWQL out of a PowerShell, Python, or shell script."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    found: list[str] = []

    for m in PS_HERESTRING_RE.finditer(text):
        found.append(m.group(1))
    for m in PY_TRIPLE_RE.finditer(text):
        found.append(m.group(1) or m.group(2) or "")
    # This pattern is already anchored on SELECT, so a quoted query inside a docstring is
    # still picked up individually even though the docstring as a whole is rejected.
    for m in QUOTED_QUERY_RE.finditer(text):
        found.append(m.group(1))

    out = []
    seen = set()
    for i, block in enumerate(found, 1):
        block = block.strip()
        if not STARTS_WITH_SELECT_RE.match(block) or not re.search(r"\bfrom\b", block, re.I):
            continue
        # Skip anything still carrying an unresolved template placeholder: the query the
        # script actually sends is not the text on the page.
        if re.search(r"[{$%]\s*\w+\s*[}]|\{\}|%s", block):
            continue
        if block in seen:
            continue
        seen.add(block)
        out.append((f"{path}#embedded-{i}", block))
    return out


SOURCE_SUFFIXES = (".ps1", ".psm1", ".py", ".sh", ".bash")


def queries_from_path(path: str) -> list[tuple[str, str]]:
    """Dispatch to the right extractor for a file, by extension."""
    if not os.path.isfile(path):
        return []
    if path.endswith(".md"):
        return queries_from_markdown(path)
    if path.endswith(SOURCE_SUFFIXES):
        return queries_from_source(path)
    if path.endswith(".swql") or path.endswith(".sql"):
        return queries_from_swql(path)
    if path.endswith(".json"):
        return queries_from_dashboard(path)
    return []


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help=".swql, .md, .ps1, .py, .sh, dashboard .json, directories, or - for stdin")
    ap.add_argument("--docs", action="append", default=[], help="directory to scan for ```sql blocks")
    ap.add_argument("--version", default=DEFAULT_VERSION)
    ap.add_argument("--strict", action="store_true", help="treat warnings as failures")
    ap.add_argument("--quiet", action="store_true", help="only print failures")
    args = ap.parse_args()

    schema = SchemaIndex(args.version)

    items: list[tuple[str, str]] = []
    targets = list(args.paths)
    for d in args.docs:
        targets.extend(sorted(glob.glob(os.path.join(d, "**", "*.md"), recursive=True)))

    for target in targets:
        if target == "-":
            items.append(("<stdin>", sys.stdin.read()))
        elif os.path.isdir(target):
            for f in sorted(glob.glob(os.path.join(target, "**", "*"), recursive=True)):
                items.extend(queries_from_path(f))
        else:
            for f in ([target] if os.path.isfile(target) else sorted(glob.glob(target))):
                items.extend(queries_from_path(f))

    if not items:
        print("no queries found", file=sys.stderr)
        sys.exit(0)

    errors = warns = 0
    for label, query in items:
        findings = validate(query, schema)
        errs = [f for f in findings if f.level == "ERROR"]
        wrns = [f for f in findings if f.level == "WARN"]
        errors += len(errs)
        warns += len(wrns)
        if errs or (wrns and not args.quiet):
            print(f"{label}")
            for f in errs + wrns:
                print(f)
        elif not args.quiet:
            print(f"{label}: ok")

    print(f"\n{len(items)} query/queries checked, {errors} error(s), {warns} warning(s)")
    sys.exit(1 if errors or (args.strict and warns) else 0)


if __name__ == "__main__":
    main()

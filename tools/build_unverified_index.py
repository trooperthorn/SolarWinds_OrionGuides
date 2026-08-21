#!/usr/bin/env python3
"""Collect every statement the documentation marks as unverified into one page.

The rule this repository is written to is that a claim which could not be checked says
so rather than being asserted quietly or dropped. That produces a lot of small honest
admissions scattered across sixty pages, which is the right place for them when you are
reading that page and the wrong place when you want to know, overall, where the edges are.

This gathers them. The result is the page to read before trusting this repository for
something load-bearing, and the working list for anyone with a live server who wants to
close a gap.

    python tools/build_unverified_index.py

Writes docs/reference/unverified.md. Regenerate with `make docs-reference`.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Phrasings the pages actually use. Deliberately narrow: "verify" on its own appears in
# ordinary instructions ("verify this on your server") that are not admissions.
MARKER_RE = re.compile(
    r"\b(?:is|are|remains?|treat\w*\s+\w+\s+as|marked)\s+\*{0,2}unverified\*{0,2}\b"
    r"|\*{0,2}unverified\*{0,2}\s+(?:here|in content)\b"
    # A bold label opening a sentence or a table cell: "**Unverified.** The standard SQL
    # spelling, but it appears in no SolarWinds documentation page". This is how a page
    # marks a whole claim rather than qualifying one inside a sentence, and reading only
    # the sentence forms meant those never reached the index.
    r"|\*\*unverified[.:]?\*\*"
    r"|\bcould not (?:be )?verif\w+\b"
    r"|\bcannot (?:be )?verif\w+\b"
    r"|\bnot verified\b"
    r"|\bno(?:t)? (?:documented|recorded) (?:anywhere )?in the (?:published )?schema\b",
    re.I,
)

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*$", re.M)
FENCE_RE = re.compile(r"```.*?```", re.S)
# Sentence-ish split that tolerates the abbreviations and version numbers in this corpus.
# The digit in the lookahead is what starts a new sentence at a numbered list item: without
# it the "3." opening the next item is read as part of the previous sentence and trails
# into the index.
SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z`*\[]|\d+\.\s)")
# A list bullet or table pipe introducing the sentence. Written to require the whitespace
# after the marker so that a leading "**" opening a bold span is left alone: stripping the
# asterisks blindly closed nothing and left an unbalanced "**" mid-sentence.
LEAD_MARKER_RE = re.compile(r"^\s*(?:[-*|]\s+)+")


TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
# The |:---|---:| separator under a table header carries no statement.
TABLE_RULE_RE = re.compile(r"^[\s|:\-]+$")


def statements(paragraph: str) -> list[str]:
    """Split a paragraph into the units a statement can live in.

    Ordinary prose splits into sentences. A markdown table does not: it has no blank line
    between its rows, so the whole table is one paragraph, and flattening it produces a
    single run of every row with the marked claim buried in the middle. Its rows are the
    units instead, rendered with the cell boundaries kept as separators so the row still
    reads as a statement about its subject.
    """
    lines = paragraph.splitlines()
    rows = [l for l in lines if TABLE_ROW_RE.match(l) and not TABLE_RULE_RE.match(l)]
    if len(rows) >= 2:
        out = []
        for row in rows:
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            cells = [c for c in cells if c]
            if cells:
                out.append(" — ".join(cells))
        return out
    return SENT_SPLIT_RE.split(" ".join(paragraph.split()))


MD_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
REFERENCE_DIR = os.path.join(ROOT, "docs", "reference")


def requalify_links(sentence: str, source_path: str) -> str:
    """Rewrite links in a lifted sentence so they still resolve from docs/reference/.

    A sentence is lifted out of its page and into this index, which sits in a different
    directory. Two kinds of link break in the move: a bare same-page anchor, which would
    now point at a heading of the index rather than of the page it came from, and a
    relative path, which was written relative to the source page's directory.
    """
    source_dir = os.path.dirname(source_path)

    def fix(m: re.Match) -> str:
        text, target = m.group(1), m.group(2)
        if target.startswith(("http://", "https://", "mailto:", "#")):
            if target.startswith("#"):
                rel = os.path.relpath(source_path, REFERENCE_DIR)
                return f"[{text}]({rel}{target})"
            return m.group(0)
        path_part, _, fragment = target.partition("#")
        if not path_part:
            return m.group(0)
        absolute = os.path.normpath(os.path.join(source_dir, path_part))
        rel = os.path.relpath(absolute, REFERENCE_DIR)
        return f"[{text}]({rel}{'#' + fragment if fragment else ''})"

    return MD_LINK_RE.sub(fix, sentence)


def slug(heading: str) -> str:
    text = re.sub(r"`([^`]*)`", r"\1", heading)
    text = re.sub(r"[*_~]", "", text).strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"\s+", "-", text)


def collect(docs_root: str) -> dict[str, list[tuple[str, str]]]:
    """Return {relative path: [(heading, sentence), ...]}."""
    found: dict[str, list[tuple[str, str]]] = {}
    for dirpath, dirnames, filenames in os.walk(docs_root):
        dirnames[:] = [d for d in dirnames if d != "reference"]  # generated
        for name in sorted(filenames):
            if not name.endswith(".md"):
                continue
            path = os.path.join(dirpath, name)
            # docs/README.md is the index. It describes the policy of marking things
            # unverified, which is not itself an unverified claim.
            if os.path.abspath(path) == os.path.abspath(os.path.join(docs_root, "README.md")):
                continue
            raw = open(path, encoding="utf-8", errors="replace").read()
            # Blank out code so a fenced example mentioning the word is not collected,
            # while keeping offsets intact so heading lookup stays correct.
            text = FENCE_RE.sub(lambda m: "\n" * m.group(0).count("\n"), raw)

            headings = [(m.start(), m.group(2).strip()) for m in HEADING_RE.finditer(text)]
            entries: list[tuple[str, str]] = []
            seen = set()

            for para in re.split(r"\n\s*\n", text):
                if not MARKER_RE.search(para):
                    continue
                start = text.find(para)
                heading = ""
                for pos, h in headings:
                    if pos <= start:
                        heading = h
                    else:
                        break
                # Keep the sentence carrying the marker, not the whole paragraph. A table
                # has no blank lines between its rows, so flattening one produces a single
                # unreadable run of every row; take the row that carries the marker instead.
                for sentence in statements(para):
                    if MARKER_RE.search(sentence):
                        s = LEAD_MARKER_RE.sub("", sentence).strip(" |")
                        # An odd count means the span was opened outside this sentence or
                        # closed after it, so the stray marker would render as literal
                        # asterisks in the index.
                        if s.count("**") % 2:
                            s = s.replace("**", "")
                        if len(s) > 400:
                            s = s[:397].rstrip() + "..."
                        s = requalify_links(s, path)
                        if s and s not in seen:
                            seen.add(s)
                            entries.append((heading, s))
            if entries:
                found[os.path.relpath(path, ROOT)] = entries
    return found


def render(found: dict[str, list[tuple[str, str]]]) -> str:
    total = sum(len(v) for v in found.values())
    out = [
        "<!-- GENERATED FILE. Do not edit by hand.",
        "     Produced by tools/build_unverified_index.py from the documentation itself.",
        "     Regenerate with: make docs-reference -->",
        "",
        "# What this repository does not verify",
        "",
        "Everything in these guides was checked against the extracted SolarWinds schema "
        "before it was written, and every SWQL statement is re-checked on each build. Some "
        "things cannot be checked that way: behaviour that only a running server exhibits, "
        "values that are installation data rather than schema, and the handful of places "
        "where SolarWinds' own documentation and their published contract disagree.",
        "",
        "The rule is that those say so rather than being asserted quietly or dropped. This "
        "page collects every such statement in one place, because an admission is in the "
        f"right place on its page and the wrong place when you want the whole picture.",
        "",
        f"**{total} statements across {len(found)} pages.**",
        "",
        "Read this before relying on this repository for something load-bearing. If you "
        "have a live server, this is also the working list: most entries name the "
        "`Metadata.*` query or the experiment that would close the gap. See "
        "[../swis/metadata-introspection.md](../swis/metadata-introspection.md).",
        "",
    ]

    for path in sorted(found):
        rel = os.path.relpath(os.path.join(ROOT, path), os.path.join(ROOT, "docs", "reference"))
        title = os.path.basename(path)
        out.append(f"## [{title}]({rel})")
        out.append("")
        last_heading = None
        for heading, sentence in found[path]:
            if heading and heading != last_heading:
                anchor = f"{rel}#{slug(heading)}"
                out.append(f"**[{heading}]({anchor})**")
                out.append("")
                last_heading = heading
            out.append(f"- {sentence}")
        out.append("")

    out += [
        "---",
        "",
        "An entry here is not a defect. It is a statement that a reader should confirm "
        "before depending on it, and that this repository declines to guess about.",
    ]
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join("docs", "reference", "unverified.md"))
    args = ap.parse_args()

    found = collect(os.path.join(ROOT, "docs"))
    if not found:
        print("no unverified statements found", file=sys.stderr)
    path = os.path.join(ROOT, args.out)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(render(found).rstrip() + "\n")
    total = sum(len(v) for v in found.values())
    print(f"wrote {args.out}: {total} statement(s) across {len(found)} page(s)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Generate the AI-facing indexes of the documentation, and check that they are current.

Two files are produced, and one hand-written file is checked:

``docs/TOC.md``
    A heading-level table of contents: every page under ``docs/``, every ``##`` heading
    on it, and the first sentence written under that heading. ``llms.txt`` is a page-level
    map, and a page can be a thousand lines long. This is the map that lets a reader, or a
    model that can fetch one URL, jump to the right section instead of the right file.

``llms-full.txt``
    Every page under ``docs/`` concatenated into one file, in the same order ``llms.txt``
    lists them, behind the root README and AGENTS.md. It exists for AI systems that can
    fetch a URL but cannot run a command: one fetch delivers the whole guide instead of a
    hundred. The convention comes from https://llmstxt.org/.

``llms.txt``
    Hand-written, because its one-line summaries are editorial. It is checked, not
    generated: every page under ``docs/`` must be listed, and every relative link in it
    must resolve. Before this check existed three pages had been added to ``docs/`` and
    never to the index, and nothing said so.

    python3 tools/build_llms_index.py            # write both generated files
    python3 tools/build_llms_index.py --check    # exit 1 if either is stale or llms.txt has drifted

The output is deterministic: the same tree produces byte-identical files, so the CI diff
after a regeneration is a real change or nothing.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
LLMS_TXT = os.path.join(ROOT, "llms.txt")
LLMS_FULL = os.path.join(ROOT, "llms-full.txt")
TOC_MD = os.path.join(DOCS, "TOC.md")

GENERATED_MARKER = "GENERATED FILE"

# The order llms.txt presents the sections in, which is the order a newcomer should read
# them in. A section directory not named here sorts after these, alphabetically, so a new
# section is indexed the day it appears rather than the day someone remembers this list.
SECTION_ORDER = [
    "platform", "swis", "swql", "schema", "modules", "automation", "polling",
    "webui", "guides", "reference",
]

# What the repository says about where its content comes from. It is stated once here and
# written into both generated files so a reader who arrives through llms-full.txt or the
# table of contents sees it without having to find the README.
PROVENANCE = (
    "Everything in this repository was assembled from resources SolarWinds publishes on "
    "the public internet: the OrionSDK repository and its rendered schema pages, the "
    "public SDK documentation, the Swagger contract shipped with the SDK, and a community "
    "SWQL examples workbook. It contains no SolarWinds internal documentation, no "
    "non-public material, and no method of access to any SolarWinds system beyond the "
    "documented, customer-facing API. It is community documentation, not a SolarWinds "
    "publication."
)

# Link and heading forms, matched the same way check_links.py matches them so the anchors
# written here are the anchors it verifies.
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
FENCE_RE = re.compile(r"^(```|~~~)")
H1_RE = re.compile(r"^#\s+(.+?)\s*$")
H2_RE = re.compile(r"^##\s+(.+?)\s*$")
INLINE_MD_RE = re.compile(r"`([^`]*)`|\*\*([^*]+)\*\*|\*([^*]+)\*|\[([^\]]+)\]\([^)]*\)")

# check_links.py owns the slug rule; importing it keeps the two in step by construction.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_links import slugify  # noqa: E402


def docs_pages() -> list[str]:
    """Every page under docs/, as a repository-relative path, in reading order."""
    pages: list[str] = []
    sections = [d for d in os.listdir(DOCS) if os.path.isdir(os.path.join(DOCS, d))]
    ordered = [s for s in SECTION_ORDER if s in sections]
    ordered += sorted(s for s in sections if s not in SECTION_ORDER)
    for section in ordered:
        sdir = os.path.join(DOCS, section)
        names = sorted(n for n in os.listdir(sdir) if n.endswith(".md"))
        # A section's README is its index and reads first.
        if "README.md" in names:
            names.remove("README.md")
            names.insert(0, "README.md")
        pages += [f"docs/{section}/{n}" for n in names]
    # Pages directly under docs/: README.md is the section index; TOC.md is this tool's
    # own output and is not indexed by itself.
    top = sorted(n for n in os.listdir(DOCS) if n.endswith(".md") and n != "TOC.md")
    if "README.md" in top:
        top.remove("README.md")
        pages.insert(0, "docs/README.md")
    pages += [f"docs/{n}" for n in top]
    return pages


def read(rel: str) -> str:
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def plain(text: str) -> str:
    """Strip inline markdown from a heading or sentence for use as a label.

    Constructs nest (a link whose text is a code span, bold around code), and one pass
    returns the outer construct's inner text with the inner markup intact. Passes repeat
    until nothing changes. A lone backtick that survives would matter: check_links.py
    strips inline code with a non-greedy pair match, and an unpaired backtick makes it
    swallow every link between there and the next one.
    """
    def sub(m: re.Match) -> str:
        return next(g for g in m.groups() if g is not None)
    while True:
        stripped = INLINE_MD_RE.sub(sub, text)
        if stripped == text:
            return text.strip()
        text = stripped


def first_sentence(lines: list[str]) -> str:
    """The first sentence of prose in a block of lines, or an empty string.

    Tables, lists, fences, HTML comments, and headings are not prose. A paragraph is read
    up to its first blank line and cut at the first sentence end, so a summary is one
    sentence even when the paragraph runs to five.
    """
    in_fence = False
    para: list[str] = []
    for raw in lines:
        line = raw.rstrip()
        if FENCE_RE.match(line.lstrip()):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        stripped = line.strip()
        if not stripped:
            if para:
                break
            continue
        # A list marker is a dash, star or plus followed by a space, or a number and a
        # dot. A bare "*" test would also skip a sentence that opens in bold, and the
        # paragraph would then be read from its second line, mid code span.
        is_block = (stripped.startswith(("|", "#", "<!--", ">"))
                    or re.match(r"(?:[-*+]|\d+\.)\s", stripped) is not None)
        if is_block and not para:
            continue
        para.append(stripped)
    if not para:
        return ""
    joined = " ".join(para)
    # A paragraph that opens with a bold label ("**What you see.** Connection refused...")
    # is summarised by what follows the label, not by the label.
    joined = re.sub(r"^\*\*[^*]+?[.:]\*\*\s*", "", joined)
    text = plain(joined)
    m = re.search(r"[.!?](?:\s|$)", text)
    if m:
        text = text[: m.start() + 1]
    if len(text) > 220:
        text = text[:217].rstrip() + "..."
    return text


def outline(rel: str) -> tuple[str, str, list[tuple[str, str, str]]]:
    """Return (title, summary, [(heading, anchor, summary), ...]) for one page."""
    lines = read(rel).splitlines()
    title = os.path.basename(rel)
    in_fence = False
    h2s: list[tuple[int, str]] = []
    h1_at = None
    for i, raw in enumerate(lines):
        if FENCE_RE.match(raw.lstrip()):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if h1_at is None:
            m = H1_RE.match(raw)
            if m:
                title = plain(m.group(1))
                h1_at = i
                continue
        m = H2_RE.match(raw)
        if m:
            h2s.append((i, m.group(1)))
    intro_end = h2s[0][0] if h2s else len(lines)
    summary = first_sentence(lines[(h1_at + 1 if h1_at is not None else 0): intro_end])
    entries = []
    for n, (i, heading) in enumerate(h2s):
        end = h2s[n + 1][0] if n + 1 < len(h2s) else len(lines)
        entries.append((plain(heading), slugify(heading), first_sentence(lines[i + 1: end])))
    return title, summary, entries


def build_toc(pages: list[str]) -> str:
    out = io.StringIO()
    out.write(
        "<!-- GENERATED FILE. Do not edit by hand.\n"
        "     Produced by tools/build_llms_index.py from the headings under docs/.\n"
        "     Regenerate with: make docs-index -->\n\n"
    )
    out.write("# Table of contents\n\n")
    out.write(
        "Every page under `docs/`, every second-level heading on it, and the first sentence "
        "written under that heading. [llms.txt](../llms.txt) is the page-level map; this is "
        "the section-level one, for jumping to the right heading rather than the right file. "
        "Anchors are the ones GitHub renders, so every link below opens at its heading.\n\n"
    )
    out.write(PROVENANCE + "\n\n")
    current_section = None
    for rel in pages:
        section = rel.split("/")[1] if rel.count("/") == 2 else "docs"
        if section != current_section:
            current_section = section
            label = "Top level" if section == "docs" else f"docs/{section}/"
            out.write(f"## {label}\n\n")
        title, summary, entries = outline(rel)
        link = os.path.relpath(os.path.join(ROOT, rel), DOCS).replace(os.sep, "/")
        out.write(f"### [{title}]({link})\n\n")
        if summary:
            out.write(summary + "\n\n")
        for heading, anchor, sentence in entries:
            line = f"- [{heading}]({link}#{anchor})"
            if sentence:
                line += f": {sentence}"
            out.write(line + "\n")
        if entries:
            out.write("\n")
    return out.getvalue()


def build_full(pages: list[str]) -> str:
    out = io.StringIO()
    out.write("# SolarWinds Orion Guides: full text\n\n")
    out.write(
        "GENERATED FILE. Do not edit by hand. Produced by tools/build_llms_index.py; "
        "regenerate with: make docs-index\n\n"
    )
    out.write(
        "This is every page of the repository's documentation in one file, for AI systems "
        "that can fetch a URL but cannot run a command. The page-level index is llms.txt "
        "and the heading-level one is docs/TOC.md. Each page below starts with a line naming "
        "its path in the repository, so a fact found here can be cited to its source page. "
        "Relative links inside the pages are relative to that path.\n\n"
    )
    out.write(PROVENANCE + "\n\n")
    out.write(
        "Read AGENTS.md, reproduced first, before answering from this file: it states the "
        "one rule (never state a schema fact you have not looked up) and lists the few facts "
        "that need no lookup.\n\n"
    )
    for rel in ["AGENTS.md", "README.md"] + pages:
        out.write("\n\n" + "=" * 78 + "\n")
        out.write(f"FILE: {rel}\n")
        out.write("=" * 78 + "\n\n")
        out.write(read(rel).rstrip() + "\n")
    return out.getvalue()


def check_llms_txt(pages: list[str]) -> list[str]:
    """Every docs page listed, every relative link resolving. Returns problems."""
    problems: list[str] = []
    if not os.path.isfile(LLMS_TXT):
        return ["llms.txt is missing"]
    text = read("llms.txt")
    linked = set()
    for target in LINK_RE.findall(text):
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        target = target.split("#")[0]
        resolved = os.path.normpath(os.path.join(ROOT, target))
        if os.path.isdir(resolved):
            # A directory link is a pointer to data or scripts, not to a page; it only has
            # to exist. Its README, when it has one, counts as listed.
            linked.add(os.path.relpath(os.path.join(resolved, "README.md"), ROOT))
            continue
        if not os.path.exists(resolved):
            problems.append(f"llms.txt links to '{target}', which does not exist")
        linked.add(os.path.relpath(resolved, ROOT))
    for rel in pages:
        if rel not in linked:
            problems.append(f"llms.txt does not list {rel}")
    if "docs/TOC.md" not in linked:
        problems.append("llms.txt does not link docs/TOC.md")
    if "llms-full.txt" not in linked:
        problems.append("llms.txt does not link llms-full.txt")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="verify the generated files are current and llms.txt is complete; write nothing")
    args = ap.parse_args()

    pages = docs_pages()
    toc = build_toc(pages)
    full = build_full(pages)
    problems = check_llms_txt(pages)

    if args.check:
        for path, content, label in ((TOC_MD, toc, "docs/TOC.md"), (LLMS_FULL, full, "llms-full.txt")):
            if not os.path.isfile(path):
                problems.append(f"{label} is missing; run make docs-index")
            elif open(path, encoding="utf-8").read() != content:
                problems.append(f"{label} is out of date; run make docs-index")
        if problems:
            print("\n".join(problems), file=sys.stderr)
            sys.exit(1)
        n_h2 = sum(len(outline(p)[2]) for p in pages)
        print(f"llms.txt lists all {len(pages)} docs pages; docs/TOC.md ({n_h2} headings) and llms-full.txt are current")
        return

    with open(TOC_MD, "w", encoding="utf-8") as fh:
        fh.write(toc)
    with open(LLMS_FULL, "w", encoding="utf-8") as fh:
        fh.write(full)
    print(f"wrote docs/TOC.md and llms-full.txt for {len(pages)} pages")
    if problems:
        print("\n".join(problems), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Check that relative links between documentation files resolve.

Cross-links are the first thing to rot in a documentation repository: a file gets
renamed or moved and every link to it breaks silently, because nothing reads them until
a person clicks one. This walks every markdown file, resolves each relative link and
image against the filesystem, and reports the ones that point at nothing.

External links (http, https, mailto) are not fetched. That would make the check slow,
flaky, and dependent on network access from CI.

    python tools/check_links.py
    python tools/check_links.py --root docs
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# [text](target) but not ![image](target) handled separately; both are checked.
LINK_RE = re.compile(r"!?\[(?P<text>[^\]]*)\]\((?P<target>[^)\s]+)(?:\s+\"[^\"]*\")?\)")
# Fenced code blocks: links inside them are examples, not navigation.
FENCE_RE = re.compile(r"```.*?```", re.S)
INLINE_CODE_RE = re.compile(r"`[^`]*`")
# Markdown heading, for resolving #anchor fragments.
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$", re.M)

EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "tel:", "ftp://")


def slugify(heading: str) -> str:
    """Approximate GitHub's heading-to-anchor rule."""
    text = re.sub(r"`([^`]*)`", r"\1", heading)
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)  # links -> their text
    # Emphasis markers are dropped from the rendered text, but an underscore is not: GitHub
    # keeps it in the anchor, and headings here carry them inside code spans (`unique_key`).
    text = re.sub(r"[*~]", "", text)
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"\s+", "-", text)


def anchors_of(path: str) -> set[str]:
    try:
        text = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return set()
    text = FENCE_RE.sub("", text)
    found = set()
    counts: dict[str, int] = defaultdict(int)
    for _, heading in HEADING_RE.findall(text):
        base = slugify(heading)
        if not base:
            continue
        # GitHub disambiguates repeated headings with -1, -2, ...
        n = counts[base]
        found.add(base if n == 0 else f"{base}-{n}")
        counts[base] += 1
    # Explicit HTML anchors.
    found |= set(re.findall(r'<a\s+(?:name|id)="([^"]+)"', text))
    found |= set(re.findall(r'id="([^"]+)"', text))
    return found


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="directory to scan (default: repository root)")
    ap.add_argument("--check-anchors", action="store_true", help="also verify #fragments resolve")
    ap.add_argument("--orphans", action="store_true", help="also report pages nothing links to")
    args = ap.parse_args()

    scan_root = os.path.join(ROOT, args.root)
    files = []
    for dirpath, dirnames, filenames in os.walk(scan_root):
        dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", ".orionsdk"}]
        for name in filenames:
            if name.endswith(".md"):
                files.append(os.path.join(dirpath, name))
    files.sort()

    anchor_cache: dict[str, set[str]] = {}
    broken: list[str] = []
    checked = 0

    for path in files:
        text = open(path, encoding="utf-8", errors="replace").read()
        # Strip code so example links are not treated as navigation.
        text = FENCE_RE.sub("", text)
        text = INLINE_CODE_RE.sub("", text)
        rel_path = os.path.relpath(path, ROOT)

        for m in LINK_RE.finditer(text):
            target = m.group("target").strip()
            if not target or target.startswith(EXTERNAL_PREFIXES):
                continue
            checked += 1

            fragment = ""
            if "#" in target:
                target, _, fragment = target.partition("#")

            if not target:
                # Pure in-page anchor.
                if args.check_anchors and fragment:
                    anchors = anchor_cache.setdefault(path, anchors_of(path))
                    if fragment.lower() not in anchors:
                        broken.append(f"{rel_path}: in-page anchor #{fragment} not found")
                continue

            resolved = os.path.normpath(os.path.join(os.path.dirname(path), target))
            if os.path.isdir(resolved):
                # A directory link is fine if it holds a README.
                if os.path.isfile(os.path.join(resolved, "README.md")):
                    continue
                broken.append(f"{rel_path}: '{target}' is a directory with no README.md")
                continue
            if not os.path.exists(resolved):
                broken.append(f"{rel_path}: '{target}' does not exist")
                continue

            if args.check_anchors and fragment and resolved.endswith(".md"):
                anchors = anchor_cache.setdefault(resolved, anchors_of(resolved))
                if fragment.lower() not in anchors:
                    broken.append(f"{rel_path}: '{target}#{fragment}' - anchor not found")

    print(f"{len(files)} markdown file(s), {checked} relative link(s) checked")

    # A page nothing links to is invisible: it will not be found by a reader browsing from
    # the top, and it quietly falls out of date because nobody revisits it.
    if args.orphans:
        linked = set()
        for path in files:
            text = INLINE_CODE_RE.sub("", FENCE_RE.sub("", open(path, encoding="utf-8", errors="replace").read()))
            for m in LINK_RE.finditer(text):
                target = m.group("target").split("#")[0].strip()
                if not target or target.startswith(EXTERNAL_PREFIXES):
                    continue
                resolved = os.path.normpath(os.path.join(os.path.dirname(path), target))
                if os.path.isdir(resolved):
                    resolved = os.path.join(resolved, "README.md")
                linked.add(os.path.abspath(resolved))

        # Two things are reachable by convention rather than by a link: a README is the
        # index for its own directory, and everything under .github is wired up by GitHub
        # itself (issue and pull request templates).
        orphans = [
            os.path.relpath(p, ROOT)
            for p in files
            if os.path.abspath(p) not in linked
            and os.path.basename(p) != "README.md"
            and ".github" not in os.path.relpath(p, ROOT).split(os.sep)
        ]
        if orphans:
            print(f"\n{len(orphans)} page(s) nothing links to:", file=sys.stderr)
            for o in sorted(orphans):
                print(f"  - {o}", file=sys.stderr)
            print("Add each to the index for its section, or to a sibling page.", file=sys.stderr)
            broken.extend(f"orphan page: {o}" for o in orphans)

        # A section README is that section's index, and it goes stale in a specific way:
        # it is written before its later siblings exist, so those pages end up reachable
        # from somewhere but not from the index a reader actually browses.
        docs_root = os.path.join(ROOT, "docs")
        if os.path.isdir(docs_root):
            for name in sorted(os.listdir(docs_root)):
                section = os.path.join(docs_root, name)
                readme = os.path.join(section, "README.md")
                if not os.path.isdir(section) or not os.path.isfile(readme):
                    continue
                siblings = sorted(
                    f for f in os.listdir(section) if f.endswith(".md") and f != "README.md"
                )
                text = open(readme, encoding="utf-8", errors="replace").read()
                linked_here = set(re.findall(r"\]\(([\w.-]+\.md)\)", text))
                unlisted = [s for s in siblings if s not in linked_here]
                for s in unlisted:
                    broken.append(f"docs/{name}/README.md does not link to its sibling {s}")

    if broken:
        print(f"\n{len(broken)} broken link(s):", file=sys.stderr)
        for b in broken:
            print(f"  - {b}", file=sys.stderr)
        sys.exit(1)
    print("all relative links resolve")


if __name__ == "__main__":
    main()

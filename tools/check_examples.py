#!/usr/bin/env python3
"""Run the tool invocations shown in the documentation and check the output matches.

A page that shows a command and its output is making a claim, and that claim rots the
same way any other does. This finds every ``python3 tools/...`` invocation in a bash
block that is immediately followed by an output block, runs it, and compares.

    python tools/check_examples.py
    python tools/check_examples.py --verbose

Only the repository's own tools are executed. Anything touching a live Orion server, a
network, or a shell pipeline is skipped, since there is nothing here to run it against.

Documentation usually shows the first few lines of a long output, so a shown block passes
when its lines appear in order at the start of the real output. Elisions written as
``...`` or ``…`` on their own line allow a gap.
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# A bash block, then optional prose-free whitespace, then an output block. The output
# block is fenced with no language or with text/console, which is how these are written.
PAIR_RE = re.compile(
    r"```bash\n(?P<cmd>.*?)```\s*\n+```(?:text|console|)\n(?P<out>.*?)```",
    re.S,
)

# Only invocations of this repository's tools are safe and meaningful to run.
RUNNABLE_RE = re.compile(r"^\s*python3?\s+(?:tools/[\w./-]+\.py)\b")
ELISION_RE = re.compile(r"^\s*(?:\.\.\.|…)\s*$")


def runnable(cmd: str) -> str | None:
    """Return the single command to run, or None when the block is not eligible."""
    lines = [l for l in cmd.strip().splitlines() if l.strip() and not l.strip().startswith("#")]
    if len(lines) != 1:
        return None
    line = lines[0].strip()
    if not RUNNABLE_RE.match(line):
        return None
    # A pipeline or redirect means the shown output is not the tool's own.
    if any(ch in line for ch in "|><&;$`"):
        return None
    return line


def matches(shown: list[str], actual: list[str]) -> tuple[bool, str]:
    """True when the shown lines appear in order in the actual output.

    Documentation frequently quotes one section of a long output rather than the whole
    thing, so the first shown line may appear anywhere. After that the lines have to
    follow closely, which is what catches an output that has genuinely changed.
    """
    ai = 0
    # The first line anchors the excerpt wherever it lives.
    allow_gap = True
    for line in shown:
        if ELISION_RE.match(line):
            allow_gap = True
            continue
        # Compare on stripped text. A page quoting one line out of an indented block
        # reasonably drops the indentation, and failing over that would train authors to
        # stop quoting output rather than to quote it accurately. The words still have to
        # match exactly, which is what catches output that genuinely changed.
        target = line.strip()
        if not target:
            continue
        found = None
        limit = len(actual) if allow_gap else min(len(actual), ai + 3)
        for j in range(ai, limit):
            if actual[j].strip() == target:
                found = j
                break
        if found is None:
            near = actual[ai].strip() if ai < len(actual) else "(end of output)"
            return False, f"expected {target!r}\n           got {near!r}"
        ai = found + 1
        allow_gap = False
    return True, ""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="directory to scan for markdown")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    files = []
    for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, args.root)):
        dirnames[:] = [d for d in dirnames if d not in {".git", ".orionsdk", ".schema-versions"}]
        files.extend(os.path.join(dirpath, f) for f in filenames if f.endswith(".md"))
    files.sort()

    checked = skipped = 0
    failures: list[str] = []

    for path in files:
        text = open(path, encoding="utf-8", errors="replace").read()
        rel = os.path.relpath(path, ROOT)
        for m in PAIR_RE.finditer(text):
            cmd = runnable(m.group("cmd"))
            if cmd is None:
                skipped += 1
                continue
            checked += 1
            try:
                proc = subprocess.run(
                    shlex.split(cmd), cwd=ROOT, capture_output=True, text=True, timeout=180
                )
            except (subprocess.TimeoutExpired, OSError) as exc:
                failures.append(f"{rel}: `{cmd}` could not be run: {exc}")
                continue

            actual = (proc.stdout + proc.stderr).splitlines()
            ok, why = matches(m.group("out").splitlines(), actual)
            if ok:
                if args.verbose:
                    print(f"ok   {rel}: {cmd}")
            else:
                failures.append(f"{rel}: `{cmd}` output does not match\n           {why}")

    print(f"{checked} documented tool invocation(s) checked, {skipped} skipped as not runnable")
    if failures:
        print(f"\n{len(failures)} mismatch(es):", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        print(
            "\nEither the documentation is stale or the tool changed. Re-run the command "
            "and paste what it actually prints.",
            file=sys.stderr,
        )
        sys.exit(1)
    print("every documented tool invocation produces the output shown")


if __name__ == "__main__":
    main()

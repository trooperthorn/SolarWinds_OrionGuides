#!/usr/bin/env python3
"""Run the tool invocations shown in the documentation and check the output matches.

A page that shows a command and its output is making a claim, and that claim rots the
same way any other does. This finds every runnable invocation in a bash block that is
immediately followed by an output block, runs it, and compares.

    python tools/check_examples.py
    python tools/check_examples.py --verbose

Two kinds of command are executed: this repository's own tools, and ``jq`` against the
checked-in data. Both are read-only, offline, and deterministic. Anything touching a live
Orion server, a network, or a shell pipeline is skipped, since there is nothing here to
run it against.

Documentation usually shows the first few lines of a long output, so a shown block passes
when its lines appear in order at the start of the real output. Elisions written as
``...`` or ``…`` on their own line allow a gap.

PowerShell blocks cannot be executed here, so they get the strongest cheap check instead:
their brackets have to balance. A block truncated when it was pasted, or one that lost a
closing brace in an edit, fails the moment a reader runs it and is invisible until then.
"""

from __future__ import annotations

import argparse
import ast
import os
import re
import shlex
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# A bash block, then optional prose-free whitespace, then an output block. The output
# block is fenced with no language or with text/console, which is how these are written.
PAIR_RE = re.compile(
    r"```bash\n(?P<cmd>.*?)```\s*\n+```(?:text|console|json|)\n(?P<out>.*?)```",
    re.S,
)

# Two kinds of invocation are safe and meaningful to run: this repository's own tools,
# and jq against the checked-in data. Both are read-only, offline, and deterministic.
RUNNABLE_RE = re.compile(r"^\s*python3?\s+(?:tools/[\w./-]+\.py)\b")
JQ_RE = re.compile(r"^\s*jq\b")
ELISION_RE = re.compile(r"^\s*(?:\.\.\.|…)\s*$")


def runnable(cmd: str) -> str | None:
    """Return the single command to run, or None when the block is not eligible."""
    lines = [l for l in cmd.strip().splitlines() if l.strip() and not l.strip().startswith("#")]
    if len(lines) != 1:
        return None
    line = lines[0].strip()
    if not (RUNNABLE_RE.match(line) or JQ_RE.match(line)):
        return None
    # A pipeline or redirect means the shown output is not the command's own.
    if any(ch in line for ch in "|><&;$`"):
        return None
    # jq is only safe to run against files in this repository.
    if JQ_RE.match(line) and not re.search(r"\b(?:data|docs|scripts)/[\w./-]+", line):
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


PS_FENCE_RE = re.compile(r"```powershell\n(.*?)```", re.S)
# @' ... '@ and @" ... "@. These must be removed before counting anything, because the
# opening quote of a here-string otherwise pairs with a later one and swallows real code.
PS_HERESTRING_RE = re.compile(r"@(['\"])\r?\n.*?\r?\n\1@", re.S)
PS_STRING_RE = re.compile(r"'[^'\n]*'|\"[^\"\n]*\"")
PS_COMMENT_RE = re.compile(r"(?m)^\s*#.*$")


def check_powershell_balance(files: list[str]) -> tuple[int, list[str]]:
    """Report PowerShell blocks whose brackets do not balance.

    These cannot be executed here, so this is the strongest cheap check available: a
    block that was truncated when it was pasted, or that lost a closing brace in an edit,
    shows up as an imbalance and would fail the moment a reader ran it.
    """
    problems: list[str] = []
    total = 0
    for path in files:
        rel = os.path.relpath(path, ROOT)
        if "reference" in rel.split(os.sep):
            continue  # generated
        for i, block in enumerate(PS_FENCE_RE.findall(open(path, encoding="utf-8", errors="replace").read()), 1):
            total += 1
            stripped = PS_HERESTRING_RE.sub(" HERESTRING ", block)
            stripped = PS_STRING_RE.sub("", stripped)
            stripped = PS_COMMENT_RE.sub("", stripped)
            for open_ch, close_ch, name in (("{", "}", "brace"), ("(", ")", "paren"), ("[", "]", "bracket")):
                if stripped.count(open_ch) != stripped.count(close_ch):
                    first = block.strip().splitlines()[0][:70] if block.strip() else ""
                    problems.append(
                        f"{rel} powershell block {i}: {name}s do not balance "
                        f"({stripped.count(open_ch)} open, {stripped.count(close_ch)} close)\n"
                        f"           starts: {first}"
                    )
                    break
    return total, problems


PY_FENCE_RE = re.compile(r"```python\n(.*?)```", re.S)


def check_python_syntax(files: list[str]) -> tuple[int, list[str]]:
    """Parse every Python block. A block that does not parse cannot possibly run.

    This is stronger than the bracket check the PowerShell blocks get, because Python has
    a parser available here. It does not prove the example works against a live server,
    only that a reader who pastes it gets past the first line.
    """
    problems: list[str] = []
    total = 0
    for path in files:
        rel = os.path.relpath(path, ROOT)
        if "reference" in rel.split(os.sep):
            continue
        for i, block in enumerate(PY_FENCE_RE.findall(open(path, encoding="utf-8", errors="replace").read()), 1):
            total += 1
            try:
                ast.parse(block)
            except SyntaxError as exc:
                problems.append(
                    f"{rel} python block {i} does not parse: {exc.msg} (line {exc.lineno})"
                )
    return total, problems


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

    ps_total, ps_problems = check_powershell_balance(files)
    failures.extend(ps_problems)
    py_total, py_problems = check_python_syntax(files)
    failures.extend(py_problems)

    print(
        f"{checked} documented tool invocation(s) checked, {skipped} skipped as not "
        f"runnable; {ps_total} PowerShell block(s) checked for balance; "
        f"{py_total} Python block(s) parsed"
    )
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

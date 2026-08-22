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

Code blocks that are not runnable here still get the strongest cheap check available.
Python blocks are parsed, shell blocks go through ``bash -n``, and PowerShell blocks have
their brackets balanced, since there is no PowerShell in this environment. A block
truncated when it was pasted, or one that lost a closing brace in an edit, fails the
moment a reader runs it and is invisible until then.

The shipped ``.ps1`` scripts under ``scripts/`` get the same balance check. The Python
samples go through ``compileall`` in CI and the shell ones through ``bash -n``, which left
the PowerShell ones as the only shipped code with nothing checking it at all.

Finally, every documented invocation of this repository's own tools is run, whether or not
an output block follows it. Most are shown as "here is how to look this up" with nothing
after them, and those outnumber the ones with output about three to one. Asking only that
they run is a weaker claim than matching output, and it catches a different bug: a flag in
the wrong position, a renamed subcommand, an option that no longer exists. A reader who
pastes one of those gets an argparse error and no reason to trust the next example.
"""

from __future__ import annotations

import argparse
import ast
import glob
import os
import re
import shlex
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GENERATED_MARKER = "GENERATED FILE"

# A bash block, then optional prose-free whitespace, then an output block. The output
# block is fenced with no language or with text/console, which is how these are written.
# Neither group may cross a fence. With a plain ".*?" the command group runs forward
# from a bash block that has no output block under it until it finds some later pair,
# swallowing the real command/output pairs in between: the match then has a
# hundred-line "command", runnable() rejects it, and everything inside was skipped
# without a word. Most bash blocks are shown without their output, so this silently
# disabled the check across whole pages.
NOFENCE = r"(?:(?!```)[\s\S])*"
PAIR_RE = re.compile(
    rf"```bash\n(?P<cmd>{NOFENCE})```\s*\n+```(?:text|console|json|)\n(?P<out>{NOFENCE})```",
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


BASH_FENCE_RE = re.compile(r"```bash\n(.*?)```", re.S)
CONTINUATION_RE = re.compile(r"\\\n\s*")
TOOL_INVOCATION_RE = re.compile(r"^\s*python3?\s+tools/[\w./-]+\.py\b")
# argparse exits 2 and says one of these; a crash prints a traceback. Anything else,
# including a validator exiting 1 because it found real errors, is the tool working.
BROKEN_MARKERS = ("unrecognized arguments", "invalid choice", "Traceback (most recent call last)")
# An argument that names a path rather than a flag or a bare value.
PATH_ARG_RE = re.compile(r"^[.\w][\w./-]*/[\w./-]+$")


def is_ignored(rel_path: str) -> bool:
    """True when git ignores the path, so its absence is an environment difference."""
    try:
        return subprocess.run(
            ["git", "check-ignore", "-q", rel_path],
            cwd=ROOT, capture_output=True, timeout=10,
        ).returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def check_tool_invocations(files: list[str]) -> tuple[int, list[str]]:
    """Run every documented invocation of this repository's own tools.

    The output comparison above only covers a command that is followed by an output block,
    which is a minority of them: most invocations are shown as "here is how to look this
    up" with no output. Those were unchecked, and a reader who pastes one gets an argparse
    error. This runs them and asks only that they run, which is a weaker claim than
    matching output and catches a different bug: a flag in the wrong position, a renamed
    subcommand, an option that no longer exists.
    """
    problems: list[str] = []
    seen: dict[str, str] = {}
    for path in files:
        rel = os.path.relpath(path, ROOT)
        text = open(path, encoding="utf-8", errors="replace").read()
        if GENERATED_MARKER in text[:400]:
            continue
        for block in BASH_FENCE_RE.findall(text):
            # A command split over several lines with trailing backslashes is one command.
            for line in CONTINUATION_RE.sub(" ", block).splitlines():
                line = line.strip()
                if not TOOL_INVOCATION_RE.match(line):
                    continue
                # A pipeline or redirect is a shell construct, not a single invocation.
                if any(ch in line for ch in "|><&;$`"):
                    continue
                seen.setdefault(line, rel)

    skipped_inputs = 0
    for line, rel in list(seen.items()):
        # A documented command may read a file this checkout does not have. The SDK
        # sparse-checkout under .orionsdk/ is the case here: it is gitignored scratch that
        # `make sdk` fetches and `make clean` removes, so on a fresh clone the command is
        # correct and its input is simply absent. Failing there reports a broken document
        # for an environment difference. A path that git tracks and that is missing is a
        # different matter and still fails.
        missing = [a for a in shlex.split(line, comments=True)[1:]
                   if PATH_ARG_RE.match(a) and not os.path.exists(os.path.join(ROOT, a))]
        if missing and all(is_ignored(a) for a in missing):
            del seen[line]
            skipped_inputs += 1
            continue
        try:
            # comments=True so a trailing "# what this does" is stripped the way a shell
            # would strip it, rather than being passed along as an argument.
            proc = subprocess.run(
                shlex.split(line, comments=True), cwd=ROOT,
                capture_output=True, text=True, timeout=180,
                # A documented command may read stdin -- validate_swql.py takes "-" for a
                # query on standard input. Inheriting this process's stdin leaves it
                # blocking on a terminal that will never send anything, and the whole
                # check dies on the timeout. EOF is the right answer here: the command
                # runs, reads nothing, and exits.
                stdin=subprocess.DEVNULL,
            )
        except (subprocess.TimeoutExpired, OSError, ValueError) as exc:
            problems.append(f"{rel}: `{line[:90]}` could not be run: {exc}")
            continue
        output = proc.stdout + proc.stderr
        if proc.returncode == 2 or any(marker in output for marker in BROKEN_MARKERS):
            detail = (output.strip().splitlines() or ["failed"])[-1]
            problems.append(f"{rel}: `{line[:90]}` does not run\n           {detail[:120]}")
    if skipped_inputs:
        print(f"note: {skipped_inputs} documented invocation(s) skipped, their input files "
              f"are not in this checkout")
    return len(seen), problems


def check_powershell_scripts() -> tuple[int, list[str]]:
    """Balance-check the shipped .ps1 files, which nothing else parses.

    The Python samples go through compileall and the shell ones through `bash -n`, but
    there is no PowerShell available here, so these three shipped scripts had no check at
    all. They are the ones a reader is most likely to run unmodified.
    """
    problems: list[str] = []
    paths = sorted(glob.glob(os.path.join(ROOT, "scripts", "**", "*.ps1"), recursive=True))
    for path in paths:
        rel = os.path.relpath(path, ROOT)
        source = open(path, encoding="utf-8", errors="replace").read()
        stripped = PS_HERESTRING_RE.sub(" HERESTRING ", source)
        stripped = PS_STRING_RE.sub("", stripped)
        stripped = PS_COMMENT_RE.sub("", stripped)
        for open_ch, close_ch, name in (("{", "}", "brace"), ("(", ")", "paren"), ("[", "]", "bracket")):
            if stripped.count(open_ch) != stripped.count(close_ch):
                problems.append(
                    f"{rel}: {name}s do not balance "
                    f"({stripped.count(open_ch)} open, {stripped.count(close_ch)} close)"
                )
                break
    return len(paths), problems


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


SH_FENCE_RE = re.compile(r"```(?:bash|sh|shell)\n(.*?)```", re.S)
# Documentation writes placeholders as <Entity> and <keyword>. Bash reads those as
# redirections, so they have to be substituted before parsing or every usage block that
# follows the convention is reported as a syntax error.
SH_PLACEHOLDER_RE = re.compile(r"<[A-Za-z][\w .:/-]*>")


def check_shell_syntax(files: list[str]) -> tuple[int, list[str]]:
    """Parse every shell block with `bash -n`, without running any of it."""
    problems: list[str] = []
    total = 0
    for path in files:
        rel = os.path.relpath(path, ROOT)
        if "reference" in rel.split(os.sep):
            continue
        for i, block in enumerate(SH_FENCE_RE.findall(open(path, encoding="utf-8", errors="replace").read()), 1):
            total += 1
            src = SH_PLACEHOLDER_RE.sub("PLACEHOLDER", block)
            with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False, encoding="utf-8") as fh:
                fh.write(src)
                tmp = fh.name
            try:
                proc = subprocess.run(["bash", "-n", tmp], capture_output=True, text=True, timeout=30)
            except (subprocess.TimeoutExpired, OSError):
                os.unlink(tmp)
                continue
            os.unlink(tmp)
            if proc.returncode != 0:
                detail = (proc.stderr.strip().splitlines() or ["syntax error"])[0]
                problems.append(f"{rel} shell block {i} does not parse: {detail[:120]}")
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
                    shlex.split(cmd), cwd=ROOT, capture_output=True, text=True,
                    timeout=180, stdin=subprocess.DEVNULL,
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
    sh_total, sh_problems = check_shell_syntax(files)
    failures.extend(sh_problems)
    ps_script_total, ps_script_problems = check_powershell_scripts()
    failures.extend(ps_script_problems)
    invocation_total, invocation_problems = check_tool_invocations(files)
    failures.extend(invocation_problems)

    print(
        f"{checked} documented tool invocation(s) checked, {skipped} skipped as not "
        f"runnable; {ps_total} PowerShell block(s) checked for balance; "
        f"{py_total} Python and {sh_total} shell block(s) parsed; "
        f"{ps_script_total} shipped PowerShell script(s) checked for balance; "
        f"{invocation_total} distinct tool invocation(s) run"
    )
    if failures:
        print(f"\n{len(failures)} mismatch(es):", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        print(
            "\nFor an output mismatch: either the page is stale or the tool changed, so "
            "re-run\nthe command and paste what it actually prints. For a block that does "
            "not parse or\nwhose brackets do not balance: it was truncated or edited into "
            "an unrunnable state.",
            file=sys.stderr,
        )
        sys.exit(1)
    print("every documented tool invocation produces the output shown")


if __name__ == "__main__":
    main()

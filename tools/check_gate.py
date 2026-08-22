#!/usr/bin/env python3
"""Prove the checks are live by seeding known errors and requiring them to be caught.

Every other tool here answers "is the documentation right?". This one answers "would we
know if it were wrong?", which is a different question and the one that goes unasked. A
checker that silently stops checking reports success, so it is indistinguishable from a
checker that works until something depends on it.

    python tools/check_gate.py
    python tools/check_gate.py --verbose     # show each checker's output

That is not hypothetical. Three real cases in this repository:

  - check_examples.py paired a command block with the output block under it using a
    non-greedy wildcard. Most commands are shown without output, so on reaching one of
    those the pattern ran forward and swallowed the genuine pairs in between. It reported
    success over 14 pairs it never compared.
  - The property-table check collected its findings into a list that was never printed and
    never reached the exit condition. It resolved 26 tables and passed regardless.
  - Its first working version then resolved the wrong entity for a table and reported nine
    false positives on a correct page.

Each case is invisible from the passing output and obvious the moment a seeded error goes
unreported. So each mutation below is a real defect of the kind the guides could plausibly
acquire in an edit: a renamed entity, a count off by one, a type that is close but wrong, an
argument inserted mid-signature, a column that does not exist, a stale pasted output, a link
to a moved page.

The file is restored from memory rather than from git, so this is safe to run with
uncommitted work in the tree. It restores in a finally block, so an interrupted run leaves
the tree as it found it.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION = "2026.2"

# (label, file, text to find, what to replace it with, the command that must object).
# The anchor has to be text this repository actually contains, so a page rewrite that
# removes one is reported as a stale case rather than passing quietly.
CASES = [
    (
        "entity name",
        "docs/automation/dependencies.md",
        "FROM Orion.DependencyEntities de",
        "FROM Orion.DependencyEntitiez de",
        ["tools/check_entity_references.py", "--version", VERSION, "--strict"],
    ),
    (
        "property count",
        "docs/automation/dependencies.md",
        "| `Orion.AutoDependencyRoot` | Roots the automatic discovery works out from, per engine | 6 properties |",
        "| `Orion.AutoDependencyRoot` | Roots the automatic discovery works out from, per engine | 7 properties |",
        ["tools/check_counts.py", "--version", VERSION],
    ),
    (
        "property type",
        "docs/automation/scheduling.md",
        "| `UtcOffsetInMinutes` | `System.Double` |",
        "| `UtcOffsetInMinutes` | `System.Int32` |",
        ["tools/check_entity_references.py", "--version", VERSION, "--strict"],
    ),
    (
        "verb signature",
        "docs/automation/dependencies.md",
        "Orion.Dependencies.RemoveDependencies(ids) -> number",
        "Orion.Dependencies.RemoveDependencies(ids, force) -> number",
        ["tools/check_signatures.py", "--version", VERSION],
    ),
    (
        "swql column",
        "docs/automation/scheduling.md",
        "    f.CronExpressionTimeZoneInfo,",
        "    f.CronExpressionTimeZoneInfoo,",
        ["tools/validate_swql.py", "--docs", "docs"],
    ),
    (
        "tool output",
        "docs/automation/alerts.md",
        "  requires: manageAlerts\n  parameters (2):",
        "  requires: manageEverything\n  parameters (2):",
        ["tools/check_examples.py"],
    ),
    (
        "test count",
        "tools/README.md",
        "Regressions in the judgement above: 179 tests",
        "Regressions in the judgement above: 178 tests",
        ["tools/check_data.py", "--version", VERSION],
    ),
    (
        "relative link",
        "docs/automation/dependencies.md",
        "[accounts-and-permissions.md](accounts-and-permissions.md)",
        "[accounts-and-permissions.md](accounts-and-permissions-nope.md)",
        ["tools/check_links.py", "--orphans", "--check-anchors"],
    ),
]


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable] + cmd, capture_output=True, text=True, cwd=ROOT)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true", help="show each checker's output")
    args = parser.parse_args()

    problems: list[str] = []
    for label, rel, old, new, cmd in CASES:
        path = os.path.join(ROOT, rel)
        with open(path, encoding="utf-8") as fh:
            original = fh.read()
        if old not in original:
            problems.append(
                f"{label}: the seeded text is no longer in {rel}, so this case tests "
                f"nothing. Re-anchor it on text the page still contains."
            )
            continue
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(original.replace(old, new, 1))
            result = run(cmd)
        finally:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(original)

        tool = os.path.basename(cmd[0])
        if result.returncode == 0:
            problems.append(f"{label}: {tool} exited 0 on a seeded error in {rel}")
            print(f"  MISSED  {label:16} {tool}")
        else:
            print(f"  caught  {label:16} {tool}")
        if args.verbose:
            for line in (result.stdout + result.stderr).splitlines():
                print(f"          {line}")

    print(f"\n{len(CASES) - len(problems)}/{len(CASES)} seeded error(s) caught")
    if problems:
        print("\nthe gate does not catch:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        print(
            "\nA check that passes over a seeded error passes over a real one. Fix the\n"
            "checker rather than the seed, unless the seed itself has gone stale.",
            file=sys.stderr,
        )
        sys.exit(1)
    print("every seeded error is caught by the check it belongs to")


if __name__ == "__main__":
    main()

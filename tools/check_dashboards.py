#!/usr/bin/env python3
"""Hold the shipped Modern Dashboard files to the invariants the guides claim decide them.

    python tools/check_dashboards.py
    python tools/check_dashboards.py scripts/dashboards/minimal-dashboard.json

docs/webui/modern-dashboard-authoring.md states five rules, read off five real exports from
two independent authors, and says a file that breaks any of them either fails to import or
imports and then misbehaves. A template that shipped breaking one of them would teach the
mistake it warns about, so the rules are checked here rather than trusted.

The failure modes are quiet, which is the reason this exists at all:

  - A duplicated `unique_key` is what you get by copying a widget, and both authors' real
    files carry collisions. The console does not object; the dashboard just renders the wrong
    widget where the copy should be.
  - The SWQL is stored twice per widget. Edit one copy and the file still imports, still
    validates, and the widget runs whichever copy the renderer reaches for.
  - A `dataFields` id that no longer matches a column of its query renders a blank column
    rather than raising.

The SWQL itself is not checked here. `tools/validate_swql.py` reads dashboard JSON directly
and `make validate` already walks `scripts/`, so the queries are covered where every other
query in the repository is.
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_GLOB = os.path.join(ROOT, "scripts", "dashboards", "*.json")

# `AS [Two Words]` and `AS OneWord`. Aliasing is how every dataField in every sample export
# is produced, so an id that is not an alias is the thing to report.
ALIAS_RE = re.compile(r"\bAS\s+(?:\[([^\]]+)\]|(\w+))", re.I)


def aliases(swql: str) -> set[str]:
    return {a or b for a, b in ALIAS_RE.findall(swql)}


def check(path: str) -> list[str]:
    rel = os.path.relpath(path, ROOT)
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except json.JSONDecodeError as exc:
        return [f"{rel}: not valid JSON: {exc}"]

    problems: list[str] = []
    for key in ("version", "dashboards", "widgets", "remove"):
        if key not in doc:
            problems.append(f"{rel}: the envelope is missing {key!r}")
    if problems:
        return problems

    widgets = doc["widgets"]

    # 1. Every unique_key is distinct.
    counts = collections.Counter(w.get("unique_key") for w in widgets)
    for key, n in counts.items():
        if n > 1:
            names = sorted({w.get("name", "?") for w in widgets if w.get("unique_key") == key})
            problems.append(
                f"{rel}: unique_key {key} defines {n} widgets ({', '.join(names)}). "
                f"Regenerate the key on every copy."
            )

    # 2. Every placement resolves to a definition.
    defined = set(counts)
    for dash in doc["dashboards"]:
        for placement in dash.get("widgets", []):
            if placement.get("unique_key") not in defined:
                problems.append(
                    f"{rel}: dashboard {dash.get('name', '?')!r} places widget "
                    f"{placement.get('unique_key')}, which no definition provides"
                )

    # 3/4. The SWQL and dataFields are stored twice, and every dataField id is a column the
    # query returns. Both live under any node carrying a dataSource, at any depth.
    def walk(node, trail: str) -> None:
        if isinstance(node, dict):
            source = node.get("dataSource")
            adapter = node.get("adapter")
            if isinstance(source, dict) and isinstance(adapter, dict):
                a = source.get("properties", {})
                b = adapter.get("properties", {}).get("dataSource", {}).get("properties", {})
                if a.get("swql") != b.get("swql"):
                    problems.append(
                        f"{rel}: {trail}: the dataSource and adapter copies of the SWQL differ. "
                        f"Both are real; edit both."
                    )
                if a.get("dataFields") != b.get("dataFields"):
                    problems.append(
                        f"{rel}: {trail}: the dataSource and adapter copies of dataFields differ"
                    )
            if isinstance(node.get("swql"), str) and isinstance(node.get("dataFields"), list):
                names = aliases(node["swql"])
                for field in node["dataFields"]:
                    if field.get("id") not in names:
                        problems.append(
                            f"{rel}: {trail}: dataField {field.get('id')!r} is not an alias of "
                            f"its query, so the column renders blank"
                        )
            for k, v in node.items():
                walk(v, f"{trail}/{k}" if trail else k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{trail}[{i}]")

    walk(doc, "")

    # 5. Every KPI tile named in `nodes` has a configuration block, and the id agrees in all
    # three of the places it is written.
    for widget in widgets:
        config = widget.get("configuration", {})
        tiles = config.get("tiles", {}).get("properties", {}).get("nodes")
        if not tiles:
            continue
        for tile_id in tiles:
            block = config.get(tile_id)
            if not isinstance(block, dict):
                problems.append(
                    f"{rel}: {widget.get('name', '?')!r} lists tile {tile_id} but has no "
                    f"configuration block for it"
                )
                continue
            if block.get("id") != tile_id:
                problems.append(f"{rel}: tile {tile_id}: its own id field says {block.get('id')}")
            component = (
                block.get("providers", {}).get("adapter", {}).get("properties", {}).get("componentId")
            )
            if component != tile_id:
                problems.append(
                    f"{rel}: tile {tile_id}: adapter componentId says {component}"
                )

    # Table columns bind data fields by id, and sort by a column id rather than a field.
    for widget in widgets:
        table = widget.get("configuration", {}).get("table")
        if not table:
            continue
        field_ids = {
            f.get("id")
            for f in table.get("providers", {}).get("dataSource", {}).get("properties", {}).get("dataFields", [])
        }
        config = table.get("properties", {}).get("configuration", {})
        column_ids = set()
        for column in config.get("columns", []):
            column_ids.add(column.get("id"))
            bindings = column.get("formatter", {}).get("properties", {}).get("dataFieldIds", {})
            for role, value in bindings.items():
                if value is not None and value not in field_ids:
                    problems.append(
                        f"{rel}: column {column.get('label')!r} binds {role} to {value!r}, "
                        f"which is not a dataField of its query"
                    )
        sort_by = config.get("sorterConfiguration", {}).get("sortBy")
        if sort_by is not None and sort_by not in column_ids:
            problems.append(
                f"{rel}: {widget.get('name', '?')!r} sorts by {sort_by!r}, which is not one of "
                f"its column ids (sortBy takes a column id, not a data field)"
            )

    return problems


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="dashboard .json files (default: scripts/dashboards/)")
    args = ap.parse_args()

    paths = args.paths or sorted(glob.glob(DEFAULT_GLOB))
    if not paths:
        print("no dashboard files found", file=sys.stderr)
        sys.exit(0)

    problems: list[str] = []
    widgets = queries = 0
    for path in paths:
        problems.extend(check(path))
        try:
            with open(path, encoding="utf-8") as fh:
                doc = json.load(fh)
            widgets += len(doc.get("widgets", []))
            queries += json.dumps(doc).count('"swql"')
        except (json.JSONDecodeError, OSError):
            pass

    print(
        f"{len(paths)} dashboard file(s), {widgets} widget definition(s) and "
        f"{queries} embedded query/queries checked"
    )
    if problems:
        print("\ndashboard problem(s):", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        sys.exit(1)
    print("every shipped dashboard satisfies the invariants in docs/webui/modern-dashboard-authoring.md")


if __name__ == "__main__":
    main()

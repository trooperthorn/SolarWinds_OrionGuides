#!/usr/bin/env python3
"""Read-only identity audit across Modern Dashboard JSON files and ZIP packages.

Print a JSON report; exit 1 for conflicting definitions or unresolved placements,
2 for invalid input, and 0 otherwise. Identical shared definitions are reported too:
they still need an explicit sharing decision. Does not contact or modify a server.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import itertools
import json
from pathlib import Path
import sys
import uuid
import zipfile


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    # Keep strings, numeric representations, array order and missing fields intact.
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def identity(key):
    if not isinstance(key, str) or not key.strip():
        raise ValueError("identity must be a nonempty string")
    try:
        return str(uuid.UUID(key))
    except ValueError:
        # Named product keys are valid. Server collation is not inferred here.
        return key


def unique_members(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate JSON member: {key}")
        obj[key] = value
    return obj


def changed_paths(left, right, path=""):
    """JSON pointers; do not include query text or credentials in the report."""
    if type(left) is not type(right):
        return [path or "/"]
    if isinstance(left, dict):
        paths = []
        for key in sorted(left.keys() | right.keys()):
            child = path + "/" + key.replace("~", "~0").replace("/", "~1")
            if key not in left or key not in right:
                paths.append(child)
            else:
                paths.extend(changed_paths(left[key], right[key], child))
        return paths
    if isinstance(left, list):
        if len(left) != len(right):
            return [path or "/"]
        return [p for i, (a, b) in enumerate(zip(left, right))
                for p in changed_paths(a, b, path + "/" + str(i))]
    return [] if left == right else [path or "/"]


def load(paths):
    documents, packages = [], []
    for source_id, path in enumerate(map(Path, paths)):
        raw = path.read_bytes()
        packages.append({"source_id": source_id, "name": path.name,
                         "bytes": len(raw), "sha256": digest(raw)})
        if path.suffix.lower() == ".zip":
            with zipfile.ZipFile(path) as archive:
                members = [i for i in archive.infolist()
                           if not i.is_dir() and i.filename.lower().endswith(".json")]
                names = [i.filename for i in members]
                if len(names) != len(set(names)):
                    raise ValueError(f"{path.name}: duplicate ZIP member names")
                if sum(i.file_size for i in members) > 100 * 1024 * 1024:
                    raise ValueError(f"{path.name}: JSON members exceed 100 MiB audit limit")
                inputs = [(i.filename, archive.read(i)) for i in members]
        else:
            inputs = [(path.name, raw)]
        if not inputs:
            raise ValueError(f"{path.name}: no JSON documents")
        for member, content in inputs:
            obj = json.loads(content, object_pairs_hook=unique_members)
            if not isinstance(obj, dict) or any(not isinstance(obj.get(k), list)
                                              for k in ("dashboards", "widgets")):
                raise ValueError(f"{member}: expected dashboard export envelope")
            documents.append({"source_id": source_id, "package": path.name,
                              "member": member, "sha256": digest(content), "data": obj})
    return documents, packages


def audit(documents, packages):
    registry = {"dashboard": defaultdict(list), "widget": defaultdict(list)}
    unresolved, files = [], []
    for file_id, source in enumerate(documents):
        obj = source["data"]
        origin = {k: v for k, v in source.items() if k != "data"}
        origin["file_id"] = file_id
        files.append({**origin, "dashboard_count": len(obj["dashboards"]),
                      "widget_definition_count": len(obj["widgets"])})
        definitions = {identity(w.get("unique_key")) for w in obj["widgets"]}
        placements = defaultdict(list)
        for di, dashboard in enumerate(obj["dashboards"]):
            for pi, placement in enumerate(dashboard.get("widgets", [])):
                key = identity(placement.get("unique_key"))
                record = {"dashboard": dashboard.get("name"),
                          "dashboard_key": dashboard.get("unique_key"),
                          "pointer": f"/dashboards/{di}/widgets/{pi}",
                          "reference": placement.get("reference"),
                          "location": placement.get("location")}
                placements[key].append(record)
                if key not in definitions:
                    unresolved.append({**origin, **record, "widget_key": key})
        for kind, field in (("dashboard", "dashboards"), ("widget", "widgets")):
            for index, definition in enumerate(obj[field]):
                key = identity(definition.get("unique_key"))
                payload = {k: v for k, v in definition.items() if k != "unique_key"}
                registry[kind][key].append({
                    **origin, "pointer": f"/{field}/{index}",
                    "name": definition.get("name"), "original_key": definition["unique_key"],
                    "definition_sha256": digest(canonical(payload).encode("utf-8")),
                    "placements": placements[key] if kind == "widget" else [],
                    "_payload": payload})
    findings = []
    for kind, entries in registry.items():
        for key, records in sorted(entries.items()):
            if len(records) < 2:
                continue
            differences = []
            for ai, bi in itertools.combinations(range(len(records)), 2):
                paths = changed_paths(records[ai]["_payload"], records[bi]["_payload"])
                if paths:
                    differences.append({"left_occurrence": ai, "right_occurrence": bi,
                                        "changed_paths": paths})
            findings.append({"kind": kind, "unique_key": key,
                             "classification": "same_key_different_definition" if differences
                             else "same_key_same_definition",
                             "cross_package": len({r["source_id"] for r in records}) > 1,
                             "occurrences": [{k: v for k, v in r.items() if k != "_payload"}
                                             for r in records], "differences": differences})
    return {"format_version": 1, "comparison": "Parsed JSON; object keys sorted; only root unique_key excluded; no SWQL normalization",
            "identity_comparison": "UUID spellings normalized; named keys compared exactly; server collation unverified",
            "packages": packages, "files": files,
            "summary": {"files": len(files),
                        "dashboard_definitions": sum(f["dashboard_count"] for f in files),
                        "widget_definitions": sum(f["widget_definition_count"] for f in files),
                        "distinct_dashboard_keys": len(registry["dashboard"]),
                        "distinct_widget_keys": len(registry["widget"]),
                        "repeated_keys": len(findings),
                        "conflicting_keys": sum(bool(f["differences"]) for f in findings),
                        "cross_package_repeated_keys": sum(f["cross_package"] for f in findings),
                        "unresolved_placements": len(unresolved)},
            "findings": findings, "unresolved_placements": unresolved}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="JSON exports or ZIPs of JSON exports")
    args = parser.parse_args()
    try:
        report = audit(*load(args.paths))
    except (OSError, ValueError, TypeError, KeyError, AttributeError, zipfile.BadZipFile) as error:
        print(f"identity audit failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return int(bool(report["summary"]["conflicting_keys"] or report["unresolved_placements"]))


if __name__ == "__main__":
    sys.exit(main())

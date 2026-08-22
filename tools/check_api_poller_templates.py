#!/usr/bin/env python3
"""Hold the shipped API Poller templates to the structure the guides document.

    python tools/check_api_poller_templates.py
    python tools/check_api_poller_templates.py path/to/one.apipoller.template

docs/polling/api-pollers.md documents the `.apipoller.template` format, derived by parsing a
real export. A sample that drifted from that description would teach the wrong shape, and the
failure would be silent in the worst way: the console rejects a bad import with a message about
XML, long after someone has copied the file as a starting point.

The checks are the ones the page states as rules:

  - it parses, and the root is <Template>
  - the elements the serialiser always writes are present, including the empty ones
  - Guid is a well-formed GUID, and no two shipped templates share one
  - PollingInterval and RequestDetailsOrder are integers, and order starts at 0
  - every ValueToMonitor has a Path, a Type and both thresholds
  - a string-to-number fallback that sits below the critical threshold is reported, because
    it silently reclassifies an unrecognised API response as healthy

That last one is a judgement rather than a schema rule, and it is here because it is the
mistake the format invites. An API Poller evaluates status on a number and only on a number,
so a text-answering endpoint reaches Up/Warning/Critical through the string rules; matching is
exact, so a provider rewording one status drops that response onto the fallback. Put the
fallback below the critical threshold and that rewording turns the alert off rather than on.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_GLOB = os.path.join(ROOT, "scripts", "api-pollers", "*.apipoller.template")

GUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

# Written by the serialiser on every export, empty ones included.
TEMPLATE_ELEMENTS = ["Guid", "Name", "DisplayName", "Description", "Created", "Updated",
                     "Version", "RequestDetailsCollection", "PollingInterval"]
REQUEST_ELEMENTS = ["Url", "Body", "HttpVerb", "RequestHeaders", "ValueToMonitorCollection",
                    "RequestVariables", "RequestDetailsOrder"]
VALUE_ELEMENTS = ["DisplayName", "Path", "ThresholdRule", "WarningThresholdValue",
                  "CriticalThresholdValue", "Type",
                  "StringToNumberTransformationOtherValues"]


def text(node: ET.Element, name: str) -> str | None:
    child = node.find(name)
    return None if child is None else (child.text or "")


def check(path: str, seen_guids: dict[str, str]) -> list[str]:
    rel = os.path.relpath(path, ROOT)
    try:
        root = ET.parse(path).getroot()
    except FileNotFoundError:
        return [f"{rel}: no such file"]
    except ET.ParseError as exc:
        return [f"{rel}: not well-formed XML: {exc}"]
    except OSError as exc:
        return [f"{rel}: cannot be read: {exc}"]

    problems: list[str] = []
    if root.tag != "Template":
        problems.append(f"{rel}: root element is <{root.tag}>, expected <Template>")
        return problems

    for name in TEMPLATE_ELEMENTS:
        if root.find(name) is None:
            problems.append(f"{rel}: missing <{name}>; the serialiser writes it even when empty")

    guid = (text(root, "Guid") or "").strip()
    if guid and not GUID_RE.match(guid):
        problems.append(f"{rel}: Guid {guid!r} is not a GUID")
    elif guid:
        if guid in seen_guids:
            problems.append(
                f"{rel}: Guid {guid} is also used by {seen_guids[guid]}. The GUID is the "
                f"template's identity across servers; regenerate it on a copy."
            )
        seen_guids[guid] = rel

    interval = (text(root, "PollingInterval") or "").strip()
    if interval and not interval.isdigit():
        problems.append(f"{rel}: PollingInterval {interval!r} is not an integer number of minutes")

    requests = root.findall("./RequestDetailsCollection/RequestDetails")
    if not requests:
        problems.append(f"{rel}: no <RequestDetails>; a template makes at least one request")

    orders = []
    for i, req in enumerate(requests):
        where = f"{rel}: request {i}"
        for name in REQUEST_ELEMENTS:
            if req.find(name) is None:
                problems.append(f"{where}: missing <{name}>")
        verb = (text(req, "HttpVerb") or "").strip()
        if verb and verb != verb.capitalize():
            problems.append(
                f"{where}: HttpVerb {verb!r} is not title-case; the serialiser writes 'Get', not 'GET'")
        order = (text(req, "RequestDetailsOrder") or "").strip()
        if order.isdigit():
            orders.append(int(order))
        elif order:
            problems.append(f"{where}: RequestDetailsOrder {order!r} is not an integer")

        for value in req.findall("./ValueToMonitorCollection/ValueToMonitor"):
            label = (text(value, "DisplayName") or "?").strip()
            for name in VALUE_ELEMENTS:
                if value.find(name) is None:
                    problems.append(f"{where}, value {label!r}: missing <{name}>")
            problems.extend(check_fallback(where, label, value))

    if orders and sorted(orders) != list(range(len(orders))):
        problems.append(
            f"{rel}: RequestDetailsOrder values are {sorted(orders)}; they should be 0..n "
            f"with no gaps or repeats")
    return problems


def check_fallback(where: str, label: str, value: ET.Element) -> list[str]:
    """A fallback below the critical threshold turns an unknown response into 'healthy'."""
    rules = value.findall("./StringToNumberTransformationRules/StringToNumberTransformationRule")
    if not rules:
        return []
    try:
        fallback = float((text(value, "StringToNumberTransformationOtherValues") or "").strip())
        critical = float((text(value, "CriticalThresholdValue") or "").strip())
    except ValueError:
        return [f"{where}, value {label!r}: threshold or fallback is not numeric"]
    if (text(value, "ThresholdRule") or "").strip() != "GreaterThan":
        return []
    if fallback <= critical:
        return [
            f"{where}, value {label!r}: the string-to-number fallback is {fallback:g} and the "
            f"critical threshold is {critical:g}, so a response none of the {len(rules)} rules "
            f"match reads as healthy. Set the fallback above critical so an unrecognised value "
            f"alerts instead of hiding."
        ]
    return []


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="template files (default: scripts/api-pollers/)")
    args = ap.parse_args()

    paths = args.paths or sorted(glob.glob(DEFAULT_GLOB))
    if not paths:
        print("no template files found", file=sys.stderr)
        sys.exit(0)

    problems: list[str] = []
    seen: dict[str, str] = {}
    metrics = 0
    for path in paths:
        problems.extend(check(path, seen))
        try:
            root = ET.parse(path).getroot()
            metrics += len(root.findall(".//ValueToMonitor"))
        except (ET.ParseError, OSError):
            pass

    print(f"{len(paths)} API poller template(s), {metrics} value(s) to monitor checked")
    if problems:
        print("\ntemplate problem(s):", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        sys.exit(1)
    print("every shipped template matches the format in docs/polling/api-pollers.md")


if __name__ == "__main__":
    main()

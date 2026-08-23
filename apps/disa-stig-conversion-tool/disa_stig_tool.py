#!/usr/bin/env python3
"""DISA STIG Conversion Tool — DISA STIG to SolarWinds compliance importer.

One self-contained file: GUI and CLI together, standard library only.

Takes a STIG package as DISA publishes it on https://public.cyber.mil/stigs/downloads/
(a zip whose payload is one or more XCCDF benchmark files named ``*-xccdf.xml``; the
``.xsl`` alongside them is only the browser stylesheet) and turns every rule into a
rule in an NCM compliance policy report, delivered to the server through the SWIS
verbs on ``Cirrus.PolicyReports``. An SCM compliance policy ``.yaml`` instead imports
verbatim through ``Orion.PolicyEngine.Policy.ImportPolicy``.

    Open the GUI (also what a double-click on Windows does):
        python disa_stig_tool.py

    Build a Windows .exe of it:
        pip install pyinstaller
        pyinstaller --onefile --windowed --name DISASTIGConversionTool disa_stig_tool.py

    Download a package from DISA's public mirror:
        python disa_stig_tool.py download U_Cisco_IOS_Router_Y26M07_STIG

    See what a package contains before touching a server:
        python disa_stig_tool.py parse U_Cisco_IOS_Router_Y26M07_STIG.zip

    Write the report payload to disk for inspection (JSON, exact import shape):
        python disa_stig_tool.py build U_Cisco_IOS_Router_Y26M07_STIG.zip -o report.json

    Import into NCM and start compliance caching for the new report:
        python disa_stig_tool.py import U_Cisco_IOS_Router_Y26M07_STIG.zip \\
            --host orion.example.com --user admin

The password is read from the SWIS_PASSWORD environment variable, or prompted for.
Never hard-code it and never pass it on the command line.

What the import produces
------------------------

One policy report named after the package, one policy per XCCDF benchmark in the zip
(the Cisco IOS Router package, for example, carries two: NDM and RTR), one NCM rule
per XCCDF rule. Severity maps ``high``→critical, ``medium``→warning, ``low``→info.
The STIG's Fix Text is stored as the rule's remediation script for an operator to
review and run; ``ExecuteScriptAutomatically`` is always false — this tool never
creates a rule that pushes configuration on its own.

Manual STIGs describe checks in prose, not machine patterns, so by default every
imported rule uses a sentinel pattern that cannot occur in a device configuration
with "pattern must exist" set. The result: every rule reports a violation on every
node in scope, which is the honest state — each finding is an open action item
carrying the full check text and the fix script, until an engineer replaces the
sentinel with a real pattern for that rule in the NCM console. ``--mode heuristic``
instead seeds each rule with the first config-looking line found in the STIG's check
content (marking the rest for review); treat those patterns as drafts, not audits.

Endpoint facts (SWIS REST on port 17774, platform 2023.1+) and the compliance verb
contract are documented in docs/modules/ncm-compliance-reports.md of this repository
and verified against 2026.2.
"""

from __future__ import annotations

import argparse
import base64
import getpass
import io
import json
import os
import queue
import re
import ssl
import sys
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
import zipfile

DEFAULT_PORT = 17774
BASE_PATH = "/SolarWinds/InformationService/v3/Json"

# DISA's public download mirror. The listing page is public.cyber.mil/stigs/downloads/
# and every package on it resolves to this WordPress upload path.
DISA_ZIP_BASE = "https://dl.dod.cyber.mil/wp-content/uploads/stigs/zip/"

XCCDF_NS = "{http://checklists.nist.gov/xccdf/1.1}"

SEVERITY_TO_ERRORLEVEL = {"high": 2, "medium": 1, "low": 0}
ERRORLEVEL_NAMES = {2: "critical", 1: "warning", 0: "info"}

# Config lines in IOS/NX-OS/JunOS check text tend to open with one of these tokens.
# Used only by --mode heuristic to seed a draft pattern.
CONFIG_TOKENS = (
    "aaa ", "ip ", "ipv6 ", "line ", "snmp-server ", "ntp ", "logging ", "login ",
    "banner ", "crypto ", "interface ", "router ", "access-list ", "username ",
    "service ", "no ", "hostname ", "enable ", "archive", "clock ", "boot ",
)


class SwisError(RuntimeError):
    """A SWIS request failed. Carries the server's message where one was returned."""


class SwisClient:
    """Minimal SWIS REST client — the same contract scripts/python/swis_client.py shows."""

    def __init__(self, host, username, password, port=DEFAULT_PORT, verify=True, ca_file=None):
        self.base = f"https://{host}:{port}{BASE_PATH}"
        self.username = username
        self.password = password
        if verify:
            self.ctx = ssl.create_default_context(cafile=ca_file)
        else:
            # Only for a lab. Accepts any certificate.
            self.ctx = ssl.create_default_context()
            self.ctx.check_hostname = False
            self.ctx.verify_mode = ssl.CERT_NONE

    def _request(self, method, path, body=None):
        url = f"{self.base}/{path.lstrip('/')}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        token = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
        req.add_header("Authorization", f"Basic {token}")
        try:
            with urllib.request.urlopen(req, context=self.ctx, timeout=300) as resp:
                payload = resp.read().decode("utf-8", "replace")
                return json.loads(payload) if payload.strip() else None
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            try:
                detail = json.loads(detail).get("Message", detail)
            except (ValueError, AttributeError):
                pass
            raise SwisError(f"HTTP {exc.code} from {url}\n{detail}") from exc
        except urllib.error.URLError as exc:
            raise SwisError(f"could not reach {url}: {exc.reason}") from exc

    def query(self, swql, parameters=None):
        body = {"query": swql}
        if parameters:
            body["parameters"] = parameters
        return (self._request("POST", "Query", body) or {}).get("results", [])

    def invoke(self, entity, verb, *args):
        return self._request("POST", f"Invoke/{entity}/{verb}", list(args))


# ---------------------------------------------------------------------------
# SCM policy YAML (Server Configuration Monitor / PolicyEngine)
# ---------------------------------------------------------------------------
#
# SCM compliance policies are YAML documents tagged `!policy` with
# `pluginName: SCM`. The SWIS import verb takes the document text verbatim —
# Orion.PolicyEngine.Policy.ImportPolicy(yaml) returns the new PolicyID — so no
# YAML parsing is needed to import; the light regex scan below is only for
# previews and sanity checks.

def is_scm_policy_text(text):
    head = text.lstrip()[:2000]
    return head.startswith("!policy") or ("pluginName: SCM" in head and "rules:" in text)


def scan_scm_policy(text):
    """Cheap preview of an SCM policy YAML: name, rule ids, severities."""
    name = ""
    m = re.search(r"^name:\s*(.+)$", text, re.MULTILINE)
    if m:
        name = m.group(1).strip().strip("'\"")
    rules = re.findall(r"^- displayId:\s*(\S+)", text, re.MULTILINE)
    severities = re.findall(r"^\s{2}severity:\s*(\S+)", text, re.MULTILINE)
    counts = {}
    for s in severities:
        counts[s] = counts.get(s, 0) + 1
    return {"name": name, "rules": rules, "severity_counts": counts}


def load_scm_policy(path):
    """Read an SCM policy YAML file, tolerating a UTF-8/UTF-16 BOM."""
    with open(path, "rb") as fh:
        raw = fh.read()
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        text = raw.decode("utf-16")
    else:
        text = raw.decode("utf-8-sig")
    if not is_scm_policy_text(text):
        raise ValueError(f"{path}: not an SCM compliance policy "
                         "(expected a YAML document tagged !policy with pluginName: SCM)")
    return text


def import_scm_policy(swis, text):
    """Import one SCM policy via Orion.PolicyEngine.Policy.ImportPolicy.

    Returns (policy_id, name). Refuses to import when a same-name policy
    already exists — this tool never overwrites or duplicates.
    """
    info = scan_scm_policy(text)
    existing = swis.query(
        "SELECT PolicyID, BuiltIn FROM Orion.PolicyEngine.Policy WHERE Name = @n",
        {"n": info["name"]}) if info["name"] else []
    if existing:
        raise SwisError(f"a policy named \"{info['name']}\" already exists "
                        f"(PolicyID {existing[0]['PolicyID']}); refusing to duplicate")
    policy_id = swis.invoke("Orion.PolicyEngine.Policy", "ImportPolicy", text)
    return policy_id, info["name"]


# ---------------------------------------------------------------------------
# XCCDF parsing
# ---------------------------------------------------------------------------

def strip_html(text):
    """XCCDF descriptions embed pseudo-XML tags (VulnDiscussion, …) as escaped text."""
    return re.sub(r"<[^>]+>", "", text or "").strip()


def extract_tag(description, tag):
    """Pull one pseudo-tag's body out of an XCCDF <description> blob."""
    m = re.search(rf"<{tag}>(.*?)</{tag}>", description or "", re.DOTALL)
    return m.group(1).strip() if m else ""


# DISA publishes two editions. Manual STIGs are bare XCCDF 1.1 benchmarks with prose
# check text. SCAP Benchmark editions (the xml-only zips, for automated scanners) are
# SCAP 1.3 data-streams: a <data-stream-collection> root embedding an XCCDF **1.2**
# benchmark whose ids are prefixed (xccdf_mil.disa.stig_group_V-…) and whose checks
# are OVAL references instead of prose.
XCCDF_12_NS = "{http://checklists.nist.gov/xccdf/1.2}"
_SCAP_ID_PREFIX = re.compile(r"^xccdf_[^_]+(?:\.[^_]+)*_(?:group|rule|benchmark)_")


def _strip_scap_prefix(value):
    return _SCAP_ID_PREFIX.sub("", value or "")


def parse_benchmarks(xml_bytes, source_name):
    """Parse an XCCDF file (manual or SCAP data-stream) into a list of benchmark dicts."""
    root = ET.fromstring(xml_bytes)
    found = []
    for ns in (XCCDF_NS, XCCDF_12_NS):
        if root.tag == f"{ns}Benchmark":
            found.append((root, ns))
        else:
            found.extend((b, ns) for b in root.iter(f"{ns}Benchmark"))
    if not found:
        raise ValueError(f"{source_name}: no XCCDF Benchmark element found "
                         f"(root is {root.tag})")
    return [_parse_one_benchmark(b, ns, source_name) for b, ns in found]


def parse_benchmark(xml_bytes, source_name):
    """Back-compatible single-benchmark parse (first benchmark in the file)."""
    return parse_benchmarks(xml_bytes, source_name)[0]


def _parse_one_benchmark(root, ns, source_name):
    def text(elem, name):
        child = elem.find(f"{ns}{name}")
        return (child.text or "").strip() if child is not None else ""

    release = ""
    for pt in root.findall(f"{ns}plain-text"):
        if pt.get("id") == "release-info":
            release = (pt.text or "").strip()

    status = root.find(f"{ns}status")
    status_date = status.get("date", "") if status is not None else ""

    rules = []
    for group in root.iter(f"{ns}Group"):
        rule = group.find(f"{ns}Rule")
        if rule is None:
            continue
        description = rule.findtext(f"{ns}description", default="")
        check = rule.find(f"{ns}check")
        check_content, oval_ref = "", ""
        if check is not None:
            check_content = check.findtext(f"{ns}check-content", default="").strip()
            ref = check.find(f"{ns}check-content-ref")
            if ref is not None and (ref.get("name") or "").startswith("oval:"):
                oval_ref = ref.get("name")
        rules.append({
            "vuln_id": _strip_scap_prefix(group.get("id", "")),   # V-215662
            "rule_id": _strip_scap_prefix(rule.get("id", "")),    # SV-215662r…_rule
            "stig_id": text(rule, "version"),                     # CISC-ND-000010
            "severity": rule.get("severity", "medium").lower(),
            "title": text(rule, "title"),
            "discussion": extract_tag(description, "VulnDiscussion"),
            "check_content": check_content,
            "oval_ref": oval_ref,
            "fix_text": rule.findtext(f"{ns}fixtext", default="").strip(),
            "ccis": [i.text for i in rule.findall(f"{ns}ident")
                     if i.text and (i.get("system") or "").endswith("/cci")],
        })

    return {
        "source": source_name,
        "benchmark_id": _strip_scap_prefix(root.get("id", "")),
        "title": root.findtext(f"{ns}title", default="").strip(),
        "version": root.findtext(f"{ns}version", default="").strip(),
        "release": release,
        "status_date": status_date,
        "edition": "scap" if ns == XCCDF_12_NS else "manual",
        "rules": rules,
    }


def _try_parse_xml(xml_bytes, name):
    """Parse benchmarks from bytes, returning [] when the XML is not one.

    Zip discovery goes by content, not filename: DISA's naming varies
    ("*-xccdf.xml", "*Manualxccdf.xml", "*_Benchmark.xml"), and the stylesheet
    or a stray XML must simply be skipped rather than fail the whole zip.
    """
    head = xml_bytes[:200]
    if b"<?xml" not in head and b"<" not in head:
        return []
    try:
        return parse_benchmarks(xml_bytes, name)
    except (ET.ParseError, ValueError):
        return []


def _dedupe_benchmarks(benchmarks):
    """When both editions of the same benchmark are present, keep the manual one.

    Verified against real files: where both editions carry the same check, the
    fix text is identical, and only the manual edition has the check prose —
    importing both would only duplicate rules.
    """
    by_id = {}
    for b in benchmarks:
        key = b["benchmark_id"] or b["title"]
        held = by_id.get(key)
        if held is None or (held["edition"] == "scap" and b["edition"] == "manual"):
            by_id[key] = b
    return list(by_id.values())


def load_benchmarks(path):
    """Load every XCCDF benchmark from a STIG zip, a bare XML file, or a directory.

    Handles all three zip shapes DISA publishes: xsl+xml (manual), xml-only
    (SCAP data-stream), and compilation zips nesting one zip per STIG.
    """
    benchmarks = []
    if os.path.isdir(path):
        for dirpath, _dirs, files in os.walk(path):
            for name in sorted(files):
                if name.lower().endswith(".xml"):
                    with open(os.path.join(dirpath, name), "rb") as fh:
                        benchmarks.extend(_try_parse_xml(fh.read(), name))
    elif zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as zf:
            for info in sorted(zf.infolist(), key=lambda i: i.filename):
                base = os.path.basename(info.filename)
                if base.lower().endswith(".xml"):
                    benchmarks.extend(_try_parse_xml(zf.read(info), base))
                elif base.lower().endswith(".zip"):
                    # Compilation zips (SRG-STIG Library) nest one zip per STIG.
                    inner = io.BytesIO(zf.read(info))
                    with zipfile.ZipFile(inner) as izf:
                        for iinfo in sorted(izf.infolist(), key=lambda i: i.filename):
                            ibase = os.path.basename(iinfo.filename)
                            if ibase.lower().endswith(".xml"):
                                benchmarks.extend(_try_parse_xml(izf.read(iinfo), ibase))
    elif path.lower().endswith(".xml"):
        with open(path, "rb") as fh:
            benchmarks.extend(parse_benchmarks(fh.read(), os.path.basename(path)))
    elif path.lower().endswith(".xsl"):
        # The .xsl is only the display stylesheet; the data lives in the
        # benchmark XML sitting next to it. Resolve that silently.
        folder = os.path.dirname(os.path.abspath(path))
        for n in sorted(os.listdir(folder)):
            if n.lower().endswith(".xml"):
                with open(os.path.join(folder, n), "rb") as fh:
                    benchmarks.extend(_try_parse_xml(fh.read(), n))
        if not benchmarks:
            raise ValueError(f"{path}: this is the STIG stylesheet, not the data, and no "
                             "XCCDF benchmark XML was found next to it")
    else:
        raise ValueError(f"{path}: not a zip, directory, or XCCDF .xml file")
    benchmarks = _dedupe_benchmarks(benchmarks)
    if not benchmarks:
        raise ValueError(f"{path}: no XCCDF benchmark found inside")
    return benchmarks


# ---------------------------------------------------------------------------
# NCM payload building
# ---------------------------------------------------------------------------

def heuristic_pattern(check_content):
    """First line of check text that looks like a device configuration command."""
    for line in (check_content or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.endswith((":", "?", ".")):
            continue
        lowered = stripped.lower()
        if any(lowered.startswith(tok) for tok in CONFIG_TOKENS):
            return stripped
    return None


def rule_object(rule, grouping, mode):
    """One XCCDF rule → one Cirrus.PolicyReports rule contract object.

    Field names follow the SolarWinds.NCM.Contracts.Compliance.PolicyRule contract
    (docs/modules/ncm-compliance-reports.md), not the SWQL column names.
    """
    sentinel = f"STIG-MANUAL-REVIEW-{rule['vuln_id']}"
    pattern, note = sentinel, (
        "PATTERN NOT SET: this sentinel never matches, so the rule flags every node "
        "as a violation until you replace it with a real pattern for this check."
    )
    if mode == "heuristic":
        found = heuristic_pattern(rule["check_content"])
        if found:
            pattern, note = found, (
                "DRAFT PATTERN extracted automatically from the STIG check text — "
                "verify it before trusting this rule's results."
            )

    comments = "\n\n".join(part for part in (
        f"{rule['vuln_id']} / {rule['rule_id']} / STIG ID {rule['stig_id']}"
        + (f" / {', '.join(rule['ccis'])}" if rule["ccis"] else ""),
        note,
        "Discussion:\n" + rule["discussion"] if rule["discussion"] else "",
        "Check:\n" + rule["check_content"] if rule["check_content"] else "",
        ("Machine check (SCAP edition): OVAL definition " + rule["oval_ref"]
         + " — no manual check text in this edition; the manual STIG for this "
           "product carries the prose.") if rule.get("oval_ref") and not rule["check_content"] else "",
    ) if part)

    name = f"{rule['vuln_id']} [{rule['severity']}] {rule['title']}"
    return {
        "RuleId": str(uuid.uuid5(uuid.NAMESPACE_URL, "stig2ncm:" + rule["rule_id"])),  # historic namespace string; changing it would change every derived RuleId
        "RuleName": name[:250],
        "Comments": comments,
        "Grouping": grouping,
        "SimplePatternText": pattern,
        "PatternType": "Like",
        "PatternMustExist": True,
        "AdvancedMode": False,
        "MultiLineRulePatterns": [],
        "ConfigBlockStart": "",
        "ConfigBlockEnd": "",
        "ConfigBlockPatternType": "Like",
        "ConfigBlockMustExist": False,
        "IsConfigBlockPatternRegEx": False,
        "ErrorLevel": SEVERITY_TO_ERRORLEVEL.get(rule["severity"], 1),
        # Fix Text as an operator-run script. Never auto-executed: an imported
        # checklist must not be allowed to push configuration on its own.
        "RemediateScript": rule["fix_text"],
        "RemediateScriptType": "CLI",
        "ExecuteScriptAutomatically": False,
        "ExecuteRemediationScriptPerBlock": False,
        "ExecuteScriptInConfigMode": False,
        "Owner": "DISA STIG Conversion Tool",
    }


def build_report(benchmarks, name=None, grouping="DISA STIG", node_where="(Nodes.Vendor = 'Cisco')",
                 config_type="Any", mode="manual", source_path=None):
    """Assemble the full PolicyReport contract object for the NCM import.

    Report = the STIG package (named after the zip when the source is one),
    Policy = the device scope (one per benchmark, filtered by node_where),
    Rule   = one per XCCDF check.
    """
    policies = []
    for b in benchmarks:
        policy_group = f"{grouping}/{b['benchmark_id']}" if b["benchmark_id"] else grouping
        rules = [rule_object(r, policy_group, mode) for r in b["rules"]]
        policies.append({
            "PolicyId": str(uuid.uuid5(uuid.NAMESPACE_URL,
                                       "stig2ncm-policy:" + (b["benchmark_id"] or b["title"]))),
            "PolicyName": f"{b['title']} V{b['version']} ({b['release']})"[:250],
            "Comments": f"Imported by the DISA STIG Conversion Tool from {b['source']} (benchmark {b['benchmark_id']}, "
                        f"status date {b['status_date']}).",
            "Grouping": grouping,
            # The literal "Criteria:" prefix plus the Where clause is what filters
            # nodes; the console's node-picker QUERY blob is optional state.
            "NodeSelectionString": f"Criteria: Where ( {node_where} )",
            "ConfigTypes": config_type,
            "AssignedPolicyRules": rules,
            "AssignedRulesList": [r["RuleId"] for r in rules],
        })

    if name is None and source_path and source_path.lower().endswith(".zip"):
        # The report carries the package's name: U_Cisco_IOS_Router_Y26M07_STIG
        name = os.path.splitext(os.path.basename(source_path))[0]
    if name is None:
        name = benchmarks[0]["title"]
        if len(benchmarks) > 1:
            name = re.sub(r"\b(NDM|RTR|Switch|Router)\b.*$", "", name).strip() or name
            name += " (all benchmarks)"
    return {
        "ID": str(uuid.uuid4()),  # advisory only — the server assigns its own GUID
        "Name": name[:250],
        "Comments": "DISA STIG imported by the DISA STIG Conversion Tool. Sources: "
                    + "; ".join(f"{b['source']} ({b['release']})" for b in benchmarks),
        "Group": grouping,
        "ShowSummaryFlag": True,
        "ShowRulesWithoutViolationFlag": True,
        "AssignedPolicies": policies,
        "AssignedPoliciesList": [p["PolicyId"] for p in policies],
        "ReportStatus": "Enabled",
    }


# ---------------------------------------------------------------------------
# Console XML wire format for the NCM contract objects
# ---------------------------------------------------------------------------
#
# The SolarWinds.NCM.Contracts.Compliance.* types are XML-serialized on the
# wire. Some servers map a JSON object onto them; others hand the argument to
# an XML reader and fail with HTTP 400 "Value cannot be null. Parameter name:
# input" (observed on 2026.2.2). For those, the argument must be the contract
# XML as a string — the same shape as a console export file, and element order
# matters because .NET XML deserializers on the receiving side are
# order-sensitive. Order below is copied from real console exports (and from
# apps/porter's export writer in this repository).

def _b_str(value):
    return "true" if value else "false"


def _sub(parent, name, text):
    el = ET.SubElement(parent, name)
    el.text = text if text else None
    return el


def _rule_xml_into(parent, rule):
    r = ET.SubElement(parent, "PolicyRule")
    pats = ET.SubElement(r, "MultiLineRulePatterns")
    for p in rule.get("MultiLineRulePatterns") or []:
        m = ET.SubElement(pats, "MultiLineRulePattern")
        _sub(m, "EndBracket", p.get("EndBracket") or "")
        _sub(m, "PatternType", str(p.get("PatternType") or "Like"))
        _sub(m, "Condition", p.get("Condition") or "")
        _sub(m, "Pattern", p.get("Pattern") or "")
        _sub(m, "Criteria", _b_str(p.get("Criteria")))
        _sub(m, "BeginBracket", p.get("BeginBracket") or "")
    _sub(r, "RuleId", rule.get("RuleId") or "")
    _sub(r, "RuleName", rule.get("RuleName") or "")
    _sub(r, "Comments", rule.get("Comments") or "")
    _sub(r, "Grouping", rule.get("Grouping") or "")
    _sub(r, "RemediateScript", rule.get("RemediateScript") or "")
    _sub(r, "ConfigBlockStart", rule.get("ConfigBlockStart") or "")
    _sub(r, "ConfigBlockEnd", rule.get("ConfigBlockEnd") or "")
    _sub(r, "ConfigBlockPatternType", str(rule.get("ConfigBlockPatternType") or "Like"))
    _sub(r, "ConfigBlockMustExist", _b_str(rule.get("ConfigBlockMustExist")))
    _sub(r, "PatternType", str(rule.get("PatternType") or "Like"))
    _sub(r, "PatternMustExist", _b_str(rule.get("PatternMustExist")))
    _sub(r, "AdvancedMode", _b_str(rule.get("AdvancedMode")))
    _sub(r, "ErrorLevel", str(int(rule.get("ErrorLevel") or 0)))
    _sub(r, "SimplePatternText", rule.get("SimplePatternText") or "")
    _sub(r, "ExecuteScriptAutomatically", _b_str(rule.get("ExecuteScriptAutomatically")))
    _sub(r, "Owner", rule.get("Owner") or "")
    _sub(r, "RemediateScriptType", str(rule.get("RemediateScriptType") or "CLI"))
    _sub(r, "ExecuteRemediationScriptPerBlock",
         _b_str(rule.get("ExecuteRemediationScriptPerBlock")))
    _sub(r, "ExecuteScriptInConfigMode", _b_str(rule.get("ExecuteScriptInConfigMode")))
    return r


def report_contract_xml(report):
    """The full nested report as console-export XML — the AddPolicyReport argument."""
    root = ET.Element("PolicyReport", {
        "xmlns:xsd": "http://www.w3.org/2001/XMLSchema",
        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
    })
    _sub(root, "ID", report.get("ID") or "")
    _sub(root, "Name", report.get("Name") or "")
    _sub(root, "Comments", report.get("Comments") or "")
    _sub(root, "Group", report.get("Group") or "")
    _sub(root, "ShowSummaryFlag", _b_str(report.get("ShowSummaryFlag")))
    _sub(root, "ShowRulesWithoutViolationFlag",
         _b_str(report.get("ShowRulesWithoutViolationFlag")))
    pols = ET.SubElement(root, "AssignedPolicies")
    for p in report.get("AssignedPolicies") or []:
        pe = ET.SubElement(pols, "Policy")
        _sub(pe, "NodeSelectionString", p.get("NodeSelectionString") or "")
        _sub(pe, "ConfigTypes", str(p.get("ConfigTypes") or "Any"))
        rules_el = ET.SubElement(pe, "AssignedPolicyRules")
        for r in p.get("AssignedPolicyRules") or []:
            _rule_xml_into(rules_el, r)
        _sub(pe, "Grouping", p.get("Grouping") or "")
        _sub(pe, "Comments", p.get("Comments") or "")
        _sub(pe, "PolicyName", p.get("PolicyName") or "")
    _sub(root, "ReportStatus", str(report.get("ReportStatus") or "Enabled"))
    return ET.tostring(root, encoding="unicode")


def _clean_id(value, fallback):
    """Verb results come back as JSON strings that may carry quotes or braces."""
    if isinstance(value, str):
        cleaned = value.strip().strip('"').strip("{}").strip()
        if cleaned:
            return cleaned
    return fallback


def _verify_report(swis, report_id, expected_policies, expected_rules, log):
    """Read the report back — the import is only done if the tree actually exists."""
    stored = swis.invoke("Cirrus.PolicyReports", "GetPolicyReport", report_id, True) or {}
    stored_policies = stored.get("AssignedPolicies") or []
    stored_rules = sum(len(p.get("AssignedPolicyRules") or []) for p in stored_policies)
    if not stored_policies or stored_rules == 0:
        raise SwisError(
            f"verification failed: report {report_id} was created but holds "
            f"{len(stored_policies)} policies and {stored_rules} rules "
            f"(expected {expected_policies} and {expected_rules}). Check the account's NCM "
            "role (WebUploader or higher) and the server's compliance settings.")
    log(f"verified: report holds {len(stored_policies)} policies and {stored_rules} rules")
    return report_id, len(stored_policies), stored_rules


def import_ncm_report(swis, report, log=print):
    """Import the report, adapting to how the server accepts the contract objects.

    First try creating the tiers bottom-up as JSON objects (AddPolicyRule →
    AddPolicy → AddPolicyReport linked by ID lists). Some servers' JSON endpoint
    hands the NCM contract types to an XML deserializer instead and rejects the
    very first call with HTTP 400 "Value cannot be null. Parameter name: input"
    (observed on 2026.2.2) — for those, fall back to one nested
    AddPolicyReport(xmlString, importFlag=true) in the console-export XML wire
    format, which is exactly what the console's own import sends.

    Either way the result is verified by reading the report back before caching.
    Returns (report_id, policy_count, rule_count) as confirmed by the read-back.
    """
    n_policies = len(report["AssignedPolicies"])
    n_rules = sum(len(p["AssignedPolicyRules"]) for p in report["AssignedPolicies"])
    try:
        return _import_ncm_bottom_up(swis, report, log)
    except SwisError as exc:
        if "HTTP 400" not in str(exc):
            raise
        log(f"the server rejected the JSON contract object ({str(exc).splitlines()[-1]});")
        log("retrying with the console XML wire format (one nested AddPolicyReport call) …")
        xml_arg = report_contract_xml(report)
        report_id = _clean_id(
            swis.invoke("Cirrus.PolicyReports", "AddPolicyReport", xml_arg, True), "")
        if not report_id:
            raise SwisError("AddPolicyReport (XML wire format) did not return "
                            "the new report id")
        return _verify_report(swis, report_id, n_policies, n_rules, log)


def _import_ncm_bottom_up(swis, report, log):
    policy_ids = []
    total_rules = 0
    for policy in report["AssignedPolicies"]:
        rules = policy["AssignedPolicyRules"]
        log(f"creating {len(rules)} rules for policy \"{policy['PolicyName']}\" …")
        rule_ids = []
        for i, rule in enumerate(rules, 1):
            result = swis.invoke("Cirrus.PolicyReports", "AddPolicyRule", rule)
            rule_ids.append(_clean_id(result, rule["RuleId"]))
            if i % 25 == 0:
                log(f"  {i}/{len(rules)} rules created")
        total_rules += len(rule_ids)

        linked = dict(policy, AssignedPolicyRules=[], AssignedRulesList=rule_ids)
        result = swis.invoke("Cirrus.PolicyReports", "AddPolicy", linked, False)
        policy_ids.append(_clean_id(result, policy["PolicyId"]))
        log(f"created policy \"{policy['PolicyName']}\" with {len(rule_ids)} rules")

    linked_report = dict(report, AssignedPolicies=[], AssignedPoliciesList=policy_ids)
    report_id = _clean_id(
        swis.invoke("Cirrus.PolicyReports", "AddPolicyReport", linked_report, False), "")
    if not report_id:
        raise SwisError("AddPolicyReport did not return the new report id")

    return _verify_report(swis, report_id, len(policy_ids), total_rules, log)


# ---------------------------------------------------------------------------
# Target detection: which compliance module should this STIG land in?
# ---------------------------------------------------------------------------
#
# The zip/file name and the benchmark title carry the product. Network-vendor
# keywords route to NCM and also set the policy's node scope; OS keywords route
# to Server Configuration Monitor.

# keyword (matched case-insensitively) -> the Vendor value NCM nodes report
NETWORK_VENDORS = {
    "cisco": "Cisco", "ios ": "Cisco", "ios_": "Cisco", "nx-os": "Cisco",
    "nx_os": "Cisco", "asa": "Cisco", "juniper": "Juniper", "junos": "Juniper",
    "arista": "Arista", "palo alto": "Palo Alto", "palo_alto": "Palo Alto",
    "paloalto": "Palo Alto", "f5 ": "F5", "f5_": "F5", "big-ip": "F5",
    "bigip": "F5", "fortinet": "Fortinet", "fortigate": "Fortinet",
    "brocade": "Brocade", "check point": "Check Point", "checkpoint": "Check Point",
    "arubaos": "Aruba", "aruba": "Aruba", "extreme": "Extreme", "huawei": "Huawei",
    "dell os10": "Dell", "router": None, "switch": None, "firewall": None,
    "network device": None,
}

# keyword -> (display OS name, SWQL filter against Orion.Nodes for assignment)
SERVER_OSES = {
    "red hat": ("Red Hat Enterprise Linux", "MachineType LIKE '%Red Hat%'"),
    "rhel": ("Red Hat Enterprise Linux", "MachineType LIKE '%Red Hat%'"),
    "ubuntu": ("Ubuntu", "MachineType LIKE '%Ubuntu%'"),
    "debian": ("Debian", "MachineType LIKE '%Debian%'"),
    "centos": ("CentOS", "MachineType LIKE '%CentOS%'"),
    "linux": ("Linux", "MachineType LIKE '%Linux%'"),
    "windows": ("Windows", "MachineType LIKE '%Windows%'"),
    "sql server": ("Windows", "MachineType LIKE '%Windows%'"),
    "iis": ("Windows", "MachineType LIKE '%Windows%'"),
    "exchange": ("Windows", "MachineType LIKE '%Windows%'"),
}


def detect_target(benchmarks, source_name):
    """Return ('network', vendor_or_None) or ('server', (os, swql)) or (None, None).

    Vendor keywords win over OS keywords only when they appear and no OS does;
    a Windows/Linux match routes to SCM even if generic words like 'router'
    also appear somewhere.
    """
    text = " ".join([source_name or ""] + [b["title"] + " " + b["source"]
                                           for b in benchmarks]).lower()
    for kw, os_info in SERVER_OSES.items():
        if kw in text:
            return "server", os_info
    vendor = None
    matched = False
    for kw, v in NETWORK_VENDORS.items():
        if kw in text:
            matched = True
            if v:
                vendor = v
                break
    if matched:
        return "network", vendor
    return None, None


def node_where_for(vendor):
    return f"(Nodes.Vendor LIKE '%{vendor}%')" if vendor else "(Nodes.Vendor = 'Cisco')"


# ---------------------------------------------------------------------------
# Server Compliance: XCCDF -> SCM policy YAML
# ---------------------------------------------------------------------------
#
# SCM's policy engine imports the !policy YAML format (see the shipped IIS 8.5
# policy and docs/modules/scm-compliance-policies.md). A manual STIG has no
# machine checks, so each generated rule carries an attestation sentinel: a
# harmless Write-Host probe whose output never matches, keeping the rule
# failing — an open action item with the STIG's check and fix text attached —
# until an operator reviews it. JSON string quoting is valid YAML, which keeps
# the emitter dependency-free.

def _yq(value):
    """Quote a scalar for YAML via JSON (JSON strings are valid YAML)."""
    return json.dumps(value or "", ensure_ascii=False)


def xccdf_to_scm_yaml(benchmark):
    """Convert one XCCDF benchmark into an importable SCM compliance policy."""
    name = f"{benchmark['title']} V{benchmark['version']} ({benchmark['release']})"[:250]
    policy_uid = uuid.uuid5(uuid.NAMESPACE_URL, "stig2ncm-scm:" + (benchmark["benchmark_id"]
                                                                   or benchmark["title"]))
    lines = [
        "!policy",
        f"name: {_yq(name)}",
        f"uniqueId: {policy_uid}",
        "pluginName: SCM",
        f"description: {_yq('DISA STIG imported by the DISA STIG Conversion Tool from ' + benchmark['source'] + '. Every rule is a manual-review attestation: it reports failed, with the STIG check and fix text attached, until an engineer verifies the setting and replaces or disables the rule. Nothing in this policy changes server configuration.')}",
        "version: 2",
        "builtIn: false",
        "rules:",
    ]
    for r in benchmark["rules"]:
        rule_uid = uuid.uuid5(uuid.NAMESPACE_URL, "stig2ncm-scm-rule:" + r["rule_id"])
        check = r["check_content"] or (
            f"Machine check (SCAP edition): OVAL definition {r['oval_ref']}. "
            "The manual STIG for this product carries the prose check text."
            if r.get("oval_ref") else "")
        probe = f"Write-Host \"{r['vuln_id']} reviewed: False\""
        lines += [
            f"- displayId: {_yq(r['vuln_id'])}",
            f"  uniqueId: {rule_uid}",
            f"  name: {_yq(r['title'][:250])}",
            f"  severity: {r['severity'].capitalize()}",
            f"  description: {_yq(r['discussion'])}",
            f"  remediationDescription: {_yq(r['fix_text'])}",
            f"  checkText: {_yq(check)}",
            "  condition: !matches",
            f"    expression: {_yq(r['vuln_id'] + ' reviewed: True')}",
            "    source: !scm.powershell",
            f"      description: {_yq('STIG ' + r['stig_id'] + ' manual-review attestation')}",
            f"      script: {_yq(probe)}",
        ]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_download(args):
    name = args.package
    if name.startswith("http://") or name.startswith("https://"):
        url = name
    else:
        if not name.lower().endswith(".zip"):
            name += ".zip"
        url = DISA_ZIP_BASE + name
    dest = os.path.join(args.dir, os.path.basename(urllib.parse.urlsplit(url).path))
    print(f"downloading {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "disa-stig-conversion-tool/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=300) as resp, open(dest, "wb") as out:
            while chunk := resp.read(1 << 16):
                out.write(chunk)
    except urllib.error.HTTPError as exc:
        sys.exit(f"error: HTTP {exc.code} for {url}\n"
                 "Check the exact package name on https://public.cyber.mil/stigs/downloads/ "
                 "(names are case-sensitive), or pass the full URL.")
    print(f"saved {dest} ({os.path.getsize(dest):,} bytes)")
    if not zipfile.is_zipfile(dest):
        sys.exit(f"error: {dest} is not a zip — the mirror may have returned an error page")
    for b in load_benchmarks(dest):
        print(f"  contains: {b['title']} — {len(b['rules'])} rules")


def is_scm_path(path):
    return os.path.isfile(path) and path.lower().endswith((".yaml", ".yml"))


def cmd_parse(args):
    if is_scm_path(args.path):
        info = scan_scm_policy(load_scm_policy(args.path))
        sev = ", ".join(f"{v} {k}" for k, v in sorted(info["severity_counts"].items()))
        print(f"{info['name']}  (SCM compliance policy)")
        print(f"  {len(info['rules'])} rules: {sev}")
        if args.rules:
            for r in info["rules"]:
                print(f"    {r}")
        return
    benchmarks = load_benchmarks(args.path)
    print(resolve_route("auto", benchmarks, os.path.basename(args.path))[2])
    for b in benchmarks:
        counts = {}
        for r in b["rules"]:
            counts[r["severity"]] = counts.get(r["severity"], 0) + 1
        sev = ", ".join(f"{counts[s]} {s}" for s in ("high", "medium", "low") if s in counts)
        print(f"{b['title']}  [{b['edition']} edition]")
        print(f"  benchmark {b['benchmark_id']}  V{b['version']}  {b['release']}  "
              f"(from {b['source']})")
        print(f"  {len(b['rules'])} rules: {sev}")
        if args.rules:
            for r in b["rules"]:
                print(f"    {r['vuln_id']:<10} {r['stig_id']:<18} [{r['severity']:<6}] {r['title']}")
        print()


def resolve_route(target, benchmarks, source_name, node_where=None):
    """Decide the destination module for parsed XCCDF benchmarks.

    target: 'auto' | 'network' | 'server' (the dropdown / --target choice).
    Returns ('network', where_clause, note) or ('server', (os_name, swql), note).
    """
    detected, info = detect_target(benchmarks, source_name)
    explicit_where = node_where and not node_where.lower().startswith("auto") \
        and not node_where.startswith("(auto")
    if target == "server" or (target == "auto" and detected == "server"):
        os_info = info if detected == "server" else ("(OS not recognized)",
                                                     "MachineType LIKE '%'")
        why = "detected from the file/benchmark name" if detected == "server" \
            else "forced by the Server Compliance selection"
        return "server", os_info, (f"target: Server Configuration Monitor — "
                                   f"{os_info[0]} ({why})")
    vendor = info if detected == "network" else None
    where = node_where if explicit_where else node_where_for(vendor)
    if target == "network" and detected == "server":
        note = ("target: NCM (forced by the Network Compliance selection — the file "
                "looks like a server STIG)")
    elif vendor:
        note = f"target: NCM — vendor {vendor} detected, node scope {where}"
    elif detected == "network":
        note = f"target: NCM — network device detected, node scope {where}"
    else:
        note = (f"target: NCM by default — nothing recognized in the name; "
                f"node scope {where} (override with the Server Compliance option "
                "or --target server if this is a server STIG)")
    return "network", where, note


def make_report_from_args(args, benchmarks, node_where):
    return build_report(
        benchmarks, name=args.name, grouping=args.grouping,
        node_where=node_where, config_type=args.config_type, mode=args.mode,
        source_path=args.path,
    )


def cmd_build(args):
    if is_scm_path(args.path):
        info = scan_scm_policy(load_scm_policy(args.path))
        print(f"\"{info['name']}\" is an SCM compliance policy: the YAML file itself is "
              "the import payload — nothing to build.\n"
              "Import it with:  disa_stig_tool.py import <file> …  "
              "(or POST [yamlText] to Invoke/Orion.PolicyEngine.Policy/ImportPolicy)")
        return
    benchmarks = load_benchmarks(args.path)
    kind, info, note = resolve_route(args.target, benchmarks,
                                     os.path.basename(args.path), args.node_where)
    print(note)
    stem = os.path.splitext(os.path.basename(args.path))[0]
    if kind == "server":
        for b in benchmarks:
            out = args.output if args.output and len(benchmarks) == 1 else \
                f"{stem}.{b['benchmark_id'] or 'benchmark'}.scm-policy.yaml"
            with open(out, "w", encoding="utf-8") as fh:
                fh.write(xccdf_to_scm_yaml(b))
            print(f"wrote {out}: SCM policy \"{b['title']}\" — {len(b['rules'])} rules")
        print("import with:  disa_stig_tool.py import <same source> --target server …")
        return
    report = make_report_from_args(args, benchmarks, info)
    out = args.output or (stem + ".ncm-report.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    n_rules = sum(len(p["AssignedPolicyRules"]) for p in report["AssignedPolicies"])
    print(f"wrote {out}: report \"{report['Name']}\" — "
          f"{len(report['AssignedPolicies'])} policies, {n_rules} rules")
    print("import it with:  disa_stig_tool.py import <same source> …  "
          "(or POST [report, true] to Invoke/Cirrus.PolicyReports/AddPolicyReport)")


def import_scm_benchmarks(swis, benchmarks, os_info, log=print):
    """Convert each benchmark to an SCM policy and import it via ImportPolicy."""
    os_name, swql = os_info
    for b in benchmarks:
        yaml_text = xccdf_to_scm_yaml(b)
        policy_id, name = import_scm_policy(swis, yaml_text)
        log(f"imported SCM policy \"{name}\" (PolicyID {policy_id}) — "
            f"{len(b['rules'])} manual-review rules")
    log(f"Assign to your {os_name} nodes under Settings → SCM Settings → Policies "
        "(or Orion.PolicyEngine.Policy.AssignToEntity). Find them with:")
    log(f"  SELECT NodeID, Caption, MachineType FROM Orion.Nodes WHERE {swql}")


def cmd_import(args):
    password = os.environ.get("SWIS_PASSWORD") or getpass.getpass(f"password for {args.user}: ")
    swis = SwisClient(args.host, args.user, password, port=args.port,
                      verify=not args.insecure, ca_file=args.ca_file)

    if is_scm_path(args.path):
        text = load_scm_policy(args.path)
        policy_id, name = import_scm_policy(swis, text)
        print(f"imported SCM policy \"{name}\" (PolicyID {policy_id}).")
        print("Assign it to nodes under Settings → SCM Settings → Policies, or via "
              "Orion.PolicyEngine.Policy.AssignToEntity.")
        return

    benchmarks = load_benchmarks(args.path)
    kind, info, note = resolve_route(args.target, benchmarks,
                                     os.path.basename(args.path), args.node_where)
    print(note)
    if kind == "server":
        import_scm_benchmarks(swis, benchmarks, info)
        return

    report = make_report_from_args(args, benchmarks, info)
    existing = swis.query("SELECT PolicyReportID FROM Cirrus.PolicyReports WHERE Name = @n",
                          {"n": report["Name"]})
    if existing:
        sys.exit(f"error: a report named \"{report['Name']}\" already exists "
                 f"({existing[0]['PolicyReportID']}). Rename with --name, or delete it first — "
                 "this tool never overwrites.")

    n_rules = sum(len(p["AssignedPolicyRules"]) for p in report["AssignedPolicies"])
    print(f"importing \"{report['Name']}\" — {len(report['AssignedPolicies'])} policies, "
          f"{n_rules} rules …")
    new_id, n_pol, n_rul = import_ncm_report(swis, report)
    print(f"imported: \"{report['Name']}\" ({new_id}) — {n_pol} policies, {n_rul} rules")

    if args.no_cache:
        print("compliance caching not started (--no-cache); the report shows no data until "
              "you run Update Violations in the console or invoke StartCaching.")
        return
    # Always pass the specific GUID: an empty array would re-cache every report.
    swis.invoke("Cirrus.PolicyReports", "StartCaching", [new_id])
    print("compliance caching started for this report. Watch it under "
          "My Dashboards → Network Configuration → Compliance.")


def add_source_args(p):
    p.add_argument("path", help="STIG zip, extracted directory, or a single *-xccdf.xml file")
    p.add_argument("--name", help="report name (default: derived from the benchmark title)")
    p.add_argument("--grouping", default="DISA STIG", help="folder for report/policies/rules")
    p.add_argument("--target", choices=("auto", "network", "server"), default="auto",
                   help="auto: route by the file/benchmark name (network vendors → NCM, "
                        "Windows/Linux/RHEL/Debian/Ubuntu/CentOS → SCM). "
                        "network: NCM compliance only. server: SCM compliance only.")
    p.add_argument("--node-where", default="auto",
                   help="NCM node-selection Where clause, e.g. \"(Nodes.Vendor = 'Cisco')\". "
                        "Default auto: derived from the detected vendor.")
    p.add_argument("--config-type", default="Any",
                   help="config type the rules scan: Any, Running, Startup, …")
    p.add_argument("--mode", choices=("manual", "heuristic"), default="manual",
                   help="manual: sentinel patterns, every rule flags for review (default). "
                        "heuristic: seed draft patterns from the STIG check text.")




# ---------------------------------------------------------------------------
# The GUI
# ---------------------------------------------------------------------------
# tkinter ships with python.org and Windows-store Python; some minimal Linux
# installs lack it. The CLI must keep working there, so the import is guarded.

try:
    import tkinter as tk
    from tkinter import filedialog, ttk
    HAVE_TK = True
except ImportError:
    HAVE_TK = False

try:  # optional: drag-and-drop
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAVE_DND = True
except ImportError:
    HAVE_DND = False


class WindowsAuthClient:
    """SWIS client that authenticates as the current Windows user (SSPI/Negotiate).

    Same query/invoke surface as SwisClient, carried by `requests` because
    the standard library cannot produce a Negotiate token.
    """

    def __init__(self, host, port, verify):
        try:
            import requests
            from requests_negotiate_sspi import HttpNegotiateAuth
        except ImportError as exc:
            raise SwisError(
                "Windows-user login needs the requests and requests-negotiate-sspi "
                "packages (Windows only):\n    pip install requests requests-negotiate-sspi"
            ) from exc
        self.base = f"https://{host}:{port}{BASE_PATH}"
        self.session = requests.Session()
        self.session.auth = HttpNegotiateAuth()
        self.session.verify = verify
        if not verify:
            import urllib3
            urllib3.disable_warnings()

    def _request(self, path, body):
        resp = self.session.post(f"{self.base}/{path}", json=body, timeout=300)
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("Message", resp.text)
            except ValueError:
                detail = resp.text
            raise SwisError(f"HTTP {resp.status_code} from {path}\n{detail}")
        return resp.json() if resp.text.strip() else None

    def query(self, swql, parameters=None):
        body = {"query": swql}
        if parameters:
            body["parameters"] = parameters
        return (self._request("Query", body) or {}).get("results", [])

    def invoke(self, entity, verb, *args):
        return self._request(f"Invoke/{entity}/{verb}", list(args))


class App:
    def __init__(self, root):
        self.root = root
        root.title("DISA STIG Conversion Tool")
        root.minsize(680, 560)
        self.log_queue = queue.Queue()
        self._downloaded = None  # temp file path when the source is a URL

        pad = {"padx": 8, "pady": 4}
        frame = ttk.Frame(root, padding=10)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)

        # --- connection -----------------------------------------------------
        conn = ttk.LabelFrame(frame, text="SolarWinds server", padding=8)
        conn.grid(row=0, column=0, columnspan=2, sticky="ew", **pad)
        conn.columnconfigure(1, weight=1)

        ttk.Label(conn, text="Server IP/FQDN").grid(row=0, column=0, sticky="w", **pad)
        self.host = tk.StringVar()
        ttk.Entry(conn, textvariable=self.host).grid(row=0, column=1, sticky="ew", **pad)
        ttk.Label(conn, text="SWIS port").grid(row=0, column=2, sticky="e", **pad)
        self.port = tk.StringVar(value=str(DEFAULT_PORT))
        ttk.Entry(conn, textvariable=self.port, width=7).grid(row=0, column=3, **pad)

        ttk.Label(conn, text="Username").grid(row=1, column=0, sticky="w", **pad)
        self.user = tk.StringVar()
        self.user_entry = ttk.Entry(conn, textvariable=self.user)
        self.user_entry.grid(row=1, column=1, columnspan=3, sticky="ew", **pad)

        ttk.Label(conn, text="Password").grid(row=2, column=0, sticky="w", **pad)
        self.password = tk.StringVar()
        self.pass_entry = ttk.Entry(conn, textvariable=self.password, show="•")
        self.pass_entry.grid(row=2, column=1, columnspan=3, sticky="ew", **pad)

        self.win_auth = tk.BooleanVar(value=False)
        ttk.Checkbutton(conn, text="Login with current Windows user",
                        variable=self.win_auth, command=self._toggle_auth).grid(
            row=3, column=0, columnspan=2, sticky="w", **pad)
        self.verify_tls = tk.BooleanVar(value=False)
        ttk.Checkbutton(conn, text="Verify TLS certificate",
                        variable=self.verify_tls).grid(row=3, column=2, columnspan=2,
                                                       sticky="e", **pad)

        # --- source ----------------------------------------------------------
        src = ttk.LabelFrame(frame, text="STIG source", padding=8)
        src.grid(row=1, column=0, columnspan=2, sticky="ew", **pad)
        src.columnconfigure(1, weight=1)

        self.source_kind = tk.StringVar(value="file")
        ttk.Radiobutton(src, text="File (zip, xccdf .xml, .xsl, SCM .yaml)",
                        variable=self.source_kind, value="file",
                        command=self._toggle_source).grid(row=0, column=0, columnspan=2,
                                                          sticky="w", **pad)
        self.file_path = tk.StringVar()
        self.file_entry = ttk.Entry(src, textvariable=self.file_path)
        self.file_entry.grid(row=1, column=1, sticky="ew", **pad)
        self.browse_btn = ttk.Button(src, text="Browse…", command=self._browse)
        self.browse_btn.grid(row=1, column=2, **pad)
        drop_hint = "or drop a file anywhere on this window" if HAVE_DND else \
            "(install tkinterdnd2 to enable drag-and-drop)"
        ttk.Label(src, text=drop_hint, foreground="gray").grid(
            row=2, column=1, sticky="w", padx=8)

        ttk.Radiobutton(src, text="STIG package URL (e.g. a dl.dod.cyber.mil zip link)",
                        variable=self.source_kind, value="url",
                        command=self._toggle_source).grid(row=3, column=0, columnspan=2,
                                                          sticky="w", **pad)
        self.url = tk.StringVar()
        self.url_entry = ttk.Entry(src, textvariable=self.url)
        self.url_entry.grid(row=4, column=1, columnspan=2, sticky="ew", **pad)

        # --- import options ---------------------------------------------------
        opts = ttk.LabelFrame(frame, text="Import options", padding=8)
        opts.grid(row=2, column=0, columnspan=2, sticky="ew", **pad)
        opts.columnconfigure(1, weight=1)

        ttk.Label(opts, text="Compliance target").grid(row=0, column=0, sticky="w", **pad)
        self.target = tk.StringVar()
        target_box = ttk.Combobox(
            opts, textvariable=self.target, state="readonly", width=52,
            values=("Auto Compliance Assignment — route by file name / device type",
                    "Network Compliance — network devices only (NCM)",
                    "Server Compliance — server systems (SCM)"))
        target_box.current(0)
        target_box.grid(row=0, column=1, sticky="w", **pad)

        ttk.Label(opts, text="NCM node scope (Where clause)").grid(row=1, column=0,
                                                                   sticky="w", **pad)
        self.node_where = tk.StringVar(value="(auto — from the detected vendor)")
        ttk.Entry(opts, textvariable=self.node_where).grid(row=1, column=1,
                                                           sticky="ew", **pad)
        ttk.Label(opts, text="NCM rule patterns").grid(row=2, column=0, sticky="w", **pad)
        self.mode = tk.StringVar(value="manual")
        box = ttk.Combobox(opts, textvariable=self.mode, state="readonly", width=52,
                           values=("manual — every rule flags for review (recommended)",
                                   "heuristic — draft patterns from the STIG check text"))
        box.current(0)
        box.grid(row=2, column=1, sticky="w", **pad)

        # --- actions and log --------------------------------------------------
        btns = ttk.Frame(frame)
        btns.grid(row=3, column=0, columnspan=2, sticky="ew", **pad)
        self.test_btn = ttk.Button(btns, text="Test connection", command=self._on_test)
        self.test_btn.pack(side="left", padx=4)
        self.preview_btn = ttk.Button(btns, text="Preview file", command=self._on_preview)
        self.preview_btn.pack(side="left", padx=4)
        self.import_btn = ttk.Button(btns, text="Import", command=self._on_import)
        self.import_btn.pack(side="left", padx=4)

        self.log = tk.Text(frame, height=14, state="disabled", wrap="word")
        self.log.grid(row=4, column=0, columnspan=2, sticky="nsew", **pad)
        frame.rowconfigure(4, weight=1)

        self._toggle_auth()
        self._toggle_source()
        if HAVE_DND:
            root.drop_target_register(DND_FILES)
            root.dnd_bind("<<Drop>>", self._on_drop)
        root.after(150, self._drain_log)

    # ---- UI plumbing --------------------------------------------------------

    def _toggle_auth(self):
        state = "disabled" if self.win_auth.get() else "normal"
        self.user_entry.configure(state=state)
        self.pass_entry.configure(state=state)

    def _toggle_source(self):
        file_mode = self.source_kind.get() == "file"
        self.file_entry.configure(state="normal" if file_mode else "disabled")
        self.browse_btn.configure(state="normal" if file_mode else "disabled")
        self.url_entry.configure(state="disabled" if file_mode else "normal")

    def _browse(self):
        path = filedialog.askopenfilename(
            title="Select a STIG file",
            filetypes=[("STIG content", "*.zip *.xml *.xsl *.yaml *.yml"),
                       ("All files", "*.*")])
        if path:
            self.file_path.set(path)

    def _on_drop(self, event):
        path = event.data.strip("{}").split("} {")[0]
        self.source_kind.set("file")
        self._toggle_source()
        self.file_path.set(path)
        self._log(f"dropped: {path}")

    def _log(self, msg):
        self.log_queue.put(msg)

    def _drain_log(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log.configure(state="normal")
                self.log.insert("end", msg + "\n")
                self.log.see("end")
                self.log.configure(state="disabled")
        except queue.Empty:
            pass
        self.root.after(150, self._drain_log)

    def _busy(self, working):
        state = "disabled" if working else "normal"
        for b in (self.test_btn, self.preview_btn, self.import_btn):
            b.configure(state=state)

    def _run_bg(self, fn):
        self._busy(True)

        def wrapper():
            try:
                fn()
            except Exception as exc:  # surfaced to the log, never a crash
                self._log(f"ERROR: {exc}")
            finally:
                self.root.after(0, self._busy, False)

        threading.Thread(target=wrapper, daemon=True).start()

    # ---- shared helpers ------------------------------------------------------

    def _client(self):
        host = self.host.get().strip()
        if not host:
            raise SwisError("enter the SolarWinds server IP/FQDN first")
        port = int(self.port.get().strip() or DEFAULT_PORT)
        verify = self.verify_tls.get()
        if self.win_auth.get():
            return WindowsAuthClient(host, port, verify)
        user = self.user.get().strip()
        if not user:
            raise SwisError("enter a username (or tick Windows-user login)")
        return SwisClient(host, user, self.password.get(), port=port, verify=verify)

    def _resolve_source(self):
        """Return a local file path for the chosen source, downloading a URL if needed."""
        if self.source_kind.get() == "file":
            path = self.file_path.get().strip()
            if not path or not os.path.isfile(path):
                raise ValueError("choose a file first")
            return path
        url = self.url.get().strip()
        if not url:
            raise ValueError("enter the STIG package URL first")
        name = os.path.basename(url.split("?")[0]) or "stig-download"
        dest = os.path.join(tempfile.gettempdir(), name)
        self._log(f"downloading {url} …")
        req = urllib.request.Request(url, headers={"User-Agent": "disa-stig-conversion-tool/1.0"})
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=300, context=ctx) as resp, \
                open(dest, "wb") as out:
            while chunk := resp.read(1 << 16):
                out.write(chunk)
        self._log(f"saved {dest} ({os.path.getsize(dest):,} bytes)")
        self._downloaded = dest
        return dest

    def _target_choice(self):
        label = self.target.get()
        if label.startswith("Network"):
            return "network"
        if label.startswith("Server"):
            return "server"
        return "auto"

    def _describe(self, path):
        """Detect the target module and return ('scm-yaml'|'ncm'|'scm', preview lines)."""
        if is_scm_path(path):
            info = scan_scm_policy(load_scm_policy(path))
            sev = ", ".join(f"{v} {k}" for k, v in sorted(info["severity_counts"].items()))
            return "scm-yaml", [f"SCM compliance policy: {info['name']}",
                                f"  {len(info['rules'])} rules ({sev})",
                                "  target: Server Configuration Monitor "
                                "(Orion.PolicyEngine.Policy.ImportPolicy)"]
        lines = []
        benchmarks = load_benchmarks(path)
        for b in benchmarks:
            counts = {}
            for r in b["rules"]:
                counts[r["severity"]] = counts.get(r["severity"], 0) + 1
            sev = ", ".join(f"{counts[s]} {s}" for s in ("high", "medium", "low")
                            if s in counts)
            lines.append(f"{b['title']} [{b['edition']} edition]")
            lines.append(f"  V{b['version']} {b['release']} — {len(b['rules'])} rules ({sev})")
        kind, _info, note = resolve_route(self._target_choice(), benchmarks,
                                          os.path.basename(path),
                                          self.node_where.get().strip())
        lines.append("  " + note)
        return kind, lines

    # ---- actions --------------------------------------------------------------

    def _on_test(self):
        def work():
            swis = self._client()
            rows = swis.query("SELECT TOP 1 EngineVersion FROM Orion.Engines")
            version = rows[0]["EngineVersion"] if rows else "unknown"
            ncm = swis.query("SELECT COUNT(FullName) AS C FROM Metadata.Entity "
                             "WHERE FullName LIKE 'Cirrus.%'")[0]["C"]
            scm = swis.query("SELECT COUNT(FullName) AS C FROM Metadata.Entity "
                             "WHERE FullName LIKE 'Orion.PolicyEngine.%'")[0]["C"]
            self._log(f"connected — platform {version}; "
                      f"NCM {'present' if ncm else 'NOT installed'}, "
                      f"SCM policy engine {'present' if scm else 'NOT installed'}")
        self._run_bg(work)

    def _on_preview(self):
        def work():
            path = self._resolve_source()
            for line in self._describe(path)[1]:
                self._log(line)
        self._run_bg(work)

    def _on_import(self):
        def work():
            path = self._resolve_source()
            kind, lines = self._describe(path)
            for line in lines:
                self._log(line)
            swis = self._client()
            if kind == "scm-yaml":
                policy_id, name = import_scm_policy(swis, load_scm_policy(path))
                self._log(f"imported SCM policy \"{name}\" (PolicyID {policy_id}).")
                self._log("Assign it to nodes under Settings → SCM Settings → Policies.")
                return
            benchmarks = load_benchmarks(path)
            # The report is named after the original source (the zip's name when the
            # source is a URL download too), not the temp file it may have landed in.
            original = self.url.get().strip() if self.source_kind.get() == "url" else path
            _kind, info, _note = resolve_route(self._target_choice(), benchmarks,
                                               os.path.basename(path),
                                               self.node_where.get().strip())
            if kind == "server":
                import_scm_benchmarks(swis, benchmarks, info, log=self._log)
                self._log("done — assign the policies to nodes, then see "
                          "My Dashboards → Home → Server Configuration.")
                return
            mode = "heuristic" if self.mode.get().startswith("heuristic") else "manual"
            report = build_report(benchmarks,
                                  node_where=info,
                                  mode=mode,
                                  source_path=os.path.basename(original.split("?")[0]))
            existing = swis.query(
                "SELECT PolicyReportID FROM Cirrus.PolicyReports WHERE Name = @n",
                {"n": report["Name"]})
            if existing:
                raise SwisError(
                    f"a report named \"{report['Name']}\" already exists — "
                    "delete or rename it first; this tool never overwrites")
            n_rules = sum(len(p["AssignedPolicyRules"]) for p in report["AssignedPolicies"])
            self._log(f"importing \"{report['Name']}\" — "
                      f"{len(report['AssignedPolicies'])} policies, {n_rules} rules …")
            new_id, n_pol, n_rul = import_ncm_report(swis, report, log=self._log)
            self._log(f"imported \"{report['Name']}\" ({new_id}) — "
                      f"{n_pol} policies, {n_rul} rules; starting compliance caching …")
            swis.invoke("Cirrus.PolicyReports", "StartCaching", [new_id])
            self._log("done — see My Dashboards → Network Configuration → Compliance.")
        self._run_bg(work)


def run_gui():
    if not HAVE_TK:
        sys.exit("could not start the GUI: tkinter is not installed for this Python.\n"
                 "Install it (Windows/macOS installers include it; Debian/Ubuntu: "
                 "apt install python3-tk) or use the CLI: python disa_stig_tool.py --help")
    root = TkinterDnD.Tk() if HAVE_DND else tk.Tk()
    try:
        ttk.Style().theme_use("vista")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


def main():
    # No arguments (a double-click on Windows) or an explicit "gui" opens the GUI.
    if len(sys.argv) == 1 or sys.argv[1:] == ["gui"]:
        run_gui()
        return
    top = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = top.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("download", help="fetch a STIG package zip from DISA's public mirror")
    d.add_argument("package", help="package name (e.g. U_Cisco_IOS_Router_Y26M07_STIG) or full URL")
    d.add_argument("--dir", default=".", help="directory to save into")

    pp = sub.add_parser("parse", help="show what a STIG package contains")
    pp.add_argument("path", help="STIG zip, directory, or *-xccdf.xml file")
    pp.add_argument("--rules", action="store_true", help="list every rule")

    b = sub.add_parser("build", help="write the NCM report payload to a JSON file")
    add_source_args(b)
    b.add_argument("-o", "--output", help="output file (default: <source>.ncm-report.json)")

    imp = sub.add_parser("import", help="import into NCM via SWIS and start caching")
    add_source_args(imp)
    imp.add_argument("--host", required=True)
    imp.add_argument("--user", required=True)
    imp.add_argument("--port", type=int, default=DEFAULT_PORT)
    imp.add_argument("--ca-file", help="CA bundle that signs the SWIS certificate")
    imp.add_argument("--insecure", action="store_true",
                     help="skip TLS verification (lab only)")
    imp.add_argument("--no-cache", action="store_true",
                     help="import but do not start compliance caching")

    args = top.parse_args()
    try:
        {"download": cmd_download, "parse": cmd_parse,
         "build": cmd_build, "import": cmd_import}[args.cmd](args)
    except (ValueError, OSError, SwisError) as exc:
        sys.exit(f"error: {exc}")


if __name__ == "__main__":
    main()

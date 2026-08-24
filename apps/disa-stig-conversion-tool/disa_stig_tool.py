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
import hashlib
import io
import json
import os
import queue
import re
import socket
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


# Credentials live in memory only: never written to disk, never placed in URLs,
# and always redacted from anything the tool prints or logs.
_SECRETS = []


def register_secret(value):
    if value:
        _SECRETS.append(value)


def redact(text):
    for secret in _SECRETS:
        text = text.replace(secret, "••••••")
    return text


def fetch_server_cert(host, port=DEFAULT_PORT):
    """Fetch the certificate SWIS presents, for explicit trust (pinning).

    Returns (pem, sha256_fingerprint, looks_like_stock) where looks_like_stock
    is True when the certificate carries the stock 'SolarWinds-Orion' name.
    The fetch itself does not verify — that is the point: the operator inspects
    the fingerprint once, and every later connection verifies against exactly
    this certificate.
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with socket.create_connection((host, port), timeout=30) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as tls:
            der = tls.getpeercert(True)
    fingerprint = hashlib.sha256(der).hexdigest().upper()
    fingerprint = ":".join(fingerprint[i:i + 2] for i in range(0, len(fingerprint), 2))
    return ssl.DER_cert_to_PEM_cert(der), fingerprint, b"SolarWinds-Orion" in der


class SwisClient:
    """Minimal SWIS REST client — the same contract scripts/python/swis_client.py shows."""

    def __init__(self, host, username, password, port=DEFAULT_PORT, verify=True, ca_file=None,
                 pinned_pem=None):
        self.base = f"https://{host}:{port}{BASE_PATH}"
        self.username = username
        self.password = password
        register_secret(password)
        if pinned_pem:
            # Trust exactly the fetched SolarWinds-Orion certificate. The stock
            # certificate's CN is 'SolarWinds-Orion', not the host name, so the
            # hostname check is off — the chain check against the pinned
            # certificate is what authenticates the server.
            self.ctx = ssl.create_default_context(cadata=pinned_pem)
            self.ctx.check_hostname = False
        elif verify:
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
    if policy_id is None:
        raise SwisError("No data returned from Orion.PolicyEngine.Policy.ImportPolicy — "
                        "the policy was not created")
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


def make_node_selection_string(node_where):
    """The NodeSelectionString in the format real console exports carry.

    Verified against exports from a live 2026.2.2 server: the literal prefix
    ``WebCriteria:``, an XML-escaped ArrayOfWebSelectionCriteria document (the
    console node-picker's state), then ``SQL:Where (…)`` — the part NCM
    actually filters on. Column names in the SQL fragment are bare (Vendor,
    not Nodes.Vendor).
    """
    where = re.sub(r"\bNodes\.", "", node_where or "").strip()
    if not where.lower().startswith("("):
        where = f"({where})"
    m = re.search(r"Vendor\s*(?:=|LIKE)\s*'%?([^%']+)%?'", where, re.IGNORECASE)
    criteria = ""
    if m:
        vendor = m.group(1)
        criteria = (
            '<?xml version="1.0" encoding="utf-16"?>\n'
            '<ArrayOfWebSelectionCriteria xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
            "  <WebSelectionCriteria>\n"
            f"    <Id>{uuid.uuid5(uuid.NAMESPACE_URL, 'stig2ncm-criteria:' + vendor)}</Id>\n"
            "    <LogicalCondition />\n"
            "    <SelectedColumn>Vendor</SelectedColumn>\n"
            "    <MatchType>=</MatchType>\n"
            f"    <SelectedValue>{vendor}</SelectedValue>\n"
            "  </WebSelectionCriteria>\n"
            "</ArrayOfWebSelectionCriteria>")
    return f"WebCriteria:{criteria}SQL:Where {where} "


def build_reports(benchmarks, name=None, grouping="DISA STIG", node_where="(Vendor = 'Cisco')",
                  config_type="Any", mode="manual", source_path=None):
    """Assemble one PolicyReport contract object per benchmark.

    Matching how the console's own exports are structured (one policy per
    report): each benchmark in the package becomes its own report — the Cisco
    IOS Router package yields an NDM report (35 rules) and an RTR report
    (92 rules) — whose single policy carries the device scope and joins the
    report to its rules.
    """
    if name is None and source_path and source_path.lower().endswith(".zip"):
        name = os.path.splitext(os.path.basename(source_path))[0]
    reports = []
    for b in benchmarks:
        policy_group = f"{grouping}/{b['benchmark_id']}" if b["benchmark_id"] else grouping
        rules = [rule_object(r, policy_group, mode) for r in b["rules"]]
        policy = {
            "PolicyId": str(uuid.uuid5(uuid.NAMESPACE_URL,
                                       "stig2ncm-policy:" + (b["benchmark_id"] or b["title"]))),
            "PolicyName": f"{b['title']} V{b['version']} ({b['release']})"[:250],
            "Comments": f"Imported by the DISA STIG Conversion Tool from {b['source']} (benchmark {b['benchmark_id']}, "
                        f"status date {b['status_date']}).",
            "Grouping": grouping,
            "NodeSelectionString": make_node_selection_string(node_where),
            "ConfigTypes": config_type,
            "AssignedPolicyRules": rules,
            "AssignedRulesList": [r["RuleId"] for r in rules],
        }
        base = name or b["title"]
        report_name = f"{base} - {b['benchmark_id']}" if name and b["benchmark_id"] else base
        reports.append({
            "ID": str(uuid.uuid4()),  # advisory only — the server assigns its own GUID
            "Name": report_name[:250],
            "Comments": f"DISA STIG imported by the DISA STIG Conversion Tool from "
                        f"{b['source']} ({b['release']}).",
            "Group": grouping,
            "ShowSummaryFlag": True,
            "ShowRulesWithoutViolationFlag": True,
            "AssignedPolicies": [policy],
            "AssignedPoliciesList": [policy["PolicyId"]],
            "ReportStatus": "Enabled",
        })
    return reports


def build_report(benchmarks, **kwargs):
    """Back-compatible single-report build (first benchmark only)."""
    return build_reports(benchmarks, **kwargs)[0]


def write_console_file(report, folder="."):
    """Write a report as a console-importable file, byte-matching real exports:
    UTF-8 without BOM, CRLF line endings, and the (lying) utf-16 declaration."""
    out = os.path.join(folder, re.sub(r"[^\w.-]+", "_", report["Name"]) + ".ncm-report.xml")
    root = ET.fromstring(report_contract_xml(report))
    ET.indent(root, space="  ")
    body = '<?xml version="1.0" encoding="utf-16"?>\n' + ET.tostring(root, encoding="unicode")
    with open(out, "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write(body)
    return out


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


# ---------------------------------------------------------------------------
# DataContract XML wire format (the .NET serializer behind "cannot unpackage")
# ---------------------------------------------------------------------------
#
# When the server says it "cannot unpackage" a parameter, it read the XML but
# the DataContractSerializer rejected it: that serializer wants the contract's
# namespace and its members in a fixed (alphabetical, absent explicit Order)
# sequence. These writers emit that shape; `ns` is the contract namespace to
# try ("" for contracts declared with an empty namespace).

DC_NS = "http://schemas.datacontract.org/2004/07/SolarWinds.NCM.Contracts.Compliance"
ARRAYS_NS = "http://schemas.microsoft.com/2003/10/Serialization/Arrays"


def _dc_el(parent, ns, name, text=None):
    el = ET.SubElement(parent, f"{{{ns}}}{name}" if ns else name)
    if text is not None and text != "":
        el.text = text
    return el


def _dc_string_list(parent, ns, name, values):
    holder = _dc_el(parent, ns, name)
    for v in values:
        item = ET.SubElement(holder, f"{{{ARRAYS_NS}}}string")
        item.text = v


def dc_rule_xml(rule, ns=DC_NS):
    root = ET.Element(f"{{{ns}}}PolicyRule" if ns else "PolicyRule")
    _dc_el(root, ns, "AdvancedMode", _b_str(rule.get("AdvancedMode")))
    _dc_el(root, ns, "Comments", rule.get("Comments") or "")
    _dc_el(root, ns, "ConfigBlockEnd", rule.get("ConfigBlockEnd") or "")
    _dc_el(root, ns, "ConfigBlockMustExist", _b_str(rule.get("ConfigBlockMustExist")))
    _dc_el(root, ns, "ConfigBlockPatternType", str(rule.get("ConfigBlockPatternType") or "Like"))
    _dc_el(root, ns, "ConfigBlockStart", rule.get("ConfigBlockStart") or "")
    _dc_el(root, ns, "ErrorLevel", str(int(rule.get("ErrorLevel") or 0)))
    _dc_el(root, ns, "ExecuteRemediationScriptPerBlock",
           _b_str(rule.get("ExecuteRemediationScriptPerBlock")))
    _dc_el(root, ns, "ExecuteScriptAutomatically", _b_str(rule.get("ExecuteScriptAutomatically")))
    _dc_el(root, ns, "ExecuteScriptInConfigMode", _b_str(rule.get("ExecuteScriptInConfigMode")))
    _dc_el(root, ns, "Grouping", rule.get("Grouping") or "")
    _dc_el(root, ns, "IsConfigBlockPatternRegEx", _b_str(rule.get("IsConfigBlockPatternRegEx")))
    _dc_el(root, ns, "MultiLineRulePatterns")
    _dc_el(root, ns, "Owner", rule.get("Owner") or "")
    _dc_el(root, ns, "PatternMustExist", _b_str(rule.get("PatternMustExist")))
    _dc_el(root, ns, "PatternType", str(rule.get("PatternType") or "Like"))
    _dc_el(root, ns, "RemediateScript", rule.get("RemediateScript") or "")
    _dc_el(root, ns, "RemediateScriptType", str(rule.get("RemediateScriptType") or "CLI"))
    _dc_el(root, ns, "RuleId", rule.get("RuleId") or "")
    _dc_el(root, ns, "RuleName", rule.get("RuleName") or "")
    _dc_el(root, ns, "SimplePatternText", rule.get("SimplePatternText") or "")
    return ET.tostring(root, encoding="unicode")


def dc_policy_xml(policy, rule_ids, ns=DC_NS):
    root = ET.Element(f"{{{ns}}}Policy" if ns else "Policy")
    _dc_el(root, ns, "AssignedPolicyRules")
    _dc_string_list(root, ns, "AssignedRulesList", rule_ids)
    _dc_el(root, ns, "Comments", policy.get("Comments") or "")
    _dc_el(root, ns, "ConfigTypes", str(policy.get("ConfigTypes") or "Any"))
    _dc_el(root, ns, "Grouping", policy.get("Grouping") or "")
    _dc_el(root, ns, "NodeSelectionString", policy.get("NodeSelectionString") or "")
    _dc_el(root, ns, "PolicyId", policy.get("PolicyId") or "")
    _dc_el(root, ns, "PolicyName", policy.get("PolicyName") or "")
    return ET.tostring(root, encoding="unicode")


def dc_report_xml(report, policy_ids, ns=DC_NS):
    root = ET.Element(f"{{{ns}}}PolicyReport" if ns else "PolicyReport")
    _dc_el(root, ns, "AssignedPolicies")
    _dc_string_list(root, ns, "AssignedPoliciesList", policy_ids)
    _dc_el(root, ns, "Comments", report.get("Comments") or "")
    _dc_el(root, ns, "Group", report.get("Group") or "")
    _dc_el(root, ns, "ID", report.get("ID") or "")
    _dc_el(root, ns, "Name", report.get("Name") or "")
    _dc_el(root, ns, "ReportStatus", str(report.get("ReportStatus") or "Enabled"))
    _dc_el(root, ns, "ShowRulesWithoutViolationFlag",
           _b_str(report.get("ShowRulesWithoutViolationFlag")))
    _dc_el(root, ns, "ShowSummaryFlag", _b_str(report.get("ShowSummaryFlag")))
    return ET.tostring(root, encoding="unicode")


# The wire formats the probe tries, in order. Each entry maps a rule/policy/
# report to the AddPolicyRule / AddPolicy / AddPolicyReport argument.
WIRE_FORMATS = {
    "json": {
        "label": "JSON contract objects",
        "rule": lambda r: r,
        "policy": lambda p, ids: dict(p, AssignedPolicyRules=[], AssignedRulesList=ids),
        "report": lambda rep, ids: dict(rep, AssignedPolicies=[], AssignedPoliciesList=ids),
    },
    "xml-dc": {
        "label": "DataContract XML strings",
        "rule": lambda r: dc_rule_xml(r, DC_NS),
        "policy": lambda p, ids: dc_policy_xml(p, ids, DC_NS),
        "report": lambda rep, ids: dc_report_xml(rep, ids, DC_NS),
    },
    "xml-plain": {
        "label": "plain XML strings (no namespace)",
        "rule": lambda r: dc_rule_xml(r, ""),
        "policy": lambda p, ids: dc_policy_xml(p, ids, ""),
        "report": lambda rep, ids: dc_report_xml(rep, ids, ""),
    },
}


def _clean_id(value, fallback):
    """Verb results come back as JSON strings that may carry quotes or braces."""
    if isinstance(value, str):
        cleaned = value.strip().strip('"').strip("{}").strip()
        if cleaned:
            return cleaned
    return fallback


def _verify_report(swis, report_id, expected_policies, expected_rules, log):
    """Read the report back — the import is only done if the tree actually exists."""
    stored = swis.invoke("Cirrus.PolicyReports", "GetPolicyReport", report_id, True)
    if not stored:
        raise SwisError(f"No data returned from GetPolicyReport for report {report_id} — "
                        "the import cannot be confirmed")
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


class NcmWireError(SwisError):
    """No wire format the server accepts was found. Carries a console-importable
    XML file body so the caller can save it and finish the import through the
    NCM web console (Compliance → Manage Policy Reports → Import)."""

    def __init__(self, message, console_xml):
        super().__init__(message)
        self.console_xml = console_xml


def import_ncm_report(swis, report, log=print):
    """Import the report, probing how this server accepts the NCM contract types.

    The JSON endpoint's handling of SolarWinds.NCM.Contracts.Compliance.*
    varies by server: some map JSON objects, some want the contract serialized
    as an XML string ("Value cannot be null" / "cannot unpackage" are the two
    observed rejections). One cheap AddPolicyRule call probes each candidate
    format — JSON object, DataContract XML, plain XML — and the first one the
    server accepts is used for the whole bottom-up import (rules → policies →
    report, linked by ID lists). If none works, a nested console-format
    AddPolicyReport is tried, and as a last resort NcmWireError hands back a
    console-importable file so the import can be finished in the web UI.

    The result is verified by reading the report back before caching starts.
    Returns (report_id, policy_count, rule_count) as confirmed by the read-back.
    """
    probe_rule = report["AssignedPolicies"][0]["AssignedPolicyRules"][0]
    fmt = None
    first_rule_id = None
    rejections = []
    for name, spec in WIRE_FORMATS.items():
        try:
            result = swis.invoke("Cirrus.PolicyReports", "AddPolicyRule",
                                 spec["rule"](probe_rule))
            first_rule_id = _clean_id(result, probe_rule["RuleId"])
            fmt = name
            log(f"server accepts {spec['label']}")
            break
        except SwisError as exc:
            if "HTTP 400" not in str(exc):
                raise
            rejections.append(f"{spec['label']}: {str(exc).splitlines()[-1]}")
            log(f"server rejected {spec['label']}; trying the next wire format …")
    if fmt:
        return _import_ncm_bottom_up(swis, report, log, WIRE_FORMATS[fmt],
                                     first_rule_id)

    log("no per-item wire format accepted; trying one nested AddPolicyReport "
        "in the console-export format …")
    n_policies = len(report["AssignedPolicies"])
    n_rules = sum(len(p["AssignedPolicyRules"]) for p in report["AssignedPolicies"])
    try:
        report_id = _clean_id(
            swis.invoke("Cirrus.PolicyReports", "AddPolicyReport",
                        report_contract_xml(report), True), "")
        if report_id:
            return _verify_report(swis, report_id, n_policies, n_rules, log)
        rejections.append("console-format XML: no report id returned")
    except SwisError as exc:
        if "HTTP 400" not in str(exc):
            raise
        rejections.append(f"console-format XML: {str(exc).splitlines()[-1]}")
    raise NcmWireError(
        "this server accepted none of the wire formats for the NCM compliance "
        "contract types:\n  " + "\n  ".join(rejections) + "\n"
        "A console-importable report file has been written instead — import it in "
        "the web console under Compliance → Manage Policy Reports → Import.",
        '<?xml version="1.0" encoding="utf-16"?>' + report_contract_xml(report))


def _import_ncm_bottom_up(swis, report, log, spec, first_rule_id):
    policy_ids = []
    total_rules = 0
    first = True
    for policy in report["AssignedPolicies"]:
        rules = policy["AssignedPolicyRules"]
        log(f"creating {len(rules)} rules for policy \"{policy['PolicyName']}\" …")
        rule_ids = []
        for i, rule in enumerate(rules, 1):
            if first:
                # The probe already created this rule.
                rule_ids.append(first_rule_id)
                first = False
                continue
            result = swis.invoke("Cirrus.PolicyReports", "AddPolicyRule",
                                 spec["rule"](rule))
            rule_ids.append(_clean_id(result, rule["RuleId"]))
            if i % 25 == 0:
                log(f"  {i}/{len(rules)} rules created")
        total_rules += len(rule_ids)

        result = swis.invoke("Cirrus.PolicyReports", "AddPolicy",
                             spec["policy"](policy, rule_ids), False)
        policy_ids.append(_clean_id(result, policy["PolicyId"]))
        log(f"created policy \"{policy['PolicyName']}\" with {len(rule_ids)} rules")

    report_id = _clean_id(
        swis.invoke("Cirrus.PolicyReports", "AddPolicyReport",
                    spec["report"](report, policy_ids), False), "")
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
    # Bare column names: the SQL fragment in real console exports says Vendor,
    # not Nodes.Vendor, and exact vendor equality is what the node picker writes.
    return f"(Vendor = '{vendor}')" if vendor else "(Vendor = 'Cisco')"


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
    return os.path.isfile(path) and path.lower().endswith((".yaml", ".yml", ".scm-profile"))


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


def make_reports_from_args(args, benchmarks, node_where):
    return build_reports(
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
                f"{stem}.{b['benchmark_id'] or 'benchmark'}.scm-profile"
            with open(out, "w", encoding="utf-8") as fh:
                fh.write(xccdf_to_scm_yaml(b))
            print(f"wrote {out}: SCM policy \"{b['title']}\" — {len(b['rules'])} rules")
        print("import with:  disa_stig_tool.py import <same source> --target server …")
        return
    reports = make_reports_from_args(args, benchmarks, info)
    for report in reports:
        out = write_console_file(report)
        n_rules = sum(len(p["AssignedPolicyRules"]) for p in report["AssignedPolicies"])
        print(f"wrote {out}: report \"{report['Name']}\" — {n_rules} rules "
              "(console-importable XML)")
    print("import via the API with:  disa_stig_tool.py import <same source> …  "
          "or through the web console: Compliance → Manage Policy Reports → Import")


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
    register_secret(password)
    pinned = None
    if args.pin_server_cert:
        pinned, fingerprint, stock = fetch_server_cert(args.host, args.port)
        print(f"pinned the server certificate — SHA-256 {fingerprint}"
              + (" (stock SolarWinds-Orion certificate)" if stock else ""))
    swis = SwisClient(args.host, args.user, password, port=args.port,
                      verify=not args.insecure, ca_file=args.ca_file, pinned_pem=pinned)

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

    reports = make_reports_from_args(args, benchmarks, info)
    for report in reports:
        existing = swis.query("SELECT PolicyReportID FROM Cirrus.PolicyReports WHERE Name = @n",
                              {"n": report["Name"]})
        if existing:
            sys.exit(f"error: a report named \"{report['Name']}\" already exists "
                     f"({existing[0]['PolicyReportID']}). Rename with --name, or delete it "
                     "first — this tool never overwrites.")

    new_ids = []
    for report in reports:
        n_rules = sum(len(p["AssignedPolicyRules"]) for p in report["AssignedPolicies"])
        print(f"importing \"{report['Name']}\" — {n_rules} rules …")
        try:
            new_id, _n_pol, n_rul = import_ncm_report(swis, report)
        except NcmWireError as exc:
            print(f"error: {exc}")
            for rep in reports:
                print(f"wrote {write_console_file(rep)}")
            sys.exit("import the files through the web console: "
                     "Compliance → Manage Policy Reports → Import")
        new_ids.append(new_id)
        print(f"imported: \"{report['Name']}\" ({new_id}) — {n_rul} rules")

    if args.no_cache:
        print("compliance caching not started (--no-cache); the reports show no data until "
              "you run Update Violations in the console or invoke StartCaching.")
        return
    # Always pass the specific GUIDs: an empty array would re-cache every report.
    swis.invoke("Cirrus.PolicyReports", "StartCaching", new_ids)
    print(f"compliance caching started for {len(new_ids)} report(s). Watch them under "
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
                   help="NCM node-selection Where clause, e.g. \"(Vendor = 'Cisco')\". "
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


DISCLAIMER_TEXT = ("This is not built by SolarWinds Inc. or DISA. All Code is visible "
                   "for Code Audit and documentation is available for SWIS calls.")
ACK_TEXT = ("I Acknowledge that I will check the Reports Imported and Understand that "
            "DISA STIG Reports do not always include explicit instructions to resolve. "
            "Resolution falls on Agency application of the standards set by the "
            "DISA STIG System")

MAX_BATCH_FILES = 10
BTN_GREEN, BTN_YELLOW, BTN_RED = "#c6efce", "#ffeb9c", "#ffc7ce"


def file_module(path):
    """NCM or SCM for one file — the module a batch locks to."""
    if is_scm_path(path):
        return "SCM"
    benchmarks = load_benchmarks(path)
    kind, _info = detect_target(benchmarks, os.path.basename(path))
    return "SCM" if kind == "server" else "NCM"


def show_disclaimer(root):
    """Startup gate: the acknowledgment checkbox must be ticked to proceed."""
    gate = tk.Toplevel(root)
    gate.title("DISA STIG Conversion Tool")
    gate.grab_set()
    gate.protocol("WM_DELETE_WINDOW", lambda: (result.update(ok=False), gate.destroy()))
    result = {"ok": False}
    frame = ttk.Frame(gate, padding=16)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text=DISCLAIMER_TEXT, wraplength=560,
              font=("TkDefaultFont", 10, "bold")).pack(anchor="w", pady=(0, 12))
    acked = tk.BooleanVar(value=False)
    ttk.Checkbutton(frame, text=ACK_TEXT, variable=acked,
                    command=lambda: proceed.configure(
                        state="normal" if acked.get() else "disabled")).pack(anchor="w")
    proceed = ttk.Button(frame, text="Proceed", state="disabled",
                         command=lambda: (result.update(ok=True), gate.destroy()))
    proceed.pack(anchor="e", pady=(16, 0))
    gate.wait_window()
    return result["ok"]


class App:
    def __init__(self, root):
        self.root = root
        root.title("DISA STIG Conversion Tool")
        root.minsize(760, 640)
        self.log_queue = queue.Queue()
        self.pinned_pem = None       # memory only, like the credentials
        self.batch_module = None     # locked to NCM or SCM by the first file

        pad = {"padx": 8, "pady": 3}
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
        self.verify_tls = tk.BooleanVar(value=True)
        ttk.Checkbutton(conn, text="Verify TLS certificate (default)",
                        variable=self.verify_tls).grid(row=3, column=2, columnspan=2,
                                                       sticky="e", **pad)
        # live connection status, directly under the login controls
        self.conn_status = tk.StringVar(value="Connection: not tested")
        ttk.Label(conn, textvariable=self.conn_status).grid(
            row=4, column=0, columnspan=2, sticky="w", **pad)
        ttk.Button(conn, text="Trust server certificate…",
                   command=self._on_pin_cert).grid(row=4, column=2, columnspan=2,
                                                   sticky="e", **pad)

        # --- files (up to MAX_BATCH_FILES; one module per batch) --------------
        src = ttk.LabelFrame(
            frame, text=f"STIG files (up to {MAX_BATCH_FILES} — one module per "
                        "batch: NCM or SCM, never both)", padding=8)
        src.grid(row=1, column=0, columnspan=2, sticky="ew", **pad)
        src.columnconfigure(0, weight=1)
        self.file_list = tk.Listbox(src, height=5)
        self.file_list.grid(row=0, column=0, rowspan=3, sticky="ew", **pad)
        ttk.Button(src, text="Browse…", command=self._browse).grid(row=0, column=1, **pad)
        ttk.Button(src, text="Remove", command=self._remove_file).grid(row=1, column=1, **pad)
        ttk.Button(src, text="Clear", command=self._clear_files).grid(row=2, column=1, **pad)
        self.url = tk.StringVar()
        ttk.Entry(src, textvariable=self.url).grid(row=3, column=0, sticky="ew", **pad)
        ttk.Button(src, text="Add URL", command=self._add_url).grid(row=3, column=1, **pad)
        self.module_notice = tk.StringVar(
            value="Module: (select a file — the batch locks to NCM or SCM "
                  "based on the first file)")
        ttk.Label(src, textvariable=self.module_notice).grid(
            row=4, column=0, columnspan=2, sticky="w", **pad)

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
        ttk.Label(opts, text="NCM node scope").grid(row=1, column=0, sticky="w", **pad)
        self.node_where = tk.StringVar(value="(auto — from the detected vendor)")
        ttk.Entry(opts, textvariable=self.node_where).grid(row=1, column=1, sticky="ew", **pad)
        ttk.Label(opts, text="NCM rule patterns").grid(row=2, column=0, sticky="w", **pad)
        self.mode = tk.StringVar(value="manual")
        box = ttk.Combobox(opts, textvariable=self.mode, state="readonly", width=52,
                           values=("manual — every rule flags for review (recommended)",
                                   "heuristic — draft patterns from the STIG check text"))
        box.current(0)
        box.grid(row=2, column=1, sticky="w", **pad)

        # --- actions (tk.Buttons so completion colors show) -------------------
        btns = ttk.Frame(frame)
        btns.grid(row=3, column=0, columnspan=2, sticky="ew", **pad)
        self.test_btn = tk.Button(btns, text="Test Connection", command=self._on_test)
        self.test_btn.pack(side="left", padx=4)
        self.import_btn = tk.Button(btns, text="Import",
                                    command=lambda: self._on_batch(offline=False))
        self.import_btn.pack(side="left", padx=4)
        self.convert_btn = tk.Button(btns, text="Local File Conversion Only",
                                     command=lambda: self._on_batch(offline=True))
        self.convert_btn.pack(side="left", padx=4)
        self.details_btn = ttk.Button(btns, text="Show detailed log",
                                      command=self._toggle_details)
        self.details_btn.pack(side="right", padx=4)

        # --- summary (always visible) + auto-hidden detailed log --------------
        self.summary = tk.Text(frame, height=8, state="disabled", wrap="word")
        self.summary.grid(row=4, column=0, columnspan=2, sticky="nsew", **pad)
        self.summary.tag_configure("success", foreground="#1e7d32")
        self.summary.tag_configure("fail", foreground="#b00020")
        self.summary.tag_configure("warn", foreground="#8a6d00")
        frame.rowconfigure(4, weight=1)
        self.detail = tk.Text(frame, height=10, state="disabled", wrap="word")
        self.detail.grid(row=5, column=0, columnspan=2, sticky="nsew", **pad)
        self.detail.grid_remove()
        frame.rowconfigure(5, weight=1)

        self._toggle_auth()
        if HAVE_DND:
            root.drop_target_register(DND_FILES)
            root.dnd_bind("<<Drop>>", self._on_drop)
        root.after(150, self._drain_log)

    def _toggle_auth(self):
        state = "disabled" if self.win_auth.get() else "normal"
        self.user_entry.configure(state=state)
        self.pass_entry.configure(state=state)

    # ---- logging: colored summary, hidden detail -----------------------------

    def _append(self, widget, msg, tag=None):
        widget.configure(state="normal")
        if tag:
            widget.insert("end", redact(str(msg)) + "\n", tag)
        else:
            widget.insert("end", redact(str(msg)) + "\n")
        widget.see("end")
        widget.configure(state="disabled")

    def _summary_line(self, msg, tag=None):
        self.root.after(0, self._append, self.summary, msg, tag)

    def _log(self, msg):        # detailed log (worker threads use this)
        self.log_queue.put(redact(str(msg)))

    def _drain_log(self):
        try:
            while True:
                self._append(self.detail, self.log_queue.get_nowait())
        except queue.Empty:
            pass
        self.root.after(150, self._drain_log)

    def _toggle_details(self):
        if self.detail.winfo_viewable():
            self.detail.grid_remove()
            self.details_btn.configure(text="Show detailed log")
        else:
            self.detail.grid()
            self.details_btn.configure(text="Hide detailed log")

    def _show_issue(self):
        self.root.after(0, lambda: (self.detail.grid(),
                                    self.details_btn.configure(text="Hide detailed log")))

    def _set_button(self, btn, color):
        self.root.after(0, lambda: btn.configure(bg=color, activebackground=color))

    # ---- file batch ----------------------------------------------------------

    def _add_files(self, paths):
        for path in paths:
            if self.file_list.size() >= MAX_BATCH_FILES:
                self._summary_line(f"at most {MAX_BATCH_FILES} files per batch", "warn")
                return
            try:
                module = file_module(path)
            except (ValueError, OSError) as exc:
                self._summary_line(f"skipped {os.path.basename(path)}: {exc}", "fail")
                continue
            if self.batch_module is None:
                self.batch_module = module
                self.module_notice.set(f"Module: locked to {module} for this batch "
                                       "(from the first file selected)")
                self._summary_line(f"notice: this batch is now a {module} import")
            elif module != self.batch_module:
                self._summary_line(
                    f"skipped {os.path.basename(path)}: it is a {module} file, but this "
                    f"batch is locked to {self.batch_module} — run it in a separate batch",
                    "warn")
                continue
            self.file_list.insert("end", path)

    def _browse(self):
        paths = filedialog.askopenfilenames(
            title="Select STIG files",
            filetypes=[("STIG content", "*.zip *.xml *.xsl *.yaml *.yml *.scm-profile"),
                       ("All files", "*.*")])
        if paths:
            self._add_files(paths)

    def _remove_file(self):
        for index in reversed(self.file_list.curselection()):
            self.file_list.delete(index)
        if self.file_list.size() == 0:
            self._clear_files()

    def _clear_files(self):
        self.file_list.delete(0, "end")
        self.batch_module = None
        self.module_notice.set("Module: (select a file — the batch locks to NCM or SCM "
                               "based on the first file)")

    def _on_drop(self, event):
        self._add_files([p for p in self.root.tk.splitlist(event.data)])

    def _add_url(self):
        url = self.url.get().strip()
        if not url:
            return
        def work():
            name = os.path.basename(url.split("?")[0]) or "stig-download"
            dest = os.path.join(tempfile.gettempdir(), name)
            self._log(f"downloading {url} …")
            req = urllib.request.Request(url, headers={"User-Agent": "disa-stig-conversion-tool/1.0"})
            with urllib.request.urlopen(req, timeout=300) as resp, open(dest, "wb") as out:
                while chunk := resp.read(1 << 16):
                    out.write(chunk)
            self._log(f"saved {dest} ({os.path.getsize(dest):,} bytes)")
            self.root.after(0, self._add_files, [dest])
        self._run_bg(work)

    # ---- shared helpers ------------------------------------------------------

    def _busy(self, working):
        state = "disabled" if working else "normal"
        for b in (self.test_btn, self.import_btn, self.convert_btn):
            b.configure(state=state)

    def _run_bg(self, fn):
        self._busy(True)
        def wrapper():
            try:
                fn()
            except Exception as exc:  # surfaced to the summary, never a crash
                self._summary_line(f"ERROR: {exc}", "fail")
                self._log(f"ERROR: {exc}")
                self._show_issue()
            finally:
                self.root.after(0, self._busy, False)
        threading.Thread(target=wrapper, daemon=True).start()

    def _client(self):
        host = self.host.get().strip()
        if not host:
            raise SwisError("enter the SolarWinds server IP/FQDN first")
        port = int(self.port.get().strip() or DEFAULT_PORT)
        verify = self.verify_tls.get()
        if self.win_auth.get():
            if self.pinned_pem:
                self._log("note: certificate pinning applies to username/password "
                          "connections; the Windows-user login uses the system trust store")
            return WindowsAuthClient(host, port, verify)
        user = self.user.get().strip()
        if not user:
            raise SwisError("enter a username (or tick Windows-user login)")
        return SwisClient(host, user, self.password.get(), port=port, verify=verify,
                          pinned_pem=self.pinned_pem)

    def _target_choice(self):
        label = self.target.get()
        if label.startswith("Network"):
            return "network"
        if label.startswith("Server"):
            return "server"
        return "auto"

    def _on_pin_cert(self):
        def work():
            host = self.host.get().strip()
            if not host:
                raise SwisError("enter the SolarWinds server IP/FQDN first")
            port = int(self.port.get().strip() or DEFAULT_PORT)
            pem, fingerprint, stock = fetch_server_cert(host, port)
            self.pinned_pem = pem  # memory only — dropped when the window closes
            note = " (stock SolarWinds-Orion certificate)" if stock else ""
            self._summary_line(f"trusted the certificate {host}:{port} presents — "
                               f"SHA-256 {fingerprint}{note}")
            self._log("this session now verifies against exactly that certificate")
        self._run_bg(work)

    # ---- actions --------------------------------------------------------------

    def _on_test(self):
        self.test_btn.configure(bg="SystemButtonFace" if sys.platform == "win32" else "#d9d9d9")
        self.conn_status.set("Connection: testing …")
        def work():
            try:
                swis = self._client()
                rows = swis.query("SELECT TOP 1 EngineVersion FROM Orion.Engines")
            except SwisError as exc:
                self._set_button(self.test_btn, BTN_RED)
                self.conn_status.set("Connection: FAILED")
                self._summary_line(f"connection failed: {exc}", "fail")
                self._log(str(exc))
                self._show_issue()
                return
            problems = []
            version = rows[0]["EngineVersion"] if rows else "unknown"
            if not rows:
                problems.append("No data returned from the Orion.Engines query — "
                                "connected, but the account may lack read access")
            match = re.match(r"(\d+)", str(version))
            if match and int(match.group(1)) < 2023:
                problems.append(f"SWIS version mismatch: platform {version} predates "
                                "2023.1 — the REST port is 17778 there, not 17774")
            ncm = swis.query("SELECT COUNT(FullName) AS C FROM Metadata.Entity "
                             "WHERE FullName LIKE 'Cirrus.%'")[0]["C"]
            scm = swis.query("SELECT COUNT(FullName) AS C FROM Metadata.Entity "
                             "WHERE FullName LIKE 'Orion.PolicyEngine.%'")[0]["C"]
            if not ncm:
                problems.append("[NCM] Cirrus entities not present — NCM is not "
                                "installed or not readable by this account")
            if not scm:
                problems.append("[SCM] Orion.PolicyEngine entities not present — SCM is "
                                "not installed or not readable by this account")
            if problems:
                self._set_button(self.test_btn, BTN_YELLOW)
                self.conn_status.set(f"Connection: limited — platform {version} (see log)")
                self._summary_line(f"connected with limitations — platform {version}", "warn")
                for problem in problems:
                    self._log(problem)
                self._show_issue()
            else:
                self._set_button(self.test_btn, BTN_GREEN)
                self.conn_status.set(f"Connection: OK — platform {version}")
                self._summary_line(f"connected — platform {version}; NCM present, "
                                   "SCM policy engine present", "success")
        self._run_bg(work)

    def _resolve_ncm_where(self, benchmarks, source_name):
        _kind, info, note = resolve_route(self._target_choice(), benchmarks,
                                          source_name, self.node_where.get().strip())
        self._log(note)
        return info

    def _on_batch(self, offline):
        btn = self.convert_btn if offline else self.import_btn
        btn.configure(bg="SystemButtonFace" if sys.platform == "win32" else "#d9d9d9")
        files = list(self.file_list.get(0, "end"))
        module = self.batch_module
        if not files:
            self._summary_line("select at least one file", "warn")
            return
        def work():
            swis = None if offline else self._client()
            ok = fail = 0
            for path in files:
                prefix = f"[{module}]"
                try:
                    if module == "SCM":
                        done = self._do_scm(swis, path, offline, prefix)
                    else:
                        done = self._do_ncm(swis, path, offline, prefix)
                    ok += 1 if done else 0
                    fail += 0 if done else 1
                except (SwisError, ValueError, OSError) as exc:
                    fail += 1
                    self._summary_line(f"{prefix} FAILED {os.path.basename(path)}: {exc}",
                                       "fail")
                    self._log(f"{prefix} {exc}")
                    self._show_issue()
            color = BTN_GREEN if fail == 0 else (BTN_YELLOW if ok else BTN_RED)
            self._set_button(btn, color)
        self._run_bg(work)

    def _do_scm(self, swis, path, offline, prefix):
        if is_scm_path(path):
            if offline:
                self._summary_line(f"{prefix} {os.path.basename(path)} is already an "
                                   "importable SCM policy — nothing to convert")
                return True
            policy_id, name = import_scm_policy(swis, load_scm_policy(path))
            self._summary_line(f"SUCCESS {prefix} \"{name}\" (PolicyID {policy_id})",
                               "success")
            return True
        folder = os.path.dirname(path) if os.access(os.path.dirname(path) or ".",
                                                    os.W_OK) else tempfile.gettempdir()
        for b in load_benchmarks(path):
            if offline:
                out = os.path.join(folder, re.sub(r"[^\w.-]+", "_",
                                                  b["benchmark_id"] or b["title"])
                                   + ".scm-profile")
                with open(out, "w", encoding="utf-8") as fh:
                    fh.write(xccdf_to_scm_yaml(b))
                self._summary_line(f"SUCCESS {prefix} wrote {os.path.basename(out)} — "
                                   f"{len(b['rules'])} rules", "success")
            else:
                policy_id, name = import_scm_policy(swis, xccdf_to_scm_yaml(b))
                self._summary_line(f"SUCCESS {prefix} \"{name}\" "
                                   f"(PolicyID {policy_id}) — {len(b['rules'])} "
                                   "manual-review rules", "success")
        return True

    def _do_ncm(self, swis, path, offline, prefix):
        benchmarks = load_benchmarks(path)
        info = self._resolve_ncm_where(benchmarks, os.path.basename(path))
        if not isinstance(info, str):   # forced-server info tuple can't reach here
            info = node_where_for(None)
        mode = "heuristic" if self.mode.get().startswith("heuristic") else "manual"
        reports = build_reports(benchmarks, node_where=info, mode=mode,
                                source_path=os.path.basename(path))
        folder = os.path.dirname(path) if os.access(os.path.dirname(path) or ".",
                                                    os.W_OK) else tempfile.gettempdir()
        if offline:
            for report in reports:
                out = write_console_file(report, folder)
                n_rules = sum(len(p["AssignedPolicyRules"])
                              for p in report["AssignedPolicies"])
                self._summary_line(f"SUCCESS {prefix} wrote {os.path.basename(out)} — "
                                   f"{n_rules} rules", "success")
            return True
        for report in reports:
            existing = swis.query(
                "SELECT PolicyReportID FROM Cirrus.PolicyReports WHERE Name = @n",
                {"n": report["Name"]})
            if existing:
                raise SwisError(f"a report named \"{report['Name']}\" already exists — "
                                "delete or rename it first; this tool never overwrites")
        new_ids = []
        partial = False
        for report in reports:
            try:
                new_id, _n_pol, n_rul = import_ncm_report(swis, report, log=self._log)
            except NcmWireError as exc:
                self._summary_line(f"{prefix} {exc}", "warn")
                for rep in reports:
                    self._summary_line(
                        f"{prefix} wrote {os.path.basename(write_console_file(rep, folder))} "
                        "— import it via Compliance → Manage Policy Reports → Import",
                        "warn")
                self._show_issue()
                partial = True
                break
            new_ids.append(new_id)
            self._summary_line(f"SUCCESS {prefix} \"{report['Name']}\" — {n_rul} rules",
                               "success")
        if new_ids:
            swis.invoke("Cirrus.PolicyReports", "StartCaching", new_ids)
            self._log(f"{prefix} compliance caching started for {len(new_ids)} report(s)")
        return not partial


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
    root.withdraw()
    accepted = show_disclaimer(root)
    if not accepted:
        root.destroy()
        return
    root.deiconify()
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

    for alias in ("build", "convert"):
        b = sub.add_parser(alias, help="offline conversion, no server needed: write "
                           "console-importable files (NCM .ncm-report.xml / SCM .scm-profile)")
        add_source_args(b)
        b.add_argument("-o", "--output", help="output file (single-benchmark sources only)")

    imp = sub.add_parser("import", help="import into NCM via SWIS and start caching")
    add_source_args(imp)
    imp.add_argument("--host", required=True)
    imp.add_argument("--user", required=True)
    imp.add_argument("--port", type=int, default=DEFAULT_PORT)
    imp.add_argument("--ca-file", help="CA bundle that signs the SWIS certificate")
    imp.add_argument("--pin-server-cert", action="store_true",
                     help="fetch the server's certificate (the stock self-signed "
                          "'SolarWinds-Orion' one), print its SHA-256 fingerprint, and "
                          "verify this session against exactly that certificate")
    imp.add_argument("--insecure", action="store_true",
                     help="skip TLS verification (lab only)")
    imp.add_argument("--no-cache", action="store_true",
                     help="import but do not start compliance caching")

    args = top.parse_args()
    try:
        {"download": cmd_download, "parse": cmd_parse, "build": cmd_build,
         "convert": cmd_build, "import": cmd_import}[args.cmd](args)
    except (ValueError, OSError, SwisError) as exc:
        sys.exit(redact(f"error: {exc}"))


if __name__ == "__main__":
    main()

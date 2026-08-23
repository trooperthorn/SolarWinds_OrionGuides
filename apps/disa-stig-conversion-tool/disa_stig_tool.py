#!/usr/bin/env python3
"""DISA STIG Conversion Tool — DISA STIG to SolarWinds compliance importer.

Takes a STIG package as DISA publishes it on https://public.cyber.mil/stigs/downloads/
(a zip whose payload is one or more XCCDF benchmark files named ``*-xccdf.xml``; the
``.xsl`` alongside them is only the browser stylesheet) and turns every rule into a
rule in an NCM compliance policy report, delivered to the server through the SWIS
verbs on ``Cirrus.PolicyReports``.

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
import re
import ssl
import sys
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


def parse_benchmark(xml_bytes, source_name):
    """Parse one XCCDF benchmark file into a plain dict."""
    root = ET.fromstring(xml_bytes)
    if not root.tag.endswith("Benchmark"):
        raise ValueError(f"{source_name}: root element is {root.tag}, not an XCCDF Benchmark")

    def text(elem, name):
        child = elem.find(f"{XCCDF_NS}{name}")
        return (child.text or "").strip() if child is not None else ""

    release = ""
    for pt in root.findall(f"{XCCDF_NS}plain-text"):
        if pt.get("id") == "release-info":
            release = (pt.text or "").strip()

    status = root.find(f"{XCCDF_NS}status")
    status_date = status.get("date", "") if status is not None else ""

    rules = []
    for group in root.findall(f"{XCCDF_NS}Group"):
        rule = group.find(f"{XCCDF_NS}Rule")
        if rule is None:
            continue
        description = rule.findtext(f"{XCCDF_NS}description", default="")
        check = rule.find(f"{XCCDF_NS}check")
        check_content = ""
        if check is not None:
            check_content = check.findtext(f"{XCCDF_NS}check-content", default="").strip()
        rules.append({
            "vuln_id": group.get("id", ""),                     # V-215662
            "rule_id": rule.get("id", ""),                      # SV-215662r…_rule
            "stig_id": text(rule, "version"),                   # CISC-ND-000010
            "severity": rule.get("severity", "medium").lower(),
            "title": text(rule, "title"),
            "discussion": extract_tag(description, "VulnDiscussion"),
            "check_content": check_content,
            "fix_text": rule.findtext(f"{XCCDF_NS}fixtext", default="").strip(),
            "ccis": [i.text for i in rule.findall(f"{XCCDF_NS}ident")
                     if i.text and (i.get("system") or "").endswith("/cci")],
        })

    return {
        "source": source_name,
        "benchmark_id": root.get("id", ""),
        "title": root.findtext(f"{XCCDF_NS}title", default="").strip(),
        "version": root.findtext(f"{XCCDF_NS}version", default="").strip(),
        "release": release,
        "status_date": status_date,
        "rules": rules,
    }


def load_benchmarks(path):
    """Load every XCCDF benchmark from a STIG zip, a bare XML file, or a directory."""
    benchmarks = []
    if os.path.isdir(path):
        for dirpath, _dirs, files in os.walk(path):
            for name in sorted(files):
                if name.lower().endswith("-xccdf.xml"):
                    with open(os.path.join(dirpath, name), "rb") as fh:
                        benchmarks.append(parse_benchmark(fh.read(), name))
    elif zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as zf:
            for info in sorted(zf.infolist(), key=lambda i: i.filename):
                base = os.path.basename(info.filename)
                if base.lower().endswith("-xccdf.xml"):
                    benchmarks.append(parse_benchmark(zf.read(info), base))
                elif base.lower().endswith(".zip"):
                    # Compilation zips (SRG-STIG Library) nest one zip per STIG.
                    inner = io.BytesIO(zf.read(info))
                    with zipfile.ZipFile(inner) as izf:
                        for iinfo in sorted(izf.infolist(), key=lambda i: i.filename):
                            ibase = os.path.basename(iinfo.filename)
                            if ibase.lower().endswith("-xccdf.xml"):
                                benchmarks.append(parse_benchmark(izf.read(iinfo), ibase))
    elif path.lower().endswith(".xml"):
        with open(path, "rb") as fh:
            benchmarks.append(parse_benchmark(fh.read(), os.path.basename(path)))
    elif path.lower().endswith(".xsl"):
        # The .xsl is only the display stylesheet; the data lives in the
        # *-xccdf.xml sitting next to it. Resolve that silently.
        folder = os.path.dirname(os.path.abspath(path))
        siblings = [n for n in sorted(os.listdir(folder)) if n.lower().endswith("-xccdf.xml")]
        if not siblings:
            raise ValueError(f"{path}: this is the STIG stylesheet, not the data, and no "
                             "*-xccdf.xml benchmark was found next to it")
        for n in siblings:
            with open(os.path.join(folder, n), "rb") as fh:
                benchmarks.append(parse_benchmark(fh.read(), n))
    else:
        raise ValueError(f"{path}: not a zip, directory, or XCCDF .xml file")
    if not benchmarks:
        raise ValueError(f"{path}: no *-xccdf.xml benchmark found inside")
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
                 config_type="Any", mode="manual"):
    """Assemble the full PolicyReport contract object AddPolicyReport(report, true) takes."""
    policies = []
    for b in benchmarks:
        policy_group = f"{grouping}/{b['benchmark_id']}" if b["benchmark_id"] else grouping
        policies.append({
            "PolicyName": f"{b['title']} V{b['version']} ({b['release']})"[:250],
            "Comments": f"Imported by the DISA STIG Conversion Tool from {b['source']} (benchmark {b['benchmark_id']}, "
                        f"status date {b['status_date']}).",
            "Grouping": grouping,
            # The literal "Criteria:" prefix plus the Where clause is what filters
            # nodes; the console's node-picker QUERY blob is optional state.
            "NodeSelectionString": f"Criteria: Where ( {node_where} )",
            "ConfigTypes": config_type,
            "AssignedPolicyRules": [rule_object(r, policy_group, mode) for r in b["rules"]],
        })

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
        "ReportStatus": "Enabled",
    }


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
    for b in load_benchmarks(args.path):
        counts = {}
        for r in b["rules"]:
            counts[r["severity"]] = counts.get(r["severity"], 0) + 1
        sev = ", ".join(f"{counts[s]} {s}" for s in ("high", "medium", "low") if s in counts)
        print(f"{b['title']}")
        print(f"  benchmark {b['benchmark_id']}  V{b['version']}  {b['release']}  "
              f"(from {b['source']})")
        print(f"  {len(b['rules'])} rules: {sev}")
        if args.rules:
            for r in b["rules"]:
                print(f"    {r['vuln_id']:<10} {r['stig_id']:<18} [{r['severity']:<6}] {r['title']}")
        print()


def make_report_from_args(args):
    benchmarks = load_benchmarks(args.path)
    return build_report(
        benchmarks, name=args.name, grouping=args.grouping,
        node_where=args.node_where, config_type=args.config_type, mode=args.mode,
    )


def cmd_build(args):
    if is_scm_path(args.path):
        info = scan_scm_policy(load_scm_policy(args.path))
        print(f"\"{info['name']}\" is an SCM compliance policy: the YAML file itself is "
              "the import payload — nothing to build.\n"
              "Import it with:  disa_stig_tool.py import <file> …  "
              "(or POST [yamlText] to Invoke/Orion.PolicyEngine.Policy/ImportPolicy)")
        return
    report = make_report_from_args(args)
    out = args.output or (os.path.splitext(os.path.basename(args.path))[0] + ".ncm-report.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    n_rules = sum(len(p["AssignedPolicyRules"]) for p in report["AssignedPolicies"])
    print(f"wrote {out}: report \"{report['Name']}\" — "
          f"{len(report['AssignedPolicies'])} policies, {n_rules} rules")
    print("import it with:  disa_stig_tool.py import <same source> …  "
          "(or POST [report, true] to Invoke/Cirrus.PolicyReports/AddPolicyReport)")


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

    report = make_report_from_args(args)
    existing = swis.query("SELECT PolicyReportID FROM Cirrus.PolicyReports WHERE Name = @n",
                          {"n": report["Name"]})
    if existing:
        sys.exit(f"error: a report named \"{report['Name']}\" already exists "
                 f"({existing[0]['PolicyReportID']}). Rename with --name, or delete it first — "
                 "this tool never overwrites.")

    n_rules = sum(len(p["AssignedPolicyRules"]) for p in report["AssignedPolicies"])
    print(f"importing \"{report['Name']}\" — {len(report['AssignedPolicies'])} policies, "
          f"{n_rules} rules …")
    new_id = swis.invoke("Cirrus.PolicyReports", "AddPolicyReport", report, True)
    if not isinstance(new_id, str) or not new_id:
        sys.exit(f"error: AddPolicyReport did not return a report id (got {new_id!r})")
    rows = swis.query("SELECT Name FROM Cirrus.PolicyReports WHERE PolicyReportID = @id",
                      {"id": new_id})
    if not rows:
        sys.exit(f"error: AddPolicyReport returned {new_id} but the report was not found afterwards")
    print(f"imported: \"{rows[0]['Name']}\" ({new_id})")

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
    p.add_argument("--node-where", default="(Nodes.Vendor = 'Cisco')",
                   help="NCM node-selection Where clause, e.g. \"(Nodes.Vendor = 'Cisco')\"")
    p.add_argument("--config-type", default="Any",
                   help="config type the rules scan: Any, Running, Startup, …")
    p.add_argument("--mode", choices=("manual", "heuristic"), default="manual",
                   help="manual: sentinel patterns, every rule flags for review (default). "
                        "heuristic: seed draft patterns from the STIG check text.")


def main():
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

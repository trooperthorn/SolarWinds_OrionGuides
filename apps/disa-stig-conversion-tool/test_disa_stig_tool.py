"""Offline tests for the DISA STIG Conversion Tool. Standard library only, no network.

    python -m unittest discover -s apps/disa-stig-conversion-tool -p "test_*.py"

The SWIS client is replaced by FakeSwis, an in-memory stand-in for the parts of
Cirrus.PolicyReports and Orion.PolicyEngine.Policy the tool touches. It honours the
same query()/invoke() surface SwisClient exposes, so every command runs end to end
against it. FakeSwis models only what the tests need; it is not evidence of how a
real server behaves (for example, whether AddPolicyRule keeps a submitted RuleId is
Unverified, and the fake simply keeps it).

When Windows PowerShell (or pwsh) is on PATH, the PowerShell edition is also parsed,
its own test script is run, and both editions convert the same inputs so their
RuleIds, PolicyIds, SCM uniqueIds, report names and payloads can be compared.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import http.client
import http.server
import io
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
import uuid
import zipfile
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import disa_stig_tool as tool  # noqa: E402

POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")
PS_TOOL = os.path.join(HERE, "disa_stig_tool.ps1")
PS_TEST = os.path.join(HERE, "test_disa_stig_tool.ps1")
PY_TOOL = os.path.join(HERE, "disa_stig_tool.py")

# The log line contract both editions follow (test_disa_stig_tool.ps1 uses the same
# expression): UTC ISO-8601 with milliseconds and Z, level padded to 5, component
# padded to 6, then the message on one line.
LOG_LINE_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z (DEBUG|INFO |WARN |ERROR) "
    r"(main  |parse |route |scope |build |swis  |import|verify|rollbk|remove|scm   "
    r"|file  |gui   ) .*$")

XXE_XML = (b'<?xml version="1.0" encoding="UTF-8"?>\n'
           b'<!DOCTYPE Benchmark [<!ENTITY xxe SYSTEM "file:///C:/Windows/win.ini">]>\n'
           b'<Benchmark xmlns="http://checklists.nist.gov/xccdf/1.1" id="XXE_STIG">'
           b'<title>&xxe;</title><version>1</version></Benchmark>\n')
DTD_ONLY_XML = (b'<?xml version="1.0"?>\n<!DOCTYPE Benchmark [<!ENTITY a "aaaaaaaaaa">]>\n'
                b'<Benchmark xmlns="http://checklists.nist.gov/xccdf/1.1" id="DTD_STIG">'
                b'<title>&a;</title></Benchmark>\n')
NASTY_VULN = "V-77$(Remove-Item C:\\x)`\"'\u2019"


def read_log_lines(path):
    with open(path, encoding="utf-8", newline="") as fh:
        text = fh.read()
    assert "\r" not in text, "log lines must end in LF only"
    return [line for line in text.split("\n") if line]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_rule(n, severity="medium", check="", oval="", title=None, fix="Configure it."):
    return {
        "vuln_id": f"V-{n}", "rule_id": f"SV-{n}r1_rule", "stig_id": f"TEST-ND-{n:06d}",
        "severity": severity, "title": title or f"Rule {n} must hold.",
        "discussion": f"Discussion {n}.", "check_content": check, "oval_ref": oval,
        "fix_text": fix, "ccis": [f"CCI-{n:06d}"],
    }


def make_benchmark(bid, rules, title=None, source="test-xccdf.xml"):
    return {
        "source": source, "benchmark_id": bid, "title": title or f"Benchmark {bid}",
        "version": "3", "release": "Release: 8 Benchmark Date: 01 Jul 2026",
        "status_date": "2026-07-01", "edition": "manual", "rules": rules,
    }


def xccdf_xml(bid, title, groups):
    """A minimal XCCDF 1.1 benchmark. groups: (vuln, rule, severity, check, oval, fix)."""
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<Benchmark xmlns="http://checklists.nist.gov/xccdf/1.1"'
        + (f' id="{bid}"' if bid else "") + ' xml:lang="en">',
        '  <status date="2026-07-01">accepted</status>',
        f"  <title>{title}</title>",
        '  <plain-text id="release-info">Release: 8 Benchmark Date: 01 Jul 2026</plain-text>',
        "  <version>3</version>",
    ]
    for vuln, rule, severity, check, oval, fix in groups:
        check_xml = ""
        if check:
            check_xml = f'<check system="C-1"><check-content>{check}</check-content></check>'
        elif oval:
            check_xml = (f'<check system="http://oval.mitre.org/XMLSchema/oval-definitions-5">'
                         f'<check-content-ref name="{oval}" href="oval.xml"/></check>')
        parts.append(
            f'  <Group id="{vuln}"><title>SRG-NET-000001</title>'
            f'<Rule id="{rule}" severity="{severity}"><version>CISC-{vuln}</version>'
            f"<title>The device must satisfy {vuln} &amp; keep &quot;quotes&quot;.</title>"
            f"<description>&lt;VulnDiscussion&gt;Why {vuln} matters.&lt;/VulnDiscussion&gt;</description>"
            f'<ident system="http://cyber.mil/cci">CCI-00{vuln[2:]}</ident>'
            f'<fixtext fixref="F-1">{fix}</fixtext>{check_xml}</Rule></Group>')
    parts.append("</Benchmark>")
    return "\n".join(parts)


NDM_GROUPS = [
    ("V-1001", "SV-1001r1_rule", "high",
     "Review the configuration:\nip http server\nIf it is present, this is a finding.", "",
     "Configure:\nno ip http server"),
    ("V-1002", "SV-1002r2_rule", "medium",
     "Verify logging:\nlogging host 10.1.1.*\nIf missing, this is a finding.", "",
     "logging host 10.1.1.5"),
    ("V-1003", "SV-1003r1_rule", "low", "", "oval:mil.disa.stig.cisco:def:1003",
     "Apply the fix."),
]
RTR_GROUPS = [
    ("V-2001", "SV-2001r1_rule", "medium", "Check:\ninterface Loopback0\nOtherwise a finding.",
     "", "interface Loopback0"),
]


def capture():
    """Collect log lines from the tool's log= callbacks."""
    lines = []
    return lines, lines.append


# ---------------------------------------------------------------------------
# FakeSwis: an in-memory NCM / SCM stand-in with the SwisClient surface
# ---------------------------------------------------------------------------

def _n(value):
    return tool._norm_id(value)


class FakeRequestsTimeout(OSError):
    """Shaped like requests.exceptions.ReadTimeout, whose bases end in IOError."""


FakeRequestsTimeout.__module__ = "requests.exceptions"
FakeRequestsTimeout.__name__ = FakeRequestsTimeout.__qualname__ = "ReadTimeout"

DOCUMENTED_400S = ("HTTP 400 from AddPolicyRule\nValue cannot be null. Parameter name: input",
                   "HTTP 400 from AddPolicy\nVerb Cirrus.PolicyReports.AddPolicy cannot "
                   "unpackage parameter 0")
UNDOCUMENTED_400 = "HTTP 400 from AddPolicyRule\nRule name must not be empty."
FORBIDDEN_403 = "HTTP 403 from Invoke/Cirrus.PolicyReports/StartCaching\nAccess is denied."


class FakeSwis:
    """In-memory Cirrus.PolicyReports / Orion.PolicyEngine.Policy.

    Knobs for the failure paths (all off by default):
      fail[verb] = exception, or (exception, n) to let n calls succeed first, or a list
                   with one entry per call (None lets that call through); "query"
                   fails queries the same way
      results[verb] = a value returned instead of the modelled one (e.g. a string)
      reject_items: every per-item AddPolicyRule is refused with a documented 400
      nested: None (the nested console-XML AddPolicyReport is refused with a documented
              400), "report-only" (it stores only the report row, as one server was
              observed doing), or "full" (it stores the whole tree)
      in_ids_broken: every IN @ids query returns no rows
      drop_rule_on_readback: GetPolicyReport leaves the last rule of each policy out
    """

    def __init__(self, tree_has_policy_ids=True):
        self.reports = {}      # id -> {"Name", "policies": [ids], "ReportStatus": bool}
        self.policies = {}     # id -> {"PolicyName", "rules": [ids]}
        self.rules = {}        # id -> RuleName
        self.scm = []          # SCM policy rows
        self.calls = []
        self.tree_has_policy_ids = tree_has_policy_ids
        self.fail_add_report = set()   # report names whose AddPolicyReport fails (HTTP 500)
        self.reject_all_after = None   # after N reports exist, every write is HTTP 400
        self.next_scm_id = 100
        self.fail = {}
        self.results = {}
        self.reject_items = False
        self.nested = None
        self.in_ids_broken = False
        self.drop_rule_on_readback = False

    # -- helpers ------------------------------------------------------------
    def add_report(self, name, policies, report_id=None):
        rid = report_id or str(uuid.uuid4())
        self.reports[rid] = {"Name": name, "policies": list(policies), "ReportStatus": True}
        return rid

    def add_policy(self, pid, rules, name=None):
        self.policies[pid] = {"PolicyName": name or f"Policy {pid}", "rules": list(rules)}
        for r in rules:
            self.rules.setdefault(r, f"Rule {r}")

    def verbs(self, name=None):
        out = [c for c in self.calls if c[0] == "invoke"]
        return [c for c in out if c[1] == name] if name else out

    def _rejecting(self):
        return self.reject_all_after is not None and len(self.reports) >= self.reject_all_after

    def _maybe_fail(self, key):
        spec = self.fail.get(key)
        if spec is None:
            return
        if isinstance(spec, list):          # one entry per call; None lets that call through
            exc = spec.pop(0) if spec else None
            if exc is not None:
                raise exc
            return
        exc, skip = spec if isinstance(spec, tuple) else (spec, 0)
        if skip > 0:
            self.fail[key] = (exc, skip - 1)
            return
        raise exc

    # -- SwisClient surface -------------------------------------------------
    def query(self, swql, parameters=None):
        self.calls.append(("query", swql, parameters))
        self._maybe_fail("query")
        p = parameters or {}
        ids = {_n(i) for i in p.get("ids", [])}
        if "IN @ids" in swql and self.in_ids_broken:
            return []
        if swql == "SELECT TOP 1 PolicyRuleID FROM Cirrus.PolicyRules":
            return [{"PolicyRuleID": k} for k in list(self.rules)[:1]]
        if swql == "SELECT TOP 1 PolicyID FROM Cirrus.Policies":
            return [{"PolicyID": k} for k in list(self.policies)[:1]]
        if "FROM Cirrus.PolicyReports WHERE Name = @n" in swql:
            return [{"PolicyReportID": k, "Name": v["Name"], "Grouping": "DISA STIG"}
                    for k, v in self.reports.items() if v["Name"] == p["n"]]
        if "FROM Cirrus.PolicyReports WHERE PolicyReportID IN @ids" in swql:
            return [{"PolicyReportID": k, "Name": v["Name"], "ReportStatus": v["ReportStatus"]}
                    for k, v in self.reports.items() if _n(k) in ids]
        if "FROM Cirrus.PolicyRules WHERE PolicyRuleID IN @ids" in swql:
            return [{"PolicyRuleID": k} for k in self.rules if _n(k) in ids]
        if "FROM Cirrus.Policies WHERE PolicyID IN @ids" in swql:
            return [{"PolicyID": k} for k in self.policies if _n(k) in ids]
        if "FROM Cirrus.PolicyAssignment WHERE PolicyReportID IN @ids" in swql:
            return [{"PolicyID": pid} for k, v in self.reports.items() if _n(k) in ids
                    for pid in v["policies"]]
        if "FROM Cirrus.PolicyAssignment WHERE PolicyID IN @ids" in swql:
            return [{"PolicyReportID": k, "PolicyID": pid} for k, v in self.reports.items()
                    for pid in v["policies"] if _n(pid) in ids]
        if "FROM Cirrus.PolicyRuleAssignment WHERE PolicyID IN @ids" in swql:
            return [{"PolicyRuleID": r} for k, v in self.policies.items() if _n(k) in ids
                    for r in v["rules"]]
        if "FROM Cirrus.PolicyRuleAssignment WHERE PolicyRuleID IN @ids" in swql:
            return [{"PolicyID": k, "PolicyRuleID": r} for k, v in self.policies.items()
                    for r in v["rules"] if _n(r) in ids]
        if "FROM Orion.PolicyEngine.Policy WHERE" in swql:
            return [row for row in self.scm
                    if row["Name"] == p.get("n") or row["UniqueId"] == p.get("u")]
        if "FROM Orion.PolicyEngine.Rule WHERE PolicyID = @p" in swql:
            return [{"N": next((r["Rules"] for r in self.scm if r["PolicyID"] == p["p"]), 0)}]
        raise AssertionError(f"FakeSwis has no answer for: {swql}")

    def invoke(self, entity, verb, *args):
        self.calls.append(("invoke", verb, args))
        self._maybe_fail(verb)
        result = getattr(self, "_" + verb)(*args)
        return self.results.get(verb, result)

    # -- Cirrus.PolicyReports verbs ------------------------------------------
    def _AddPolicyRule(self, rule):
        if self._rejecting() or self.reject_items or not isinstance(rule, dict):
            raise tool.SwisError(DOCUMENTED_400S[0])
        self.rules[rule["RuleId"]] = rule["RuleName"]
        return f'"{rule["RuleId"]}"'

    def _AddPolicy(self, policy, import_flag):
        if self._rejecting():
            raise tool.SwisError(DOCUMENTED_400S[1])
        pid = str(uuid.uuid4())
        self.add_policy(pid, policy["AssignedRulesList"], policy["PolicyName"])
        return pid

    def _AddPolicyReport(self, report, import_flag):
        if isinstance(report, str) and self.nested and not self._rejecting():
            return self._nested_import(report)
        if self._rejecting() or not isinstance(report, dict):
            raise tool.SwisError("HTTP 400 from AddPolicyReport\ncannot unpackage parameter 0")
        if report["Name"] in self.fail_add_report:
            raise tool.SwisError("HTTP 500 from AddPolicyReport\nsimulated server error")
        return self.add_report(report["Name"], report["AssignedPoliciesList"])

    def _nested_import(self, xml_text):
        root = tool.ET.fromstring(xml_text)
        policies = []
        if self.nested == "full":
            for pol in root.iter("Policy"):
                pid = str(uuid.uuid4())
                rule_ids = []
                for rule in pol.iter("PolicyRule"):
                    self.rules[rule.findtext("RuleId")] = rule.findtext("RuleName")
                    rule_ids.append(rule.findtext("RuleId"))
                self.add_policy(pid, rule_ids, pol.findtext("PolicyName"))
                policies.append(pid)
        return self.add_report(root.findtext("Name"), policies)

    def _GetPolicyReport(self, report_id, export_flag):
        rep = self.reports.get(report_id)
        if rep is None:
            return None
        pols = []
        for pid in rep["policies"]:
            pol = self.policies.get(pid, {"PolicyName": "?", "rules": []})
            rules = pol["rules"][:-1] if self.drop_rule_on_readback else pol["rules"]
            entry = {"PolicyName": pol["PolicyName"],
                     "AssignedPolicyRules": [{"RuleId": r, "RuleName": self.rules.get(r)}
                                             for r in rules]}
            if self.tree_has_policy_ids:
                entry["PolicyId"] = pid
            pols.append(entry)
        return {"Name": rep["Name"], "AssignedPolicies": pols}

    def _DeletePolicyReports(self, ids, delete_children):
        for i in ids:
            self.reports.pop(i, None)
        return len(ids)

    def _DeletePolicies(self, ids, delete_children):
        for i in ids:
            self.policies.pop(i, None)
        return len(ids)

    def _DeletePolicyRules(self, ids):
        for i in ids:
            self.rules.pop(i, None)
        return len(ids)

    def _StartCaching(self, ids):
        return True     # the contract declares a boolean result

    def _UpdateReportStatus(self, status, ids):
        for i in ids:
            if i in self.reports:
                self.reports[i]["ReportStatus"] = status != "Disabled"
        return None

    # -- Orion.PolicyEngine.Policy ------------------------------------------
    def _ImportPolicy(self, yaml_text):
        info = tool.scan_scm_policy(yaml_text)
        self.next_scm_id += 1
        self.scm.append({"PolicyID": self.next_scm_id, "Name": info["name"],
                         "UniqueId": info["uniqueId"], "Rules": len(info["rules"])})
        return self.next_scm_id


def import_args(path, **overrides):
    values = dict(path=path, name=None, grouping="DISA STIG", target="auto", node_where="auto",
                  config_type="Any", mode="manual", disabled=False, no_cache=False,
                  no_rollback=False)
    values.update(overrides)
    return argparse.Namespace(**values)


class TempDirTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="disa-stig-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def write(self, name, data):
        path = os.path.join(self.tmp, name)
        mode = "wb" if isinstance(data, bytes) else "w"
        kwargs = {} if isinstance(data, bytes) else {"encoding": "utf-8", "newline": ""}
        with open(path, mode, **kwargs) as fh:
            fh.write(data)
        return path

    def router_zip(self, name="U_Test_Cisco_Router_STIG.zip"):
        path = os.path.join(self.tmp, name)
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("a_ndm/a_ndm-xccdf.xml",
                        xccdf_xml("Test_Router_NDM_STIG", "Test Cisco Router NDM STIG", NDM_GROUPS))
            zf.writestr("b_rtr/b_rtr-xccdf.xml",
                        xccdf_xml("Test_Router_RTR_STIG", "Test Cisco Router RTR STIG", RTR_GROUPS))
            zf.writestr("a_ndm/STIG_unclass.xsl", "<xsl:stylesheet/>")
        return path


# ---------------------------------------------------------------------------
# 0. Console robustness and ASCII help
# ---------------------------------------------------------------------------

class HelpAndConsoleTests(unittest.TestCase):
    def test_every_help_screen_is_ascii(self):
        parser = tool.build_parser()
        screens = [parser.format_help()]
        sub = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
        screens += [p.format_help() for p in sub.choices.values()]
        for text in screens:
            bad = sorted({ch for ch in text if ord(ch) > 127})
            self.assertEqual(bad, [], f"non-ASCII characters in help: {bad}")

    def test_configure_console_streams_prevents_encode_errors(self):
        raw = io.BytesIO()
        stream = io.TextIOWrapper(raw, encoding="cp1252", errors="strict")
        with self.assertRaises(UnicodeEncodeError):
            stream.write("→—")
            stream.flush()
        raw = io.BytesIO()
        stream = io.TextIOWrapper(raw, encoding="cp1252", errors="strict")
        tool.configure_console_streams([stream, None])
        stream.write("arrow → dash —\n")
        stream.flush()
        self.assertIn("→".encode("utf-8"), raw.getvalue())

    def test_help_runs_on_a_cp1252_console(self):
        env = dict(os.environ, PYTHONIOENCODING="cp1252:strict")
        script = os.path.join(HERE, "disa_stig_tool.py")
        for cmd in ([], ["download"], ["parse"], ["build"], ["convert"], ["import"],
                    ["test"], ["remove"]):
            result = subprocess.run([sys.executable, script, *cmd, "--help"], env=env,
                                    capture_output=True, timeout=120)
            self.assertEqual(result.returncode, 0, (cmd, result.stderr[-400:]))

    def test_errorlevel_names_constant_removed(self):
        self.assertFalse(hasattr(tool, "ERRORLEVEL_NAMES"))
        self.assertEqual(tool.SEVERITY_TO_ERRORLEVEL, {"high": 2, "medium": 1, "low": 0})


# ---------------------------------------------------------------------------
# 1. remove: report, then unshared policies, then unshared rules
# ---------------------------------------------------------------------------

class RemoveTests(unittest.TestCase):
    def shared_server(self, tree_has_policy_ids=True):
        # Report A: p1 (r1, r2) and p2 (r3). Report B shares p2 and has p3 (r2, r4).
        fake = FakeSwis(tree_has_policy_ids)
        fake.add_policy("p1", ["r1", "r2"])
        fake.add_policy("p2", ["r3"])
        fake.add_policy("p3", ["r2", "r4"])
        fake.add_report("Report A", ["p1", "p2"], "rA")
        fake.add_report("Report B", ["p2", "p3"], "rB")
        return fake

    def run_remove(self, fake, **flags):
        args = argparse.Namespace(name="Report A", dry_run=False, yes=False,
                                  delete_children=False)
        for k, v in flags.items():
            setattr(args, k, v)
        out = io.StringIO()
        with mock.patch.object(tool, "connect", return_value=fake), \
                contextlib.redirect_stdout(out):
            tool.cmd_remove(args)
        return out.getvalue()

    def test_plan_keeps_shared_objects(self):
        for tree_ids in (True, False):
            with self.subTest(tree_has_policy_ids=tree_ids):
                plan = tool.plan_ncm_removal(self.shared_server(tree_ids), ["rA"], log=lambda m: None)
                self.assertEqual(plan["delete_policies"], ["p1"])
                self.assertEqual(sorted(plan["keep_policies"]), ["p2"])
                self.assertEqual(plan["delete_rules"], ["r1"])
                self.assertEqual(sorted(plan["keep_rules"]), ["r2", "r3"])

    def test_remove_order_and_flags(self):
        fake = self.shared_server()
        out = self.run_remove(fake, yes=True)
        deletes = [(c[1], c[2]) for c in fake.verbs() if c[1].startswith("Delete")]
        self.assertEqual(deletes, [
            ("DeletePolicyReports", (["rA"], False)),
            ("DeletePolicies", (["p1"], False)),
            ("DeletePolicyRules", (["r1"],)),
        ])
        self.assertNotIn(True, [arg for _v, args in deletes for arg in args],
                         "deleteChildren=true must never be sent")
        self.assertEqual(set(fake.reports), {"rB"})
        self.assertEqual(set(fake.policies), {"p2", "p3"})
        self.assertEqual(set(fake.rules), {"r2", "r3", "r4"})
        self.assertIn("kept policy p2", out)
        self.assertIn("kept rule r2", out)
        self.assertIn("deleted 1 report(s), 1 policy/policies and 1 rule(s)", out)

    def test_dry_run_deletes_nothing(self):
        fake = self.shared_server()
        out = self.run_remove(fake, dry_run=True)
        self.assertEqual([c for c in fake.verbs() if c[1].startswith("Delete")], [])
        self.assertIn("would delete", out)
        self.assertIn("dry run: nothing was deleted", out)

    def test_refuses_without_yes(self):
        fake = self.shared_server()
        with self.assertRaises(SystemExit):
            self.run_remove(fake)
        self.assertEqual([c for c in fake.verbs() if c[1].startswith("Delete")], [])

    def test_delete_children_flag_is_ignored(self):
        fake = self.shared_server()
        out = self.run_remove(fake, yes=True, delete_children=True)
        self.assertIn("deprecated and ignored", out)
        self.assertIn("p2", fake.policies)


# ---------------------------------------------------------------------------
# 2. Seeds (Python is the reference; the PowerShell parity test is below)
# ---------------------------------------------------------------------------

class SeedTests(unittest.TestCase):
    def test_seeds_use_benchmark_id_else_title(self):
        with_id = make_benchmark("Test_NDM", [make_rule(1)], title="Some Title")
        no_id = make_benchmark("", [make_rule(1)], title="Some Title")
        pid = tool.build_reports([with_id])[0]["AssignedPolicies"][0]["PolicyId"]
        self.assertEqual(pid, str(uuid.uuid5(uuid.NAMESPACE_URL, "stig2ncm-policy:Test_NDM")))
        pid = tool.build_reports([no_id])[0]["AssignedPolicies"][0]["PolicyId"]
        self.assertEqual(pid, str(uuid.uuid5(uuid.NAMESPACE_URL, "stig2ncm-policy:Some Title")))
        self.assertIn(f"uniqueId: {uuid.uuid5(uuid.NAMESPACE_URL, 'stig2ncm-scm:Test_NDM')}\n",
                      tool.xccdf_to_scm_yaml(with_id))
        self.assertIn(f"uniqueId: {uuid.uuid5(uuid.NAMESPACE_URL, 'stig2ncm-scm:Some Title')}\n",
                      tool.xccdf_to_scm_yaml(no_id))


# ---------------------------------------------------------------------------
# 3/4. SCM routing: extension, legacy .scm-profile, JSON collection profiles, CRLF
# ---------------------------------------------------------------------------

POLICY_LF = ("!policy\nname: 'IIS Test Policy'\nuniqueId: 81d7a7f2-d976-486d-a6b9-39f2298c2348\n"
             "pluginName: SCM\nrules:\n- displayId: V-1\n  severity: High\n")
PROFILE_JSON = json.dumps({
    "name": "Scheduled Task Profile", "uniqueId": "ce741ac1-d041-49cb-bb86-613ef130b6bf",
    "version": None, "profileElements": [{"type": "powershell", "settings": json.dumps(
        {"path": 'Get-ScheduledTask | Where-Object { $_.TaskPath -notlike "\\Microsoft\\*" }'})}],
})


class ScmRoutingTests(TempDirTest):
    def test_scan_handles_lf_and_crlf(self):
        for text in (POLICY_LF, POLICY_LF.replace("\n", "\r\n")):
            info = tool.scan_scm_policy(text)
            self.assertEqual(info["uniqueId"], "81d7a7f2-d976-486d-a6b9-39f2298c2348")
            self.assertEqual(info["name"], "IIS Test Policy")

    def test_crlf_uniqueid_collision_is_caught(self):
        fake = FakeSwis()
        fake.scm.append({"PolicyID": 7, "Name": "Other Name",
                         "UniqueId": "81d7a7f2-d976-486d-a6b9-39f2298c2348", "Rules": 1})
        with self.assertRaisesRegex(tool.SwisError, "same uniqueId"):
            tool.import_scm_policy(fake, POLICY_LF.replace("\n", "\r\n"))
        self.assertEqual(fake.verbs("ImportPolicy"), [])

    def test_new_extension_and_legacy_profile_extension(self):
        new = self.write("x" + tool.SCM_POLICY_SUFFIX, POLICY_LF)
        self.assertTrue(tool.is_scm_path(new))
        self.assertEqual(tool.load_scm_policy(new), POLICY_LF)
        self.assertEqual(tool.file_module(new), "SCM")

        legacy = self.write("old.scm-profile", POLICY_LF.replace("\n", "\r\n"))
        lines, log = capture()
        self.assertIn("!policy", tool.load_scm_policy(legacy, log=log))
        self.assertTrue(any("older build" in line for line in lines))

    def test_utf16_policy_yaml_is_read(self):
        path = self.write("exported.yaml", b"\xff\xfe" + POLICY_LF.encode("utf-16-le"))
        self.assertEqual(tool.load_scm_policy(path), POLICY_LF)

    def test_json_collection_profile_is_refused(self):
        for raw in (b"\xff\xfe" + PROFILE_JSON.encode("utf-16-le"), PROFILE_JSON.encode()):
            path = self.write("Scheduled_Task_Profile.scm-profile", raw)
            with self.assertRaisesRegex(ValueError, "collection profile"):
                tool.load_scm_policy(path)
            with self.assertRaisesRegex(ValueError, "ImportProfile"):
                tool.file_module(path)

    def test_import_refuses_profile_before_any_swis_call(self):
        path = self.write("p.scm-profile", b"\xff\xfe" + PROFILE_JSON.encode("utf-16-le"))
        fake = FakeSwis()
        with mock.patch.object(tool, "connect", return_value=fake), \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, "collection profile"):
                tool.cmd_import(import_args(path))
        self.assertEqual(fake.calls, [])

    def test_convert_writes_scm_policy_yaml(self):
        xml = self.write("U_MS_Windows_Server_Test-xccdf.xml",
                         xccdf_xml("Windows_Server_Test_STIG", "Microsoft Windows Server Test STIG",
                                   RTR_GROUPS))
        cwd = os.getcwd()
        os.chdir(self.tmp)
        self.addCleanup(os.chdir, cwd)
        with contextlib.redirect_stdout(io.StringIO()):
            tool.cmd_build(import_args(xml, output=None))
        written = [f for f in os.listdir(self.tmp) if f.endswith(tool.SCM_POLICY_SUFFIX)]
        self.assertEqual(written, ["U_MS_Windows_Server_Test-xccdf.Windows_Server_Test_STIG.scm-policy.yaml"])
        self.assertFalse([f for f in os.listdir(self.tmp) if f.endswith(".scm-profile")])
        with open(os.path.join(self.tmp, written[0]), encoding="utf-8") as fh:
            self.assertTrue(fh.read().startswith("!policy\n"))


# ---------------------------------------------------------------------------
# 6/7. Multi-report runs and rollback scope
# ---------------------------------------------------------------------------

class ImportFlowTests(TempDirTest):
    def two_reports(self):
        b1 = make_benchmark("NDM", [make_rule(1), make_rule(2)])
        b2 = make_benchmark("RTR", [make_rule(3), make_rule(4)])
        return tool.build_reports([b1, b2], name="Pkg")

    def run_import(self, fake, path, **overrides):
        out = io.StringIO()
        with mock.patch.object(tool, "connect", return_value=fake), \
                contextlib.redirect_stdout(out):
            try:
                tool.cmd_import(import_args(path, **overrides))
            finally:
                self.output = out.getvalue()

    def test_wire_failure_on_second_report_keeps_first(self):
        path = self.router_zip()
        fake = FakeSwis()
        fake.reject_all_after = 1      # the first report lands, then every format is refused
        cwd = os.getcwd()
        os.chdir(self.tmp)
        self.addCleanup(os.chdir, cwd)
        with self.assertRaises(SystemExit):
            self.run_import(fake, path)
        self.assertEqual(len(fake.reports), 1)
        first_id = next(iter(fake.reports))
        self.assertEqual(fake.verbs("StartCaching"), [("invoke", "StartCaching", ([first_id],))])
        written = sorted(f for f in os.listdir(self.tmp) if f.endswith(".ncm-report.xml"))
        self.assertEqual(written, ["U_Test_Cisco_Router_STIG_-_Test_Router_RTR_STIG.ncm-report.xml"])
        self.assertIn("1 of 2 report(s) were imported before the failure", self.output)

    def test_server_error_on_second_report_still_disables_first(self):
        path = self.router_zip()
        fake = FakeSwis()
        fake.fail_add_report.add("U_Test_Cisco_Router_STIG - Test_Router_RTR_STIG")
        with self.assertRaisesRegex(tool.SwisError, "simulated server error"):
            self.run_import(fake, path, disabled=True)
        self.assertEqual(len(fake.reports), 1)
        first_id = next(iter(fake.reports))
        self.assertEqual(fake.verbs("UpdateReportStatus"),
                         [("invoke", "UpdateReportStatus", ("Disabled", [first_id]))])
        self.assertFalse(fake.reports[first_id]["ReportStatus"])
        self.assertIn("imported Disabled and not cached", self.output)
        self.assertEqual(fake.verbs("StartCaching"), [])
        # the failed report's rules were rolled back; the first report's survive
        self.assertEqual(sorted(fake.rules.values()),
                         sorted(r["RuleName"] for r in tool.build_reports(
                             tool.load_benchmarks(path))[0]["AssignedPolicies"][0]["AssignedPolicyRules"]))

    def test_no_cache_and_status_readback(self):
        fake = FakeSwis()
        lines, log = capture()
        self.assertTrue(tool.finish_ncm_imports(fake, ["x"], no_cache=True, log=log))
        self.assertEqual(fake.verbs(), [])
        fake.add_report("still on", [], "y")
        fake._UpdateReportStatus = lambda status, ids: None   # server ignores the change
        self.assertFalse(tool.finish_ncm_imports(fake, ["y"], disabled=True, log=log))
        self.assertTrue(any("still enabled" in line for line in lines))

    def test_rollback_skips_preexisting_rules(self):
        report = self.two_reports()[0]
        rules = report["AssignedPolicies"][0]["AssignedPolicyRules"]
        fake = FakeSwis()
        earlier = rules[0]["RuleId"]
        fake.add_policy("earlier-policy", [earlier])   # an earlier import of the same release
        fake.add_report("Earlier import", ["earlier-policy"], "earlier-report")
        fake.fail_add_report.add(report["Name"])
        lines, log = capture()
        with self.assertRaises(tool.SwisError):
            tool.import_ncm_report(fake, report, log=log)
        deleted = [c[2][0] for c in fake.verbs("DeletePolicyRules")]
        self.assertEqual(deleted, [[rules[1]["RuleId"]]])
        self.assertIn(earlier, fake.rules, "the earlier import's rule must survive the rollback")
        self.assertTrue(any(f"skipped rule {earlier}" in line for line in lines))
        self.assertTrue(any("already exist on the server" in line for line in lines))

    def test_rollback_deletes_everything_it_created(self):
        report = self.two_reports()[0]
        fake = FakeSwis()
        fake.fail_add_report.add(report["Name"])
        with self.assertRaises(tool.SwisError):
            tool.import_ncm_report(fake, report, log=lambda m: None)
        self.assertEqual(fake.rules, {})
        self.assertEqual(fake.policies, {})


# ---------------------------------------------------------------------------
# 7b. Import reliability: transport errors, 400 classification, nested fallback,
#     permissions, the IN @ids sanity probe and read-back comparison
# ---------------------------------------------------------------------------

class ImportReliabilityTests(TempDirTest):
    def report(self, n_rules=2, bid="NDM", name="Pkg"):
        bench = make_benchmark(bid, [make_rule(i) for i in range(1, n_rules + 1)])
        return tool.build_reports([bench], name=name)[0]

    def run_import(self, fake, path=None, **overrides):
        path = path or self.router_zip()
        cwd = os.getcwd()
        os.chdir(self.tmp)
        self.addCleanup(os.chdir, cwd)
        out = io.StringIO()
        with mock.patch.object(tool, "connect", return_value=fake), \
                contextlib.redirect_stdout(out):
            try:
                tool.cmd_import(import_args(path, **overrides))
            finally:
                self.output = out.getvalue()

    def console_files(self):
        return sorted(f for f in os.listdir(self.tmp) if f.endswith(".ncm-report.xml"))

    def open_log(self, level="info"):
        path = os.path.join(self.tmp, "reliability.log")
        self.addCleanup(tool.close_logging)
        tool.setup_logging(path, level)
        return path

    # -- item 9: every exception, transport errors wrapped ---------------------
    def test_transport_errors_become_swis_errors_with_the_original_message(self):
        for exc in (TimeoutError("The read operation timed out"),
                    FakeRequestsTimeout("Read timed out. (read timeout=300)"),
                    http.client.RemoteDisconnected("Remote end closed connection"),
                    json.JSONDecodeError("Expecting value", "<html>", 0)):
            with self.subTest(type(exc).__name__):
                fake = FakeSwis()
                fake.fail["AddPolicyRule"] = exc
                with self.assertRaises(tool.SwisError) as ctx:
                    tool.logged(fake).invoke("Cirrus.PolicyReports", "AddPolicyRule",
                                             {"RuleName": "r", "RuleId": "x"})
                self.assertIn(f"{type(exc).__name__}: {exc}", str(ctx.exception))
                self.assertIs(ctx.exception.__cause__, exc)

    def test_swis_client_wraps_timeouts_and_bodies_that_are_not_json(self):
        client = tool.SwisClient("orion.example.com", "u", "Pw-Reliability-8812")

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return b"<html>proxy error</html>"

        with mock.patch.object(tool.urllib.request, "urlopen",
                               side_effect=TimeoutError("The read operation timed out")):
            with self.assertRaisesRegex(tool.SwisError,
                                        "transport error .*TimeoutError: The read operation"):
                client.query("SELECT TOP 1 EngineVersion FROM Orion.Engines")
        with mock.patch.object(tool.urllib.request, "urlopen", return_value=Response()):
            with self.assertRaisesRegex(tool.SwisError, "JSONDecodeError"):
                client.invoke("Cirrus.PolicyReports", "GetPolicyReport", tool.NIL_GUID, False)

    def test_timeout_mid_import_rolls_back_and_is_recorded(self):
        report = self.report(3)
        fake = FakeSwis()
        fake.fail["AddPolicy"] = TimeoutError("timed out")
        lines, log = capture()
        imported, failure, remaining = tool.import_ncm_reports(tool.logged(fake), [report], log=log)
        self.assertEqual(imported, [])
        self.assertIsInstance(failure, tool.SwisError)
        self.assertIn("TimeoutError: timed out", str(failure))
        self.assertEqual(remaining, [report])
        self.assertEqual(fake.rules, {}, "the three rules were rolled back")
        self.assertTrue(any("outcome of the failed call is unknown" in line for line in lines))
        # An unwrapped client raising a raw exception is rolled back and recorded too.
        fake = FakeSwis()
        fake.fail["AddPolicy"] = TimeoutError("timed out")
        _imported, failure, _remaining = tool.import_ncm_reports(fake, [report], log=lambda m: None)
        self.assertIsInstance(failure, TimeoutError)
        self.assertEqual(fake.rules, {})

    def test_rollback_carries_on_after_a_failing_delete(self):
        report = self.report(2)
        fake = FakeSwis()
        fake.fail_add_report.add(report["Name"])
        fake.fail["DeletePolicies"] = FakeRequestsTimeout("Read timed out.")
        lines, log = capture()
        with self.assertRaises(tool.SwisError):
            tool.import_ncm_report(fake, report, log=log)
        self.assertEqual(fake.rules, {}, "rules are still deleted after the policy delete failed")
        self.assertEqual(len(fake.policies), 1)
        self.assertTrue(any("DeletePolicies failed, clean up by hand - ReadTimeout" in line
                            for line in lines))

    def test_a_string_read_back_is_a_verification_failure(self):
        report = self.report(2)
        fake = FakeSwis()
        fake.results["GetPolicyReport"] = "<PolicyReport />"
        with self.assertRaisesRegex(tool.NcmVerificationError,
                                    "instead of a readable report object"):
            tool.import_ncm_report(fake, report, log=lambda m: None)
        self.assertEqual((fake.reports, fake.policies, fake.rules), ({}, {}, {}))

    # -- verification gap: counts and names compared ---------------------------
    def test_partial_tree_fails_verification_and_rolls_back(self):
        report = self.report(3)
        fake = FakeSwis()
        fake.drop_rule_on_readback = True
        with self.assertRaises(tool.NcmVerificationError) as ctx:
            tool.import_ncm_report(fake, report, log=lambda m: None)
        msg = str(ctx.exception)
        self.assertIn("rules: expected 3, stored 2", msg)
        self.assertIn('(missing "V-3 [medium] Rule 3 must hold.")', msg)
        self.assertIn("WebDownloader", msg)
        self.assertNotIn("WebUploader or higher", msg)
        self.assertEqual((fake.reports, fake.policies, fake.rules), ({}, {}, {}))

    def test_compare_report_trees(self):
        expected = [("P", ["a", "b", "c"]), ("Q", ["d"])]
        self.assertEqual(tool.compare_report_trees(expected, expected), [])
        self.assertEqual(tool.compare_report_trees(expected, [("P", ["a", "b"])]), [
            "policies: expected 2, stored 1", "rules: expected 4, stored 2",
            'policy "P": expected 3 rules, stored 2 (missing "c")', 'policy "Q" missing'])
        self.assertEqual(tool.compare_report_trees([("P", ["a", "b"])], [("P", ["b", "x"])]),
                         ['policy "P": expected 2 rules, stored 2 (missing "a")'])
        self.assertIsNone(tool.read_back_tree({"AssignedPoliciesList": ["x"]}))
        self.assertEqual(tool.read_back_tree({}), [])
        self.assertIsNone(tool.read_back_tree("<PolicyReport />"))
        self.assertIsNone(tool.read_back_tree({"AssignedPolicies": ["x"]}))

    # -- item 13: only the documented 400s mean "try the next wire format" -----
    def test_only_documented_400s_are_wire_rejections(self):
        for text in DOCUMENTED_400S:
            self.assertTrue(tool.is_wire_rejection(tool.SwisError(text)), text)
        for text in (UNDOCUMENTED_400, FORBIDDEN_403,
                     "HTTP 500 from AddPolicy\ncannot unpackage parameter 0",
                     "HTTP 409 from AddPolicyRule\nValue cannot be null. Parameter name: input",
                     "HTTP 400 from AddPolicyRule\nValue cannot be null. (Parameter 'input')",
                     "transport error calling x: TimeoutError: timed out"):
            self.assertFalse(tool.is_wire_rejection(text), text)

    def test_other_errors_stop_the_report_without_console_files(self):
        for message in (UNDOCUMENTED_400, "HTTP 401 from AddPolicyRule\nUnauthorized",
                        "HTTP 403 from AddPolicyRule\nAccess is denied.",
                        "HTTP 409 from AddPolicyRule\nConflict",
                        "HTTP 500 from AddPolicyRule\nObject reference not set"):
            with self.subTest(message.split("\n")[0]):
                fake = FakeSwis()
                fake.fail["AddPolicyRule"] = tool.SwisError(message)
                with self.assertRaises(tool.SwisError) as ctx:
                    self.run_import(fake)
                self.assertIn(message.split("\n")[1], str(ctx.exception))
                self.assertEqual(len(fake.verbs("AddPolicyRule")), 1, "no other format tried")
                self.assertEqual(fake.verbs("AddPolicyReport"), [], "no nested fallback")
                self.assertEqual(self.console_files(), [])
                self.assertIn("not imported:", self.output)

    def test_undocumented_400_mid_import_rolls_back_without_console_files(self):
        fake = FakeSwis()
        fake.fail["AddPolicy"] = tool.SwisError("HTTP 400 from AddPolicy\nPolicy name too long")
        with self.assertRaisesRegex(tool.SwisError, "Policy name too long"):
            self.run_import(fake)
        self.assertEqual((fake.reports, fake.rules), ({}, {}))
        self.assertEqual(self.console_files(), [])

    # -- item 12: the nested fallback cleans up after a failed verification ----
    def test_nested_report_row_only_is_deleted_then_console_files_written(self):
        fake = FakeSwis()
        fake.reject_items = True
        fake.nested = "report-only"
        with self.assertRaises(SystemExit):
            self.run_import(fake)
        self.assertEqual(fake.reports, {}, "the bare report rows were deleted")
        # The run stops at the first failed report, so one nested row was created and
        # deleted, and both reports are written out for the console.
        self.assertEqual(len(fake.verbs("DeletePolicyReports")), 1)
        self.assertEqual(len(self.console_files()), 2)
        self.assertIn("accepted, but verification failed", self.output)
        self.assertEqual(fake.verbs("StartCaching"), [])

    def test_nested_timeout_stops_without_console_files(self):
        fake = FakeSwis()
        fake.reject_items = True
        fake.fail["AddPolicyReport"] = TimeoutError("timed out")
        with self.assertRaisesRegex(tool.SwisError, "TimeoutError: timed out"):
            self.run_import(fake)
        self.assertIn("outcome of the failed AddPolicyReport is unknown", self.output)
        self.assertEqual(self.console_files(), [])

    def test_nested_full_tree_verifies_and_is_cached(self):
        fake = FakeSwis()
        fake.reject_items = True
        fake.nested = "full"
        self.run_import(fake)
        self.assertEqual(len(fake.reports), 2)
        self.assertEqual(len(fake.verbs("StartCaching")), 1)
        self.assertEqual(self.console_files(), [])

    def test_nested_rollback_keeps_ids_that_existed_before(self):
        report = self.report(2)
        rule_ids = [r["RuleId"] for r in report["AssignedPolicies"][0]["AssignedPolicyRules"]]
        fake = FakeSwis()
        fake.add_policy("earlier-policy", [rule_ids[0]])
        fake.add_report("Earlier import", ["earlier-policy"], "earlier-report")
        fake.reject_items = True
        fake.nested = "full"
        fake.drop_rule_on_readback = True
        lines, log = capture()
        with self.assertRaises(tool.NcmWireError):
            tool.import_ncm_report(fake, report, log=log)
        self.assertIn(rule_ids[0], fake.rules, "the earlier import's rule survives")
        self.assertNotIn(rule_ids[1], fake.rules)
        self.assertEqual(set(fake.reports), {"earlier-report"})

    def test_nested_rollback_stops_when_in_ids_is_broken(self):
        fake = FakeSwis()
        fake.reject_items = True
        fake.nested = "report-only"
        fake.in_ids_broken = True
        with self.assertRaises(tool.InIdsProbeError):
            self.run_import(fake)
        self.assertEqual(len(fake.reports), 1, "nothing was deleted on an unverified basis")
        self.assertEqual([c for c in fake.verbs() if c[1].startswith("Delete")], [])
        self.assertEqual(self.console_files(), [])

    # -- item 14: permissions ----------------------------------------------------
    def test_preflight_refuses_a_denied_account_before_writing(self):
        log = self.open_log()
        fake = FakeSwis()
        fake.fail["GetPolicyReport"] = tool.SwisError(
            "HTTP 403 from Invoke/Cirrus.PolicyReports/GetPolicyReport\nAccess is denied.")
        with self.assertRaisesRegex(tool.SwisError, "WebDownloader NCM role"):
            self.run_import(fake)
        self.assertEqual([c for c in fake.verbs() if c[1].startswith("Add")], [])
        tool.close_logging()
        text = "\n".join(read_log_lines(log))
        self.assertIn("NCM role needed (2026.2 verb descriptions): WebUploader or higher for "
                      "StartCaching, UpdateReportStatus", text)
        self.assertIn("WebDownloader or higher for AddPolicyRule", text)

    def test_preflight_inconclusive_answer_continues(self):
        log = self.open_log()
        fake = FakeSwis()
        fake.fail["GetPolicyReport"] = [tool.SwisError("HTTP 500 from GetPolicyReport\nnot found")]
        self.run_import(fake)
        self.assertEqual(len(fake.reports), 2)
        tool.close_logging()
        self.assertTrue(any(" WARN  import permission preflight inconclusive" in line
                            for line in read_log_lines(log)))

    def test_start_caching_denied_still_writes_the_console_files_due(self):
        fake = FakeSwis()
        fake.reject_all_after = 1
        fake.fail["StartCaching"] = tool.SwisError(FORBIDDEN_403)
        with self.assertRaises(SystemExit):
            self.run_import(fake)
        self.assertEqual(len(fake.reports), 1)
        self.assertEqual(len(self.console_files()), 1)
        self.assertIn("StartCaching failed", self.output)
        self.assertIn("WebUploader", self.output)

    def test_start_caching_denied_after_a_full_import_exits_nonzero(self):
        fake = FakeSwis()
        fake.fail["StartCaching"] = tool.SwisError(FORBIDDEN_403)
        with self.assertRaisesRegex(SystemExit, "caching could not be confirmed"):
            self.run_import(fake)
        self.assertEqual(len(fake.reports), 2)

    def test_update_report_status_denied_is_reported(self):
        fake = FakeSwis()
        fake.fail["UpdateReportStatus"] = tool.SwisError(
            "HTTP 403 from UpdateReportStatus\nAccess is denied.")
        with self.assertRaisesRegex(SystemExit, "disabled state could not be confirmed"):
            self.run_import(fake, disabled=True)
        self.assertIn("UpdateReportStatus('Disabled') failed", self.output)

    def test_start_caching_result_is_logged(self):
        log = self.open_log()
        fake = FakeSwis()
        fake.add_report("r", [], "r1")
        self.assertTrue(tool.finish_ncm_imports(fake, ["r1"], log=lambda m: None))
        fake.results["StartCaching"] = False
        self.assertFalse(tool.finish_ncm_imports(fake, ["r1"], log=lambda m: None))
        tool.close_logging()
        lines = read_log_lines(log)
        self.assertTrue(any("StartCaching returned true" in line for line in lines))
        self.assertTrue(any("StartCaching returned false" in line for line in lines))
        self.assertTrue(any(" WARN  import warning: StartCaching returned false" in line
                            for line in lines))

    # -- item 16: IN @ids sanity probe ---------------------------------------------
    def test_import_stops_when_in_ids_misses_a_rule_known_to_exist(self):
        fake = FakeSwis()
        fake.add_policy("old-p", ["old-r"])
        fake.add_report("Old", ["old-p"], "old")
        fake.in_ids_broken = True
        with self.assertRaisesRegex(tool.InIdsProbeError, "known to exist"):
            self.run_import(fake)
        self.assertEqual([c for c in fake.verbs() if c[1].startswith("Add")], [])
        self.assertEqual(set(fake.rules), {"old-r"})

    def test_remove_stops_when_in_ids_misses_the_report(self):
        fake = FakeSwis()
        fake.add_policy("p1", ["r1"])
        fake.add_report("Report A", ["p1"], "rA")
        fake.in_ids_broken = True
        args = argparse.Namespace(name="Report A", dry_run=False, yes=True, delete_children=False)
        with mock.patch.object(tool, "connect", return_value=fake), \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(tool.InIdsProbeError):
                tool.cmd_remove(args)
        self.assertEqual([c for c in fake.verbs() if c[1].startswith("Delete")], [])
        self.assertIn("rA", fake.reports)

    def test_probe_success_is_logged(self):
        log = self.open_log()
        fake = FakeSwis()
        fake.add_report("Report A", [], "rA")
        tool.confirm_in_ids(tool.logged(fake), "report", "rA", "a test")
        tool.close_logging()
        self.assertTrue(any("IN @ids sanity probe ok before a test" in line
                            for line in read_log_lines(log)))


# ---------------------------------------------------------------------------
# 8. Run log: format, redaction, default path, one line per SWIS call
# ---------------------------------------------------------------------------

class LoggingTests(TempDirTest):
    def open_log(self, level="info"):
        path = os.path.join(self.tmp, "run.log")
        self.addCleanup(tool.close_logging)
        self.assertEqual(tool.setup_logging(path, level), os.path.abspath(path))
        return path

    def test_line_format(self):
        line = tool.format_log_line(1791547387.1234, "warn", "rollbk", "two\r\nlines\nhere")
        self.assertEqual(line, "2026-10-09T12:03:07.123Z WARN  rollbk two\\nlines\\nhere")
        for level in ("debug", "info", "warn", "error"):
            for comp in tool.LOG_COMPONENTS:
                self.assertRegex(tool.format_log_line(0.5, level, comp, "m"), LOG_LINE_RE)

    def test_every_line_matches_and_levels_filter(self):
        path = self.open_log("info")
        tool.log_event("parse", "kept")
        tool.log_event("swis", "dropped at info", "debug")
        tool.log_event("not-a-component", "falls back to main", "warn")
        tool.close_logging()
        lines = read_log_lines(path)
        self.assertEqual(len(lines), 2)
        for line in lines:
            self.assertRegex(line, LOG_LINE_RE)
        self.assertIn(" WARN  main   falls back to main", lines[1])

    def test_secrets_never_reach_the_file(self):
        secret = "Pw-Log-Test-7731"
        tool.register_secret(secret)
        token = base64.b64encode(f"admin:{secret}".encode()).decode()
        path = self.open_log("debug")
        tool.log_event("swis", f"server echoed the password {secret}", "error")
        swis = tool.logged(FakeSwis())
        swis.query("SELECT PolicyReportID FROM Cirrus.PolicyReports WHERE Name = @n", {"n": secret})
        client = tool.SwisClient("orion.example.com", "admin", secret)
        self.assertIsNotNone(client)
        tool.close_logging()
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        self.assertNotIn(secret, text)
        self.assertNotIn(token, text)
        self.assertIn("as user 'admin'", text)
        self.assertIn("orion.example.com", text)

    def test_default_path_and_override(self):
        win = tool.default_log_path(now=0, env={"LOCALAPPDATA": r"C:\Users\x\AppData\Local"},
                                    platform_name="win32", home=r"C:\Users\x")
        self.assertEqual(win, os.path.join(r"C:\Users\x\AppData\Local", "DisaStigTool", "logs",
                                           "disa-stig-tool_19700101-000000.log"))
        win_no_env = tool.default_log_path(now=0, env={}, platform_name="win32", home="H")
        self.assertEqual(win_no_env, os.path.join("H", "AppData", "Local", "DisaStigTool", "logs",
                                                  "disa-stig-tool_19700101-000000.log"))
        other = tool.default_log_path(now=0, env={}, platform_name="linux", home="/home/u")
        self.assertEqual(other, os.path.join("/home/u", ".local", "state", "disa-stig-tool", "logs",
                                             "disa-stig-tool_19700101-000000.log"))
        xdg = tool.default_log_path(now=0, env={"XDG_STATE_HOME": "/st"}, platform_name="linux")
        self.assertEqual(xdg, os.path.join("/st", "disa-stig-tool", "logs",
                                           "disa-stig-tool_19700101-000000.log"))
        # Without --log-file the default location is used ...
        default = os.path.join(self.tmp, "default", "logs", "d.log")
        self.addCleanup(tool.close_logging)
        with mock.patch.object(tool, "default_log_path", return_value=default):
            self.assertEqual(tool.setup_logging(None), default)
        # ... and --log-file overrides it.
        override = os.path.join(self.tmp, "elsewhere", "mine.log")
        self.assertEqual(tool.setup_logging(override), override)
        self.assertTrue(os.path.isfile(override))

    def test_one_line_per_swis_call(self):
        path = self.open_log()
        fake = FakeSwis()
        out = io.StringIO()
        with mock.patch.object(tool, "connect", return_value=fake), contextlib.redirect_stdout(out):
            tool.cmd_import(import_args(self.router_zip()))
        tool.close_logging()
        calls = [line for line in read_log_lines(path)
                 if " swis   " in line and (" -> ok " in line or " -> error " in line)]
        self.assertEqual(len(calls), len(fake.calls))
        self.assertGreater(len(calls), 5)
        self.assertTrue(any("Cirrus.PolicyReports.AddPolicyRule(<object V-1001 [high]" in c
                            for c in calls))
        self.assertTrue(any(re.search(r"query SELECT .* -> ok \d+ ms, \d+ row\(s\)", c) for c in calls))

    def test_failed_call_and_debug_bodies(self):
        path = self.open_log("debug")
        fake = FakeSwis()
        fake.reject_all_after = 0
        with self.assertRaises(tool.SwisError):
            tool.logged(fake).invoke("Cirrus.PolicyReports", "AddPolicyRule", {"RuleName": "r"})
        tool.logged(fake).invoke("Orion.PolicyEngine.Policy", "ImportPolicy", "x" * 10000)
        tool.close_logging()
        lines = read_log_lines(path)
        self.assertTrue(any(" WARN  swis   Cirrus.PolicyReports.AddPolicyRule(<object r>) -> error "
                            in line and "HTTP 400" in line for line in lines))
        bodies = [line for line in lines if " DEBUG swis   request " in line]
        self.assertEqual(len(bodies), 2)
        self.assertTrue(any("[truncated, " in line for line in bodies))
        self.assertTrue(all(len(line) < tool.LOG_BODY_LIMIT + 400 for line in lines))

    def test_cli_run_logs_start_and_end_without_the_password(self):
        secret = "Cli-Secret-5521"
        env = dict(os.environ, SWIS_PASSWORD=secret)
        log = os.path.join(self.tmp, "cli.log")
        result = subprocess.run([sys.executable, PY_TOOL, "convert", self.router_zip(), "--name",
                                 secret, "--log-file", log], cwd=self.tmp, env=env,
                                capture_output=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.assertEqual(result.stderr.decode(errors="replace").count(f"log file: {log}"), 2)
        lines = read_log_lines(log)
        for line in lines:
            self.assertRegex(line, LOG_LINE_RE)
        text = "\n".join(lines)
        self.assertNotIn(secret, text)
        self.assertIn(f"DISA STIG Conversion Tool {tool.TOOL_VERSION} (Python edition)", lines[0])
        self.assertIn("command line: disa_stig_tool.py convert", text)
        self.assertIn("run end: exit code 0; 0 SWIS call(s)", lines[-1])
        self.assertIn("2 file(s) written", lines[-1])

    def test_log_path_is_printed_once_at_start_and_once_at_end(self):
        """With stdout and stderr in one stream (2>&1), buffered stdout used to land
        after both announcements, so the path looked printed twice at the start."""
        xml = self.write("U_Cisco_X-xccdf.xml", xccdf_xml("X_STIG", "Cisco X STIG", RTR_GROUPS))
        log = os.path.join(self.tmp, "once.log")
        result = subprocess.run([sys.executable, PY_TOOL, "convert", xml, "--log-file", log],
                                cwd=self.tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                timeout=120)
        self.assertEqual(result.returncode, 0)
        lines = [line for line in result.stdout.decode(errors="replace").splitlines() if line]
        self.assertEqual(sum(line.startswith("log file: ") for line in lines), 2, lines)
        self.assertTrue(lines[0].startswith("log file: "), lines)
        self.assertTrue(lines[-1].startswith("log file: "), lines)
        self.assertTrue(any(line.startswith("wrote ") for line in lines[1:-1]), lines)

    def test_cli_failure_is_logged_with_exit_code(self):
        log = os.path.join(self.tmp, "fail.log")
        result = subprocess.run([sys.executable, PY_TOOL, "parse",
                                 os.path.join(self.tmp, "missing.txt"), "--log-file", log],
                                capture_output=True, timeout=120)
        self.assertEqual(result.returncode, 1)
        lines = read_log_lines(log)
        self.assertTrue(any(" ERROR main   error: " in line for line in lines))
        self.assertIn("run end: exit code 1;", lines[-1])

    def test_version_constant(self):
        self.assertEqual(tool.TOOL_VERSION, "2.0.0")
        with open(PS_TOOL, encoding="ascii") as fh:
            self.assertIn(f"$script:ToolVersion = '{tool.TOOL_VERSION}'", fh.read())


# ---------------------------------------------------------------------------
# 9. Security: DTD/XXE refusal, SCM probe quoting, file-name sanitizing
# ---------------------------------------------------------------------------

class SecurityTests(TempDirTest):
    def test_dtd_and_external_entities_are_refused_with_a_logged_reason(self):
        path = os.path.join(self.tmp, "sec.log")
        self.addCleanup(tool.close_logging)
        tool.setup_logging(path)
        for raw in (XXE_XML, DTD_ONLY_XML):
            with self.assertRaisesRegex(ValueError, "declares a DTD"):
                tool.parse_benchmarks(raw, "evil-xccdf.xml")
            self.assertEqual(tool._try_parse_xml(raw, "evil-xccdf.xml"), [])
        # A zip carrying one hostile member still yields its good benchmark.
        zpath = os.path.join(self.tmp, "U_Mixed_Cisco_STIG.zip")
        with zipfile.ZipFile(zpath, "w") as zf:
            zf.writestr("evil-xccdf.xml", XXE_XML)
            zf.writestr("good-xccdf.xml", xccdf_xml("Good_STIG", "Good Cisco STIG", RTR_GROUPS))
        self.assertEqual([b["benchmark_id"] for b in tool.load_benchmarks(zpath)], ["Good_STIG"])
        bare = self.write("evil-xccdf.xml", XXE_XML)
        with self.assertRaisesRegex(ValueError, "declares a DTD"):
            tool.load_benchmarks(bare)
        tool.close_logging()
        refusals = [line for line in read_log_lines(path)
                    if " WARN  parse  " in line and "declares a DTD" in line]
        self.assertGreaterEqual(len(refusals), 3)

    def test_declared_encoding_is_honoured(self):
        xml = xccdf_xml("Enc_STIG", "Caf\u00e9 STIG", RTR_GROUPS).replace(
            'encoding="UTF-8"', 'encoding="windows-1252"').encode("cp1252")
        self.assertEqual(tool.parse_benchmarks(xml, "enc.xml")[0]["title"], "Caf\u00e9 STIG")
        utf16 = xccdf_xml("U16_STIG", "Caf\u00e9 STIG", RTR_GROUPS).replace(
            'encoding="UTF-8"', 'encoding="UTF-16"').encode("utf-16")
        self.assertEqual(tool.parse_benchmarks(utf16, "u16.xml")[0]["title"], "Caf\u00e9 STIG")

    def test_ps_single_quote(self):
        self.assertEqual(tool.ps_single_quote("it's"), "'it''s'")
        self.assertEqual(tool.ps_single_quote('a`b $(c) "d"'), "'a`b $(c) \"d\"'")
        self.assertEqual(tool.ps_single_quote("x\u2019y"), "'x\u2019\u2019y'")

    def test_probe_never_carries_stig_text_into_script_source(self):
        path = os.path.join(self.tmp, "probe.log")
        self.addCleanup(tool.close_logging)
        tool.setup_logging(path)
        bench = make_benchmark("Probe_STIG", [make_rule(1), dict(make_rule(2), vuln_id=NASTY_VULN,
                                                                 rule_id="SV-2$(x)")])
        text = tool.xccdf_to_scm_yaml(bench)
        tool.close_logging()
        scripts = [line for line in text.splitlines() if line.startswith("      script: ")]
        self.assertEqual(scripts[0], "      script: \"Write-Host 'V-1 reviewed: False'\"")
        self.assertEqual(scripts[1], "      script: \"Write-Host 'V-77_Remove-Item_C_x_ reviewed: False'\"")
        for line in scripts:
            self.assertNotIn("$(", line)
            self.assertNotIn("`", line)
        self.assertIn("    expression: \"V-77_Remove-Item_C_x_ reviewed: True\"", text)
        warnings = [line for line in read_log_lines(path) if " WARN  scm    " in line]
        self.assertEqual(len(warnings), 2)   # the vuln id and the rule id

    def test_probe_id_accepts_scap_prefixes(self):
        self.assertEqual(tool.scm_probe_id("xccdf_mil.disa.stig_group_V-123",
                                           "xccdf_mil.disa.stig_rule_SV-123r2_rule"), "V-123")
        self.assertEqual(tool.scm_probe_id("V-1\n"), "V-1_")

    def test_safe_file_name(self):
        name = tool.safe_file_name("../../x", ".ncm-report.xml")
        self.assertEqual(name, "_.._x.ncm-report.xml")
        self.assertNotIn("/", name)
        self.assertNotIn("\\", name)
        long_name = tool.safe_file_name("T" * 300, ".scm-policy.yaml")
        self.assertEqual(len(long_name), tool.MAX_FILE_NAME)
        self.assertTrue(long_name.endswith(".scm-policy.yaml"))
        self.assertEqual(tool.safe_file_name("CON", ".ncm-report.xml"), "_CON.ncm-report.xml")
        self.assertEqual(tool.safe_file_name("...", ".x"), "unnamed.x")
        self.assertEqual(tool.safe_file_name("Caf\u00e9 / R\u00e9seau: V1", ""), "Caf_R_seau_V1")

    def test_console_file_stays_in_its_folder_and_fits(self):
        out_dir = os.path.join(self.tmp, "out")
        os.makedirs(out_dir)
        for report_name in ("../../evil", "N" * 250):
            report = tool.build_reports([make_benchmark("B", [make_rule(1)])],
                                        name=report_name)[0]
            written = tool.write_console_file(report, out_dir)
            self.assertEqual(os.path.dirname(os.path.abspath(written)), os.path.abspath(out_dir))
            self.assertTrue(os.path.isfile(written))
            self.assertLessEqual(len(os.path.basename(written)), tool.MAX_FILE_NAME)
        long_bench = make_benchmark("", [make_rule(1)], title="Very long title " * 20)
        self.assertLessEqual(len(tool.scm_policy_filename(long_bench)), tool.MAX_FILE_NAME)
        self.assertLessEqual(len(tool.scm_policy_filename(long_bench, "S" * 300)),
                             tool.MAX_FILE_NAME)


# ---------------------------------------------------------------------------
# Loopback SWIS stand-in: what actually goes over the wire, and certificate pins
# ---------------------------------------------------------------------------

class _Recorder(http.server.BaseHTTPRequestHandler):
    """Records each POST (path, Content-Type, raw body, Authorization) and answers
    every Invoke with the JSON string "new-rule-id"."""

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        self.server.seen.append({"path": self.path, "type": self.headers.get("Content-Type"),
                                 "body": self.rfile.read(length),
                                 "auth": self.headers.get("Authorization")})
        out = json.dumps("new-rule-id").encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *args):
        pass


@contextlib.contextmanager
def loopback_server(cert=None, key=None):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Recorder)
    server.seen = []
    server.handle_error = lambda request, address: None   # refused handshakes are expected
    if cert:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert, key)
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


def make_self_signed(folder, cn="SolarWinds-Orion"):
    """(cert.pem, key.pem, SHA-256 hex) of a fresh self-signed certificate, made with
    the openssl that Git for Windows ships (or any on PATH); None when there is none."""
    candidates = [shutil.which("openssl")]
    git = shutil.which("git")
    if git:
        for base in (os.path.dirname(os.path.dirname(git)),
                     os.path.dirname(os.path.dirname(os.path.dirname(git)))):
            candidates += [os.path.join(base, "usr", "bin", "openssl.exe"),
                           os.path.join(base, "mingw64", "bin", "openssl.exe")]
    exe = next((c for c in candidates if c and os.path.isfile(c)), None)
    if not exe:
        return None
    os.makedirs(folder, exist_ok=True)
    cert, key = os.path.join(folder, "cert.pem"), os.path.join(folder, "key.pem")
    result = subprocess.run([exe, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", key,
                             "-out", cert, "-days", "2", "-subj", "/CN=" + cn],
                            capture_output=True, timeout=120,
                            env=dict(os.environ, MSYS_NO_PATHCONV="1"))
    if result.returncode != 0 or not os.path.isfile(cert):
        return None
    with open(cert, encoding="ascii") as fh:
        der = ssl.PEM_cert_to_DER_cert(fh.read())
    return cert, key, hashlib.sha256(der).hexdigest().upper()


class PythonPinTests(TempDirTest):
    def test_python_pin_is_enforced(self):
        made = make_self_signed(os.path.join(self.tmp, "server"))
        other = make_self_signed(os.path.join(self.tmp, "other"))
        if not made or not other:
            self.skipTest("openssl not found; cannot make a test certificate")
        cert, key, fingerprint = made
        with loopback_server(cert, key) as server:
            port = server.server_address[1]
            pem, shown, stock = tool.fetch_server_cert("127.0.0.1", port)
            self.assertEqual(shown.replace(":", ""), fingerprint)
            self.assertTrue(stock)
            good = tool.SwisClient("127.0.0.1", "admin", "Pin-Py-7781", port=port, pinned_pem=pem)
            self.assertEqual(good.invoke("Cirrus.PolicyReports", "GetPolicyReport", tool.NIL_GUID,
                                         False), "new-rule-id")
            with open(other[0], encoding="ascii") as fh:
                wrong = tool.SwisClient("127.0.0.1", "admin", "Pin-Py-7781", port=port,
                                        pinned_pem=fh.read())
            with self.assertRaisesRegex(tool.SwisError, "could not reach"):
                wrong.invoke("Cirrus.PolicyReports", "GetPolicyReport", tool.NIL_GUID, False)
            self.assertEqual(len(server.seen), 1, "the refused connection delivered nothing")


PS_LOOPBACK_RUNNER = r"""
param([string]$Tool, [string]$Base, [string]$Pin, [string]$Mode)
. $Tool -NoGui
$sentinel = [System.Net.Security.RemoteCertificateValidationCallback] { param($a, $b, $c, $d) $false }
[System.Net.ServicePointManager]::ServerCertificateValidationCallback = $sentinel
$script:ForceHttpClient = ($Mode -eq 'httpclient')
if ($Pin -eq 'none') { $Pin = '' }
$conn = New-SwisConnection '127.0.0.1' 1 'admin' 'Loopback-Pw-5512' $false $false $Pin
$conn.Base = $Base
$out = [ordered]@{}
try {
    $text = 'Caf' + [char]0xE9 + ' ' + [char]0x2014 + ' ' + [char]0x2713
    $r = Invoke-SwisVerbCall $conn 'Cirrus.PolicyReports' 'AddPolicyRule' @([ordered]@{ RuleName = $text })
    $out.ok = $true; $out.result = [string]$r
} catch { $out.ok = $false; $out.error = $_.Exception.Message }
$out.restored = [object]::ReferenceEquals([System.Net.ServicePointManager]::ServerCertificateValidationCallback, $sentinel)
$out.pinCalls = 0; if ($conn.PinCheck) { $out.pinCalls = $conn.PinCheck.Calls }
[Console]::Out.Write((ConvertTo-Json $out -Compress))
"""


# ---------------------------------------------------------------------------
# PowerShell edition: parse, self-tests, and cross-edition parity
# ---------------------------------------------------------------------------

def run_powershell(*args, timeout=300):
    return subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
                           "Bypass", *args], capture_output=True, timeout=timeout)


def ps_benchmark(b):
    """A Python benchmark dict in the PowerShell edition's key names."""
    return {
        "BenchmarkId": b["benchmark_id"], "Title": b["title"], "Version": b["version"],
        "Release": b["release"], "StatusDate": b["status_date"], "Source": b["source"],
        "Edition": b["edition"],
        "Rules": [{"VulnId": r["vuln_id"], "RuleId": r["rule_id"], "StigId": r["stig_id"],
                   "Severity": r["severity"], "Title": r["title"], "Discussion": r["discussion"],
                   "CheckContent": r["check_content"], "OvalRef": r["oval_ref"],
                   "FixText": r["fix_text"], "Ccis": r["ccis"]} for r in b["rules"]],
    }


def strip_advisory(reports):
    """The report ID is a random advisory GUID in both editions; everything else must match."""
    return [{k: v for k, v in rep.items() if k != "ID"} for rep in reports]


@unittest.skipUnless(POWERSHELL, "Windows PowerShell / pwsh not found")
class PowerShellEditionTests(TempDirTest):
    def test_parses_without_errors(self):
        script = ("$t=$null; $e=$null; [void][System.Management.Automation.Language.Parser]::"
                  f"ParseFile('{PS_TOOL}', [ref]$t, [ref]$e); $e.Count")
        result = run_powershell("-Command", script)
        self.assertEqual(result.stdout.decode(errors="replace").strip(), "0", result.stderr)

    def test_powershell_self_tests_pass(self):
        result = run_powershell("-File", PS_TEST)
        self.assertEqual(result.returncode, 0,
                         result.stdout.decode(errors="replace") + result.stderr.decode(errors="replace"))

    def test_both_editions_build_identical_payloads(self):
        router_zip = self.router_zip()
        bare_xml = self.write("U_Test_Router_NDM_Manual-xccdf.xml",
                              xccdf_xml("Test_Router_NDM_STIG", "Test Cisco Router NDM STIG", NDM_GROUPS))
        no_id_xml = self.write("no-id-xccdf.xml",
                               xccdf_xml("", "Benchmark Without An Id", RTR_GROUPS))
        # Declared windows-1252: both editions must decode by the declaration.
        cp1252_xml = self.write("U_Café_Router-xccdf.xml", xccdf_xml(
            "Cafe_STIG", "Café Router STIG", RTR_GROUPS).replace(
            'encoding="UTF-8"', 'encoding="windows-1252"').encode("cp1252"))
        refuse = [self.write("xxe-xccdf.xml", XXE_XML), self.write("dtd-xccdf.xml", DTD_ONLY_XML)]
        ps_log = os.path.join(self.tmp, "ps-parity.log")
        where = "(Vendor = 'Cisco')"
        files = [
            dict(path=router_zip, name="", where=where, mode="manual", folder="DISA STIG",
                 enabled=True, configType="Any"),
            dict(path=router_zip, name="Custom Name", where=where, mode="heuristic",
                 folder="DISA STIG", enabled=False, configType="Running"),
            dict(path=bare_xml, name="", where="(Vendor LIKE '%Juniper%')", mode="heuristic",
                 folder="Team/STIG", enabled=True, configType="Any"),
            dict(path=no_id_xml, name="Named", where=where, mode="manual", folder="DISA STIG",
                 enabled=True, configType="Startup"),
            dict(path=cp1252_xml, name="", where=where, mode="manual", folder="DISA STIG",
                 enabled=True, configType="Any"),
        ]
        long_title = "Very Long Benchmark Title " * 15
        tricky = make_rule(9, "high",
                           check="Check:\r\nlogging buffered *\r\nOtherwise a finding.",
                           title="Quote \" backslash \\ tab \t unicode é dash —",
                           fix="Line one\nline two\bwith\fcontrol\x01chars")
        memory = [
            dict(benchmarks=[make_benchmark("Mem_One", [tricky, make_rule(10, "low", oval="oval:x:def:10")],
                                            title=long_title)],
                 baseName="", where=where, mode="heuristic", folder="DISA STIG", enabled=True,
                 configType="Any"),
            dict(benchmarks=[make_benchmark("", [make_rule(11)], title="No Id In Memory")],
                 baseName="Base", where=where, mode="manual", folder="DISA STIG", enabled=True,
                 configType="Any"),
            # Hostile ids: the SCM probe must come out identical (and inert) in both.
            dict(benchmarks=[make_benchmark("Probe_STIG", [
                dict(make_rule(12), vuln_id=NASTY_VULN, rule_id="SV-12$(x)"),
                dict(make_rule(13), vuln_id="xccdf_mil.disa.stig_group_V-13",
                     rule_id="xccdf_mil.disa.stig_rule_SV-13r1_rule")])],
                 baseName="", where=where, mode="manual", folder="DISA STIG", enabled=True,
                 configType="Any"),
        ]
        name_cases = [{"stem": stem, "suffix": suffix} for stem, suffix in (
            ("../../x", ".ncm-report.xml"), ("T" * 300, ".scm-policy.yaml"), ("CON", ".x"),
            ("...", ""), ("Café / Réseau: V1 — x", ".ncm-report.xml"),
            ("a" * 250 + " - Bench_ID", ".ncm-report.xml"), ("plain_name-1.2", ".yaml"))]
        quotes = ["it's", 'a`b $(c) "d"', "x’y‘z‚‛", ""]
        probe_ids = ["V-1", NASTY_VULN, "xccdf_mil.disa.stig_group_V-5", "V-1\n", "", "v-1"]
        wire = [*DOCUMENTED_400S, UNDOCUMENTED_400, FORBIDDEN_403,
                "SWIS HTTP 400 from Invoke/Cirrus.PolicyReports/AddPolicyRule\nValue cannot be null. "
                "Parameter name: input",
                "HTTP 400 from X\nValue cannot be null. (Parameter 'input')",
                "HTTP 500 from X\ncannot unpackage parameter 0",
                "transport error calling x: TimeoutError: timed out"]
        trees = [
            {"expected": [["P", ["a", "b", "c"]], ["Q", ["d"]]], "actual": [["P", ["a", "b"]]]},
            {"expected": [["P", ["a", "b"]]], "actual": [["P", ["b", "x"]]]},
            {"expected": [["P", ["a", "a", "b"]]], "actual": [["P", ["b"]]]},
            {"expected": [["P", ["1", "2", "3", "4", "5"]]], "actual": [["P", []]]},
            {"expected": [["Café", ["r"]], ["café", ["s"]]],
             "actual": [["café", ["s"]], ["Café", ["r"]]]},
            {"expected": [["P", ["a"]], ["P", ["b"]]], "actual": [["P", ["b"]], ["P", ["a"]]]},
            {"expected": [["P", ["a"]]], "actual": [["P", ["a"]]]},
        ]
        spec = {"files": files,
                "memory": [dict(c, benchmarks=[ps_benchmark(b) for b in c["benchmarks"]]) for c in memory],
                "names": name_cases, "quotes": quotes, "probeIds": probe_ids,
                "refuse": refuse, "logFile": ps_log, "wire": wire, "trees": trees}
        spec_path = self.write("parity-in.json", json.dumps(spec))
        out_path = os.path.join(self.tmp, "parity-out.json")
        result = run_powershell("-File", PS_TEST, "-ParityJson", spec_path, "-ParityOut", out_path)
        self.assertEqual(result.returncode, 0, result.stdout.decode(errors="replace")
                         + result.stderr.decode(errors="replace"))
        with open(out_path, encoding="utf-8-sig") as fh:
            ps = json.load(fh)

        for i, c in enumerate(files):
            with self.subTest(file_case=i):
                benches = tool.load_benchmarks(c["path"])
                py_reports = tool.build_reports(
                    benches, name=c["name"] or None, grouping=c["folder"], node_where=c["where"],
                    config_type=c["configType"], mode=c["mode"], source_path=c["path"],
                    enabled=c["enabled"])
                self.assertEqual(strip_advisory(ps["files"][i]["reports"]), strip_advisory(py_reports))
                self.assertEqual(ps["files"][i]["scm"], [tool.xccdf_to_scm_yaml(b) for b in benches])
        for i, c in enumerate(memory):
            with self.subTest(memory_case=i):
                py_reports = tool.build_reports(
                    c["benchmarks"], name=c["baseName"] or None, grouping=c["folder"],
                    node_where=c["where"], config_type=c["configType"], mode=c["mode"],
                    enabled=c["enabled"])
                self.assertEqual(strip_advisory(ps["memory"][i]["reports"]), strip_advisory(py_reports))
                self.assertEqual(ps["memory"][i]["scm"], [tool.xccdf_to_scm_yaml(b) for b in c["benchmarks"]])

        # Spot-check that the comparison covered what matters.
        names = [r["Name"] for case in ps["files"] for r in case["reports"]]
        self.assertIn("U_Test_Cisco_Router_STIG - Test_Router_NDM_STIG", names)
        self.assertIn("Custom Name - Test_Router_RTR_STIG", names)
        self.assertIn("Test Cisco Router NDM STIG", names)       # .xml input: title, not file name
        self.assertIn("Named", names)                            # no benchmark id: name alone
        self.assertIn("Café Router STIG", names)            # declared encoding honoured
        self.assertEqual(len(ps["memory"][0]["reports"][0]["Name"]), 250)
        self.assertIn("script: \"Write-Host 'V-77_Remove-Item_C_x_ reviewed: False'\"",
                      ps["memory"][2]["scm"][0])

        # Shared helpers agree byte for byte.
        self.assertEqual(ps["names"], [tool.safe_file_name(n["stem"], n["suffix"]) for n in name_cases])
        self.assertEqual(ps["quoted"], [tool.ps_single_quote(q) for q in quotes])
        self.assertEqual(ps["probeIds"], [tool.scm_probe_id(i) for i in probe_ids])
        # Import decisions agree: which 400s are wire rejections, and the read-back diff text.
        self.assertEqual(ps["wire"], [tool.is_wire_rejection(w) for w in wire])
        self.assertEqual(ps["wire"][:3], [True, True, False])
        self.assertEqual(ps["trees"], ["\n".join(tool.compare_report_trees(
            [tuple(p) for p in c["expected"]], [tuple(p) for p in c["actual"]])) for c in trees])
        self.assertIn("(missing \"1\", \"2\", \"3\", ...)", ps["trees"][3])

        # Both editions refuse DTDs, and the PowerShell log says why in the same format.
        self.assertEqual(ps["refused"], [0, 0])
        for path in refuse:
            with open(path, "rb") as fh:
                self.assertEqual(tool._try_parse_xml(fh.read(), "x.xml"), [])
        ps_lines = read_log_lines(ps_log)
        for line in ps_lines:
            self.assertRegex(line, LOG_LINE_RE)
        self.assertEqual(len([line for line in ps_lines if "declares a DTD" in line]), 2)

    def run_ps_loopback(self, base, pin, mode):
        runner = self.write("loopback.ps1", PS_LOOPBACK_RUNNER)
        result = run_powershell("-File", runner, "-Tool", PS_TOOL, "-Base", base,
                                "-Pin", pin or "none", "-Mode", mode, timeout=180)
        text = result.stdout.decode(errors="replace")
        self.assertIn("{", text, text + result.stderr.decode(errors="replace"))
        return json.loads(text[text.index("{"):])

    def test_powershell_sends_utf8_bytes_with_a_charset(self):
        """Both transport paths put the UTF-8 bytes of the JSON on the wire, with
        charset=utf-8 said explicitly (Windows PowerShell 5.1 otherwise encodes a
        string body as ISO-8859-1)."""
        for mode in ("restmethod", "httpclient"):
            with self.subTest(mode=mode), loopback_server() as server:
                base = f"http://127.0.0.1:{server.server_address[1]}{tool.BASE_PATH}"
                res = self.run_ps_loopback(base, None, mode)
                self.assertTrue(res["ok"], res)
                self.assertEqual(res["result"], "new-rule-id")
                seen = server.seen[0]
                self.assertEqual(seen["path"], tool.BASE_PATH + "/Invoke/Cirrus.PolicyReports/AddPolicyRule")
                self.assertEqual(seen["type"].replace(" ", "").lower(), "application/json;charset=utf-8")
                self.assertEqual(json.loads(seen["body"].decode("utf-8")),
                                 [{"RuleName": "Café — ✓"}])
                self.assertTrue(seen["auth"].startswith("Basic "))

    def test_powershell_pin_fails_closed_on_both_paths(self):
        made = make_self_signed(os.path.join(self.tmp, "server"))
        if not made:
            self.skipTest("openssl not found; cannot make a test certificate")
        cert, key, fingerprint = made
        with loopback_server(cert, key) as server:
            port = server.server_address[1]
            base = f"https://127.0.0.1:{port}{tool.BASE_PATH}"
            fetched = run_powershell("-Command", f". '{PS_TOOL}' -NoGui; [Console]::Out.Write("
                                                 f"(Get-ServerCertThumbprint '127.0.0.1' {port}).Thumbprint)")
            self.assertEqual(fetched.stdout.decode(errors="replace").strip(), fingerprint,
                             fetched.stderr.decode(errors="replace"))
            for mode in ("restmethod", "httpclient"):
                with self.subTest(mode=mode):
                    good = self.run_ps_loopback(base, fingerprint, mode)
                    self.assertTrue(good["ok"], good)
                    self.assertGreaterEqual(good["pinCalls"], 1, "the pin was checked")
                    self.assertTrue(good["restored"], "the previous callback is back after the call")
                    bad = self.run_ps_loopback(base, "AB" * 32, mode)
                    self.assertFalse(bad["ok"], bad)
                    self.assertIn("pin mismatch", bad["error"])
                    self.assertIn(fingerprint, bad["error"])
                    self.assertTrue(bad["restored"])
            self.assertEqual(len(server.seen), 2, "only the two pinned-correctly calls arrived")

    def test_both_editions_write_the_same_log_format(self):
        """Run a real conversion through each edition's CLI with a log file and a
        password in the environment and on the command line: every line of both
        logs matches the same contract, and neither carries the password."""
        secret = "Parity-Secret-6630"
        env = dict(os.environ, SWIS_PASSWORD=secret)
        results = {}
        for edition in ("py", "ps"):
            folder = os.path.join(self.tmp, edition)
            os.makedirs(folder)
            source = shutil.copy(self.router_zip(), folder)
            log = os.path.join(self.tmp, f"{edition}.log")
            if edition == "py":
                cmd = [sys.executable, PY_TOOL, "convert", source, "--name", secret,
                       "--log-file", log]
            else:
                cmd = [POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                       "-File", PS_TOOL, "-Convert", "-Path", source, "-Name", secret,
                       "-LogFile", log]
            proc = subprocess.run(cmd, cwd=folder, env=env, capture_output=True, timeout=300)
            self.assertEqual(proc.returncode, 0, (edition, proc.stdout.decode(errors="replace"),
                                                  proc.stderr.decode(errors="replace")))
            console = (proc.stdout + proc.stderr).decode(errors="replace")
            self.assertEqual(console.count("log file: "), 2, (edition, console))
            results[edition] = read_log_lines(log)
        for edition, lines in results.items():
            with self.subTest(edition=edition):
                for line in lines:
                    self.assertRegex(line, LOG_LINE_RE)
                text = "\n".join(lines)
                self.assertNotIn(secret, text)
                self.assertIn(f"DISA STIG Conversion Tool {tool.TOOL_VERSION} (", lines[0])
                self.assertTrue(lines[-1].endswith(" s") and "run end: exit code 0;" in lines[-1])
                self.assertIn("2 file(s) written", lines[-1])
                for needle in (" parse  benchmark Test_Router_NDM_STIG ", " route  ", " scope  ",
                               " build  report ", " file   wrote "):
                    self.assertIn(needle, text)
        # The per-benchmark lines carry the same facts in both editions.
        def benchmark_lines(lines):
            # <24-char time stamp> <level 5> <component 6> <message>
            return sorted({line[38:] for line in lines
                           if line[31:37] == "parse " and line[38:].startswith("benchmark ")})
        self.assertEqual(len(benchmark_lines(results["py"])), 2)
        self.assertEqual(benchmark_lines(results["py"]), benchmark_lines(results["ps"]))


if __name__ == "__main__":
    unittest.main()

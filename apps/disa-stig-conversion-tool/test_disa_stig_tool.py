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
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
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


class FakeSwis:
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

    # -- SwisClient surface -------------------------------------------------
    def query(self, swql, parameters=None):
        self.calls.append(("query", swql, parameters))
        p = parameters or {}
        ids = {_n(i) for i in p.get("ids", [])}
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
        return getattr(self, "_" + verb)(*args)

    # -- Cirrus.PolicyReports verbs ------------------------------------------
    def _AddPolicyRule(self, rule):
        if self._rejecting() or not isinstance(rule, dict):
            raise tool.SwisError("HTTP 400 from AddPolicyRule\nValue cannot be null. Parameter name: input")
        self.rules[rule["RuleId"]] = rule["RuleName"]
        return f'"{rule["RuleId"]}"'

    def _AddPolicy(self, policy, import_flag):
        if self._rejecting():
            raise tool.SwisError("HTTP 400 from AddPolicy\ncannot unpackage parameter 0")
        pid = str(uuid.uuid4())
        self.add_policy(pid, policy["AssignedRulesList"], policy["PolicyName"])
        return pid

    def _AddPolicyReport(self, report, import_flag):
        if self._rejecting() or not isinstance(report, dict):
            raise tool.SwisError("HTTP 400 from AddPolicyReport\ncannot unpackage parameter 0")
        if report["Name"] in self.fail_add_report:
            raise tool.SwisError("HTTP 500 from AddPolicyReport\nsimulated server error")
        return self.add_report(report["Name"], report["AssignedPoliciesList"])

    def _GetPolicyReport(self, report_id, export_flag):
        rep = self.reports.get(report_id)
        if rep is None:
            return None
        pols = []
        for pid in rep["policies"]:
            pol = self.policies.get(pid, {"PolicyName": "?", "rules": []})
            entry = {"PolicyName": pol["PolicyName"],
                     "AssignedPolicyRules": [{"RuleId": r, "RuleName": self.rules.get(r)}
                                             for r in pol["rules"]]}
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
        return None

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
        ]
        spec = {"files": files,
                "memory": [dict(c, benchmarks=[ps_benchmark(b) for b in c["benchmarks"]]) for c in memory]}
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
        self.assertEqual(len(ps["memory"][0]["reports"][0]["Name"]), 250)


if __name__ == "__main__":
    unittest.main()

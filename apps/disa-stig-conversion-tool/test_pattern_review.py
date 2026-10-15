"""Tests for pattern_review.py: the prompt builder, the scorer and the schema round trip
through a fake client. No live API call: the fake client answers the batch from canned
messages, and the tests that need the Pydantic model skip when pydantic is not installed
(CI's runner has the standard library only)."""

import io
import json
import os
import shutil
import sys
import tempfile
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pattern_review as pr  # noqa: E402
import disa_stig_tool as tool  # noqa: E402

try:
    import pydantic  # noqa: F401
    HAVE_PYDANTIC = True
except ImportError:
    HAVE_PYDANTIC = False

DRAFT = {
    "title": "The Cisco router must be configured to have Internet Control Message Protocol "
             "(ICMP) mask replies disabled on all external interfaces.",
    "stig_id": "CISC-RT-000170",
    "check_content": "Review the router configuration.\n\ninterface GigabitEthernet0/0\n"
                     " no ip mask-reply\n\nIf ip mask-reply is enabled, this is a finding.",
    "fix_text": "Disable ICMP mask replies on all external interfaces.\n\nR1(config-if)#no ip "
                "mask-reply",
    "origin": "blocks", "must_exist": True, "advanced": True,
    "patterns": [{"pattern": "interface GigabitEthernet0/0\n no ip mask-reply", "type": "Like",
                  "must_contain": True, "condition": ""}],
}
SKIP_DRAFT = {"title": "Interview", "stig_id": "CISC-RT-000001", "origin": "sentinel",
              "check_content": "Interview the ISSM.", "fix_text": "Document it.",
              "must_exist": True, "advanced": False,
              "pattern": "STIG-MANUAL-REVIEW-V-2", "type": "Like"}

ANSWER_1 = {
    "outcome": "per-interface", "skip": False, "advanced": True, "must_exist": True,
    "patterns": [{"pattern": " ip mask-reply", "type": "Like", "must_contain": False,
                  "condition": ""}],
    "config_block": {"start": "^interface \\S+", "end": "!", "type": "Regex", "must_exist": True},
    "note": "ip mask-reply is off by default on IOS, so an explicit line is the finding.",
    "confidence": "medium",
    "review_reason": "The check says 'If ip mask-reply is enabled, this is a finding' and the "
                     "example shows the no form under a sample interface; the scope 'all external "
                     "interfaces' is inferred as every interface stanza.",
}
ANSWER_2 = {
    "outcome": "not-automatable", "skip": True, "advanced": False, "must_exist": True,
    "patterns": [], "config_block": None, "note": "An interview.", "confidence": "high",
    "review_reason": "The check is 'Interview the ISSM.'; there is nothing in a configuration "
                     "to match.",
}


def _obj(**kw):
    """A nested attribute object standing in for an SDK model (with model_dump)."""
    def conv(v):
        if hasattr(v, "model_dump"):
            return v.model_dump()
        if isinstance(v, list):
            return [conv(x) for x in v]
        return v

    def dump(mode="json"):
        return {k: conv(v) for k, v in kw.items()}
    ns = types.SimpleNamespace(**kw)
    ns.model_dump = dump
    return ns


def fake_message(answer, stop_reason="end_turn", model="claude-opus-5-5"):
    return _obj(model=model, stop_reason=stop_reason, stop_details=None,
                content=[_obj(type="text", text=json.dumps(answer))],
                usage=_obj(iterations=[]))


class FakeClient:
    """Enough of the Anthropic client for pattern_review.py: records the batch it was
    given and answers it from a {custom_id: message} table; a refusal in the table is
    retried through beta.messages.create, which answers from the retry table."""

    def __init__(self, answers, retries=None):
        self.answers, self.retries = answers, retries or {}
        self.created, self.retried = [], []
        self.messages = types.SimpleNamespace(batches=types.SimpleNamespace(
            create=self._create, retrieve=self._retrieve, results=self._results))
        self.beta = types.SimpleNamespace(messages=types.SimpleNamespace(create=self._beta_create))

    def _create(self, requests):
        self.created.append(list(requests))
        return _obj(id="msgbatch_test", processing_status="in_progress")

    def _retrieve(self, batch_id):
        return _obj(id=batch_id, processing_status="ended",
                    request_counts=_obj(processing=0, succeeded=len(self.answers), errored=0,
                                        canceled=0, expired=0))

    def _results(self, batch_id):
        for rid, msg in self.answers.items():
            if isinstance(msg, str):
                yield _obj(custom_id=rid, result=_obj(type=msg, error=_obj(type="server_error")))
            else:
                yield _obj(custom_id=rid, result=_obj(type="succeeded", message=msg))

    def _beta_create(self, **params):
        self.retried.append(params)
        rid = params["messages"][-1]["content"].split("\n", 1)[0][len("Rule: "):]
        return self.retries[rid]


class PromptTests(unittest.TestCase):
    def test_rule_prompt_carries_the_rule_and_its_draft(self):
        text = pr.rule_prompt("V-1", DRAFT)
        for piece in ("Rule: V-1", "Title: The Cisco router", "STIG id: CISC-RT-000170",
                      "Draft origin: blocks", "Check text:\nReview the router configuration.",
                      "Fix Text:\nDisable ICMP", "\"patterns\": [", "no ip mask-reply"):
            self.assertIn(piece, text)
        simple = pr.rule_prompt("V-2", SKIP_DRAFT)
        self.assertIn("\"pattern\": \"STIG-MANUAL-REVIEW-V-2\"", simple)
        self.assertNotIn("\"patterns\"", simple)

    def test_messages_are_example_then_rule(self):
        msgs = pr.build_messages("V-1", DRAFT)
        self.assertEqual([m["role"] for m in msgs], ["user", "assistant", "user"])
        self.assertIn("Rule: V-230158", msgs[0]["content"])
        self.assertIn("ipv6 access-list FILTER_IPV6", msgs[0]["content"])
        example = json.loads(msgs[1]["content"])
        self.assertEqual(example["outcome"], "illustrative")
        self.assertEqual(len(example["patterns"]), 2)
        self.assertNotIn("interface gigabitethernet1/0", msgs[1]["content"])
        self.assertIn("Rule: V-1", msgs[2]["content"])

    def test_system_prompt_states_the_contract(self):
        for piece in ("not-automatable", "absent", "present", "parameterized", "per-interface",
                      "illustrative", "Never invent a configuration line", "Keep the device dialect",
                      "One idea per pattern", "\"no \" lines", "Like versus Regex",
                      "ComplianceRulesWildcardsEnabled", "disa-stig-tool/pattern-drafts/2",
                      "review_reason", "config_block"):
            self.assertIn(piece, pr.SYSTEM_PROMPT)

    def test_prompt_hash_is_stable_and_tracks_the_prompt(self):
        self.assertEqual(pr.prompt_hash(), pr.prompt_hash())
        self.assertEqual(len(pr.prompt_hash()), 64)
        original = pr.SYSTEM_PROMPT
        try:
            pr.SYSTEM_PROMPT = original + "x"
            changed = pr.prompt_hash()
        finally:
            pr.SYSTEM_PROMPT = original
        self.assertNotEqual(changed, pr.prompt_hash())

    def test_dry_run_prints_prompts_without_a_client(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        path = os.path.join(tmp, "drafts.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"schema": "disa-stig-tool/pattern-drafts/1",
                       "rules": {"V-1": DRAFT, "V-2": SKIP_DRAFT}}, fh)
        out = []

        def no_client():
            raise AssertionError("dry run must not build a client")
        self.assertEqual(pr.main([path, "--dry-run", "--rules", "V-2"], client_factory=no_client,
                                 log=out.append), 0)
        text = "\n".join(out)
        self.assertIn("1 rule(s)", text)
        self.assertIn("# --- system prompt ---", text)
        self.assertIn("# --- rule V-2 ---", text)
        self.assertNotIn("# --- rule V-1 ---", text)
        with self.assertRaisesRegex(SystemExit, "not in the drafts file: V-9"):
            pr.main([path, "--dry-run", "--rules", "V-9"], client_factory=no_client, log=out.append)


class ScoreTests(unittest.TestCase):
    def test_normalize_makes_a_like_literal_equal_its_escaped_regex(self):
        self.assertEqual(pr.normalize_pattern("ip http  secure-server", "Like"),
                         pr.normalize_pattern("^ip\\ http secure\\-server$", "Regex"))

    def test_score_by_outcome_class(self):
        labelled = {"rules": {
            "V-1": {"pattern": "ip http secure-server", "type": "Like", "must_exist": True},
            "V-2": {"advanced": True, "patterns": [
                {"pattern": "no ip source-route", "type": "Like", "must_contain": True}]},
            "V-3": {"pattern": "login block-for 900 attempts 3 within 120", "type": "Like"},
            "V-4": {"skip": True},
            "V-5": {"pattern": "only here", "type": "Like"},
        }}
        reviewed = {"rules": {
            "V-1": {"outcome": "present", "confidence": "high", "pattern": "ip\\ http secure\\-server",
                    "type": "Regex", "must_exist": True},
            "V-2": {"outcome": "present", "confidence": "high", "advanced": True, "patterns": [
                {"pattern": "no ip source-route", "type": "Like", "must_contain": True,
                 "condition": ""}]},
            "V-3": {"outcome": "parameterized", "confidence": "high", "advanced": True, "patterns": [
                {"pattern": "login block-for \\d+ attempts 3 within \\d+", "type": "Regex",
                 "must_contain": True, "condition": ""}]},
            "V-4": {"outcome": "not-automatable", "confidence": "low", "skip": True},
            "V-6": {"outcome": "absent", "pattern": "x", "type": "Like"},
        }}
        report = pr.score(labelled, reviewed)
        self.assertEqual(report["by_outcome"]["present"],
                         {"exact": 1, "equivalent": 1, "disagreement": 0})
        self.assertEqual(report["by_outcome"]["parameterized"],
                         {"exact": 0, "equivalent": 0, "disagreement": 1})
        self.assertEqual(report["by_outcome"]["not-automatable"],
                         {"exact": 1, "equivalent": 0, "disagreement": 0})
        self.assertEqual(report["rules"]["V-1"]["verdict"], "equivalent")
        self.assertEqual(report["only_in_labelled"], ["V-5"])
        self.assertEqual(report["only_in_reviewed"], ["V-6"])
        text = pr.format_score(report)
        self.assertIn("present               1      1         0      2", text)
        self.assertIn("disagreements: V-3 (parameterized, high)", text)
        # A reviewed sentinel against a labelled pattern is a disagreement, not a skip match.
        self.assertEqual(pr.compare_patterns(pr.entry_patterns(labelled["rules"]["V-1"]),
                                             pr.entry_patterns({"pattern": "STIG-MANUAL-REVIEW-V-1",
                                                                "type": "Like"})), "disagreement")

    def test_score_command_writes_a_report(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        labelled = os.path.join(tmp, "labelled.json")
        reviewed = os.path.join(tmp, "reviewed.json")
        for path in (labelled, reviewed):
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"schema": "disa-stig-tool/pattern-drafts/2",
                           "rules": {"V-1": {"pattern": "a", "type": "Like"}}}, fh)
        out, report = [], os.path.join(tmp, "score.json")
        self.assertEqual(pr.main([reviewed, "--score", labelled, "--score-out", report],
                                 log=out.append), 0)
        self.assertIn("unclassified", out[0])
        with open(report, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["rules"]["V-1"]["verdict"], "exact")
        with self.assertRaisesRegex(SystemExit, "refusing to overwrite"):
            pr.main([reviewed, "--score", labelled, "--score-out", report], log=out.append)


@unittest.skipUnless(HAVE_PYDANTIC, "pydantic not installed")
class RoundTripTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.drafts = os.path.join(self.tmp, "drafts.json")
        with open(self.drafts, "w", encoding="utf-8") as fh:
            json.dump({"schema": "disa-stig-tool/pattern-drafts/1",
                       "rules": {"V-1": DRAFT, "V-2": SKIP_DRAFT}}, fh)

    def test_validate_review(self):
        review = pr.validate_review(json.dumps(ANSWER_1))
        self.assertEqual(review.config_block.start, "^interface \\S+")
        with self.assertRaisesRegex(ValueError, "patterns is empty while skip is false"):
            pr.validate_review(dict(ANSWER_1, patterns=[]))
        with self.assertRaisesRegex(ValueError, "skip is true but patterns were given"):
            pr.validate_review(dict(ANSWER_2, patterns=ANSWER_1["patterns"]))
        with self.assertRaises(ValueError):
            pr.validate_review(dict(ANSWER_1, confidence="sure"))
        with self.assertRaises(ValueError):
            pr.validate_review(dict(ANSWER_1, outcome="maybe"))
        with self.assertRaises(ValueError):
            pr.validate_review("not json")
        self.assertEqual(pr.output_schema()["type"], "object")
        self.assertIn("outcome", pr.output_schema()["properties"])

    def test_batch_round_trip_into_the_tool(self):
        """Submit through the fake client, write reviewed.json, and load it with the tool."""
        client = FakeClient({"V-1": fake_message(ANSWER_1), "V-2": fake_message(ANSWER_2)})
        out, reviewed = [], os.path.join(self.tmp, "reviewed.json")
        self.assertEqual(pr.main([self.drafts, "--out", reviewed, "--poll", "0"],
                                 client_factory=lambda: client, log=out.append), 0)
        # One request per rule, keyed by rule id, with the schema and the cached system prompt.
        requests = client.created[0]
        self.assertEqual([r["custom_id"] for r in requests], ["V-1", "V-2"])
        params = requests[0]["params"]
        self.assertEqual(params["model"], "claude-opus-5-5")
        self.assertEqual(params["output_config"]["effort"], "high")
        self.assertEqual(params["output_config"]["format"]["type"], "json_schema")
        self.assertEqual(params["system"][0]["cache_control"], {"type": "ephemeral"})
        self.assertEqual(len(params["messages"]), 3)
        self.assertNotIn("thinking", params)
        with open(reviewed, encoding="utf-8") as fh:
            doc = json.load(fh)
        self.assertEqual(doc["schema"], "disa-stig-tool/pattern-drafts/2")
        self.assertEqual(doc["review"]["model"], "claude-opus-5-5")
        self.assertEqual(doc["review"]["prompt_hash"], pr.prompt_hash())
        self.assertEqual(doc["review"]["batch_id"], "msgbatch_test")
        v1, v2 = doc["rules"]["V-1"], doc["rules"]["V-2"]
        self.assertEqual((v1["outcome"], v1["confidence"], v1["advanced"], v1["skip"]),
                         ("per-interface", "medium", True, False))
        self.assertEqual(v1["patterns"], [{"pattern": " ip mask-reply", "type": "Like",
                                           "must_contain": False, "condition": ""}])
        self.assertEqual(v1["config_block"]["start"], "^interface \\S+")
        self.assertTrue(v1["note"].startswith("reviewed 20"))
        self.assertIn("by claude-opus-5-5 (prompt " + pr.prompt_hash()[:12], v1["note"])
        self.assertTrue(v1["note"].endswith("the finding."))
        self.assertEqual((v2["skip"], v2["outcome"]), (True, "not-automatable"))
        self.assertNotIn("patterns", v2)
        # The raw results sit beside the reviewed file; neither is ever overwritten.
        raw = os.path.join(self.tmp, "reviewed.batch-results.jsonl")
        with open(raw, encoding="utf-8") as fh:
            self.assertEqual(len(fh.read().splitlines()), 2)
        with self.assertRaisesRegex(SystemExit, "refusing to overwrite"):
            pr.main([self.drafts, "--out", reviewed], client_factory=lambda: client, log=out.append)
        # The tool reads the file: V-1 follows it, V-2 is left to the mode, and the note,
        # confidence, reason and config block reach the rule.
        drafts = tool.load_pattern_drafts(reviewed)
        self.assertEqual(sorted(drafts), ["V-1"])
        rule = tool.rule_object({"vuln_id": "V-1", "rule_id": "SV-1r1_rule", "stig_id": "CISC-RT-000170",
                                 "severity": "medium", "title": "T", "discussion": "d",
                                 "check_content": DRAFT["check_content"], "oval_ref": "",
                                 "fix_text": "Fix it.", "ccis": [], "display_id": "V-1"},
                                "G", "manual", drafts=drafts)
        self.assertTrue(rule["AdvancedMode"])
        self.assertEqual(rule["MultiLineRulePatterns"][0]["Pattern"], " ip mask-reply")
        self.assertFalse(rule["MultiLineRulePatterns"][0]["Criteria"])
        self.assertEqual((rule["ConfigBlockStart"], rule["ConfigBlockEnd"],
                          rule["ConfigBlockPatternType"], rule["ConfigBlockMustExist"]),
                         ("^interface \\S+", "!", "Regex", True))
        self.assertIn("PATTERN FROM DRAFTS FILE: reviewed 20", rule["Comments"])
        self.assertIn("Review confidence: medium.", rule["Comments"])
        self.assertIn("Review reason: The check says", rule["Comments"])

    def test_refusal_is_retried_with_the_fallback_and_logged(self):
        fallback_msg = fake_message(ANSWER_1, model="claude-opus-4-8")
        fallback_msg.usage = _obj(iterations=[_obj(type="fallback_message")])
        client = FakeClient({"V-1": fake_message({}, stop_reason="refusal"),
                             "V-2": "errored"},
                            retries={"V-1": fallback_msg})
        out, reviewed = [], os.path.join(self.tmp, "reviewed.json")
        pr.main([self.drafts, "--out", reviewed, "--poll", "0"], client_factory=lambda: client,
                log=out.append)
        self.assertEqual(client.retried[0]["betas"], [pr.FALLBACK_BETA])
        self.assertEqual(client.retried[0]["fallbacks"], "default")
        with open(reviewed, encoding="utf-8") as fh:
            doc = json.load(fh)
        self.assertEqual(doc["review"]["fallback_rules"], ["V-1"])
        self.assertEqual(doc["review"]["failed_rules"], {"V-2": "errored: server_error"})
        self.assertIn("by claude-opus-4-8 (prompt", doc["rules"]["V-1"]["note"])
        self.assertNotIn("V-2", doc["rules"])
        self.assertIn("1 answered by a fallback model; 1 failed", "\n".join(out))

    def test_invalid_answer_is_a_failure_not_a_crash(self):
        client = FakeClient({"V-1": fake_message(dict(ANSWER_1, confidence="sure")),
                             "V-2": fake_message(ANSWER_2, stop_reason="max_tokens")})
        out, reviewed = [], os.path.join(self.tmp, "reviewed.json")
        pr.main([self.drafts, "--out", reviewed, "--poll", "0"], client_factory=lambda: client,
                log=out.append)
        with open(reviewed, encoding="utf-8") as fh:
            doc = json.load(fh)
        self.assertEqual(doc["rules"], {})
        self.assertIn("invalid answer", doc["review"]["failed_rules"]["V-1"])
        self.assertEqual(doc["review"]["failed_rules"]["V-2"], "stop_reason max_tokens")

    def test_no_wait_and_batch_id(self):
        client = FakeClient({"V-1": fake_message(ANSWER_1), "V-2": fake_message(ANSWER_2)})
        out, reviewed = [], os.path.join(self.tmp, "reviewed.json")
        pr.main([self.drafts, "--out", reviewed, "--no-wait"], client_factory=lambda: client,
                log=out.append)
        self.assertFalse(os.path.exists(reviewed))
        self.assertIn("--batch-id msgbatch_test", "\n".join(out))
        pr.main([self.drafts, "--out", reviewed, "--batch-id", "msgbatch_test", "--poll", "0"],
                client_factory=lambda: client, log=out.append)
        self.assertEqual(len(client.created), 1)
        self.assertTrue(os.path.exists(reviewed))


if __name__ == "__main__":
    unittest.main()

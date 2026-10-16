#!/usr/bin/env python3
"""Pattern review task: turn a pattern-drafts file into reviewed NCM patterns with Claude.

Step 2 of the pipeline in pattern-review-task.md. Reads a drafts file written by
``disa_stig_tool.py convert <zip> --mode blocks --write-pattern-drafts drafts.json``,
builds one request per rule (the contract as the system prompt, one worked example, then
the rule), submits them as a Message Batch with structured output, and writes
``reviewed.json`` in pattern-drafts schema 2 beside the batch's raw results. The tool
then validates the file with ``--pattern-drafts reviewed.json``; nothing here touches the
SolarWinds server.

    python pattern_review.py drafts.json --out reviewed.json         # submit, wait, write
    python pattern_review.py drafts.json --dry-run                   # print the prompts
    python pattern_review.py drafts.json --out reviewed.json --no-wait   # submit and exit
    python pattern_review.py drafts.json --out reviewed.json --batch-id msgbatch_...
    python pattern_review.py --score labelled.json reviewed.json     # compare two files

Python edition only. Needs ``anthropic`` and ``pydantic`` for a live run; ``--dry-run``
and ``--score`` need neither. Credentials come from the SDK's usual sources
(ANTHROPIC_API_KEY, or an ``ant auth login`` profile).
"""

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import sys
import time

TASK_VERSION = "1.0.0"
DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_EFFORT = "high"
MAX_TOKENS = 16000
FALLBACK_BETA = "server-side-fallback-2026-07-01"
SCHEMA_OUT = "disa-stig-tool/pattern-drafts/2"
SCHEMAS_IN = ("disa-stig-tool/pattern-drafts/1", SCHEMA_OUT)
OUTCOMES = ("not-automatable", "absent", "present", "parameterized", "per-interface",
            "illustrative")
CONFIDENCE = ("low", "medium", "high")

# ---------------------------------------------------------------------------
# The prompt: the contract from pattern-review-task.md ("What the task must decide per
# rule" and "File contract"), then one worked example. Changing a character here changes
# PROMPT_HASH, which every note records, so a reviewed file says which prompt made it.
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You review one DISA STIG rule at a time and decide how SolarWinds NCM should check a
Cisco device configuration for it. NCM runs each rule as a pattern search over the
device's backed-up running configuration: a simple pattern (Like, or Regex) that must
or must not exist, or an Advanced Config Search of several patterns joined with AND/OR,
optionally scoped to a configuration block (a stanza such as every interface).

You receive the rule's id, title, STIG id, check text, Fix Text and the current draft
patterns the tool extracted mechanically from the check text's configuration examples.
Those drafts are not trusted: their values are the STIG's own examples (2001::1:0:22/64,
FILTER_IPV6, x.x.x.x), some blocks are illustrations rather than requirements, and a
check that says "must not be configured" still produced a "must contain" block.

## Classify the rule into exactly one outcome, in this order

| outcome | when | what you write |
| --- | --- | --- |
| not-automatable | the check is an interview, a document review, a vendor-support question, a review of logs or of a server outside the device, or applies only in a circumstance NCM cannot see ("if the router is a PE router ...") | skip true plus a review_reason; patterns empty. The tool keeps its sentinel so the rule flags for manual review, which is the honest state |
| absent | the check says a line or feature must NOT be present ("if ... is configured, this is a finding", "the following commands should not be in the configuration") | the lines that must be absent, each a pattern with must_contain false, OR-joined when any one of them is a finding; must_exist true |
| present | the check shows lines that must be present and says so plainly | the lines, each must_contain true, AND-joined; must_exist true |
| parameterized | a line must be present with a value the organization chooses (a timeout, an address, an ACL name) | a Regex pattern with the value generalized (ip http max-connections \\d+, access-class \\S+ in), never a literal from the STIG example |
| per-interface | the requirement applies to every interface, VLAN or line of a kind ("on all interfaces") | the pattern plus a config_block: start a regex for the stanza opener (^interface \\S+), end "!", type Regex, must_exist as the check implies |
| illustrative | a block in the draft is an example of the surrounding prose, not the requirement (a sample interface, a sample ip pim rp-address) | drop that block, keep the others, and name the dropped block in review_reason |

## Rules that apply to every outcome

- Never invent a configuration line. Every pattern must appear in the check text, or be
  the check text's line with a value generalized. If the check names a command only in
  prose ("verify that NTP authentication is enabled"), you may propose the command
  (ntp authenticate) but must set confidence low and say the line is inferred.
- Keep the device dialect. IOS and IOS-XE, NX-OS, ASA and IOS-XR spell the same thing
  differently; write what the check text shows and do not translate.
- One idea per pattern. Keep a multi-line block only when the lines must appear together
  in that order (an ACL and its entries); otherwise split it, so one missing line reads
  as one violation.
- "no " lines. A check that requires "no ip source-route" is an absent rule for
  "ip source-route" when the platform omits defaults from the running config, and a
  present rule for the literal "no ip source-route" when it does not. Say which you chose
  and why; this is the most common place a reviewer overrides you.
- Like versus Regex. Like for literal lines; Regex only when a value is generalized, with
  the literal parts escaped. A literal containing * or ? becomes an escaped Regex,
  because NCM's Like treats them as wildcards only when the server's
  ComplianceRulesWildcardsEnabled setting is on.
- Confidence and reason on every rule, so the human review can be sorted: high (lines
  verbatim from the check, polarity stated plainly), medium (polarity or scope
  inferred), low (command inferred, or the check is ambiguous).
- Indentation matters to NCM's multi-line matching: keep a sub-command's leading space
  exactly as the configuration shows it (" ipv6 traffic-filter FILTER_IPV6 in" under an
  interface), and separate the lines of one pattern with \\n.

## What you write

One JSON object, the rule's entry in the pattern-drafts file (schema
disa-stig-tool/pattern-drafts/2):

- outcome: one of not-automatable, absent, present, parameterized, per-interface,
  illustrative.
- skip: true only for not-automatable; then patterns is empty.
- advanced: true when patterns has more than one entry or a config_block is set; a single
  pattern may still be advanced.
- must_exist: true when the rule reports a violation if the pattern search fails.
- patterns: list of {pattern, type (Like|Regex), must_contain, condition}; condition is
  "" on the first pattern and AND or OR on the others.
- config_block: null, or {start, end, type (Like|Regex), must_exist} for per-interface.
- note: one sentence for the rule's Comments in NCM: what you decided and what a reviewer
  should check. The tool prefixes it with the model, prompt hash and date.
- confidence: low, medium or high.
- review_reason: why, in two or three sentences, quoting the check text that decided it.

Reply with the JSON object only.
"""

# The worked example: V-230158 (Cisco IOS Router RTR, CISC-RT-000398). Three blocks in,
# the two real ones kept with the ACL name generalized, the illustrative interface block
# dropped and the reason given.
EXAMPLE_RULE = {
    "id": "V-230158",
    "title": "The Cisco perimeter router must be configured to drop IPv6 packets containing a "
             "Hop-by-Hop or Destination Option extension header with an undefined option type.",
    "stig_id": "CISC-RT-000398",
    "check_content": (
        "This requirement is not applicable for the DODIN Backbone. \n\n"
        "Review the router configuration to determine if it is compliant with this requirement.  \n\n"
        "Step 1: Verify that an inbound IPv6 ACL has been configured on the external interface.\n\n"
        "interface gigabitethernet1/0\n ipv6 address 2001::1:0:22/64\n ipv6 traffic-filter FILTER_IPV6 in\n\n"
        "Step 2: Verify that the ACL drops IPv6 packets containing a Destination Option header as "
        "shown in the example below.\n\n"
        "ipv6 access-list FILTER_IPV6\n deny 60 any any dest-option log\n deny hbh any any dest-option log\n"
        " permit ipv6 …\n …\n …\n …\n deny ipv6 any any log\n\n"
        "Note: Cisco has deprecated the dest-option-type command used to filter by option type within "
        "the Destination Option and Hop-by-Hop header. Therefore, all packets with the Destination "
        "Option header and Hop-by-Hop options must be dropped.\n\n"
        "If the router is not configured to drop IPv6 packets containing a Destination Option header, "
        "this is a finding."),
    "fix_text": (
        "Configure the router to drop all inbound IPv6 packets containing destination option type "
        "values regardless of whether they appear in a Hop-by-Hop or Destination Option header as "
        "shown in the example below.\n\n"
        "R1(config)#ipv6 access-list FILTER_IPV6\nR1(config-ipv6-acl)#deny 60 any any dest-option log\n"
        "R1(config-ipv6-acl)#deny hbh any any dest-option log\nR1(config-ipv6-acl)#permit …\n"
        "…\n…\n…\nR1(config-ipv6-acl)#deny ipv6 any any log\nR1(config-ipv6-acl)#exit\n"
        "R1(config)#int g1/0\nR1(config-if)#ipv6 traffic-filter FILTER_IPV6\nR1(config-if)#end"),
    "origin": "blocks",
    "must_exist": True,
    "advanced": True,
    "patterns": [
        {"pattern": "interface gigabitethernet1/0\n ipv6 address 2001::1:0:22/64\n"
                    " ipv6 traffic-filter FILTER_IPV6 in",
         "type": "Like", "must_contain": True, "condition": ""},
        {"pattern": "ipv6 access-list FILTER_IPV6\n deny 60 any any dest-option log\n"
                    " deny hbh any any dest-option log\n permit ipv6",
         "type": "Like", "must_contain": True, "condition": "AND"},
        {"pattern": " deny ipv6 any any log", "type": "Like", "must_contain": True,
         "condition": "AND"},
    ],
}

EXAMPLE_ANSWER = {
    "outcome": "illustrative",
    "skip": False,
    "advanced": True,
    "must_exist": True,
    "patterns": [
        {"pattern": "ipv6 access-list \\S+\\n deny 60 any any dest-option( log)?\\n"
                    " deny hbh any any dest-option( log)?",
         "type": "Regex", "must_contain": True, "condition": ""},
        {"pattern": " deny ipv6 any any log", "type": "Like", "must_contain": True,
         "condition": "AND"},
    ],
    "config_block": None,
    "note": "Kept the IPv6 ACL's two dest-option deny lines (ACL name and the optional log "
            "keyword generalized) and the closing deny; dropped the sample interface block. "
            "Reviewer: confirm the ACL is applied inbound on the external interface, which "
            "this rule does not check.",
    "confidence": "medium",
    "review_reason": "The requirement is in Step 2: 'Verify that the ACL drops IPv6 packets "
                     "containing a Destination Option header', with the deny 60 and deny hbh "
                     "lines shown verbatim; FILTER_IPV6 is the STIG's example name, so the ACL "
                     "name is generalized. Step 1's interface block (gigabitethernet1/0, "
                     "2001::1:0:22/64) illustrates where such an ACL is applied and names an "
                     "address the organization chooses, so it is dropped rather than matched "
                     "literally. The ' permit ipv6 ...' line is elided in the STIG and cannot be "
                     "matched; the ' deny ipv6 any any log' closing line is kept as its own "
                     "pattern. Medium: the interface application is required by the prose but "
                     "cannot be expressed without knowing the external interface.",
}

ENTRY_MEMBERS = ("outcome", "skip", "advanced", "must_exist", "patterns", "config_block", "note",
                 "confidence", "review_reason")


def rule_prompt(rule_id, entry):
    """The user message for one rule: id, title, STIG id, check text, Fix Text, the draft."""
    draft = {"must_exist": entry.get("must_exist", True), "advanced": entry.get("advanced", False)}
    if entry.get("patterns") is not None:
        draft["patterns"] = entry["patterns"]
    else:
        draft["pattern"] = entry.get("pattern", "")
        draft["type"] = entry.get("type", "Like")
    return (f"Rule: {rule_id}\n"
            f"Title: {entry.get('title', '')}\n"
            f"STIG id: {entry.get('stig_id', '')}\n"
            f"Draft origin: {entry.get('origin', '')}\n\n"
            f"Check text:\n{entry.get('check_content', '')}\n\n"
            f"Fix Text:\n{entry.get('fix_text', '')}\n\n"
            f"Current draft (JSON):\n{json.dumps(draft, ensure_ascii=False, indent=1)}\n")


def build_messages(rule_id, entry):
    """The messages for one request: the worked example as a user/assistant pair, then the rule."""
    return [
        {"role": "user", "content": rule_prompt(EXAMPLE_RULE["id"], EXAMPLE_RULE)},
        {"role": "assistant", "content": json.dumps(EXAMPLE_ANSWER, ensure_ascii=False)},
        {"role": "user", "content": rule_prompt(rule_id, entry)},
    ]


def prompt_hash():
    """sha256 of the system prompt and the worked example, so a reviewed file says which
    prompt produced it."""
    h = hashlib.sha256()
    h.update(SYSTEM_PROMPT.encode("utf-8"))
    h.update(json.dumps(build_messages(EXAMPLE_RULE["id"], EXAMPLE_RULE)[:2],
                        ensure_ascii=False, sort_keys=True).encode("utf-8"))
    return h.hexdigest()


# ---------------------------------------------------------------------------
# The response model (Pydantic, loaded lazily so --dry-run and --score need nothing).
# ---------------------------------------------------------------------------

_MODELS = {}


def response_models():
    """RuleReview and its parts as Pydantic models; the schema the batch asks for."""
    if _MODELS:
        return _MODELS
    try:
        from pydantic import BaseModel, Field
        from typing import List, Literal, Optional
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("pattern_review.py needs pydantic for a live run: pip install anthropic "
                         f"({exc})")

    class Pattern(BaseModel):
        pattern: str = Field(description="The configuration line or lines, \\n between lines.")
        type: Literal["Like", "Regex"]
        must_contain: bool
        condition: Literal["", "AND", "OR"] = Field(
            description="Empty on the first pattern; AND or OR on the others.")

    class ConfigBlock(BaseModel):
        start: str
        end: str
        type: Literal["Like", "Regex"]
        must_exist: bool

    class RuleReview(BaseModel):
        outcome: Literal[OUTCOMES]
        skip: bool
        advanced: bool
        must_exist: bool
        patterns: List[Pattern]
        config_block: Optional[ConfigBlock]
        note: str
        confidence: Literal[CONFIDENCE]
        review_reason: str

    _MODELS.update(Pattern=Pattern, ConfigBlock=ConfigBlock, RuleReview=RuleReview)
    return _MODELS


def validate_review(obj):
    """A RuleReview from a dict or a JSON string; ValueError with the reason when it is not
    one (a pattern list that is empty while skip is false counts as invalid)."""
    RuleReview = response_models()["RuleReview"]
    try:
        review = (RuleReview.model_validate_json(obj) if isinstance(obj, str)
                  else RuleReview.model_validate(obj))
    except Exception as exc:  # pydantic.ValidationError
        raise ValueError(str(exc)) from exc
    if not review.skip and not review.patterns:
        raise ValueError("patterns is empty while skip is false")
    if review.skip and review.patterns:
        raise ValueError("skip is true but patterns were given")
    return review


def review_to_entry(review, model, phash, date):
    """A validated RuleReview as the pattern-drafts schema-2 entry the tool reads."""
    data = review.model_dump()
    stamp = f"reviewed {date} by {model} (prompt {phash[:12]}, pattern_review {TASK_VERSION})"
    note = data["note"].strip()
    entry = {"outcome": data["outcome"], "confidence": data["confidence"],
             "review_reason": data["review_reason"],
             "note": f"{stamp}: {note}" if note else stamp}
    if data["skip"]:
        entry["skip"] = True
        return entry
    entry["skip"] = False
    entry["advanced"] = bool(data["advanced"] or len(data["patterns"]) > 1 or data["config_block"])
    entry["must_exist"] = data["must_exist"]
    pats = []
    for i, p in enumerate(data["patterns"]):
        pats.append({"pattern": p["pattern"], "type": p["type"], "must_contain": p["must_contain"],
                     "condition": "" if i == 0 else (p["condition"] or "AND")})
    if entry["advanced"]:
        entry["patterns"] = pats
    else:
        entry["pattern"], entry["type"] = pats[0]["pattern"], pats[0]["type"]
    if data["config_block"]:
        entry["config_block"] = data["config_block"]
    return entry


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------

def load_drafts(path):
    with open(path, encoding="utf-8-sig") as fh:
        doc = json.load(fh)
    if not isinstance(doc, dict) or not isinstance(doc.get("rules"), dict):
        raise SystemExit(f"{path}: not a pattern-drafts file (an object with a \"rules\" object)")
    if doc.get("schema") not in (None,) + SCHEMAS_IN:
        raise SystemExit(f"{path}: schema {doc.get('schema')!r} is not one of {', '.join(SCHEMAS_IN)}")
    return doc


def select_rules(doc, only=None, limit=0):
    rules = doc["rules"]
    if only:
        missing = [r for r in only if r not in rules]
        if missing:
            raise SystemExit(f"rule(s) not in the drafts file: {', '.join(missing)}")
        rules = {r: rules[r] for r in only}
    if limit:
        rules = dict(list(rules.items())[:limit])
    return rules


def refuse_overwrite(path):
    if os.path.exists(path):
        raise SystemExit(f"refusing to overwrite {path}: a reviewed file is never rewritten in "
                         "place; pass another --out")


def write_json(path, doc):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def reviewed_document(entries, model, phash, date, batch_id, fallbacks, failures, source):
    return {
        "schema": SCHEMA_OUT,
        "about": ("Written by pattern_review.py: one Claude review per rule, as a pattern-drafts "
                  "file for disa_stig_tool.py --pattern-drafts. Every entry is a proposal: read "
                  "the low-confidence and absent rules first. outcome is this task's own member "
                  "and is ignored by the tool."),
        "review": {"task_version": TASK_VERSION, "model": model, "prompt_hash": phash,
                   "date": date, "batch_id": batch_id, "source": os.path.basename(source),
                   "rules_reviewed": len(entries), "fallback_rules": sorted(fallbacks),
                   "failed_rules": {k: failures[k] for k in sorted(failures)}},
        "rules": entries,
    }


# ---------------------------------------------------------------------------
# The batch
# ---------------------------------------------------------------------------

def request_params(rule_id, entry, model, effort, schema):
    """The Messages API parameters for one rule (a plain dict; the SDK's typed Request
    wraps it)."""
    return {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "system": [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        "messages": build_messages(rule_id, entry),
        "output_config": {"effort": effort, "format": {"type": "json_schema", "schema": schema}},
    }


def output_schema():
    """The RuleReview JSON schema in the shape the API accepts."""
    from anthropic import transform_schema
    return transform_schema(response_models()["RuleReview"])


def submit_batch(client, rules, model, effort):
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request
    schema = output_schema()
    requests = [Request(custom_id=rid,
                        params=MessageCreateParamsNonStreaming(
                            **request_params(rid, entry, model, effort, schema)))
                for rid, entry in rules.items()]
    batch = client.messages.batches.create(requests=requests)
    return batch


def wait_for_batch(client, batch_id, poll_seconds, log=print):
    while True:
        batch = client.messages.batches.retrieve(batch_id)
        counts = batch.request_counts
        log(f"batch {batch_id}: {batch.processing_status}; processing {counts.processing}, "
            f"succeeded {counts.succeeded}, errored {counts.errored}, canceled {counts.canceled}, "
            f"expired {counts.expired}")
        if batch.processing_status == "ended":
            return batch
        time.sleep(poll_seconds)


def message_text(message):
    return "".join(getattr(b, "text", "") for b in message.content if getattr(b, "type", "") == "text")


def retry_with_fallback(client, rule_id, entry, model, effort, schema):
    """A rule the batch answered with a refusal, re-sent one at a time with the server-side
    fallback (the Batches API rejects the fallbacks parameter, so it goes through
    messages.create). Returns (message, fell_back)."""
    params = request_params(rule_id, entry, model, effort, schema)
    message = client.beta.messages.create(betas=[FALLBACK_BETA], fallbacks="default", **params)
    iterations = getattr(message.usage, "iterations", None) or []
    fell_back = any(getattr(it, "type", "") == "fallback_message" for it in iterations)
    return message, fell_back


def collect_results(client, batch_id, rules, model, effort, raw_path, log=print):
    """Walk the batch results, validate every answer, retry refusals with the fallback, and
    return (entries, fallbacks, failures). The raw results are appended to raw_path as
    JSON lines as they arrive."""
    phash, date = prompt_hash(), _dt.date.today().isoformat()
    schema = output_schema()
    entries, fallbacks, failures = {}, set(), {}
    with open(raw_path, "a", encoding="utf-8", newline="\n") as raw:
        for result in client.messages.batches.results(batch_id):
            rid = result.custom_id
            raw.write(json.dumps(result.model_dump(mode="json"), ensure_ascii=False) + "\n")
            kind = result.result.type
            if kind != "succeeded":
                err = getattr(result.result, "error", None)
                failures[rid] = f"{kind}" + (f": {getattr(err, 'type', '')}" if err else "")
                log(f"{rid}: {failures[rid]}")
                continue
            message = result.result.message
            fell_back = False
            if message.stop_reason == "refusal":
                if rid not in rules:
                    failures[rid] = "refusal (rule not in the drafts file, not retried)"
                    continue
                details = getattr(message, "stop_details", None)
                log(f"{rid}: refusal ({getattr(details, 'category', None)}); retrying with fallbacks")
                try:
                    message, fell_back = retry_with_fallback(client, rid, rules[rid], model, effort,
                                                             schema)
                except Exception as exc:
                    failures[rid] = f"refusal; retry failed: {exc}"
                    log(f"{rid}: {failures[rid]}")
                    continue
                raw.write(json.dumps({"custom_id": rid, "retry": message.model_dump(mode="json")},
                                     ensure_ascii=False) + "\n")
                if message.stop_reason == "refusal":
                    failures[rid] = "refusal on the fallback too"
                    log(f"{rid}: {failures[rid]}")
                    continue
                if fell_back:
                    fallbacks.add(rid)
            if message.stop_reason not in ("end_turn", "stop_sequence"):
                failures[rid] = f"stop_reason {message.stop_reason}"
                log(f"{rid}: {failures[rid]}")
                continue
            try:
                review = validate_review(message_text(message))
            except ValueError as exc:
                failures[rid] = f"invalid answer: {exc}"
                log(f"{rid}: {failures[rid]}")
                continue
            # A fallback answer is stamped with the model that actually wrote it.
            used_model = str(message.model) if fell_back else model
            entries[rid] = review_to_entry(review, used_model, phash, date)
    return entries, fallbacks, failures


# ---------------------------------------------------------------------------
# Scoring against a labelled file
# ---------------------------------------------------------------------------

def entry_patterns(entry):
    """A drafts entry's patterns as a list of (pattern, type, must_contain) tuples, or None
    for a skipped rule."""
    if entry.get("skip"):
        return None
    if entry.get("patterns") is not None:
        return [(str(p.get("pattern", "")), str(p.get("type", "Like")),
                 bool(p.get("must_contain", True))) for p in entry["patterns"]]
    pattern = str(entry.get("pattern", ""))
    if pattern.startswith("STIG-MANUAL-REVIEW-"):
        return None
    return [(pattern, str(entry.get("type", "Like")), bool(entry.get("must_exist", True)))]


def normalize_pattern(pattern, ptype):
    """A pattern in a form where a Like literal and the Regex that escapes it compare equal:
    whitespace collapsed, case folded, Regex escapes removed and anchors dropped."""
    text = pattern
    if ptype == "Regex":
        text = re.sub(r"\\(.)", r"\1", text)
        text = text.replace("^", "").replace("$", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = "\n".join(line.strip() for line in text.split("\n")).strip()
    return text.lower()


def compare_patterns(labelled, reviewed):
    """exact, equivalent or disagreement for one rule."""
    if labelled is None or reviewed is None:
        return "exact" if labelled is None and reviewed is None else "disagreement"
    if sorted(labelled) == sorted(reviewed):
        return "exact"
    norm = lambda pats: sorted((normalize_pattern(p, t), mc) for p, t, mc in pats)
    if norm(labelled) == norm(reviewed):
        return "equivalent"
    return "disagreement"


def score(labelled_doc, reviewed_doc):
    """{outcome class: {exact, equivalent, disagreement}} plus the per-rule verdicts; rules
    present in one file only are reported, not scored."""
    labelled, reviewed = labelled_doc["rules"], reviewed_doc["rules"]
    by_class, verdicts = {}, {}
    for rid in sorted(set(labelled) & set(reviewed)):
        verdict = compare_patterns(entry_patterns(labelled[rid]), entry_patterns(reviewed[rid]))
        klass = reviewed[rid].get("outcome") or "unclassified"
        by_class.setdefault(klass, {"exact": 0, "equivalent": 0, "disagreement": 0})[verdict] += 1
        verdicts[rid] = {"verdict": verdict, "outcome": klass,
                         "confidence": reviewed[rid].get("confidence", "")}
    return {"by_outcome": by_class, "rules": verdicts,
            "only_in_labelled": sorted(set(labelled) - set(reviewed)),
            "only_in_reviewed": sorted(set(reviewed) - set(labelled))}


def format_score(report):
    lines = [f"{'outcome':<16} {'exact':>6} {'equiv':>6} {'disagree':>9} {'total':>6}"]
    totals = {"exact": 0, "equivalent": 0, "disagreement": 0}
    for klass in sorted(report["by_outcome"]):
        c = report["by_outcome"][klass]
        for k in totals:
            totals[k] += c[k]
        lines.append(f"{klass:<16} {c['exact']:>6} {c['equivalent']:>6} {c['disagreement']:>9} "
                     f"{sum(c.values()):>6}")
    lines.append(f"{'all':<16} {totals['exact']:>6} {totals['equivalent']:>6} "
                 f"{totals['disagreement']:>9} {sum(totals.values()):>6}")
    disagreements = [rid for rid, v in report["rules"].items() if v["verdict"] == "disagreement"]
    if disagreements:
        lines.append("disagreements: " + ", ".join(
            f"{rid} ({report['rules'][rid]['outcome']}, {report['rules'][rid]['confidence'] or '?'})"
            for rid in disagreements))
    if report["only_in_labelled"]:
        lines.append("only in the labelled file: " + ", ".join(report["only_in_labelled"]))
    if report["only_in_reviewed"]:
        lines.append("only in the reviewed file: " + ", ".join(report["only_in_reviewed"]))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("drafts", nargs="?", help="the pattern-drafts file to review")
    p.add_argument("--out", metavar="FILE", help="the reviewed file to write (default: "
                   "<drafts>.reviewed.json); never overwritten")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--effort", default=DEFAULT_EFFORT,
                   choices=("low", "medium", "high", "xhigh", "max"))
    p.add_argument("--rules", metavar="IDS", help="comma-separated rule ids to review (default all)")
    p.add_argument("--limit", type=int, default=0, help="review only the first N rules")
    p.add_argument("--dry-run", action="store_true",
                   help="print the system prompt and every per-rule prompt; no API call")
    p.add_argument("--no-wait", action="store_true",
                   help="submit the batch, print its id and exit; collect later with --batch-id")
    p.add_argument("--batch-id", metavar="ID",
                   help="collect the results of an already-submitted batch instead of submitting")
    p.add_argument("--poll", type=int, default=60, metavar="SECONDS",
                   help="how often to poll the batch (default 60)")
    p.add_argument("--score", metavar="LABELLED", help="compare a reviewed file (the positional "
                   "argument) with this labelled pattern-drafts file, pattern by pattern")
    p.add_argument("--score-out", metavar="FILE", help="with --score: also write the report as JSON")
    return p.parse_args(argv)


def main(argv=None, client_factory=None, log=print):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not args.drafts:
        raise SystemExit("a drafts file is required (or --score LABELLED REVIEWED)")
    if args.score:
        report = score(load_drafts(args.score), load_drafts(args.drafts))
        log(format_score(report))
        if args.score_out:
            refuse_overwrite(args.score_out)
            write_json(args.score_out, report)
        return 0

    doc = load_drafts(args.drafts)
    only = [r.strip() for r in args.rules.split(",") if r.strip()] if args.rules else None
    rules = select_rules(doc, only, args.limit)
    phash = prompt_hash()
    if args.dry_run:
        log(f"# model {args.model}, effort {args.effort}, prompt {phash}, {len(rules)} rule(s)")
        log("# --- system prompt ---")
        log(SYSTEM_PROMPT)
        log("# --- worked example (user, then assistant) ---")
        for m in build_messages("", {})[:2]:
            log(f"[{m['role']}]\n{m['content']}")
        for rid, entry in rules.items():
            log(f"# --- rule {rid} ---\n{rule_prompt(rid, entry)}")
        return 0

    out = args.out or re.sub(r"\.json$", "", args.drafts) + ".reviewed.json"
    refuse_overwrite(out)
    raw_path = re.sub(r"\.json$", "", out) + ".batch-results.jsonl"
    refuse_overwrite(raw_path)
    if client_factory is None:
        import anthropic
        client = anthropic.Anthropic()
    else:
        client = client_factory()

    if args.batch_id:
        batch_id = args.batch_id
    else:
        batch = submit_batch(client, rules, args.model, args.effort)
        batch_id = batch.id
        log(f"submitted batch {batch_id}: {len(rules)} request(s), model {args.model}, effort "
            f"{args.effort}, prompt {phash[:12]}")
        if args.no_wait:
            log(f"collect later with: pattern_review.py {args.drafts} --out {out} --batch-id {batch_id}")
            return 0
    wait_for_batch(client, batch_id, args.poll, log)
    entries, fallbacks, failures = collect_results(client, batch_id, rules, args.model, args.effort,
                                                   raw_path, log)
    ordered = {rid: entries[rid] for rid in rules if rid in entries}
    write_json(out, reviewed_document(ordered, args.model, phash, _dt.date.today().isoformat(),
                                      batch_id, fallbacks, failures, args.drafts))
    by_outcome = {}
    for e in ordered.values():
        by_outcome[e["outcome"]] = by_outcome.get(e["outcome"], 0) + 1
    log(f"wrote {out}: {len(ordered)} rule(s) reviewed ("
        + ", ".join(f"{v} {k}" for k, v in sorted(by_outcome.items()))
        + f"); {len(fallbacks)} answered by a fallback model; {len(failures)} failed; raw results "
        f"in {raw_path}")
    if failures:
        log("failed: " + ", ".join(f"{k}: {v}" for k, v in sorted(failures.items())))
    log(f"next: python disa_stig_tool.py convert <zip> --pattern-drafts {out} "
        f"--write-pattern-drafts final.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# Pattern review task: from STIG check text to real NCM rules

Plan, 2026-10-15. Status: design, not built. Everything in the "Tool side" section that is
marked *exists* is in the tool today (2.1.0); everything else is proposed.

## What the task is for

`--mode blocks` already turns a STIG check's configuration examples into an Advanced
Config Search, and on the Cisco IOS Router package that gave 126 of 127 rules a pattern.
Those patterns are drafts: the values are the STIG's own examples (`2001::1:0:22/64`,
`FILTER_IPV6`, `x.x.x.x`), some blocks are illustrations rather than requirements, and a
check that says "must **not** be configured" still produced a "must contain" block.
Turning a draft into a rule an auditor can stand behind takes a reading of the check
text, which is what the review task does, one rule at a time, with a person in the loop.

The hand-off already exists: `--write-pattern-drafts FILE` writes every rule with its
check text and current pattern, `--pattern-drafts FILE` reads the reviewed file back
and validates it. The task sits between those two commands and never touches the server.

## Pipeline

1. **Draft.** `convert <zip> --mode blocks --write-pattern-drafts drafts.json` (offline).
   The file holds, per rule: id, title, STIG id, check text, Fix Text, `origin`, and the
   pattern or patterns the tool produced.
2. **Review.** The task reads `drafts.json`, reasons about each rule, and writes
   `reviewed.json` in the same schema with its proposals, a confidence and a reason per
   rule. Rules it cannot automate are marked, not guessed.
3. **Validate.** `convert <zip> --pattern-drafts reviewed.json --write-pattern-drafts
   final.json`: the tool refuses a malformed entry naming the rule and pattern, builds
   the reports, and writes what it will send. A person reads `final.json`, at least the
   rules the task flagged, and edits in place.
4. **Test against a real config.** `test <zip> --pattern-drafts final.json --config-id
   <ConfigID>` runs every rule through `TestRuleOnBackedUpConfig` against a configuration
   NCM already holds. This needs at least one Cisco node with a backed-up config; the
   lab has none today, which is also why every report scopes to no node. Without it the
   patterns are reviewed but not exercised.
5. **Import.** `import <zip> --mode blocks --pattern-drafts final.json --suffix _v4`,
   beside the `_v1` to `_v3` reports, so results can be compared report by report in the
   console before the older ones are removed with `remove`.

Steps 1, 3 and 5 exist. Step 2 is the task. Step 4 exists for the sentinel and
heuristic rules and must be checked for advanced-mode rules (below).

## What the task must decide per rule

Read the check text and classify the rule into one of these outcomes, in this order:

| Outcome | When | What it writes |
| --- | --- | --- |
| `not-automatable` | The check is an interview, a document review, a vendor-support question, a review of logs or of a server outside the device, or applies only in a circumstance NCM cannot see ("if the router is a PE router ...") | `"skip": true` plus a `review_reason`; the tool keeps the sentinel, so the rule flags for manual review, which is the honest state |
| `absent` | The check says a line or feature must **not** be present ("if ... is configured, this is a finding", "the following commands should not be in the configuration") | the lines that must be absent, each as a pattern with `must_contain: false`, OR-joined when any one of them is a finding; `must_exist` true |
| `present` | The check shows lines that must be present and says so plainly | the lines, each `must_contain: true`, AND-joined; `must_exist` true |
| `parameterized` | A line must be present with a value the organization chooses (a timeout, an address, an ACL name) | a `Regex` pattern with the value generalized (`ip http max-connections \d+`, `access-class \S+ in`), never a literal from the STIG example |
| `per-interface` | The requirement applies to every interface, VLAN, or line of a kind ("on all interfaces") | the pattern plus a config block: `ConfigBlockStart` a regex for the stanza opener, `ConfigBlockEnd` `!`, `ConfigBlockMustExist` as the check implies. This needs the schema extension below |
| `illustrative` | A block in the draft is an example of the surrounding prose, not the requirement (a sample interface, a sample `ip pim rp-address`) | drop that block, keep the others, and say so in `review_reason` |

Rules the task applies to every outcome:

- **Never invent a configuration line.** Every pattern must appear in the check text, or
  be the check text's line with a value generalized. If the check names a command only in
  prose ("verify that NTP authentication is enabled"), the task may propose the command
  (`ntp authenticate`) but must set confidence `low` and say the line is inferred.
- **Keep the device dialect.** IOS and IOS-XE, NX-OS, ASA and IOS-XR spell the same thing
  differently; the task writes what the check text shows and does not translate.
- **One idea per pattern.** A multi-line block is kept only when the lines must appear
  together in that order (an ACL and its entries); otherwise split it, so one missing
  line reads as one violation.
- **`no ` lines.** A check that requires `no ip source-route` is an `absent` rule for `ip
  source-route` when the platform omits defaults from the running config, and a
  `present` rule for the literal `no ip source-route` when it does not. The task says
  which it chose and why; this is the most common place a reviewer overrides it.
- **Like versus Regex.** `Like` for literal lines; `Regex` only when a value is
  generalized, with the literal parts escaped. NCM's `Like` treats `*` and `?` as
  wildcards only when the server's `ComplianceRulesWildcardsEnabled` setting is on, so a
  literal containing them becomes an escaped `Regex` (the tool already does this in
  heuristic mode).
- **Confidence and reason on every rule**, so the human review can be sorted: `high`
  (lines verbatim from the check, polarity stated plainly), `medium` (polarity or scope
  inferred), `low` (command inferred, or the check is ambiguous).

## File contract

Input and output are the pattern-drafts schema (`disa-stig-tool/pattern-drafts/1`).
The task writes back only these members per rule; the tool ignores members it does not
know, which is what makes the two extra ones safe today:

```json
"V-215668": {
  "advanced": true,
  "must_exist": true,
  "patterns": [
    {"pattern": "login block-for \\d+ attempts 3 within \\d+", "type": "Regex", "must_contain": true, "condition": ""}
  ],
  "note": "reviewed 2026-10-15 by <model or person>: parameterized the timers; attempts fixed at 3 by the STIG",
  "confidence": "high",
  "review_reason": "The check shows the exact command and the Fix Text repeats it; only the two timers are organization-defined."
}
```

A rule the task leaves to the run's own mode is `{"skip": true, "confidence": "...",
"review_reason": "..."}`. The `note` is carried into the rule's Comments by the tool, so
the audit trail (who reviewed, when, what changed) lands in NCM with the rule.

## Tool side

| Item | State | Note |
| --- | --- | --- |
| `--write-pattern-drafts`, `--pattern-drafts`, validation with the rule and pattern named | exists | both editions |
| `skip`, `must_exist`, `note`, `patterns` with `type`, `must_contain`, `condition`, single `pattern` | exists | schema 1 |
| `confidence`, `review_reason` | proposed, schema 2 | read and carried into the note; unknown members are ignored today, so a schema-2 file already loads |
| `config_block`: `{start, end, type, must_exist}` per rule | proposed, schema 2 | maps to `ConfigBlockStart`, `ConfigBlockEnd`, `ConfigBlockPatternType`, `ConfigBlockMustExist`, which the rule object already carries but nothing sets |
| `OR` inside a group with brackets | proposed | `BeginBracket` / `EndBracket` exist on the pattern; the drafts schema would gain `group` |
| `test` with advanced-mode rules | to verify | `TestRuleOnBackedUpConfig` takes the same `PolicyRule` contract, so the JSON object with `MultiLineRulePatterns` should test; unverified until a backed-up Cisco config exists |
| The server rebuilds the scope SQL from the typed criteria | known limit | the `MachineType` condition is lost on API import; add it in the console, or add a second `WebSelectionCriteria` once a LIKE match type is confirmed |

## Running the task

Recommended shape: a small script beside the tool, `pattern_review.py`, standard
`anthropic` SDK, one request per rule, run as a Message Batch (half price, no rate
pressure, results keyed by `custom_id` = rule id), with structured output so every
answer is schema-valid before the tool sees it. Design choices, each with the reason:

- **Model:** `claude-opus-5-5`, adaptive thinking (the default), effort `high`. The job
  is reading comprehension of security prose with a cost of being wrong; a cheaper
  worker can be measured against it later on the same drafts file.
- **One rule per request**, not the whole file: the check texts are independent, a
  mistake stays local, and the batch spreads the 127 requests over the batch window.
- **Structured output** (`client.messages.parse()` with a Pydantic model of the rule
  entry, or `output_config.format` with the JSON schema) so the reply is the entry
  itself, never prose to parse. `confidence` as an enum, `type` as an enum, `patterns`
  non-empty when `skip` is false.
- **The prompt**, in order: the contract above as the system prompt (outcomes, the
  never-invent rule, Like versus Regex, the `no ` note, the file members), then one
  worked example (V-230158: three blocks in, the two real ones kept, the illustrative
  `interface` block dropped and the reason), then the rule: id, title, STIG id, check
  text, Fix Text, the current draft. The Fix Text is included because it often states
  the command more plainly than the check.
- **Refusals**: pass `fallbacks: "default"` with the `server-side-fallback-2026-07-01`
  beta, so a rule whose check text trips a safety classifier (some STIG text reads like
  attack instructions) is answered by a fallback model rather than dropped; log which
  rules fell back.
- **Determinism for review:** write the model id, the prompt hash and the date into
  every `note`, keep the batch's raw results beside `reviewed.json`, and never overwrite
  a reviewed file in place.

The alternative is to run the same prompt from a Claude Code session or a repo skill
over the file: fine for a first pass by hand, but the batch script is what makes the
review repeatable per STIG release.

## Human review, by design

- The task output is a proposal. `--pattern-drafts` applies it, the run log and the rule
  note say it came from a file, and nothing is imported until a person runs `import`.
- Review every `absent` rule and every `low`: those are where a wrong polarity makes a
  non-compliant device read as compliant, which is worse than a false violation.
- `ExecuteScriptAutomatically` stays false everywhere; the task never writes remediation
  scripts, only patterns. The Fix Text stays prose in the Remediation field.
- Keep the `_v3` blocks report as the baseline and import the reviewed set as `_v4`; the
  console shows both, and `audit` lists what each run created.

## Measuring it

Before trusting the task on a new STIG, score it on one where the answers are known: the
hand-built rules Development maintains for the Cisco IOS Switch RTR STIG are a labelled
set (`CSCO-IOS-SW-RTR - Service.xml` and its siblings). Run the task on the matching
XCCDF, compare pattern by pattern, and count exact matches, equivalent patterns, and
disagreements by outcome class. That number, not a demo, decides whether the task runs
unattended on the next release.

## Order of work

1. Schema 2 in the tool: `confidence`, `review_reason`, `config_block`; carry the note.
   Both editions, tests, docs. Small.
2. `test` with advanced-mode rules against a backed-up config, once a Cisco node exists
   in the lab NCM. Verifies steps 4 and the matching semantics of multi-line `Like`.
3. `pattern_review.py`: the batch script with the prompt and the Pydantic model, a
   `--dry-run` that prints the per-rule prompts, and a scorer against a labelled file.
4. Score on the Switch RTR STIG; tune the prompt; record the numbers in this file.
5. Run on the Router package, review, import as `_v4`, compare in the console.

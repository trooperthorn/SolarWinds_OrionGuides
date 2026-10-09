# NCM compliance portability and DISA conversion: export audit

The report XML preserves a useful rule-authoring vocabulary, but moving the file is only
one part of moving a compliance assessment. The destination also needs the same intended
device scope, collected text, rule semantics, dependency relationships, and source
requirement identity. A successfully imported report is not proof of STIG coverage.

## Evidence and limits

This audit reads the owner-supplied `NCM-Compliance.zip`, SHA-256
`e87b7e4df42b4e196e8bd3b4e542a6bc968e9ec13a3f5fe8f19acb5338cdfae8`.
The owner reports contractor authorship and files originating across approximately 2022
through 2026.1. Individual file versions and the original publication URL are unknown.
The files are examples of authored content, not an independently verified vendor baseline.

The code baseline is repository commit `0b1dfa2aa330a3694f199c86cf42e04e68f02b16`.
API shapes were checked against the repository's 2026.2 contract. XML and regex parsing,
code inspection, and offline probes were performed; no imports, remediation scripts,
exported instructions, or device checks were executed on a server.

The [machine-readable evidence](../../reference/ncm-compliance-evidence/2026-09-18.json)
contains file hashes, report/policy/rule inventories, source XPaths, selected findings,
and probe outcomes. Counts below are occurrences unless explicitly called unique.

| Evidence | Count |
|---|---:|
| Report files | 24 |
| Policy occurrences / distinct policy names | 39 / 38 |
| Rule occurrences / distinct rule IDs | 415 / 405 |
| Advanced / basic rules | 236 / 179 |
| Condition rows in advanced rules | 1,178 |
| Rules with nonempty block delimiters | 56 |
| Rules carrying remediation text | 414 |
| Rules with recognizable narrative section headings in remediation | 413 |
| Rules with automatic remediation enabled | 0 |
| Explicit unfinished template patterns | 47 |
| Selected regex fields checked / syntax failures | 101 / 1 |

All files use the same observed element order. This supports a common serialized shape
across this sample; it does not prove unchanged APIs or evaluation behavior across every
intervening product version. In particular, SolarWinds documents
`ComplianceRulesWildcardsEnabled` beginning in 2023.1.1. Record that setting with the target
version when validating literal/wildcard patterns.
[SolarWinds rule documentation](https://documentation.solarwinds.com/en/success_center/ncm/content/ncm-manage-policy-rules.htm).

## Report, policy, rule, and requirement are different identities

The exported hierarchy remains `PolicyReport` → `AssignedPolicies/Policy` →
`AssignedPolicyRules/PolicyRule`. SolarWinds documents that a report export includes its
underlying policies and rules and can be transferred between servers.
[Import/export documentation](https://documentation.solarwinds.com/en/success_center/ncm/content/ncm-import_export_policy_reports.htm).

The largest report, `73_SRG-Router - Report.xml`, has eight policies and 103 rule
occurrences. The Arista routing report has six policies and 74 rules. One policy per
report is therefore a converter design choice, not a console format constraint.

The SRG Router IPv6 policy appears both inside the larger report and in
`SRG-Router - IPv6.xml`. Its ten rule IDs have identical parsed content in both locations.
Do not regenerate all child IDs independently when importing this package: that would
discard evidence that the exports share children. Conversely, do not reuse a destination
rule solely because a name matches.

| Identity | How to preserve it |
|---|---|
| Exported report | Retain source `ID`, name, file hash, and archive path; record the destination ID returned by import. |
| Exported policy | These files omit `PolicyId`. Retain name, grouping, scope, config type, content hash, and source path as a portable key. Ambiguous matches need review. |
| API policy | The 2026.2 contract does include `PolicyId`; map it separately from the portable key. |
| NCM rule | Retain `RuleId` and content hash; distinguish identical reuse from conflicting definitions. |
| DISA requirement | Retain benchmark identity and release, original XCCDF Rule ID, vulnerability ID where present, STIG ID, and references. An NCM GUID is not a DISA requirement ID. |

None of the 415 rule records contains a recognizable canonical `V-<number>` or
`SV-<number>...` identifier in its scalar fields. Many names retain STIG/SRG-style control
identifiers, and 398 records retain CCI references. These are useful crosswalk inputs but
do not establish an exact DISA release. Generic SRG and operational rules may legitimately
lack vulnerability IDs; do not invent them or label all such rules invalid.

For reuse, build a crosswalk with statuses such as `exact-source-match`,
`candidate-match`, `locally-authored`, and `unresolved`. Confirm candidates against the
chosen official source package. CCI overlap or a similar title is insufficient to merge
rules automatically. Completeness against DISA is **unverified** until a specific source
benchmark, release, and selected profile have been compared.

## Scope and collected configuration are portable dependencies

Thirty-eight policies contain `WebCriteria:` followed by an escaped picker document and
an `SQL:Where` suffix. One carries `*:`. Preserve the unrecognized or unrestricted-looking
selector for explicit review instead of silently replacing it with all nodes.

Thirty-four policies reference `C1_DeviceType` or `C2_OS`, custom-property names specific
to the source environment. Thirteen selector documents contain a `Vendor` field; a
policy may contain more than one field. These figures are not independent policy totals.

SolarWinds places device selection and configuration type at the policy level and supports
custom-property scoping. It also states that NCM policy reports cannot evaluate downloaded
XML-format device configurations, including the usual Palo Alto example.
[Policy documentation](https://documentation.solarwinds.com/en/success_center/ncm/content/ncm-policies.htm).

An import planner should therefore expose a scope mapping, show the resolved node count,
and distinguish an empty match from a compliant result. Preserve the picker document and
the SQL suffix together. This suffix is not SWQL and should not be sent to a SWQL validator
as if it were a standalone query. Runtime precedence if the two representations disagree
is **unverified** here.

Observed `ConfigTypes` are:

| Value | Policies | Required preflight |
|---|---:|---|
| `Running` | 34 | Confirm recent, readable text exists for the selected devices. |
| `Any` | 1 | Confirm the intended semantics when multiple stored config types exist. |
| `Version` | 2 | Verify the target type and the collected version text. |
| `CryptoCACertificates` | 1 | Verify the target type, collection commands, and certificate text. |
| `OSPF-Key-Chain` | 1 | Verify the target type and collection of the routing key-chain evidence. |

Do not assume every non-Running type is custom. Inspect the target:

```sql
SELECT Id, Name, IsCustom
FROM NCM.ConfigTypes
ORDER BY Name
```

The XML does not supply the collection commands or device-template dependencies behind
these type names. The two special ASA policies and the special IOS-XE routing policy
cannot be made portable merely by changing their config type to `Running`: that could
remove the evidence they need. Export dependency metadata and require a target mapping.

All 41 Palo Alto rules in the three supplied Palo Alto reports are unfinished template
checks. Completing their patterns would still require a supported text collection path;
the presence of a `Running` policy does not prove the downloaded config is suitable.

## Preserve condition structure and whitespace

The 236 advanced rules contain 1,178 ordered condition rows: 236 first rows have an empty
`Condition`, with 707 `AND` and 235 `OR` connectors afterward. Parenthesis fields include
multiple opening/closing brackets. All condition `Criteria` values in this advanced sample
are true, so this corpus alone does not demonstrate mixed must/must-not conditions.

Preserve `AdvancedMode`, each row's `PatternType`, `Criteria`, connector, parentheses,
order, and pattern text. Root-level `PatternType` is `Like` for every rule, while 21
advanced condition rows are `Regex`; reading only the root field would lose that
distinction. Preserve block start/end, block type, and `ConfigBlockMustExist` separately.

Basic rules also retain a one-row `MultiLineRulePatterns` container. Its presence does
not mean advanced mode is active. A faithful archival export should preserve inactive
fields too; a semantic evaluator must honor the mode.

The scan identified 155 selected pattern fields with leading or trailing whitespace.
This is a review flag, not a recommendation to trim them. Indentation and newlines may
be part of the intended match. Parenthesis balance passed for all advanced rule lists;
that proves structural balance, not correct logic or operator precedence.

SolarWinds specifies the .NET regex engine and recommends testing compliant and violating
configurations. Local regex compilation tests syntax only; the target NCM evaluator is
still needed for block scope and violation behavior.
[Rule testing guidance](https://documentation.solarwinds.com/en/success_center/ncm/content/ncm-manage-policy-rules.htm).

## Concrete content findings

These findings support remediation work; they do not establish the entire package's
compliance effectiveness without representative device configurations.

| Finding | Exact evidence | Proposed handling |
|---|---|---|
| Invalid block regex | `64_ARST-MLS-EOS-42-L2 - Report.xml`, policy 1, rule 8, `ConfigBlockStart`: `interface vlan 1\`. The .NET regex constructor rejects the terminal backslash. | Confirm the intended VLAN/block boundary, correct it, and test matching and nonmatching blocks. |
| Unfinished checks | 47 distinct rules contain `[Place ...]` templates: 24 Palo Alto ALG, 11 Palo Alto IDPS, six Palo Alto NDM, six Juniper VPN. | Mark as manual/unimplemented in the converter's coverage inventory. Do not count them as implemented automated checks. |
| Literal placeholders | Arista rule `ARST-L2-000110` includes `ip arp inspection vlan <vlan-list>`; Juniper rule `JUSX-VN-000002` contains `<P2-PROPOSAL-NAME>`. Both are `Like` patterns. | Parameterize with validated site input or design and test the intended expression. |
| Embedded addresses | 142 selected pattern fields contain dotted IPv4 literals. | Classify each as a required protocol constant, illustrative example, or site-specific value before changing it. |
| Type/notation ambiguity | Fifty `Like` fields contain bracket, wildcard, or regex-looking notation, including unfinished templates. | Review literal intent and the target wildcard setting; do not automatically relabel them `Regex`. |
| Guidance in script fields | 413 remediation values have narrative headings such as Discussion, Check Text, or Fix Text; all 415 rules have automatic execution false. | Preserve the original as evidence. In newly generated content keep guidance apart from reviewed executable commands. |

All 101 selected regex fields were compiled locally using .NET with a bounded match
timeout configured, without matching them against live configurations. One failed syntax.
No auto-remediation flag was enabled; four rules nevertheless set
`ExecuteScriptInConfigMode=true`, so execution flags remain independent fields to preserve.

## Encoding is a compatibility issue, not a format prescription

All 24 files declare `utf-16` but contain UTF-8 bytes without a UTF-16 BOM. Parsing the bytes
directly fails; explicit UTF-8 decoding followed by parsing the resulting text succeeds.
Record that repair and retain the original bytes/hash. Do not generalize this observation
into “ignore every XML declaration.” Correctly encoded UTF-8 and UTF-16 must also work.

Use three distinct artifacts: immutable source bytes, a parsed model with diagnostic
metadata, and a newly serialized export. New exports should normally declare the encoding
actually written. A legacy compatibility option may reproduce the observed mismatch only
when a named target's import tests justify it.

The current tools differ: Python's `write_console_file` deliberately emits UTF-8 bytes
with a UTF-16 declaration, while Porter's `ExportAsync` writes actual UTF-16 with a BOM.
The sample proves the former input quirk; it does not establish that either output form
is universally required by every console release.

There is also a positive preservation result: an audit adapter converted all 24 source
trees to typed report objects, passed them through Python's `report_contract_xml`, and
compared the parsed fields afterward. All 24 retained their exported fields, including
advanced conditions. This verifies the console writer on this corpus; it does not add
NCM XML input support to the tool or validate its separate DataContract writers.

## Code gaps affecting the STIG Tool and Porter

These are findings against the named baseline, not changes implemented by this audit.
The relevant sources are the [Python tool](../../apps/disa-stig-conversion-tool/disa_stig_tool.py),
[PowerShell tool](../../apps/disa-stig-conversion-tool/disa_stig_tool.ps1), and
[Porter provider](../../apps/porter/Porter/Areas/NcmComplianceProvider.cs).

| Priority | Location | Evidence and effect | Acceptance requirement |
|---|---|---|---|
| P0 | Python `dc_rule_xml`; PowerShell `ConvertTo-DcXml` | These writers emit an empty multiline container. An offline Python probe supplied two real advanced conditions and serialized zero in both XML namespace modes. | Preserve every ordered condition in all supported serializers; refuse unsupported structures rather than drop them. |
| P0 | PowerShell `ConvertTo-ConsoleReportXml` | Code inspection shows an empty multiline container even if the supplied object has conditions. Python's console writer does iterate them. | Test Python/PowerShell console and API output equivalence for advanced rules. |
| P0 | Python `_verify_report`; PowerShell `Test-NcmImport` | Verification rejects an empty tree but does not compare expected counts. The Python probe expected two policies/ten rules; one policy/one rule was accepted. **Addressed in code in DISA STIG tool 2.0.0 (2026-10-09):** both editions compare the read-back with what was submitted (policy count, rule count, and rule names per policy, as Porter 0.3.0 does); a mismatch or a result that is not a report object is a failed import, named with both counts and rolled back, and a nested `AddPolicyReport` that fails it is deleted before the console-file fallback. Covered by offline tests; no live import was run. | Verify exact relationships and canonical content, not merely nonzero counts; report partial imports explicitly. Still open: comparison of rule content beyond names and counts, and a live acceptance test. |
| P0 | Porter `ImportAsync` | At baseline, read-back checked the report row's name and then started caching; it did not read the nested tree. **Addressed in code in Porter 0.3.0 (2026-10-08):** the report is created `Disabled`, `GetPolicyReport(reportId, exportFlag)` with `exportFlag` true is read back, and policy and rule counts and names are compared with the file. A mismatch is reported as a partial import with both counts, and caching starts only for a verified report the operator chose to keep `Enabled`. Covered by offline unit tests; no live import was run. | Verify the complete imported definition before evaluation. A report row alone is insufficient. Still open: canonical comparison of rule content beyond names and counts, and a live acceptance test. |
| P1 | Python `_parse_one_benchmark`; PowerShell `Read-OneBenchmark` | Only the first direct Rule per Group is selected. A synthetic two-rule Group produced one rule. Profile metadata is not retained. | Preserve all rules and group ancestry; represent profile selection explicitly. |
| P1 | XCCDF parsers and deduplication | Only one check/reference and one fix text are selected; check-reference href/system and tailoring are not modeled. Namespace 1.2 is treated as SCAP edition, and deduplication prefers manual by benchmark ID without release comparison. | Keep source structure and versions before deciding how much can be converted; namespace alone is not an edition test. |
| P1 | `make_node_selection_string` / `New-NodeSelectionString` | The picker is synthesized from Vendor alone with equality, while the SQL suffix can retain LIKE and additional properties. An offline probe reproduced that disagreement. | Generate both representations from the same scope model; test save/reopen behavior on the target. |
| P1 | Import orchestration / `_clean_id` | Probe calls create rules. A missing returned rule/policy ID can fall back to the submitted ID. No durable dependency/import ledger is maintained. Partly addressed in tool 2.0.0 (2026-10-09): only the two documented 400 rejections move the probe on, a call that fails without an HTTP status is reported as an unknown outcome naming the submitted id, and every rollback or removal decision based on `IN @ids` is preceded by a probe for an id known to exist. | Treat probes as writes, verify returned identities, account for partial progress, and support deliberate resume/cleanup. Still open: a durable import ledger and resume. |
| P1 | `rule_object` / `New-NcmRule` | Default generation creates basic literal sentinel/draft rules and copies fix prose into a CLI script field. It does not compile advanced/block conditions from DISA prose. | Separate review status, guidance, machine-check implementation, and executable remediation. |

The advanced-rule serialization findings do not imply that today's default converter
already imports these contractor reports: its input parser expects XCCDF, not
`PolicyReport` XML. They become critical when reusing its writers for this richer content.
Porter is the existing reader for NCM report XML. The three artifact types need separate
classification before any conversion is attempted.

## A conversion model that retains DISA meaning

DISA distinguishes human-readable STIG content from SCAP data streams containing multiple
components; displaying or extracting a reference to OVAL does not evaluate that check.
[DISA FAQ](https://www.cyber.mil/stigs/faqs).
XCCDF supports grouped rules, profile selection and tailoring, and check references with
their own locations and identifiers. Preserve those structures before reducing content to
NCM matching operations.
[NIST XCCDF specification](https://csrc.nist.gov/files/pubs/ir/7275/r4/upd1/final/docs/nistir-7275r4_updated-march-2012_clean.pdf).

Use an intermediate model with these separate concerns:

| Concern | Minimum retained data |
|---|---|
| Provenance | Source URL/file, archive member path, byte hash, benchmark ID/version/release, original XML namespace and IDs. |
| Requirement | Group ancestry, rule ID/version, title, severity, discussion, all references and identifiers. |
| Applicability | Platform/role/version constraints, profile selection, tailoring values, scope predicates, exclusion reasons. |
| Evidence | Check text, check system and references, required config type/collection, operational or human evidence needs. |
| Implementation | Basic/advanced/block matcher, per-condition type and polarity, parameter definitions, test fixtures and review status. |
| Remediation | Original fix guidance separately from reviewed command script, parameters, and execution flags. |
| Import identity | Source-to-target report/policy/rule mapping, shared dependencies, content hashes, conflict decision, import journal. |

Keep source identifiers even if a normalized identifier is convenient. The current UUID5
rule identity changes when the revision-bearing XCCDF Rule ID changes; that alone does not
decide whether to update, replace, or retain an older rule. Preserve both requirement
continuity and revision identity. Never use a CCI as the unique rule key.

The compiler should account for every selected requirement with an explicit outcome:
`implemented-and-tested`, `draft`, `manual-review`, `unsupported-check-system`,
`not-selected`, or `not-applicable-with-evidence`. These are proposed tool-side statuses,
not asserted native NCM result states. A sentinel can make an action item visible, but its
violation must not be misreported as an observed configuration failure.

Manual check prose often combines configuration, operational state, architecture, and
interviews. A first-command heuristic cannot establish that full requirement. Likewise,
SCAP/OVAL logic requires an appropriate evaluation or deliberate translation; a comment
containing an OVAL ID is traceability only. Show automated coverage separately from native
violation totals, including unmapped, manual, unknown, and not-applicable requirements.

For new generated packages, preserve raw fix guidance in comments or a companion manifest
and leave executable remediation empty until commands are explicitly authored and reviewed.
For archival import/export, preserve the original field and mark its content type; silently
moving it would break fidelity. These are different operations.

## Proposed import and export contract

1. **Detect the artifact by content.** Classify NCM report XML, XCCDF, and SCAP data-stream
   containers separately. Record encoding diagnostics and original bytes. Preserve unknown
   fields in an extension area or report unsupported content; never silently discard them.
2. **Build the dependency graph.** Inventory reports, policies, rules, and shared references;
   compare IDs and content hashes. Plan reuse, clone, or conflict resolution explicitly.
3. **Resolve target dependencies.** Verify entity/verb availability, NCM permissions, scope
   custom properties and allowed values, config types, collected text, and matcher settings.
   Stable SWIS transport does not prove all of these dependencies exist.
4. **Preview the plan.** Show all proposed creations, reuse, conflicts, target node counts,
   unavailable evidence, manual checks, and executable remediation. Do not enable broad
   evaluation while scope is unresolved.
5. **Write with a journal.** Use verified nested import or bottom-up composition with ID
   lists. Store returned IDs and relationship mappings, including created-but-unlinked items.
   Do not delete a shared child to replace one report.
6. **Verify definitions.** Read the exported tree back and compare fields and relationships
   after mapping server-assigned IDs. Equal counts alone can hide substituted or empty rules.
7. **Test behavior.** Use `TestRule` and selected stored configurations. The published contract
   says macro parsing is unavailable for pasted config in `TestRule`; include backed-up
   configurations when macros are involved. Separate syntax success from evaluated truth.
8. **Evaluate and report.** Cache only the intended report after successful validation, then
   distinguish cache error, missing/old configuration, zero scoped devices, manual status,
   and an actual finding. Export the verified mapping and dependency manifest for reuse.

The contract types contain nested child objects and parallel ID lists. Use them deliberately:
console files describe content; ID lists compose references to target objects. See
[the format and verb guide](ncm-compliance-reports.md) for the API boundary. Neither the
contract nor this archive proves transactionality or collision resolution on every server.

## Acceptance tests before claiming cross-customer support

| Test | Required result |
|---|---|
| Encoding fixtures | Valid UTF-8, valid UTF-16, and the observed mismatched declaration are classified accurately; repairs are recorded. |
| Advanced serialization | AND/OR, nested parentheses, negative criteria, Regex/Like, inactive fields, block settings, whitespace, and unknown fields are retained or explicitly rejected. |
| Shared imports | The SRG IPv6 overlap retains planned shared relationships; divergent same-ID content triggers a conflict. |
| Partial failure | Failures after rule/policy creation produce an accurate journal; retry does not silently duplicate or orphan objects. |
| Exact read-back | Missing/replaced rules, missing patterns, changed scope, and changed flags fail verification even with plausible counts. |
| XCCDF coverage | Nested groups, multiple rules, profile selection, values, multiple checks/fixes, version conflicts, and referenced check systems are accounted for. |
| Positive/negative evaluation | One compliant and one violating fixture per implemented rule, plus absent block, multiple blocks, empty config, and line-ending variants where relevant. |
| Portability | Custom scope fields and required config types are mapped; a zero-node scope or unavailable config cannot appear as a pass. |
| Cross-version behavior | Record actual import/read-back/evaluation results per tested server build and matcher settings; do not extrapolate from a common XML shape. |

This documentation proposal adds evidence and an implementation contract. It does not
modify the tools, repair the contractor's rules, re-import reports, or claim that every
selected STIG requirement is machine-checkable in NCM.

## Official DISA package comparison, 2026-09-18

The live [DISA download catalog](https://www.cyber.mil/stigs/downloads/) was accessed in a browser and 11 packages were downloaded using its Download buttons. The text-only web fetch returned an empty application shell; this was an access-method limitation, not an unavailable catalog. Source download URLs were recovered from each downloaded file's Windows `Zone.Identifier`. All original ZIP bytes were retained locally and hashed. No checks or remediation were executed.

The packages contain 29 XCCDF 1.1 benchmarks and 1,346 rules. Independent XML enumeration and the current Python `load_benchmarks` function returned identical benchmark counts and rule identity sets for all 11 packages. This verifies discovery for these particular manual packages. It does not remove the multi-Rule, profile, SCAP, serializer, or import-verification limitations described above.

The [machine-readable DISA crosswalk](../../reference/ncm-compliance-evidence/2026-09-18-disa-crosswalk.json) records every NCM occurrence, source XPath, NCM GUID, benchmark ID, XCCDF member/hash, current V-/SV- and STIG/SRG IDs, severity, CCI identifiers, package version/release, and documented historical transition. The 402 matches are identity matches to the downloaded release, not proof of the contractor's original authoring release or equivalent assessment logic.

| Comparison result | NCM rule occurrences |
|---|---:|
| Same STIG/SRG identifier in the corresponding benchmark | 402 |
| Absent identifier explained by an official merge | 8 |
| Absent identifier documented as removed | 1 |
| Absent identifier moved to Not Applicable in the source revision | 2 |
| Historical identifier still unresolved | 1 |
| Operational hardware check, outside this STIG crosswalk | 1 |

The 402 matches represent 392 distinct NCM rule GUIDs. Ten occurrences reuse the same rules in two Router SRG reports. Of the matched occurrences, 242 have check prose identical after whitespace normalization; 160 do not pass that comparison (changed prose or unsuccessful section extraction). Neither result verifies the authored NCM pattern semantics. Five severity pairs differ from the working mapping `0=low, 1=medium, 2=high`; these need review, not silent rewriting of customer severity settings.

### Downloaded packages and corresponding exports

| Official package | Relevant benchmark version/release | Contractor report family | Catalog status / upload date |
|---|---|---|---|
| [Arista MLS EOS 4.X STIG](https://dl.dod.cyber.mil/wp-content/uploads/stigs/zip/U_Arista_MLS_EOS_4-X_Y25M07_STIG.zip) | L2S V2R3; Router V2R2 | ARST-MLS-EOS-42 L2/RTR | listed; 2025-08-07 |
| [Cisco ASA STIG](https://dl.dod.cyber.mil/wp-content/uploads/stigs/zip/U_Cisco_ASA_Y26M07_STIG.zip) | FW V2R1; IPS V2R1; NDM V2R5 | CSCO-ASA FW/IPS/NDM | listed; 2026-07-10 |
| [Cisco IOS Switch STIG](https://dl.dod.cyber.mil/wp-content/uploads/stigs/zip/U_Cisco_IOS_Switch_Y26M07_STIG.zip) | RTR V3R3 | CSCO-IOS-SW-RTR | listed; 2026-07-10 |
| [Cisco IOS XE Switch STIG](https://dl.dod.cyber.mil/wp-content/uploads/stigs/zip/U_Cisco_IOS-XE_Switch_Y26M04_STIG.zip) | RTR V3R4 | CSCO-IOS-XE-SW-RTR | listed; 2026-04-07 |
| [Cisco IOS XR Router STIG](https://dl.dod.cyber.mil/wp-content/uploads/stigs/zip/U_Cisco_IOS-XR_Router_Y26M04_STIG.zip) | RTR V3R3 | CSCO-IOS-XR-RTR-RTR | listed; 2026-04-07 |
| [Cisco NX OS Switch STIG](https://dl.dod.cyber.mil/wp-content/uploads/stigs/zip/U_Cisco_NX-OS_Switch_Y26M07_STIG.zip) | L2S V3R4; RTR V3R4 | CSCO-NXOS-SW-L2S/RTR | listed; 2026-07-10 |
| [Fortinet FortiGate Firewall STIG](https://dl.dod.cyber.mil/wp-content/uploads/stigs/zip/U_FN_FortiGate_Firewall_Y26M01_STIG.zip) | NDM V1R5 | FORT-FW-NDM | listed; 2026-01-22 |
| [Juniper SRX Services Gateway STIG](https://dl.dod.cyber.mil/wp-content/uploads/stigs/zip/U_Juniper_SRX_SG_Y25M01_STIG.zip) | VPN V3R2 | JNPR-SRX-SG-VPN | listed; 2025-01-28 |
| [Sunset - Palo Alto Networks STIG](https://dl.dod.cyber.mil/wp-content/uploads/stigs/zip/U_PAN_Y26M07_STIG.zip) | ALG V3R4; IDPS V3R2; NDM V3R4 | PALO-ALG/IDPS/NDM | sunset; 2026-07-10 |
| [Router SRG - Ver 5, Rel 2](https://dl.dod.cyber.mil/wp-content/uploads/stigs/zip/U_Router_V5R2_SRG.zip) | V5R2 | 73_SRG-Router; SRG-Router IPv6 | listed; 2026-01-08 |
| [Network Device Management SRG - Ver 5, Rel 5](https://dl.dod.cyber.mil/wp-content/uploads/stigs/zip/U_NDM_V5R5_SRG.zip) | V5R5 | SRG-NDM SNMP/SSH/NTP | listed; 2026-07-10 |

Package dates, catalog upload dates, benchmark dates, and rule revisions are separate fields. For example, the July 2026 Cisco ASA ZIP includes FW/IPS benchmarks dated July 2024 and NDM dated July 2026. Do not assign the outer ZIP date to every child requirement.

Arista is listed as EOS 4.X, but its benchmark IDs still contain `4-2x`. Cisco IOS XE uses underscores in `Cisco_IOS_XE_Switch_RTR_STIG`, while Cisco IOS-XR uses a hyphen in `Cisco_IOS-XR_Router_RTR_STIG`. Match actual source IDs through an explicit family map. `CISC-RT-*` identifiers are reused across different Cisco platform benchmarks and are not globally unique.

The Palo Alto Networks package is explicitly listed as **Sunset** in the live catalog, despite its July 2026 upload date. Preserve this catalog lifecycle status separately from XCCDF status and version. All 41 Palo Alto rule occurrences matched identifiers, but all 41 remain unfinished template checks in the supplied NCM exports. Identity resolution does not make them executable assessments.

### Historical transitions that the parser must retain

| NCM family / old identifier | Official disposition | Evidence inside downloaded ZIP |
|---|---|---|
| Arista L2 `ARST-L2-000150` | Removed in L2S V2R3 | `U_Arista_MLS_EOS_4-X_Revision_History.pdf`, PDF page 2 |
| Cisco IOS XE Switch RTR `CISC-RT-000020`, `000030`, `000040` | Merged into `CISC-RT-000050` in RTR V2R5 | `U_Cisco_IOS-XE_Switch_Revision_History.pdf`, PDF page 4 |
| Cisco IOS XE Switch RTR `CISC-RT-000130`, `000140` | Merged into `CISC-RT-000120` in RTR V2R5 | Same PDF, page 4 |
| Cisco IOS XR Router RTR `CISC-RT-000020`, `000030`, `000040` | Merged into `CISC-RT-000050` in RTR V2R4 | `U_Cisco_IOS-XR_Router_Revision_History.pdf`, PDF page 3 |
| NDM `SRG-APP-000004-NDM-000203`, `SRG-APP-000005-NDM-000204` | Moved to Not Applicable in V5R5 | `U_NDM_V5R5_Revision_History.pdf`, PDF page 2 |

These are reviewed revision-history relationships, not replacements to apply automatically. Merging requirements can change scope, severity, and check logic; several successors already have NCM occurrences. Preserve both historical identity and the successor relationship, present duplicate/consolidation conflicts, and require an assessment review before generating replacement conditions. PDF page numbers above count the cover as page 1.

### Historical source lookup skipped by owner

`SRG-NDM - SNMP SSH and NTP.xml` contains `SRG-NDM-APP-000373-NDM-000298 - NTP`, corresponding to `SRG-APP-000373-NDM-000298`. It is absent from the downloaded Network Device Management SRG V5R5 XCCDF. The V5R5 revision history mentions this identifier as updated for V5R1, but does not establish a later removal or a successor. No successor is inferred from similar NTP wording.

The owner elected on 2026-09-18 to skip further historical-source lookup for this requirement. Retain its unresolved identity for traceability, but exclude it from verified mappings and do not block publication or other parser work on it. No source package or successor is asserted. The other 11 absent identifiers have documented dispositions, so their absence is not by itself a parser failure. The `555_OM Req - 9300 Memory Leak` report embeds Cisco field notice FN72416 and should retain operational provenance rather than receive an invented STIG ID.

### Concrete XCCDF-to-NCM ingestion contract

| Source information | Ingestion and NCM representation |
|---|---|
| ZIP source URL/hash; member path/hash; catalog lifecycle | Keep in a sidecar manifest. Preserve archived input and allow offline re-ingestion. Catalog status is not available by reading XCCDF alone. |
| `Benchmark/@id`, title, version, `plain-text[@id="release-info"]`, status/date | Keep separate fields. Create a report/policy plan per selected benchmark, then allow reviewed functional grouping such as ACL, IPv6, or Routing Protocol. DISA does not supply the contractor's NCM grouping plan. |
| Group ancestry, `Rule/@id`, `Rule/version` | Preserve full V-/SV-/STIG/SRG identities and revision. Use benchmark context plus source requirement identity; retain an explicit NCM GUID mapping. Do not key only by title, CCI, or revision-bearing SV ID. |
| `Rule/@severity` and all `ident` entries | Keep original severity/identifier systems; apply an explicit target severity policy and retain differences for review. CCI mappings are many-to-many. |
| Description fragments, all check bodies/references, all fix texts and fixes | Preserve source prose, reference system/href/name, and ordering before any conversion. Guidance and executable remediation need separate representations. |
| Profiles, selectors, values, tailoring, applicability | Preserve/evaluate selection before reporting coverage; report unsupported semantics explicitly. Do not label absence from the selected assessment as a pass. |
| Human check instructions | Translate only through a reviewed rule implementation with compliant/violating fixtures. An example command or first configuration-looking line is not sufficient evidence for a safe `StringMatching`, ordered `MultiLineRulePatterns`, or config-block assessment. |
| Node scope and collected configuration | Resolve `NodeSelectionString`, target custom properties, `ConfigTypes`, and collection commands separately. These customer-specific NCM dependencies are not supplied by XCCDF. |
| Removed, merged, Not Applicable, or sunset source content | Keep lifecycle metadata and historical relationships. Require review before retiring/consolidating NCM checks; never silently map them to a passing result. |

Acceptance additions: reload the 11 saved ZIPs and reproduce all 29 benchmark / 1,346 rule identities; reproduce the 415-row crosswalk; preserve the 11 documented transitions and one unresolved requirement; keep Cisco platform collisions separate; retain package-versus-benchmark dates; retain Palo Alto sunset status; expose the 47 draft checks already identified; and verify generated advanced NCM rules on compliant and violating text in the target product. The first two are offline verified here; implementation and live assessment checks remain outstanding.

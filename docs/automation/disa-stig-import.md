# Importing DISA STIGs: from cyber.mil to NCM and SCM compliance

A DISA Security Technical Implementation Guide is a list of requirements — check text,
fix text, severity — for hardening one product. The DoD publishes them all publicly on
[public.cyber.mil/stigs/downloads](https://public.cyber.mil/stigs/downloads/), and the
platform can track them in two different modules depending on what the STIG targets:

| STIG targets | Module | The import payload |
|---|---|---|
| Network devices (Cisco IOS, JunOS, firewalls…) | NCM compliance policy reports | Built from the STIG's XCCDF XML |
| Servers (Windows, IIS, SQL Server…) | Server Configuration Monitor compliance | SolarWinds' SCM policy YAML, imported verbatim |

This page is the whole flow for both: what is inside the files, which SWIS calls land
them, and the DISA STIG Conversion Tool (`apps/disa-stig-conversion-tool`) in this repository that does it end to end.

**Source.** Verified against a real DISA package (Cisco IOS Router, Y26M07 release: NDM
V3R8 and RTR V3R4 benchmarks, 127 rules) and a real SCM policy export (Microsoft IIS 8.5
Server STIG version 1 rel. 10, 18 rules), and against the 2026.2 schema and verb
contracts. A later [NCM portability audit](../modules/ncm-compliance-portability-audit.md)
adds contractor-export evidence and concrete gaps in the current converters. This page
describes current behavior; it does not certify complete XCCDF interpretation or live
import verification.

## What DISA actually publishes

Every package on the downloads page resolves to one URL shape:

```
https://dl.dod.cyber.mil/wp-content/uploads/stigs/zip/<PackageName>.zip
    e.g.  …/zip/U_Cisco_IOS_Router_Y26M07_STIG.zip
```

Names are case-sensitive; a wrong guess returns an HTTP error page, so verify a
download is a zip before trusting it. Inside the zip:

```
U_Cisco_IOS_Router_Y26M07_STIG.zip
├── U_Cisco_IOS_Router_NDM_V3R8_Manual_STIG/
│   ├── U_Cisco_IOS_Router_NDM_STIG_V3R8_Manual-xccdf.xml   ← the data
│   ├── STIG_unclass.xsl                                    ← only a stylesheet
│   └── DoD-DISA-logos-as-JPEG.jpg
├── U_Cisco_IOS_Router_RTR_V3R4_Manual_STIG/                ← a second benchmark
└── *.pdf                                                    overview, release memo
```

Three facts that save time:

- **The `.xsl` is not the data.** It is the stylesheet the `*-xccdf.xml` references so
  a browser renders it readably. Parse the XML; ignore the XSL.
- **One package can carry several benchmarks.** The Cisco IOS Router package has NDM
  (device management, 35 rules) and RTR (routing, 92 rules), each its own folder and
  release cycle.
- **Compilation zips nest zips.** The SRG-STIG Library downloads hold one inner zip per
  STIG in the same layout.

### The XCCDF benchmark, the fields that matter

The XML is [XCCDF 1.1](https://csrc.nist.gov/projects/security-content-automation-protocol/specifications/xccdf)
(`http://checklists.nist.gov/xccdf/1.1` namespace): a `Benchmark` root with `title`,
`version`, a `plain-text id="release-info"` ("Release: 8 Benchmark Date: 01 Jul 2026"),
several `Profile` elements selecting rule subsets by MAC level, and then one `Group` per
requirement:

| XCCDF | Content |
|---|---|
| `Group@id` | The vulnerability id, `V-215662` — stable across releases |
| `Rule@id` | `SV-215662r1192908_rule` — changes when the rule text is revised |
| `Rule@severity` | `high` / `medium` / `low` (CAT I/II/III) |
| `Rule/version` | The STIG id, `CISC-ND-000010` |
| `Rule/title` | The requirement sentence |
| `Rule/description` | Escaped pseudo-XML; `<VulnDiscussion>` holds the rationale |
| `Rule/check/check-content` | How to verify, prose plus config excerpts |
| `Rule/fixtext` | How to fix — for network STIGs, usually literal CLI |
| `Rule/ident` | CCI references and legacy ids |

Manual STIGs (the common kind) describe checks in prose for a human auditor — there is
no machine-checkable pattern in the file. Any automated translation has to be honest
about that; see the two modes below.

## Path one: network STIGs into NCM

The target format is the three-tier NCM policy report — report → policies → rules —
whose file format and verbs [../modules/ncm-compliance-reports.md](../modules/ncm-compliance-reports.md)
documents in full. The mapping that works:

- The current `build_reports` implementation creates one **report and policy per
  benchmark**, with a basic rule for each parsed requirement. This is a packaging choice: a
  report can have several policies, and policies can share rules. `NodeSelectionString`
  carries both picker state and a SQL-like suffix; use a target-validated scope and preserve
  both representations. The current parser selects the first Rule in each Group and does
  not retain profiles, so it is not a complete general XCCDF reader.
- Severity → `ErrorLevel`: high `2` (critical), medium `1` (warning), low `0` (info).
- Discussion, selected check content and the supported IDs land in `Comments`; this is
  not lossless preservation of all XCCDF metadata. The current tool copies fix text into
  `RemediateScript` (CLI) with `ExecuteScriptAutomatically` **false**. Fix prose is not
  necessarily executable CLI; future generation should separate guidance from reviewed
  commands. Retain full source provenance in a companion manifest.
- Because the checks are prose, the rule pattern is a choice: a sentinel that never
  matches with must-exist set, so every rule flags a violation and each finding is an
  open action item until an engineer writes the real pattern — or a heuristic draft
  pattern lifted from the first config-looking line of the check text, to accelerate
  authoring. Both are honest; silently importing green is not.
- A drafted pattern carrying `*` or `?` cannot be left as a `Like` pattern. From NCM
  2023.1.1 those characters are wildcards only when the server's
  `ComplianceRulesWildcardsEnabled` advanced setting is selected, and it is not
  selected by default, so the same rule means two different things on two servers.
  Emit it as a `Regex` over the escaped literal instead.
- **Check what the STIG's node scope implies.** A policy report cannot evaluate a
  config downloaded in XML format, which is how Palo Alto devices back up by default,
  and the result is an empty report rather than an error. A scope that matches no node
  fails the same silent way, so count the nodes it selects in `Orion.Nodes` before
  importing, and scope a platform-specific STIG (Cisco IOS XE versus IOS XR, NX-OS or
  ASA) to that platform rather than to the whole vendor.

The calls, in order (all on `Cirrus.PolicyReports`, positional JSON bodies). The tiers
are created bottom-up and linked by ID lists — the one-call nested alternative,
`AddPolicyReport(report, importFlag)` with `importFlag` true, is documented to persist the whole tree
but has been observed in the field creating only the report row over JSON REST:

1. `SELECT PolicyReportID FROM Cirrus.PolicyReports WHERE Name = @n` — collision check
   (the tool also checks policy names and the ids it will submit; see below).
2. `AddPolicyRule(rule)` once per check — each returns the new rule GUID.
3. `AddPolicy(policy, importFlag)` once per benchmark, `importFlag` false with
   `AssignedRulesList` carrying the rule GUIDs — returns the policy GUID.
4. `AddPolicyReport(report, importFlag)` with `importFlag` false and
   `AssignedPoliciesList` carrying the policy GUIDs — returns the report GUID.
5. `GetPolicyReport(reportId, exportFlag)` with `exportFlag` true — read the tree back and
   compare expected relationships and content before claiming success. Since tool 2.0.0
   (2026-10-09) both editions compare the policy count, the rule count and the rule
   names in each policy with what was submitted, the comparison Porter 0.3.0 makes, and
   treat a mismatch or a result that is not a report object as a failed import that is
   rolled back. Rule content is not compared yet, so exact verification remains an open
   improvement; the earlier tool checked only that the counts were nonzero, which is how
   the audit got a partial tree accepted.
6. `StartCaching(selectedReportsIds)` with `[thatGuid]` — the report shows nothing
   until cached, and an empty array would re-cache every report on the server. Skip
   this and call `UpdateReportStatus('Disabled', [thatGuid])` instead when a large
   benchmark needs reviewing before it evaluates: the policy cache otherwise refreshes
   on its own at 11:55 PM daily.

Two things to build in around that sequence, because bottom-up creation is not atomic:

- **Test a rule before importing a hundred of them.**
  `TestRule(policyRule, config)` evaluates an unsaved rule against configuration text
  and `TestRuleOnBackedUpConfig(policyRule, configId)` against a config NCM already
  holds (`SELECT ConfigID, NodeID, ConfigType, DownloadTime FROM NCM.ConfigArchive`).
  Neither creates anything and both need only WebDownloader. Macros are expanded only
  on the backed-up-config route.
- **Roll back a partial import.** Steps 2 to 4 create rules before the policy that
  references them and the policy before the report, so a failure at step 3 or 4 leaves
  rules in the library that nothing points at — invisible in the Compliance view and
  duplicated by the next attempt. Keep the ids as they come back and, on failure,
  delete them with `DeletePolicyRules(ruleIds)` and
  `DeletePolicies(policyIds, deleteChildren)` passing `deleteChildren` false, not with
  `DeletePolicyReports(policyReportIds, deleteChildren)` passing it true, which reaches
  children other reports share.

## Path two: server STIGs into SCM

SolarWinds ships server STIGs as SCM compliance policies — YAML documents tagged
`!policy` with `pluginName: SCM`, whose rules carry actual machine checks
(`!scm.registry` and `!scm.powershell` sources under `!all`/`!any`/`!none`
combinators). The format is documented field by field in
[../modules/scm-compliance-policies.md](../modules/scm-compliance-policies.md). The
[three-policy export audit](../modules/scm-policy-portability-audit.md) adds status
translations, rule dependencies, database sources, legacy identities, and verified
preview/import-validation gaps. A ZIP of SCM YAML is not currently recognized by
the converter's XCCDF ZIP path; select individual policy files until that is implemented.

The import is one verb, because the file itself is the payload:

1. `SELECT PolicyID, Name, UniqueId FROM Orion.PolicyEngine.Policy WHERE Name = @n OR
   UniqueId = @u` — the verb always creates, and SolarWinds rejects an import matching
   an existing policy's name **or** its uniqueId, so check both. A converter that
   derives the uniqueId from the benchmark collides on it even after a rename, and the
   server-side rejection is far less legible than a local one.
2. `Orion.PolicyEngine.Policy.ImportPolicy(yaml)` — the document text verbatim, returns
   the new `PolicyID`.
3. `SELECT COUNT(RuleID) AS N FROM Orion.PolicyEngine.Rule WHERE PolicyID = @p` — an id
   coming back is not evidence the rules landed. Read them back the same way the NCM
   path reads its report back.
4. Assign to nodes (console: Settings → SCM Settings → Policies, or
   `AssignToEntity(policyId, entityUri, data)` — the URI must be a node) and evaluate
   with `PollNowAndEvaluate(policyId, entityUri)`. An assigned policy is otherwise
   evaluated once a day.

For a converted manual STIG, whose rules are attestations rather than machine checks,
the end state of a check an engineer has verified by hand is a rule disabled with a
reason (`Orion.PolicyEngine.Rule.Enabled` and `DisableReason`) rather than one that
reports failed forever. Disabling is global, never per node.

Audit before importing: the `!scm.powershell` scripts in a policy run on every assigned
node. Treat a YAML from outside the organisation as executable content.

## The tool that does all of this

[`apps/disa-stig-conversion-tool/`](../../apps/disa-stig-conversion-tool/README.md) implements both paths with format
auto-detection — zip, `*-xccdf.xml` or `.xsl` (it silently reads the benchmark next to
the stylesheet) goes to NCM; `.yaml` goes to SCM — as a stdlib-only CLI and a desktop
GUI buildable into a Windows executable, with a PowerShell edition that takes the same
options and derives the same ids:

```bash
python3 apps/disa-stig-conversion-tool/disa_stig_tool.py download U_Cisco_IOS_Router_Y26M07_STIG
python3 apps/disa-stig-conversion-tool/disa_stig_tool.py parse U_Cisco_IOS_Router_Y26M07_STIG.zip
python3 apps/disa-stig-conversion-tool/disa_stig_tool.py test U_Cisco_IOS_Router_Y26M07_STIG.zip \
    --host orion.example.com --user admin --config-id <ConfigID>
python3 apps/disa-stig-conversion-tool/disa_stig_tool.py import U_Cisco_IOS_Router_Y26M07_STIG.zip \
    --host orion.example.com --user admin
```

Its intended safety posture is: nothing auto-executes, name collisions are errors
rather than merges, caching/evaluation is started for the specific import only, a
failed import deletes what it created rather than leaving orphaned rules behind, and
`remove --name … --yes` is the supported way to undo one.

Since 2026-10-08 those last two follow the rollback guidance above more closely:

- `remove` reads the report's tree, deletes the report with
  `DeletePolicyReports(policyReportIds, deleteChildren)` passing false, then its policies
  with `DeletePolicies(policyIds, deleteChildren)` passing false, then their rules with
  `DeletePolicyRules(ruleIds)`. A policy another report is still assigned to
  (`Cirrus.PolicyAssignment`) and a rule a surviving policy still uses
  (`Cirrus.PolicyRuleAssignment`) are kept and named in the output. `--dry-run` prints
  the plan without deleting. The earlier `remove` deleted only the report row, which is
  the orphaning state described above.
- The rollback skips any rule or policy id that existed before the run. Rule ids are
  derived deterministically from the DISA rule id, so an earlier import of the same
  release can share them, and whether `AddPolicyRule` keeps a submitted id is not
  documented. The tool snapshots `Cirrus.PolicyRules` and `Cirrus.Policies` for the ids
  it will submit and excludes those from the rollback.
- In a package with several benchmarks, reports imported before a failure stay, are
  cached or disabled as requested, and only the reports not yet imported are written
  out as console files when no wire format is accepted.
- SCM policy output is written as `.scm-policy.yaml`. `.scm-profile` is the
  [collection-profile](../modules/scm-profile-portability-audit.md) export extension;
  a JSON profile is refused rather than sent to `ImportPolicy`, and policy YAML that an
  older build wrote under that extension is still accepted.

Tool 2.0.0 (2026-10-09) also changes how an import fails, in both editions:

- Only an HTTP 400 carrying one of the two rejection messages
  [ncm-compliance-reports.md](../modules/ncm-compliance-reports.md#the-swis-round-trip-20262-verified)
  records counts as "this wire format was refused". Any other 400, and every 401, 403,
  409 or 500, stops that report with the server's message, rolls back what it created,
  and writes no console file. Timeouts, reset connections and bodies that are not JSON
  are reported with their original message and handled like any other failure.
- A nested `AddPolicyReport(report, importFlag)` that is accepted but fails the
  read-back is deleted (the report, then the policies and rules nothing else uses, never
  an id that existed before the run) before the console file is written.
- Before writing, the tool logs the role each verb needs and calls `GetPolicyReport` for
  the nil GUID; HTTP 401 or 403 stops the run. The 2026.2 verb descriptions put
  `AddPolicyRule`, `AddPolicy`, `AddPolicyReport`, `GetPolicyReport` and the `Delete*`
  verbs at WebDownloader and `StartCaching` / `UpdateReportStatus` at WebUploader, all of
  them Orion-administrator only when compliance is restricted to administrators. A
  refused `StartCaching` or `UpdateReportStatus` is logged, the console files still due
  are written, and the run exits non-zero.
- A pinned certificate is enforced on every connection and fails closed, including on
  PowerShell 7, where the PowerShell edition uses an `HttpClient` with a validation
  callback because `Invoke-RestMethod` offers none for server certificates. That path
  is tested offline by forcing it on Windows PowerShell 5.1; it has not been run under
  PowerShell 7 itself.
- Every decision based on an `IN @ids` query over GUIDs (the existing-id snapshot, the
  removal plan, the nested rollback) is preceded by the same query for one id known to
  exist, and stops unless exactly one row comes back. **Unverified:** the documented
  array binding uses integers; whether every server binds GUID strings the same way is
  not documented.

Tool 2.0.0 (2026-10-09) also changes naming, node scope and Linux handling, in both
editions:

- **Version suffix.** Every report, NCM policy and SCM policy name ends in `--suffix`
  (`_v1` by default), and the suffix is part of the uuid5 seed of every generated id (NCM
  `PolicyId` and `RuleId`s, SCM policy and rule `uniqueId`s). Before the first write, the
  import refuses when any name or id it would create already exists and suggests the next
  free suffix, found by listing names with the same base. A new STIG release therefore
  imports next to the old one with `--suffix _v2`, shares no id with it, and the old one
  is removed afterwards by its full `_v1` name. The existing-id snapshot described above
  stays as defense in depth. Imports made before 2.0.0 carry no suffix and share no id
  with suffixed ones.
- **Node scope.** A network STIG's NCM scope is its vendor, and for Cisco also a
  `MachineType LIKE` pattern per platform: `%IOS-XE%`, `%IOS-XR%`, `%NX-OS%`, `%ASA%`,
  and `%IOS%` for classic IOS only when none of those match. **Tentative:** these
  `MachineType` values are to be verified against a live server; nothing in this
  repository records what `Orion.Nodes.MachineType` holds for them. `--machine-type`
  overrides the pattern and `--vendor` the vendor. An unrecognized network STIG (a Router
  or NDM SRG, ESXi) and a Cisco STIG without a recognized platform are refused, offline
  conversion included, instead of being scoped to every Cisco node. The console node
  picker part of `NodeSelectionString` stays Vendor-only; the `MachineType` condition is
  in the SQL part. Before writing, the import counts the matching nodes with the same
  condition as bound SWQL parameters on `Orion.Nodes`, logs both forms and a sample of the
  `MachineType` values the vendor's nodes report, and refuses an empty scope unless
  `--allow-empty-scope` is given.
- **Linux STIGs** stay routed to SCM with the same `!scm.powershell` attestation probe as
  Windows. **Unverified:** no SCM policy source for Linux nodes is documented in this
  repository, so the tool logs a warning and the tool README's "Testing Linux STIGs in
  SCM" section gives the test procedure. `--scm-probe-template` replaces the probe's
  source block per run; it is validated as a small YAML fragment, and its `{id}`
  placeholder receives only the validated vulnerability id, inside a quoted value.

These are offline-tested behaviors against an in-memory stand-in and a local listener,
not a live import test.

For current serializer and verification limitations, read the
[implementation findings](../modules/ncm-compliance-portability-audit.md#code-gaps-affecting-the-stig-tool-and-porter).
In particular, the XML fallback drops advanced conditions if those are supplied, and the
normal generator currently emits only basic (sentinel or heuristic) rules rather than
compiling advanced conditions from DISA prose — the rollback and dry-run additions above
do not close those gaps, they only make a basic-rule import safer to retry and cheaper to
check before committing.

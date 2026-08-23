# DISA STIG Conversion Tool

Takes DISA STIG content exactly as it is published on
[public.cyber.mil/stigs/downloads](https://public.cyber.mil/stigs/downloads/) and imports
it into SolarWinds over the SWIS API, so every STIG requirement becomes a trackable,
remediable item. Two target modules, detected automatically from the file:

| You give it | It imports into |
| --- | --- |
| STIG zip, `*-xccdf.xml`, or the `.xsl` next to it | **NCM** compliance policy report (`Cirrus.PolicyReports`) |
| SCM compliance policy `.yaml` (`!policy`, `pluginName: SCM`) | **Server Configuration Monitor** (`Orion.PolicyEngine.Policy.ImportPolicy`) |

The whole tool is **one self-contained file**, `disa_stig_tool.py` — GUI and CLI
together, standard library only. Download that single file and it runs; nothing else
from this repository is required.

## The GUI

```
python disa_stig_tool.py          ← no arguments (or a double-click on Windows) opens the GUI
```

One window: server IP/FQDN + SWIS port, username/password or a **Login with current
Windows user** checkbox, then either **Browse/drop a file** (zip, xccdf `.xml`, `.xsl`,
SCM `.yaml`) or **enter a STIG package URL**. Buttons: Test connection (also reports
whether NCM and the SCM policy engine are installed on the server), Preview file
(what would be imported, and into which module), Import.

Build the Windows executable on a Windows machine:

```bat
pip install pyinstaller
pyinstaller --onefile --windowed --name DISASTIGConversionTool disa_stig_tool.py
```

(the exe lands in `dist\`). Two optional
packages unlock extras and can be installed before building so PyInstaller bundles them:

- `requests` + `requests-negotiate-sspi` — required for the "current Windows user"
  login (SSPI produces the Negotiate token; Windows only). Without them the checkbox
  reports what to install; username/password login always works.
- `tkinterdnd2` — drag-and-drop onto the window. Without it, Browse does the same job.

Dropping or browsing to the `.xsl` works — it is only the display stylesheet, so the
tool silently reads the `*-xccdf.xml` benchmark next to it.

## The CLI

```bash
# 1. Fetch the package from DISA's public mirror (or download it in a browser)
python3 disa_stig_tool.py download U_Cisco_IOS_Router_Y26M07_STIG

# 2. See what is inside before touching a server
python3 disa_stig_tool.py parse U_Cisco_IOS_Router_Y26M07_STIG.zip --rules

# 3. Import: creates the report, its policies and rules, and starts compliance caching
export SWIS_PASSWORD=…
python3 disa_stig_tool.py import U_Cisco_IOS_Router_Y26M07_STIG.zip \
    --host orion.example.com --user admin
```

There is also `build`, which writes the exact `AddPolicyReport` payload to a JSON file
for inspection or for importing by other tooling.

## What is actually in a STIG zip

DISA's zips come in three shapes, all handled — benchmarks are discovered by content,
not filename, since the naming varies (`*-xccdf.xml`, `*Manualxccdf.xml`,
`*_Benchmark.xml`):

- **xsl + xml (Manual edition)** — a bare [XCCDF 1.1](https://csrc.nist.gov/projects/security-content-automation-protocol/specifications/xccdf)
  benchmark holding every requirement (`Group id="V-…"` → `Rule`) with prose check
  text on each. The `STIG_unclass.xsl` next to it is only a browser stylesheet — pure
  display templates, zero rule data (its check template even *skips* OVAL references).
- **xml only (SCAP Benchmark edition)** — a SCAP 1.3 `data-stream-collection` wrapping
  an XCCDF **1.2** benchmark plus OVAL definitions. Rules carry prefixed IDs
  (stripped on parse), the same fix text as the manual edition, **no** check prose —
  each check is an OVAL machine-check reference, which the tool records in the rule
  comments.
- **Compilation zips** nesting one zip per STIG.

A package can hold several benchmarks (the Cisco IOS Router package has NDM and RTR).
When both editions of the *same* benchmark are present, the manual one is kept:
verified on real files, the fix text matches between editions and only the manual has
the check prose — importing both would just duplicate rules. Packages download from
`https://dl.dod.cyber.mil/wp-content/uploads/stigs/zip/<PackageName>.zip`
(case-sensitive names).

## How STIG fields map to NCM

| XCCDF | NCM rule (verb contract field) |
| --- | --- |
| Group id + severity + Rule title | `RuleName` — `V-215662 [medium] The Cisco router must…` |
| severity high / medium / low | `ErrorLevel` 2 critical / 1 warning / 0 info |
| VulnDiscussion + check-content + IDs (SV, STIG ID, CCIs) | `Comments` |
| fixtext (the Fix Text) | `RemediateScript`, type CLI, **never auto-executed** |
| one XCCDF Group/Rule (each check) | one NCM rule |
| one benchmark | one policy — the device scope (`--node-where`, default `(Nodes.Vendor = 'Cisco')`) |
| one package | one report **named after the zip file** (e.g. `U_Cisco_IOS_Router_Y26M07_STIG`), `Enabled`, in the `DISA STIG` folder |

Manual STIGs describe their checks in prose, not machine-checkable patterns, so the
tool is honest about that:

- **`--mode manual` (default)** — every rule gets a sentinel pattern
  (`STIG-MANUAL-REVIEW-V-…`, must-exist) that no configuration contains, so every rule
  reports a violation on every node in scope. That is the point: each finding is an
  open action item carrying the full check text and the fix script, until an engineer
  replaces the sentinel with a real pattern for that rule in the console.
- **`--mode heuristic`** — seeds each rule with the first config-looking line found in
  the STIG's check text (121 of the 127 Cisco IOS rules get one). These are drafts to
  accelerate rule authoring, not audits — the STIG's examples include sample values
  (`hostname R1`) that must be reviewed per environment.

`RuleId` GUIDs are derived deterministically from the DISA rule ID (uuid5), so
re-importing the same STIG release produces the same rule identities.

## SCM policies (Server Configuration Monitor)

SCM compliance policies are YAML documents tagged `!policy` with `pluginName: SCM`,
whose rules carry the actual machine checks (`!scm.registry`, `!scm.powershell` sources
with `!equals`/`!matches` conditions). The import needs no translation at all: the SWIS
verb `Orion.PolicyEngine.Policy.ImportPolicy(yaml)` takes the file text verbatim and
returns the new PolicyID. The tool refuses to import when a same-name policy already
exists, then leaves assignment to you: Settings → SCM Settings → Policies (or the
`AssignToEntity` verb). Preview parses nothing server-side — it just scans the YAML for
the policy name, rule ids and severities.

## Safety posture

- `ExecuteScriptAutomatically` is always false. A downloaded checklist must never be
  allowed to push configuration to devices on its own — remediation scripts are stored
  for an operator to review and run per node from the console. The same caution applies
  in reverse to SCM YAML: its `!scm.powershell` scripts run on every assigned node, so
  read them before importing a file from outside the organisation.
- The importer never updates or deletes: a name collision is an error, not a merge.
- `download` verifies the fetched file is a zip containing at least one XCCDF
  benchmark before reporting success.

## Where to see the results

NCM: My Dashboards → Network Configuration → Compliance. Each policy report lists its
policies and rules; violations link to the node and show the rule comments (the STIG
check text) and the remediation script (the STIG fix text), which can be executed per
device after review.

SCM: assign the imported policy to nodes under Settings → SCM Settings → Policies, then
My Dashboards → Home → Server Configuration shows per-node, per-rule pass/fail.

---

# API data reference

Everything the tool needs from the platform, verified against the 2026.2 schema and
verb contracts shipped in this repository (`data/schema/2026.2/`). Deeper treatments:
[docs/modules/ncm-compliance-reports.md](../../docs/modules/ncm-compliance-reports.md),
[docs/modules/scm-compliance-policies.md](../../docs/modules/scm-compliance-policies.md),
[docs/automation/disa-stig-import.md](../../docs/automation/disa-stig-import.md).

## Connection

| Item | Value |
| --- | --- |
| Endpoint | `https://<host>:17774/SolarWinds/InformationService/v3/Json` |
| Port | `17774` (platform 2023.1+; `17778` is the deprecated pre-2023 REST port, `17777` is SOAP) |
| Query | `POST /Query` with `{"query": …, "parameters": {…}}` |
| Invoke | `POST /Invoke/{Entity}/{Verb}` with a **positional JSON array** of arguments — order is the contract |
| Auth | HTTP Basic (Orion local or AD account), or Windows Negotiate/SSPI for the current-user option |
| TLS | SWIS ships a self-signed certificate; trust it via a CA bundle rather than disabling verification outside a lab |

Required rights: NCM imports need the NCM **WebUploader** role at minimum
(**WebDownloader** for read/export), and a server option can restrict all compliance
verbs to Orion admins. SCM policy import/assignment requires the **manageNodes**
right on `Orion.PolicyEngine.Policy`.

## NCM: entities and verbs used

The `Cirrus.Policy*` SWQL entities are read-only; all writes are Invoke verbs on
`Cirrus.PolicyReports`.

| Call | Signature (positional) | Used for |
| --- | --- | --- |
| Query | `SELECT PolicyReportID FROM Cirrus.PolicyReports WHERE Name = @n` | Collision check before import |
| `AddPolicyRule` | `(rule)` → new rule GUID (string) | One call per STIG check — the rules are created first |
| `AddPolicy` | `(policy, importFlag)` → new policy GUID (string) | One per benchmark, with `importFlag=false` and `AssignedRulesList` carrying the rule GUIDs just created |
| `AddPolicyReport` | `(report, importFlag)` → new report GUID (string) | Last, with `importFlag=false` and `AssignedPoliciesList` carrying the policy GUIDs |
| `GetPolicyReport` | `(reportId, exportFlag)` with `exportFlag=true` | Read-back verification: the import only reports success once the returned tree holds the expected policies and rules |
| `StartCaching` | `(selectedReportsIds)` — array of GUID strings | Activation; **always pass the specific GUID** — an empty array re-caches every report on the server |
| `GetPolicy` / `GetPolicyRule` | `(policyId, exportFlag)` / `(ruleId)` | Per-item export |

The tool builds bottom-up (rules → policies → report, linked by ID lists) rather than
one nested `AddPolicyReport(report, importFlag)` call with `importFlag` true: the nested route is
documented to persist children, but has been observed in the field creating only the
report row over JSON REST — an empty report with no policies or rules. The explicit
route is unambiguous and verifiable.

`Cirrus.PolicyReports.CacheStatus` values, for watching an import become visible:
`0` not cached, `1` waiting in a queue, `2` caching now, `3` cached, `4` error
(`5` is defined but unused).

### The AddPolicyReport payload, field by field

Contract member names differ from the SWQL column names (`Comments`/`Group` vs
`Comment`/`Grouping`; `SimplePatternText` vs `Pattern`) — payloads use the contract
names below, never the column names.

**PolicyReport** (`SolarWinds.NCM.Contracts.Compliance.PolicyReport`):

| Field | Type | Notes |
| --- | --- | --- |
| `ID` | string GUID | Advisory only — the server always assigns a fresh GUID; resolve by `Name` afterwards |
| `Name`, `Comments`, `Group` | string | `Group` is the console folder |
| `ShowSummaryFlag`, `ShowRulesWithoutViolationFlag` | boolean | Report layout options |
| `AssignedPolicies` | array of Policy | The nested children `importFlag=true` persists |
| `AssignedPoliciesList` | array of string | ID-list alternative used with `importFlag=false` to link policies already on the server |
| `ReportStatus` | string | `Enabled` / `Disabled` in payloads (a boolean in SWQL) |

**Policy** (`…Compliance.Policy`): `PolicyName` (the identity — policies carry no GUID
in export files), `Comments`, `Grouping`, `ConfigTypes` (`Any`, `Running`,
`Startup`, …), `AssignedPolicyRules` / `AssignedRulesList` (same nested-vs-ID-list pair
as above), and `NodeSelectionString` — the literal prefix `Criteria:`, optionally the
console node-picker's XML-escaped `<QUERY>` state, then the ` Where ( … )` clause that
actually filters nodes, e.g. `Criteria: Where ( (Nodes.Vendor = 'Cisco') )`.

**PolicyRule** (`…Compliance.PolicyRule`), all 21 members:

| Field | Type | The tool sets |
| --- | --- | --- |
| `RuleId` | string GUID | uuid5 of the DISA rule id (stable across re-imports) |
| `RuleName`, `Comments`, `Grouping`, `Owner` | string | Name ≤250 chars; comments carry discussion + check text + CCIs |
| `SimplePatternText` | string | Sentinel or heuristic pattern |
| `PatternType` | string | `Like` (or `Regex`) |
| `PatternMustExist` | boolean | `true` = violation when the pattern is missing |
| `AdvancedMode` | boolean | `false` — simple pattern, not `MultiLineRulePatterns` |
| `MultiLineRulePatterns` | array | Empty; members are `{Pattern, PatternType, IsRegEx, Condition, Criteria, BeginBracket, EndBracket}` |
| `ConfigBlockStart` / `ConfigBlockEnd` / `ConfigBlockPatternType` / `ConfigBlockMustExist` / `IsConfigBlockPatternRegEx` | string/boolean | Unused (`""` / `Like` / `false`) — restricts matching to a config stanza |
| `ErrorLevel` | number | `0` info, `1` warning, `2` critical |
| `RemediateScript` | string | The STIG Fix Text |
| `RemediateScriptType` | string | `CLI` |
| `ExecuteScriptAutomatically` | boolean | **Always `false`** — `true` pushes remediation to failing devices on its own |
| `ExecuteRemediationScriptPerBlock`, `ExecuteScriptInConfigMode` | boolean | `false` |

## SCM: entities and verbs used

SCM compliance rides the policy engine namespace, `Orion.PolicyEngine.` (12 entities).
All verbs live on `Orion.PolicyEngine.Policy`; positional JSON bodies.

| Call | Signature (positional) | Used for |
| --- | --- | --- |
| Query | `SELECT PolicyID FROM Orion.PolicyEngine.Policy WHERE Name = @n` | Collision check — `ImportPolicy` always creates |
| `ImportPolicy` | `(yaml)` → new `PolicyID` (number) | The import; the argument is the `!policy` YAML document text **verbatim** |
| `ExportPolicy` | `(policyId)` → YAML string | Round-trip/export |
| `AssignToEntity` | `(policyId, entityUri, data)` | Assignment; the URI must be a Node for SCM policies (`swis://…/Orion/Orion.Nodes/NodeID=42`) |
| `PollNowAndEvaluate` | `(policyId, entityUri)` | Collect and evaluate every rule against that node now |
| `UnassignFromEntity` | `(policyId, entityUri)` | Removal |

The tool imports and stops there; assignment and evaluation are console (or
`AssignToEntity`) steps, because which nodes a STIG applies to is an operator decision.

Useful readback entities: `Orion.PolicyEngine.Rule` holds each rule's `DisplayId`
(the `V-…` number), `Severity` (`100` low / `200` medium / `300` high — the YAML's
`Low`/`Medium`/`High` words), check/remediation text, and the condition **as YAML text**
in `ConditionYAML`/`PreconditionYAML`. `Orion.PolicyEngine.AssignedRule.Status` is
`0` unknown, `1` passed, `2` failed, `3` disabled. `Orion.PolicyEngine.PolicyCompliance`
is the per-policy rollup for alerting and reporting.

### The policy YAML, in brief

Root tag `!policy` with `name`, `uniqueId` (GUID, recognises the same policy across
servers), `pluginName: SCM`, `description`, `version`, `builtIn`, and `rules:`. Each
rule: `displayId`, `uniqueId`, `name`, `severity` (`High`/`Medium`/`Low`),
`description`, `remediationDescription`, `checkText`, optional `precondition`, and a
`condition` tree of `!all`/`!any`/`!none` combinators over `!equals` (`expected:`),
`!matches` (`expression:`) and `!notExists` comparisons, each reading a source:
`!scm.registry` (`key:`, `name:`) or `!scm.powershell` (`description:`, `script:`).
YAML anchors (`&o0`/`*o0`) share one source across several comparisons. Full format:
[docs/modules/scm-compliance-policies.md](../../docs/modules/scm-compliance-policies.md).

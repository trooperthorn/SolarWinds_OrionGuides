# NCM compliance policy reports: the export file and its round trip

A policy report checks device configurations against rules and reports the violations.
The console can export a whole report — policies and rules included — as one XML file,
and that file is how compliance content moves between servers and between teams
(SolarWinds ships DISA STIG, SOX, HIPAA, PCI and Cisco-audit sample reports in exactly
this format).

**Source.** Derived by parsing three real console exports — the shipped SOX Security
Report, a DISA STIG routing-interface report, and the Cisco Security Audit sample —
against the 2026.2 schema and verb contract. [ncm.md](ncm.md) covers the entity model
and the full compliance verb table; this page is the file format and the API round trip.

## The three-tier structure

```
PolicyReport            the file's root — one report
  └─ Policy[]           which nodes and config type each group of rules applies to
      └─ PolicyRule[]   the actual tests, each with optional remediation
```

The same rule can appear in several policies and the same policy in several reports —
the file denormalizes that: each export carries complete copies of everything it uses.

## The file

```xml
<?xml version="1.0" encoding="utf-16"?>
<PolicyReport xmlns:xsd="http://www.w3.org/2001/XMLSchema"
              xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <ID>efbb7d93-3d68-42ab-be23-7bb1ddd21468</ID>
  <Name>SOX Security Report</Name>
  <Comments>Sample Report for SOX (Sarbanes-Oxley)</Comments>
  <Group>SOX Reports</Group>
  <ShowSummaryFlag>false</ShowSummaryFlag>
  <ShowRulesWithoutViolationFlag>true</ShowRulesWithoutViolationFlag>
  <AssignedPolicies>
    <Policy>…</Policy>
  </AssignedPolicies>
  <ReportStatus>Enabled</ReportStatus>
</PolicyReport>
```

**The encoding lies.** All three sample files declare `encoding="utf-16"` in the XML
prolog while the bytes on disk are UTF-8. Any parser that trusts the declaration
fails; sniff the byte-order mark and fall back to UTF-8, never believe the prolog.

### Policy

```xml
<Policy>
  <NodeSelectionString>Criteria:&lt;QUERY&gt;…&lt;/QUERY&gt; Where ( (Nodes.Vendor = 'Cisco') )</NodeSelectionString>
  <ConfigTypes>Any</ConfigTypes>
  <AssignedPolicyRules>
    <PolicyRule>…</PolicyRule>
  </AssignedPolicyRules>
  <Grouping>SOX Policies</Grouping>
  <Comments />
  <PolicyName>SOX Cisco Password Security</PolicyName>
</Policy>
```

- `NodeSelectionString` is three things concatenated: the literal prefix `Criteria:`,
  an XML-escaped `<QUERY>` document (the console's node-picker state), and a
  SQL-flavoured ` Where ( … )` suffix that is what actually filters nodes.
- **Policies carry no GUID in the file** — `PolicyName` is the identity. Rules do
  carry a `RuleId` GUID.
- `ConfigTypes` restricts which downloaded config type the rules scan (`Any`,
  `Running`, `Startup`, …). Reports never run against XML-format configs.

### PolicyRule — every field, from the samples

| Field | Meaning |
| --- | --- |
| `RuleId` | GUID — the only per-rule identity that travels |
| `RuleName`, `Comments`, `Grouping`, `Owner` | naming and organization |
| `SimplePatternText` | the pattern, when the rule is simple mode |
| `PatternType` | `Like` or `Regex` |
| `PatternMustExist` | `true` = violation when missing; `false` = violation when present |
| `ErrorLevel` | severity: `0` info, `1` warning, `2` critical |
| `AdvancedMode` | `true` = the test is `MultiLineRulePatterns`, not the simple pattern |
| `MultiLineRulePatterns` | list of `MultiLineRulePattern` {`Pattern`, `PatternType`, `Criteria`, `Condition`, `BeginBracket`, `EndBracket`} — multi-line/AND-OR matching |
| `ConfigBlockStart` / `ConfigBlockEnd` / `ConfigBlockPatternType` / `ConfigBlockMustExist` | restrict matching to a config block (e.g. one interface stanza) |
| `RemediateScript` | CLI script run to fix a violation — the shipped DISA STIG rules carry full "Fix Text" scripts |
| `RemediateScriptType` | `CLI`, or a config change template |
| `ExecuteScriptAutomatically` | **the dangerous one** — `true` pushes the remediation to failing devices automatically |
| `ExecuteRemediationScriptPerBlock`, `ExecuteScriptInConfigMode` | how the script is delivered |

A rule with `ExecuteScriptAutomatically=true` **changes device configuration on its
own** once the report is imported and cached. Audit every imported report for this
flag before it lands on a production server — a compliance file from outside the
organisation is executable content, not just a checklist.

## The SWIS round trip (2026.2, verified)

All writes are Invoke verbs on `Cirrus.PolicyReports` — the `Cirrus.Policy*` SWQL
entities are read-only. Positional JSON bodies on the REST endpoint.

| Step | Call |
| --- | --- |
| Inventory | `SELECT PolicyReportID, Name, Grouping, ReportStatus, CacheStatus FROM Cirrus.PolicyReports` |
| Export | `GetPolicyReport(reportId, exportFlag=true)` → the full nested object (maps 1:1 to the file's elements) |
| Import | `AddPolicyReport(report, importFlag=true)` → the **new server-assigned GUID**; nested policies and rules persist in the same call |
| Per-item | `GetPolicy(policyId, exportFlag)` / `GetPolicyRule(ruleId)` / `AddPolicy(policy, importFlag)` / `AddPolicyRule(rule)` |
| Rule dry run | `TestRule(policyRule, configText)` / `TestRuleOnBackedUpConfig(policyRule, configId)` — evaluate an unsaved rule against real config |
| Activate | `StartCaching([reportId])` — an imported report shows nothing until cached; **always pass the specific GUID** (an empty array re-caches every report on the server) |

Round-trip gotchas:

- The file's `ID` is advisory: `AddPolicyReport` always assigns a fresh GUID.
  Resolve by `Name` after import.
- Contract member names differ from SWQL columns (`Comments`/`Group` vs
  `Comment`/`Grouping`; rule `SimplePatternText` vs column `Pattern`) — map file
  fields to the verb contract, never to column names.
- The `Update*` verbs have no `importFlag`, so they touch only their own level;
  cascading replace means delete-then-add, and `DeletePolicyReports(ids,
  deleteChildren=true)` can rip shared policies out from under other reports —
  default `deleteChildren=false`.
- `ReportStatus` is the string `Enabled`/`Disabled` in payloads but a boolean in SWQL.
- Verb access is role-gated NCM-side (download = WebDownloader, upload = WebUploader),
  and the whole compliance verb set can be restricted to admins by a server option.

## Porter

The Porter utility in this repository (`apps/porter`) implements this round trip as
its NCM Compliance area: console-compatible XML out (UTF-16, matching element order),
`AddPolicyReport(report, true)` in, name-collision skip, and `StartCaching` for the
new report. Its import validation raises a **blocking security flag** for every
auto-executing remediation rule; the file cannot be imported until the operator
explicitly acknowledges the flags.

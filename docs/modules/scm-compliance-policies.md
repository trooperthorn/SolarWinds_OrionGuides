# SCM compliance policies: the YAML format and its round trip

Server Configuration Monitor's compliance side answers a different question than its
drift-detection side. Where [scm.md](scm.md) covers profiles — *what changed on this
server* — a compliance **policy** evaluates rules against a node and reports pass or
fail: *does this server meet the standard*. SolarWinds ships DISA STIG and CIS policies
in this system (the console's SCM Settings page offers them for download), every one of
them a YAML document in the format this page describes, and the whole thing rides a
generic rule engine in the `Orion.PolicyEngine.` namespace rather than `Orion.SCM.`.

**Source.** Derived by parsing a real shipped policy — the Microsoft IIS 8.5 Server STIG
(version 1, rel. 10) export, 18 rules — against the 2026.2 schema and verb contract.

## The entity model

`Orion.PolicyEngine.` contributes 12 entities. The ones that carry the weight:

| Entity | What it is |
|---|---|
| `Orion.PolicyEngine.Policy` | The policy: `Name`, `PluginName` (`SCM` for these), `Version`, `BuiltIn`, `UniqueId` ("valuable for identifying imported/exported policies"), `Status`, and two console URLs |
| `Orion.PolicyEngine.Rule` | One rule: `DisplayId` (the STIG `V-…` number), `Severity` (`0` undefined, `100` low, `200` medium, `300` high), `PreconditionYAML` and `ConditionYAML` holding the rule's logic **as YAML text in columns**, `Description`, `CheckText`, `RemediationDescription`, `Enabled` + `DisableReason` |
| `Orion.PolicyEngine.AssignedPolicy` / `AssignedRule` | One assignment of a policy/rule to an entity. `EntityName` — "SCM uses only \"Orion.Nodes\"". `AssignedRule.Status`: `0` unknown, `1` passed, `2` failed, `3` disabled; waiver columns (`RuleWaiverID`, `OriginalStatus`) record accepted exceptions |
| `Orion.PolicyEngine.PolicyCompliance` | Per-policy rollup of evaluated/passed/failed, "can be used in alerting and reporting" |
| `Orion.PolicyEngine.DataSource` / `AssignedRuleDataSource` | The collected inputs a rule evaluates — what `Orion.SCM.ProfileElementPolicyDataSources` maps profile elements onto |

Policies also surface in SWQL as rows joined to nodes, so a compliance report is one
query:

```sql
SELECT AR.Rule.Policy.Name AS PolicyName, AR.Rule.DisplayId, AR.Rule.Name,
       AR.StatusName, AR.Node.Caption, AR.LastUpdate
FROM Orion.PolicyEngine.AssignedRule AS AR
WHERE AR.Status = 2
ORDER BY PolicyName, AR.Rule.DisplayId
```

## The file

A policy is one YAML document using application-specific tags. The root is `!policy`:

```yaml
!policy
name: IIS 8.5 Server STIG (version 1, rel. 10)
uniqueId: 81d7a7f2-d976-486d-a6b9-39f2298c2348
pluginName: SCM
description: 'This policy compares the configuration for a IIS 8.5 Server to …'
version: 2
builtIn: true
rules:
- displayId: V-76759
  uniqueId: 5bef45ff-f28f-4d1b-b0e6-51482d0dce72
  name: An IIS 8.5 web server must maintain the confidentiality of controlled information …
  severity: High
  description: Transport Layer Security (TLS) encryption is a required security setting …
  remediationDescription: "Access the IIS 8.5 Web Server.\n\nAccess an administrator …"
  checkText: "Access the IIS 8.5 Web Server.\n\n… If any of the respective registry
    paths do not exist or are configured with the wrong value, this is a finding."
  condition: !all
    of:
    - !equals
      expected: 0
      source: !scm.registry
        key: HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL\Protocols\TLS 1.1\Server
        name: DisabledByDefault
```

Field by field, at the policy level: `name`, `uniqueId` (the GUID that identifies the
same policy across servers, exactly like the entity column), `pluginName: SCM`,
`description`, `version`, `builtIn`, `rules`. At the rule level: `displayId` (the DISA
vulnerability id), `uniqueId`, `name`, `severity` (`High`/`Medium`/`Low` as words —
mapped to the entity's `300`/`200`/`100`), `description`, `remediationDescription`,
`checkText`, an optional `precondition`, and the `condition`. The prose fields land
verbatim in the `Orion.PolicyEngine.Rule` columns of the same names, so what the console
shows an operator next to a failing rule is exactly the STIG's own check and fix text.

### Conditions: combinators, comparisons, sources

A condition is a tree of three layers of YAML tags:

**Combinators** take a list under `of:` — `!all` (every child must hold), `!any` (at
least one), `!none` (none may hold). They nest: the IIS machine-key rule wraps an `!any`
of three accepted HMAC algorithms inside an `!all`.

**Comparisons** test one collected value: `!equals` (`expected:` against the source's
output — numbers, booleans and strings all appear in the shipped file), `!matches`
(`expression:` — a substring/pattern match over the source's output, used for
flag-lists like `logExtFileFlags`), and `!notExists` (the source must have no value —
used for registry keys whose absence is compliant).

**Sources** are what gets collected on the node:

- `!scm.registry` — `key:` (a full `HKEY_LOCAL_MACHINE\…` path) and `name:` (the value
  name).
- `!scm.powershell` — `description:` (the label the console shows for the collected
  datum) and `script:` (the PowerShell to run; the shipped rules read IIS configuration
  through `appcmd.exe` and `Get-WebConfigurationProperty`, print the interesting value
  with `Write-Host`, and `throw` on collection failure so the rule reports an error
  rather than a false pass).

A `precondition:` uses the same grammar and gates whether the rule applies at all — the
IIS Internet-Printing rule only evaluates when a `!scm.powershell` probe finds the
Print Services role installed, otherwise the rule is not applicable rather than passed
or failed.

Two YAML features matter for parsing these files: anchors and aliases (`&o0` / `*o0`)
de-duplicate a source that several comparisons share — one collection, many tests — and
the custom tags mean a stock `yaml.safe_load` refuses the document. Either register the
tags with the loader or, better, don't parse at all: the import verb wants the text.

## The SWIS round trip (2026.2, verified)

The verbs live on `Orion.PolicyEngine.Policy`. Positional JSON bodies on the REST
endpoint; the entity requires `manageNodes` for anything beyond read.

| Step | Call |
|---|---|
| Inventory | `SELECT PolicyID, Name, PluginName, Version, BuiltIn, UniqueId FROM Orion.PolicyEngine.Policy` |
| Export | `ExportPolicy(policyId)` → the policy with rules as one YAML string |
| Import | `ImportPolicy(yaml)` → the new `PolicyID` (a number). The parameter is the document text verbatim — no wrapper object, no translation |
| Assign | `AssignToEntity(policyId, entityUri, data)` — `entityUri` is a SWIS URI, and "For SCM policies it needs to be a Node"; `data` is "optional additional data" with no documented content — **unverified**, observe the console's own call before composing one |
| Evaluate now | `PollNowAndEvaluate(policyId, entityUri)` — collection plus evaluation of every rule in the policy against that node |
| Unassign | `UnassignFromEntity(policyId, entityUri)` |

Round-trip gotchas:

- `ImportPolicy` always creates; there is no update-by-import. The file's `uniqueId` is
  how you *recognise* a re-import of the same policy (the `UniqueId` column), not how
  the server deduplicates it — query `Name`/`UniqueId` first and refuse or delete
  before importing again.
- A `builtIn: true` in the file does not make the imported row `BuiltIn` — that column
  is read-only and "true only for policies deployed with the SCM installation"
  (**unverified** for the import path specifically; the column's read-only contract is
  schema fact).
- The rules' scripts run on monitored nodes with the SCM agent's authority. A policy
  YAML from outside the organisation is executable content: read every
  `!scm.powershell` `script:` block before importing, the same way
  [ncm-compliance-reports.md](ncm-compliance-reports.md) demands auditing
  `RemediateScript` blocks.
- Assignment is per node. Nothing evaluates — and `PolicyCompliance` stays empty —
  until the policy is assigned (console: Settings → SCM Settings → Policies) and
  polled.

## DISA STIGs, two modules, one repository

The same STIG exists in two shapes in this repository's world: DISA's own XCCDF zip
(imported into NCM compliance for network devices) and SolarWinds' SCM policy YAML
(evaluated agent-side on servers). The end-to-end import path for both — including the
`apps/stig2ncm` tool that detects the format and picks the module — is
[../automation/disa-stig-import.md](../automation/disa-stig-import.md).

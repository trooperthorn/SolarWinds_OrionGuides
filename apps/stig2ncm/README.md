# stig2ncm — DISA STIG → NCM compliance report importer

A single-file, stdlib-only Python CLI that takes a STIG package exactly as DISA
publishes it on [public.cyber.mil/stigs/downloads](https://public.cyber.mil/stigs/downloads/)
and imports it as a SolarWinds NCM compliance policy report over the SWIS API, so every
STIG requirement becomes a trackable, remediable item in the NCM console.

```bash
# 1. Fetch the package from DISA's public mirror (or download it in a browser)
python3 stig2ncm.py download U_Cisco_IOS_Router_Y26M07_STIG

# 2. See what is inside before touching a server
python3 stig2ncm.py parse U_Cisco_IOS_Router_Y26M07_STIG.zip --rules

# 3. Import: creates the report, its policies and rules, and starts compliance caching
export SWIS_PASSWORD=…
python3 stig2ncm.py import U_Cisco_IOS_Router_Y26M07_STIG.zip \
    --host orion.example.com --user admin
```

There is also `build`, which writes the exact `AddPolicyReport` payload to a JSON file
for inspection or for importing by other tooling.

## What is actually in a STIG zip

The zip contains one folder per benchmark. The file that matters is
`*-xccdf.xml` — an [XCCDF 1.1](https://csrc.nist.gov/projects/security-content-automation-protocol/specifications/xccdf)
benchmark holding every requirement (`Group id="V-…"` → `Rule`). The `STIG_unclass.xsl`
next to it is only the stylesheet browsers use to render that XML; it carries no data.
A package can hold several benchmarks — the Cisco IOS Router package has NDM
(device management, 35 rules) and RTR (routing, 92 rules) — and compilation zips that
nest one zip per STIG are handled too.

## How STIG fields map to NCM

| XCCDF | NCM rule (verb contract field) |
| --- | --- |
| Group id + severity + Rule title | `RuleName` — `V-215662 [medium] The Cisco router must…` |
| severity high / medium / low | `ErrorLevel` 2 critical / 1 warning / 0 info |
| VulnDiscussion + check-content + IDs (SV, STIG ID, CCIs) | `Comments` |
| fixtext (the Fix Text) | `RemediateScript`, type CLI, **never auto-executed** |
| one benchmark | one policy (`--node-where` scopes the nodes, default Cisco) |
| one package | one report, `Enabled`, in the `DISA STIG` folder |

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

## The API round trip

Everything rides the verbs on `Cirrus.PolicyReports` (the `Cirrus.Policy*` SWQL
entities are read-only), documented and verified in
[docs/modules/ncm-compliance-reports.md](../../docs/modules/ncm-compliance-reports.md):

1. `SELECT PolicyReportID FROM Cirrus.PolicyReports WHERE Name = @n` — collision
   check; the tool refuses to overwrite an existing report.
2. `AddPolicyReport(report, importFlag=true)` — one call persists the report and all
   nested policies and rules; returns the server-assigned GUID.
3. `StartCaching([newId])` — a report shows nothing until cached; the specific GUID is
   always passed, because an empty array would re-cache every report on the server.

Connection details match [scripts/python/swis_client.py](../../scripts/python/swis_client.py):
REST on port 17774, basic auth, password from `SWIS_PASSWORD` or an interactive
prompt, `--ca-file` to trust the server certificate properly (`--insecure` for labs
only). The account needs the NCM WebUploader role at minimum; a server option can
restrict the compliance verbs to admins.

## Safety posture

- `ExecuteScriptAutomatically` is always false. A downloaded checklist must never be
  allowed to push configuration to devices on its own — remediation scripts are stored
  for an operator to review and run per node from the console.
- The importer never updates or deletes: a name collision is an error, not a merge.
- `download` verifies the fetched file is a zip containing at least one XCCDF
  benchmark before reporting success.

## Where to see the results

My Dashboards → Network Configuration → Compliance. Each policy report lists its
policies and rules; violations link to the node and show the rule comments (the STIG
check text) and the remediation script (the STIG fix text), which can be executed per
device after review.

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
them, and the `apps/stig2ncm` tool in this repository that does it end to end.

**Source.** Verified against a real DISA package (Cisco IOS Router, Y26M07 release: NDM
V3R8 and RTR V3R4 benchmarks, 127 rules) and a real SCM policy export (Microsoft IIS 8.5
Server STIG version 1 rel. 10, 18 rules), and against the 2026.2 schema and verb
contracts.

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

- One **report** per STIG package, one **policy** per benchmark (its
  `NodeSelectionString` scopes the nodes — `Criteria: Where ( (Nodes.Vendor = 'Cisco') )`
  is the part that filters), one **rule** per XCCDF rule.
- Severity → `ErrorLevel`: high `2` (critical), medium `1` (warning), low `0` (info).
- Discussion, check content and every id land in the rule's `Comments`; the fix text
  becomes `RemediateScript` (type CLI) with `ExecuteScriptAutomatically` **false** — a
  downloaded checklist must never push configuration on its own.
- Because the checks are prose, the rule pattern is a choice: a sentinel that never
  matches with must-exist set, so every rule flags a violation and each finding is an
  open action item until an engineer writes the real pattern — or a heuristic draft
  pattern lifted from the first config-looking line of the check text, to accelerate
  authoring. Both are honest; silently importing green is not.

The calls, in order (all on `Cirrus.PolicyReports`, positional JSON bodies):

1. `SELECT PolicyReportID FROM Cirrus.PolicyReports WHERE Name = @n` — collision check.
2. `AddPolicyReport(report, importFlag)` with `importFlag` true — persists report,
   policies and rules in one call, returns the server-assigned GUID.
3. `StartCaching(selectedReportsIds)` with `[thatGuid]` — the report shows nothing
   until cached, and an empty array would re-cache every report on the server.

## Path two: server STIGs into SCM

SolarWinds ships server STIGs as SCM compliance policies — YAML documents tagged
`!policy` with `pluginName: SCM`, whose rules carry actual machine checks
(`!scm.registry` and `!scm.powershell` sources under `!all`/`!any`/`!none`
combinators). The format is documented field by field in
[../modules/scm-compliance-policies.md](../modules/scm-compliance-policies.md).

The import is one verb, because the file itself is the payload:

1. `SELECT PolicyID FROM Orion.PolicyEngine.Policy WHERE Name = @n` — the verb always
   creates, so check first.
2. `Orion.PolicyEngine.Policy.ImportPolicy(yaml)` — the document text verbatim, returns
   the new `PolicyID`.
3. Assign to nodes (console: Settings → SCM Settings → Policies, or
   `AssignToEntity(policyId, entityUri, data)` — the URI must be a node) and evaluate
   with `PollNowAndEvaluate(policyId, entityUri)`.

Audit before importing: the `!scm.powershell` scripts in a policy run on every assigned
node. Treat a YAML from outside the organisation as executable content.

## The tool that does all of this

[`apps/stig2ncm/`](../../apps/stig2ncm/README.md) implements both paths with format
auto-detection — zip, `*-xccdf.xml` or `.xsl` (it silently reads the benchmark next to
the stylesheet) goes to NCM; `.yaml` goes to SCM — as a stdlib-only CLI and a desktop
GUI buildable into a Windows executable:

```bash
python3 apps/stig2ncm/stig2ncm.py download U_Cisco_IOS_Router_Y26M07_STIG
python3 apps/stig2ncm/stig2ncm.py parse U_Cisco_IOS_Router_Y26M07_STIG.zip
python3 apps/stig2ncm/stig2ncm.py import U_Cisco_IOS_Router_Y26M07_STIG.zip \
    --host orion.example.com --user admin
```

Its safety posture is the one this page argues for: nothing auto-executes, name
collisions are errors rather than merges, and caching/evaluation is started for the
specific import only.

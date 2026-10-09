# DISA STIG Conversion Tool

Takes DISA STIG content exactly as it is published on
[public.cyber.mil/stigs/downloads](https://public.cyber.mil/stigs/downloads/) and imports
it into SolarWinds over the SWIS API, so every STIG requirement becomes a trackable,
remediable item. Two target modules, detected automatically from the file:

| You give it | It imports into |
| --- | --- |
| STIG zip / xccdf `.xml` / `.xsl` for a **network device** (Cisco, Juniper, Arista, Palo Alto, F5, Fortinet, …) | **NCM** compliance policy report (`Cirrus.PolicyReports`), node scope set from the vendor and, for Cisco, the platform's `MachineType` ([node scope](#node-scope-vendor-and-cisco-platform)) |
| STIG zip / xccdf `.xml` for a **server OS** (Windows, Linux, RHEL, Debian, Ubuntu, CentOS) | **Server Configuration Monitor** — converted to an SCM policy and imported via `Orion.PolicyEngine.Policy.ImportPolicy` (Linux: see [Testing Linux STIGs in SCM](#testing-linux-stigs-in-scm)) |
| SCM compliance policy `.yaml` / `.scm-policy.yaml` (`!policy`, `pluginName: SCM`) | **Server Configuration Monitor**, imported verbatim |

The **Compliance target** dropdown (or `--target`) controls the routing:
**Auto Compliance Assignment** (default) decides from the file and benchmark
names as above; **Network Compliance** forces NCM; **Server Compliance** forces
SCM. Auto falls back to NCM when nothing is recognized, but since 2.0.0 (2026-10-09) such
a STIG (the Router or NDM SRG, ESXi, an unlisted product) gets no node scope by default:
it is refused, offline `convert` included, until `--vendor` or `--node-where` says which
nodes it applies to. Earlier builds scoped it to every Cisco node.

The tool ships in **two self-contained single-file editions**, both at version
**2.0.0** (`TOOL_VERSION` in the Python file, `$script:ToolVersion` in the PowerShell
file; every run log records it). The Python edition is the reference. For the same input
and [version suffix](#version-suffix-and-the-upgrade-workflow) both derive the same NCM
`RuleId`s and `PolicyId`s, the same SCM policy and rule `uniqueId`s, the same report and
policy names, the same node scope and the same SCM probe, and the generated basic-rule
payloads are byte-identical; `test_disa_stig_tool.py` compares the two editions on fixed
inputs (suffixes, Cisco platforms, scope refusals, probe templates) whenever PowerShell
is available. Do not assume full
serialization parity for advanced rules: the
[NCM portability audit](../../docs/modules/ncm-compliance-portability-audit.md)
records differences and offline-reproduced limitations. The generated default rules are basic:

- **`disa_stig_tool.py`** — Python 3, standard library only (no `orionsdk`).
- **`disa_stig_tool.ps1`** — Windows PowerShell 5.1+ / PowerShell 7+, built-in .NET
  classes only (no `SwisPowerShell`, no gallery modules). Run it plain for the
  WinForms GUI, or with the parameters in [the table below](#cli-parameters-in-both-editions).
  The file is pure ASCII on purpose: Windows PowerShell 5.1 reads a script without a
  byte-order mark in the ANSI code page.

**Policies imported by older PowerShell builds carry different ids.** Before this
change the PowerShell edition seeded the NCM `PolicyId` and the SCM policy `uniqueId`
from the benchmark id and title concatenated, where the Python edition uses the
benchmark id alone (the title only when there is no id). An SCM policy imported by an
older PowerShell build therefore has a `uniqueId` no current build derives, so a
re-import of the same benchmark is not caught by the `UniqueId` collision check; the
`Name` check still catches it unless the name changed. Look those policies up by name.
NCM policies imported by those builds were submitted with a different `PolicyId`
(**Unverified:** whether `AddPolicy` keeps a submitted `PolicyId` or assigns its own is
not documented; compare `Cirrus.Policies.PolicyID` after an import to find out). Rule
ids (`RuleId`, rule `uniqueId`) were already identical in both editions. Since 2.0.0 every
id also carries the version suffix, so no current build derives any pre-2.0.0 id; see
[the upgrade workflow](#version-suffix-and-the-upgrade-workflow).

Both GUIs open with a disclaimer — *"This is not built by SolarWinds Inc. or DISA.
All Code is visible for Code Audit and documentation is available for SWIS calls."* —
and require acknowledging that imported reports must be checked and that resolution
falls on Agency application of the DISA STIG standards before the tool opens.

## The GUI

```
python disa_stig_tool.py          ← no arguments (or a double-click on Windows) opens the GUI
```

One window: server IP/FQDN + SWIS port, username/password or a **Login with current
Windows user** checkbox with a **live connection status line** beneath it, a file list
taking **up to 10 STIG files per batch** (zip, xccdf `.xml`, `.xsl`, SCM policy
`.yaml`/`.scm-policy.yaml`, a legacy policy `.scm-profile`, or a URL), the
**Compliance target** dropdown, the **NCM node scope** box (`auto`, or a WHERE clause like
`--node-where`), a
**Import the NCM report disabled (no caching) so it can be reviewed first** checkbox
(the CLI's `--disabled` / PowerShell's `-ImportDisabled`), a **Name suffix** box (`_v1`
by default, the CLI's `--suffix`) and an **Import even when the NCM node scope matches no
node** checkbox (`--allow-empty-scope`). The GUIs use the default SCM probe for the
detected OS; a probe template is a CLI option. A batch
imports into **one module only — NCM or SCM, never both**: the first file selected
locks the module (a notice says so), and files of the other kind are skipped with a
message rather than misprocessed.

Buttons carry their outcome as color: **Test Connection** turns green on success, red
on failure, and **yellow** when connected but limited — a pre-2023.1 SWIS version
(the mismatch is written to the log) or the NCM/SCM entities not readable by the
account. **Import** and **Local File Conversion Only** turn green when everything
completed, yellow on a partial result, red on failure. Successful imports print a
green **SUCCESS** line with the report/policy name; errors are prefixed `[NCM]` or
`[SCM]`. The detailed log is hidden by default behind a **Show detailed log** button
and expands automatically when there is an issue. The path of the [run log](#run-log)
is shown at the bottom of the window and in the summary when the window opens and after
every batch; `python disa_stig_tool.py gui --log-file PATH --log-level debug` (or
`disa_stig_tool.ps1 -LogFile PATH -LogLevel debug`) chooses where it goes.

**Verify TLS certificate is on by default**; **Trust server certificate…** fetches the
certificate SWIS presents (the stock self-signed `SolarWinds-Orion` one), shows its
SHA-256 fingerprint, and pins the session to exactly that certificate — held in
memory only, like the credentials. A pinned certificate is checked even when the
verify box is cleared ([Security rules](#security-rules)).

## Offline conversion — no server connection

When the machine running the tool cannot reach the SolarWinds server, the same
conversions run without connecting at all — point at the file or URL and convert:

```bash
python3 disa_stig_tool.py convert U_Cisco_IOS_Router_Y26M07_STIG.zip
```

(or the **Local File Conversion Only** button in the GUI; `build` is an alias — the PowerShell edition uses `-Convert`).
The outputs are the exact payloads the API import would have sent:

- **NCM** → one `.ncm-report.xml` per benchmark, byte-matched to a real console
  export — import with Compliance → Manage Policy Reports → **Import** in the web
  console.
- **SCM** → one `.scm-policy.yaml` per benchmark (the `!policy` YAML document) — import
  through the console, or later with this tool's `import` against the file.

The repository's SCM documentation names no file extension for compliance policies,
and the policies SolarWinds publishes are plain `.yaml`, so the tool writes
`.scm-policy.yaml`. Earlier builds wrote the same YAML as `.scm-profile`, but that
extension belongs to SCM **collection profiles**: UTF-16 JSON documents that define what
SCM collects and carry no compliance rules
([SCM profile audit](../../docs/modules/scm-profile-portability-audit.md)). On input the
tool classifies a `.scm-profile` by its content. Policy YAML from an older build is still
imported, with a note asking for the file to be renamed; a JSON collection profile is
refused with a pointer to SCM's profile import (`Orion.SCM.Profiles.ImportProfile`), since
it is not a compliance policy. A policy `.yaml` exported as UTF-16 is decoded either way.

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

# 3. Dry-run the generated rules against a real config. Creates nothing on the
#    server and needs only the WebDownloader role.
export SWIS_PASSWORD=…
python3 disa_stig_tool.py test U_Cisco_IOS_Router_Y26M07_STIG.zip \
    --host orion.example.com --user admin --config-id <ConfigID>

# 4. Import: creates the report, its policies and rules, and starts compliance caching
python3 disa_stig_tool.py import U_Cisco_IOS_Router_Y26M07_STIG.zip \
    --host orion.example.com --user admin

# and, if it needs undoing: preview, then delete (the name ends in the version suffix)
python3 disa_stig_tool.py remove --name "U_Cisco_IOS_Router_Y26M07_STIG - Cisco_IOS_Router_NDM_STIG_v1" \
    --host orion.example.com --user admin --dry-run
python3 disa_stig_tool.py remove --name "U_Cisco_IOS_Router_Y26M07_STIG - Cisco_IOS_Router_NDM_STIG_v1" \
    --host orion.example.com --user admin --yes
```

`remove` takes the exact report name, suffix included. When no report has that name, the
error lists the reports whose names start with it, so a name given without its `_v1` is
answered with the names it probably meant.

`remove` undoes an import completely without reaching anything another report uses. It
reads the report's tree (`GetPolicyReport` with `exportFlag` true, plus the
`Cirrus.PolicyAssignment` and `Cirrus.PolicyRuleAssignment` link tables), deletes the
report row with `DeletePolicyReports(ids, false)`, then the report's policies with
`DeletePolicies(ids, false)`, then their rules with `DeletePolicyRules(ids)`. A policy
that another report is still assigned to is kept, and so is a rule that a policy not
being deleted still uses; each kept object is printed with the report or policy that
still references it. `deleteChildren` is never sent as true, because that flag reaches
children other reports share. `--dry-run` prints the same plan and deletes nothing, and
the deletion needs `--yes`. Afterwards the tool reads the ids back and reports anything
still present. `--delete-children` is accepted for compatibility and ignored. Earlier
builds of `remove` deleted only the report row and left its policies and rules orphaned;
those orphans have no report left to find them by, and this tool does not search for
them.

### CLI parameters in both editions

| Python (`disa_stig_tool.py <command>`) | PowerShell (`disa_stig_tool.ps1`) | Meaning |
| --- | --- | --- |
| `convert` / `build <path>` | `-Convert -Path <paths>` | Offline conversion to console-importable files |
| `import <path>` | `-Server <host> -Path <paths>` | Import over SWIS |
| `test <path>` | `-Test -Server <host> -Path <paths>` | `TestRule` dry run; creates nothing |
| `remove --name <n>` | `-Remove -Name <n> -Server <host>` | Undo an import (see above) |
| `parse <path>` | none | Summarize a package |
| `download <package>` | none | Fetch a package from DISA's mirror |
| `--name` | `-Name` | Report name base (`<name> - <benchmark id>`) with convert, import and test; the exact report name with remove |
| `--grouping` | `-Grouping` | Folder for reports, policies and rules |
| `--target auto\|network\|server` | `-Target auto\|network\|server` | Module routing for XCCDF input |
| `--node-where` | `-NodeWhere` | NCM node scope (`auto` derives it from the vendor and Cisco platform) |
| `--vendor NAME` | `-Vendor NAME` | The `Vendor` value the nodes report; overrides detection, required for an unrecognized network STIG |
| `--machine-type PATTERN` | `-MachineType PATTERN` | `MachineType LIKE` pattern added to the scope; overrides the Tentative Cisco platform table |
| `--allow-empty-scope` (import) | `-AllowEmptyScope` | Import even when the node scope matches no node |
| `--suffix _vN` | `-Suffix _vN` | Version suffix on every name and id seed (`_v1` by default) |
| `--scm-probe-template FILE` | `-ScmProbeTemplate FILE` | Replace the SCM attestation probe's source block ([Linux testing](#testing-linux-stigs-in-scm)) |
| `--config-type` | `-ConfigType` | Config type the rules scan (`Any`, `Running`, `Startup`, ...) |
| `--mode manual\|heuristic` | `-Mode manual\|heuristic` | Sentinel or drafted patterns |
| `--disabled` | `-ImportDisabled` | `ReportStatus` `Disabled`, no caching; honored by convert too |
| `--no-cache` | `-NoCache` | Import without `StartCaching` |
| `--no-rollback` | `-NoRollback` | Keep what a failed import created |
| `--config-file` / `--config-id` / `--limit` | `-ConfigFile` / `-ConfigId` / `-Limit` | Inputs for `test` |
| `--dry-run` / `--yes` | `-DryRun` / `-Yes` | Preview or confirm `remove` |
| `--host` / `--port` / `--user` | `-Server` / `-Port` / `-Username` (or `-WindowsAuth`) | Connection; the password comes from `SWIS_PASSWORD` or a prompt in both |
| `--pin-server-cert` / `--insecure` / `--ca-file` | `-PinServerCert` / `-Insecure` / none | TLS trust |
| `-o` / `--output` | none | Output file for a single-benchmark convert |
| `--log-file PATH` | `-LogFile PATH` | Where the [run log](#run-log) goes (default below) |
| `--log-level debug\|info\|warn` | `-LogLevel debug\|info\|warn` | Run log detail; `info` by default |

When no `--name` / `-Name` is given, a zip's reports are named `<zip file name> -
<benchmark id>` and a bare `.xml` or a directory's reports take the benchmark title, in
both editions. Every report, NCM policy and SCM policy name then ends in the version
suffix (`<zip file name> - <benchmark id>_v1`), and the files written for them carry it
too. Names are cut to 250 characters, suffix included; the suffix itself is never cut.

`--disabled` imports the report with `ReportStatus` `Disabled` and skips caching, which
is what you want for a 92-rule benchmark that still needs tuning: the report exists and
holds its rules but evaluates nothing until it is switched on. Without it the report
starts evaluating immediately, and the policy cache refreshes on its own at 11:55 PM
daily anyway.

`test` takes either `--config-file <path>` (configuration as text) or `--config-id
<GUID>` (a config NCM already holds — `SELECT ConfigID, NodeID, ConfigType,
DownloadTime FROM NCM.ConfigArchive ORDER BY DownloadTime DESC`), and `--limit` caps how
many rules it evaluates (10 by default, `0` for all). Only the backed-up-config route
expands NCM macros. SolarWinds documents the result as a string without documenting its
shape, so the tool prints it exactly as the server sent it rather than interpreting it.

Add `--pin-server-cert` to trust the server's own `SolarWinds-Orion` certificate for
the session (its SHA-256 fingerprint is printed). `convert`/`build` is the offline
mode described above.

### Node scope (vendor and Cisco platform)

Every generated NCM policy carries a node scope, the `SQL:Where (...)` part of its
`NodeSelectionString`, which is what NCM filters nodes on. Since 2.0.0 (2026-10-09) it is
decided like this, in both editions:

1. `--node-where` / `-NodeWhere` is used exactly as written (combining it with `--vendor`
   or `--machine-type` is refused).
2. Otherwise the vendor is `--vendor`, else the one detected from the file and benchmark
   names. With no vendor at all the STIG is refused, offline `convert` included: a Router
   or NDM SRG, an ESXi STIG or any product the name table does not know no longer
   defaults to `(Vendor = 'Cisco')`.
3. Non-Cisco vendors keep a Vendor-only scope, `(Vendor = 'Juniper')`.
4. For Cisco the platform is read from the package file name plus each benchmark's title
   and source member name, with `-`, `_` and spaces treated alike, so "IOS-XE",
   "IOS_XE", "IOS XE" and "IOSXE" all match. The specific platforms are tried before
   classic IOS:

   | Platform | Matched in the names | Scope added |
   | --- | --- | --- |
   | IOS-XE | `ios xe`, `ios-xe`, `ios_xe`, `iosxe` | `MachineType LIKE '%IOS-XE%'` |
   | IOS-XR | `ios xr`, `ios-xr`, `iosxr` | `MachineType LIKE '%IOS-XR%'` |
   | NX-OS | `nx os`, `nx-os`, `nxos` | `MachineType LIKE '%NX-OS%'` |
   | ASA | `asa` as a word | `MachineType LIKE '%ASA%'` |
   | IOS (classic, only when none of the above match) | `ios` as a word | `MachineType LIKE '%IOS%'` |

   **Tentative: MachineType values to be verified against a live server.** Nothing in
   this repository records what `Orion.Nodes.MachineType` holds for these platforms, and
   `%IOS%` also matches any `MachineType` containing IOS-XE or IOS-XR. The import logs
   the `MachineType` values the vendor's nodes report (up to 25, with counts), which is
   the check. A Cisco STIG whose platform is not recognized (Cisco ISE, for example), or
   a package whose benchmarks name different platforms, is refused rather than scoped to
   every Cisco node; `--machine-type PATTERN` (or `'%'` for every Cisco node that reports
   a `MachineType`) or `--node-where` decides it instead. `--machine-type` also adds the
   condition for any other vendor.

The resulting fragment uses bare column names, as console exports do:
`(Vendor = 'Cisco' AND MachineType LIKE '%IOS-XE%')`. A single quote in `--vendor` or
`--machine-type` is doubled, and the values must be one line of at most 200 printable
characters. **The console node picker stays Vendor-only**: the `WebCriteria:` XML holds
one `Vendor =` criterion (its value XML-escaped) and the `MachineType` condition lives in
the SQL part alone, so the console's picker view of an imported policy does not show the
platform condition, while the filtering does use it. Reopening and saving the policy in
the console may rebuild the SQL from the picker; **Unverified**, check on the target.

Before an import writes anything, the scope is counted on the server, with the same
condition as SWQL: `SELECT COUNT(NodeID) AS N FROM Orion.Nodes WHERE Vendor = @vendor AND
MachineType LIKE @machineType` for a generated scope (bound parameters, never spliced),
or the `--node-where` text itself, `Nodes.` prefix dropped, for an explicit one. Both
forms are logged. A scope that matches no node is refused, because a report scoped to
nothing evaluates nothing and reads like compliance; `--allow-empty-scope` /
`-AllowEmptyScope` imports it anyway. An explicit NCM WHERE clause is not always valid
SWQL; when the count cannot be run, the run log says so and the import goes on.

### Version suffix and the upgrade workflow

Every report name, NCM policy name and SCM policy name ends in a version suffix,
`--suffix` / `-Suffix`, `_v1` by default and always `_v` followed by digits. The same
suffix is part of the uuid5 seed of every generated id: the NCM `PolicyId` and `RuleId`s
(`stig2ncm-policy:<benchmark id><suffix>`, `stig2ncm:<rule id><suffix>`) and the SCM
policy and rule `uniqueId`s. A different suffix therefore produces entirely fresh names
and ids, which nothing on the server shares with the earlier import.

Before anything is written, the import checks every name and id it would create: report
names (`Cirrus.PolicyReports`), policy names and `PolicyId`s (`Cirrus.Policies`),
`RuleId`s (`Cirrus.PolicyRules`), and for SCM the policy name and `uniqueId` and every rule
`uniqueId` (`Orion.PolicyEngine.Policy`, `Orion.PolicyEngine.Rule`). Any hit refuses the
whole run, names what collided, and suggests the next free suffix: one above the highest
`_v<n>` that any existing name with the same base carries. The id lookups are `IN @ids`
queries over GUIDs and are preceded by the same sanity probe as the rest of the tool.
**Unverified:** whether SCM rejects a rule `uniqueId` that another policy uses is not
documented; the tool checks it so that a new suffix really means fresh ids. The
existing-id snapshot that keeps a rollback from deleting earlier objects stays in place
behind this check, as defense in depth; normally it now finds nothing.

To move to a new STIG release:

1. Import the new release next to the old one with the next suffix:
   `import U_Cisco_IOS-XE_Router_Y26M10_STIG.zip --suffix _v2 --disabled ...`
   (`--disabled` keeps it from evaluating until it has been reviewed).
2. Review the `_v2` report in the console, carry over any rule patterns tuned in `_v1`,
   and enable it (`UpdateReportStatus('Enabled', [ids])` or the console).
3. Remove the old import by its full name:
   `remove --name "<zip name> - <benchmark id>_v1" --dry-run`, then `--yes`.
   Because no id is shared, removing `_v1` cannot reach a `_v2` policy or rule.

Imports made before 2.0.0 have no suffix. Their names and ids differ from every suffixed
one, so a `_v1` import goes in beside them; remove them by their old names when ready.

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
| severity high / medium / low | `ErrorLevel` 2 / 1 / 0 (console names critical / warning / info by default; the names are editable per server) |
| VulnDiscussion + check-content + IDs (SV, STIG ID, CCIs) | `Comments` |
| fixtext (the Fix Text) | `RemediateScript`, type CLI, **never auto-executed** |
| one XCCDF Group/Rule (each check) | one NCM rule |
| one benchmark | one policy — the device scope ([node scope](#node-scope-vendor-and-cisco-platform): the vendor, plus the Cisco platform's `MachineType`, or `--node-where`) |
| one benchmark | one report **named `<zip name> - <benchmark>_v1`** (the router zip yields an NDM report with 35 rules and an RTR report with 92), `Enabled`, in the `DISA STIG` folder — a converter packaging choice, not a one-policy limit in the console format |

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
  (`hostname R1`) that must be reviewed per environment. A drafted line containing `*`
  or `?` is emitted as `PatternType` `Regex` over the escaped literal rather than as a
  `Like` pattern, because NCM treats those two characters as wildcards only when the
  server's `ComplianceRulesWildcardsEnabled` advanced setting is on (NCM 2023.1.1 and
  later, off by default) — a `Like` pattern carrying one would otherwise mean different
  things on different servers. The escaping is written out explicitly in both editions
  so they still produce the same bytes.

**Palo Alto and anything else that stores XML.** A policy report cannot be run against
a configuration downloaded in XML format, which is how Palo Alto devices back up unless
the config type is changed. The rules import and cache normally and then report nothing
at all, which reads exactly like compliance, so the tool prints a warning whenever the
node scope selects those devices. Confirm the nodes have a text config of the selected
type, or route the benchmark to SCM.

`RuleId` GUIDs are derived deterministically from the DISA rule ID and the version suffix
(uuid5), so re-importing the same STIG release with the same suffix submits the same rule
identities, and the collision check refuses it. **Unverified:**
whether `AddPolicyRule` keeps a submitted `RuleId` or assigns a fresh one is not
documented; the tool always uses the id the verb returns. Check by importing one
benchmark and comparing `SELECT PolicyRuleID FROM Cirrus.PolicyRules WHERE Name = @n`
with the generated id.

## Current NCM coverage and import limits

The input parser reads XCCDF benchmarks; it is not an importer for an existing
`PolicyReport` XML file. Porter is the repository's reader for that artifact. The current
XCCDF model omits profile selection and retains only the first direct Rule per Group.
OVAL references are recorded, not evaluated. A generated sentinel or heuristic is not
an implemented automated STIG assessment.

Before extending the tool to richer rules, fix the XML fallback serializers, preserve
advanced conditions in both editions, and compare exact imported relationships and
content. Since 2.0.0 (2026-10-09) the read-back compares the stored tree with what was
submitted, as Porter 0.3.0 does: the policy count, the rule count, and the rule names in
each policy (matched by policy name). A mismatch, or a `GetPolicyReport` result that is
not a report object, is a failed import and is rolled back. Rule content (patterns,
severity, remediation fields) is not compared yet, and no live import has exercised
this; the behavior is covered by offline tests against an in-memory stand-in.
See the [evidence and acceptance tests](../../docs/modules/ncm-compliance-portability-audit.md)
for scope/config dependencies, version tracking, and the proposed import journal.

## Server STIGs into SCM (the Server Compliance route)

A server-OS XCCDF (manual or SCAP) is converted into an SCM compliance policy —
one `!policy` YAML per benchmark — and imported through `ImportPolicy`. Manual STIGs
carry no machine checks, so every generated rule is a **manual-review attestation**:
its condition is a harmless `Write-Host` probe (a single-quoted literal; see
[Security rules](#security-rules)) that always reports failed, keeping
the rule an open action item carrying the STIG's check and fix text until an engineer
verifies the setting and replaces or disables the rule. Nothing in a generated policy
changes server configuration. SCM policies carry no node scope in the file —
assignment is per node after import — so the tool prints the `Orion.Nodes` query
(by `MachineType` for the detected OS) that lists the nodes to assign.

The probe comes from a per-OS table. Windows STIGs (Windows, SQL Server, IIS, Exchange)
get the `!scm.powershell` attestation, the source type SolarWinds' own shipped STIG
policies use. Linux STIGs (Linux, RHEL, Debian, Ubuntu, CentOS) stay routed to SCM and,
for now, get the same probe, which is **Unverified** on Linux nodes (next section). A
benchmark forced to SCM with no recognized OS gets the Windows probe, with a warning. The
run log records the OS family detected and the probe used, and a Linux STIG adds a
warning that points here. `--scm-probe-template FILE` / `-ScmProbeTemplate FILE` replaces
the probe's source block for one run, so another source type can be tried without
changing code.

### Testing Linux STIGs in SCM

**Unverified:** this repository documents no SCM policy source for Linux nodes, and
SolarWinds' SCM documentation is understood to treat script data sources on Linux as
unsupported, so a generated Linux policy may report its rules as an error or Unknown
rather than failed. Before relying on one:

1. Convert or import one Linux benchmark and assign the policy to **one** test node
   (Settings → SCM Settings → Policies).
2. Run `PollNowAndEvaluate(policyId, entityUri)` for that node, then read
   `Orion.PolicyEngine.AssignedRule.Status` for its rules: `2` failed is the intended
   manual-review state; `0` unknown, or rows in `Orion.PolicyEngine.AssignedRuleError`,
   mean the source did not collect on Linux.
3. Read `Orion.PolicyEngine.Rule.ConditionYAML` for one rule to confirm what was stored.
4. If the default probe does not collect, write a source block for a type your SCM
   supports on Linux and pass it with `--scm-probe-template`. The file is a YAML
   fragment: the source tag on its first line, then that source's `key: value` lines,
   nested by spaces:

   ```yaml
   !scm.powershell
   description: "STIG {id} manual-review attestation"
   script: "Write-Host '{id} reviewed: False'"
   ```

   `{id}` becomes the vulnerability id after the same validation the default probe uses
   (`V-<digits>`, otherwise reduced to `[A-Za-z0-9._-]` with a warning), never raw STIG
   text, and it is accepted only inside a quoted value (`"..."` or `'...'`), where those
   characters cannot end the string or change the quoting of a script inside it. The
   template is refused, before anything is written, when it does not start with an
   `!scm.<type>` tag, uses `{id}` in a key or an unquoted value, puts a backslash right
   before `{id}`, contains sequences, anchors, block scalars, flow collections or tabs,
   is indented inconsistently, or is larger than 4 KB. The rule's condition stays
   `!matches` with the expression `<id> reviewed: True`, so the collected value must
   never contain that text for the rule to stay an open item.
5. Repeat step 2 with the new policy (use the next `--suffix`, since the first policy's
   names and ids already exist).

## SCM policies (Server Configuration Monitor)

SCM compliance policies are YAML documents tagged `!policy` with `pluginName: SCM`,
whose rules carry the actual machine checks (`!scm.registry`, `!scm.powershell` sources
with `!equals`/`!matches` conditions). The import needs no translation at all: the SWIS
verb `Orion.PolicyEngine.Policy.ImportPolicy(yaml)` takes the file text verbatim and
returns the new PolicyID. The tool refuses to import when a policy with the same name
**or** the same `uniqueId` already exists, then leaves assignment to you: Settings → SCM
Settings → Policies (or the `AssignToEntity` verb). Preview parses nothing server-side —
it just scans the YAML for the policy name, rule ids and severities. The
[SCM export audit](../../docs/modules/scm-policy-portability-audit.md) documents
additional database sources, numeric comparisons, status translations, dependencies,
and optional fields. Current preview is regex-based. Both editions check `Name` and
`UniqueId` before importing (the PowerShell edition normalizes CRLF line endings first,
so a Windows-edited file is checked too) and read the rule count back afterwards; that
read-back rejects a policy holding no rules, which also catches a returned id of 0, but
it does not compare the count or the content with the file. A ZIP containing policy
YAML is not accepted by the XCCDF package reader.

## Run log

Every run, CLI or GUI, in either edition, writes a log file in addition to its console
output, and prints the file's path when it starts and when it ends (the Python CLI
prints it on stderr so stdout is unchanged). Both editions write the same line format,
one event per line:

```text
2026-10-09T14:03:07.123Z INFO  swis   Cirrus.PolicyReports.AddPolicyRule(<object V-215662 [medium] ...>) -> ok 41 ms, "6f1c..."
```

That is the UTC time with milliseconds, the level padded to five characters (`DEBUG`,
`INFO`, `WARN`, `ERROR`), the component padded to six, and the message; a line break
inside a message is written as a literal `\n`. The components are `main`, `parse`,
`route`, `scope`, `build`, `swis`, `import`, `verify`, `rollbk`, `remove`, `scm`,
`file` and `gui`.

| Default location | |
| --- | --- |
| Windows | `%LOCALAPPDATA%\DisaStigTool\logs\disa-stig-tool_<yyyyMMdd-HHmmss>.log` |
| Elsewhere | `~/.local/state/disa-stig-tool/logs/disa-stig-tool_<yyyyMMdd-HHmmss>.log` (or under `$XDG_STATE_HOME`) |

The time stamp in the file name is UTC. `--log-file` / `-LogFile` writes somewhere else
instead; when the default folder cannot be created the log falls back to the temp
directory. What a run records at `info`:

- the tool version, the interpreter and OS, and the full command line;
- each input file and zip member considered, and whether it was parsed or skipped and
  why (not XML, not XCCDF, a refused DTD, malformed XML);
- each benchmark found (id, title, version, release, edition, rule count) and every
  dedupe decision;
- the routing decision and the keyword that drove it, and the node scope and where it
  came from: the Cisco platform per benchmark (Tentative), the NCM SQL and SWQL forms of
  the scope preflight, the node count, and the `MachineType` values the vendor's nodes
  report;
- the version suffix of each report, the collision check (what collided, the names that
  share the base, the next free suffix), and for SCM the OS family, the probe or probe
  template used, and a warning for Linux;
- each report or SCM policy built, every file written, and SCM probe ids that had to be
  sanitized (as warnings);
- every SWIS call: `entity.verb` or the query, a short argument summary, the duration,
  and `ok` or the error message, plus the endpoint, the user name and the TLS mode of the
  connection (never the password);
- import, verification, rollback and removal decisions, including the wire-format
  classification of every rejection, the permission preflight and the role each verb
  needs, each `IN @ids` sanity probe, `StartCaching`'s result, and the transport and
  certificate check a connection uses;
- an end-of-run summary: exit code, SWIS calls and failures, files written, verified
  imports, warnings and errors.

`debug` adds the request and response body of every SWIS call, redacted and cut to
4 KB. `warn` keeps only warnings and errors. Every line passes through the same secret
redaction as the console, and the `SWIS_PASSWORD` value is registered before the first
line is written, so it is masked even in the logged command line.

## Security rules

- **TLS verification is on by default** (GUI checkbox and CLI alike; `--insecure` is a
  deliberate lab-only override). Three ways to make the stock self-signed
  `SolarWinds-Orion` certificate verifiable: the GUI's **Trust server certificate…**
  button / CLI `--pin-server-cert` (fetch once, show the SHA-256 fingerprint, verify
  every call in the session against exactly that certificate — the hostname check is
  waived only for the pinned certificate, whose CN is `SolarWinds-Orion`, never in
  general), `--ca-file` with an exported copy, or binding a domain-trusted certificate
  to SWIS.
- **A pinned certificate is enforced on every connection and fails closed** (since
  2.0.0, 2026-10-09). The Python edition trusts only the pinned certificate. Windows
  PowerShell 5.1 sets the process-wide `ServicePointManager` callback only for the
  duration of each call and puts the previous one back afterwards. PowerShell 7's
  `Invoke-RestMethod` has no server-certificate callback (`-CertificateThumbprint`
  selects a *client* certificate), so a pinned connection there goes through a
  `System.Net.Http.HttpClient` whose handler compares the SHA-256 of the presented
  certificate with the pin; `-SkipCertificateCheck` is used only for `-Insecure`
  without a pin, and `-Insecure` is ignored when a certificate is pinned. The check is
  a small C# class compiled with `Add-Type` (a script block cannot run as a TLS
  callback where no runspace exists); if it cannot be compiled, the tool refuses to
  connect. A mismatch names both fingerprints. The PowerShell 7 path is exercised in
  the offline tests by forcing it on Windows PowerShell 5.1 against a local TLS
  listener; it has not been run under PowerShell 7 itself.
- **Request bodies are UTF-8.** The PowerShell edition sends the JSON as UTF-8 bytes
  with `Content-Type: application/json; charset=utf-8`; Windows PowerShell 5.1 would
  otherwise encode a string body as ISO-8859-1 and mangle STIG text outside Latin-1.
- **Credentials live in memory only.** Nothing is written to disk, credentials never
  appear in URLs, and the CLI takes the password from `SWIS_PASSWORD` or an interactive
  prompt — never a command-line argument.
- **Passwords are always redacted** from everything the tool prints or logs, including
  server error messages that might echo them.
- **XML is read without DTDs.** A STIG file that declares a `<!DOCTYPE>` is refused,
  with the reason in the run log, so external entities (XXE) and entity expansion are
  never processed. The PowerShell edition loads XML through an `XmlReader` with
  `DtdProcessing=Prohibit` and no resolver, reading the bytes so the BOM and the
  declared encoding are honoured (a `windows-1252` file decodes as `windows-1252`); the
  Python edition refuses any DTD before parsing. XCCDF does not use DTDs.
- **STIG text never becomes script source.** The SCM probe is
  `Write-Host '<vuln id> reviewed: False'`, a single-quoted PowerShell literal in which
  `'` (and the typographic single quotes PowerShell also honours) is doubled, so
  `$(...)`, `$var`, backticks and double quotes stay inert. The vuln id must match
  `V-<digits>` (rule ids `SV-<digits>r<digits>_rule`) after any SCAP `xccdf_` prefix is
  stripped; anything else is reduced to `[A-Za-z0-9._-]` with a warning in the log. A
  `--scm-probe-template` receives the same validated id, and only inside a quoted value.
- **Scope values are quoted, and the scope is counted with bound parameters.** A single
  quote in `--vendor` or `--machine-type` is doubled in the NCM WHERE fragment, the
  picker's vendor value is XML-escaped, and the SWQL node count binds the values as
  `@vendor` / `@machineType` rather than splicing them in.
- **Generated file names are sanitized in one place.** Report, policy and download file
  names keep `[A-Za-z0-9._-]`, every other run of characters becomes `_`, leading dots
  are stripped, Windows device names (`CON`, `NUL`, ...) are prefixed, and the whole name
  is capped at 200 characters, so a title can neither leave the output folder
  (`../../x`) nor exceed the 255-character file name limit.
- **"No Data Returned" is said plainly.** Every import is verified by reading the
  result back; an empty read-back is reported as *No data returned from &lt;call&gt;*,
  never as success.
- **The account's rights are checked before anything is written.** An NCM import (and
  `remove`) first logs the role each verb needs and calls `GetPolicyReport` for the nil
  GUID. HTTP 401, 403 or a permission message stops the run with the role it needs;
  any other answer is logged as inconclusive and the run continues (**Unverified:** how
  a server answers `GetPolicyReport` for an id that does not exist is not documented).
- **SCM configuration text stays on the server.** The tool never reads
  `Orion.SCM.Results.ElementContents` (collected file/config content) or any other
  config-bearing API — the only SCM data it touches is policy metadata. Any future
  feature that would retrieve configuration content will be an explicit
  `includeConfigText`-style opt-in, defaulting to hashes and metadata.

## Safety posture

- `ExecuteScriptAutomatically` is always false. A downloaded checklist must never be
  allowed to push configuration to devices on its own — remediation scripts are stored
  for an operator to review and run per node from the console. The same caution applies
  in reverse to SCM YAML: its `!scm.powershell` scripts run on every assigned node, so
  read them before importing a file from outside the organisation.
- The importer never updates or deletes an existing report: a collision on any name or
  id the run would create is an error, not a merge, and it is caught before the first
  write, with the next free suffix suggested
  ([details](#version-suffix-and-the-upgrade-workflow)). `remove --name … --yes` deletes
  one the tool imported together with its policies and rules, except any policy or rule
  another report or policy still uses ([details](#the-cli)).
- **A report scoped to no node is not imported** unless `--allow-empty-scope` says so,
  and a network STIG whose vendor (or Cisco platform) cannot be told from its names is
  not converted at all until `--vendor`, `--machine-type` or `--node-where` decides it
  ([node scope](#node-scope-vendor-and-cisco-platform)).
- **A failed import cleans up after itself, and only after itself.** The NCM tiers are
  created bottom-up, so a failure at the policy or report step would otherwise leave
  every rule already created sitting in the rules library with nothing pointing at it:
  invisible in the Compliance view, deleted by nothing, and duplicated by the next
  attempt. The ids are tracked as they come back and deleted in reverse on failure.
  Before creating anything, the tool records which of the `RuleId`s and `PolicyId`s it is
  about to submit already exist (`Cirrus.PolicyRules`, `Cirrus.Policies`), because the
  deterministic rule ids make an earlier import of the same STIG release share them, and
  a verb that returns no id falls back to the submitted one. The rollback skips those
  and prints each one it skipped. Since the 2.0.0 collision check refuses a run whose ids
  already exist, this snapshot is now defense in depth and normally empty. `--no-rollback`
  keeps everything for diagnosis.
- **A multi-report run keeps what it finished.** A package with several benchmarks
  imports one report at a time. When a later report fails, the reports already imported
  and verified stay on the server, are reported as imported, and still get caching
  started (or `UpdateReportStatus('Disabled')` and its read-back with `--disabled`,
  nothing with `--no-cache`). Only the failed report is rolled back. When no wire format
  is accepted, console-importable files are written for the reports that were not
  imported, not for the ones that were.
- **Since 2.0.0 (2026-10-09), every failure is handled the same way.** In both editions
  a timeout, a reset connection, a TLS failure or a body that is not JSON is reported
  as a SWIS error carrying the original type and message, and any exception during an
  import (not only an HTTP error) is logged, rolled back and recorded as that report's
  failure. A rollback step that fails is logged and the next level is still deleted.
  A call that failed without an HTTP status may still have run on the server, so the
  tool names the id it submitted for checking.
- **Only the documented rejections mean "try another wire format".** An HTTP 400 whose
  message is one of the two rejections
  [ncm-compliance-reports.md](../../docs/modules/ncm-compliance-reports.md#the-swis-round-trip-20262-verified)
  records ("Value cannot be null. Parameter name: input", "... cannot unpackage
  parameter 0") moves on to the next format. Any other 400, and every 401, 403, 409 or
  500, stops that report with the server's message, rolls back, and writes no console
  file, because the problem is not the wire format.
- **The nested fallback cleans up too.** If the one-call nested `AddPolicyReport` is
  accepted but the read-back does not match, the report it created is deleted (the
  report row, then the policies and rules nothing else uses, never an id that existed
  before the run) before the console file is written.
- **`IN @ids` is checked before anything is decided with it.** The existing-id snapshot,
  the removal plan and the nested rollback all read sets of GUIDs with `IN @ids`.
  **Unverified:** the documented array binding uses integers, and whether every server
  binds an array of GUID strings the same way is not documented; a server that matched
  nothing would make the snapshot say "nothing existed before". So the same query is
  first run for one id known to exist, and anything other than exactly one row stops
  the run with nothing deleted.
- **A refused `StartCaching` or `UpdateReportStatus` does not stop the run.** Both need
  WebUploader, one step above what the import needs. The refusal is logged with that
  role, the console files still due are written, and the command exits non-zero
  because the requested end state was not confirmed. `StartCaching`'s boolean result is
  logged; `false` is reported (**Unverified:** what `false` means is not documented).
- **The SCM collision check covers the uniqueId too**, not just the name. SolarWinds
  rejects an import matching either, and the tool derives the uniqueId deterministically
  from the benchmark, so a re-import under a new `--name` still collides. Checking
  locally turns an opaque server error into a legible one.
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

## The SWIS calls executed on import

| Route | Calls, in order |
| --- | --- |
| NCM (network STIGs) | Permission preflight `GetPolicyReport(<nil GUID>, false)` → scope preflight: node count on `Orion.Nodes` and a `Vendor, MachineType` sample → collision check, for every report before any write: report name on `Cirrus.PolicyReports`, policy name on `Cirrus.Policies`, and the `IN @ids` probe plus `PolicyId`/`RuleId` lookups (on a hit, `Name LIKE` listings for the next free suffix) → per report: `IN @ids` sanity probe on one existing rule and policy (`SELECT TOP 1 …`), existing-id snapshot on `Cirrus.PolicyRules` / `Cirrus.Policies`, wire-format probe with one `AddPolicyRule(rule)`, `AddPolicyRule` per check, `AddPolicy(policy, importFlag)` with the rule-ID list, `AddPolicyReport(report, importFlag)` with the policy-ID list, `GetPolicyReport(reportId, exportFlag)` read-back verification → after the last report, or at the first failure, one `StartCaching([ids])` for every report that was imported, or `UpdateReportStatus('Disabled', [ids])` plus a `ReportStatus` read-back with `--disabled`. A failure within one report triggers `DeletePolicyReports` / `DeletePolicies` / `DeletePolicyRules` for what that report's attempt created, skipping ids that existed beforehand |
| NCM rule dry run (`test`) | Wire-format probe against `TestRule` → `TestRule(rule, configText)` or `TestRuleOnBackedUpConfig(rule, configId)` per rule. Read-only; nothing is created |
| NCM fallback | Only after documented 400 rejections: nested `AddPolicyReport(report, importFlag)` in console-export XML, verified with `GetPolicyReport`; a nested report that fails verification is removed the way `remove` does it (after the `IN @ids` probe), skipping ids that existed before. If every wire format is refused, console-importable `.ncm-report.xml` files are written for the reports not yet imported |
| NCM undo (`remove`) | Name query on `Cirrus.PolicyReports` → permission preflight (not on `--dry-run`) → `IN @ids` sanity probe on the report → `GetPolicyReport(reportId, exportFlag)` per report → membership and sharing queries on `Cirrus.PolicyAssignment` and `Cirrus.PolicyRuleAssignment` → `DeletePolicyReports(ids, false)` → `DeletePolicies(unsharedIds, false)` → `DeletePolicyRules(unsharedIds)` → read-back of all three |
| SCM (server STIGs / `.yaml` / `.scm-policy.yaml` / legacy policy `.scm-profile`) | For converted STIGs, before any import: `Name`/`UniqueId` query per policy and, after the `IN @ids` probe, a rule `UniqueId` lookup on `Orion.PolicyEngine.Rule` → per policy: collision check query on `Orion.PolicyEngine.Policy` by `Name` **and** `UniqueId` → `ImportPolicy(yaml)` → rule-count read-back on `Orion.PolicyEngine.Rule` |
| NCM undo by a name that does not exist | `Name LIKE` listing on `Cirrus.PolicyReports` to name the reports that start with it (usually the same name with its suffix) |
| Test connection | `Orion.Engines` version query + `Metadata.Entity` counts for the `Cirrus.` and `Orion.PolicyEngine.` namespaces |

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

Required rights, from the 2026.2 verb descriptions: `AddPolicyRule`, `AddPolicy`,
`AddPolicyReport`, `GetPolicyReport`, the three `Delete*` verbs and the two `TestRule`
verbs need at least the NCM **WebDownloader** role; `StartCaching` and
`UpdateReportStatus` need **WebUploader**. When the server's "compliance only for
administrators" option is on, all of them are valid only for Orion administrators.
(Before 2.0.0 this README and the tool's verification error said WebUploader was the
minimum for an import, which was wrong.) SCM policy import/assignment requires the **manageNodes**
right on `Orion.PolicyEngine.Policy`.

## NCM: entities and verbs used

The `Cirrus.Policy*` SWQL entities are read-only; all writes are Invoke verbs on
`Cirrus.PolicyReports`.

| Call | Signature (positional) | Used for |
| --- | --- | --- |
| Query | `SELECT PolicyReportID FROM Cirrus.PolicyReports WHERE Name = @n` | Collision check before import |
| Query | `SELECT PolicyID, Name FROM Cirrus.Policies WHERE Name = @n` | Collision check on the policy name |
| Query | `SELECT TOP 200 Name FROM Cirrus.PolicyReports WHERE Name LIKE @p` (and the same on `Cirrus.Policies`) | After a collision: the names sharing the base, for the next free suffix |
| Query | `SELECT COUNT(NodeID) AS N FROM Orion.Nodes WHERE Vendor = @vendor AND MachineType LIKE @machineType` | Scope preflight (without the `MachineType` condition for a Vendor-only scope) |
| Query | `SELECT TOP 25 Vendor, MachineType, COUNT(NodeID) AS N FROM Orion.Nodes WHERE Vendor = @vendor GROUP BY Vendor, MachineType ORDER BY MachineType` | Logs the `MachineType` values the vendor's nodes report, to check the Tentative platform table |
| `AddPolicyRule` | `(rule)` → new rule GUID (string) | One call per STIG check — the rules are created first |
| `AddPolicy` | `(policy, importFlag)` → new policy GUID (string) | One per benchmark, with `importFlag=false` and `AssignedRulesList` carrying the rule GUIDs just created |
| `AddPolicyReport` | `(report, importFlag)` → new report GUID (string) | Last, with `importFlag=false` and `AssignedPoliciesList` carrying the policy GUIDs |
| `GetPolicyReport` | `(reportId, exportFlag)` with `exportFlag=true` | Read-back verification: the import only reports success once the returned tree has the submitted policy count, rule count and rule names per policy. Also the permission preflight, for the nil GUID with `exportFlag=false` |
| `StartCaching` | `(selectedReportsIds)` — array of GUID strings → boolean | Activation; **always pass the specific GUID** — an empty array re-caches every report on the server. The result is logged |
| `UpdateReportStatus` | `(status, selectedReportsIds)` — `Enabled`/`Disabled` | `--disabled`: the verb that owns the field, said explicitly rather than trusting the payload to have carried it |
| `TestRule` / `TestRuleOnBackedUpConfig` | `(policyRule, config)` / `(policyRule, configId)` → string | The `test` command. Creates nothing, needs only WebDownloader, and takes the same contract type `AddPolicyRule` does, so the same wire-format probe applies |
| `DeletePolicyRules` / `DeletePolicies` / `DeletePolicyReports` | `(ruleIds)` / `(policyIds, deleteChildren)` / `(policyReportIds, deleteChildren)` | Rollback of a failed import, and the `remove` command; `deleteChildren` is always false |
| Query | `SELECT PolicyReportID, PolicyID FROM Cirrus.PolicyAssignment WHERE PolicyID IN @ids` | `remove`: a policy another report is assigned to is kept |
| Query | `SELECT PolicyID, PolicyRuleID FROM Cirrus.PolicyRuleAssignment WHERE PolicyRuleID IN @ids` | `remove`: a rule a surviving policy uses is kept |
| Query | `SELECT PolicyRuleID FROM Cirrus.PolicyRules WHERE PolicyRuleID IN @ids` | Pre-import snapshot so a rollback skips rules that already existed |
| Query | `SELECT TOP 1 PolicyRuleID FROM Cirrus.PolicyRules` / `SELECT TOP 1 PolicyID FROM Cirrus.Policies` | An id known to exist, for the `IN @ids` sanity probe before the snapshot (the report itself is the probe id for `remove` and the nested rollback) |
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
as above), and `NodeSelectionString`. The tool writes it in the shape its code records
from 2026.2.2 console exports: the literal prefix `WebCriteria:`, the console
node-picker's `ArrayOfWebSelectionCriteria` XML (Vendor only, see
[node scope](#node-scope-vendor-and-cisco-platform)), then `SQL:Where ( … )`, the clause
that actually filters nodes, e.g.
`SQL:Where (Vendor = 'Cisco' AND MachineType LIKE '%IOS-XE%')`.

**PolicyRule** (`…Compliance.PolicyRule`), all 21 members:

| Field | Type | The tool sets |
| --- | --- | --- |
| `RuleId` | string GUID | uuid5 of the DISA rule id and the version suffix (stable across re-imports with the same suffix) |
| `RuleName`, `Comments`, `Grouping`, `Owner` | string | Name ≤250 chars; comments carry discussion + check text + CCIs |
| `SimplePatternText` | string | Sentinel or heuristic pattern |
| `PatternType` | string | `Like`, or `Regex` when a heuristic pattern carries `*` or `?` (see above). Regular expressions are evaluated by the .NET engine, and NCM reports the first line of a multi-line match as the violation |
| `PatternMustExist` | boolean | `true` = violation when the pattern is missing |
| `AdvancedMode` | boolean | `false` — simple pattern, not `MultiLineRulePatterns` |
| `MultiLineRulePatterns` | array | Empty; the contract's ten members are `{Pattern, PatternType, IsRegEx, Condition, Criteria, BeginBracket, EndBracket}` plus `RuleId`, `PatternId` and `FoundMatch`, which the server fills in. `Condition` is the `AND`/`OR` joining a pattern to the previous one and the brackets are the grouping parentheses |
| `ConfigBlockStart` / `ConfigBlockEnd` / `ConfigBlockPatternType` / `ConfigBlockMustExist` / `IsConfigBlockPatternRegEx` | string/boolean | Unused (`""` / `Like` / `false`) — restricts matching to a config stanza |
| `ErrorLevel` | number | `0` info, `1` warning, `2` critical. The console's *names* for these are editable per server (NCM Settings → Compliance Policy Report Management → Manage Violation Levels), so the words this tool prints may not match what an operator sees |
| `RemediateScript` | string | The STIG Fix Text |
| `RemediateScriptType` | string | `CLI` |
| `ExecuteScriptAutomatically` | boolean | **Always `false`** — `true` pushes remediation to failing devices on its own |
| `ExecuteRemediationScriptPerBlock`, `ExecuteScriptInConfigMode` | boolean | `false` |

## SCM: entities and verbs used

SCM compliance rides the policy engine namespace, `Orion.PolicyEngine.` (12 entities).
All verbs live on `Orion.PolicyEngine.Policy`; positional JSON bodies.

| Call | Signature (positional) | Used for |
| --- | --- | --- |
| Query | `SELECT PolicyID, Name, UniqueId, BuiltIn FROM Orion.PolicyEngine.Policy WHERE Name = @n OR UniqueId = @u` | Collision check — `ImportPolicy` always creates, and SolarWinds rejects a match on **either** field |
| Query | `SELECT UniqueId FROM Orion.PolicyEngine.Rule WHERE UniqueId IN @ids` (after `SELECT TOP 1 UniqueId FROM Orion.PolicyEngine.Rule` for the probe) | Converted STIGs: no rule `uniqueId` this run would create may exist already |
| Query | `SELECT TOP 200 Name FROM Orion.PolicyEngine.Policy WHERE Name LIKE @p` | After a collision: the names sharing the base, for the next free suffix |
| `ImportPolicy` | `(yaml)` → new `PolicyID` (number) | The import; the argument is the `!policy` YAML document text **verbatim** |
| `ExportPolicy` | `(policyId)` → YAML string | Round-trip/export |
| `AssignToEntity` | `(policyId, entityUri, data)` | Assignment; the URI must be a Node for SCM policies (`swis://…/Orion/Orion.Nodes/NodeID=42`) |
| `PollNowAndEvaluate` | `(policyId, entityUri)` | Collect and evaluate every rule against that node now |
| `UnassignFromEntity` | `(policyId, entityUri)` | Removal |

The tool imports and stops there; assignment and evaluation are console (or
`AssignToEntity`) steps, because which nodes a STIG applies to is an operator decision.

The tool checks both `Name` and `UniqueId` before importing, then reads the rule count
back from `Orion.PolicyEngine.Rule`, because `ImportPolicy` returning an id is not by
itself evidence that the rules landed.

Useful readback entities: `Orion.PolicyEngine.Rule` holds each rule's `DisplayId`
(the `V-…` number), `Severity` (`100` low / `200` medium / `300` high — the YAML's
`Low`/`Medium`/`High` words), check/remediation text, and the condition **as YAML text**
in `ConditionYAML`/`PreconditionYAML`. `Orion.PolicyEngine.AssignedRule.Status` is
`0` unknown, `1` passed, `2` failed, `3` disabled. `Orion.PolicyEngine.PolicyCompliance`
is the per-policy rollup for alerting and reporting.

An assigned SCM policy is evaluated once a day and on demand
(`PollNowAndEvaluate`). For the manual-review rules this tool generates, the end state
of a check an engineer has verified by hand is a rule **disabled with a reason**
(`Enabled` plus `DisableReason`) rather than one that reports failed forever — and
disabling is global, never per node.

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

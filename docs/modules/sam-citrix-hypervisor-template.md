# A SAM template for Citrix Hypervisor (XenServer)

SolarWinds does not ship an AppInsight application for Citrix Hypervisor (formerly XenServer,
and the commercial counterpart of XCP-ng), but a real, community-sourced template for it exists
on SolarWinds' Content Exchange: a 63-component `.apmtemplate` covering host and VM performance
counters, built entirely from `LinuxScript` components running the `xe` CLI over SSH. A copy of
that template was supplied during this repository's own work on the subject and is the ground
truth this page and [scripts/sam-templates/citrix-hypervisor-monitoring.apmtemplate](../../scripts/sam-templates/citrix-hypervisor-monitoring.apmtemplate)
are now built against.

This page documents that reference template's structure, the smaller complementary template
this repository ships (pool-wide inventory facts the reference template does not cover), and
says plainly which parts of the shipped file are verified against the reference and which parts
are still this repository's own construction and need confirming on a real host before you rely
on them.

Read [sam-templates.md](sam-templates.md) first if you have not: it documents the `.apmtemplate`
XML shape in general, and now records this Citrix template as a fourth real sample that
disagrees with the first three on element order and on the `Settings` namespace. [sam.md](sam.md)
covers the SAM entities and verbs a template becomes once imported and assigned.

## Supported versions

**The reference template documents one version: Citrix Hypervisor 8.0.** Its own `Description`
states "Prerequisites: Hypervisor 8.0" in as many words, and its `Tags` list includes `8.0`
alongside `Citrix` and `Hypervisor`. (A fourth tag, `New in 2020.2`, names the SolarWinds SAM
release the template shipped in, not a Citrix version — do not read it as a second supported
version.) Nothing else in that file names any other version, and nothing in it claims broader
compatibility.

That is a documented prerequisite, not a tested compatibility matrix, and the two are worth
telling apart:

- **No other version is confirmed working, and none is confirmed broken.** The `xe` commands and
  RRD data source names both templates use (`cpu_avg`, `memory_free_kib`, `memory_total_kib`,
  `pif_<interface>_rx`/`_tx`, `vm-list`, `pool-list`, `sr-param-get`, `snapshot-list`, `vdi-list`,
  `vbd-list`) have been stable across Citrix Hypervisor and XenServer releases for years, which
  makes it likely that both templates work on adjacent versions (XenServer 7.x, Citrix Hypervisor
  8.1/8.2) and on XCP-ng, which tracks the same `xe` CLI. That is an inference from Citrix's own
  CLI stability, not a claim either template or SolarWinds makes.
- **This repository's own complementary template inherits the same exposure without adding to
  it.** Its host-level components copy their data source names directly from the reference
  template (see "`xe` commands and data source names" above), so they carry the same 8.0
  prerequisite by construction. Its pool-level components use commands checked against Citrix's
  general `xe` CLI reference rather than pinned to any one release, which is a wider net than a
  documented guarantee.
- **The one way to know for a version other than 8.0** is the same answer this page gives
  everywhere else: run `StartTestComponents` against a real host on the version you actually
  run. A data source or `xe` subcommand that exists in 8.0 is not guaranteed to exist, or to be
  named the same way, on a version Citrix has not tested this against.

## What a fourth real export corrected

An earlier version of both this template and this page assumed several things about SAM script
components that turned out to be wrong once a real, working Citrix Hypervisor export was
available to check them against. Recording the corrections here, because getting something
wrong quietly and then fixing it silently would defeat the purpose of a repository whose value
is that its claims are checkable:

- **The script output contract is `Statistic.<Name> : <value>`, one line per named column, not
  a numbered `Statistic1`/`Message1`..`Statistic10`/`Message10` slot scheme.** An earlier
  revision of this template used the numbered-slot form on a practitioner's description of SAM
  script monitors in general; the real Citrix export never uses that form anywhere across its
  63 components. What it uses instead, on every component, is exactly one `echo` line whose
  text is `Statistic.` followed by the `Name` of a `DynamicEvidenceColumnSchema` entry declared
  in that component's own `DynamicColumnSettings`, then ` : `, then the value. See
  [sam-templates.md](sam-templates.md#dynamic-script-columns-dynamiccolumnsettings-and-the-statisticname-output-contract)
  for the full structure. **One component reports one named value this way in every sample
  seen**; whether a single script run can emit several `Statistic.<Name>` lines for several
  columns on one component is structurally plausible (the schema is a list) but not exercised
  by this reference, so this repository's own components stay one metric per component to match
  what is actually proven.
  **Answered since:** the MongoDB 5.0+ (Linux) v2 template re-exported from a 2026.4 server on
  2026-09-17 emits up to eight named pairs from one `LinuxScript` component, each name with a
  `String` and a `Numeric` column. One metric per component is a choice, not a limit; see
  [sam-templates.md](sam-templates.md#dynamic-script-columns-dynamiccolumnsettings-and-the-statisticname-output-contract).
- **`LinuxScript` does not use an `ExecutionMode` setting**, and does not use `ScriptArguments`
  either. It uses `AuthenticationType` (`UsernamePassword`), `Port` (`22`), `ScriptDirectory`
  (`/tmp`), `CommandLineToPass` (see below), `CountAsDifference` (`false`), and
  `StatusRollupType` (`Worst`), none of which an earlier version of this template's components
  carried.
- **A `LinuxScript` component's arguments are supplied by a `CommandLineToPass` value with
  angle-bracket placeholders**, not by the platform substituting `${USER}`/`${PASSWORD}`/`${IP}`
  macros into the script body. See "The `CommandLineToPass` argument-prompt mechanism" below.
- **The `.apmtemplate` root's element order and the `Settings` map's XML namespace differ from
  what the first three samples behind `sam-templates.md` established**, and this template's own
  file now follows the Citrix export's order and namespace rather than the earlier three-sample
  convention, on the reasoning that matching a real, working file beats matching an inferred
  table. See [sam-templates.md](sam-templates.md#a-fourth-sample-disagrees-with-the-table-above-and-is-worth-recording-rather-than-resolving)
  for the specifics.

## Two templates, not one

Rather than try to reproduce the reference template's 63 components, this repository ships a
**smaller, complementary** template:
[citrix-hypervisor-monitoring.apmtemplate](../../scripts/sam-templates/citrix-hypervisor-monitoring.apmtemplate),
16 components covering pool-wide inventory facts the reference template does not: VM
power-state counts, default storage repository capacity, snapshot age and count, and orphaned
virtual disk detection, plus a handful of single-value host metrics (CPU, memory, one named
physical interface, uptime, enabled/live status) built the same way the reference template's own
components are. Import both if you want the full picture: the reference template for detailed
per-host and per-VM performance counters, this one for pool-level inventory.

| Component | Type | Inputs prompted at assignment | Reports (`Statistic.<Name>`) |
| --- | --- | --- | --- |
| Host - CPU Utilization | `LinuxScript` | XenServerHostname | `Host_CPU_Utilization` — CPU (%) |
| Host - Free Memory | `LinuxScript` | XenServerHostname | `Host_FreeMemoryMB` — free memory (MB) |
| Host - Total Memory | `LinuxScript` | XenServerHostname | `Host_TotalMemoryMB` — installed memory (MB) |
| Host - Physical Interface Receive | `LinuxScript` | XenServerHostname, InterfaceName | `Host_InterfaceReceiveBytesPerSec` |
| Host - Physical Interface Send | `LinuxScript` | XenServerHostname, InterfaceName | `Host_InterfaceSendBytesPerSec` |
| Host - Enabled and Live | `LinuxScript` | XenServerHostname | `Host_EnabledAndLive` — 1 or 0 |
| Host - Uptime | `LinuxScript` | none | `Host_UptimeSeconds` — dom0's own `/proc/uptime`, not an `xe` value |
| Pool - VMs Running | `LinuxScript` | none | `Pool_VMsRunning` |
| Pool - VMs Halted | `LinuxScript` | none | `Pool_VMsHalted` |
| Pool - VMs Suspended | `LinuxScript` | none | `Pool_VMsSuspended` |
| Pool - Default Storage Repository Used Percent | `LinuxScript` | none | `Pool_DefaultSRUsedPercent` |
| Pool - Default Storage Repository Free | `LinuxScript` | none | `Pool_DefaultSRFreeGB` |
| Pool - Snapshot Count | `LinuxScript` | none | `Pool_SnapshotCount` |
| Pool - Oldest Snapshot Age | `LinuxScript` | none | `Pool_OldestSnapshotAgeDays` |
| Pool - Orphaned Virtual Disk Count | `LinuxScript` | none | `Pool_OrphanedVDICount` — the `xe`/XenAPI analogue of `Orion.VIM.DiskFiles.Orphaned` |
| Host - XenAPI Management Port (443) | `TcpPort` | none (uses the assigned node's own address) | reachability of the management API itself |

Every `LinuxScript` component here is **one metric, one component**, matching what all 63
reference components do — not the multi-statistic-per-component design an earlier revision of
this template used, which the reference export gives no evidence for.

## The `CommandLineToPass` argument-prompt mechanism

This is the mechanism that makes a single-component, single-metric template usable across
different hosts and VMs without hand-editing the `.apmtemplate` file per target, and it was
missed entirely in this template's first draft.

A `LinuxScript` component's `CommandLineToPass` setting holds the shell invocation, built from
the `${SCRIPT}` macro (substituted with the uploaded script's path on the target, the same macro
[sam-templates.md](sam-templates.md#credentials-do-not-travel-and-neither-do-secrets) already
documents) followed by zero or more `<PlaceholderName>` tokens:

```
/bin/sh ${SCRIPT} <XenServerHostname> <InterfaceName>
```

**Each `<PlaceholderName>` becomes a field SAM prompts for when the component is added to a
node**, and the value entered there is passed to the script as a positional argument in order —
`<XenServerHostname>` becomes `$1`, `<InterfaceName>` becomes `$2`, and so on. This is how the
reference template's "Host - Average CPU" component, reused against any host in a pool, gets
told *which* host to query: the operator types the Citrix hostname once, at assignment time, and
the same template definition serves every host. It is also how "VM - CPU Utilization" in the
reference template is told which VM and which named vCPU data source to read.

Practical consequences for this repository's own components:

- **Components with `Inputs: None`** (everything under "Pool -" above, plus "Host - Uptime")
  self-discover their target by running `xe host-list`, `xe vm-list`, `xe pool-list` and so on
  with no arguments, which works because those commands query whichever pool member the SSH
  credential lands the session on. They carry a bare `CommandLineToPass` of
  `/bin/sh ${SCRIPT}` with no placeholders. **The reference template never demonstrates a
  zero-placeholder `CommandLineToPass`** — all 63 of its components take at least one argument
  — so this specific shape is this repository's own extrapolation, not something read off the
  reference file. It is ordinary enough shell invocation syntax that it should work, but it has
  not been seen in a real export the way every other structural claim on this page has.
- **Components with named inputs** (`Host - CPU Utilization` and the rest of the host-level
  ones) prompt for the same `XenServerHostname` the reference template's host-level components
  do, and `Host - Physical Interface Receive`/`Send` additionally prompt for `InterfaceName`,
  mirroring the reference template's own "Host - Physical Interface Receive" component exactly
  (down to reading `pif_"$IfName"_rx` from the second argument).

## `xe` commands and data source names

Every `xe` invocation and RRD data source name in this template's host-level components
(`cpu_avg`, `memory_free_kib`, `memory_total_kib`, `pif_<interface>_rx`/`_tx`, and the
`xe host-data-source-query hostname=$Hostname data-source=...` calling convention itself) is
copied from the reference template's own scripts rather than reconstructed from Citrix's
documentation independently — this is the "export a known-good one and rewrite values in place"
approach [sam-templates.md](sam-templates.md#writing-one-by-hand) recommends, applied to a
template file instead of a single query. `xe host-list hostname=$Hostname params=enabled
--minimal` in "Host - Enabled and Live" is the one host-level command this repository's own
component uses that the reference template does not demonstrate in that exact form (the
reference template has no equivalent component); confirm it against `xe host-list --help`
on your own host before relying on it.

The pool-level components' commands (`xe vm-list power-state=...`, `xe pool-list
params=default-SR`, `xe sr-param-get`, `xe snapshot-list`/`snapshot-param-get`, `xe vdi-list`/
`vbd-list`) are this repository's own, verified against Citrix's published `xe` CLI reference
rather than against a SolarWinds sample, because the reference template has no pool-inventory
components to copy from.

## Assign it like any other template

Nothing about assignment is Citrix-specific; it is exactly the flow in
[sam.md](sam.md#assigning-a-template-from-powershell). The credential must be SSH-capable for an
account on a Citrix Hypervisor host with permission to run `xe`; `root` always can, and a
non-root user needs the appropriate group membership or `xe` calls fail with a permission error
rather than a missing-command error.

```powershell
$xml = Get-Content -Raw '.\citrix-hypervisor-monitoring.apmtemplate'
$templateId = (Invoke-SwisVerb $swis 'Orion.APM.ApplicationTemplate' 'ImportTemplate' @($xml)).InnerText

$nodeId = Get-SwisData $swis `
    "SELECT NodeID FROM Orion.Nodes WHERE IPAddress = @ip" @{ ip = '192.0.2.20' }

$applicationId = (Invoke-SwisVerb $swis 'Orion.APM.Application' 'CreateApplication' @(
    $nodeId, $templateId, $credentialSetId, 'false'
)).InnerText
```

When you add each component to the application (or edit it afterward), fill in the
`XenServerHostname`/`InterfaceName` prompts the console shows for the components that declare
them — an empty prompt means `$1`/`$2` is empty in the script, and every script here treats a
missing value as `0` rather than failing loudly, so a blank prompt reads as "the metric is zero"
rather than "not configured."

**Test before you assign at scale.** `StartTestComponents` (documented in
[sam-templates.md](sam-templates.md#test-before-you-assign)) runs every component against a real
node without creating an application, which is the way to find a missing `xe` binary, a
non-root credential, an unset prompt, or a host with no default storage repository before it
shows up as a broken application in the console.

## What is verified here and what is not

- **The `.apmtemplate` XML shape used in this file** — root element order, the `Settings`
  namespace, the per-component setting keys (`AuthenticationType`, `CommandLineToPass`,
  `CountAsDifference`, `Port`, `ScriptBody`, `ScriptDirectory`, `StatusRollupType`), and the full
  `DynamicColumnSettings`/`DynamicEvidenceColumnSchema`/`Threshold` structure — is copied
  element-for-element from the real Citrix Hypervisor reference export, not inferred.
- **The `Statistic.<Name> : <value>` output line and its one-metric-per-component design** are
  likewise copied from the reference template's own proven pattern.
- **The host-level `xe` commands and data source names this file's host-level components use**
  are copied from the reference template's own scripts.
- **The zero-placeholder `CommandLineToPass` this file's pool-level components use**
  (`/bin/sh ${SCRIPT}` with no arguments) is this repository's own construction — the reference
  template never has a component that needs no operator input, so this shape has not been seen
  in a real export.
- **The pool-level `xe` commands** (`vm-list`, `pool-list`, `sr-param-get`, `snapshot-list`,
  `snapshot-param-get`, `vdi-list`, `vbd-list`) are this repository's own, checked against
  Citrix's published `xe` reference, not against a SolarWinds sample.
- **Whether a single script run can emit more than one `Statistic.<Name>` line for more than one
  `DynamicEvidenceColumnSchema` column on the same component** is structurally plausible but
  unexercised by the reference template, which never does it. This repository's components stay
  one metric per component specifically to avoid relying on that unverified extension.
- **The template-level `Id` (`9000`) and `ApplicationTemplateId`/`ComponentTemplateID` values
  used to cross-reference components to their columns** are made-up integers chosen not to
  collide with the reference template's own `Id` of `30`, following the same "local integer,
  meaningless across servers" rule [sam-templates.md](sam-templates.md#the-template) documents;
  they matter only for internal consistency within this file, not for import correctness.

None of the above blocks the template from being imported and read as a starting point. It
distinguishes what was copied from a proven, working file from what this repository built by
extension and has not yet seen confirmed.

## Known limitations

- **Per-VM metrics are not covered at all.** The reference template's own VM-level components
  (CPU, memory, disk, network, per-vCPU run states) already cover this territory in detail, one
  component per metric with a `VirtualMachineUuid` (and sometimes a second identifier such as
  `CPU Name`) prompt at assignment time. This repository's template does not duplicate them;
  import the reference template alongside this one if you need per-VM detail.
- **Pool-level components assume a pool master's view.** `xe vm-list`, `xe pool-list` and
  `xe snapshot-list` all query the pool database, which every member can see, but the numbers
  are pool-wide regardless of which member you assign the component to. There is no equivalent
  concern for the host-level components, since those are explicitly told which host to query via
  `XenServerHostname`.
- **One storage repository only.** "Pool - Default Storage Repository Used Percent"/"Free" read
  `xe pool-list params=default-SR`, so a pool with several SRs worth watching individually needs
  one more pair of components per additional SR, following the same `sr-param-get` pattern with
  a hard-coded SR UUID (or, more robustly, an SR name prompted for through `CommandLineToPass`
  the way the host-level components take a hostname).
- **Credentials do not travel with the export**, exactly as `sam-templates.md` documents for
  every `.apmtemplate`: `__CredentialSetId` is `0` in this file, so every node this template is
  assigned to needs a credential chosen at assignment time.

## The API Poller alternative

[scripts/api-pollers/citrix-hypervisor-xenapi.apipoller.template](../../scripts/api-pollers/citrix-hypervisor-xenapi.apipoller.template)
remains in this repository as an experimental sketch of reaching XenAPI's JSON-RPC endpoint
directly over HTTPS instead of through SSH and `xe`. Nothing about the discovery of a real,
working SAM template changes its status: it is still unverified, for the reasons
[api-pollers.md](../polling/api-pollers.md) and its own file comments already state — chiefly
that the session-token handoff syntax between chained requests has never been seen in a real
export. With a proven SAM template now available for the SSH/`xe` route, there is even less
reason to reach for the API Poller route unless a specific policy forbids SSH to dom0 while
allowing HTTPS to the management API.

## Status and open questions for whoever picks this up next

1. **Import both templates against a real host and run `StartTestComponents` on every
   component.** Nothing in either template has touched a live Citrix Hypervisor host or a live
   SAM server. The structural claims above are now grounded in a real export rather than
   inferred, which is a materially stronger position than this page was in before, but "the XML
   shape matches a working file" and "the numbers this file's own new scripts produce are
   correct" are still two different kinds of confidence.
2. **Confirm whether a zero-placeholder `CommandLineToPass` (`/bin/sh ${SCRIPT}` with no
   arguments) imports and runs correctly.** This is the one structural shape in this file with
   no precedent in the reference export; if it fails, the fix is to give every pool-level
   component a `PoolMasterHostname`-style placeholder even though the script does not strictly
   need it, purely to match a proven shape.
3. **Confirm the pool-level `xe` commands** (`vm-list`, `pool-list`, `sr-param-get`,
   `snapshot-list`, `vbd-list`, `vdi-list`) against a real pool, since they are this repository's
   own construction rather than copied from a working sample.
4. **Consider whether a single component can legitimately emit several `Statistic.<Name>`
   lines.** If confirmed, later revisions of this template could consolidate related metrics
   (for example the three storage numbers, or the three VM power-state counts) back into fewer,
   richer components, the way this template's very first draft attempted before that approach
   was found to have no support in a real export.

## See also

- [sam-templates.md](sam-templates.md) — the `.apmtemplate` file format, including the fourth
  sample's corrections to element order, the `Settings` namespace, and `DynamicColumnSettings`
- [sam.md](sam.md) — SAM entities, verbs, and assigning a template to a node
- [../../scripts/sam-templates/](../../scripts/sam-templates/) — the template file itself
- [../polling/api-pollers.md](../polling/api-pollers.md) — the API Poller format, for the
  still-experimental XenAPI alternative
- [../../scripts/api-pollers/citrix-hypervisor-xenapi.apipoller.template](../../scripts/api-pollers/citrix-hypervisor-xenapi.apipoller.template) —
  the experimental multi-request API Poller template
- [vman.md](vman.md) — why Citrix Hypervisor gets none of this natively: it is not one of the
  platforms `Orion.VIM.Discovery` supports

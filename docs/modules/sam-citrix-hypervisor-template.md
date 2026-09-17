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
  by this reference, so this repository's own components stayed one metric per component
  until the MongoDB 5.0+ (Linux) v2 template, re-exported from a 2026.4 server on 2026-09-17,
  proved several named pairs from one component. The file was regrouped to five scripts on
  that evidence; see [the rework](#the-2026-09-17-rework-five-scripts-instead-of-fifteen).
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
six components covering pool-wide inventory facts the reference template does not: VM
power-state counts, default storage repository capacity, snapshot age and count, and orphaned
virtual disk detection, plus the host metrics worth having beside them (CPU, memory, one named
physical interface, uptime, enabled/live status). Import both if you want the full picture:
the reference template for detailed per-host and per-VM performance counters, this one for
pool-level inventory.

| Component | Type | Inputs prompted at assignment | Reports (`Statistic.<Name>`) |
| --- | --- | --- | --- |
| Host - Resources | `LinuxScript` | XenServerHostname | `Host_CPU_Utilization` (%), `Host_FreeMemoryMB`, `Host_TotalMemoryMB`, `Host_EnabledAndLive` (1/0), `Host_UptimeSeconds` (dom0's own `/proc/uptime`) |
| Host - Physical Interface Throughput | `LinuxScript` | XenServerHostname, InterfaceName | `Host_InterfaceReceiveBytesPerSec`, `Host_InterfaceSendBytesPerSec` |
| Pool - Virtual Machines | `LinuxScript` | none | `Pool_VMsRunning`, `Pool_VMsHalted`, `Pool_VMsSuspended` |
| Pool - Default Storage Repository | `LinuxScript` | none | `Pool_DefaultSRUsedPercent`, `Pool_DefaultSRFreeGB` |
| Pool - Snapshots and Orphaned Disks | `LinuxScript` | none | `Pool_SnapshotCount`, `Pool_OldestSnapshotAgeDays`, `Pool_OrphanedVDICount` (the `xe` analogue of `Orion.VIM.DiskFiles.Orphaned`) |
| Host - XenAPI Management Port (443) | `TcpPort` | none (uses the assigned node's own address) | reachability of the management API itself, `Response` time |

### The 2026-09-17 rework: five scripts instead of fifteen

The previous revision of this file had sixteen components, one metric each, because the
Citrix reference export never shows more than one `Statistic.<Name>` per component and that
was the only proven shape. SolarWinds' own MongoDB 5.0+ (Linux) v2 template, re-exported from
a 2026.4 server the same day (see
[sam-templates.md](sam-templates.md#dynamic-script-columns-dynamiccolumnsettings-and-the-statisticname-output-contract)),
emits up to eight named pairs from one `LinuxScript` component, so the fifteen scripts are now
five, grouped by what they need from the operator and by the `xe` calls they share. Three
things changed with that:

- **A poll costs five SSH sessions instead of fifteen.** Each `LinuxScript` component is one
  SSH login, one script upload and one run; the reference template's 63 components are 63
  logins every polling interval, which is why it is heavy. Grouping is the mitigation.
- **Every value has a `Message.<Name>` beside it**, so the component's detail view names the
  host, the interface, the storage repository, rather than showing a bare number. This is the
  MongoDB shape exactly: for each name a `String` column (the message) and then a `Numeric`
  column (the value), both carrying that name.
- **Failures say why.** The old scripts ran under `set -e` and died silently, leaving a Down
  component with no message. Each script now checks its arguments, checks that `xe` exists,
  captures the error text of every `xe` call, and on any failure prints one unnamed
  `Message:` line and exits `1`, the same pattern the MongoDB scripts use. The argument and
  missing-`xe` paths were exercised on a host without `xe`; the `xe` failure paths were not.

The `TcpPort` component was also wrong in the previous revision: it carried a setting named
`Port` where the type uses `PortNumber`, and no `Thresholds` block where the type carries one
keyed `Response`. Both are corrected from the MongoDB export's own `TcpPort` component. That
component would have failed on import or polled with no port; nothing else in the old file was
structurally wrong.

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
  namespace, the `LinuxScript` setting keys (`AuthenticationType`, `CommandLineToPass`,
  `CountAsDifference`, `Port`, `ScriptBody`, `ScriptDirectory`, `StatusRollupType`), the
  `TcpPort` keys (`PortNumber` and the `Response` threshold), and the full
  `DynamicColumnSettings`/`DynamicEvidenceColumnSchema`/`Threshold` structure — is copied
  element-for-element from real exports: the Citrix Hypervisor reference and, since
  2026-09-17, SolarWinds' MongoDB 5.0+ (Linux) v2 template as a 2026.4 server writes it. A
  structural diff of every component in this file against the matching MongoDB component,
  ignoring only ids, names, labels and values, is empty.
- **Several `Statistic.<Name>` / `Message.<Name>` pairs from one component**, with a `String`
  and a `Numeric` column per name, is the MongoDB template's own shape, not an extension.
- **The host-level `xe` commands and data source names** are copied from the reference
  template's own scripts.
- **The zero-placeholder `CommandLineToPass`** (`/bin/sh ${SCRIPT}` with no arguments) is now
  also proven: the MongoDB template passes fixed arguments (`perl ${SCRIPT} /usr/bin/mongosh
  test`) rather than prompts, so a `CommandLineToPass` with no `<Placeholder>` is a shape a
  real template uses.
- **The pool-level `xe` commands** (`vm-list`, `pool-list`, `sr-param-get`, `snapshot-list`,
  `snapshot-param-get`, `vdi-list`, `vbd-list`) are this repository's own, checked against
  Citrix's published `xe` reference, not against a SolarWinds sample.
- **The scripts' failure paths** were exercised only for missing arguments and a missing `xe`
  binary, on a host that has no `xe`; what a real `xe` error looks like in the message has not
  been seen.
- **Import of this file** has not been tried against a SolarWinds server, and no Citrix
  Hypervisor host was available to run the scripts. The shape is proven; the `xe` output
  parsing is not.
- **The template-level `Id` (`9000`) and `ApplicationTemplateId`/`ComponentTemplateID` values**
  are made-up integers chosen not to collide with the reference template's own `Id` of `30`,
  following the same "local integer, meaningless across servers" rule
  [sam-templates.md](sam-templates.md#the-template) documents; they matter only for internal
  consistency within this file, not for import correctness.

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

# A SAM template for Citrix Hypervisor (XenServer)

SolarWinds ships no AppInsight application for Citrix Hypervisor (formerly XenServer, and the
commercial counterpart of XCP-ng), and SAM's stock template library has nothing for it either.
This page documents a hand-built `.apmtemplate` that fills that gap for host-level status and
performance, and says plainly which parts of it are verified against SAM's documented behaviour
and which parts are inferred and need confirming on your own server before you rely on them.

The file is [../../scripts/sam-templates/citrix-hypervisor-monitoring.apmtemplate](../../scripts/sam-templates/citrix-hypervisor-monitoring.apmtemplate).
Read [sam-templates.md](sam-templates.md) first if you have not: it documents the `.apmtemplate`
XML shape this file follows, and [sam.md](sam.md) covers the SAM entities and verbs it becomes
once imported and assigned.

## Why SSH and `xe`, not an API poller

Citrix Hypervisor's management API, XenAPI, is an XML-RPC/JSON-RPC service on port 443, not a
REST API with a stable JSON contract, so it does not fit
[the API Poller](../polling/api-pollers.md) the way a REST-based system does. What every
Citrix Hypervisor host carries instead is the `xe` command-line client in dom0, which talks to
the same XenAPI locally over a Unix socket and needs no separate authentication once you have a
shell. That makes an SSH-based `LinuxScript` component the direct fit: SAM already documents
`LinuxScript` as "a script executed over SSH" (see the component type table in
[sam-templates.md](sam-templates.md#the-component-types-seen)), and the platform supplies the
SSH connection and credential itself, so the script body only ever runs `xe` and formats its
output.

## What the template monitors

Thirteen components, each independent, so a target that lacks one capability (no shared
storage, no guests yet) does not take the rest of the application down with it:

| Component | Type | What it runs | Reports (`StatisticN`: `MessageN`) |
| --- | --- | --- | --- |
| Host: CPU Utilization | `LinuxScript` | `xe host-data-source-query data-source=cpu_avg` | 1: CPU Utilization (%) |
| Host: Memory Utilization | `LinuxScript` | `xe host-data-source-query` for `memory_total_kib` and `memory_free_kib` | 1: Memory Used (%), 2: Memory Free (KiB), 3: Memory Total (KiB) |
| Pool: VM Power State Counts | `LinuxScript` | `xe vm-list power-state=<state> is-control-domain=false` | 1: VMs Running, 2: VMs Halted, 3: VMs Suspended |
| Pool: Default Storage Repository Utilization | `LinuxScript` | `xe pool-list params=default-SR`, then `xe sr-param-get` for `physical-size`/`physical-utilisation` | 1: Default SR Used (%), 2: Default SR Free (Bytes), 3: Default SR Size (Bytes) |
| Host: Enabled and Live | `LinuxScript` | `xe host-param-get` for `enabled` and `live` | 1: Host Enabled and Live (1/0) |
| Host: XenAPI Management Port (443) | `TcpPort` | a TCP connect to port 443 | reachability of the management API itself (not a script component) |
| Host: Management NIC Throughput | `LinuxScript` | `xe pif-list management=true`, then `xe host-data-source-query` for `pif_<device>_rx`/`pif_<device>_tx` | 1: Management NIC RX (Bytes/sec), 2: Management NIC TX (Bytes/sec) |
| Pool: VM Snapshot Age and Count | `LinuxScript` | `xe snapshot-list is-a-snapshot=true`, then `xe snapshot-param-get param-name=snapshot-time` per snapshot | 1: Snapshot Count, 2: Oldest Snapshot Age (days) |
| Host: Uptime | `LinuxScript` | reads `/proc/uptime` directly on the host, no `xe` call needed | 1: Host Uptime (seconds) |

The last one does not call `xe` at all: once SSH lands you on the dom0 shell, anything readable
there is fair game, and `/proc/uptime` is the plain Linux mechanism rather than a XenAPI
concept. It is a reminder that a `LinuxScript` component is not limited to `xe`; it is limited
to whatever the SSH credential can read on the box.

**The `pif_<device>_rx`/`pif_<device>_tx` data source names are Citrix's own documented naming
convention** (one pair per physical interface, named after the Linux device), not something
this repository's SAM documentation records, so confirm the exact device name and the data
source's existence on your host before relying on the numbers:

```bash
ssh root@host "xe host-data-source-list | grep pif_"
```

A host with bonded or VLAN interfaces may expose additional `pif_bond0_rx`-style sources; the
script here only reads the management interface's pair.

## Virtual machine and storage coverage, closer to what VIM gives other hypervisors

Four more components push this template past single-number host metrics into the same territory
Virtualization Manager covers with `Orion.VIM.VirtualMachines` and `Orion.VIM.Datastores` for
VMware, Hyper-V, Nutanix and Proxmox VE — with the caveat that none of it is backed by a real
object model the way VIM's is. There is no `Orion.VIM`-style entity for a Citrix VM or SR; every
value below is a line of script output, and the "hierarchy" is whatever component names and
node grouping you build around it.

| Component | Type | What it runs | Reports (`StatisticN`: `MessageN`) |
| --- | --- | --- | --- |
| Pool: VM Resource Allocation Summary | `LinuxScript` | Sums `VCPUs-max` and `memory-actual` across running VMs, compares against the host's `cpu_info`/`memory-total` | 1: Allocated vCPUs, 2: Physical CPU Cores, 3: vCPU to Core Ratio, 4: Allocated Memory (MiB), 5: Physical Memory (MiB) |
| VM: Top 5 CPU Consumers | `LinuxScript` | For each running VM, sums its `cpu<N>` data sources via `xe vm-data-source-query`, keeps the five highest | 1-5: one VM's CPU (%) each, `MessageN` names the VM |
| Pool: All Storage Repositories Utilization | `LinuxScript` | Loops every `content-type=user` SR (not just the pool's default), reading `physical-size`/`physical-utilisation`, keeps the five fullest | 1-5: one SR's Used (%) each, `MessageN` names the SR |
| Pool: Orphaned Virtual Disks | `LinuxScript` | Diffs `xe vdi-list` against every VDI referenced by `xe vbd-list`, the direct analogue of `Orion.VIM.DiskFiles.Orphaned` | 1: Orphaned VDI Count, 2: Orphaned VDI Total (GiB) |

Three things about these four are worth understanding before you rely on them:

**"VM: Top 5 CPU Consumers" and "Pool: All Storage Repositories Utilization" both discover their
objects at poll time and can report fewer than five pairs**, never more: a pool with three SRs
fills `Statistic1`-`Statistic3` and leaves `Statistic4`/`Statistic5` unset for that poll, and a
pool with twelve SRs still reports only the five fullest. That is a direct consequence of the
ten-`Statistic`/ten-`Message` ceiling described below applied to an object count that varies per
pool — there is no way to fit "every SR" into a fixed-slot output, so both scripts rank and keep
the top five. It also means the *meaning* of `Statistic3` on "All Storage Repositories
Utilization" can change from one poll to the next if SR usage reshuffles which five are fullest,
which is worth knowing before wiring an alert to a specific slot number rather than reading
`Message3` alongside it to see which SR it currently refers to.

**`cpu_info param-key=cpu_count` and the per-vCPU `cpu<N>` data source names are Citrix's
documented conventions, not something this repository's SAM documentation records.** Confirm
both before trusting the numbers:

```bash
ssh root@host "xe host-param-get uuid=\$(xe host-list --minimal | cut -d',' -f1) param-name=cpu_info"
ssh root@host "xe vm-data-source-list uuid=<a-running-vm-uuid>"
```

`vm-data-source-list` on a Windows guest without the Citrix VM tools installed, or a guest that
has never been queried before, can come back empty; the top-5 script treats that VM as
contributing zero rather than failing the whole component, which is deliberate but means a
missing VM from the report is not necessarily an idle one.

**"Orphaned Virtual Disks" answers the same question `Orion.VIM.DiskFiles.Orphaned` answers for
VMware, and the same caveat vman.md records for that column applies here too**: a VDI with no
`VBD` is the mechanical definition of orphaned, but *why* it has no VBD is not something the
script (or the schema, on VIM's side) can tell you — it could be a stale leftover from a
half-finished VM deletion, or a disk deliberately detached and kept for later. Review the list
before deleting anything from it.

`cpu_avg`, `memory_total_kib` and `memory_free_kib` are RRD data source names that Citrix's own
`xe host-data-source-list` documentation exposes for exactly this purpose: live performance
counters read off the host's in-memory round-robin database, the same data XenCenter and
`xe`'s own `vm-list vgpu-uuid=... ` style monitoring graphs draw from. `host-data-source-query`
returns a bare floating-point number (a fraction for `cpu_avg`, hence the `* 100` in the CPU
script), which is why each script does its own arithmetic before printing a labelled line.

## The script output contract: up to ten statistics and ten messages per run

Every script here prints paired lines of the form:

```
Statistic1: 42.00
Message1: CPU Utilization (%)
```

**A single script monitor run can report at most ten `StatisticN`/`MessageN` pairs, numbered
1 through 10.** `StatisticN` carries the number the console charts and thresholds against;
`MessageN` is the label an operator reads next to it. This is a fixed-slot contract, not the
free-form arbitrary-column mechanism an earlier version of this page assumed: a script cannot
invent an eleventh statistic, and it cannot name a slot anything other than the literal string
`StatisticN`/`MessageN` in its own output — the human-readable label lives entirely in
`MessageN`'s text, not in the key.

**This convention is stated here on a practitioner's word, not verified against this
repository's own schema data or a real `.apmtemplate` export that uses it.** `sam-templates.md`
documents the `DynamicEvidence`/`DynamicEvidenceColumnSchema` entities as one real mechanism SAM
uses to carry "the columns a script monitor returned," but does not describe the ten-slot
`Statistic`/`Message` contract, because none of the three source exports that page was built
from used it. Treat the exact literal keys (`Statistic1` versus `Stat1`, colon-plus-space
versus some other separator, case sensitivity) as worth confirming with `StartTestComponents`
against a real host before trusting a component's output blindly — the same test-before-scale
advice this page already gives for the credential and the `xe` binary applies here too, and it
is the cheapest way to see the raw parsed result rather than guessing at it.

Every component in this template stays at or under ten pairs by design: five is the largest
fixed count any single component uses (`Pool: VM Resource Allocation Summary`), and the two
components with a variable object count (`VM: Top 5 CPU Consumers`,
`Pool: All Storage Repositories Utilization`) cap themselves at five pairs with `head -5` for
exactly this reason.

## Assign it like any other template

Nothing about assignment is Citrix-specific; it is exactly the flow in
[sam.md](sam.md#assigning-a-template-from-powershell). The one thing to get right is the
credential: it must be an SSH-capable credential (a username with a password, or a key,
depending on what your SAM server's script credential type supports) for an account on the
Citrix Hypervisor host with permission to run `xe`. `root` is the account that can always run
`xe` without additional configuration; a non-root local user needs to be added to the
appropriate group or the calls will fail with a permission error rather than a missing-command
error.

```powershell
$xml = Get-Content -Raw '.\citrix-hypervisor-monitoring.apmtemplate'
$templateId = (Invoke-SwisVerb $swis 'Orion.APM.ApplicationTemplate' 'ImportTemplate' @($xml)).InnerText

$nodeId = Get-SwisData $swis `
    "SELECT NodeID FROM Orion.Nodes WHERE IPAddress = @ip" @{ ip = '192.0.2.20' }

$applicationId = (Invoke-SwisVerb $swis 'Orion.APM.Application' 'CreateApplication' @(
    $nodeId, $templateId, $credentialSetId, 'false'
)).InnerText
```

**Test before you assign at scale.** `StartTestComponents` (documented in
[sam-templates.md](sam-templates.md#test-before-you-assign)) runs every component against a real
node without creating an application, which is the way to find a missing `xe` binary, a
non-root credential, or a host with no default storage repository before it shows up as a
broken application in the console.

## What is verified here and what is not

Following this repository's own rule of never asserting a fact that has not been looked up:

- **The `.apmtemplate` XML shape** (element order, the `KeyValueOfstringSettingValueyR_SGpLPx`
  type name, the `Settings`/`ValueType` grouping) is exactly what
  [sam-templates.md](sam-templates.md) documents from three real SolarWinds exports, and this
  file follows it element-for-element.
- **The `xe` commands and RRD data source names** (`cpu_avg`, `memory_total_kib`,
  `memory_free_kib`, `physical-size`, `physical-utilisation`, `enabled`, `live`) are Citrix's own
  published `xe` CLI and XenAPI vocabulary, not something inferred from a SolarWinds sample.
- **`ExecutionMode: SSH` on the `LinuxScript` components is inferred, not verified against a
  real SAM export.** The three templates this repository's SAM documentation was built from
  (a MongoDB template, an Azure App Service template, and one monitoring an Orion polling
  engine) all use `LinuxScript` components, and `sam-templates.md` records that the type reads
  `ScriptBody`, `ScriptArguments` and `ExecutionMode` from `Settings`, but does not record which
  literal string `ExecutionMode` holds for a `LinuxScript` component, because none of the three
  source exports needed to distinguish it from another mode. `SSH` is the only transport SAM
  documents for `LinuxScript`, so it is the most likely value, but confirm it by exporting any
  working `LinuxScript`-based template from your own server (`ExportTemplate`) and diffing its
  `ExecutionMode` value against this file before assuming an import failure is unrelated.
- **`ScriptBody`'s `ValueType` of `External` follows the pattern `sam-templates.md` documents**
  ("`External` | A large payload held outside the normal value flow | `ScriptBody` — and
  nothing else"), but that page also notes the samples do not fully explain what "held outside
  the normal value flow" means for how the value round-trips. This file embeds the script text
  directly inside `<Value>` regardless, matching what SolarWinds' own exports show on the wire.
- **The `Statistic1..10`/`Message1..10` script output contract itself** is asserted here on
  outside practitioner knowledge, not derived from this repository's schema data or a real
  export — see the section above for exactly what that means for how much to trust it as
  written.
- **`DynamicColumnSettings` is left empty (`<DynamicColumnSettings/>`)** on every component.
  `sam-templates.md` shows this element holding real content on the one `LinuxScript` component
  it quotes in full, but does not document that content's structure. The most likely purpose,
  given the ten-slot contract above, is that it is where the console records a friendlier
  display name and a threshold for each `StatisticN` slot once you set one — but that is an
  inference about an undocumented element, not a confirmed mapping. The practical effect either
  way: after import, open each component in **Manage Templates** and set each statistic's
  display name and threshold there once, rather than expecting them pre-populated. The
  application will still poll and report the numbers in `MessageN`'s text without that step;
  only client-side thresholding and relabeling depend on it.
- **`Thresholds` is left empty on every component** for the same reason: the threshold shape
  `sam-templates.md` documents applies to a single named metric on the component
  (`CriticalLevel`, `WarnLevel`, and so on), and these are multi-statistic script components
  where thresholding is configured per `StatisticN` slot through the console instead.

None of the above blocks the template from polling. It changes only whether thresholds and
column labels come pre-configured on import or need one pass through the console afterward,
which is a cheap, one-time step per template rather than per node.

## The API Poller alternative, and why it is harder here

Citrix Hypervisor's XenAPI is reachable directly over HTTPS as a JSON-RPC service, which means
[the API Poller](../polling/api-pollers.md) can in principle reach it without an SSH hop at
all. Whether that is a better fit than the SAM template above depends on what XenAPI demands of
a caller, and it demands more than a single GET.

**Every XenAPI call needs a session reference, and getting one is itself a call.** The sequence
is always: POST `session.login_with_password` to get an opaque session ref back, then pass that
ref as the first argument to every real call, one call per data point
(`host.query_data_source(session, host, data_source)` returns exactly one number). The API
Poller model supports exactly this shape in principle:
`Orion.APIPoller.RequestVariable` exists precisely "to use in a later request" (see
[api-pollers.md](../polling/api-pollers.md#the-request)), and `RequestDetailsOrder` sequences
a multi-request template. So a login request followed by one `host.query_data_source` request
per metric is a legitimate use of the format, not a workaround.

**What is not documented, anywhere in the extracted schema or this repository's own API Poller
page, is the placeholder syntax a later request uses to reference an earlier `RequestVariable`
inside its own `Body`.** `api-pollers.md` states plainly that `Path` syntax, `Type` and
`ThresholdRule` values are themselves unverified against the schema; the variable-substitution
mechanism sits one level further out; there is no worked multi-request example with a body
substitution to derive it from.
[scripts/api-pollers/citrix-hypervisor-xenapi.apipoller.template](../../scripts/api-pollers/citrix-hypervisor-xenapi.apipoller.template)
uses `{{SessionRef}}` inside the JSON body of each follow-up request as the most likely
candidate (double-brace mustache-style interpolation is the common convention this kind of
feature reaches for), but **this specific syntax is inferred, not confirmed**, and is exactly
the kind of plausible-but-wrong detail this repository's own rule warns against stating flatly.

Do not import that file into a production server expecting it to work as shipped. Instead:

1. Build one two-request poller by hand in the console — **Settings > All Settings > API
   Poller** — with a login request and a single dependent request, and confirm it actually
   substitutes the session ref before trusting the mechanism at all.
2. Export it (`ExportTemplateFromApiPoller` or the console's export) and read back what
   placeholder syntax the console itself wrote into the `Body` of the second request. That is
   the authoritative answer, the same way this repository derives every other file format from
   a real export rather than from a guess.
3. Only then treat the shipped template here as a starting shape to edit, not as something to
   import as-is.

**Even once the substitution syntax is confirmed, this route buys you less than it costs.**
Every additional metric is another full request block (its own URL, headers, and a fresh
`RequestDetailsOrder`), because a single `host.query_data_source` call returns one number, not
a record. The nine-component SAM template above gets the same data with fewer moving parts,
each component testable independently with `StartTestComponents`, at the cost of an SSH hop
instead of a direct HTTPS call. Reach for the API Poller route only if a policy in your
environment prohibits SSH to hypervisor dom0 but allows HTTPS to the management API, since that
is the one condition under which the extra fragility is worth it.

The shipped file demonstrates the pattern (login, then two chained `host.query_data_source`
calls for CPU and free memory) with placeholders (`__CITRIX_HOST__`, `__USERNAME__`,
`__PASSWORD__`, `__HOST_UUID__`) to replace, and its free-memory metric's thresholds are
deliberately set so high they cannot fire — because `ThresholdRule` is documented here as
`GreaterThan` in every sample seen, with no confirmation that any "lower is worse" operator
exists (see [api-pollers.md](../polling/api-pollers.md#the-threshold-boundary)), and asserting
one would be exactly the kind of unverified claim this repository declines to state as fact.
Treat that value as informational until you confirm what operators your server actually
supports.

## Known limitations

- **The original storage component still reads only the pool's default SR.** "Pool: Default
  Storage Repository Utilization" (component 4) reads `pool-list params=default-SR`; "Pool: All
  Storage Repositories Utilization" (component 12) covers every `content-type=user` SR and
  supersedes it for capacity monitoring. The two overlap on the default SR, which is redundant
  rather than wrong; disable component 4 after import if you only want the per-SR view.
- **Per-VM coverage is CPU only, and only the top five.** "VM: Top 5 CPU Consumers" answers "is
  something busy" for the biggest consumers, not "what is every VM doing." Per-VM memory,
  network or disk I/O would need the same `vm-data-source-query` pattern against
  `memory_internal_free`, `vif_<device>_rx`/`tx`, or `vbd_<device>_read`/`write`, and a pool
  with more VMs than fit in a top-5 report loses the smaller ones entirely. A pool small enough
  to name every VM in its own component (rather than discovering them at poll time) could get
  one `LinuxScript` component per VM instead, at the cost of hand-editing the template whenever
  a VM is added or removed — VIM's discovery-driven model does not have that tradeoff because it
  polls in an object model, not a script.
- **A pool master's view, not necessarily a slave's.** `xe host-list`, `xe pool-list` and
  `xe vm-list` all query the pool database, which every host in a pool can see, but assigning
  this template to a pool slave still reports pool-wide VM counts and the pool's default SR
  rather than that slave's own local view. Point it at the pool master, or add a `host-uuid=`
  filter to `host-list`/`vm-list` if you specifically want one slave's local state.
- **Credentials do not travel with the export**, exactly as `sam-templates.md` documents for
  every `.apmtemplate`: `__CredentialSetId` is `0` in this file, so every node this template is
  assigned to needs a credential chosen at assignment time.

## Status and open questions for whoever picks this up next

Nothing here has been tested against a live Citrix Hypervisor host or a live SAM server. Every
`xe` command is real Citrix CLI syntax and every SWQL/schema fact elsewhere in this repository
is checked by `make check`, but the two artifacts this page documents sit outside that gate:
`tools/check_api_poller_templates.py` validates the API Poller file's XML *shape*, and nothing
in this repository validates an `.apmtemplate`'s XML shape or either file's *runtime* behavior.
Treat both as drafts a human (or the next agent, with `StartTestComponents` and a lab host)
needs to run before they reach production. In priority order, the open items are:

1. **Confirm the `Statistic1..10`/`Message1..10` script output contract.** This was corrected
   into the template mid-session on a practitioner's statement that a SAM script run supports
   at most ten statistics and ten messages; the earlier draft had every component print
   arbitrary `Label : Value` lines instead, which is very likely wrong for a real `LinuxScript`
   or PowerShell script component. The current text and literal key casing (`Statistic1:` with
   a colon and single space, `MessageN` for the label) is not verified against a real SAM
   export or console-parsed output. Import the template, run `StartTestComponents` against one
   host, and read back what the console actually parsed before trusting any component's output.
   If the real separator, key name, or slot count differs, every `ScriptBody` in
   `citrix-hypervisor-monitoring.apmtemplate` needs the same fix applied uniformly.
2. **Confirm `ExecutionMode: SSH`** on the `LinuxScript` components (see "What is verified here
   and what is not" above) by exporting a known-working `LinuxScript` template from a real
   server and diffing the value.
3. **Confirm the API Poller's session-variable substitution syntax** (`{{SessionRef}}` in
   `citrix-hypervisor-xenapi.apipoller.template`) the same way, per "The API Poller alternative"
   section above. This one is lower priority than the two SAM items: the API Poller route is
   already documented as the weaker option, and the SAM template is the one meant for actual use.
4. **`DynamicColumnSettings`'s real structure** remains unknown; confirming it is optional
   (see the bullet above) but would let a future revision ship components with display names
   and thresholds pre-populated instead of needing one console pass per import.

None of the four block the template from being imported and read as a starting point — they
block trusting its numbers without first testing them, which this page says plainly everywhere
it applies rather than only here.

## See also

- [sam-templates.md](sam-templates.md) — the `.apmtemplate` file format this template follows
- [sam.md](sam.md) — SAM entities, verbs, and assigning a template to a node
- [../../scripts/sam-templates/](../../scripts/sam-templates/) — the template file itself
- [../polling/api-pollers.md](../polling/api-pollers.md) — the API Poller format, and the
  request-chaining model the experimental XenAPI template above depends on
- [../../scripts/api-pollers/citrix-hypervisor-xenapi.apipoller.template](../../scripts/api-pollers/citrix-hypervisor-xenapi.apipoller.template) —
  the experimental multi-request API Poller template
- [vman.md](vman.md) — why Citrix Hypervisor gets none of this natively: it is not one of the
  platforms `Orion.VIM.Discovery` supports

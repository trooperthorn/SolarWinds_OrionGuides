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

Nine components, each independent, so a target that lacks one capability (no shared storage,
no guests yet) does not take the rest of the application down with it:

| Component | Type | What it runs | Reports |
| --- | --- | --- | --- |
| Host: CPU Utilization | `LinuxScript` | `xe host-data-source-query data-source=cpu_avg` | `CPU_Utilization_Percent` |
| Host: Memory Utilization | `LinuxScript` | `xe host-data-source-query` for `memory_total_kib` and `memory_free_kib` | `Memory_Used_Percent`, `Memory_Free_KiB`, `Memory_Total_KiB` |
| Pool: VM Power State Counts | `LinuxScript` | `xe vm-list power-state=<state> is-control-domain=false` | `VMs_Running`, `VMs_Halted`, `VMs_Suspended` |
| Pool: Default Storage Repository Utilization | `LinuxScript` | `xe pool-list params=default-SR`, then `xe sr-param-get` for `physical-size`/`physical-utilisation` | `SR_Used_Percent`, `SR_Free_Bytes`, `SR_Size_Bytes` |
| Host: Enabled and Live | `LinuxScript` | `xe host-param-get` for `enabled` and `live` | `Host_Available` (1 or 0) |
| Host: XenAPI Management Port (443) | `TcpPort` | a TCP connect to port 443 | reachability of the management API itself |
| Host: Management NIC Throughput | `LinuxScript` | `xe pif-list management=true`, then `xe host-data-source-query` for `pif_<device>_rx`/`pif_<device>_tx` | `Management_NIC_RX_Bytes_Per_Sec`, `Management_NIC_TX_Bytes_Per_Sec` |
| Pool: VM Snapshot Age and Count | `LinuxScript` | `xe snapshot-list is-a-snapshot=true`, then `xe snapshot-param-get param-name=snapshot-time` per snapshot | `Snapshot_Count`, `Oldest_Snapshot_Age_Days` |
| Host: Uptime | `LinuxScript` | reads `/proc/uptime` directly on the host, no `xe` call needed | `Host_Uptime_Seconds` |

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

`cpu_avg`, `memory_total_kib` and `memory_free_kib` are RRD data source names that Citrix's own
`xe host-data-source-list` documentation exposes for exactly this purpose: live performance
counters read off the host's in-memory round-robin database, the same data XenCenter and
`xe`'s own `vm-list vgpu-uuid=... ` style monitoring graphs draw from. `host-data-source-query`
returns a bare floating-point number (a fraction for `cpu_avg`, hence the `* 100` in the CPU
script), which is why each script does its own arithmetic before printing a labelled line.

Every script prints one or more lines shaped `Label : Value`. That is the same
`Name : Value` layout SAM's own `DynamicEvidence` model expects out of a script monitor
(see [sam.md](sam.md#status-statistics-and-evidence)) so that the console can chart each
labelled value and let you threshold on it individually once the template is imported and the
component's columns are recognised.

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
- **`DynamicColumnSettings` is left empty (`<DynamicColumnSettings/>`)** on every component.
  `sam-templates.md` shows this element holding real content on the one `LinuxScript` component
  it quotes in full, but does not document that content's structure, so there is nothing
  verified to construct here. The practical effect: after import, open each component in
  **Manage Templates** and set per-line thresholds there once, rather than expecting them
  pre-populated. The application will still poll and report the labelled values without that
  step; only client-side thresholding depends on it.
- **`Thresholds` is left empty on every component** for the same reason: the threshold shape
  `sam-templates.md` documents applies to a single named metric on the component
  (`CriticalLevel`, `WarnLevel`, and so on), and these are multi-value script components where
  thresholding is configured per output line through the console instead.

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

- **One default storage repository only.** The storage component reads `pool-list
  params=default-SR`, so it reports on the pool's default SR and not on every SR attached to
  the pool. A host with several SRs worth watching individually needs one component per SR
  UUID, following the same `sr-param-get` pattern.
- **No per-VM metrics.** The VM component only counts VMs by power state. Per-VM CPU, memory
  or network figures would need `xe vm-data-source-query` against each VM's UUID, which this
  template does not attempt because the number of VMs, and therefore the number of components
  needed, varies per host.
- **A pool master's view, not necessarily a slave's.** `xe host-list`, `xe pool-list` and
  `xe vm-list` all query the pool database, which every host in a pool can see, but assigning
  this template to a pool slave still reports pool-wide VM counts and the pool's default SR
  rather than that slave's own local view. Point it at the pool master, or add a `host-uuid=`
  filter to `host-list`/`vm-list` if you specifically want one slave's local state.
- **Credentials do not travel with the export**, exactly as `sam-templates.md` documents for
  every `.apmtemplate`: `__CredentialSetId` is `0` in this file, so every node this template is
  assigned to needs a credential chosen at assignment time.

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

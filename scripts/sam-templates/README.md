# SAM application templates

Importable `.apmtemplate` files for Server and Application Monitor.

| File | Demonstrates |
| --- | --- |
| [citrix-hypervisor-monitoring.apmtemplate](citrix-hypervisor-monitoring.apmtemplate) | Five multi-statistic `LinuxScript` components and one `TcpPort` covering Citrix Hypervisor pool inventory (VM counts, storage, snapshots, orphaned disks) plus host CPU, memory, one interface, uptime and enabled/live state, shaped against SolarWinds' own MongoDB template as a 2026.4 server exports it — complements the 63-component Content Exchange Citrix template rather than duplicating it, at five SSH sessions a poll instead of fifteen |
| [windows-udp-port-exhaustion.apmtemplate](windows-udp-port-exhaustion.apmtemplate) | Two `PowerShell` components run on the target over WinRM (percent of the UDP dynamic port range in use and the count, with the processes holding it), four native `UDPv4`/`TCPv4` `PerformanceCounter` components, and two `EventLog` components that go Down on System / Tcpip / 4266 or 4231. Catches the condition before the event fires, and confirms it when it does. The script is also here standalone as [windows-udp-port-exhaustion.ps1](windows-udp-port-exhaustion.ps1) |

The format is documented in
[../../docs/modules/sam-templates.md](../../docs/modules/sam-templates.md), and the module it
belongs to in [../../docs/modules/sam.md](../../docs/modules/sam.md).

## Citrix Hypervisor (XenServer) monitoring

SAM ships no AppInsight for Citrix Hypervisor, so this template gets host status and
performance metrics the way SAM gets anything from a platform it has no purpose-built monitor
for: SSH to the host and read the CLI that ships on it. Citrix Hypervisor's dom0 always carries
`xe`, so no agent or extra package is required on the target.

Full setup, the exact `xe` commands each component runs, required rights, and what is
inferred rather than verified against a real import, are in
[../../docs/modules/sam-citrix-hypervisor-template.md](../../docs/modules/sam-citrix-hypervisor-template.md).
Read it before assigning this template, and test it with `StartTestComponents`
([../../docs/modules/sam-templates.md#test-before-you-assign](../../docs/modules/sam-templates.md#test-before-you-assign))
before rolling it out beyond one host.

## Windows UDP ephemeral port exhaustion

No Windows counter reports how full the UDP dynamic port range is, and the only native signal,
System event Tcpip 4266, fires once it is already full and DNS has stopped working. This
template reads the socket table on the target with `Get-NetUDPEndpoint` and reports the
percentage and the top five owning processes, with the native UDP counters alongside for the
burst itself, and two Windows Event Log components go Down the poll after the event lands.
Every component type in it is shaped against a real 2026.4 export; the details are in
[../../docs/modules/sam-udp-port-exhaustion-template.md](../../docs/modules/sam-udp-port-exhaustion-template.md),
which also says which parts of the file are verified against a real 2026.4 export of a SolarWinds-shipped PowerShell template and which the first import will test.

## Editing one of these

The two safe edits documented in `sam-templates.md` apply here: a component's `ScriptBody`
(plain text, `<` and `&` XML-escaped) and threshold levels. Regenerate the `UniqueId` GUIDs if
you fork a copy for your own environment, since that value is the template's identity across
servers and across SAM's own dedupe logic.

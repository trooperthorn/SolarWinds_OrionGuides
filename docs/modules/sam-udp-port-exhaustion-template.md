# A SAM template for Windows UDP ephemeral port exhaustion

Windows hands every outbound UDP socket a port from one dynamic range (`49152`–`65535` by
default, 16,384 ports). When a process opens sockets faster than it closes them the range
fills, the kernel logs **System / Tcpip / event 4266** ("A request to allocate an ephemeral
port number from the global UDP port space has failed due to all such ports being in use"),
and from that moment every UDP client on the host fails: DNS resolution first, then anything
built on it. Nothing in the stock Windows counters reports how full the range is, and the
event only fires once it is already full, which is why this template exists.

The template in
[scripts/sam-templates/windows-udp-port-exhaustion.apmtemplate](../../scripts/sam-templates/windows-udp-port-exhaustion.apmtemplate)
gets the number SAM cannot get natively — percent of the dynamic range in use and which
processes hold it — with a `PowerShell` component run on the target over WinRM, and surrounds
it with the native `PerformanceCounter` components that show a burst as it happens. The one
component SAM does ship for this signal, a Windows Event Log monitor for event 4266, is added
in the console rather than in the file, for the reason given under
[What is verified and what is not](#what-is-verified-and-what-is-not).

Read [sam-templates.md](sam-templates.md) first for the `.apmtemplate` shape. This file is
built to the fourth-sample shape documented there (payload first, `Serialization/Arrays`
namespace, inner `Key` repeating the setting name), which is the shape of the only real
export this repository holds.

## Why a script and not a counter

The candidates, against the SAM component types:

| Signal | SAM type that could carry it | Verdict |
| --- | --- | --- |
| Ports in use as a fraction of the range | none native — no Windows performance counter or WMI class exposes the count of open UDP endpoints | `PowerShell` component reading `Get-NetUDPEndpoint` |
| Event 4266 has fired | Windows Event Log monitor | native; add in the console |
| UDP datagram rate, no-port datagrams, receive errors | `PerformanceCounter` under category `UDPv4` | native; in the file |
| TCP connections established | `PerformanceCounter` under `TCPv4` | native; in the file, because the TCP pool has the same failure (event 4231) |

`Get-NetUDPEndpoint` is the NetTCPIP module's view of the kernel socket table, the same rows
`netstat -ano -p udp` prints, delivered as objects with an `OwningProcess` column. It is a
local CIM call on the target (class `MSFT_NetUDPEndpoint`), not a performance counter and not a
remote WMI query from the poller. SAM reaches it by running the script on the target, which
is what `ExecutionMode` = `RemoteHost` means for a `PowerShell` component: the poller opens a
WinRM session with the component's credential and runs the script there.

## The components

| # | Component | Type | Reports | Threshold shipped |
| --- | --- | --- | --- | --- |
| 1 | UDP Ephemeral Ports - Percent Used | `PowerShell` (remote) | `PercentUsed`, `EphemeralInUse` | warn 70 %, critical 90 % (and the matching counts, 11 469 / 14 746 of 16 384) |
| 2 | UDPv4 - Datagrams/sec | `PerformanceCounter` | rate | none; baseline |
| 3 | UDPv4 - Datagrams No Port/sec | `PerformanceCounter` | rate | none; baseline |
| 4 | UDPv4 - Datagrams Received Errors | `PerformanceCounter`, `CountAsDifference` | errors per poll | none; baseline |
| 5 | TCPv4 - Connections Established | `PerformanceCounter` | count | none; baseline |

Component 1's script is also shipped standalone as
[scripts/sam-templates/windows-udp-port-exhaustion.ps1](../../scripts/sam-templates/windows-udp-port-exhaustion.ps1)
so it can be run by hand on a suspect host. It prints, for example:

```
Statistic.PercentUsed : 0.23
Message.PercentUsed : 38 of 16384 ephemeral UDP ports (49152-65535) in use. Top: chrome(2628)=17, svchost(7668)=6, svchost(4480)=3, svchost(4220)=2, dasHost(5868)=2
Statistic.EphemeralInUse : 38
Message.EphemeralInUse : total UDP endpoints 58; dynamic range size 16384
```

The script reads the range from `netsh int ipv4 show dynamicport udp` rather than assuming
the default, counts only endpoints whose local port falls inside that range (listening
services on fixed ports below it are not exhaustion), and names the five processes holding the
most. It exits `0` below 70 %, `2` at 70 %, `3` at 90 %, and `1` if it could not read the
table, so the component's own status tracks the number even before a threshold is edited.

The 70 / 90 levels are a starting point. A host that legitimately runs a DNS server, a SIP
proxy or a scanner will sit higher; set the warning a comfortable margin above what that host
shows at its busiest.

## The event log component, added in the console

Add a **Windows Event Log Monitor** to the assigned application with these values. The console
labels are quoted from SolarWinds' page for the monitor:

| Field | Value |
| --- | --- |
| Log to Monitor | `System` |
| Log Source | `Tcpip` |
| Event ID | match specific IDs: `4266` (add `4231` to catch the TCP pool as well) |
| Event Type | Any Event |
| Match Definition | Custom, the fields above |
| Number of past polling intervals to search for events | `1` |
| If a match is found in a polling period, component is | Down |
| Fetching Method | WMI (WinRM/DCOM), or Agent if the node has one |

Its statistic is the count of matching events in the window, so it reads `0` in normal
operation and turns Down the poll after a 4266 lands. Because event 4266 fires only when the
range is already at 100 %, this component is the confirmation; component 1 is the early
warning.

## Assigning it

The `PowerShell` component needs a credential that can open a WinRM session on the target and
has rights to read the socket table, which any local administrator has. WinRM must be listening
(`winrm quickconfig` on the target if it is not), and TCP `5985` must be open from the poller.
The `PerformanceCounter` components use whatever fetching method the node already polls with
and inherit the node credential.

Test with `StartTestComponents` before assigning broadly, as
[sam-templates.md](sam-templates.md#test-before-you-assign) describes.

## Finding the culprit once it fires

The `Message.PercentUsed` line names the processes. When the top entry is `svchost`, the PID
in parentheses resolves to a service group with:

```powershell
tasklist /svc /fi "PID eq <pid>"
```

The range fills in a burst, not a drift, so a poll every five minutes can miss the peak
entirely; the six 4266 events that prompted this template each landed between polls that
showed under 1 %. For a host that has already exhibited the fault, drop `__Frequency` on
component 1 to `60` until the process is identified, then restore it.

## What is verified and what is not

**Verified on a real host (Windows 11 Pro 26200, 2026-09-17):**

- The script's output, exit codes and range detection.
- That the `UDPv4` and `TCPv4` counter names in components 2–5 exist by those exact names,
  from `Get-Counter -ListSet`.
- The file is well-formed XML and mirrors the element order, namespaces, setting element name
  and `DynamicEvidenceColumnSchema` structure of the real Citrix Hypervisor export in this
  repository.

**Taken from real exports described in [sam-templates.md](sam-templates.md) but not
re-exercised here:**

- The `PowerShell` component's setting keys (`ExecutionMode`, `WinRmAuthenticationMechanism`,
  `WrmPort`, `ScriptArguments`, `ScriptBody`) come from the three original samples that page
  was built on, which held fifteen `PowerShell` components between them. The option value
  `RemoteHost` for `ExecutionMode` is this template's inference from the console label
  "Remote Host"; if import rejects it, build one `PowerShell` component in the console, export,
  and copy the value the platform writes.
- The `PerformanceCounter` component's keys `Category`, `Counter` and `Instance` likewise. The
  same page lists `PreferredPollingMethod` as a fourth key; it is omitted here so the platform
  default applies, on the reasoning that a missing optional key is safer than a wrong option
  string. If import complains, add it with the value your own export shows.
- The `Statistic.<Name> : <value>` line and one `DynamicEvidenceColumnSchema` per name are
  proven by the Citrix export. **Two statistics from one script run is not** — every proven
  component emits one. SolarWinds' page for the monitor states the limit is ten pairs, so two
  should be fine, but if `EphemeralInUse` never populates, split component 1 into two
  components running the same script.

**Not verified at all:**

- Import of this exact file through `ImportTemplate` or the console, because no SolarWinds
  server was reachable when it was written. The first import is the test.
- The Windows Event Log component's setting keys in the file format. No export in this
  repository contains one, which is why it is documented as a console step above instead of
  being guessed into the XML, where a wrong key would fail the whole import.

## See also

- [sam-templates.md](sam-templates.md) — the file format this is built to
- [sam-citrix-hypervisor-template.md](sam-citrix-hypervisor-template.md) — the other template
  in this repository, and the real export both are shaped against
- [sam.md](sam.md) — assigning a template and testing components

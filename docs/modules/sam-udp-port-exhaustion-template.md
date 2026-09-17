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
it with the native `PerformanceCounter` components that show a burst as it happens, and two
`EventLog` components that go Down the poll after Windows logs event 4266 (UDP) or 4231 (TCP).

Read [sam-templates.md](sam-templates.md) first for the `.apmtemplate` shape. This file is
built against a real 2026.4 export of SolarWinds' own *Server Clock Drift (PowerShell)*
template (two `PowerShell`, 25 `PerformanceCounter`) and a console-built export holding four
`EventLog` components, one per status mode. Every setting key, its `Required` flag, its
`ValueType` and its order, the threshold and dynamic-column blocks, and the template trailer
are copied from those exports; [sam-templates.md](sam-templates.md#a-fifth-sample-the-powershell-and-performancecounter-key-sets)
records what they settled.

## Why a script and not a counter

The candidates, against the SAM component types:

| Signal | SAM type that could carry it | Verdict |
| --- | --- | --- |
| Ports in use as a fraction of the range | none native — no Windows performance counter or WMI class exposes the count of open UDP endpoints | `PowerShell` component reading `Get-NetUDPEndpoint` |
| Event 4266 or 4231 has fired | `EventLog` component | native; in the file |
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
| 1 | UDP Ephemeral Ports - Percent Used | `PowerShell` (Remote Host), argument `percent` | percent of the range in use | warn 70, critical 90 |
| 2 | UDP Ephemeral Ports - In Use | `PowerShell` (Remote Host), argument `count` | ports in use | warn 11 469, critical 14 746 (70 / 90 % of 16 384) |
| 3 | UDPv4 - Datagrams/sec | `PerformanceCounter` | rate | unset; baseline |
| 4 | UDPv4 - Datagrams No Port/sec | `PerformanceCounter` | rate | unset; baseline |
| 5 | UDPv4 - Datagrams Received Errors | `PerformanceCounter`, `CountAsDifference` | errors per poll | unset; baseline |
| 6 | TCPv4 - Connections Established | `PerformanceCounter` | count | unset; baseline |
| 7 | System - Tcpip 4266 UDP port exhaustion | `EventLog`, `StatusSetting` Down | matching events in the last 1.5 polls | Down on any match |
| 8 | System - Tcpip 4231 TCP port exhaustion | `EventLog`, `StatusSetting` Down | matching events in the last 1.5 polls | Down on any match |

Components 1 and 2 run the same script; the argument in `ScriptArguments` picks which number
it reports, the way SolarWinds' own clock-drift template passes its time server. One value per
component is the only output shape a real export shows, so that is the shape used. The
counters' thresholds are "unset" the way the platform writes it, `double.MaxValue` in both
levels with `ComputeBaseline` on, so after the platform's baseline window (seven days of data)
the baseline-derived levels apply until you set your own.

The script is also shipped standalone as
[scripts/sam-templates/windows-udp-port-exhaustion.ps1](../../scripts/sam-templates/windows-udp-port-exhaustion.ps1)
so it can be run by hand on a suspect host. With `percent` (the default) it prints:

```
Message: 0.14% of the UDP dynamic range (49152-65535, 16384 ports) in use. Top: svchost(7668)=6, chrome(2628)=4, svchost(4480)=3, svchost(4220)=2, dasHost(5868)=2
Statistic: 0.14
```

and with `count`:

```
Message: 23 of 16384 ephemeral UDP ports (49152-65535) in use; 43 UDP endpoints total. Top: svchost(7668)=6, chrome(2628)=4, svchost(4480)=3, svchost(4220)=2, dasHost(5868)=2
Statistic: 23
```

`Message:` and `Statistic:` with no name suffix is the pair SolarWinds' own PowerShell
templates emit, matched by the two dynamic columns both named `Statistic` (one `String`, one
`Numeric`) that a real export carries on every `PowerShell` component.

The script reads the range from `netsh int ipv4 show dynamicport udp` rather than assuming
the default, counts only endpoints whose local port falls inside that range (listening
services on fixed ports below it are not exhaustion), and names the five processes holding the
most. It exits `0` below 70 %, `2` at 70 %, `3` at 90 %, and `1` if it could not read the
table, so the component's own status tracks the number even before a threshold is edited.

The 70 / 90 levels are a starting point. A host that legitimately runs a DNS server, a SIP
proxy or a scanner will sit higher; set the warning a comfortable margin above what that host
shows at its busiest.

## The event log components

Components 7 and 8 are Windows Event Log Monitors with `LogName` = `Custom`, `LogNameFilter` =
`System`, `EntrySource` = `Tcpip`, `EntryIDType` = `IncludeIDs` with the one id, `EntryType` =
`Warning` (the level Windows assigns to both events, read from the provider's manifest on a
Windows 11 host), `EntryMatch` = `Custom`, `FetchingMethod` = `Wmi`, `NumberOfFrequencies` =
`1.5`, and `StatusSetting` = `Down`. That last one is the console's "If a match is found in a
polling period, component is: Down". The statistic is the count of matching events in the
window, so it reads `0` in normal operation and the component turns Down the poll after a
4266 lands, then returns to Up once the event ages out of the 1.5-interval window.

The other three `StatusSetting` values the platform writes, all seen in a real export, are
`Up` (a match keeps the component Up, and the count is thresholded instead), `EventsBased`
(status follows the matched events' own levels) and `EventCountBased` (status follows the
count against the thresholds). `Down` is the right one here because a single 4266 is already
the failure.

Because event 4266 fires only when the range is already at 100 %, these two components are
the confirmation; component 1 is the early warning.

## Assigning it

The `PowerShell` component needs a credential that can open a WinRM session on the target and
has rights to read the socket table, which any local administrator has. WinRM must be listening
(`winrm quickconfig` on the target if it is not), and TCP `5985` must be open from the poller.
The `PerformanceCounter` and `EventLog` components use whatever fetching method the node
already polls with and inherit the node credential.

Test with `StartTestComponents` before assigning broadly, as
[sam-templates.md](sam-templates.md#test-before-you-assign) describes.

## Finding the culprit once it fires

The `Message:` line names the processes. When the top entry is `svchost`, the PID
in parentheses resolves to a service group with:

```powershell
tasklist /svc /fi "PID eq <pid>"
```

The range fills in a burst, not a drift, so a poll every five minutes can miss the peak
entirely; the six 4266 events that prompted this template each landed between polls that
showed under 1 %. For a host that has already exhibited the fault, drop `__Frequency` on
component 1 to `60` until the process is identified, then restore it.

## What is verified and what is not

**Verified against a real export (SolarWinds' *Server Clock Drift (PowerShell)* template,
exported from a 2026.4 server on 2026-09-17):**

- The `PowerShell` component: all thirteen setting keys, their order, `Required` flags and
  `ValueType`s; the empty `<Thresholds />`; the two `DynamicEvidenceColumnSchema` entries
  (`String` then `Numeric`, both named `Statistic`, the `String` one with an empty
  `<DataTransform />`); the trailer with an empty `ApplicationItemType` and a nil
  `ComponentCategoryName`.
- The `PerformanceCounter` component: all eighteen setting keys the same way, including the
  four `__DataTransform*` keys, `_BB_CanBeDisabled`, `FeatureNameRegex`, `SkipFallback`,
  `PreferredPollingMethod` = `Default` and `WinRmAuthenticationMechanism` = `Negotiate`; the
  `Thresholds` block keyed `StatisticData`; an empty `<DynamicColumnSettings />`.
- The template trailer: `Tags` as `TagInfo` entries, nil `CustomApplicationType` and `ViewXml`,
  `Version` `6.2.774.0`, the structured `ModuleVersion`; and that **no component carries
  `__Frequency` or `__Timeout`**. An earlier version of this file wrote both on every
  component, which is the most likely reason its import failed.
- A structural diff of every component in this file against the matching real component,
  ignoring only ids, names, labels and values, is empty.

**Verified on a real host (Windows 11 Pro 26200, 2026-09-17):**

- The script's output in both modes, its exit codes and its range detection.
- That the `UDPv4` and `TCPv4` counter names in components 3 to 6 exist by those exact
  names, from `Get-Counter -ListSet`.

**Verified by import (2026.4 server, 2026-09-17):**

- The six-component version of this file imports as-is through the console, and all six
  components poll Up on assignment. That confirms `ExecutionMode` = `RemoteHost` as the string
  the platform accepts for the console's "Remote Host", and that two `PowerShell` components
  running one script with different `ScriptArguments` is a working shape.

**Verified against a second real export (a console-built template with four `EventLog`
components, same server, same day):**

- The `EventLog` component: all 26 setting keys, their order, `Required` flags and
  `ValueType`s, including `NumberOfFrequencies` as the file's only `Double`; the `Thresholds`
  block keyed `StatisticData`; an empty `<DynamicColumnSettings />`. The four `StatusSetting`
  values (`Down`, `Up`, `EventsBased`, `EventCountBased`), two `EntryType` values
  (`Information`, `Error`), three include/exclude operations (`Match`, `Keywords`, `Disable`),
  and `LogName` = `Custom` with the log's name in `LogNameFilter`.
- A structural diff of components 7 and 8 against a real `EventLog` component, ignoring only
  ids, names and values, is empty.

**Inferred, one value:**

- `EntryType` = `Warning`. The real export shows `Information` and `Error`; Windows assigns
  both events the Warning level, and `Warning` follows the same naming. If the imported
  component shows a different event type in the console, set it there and export to learn
  the string.

**Not yet verified:**

- Import of the eight-component file. The six-component version imported; components 7 and 8
  are new. Report the result either way.
- What each component reports once the range actually fills. The 70 / 90 thresholds, the
  exit codes and the event-log Down transition have only been exercised against a host
  sitting under 1 %.

## See also

- [sam-templates.md](sam-templates.md) — the file format this is built to
- [sam-citrix-hypervisor-template.md](sam-citrix-hypervisor-template.md) — the other template
  in this repository, and the real export both are shaped against
- [sam.md](sam.md) — assigning a template and testing components

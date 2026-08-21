# UDT: User Device Tracker

User Device Tracker exists to answer one question: **where is this device plugged in?**

Somebody hands you a MAC address, an IP address or a hostname from a security alert, a
DHCP log or a help desk ticket, and you need to know which switch and which port it is on,
right now or at some point last Tuesday. Without UDT that is a walk through ARP caches and
bridge tables on every access switch. With UDT it is one query, because UDT does that walk
for you on a schedule and keeps the answers.

The mechanism is worth understanding because it explains the entity model. UDT polls each
monitored switch for its **bridge forwarding table**, which maps MAC addresses to physical
ports. It polls routers for their **ARP tables**, which map IP addresses to MAC addresses.
It resolves those IP addresses in **DNS** to get hostnames. Optionally it reads Active
Directory to map logged-on **users** to IP addresses. Then it stitches the four together:
hostname to IP to MAC to port to switch. Each of those four links is a separate entity with
its own timestamps, and each one is stored twice, once as "current" and once as "history".

## Namespaces and how many entities

UDT contributes **85 entities**, all under `Orion.UDT.`.

```bash
python3 tools/schema_query.py find UDT
python3 tools/schema_query.py show Orion.UDT.Port
python3 tools/schema_query.py verbs --entity Orion.UDT.Port
```

They group like this:

| Family | Entities | What is in it |
|---|---|---|
| Endpoints and correlation | 29 | `Orion.UDT.Endpoint`, `Orion.UDT.AllEndpoints`, the `IPAddress`, `DNSName` and `PortToEndpoint` current and history pairs, the MAC info views |
| Ports | 21 | `Orion.UDT.Port` and its usage, capacity, history, display and rule entities |
| Rogue and change alerts | 9 | `RogueMACAlert`, `RogueIPAlert`, `RogueDNSAlert`, `RogueEmptyDNSAlert`, `RogueEndpoints`, `EmptyDNSRogue`, `NewMACAlert`, `NewMACVendorAlert`, `MovedMACAlert` |
| Users | 9 | `Orion.UDT.User`, `UserToIPAddress` current and history, `UserHistory`, `UserLastActivity` |
| Topology and inventory | 7 | `CdpEntry`, `LldpEntry`, `VLAN`, `VLANDevice`, `Vrf`, `OUIReport`, `OUISummary` |
| Watch lists | 6 | `WatchList`, `WatchListPresent`, `WatchListAggregated` and three `Latest...ForWatchID` views |
| Operations | 4 | `Job`, `Setting`, `NodeCapability`, `NodeCapabilityDashboard` |

Only two of the 85 are writable and only two carry verbs, both of them `Orion.UDT.Port`.
Everything else is read-only, and most of it is a view over the same handful of underlying
tables shaped for a particular console resource. That is why the entity count is high and
the useful entity count is low.

## The current and history pattern

This is the structural idea in UDT and it repeats four times. For each kind of association,
there are two entities with almost the same columns:

| Association | Current | History |
|---|---|---|
| MAC to switch port | `Orion.UDT.PortToEndpointCurrent` | `Orion.UDT.PortToEndpointHistory` |
| IP to MAC | `Orion.UDT.IPAddressCurrent` | `Orion.UDT.IPAddressHistory` |
| Hostname to IP | `Orion.UDT.DNSNameCurrent` | `Orion.UDT.DNSNameHistory` |
| User to IP | `Orion.UDT.UserToIPAddressCurrent` | `Orion.UDT.UserToIPAddressHistory` |

The difference between the two halves of each pair is one column. **Current entities have
`FirstSeen` and no `LastSeen`**, because the association is still true and "last seen" would
be now. **History entities have both `FirstSeen` and `LastSeen`**, and the pair is a closed
interval during which the association held.

That gives you the rule for choosing between them, and it is not the obvious one. "Where is
this device now" is a `Current` query. "Where was this device at 14:00 last Tuesday" is a
`History` query with `FirstSeen <= @when AND LastSeen >= @when`. And "everywhere this device
has ever been" needs both, because the connection that is live right now is in `Current`
only and will not appear in `History` until it ends.

`Orion.UDT.PortHistoryCurrent` and `Orion.UDT.PortHistoryHistory` are a fifth pair on the
same pattern, denormalised down to `MACAddress`, `IPAddress` and `DNSName` on one row for
the port history resource.

## The correlation chain

Four entities and three joins get you from a name to a port.

```
Orion.UDT.DNSNameCurrent      hostname  ->  IP address
        |  (IPAddressID)
Orion.UDT.IPAddressCurrent    IP address ->  endpoint (a MAC)
        |  (EndpointID)
Orion.UDT.Endpoint            the MAC itself, first seen, vendor, rogue flag
        |  (EndpointID)
Orion.UDT.PortToEndpointCurrent   endpoint -> port, with VLAN
        |  (PortID)
Orion.UDT.Port                the physical switch port
        |  (NodeID)
Orion.Nodes                   the switch
```

**`Orion.UDT.Endpoint` is the anchor.** It is one row per MAC address UDT has ever seen, and
it is deliberately small: `EndpointID`, `MACAddress`, `FirstSeen`, `LastUpdate`, `Rogue` and
`Vendor`. Everything else about that device hangs off `EndpointID`. `Vendor` is resolved
from the OUI, the first three bytes of the MAC, which is how UDT can tell you a device is
probably a printer without ever talking to it.

Navigation makes the chain shorter than the joins suggest. `Orion.UDT.Endpoint` navigates
to `Orion.UDT.IPAddressCurrent` (`IPAddresses`), `Orion.UDT.IPAddressHistory`
(`IPAddressesHistory`), `Orion.UDT.PortToEndpointCurrent` (`Ports`) and
`Orion.UDT.PortToEndpointHistory` (`PortsHistory`). `Orion.UDT.IPAddressCurrent` navigates
on to `Orion.UDT.DNSNameCurrent` (`DNSNames`), to the users on that address (`Users`), and
to the router that held the ARP entry (`RouterNodes`, reaching `Orion.Nodes`, and
`RouterPorts`, reaching `Orion.UDT.Port`).

**`Orion.UDT.AllEndpoints` is the shortcut.** It is a denormalised view that has already
done the whole chain: `MACAddress`, `MACVendor`, `IPAddress`, `HostName`, `ConnectedTo` (the
switch name), `PortName`, `PortNumber`, `VLAN`, `ConnectionType`, `ConnectionTypeName`,
plus `NodeID` and `PortID` for joining onward. For the everyday "where is this thing" answer
it is the entity to use, and the rest of the chain is for when you need timestamps or
history that the view does not carry.

`Orion.UDT.RoutingEndpoints` is a one-column list of `EndpointID` values belonging to
routing devices, which is how the console filters out the router MACs that appear on every
uplink.

## Ports

**`Orion.UDT.Port` is a physical switch port**, and it is not an NPM interface. That
distinction trips people constantly. `Orion.NPM.Interfaces` is a polled interface with
traffic counters, errors and utilization, and it exists because you want a graph.
`Orion.UDT.Port` is a port UDT reads the forwarding table from, and it exists because you
want to know what is plugged into it. A given physical port on a switch can appear in both,
under different ids, and there is no navigation property between them. See
[npm.md](npm.md) for the interface side.

`Orion.UDT.Port` is the only UDT entity with a real platform identity. It inherits
`System.Entity` then `System.DashboardEntity` then `System.ManagedEntity`, which means it
gets `Status`, `StatusDescription`, `DisplayName`, `Uri`, and the maintenance columns
`UnManaged`, `UnManageFrom` and `UnManageUntil` on top of the 22 it declares itself.

| Property | Type | Notes |
|---|---|---|
| `PortID` | `System.Int32` | Primary key |
| `NodeID` | `System.Int32` | The switch, matching `Orion.Nodes.NodeID` |
| `PortIndex` | `System.Int32` | The SNMP ifIndex. `ORDER BY PortIndex` gives physical order; `ORDER BY Name` gives `Gi1/0/10` before `Gi1/0/2` |
| `Name`, `PortDescription` | `System.String` | The port's name and its configured description |
| `MACAddress` | `System.String` | The port's **own** MAC, not the MAC of anything attached |
| `PortType` | `System.Int16` | IANA interface type |
| `Speed` | `System.Double` | |
| `Duplex`, `TrunkMode` | `System.Byte` | See the values below |
| `OperationalStatus`, `AdministrativeStatus` | `System.Int16` | See the values below |
| `IsMonitored` | `System.Boolean` | Whether UDT reads this port. This is the licence-consuming flag |
| `IsExcluded` | `System.Boolean` | Excluded by a monitored-port rule |
| `IgnorePortRules` | `System.Boolean` | This port ignores the rules and keeps whatever `IsMonitored` you set |
| `IsMissing` | `System.Boolean` | The port was there last poll and is not there now |
| `StatusLED`, `ModernIcon`, `DetailsUrl`, `Flag`, `OrionIdPrefix`, `OrionIdColumn` | | Presentation |

The status and mode values are documented by SolarWinds on the
[UDT vNext API](https://solarwinds.github.io/OrionSDK/docs/udt-vnext-api/) page as part of
the create contract:

| Column | Values |
|---|---|
| `OperationalStatus` | 1 Up, 2 Down, 3 Testing, 4 Unknown, 5 Dormant, 6 NotPresent |
| `AdministrativeStatus` | 0 Unknown, 1 Up, 2 Down, 3 Testing |
| `Duplex` | 0 Unknown, 1 FullDuplex, 2 HalfDuplex, 3 Disagree, 4 AutoNegotiate |
| `TrunkMode` | 0 Unknown, 1 Trunking, 2 NonTrunking |
| `PortType` | 0 to 258 and 555 are accepted; the default is 6 |

`AdministrativeStatus = 1` with `OperationalStatus = 2` is the important combination: the
port is enabled and nothing is plugged into it. That is the definition of a free port, and
it is what a port capacity report counts.

`Orion.UDT.Port` navigates to `Orion.Nodes` (`Node`), to the endpoints on it
(`Endpoints` and `EndpointsHistory`), to the addresses routed through it (`IPAddresses`,
`IPAddressesHistory`), to its VLANs (`PortVLANs`) and to `Orion.UDT.AllEndpoints`
(`AllEndpoints`). `Orion.Nodes` navigates back through `Ports`.

### Which ports UDT monitors

UDT does not monitor every port it finds, because ports are licensed. **`Orion.UDT.Port.IsMonitored`**
is the switch, and **`Orion.UDT.MonitoredPortRule`** holds the rules that set it
automatically: `PropertyName`, `PropertyValue` and `MatchType`. A port with
`IgnorePortRules = TRUE` keeps whatever you set by hand; `IsExcluded = TRUE` means a rule
excluded it. `Orion.UDT.MonitoredPortsCount` and `Orion.UDT.PortCapacity` are the count and
percentage views behind the licence dashboards.

`Orion.UDT.UnusedPorts` is the report that pays for the module: ports with a `DaysUnused`
count, joined to their switch, which is how you find out that the access layer you were
about to expand is 40 percent idle. Note that `DaysUnused` is a `System.String`, not a
number, so it does not sort or compare numerically.

`Orion.UDT.PortUsage` and its `.Daily`, `.Hourly` and `.Detail` rollups hold
`AvgPortCount` and `AvgActivePortCount` per node over time. Those are ordinary Orion
statistics rollups, so time-bound every query against them.

## The other entities that carry the whole load

Beyond the chain and the ports, five denormalised views do most of the real work, and it is
worth knowing which one has which columns because their names are nearly identical.

**`Orion.UDT.MACAddressInfo`** is 30 columns per MAC per port, including `NodeName`,
`PortName`, `UserName`, `HostName`, `IPAddress`, `MACVendor`, `ClientSSID`, `IsWireless`,
`LastUpdate`, and crucially **`IsCurrent`**, which lets one query cover both current and
historic connections. It navigates to `Orion.Nodes` through `Node`.

**`Orion.UDT.MACCurrentInfo`** is 27 columns and looks like the same entity but is not. It
has **no `NodeName` and no `UserName`**, it uses `LastSeen` where `MACAddressInfo` uses
`LastUpdate`, and its port id column is `PortID` where `MACAddressInfo` spells it `PortId`.
`Orion.UDT.MACCurrentInformation` is a third variant with the same 27 columns.

If you write `NodeName` against `MACCurrentInfo` the query fails with a column error, which
is the good outcome. If you write `PortId` against it, you get a different error. Check the
entity you actually chose:

```bash
python3 tools/schema_query.py props Orion.UDT.MACAddressInfo --grep name
python3 tools/schema_query.py props Orion.UDT.MACCurrentInfo --grep name
```

**`Orion.UDT.DeviceInventory`** is the per-node device list: `MacAddress`, `Vendor`,
`IpAddress`, `DnsName`, `UserName` with `FirstName` and `LastName`, `PortName`,
`ConnectedTo`, `ConnectionType`, `EndpointType`, and both `NodeStatus` and
`PortOperationalStatus`. It is the only view that carries the user's real name next to the
device.

**`Orion.UDT.ConnectedMACsAndIPs`** is the per-port summary: `ConnectedMACs` and
`ConnectedIPs` counts with `NodeName`, `PortName` and `PortNumber`.
`Orion.UDT.PortToEndpointCounts` is the same idea keyed only on `PortID`, adding
`EndpointVlanCount` and `PortVlanCount`.

**`Orion.UDT.AllWirelessEndpoints`** is the wireless equivalent of `AllEndpoints`, keyed on
`APID` and `AccessPoint` rather than a switch port, and
`Orion.UDT.Wireless_Clients_Session_History_View_Data` holds the session history behind it.

## Rogue devices

A **rogue** in UDT is not a device that broke in. It is a device that is not on a list you
approved. The `Rogue` boolean appears on `Orion.UDT.Endpoint`, `Orion.UDT.EndpointIP` and
`Orion.UDT.EndpointDNS`, and there is a dedicated alert entity per identity type so that
the alerting engine has something with a NetObject to trigger on.

| Entity | Keyed on | Prefix | Columns beyond the common set |
|---|---|---|---|
| `Orion.UDT.RogueMACAlert` | `EndpointID` | `UE-MAC` | `MACAddress`, `Hostname`, `ConnectedTo`, `Port`, `PortID`, `DeviceID` |
| `Orion.UDT.RogueIPAlert` | `IPAddressID` | `UE-IP` | `IPAddress`, `NodeID` |
| `Orion.UDT.RogueDNSAlert` | `DNSNameID` | `UE-DNS` | `DNSName`, `NodeID` |
| `Orion.UDT.RogueEmptyDNSAlert` | `IPAddressID` | `UE-IP` | `DNSName`, `NodeID` |

All four carry `FirstSeen`, `LastUpdate`, `Rogue` and `DetailsUrl`. `Orion.UDT.RogueMACAlert`
is the richest of the four, and the only one that already names the switch and port, which
makes it the one to alert on if you have to pick one.

**`Orion.UDT.RogueEmptyDNSAlert` and `Orion.UDT.EmptyDNSRogue` are two different entities
for the same idea**: an IP address that is in use and has no reverse DNS name at all. The
alert version carries `NodeID` and `DetailsUrl`; the plain version carries the `IPAddress`
instead. On a network where everything is supposed to be registered, an address with no
name is a stronger signal than a name that is merely unfamiliar.

Three more entities detect change rather than membership:

- **`Orion.UDT.NewMACAlert`** fires on a MAC seen for the first time: `MACAddress`,
  `RawMAC`, `Vendor`, `FirstSeen`, `PortID`, `DeviceID` and the `IsNewMac` flag.
- **`Orion.UDT.NewMACVendorAlert`** fires on a vendor seen for the first time:
  `MacPrefix`, `Vendor`, `IsNewVendor`, `DeviceID`, `PortID`. This is the one that notices
  somebody brought their own access point.
- **`Orion.UDT.MovedMACAlert`** fires when a known MAC turns up somewhere else:
  `MACAddress`, `HasMoved`, `NodeID`. Only five columns, so pair it with
  `Orion.UDT.PortToEndpointHistory` to find out where it moved from.

`Orion.UDT.RogueEndpoints` is the generic version used by the console:
`NetobjectID`, `NetobjectType`, `LastSeen`, `WatchID` and `DisplayText`. The `WatchID`
column is the link into the watch list system.

Note that `IsNewMac`, `IsNewVendor`, `HasMoved` and `Rogue` are not all the same type.
`Rogue` and `IsNewMac` are `System.Boolean`; `IsNewVendor` and `HasMoved` are
`System.Int32`. Compare with `= TRUE` on the first pair and `= 1` on the second.

## Watch lists

A watch list is the opposite of a rogue list: a set of specific things you want to be told
about when they appear.

**`Orion.UDT.WatchList`** is the list itself, and it is small on purpose: `WatchID`,
`WatchItem` (the MAC, IP or hostname being watched), `WatchItemDisplay`, `WatchItemType`,
`WatchName` and a free-text `Note`. Both `WatchItem` and `WatchItemType` are strings here.

**`Orion.UDT.WatchListPresent`** is the flat answer: the same list plus a `Present` boolean
and a `NodeID`. This is the entity to alert on.

**`Orion.UDT.WatchListAggregated`** is the full answer: 27 columns joining the watch entry
to everything currently known about the item. `IsFound`, `IsActive`, `LastSeen`,
`MACAddress`, `IPAddress`, `DNSName`, `UserName`, `NodeName`, `PortName`,
`PortDescription`, `VlanID`, `IsWireless`, `APName`, `clSSID`, `ifSSID` and `VrfName`.
Note that its `WatchItemType` is a `System.Int32` while `Orion.UDT.WatchList.WatchItemType`
is a `System.String`, so do not carry a filter value between the two.

The three `Orion.UDT.Latest...ForWatchID` entities
(`LatestPortToEndpointHistoryForWatchID`, `LatestIPAddressHistoryForWatchID`,
`LatestDNSAddressHistoryForWatchID`) give the most recent historic association for a
watched item, which is how the console shows "last seen here" for something that is not
present now.

`Orion.UDT.WatchListPresent` carries the `UW` NetObject prefix.

## Users

If UDT is configured with Active Directory credentials it also tracks which account is
logged on to which address.

**`Orion.UDT.User`** is the directory record: `UserID`, `AccountSID`, `AccountName`,
`FirstName`, `LastName`, `Title`, `Department`, `Office`, `Company`, `Manager`,
`EmailAddressList`, `MemberOfList`, `Phone` and the postal address fields. It navigates to
`Orion.UDT.UserToIPAddressCurrent` (`IPAddresses`) and `...History`
(`IPAddressesHistory`).

**`Orion.UDT.UserToIPAddressCurrent`** and its history twin are the association:
`UserID`, `IPAddress`, `LogonDateTime` and `LogonCount`. From there, `IP` navigates to
`Orion.UDT.IPAddressCurrent`, which reaches the MAC and then the port. That is the full
"which port is this person's laptop on" chain, and it is four navigation hops.

`Orion.UDT.UserLastActivity` precomputes the last logon per user with `LastLogonDays`, and
`Orion.UDT.UserHistory` gives the logon history with a `DaysBeforeLogin` column that is,
like `UnusedPorts.DaysUnused`, a `System.String` rather than a number.

## Topology and inventory

`Orion.UDT.CdpEntry` and `Orion.UDT.LldpEntry` hold the neighbour tables UDT reads to work
out which ports are uplinks to other switches rather than access ports with devices on
them. CDP gives `NodeID`, `IfIndex`, `IpAddress`, `DeviceId` and `DevicePort`; LLDP gives
`LocalPortNumber`, `RemoteIfIndex`, `RemotePortId`, `RemotePortDescription`,
`RemoteSystemName` and `RemoteIpAddress`. `Orion.UDT.PortToPort`, `...Current` and
`...History` record the resulting switch-to-switch links as `Port1ID` and `Port2ID` pairs.

`Orion.UDT.VLAN` is per port (`PortID`, `VlanID`, `VlanName`) and navigates back to the
port through `VLANPort`. `Orion.UDT.VLANDevice` is the device-centric view of the same
thing. `Orion.UDT.Vrf` holds VRF names per node, which matters on a network where the same
IP address legitimately exists twice.

`Orion.UDT.OUIReport` and `Orion.UDT.OUISummary` break endpoints down by MAC prefix and
manufacturer, which is the fastest way to answer "how many Apple devices are on the guest
network" without touching a single device.

## Operations and polling health

**`Orion.UDT.NodeCapability`** is the entity to watch if UDT stops being right.
One row per node per capability: `Capability`, `Enabled`, `LastScan`, `LastSuccessfulScan`,
`LastScanResult`, `PollingIntervalMinutes`, `AddedManually`, `AverageScanDurationSec` and
`AveragingFactor`. It is hosted by `Orion.Nodes` and reachable from it through
`UDTCapabilities`.

`LastScan` moving while `LastSuccessfulScan` stands still is the signature of a switch UDT
can reach but cannot read, which is usually an SNMP community that lacks the VLAN context
needed for the bridge table. That failure is silent from the query side: the port rows stay
where they were and simply stop updating.

`Orion.UDT.Job` records `NodeID`, `JobType`, `JobLastRun` and `JobLastResult`.
`Orion.UDT.Setting` holds module settings as `SettingName`, `SettingValue` and
`DefaultValue`. `Orion.UDT.NodeCapabilityDashboard` carries the module's only non-port
verb, `PollNow(nodeIdJobType)`, which takes a single string argument combining the node id
and the job type and requires the `manageNodes` right.

## Verbs

UDT declares **three verbs in total**, which is the smallest verb surface of any major
module and reflects what UDT is: a reader, not a controller.

| Verb | Right | Parameters in the extracted schema |
|---|---|---|
| `Orion.UDT.Port.AdministrativeShutdown` | `manageNodes` | none recorded |
| `Orion.UDT.Port.AdministrativeEnable` | `manageNodes` | none recorded |
| `Orion.UDT.NodeCapabilityDashboard.PollNow` | `manageNodes` | `nodeIdJobType` (string) |

Everything else UDT does through the API it does through CRUD on `Orion.UDT.Port`.

### Port shutdown, and how disruptive it is

`AdministrativeShutdown` **administratively disables a physical switch port**. It is not a
UDT bookkeeping operation. UDT logs in to the switch and shuts the interface, and anything
plugged into that port loses its network connection immediately. If the port happens to be
an uplink or a trunk, everything downstream of it goes with it. There is no undo beyond
calling `AdministrativeEnable`, and if the port you just shut was the path to the switch
itself, that call will not reach it.

This is the most destructive single call in the module and one of the more destructive in
the platform, so treat it accordingly: confirm the port, confirm what is on it, and confirm
it is not a trunk, before you invoke anything.

**The signature is not in the extracted schema.** Both verbs came from the rendered schema
pages, which list the verb name and nothing else, and neither appears in the 2026.2 Swagger
contract, so `data/schema/2026.2/verbs.json` records an empty parameter list for both. What
we do have is SolarWinds' own sample script,
[`UDT.PortShutdown.ps1`](https://github.com/solarwinds/OrionSDK/blob/master/Samples/PowerShell/UDT.PortShutdown.ps1),
which calls it like this:

```powershell
Invoke-SwisVerb $swis Orion.UDT.Port AdministrativeShutdown @( $nodeID, [int[]]@( $portID ) )
```

So the practical contract is **two positional arguments: the node id as an integer, then an
array of port ids**. That is consistent with the batch shape used elsewhere in the platform,
and `AdministrativeEnable` takes the same pair. Treat this as **verified from SolarWinds'
sample, not from the schema**, and confirm it on your own server before automating it:

```sql
SELECT Position, Name, Type, IsOptional
FROM Metadata.VerbArgument
WHERE EntityName = 'Orion.UDT.Port' AND VerbName = 'AdministrativeShutdown'
ORDER BY Position
```

An empty result there means your server does not describe the arguments either, which is
the case the sample exists to cover.

The sample script takes a node id and a port id and shuts the port with no checks at all.
Here is the same operation with the checks that make it safe to run from something other
than a prompt you are watching:

```powershell
# Shut one UDT port after showing what is attached to it. Requires manageNodes.
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
    [Parameter(Mandatory)][int]$PortID,
    [string]$OrionHost = 'orion.example.com'
)

Import-Module SwisPowerShell
$swis = Connect-Swis -Hostname $OrionHost -Credential (Get-Credential)

$port = Get-SwisData $swis @"
SELECT TOP 1
    p.PortID,
    p.NodeID,
    p.Name,
    p.PortDescription,
    p.TrunkMode,
    p.OperationalStatus,
    p.AdministrativeStatus,
    p.Node.Caption AS SwitchName
FROM Orion.UDT.Port p
WHERE p.PortID = @portId
"@ @{ portId = $PortID }

if (-not $port) { throw "No UDT port with PortID $PortID." }

# TrunkMode 1 is Trunking. Shutting a trunk takes out everything behind it.
if ($port.TrunkMode -eq 1) {
    throw "$($port.SwitchName) $($port.Name) is a trunk. Refusing to shut it."
}

$attached = Get-SwisData $swis @"
SELECT
    e.MACAddress,
    e.MACVendor,
    e.IPAddress,
    e.HostName,
    e.VLAN
FROM Orion.UDT.AllEndpoints e
WHERE e.PortID = @portId
"@ @{ portId = $PortID }

Write-Host "$($port.SwitchName) $($port.Name)  ($($port.PortDescription))"
Write-Host "Currently attached: $($attached.Count) endpoint(s)"
$attached | Format-Table -AutoSize

$target = "$($port.SwitchName) port $($port.Name)"
if ($PSCmdlet.ShouldProcess($target, 'AdministrativeShutdown')) {
    Invoke-SwisVerb $swis 'Orion.UDT.Port' 'AdministrativeShutdown' `
        @($port.NodeID, [int[]]@($PortID)) | Out-Null
    Write-Host "Shut $target. Re-enable with AdministrativeEnable @($($port.NodeID), @($PortID))."
}
```

`-WhatIf` prints the target and attached endpoints without invoking anything, and
`ConfirmImpact = 'High'` means an interactive run prompts by default. Both matter for a
call whose failure mode is an outage.

The other reason to list the endpoints first is that a port with several MACs on it is
usually not a workstation. It is an unmanaged desk switch, a hypervisor, an IP phone with a
PC behind it, or an uplink UDT has not classified. Query 8 below finds those in advance.

### Creating, updating and deleting a port

`Orion.UDT.Port` supports full CRUD under `manageNodes` or `admin`, and SolarWinds
documents the contract on the
[UDT vNext API](https://solarwinds.github.io/OrionSDK/docs/udt-vnext-api/) page. This is for
ports UDT cannot discover on its own, on a device it cannot poll properly.

Required on create: `NodeID` (which must already exist in the nodes table), `PortIndex`,
`Name` (255 characters maximum) and `MACAddress` (12 hex characters, optionally separated by
`:` or `-`). Optional with defaults: `IsMonitored` true, `PortType` 6, `Speed` 0, `Duplex`
0, `TrunkMode` 0, `OperationalStatus` 1, `AdministrativeStatus` 0, `IgnorePortRules` false,
`Flag` 0, `IsExcluded` false, and a `PortDescription` of up to 255 characters.

**On update, only `IsMonitored` may be changed.** That is SolarWinds' own statement, and it
makes `Orion.UDT.Port` a create-and-delete entity in practice. The URI form is nested under
the node:

```powershell
# Stop monitoring a port, which frees the licence it consumes.
Set-SwisObject $swis `
    -Uri 'swis://localhost/Orion/Orion.Nodes/NodeID=42/Ports/PortID=1701' `
    -Properties @{ IsMonitored = 0 }

# Delete a manually created port.
Remove-SwisObject $swis `
    -Uri 'swis://localhost/Orion/Orion.Nodes/NodeID=42/Ports/PortID=1701'
```

Note that the URI segment is `Ports`, the navigation property on `Orion.Nodes`, not the
entity name. See [../swis/uris.md](../swis/uris.md).

## Worked queries

Every query below was validated against the 2026.2 schema with
`python3 tools/validate_swql.py`. Time bounds are bound parameters rather than SWQL
expressions, for the reason under [Gotchas](#gotchas).
[`../../scripts/swql/12-udt-and-storage.swql`](../../scripts/swql/12-udt-and-storage.swql)
has the basic lookups; these go further.

### 1. Where is this MAC address plugged in

The question UDT exists to answer, in its shortest form.

```sql
SELECT
    e.MACAddress,
    e.MACVendor,
    e.IPAddress,
    e.HostName,
    e.ConnectedTo AS SwitchName,
    e.PortName,
    e.PortNumber,
    e.VLAN,
    e.ConnectionTypeName,
    e.NodeID,
    e.PortID
FROM Orion.UDT.AllEndpoints e
WHERE e.MACAddress = @macAddress
```

`Orion.UDT.AllEndpoints` has already done the correlation, so this needs no joins.
`ConnectionTypeName` is the readable form of `ConnectionType` and tells you whether the
answer is a wired port or a wireless association, which changes what you do next. Selecting
`NodeID` and `PortID` costs nothing and gives you the handles for a shutdown or a deeper
query.

The same query with `WHERE e.IPAddress = @ipAddress` or `WHERE e.HostName = @hostName`
answers the other two forms of the question, which is the whole value of the correlation.

### 2. The same answer with timestamps, through the chain

`AllEndpoints` does not carry `FirstSeen`, so when you need to know how long the device has
been there, go through the association entities.

```sql
SELECT TOP 20
    ep.MACAddress,
    ep.Vendor,
    pe.FirstSeen,
    pe.VlanID,
    pe.ConnectionType,
    pe.Port.Name AS PortName,
    pe.Port.PortDescription,
    pe.Port.Node.Caption AS SwitchName,
    pe.Port.Node.IPAddress AS SwitchIP
FROM Orion.UDT.PortToEndpointCurrent pe
JOIN Orion.UDT.Endpoint ep ON pe.EndpointID = ep.EndpointID
WHERE ep.MACAddress = @macAddress
ORDER BY pe.FirstSeen DESC
```

`pe.Port.Node.Caption` walks two navigation properties in one expression: from the
association to the port, then from the port to the switch. `TOP 20` rather than `TOP 1` is
deliberate, because a MAC genuinely can be current on more than one port at once when it is
seen on both an access port and an uplink.

### 3. Where has this device been

The history side of the same association. This is the query for the security ticket that
arrives three days after the event.

```sql
SELECT TOP 100
    ep.MACAddress,
    ph.FirstSeen,
    ph.LastSeen,
    ph.VlanID,
    ph.Port.Name AS PortName,
    ph.Port.Node.Caption AS SwitchName
FROM Orion.UDT.PortToEndpointHistory ph
JOIN Orion.UDT.Endpoint ep ON ph.EndpointID = ep.EndpointID
WHERE ep.MACAddress = @macAddress
  AND ph.LastSeen >= @startUtc
ORDER BY ph.LastSeen DESC
```

To ask where the device was at a specific moment rather than over a window, replace the
`LastSeen` filter with `ph.FirstSeen <= @when AND ph.LastSeen >= @when`. Remember that the
connection which is live right now is in `PortToEndpointCurrent` and not here, so a
complete answer needs both queries.

### 4. Everything known about one IP address

```sql
SELECT TOP 100
    ipc.IPAddress,
    ipc.FirstSeen,
    ipc.Endpoint.MACAddress,
    ipc.Endpoint.Vendor,
    ipc.DNSNames.DNSName,
    ipc.RouterNodes.Caption AS RouterName
FROM Orion.UDT.IPAddressCurrent ipc
WHERE ipc.IPAddress = @ipAddress
ORDER BY ipc.FirstSeen DESC
```

Three navigation properties from one entity: down to the MAC, sideways to the hostname, and
back to the router whose ARP table produced the mapping. `RouterNodes` is the one people
miss, and it matters when the same private address exists in two VRFs, because it tells you
which router believes this particular mapping.

### 5. Free ports on a switch, and how long they have been free

```sql
SELECT TOP 100
    u.Node.Caption AS SwitchName,
    u.Name AS PortName,
    u.PortDescription,
    u.DaysUnused,
    u.IpAddress AS SwitchIP
FROM Orion.UDT.UnusedPorts u
ORDER BY u.Caption, u.Name
```

`Orion.UDT.UnusedPorts` is precomputed, so this is far cheaper than deriving the same answer
from `Orion.UDT.Port`. Do not try to sort or filter numerically on `DaysUnused`: it is a
`System.String`.

For a live view rather than the precomputed one, ask `Orion.UDT.Port` directly. A port that
is administratively up and operationally down has nothing plugged into it:

```sql
SELECT TOP 200
    p.Node.Caption AS SwitchName,
    p.Name AS PortName,
    p.PortDescription,
    p.PortIndex,
    p.OperationalStatus,
    p.AdministrativeStatus,
    p.Speed,
    p.Duplex,
    p.TrunkMode,
    p.IsMonitored,
    p.IsMissing,
    p.IsExcluded
FROM Orion.UDT.Port p
WHERE p.Node.Caption = @switchName
ORDER BY p.PortIndex
```

`ORDER BY p.PortIndex` rather than `p.Name`, because port names sort as text and put
`Gi1/0/10` before `Gi1/0/2`.

### 6. Port licence consumption per switch

```sql
SELECT
    p.Node.Caption AS SwitchName,
    COUNT(p.PortID) AS MonitoredPorts
FROM Orion.UDT.Port p
WHERE p.IsMonitored = TRUE
  AND p.IsExcluded = FALSE
GROUP BY p.Node.Caption
ORDER BY COUNT(p.PortID) DESC
```

UDT is licensed by monitored port, so this is the query that explains where the licence
went. Compare it against `Orion.UDT.MonitoredPortsCount` for the platform's own total, and
check `Orion.UDT.MonitoredPortRule` if a switch is consuming more ports than you expected.

### 7. Rogue MAC addresses, already located

```sql
SELECT TOP 100
    r.MACAddress,
    r.Hostname,
    r.FirstSeen,
    r.LastUpdate,
    r.ConnectedTo AS SwitchName,
    r.Port AS PortName,
    r.PortID,
    r.DeviceID
FROM Orion.UDT.RogueMACAlert r
WHERE r.Rogue = TRUE
ORDER BY r.LastUpdate DESC
```

`Orion.UDT.RogueMACAlert` is the only rogue entity that already names the switch and port,
which turns a list of unfamiliar MACs into a list of desks to walk to. `PortID` is what you
would pass to `AdministrativeShutdown`, though read
[the warning](#port-shutdown-and-how-disruptive-it-is) before you do.

Newly seen MACs, as opposed to unapproved ones, are a separate entity:

```sql
SELECT TOP 100
    nm.MACAddress,
    nm.RawMAC,
    nm.Vendor,
    nm.FirstSeen,
    nm.PortID,
    nm.DeviceID,
    nm.IsNewMac
FROM Orion.UDT.NewMACAlert nm
WHERE nm.IsNewMac = TRUE
  AND nm.FirstSeen >= @startUtc
ORDER BY nm.FirstSeen DESC
```

### 8. Ports carrying more devices than they should

```sql
SELECT
    e.ConnectedTo AS SwitchName,
    e.PortName,
    e.PortID,
    COUNT(e.MACAddress) AS MACCount
FROM Orion.UDT.AllEndpoints e
GROUP BY e.ConnectedTo, e.PortName, e.PortID
HAVING COUNT(e.MACAddress) > 4
ORDER BY COUNT(e.MACAddress) DESC
```

An access port with one or two MACs is a workstation, possibly with a phone. Four or more
means an unmanaged desk switch somebody brought in, a hypervisor, or an uplink UDT has not
recognised as one. All three are worth knowing about, and all three are reasons never to
shut a port without looking at it first. Selecting `PortID` gives you the handle to
investigate.

`Orion.UDT.ConnectedMACsAndIPs` answers the same question from a precomputed view if you
want it cheaper.

### 9. Watch list hits

```sql
SELECT TOP 100
    w.WatchName,
    w.WatchItem,
    w.WatchItemType,
    w.IsFound,
    w.IsActive,
    w.LastSeen,
    w.MACAddress,
    w.IPAddress,
    w.DNSName,
    w.UserName,
    w.NodeName,
    w.PortName,
    w.IsWireless
FROM Orion.UDT.WatchListAggregated w
WHERE w.IsFound = TRUE
ORDER BY w.LastSeen DESC
```

`IsFound` says the watched item is somewhere on the network; `IsActive` says the connection
is live. Both are worth selecting, because "the laptop we are looking for was seen an hour
ago on port 14" and "it is on port 14 now" lead to different actions.

### 10. Which port is this person's machine on

```sql
SELECT TOP 100
    usr.AccountName,
    usr.FirstName,
    usr.LastName,
    usr.Department,
    ui.LogonDateTime,
    ui.LogonCount,
    ui.IPAddress,
    ui.IP.Endpoint.MACAddress AS MACAddress
FROM Orion.UDT.UserToIPAddressCurrent ui
JOIN Orion.UDT.User usr ON ui.UserID = usr.UserID
WHERE ui.LogonDateTime >= @startUtc
ORDER BY ui.LogonDateTime DESC
```

`ui.IP.Endpoint.MACAddress` walks from the user-to-address association to the address, then
to the endpoint. Add `WHERE usr.AccountName = @account` to answer it for one person.
`Orion.UDT.DeviceInventory` gives a flatter version of the same information per node if you
would rather not walk the chain.

### 11. Is UDT actually reading these switches

```sql
SELECT TOP 100
    n.Caption AS SwitchName,
    n.IPAddress,
    c.Capability,
    c.Enabled,
    c.LastScan,
    c.LastSuccessfulScan,
    c.LastScanResult,
    c.PollingIntervalMinutes,
    c.AverageScanDurationSec
FROM Orion.UDT.NodeCapability c
JOIN Orion.Nodes n ON c.NodeID = n.NodeID
WHERE c.Enabled = TRUE
ORDER BY c.LastSuccessfulScan
```

Run this before you trust anything else on this page. A gap between `LastScan` and
`LastSuccessfulScan` means UDT is trying and failing, and the port data for that switch is
as old as `LastSuccessfulScan`. Everything downstream, including rogue detection and watch
lists, is stale for that device and nothing in the data says so.

A rising `AverageScanDurationSec` on a large switch is the other thing to watch: it usually
means the bridge table has grown past what the poll interval allows for.

### 12. All MACs on one switch, current and historic in one pass

```sql
SELECT TOP 100
    m.NodeName,
    m.PortName,
    m.PortDescription,
    m.MACAddress,
    m.MACVendor,
    m.IPAddress,
    m.HostName,
    m.UserName,
    m.LastUpdate,
    m.IsWireless,
    m.IsCurrent,
    m.OperationalStatus,
    m.AdministrativeStatus
FROM Orion.UDT.MACAddressInfo m
WHERE m.NodeID = @nodeId
  AND m.IsCurrent = 1
ORDER BY m.PortName
```

`Orion.UDT.MACAddressInfo` is the widest of the MAC views and the only one carrying both
`NodeName` and `UserName`. Drop the `IsCurrent` filter to include historic connections, and
note that `IsCurrent` is a `System.Int32`, so compare it with `1` rather than `TRUE`. If you
switch this query to `Orion.UDT.MACCurrentInfo` it will fail, because that entity has
neither `NodeName` nor `UserName`.

## Gotchas

**`Orion.UDT.Port` is not `Orion.NPM.Interfaces`.** They describe the same physical thing
from different modules with different ids and no navigation property between them. UDT's
port is for finding out what is attached; NPM's interface is for traffic and errors.
Joining them requires matching `Orion.UDT.Port.PortIndex` to
`Orion.NPM.Interfaces.InterfaceIndex` on the same `NodeID`, which is an ifIndex match and
is only as stable as ifIndex is on that device.

**`AdministrativeShutdown` disables a real switch port.** Anything plugged into it drops off
the network immediately, and on a trunk everything behind it goes too. Its argument list is
not in the extracted schema; SolarWinds' own sample passes `@(nodeId, [int[]]@(portId))`.
Confirm on your server with `Metadata.VerbArgument` before automating it, and list what is
attached before you invoke it.

**Only `IsMonitored` can be updated on a port.** SolarWinds states this explicitly. Every
other property on `Orion.UDT.Port` is set at create time or discovered, so changing one
means delete and recreate.

**`Current` entities have no `LastSeen`.** `Orion.UDT.PortToEndpointCurrent`,
`IPAddressCurrent`, `DNSNameCurrent` and `UserToIPAddressCurrent` carry `FirstSeen` only.
Writing `LastSeen` against one of them fails. A complete history needs the `Current` row
plus the `History` rows, because the live association is not in `History` yet.

**Three MAC info entities with nearly the same name and different columns.**
`Orion.UDT.MACAddressInfo` has `NodeName`, `UserName`, `LastUpdate` and `PortId`.
`Orion.UDT.MACCurrentInfo` and `Orion.UDT.MACCurrentInformation` have neither `NodeName`
nor `UserName`, and use `LastSeen` and `PortID`. The lower-case `d` in `MACAddressInfo`'s
`PortId` is real. Look up the one you chose.

**Booleans that are not booleans.** `Orion.UDT.Endpoint.Rogue` and
`Orion.UDT.NewMACAlert.IsNewMac` are `System.Boolean`, so compare with `TRUE`.
`Orion.UDT.NewMACVendorAlert.IsNewVendor`, `Orion.UDT.MovedMACAlert.HasMoved`,
`Orion.UDT.MACAddressInfo.IsCurrent` and `Orion.UDT.MACAddressInfo.IsWireless` are
`System.Int32`, so compare with `1`.

**Two day-count columns are strings.** `Orion.UDT.UnusedPorts.DaysUnused` and
`Orion.UDT.UserHistory.DaysBeforeLogin` are `System.String`. They will not sort or compare
numerically, and a `> 30` filter on either does something surprising rather than something
useful.

**`WatchItemType` changes type between entities.** It is a `System.String` on
`Orion.UDT.WatchList` and `Orion.UDT.WatchListPresent`, and a `System.Int32` on
`Orion.UDT.WatchListAggregated`. Do not carry a filter value from one to the other.

**Two entities for empty reverse DNS.** `Orion.UDT.RogueEmptyDNSAlert` carries `NodeID` and
`DetailsUrl`; `Orion.UDT.EmptyDNSRogue` carries `IPAddress` instead. Same idea, different
columns, and the names are one word apart.

**`Orion.UDT.Port` has no NetObject prefix.** [`netobject-types.json`](../../data/reference/netobject-types.json)
records an empty prefix for it, with `Orion.Nodes` as its parent and `NodeID`, `PortID` and
`PortIndex` as its key properties. The rogue and watch entities do have prefixes (`UE-MAC`,
`UE-IP`, `UE-DNS`, `UW`, `UP`), which is what makes them alertable. See
[../reference/netobject-types.md](../reference/netobject-types.md).

**A MAC legitimately appears on more than one port.** It is on the access port it is plugged
into and on every uplink between there and the switch you polled. `Orion.UDT.RoutingEndpoints`
and the CDP and LLDP entities are how the console distinguishes them; a query that assumes
one row per MAC will be wrong on any network with more than one switch.

**Stale port data looks exactly like accurate port data.** If `Orion.UDT.NodeCapability`
shows `LastSuccessfulScan` well behind `LastScan`, everything UDT tells you about that
switch is from the last successful poll, and no column in the endpoint entities says so.
Check capability health before you act on a location.

**UDT is licensed per monitored port.** `IsMonitored` is the flag that consumes the licence
and `Orion.UDT.MonitoredPortRule` is what sets it automatically. A port that suddenly stops
appearing in results has usually been excluded by a rule rather than unplugged; check
`IsExcluded` and `IsMissing` before concluding anything physical.

**Do not build time windows with `GetUtcDate()` plus the `AddX` functions.** They compile to
T-SQL `DATEADD`, which is timezone blind, so the combination is wrong by your server's UTC
offset. Compute the bounds in the client and bind them, which is what the history queries
above do. See [../swql/date-and-time.md](../swql/date-and-time.md).

**Account limitations filter silently.** Two accounts running the same UDT query
legitimately get different switches, and nothing in the response says so. "The device is
not on the network" is a permissions hypothesis before it is a physical one.

## Related pages

- [README.md](README.md) for the module index and how to check what is installed.
- [ipam.md](ipam.md) for the other half of the address question: UDT says which port a
  device is on, IPAM says who the address belongs to.
- [npm.md](npm.md) for `Orion.NPM.Interfaces`, which is the same physical port seen as a
  traffic source rather than an attachment point.
- [../platform/modules.md](../platform/modules.md) for the whole-schema namespace map.
- [../swis/invoke-verbs.md](../swis/invoke-verbs.md) for positional arguments and the
  single-array-argument trap, which `AdministrativeShutdown` is an instance of.
- [../swis/crud.md](../swis/crud.md) and [../swis/uris.md](../swis/uris.md) for creating and
  updating ports.
- [../swis/metadata-introspection.md](../swis/metadata-introspection.md) for confirming the
  shutdown verb's arguments on a live server.
- [../swql/joins-and-navigation.md](../swql/joins-and-navigation.md) for the multi-hop
  navigation the correlation queries use.
- [../swql/date-and-time.md](../swql/date-and-time.md) for time-bounding the history
  entities.
- [../reference/netobject-types.md](../reference/netobject-types.md) for the `UE-MAC`,
  `UE-IP`, `UE-DNS`, `UW` and `UP` prefixes.
- [../reference/verb-index.md](../reference/verb-index.md) for the three UDT verbs.
- [../../scripts/swql/12-udt-and-storage.swql](../../scripts/swql/12-udt-and-storage.swql)
  for the basic lookup queries this page builds on.

## Official SolarWinds documentation

- [UDT vNext API](https://solarwinds.github.io/OrionSDK/docs/udt-vnext-api/), which
  documents the `Orion.UDT.Port` create, update and delete contract and the enumerated
  values for `Duplex`, `TrunkMode`, `OperationalStatus` and `AdministrativeStatus`
- [`UDT.PortShutdown.ps1`](https://github.com/solarwinds/OrionSDK/blob/master/Samples/PowerShell/UDT.PortShutdown.ps1),
  the only published example of calling `AdministrativeShutdown`
- [Orion SDK documentation index](https://solarwinds.github.io/OrionSDK/)

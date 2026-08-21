# NPM: Network Performance Monitor

Network Performance Monitor is the module that turns a monitored node into a monitored
*network*. The platform core already knows a node is up, how it responds to ping, how busy
its CPU is and how full its disks are. NPM adds everything about the paths in and out of it:
the interfaces and their traffic, the wireless infrastructure serving clients, the routing
adjacencies the device maintains, the multicast trees it participates in, arbitrary SNMP
values you decide to collect yourself, and the hop-by-hop path from a probe to a service.

NPM is the oldest module in the suite and it shows in the schema. It has more shapes for the
same idea than any other module, several generations of wireless entities live side by side,
and two families that once lived under `Orion.NPM.` have been moved out to namespaces of
their own. This page maps that out so you can pick the right entity the first time.

## Namespaces and how many entities

NPM's headline entities live under five prefixes. These counts are exact for the 2026.2
extraction and count every entity whose name begins with the prefix:

| Prefix | Entities | What is in it |
|---|---|---|
| `Orion.NPM.` | 86 | Interfaces and their statistics, universal device pollers, multicast routing, EnergyWise, fibre channel, switch stacks, VSANs |
| `Orion.Packages.Wireless.` | 19 | The current wireless model: controllers, access points, radios, clients, rogues, SSIDs, session history |
| `Orion.NetPath.` | 12 | Probes, services, service assignments, tests, traces, per-hop performance |
| `Orion.WirelessHeatMap.` | 11 | Floor plan heat maps, map points, client location, signal measurements |
| `Orion.Routing.` | 11 | Routers, neighbors, routing tables, VRFs, route and adjacency flap history |

That is **139 entities**. Two more families belong to NPM but sit outside those prefixes,
because they were moved rather than renamed:

| Prefix | Entities | What is in it |
|---|---|---|
| `Orion.F5.` | 24 | F5 BIG-IP monitoring, split into `Orion.F5.System.` (8), `Orion.F5.LTM.` (8), `Orion.F5.GTM.` (7) and `Orion.F5.Map.` (1) |
| `Orion.UCS.` | 8 | Cisco UCS chassis, blades, fabrics, and their fans and power supplies |

And one older wireless shape, `Orion.Wireless.` (14 entities), still exists alongside the
`Orion.Packages.Wireless.` family. See [Wireless](#wireless) for how to tell them apart.

The [netobject reference](../reference/netobject-types.md) attributes all of these to the
NPM module, including the F5 and UCS rows, which is the evidence for grouping them here.

Verify the grouping for yourself:

```bash
python3 tools/schema_query.py find Orion.Routing
python3 tools/schema_query.py find Orion.Packages.Wireless
python3 tools/schema_query.py show Orion.NPM.Interfaces
```

## Interfaces are the core entity

`Orion.NPM.Interfaces` is where most NPM work starts and where most of it ends. Every other
NPM entity either hangs off an interface, hangs off the node that owns the interfaces, or
describes something that flows through them.

| Fact | Value |
|---|---|
| Key property | `InterfaceID` (`System.Int32`) |
| NetObject prefix | `I`, so interface 42 is `I:42` |
| Owning node | `NodeID`, or the `Node` navigation property |
| Properties | 92 declared, plus inherited members from `System.ManagedEntity` and `System.Entity` |
| Operations | create, read, update, delete, invoke |
| Rights | `read` for everyone; `manageNodes` for create, update, delete and invoke; `allowRealTimePolling` for the real-time verbs |

The relationship to nodes is `System.Hosting` and is navigable from both ends, so you never
need to write the join by hand:

```bash
python3 tools/schema_query.py path Orion.Nodes Orion.NPM.Interfaces
```

`Orion.Nodes.Interfaces` walks from a node to its interfaces and behaves as a left join;
`Orion.NPM.Interfaces.Node` walks back and behaves as an inner join, so an interface whose
node has been deleted will not appear.

### The properties worth knowing

**Identity and shape.** `Name`, `Caption`, `FullName`, `IfName`, `Alias`, `Index`,
`PhysicalAddress`, `MTU`, `Speed`, `Type`, `TypeName`, `TypeDescription`, `DuplexMode`,
`Counter64`.

**State.** `AdminStatus` and `OperStatus` are the two SNMP values, both `System.Int16`.
`Status` is the platform's combined view, and its schema description enumerates the values
it takes: `0` Unknown, `1` Up, `2` Down, `3` Warning, `4` Shutdown, `9` Unmanaged, `10`
Unplugged, `12` Unreachable. Join [`Orion.StatusInfo`](../reference/status-codes.md) rather
than hard-coding those integers.

**Live counters.** `Inbps`, `Outbps`, `Bps`, `InPercentUtil`, `OutPercentUtil`,
`PercentUtil`, `InPps`, `OutPps`, `InUcastPps`, `OutUcastPps`, `InMcastPps`, `OutMcastPps`,
`InPktSize`, `OutPktSize`. These hold the most recent poll, not a history.

**Rolled-up counters.** `InErrorsToday`, `InErrorsThisHour`, `OutDiscardsToday`,
`CRCAlignErrorsToday`, `LateCollisionsToday`, `MaxInBpsToday`, `MaxInBpsTime`,
`MaxOutBpsToday`, `MaxOutBpsTime`, and the `ThisHour` variants of each.

**Bandwidth overrides.** `InBandwidth` and `OutBandwidth` are settable values used in place
of the polled `Speed` when `CustomBandwidth` is true. The `SetBandwidth` verb is how you
change them.

**Polling control.** `PollInterval`, `NextPoll`, `RediscoveryInterval`, `NextRediscovery`,
`StatCollection`, `SkippedPollingCycles`, `LastSync`, `MinutesSinceLastSync`,
`HasObsoleteData`, `ObsoleteDataCurrentSettingValue`, `ObsoleteDataFeatureStatus`.

**Inherited.** `UnManaged`, `UnManageFrom` and `UnManageUntil` come from
`System.ManagedEntity`; `Uri`, `DisplayName` and `InstanceType` come from `System.Entity`.
They are queryable on `Orion.NPM.Interfaces` even though it does not declare them.

For runnable inventory, utilization, error and duplex-mismatch queries against this entity,
use [`../../scripts/swql/02-interfaces.swql`](../../scripts/swql/02-interfaces.swql) rather
than rewriting them. The queries further down this page pick up where that file stops, at
the historical statistics tables.

### Interface satellites

Fifteen entities have names beginning `Orion.NPM.Interface`, and most of them are satellites
of the one above. The ones you will actually reach for:

| Entity | What it holds |
|---|---|
| `Orion.NPM.InterfaceTraffic` | Historical throughput. `DateTime`, `InAveragebps`, `InMinbps`, `InMaxbps`, `InTotalBytes`, and the `Out` equivalents, plus `PercentUtil` |
| `Orion.NPM.InterfaceErrors` | Historical errors and discards. `InErrors`, `OutErrors`, `InDiscards`, `OutDiscards`, `CRCAlignErrors`, `LateCollisions`, `PercentErrors` |
| `Orion.NPM.InterfaceAvailability` | Historical availability percentage with a `Weight` column |
| `Orion.NPM.InterfacePercentiles` | Precomputed 90th, 95th and 99th percentile bps, inbound, outbound and total |
| `Orion.NPM.InterfaceNetObjectDowntime` | Down periods, as `DateTimeFrom` / `DateTimeUntil` / `TotalDurationMin` |
| `Orion.NPM.InterfacesRelationship` | Parent/child interface links such as LAG bundles, with `LACPOperState` |
| `Orion.NPM.InterfacesCustomProperties` | Interface custom property values, plus the four verbs that manage the property definitions |
| `Orion.NPM.DiscoveredInterfaces` | Interfaces found by a discovery profile but not yet added, carrying `ProfileID`, `DiscoveredNodeID` and `DiscoveredInterfaceID`. Reading it requires the `manageNodes` right, unlike most read-only entities |
| `Orion.NPM.InterfacesForecastCapacity` | Capacity forecasting, inheriting from `Orion.ForecastCapacity` |

`Orion.NPM.InterfaceTraffic`, `Orion.NPM.InterfaceErrors` and
`Orion.NPM.InterfaceAvailability` all inherit from `System.StatisticsEntity`. They are among
the largest tables on the system, so every query against them must be time-bounded.

`Orion.NPM.InterfaceTraffic` and `Orion.NPM.InterfaceErrors` each expose an `Interface`
navigation property, which makes `t.Interface.Node.Caption` a two-hop dot-walk with no join
written. `Orion.NPM.InterfacePercentiles` does not, so join it on `InterfaceID` explicitly.

## Universal device pollers

Universal Device Pollers, called UnDP in the product and "custom pollers" in the schema, are
NPM's mechanism for collecting arbitrary SNMP OIDs. SolarWinds documents the feature and its
API at
[NPM Universal Device Pollers](https://solarwinds.github.io/OrionSDK/docs/network-performance-monitor/npm-universal-device-pollers/),
and the key point from that page is a division of labour: **you define pollers in the
Universal Device Poller desktop application, and you assign them through the API.** There is
no verb for creating a poller definition, and there is no entity you can `Create` to make
one. Creating assignments, on the other hand, is ordinary CRUD.

Thirteen entities have names beginning `Orion.NPM.CustomPoller`, and they split into three
layers.

**The definition.** `Orion.NPM.CustomPollers` is the poller itself: `CustomPollerID`
(`System.Guid`), `UniqueName`, `Description`, `OID`, `MIB`, `SNMPGetType`, `PollerType`,
`NetObjectPrefix`, `GroupName`, `Format`, `Unit`, `PollInterval`, `Enabled` and
`IncludeHistoricStatistics`. Two subtypes inherit from it and declare no properties of their
own, existing to carry a relationship to the matching assignment entity:
`Orion.NPM.NodeCustomPollers` and `Orion.NPM.InterfaceCustomPollers`.

**The assignment.** `Orion.NPM.CustomPollerAssignment` is an abstract parent with two
concrete children:

| Entity | Assigned to | NetObject prefix | Key |
|---|---|---|---|
| `Orion.NPM.CustomPollerAssignmentOnNode` | A node, through `NodeID` | `UNDPN` | `CustomPollerAssignmentID` (`System.Guid`) |
| `Orion.NPM.CustomPollerAssignmentOnInterface` | An interface, through `InterfaceID` | `UNDPI` | `CustomPollerAssignmentID` (`System.Guid`) |

Both support create, read, update, delete and invoke, all requiring the `manageNodes` right,
with read available to everyone. Both declare only five properties of their own and inherit
the interesting ones from `Orion.NPM.CustomPollerAssignment`: `CustomPollerID`,
`AssignmentName`, `CustomPollerName`, `CustomPollerDescription`, `CustomPollerOid`,
`CustomPollerMIB`, `CurrentValue` and the `UnManaged` trio. This is why the official
documentation can filter `Orion.NPM.CustomPollerAssignmentOnNode` on `CustomPollerID` even
though `show` lists only `NodeID`, `CustomPollerAssignmentID`, `Description`, `DetailsUrl`
and `ModernIcon`. Use `props`, not `show`, when you want the full picture:

```bash
python3 tools/schema_query.py props Orion.NPM.CustomPollerAssignmentOnNode
```

**The results.** `Orion.NPM.CustomPollerStatusOnNode` and
`Orion.NPM.CustomPollerStatusOnInterface` hold the latest polled value per assignment, with
`DateTime`, `Rate`, `Total`, `RawStatus`, `Status` (a `System.String` here, not a status
integer), `RowID` and `Description`. `Orion.NPM.CustomPollerStatusOnNodeScalar` and
`Orion.NPM.CustomPollerStatusOnNodeTabular` are the single-value and table-valued
specialisations of the node one; the tabular variant carries `RowLabel` and
`CompressedRowID` and has its own NetObject prefix, `UNDPT`.
`Orion.NPM.CustomPollerStatistics` holds the history, as `MinRate`, `AvgRate`, `MaxRate` and
`Total` per `DateTime`, and inherits from `System.StatisticsEntity`, so time-bound it.
`Orion.NPM.CustomPollerThresholds` carries `Warning` and `Critical` per `CustomPollerID`,
both as strings, and `Orion.NPM.CustomPollerLabels` names the rows of a tabular poller.

### Assigning a poller

Assignment is a plain create against the assignment entity with two values, exactly as the
official page describes. In PowerShell:

```powershell
$swis = Connect-Swis -Hostname orion.example.com -Username admin -Password ''

$customPollerId = Get-SwisData $swis @"
SELECT CustomPollerID
FROM Orion.NPM.CustomPollers
WHERE UniqueName = @name
"@ @{ name = 'ciscoEnvMonFanState' }

New-SwisObject $swis Orion.NPM.CustomPollerAssignmentOnNode @{
    NodeID         = 14
    CustomPollerID = $customPollerId
}
```

Over REST, that is a `POST` to
`/SolarWinds/InformationService/v3/Json/Create/Orion.NPM.CustomPollerAssignmentOnNode` with
`{"NodeID": 14, "CustomPollerID": "..."}` as the body. The SolarWinds page still shows port
17778 in its example URL; use **17774** on platform release 2023.1 and later, since 17778 is
deprecated. See [../swis/rest-api.md](../swis/rest-api.md).

Removing an assignment is a delete against its `Uri`, which you look up first:

```sql
SELECT Uri
FROM Orion.NPM.CustomPollerAssignmentOnNode
WHERE NodeID = @nodeId AND CustomPollerID = @customPollerId
```

[../swis/uris.md](../swis/uris.md) explains the URI format and
[../swis/crud.md](../swis/crud.md) covers the create and delete calls.

## Wireless

Wireless is the part of NPM where guessing an entity name is most likely to fail, because
four families with overlapping names coexist in 2026.2.

| Family | Entities | Relationships to the rest of the model |
|---|---|---|
| `Orion.Packages.Wireless.` | 19 | Fully connected. `Controllers` and `AccessPoints` both navigate to `Orion.Nodes`, and the family joins internally through `AccessPoint`, `WirelessInterface` and `Controller` navigation properties |
| `Orion.Wireless.` | 14 | Same entity names in a much thinner shape. `Orion.Wireless.Controllers` declares two properties; the equivalent in the other family declares nine. No navigation path exists from `Orion.Nodes` to `Orion.Wireless.AccessPoints` within three hops |
| `Orion.NPM.WL.` | 4 | `APs`, `Clients`, `Controllers`, `Interfaces`. Flat tables with `NodeID`, `RecordID` and `LastUpdate` columns and no declared relationships at all |
| `Orion.NPM.Wireless.` | 2 | `Clients` and `Interface`. Same flat shape, no relationships |

Prefer `Orion.Packages.Wireless.` unless you have a specific reason not to. It is the family
the rest of the schema is wired into, and the only one whose entities appear in the
[netobject reference](../reference/netobject-types.md), as `WLAP` for access points and
`WLC` for controllers.

Which of the other three are deprecated, and in which release, is **not recorded in the
published schema**: none of these entities carries a summary, and none is marked obsolete.
Confirm the state on your own server before depending on one:

```sql
SELECT FullName, IsObsolete, ObsolescenceReason
FROM Metadata.Entity
WHERE FullName LIKE 'Orion.Wireless.%' OR FullName LIKE 'Orion.NPM.WL.%'
ORDER BY FullName
```

Inside the recommended family the model is:

- `Orion.Packages.Wireless.Controllers` is the controller, keyed by `NodeID`, with `Name`,
  `Model`, `ThinAPsCount` and `RogueAPsCount`. From a node, the navigation property is
  `Controller`, singular.
- `Orion.Packages.Wireless.AccessPoints` is the access point, with `ID`, `ControllerID`,
  `ControllerName`, `Name`, `SSID`, `Clients`, throughput counters and `LastReported`. Two
  specialisations exist, `.Thin` and `.Autonomous`. From a node, the navigation property is
  `AccessPoints`.
- `Orion.Packages.Wireless.Interfaces` is the radio, keyed by `AccessPointID`, with `SSID`,
  `Channel`, `AutoChannel`, `RadioType`, `WEPEnabled`, `Clients` and error counters
  (`InAckFailure`, `OutFailures`, `InFCSError`).
- `Orion.Packages.Wireless.Clients` is the associated station, reached from the radio through
  `WirelessInterface`, with `MAC`, `IPAddress`, `RDNS`, `SSID`, `SignalStrength` and byte and
  packet counters.
- `Orion.Packages.Wireless.Rogues` hangs off the controller and carries `MAC`, `SSID`,
  `Channel` and `SignalStrength`.
- The `Historical*` entities (`HistoricalAccessPoints`, `HistoricalClients`,
  `HistoricalInterfaces`, `HistoricalRogues`) inherit from
  `Orion.Packages.Wireless.HistoryEntity`, which inherits from `System.StatisticsEntity`.
  Time-bound them.
- `Orion.Packages.Wireless.ClientsSessionHistory` records completed client sessions with
  `FirstUpdate`, `LastUpdate`, `APName` and the SSID the client used.

### Heat maps

`Orion.WirelessHeatMap.` is a separate prefix because heat maps are a separate feature built
on top of the wireless data. `Orion.WirelessHeatMap.Map` is the map itself (`MapID`,
`DisplayName`, `Scale`, `ScaleUnit`, `PercentProgress`, `LastGenerationStarted`,
`LastGenerationFinished`, `ErrorCode`), `Orion.WirelessHeatMap.MapPoint` places an entity on
it, `Orion.WirelessHeatMap.AccessPoints` is the heat-map view of an AP, and
`Orion.WirelessHeatMap.ClientLocation` holds computed client `X` and `Y` coordinates per
map. `Orion.WirelessHeatMap.Map` carries 14 verbs. The heat map entities are also the only
ones in the NPM families whose management right is `manageMaps` rather than `manageNodes`:
`Orion.WirelessHeatMap.Map` requires it for create, update, delete and invoke, and
`Orion.WirelessHeatMap.MapPoint` requires it for invoke.

## Routing

`Orion.Routing.` is eleven entities describing what the device knows about reaching other
networks.

`Orion.Routing.Router` is the thin anchor: `NodeID`, `Caption`, `Description`, and
navigation to everything else in the family. It is the parent of `Neighbors`,
`RoutingDetails`, `RoutingTableFlap` and `DefaultRouteChange`, and it navigates back to
`Orion.Nodes` through a property called `Nodes`, plural.

`Orion.Routing.Neighbors` is the adjacency, and the entity most people want. It carries
`NeighborID`, `NodeID`, `NeighborIP`, `ProtocolID`, `ProtocolName`, `ProtocolStatus`,
`ProtocolStatusDescription`, `ProtocolOrionStatus`, `AutonomousSystem`,
`LocalAutonomousSystemNumber`, `BgpRole`, `BgpNeighborAdminStatus`,
`BgpNeighborLastError`, `VrfList`, `IsDeleted` and `LastChange`. Note both `ProtocolStatus`,
which is protocol-specific, and `ProtocolOrionStatus`, which is the value mapped onto the
platform's status scale; `Orion.Routing.RoutingProtocolStateMapping` is the lookup table
between them. `LocalProtocolInterface` navigates to the `Orion.NPM.Interfaces` row the
adjacency is formed over.

`Orion.Routing.RoutingTable` is the FIB view, with `RouteDestination`, `RouteMaskLen`,
`RouteNextHop`, `Metric`, `ProtocolName`, `VrfIndex` and pre-joined display columns
(`NodeCaption`, `InterfaceCaption`, `NextHopStatus`). It navigates to `Interface`,
`Neighbor` and `VRF`.

`Orion.Routing.VRF` is the virtual routing instance: `VrfIndex`, `NodeID`, `Name`,
`RouteDistinguisher`, `Status`, `CompleteValues`. It hosts `Orion.Routing.VRFInterface`,
which maps a VRF to interfaces by `IfIndex`, and it navigates to `Orion.Nodes` through
`Node`. Its NetObject prefix is `VRF`, and `Orion.Routing.Neighbors` uses `NBR`.

Two entities exist purely for churn: `Orion.Routing.NeighborsFlapCount` counts adjacency
resets per day bucket, and `Orion.Routing.RoutingTableFlap` records individual route
withdrawals and reinstallations. Both carry a `DaysBucket` column alongside `DateTime`,
which is what the product uses for its daily rollups. `Orion.Routing.DefaultRouteChange`
records changes to the default route specifically, with `ChangeType` as a boolean.

`Orion.Routing.RoutingDetails` is the poller's own status for a node: `Poller`, `LastPoll`,
`NextPoll`, `ErrorMessage`, `CompleteValues`. If routing data looks stale, look there first.

## NetPath

NetPath probes a service from a location and reconstructs the path, hop by hop, including
hops you do not own. Twelve entities model it.

- `Orion.NetPath.Probes` is the probing location: `ProbeID`, `Name`, `Enabled`, `Status`, and
  navigation to `Orion.AgentManagement.Agent` and `Orion.Engines`. A probe runs on an agent
  or on a polling engine, which is why two navigation paths exist from a node to a probe.
- `Orion.NetPath.EndpointServices` is the target: `EndpointServiceID`, `DisplayName`,
  `HostName`, `Protocol`, `Port`, `ProbeIntervalInMinutes`.
- `Orion.NetPath.ServiceAssignments` pairs a probe with a service. It inherits from
  `Orion.NetPath.ServiceAssignmentsBase`, and that parent is where the useful columns are
  declared: `ProbeName`, `ServiceName`, `Enabled`, `Status`, `LastStatus`, `LastProbeTime`,
  `SourceModule`, plus URL columns for the rendered path graph. The child declares exactly
  one property of its own. `Orion.NetPath.EndpointServiceAssignments` is the creatable
  variant, supporting create, update and delete under `manageNodes`.
- `Orion.NetPath.Tests` is one probe run: `ExecutedAt`, `Rtt`, `RttMin`, `PacketLoss`,
  `SentPackets`, `LostPackets`, `UniquePathCount`, `RouteChangeCount`, `EdgeChangeCount`,
  `CompletionRatio`, and a `Graph` blob.
- `Orion.NetPath.Performances` is per-node and per-edge latency and loss within a path,
  keyed by `ObjectID` and `ObjectType`.
- `Orion.NetPath.Traces` holds the raw paths as `CompressedTraces`, a byte array.
- `Orion.NetPath.Networks` is the BGP and WHOIS context for discovered hops:
  `CidrBlockPrefix`, `OrganizationName`, `OriginAs`, `AbusePocs`.
- `Orion.NetPath.Thresholds` and `Orion.NetPath.ThresholdTypes` hold per-assignment
  `Critical`, `Warning` and `Benign` values.

## Multicast

`Orion.NPM.MulticastRouting.` is fourteen entities modelling PIM and the multicast routing
table.

`Orion.NPM.MulticastRouting.Groups` is the group address (`MulticastGroupID`, `GroupIP`,
`GroupName`, `Status`), NetObject prefix `MCG`.
`Orion.NPM.MulticastRouting.GroupNodes` is one node's participation in one group
(`MulticastGroupNodeID`, `NodeID`, `SourcePPS`, `SourceBPS`, `StatusReason`), NetObject
prefix `MCGN`, and it navigates to both `Orion.Nodes` and the group.
`Orion.NPM.MulticastRouting.RoutingTable` is the mroute entry, with upstream neighbour,
`InPps`, `InBps`, `Flags`, `UpTime` and `ExpiryTime`.
`Orion.NPM.MulticastRouting.Interfaces` is the multicast-enabled interface, hosted by
`Orion.NPM.Interfaces`, and `PIMNeighbors` hangs off that.
`RendezvousPoints`, `Sources`, `GroupTranslation` and the report and history entities
complete the family.

## F5 and Cisco UCS

Both families were reorganised, and old entity names that circulate in the community no
longer resolve. The [reconciliation data](../../data/reference/reconciliation.json) records
each rename:

| Name you may see | Status in 2026.2 | Current name |
|---|---|---|
| `Orion.F5.Device` | Not in the schema | `Orion.F5.System.Device` |
| `Orion.F5.Pools` | Not in the schema | `Orion.F5.LTM.Pool`, `Orion.F5.GTM.Pool` |
| `Orion.F5.VirtualServers` | Not in the schema | `Orion.F5.Map.VirtualServer`, `Orion.F5.LTM.VirtualServer`, `Orion.F5.GTM.VirtualServer` |
| `Orion.F5.Nodes` | Not in the schema | No confident successor |
| `Orion.NPM.UCSChassis` | Not in the schema | `Orion.UCS.Chassis` |
| `Orion.NPM.UCSBlades` | Not in the schema | `Orion.UCS.Blades` |
| `Orion.NPM.UCSFabrics` | Not in the schema | `Orion.UCS.Fabrics` |
| `Orion.NPM.UCSManagers`, `Orion.NPM.UCSFans`, `Orion.NPM.UCSPSUs` | Not in the schema | No confident successor |

**F5** now splits by BIG-IP module. `Orion.F5.System.Device` is the appliance, keyed by
`NodeID`, with `ProductVersion`, `SerialNumber`, `FailoverStatus`, `SyncStatus`,
`Connections`, `In_Throughput` and `IsPollerEnabled`. It hosts `Orion.F5.System.Module`
(with `ModuleLTM`, `ModuleGTM` and `ModuleOther` specialisations), `Orion.F5.System.VLAN`,
`Orion.F5.System.Failover` and the virtual servers. `Orion.F5.LTM.` is local traffic
management: `VirtualServer`, `Pool`, `PoolMember`, `Monitor`, `Server`, `VirtualIPAddress`
and two stats entities. `Orion.F5.GTM.` is global traffic management: `WideIP`, `Pool`,
`PoolMember`, `Server`, `VirtualServer`. Both keep a device-native status and a
platform-mapped one side by side, as `F5Status` and `OrionStatus`, each with a
`...StatusDescription` string.

**UCS** moved out of `Orion.NPM.` wholesale. `Orion.UCS.Chassis` inherits from
`Orion.HardwareHealth.BMC.Chassis`, `Orion.UCS.Blades` from
`Orion.HardwareHealth.BMC.Blades`, and both declare almost nothing themselves:
`Orion.UCS.Chassis` declares only `DetailsUrl` and `Orion.UCS.Blades` declares nothing at
all, so use `props` rather than `show` to see what they offer. The chassis picks up `Fans`
and `PSUs` navigation properties from its BMC parent, and `Orion.UCS.FansOnChassis` and
`Orion.UCS.PSUsOnChassis` are the UCS specialisations of what those lead to.
`Orion.UCS.Fabrics` is the fabric interconnect and is the one entity in the family with a
substantial property list of its own; `Orion.UCS.FansOnFabrics` and
`Orion.UCS.PSUsOnFabrics` hang off it directly. `Orion.UCS.Events` completes the family.

## Smaller families in the NPM namespace

| Family | Entities | What it covers |
|---|---|---|
| `Orion.NPM.EW.` | 14 | EnergyWise: device, entity, neighbour, readiness and their hourly and daily rollups |
| `Orion.NPM.MulticastRouting.` | 14 | Multicast, described above |
| `Orion.NPM.SwitchStack*` | 5 | Stacked switches: `SwitchStack`, `SwitchStackMember`, `SwitchStackMemberPort`, `SwitchStackPower`, `SwitchStackPowerPort` |
| `Orion.NPM.FC*` | 4 | Fibre channel: `FCUnits`, `FCPorts`, `FCSensors`, `FCRevisions`, NetObject prefixes `FCU`, `FCP`, `FCS`, `FCR` |
| `Orion.NPM.Vsan*` and `Orion.NPM.VSANs` | 4 | VSANs and their traffic, error and current-stats tables, NetObject prefix `NVS` |

Two entities are named misleadingly and worth flagging. `Orion.NPM.Nodes` is **not** an NPM
view of a node: it is polling bookkeeping, holding `PollerJobID`, `SecondaryPollerJobID`,
`Reschedule`, `State` and `LastHistorySave`. The node you want is `Orion.Nodes`, covered in
[`../../scripts/swql/01-nodes.swql`](../../scripts/swql/01-nodes.swql).
`Orion.NPM.OrionSwitchPortMapping` pairs a source port with the port mapped to it, carrying
`SourceNodeID`, `SourceInterfaceID`, `SourcePortName` and `SourceMACAddress` alongside
`MappedNodeID`, `MappedPortName`, `MappedMACAddress` and `MappedIPAddress`. It sounds like
User Device Tracker but is a separate NPM table, reachable from `Orion.Nodes` through
`SwitchPortEntriesAsSource` and `SwitchPortEntriesAsMapped`.

## Verbs

NPM is a read-heavy module. Of its 139 headline entities plus the F5 and UCS families, seven
declare verbs at all. Everything else you change through NPM you change with CRUD, as with
custom poller assignments above.

```bash
python3 tools/schema_query.py verbs --entity Orion.NPM.Interfaces
python3 tools/schema_query.py verb Orion.NPM.Interfaces SetBandwidth
```

### `Orion.NPM.Interfaces` (10 verbs)

| Verb | Parameters, in order | Right |
|---|---|---|
| `Unmanage` | `netObjectId`, `unmanageTime`, `remanageTime`, `isRelative`, `allowOverlapping` (optional) | `allowUnmanage` |
| `Remanage` | `netObjectId` | `allowUnmanage` |
| `SetBandwidth` | `netObjectId`, `inBandwidth`, `outBandwidth`, `customBandwidth` | `manageNodes` |
| `SetPowerLevel` | `interfaceId`, `powerLevel` | `manageNodes` |
| `DiscoverInterfacesOnNode` | `nodeId` | `manageNodes` |
| `AddInterfacesOnNode` | `nodeId`, `interfacesToAdd`, `pollers` | `manageNodes` |
| `CreateInterfacesPluginConfiguration` | `context` | `manageNodes` |
| `GetSupportedMetrics` | `netObjectId` | `allowRealTimePolling`, `admin` |
| `StartRealTimePolling` | `netObjectId`, `owner`, `properties`, `pollingExpiration` (optional), `pollingFrequency` (optional) | `allowRealTimePolling`, `admin` |
| `StopRealTimePolling` | `netObjectId`, `owner`, `properties` | `allowRealTimePolling`, `admin` |

Arguments are positional. Names appear in the documentation and in the Swagger contract but
never travel on the wire, so the order in that table is the entire contract.

`DiscoverInterfacesOnNode` returns a `LiteDiscoveryResult`, and `AddInterfacesOnNode` takes
the discovered set back. `pollers` is an enum accepting `AddDefaultPollers` or
`AddNoPollers`. SolarWinds' own script for the pair is
`Samples/PowerShell/NPM.DiscoverAndAddInterfacesOnNode.ps1` in the
[OrionSDK repository](https://github.com/solarwinds/OrionSDK), and the shape is:

```powershell
$discovered = Invoke-SwisVerb $swis Orion.NPM.Interfaces DiscoverInterfacesOnNode $nodeId

if ($discovered.Result -eq 'Succeed') {
    # Optionally drop entries from $discovered.DiscoveredInterfaces before adding.
    Invoke-SwisVerb $swis Orion.NPM.Interfaces AddInterfacesOnNode `
        @($nodeId, $discovered.DiscoveredInterfaces, 'AddDefaultPollers') | Out-Null
}
```

### The other six

| Entity | Verbs | Notes |
|---|---|---|
| `Orion.NPM.InterfacesCustomProperties` | `CreateCustomProperty`, `CreateCustomPropertyWithValues`, `ModifyCustomProperty`, `DeleteCustomProperty` | The entity requires `admin` for invoke. These manage interface custom property *definitions*; values are set by updating the property on the entity |
| `Orion.WirelessHeatMap.Map` | 14, including `InsertWirelessHeatMap`, `UpdateWirelessHeatMap`, `DeleteWirelessHeatMap`, `PollAPSignalStrengthNow`, `StartClientSignalPoll`, `GetProgress` | `manageMaps` for create, update, delete and invoke |
| `Orion.WirelessHeatMap.MapPoint` | `InsertMapPoint`, `DeleteMapPoint`, `DeleteMapPoints`, `SyncMapPoints` | |
| `Orion.WirelessHeatMap.ResourceLimitation` | `InsertResourceLimitation` | |
| `Orion.F5.System.Device` | `EnableApiPolling` (`nodeId`, `port`, `useSsl`, `userName`, `password`, `reservedSslCertificateIdentity`), `DisableApiPolling` (`nodeId`), `TestApiPolling` | `manageNodes` |
| `Orion.F5.LTM.Server` | `LinkNode` (`f5ServerId`, `nodeId`), `UnlinkNode` (`f5ServerId`) | `manageNodes`. `LinkNode` associates an F5 pool member with the monitored node behind it |

## Worked queries

Every query below has been validated against the 2026.2 schema. Bound parameters are written
as `@name`; supply window boundaries yourself in UTC rather than computing them in SWQL, for
the reason in the gotchas section.

### 1. Peak and mean throughput per interface over a window

The live `Inbps` and `PercentUtil` columns on `Orion.NPM.Interfaces` only tell you about the
last poll. For "what did this circuit actually do overnight", aggregate the statistics table.

```sql
SELECT TOP 25
    t.Interface.Node.Caption AS NodeName,
    t.Interface.Name AS InterfaceName,
    t.Interface.InterfaceSpeed,
    MAX(t.InMaxbps) AS PeakInbps,
    MAX(t.OutMaxbps) AS PeakOutbps,
    AVG(t.InAveragebps) AS MeanInbps,
    AVG(t.OutAveragebps) AS MeanOutbps
FROM Orion.NPM.InterfaceTraffic t
WHERE t.DateTime >= @startUtc
  AND t.DateTime < @endUtc
GROUP BY t.Interface.Node.Caption, t.Interface.Name, t.Interface.InterfaceSpeed
ORDER BY MAX(t.InMaxbps) DESC
```

`t.Interface.Node.Caption` walks two hosting relationships in one expression. The half-open
range (`>=` and `<`) avoids double-counting the boundary sample when you run the query for
consecutive windows.

### 2. Interfaces accumulating errors and discards

Errors and discards usually show up before a user complains, and they are far more useful
summed over a window than sampled once.

```sql
SELECT TOP 25
    e.Interface.Node.Caption AS NodeName,
    e.Interface.Name AS InterfaceName,
    e.Interface.InterfaceTypeName,
    SUM(e.InErrors) AS InErrors,
    SUM(e.OutErrors) AS OutErrors,
    SUM(e.InDiscards) AS InDiscards,
    SUM(e.OutDiscards) AS OutDiscards,
    MAX(e.PercentErrors) AS WorstPercentErrors
FROM Orion.NPM.InterfaceErrors e
WHERE e.DateTime >= @startUtc
  AND e.DateTime < @endUtc
  AND e.Interface.UnManaged = FALSE
GROUP BY e.Interface.Node.Caption, e.Interface.Name, e.Interface.InterfaceTypeName
HAVING SUM(e.InErrors) + SUM(e.OutErrors) > 0
ORDER BY SUM(e.InErrors) + SUM(e.OutErrors) DESC
```

Filtering `UnManaged = FALSE` on the parent interface excludes anything in a maintenance
window, which is the difference between "actually broken" and "deliberately silenced".
`UnManaged` is inherited from `System.ManagedEntity` and is queryable even though
`Orion.NPM.Interfaces` does not declare it.

### 3. 95th percentile utilisation against provisioned speed

This is the query a capacity conversation actually needs, because peak-of-peaks
over-provisions and a plain average under-provisions. `Orion.NPM.InterfacePercentiles`
declares no navigation properties, so the join is explicit.

```sql
SELECT TOP 100
    i.Node.Caption AS NodeName,
    i.Name AS InterfaceName,
    i.InterfaceSpeed,
    pct.AverageInboundBps95th,
    pct.AverageOutboundBps95th,
    pct.DateTime
FROM Orion.NPM.Interfaces i
JOIN Orion.NPM.InterfacePercentiles pct ON pct.InterfaceID = i.InterfaceID
WHERE pct.DateTime >= @sinceUtc
  AND i.InterfaceSpeed > 0
ORDER BY pct.AverageInboundBps95th DESC
```

### 4. Where a given universal device poller is assigned, and what it last returned

Start from the poller's name, which is what a human knows, and end at the current value per
node. `CurrentValue`, `CustomPollerName` and `CustomPollerOid` are inherited from
`Orion.NPM.CustomPollerAssignment`.

```sql
SELECT TOP 100
    a.Node.Caption AS NodeName,
    a.CustomPollerName,
    a.CustomPollerOid,
    a.CurrentValue,
    a.CustomPollerAssignmentID,
    a.Uri
FROM Orion.NPM.CustomPollerAssignmentOnNode a
WHERE a.CustomPollerID = @customPollerId
ORDER BY a.Node.Caption
```

Selecting `Uri` in the same pass is deliberate: it is what you pass to a delete call if the
next step is to remove some of these assignments.

### 5. Which poller definitions are actually being used

Pollers accumulate. This tells you which definitions earn their place and which were defined
once and never assigned, since an unassigned poller simply produces no rows.

```sql
SELECT
    p.UniqueName,
    p.OID,
    COUNT(a.CustomPollerAssignmentID) AS NodeAssignments
FROM Orion.NPM.CustomPollers p
JOIN Orion.NPM.CustomPollerAssignmentOnNode a ON a.CustomPollerID = p.CustomPollerID
GROUP BY p.UniqueName, p.OID
ORDER BY COUNT(a.CustomPollerAssignmentID) DESC
```

### 6. Recent universal device poller results

`Orion.NPM.CustomPollerStatusOnNode` carries the polled value. Its `Status` is a string set
by the poller, not a platform status integer, so do not join `Orion.StatusInfo` to it.

```sql
SELECT TOP 50
    s.CustomPollerAssignment.Node.Caption AS NodeName,
    s.AssignmentName,
    s.RowID,
    s.Status,
    s.RawStatus,
    s.Rate,
    s.Total,
    s.DateTime
FROM Orion.NPM.CustomPollerStatusOnNode s
WHERE s.DateTime >= @sinceUtc
ORDER BY s.DateTime DESC
```

### 7. Busiest access points, with a readable status

```sql
SELECT TOP 50
    ap.Node.Caption AS AccessPointNode,
    ap.Name AS AccessPointName,
    ap.ControllerName,
    ap.SSID,
    ap.Clients,
    ap.Status,
    st.StatusName
FROM Orion.Packages.Wireless.AccessPoints ap
JOIN Orion.StatusInfo st ON ap.Status = st.StatusId
ORDER BY ap.Clients DESC
```

### 8. Wireless clients with a weak signal on one SSID

Walking `WirelessInterface` reaches the radio, and one more hop reaches the access point, so
a single row tells you the client, the radio it is on, the channel, and which AP to look at.

```sql
SELECT TOP 100
    cl.WirelessInterface.AccessPoint.Name AS AccessPointName,
    cl.WirelessInterface.SSID AS RadioSSID,
    cl.WirelessInterface.Channel,
    cl.Name AS ClientName,
    cl.MAC,
    cl.IPAddress,
    cl.SignalStrength,
    cl.InBps,
    cl.OutBps
FROM Orion.Packages.Wireless.Clients cl
WHERE cl.SSID = @ssid
  AND cl.SignalStrength < @minSignal
ORDER BY cl.SignalStrength
```

### 9. Routing adjacencies that are not up

`ProtocolOrionStatus` is the protocol state mapped onto the platform's status scale, so
comparing it to 1 means "not Up" regardless of which routing protocol formed the adjacency.
`IsDeleted` filters out adjacencies the poller has retired.

```sql
SELECT TOP 100
    n.Router.Nodes.Caption AS NodeName,
    n.NeighborIP,
    n.ProtocolName,
    n.ProtocolStatusDescription,
    n.AutonomousSystem,
    n.BgpRole,
    n.BgpNeighborLastError,
    n.LastChange,
    n.LocalProtocolInterface.Name AS LocalInterface
FROM Orion.Routing.Neighbors n
WHERE n.IsDeleted = FALSE
  AND n.ProtocolOrionStatus <> 1
ORDER BY n.LastChange DESC
```

### 10. Adjacencies that keep flapping

A neighbour that is up right now but reset forty times yesterday is a different problem from
one that is simply down, and it is the one that gets missed.

```sql
SELECT TOP 50
    f.RoutingNeighbor.NeighborIP,
    f.RoutingNeighbor.ProtocolName,
    f.NodeID,
    SUM(f.FlapCount) AS Flaps
FROM Orion.Routing.NeighborsFlapCount f
WHERE f.DateTime >= @sinceUtc
GROUP BY f.RoutingNeighbor.NeighborIP, f.RoutingNeighbor.ProtocolName, f.NodeID
ORDER BY SUM(f.FlapCount) DESC
```

### 11. NetPath results ranked by packet loss

```sql
SELECT TOP 100
    t.ServiceAssignment.ProbeName,
    t.ServiceAssignment.ServiceName,
    t.ExecutedAt,
    t.Rtt,
    t.PacketLoss,
    t.SentPackets,
    t.LostPackets,
    t.RouteChangeCount
FROM Orion.NetPath.Tests t
WHERE t.ExecutedAt >= @sinceUtc
ORDER BY t.PacketLoss DESC
```

`ProbeName` and `ServiceName` are declared on `Orion.NetPath.ServiceAssignmentsBase` and
inherited by `Orion.NetPath.ServiceAssignments`, which is what the `ServiceAssignment`
navigation property points at.

### 12. F5 pools missing members

`MemberCountActual` below `MemberCountTotal` means the pool is running degraded, which is
exactly the state that does not show up as an outage.

```sql
SELECT TOP 50
    p.F5Device.Caption AS F5Device,
    p.Name AS PoolName,
    p.LBModeDescription,
    p.MemberCountTotal,
    p.MemberCountActual,
    p.MemberPercentActual,
    p.F5StatusDescription,
    p.OrionStatusDescription
FROM Orion.F5.LTM.Pool p
WHERE p.MemberCountActual < p.MemberCountTotal
ORDER BY p.MemberPercentActual
```

### 13. Busiest multicast groups per node

```sql
SELECT TOP 50
    gn.Node.Caption AS NodeName,
    gn.MulticastGroup.GroupIP AS GroupIP,
    gn.MulticastGroup.GroupName,
    gn.GroupNodeName,
    gn.SourcePPS,
    gn.SourceBPS,
    gn.StatusDescription
FROM Orion.NPM.MulticastRouting.GroupNodes gn
ORDER BY gn.SourceBPS DESC
```

### 14. LAG bundles and their members

```sql
SELECT
    r.RelationshipType.Name AS RelationshipType,
    r.ParentInterface.Node.Caption AS NodeName,
    r.ParentInterface.Name AS ParentInterface,
    r.ChildInterface.Name AS ChildInterface,
    r.LACPOperState
FROM Orion.NPM.InterfacesRelationship r
ORDER BY r.ParentInterface.Node.Caption
```

## Gotchas

**`netObjectId` does not mean the same thing on every NPM verb.** `Unmanage` and `Remanage`
type it as a string and document the example `'I:1'`, so they want the NetObject form.
`SetBandwidth` types it as a string but documents it as "InterfaceID of the target
interface". `GetSupportedMetrics`, `StartRealTimePolling` and `StopRealTimePolling` type it
as a number and document it as the `InterfaceID`. And `SetPowerLevel` does not use the name
at all, taking `interfaceId` instead. Check the specific verb before you call it:

```bash
python3 tools/schema_query.py verb Orion.NPM.Interfaces Unmanage
```

**`Orion.NPM.Interfaces` has duplicate property pairs.** `Name` and `InterfaceName`, `Index`
and `InterfaceIndex`, `Alias` and `InterfaceAlias`, `Speed` and `InterfaceSpeed`, `MTU` and
`InterfaceMTU`, `Type` and `InterfaceType`, `TypeName` and `InterfaceTypeName`, `Caption`
and `InterfaceCaption`, `LastChange` and `InterfaceLastChange`. The schema explicitly says
`InterfaceAlias` "Aligns with Alias field" and `InterfaceIndex` "Aligns with Index field";
the others carry identical descriptions to their partners. Pick one convention per query so
your output columns stay predictable, and expect to see both in other people's queries.

**Interface `Status` is not the same as `OperStatus`.** `Status` is calculated from
`AdminStatus` and `OperStatus` together and adds platform-level values that SNMP has no
concept of: 9 for Unmanaged, 10 for Unplugged, 12 for Unreachable. An interface that is
`Status = 12` is not broken, it is behind a node that is down. Filtering on `OperStatus <> 1`
and filtering on `Status <> 1` answer different questions.

**Unpluggable interfaces report Up or Unplugged, not Up or Down.** `UnPluggable` is a
per-interface boolean, and setting it changes which status values that interface can take.
An alert written against `Status = 2` will never fire on an unpluggable interface.

**Statistics entities are the largest tables you can touch.** `Orion.NPM.InterfaceTraffic`,
`Orion.NPM.InterfaceErrors`, `Orion.NPM.InterfaceAvailability`,
`Orion.NPM.CustomPollerStatistics` and the wireless `Historical*` entities all inherit from
`System.StatisticsEntity`. Always bound them by `DateTime`, and always bound the result set
with `TOP n` or `WITH ROWS a TO b`.

**Do not build the time window with `GetUtcDate()` plus the `AddX` functions.** Those
compile to T-SQL `DATEADD`, which is timezone blind, so the combination produces an offset
that is wrong by your server's UTC offset. Compute the bounds in the client and pass them as
bound parameters, which is what the queries above assume.

**Four wireless families coexist, and only one is wired into the rest of the model.** Prefer
`Orion.Packages.Wireless.`. Navigating from a node uses `Controller` in the singular and
`AccessPoints` in the plural, which is easy to get backwards.

**Two NetPath relationships point at entities that do not exist in this schema.**
`Orion.NetPath.EndpointServiceAssignments` declares navigation properties `ProbeBase` and
`EndpointServiceBase` targeting `Orion.NetPath.ProbesBase` and
`Orion.NetPath.EndpointServicesBase`, neither of which is in the 2026.2 entity list. Use
`Probe` and `EndpointService` instead, which target entities that do exist. Whether the
`Base` entities are present but undocumented on a live server is unverified here; check with
`SELECT FullName FROM Metadata.Entity WHERE FullName LIKE 'Orion.NetPath.%'`.

**UCS status columns are not all integers.** `Orion.UCS.Chassis.Status` is a
`System.Int32` inherited from `Orion.HardwareHealth.BMC.Chassis`, but
`Orion.UCS.Blades.Status` and `Orion.UCS.Fabrics.Status` are `System.String`. Joining
`Orion.StatusInfo` works for the first and fails for the other two.

**F5 entities carry two statuses on purpose.** `F5Status` is what the device reports and
`OrionStatus` is the mapped platform value. Alerting on the wrong one produces surprises,
and each has a matching `...StatusDescription` string that is safer to display.

**`Orion.NPM.Nodes` is not the node entity.** It is NPM's polling bookkeeping table. Query
`Orion.Nodes`.

**Custom poller definitions cannot be created through the API.** Only assignments can. If a
script needs a poller that does not exist yet, that step happens in the Universal Device
Poller application, and the definition can be exported and imported between servers.

**Account limitations filter silently.** Two accounts running the same interface query get
different rows, and nothing in the response says so. When a query "returns nothing", rule
out permissions before data.

## Related pages

- [README.md](README.md) for the module index and how to check what is installed.
- [../platform/modules.md](../platform/modules.md) for the whole-schema module map.
- [../reference/netobject-types.md](../reference/netobject-types.md) for the NetObject
  prefixes the verbs need.
- [../reference/status-codes.md](../reference/status-codes.md) for the `Status` integers.
- [../swis/crud.md](../swis/crud.md) and [../swis/uris.md](../swis/uris.md) for creating and
  deleting custom poller assignments.
- [../../scripts/swql/02-interfaces.swql](../../scripts/swql/02-interfaces.swql) for
  interface inventory, utilization, error and duplex queries.
- [../../scripts/swql/08-schema-introspection.swql](../../scripts/swql/08-schema-introspection.swql)
  for asking a live server what it actually has.

## Official SolarWinds documentation

- [NPM Universal Device Pollers](https://solarwinds.github.io/OrionSDK/docs/network-performance-monitor/npm-universal-device-pollers/)
- [Orion SDK documentation index](https://solarwinds.github.io/OrionSDK/)
- [OrionSDK sample scripts](https://github.com/solarwinds/OrionSDK/tree/master/Samples), including
  `NPM.DiscoverAndAddInterfacesOnNode.ps1` and `Interface.Cleanup.ps1`

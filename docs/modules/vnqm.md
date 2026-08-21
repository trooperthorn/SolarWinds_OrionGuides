# VNQM: VoIP and Network Quality Manager

VoIP and Network Quality Manager answers two different questions with two completely
different mechanisms, and almost every surprise in its schema comes from not knowing which
half you are looking at.

The first half is **synthetic**. VNQM configures Cisco IP SLA operations on routers, tells
them to send test traffic to another router or to a service, and collects the results. The
router does the measuring; VNQM stores what it reports. This is the half that produces
jitter, latency, packet loss and MOS numbers on a schedule whether or not anybody is on a
call, and it is the half that can tell you a WAN link is degrading before the phones start
sounding bad.

The second half is **passive**. VNQM connects to a call manager, Cisco Unified
Communications Manager or Avaya, and reads what it already knows: which phones and gateways
are registered, and the call detail records for calls that actually happened. This is the
half that tells you that the call from extension 4412 at 09:14 dropped with a particular
cause code and had a MOS of 2.1 at the destination.

Both halves land in the same `Orion.IpSla.` namespace, which is why the entity count is far
larger than people expect and why a search for "VoIP" finds only part of the module.

## Namespace and how many entities

VNQM contributes **140 entities**, all under `Orion.IpSla.`. There is no `Orion.VNQM.`
namespace and no `Orion.VoIP.` namespace: the prefix is the name of the underlying Cisco
feature, IP SLA, which predates the product name. See
[../platform/modules.md](../platform/modules.md) for why that is normal on this platform.

The 140 divide like this. The counts are exact for the 2026.2 extraction and they add up.

| Group | Count | What is in it |
|---|---|---|
| Operation definitions and configuration | 24 | `Operations`, the `OperationTypes` / `OperationStates` / `OperationStatuses` lookups, `OperationParameters`, `OperationThresholds`, and the per-type summary views |
| Operation results and statistics | 43 | `OperationCurrentStats`, `OperationStats`, and the detail / hourly / daily rollup families for round trip time, jitter, MOS, one-way delay, HTTP and FTP |
| Call manager | 28 | `CCMMonitoring`, `CCMRegions`, `CCMPhones`, `CCMGateways`, `CCMSipTrunk`, `CallManagerStats` and their rollups |
| Calls and call detail records | 9 | `VoipCallDetails`, `VoipCallDetailsHist`, `VoipCalls`, `CDRDetails`, the four `VoipCall*MMA` series, `VoipSuccessFailedCalls` |
| Gateways and PRI trunks | 17 | `VoipGateways`, `VoipGatewayEndpoints`, `VoipGatewayChannels`, `PRIGatewayUtilization`, the SIP trunk entities |
| Sites, call paths and hops | 10 | `Sites`, `Paths`, `PathHops`, `CallPathMetrics`, `AlertQos`, the path-hop result entities |
| Plumbing | 9 | `Config`, `Engines`, `Events`, `InfrastructureNodes`, `InfrastructureInterfaces`, the connection-info entities, `NumberTable` |

Check the shape for yourself without a server:

```bash
python3 tools/schema_query.py find IpSla
python3 tools/schema_query.py show Orion.IpSla.Operations
python3 tools/schema_query.py show Orion.IpSla.VoipCallDetails
python3 tools/schema_query.py path Orion.Nodes Orion.IpSla.Operations
```

And confirm the module is installed on the server in front of you before relying on any of
it, because a query against an entity a server does not have fails outright rather than
returning nothing:

```sql
SELECT FullName, BaseType, CanCreate, CanUpdate, CanDelete, CanInvoke, IsObsolete
FROM Metadata.Entity
WHERE FullName LIKE 'Orion.IpSla.%'
ORDER BY FullName
```

### The nine NetObject types

Nine VNQM entities carry a NetObject prefix in
[`data/reference/netobject-types.json`](../../data/reference/netobject-types.json), and the
display names are worth reading because they are what the console calls these things:

| Entity | Console name | Prefix | Key |
|---|---|---|---|
| `Orion.IpSla.Operations` | IP SLA QoS | `ISOP` | `OperationInstanceID` |
| `Orion.IpSla.CCMMonitoring` | VoIP CallManager | `VCCM` | `NodeID` |
| `Orion.IpSla.CCMPhones` | VoIP Phone | `VCCMP` | `ID` |
| `Orion.IpSla.CCMRegions` | VoIP Region | `VR` | `RegionID` |
| `Orion.IpSla.CCMGateways` | VoIP Gateway | `VG` | `GatewayID` |
| `Orion.IpSla.VoipGateways` | VoIP PRI Gateway | `VVG` | `VoipGatewayID` |
| `Orion.IpSla.VoipGatewayEndpoints` | VoIP PRI Trunk | `VVGT` | `VoipGatewayEndpointID` |
| `Orion.IpSla.VoipCallDetails` | VoIP Call Details | `VCDS` | `ID` |
| `Orion.IpSla.InfrastructureNodes` | VoIP Infrastructure | `P` | `InfrastructureNodeID` |

Two of those pairs are the trap. `Orion.IpSla.CCMGateways` is a gateway **as the call
manager sees it**, discovered by reading the call manager, and `Orion.IpSla.VoipGateways` is
a gateway **as the platform polls it**, a monitored node with PRI trunks and channel
utilisation. They are not the same table, they have different keys, and there is no
navigation property between them. Full list in
[../reference/netobject-types.md](../reference/netobject-types.md).

## IP SLA operations

`Orion.IpSla.Operations` is the centre of the synthetic half. One row is one IP SLA
operation configured on one router. It inherits from `System.ManagedEntity` through
`System.DashboardEntity`, so it has a `Status`, a `Uri`, an `AlertObject`, and the
`UnManaged` / `UnManageFrom` / `UnManageUntil` trio, on top of the 26 properties it declares
itself.

The declared properties group into four ideas.

**What the operation is.** `OperationInstanceID` is the platform's key.
`IpSlaOperationNumber` is the number the operation carries **on the router**, which is what
you compare against `show ip sla configuration` when the two disagree. `OperationTypeID` and
`OperationType` say what kind of test it is, `OperationName` and `OperationNameFull` name it,
and `Description` is free text.

**Where it runs and what it targets.** `NodeID` and `SourceNodeID` are the source, and
`TargetNodeID` is the target when the target is itself a monitored node. `DisplaySource` and
`DisplayTarget` are the readable strings the console shows and they are populated even when
the target is not a monitored node, which is why a report should prefer them over joining
`Orion.Nodes` twice.

**How it runs.** `Frequency` is the interval, `LifeTimeUtc` is how long the router keeps the
operation alive, and `IsAutoConfigured` records whether VNQM created the operation itself
rather than discovering one an engineer configured by hand. That flag matters before anybody
starts deleting things.

**How it is doing.** `OperationStateID`, `OperationStatusID`, `StatusMessage`,
`DateChangedUtc`, `OperationResultID` and `OperationResultRecordTime`, plus `Deleted`, which
is a soft-delete marker rather than a row that has gone away.

An operation declares seventeen navigation properties in total. Twelve lead down to things it
owns: ten statistics entities, covered in
[where the numbers actually live](#where-the-numbers-actually-live), plus
`Orion.IpSla.Operations.WebUri` for the console link and
`Orion.IpSla.Operations.ParameterInfo` for its VoIP parameters. The other five lead out to
objects the operation refers to, and two of those five go to the same entity:

| Navigation | Target | Kind |
|---|---|---|
| `Node` | `Orion.Nodes` | `System.Hosting` |
| `TargetNode` | `Orion.Nodes` | `System.Reference` |
| `OperationTypes` | `Orion.IpSla.OperationTypes` | `System.Reference` |
| `OperationStatus` | `Orion.IpSla.OperationStatuses` | `System.Reference` |
| `OperationStates` | `Orion.IpSla.OperationStates` | `System.Reference` |

Note the naming: `OperationStatus` is singular and `OperationTypes` and `OperationStates` are
plural. Nothing about that is guessable, so look it up rather than assuming.

From a node, the reverse edges are `Orion.Nodes.IpSlaOperations` for operations sourced on
that node and `Orion.Nodes.IpSlaOperationsAsTarget` for operations aimed at it. Both are
navigable, as [../schema/relationships.md](../schema/relationships.md) explains for every
relationship in the schema.

### Two different status columns on the same row

`Orion.IpSla.Operations` carries two status numbers and they do not mean the same thing.

`Status`, inherited from `System.DashboardEntity`, is the platform's `System.Int32` status
and joins to [`Orion.StatusInfo`](../reference/status-codes.md) like every other monitored
object. The status reference has a VNQM-specific note on code 0, Unknown: for IP SLA
operations it means the platform could not contact the router to collect the operation's
results, which is a different failure from the operation itself reporting a bad result.

`OperationStatusID` is a `System.Int16` and belongs to VNQM's own two-column lookup,
`Orion.IpSla.OperationStatuses` (`OperationStatusID`, `OperationStatus`). Do not join it to
`Orion.StatusInfo`: the types differ and so do the code sets. Read the lookup instead:

```sql
SELECT s.OperationStatusID, s.OperationStatus
FROM Orion.IpSla.OperationStatuses s
ORDER BY s.OperationStatusID
```

`OperationStateID` behaves the same way against `Orion.IpSla.OperationStates`
(`OperationStateID`, `OperationState`). State is the operation's lifecycle on the router;
status is its result. The specific integers each lookup contains are not recorded in the
schema, so enumerate them on your own server rather than hard-coding a number.

### Operation types

`Orion.IpSla.OperationTypes` has three columns: `OperationTypeID`, `OperationType` and
`MinIosVersionSupport`. That third column is the clearest evidence in the schema that these
are Cisco IOS operation types rather than a VNQM abstraction, and it is genuinely useful when
you are working out why an operation cannot be created on an older switch.

```sql
SELECT t.OperationTypeID, t.OperationType, t.MinIosVersionSupport
FROM Orion.IpSla.OperationTypes t
ORDER BY t.OperationType
```

The type also decides **which statistics entity carries your numbers**, which is the single
most important structural fact in this module and is covered in the next section.

There is a family of entities named `Orion.IpSla.OperationsHTTP`,
`Orion.IpSla.OperationsDNS`, `Orion.IpSla.OperationsDHCP`, `Orion.IpSla.OperationsFTP`,
`Orion.IpSla.OperationsTCP`, `Orion.IpSla.OperationsJitter`, `Orion.IpSla.OperationsMOS`,
`Orion.IpSla.OperationsUDPJitter` and `Orion.IpSla.OperationsVoIpUDPJitter`. Despite the
names these are **not** per-type configuration tables. Every one of them has a `SummaryDate`
column and aggregate columns such as `AVERAGEofAvgMOS`, `MAXofMaxJitter` and `TotalFailed`:
they are pre-built daily summary views for the console's reports. They declare no navigation
properties, so `OperationId` on them is a bare integer you join yourself.
`Orion.IpSla.VoipOperationsICMPEcho` and `Orion.IpSla.VoipOperationsUDPEcho` are the same
idea with underscore-separated column names (`Operation_Name`,
`MIN_of_Min_Round_Trip_Time`), which is what happens when a report designer's output becomes
a schema entity.

### Parameters and thresholds

`Orion.IpSla.OperationParameters` is a per-operation name/value bag keyed by
`OperationParameterTypeID`, with `Orion.IpSla.OperationParameterTypes` giving the readable
`OperationParameterType` name and a `DataTypeID` that resolves through
`Orion.IpSla.DataTypes`. `Orion.IpSla.VoipOperationParameterInfo` is the flattened version
for VoIP operations specifically, carrying `TargetPort`, `DhcpServer`, `DnsServer`,
`DnsHostName` and `Url` as real columns, and it is reachable from an operation as
`Orion.IpSla.Operations.ParameterInfo`.

Thresholds come in two layers:

- `Orion.IpSla.OperationTypesThresholds` holds the defaults for a whole operation type:
  `OperationTypeID`, `ThresholdTypeID`, `WarningLevel`, `ErrorLevel`, and separately
  `DefaultWarningLevel` and `DefaultErrorLevel` so the shipped default survives an edit.
- `Orion.IpSla.OperationThresholds` holds the per-operation override: `OperationInstanceID`,
  `ThresholdTypeID`, `WarningLevel`, `ErrorLevel`, `MaxLevel`.

`Orion.IpSla.ThresholdTypes` names the metric each threshold applies to and carries
`IsReverse`, which is what distinguishes a metric where higher is worse (jitter, latency,
packet loss) from one where lower is worse (MOS). Any report that colours a cell red needs
that flag, and neither threshold entity declares a navigation property, so all three joins
are written by hand on the id columns.

## Where the numbers actually live

This is the part that costs people the most time. There is no single "IP SLA results" table.
The results are split by operation family, then split again by retention rollup, and an
operation only writes to the entity that matches its type.

**Current values, one row per operation.**

| Entity | Carries | Navigable from `Operations` |
|---|---|---|
| `Orion.IpSla.OperationCurrentStats` | `RoundTripTime`, `Jitter`, `JitterSD`, `JitterDS`, `Latency`, `PacketLoss`, `PacketLossSD`, `PacketLossDS`, `MOS`, `HttpRtt`, `DnsRtt`, `TcpConnectRtt`, `TransactionRtt`, `OneWayDelaySD`, `OneWayDelayDS`, plus `SourceSiteID` and `TargetSiteID` | `CurrentStats` |
| `Orion.IpSla.OperationCurrentMos` | `Mos` only, with `SourceNodeID` and `RecordTimeUtc` | not navigable |
| `Orion.IpSla.OperationCurrentJitterLatencyPacketLoss` | the jitter, latency and packet loss trio without MOS | not navigable |
| `Orion.IpSla.OperationCurrentBasicMetrics` | `RoundTripTime` with `OperationName`, `OperationTypeName` and `StatusMessage` pre-joined | not navigable |
| `Orion.IpSla.OperationCurrentHttpMetrics`, `Orion.IpSla.OperationCurrentOneWayDelay`, `Orion.IpSla.OperationCurrentPathJitterLatencyPacketLoss` | the narrow per-family versions | not navigable |

`Orion.IpSla.OperationCurrentStats` is the one to reach for by default: it is the widest, and
it is the only one of the seven `Orion.IpSla.OperationCurrent*` entities with a
`System.Hosting` relationship back to `Orion.IpSla.Operations`, so
`cs.Operation.OperationName` works without a join. The other six are narrow views built for
particular console resources and give you bare `OperationInstanceID` values.

**History, several rows per operation.**

| Entity | Written by | Metrics |
|---|---|---|
| `Orion.IpSla.OperationStats` | every operation family | 47 columns: min/avg/max of round trip time, jitter (plain, SD and DS), latency, packet loss (plain, SD and DS), MOS, HTTP, DNS, TCP connect, transaction, one-way delay |
| `Orion.IpSla.UdpJitterOperationStats` | UDP jitter operations that produce MOS | round trip time, MOS, jitter, latency, packet loss |
| `Orion.IpSla.NonMOSUdpJitterOperationStats` | UDP jitter operations that do not | the same minus MOS |
| `Orion.IpSla.IcmpPathJitterOperationStats` | ICMP path jitter | the same minus MOS, but with the three round trip time columns declared as `System.Double` rather than `System.Int32` |
| `Orion.IpSla.NonPathOperationStats` | everything else | round trip time only |
| `Orion.IpSla.RpmOperationStats`, `Orion.IpSla.RpmTimestampOperationStats` | Juniper RPM operations | round trip time, jitter, packet loss |

All seven of those entities inherit from `System.StatisticsEntity` and all seven are
navigable from an operation, though the navigation property names are not consistent:
`Orion.IpSla.Operations.UdpJitterOperationStats`,
`Orion.IpSla.Operations.NonMOSUdpJitterOperationStats`,
`Orion.IpSla.Operations.IcmpPathJitterOperationStats`,
`Orion.IpSla.Operations.NonPathOperationStats`,
`Orion.IpSla.Operations.RpmOperationStats` and
`Orion.IpSla.Operations.RpmTimestampOperationStats` all exist, but `Orion.IpSla.OperationStats`
is reached as `Orion.IpSla.Operations.Stats`.

Because they inherit `System.StatisticsEntity`, every one of them also has
`ObservationTimestamp`, `ObservationFrequency` and `Weight` without declaring them.
The schema documents `Weight` as how long the row's value was collected over, in seconds, so
a row covering an hour carries 3600 and a row covering twenty seconds carries 20. That is
what makes `SUM(metric * Weight) / SUM(Weight)` the correct way to aggregate across intervals
of different lengths, and plain `AVG` the wrong way. The declared `RecordTime` column and the
inherited `ObservationTimestamp` are two separate columns, so check which one your data
actually populates before writing a predicate against it.

**`Orion.IpSla.OperationStats` is new in 2026.2.** It appears in the new-entity list of
[../reference/schema-changes-2026.1-to-2026.2.md](../reference/schema-changes-2026.1-to-2026.2.md),
and it is the consolidated table: 47 columns covering every metric family in one place. If
you are writing a new report and your server is on 2026.2, start here. If the report has to
run on an older release too, use the per-family entities, which have been there all along.

**Rollups.** Beneath all of that there is a third axis. Several result families exist as a
`...Detail` / `...Hourly` / `...Daily` triplet with progressively coarser retention:
`Orion.IpSla.OperationResultsDetail` / `Hourly` / `Daily`,
`Orion.IpSla.JitterOperationResultsDetail` / `Hourly` / `Daily`,
`Orion.IpSla.MosOperationResultsDetail` / `Hourly` / `Daily`,
`Orion.IpSla.OneWayDelayOperationResultsDetail` / `Hourly` / `Daily`,
`Orion.IpSla.HttpFtpOperationResultsDetail` / `Hourly` / `Daily` and
`Orion.IpSla.OperationStdDevResultsDetail` / `Hourly` / `Daily`. `Detail` holds raw samples
and is the largest and shortest-lived; `Daily` is what a month-long trend should read.
Choosing the wrong one either returns nothing, because detail data has already been rolled
up and discarded, or scans far more rows than the question needed. See
[../swql/performance.md](../swql/performance.md).

## MOS, jitter and the other quality metrics

These are the numbers people come to this module for, so the exact spellings matter.

**MOS** appears under four different spellings, and they are not interchangeable in a query:

| Spelling | Entities |
|---|---|
| `MOS` | `Orion.IpSla.OperationCurrentStats`, `Orion.IpSla.MosOperationResultsDetail`, `Orion.IpSla.CallPathMetrics`, `Orion.IpSla.AlertQos` |
| `MinMOS`, `AvgMOS`, `MaxMOS` | `Orion.IpSla.OperationStats`, `Orion.IpSla.UdpJitterOperationStats`, `Orion.IpSla.JitterMosOperationResults`, `Orion.IpSla.MosOperationResultsHourly`, `Orion.IpSla.MosOperationResultsDaily` |
| `Mos` | `Orion.IpSla.OperationCurrentMos`, and only there |
| `OrigMOS`, `DestMOS` | `Orion.IpSla.VoipCallDetails`, `Orion.IpSla.VoipCallDetailsHist`, `Orion.IpSla.VoipCalls` |

`Orion.IpSla.VoipCallMosMMA` is a fifth shape again: it is a per-call-manager time series
whose columns are the generic `MinValue`, `MaxValue` and `AvgValue`, with the metric implied
by the entity name. Its three siblings `Orion.IpSla.VoipCallJitterMMA`,
`Orion.IpSla.VoipCallLatencyMMA` and `Orion.IpSla.VoipCallPacketLossMMA` have exactly the
same six columns. Selecting `AvgValue` from the wrong one of the four is a mistake nothing in
the result will reveal, so alias the column to something that names the metric.

**Jitter** splits by direction on the synthetic side and by call leg on the passive side:

- `JitterSD` is source to destination, `JitterDS` is destination to source, and plain
  `Jitter` is the combined figure. All three appear on
  `Orion.IpSla.OperationCurrentStats` and, as min/avg/max triples, on
  `Orion.IpSla.OperationStats` and `Orion.IpSla.JitterMosOperationResults`. The narrower
  per-family stats entities carry only the combined `MinJitter` / `AvgJitter` / `MaxJitter`.
- `PacketLossSD` and `PacketLossDS` follow the identical pattern, as do `OneWayDelaySD` and
  `OneWayDelayDS`.
- On calls, the split is `OrigJitter` and `DestJitter`, with `OrigLatency` / `DestLatency`
  and `OrigPacketLoss` / `DestPacketLoss` alongside.

A one-way problem is invisible in the combined column and obvious in the SD/DS pair, which is
the entire reason the directional columns exist. If you are diagnosing "calls are fine one
way", the SD/DS columns are the query.

The schema does not carry descriptions for any of these columns, so the **scale and units are
not established by this data**. They are listed in
[what is not verified here](#what-is-not-verified-here) with a query that shows you the
observed range on your own server.

## The call manager side

`Orion.IpSla.CCMMonitoring` is one row per monitored call manager and it is the hub of the
passive half. It inherits from `System.ManagedEntity` and is hosted by a node, so
`Orion.Nodes.CCMMonitoring` navigates down to it and `Orion.IpSla.CCMMonitoring.Node`
navigates back.

Its 23 properties cover identity (`CcmName`, `ClusterName`, `ClusterNodeID`, `Version`,
`Caption`, `SysName`), polling configuration (`MonitoringEnabled`, `PollingFrequency`,
`PollingStatus`, `SipTrunkMonitoringEnabled`, `SipTrunkPollingFrequency`,
`UtcOffsetMinutes`) and state (`Status`, `RecordTime`, `Deleted`, the `UnManaged` trio).
`CCMMonitoringTypeID` resolves through `Orion.IpSla.CCMMonitoringType`, whose `Code` and
`Description` distinguish the vendor families, and the navigation for that is
`Orion.IpSla.CCMMonitoring.MonitoringType`.

`UtcOffsetMinutes` deserves a sentence on its own. A call manager reports call detail records
in its own local time, and VNQM records the offset rather than normalising, so any
cross-cluster comparison of call times has to account for it. See
[../swql/date-and-time.md](../swql/date-and-time.md) before writing that arithmetic, because
the obvious approach with `GetUtcDate()` and the `AddX` functions produces wrong offsets.

Thirteen entities hang off `CCMMonitoring` as hosted children, which is the fastest way to
see the shape of this half of the module:

```bash
python3 tools/schema_query.py show Orion.IpSla.CCMMonitoring
```

`Region`, `CCMGateways`, `CCMPhones`, `CCMSipTrunk`, `CurrentStats`, `Stats`,
`VoipSuccessFailedCalls`, `VoipCallDetails`, the four `VoipCall*MMA` series and `WebUri`.

### Regions

`Orion.IpSla.CCMRegions` is small and structurally important: `RegionID`,
`CCMMonitoringID`, `RegionIndex`, `RegionName`, `DetailsUrl`. A region in Cisco Unified
Communications Manager is the unit that codec and bandwidth policy is set on, which is why
call quality reported by region is a meaningful grouping rather than an arbitrary one.

Its three outbound navigations are the interesting part:
`Orion.IpSla.CCMRegions.CallDetailsAsOrigin` and
`Orion.IpSla.CCMRegions.CallDetailsAsDestination` both lead to
`Orion.IpSla.VoipCallDetails`, and `Orion.IpSla.CCMRegions.CCMGateways` leads to the
gateways in that region. The two call-detail edges exist because a call has two ends and
either one can be the region you are asking about, and forgetting that is how a
region-quality report ends up counting only half its calls.

### Phones

`Orion.IpSla.CCMPhones` is the phone inventory: `ID`, `CCMMonitoringID`, `Name`,
`Description`, `MACAddress`, `IPAddress`, `IpAddressRaw`, `Extension`, `Location`,
`RegionID`, `Status`, `Licensed`, `DetailsUrl` and the `UnManaged` trio, which it declares
itself even though it inherits from plain `System.Entity` rather than `System.ManagedEntity`.

`Licensed` is the one that catches people out. VNQM discovers every phone the call manager
knows about, but only monitors the ones covered by the licence, so a phone with
`Licensed = FALSE` is present in the inventory and has no useful status. Filter on it before
concluding that a site has gone dark.

The gap in this entity is navigation. It declares `RegionID` but has **no `Region`
navigation property**; its only inbound edge is `Orion.IpSla.CCMPhones.CCMMonitoring`, and
its two outbound edges are the same `CallDetailsAsOrigin` and `CallDetailsAsDestination`
pair. To put a region name next to a phone you join `Orion.IpSla.CCMRegions` on `RegionID`
yourself.

`Orion.IpSla.CCMPhoneDetails` is an extension entity carrying `StatusDescription`,
`Location`, `Extension` and `PhoneRegion` for a `PhoneID`. Vendor-specific extras live in
`Orion.IpSla.CCMPhonesCiscoData` and `Orion.IpSla.CCMPhonesAvayaData`, and the phone status
history is the `Orion.IpSla.CCMPhoneStats` / `Hourly` / `Daily` / `Detail` family, whose
`AvgStatus`, `MinStatus` and `MaxStatus` columns are averaged status integers rather than
measurements.

### Gateways as the call manager sees them

`Orion.IpSla.CCMGateways` is registration state, not utilisation: `GatewayID`,
`CCMMonitoringID`, `GatewayIndex`, `Name`, `Description`, `IpAddress`, `IpAddressRaw`,
`ProductType`, `RegionID`, `Status`, `LastStatusUpdatedUTC`, `LastRegisteredUTC`,
`DetailsUrl` and the `UnManaged` trio. Unlike phones it **does** carry a
`Orion.IpSla.CCMGateways.Region` navigation property, so region names come for free here and
have to be joined by hand one entity over. `Orion.IpSla.CCMH323Devices` is nearly the same shape for
H.323 endpoints. It adds `StatusReason`, drops `DetailsUrl` and the `UnManaged` trio, and
declares `ProductType` as a `System.Int32` where `Orion.IpSla.CCMGateways` declares it as a
`System.String`, so the two do not interchange in a union.

`Orion.IpSla.ConnectedCCMGateways` and `Orion.IpSla.ConnectedPhonesReport` are flattened
report views over the same data, with the call manager name and region already resolved to
strings. They declare no navigation properties, and note that
`Orion.IpSla.ConnectedCCMGateways.Status` is a `System.String` while
`Orion.IpSla.CCMGateways.Status` is a `System.Int32`. Check the type before writing a
comparison.

### Registration counts

`Orion.IpSla.CallManagerCurrentStats` is the current registration snapshot per call manager
and `Orion.IpSla.CallManagerStats` is the same thing as a time series. Both carry
`RegisteredPhones`, `UnRegisteredPhones`, `RejectedPhones`, `TotalPhones` and the matching
four gateway counters, plus percentage versions of each. The difference in type is a real
trap: the percentages are `System.Int32` on `CallManagerCurrentStats` and `System.Double` on
`CallManagerStats`.

`Orion.IpSla.CallManagerCurrentStats` also has four extra columns the historical entity does
not: `ActivePhonesPercentage`, `InactivePhonesPercentage`, `ActiveGatewaysPercentage` and
`InactiveGatewaysPercentage`. `Orion.IpSla.CCMStats` is a third shape again, with min, avg
and max of each counter keyed by `NodeID` and `RecordTime`.

## Calls and call detail records

Four entities describe calls and they answer different questions.

| Entity | Rows | Navigations | Use it for |
|---|---|---|---|
| `Orion.IpSla.VoipCallDetails` | 67 columns, one per call, live retention | 7 | Anything analytical. This is the one to use |
| `Orion.IpSla.VoipCallDetailsHist` | the same 67 columns, byte for byte | none | The archived twin, after retention moves rows out |
| `Orion.IpSla.VoipCalls` | 17 columns, no ids beyond `CallID` | none | A narrow console view; region names are strings |
| `Orion.IpSla.CDRDetails` | 29 columns of raw CDR fields | none | The protocol-level detail the analytical view drops |

`Orion.IpSla.VoipCallDetails` is where a call quality investigation starts. Its columns come
in matched origin and destination pairs, which is the structure of a call detail record:
`OrigDeviceName` / `DestDeviceName`, `OrigPhoneName` / `DestPhoneName`, `OrigGatewayName` /
`DestGatewayName`, `OrigCCMPhoneExtension` / `DestCCMPhoneExtension`, `OrigCCMRegionName` /
`DestCCMRegionName`, `OrigCause_value` / `DestCause_value`, and the four quality pairs
`OrigMOS` / `DestMOS`, `OrigJitter` / `DestJitter`, `OrigLatency` / `DestLatency`,
`OrigPacketLoss` / `DestPacketLoss`.

Alongside those it carries the party numbers (`CallingPartyNumber`,
`OriginalCalledPartyNumber`, `FinalCalledPartyNumber`, `LastRedirectDn`), the three
timestamps (`DateTime`, `DateTimeOrigination`, `DateTimeDisconnect`), `Duration`, and five
boolean or near-boolean flags that are the fastest way to filter: `CallSuccess`,
`ZeroDurationCall`, `ConferenceCall`, `CallWithIssue`, plus the integer `OrigFailedCall` and
`DestFailedCall`.

Its seven navigation properties are the reason to prefer it over the flat views:
`Orion.IpSla.VoipCallDetails.OriginRegion`, `.DestinationRegion`, `.OriginGateway`,
`.DestinationGateway`, `.OriginPhone`, `.DestinationPhone` and `.CCMMonitoring`. The first
six are `System.Reference` and the last is `System.Hosting`.

`Orion.IpSla.CDRDetails` is the layer below: `Pkid` (the call manager's own GUID for the
record), the media transport addresses and ports as raw integers, the partition names for
each number, the `...OnBehalfOf` fields that explain who terminated or redirected the call,
precedence levels, and the media and video codec capability integers. It joins to the
analytical view on `CCMMonitoringID` and `CallID`, and it declares no navigation properties.

`Orion.IpSla.VoipSuccessFailedCalls` is the cheap aggregate: `NodeID`, `CcmID`,
`DateTimeUTC`, `Success` and `Failed`, hosted by `CCMMonitoring`. If the question is "how
many calls failed yesterday" rather than "which calls failed yesterday", read this and do not
touch the 67-column table at all.

## Gateways, PRI trunks and SIP trunks

The polled side of gateway monitoring is a three-level hierarchy.

`Orion.IpSla.VoipGateways` is a monitored gateway: `VoipGatewayID`, `NodeID`, `DisplayName`,
`DeviceName`, `SysName`, `Status`, `StatusName`, `MaxConcurrentSipCalls`,
`SipTrunkMonitoringEnabled`, `LastResultRecordTime`, `DateTime`, `DetailsUrl` and the
`UnManaged` trio. It inherits `System.ManagedEntity`, is hosted by `Orion.Nodes`, and is
reached from a node as `Orion.Nodes.VoipGateways`.

`Orion.IpSla.VoipGatewayEndpoints` is a **PRI trunk** on that gateway, which is what the
console calls it and what the NetObject display name says, even though the entity name says
endpoint. It has `VoipGatewayEndpointID`, `VoipGatewayID`, `IfName`, `IfIndex`,
`DisplayName`, `EndPointType`, `Status` and `DetailsUrl`, and it is reached from a gateway as
`Orion.IpSla.VoipGateways.VoipGatewaysEndpoints`, which is plural in the middle as well as at
the end.

`Orion.IpSla.VoipGatewayChannels` is a single B-channel: `VoipGatewayChannelID`,
`VoipGatewayEndpointID`, `IfName`, `IfIndex`, `ChannelNumber`. It declares **no navigation
properties at all**, so the join up to the trunk is written by hand on
`VoipGatewayEndpointID`. `Orion.IpSla.VoipGatewayChannelStats` counts calls per channel per
`RecordTime`, split by `CallOrigin` and `VoipGatewayChannelMediaTypeID`.

Utilisation is reported at two levels with the same column vocabulary. Both
`Orion.IpSla.VoipGatewayEndpointStats` (per trunk) and
`Orion.IpSla.VoipGatewayDetailStats` (per gateway, with a `TrunkCount`) carry min, max and
average of `Utilization`, `VoiceIncomingUtilization`, `VoiceOutgoingUtilization`,
`DataIncomingUtilization`, `DataOutgoingUtilization` and `ChannelCount`. The separation of
voice from data on a PRI is the point: a trunk at 95 percent that is 90 percent data is a
completely different conversation from one that is 90 percent voice.
`Orion.IpSla.PRIGatewayUtilization` is a flattened per-gateway view of the same averages with
a `Node` column that is a `System.String`, not an id, and both it and the two stats entities
have current-value twins (`Orion.IpSla.VoipGatewayEndpointCurrentStats`,
`Orion.IpSla.VoipGatewayDetailCurrentStats`).

SIP trunks are split the same way the gateways are, by who reports them:

- `Orion.IpSla.CCMSipTrunk` is a SIP trunk **as the call manager describes it**, with
  `SipTrunkGuid`, `DevicePool`, `Location`, `SipProfile`, `SecurityProfile`, `MTPOrigCodec`
  and `DefaultDtmfCapability`. Its activity entities are
  `Orion.IpSla.CCMSipTrunkCallActivity` and `Orion.IpSla.CCMSipTrunkCurrentCallActivity`
  (`CallsActive`, `CallsAttempted`, `CallsCompleted`, `CallsInProgress`, `VCallsActive`,
  `VCallsCompleted`), plus `Orion.IpSla.CCMSipTrunkAvailability` and
  `Orion.IpSla.CCMSipTrunkDestinations`.
- `Orion.IpSla.VoipGatewaySipTrunks` is a SIP trunk **as the polled gateway reports it**,
  with `SipTrunkName`, `DialPeer` and `Status`, and its own
  `Orion.IpSla.VoipGatewaySipTrunkCallActivity`,
  `Orion.IpSla.VoipGatewaySipTrunkStatusStats` and
  `Orion.IpSla.VoipGatewaySipTrunkUtilization`.

`Orion.IpSla.VoipGatewaySipStats` counts SIP response classes on a gateway:
`SipStatsSuccess`, `SipStatsRedirect`, `SipStatsErrClient`, `SipStatsErrServer`,
`SipStatsGlobalFail` and `SipStatsRetry`. **All six of those widened from `System.Int32` to
`System.Int64` in 2026.2**, recorded in
[../reference/schema-changes-2026.1-to-2026.2.md](../reference/schema-changes-2026.1-to-2026.2.md).
A SWQL query does not care. A typed client that binds those columns to a 32-bit integer
field does, and that is exactly the class of change that fails months after an upgrade.

## Sites, call paths and hops

`Orion.IpSla.Sites` is VNQM's own site model, separate from the platform's group and
container features: `SiteID`, `Name`, `IPAddress`, `NodeID`, `RegionID`, `IsHub` and
`IsAutoConfigured`. It is hosted by a node and reached as `Orion.Nodes.IpSlaSite`. `IsHub` is
what makes hub-and-spoke reporting possible, because in a hub-and-spoke WAN the interesting
call paths all pass through the hub.

Sites connect to measurements through `Orion.IpSla.OperationCurrentStats`, which is the only
statistics entity carrying `SourceSiteID` and `TargetSiteID`. That is the join that turns
"operation 41 is degraded" into "the path from the Manchester branch to the London hub is
degraded".

Two entities pre-compute the site-to-site view:

- `Orion.IpSla.CallPathMetrics` is the compact one: `SourceSiteName`, `DestSiteName`,
  `SourceSiteID`, `DestSiteID`, `DateTime`, `MOS`, `Jitter`, `Latency`, `PacketLoss`.
- `Orion.IpSla.AlertQos` is the wide one, adding `CallPathID`, `CallPathName`, source and
  destination node ids, names and IP addresses, `IpSlaOp`, `IsHub`, `IsAutoConfigured` and a
  `Status` that is a `System.Char` rather than an integer, so it does not join to
  `Orion.StatusInfo`.

Neither declares a navigation property, and both are read-only views.

Path hops are the traceroute-style detail for path-capable operations.
`Orion.IpSla.Paths` (`PathID`, `MaxHopIndex`, `PathLength`) and `Orion.IpSla.PathHops`
(`PathID`, `HopIndex`, `IpAddress`, `IpAddressV4`) describe the route, and
`Orion.IpSla.PathHopOperationCurrentStats` and `Orion.IpSla.PathHopOperationResults` carry
per-hop `RoundTripTime`, `Jitter`, `Latency` and `PacketLoss`. Both are reached from an
operation, as `Orion.IpSla.Operations.PathHopCurrentStats` and
`Orion.IpSla.Operations.PathHopStats`, and the navigation back from either is `Operations`,
plural. Per-hop numbers are how you tell a degraded WAN circuit from a degraded far end.

## Verbs

**VNQM publishes no verbs in the 2026.2 schema, and declares no CRUD operations either.**

That is a statement about the extracted data, and it is worth being exact about it. Of the
140 `Orion.IpSla.` entities, zero appear in
[`data/schema/2026.2/verbs.json`](../../data/schema/2026.2/verbs.json), zero declare
`create`, `update` or `delete`, and zero declare any access-control requirement. Confirm it
offline:

```bash
python3 tools/schema_query.py verbs --grep IpSla
```

which returns `0 verb(s)`. The whole module is a read surface through SWIS. Compare
[../reference/verb-index.md](../reference/verb-index.md), which enumerates every verb the
platform publishes, and note the absence.

The practical consequences:

- **Creating or editing an IP SLA operation is not a SWIS operation.** It is done in the
  VNQM part of the web console, or on the router itself and then discovered. There is no
  `Orion.IpSla.Operations` create verb to call and no CRUD create to fall back on.
- **`Orion.IpSla.Operations` inherits `UnManaged` but exposes no `Unmanage` verb.** Only
  six entities across the whole platform publish `Unmanage`, and none of them is a VNQM
  entity. To take an IP SLA operation out of alerting scope through the API you have two
  verified routes: unmanage the **node** that hosts it with
  `Orion.Nodes.Unmanage(netObjectId, unmanageTime, remanageTime, isRelative, allowOverlapping)`,
  which stops polling everything on that node, or suppress alerts on the operation's own
  `Uri` with
  `Orion.AlertSuppression.SuppressAlerts(entityUris, suppressFrom, suppressUntil, allowOverlapping, reason)`,
  which is narrower and is usually what you actually want. Both are covered in
  [../swis/verb-catalog.md](../swis/verb-catalog.md).

Getting the operation's URI for the second route is a one-line query, since `Uri` is
inherited from `System.Entity` on every entity in the schema:

```sql
SELECT TOP 10 o.OperationInstanceID, o.OperationName, o.Uri
FROM Orion.IpSla.Operations o
WHERE o.Deleted = FALSE
  AND o.OperationName LIKE @namePattern
```

```powershell
$swis = Connect-Swis -Hostname orion.example.com -Credential $cred

$uris = Get-SwisData $swis @"
SELECT o.Uri
FROM Orion.IpSla.Operations o
WHERE o.Deleted = FALSE AND o.NodeID = @nodeId
"@ @{ nodeId = 42 }

# Suppress alerts on those operations for a four hour change window.
Invoke-SwisVerb $swis 'Orion.AlertSuppression' 'SuppressAlerts' @(
    $uris,
    (Get-Date).ToUniversalTime().ToString('o'),
    (Get-Date).ToUniversalTime().AddHours(4).ToString('o'),
    $false,
    'CHG0041288 WAN circuit replacement'
) | Out-Null
```

Because alert suppression is inherited, suppressing the hosting node's URI also suppresses
every IP SLA operation on it. Suppressing the operation URIs individually, as above, leaves
the rest of the node alerting normally.

If you are on a version other than 2026.2, ask your own server rather than trusting this
page, since a later release could add verbs here:

```sql
SELECT v.Entity.FullName AS EntityName, v.Name AS VerbName, v.CanInvoke, v.Summary
FROM Metadata.Verb v
WHERE v.Entity.FullName LIKE 'Orion.IpSla.%'
  AND v.IsInternal = FALSE
ORDER BY v.Entity.FullName, v.Name
```

More on that pattern in [../swis/metadata-introspection.md](../swis/metadata-introspection.md).

## Worked queries

Every query below has been validated against the 2026.2 schema with
`tools/validate_swql.py`. More of the same live in
[`../../scripts/swql/15-voip-and-web-transactions.swql`](../../scripts/swql/15-voip-and-web-transactions.swql).

### 1. The IP SLA operation inventory, with every lookup resolved

The three lookup navigations are the point here. Writing them out once shows how the
singular `OperationStatus` and the plural `OperationTypes` and `OperationStates` differ, and
selecting both `Node.Caption` and `TargetNode.Caption` shows the two edges to `Orion.Nodes`
side by side. `Deleted` is a soft-delete flag, so filtering it is not optional.

```sql
SELECT TOP 200
    o.OperationInstanceID,
    o.IpSlaOperationNumber,
    o.OperationName,
    o.OperationTypes.OperationType AS OperationTypeName,
    o.OperationStatus.OperationStatus AS OperationStatusName,
    o.OperationStates.OperationState AS OperationStateName,
    o.Node.Caption AS SourceNodeName,
    o.TargetNode.Caption AS TargetNodeName,
    o.DisplaySource,
    o.DisplayTarget,
    o.Frequency,
    o.IsAutoConfigured
FROM Orion.IpSla.Operations o
WHERE o.Deleted = FALSE
ORDER BY o.OperationName
```

### 2. IP SLA operations that are failing right now

Two status columns, two different meanings, and both are worth seeing. `StatusMessage`
usually explains the failure well enough that you do not have to log into the router.
Filtering `UnManaged = FALSE` is the difference between "actually broken" and "in a
maintenance window", and per the [status reference](../reference/status-codes.md) a
platform status of 0 on an IP SLA operation specifically means the platform could not reach
the router to collect results, which is a polling problem rather than a network quality
problem.

```sql
SELECT TOP 100
    o.OperationName,
    o.OperationTypes.OperationType AS OperationTypeName,
    o.DisplaySource,
    o.DisplayTarget,
    st.StatusName AS PlatformStatus,
    o.OperationStatus.OperationStatus AS OperationStatusName,
    o.StatusMessage,
    o.DateChangedUtc,
    o.OperationResultRecordTime
FROM Orion.IpSla.Operations o
JOIN Orion.StatusInfo st ON st.StatusId = o.Status
WHERE o.Deleted = FALSE
  AND o.UnManaged = FALSE
  AND o.Status <> 1
ORDER BY st.Ranking, o.DateChangedUtc DESC
```

### 3. Current call quality per operation, worst first

`Orion.IpSla.OperationCurrentStats` is the only current-value entity with a hosting
relationship back to the operation, so `cs.Operation.*` needs no join. Selecting `JitterSD`
and `JitterDS` next to the combined `Jitter` is what turns "the call is bad" into "the call
is bad in one direction".

```sql
SELECT TOP 50
    cs.Operation.OperationName AS OperationName,
    cs.Operation.DisplaySource AS Source,
    cs.Operation.DisplayTarget AS Target,
    cs.RecordTime,
    cs.MOS,
    cs.Jitter,
    cs.JitterSD,
    cs.JitterDS,
    cs.Latency,
    cs.PacketLoss,
    cs.PacketLossSD,
    cs.PacketLossDS,
    cs.RoundTripTime
FROM Orion.IpSla.OperationCurrentStats cs
WHERE cs.MOS IS NOT NULL
ORDER BY cs.MOS
```

### 4. Call quality by region pair

This is the report a voice team actually asks for. Grouping by the origin and destination
region names gives one row per path through the dial plan, and the origin and destination
MOS columns are separate because the two ends of a call do not experience the same thing.
`Orion.IpSla.VoipCallDetails` inherits from `System.StatisticsEntity` and is one of the
largest tables in the module, so the time bound is mandatory rather than polite.

```sql
SELECT TOP 100
    cd.OrigCCMRegionName,
    cd.DestCCMRegionName,
    COUNT(cd.ID) AS Calls,
    AVG(cd.OrigMOS) AS AvgOriginMOS,
    AVG(cd.DestMOS) AS AvgDestinationMOS,
    AVG(cd.OrigJitter) AS AvgOriginJitter,
    AVG(cd.DestJitter) AS AvgDestinationJitter,
    AVG(cd.OrigLatency) AS AvgOriginLatency,
    AVG(cd.DestLatency) AS AvgDestinationLatency,
    AVG(cd.Duration) AS AvgDurationSeconds
FROM Orion.IpSla.VoipCallDetails cd
WHERE cd.DateTime >= @startUtc
  AND cd.DateTime < @endUtc
  AND cd.CallSuccess = TRUE
  AND cd.ZeroDurationCall = FALSE
GROUP BY cd.OrigCCMRegionName, cd.DestCCMRegionName
ORDER BY AVG(cd.DestMOS)
```

Excluding zero-duration calls matters: a call that never connected has no meaningful MOS,
and leaving those rows in drags the average toward a number that describes nothing.

### 5. Failed calls, with both ends resolved

The navigation properties earn their keep here. `OriginPhone`, `DestinationPhone`,
`OriginRegion`, `DestinationRegion` and `CCMMonitoring` are all followed in the select list,
which is a lot of context for a query with a single `FROM` clause. `OrigCause_value` and
`DestCause_value` are the codes the call manager recorded for why each leg ended.

```sql
SELECT TOP 100
    cd.DateTimeOrigination,
    cd.CallingPartyNumber,
    cd.FinalCalledPartyNumber,
    cd.Duration,
    cd.OrigCause_value,
    cd.DestCause_value,
    cd.OriginPhone.Name AS OriginPhoneName,
    cd.OriginPhone.Location AS OriginPhoneLocation,
    cd.DestinationPhone.Name AS DestinationPhoneName,
    cd.OriginRegion.RegionName AS OriginRegionName,
    cd.DestinationRegion.RegionName AS DestinationRegionName,
    cd.CCMMonitoring.CcmName AS CallManagerName,
    cd.ConferenceCall,
    cd.CallWithIssue
FROM Orion.IpSla.VoipCallDetails cd
WHERE cd.DateTime >= @startUtc
  AND cd.DateTime < @endUtc
  AND cd.CallSuccess = FALSE
ORDER BY cd.DateTime DESC
```

For the "how bad is it overall" version of the same question, read
`Orion.IpSla.VoipSuccessFailedCalls` instead. It is five columns wide and pre-aggregated:

```sql
SELECT TOP 100
    f.CCMMonitoring.CcmName AS CallManagerName,
    f.DateTimeUTC,
    f.Success,
    f.Failed
FROM Orion.IpSla.VoipSuccessFailedCalls f
WHERE f.DateTimeUTC >= @startUtc
  AND f.DateTimeUTC < @endUtc
ORDER BY f.Failed DESC
```

### 6. Site-to-site call path quality

`Orion.IpSla.OperationCurrentStats` is joined to `Orion.IpSla.Sites` twice, once for each
end. `IsHub` on the source side tells you whether this is a spoke-to-hub path or a
spoke-to-spoke one, which changes what a bad number means.

```sql
SELECT TOP 100
    src.Name AS SourceSite,
    src.IsHub AS SourceIsHub,
    dst.Name AS DestinationSite,
    dst.IsHub AS DestinationIsHub,
    o.OperationName,
    cs.RecordTime,
    cs.MOS,
    cs.Jitter,
    cs.Latency,
    cs.PacketLoss
FROM Orion.IpSla.OperationCurrentStats cs
JOIN Orion.IpSla.Operations o ON o.OperationInstanceID = cs.OperationInstanceID
JOIN Orion.IpSla.Sites src ON src.SiteID = cs.SourceSiteID
JOIN Orion.IpSla.Sites dst ON dst.SiteID = cs.TargetSiteID
WHERE cs.MOS IS NOT NULL
ORDER BY cs.MOS
```

If your installation populates the pre-built call path view, the same answer is a
single-entity read, at the cost of not being able to filter on anything the view does not
carry:

```sql
SELECT TOP 100
    m.SourceSiteName,
    m.DestSiteName,
    m.DateTime,
    m.MOS,
    m.Jitter,
    m.Latency,
    m.PacketLoss
FROM Orion.IpSla.CallPathMetrics m
WHERE m.DateTime >= @startUtc
ORDER BY m.MOS
```

### 7. A quality trend for a window, from the consolidated statistics entity

`Orion.IpSla.OperationStats` is new in 2026.2 and is the only history entity that covers
every operation family, so a trend report no longer has to know which family an operation
belongs to. Grouping by the navigated operation name keeps the output readable.

```sql
SELECT TOP 100
    s.Operation.OperationName AS OperationName,
    s.Operation.DisplaySource AS Source,
    s.Operation.DisplayTarget AS Target,
    COUNT(s.RecordTime) AS Samples,
    AVG(s.AvgMOS) AS MeanMOS,
    MIN(s.MinMOS) AS WorstMOS,
    AVG(s.AvgJitter) AS MeanJitter,
    MAX(s.MaxJitter) AS PeakJitter,
    AVG(s.AvgLatency) AS MeanLatency,
    AVG(s.AvgPacketLoss) AS MeanPacketLoss,
    AVG(s.AvgRoundTripTime) AS MeanRoundTripTime
FROM Orion.IpSla.OperationStats s
WHERE s.RecordTime >= @startUtc
  AND s.RecordTime < @endUtc
GROUP BY s.Operation.OperationName, s.Operation.DisplaySource, s.Operation.DisplayTarget
ORDER BY AVG(s.AvgMOS)
```

`AVG(s.AvgMOS)` averages an average, which weights every polling interval equally regardless
of how many probes it contained. That is the right shape for a trend line and the wrong
shape for a service level number.

### 8. Phones by region, with a readable status

`Orion.IpSla.CCMPhones` declares `RegionID` and no `Region` navigation, so the region join is
explicit. `Licensed` is selected rather than filtered so that an unlicensed phone shows up as
what it is instead of vanishing from the report.

```sql
SELECT TOP 200
    r.RegionName,
    p.Name AS PhoneName,
    p.Extension,
    p.IPAddress,
    p.MACAddress,
    p.Location,
    st.StatusName,
    p.Licensed,
    p.CCMMonitoring.CcmName AS CallManagerName
FROM Orion.IpSla.CCMPhones p
JOIN Orion.IpSla.CCMRegions r ON r.RegionID = p.RegionID
JOIN Orion.StatusInfo st ON st.StatusId = p.Status
WHERE p.UnManaged = FALSE
ORDER BY r.RegionName, p.Extension
```

### 9. Call manager registration health

Registration counts are the first thing to look at when several sites report problems at
once, because a call manager that has lost a hundred phone registrations is not a network
quality problem at all.

```sql
SELECT TOP 50
    cm.CcmName,
    cm.ClusterName,
    cm.Node.Caption AS NodeName,
    cs.DateTime,
    cs.RegisteredPhones,
    cs.UnRegisteredPhones,
    cs.RejectedPhones,
    cs.TotalPhones,
    cs.RegisteredPhonesPercentage,
    cs.RegisteredGateways,
    cs.UnRegisteredGateways,
    cs.TotalGateways
FROM Orion.IpSla.CallManagerCurrentStats cs
JOIN Orion.IpSla.CCMMonitoring cm ON cm.NodeID = cs.NodeID
ORDER BY cs.UnRegisteredPhones DESC
```

### 10. PRI trunk utilisation, voice separated from data

`Orion.IpSla.PRIGatewayUtilization` is hosted by the gateway, so `u.VoipGateways.*` navigates
up without a join, and the voice and data columns are kept apart because a trunk saturated by
data has a completely different remedy from one saturated by calls.

```sql
SELECT TOP 100
    u.VoipGateways.DisplayName AS GatewayName,
    u.VoipGateways.Node.Caption AS NodeName,
    u.IfName AS TrunkInterface,
    u.RecordTimeUtc,
    u.AvgChannelCount,
    u.AvgVoiceIncomingUtilization,
    u.AvgVoiceOutgoingUtilization,
    u.AvgDataIncomingUtilization,
    u.AvgDataOutgoingUtilization
FROM Orion.IpSla.PRIGatewayUtilization u
WHERE u.RecordTimeUtc >= @startUtc
  AND u.RecordTimeUtc < @endUtc
ORDER BY u.AvgVoiceOutgoingUtilization DESC
```

### 11. SIP error classes per gateway

The six `SipStats*` counters split SIP responses by class, and a rising `SipStatsErrServer`
against a flat `SipStatsSuccess` is a far-end problem rather than a local one.

```sql
SELECT TOP 100
    s.VoipGateway.DisplayName AS GatewayName,
    s.VoipGateway.Node.Caption AS NodeName,
    s.RecordTimeUtc,
    s.SipStatsSuccess,
    s.SipStatsRedirect,
    s.SipStatsErrClient,
    s.SipStatsErrServer,
    s.SipStatsGlobalFail,
    s.SipStatsRetry
FROM Orion.IpSla.VoipGatewaySipStats s
WHERE s.RecordTimeUtc >= @startUtc
  AND s.RecordTimeUtc < @endUtc
ORDER BY s.SipStatsErrServer DESC
```

### 12. Per-hop detail for one degraded operation

When a path-capable operation is bad, this says which hop is responsible. The navigation back
from a hop result to its operation is `Operations`, plural.

```sql
SELECT TOP 100
    h.Operations.OperationName AS OperationName,
    h.HopIndex,
    h.HopIpAddress,
    h.RecordTime,
    h.RoundTripTime,
    h.Jitter,
    h.Latency,
    h.PacketLoss
FROM Orion.IpSla.PathHopOperationCurrentStats h
WHERE h.Operations.OperationInstanceID = @operationInstanceId
ORDER BY h.HopIndex
```

### 13. Every VoIP object on one node

A single query that walks all five of the node's VNQM edges, useful when somebody asks "what
does VNQM know about this router".

```sql
SELECT TOP 100
    n.Caption AS NodeName,
    n.IpSlaSite.Name AS SiteName,
    n.IpSlaSite.IsHub AS IsHubSite,
    n.CCMMonitoring.CcmName AS CallManagerName,
    n.CCMMonitoring.ClusterName AS ClusterName,
    n.VoipGateways.DisplayName AS VoipGatewayName,
    n.VoIPInfrastructure.DisplayName AS VoipInfrastructureName,
    n.IpSlaOperations.OperationName AS SourcedOperation,
    n.IpSlaOperationsAsTarget.OperationName AS TargetedOperation
FROM Orion.Nodes n
WHERE n.NodeID = @nodeId
```

## Gotchas

**There are two gateway models and they are unrelated in the schema.**
`Orion.IpSla.CCMGateways` is the call manager's view, keyed by `GatewayID` and carrying
registration state. `Orion.IpSla.VoipGateways` is the polled view, keyed by `VoipGatewayID`
and carrying utilisation. No navigation property connects them. The same split repeats for
SIP trunks, `Orion.IpSla.CCMSipTrunk` against `Orion.IpSla.VoipGatewaySipTrunks`.

**A PRI trunk is called an endpoint in the entity name.**
`Orion.IpSla.VoipGatewayEndpoints` has the NetObject display name "VoIP PRI Trunk". Searching
the schema for "trunk" finds the SIP trunk entities and misses this one entirely.

**The navigation property from a gateway to its trunks is
`VoipGatewaysEndpoints`.** Plural in the middle as well as at the end. Nobody guesses this;
run `python3 tools/schema_query.py show Orion.IpSla.VoipGateways` instead.

**`OperationStatusID` is not a platform status.** It is a `System.Int16` into
`Orion.IpSla.OperationStatuses`. The platform status is the inherited `Status`, a
`System.Int32`, and only that one joins to `Orion.StatusInfo`. The same warning applies to
`OperationStateID` and to `Orion.IpSla.AlertQos.Status`, which is a `System.Char`.

**`Deleted` is a soft delete and it is on several entities.**
`Orion.IpSla.Operations`, `Orion.IpSla.CCMMonitoring`, `Orion.IpSla.OperationThresholds`,
`Orion.IpSla.OperationTypesThresholds` and `Orion.IpSla.OperationParameters` all carry it.
Omit `WHERE Deleted = FALSE` and your inventory silently includes objects that were removed.

**`Orion.IpSla.CCMPhones` has `RegionID` but no `Region` navigation.**
`Orion.IpSla.CCMGateways` has both. Do not assume symmetry between the two; check with
`python3 tools/schema_query.py show <entity>` before writing the dotted expression.

**The `Operations<TYPE>` entities are report views, not configuration.**
`Orion.IpSla.OperationsHTTP` and its eight siblings all have a `SummaryDate` column and
pre-aggregated `AVERAGEof...` columns. If you want an operation's configuration, the answer
is `Orion.IpSla.Operations` joined to `Orion.IpSla.OperationParameters`.

**`Orion.IpSla.VoipCallDetailsHist` is byte-for-byte the same 67 columns as
`Orion.IpSla.VoipCallDetails`, and has none of its seven navigation properties.** A query
written against the live table does not port to the history table by changing the entity
name, because every `cd.OriginPhone.Name` style expression stops resolving.

**Four entities called `VoipCall*MMA` share identical columns.**
`Orion.IpSla.VoipCallMosMMA`, `Orion.IpSla.VoipCallJitterMMA`,
`Orion.IpSla.VoipCallLatencyMMA` and `Orion.IpSla.VoipCallPacketLossMMA` all expose `NodeID`,
`CcmID`, `DateTimeUTC`, `MinValue`, `MaxValue` and `AvgValue`. Nothing in a result set says
which metric you read, so alias the column.

**`Orion.IpSla.CCMPhoneDetails` declares its relationship against `Orion.Ipsla.CCMPhones`,
with a lowercase `s`.** The entity in the schema is `Orion.IpSla.CCMPhones`. The relationship
target string in the extracted data does not match the entity's own casing, so a tool that
resolves relationship targets by exact string comparison will fail to follow that one edge.
Query the extension entity by `PhoneID` if you hit it.

**The registration percentage columns change type between the current and historical
entities.** `System.Int32` on `Orion.IpSla.CallManagerCurrentStats`, `System.Double` on
`Orion.IpSla.CallManagerStats`.

**The six `SipStats*` columns widened to `System.Int64` in 2026.2.** Harmless in SWQL,
breaking in a typed client. Check
[../reference/schema-changes-2026.1-to-2026.2.md](../reference/schema-changes-2026.1-to-2026.2.md)
before an upgrade.

**Time-bound everything below `System.StatisticsEntity`.** In this module that is
`Orion.IpSla.VoipCallDetails`, `Orion.IpSla.VoipCallDetailsHist`, `Orion.IpSla.OperationStats`
and the whole per-family statistics group, plus the trunk and gateway series. A call detail
table on a busy cluster is one of the largest tables in the database.

**Account limitations filter silently.** Two accounts running the same call quality report
legitimately return different rows with no indication that anything was removed, so "the
report is empty" is often a permissions answer rather than a data answer.

## What is not verified here

The `Orion.IpSla.` entities carry no property descriptions at all in the published schema, so
several things a reader will want are genuinely not established by this data. Rather than
fill those gaps with plausible narrative, here is each one with the query that settles it on
your own server.

| Claim | Status | How to check |
|---|---|---|
| MOS values are on the ITU 1 to 5 mean opinion score scale | The column type is `System.Double` and nothing in the schema states a range. The scale is the industry standard and the product documentation uses it, but this data does not establish it | `SELECT MIN(cs.MOS) AS Lowest, MAX(cs.MOS) AS Highest, AVG(cs.MOS) AS Mean FROM Orion.IpSla.OperationCurrentStats cs WHERE cs.MOS IS NOT NULL` |
| Jitter, latency and round trip time are in milliseconds | Not stated. `RoundTripTime` is `System.Int32` while `Jitter` and `Latency` are `System.Double`, which is consistent with milliseconds but does not prove it | Compare a known path against a `ping` from the source router, or read `SELECT p.Name, p.Type, p.Summary FROM Metadata.Property p WHERE p.Entity.FullName = 'Orion.IpSla.OperationCurrentStats'` |
| `PacketLoss` is a percentage rather than a packet count | Not stated. It is `System.Double` on the statistics entities and `System.Int32` on `Orion.IpSla.VoipCallDetails`, which suggests two different meanings | `SELECT MIN(cs.PacketLoss) AS Lowest, MAX(cs.PacketLoss) AS Highest FROM Orion.IpSla.OperationCurrentStats cs` and compare against `SELECT MAX(cd.OrigPacketLoss) AS Highest FROM Orion.IpSla.VoipCallDetails cd WHERE cd.DateTime >= @startUtc` |
| `SD` means source to destination and `DS` destination to source | Inferred from the naming convention and from the pairing with `OneWayDelaySD` and `OneWayDelayDS`. Not stated in the schema | Run a one-directional test and see which column moves |
| The integers in `Orion.IpSla.OperationStatuses` and `Orion.IpSla.OperationStates` | Not enumerated anywhere in the extracted data | `SELECT s.OperationStatusID, s.OperationStatus FROM Orion.IpSla.OperationStatuses s ORDER BY s.OperationStatusID` and the same for `Orion.IpSla.OperationStates` |
| `OrigCause_value` and `DestCause_value` are Q.850 cause codes | Not stated. They are `System.Int64` with no description | `SELECT TOP 50 cd.OrigCause_value, cd.DestCause_value, COUNT(cd.ID) AS Calls FROM Orion.IpSla.VoipCallDetails cd WHERE cd.DateTime >= @startUtc GROUP BY cd.OrigCause_value, cd.DestCause_value ORDER BY COUNT(cd.ID) DESC` and compare the top values against your call manager's own documentation |
| `EndPointType` on `Orion.IpSla.VoipGatewayEndpoints` distinguishes PRI from other trunk kinds | Undocumented `System.Int32` | `SELECT ep.EndPointType, COUNT(ep.VoipGatewayEndpointID) AS Trunks FROM Orion.IpSla.VoipGatewayEndpoints ep GROUP BY ep.EndPointType` |
| `CallOrigin` and `VoipGatewayChannelMediaTypeID` on `Orion.IpSla.VoipGatewayChannelStats` | Undocumented integers with no lookup entity in the module | `SELECT cs.CallOrigin, cs.VoipGatewayChannelMediaTypeID, SUM(cs.CallCount) AS Calls FROM Orion.IpSla.VoipGatewayChannelStats cs WHERE cs.RecordTime >= @startUtc GROUP BY cs.CallOrigin, cs.VoipGatewayChannelMediaTypeID` |
| `Orion.IpSla.CCMPhones.Status` uses the platform status codes | The column is `System.Int32`, which matches `Orion.StatusInfo.StatusId`, and the status reference documents a VNQM meaning for code 0. The schema does not state the mapping for this specific entity | `SELECT p.Status, st.StatusName, COUNT(p.ID) AS Phones FROM Orion.IpSla.CCMPhones p JOIN Orion.StatusInfo st ON st.StatusId = p.Status GROUP BY p.Status, st.StatusName` and see whether the names are sensible for phones |
| The retention windows behind the `Detail` / `Hourly` / `Daily` rollups | Configured per installation and not in the schema | Compare `SELECT MIN(d.RecordTime) AS Oldest FROM Orion.IpSla.OperationResultsDetail d` against the same query on the `Hourly` and `Daily` entities |
| The metric each `ThresholdTypeID` refers to | Not enumerated; the readable name is on the lookup entity | `SELECT t.ThresholdTypeID, t.ThresholdType, t.IsReverse FROM Orion.IpSla.ThresholdTypes t ORDER BY t.ThresholdTypeID` |
| VNQM publishes no verbs on any release | Verified for 2026.2 only, from `data/schema/2026.2/verbs.json` | The `Metadata.Verb` query in [Verbs](#verbs), run against your own server |

There is no VNQM page in SolarWinds' published OrionSDK documentation and no VNQM sample
script in the SDK samples directory. That absence is itself informative: the schema, the
`Metadata.*` entities and your own data are the only sources, and
[`../../scripts/swql/08-schema-introspection.swql`](../../scripts/swql/08-schema-introspection.swql)
is the tool for using them.

## Related pages

- [README.md](README.md) for the module index and how to check what is installed.
- [wpm.md](wpm.md) for Web Performance Monitor, the other module whose namespace does not
  match its product name.
- [npm.md](npm.md) for `Orion.NPM.Interfaces`, which reaches VNQM through
  `Orion.NPM.Interfaces.VoIPCallManager` and `Orion.NPM.Interfaces.VoIPInterface`.
- [nta.md](nta.md) and [qoe.md](qoe.md) for the two other ways this platform measures traffic
  quality, from flow records and from packet inspection respectively.
- [../platform/modules.md](../platform/modules.md) for the whole-schema module map.
- [../reference/netobject-types.md](../reference/netobject-types.md) for the nine VNQM
  NetObject prefixes.
- [../reference/status-codes.md](../reference/status-codes.md), including the IP SLA specific
  meaning of status 0.
- [../reference/schema-changes-2026.1-to-2026.2.md](../reference/schema-changes-2026.1-to-2026.2.md)
  for the `SipStats*` type widening and the new `Orion.IpSla.OperationStats`.
- [../swis/verb-catalog.md](../swis/verb-catalog.md) for `Orion.Nodes.Unmanage` and
  `Orion.AlertSuppression.SuppressAlerts`, the two platform verbs that apply to VNQM objects.
- [../swql/date-and-time.md](../swql/date-and-time.md) before doing arithmetic with
  `UtcOffsetMinutes`.
- [../swql/performance.md](../swql/performance.md) for choosing between the detail, hourly and
  daily rollups.
- [`../../scripts/swql/15-voip-and-web-transactions.swql`](../../scripts/swql/15-voip-and-web-transactions.swql)
  for more verified sample queries against this module.

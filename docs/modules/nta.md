# NTA: NetFlow Traffic Analyzer

Every other monitoring module tells you *how much* traffic crossed an interface. NetFlow
Traffic Analyzer tells you *what* that traffic was: which application, which pair of hosts,
which country, which DSCP marking, which autonomous system, and which QoS class the router
put it in. It does that by receiving flow records exported by the devices themselves, so
NTA does not poll for this data. The router, switch or firewall pushes it, and NTA's job is
to receive, decode, correlate and store it.

That difference in data source shapes everything about the module. Turning NTA on for a
device is not "add a poller", it is "mark this device as a flow source and configure the
device to export to us". And because a busy router can emit thousands of flow records per
second, the flow tables are, by a very wide margin, the largest tables in the database.
Almost every mistake people make with the NTA schema is a variation of forgetting that.

## Namespaces and how many entities

All 49 NTA entities live under a single prefix, `Orion.Netflow.`, spelled with a lowercase
`f`. There is no `Orion.NTA.` namespace and no `Orion.NetFlow.` namespace.

| Group | Entities | What is in it |
|---|---|---|
| Flow records | 12 | `Orion.Netflow.Flows` and the eleven views over it |
| CBQoS | 13 | Class-based QoS policies, class maps, statistics and their lookups |
| Sources | 5 | Which nodes and interfaces are enabled for flow and CBQoS collection |
| Lookups | 10 | Applications, protocols, countries, autonomous systems, types of service |
| IP address groups | 4 | Operator-defined address groupings and the segments behind them |
| Engines and diagnostics | 5 | Flow collectors, and NTA's own storage sizing tables |

Check the grouping yourself:

```bash
python3 tools/schema_query.py find Netflow --properties
python3 tools/schema_query.py show Orion.Netflow.Flows
python3 tools/schema_query.py verbs --entity Orion.Netflow.NodeSources
```

Only one NTA entity has a NetObject prefix in the
[netobject reference](../reference/netobject-types.md): `Orion.Netflow.CBQoSPolicyMetric`,
which uses `CCM` and is displayed as "NTA: CBQoS Class Map". Nothing else in the module is
addressed as a NetObject, which is consistent with the NTA verbs taking bare integer ids
rather than `netObjectId` strings.

## Flow sources: what NTA is allowed to receive

A device sends flow records to the collector whether or not NTA is expecting them, because
flow export is one-way UDP. The source entities are how NTA records which senders it should
accept and decode. Four entities describe that idea at different granularities and for the
two different collection methods, and knowing which one to use is most of the battle.

| Entity | One row per | Identifier column | Verbs | Create |
|---|---|---|---|---|
| `Orion.Netflow.Source` | Node and interface pairing, with both flow and CBQoS state on one row | `NetflowSourceID` | none | no |
| `Orion.Netflow.NodeSources` | Node | `NetflowNodeSourceID` | 4 | no |
| `Orion.Netflow.InterfaceSources` | Exporting interface | `NetflowInterfaceSourceID` | 3 | no |
| `Orion.Netflow.CBQoSSource` | Node and interface pairing, CBQoS only | `CBQoSSourceID` | none | **yes** |

The extracted schema records property names and types but **not** which properties are
formally keys, so the identifier columns above and in the lookup table further down are
named from their shape rather than from a key declaration. The only NTA key the reference
data does record is `MetricID` on `Orion.Netflow.CBQoSPolicyMetric`. If you need the formal
keys, for instance to build a `Uri` by hand, ask your own server:
`SELECT p.Entity.FullName AS EntityName, p.Name, p.Type FROM Metadata.Property p WHERE p.IsKey = TRUE AND p.Entity.FullName LIKE 'Orion.Netflow.%' ORDER BY p.Entity.FullName`.

**`Orion.Netflow.Source`** is the widest read-side view. It carries `NodeID`,
`InterfaceID`, `EngineID`, `Enabled`, `CBQoSEnabled`, `LastTimeFlow`, `LastTime`,
`CBQoSLastTime`, `LastTimeAAR`, `LastTimeWLC`, `IsWLC`, `AutoDetectedSamplingRate` and
`ManualSamplingRate`. It is the only source entity that shows flow state and CBQoS state
side by side, and it navigates to both `Node` and `Interface`. It declares `invoke` in its
operations but publishes no verbs, so treat it as read-only unless your server says
otherwise.

**`Orion.Netflow.NodeSources`** is the per-node record, with `NodeID`, `EngineID`,
`Enabled` and `LastTimeFlow`, a `Node` navigation property, and a `NodeStatistics`
navigation to the arrival-rate counters. It owns the four node-level verbs.

**`Orion.Netflow.InterfaceSources`** is the per-interface record, and it is the odd one out
because its target is *polymorphic*: rather than an `InterfaceID` column it has an
`EntityType` string and an `EntityID` integer. For an ordinary interface, `EntityType` is
`'Orion.NPM.Interfaces'` and `EntityID` is the `InterfaceID`. It has no `Node` navigation
property, so joining to node information means joining `Orion.Netflow.NodeSources` or
`Orion.Nodes` on `NodeID` by hand. Its other columns are `InterfaceIndex` (the router's own
ifIndex, which is what appears in the flow record and is not the platform's `InterfaceID`),
`IfName`, `Enabled`, `Managed`, `LastTime`, `AutoDetectedSamplingRate` and
`ExporterFlowDirectionID`.

**`Orion.Netflow.NodeProperties`** is not a source but sits with them: it records what the
exporter is capable of, as `FlowVersion`, `FlowType`, `FlowVersionFormatted`,
`IsAARCapable`, `IsAARMainDevice` and `ManualSamplingRate`. It supports create, update and
invoke under `manageNodes`, but like `Orion.Netflow.Source` it publishes no verbs.

### Enabling and disabling flow sources

Flow sources are toggled with verbs, not with CRUD. Each of the four enable and disable
verbs takes an **array** of ids and returns an array. SolarWinds' own
`NTA.EnableDisableFlowSources.ps1` sample does the node level and the interface level
together, because enabling one without the other leaves you half configured:

```powershell
$swis = Connect-Swis -Hostname orion.example.com -Credential $cred

$nodeId = Get-SwisData $swis `
    "SELECT NodeID FROM Orion.Nodes WHERE Caption = @caption" `
    @{ caption = 'core-router-01' }

$interfaceIds = Get-SwisData $swis `
    "SELECT InterfaceID FROM Orion.NPM.Interfaces WHERE NodeID = @nodeId" `
    @{ nodeId = $nodeId }
$interfaceIds = $interfaceIds | ForEach-Object { [int]$_ }

Invoke-SwisVerb $swis Orion.Netflow.NodeSources EnableFlowNodeSources `
    @(, @([int]$nodeId)) | Out-Null
Invoke-SwisVerb $swis Orion.Netflow.InterfaceSources EnableFlowInterfaceSources `
    @(, $interfaceIds) | Out-Null
```

The two PowerShell details in that snippet are the ones people lose an afternoon to.
`@(, $interfaceIds)` uses the unary comma operator to wrap the array in another array, so
the verb receives **one** argument that happens to be a list, rather than N arguments. Drop
the comma and a single-element list arrives as a scalar and a multi-element list arrives as
several positional arguments, neither of which matches the signature. And
`ForEach-Object { [int]$_ }` matters because `Get-SwisData` returns the ids in a form that
does not always serialise as `array<number>`. Both idioms come straight from the SolarWinds
sample; keep them.

Disabling is the same call with the `Disable` verbs, and it is genuinely destructive of
future data: the collector will drop records from that exporter from then on. Confirm the
set before you act, and check afterwards:

```sql
SELECT TOP 100
    src.NodeID,
    src.EntityType,
    src.EntityID,
    src.IfName,
    src.Enabled
FROM Orion.Netflow.InterfaceSources src
WHERE src.EntityType <> 'Orion.NPM.Interfaces'
ORDER BY src.NodeID
```

That last query is worth running once on any server before you write automation against
`Orion.Netflow.InterfaceSources`. If it returns rows, your installation has flow sources
whose exporter is something other than an NPM interface, and any code that assumes
`EntityID` is an `InterfaceID` will silently mis-join.

### Sampling rate

Sampled exporters send one record for every N flows, and NTA has to multiply the byte
counts back up. It will detect the rate if the exporter advertises it, and you can override
it when the exporter lies or says nothing:

| Verb | Entity | Parameters, in order | Returns |
|---|---|---|---|
| `SetManualSamplingRate` | `Orion.Netflow.NodeSources` | `nodeId`, `samplingRate` | boolean |
| `SetAutoDetectedSamplingRate` | `Orion.Netflow.NodeSources` | `nodeId` | boolean |

`SetAutoDetectedSamplingRate` takes only the node id: it clears the manual override and
returns the node to whatever NTA detects. The two rates are visible side by side on
`Orion.Netflow.Source` as `AutoDetectedSamplingRate` and `ManualSamplingRate`, which is the
fastest way to see which nodes have been overridden.

### CBQoS sources

Class-based QoS data is polled from the device rather than pushed as flow records, which is
the wording SolarWinds' own `NTA.ChangeSettings.ps1` sample uses for the global switch. It
has its own source entity and, unusually for NTA, its own lifecycle through **CRUD rather
than verbs**.
`Orion.Netflow.CBQoSSource` supports create, read, update and delete under `manageNodes`.

Creating one, adapted from `NTA.AddCBQoSSources.ps1`:

```powershell
foreach ($interfaceId in $interfaceIds) {
    New-SwisObject $swis Orion.Netflow.CBQoSSource @{
        NodeID      = $nodeId
        InterfaceID = $interfaceId
        EngineID    = $engineId
        Enabled     = $true
    } | Out-Null
}
```

Toggling one, adapted from `NTA.EnableDisableCBQoSSources.ps1`, is an update against the
row's `Uri` rather than a verb call:

```powershell
$uris = Get-SwisData $swis `
    "SELECT Uri FROM Orion.Netflow.CBQoSSource WHERE NodeID = @nodeId" `
    @{ nodeId = $nodeId }

foreach ($uri in $uris) {
    Set-SwisObject $swis -Uri $uri -Properties @{ Enabled = $false }
}
```

See [../swis/crud.md](../swis/crud.md) for the create and update calls and
[../swis/uris.md](../swis/uris.md) for what a `Uri` is and why you select it in the same
pass as the rows you intend to change.

Per-source enabling is not the only switch. CBQoS polling has a global setting that
overrides all of it, and `NTA.ChangeSettings.ps1` shows the pattern for reaching it. NTA
settings are stored in the platform-wide `Orion.Settings` entity, keyed by a string
`SettingID`, and changed by updating `CurrentValue`:

```sql
SELECT SettingID, Name, Description, CurrentValue, DefaultValue, Minimum, Maximum, Units
FROM Orion.Settings
WHERE SettingID LIKE '%CBQoS%'
```

```powershell
$uri = Get-SwisData $swis `
    "SELECT Uri FROM Orion.Settings WHERE SettingID = @settingId" `
    @{ settingId = 'CBQoS_Enabled' }

Set-SwisObject $swis -Uri $uri -Properties @{ CurrentValue = 1 }
```

`CBQoS_Enabled` is the `SettingID` SolarWinds' own sample uses, and `CurrentValue` is a
`System.Single`, so `0` and `1` are the values for a boolean-shaped setting. The full list
of NTA-related setting ids is not carried in the extracted schema; drop the `WHERE` clause
from the query above to enumerate every setting your server has, and read `Description` and
`Hint` before changing anything.

## Flow records: one table and eleven views over it

`Orion.Netflow.Flows` exposes flows as NTA received them, at the finest granularity
available, which is how SolarWinds' own
[NTA 4.0 Entity Model](https://solarwinds.github.io/OrionSDK/docs/netflow-traffic-analyzer/nta-4-0-entity-model/)
describes it. Its columns divide into four groups.

**Identity and volume.** `TimeStamp`, `ObservationTimestamp`, `NodeID`, `Bytes`, `Packets`,
`TotalBytes`, `TotalPackets`, `IngressBytes`, `EgressBytes`, `IngressPackets`,
`EgressPackets`.

**The two endpoints.** Everything about a flow that has a direction appears twice, once for
each end: `SourceIP` / `DestinationIP`, `SourceHostname` / `DestinationHostname`,
`SourceHostnameID` / `DestinationHostnameID`, `SourceDomain` / `DestinationDomain`,
`SourceDomainID` / `DestinationDomainID`, `SourceASID` / `DestinationASID`,
`SourceCountryCode` / `DestinationCountryCode`, `SourceIPGroupSegmentID` /
`DestinationIPGroupSegmentID`.

**Classification.** `ApplicationID`, `AdvancedApplicationID`, `EnabledApplicationID`,
`ApplicationEnabled`, `ProtocolID`, `Port`, `PortDirection`, `ToSID`, `TrafficClassID`,
`PaloAltoAppID`, `IsIPv6`.

**The exporter's own view.** `InterfaceIDRx` and `InterfaceIDTx` are the platform's
interface ids; `InputInterfaceIndex` and `OutputInterfaceIndex` are the ifIndex values the
router put in the record. They are not the same numbers and confusing them produces joins
that return nothing.

Fourteen navigation properties save you the lookup joins: `Node`, `IngressInterface`,
`EgressInterface`, `Protocol`, `ToS`, `SourceAutonomousSystem`,
`DestinationAutonomousSystem`, `SourceCountry`, `DestinationCountry`, `Application`,
`AdvancedApplication`, `SourceIPGroup`, `DestinationIPGroup` and `TrafficClass`.

### The non-directional views, and why they duplicate rows

The problem the views solve is stated well in SolarWinds' own
[NTA 4.0 Entity Model](https://solarwinds.github.io/OrionSDK/docs/netflow-traffic-analyzer/nta-4-0-entity-model/):
because every flow has a source and a destination, "how much traffic did 10.1.2.3 move" is
awkward against `Orion.Netflow.Flows`, since you would have to sum it as a source and again
as a destination and add the two.

So NTA publishes views that add a single non-directional column and **duplicate the flow**
to fill it. If a flow's source and destination values differ, the view emits two rows, one
carrying the source value and one carrying the destination value. If they are the same, it
emits one. That is what makes `GROUP BY IP` correct, and it is also why totals from a view
are not comparable with totals from `Orion.Netflow.Flows`.

| Entity | Extra column | Extra navigation |
|---|---|---|
| `Orion.Netflow.FlowsByIP` | `IP`, plus `PartnerIP`, `Hostname`, `HostnameID`, `Domain`, `DomainID`, `CountryCode`, `ASID`, `IPGroupSegmentID` | `IPGroup` |
| `Orion.Netflow.FlowsByHostname` | the same nine columns | `IPGroup` |
| `Orion.Netflow.FlowsByDomain` | `Domain`, `DomainID` | none |
| `Orion.Netflow.FlowsByAS` | `ASID` | none |
| `Orion.Netflow.FlowsByCountryCode` | `CountryCode` | `Country` |
| `Orion.Netflow.FlowsByInterface` | `InterfaceID`, `InterfaceIndex` | `Interface` |

`Orion.Netflow.FlowsByConversation` is the exception. It adds no column and duplicates
nothing. Instead it normalises direction, so that the pairs (A, B) and (B, A) both come back
as (A, B). That is what makes a conversation report add up: group by `SourceIP` and
`DestinationIP` on this entity and each conversation appears once, with both directions
summed. `Orion.Netflow.FlowsByInterfaceByConversation` does the same thing scoped to an
interface, and is the one flow entity that declares no navigation properties at all.

Three more entities complete the set:

- `Orion.Netflow.FlowsByApplication` is a narrower projection, 21 columns, with none of the
  endpoint or protocol classification and only `Node`, `IngressInterface` and
  `EgressInterface` to navigate. It has **no `Application` navigation property**, so join
  `Orion.Netflow.Applications` on `ApplicationID` explicitly.
- `Orion.Netflow.FlowsByAdvancedApplication` is the equivalent for the NBAR-style
  application catalogue, and likewise has no `AdvancedApplication` navigation.
- `Orion.Netflow.FlowsWLC` is the wireless controller variant, adding `SSID`, `ClientIP`,
  `ClientMAC`, `WtpMAC` and `PostDSCPID`, and dropping most of the IP-level columns. It
  navigates to `Node`, `AdvancedApplication` and `ToS` only.

All twelve inherit from `System.StatisticsEntity`.

### Lookup entities

| Entity | Identifier column | Useful columns |
|---|---|---|
| `Orion.Netflow.Applications` | `ApplicationID` | `Name`, `PortName`, `TCP`, `UDP`, `Multiport`, `MapTo`, `Enabled`, `Description` |
| `Orion.Netflow.AdvancedApplications` | `ID` | `Name`, `Vendor`, `Category`, `SubCategory`, `ApplicationGroup`, `Icon` |
| `Orion.Netflow.Protocols` | `ProtocolID` | `Name`, `Description`, `Enabled` |
| `Orion.Netflow.TypesOfService` | `ToSID` | `Name`, `DSCP`, `DSCPinByte` |
| `Orion.Netflow.AutonomousSystems` | `AutonomousSystemID` | `Name`, `Organization`, `RegistrationDate`, `LastUpdated` |
| `Orion.Netflow.Countries` | `CountryCode` | `Name` |
| `Orion.Netflow.TrafficClass` | `TrafficClassID` | `Name` |
| `Orion.Netflow.Hostnames` | `ID` | `Hostname` |
| `Orion.Netflow.IP2Country` | a `Low` to `High` range | `Low`, `High`, `CountryCode`, the geolocation range table |
| `Orion.Netflow.CorrelationPostDNS` | `IPAddress` | `IPAddress`, `Hostname`, `Domain`, plus sortable integer forms |

`Multiport` and `MapTo` on `Orion.Netflow.Applications` carry no description in the
published schema, so their semantics are **unverified** here. Read the values your server
holds before depending on them:
`SELECT TOP 50 ApplicationID, Name, PortName, Multiport, MapTo FROM Orion.Netflow.Applications WHERE MapTo <> 0`.

### IP address groups

IP address groups are the operator's own naming of address space: "Datacenter A", "Guest
WiFi", "Partner VPN". Four entities model them.

`Orion.Netflow.IPAddressGroups` is the group itself, with `IPAddressGroupID`, `Name` and
`Enabled`, and it has twenty navigation properties: eighteen into the flow views, because
every flow entity can point at it from both ends, plus `SegmentsCS` and `SegmentsPivot`
into the two segment entities below. `Orion.Netflow.IPAddressGroupRanges` holds the
address ranges: `IPRangeStart`, `IPRangeEnd`, `CIDRPrefix`, `IsIPv6`, `System`,
`LowerBoundNormalized`, `UpperBoundNormalized`, plus a denormalised `IPAddressGroupName`.

None of the four declares create, update or delete, so a group's ranges are not written
with CRUD. The write path is the `SetIPRanges`, `DeleteIpGroups` and `CreateFromIPAMGroup`
verbs described in [IP address group management](#ip-address-group-management).

`Orion.Netflow.IPGroupSegments` and `Orion.Netflow.IPGroupsBySegments` are the internal
mapping NTA uses to attach a group to a flow efficiently: a flow row stores
`SourceIPGroupSegmentID` and `DestinationIPGroupSegmentID`, not a group id. You rarely
query these directly because the `SourceIPGroup`, `DestinationIPGroup` and `IPGroup`
navigation properties resolve the indirection for you.

### Flow engines and storage diagnostics

`Orion.Netflow.FlowEngines` is one row per collector: `EngineID`, `NetFlowPort` (a string,
not an integer), `FlowCollectorStartTime`, `FlowCollectorKeepAlive`, and an `Engine`
navigation to `Orion.Engines`. A `FlowCollectorKeepAlive` that has stopped advancing is the
first thing to look at when flows stop arriving from everything at once.
`Orion.Netflow.NetFlowEnginesStatistics` is a name/value bag per engine, as `EngineID`,
`StatisticsName` and `StatisticsValue`.

The three `Orion.Netflow.Diagnostics.*` entities are how NTA reports its own storage
footprint, and they are the only NTA entities whose access control requires the `system`
right rather than `manageNodes` or `everyone`:

| Entity | Columns |
|---|---|
| `Orion.Netflow.Diagnostics.Database` | `Name`, `TotalSpaceMB`, `UsedSpaceMB`, `UnusedSpaceMB` |
| `Orion.Netflow.Diagnostics.Tables` | `Name`, `RowCount`, `TotalSpaceMB`, `UsedSpaceMB`, `UnusedSpaceMB` |
| `Orion.Netflow.Diagnostics.Partitions` | `PartitionNumber`, `PartitionBoundary`, `RowCount` |

All three declare create, update and delete operations. Nothing in the schema explains what
creating a diagnostics row would mean, and the `system` right is not something a normal
account holds, so treat them as read-only.

## CBQoS

Class-based QoS answers a different question from flow: not "what is on the wire" but "what
did the router's own queueing do with it". Thirteen entities model it, and they form a
chain from the interface down to a single measured value.

`Orion.Netflow.CBQoSPolicy` is the centre. One row is one class in one policy applied to one
interface in one direction. It carries `PolicyID`, `NodeID`, `InterfaceID`, `PolicyMapID`,
`ClassMapID`, `PolicyActionID`, `PolicyIndex`, `RateBps`, `DirectionID`, `IsActive`,
`HasChildren`, `PolicyFullPathName`, `ParentPolicyID`, `RootPolicyID`, `StartDate` and
`EndDate`. Policies nest, which is what `ParentPolicyID`, `RootPolicyID`, `HasChildren` and
the pre-computed `PolicyFullPathName` are for: a hierarchical policy map has a parent class
that shapes and child classes that prioritise inside it, and summing across levels
double-counts. `StartDate` and `EndDate` exist because a policy can be reconfigured on the
device, and NTA keeps the superseded row so old statistics still resolve.

Around it:

- `Orion.Netflow.CBQoSPolicyMap` (`PolicyMapID`, `Name`, `Description`) and
  `Orion.Netflow.CBQoSClassMap` (`ClassMapID`, `Name`, `Description`) are the device's own
  names, reached through the `PolicyMap` and `ClassMap` navigation properties.
- `Orion.Netflow.CBQoSDirectionDescription` turns `DirectionID` into `DirectionName`, and
  is reached as `DirectionDescription`. Use it rather than hard-coding the integer.
- `Orion.Netflow.CBQoSPolicyAction` (`PolicyActionID`, `NodeID`, `RateType`, `Rate`) is what
  the class is configured to do. `RateType` is a `System.Int16` whose values are not
  described in the schema.
- `Orion.Netflow.CBQoSPolicyMetric` is one measurable series: `MetricID`, `PolicyID`,
  `StatisticsID`, `PolicyFullPathName`, `StatisticsName`, `DisplayName`. This is the entity
  with the `CCM` NetObject prefix.
- `Orion.Netflow.CBQoSStatistics` is the history, inheriting from `System.StatisticsEntity`.
  Its columns are `PolicyID`, `StatisticsID`, `Timestamp`, `Bytes`, `Bitrate` and
  `ClassUtilization`. Note the spelling: `Timestamp`, not the `TimeStamp` used on every flow
  entity.
- `Orion.Netflow.CBQoSStatisticsDescription` names the `StatisticsID`, which is how you tell
  a pre-policy byte count from a drop count without memorising integers.
- `Orion.Netflow.CBQoSConfigurationDetails` is a flattened, pre-joined reporting view over
  all of the above, with `PolicyName`, `ClassMapName`, `Condition`, `Direction` as a string,
  `Rate`, `EffectiveRate`, `LastHourRate`, `LastDayRate`, `LastHourRatePerc` and
  `LastDayRatePerc`. When you want a readable answer rather than a schema tour, start here.
- `Orion.Netflow.CBQoSTop`, `Orion.Netflow.CBQoSDetail` and
  `Orion.Netflow.CBQoSPolicyClassPaths` are further pre-aggregated views used by the product's
  own resources.

From a node, the navigation properties are `CBQoSPolicies`, `CBQoSPolicyActions` and
`CBQoSSource`; from an interface, `CBQoSPolicies` and `CBQoSSource`.

## Verbs

NTA publishes 12 verbs across four entities. Seven sit on the two source entities below,
whose schema pages declare them. The other five sit on two management facades —
`Orion.Netflow.IPAddressGroupsManagement` and `Orion.Netflow.IPGroupExternalRelation` —
that exist only in the Swagger contract: they have no schema page and no properties, so
`schema_query.py show` fails on them with an unknown-entity error, but
`verbs --entity Orion.Netflow.IPAddressGroupsManagement` lists them and every one has an
`/Invoke/` path. Everything else in the module is read-only or, as with
`Orion.Netflow.CBQoSSource`, managed with CRUD.

### `Orion.Netflow.NodeSources`

Invoke requires the `manageNodes` right, which the entity declares for `read,invoke`.

| Verb | Parameters, in order | Returns |
|---|---|---|
| `EnableFlowNodeSources` | `nodeIds` (`array<number>`) | array |
| `DisableFlowNodeSources` | `nodeIds` (`array<number>`) | array |
| `SetManualSamplingRate` | `nodeId` (`number`), `samplingRate` (`number`) | boolean |
| `SetAutoDetectedSamplingRate` | `nodeId` (`number`) | boolean |

### `Orion.Netflow.InterfaceSources`

Also `manageNodes` for `read,invoke`.

| Verb | Parameters, in order | Returns |
|---|---|---|
| `EnableFlowInterfaceSources` | `interfaceIds` (`array<number>`) | array |
| `DisableFlowInterfaceSources` | `interfaceIds` (`array<number>`) | array |
| `SetExporterFlowDirection` | `configurations` (`array<SolarWinds.Netflow.Contracts.InterfaceSources.FlowExporterConfiguration>`) | boolean |

Arguments are positional. The parameter names above appear in the Swagger contract and in
documentation, but never on the wire, so the order is the whole contract. See
[../swis/invoke-verbs.md](../swis/invoke-verbs.md).

`SetExporterFlowDirection` is the one verb here you cannot call from this page alone. Its
`FlowExporterConfiguration` type is declared in SolarWinds' Swagger contract as a bare
object with **no properties**, so the field names it expects are **unverified**. The
related column is `Orion.Netflow.InterfaceSources.ExporterFlowDirectionID`, and the meaning
of its integer values is also undocumented in the schema. Read what your server already
holds before constructing a payload:

```sql
SELECT TOP 10
    src.ExporterFlowDirectionID,
    COUNT(src.NetflowInterfaceSourceID) AS SourceCount
FROM Orion.Netflow.InterfaceSources src
GROUP BY src.ExporterFlowDirectionID
ORDER BY COUNT(src.NetflowInterfaceSourceID) DESC
```

Confirm the parameter list on your own server, which is authoritative for your version:

```sql
SELECT Position, Name, Type, IsOptional
FROM Metadata.VerbArgument
WHERE EntityName = 'Orion.Netflow.InterfaceSources'
  AND VerbName = 'SetExporterFlowDirection'
ORDER BY Position
```

### IP address group management

The write path for [IP address groups](#ip-address-groups) is verbs, not CRUD.
`Orion.Netflow.IPAddressGroups` and `Orion.Netflow.IPAddressGroupRanges` declare no
operations at all in the extracted schema, so an insert against either fails; the ranges
are written through `Orion.Netflow.IPAddressGroupsManagement`, a contract-only verb anchor:

| Verb | Parameters, in order | Returns |
|---|---|---|
| `SetIPRanges` | `ipGroupId` (`number`), `ipRanges` (`array<IPRange>`), `autoResolveApplicationConflicts` (`boolean`) | `ManageIpGroupsResult` |
| `DeleteIpGroups` | `ipGroupIds` (`array<number>`), `autoResolveApplicationConflicts` (`boolean`) | `ManageIpGroupsResult` |
| `DeleteAllIpGroups` | `autoResolveApplicationConflicts` (`boolean`) | `ManageIpGroupsResult` |
| `SetIpGroupsAsModified` | none | void |

Unlike `SetExporterFlowDirection` above, the argument types here are fully declared in
`data/schema/2026.2/types.json`. Each `IPRange` element is an object of four members:
`StartIP`, `EndIP` and `CIDR` as strings, and `CIDRBased` as a boolean. The
`ManageIpGroupsResult` that comes back carries `Result` — a string enum, one of `Succeed`,
`ApplicationCollision`, `InvalidIpGroupId`, `GenericError` — plus an
`ApplicationCollisions` array naming each colliding application definition
(`ApplicationId`, `ApplicationName`, `ApplicationPort`, `IpGroupId`, `IpGroupName`,
`IsAutoResolveVictim` among its members) and a `Message` string. That is what
`autoResolveApplicationConflicts` governs: whether a collision between the new ranges and
an application definition is resolved for you or reported back. Pass `false` on a first
call and read `ApplicationCollisions` before letting the server resolve anything.

Two of the four deserve extra care. `DeleteAllIpGroups` takes a single boolean and removes
every IP address group on the server — there is no id list to narrow it. And
`SetIpGroupsAsModified` takes nothing and returns nothing; the contract records no summary
for it, so what it actually marks as modified is **unverified** here.

The second facade, `Orion.Netflow.IPGroupExternalRelation`, holds the bridge from IPAM:

| Verb | Parameters, in order | Returns |
|---|---|---|
| `CreateFromIPAMGroup` | `externalIpGroupId` (`number`) | void |

It materialises an NTA IP address group from a group that already exists in IPAM's tree
(see [ipam.md](ipam.md)), so address space curated once in IPAM can be reused for flow
reporting. The contract states nothing beyond the parameter name about which id it expects;
IPAM's tree rows key on `IPAM.GroupNode.GroupId`, and confirming that is the id it wants is
a one-call test on your own server.

There is no verb that creates a native NTA IP address group from a name — in the 2026.2
contract, `SetIPRanges` addresses an existing `ipGroupId`, and only `CreateFromIPAMGroup`
creates one. Creating a group from scratch remains a console operation.

### NTA alerts are ordinary alerts

There is no NTA-specific alert entity or verb. `NTA.EnableDisableAlert.ps1` toggles an NTA
alert exactly the way any other alert is toggled, by updating `Enabled` on
`Orion.AlertConfigurations`:

```powershell
$uri = Get-SwisData $swis `
    "SELECT Uri FROM Orion.AlertConfigurations WHERE Name = @name" `
    @{ name = 'Flow sources not reporting' }

Set-SwisObject $swis -Uri $uri -Properties @{ Enabled = $false }
```

That requires the alert management right rather than `manageNodes`.

## Flow tables are enormous, and TOP does not save you

This is the section to read before writing any query on this page.

Flow volume is a rate, not a count. `Orion.Netflow.NodeStatistics` records the arrival rate
per exporter, so you can measure it rather than guess:

```sql
SELECT TOP 25
    ns.NodeSource.Node.Caption AS NodeName,
    ns.NodeID,
    ns.FlowsPerSecondForLast5Minutes,
    ns.FlowsPerSecondForLast24Hours,
    ns.FlowsPerSecondForLast3Days,
    ns.ObservationTimestamp
FROM Orion.Netflow.NodeStatistics ns
WHERE ns.ObservationTimestamp >= @sinceUtc
ORDER BY ns.FlowsPerSecondForLast24Hours DESC
```

Multiply out whatever that returns. A single exporter sustaining 2,000 flows per second
produces about 172 million rows a day and roughly 5.2 billion over a thirty-day retention
window. A modest estate of ten such exporters is an order of magnitude more. Now recall that
`Orion.Netflow.FlowsByIP` duplicates most rows, and the working set for a naive query on it
is roughly twice that again.

Then measure what is actually on disk:

```sql
SELECT TOP 25
    t.Name AS TableName,
    t.RowCount,
    t.TotalSpaceMB,
    t.UsedSpaceMB,
    t.UnusedSpaceMB
FROM Orion.Netflow.Diagnostics.Tables t
ORDER BY t.UsedSpaceMB DESC
```

```sql
SELECT TOP 50
    p.PartitionNumber,
    p.PartitionBoundary,
    p.RowCount
FROM Orion.Netflow.Diagnostics.Partitions p
ORDER BY p.PartitionBoundary DESC
```

`Orion.Netflow.Diagnostics.Partitions` is the important one, because it tells you the flow
data is partitioned by time. That is exactly why a `TimeStamp` predicate is the difference
between a fast query and an outage: with one, the engine reads the partitions that overlap
your window; without one, it reads all of them.

Here is the mistake, in full:

```sql
-- DO NOT RUN THIS. It has TOP 20 and it is still unbounded.
SELECT TOP 20
    f.Application.Name AS ApplicationName,
    SUM(f.Bytes) AS TotalBytes
FROM Orion.Netflow.Flows f
GROUP BY f.Application.Name
ORDER BY SUM(f.Bytes) DESC
```

That query validates cleanly and is completely correct SWQL. It is also an aggregation over
every flow record ever retained. `TOP 20` bounds the number of rows *returned*, not the
number of rows *read*: the engine cannot know which twenty applications are the largest
until it has summed all of them, so it scans every partition first and truncates last. The
result is a long-running query holding locks and pushing everything else out of the buffer
pool on the database instance that the entire monitoring platform depends on. Adding one
`WHERE` clause on `TimeStamp` turns the same query into a partition-local scan.

The rules that follow from this:

1. **Every query against a flow entity gets a `TimeStamp` predicate.** Not "usually". Every
   one. The same applies to `Timestamp` on `Orion.Netflow.CBQoSStatistics` and
   `ObservationTimestamp` on `Orion.Netflow.NodeStatistics`.
2. **Use a half-open range**, `>= @startUtc AND < @endUtc`, so consecutive windows neither
   overlap nor leave a gap.
3. **Narrow before you aggregate.** A `NodeID` or `ApplicationID` filter in the same
   `WHERE` clause costs nothing and cuts the scan further. To narrow by interface, mind
   which column exists: `Orion.Netflow.Flows` has `InterfaceIDRx` and `InterfaceIDTx`, not
   `InterfaceID`, which only the two `FlowsByInterface*` entities carry.
4. **Do not use `AddDay`, `AddHour` or the other date-math functions in a flow query.**
   SolarWinds states plainly in the
   [NTA 4.0 Entity Model](https://solarwinds.github.io/OrionSDK/docs/netflow-traffic-analyzer/nta-4-0-entity-model/)
   that those functions work against flow data but are not optimised, and that the
   difference is "several orders of magnitude". They compile to T-SQL `DATEADD`, which the
   engine cannot use to eliminate partitions.
5. **Prefer bound parameters computed in the client.** The queries below take `@startUtc`
   and `@endUtc`. If you must express the window inside the query, SolarWinds' own guidance
   is plain arithmetic on `GetUtcDate()`, where the unit is days: `GetUtcDate() - 1` is
   twenty-four hours ago and `GetUtcDate() - 1/24` is one hour ago.

```sql
SELECT TOP 20
    f.Protocol.Name AS ProtocolName,
    SUM(f.Bytes) AS TotalBytes
FROM Orion.Netflow.Flows f
WHERE f.TimeStamp > GetUtcDate() - 1
GROUP BY f.Protocol.Name
ORDER BY SUM(f.Bytes) DESC
```

Note that this is the one place the repository's general advice about `GetUtcDate()` is
narrowed rather than repeated. The warning elsewhere is about combining `GetUtcDate()` with
the `AddX` functions, which produces a timezone-blind offset. Plain subtraction has no such
problem and is what the NTA documentation recommends.

## Worked queries

Every query below has been validated against the 2026.2 schema. Supply `@startUtc` and
`@endUtc` from the client in UTC.

### 1. Top applications over a window

The obvious question, and the one that shows why the `Application` navigation property is
worth using: `Orion.Netflow.Flows` stores only `ApplicationID`, and the join to the name is
written for you.

```sql
SELECT TOP 20
    f.Application.Name AS ApplicationName,
    f.Application.PortName,
    SUM(f.Bytes) AS TotalBytes,
    SUM(f.Packets) AS TotalPackets
FROM Orion.Netflow.Flows f
WHERE f.TimeStamp >= @startUtc
  AND f.TimeStamp < @endUtc
GROUP BY f.Application.Name, f.Application.PortName
ORDER BY SUM(f.Bytes) DESC
```

If you reach for `Orion.Netflow.FlowsByApplication` instead, remember it does **not** have
an `Application` navigation property and you must join `Orion.Netflow.Applications` on
`ApplicationID` yourself.

### 2. Top talkers, counting both directions

This is the query the duplicating views exist for. Grouping by `f.IP` counts an address's
traffic whether it was the source or the destination, in one pass.

```sql
SELECT TOP 25
    f.IP,
    f.Hostname,
    f.CountryCode,
    SUM(f.Bytes) AS TotalBytes
FROM Orion.Netflow.FlowsByIP f
WHERE f.TimeStamp >= @startUtc
  AND f.TimeStamp < @endUtc
GROUP BY f.IP, f.Hostname, f.CountryCode
ORDER BY SUM(f.Bytes) DESC
```

Do not compare `SUM(f.Bytes)` here against a sum taken from `Orion.Netflow.Flows`. The rows
are duplicated on purpose and the grand total will be close to double.

### 3. Top conversations on one exporter

`Orion.Netflow.FlowsByConversation` normalises direction, so each pair appears once with
both directions already summed. Adding `NodeID` to the `WHERE` clause narrows the scan to a
single exporter before any aggregation happens.

```sql
SELECT TOP 25
    c.SourceIP,
    c.DestinationIP,
    c.Protocol.Name AS ProtocolName,
    c.Application.Name AS ApplicationName,
    SUM(c.Bytes) AS TotalBytes
FROM Orion.Netflow.FlowsByConversation c
WHERE c.TimeStamp >= @startUtc
  AND c.TimeStamp < @endUtc
  AND c.NodeID = @nodeId
GROUP BY c.SourceIP, c.DestinationIP, c.Protocol.Name, c.Application.Name
ORDER BY SUM(c.Bytes) DESC
```

### 4. Traffic per monitored interface

`Orion.Netflow.FlowsByInterface` is the only flow entity with a plain `Interface`
navigation property, which makes `fi.Interface.Node.Caption` a two-hop walk with no join
written. `IngressBytes` and `EgressBytes` separate the directions without a second query.

```sql
SELECT TOP 25
    fi.Interface.Node.Caption AS NodeName,
    fi.Interface.Name AS InterfaceName,
    SUM(fi.IngressBytes) AS IngressBytes,
    SUM(fi.EgressBytes) AS EgressBytes
FROM Orion.Netflow.FlowsByInterface fi
WHERE fi.TimeStamp >= @startUtc
  AND fi.TimeStamp < @endUtc
GROUP BY fi.Interface.Node.Caption, fi.Interface.Name
ORDER BY SUM(fi.IngressBytes) + SUM(fi.EgressBytes) DESC
```

### 5. Traffic by destination country

`Orion.Netflow.FlowsByCountryCode` has a `Country` navigation property for the
non-directional `CountryCode`, unlike `Orion.Netflow.FlowsByAS`, which does not.

```sql
SELECT TOP 20
    cc.Country.Name AS CountryName,
    cc.CountryCode,
    SUM(cc.Bytes) AS TotalBytes
FROM Orion.Netflow.FlowsByCountryCode cc
WHERE cc.TimeStamp >= @startUtc
  AND cc.TimeStamp < @endUtc
GROUP BY cc.Country.Name, cc.CountryCode
ORDER BY SUM(cc.Bytes) DESC
```

### 6. Top autonomous systems, with the join written by hand

`Orion.Netflow.FlowsByAS` adds the non-directional `ASID` column, but the only autonomous
system navigation properties it publishes are `SourceAutonomousSystem` and
`DestinationAutonomousSystem`, neither of which follows `ASID`. This is the case where you
write the join yourself.

```sql
SELECT TOP 20
    a.ASID,
    asys.Name AS ASName,
    asys.Organization,
    SUM(a.Bytes) AS TotalBytes
FROM Orion.Netflow.FlowsByAS a
JOIN Orion.Netflow.AutonomousSystems asys ON asys.AutonomousSystemID = a.ASID
WHERE a.TimeStamp >= @startUtc
  AND a.TimeStamp < @endUtc
GROUP BY a.ASID, asys.Name, asys.Organization
ORDER BY SUM(a.Bytes) DESC
```

### 7. Is QoS marking actually being applied?

A common finding is that traffic which is supposed to be marked EF is arriving as best
effort. `Orion.Netflow.TypesOfService` gives you both the friendly name and the DSCP.

```sql
SELECT TOP 20
    f.ToS.Name AS ToSName,
    f.ToS.DSCP,
    SUM(f.Bytes) AS TotalBytes
FROM Orion.Netflow.Flows f
WHERE f.TimeStamp >= @startUtc
  AND f.TimeStamp < @endUtc
GROUP BY f.ToS.Name, f.ToS.DSCP
ORDER BY SUM(f.Bytes) DESC
```

### 8. Traffic between named parts of your own network

Grouping by both IP group navigation properties turns a flat conversation list into a
matrix of "which zone talks to which zone", which is the form a segmentation or firewall
review actually wants.

```sql
SELECT TOP 20
    f.SourceIPGroup.Name AS SourceGroup,
    f.DestinationIPGroup.Name AS DestinationGroup,
    SUM(f.Bytes) AS TotalBytes
FROM Orion.Netflow.FlowsByConversation f
WHERE f.TimeStamp >= @startUtc
  AND f.TimeStamp < @endUtc
GROUP BY f.SourceIPGroup.Name, f.DestinationIPGroup.Name
ORDER BY SUM(f.Bytes) DESC
```

The group definitions behind those names:

```sql
SELECT TOP 100
    g.IPAddressGroupID,
    g.Name AS IPGroupName,
    g.Enabled,
    r.IPRangeStart,
    r.IPRangeEnd,
    r.CIDRPrefix,
    r.IsIPv6
FROM Orion.Netflow.IPAddressGroups g
JOIN Orion.Netflow.IPAddressGroupRanges r ON r.IPAddressGroupID = g.IPAddressGroupID
WHERE g.Enabled = TRUE
ORDER BY g.Name, r.IPRangeStart
```

### 9. Flow sources that have gone quiet

An exporter that stops sending produces no error anywhere: the graphs simply flatten. This
is the query to alert on. `LastTimeFlow` is when NTA last accepted a record from that node,
so comparing it to a threshold catches a device whose configuration was wiped by a reload.

```sql
SELECT TOP 50
    ns.Node.Caption AS NodeName,
    ns.NodeID,
    ns.EngineID,
    ns.Enabled,
    ns.LastTimeFlow,
    ns.NodeStatistics.FlowsPerSecondForLast5Minutes AS FlowsPerSec5Min,
    ns.NodeStatistics.FlowsPerSecondForLast24Hours AS FlowsPerSec24Hr
FROM Orion.Netflow.NodeSources ns
WHERE ns.Enabled = TRUE
  AND ns.LastTimeFlow < @staleBeforeUtc
ORDER BY ns.LastTimeFlow
```

`Enabled = TRUE` is what makes this useful rather than noisy: a disabled source is supposed
to be silent.

### 10. What is enabled on one router, interface by interface

`Orion.Netflow.InterfaceSources` has no `Node` navigation property, and its `EntityID` is
the interface id only when `EntityType` says so. Both facts are in this one query.

```sql
SELECT TOP 100
    i.Node.Caption AS NodeName,
    src.IfName,
    src.InterfaceIndex,
    src.Enabled,
    src.Managed,
    src.LastTime,
    src.AutoDetectedSamplingRate,
    src.ExporterFlowDirectionID
FROM Orion.Netflow.InterfaceSources src
JOIN Orion.NPM.Interfaces i ON i.InterfaceID = src.EntityID
WHERE src.EntityType = 'Orion.NPM.Interfaces'
  AND src.NodeID = @nodeId
ORDER BY src.InterfaceIndex
```

For the combined flow and CBQoS picture on the same device, `Orion.Netflow.Source` gives it
in one row per interface:

```sql
SELECT TOP 25
    src.Node.Caption AS NodeName,
    src.Interface.Name AS InterfaceName,
    src.NetflowSourceID,
    src.Enabled,
    src.CBQoSEnabled,
    src.LastTimeFlow,
    src.CBQoSLastTime,
    src.AutoDetectedSamplingRate,
    src.ManualSamplingRate,
    src.IsWLC
FROM Orion.Netflow.Source src
WHERE src.NodeID = @nodeId
ORDER BY src.Interface.Name
```

### 11. QoS classes under pressure

`ClassUtilization` against the class's configured rate is the number that tells you a
policy is doing something, and `StatisticsDescription.StatisticsName` tells you which
series each row is, so a drop counter is not mistaken for a byte counter.

```sql
SELECT TOP 25
    s.Policy.Node.Caption AS NodeName,
    s.Policy.Interface.Name AS InterfaceName,
    s.Policy.PolicyFullPathName,
    s.StatisticsDescription.StatisticsName,
    AVG(s.Bitrate) AS AvgBitrate,
    MAX(s.ClassUtilization) AS PeakClassUtilization
FROM Orion.Netflow.CBQoSStatistics s
WHERE s.Timestamp >= @startUtc
  AND s.Timestamp < @endUtc
GROUP BY s.Policy.Node.Caption, s.Policy.Interface.Name, s.Policy.PolicyFullPathName, s.StatisticsDescription.StatisticsName
ORDER BY MAX(s.ClassUtilization) DESC
```

Because policies nest, `PolicyFullPathName` is the safe thing to group on. Grouping on
`ClassMap.Name` alone merges a child class with an identically named class under a different
parent.

### 12. The QoS configuration on one interface, in readable form

`Orion.Netflow.CBQoSConfigurationDetails` is the pre-joined view, so the whole policy shows
up without walking five entities.

```sql
SELECT TOP 50
    cd.PolicyName,
    cd.ClassMapName,
    cd.Direction,
    cd.Condition,
    cd.Rate,
    cd.EffectiveRate,
    cd.LastHourRatePerc,
    cd.LastDayRatePerc
FROM Orion.Netflow.CBQoSConfigurationDetails cd
WHERE cd.InterfaceID = @interfaceId
ORDER BY cd.LastHourRatePerc DESC
```

### 13. Collector health

If flows stopped arriving from every device at once, the problem is the collector, not the
routers.

```sql
SELECT
    fe.EngineID,
    fe.Engine.ServerName,
    fe.NetFlowPort,
    fe.FlowCollectorStartTime,
    fe.FlowCollectorKeepAlive
FROM Orion.Netflow.FlowEngines fe
ORDER BY fe.EngineID
```

## Gotchas

**`TOP` does not bound the work an aggregate does.** Covered above, and it is the single
most expensive misunderstanding in this module.

**Timestamp column names are not consistent.** Flow entities use `TimeStamp` with a capital
S and also carry `ObservationTimestamp`. `Orion.Netflow.CBQoSStatistics` uses `Timestamp`
with a lowercase s and has no `TimeStamp` at all. `Orion.Netflow.NodeStatistics` has only
`ObservationTimestamp`. Look the column up rather than assuming.

**The `FlowsBy*` views duplicate rows by design.** This is correct behaviour and is what
makes non-directional aggregation work, but it means totals are not comparable across
entities and a `COUNT` on a view is not a count of flows.
`Orion.Netflow.FlowsByConversation` is the exception: it duplicates nothing and normalises
(A, B) and (B, A) into one pair.

**Three flow entities lack the navigation property their name implies.**
`Orion.Netflow.FlowsByApplication` has no `Application`,
`Orion.Netflow.FlowsByAdvancedApplication` has no `AdvancedApplication`, and
`Orion.Netflow.FlowsByAS` has no navigation that follows its non-directional `ASID`. Join
the lookup entity explicitly in those three cases.

**`Orion.Nodes.Flows` is ambiguous in the published relationship set.** The extracted
relationships contain two edges named `Flows` from `Orion.Nodes`, one to
`Orion.Netflow.Flows` and one to `Orion.Netflow.FlowsByApplication`. The same collision
exists on `Orion.NPM.Interfaces` for `IngressFlows` and `EgressFlows`. Write flow queries
with the flow entity in the `FROM` clause and navigate *to* the node, which is unambiguous,
rather than starting from the node and walking down.

**`InterfaceIndex` is not `InterfaceID`.** `Orion.Netflow.InterfaceSources.InterfaceIndex`,
and `InputInterfaceIndex` and `OutputInterfaceIndex` on the flow entities, are the ifIndex
values the exporting device put in the record. The platform's `InterfaceID` is a different
number. `Orion.Netflow.Flows` gives you both: `InterfaceIDRx` and `InterfaceIDTx` are the
platform ids and are what the `IngressInterface` and `EgressInterface` navigation properties
follow.

**`Orion.Netflow.InterfaceSources` is polymorphic.** Filter on
`EntityType = 'Orion.NPM.Interfaces'` before treating `EntityID` as an `InterfaceID`, and it
has no `Node` navigation property, so join on `NodeID` explicitly.

**Flow sources are toggled with verbs; CBQoS sources are toggled with CRUD.** There is no
`EnableCBQoSSources` verb and no `Orion.Netflow.FlowSources` entity to update. Use
`EnableFlowNodeSources` and `EnableFlowInterfaceSources` for flow, and an update of
`Enabled` on `Orion.Netflow.CBQoSSource` for CBQoS. `Orion.Netflow.CBQoSSource` is the only
NTA entity that supports create and delete under `manageNodes`.

**In PowerShell, wrap array arguments with the unary comma.**
`Invoke-SwisVerb $swis Orion.Netflow.NodeSources EnableFlowNodeSources @(, @([int]$nodeId))`.
Without the leading comma the array is splatted into positional arguments and the call does
not match the signature. Cast the ids to `[int]` as well.

**Two NTA entities declare `invoke` but publish no verbs.** `Orion.Netflow.Source` and
`Orion.Netflow.NodeProperties` both list `invoke` in their operations while the extracted
schema shows no verbs on them. Whether verbs exist there on a live server is
**unverified**; check with
`SELECT v.Entity.FullName, v.Name FROM Metadata.Verb v WHERE v.Entity.FullName LIKE 'Orion.Netflow.%'`.

**CBQoS policies nest, so naive sums double-count.** Use `PolicyFullPathName`, and use
`HasChildren`, `ParentPolicyID` and `RootPolicyID` when you need to pick one level of the
hierarchy. `StartDate` and `EndDate` mean a superseded policy version can still return rows.

**The diagnostics entities need the `system` right.** `Orion.Netflow.Diagnostics.Database`,
`.Tables` and `.Partitions` declare `create,read,update,delete requires system`. An ordinary
administrator account may not be able to read them, which looks like an empty result rather
than a permission error.

**Account limitations filter flow results silently.** Two accounts running the same top
talkers query legitimately get different answers, and nothing in the response says so. Rule
out permissions before concluding the data is missing.

## Related pages

- [README.md](README.md) for the module index and how to check what is installed.
- [npm.md](npm.md) for `Orion.NPM.Interfaces`, which every flow query eventually joins to.
- [qoe.md](qoe.md) for Quality of Experience, the other traffic-content module, which uses
  packet inspection rather than flow export.
- [ipam.md](ipam.md) for the IPAM group tree that `CreateFromIPAMGroup` reads from.
- [../platform/modules.md](../platform/modules.md) for the whole-schema module map.
- [../swis/invoke-verbs.md](../swis/invoke-verbs.md) for positional argument handling.
- [../swis/crud.md](../swis/crud.md) and [../swis/uris.md](../swis/uris.md) for creating and
  updating CBQoS sources and settings.
- [../reference/netobject-types.md](../reference/netobject-types.md) for the `CCM` prefix.
- [../../scripts/swql/08-schema-introspection.swql](../../scripts/swql/08-schema-introspection.swql)
  for asking a live server what it actually has.

## Official SolarWinds documentation

- [NTA 4.0 Entity Model](https://solarwinds.github.io/OrionSDK/docs/netflow-traffic-analyzer/nta-4-0-entity-model/),
  which is the authoritative explanation of the duplicating views and of the relative-date
  performance warning.
- [SWQL Functions](https://solarwinds.github.io/OrionSDK/docs/swql-functions/), including
  the date-math functions to avoid in flow queries.
- [OrionSDK sample scripts](https://github.com/solarwinds/OrionSDK/tree/master/Samples),
  including `NTA.AddFlowSources.ps1`, `NTA.AddCBQoSSources.ps1`,
  `NTA.EnableDisableFlowSources.ps1`, `NTA.EnableDisableCBQoSSources.ps1`,
  `NTA.ChangeSettings.ps1`, `NTA.EnableDisableAlert.ps1` and
  `NTA.DownloadRouterConfigFromNCM.ps1`.

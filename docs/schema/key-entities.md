# Key entities

The 2026.2 schema has 2067 entities. About fifteen of them account for most of the work.
This page is the deep reference for those: what each one is for, the property you key on,
the properties an engineer actually selects, the navigations worth knowing, the verbs it
exposes, and one runnable query per entity.

Nothing here lists every property of a wide entity, because a 102-row table is not a
reference, it is a wall. Each section says how many properties the entity has and gives the
one command that prints the rest:

```bash
python3 tools/schema_query.py show Orion.Nodes
python3 tools/schema_query.py props Orion.Nodes --grep memory
python3 tools/schema_query.py verb Orion.Nodes Unmanage
```

Two conventions used throughout. **Inherited properties are queryable.** `Uri` and
`InstanceType` come from `System.Entity`; `Status`, `DetailsUrl` and `ModernIcon` come from
`System.DashboardEntity`; `UnManaged`, `UnManageFrom`, `UnManageUntil`, `StatusDescription`
and `DisplayName` come from `System.ManagedEntity` or above. They work on descendants even
though the entity page does not declare them. See [entity-model.md](entity-model.md).
**Both relationship directions are navigable from the entity that lists them**, so
`Orion.Nodes.Interfaces` and `Orion.NPM.Interfaces.Node` are both valid SWQL. See
[relationships.md](relationships.md).

Where a "key" is given below, it is the identifier the platform and the NetObject reference
use. The published schema only states the key in prose for a handful of entities, so the
authoritative answer for your server is always:

```sql
SELECT p.Name, p.Type
FROM Metadata.Property p
WHERE p.IsKey = TRUE AND p.Entity.FullName = 'Orion.Nodes'
ORDER BY p.Name
```

Contents:

- [Orion.Nodes](#orionnodes)
- [Orion.NPM.Interfaces](#orionnpminterfaces)
- [Orion.Volumes](#orionvolumes)
- [Orion.Engines](#orionengines)
- [Orion.APM.Application](#orionapmapplication)
- [Orion.APM.Component](#orionapmcomponent)
- [Orion.Groups and Orion.ContainerMembers](#oriongroups-and-orioncontainermembers)
- [Orion.Events](#orionevents)
- [Orion.AuditingEvents](#orionauditingevents)
- [The alerting entities](#the-alerting-entities)
- [Custom property entities](#custom-property-entities)
- [Cirrus.Nodes](#cirrusnodes)
- [Orion.VIM.VirtualMachines](#orionvimvirtualmachines)

---

## Orion.Nodes

**Purpose.** The device record. Everything else in the platform hangs off it: interfaces,
volumes, applications, hardware sensors, NCM configuration, virtualization, flows. If you
are writing your first query against a new server, write it here.

**Key.** `NodeID` (`System.Int32`). NetObject prefix `N`, so node 42 is `N:42`.

**Inheritance.** `System.Entity` -> `System.DashboardEntity` ->
`System.ManagedEntity` -> `Orion.Nodes`.

**Access control.** `read` requires `everyone`; `read,invoke` requires
`allowRealTimePolling`; `create,read,update,delete,invoke` requires `manageNodes`.

**Size.** 102 declared properties, 135 source relationships, 26 target relationships,
17 verbs.

### Properties worth knowing

| Property | Type | Why you want it |
| --- | --- | --- |
| `NodeID` | `System.Int32` | The key, and the join column for almost everything |
| `Caption` | `System.String` | The display name people recognise |
| `IPAddress` | `System.String` | Primary address; `IPAddressType`, `IP`, `IP_Address` and `DNS` are also present |
| `ObjectSubType` | `System.String` | Polling method. `Orion.NPM.Interfaces.ObjectSubType` documents the equivalent values as None, SNMP, WMI, ICMP, Agent |
| `Status` | `System.Int32` | The status integer. See [status-codes.md](status-codes.md) |
| `PolledStatus` | `System.Int32` | A second status integer, node-only, undocumented relationship to `Status` |
| `StatusDescription` | `System.String` | Text form. `Orion.Nodes` redeclares it with no summary of its own, so the documentation comes from the `System.ManagedEntity` declaration |
| `UnManaged`, `UnManageFrom`, `UnManageUntil` | `System.Boolean`, `System.DateTime` | Maintenance window state, inherited |
| `Vendor`, `MachineType`, `SysObjectID`, `SysName` | `System.String` | What the device is |
| `Location`, `Contact` | `System.String` | SNMP sysLocation and sysContact |
| `EngineID` | `System.Int32` | Which polling engine owns it. Writable: this is how you rebalance |
| `PollInterval`, `StatCollection`, `RediscoveryInterval` | `System.Int32` | Scheduling |
| `NextPoll`, `NextRediscovery`, `LastSync`, `MinutesSinceLastSync` | `System.DateTime`, `System.Int32` | Poller health |
| `ResponseTime`, `AvgResponseTime`, `MinResponseTime`, `MaxResponseTime`, `PercentLoss` | `System.Int32`, `System.Double` | ICMP results |
| `CPULoad`, `CPUCount`, `PercentMemoryUsed`, `MemoryUsed`, `MemoryAvailable`, `TotalMemory` | mixed numerics | Current resource load |
| `LoadAverage1`, `LoadAverage5`, `LoadAverage15` | `System.Double` | Unix-style load, when polled |
| `LastBoot`, `SystemUpTime` | `System.DateTime`, `System.Double` | Uptime |
| `External` | `System.Boolean` | Node is not pinged for up/down; pairs with status 11 |
| `IsServer`, `IsOrionServer` | `System.Boolean` | Role flags |
| `SNMPVersion`, `Community`, `RWCommunity`, `AgentPort`, `Allow64BitCounters` | mixed | SNMP configuration |
| `Severity`, `UiSeverity`, `ChildStatus`, `CustomStatus`, `GroupStatus` | mixed | Status-adjacent, and each means something different. See [status-codes.md](status-codes.md) |
| `DetailsUrl` | `System.String` | Link to the node's page in the web console |
| `Uri` | `System.String` | The SWIS URI, which is what CRUD addresses |

That is 55 names in the left-hand column, but they do not all come out of the same pot: 51
are among the 102 `Orion.Nodes` declares, and four are inherited rather than declared,
namely `Uri` and the `UnManage*` trio. Four more declared properties, `IPAddressType`,
`IP`, `IP_Address` and `DNS`, are named in passing in the third column, which leaves 47 of
the 102 unmentioned on this page. For those, including the buffer-miss counters and the
cloud instance fields:

```bash
python3 tools/schema_query.py show Orion.Nodes
```

### Navigations worth knowing

| Navigation | Leads to | Kind |
| --- | --- | --- |
| `Interfaces` | `Orion.NPM.Interfaces` | Hosting, to-many |
| `Volumes` | `Orion.Volumes` | Hosting, to-many |
| `Applications` | `Orion.APM.Application` | Hosting, to-many |
| `CustomProperties` | `Orion.NodesCustomProperties` | Hosting, to-one |
| `Engine` | `Orion.Engines` | Reference, to-one |
| `Events` | `Orion.Events` | Reference, to-many |
| `HardwareHealthInfos` | `Orion.HardwareHealth.HardwareInfo` | Hosting |
| `Agent` | `Orion.AgentManagement.Agent` | Reference |
| `VirtualMachine` | `Orion.VIM.VirtualMachines` | Reference |
| `NodeProperties` | `NCM.NodeProperties` | Hosting |
| `NodeVlans` | `Orion.NodeVlans` | Hosting |
| `CPULoadHistory`, `CPUMultiLoadHistory`, `ResponseTimeHistory` | `Orion.CPULoad`, `Orion.CPUMultiLoad`, `Orion.ResponseTime` | Hosting, historical |
| `WebUri` | `Orion.NodeWebUri` | Hosting |

There is **no** `Orion.Nodes.StatusInfo` navigation. Join `Orion.StatusInfo` explicitly.
There is also no direct navigation to `Cirrus.Nodes`; see [Cirrus.Nodes](#cirrusnodes).

### Verbs

17 of them. The ones you will actually call:

| Verb | Parameters, in order | Right |
| --- | --- | --- |
| `Unmanage` | `netObjectId: string`, `unmanageTime: string`, `remanageTime: string`, `isRelative: boolean`, `allowOverlapping: boolean` (optional) | `allowUnmanage` |
| `Remanage` | `netObjectId: string` | `allowUnmanage` |
| `PollNow` | `netObjectId: string` | `manageNodes` |
| `PollStatusNow` | `netObjectId: string` | `manageNodes` |
| `RediscoverNow` | `netObjectId: string` | `manageNodes` |
| `GetSupportedMetrics` | `netObjectId: number` | `allowRealTimePolling` or `admin` |
| `StartRealTimePolling` | `netObjectId: number`, `owner: string`, `properties: array`, `pollingExpiration: System.TimeSpan`, `pollingFrequency: System.TimeSpan` | `allowRealTimePolling` or `admin` |
| `StopRealTimePolling` | `netObjectId: number`, `owner: string`, `properties: array` | `allowRealTimePolling` or `admin` |
| `ScheduleListResources` | `nodeId: number` | `manageNodes` |
| `GetScheduledListResourcesStatus` | `jobId: string`, `nodeId: number` | `manageNodes` |
| `GetListResourcesResult` | `jobId: string`, `nodeId: number` | `manageNodes` |
| `ImportSelectedListResourcesResult` | `jobId: string`, `nodeId: number`, `resources: array` | `manageNodes` |
| `ImportListResourcesResult` | `jobId: string`, `nodeId: number` | `manageNodes` |

The remaining four are `GetCountOfElementsPerEngineForLicensing`,
`ScheduleListResourcesForAddress`, `GetScheduledListResourcesStatusByEngine` and
`GetListResourcesResultByEngine`.

Note the split in the `netObjectId` type. `Unmanage`, `Remanage`, `PollNow`,
`PollStatusNow` and `RediscoverNow` declare it as a **string** and want `N:42`.
`GetSupportedMetrics`, `StartRealTimePolling` and `StopRealTimePolling` declare it as a
**number** and want `42`. Same parameter name, different contract. Arguments go on the wire
positionally, so see [../swis/invoke-verbs.md](../swis/invoke-verbs.md) before calling any
of these, and [netobject-types.md](netobject-types.md) for the prefixes.

### Example

Every unmanaged-excluded node that is not up, with the polling engine that owns it:

```sql
SELECT TOP 50
    n.NodeID,
    n.Caption,
    n.IPAddress,
    n.Vendor,
    n.MachineType,
    n.Status,
    n.StatusDescription,
    n.PercentLoss,
    n.AvgResponseTime,
    n.Engine.ServerName AS PollingEngine
FROM Orion.Nodes n
WHERE n.UnManaged = FALSE AND n.Status <> 1
ORDER BY n.Caption
```

---

## Orion.NPM.Interfaces

**Purpose.** One row per monitored interface. The published schema summarises it as "This
entity presents information about Node interfaces". This is the highest-cardinality core
entity on most installations, so it is also where careless queries hurt most.

**Key.** `InterfaceID` (`System.Int32`), stated in the schema's own property prose:
"Interface ID. Primary key." NetObject prefix `I`, so interface 7 is `I:7`.

**Inheritance.** `System.Entity` -> `System.DashboardEntity` ->
`System.ManagedEntity` -> `Orion.NPM.Interfaces`.

**Access control.** `read` requires `everyone`; `read,invoke` requires
`allowRealTimePolling`; `create,read,update,delete,invoke` requires `manageNodes`.

**Size.** 92 declared properties, 47 source relationships, 11 target relationships,
10 verbs.

### Properties worth knowing

This entity has an unusual habit: many properties exist twice under different names, once
plain and once `Interface`-prefixed. `Speed` and `InterfaceSpeed`, `Caption` and
`InterfaceCaption`, `Alias` and `InterfaceAlias`, `MTU` and `InterfaceMTU`, `Index` and
`InterfaceIndex`, `Type` and `InterfaceType`, `TypeName` and `InterfaceTypeName`,
`LastChange` and `InterfaceLastChange`. Both spellings are real properties. Pick one and be
consistent, because a report that mixes them is harder to read than it needs to be.

| Property | Type | Why you want it |
| --- | --- | --- |
| `InterfaceID` | `System.Int32` | The key |
| `NodeID` | `System.Int32` | Parent node; the join column if you are not navigating |
| `Caption`, `FullName`, `Name`, `IfName` | `System.String` | Names. `FullName` includes the node |
| `Alias` | `System.String` | The `ifAlias` a network manager set, described as a non-volatile handle |
| `Index` | `System.Int32` | `ifIndex` |
| `Status` | `System.Int32` | "calculated from the AdminStatus and OperStatus properties" |
| `AdminStatus`, `OperStatus` | `System.Int16` | SNMP `ifAdminStatus` and `ifOperStatus`. Their own enumerations, not platform status codes |
| `Speed`, `InBandwidth`, `OutBandwidth`, `CustomBandwidth` | `System.Double`, `System.Boolean` | Capacity. Utilisation percentages are computed against these |
| `Inbps`, `Outbps`, `Bps` | `System.Single`, `System.Double` | Current throughput |
| `InPercentUtil`, `OutPercentUtil`, `PercentUtil` | `System.Single`, `System.Double` | Current utilisation |
| `InPps`, `OutPps`, `InUcastPps`, `OutUcastPps`, `InMcastPps`, `OutMcastPps` | `System.Single` | Packet rates |
| `InErrorsToday`, `OutErrorsToday`, `InDiscardsToday`, `OutDiscardsToday` | `System.Single` | Error and discard counts; `...ThisHour` variants exist too |
| `CRCAlignErrorsToday`, `LateCollisionsToday` | `System.Single` | Ethernet-specific counters |
| `MaxInBpsToday`, `MaxOutBpsToday`, `MaxInBpsTime`, `MaxOutBpsTime` | `System.Single`, `System.DateTime` | Daily peaks and when they happened |
| `TypeName`, `TypeDescription`, `Type` | `System.String`, `System.Int32` | `ethernetCsmacd`, `Ethernet`, and the numeric type |
| `PhysicalAddress`, `MAC` | `System.String` | Hardware address |
| `MTU` | `System.Int32` | Largest packet in octets |
| `UnPluggable` | `System.Boolean` | Marks the interface as reporting Unplugged instead of Down |
| `Counter64` | `System.Char` | `'Y'` or `'N'`, whether 64-bit counters are in use |
| `HasObsoleteData`, `ObsoleteDataCurrentSettingValue`, `ObsoleteDataFeatureStatus` | mixed | Whether the displayed data is stale, and the thresholds controlling that |
| `LastChange`, `LastSync`, `NextPoll`, `NextRediscovery`, `SkippedPollingCycles` | mixed | Freshness |
| `OrionIdPrefix`, `OrionIdColumn` | `System.String` | The entity's own NetObject prefix, documented as `'I:'` |

For the rest, including the duplicate-named set in full:

```bash
python3 tools/schema_query.py props Orion.NPM.Interfaces
```

### Navigations worth knowing

| Navigation | Leads to | Direction |
| --- | --- | --- |
| `Node` | `Orion.Nodes` | Target, hosting, to-one |
| `StatusInfo` | `Orion.StatusInfo` | Source, to-one |
| `CustomProperties` | `Orion.NPM.InterfacesCustomProperties` | Source, hosting |
| `Traffic` | `Orion.NPM.InterfaceTraffic` | Source, hosting, historical |
| `Errors` | `Orion.NPM.InterfaceErrors` | Source, hosting, historical |
| `Availability` | `Orion.NPM.InterfaceAvailability` | Source, reference |
| `InterfaceDowntimeHistory` | `Orion.NPM.InterfaceNetObjectDowntime` | Source, hosting |
| `InPercentUtilizationThreshold`, `OutPercentUtilizationThreshold` | `Orion.NPM.InPercentUtilizationThreshold`, `Orion.NPM.OutPercentUtilizationThreshold` | Source, hosting |
| `IngressFlows`, `EgressFlows` | `Orion.Netflow.Flows` and friends | Source, reference |
| `RoutingNeighbor`, `RoutingTable` | `Orion.Routing.Neighbors`, `Orion.Routing.RoutingTable` | Target |

`StatusInfo` is one of only ten navigations to `Orion.StatusInfo` in the whole schema, so
interface queries can resolve a status name without an explicit join.

### Verbs

| Verb | Parameters, in order |
| --- | --- |
| `Unmanage` | `netObjectId: string`, `unmanageTime: string`, `remanageTime: string`, `isRelative: boolean`, `allowOverlapping: boolean` |
| `Remanage` | `netObjectId: string` |
| `SetBandwidth` | `netObjectId: string`, `inBandwidth: number`, `outBandwidth: number`, `customBandwidth: boolean` |
| `SetPowerLevel` | `interfaceId: number`, `powerLevel: number` |
| `DiscoverInterfacesOnNode` | `nodeId: number` |
| `AddInterfacesOnNode` | `nodeId: number`, `interfacesToAdd: array`, `pollers: ...AddPollers` |
| `CreateInterfacesPluginConfiguration` | `context: ...InterfacesDiscoveryPluginContext` |
| `GetSupportedMetrics` | `netObjectId: number` |
| `StartRealTimePolling` | `netObjectId: number`, `owner: string`, `properties: array`, `pollingExpiration: System.TimeSpan`, `pollingFrequency: System.TimeSpan` |
| `StopRealTimePolling` | `netObjectId: number`, `owner: string`, `properties: array` |

`DiscoverInterfacesOnNode` then `AddInterfacesOnNode` is the two-step for adding interfaces
to an existing node without running a full discovery. `SetBandwidth` is documented as
applying the provided values when `customBandwidth` is true and resetting both when it is
false.

### Example

Interfaces running hot, with the status name resolved through the navigation rather than a
join:

```sql
SELECT TOP 50
    i.Node.Caption AS NodeName,
    i.Caption AS InterfaceName,
    i.InterfaceID,
    i.AdminStatus,
    i.OperStatus,
    i.StatusInfo.StatusName,
    i.Speed,
    i.InPercentUtil,
    i.OutPercentUtil
FROM Orion.NPM.Interfaces i
WHERE i.UnManaged = FALSE AND i.InPercentUtil > 80
ORDER BY i.InPercentUtil DESC
```

---

## Orion.Volumes

**Purpose.** Disks and logical volumes on a node, including the space and IOPS figures that
capacity reports live on.

**Key.** `VolumeID` (`System.Int32`). NetObject prefix `V`.

**Inheritance.** `System.Entity` -> `System.DashboardEntity` ->
`System.ManagedEntity` -> `Orion.Volumes`.

**Access control.** Same three rules as `Orion.Nodes`: `everyone` to read,
`allowRealTimePolling` for real-time invoke, `manageNodes` for everything.

**Size.** 53 declared properties, 19 source relationships, 3 target relationships, 5 verbs.

### Properties worth knowing

| Property | Type | Why you want it |
| --- | --- | --- |
| `VolumeID` | `System.Int32` | The key |
| `NodeID` | `System.Int32` | Parent node |
| `Caption`, `FullName`, `DisplayName`, `VolumeDescription` | `System.String` | Names |
| `VolumeType`, `VolumeTypeID`, `Type` | `System.String`, `System.Int32` | Fixed disk, network share, RAM disk and so on |
| `VolumeSize`, `Size` | `System.Double` | Capacity in bytes |
| `VolumeSpaceUsed`, `VolumeSpaceAvailable`, `VolumeSpaceAvailableExp` | `System.Double` | Used and free |
| `VolumePercentUsed`, `VolumePercentAvailable` | `System.Single`, `System.Double` | The two columns capacity reports actually select |
| `Status`, `StatusDescription` | `System.Int32`, `System.String` | Status |
| `DiskQueueLength`, `DiskReads`, `DiskWrites`, `DiskTransfer`, `TotalDiskIOPS` | `System.Double` | Performance |
| `VolumeAllocationFailuresToday`, `VolumeAllocationFailuresThisHour` | `System.Int32` | Allocation failures |
| `Responding`, `VolumeResponding` | `System.Char` | Whether the volume answered |
| `Index`, `VolumeIndex` | `System.Int32` | Position on the node |
| `DeviceId`, `DiskSerialNumber`, `InterfaceType` | `System.String` | Physical identity |
| `SCSITargetId`, `SCSILunId`, `SCSIPortId`, `SCSIControllerId`, `SCSIPortOffset` | mixed | SCSI addressing |
| `PollInterval`, `StatCollection`, `RediscoveryInterval`, `NextPoll`, `NextRediscovery` | mixed | Scheduling |
| `LastSync`, `MinutesSinceLastSync`, `SkippedPollingCycles` | mixed | Freshness |
| `OrionIdPrefix`, `OrionIdColumn` | `System.String` | NetObject prefix, from the server |

### Navigations worth knowing

`Node` (target, to `Orion.Nodes`, hosting) and `StatusInfo` (source, to
`Orion.StatusInfo`) are the two you use constantly. Also present: `CustomProperties` to
`Orion.VolumesCustomProperties`, `Stats` to `Orion.VolumesStats`, `VolumeUsageHistory` and
`VolumePerformanceHistory` for history, `ForecastCapacity` to
`Orion.VolumesForecastCapacity`, `PercentDiskUsedThreshold` to
`Orion.PercentDiskUsedThreshold`, and a set of `Rely...` reliance edges into Storage
Resource Monitor: `RelyLUN`, `RelyFileShare`, `RelyStorageArray`, `RelyPool`,
`RelyNasVolume`, `RelyVserver`. `LUN` and `FileShare` are the target-side counterparts.

### Verbs

| Verb | Parameters, in order | Right |
| --- | --- | --- |
| `Unmanage` | `netObjectId: string`, `unmanageTime: string`, `remanageTime: string`, `isRelative: boolean`, `allowOverlapping: boolean` | `allowUnmanage` |
| `Remanage` | `netObjectId: string` | `allowUnmanage` |
| `GetSupportedMetrics` | `netObjectId: number` | `allowRealTimePolling` or `admin` |
| `StartRealTimePolling` | `netObjectId: number`, `owner: string`, `properties: array`, `pollingExpiration: System.TimeSpan`, `pollingFrequency: System.TimeSpan` | `allowRealTimePolling` or `admin` |
| `StopRealTimePolling` | `netObjectId: number`, `owner: string`, `properties: array` | `allowRealTimePolling` or `admin` |

The string form takes `V:` prefixed ids.

### Example

The classic "which disks are about to fill up" query:

```sql
SELECT TOP 25
    v.Node.Caption AS NodeName,
    v.Caption AS VolumeName,
    v.VolumeType,
    v.VolumeSize,
    v.VolumeSpaceUsed,
    v.VolumePercentUsed,
    v.StatusInfo.StatusName
FROM Orion.Volumes v
WHERE v.UnManaged = FALSE AND v.VolumePercentUsed > 90
ORDER BY v.VolumePercentUsed DESC
```

---

## Orion.Engines

**Purpose.** The polling engines. The schema summarises it as "This entity contains main
poller and all additional pollers list". You read this entity to answer "is polling keeping
up" and you write to `Orion.Nodes.EngineID` to change the answer.

**Key.** `EngineID` (`System.Int32`). No NetObject prefix.

**Inheritance.** `System.Entity` -> `Orion.Engines`. Note that it is **not** a
`System.ManagedEntity`, so there is no `UnManaged` and no `Status` on it.

**Access control.** `read` requires `everyone`; `create,update,delete` requires `system`.

**Size.** 51 declared properties, 9 source relationships, 3 target relationships, and
**no verbs at all**. Everything you do to an engine you do through CRUD or by editing nodes.

### Properties worth knowing

| Property | Type | Why you want it |
| --- | --- | --- |
| `EngineID` | `System.Int32` | The key, and `Orion.Nodes.EngineID` points at it |
| `ServerName`, `IP`, `DisplayName` | `System.String` | Which machine |
| `ServerType` | `System.String` | Primary versus additional poller |
| `MasterEngineID` | `System.Int32` | Which engine this one reports to |
| `PollingCompletion` | `System.Single` | The health number. See below |
| `AvgCPUUtil`, `MemoryUtil` | `System.Single` | Engine host load |
| `Elements`, `Nodes`, `Interfaces`, `Volumes`, `Pollers` | `System.Int32` | Configured load, by object type |
| `LicensedElements`, `Evaluation`, `EvalDaysLeft`, `PackageName`, `SerialNumber` | mixed | Licensing |
| `KeepAlive`, `MinutesSinceKeepAlive` | `System.DateTime`, `System.Int32` | Is the engine alive |
| `SysLogKeepAlive`, `TrapsKeepAlive`, `MinutesSinceSysLogKeepAlive`, `MinutesSinceTrapsKeepAlive` | mixed | Are the syslog and trap receivers alive |
| `Restart`, `StartTime`, `MinutesSinceRestart`, `MinutesSinceStartTime` | mixed | Recent restarts |
| `FailOverActive`, `MinutesSinceFailOverActive` | mixed | High availability state |
| `EngineVersion`, `WindowsVersion`, `ServicePack` | `System.String` | Version drift across a pool |
| `NodePollInterval`, `InterfacePollInterval`, `VolumePollInterval` | `System.Int16` | Default intervals |
| `NodeStatPollInterval`, `InterfaceStatPollInterval`, `VolumeStatPollInterval`, `StatPollInterval` | mixed | Statistics intervals |
| `MaxPollsPerSecond`, `MaxStatPollsPerSecond` | `System.Int16` | Rate caps |
| `BusinessLayerPort`, `FIPSModeEnabled`, `IsFree` | mixed | Configuration flags |

SolarWinds explains `PollingCompletion` directly:

> A polling completion value of 100 indicates that all jobs are completed on schedule.
> Polling completion should stay in the high 90s. Anything less indicates a performance
> problem.
>
> [Polling engine load balancing](https://solarwinds.github.io/OrionSDK/docs/polling-engine-load-balancing/)

The same page names `Orion.PollingUsage` as the licensed-capacity counterpart, which carries
`EngineID`, `ScaleFactor`, `CurrentUsage` and `IsExceeded`, and it states that reassignment
is done "by setting the `EngineID` property of the `Orion.Nodes` instance", which is a CRUD
update against the node's `Uri` rather than a verb.

### Navigations worth knowing

`AssignedNodes` leads to `Orion.Nodes` and is to-many, which is the reverse of
`Orion.Nodes.Engine`. `PollingUsage` leads to `Orion.PollingUsage`, `EngineProperties` to
`Orion.EngineProperties`, `Events` to `Orion.Events`, `Agents` to
`Orion.AgentManagement.Agent`, `PoolMember` to `Orion.HA.PoolMembers` and
`ReachabilityInfo` to `Orion.ReachabilityInfo`.

### Example

The polling engine health board, in one query:

```sql
SELECT
    e.EngineID,
    e.ServerName,
    e.ServerType,
    e.EngineVersion,
    e.Elements,
    e.Nodes,
    e.Interfaces,
    e.Volumes,
    e.Pollers,
    e.PollingCompletion,
    e.AvgCPUUtil,
    e.MemoryUtil,
    e.MinutesSinceKeepAlive
FROM Orion.Engines e
ORDER BY e.ServerName
```

---

## Orion.APM.Application

**Purpose.** One monitored application instance, meaning one SAM template applied to one
node. The schema summarises it as "This entity presents all applications". The components
under it do the actual measuring.

**Key.** `ApplicationID` (`System.Int32`). There is also an `ID` property carrying the same
description, "The unique integer representation of application". NetObject prefix `AA`, so
application 91 is `AA:91`.

**Inheritance.** `System.Entity` -> `System.DashboardEntity` ->
`System.ManagedEntity` -> `Orion.APM.Application`.

**Access control.** `read` requires `everyone`; `read,update,invoke` requires `manageNodes`;
`invoke` requires `allowUnmanage`. Note there is no `create` or `delete` right listed:
applications are created and deleted through the `CreateApplication` and `DeleteApplication`
verbs, not through CRUD.

**Size.** 25 declared properties, 14 source relationships, 4 target relationships, 7 verbs.
This is a narrow entity, so the table below is nearly all of it.

### Properties worth knowing

| Property | Type | Summary from the schema |
| --- | --- | --- |
| `ApplicationID` | `System.Int32` | The unique integer representation of application |
| `Name` | `System.String` | The name of the application |
| `DisplayName` | `System.String` | A user friendly name |
| `NodeID` | `System.Int32` | The parent node |
| `ApplicationTemplateID` | `System.Int32` | Which template it came from |
| `Status` | `System.Int32` | The status of an application |
| `StatusDescription` | `System.String` | Application status description |
| `UnManaged`, `UnManageFrom`, `UnManageUntil` | `System.Boolean`, `System.DateTime` | Maintenance window |
| `Created`, `LastModified` | `System.DateTime` | Lifecycle timestamps |
| `FullyQualifiedName` | `System.String` | The fully qualified name of the parent node |
| `HasCredentials` | `System.Boolean` | Whether a credential set is attached |
| `CustomApplicationType` | `System.String` | Custom application type |
| `PrimaryGroupID` | `System.Int32` | Set when the application came from a template group assignment |
| `DetailsUrl` | `System.String` | URL to the details page, documented as used in alerting |
| `Uri` | `System.String` | The SWIS URI |

### Navigations worth knowing

| Navigation | Leads to | Note |
| --- | --- | --- |
| `Node` | `Orion.Nodes` | Target, hosting. The normal way up |
| `RelyNode` | `Orion.Nodes` | Source, reliance. A second, different edge |
| `Components` | `Orion.APM.Component` | Source, hosting, to-many |
| `Template` | `Orion.APM.ApplicationTemplate` | Target, reference. `Template.Name` is the template name |
| `CurrentStatus` | `Orion.APM.CurrentApplicationStatus` | Latest poll: `LastTimeUp`, `ErrorMessage`, `LastSuccessfulPoll`, `Availability` |
| `ApplicationStatus` | `Orion.APM.ApplicationStatus` | Historical availability rows |
| `CustomProperties` | `Orion.APM.ApplicationCustomProperties` | Source, hosting |
| `DatabaseInstance` | `Orion.DPA.DatabaseInstance` | Source, reference |
| `ScheduledTasks` | `Orion.APM.Wstm.Task` | Source, hosting |

`Node` and `RelyNode` both reach `Orion.Nodes` and are different relationship kinds
(hosting versus reliance). Use `Node` unless you specifically want the dependency edge.

### Verbs

| Verb | Parameters, in order | Right |
| --- | --- | --- |
| `CreateApplication` | `nodeId: number`, `applicationTemplateId: number`, `credentialSetId: number`, `skipIfDuplicate: boolean`, `applicationSettings: array` | `manageNodes` |
| `DeleteApplication` | `applicationId: number` | `manageNodes` |
| `PollNow` | `applicationId: number` | `manageNodes` |
| `Unmanage` | `netObjetId: string`, `unmanageTime: string`, `remanageTime: string`, `isRelative: boolean`, `allowOverlapping: boolean` | none on the verb; the entity's `invoke` rule is `allowUnmanage` |
| `Remanage` | `netObjetId: string` | none on the verb; the entity's `invoke` rule is `allowUnmanage` |
| `TriggerInstantTemplateGroupAssignment` | none | `manageNodes` |
| `TriggerScheduledTemplateGroupAssignment` | none | `manageNodes` |

`netObjetId` is spelled that way in the contract, missing the `c`. It is a real,
documented quirk, not a transcription error here. Positional callers are unaffected;
generated clients that bind by name are not. Note also that `Unmanage` here takes an `AA:`
prefixed string while `PollNow` and `DeleteApplication` take a bare integer.

### Example

Applications that are down, warning or critical, with their template:

```sql
SELECT TOP 50
    a.ApplicationID,
    a.Name AS ApplicationName,
    a.Node.Caption AS NodeName,
    a.Status,
    a.StatusDescription,
    a.Template.Name AS TemplateName,
    a.CurrentStatus.LastSuccessfulPoll
FROM Orion.APM.Application a
WHERE a.UnManaged = FALSE AND a.Status IN (2, 3, 14)
ORDER BY a.Node.Caption, a.Name
```

---

## Orion.APM.Component

**Purpose.** One monitored thing inside an application: a process, a port check, a
performance counter, a script. Summarised as "This entity presents component". Component
status is what rolls up into application status.

**Key.** `ComponentID` (`System.Int64`). Note the 64-bit width, which matters when you carry
the value into client code. NetObject prefix `AM`.

**Inheritance.** `System.Entity` -> `System.DashboardEntity` ->
`System.ManagedEntity` -> `Orion.APM.Component`.

**Access control.** `read` requires `everyone`; `read,update,delete,invoke` requires
`manageNodes`. There is no `create`: components come from the template.

**Size.** 22 declared properties, 18 source relationships, 4 target relationships, 1 verb.

### Properties worth knowing

| Property | Type | Summary from the schema |
| --- | --- | --- |
| `ComponentID` | `System.Int64` | The unique integer representation of component |
| `ApplicationID` | `System.Int32` | The parent application |
| `TemplateID` | `System.Int64` | The parent application template |
| `Name`, `ComponentName`, `ShortName` | `System.String` | Names |
| `ComponentType` | `System.Int32` | The component type |
| `ComponentEvidenceType` | `System.Int32` | Which evidence chart applies |
| `Status`, `StatusDescription` | `System.Int32`, `System.String` | Status |
| `Disabled` | `System.Boolean` | Whether the component is disabled |
| `UnManaged`, `UnManageFrom`, `UnManageUntil` | `System.Boolean`, `System.DateTime` | Maintenance window |
| `ComponentOrder` | `System.Int32` | Display position |
| `UserDescription`, `UserNotes` | `System.String` | Operator annotations |
| `FullyQualifiedName` | `System.String` | Fully qualified name of the parent node |
| `ApplicationItemID` | `System.Int32` | The application item this maps to |
| `DetailsUrl` | `System.String` | Used in alerting |

### Navigations worth knowing

**There is no `Orion.APM.Component.Node`.** This is the single most common invented
navigation in SAM queries. The route to the node is two hops:

```text
Orion.APM.Component --Application--> Orion.APM.Application --Node--> Orion.Nodes
```

which is `c.Application.Node.Caption` in SWQL. Confirm it yourself with:

```bash
python3 tools/schema_query.py path Orion.APM.Component Orion.Nodes
```

Other navigations worth knowing: `CurrentStatus` to `Orion.APM.CurrentComponentStatus`,
which carries `ErrorCode`, `ErrorMessage`, `PercentCPU`, `PercentMemory`,
`PercentVirtualMemory`, `LastTimeUp` and `IsFallbackUsed`; `ComponentStatus` to
`Orion.APM.ComponentStatus` for historical availability; `CurrentStatistics` to
`Orion.APM.CurrentStatistics`; `ResponseTime`, `HistoricalCPULoad`, `HistoricalMemory` and
`HistoricalIOOperations` for trends; `ComponentDefinition` to
`Orion.APM.ComponentDefinition`; and `ComponentAlertThresholds` to
`Orion.APM.ComponentAlertThresholds`.

### Verbs

One: `CalculateBaselineThresholds(componentId: number, thresholdName: string)`, which
"Calculates and sets baseline thresholds for component threshold" and returns a
`SolarWinds.APM.Common.Models.Threshold`.

### Example

Down components with the error message the poller recorded, reaching the node through the
application:

```sql
SELECT TOP 50
    c.ComponentID,
    c.Name AS ComponentName,
    c.Application.Name AS ApplicationName,
    c.Application.Node.Caption AS NodeName,
    c.Status,
    c.CurrentStatus.ErrorMessage,
    c.CurrentStatus.PercentCPU
FROM Orion.APM.Component c
WHERE c.Status = 2 AND c.Disabled = FALSE
ORDER BY c.Application.Node.Caption, c.Name
```

---

## Orion.Groups and Orion.ContainerMembers

**Purpose.** Arbitrary collections of monitored objects that track an aggregate status.
SolarWinds puts it plainly:

> Orion Groups allow you to create arbitrary collections of managed entities. Once created,
> a group tracks the aggregate status of its members. A group is itself a managed entity,
> which means that groups can be nested. [...] Within Orion, Groups are a specific type of
> the more general "container" system, so the API refers to them this way.
>
> [Groups](https://solarwinds.github.io/OrionSDK/docs/groups/)

That last sentence is the thing to internalise, because it explains the entity layout.

**Three entities, three jobs.**

`Orion.Container` is the base. It declares the 13 real properties and **all 11 verbs**.

`Orion.Groups` inherits from `Orion.Container` and declares exactly one property of its own,
`ModernIcon`. Everything useful on a group, `ContainerID`, `Name`, `Owner`, `RollupType`,
`PollingEnabled`, `IsDeleted`, `LastChanged`, comes from `Orion.Container` by inheritance,
and `Status` comes from `System.DashboardEntity` two levels further up. Selecting from
`Orion.Groups` and from `Orion.Container` gives you the same columns; the difference is
which rows come back.

`Orion.ContainerMembers` is the membership table, and it is deliberately polymorphic.

**Keys.** `Orion.Groups`: `ContainerID` (`System.Int32`), NetObject prefix `C`.
`Orion.ContainerMembers`: the composite `ContainerID`, `MemberEntityType`,
`MemberPrimaryID`, NetObject prefix `GM`.

### Orion.Container properties

| Property | Type | Why you want it |
| --- | --- | --- |
| `ContainerID` | `System.Int32` | The key |
| `Name` | `System.String` | Group name |
| `Owner` | `System.String` | The managing component, documented as "should always be `Core`" |
| `Frequency` | `System.Int32` | How often status is recalculated, in seconds |
| `StatusCalculator` | `System.Int16` | Which calculator is in use |
| `RollupType` | `System.String` | Rollup mode |
| `PollingEnabled` | `System.Boolean` | Whether status history is kept |
| `IsDeleted` | `System.Boolean` | Soft-delete flag. Filter on it |
| `LastChanged` | `System.DateTime` | Last edit |
| `DetailsUrl` | `System.String` | Console link |

SolarWinds documents the rollup modes as arguments to `CreateContainer`: "0 means Mixed
status shows warning, 1 means Show worst status, and 2 means Show best status".

### Orion.ContainerMembers properties

| Property | Type | Why you want it |
| --- | --- | --- |
| `ContainerID` | `System.Int32` | Which group |
| `MemberEntityType` | `System.String` | The member's entity name, for example `Orion.Nodes` |
| `MemberPrimaryID` | `System.Int64` | The member's key. 64-bit, so it accommodates every member type |
| `Name`, `FullName` | `System.String` | Member names |
| `Status` | `System.Int32` | The member's status, resolvable against `Orion.StatusInfo` |
| `MemberUri` | `System.Uri` | The type-agnostic handle to act on the member |
| `EntityDisplayName`, `EntityDisplayNamePlural` | `System.String` | Human labels for the member's type |
| `MemberAncestorDisplayNames`, `MemberAncestorDetailsUrls` | `System.String[]` | The containment chain |
| `DetailsUrl` | `System.String` | Console link |

`Container` is the one navigation, leading back to `Orion.Container`, so
`cm.Container.Name` needs no join. Getting from a member row to the typed entity does need a
join, and it needs `MemberEntityType` in the `WHERE` clause as well as the key comparison,
or a volume whose `VolumeID` happens to match a node's `NodeID` will match. See
[../swql/joins-and-navigation.md](../swql/joins-and-navigation.md).

### Verbs

All 11 live on `Orion.Container`, not on `Orion.Groups`, which has none.

| Verb | Parameters, in order |
| --- | --- |
| `CreateContainer` | `name: string`, `owner: string`, `frequency: number`, `statusCalculator: number`, `description: string`, `pollingEnabled: boolean`, `memberDefinitions: array` |
| `CreateContainerWithParent` | `parentId: number`, then the same seven |
| `UpdateContainer` | `containerId: number`, `name`, `owner`, `frequency`, `statusCalculator`, `description`, `pollingEnabled` |
| `DeleteContainer` | `containerId: number` |
| `AddDefinition` | `containerId: number`, `memberDefinition: MemberDefinitionInfo` |
| `AddDefinitions` | `containerId: number`, `memberDefinitions: array` |
| `UpdateDefinition` | `definitionId: number`, `memberDefinition: MemberDefinitionInfo` |
| `SetDefinitions` | `containerId: number`, `memberDefinitions: array` |
| `DeleteDefinition` | `definitionId: number` |
| `DeleteDefinitions` | `containerId: number`, `definitionIds: array` |
| `GetDefinitionFilterQuery` | `queryDefinition: string` |

A `MemberDefinitionInfo` has `Name` and `Definition`. `Definition` is either a SWIS URI for
a static member, such as `swis://my-orion-instance/Orion/Orion.Nodes/NodeID=42`, or a
filter for a dynamic rule, such as `filter:/Orion.Nodes[Vendor='Cisco']`. Navigation
properties work inside a filter, which is how you build a group from a custom property:
`filter:/Orion.Nodes[CustomProperties.City='Austin']`. All three forms are SolarWinds'
own examples.

### Example

Every group with its member count, biggest first:

```sql
SELECT
    g.ContainerID,
    g.Name AS GroupName,
    g.Status,
    g.RollupType,
    g.PollingEnabled,
    COUNT(cm.MemberPrimaryID) AS MemberCount
FROM Orion.Groups g
LEFT JOIN Orion.ContainerMembers cm ON cm.ContainerID = g.ContainerID
GROUP BY g.ContainerID, g.Name, g.Status, g.RollupType, g.PollingEnabled
ORDER BY COUNT(cm.MemberPrimaryID) DESC
```

---

## Orion.Events

**Purpose.** The event log. The schema summarises it as containing "event records generated
by the Orion monitoring system, including network events, status changes, and system
notifications".

**Key.** `EventID` (`System.Int32`). No NetObject prefix; events are addressed by key.

**Inheritance.** `System.Entity` -> `Orion.MixedObjectType` -> `Orion.Events`.
`Orion.MixedObjectType` is described as the "Base class for SWIS entities that contains
records from multiple netobject types. E.g. Orion.Events", and it contributes
`NetworkNode`, `NetObjectID` and `NetObjectType`.

**Access control.** `read,invoke` requires `everyone`; `create,read,invoke` requires
`admin`. There is no update and no delete: events are append-only from the API's point of
view.

**Size.** 8 declared properties plus 3 inherited from `Orion.MixedObjectType`, 3 target
relationships, 1 verb.

### Properties

| Property | Type | Summary from the schema |
| --- | --- | --- |
| `EventID` | `System.Int32` | Unique identifier for the event record |
| `EventTime` | `System.DateTime` | When the event occurred, **displayed in local time** |
| `EventType` | `System.Int32` | Numeric identifier referencing the type of event from `Orion.EventTypes` |
| `Message` | `System.String` | Descriptive message or details |
| `Acknowledged` | `System.Boolean` | Whether an administrator has acknowledged it |
| `EngineID` | `System.Int32` | The polling engine that generated it |
| `NetObjectValue` | `System.String` | Display name or value of the network object |
| `TimeStamp` | `System.Byte[]` | Internal, for database concurrency control. Not a date |
| `NetObjectID` | `System.Int32` | Inherited. The object's id, without a prefix |
| `NetObjectType` | `System.String` | Inherited. The prefix, in its own column |
| `NetworkNode` | `System.Int32` | Inherited. The related node id |

`EventTime` being local and `TimeStamp` being a byte array are both traps. Use `GetDate()`
arithmetic against `EventTime`, not `GetUtcDate()`, and never try to sort by `TimeStamp`
expecting chronology. See [../swql/date-and-time.md](../swql/date-and-time.md).

### Navigations

`Nodes` to `Orion.Nodes`, `Engine` to `Orion.Engines`, and `EventTypeProperties` to
`Orion.EventTypes`. That last one is how you turn `EventType` into a readable name without
a join: `Orion.EventTypes` carries `EventType`, `Name`, `Notify`, `Record`, `NotifyMessage`
and `NotifySubject`.

### Verbs

One: `Acknowledge(eventIDs: array of number)` returns `boolean`, requiring the
`clearEvents` right. It "Marks the specified event as acknowledged, typically used to clear
events from active monitoring views". The parameter is an **array**, so acknowledge in
batches rather than one call per event.

### Example

The last day of events with their type names resolved:

```sql
SELECT TOP 100
    e.EventID,
    e.EventTime,
    e.EventTypeProperties.Name AS EventTypeName,
    e.NetObjectType,
    e.NetObjectID,
    e.NetObjectValue,
    e.Message,
    e.Acknowledged
FROM Orion.Events e
WHERE e.EventTime > AddDay(-1, GetDate())
ORDER BY e.EventTime DESC
```

Always time-bound a query against this entity. It is one of the largest tables on the
system. See [../swql/performance.md](../swql/performance.md).

---

## Orion.AuditingEvents

**Purpose.** Who changed what, and when. This is the audit trail, and it is a different
entity from `Orion.Events` with a different shape and a different time base.

**Key.** `AuditEventID` (`System.Int32`).

**Inheritance.** `System.Entity` -> `Orion.LogEntity` -> `Orion.AuditingEvents`.

**Size.** 10 declared properties, 1 source relationship, 2 target relationships, no verbs.

### Properties

| Property | Type | Why you want it |
| --- | --- | --- |
| `AuditEventID` | `System.Int32` | The key |
| `TimeLoggedUtc` | `System.DateTime` | When. **UTC**, unlike `Orion.Events.EventTime` |
| `AccountID` | `System.String` | Who |
| `ActionTypeID` | `System.Int32` | What kind of change |
| `AuditEventMessage` | `System.String` | The rendered description |
| `NetObjectID` | `System.Int32` | The affected object's id |
| `NetObjectType` | `System.String` | The affected object's type prefix |
| `NetworkNode` | `System.Int32` | The related node |
| `DetailsUrl`, `DisplayName` | `System.String` | Presentation |

The UTC suffix on `TimeLoggedUtc` is the whole warning. Filtering it with
`AddDay(-7, GetUtcDate())` produces a value stamped with the SQL Server's local offset,
which silently shifts your window. Write `ToUtc(AddDay(-7, GetDate()))` instead. See
[../swql/date-and-time.md](../swql/date-and-time.md).

### Navigations

`AuditingActionType` leads to `Orion.AuditingActionTypes`, which carries `ActionTypeID`,
`ActionType`, `ActionTypeDisplayName` and `OperationStatus`, so you get a readable action
name without a join. `Account` leads to `Orion.Accounts`. `Arguments` leads to
`Orion.AuditingArguments`, the structured detail behind the message.

### Example

The last week of audited changes, with the action name resolved:

```sql
SELECT TOP 100
    a.AuditEventID,
    a.TimeLoggedUtc,
    a.AccountID,
    a.AuditingActionType.ActionTypeDisplayName AS Action,
    a.NetObjectType,
    a.NetObjectID,
    a.AuditEventMessage
FROM Orion.AuditingEvents a
WHERE a.TimeLoggedUtc > ToUtc(AddDay(-7, GetDate()))
ORDER BY a.TimeLoggedUtc DESC
```

---

## The alerting entities

There are six, and picking the wrong one is the usual reason an alert query returns
nothing. All six exist in 2026.2, verified.

| Entity | What it holds | Key-ish identifier |
| --- | --- | --- |
| `Orion.AlertConfigurations` | The **definition**: name, trigger, reset, severity, enabled | `AlertID` (`System.Int32`) |
| `Orion.AlertObjects` | The **join table**: one row per (definition, object) pair that has ever triggered | `AlertObjectID` (`System.Int32`) |
| `Orion.AlertActive` | The **currently firing** alerts | `AlertActiveID` (`System.Int64`) |
| `Orion.AlertHistory` | Everything that has happened to an alert: triggered, reset, acknowledged | `AlertHistoryID` (`System.Int32`) |
| `Orion.AlertDefinitions` | The **older** advanced-alert model, keyed by `AlertDefID` (`System.Guid`) | `AlertDefID` |
| `Orion.AlertStatus` | A flat view keyed by `AlertDefID`, `ActiveObject` and `AlertObjectID` | composite |

The current model is `Orion.AlertConfigurations` plus `Orion.AlertObjects` plus
`Orion.AlertActive`. `Orion.AlertDefinitions` uses a `System.Guid` key and a different
vocabulary (`TriggerQuery`, `ResetQuery`, `SuppressionQuery`, `DOW`, `TriggerSustained`),
and `Orion.AlertConfigurations` carries verbs named `MigrateAllAdvancedAlerts`,
`MigrateAdvancedAlert` and `MigrateAdvancedAlertFromXML`, which is the schema telling you
which direction the migration runs. Write new work against the configuration entities.

### Orion.AlertConfigurations

20 properties. The ones that matter: `AlertID`, `Name`, `Description`, `Enabled`
(`System.Boolean`), `Severity` (`System.Int32`), `ObjectType` (`System.String`, the entity
the alert targets), `Frequency` (`System.Int64`), `Trigger`, `Reset` and `Suppress`
(`System.String`, the stored condition definitions), `AlertMessage`, `SuppressMessage`,
`NotifyEnabled`, `NotificationSettings`, `Category`, `Canned` (`System.Boolean`, whether it
shipped with the product), `CreatedBy`, `LastEdit` and `AlertRefID` (`System.Guid`).

Access control: `read,invoke` for `everyone`, `read,update,invoke` for `allowDisableAlert`,
and full `create,read,update,delete,invoke` for `manageAlerts`. The `allowDisableAlert`
right existing separately is why an operator can silence an alert without being able to
rewrite it.

Verbs: `Import(alertXml: string, stripSensitiveInformation: boolean, protectionPassword:
string)`, `Export(alertId: number, stripSensitiveData: boolean, protectionPassword:
string)`, `GetComplexPropertiesByAlertID(alertId: number)`, and the three migration verbs.
`Import` and `Export` both require `admin` or `manageAlerts` and are the supported way to
move an alert between servers.

### Orion.AlertObjects

18 properties, and this is the entity that answers "what triggered". `AlertObjectID`,
`AlertID`, `EntityUri`, `EntityType`, `EntityCaption`, `EntityDetailsUrl`,
`EntityNetObjectId`, `RealEntityUri`, `RealEntityType`, `RelatedNodeUri`, `RelatedNodeId`,
`RelatedNodeCaption`, `RelatedNodeDetailsUrl`, `TriggeredCount`, `LastTriggeredDateTime`,
`Context`, `AlertNote` and `IsActiveAlert`.

Two things to know. The `RelatedNode...` set means you usually do not need to join to
`Orion.Nodes` at all. And rows here **do not disappear when an alert resets**, which is why
counting rows in `Orion.AlertObjects` gives a much larger number than counting active
alerts. `IsActiveAlert` is the filter, or join to `Orion.AlertActive`.

Navigations: `AlertConfigurations` to `Orion.AlertConfigurations`, `AlertHistory` to
`Orion.AlertHistory`, `ManagedEntity` to `System.ManagedEntity` (the polymorphic route to
whatever triggered), `AlertActive` to `Orion.AlertActive`, and `Node` to `Orion.Nodes`.

### Orion.AlertActive

11 properties: `AlertActiveID`, `AlertObjectID`, `TriggeredDateTime`, `TriggeredMessage`,
`Acknowledged`, `AcknowledgedBy`, `AcknowledgedDateTime`, `AcknowledgedNote`, `Status`
(`System.Byte`), `NumberOfNotes` and `LastExecutedEscalationLevel`.

It carries nothing about *what* triggered, which is the point: that lives in
`Orion.AlertObjects`, joined on `AlertObjectID`.

Four verbs, all requiring `clearEvents` and all taking an **array** as the first argument:

| Verb | Parameters, in order |
| --- | --- |
| `Acknowledge` | `alertObjectIds: array of number`, `notes: string` |
| `Unacknowledge` | `alertObjectIds: array of number` |
| `ClearAlert` | `alertObjectIds: array of number` |
| `AppendNote` | `alertObjectIds: array of number`, `note: string` |

The parameter is named `alertObjectIds`, not `alertActiveIds`, so pass `AlertObjectID`
values even though you invoke on `Orion.AlertActive`. `ClearAlert` is documented as "Delete
active alert from database. Manual alert reset".

### Orion.AlertHistory

8 properties: `AlertHistoryID`, `AlertObjectID`, `AlertActiveID`, `EventType`
(`System.Int32`), `Message`, `TimeStamp` (`System.DateTime`, a real date here unlike on
`Orion.Events`), `AccountID` and `ActionID`. Described as "Information about all actions
done for active alerts such as Alert reset, Alert triggered and so on".

### Orion.AlertStatus

18 properties keyed by `AlertDefID` plus `ActiveObject`, including `ObjectType`, `State`,
`WorkingState`, `ObjectName`, `AlertMessage`, `TriggerTimeStamp`, `TriggerCount`,
`ResetTimeStamp`, `Acknowledged`, `AcknowledgedBy`, `AlertNotes` and `AlertObjectID`. It
declares three verbs, `Acknowledge`, `AcknowledgeAlert` and `AddNote`, and the published
contract records **no parameters and no return type** for any of them.
Their signatures are **unverified**, so confirm them on your own server with
`Metadata.VerbArgument` before calling them.

### Example

Every currently active alert, with its definition and what it fired on:

```sql
SELECT TOP 100
    ac.Name AS AlertName,
    ac.Severity,
    ao.EntityCaption,
    ao.EntityType,
    ao.RelatedNodeCaption,
    aa.TriggeredDateTime,
    aa.Acknowledged,
    aa.AcknowledgedBy,
    aa.TriggeredMessage
FROM Orion.AlertActive aa
INNER JOIN Orion.AlertObjects ao ON ao.AlertObjectID = aa.AlertObjectID
INNER JOIN Orion.AlertConfigurations ac ON ac.AlertID = ao.AlertID
ORDER BY aa.TriggeredDateTime DESC
```

---

## Custom property entities

**Purpose.** User-defined columns bolted onto a monitored object. They are the standard way
to record ownership, location, criticality, change window, or anything else the platform
does not model.

**The pattern.** Every entity that supports custom properties has a partner entity named
`<Entity>CustomProperties`, reachable through a `CustomProperties` navigation. They are
identifiable by inheritance rather than by name: 25 entities inherit from
`System.CustomPropertiesEntity` in 2026.2, among them `Orion.NodesCustomProperties`,
`Orion.NPM.InterfacesCustomProperties`, `Orion.VolumesCustomProperties`,
`Orion.APM.ApplicationCustomProperties`, `Orion.GroupCustomProperties`,
`Orion.VIM.VirtualMachinesCustomProperties` and `Orion.AlertConfigurationsCustomProperties`.
List them all with `python3 tools/schema_query.py children System.CustomPropertiesEntity`.

### Orion.NodesCustomProperties

**Inheritance.** `System.Entity` -> `System.ExtensionEntity` ->
`System.CustomPropertiesEntity` -> `Orion.NodesCustomProperties`.

**Access control.** `read` requires `everyone`; `read,update` requires `manageNodes`;
`read,update,invoke` requires `admin`. Creating or deleting a custom property definition is
an admin operation; setting a value on one node is not.

**Properties.** Exactly one is declared: `NodeID` (`System.Int32`), which ties a row to its
node. Every other column on this entity is created by an administrator on that specific
server, which is why the extracted schema cannot list them and why a query naming one cannot
be validated offline. `Orion.NodesCustomProperties` hosts off `Orion.Nodes` through the
`Node` target navigation.

With real property names substituted, node queries take this shape. It is shown as plain
text rather than as a checked SWQL block precisely because `City` and `Owner` are
installation-specific:

```text
SELECT TOP 100
    n.Caption,
    n.CustomProperties.City,
    n.CustomProperties.Owner
FROM Orion.Nodes n
ORDER BY n.Caption
```

**Verbs.** Five, all operating on the *definition* rather than on values:

| Verb | Parameters, in order |
| --- | --- |
| `CreateCustomProperty` | `PropertyName`, `Description`, `ValueType`, `Size`, `ValidRange`, `Parser`, `Header`, `Alignment`, `Format`, `Units`, `Usages`, `Mandatory`, `Default`, `SourceId`, `SourceName`, `DisplayName` |
| `CreateCustomPropertyWithValues` | the same, with `Value` inserted after `Units` |
| `ModifyCustomProperty` | `PropertyName`, `Description`, `Size`, `Values`, `Usages`, `Mandatory`, `Default`, `SourceId`, `SourceName`, `propertyDisplayName` |
| `DeleteCustomProperty` | `PropertyName` |
| `ValidateCustomProperty` | `PropertyName`, `Description`, `ValueType`, `Size`, `Value`, `Usages`, `propertyDisplayName`, returning a `CustomPropertyValidationResult` |

SolarWinds documents `ValueType` as one of `string`, `integer`, `datetime`, `single`,
`double`, `boolean`, and describes `ValidRange`, `Parser`, `Header`, `Alignment`, `Format`
and `Units` as unused, to be passed as null. Sixteen positional arguments with six dead
slots in the middle is exactly the situation where getting the order wrong is easy, so read
[../swis/invoke-verbs.md](../swis/invoke-verbs.md) first.

Setting a *value* is not a verb at all. It is a CRUD update against the custom properties
row, addressed by its `Uri`.

### Discovering what exists on a server

`Orion.CustomProperty` is the catalogue, and it is queryable offline-safe because its own
columns are fixed: `Table`, `Field`, `DataType`, `MaxLength`, `StorageMethod`,
`Description`, `TargetEntity`, `Mandatory`, `Default` and `DisplayName`.

```sql
SELECT
    cp.Table,
    cp.Field,
    cp.DataType,
    cp.MaxLength,
    cp.Mandatory,
    cp.Default,
    cp.Description
FROM Orion.CustomProperty cp
WHERE cp.Table = 'NodesCustomProperties'
ORDER BY cp.Field
```

`TargetEntity` holds the entity name if you would rather filter that way.
`Orion.CustomPropertyValues` (`Table`, `Field`, `Value`) holds the restricted value list for
properties created with `CreateCustomPropertyWithValues`, and SolarWinds' own documented
procedure for adding one allowed value is to read the existing list from there, append, and
call `ModifyCustomProperty` with the whole list. `Orion.CustomPropertyUsage` and
`Orion.CustomPropertySources` complete the family.

---

## Cirrus.Nodes

**Purpose.** Network Configuration Manager's own node record. NCM does not extend
`Orion.Nodes`; it keeps a parallel row, and the two are joined by id.

The schema is explicit about the access model: "Data about NCM nodes. For valid Orion user
with at least WebViewer NCM role. Updates possible only by users with manage node
permissions." A user with full Orion rights but no NCM role sees nothing here, and that is
the usual explanation for an NCM query returning zero rows.

**Key.** `NodeID`, and this is the trap: on `Cirrus.Nodes` it is a **`System.Guid`**, stated
in the schema as "Unique identifier and primary key of the NCM node". The Orion node id is
a separate property, `CoreNodeID` (`System.Int32`), documented as "Orion node ID".

**Inheritance.** `System.Entity` -> `Cirrus.Nodes`. Not a managed entity, so no
`UnManaged` and no inherited `Status` from `System.DashboardEntity`. It declares its own
`Status` as a `System.Byte`.

**Access control.** `read,invoke` requires `everyone`; `read,update,invoke` requires
`manageNodes`.

**Size.** 66 declared properties, 1 source relationship, no target relationships, 25 verbs.

### Properties worth knowing

Many of these are documented as mirrors of the Orion values, which the schema says outright,
for example `ReverseDNS` is "The Orion.Nodes DNS value".

| Property | Type | Why you want it |
| --- | --- | --- |
| `NodeID` | `System.Guid` | NCM's key |
| `CoreNodeID` | `System.Int32` | The `Orion.Nodes.NodeID`. Your join column |
| `EngineID` | `System.Int32` | Polling engine assignment |
| `NodeCaption` | `System.String` | Mirrors `Orion.Nodes.Caption` |
| `NodeGroup` | `System.String` | Folder name |
| `Status`, `StatusText` | `System.Byte`, `System.String` | Mirrors the Orion status |
| `AgentIP`, `AgentIPv6`, `ManagedProtocol` | mixed | Address used for polling |
| `ConfigTypes` | `System.String` | Which config types are collected |
| `LastInventory` | `System.DateTime` | When inventory last ran |
| `LoginStatus` | `System.String` | "Description about the last connection". The first thing to check when transfers fail |
| `ConnectionProfile` | `System.Int32` | Which stored profile is in use |
| `ExecProtocol`, `CommandProtocol`, `TransferProtocol` | `System.String` | How NCM talks to the device |
| `TelnetPort`, `SSHPort`, `SNMPPort` | `System.String` | Ports |
| `Username`, `Password`, `EnableLevel`, `EnablePassword` | `System.String` | CLI credentials, stored encrypted |
| `UseUserDeviceCredentials`, `UseKeybInteractiveAuth`, `AllowIntermediary` | `System.Boolean` | Authentication behaviour |
| `SNMPUsername`, `SNMPAuthType`, `SNMPAuthPass`, `SNMPEncryptType`, `SNMPEncryptPass`, `SNMPContext` | `System.String` | SNMPv3 |
| `EndOfSupport`, `EndOfSales`, `EndOfSoftware`, `EosType`, `EosVersion`, `EosMatchDate`, `EosLink`, `EosComments`, `ReplacementPartNumber` | mixed | End-of-life tracking |
| `NodeComments` | `System.String` | Free text |

`EosType` is one of the few enumerations the schema spells out: 0 not assigned, 1 user,
2 manual, 3 auto, 4 awaiting, 5 node ignored. Several properties are documented as "Not
used", including `AgentIPSort`, `UseHTTPS`, `LastRediscoveryTime`, `EnableOrionImport` and
`ResponseError`.

### Navigations

Only one: `Interfaces`, leading to `Cirrus.Interfaces`. **There is no navigation between
`Cirrus.Nodes` and `Orion.Nodes`.** Joining on `CoreNodeID` is not a stylistic choice, it is
the only route.

### Verbs

25, the widest verb surface of any entity on this page. The core lifecycle:

| Verb | Parameters, in order | Note |
| --- | --- | --- |
| `AddNodeToNCM` | `coreNodeId: number` | The recommended way to add one node |
| `AddNodes` | `coreNodeIds: array` | Batch version |
| `AddNode` | `node: NCMNode` | Documented as "Not recommended - use AddNodeToNCM instead" |
| `RemoveNode` | `nodeId: string` | Removes from NCM only, not from Orion |
| `RemoveNodes` | `ncmNodeIds: array` | Batch version |
| `GetNode` | `nodeId: string` | Fetches the full model |
| `UpdateNode` | `node: NCMNode` | Overwrites **every** property. Fetch with `GetNode`, modify, send back |

Connection profiles have their own five: `GetConnectionProfile`, `AddConnectionProfile`,
`UpdateConnectionProfile`, `DeleteConnectionProfile`, `GetAllConnectionProfiles`.
End-of-support has `AssignEOSEntry`, `DeleteEOSData`, `ChangeEOSType`,
`GetPageableEosDataTable` and `GetPageableEosRowCount`. `ValidateLogin`, `ParseMacros`,
`ExecuteConfigChangeReportAction`, `CheckAPLicence` and `DeleteOverLicenseNodes` round it
out.

Three verbs carry an explicit deprecation notice in their own summary:
`ChangeVulnerabilityStateForNodes`, `ChangeVulnerabilityStateForAllNodes` and
`DeleteAllVulnerabilityData` each say "Verb will be removed in a future version of the
product". Do not build on them.

The summaries also state the role each verb needs, which is worth reading before debugging a
permission error: most need "Orion manage node users with at least WebViewer NCM role", and
the EOS verbs need the Engineer NCM role.

### Example

NCM nodes joined to their Orion counterparts, which is the join every NCM report starts
with:

```sql
SELECT TOP 50
    c.NodeID AS NcmNodeID,
    c.CoreNodeID,
    c.NodeCaption,
    c.SysName,
    c.Vendor,
    c.MachineType,
    c.LastInventory,
    c.LoginStatus,
    n.IPAddress,
    n.Status
FROM Cirrus.Nodes c
INNER JOIN Orion.Nodes n ON n.NodeID = c.CoreNodeID
ORDER BY c.NodeCaption
```

See [../modules/ncm.md](../modules/ncm.md) for the rest of the NCM surface, including the
`NCM.*` namespace and configuration archives.

---

## Orion.VIM.VirtualMachines

**Purpose.** Virtual machines from Virtualization Manager. Summarised simply as "Virtual
Machine". NetObject prefix `VVM`.

**Key.** `VirtualMachineID` (`System.Int32`), which comes from the parent entity
`Orion.Virtualization.Instance`, not from `Orion.VIM.VirtualMachines` itself. `HostID` and
`NodeID` are the two id columns you join on.

**Inheritance.** `System.Entity` -> `System.DashboardEntity` ->
`System.ManagedEntity` -> `Orion.Virtualization.Instance` ->
`Orion.VIM.VirtualMachines`. That extra level matters: `VirtualMachineID`, `Name`,
`CpuLoad`, `NodeID`, `PlatformID`, `NetworkUsageRate`, `NetworkTransmitRate` and
`NetworkReceiveRate` are all declared on `Orion.Virtualization.Instance` and inherited here.
Looking only at the `Orion.VIM.VirtualMachines` page and concluding it has no `Name` is a
common mistake.

**Size.** 76 declared properties, 99 including inherited ones, 29 source relationships,
5 target relationships, 7 verbs.

### Properties worth knowing

| Property | Type | Where declared | Why you want it |
| --- | --- | --- | --- |
| `VirtualMachineID` | `System.Int32` | inherited | The key |
| `Name` | `System.String` | inherited | The VM name |
| `NodeID` | `System.Int32` | inherited | The Orion node, when the VM is also monitored as a node |
| `HostID` | `System.Int32` | declared | The hypervisor host |
| `PowerState` | `System.String` | declared | Powered on, off, suspended |
| `GuestState` | `System.String` | declared | What the guest OS reports |
| `Status` | `System.Int32` | inherited from `System.DashboardEntity` | The status integer |
| `NodeStatus` | `System.Int32` | declared | A second status column, distinct from `Status` |
| `ConfigStatus`, `OverallStatus` | `System.String` | declared | Hypervisor-reported strings, not status integers |
| `ProcessorCount`, `CPUShares`, `CpuUsageMHz`, `CpuReady`, `CpuCostop` | mixed | declared | CPU |
| `CpuLoad` | `System.Single` | inherited | CPU load percentage |
| `MemoryConfigured`, `MemUsage`, `MemUsageMB`, `MemoryShares`, `MemoryAllocationLimit` | mixed | declared | Memory |
| `BalloonMemload`, `BalloonMemloadPercent`, `SwappedMemoryUtilization`, `SwappedMemoryUtilizationPercent`, `ConsumedMemLoad` | `System.Single` | declared | Memory pressure indicators |
| `IOPSTotal`, `IOPSRead`, `IOPSWrite` | `System.Single` | declared | Storage IOPS |
| `LatencyTotal`, `LatencyRead`, `LatencyWrite` | `System.Single` | declared | Storage latency in ms |
| `ThroughputTotal`, `ThroughputRead`, `ThroughputWrite` | `System.Single` | declared | Storage throughput in kB/s |
| `NetworkUsageRate`, `NetworkTransmitRate`, `NetworkReceiveRate` | `System.Single` | inherited | Network rates |
| `TotalStorageSize`, `TotalStorageSizeUsed`, `VolumeSummaryCapacity`, `VolumeSummaryFreeSpace`, `VolumeSummaryFreeSpacePercent` | mixed | declared | Storage capacity |
| `VolumeSummaryCapacityDepletionDate` | `System.DateTime` | declared | Forecast exhaustion |
| `SnapshotStorageSize`, `SnapshotSummaryCount`, `OldestSnapshotDate`, `SnapshotDateModified` | mixed | declared | Snapshot sprawl, a common report |
| `GuestVmWareToolsVersion`, `GuestVmWareToolsStatus`, `GuestName`, `GuestFamily`, `GuestDnsName` | `System.String` | declared | Guest identity |
| `BootTime`, `OSUptime`, `RunTime`, `DateCreated`, `LastActivityDate` | mixed | declared | Lifecycle |
| `UUID`, `InstanceUuid`, `ManagedObjectID` | mixed | declared | Hypervisor identifiers |
| `IsLicensed` | `System.Boolean` | declared | Whether Virtualization Manager is licensing it |
| `HeartBeat` | `System.Single` | declared | VM heartbeat |
| `DynamicMemoryEnabled`, `MinimumMemory`, `StartupMemory`, `MemoryBuffer` | mixed | declared | Hyper-V dynamic memory |

Note that `Status`, `NodeStatus`, `ConfigStatus` and `OverallStatus` are four different
things and only `Status` resolves against `Orion.StatusInfo`. `ConfigStatus` and
`OverallStatus` are `System.String`.

### Navigations worth knowing

| Navigation | Leads to | Note |
| --- | --- | --- |
| `Host` | `Orion.VIM.Hosts` | Target. `Host.HostName` is the hypervisor |
| `Node` | `Orion.Nodes` | Target. Present only when the VM is also a monitored node |
| `RelyNode`, `RelyHost` | `Orion.Nodes`, `Orion.VIM.Hosts` | Source, reliance edges |
| `StatusInfo` | `Orion.StatusInfo` | Source. One of the ten entities with this navigation |
| `CustomProperties` | `Orion.VIM.VirtualMachinesCustomProperties` | Source, hosting |
| `VirtualDisks`, `VirtualVolumes`, `VirtualMediaDevices` | `Orion.VIM.VirtualDisks`, `Orion.VIM.VirtualMachineVolumes`, `Orion.VIM.VirtualMachineMediaDevices` | Virtual hardware |
| `IPAddresses`, `MACAddresses` | `Orion.VIM.VirtualMachineIPAddresses`, `Orion.VIM.VirtualMachineMACAddresses` | Addressing |
| `DataStores`, `RelyDatastores`, `Luns` | `Orion.VIM.Datastores`, `Orion.VIM.Luns` | Storage. Note `Orion.VIM.Luns`, not `LUNs` |
| `VMStatistics` | `Orion.VIM.VMStatistics` | Historical |
| `ResourcePool` | `Orion.VIM.ResourcePools` | |
| `Tags` | `Orion.VIM.Tags` | |
| `TriggeredAlarmStates` | `Orion.VIM.TriggeredAlarmState` | Hypervisor-side alarms |

`Orion.VIM.LUNs` does not exist in 2026.2. The current name is `Orion.VIM.Luns`, and the
capitalisation change is exactly the kind of thing that fails on a live server while looking
correct on the page. See [netobject-types.md](netobject-types.md).

### Verbs

Seven, and they are real management actions against the hypervisor, not polling controls:

| Verb | Parameters, in order |
| --- | --- |
| `PerformBasicAction` | `virtualMachineId: number`, `actionType` |
| `TakeSnapshot` | `virtualMachineId: number`, `snapshotName` (optional) |
| `DeleteSnapshot` | `virtualMachineId: number`, `snapshotId: number`, `deleteAllChildren: boolean` |
| `ChangeSettings` | `virtualMachineId: number`, `processorCount: number`, `ramInMB: number`, `restartRequired: boolean` |
| `Migrate` | `virtualMachineId: number`, `destinationHostId: number`, `restartRequired: boolean`, `storageDestination` (optional) |
| `Relocate` | `virtualMachineId: number`, `destinationDataStoreId: number` |
| `GetManagementActionBatchResult` | `batchGuid` |

`PerformBasicAction` covers "PowerOff, PowerOn, Pause, Resume, Suspend, Reboot, DeleteVM,
and UnregisterVM" according to its own summary, so a single verb can power off or delete a
virtual machine. `ChangeSettings` "restarts the VM if it is powered on". Treat this entity's
verb surface with more care than the rest of this page.

All seven take a bare `virtualMachineId` number, not a `VVM:` prefixed string.

### Example

The busiest powered-on VMs, with host and resolved status name:

```sql
SELECT TOP 50
    vm.VirtualMachineID,
    vm.Name AS VmName,
    vm.PowerState,
    vm.GuestState,
    vm.ProcessorCount,
    vm.MemoryConfigured,
    vm.CpuLoad,
    vm.MemUsage,
    vm.StatusInfo.StatusName,
    vm.Host.HostName AS HostName
FROM Orion.VIM.VirtualMachines vm
WHERE vm.PowerState = 'PoweredOn'
ORDER BY vm.CpuLoad DESC
```

`'PoweredOn'` is a data value, not a schema fact. Confirm the spelling your hypervisor
reports with `SELECT DISTINCT PowerState FROM Orion.VIM.VirtualMachines` before relying on
it in a saved report.

---

## Where to go next

- [netobject-types.md](netobject-types.md) for the prefix each of these entities uses.
- [status-codes.md](status-codes.md) for what the status integers mean.
- [entity-model.md](entity-model.md) for inheritance, keys, URIs and rights.
- [relationships.md](relationships.md) for the three relationship kinds.
- [../swql/joins-and-navigation.md](../swql/joins-and-navigation.md) for what a navigation
  does to your row count.
- [../swis/invoke-verbs.md](../swis/invoke-verbs.md) before calling any verb on this page.
- [../reference/entity-index.md](../reference/entity-index.md) for all 2067 entities, and
  [../reference/verb-index.md](../reference/verb-index.md) for all 1021 verbs.
- [../modules/README.md](../modules/README.md) for the module-specific entities this page
  does not cover.

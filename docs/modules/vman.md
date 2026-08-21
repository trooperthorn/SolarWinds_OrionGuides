# VMAN: Virtualization Manager

Virtualization Manager is the module that lets the platform see inside a hypervisor. Without
it, an ESXi host is just a node that answers pings and a virtual machine is just another
server with an IP address. With it, the platform knows that those forty servers are guests on
six hosts in two clusters, that one of them has a snapshot from eleven months ago quietly
consuming 400 GB, and that the datastore they all share will be full in nine weeks.

It monitors more than VMware. The same entities carry Hyper-V, Nutanix and Proxmox VE data,
with a `PlatformID` column on the host and virtual machine rows saying which. The naming
throughout is VMware-flavoured for historical reasons, and reading `Orion.VIM.VCenters` or
`Orion.VIM.VMwareNodes` as "VMware only" is a mistake that gets made regularly.

Start with the name. **The module is Virtualization Manager and the namespace is
`Orion.VIM.`**, an engineering prefix that predates the product name. There is no
`Orion.VMAN.` namespace and no `Orion.Virtualization.Manager.` namespace, and deriving one
from the product name is the usual first failure.

## Namespace and size

There are 90 entities under `Orion.VIM.`, and three more namespaces carry virtualization data
alongside it.

| Group | Entities | What is in it |
|---|---|---|
| Monitored objects | 6 | `VCenters`, `DataCenters`, `Clusters`, `Hosts`, `VirtualMachines`, `Datastores` |
| Thresholds | 25 | Per-metric threshold entities for clusters, hosts, VMs and datastores |
| Statistics | 7 | Rolled-up history for VMs, hosts, clusters, datastores and virtual disks |
| Custom properties | 5 | One per monitored object type except vCenters |
| Capacity planning | 4 | Report definitions, results, and the host and VM profiles they simulate |
| Indications | 10 | Events the module raises internally, such as `Orion.VIM.HyperVDiscovered` |
| Supporting entities | 33 | LUNs, NAS, snapshots, virtual disks, disk files, resource pools, alarms, tags, discovery, polling tasks, chargeback |

Beyond `Orion.VIM.`:

- **`Orion.Virtualization.`** (3 entities) is the shared base layer.
  `Orion.Virtualization.Instance` is the parent of `Orion.VIM.VirtualMachines` **and** of the
  cloud instance entities, which is a useful fact in its own right; see
  [one query across virtual and cloud instances](#one-query-across-virtual-and-cloud-instances).
- **`Cortex.Orion.Virtualization.`** (18 entities) carries the newer telemetry, most visibly
  vSAN: `Cortex.Orion.Virtualization.VSan`, `VSanDiskGroup`, `VSanResyncInfo`,
  `VSanHealthGroup`, plus host and cluster storage metric entities.
  `Orion.VIM.Hosts` and `Orion.VIM.Clusters` navigate into it.
- **`Orion.Nutanix.`** (2 entities) holds Nutanix discovery metadata, reachable from
  `Orion.VIM.Clusters.NutanixDiscoveryMetadata`.

Check any of this yourself:

```bash
python3 tools/schema_query.py find Orion.VIM --properties
python3 tools/schema_query.py show Orion.VIM.VirtualMachines
python3 tools/schema_query.py children Orion.Virtualization.Instance
python3 tools/schema_query.py verbs --entity Orion.VIM.VirtualMachines
```

### `Orion.VIM.LUNs` was renamed to `Orion.VIM.Luns`

Older references, including the community SWQL workbook, spell the LUN entity
`Orion.VIM.LUNs` with three capitals. In the 2026.2 schema the entity is
`Orion.VIM.Luns`, capital L and lowercase `uns`. This repository records the rename in
[`data/reference/reconciliation.json`](../../data/reference/reconciliation.json), and
[../reference/netobject-types.md](../reference/netobject-types.md) marks the workbook row as
superseded.

The capitalisation is worth dwelling on because the platform is inconsistent about it and
there is no rule to fall back on. `Orion.VIM.Luns` is mixed case, but the *SRM* LUN entity
`Orion.SRM.LUNs` is capitalised, and inside `Orion.VIM.Luns` the key is `LunID` while inside
`Orion.SRM.LUNs` the key is `LUNID`. All four spellings are correct in their own place. Look
each one up rather than deriving it:

```bash
python3 tools/schema_query.py find Lun
```

## The hierarchy

vSphere's own object model maps onto the schema almost exactly, and the id columns make each
level joinable in both directions.

```
Orion.VIM.VCenters          the management server (VCenterID, NodeID)
  └── Orion.VIM.DataCenters       (DataCenterID, VCenterID)
        └── Orion.VIM.Clusters    (ClusterID, DataCenterID)
              └── Orion.VIM.Hosts (HostID, ClusterID, DataCenterID, NodeID)
                    └── Orion.VIM.VirtualMachines   (VirtualMachineID, HostID, NodeID,
                                                     ResourcePoolID)

Orion.VIM.Datastores        attached to hosts, clusters and VMs rather than owned by one
  ├── Orion.VIM.Luns        block backing for a VMFS datastore  (LunID, DataStoreID)
  ├── Orion.VIM.Nas         NFS backing for an NFS datastore    (NasID, DataStoreID)
  └── Orion.VIM.DiskFiles   the files on it, including orphans  (DiskFileID, DataStoreID)

Orion.VIM.ResourcePools     a CPU and memory container inside a cluster or host
Orion.VIM.VirtualDisks      one VMDK, joining a VM to a datastore and a LUN
Orion.VIM.Snapshots         one snapshot of one VM
```

Hosts carry both `ClusterID` and `DataCenterID`, so a standalone host outside any cluster
still has a datacenter. That is why `Orion.VIM.Hosts` has both a `Cluster` and a `DataCenter`
navigation rather than reaching the datacenter only through the cluster: joining hosts to
datacenters via clusters silently drops every standalone host.

Hosts also carry `SecondaryClusterID` and a matching `RelySecondaryCluster` dependency edge,
which is how a host that participates in a second cluster grouping is represented.

Walking down is navigation properties; walking up is the same. From the VM side the entire
chain is one dotted expression:

```sql
SELECT TOP 200
    vm.Host.Cluster.DataCenter.VCenter.Name AS VCenterName,
    vm.Host.Cluster.DataCenter.Name AS DataCenterName,
    vm.Host.Cluster.Name AS ClusterName,
    vm.Host.HostName AS HostName,
    vm.Name AS VMName,
    vm.PowerState,
    vm.ProcessorCount,
    vm.MemoryConfigured,
    vm.CpuLoad,
    vm.MemUsage
FROM Orion.VIM.VirtualMachines vm
WHERE vm.UnManaged = FALSE
ORDER BY vm.Host.HostName, vm.Name
```

Each hop in that chain is an inner join. A VM on a standalone host has no `ClusterID`, so it
vanishes from this result entirely rather than appearing with nulls. When you need every VM,
select `vm.Host.DataCenter.Name` instead of routing through the cluster, or write explicit
`LEFT JOIN`s. [../swql/joins-and-navigation.md](../swql/joins-and-navigation.md) covers why.

## A virtual host is also an Orion node

`Orion.VIM.Hosts.NodeID` is the single most useful column in this module, because it is the
bridge between the virtualization world and everything else the platform does.

When Virtualization Manager polls an ESXi host, that host also exists as an ordinary row in
`Orion.Nodes`. The node row is what carries the platform's up/down status, its response time,
its alerts, its dependencies, its custom properties and its group memberships. The
`Orion.VIM.Hosts` row is what carries `VmCount`, `CpuLoad`, `MemUsage`, `ConnectionState` and
the rest of the hypervisor detail. Neither is complete without the other, and `NodeID` joins
them.

Three entities carry a `NodeID` into the platform core:

| Entity | Column | What it means |
|---|---|---|
| `Orion.VIM.Hosts` | `NodeID` | The hypervisor host as a monitored node. Navigation: `Node`. |
| `Orion.VIM.VCenters` | `NodeID` | The vCenter server as a monitored node. Navigation: `Node`. |
| `Orion.VIM.VirtualMachines` | `NodeID` | Populated only when the **guest** is separately monitored as a node in its own right. Navigation: `Node`. |

The third is the one that surprises people. A virtual machine always has a
`VirtualMachineID`; it has a `NodeID` only if someone also added the guest operating system
as a node. That means `INNER JOIN Orion.Nodes n ON n.NodeID = vm.NodeID` quietly reports only
the subset of VMs that are also monitored from the inside, which is usually far fewer than
the VM count. If you meant "all VMs", do not join to `Orion.Nodes` at all.

There is a fourth, older view of the same idea. `Orion.VIM.VMwareNodes` has 17 properties and
maps `NodeID` to `HostID` and `VCenterID` in one row, with `ConnectionState`,
`ManagedStatus`, `ManagedStatusMessage` and `VCenterHostStatus`. It has no navigation
properties at all, so it is a lookup table rather than a place to start a query.

Because a host is a node, everything the platform does to nodes works on hypervisors: alerts,
dependencies, groups, hardware health, and the `Orion.Nodes.Unmanage` verb. That last point
matters, because none of the `Orion.VIM.*` entities publishes an unmanage verb of its own.

## Virtual machines

`Orion.VIM.VirtualMachines` is the widest entity in the module: 76 declared properties on top
of eight inherited from `Orion.Virtualization.Instance` and the usual `System.ManagedEntity`
set. It is also the only VIM entity with meaningful verbs.

Its inheritance chain is worth knowing, because several of the columns people reach for most
are inherited rather than declared: `VirtualMachineID` (the key), `Name`, `CpuLoad`,
`PlatformID`, `NodeID`, `NetworkUsageRate`, `NetworkTransmitRate` and `NetworkReceiveRate`
all come from `Orion.Virtualization.Instance`. `show` will not list them; `props` will, and
marks where each came from.

```bash
python3 tools/schema_query.py props Orion.VIM.VirtualMachines --grep Network
```

Identity and configuration: `VirtualMachineID`, `Name`, `UUID`, `InstanceUuid`,
`ManagedObjectID`, `HostID`, `ResourcePoolID`, `NodeID`, `PlatformID`, `VMConfigFile`,
`LogDirectory`, `RelativePath`, `DatastoreIdentifier`, `ProcessorCount`, `MemoryConfigured`,
`MemoryShares`, `CPUShares`, `MemoryAllocationLimit`, `MinimumMemory`, `StartupMemory`,
`MemoryBuffer`, `DynamicMemoryEnabled`, `NicCount`, `VDisksCount`, `DateCreated`.

Guest state: `PowerState`, `GuestState`, `IPAddress`, `GuestName`, `GuestFamily`,
`GuestDnsName`, `GuestVmWareToolsVersion`, `GuestVmWareToolsStatus`, `BootTime`, `OSUptime`,
`RunTime`, `HeartBeat`, `LastActivityDate`, `ConfigStatus`, `OverallStatus`, `NodeStatus`,
`IsLicensed`.

Performance: `CpuLoad`, `CpuUsageMHz`, `CpuReady`, `CpuCostop`, `MemUsage`, `MemUsageMB`,
`ConsumedMemLoad`, `ConsumedPercentMemLoad`, `BalloonMemload`, `BalloonMemloadPercent`,
`SwappedMemoryUtilization`, `SwappedMemoryUtilizationPercent`, `IOPSTotal`, `IOPSRead`,
`IOPSWrite`, `LatencyTotal`, `LatencyRead`, `LatencyWrite`, `ThroughputTotal`,
`ThroughputRead`, `ThroughputWrite`, `NetworkUsageRate`, `NetworkTransmitRate`,
`NetworkReceiveRate`.

`CpuReady` and `CpuCostop` are the two that diagnose a symptom nothing else explains: a VM
that is slow while its own CPU usage looks low, because it is waiting for a physical core.
`BalloonMemloadPercent` and `SwappedMemoryUtilizationPercent` are the memory equivalent.

Storage: `TotalStorageSize`, `TotalStorageSizeUsed`, `VolumeSummaryCapacity`,
`VolumeSummaryFreeSpace`, `VolumeSummaryFreeSpacePercent`,
`VolumeSummaryCapacityDepletionDate`, `SnapshotStorageSize`, `SnapshotSummaryCount`,
`OldestSnapshotDate`, `SnapshotDateModified`, `VirtualDiskDateModified`.

`TotalStorageSize` is what the VM occupies on datastores. `VolumeSummary*` is the aggregate
of what the guest filesystems report from inside. The two disagree constantly on a
thin-provisioned VM, and both are correct answers to different questions.

Navigations worth knowing: `Host`, `Node`, `Platform`, `ResourcePool`, `DataStores`,
`VirtualDisks`, `VirtualVolumes`, `VirtualMediaDevices`, `IPAddresses`, `MACAddresses`,
`Luns`, `NasShares`, `SRMLUNs` to `Orion.SRM.LUNs`, `Tags`, `TriggeredAlarmStates`,
`VMStatistics`, `CustomProperties`, `Thresholds`.

## Hosts, clusters, datacenters and vCenters

`Orion.VIM.Hosts` (62 properties) is the hypervisor. Beyond the identity and bridge columns
already covered: `HostName`, `DNSHostName`, `IPAddress`, `Model`, `Vendor`, `ProcessorType`,
`BiosSerial`, `BuildNumber`, `VMwareProductName`, `VMwareProductVersion`, `CpuCoreCount`,
`CpuPkgCount`, `CpuMhz`, `MemorySize`, `NicCount`, `HbaCount`, `HbaFcCount`, `HbaScsiCount`,
`HbaIscsiCount`, `VsanNodeUuid`, `CertificateThumbprint`.

Its live state: `ConnectionState`, `ConfigStatus`, `OverallStatus`, `NodeStatus`,
`HostStatus`, `InMaintenanceMode`, `StatusMessage`, `BootTime`, `RunTime`, `VmCount`,
`VmRunningCount`, `CpuLoad`, `CpuUsageMHz`, `MemUsage`, `MemUsageMB`, `NetworkUtilization`,
`NetworkUsageRate`, `NetworkTransmitRate`, `NetworkReceiveRate`, `NetworkCapacityKbps`,
`TotalLatency`, `PollingMethod`, `PollingSource`, `PollingJobID`, `CredentialID`.

`VmCount` and `VmRunningCount` differ by the number of powered-off VMs on that host, and
`InMaintenanceMode` explains an otherwise alarming drop in both. `Orion.VIM.Hosts` declares
`read` and `invoke` for `everyone` and `update` for `admin`, so a read-only account can query
it but not modify it.

`Orion.VIM.Clusters` (41 properties) is the resource-pooling and availability layer:
`ClusterID`, `DataCenterID`, `Name`, `TotalCpu`, `TotalMemory`, `CpuCoreCount`,
`CpuThreadCount`, `EffectiveCpu`, `EffectiveMemory`, `CPULoad`, `CPUUsageMHz`, `MemoryUsage`,
`MemoryUsageMB`, `DatastoreUsedSpace`. Its HA and DRS posture is `HaStatus`,
`HaAdmissionControlStatus`, `HaFailoverLevel`, `DrsStatus`, `DrsBehaviour`,
`DrsVmotionRate`. Its vSAN state is `VsanEnabled` and `VsanUuid`.

The five capacity planning columns on a cluster are the ones to reach for in a budget
conversation, because they are forecasts rather than snapshots: `VmCapacityCount` (how many
more VMs the cluster can take), `VmCapacityConstraint` (which resource runs out first),
`CpuUtilizationDepletionDate`, `MemoryUtilizationDepletionDate` and
`DiskUtilizationDepletionDate`.

`Orion.VIM.DataCenters` (14 properties) is deliberately thin: `DataCenterID`, `VCenterID`,
`ManagedObjectID`, `Name`, `ConfigStatus`, `OverallStatus`, `ManagedStatus`,
`TriggeredAlarmDescription`, `PollingSource`. It exists to group clusters, not to carry
metrics, so there is nothing to aggregate on it directly.

`Orion.VIM.VCenters` (26 properties) is the management server: `VCenterID`, `NodeID`, `Name`,
`IPAddress`, `VMwareProductName`, `VMwareProductVersion`, `Model`, `Vendor`, `BuildNumber`,
`BiosSerial`, `ConnectionState`, `HostStatus`, `ManagedStatus`, `ManagedStatusMessage`,
`StatusMessage`, `CredentialID`, `PollingJobID`, `ServiceURIID`, `CertificateThumbprint`.
When VIM data stops arriving, this row and `Orion.VIM.PollingTasks` are where the reason is.

`Orion.VIM.PollingTasks` records one row per polling job: `VCenterID`, `HostID`, `NodeID`,
`PollingTaskTypeID`, `PollingInterval`, `JobTimeout`, `APITimeout`, `LastPoll`,
`LastPollStatus`, `LastPollStatusMessage`. **Unverified:** `PollingTaskTypeID` is an integer
whose enumeration is not in the extracted schema, so select `DISTINCT` on your own server
before filtering on a specific value.

## Datastores, LUNs, NAS and virtual disks

`Orion.VIM.Datastores` (34 properties) is where virtualization meets storage. It is not owned
by a single host: the `Hosts`, `Clusters` and `VirtualMachines` navigations are all to-many,
and `ClusterCount` counts how many clusters see it.

Capacity: `Capacity`, `FreeSpace`, `ReservedCapacity`, `ProvisionedSpace`,
`ProvisionedSpaceAllocation`, `SpaceUtilization`, `DepletionDate`, `CapacityFromAdvertised`.
`ProvisionedSpace` exceeding `Capacity` is thin provisioning working as designed;
`ProvisionedSpace` exceeding `Capacity` *while* `SpaceUtilization` is high is an incident
waiting to happen.

Performance: `IOPSTotal`, `IOPSRead`, `IOPSWrite`, `ThroughputTotal`, `ThroughputRead`,
`ThroughputWrite`, `LatencyTotal`, `LatencyRead`, `LatencyWrite`.

Identity and flags: `DataStoreID`, `DataStoreIdentifier`, `ManagedObjectID`, `Name`, `Type`,
`URL`, `Accessible`, `Local`, `Platform`, `ManagedStatus`.

`Orion.VIM.Luns` (7 properties) is the block device behind a VMFS datastore: `LunID`,
`LunIdentifier`, `CanonicalName`, `DataStoreID`, `ScsiLunID`, `Name`, `Type`. It is a plain
`System.Entity`, so it has no `Status`, no `UnManaged` and no statistics of its own. It is a
join table with names on it.

`Orion.VIM.LunStoragePaths` (5 properties) is the multipathing view: `LunID`, `HostID`,
`Initiator` (the host bus adapter), `Target` (the array port), `Active`. This is how you
answer "which hosts can see this LUN, and by how many paths", which is exactly the question
before a SAN maintenance window.

`Orion.VIM.Nas` (7 properties) is the NFS equivalent: `NasID`, `RemotePath`, `RemoteHost`,
`IPAddress`, `DnsHostName`, `DataStoreID`, `Name`.

`Orion.VIM.VirtualDisks` (30 properties) is one VMDK, and it is unusually convenient because
its whole ancestry is denormalised onto the row: `VirtualMachineName`, `HostName`,
`ClusterName`, `DatacenterName`, `VCenterName`, `DataStoreName`, `LunName` are all present as
strings alongside the ids. It also has `FileName`, `Label`, `Capacity`, `ThinProvisioned`,
`IsRawMapping`, `SerialNumber`, `ControllerBusNumber`, `DiskUnitNumber`, and its own IOPS,
latency and throughput columns.

`Orion.VIM.DiskFiles` (8 properties) is a file on a datastore: `DiskFileID`, `DataStoreID`,
`Name`, `Size`, `LastModifiedTime`, `Type`, `VirtualDiskID` and, most usefully,
`Orphaned`.

`Orion.VIM.VirtualMachineVolumes` (5 properties) is the guest's own view of its filesystems:
`VirtualMachineID`, `MountPoint`, `Capacity`, `FreeSpace`, `SpaceUtilization`. This is the
inside-the-guest number that `VolumeSummary*` on the VM aggregates.

### Crossing to Storage Resource Monitor

If SRM is licensed as well, the two modules are joined by explicit mapping tables rather than
by matching identifiers:

- `Orion.SRM.LunsToVIMLuns` joins `Orion.SRM.LUNs.LUNID` to `Orion.VIM.Luns.LunID`.
- `Orion.SRM.FileSharesToVIMNas` joins `Orion.SRM.FileShares.FileShareID` to
  `Orion.VIM.Nas.NasID`.

Both carry a `Manual` flag marking mappings an operator made by hand. There are also direct
navigations, `Orion.VIM.Datastores.LUNs` and `Orion.VIM.VirtualMachines.SRMLUNs` reaching
`Orion.SRM.LUNs`, and `Orion.VIM.Datastores.FileShares` reaching `Orion.SRM.FileShares`. See
[srm.md](srm.md) for the storage side.

## Snapshots

`Orion.VIM.Snapshots` exists and is small: `SnapshotID`, `VirtualMachineID`,
`SnapshotIdentifier`, `Name`, `Description`, `DateCreated`, `PowerState`. One row per
snapshot, so a VM with a chain of five has five rows.

It has exactly one relationship, `DiskFiles` to `Orion.VIM.DiskFiles`, and **no navigation to
the virtual machine**. To get the VM name you must join explicitly on `VirtualMachineID`;
there is no `s.VirtualMachine.Name` to write.

`Orion.VIM.VirtualMachines` carries a per-VM summary of the same data, which is cheaper when
you do not need the individual snapshots: `SnapshotSummaryCount`, `OldestSnapshotDate`,
`SnapshotStorageSize` and `SnapshotDateModified`. Use the summary for a fleet-wide report and
`Orion.VIM.Snapshots` when you need to name the snapshot somebody has to delete.

`Orion.VIM.Snapshots.PowerState` records the power state at the moment the snapshot was
taken, which is not the VM's current state. Selecting both without aliasing them apart
produces a confusing report.

## Statistics and capacity planning

Seven statistics entities hold the rolled-up history. All inherit `System.StatisticsEntity`
and therefore carry `ObservationTimestamp`, `ObservationFrequency` and `Weight`, but four of
them **also declare a `DateTime` column**, and that is the one to filter on for those four.

| Entity | Rows about | Time column to filter |
|---|---|---|
| `Orion.VIM.VMStatistics` | Virtual machines | `DateTime` |
| `Orion.VIM.HostStatistics` | Hosts | `DateTime` |
| `Orion.VIM.ClusterStatistics` | Clusters | `DateTime` |
| `Orion.VIM.DatastoreStatistics` | Datastores | `DateTime` |
| `Orion.VIM.HostStorageStatistics` | Host storage adapters | `ObservationTimestamp` |
| `Orion.VIM.ClusterStorageStatistics` | Cluster storage | `ObservationTimestamp` |
| `Orion.VIM.VirtualDisksStatistics` | Individual VMDKs | `ObservationTimestamp` |

Check before you assume:

```bash
python3 tools/schema_query.py props Orion.VIM.VMStatistics --grep Date
python3 tools/schema_query.py props Orion.VIM.HostStorageStatistics --grep Timestamp
```

`Orion.VIM.VMStatistics` is 80 properties of `Min`/`Max`/`Avg` triples plus
`Unavailability`. It inherits from `Orion.Virtualization.Statistics`, which is where
`VirtualMachineID`, `DateTime`, `Availability` and the `*CPULoad` and `*NetworkUsageRate`
triples come from. The triples worth knowing about are `AvgCpuReady`, `AvgCpuLatency`,
`AvgCpuSwapWait`, `AvgCpuMaxLimited`, `AvgCpuDemandMHz`, `AvgBalloonMemload`,
`AvgMemoryDemand` and `AvgMemoryGranted`, because they diagnose contention rather than
merely report usage.

`Orion.VIM.HostStorageStatistics` and `Orion.VIM.ClusterStorageStatistics` share a shape and
add two columns nothing else in the module has: `Congestions` and `OutstandingIO`. Sustained
`OutstandingIO` on a host is queueing at the adapter, which is a different problem from
latency at the datastore.

The four capacity planning entities are a self-contained simulator rather than a metric
store:

- `Orion.VIM.CapacityPlanning.ReportDefinitions` is the scenario: `EntityNetObjectID`,
  `EntityCaption`, `UtilizationPeriodInDays`, `Runway`, `FailoverReservation`, `Counters`,
  `SimulatedResourcesEnabled`, `SimulatedWorkloadsEnabled`, `ResourceAllocationType`,
  `ComputeTotalUtilizationTrend`.
- `Orion.VIM.CapacityPlanning.HostProfiles` and `Orion.VIM.CapacityPlanning.VMProfiles` are
  the hypothetical hardware and workload added to the scenario, each with an `InstanceCount`.
- `Orion.VIM.CapacityPlanning.ReportResults` is the outcome: `ReportStatus`, `ErrorMessage`,
  `ComputationDateStarted`, `ComputationDateFinished`, and `SimulationResult`, which is a
  JSON string. SWQL cannot parse it; select it and parse it in your client.

Note that `EntityNetObjectID` is typed `System.String` and holds a NetObject reference rather
than an integer, so joining it to `ClusterID` or `HostID` requires parsing rather than a
direct comparison. A cluster NetObject uses the `VMC` prefix and a host uses `VH`; the full
list is in [../reference/netobject-types.md](../reference/netobject-types.md).

## Alarms

Virtualization Manager surfaces the hypervisor's own alarms, which are separate from the
platform's `Orion.Alerts` machinery. Two entities, both restricted to `admin` for anything
other than reading:

`Orion.VIM.Alarm` is the definition as it exists in vCenter: `Id`, `ManagedObjectId`, `Name`,
`Description`, `SystemName`, `IsEnabled`, `IsDeleted`, `LastSeenTimestamp`,
`RelatedVCenter`.

`Orion.VIM.TriggeredAlarmState` is one firing: `Id`, `AlarmStatus`, `Timestamp`,
`Acknowledged`, `AcknowledgedByUser`, `AcknowledgedTime`, `IsResolved`, `LastSeenTimestamp`,
and seven `Related*` columns naming what the alarm is about: `RelatedAlarm`,
`RelatedVCenter`, `RelatedCluster`, `RelatedDataCenter`, `RelatedDatastore`, `RelatedHost`
and `RelatedVirtualMachine`. Six of the seven have a matching navigation, so
`t.VirtualMachine.Name` and `t.Host.HostName` work directly; `RelatedVCenter` has no
navigation of its own and needs an explicit join to `Orion.VIM.VCenters`.

`AlarmStatus` is its own scale and is **not** the platform `Status` scale. The schema
documents it inline: 0 unknown, 1 green (success), 2 yellow (warning), 3 red. Do not join
`Orion.StatusInfo` to it.

`Timestamp`, `AcknowledgedTime` and `LastSeenTimestamp` are all documented as UTC, unlike
most platform datetime columns which are local server time. Compare them against
`GetUtcDate()`, not `GetDate()`; see [../swql/date-and-time.md](../swql/date-and-time.md)
for why mixing the two produces off-by-hours results.

A monitored object also carries a `TriggeredAlarmDescription` string, denormalised onto
`Orion.VIM.VirtualMachines`, `Hosts`, `Clusters`, `DataCenters`, `Datastores` and `VCenters`,
for when you only need the summary line.

## Tags

`Orion.VIM.Tags` and `Orion.VIM.TagCategories` mirror vSphere tags into the schema, and
`Orion.VIM.Tags` navigates to all six monitored object types plus `Orion.CustomProperty`.
That last one is the interesting part: the module can copy tags into platform custom
properties so that alerts, groups and reports written against custom properties pick them up.

`Orion.VIM.Tags.SynchronizeToCustomProperties` is the verb that performs the copy. It takes
no arguments and requires the `admin` right, which the entity declares explicitly:
`read` for `everyone`, `invoke` for `admin`. `Orion.VIM.TagCustomPropertiesMapping` records
which tag category became which custom property, with `GroupingID`, `TargetTable`, `Name` and
`OriginalName`.

## Verbs

Virtualization Manager publishes 34 verbs. Twenty are the standard custom property
management set across five custom property entities. The other fourteen are six discovery
verbs, one tag verb, and seven on `Orion.VIM.VirtualMachines`.

### The virtual machine verbs change production state

Most of the platform's verbs change monitoring. These seven change the thing being monitored:
they power machines off, reboot them, move them between hosts, resize them and delete them.
Read this section before calling any of them.

| Verb | Positional parameters | Returns |
|---|---|---|
| `PerformBasicAction` | `virtualMachineId`, `actionType` | string |
| `TakeSnapshot` | `virtualMachineId`, `snapshotName` | string |
| `DeleteSnapshot` | `virtualMachineId`, `snapshotId`, `deleteAllChildren` (optional) | string |
| `ChangeSettings` | `virtualMachineId`, `processorCount`, `ramInMB`, `restartRequired` (optional) | string |
| `Migrate` | `virtualMachineId`, `destinationHostId`, `restartRequired` (optional), `storageDestination` (optional) | string |
| `Relocate` | `virtualMachineId`, `destinationDataStoreId` | string |
| `GetManagementActionBatchResult` | `batchGuid` | string |

Confirm each signature before use, because arguments travel positionally and names never go
on the wire:

```bash
python3 tools/schema_query.py verb Orion.VIM.VirtualMachines PerformBasicAction
python3 tools/schema_query.py verb Orion.VIM.VirtualMachines Migrate
```

**`PerformBasicAction`** takes a `virtualMachineId` and an `actionType` string. The schema
documents the accepted values as `PowerOff`, `PowerOn`, `Pause`, `Resume`, `Suspend`,
`Reboot`, `DeleteVM` and `UnregisterVM`. Two of those are destructive and irreversible from
the API: `DeleteVM` removes the virtual machine and its files, and `UnregisterVM` removes it
from inventory while leaving the files behind. There is no confirmation step and no dry run.
Anything scripted around this verb should require an explicit confirmation and should log the
`virtualMachineId` it acted on.

**`ChangeSettings`** is the one whose side effect is easy to miss. In the schema's own words
it "restarts the VM if it is powered on or starts it after the change if it was powered off
before". Changing CPU or RAM on a running production VM through this verb reboots it. On a
powered-off VM it powers it **on** unless you pass `restartRequired` as `false`, which means
the safe call on a stopped VM has four arguments, not three.

**`Migrate`** moves a VM to a different host and optionally to different storage.
`restartRequired` forces a power cycle rather than a live migration, so passing `true`
converts a vMotion into an outage. `storageDestination` is a string and is optional; the
schema does not record what form it takes, so **unverified**: confirm against your own server
before relying on it, for example by checking the argument type in `Metadata.VerbArgument`.

**`TakeSnapshot`** is described in its own summary as taking an optional `snapshotName`, but
the Swagger contract marks that parameter **required**. The two sources disagree. Pass a name
rather than testing which one is right on a production VM, and note that snapshots left
behind by automation are one of the most common causes of a datastore filling up.

**`GetManagementActionBatchResult`** takes a `batchGuid` and is how you find out what
happened, since the action verbs return promptly rather than waiting for the hypervisor.

`Orion.VIM.VirtualMachines` declares **no access control** in the published schema. That is
not a statement that no right is required, only that the rendered schema page did not carry
one. Test with a low-privilege account before assuming either way.

A worked call, with the confirmation this class of verb deserves:

```powershell
Import-Module SwisPowerShell
$swis = Connect-Swis -Hostname orion.example.com -Trusted

# Identify the target explicitly rather than trusting a name to be unique. TOP 2 is
# deliberate: it is enough to detect a duplicate without fetching the whole estate.
$targetName = 'lab-build-01'
$matches = @(Get-SwisData $swis @"
SELECT TOP 2 vm.VirtualMachineID, vm.Name, vm.PowerState, vm.Host.HostName AS HostName
FROM Orion.VIM.VirtualMachines vm
WHERE vm.Name = @name
"@ @{ name = $targetName })

if ($matches.Count -ne 1) {
    throw "Expected exactly one VM named '$targetName', found $($matches.Count)."
}
$vm = $matches[0]

Write-Host "About to power off $($vm.Name) (id $($vm.VirtualMachineID)) on $($vm.HostName)."
if ((Read-Host "Type the VM name to confirm") -ne $vm.Name) { throw "Not confirmed." }

# PerformBasicAction(virtualMachineId, actionType). Two positional arguments.
$batch = (Invoke-SwisVerb $swis Orion.VIM.VirtualMachines PerformBasicAction @(
    [int]$vm.VirtualMachineID,
    'PowerOff'
)).InnerText

# The action is asynchronous; this is how you find out whether it worked.
Invoke-SwisVerb $swis Orion.VIM.VirtualMachines GetManagementActionBatchResult @($batch)
```

### Discovery verbs

`Orion.VIM.Discovery` is a verb-only entity: zero properties, six verbs, and an access
control declaration requiring the `manageNodes` right for both `read` and `invoke`. It is the
only VIM entity that names `manageNodes`; every other VIM entity that restricts anything uses
`admin` or `everyone`. A read-only account cannot even list this entity, which is a rare
shape in the schema and worth knowing when a query fails with a permission error rather than
an empty result.

| Verb | Positional parameters |
|---|---|
| `ValidateCredentials` | `hypervisorId`, `ipAddress`, `credentialProperties` (array), `engineId` (optional) |
| `ValidateExistingCredentials` | `hypervisorId`, `ipAddress`, `credentialsId`, `engineId` (optional) |
| `CreateDiscoveryJob` | `entityType`, `credentialsId`, `ipAddress`, `hostName` (optional), `engineId` (optional) |
| `GetDiscoveryJobResult` | `discoveryJobId`, `engineId` (optional), `timeoutInSeconds` (optional) |
| `AddNode` | `entityType`, `credentialsId`, `discoveryJobId`, `ipAddress`, `hostName` (optional), `engineId` (optional), `caption` (optional), `timeoutInSeconds` (optional) |
| `CreateVimPluginConfiguration` | `context` (a `VimPluginConfigurationContext` object) |

The onboarding sequence is validate, create a discovery job, poll for its result, then add
the node with the job id.

**There are two different numbering schemes here and mixing them up is the trap.**
`CreateDiscoveryJob` and `AddNode` take an `entityType`; `ValidateCredentials` and
`ValidateExistingCredentials` take a `hypervisorId`. They are not the same list.

| `entityType` (`CreateDiscoveryJob`, `AddNode`) | `hypervisorId` (`ValidateCredentials`, `ValidateExistingCredentials`) |
|---|---|
| 1 VMware vCenter | 1 VMware vCenter **or** VMware ESXi host |
| 2 VMware ESXi host | 2 Hyper-V hosts |
| 3 Hyper-V hosts | 3 Nutanix Prism Elements **or** Nutanix Prism Central |
| 4 Nutanix Prism Elements | |
| 5 Nutanix Prism Central | |
| 6 Proxmox VE | |

Both lists come from the verbs' own documented summaries. Note also that only `AddNode`
documents value 6 for Proxmox VE; `CreateDiscoveryJob`'s summary stops at 5. **Unverified:**
whether `CreateDiscoveryJob` accepts 6 in practice. Check on your own version before
scripting Proxmox onboarding, and read the argument list from the server directly:

```sql
SELECT Position, Name, Type, IsOptional
FROM Metadata.VerbArgument
WHERE EntityName = 'Orion.VIM.Discovery' AND VerbName = 'CreateDiscoveryJob'
ORDER BY Position
```

`credentialProperties` on `ValidateCredentials` is an array of `Username`, `Password`,
`CredentialName` and `CredentialDescription` keys and values, which is the case where
`Invoke-SwisVerb` needs the leading-comma idiom described in
[../swis/invoke-verbs.md](../swis/invoke-verbs.md). Prefer `ValidateExistingCredentials`
with a `credentialsId` from `Orion.Credential` where you can, so a password never travels
through your script.

### Elsewhere

`Cortex.Orion.Virtualization.HypervisorEntity` and `Cortex.Orion.Virtualization.VSan` each
publish seven `Core.*` verbs, including `Core.PollNow`, `Core.InventoryNow`,
`Core.SetPolling`, `Core.AssignToEngine` and the real-time polling pair. **Unverified:** the
extracted schema records no parameters for any of them, so read the signature from
`Metadata.VerbArgument` on your own server before calling one. Both entities require the
`admin` right for `invoke`.

## Worked queries

Every query below has been validated against the 2026.2 schema with
`tools/validate_swql.py`.

### Virtual machines by host, with the whole chain

The chain query from earlier in this page, narrowed to one host. Note the filter is on
`vm.Host.HostName` rather than on `HostID`, so it reads the way the question was asked.

```sql
SELECT
    vm.Host.Cluster.Name AS ClusterName,
    vm.Host.HostName AS HostName,
    vm.Name AS VMName,
    vm.PowerState,
    vm.GuestFamily,
    vm.ProcessorCount,
    vm.MemoryConfigured,
    vm.CpuLoad,
    vm.MemUsage,
    vm.CpuReady
FROM Orion.VIM.VirtualMachines vm
WHERE vm.Host.HostName = @hostName
ORDER BY vm.CpuLoad DESC
```

For the fleet view, aggregate from the host side instead, which keeps one row per host and
avoids multiplying host columns across every VM:

```sql
SELECT
    h.Cluster.Name AS ClusterName,
    h.HostName,
    h.Node.Caption AS OrionNodeCaption,
    h.NodeID,
    h.CpuCoreCount,
    h.CpuMhz,
    h.MemorySize,
    h.VmCount,
    h.VmRunningCount,
    h.CpuLoad,
    h.MemUsage,
    h.ConnectionState,
    h.InMaintenanceMode
FROM Orion.VIM.Hosts h
WHERE h.UnManaged = FALSE
ORDER BY h.VmRunningCount DESC
```

`h.VmCount` is maintained by the module, so this does not need a join to
`Orion.VIM.VirtualMachines` at all. Counting VMs yourself and comparing the two is a
reasonable consistency check when polling looks suspect. Note that `h.Cluster.Name` is still
an inner join, so standalone hosts drop out of this list; swap it for `h.DataCenter.Name`
when you want every host.

### Datastore capacity and how long it has left

```sql
SELECT
    ds.Name AS DatastoreName,
    ds.Type,
    ds.Local,
    ds.Capacity,
    ds.FreeSpace,
    ds.ProvisionedSpace,
    ds.ProvisionedSpaceAllocation,
    ds.SpaceUtilization,
    ds.DepletionDate,
    DayDiff(GetDate(), ds.DepletionDate) AS DaysOfHeadroom
FROM Orion.VIM.Datastores ds
WHERE ds.UnManaged = FALSE
  AND ds.Accessible = TRUE
ORDER BY ds.SpaceUtilization DESC
```

`DayDiff(a, b)` counts days from `a` to `b`, so `GetDate()` first yields days remaining and a
negative result means the forecast date has already passed. `Accessible = FALSE` datastores
report stale capacity, which is why they are excluded here and why they deserve their own
alert.

### Snapshots older than two weeks

The question that recovers the most datastore space for the least effort. `Orion.VIM.Snapshots`
has no navigation to the virtual machine, so the join on `VirtualMachineID` is explicit.

```sql
SELECT
    vm.Name AS VMName,
    vm.Host.HostName AS HostName,
    s.Name AS SnapshotName,
    s.Description,
    s.PowerState AS SnapshotPowerState,
    s.DateCreated,
    DayDiff(s.DateCreated, GetDate()) AS AgeDays,
    vm.SnapshotStorageSize,
    vm.SnapshotSummaryCount
FROM Orion.VIM.Snapshots s
INNER JOIN Orion.VIM.VirtualMachines vm ON vm.VirtualMachineID = s.VirtualMachineID
WHERE s.DateCreated < AddDay(-14, GetDate())
ORDER BY s.DateCreated
```

`vm.SnapshotStorageSize` is the total across all of that VM's snapshots, not this one's, so a
VM with a five-deep chain repeats the same total on five rows. When you want per-VM totals,
query the summary columns on `Orion.VIM.VirtualMachines` and leave `Orion.VIM.Snapshots` out.

### Orphaned files on datastores

The schema's answer to "what is orphaned" is about **files**, not virtual machines.
`Orion.VIM.DiskFiles.Orphaned` is a `System.Boolean` and it is the only column in the module
with that name. **Unverified:** the schema documents the column but not the rule behind it.
The usual reading is that it marks datastore files no registered virtual machine references,
which is what accumulates after a VM is removed from inventory or a migration is interrupted.
Confirm against a file you already know the history of before acting on the list.

```sql
SELECT
    ds.Name AS DatastoreName,
    df.Name AS FileName,
    df.Type AS FileType,
    df.Size,
    df.LastModifiedTime,
    df.Orphaned
FROM Orion.VIM.DiskFiles df
INNER JOIN Orion.VIM.Datastores ds ON ds.DataStoreID = df.DataStoreID
WHERE df.Orphaned = TRUE
ORDER BY df.Size DESC
```

There is **no** orphaned flag on `Orion.VIM.VirtualMachines`, so "orphaned VM" has no direct
schema answer. The nearest operational proxy is a VM that is powered off and has not been
active for a long time, which is a heuristic rather than a fact and should be reviewed by a
human before anything is deleted:

```sql
SELECT
    vm.Name AS VMName,
    vm.Host.HostName AS HostName,
    vm.PowerState,
    vm.GuestState,
    vm.LastActivityDate,
    DayDiff(vm.LastActivityDate, GetDate()) AS DaysSinceActivity,
    vm.TotalStorageSize,
    vm.MemoryConfigured,
    vm.ProcessorCount,
    vm.DateCreated
FROM Orion.VIM.VirtualMachines vm
WHERE vm.PowerState <> 'PoweredOn'
  AND vm.LastActivityDate < AddDay(-30, GetDate())
ORDER BY vm.LastActivityDate
```

`PowerState` is a string coming from the hypervisor rather than a platform enumeration.
`'PoweredOn'` is the vSphere spelling; run `SELECT DISTINCT vm.PowerState FROM
Orion.VIM.VirtualMachines vm` on a mixed-hypervisor estate before relying on any literal.

### Which VMs are waiting for CPU

`CpuReady` is the number that explains a slow VM whose own CPU graph looks fine. Reading it
from history rather than the current value avoids chasing a single bad poll.

```sql
SELECT
    vm.Name AS VMName,
    vm.Host.HostName AS HostName,
    AVG(st.AvgCpuReady) AS MeanCpuReady,
    MAX(st.MaxCpuReady) AS PeakCpuReady,
    AVG(st.AvgCPUUsageMHz) AS MeanCpuMHz
FROM Orion.VIM.VMStatistics st
INNER JOIN Orion.VIM.VirtualMachines vm ON vm.VirtualMachineID = st.VirtualMachineID
WHERE st.DateTime > AddDay(-7, GetDate())
GROUP BY vm.Name, vm.Host.HostName
HAVING AVG(st.AvgCpuReady) > 5
ORDER BY AVG(st.AvgCpuReady) DESC
```

The `st.DateTime` bound is not optional. `Orion.VIM.VMStatistics` is one of the largest tables
the module writes, and it is `DateTime` here rather than `ObservationTimestamp`, even though
the entity inherits both.

### Cluster capacity, as a forecast rather than a snapshot

```sql
SELECT
    c.DataCenter.Name AS DataCenterName,
    c.Name AS ClusterName,
    c.CpuCoreCount,
    c.TotalCpu,
    c.TotalMemory,
    c.CPULoad,
    c.MemoryUsage,
    c.VmCapacityCount,
    c.VmCapacityConstraint,
    c.CpuUtilizationDepletionDate,
    c.MemoryUtilizationDepletionDate,
    c.DiskUtilizationDepletionDate,
    c.HaStatus,
    c.DrsStatus
FROM Orion.VIM.Clusters c
WHERE c.UnManaged = FALSE
ORDER BY c.CPULoad DESC
```

`VmCapacityConstraint` names the resource that runs out first, which turns three depletion
dates into one actionable sentence. `HaStatus` and `DrsStatus` are typed `System.Boolean`
rather than as strings, so they filter cleanly: `WHERE c.HaStatus = FALSE` finds the clusters
where high availability is not in effect, which is worth reviewing alongside the capacity
numbers rather than after an incident.

### Unresolved hypervisor alarms

```sql
SELECT TOP 100
    a.Name AS AlarmName,
    a.SystemName,
    t.AlarmStatus,
    t.Timestamp,
    t.Acknowledged,
    t.AcknowledgedByUser,
    t.IsResolved,
    t.VirtualMachine.Name AS VMName,
    t.Host.HostName AS HostName,
    t.Cluster.Name AS ClusterName,
    t.Datastore.Name AS DatastoreName
FROM Orion.VIM.TriggeredAlarmState t
INNER JOIN Orion.VIM.Alarm a ON a.Id = t.RelatedAlarm
WHERE t.IsResolved = FALSE
  AND t.Timestamp > AddDay(-7, GetUtcDate())
ORDER BY t.Timestamp DESC
```

`GetUtcDate()` rather than `GetDate()`, because `Timestamp` on this entity is documented as
UTC. The four `Related*` navigations selected here are all to-one, and any of them can be
null for a given alarm, since one alarm is about one kind of object. Selecting all four and
letting three be null is deliberate: it gives one column shape whatever the alarm is about.

### Datastores and the storage array behind them

When SRM is licensed too, this is the query that ends the argument about whether a latency
problem is the hypervisor's or the array's, by putting both numbers on one row.

```sql
SELECT TOP 100
    ds.Name AS DatastoreName,
    ds.Capacity,
    ds.SpaceUtilization,
    l.Caption AS SrmLunName,
    l.StorageArray.Name AS ArrayName,
    l.IOLatencyTotal AS ArraySideLatency,
    ds.LatencyTotal AS HypervisorSideLatency
FROM Orion.VIM.Datastores ds
INNER JOIN Orion.VIM.Luns vl ON vl.DataStoreID = ds.DataStoreID
INNER JOIN Orion.SRM.LunsToVIMLuns map ON map.VIMLunID = vl.LunID
INNER JOIN Orion.SRM.LUNs l ON l.LUNID = map.LunID
ORDER BY ds.SpaceUtilization DESC
```

Four spellings of "LUN" appear in that query, and each is right where it stands:
`Orion.VIM.Luns`, `vl.LunID`, `Orion.SRM.LUNs`, `l.LUNID`.

### Which hosts can see this LUN, and by how many paths

```sql
SELECT
    vl.CanonicalName,
    vl.Name AS LunName,
    ds.Name AS DatastoreName,
    h.HostName,
    h.Node.Caption AS OrionNodeCaption,
    sp.Initiator,
    sp.Target,
    sp.Active
FROM Orion.VIM.LunStoragePaths sp
INNER JOIN Orion.VIM.Luns vl ON vl.LunID = sp.LunID
INNER JOIN Orion.VIM.Hosts h ON h.HostID = sp.HostID
LEFT JOIN Orion.VIM.Datastores ds ON ds.DataStoreID = vl.DataStoreID
WHERE vl.CanonicalName = @canonicalName
ORDER BY h.HostName, sp.Initiator
```

A host showing a single row here has one path to the LUN and no redundancy, which is worth
finding before the maintenance window rather than during it. The `LEFT JOIN` to datastores
keeps LUNs presented to a host but not yet formatted.

### Guest filesystems that are nearly full

The inside-the-guest view, which is not the same as the VM's storage footprint on the
datastore.

```sql
SELECT TOP 100
    vm.Name AS VMName,
    vmv.MountPoint,
    vmv.Capacity,
    vmv.FreeSpace,
    vmv.SpaceUtilization
FROM Orion.VIM.VirtualMachineVolumes vmv
INNER JOIN Orion.VIM.VirtualMachines vm ON vm.VirtualMachineID = vmv.VirtualMachineID
WHERE vmv.SpaceUtilization > 85
ORDER BY vmv.SpaceUtilization DESC
```

### The hypervisor mix

`PlatformID` is what separates VMware from Hyper-V, Nutanix and Proxmox VE, and
`Orion.VIM.Platform` is the lookup that turns it into a name. `Orion.VIM.Hosts` has the id
but no navigation to the lookup, so this join is explicit; `Orion.VIM.VirtualMachines` does
have a `Platform` navigation.

```sql
SELECT
    p.Name AS PlatformName,
    COUNT(h.HostID) AS HostCount,
    SUM(h.VmCount) AS VMCount,
    SUM(h.CpuCoreCount) AS TotalCores,
    SUM(h.MemorySize) AS TotalMemory
FROM Orion.VIM.Hosts h
INNER JOIN Orion.VIM.Platform p ON p.PlatformID = h.PlatformID
GROUP BY p.Name
ORDER BY COUNT(h.HostID) DESC
```

### Why VIM data stopped arriving

`Orion.VIM.PollingTasks` is the first place to look, because a vCenter can be reachable while
one of its polling jobs is timing out.

```sql
SELECT
    vc.Name AS VCenterName,
    vc.IPAddress,
    vc.VMwareProductName,
    vc.VMwareProductVersion,
    vc.ConnectionState,
    vc.StatusMessage,
    vc.Node.Caption AS OrionNodeCaption,
    pt.PollingTaskTypeID,
    pt.PollingInterval,
    pt.LastPoll,
    pt.LastPollStatus,
    pt.LastPollStatusMessage
FROM Orion.VIM.PollingTasks pt
INNER JOIN Orion.VIM.VCenters vc ON vc.VCenterID = pt.VCenterID
ORDER BY vc.Name, pt.PollingTaskTypeID
```

### One query across virtual and cloud instances

`Orion.VIM.VirtualMachines` and the four cloud instance entities all inherit
`Orion.Virtualization.Instance`, so querying the base entity returns on-premises VMs and
cloud instances together. `InstanceType` tells you which is which.

```sql
SELECT TOP 200
    i.VirtualMachineID,
    i.Name,
    i.InstanceType,
    i.NodeID,
    i.CpuLoad,
    i.NetworkUsageRate,
    i.UnManaged
FROM Orion.Virtualization.Instance i
ORDER BY i.Name
```

Only the nine columns the base declares plus the inherited platform ones are available here.
Anything specific to VMware, such as `PowerState` or `CpuReady`, requires querying
`Orion.VIM.VirtualMachines` directly. Confirm the family on your own server:

```bash
python3 tools/schema_query.py children Orion.Virtualization.Instance
```

## Gotchas

**`Orion.VIM.LUNs` does not exist; the entity is `Orion.VIM.Luns`.** The all-capitals form
appears throughout older references. `Orion.SRM.LUNs` *is* capitalised, which is what makes
the wrong form feel right.

**There is no `Caption` anywhere in `Orion.VIM.`** Every other module uses `Caption` as the
display name and this one does not: hosts use `HostName`, everything else uses `Name`, and
`DisplayName` is available on the managed entities because it is inherited from
`System.Entity`. A query written from habit with `vm.Caption` fails.

**A VM's `NodeID` is usually null.** It is populated only when the guest is separately
monitored as a node. Inner-joining `Orion.Nodes` on it silently narrows the result to that
subset. `Orion.VIM.Hosts.NodeID` and `Orion.VIM.VCenters.NodeID` behave differently: those
are the hypervisor and the management server as monitored nodes, and are normally populated.

**The chain through the cluster drops standalone hosts.** `vm.Host.Cluster.DataCenter.Name`
is four inner joins. Hosts outside a cluster have no `ClusterID`, so their VMs disappear. Use
`vm.Host.DataCenter.Name` when you want everything.

**Four statistics entities filter on `DateTime`, not `ObservationTimestamp`.**
`Orion.VIM.VMStatistics`, `HostStatistics`, `ClusterStatistics` and `DatastoreStatistics`
declare their own `DateTime` column while also inheriting `ObservationTimestamp`. The storage
statistics entities use `ObservationTimestamp`. Run `props` before writing the filter.

**`Orion.VIM.Snapshots` cannot reach its virtual machine.** It has one relationship,
`DiskFiles`. Join on `VirtualMachineID` explicitly, and remember `s.PowerState` is the state
at snapshot time rather than now.

**`Orion.VIM.VirtualDisks.DataStore` points at an entity name that is not in the schema.**
The published relationship declares its target as `Orion.VIM.DataStores`, capital S, and the
2026.2 schema contains no entity by that name; the real entity is `Orion.VIM.Datastores`.
Anything that resolves the chain strictly, including `tools/validate_swql.py` in this
repository, rejects `vd.DataStore.SomeColumn`. **Unverified:** whether a live server resolves
it anyway by matching case-insensitively. Sidestep the question entirely by using the
denormalised `DataStoreName` column already on the virtual disk row, or by joining
`Orion.VIM.Datastores` explicitly on `DataStoreID`. The same row also carries
`VirtualMachineName`, `HostName`, `ClusterName`, `DatacenterName`, `VCenterName` and
`LunName`, so the join is rarely needed at all.

**`Orion.VIM.TriggeredAlarmState.AlarmStatus` is not a platform status.** Its scale is 0
unknown, 1 green, 2 yellow, 3 red. Joining `Orion.StatusInfo` to it produces plausible
nonsense.

**Alarm timestamps are UTC.** `Timestamp`, `AcknowledgedTime` and `LastSeenTimestamp` on
`Orion.VIM.TriggeredAlarmState` are documented as UTC, unlike most platform datetime columns.
Compare against `GetUtcDate()`, and read
[../swql/date-and-time.md](../swql/date-and-time.md) before combining `GetUtcDate()` with the
`Add*` functions.

**`ChangeSettings` restarts a running VM and starts a stopped one.** Pass `restartRequired`
as `false` on a powered-off VM if you do not want it powered on as a side effect.

**`TakeSnapshot`'s summary and the Swagger contract disagree about whether `snapshotName` is
optional.** Pass a name.

**`DeleteVM` and `UnregisterVM` are `PerformBasicAction` values, not separate verbs.** They
are as easy to type as `Reboot` and considerably harder to undo. Nothing in the API asks you
to confirm.

**`entityType` and `hypervisorId` number the hypervisors differently.** Discovery uses one
scheme, credential validation uses another. Reusing the value across the two verbs onboards
the wrong platform.

**`SimulationResult` is a JSON string.** SWQL will hand you the whole document as text.
Parse it in your client.

**`EntityNetObjectID` on a capacity planning report is a NetObject string, not an integer.**
It cannot be joined directly to `ClusterID` or `HostID`.

**No VIM entity publishes an unmanage verb.** They inherit `UnManaged`, `UnManageFrom` and
`UnManageUntil` from `System.ManagedEntity` and can be put into a maintenance window from the
console, but the verb to call from a script is `Orion.Nodes.Unmanage` against the underlying
node, which only works for hosts and vCenters.

**Account limitations silently filter results.** Two accounts running the same VM inventory
legitimately get different rows, so an unexpectedly empty result is often a permissions
problem rather than a monitoring gap.

**The module has to be installed.** Some VIM entities appear on servers where NPM or SAM
provides limited virtualization polling, and the full set does not. Confirm rather than
assume:

```sql
SELECT COUNT(FullName) AS EntityCount
FROM Metadata.Entity
WHERE FullName LIKE 'Orion.VIM.%'
```

## See also

- [srm.md](srm.md) for Storage Resource Monitor and the storage side of the LUN, NAS and
  datastore joins.
- [README.md](README.md) for the index of every module page.
- [../platform/modules.md](../platform/modules.md) for the whole namespace map, including the
  note that Virtualization Manager is `Orion.VIM.` and not `Orion.VMAN.`.
- [../swql/joins-and-navigation.md](../swql/joins-and-navigation.md) for why a chain of
  to-one navigations drops rows and a to-many navigation multiplies them.
- [../swql/date-and-time.md](../swql/date-and-time.md) for the UTC and local-time trap the
  alarm entities walk straight into.
- [../swis/invoke-verbs.md](../swis/invoke-verbs.md) for the positional argument rules the VM
  management verbs depend on.
- [../reference/netobject-types.md](../reference/netobject-types.md) for the VIM NetObject
  prefixes: `VVC` vCenter, `VMD` datacenter, `VMC` cluster, `VH` host, `VVM` virtual machine,
  `VMS` datastore.
- [../reference/verb-index.md](../reference/verb-index.md) for every verb with its ordered
  parameters.
- [../../scripts/swql/10-virtualization.swql](../../scripts/swql/10-virtualization.swql) for
  more verified virtualization sample queries.

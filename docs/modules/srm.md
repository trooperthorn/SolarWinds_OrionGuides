# SRM: Storage Resource Monitor

Every other part of the platform sees storage the way a server sees it: a drive letter, a
mount point, a percentage full. Storage Resource Monitor sees it the way the array sees it.
It talks to the controller of a SAN or NAS device and pulls back the objects the array
itself is built from, so you can answer questions that are invisible from the host side.
Which pool is oversubscribed. Which LUN is queueing. Which physical disk failed and which
spare took over. Which of the sixty servers attached to that array will notice if you take
one LUN offline.

That difference in vantage point is the single most important thing to hold onto when
reading this schema, and it is where nearly every SRM mistake starts. SRM has an entity
called `Orion.SRM.Volumes` and the platform core has an entity called `Orion.Volumes`.
They are not the same object, they are not even the same layer, and adding their capacity
columns together produces a number that means nothing. The
[SRM volumes are not Orion volumes](#srm-volumes-are-not-orion-volumes) section deals with
that before anything else.

## Namespace and size

All 135 SRM entities live under one prefix, `Orion.SRM.`, with the module code spelled in
capitals. There is no `Orion.Storage.` namespace.

| Group | Entities | What is in it |
|---|---|---|
| Monitored objects | 9 | The things that appear in the web console and can be unmanaged, alerted on, and given custom properties |
| Thresholds | 85 | One concrete entity per metric per object type, plus eight base entities |
| Statistics | 12 | Capacity history and performance history, covering seven of the object types |
| Custom properties | 9 | One per monitored object type |
| Everything else | 20 | Polling engines, device templates, topology, cross-module mappings, LUN masking, physical disks, file servers |

The thresholds dominate the count and carry almost none of the meaning, which is why a raw
"135 entities" figure overstates how much of this module you need to learn. Nine entities do
the real work.

Check the grouping yourself:

```bash
python3 tools/schema_query.py find Orion.SRM --properties
python3 tools/schema_query.py show Orion.SRM.StorageArrays
python3 tools/schema_query.py verbs --entity Orion.SRM.StorageArrays
```

SRM also brings four entities into the hardware health namespace, because a storage array
has fans and power supplies like any other chassis:
`Orion.HardwareHealth.HardwareInfoForArray`, `Orion.HardwareHealth.HardwareItemForArray`,
`Orion.HardwareHealth.HardwareCategoryStatusForArray` and
`Orion.HardwareHealth.HardwareHierarchyForArray`. See
[hardware-health.md](hardware-health.md) for how that family is shaped.

## SRM volumes are not Orion volumes

This deserves its own section because conflating the two is the classic SRM error, and the
symptom is a report that looks plausible and is wrong.

| | `Orion.Volumes` | `Orion.SRM.Volumes` |
|---|---|---|
| What it is | A filesystem or disk as the operating system on a monitored node presents it | A volume as the storage array presents it, which SolarWinds' own NetObject reference calls a "NAS Volume" |
| Where the data comes from | Polling the host, by SNMP, WMI or agent | Polling the array controller |
| Key | `VolumeID`, unique within `Orion.Volumes` | `VolumeID`, unique within `Orion.SRM.Volumes` |
| Parent | `NodeID`, a monitored node | `StorageArrayID`, and usually a pool and a vServer |
| Capacity columns | `VolumeSize`, `VolumeSpaceUsed`, `VolumeSpaceAvailable`, `VolumePercentUsed` | `CapacityTotal`, `CapacityAllocated`, `CapacityFree`, `CapacityUsedPercentage`, `CapacityFileSystem` |
| NetObject prefix | `V` | `SMV` |
| Comes from | The platform core, always present | Storage Resource Monitor, only when licensed |

Both entities have a `VolumeID` integer and both are about "a volume", which is exactly why
the mistake is easy. Two independent id spaces called `VolumeID` in the same database means
a join written on `VolumeID` alone will silently match unrelated rows.

The right way across the boundary is the navigation properties, which SRM populates from its
topology polling. From a host filesystem you can reach the array object behind it:

```sql
SELECT TOP 100
    v.Node.Caption AS ServerName,
    v.Caption AS HostFilesystem,
    v.VolumeSize,
    v.VolumePercentUsed,
    v.LUN.Caption AS BackingLUN,
    v.LUN.StorageArray.Name AS ArrayName,
    v.FileShare.Caption AS BackingFileShare
FROM Orion.Volumes v
WHERE v.LUN.LUNID IS NOT NULL
   OR v.FileShare.FileShareID IS NOT NULL
ORDER BY v.Node.Caption, v.Caption
```

`Orion.Volumes.LUN` leads to `Orion.SRM.LUNs` for block storage, and
`Orion.Volumes.FileShare` leads to `Orion.SRM.FileShares` for a mounted share. Both are
to-one navigations, so each row stays one row. Rows where both are null are host volumes
with no array behind them that SRM knows about, which is the normal case for local disks.

The same idea runs the other way. `Orion.SRM.LUNs.ServerVolumes` and
`Orion.SRM.FileShares.ServerVolumes` are the reverse navigation to `Orion.Volumes`, and
`Orion.SRM.Volumes.RelyServerVolumes` is the dependency-model edge from an array volume to
the host filesystems that depend on it.

## The storage hierarchy

SRM models two paths through an array, block and file, that share the top of the tree and
diverge below the pool. Every level below is a real entity; the names, keys and parent
columns here were read out of the schema rather than recalled.

```
Orion.SRM.Providers            a management endpoint (SMI-S provider or native API)
  └── Orion.SRM.StorageArrays  one physical or clustered array
        ├── Orion.SRM.PhysicalDisks        the spindles and SSDs, including spares
        ├── Orion.SRM.StorageControllers   the array's controllers or nodes
        │     └── Orion.SRM.StorageControllerPorts   FC, iSCSI and Ethernet ports
        ├── Orion.SRM.Pools                aggregates, RAID groups, storage pools
        │     ├── Orion.SRM.LUNs           block storage presented to hosts
        │     │     └── Orion.SRM.LunMasking   which initiator may see which LUN
        │     └── Orion.SRM.Volumes        array-side (NAS) volumes
        │           └── Orion.SRM.FileShares   NFS exports and SMB shares
        └── Orion.SRM.VServers             storage virtual machines / SVMs / vFilers
```

`Orion.SRM.FileServers` and `Orion.SRM.FileServerIdentification` sit alongside file shares
rather than inside the tree; see [file servers](#file-servers) below.

### Providers

`Orion.SRM.Providers` is the thing you give credentials to, not the thing you monitor. For
an SMI-S array it is the SMI-S provider host; for arrays SRM polls natively it is the
management endpoint. One provider can front several arrays, which is why the relationship
runs provider to arrays and not the other way round.

Key columns: `ProviderID`, `EngineID`, `IPAddress`, `HostName`, `UsingHostName`, `Name`,
`Caption`, `Status`, `ProviderType`, `ProviderLocation`, `CredentialType`, `CredentialID`,
`Version`, `Build`, `LastSync`, `DeviceGroupID`, `ProviderGroupID`, `TemplateID`,
`PollerType`, `PollingInterval`. Navigations: `Engine` to `Orion.SRM.Engines`, `DeviceGroup`
to `Orion.SRM.DeviceGroups`, `StorageArrays` to `Orion.SRM.StorageArrays`, and
`CustomProperties`.

`ProviderType`, `ProviderLocation` and `CredentialType` are integers whose meanings are not
recorded in the extracted schema. **Unverified:** treat their values as opaque until you
have confirmed them on your own server. `Metadata.Property` sometimes carries the
enumeration in its `Values` array, and it is the cheapest place to look first:

```sql
SELECT p.Name, p.Type, p.Values, p.Summary
FROM Metadata.Property p
WHERE p.Entity.FullName = 'Orion.SRM.Providers'
  AND p.Name IN ('ProviderType', 'ProviderLocation', 'CredentialType')
ORDER BY p.Name
```

If `Values` comes back empty, fall back to
`SELECT DISTINCT pr.ProviderType FROM Orion.SRM.Providers pr` and match the results against
what the web console shows.

### Storage arrays

`Orion.SRM.StorageArrays` is the centre of the module. It has 65 properties, 24 outgoing
relationships and four of SRM's seven non-custom-property verbs, and almost every useful
query either starts here or joins back to here for a name.

Identity and inventory: `StorageArrayID` (the key), `ID` (the array's own identifier
string), `Name`, `UserCaption`, `Caption`, `DisplayName`, `IPAddress`, `Vendor`,
`Manufacturer`, `Model`, `Firmware`, `SerialNumber`, `Disks`, `IsCluster`, `Type`.

Capacity, in two independent families that answer different questions:

- **Raw**, what the disks physically hold: `CapacityRawTotal`, `CapacityRawUsed`,
  `CapacityRawUsedPercentage`, `CapacityRawFree`, `CapacityRawSpare`.
- **User**, what is usable after RAID and data reduction: `CapacityUserTotal`,
  `CapacityUserUsed`, `CapacityUserUsedPercentage`, `CapacityUserFree`,
  `CapacityUserFreePercentage`.
- **Reduction ratios** that connect the two: `DataReduction`, `TotalReduction`.

Reporting raw capacity when someone asked "how much space is left" overstates it, sometimes
by a factor of two or three on a modern all-flash array. Report `CapacityUserFree` for
"space available to provision" and the raw family for "how much hardware is installed".

Performance, polled separately from capacity: `IOPSTotal`, `IOPSRead`, `IOPSWrite`,
`IOPSOther`, `IOPSReadWriteRatio`, `BytesPSTotal`, `BytesPSRead`, `BytesPSWrite`,
`IOSizeTotal`, `IOSizeRead`, `IOSizeWrite`. Note there is **no** latency column on the array
entity; latency lives on LUNs, volumes, pools and controllers.

Forecasting: `CapacityRunoutSlope`, `CapacityRunoutOffset`, `CapacityRunout`,
`CapacityRunoutDate`. SRM fits the trend for you, and a report built on `CapacityRunoutDate`
is far more useful in a budget conversation than a current percentage.

Polling state, which is what you check when numbers look stale: `EngineID`, `PollerType`,
`TemplateID`, `StatCollection`, `RediscoveryInterval`, `TopologyInterval`,
`ControllerInterval`, `DeviceSyncInterval`, `LastSync`, `DeviceLastSync`,
`LastCapacityPollTime`, `LastPerformancePollTime`, `LastTopologyPollTime`,
`LastControllerPollTime`, `ControllersPollingFeature`. Four separate poll timestamps is not
redundancy: capacity, performance, topology and controller data are collected on independent
schedules, so one can be hours stale while the others are current.

Status: `Status` (the platform integer, join `Orion.StatusInfo`), `StatusDescription`,
`OperStatus`, `OperStatusDescription`. `OperStatus` is the array's own reported operational
state and is not the same scale as `Status`.

### Pools

`Orion.SRM.Pools` covers whatever the vendor calls the layer between disks and provisioned
storage: aggregate, RAID group, storage pool, disk group. Key `PoolID`, parent
`StorageArrayID`, navigations `StorageArray`, `LUNs`, `Volumes`, `Statistics`,
`CapacityStatistics`, `CustomProperties`.

The capacity columns are the ones worth knowing, because they are the only place in the
module where thin provisioning is made visible:

| Column | Meaning |
|---|---|
| `CapacityUserTotal` | Usable capacity the pool actually has |
| `CapacityUserUsed`, `CapacityUserUsedPercentage` | How much of it is really written |
| `CapacityUserFree`, `CapacityUserFreePercentage` | What is left |
| `CapacityAllocated` | What has been carved out of the pool |
| `CapacitySubscribed`, `CapacitySubscribedPercentage` | What has been *promised* to consumers |
| `CapacityOversubscribed` | The amount by which promises exceed capacity |
| `EstimatedFreeCapacity` | SRM's estimate of the space genuinely available |

`CapacityOversubscribed > 0` is normal on a thin-provisioned array and is a problem only in
combination with a high `CapacityUserUsedPercentage` and a near `CapacityRunoutDate`. A
report that alerts on oversubscription alone will fire on healthy pools forever.

Pools can nest. `Orion.SRM.PoolToPoolsMapping` records `PoolID`, `ParentPoolID` and
`SpaceConsumed`, and the pool entity carries a `RelyParentPool` dependency edge to itself.
A naive `SUM(CapacityUserTotal)` over all pools on an array will double count where a
hierarchy exists, so check whether `Orion.SRM.PoolToPoolsMapping` has rows before summing.

Other columns: `RaidType`, `Thin`, `Type`, `Category`, `DataReduction`, `TotalReduction`,
the IOPS/BytesPS/IOSize/IOLatency families, and the `CapacityRunout*` forecast set.
**Unverified:** `Type` and `Category` are integers whose enumerations are not in the
extracted schema; select `DISTINCT` on your own array before filtering on them.

### LUNs

`Orion.SRM.LUNs` is block storage as presented to a host. Key `LUNID`, NetObject prefix
`SML`. Note the capitalisation: the entity is `Orion.SRM.LUNs` with `LUN` in capitals, and
the key is `LUNID`, but the LUN masking entity spells its foreign key `LunID` in mixed case.
Both are correct in their own entity, and neither is a typo you should fix.

Identity: `LUNID`, `StorageArrayID`, `VolumeID`, `ID`, `UUID`, `Name`, `UserCaption`,
`Caption`, `DisplayName`, `RaidType`, `Protocol`, `Thin`, `Free`, `ReadOnly`,
`CacheEnabled`, `DefaultControllerID`, `CurrentControllerID`.

`Free` is a **boolean**, not a byte count. The byte count of free space is `CapacityFree`.
Writing `WHERE l.Free > 1000000000` will not error, it will just be wrong.
`DefaultControllerID` and `CurrentControllerID` differing is how you spot a LUN that has
failed over to its partner controller and never failed back, which is a quiet cause of
imbalanced array performance.

Capacity: `CapacityTotal`, `CapacityAllocated`, `CapacityFree`, `CapacityFreePercentage`,
`CapacityUsedPercentage`, `CapacityRatePerDay`, `CapacityRatePerDayPercentage`, plus the
pool's capacity denormalised onto the LUN as `PoolCapacityTotal`, `PoolCapacityAllocated`,
`PoolCapacityFree`, `PoolCapacityFreePercentage`. The denormalised pool columns exist so a
LUN-level report can show "this LUN is only 40 percent full but the pool underneath it is at
97 percent", which is the situation that actually causes an outage on a thin-provisioned
array.

Forecast: `CapacityRunoutSlope`, `CapacityRunoutOffset`, `CapacityRunout`,
`CapacityRunoutDate`, and two convenience columns `EightyPercentUsageDate` and
`NinetyPercentUsageDate`. Those last two are typed `System.String`, not `System.DateTime`,
so date functions will not apply to them directly.

Performance: `IOPSTotal`, `IOPSRead`, `IOPSWrite`, `IOPSOther`, `IOPSReadWriteRatio`,
`BytesPSTotal`, `BytesPSRead`, `BytesPSWrite`, `IOLatencyTotal`, `IOLatencyRead`,
`IOLatencyWrite`, `IOLatencyOther`, `IOSizeTotal`, `IOSizeRead`, `IOSizeWrite`,
`QueueLength`. Latency is the number that correlates with a user complaining; IOPS on its
own tells you how busy something is, not whether it is suffering.

Navigations out of a LUN are unusually rich, because a LUN is where SRM meets the platform
core, Virtualization Manager and Database Performance Analyzer at once: `StorageArray`,
`Pools`, `Statistics`, `CapacityStatistics`, `LunMaskings`,
`ServerVolumes` to `Orion.Volumes`, `Datastores` to `Orion.VIM.Datastores`,
`VirtualMachines` to `Orion.VIM.VirtualMachines`, and `DatabaseInstance` to
`Orion.DPA.DatabaseInstance`.

### NAS volumes and vServers

`Orion.SRM.Volumes` is the file-side sibling of a LUN: a volume carved from a pool and
exported through a vServer. Key `VolumeID`, NetObject prefix `SMV`, displayed by SolarWinds
as "NAS Volume".

Its capacity family adds a pair of columns LUNs do not have, `CapacityFileSystem` and
`CapacityFileSystemPercentage`, which is what the filesystem on the volume is consuming as
opposed to what the volume has allocated from the pool. Everything else matches the LUN
shape: `CapacityTotal`, `CapacityAllocated`, `CapacityFree`, `CapacityFreePercentage`,
`CapacityUsedPercentage`, `CapacityRatePerDay`, the `PoolCapacity*` denormalisation, the
`CapacityRunout*` forecast, the IOPS/BytesPS/IOLatency/IOSize performance families,
`QueueLength`, `Thin`, `CacheEnabled`.

Navigations: `Pools`, `StorageArray`, `VServers`, `FileShares`, `Statistics`,
`CapacityStatistics`, `RootVolumeForVServer`, `CustomProperties`.

`Orion.SRM.VServers` is the storage virtual machine: NetApp SVM, EMC VDM, or the vendor's
equivalent. Key `VServerID`, NetObject prefix `SMVS`. It carries `RootVolumeID` with a
`RootVolume` navigation back to `Orion.SRM.Volumes`, an `IPAddress`, the capacity pair
`CapacityAllocated` and `CapacitySubscribed`, the IOPS/BytesPS/IOSize performance families
(but **not** latency), and a `Volumes` navigation to everything it serves.

### File shares

`Orion.SRM.FileShares` is an individual export: an NFS export or SMB share. Key
`FileShareID`, NetObject prefix `SMS`. It is deliberately small, 21 properties, because a
share is a name and a quota rather than a performance object.

`FileShareID`, `FileServerID`, `VolumeID`, `ID`, `Name`, `UserCaption`, `Caption`,
`DisplayName`, `Type`, `Path`, `Quota`, `Free`, `Used`, `LastSync`, `Status`,
`StatusDescription`, `DetailsUrl`, plus the inherited `UnManaged` trio.

Here `Free` and `Used` are `System.Int64` byte counts, unlike the boolean `Free` on
`Orion.SRM.LUNs`. Two entities in the same namespace using the same column name for a
boolean and for a byte count is exactly the sort of thing to check rather than assume.

Navigations: `Volume` to the NAS volume it lives on, `FileServer` to the server exporting
it, `ServerVolumes` to the host filesystems that mount it, `Datastores` to
`Orion.VIM.Datastores` for NFS datastores, and `CustomProperties`.

### File servers

Two small entities describe the server side of a share, and one of them is the subject of a
well-known naming trap.

`Orion.SRM.FileServers` has five properties: `FileServerID`, `ID`, `Name`, `IPAddress`,
`Description`. It navigates to `FileShares` and to `FileServerIdentifications`.

`Orion.SRM.FileServerIdentification` exists so a file server can have more than one address:
`FileServerIdentificationID`, `FileServerID`, `ID`, `IPAddress`, `Description`, with a
`FileServer` navigation back. Its purpose, in the schema's own words, is "mainly for storing
additional IP addresses". That matters operationally, because a share advertised on a
secondary address will not match a host mount unless you look here too.

**The community SWQL workbook spells this entity `Orion.SRM.FIleServerIdentification`, with
a capital `I` in "File".** That is a typo in the workbook and not a real entity name. The
correct name in the 2026.2 schema is `Orion.SRM.FileServerIdentification`. This repository
records the discrepancy in
[`data/reference/reconciliation.json`](../../data/reference/reconciliation.json), and
[../reference/netobject-types.md](../reference/netobject-types.md) marks the workbook row as
superseded. If you are working from the workbook, or from a model that learned it, the
misspelled form will fail on a live server with an unknown-entity error.

### Physical disks, controllers and ports

`Orion.SRM.PhysicalDisks` is the individual drive: `PhysicalDiskID`, `StorageArrayID`, `ID`,
`Name`, `Vendor`, `Model`, `Type`, `SerialNumber`, `Capacity`, `Spare`, `OperStatus`,
`OperStatusDescription`, `Status`, `StatusDescription`, `LastSync`. It has a `StorageArray`
navigation and one verb, `GetCountOfElementsPerEngineForLicensing`. `Spare` is the boolean
that separates a hot spare from a member drive, and a spare that has gone from `Spare = TRUE`
to `Spare = FALSE` has been consumed by a rebuild.

`Orion.SRM.StorageControllers` is the controller or node: `StorageControllerID`,
`StorageArrayID`, `Manufacturer`, `Model`, `SerialNumber`, `Firmware`, `Type`,
`HAConfigurationState`, `TotalMemory`, `MemoryUsed`, `MemoryUtilization`, `CPUFrequency`,
`CPUCount`, `TotalCacheSize`, `Utilization`, the IOPS/BytesPS/IOSize/IOLatency families, and
two columns unique to this entity: `IOPSDistribution` and `BytesPSDistribution`, the share of
the array's total work this controller is doing. Port counts come as `FcPortCount`,
`EthernetPortCount` and `ISCSIPortCount`.

Controller balance is the thing to watch. On a dual-controller array both
`IOPSDistribution` values should sit near 50, and a persistent split like 85/15 usually means
LUNs have failed over and not failed back, which is visible on the LUN side as
`DefaultControllerID <> CurrentControllerID`.

`Orion.SRM.StorageControllerPorts` is one row per port: `StorageControllerPortID`,
`StorageControllerID`, `Name`, `PortType`, `LinkType`, `PortNumber`, `PortIdentifier`,
`IPAddress`, `PortSpeed`, `IOPSTotal`, `IOPSDistribution`, `BytesPSTotal`,
`BytesPSDistribution`, `Status`, `OperStatus`, `OperStatusDescription`. It is the only one of
the nine monitored object types with **no** `Caption` column, so use `Name` or `DisplayName`.

### LUN masking and topology

Two entities record who is allowed to see what, and who actually does.

`Orion.SRM.LunMasking` is the array's masking table as SRM read it: `LunID`,
`InitiatorLunID`, `InitiatorEndpoint`, `TargetEndpoint`, `UUID`, `HostGroup`, `HostAlias`,
with a `Lun` navigation back to `Orion.SRM.LUNs`. `InitiatorEndpoint` is the host's WWPN or
iSCSI IQN and `TargetEndpoint` is the array port. This is configuration, not observation: it
tells you which hosts *may* use a LUN, including ones that never have.

`Orion.SRM.Topology` is the correlation SRM computed between array objects and monitored
Orion objects: `NodeID`, `VolumeID`, `StorageArrayID`, `NetObjectType`, `NetObjectID`,
`Manual`. `Manual` marks a mapping an operator created by hand rather than one SRM inferred,
which is worth selecting whenever a mapping looks wrong, because a hand-made mapping will
not self-correct after the underlying storage is reconfigured.

### Cross-module mappings

Three small entities join SRM to Virtualization Manager and are the honest path between the
two modules:

| Entity | Columns | Joins |
|---|---|---|
| `Orion.SRM.LunsToVIMLuns` | `StorageArrayID`, `LunID`, `VIMLunID`, `Manual` | `Orion.SRM.LUNs` to `Orion.VIM.Luns` |
| `Orion.SRM.FileSharesToVIMNas` | `StorageArrayID`, `FileShareID`, `VIMNasID`, `Manual` | `Orion.SRM.FileShares` to `Orion.VIM.Nas` |
| `Orion.SRM.PoolToPoolsMapping` | `PoolID`, `ParentPoolID`, `SpaceConsumed` | Pools to their parent pools |

Both cross-module mapping tables carry `Manual`, for the same reason `Orion.SRM.Topology`
does. See [vman.md](vman.md) for the Virtualization Manager side of these joins.

## Statistics

Twelve statistics entities cover seven of the object types. Five of them get a pair, one
entity for capacity and one for performance; controllers and controller ports get
performance only; file shares and physical disks get neither. All twelve inherit
`System.StatisticsEntity`, so all twelve carry `ObservationTimestamp`,
`ObservationFrequency` and `Weight` even though none of them declares those columns.

| Object | Capacity history | Performance history |
|---|---|---|
| Storage array | `Orion.SRM.StorageArrayCapacityStatistics` | `Orion.SRM.StorageArrayStatistics` |
| Pool | `Orion.SRM.PoolCapacityStatistics` | `Orion.SRM.PoolStatistics` |
| LUN | `Orion.SRM.LUNCapacityStatistics` | `Orion.SRM.LUNStatistics` |
| NAS volume | `Orion.SRM.VolumeCapacityStatistics` | `Orion.SRM.VolumeStatistics` |
| vServer | `Orion.SRM.VServerCapacityStatistics` | `Orion.SRM.VServerStatistics` |
| Storage controller | none | `Orion.SRM.StorageControllerStatistics` |
| Controller port | none | `Orion.SRM.StorageControllerPortStatistics` |

The capacity entities are deliberately narrow. `Orion.SRM.LUNCapacityStatistics` has four
real columns, `LUNID`, `CapacityTotal`, `CapacityAllocated` and `CapacityFree`, because
capacity moves slowly and only a few numbers are worth keeping.
`Orion.SRM.PoolCapacityStatistics` adds `CapacitySubscribed` and `CapacityOversubscribed`,
which is what makes a "when did we become oversubscribed" question answerable.

The performance entities are wide and include both counters and rates.
`Orion.SRM.LUNStatistics` has `IOTotal`, `IORead`, `IOWrite`, `IOOther` as raw operation
counts and `IOPSTotal`, `IOPSRead`, `IOPSWrite`, `IOPSOther` as the per-second rates over the
interval, plus `BytesTotal`/`BytesPSTotal` in the same pairing, the four `IOLatency*` columns,
`IOSize*`, `QueueLength`, `HitIORead`, `HitIOWrite`, `CacheHitRatio`, `RatioRead` and
`RatioWrite`.

These are the largest tables SRM writes. Always bound them by `ObservationTimestamp`, and
bound them by object id too where you can. Each statistics entity navigates back to its
parent through a single named property, so `cs.LUN.Caption` works without an explicit join.

## Thresholds

SRM's thresholds are the most numerous part of the namespace and the least interesting per
entity, because they are all the same shape. Each concrete threshold entity declares no
properties of its own and inherits twenty from `Orion.Thresholds` through the chain
`Orion.Thresholds` to `Orion.SRM.Thresholds` to a per-object base to the concrete entity.

The seven per-object base entities and their concrete counts:

| Base | Concrete thresholds | Metrics covered |
|---|---|---|
| `Orion.SRM.LUNThresholds` | 14 | IOPS (4), IO latency (4), IO size (3), bytes per second (3) |
| `Orion.SRM.VolumeThresholds` | 14 | Same four families as LUNs |
| `Orion.SRM.PoolThresholds` | 10 | IOPS (4), IO size (3), bytes per second (3), no latency |
| `Orion.SRM.StorageArrayThresholds` | 10 | Same as pools |
| `Orion.SRM.VServerThresholds` | 10 | Same as pools |
| `Orion.SRM.StorageControllerThresholds` | 15 | The above plus latency, utilization and the two distribution metrics |
| `Orion.SRM.StorageControllerPortThresholds` | 4 | IOPS total and distribution, bytes per second total and distribution |

Because the properties are inherited, `show` reports zero properties for every one of them
and `props` reports twenty. Use `props`:

```bash
python3 tools/schema_query.py show Orion.SRM.LUNIOLatencyTotalThreshold
python3 tools/schema_query.py props Orion.SRM.LUNIOLatencyTotalThreshold
```

The columns that matter in a query are `Level1Value` (warning), `Level2Value` (critical),
`IsLevel1State` and `IsLevel2State` (whether the object is currently in that state),
`CurrentValue`, `GlobalWarningValue` and `GlobalCriticalValue` (the platform default this
object may be inheriting), `WarningEnabled` and `CriticalEnabled`, and the polls-based
suppression set `WarningPolls`, `WarningPollsInterval`, `CriticalPolls`,
`CriticalPollsInterval`.

Each threshold is reachable as a named navigation from its object, which is much easier than
joining on `EntityType` and `InstanceId`: `l.IOLatencyTotalThreshold.Level2Value` gets the
critical latency configured for that LUN.

There is one threshold entity in the namespace that is not part of this family.
`Orion.SRM.ApplicationThresholds` declares fourteen properties directly and inherits from
`System.Entity` rather than `Orion.Thresholds`, so it has no `WarningEnabled`,
`CriticalEnabled` or polls-based suppression columns. **Unverified:** the schema does not
say what "application" means in that name; check for rows on your own server before
building on it.

## Verbs

SRM publishes 52 verbs, but 45 of them are the standard five-verb custom property management
set repeated across nine custom property entities. Seven verbs do anything SRM-specific.

| Entity | Verb | Positional parameters | Returns |
|---|---|---|---|
| `Orion.SRM.StorageArrays` | `GetLicensedArrays` | none | array of storage array ids |
| `Orion.SRM.StorageArrays` | `AddSmisCredentials` | `displayName`, `userName`, `password`, `interopNamespace`, `arrayNamespace`, `httpPort` (optional), `httpsPort` (optional), `useSsl` (optional) | credential id |
| `Orion.SRM.StorageArrays` | `AddExternalProvider` | `ipAddress`, `credentialsId` | provider id |
| `Orion.SRM.StorageArrays` | `AddAllArrays` | `deviceGroupId`, `providersIds` (array), `engineIp` (optional) | boolean |
| `Orion.SRM.PhysicalDisks` | `GetCountOfElementsPerEngineForLicensing` | none | licensing count result |
| `Orion.SRM.DeviceMigrations` | `RefreshDeviceMigrations` | none | void |
| `Orion.SRM.DeviceMigrations` | `TriggerMigration` | `migrationType`, `migrationObject`, `objectID` | migration entity |

Confirm the signature before you call one, because argument order is the whole contract and
names never travel on the wire:

```bash
python3 tools/schema_query.py verb Orion.SRM.StorageArrays AddSmisCredentials
python3 tools/schema_query.py verb Orion.SRM.DeviceMigrations TriggerMigration
```

The three `Add*` verbs are the onboarding sequence, and they run in that order: create the
credential, register the provider that credential reaches, then add the arrays the provider
fronts. `AddAllArrays` takes an **array** of provider ids as its second argument, which is
the case where `Invoke-SwisVerb` needs the leading-comma idiom described in
[../swis/invoke-verbs.md](../swis/invoke-verbs.md).

```powershell
Import-Module SwisPowerShell
$swis = Connect-Swis -Hostname orion.example.com -Trusted

# 1. Store SMI-S credentials. Returns the new credential id.
$credentialId = (Invoke-SwisVerb $swis Orion.SRM.StorageArrays AddSmisCredentials @(
    'Lab SMI-S',            # displayName
    'srm-readonly',         # userName
    $plainTextPassword,     # password
    'root/interop',         # interopNamespace
    'root/emc',             # arrayNamespace
    5988,                   # httpPort
    5989,                   # httpsPort
    $true                   # useSsl
)).InnerText

# 2. Register the provider that those credentials reach. Returns the new provider id.
$providerId = (Invoke-SwisVerb $swis Orion.SRM.StorageArrays AddExternalProvider @(
    '10.10.0.50',
    [int]$credentialId
)).InnerText

# 3. Add every array the provider fronts. providersIds is an array parameter, so the
#    argument list needs the leading comma and an explicit cast.
$deviceGroupId = Get-SwisData $swis @"
SELECT TOP 1 dg.DeviceGroupID
FROM Orion.SRM.DeviceGroups dg
WHERE dg.Name = @name
"@ @{ name = 'EMC VNX' }

Invoke-SwisVerb -SwisConnection $swis -EntityName Orion.SRM.StorageArrays -Verb AddAllArrays `
    -Arguments @( $deviceGroupId, ( , [int[]] @($providerId) ) ) | Out-Null
```

`TriggerMigration` moves an array from one polling implementation to another and is the
verb behind SolarWinds' "migrate this device to the new poller" workflow.
`Orion.SRM.DeviceMigrations` rows tell you what can be migrated and what state a migration is
in: `ObjectID`, `MigrationObject`, `MigrationType`, `SRMDeviceMigrationStatus`, `Message`,
`LastUpdate`. Call `RefreshDeviceMigrations` first if the table looks stale, read a candidate
row, then pass that row's `MigrationType`, `MigrationObject` and `ObjectID` straight through.
This changes how a production array is polled, so read the row before you act on it and
expect a gap in collection while it runs.

The extracted schema records **no required right** on any of these seven verbs, and none of
the SRM entities declares access control. That is not the same as "anyone may call them", it
means the rendered schema page did not carry the information. Verify with a low-privilege
account, or ask your own server:

```sql
SELECT EntityName, VerbName, Position, Name, Type, IsOptional
FROM Metadata.VerbArgument
WHERE EntityName LIKE 'Orion.SRM.%'
ORDER BY EntityName, VerbName, Position
```

Note also what is **not** here. SRM's monitored objects inherit `UnManaged`,
`UnManageFrom` and `UnManageUntil` from `System.ManagedEntity`, so you can filter on them,
but none of them publishes `Unmanage` or `Remanage` verbs the way `Orion.Nodes`,
`Orion.Volumes` and `Orion.NPM.Interfaces` do. See
[../swis/verb-catalog.md](../swis/verb-catalog.md) for the verbs that do exist.

## Worked queries

Every query below has been validated against the 2026.2 schema with
`tools/validate_swql.py`.

### Array capacity and headroom

The everyday inventory question, with both capacity families side by side so nobody
mistakes raw for usable, and with the platform's own runout forecast turned into a number of
days.

```sql
SELECT
    sa.Name AS ArrayName,
    sa.Manufacturer,
    sa.Model,
    si.StatusName,
    sa.CapacityRawTotal,
    sa.CapacityUserTotal,
    sa.CapacityUserUsed,
    sa.CapacityUserUsedPercentage,
    sa.CapacityUserFree,
    sa.DataReduction,
    sa.CapacityRunoutDate,
    DayDiff(GetDate(), sa.CapacityRunoutDate) AS DaysOfHeadroom
FROM Orion.SRM.StorageArrays sa
INNER JOIN Orion.StatusInfo si ON si.StatusId = sa.Status
WHERE sa.UnManaged = FALSE
ORDER BY sa.CapacityUserUsedPercentage DESC
```

`DayDiff(a, b)` returns how many days `b` is later than `a`, so putting `GetDate()` first
gives days remaining and a negative number means the forecast date has already passed.
Filtering `UnManaged = FALSE` keeps arrays that are in a maintenance window out of a report
about real headroom.

### Pools that have promised more than they hold

Oversubscription is the failure mode that surprises people, because every individual LUN
looks fine right up until the pool underneath runs out.

```sql
SELECT
    p.StorageArray.Name AS ArrayName,
    p.Name AS PoolName,
    p.RaidType,
    p.Thin,
    p.CapacityUserTotal,
    p.CapacityUserUsed,
    p.CapacityUserFreePercentage,
    p.CapacitySubscribed,
    p.CapacitySubscribedPercentage,
    p.CapacityOversubscribed,
    p.EstimatedFreeCapacity
FROM Orion.SRM.Pools p
WHERE p.CapacityOversubscribed > 0
  AND p.UnManaged = FALSE
ORDER BY p.CapacitySubscribedPercentage DESC
```

`p.StorageArray.Name` is a to-one navigation, so no explicit join is needed and the row count
does not change. Add `AND p.CapacityUserFreePercentage < 15` when you want only the pools
where oversubscription has become a live risk rather than a design choice.

### LUN performance against its own configured thresholds

Latency is the metric users feel. Reading the threshold through the navigation property shows
the number this particular LUN is judged against, which may be an override rather than the
global default.

```sql
SELECT TOP 25
    l.StorageArray.Name AS ArrayName,
    l.Pools.Name AS PoolName,
    l.Caption AS LUNName,
    l.IOLatencyTotal,
    l.IOLatencyRead,
    l.IOLatencyWrite,
    l.IOPSTotal,
    l.QueueLength,
    l.IOLatencyTotalThreshold.Level1Value AS WarningMs,
    l.IOLatencyTotalThreshold.Level2Value AS CriticalMs
FROM Orion.SRM.LUNs l
WHERE l.UnManaged = FALSE
  AND l.IOLatencyTotal IS NOT NULL
ORDER BY l.IOLatencyTotal DESC
```

### Which hosts are using this LUN

This is the question SRM exists to answer and it has three separate answers, because "using"
means three different things. Run all three when you are about to take a LUN offline.

**Servers with a filesystem on it.** These are hosts the platform monitors directly, and the
mapping comes from SRM's topology correlation.

```sql
SELECT
    l.Caption AS LUNName,
    l.StorageArray.Name AS ArrayName,
    v.Node.Caption AS ServerName,
    v.Caption AS MountPoint,
    v.VolumeSize,
    v.VolumePercentUsed
FROM Orion.Volumes v
INNER JOIN Orion.SRM.LUNs l ON l.LUNID = v.LUN.LUNID
WHERE l.LUNID = @lunId
ORDER BY v.Node.Caption, v.Caption
```

**Hypervisors with a path to it.** A VMware host attached to the LUN appears here even if no
virtual machine is currently using it, which is exactly what you want before an outage.

```sql
SELECT
    l.Caption AS LUNName,
    vl.CanonicalName,
    h.HostName,
    h.Node.Caption AS OrionNodeCaption,
    sp.Initiator,
    sp.Target,
    sp.Active
FROM Orion.SRM.LunsToVIMLuns map
INNER JOIN Orion.SRM.LUNs l ON l.LUNID = map.LunID
INNER JOIN Orion.VIM.Luns vl ON vl.LunID = map.VIMLunID
INNER JOIN Orion.VIM.LunStoragePaths sp ON sp.LunID = vl.LunID
INNER JOIN Orion.VIM.Hosts h ON h.HostID = sp.HostID
WHERE l.LUNID = @lunId
ORDER BY h.HostName, sp.Initiator
```

**Initiators the array will accept.** Masking is configuration rather than observation, so
this list includes hosts that were zoned years ago and never used the LUN. It is also the
only one of the three that works when the consuming host is not monitored at all.

```sql
SELECT
    l.Caption AS LUNName,
    m.InitiatorLunID,
    m.InitiatorEndpoint,
    m.TargetEndpoint,
    m.HostGroup,
    m.HostAlias
FROM Orion.SRM.LunMasking m
INNER JOIN Orion.SRM.LUNs l ON l.LUNID = m.LunID
WHERE l.LUNID = @lunId
ORDER BY m.HostGroup, m.InitiatorEndpoint
```

### How fast is this LUN filling

The forecast columns on the LUN give you a date. The statistics entity gives you the shape of
the curve that produced it, which is what you need when the forecast looks implausible.

```sql
SELECT
    cs.LUN.Caption AS LUNName,
    DateTrunc('day', cs.ObservationTimestamp) AS Day,
    AVG(cs.CapacityAllocated) AS AvgAllocated,
    AVG(cs.CapacityFree) AS AvgFree
FROM Orion.SRM.LUNCapacityStatistics cs
WHERE cs.ObservationTimestamp >= AddDay(-30, GetDate())
  AND cs.LUNID = @lunId
GROUP BY cs.LUN.Caption, DateTrunc('day', cs.ObservationTimestamp)
ORDER BY DateTrunc('day', cs.ObservationTimestamp)
```

Both bounds matter. Without the `ObservationTimestamp` filter this reads the whole retention
window, and without the `LUNID` filter it reads every LUN on every array. Together they turn
one of the largest tables in the database into a few hundred rows.

### The NAS chain, from vServer to share

The file-side equivalent of "which LUN is full": follow vServer to volume to share and show
where the quota is actually being consumed.

```sql
SELECT
    vs.StorageArray.Name AS ArrayName,
    vs.Caption AS VServerName,
    vol.Caption AS NasVolumeName,
    vol.CapacityTotal,
    vol.CapacityUsedPercentage,
    fs.Caption AS ShareName,
    fs.Path,
    fs.Quota,
    fs.Used,
    fs.Free
FROM Orion.SRM.FileShares fs
INNER JOIN Orion.SRM.Volumes vol ON vol.VolumeID = fs.VolumeID
INNER JOIN Orion.SRM.VServers vs ON vs.VServerID = vol.VServers.VServerID
WHERE fs.UnManaged = FALSE
ORDER BY fs.Used DESC
```

The two id spaces are joined explicitly here rather than by navigation, because
`Orion.SRM.FileShares.VolumeID` refers to `Orion.SRM.Volumes.VolumeID` and **not** to
`Orion.Volumes.VolumeID`. Writing the join against the wrong entity is the mistake this page
opened with, and it will not error.

### Physical disks that are not healthy

A failed drive is usually invisible from the host, and a consumed spare is invisible from
everywhere except here.

```sql
SELECT
    pd.StorageArray.Name AS ArrayName,
    pd.Name AS DiskName,
    pd.Vendor,
    pd.Model,
    pd.Type,
    pd.SerialNumber,
    pd.Capacity,
    pd.Spare,
    pd.OperStatusDescription,
    si.StatusName
FROM Orion.SRM.PhysicalDisks pd
INNER JOIN Orion.StatusInfo si ON si.StatusId = pd.Status
WHERE pd.Status <> 1
ORDER BY pd.StorageArray.Name, pd.Name
```

`OperStatusDescription` is the array's own words for what is wrong, which is usually more
specific than the platform status. Both are worth showing, because they can disagree.

### Controller balance on a dual-controller array

```sql
SELECT
    sc.StorageArrays.Name AS ArrayName,
    sc.Name AS ControllerName,
    sc.IOPSTotal,
    sc.IOPSDistribution,
    sc.BytesPSTotal,
    sc.BytesPSDistribution,
    sc.Utilization,
    sc.MemoryUtilization,
    sc.IOLatencyTotal
FROM Orion.SRM.StorageControllers sc
WHERE sc.UnManaged = FALSE
ORDER BY sc.StorageArrays.Name, sc.IOPSDistribution DESC
```

Note the navigation is `sc.StorageArrays`, plural, even though a controller belongs to one
array. The name comes from the relationship declaration and not from the cardinality, and the
singular form does not exist on this entity.

### Which arrays have stopped reporting

SRM polls capacity, performance, topology and controller data on four independent schedules,
so "the array is up" and "the numbers are current" are different questions.

```sql
SELECT
    sa.Name AS ArrayName,
    sa.PollerType,
    sa.Template.Template AS TemplateName,
    sa.Engine.ServerName AS PollingEngine,
    sa.LastSync,
    sa.LastCapacityPollTime,
    sa.LastPerformancePollTime,
    sa.LastTopologyPollTime,
    MinuteDiff(sa.LastPerformancePollTime, GetDate()) AS MinutesSincePerformancePoll
FROM Orion.SRM.StorageArrays sa
WHERE sa.UnManaged = FALSE
ORDER BY sa.LastPerformancePollTime
```

`sa.Engine` reaches `Orion.SRM.Engines`, SRM's own view of the polling engine table. It
declares 48 of the 51 columns `Orion.Engines` declares; the three missing are
`MasterEngineID`, `DetailsUrl` and `DisplayName`, and `DisplayName` remains queryable
because it is inherited from `System.Entity`. A single engine falling behind shows up here
as a group of arrays sharing one `PollingEngine` value and one stale timestamp.

### Storage events in the last week

`Orion.SRM.EventType` exists purely to filter the platform event stream down to SRM's own
event types, which is otherwise awkward because event types are integers.

```sql
SELECT TOP 100
    e.EventTime,
    e.Message,
    et.Name AS EventTypeName,
    e.NetObjectType,
    e.NetObjectID
FROM Orion.Events e
INNER JOIN Orion.SRM.EventType se ON se.EventTypeID = e.EventType
INNER JOIN Orion.EventTypes et ON et.EventType = e.EventType
WHERE e.EventTime > AddDay(-7, GetDate())
ORDER BY e.EventTime DESC
```

`NetObjectType` on the resulting rows will be one of SRM's prefixes, and
[../reference/netobject-types.md](../reference/netobject-types.md) turns those back into
entity names.

## Gotchas

**`Orion.SRM.Volumes` is not `Orion.Volumes`.** Different layer, different id space, same
column name for the key. This is the first section of this page for a reason. Cross the
boundary through `Orion.Volumes.LUN`, `Orion.Volumes.FileShare` or the `Rely*` dependency
edges, never by joining `VolumeID` to `VolumeID`.

**`Orion.SRM.FIleServerIdentification` does not exist.** The community workbook spells it
with a capital `I` in the middle of "File". The real entity is
`Orion.SRM.FileServerIdentification`. The misspelling is recorded in
[`data/reference/reconciliation.json`](../../data/reference/reconciliation.json) precisely
because it circulates.

**`Free` means two different things in one namespace.** On `Orion.SRM.LUNs` it is a
`System.Boolean`. On `Orion.SRM.FileShares` it is a `System.Int64` byte count. The byte count
of free space on a LUN is `CapacityFree`.

**Raw capacity and user capacity are not interchangeable.** `CapacityRawTotal` is what the
disks hold; `CapacityUserTotal` is what you can provision after RAID and reduction. On an
array with `TotalReduction` of 4, quoting the raw number as available space overstates it
enormously in one direction and quoting it as usable capacity understates it in the other.
Say which one you mean.

**Arrays have no latency column.** `Orion.SRM.StorageArrays` carries IOPS, throughput and
IO size but no `IOLatency*`. Latency exists on `Orion.SRM.LUNs`, `Orion.SRM.Volumes`,
`Orion.SRM.Pools` and `Orion.SRM.StorageControllers`. Aggregate up from one of those rather
than looking for a column that is not there.

**vServers have no latency either**, and no `CapacityTotal`. `Orion.SRM.VServers` has only
`CapacityAllocated` and `CapacitySubscribed`, because a vServer is an access layer rather
than a container of blocks.

**Four poll timestamps, not one.** `LastCapacityPollTime`, `LastPerformancePollTime`,
`LastTopologyPollTime` and `LastControllerPollTime` move independently, and `LastSync` is
different again. Checking only `LastSync` will miss an array whose performance collection has
been failing for a day.

**`EightyPercentUsageDate` and `NinetyPercentUsageDate` are strings.** They are typed
`System.String` on both `Orion.SRM.LUNs` and `Orion.SRM.Volumes`, so `DayDiff` and the `Add*`
functions do not apply. Use `CapacityRunoutDate`, which is a real `System.DateTime`, when you
need arithmetic.

**`Orion.SRM.StorageControllerPorts` has no `Caption`.** It is the only one of the nine
monitored object types without one. Use `Name` or the inherited `DisplayName`.

**Thresholds report zero properties under `show`.** All twenty columns are inherited from
`Orion.Thresholds`. Use `props`, which includes inherited members and marks where each came
from, or reach the threshold through its navigation property from the object it belongs to.

**Pools can nest, so summing them double counts.** Check
`Orion.SRM.PoolToPoolsMapping` for rows before writing `SUM(CapacityUserTotal)` across an
array's pools.

**SRM objects can be unmanaged but have no unmanage verb.** They inherit `UnManaged`,
`UnManageFrom` and `UnManageUntil` from `System.ManagedEntity`, and the web console can put
them in a maintenance window, but there is no `Orion.SRM.LUNs.Unmanage` to call. Filter on the
column; do not go looking for the verb.

**Account limitations silently filter results.** Two accounts running the same array report
legitimately get different rows, so an unexpectedly empty result is often a permissions
problem rather than a monitoring gap.

**The module has to be installed.** Every entity on this page disappears from a server
without Storage Resource Monitor, and a query against a missing entity fails by name rather
than returning nothing. Confirm before concluding anything:

```sql
SELECT COUNT(FullName) AS EntityCount
FROM Metadata.Entity
WHERE FullName LIKE 'Orion.SRM.%'
```

## See also

- [vman.md](vman.md) for the Virtualization Manager side of the LUN, NAS and datastore
  joins.
- [hardware-health.md](hardware-health.md) for the four `ForArray` entities SRM contributes
  to the hardware health namespace.
- [README.md](README.md) for the index of every module page.
- [../platform/modules.md](../platform/modules.md) for the whole namespace map.
- [../swql/joins-and-navigation.md](../swql/joins-and-navigation.md) for why a to-one
  navigation keeps the row count and a to-many navigation does not.
- [../swql/date-and-time.md](../swql/date-and-time.md) before combining `GetUtcDate()` with
  the `Add*` functions on a statistics query.
- [../swis/invoke-verbs.md](../swis/invoke-verbs.md) for the positional argument rules the
  `Add*` verbs depend on, including the single-array-argument trap.
- [../reference/netobject-types.md](../reference/netobject-types.md) for the SRM NetObject
  prefixes: `SMP` provider, `SMSA` storage array, `SMSP` pool, `SML` LUN, `SMV` NAS volume,
  `SMVS` vServer, `SMS` file share.
- [../reference/status-codes.md](../reference/status-codes.md) for what each `Status`
  integer means.
- [../reference/verb-index.md](../reference/verb-index.md) for every verb with its ordered
  parameters.
- [../../scripts/swql/12-udt-and-storage.swql](../../scripts/swql/12-udt-and-storage.swql)
  for more verified SRM sample queries.

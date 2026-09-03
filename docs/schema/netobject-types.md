# NetObject types and prefixes

A **NetObject** is Orion's short, type-tagged handle for one monitored object. It is a
prefix, a colon, and the object's primary key: node 42 is `N:42`, interface 7 is `I:7`,
application 91 is `AA:91`. Two different objects can share the number 42 and still be
told apart, because the prefix carries the type.

This matters because the prefix is not cosmetic. It is the value several verbs demand,
and passing a bare `42` where `N:42` is required is one of the most common automation
failures on the platform. SolarWinds' own documentation states the rule plainly for the
verb people call first:

> `netObjectId` - the identity of the node to unmanage. It looks like `N:123` where 123
> is the NodeID.
>
> [Unmanaging entities](https://solarwinds.github.io/OrionSDK/docs/unmanaging-entities/)

The same page for SAM says the application form "consists of 2 parts NetObjectType for
Application (`AA`) and ApplicationId", which is `AA:91`. Hardware health repeats it:
`EnableHardwareHealth` wants "the NodeID prefixed with `N:`".

## Where a NetObject string shows up

**Verb arguments.** Any verb parameter named `netObjectId` typed as a string takes the
prefixed form. `Orion.Nodes.Unmanage`, `Orion.Nodes.Remanage`, `Orion.Nodes.PollNow`,
`Orion.Nodes.PollStatusNow`, `Orion.Nodes.RediscoverNow`, `Orion.NPM.Interfaces.Unmanage`,
`Orion.NPM.Interfaces.SetBandwidth`, `Orion.Volumes.Unmanage` and `Orion.Volumes.Remanage`
are all in this group. Verify any specific one before calling it:

```bash
python3 tools/schema_query.py verb Orion.Nodes Unmanage
```

The distinction that trips people up is that some verbs declare `netObjectId` as a
**number**, not a string, and those want the bare integer. On `Orion.Nodes`,
`Unmanage`/`Remanage`/`PollNow` take `netObjectId: string` while `GetSupportedMetrics`,
`StartRealTimePolling` and `StopRealTimePolling` take `netObjectId: number`. The parameter
name is identical; only the type tells them apart. See
[../swis/invoke-verbs.md](../swis/invoke-verbs.md).

**Alert data.** `Orion.AlertObjects.EntityNetObjectId` stores the triggering object's
NetObject string, alongside `EntityUri`, `EntityType` and `EntityCaption`. That is the
value an alert action hands to a script.

**Event and audit records.** `Orion.MixedObjectType` declares `NetObjectID`
(`System.Int32`) and `NetObjectType` (`System.String`), and `Orion.Events` inherits both.
`Orion.AuditingEvents` declares its own `NetObjectID` and `NetObjectType`. In these
entities the prefix and the id are stored in **separate columns**, so you filter on
`NetObjectType` directly instead of parsing a combined string. Which values your server
actually stores in that column is a data question, so group by it once before writing a
filter, as in the audit query below.

**Web console URLs.** Detail pages address objects the same way, which is why
`DetailsUrl` on an entity such as `Orion.Nodes` resolves to a page for that specific
object.

## Building the string in SWQL

Fifteen entities in 2026.2 publish their own prefix as a queryable property,
`OrionIdPrefix`. Fourteen of the fifteen also carry `OrionIdColumn`, which names the key
column the prefix applies to; `Orion.Cloud.Aws.Instances` has the prefix but not the
column. The fifteen are `Orion.Nodes`, `Orion.NPM.Interfaces`, `Orion.Volumes`, `Orion.UDT.Port`,
`Orion.VIM.Clusters`, `Orion.VIM.DataCenters`, `Orion.VIM.Datastores`, `Orion.VIM.Hosts`,
`Orion.VIM.VCenters`, `Orion.VIM.VirtualMachines`, `Orion.Cloud.Aws.Instances`,
`Orion.Cloud.Aws.Volumes`, `Orion.Cloud.Azure.ApplicationGateway`,
`Orion.Cloud.Azure.Volumes` and `Orion.Cloud.Gcp.Volumes`. The published schema documents
the interface one as "Orion id prefix. Example:`'I:'`", so the stored value already
includes the colon.

Where that property exists, prefer it over hard-coding, because it is the server's own
answer:

```sql
SELECT TOP 10
    n.NodeID,
    n.Caption,
    n.OrionIdPrefix,
    n.OrionIdColumn,
    Concat(n.OrionIdPrefix, ToString(n.NodeID)) AS NetObjectId
FROM Orion.Nodes n
ORDER BY n.Caption
```

For the other 2000-odd entities there is no such property, and the table below is the
lookup.

Reading NetObject values back out of alert data needs no construction at all:

```sql
SELECT TOP 100
    ao.AlertObjectID,
    ao.EntityType,
    ao.EntityCaption,
    ao.EntityNetObjectId,
    ao.EntityUri,
    ao.RelatedNodeId,
    ao.RelatedNodeCaption
FROM Orion.AlertObjects ao
ORDER BY ao.EntityType, ao.EntityCaption
```

And auditing keeps the two halves apart, so grouping by type tells you which object kinds
people have been changing:

```sql
SELECT
    a.NetObjectType,
    COUNT(a.AuditEventID) AS AuditEvents
FROM Orion.AuditingEvents a
WHERE a.TimeLoggedUtc > ToUtc(AddDay(-30, GetDate()))
GROUP BY a.NetObjectType
ORDER BY COUNT(a.AuditEventID) DESC
```

`ToUtc(AddDay(-30, GetDate()))` rather than `AddDay(-30, GetUtcDate())` is deliberate.
`TimeLoggedUtc` is UTC, and wrapping `GetUtcDate()` in an `AddX` function produces a value
stamped with the SQL Server's local offset. See
[../swql/date-and-time.md](../swql/date-and-time.md).

## A NetObject is not a SWIS URI

They solve the same problem at different layers and are not interchangeable.

| | NetObject string | SWIS URI |
| --- | --- | --- |
| Looks like | `N:42` | `swis://server/Orion/Orion.Nodes/NodeID=42` |
| Scope | The Orion object model | The SWIS data layer |
| Used by | Verb `netObjectId` arguments, alert macros, console URLs | CRUD (`GET`/`POST`/`DELETE` on `/{uri}`), group member definitions, `BulkUpdate` |
| Covers | Only entities that have a prefix | Every entity with a key |
| Composite keys | Cannot express them | Expresses them, comma separated, as in `IPAM.Subnet/SubnetId=100,ParentId=2` |

Group membership makes the difference concrete: a static group member is defined by URI,
not by NetObject string, as in
`swis://my-orion-instance/Orion/Orion.Nodes/NodeID=42` from SolarWinds'
[Groups](https://solarwinds.github.io/OrionSDK/docs/groups/) documentation. Read
[../swis/uris.md](../swis/uris.md) for the URI form.

## The table

The full table (115 entries, sorted by module then entity) lives in
[../reference/netobject-types.md](../reference/netobject-types.md), generated straight from
`data/reference/netobject-types.json` by `make docs-reference` so it cannot drift from the
data the way a second hand-copied table would. A representative slice, enough to show the
shape of every column:

| Module | Entity | Display name | Prefix | Key properties | Parent entity |
| --- | --- | --- | --- | --- | --- |
| Core | `Orion.Nodes` | Node | `N` | `NodeID` | `Orion.Engines` |
| Core | `Orion.Volumes` | Volume | `V` | `VolumeID` | - |
| Core | `Orion.Events` | Core Events | - | `EventID` | - |
| NPM | `Orion.NPM.Interfaces` | Interface | `I` | `InterfaceID` | - |
| SAM | `Orion.APM.Application` | APM: Application | `AA` | `ApplicationID` | `Orion.Nodes` |
| NCM | `Cirrus.Nodes` | NCM Nodes | - | `NodeID`, `CoreNodeID`, `EngineID` | - |
| SRM | `Orion.SRM.LUNs` | Lun | `SML` | `LUNID` | `Orion.SRM.Pools` |
| VIM | `Orion.VIM.VirtualMachines` | Virtual Machine | `VVM` | `VirtualMachineID`, `HostID`, `NodeID` | - |
| UDT | `Orion.UDT.Port` | UDT Port | - | `NodeID`, `PortID`, `PortIndex` | `Orion.Nodes` |
| IPAM | `IPAM.IPNodeReport` | IPAM Nodes | `IPAMN` | `IPNodeId` | - |

**Module** is the workbook's own product label, not a namespace: NCM entities live in the
`Cirrus` namespace, and Storage Resource Monitor, Virtualization Manager and User Device
Tracker all sit inside `Orion` as `Orion.SRM.*`, `Orion.VIM.*` and `Orion.UDT.*`. See
[../platform/modules.md](../platform/modules.md).

A dash in the **Prefix** column means the workbook records no NetObject prefix for that
entity. Sixteen of the 115 entries are in that state, `Orion.Events`, `Orion.Engines`,
`Orion.AuditingEvents` and `Cirrus.Nodes` among them. Those objects are addressed by URI
or by key, not by a NetObject string.

Rows whose entity is marked **(superseded)** in the full table do not exist under that name
in the 2026.2 schema. The section after this one gives each one's replacement.

### Entries that no longer resolve in 2026.2

The prefix table comes from a community reference workbook that predates the current
schema, so twelve of its entity names have since been renamed or removed. The workbook is
still the only consolidated source for the prefixes themselves, which is why it is carried
here rather than discarded, but every name in it is checked against the published entity
list on each build. The findings are recorded in
[`data/reference/reconciliation.json`](../../data/reference/reconciliation.json).

| Workbook entity | Prefix | Status in 2026.2 |
| --- | --- | --- |
| `Orion.F5.Device` | `F5` | Renamed to `Orion.F5.System.Device` |
| `Orion.F5.Nodes` | `FN` | No successor identified |
| `Orion.F5.Pools` | `FP` | Two candidates: `Orion.F5.GTM.Pool` and `Orion.F5.LTM.Pool` |
| `Orion.F5.VirtualServers` | `FVS` | Three candidates: `Orion.F5.GTM.VirtualServer`, `Orion.F5.LTM.VirtualServer`, `Orion.F5.Map.VirtualServer` |
| `Orion.NPM.UCSBlades` | `UCSB` | Renamed to `Orion.UCS.Blades` |
| `Orion.NPM.UCSChassis` | `NCH` | Two candidates: `Orion.UCS.Chassis` and `Orion.HardwareHealth.HardwareInfoForUCSChassis` |
| `Orion.NPM.UCSFabrics` | `UCSF` | Renamed to `Orion.UCS.Fabrics` |
| `Orion.NPM.UCSFans` | `UCSFAN` | No successor identified |
| `Orion.NPM.UCSManagers` | `UCSM` | No successor identified |
| `Orion.NPM.UCSPSUs` | `UCSPSU` | No successor identified |
| `Orion.SRM.FIleServerIdentification` | - | Renamed to `Orion.SRM.FileServerIdentification` |
| `Orion.VIM.LUNs` | - | Renamed to `Orion.VIM.Luns` |

Two of these are pure capitalisation changes that look like nothing and fail like
everything: `Orion.SRM.FIleServerIdentification` has a capital `I` where the current name
has a lowercase `l`, and `Orion.VIM.LUNs` became `Orion.VIM.Luns`. Entity names are matched
exactly by SWIS, so both spellings fail on a live server.

Where a row above lists more than one candidate, the reconciliation could not pick a single
successor and neither can this page: the workbook records one old name and one prefix, and
2026.2 spreads that name across several entities. Pick the one holding the data you
actually want, and confirm it exists on your server before writing a report against it.

Whether a replacement exists at all also depends on licensing. The entries with no
successor may be genuinely removed, or may simply be absent from the published schema
because that module is not part of the documented build. Which of the two applies
cannot be verified from the schema alone, so ask your own server before concluding
they are gone:

```sql
SELECT FullName, BaseType, CanCreate, CanInvoke
FROM Metadata.Entity
WHERE FullName LIKE '%UCS%'
ORDER BY FullName
```

### Other places the workbook and the schema disagree

Six more cells in the table above name a property that the 2026.2 schema does not have
under that spelling. They are listed here rather than silently corrected, because the
workbook is the source for the prefixes and its other columns should be treated as hints:

| Cell | Workbook value | 2026.2 schema |
| --- | --- | --- |
| `Orion.SRM.StorageArrays` key | `ArrayID` | `StorageArrayID` exists; `ArrayID` does not |
| `Orion.VIM.Hosts` key | `CluserID` | Misspelling of `ClusterID` |
| `Orion.VIM.Hosts` key | `DatacenterID` | The schema spells it `DataCenterID`, with a capital `C` |
| `Orion.AgentManagement.Agent` key | `PollingEngineID` | The schema spells it `PollingEngineId`, with a lowercase `d` |
| `Orion.APM.Application` caption column | `ApplicationName` | The entity has `Name` and `DisplayName` |
| `Orion.SRM.StorageArrays` caption column | `ArrayName` | The entity has `Name`, `Caption` and `DisplayName` |

The last two of the four key rows differ from the schema only in capitalisation. SWQL
identifiers are generally matched case-insensitively, so those two may well work on a live
server; the spelling in the right-hand column is the one the published schema carries, and
the one to fall back on if a query comes back complaining about an unknown column.

One parent-entity cell is stale in the same way the entity column is: the workbook records
`Orion.VIM.Datastores` as hanging off `Orion.VIM.LUNs`, which in 2026.2 is
`Orion.VIM.Luns`.

The caption column is a field the JSON carries but this table does not render; it is the
property a UI would use as the object's label. Read it from
[`data/reference/netobject-types.json`](../../data/reference/netobject-types.json) if you
need it.

One parent-entity cell, `Orion.DPI.Probes`, holds a free-text note rather than a list of
entity names. It is reproduced as-is.

## Confirming any of this on your own server

Your server is the authority for your version and your licensed modules. Key properties
come from `Metadata.Property`:

```sql
SELECT p.Entity.FullName AS EntityName, p.Name AS KeyProperty, p.Type
FROM Metadata.Property p
WHERE p.IsKey = TRUE AND p.Entity.FullName = 'Orion.NPM.Interfaces'
ORDER BY p.Name
```

And the entities that publish their own prefix:

```sql
SELECT p.Entity.FullName AS EntityName
FROM Metadata.Property p
WHERE p.Name = 'OrionIdPrefix'
ORDER BY p.Entity.FullName
```

More introspection patterns are in
[../swis/metadata-introspection.md](../swis/metadata-introspection.md).

## Related pages

- [key-entities.md](key-entities.md) for the entities behind the most-used prefixes.
- [status-codes.md](status-codes.md) for the other integer lookup you will need constantly.
- [../swis/invoke-verbs.md](../swis/invoke-verbs.md) for how `netObjectId` arguments go on
  the wire, and why argument order is the whole contract.
- [../swis/uris.md](../swis/uris.md) for the URI form and when to use it instead.
- [../reference/netobject-types.md](../reference/netobject-types.md) for the generated
  version of this table, rebuilt by `make docs-reference` on every data refresh.

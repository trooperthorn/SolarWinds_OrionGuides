# Module Map: Which Product Owns Which Entities

The platform is one installation with one database and one API, but the data model is
contributed by many products. When a query fails with an unknown entity error, the usual
cause is not a typo: it is that the module which defines that entity is not installed on
the server you are querying.

This page maps each module to the SWIS namespace or entity prefix it contributes, gives an
entity count for the 2026.2 schema, and provides a starter query per module so you can
tell in one call whether a module is present and populated.

## Read the prefixes literally, not as product names

The single most confusing thing about this schema is that entity prefixes are historical
engineering names, not marketing names. Nothing lines up the way you would expect:

- Server and Application Monitor entities are prefixed `Orion.APM.`, from the product's
  former name.
- Network Configuration Manager entities live under **two** prefixes, `Cirrus.` and
  `NCM.`.
- Virtualization Manager entities are prefixed `Orion.VIM.`, and there is no `Orion.VMAN.`
  namespace at all.
- VoIP monitoring entities are prefixed `Orion.IpSla.`.
- Web transaction monitoring entities are prefixed `Orion.SEUM.`.
- NetFlow Traffic Analyzer entities are prefixed `Orion.Netflow.`, with a lowercase `f`.

So do not derive an entity name from a product name. Look it up.

### About the module names in this page

The short module codes (NPM, SAM, NCM, NTA, SRM, VIM, IPAM, UDT, VNQM, WPM, DPA, QoE) are
verified: they come from the `module` field in
[`data/reference/netobject-types.json`](../../data/reference/netobject-types.json), which
maps entities to the module that owns them. The product names spelled out in full are
taken from SolarWinds' own SDK documentation where it names them (Network Performance
Monitor, Server and Application Monitor, Network Configuration Manager, NetFlow Traffic
Analyzer, IP Address Manager, Log Analyzer, and Virtualization Manager all appear there).
Where a full product name is given below for a module that the SDK docs only ever refer to
by its code, it is offered as orientation and is not carried in the schema data.

The entity counts are exact: they are the number of entities in the 2026.2 extraction whose
name equals the prefix or begins with the prefix plus a dot.

## The map

| Module | What it monitors | Entity prefix | Entities in 2026.2 |
|---|---|---|---|
| Platform core | Nodes, volumes, groups, alerts, events, credentials, pollers, engines | `Orion.` (direct children) | 243 |
| NPM (Network Performance Monitor) | Interfaces, wireless, routing, F5, fibre channel, NetPath | `Orion.NPM.` | 86 |
| SAM (Server and Application Monitor) | Applications, components, AppInsight for SQL/IIS/Exchange | `Orion.APM.` | 140 |
| NCM (Network Configuration Manager) | Device configs, compliance, config transfer, inventory | `Cirrus.` and `NCM.` | 57 + 72 |
| NTA (NetFlow Traffic Analyzer) | Flow records, applications, endpoints, CBQoS | `Orion.Netflow.` | 49 |
| SRM (Storage Resource Monitor) | Storage arrays, LUNs, pools, file shares, NAS volumes | `Orion.SRM.` | 135 |
| VMAN / VIM (Virtualization Manager) | vCenters, hosts, clusters, datastores, virtual machines | `Orion.VIM.` | 90 |
| IPAM (IP Address Manager) | Subnets, IP nodes, DHCP scopes, DNS zones | `IPAM.` | 77 |
| UDT (User Device Tracker) | Switch ports, endpoints, MAC/IP/user history, watch lists | `Orion.UDT.` | 85 |
| VNQM (VoIP and Network Quality Manager) | IP SLA operations, call managers, phones, call detail records | `Orion.IpSla.` | 140 |
| WPM (Web Performance Monitor) | Recorded transactions, steps, playback locations | `Orion.SEUM.` | 31 |
| DPA (Database Performance Analyzer) | Database instances, waits, blocking, expensive queries | `DPA.` and `Orion.DPA.` | 18 + 9 |
| Log Analyzer | Syslog, traps, log entries, processing rules | `Orion.OLM.` | 21 |
| Hardware Health | Fans, PSUs, temperature sensors on nodes | `Orion.HardwareHealth.` | 33 |
| QoE (Quality of Experience) | Deep packet inspection applications and probes | `Orion.DPI.` | 14 |
| Cortex | Newer polling and metrics pipeline | `Cortex.` | 69 |

Beyond that table the schema also carries namespaces for cloud monitoring
(`Orion.Cloud.`, 148 entities), agent management (`Orion.AgentManagement.`, 16), asset
inventory (`Orion.AssetInventory.`, 23), Server Configuration Monitor (`Orion.SCM.`, 23),
Patch Manager integration (`Orion.PM.`, 30), Access Rights Manager integration
(`Orion.ARM.`, 9), Security Event Manager integration (`Orion.SEM.`, 14), anomaly
detection (`Orion.AIIM.`, 16), and about seventy more smaller prefixes. To see the whole
list for yourself:

```bash
python3 tools/schema_query.py stats
python3 tools/schema_query.py find Orion.Cloud
```

## Platform core

Everything that exists regardless of which modules you licensed. `Orion.Nodes` is the
centre of gravity: 102 properties, 17 verbs, 135 outbound navigation properties and 26
inbound ones in 2026.2. Most module entities hang off it.

```sql
SELECT TOP 10 NodeID, Caption, IPAddress, Status, StatusDescription, EngineID
FROM Orion.Nodes
ORDER BY Caption
```

Other core entities you will use constantly: `Orion.Volumes`, `Orion.Groups` and
`Orion.ContainerMembers`, `Orion.Events`, `Orion.AuditingEvents`, `Orion.Credential`,
`Orion.Pollers`, `Orion.Engines`, and `Orion.AlertStatus`.

## NPM: Network Performance Monitor

Interfaces are the headline entity, but NPM contributes considerably more than that:
wireless (`Orion.NPM.WL.*` plus `Orion.Wireless.` and `Orion.WirelessHeatMap.`), routing
(`Orion.Routing.`), fibre channel (`Orion.NPM.FCPorts`, `Orion.NPM.FCUnits`,
`Orion.NPM.FCSensors`), EnergyWise (`Orion.NPM.EW.*`), F5 (`Orion.F5.`), and NetPath
(`Orion.NetPath.`).

```sql
SELECT TOP 10 i.InterfaceID,
       i.Node.Caption AS NodeName,
       i.Caption,
       i.Status,
       i.InPercentUtil,
       i.OutPercentUtil
FROM Orion.NPM.Interfaces i
ORDER BY i.Node.Caption, i.Caption
```

`Orion.NPM.Interfaces` and `Orion.Nodes` are joined by the `Orion.NodeHostsInterfaces`
relationship, and both directions are usable in SWQL: `Orion.Nodes.Interfaces` navigates
from node to interface, `Orion.NPM.Interfaces.Node` navigates back.

Custom (universal device) pollers are NPM's mechanism for monitoring arbitrary SNMP OIDs;
SolarWinds documents them at
[NPM Universal Device Pollers](https://solarwinds.github.io/OrionSDK/docs/network-performance-monitor/npm-universal-device-pollers/).

## SAM: Server and Application Monitor

`Orion.APM.` covers generic template-based application monitoring and the AppInsight
deep-dive monitors for SQL Server, IIS, and Exchange.

```sql
SELECT TOP 10 a.ApplicationID,
       a.Name,
       a.Node.Caption AS NodeName,
       a.Status,
       a.StatusDescription
FROM Orion.APM.Application a
ORDER BY a.Node.Caption, a.Name
```

Components hang off applications:

```sql
SELECT TOP 20 c.ComponentID,
       c.Application.Name AS ApplicationName,
       c.Name AS ComponentName,
       c.Status
FROM Orion.APM.Component c
ORDER BY c.Application.Name, c.Name
```

The AppInsight families are `Orion.APM.SqlServerApplication` and `Orion.APM.SqlDatabase`,
`Orion.APM.IIS.Site` and `Orion.APM.IIS.ApplicationPool`, and
`Orion.APM.Exchange.Application` with its database and mailbox entities. SolarWinds
documents the template model at
[SAM Application Monitoring Templates](https://solarwinds.github.io/OrionSDK/docs/server-and-application-monitor/sam-application-monitoring-templates/)
and the AppInsight entities at
[SAM AppInsight Applications](https://solarwinds.github.io/OrionSDK/docs/sam-appinsight-applications/).

## NCM: Network Configuration Manager

NCM is the one module with two live namespaces, and knowing which to use matters.
`Cirrus.` is the original namespace and still holds the entities with the verbs on them:
`Cirrus.Nodes` alone declares 25 verbs, and `Cirrus.Settings` declares 20. `NCM.` is the
newer namespace and largely provides read-only inventory and reporting views, often
mirroring a `Cirrus.` entity with an extra property or two.

```sql
SELECT TOP 10 n.NodeID, n.NodeCaption, n.AgentIP, n.SysName, n.LastInventory
FROM Cirrus.Nodes n
ORDER BY n.NodeCaption
```

Downloaded configurations:

```sql
SELECT TOP 10 ConfigID, NodeID, ConfigType, ConfigTitle, DownloadTime
FROM NCM.ConfigArchive
ORDER BY DownloadTime DESC
```

The single most important thing to know about NCM is that its node IDs are not the
platform's node IDs, and they are not even the same data type. `Cirrus.Nodes.NodeID` is a
`System.Guid`, documented as "Unique identifier and primary key of the NCM node".
`Orion.Nodes.NodeID` is a `System.Int32`. The bridge is `Cirrus.Nodes.CoreNodeID`, a
`System.Int32` documented as "Orion node ID".

There is no navigation property between the two entities, so you join on that column
explicitly:

```sql
SELECT TOP 10 n.Caption AS OrionNode,
       n.IPAddress,
       c.NodeID AS NcmNodeGuid,
       c.LastInventory
FROM Orion.Nodes n
JOIN Cirrus.Nodes c ON c.CoreNodeID = n.NodeID
ORDER BY n.Caption
```

Passing a `Cirrus.Nodes.NodeID` where an `Orion.Nodes.NodeID` is expected is the most
common NCM automation bug, and because one value is a GUID it usually fails loudly rather
than silently. Config transfer and search are documented at
[NCM Config Transfer](https://solarwinds.github.io/OrionSDK/docs/network-configuration-manager/ncm-config-transfer/)
and
[NCM Config Search](https://solarwinds.github.io/OrionSDK/docs/network-configuration-manager/ncm-config-search/).

## NTA: NetFlow Traffic Analyzer

`Orion.Netflow.Flows` is the raw flow record at the finest granularity available. Because
flows have a source and a destination, NTA also publishes non-directional views that
duplicate each flow so you can aggregate by an address or hostname regardless of which end
it appeared on: `Orion.Netflow.FlowsByIP`, `FlowsByHostname`, `FlowsByDomain`,
`FlowsByAS`, `FlowsByCountryCode`, `FlowsByInterface`.

```sql
SELECT TOP 10 f.Protocol.Name, SUM(f.Bytes) AS TotalBytes
FROM Orion.Netflow.Flows f
WHERE f.TimeStamp > '2014-01-01 00:00:00' AND f.TimeStamp <= '2014-01-01 01:00:00'
GROUP BY f.Protocol.Name
ORDER BY SUM(f.Bytes) DESC
```

That example is SolarWinds' own, from
[NTA 4.0 Entity Model](https://solarwinds.github.io/OrionSDK/docs/netflow-traffic-analyzer/nta-4-0-entity-model/);
change the timestamps to a window that exists in your data. Always constrain the time
range. Flow tables are the largest in the database by a wide margin, and an unbounded
query against them is the fastest way to make yourself unpopular.

Which nodes are actually sending flows:

```sql
SELECT NetflowNodeSourceID, NodeID, EngineID, Enabled, LastTimeFlow
FROM Orion.Netflow.NodeSources
ORDER BY LastTimeFlow DESC
```

## SRM: Storage Resource Monitor

135 entities covering block and file storage. The ones you start from are
`Orion.SRM.StorageArrays`, `Orion.SRM.LUNs`, `Orion.SRM.Pools`, `Orion.SRM.Volumes` (NAS
volumes), `Orion.SRM.FileShares`, and `Orion.SRM.Providers`.

```sql
SELECT TOP 10 StorageArrayID, Name, Status, StatusDescription, Vendor, Model
FROM Orion.SRM.StorageArrays
ORDER BY Name
```

`Orion.SRM.LunsToVIMLuns` maps storage LUNs to the virtualization module's view of the
same LUNs, which is how you get from a slow VM to the array behind it.

## VMAN: Virtualization, under the VIM prefix

The SDK confirms the naming: Virtualization Manager (VMAN) "has fully transitioned to just
being an Orion module". Its entities use the `Orion.VIM.` prefix.

```sql
SELECT TOP 10 vm.VirtualMachineID,
       vm.Name,
       vm.Status,
       vm.Host.HostName AS HostName,
       vm.PowerState
FROM Orion.VIM.VirtualMachines vm
ORDER BY vm.Name
```

The hierarchy runs `Orion.VIM.VCenters` to `Orion.VIM.DataCenters` to
`Orion.VIM.Clusters` to `Orion.VIM.Hosts` to `Orion.VIM.VirtualMachines`, and each step has
a navigation property named after the child (`VCenters.DataCenters`,
`DataCenters.Clusters`, `Clusters.Hosts`, `Hosts.VirtualMachines`). Datastores hang off
both hosts and clusters, and here the casing bites: the entity is `Orion.VIM.Datastores`
with a lowercase `s`, but the navigation property on both parents is `DataStores` with a
capital `S`. Above all of them sits
`Orion.Virtualization.Instance`, an abstract base that `Orion.VIM.VirtualMachines`
inherits from, so a query against the base type returns instances from every supported
hypervisor.

Confirm the exact navigation property names before writing a join:

```bash
python3 tools/schema_query.py show Orion.VIM.VirtualMachines
python3 tools/schema_query.py path Orion.VIM.VirtualMachines Orion.VIM.Hosts
```

## IPAM: IP Address Manager

The only major module whose namespace is a bare top-level prefix rather than
`Orion.something`. 77 entities, split between address management (`IPAM.Subnet`,
`IPAM.IPNode`, `IPAM.IPInfo`, `IPAM.Conflict`), DHCP (`IPAM.DhcpScope`, `IPAM.DhcpLease`,
`IPAM.DhcpRange`), and DNS (`IPAM.DnsZone`, `IPAM.DnsView`).

```sql
SELECT TOP 10 SubnetId, Address, CIDR, FriendlyName, VLAN, PercentUsed, AvailableCount
FROM IPAM.Subnet
ORDER BY Address
```

IPAM has the longest and most version-dependent API history of any module. SolarWinds
publishes separate pages per generation (4.5.x, 4.6, 4.7, 4.9, 2019.4 and later, and the
Observability 2022.2 revision). Start from
[IPAM API](https://solarwinds.github.io/OrionSDK/docs/ip-address-manager/ipam-api/) and
pick the page matching your version, because the verb signatures genuinely changed between
them.

## UDT: User Device Tracker

Answers "where is this MAC address plugged in, and who was using it". The entities that
matter are `Orion.UDT.Port`, `Orion.UDT.Endpoint`, `Orion.UDT.User`,
`Orion.UDT.DNSName`, and the alert entities for rogue and moved addresses.

```sql
SELECT TOP 10 p.PortID,
       p.Node.Caption AS NodeName,
       p.Name,
       p.PortDescription,
       p.OperationalStatus,
       p.AdministrativeStatus,
       p.MACAddress
FROM Orion.UDT.Port p
ORDER BY p.Node.Caption, p.Name
```

## VNQM: VoIP and Network Quality Manager, under the IpSla prefix

140 entities, the largest module namespace after SAM. It covers two related things: IP SLA
operations configured on routers (`Orion.IpSla.Operations`, `Orion.IpSla.Sites`,
`Orion.IpSla.Paths`) and Cisco call manager monitoring (`Orion.IpSla.CCMMonitoring`,
`Orion.IpSla.CCMPhones`, `Orion.IpSla.CCMGateways`, `Orion.IpSla.VoipCallDetails`).

```sql
SELECT TOP 10 OperationInstanceID, OperationName, OperationTypeID, Status, StatusDescription
FROM Orion.IpSla.Operations
ORDER BY OperationName
```

## WPM: Web Performance Monitor, under the SEUM prefix

Records and replays browser transactions from playback locations. Note the terminology
mapping in the netobject reference: `Orion.SEUM.Agents` is displayed in the product as
"Location".

```sql
SELECT TOP 10 t.TransactionId, t.Name, t.Status, t.StatusDescription
FROM Orion.SEUM.Transactions t
ORDER BY t.Name
```

Steps within a transaction are `Orion.SEUM.TransactionSteps`, and individual HTTP requests
within a step are `Orion.SEUM.TransactionStepRequests`.

## DPA: Database Performance Analyzer

DPA is unusual because it is a separate product that integrates with the platform rather
than a module installed into it, and the schema reflects that with two namespaces:

- `Orion.DPA.` (9 entities) is the platform-side integration: `Orion.DPA.DatabaseInstance`
  is the monitored instance as the platform sees it, and the various
  `Orion.DPA.DatabaseInstanceApplication*` entities correlate DPA instances with SAM
  applications monitoring the same database.
- `DPA.` (18 entities) is a federated pass-through to the DPA server itself:
  `DPA.PerformanceOverview`, `DPA.WaitData`, `DPA.BlockingChain`, `DPA.Deadlock`,
  `DPA.SQLQueryInfo`, `DPA.ProblemSQLStatement`.

```sql
SELECT TOP 10 DatabaseInstanceID, Name, Status, StatusDescription
FROM Orion.DPA.DatabaseInstance
ORDER BY Name
```

Several `DPA.` entities require parameters in the `WHERE` clause and will fail without
them. `DPA.ResourceData`, for example, documents `DatabaseId` as required, and
`DPA.SQLQueryInfo` requires both `DatabaseId` and `Hash`. Check the entity summary before
querying:

```bash
python3 tools/schema_query.py show DPA.ResourceData
```

## Log Analyzer, under the OLM prefix

Syslog messages, SNMP traps, and log file entries land in `Orion.OLM.LogEntry`, with
`Orion.OLM.LogEntryType` naming the source type and `Orion.OLM.LogEntryLevel` the
severity.

```sql
SELECT logEntry.DateTime,
       logEntry.Level,
       logEntry.LogMessageSource.IPAddress,
       logEntry.LogMessageSource.Caption AS NodeName,
       logEntry.LogType.Type AS SourceType,
       logEntry.Message
FROM Orion.OLM.LogEntry AS logEntry
WHERE logEntry.DateTime >= @startDate AND logEntry.DateTime <= @endDate
```

That query is adapted from SolarWinds'
[Exporting log events](https://solarwinds.github.io/OrionSDK/docs/log-analyzer/exporting-log-events/)
example. As with flows, always bound the date range, and pass the bounds in UTC.

## Hardware Health

Not a standalone product. The netobject reference attributes it to "NPM / SAM", meaning
its entities appear when either module is present. It adds sensor-level detail to nodes:
`Orion.HardwareHealth.HardwareInfo` for the node's hardware as a whole,
`Orion.HardwareHealth.HardwareItem` for individual sensors, and
`Orion.HardwareHealth.HardwareCategoryStatus` for rolled-up status per category.

```sql
SELECT TOP 20 h.ID,
       h.Node.Caption AS NodeName,
       h.Name,
       h.Status,
       h.Value,
       h.HardwareUnitDescription,
       h.StatusDescription
FROM Orion.HardwareHealth.HardwareItem h
ORDER BY h.Node.Caption, h.Name
```

Most of those properties are declared on the parent entity
`Orion.HardwareHealth.HardwareItemBase` and inherited, which is why
`show Orion.HardwareHealth.HardwareItem` lists only two of its own. Inherited properties
are queryable exactly like declared ones; use `props` rather than `show` when you want the
full picture:

```bash
python3 tools/schema_query.py props Orion.HardwareHealth.HardwareItem
```

The BMC sub-family (`Orion.HardwareHealth.BMC.*`) covers chassis, blades, racks, fans, and
power supplies polled through baseboard management controllers. SolarWinds documents the
module at
[Hardware Health](https://solarwinds.github.io/OrionSDK/docs/hardware-health/).

## Cortex and Cirrus: two names that are not modules

Two prefixes look like products but are not.

**`Cirrus.`** (57 entities) is NCM's original namespace, described above. The name is
historical; treat `Cirrus.*` as "NCM, the part with the verbs".

**`Cortex.`** (69 entities) is a newer internal data pipeline rather than a product you
buy. Almost all of it sits under `Cortex.Orion.`, and it mirrors familiar objects with a
metrics-oriented shape: `Cortex.Orion.Node`, `Cortex.Orion.Interface`,
`Cortex.Orion.Volume`, each with companion `.Metrics` and `.Statistics` entities such as
`Cortex.Orion.Interface.Metrics` (27 properties) and `Cortex.Orion.Node.HealthMetrics`. It
also carries newer integrations, including `Cortex.Orion.CiscoAci.*` and
`Cortex.Orion.NetMan.Firewalls.*`.

Do not reach for `Cortex.*` when a classic `Orion.*` entity will do. The classic entities
are the documented, stable surface; the Cortex namespace exists to serve newer features
and its shape is more likely to change between versions.

```bash
python3 tools/schema_query.py find Cortex
```

## Which modules are installed on this server

Rather than inferring from which queries succeed, ask directly:

```sql
SELECT Name, LicenseName, Version, Family, IsEval, IsExpired, DaysRemaining
FROM Orion.InstalledModule
ORDER BY Name
```

For the licensing view, including product versions as the licence system sees them:

```sql
SELECT LicenseName, ProductName, ProductVersion, LicenseType, LicenseExpiresOn, MaintenanceExpiresOn
FROM Orion.Licensing.Licenses
ORDER BY ProductName
```

`Orion.Licensing.Licenses` requires the `admin` right for both read and invoke, so a
limited account will get nothing back from it. `Orion.InstalledModule` declares no access
restrictions in the schema.

To check whether a specific entity exists on this server before you depend on it:

```sql
SELECT FullName, BaseType, CanCreate, CanInvoke, IsObsolete, ObsolescenceReason
FROM Metadata.Entity
WHERE FullName LIKE 'Orion.SRM.%'
ORDER BY FullName
```

`IsObsolete` and `ObsolescenceReason` are worth selecting. Some entities remain queryable
while being formally deprecated; `NCM.VulnerabilitiesAnnouncements`, for example, carries
the note that it "is obsolete and will be removed in a future version of the product".

## A caution about older entity lists

Entity lists that circulate in the community were often written against much older
versions, and some of the names in them no longer resolve. This repository tracks the
known discrepancies in
[`data/reference/reconciliation.json`](../../data/reference/reconciliation.json). Examples
that come up frequently:

| Name you may see | Status in 2026.2 | Likely current name |
|---|---|---|
| `Orion.F5.Device` | Not in the schema | `Orion.F5.System.Device` |
| `Orion.F5.Pools` | Not in the schema | `Orion.F5.LTM.Pool`, `Orion.F5.GTM.Pool` |
| `Orion.F5.VirtualServers` | Not in the schema | `Orion.F5.LTM.VirtualServer`, `Orion.F5.GTM.VirtualServer` |
| `Orion.NPM.UCSChassis` | Not in the schema | `Orion.UCS.Chassis` |
| `Orion.NPM.UCSBlades` | Not in the schema | `Orion.UCS.Blades` |
| `Orion.VIM.LUNs` | Not in the schema | `Orion.VIM.Luns` (note the casing) |
| `Orion.SRM.FIleServerIdentification` | Not in the schema | `Orion.SRM.FileServerIdentification` |

The replacements are the best matches found in the 2026.2 schema and should be confirmed
on your own server with `Metadata.Entity` before you rely on them.
[versions-and-naming.md](versions-and-naming.md) explains why this drift happens and how
to write queries that survive it.

## Next

- [architecture.md](architecture.md) for how these modules are polled and by which server.
- [versions-and-naming.md](versions-and-naming.md) for version numbering and the naming
  history.

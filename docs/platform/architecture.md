# Deployment Architecture

A SolarWinds deployment is a small distributed system, not a single application. To
automate it well you need to know which machine does what, because the answer determines
where a monitoring job actually runs, which server you point an API client at, and what
happens during a failover.

This page describes the moving parts and then gives you runnable SWQL for inspecting each
one on your own server. Every entity and property named here was verified against the
extracted 2026.2 schema in [`data/schema/2026.2/`](../../data/schema/2026.2/).

## The parts

```text
                       ┌──────────────────────────┐
   browsers, API  ───▶  │  Web server(s)           │
   clients              │  Orion.Websites          │
                       └───────────┬──────────────┘
                                   │
                       ┌───────────▼──────────────┐
                       │  SWIS                    │   data access layer + SWQL
                       │  REST :17774             │   (query is read-only)
                       │  net.tcp :17777          │
                       └───────────┬──────────────┘
                                   │
   ┌───────────────────────────────┼───────────────────────────────┐
   │                               │                               │
┌──▼──────────────────┐   ┌────────▼─────────────┐   ┌─────────────▼────────┐
│ Primary server      │   │ Additional polling   │   │ SQL Server database  │
│ (main poller)       │   │ engines              │   │ (one, shared)        │
│ Orion.Engines       │   │ Orion.Engines        │   │ not exposed as an    │
│ Orion.OrionServers  │   │ Orion.OrionServers   │   │ entity; reached      │
└──┬──────────────────┘   └────────┬─────────────┘   │ through SWIS         │
   │                               │                 └──────────────────────┘
   │  polling jobs                 │  polling jobs
   ▼                               ▼
 monitored devices              monitored devices
```

High Availability pools (`Orion.HA.Pools`) sit alongside this picture: they pair a server
with a standby that can take over its role.

## SWIS, the data access layer

SWIS is the component that every supported integration talks to. SolarWinds describes it
in [About SWIS](https://solarwinds.github.io/OrionSDK/docs/about-swis/) as

> a data access layer for the Orion product family that provides a hybrid of
> object-oriented and relational features.

The reason to go through SWIS rather than opening a connection to SQL Server is spelled
out in that same document, and it is worth internalising because it is the difference
between an integration that survives an upgrade and one that does not:

- **Credentials.** Direct database access requires database credentials that a DBA has to
  create and manage. SWIS uses the same accounts you already manage in the web console, so
  access control stays in one place.
- **Account limitations.** Web console accounts can carry limitations restricting which
  nodes and interfaces a user may see. SWIS enforces those limitations on query results.
  Raw SQL does not, which means a direct-database integration can silently leak data that
  the equivalent SWIS query would have filtered.
- **Insulation from database schema changes.** SWIS maps entities onto database tables.
  SolarWinds can restructure the tables between releases while keeping the entity model
  backward compatible. Queries written against `Orion.Nodes` keep working; queries written
  against the underlying tables are on their own.
- **Higher-level operation.** The entity model is a type hierarchy, so tools can ask SWIS
  what kinds of objects exist rather than hard-coding a list.

The type hierarchy is real and useful. Every entity descends from `System.Entity`, and
`System.ManagedEntity` is the ancestor of everything with an externally determined up/down
status. Querying a base type returns rows from all its descendants:

```sql
SELECT TOP 10 DisplayName, Status, StatusDescription
FROM System.ManagedEntity
ORDER BY DisplayName
```

Neither `DisplayName` nor `Status` is declared on `System.ManagedEntity` itself.
`DisplayName` comes from `System.Entity` at the root, and `Status` from
`System.DashboardEntity` in between. Inherited properties are queryable exactly like
declared ones, which is why `show` (declared properties) and `props` (declared plus
inherited) give different answers for the same entity, and why `props` is what you want
when composing a query.

The schema summary for `Status` also tells you how to decode it: "for Orion.* entities,
you can query `Orion.StatusInfo` to see what the different numbers mean". This repository
carries the same mapping offline in
[`data/reference/status-codes.json`](../../data/reference/status-codes.json).

To see what descends from a base type in 2026.2 without a server:

```bash
python3 tools/schema_query.py children System.ManagedEntity
python3 tools/schema_query.py props System.ManagedEntity
```

### Read path and write path are different

The query interface is read-only. From
[About SWIS](https://solarwinds.github.io/OrionSDK/docs/about-swis/):

> The SWIS query interface is read-only and cannot be used to insert, update, or delete
> data.

Writes take one of two other routes:

1. **CRUD**, addressed by SWIS URI. `Create` returns the URI of the new entity; read,
   update, and delete take one or more URIs. Two things limit what you can do this way.
   First, SWIS defines no URI for an entity type without at least one key property, so
   those types cannot be used with CRUD at all
   ([SWIS URIs](https://solarwinds.github.io/OrionSDK/docs/uris/)). Second, an entity
   declares which operations it supports: 250 of the 2067 entities in 2026.2 declare
   `create`, and the rest do not.
2. **Invoke verbs**, which are named operations that an entity declares. 2026.2 exposes
   958 verbs, 794 of them with typed parameters. Verbs exist because some changes are not
   expressible as a row update. `Orion.AlertActive.Acknowledge(alertObjectIds, notes)`
   records who acknowledged an alert and when. `Orion.Nodes.Unmanage(netObjectId,
   unmanageTime, remanageTime, isRelative, allowOverlapping)` puts a node into maintenance
   mode for a window and requires the `allowUnmanage` right. `Orion.HA.Pools.Switchover`
   triggers a failover. None of those are expressible as a column assignment.

## Primary server, additional polling engines, additional web servers

`Orion.OrionServers` is the entity that enumerates the servers in a deployment. Its own
schema summary is:

> Represents Orion servers (MPE, APE, AW).

Those abbreviations line up with the three roles a server can play. The schema does not
expand them, but they correspond to the main polling engine, additional polling engines,
and additional web servers, and the SDK's own documentation uses the phrase "Additional
Polling Engines" for the middle one.

```sql
SELECT OrionServerID, HostName, FQDN, ServerType, Status, SWAVersion, SWAKeepAlive
FROM Orion.OrionServers
ORDER BY ServerType, HostName
```

`Orion.Engines` is the polling-engine view of the same deployment. Its summary reads
"This entity contains main poller and all additional pollers list." It carries 51
properties, including the load and health numbers you actually want:

```sql
SELECT EngineID,
       ServerName,
       IP,
       ServerType,
       EngineVersion,
       PackageName,
       Elements,
       Nodes,
       Interfaces,
       Volumes,
       PollingCompletion,
       MinutesSinceKeepAlive
FROM Orion.Engines
ORDER BY EngineID
```

Web console instances are separate again:

```sql
SELECT WebsiteID, ServerName, IPAddress, Port, Type, SSLEnabled, FQDN, ExternalUrl
FROM Orion.Websites
```

Per-engine configuration overrides live in a key/value entity hanging off the engine:

```sql
SELECT EngineID, PropertyName, PropertyType, PropertyValue
FROM Orion.EngineProperties
WHERE EngineID = 1
ORDER BY PropertyName
```

If your client needs to reach a specific server, `Orion.ReachabilityInfo` is a purpose-built
list of "host names and IP addresses of all polling engines", including which address is
preferred and which is a virtual (HA) address:

```sql
SELECT HostName, IP, EngineId, OrionServerId, IsMyOwn, IsPreferred, IsVirtual
FROM Orion.ReachabilityInfo
ORDER BY OrionServerId
```

## How nodes are assigned to polling engines

Assignment is static: every node carries an `EngineID` naming exactly one engine, and all
of that node's related monitoring work runs from that engine. One engine polls many nodes,
but a node is never split across engines. The SDK's
[Polling Engine Load Balancing](https://solarwinds.github.io/OrionSDK/docs/polling-engine-load-balancing/)
page states it plainly:

> Nodes are statically assigned to polling engines and all related monitoring jobs such as
> Interfaces, Applications, and Configs are run from the node's assigned polling engine.

This has a consequence people discover the hard way, and the same page warns about it:
moving a node to a different engine only works if the new engine can actually reach the
device. Different IP address spaces, firewall rules, or SNMP ACLs on the target will turn
a rebalance into a monitoring outage.

The schema gives you two directions to travel between nodes and engines, and both are
valid SWQL:

- `Orion.Nodes` has a navigation property `Engine` leading to `Orion.Engines`.
- `Orion.Engines` has a navigation property `AssignedNodes` leading to `Orion.Nodes`.

Both come from the same underlying relationship, `Orion.EngineHostsNodes`. Confirm it
yourself with:

```bash
python3 tools/schema_query.py path Orion.Nodes Orion.Engines
```

### Counting nodes per engine

The portable form, using an explicit join on `EngineID`:

```sql
SELECT e.EngineID,
       e.ServerName,
       e.ServerType,
       COUNT(n.NodeID) AS AssignedNodeCount
FROM Orion.Engines e
LEFT JOIN Orion.Nodes n ON n.EngineID = e.EngineID
GROUP BY e.EngineID, e.ServerName, e.ServerType
ORDER BY COUNT(n.NodeID) DESC
```

The shorter form, grouping on the navigation property:

```sql
SELECT n.Engine.EngineID AS EngineID,
       n.Engine.ServerName AS EngineName,
       COUNT(n.NodeID) AS AssignedNodeCount
FROM Orion.Nodes n
GROUP BY n.Engine.EngineID, n.Engine.ServerName
ORDER BY COUNT(n.NodeID) DESC
```

The second form is more concise but drops engines with zero nodes, because there is no row
in `Orion.Nodes` to group. Use the left join when you want every engine listed.

One trap worth flagging: `Orion.Engines` has a property literally named `Nodes`, of type
`System.Int32`. It is a stored counter, not a navigation property, so `e.Nodes` is a
number and `FROM Orion.Engines.Nodes` is not a thing. The navigation property is
`AssignedNodes`. When the stored counter and a live `COUNT()` disagree, trust the
`COUNT()`.

### Reassigning a node

Reassignment is an ordinary property update on the node, not a verb. From the SDK's
polling engine page:

```powershell
$swis = Connect-Swis   # connection options go here
$nodeIdToMove = 1234   # choose node somehow
$targetEngineId = 4    # choose an appropriate engine with spare capacity
$nodeUriToMove = Get-SwisData $swis "SELECT Uri FROM Orion.Nodes WHERE NodeID=@nodeId" @{nodeId = $nodeIdToMove}
Set-SwisObject $swis $nodeUriToMove @{EngineID = $targetEngineId}
```

Note the shape of it: you fetch the node's SWIS URI with a query, then write through the
CRUD interface addressed by that URI. That is the general pattern for every property
update in SWIS.

## The polling job engine

Polling work is scheduled and executed as jobs on the assigned engine. The job engine is a
service running on each engine, and it is not exposed as a SWIS entity: searching the
2026.2 schema for "JobEngine" turns up only `Cirrus.NCM_JobEngineNCMJobs`, an NCM job
queue, and nothing representing the engine itself. So you cannot query the scheduler
directly. What you can query are the two numbers it produces, and they answer two
different questions.

**Is this engine keeping up?** `PollingCompletion` on `Orion.Engines` is a percentage of
configured jobs completed on schedule. The SDK documentation says it should stay in the
high 90s and that anything less indicates a performance problem, while cautioning that the
number tells you a problem exists and not what caused it.

```sql
SELECT EngineID, ServerName, PollingCompletion
FROM Orion.Engines
ORDER BY PollingCompletion
```

**Is this engine within its license?** Polling engine licenses cover a polling rate
expressed as abstract "job weight", proportional to the number of monitored elements and
to how often they are polled. Exceed it and the platform stretches polling intervals across
the board to fit. The SDK's worked example: a licence allowing 1000 job weight against a
configuration worth 1500 multiplies every interval by 1.5, so a node configured for
two-minute polling is actually polled every three minutes. Nothing warns you at the node
level, which is why this is worth monitoring. `Orion.PollingUsage` reports it:

```sql
SELECT EngineID, ScaleFactor, CurrentUsage, IsExceeded
FROM Orion.PollingUsage
```

That entity can return several rows per engine, so to get one row each:

```sql
SELECT EngineID, MAX(CurrentUsage) AS CurrentUsage, MAX(IsExceeded) AS IsExceeded
FROM Orion.PollingUsage
GROUP BY EngineID
```

Both queries are taken from the SDK's
[Polling Engine Load Balancing](https://solarwinds.github.io/OrionSDK/docs/polling-engine-load-balancing/)
page, and both were verified against the 2026.2 schema: `Orion.PollingUsage` declares
exactly four properties, `EngineID`, `ScaleFactor`, `CurrentUsage`, and `IsExceeded`.

### What is actually being polled

Individual poller assignments live in `Orion.Pollers`, which links a poller type to a
specific network object:

```sql
SELECT PollerID, PollerType, NetObject, NetObjectType, NetObjectID, Enabled
FROM Orion.Pollers
WHERE NetObjectType = 'N' AND NetObjectID = 1
ORDER BY PollerType
```

`NetObjectType` is the short prefix for an object kind: `N` for a node, `I` for an
interface, `V` for a volume. The full mapping this repository uses is in
[`data/reference/netobject-types.json`](../../data/reference/netobject-types.json). The
catalogue of `PollerType` string values, more than a hundred of them with descriptions of
what each one collects, is published by SolarWinds at
[Poller Types](https://solarwinds.github.io/OrionSDK/docs/poller-types/).

### Automatic engine load balancing

The SDK's load balancing page describes rebalancing as the administrator's job. The 2026.2
schema also contains entities for an automated Engine Load Balancing (ELB) feature, which
records what it moved and lets you exclude nodes from being moved:

```sql
SELECT TOP 50 Id, NodeId, SourceEngineId, TargetEngineId, ReassignmentTimestamp
FROM Orion.ELB.NodeReassignments
ORDER BY ReassignmentTimestamp DESC
```

```sql
SELECT NodeId
FROM Orion.ELB.NodeExclusions
```

`Orion.ELB.NodeExclusions` is described in the schema as "Nodes that are excluded from
Engine Load Balancing" and requires the `manageNodes` right to modify.
`Orion.ELB.NodeReassignments` is "History of node reassignments performed by Engine Load
Balancing (ELB)". Whether ELB is switched on in your deployment is a per-pool setting; see
the `ElbEnabled` property and the `ElbEnable` and `ElbDisable` verbs on `Orion.HA.Pools`
below.

## The SQL Server database

There is exactly one database behind the whole deployment, shared by every server and
every module. It is not exposed as a SWIS entity, deliberately: the mapping layer between
entities and tables is what lets SolarWinds change the tables between releases without
breaking your queries.

Practical implications for anyone writing automation:

- Query through SWIS, not through SQL Server. You get account limitations, a stable
  contract, and no database credentials to manage.
- Write through CRUD or verbs, never with `INSERT`/`UPDATE` against the tables. Direct
  writes bypass validation, auditing, and cache invalidation, and they are unsupported.
- If SWIS does not expose the data you want, the answer is not to go find the table. A
  database table is an implementation detail that can be restructured in the next release;
  if `Metadata.Entity` does not list an entity, that data is not part of the supported
  contract on that server, and code depending on it will break silently at some upgrade.

## High Availability pools

An HA pool pairs servers of the same type so one can take over from the other. The schema
summary for `Orion.HA.Pools` is "High Availability pools. Pool unites pool members of the
same type to provide high availability of Orion servers."

A pool has a type, a master member, a virtual host name and virtual IP that clients follow
across a failover, and DNS settings used to move that virtual host name. The virtual
address is the whole point: clients keep talking to one name, and the pool decides which
physical server is behind it.

`PoolType` is documented as "`0` - main poller, `1` - additional poller", but its declared
type is `System.String`, not an integer, so compare it as a string. `DnsType` is one of
`Microsoft`, `BIND`, or `Other`.

```sql
SELECT PoolId,
       DisplayName,
       PoolType,
       Enabled,
       CurrentStatus,
       PoolMasterMemberId,
       VirtualHostName,
       VirtualIpAddress,
       ElbEnabled,
       FailoverTimestamp
FROM Orion.HA.Pools
ORDER BY PoolId
```

Members are the individual servers, polling engines and backup servers alike:

```sql
SELECT m.PoolId,
       m.Pool.DisplayName AS PoolName,
       m.PoolMemberId,
       m.HostName,
       m.PoolMemberType,
       m.Status,
       m.LastHeartBeatTimestamp,
       m.ReasonOfFail,
       m.StatusMessage
FROM Orion.HA.PoolMembers m
ORDER BY m.PoolId, m.PoolMemberId
```

Two of those columns come with their value sets documented in the schema, which saves you
guessing:

- `PoolMemberType` is one of `MainPoller`, `MainPollerStandby`, `AdditionalPoller`,
  `AdditionalPollerStandby`. The pairing of each role with its standby is what makes a
  pool.
- `ReasonOfFail` records why the member last failed: `0` ResourceFail, `1` FacilityFail,
  `2` NotResponding, `3` SuicideRule, `4` Switchover, `5` Failback. Note that `4` and `5`
  are deliberate operations rather than faults, so a non-zero `ReasonOfFail` is not by
  itself a problem.

`Status`, `PreferredStatus`, and `RepairStatus` are integers whose value sets the schema
does not document. Read `StatusMessage` alongside them, since it carries the description of
the last failure in text.

Note the asymmetry in permissions: `Orion.HA.PoolMembers` is read-only, declaring only a
`read` operation. Everything you change about a pool goes through verbs on
`Orion.HA.Pools`, which declares 13 of them:

| Verb | Parameters | Purpose |
|---|---|---|
| `CreatePool` | `displayName`, `poolMembersIds`, `properties` | Creates a pool from members and resource parameters |
| `ValidateCreatePool` | `displayName`, `poolMembersIds`, `properties` | Validates without creating |
| `EditPool` | `poolId`, `displayName`, `properties` | Updates a pool |
| `ValidateEditPool` | `poolId`, `displayName`, `poolMembersIds`, `properties` | Validates without updating |
| `EnablePool` / `DisablePool` | `poolId` | Turns the pool on or off |
| `ElbEnable` / `ElbDisable` | `poolId` | Turns Engine Load Balancing on or off for the pool |
| `Switchover` | `poolId` | Manual failover |
| `SelectiveSwitchover` | `poolId`, `poolMemberIdsToFailover`, `poolMemberIdsToFailoverTo`, `failoverMessage` | Failover of chosen members |
| `RepairPool` | `poolId` | Repairs the pool |
| `DeletePool` | `poolId` | Deletes the pool |
| `DeleteStaleEngine` | `hostName` | Deletes an OrionServer and its pool member by host name |

All of them return
`SolarWinds.Orion.HighAvailability.Common.Model.OperationResult` and require the `admin`
right. A manual failover looks like this:

```powershell
Invoke-SwisVerb $swis 'Orion.HA.Pools' 'Switchover' @($poolId)
```

or over REST:

```bash
curl -k -u admin: \
  -X POST 'https://orion.example.com:17774/SolarWinds/InformationService/v3/Json/Invoke/Orion.HA.Pools/Switchover' \
  -H 'Content-Type: application/json' \
  -d '[1]'
```

The request body for an Invoke call is a positional JSON array matching the verb's
parameter order, which is why knowing the signature matters. Check any verb before calling
it:

```bash
python3 tools/schema_query.py verb Orion.HA.Pools SelectiveSwitchover
```

## Putting it together: a deployment health query

```sql
SELECT e.EngineID,
       e.ServerName,
       e.ServerType,
       e.EngineVersion,
       e.PollingCompletion,
       e.MinutesSinceKeepAlive,
       COUNT(n.NodeID) AS AssignedNodeCount
FROM Orion.Engines e
LEFT JOIN Orion.Nodes n ON n.EngineID = e.EngineID
GROUP BY e.EngineID, e.ServerName, e.ServerType, e.EngineVersion,
         e.PollingCompletion, e.MinutesSinceKeepAlive
ORDER BY e.EngineID
```

An engine whose `MinutesSinceKeepAlive` is climbing is not reporting in, whatever its
`PollingCompletion` last said. Pair this with the `Orion.PollingUsage` query above and you
have configured load, achieved load, and liveness for every engine in one pass.

## Next

- [modules.md](modules.md) for which product owns which entities.
- [versions-and-naming.md](versions-and-naming.md) for why the schema on your server may
  differ from the 2026.2 schema documented here.
- [../swis/connecting.md](../swis/connecting.md) to authenticate and run these queries.
- [../swis/crud.md](../swis/crud.md) for the write path used by the node reassignment
  example above.
- [../reference/status-codes.md](../reference/status-codes.md) to decode the `Status` and
  `CurrentStatus` integers returned by the queries on this page.
- [../../scripts/swql/09-engines-and-health.swql](../../scripts/swql/09-engines-and-health.swql)
  for the engine and licensing queries as a runnable file.

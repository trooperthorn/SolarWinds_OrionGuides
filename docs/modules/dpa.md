# DPA: Database Performance Analyzer

Database Performance Analyzer answers a question the rest of the platform cannot: not "is
the database server up" but "what is the database waiting on". Its unit of measurement is
wait time, the seconds a session spends blocked on something instead of doing work, sliced
by the SQL statement, the program, the machine, the database user, the file or the wait
type responsible. [SAM](sam.md) tells you a SQL Server instance is consuming 90% CPU. DPA
tells you which three queries account for it.

The reason this page reads differently from the other module pages is that **DPA is a
separate product, not a native module**. It has its own server, its own repository
database, its own web interface and its own release cycle, and it is *integrated with* the
platform rather than installed into it. Almost everything unusual about its schema follows
from that.

## Two namespaces, and the split is the important part

DPA contributes **27 entities** in 2026.2, divided unevenly across two namespaces, and the
division is not cosmetic.

| Namespace | Entities | What they are |
|---|---:|---|
| `Orion.DPA.` | 9 | Rows in the Orion database: the integrated DPA servers, the database instances the platform knows about, and the links joining those instances to nodes, applications and LUNs |
| `DPA.` | 18 | The DPA server's own data, reached through the integration |

Confirm the split yourself:

```bash
python3 tools/schema_query.py find DPA --properties
python3 tools/schema_query.py show Orion.DPA.DatabaseInstance
python3 tools/schema_query.py show Orion.DPA.DpaServer
```

```sql
SELECT FullName, BaseType, CanCreate, CanUpdate, CanDelete, CanInvoke, IsObsolete
FROM Metadata.Entity
WHERE FullName LIKE 'DPA.%' OR FullName LIKE 'Orion.DPA.%'
ORDER BY FullName
```

An empty result means DPA is not integrated with this installation. One further entity,
`Orion.Web.DPA.MenuBarChanges`, matches a keyword search for "DPA" but belongs to the web
layer rather than to the module, so it is not counted in the 27.

### What the schema says about where the data lives

The evidence for "some of this lives on the DPA server" is in the schema itself, in three
places.

**`Orion.DPA.DpaServer` describes a remote endpoint, not a local table.** Its 15 properties
include `JSwisAddress` ("Address of jSwis endpoint"), `JSwisObjectUriBase` ("Scheme and
hostname for URIs of entities from this DPA server"), `JSwisCredentialId` ("ID of
credentials to DPA jSwis"), `OrionHostname`, `DpaServiceUserAccountId`, `IntegrationStatus`
and `IntegrationStatusDescription`. Those are the fields of a connection, and
`JSwisObjectUriBase` says outright that entity URIs coming back from this server are
stamped with a different hostname.

**It navigates to `SWISf.RemoteSWIS`.** The navigation property is `RemoteSwis`, and the
target entity declares `SwisUri`, `Tag`, `Enabled` and `AlwaysIncludeEntities`. Its reverse
navigation is `SWISf.RemoteSWIS.DPAServer`.

**Its one verb is `RefreshSchema`**, whose summary in the schema is "Refresh federation
schema of for particular DPA Server" (the wording is SolarWinds', typo included). A
federation schema is what you refresh when the entity types you serve are defined
elsewhere.

Put together, that is the mechanism: your SWIS connection stays the same, and the `DPA.*`
entity types are served through a federated link to the DPA server's own SWIS. The
practical consequences are the ones to remember.

- `DPA.*` queries depend on the DPA server being reachable and the integration being
  healthy. Check `Orion.DPA.DpaServer.IntegrationStatusDescription` before concluding that
  a database has no data.
- After a DPA upgrade adds entity types or properties, the platform does not see them until
  the federation schema is refreshed. That is what `RefreshSchema` is for.
- `DPA.*` entities are read-only. None of the 18 declares create, update or delete.
- Several `DPA.*` entities behave like **parameterised requests rather than tables**, which
  is covered in [its own section](#the-dpa-entities-are-requests-not-tables) below and is
  the single most surprising thing about querying this module.

## `Orion.DPA.DatabaseInstance` is the hinge

Everything in DPA is anchored on one entity. `Orion.DPA.DatabaseInstance` is "Represents
single monitored database instance", it inherits
`System.Entity -> System.DashboardEntity -> System.ManagedEntity`, and it is **read-only:
its only declared operation is `read`, available to `everyone`**. You cannot add a
monitored database instance through SWIS. That happens in DPA.

Its NetObject prefix is **`DBI`**, keyed on `DatabaseInstanceID`, per
[`data/reference/netobject-types.json`](../../data/reference/netobject-types.json). It is
the only DPA entity in that reference at all.

### Two ids, and using the wrong one is the classic mistake

The entity carries both `DatabaseInstanceID` ("Unique identifier of the monitored
database") and `GlobalDatabaseInstanceID` ("Unique ID of database instance in Orion"). The
first is DPA's own id; the second is the platform's. Almost every `DPA.*` entity carries
the pair too, under slightly different names:

| Entity family | DPA-side column | Platform-side column |
|---|---|---|
| `Orion.DPA.DatabaseInstance` | `DatabaseInstanceID` | `GlobalDatabaseInstanceID` |
| `DPA.Deadlock`, `DPA.BlockingChain`, `DPA.BlockingOverview`, `DPA.PerformanceOverview`, `DPA.TrendDataDimension`, `DPA.DetailDataDimension`, `DPA.ProblemSummary`, `DPA.ProblemSQLStatement`, `DPA.ResourceData`, `DPA.ResourceDefinition`, `DPA.SQLQueryInfo`, `DPA.SqlServerQueryHash`, `DPA.DatabaseClient` | `DatabaseId` | `GlobalDatabaseId` |
| `DPA.WaitData`, `DPA.TimeSeriesData`, `DPA.TimeSeriesDefinition` | `DatabaseInstanceId` | `GlobalDatabaseInstanceID` |

Three different spellings for the same two concepts, so check the entity before writing the
join. When you join a `DPA.*` entity to `Orion.DPA.DatabaseInstance` by hand, join the
global ids: `di.GlobalDatabaseInstanceID = d.GlobalDatabaseId`. When you are passing an id
into a `WHERE` clause that DPA will act on, either works, but the global id is the one you
already have from a platform-side query.

Several property descriptions point at a property that is not there. They say "Reference to
`Orion.DPA.DatabaseInstance.Id`", and the column is actually called `DatabaseInstanceID`.
Two other references in the descriptions point at entities that do not exist here either:
there is no
`DPA.MonitorStatus` entity and no `DPA.AlarmLevel` entity in the 2026.2 schema, so
`MonitorStatus` and the `*AlarmLevel` integers have no lookup table to join to. Select
`MonitorStatusText` alongside `MonitorStatus` and read the text.

### The rest of its properties

**Identity and platform.** `Name`, `DisplayName` ("Name of DB instance with name of DPA
server monitoring this DB instance"), `Description` ("Type of DB Instance including
version"), `Host`, `IP`, `Port`, `Type` ("Possible values: Unknown, Oracle, SQL Server,
DB2, Sybase"), `Version`, `VersionSuffix`, `DefaultDatabase`, `OracleSID`, `ServiceName`,
`GroupId`.

**State.** `MonitorStatus` (0 to 7) and `MonitorStatusText`, `IsLicensed`,
`OverallAlarmLevel` ("Max from performance overview"), `Status` (`System.Int32`, so it
joins to [`Orion.StatusInfo`](../reference/status-codes.md) cleanly), `StatusDescription`,
`DetailsUrl`, `ModernIcon`, and the inherited `UnManaged`, `UnManageFrom` and
`UnManageUntil`.

Note that `Type` is a display string, not a code. `'SQL Server'` has a space in it.

## How an instance relates to a node, an application and a LUN

This is the part of DPA that most affects how you write queries, because a DPA database
instance is *not* automatically the same object as the node you already monitor. The
platform models the correspondence explicitly, with a separate link entity for each kind of
relationship and a `UserDefined` flag on each saying whether a human asserted it or the
integration inferred it.

### To a node

Two paths exist and they are not the same thing.

`Orion.DPA.DatabaseInstance.RelyNode` is a `System.Reliance` edge straight to
`Orion.Nodes`, with `Orion.Nodes.RelyDatabaseInstances` navigating back. A reliance
relationship is what drives dependency and rollup behaviour, so this is the edge to use
when you want "which node does this database sit on" in a single hop.

`Orion.DPA.DatabaseInstanceData` is the link row itself: `GlobalDatabaseInstanceID`,
`NodeID`, `UserDefined`, plus `CloudResourceId` and `CloudResourceType` ("SWIS entity type
of the cloud resource, e.g. `Orion.Cloud.Azure.SqlServer`"). It navigates to
`DatabaseInstance` and to `Node`, and from a node it is reached as
`Orion.Nodes.DatabaseInstanceData`. Unlike the instance itself this entity supports create,
read, update, delete and invoke under **`admin`**, which makes it the supported way to
assert a mapping the integration did not find. Those `CloudResource*` columns are why a
managed Azure SQL Server, which has no node, can still be tied to a DPA instance; see
[cloud.md](cloud.md).

### To a SAM application

`Orion.APM.Application` and `Orion.DPA.DatabaseInstance` can describe the same database
from two directions, and the schema models both directions plus the negative case.

| Entity | Meaning | Operations |
|---|---|---|
| `Orion.DPA.DatabaseInstanceApplicationRelationship` | The base link row. `GlobalDatabaseInstanceID`, `ApplicationID`, `RelationshipType`, `RelationshipTypeName`, `NoRelationship`, `UserDefined`, `CloudResourceId`, `CloudResourceType` | create, read, update, delete, invoke, requires `admin` |
| `Orion.DPA.DatabaseInstanceApplication` | "both are monitoring the same db instance". Declares no properties of its own, inherits all eight | No access control table published; creatable per the contract |
| `Orion.DPA.DatabaseInstanceClientApplication` | "application is client and database instance is server" | Same |
| `Orion.DPA.DatabaseInstanceApplicationNoRelationship` | "All removed relationships" | Same |

The three subtypes are filtered views over the same rows, which is why they declare zero
properties and inherit everything. Write to the base entity,
`Orion.DPA.DatabaseInstanceApplicationRelationship`, and read from whichever subtype
expresses the question. Those three are among the eleven entities in the whole schema whose
`/Create` path exists in the Swagger contract while the rendered schema publishes no access
control table for them, which is documented in
[using-the-data.md](../schema/using-the-data.md); resolve it against `Metadata.Entity` on
your own server before automating against them.

The navigation properties are worth writing out because none of them is guessable:

- `Orion.DPA.DatabaseInstance.ServerApplication` goes straight to `Orion.APM.Application`.
- `Orion.DPA.DatabaseInstance.RelyApplications` is the `System.Reliance` edge to the same
  entity, with `Orion.APM.Application.RelyDatabaseInstances` navigating back.
- `Orion.DPA.DatabaseInstance.ApplicationReference` and `.UsedByApplicationReference` reach
  the two link subtypes.
- From the application side: `Orion.APM.Application.DatabaseInstance`,
  `.DatabaseInstanceReference` and `.UsingDatabaseInstanceReference`.

`Orion.DPA.ServerApplicationTemplate` is a two-column list, `UniqueID` and `Name`, of the
SAM application templates that can legitimately be paired with a database instance. It is
what the console offers when you create the mapping by hand.

### To a LUN

`Orion.DPA.DatabaseInstanceLun` carries `LunId`, `GlobalDatabaseInstanceID` and
`UserDefined`, navigates to `Lun` and `DatabaseInstance`, and is reached from the instance
as `LunReference` or directly as `Lun`. From the storage side,
`Orion.SRM.LUNs.DatabaseInstance` and `Orion.SRM.LUNs.DatabaseInstanceReference` navigate
back. This is the join that turns "the database is waiting on IO" into "and here is the
array it is waiting on". See [srm.md](srm.md).

## The DPA entities are requests, not tables

This is the trap that costs the most time. Several `DPA.*` entities do not hold rows you
can page through. They take parameters from your `WHERE` clause, ask the DPA server, and
return the answer. The schema states this in the entity and property summaries, and the
giveaway is a property that is obviously an input rather than data.

| Entity | What the schema says |
|---|---|
| `DPA.ResourceData` | "It has single parameter that is required (`DatabaseId`) and two more that specifies what data will be returned". If both `ResourceName` and `CategoryName` are given you get one metric over a time frame; if either is missing you get the last data point for every metric. Its `TimeUnit` "will be ignored" when both bounds of `Time` are supplied |
| `DPA.SQLQueryInfo` | "`DatabaseId` and Hash are mandatory in where condition" |
| `DPA.SqlServerQueryHash` | "Both `DatabaseId` and Handle are mandatory in where condition" |
| `DPA.DetailDataDimension` | `TopN` "Limits the maximal number of categories to be retrieved", `IntervalUnit` and `TimesliceUnit` are enumerated granularity codes |
| `DPA.TrendDataDimension` | `MaxInstances` "Serves only to limit the maximal number of monitored database instances to be retrieved (top 5, 10, etc.)", `TimeUnit` restricted to hours (3) or days (4) |
| `DPA.BlockingOverview`, `DPA.BlockingChain` | `Time` is "Beginning and end of the interval ... End defaults to now" |

Three consequences follow.

**A `TOP n` is not a substitute for the entity's own limit.** `TopN` and `MaxInstances`
change what DPA computes; `TOP` only truncates what it already sent.

**A missing `WHERE` clause is an error, not an empty result.** Query
`DPA.SQLQueryInfo` without both `DatabaseId` and `SqlHash` and you are not asking for all
rows, you are making an incomplete request.

**`DPA.BlockingChain.ChainNumber` is not stable.** The schema is explicit: "This value is
generated with each request, so it is not guaranteed that the same blocker/blockee tree
will have the same `ChainNumber` in two SWQL results." Use it to group rows within one
result set and never store it.

### The wait-time entities

`DPA.TrendDataDimension` and `DPA.DetailDataDimension` both slice wait time by a dimension,
and both enumerate the dimensions in their schema descriptions: SQL (1), WAIT (2),
PROGRAM (3), DATABASE_INSTANCE (4), MACHINE (5), DB_USER (6), OS_USER (7), FILE (8),
DRIVE (9), PLAN (10), ACTION (11), MODULE (12), PARTITION (13), OBJECT (14),
PROCEDURE (15), and on the trend entity three additional virtual dimensions,
TOP_WAIT (18), TRENDING_UP_WAIT (19) and TRENDING_DOWN_WAIT (20). The column holding the
dimension is called `Id` on `DPA.TrendDataDimension` and `DimensionId` on
`DPA.DetailDataDimension`.

`DPA.WaitData` is the PerfStack-facing version, one row per dimension entry per interval,
with `PrimaryDimension`, `PrimaryDimensionValue`, `WaitTime`, `TotalWaitPercentage`,
`Executions`, `Rank`, and comma-separated context columns `WaitTypes`, `Databases`,
`DbUsers`, `Machines` and `Programs` that are populated only for the SQL and TOP_WAIT
dimensions. `PrimaryDimension` is a string whose valid values the schema does not
enumerate: it says only "Has to be equal to dimension name without non-alphanumeric
characters. See the names in NormalizedDataDimension class." That class is not in the
extracted data, so treat the exact strings as **unverified** and read them off your own
server before hard-coding one:

```sql
SELECT TOP 50
    w.PrimaryDimension,
    COUNT(w.PrimaryDimensionValue) AS Entries
FROM DPA.WaitData w
WHERE w.GlobalDatabaseInstanceID = @globalDatabaseId
  AND w.Time >= @startUtc
  AND w.Time < @endUtc
GROUP BY w.PrimaryDimension
```

`DPA.TimeSeriesData` is the only DPA entity inheriting from `System.StatisticsEntity`, so
it is the one with `ObservationTimestamp`, `ObservationFrequency` and `Weight` available.
`DPA.TimeSeriesDefinition` is its catalogue: `CategoryName`, `CategoryDisplayName`,
`MetricName`, `MinValue`, `MaxValue`, `DefaultAggregation`, `Units`, `ChartType` ("Gauge" =
sparklines, "Bar" = bars, "Stacked" = stacked) and `Subtitle`. Read the definition entity
first to learn which `CategoryName` and `MetricName` pairs exist for a given instance,
because those two strings are required inputs to the data entity.

### Blocking, deadlocks and advice

`DPA.BlockingOverview` is the per-time-slice summary: `BlockingSessions`,
`BlockedSessions`, `TotalTimeBlocking`, `TotalTimeBlocked`, with `TimesliceUnit`
controlling the granularity.

`DPA.BlockingChain` is the tree behind it, "as in the Blockers tab in the UI": `SessionId`,
`BlockedBySession` (null on the root blocker), `WaitTimeSecs` (zero on the root, because
the root is not blocked by itself) and `ChainNumber` grouping one tree.

`DPA.Deadlock` is a flat list with `DeadlockId`, `EventDate`, `VictimImpact` ("Time impact
on queries"), `SessionCount`, `Program`, `Machine`, `User`, `Database` and `Object`. It
declares **no navigation properties at all**, so joining it to the instance is manual. Its
`Machine` column carries the summary "ID of Deadlock", which is a copy-paste error in the
schema documentation; the column name is the reliable guide.

`DPA.ProblemSummary` and `DPA.ProblemSQLStatement` are the Advisors output.
`DPA.ProblemSummary` has `ProblemId`, `AnalysisId`, `Category` ("Currently SQL only"),
`AlarmLevel`, `Score`, `Item`, `ItemDescription`, `Summary`, and `RunTime`, `StartTime`
("Default is 30 days ago") and `EndTime` ("Default is the current time").
`DPA.ProblemSQLStatement` joins to it on `ProblemId` and adds `SqlHash`, `SqlText`,
`TotalSqlWaitTime` and `PercentOfTotalDatabaseWaitTime`.

`DPA.ExpertAdviceInfo` maps a wait type to HTML advice: `WaitId` ("Name of the wait type as
is displayed in the UI, eg. 'CPU/Memory'") and `AdviceInfo`. `DPA.DatabaseClient` maps a
client machine `Address` to a database instance over a time window.

## Verbs

DPA publishes exactly **one verb** in 2026.2, and it is an integration control rather than
a monitoring action. Arguments are positional, as everywhere in SWIS.

| Entity | Verb | Parameters, in order | Returns |
|---|---|---|---|
| `Orion.DPA.DpaServer` | `RefreshSchema` | `dpaServerId` | boolean |

```powershell
$swis = Connect-Swis -Hostname orion.example.com -Credential $cred

$servers = Get-SwisData $swis @"
SELECT DpaServerId, DisplayName, IntegrationStatusDescription
FROM Orion.DPA.DpaServer
"@

foreach ($server in $servers) {
    $ok = Invoke-SwisVerb $swis Orion.DPA.DpaServer RefreshSchema @($server.DpaServerId)
    Write-Host "$($server.DisplayName): refresh returned $ok"
}
```

Run it after a DPA upgrade, or when a `DPA.*` entity that should exist is rejected as
unknown. See [../swis/invoke-verbs.md](../swis/invoke-verbs.md).

Everything else in DPA is either read-only or plain CRUD. Four entities accept writes, all
requiring **`admin`**:

| Entity | What creating a row means |
|---|---|
| `Orion.DPA.DpaServer` | Register a DPA server for integration |
| `Orion.DPA.DatabaseInstanceData` | Assert that a database instance runs on a given node |
| `Orion.DPA.DatabaseInstanceApplicationRelationship` | Assert a link between an instance and a SAM application |
| `Orion.DPA.DatabaseInstanceLun` | Assert that an instance's storage is a given LUN |

All three link entities carry `UserDefined`, and setting it to true is how you record that
the mapping is yours rather than the integration's:

```powershell
New-SwisObject $swis Orion.DPA.DatabaseInstanceData @{
    GlobalDatabaseInstanceID = $globalDatabaseInstanceId
    NodeID                   = $nodeId
    UserDefined              = $true
} | Out-Null
```

## Worked queries

Every query below has been validated against the 2026.2 schema with
`python3 tools/validate_swql.py`.

### 1. The database instance inventory, with node and DPA server

The one query to start from. It crosses all three of the module's structural boundaries:
`DpaServer` for which DPA server monitors the instance, `Data.Node` for which platform node
it maps to, and `Orion.StatusInfo` for a readable status. A null `OrionNodeCaption` is a
database instance DPA is monitoring that the platform has not tied to a node, which is
usually the thing worth fixing.

```sql
SELECT TOP 100
    di.DatabaseInstanceID,
    di.GlobalDatabaseInstanceID,
    di.DisplayName,
    di.Type,
    di.Version,
    di.Host,
    di.Port,
    di.IsLicensed,
    di.MonitorStatusText,
    st.StatusName,
    di.DpaServer.DisplayName AS DpaServerName,
    di.Data.Node.Caption AS OrionNodeCaption
FROM Orion.DPA.DatabaseInstance di
JOIN Orion.StatusInfo st ON st.StatusId = di.Status
WHERE di.UnManaged = FALSE
ORDER BY di.DisplayName
```

Filtering `UnManaged = FALSE` is the difference between "actually in trouble" and "in a
maintenance window", and it works here because `Orion.DPA.DatabaseInstance` inherits from
`System.ManagedEntity` even though it does not declare those columns itself.

### 2. Which databases are alarming, and on what

`DPA.PerformanceOverview` is the meter panel from the DPA home page, one row per instance,
with a separate alarm level per subsystem. Reading the six levels side by side is what tells
you whether the problem is the storage, the memory, or the queries.

```sql
SELECT TOP 50
    po.DatabaseInstance.DisplayName AS InstanceName,
    po.DatabaseInstance.Type AS Platform,
    po.OverallAlarmLevel,
    po.CPUAlarmLevel,
    po.MemoryAlarmLevel,
    po.DiskAlarmLevel,
    po.SessionAlarmLevel,
    po.QueriesAlarmLevel,
    po.WaitTimeAlarmLevel,
    po.WaitTimeCategory,
    po.WaitTimeSecs,
    po.WaitTimeEnd
FROM DPA.PerformanceOverview po
ORDER BY po.WaitTimeSecs DESC
```

`WaitTimeAlarmLevel` is documented as taking only Normal (2), Critical (5) or Unknown (3),
which is narrower than the other alarm columns. `WaitTimeCategory` runs -1 to 10 with
DOWN(-1) and IDLE(0) at the bottom; the schema description is truncated in the extracted
data, so the meaning of the upper values is **unverified** here. `WaitTimeSecs` is "Total
wait time today in seconds", which means this query ranks by today's accumulated wait and
will look different at 09:00 and at 17:00.

### 3. Deadlocks in a window, attributed to an instance

`DPA.Deadlock` declares no navigation properties, so the instance name has to come from an
explicit join on the global id. Always bound `EventDate`: this is event data and the
sensible default is a day or a shift, not everything DPA has retained.

```sql
SELECT TOP 100
    di.DisplayName AS InstanceName,
    d.EventDate,
    d.Database,
    d.Object,
    d.Program,
    d.Machine,
    d.User,
    d.SessionCount,
    d.VictimImpact
FROM DPA.Deadlock d
JOIN Orion.DPA.DatabaseInstance di ON di.GlobalDatabaseInstanceID = d.GlobalDatabaseId
WHERE d.EventDate >= @startUtc
  AND d.EventDate < @endUtc
ORDER BY d.VictimImpact DESC
```

Ordering by `VictimImpact` rather than by count puts the deadlock that actually cost time
at the top, which is usually not the most frequent one.

### 4. Blocking over a shift, for one instance

`DPA.BlockingOverview` needs an instance and a time window because the entity is a request.
`TotalTimeBlocked` and `TotalTimeBlocking` are different measurements and reading them
together separates "one session held a lock for an hour" from "fifty sessions each waited a
minute".

```sql
SELECT TOP 200
    bo.Time,
    bo.BlockingSessions,
    bo.BlockedSessions,
    bo.TotalTimeBlocking,
    bo.TotalTimeBlocked
FROM DPA.BlockingOverview bo
WHERE bo.GlobalDatabaseId = @globalDatabaseId
  AND bo.Time >= @startUtc
  AND bo.Time < @endUtc
ORDER BY bo.TotalTimeBlocked DESC
```

To go from a bad time slice to the sessions involved, run `DPA.BlockingChain` for the same
instance over a narrower `Time` range and follow `BlockedBySession` up to the row whose
`BlockedBySession` is null. That row is the root blocker.

### 5. Top wait-time contributors for an instance

The query the module exists for. `Rank` is already computed by DPA, so ordering by it
rather than by `WaitTime` gives you DPA's own ranking. `PrimaryDimension` is bound rather
than literal because the valid strings are not enumerated in the schema.

```sql
SELECT TOP 25
    w.Rank,
    w.PrimaryDimension,
    w.PrimaryDimensionValue,
    w.WaitTime,
    w.TotalWaitPercentage,
    w.Executions,
    w.WaitTypes,
    w.Databases,
    w.Programs,
    w.Text
FROM DPA.WaitData w
WHERE w.GlobalDatabaseInstanceID = @globalDatabaseId
  AND w.PrimaryDimension = @primaryDimension
  AND w.Time >= @startUtc
  AND w.Time < @endUtc
ORDER BY w.Rank
```

`Text` carries "first part of the SQL query" for the SQL and TOP_WAIT dimensions. For the
full statement, take the hash from `PrimaryDimensionValue` and query `DPA.SQLQueryInfo`
with both `DatabaseId` and `SqlHash` in the `WHERE` clause, which that entity requires.

### 6. Database instances paired with a SAM application

Where the two products overlap. A row here means the same database is being watched twice,
by DPA from the inside and by a SAM template from the outside, and the two views should
agree.

```sql
SELECT TOP 100
    di.DisplayName AS InstanceName,
    di.Type AS Platform,
    di.ServerApplication.Name AS SamApplicationName,
    di.ServerApplication.Node.Caption AS SamNodeCaption,
    di.ServerApplication.StatusDescription AS SamStatus
FROM Orion.DPA.DatabaseInstance di
WHERE di.ServerApplication.ApplicationID IS NOT NULL
ORDER BY di.DisplayName
```

For the raw link rows including the ones a human removed, read the base entity instead. A
`NoRelationship` of true is a pairing someone explicitly rejected, which is worth seeing
before you re-create it:

```sql
SELECT TOP 100
    r.GlobalDatabaseInstanceID,
    r.ApplicationID,
    r.RelationshipTypeName,
    r.UserDefined,
    r.NoRelationship,
    r.CloudResourceType
FROM Orion.DPA.DatabaseInstanceApplicationRelationship r
ORDER BY r.GlobalDatabaseInstanceID
```

### 7. Databases and the storage underneath them

```sql
SELECT TOP 100
    l.DatabaseInstance.DisplayName AS InstanceName,
    l.DatabaseInstance.Type AS Platform,
    l.Lun.Caption AS LunCaption,
    l.Lun.StorageArray.Name AS ArrayName,
    l.UserDefined
FROM Orion.DPA.DatabaseInstanceLun l
ORDER BY l.DatabaseInstance.DisplayName
```

### 8. Integration health

Run this before believing any `DPA.*` result. `IntegrationStatusDescription` and the remote
SWIS URI together tell you whether the federated link is up and where it points.

```sql
SELECT TOP 100
    s.DpaServerId,
    s.DisplayName,
    s.JSwisAddress,
    s.OrionHostname,
    s.IntegrationStatus,
    s.IntegrationStatusDescription,
    s.StatusDescription,
    s.ProductInfo.ProductVersion,
    s.ProductInfo.SwisSchemaVersion,
    s.RemoteSwis.SwisUri,
    s.RemoteSwis.Enabled
FROM Orion.DPA.DpaServer s
ORDER BY s.DisplayName
```

`DPA.ProductInfo` also exposes `HttpPort` and `HttpsPort` ("NULL if not enabled"), which is
how you learn which scheme the DPA web interface is answering on without leaving SWQL.

### 9. A metric time series for PerfStack-style charting

`DPA.TimeSeriesData` is the statistics entity, so it takes `ObservationTimestamp`
predicates like any other. Both `CategoryName` and `MetricName` are required inputs, and
`DPA.TimeSeriesDefinition` is where you find the legal pairs.

```sql
SELECT TOP 200
    t.ObservationTimestamp,
    t.CategoryName,
    t.MetricName,
    t.Value,
    t.Label,
    t.Rank
FROM DPA.TimeSeriesData t
WHERE t.GlobalDatabaseInstanceID = @globalDatabaseId
  AND t.CategoryName = @categoryName
  AND t.MetricName = @metricName
  AND t.ObservationTimestamp >= @startUtc
  AND t.ObservationTimestamp < @endUtc
ORDER BY t.ObservationTimestamp
```

Discover the pairs first:

```sql
SELECT TOP 200
    d.CategoryName,
    d.CategoryDisplayName,
    d.MetricName,
    d.Units,
    d.ChartType,
    d.DefaultAggregation,
    d.MinValue,
    d.MaxValue
FROM DPA.TimeSeriesDefinition d
WHERE d.GlobalDatabaseInstanceID = @globalDatabaseId
ORDER BY d.CategoryName, d.MetricName
```

### 10. Nodes that host a database instance

Starting from the node and walking down, which is the direction a node-centric report needs.

```sql
SELECT TOP 100
    n.Caption,
    n.IPAddress,
    n.RelyDatabaseInstances.DisplayName AS InstanceName,
    n.RelyDatabaseInstances.Type AS Platform,
    n.RelyDatabaseInstances.MonitorStatusText AS MonitorStatus,
    n.DatabaseInstanceData.UserDefined AS MappingIsUserDefined
FROM Orion.Nodes n
WHERE n.RelyDatabaseInstances.DatabaseInstanceID IS NOT NULL
ORDER BY n.Caption
```

### 11. The Advisors backlog, worst first

```sql
SELECT TOP 50
    ps.DatabaseInstance.DisplayName AS InstanceName,
    ps.ProblemId,
    ps.Category,
    ps.AlarmLevel,
    ps.Score,
    ps.ItemDescription,
    ps.Summary,
    ps.RunTime
FROM DPA.ProblemSummary ps
WHERE ps.StartTime >= @startUtc
ORDER BY ps.Score DESC
```

Join `DPA.ProblemSQLStatement` on `ProblemId` when you need the statement text and its
share of total wait:

```sql
SELECT TOP 50
    pq.DatabaseId,
    pq.ProblemId,
    pq.SqlHash,
    pq.SqlText,
    pq.TotalSqlWaitTime,
    pq.PercentOfTotalDatabaseWaitTime
FROM DPA.ProblemSQLStatement pq
WHERE pq.GlobalDatabaseId = @globalDatabaseId
ORDER BY pq.TotalSqlWaitTime DESC
```

## Gotchas

**You cannot create a monitored database instance through SWIS.**
`Orion.DPA.DatabaseInstance` declares `read` only. Adding a database to monitoring is a DPA
operation. What SWIS lets you create is the *links* between an instance and the platform
objects it corresponds to.

**Three spellings of the same two ids.** `DatabaseInstanceID` /
`GlobalDatabaseInstanceID` on the platform entity, `DatabaseId` / `GlobalDatabaseId` on most
`DPA.*` entities, `DatabaseInstanceId` / `GlobalDatabaseInstanceID` on `DPA.WaitData`,
`DPA.TimeSeriesData` and `DPA.TimeSeriesDefinition`. Look the entity up rather than
copying a column name from the query above it.

**Several `DPA.*` entities require `WHERE` clause inputs.** They are requests, not tables.
`DPA.ResourceData` needs `DatabaseId`; `DPA.SQLQueryInfo` needs `DatabaseId` and the hash;
`DPA.SqlServerQueryHash` needs `DatabaseId` and the handle. `TopN`, `MaxInstances`,
`TimeUnit`, `IntervalUnit` and `TimesliceUnit` are inputs that change what the server
computes, not columns you filter after the fact.

**`DPA.BlockingChain.ChainNumber` changes between requests.** Group by it inside one
result. Never persist it or join it across queries.

**`DPA.Deadlock` has no navigation properties.** Join it to
`Orion.DPA.DatabaseInstance` on `GlobalDatabaseId` yourself.

**A `DPA.*` failure can be an integration failure.** Because the `DPA.*` types are served
through a federated link, an unreachable or unhealthy DPA server does not look like an
empty table. Check `Orion.DPA.DpaServer.IntegrationStatusDescription` first, and refresh
the federation schema with `RefreshSchema` after a DPA version change.

**`Type` is a display string.** `'SQL Server'`, `'Oracle'`, `'DB2'`, `'Sybase'`,
`'Unknown'`. Comparing it to `'SQLServer'` or `'MSSQL'` silently matches nothing.

**Alarm levels have no lookup entity.** `OverallAlarmLevel` and the five per-subsystem
levels on `DPA.PerformanceOverview` are bare integers whose lookup table the schema
references but does not publish. `Orion.DPA.DatabaseInstance.Status` is different: it is a
normal platform status integer and joins to
[`Orion.StatusInfo`](../reference/status-codes.md).

**Account limitations filter silently.** As everywhere, two accounts running the same query
can legitimately get different rows. See [../platform/architecture.md](../platform/architecture.md).

## What is not verified here

| Claim | Status | How to check on your server |
|---|---|---|
| The `DPA.*` entity types are served from the DPA server rather than the Orion database | Strongly implied by `JSwisAddress`, `JSwisObjectUriBase`, the `SWISf.RemoteSWIS` navigation and the `RefreshSchema` summary, but not stated as such in the schema | `SELECT DpaServerId, JSwisAddress, JSwisObjectUriBase, IntegrationStatusDescription FROM Orion.DPA.DpaServer`, then compare `Uri` values returned by a `DPA.*` query against `JSwisObjectUriBase` |
| The valid strings for `DPA.WaitData.PrimaryDimension` | The schema points at a code class that is not in the extracted data | `SELECT TOP 50 PrimaryDimension, COUNT(PrimaryDimensionValue) AS Entries FROM DPA.WaitData WHERE GlobalDatabaseInstanceID = @id AND Time >= @start GROUP BY PrimaryDimension` |
| The meaning of `DPA.PerformanceOverview.WaitTimeCategory` values 1 to 10 | The description is truncated in the extracted data at "DOWN(-1), IDLE(0), LOW(1" | Read the full property summary from your own server: `SELECT Name, Type, Summary FROM Metadata.Property WHERE Entity.FullName = 'DPA.PerformanceOverview'` |
| The `MonitorStatus` values 0 to 7 | The description references a lookup entity the schema does not publish | Select `MonitorStatus` and `MonitorStatusText` together and build the mapping from your own data |
| The `RelationshipType` integers on `Orion.DPA.DatabaseInstanceApplicationRelationship` | Not enumerated | `SELECT RelationshipType, RelationshipTypeName, COUNT(ApplicationID) AS Links FROM Orion.DPA.DatabaseInstanceApplicationRelationship GROUP BY RelationshipType, RelationshipTypeName` |
| Whether the three `DatabaseInstanceApplication*` subtypes really accept `create` | Their `/Create` paths exist in the Swagger contract but the rendered schema publishes no access control table for them | `SELECT FullName, CanCreate, CanUpdate, CanDelete FROM Metadata.Entity WHERE FullName LIKE 'Orion.DPA.DatabaseInstanceApplication%'` |

There is no DPA page in SolarWinds' published OrionSDK documentation and no DPA sample
script in the SDK samples, so the schema, the Swagger contract and your own server are the
only sources. [`../../scripts/swql/08-schema-introspection.swql`](../../scripts/swql/08-schema-introspection.swql)
is the tool for the last of those.

## Related pages

- [README.md](README.md) for the module index and how to check what is installed.
- [sam.md](sam.md) for `Orion.APM.Application` and AppInsight for SQL, the other way the
  platform watches a database.
- [srm.md](srm.md) for `Orion.SRM.LUNs`, the storage a database instance sits on.
- [cloud.md](cloud.md) for the cloud database resources a DPA instance can be tied to
  through `CloudResourceId` and `CloudResourceType`.
- [../swis/invoke-verbs.md](../swis/invoke-verbs.md) for positional verb arguments.
- [../swis/crud.md](../swis/crud.md) for creating the link rows.
- [../schema/using-the-data.md](../schema/using-the-data.md) for the entities whose
  contract and schema disagree.
- [../swql/date-and-time.md](../swql/date-and-time.md) before writing the time windows these
  queries all need.
- [../reference/status-codes.md](../reference/status-codes.md) for the `Status` integers.

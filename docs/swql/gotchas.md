# SWQL gotchas

A SWQL error is cheap. The query fails, you read the message, you fix it. This page is about
the other category: queries that parse, run, return a tidy grid of numbers, and are wrong.
Those cost weeks, because nothing ever tells you.

Every entity, property, navigation and status value on this page was resolved against the
extracted 2026.2 schema in `data/schema/2026.2/` before it was written. Where something is
widely believed but could not be verified from the schema, the official docs or SolarWinds'
own samples, it is marked **unverified** and comes with a query you can run on your own
server to settle it.

- [1. The empty result set is usually a permissions answer](#1-the-empty-result-set-is-usually-a-permissions-answer)
- [2. Status is an integer, and the integer means different things on different entities](#2-status-is-an-integer-and-the-integer-means-different-things-on-different-entities)
- [3. Status versus PolledStatus on Orion.Nodes](#3-status-versus-polledstatus-on-orionnodes)
- [4. UTC, DATEADD and the timestamp that quietly shifts](#4-utc-dateadd-and-the-timestamp-that-quietly-shifts)
- [5. NULL, IsNull, and the rows that disappear instead of going null](#5-null-isnull-and-the-rows-that-disappear-instead-of-going-null)
- [6. To-many navigation multiplies rows and poisons aggregates](#6-to-many-navigation-multiplies-rows-and-poisons-aggregates)
- [7. Averaging statistics rows without Weight](#7-averaging-statistics-rows-without-weight)
- [8. Entities that look like the same thing and are not](#8-entities-that-look-like-the-same-thing-and-are-not)
- [9. Columns that look boolean and are not](#9-columns-that-look-boolean-and-are-not)
- [10. String comparison, collation and case](#10-string-comparison-collation-and-case)
- [11. The query interface cannot write, and some entities cannot be written at all](#11-the-query-interface-cannot-write-and-some-entities-cannot-be-written-at-all)
- [12. Port 17778 is deprecated](#12-port-17778-is-deprecated)
- [13. Entity names change between versions](#13-entity-names-change-between-versions)
- [14. Types change between versions too](#14-types-change-between-versions-too)
- [15. Legacy properties the schema tells you to ignore](#15-legacy-properties-the-schema-tells-you-to-ignore)
- [A ten-minute audit for a query you inherited](#a-ten-minute-audit-for-a-query-you-inherited)

## 1. The empty result set is usually a permissions answer

Start here, because it is the single most common wrong conclusion drawn from a SWQL result.

SWIS applies Orion account limitations to every query it serves. SolarWinds describes this as
a feature of going through SWIS rather than the database:

> Orion administrators can associate Orion accounts with limitations that restrict what nodes
> and interfaces users can access. SWIS respects these limitations when they provide
> information. For example, SWIS will only return nodes the user has permission to see when
> the user runs a query for nodes.
>
> [About SWIS](https://solarwinds.github.io/OrionSDK/docs/about-swis/)

The consequences are not obvious:

- **The same query text returns different rows for different accounts.** A report that works
  for you and is empty for the service account is not a broken report.
- **The filtering is invisible.** There is no flag on the response saying "14 rows were
  removed". A limited account sees a smaller world and no evidence that a larger one exists.
- **Aggregates are silently scoped.** `COUNT`, `SUM` and `AVG` run over the rows the caller is
  allowed to see. A "total node count" widget can legitimately disagree with the licensing
  page.
- **It is not only node queries.** SolarWinds' own wording is "restrict what nodes **and
  interfaces** users can access", and `Orion.LimitationTypes` enumerates the types on your
  server with an `EntityType` column, so a query that never mentions `Orion.Nodes` can still be
  filtered.

Before debugging the SWQL, rule this out. Run the query as an account with no limitations and
compare row counts. Then look at what limitations exist:

```sql
SELECT
    l.LimitationID,
    t.Name        AS LimitationType,
    l.Definition,
    l.WhereClause
FROM Orion.Limitations l
JOIN Orion.LimitationTypes t ON t.LimitationTypeID = l.LimitationTypeID
ORDER BY l.LimitationID
```

`Orion.Accounts` carries up to three limitation slots per account, so you can see which
account is affected by which:

```sql
SELECT
    a.AccountID,
    a.Enabled,
    a.LimitationID1,
    a.LimitationID2,
    a.LimitationID3,
    a.LastLogin
FROM Orion.Accounts a
WHERE a.LimitationID1 <> 0
   OR a.LimitationID2 <> 0
   OR a.LimitationID3 <> 0
ORDER BY a.AccountID
```

`Orion.LimitationTypes` carries an `IsSwisLimitation` (`System.Boolean`) column and an
`EntityType` (`System.String`) column. The schema publishes no summary for either, so what
exactly `IsSwisLimitation` gates is **unverified** here; the name and the surrounding entity
make it the first thing to look at when a limitation appears to affect the web console but not
an API query. List them and compare against observed behaviour on your server:

```sql
SELECT t.LimitationTypeID, t.Name, t.EntityType, t.IsSwisLimitation, t.IsGroupOfEntity
FROM Orion.LimitationTypes t
ORDER BY t.Name
```

There is a second, separate permission layer: **entity-level access control**. Reading
`Orion.Nodes` requires only `everyone`, but plenty of entities do not. `Orion.Engines` allows
`read` for `everyone` and restricts `create`, `update` and `delete` to `system`.
`Orion.NodesCustomProperties` allows `read` for `everyone`, `update` for `manageNodes`, and
`invoke` only for `admin`. `Cirrus.Nodes` is documented as needing "at least WebViewer NCM
role". Check before you blame the query:

```bash
python3 tools/schema_query.py show Orion.NodesCustomProperties
```

Related: [../swis/rest-api.md](../swis/rest-api.md#errors) for what an authorisation failure
looks like over HTTP, and [../platform/architecture.md](../platform/architecture.md) for where
SWIS sits.

## 2. Status is an integer, and the integer means different things on different entities

`Status` is declared on `System.DashboardEntity`, and its own schema summary is the warning:

> An int value denoting the up/down/warning/etc. status of this entity. The interpretation of
> this int will be application-dependent, but for `Orion.*` entities, you can query
> `Orion.StatusInfo` to see what the different numbers mean.

290 entities in 2026.2 declare a `Status` property of their own on top of that. Three separate
traps follow.

### 2.1 There is no such thing as "the status column"

A query result showing `Status` = 4 means "Shutdown" for an interface and nothing meaningful
for a node, because the [status code reference](../reference/status-codes.md) records 4, 5, 6,
7 and 8 as applying to network interfaces only. Never carry a hard-coded status integer from
one entity type to another.

### 2.2 The type is not consistent either

| Entity | `Status` type |
|:---|:---|
| `Orion.Nodes` | `System.Int32` |
| `Orion.NPM.Interfaces` | `System.Int32` |
| `Orion.Volumes` | `System.Int32` |
| `Cirrus.Nodes` | `System.Byte` |
| `Cirrus.NCM_NCMJobsView` | `System.Int32`, and the values are job states (0 Unknown, 1 Running now, 2 Disabled, 3 Scheduled for job engine), not up/down |

`Cirrus.NCM_NCMJobsView.Status` is the clearest case: the column is called `Status`, it is an
integer, and joining it to `Orion.StatusInfo` produces a table of complete nonsense that looks
entirely plausible.

### 2.3 Resolve status by joining, and note that Orion.Nodes has no StatusInfo navigation

`Orion.StatusInfo` is the lookup table: `StatusId`, `StatusName`, `ShortDescription`,
`Ranking`, `RollupType`, `Color`. Some entities have a declared navigation to it and some do
not. In 2026.2 the entities with a `StatusInfo` navigation property are
`Orion.NPM.Interfaces`, `Orion.Volumes`, `Orion.Cman.Container`, `Orion.DPA.DatabaseInstance`,
`Orion.APIPoller.ApiPoller` and five `Orion.VIM.*` entities. **`Orion.Nodes` is not one of
them.** It has 161 navigation properties and none of them is `StatusInfo`, so this fails:

```text
-- Wrong: Orion.Nodes has no StatusInfo navigation property.
SELECT n.Caption, n.StatusInfo.StatusName FROM Orion.Nodes n
```

Write the join out:

```sql
SELECT TOP 100
    n.Caption,
    n.Status,
    s.StatusName,
    s.ShortDescription
FROM Orion.Nodes n
JOIN Orion.StatusInfo s ON s.StatusId = n.Status
ORDER BY s.Ranking, n.Caption
```

For an interface the navigation exists, and it is shorter:

```sql
SELECT TOP 100
    i.Caption,
    i.Status,
    i.StatusInfo.StatusName AS StatusName
FROM Orion.NPM.Interfaces i
WHERE i.Status <> 1
ORDER BY i.Caption
```

### 2.4 Ranking is not severity, and lower is worse

`Orion.StatusInfo.Ranking` orders statuses for rollup, and **a lower rank is worse**. Down is
110, Warning is 220, Up is 500, Unknown is 495. Sorting `ORDER BY s.Ranking DESC` to get "worst
first" puts Dormant (560) and Expired (580) at the top and Down near the bottom. Sort
ascending.

### 2.5 Unmanaged and External are statuses, so "not Up" is not "broken"

Status 9 is Unmanaged, 11 is External, 26 is Monitoring Disabled and 27 is Disabled. A
dashboard filtering `WHERE Status <> 1` counts every maintenance window as an outage. Be
explicit about what you are excluding, and use the `UnManaged` boolean from
`System.ManagedEntity` rather than inferring it from the status integer:

```sql
SELECT TOP 100 n.Caption, n.Status, n.UnManaged, n.UnManageUntil
FROM Orion.Nodes n
WHERE n.Status NOT IN (1, 9, 11, 26, 27)
  AND n.UnManaged = FALSE
ORDER BY n.Caption
```

`Status` and `UnManaged` are independent columns fed from different places, so do not assume
one implies the other. Cross-tabulate them once on your own server and you will know for
certain how your platform version behaves:

```sql
SELECT
    n.Status,
    n.UnManaged,
    COUNT(n.NodeID) AS Nodes
FROM Orion.Nodes n
GROUP BY n.Status, n.UnManaged
ORDER BY COUNT(n.NodeID) DESC
```

## 3. Status versus PolledStatus on Orion.Nodes

Both properties exist on `Orion.Nodes` and both are `System.Int32`. That much is verified from
the schema. What is **not** verified is the difference between them: the published 2026.2
schema carries no summary text for either property, and neither the OrionSDK documentation nor
any SolarWinds sample script in this repository's sources explains it.

So do not guess, and do not let a report guess for you. Two queries settle it on your server in
under a minute.

Where do they disagree, and what else is true of those nodes?

```sql
SELECT TOP 100
    n.Caption,
    n.Status,
    n.PolledStatus,
    n.UnManaged,
    n.ChildStatus,
    n.CustomStatus,
    n.StatusDescription
FROM Orion.Nodes n
WHERE n.Status <> n.PolledStatus
ORDER BY n.Caption
```

Which pairings occur at all, and how often?

```sql
SELECT
    n.Status,
    n.PolledStatus,
    COUNT(n.NodeID) AS Nodes
FROM Orion.Nodes n
GROUP BY n.Status, n.PolledStatus
ORDER BY COUNT(n.NodeID) DESC
```

Two things you can rely on without running anything:

- **`PolledStatus` is node-specific.** It is declared on `Orion.Nodes`, not on
  `System.ManagedEntity` or `System.DashboardEntity`, so a query written against a base entity
  cannot select it. `Status` can, because it comes from `System.DashboardEntity`.
- **Whichever you pick, pick one.** A report that filters on `Status` and a matching alert that
  triggers on `PolledStatus` will disagree with each other at exactly the moments anybody is
  looking, and the disagreement will be blamed on the alert engine.

Related properties worth knowing before you write a status filter: `ChildStatus`
(`System.Int32`), `CustomStatus` (`System.Boolean`), `GroupStatus` (`System.String`, so it is
not a status integer at all), `Severity` and `UiSeverity` (`System.Int32`), and
`StatusDescription` (`System.String`, inherited from `System.ManagedEntity`, documented as
"Textual information about the status of this entity").

## 4. UTC, DATEADD and the timestamp that quietly shifts

This one has its own page, [date-and-time.md](date-and-time.md), because it is the trap that
produces the most convincing wrong numbers. The short version:

SWIS translates SWQL into T-SQL and runs it on the Orion SQL Server. `AddMinute`, `AddHour`,
`AddDay` and the rest compile to T-SQL `DATEADD`, which has no concept of a timezone offset. If
you feed it the result of `GetUtcDate()`, SQL Server returns the adjusted value stamped with
**its own local offset**, not UTC. SolarWinds documents this, shows the generated T-SQL and the
serialised response, and gives the fix on the
[possible issues](https://solarwinds.github.io/OrionSDK/docs/swql-functions/possible-issues/)
page:

> If you are using `AddMinute` etc. functions you need to first convert the value to the local
> time of the MSSQL server and then convert the result back to UTC time.

So `ToUtc(AddMinute(-10, ToLocal(GetUtcDate())))`, not `AddMinute(-10, GetUtcDate())`.

Two related facts that catch people out separately:

- **Not every timestamp in the schema is UTC.** `Orion.Events.EventTime` is documented as "Date
  and time when the event occurred, **displayed in local time**", while
  `Orion.Nodes.LastSystemUpTimePollUtc` says UTC in its name. Check the property, do not assume
  the database convention.
- **The SQL Server, the Orion server and your workstation can all be in different timezones.**
  The value that arrives at your client has been through all three. `WITH LOGS` (documented, in
  SolarWinds' own example above) is the cheapest way to see what SWIS actually sent.

## 5. NULL, IsNull, and the rows that disappear instead of going null

### 5.1 `= NULL` is always false

Nothing equals NULL, including NULL. `WHERE n.Location = NULL` returns zero rows on every
server forever, and it does not error. Use `IS NULL` and `IS NOT NULL`, both of which appear in
SolarWinds' own PowerShell samples (`WHERE ParentID IS NULL` in `func_ModernDashboards.ps1`,
`WHERE pm.Engine.EngineId IS NOT NULL` in `HA.PoolOperations.ps1`).

### 5.2 `IsNull` is a two-argument substitution, not a predicate

The documented signature is `IsNull(a, b)`: "Returns `a` unless it is NULL, else returns `b`."
It is the T-SQL `ISNULL`, not the Oracle `NVL2` and not a one-argument test. `IsNull(x)` is not
a thing.

```sql
SELECT TOP 100
    n.Caption,
    IsNull(n.Location, 'unset') AS Location,
    IsNull(n.Contact, 'unset')  AS Contact
FROM Orion.Nodes n
ORDER BY n.Caption
```

The documented SWQL function library has 63 entries and **`Coalesce` and `NullIf` are not among
them**. If you need three-way fallback, nest `IsNull` or use `CASE`. Full list:
[../reference/swql-function-index.md](../reference/swql-function-index.md).

### 5.3 NULL propagates through arithmetic and concatenation

`n.MemoryUsed / n.TotalMemory` is NULL if either side is NULL, and the row still appears with a
blank cell rather than being excluded. If a percentage column in a report is intermittently
blank, this is usually why. Deal with the operands, not the result:

```sql
SELECT TOP 100
    n.Caption,
    Round(IsNull(n.MemoryUsed, 0) / n.TotalMemory * 100, 1) AS PercentMemory
FROM Orion.Nodes n
WHERE n.TotalMemory > 0
ORDER BY n.Caption
```

Two different fixes are doing two different jobs here, and it is worth being deliberate about
which you want. `IsNull(n.MemoryUsed, 0)` says "a node reporting no memory usage counts as
zero", which keeps the row. `WHERE n.TotalMemory > 0` excludes both zero and NULL denominators
in one predicate, because `NULL > 0` is not true either, which **drops** the row. Substituting a
value keeps rows; filtering removes them. Choosing by accident is how a report ends up with a
different node count than the one next to it.

### 5.4 Aggregates skip NULL, so COUNT and AVG disagree about the denominator

`Avg(n.CPULoad)` is the mean of the non-NULL values, over a denominator you never see. If half
your nodes do not report CPU, the average is of the other half, and it looks completely normal.
When the denominator matters, count it explicitly:

```sql
SELECT
    COUNT(n.NodeID)  AS AllNodes,
    COUNT(n.CPULoad) AS NodesReportingCpu,
    Avg(n.CPULoad)   AS AvgCpuOfThoseReporting
FROM Orion.Nodes n
```

That NULL-skipping behaviour is standard SQL semantics arriving through the T-SQL translation
rather than something the SWQL reference spells out for every aggregate, but SolarWinds does
state it for one of them: `String_Agg` is documented as concatenating "the non-NULL string
values in the group" and returning NULL when the group has no non-NULL values, so an
empty-looking cell there means "no values", not "no group". If you want to be certain how your
server treats a particular aggregate, the query above is the test: run it and compare the two
counts.

### 5.5 A to-one navigation drops rows; it does not null them

This is the NULL trap that is not about NULL. Walking `i.Node.Caption` behaves as an inner
join: an interface whose node row is missing produces **no row at all**, rather than a row with
a blank caption. Chain three navigations and you have three silent filters. When you need the
unmatched rows, write a `LEFT JOIN` instead. The mechanics are in
[joins-and-navigation.md](joins-and-navigation.md#a-to-one-navigation-is-an-implicit-inner-join).

## 6. To-many navigation multiplies rows and poisons aggregates

`Orion.Nodes.Interfaces` is a `System.Hosting` relationship in the source-to-target direction,
which means one node leads to many interfaces. Selecting through it produces one row per
node-and-interface pair, with every node column repeated on each.

The reason this is a *gotcha* rather than an inconvenience is that the multiplied result looks
fine. Nothing warns you. `SUM(n.TotalMemory)` across a node-to-interface join counts a node's
memory once per interface, so a 48-port switch contributes its memory 48 times, and the total
is off by a factor that varies by device. `TOP 100` returns 100 pairs, which might be two nodes.

**How to spot it in under a minute.** Run two counts over the same `FROM` and `WHERE`: one that
counts the rows the join produces, and one that counts the objects you believe you are listing.

Rows the join produces:

```sql
SELECT COUNT(n.NodeID) AS RowsReturned
FROM Orion.Nodes n
JOIN Orion.NPM.Interfaces i ON i.NodeID = n.NodeID
WHERE i.Status = 2
```

Nodes those rows actually represent:

```sql
SELECT COUNT(n.NodeID) AS ActualNodes
FROM Orion.Nodes n
WHERE n.NodeID IN (
    SELECT i.NodeID
    FROM Orion.NPM.Interfaces i
    WHERE i.Status = 2
)
```

If those two numbers differ, every aggregate in the joined form is counting some nodes more than
once. Two counts rather than one because `Count(n)` is the only counting signature in
SolarWinds' [documented function reference](https://solarwinds.github.io/OrionSDK/docs/swql-functions/);
`COUNT(DISTINCT column)` is standard T-SQL and may well work, but it is **unverified** here.
Confirm it on your own server by running `SELECT COUNT(DISTINCT n.Vendor) AS V FROM Orion.Nodes
n` in SWQL Studio, where an unsupported construct fails to parse immediately.

The usual fix is to stop joining and start filtering with a subquery, which also avoids
materialising the multiplied set:

```sql
SELECT TOP 100 n.Caption, n.IPAddress
FROM Orion.Nodes n
WHERE n.NodeID IN (
    SELECT i.NodeID
    FROM Orion.NPM.Interfaces i
    WHERE i.Status = 2
)
ORDER BY n.Caption
```

Telling to-one from to-many, and the ten worked joins, are in
[joins-and-navigation.md](joins-and-navigation.md#cardinality-the-thing-that-decides-your-row-count).

## 7. Averaging statistics rows without Weight

`System.StatisticsEntity` is the base type for 236 entities in 2026.2, and it declares three
properties that most people never notice. One of them is a correctness landmine:

> `Weight` - Weight of value in this row. Useful to compute weighted average of values. For
> example one row with value collected for 20 seconds will have Weight=20. Other row collected
> for one hour will have Weight=3600.

SolarWinds' own example in that summary is the whole problem: one row can cover twenty seconds
and another one hour, in the same entity. A plain `Avg()` treats those two rows as equally
important, so the result is skewed towards whichever period contributed more rows rather than
towards whichever period covered more time. Detail rows are normally the dense ones, so an
average over a window that mixes detail and summarised data leans towards the recent end of the
window.

```sql
SELECT
    c.NodeID,
    Avg(c.AvgLoad) AS UnweightedAvg,
    Sum(c.AvgLoad * c.Weight) / Sum(c.Weight) AS WeightedAvg,
    Sum(c.Weight) AS SecondsCovered
FROM Orion.CPULoad c
WHERE c.DateTime >= @start
  AND c.DateTime <  @end
GROUP BY c.NodeID
ORDER BY c.NodeID
```

If `UnweightedAvg` and `WeightedAvg` differ noticeably, your rows do not all cover the same span
and the unweighted figure is the wrong one. `ObservationTimestamp` ("When this statistic was
collected") and `ObservationFrequency` ("The interval between collections") are the other two
inherited properties, and `ObservationFrequency` is the other way to see how coarse a given row
is.

The same entities also carry an `Archive` flag on many of the older `Orion.*` statistics tables
(`Orion.CPULoad.Archive`, `Orion.ResponseTime.Archive`, `Orion.NPM.InterfaceTraffic.Archive`,
all `System.Byte`). Where the schema documents it, the wording is "specifies if ... data was
archived", for example on `Orion.APM.ComponentStatus`. Look at the distinct values on your own
server before you either filter on it or ignore it:

```sql
SELECT c.Archive, COUNT(c.NodeID) AS Rows
FROM Orion.CPULoad c
WHERE c.DateTime >= @start
GROUP BY c.Archive
ORDER BY c.Archive
```

## 8. Entities that look like the same thing and are not

Four real pairs from the 2026.2 schema. All four produce a query that runs.

### 8.1 `Orion.Volumes` versus `Orion.SRM.Volumes`

Both exist. Both have a key property called `VolumeID`. Neither is a superset of the other.

| | `Orion.Volumes` | `Orion.SRM.Volumes` |
|:---|:---|:---|
| Module | Core | SRM |
| What it is | A logical disk on a monitored node | A volume on a monitored storage array |
| NetObject prefix | `V` | `SMV` |
| Key property | `VolumeID` | `VolumeID` |
| Parent | the node (`NodeID` column) | `Orion.SRM.Pools` (`StorageArrayID` column) |
| Size column | `VolumeSize` (`System.Double`) | `CapacityTotal` (`System.Int64`) |
| Used-percent column | `VolumePercentUsed` (`System.Single`) | `CapacityUsedPercentage` (`System.Single`) |
| Properties | 53 | 54 |

These are two different entities with two different NetObject prefixes, so there is no reason to
expect `VolumeID` 412 in one to have anything to do with `VolumeID` 412 in the other. A capacity
report that joins the wrong one returns rows, numbers and a completely fictional picture of your
storage. The
[NetObject type reference](../reference/netobject-types.md) lists the prefix and key properties
for all 115 mapped entities, which is the fastest way to check you have the right one.

### 8.2 `Orion.Nodes` versus `Cirrus.Nodes` and `NCM.Nodes`

The NCM node entities describe the same physical devices, but they are a different table with a
different key **of a different type**:

| Property | `Orion.Nodes` | `Cirrus.Nodes` / `NCM.Nodes` |
|:---|:---|:---|
| `NodeID` | `System.Int32` | `System.Guid` |
| Orion node id | `NodeID` | `CoreNodeID` (`System.Int32`) |
| Caption | `Caption` | `NodeCaption` ("The `Orion.Nodes` Caption value") |
| `Status` | `System.Int32` | `System.Byte` |

So `ON c.NodeID = n.NodeID` between `Cirrus.Nodes` and `Orion.Nodes` is comparing a GUID to an
integer. The correct join is through `CoreNodeID`:

```sql
SELECT TOP 100
    n.Caption,
    c.NodeCaption,
    c.NodeGroup,
    c.ReverseDNS
FROM Orion.Nodes n
JOIN Cirrus.Nodes c ON c.CoreNodeID = n.NodeID
ORDER BY n.Caption
```

`Cirrus.Interfaces` and `NCM.Interfaces` stand in the same relationship to
`Orion.NPM.Interfaces`, and `Cirrus.NodeProperties` (40 properties) and `NCM.NodeProperties`
(31 properties) are yet another near-identical pair carrying NCM node data.

### 8.3 `Orion.Nodes.Volumes` versus `Orion.Nodes.RelyVolumes`

Two navigation properties on the same entity, both leading to `Orion.Volumes`, meaning entirely
different things:

| Navigation | Relationship | Kind | Meaning |
|:---|:---|:---|:---|
| `Volumes` | `Orion.NodeHostsVolumes` | `System.Hosting` | volumes that live on this node |
| `RelyVolumes` | `Orion.Rely.Core.VolumesRelyOnNodes` | `System.Reliance` | volumes elsewhere that depend on this node |

A `System.Hosting` relationship describes containment: the target lives on the source. A
`System.Reliance` relationship describes dependency. Picking the wrong one gives you a plausible
list of volumes that answers a question you did not ask. This is not a one-off:
of the 161 navigations on `Orion.Nodes`, 63 are source-side `System.Hosting`, 68 are source-side
`System.Reference`, and 18 are `System.Reliance` (`RelyApplications`, `RelyContainers`,
`RelyVCenter`, `RelyHost`, `RelyVirtualMachine` and more). See
[../automation/dependencies.md](../automation/dependencies.md) for what Orion does with
reliance.

### 8.4 `Orion.Nodes.Flows` is declared twice

`Orion.Nodes` has 161 navigation properties and exactly one duplicated name: `Flows` is declared
both to `Orion.Netflow.Flows` and to `Orion.Netflow.FlowsByApplication`, both as
`System.Reference`. Which one `n.Flows.Bytes` resolves to is not something the extracted schema
records, and it is not documented. **Unverified:** treat `n.Flows` as ambiguous and write the
target entity out in an explicit join instead. To confirm the behaviour on your own server, run
a query selecting a property that exists on only one of the two (for example `ApplicationID`,
which is on `Orion.Netflow.FlowsByApplication`) and see whether it resolves.

Check for this pattern on any entity before you dot-walk it:

```bash
python3 tools/schema_query.py show Orion.Nodes
```

## 9. Columns that look boolean and are not

2026.2 has 942 `System.Boolean` properties and 24 `System.Char` properties, and the `Char` ones
are where the trouble is. `Orion.NPM.Interfaces.Counter64` documents itself:

> Char value that indicates if interface supports 64-bit counters. Example: `'Y'`, `'N'`.

So `WHERE i.Counter64 = TRUE` does not do what it looks like. It is `WHERE i.Counter64 = 'Y'`.
Other `System.Char` columns in the core schema include `Orion.Volumes.Responding`,
`Orion.Volumes.VolumeResponding`, `Orion.Nodes.CMTS` and `Orion.Accounts.Enabled`.

SolarWinds documents the same shape for account rights, and adds a twist worth reading twice:

> The various `AllowXYZ` properties (plus `CanClearEvents`) that control user rights show up as
> `"Y"` or `"N"` if you query them like `SELECT AllowNodeManagement FROM Orion.Accounts WHERE
> AccountID='bob'`, but when setting them using `UpdateAccount`, specify them as a boolean:
> `true` or `false` in JSON, `$true`/`$false` in PowerShell.
>
> [Account Management](https://solarwinds.github.io/OrionSDK/docs/account-management/)

Read `'Y'`, write `true`. On `Orion.Accounts` the `AllowXYZ` properties are typed
`System.String`, not `System.Char` and not `System.Boolean`, so the query below is the correct
form:

```sql
SELECT a.AccountID, a.AllowAdmin, a.AllowNodeManagement, a.AllowUnmanage
FROM Orion.Accounts a
WHERE a.AllowAdmin = 'Y'
ORDER BY a.AccountID
```

Genuine `System.Boolean` properties do compare against the `TRUE` and `FALSE` keywords, and
`n.UnManaged = FALSE` is the idiomatic form. The rule is simply: check the type first.

```bash
python3 tools/schema_query.py props Orion.NPM.Interfaces --grep Counter
```

## 10. String comparison, collation and case

SWIS hands string comparison to SQL Server, so `=`, `!=`, `LIKE`, `ORDER BY` and `DISTINCT` all
behave according to the **collation the Orion database was created with**. That is chosen at
install time. It is not a SWQL setting, it is not consistent across customers, and nothing in a
query result tells you which way it went.

Practical consequences:

- **Do not assume case insensitivity, and do not assume case sensitivity.** `WHERE n.Caption =
  'core-sw-01'` may or may not match `Core-SW-01`.
- **`ORDER BY` on a caption can interleave or segregate mixed case** depending on collation, so
  a report's row order can differ between two customers running identical code.
- **`DISTINCT` and `GROUP BY` may or may not fold `Cisco` and `CISCO` into one bucket.** This is
  the version of the problem that silently changes a count.
- **Accent sensitivity is part of collation too**, which matters for location and contact
  fields.

When a comparison must be case insensitive regardless of collation, force it on both sides:

```sql
SELECT TOP 100 n.Caption, n.Vendor
FROM Orion.Nodes n
WHERE ToUpper(n.Vendor) = ToUpper(@vendor)
ORDER BY n.Caption
```

That is correct and it is also slow, because a function wrapped around a column stops an index
on that column from being usable. Prefer resolving the name to a key once and filtering on the
key; see [performance.md](performance.md#3-filter-on-keys-not-on-captions).

Two more string-shaped traps:

- **`LIKE` has no regular expressions.** `%` matches any run of characters, `_` matches exactly
  one, and that is the entire pattern language. There is no `*`, no `?`, no character class and
  no alternation.
- **Compare Uris with `UriEquals`, not `=`.** The documented description is "Returns true if
  SWIS Uri `a` refers to the same entity instance as SWIS Uri `b`", which is a different
  question from whether two strings match character by character. A string `=` on two Uris can
  say false about one entity.

## 11. The query interface cannot write, and some entities cannot be written at all

There is no `INSERT`, `UPDATE`, `DELETE` or `MERGE` in SWQL. SolarWinds states it plainly:

> The SWIS query interface is read-only and cannot be used to insert, update, or delete data.
>
> [About SWIS](https://solarwinds.github.io/OrionSDK/docs/about-swis/)

Changes go through CRUD on a Uri, an Invoke verb, or `BulkUpdate` / `BulkDelete`. See
[../swis/crud.md](../swis/crud.md), [../swis/invoke-verbs.md](../swis/invoke-verbs.md) and
[../swis/bulk-operations.md](../swis/bulk-operations.md).

The part that surprises people is the next layer down: **not every entity supports CRUD even
through the right interface.** Of 2067 entities in 2026.2, 250 are creatable and 85 carry an
explicit `readOnly` flag in the schema. All 85 are in the NCM namespaces, 43 under `Cirrus.*`
and 42 under `NCM.*`, for example `Cirrus.Interfaces` and `Cirrus.PolicyCacheResults`.
SolarWinds acknowledges the general point directly:

> However, there may be entity types that do not support this interface or provide only limited
> support due to technical or design reasons. In these cases, the operations may reject
> requests.
>
> [About SWIS](https://solarwinds.github.io/OrionSDK/docs/about-swis/)

Check before you write code against an entity:

```bash
python3 tools/schema_query.py show Orion.Engines
```

```text
operations: create, delete, read, update
  read                                   requires everyone
  create,update,delete                   requires system
```

`requires system` means an ordinary admin account cannot do it. On a live server the same
question is answered by `Metadata.Entity`:

```sql
SELECT e.FullName, e.CanCreate, e.CanRead, e.CanUpdate, e.CanDelete, e.CanInvoke
FROM Metadata.Entity e
WHERE e.FullName = 'Orion.Engines'
```

One related trap: **custom property columns are not in the published schema.**
`Orion.NodesCustomProperties` declares exactly one property, `NodeID`. Everything else on it is
created on your server at runtime. That means `python3 tools/schema_query.py props
Orion.NodesCustomProperties` will never show your `City` or `Owner` column, and a validator
built on the published schema cannot check it. Ask the server:

```sql
SELECT p.Name, p.Type, p.IsNullable
FROM Metadata.Property p
WHERE p.Entity.FullName = 'Orion.NodesCustomProperties'
ORDER BY p.Name
```

## 12. Port 17778 is deprecated

The REST endpoint moved. From platform release 2023.1 onward the REST/JSON port is **17774**.
Port **17778** was the REST port through 2022.4.1 and is deprecated. The SOAP/net.tcp endpoint
is a third port, **17777**, and is unaffected.

```text
https://orion.example.com:17774/SolarWinds/InformationService/v3/Json/Query
```

This is a gotcha rather than a footnote because of how it fails. Sending a request to a port
that no longer serves the API produces a connection-level failure, not an API error, so there is
no response body explaining what went wrong. A script copied from a pre-2023 blog post stops
working after an upgrade in a way that reads as a firewall or certificate problem, and people
spend a day on TLS before checking the number after the colon.

Details, including TLS and the self-signed certificate, are in
[../swis/connecting.md](../swis/connecting.md#endpoints-and-ports).

## 13. Entity names change between versions

An entity name that was correct three versions ago can be gone, and a SWQL query naming a
missing entity fails outright rather than returning zero rows, which is at least honest. The
problem is the reverse case: documentation, blog posts and community query libraries that still
name the old entity.

`data/reference/reconciliation.json` in this repository records every name in the community
reference workbook that could not be resolved against the published schema, with the closest
matching real entity:

| Name you will see quoted | Real entity in 2026.2 | Note |
|:---|:---|:---|
| `Orion.VIM.LUNs` | `Orion.VIM.Luns` | capitalisation only |
| `Orion.NPM.UCSBlades` | `Orion.UCS.Blades` | moved namespace |
| `Orion.NPM.UCSChassis` | `Orion.UCS.Chassis` | moved namespace |
| `Orion.NPM.UCSFabrics` | `Orion.UCS.Fabrics` | moved namespace |
| `Orion.NPM.UCSFans`, `Orion.NPM.UCSManagers`, `Orion.NPM.UCSPSUs` | no direct successor | see `Orion.UCS.FansOnChassis`, `Orion.UCS.FansOnFabrics`, `Orion.UCS.PSUsOnChassis` |
| `Orion.F5.Device` | `Orion.F5.System.Device` | moved namespace |
| `Orion.F5.Pools` | `Orion.F5.GTM.Pool`, `Orion.F5.LTM.Pool` | split by module |
| `Orion.F5.VirtualServers` | `Orion.F5.GTM.VirtualServer`, `Orion.F5.LTM.VirtualServer`, `Orion.F5.Map.VirtualServer` | split by module |
| `Orion.SRM.FIleServerIdentification` | `Orion.SRM.FileServerIdentification` | capitalisation only |

Note the two capitalisation-only cases. `Orion.VIM.LUNs` versus `Orion.VIM.Luns` and
`FIleServerIdentification` versus `FileServerIdentification` are the kind of difference that
survives a code review and fails at runtime.

And there is no rule you can apply instead of looking it up, because the capitalisation is not
consistent across the schema. `Orion.VIM.Luns` is correct **and so is `Orion.SRM.LUNs`**, which
is a different entity in a different module. Even within the SRM namespace both spellings occur:

```bash
python3 tools/schema_query.py find LUN
```

```text
  Orion.SRM.LUNs                                         62p   0v  Contains information about all LUNs
  Orion.VIM.Luns                                          7p   0v  LUN
  Orion.SRM.LunMasking                                    8p   0v  Defines LUN masking
  Orion.SRM.LUNStatistics                                31p   0v  Stores LUNs statistics.
  Orion.SRM.LunsToVIMLuns                                 4p   0v  Defines mapping between SRM LUNs and VIM LUNs
```

**When did these change?** Not recently. Every published schema version from 2023.1 to 2026.2
(2023.1, 2023.2, 2023.3, 2023.4, 2024.1, 2024.2, 2024.4, 2024.4.1, 2025.1, 2025.1.1, 2025.2,
2025.2.1, 2025.4, 2026.1, 2026.2, fifteen releases) already uses `Orion.VIM.Luns`,
`Orion.UCS.*` and `Orion.F5.System.Device`, and none of them contains `Orion.VIM.LUNs`, any
`Orion.NPM.UCS*` entity, or `Orion.F5.Device`. The renames therefore predate 2023.1, which means
any source still quoting the old names has been stale for years. You can confirm this yourself
with the URL pattern in check 2 below, substituting each version.

### How to check whether an entity exists on the version you are targeting

Four checks, cheapest first.

**1. Against this repository's extracted 2026.2 schema.** Instant, no server:

```bash
python3 tools/schema_query.py show Orion.VIM.Luns
python3 tools/schema_query.py find LUN
```

`find` matches case-insensitively on a substring, so it is the right tool when you suspect the
name is nearly right.

**2. Against SolarWinds' published schema for a specific version.** The gh-pages site keeps one
directory per version, so you can check any of them directly:

```text
https://solarwinds.github.io/OrionSDK/2026.2/schema/Orion.VIM.Luns.html
https://solarwinds.github.io/OrionSDK/2025.4/schema/Orion.VIM.Luns.html
```

A 404 means the entity does not exist in that version.

**3. Against the server actually in front of you.** This is the authoritative answer, because it
accounts for which modules are installed, which the published schema does not:

```sql
SELECT e.FullName, e.BaseType, e.IsObsolete, e.ObsolescenceReason
FROM Metadata.Entity e
WHERE e.FullName LIKE 'Orion.VIM.Lun%'
ORDER BY e.FullName
```

`IsObsolete` and `ObsolescenceReason` are the early warning: an entity marked obsolete still
works today and is scheduled to stop. Sweep for them all at once:

```sql
SELECT e.FullName, e.ObsolescenceReason
FROM Metadata.Entity e
WHERE e.IsObsolete = TRUE
ORDER BY e.FullName
```

The same applies at property level via `Metadata.Property.IsObsolete`. More introspection
recipes are in
[../swis/metadata-introspection.md](../swis/metadata-introspection.md#obsolete-and-internal-members).

**4. Against your whole query corpus, before deploying.** The repository's validator resolves
every entity, property and navigation in a query against the extracted schema:

```bash
echo "SELECT LUNID FROM Orion.VIM.LUNs" | python3 tools/validate_swql.py -
```

```text
ERROR: unknown entity 'Orion.VIM.LUNs'. Did you mean: Orion.VIM.Luns?
```

## 14. Types change between versions too

A property that keeps its name but changes its type does not break SWQL. It breaks the typed
client on the other end, which is worse, because the failure surfaces somewhere else entirely.

Real examples from the 2025.4 to 2026.2 diff in
[../reference/schema-changes-2025.4-to-2026.2.md](../reference/schema-changes-2025.4-to-2026.2.md):

- Twenty-plus IPAM identifier properties went from `System.Int32` to `System.Int64`
  (`IPAM.IPNode.IpNodeId`, `IPAM.IPConflict.IPNodeId`, `IPAM.DhcpServer.StatAcks` and others). A
  C# client binding those to `int` throws at deserialisation; a PowerShell script does not, and
  quietly keeps working until an id exceeds 2147483647.
- `Orion.MemoryMultiLoad.Index` went from `System.Int16` to `System.Int32`.
- `Orion.GroupMembers.IsGroup` was published as `System.boolean` (lower case `b`) and is now
  `System.Boolean`. Any code doing a string comparison on the type name broke.

There is a matching page for the single-release step,
[../reference/schema-changes-2026.1-to-2026.2.md](../reference/schema-changes-2026.1-to-2026.2.md).

The same section of that diff carries the nastiest version-change trap of all, which is not a
SWQL issue but will find you through the same code path: **Invoke sends verb arguments as a
positional array with no names**. When SolarWinds reorders a verb's parameters, an existing call
still has the right number of arguments and puts them in the wrong slots. In 2026.2 that
happened to `Orion.Orchestrators.Info.AddFortinetFortiManagerNode`. See
[../swis/invoke-verbs.md](../swis/invoke-verbs.md).

## 15. Legacy properties the schema tells you to ignore

Some properties exist only for backward compatibility and their own schema summaries say so.
`System.ManagedEntity` documents two of them in as many words:

- `StatusLED` (`System.String`): "A legacy property. Ignore this."
- `Image` (`System.String`): "A legacy property. Ignore this."

Both are inherited by all 174 entities under `System.ManagedEntity`, including `Orion.Nodes`, so
they show up in autocomplete and look like reasonable things to select. They are not.

Near-duplicate columns are the related hazard. `Orion.Nodes` alone carries `IPAddress`, `IP`,
`IP_Address` and `IPAddressGUID`; `Caption`, `NodeName`, `DisplayName`, `DNS` and `SysName`;
`NodeDescription` and `Description`. They are not guaranteed to hold the same value, and picking
the wrong one produces a report that is right for most rows and wrong for the ones that matter.
When in doubt, select several at once on a sample and look:

```sql
SELECT TOP 20 n.NodeID, n.Caption, n.NodeName, n.DisplayName, n.DNS, n.SysName,
       n.IPAddress, n.IP
FROM Orion.Nodes n
ORDER BY n.NodeID
```

## A ten-minute audit for a query you inherited

Run down this list before trusting a number that came out of a SWQL query.

1. **Who ran it?** Compare the row count against an unlimited account.
   ([1](#1-the-empty-result-set-is-usually-a-permissions-answer))
2. **Does it hard-code a status integer?** If so, does that integer mean the same thing on that
   entity? ([2](#2-status-is-an-integer-and-the-integer-means-different-things-on-different-entities))
3. **Does it filter on `Status` or `PolledStatus`, and does the matching alert use the same
   one?** ([3](#3-status-versus-polledstatus-on-orionnodes))
4. **Does it mix `GetUtcDate()` with an `AddX` function?**
   ([4](#4-utc-dateadd-and-the-timestamp-that-quietly-shifts))
5. **Does it use `= NULL` anywhere, or arithmetic on a nullable column?**
   ([5](#5-null-isnull-and-the-rows-that-disappear-instead-of-going-null))
6. **Does the join row count match the object count?**
   ([6](#6-to-many-navigation-multiplies-rows-and-poisons-aggregates))
7. **Does it average anything under `System.StatisticsEntity` without `Weight`?**
   ([7](#7-averaging-statistics-rows-without-weight))
8. **Is every entity name the one you meant, in the namespace you meant?**
   ([8](#8-entities-that-look-like-the-same-thing-and-are-not))
9. **Does it compare a `System.Char` or `System.String` flag against `TRUE`?**
   ([9](#9-columns-that-look-boolean-and-are-not))
10. **Does it depend on case-insensitive string matching?**
    ([10](#10-string-comparison-collation-and-case))
11. **Does it name an entity that still exists on the target version?**
    ([13](#13-entity-names-change-between-versions))

Then run it through the static checker, which catches the name errors without a server:

```bash
python3 tools/validate_swql.py my-query.swql
python3 tools/validate_swql.py --docs docs/
```

## Next

- [performance.md](performance.md) for the queries that are correct and still a problem.
- [date-and-time.md](date-and-time.md) for the full treatment of the UTC trap.
- [joins-and-navigation.md](joins-and-navigation.md) for cardinality and worked joins.
- [../reference/status-codes.md](../reference/status-codes.md) for the status integers.
- [../swis/metadata-introspection.md](../swis/metadata-introspection.md) for asking your own
  server what exists.

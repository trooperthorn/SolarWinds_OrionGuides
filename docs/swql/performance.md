# SWQL performance

A SWQL query is not free and it is not isolated. SWIS satisfies most queries by translating
them into T-SQL and executing them **against the live Orion database**, which is the same
database the polling engines are writing to continuously. SolarWinds shows this translation
happening on the
[possible issues](https://solarwinds.github.io/OrionSDK/docs/swql-functions/possible-issues/)
page, where a five-column SWQL statement is printed alongside the exact T-SQL it becomes:

```text
SET DATEFIRST 7;
SET TRANSACTION ISOLATION LEVEL READ COMMITTED;
SELECT [T1].[EngineID] AS C1, [T1].[ServerName] AS C2, ... FROM dbo.Engines AS T1
WHERE [T1].[ServerType] = 'Primary'
```

That is why "my report is a bit slow" and "polling is falling behind" are sometimes the same
incident. The query interface is read-only, so a bad query cannot corrupt anything, but it can
absolutely take resources away from the thing the product exists to do.

This page is about the queries that are *correct* and still a problem. For the ones that are
wrong, see [gotchas.md](gotchas.md).

Every entity and property name here was resolved against `data/schema/2026.2/` before it was
written.

- [Where the size is](#where-the-size-is)
- [1. Bound every result set](#1-bound-every-result-set)
- [2. Select only the columns you need](#2-select-only-the-columns-you-need)
- [3. Filter on keys, not on captions](#3-filter-on-keys-not-on-captions)
- [4. Never wrap a filtered column in a function](#4-never-wrap-a-filtered-column-in-a-function)
- [5. Time-bound everything historical](#5-time-bound-everything-historical)
- [6. Filter before you aggregate](#6-filter-before-you-aggregate)
- [7. Dot-walking is joining, and deep chains join repeatedly](#7-dot-walking-is-joining-and-deep-chains-join-repeatedly)
- [8. Page with WITH ROWS, do not pull everything](#8-page-with-with-rows-do-not-pull-everything)
- [9. Bind parameters instead of building query text](#9-bind-parameters-instead-of-building-query-text)
- [Six rewrites](#six-rewrites)
- [Measuring rather than guessing](#measuring-rather-than-guessing)
- [Checklist](#checklist)

## Where the size is

Not all 2067 entities are the same size. Knowing which category you are in decides how much
care a query needs.

| Category | How to recognise it | Rough size | Care needed |
|:---|:---|:---|:---|
| Inventory | `Orion.Nodes`, `Orion.NPM.Interfaces`, `Orion.Volumes`, `Orion.APM.Application` | one row per monitored object | `TOP` and a sensible `WHERE` |
| Lookup | `Orion.StatusInfo` (26 rows), `Orion.EventTypes`, `Orion.LimitationTypes`, `Orion.Engines` | tens of rows | none |
| Extension | the 305 entities under `System.ExtensionEntity` that are not statistics, for example `Orion.NodesCustomProperties` | one row per object | joins to inventory, so watch cardinality |
| **Statistics and history** | the **236 entities under `System.StatisticsEntity`** | one row per object *per collection interval*, retained for months | **always time-bounded, always** |
| Event and audit | `Orion.Events`, `Orion.AlertHistory`, `Cirrus.Audit` | one row per thing that happened | always time-bounded |

Find out which category an entity is in without a server:

```bash
python3 tools/schema_query.py show Orion.CPULoad
```

```text
inherits: System.Entity -> System.ExtensionEntity -> System.StatisticsEntity -> Orion.CPULoad
```

That inheritance line is the whole warning. `Orion.CPULoad`, `Orion.ResponseTime`,
`Orion.NPM.InterfaceTraffic`, `Orion.VolumeUsageHistory`, every `Orion.Netflow.Flows*` entity
and every `Cortex.Orion.*.Statistics` entity sit under `System.StatisticsEntity`. List them all:

```bash
python3 tools/schema_query.py children System.StatisticsEntity
```

## 1. Bound every result set

SWQL has no implicit row limit. `SELECT NodeID, Caption FROM Orion.Nodes` returns every node
the caller can see, and the equivalent statement against a statistics entity returns every
sample ever retained.

Two bounding mechanisms, and they do different jobs:

```sql
SELECT TOP 100 n.NodeID, n.Caption, n.IPAddress
FROM Orion.Nodes n
ORDER BY n.Caption
```

`TOP n` caps the result. Always pair it with `ORDER BY`, because "the first 100" is meaningless
otherwise and will not be stable between runs.

```sql
SELECT n.NodeID, n.Caption
FROM Orion.Nodes n
ORDER BY n.NodeID
WITH ROWS 1 TO 500 WITH TOTALROWS
```

`WITH ROWS a TO b` takes a window, 1-based and inclusive, and `WITH TOTALROWS` adds the
unwindowed count to the response envelope so a client can work out how many more pages there
are. Both appear in SolarWinds' own [REST examples](https://solarwinds.github.io/OrionSDK/docs/rest/).
See [8. Page with WITH ROWS](#8-page-with-with-rows-do-not-pull-everything).

The exploratory habit worth building: put `TOP 10` on a query the first time you run it, look
at the shape of the result, and only then decide what the real bound should be. This is
especially true in SWQL Studio, where an unbounded query against a statistics entity will
happily try to render millions of rows into a grid.

## 2. Select only the columns you need

There is no `SELECT *` in SWQL. That is not an oversight, and the reason is a performance
reason.

`Orion.Nodes` declares 102 properties and exposes 113 once inheritance is counted, and they are
not all the same cost. Some are stored columns. Others are **computed by SWIS at query time**,
and the schema says so:

| Property | Declared on | What its own summary says |
|:---|:---|:---|
| `Uri` | `System.Entity` | "The values for `InstanceType` and `Uri` will be filled in by SWIS, so you should not map those to storage properties" |
| `InstanceType` | `System.Entity` | as above |
| `DetailsUrl` | `System.DashboardEntity` | "typically constructed using a string concatenation expression in a defining query storage entity" |
| `AncestorDisplayNames` | `System.ManagedEntity` | "Returns an array containing the `DisplayName` properties of this entity, the entity that hosts this entity, and so on, **recursively**. Generated automatically by SWIS" |
| `AncestorDetailsUrls` | `System.ManagedEntity` | as above |

`AncestorDisplayNames` and `AncestorDetailsUrls` are the expensive ones: they walk the hosting
chain upward for every row in your result and return a `System.String[]`. Selecting them on a
10-row result is nothing. Selecting them on a 200000-row result is a different query entirely.

So name your columns, and name the cheap ones:

```sql
SELECT TOP 200 n.NodeID, n.Caption, n.Status
FROM Orion.Nodes n
WHERE n.Status <> 1
ORDER BY n.Caption
```

There is a second, non-performance reason that matters just as much in automation: a named
column list means a module upgrade that adds a property cannot change your result shape
underneath you.

To find out what a column costs, look at what it is:

```bash
python3 tools/schema_query.py props Orion.Nodes --grep Ancestor
```

## 3. Filter on keys, not on captions

Key columns are integers, they are the primary keys of the underlying tables, and they are what
every relationship in the schema is expressed in terms of. Captions are user-editable strings
whose comparison behaviour depends on the database collation
([gotchas.md](gotchas.md#10-string-comparison-collation-and-case)).

`data/reference/netobject-types.json` records the key properties for 115 mapped entities. The
core ones:

| Entity | Key property | NetObject prefix |
|:---|:---|:---|
| `Orion.Nodes` | `NodeID` | `N` |
| `Orion.NPM.Interfaces` | `InterfaceID` | `I` |
| `Orion.Volumes` | `VolumeID` | `V` |
| `Orion.SRM.Volumes` | `VolumeID` | `SMV` |
| `Orion.APM.Application` | `ApplicationID` | `AA` |
| `Orion.APM.Component` | `ComponentID` | `AM` |
| `Orion.Groups` | `ContainerID` | `C` |

The practical rule: **resolve a name to a key once, then use the key**. A script that looks up a
node by caption on every iteration is doing a string scan every time; a script that resolves the
caption to a `NodeID` at the top and passes the integer around is doing one.

```sql
SELECT TOP 1 n.NodeID
FROM Orion.Nodes n
WHERE n.Caption = @caption
```

```sql
SELECT
    i.InterfaceID,
    i.Caption,
    i.Status,
    i.InPercentUtil,
    i.OutPercentUtil
FROM Orion.NPM.Interfaces i
WHERE i.NodeID = @nodeId
ORDER BY i.InterfaceID
```

When you have a set of names rather than one, bind the whole set as a single multi-valued
parameter and resolve them in one round trip rather than in a loop:

```sql
SELECT n.NodeID, n.Caption
FROM Orion.Nodes n
WHERE n.Caption IN @captions
ORDER BY n.Caption
```

Note there are **no parentheses** around the parameter. This is SolarWinds' own pattern; the
`BulkEnableAssetInventory` Go sample uses `WHERE IPAddress IN @ipaddresses`.

To confirm which properties your server considers keys:

```sql
SELECT p.Name, p.Type, p.IsKey, p.IsSortable
FROM Metadata.Property p
WHERE p.Entity.FullName = 'Orion.Nodes'
  AND p.IsKey = TRUE
ORDER BY p.Name
```

## 4. Never wrap a filtered column in a function

This is the single highest-value rewrite on the page, and it is worth understanding *why*
rather than memorising it.

An index on a column is an ordered structure over the **column's values**. A predicate like
`n.NodeID = 42` can be answered by descending the index. A predicate like
`ToUpper(n.Caption) = 'CORE-SW-01'` cannot, because the index knows nothing about the values of
`ToUpper(Caption)`. SQL Server's only remaining option is to compute the function for every row
and compare, which is a full scan. The optimiser does not warn you; the query simply becomes
linear in the size of the table.

SWQL compiles to T-SQL, so this behaviour comes straight through. Every one of these is a scan:

```text
WHERE Year(c.DateTime) = 2026
WHERE ToUpper(n.Caption) LIKE '%CORE%'
WHERE DateTrunc('day', e.EventTime) = @day
WHERE SubString(n.Caption, 1, 4) = 'core'
WHERE HourDiff(c.DateTime, GetUtcDate()) < 24
```

Each has a rewrite that keeps the column bare on one side of the comparison:

| Instead of | Write |
|:---|:---|
| `Year(c.DateTime) = 2026` | `c.DateTime >= @yearStart AND c.DateTime < @yearEnd` |
| `DateTrunc('day', e.EventTime) = @day` | `e.EventTime >= @dayStart AND e.EventTime < @dayEnd` |
| `HourDiff(c.DateTime, GetUtcDate()) < 24` | `c.DateTime >= @since` with `@since` computed by the client |
| `SubString(n.Caption, 1, 4) = 'core'` | `n.Caption LIKE 'core%'` |
| `ToUpper(n.Caption) LIKE '%CORE%'` | resolve to `NodeID` once, then filter on the key |

The half-open range (`>= start AND < end`) is the right shape for time windows: it is
index-friendly, it has no off-by-one at the boundary, and unlike `BETWEEN` it does not include
the endpoint twice when you run consecutive windows.

Note the `HourDiff` row in particular. Computing the boundary **in the client** and binding it
is better than computing it in the query, because it also sidesteps the `GetUtcDate()` plus
`AddX` timezone trap described in [gotchas.md](gotchas.md#4-utc-dateadd-and-the-timestamp-that-quietly-shifts)
and [date-and-time.md](date-and-time.md). One computation, in one place, with a type.

Functions in the `SELECT` list are a different matter. `Round()`, `Concat()` and `CASE` applied
to output columns run once per returned row, and if the result set is bounded, so is the cost.
It is specifically functions on a **filtered or joined** column that hurt.

## 5. Time-bound everything historical

236 entities in 2026.2 inherit from `System.StatisticsEntity`. A statistics row exists per
monitored object per collection interval, retained according to your retention settings, so the
row count is roughly *objects x intervals x days*. On a mid-sized installation
`Orion.NPM.InterfaceTraffic` alone is comfortably into the hundreds of millions of rows.

An unbounded query against one of those is not slow. It is an outage.

```text
-- Do not run this on a production server.
SELECT t.InterfaceID, t.DateTime, t.InAveragebps, t.OutAveragebps
FROM Orion.NPM.InterfaceTraffic t
```

Every historical query needs three things: a time bound, an object bound, and a row bound.

```sql
SELECT TOP 5000
    t.InterfaceID,
    t.DateTime,
    t.InAveragebps,
    t.OutAveragebps
FROM Orion.NPM.InterfaceTraffic t
WHERE t.InterfaceID = @interfaceId
  AND t.DateTime   >= @start
  AND t.DateTime   <  @end
ORDER BY t.DateTime
```

### The time column is not called the same thing on every entity

This trips people up constantly. Every entity under `System.StatisticsEntity` inherits
`ObservationTimestamp` ("When this statistic was collected") and `ObservationFrequency` ("The
interval between collections"), but most of them also declare their own timestamp column, and
the name varies. Counting only entities that declare their own: 32 use `TimeStamp`, 19 use
`DateTime`, 11 use `Timestamp` (different capitalisation), 5 use `Date` and 5 use `DateTimeUTC`.

| Entity | Its own time column |
|:---|:---|
| `Orion.CPULoad` | `DateTime` |
| `Orion.ResponseTime` | `DateTime` |
| `Orion.NPM.InterfaceTraffic` | `DateTime` |
| `Orion.VolumeUsageHistory` | `DateTime` |
| `Orion.Netflow.Flows` | `TimeStamp` |
| `Orion.Netflow.FlowsByApplication` | `TimeStamp` |
| `Orion.APM.HistoricalCPULoad` | `Date` ("The date of poll") |
| `Orion.AlertHistory` | `TimeStamp` |
| `Orion.Events` | `EventTime` (documented as local time, not UTC) |

Check before you write the `WHERE`:

```bash
python3 tools/schema_query.py props Orion.Netflow.FlowsByApplication --grep Time
```

### Aggregate in the database, not in the client

Pulling 200000 rows over HTTP to compute an average in PowerShell is slow at both ends. Let
SWIS do it, and remember `Weight` when the window might cross a rollup boundary
([gotchas.md](gotchas.md#7-averaging-statistics-rows-without-weight)):

```sql
SELECT
    c.NodeID,
    Sum(c.AvgLoad * c.Weight) / Sum(c.Weight) AS WeightedAvgCpu,
    Max(c.MaxLoad)                            AS PeakCpu,
    Sum(c.Weight)                             AS SecondsCovered
FROM Orion.CPULoad c
WHERE c.DateTime >= @start
  AND c.DateTime <  @end
  AND c.NodeID IN @nodeIds
GROUP BY c.NodeID
ORDER BY c.NodeID
```

When you need a chart rather than a number, `Downsample(d, p)` rounds timestamps to a period, so
you can return one point per bucket instead of one point per sample. It is documented as
requiring Orion 2018.3 or later.

```sql
SELECT
    Downsample(c.DateTime, '01:00:00') AS Bucket,
    Avg(c.AvgLoad)                     AS AvgCpu
FROM Orion.CPULoad c
WHERE c.NodeID   = @nodeId
  AND c.DateTime >= @start
  AND c.DateTime <  @end
GROUP BY Downsample(c.DateTime, '01:00:00')
ORDER BY Downsample(c.DateTime, '01:00:00')
```

`Downsample` here is applied to a column in `GROUP BY` and `SELECT`, not in `WHERE`. The `WHERE`
still uses a bare-column range, which is exactly the split you want.

## 6. Filter before you aggregate

`WHERE` runs before grouping and reduces the rows the aggregate has to touch. `HAVING` runs
after grouping and discards finished groups. They produce the same answer for a non-aggregate
condition and do a completely different amount of work.

The rule is mechanical: **if the condition does not mention an aggregate function, it belongs in
`WHERE`.**

Slow, because every vendor's nodes are grouped and averaged and then all but one vendor's groups
are thrown away:

```sql
SELECT
    c.Node.Vendor  AS Vendor,
    c.Node.Caption AS NodeCaption,
    Avg(c.AvgLoad) AS AvgCpu
FROM Orion.CPULoad c
WHERE c.DateTime >= @start
GROUP BY c.Node.Vendor, c.Node.Caption
HAVING c.Node.Vendor = 'Cisco'
ORDER BY Avg(c.AvgLoad) DESC
```

Faster, because the rows are discarded before any grouping happens:

```sql
SELECT
    c.Node.Caption AS NodeCaption,
    Avg(c.AvgLoad) AS AvgCpu
FROM Orion.CPULoad c
WHERE c.DateTime  >= @start
  AND c.Node.Vendor = 'Cisco'
GROUP BY c.Node.Caption
ORDER BY Avg(c.AvgLoad) DESC
```

Faster still, because the vendor filter now runs against inventory-sized data and reaches the
statistics table as an integer key predicate:

```sql
SELECT
    c.NodeID,
    Avg(c.AvgLoad) AS AvgCpu
FROM Orion.CPULoad c
WHERE c.DateTime >= @start
  AND c.NodeID IN (
      SELECT n.NodeID
      FROM Orion.Nodes n
      WHERE n.Vendor = 'Cisco'
  )
GROUP BY c.NodeID
ORDER BY Avg(c.AvgLoad) DESC
```

`HAVING` still earns its keep for genuinely aggregate conditions, which cannot be expressed any
other way:

```sql
SELECT
    a.NodeID,
    COUNT(a.ApplicationID) AS Applications
FROM Orion.APM.Application a
GROUP BY a.NodeID
HAVING COUNT(a.ApplicationID) > 20
ORDER BY COUNT(a.ApplicationID) DESC
```

## 7. Dot-walking is joining, and deep chains join repeatedly

A navigation property is a declared join. `cp.Application.Node.Engine.ServerName` is three
joins, written in eleven characters plus some dots, which is exactly what makes it so easy to
write something expensive by accident.

Two distinct costs:

**Depth.** Each dot adds a join to the generated T-SQL. A four-segment path is a four-table
join, and if four different columns in your `SELECT` each start with `cp.Application.Node.`,
you are relying on SWIS to recognise the shared prefix. Whether it always does is not
documented. Writing the join once, explicitly, removes the question:

```sql
SELECT TOP 500
    n.Caption    AS NodeCaption,
    n.IPAddress  AS NodeIp,
    e.ServerName AS PollingEngine,
    a.Name       AS ApplicationName,
    cp.Name      AS ComponentName,
    cp.Status
FROM Orion.APM.Component cp
JOIN Orion.APM.Application a ON a.ApplicationID = cp.ApplicationID
JOIN Orion.Nodes n          ON n.NodeID        = a.NodeID
JOIN Orion.Engines e        ON e.EngineID      = n.EngineID
WHERE cp.Status = 2
ORDER BY n.Caption, a.Name, cp.Name
```

The explicit form is longer and it makes the join keys, the join order and the row count
obvious, which is the point.

**Cardinality.** Dot-walking a **to-many** navigation multiplies rows, and it does it silently.
`n.Interfaces.InPercentUtil` produces one row per interface, with every node column repeated. If
what you actually need is "does this node have any interface matching X", use a subquery, which
never materialises the multiplied set:

```sql
SELECT TOP 100 n.NodeID, n.Caption
FROM Orion.Nodes n
WHERE n.NodeID IN (
    SELECT i.NodeID
    FROM Orion.NPM.Interfaces i
    WHERE i.InPercentUtil > 80
)
ORDER BY n.Caption
```

Rule of thumb: **dot-walk to-one navigations for a column or two; join explicitly for anything
wider, deeper or to-many.** Cardinality, and how to tell the two apart, are covered in
[joins-and-navigation.md](joins-and-navigation.md#cardinality-the-thing-that-decides-your-row-count).

## 8. Page with WITH ROWS, do not pull everything

If a result set can be large, page it. `WITH ROWS a TO b` takes a window and `WITH TOTALROWS`
tells you how big the whole thing is.

```sql
SELECT
    n.NodeID,
    n.Caption,
    n.IPAddress
FROM Orion.Nodes n
ORDER BY n.NodeID
WITH ROWS 1 TO 500 WITH TOTALROWS
```

Then 501 TO 1000, and so on. Four rules make this work rather than half work:

1. **`ORDER BY` must be deterministic.** Order by a key, or by something plus a key as a
   tie-breaker. Without a total order, page 2 is not guaranteed to continue where page 1
   stopped, and rows can be repeated or skipped between pages.
2. **Ask for `WITH TOTALROWS` once, on the first page.** It is a count over the unwindowed
   result, so it is not free; requesting it on every page pays for it every page.
3. **Order by the key rather than by a caption when you can.** Sorting a large result on an
   unindexed string is a large part of what makes paging expensive.
4. **For a set you already know, skip paging entirely** and bind the ids as one multi-valued
   parameter (`WHERE n.NodeID IN @ids`). One round trip beats twenty pages.

The request and response shapes over HTTP are in
[../swis/rest-api.md](../swis/rest-api.md#paging-with-with-rows-and-with-totalrows).

## 9. Bind parameters instead of building query text

Bind values. Do not concatenate them into the query string.

```sql
SELECT n.NodeID, n.Caption, n.IPAddress
FROM Orion.Nodes n
WHERE n.Vendor    = @vendor
  AND n.Status    = @status
  AND n.EngineID  = @engineId
ORDER BY n.Caption
```

`{"query": "...", "parameters": {"vendor": "Cisco", "status": 2, "engineId": 1}}` over REST,
`Get-SwisData $swis $query @{ vendor = 'Cisco'; status = 2; engineId = 1 }` in PowerShell.

Three reasons, in the order they usually matter:

1. **Types survive the trip.** A bound integer arrives as an integer and a bound
   `System.DateTime` arrives as a date. Concatenating a date into query text means picking a
   literal format and hoping SWIS parses it the way you meant, which is a correctness problem
   before it is a performance one.
2. **The query text stops changing.** A thousand executions of one parameterised statement look
   like one statement to every layer that caches or logs, instead of a thousand distinct
   strings. SWQL exposes a `WITH NOPLANCACHE` option (**attested, not documented**: it appears
   in SWQL Studio's keyword list) whose existence implies there is a plan cache to suppress.
   Whether SWIS actually reuses a plan across executions of the same parameterised query is
   **unverified** here; you can test it on your own server by running the same query with
   different parameter values and comparing the timings reported by `WITH QUERYSTATS`.
3. **An injection class disappears.** SWQL cannot write data, so the blast radius is smaller
   than SQL injection, but someone who can shape your query text can still read entities your
   query never intended to touch.

Parameters are values, not fragments. Entity names and property names cannot be parameterised,
and SolarWinds says so explicitly for the unit argument of `AddDate(u, n, d)`: it "must be a
string literal. It can't be a query parameter or value derived from the data."

Full parameter-binding detail per client is in
[../swis/rest-api.md](../swis/rest-api.md#parameter-binding) and
[../swis/connecting.md](../swis/connecting.md).

## Six rewrites

Each pair is the same question asked twice.

### Rewrite 1: an unbounded historical scan

**Slow.** No time bound, no object bound, no row bound. Against
`Orion.NPM.InterfaceTraffic` this reads the whole retention window for every interface.

```text
SELECT t.NodeID, t.InterfaceID, t.DateTime, t.InAveragebps, t.OutAveragebps
FROM Orion.NPM.InterfaceTraffic t
ORDER BY t.DateTime DESC
```

**Fast.**

```sql
SELECT TOP 2000
    t.InterfaceID,
    t.DateTime,
    t.InAveragebps,
    t.OutAveragebps
FROM Orion.NPM.InterfaceTraffic t
WHERE t.InterfaceID = @interfaceId
  AND t.DateTime   >= @start
  AND t.DateTime   <  @end
ORDER BY t.DateTime DESC
```

**Why it is better.** Three independent bounds. `InterfaceID` is the key column and a single
integer comparison; `DateTime` is a half-open range that an index can seek rather than scan; and
`TOP` caps the worst case even if the range is wider than you thought. Dropping `t.NodeID` from
the select list also removes a column you can already derive from `@interfaceId`.

### Rewrite 2: a function on the filtered column

**Slow.** `Year()` and `Month()` are computed for every row in the table before anything can be
discarded.

```sql
SELECT TOP 1000 c.NodeID, c.DateTime, c.AvgLoad
FROM Orion.CPULoad c
WHERE Year(c.DateTime)  = 2026
  AND Month(c.DateTime) = 8
ORDER BY c.DateTime
```

**Fast.**

```sql
SELECT TOP 1000 c.NodeID, c.DateTime, c.AvgLoad
FROM Orion.CPULoad c
WHERE c.DateTime >= @monthStart
  AND c.DateTime <  @nextMonthStart
ORDER BY c.DateTime
```

**Why it is better.** The column is bare on one side of both comparisons, so the predicate is
index-friendly. The bounds are computed once in the client instead of twice per row in the
database. And because the client computed them, there is no `GetUtcDate()` plus `AddX` in the
query to go wrong on a SQL Server in a different timezone.

### Rewrite 3: looking up by caption in a loop

**Slow.** One round trip and one string comparison across the whole node table, per name. Run
this for 300 names and it is 300 queries.

```sql
SELECT TOP 1 n.NodeID, n.Caption, n.IPAddress
FROM Orion.Nodes n
WHERE ToUpper(n.Caption) = ToUpper(@caption)
```

**Fast.** One round trip for the whole set.

```sql
SELECT n.NodeID, n.Caption, n.IPAddress
FROM Orion.Nodes n
WHERE n.Caption IN @captions
ORDER BY n.Caption
```

**Why it is better.** One query instead of N. The column is bare, so the comparison can use an
index instead of computing `ToUpper` for every row on both sides. The `ToUpper` on both sides in
the slow form was defending against collation
([gotchas.md](gotchas.md#10-string-comparison-collation-and-case)); if you genuinely need
case-insensitive matching, do the fold once when you build the caption list, and cache the
resulting `NodeID` values so the lookup happens once per run rather than once per operation.

### Rewrite 4: aggregating first and filtering afterwards

**Slow.** Every node in the estate is grouped and averaged, then all but one engine's worth is
discarded.

```sql
SELECT
    r.Node.Engine.ServerName AS PollingEngine,
    r.NodeID,
    Avg(r.AvgResponseTime)   AS AvgMs
FROM Orion.ResponseTime r
WHERE r.DateTime >= @start
GROUP BY r.Node.Engine.ServerName, r.NodeID
HAVING r.Node.Engine.ServerName = @engineName
ORDER BY Avg(r.AvgResponseTime) DESC
```

**Fast.**

```sql
SELECT
    r.NodeID,
    Avg(r.AvgResponseTime) AS AvgMs
FROM Orion.ResponseTime r
WHERE r.DateTime >= @start
  AND r.NodeID IN (
      SELECT n.NodeID
      FROM Orion.Nodes n
      WHERE n.EngineID = @engineId
  )
GROUP BY r.NodeID
ORDER BY Avg(r.AvgResponseTime) DESC
```

**Why it is better.** Three changes compound. The filter moved from `HAVING` to `WHERE`, so
rows are discarded before grouping instead of groups after. The two-hop navigation
`r.Node.Engine.ServerName` disappeared from the `GROUP BY`, which was forcing a join across the
whole statistics range on every row. And the remaining predicate against the statistics entity
is `NodeID IN (small set of integers)` rather than a string comparison reached through two
joins.

### Rewrite 5: a to-many dot-walk used as an existence test

**Slow.** `n.Interfaces` is a to-many navigation, so this produces one row per node-interface
pair. A node with 48 interfaces appears 48 times, `TOP 100` returns roughly two nodes, and any
aggregate over node columns would be multiplied.

```sql
SELECT TOP 100
    n.NodeID,
    n.Caption,
    n.Interfaces.Caption AS InterfaceCaption
FROM Orion.Nodes n
WHERE n.Interfaces.Status = 2
ORDER BY n.Caption
```

**Fast.**

```sql
SELECT TOP 100 n.NodeID, n.Caption, n.IPAddress
FROM Orion.Nodes n
WHERE n.NodeID IN (
    SELECT i.NodeID
    FROM Orion.NPM.Interfaces i
    WHERE i.Status = 2
)
ORDER BY n.Caption
```

**Why it is better.** The multiplied set is never materialised, `TOP 100` now means a hundred
nodes, and the answer is one row per node, which is what the question asked for. If you do want
the interface names as well, join explicitly and accept the row multiplication knowingly rather
than discovering it in a total.

### Rewrite 6: fetching everything to count it

**Slow.** Transfers every matching row over HTTP so the client can call `.Count` on it.

```sql
SELECT n.NodeID, n.Caption, n.Status
FROM Orion.Nodes n
WHERE n.Status = 2
```

**Fast.**

```sql
SELECT
    s.StatusName,
    COUNT(n.NodeID) AS Nodes
FROM Orion.Nodes n
JOIN Orion.StatusInfo s ON s.StatusId = n.Status
GROUP BY s.StatusName
ORDER BY COUNT(n.NodeID) DESC
```

**Why it is better.** One row per status instead of one row per node, so the response is tens of
bytes rather than megabytes, and the counting happens where the data already is. As a bonus the
join to `Orion.StatusInfo` means the result stays correct if SolarWinds adds a status code,
which a client-side count against a hard-coded `Status = 2` would not.

If you only want the number and not the breakdown, `WITH TOTALROWS` on a one-row window gives
you the count in the response envelope without transferring the rows at all:

```sql
SELECT n.NodeID
FROM Orion.Nodes n
WHERE n.Status = 2
ORDER BY n.NodeID
WITH ROWS 1 TO 1 WITH TOTALROWS
```

## Measuring rather than guessing

Every claim on this page is about the shape of a query, not about how many milliseconds it will
take on your hardware. Measure.

| Tool | Status | What it gives you |
|:---|:---|:---|
| `WITH LOGS` | Documented, in SolarWinds' [possible issues](https://solarwinds.github.io/OrionSDK/docs/swql-functions/possible-issues/) example | Server-side diagnostic logging appended to the result. The fastest way to see what SWIS actually sent to SQL Server |
| `WITH QUERYPLAN` | **Attested, not documented.** `queryplan` is in SWQL Studio's keyword list and SWQL Studio has a "Query Plan" result tab | The plan for the generated query |
| `WITH QUERYSTATS` | **Attested, not documented.** `querystats` is in SWQL Studio's keyword list and SWQL Studio has a "Query Stats" result tab | Execution statistics |
| `WITH NOPLANCACHE` | **Attested, not documented.** `noplancache` is in SWQL Studio's keyword list | Presumably suppresses plan reuse, which is what you want when timing a query repeatedly |

A rejected `WITH` clause produces a parse error immediately in SWQL Studio, which makes checking
whether your platform version supports one a two-second test.

Two habits worth more than any single tool:

- **Time the two forms back to back on the same server**, with the same parameters, in the same
  minute. A rewrite that is faster on your lab and slower on a customer's estate usually means
  the data distribution differs, and that is worth knowing before you ship it.
- **Test with production-sized bounds.** A historical query tested over one hour and deployed
  over ninety days is not the same query.

## Checklist

Before a SWQL query goes into a report, an alert, a dashboard or a script:

1. Is the result set bounded, by `TOP` or by `WITH ROWS`?
2. Does `ORDER BY` make the bound deterministic?
3. Are the selected columns the ones you need, and none of them
   `AncestorDisplayNames` or `AncestorDetailsUrls` on a large result?
4. Do the `WHERE` predicates compare bare columns, with no function wrapping the column?
5. If the entity inherits from `System.StatisticsEntity`, is there a time bound **and** an
   object bound?
6. Is the time bound a half-open range (`>= start AND < end`) on the entity's own timestamp
   column, whatever it happens to be called?
7. Is every non-aggregate condition in `WHERE` rather than `HAVING`?
8. Is any navigation path more than two segments deep, or to-many? If so, would an explicit join
   or a subquery be clearer and cheaper?
9. Are all values bound as parameters rather than concatenated into the query text?
10. Does the query run as the account that will actually run it in production
    ([gotchas.md](gotchas.md#1-the-empty-result-set-is-usually-a-permissions-answer))?

Then check the names without touching a server:

```bash
python3 tools/validate_swql.py my-query.swql
```

## Next

- [gotchas.md](gotchas.md) for the queries that are fast and wrong.
- [joins-and-navigation.md](joins-and-navigation.md) for cardinality and worked joins.
- [date-and-time.md](date-and-time.md) for building time bounds that are correct.
- [../swis/rest-api.md](../swis/rest-api.md) for paging and parameter binding over HTTP.
- [../swis/bulk-operations.md](../swis/bulk-operations.md) for when the answer is not a query at
  all.

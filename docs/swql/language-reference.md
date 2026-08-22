# SWQL language reference

A clause-by-clause reference for SolarWinds Query Language, with runnable examples against
the 2026.2 schema. Every entity, property and navigation name here was resolved against
`data/schema/2026.2/` before it was written.

For what SWQL is and how it differs from T-SQL in outline, start at
[README.md](README.md). For the part people spend the most time on, see
[joins-and-navigation.md](joins-and-navigation.md).

## How this page marks its evidence

SolarWinds does not publish a formal SWQL grammar. What it does publish is the
[SWQL function reference](https://solarwinds.github.io/OrionSDK/docs/swql-functions/), a set
of worked examples in the [REST](https://solarwinds.github.io/OrionSDK/docs/rest/) and
[possible issues](https://solarwinds.github.io/OrionSDK/docs/swql-functions/possible-issues/)
pages, dozens of sample scripts in the
[OrionSDK repository](https://github.com/solarwinds/OrionSDK/tree/master/Samples), and the
source of SWQL Studio, whose autocomplete keyword list
(`Src/SwqlStudio/Autocomplete/Grammar.cs`) enumerates the words the language recognises.

Where a clause appears in a SolarWinds example, this page says so. Where a keyword appears
only in SWQL Studio's list, it is marked **attested, not documented**. Where a construct
could not be corroborated at all, it is marked **unverified** with a one-line note on how to
confirm it on your own server rather than being quietly dropped or quietly asserted.

## Statement shape

```text
SELECT [DISTINCT] [TOP n] <column list>
FROM <Entity> [[AS] alias]
[<join> <Entity> [[AS] alias] ON <predicate>] ...
[WHERE <predicate>]
[GROUP BY <expression list>]
[HAVING <predicate>]
[ORDER BY <expression> [ASC | DESC] [, ...]]
[UNION <select statement>]
[WITH <query option> ...]
```

`WITH` is a trailing modifier here, not the leading `WITH` of a T-SQL common table
expression.

## SELECT

### Column lists

There is no `SELECT *`. Name every column. An entity such as `Orion.Nodes` carries 102
properties, so a wildcard would make every query on it a worst case, and naming columns also
means a module upgrade that adds a property cannot change your result shape underneath you.

```sql
SELECT TOP 10 NodeID, Caption, IPAddress
FROM Orion.Nodes
ORDER BY Caption
```

Columns may be bare properties, dotted navigation paths, function calls, arithmetic, or
`CASE` expressions.

### Aliasing with AS

`AS` is optional in T-SQL and conventional here. Alias anything computed, anything dotted,
and anything whose name would otherwise collide, because the response column names come
straight from the `SELECT` list.

```sql
SELECT TOP 10
    n.NodeID            AS Id,
    n.Caption           AS Name,
    n.IPAddress         AS Address,
    n.Engine.ServerName AS PollingEngine
FROM Orion.Nodes n
ORDER BY n.Caption
```

Without the alias, `n.Engine.ServerName` would arrive as a column named `ServerName`, which
is fine until you also select `n.Caption AS ServerName` somewhere and one silently wins.

Square brackets quote an alias that contains spaces or reserved words. SolarWinds' own
documentation uses this form (`GETUTCDATE() AS [Time_Now]`):

```sql
SELECT TOP 10 n.Caption AS [Node Name], n.Vendor AS [Hardware Vendor]
FROM Orion.Nodes n
ORDER BY n.Caption
```

### DISTINCT

`DISTINCT` applies to the whole row, as in SQL.

```sql
SELECT DISTINCT n.Vendor
FROM Orion.Nodes n
ORDER BY n.Vendor
```

`DISTINCT` is the standard repair for the row multiplication that a to-many navigation or
join produces. See
[joins-and-navigation.md](joins-and-navigation.md#a-to-many-navigation-multiplies-rows).

### TOP n

`TOP` goes immediately after `SELECT` (and after `DISTINCT` if both are present). There is
no `LIMIT` and no `OFFSET`. SolarWinds' own examples use it constantly, from
`SELECT TOP 10 DisplayName FROM System.ManagedEntity ORDER BY DisplayName` in the
[About SWIS](https://solarwinds.github.io/OrionSDK/docs/about-swis/) page to
`SELECT TOP 1 AlertObjectID FROM Orion.AlertActive ORDER BY TriggeredDateTime DESC` in the
C# sample.

`TOP` without `ORDER BY` returns an arbitrary n rows, not the first n by any meaningful
ordering. If you care which rows you get, order them.

```sql
SELECT TOP 25 n.Caption, n.Status, n.LastBoot
FROM Orion.Nodes n
ORDER BY n.Status ASC, n.LastBoot DESC
```

Bound your result sets as a habit. Statistics, event and history entities are the largest
tables in an Orion installation, and an unbounded query against them is felt by everyone
using the web console.

## FROM and aliases

One entity name, optionally followed by an alias, optionally with `AS`. All three of
`FROM Orion.Nodes AS Nodes`, `FROM Orion.Nodes Nodes` and a bare `FROM Orion.Nodes` are
valid and equivalent. Spelled out, the first is:

```sql
SELECT TOP 5
    Nodes.NodeID,
    Nodes.Caption
FROM Orion.Nodes AS Nodes
ORDER BY Nodes.Caption
```

The full entity name and its last segment also work as qualifiers without any alias at all
(`Orion.Nodes.Caption`, `Nodes.Caption`), but a short explicit alias is easier to read and
avoids ambiguity once a second entity joins the query.

Entity names are namespaced and dotted: `Orion.Nodes`, `Orion.NPM.Interfaces`,
`NCM.NodeProperties`, `Metadata.Entity`. Match the schema's capitalisation. Property names
and keywords are treated case insensitively in SolarWinds' own samples (`order by nodeid`,
`Interfaces.URI`), but matching the documented casing keeps queries greppable and lets
`tools/validate_swql.py` resolve them without warnings.

## Joins

`INNER`, `LEFT`, `RIGHT`, `FULL` and `OUTER` are all SWQL keywords, recognised by SWQL
Studio and used in SolarWinds' own samples (`JOIN Orion.VolumesCustomProperties vcp ON
v.VolumeID = vcp.VolumeID` in `SetVolumeCustomProperty.ps1`). A bare `JOIN` means
`INNER JOIN`.

Before writing an `ON` clause, check whether a navigation property already exists for the
relationship. Most of the joins people write by hand in SWQL are already declared in the
schema, and using the navigation is shorter, less error prone, and expresses the intended
cardinality. [joins-and-navigation.md](joins-and-navigation.md) covers when to use which.

### INNER JOIN

```sql
SELECT TOP 50
    n.Caption AS NodeCaption,
    i.Name    AS InterfaceName,
    i.InPercentUtil,
    i.OutPercentUtil
FROM Orion.Nodes n
INNER JOIN Orion.NPM.Interfaces i ON n.NodeID = i.NodeID
ORDER BY n.Caption, i.Name
```

### LEFT JOIN

Keeps every row from the left entity, filling the right side with nulls where there is no
match. This is how you ask "which nodes have no applications" rather than "which nodes have
applications".

```sql
SELECT TOP 100
    n.Caption,
    a.Name AS ApplicationName
FROM Orion.Nodes n
LEFT JOIN Orion.APM.Application a ON a.NodeID = n.NodeID
ORDER BY n.Caption
```

The anti-join form, which is usually what you actually wanted:

```sql
SELECT TOP 100 n.Caption, n.IPAddress
FROM Orion.Nodes n
LEFT JOIN Orion.APM.Application a ON a.NodeID = n.NodeID
WHERE a.ApplicationID IS NULL
ORDER BY n.Caption
```

Note that a predicate on the right-hand entity in the `WHERE` clause turns a `LEFT JOIN`
back into an inner join, exactly as in SQL, because null fails every comparison except
`IS NULL`. Put right-side filters in the `ON` clause if you want to keep the unmatched rows.

### RIGHT JOIN

`RIGHT JOIN` is the mirror image of `LEFT JOIN`. It is legal and almost never the clearest
way to say what you mean: swapping the two entities and using `LEFT JOIN` reads better and
is easier to review.

### FULL OUTER JOIN

Keeps unmatched rows from both sides. The useful case is reconciling two inventories that
should agree, such as the platform's node list against the NCM node list:

```sql
SELECT TOP 100
    n.Caption AS OrionNode,
    np.NodeID AS NcmNodeId
FROM Orion.Nodes n
FULL OUTER JOIN NCM.NodeProperties np ON np.CoreNodeID = n.NodeID
WHERE n.NodeID IS NULL OR np.CoreNodeID IS NULL
```

`NCM.NodeProperties.NodeID` is a `System.Guid` and `NCM.NodeProperties.CoreNodeID` is the
`System.Int32` that matches `Orion.Nodes.NodeID`. Joining on the wrong one of those two
returns nothing and no error, which is the most common way this query goes wrong.

### CROSS JOIN

**Unverified.** `CROSS` does not appear in SolarWinds' documentation, in the SDK samples, or
in SWQL Studio's keyword list, and this repository has no evidence that SWQL accepts it. Do
not assume it works. If you need a Cartesian product, confirm it first by running
`SELECT TOP 1 a.StatusId, b.StatusId FROM Orion.StatusInfo a CROSS JOIN Orion.StatusInfo b`
in SWQL Studio against your own server; a parse error is the answer. In practice a join
predicate that is always true, or a join through `Orion.StatusInfo`, covers most of what a
cross join would be used for here.

## WHERE

### Comparison operators

| Operator | Meaning | Evidence |
|:---|:---|:---|
| `=` | Equal | Used throughout the official samples |
| `!=` | Not equal | `WHERE Interfaces.Status != 1` in `Interface.Cleanup.ps1`; `WHERE ISNULL(Acknowledged,0)!=1` in the C# sample |
| `<>` | Not equal | **Unverified.** The standard SQL spelling, but it appears in no SolarWinds documentation page, no SDK sample and no SWQL Studio source available here, and SWQL Studio's keyword list covers keywords, not operators. Confirm it on your own server with `SELECT TOP 1 NodeID FROM Orion.Nodes WHERE Status <> 1`; a parse error is the answer. `!=` is the form SolarWinds itself writes |
| `>`, `<`, `>=`, `<=` | Ordering comparisons | Standard |

```sql
SELECT TOP 100 n.Caption, n.IPAddress, n.Status, n.Vendor
FROM Orion.Nodes n
WHERE n.Status != 1
  AND n.UnManaged = FALSE
  AND n.Vendor IN ('Cisco', 'Juniper')
  AND n.Caption LIKE 'core-%'
  AND n.Location IS NOT NULL
  AND n.CPULoad BETWEEN 50 AND 100
ORDER BY n.Caption
```

`Status = 1` is Up and `Status = 2` is Down. `Orion.Nodes.Status` is a `System.Int32`, not a
string; the full mapping is in [../reference/status-codes.md](../reference/status-codes.md).

### Boolean literals

`TRUE` and `FALSE` are SWQL keywords and compare directly against `System.Boolean`
properties. `n.UnManaged = FALSE` is the idiomatic way to exclude objects that are only
"down" because someone put them into a maintenance window.

### IN and NOT IN

```sql
SELECT TOP 100 n.Caption, n.Status
FROM Orion.Nodes n
WHERE n.Status NOT IN (1, 9, 11)
ORDER BY n.Caption
```

Status 1 is Up, 9 is Unmanaged and 11 is External, so this is "genuinely not healthy, and
not excluded on purpose".

`IN` also accepts a subquery, and, uniquely to SWQL, a single multi-valued query parameter.
See [Query parameters](#query-parameters) below.

### LIKE

`%` matches any run of characters including none; `_` matches exactly one character. There
is no `*`, no `?` and no regular expression support.

```sql
SELECT DefinitionID
FROM Orion.ContainerMemberDefinition
WHERE ContainerID = @containerID AND Name LIKE 'Unreachable%'
```

That is SolarWinds' own `Groups.ps1` sample, unchanged. Case sensitivity follows the Orion
database collation, so if a match has to be case insensitive regardless of collation, apply
`ToUpper()` or `ToLower()` to both sides.

### IS NULL and IS NOT NULL

Null never equals anything, including null, so `= NULL` is always false. Use `IS NULL` and
`IS NOT NULL`. `IsNull(a, b)` is the function form that substitutes a default, and it is the
one SolarWinds uses in the C# sample: `WHERE ISNULL(Acknowledged,0)!=1`.

### BETWEEN

`BETWEEN a AND b` is inclusive at both ends. It works for numbers and for dates, and for
dates it is the readable way to express a window without repeating the column.

### AND, OR, NOT

Standard precedence: `NOT` binds tighter than `AND`, which binds tighter than `OR`.
Parenthesise any mixed expression, because the bug this produces is silent.

```sql
SELECT TOP 100 n.Caption, n.Status, n.Vendor
FROM Orion.Nodes n
WHERE n.UnManaged = FALSE
  AND (n.Status = 2 OR n.Status = 12)
ORDER BY n.Caption
```

Status 12 is Unreachable, meaning the object's own status could not be determined because
something it depends on is down.

## GROUP BY and HAVING

Aggregates are `Avg`, `Count`, `Max`, `Min`, `Sum` and `String_Agg`. With no `GROUP BY`
they operate over the whole result; with one, over each group.

```sql
SELECT
    n.Vendor,
    COUNT(n.NodeID) AS NodeCount,
    AVG(n.CPULoad)  AS AvgCpuLoad
FROM Orion.Nodes n
WHERE n.Vendor IS NOT NULL
GROUP BY n.Vendor
HAVING COUNT(n.NodeID) > 5
ORDER BY COUNT(n.NodeID) DESC
```

`WHERE` filters rows before grouping; `HAVING` filters groups after. Aggregate conditions
belong in `HAVING`, row conditions belong in `WHERE`, and moving a row condition into
`HAVING` makes the query slower for no benefit.

`Count(n)` counts non-null values, so counting a nullable column and counting the key give
different answers. Count the key.

Note that repeating the aggregate expression in `ORDER BY` rather than ordering by the alias
is the form used in this repository's verified samples, and it is the form that always
works.

## ORDER BY

```sql
SELECT TOP 25 n.Caption, n.Status, n.LastBoot
FROM Orion.Nodes n
ORDER BY n.Status ASC, n.LastBoot DESC
```

`ASC` is the default and may be omitted. Multiple keys are comma separated and applied left
to right. Sorting strings uses the database collation, so the position of mixed case and
accented values is a property of the installation, not of the query.

For status, ordering by the raw integer is not severity order. `Orion.StatusInfo.Ranking`
exists precisely for this: join to it and order by `Ranking` to get worst-first ordering that
matches the web console. See
[joins-and-navigation.md](joins-and-navigation.md#example-8-status-integers-to-status-names).

## WITH ROWS and WITH TOTALROWS

`WITH` clauses trail the whole statement, after `ORDER BY`.

```sql
SELECT Uri
FROM Orion.Pollers
ORDER BY PollerID
WITH ROWS 1 TO 3 WITH TOTALROWS
```

That is the query from SolarWinds'
[REST documentation](https://solarwinds.github.io/OrionSDK/docs/rest/), which returns three
rows out of thirteen, so the bounds are **1-based and inclusive**. `WITH TOTALROWS` adds a
`totalRows` member to the response envelope carrying the count the query would have returned
without the window, which is what lets a client compute how many pages there are.

Always pair `WITH ROWS` with a deterministic `ORDER BY`. Without one, page 2 is not
guaranteed to continue where page 1 stopped.

The request and response shapes are covered in
[../swis/rest-api.md](../swis/rest-api.md#paging-with-with-rows-and-with-totalrows).

## WITH LOGS

Appends server-side diagnostic logging for the query to the result. SolarWinds uses it in
its own worked example on the
[possible issues](https://solarwinds.github.io/OrionSDK/docs/swql-functions/possible-issues/)
page:

```sql
SELECT
    EngineID,
    ServerName,
    IP,
    ServerType,
    GETUTCDATE() AS [Time_Now],
    TOUTC(ADDMINUTE(-10, TOLOCAL(GETUTCDATE()))) AS [Time_Past_Minute]
FROM Orion.Engines
WHERE ServerType = 'Primary'
WITH LOGS
```

That example is also the canonical demonstration of the date arithmetic trap: `ADDMINUTE`
compiles to T-SQL `DATEADD`, which is timezone blind, so the value has to be brought to
local time, adjusted, and pushed back to UTC. See [date-and-time.md](date-and-time.md).

## Other WITH options

| Option | Status |
|:---|:---|
| `WITH ROWS a TO b` | Documented, in the official REST example |
| `WITH TOTALROWS` | Documented, in the official REST example |
| `WITH LOGS` | Documented, in the official possible-issues example |
| `WITH NOPLANCACHE` | **Attested, not documented.** `noplancache` is in SWQL Studio's keyword list. Presumably suppresses reuse of a cached query plan |
| `WITH QUERYPLAN` | **Attested, not documented.** `queryplan` is in SWQL Studio's keyword list, and SWQL Studio has a "Query Plan" result tab |
| `WITH QUERYSTATS` | **Attested, not documented.** `querystats` is in SWQL Studio's keyword list, and SWQL Studio has a "Query Stats" result tab |
| `WITH LIMITATION ...` | **Attested, not documented.** `limitation` is in SWQL Studio's keyword list; its syntax and effect are not published |
| `WITH SCHEMAONLY` | **Unverified.** It appears in community usage and in this repository's own validator keyword list, but not in any SolarWinds documentation, sample or source available here. Confirm on your own server by running a query with and without it and comparing the response |

To check any of these on your server, run the statement in SWQL Studio. A rejected clause
produces a parse error immediately, which is a cheap and definitive test.

## UNION

The official function reference documents `UNION(q)` as "adds the results of an additional
query `q` directly below the former"; the column counts must match. Written as a statement
that is:

```sql
SELECT n.Caption AS ObjectName, n.Status AS StatusId
FROM Orion.Nodes n
WHERE n.Status = 2
UNION
SELECT i.Caption AS ObjectName, i.Status AS StatusId
FROM Orion.NPM.Interfaces i
WHERE i.Status = 2
```

Column names come from the first `SELECT`. Column counts and compatible types are your
responsibility, and a mismatch is a runtime error rather than something the schema can catch
for you.

**`UNION ALL` is unverified.** The official reference documents only `UNION`. If you need
duplicate rows preserved and cannot confirm `UNION ALL` on your version, add a discriminator
column to each branch so no two rows collide.

Before reaching for `UNION` across entity types, check whether a shared base entity already
gives you the same rows in one query. Nodes, interfaces, volumes and applications all
descend from `System.ManagedEntity`, so "everything that is down" is often one `SELECT`
rather than four unioned ones. See
[joins-and-navigation.md](joins-and-navigation.md#querying-a-base-entity).

## CASE

The official reference gives the form as `Case when c then a else b end`. Multiple `WHEN`
branches work as in SQL, evaluated top to bottom, first match wins.

```sql
SELECT TOP 20
    v.Caption,
    v.VolumeSize,
    v.VolumeSpaceUsed,
    ROUND(v.VolumePercentUsed, 1) AS PercentUsed,
    CASE
        WHEN v.VolumePercentUsed >= 90 THEN 'critical'
        WHEN v.VolumePercentUsed >= 75 THEN 'warning'
        ELSE 'ok'
    END AS Band
FROM Orion.Volumes v
WHERE v.VolumeSize > 0
ORDER BY v.VolumePercentUsed DESC
```

All branches must yield compatible types. `ELSE` is optional; without it, an unmatched row
yields null.

Whether the simple form, `CASE Severity WHEN 2 THEN ...`, is also accepted **is unverified
here**. The official reference gives only the searched form above, and the schema does not
record grammar, so this repository cannot settle it. Write the searched form: it is the
documented one, it costs a repeated column reference, and it works everywhere the simple
form would. If you want to know for your own version, run both against a small entity:

```sql
SELECT TOP 1 CASE WHEN n.Status = 1 THEN 'up' ELSE 'other' END AS Searched
FROM Orion.Nodes n
```

`CASE` also works in `WHERE`, `GROUP BY` and `ORDER BY`, which is how you get a custom sort
order without adding a column to the model.

## Subqueries

### IN with a subquery

```sql
SELECT TOP 50 n.Caption, n.IPAddress
FROM Orion.Nodes n
WHERE n.NodeID IN (
    SELECT i.NodeID
    FROM Orion.NPM.Interfaces i
    WHERE i.Status = 2
)
ORDER BY n.Caption
```

The subquery must return exactly one column. This is the readable way to express "nodes that
have at least one down interface" without a join that multiplies rows, and it needs no
`DISTINCT`.

### EXISTS and NOT EXISTS

`exists` is in SWQL Studio's keyword list, so the correlated form is recognised. Mark this
one **attested, not documented**: no SolarWinds documentation page or sample in this
repository's sources uses it. This repository's own recipe pages, however, lean on the
negated form routinely:
[cookbook.md](../guides/cookbook.md), [node-management.md](../automation/node-management.md)
and [standard-pollers.md](../polling/standard-pollers.md) all ship `NOT EXISTS` queries as
ready-to-run recommendations. Treat the construct as reliable in practice, while
remembering that the attestation is this repository's usage plus the keyword list, not a
SolarWinds documentation page.

```sql
SELECT TOP 50 n.Caption
FROM Orion.Nodes n
WHERE EXISTS (
    SELECT a.ApplicationID
    FROM Orion.APM.Application a
    WHERE a.NodeID = n.NodeID AND a.Status = 2
)
ORDER BY n.Caption
```

The anti-join form, `NOT EXISTS`, is what those recipes use. This is
[standard-pollers.md](../polling/standard-pollers.md)'s "nodes that are not being polled at
all", unchanged:

```sql
SELECT n.NodeID, n.Caption, n.IPAddress, n.ObjectSubType, n.EngineID
FROM Orion.Nodes n
WHERE NOT EXISTS (
    SELECT p.PollerID
    FROM Orion.Pollers p
    WHERE p.NetObjectType = 'N'
      AND p.NetObjectID = n.NodeID
)
ORDER BY n.Caption
```

`any`, `some` and `all` are also in SWQL Studio's keyword list, which suggests the quantified
comparison forms are recognised. They are undocumented and untested here.

### Subqueries in FROM

**Unverified.** Nothing in the sources available here shows a derived table
(`FROM (SELECT ...) x`). Where you would reach for one, a subquery in `WHERE`, a `GROUP BY`
with `HAVING`, or a navigation property usually covers the need.

## Query parameters

Bind values; do not concatenate them into query text. Two reasons, in order of how often
they matter:

1. **Types survive.** A bound integer stays an integer and a bound `System.DateTime` stays a
   date, so you are not guessing at a literal date format that SWIS then has to parse.
2. **An injection class disappears.** SWQL cannot write data, so the blast radius is smaller
   than SQL injection, but an attacker who can shape your query text can still read entities
   your query never intended to touch.

Parameters are named with a leading `@` and supplied out of band by the client.

```sql
SELECT n.NodeID, n.Caption, n.IPAddress
FROM Orion.Nodes n
WHERE n.Vendor = @vendor
  AND n.Status = @status
ORDER BY n.Caption
```

Over REST that is a `POST /Query` with `{"query": "...", "parameters": {"vendor": "Cisco",
"status": 2}}`. In PowerShell it is a hash table:
`Get-SwisData $swis $query @{ vendor = 'Cisco'; status = 2 }`. In Python the client turns
keyword arguments into the same object. Full detail in
[../swis/rest-api.md](../swis/rest-api.md#parameter-binding).

### Multi-valued parameters for IN

A single parameter can carry a whole list. Note the syntax carefully: **no parentheses
around the parameter.**

```sql
SELECT n.NodeID, n.Caption
FROM Orion.Nodes n
WHERE n.NodeID IN @ids
ORDER BY n.Caption
```

`{"parameters": {"ids": [2, 4, 6]}}` supplies the list. This is SolarWinds' own pattern; the
`BulkEnableAssetInventory` Go sample uses `SELECT NodeID FROM Orion.Nodes WHERE IPAddress IN
@ipaddresses` with a string array bound to `ipaddresses`.

This is the right way to fetch a specific set of objects in one round trip, and it composes
well with `WITH ROWS` when the set is large enough to need chunking.

### Where parameters cannot go

A parameter is a value, not a fragment of the query. Entity names, property names, and the
unit argument of `AddDate` cannot be parameterised. SolarWinds says so explicitly for the
last of these: in `AddDate(u, n, d)`, "the `u` argument must be a string literal. It can't be
a query parameter or value derived from the data."

## Data types in results

SWIS property types are .NET type names, and the schema records the exact type for each of
the 19328 properties. This is the distribution across 2026.2, which is a useful sense of what
you will actually encounter:

| Type | Properties | Notes |
|:---|---:|:---|
| `System.String` | 6732 | |
| `System.Int32` | 5078 | Includes the `Status` declared on `System.DashboardEntity`, and so the `Status` of every managed entity |
| `System.Double` | 1946 | |
| `System.Int64` | 1679 | `Orion.APM.Component.ComponentID`, `Orion.AlertActive.AlertActiveID` |
| `System.DateTime` | 1301 | |
| `System.Boolean` | 942 | |
| `System.Single` | 752 | |
| `System.Guid` | 390 | |
| `System.Byte` | 214 | `Orion.AlertActive.Status` is one of these |
| `System.Int16` | 169 | |
| `System.Decimal` | 29 | |
| `System.Char` | 24 | Often a single-letter flag such as `'Y'` or `'N'` |
| `System.Byte[]` | 21 | Binary; `Orion.Events.TimeStamp` is a row version, not a date |
| `System.String[]` | 17 | `System.ManagedEntity.AncestorDisplayNames` |
| `System.Type` | 10 | `System.Entity.InstanceType` |
| `System.Uri` | 9 | `Orion.ContainerMembers.MemberUri` |
| `System.Int32[]` | 2 | |
| `System.UInt32` | 2 | |

A query that touches most of the interesting ones:

```sql
SELECT TOP 5
    n.NodeID,
    n.Caption,
    n.IPAddressGUID,
    n.LastBoot,
    n.PercentMemoryUsed,
    n.UnManaged,
    n.InstanceType,
    n.AncestorDisplayNames
FROM Orion.Nodes n
```

### System.DateTime

Dates come back as ISO 8601 strings. The offset they carry depends on how the value was
produced, and this is not cosmetic. In SolarWinds' own worked example, `GETUTCDATE()`
serialises as `2024-05-17T10:37:27.8070000Z` while `DateAdd(minute,-10,GETUTCDATE())` in the
same row serialises as `2024-05-17T10:27:27.8070000-05:00`, because T-SQL `DATEADD` discards
the UTC-ness of its input and the server stamps its own offset on the way out. Read
[date-and-time.md](date-and-time.md) before writing any time-bounded query.

Bind dates as parameters rather than formatting literals, so the client library's date type
does the conversion.

### System.Guid

Surfaces as a string. `Orion.Nodes.IPAddressGUID`, `Orion.AlertConfigurations.AlertRefID` and
`Orion.AgentManagement.Agent.AgentGuid` are all Guids. So is `NCM.NodeProperties.NodeID`,
which is why joining NCM to the platform uses `NCM.NodeProperties.CoreNodeID` instead.

### System.String

Plain strings. Comparison and sort behaviour comes from the Orion database collation, not
from SWQL. String functions available are `CharIndex`, `Concat`, `Length`, `Replace`,
`SubString`, `ToLower`, `ToString`, `ToUpper`, `UriEquals` and `EscapeSWISUriValue`, all
listed in [../reference/swql-function-index.md](../reference/swql-function-index.md).

### System.Int32 and the other integer types

On a managed entity `Status` is always an integer, never a name: it is declared
`System.Int32` on `System.DashboardEntity` and no descendant redeclares it as anything else.
Join `Orion.StatusInfo` to make it readable;
[../reference/status-codes.md](../reference/status-codes.md) has the full table.

Outside that hierarchy the name is not reserved and the width is not guaranteed.
`Orion.AlertActive.Status` is a `System.Byte` and `Orion.Batching.Actions.Status` is a
`System.String`, so check the type before assuming. Watch the width when joining too:
`Orion.ContainerMembers.MemberPrimaryID` is a `System.Int64` while `Orion.Nodes.NodeID` is a
`System.Int32`, and `Orion.APM.Component.ComponentID` is `System.Int64` while
`Orion.APM.Component.ApplicationID` is `System.Int32`.

### Arrays

Array-typed properties come back as JSON arrays. Four functions operate on them:
`ArrayLength(a)`, `ArrayValueAt(a, i)` counting from zero, `ArrayContains(a, v)`, and
`SplitStringToArray(a)`.

```sql
SELECT TOP 10
    cm.Name,
    ARRAYLENGTH(cm.MemberAncestorDisplayNames)     AS AncestorCount,
    ARRAYVALUEAT(cm.MemberAncestorDisplayNames, 0) AS FirstAncestor
FROM Orion.ContainerMembers cm
```

`ArrayValueAt` fails the query if the index is out of range, so guard it with `ArrayLength`
rather than assuming an element exists.

`SplitStringToArray` carries a discrepancy worth knowing about: the official reference says
it splits on commas, while the community workbook example recorded next to it in
`data/reference/swql-functions.json` splits `'Hello|§|§|world'` into `[Hello, world]`.
Verify the delimiter on your version before depending on it.

### System.Type

`InstanceType` is the concrete entity type of the row, filled in by SWIS. It is what makes a
base-entity query useful, because it tells you which descendant each row actually came from.

### System.Byte[] and PropertyBag

Avoid selecting these unless you specifically want them. `Orion.Events.TimeStamp` is a
`System.Byte[]` used for database concurrency control, not a date, and the name misleads
people into using it as one. `SolarWinds.InformationService.PropertyBag` properties such as
`Orion.AlertIndication.UserProperties` carry a nested structure rather than a scalar.

## Comments

`--` introduces a line comment. SWQL Studio highlights line comments with the SQL lexer, and
the sample files in [../../scripts/swql/](../../scripts/swql/) use them throughout. Whether
a given client strips them before transmission is a client concern; over REST the comment
text is part of the query string and must be URL encoded like anything else.

## Reserved words

The words SWQL Studio recognises as language keywords, and therefore the ones to avoid as
bare identifiers or aliases:

```text
all      and      any      as       asc      auto     between  by       case
class    desc     distinct else     end      exists   false    from     full
group    having   in       inner    into     is       isa      join     left
like     limitation        noplancache        not     null     on       or
order    outer    queryplan         querystats         raw     return   right
rows     select   set      some     then     to       top      totalrows
true     union    when     where    with     xml
```

If a property name collides with one of these, bracket it: `[Set]`. Aliases containing
spaces need brackets too.

`isa` is interesting and undocumented: its presence alongside the inheritance model suggests
a type test operator. Treat it as **attested, not documented**. The supported way to filter a
base-entity query by concrete type is `InstanceType`, described in
[joins-and-navigation.md](joins-and-navigation.md#filtering-a-base-entity-query-by-type).

## Verifying anything on this page

Offline, against the extracted schema:

```bash
python3 tools/schema_query.py show Orion.Nodes
python3 tools/schema_query.py props Orion.Volumes --grep percent
python3 tools/schema_query.py path Orion.APM.Component Orion.Nodes
python3 tools/validate_swql.py docs/swql/language-reference.md
```

Online, against the server you are actually targeting:

```sql
SELECT p.Name, p.Type, p.IsNavigable, p.IsKey, p.IsInherited
FROM Metadata.Property p
WHERE p.Entity.FullName = 'Orion.Nodes'
ORDER BY p.Name
```

`Metadata.Entity.GetAliases` will also tell you how SWIS resolved the aliases in a query,
which is a quick way to confirm that a `FROM` clause bound the entity you expected. Its
single parameter is the query text; see
[../reference/verb-index.md](../reference/verb-index.md).

## Next

- [joins-and-navigation.md](joins-and-navigation.md) for navigation properties, cardinality,
  and worked joins across the common entity pairings.
- [functions.md](functions.md) for the function library.
- [date-and-time.md](date-and-time.md) for time-bounded queries.
- [../../scripts/swql/](../../scripts/swql/) for verified samples by subject area.

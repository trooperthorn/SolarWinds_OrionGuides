# SolarWinds Query Language (SWQL)

SWQL is the query language of the SolarWinds Information Service. It is the only supported
read path into the Orion data model, and it is what alerts, reports, Modern Dashboards, the
REST `/Query` endpoint, `Get-SwisData` in PowerShell, and SWQL Studio all speak.

It looks enough like T-SQL that most people can write a working `SELECT` in the first
minute, and different enough that the second hour is spent finding out why something that
should obviously work does not. This section exists to compress that second hour.

This documentation covers SWIS schema version **2026.2**: 2067 entities, 19328 properties
and 2992 navigation relationships. Every entity, property and navigation name in these
pages was checked against the extracted schema in `data/schema/2026.2/` before it was
written, and every `sql` block is re-checked on every build by
[`tools/validate_swql.py`](../../tools/validate_swql.py).

## What SWQL actually queries

SWQL does not query tables. It queries **entities**, which are types in an inheritance
hierarchy that SWIS maps onto the Orion database. The distinction matters in four practical
ways:

1. **An entity can expose data that is not a column.** `Orion.Nodes.DetailsUrl` and
   `System.ManagedEntity.AncestorDisplayNames` are computed by SWIS, not stored.
2. **Entities inherit.** `Uri` is declared once on `System.Entity` and is queryable on all
   2043 entities that descend from it. `UnManaged`, `UnManageFrom` and `UnManageUntil` come
   from `System.ManagedEntity` and are queryable on the 174 entity types beneath it.
3. **Querying a base type returns rows from every type beneath it.** This is what makes
   "show me everything that is down, whatever kind of thing it is" a single query. See
   [joins-and-navigation.md](joins-and-navigation.md#querying-a-base-entity).
4. **Entities are linked by named navigation properties**, so a great deal of joining is
   done by writing a dotted path rather than an `ON` clause. This is the single highest
   leverage skill in SWQL and it has its own page:
   [joins-and-navigation.md](joins-and-navigation.md).

There is a second, less pleasant consequence. SWIS satisfies most queries by translating
SWQL into T-SQL and running it against the Orion database, so SQL Server behaviour leaks
through the abstraction. The official
[possible issues](https://solarwinds.github.io/OrionSDK/docs/swql-functions/possible-issues/)
page shows the generated T-SQL for a date query and explains exactly how a UTC timestamp
ends up carrying the SQL Server's local offset. That is not a bug you can work around by
writing better SWQL; it is a translation artefact you have to know about.

## The differences from T-SQL that actually bite

### SWQL is read only

There is no `INSERT`, `UPDATE`, `DELETE` or `MERGE`. SolarWinds states this plainly:
["The SWIS query interface is read-only and cannot be used to insert, update, or delete
data."](https://solarwinds.github.io/OrionSDK/docs/about-swis/)

Every change goes through a different interface: CRUD on a URI, a verb through Invoke, or
`BulkUpdate`/`BulkDelete`. If you are trying to phrase a mutation as a query, you are on the
wrong interface. See [../swis/crud.md](../swis/crud.md) and
[../swis/rest-api.md](../swis/rest-api.md#invoke).

### There is no `SELECT *`

Name your columns. Every one of them.

```sql
SELECT TOP 10 NodeID, Caption, IPAddress
FROM Orion.Nodes
ORDER BY Caption
```

This is a nuisance the first time and a feature afterwards. An entity such as `Orion.Nodes`
has 102 properties, several of which are expensive to materialise, and a wildcard would make
every query on it a worst case. It also means a query never silently changes shape when a
module upgrade adds a property.

To find out what you can name, look it up rather than guessing:

```bash
python3 tools/schema_query.py props Orion.Nodes
python3 tools/schema_query.py props Orion.Nodes --grep memory
```

### `TOP n`, not `LIMIT`

SWQL uses the T-SQL spelling. `TOP` goes immediately after `SELECT`, and there is no
`OFFSET`.

```sql
SELECT TOP 25 n.Caption, n.Status, n.LastBoot
FROM Orion.Nodes n
ORDER BY n.Status ASC, n.LastBoot DESC
```

For paging, SWQL has its own trailing clause instead: `WITH ROWS <first> TO <last>`,
optionally with `WITH TOTALROWS` to get the unwindowed count back in the response envelope.
Both appear in SolarWinds' own [REST examples](https://solarwinds.github.io/OrionSDK/docs/rest/):

```sql
SELECT Uri
FROM Orion.Pollers
ORDER BY PollerID
WITH ROWS 1 TO 3 WITH TOTALROWS
```

The bounds are 1-based and inclusive. Full detail in
[language-reference.md](language-reference.md#with-rows-and-with-totalrows).

### String literals are single quoted

`'Cisco'` is a string. `"Cisco"` is not a SWQL string literal, and double quotes are also
what you have to escape in JSON request bodies, which is a good reason never to reach for
them. Escape an embedded quote by doubling it: `'O''Brien'`.

Square brackets are used for aliases and identifiers that need quoting, exactly as in
T-SQL. SolarWinds' own documentation example uses them:
`GETUTCDATE() AS [Time_Now]`.

### `LIKE` uses `%` and `_`

`%` matches any run of characters, `_` matches exactly one. There is no `*`, no `?`, and no
regular expression support. From SolarWinds' own `Groups.ps1` sample:

```sql
SELECT DefinitionID
FROM Orion.ContainerMemberDefinition
WHERE ContainerID = @containerID AND Name LIKE 'Unreachable%'
```

Whether `LIKE` and `=` are case sensitive depends on the collation of the Orion database,
which is chosen at install time and is not something SWQL controls. Do not assume either
way. If a comparison has to be case insensitive regardless of collation, force it with
`ToUpper()` or `ToLower()` on both sides.

### There is no DDL and no stored procedure surface

You cannot create a table, declare a variable, create a temp table, write a `WHILE` loop, or
call a stored procedure. The operations that a T-SQL developer would reach for a stored
procedure to do are exposed instead as **verbs** on entities, invoked over a separate
interface: `Orion.Nodes.Unmanage`, `Orion.AlertActive.Acknowledge`,
`Orion.NodesCustomProperties.CreateCustomProperty`. In 2026.2 there are 958 of them, 794
with typed parameters. They are documented in
[../reference/verb-index.md](../reference/verb-index.md).

Note also that `WITH` in SWQL is a **trailing** modifier (`... WITH TOTALROWS`), not the
leading `WITH` of a T-SQL common table expression. No CTE form is documented for SWQL.

### The underlying store is SQL Server, and it shows

Three leaks are worth knowing before they cost you an afternoon:

- **`DATEADD` is timezone blind.** SWQL's `AddMinute`, `AddHour` and friends compile to
  T-SQL `DATEADD`, which has no concept of the offset attached to the value it is given. Mix
  `GetUtcDate()` with an `AddX` function and the result comes back stamped with the SQL
  Server's local offset rather than UTC. SolarWinds documents this, shows the generated
  T-SQL, and gives the fix (convert to local, add, convert back) on the
  [possible issues](https://solarwinds.github.io/OrionSDK/docs/swql-functions/possible-issues/)
  page. See [date-and-time.md](date-and-time.md).
- **Collation drives string comparison and sort order.** Case sensitivity, accent
  sensitivity and the ordering of mixed-case results all come from the database collation,
  not from SWQL.
- **Numeric types are the SQL Server ones.** `Orion.Nodes.TotalMemory` is a
  `System.Single`, `Orion.Volumes.VolumeSize` is a `System.Double`, and
  `Orion.APM.Exchange.Mailbox.PercentageOfUsedQuota` is a `System.Decimal`. Rounding and
  accumulated float error behave accordingly, and `Round(n, p)` is the tool for making a
  displayed number stable.

### Results are filtered by who is asking

Orion account limitations are applied by SWIS on every query. Two accounts running the same
query legitimately get different rows. "The query returns nothing" is therefore often a
permissions answer rather than a data answer, and it is worth ruling out before debugging
the SWQL. This is a
[deliberate benefit](https://solarwinds.github.io/OrionSDK/docs/about-swis/) of going through
SWIS rather than the database, but it does make results non-reproducible across accounts.

## Where to run a query

| Surface | How | Notes |
|:---|:---|:---|
| SWQL Studio | Ships in the [Orion SDK installer](https://github.com/solarwinds/OrionSDK/releases) | Best place to explore; shows the entity tree and result grid |
| REST | `GET /Query?query=...` or `POST /Query` with a JSON body | See [../swis/rest-api.md](../swis/rest-api.md#query) |
| PowerShell | `Get-SwisData $swis $query @{ p = 1 }` | See [../swis/connecting.md](../swis/connecting.md#powershell) |
| Python | `swis.query(sql, p=1)` | See [../swis/connecting.md](../swis/connecting.md#python) |
| Alerts and reports | Custom SWQL trigger conditions and custom table resources | Same language, evaluated by the Orion server |

## This section

| Page | What it covers |
|:---|:---|
| [language-reference.md](language-reference.md) | Every clause: `SELECT`, `FROM`, joins, `WHERE`, `GROUP BY`, `HAVING`, `ORDER BY`, `TOP`, `WITH ROWS`, `UNION`, `CASE`, subqueries, parameters, and how the data types surface in results |
| [joins-and-navigation.md](joins-and-navigation.md) | Navigation properties versus explicit joins, cardinality and row multiplication, finding a path between two entities, inheritance-based querying, and worked joins for the common entity pairings |
| [functions.md](functions.md) | The built-in function library with worked examples |
| [date-and-time.md](date-and-time.md) | Time-bounding queries correctly, and the `GetUtcDate()` plus `AddX` trap |
| [gotchas.md](gotchas.md) | Constructs that run cleanly and return the wrong answer |
| [performance.md](performance.md) | Writing queries that do not hurt the database |

Related reading elsewhere in this repository:

- [../swis/README.md](../swis/README.md) for how the query interface relates to CRUD,
  Invoke and Bulk.
- [../swis/rest-api.md](../swis/rest-api.md) for the request and response contract,
  parameter binding and paging over HTTP.
- [../reference/entity-index.md](../reference/entity-index.md) to find an entity.
- [../reference/status-codes.md](../reference/status-codes.md) because `Status` is an
  integer and you will need the mapping.
- [../../scripts/swql/](../../scripts/swql/) for verified sample queries grouped by subject.

## Checking a query before you run it

Two commands, no server required. The first tells you what exists; the second tells you
whether what you wrote resolves against it.

```bash
# What is this entity, and what does it connect to?
python3 tools/schema_query.py show Orion.Nodes

# How do I get from here to there?
python3 tools/schema_query.py path Orion.APM.Component Orion.Nodes

# Does this query reference anything that does not exist?
echo "SELECT n.Caption, n.Node.Foo FROM Orion.Nodes n" | python3 tools/validate_swql.py -
```

```text
ERROR: Orion.Nodes has no property or navigation property named 'Node'.
       Closest members: nodeid, asanode, npmnode.
```

For the server actually in front of you, which may run a different platform version and a
different set of modules, ask it directly through the `Metadata.*` entities:

```sql
SELECT p.Name, p.Type, p.IsNavigable, p.IsKey
FROM Metadata.Property p
WHERE p.Entity.FullName = 'Orion.Nodes'
ORDER BY p.Name
```

More introspection queries are in
[../../scripts/swql/08-schema-introspection.swql](../../scripts/swql/08-schema-introspection.swql).

## Official sources

- [About SWIS](https://solarwinds.github.io/OrionSDK/docs/about-swis/)
- [SWQL functions](https://solarwinds.github.io/OrionSDK/docs/swql-functions/) and
  [possible issues](https://solarwinds.github.io/OrionSDK/docs/swql-functions/possible-issues/)
- [REST](https://solarwinds.github.io/OrionSDK/docs/rest/)
- [Schema reference](https://solarwinds.github.io/OrionSDK/2026.2/schema/index.html)
- [Orion SDK wiki](https://github.com/solarwinds/OrionSDK/wiki)

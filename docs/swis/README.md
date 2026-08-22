# The SolarWinds Information Service (SWIS)

The SolarWinds Information Service is the API for SolarWinds Orion, now shipped as
SolarWinds Observability Self-Hosted. It is a data access layer that sits in front of the
Orion database and exposes a hybrid object-oriented and relational model. It has its own
SQL-like query language, SolarWinds Query Language (SWQL).

Everything the Orion Web Console does, every alert action, every report, every integration
and every automation script ultimately goes through SWIS. If you are writing code against
Orion, SWIS is the contract you write against.

This guide documents SWIS schema version **2026.2**, which contains 2067 entities,
19328 properties, 958 verbs (794 of which publish typed parameters) and 2992 navigation
edges across 1501 relationship definitions. Each relationship is navigable from both ends,
which is why there are twice as many edges as definitions.

## Why SWIS instead of the SQL database

You can technically read the Orion database with a SQL client. You should not build on it.
SolarWinds gives four reasons in
[About SWIS](https://solarwinds.github.io/OrionSDK/docs/about-swis/), and each one has a
concrete operational consequence.

### Credentials

Direct database access needs SQL Server credentials that a DBA has to create, grant, rotate
and audit separately from Orion. SWIS uses the **same accounts you already manage in the
Orion Web Console**. Onboarding a new integration becomes "create an Orion account with the
right roles", not "file a ticket with the database team". Offboarding is one action in one
place.

### Account limitations

Orion administrators can attach *limitations* to an account that restrict which nodes,
interfaces and other objects it can see. SWIS enforces those limitations on every query, so
a query for nodes returns only the nodes that account is entitled to see. A direct SQL
connection has no idea limitations exist and will happily return everything. If you build a
multi-tenant or delegated-access tool on raw SQL, you are re-implementing (and eventually
mis-implementing) Orion's authorization model.

### Insulation from database schema changes

SWIS satisfies most queries by reading the database, but the mapping between SWIS entities
and the underlying tables is an indirection layer. SolarWinds can restructure `dbo.Nodes`
between releases and keep `Orion.Nodes` stable. Code written against SWIS survives upgrades
that would break code written against tables.

### Higher-level operation

The relational model alone cannot tell you that a node, an interface and an application are
all "managed objects" with an up/down status. SWIS adds an inheritance hierarchy that can.
`System.ManagedEntity` is described in the schema as "something that has an
externally-determined up/down status", and 174 entity types inherit from it in 2026.2. That
is what lets a tool such as Network Atlas put *any* managed object on a map without knowing
the specific type in advance.

## The entity inheritance hierarchy

Every SWIS entity type has a parent type, and the root of the tree is `System.Entity`.
`System.Entity` declares five properties that every other entity inherits: `DisplayName`,
`Description`, `InstanceType`, `Uri` and `InstanceSiteId`. SWIS fills in `InstanceType` and
`Uri` itself. Note that SolarWinds' own summary sentence for `System.Entity` still says it
defines *four* properties and names only the first four; `InstanceSiteId` is in the
published property table but was never added to that sentence. The table is the one to
trust, and it is what this repository extracts.

Querying a base type returns rows from every type beneath it:

```sql
SELECT TOP 10 DisplayName, InstanceType
FROM System.ManagedEntity
ORDER BY DisplayName
```

That returns nodes, interfaces, applications, groups and anything else that inherits from
`System.ManagedEntity`, with `InstanceType` telling you which concrete type each row came
from. `Orion.Nodes`, for example, has the inheritance chain
`System.Entity -> System.DashboardEntity -> System.ManagedEntity -> Orion.Nodes`.

You can see the chain for any entity with the repo's own tool:

```bash
python3 tools/schema_query.py show Orion.Nodes
python3 tools/schema_query.py children System.ManagedEntity
```

## The four interfaces

SWIS exposes four distinct interfaces. They are not interchangeable, and picking the wrong
one is the most common reason a script does not work.

| Interface | REST path | Direction | Use it for |
|:---|:---|:---|:---|
| Query | `GET /Query`, `POST /Query` | Read only | Anything you want to *read*, in any shape, across joins |
| CRUD | `POST /Create/{Entity}`, `GET /{uri}`, `POST /{uri}`, `DELETE /{uri}` | Read and write | Creating, reading, changing and removing single entity instances |
| Invoke | `POST /Invoke/{Entity}/{Verb}` | Write (mostly) | Operations that are more than a row edit: unmanage, poll now, acknowledge, deploy |
| Bulk | `POST /BulkUpdate`, `POST /BulkDelete` | Write | The same property change or delete applied to many URIs in one round trip |

### Query is read only

This is the single most important rule in SWIS. **The query interface cannot insert, update
or delete anything.** There is no `INSERT`, `UPDATE` or `DELETE` statement in SWQL. Every
change goes through CRUD, Invoke or Bulk. If you find yourself trying to write a SWQL
statement that modifies data, you are on the wrong interface.

See [rest-api.md](rest-api.md) for the query request and response contract, parameter
binding and paging.

### CRUD operates on URIs

Create takes an entity type name and a property bag, and returns the URI of the new
instance. Read, Update and Delete take URIs. It is a generic interface: the same four
operations work against any entity type that supports them, which is what makes generic
tooling possible.

Not every entity type supports CRUD. In 2026.2, 250 of the 2067 documented entities publish
a `/Create/{Entity}` REST path. See [crud.md](crud.md) for how to check a specific entity,
both offline against this repo's data and at runtime against your own server.

### Invoke runs verbs

Some entity types declare verbs: named operations with typed parameters. `Orion.AlertActive`
declares `Acknowledge(alertObjectIds, notes)`, `Orion.Nodes` declares
`Unmanage(netObjectId, unmanageTime, remanageTime, isRelative, allowOverlapping)` and
`PollNow(netObjectId)`. Going through SWIS rather than the database means the verb can check
that the caller is allowed to perform the operation and can record who did it and when.
`Orion.Nodes.Unmanage`, for example, requires the `allowUnmanage` right.

Verb arguments over REST are **positional**, sent as a JSON array, not named. This is a
frequent source of bugs. Check the exact order before you call:

```bash
python3 tools/schema_query.py verb Orion.Nodes Unmanage
python3 tools/schema_query.py verbs --entity Orion.AlertActive
```

Of the 958 verbs in 2026.2, 794 publish typed parameters in the Swagger contract, so for
those the parameter names, types, order and required flags are all machine-checkable.

### Bulk amortizes the round trip

`BulkUpdate` applies one property bag to a list of URIs. `BulkDelete` deletes a list of
URIs. Both take a `uris` array in the request body. This is how you set a custom property on
four hundred nodes without four hundred HTTP requests. See
[rest-api.md](rest-api.md#bulkupdate) for the request shapes.

## Which interface for which task

| Task | Interface |
|:---|:---|
| List nodes down in a location | Query |
| Add a node to monitoring | CRUD (Create `Orion.Nodes`, then Create `Orion.Pollers` rows) |
| Change one node's caption | CRUD (Update on the node URI) |
| Change a custom property on one node | CRUD (Update on the node's `CustomProperties` URI) |
| Change a custom property on many nodes | Bulk (`BulkUpdate` over the `CustomProperties` URIs) |
| Put a node in a maintenance window | Invoke (`Orion.Nodes.Unmanage`) |
| Acknowledge alerts | Invoke (`Orion.AlertActive.Acknowledge`) |
| Force a poll right now | Invoke (`Orion.Nodes.PollNow`) |
| Delete a node | CRUD (Delete on the node URI) |
| Delete many interfaces | Bulk (`BulkDelete`) |

## Where to go next

- [connecting.md](connecting.md) covers endpoints, ports, authentication modes and working
  connection snippets for PowerShell, Python and curl.
- [rest-api.md](rest-api.md) is the REST contract in detail: request and response shapes,
  parameter binding, paging and the bulk operations.
- [crud.md](crud.md) covers create, read, update and delete, and how to determine which
  entities support which operations.
- [uris.md](uris.md) explains the SWIS URI format, the system identifier, and how to build
  URIs that address nav properties and custom properties.
- [bulk-operations.md](bulk-operations.md) covers `BulkUpdate` and `BulkDelete`, and why
  their empty response means the read-back is part of the operation rather than optional.
- [invoke-verbs.md](invoke-verbs.md) is the complete guide to calling verbs: the positional
  argument contract, how to pass parameters from each client, and worked examples.
- [verb-catalog.md](verb-catalog.md) is the shortlist of verbs worth knowing, grouped by
  the task you are trying to do.
- [invoke-at-scale.md](invoke-at-scale.md) is what to read before running any of it
  unattended: the risk surface derived from the contract, the failure modes that turn a
  working script into an incident, and how to scale one safely.
- [metadata-introspection.md](metadata-introspection.md) shows how to ask a live server
  about its own schema, which is the authority for the version in front of you.

## Verifying anything in this guide

Every entity name, property name, verb name and parameter in these documents was checked
against the extracted schema in `data/schema/2026.2/`. You can check them too:

```bash
python3 tools/schema_query.py stats
python3 tools/schema_query.py find <keyword> --properties
python3 tools/schema_query.py show <Entity>
python3 tools/schema_query.py props <Entity>
python3 tools/schema_query.py verbs --entity <Entity>
python3 tools/schema_query.py verb <Entity> <Verb>
python3 tools/schema_query.py path <FromEntity> <ToEntity>
```

Official upstream sources:

- [Orion SDK documentation](https://solarwinds.github.io/OrionSDK/)
- [Orion SDK wiki](https://github.com/solarwinds/OrionSDK/wiki)
- [About SWIS](https://solarwinds.github.io/OrionSDK/docs/about-swis/)
- [Schema reference](https://solarwinds.github.io/OrionSDK/2026.2/schema/index.html)

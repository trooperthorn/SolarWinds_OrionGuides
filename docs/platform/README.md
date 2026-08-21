# The SolarWinds Platform: Orientation

This section explains what the product actually is, how a deployment is put together,
which modules contribute which parts of the data model, and why almost everything you
touch through the API is still called `Orion.*` even though the product has been renamed
twice.

Read this section first if you are new to the platform. Everything else in this
repository (SWQL queries, REST calls, entity references, automation recipes) assumes you
know the vocabulary defined here.

## What the product is

SolarWinds sells a self-hosted monitoring suite that you install on your own Windows
servers against your own SQL Server database. The SolarWinds Orion SDK describes it this
way:

> The SolarWinds Orion Platform is a unified suite of network and system management
> products. Orion is installed on one or more servers in your organization's intranet.
> IT professionals in your organization interact with Orion primarily through the Orion
> website, which provides a single pane of glass for monitoring your IT infrastructure.

Source: [SolarWinds Orion SDK documentation](https://solarwinds.github.io/OrionSDK/).

The key architectural idea is that the suite is one platform plus many modules. You do not
install "NPM" and "SAM" as separate products with separate databases and separate APIs.
You install the platform, and each module extends it: new polling logic, new pages in the
web console, and, the part that matters here, new entities in the one shared data model.
That is why a single SWQL query can join a node to its interfaces, its applications, and
its configuration backups even though three different modules supplied those three things.

That shared data model is exposed by the **SolarWinds Information Service (SWIS)**, a
data access layer with its own SQL-like query language, **SWQL**. SWIS is the API. When
this repository says "the API", it means SWIS, reachable over REST or over SOAP/net.tcp.
See [architecture.md](architecture.md) for how SWIS sits between you and the database, and
why you should go through it rather than querying SQL Server directly.

## How to navigate this section

| Document | What it answers |
|---|---|
| [architecture.md](architecture.md) | What the moving parts are: primary server, additional polling engines, additional web servers, the SQL Server database, SWIS, the polling job engine, and High Availability pools. Includes runnable SWQL for inspecting your own deployment. |
| [modules.md](modules.md) | Which product contributes which entities. Maps each module to its SWIS namespace or entity prefix, with the entity count in 2026.2 and a starter query per module. |
| [versions-and-naming.md](versions-and-naming.md) | The naming history (Orion Platform, SolarWinds Platform, SolarWinds Observability Self-Hosted), why the `Orion.*` namespace survived all of it, how version numbers work, and how to tell which schema your server actually has. |

## The numbers, for the version documented here

This repository documents SWIS schema version **2026.2**. The extraction under
[`data/schema/2026.2/`](../../data/schema/2026.2/) contains:

| Item | Count |
|---|---|
| Entities | 2067 |
| Namespaces (top-level) | 16 |
| Properties | 19328 |
| Verbs | 958 |
| Verbs with typed parameters | 794 |
| Relationship (navigation) edges | 2992 |
| Entities that support create | 250 |

Those counts are not trivia. They are the reason this repository exists: a data model with
two thousand entity types is not something you can hold in your head or guess at, and
guessing produces queries that fail with an unhelpful error at runtime.

## The API surface in one table

| Fact | Value |
|---|---|
| REST base path | `/SolarWinds/InformationService/v3/Json` |
| Scheme | `https` only |
| REST port, 2023.1 and later | 17774 |
| REST port through 2022.4.1 | 17778 (deprecated) |
| SOAP / net.tcp port | 17777 |
| Generic REST paths | `/Query` (GET and POST), `/{uri}` (CRUD), `/BulkUpdate`, `/BulkDelete` |
| Per-entity REST paths | `/Create/{Entity}`, `/Invoke/{Entity}/{Verb}` |

The port change is the single most common cause of "the API used to work and now it does
not". SolarWinds documents it in the SDK's
[REST page](https://solarwinds.github.io/OrionSDK/docs/rest/):

> Orion Platform had been using port 17778 for REST communication until the 2022.4.1
> release. This changed in the 2023.1 release where the REST endpoint can be found on port
> 17774 and port 17778 is deprecated and will be removed in a future release.

One more rule that shapes every automation you will write: **the query interface is
read-only**. `SELECT` through `/Query` cannot insert, update, or delete anything. Changes
go through the CRUD interface (create, update, delete against a SWIS URI) or through
Invoke verbs. This is not a limitation of the REST binding, it is how SWIS is designed,
and it is why so much of the useful surface area of this API is verbs rather than DML.

## Your first query

Every SWIS deployment has polling engines, so this query works on any server and tells you
something immediately useful:

```sql
SELECT EngineID, ServerName, ServerType, PollingCompletion, Elements
FROM Orion.Engines
ORDER BY EngineID
```

A single-server deployment returns one row. If it returns several, you have additional
polling engines, and [architecture.md](architecture.md) explains what that means for where
your monitoring jobs actually run.

## Verify before you trust

Entity names, property names, and verb signatures differ between platform versions and
between servers with different modules installed. Nothing in this repository should be
taken on faith when you can check it in seconds.

Against the extracted 2026.2 data, offline, from the repository root:

```bash
python3 tools/schema_query.py stats
python3 tools/schema_query.py find engine --properties
python3 tools/schema_query.py show Orion.Engines
python3 tools/schema_query.py props Orion.Nodes --grep Engine
python3 tools/schema_query.py verbs --entity Orion.HA.Pools
python3 tools/schema_query.py verb Orion.HA.Pools Switchover
python3 tools/schema_query.py path Orion.Nodes Orion.Engines
```

Against your own live server, the `Metadata.*` entities describe the schema that server
actually has:

```sql
SELECT FullName, BaseType, CanCreate, CanInvoke, Summary
FROM Metadata.Entity
WHERE Namespace = 'Orion'
ORDER BY FullName
```

If a name you read here does not come back from `Metadata.Entity` on your server, believe
your server. [versions-and-naming.md](versions-and-naming.md) explains why the two can
legitimately disagree.

## Where to go after this section

| Next | Why |
|---|---|
| [../swis/connecting.md](../swis/connecting.md) | Get authenticated and run a query for real |
| [../swis/rest-api.md](../swis/rest-api.md) | The HTTP contract: paths, bodies, status codes |
| [../swis/crud.md](../swis/crud.md) | Changing data through create, update, and delete |
| [../swis/uris.md](../swis/uris.md) | The URI format that CRUD addresses entities with |
| [../reference/entity-index.md](../reference/entity-index.md) | Every entity in 2026.2, generated from the extracted schema |
| [../reference/verb-index.md](../reference/verb-index.md) | Every verb with its parameters |
| [../reference/status-codes.md](../reference/status-codes.md) | What the `Status` integers mean |
| [../reference/netobject-types.md](../reference/netobject-types.md) | Entity to NetObject prefix mapping |
| [../../scripts/swql/09-engines-and-health.swql](../../scripts/swql/09-engines-and-health.swql) | Runnable versions of the engine health queries in this section |

## Related official documentation

- [SolarWinds Orion SDK documentation](https://solarwinds.github.io/OrionSDK/)
- [About SWIS](https://solarwinds.github.io/OrionSDK/docs/about-swis/)
- [SWIS URIs](https://solarwinds.github.io/OrionSDK/docs/uris/)
- [OrionSDK wiki](https://github.com/solarwinds/OrionSDK/wiki)

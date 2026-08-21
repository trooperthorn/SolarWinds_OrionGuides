# The SWIS schema

Everything SWIS exposes is described by a schema: a set of **entity types**, each with
**properties**, **relationships** to other entity types, **verbs** that can be invoked on
it, and **access control** rules saying which Orion right is needed for which operation.
That schema is the contract. A query, a CRUD call and an Invoke call are all expressed in
terms of it, so getting a name wrong is not a style problem, it is a runtime failure.

This section explains the model. The rest of the section splits it up:

| Page | Covers |
| --- | --- |
| [entity-model.md](entity-model.md) | Inheritance, inherited properties, keys, URIs, access control |
| [relationships.md](relationships.md) | The three relationship kinds and how to navigate them |
| [key-entities.md](key-entities.md) | Deep reference for the entities you will actually use |
| [using-the-data.md](using-the-data.md) | The generated JSON under `data/`, and how to query it |

## What version this documents

**2026.2.** The schema changes between platform releases, and it also changes on a single
release depending on which modules are licensed and installed, because each module adds its
own entities. Two servers on the same version do not necessarily have the same schema.

```bash
python3 tools/schema_query.py stats
```

```text
SWIS schema 2026.2  (source: https://github.com/solarwinds/OrionSDK (gh-pages branch))
  entities                   2067
  namespaces                 16
  properties                 19328
  verbs                      958
  verbsWithTypedParameters   794
  relationshipEdges          2992
  creatableEntities          250
  skippedPages               0
```

Those counts are the whole of the published 2026.2 schema, not a sample. The published
documentation for 2026.2 contains 2069 HTML pages under `schema/`, of which 2067 are entity
pages and two are the index and table of contents, and `skippedPages` is 0 because every one
of the 2067 parsed cleanly.

## Namespaces

An entity name is a namespace followed by one or more dotted segments, for example
`Orion.NPM.Interfaces`. The first segment is the namespace and it is the coarsest grouping
in the schema. The counts below come from `data/schema/2026.2/manifest.json`.

| Namespace | Entities | What lives there |
| --- | ---: | --- |
| `Orion` | 1705 | The core platform and most modules. `Orion.Nodes`, `Orion.NPM.Interfaces`, `Orion.APM.Application`, alerts, events, groups, statistics and the rest |
| `IPAM` | 77 | IP Address Manager: subnets, DHCP and DNS management, IP conflicts |
| `NCM` | 72 | Network Configuration Manager, current-generation entities |
| `Cortex` | 69 | A second element model whose entities are named `Cortex.Orion.*` and `Cortex.System.*`, covering Cisco ACI, cloud monitoring, firewalls, virtualization and power control units, plus `Cortex.Orion.Node`, `Cortex.Orion.Interface`, `Cortex.Orion.Volume` and `Cortex.Orion.Cpu` counterparts |
| `Cirrus` | 57 | Network Configuration Manager, original engineering namespace. `Cirrus.Nodes` is NCM's node record |
| `System` | 29 | SWIS's own base types and infrastructure: `System.Entity`, `System.ManagedEntity`, subscriptions, thresholds, indications |
| `DPA` | 18 | Database Performance Analyzer: wait data, blocking, problem SQL |
| `Metadata` | 11 | The live schema, queryable as data. See [metadata-introspection.md](../swis/metadata-introspection.md) |
| `ContentModel` | 8 | Content types and formatter mappings used by the modern dashboards |
| `Cli` | 5 | The CLI component's session settings, credentials and device templates |
| `UamsClient` | 5 | Runtime and installation state of the UAMS client |
| `PlatformConnect` | 3 | Platform Connect activation data and status |
| `SWISf` | 3 | `SWISf.EntitySubscriptions`, `SWISf.ProviderSubscriptions` and `SWISf.RemoteSWIS`. The published schema gives these no summary text, so treat any account of their purpose beyond the names as unverified |
| `SOC` | 2 | Identifier mapping and settings for the UAMS SOC plugin |
| `Vdc` | 2 | Virtual device contexts, gated behind the same NCM role as `Cirrus` and `NCM` |
| `PlatformBridge` | 1 | `PlatformBridge.Info`, an encrypted key-value store for Platform Bridge data |

Two things about that table trip people up.

**`Orion` is not legacy.** The product was renamed to SolarWinds Observability
Self-Hosted, but the entity names did not change, so `Orion.*` is the current, correct
namespace. See [versions-and-naming.md](../platform/versions-and-naming.md).

**A namespace is not a module.** NCM occupies both `Cirrus` and `NCM`, and also `Vdc`.
Storage Resource Monitor, Virtualization Manager and User Device Tracker all live inside
`Orion` as `Orion.SRM.*`, `Orion.VIM.*` and `Orion.UDT.*`. The mapping from product to
entities is in [modules.md](../platform/modules.md) and
[modules/README.md](../modules/README.md).

## The published schema browser versus this extract

SolarWinds publishes the same schema as a browsable site at
<https://solarwinds.github.io/OrionSDK/2026.2/schema/index.html>, one HTML page per entity,
with a URL you can guess: `Orion.Nodes` is at
<https://solarwinds.github.io/OrionSDK/2026.2/schema/Orion.Nodes.html>. Each page has
exactly the sections you would expect: Inheritance, Access control, Properties, Source
Relationships, Target Relationships, and Verbs with a nested Access control block per verb.

The data under `data/schema/2026.2/` is those pages parsed into JSON, joined with the
Swagger contract published alongside them at
<https://solarwinds.github.io/OrionSDK/2026.2/swagger.json>. It is the same facts, from the
same source, in a form you can query.

Use the published browser when:

- You want to read one entity, in a browser, with SolarWinds' own wording and links.
- You are on a platform version this repository does not carry. The site publishes several
  versions side by side.
- You want to confirm something written here against the original.

Use this extract when:

- You need to answer a question that spans entities. "Which entities have a property called
  `EngineID`", "which verbs take a parameter named `netObjectId`", "what is the shortest
  navigation path from `Orion.APM.Component` to `Orion.Nodes`" are one command here and a
  lot of clicking there.
- You want verb parameters. This is the big one. The rendered HTML flattens every verb's
  parameter documentation into a single run-on sentence, so `StartRealTimePolling` reads as
  "Starts realtime polling on Node entityNodeID of target NodeOwner identifier that owns
  this polling..." with no separation between the summary and the five parameters. The
  Swagger contract has the parameters typed, named and ordered but carries no properties or
  relationships. Neither artifact is sufficient alone, which is why
  [build_schema_data.py](../../tools/build_schema_data.py) parses both and joins them on
  the verb name.
- You are working offline, in CI, or from a script.
- You want inheritance resolved. An entity page lists only what that entity declares. The
  tools here walk the inheritance chain, which is why `Orion.Nodes.Uri` resolves even though
  `Orion.Nodes` does not declare `Uri`.

Use neither, and ask the server, when the question is about **a specific installation**.
Whether an entity exists at all depends on licensing and installed modules. The `Metadata.*`
entities answer that authoritatively: see
[metadata-introspection.md](../swis/metadata-introspection.md).

## Looking something up

[tools/schema_query.py](../../tools/schema_query.py) reads the extract, needs no network and
no server, and answers the questions people actually have. Run it from the repository root.
Add `--json` to any subcommand for machine-readable output.

### Which entity holds this data?

```bash
python3 tools/schema_query.py find volume capacity --properties
```

```text
entities matching 'volume capacity' (3 total)
  Orion.VolumesForecastCapacity                           3p   0v  Capacity Forecasting for Volumes.
  Orion.SRM.VolumeCapacityStatistics                      7p   0v  Stores capacity statistics for all Volumes
  Cortex.Orion.Volume.CapacityMetrics                     7p   0v  

properties matching 'volume capacity' (5 total)
  Orion.Cloud.Gcp.GkePod.VolumeCapacity : System.Int64  
  Orion.Cloud.Gcp.GkePodStatistics.VolumeCapacity : System.Int64  
  Orion.VIM.VMStatistics.AvgVolumeSummaryCapacity : System.Int64  Average Volume Summary Capacity
  Orion.VIM.VirtualMachines.VolumeSummaryCapacity : System.Int64  Volume Summary Capacity
  Orion.VIM.VirtualMachines.VolumeSummaryCapacityDepletionDate : System.DateTime  Volume Summary Capacity Depletion Date
```

`3p 0v` is the property and verb count, so you can tell a lookup table from a
verb-carrying entity at a glance.

### Everything about one entity

```bash
python3 tools/schema_query.py show Orion.Nodes
```

```text
Orion.Nodes   [2026.2]
  inherits: System.Entity -> System.DashboardEntity -> System.ManagedEntity -> Orion.Nodes
  operations: create, delete, invoke, read, update
    read                                   requires everyone
    read,invoke                            requires allowRealTimePolling
    create,read,update,delete,invoke       requires manageNodes
```

The output continues with all 102 declared properties, both relationship tables and the
17 verbs. It is the single command worth running before writing anything that touches an
entity.

### Does this property exist, and where did it come from?

```bash
python3 tools/schema_query.py props Orion.Nodes --grep unmanage
```

```text
Orion.Nodes properties (3 shown, including inherited)
  UnManaged                                  System.Boolean                True, Whether the entity is current unmanaged, otherwise false.  [from System.ManagedEntity]
  UnManageFrom                               System.DateTime               The datetime when this entity became/will become unmanaged  [from System.ManagedEntity]
  UnManageUntil                              System.DateTime               The datetime when this entity will exit the unmanaged state  [from System.ManagedEntity]
```

The `[from ...]` marker is the answer to "why is this property not on the entity page".
Pass `--no-inherited` to see only what the entity declares itself.

### What can I invoke, and what does it take?

```bash
python3 tools/schema_query.py verb Orion.Nodes Unmanage
```

```text
Orion.Nodes.Unmanage
  Set the given node into maintenance mode so the node polling is disabled
  returns: System.Void
  REST:    POST /Invoke/Orion.Nodes/Unmanage
  requires: allowUnmanage
  parameters (5):
    netObjectId: string (required)
    unmanageTime: string (required)
    remanageTime: string (required)
    isRelative: boolean (required)
    allowOverlapping: boolean (optional)
```

Invoke arguments go on the wire **positionally**, so the order in that list is the entire
contract. See [invoke-verbs.md](../swis/invoke-verbs.md).

### How do I join A to B?

```bash
python3 tools/schema_query.py path Orion.NPM.Interfaces Orion.Nodes
```

```text
1 path(s) from Orion.NPM.Interfaces to Orion.Nodes, shortest first

  Orion.NPM.Interfaces.Node
    Orion.NPM.Interfaces --Node--> Orion.Nodes

    SELECT TOP 10 a.DisplayName, a.Node.DisplayName
    FROM Orion.NPM.Interfaces a
```

### What inherits from this base type?

```bash
python3 tools/schema_query.py children System.ManagedEntity
```

```text
174 entity/entities inherit from System.ManagedEntity
  Cortex.Orion.CiscoAci.Apic
  Cortex.Orion.CiscoAci.ApplicationProfile
...
  Orion.Cloud.Gcp.CloudStorage
  ... 94 more (use --limit)
```

Because a query against a base entity returns rows from every descendant, that list is also
the list of things a single `FROM System.ManagedEntity` query will span.

## Then check your work

Looking a name up is half of it. [tools/validate_swql.py](../../tools/validate_swql.py)
parses a query, resolves every dotted reference through the schema including inherited
members and both relationship directions, and tells you exactly what is wrong:

```bash
echo "SELECT n.Caption, n.Node.Foo FROM Orion.Nodes n" | python3 tools/validate_swql.py -
```

```text
<stdin>
  ERROR: Orion.Nodes has no property or navigation property named 'Node'. Closest members: nodeid, asanode, npmnode.
      in: n.Node.Foo

1 query/queries checked, 1 error(s), 0 warning(s)
```

It reads `.swql`, `.md`, `.ps1`, `.py` and `.sh`, so a query embedded in a script is checked
too. Every `sql` block in this documentation is re-validated on every build.

## Where to go next

- [entity-model.md](entity-model.md) for inheritance, keys, URIs and rights.
- [relationships.md](relationships.md) for the three relationship kinds and navigation.
- [using-the-data.md](using-the-data.md) to query the JSON directly or regenerate it.
- [joins-and-navigation.md](../swql/joins-and-navigation.md) for the SWQL side of the same
  material: what a navigation does to your row count, and how to filter a base-entity query.
- [entity-index.md](../reference/entity-index.md) for all 2067 entities in one table, and
  [verb-index.md](../reference/verb-index.md) for all 958 verbs with their signatures.

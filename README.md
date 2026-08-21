# SolarWinds Orion Guides

Documentation, schema, and automation reference for **SolarWinds Orion**, now sold as
**SolarWinds Observability Self-Hosted**.

The product was renamed, but the API was not: entity names still live in the `Orion.*`
namespace, SWQL is still SWQL, and the SDK still calls itself the Orion SDK. Both names
refer to the same platform throughout this repository.

## Why this exists

The official SolarWinds documentation is good and this repository links to it constantly.
What it does not do is put the schema, the query language, the invoke surface, and worked
examples in one place that a person or a program can search offline.

So this repository:

- **Centralizes the guidance** on how the platform actually works, from architecture down
  to the specific reason a date filter returns the wrong hour.
- **Ships the schema as data.** 2067 entities, 19,328 properties, 958 verbs, and 2992
  relationship edges, extracted from SolarWinds' own published sources into JSON that
  automations and AI systems can read directly.
- **Documents every Invoke verb with its parameters**, in order, with the required right
  and the exact call syntax for REST, PowerShell, and Python.
- **Provides sample queries that are verified**, not aspirational. Every SWQL statement in
  this repository is checked against the schema on every build.

## Start here

| If you want to | Read |
| --- | --- |
| Understand the platform and its parts | [docs/platform/](docs/platform/README.md) |
| Connect to the API and run your first query | [docs/swis/connecting.md](docs/swis/connecting.md) |
| Learn SWQL properly | [docs/swql/](docs/swql/README.md) |
| Look up an entity, property, or relationship | [docs/schema/](docs/schema/README.md) |
| Change something, not just read it | [docs/swis/invoke-verbs.md](docs/swis/invoke-verbs.md) |
| Automate a task end to end | [docs/automation/](docs/automation/README.md) |
| Copy a working query | [scripts/swql/](scripts/swql/) |
| Use this repository from an AI agent | [AGENTS.md](AGENTS.md) |

## The tooling

Everything below works offline against the extracted data. No server, no network, no
credentials.

```bash
# Which entity holds interface utilization?
python3 tools/schema_query.py find interface utilization --properties

# Everything about an entity: properties, relationships, verbs, access control
python3 tools/schema_query.py show Orion.Nodes

# What can I invoke on a node, and what does it take?
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

Joining across the model is the part people lose the most time to, so it has its own
command. It searches the relationship graph in both directions, because a navigation
property can be declared at either end. That is what makes this a single hop rather than
a three-hop detour:

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

Where several routes exist it lists them all, shortest first, and you pick the one that
matches your intent. A component reaches a node through its application, but it can also
reach one through an alert object, and only you know which you meant.

And before a query goes anywhere near a live server:

```bash
echo "SELECT n.Caption, n.Node.Foo FROM Orion.Nodes n" | python3 tools/validate_swql.py -
```

```text
<stdin>
  ERROR: Orion.Nodes has no property or navigation property named 'Node'. Closest members: nodeid, asanode, npmnode.
      in: n.Node.Foo

1 query/queries checked, 1 error(s), 0 warning(s)
```

## Layout

```
docs/
  platform/     what the product is: architecture, modules, versions and naming
  swis/         the API: connecting, REST, CRUD, URIs, Invoke, introspection
  swql/         the query language: reference, functions, joins, date/time, gotchas
  schema/       the data model: entities, inheritance, relationships, key entities
  automation/   task guides: node lifecycle, maintenance, custom properties, alerts
  reference/    generated enumerations: every entity, verb, prefix, status, function
data/
  schema/2026.2/    entities, verbs, relationships, index, manifest
  reference/        SWQL functions, status codes, NetObject types, reconciliation
scripts/
  swql/         207 verified sample queries by subject area
  powershell/   SwisPowerShell examples
  python/       a dependency-light REST client
  curl/         the raw wire protocol
tools/          extraction, query, validation, and generation scripts
```

## Where the data comes from

Everything in `data/` is generated from sources SolarWinds publishes, by the scripts in
`tools/`. Nothing is hand-transcribed.

| Source | Provides |
| --- | --- |
| [OrionSDK `gh-pages`](https://github.com/solarwinds/OrionSDK/tree/gh-pages) schema pages | Entities, properties, relationships, verbs, access control |
| The same branch's `swagger.json` | Typed, ordered verb parameters and the REST surface |
| [OrionSDK `docs/`](https://solarwinds.github.io/OrionSDK/) | The official SWQL function reference and platform guides |
| A community SWQL examples workbook | Worked examples, NetObject prefixes, status codes |

The two sources disagree in places, and those disagreements are recorded rather than
resolved silently. `data/reference/reconciliation.json` lists every one: functions the
workbook uses that the official reference does not document, version numbers that differ,
and entities that have since been renamed. The build proposes the successor where it can
identify one, which is how `Orion.NPM.UCSBlades` resolves to `Orion.UCS.Blades` and
`Orion.VIM.LUNs` to `Orion.VIM.Luns`.

## Version coverage

The checked-in data documents platform version **2026.2**. The schema changes between
releases and also depends on which modules are licensed and installed, so treat this as a
strong default rather than as gospel for your server.

To build the data for another published version:

```bash
make data VERSION=2025.4
```

To get the authoritative answer for the server in front of you, ask it. SWIS describes
itself through the `Metadata.*` entities, and
[scripts/swql/08-schema-introspection.swql](scripts/swql/08-schema-introspection.swql) has
the queries:

```sql
SELECT Position, Name, Type, IsOptional
FROM Metadata.VerbArgument
WHERE EntityName = 'Orion.Nodes' AND VerbName = 'Unmanage'
ORDER BY Position
```

## Working on this repository

```bash
make data            # rebuild data/ from the OrionSDK sources
make docs-reference  # regenerate the tables in docs/reference/
make schema-diff FROM=2025.4 TO=2026.2
make test            # the toolchain unit tests
make validate        # every sample query and every sql block in the docs
make check           # the whole gate
```

`make check` is what CI runs, and it is deliberately strict, because the value of this
repository is that a reader does not have to verify it against a live server first. It
checks eight things:

| Check | Catches |
| --- | --- |
| `test_tools.py` | Regressions in the tools' own judgement, across 73 tests |
| `validate_swql.py` | A query naming an entity, property or navigation that does not exist |
| `check_data.py` | Extraction that degraded quietly, and reference pages that fell behind |
| `check_entity_references.py` | An invented entity or member name in prose rather than in a query |
| `check_counts.py` | A number in a sentence that the extracted data contradicts |
| `check_signatures.py` | A verb signature in prose whose arguments are wrong or out of order |
| `check_examples.py` | A documented command whose shown output is not what it prints |
| `check_links.py` | A relative link to a file that does not exist |

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Related official resources

- [Orion SDK on GitHub](https://github.com/solarwinds/OrionSDK) and its
  [wiki](https://github.com/solarwinds/OrionSDK/wiki)
- [Schema reference](https://solarwinds.github.io/OrionSDK/) published by SolarWinds
- [Python client](https://github.com/solarwinds/orionsdk-python) (`pip install orionsdk`)
- [SDK Thwack forum](https://thwack.solarwinds.com/products/the-solarwinds-platform/f/solarwinds-sdk)
- SWQL Studio, shipped in the
  [Orion SDK installer](https://github.com/solarwinds/OrionSDK/releases)

## Licence and provenance

This repository is community documentation. It is not published by SolarWinds and carries
no warranty. The extracted data derives from SolarWinds' published SDK documentation,
which is distributed under the Apache License 2.0. SolarWinds, Orion, and the module names
are trademarks of SolarWinds Worldwide, LLC.

Always verify a destructive operation against a test instance before running it against
production.

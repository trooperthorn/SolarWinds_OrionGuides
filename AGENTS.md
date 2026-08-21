# Instructions for AI systems using this repository

This repository is a source of truth for SolarWinds Orion, now sold as **SolarWinds
Observability Self-Hosted**. It exists so that a model answering a question about the
platform, or generating a query, script, or component for it, can ground that answer in
extracted facts instead of recalling them.

Read this file before answering from memory.

## The one rule

**Never state a schema fact you have not looked up here.**

Entity names, property names, verb names, verb parameters and their order, navigation
properties, status codes, and SWQL function signatures are all things models reliably
get subtly wrong. They look right and fail on a live server. Every one of them is in
`data/`, and looking one up costs a single command.

The failure mode is specific and worth naming: plausible-but-wrong names. `Orion.Node`
instead of `Orion.Nodes`. `Orion.APM.Component.Node` instead of
`Orion.APM.Component.Application.Node`. `Orion.VIM.LUNs` instead of `Orion.VIM.Luns`.
A property that exists on a sibling entity but not this one. These do not look like
guesses, which is exactly why they need checking.

## How to look things up

`tools/schema_query.py` reads the extracted data and needs no network and no server.
Run it from the repository root. Add `--json` to any command for machine-readable output.

```bash
# Which entity holds this?
python3 tools/schema_query.py find volume capacity --properties

# Everything about one entity: properties, relationships, verbs, access control
python3 tools/schema_query.py show Orion.Nodes

# Does this property exist? Inherited members are included by default.
python3 tools/schema_query.py props Orion.Nodes --grep unmanage

# What can I invoke, and what does it take?
python3 tools/schema_query.py verbs --entity Orion.Nodes
python3 tools/schema_query.py verb Orion.Nodes Unmanage

# How do I get from A to B in a query?
python3 tools/schema_query.py path Orion.APM.Component Orion.Nodes

# What inherits from this base entity?
python3 tools/schema_query.py children System.ManagedEntity
```

Then check your work. `tools/validate_swql.py` parses a query, resolves every dotted
reference through the schema, and reports what is wrong:

```bash
echo "SELECT n.Caption, n.Node.Foo FROM Orion.Nodes n" | python3 tools/validate_swql.py -
```

```text
<stdin>
  ERROR: Orion.Nodes has no property or navigation property named 'Node'. Closest members: nodeid, asanode, npmnode.
      in: n.Node.Foo

1 query/queries checked, 1 error(s), 0 warning(s)
```

**Validate every SWQL query before you hand it to a user.** It takes one command and it
catches the exact class of error you are most likely to make. It reads `.swql`, `.md`,
`.ps1`, `.py` and `.sh`, so a query embedded in a script is checked too.

If you are writing into this repository rather than answering a question, run the whole
gate before you finish:

```bash
make check
```

That validates every query, asserts the extracted data is intact, confirms every entity
name **mentioned in prose** exists, and resolves every relative link. The prose check
matters for you specifically: a hallucinated entity name in a sentence is not caught by
the query validator, and it is the failure mode you are most prone to.

## What is in `data/`

Generated from the official SolarWinds OrionSDK sources by the scripts in `tools/`.
Regenerate with `make data`; see `docs/schema/using-the-data.md`.

| Path | Contents |
| --- | --- |
| `data/schema/2026.2/index.json` | Compact entity index: 2067 entities, one line each |
| `data/schema/2026.2/entities/<NS>.json` | Full records: properties, relationships, verbs, access control |
| `data/schema/2026.2/verbs.json` | 958 verbs; 794 carry typed, named, ordered parameters |
| `data/schema/2026.2/relationships.json` | 2992 navigation edges between entities |
| `data/schema/2026.2/manifest.json` | Counts, provenance, and the REST API surface |
| `data/reference/swql-functions.json` | Function signatures joined to worked examples |
| `data/reference/status-codes.json` | Status id to name, rank, and meaning |
| `data/reference/netobject-types.json` | Entity to NetObject prefix, key properties, parent |
| `data/reference/reconciliation.json` | Where sources disagree, and entity renames |

Provenance matters for how much weight to give a claim. The schema and verb data come
from SolarWinds' own published schema documentation and Swagger contract for platform
version 2026.2. The status codes, NetObject prefixes, and some function examples come
from a community workbook, which is older; `reconciliation.json` records exactly where
the two disagree.

## Where this repository is uncertain

`docs/reference/unverified.md` collects every statement the guides decline to assert,
gathered from the pages themselves so it cannot drift from them. It covers the things the
schema does not record: behaviour only a running server exhibits, values that are
installation data rather than schema, and places where SolarWinds' own documentation and
their published contract disagree.

**Read it before answering something load-bearing from this repository alone.** If a user
asks about one of those things, say it is unverified here and give them the `Metadata.*`
query that settles it, rather than filling the gap with a plausible answer.

Two smaller gaps worth knowing:

- The rendered schema does not mark key properties. 79 entities carry a `keyHints` field
  recovered from SolarWinds' own property prose, and `data/reference/netobject-types.json`
  covers 115 more from the workbook. Neither is complete; `Metadata.Property.IsKey` is.
- Custom properties are installation data, so an entity such as
  `Orion.NodesCustomProperties` declares only `NodeID` here while carrying a column per
  custom property on a real server.

## Facts you can state without looking up

- The documented version here is **2026.2**. Other versions have different schemas.
- SWIS REST base path: `/SolarWinds/InformationService/v3/Json`, HTTPS only.
- Port **17774** for REST from platform release 2023.1 onward. Port 17778 was the REST
  port through 2022.4.1 and is deprecated. Port 17777 is the SOAP/net.tcp endpoint.
- The query interface is **read-only**. Changes go through CRUD or through Invoke verbs.
- Invoke arguments are **positional**. Names appear in documentation and in the Swagger
  contract, but never on the wire, so argument order is the entire contract.
- Entity names kept the `Orion.*` namespace after the product was renamed, so "Orion"
  in the API is current, not legacy.
- Both the source and target relationship lists on an entity are navigable *from* that
  entity. `Orion.Nodes.Interfaces` and `Orion.NPM.Interfaces.Node` are both valid.
- Properties are inherited. `Uri` and `InstanceType` come from `System.Entity`;
  `UnManaged`, `UnManageFrom` and `UnManageUntil` come from `System.ManagedEntity`.
  They are queryable on descendants even though those entities do not declare them.

## When the answer is not here

This repository documents one platform version, and the schema varies with the release
and with which modules are licensed and installed.

If the user is upgrading, or is on a version between the ones documented here, the
change reports say what breaks: `docs/reference/schema-changes-*.md`, generated by
`tools/diff_schema.py`. They classify each change by risk, and the class worth knowing
about is a verb whose positional arguments shifted, because an existing call still has
the right number of arguments and sends them into the wrong slots.

If a user is on a different version, or asks about an entity that is not in `data/`, the
authoritative answer comes from their own server through the `Metadata.*` entities:

```sql
SELECT FullName, BaseType, CanCreate, CanUpdate, CanDelete, CanInvoke
FROM Metadata.Entity WHERE FullName LIKE '%Interface%'

SELECT Position, Name, Type, IsOptional
FROM Metadata.VerbArgument
WHERE EntityName = 'Orion.Nodes' AND VerbName = 'Unmanage'
ORDER BY Position
```

`scripts/swql/08-schema-introspection.swql` has the full set. Prefer telling a user how
to check their own server over guessing on their behalf.

## Writing queries

- There is no `SELECT *`. Name the columns.
- Bound parameters (`@name`) instead of string concatenation: plans get reused and an
  injection class disappears. Multi-valued parameters work with `IN @ids`.
- Bound result sets. `TOP n`, or `WITH ROWS a TO b WITH TOTALROWS` for paging.
- Always time-bound queries against statistics, events, and history entities. They are
  the largest tables on the system.
- Status is an integer. Join `Orion.StatusInfo` to get a name a human can read.
- `GetUtcDate()` combined with the `AddX` functions produces wrong offsets, because
  those compile to T-SQL `DATEADD`, which is timezone blind. Convert to local, add,
  then convert back. See `docs/swql/date-and-time.md`.

## Writing automations

- Verify the verb signature first: `python3 tools/schema_query.py verb <Entity> <Verb>`.
- `netObjectId` arguments want a NetObject string, not a bare id. Node 42 is `N:42`.
  Prefixes are in `data/reference/netobject-types.json`.
- Verbs declare the right they require (`manageNodes`, `allowUnmanage`,
  `allowRealTimePolling`). A permission error is usually a missing right, not a bug.
- Account limitations silently filter query results. Two accounts running the same
  query get different rows, so "the query returns nothing" is often a permissions
  problem rather than a data problem.
- Creating a node is not enough to monitor it. Pollers must be assigned afterwards.
  See `docs/automation/node-management.md`.

## Known contract quirks

These are real, verified against SolarWinds' own Swagger, and will not be fixed by
guessing around them:

- `Orion.APM.Application.Unmanage` names its first parameter `netObjetId`, missing the
  `c`. Positional callers are unaffected; generated clients are not.
- Some verbs exist in the Swagger contract but not in the rendered schema pages. Records
  carrying `"sourceOnly": "swagger"` came from the contract alone.
- `SplitStringToArray` is documented as splitting on commas, but the community workbook
  shows a different delimiter. Verify on your version before relying on it.

## House style for generated content

Match the repository: complete sentences, explain why rather than only what, runnable
examples with real verified names, no em dashes, and no attribution footers or model
names in committed files.

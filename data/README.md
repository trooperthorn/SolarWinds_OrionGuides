# Extracted data

Machine-readable schema and reference data for SolarWinds Orion / Observability
Self-Hosted. Everything here is **generated**; do not edit it by hand. Regenerate with
`make data`.

The narrative guide to using these files, with worked `jq` recipes, is
[../docs/schema/using-the-data.md](../docs/schema/using-the-data.md).

## Layout

```
data/
  schema/2026.2/
    index.json           compact entity index, one record per entity
    entities/<NS>.json   full entity records, split by namespace
    verbs.json           every verb with typed, ordered parameters
    relationships.json   navigation edges between entities
    manifest.json        counts, provenance, and the REST API surface
  reference/
    swql-functions.json  function signatures joined to worked examples
    status-codes.json    status id to name, rank, and meaning
    netobject-types.json entity to NetObject prefix, key properties, parent
    reconciliation.json  where the sources disagree, and entity renames
```

## Provenance

Provenance decides how much weight a claim deserves, so it is worth being precise about.

| File | Built from | Confidence |
| --- | --- | --- |
| `schema/*` | SolarWinds' published schema documentation and Swagger contract for the version | High. This is SolarWinds' own output. |
| `reference/swql-functions.json` | The official SWQL function reference, joined to a community workbook | High for signatures, mixed for examples |
| `reference/status-codes.json` | A community reference workbook | Good, stable for many years, but not vendor-published |
| `reference/netobject-types.json` | The same workbook, cross-checked against the current entity list | Good, with stale rows explicitly marked |
| `reference/reconciliation.json` | Computed during the build | The disagreements themselves |

Two sources are joined to produce the schema data because neither is sufficient alone.
The rendered HTML carries entity structure, properties, relationships and access control,
but flattens every verb's parameter documentation into a single run-on paragraph. The
Swagger contract carries typed, named, ordered verb parameters but no properties or
relationships. `tools/build_schema_data.py` parses both and joins them on the verb name.

## Reading it

The offline query tool is usually easier than reading the JSON directly:

```bash
python3 tools/schema_query.py show Orion.Nodes
python3 tools/schema_query.py verb Orion.Nodes Unmanage
python3 tools/schema_query.py --json find volume capacity
```

For direct access, the files are plain JSON:

```bash
# Every verb on an entity, with its parameter names in order
jq '.[] | select(.entity=="Orion.Nodes") | {verb:.name, params:[.parameters[].name]}' \
   data/schema/2026.2/verbs.json

# Which entities can be created through CRUD
jq -r '.[] | select(.canCreate) | .entity' data/schema/2026.2/index.json

# Where the official reference and the workbook disagree
jq -r '.[] | "\(.type): \(.function // .entity)"' data/reference/reconciliation.json
```

## Version

The checked-in data documents platform version **2026.2**. The schema changes between
releases and also depends on which modules are licensed and installed.

```bash
make data VERSION=2025.4
```

The authoritative answer for a specific server always comes from that server, through the
`Metadata.*` entities. See
[../scripts/swql/08-schema-introspection.swql](../scripts/swql/08-schema-introspection.swql).

## Integrity

`tools/check_data.py` guards against silent extraction failures, which are the real risk
with regex parsing of generated HTML: a template changes, a selector stops matching, a
section comes back empty, and the output is still valid JSON. It enforces count floors,
the presence of core entities, and three hand-verified verb signatures.

```bash
python3 tools/check_data.py --version 2026.2
```

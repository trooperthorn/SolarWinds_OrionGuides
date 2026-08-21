# Using the extracted data

Everything under [data/](../../data/) is generated. It is SolarWinds' own published schema
documentation and Swagger contract for platform version 2026.2, parsed into JSON you can
query, plus a small set of reference tables merged from a community workbook. Nothing in
there is hand-written, and nothing in there should be hand-edited: the next `make data` will
overwrite it.

This page is the practical guide. What each file holds, what shape it has, how to get answers
out of it with `jq`, and how to regenerate the whole thing for a different platform version.

If you only want to look one thing up, [schema_query.py](../../tools/schema_query.py) is
easier than any of this and is covered in [README.md](README.md). Come here when you want to
answer a question that spans the whole schema, or when you are writing a tool.

## What is in data/

```text
data/
  schema/2026.2/
    index.json           compact entity index, one record per entity
    entities/<NS>.json   full entity records, split by namespace
    verbs.json           every verb with typed, ordered parameters
    relationships.json   navigation edges between entities
    types.json           the shape of every type a verb returns or takes
    manifest.json        counts, provenance, and the REST API surface
  reference/
    swql-functions.json  function signatures joined to worked examples
    status-codes.json    status id to name, rank, and meaning
    netobject-types.json entity to NetObject prefix, key properties, parent
    reconciliation.json  where the sources disagree, and entity renames
```

Provenance decides how much weight a claim deserves. The four files under `schema/` come
from SolarWinds' own output and are high confidence. Under `reference/`, only the function
*signatures* are vendor-published; the status codes, NetObject prefixes and many examples
come from a community workbook that is older than the schema, and `reconciliation.json`
records exactly where the two disagree. See [data/README.md](../../data/README.md).

### manifest.json

Provenance and counts for the whole build. Read this first when you want to know what you
are looking at.

```bash
jq '.counts, .apiSurface' data/schema/2026.2/manifest.json
```

```json
{
  "entities": 2067,
  "namespaces": 16,
  "properties": 19328,
  "verbs": 1021,
  "verbsWithTypedParameters": 848,
  "verbsFromSwaggerOnly": 63,
  "entitiesWithoutSchemaPage": 5,
  "types": 309,
  "verbsWithKnownReturnShape": 542,
  "relationshipEdges": 2992,
  "creatableEntities": 250,
  "skippedPages": 0
}
{
  "basePath": "/SolarWinds/InformationService/v3/Json",
  "host": "localhost:17774",
  "schemes": [
    "https"
  ],
  "swaggerVersion": "2.0",
  "serviceVersion": "3.0.0",
  "genericPaths": [
    "/BulkDelete",
    "/BulkUpdate",
    "/Query",
    "/{uri}"
  ]
}
```

`skippedPages: 0` is the one to watch. It counts entity pages the parser could not read, so
anything above zero means the extraction degraded and the other counts are understated.

### index.json

One flat array, one record per entity, 2067 records. Use it whenever you want to iterate
every entity without loading 16 namespace files.

```bash
jq '.[] | select(.entity=="Orion.Nodes")' data/schema/2026.2/index.json
```

```json
{
  "entity": "Orion.Nodes",
  "namespace": "Orion",
  "baseEntity": "System.ManagedEntity",
  "summary": "",
  "operations": [
    "create",
    "delete",
    "invoke",
    "read",
    "update"
  ],
  "canCreate": true,
  "keyHints": null,
  "counts": {
    "properties": 102,
    "targetRelationships": 26,
    "sourceRelationships": 135,
    "verbs": 17
  },
  "file": "entities/Orion.json"
}
```

`baseEntity` is the immediate parent, not the whole chain. `operations` is the union of the
operations named in the entity's access control table, so an empty array means the page
declares no access control rather than that the entity is unusable. `counts.properties`
counts **declared** properties only; `Orion.Nodes` resolves to 113 once inheritance is
applied. `file` points at the namespace file holding the full record.

### The `entities/` files

The full records, one file per namespace, same array shape. Fifteen fields on every entity,
plus `keyHints` and `keyHintSource` on the 79 that have them:

```bash
jq -r '.[0] | keys_unsorted[]' data/schema/2026.2/entities/System.json
```

```text
entity
namespace
version
summary
flags
inheritance
baseEntity
accessControl
properties
targetRelationships
sourceRelationships
verbs
supportedOperations
counts
canCreate
```

`inheritance` is the full ancestor chain, root first, excluding the entity itself, which is
what makes "does this entity descend from X" a single `contains` test.
`sourceRelationships` and `targetRelationships` are both lists of navigation properties
usable **from** this entity; see [relationships.md](relationships.md). `keyHints` is present
only where SolarWinds names a key in the property's own description text, so its absence
means the prose was silent, not that the entity has no key. The authority for a given server
is `Metadata.Property.IsKey`; see [entity-model.md](entity-model.md).

### verbs.json

Every verb in the schema flattened into one array of 1021 records, so you never have to know
which entity a verb is on to search for it. 848 of them carry typed, named, ordered
parameters recovered from the Swagger contract.

```bash
jq '.[] | select(.entity=="Orion.Volumes" and .name=="Unmanage")' data/schema/2026.2/verbs.json
```

```json
{
  "entity": "Orion.Volumes",
  "namespace": "Orion",
  "name": "Unmanage",
  "summary": "Unmanages specified volume in the specified time range",
  "parameters": [
    {
      "name": "netObjectId",
      "type": "string",
      "required": true
    },
    {
      "name": "unmanageTime",
      "type": "string",
      "required": true
    },
    {
      "name": "remanageTime",
      "type": "string",
      "required": true
    },
    {
      "name": "isRelative",
      "type": "boolean",
      "required": true
    },
    {
      "name": "allowOverlapping",
      "type": "boolean",
      "required": false
    }
  ],
  "returns": "System.Void",
  "restPath": "/Invoke/Orion.Volumes/Unmanage",
  "accessControl": [
    {
      "operations": [
        "invoke"
      ],
      "right": "allowUnmanage"
    }
  ]
}
```

**The order of the `parameters` array is the contract.** Invoke arguments travel positionally
and the names never appear on the wire, so a generated client that reorders them still
type-checks and still sends the wrong values into the wrong slots. One optional field
actually shows up in this build: `summaryRaw`, on 245 of the 1021 records, preserving the
original run-on prose from the HTML page where the Swagger description replaced it. The
builder also emits `sourceOnly: "swagger"` on a verb the contract publishes for an entity
with no rendered schema page at all. 63 verbs across five entities carry it in 2026.2. They
are invokable and fully typed, so they belong in the verb list, but there is no entity
record for them and `schema_query.py show` cannot reach them. Filter the field out if you
are joining verbs to entities and want the join to stay total.

### relationships.json

A flat edge list, 2992 records, six fields each. Covered in full in
[relationships.md](relationships.md), including a worked traversal.

### The reference files

```bash
jq '.[] | select(.status==12)' data/reference/status-codes.json
```

```json
{
  "status": 12,
  "name": "Unreachable",
  "rank": 150,
  "description": "Object status cannot be determined because it is dependent on another node that is currently down. See the doc."
}
```

```bash
jq '.[] | select(.name=="AddDate") | {name, signature, category, documented, exampleCount}' data/reference/swql-functions.json
```

```json
{
  "name": "AddDate",
  "signature": "AddDate(u, n, d)",
  "category": "Date/time",
  "documented": true,
  "exampleCount": 1
}
```

`documented: true` means the function is in SolarWinds' official reference. A function with
`documented: false` came from the workbook alone and should be verified against your own
version before you rely on it.

`reconciliation.json` is the record of every disagreement the build found, 14 of them:

```bash
jq -r 'group_by(.type)[] | "\(.[0].type)\t\(length)"' data/reference/reconciliation.json
```

```text
undocumented-function	1
unknown-entity	12
version-mismatch	1
```

Read that file before trusting anything in `netobject-types.json` or the function examples.
It is also what turns a stale entity name into a current one: eight of the twelve
`unknown-entity` rows carry a `likelyReplacements` list.

## jq recipes

Every command below was run against the checked-in 2026.2 data and the output is real.

### Every verb on an entity, with its positional signature

The single most useful one, because it is the answer to "how do I call this".

```bash
jq -r '.[] | select(.entity=="Orion.Volumes") | "\(.name)(\([.parameters[].name] | join(", ")))"' data/schema/2026.2/verbs.json
```

```text
GetSupportedMetrics(netObjectId)
Remanage(netObjectId)
StartRealTimePolling(netObjectId, owner, properties, pollingExpiration, pollingFrequency)
StopRealTimePolling(netObjectId, owner, properties)
Unmanage(netObjectId, unmanageTime, remanageTime, isRelative, allowOverlapping)
```

### Every entity that declares a given property

"I know the column name, which entity is it on." Slurp the namespace files together with
`-s` so one command covers all 2067 entities.

```bash
jq -rs 'add | .[] | select(.properties[]?.name=="EngineID") | .entity' data/schema/2026.2/entities/*.json
```

```text
Cirrus.Nodes
IPAM.GroupNode
NCM.Nodes
Orion.ActiveAlerts
Orion.ActiveDiagnosticsDetail
Orion.AutoDependencyRoot
Orion.Cman.ContainerAgent
Orion.DeletedAutoDependencies
Orion.Dependencies
Orion.DiscoveryIgnoredNodes
Orion.DiscoveryProfiles
Orion.EngineProperties
```

That is the first twelve of 30. Note that this finds **declared** properties only. A property
inherited from a base type will not show up, which is exactly the gap
`python3 tools/schema_query.py props <Entity> --grep <text>` exists to close.

### Every entity you can create through CRUD

```bash
jq -r '[.[] | select(.canCreate)] | length' data/schema/2026.2/index.json
```

```text
250
```

`canCreate` is derived from the Swagger contract: an entity is creatable when the contract
publishes a `/Create/<Entity>` path for it. Two details are worth knowing if you compare
this number against the raw Swagger. The contract carries 378 `/Create/` paths in 2026.2.
Of those, 250 name an entity that also has a rendered schema page, 113 use a `Local.`
prefix that is not one of the 16 documented namespaces, and 15 name entities with no
rendered page in this version. Only the 250 are counted.

Creatable entities that also have verbs are the ones worth reading first, because they are
the ones you both build and operate:

```bash
jq -r '.[] | select(.canCreate and .counts.verbs > 0) | "\(.entity)\t\(.counts.verbs) verbs"' data/schema/2026.2/index.json
```

```text
Cli.CliSessionSettings	4 verbs
Cortex.Orion.CiscoAci.Apic	2 verbs
Cortex.Orion.Interface	8 verbs
Cortex.Orion.NetMan.CloudMonitoring.CloudAccount	10 verbs
Cortex.Orion.NetMan.CloudMonitoring.VirtualNetwork	7 verbs
Cortex.Orion.NetMan.CloudMonitoring.VirtualNetworkConnection	7 verbs
Cortex.Orion.NetMan.CloudMonitoring.VirtualNetworkGateway	7 verbs
Cortex.Orion.NetMan.Firewalls.Firewall	5 verbs
```

### Every verb taking a parameter of a given name

This is how you find the whole family of verbs that share a calling convention. The shared
name does not mean a shared format, though, and this is the trap: of the 21 verbs taking a
`netObjectId`, 12 declare it `string` and want a NetObject string such as `N:42`, while nine
declare it `number` and want the bare integer key. The nine are `GetSupportedMetrics`,
`StartRealTimePolling` and `StopRealTimePolling` on each of `Orion.Nodes`,
`Orion.NPM.Interfaces` and `Orion.Volumes`; `Orion.Nodes.StartRealTimePolling` even documents
its first argument as "NodeID of target Node". Read the declared type before you build the
argument:

```bash
jq -r '.[] | select(any(.parameters[]?; .name=="netObjectId")) | "\(.entity).\(.name)"' data/schema/2026.2/verbs.json
```

```text
Orion.NPM.Interfaces.GetSupportedMetrics
Orion.NPM.Interfaces.Remanage
Orion.NPM.Interfaces.SetBandwidth
Orion.NPM.Interfaces.StartRealTimePolling
Orion.NPM.Interfaces.StopRealTimePolling
Orion.NPM.Interfaces.Unmanage
Orion.Nodes.GetSupportedMetrics
Orion.Nodes.PollNow
Orion.Nodes.PollStatusNow
Orion.Nodes.RediscoverNow
```

Ten of 21. Add `select(any(.parameters[]?; .name=="netObjectId" and .type=="string"))` to
narrow it to the twelve that really do want a prefix. Prefixes are in
[netobject-types.json](../../data/reference/netobject-types.json) and
[netobject-types.md](../reference/netobject-types.md).

### Every verb requiring a given right

```bash
jq -r '.[] | select(any(.accessControl[]?; .right=="manageAlerts")) | "\(.entity).\(.name)"' data/schema/2026.2/verbs.json
```

```text
Orion.Actions.DeleteActionsByAssignments
Orion.Actions.DeleteActionsByAssignmentsAndCategory
Orion.Actions.SaveActionsForAssignments
Orion.Actions.TestAlertingAction
Orion.Actions.UpdateAction
Orion.Actions.UpdateActionsDescriptions
Orion.Actions.UpdateActionsFrequencies
Orion.Actions.UpdateActionsProperties
Orion.AlertConfigurations.Export
Orion.AlertConfigurations.GetComplexPropertiesByAlertID
Orion.AlertConfigurations.Import
Orion.Frequencies.DeleteFrequencies
Orion.Frequencies.SaveTimePeriodFrequencies
```

That is the practical answer to "what will this service account be able to do if I grant it
this right". See [entity-model.md](entity-model.md) for the full list of rights.

### Everything an entity contains

Hosting relationships are the containment tree, so this is the pre-flight check before a
delete:

```bash
jq -r '.[] | select(.from=="Orion.NPM.Interfaces" and .kind=="System.Hosting" and .direction=="source") | "\(.navigationProperty) -> \(.to)"' data/schema/2026.2/relationships.json
```

```text
Anomalies -> Orion.AIIM.Orion_NPM_Interfaces_Anomalies
ASAInterface -> Orion.ASA.Interfaces
CustomProperties -> Orion.NPM.InterfacesCustomProperties
InErrorsDiscardsThreshold -> Orion.NPM.InErrorsDiscardsThreshold
OutErrorsDiscardsThreshold -> Orion.NPM.OutErrorsDiscardsThreshold
InPercentUtilizationThreshold -> Orion.NPM.InPercentUtilizationThreshold
OutPercentUtilizationThreshold -> Orion.NPM.OutPercentUtilizationThreshold
InterfaceDowntimeHistory -> Orion.NPM.InterfaceNetObjectDowntime
Errors -> Orion.NPM.InterfaceErrors
Traffic -> Orion.NPM.InterfaceTraffic
WebUri -> Orion.NPM.InterfaceWebUri
ForecastCapacity -> Orion.NPM.InterfacesForecastCapacity
MulticastInterface -> Orion.NPM.MulticastRouting.Interfaces
CustomPollerAssignmentOnInterface -> Orion.NPM.CustomPollerAssignmentOnInterface
```

### Entities carrying the most verbs

A quick way to find the operational surface of the platform:

```bash
jq -r 'group_by(.entity)[] | "\(length)\t\(.[0].entity)"' data/schema/2026.2/verbs.json | sort -rn | head -10
```

```text
29	Orion.Orchestrators.Info
26	Cirrus.PolicyReports
25	Cirrus.Nodes
24	Cirrus.ConfigArchive
21	IPAM.SubnetManagement
20	Orion.AgentManagement.Agent
20	Cirrus.Settings
18	IPAM.DhcpDnsManagement
17	Orion.Nodes
16	Orion.Dashboards.Instances
```

## The tools

Everything lives in [tools/](../../tools/README.md), and nothing there needs anything beyond
the Python standard library except `openpyxl`, which is used only to read the source
workbook. Three scripts matter for this page: two that build the data and one that reads it.

### build_schema_data.py

Turns the OrionSDK gh-pages checkout into everything under `data/schema/<version>/`.

```bash
python3 tools/build_schema_data.py --source .orionsdk --version 2026.2
```

| Argument | Default | Meaning |
| --- | --- | --- |
| `--source` | required | A checkout of the OrionSDK `gh-pages` branch |
| `--version` | `2026.2` | The version directory inside that checkout to build |
| `--out` | `data/schema` | Output root. The version directory is created inside it, so the default writes `data/schema/2026.2/` |

It reads two artifacts from `<source>/<version>/` and joins them, because **neither is
sufficient alone**:

| Artifact | Has | Lacks |
| --- | --- | --- |
| `schema/<Entity>.html` | Properties, relationships, verbs, access control, inheritance | Verb parameters, flattened into one run-on paragraph |
| `swagger.json` | Typed, named, ordered verb parameters and return types | Properties, relationships, inheritance |

The join is on the verb name, and it is what turns a summary reading "Starts realtime polling
on Node entityNodeID of target NodeOwner identifier that owns this polling..." into five
named, typed, ordered parameters.

The HTML is parsed with regular expressions rather than an HTML library. The docfx output is
regular enough for that, and it keeps the tool runnable anywhere with a stock Python 3. The
risk with that choice is silent degradation: a template changes, a selector stops matching, a
section comes back empty, and the output is still valid JSON. That is what
[check_data.py](../../tools/check_data.py) exists to make loud, through count floors,
required core entities and three hand-verified verb signatures.

```bash
python3 tools/check_data.py --version 2026.2
```

Run it after any rebuild. If it fails, the data is wrong, not the check.

### build_reference_data.py

Merges the official SWQL function reference with the community examples workbook, and emits
everything under `data/reference/`.

```bash
python3 tools/build_reference_data.py \
    --functions-md .orionsdk/docs/swql-functions/index.md \
    --workbook reference/SWQL_Examples.xlsx \
    --schema-index data/schema/2026.2/index.json
```

| Argument | Meaning |
| --- | --- |
| `--functions-md` | Required. `docs/swql-functions/index.md` from the gh-pages checkout, the authoritative signature list |
| `--workbook` | Required. The community workbook, which supplies worked examples, status codes and NetObject prefixes |
| `--schema-index` | Optional, default `data/schema/2026.2/index.json`. The entity index for the version being documented, which is what lets the build mark workbook rows whose entity no longer exists |
| `--out` | Output root, default `data/reference` |

The two inputs disagree in places, and the design decision worth knowing is that the merge
does not silently pick a winner. It records both and writes `reconciliation.json`, so a
discrepancy stays visible and can be checked against a live server. Point `--schema-index` at
a file that is not there — which is what happens if you build reference data for a version
whose schema you have not extracted yet — and you still get the reference files, but the
`unknown-entity` findings and the `inCurrentSchema` flags will not be there.

### schema_query.py

The read side. Eight subcommands, all offline, all reading `data/schema/<version>/`.

| Command | Answers |
| --- | --- |
| `find <terms...> [--properties]` | Which entity or property holds this |
| `show <Entity>` | Everything about one entity |
| `props <Entity> [--grep T] [--no-inherited]` | Does this property exist, and where from |
| `verbs [--entity E] [--grep T]` | What can I invoke |
| `verb <Entity> <Verb>` | The positional signature and call syntax |
| `path <From> <To> [--max-hops N] [--max-paths N]` | How do I join A to B |
| `children <BaseEntity>` | What inherits from this |
| `stats` | Counts and provenance |

Two global options apply to all of them. `--json` emits machine-readable output instead of
text, which is what you want when scripting against it. `--version` selects which extracted
schema to read, so once you have built a second version you can compare them without
touching the tools. Both belong to the top-level parser, so they go before the subcommand
name — `schema_query.py --json show Orion.Nodes`, not `schema_query.py show Orion.Nodes
--json`, which argparse rejects as an unrecognized argument.

The tool knows two things the raw JSON does not, and both are why it is usually the right
starting point:

- **Inherited members are resolved.** An entity record lists only what that entity declares.
  `props`, `path` and `validate_swql.py` all walk the inheritance chain first, which is why
  `Orion.Nodes.Uri` resolves even though `Orion.Nodes` does not declare `Uri`.
- **Both relationship directions are navigable.** `path` searches source and target
  relationships together, which is what makes `Orion.NPM.Interfaces.Node` a one-hop answer
  rather than a detour.

The rest of the toolchain is [validate_swql.py](../../tools/validate_swql.py), which checks
SWQL against the schema and is the CI gate, [diff_schema.py](../../tools/diff_schema.py),
which reports what changed between two versions,
[build_reference_docs.py](../../tools/build_reference_docs.py), which regenerates the
enumerated tables under `docs/reference/`,
[check_entity_references.py](../../tools/check_entity_references.py), which catches invented
entity names in prose, [check_examples.py](../../tools/check_examples.py), which re-runs
every documented command and compares the output against what the page claims, and
[check_links.py](../../tools/check_links.py).

## Regenerating for a different platform version

The published SDK site carries several versions side by side, and this repository documents
one at a time. To build another, point `VERSION` at it:

```bash
make clean
make data VERSION=2025.4
python3 tools/check_data.py --version 2025.4
```

`make clean` first is not optional when you are changing versions. The `sdk` target does a
sparse checkout of `docs` and the one version you asked for, and marks it done with a
`.orionsdk/.fetched` file. If that marker already exists from a previous build, the target is
skipped and the new version's directory will not be in the checkout.

What the build actually does:

1. Blobless, sparse clone of the `gh-pages` branch of
   <https://github.com/solarwinds/OrionSDK> into `.orionsdk`, limited to `docs/` and the one
   version directory. The filter keeps the download to what is actually read.
2. `build_schema_data.py` against `.orionsdk/<VERSION>/`.
3. `build_reference_data.py`, but only if `reference/SWQL_Examples.xlsx` is present. Without
   the workbook the schema data is still rebuilt and the step is skipped with a note, since
   the workbook is not version specific.

Once you have two versions on disk, the change report says what breaks:

```bash
make schema-diff FROM=2025.4 TO=2026.2
```

That writes `docs/reference/schema-changes-2025.4-to-2026.2.md`, classifying each change by
risk. The class worth reading carefully is a verb whose positional arguments changed, because
an existing call can still have the right number of arguments and send them into the wrong
slots, which fails silently rather than loudly. See
[schema-changes-2025.4-to-2026.2.md](../reference/schema-changes-2025.4-to-2026.2.md).

## Before you commit anything

```bash
make check
```

That runs the toolchain unit tests, validates every sample query and every `sql` block in the
documentation, asserts the extracted data is intact, confirms every entity name mentioned in
prose actually exists, checks that every documented tool invocation still prints what the
page says it prints, and resolves every relative link. The prose check is the one that
matters most for trust: a wrong entity name in a sentence is invisible to the query
validator, and a reader who finds one invented name stops believing the rest of the page.

## Where to go next

- [README.md](README.md) for the schema section overview and the lookup commands.
- [entity-model.md](entity-model.md) and [relationships.md](relationships.md) for what the
  data means.
- [tools/README.md](../../tools/README.md) for the full toolchain, including how extraction
  works and how to add a check.
- [metadata-introspection.md](../swis/metadata-introspection.md) for the same questions
  asked of a live server, which is always the authority for a specific installation.

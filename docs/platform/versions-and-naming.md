# Versions and Naming

The product has been renamed twice. The API has not been renamed at all. Understanding
that gap is the difference between reading SolarWinds documentation fluently and being
permanently confused by it.

## The naming history

| Era | Name you will see |
|---|---|
| Original and longest-lived | **Orion Platform** |
| Renamed around the 2022.4 releases | **SolarWinds Platform** |
| Current name for the self-hosted product | **SolarWinds Observability Self-Hosted** |

You can watch the first rename happen in SolarWinds' own SDK documentation. The
[credential management page](https://solarwinds.github.io/OrionSDK/docs/credential-management/)
says:

> The SolarWinds Platform 2022.4 introduced two verbs for managing shared credentials:
> `CreateCredentials` and `UpdateCredentials`

and marks individual verbs with notes like "Supported since: SolarWinds Platform 2022.4"
and "Supported since: SolarWinds Platform 2023.2". Meanwhile the SDK's own front page
still opens with "The SolarWinds Orion Platform is a unified suite of network and system
management products", and the SDK itself is still called the Orion SDK. Both names are
live in the same documentation set.

The second rename, to SolarWinds Observability Self-Hosted, distinguishes the product you
install on your own servers from SolarWinds Observability, the SaaS offering. It is a
product-name change and not a technology change. The SDK documentation set has not been
renamed to match, so you will not find the phrase in it; that absence is the point. If you
search SolarWinds' documentation site for a feature and land on a page titled with any of
these three names, you are in the right place.

## Why "Orion" is still everywhere in the API

Renaming a product is a marketing decision. Renaming an API is a breaking change.

Entity names, SWQL, SWIS URIs, and the SDK all kept the `Orion` identifier, and they kept
it in several distinct places:

- **The entity namespace.** 1705 of the 2067 entities in the 2026.2 schema are named
  `Orion.something`: `Orion.Nodes`, `Orion.Engines`, `Orion.NPM.Interfaces`,
  `Orion.APM.Application`, `Orion.HA.Pools`.
- **SWIS URIs.** The URI format is
  `swis://<system-identifier>/<endpoint>/<entity type>/<key filter>`, and the endpoint
  segment for the platform is literally `Orion`, giving URIs like
  `swis://abcdef/Orion/Orion.Nodes/NodeID=1`. See
  [SWIS URIs](https://solarwinds.github.io/OrionSDK/docs/uris/).
- **The SDK.** The toolkit is the Orion SDK, published at
  [solarwinds.github.io/OrionSDK](https://solarwinds.github.io/OrionSDK/), and its
  PowerShell module is `SwisPowerShell` with cmdlets like `Connect-Swis` and
  `Get-SwisData`.
- **The web console.** Administrative pages still live under `/Orion/`, for example the
  polling engine page at `/Orion/Admin/Details/Engines.aspx`.

The practical rule: **read `Orion.` as "the platform", not as "a product called Orion"**.
There is no module named Orion and there never was; the prefix marks the shared namespace
that every module extends. When you are searching for how to do something and the
documentation says "SolarWinds Platform" while your code says `Orion.Nodes`, nothing is
wrong.

The same logic explains most of the odd prefixes in
[modules.md](modules.md): `Orion.APM.` for Server and Application Monitor, `Cirrus.` for
Network Configuration Manager, `Orion.SEUM.` for Web Performance Monitor. All are
engineering names frozen at the moment the entities were first published, kept stable
precisely so that queries written years ago keep running.

## How version numbers work

Since the 2020 releases, versions are **year.release**, sometimes with a patch component:

```text
2026.2
 │    │
 │    └── release within the year (1, 2, 4, ...)
 └─────── calendar year
```

A third component appears for patch releases, giving versions such as `2024.4.1`,
`2025.1.1`, and `2025.2.1`. The release numbers within a year are not always consecutive:
the SDK publishes schema for 2024.1, 2024.2, and 2024.4 but no 2024.3, and for 2025.1,
2025.2, and 2025.4 but no 2025.3.

Before this scheme, the platform used names like 2019.4 and 2020.2.6, and individual
modules carried their own independent version numbers. Evidence of that older world is
still visible in the SDK's documentation tree, which contains separate IP Address Manager
API pages for versions 4.5.x, 4.6, 4.7, and 4.9 alongside pages for "2019.4 and higher
versions" and "Observability 2022.2". Module-specific version numbers still turn up in
older community material, so if you see a reference to "NPM 12.5" or "IPAM 4.7", it
predates the unified year.release scheme.

## The SDK publishes a schema per version

SolarWinds publishes full SWIS schema documentation for each platform version. As of this
writing the SDK site lists these 15 versions:

`2026.2`, `2026.1`, `2025.4`, `2025.2.1`, `2025.2`, `2025.1.1`, `2025.1`, `2024.4.1`,
`2024.4`, `2024.2`, `2024.1`, `2023.4`, `2023.3`, `2023.2`, `2023.1`

Each is browsable at `https://solarwinds.github.io/OrionSDK/<version>/schema/index.html`,
for example
[2026.2](https://solarwinds.github.io/OrionSDK/2026.2/schema/index.html). Versions older
than 2023.1 are not published there.

**This repository documents 2026.2.** The extraction lives in
[`data/schema/2026.2/`](../../data/schema/2026.2/) and its provenance is recorded in
[`manifest.json`](../../data/schema/2026.2/manifest.json). The layout of the data is
version-scoped on purpose, and the query tool takes a `--version` flag, so a second
version can be added later without disturbing the first:

```bash
python3 tools/schema_query.py --version 2026.2 stats
```

## The schema genuinely differs between versions

This is not a theoretical concern. Entities are added, renamed, split, and removed;
properties appear and disappear; verb signatures gain parameters. Concrete examples that
this repository has already had to reconcile:

| Older name | In 2026.2 |
|---|---|
| `Orion.F5.Device` | Gone; the closest match is `Orion.F5.System.Device` |
| `Orion.NPM.UCSChassis` | Gone; UCS entities moved to `Orion.UCS.Chassis` |
| `Orion.NPM.UCSBlades` | Gone; now `Orion.UCS.Blades` |
| `Orion.VIM.LUNs` | Now `Orion.VIM.Luns` (casing change only) |

The full list is in
[`data/reference/reconciliation.json`](../../data/reference/reconciliation.json).

The same drift affects SWQL functions and not just entities. The reconciliation data
records that the official function reference dates `WeekDay` to 2016.1 while a widely
circulated community workbook records a minimum core version of 2015.2, and that
`ChangeTimeZone` appears in that workbook but not in the official function reference at
all. Where sources disagree, this repository flags the disagreement rather than picking a
winner.

A version difference is also not the only reason a name can fail to resolve. A module you
have not licensed contributes no entities, so `Orion.SRM.LUNs` is equally absent from a
2026.2 server without Storage Resource Monitor and from a 2019.4 server that has it. The
error looks the same; the fix does not.

## Finding out what you actually have

Never infer a version from a name. Ask the server.

**Which modules and versions are installed:**

```sql
SELECT Name, LicenseName, Version, Family, IsEval, IsExpired
FROM Orion.InstalledModule
ORDER BY Name
```

**Which version each polling engine is running**, which also reveals a deployment mid-way
through an upgrade, where engines disagree:

```sql
SELECT EngineID, ServerName, ServerType, EngineVersion, PackageName
FROM Orion.Engines
ORDER BY EngineID
```

**Whether a specific entity exists on this server**, which is the check worth building
into any integration that must run against more than one deployment:

```sql
SELECT FullName, BaseType, CanCreate, CanRead, CanUpdate, CanDelete, CanInvoke,
       IsObsolete, ObsolescenceReason
FROM Metadata.Entity
WHERE FullName = 'Orion.SRM.StorageArrays'
```

An empty result means the entity is not part of this server's schema. Selecting the `Can*`
flags at the same time is worth the extra characters: an entity can exist and still refuse
the operation you were planning, and finding that out at query time beats finding it out
in production.

**Whether a property exists**, before you put it in a `SELECT`:

```sql
SELECT p.Entity.FullName AS EntityName,
       p.Name,
       p.Type,
       p.IsKey,
       p.IsNavigable,
       p.IsInherited,
       p.IsObsolete
FROM Metadata.Property p
WHERE p.Entity.FullName = 'Orion.Nodes' AND p.Name LIKE '%Engine%'
ORDER BY p.Name
```

Note that `Metadata.Property` has no entity-name column of its own. It reaches its owning
entity through the `Entity` navigation property, which is the reverse of
`Metadata.Entity.Properties`. That is the standard SWIS pattern, and it is why guessing a
join key is usually the wrong move: check the relationship first with
`python3 tools/schema_query.py path Metadata.Property Metadata.Entity`.

The `Metadata.*` namespace holds 11 entities describing the schema itself:
`Metadata.Entity`, `Metadata.Property`, `Metadata.Verb`, `Metadata.VerbArgument`,
`Metadata.Relationship`, and their companions. It is the only fully version-proof way to
ask questions about the schema, because it is generated from whatever schema the server is
actually running.

Verify the exact property names before writing a `Metadata` query of your own, since these
entities are as version-dependent as anything else:

```bash
python3 tools/schema_query.py show Metadata.Property
```

**Which deployment you are talking to**, which matters because SWIS URIs embed a system
identifier that is fixed when the database is created and never changes afterwards, even
if the server is renamed or replaced:

```sql
SELECT Identifier, IsLocal
FROM System.SystemIdentifier
```

## Writing automation that survives an upgrade

1. **Pin your assumptions to a version and say so.** A script that works on 2026.2 should
   record that in a comment. "It works on our server" is not a version.
2. **Probe with `Metadata.Entity` at startup** if the code will run against more than one
   deployment, and fail with a clear message naming the missing entity rather than letting
   a SWQL error surface.
3. **Prefer base entities where the semantics allow it.** `System.ManagedEntity` has
   outlived many of its descendants. A query for status across everything monitored is
   more durable written against the base type than against a list of concrete types you
   maintain by hand.
4. **Select the columns you need, never the equivalent of `SELECT *`.** A query naming six
   properties breaks only if one of those six changes; a query that consumes everything
   breaks whenever anything is added.
5. **Check verb signatures before every release upgrade.** Invoke calls pass arguments
   positionally, so a verb that gains a parameter can change meaning without changing its
   name. `python3 tools/schema_query.py verb <Entity> <Verb>` shows the current signature
   for 2026.2, and `Metadata.VerbArgument` shows it on a live server, in order:

   ```sql
   SELECT EntityName, VerbName, Position, Name, Type, IsOptional
   FROM Metadata.VerbArgument
   WHERE EntityName = 'Orion.HA.Pools' AND VerbName = 'SelectiveSwitchover'
   ORDER BY Position
   ```

   `Position` is the whole point of that query. It is the index into the JSON array you
   post to `/Invoke/{Entity}/{Verb}`, so a parameter inserted anywhere but the end shifts
   every argument after it.

## Related

- [README.md](README.md) for the section overview and the API surface summary.
- [architecture.md](architecture.md) for the deployment roles these versions apply to.
- [modules.md](modules.md) for the namespace-to-product map and the stale-name table.

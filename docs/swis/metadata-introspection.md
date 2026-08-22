# Schema introspection with the Metadata namespace

SWIS describes itself. The `Metadata` namespace exposes the schema as ordinary queryable
entities, so "what entities exist", "what is this property called", "what arguments does this
verb take and in what order" and "how do I join A to B" are all SWQL questions with SWQL
answers.

This matters more than it sounds. The extracted data in this repository documents platform
version **2026.2**, and the schema varies with the release *and* with which modules are
licensed and installed. Two servers on the same platform version legitimately expose different
entity sets. `Metadata.*` is the authoritative answer for **your** server, and it is what
SWQL Studio itself queries to build its object explorer.

Everything on this page is a plain read through the query interface. See
[rest-api.md](rest-api.md) for how to run a query, and
[../reference/entity-index.md](../reference/entity-index.md) for the offline equivalent.

## The eleven Metadata entities

Property counts below are the members each entity declares itself. All eleven additionally
inherit `DisplayName`, `Description`, `InstanceType`, `Uri` and `InstanceSiteId` from
`System.Entity`.

| Entity | Declared properties | Holds |
|:---|---:|:---|
| `Metadata.Entity` | 22 | One row per entity type, with its base type, namespace and CRUD/invoke capability flags |
| `Metadata.Property` | 23 | One row per property, with type, key/nullable/navigable/inherited flags and per-operation capability |
| `Metadata.Verb` | 8 | One row per verb, with its method name and summary |
| `Metadata.VerbArgument` | 9 | One row per verb argument, **with its position**, type, optionality and XML template |
| `Metadata.Relationship` | 20 | One row per relationship, with both navigation property names and cardinalities on both ends |
| `Metadata.EntityAlias` | 5 | Alternative names an entity answers to |
| `Metadata.EntityArgument` | 3 | Arguments an entity type itself accepts |
| `Metadata.EntityMetadata` | 4 | Free-form name/value/type annotations attached to an entity |
| `Metadata.PropertyMetadata` | 5 | The same, attached to a property |
| `Metadata.RelationshipMetadata` | 4 | The same, attached to a relationship |
| `Metadata.Functions` | 1 | The names of the SWQL functions this server supports |

All eleven inherit directly from `System.Entity` and none of them declares any CRUD or
invoke access control. They are read-only views of the schema, not something you write to.
The one exception is that `Metadata.Entity` declares two verbs of its own, covered
[below](#the-two-metadataentity-verbs).

### How they connect

Navigation properties, not string joins, are the intended way through this namespace:

```text
Metadata.Entity ──Properties──▶ Metadata.Property ──Metadata──▶ Metadata.PropertyMetadata
       │                                 └──Entity──▶ Metadata.Entity
       ├──Verbs──▶ Metadata.Verb ──Arguments──▶ Metadata.VerbArgument
       │                  └──Entity──▶ Metadata.Entity      └──Verb──▶ Metadata.Verb
       ├──Arguments──▶ Metadata.EntityArgument
       ├──EntityAliases──▶ Metadata.EntityAlias
       ├──Metadata──▶ Metadata.EntityMetadata
       ├──Dependents──▶ Metadata.Relationship
       └──Antecedents──▶ Metadata.Relationship

Metadata.Relationship ──Source──▶ Metadata.Entity
                      ──Target──▶ Metadata.Entity
                      ──Metadata──▶ Metadata.RelationshipMetadata
```

**Read the naming carefully, because it is the thing that breaks queries copied from older
scripts.** In 2026.2:

- `Metadata.Verb` has **no** `EntityName` property. It reaches its owner through the
  `Entity` navigation property, so you filter with `v.Entity.FullName = '...'`.
- `Metadata.Property` also has **no** `EntityName` property. Same rule: `p.Entity.FullName`.
- `Metadata.VerbArgument` **does** carry flat `EntityName` and `VerbName` strings, which is
  why the most important query on this page needs no join at all.
- `Metadata.EntityAlias`, `Metadata.EntityArgument`, `Metadata.EntityMetadata` and
  `Metadata.PropertyMetadata` all carry a flat `EntityName` as well.

This is worth stressing because the pattern outlives the schema. A query of the form
`SELECT Name FROM Metadata.Property WHERE Entity.FullName='Metadata.Entity' AND Name IN (...)`
is reported to ship in SWQL Studio's own source; that provenance is **unverified** here,
because this repository holds no copy of it. The part that matters is checked: `EntityName`
is not a `Metadata.Property` property in the 2026.2 schema. If you inherit a script written
that way, rewrite the filter as `Entity.FullName` and confirm it against your own server
before trusting either form.

## Metadata.Entity: what exists and what you can do to it

The capability flags are the reason to start here. `CanCreate`, `CanRead`, `CanUpdate`,
`CanDelete` and `CanInvoke` tell you which interfaces will accept the entity **before** you
write code against it.

```sql
SELECT FullName, BaseType, IsAbstract, CanCreate, CanRead, CanUpdate, CanDelete, CanInvoke
FROM Metadata.Entity
WHERE IsInternal = FALSE
ORDER BY FullName
```

Find an entity when you only remember part of the name. This is the single most useful query
in the namespace, because plausible-but-wrong entity names are the most common mistake anyone
makes against SWIS:

```sql
SELECT FullName, BaseType, Summary
FROM Metadata.Entity
WHERE FullName LIKE @pattern
ORDER BY FullName
```

Bind `@pattern` to something like `%Interface%` or `Orion.SRM.%`.

Everything you can create through CRUD:

```sql
SELECT FullName, BaseType
FROM Metadata.Entity
WHERE CanCreate = TRUE AND IsInternal = FALSE
ORDER BY FullName
```

Everything that has verbs to invoke:

```sql
SELECT FullName, CanInvoke
FROM Metadata.Entity
WHERE CanInvoke = TRUE AND IsInternal = FALSE
ORDER BY FullName
```

Entity counts by namespace, which is the live equivalent of
`data/schema/2026.2/manifest.json` and a fast way to see which modules are installed:

```sql
SELECT Namespace, COUNT(FullName) AS EntityCount
FROM Metadata.Entity
GROUP BY Namespace
ORDER BY COUNT(FullName) DESC
```

Everything that inherits from a given base type. `System.ManagedEntity` is the interesting
one, because it is the set of things with an externally determined up/down status:

```sql
SELECT FullName, BaseType, IsAbstract, IsSingleton, IsDynamic, IsFederated
FROM Metadata.Entity
WHERE BaseType = 'System.ManagedEntity'
ORDER BY FullName
```

`BaseType` gives one level of the chain. To walk the whole chain you query repeatedly, or use
the offline equivalent which already has it flattened:

```bash
python3 tools/schema_query.py children System.ManagedEntity
python3 tools/schema_query.py show Orion.Nodes          # prints the full inheritance chain
```

## Metadata.Property: what the columns are called

Every property of one entity, with the flags that decide how you can use each one:

```sql
SELECT p.Name, p.Type, p.IsKey, p.IsNullable, p.IsNavigable, p.IsInherited, p.IsMetric, p.Units, p.Summary
FROM Metadata.Property p
WHERE p.Entity.FullName = @entity
ORDER BY p.IsKey DESC, p.Name
```

Ordering keys first is deliberate: the key properties are what you need to build a URI and to
address the entity through CRUD.

Just the keys:

```sql
SELECT p.Entity.FullName AS EntityName, p.Name, p.Type
FROM Metadata.Property p
WHERE p.IsKey = TRUE AND p.Entity.FullName IN @entities
ORDER BY p.Entity.FullName, p.Name
```

Only the properties this entity declares itself, with `IsInherited = FALSE` filtering out
everything that came from a base type. Useful when you want to know what makes this entity
different from its parent:

```sql
SELECT p.Name, p.Type, p.IsKey, p.IsNavigable, p.IsSortable, p.FilterBy, p.GroupBy
FROM Metadata.Property p
WHERE p.Entity.FullName = 'Orion.Nodes' AND p.IsInherited = FALSE
ORDER BY p.Name
```

Which entities expose a property of a given name. This answers "I know the column, which
table is it on":

```sql
SELECT p.Entity.FullName AS EntityName, p.Name, p.Type
FROM Metadata.Property p
WHERE p.Name = @property AND p.IsInherited = FALSE
ORDER BY p.Entity.FullName
```

What is actually settable, which is how you find out that a property is readable but not
writable **before** your update silently changes nothing:

```sql
SELECT p.Name, p.Type, p.CanCreate, p.CanUpdate
FROM Metadata.Property p
WHERE p.Entity.FullName = 'Orion.Nodes' AND p.CanUpdate = TRUE
ORDER BY p.Name
```

Metric properties, with their units and bounds. These are the properties worth charting:

```sql
SELECT p.Name, p.Type, p.IsMetric, p.Units, p.MinValue, p.MaxValue
FROM Metadata.Property p
WHERE p.Entity.FullName = 'Orion.Nodes' AND p.IsMetric = TRUE
ORDER BY p.Name
```

Enumerated properties. `Values` is a `System.String[]` holding the permitted values where the
schema declares them, which saves guessing at magic strings:

```sql
SELECT p.Name, p.Values
FROM Metadata.Property p
WHERE p.Entity.FullName = 'Orion.Nodes' AND p.Values IS NOT NULL
ORDER BY p.Name
```

## Metadata.Verb and Metadata.VerbArgument: how to call things

This is the pair that matters most, because verb arguments are positional and the order is
the entire contract. See [invoke-verbs.md](invoke-verbs.md) for how to actually make the call.

Every verb on one entity:

```sql
SELECT v.Name, v.CanInvoke, v.IsObsolete, v.Summary
FROM Metadata.Verb v
WHERE v.Entity.FullName = 'Orion.Nodes'
ORDER BY v.Name
```

**A verb's arguments, in order.** This is the definitive answer to "what do I pass to Invoke",
and it needs no join because `Metadata.VerbArgument` carries `EntityName` and `VerbName`
directly:

```sql
SELECT Position, Name, Type, IsOptional, Summary
FROM Metadata.VerbArgument
WHERE EntityName = 'Orion.Nodes' AND VerbName = 'Unmanage'
ORDER BY Position
```

`ORDER BY Position` is not cosmetic. A result set in arbitrary order is actively dangerous
here, because it looks like an answer and is not one.

Every verb on the server, with its owner:

```sql
SELECT v.Entity.FullName AS EntityName, v.Name AS VerbName, v.CanInvoke, v.Summary
FROM Metadata.Verb v
WHERE v.IsInternal = FALSE
ORDER BY v.Entity.FullName, v.Name
```

**Which entities support a verb of a given name.** This is how you answer "what else can I
unmanage on this server", and it is a question the offline data cannot answer for a module you
have installed but this repository does not document:

```sql
SELECT v.Entity.FullName AS EntityName, v.Name AS VerbName, v.Summary
FROM Metadata.Verb v
WHERE v.Name = 'Unmanage'
ORDER BY v.Entity.FullName
```

Verbs and their full argument lists together, joining the two entities explicitly. Note that
the join predicate uses the navigation property on the left side, because `Metadata.Verb` has
no flat entity-name column:

```sql
SELECT v.Entity.FullName AS EntityName, v.Name AS VerbName, a.Position, a.Name AS ArgumentName, a.Type, a.IsOptional
FROM Metadata.Verb v
JOIN Metadata.VerbArgument a ON a.EntityName = v.Entity.FullName AND a.VerbName = v.Name
WHERE v.Entity.FullName = 'Orion.AlertActive'
ORDER BY v.Name, a.Position
```

You can go the other way too. `Metadata.VerbArgument.Verb` navigates back to the verb, which
lets you pull the verb's summary alongside each argument in one pass:

```sql
SELECT a.EntityName, a.VerbName, a.Position, a.Name AS ArgumentName, a.Type, a.Verb.Summary AS VerbSummary
FROM Metadata.VerbArgument a
WHERE a.EntityName = 'Orion.Nodes'
ORDER BY a.VerbName, a.Position
```

Which entities have how many verbs, useful for finding where the surface area is:

```sql
SELECT v.Entity.FullName AS EntityName, COUNT(v.Name) AS VerbCount
FROM Metadata.Verb v
GROUP BY v.Entity.FullName
ORDER BY COUNT(v.Name) DESC
```

### Complex arguments: XmlTemplate and XmlSchemas

Most verb arguments are scalars or arrays. Some are .NET contract types, and for those you
have to hand SWIS an XML document. `Metadata.VerbArgument` publishes the skeleton:

```sql
SELECT Position, Name, Type, XmlTemplate
FROM Metadata.VerbArgument
WHERE EntityName = 'Orion.Discovery' AND VerbName = 'StartDiscovery'
ORDER BY Position
```

`XmlSchemas` is a `System.String[]` of the schemas the document is validated against, and it
is where the namespace declarations on the root element come from:

```sql
SELECT a.EntityName, a.VerbName, a.Position, a.Name, a.Type, a.XmlSchemas
FROM Metadata.VerbArgument a
WHERE a.EntityName = 'Orion.Discovery'
ORDER BY a.VerbName, a.Position
```

Every argument on the server that needs this treatment, so you know what you are in for
before you start:

```sql
SELECT EntityName, VerbName, Position, Name, Type
FROM Metadata.VerbArgument
WHERE XmlTemplate IS NOT NULL
ORDER BY EntityName, VerbName, Position
```

This is exactly what SWQL Studio's Invoke Verb tab renders next to each complex argument.

### The two Metadata.Entity verbs

`Metadata.Entity` is the only entity in the namespace that declares verbs.

```text
Metadata.Entity.GetAliases(query) -> array
Metadata.Entity.GetSchemaLoadTime() -> string
```

`GetAliases` takes a SWQL statement and returns the table aliases SWIS assigns to it,
**without running the query**. It is SolarWinds' own example in the official
[REST](https://solarwinds.github.io/OrionSDK/docs/rest/) documentation: posting
`["SELECT B.Caption FROM Orion.Nodes B"]` to
`/Invoke/Metadata.Entity/GetAliases` returns `{"B":"Orion.Nodes"}`. That makes it a cheap
parse check for a generated query.

```powershell
Invoke-SwisVerb $swis 'Metadata.Entity' 'GetAliases' @('SELECT B.Caption FROM Orion.Nodes B')
```

`GetSchemaLoadTime` takes no arguments and reports when the server last loaded its schema.
Worth checking after installing or licensing a module, because until the schema reloads the
new entities are not there to find.

```powershell
Invoke-SwisVerb $swis 'Metadata.Entity' 'GetSchemaLoadTime' @()
```

## Metadata.Relationship: how to join A to B

`Metadata.Relationship` is the only place that tells you both navigation property names and
the cardinality on each end. `SourcePropertyName` and `TargetPropertyName` are the names you
dot-walk in SWQL.

Everything touching one entity, from either direction:

```sql
SELECT Name, SourceType, TargetType, SourcePropertyName, TargetPropertyName, SourceCardinalityMin, SourceCardinalityMax, TargetCardinalityMin, TargetCardinalityMax
FROM Metadata.Relationship
WHERE SourceType = 'Orion.Nodes' OR TargetType = 'Orion.Nodes'
ORDER BY Name
```

Both directions are navigable **from** the entity in question. `Orion.Nodes.Interfaces`
(where `Orion.Nodes` is the source) and `Orion.NPM.Interfaces.Node` (where `Orion.Nodes` is
the target) are both valid SWQL. This surprises people who assume the source column means
"one-way".

What points **at** this entity, which is the query you want when working out what a delete
would cascade into:

```sql
SELECT r.Name, r.SourceType, r.SourcePropertyName, r.TargetType, r.TargetPropertyName
FROM Metadata.Relationship r
WHERE r.TargetType = 'Orion.Nodes'
ORDER BY r.SourceType
```

`Source` and `Target` are navigation properties leading to `Metadata.Entity`, so you can pull
entity-level facts into the same result set:

```sql
SELECT r.Name, r.SourcePropertyName, r.TargetPropertyName, r.Source.FullName AS SourceEntity, r.Target.FullName AS TargetEntity
FROM Metadata.Relationship r
WHERE r.Source.FullName = 'Orion.Nodes'
ORDER BY r.Name
```

The offline equivalent, which also does multi-hop pathfinding that a single SWQL query cannot:

```bash
python3 tools/schema_query.py path Orion.APM.Component Orion.Nodes
```

## Aliases, entity arguments and metadata bags

`Metadata.EntityAlias` lists alternative names an entity answers to. Worth checking when a
script from another version references a name that no longer resolves:

```sql
SELECT ea.EntityName, ea.Alias
FROM Metadata.EntityAlias ea
WHERE ea.EntityName LIKE 'Orion.%'
ORDER BY ea.EntityName
```

`Metadata.EntityArgument` holds arguments attached to an entity type rather than to a verb.
The schema publishes no summary for it, so take the three property names as the description:
`EntityName`, `ArgumentName` and `ArgumentType`. `Metadata.Entity` reaches it through the
`Arguments` navigation property. Run the query on your own server to see what it actually
contains there:

```sql
SELECT EntityName, ArgumentName, ArgumentType
FROM Metadata.EntityArgument
ORDER BY EntityName, ArgumentName
```

The three `*Metadata` entities are free-form name/value/type annotation bags hung off
entities, properties and relationships. What they contain is server-specific, so treat these
as exploratory:

```sql
SELECT EntityName, Name, Value, Type
FROM Metadata.EntityMetadata
WHERE EntityName = 'Orion.Nodes'
ORDER BY Name
```

```sql
SELECT EntityName, PropertyName, Name, Value, Type
FROM Metadata.PropertyMetadata
WHERE EntityName = 'Orion.Nodes'
ORDER BY PropertyName, Name
```

```sql
SELECT RelationshipName, Name, Value, Type
FROM Metadata.RelationshipMetadata
ORDER BY RelationshipName, Name
```

## Metadata.Functions: which SWQL functions this server has

One property, `Name`. This is the live version of
[../reference/swql-function-index.md](../reference/swql-function-index.md), and it is the way
to settle "does my version have this function" without trial and error:

```sql
SELECT Name
FROM Metadata.Functions
ORDER BY Name
```

Checking one function before you build a query around it:

```sql
SELECT Name
FROM Metadata.Functions
WHERE Name = @functionName
```

This is particularly worth doing for functions where the published sources disagree.
`data/reference/reconciliation.json` in this repository records `ChangeTimeZone` as used in
the community workbook but absent from the official function reference, so
`Metadata.Functions` is how you find out whether your server actually has it.

## Obsolete and internal members

`IsObsolete`, `ObsolescenceReason` and `IsInternal` appear on `Metadata.Entity`,
`Metadata.Property`, `Metadata.Verb`, `Metadata.Relationship` and `Metadata.EntityAlias`.
Check them before building an automation on something you found in an old script.

```sql
SELECT FullName, ObsolescenceReason
FROM Metadata.Entity
WHERE IsObsolete = TRUE
ORDER BY FullName
```

```sql
SELECT v.Entity.FullName AS EntityName, v.Name AS VerbName, v.ObsolescenceReason
FROM Metadata.Verb v
WHERE v.IsObsolete = TRUE
ORDER BY v.Entity.FullName, v.Name
```

`IsInternal = TRUE` marks members SolarWinds exposes for its own use. They are visible and
sometimes queryable, but they are not a contract and they will change without notice. Filter
them out of anything you build on, which is why most of the queries on this page carry
`WHERE ... IsInternal = FALSE`.

## Comparing your server against this repository

If an entity, property or verb in `data/schema/2026.2/` does not exist on your server, the
usual explanations, in order of likelihood, are: a different platform version; a module that
is not installed or not licensed; or the schema has not reloaded since a module was added.

A concrete workflow for reconciling the two:

```bash
# 1. What does the repository think exists?
python3 tools/schema_query.py find interface --properties
python3 tools/schema_query.py verbs --entity Orion.Nodes
python3 tools/schema_query.py stats
```

```sql
-- 2. What does your server actually have? Compare the counts first.
SELECT COUNT(FullName) AS Entities FROM Metadata.Entity
```

```sql
-- 3. Then the specific thing you care about.
SELECT FullName, BaseType, CanCreate, CanInvoke
FROM Metadata.Entity
WHERE FullName LIKE '%Interface%'
ORDER BY FullName
```

```sql
-- 4. And the exact call signature, which is the part worth being certain about.
SELECT Position, Name, Type, IsOptional
FROM Metadata.VerbArgument
WHERE EntityName = 'Orion.Nodes' AND VerbName = 'Unmanage'
ORDER BY Position
```

When the two disagree, the server wins. Prefer telling a user how to check their own server
over guessing on their behalf.

## Practical notes

- **These are queries, so account limitations and query rules apply.** Bind parameters rather
  than concatenating strings, and bound the result set with `TOP n` or
  `WITH ROWS a TO b WITH TOTALROWS` when you are exploring. `Metadata.Property` returns one
  row per property per entity and carries an `IsInherited` flag, so inherited members are rows
  too. The offline extraction counts 19328 **declared** properties across 2067 entities in
  2026.2; the live entity will return more than that, because every inherited member of every
  descendant is its own row.
- **Cache the answers.** The schema changes when a module is installed or the platform is
  upgraded, not between requests. `Metadata.Entity.GetSchemaLoadTime` gives you a cheap
  cache-invalidation key.
- **`Type` and `BaseType` on `Metadata.Entity` are `System.Type`, not `System.String`.** They
  compare against string literals in the queries above, which is how the repository's own
  sample queries and SWQL Studio use them, but it is worth knowing the declared type if a
  comparison behaves oddly.
- **Verbs whose `parameters` list is empty in the offline data are exactly the case this page
  solves.** 173 of the 1021 verb records in `data/schema/2026.2/verbs.json` carry no parameter
  list, and 84 of those have no `/Invoke/` path in the Swagger contract either. For any of
  them, `Metadata.VerbArgument` on your own server is the only reliable answer.

## Where to go next

- [invoke-verbs.md](invoke-verbs.md) turns a `Metadata.VerbArgument` result into an actual
  call.
- [verb-catalog.md](verb-catalog.md) is the curated shortlist of useful verbs by task.
- [crud.md](crud.md) uses `Metadata.Entity` and `Metadata.Property` capability flags to decide
  which operations an entity supports.
- [uris.md](uris.md) explains why the key properties from `Metadata.Property` matter.
- `scripts/swql/08-schema-introspection.swql` holds these queries in runnable form.
- [../reference/entity-index.md](../reference/entity-index.md),
  [../reference/verb-index.md](../reference/verb-index.md) and
  [../reference/swql-function-index.md](../reference/swql-function-index.md) are the offline
  equivalents for platform version 2026.2.

Official upstream sources:

- [About SWIS](https://solarwinds.github.io/OrionSDK/docs/about-swis/)
- [REST](https://solarwinds.github.io/OrionSDK/docs/rest/)
- [Schema reference](https://solarwinds.github.io/OrionSDK/2026.2/schema/index.html)
- [Orion SDK wiki](https://github.com/solarwinds/OrionSDK/wiki)

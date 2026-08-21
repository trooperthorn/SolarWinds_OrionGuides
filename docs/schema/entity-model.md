# The entity model

SWIS is described by SolarWinds as "a hybrid of object-oriented and relational features"
([About SWIS](https://solarwinds.github.io/OrionSDK/docs/about-swis/)). The relational half
is familiar: entities have properties, and SWQL selects them. The object-oriented half is
what surprises people, and it is where most of the leverage is. Entity types are arranged in
an inheritance tree, properties are inherited down that tree, and a query against a base
type returns rows from every type beneath it.

This page explains that model. For what inheritance does to a **query** in practice, and how
to filter a base-entity result by concrete type, see
[joins-and-navigation.md](../swql/joins-and-navigation.md).

## The tree is rooted at System.Entity

```bash
python3 tools/schema_query.py show System.Entity
```

```text
System.Entity   [2026.2]
  System.Entity is the root of the SWIS type hierarchy. It carries no particular meaning or semantics. Choose System.Entity as your base type when no other type makes sense. It does define four properties that will be inherited by every other entity type in SWIS: DisplayName, Description, InstanceType, and Uri. The values for InstanceType and Uri will be filled in by SWIS, so you should not map those to storage properties. If you have a property that makes sense to call "DisplayName" or "Description", then you should map accordingly.
  operations: (none declared)

  properties (5)
    DisplayName                                System.String               
    Description                                System.String               
    InstanceType                               System.Type                 
    Uri                                        System.String                 All entity types have the Uri property which value is uniquely identifying an entity insta
    InstanceSiteId                             System.Int32                

  targetRelationships (1) - this entity is the target; property leads back to the source
    OrionSite                                  -> Orion.Sites                                  System.Reference
```

The summary says four properties; the page lists five. `InstanceSiteId` is present in the
2026.2 schema and is not mentioned in that prose, which was presumably written earlier. The
property list is the authority.

Of the 2067 entities in 2026.2, **2043 have `System.Entity` somewhere in their inheritance
chain**. The remaining 24 are `System.Entity` itself and 23 entities in the `Cortex`
namespace: `Cortex.System.ElementInstance`, the 21 entities that descend from it, and
`Cortex.Orion.NetMan.CloudMonitoring.VirtualNetworkGateway.Metrics`. Two of those 23 record
no base type at all on their published pages — `Cortex.System.ElementInstance` and
`Cortex.Orion.NetMan.CloudMonitoring.VirtualNetworkGateway.Metrics` — which makes them look
like additional roots alongside `System.Entity`.

The official documentation says "each entity type has a parent entity type except the root
type, `System.Entity`", so the likelier explanation is that those two pages do not render an
inheritance section rather than that the tree has three roots. Treat it as unverified. On
your own server one query settles it:

```sql
SELECT e.FullName, e.BaseType
FROM Metadata.Entity e
WHERE e.FullName LIKE 'Cortex.%'
ORDER BY e.FullName
```

Verify the split yourself:

```bash
python3 tools/schema_query.py children System.Entity
```

```text
2043 entity/entities inherit from System.Entity
```

## Properties are inherited

From the official documentation:

> Properties declared on parent entity types are inherited by the child entity types. For
> example, `System.Entity` defines a `DisplayName` property. Because all other entity types
> ultimately have `System.Entity` as a parent/ancestor type, all entities have a
> `DisplayName` property.

The consequence for anyone reading the schema is important and easy to miss: **an entity
page lists only the properties that entity declares.** `Orion.Nodes` declares 102
properties. It has 113. The other 11 come from its ancestors and are perfectly queryable,
but you will not find them by reading the `Orion.Nodes` page.

`schema_query.py props` resolves the chain by default, and tags each inherited member with
where it came from:

```bash
python3 tools/schema_query.py props Orion.Nodes --grep unmanage
```

```text
Orion.Nodes properties (3 shown, including inherited)
  UnManaged                                  System.Boolean                True, Whether the entity is current unmanaged, otherwise false.  [from System.ManagedEntity]
  UnManageFrom                               System.DateTime               The datetime when this entity became/will become unmanaged  [from System.ManagedEntity]
  UnManageUntil                              System.DateTime               The datetime when this entity will exit the unmanaged state  [from System.ManagedEntity]
```

Pass `--no-inherited` when you want to know what makes an entity different from its parent
rather than what you can select from it.

An entity may also **redeclare** a property its parent already has. The ancestors of
`Orion.Nodes` declare 18 properties between them, and `Orion.Nodes` redeclares seven of them
(`DisplayName`, `Description`, `Status`, `StatusLED`, `StatusDescription`, `DetailsUrl` and
`ModernIcon`). That is why the resolved count is 113 and not 120.

## The chain for a real entity

```bash
python3 tools/schema_query.py show Orion.Nodes
```

```text
Orion.Nodes   [2026.2]
  inherits: System.Entity -> System.DashboardEntity -> System.ManagedEntity -> Orion.Nodes
  operations: create, delete, invoke, read, update
```

Reading the chain left to right tells you what a node is, in the schema's own terms:

| Level | Declares | Meaning |
| --- | --- | --- |
| `System.Entity` | `DisplayName`, `Description`, `InstanceType`, `Uri`, `InstanceSiteId` | It is a thing SWIS knows about |
| `System.DashboardEntity` | `Status`, `DetailsUrl`, `ModernIcon`, `EntityLink` | It can be put on a modern dashboard |
| `System.ManagedEntity` | `StatusDescription`, `StatusLED`, `UnManaged`, `UnManageFrom`, `UnManageUntil`, `Image`, `AncestorDisplayNames`, `AncestorDetailsUrls`, `StatusIconHint` | It has an externally determined up/down status, and can be unmanaged |
| `Orion.Nodes` | 102 properties including `NodeID`, `IPAddress`, `Caption`, `EngineID` | It is specifically a node |

`System.ManagedEntity`'s own summary is the clearest one-line definition in the schema: "A
ManagedEntity is basically 'something that has an externally-determined up/down status'.
These entities represent the things that our monitoring products monitor: servers, network
interfaces, applications, etc."

The chain is at most six levels deep in 2026.2. The deepest examples are the cloud instance
types, for example `Orion.Cloud.Aws.Instances`, whose chain runs `System.Entity ->
System.DashboardEntity -> System.ManagedEntity -> Orion.Virtualization.Instance ->
Orion.Cloud.Instances -> Orion.Cloud.Aws.Instances`.

## The base types worth knowing

Counts are the number of entity types with that base type anywhere in their chain.

| Base entity | Descendants | Why it matters |
| --- | ---: | --- |
| `System.Entity` | 2043 | The root |
| `System.ExtensionEntity` | 305 | "Providing additional properties about another entity", linked back by a `System.Hosting` relationship. Declares nothing itself |
| `System.StatisticsEntity` | 236 | Statistical data. Declares `ObservationTimestamp`, `ObservationFrequency`, `Weight` |
| `System.DashboardEntity` | 180 | Declares `Status`, `DetailsUrl`, `ModernIcon`, `EntityLink` |
| `System.ManagedEntity` | 174 | Monitored objects with an up/down status |
| `Orion.Thresholds` | 133 | Threshold configuration |
| `System.Indication` | 112 | Events SWIS publishes, with `IndicationID`, `IndicationTime`, `IndicationSequence`, `AccountID` |
| `System.CustomPropertiesEntity` | 25 | Installation-defined custom properties |
| `Cortex.System.ElementInstance` | 21 | The root of the `Cortex` element tree |

`System.ExtensionEntity` and `System.StatisticsEntity` are the two that explain the shape of
the rest of the schema. Statistics and rollups are not columns on the monitored entity, they
are separate entity types hosted off it, which is why `Orion.Nodes` has a `CPULoadHistory`
navigation to `Orion.CPULoad` rather than a history column.

## Querying a base entity returns every descendant

This is the payoff of the whole arrangement, and it is stated plainly in the official
documentation:

> If you write a query against a base entity type, data from all entity types that have that
> base entity type as an ancestor will be returned. So `SELECT TOP 10 DisplayName FROM
> System.ManagedEntity ORDER BY DisplayName` would return the first 10 display names
> (alphabetically) across all managed entity types (nodes, interfaces, applications, groups,
> etc.).

So "what is in a maintenance window right now, of any type" is one query rather than a union
over every monitored entity type, because `UnManaged` is declared once, on
`System.ManagedEntity`:

```sql
SELECT TOP 20 m.DisplayName, m.InstanceType, m.Status, m.UnManaged
FROM System.ManagedEntity m
ORDER BY m.DisplayName
```

The same applies at every level, not just at the top. `Orion.Cloud.Instances` has three
descendants:

```bash
python3 tools/schema_query.py children Orion.Cloud.Instances
```

```text
3 entity/entities inherit from Orion.Cloud.Instances
  Orion.Cloud.Aws.Instances
  Orion.Cloud.Azure.Instances
  Orion.Cloud.Gcp.Instances
```

so selecting from the parent covers all three clouds at once, and `InstanceType` tells you
which one each row came from:

```sql
SELECT TOP 20 i.DisplayName, i.InstanceType, i.Provider, i.Region
FROM Orion.Cloud.Instances i
WHERE i.InstanceType = 'Orion.Cloud.Aws.Instances'
ORDER BY i.DisplayName
```

The cost is that a base-entity query only gives you the base type's properties. `Status` and
`DisplayName` are there because they are declared high up; `Orion.Nodes.IPAddress` is not,
because most managed entities do not have an IP address. When you need type-specific
columns, select from the concrete entity.

## The four cross-entity properties

Four properties are on effectively every entity, and each answers a different question. Only
the first three are declared on `System.Entity`; `DetailsUrl` comes from
`System.DashboardEntity` and so exists on 180 entity types rather than all of them.

### DisplayName

Declared on `System.Entity`. The human-readable label for one instance. It is the property
that makes a base-entity query useful, because it is the one column you can select from
`System.ManagedEntity` and get something meaningful for a node, an interface and an
application alike.

Note that many concrete entities also have their own caption-like column: `Orion.Nodes` has
`Caption`, `Orion.APM.Application` has `Name`. When you are selecting from the concrete
entity, prefer its own column; `DisplayName` is for when you do not know what you are
looking at.

### InstanceType

Declared on `System.Entity`, type `System.Type`. SWIS fills it in with the concrete entity
type of each row. It is both the column that tells you what a base-entity query actually
returned and the predicate that narrows it, as in the cloud example above. The schema
summary is explicit that SWIS supplies the value: "The values for InstanceType and Uri will
be filled in by SWIS, so you should not map those to storage properties."

### Uri

Declared on `System.Entity`. The identity of one instance, and the handle that Read, Update
and Delete take. Selecting it is the correct way to obtain one:

```sql
SELECT TOP 10 n.Uri, n.Caption
FROM Orion.Nodes n
WHERE n.Uri IS NOT NULL
```

The format, the system identifier and the reasons not to assemble URIs by hand are covered
in [uris.md](../swis/uris.md).

### DetailsUrl

Declared on `System.DashboardEntity`, described there as "A relative url for the 'details
page' for this entity". It is a web console link, not an API address. `Orion.Nodes`
redeclares it. `System.ManagedEntity` additionally declares `AncestorDetailsUrls`, an array
that walks the hosting chain upward, which is what lets a UI render a breadcrumb without
knowing the entity type.

## Key properties

A key property is what identifies one instance. Keys are what go into the key filter segment
of a URI, and they are what a CRUD create returns to you.

The extract carries them for the entities most people address by NetObject, in
[data/reference/netobject-types.json](../../data/reference/netobject-types.json), 115 rows
covering the main monitored types:

```bash
jq -r '.[] | select(.entity=="Orion.Nodes")' data/reference/netobject-types.json
```

```json
{
  "entity": "Orion.Nodes",
  "module": "Core",
  "displayName": "Node",
  "netObjectPrefix": "N",
  "keyProperties": [
    "NodeID"
  ],
  "parentEntities": [
    "Orion.Engines"
  ],
  "captionColumn": null,
  "inCurrentSchema": true
}
```

Twelve of those 115 rows have `inCurrentSchema: false`, meaning the workbook they came from
names an entity that is not in the published 2026.2 schema. Eight of the twelve carry a
`supersededBy` field pointing at the current name, which is how `Orion.VIM.LUNs` resolves to
`Orion.VIM.Luns`. Never take a row with `inCurrentSchema: false` as a current fact. See
[netobject-types.md](../reference/netobject-types.md) and
[reconciliation.json](../../data/reference/reconciliation.json).

### Keys stated in the schema's own prose

The rendered schema pages have no column marking a key, but SolarWinds sometimes says so in
the property's description: `Orion.NPM.Interfaces.InterfaceID` reads "Interface ID. Primary
key." The extraction picks those up into a `keyHints` field, which covers 79 entities. It
appears in `show`:

```bash
python3 tools/schema_query.py show Orion.NPM.Interfaces
```

```text
Orion.NPM.Interfaces   [2026.2]
  This entity presents information about Node interfaces
  inherits: System.Entity -> System.DashboardEntity -> System.ManagedEntity -> Orion.NPM.Interfaces
  operations: create, delete, invoke, read, update
  key (from property prose): InterfaceID
```

The name says what it is. A hint is SolarWinds' prose, not a schema declaration, and the
absence of one means nothing at all: most entities simply have no description on the
property. Treat it as a strong starting point and confirm it.

Some entities also carry the answer on themselves. `Orion.Nodes` declares `OrionIdPrefix`
and `OrionIdColumn`, which is the schema naming the NetObject prefix and the key column
rather than making you look them up. Both properties exist in 2026.2; their values are a
runtime matter, so select them on your own server rather than trusting a value quoted
anywhere.

### The authoritative answer

For a specific server, the schema declares keys properly and `Metadata.Property` has an
`IsKey` flag. This is the only source that is both complete and current for the version in
front of you, and it covers entities the workbook never mentioned:

```sql
SELECT p.Name, p.Type, p.IsKey, p.CanCreate, p.CanUpdate
FROM Metadata.Property p
WHERE p.Entity.FullName = @entity
ORDER BY p.IsKey DESC, p.Name
```

Note the shape of that `WHERE` clause. `Metadata.Property` has no `EntityName` column; it
reaches its entity through the `Entity` navigation property, which is the target end of a
`System.Hosting` relationship from `Metadata.Entity`. Trying to filter on a bare
`EntityName` is a common and confusing failure. `Metadata.VerbArgument`, by contrast, does
have `EntityName` and `VerbName` columns. See
[metadata-introspection.md](../swis/metadata-introspection.md) for the full set.

## Why some entities have no URI

Every entity inherits `Uri`, so every entity has the column. That does not mean every row has
a value. The schema says so on the property itself:

> All entity types have the Uri property which value is uniquely identifying an entity
> instance in the system. The value may be blank if the entity type doesn't define an
> identity for its instances.

An entity type has no identity for its instances when there is nothing to identify: an
aggregate, a rollup, a computed view, a statistics row keyed only by a timestamp. Those types
are readable but not addressable, which has three practical consequences:

1. **CRUD does not apply to them.** Read, Update and Delete take URIs. Without one, there is
   nothing to pass. This is separate from, and additional to, the official caveat that "there
   may be entity types that do not support this interface or provide only limited support due
   to technical or design reasons."
2. **They cannot be the target of a saved reference.** Alerts, reports and group definitions
   store URIs, so an entity with no URI cannot be referenced from one.
3. **`BulkUpdate` and `BulkDelete` cannot touch them**, for the same reason. See
   [bulk-operations.md](../swis/bulk-operations.md).

The extract cannot tell you which entities these are, because the published pages record
properties and inheritance but not which properties are keys. Ask your server:

```sql
SELECT e.FullName, e.BaseType
FROM Metadata.Entity e
WHERE e.FullName NOT IN (
    SELECT p.Entity.FullName
    FROM Metadata.Property p
    WHERE p.IsKey = TRUE
)
ORDER BY e.FullName
```

What the extract *can* tell you is which entities declare no CRUD operations at all, which is
a related and useful signal. Of the 2067 entities, 1610 declare no operations in their access
control table, and 250 are creatable.

## Access control

Every entity page carries an **Access control** table mapping a set of operations to the
Orion right that grants them, and every verb carries its own. This is the part of the schema
that explains permission failures, and it is worth reading before assuming a bug.

```bash
python3 tools/schema_query.py show Orion.Nodes
```

```text
  operations: create, delete, invoke, read, update
    read                                   requires everyone
    read,invoke                            requires allowRealTimePolling
    create,read,update,delete,invoke       requires manageNodes
```

Read that as a set of grants, not a hierarchy. Any account can read nodes. An account with
`allowRealTimePolling` can additionally invoke the real-time polling verbs. An account with
`manageNodes` can do everything including create and delete.

### The rights that appear in 2026.2

Fifteen distinct rights appear across entity and verb access control tables in the extract.
The counts are how many entities name that right.

| Right | Entities | Gates |
| --- | ---: | --- |
| `everyone` | 393 | No right required beyond being authenticated. Almost always paired with `read` |
| `admin` | 229 | Full administrative access |
| `manageNodes` | 104 | Creating, changing and deleting monitored objects, and most polling verbs |
| `system` | 21 | Internal operations |
| `manageAlerts` | 16 | Alert definitions and alert lifecycle verbs |
| `manageReports` | 12 | Report definitions |
| `allowUnmanage` | 6 | Putting objects into and out of maintenance mode |
| `allowRealTimePolling` | 6 | Starting and stopping real-time polling |
| `allowDisableAlert` | 3 | Disabling alerts |
| `allowOrionMapsManagement` | 3 | Orion Maps projects and topology |
| `manageMaps` | 3 | Network Atlas map files and wireless heat maps |
| `AllowDisableAllActions` | 1 | Disabling all alert actions |
| `allowDisableAction` | 1 | Disabling an individual alert action |
| `clearEvents` | 1 | Clearing events |
| `allowCustomize` | 1 | Customizing web resources |

Three of those are worth spelling out because they come up constantly in automation.

**`manageNodes`** is the broad one. It gates create, read, update, delete and invoke on
`Orion.Nodes` and 103 other entities, and it is required by 129 verbs. If a script that adds
nodes, assigns pollers or edits custom properties fails with a permission error, this is
almost always the missing right.

**`allowUnmanage`** gates maintenance mode specifically, and it is deliberately separate from
`manageNodes` so that an operator can silence alerts during a change window without also
being able to delete monitoring. Ten verbs require it:

```bash
jq -r '.[] | select(any(.accessControl[]?; .right=="allowUnmanage")) | "\(.entity).\(.name)"' data/schema/2026.2/verbs.json
```

```text
Orion.AlertSuppression.ResumeAlerts
Orion.AlertSuppression.SuppressAlerts
Orion.Cloud.Instances.Remanage
Orion.Cloud.Instances.Unmanage
Orion.NPM.Interfaces.Remanage
Orion.NPM.Interfaces.Unmanage
Orion.Nodes.Remanage
Orion.Nodes.Unmanage
Orion.Volumes.Remanage
Orion.Volumes.Unmanage
```

Note that alert suppression sits under the same right as unmanaging, which is a sensible
grouping and not an obvious one. Note also that the six entities naming `allowUnmanage` in
their own access control table are not the entities those ten verbs sit on.
`Orion.APM.Application` grants `invoke` for it. The other five —
`Orion.Frequencies`, `Orion.MaintenancePlan`, `Orion.MaintenancePlanAssignment`,
`Orion.ScheduleEntityAssignment` and `Orion.ScheduleTaskDefinition`, the scheduling records
behind a maintenance window — grant create, read, update and delete, and
`Orion.ScheduleEntityAssignment` grants `invoke` as well. So the right covers writing the
schedule as much as invoking the verbs, and the set of things it touches is wider than the
verb list alone suggests.

**`allowRealTimePolling`** gates on-demand polling, which is expensive and can be triggered
in a loop, so it is separated out. It appears on `Orion.Nodes`, `Orion.NPM.Interfaces` and
`Orion.Volumes` plus their three `Cortex.Orion.*` counterparts, and on 21 verbs. On
`Orion.Nodes` the entity grants `read` and `invoke` for that right, so an account holding it
can start and stop real-time polling without holding `manageNodes`.

### Verbs carry their own access control

An entity's table is not the whole story, because a verb can require a different right than
the entity does:

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

`Orion.Nodes` as an entity lists `manageNodes` for invoke, but `Unmanage` specifically wants
`allowUnmanage`. Always check the verb, not just the entity. `StartRealTimePolling` on the
same entity lists two acceptable rights, `allowRealTimePolling` and `admin`, so the grants
are a union rather than a single requirement.

### Rights are not the only filter

A right decides whether an operation is permitted. **Account limitations** decide which rows
you see, and they are invisible in the response. From the official documentation: "Orion
administrators can associate Orion accounts with limitations that restrict what nodes and
interfaces users can access. SWIS respects these limitations."

The practical consequence is that two accounts running the same query get different result
sets, with no error and no indication that filtering happened. "The query returns nothing" is
therefore a permissions hypothesis at least as often as it is a data hypothesis. See
[accounts-and-permissions.md](../automation/accounts-and-permissions.md).

## Where to go next

- [relationships.md](relationships.md) for how entities connect and how to navigate between
  them.
- [using-the-data.md](using-the-data.md) to query the JSON behind every count on this page.
- [joins-and-navigation.md](../swql/joins-and-navigation.md) for the SWQL mechanics of
  base-entity queries and navigation.
- [uris.md](../swis/uris.md) for the URI format and the system identifier.
- [metadata-introspection.md](../swis/metadata-introspection.md) to ask your own server any
  of these questions directly.

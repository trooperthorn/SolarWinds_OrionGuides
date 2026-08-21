# Joins, navigation and inheritance in SWQL

This is the highest leverage page in the SWQL section. Almost every SWQL query that matters
crosses more than one entity, and SWIS gives you two ways to do that: **navigation
properties**, written as a dotted path, and **explicit joins**, written with `ON`. Knowing
which one applies, and what each does to your row count, is most of the skill.

Everything here was resolved against `data/schema/2026.2/`, which holds 2992 navigation
edges between 2067 entities. Every `sql` block is re-checked on every build.

## Navigation properties are declared joins

The schema does not just record which properties an entity has. It records the
**relationships** between entities, and each relationship gives at least one side a named
navigation property. `Orion.Nodes` has 135 of them as the source of a relationship and 26
as the target: 161 pre-declared joins you do not have to write out.

Look at any entity and the relationships are right there:

```bash
python3 tools/schema_query.py show Orion.Nodes
```

```text
  sourceRelationships (135) - this entity is the source; property leads to the target
    Inventory                                  -> Orion.ADM.NodeInventory                      System.Hosting
    ChildNodeToNodeLinks                       -> Orion.APM.NodeToNodeLink                     System.Reference
    ParentNodeToNodeLinks                      -> Orion.APM.NodeToNodeLink                     System.Reference
    OutApplicationTcpConnections               -> Orion.APM.ApplicationTcpConnection           System.Reference
    InApplicationTcpConnections                -> Orion.APM.ApplicationTcpConnection           System.Reference
    Agent                                      -> Orion.AgentManagement.Agent                  System.Reference
    Anomalies                                  -> Orion.AIIM.Orion_Nodes_Anomalies             System.Hosting
    ...
```

**Both lists are navigable from this entity.** That is the single most common point of
confusion. "Source" and "target" describe which end of the relationship declaration the
entity sits at, not which direction you may travel. `Orion.Nodes.Interfaces` (source) and
`Orion.NPM.Interfaces.Node` (target) are both valid SWQL, and both are usable from the
entity they are listed on.

So this:

```sql
SELECT TOP 100
    n.Caption            AS NodeCaption,
    n.Interfaces.Caption AS InterfaceCaption,
    n.Interfaces.Status  AS InterfaceStatus
FROM Orion.Nodes n
ORDER BY n.Caption
```

is equivalent to this:

```sql
SELECT TOP 100
    n.Caption AS NodeCaption,
    i.Caption AS InterfaceCaption,
    i.Status  AS InterfaceStatus
FROM Orion.Nodes n
INNER JOIN Orion.NPM.Interfaces i ON i.NodeID = n.NodeID
ORDER BY n.Caption
```

The first form is shorter, cannot get the join key wrong, and survives a schema change that
alters the underlying keys. The second form is what you need as soon as you want a `LEFT
JOIN`, a compound predicate in the `ON` clause, or a join for which no relationship is
declared.

## Cardinality: the thing that decides your row count

A navigation is either **to-one** or **to-many**, and it matters enormously.

### A to-one navigation is an implicit inner join

`Orion.NPM.Interfaces.Node` leads to exactly one node. Walking it adds columns without
adding rows, and it behaves as an inner join: an interface whose node is missing produces no
row at all.

This is SolarWinds' own `Interface.Cleanup.ps1` sample, reformatted and given a short alias.
The sample itself selects `Interfaces.Node.Caption`, `Interfaces.Caption`, `Interfaces.URI`
and `Interfaces.Status` from `Orion.NPM.Interfaces AS Interfaces` with the same `WHERE`; the
`TOP 100` and the `ORDER BY` are added here, because an unbounded interface query on a real
installation is not something you want to run twice:

```sql
SELECT TOP 100
    i.Node.Caption AS NodeName,
    i.Caption      AS InterfaceName,
    i.Uri,
    i.Status
FROM Orion.NPM.Interfaces i
WHERE i.Status != 1
ORDER BY i.Node.Caption
```

You can chain to-one navigations. Each hop is still one row:

```sql
SELECT TOP 200
    c.Application.Node.Caption AS NodeCaption,
    c.Application.Name         AS ApplicationName,
    c.Name                     AS ComponentName,
    c.Status,
    c.StatusDescription
FROM Orion.APM.Component c
WHERE c.Status = 2
ORDER BY c.Application.Node.Caption
```

Because a to-one navigation is an inner join, a chain of them silently drops rows whose
chain is incomplete. If a component's application row were missing, that component would
vanish from the result rather than appearing with nulls. When you need the unmatched rows,
write a `LEFT JOIN` instead.

### A to-many navigation multiplies rows

`Orion.Nodes.Interfaces` leads to many interfaces. Selecting through it gives you one row
per node and interface pair, not one row per node. A node with 48 interfaces contributes 48
rows, and every node column repeats on each of them.

Count the difference:

```sql
SELECT COUNT(n.NodeID) AS NodeRows
FROM Orion.Nodes n
```

```sql
SELECT COUNT(i.InterfaceID) AS NodeInterfacePairs
FROM Orion.Nodes n
INNER JOIN Orion.NPM.Interfaces i ON i.NodeID = n.NodeID
```

The second number is typically an order of magnitude larger. Three consequences follow:

- **Aggregates over the parent become wrong.** `SUM(n.TotalMemory)` across a node-to-interface
  join counts each node's memory once per interface. Aggregate over the entity you are
  actually counting, or aggregate in a subquery.
- **`TOP n` no longer means n objects.** `TOP 100` over a node-to-interface join returns 100
  pairs, which might be two nodes.
- **You usually want `DISTINCT` or a subquery.** For "which nodes have a down interface",
  either works, and the subquery is cheaper because it never materialises the multiplied
  rows:

```sql
SELECT DISTINCT n.Caption
FROM Orion.Nodes n
INNER JOIN Orion.NPM.Interfaces i ON i.NodeID = n.NodeID
WHERE i.Status = 2
ORDER BY n.Caption
```

```sql
SELECT TOP 50 n.Caption, n.IPAddress
FROM Orion.Nodes n
WHERE n.NodeID IN (
    SELECT i.NodeID
    FROM Orion.NPM.Interfaces i
    WHERE i.Status = 2
)
ORDER BY n.Caption
```

### Telling them apart

The schema records the relationship kind but not, in the extracted form, the cardinality
numbers. Two reliable heuristics plus one authoritative check:

- **The name.** A plural navigation property (`Interfaces`, `Volumes`, `Applications`,
  `Components`, `AssignedNodes`) is to-many. A singular one (`Node`, `Engine`, `Application`,
  `Container`, `StatusInfo`) is to-one.
- **The direction of the hosting relationship.** `Orion.NodeHostsInterfaces` is declared with
  `Orion.Nodes` as source and `Orion.NPM.Interfaces` as target. Source to target on a
  `System.Hosting` relationship is the one-to-many direction; target back to source is the
  many-to-one direction.
- **Ask the server.** `Metadata.Relationship` publishes the cardinalities directly:

```sql
SELECT TOP 50
    r.Name,
    r.SourceType,
    r.TargetType,
    r.SourcePropertyName,
    r.TargetPropertyName,
    r.SourceCardinalityMin,
    r.SourceCardinalityMax,
    r.TargetCardinalityMin,
    r.TargetCardinalityMax
FROM Metadata.Relationship r
WHERE r.SourceType = 'Orion.Nodes'
ORDER BY r.Name
```

## Finding a navigation path

You rarely need to read a relationship list by hand. The repository's own tool searches the
graph in both directions and prints a runnable query for each path it finds:

```bash
python3 tools/schema_query.py path Orion.APM.Component Orion.Nodes
```

```text
5 path(s) from Orion.APM.Component to Orion.Nodes, shortest first

  Orion.APM.Component.AlertObject.Node
    Orion.APM.Component --AlertObject--> Orion.AlertObjects
    Orion.AlertObjects --Node--> Orion.Nodes

    SELECT TOP 10 a.DisplayName, a.AlertObject.Node.DisplayName
    FROM Orion.APM.Component a

  Orion.APM.Component.Application.Node
    Orion.APM.Component --Application--> Orion.APM.Application
    Orion.APM.Application --Node--> Orion.Nodes

    SELECT TOP 10 a.DisplayName, a.Application.Node.DisplayName
    FROM Orion.APM.Component a
```

Multiple paths are normal and they are not interchangeable. Here the first goes through the
alerting model and only returns components that have triggered an alert; the second is the
structural containment path and returns every component. Read the hops before picking one.

The remaining three paths in that same output are different questions again: two go through
`Orion.APM.ApplicationTcpConnection` to a `ClientNode` or a `ServerNode`, and one is
`Application.RelyNode`, a `System.Reliance` edge rather than the containment one. The tool
gives you the options; the semantics are yours to choose.

When there is no path, the tool says so and tells you what to do instead:

```bash
python3 tools/schema_query.py path Orion.Nodes Orion.Container
```

```text
no navigation path from Orion.Nodes to Orion.Container within 3 hops
join explicitly on key columns instead, e.g.
  SELECT ... FROM Orion.Nodes a JOIN Orion.Container b ON a.<Key> = b.<Key>
```

That is a real and important gap: group membership is polymorphic, so it deliberately has no
typed relationship back to `Orion.Nodes`. See
[example 7](#example-7-group-membership) below.

## Querying a base entity

SWIS entity types form an inheritance tree rooted at `System.Entity`, and
[SolarWinds states the consequence directly](https://solarwinds.github.io/OrionSDK/docs/about-swis/):
"If you write a query against a base entity type, data from all entity types that have that
base entity type as an ancestor will be returned."

This is a join you do not have to write. Instead of unioning four entity types to answer
"what is down", you select from the base type once.

The base entities worth knowing, with the number of types that inherit from each in 2026.2:

| Base entity | Descendants | What it means |
|:---|---:|:---|
| `System.Entity` | 2043 | The root. Declares `DisplayName`, `Description`, `InstanceType`, `Uri`, `InstanceSiteId` |
| `System.ExtensionEntity` | 305 | Extra properties about another entity, linked by a hosting relationship |
| `System.StatisticsEntity` | 236 | Statistical data. Declares `ObservationTimestamp`, `ObservationFrequency`, `Weight` |
| `System.DashboardEntity` | 180 | Declares `Status`, `DetailsUrl`, `ModernIcon`, `EntityLink` |
| `System.ManagedEntity` | 174 | "Something that has an externally-determined up/down status". Declares `UnManaged`, `UnManageFrom`, `UnManageUntil`, `StatusDescription`, `AncestorDisplayNames` |
| `Orion.Thresholds` | 133 | Threshold configuration |
| `System.Indication` | 112 | Events published by SWIS |
| `System.CustomPropertiesEntity` | 25 | Dynamic, installation-defined properties |

Verify any of these yourself:

```bash
python3 tools/schema_query.py children System.ManagedEntity
python3 tools/schema_query.py children Orion.APM.Application
```

```text
6 entity/entities inherit from Orion.APM.Application
  Orion.APM.ActiveDirectory.Application
  Orion.APM.Exchange.Application
  Orion.APM.GenericApplication
  Orion.APM.IIS.Application
  Orion.APM.SqlServerApplication
  Orion.APM.Wstm.ScheduledTasksStatus
```

Note that `Orion.Nodes`, `Orion.NPM.Interfaces`, `Orion.Volumes`, `Orion.APM.Application`,
`Orion.APM.Component` and `Orion.Container` are all among the 174 descendants of
`System.ManagedEntity`. So this one query spans all of them:

```sql
SELECT TOP 20
    m.DisplayName,
    m.InstanceType,
    m.Status
FROM System.ManagedEntity m
ORDER BY m.DisplayName
```

`Status` is inherited from `System.DashboardEntity`, where the property's own schema summary
says it plainly: "An int value denoting the up/down/warning/etc. status of this entity. The
interpretation of this int will be application-dependent, but for Orion.\* entities, you can
query Orion.StatusInfo to see what the different numbers mean."

"Everything currently in a maintenance window, of any type" is likewise a single query,
because `UnManaged` is declared once on `System.ManagedEntity`:

```sql
SELECT TOP 100
    m.DisplayName,
    m.InstanceType,
    m.UnManageFrom,
    m.UnManageUntil
FROM System.ManagedEntity m
WHERE m.UnManaged = TRUE
ORDER BY m.DisplayName
```

Note there is **no** `Orion.NetObjects` entity in the 2026.2 schema. If you have seen that
name, it is not the base entity you want; `System.ManagedEntity` is.

### Filtering a base-entity query by type

`InstanceType` is filled in by SWIS with the concrete type of each row, so it is both the
column that tells you what you got and the predicate that narrows it.

```sql
SELECT TOP 50
    a.Name,
    a.InstanceType,
    a.Node.Caption AS NodeCaption
FROM Orion.APM.Application a
ORDER BY a.Name
```

That returns generic applications, Exchange applications, IIS applications, SQL Server
applications and the rest, with `InstanceType` distinguishing them, and `a.Node.Caption`
working on all of them because the `Node` navigation is declared on the base type.

The cost of a base-entity query is that you only get the base type's properties. `Status` and
`DisplayName` are there; `Orion.Nodes.IPAddress` is not, because most managed entities do not
have one. When you need type-specific columns, select from the concrete entity.

## Ten worked joins

### Example 1: nodes to interfaces

Navigation form, one row per node and interface pair:

```sql
SELECT TOP 100
    n.Caption            AS NodeCaption,
    n.Interfaces.Caption AS InterfaceCaption,
    n.Interfaces.Status  AS InterfaceStatus
FROM Orion.Nodes n
ORDER BY n.Caption
```

Reverse navigation, which is usually the better shape because interfaces are what you are
listing and the node is context:

```sql
SELECT TOP 100
    i.Node.Caption AS NodeName,
    i.Caption      AS InterfaceName,
    i.InPercentUtil,
    i.OutPercentUtil,
    i.Speed
FROM Orion.NPM.Interfaces i
WHERE i.Status = 2
ORDER BY i.Node.Caption, i.Caption
```

`Orion.Nodes.Interfaces` is declared by the relationship `Orion.NodeHostsInterfaces`, and
`Orion.NPM.Interfaces.Node` is the same relationship read from the other end.

### Example 2: nodes to volumes

```sql
SELECT TOP 100
    v.Node.Caption AS NodeCaption,
    v.Caption      AS VolumeCaption,
    v.VolumeType,
    v.VolumeSize,
    v.VolumePercentUsed
FROM Orion.Volumes v
WHERE v.VolumePercentUsed > 85
ORDER BY v.VolumePercentUsed DESC
```

Starting from `Orion.Volumes` rather than `Orion.Nodes` is deliberate. The filter is on the
volume, so filtering the many side first is both clearer and cheaper than filtering after a
to-many expansion.

Note that `Orion.Volumes` also has a `RelyNode` navigation, which is a `System.Reliance`
relationship rather than the `System.Hosting` one. `Node` is the containment relationship and
is the one you want here.

### Example 3: nodes to applications and components

Two hops of to-one navigation from the component, so one row per component:

```sql
SELECT TOP 200
    c.Application.Node.Caption AS NodeCaption,
    c.Application.Name         AS ApplicationName,
    c.Name                     AS ComponentName,
    c.Status,
    c.StatusDescription
FROM Orion.APM.Component c
WHERE c.Status = 2
ORDER BY c.Application.Node.Caption
```

The same thing as explicit joins, which is what you need if you want a `LEFT JOIN` to keep
applications that have no failing components:

```sql
SELECT TOP 200
    n.Caption AS NodeCaption,
    a.Name    AS ApplicationName,
    c.Name    AS ComponentName,
    c.Status
FROM Orion.APM.Application a
INNER JOIN Orion.Nodes n         ON n.NodeID = a.NodeID
LEFT  JOIN Orion.APM.Component c ON c.ApplicationID = a.ApplicationID AND c.Status = 2
ORDER BY n.Caption, a.Name
```

Putting `c.Status = 2` in the `ON` clause rather than in `WHERE` is what keeps the healthy
applications in the result with a null component. Moving it to `WHERE` would silently turn
the `LEFT JOIN` back into an inner join.

`Orion.APM.Component.ComponentID` is a `System.Int64` while `ApplicationID` is a
`System.Int32`. Join on the matching pair.

### Example 4: nodes to custom properties

Custom properties are the one place where the published schema deliberately cannot tell you
the column names. `Orion.NodesCustomProperties` declares exactly one property, `NodeID`,
because the rest are created per installation. The base type says so:
`System.CustomPropertiesEntity` is documented as the type you inherit from when you
"support user-defined properties ... set `dynamic="true"` on it, and have your data provider
fill in the user-defined properties at runtime."

So the first query is a discovery query, not a data query. Ask the server what exists:

```sql
SELECT cp.Table, cp.Field, cp.DataType, cp.TargetEntity, cp.Mandatory
FROM Orion.CustomProperty cp
ORDER BY cp.Table, cp.Field
```

Or ask the metadata layer, which gives you the exact SWQL property names and types:

```sql
SELECT p.Name, p.Type
FROM Metadata.Property p
WHERE p.Entity.FullName = 'Orion.NodesCustomProperties'
ORDER BY p.Name
```

Then use the names you got back. The join itself is a to-one navigation
(`Orion.Nodes.CustomProperties`) or an ordinary join on `NodeID`:

```sql
SELECT TOP 100
    n.Caption,
    ncp.Uri AS CustomPropertiesUri
FROM Orion.Nodes n
INNER JOIN Orion.NodesCustomProperties ncp ON ncp.NodeID = n.NodeID
ORDER BY n.Caption
```

With real custom property names substituted, the query takes this shape. It is shown as
plain text rather than as a checked SWQL block precisely because `City` and `Owner` are
installation-specific names that cannot be validated against the published schema:

```text
SELECT TOP 100
    n.Caption,
    n.CustomProperties.City,
    n.CustomProperties.Owner
FROM Orion.Nodes n
ORDER BY n.Caption
```

SolarWinds' own `SetVolumeCustomProperty.ps1` sample uses the explicit-join spelling of the
same idea against `Orion.VolumesCustomProperties` with a `Bitlocker_Enabled` property, which
exists in their environment and probably not in yours.

Every entity that supports custom properties follows this pattern. There are 25 such
entities in 2026.2, including `Orion.NodesCustomProperties`,
`Orion.NPM.InterfacesCustomProperties`, `Orion.VolumesCustomProperties`,
`Orion.APM.ApplicationCustomProperties` and `Orion.GroupCustomProperties`.

### Example 5: alerts to their triggering object

The alerting model has three entities and the join between them is the one people get wrong
most often.

- `Orion.AlertActive` is one row per currently active alert. It carries the trigger time and
  the acknowledgement state, and nothing about what triggered.
- `Orion.AlertObjects` is one row per (alert configuration, object) pair that has ever
  triggered. It carries `EntityType`, `EntityUri`, `EntityCaption` and the `RelatedNode...`
  properties. It does not go away when the alert resets.
- `Orion.AlertConfigurations` is the alert definition: name, severity, enabled state.

SolarWinds' [alerts documentation](https://solarwinds.github.io/OrionSDK/docs/alerts/) says
the recommended access pattern is to query `Orion.AlertActive` and join to
`Orion.AlertObjects`:

```sql
SELECT TOP 100
    aa.AlertActiveID,
    aa.TriggeredDateTime,
    aa.TriggeredMessage,
    ao.AlertConfigurations.Name     AS AlertName,
    ao.AlertConfigurations.Severity AS AlertSeverity,
    ao.EntityType,
    ao.EntityCaption,
    ao.RelatedNodeCaption
FROM Orion.AlertActive aa
INNER JOIN Orion.AlertObjects ao ON ao.AlertObjectID = aa.AlertObjectID
ORDER BY aa.TriggeredDateTime DESC
```

The same thing purely by navigation, since `Orion.AlertActive.AlertObjects` is declared:

```sql
SELECT TOP 100
    aa.TriggeredDateTime,
    aa.AlertObjects.EntityCaption,
    aa.AlertObjects.AlertConfigurations.Name AS AlertName
FROM Orion.AlertActive aa
ORDER BY aa.TriggeredDateTime DESC
```

When the triggering object is a node, or hangs off one, `Orion.AlertObjects.Node` takes you
straight there:

```sql
SELECT TOP 100
    ao.EntityCaption,
    ao.EntityType,
    ao.Node.Caption   AS NodeCaption,
    ao.Node.IPAddress AS NodeIPAddress
FROM Orion.AlertObjects ao
WHERE ao.IsActiveAlert = TRUE
ORDER BY ao.EntityCaption
```

And when it could be any kind of object, `Orion.AlertObjects.ManagedEntity` navigates to
`System.ManagedEntity`, which is the polymorphic answer:

```sql
SELECT TOP 100
    aa.TriggeredDateTime,
    ao.ManagedEntity.DisplayName AS TriggeringObject,
    ao.ManagedEntity.Status      AS TriggeringObjectStatus
FROM Orion.AlertActive aa
INNER JOIN Orion.AlertObjects ao ON ao.AlertObjectID = aa.AlertObjectID
ORDER BY aa.TriggeredDateTime DESC
```

Two cautions from SolarWinds' own documentation. For global alerts that examine the whole
environment, `EntityUri`, `EntityDetailsUrl` and the `RelatedNode...` properties are blank
and `EntityCaption` reads like "38 interfaces"; the contributing objects are in
`Orion.AlertActiveObjects` instead. And `Orion.AlertObjects` rows persist after the alert
resets, so querying it alone tells you what has ever alerted, not what is alerting now.
Join through `Orion.AlertActive`, or filter on `IsActiveAlert`.

### Example 6: nodes to their polling engine

`Orion.Nodes.Engine` is a target relationship (`Orion.EngineHostsNodes`) and is navigable
from the node:

```sql
SELECT TOP 100
    n.Caption,
    n.Engine.ServerName       AS PollingEngine,
    n.Engine.PollingCompletion
FROM Orion.Nodes n
ORDER BY n.Caption
```

For load balancing work, the aggregate is what you want, and that needs the explicit join so
the engine columns can be grouped:

```sql
SELECT
    e.ServerName,
    e.ServerType,
    e.PollingCompletion,
    COUNT(n.NodeID) AS NodeCount
FROM Orion.Nodes n
INNER JOIN Orion.Engines e ON e.EngineID = n.EngineID
GROUP BY e.ServerName, e.ServerType, e.PollingCompletion
ORDER BY COUNT(n.NodeID) DESC
```

`Orion.Engines` also carries its own running counts in `Elements`, `Nodes`, `Interfaces`,
`Volumes` and `Pollers`, plus `PollingCompletion`. Those are maintained by the platform, so
they are a cross-check on the join rather than a substitute for it. See
[../platform/architecture.md](../platform/architecture.md) for what the engine health
columns mean.

The reverse navigation exists too: `Orion.Engines.AssignedNodes` leads back to
`Orion.Nodes`, and it is to-many.

### Example 7: group membership

Groups are containers, and container membership is deliberately polymorphic: a group can hold
nodes, interfaces, volumes, applications and other groups. That is why
`tools/schema_query.py path Orion.Nodes Orion.Container` finds nothing. There is no typed
relationship because a typed relationship would only work for one member type.

`Orion.ContainerMembers` identifies each member with `MemberEntityType` (a string naming the
entity type) plus `MemberPrimaryID` (its key). Listing membership needs no join at all,
because the container navigation is declared:

```sql
SELECT TOP 200
    cm.Container.Name AS GroupName,
    cm.Name           AS MemberName,
    cm.MemberEntityType,
    cm.MemberPrimaryID,
    cm.Status
FROM Orion.ContainerMembers cm
ORDER BY cm.Container.Name, cm.Name
```

Getting back to the typed entity is where the manual join comes in. You must filter on
`MemberEntityType` as well as joining on the key, or you will match a volume whose
`VolumeID` happens to equal some node's `NodeID`:

```sql
SELECT TOP 200
    cm.Container.Name AS GroupName,
    n.Caption,
    n.IPAddress,
    n.Status
FROM Orion.ContainerMembers cm
INNER JOIN Orion.Nodes n ON n.NodeID = cm.MemberPrimaryID
WHERE cm.MemberEntityType = 'Orion.Nodes'
ORDER BY cm.Container.Name, n.Caption
```

`MemberPrimaryID` is a `System.Int64` and `NodeID` is a `System.Int32`, which the comparison
handles, but it is worth knowing when you carry the value into client code.

`Orion.Groups` inherits from `Orion.Container` and declares almost nothing of its own, so
`Name`, `Owner`, `RollupType`, `PollingEnabled` and `IsDeleted` all come from
`Orion.Container` by inheritance, and `Status` from `System.DashboardEntity` two levels
further up. Selecting from `Orion.Groups` and from `Orion.Container` therefore give you the
same columns; the difference is which rows you get.

`Orion.ContainerMembers.MemberUri` is a `System.Uri` pointing at the member, which is the
type-agnostic handle to use when you are going to act on the member through CRUD or a verb
rather than read more of its columns. See [../swis/uris.md](../swis/uris.md).

### Example 8: status integers to status names

`Status` is an integer on every managed entity. Some entities have a declared navigation to
`Orion.StatusInfo` and some do not, and knowing which saves you a guess.

`Orion.NPM.Interfaces`, `Orion.Volumes`, `Orion.VIM.Hosts`, `Orion.VIM.VirtualMachines`,
`Orion.VIM.Clusters`, `Orion.VIM.DataCenters`, `Orion.VIM.Datastores`,
`Orion.DPA.DatabaseInstance`, `Orion.Cman.Container` and `Orion.APIPoller.ApiPoller` all
declare a `StatusInfo` navigation:

```sql
SELECT TOP 100
    i.Node.Caption          AS NodeCaption,
    i.Caption               AS InterfaceCaption,
    i.StatusInfo.StatusName AS StatusName
FROM Orion.NPM.Interfaces i
ORDER BY i.Node.Caption
```

`Orion.Nodes` does **not**. There is no `Orion.Nodes.StatusInfo`, and
`tools/schema_query.py path Orion.Nodes Orion.StatusInfo` finds only routes that detour
through some other object's status: `Volumes.StatusInfo`, `Host.StatusInfo` and
`RelyHost.StatusInfo` through a virtualisation host, `ApiPollers.StatusInfo`, and
`Containers.StatusInfo` through a container-manager container. Every one of them returns the
status of the thing at the far end, not of the node. For nodes, write the explicit join:

```sql
SELECT
    s.StatusName,
    s.Ranking,
    COUNT(n.NodeID) AS NodeCount
FROM Orion.Nodes n
INNER JOIN Orion.StatusInfo s ON s.StatusId = n.Status
GROUP BY s.StatusName, s.Ranking
ORDER BY s.Ranking
```

Ordering by `Ranking` rather than by `StatusId` gives worst-first ordering that matches the
web console: Down ranks 110, Lower Layer Down 130, Unreachable 150, Critical 210, Warning
220, Up 500. The full table is in
[../reference/status-codes.md](../reference/status-codes.md).

### Example 9: nodes to their NCM configuration record

Cross-module joins work exactly like any other, and `Orion.Nodes.NodeProperties` is declared
straight to `NCM.NodeProperties`:

```sql
SELECT TOP 100
    n.Caption,
    n.NodeProperties.NodeGroup,
    n.NodeProperties.LastInventory
FROM Orion.Nodes n
ORDER BY n.Caption
```

The trap here is the key. `NCM.NodeProperties.NodeID` is a `System.Guid`, NCM's own
identifier; `NCM.NodeProperties.CoreNodeID` is the `System.Int32` that matches
`Orion.Nodes.NodeID`. An explicit join on the wrong one returns zero rows and no error:

```sql
SELECT TOP 100
    n.Caption AS OrionNode,
    np.NodeID AS NcmNodeId
FROM Orion.Nodes n
FULL OUTER JOIN NCM.NodeProperties np ON np.CoreNodeID = n.NodeID
WHERE n.NodeID IS NULL OR np.CoreNodeID IS NULL
```

That `FULL OUTER JOIN` is the reconciliation query: nodes the platform knows and NCM does
not, and NCM records whose platform node has gone.

### Example 10: nodes to their agent

```sql
SELECT TOP 100
    n.Caption,
    n.Agent.Name                    AS AgentName,
    n.Agent.AgentVersion,
    n.Agent.ConnectionStatusMessage
FROM Orion.Nodes n
ORDER BY n.Caption
```

`Orion.Nodes.Agent` is a `System.Reference` relationship to
`Orion.AgentManagement.Agent`. Because a to-one navigation behaves as an inner join, nodes
with no agent simply produce no `Agent` columns rather than an error, and if you need to
list the agentless nodes explicitly, use a `LEFT JOIN` on `Orion.AgentManagement.Agent`
matching `NodeId` and test for null.

## Choosing between navigation and an explicit join

| Situation | Use |
|:---|:---|
| A relationship is declared and you want an inner join | Navigation. Shorter, and the key cannot be wrong |
| You need unmatched rows kept | Explicit `LEFT JOIN` |
| You need a compound or filtered join predicate | Explicit join, predicate in `ON` |
| The relationship is polymorphic (group membership, alert objects by `EntityType`) | Explicit join plus a type filter |
| Keys differ in type or name across a module boundary | Explicit join, after checking which key actually matches |
| You are aggregating over the joined entity's columns | Explicit join, so the columns can appear in `GROUP BY` |
| The same entity appears twice with different roles | Explicit joins with distinct aliases |
| You want the query to survive an underlying key change | Navigation |

Navigation and explicit joins mix freely in one query. The common shape is to navigate for
context columns and join explicitly for the one relationship that needs `LEFT` semantics or
a predicate.

## Common mistakes

**Assuming a navigation exists because it feels like it should.** `Orion.Nodes.StatusInfo`
does not exist even though `Orion.NPM.Interfaces.StatusInfo` does. Check with
`tools/schema_query.py path` or `tools/schema_query.py show` before writing it.

**Getting the property name subtly wrong.** `Orion.APM.Component.Node` does not exist; the
path is `Orion.APM.Component.Application.Node`. These are exactly the names that look right
and fail on a live server, which is what `tools/validate_swql.py` exists to catch.

**Forgetting that a to-many navigation multiplies rows**, then aggregating the parent's
columns over the multiplied set.

**Filtering the right side of a `LEFT JOIN` in `WHERE`**, which turns it back into an inner
join.

**Joining polymorphic membership without a type filter.** `Orion.ContainerMembers` requires
`MemberEntityType` in the predicate.

**Joining NCM to the platform on `NodeID`.** Use `CoreNodeID`.

**Reading `Orion.AlertObjects` as though it were the active alert list.** Those rows persist
after the alert resets.

## Verifying every name on this page

```bash
python3 tools/schema_query.py show Orion.Nodes
python3 tools/schema_query.py path Orion.APM.Component Orion.Nodes
python3 tools/schema_query.py path Orion.Nodes Orion.StatusInfo
python3 tools/schema_query.py children System.ManagedEntity
python3 tools/schema_query.py props Orion.ContainerMembers
python3 tools/validate_swql.py docs/swql/joins-and-navigation.md
```

Against your own server, `Metadata.Relationship` is the authority, and it publishes the
cardinalities the extracted data does not:

```sql
SELECT
    r.Name,
    r.SourceType,
    r.SourcePropertyName,
    r.TargetType,
    r.TargetPropertyName,
    r.SourceCardinalityMax,
    r.TargetCardinalityMax
FROM Metadata.Relationship r
WHERE r.TargetType = 'Orion.Nodes'
ORDER BY r.Name
```

## Next

- [language-reference.md](language-reference.md) for the clause-by-clause reference.
- [functions.md](functions.md) for the function library.
- [date-and-time.md](date-and-time.md) for time-bounded queries, which is where joins to
  statistics entities usually go wrong.
- [../swis/uris.md](../swis/uris.md) for turning a joined row into something you can act on.
- [../../scripts/swql/](../../scripts/swql/) for verified samples by subject area.

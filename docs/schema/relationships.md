# Relationships and navigation

The schema does not only record what properties an entity has. It records how entities
connect, and every connection it records becomes a **navigation property**: a named,
pre-declared join you write as a dotted path instead of an `ON` clause. In 2026.2 there are
**2992 navigation edges** across 1501 relationship definitions, which is 2992 joins you do
not have to work out for yourself.

This page is about the model: what the relationship kinds mean, why both ends are navigable,
how to find a path, and how to drive automation from
[relationships.json](../../data/schema/2026.2/relationships.json). For what a navigation
does to your row count and how to choose between a navigation and an explicit join, see
[joins-and-navigation.md](../swql/joins-and-navigation.md).

## The three relationship kinds

Every relationship in 2026.2 has one of exactly three base types. Compute the set yourself
from the extract:

```bash
jq -r 'group_by(.kind)[] | "\(.[0].kind)\t\(length)"' data/schema/2026.2/relationships.json
```

```text
System.Hosting	1305
System.Reference	1581
System.Reliance	106
```

| Kind | Edges | What it means |
| --- | ---: | --- |
| `System.Reference` | 1581 | A plain association. One entity points at another with no ownership implied |
| `System.Hosting` | 1305 | Containment. The target belongs to the source and does not exist independently of it |
| `System.Reliance` | 106 | Dependency. One entity's state depends on another's, across a boundary the two do not share |

The distinction is not decoration, it tells you what to expect from the data.

**`System.Hosting` is the parent/child relationship.** `Orion.Nodes` hosts
`Orion.NPM.Interfaces`, `Orion.Volumes`, `Orion.APM.Application` and
`Orion.NodesCustomProperties`. The hosted entity carries the host's key as a foreign key,
deleting the host deletes the hosted rows, and `System.ManagedEntity.AncestorDisplayNames`
walks exactly this chain upward. If you are looking for "the things that belong to this
node", you are looking for hosting relationships. `System.ExtensionEntity`'s own summary
names this explicitly: extension entity types "are for providing additional properties about
another entity and these types should be linked by a `System.Hosting` relationship to some
other entity."

**`System.Reference` is everything else.** `Orion.Nodes` references `Orion.Engines` (its
polling engine), `Orion.Vendors`, `Orion.Events` and `Orion.AlertObjects`. Neither side owns
the other, and the referenced entity has an independent lifetime.

**`System.Reliance` is the rarest and the most interesting.** It is used where one entity's
health depends on another's but the two are separately managed, typically because they come
from different modules or different discovery paths. `Orion.APM.Application` has `RelyNode`
to `Orion.Nodes`; `Orion.DPA.DatabaseInstance` has `RelyNode`; `Orion.Nodes` has
`CloudInstance` to `Orion.Cloud.Instances`, matching a monitored node to the cloud instance
it actually runs on. The naming convention is a giveaway: most reliance navigations start
with `Rely`.

Reliance edges frequently coexist with a hosting or reference edge that answers a slightly
different question, which is the trap. `Orion.APM.Application` reaches `Orion.Nodes` two
ways: `Node`, the `System.Hosting` edge for the node the application is configured on, and
`RelyNode`, the `System.Reliance` edge for the node it depends on. They are separate
relationships and are not guaranteed to resolve to the same row, so picking the wrong one
gives you a plausible answer to a question you did not ask.

```sql
SELECT TOP 20
    a.Name                AS ApplicationName,
    a.RelyNode.Caption    AS DependsOnNode
FROM Orion.APM.Application a
ORDER BY a.Name
```

## Both relationship tables are navigable

This is the single most common misunderstanding about the SWIS schema, so it is worth being
blunt about.

An entity page has two relationship tables, **Source Relationships** and **Target
Relationships**. Those labels describe which end of the relationship *declaration* the entity
sits at. They do **not** describe which direction you are allowed to travel. Every row in
both tables is a navigation property usable **from the entity the table is on**.

The worked pair is nodes and interfaces. One relationship definition,
`Orion.NodeHostsInterfaces`, of kind `System.Hosting`, produces two edges:

```bash
jq -c '.[] | select(.relationship=="Orion.NodeHostsInterfaces")' data/schema/2026.2/relationships.json
```

```text
{"from":"Orion.NPM.Interfaces","navigationProperty":"Node","to":"Orion.Nodes","direction":"target","relationship":"Orion.NodeHostsInterfaces","kind":"System.Hosting"}
{"from":"Orion.Nodes","navigationProperty":"Interfaces","to":"Orion.NPM.Interfaces","direction":"source","relationship":"Orion.NodeHostsInterfaces","kind":"System.Hosting"}
```

`Orion.Nodes` is the source, so `Interfaces` appears in its Source Relationships table.
`Orion.NPM.Interfaces` is the target, so `Node` appears in its Target Relationships table.
Both are valid SWQL, and each is usable only from the entity it is listed on:

```sql
SELECT TOP 20
    n.Caption            AS NodeCaption,
    n.Interfaces.Caption AS InterfaceCaption
FROM Orion.Nodes n
ORDER BY n.Caption
```

```sql
SELECT TOP 20
    i.Caption      AS InterfaceCaption,
    i.Node.Caption AS NodeCaption
FROM Orion.NPM.Interfaces i
ORDER BY i.Caption
```

The second one is the important demonstration. `Node` is in the *Target* Relationships table
of `Orion.NPM.Interfaces`, and it still works, and it is a single hop. Anyone who reads
"target" as "you may not go this way" ends up writing the explicit join instead:

```sql
SELECT TOP 20
    i.Caption      AS InterfaceCaption,
    n.Caption      AS NodeCaption
FROM Orion.NPM.Interfaces i
INNER JOIN Orion.Nodes n ON n.NodeID = i.NodeID
ORDER BY i.Caption
```

which produces the same rows with more surface area for error. Both work; the navigation is
shorter and cannot get the join key wrong.

Of the 2992 edges, 1496 are marked `direction: "source"` and 1496 `direction: "target"`, and
the tools in this repository walk both. That is why
`python3 tools/schema_query.py path Orion.NPM.Interfaces Orion.Nodes` returns a one-hop
answer instead of a three-hop detour through some other entity.

### Inherited navigations count too

Navigation properties are inherited exactly like ordinary properties. `System.ManagedEntity`
declares `AlertObject` to `Orion.AlertObjects`, so every one of its 174 descendants can
navigate to its alert object without declaring anything. `System.Entity` declares
`OrionSite` to `Orion.Sites`, which every entity in the tree inherits. Neither appears on the
`Orion.Nodes` page.

`schema_query.py path` and `validate_swql.py` both resolve the inheritance chain before
looking for a navigation, which is why a query using an inherited navigation validates.

## Relationship coverage across the schema

Navigation is not evenly distributed, and knowing the shape saves time.

| Measure | Value |
| --- | ---: |
| Navigation edges | 2992 |
| Distinct relationship definitions | 1501 |
| Definitions with both ends recorded | 1491 |
| Definitions with only one end recorded | 10 |
| Entities that declare at least one navigation | 1167 |
| Entities that declare none | 900 |
| Self-referential edges (source and target are the same entity) | 16 |
| Definitions behind those self-referential edges | 8 |

Roughly 44 percent of entities have no navigation properties at all. Those are the lookup
tables, statistics rows and settings entities that are joined to by key rather than
navigated from.

At the other end, navigation is concentrated in a handful of hub entities:

```bash
jq -r 'group_by(.from)[] | "\(length)\t\(.[0].from)"' data/schema/2026.2/relationships.json | sort -rn | head -8
```

```text
161	Orion.Nodes
58	Orion.NPM.Interfaces
40	NCM.NodeProperties
39	Orion.Cloud.Accounts
34	Orion.VIM.VirtualMachines
31	Orion.SRM.StorageArrays
31	Orion.SRM.LUNs
30	Orion.VIM.Hosts
```

`Orion.Nodes` alone accounts for 161 of the 2992 edges, 135 as source and 26 as target. That
is the practical reason a node is the natural anchor for almost any query: nearly everything
in the platform is one hop from it.

## The navigations from Orion.Nodes worth memorising

All 161 are in `python3 tools/schema_query.py show Orion.Nodes`. These are the ones that come
up constantly, with the kind and the direction they are declared in.

| Navigation | Target | Kind | Direction | Answers |
| --- | --- | --- | --- | --- |
| `Interfaces` | `Orion.NPM.Interfaces` | Hosting | source | The node's monitored interfaces |
| `Volumes` | `Orion.Volumes` | Hosting | source | Disks and filesystems |
| `Applications` | `Orion.APM.Application` | Hosting | source | SAM applications on this node |
| `CustomProperties` | `Orion.NodesCustomProperties` | Hosting | source | The installation's custom property values |
| `Engine` | `Orion.Engines` | Reference | target | Which polling engine owns this node |
| `VendorInfo` | `Orion.Vendors` | Reference | target | Vendor name and icon |
| `Agent` | `Orion.AgentManagement.Agent` | Reference | source | The SolarWinds agent, if agent-managed |
| `Events` | `Orion.Events` | Reference | source | Event history for this node |
| `AlertObjects` | `Orion.AlertObjects` | Reference | source | Alert bindings |
| `ActiveAlerts` | `Orion.ActiveAlerts` | Reference | source | Alerts currently firing |
| `NodeProperties` | `NCM.NodeProperties` | Hosting | source | The NCM configuration record |
| `NCMLicenseStatus` | `Cirrus.NCMNodeLicenseStatus` | Hosting | source | Whether NCM is licensed for this node |
| `Stats` | `Orion.NodesStats` | Hosting | source | Current rollup statistics |
| `CPULoadHistory` | `Orion.CPULoad` | Hosting | source | Historical CPU samples |
| `ResponseTimeHistory` | `Orion.ResponseTime` | Hosting | source | Historical latency and loss samples |
| `NodeDowntimeHistory` | `Orion.NetObjectDowntime` | Hosting | source | Availability history |
| `HardwareHealthInfos` | `Orion.HardwareHealth.HardwareInfo` | Hosting | source | Hardware sensors |
| `CustomPollerAssignmentOnNode` | `Orion.NPM.CustomPollerAssignmentOnNode` | Hosting | source | Assigned custom pollers |
| `Ports` | `Orion.UDT.Port` | Hosting | source | UDT switch ports |
| `IpSlaOperations` | `Orion.IpSla.Operations` | Hosting | source | VNQM IP SLA operations |
| `OrionServer` | `Orion.OrionServers` | Reference | source | The Orion server record, when the node is one |
| `PollingErrors` | `Orion.PollingErrors` | Reference | source | Why polling is failing |
| `WorldMapPoint` | `Orion.WorldMap.Point` | Reference | source | Geographic position |
| `CloudInstance` | `Orion.Cloud.Instances` | Reliance | source | The cloud instance this node runs on |
| `VirtualMachine` | `Orion.VIM.VirtualMachines` | Reference | source | The VM this node is |
| `Host` | `Orion.VIM.Hosts` | Reference | source | The hypervisor host this node is |

Several of those chain usefully. This one crosses three modules in a single statement:

```sql
SELECT TOP 20
    n.Caption                      AS NodeCaption,
    n.Engine.ServerName            AS PollingEngine,
    n.VendorInfo.Name              AS Vendor,
    n.NodeProperties.NodeGroup     AS NcmFolder,
    n.NodeProperties.LastInventory AS LastInventory
FROM Orion.Nodes n
ORDER BY n.Caption
```

A to-many navigation multiplies rows, so filtering through one is a filter on the pair, not
on the node:

```sql
SELECT TOP 50
    n.Caption                   AS NodeCaption,
    n.Volumes.Caption           AS VolumeCaption,
    n.Volumes.VolumePercentUsed AS PercentUsed
FROM Orion.Nodes n
WHERE n.Volumes.VolumePercentUsed > 90
ORDER BY n.Caption
```

That returns one row per node and volume pair over 90 percent, not one row per node.
[joins-and-navigation.md](../swql/joins-and-navigation.md) covers the cardinality rules in
full.

## Finding a path

When you know the two ends but not the route, let the tool search. It walks both directions
and resolves inherited navigations, breadth first, so the shortest route comes back first.

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
```

Five routes exist, and this is exactly the case where guessing goes wrong. The one you almost
certainly want is the second, `Orion.APM.Component.Application.Node`, because a component
belongs to an application and the application belongs to a node. The first route, through
`AlertObject`, is shorter to type but only returns components that have an alert object.
`InApplicationTcpConnections.ClientNode` and `.ServerNode` reach a node too, and mean
something entirely different.

The lesson generalises: **shortest is not the same as correct.** Read the hops, decide which
relationship expresses the question you are actually asking, then use that one. The tool
narrows the candidates from 2067 entities to five; picking among five is your job.

`--max-hops` and `--max-paths` bound the search when the default is not enough.

## Asking a live server instead

`Metadata.Relationship` is the same information on your own installation, including modules
this repository's extract does not cover, and it carries two things the published pages do
not: cardinality, and the primary and foreign key names behind each navigation.

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
WHERE r.SourceType = 'Orion.Nodes' OR r.TargetType = 'Orion.Nodes'
ORDER BY r.Name
```

`SourcePropertyName` and `TargetPropertyName` are the two navigation property names the
relationship creates, which is the live equivalent of the source and target tables.
`SourceCardinalityMax` and `TargetCardinalityMax` tell you which end is to-many, which is
what decides whether a navigation multiplies your rows.

`Metadata.Property` also flags navigations directly:

```sql
SELECT p.Name, p.Type, p.IsNavigable
FROM Metadata.Property p
WHERE p.Entity.FullName = 'Orion.Nodes' AND p.IsNavigable = TRUE
ORDER BY p.Name
```

See [metadata-introspection.md](../swis/metadata-introspection.md).

## Building automations on relationships.json

[relationships.json](../../data/schema/2026.2/relationships.json) is a flat edge list, which
makes it directly usable as a graph. Each record has six fields:

```json
{
  "from": "Orion.Nodes",
  "navigationProperty": "Interfaces",
  "to": "Orion.NPM.Interfaces",
  "direction": "source",
  "relationship": "Orion.NodeHostsInterfaces",
  "kind": "System.Hosting"
}
```

`from` is always the entity the navigation is usable from, so a single adjacency list built
on `from` already covers both directions. `direction` is retained only so you can tell which
schema table the row came from; it is not a constraint on traversal.

A path finder is about twenty lines:

```python
import json
from collections import defaultdict, deque

EDGES = json.load(open("data/schema/2026.2/relationships.json"))

# "from" is always the navigable end, so one adjacency list covers both directions.
adjacency = defaultdict(list)
for edge in EDGES:
    adjacency[edge["from"]].append((edge["navigationProperty"], edge["to"], edge["kind"]))


def shortest_path(source, target, max_hops=3):
    """Return the dotted navigation path from source to target, or None."""
    queue = deque([(source, [])])
    seen = {source}
    while queue:
        entity, trail = queue.popleft()
        if len(trail) >= max_hops:
            continue
        for nav, nxt, _kind in adjacency[entity]:
            if nxt == target:
                return ".".join(step[0] for step in trail + [(nav, nxt)])
            if nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, trail + [(nav, nxt)]))
    return None


print(shortest_path("Orion.NPM.Interfaces", "Orion.Nodes"))
print(shortest_path("Orion.Nodes", "Orion.Engines"))
```

```text
Node
Engine
```

Three patterns are worth knowing.

**Generating a query rather than hand-writing one.** Given an anchor entity and a list of
facts you want, look each one up as a path and emit the dotted column list. This is how you
build a reporting tool that does not break when someone asks for a column on a different
entity.

**Discovering everything owned by an object.** Filter to `kind == "System.Hosting"` and
`direction == "source"` and you have the containment tree. Walking it from `Orion.Nodes`
gives you every entity type that would be affected by deleting a node, which is the
pre-flight check worth running before a bulk delete.

```bash
jq -r '.[] | select(.from=="Orion.Nodes" and .kind=="System.Hosting") | "\(.navigationProperty) -> \(.to)"' data/schema/2026.2/relationships.json | head -8
```

```text
Inventory -> Orion.ADM.NodeInventory
Anomalies -> Orion.AIIM.Orion_Nodes_Anomalies
Applications -> Orion.APM.Application
ASANode -> Orion.ASA.Node
ConnectionStatistic -> Orion.ASA.ConnectionStatistics
ASAFavoriteInterface -> Orion.ASA.FavoriteInterfaces
NCMLicenseStatus -> Cirrus.NCMNodeLicenseStatus
NodeProperties -> NCM.NodeProperties
```

**Detecting which modules are installed.** An entity only exists when its module is
installed, so a navigation whose target entity is missing from a server tells you the module
is not there. Compare the edge list against `Metadata.Entity` on the server and the
difference is the module inventory. See
[modules/README.md](../modules/README.md).

Remember that the edge list describes the schema, not the data. An edge from `Orion.Nodes` to
`Orion.UDT.Port` exists whether or not User Device Tracker is licensed, and whether or not
any node has ports. Always confirm against the server before acting on the result.

## Four things in the data that will surprise you

These are all verified properties of the published 2026.2 schema, not bugs in the extraction.

**A navigation property name is not unique on an entity.** There are 21 (entity, navigation
property) pairs in 2026.2 where the same name is declared twice. Ten of the 21 lead to two
different targets: on `Orion.Nodes`, `Flows` leads both to `Orion.Netflow.Flows` and to
`Orion.Netflow.FlowsByApplication`. The other eleven lead to the same target through two
different relationship definitions. How a live server resolves either case is not something
the published pages answer, so if you hit one, check `Metadata.Relationship` on the server
before relying on any single reading.

```bash
jq -r 'group_by([.from, .navigationProperty])[] | select(length > 1) | "\(.[0].from).\(.[0].navigationProperty) -> \([.[].to] | join(", "))"' data/schema/2026.2/relationships.json | head -5
```

```text
IPAM.GroupNodeAttr.GroupNode -> IPAM.GroupReport, IPAM.GroupNode
IPAM.GroupsCustomProperties.GroupNode -> IPAM.GroupReport, IPAM.GroupNode
Orion.APIPoller.ApiPoller.Metrics -> Orion.APIPoller.ApiPoller.Metrics, Orion.APIPoller.ValueToMonitor
Orion.APM.Exchange.DatabaseCopy.Database -> Orion.APM.Exchange.Database, Orion.APM.Exchange.Database
Orion.AlertConfigurationsCustomProperties.Alert -> Orion.AlertConfigurations, Orion.AllActiveAlerts.Dashboard
```

The fourth line is the subtler variant: the same name, the same target, two different
relationship definitions, one `System.Reference` and one `System.Reliance`.

**Ten relationships are recorded from one end only.** 1491 of the 1501 definitions appear
twice, once from each end. The other ten appear once, because the page at the far end does
not list the counterpart. `Orion.Dashboards.Instances.Routes` is one of them. That does not
mean the reverse navigation does not exist on a server, only that the published page does not
name it.

**Eight relationship targets have no entity page.** The edge list names eight entities that
are not among the 2067 documented types, so a name appearing as a target is not proof that
the entity exists. Two of the eight are casing slips in the published schema:
`Orion.VIM.DataStores` and `Orion.Ipsla.CCMPhones` are absent, while `Orion.VIM.Datastores`
and `Orion.IpSla.CCMPhones` are real. Check a target name before using it:

```bash
python3 tools/schema_query.py find Datastores
```

```text
entities matching 'datastores' (3 total)
  Orion.VIM.Datastores                                   34p   0v  Virtual Datastore
  Orion.VIM.DatastoreStatistics                          33p   0v  Datastore Statistics History
  Orion.VIM.DatastoresCustomProperties                    1p   4v  Custom Properties
```

`python3 tools/check_data.py --version 2026.2` notes the count of eight on every run, naming
the five most common, which is how they stay visible rather than quietly becoming folklore.
For all eight names at once, ask the edge list directly:

```bash
jq -rs '(.[0] | map(.to)) - (.[1] | map(.entity)) | unique[]' data/schema/2026.2/relationships.json data/schema/2026.2/index.json
```

```text
Orion.Cloud.Azure.SWIPUnsupportedResources
Orion.Dashboards.DashboardRoute
Orion.Ipsla.CCMPhones
Orion.NetPath.EndpointServicesBase
Orion.NetPath.ProbesBase
Orion.PolicyEngine.RuleWaiver
Orion.SCM.AssignedElementSettingOverride
Orion.VIM.DataStores
```

**Sixteen edges point an entity at itself.** They come from eight relationship definitions
across seven entities, each recorded from both ends. `Orion.Nodes` accounts for four of the
sixteen edges, and every one of them is `System.Reliance`: `BMCControllerNodeForRack` and
`SdWanNodeRelyOrchestratorInfo` as source, `RackNodes` and `OrchestratorInfoRelySdWanNode` as
target. Any graph traversal over this data therefore needs cycle handling, which is why the
path finder above tracks `seen`, and why the repository's own `path` command excludes cycles
per trail rather than globally, so that an alternate route through a hub entity is not hidden
by the first one to reach it.

## Where to go next

- [joins-and-navigation.md](../swql/joins-and-navigation.md) for cardinality, explicit joins
  and ten worked examples.
- [entity-model.md](entity-model.md) for inheritance, which governs which navigations an
  entity actually has.
- [using-the-data.md](using-the-data.md) for the rest of the generated files and how to
  query them.
- [metadata-introspection.md](../swis/metadata-introspection.md) to ask your own server.

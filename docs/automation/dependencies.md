# Dependencies

A dependency tells the platform that one object's availability depends on another's. When
the parent goes down, the children are marked **Unreachable** (status 12) rather than
**Down** (status 2), and alerts for them are suppressed.

That is the whole point. Without dependencies, a failed core switch produces one alert for
the switch and several hundred for everything behind it, and the one alert that matters is
buried. With dependencies, you get the switch.

## The entities

| Entity | Holds | Size |
| --- | --- | --- |
| `Orion.Dependencies` | Dependencies, both user-defined and automatically discovered | 16 properties, 1 verb |
| `Orion.DeletedAutoDependencies` | Automatic dependencies a user has dismissed | 16 properties, 1 verb |
| `Orion.AutoDependencyRoot` | Roots the automatic discovery works out from, per engine | 6 properties |
| `Orion.DependencyEntities` | Entity types that can take part in a dependency | 3 properties |

`Orion.Dependencies` and `Orion.DeletedAutoDependencies` declare the same sixteen
properties and carry the same operations: create, read, update, delete and invoke, gated on
the `manageNodes` right for everything except read. They are the same shape because a
dismissed dependency is a dependency that has been moved rather than one that has been
rewritten. `Orion.AutoDependencyRoot` is also writable; `Orion.DependencyEntities` declares
no operations at all and is read-only reference data. Confirm on your own version with:

```bash
python3 tools/schema_query.py show Orion.Dependencies
```

### The verbs want `admin`, not `manageNodes`

Read the entity's access control and the verb's separately. The CRUD operations are gated on
`manageNodes`, but both verbs declare **`admin`**:

```bash
python3 tools/schema_query.py verb Orion.Dependencies RemoveDependencies
```

This is the difference between an automation account that can create and delete dependencies
all day and one that can also dismiss automatic ones. An account provisioned with
`manageNodes` on the assumption that it covers the whole entity will do everything on this
page except the two verbs, and will fail on those at call time rather than at setup time. See
[accounts-and-permissions.md](accounts-and-permissions.md).

## Which objects can take part

Not every entity type can be either end of a dependency, and the two ends are gated
separately. `Orion.DependencyEntities` is the list, and `ValidParent` and `ValidChild` are
independent flags:

```sql
SELECT
    de.EntityName,
    de.ValidParent,
    de.ValidChild
FROM Orion.DependencyEntities de
ORDER BY de.EntityName
```

Run it before building a dependency programmatically. A type that is a valid child but not a
valid parent is the case that catches people out: the create call is rejected, or worse
accepted into a dependency that never participates in status calculation. The contents are
runtime data that varies with which modules are installed, so **this repository does not
enumerate them** — the query above is the authority on your own server.

To check one type before you use it:

```sql
SELECT de.EntityName, de.ValidParent, de.ValidChild
FROM Orion.DependencyEntities de
WHERE de.EntityName = 'Orion.Groups'
```

## How a dependency is expressed

Parent and child are identified two ways at once, and knowing which to use matters:

- `ParentUri` and `ChildUri` are `System.Uri` values, the canonical references. Use these
  when creating a dependency.
- `ParentEntityType` with `ParentNetObjectID`, and the child equivalents, are the
  decomposed form. These are far easier to filter and join on in a query.

`AutoManaged` distinguishes a dependency the platform discovered from topology
(`true`) from one a person created (`false`). `IncludeInStatusCalculation` controls
whether the dependency actually suppresses child status, which is what makes a
dependency do anything.

Four more of the sixteen are worth knowing about, because they appear in query results and
are easy to misread:

| Property | Type | What it is |
| --- | --- | --- |
| `FoundAsAutoManaged` | `System.Boolean` | Whether this dependency was originally discovered, regardless of what `AutoManaged` says now |
| `EngineID` | `System.Int32` | The polling engine the dependency is associated with |
| `Category` | `System.Int32` | An integer classification |
| `Owner` | `System.String` | Who created it |

`FoundAsAutoManaged` next to `AutoManaged` is the useful pair. A row where
`FoundAsAutoManaged = TRUE` and `AutoManaged = FALSE` is a dependency the platform found and a
person has since taken over, which means automatic discovery will no longer maintain it and
nobody was necessarily told:

```sql
SELECT
    d.Name,
    d.Owner,
    d.ParentEntityType,
    d.ChildEntityType,
    d.LastUpdateUTC
FROM Orion.Dependencies d
WHERE d.FoundAsAutoManaged = TRUE
  AND d.AutoManaged = FALSE
ORDER BY d.LastUpdateUTC DESC
```

What the `Category` integer classifies is **not recorded in the published schema** and is
unverified here. Read the distinct values on your own server before filtering on it.

## Listing what exists

```sql
SELECT
    d.DependencyId,
    d.Name,
    d.ParentEntityType,
    d.ParentNetObjectID,
    d.ChildEntityType,
    d.ChildNetObjectID,
    d.AutoManaged,
    d.IncludeInStatusCalculation,
    d.LastUpdateUTC
FROM Orion.Dependencies d
ORDER BY d.Name
```

Manually created dependencies only, which is the set a person is responsible for:

```sql
SELECT
    d.Name,
    d.Description,
    d.Owner,
    d.ParentEntityType,
    d.ChildEntityType,
    d.IncludeInStatusCalculation
FROM Orion.Dependencies d
WHERE d.AutoManaged = FALSE
ORDER BY d.Name
```

## Dependencies that are not doing anything

This is the query worth running periodically. A dependency with
`IncludeInStatusCalculation = FALSE` exists, appears in the web console, and suppresses
nothing. It is a common reason for an alert storm that everyone believed was already
handled:

```sql
SELECT
    d.Name,
    d.ParentEntityType,
    d.ChildEntityType,
    d.AutoManaged,
    d.IncludeInStatusCalculation
FROM Orion.Dependencies d
WHERE d.IncludeInStatusCalculation = FALSE
ORDER BY d.Name
```

## Finding what depends on a node

Because the decomposed columns exist, this is a plain filter rather than a URI comparison:

```sql
SELECT
    d.Name,
    d.ChildEntityType,
    d.ChildNetObjectID,
    d.IncludeInStatusCalculation
FROM Orion.Dependencies d
WHERE d.ParentEntityType = 'Orion.Nodes'
  AND d.ParentNetObjectID = @nodeId
```

And the reverse, what a node depends on:

```sql
SELECT
    d.Name,
    d.ParentEntityType,
    d.ParentNetObjectID
FROM Orion.Dependencies d
WHERE d.ChildEntityType = 'Orion.Nodes'
  AND d.ChildNetObjectID = @nodeId
```

## Objects currently suppressed by a dependency

Status 12 is Unreachable, which means the object is not being reported as down because
something it depends on already is. If an outage looks smaller than expected, this is
where the rest of it went:

```sql
SELECT
    n.Caption,
    n.IPAddress,
    n.Status,
    n.NodeStatusRootCause
FROM Orion.Nodes n
WHERE n.Status = 12
ORDER BY n.Caption
```

`NodeStatusRootCause` is worth selecting here: it names why the platform reached that
conclusion, which saves tracing the dependency chain by hand.

## Creating a dependency

Dependencies are created through CRUD rather than through a verb. Get both URIs from a
query rather than assembling them, since the system identifier is fixed per installation:

```powershell
$swis = Connect-Swis -Hostname orion.example.com -Trusted

$parentUri = Get-SwisData $swis @'
SELECT Uri FROM Orion.Nodes WHERE Caption = 'core-switch-01'
'@

$childUri = Get-SwisData $swis @'
SELECT Uri FROM Orion.Nodes WHERE Caption = 'access-switch-14'
'@

$props = @{
    Name                       = 'access-switch-14 depends on core-switch-01'
    ParentUri                  = $parentUri
    ChildUri                   = $childUri
    IncludeInStatusCalculation = $true
}

$uri = New-SwisObject $swis -EntityType 'Orion.Dependencies' -Properties $props
Get-SwisObject $swis -Uri $uri
```

Read it back. A dependency that was created but left out of status calculation is
indistinguishable from a working one until the next outage.

## Dismissing an automatic dependency

Automatic dependencies are discovered from topology and are sometimes wrong. Rather than
deleting them, which invites rediscovery, dismiss them: `Orion.Dependencies` exposes a
single verb for this.

```bash
python3 tools/schema_query.py verb Orion.Dependencies RemoveDependencies
```

Which summarises to:

```
Orion.Dependencies.RemoveDependencies(ids) -> number
  Ignore dependencies. Such dependencies are ingored in Autodependency calculation.
```

It takes an array of dependency ids and returns a count. Dismissed dependencies move to
`Orion.DeletedAutoDependencies`, which is how the platform remembers not to bring them
back:

```powershell
$ids = Get-SwisData $swis @'
SELECT DependencyId
FROM Orion.Dependencies
WHERE AutoManaged = TRUE
  AND ParentEntityType = 'Orion.Nodes'
  AND ParentNetObjectID = 42
'@

Invoke-SwisVerb $swis 'Orion.Dependencies' 'RemoveDependencies' @(,$ids)
```

The `@(,$ids)` form passes the array as a single argument rather than splatting its
elements into separate positional arguments. Verb arguments are positional, so this
distinction matters; see [../swis/invoke-verbs.md](../swis/invoke-verbs.md).

To review what has been dismissed:

```sql
SELECT
    dd.Name,
    dd.ParentEntityType,
    dd.ParentNetObjectID,
    dd.ChildEntityType,
    dd.ChildNetObjectID,
    dd.LastUpdateUTC
FROM Orion.DeletedAutoDependencies dd
ORDER BY dd.LastUpdateUTC DESC
```

## Undoing a dismissal

A dismissal is reversible, and the verb that reverses it lives on the other entity. This is
the symmetry worth internalising: `RemoveDependencies` on `Orion.Dependencies` moves a row
*into* the dismissed set, and `RemoveIgnoredAutoDependencies` on
`Orion.DeletedAutoDependencies` removes it from that set, which lets automatic discovery find
the dependency again on its next pass.

```bash
python3 tools/schema_query.py verb Orion.DeletedAutoDependencies RemoveIgnoredAutoDependencies
```

Which summarises to:

```
Orion.DeletedAutoDependencies.RemoveIgnoredAutoDependencies(ids) -> number
  Removes ignored dependencies.
```

The signature is identical to its counterpart — one array of ids, returning a count — so the
same array-passing care applies:

```powershell
$ids = Get-SwisData $swis @'
SELECT DependencyId
FROM Orion.DeletedAutoDependencies
WHERE ParentEntityType = 'Orion.Nodes'
  AND ParentNetObjectID = 42
'@

Invoke-SwisVerb $swis 'Orion.DeletedAutoDependencies' 'RemoveIgnoredAutoDependencies' @(,$ids)
```

Note what this verb does not do. It does not recreate the dependency; it removes the record
that suppressed rediscovery. The dependency comes back only if automatic discovery still sees
the topology that produced it in the first place. If the link is gone, nothing returns, and
that is the correct outcome rather than a failure.

## How automatic discovery is scoped

`Orion.AutoDependencyRoot` is the working state of the automatic discovery process, one row
per root it calculates outward from:

```sql
SELECT
    r.RootNodeID,
    r.RootEngineID,
    r.EngineID,
    r.TotalNodeCount,
    r.EngineNodeCount,
    r.LastUpdateUTC
FROM Orion.AutoDependencyRoot r
ORDER BY r.TotalNodeCount DESC
```

The two counts are the interesting pair. `TotalNodeCount` is how many nodes the root reaches
overall and `EngineNodeCount` how many of those belong to the engine in `EngineID`, so a root
whose two counts diverge sharply is one whose topology crosses a polling engine boundary.
`LastUpdateUTC` tells you when discovery last ran; a stale timestamp across every row means
automatic dependencies have quietly stopped being maintained, which looks exactly like a
network that has stopped changing.

Join it to node captions to make it readable:

```sql
SELECT
    n.Caption,
    r.TotalNodeCount,
    r.EngineNodeCount,
    r.LastUpdateUTC
FROM Orion.AutoDependencyRoot r
JOIN Orion.Nodes n ON n.NodeID = r.RootNodeID
ORDER BY r.TotalNodeCount DESC
```

The precise algorithm that selects a root, and what the counts are used for once calculated,
are **not recorded in the published schema** and are unverified here. Treat the table as
diagnostic evidence about discovery rather than as a control surface.

## Application dependencies from SAM

Topology is not the only source of dependencies. When SAM is monitoring processes, it observes
TCP connections between them and hangs the result off the same `Orion.Dependencies` rows,
through two entities:

| Entity | Grain |
| --- | --- |
| `Orion.APM.ApplicationTcpConnection` | One row per observed process-to-process connection, 38 properties |
| `Orion.APM.DependencyTcpStatistics` | Latency and packet loss rolled up per dependency, 19 properties |

`Orion.APM.ApplicationTcpConnection` carries both ends of the conversation in parallel
columns — `ClientProcessName` against `ServerProcessName`, `ClientNodeID` against
`ServerNodeID`, and so on — plus `ServerPort`, which is usually what identifies the service:

```sql
SELECT
    c.ClientProcessName,
    c.ClientNodeIPAddress,
    c.ServerProcessName,
    c.ServerNodeIPAddress,
    c.ServerPort,
    c.Latency,
    c.PacketLoss,
    c.LastSeenTimeStamp
FROM Orion.APM.ApplicationTcpConnection c
ORDER BY c.LastSeenTimeStamp DESC
```

`ParentDependencyID` is the link back: it holds the `DependencyId` of the `Orion.Dependencies`
row this connection belongs to. There is also a navigation property for it, which is the
better way to write the join:

```sql
SELECT
    c.DisplayName,
    c.ServerPort,
    c.Status,
    c.Dependency.Name,
    c.Dependency.IncludeInStatusCalculation
FROM Orion.APM.ApplicationTcpConnection c
WHERE c.Dependency.IncludeInStatusCalculation = FALSE
```

That query is the application-layer version of the "not doing anything" check earlier on this
page: an observed application dependency whose underlying dependency row suppresses nothing.

Both ends also navigate to nodes, so you can ask what a given node talks to without joining on
ids. From the connection, `ClientNode` and `ServerNode`; from `Orion.Nodes`, the reverse pair
is `OutApplicationTcpConnections` where the node is the client and `InApplicationTcpConnections`
where it is the server:

```sql
SELECT
    n.Caption,
    conn.ServerProcessName,
    conn.ServerPort,
    conn.ServerNodeIPAddress
FROM Orion.Nodes n
JOIN Orion.APM.ApplicationTcpConnection conn ON conn.ClientNodeID = n.NodeID
WHERE n.NodeID = @nodeId
ORDER BY conn.ServerPort
```

The rolled-up view is `Orion.APM.DependencyTcpStatistics`, one row per dependency rather than
per connection, which is what a dashboard shows:

```sql
SELECT
    s.DependencyID,
    s.Latency,
    s.PacketLoss,
    s.Status,
    s.LastPoll,
    s.Dependency.Name
FROM Orion.APM.DependencyTcpStatistics s
ORDER BY s.PacketLoss DESC
```

Note that `Orion.APM.DependencyTcpStatistics` spells its key `DependencyID` with a capital D
in `ID`, while `Orion.Dependencies` spells the same key `DependencyId`. Property names are
treated case insensitively in SolarWinds' own samples, so writing either is unlikely to fail
the query, but the column comes back spelled as the schema declares it — and a client that
maps result columns onto a case-sensitive structure will read one of the two and miss the
other. Match the schema's casing per entity. See
[../swql/language-reference.md](../swql/language-reference.md).

## Practical notes

**Dependencies are not the same as groups.** A group rolls child status up into a
container status. A dependency suppresses child alerts when a parent fails. They are often
used together, and a group can be either end of a dependency, but they solve different
problems. See [../schema/relationships.md](../schema/relationships.md).

**Check the direction.** Parent is the thing that must be up; child is the thing that
depends on it. Reversing them produces a dependency that suppresses nothing during the
outage you built it for and suppresses the wrong things during one you did not.

**Automatic discovery needs topology.** It works from what the platform knows about how
devices connect, so it covers well-discovered network paths and not much else. Anything
where the dependency is logical rather than topological (an application depending on a
database on another host) has to be created manually — or, if SAM is watching both
processes, is observed as a TCP connection instead, which is what the APM entities above
hold.

**Delete and dismiss are different operations.** Deleting an automatic dependency through
CRUD removes the row and leaves nothing to stop discovery recreating it on the next pass.
Dismissing it through `RemoveDependencies` moves it to `Orion.DeletedAutoDependencies`, which
is the record that keeps it away. If a dependency you removed keeps coming back, this is why.

**Check both entities when auditing.** A dependency that is absent from `Orion.Dependencies`
has either never existed or been dismissed, and only `Orion.DeletedAutoDependencies`
distinguishes the two. An audit that reads one entity reports the second case as the first.

**The child is the thing that gets suppressed.** Because suppression is the whole point,
the blast radius of a wrong dependency is the child set, not the parent. A dependency
pointing at a busy core device as its *child* silences that device during unrelated outages,
and nothing about the configuration looks wrong until it matters.

## See also

- [../swis/crud.md](../swis/crud.md) for creating and updating entities
- [../swis/invoke-verbs.md](../swis/invoke-verbs.md) for the Invoke contract, including array arguments
- [accounts-and-permissions.md](accounts-and-permissions.md) for the rights the verbs need
- [../reference/status-codes.md](../reference/status-codes.md) for what status 12 means
- [alerts.md](alerts.md) for alert suppression more broadly
- [../modules/sam.md](../modules/sam.md) for the application monitoring behind the TCP connection entities
- [../schema/relationships.md](../schema/relationships.md) for navigation properties and both relationship directions
- [../../scripts/swql/07-groups-and-dependencies.swql](../../scripts/swql/07-groups-and-dependencies.swql)

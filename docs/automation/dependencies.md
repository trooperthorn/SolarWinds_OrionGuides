# Dependencies

A dependency tells the platform that one object's availability depends on another's. When
the parent goes down, the children are marked **Unreachable** (status 12) rather than
**Down** (status 2), and alerts for them are suppressed.

That is the whole point. Without dependencies, a failed core switch produces one alert for
the switch and several hundred for everything behind it, and the one alert that matters is
buried. With dependencies, you get the switch.

## The entities

| Entity | Holds |
| --- | --- |
| `Orion.Dependencies` | Dependencies, both user-defined and automatically discovered |
| `Orion.DeletedAutoDependencies` | Automatic dependencies a user has dismissed |
| `Orion.AutoDependencyRoot` | Roots the automatic discovery works out from |
| `Orion.DependencyEntities` | Entity types that can take part in a dependency |

`Orion.Dependencies` supports create, read, update, delete and invoke, gated on the
`manageNodes` right for everything except read. Confirm on your own version with:

```bash
python3 tools/schema_query.py show Orion.Dependencies
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
database on another host) has to be created manually.

## See also

- [../swis/crud.md](../swis/crud.md) for creating and updating entities
- [../swis/invoke-verbs.md](../swis/invoke-verbs.md) for the Invoke contract
- [../reference/status-codes.md](../reference/status-codes.md) for what status 12 means
- [alerts.md](alerts.md) for alert suppression more broadly
- [../../scripts/swql/07-groups-and-dependencies.swql](../../scripts/swql/07-groups-and-dependencies.swql)

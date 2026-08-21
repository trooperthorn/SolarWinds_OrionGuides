# Device Studio pollers

Device Studio is the console feature for building a vendor-specific poller without writing an
OID by hand. You pick a technology, describe what to collect, and the result is a poller that
can be assigned to nodes like any other — except that it lives in its own three entities and
none of the queries in [standard-pollers.md](standard-pollers.md) can see it.

Everything here is **read-only through SWIS**. None of the three entities declares any
operations, so a poller is built in the console and this API tells you what exists and what it
is assigned to. That is still the useful half: it answers "what is this node actually
collecting" when the answer is not in `Orion.Pollers`.

## The three entities

| Entity | Holds | Size |
| --- | --- | --- |
| `Orion.DeviceStudio.Technologies` | The technology a poller belongs to | 3 properties |
| `Orion.DeviceStudio.Pollers` | The poller definition | 10 properties |
| `Orion.DeviceStudio.PollerAssignments` | What it is assigned to | 5 properties |

They form a straight chain. `Orion.DeviceStudio.Technologies` navigates down through `Pollers`,
`Orion.DeviceStudio.Pollers` navigates down through `Assignments` and back up through
`Technology`, and `Orion.DeviceStudio.PollerAssignments` navigates back through `Poller`. Both
hops are `System.Hosting`, which is the schema saying the child does not exist without its
parent.

## The technologies

```sql
SELECT
    t.TechnologyID,
    t.Name,
    t.Enabled
FROM Orion.DeviceStudio.Technologies t
ORDER BY t.Name
```

Three columns, and `Enabled` is the one worth noticing: a technology that is switched off takes
its pollers with it, so a poller can be `Enabled = TRUE` and collecting nothing because the
technology above it is not. Check both:

```sql
SELECT
    p.Name,
    p.Enabled AS PollerEnabled,
    p.Technology.Name AS TechnologyName,
    p.Technology.Enabled AS TechnologyEnabled
FROM Orion.DeviceStudio.Pollers p
WHERE p.Technology.Enabled = FALSE
ORDER BY p.Technology.Name, p.Name
```

## The poller definitions

```sql
SELECT
    p.PollerID,
    p.Name,
    p.Description,
    p.Vendor,
    p.Author,
    p.Tags,
    p.Priority,
    p.Enabled
FROM Orion.DeviceStudio.Pollers p
ORDER BY p.Vendor, p.Name
```

`Vendor` and `Tags` are how the console groups these, and `Author` is the closest thing to a
record of who built one — worth selecting before deleting anything in the console, since the
API cannot.

`Priority` is a `System.Int32` and orders pollers that could both apply to the same device.
What the ordering means when two share a priority is **not recorded in the published schema**
and is unverified here.

## The assignments

```sql
SELECT
    a.ID,
    a.PollerID,
    a.NetObjectType,
    a.NetObjectID,
    a.Enabled,
    a.Poller.Name AS PollerName,
    a.Poller.Vendor AS Vendor
FROM Orion.DeviceStudio.PollerAssignments a
ORDER BY a.Poller.Name
```

`NetObjectType` and `NetObjectID` are the **same two columns `Orion.Pollers` uses**, holding
the same values — `N` and a node id, `I` and an interface id. That is the whole reason these
two systems get confused, and it is also what makes the confusion consequential: a query
written against one returns a clean, plausible, complete-looking result while missing
everything in the other.

What one node is collecting from Device Studio:

```sql
SELECT
    a.ID,
    a.PollerID,
    a.Enabled,
    a.Poller.Name AS PollerName,
    a.Poller.Vendor AS Vendor
FROM Orion.DeviceStudio.PollerAssignments a
WHERE a.NetObjectType = 'N'
  AND a.NetObjectID = @nodeId
ORDER BY a.Poller.Name
```

Run this alongside the equivalent `Orion.Pollers` query when a node is collecting something you
cannot account for. A node can have assignments in both and neither query sees the other's.

## `TechnologyID` is a GUID here and a string elsewhere

`Orion.DeviceStudio.Pollers` carries two ids that look like they point into the neighbouring
technology polling system, and only one of them does:

| Property | Type | Points at |
| --- | --- | --- |
| `TechnologyID` | `System.Guid` | `Orion.DeviceStudio.Technologies.TechnologyID`, also a `System.Guid` |
| `TechnologyPollingID` | `System.String` | `Orion.TechnologyPolling.TechnologyPollingID`, also a `System.String` |

`Orion.TechnologyPolling` has a `TechnologyID` of its own and it is a **`System.String`**, not
a GUID. Same property name, different entity, different type, different id space — so joining
`Orion.DeviceStudio.Pollers.TechnologyID` to `Orion.TechnologyPolling.TechnologyID` is
comparing a GUID against a string and returns nothing, silently.

`TechnologyPollingID` is the column that actually bridges the two systems, and it is not a
declared relationship, so it has to be written as an explicit join:

```sql
SELECT
    p.Name AS PollerName,
    p.Vendor,
    p.TechnologyPollingID,
    tp.Priority
FROM Orion.DeviceStudio.Pollers p
JOIN Orion.TechnologyPolling tp ON tp.TechnologyPollingID = p.TechnologyPollingID
ORDER BY p.Name
```

Whether every Device Studio poller has a matching `Orion.TechnologyPolling` row, or only those
built on a technology the platform also polls declaratively, is **not recorded in the schema**
and is unverified here. Use a `LEFT JOIN` and count before assuming either.

See [technology-polling.md](technology-polling.md) for what is on the other side of that join.

## Gotchas

**Nothing here is writable.** All three entities declare no operations, so a Device Studio
poller cannot be created, assigned, enabled or deleted through SWIS. Automation can report on
them and nothing more.

**`NetObjectType` and `NetObjectID` collide with `Orion.Pollers`.** Same column names, same
values, unrelated tables. Always name the entity you mean.

**Two `Enabled` flags gate one assignment**, three counting the technology. The assignment, the
poller and the technology each carry one, and all three have to be true.

**`PollerID` is a GUID, not a `PollerType` string.** There is no overlap with the poller type
catalogue.

## Related pages

- [README.md](README.md) for the other four polling systems and how to tell them apart
- [technology-polling.md](technology-polling.md) for `Orion.TechnologyPolling`, which
  `TechnologyPollingID` joins to
- [standard-pollers.md](standard-pollers.md) for the `Orion.Pollers` system these share
  `NetObjectType` and `NetObjectID` with
- [../reference/netobject-types.md](../reference/netobject-types.md) for the prefixes
- [../swql/joins-and-navigation.md](../swql/joins-and-navigation.md) for navigation properties
  and why a type mismatch join returns nothing rather than erroring

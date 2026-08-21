# Polling

Creating an object does not monitor it. A node created through CRUD is a row; what turns it
into monitoring is a poller assignment, and nothing creates one for you.

That much is one idea. The complication is that the platform has grown **five separate
polling systems**, they share no entities, and several of them use the same column names for
unrelated things. A query written against one returns a clean, complete-looking result while
seeing nothing of the other four. This section is one page per system, and this page is the
map.

## The five systems

| System | Assignment entity | Keyed on | Writable through SWIS |
| --- | --- | --- | --- |
| [Standard pollers](standard-pollers.md) | `Orion.Pollers` | `PollerType` string plus `NetObjectType` and `NetObjectID` | Yes, CRUD |
| [Universal device pollers](universal-device-pollers.md) | `Orion.NPM.CustomPollerAssignmentOnNode`, `...OnInterface` | `CustomPollerID` GUID plus `NodeID` or `InterfaceID` | Assignments yes, definitions no |
| [Device Studio](device-studio.md) | `Orion.DeviceStudio.PollerAssignments` | `PollerID` GUID plus `NetObjectType` and `NetObjectID` | No |
| [Technology polling](technology-polling.md) | `Orion.TechnologyPollingAssignments` | `TechnologyPollingID` string plus `InstanceID` | Verbs only |
| [API pollers](api-pollers.md) | `Orion.APIPoller.ApiPoller` | `RelatedEntityType` and `RelatedEntityId` | Yes, CRUD and verbs |

Read the last column before planning any automation. Only two of the five can be fully
driven through CRUD, one is read-only, and one exposes nothing but verbs.

## Telling them apart

The fastest way to identify what you are looking at is the shape of its key:

- **A `PollerType` string** like `N.Cpu.SNMP.CiscoGen3` — standard pollers, and only there.
- **`NetObjectType` with `NetObjectID`** — standard pollers *or* Device Studio. These two use
  the same two column names holding the same values, which is the most consequential collision
  in this section. Name the entity you mean.
- **A GUID** — universal device pollers (`CustomPollerID`) or Device Studio (`PollerID`).
- **`InstanceID` with `TargetEntity`** — technology polling. `TargetEntity` holds an entity
  name rather than a prefix.
- **`RelatedEntityId` with `RelatedEntityType`** — API pollers. No NetObject anywhere.

Two id traps are worth learning before you write a join:

- **`TechnologyID` is a `System.Guid` in Device Studio and a `System.String` in technology
  polling.** Same name, two id spaces. Joining across them compares a GUID to a string and
  returns nothing rather than erroring. `TechnologyPollingID`, a string on both sides, is the
  column that genuinely bridges the two.
- **`PollerType` is a `System.String` on `Orion.Pollers` and a `System.Char` on
  `Orion.NPM.CustomPollers`**, and the two mean unrelated things.

## What a single object is actually collecting

There is no one query for this, and that is the point of the map. An object can carry
assignments in several systems at once, and each of the queries below sees only its own:

```sql
SELECT p.PollerID, p.PollerType, p.Enabled
FROM Orion.Pollers p
WHERE p.NetObjectType = 'N' AND p.NetObjectID = @nodeId
```

```sql
SELECT a.CustomPollerAssignmentID, a.CustomPoller.UniqueName, a.CustomPoller.OID
FROM Orion.NPM.CustomPollerAssignmentOnNode a
WHERE a.NodeID = @nodeId
```

```sql
SELECT dsa.ID, dsa.Enabled, dsa.Poller.Name
FROM Orion.DeviceStudio.PollerAssignments dsa
WHERE dsa.NetObjectType = 'N' AND dsa.NetObjectID = @nodeId
```

```sql
SELECT tpa.TechnologyPollingID, tpa.Enabled
FROM Orion.TechnologyPollingAssignments tpa
WHERE tpa.TargetEntity = 'Orion.Nodes' AND tpa.InstanceID = @nodeId
```

```sql
SELECT ap.Name, ap.Status, ap.LastPollTimestamp
FROM Orion.APIPoller.ApiPoller ap
WHERE ap.RelatedEntityType = 'Orion.Nodes' AND ap.RelatedEntityId = @nodeId
```

Run all five when the question is "why is this node collecting something I cannot find", or
"why is it still collecting after I removed the poller".

## The one gotcha that spans all five

**`Enabled = FALSE` is a third state, everywhere.** Every system distinguishes an assignment
that does not exist from one that exists and is switched off, and the second passes every
"does this object have pollers" check while collecting nothing. Device Studio stacks three of
these: the assignment, the poller and the technology each carry an `Enabled`, and all three
have to be true.

## The pages

| Page | Covers |
| --- | --- |
| [standard-pollers.md](standard-pollers.md) | `Orion.Pollers`: the poller type string, adding and removing assignments, letting discovery choose them, polling intervals, engine placement |
| [universal-device-pollers.md](universal-device-pollers.md) | UnDPs: an SNMP OID you defined, assigned through CRUD but defined in a Windows application |
| [device-studio.md](device-studio.md) | The three `Orion.DeviceStudio.*` entities, read-only, and the id space they share with technology polling |
| [technology-polling.md](technology-polling.md) | `Orion.Technology`, `Orion.TechnologyPolling` and its assignments, the four bulk enable and disable verbs, and the declarative poller templates |
| [api-pollers.md](api-pollers.md) | The ten `Orion.APIPoller.*` entities, HTTP collection, and moving a poller between servers |

## Related pages

- [../automation/README.md](../automation/README.md) for the method these guides follow:
  pick the interface, look the names up, write the SELECT first
- [../automation/node-management.md](../automation/node-management.md) for creating the node a
  poller attaches to
- [../automation/discovery.md](../automation/discovery.md) for network sonar and list resources
- [../automation/maintenance-mode.md](../automation/maintenance-mode.md) for stopping polling
  without touching assignments
- [../platform/architecture.md](../platform/architecture.md) for polling engines and where a
  poller actually runs
- [../reference/netobject-types.md](../reference/netobject-types.md) for the NetObject prefixes

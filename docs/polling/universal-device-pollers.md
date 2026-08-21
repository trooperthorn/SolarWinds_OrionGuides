# Universal Device Pollers

A universal device poller, or UnDP, is an SNMP OID you defined yourself. It is the answer when
the platform has no built-in poller for something a device exposes over SNMP, and you want it
charted and alertable like anything else.

It shares no entities with `Orion.Pollers`. Reaching for `Orion.Pollers` to assign a UnDP is
the single most common wrong turn in this section. See [README.md](README.md) for the other
three systems.

| Concept | Assignment entity | Key type |
|:---|:---|:---|
| Built-in poller | `Orion.Pollers` | `PollerType` string plus NetObject |
| Universal device poller on a node | `Orion.NPM.CustomPollerAssignmentOnNode` | `CustomPollerID` GUID plus `NodeID` |
| Universal device poller on an interface | `Orion.NPM.CustomPollerAssignmentOnInterface` | `CustomPollerID` GUID plus `InterfaceID` |

**The definition is created interactively, not through the API.** SolarWinds is explicit about
this on the
[NPM Universal Device Pollers](https://solarwinds.github.io/OrionSDK/docs/network-performance-monitor/npm-universal-device-pollers/)
page: you define a UnDP in the Universal Device Poller Windows application on the Orion server,
and you can export and import those definitions as files. `Orion.NPM.CustomPollers` declares no
operations at all in the schema, which is consistent: it is a read-only view of definitions
made elsewhere.

**The assignment is created through the API**, and it is an ordinary CRUD create with two
properties:

```powershell
$customPollerId = Get-SwisData $swis `
    "SELECT CustomPollerID FROM Orion.NPM.CustomPollers WHERE UniqueName = @name" `
    @{ name = 'ciscoEnvMonFanState' }

New-SwisObject $swis -EntityType 'Orion.NPM.CustomPollerAssignmentOnNode' -Properties @{
    NodeID         = $nodeId
    CustomPollerID = $customPollerId
}
```

To remove one, find its URI and delete it:

```sql
SELECT a.Uri, a.CustomPollerAssignmentID, a.NodeID
FROM Orion.NPM.CustomPollerAssignmentOnNode a
WHERE a.NodeID = @nodeId
```

`Orion.NPM.CustomPollerAssignmentOnNode` inherits through
`Orion.NPM.CustomPollerAssignment` from `System.ManagedEntity`, so unlike `Orion.Pollers` it
carries `UnManaged`, `UnManageFrom` and `UnManageUntil` and can be put into a maintenance
window on its own. It navigates to the node through `Node`, to the poller definition through
`CustomPoller`, and to the collected values through `CustomPollerStatus`. It carries the
`UNDPN` NetObject prefix; the interface variant carries `UNDPI`.

The definition entity, `Orion.NPM.CustomPollers`, is where the OID lives: `CustomPollerID`,
`UniqueName`, `Description`, `OID`, `MIB`, `SNMPGetType`, `NetObjectPrefix`, `PollerType`,
`GroupName`, `Format`, `Unit`, `Enabled`, `PollInterval`, `IncludeHistoricStatistics` and the
time-unit columns. Note that its own `PollerType` property is a `System.Char`, not the
`System.String` that `Orion.Pollers.PollerType` is, and means something entirely different.


## Worked queries

### Assignments and their last values

```sql
SELECT
    a.CustomPollerAssignmentID,
    a.NodeID,
    a.Node.Caption AS NodeCaption,
    a.CustomPoller.UniqueName AS PollerName,
    a.CustomPoller.OID AS PollerOID,
    a.Description
FROM Orion.NPM.CustomPollerAssignmentOnNode a
ORDER BY a.Node.Caption
```

`a.CustomPoller` navigates to `Orion.NPM.NodeCustomPollers`, which declares no properties of
its own and inherits every one of them from `Orion.NPM.CustomPollers`, so `UniqueName` and
`OID` resolve through it. That inheritance is invisible in the entity listing and is the reason
this join looks like it should not work.

The values themselves:

```sql
SELECT TOP 100
    s.NodeID, s.AssignmentName, s.CustomPollerID, s.DateTime,
    s.Status, s.RawStatus, s.Rate, s.Total, s.RowID
FROM Orion.NPM.CustomPollerStatusOnNode s
WHERE s.DateTime >= @startUtc
ORDER BY s.DateTime DESC
```

Time-bound, because this is a statistics table. `Status` is a `System.String` here and
`RawStatus` is the `System.Single` number behind it, which is the opposite of the convention
everywhere else in the platform.

The full definition list, when you need a `CustomPollerID` for an assignment:

```sql
SELECT cp.CustomPollerID, cp.UniqueName, cp.Description, cp.OID, cp.MIB,
       cp.SNMPGetType, cp.NetObjectPrefix, cp.Enabled, cp.PollInterval
FROM Orion.NPM.CustomPollers cp
ORDER BY cp.UniqueName
```


## Gotchas

**A UnDP is not an `Orion.Pollers` row.** It is `Orion.NPM.CustomPollerAssignmentOnNode` or
`...OnInterface`, keyed on a GUID `CustomPollerID`, and its definition is created in a Windows
application rather than through the API.

**`Orion.NPM.CustomPollers.PollerType` is a `System.Char`.** It is unrelated to
`Orion.Pollers.PollerType`, which is a `System.String`. Same property name, different entity,
different type, different meaning.

**`Status` and `RawStatus` are the wrong way round here.** On
`Orion.NPM.CustomPollerStatusOnNode`, `Status` is the `System.String` and `RawStatus` is the
number behind it, which inverts the convention used everywhere else in the platform.

**The status tables are statistics tables.** Window them by `DateTime` rather than scanning.
See [../swql/performance.md](../swql/performance.md).

## Related pages

- [README.md](README.md) for the other four polling systems
- [standard-pollers.md](standard-pollers.md) for `Orion.Pollers`, the system this one is most
  often confused with
- [../modules/npm.md](../modules/npm.md) for universal device pollers in their module context
- [../swis/crud.md](../swis/crud.md) for the assignment create and delete mechanics
- [../reference/netobject-types.md](../reference/netobject-types.md) for the `UNDPN` and
  `UNDPI` prefixes

## Official SolarWinds documentation

- [NPM Universal Device Pollers](https://solarwinds.github.io/OrionSDK/docs/network-performance-monitor/npm-universal-device-pollers/)

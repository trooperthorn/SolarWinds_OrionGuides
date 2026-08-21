# Hardware Health: sensors on physical machines

Hardware health is the sensor layer: fan speeds, power supply state, inlet and exhaust
temperatures, physical and logical disk state, RAID controller battery status, memory
module errors, and whatever else the vendor's agent or MIB exposes. It answers the
question that node status cannot, which is "the server is up, but is the hardware
underneath it dying".

## It is not a module you buy

This is the first thing to get straight, because it changes how you reason about whether
the entities will be there. Hardware health is **a shared capability, not a separately
licensed product**. There is no "Hardware Health" line on a licence. The netobject
reference in this repository attributes the entities to "NPM / SAM", meaning they appear
when either Network Performance Monitor or Server and Application Monitor is installed, and
they are collected as part of polling a node you already monitor.

The schema shows the capability reaching wider still. `Orion.HardwareHealth.HardwareInfo`
hangs off `Orion.Nodes`, `Orion.HardwareHealth.HardwareInfoForArray` hangs off
`Orion.SRM.StorageArrays`, and `Orion.HardwareHealth.HardwareInfoForChassis` hangs off
`Orion.HardwareHealth.BMC.Chassis`. So the same sensor model is reused for storage arrays
from Storage Resource Monitor and for blade chassis reached through a baseboard management
controller. Practically, that means the entities exist on almost any installation, and
whether they return rows depends on whether hardware health polling has been **enabled per
node**, not on licensing.

Enablement is explicit and per node. See [Enabling and disabling polling](#enabling-and-disabling-polling)
below, and SolarWinds'
[Hardware Health](https://solarwinds.github.io/OrionSDK/docs/hardware-health/) page.

## Namespace and size

Everything lives under `Orion.HardwareHealth.`, which holds **33 entities** in the 2026.2
schema, with **9 verbs** declared across four of them. Twenty-four of the entities are the
`Hardware*` core; the other eight are the `BMC.*` sub-family.

```bash
python3 tools/schema_query.py find Orion.HardwareHealth
python3 tools/schema_query.py props Orion.HardwareHealth.HardwareItem
python3 tools/schema_query.py verbs --entity Orion.HardwareHealth.HardwareInfoBase
```

## The three-level model

Hardware health has exactly three levels, and each has a `*Base` entity that declares the
properties plus per-parent subtypes that add only the parent's key.

```
Orion.HardwareHealth.HardwareInfoBase        one row per monitored piece of hardware
  |    Manufacturer, Model, ServiceTag, PollingMethod, LastPollTime, LastPollStatus
  |    CategoriesWithProblems, CategoriesWithStatus, AgentName, AgentVersion
  |
  |  subtypes, by what the hardware belongs to:
  |    Orion.HardwareHealth.HardwareInfo             + NodeID       -> Orion.Nodes
  |    Orion.HardwareHealth.HardwareInfoForChassis   + ChassisID    -> BMC.Chassis
  |    Orion.HardwareHealth.HardwareInfoForArray                    -> Orion.SRM.StorageArrays
  |    Orion.HardwareHealth.HardwareInfoForUCSChassis
  v
Orion.HardwareHealth.HardwareCategoryStatusBase   one row per category per machine
  |    HardwareCategoryID, HardwareCategoryName, ItemsWithProblems, ItemsWithStatus
  |
  |    Orion.HardwareHealth.HardwareCategoryStatus            + NodeID
  |    Orion.HardwareHealth.HardwareCategoryStatusForChassis  + ChassisID
  |    Orion.HardwareHealth.HardwareCategoryStatusForArray
  v
Orion.HardwareHealth.HardwareItemBase        one row per sensor
       Name, UniqueName, Value, Unit, OriginalStatus, Message, HardwareCategoryID

       Orion.HardwareHealth.HardwareItem            + NodeID -> Orion.Nodes
       Orion.HardwareHealth.HardwareItemForChassis  + ChassisID
       Orion.HardwareHealth.HardwareItemForArray
```

Because the base entities declare the properties, `schema_query.py show
Orion.HardwareHealth.HardwareItem` lists only two properties of its own. That is not the
whole story. Use `props`, which resolves inheritance and marks the origin of each member:

```bash
python3 tools/schema_query.py props Orion.HardwareHealth.HardwareItem
```

Thirty-five properties come back, including `Status` from `System.DashboardEntity` and
`UnManaged` from `System.ManagedEntity`. Inherited properties are queryable exactly like
declared ones.

**Query the subtype, not the base, when you want node context.** `Orion.HardwareHealth.HardwareItem`
has a `Node` navigation property; `Orion.HardwareHealth.HardwareItemBase` does not, because
a base row might belong to a chassis or an array instead.

## Sensors are typed by category

A sensor's type is not a string on the sensor. It is a foreign key,
`HardwareCategoryID`, pointing at `Orion.HardwareHealth.HardwareCategory`, and the
navigation property `HardwareCategory` walks it.

`Orion.HardwareHealth.HardwareCategory` has just four properties: `ID`, `Name`,
`IsDisabled`, and `CategoryOrder`. **The category rows are data, not schema.** They are not
in the extracted schema, and the exact set can vary with the version and the polling
method, so list them from your own server rather than hard-coding names:

```sql
SELECT
    c.ID,
    c.Name,
    c.IsDisabled,
    c.CategoryOrder
FROM Orion.HardwareHealth.HardwareCategory c
ORDER BY c.CategoryOrder
```

Once you have the names, filter on `hi.HardwareCategory.Name` rather than on the ID, so
the query keeps working across servers whose category IDs differ.

`Orion.HardwareHealth.HardwareHierarchy` gives the tree beneath a category: it carries
`HardwareInfoID`, `HardwareCategoryID`, `ParentID`, `ItemID`, `HasItem`, and `Name`, and
navigates to `Children`, which are `HardwareItemBase` rows. That is what the web console
uses to render nested groups such as physical disks inside a controller.

## Reading a sensor's state

A sensor row carries four different things that all look like status, and they are not
interchangeable:

| Property | Type | What it is |
|---|---|---|
| `Status` | `System.Int32` | The platform status integer. Join `Orion.StatusInfo` for a name. |
| `StatusDescription` | `System.String` | Already-rendered status text |
| `OriginalStatus` | `System.String` | **The vendor's own status string**, before the platform mapped it |
| `Message` | `System.String` | The last poll message, often the actual error text |

`OriginalStatus` is the one worth reaching for when the mapped status is unhelpfully
generic. A vendor reporting `predictiveFailure` or `degraded` maps to the same platform
`Warning` integer as a dozen other conditions, and the original string is what tells you
which.

The value itself is `Value`, a `System.Double`, and its unit is `Unit`, an integer keying
`Orion.HardwareHealth.HardwareUnit` (`ID`, `Name`, `HtmlText`). The sensor row also carries
`HardwareUnitDescription`, a pre-joined string, which is usually all you need.

Two more flags matter when you are counting failures. `IsDisabled` means the sensor was
switched off, and `IsDeleted` means the sensor disappeared from the hardware but its row
was kept. Neither is a failure, and neither is caught by a `Status` filter.

## Thresholds

`Orion.HardwareHealth.HardwareItemThreshold` is a small entity keyed by the sensor's `ID`,
with `Warning` and `Critical`. **Both are `System.String`, not numbers**, and the verbs
that set them take strings too. Reach it from a sensor with
`hi.HardwareItemThreshold.Warning`.

## Historical data

Three statistics entities hang off `HardwareItemBase`, all inheriting `ObservationTimestamp`,
`ObservationFrequency` and `Weight` from `System.StatisticsEntity`:

| Entity | Carries |
|---|---|
| `Orion.HardwareHealth.HardwareItemValueStatistics` | `MinValue`, `AvgValue`, `MaxValue`, `Availability`, `Status` |
| `Orion.HardwareHealth.HardwareItemStatistics` | The same plus `Weight` |
| `Orion.HardwareHealth.HardwareItemStatusStatistics` | `Status` and `Weight` only |

These are the tables to graph a temperature or a fan speed over time. As with every
statistics entity on the platform, bound the time range.

## The BMC family

Eight entities under `Orion.HardwareHealth.BMC.` cover hardware reached through a baseboard
management controller rather than through the operating system, which is how blade chassis
and rack enclosures are monitored.

| Entity | Key properties |
|---|---|
| `Orion.HardwareHealth.BMC.Controllers` | `NodeID`, `Port`, `Mode`, `UseSSL`, `CredentialID`, `SystemUpTime` |
| `Orion.HardwareHealth.BMC.Chassis` | `ID`, `ControllerID`, `Model`, `SerialNumber`, `DistinguishedName`, `Status` |
| `Orion.HardwareHealth.BMC.Blades` | `ID`, `ParentID`, `NodeID`, `BladeNodeID`, `Model`, `IPAddress`, `Status` |
| `Orion.HardwareHealth.BMC.Racks` | `ID`, `ControllerID`, `NodeID`, `RackNodeID`, `Model`, `IPAddress`, `Status` |
| `Orion.HardwareHealth.BMC.Fans` | `ID`, `ParentID`, `ParentType`, `NodeID`, `Power`, `Module`, `Status` |
| `Orion.HardwareHealth.BMC.PSUs` | `ID`, `ParentID`, `ParentType`, `NodeID`, `Power`, `Model`, `Status` |
| `Orion.HardwareHealth.BMC.FansOnChassis` | Subtype of `Fans`, the chassis-scoped view |
| `Orion.HardwareHealth.BMC.PSUsOnChassis` | Subtype of `PSUs`, the chassis-scoped view |

**`Status` on `Fans`, `PSUs`, `Blades` and `Racks` is a `System.String`, not an integer.**
`Orion.HardwareHealth.BMC.Chassis.Status` is a `System.Int32` and does join
`Orion.StatusInfo`. This inconsistency is real and it is the single most likely thing to
break a BMC query written by analogy with the rest of the platform. Check the type before
you write the join:

```bash
python3 tools/schema_query.py props Orion.HardwareHealth.BMC.Fans --grep status
```

`Orion.HardwareHealth.BMC.Controllers` also navigates out to `Orion.UCS.Chassis`,
`Orion.UCS.Fabrics`, and `Orion.UCS.Events`, which is how Cisco UCS gear is represented.

## Verbs

Nine verbs. All except `IsHardwareHealthEnabled` require the `manageNodes` right.
**Invoke arguments are positional**, so the order below is the contract; the names never
travel on the wire.

| Verb | Parameters | Returns |
|---|---|---|
| `Orion.HardwareHealth.HardwareInfoBase.EnableHardwareHealth` | `netObject`, `pollingmethod` | void |
| `Orion.HardwareHealth.HardwareInfoBase.DisableHardwareHealth` | `netObject` | void |
| `Orion.HardwareHealth.HardwareInfoBase.DeleteHardwareHealth` | `netObject` | void |
| `Orion.HardwareHealth.HardwareInfoBase.IsHardwareHealthEnabled` | `netObject` | boolean |
| `Orion.HardwareHealth.HardwareItemBase.EnableSensors` | `hardwareItems` | void |
| `Orion.HardwareHealth.HardwareItemBase.DisableSensors` | `hardwareItems` | void |
| `Orion.HardwareHealth.HardwareItemThreshold.SetThreshold` | `sensorId`, `warningThreshold`, `criticalThreshold` | void |
| `Orion.HardwareHealth.HardwareItemThreshold.ClearThresholds` | `sensorIds` | void |
| `Orion.HardwareHealth.BMC.Controllers.TestBmcConnection` | `nodeIpAddress`, `portNumber`, `userName`, `password`, `ssl`, `engineId` | connection test result |

Note that the verbs are declared on the **base** entities, `HardwareInfoBase` and
`HardwareItemBase`, not on `HardwareInfo` and `HardwareItem`. Invoke them on the base name.

### Enabling and disabling polling

`netObject` is a NetObject string, not a bare ID. For a node that is `N:<NodeID>`, so node
123 is `N:123`. SolarWinds' page states this explicitly.

```powershell
Import-Module SwisPowerShell
$swis = Connect-Swis -Hostname 'orion.example.com' -Credential (Get-Credential)

$nodeId = Get-SwisData $swis `
    "SELECT NodeID FROM Orion.Nodes WHERE Caption = @caption" @{ caption = 'app-server-01' }

# 6 is WmiDell. Pick the value that matches how the node is polled.
Invoke-SwisVerb $swis 'Orion.HardwareHealth.HardwareInfoBase' 'EnableHardwareHealth' `
    @("N:$nodeId", 6) | Out-Null

(Invoke-SwisVerb $swis 'Orion.HardwareHealth.HardwareInfoBase' 'IsHardwareHealthEnabled' `
    @("N:$nodeId")).InnerText
```

`pollingmethod` is one of the `HardwareHealthPollingMethod` values. This table is
SolarWinds' own, from their
[Hardware Health](https://solarwinds.github.io/OrionSDK/docs/hardware-health/) page:

| Value | Method | | Value | Method |
|---|---|---|---|---|
| 0 | Unknown | | 10 | SnmpJuniper |
| 1 | VMware | | 11 | SnmpNPMHP |
| 2 | SnmpDell | | 12 | SnmpF5 |
| 3 | SnmpHP | | 13 | SnmpDellPowerEdge |
| 4 | SnmpIBM | | 14 | SnmpDellPowerConnect |
| 5 | VMwareAPI | | 15 | SnmpDellBladeChassis |
| 6 | WmiDell | | 16 | SnmpHPBladeChassis |
| 7 | WmiHP | | 17 | Forwarded |
| 8 | WmiIBM | | 18 | SnmpArista |
| 9 | SnmpCisco | | | |

Those values are documented by SolarWinds but are **not** carried in the extracted schema,
which types the parameter only as a number. The `PollingMethod` column on
`Orion.HardwareHealth.HardwareInfoBase` holds the same integer, so you can confirm the
mapping on your own server by enabling one node through the web console and reading the
value back:

```sql
SELECT
    hwi.Node.Caption AS NodeName,
    hwi.PollingMethod,
    hwi.Manufacturer,
    hwi.Model
FROM Orion.HardwareHealth.HardwareInfo hwi
ORDER BY hwi.PollingMethod
```

`DisableHardwareHealth` stops collection but keeps what was already collected.
`DeleteHardwareHealth` removes the collected data as well. SolarWinds is explicit about
the difference, and it matters: disabling is reversible without losing history, deleting is
not.

### Enabling and disabling individual sensors

`EnableSensors` and `DisableSensors` take a single argument, `hardwareItems`, typed in the
contract as an enumerable of `HardwareHealthItemKey`. The shape of that key object is not
described in the schema or the Swagger contract, so *the exact structure to pass is
unverified here.* `Metadata.VerbArgument` on your own server carries an `XmlTemplate`
column that shows the shape SWIS expects for complex arguments, which is the reliable way
to find out:

```sql
SELECT
    a.EntityName,
    a.VerbName,
    a.Position,
    a.Name AS ArgumentName,
    a.Type,
    a.XmlTemplate
FROM Metadata.VerbArgument a
WHERE a.EntityName = 'Orion.HardwareHealth.HardwareItemBase'
  AND a.VerbName = 'EnableSensors'
ORDER BY a.Position
```

`SetThreshold` and `ClearThresholds` are simpler: the first takes one sensor `ID` and two
threshold strings, the second takes an array of sensor IDs.

## Worked queries

Every query below has been validated against the 2026.2 schema with
`tools/validate_swql.py`.

### Every failing sensor, with the node it belongs to

This is the query most operators actually want. It joins the sensor back to its node
through the `Node` navigation property on `Orion.HardwareHealth.HardwareItem`, joins
`Orion.StatusInfo` so the status reads as a word, and excludes the three states that look
like failures but are not: `Unknown` (status 0, never polled), disabled sensors, and
sensors that have been removed from the hardware.

```sql
SELECT
    hi.Node.Caption AS NodeName,
    hi.HardwareCategory.Name AS CategoryName,
    hi.Name AS SensorName,
    s.StatusName,
    hi.Value,
    hi.HardwareUnitDescription,
    hi.OriginalStatus,
    hi.Message
FROM Orion.HardwareHealth.HardwareItem hi
JOIN Orion.StatusInfo s ON hi.Status = s.StatusId
WHERE hi.Status NOT IN (0, 1)
  AND hi.UnManaged = FALSE
  AND hi.IsDisabled = FALSE
  AND hi.IsDeleted = FALSE
ORDER BY s.Ranking, hi.Node.Caption, hi.Name
```

`ORDER BY s.Ranking` puts the worst first, because the raw `Status` integers are not
ordered by severity while `Orion.StatusInfo.Ranking` is.

### Count failures by sensor category

Grouping on the category name rather than the ID makes the result readable and portable
between servers, since the IDs are per-installation. This is the query to run first when
something is wrong across a fleet: a spike concentrated in one category usually means a
batch of identical hardware or one bad firmware level, not thirty unrelated faults.

```sql
SELECT
    hi.HardwareCategory.Name AS CategoryName,
    COUNT(hi.ID) AS FailingSensors
FROM Orion.HardwareHealth.HardwareItem hi
WHERE hi.Status NOT IN (0, 1)
  AND hi.UnManaged = FALSE
  AND hi.IsDisabled = FALSE
  AND hi.IsDeleted = FALSE
GROUP BY hi.HardwareCategory.Name
ORDER BY COUNT(hi.ID) DESC
```

### The per-category rollup, one row per node per category

`Orion.HardwareHealth.HardwareCategoryStatus` is the middle level, and it is much cheaper
to scan than the sensor table when you only need to know which nodes have a problem
somewhere. `ItemsWithProblems` names the offending sensors without a second query.

```sql
SELECT
    cs.Node.Caption AS NodeName,
    cs.HardwareCategoryName,
    s.StatusName,
    cs.ItemsWithProblems,
    cs.StatusDescription
FROM Orion.HardwareHealth.HardwareCategoryStatus cs
JOIN Orion.StatusInfo s ON cs.Status = s.StatusId
WHERE cs.Status NOT IN (0, 1)
ORDER BY s.Ranking, cs.Node.Caption
```

### Hardware inventory, and nodes whose hardware poll is failing

`Orion.HardwareHealth.HardwareInfo` is the per-node summary. Ordering by `LastPollTime`
ascending surfaces the nodes that have stopped reporting at all, which is a different and
often more urgent problem than a sensor reading badly.

```sql
SELECT TOP 100
    hwi.Node.Caption AS NodeName,
    hwi.Manufacturer,
    hwi.Model,
    hwi.ServiceTag,
    hwi.PollingMethod,
    hwi.LastPollTime,
    hwi.LastPollMessage,
    hwi.CategoriesWithProblems
FROM Orion.HardwareHealth.HardwareInfo hwi
WHERE hwi.IsDisabled = FALSE
ORDER BY hwi.LastPollTime
```

### Sensors in one category with their configured thresholds

Pass the category name you found from the category list above. This is how you audit
whether the fan or temperature thresholds actually got set, rather than assuming the
defaults are in place.

```sql
SELECT
    hi.Node.Caption AS NodeName,
    hi.Name AS SensorName,
    hi.Value,
    hi.HardwareUnitDescription,
    hi.HardwareItemThreshold.Warning,
    hi.HardwareItemThreshold.Critical
FROM Orion.HardwareHealth.HardwareItem hi
WHERE hi.HardwareCategory.Name = @categoryName
  AND hi.IsDisabled = FALSE
ORDER BY hi.Value DESC
```

### One sensor's value over the last week

Note the explicit join instead of dot-walking from the statistics row. The statistics
entity navigates to `HardwareItemBase`, which has no `Node`, so
`st.HardwareItem.Node.Caption` does not resolve. Joining `Orion.HardwareHealth.HardwareItem`
on `ID` gets you the subtype that does.

```sql
SELECT
    hi.Node.Caption AS NodeName,
    hi.Name AS SensorName,
    st.ObservationTimestamp,
    st.MinValue,
    st.AvgValue,
    st.MaxValue
FROM Orion.HardwareHealth.HardwareItemValueStatistics st
JOIN Orion.HardwareHealth.HardwareItem hi ON hi.ID = st.HardwareItemID
WHERE st.HardwareItemID = @sensorId
  AND st.ObservationTimestamp >= AddDay(-7, GetDate())
ORDER BY st.ObservationTimestamp
```

### BMC fans and power supplies

`Status` here is a string, so there is no `Orion.StatusInfo` join and no numeric
comparison. `ParentTypeDescription` tells you whether the part belongs to a chassis or
directly to a node.

```sql
SELECT
    f.Node.Caption AS NodeName,
    f.Name AS FanName,
    f.Status AS FanStatus,
    f.Power,
    f.Model,
    f.ParentTypeDescription
FROM Orion.HardwareHealth.BMC.Fans f
ORDER BY f.Node.Caption, f.Name
```

```sql
SELECT
    p.Node.Caption AS NodeName,
    p.Name AS PsuName,
    p.Status AS PsuStatus,
    p.Power,
    p.Model,
    p.ParentTypeDescription
FROM Orion.HardwareHealth.BMC.PSUs p
ORDER BY p.Node.Caption, p.Name
```

### Chassis with the blades installed in them

```sql
SELECT
    ch.Name AS ChassisName,
    ch.Model,
    ch.SerialNumber,
    ch.Status,
    ch.Controller.Name AS ControllerName,
    ch.Blades.Name AS BladeName,
    ch.Blades.Status AS BladeStatus
FROM Orion.HardwareHealth.BMC.Chassis ch
ORDER BY ch.Name
```

### Walking from the node side

`Orion.Nodes` navigates to hardware health three ways, and all three are usable in a query.
This is the shape to use when you already have a node-centred query and want to add
hardware columns to it.

```sql
SELECT TOP 50
    n.Caption AS NodeName,
    n.HardwareHealthInfos.Manufacturer,
    n.HardwareHealthInfos.Model,
    n.HardwareHealthInfos.LastPollStatus,
    n.HardwareHealthInfos.LastPollMessage
FROM Orion.Nodes n
WHERE n.HardwareHealthInfos.LastPollStatus <> 0
ORDER BY n.Caption
```

The other two are `n.HardwareCategoryStatus` and `n.HardwareItems`.

## Gotchas

**The statistics entities cannot reach a node.** `HardwareItemValueStatistics.HardwareItem`
navigates to `Orion.HardwareHealth.HardwareItemBase`, which has no `Node` property, because
a base row might belong to a chassis or a storage array. Join
`Orion.HardwareHealth.HardwareItem` on `ID` instead. This is the error the validator in this
repository catches most often on hardware health queries.

**`Status` is a string on four of the six BMC entities.** `Fans`, `PSUs`, `Blades` and
`Racks` type it as `System.String`; `Chassis` types it as `System.Int32`. Only the last one
joins `Orion.StatusInfo`.

**`show` under-reports these entities.** `Orion.HardwareHealth.HardwareItem` declares two
properties and inherits thirty-three. Always use `props` here, not `show`.

**Three separate flags mean "not a real failure".** A row can be `UnManaged` (in a
maintenance window), `IsDisabled` (the sensor was switched off), or `IsDeleted` (the part
was removed but its row was kept). None is caught by a `Status` filter, and leaving any of
them out inflates a failure count.

**Status 0 is `Unknown`, not "fine".** It means the sensor has not been polled since it was
added or since it came out of an unmanaged state. Excluding it with `NOT IN (0, 1)` is
usually right for a failure report and usually wrong for a coverage report, where the
unknowns are exactly what you are looking for.

**`LastPollStatusName` is typed `System.Int32` despite the name.** It is not a string, and
it is not the same column as `LastPollStatus`. Both are integers on
`Orion.HardwareHealth.HardwareInfoBase`.

**`EnableHardwareHealth` names its second parameter `pollingmethod`, all lowercase.**
SolarWinds' documentation writes it `pollingMethod`. Positional callers are unaffected;
generated clients that bind by name are not.

**Category names are rows, not schema.** They can differ by version and by polling method.
List them from `Orion.HardwareHealth.HardwareCategory` before filtering on one.

**Account limitations silently filter results.** A restricted account querying sensors gets
a smaller set with no error, so an unexpectedly empty result is often a permissions problem
rather than a monitoring gap.

## See also

- [sam.md](sam.md) for Server and Application Monitor, one of the two modules that brings
  hardware health with it.
- [../platform/modules.md](../platform/modules.md) for the module and namespace map,
  including the note that this capability is attributed to "NPM / SAM".
- [../reference/status-codes.md](../reference/status-codes.md) for what each `Status`
  integer means.
- [../reference/netobject-types.md](../reference/netobject-types.md) for the NetObject
  prefixes: `HWH` for hardware, `HWHT` for a hardware type, `HWHS` for a sensor.
- [../reference/verb-index.md](../reference/verb-index.md) for every verb with parameters.
- SolarWinds:
  [Hardware Health](https://solarwinds.github.io/OrionSDK/docs/hardware-health/).

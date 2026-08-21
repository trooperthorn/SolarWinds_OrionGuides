# The SWQL cookbook

Sixty questions an operator actually asks, each with a short answer and a query that runs.
This page is indexed by the question rather than by the entity, because when you need a
number you usually know what you want to know and not which of the 2067 entities holds it.

Every query here was checked against the extracted 2026.2 schema with
`python3 tools/validate_swql.py`, so the entity names, property names and navigation
properties are known to exist rather than merely believed to. Whether a query returns rows
on your server is a different question, and the two things that decide it are covered under
[when a recipe returns nothing](#when-a-recipe-returns-nothing).

## Contents

| Section | Recipes |
|:---|:---|
| [Inventory and audit](#inventory-and-audit) | 1 to 8 |
| [Availability and outages](#availability-and-outages) | 9 to 16 |
| [Capacity](#capacity) | 17 to 23 |
| [Performance](#performance) | 24 to 29 |
| [Alerting and noise](#alerting-and-noise) | 30 to 36 |
| [Change and configuration](#change-and-configuration) | 37 to 41 |
| [Licensing](#licensing) | 42 to 45 |
| [Security posture](#security-posture) | 46 to 51 |
| [Housekeeping](#housekeeping) | 52 to 60 |

## How to run these

Paste one into SWQL Studio, or run it through a client. Parameters written as `@name` are
bound by the client rather than substituted into the text:

```powershell
Get-SwisData $swis 'SELECT NodeID, Caption FROM Orion.Nodes WHERE Vendor = @vendor' @{ vendor = 'Cisco' }
```

```python
swis.query("SELECT NodeID, Caption FROM Orion.Nodes WHERE Vendor = @vendor", vendor="Cisco")
```

If you have not connected yet, start at [getting-started.md](getting-started.md). The
longer, subject-grouped query files are in [../../scripts/swql/](../../scripts/swql/), and
several recipes below point at the file that has more of the same kind.

## Rules these queries follow

Each of these prevents a specific failure rather than being a house style:

- **Bounded result sets.** `TOP n`, or `WITH ROWS a TO b`. There is no `SELECT *` in SWQL
  and an unbounded query against a large installation is a real production risk. See
  [../swql/performance.md](../swql/performance.md#1-bound-every-result-set).
- **Bound parameters**, never string concatenation, so plans get reused and an injection
  class disappears.
- **Time bounds on anything historical.** Events, alert history and the statistics entities
  are the largest tables on the system.
- **Status resolved by joining `Orion.StatusInfo`** rather than by hard-coding integers, so
  the query stays correct if SolarWinds adds a status.
- **`UnManaged = FALSE`** when the question is "what is actually broken" rather than "what
  is in a maintenance window". `UnManaged` is inherited from `System.ManagedEntity` and is
  queryable on every managed object even though those entities do not declare it.
- **The right clock on each side of a time comparison.** A column whose name ends in `Utc`,
  such as `Orion.AuditingEvents.TimeLoggedUtc`, belongs next to `GetUtcDate()`.
  `Orion.Events.EventTime` documents itself as local time and belongs next to `GetDate()`.
  Most other date columns, including `Orion.AlertActive.TriggeredDateTime`,
  `Orion.AlertHistory.TimeStamp` and `Cirrus.ConfigArchive.DownloadTime`, carry **no
  documented timezone in the schema and are unverified here**: measure them once on your own
  server with the `MinuteDiff` probe in
  [../swql/date-and-time.md](../swql/date-and-time.md#measuring-a-columns-timezone) before
  writing a narrow window against them. Getting it backwards shifts the window by your
  offset, which returns nothing on a tight filter and the wrong hours on a loose one. The
  wide windows used below, seven days and thirty, are deliberately tolerant of that.

## Inventory and audit

### 1. What am I monitoring, and where is it?

The estate list. `Location` and `Contact` come from SNMP `sysLocation` and `sysContact`, so
they are only as good as the device configuration, which is itself a useful finding.

```sql
SELECT TOP 1000
    n.NodeID,
    n.Caption,
    n.IPAddress,
    n.DNS,
    n.Vendor,
    n.MachineType,
    n.Location,
    n.Contact,
    n.ObjectSubType,
    n.Engine.ServerName AS PolledBy
FROM Orion.Nodes n
ORDER BY n.Location, n.Caption
```

A ready-made export with custom properties included is
[../../scripts/powershell/Export-OrionInventory.ps1](../../scripts/powershell/Export-OrionInventory.ps1).

### 2. How many of each kind of device do I have?

The query to run before a hardware refresh conversation or a vendor negotiation.

```sql
SELECT
    n.Vendor,
    n.MachineType,
    COUNT(n.NodeID) AS NodeCount
FROM Orion.Nodes n
GROUP BY n.Vendor, n.MachineType
ORDER BY COUNT(n.NodeID) DESC
```

### 3. How is each node polled?

`ObjectSubType` distinguishes ICMP, SNMP, WMI and agent nodes. `SNMPVersion` only means
anything for the SNMP ones, which is why it is grouped alongside rather than filtered on.

```sql
SELECT
    n.ObjectSubType AS PollingMethod,
    n.SNMPVersion,
    COUNT(n.NodeID) AS NodeCount
FROM Orion.Nodes n
GROUP BY n.ObjectSubType, n.SNMPVersion
ORDER BY COUNT(n.NodeID) DESC
```

An ICMP-only node is monitored for up or down and nothing else, so a large ICMP count is
usually a finding rather than a design.

### 4. Which modules are actually installed on this server?

The schema depends on which modules are licensed and installed, so an entity that exists in
this repository may not exist on your server. Ask the server:

```sql
SELECT
    e.Namespace,
    COUNT(e.FullName) AS EntityCount
FROM Metadata.Entity e
WHERE e.IsInternal = FALSE
GROUP BY e.Namespace
ORDER BY COUNT(e.FullName) DESC
```

Namespace counts are a rough signal. To test for one module specifically, name its entities
and see which come back:

```sql
SELECT e.FullName, e.BaseType, e.CanCreate, e.CanInvoke
FROM Metadata.Entity e
WHERE e.FullName IN @names
ORDER BY e.FullName
```

Pass something like `['Orion.NPM.Interfaces', 'Orion.APM.Application', 'Cirrus.Nodes',
'Orion.SRM.Volumes', 'IPAM.Subnet']`. A name that is absent from the result is a module
that is absent from the server. More of this in
[../swis/metadata-introspection.md](../swis/metadata-introspection.md).

### 5. Everything monitored on one node, in one result

Interfaces, volumes and applications live in three entities, so this is a `UNION ALL` rather
than a join. Trying to reach all three by dot-walking from `Orion.Nodes` in a single `SELECT`
multiplies the rows together instead.

```sql
SELECT 'Interface' AS ObjectType, i.Caption AS ObjectName, i.Status, i.UnManaged
FROM Orion.NPM.Interfaces i
WHERE i.NodeID = @nodeId
UNION ALL
SELECT 'Volume' AS ObjectType, v.Caption AS ObjectName, v.Status, v.UnManaged
FROM Orion.Volumes v
WHERE v.NodeID = @nodeId
UNION ALL
SELECT 'Application' AS ObjectType, a.Name AS ObjectName, a.Status, a.UnManaged
FROM Orion.APM.Application a
WHERE a.NodeID = @nodeId
```

### 6. Which custom properties exist, and what do they apply to?

Custom properties are installation data rather than schema, so this repository cannot list
yours. The definitions are queryable, and this is where to start before writing anything
that depends on one.

```sql
SELECT
    cp.Table,
    cp.Field,
    cp.DataType,
    cp.MaxLength,
    cp.Mandatory,
    cp.Description,
    cp.TargetEntity
FROM Orion.CustomProperty cp
ORDER BY cp.Table, cp.Field
```

The values then live on the per-entity custom-property entity, reached through a navigation
property. Because the columns are created on your server, they cannot be validated here; the
shape is:

```text
SELECT n.Caption, n.CustomProperties.YourFieldName
FROM Orion.Nodes n
WHERE n.CustomProperties.YourFieldName IS NULL
```

Substitute a `Field` value from the first query. Full treatment in
[../automation/custom-properties.md](../automation/custom-properties.md).

### 7. What is in each group?

A group is a container, and membership rows identify a member by entity type plus primary
id rather than by a typed foreign key, because a member can be any entity type.

```sql
SELECT
    cm.Container.Name AS GroupName,
    cm.Name AS MemberName,
    cm.MemberEntityType,
    cm.MemberPrimaryID,
    cm.Status AS MemberStatus
FROM Orion.ContainerMembers cm
ORDER BY cm.Container.Name, cm.Name
```

### 8. Which groups is one node in?

Match on both the entity type and the id. Matching on the id alone will happily return the
interface, volume or application that shares that number.

```sql
SELECT
    cm.Container.Name AS GroupName,
    cm.Name AS MemberName,
    cm.MemberEntityType
FROM Orion.ContainerMembers cm
WHERE cm.MemberEntityType = 'Orion.Nodes'
  AND cm.MemberPrimaryID = @nodeId
ORDER BY cm.Container.Name
```

## Availability and outages

### 9. What is down right now?

Status `2` is Down. Excluding unmanaged objects is what turns "not up" into "actually
broken", because an object in a maintenance window reports status `9` and would otherwise
pad the list.

```sql
SELECT
    n.NodeID,
    n.Caption,
    n.IPAddress,
    si.StatusName,
    n.Engine.ServerName AS PolledBy,
    n.DetailsUrl
FROM Orion.Nodes n
JOIN Orion.StatusInfo si ON n.Status = si.StatusId
WHERE n.Status = 2
  AND n.UnManaged = FALSE
ORDER BY n.Caption
```

### 10. Is this one outage or many?

The first question during an incident. If everything down is on one polling engine, the
engine is the problem and the devices are probably fine.

```sql
SELECT
    n.Engine.ServerName AS EngineName,
    COUNT(n.NodeID) AS DownNodes
FROM Orion.Nodes n
WHERE n.Status = 2
  AND n.UnManaged = FALSE
GROUP BY n.Engine.ServerName
ORDER BY COUNT(n.NodeID) DESC
```

Cross-check against the engines themselves with recipe 28. A stale keep-alive there and a
large count here are the same event seen from two sides.

### 11. Which interfaces are down but administratively up?

An interface that is admin-down was switched off deliberately and is not interesting. One
that is admin-up and operationally down is.

```sql
SELECT
    i.Node.Caption AS NodeName,
    i.Name,
    i.InterfaceAlias,
    i.AdminStatus,
    i.OperStatus,
    si.StatusName
FROM Orion.NPM.Interfaces i
JOIN Orion.StatusInfo si ON i.Status = si.StatusId
WHERE i.AdminStatus = 1
  AND i.OperStatus <> 1
  AND i.UnManaged = FALSE
ORDER BY i.Node.Caption, i.Name
```

### 12. Which applications are not up, and which component broke?

The application status tells you something is wrong; the component tells you what. There is
no direct navigation from `Orion.APM.Component` to a node, so the route is through the
application.

```sql
SELECT
    c.Application.Node.Caption AS NodeName,
    c.Application.Name AS ApplicationName,
    c.Name AS ComponentName,
    si.StatusName,
    c.StatusDescription
FROM Orion.APM.Component c
JOIN Orion.StatusInfo si ON c.Status = si.StatusId
WHERE c.Status <> 1
  AND c.Disabled = FALSE
  AND c.UnManaged = FALSE
ORDER BY si.Ranking, c.Application.Node.Caption, c.ComponentOrder
```

### 13. What changed state in the last hour?

`Orion.Events` records what the platform observed. `EventTime` is local, so it is compared
against `GetDate()`.

```sql
SELECT TOP 200
    e.EventTime,
    et.Name AS EventTypeName,
    e.NetObjectValue,
    e.Message
FROM Orion.Events e
JOIN Orion.EventTypes et ON e.EventType = et.EventType
WHERE e.EventTime > AddHour(-1, GetDate())
ORDER BY e.EventTime DESC
```

Read the event type catalogue once before filtering on a name, because the set depends on
which modules are installed:

```sql
SELECT et.EventType, et.Name, et.OrionFeatureName
FROM Orion.EventTypes et
ORDER BY et.Name
```

### 14. Which nodes flap?

Count events of one type per node over a week. Ten node-down events on one device is a
different problem from one, and it is the difference between a fault and a link.

```sql
SELECT TOP 25
    e.Nodes.Caption AS NodeName,
    COUNT(e.EventID) AS Occurrences
FROM Orion.Events e
JOIN Orion.EventTypes et ON e.EventType = et.EventType
WHERE e.EventTime > AddDay(-7, GetDate())
  AND et.Name = @eventTypeName
GROUP BY e.Nodes.Caption
ORDER BY COUNT(e.EventID) DESC
```

`Orion.Events` navigates to nodes through a property called `Nodes`, which is plural even
though it resolves to a single node.

### 15. What was availability over a window?

`Orion.ResponseTime` is a statistics entity, and statistics rows do not all cover the same
span of time: `Weight` is the number of seconds a row represents. A plain average over a
window that mixes detail rows with rolled-up rows is therefore wrong, and wrong in a
direction that flatters recent data. Weight it.

```sql
SELECT TOP 50
    rt.Node.Caption AS NodeName,
    Round(Sum(rt.Availability * rt.Weight) / Sum(rt.Weight), 3) AS AvailabilityPercent,
    Sum(rt.Weight) AS SecondsCovered
FROM Orion.ResponseTime rt
WHERE rt.DateTime >= @start
  AND rt.DateTime <  @end
GROUP BY rt.Node.Caption
ORDER BY Sum(rt.Availability * rt.Weight) / Sum(rt.Weight)
```

`SecondsCovered` is there as a sanity check. If it is far short of the window you asked for,
the node was not being polled for part of it and the percentage is an average of a smaller
window than you think. Background in
[../swql/gotchas.md](../swql/gotchas.md#7-averaging-statistics-rows-without-weight).

### 16. Which volumes stopped responding?

`VolumeResponding` is a character column holding `Y` or `N`, not a boolean, which is one of
several columns on the platform that look boolean and are not.

```sql
SELECT
    v.Node.Caption AS NodeName,
    v.Caption AS VolumeName,
    v.VolumeResponding,
    si.StatusName,
    v.MinutesSinceLastSync
FROM Orion.Volumes v
JOIN Orion.StatusInfo si ON v.Status = si.StatusId
WHERE v.VolumeResponding = 'N'
  AND v.UnManaged = FALSE
ORDER BY v.Node.Caption, v.Caption
```

## Capacity

### 17. Which disks are about to fill?

The most requested report on the platform. `VolumeType` matters: filtering to `Fixed Disk`
keeps swap files, RAM disks and mount points out of a capacity conversation.

```sql
SELECT
    v.Node.Caption AS NodeName,
    v.Caption AS VolumeName,
    Round(v.VolumePercentUsed, 1) AS PercentUsed,
    Round(v.VolumeSize / 1073741824, 2) AS SizeGB,
    Round(v.VolumeSpaceAvailable / 1073741824, 2) AS FreeGB
FROM Orion.Volumes v
WHERE v.VolumePercentUsed > 85
  AND v.VolumeType = 'Fixed Disk'
  AND v.UnManaged = FALSE
ORDER BY v.VolumePercentUsed DESC
```

Check what volume types your installation actually uses before trusting the filter:
`SELECT v.VolumeType, COUNT(v.VolumeID) AS VolumeCount FROM Orion.Volumes v GROUP BY v.VolumeType`.

### 18. How long until they fill?

Percentage used answers "is it nearly full". Capacity forecasting answers "when", which is
the number a change request needs. `Orion.VolumesForecastCapacity` inherits its columns from
`Orion.ForecastCapacity`, so `DaysToCapacityAvg` resolves on it even though the entity
declares only three properties of its own.

```sql
SELECT TOP 25
    f.InstanceCaption,
    f.MetricName,
    Round(f.CurrentValue, 1) AS CurrentValue,
    Round(f.DaysToWarningAvg, 0) AS DaysToWarning,
    Round(f.DaysToCapacityAvg, 0) AS DaysToFull,
    f.DetailsUrl
FROM Orion.VolumesForecastCapacity f
WHERE f.DaysToCapacityAvg > 0
ORDER BY f.DaysToCapacityAvg
```

The `Avg` and `Peak` variants of each column are two different projections, fitted to the
average and to the peak series. Quote the average for planning and the peak for risk.

### 19. Which interfaces are running hot?

`PercentUtil` is the higher of the two directions, which is what you want for a saturation
question. Keep the two directions in the result anyway, because a link that is hot in one
direction only is a different conversation from one that is hot in both.

```sql
SELECT TOP 50
    i.Node.Caption AS NodeName,
    i.Name,
    i.InterfaceAlias,
    Round(i.InPercentUtil, 1) AS InPercent,
    Round(i.OutPercentUtil, 1) AS OutPercent,
    i.InterfaceSpeed
FROM Orion.NPM.Interfaces i
WHERE i.PercentUtil > 70
  AND i.UnManaged = FALSE
ORDER BY i.PercentUtil DESC
```

### 20. What is the total storage footprint?

The one-row answer for a capacity review. Divide by `1099511627776` for terabytes.

```sql
SELECT
    COUNT(v.VolumeID) AS VolumeCount,
    Round(SUM(v.VolumeSize) / 1099511627776, 2) AS TotalTB,
    Round(SUM(v.VolumeSpaceUsed) / 1099511627776, 2) AS UsedTB,
    Round(SUM(v.VolumeSpaceAvailable) / 1099511627776, 2) AS FreeTB
FROM Orion.Volumes v
WHERE v.VolumeType = 'Fixed Disk'
```

Remember that this total is scoped to what your account may see. Two accounts get two
different answers, legitimately.

### 21. Which nodes are short of memory or CPU headroom?

Current values, which answer "right now". For "all week", use recipe 25.

```sql
SELECT TOP 50
    n.Caption,
    n.CPUCount,
    n.CPULoad,
    n.PercentMemoryUsed,
    Round(n.TotalMemory / 1073741824, 1) AS TotalMemoryGB,
    n.Engine.ServerName AS PolledBy
FROM Orion.Nodes n
WHERE (n.CPULoad > 85 OR n.PercentMemoryUsed > 90)
  AND n.UnManaged = FALSE
ORDER BY n.PercentMemoryUsed DESC, n.CPULoad DESC
```

### 22. Which datastores are running out?

Virtualization capacity, which usually bites before guest disks do because it is shared.
`DepletionDate` is the platform's own projection.

```sql
SELECT TOP 25
    ds.Name AS Datastore,
    Round(ds.Capacity / 1099511627776.0, 2) AS CapacityTB,
    Round(ds.FreeSpace / 1099511627776.0, 2) AS FreeTB,
    Round(ds.SpaceUtilization, 1) AS PercentUsed,
    Round(ds.ProvisionedSpaceAllocation, 1) AS PercentProvisioned,
    ds.DepletionDate
FROM Orion.VIM.Datastores ds
WHERE ds.SpaceUtilization > 80
  AND ds.Accessible = TRUE
  AND ds.UnManaged = FALSE
ORDER BY ds.SpaceUtilization DESC
```

`ProvisionedSpaceAllocation` above 100 means thin provisioning has promised more than the
datastore holds, which is normal until it is not. Inaccessible datastores are excluded
because they report stale capacity, and a datastore that has gone inaccessible deserves its
own alert rather than a line in a capacity report.

### 23. Where is peak traffic against provisioned speed?

Average utilization hides bursts. Peak against the link speed is the number that decides an
upgrade.

```sql
SELECT TOP 50
    i.Node.Caption AS NodeName,
    i.Name,
    i.InterfaceSpeed,
    i.MaxInBpsToday,
    i.MaxInBpsTime,
    i.MaxOutBpsToday,
    i.MaxOutBpsTime
FROM Orion.NPM.Interfaces i
WHERE i.InterfaceSpeed > 0
ORDER BY i.MaxInBpsToday DESC
```

## Performance

### 24. Which nodes are slow or losing packets?

Latency and loss together, because either alone produces a misleading list.

```sql
SELECT TOP 50
    n.Caption,
    n.IPAddress,
    n.ResponseTime,
    n.AvgResponseTime,
    n.MaxResponseTime,
    n.PercentLoss,
    n.Engine.ServerName AS PolledBy
FROM Orion.Nodes n
WHERE (n.PercentLoss > 0 OR n.AvgResponseTime > 200)
  AND n.UnManaged = FALSE
ORDER BY n.PercentLoss DESC, n.AvgResponseTime DESC
```

If the slow nodes are all on one engine, you are looking at the poller and not at the
network. Recipe 28 settles it.

### 25. Which nodes ran hot all week?

The same weighting rule as recipe 15: `Weight` is the seconds a statistics row covers, and
an unweighted average over a mixed window is wrong.

```sql
SELECT TOP 25
    c.Node.Caption AS NodeName,
    Round(Sum(c.AvgLoad * c.Weight) / Sum(c.Weight), 1) AS WeightedAvgCpu,
    Max(c.MaxLoad) AS PeakCpu,
    Round(Sum(c.AvgPercentMemoryUsed * c.Weight) / Sum(c.Weight), 1) AS WeightedAvgMemory
FROM Orion.CPULoad c
WHERE c.DateTime >= @start
  AND c.DateTime <  @end
GROUP BY c.Node.Caption
ORDER BY Sum(c.AvgLoad * c.Weight) / Sum(c.Weight) DESC
```

A half-open window, `>=` and `<`, rather than `BETWEEN`. It composes: consecutive windows
neither overlap nor leave a gap.

### 26. Which interfaces are erroring?

Errors and discards usually precede a user complaint by a day or so, which makes this the
most useful proactive query NPM offers.

```sql
SELECT TOP 50
    i.Node.Caption AS NodeName,
    i.Name,
    i.InErrorsToday,
    i.OutErrorsToday,
    i.InDiscardsToday,
    i.OutDiscardsToday,
    i.CRCAlignErrorsToday
FROM Orion.NPM.Interfaces i
WHERE i.InErrorsToday > 0
   OR i.OutErrorsToday > 0
   OR i.InDiscardsToday > 0
   OR i.OutDiscardsToday > 0
ORDER BY i.InErrorsToday + i.OutErrorsToday DESC
```

The classic cause of "slow but not down" is a duplex mismatch, which is its own query:

```sql
SELECT
    i.Node.Caption AS NodeName,
    i.Name,
    i.DuplexMode,
    i.InterfaceSpeed
FROM Orion.NPM.Interfaces i
WHERE i.DuplexMode = 2
ORDER BY i.Node.Caption
```

### 27. Which application components fail most often?

Component-level failure counts, so you can tell a flaky check from a broken service.

```sql
SELECT TOP 50
    c.Application.Node.Caption AS NodeName,
    c.Application.Name AS ApplicationName,
    c.Name AS ComponentName,
    c.ComponentType,
    si.StatusName,
    c.StatusDescription
FROM Orion.APM.Component c
JOIN Orion.StatusInfo si ON c.Status = si.StatusId
WHERE c.Status <> 1
  AND c.Disabled = FALSE
ORDER BY c.Application.Node.Caption, c.Application.Name, c.ComponentOrder
```

### 28. Which polling engines are behind?

`PollingCompletion` below 100 means the engine could not finish its cycle in the time
available, which shows up to everyone else as stale data rather than as an error.

```sql
SELECT
    e.ServerName,
    e.ServerType,
    e.PollingCompletion,
    e.Elements,
    e.LicensedElements,
    e.AvgCPUUtil,
    e.MemoryUtil,
    e.MinutesSinceKeepAlive
FROM Orion.Engines e
WHERE e.PollingCompletion < 100
   OR e.MinutesSinceKeepAlive > 5
ORDER BY e.PollingCompletion
```

A stale keep-alive usually means the service is stopped, which is a different problem from a
loaded engine and needs a different fix.

### 29. Which nodes are skipping polls?

The per-node view of the same problem.

```sql
SELECT TOP 50
    n.Caption,
    n.Engine.ServerName AS EngineName,
    n.PollInterval,
    n.NextPoll,
    n.SkippedPollingCycles,
    n.MinutesSinceLastSync
FROM Orion.Nodes n
WHERE n.SkippedPollingCycles > 0
  AND n.UnManaged = FALSE
ORDER BY n.SkippedPollingCycles DESC
```

## Alerting and noise

The alerting model has four parts and confusing them is the usual reason an alert query
returns nothing. `Orion.AlertConfigurations` is the definition. `Orion.AlertObjects` is one
row per definition-and-entity pair, and is the only place that knows what an alert is about.
`Orion.AlertActive` is one row per currently firing alert. `Orion.AlertHistory` is the audit
trail. Almost every useful query goes through `Orion.AlertObjects`.

### 30. What is firing right now?

```sql
SELECT
    aa.AlertActiveID,
    ao.AlertObjectID,
    ao.AlertConfigurations.Name AS AlertName,
    ao.AlertConfigurations.Severity,
    ao.EntityCaption AS TriggeringObject,
    ao.EntityType,
    ao.RelatedNodeCaption AS NodeName,
    aa.TriggeredDateTime,
    aa.Acknowledged
FROM Orion.AlertActive aa
JOIN Orion.AlertObjects ao ON aa.AlertObjectID = ao.AlertObjectID
ORDER BY ao.AlertConfigurations.Severity DESC, aa.TriggeredDateTime DESC
```

`AlertObjectID` is selected rather than only joined on, because it is the argument every
alert verb takes. `Orion.AlertActive.Acknowledge` wants `AlertObjectID` values and not
`AlertActiveID` values, despite living on `Orion.AlertActive`; see
[../automation/alerts.md](../automation/alerts.md#pass-alertobjectid-not-alertactiveid).

### 31. What is unacknowledged and old?

The triage list, with the age computed both ways because
`Orion.AlertActive.TriggeredDateTime` carries no documented timezone in the schema and is
therefore unverified here.

```sql
SELECT
    ao.AlertConfigurations.Name AS AlertName,
    ao.EntityCaption AS TriggeringObject,
    ao.RelatedNodeCaption AS NodeName,
    aa.TriggeredDateTime,
    HourDiff(aa.TriggeredDateTime, GetUtcDate()) AS AgeHoursIfUtc,
    HourDiff(aa.TriggeredDateTime, GetDate()) AS AgeHoursIfLocal
FROM Orion.AlertActive aa
JOIN Orion.AlertObjects ao ON aa.AlertObjectID = ao.AlertObjectID
WHERE aa.Acknowledged = FALSE
ORDER BY aa.TriggeredDateTime
```

Look at a row you know the age of. Whichever of the two age columns is plausible identifies
the clock the column is stored on, and the other is off by your UTC offset. Once you know,
add the filter with the matching function, `AND aa.TriggeredDateTime < AddDay(-1,
GetUtcDate())` or the `GetDate()` form, and drop the column you do not need.

### 32. Which alert definitions produce the most noise?

Counting active instances tells you what is loud now. Counting history entries over a week
tells you what is loud in general, which is the number that justifies changing a threshold.

```sql
SELECT TOP 25
    ah.AlertObjects.AlertConfigurations.Name AS AlertName,
    COUNT(ah.AlertHistoryID) AS HistoryEntries
FROM Orion.AlertHistory ah
WHERE ah.TimeStamp > AddDay(-7, GetDate())
GROUP BY ah.AlertObjects.AlertConfigurations.Name
ORDER BY COUNT(ah.AlertHistoryID) DESC
```

History records triggers, acknowledgements, resets and notes together, so a high count is
"this alert generates work" rather than strictly "this alert fires often". Split it by
`ah.EventType` when you need the distinction.

`Orion.AlertHistory.TimeStamp` has the same undocumented timezone as `TriggeredDateTime`
above, which a seven-day window absorbs. Narrow the window and you need to know which clock
it is on first.

### 33. Which definitions never fire?

An enabled alert that has never triggered is either well-tuned or broken, and the two are
indistinguishable until you look. It is worth a periodic review because a broken definition
is silent by construction.

```sql
SELECT
    ac.AlertID,
    ac.Name,
    ac.ObjectType,
    ac.Severity,
    ac.LastEdit,
    ac.CreatedBy
FROM Orion.AlertConfigurations ac
WHERE ac.Enabled = TRUE
  AND NOT EXISTS (
      SELECT ao.AlertObjectID
      FROM Orion.AlertObjects ao
      WHERE ao.AlertID = ac.AlertID
        AND ao.TriggeredCount > 0
  )
ORDER BY ac.Name
```

### 34. Which definitions are switched off?

The usual answer to "why did nobody get paged".

```sql
SELECT
    ac.AlertID,
    ac.Name,
    ac.ObjectType,
    ac.Severity,
    ac.LastEdit,
    ac.CreatedBy
FROM Orion.AlertConfigurations ac
WHERE ac.Enabled = FALSE
ORDER BY ac.LastEdit DESC
```

Ordering by `LastEdit` puts the recently disabled ones at the top, which is where the
interesting ones usually are.

### 35. Are alerts firing on objects nobody is polling?

An alert on an unmanaged object is noise by definition, and a signal that someone unmanaged
an object without suppressing its alerts. `Orion.AlertObjects` has a declared navigation to
`System.ManagedEntity`, so the inherited `UnManaged` flag is reachable directly.

```sql
SELECT
    ao.AlertConfigurations.Name AS AlertName,
    ao.EntityCaption,
    ao.EntityType,
    ao.ManagedEntity.UnManageUntil AS WindowEnds,
    aa.TriggeredDateTime
FROM Orion.AlertActive aa
JOIN Orion.AlertObjects ao ON aa.AlertObjectID = ao.AlertObjectID
WHERE ao.ManagedEntity.UnManaged = TRUE
ORDER BY aa.TriggeredDateTime DESC
```

The fix is usually `Orion.AlertSuppression` rather than unmanage; see
[../automation/maintenance-mode.md](../automation/maintenance-mode.md).

### 36. Who acknowledged what?

```sql
SELECT
    ao.AlertConfigurations.Name AS AlertName,
    ao.EntityCaption AS TriggeringObject,
    aa.AcknowledgedBy,
    aa.AcknowledgedDateTime,
    aa.AcknowledgedNote
FROM Orion.AlertActive aa
JOIN Orion.AlertObjects ao ON aa.AlertObjectID = ao.AlertObjectID
WHERE aa.Acknowledged = TRUE
ORDER BY aa.AcknowledgedDateTime DESC
```

More alert queries, including history by event type and per-node views, are in
[../../scripts/swql/05-alerts.swql](../../scripts/swql/05-alerts.swql).

## Change and configuration

### 37. Who changed what?

`Orion.Events` records what the platform observed. `Orion.AuditingEvents` records what a
person or an API client did, and it is the one you want when the question is "why did this
change". `TimeLoggedUtc` is UTC.

```sql
SELECT TOP 200
    a.TimeLoggedUtc,
    a.AccountID,
    a.AuditEventMessage,
    a.NetObjectType,
    a.NetObjectID,
    a.NetworkNode
FROM Orion.AuditingEvents a
WHERE a.TimeLoggedUtc > AddDay(-7, GetUtcDate())
ORDER BY a.TimeLoggedUtc DESC
```

Change volume per account, which is the version to graph:

```sql
SELECT
    a.AccountID,
    COUNT(a.AuditEventID) AS ChangeCount
FROM Orion.AuditingEvents a
WHERE a.TimeLoggedUtc > AddDay(-30, GetUtcDate())
GROUP BY a.AccountID
ORDER BY COUNT(a.AuditEventID) DESC
```

### 38. Which alert definitions were edited recently?

Pair this with recipe 34 after any incident where an alert did not fire.

```sql
SELECT
    ac.AlertID,
    ac.Name,
    ac.Enabled,
    ac.Severity,
    ac.LastEdit,
    ac.CreatedBy
FROM Orion.AlertConfigurations ac
WHERE ac.LastEdit > AddDay(-30, GetDate())
ORDER BY ac.LastEdit DESC
```

### 39. Which device configs changed in the last week?

NCM keeps its own node table. `Cirrus.Nodes.NodeID` is an NCM GUID and `CoreNodeID` is the
link back to the platform node, so a config row joins to `Cirrus.Nodes` on the GUID and to
`Orion.Nodes` on the integer. Joining the wrong one is the most common NCM query mistake.

```sql
SELECT TOP 200
    cn.NodeCaption,
    ca.ConfigType,
    ca.ConfigTitle,
    ca.DownloadTime,
    ca.Baseline
FROM Cirrus.ConfigArchive ca
JOIN Cirrus.Nodes cn ON ca.NodeID = cn.NodeID
WHERE ca.DownloadTime > AddDay(-7, GetDate())
ORDER BY ca.DownloadTime DESC
```

Never select the `Config` column into a report or a log without meaning to. Device configs
contain credentials.

### 40. Which devices have no recent config backup?

The archive is only as good as the last download, and a device NCM cannot log into stops
being backed up silently.

```sql
SELECT
    cn.NodeCaption,
    cn.AgentIP,
    cn.LoginStatus,
    cn.LastInventory,
    cn.ConnectionProfile
FROM Cirrus.Nodes cn
WHERE NOT EXISTS (
    SELECT ca.ConfigID
    FROM Cirrus.ConfigArchive ca
    WHERE ca.NodeID = cn.NodeID
      AND ca.DownloadTime > AddDay(-7, GetDate())
)
ORDER BY cn.NodeCaption
```

`LoginStatus` is the first thing to read on a row that comes back. More in
[../modules/ncm.md](../modules/ncm.md).

### 41. What did the last discovery jobs do?

```sql
SELECT TOP 50
    dl.DiscoveryLogID,
    dl.Profile.Name AS ProfileName,
    dl.FinishedTimeStamp,
    dl.AutoImport,
    dl.Result,
    dl.ResultDescription,
    dl.ErrorMessage
FROM Orion.DiscoveryLogs dl
ORDER BY dl.FinishedTimeStamp DESC
```

Reading `Orion.DiscoveryLogs` requires `manageNodes` even though it is a read, so an empty
result from a low-privilege account is a permission answer. Full treatment in
[../automation/discovery.md](../automation/discovery.md).

## Licensing

### 42. How much licence headroom is left per engine?

Elements, not nodes, are what a licence counts. This is the number to check before adding
monitoring rather than after.

```sql
SELECT
    e.ServerName,
    e.ServerType,
    e.Elements,
    e.LicensedElements,
    e.LicensedElements - e.Elements AS Headroom,
    Round((e.Elements * 100.0) / e.LicensedElements, 1) AS PercentUsed
FROM Orion.Engines e
WHERE e.LicensedElements > 0
ORDER BY e.Elements DESC
```

Estate totals, for a renewal conversation:

```sql
SELECT
    COUNT(e.EngineID) AS EngineCount,
    SUM(e.Nodes) AS TotalNodes,
    SUM(e.Interfaces) AS TotalInterfaces,
    SUM(e.Volumes) AS TotalVolumes,
    SUM(e.Elements) AS TotalElements,
    SUM(e.LicensedElements) AS TotalLicensedElements
FROM Orion.Engines e
```

### 43. What is the licence saturation by element type?

`Orion.LicenseSaturation` gives the current position per element type in one short table,
including the overage allowance where one applies.

```sql
SELECT
    ls.ElementType,
    ls.ElementCount,
    ls.MaxCount,
    ls.AvailableCount,
    Round(ls.Saturation, 1) AS SaturationPercent,
    ls.MaxCountWithOverage,
    ls.AvailableCountWithOverage
FROM Orion.LicenseSaturation ls
ORDER BY ls.Saturation DESC
```

The historical version, for a trend rather than a snapshot:

```sql
SELECT TOP 200
    us.Timestamp,
    us.LicenseElement.ElementType AS ElementType,
    us.Used,
    us.LicenseSize,
    us.Remaining,
    Round(us.Saturation, 1) AS SaturationPercent,
    us.HasOverage
FROM Orion.Licensing.UtilizationSummary us
WHERE us.Timestamp > AddDay(-30, GetDate())
ORDER BY us.Timestamp DESC
```

`Orion.Licensing.UtilizationSummary` restricts `read` to `admin`, so a service account gets
an empty result from that second query even though the query is correct.
`Orion.LicenseSaturation` declares no entity-level access control at all, which is why the
first one is the more portable of the two.

### 44. When do the licences and maintenance expire?

```sql
SELECT
    l.ProductName,
    l.LicenseName,
    l.LicenseType,
    l.LicenseExpiresOn,
    l.MaintenanceExpiresOn,
    l.IsTempKey,
    l.IsSubscription
FROM Orion.Licensing.Licenses l
ORDER BY l.MaintenanceExpiresOn
```

`Orion.Licensing.Licenses` restricts both `read` and `invoke` to `admin`, so this is one of
the few recipes here that a read-only service account cannot run. It also carries a
`LicenseKey` column. Leave that out of anything you export or paste.

Evaluation licences and their remaining days sit on the engines instead:

```sql
SELECT
    e.ServerName,
    e.Evaluation,
    e.EvalDaysLeft,
    e.PackageName,
    e.LicensedElements
FROM Orion.Engines e
WHERE e.Evaluation = TRUE
ORDER BY e.EvalDaysLeft
```

### 45. Which nodes consume the most interface elements?

Interfaces are usually the largest element category, and they accumulate without anyone
deciding to add them.

```sql
SELECT TOP 50
    n.Caption,
    COUNT(i.InterfaceID) AS MonitoredInterfaces
FROM Orion.Nodes n
JOIN Orion.NPM.Interfaces i ON i.NodeID = n.NodeID
GROUP BY n.Caption
ORDER BY COUNT(i.InterfaceID) DESC
```

## Security posture

### 46. Which nodes still use SNMPv1 or v2c?

Both send the community string in clear text on every poll. This is the shortest useful
security query on the platform.

```sql
SELECT
    n.Caption,
    n.IPAddress,
    n.SNMPVersion,
    n.Engine.ServerName AS PolledBy
FROM Orion.Nodes n
WHERE n.ObjectSubType = 'SNMP'
  AND n.SNMPVersion < 3
ORDER BY n.Caption
```

`Orion.Nodes` also has `Community` and `RWCommunity` columns. Do not select them. A report
that includes them turns a monitoring export into a credential leak, and the read-write one
is worse than the read-only one.

### 47. Who has admin?

Administrative access accumulates and nothing removes it for you, so this is a query to run
on a schedule rather than during an audit.

```sql
SELECT
    a.AccountID,
    a.AccountType,
    a.Enabled,
    a.LastLogin,
    a.Expires,
    a.LockoutTime,
    a.PasswordExpirationDate
FROM Orion.Accounts a
WHERE a.AllowAdmin = 'Y'
ORDER BY a.AccountID
```

Rights read back as the strings `Y` and `N`, so the filter compares against `'Y'` and not
against `TRUE`. An account with `AllowAdmin = 'Y'` and `Enabled = 'N'` is a dormant admin,
which is a finding and not a comfort, because enabling it is one click. A `Y` on a row whose
`AccountType` marks a directory group is not one administrator, it is however many people
are in that group.

### 48. Which accounts are dormant?

```sql
SELECT
    a.AccountID,
    a.AccountType,
    a.Enabled,
    a.LastLogin,
    a.AllowAdmin,
    a.AllowNodeManagement,
    a.AllowUnmanage
FROM Orion.Accounts a
WHERE a.LastLogin < AddDay(-90, GetDate())
ORDER BY a.LastLogin
```

### 49. Which accounts see less than the whole estate?

Account limitations are the first half of "why does this account see fewer rows than I do".
An account carries up to three, in three separate columns.

```sql
SELECT
    a.AccountID,
    a.Enabled,
    a.LimitationID1,
    a.LimitationID2,
    a.LimitationID3
FROM Orion.Accounts a
WHERE IsNull(a.LimitationID1, 0) <> 0
   OR IsNull(a.LimitationID2, 0) <> 0
   OR IsNull(a.LimitationID3, 0) <> 0
ORDER BY a.AccountID
```

`IsNull(column, 0) <> 0` because whether an unused slot holds `0` or `NULL` is not recorded
in the schema; written this way the query is correct either way. The second half, which
limitation does what, is the catalogue:

```sql
SELECT
    l.LimitationID,
    t.Name AS LimitationType,
    t.EntityType,
    l.Definition,
    l.WhereClause
FROM Orion.Limitations l
JOIN Orion.LimitationTypes t ON l.LimitationTypeID = t.LimitationTypeID
ORDER BY l.LimitationID
```

### 50. Which credentials exist?

Names and types only. `Orion.Credential` deliberately exposes no secret material, and the
places that do hold secrets are elsewhere: device credential columns on `Cirrus.Nodes`, the
SNMP community strings on `Orion.Nodes`, and the property bag on `Orion.Actions`.

```sql
SELECT
    c.ID,
    c.Name,
    c.Description,
    c.CredentialType,
    c.CredentialOwner
FROM Orion.Credential c
ORDER BY c.CredentialType, c.Name
```

See [../automation/credentials.md](../automation/credentials.md) for what can and cannot be
read back.

### 51. Which devices are past end of support?

NCM inventories vendor lifecycle data, which turns a refresh budget argument into a list.

```sql
SELECT
    cn.NodeCaption,
    cn.Vendor,
    cn.MachineType,
    cn.OSVersion,
    cn.EndOfSales,
    cn.EndOfSupport,
    cn.ReplacementPartNumber
FROM Cirrus.Nodes cn
WHERE cn.EndOfSupport < GetDate()
ORDER BY cn.EndOfSupport
```

The data is only as fresh as the last inventory, so check that too:

```sql
SELECT
    cn.NodeCaption,
    cn.LastInventory,
    DayDiff(cn.LastInventory, GetDate()) AS DaysSinceInventory
FROM Cirrus.Nodes cn
WHERE cn.LastInventory < AddDay(-30, GetDate())
ORDER BY cn.LastInventory
```

## Housekeeping

### 52. Are there duplicate captions?

Two nodes with the same caption make every report ambiguous and every alert message
useless. This is usually the residue of a rebuild where the old node was never removed.

```sql
SELECT
    n.Caption,
    COUNT(n.NodeID) AS Copies
FROM Orion.Nodes n
GROUP BY n.Caption
HAVING COUNT(n.NodeID) > 1
ORDER BY COUNT(n.NodeID) DESC
```

Then look at the copies before deleting anything, because one of them is usually still
being polled:

```sql
SELECT
    n.NodeID,
    n.Caption,
    n.IPAddress,
    n.LastSync,
    n.MinutesSinceLastSync,
    n.Uri
FROM Orion.Nodes n
WHERE n.Caption = @caption
ORDER BY n.MinutesSinceLastSync
```

### 53. Are there duplicate IP addresses?

The same object monitored twice, usually once by hostname and once by address, which
double-counts against the licence and doubles every alert.

```sql
SELECT
    n.IPAddress,
    COUNT(n.NodeID) AS NodeCount
FROM Orion.Nodes n
WHERE n.IPAddress IS NOT NULL
GROUP BY n.IPAddress
HAVING COUNT(n.NodeID) > 1
ORDER BY COUNT(n.NodeID) DESC
```

### 54. Which nodes have no pollers at all?

`Orion.Pollers` is an assignment table: a row says "collect this kind of data from this
object". A node with no rows exists, looks configured, appears in the console, and collects
nothing. Creating a node is not enough to monitor it.

```sql
SELECT
    n.NodeID,
    n.Caption,
    n.IPAddress,
    n.ObjectSubType,
    n.EngineID
FROM Orion.Nodes n
WHERE NOT EXISTS (
    SELECT p.PollerID
    FROM Orion.Pollers p
    WHERE p.NetObjectType = 'N'
      AND p.NetObjectID = n.NodeID
)
ORDER BY n.Caption
```

The softer version finds the half-configured ones. Note that the `NetObjectType` predicate
sits in the `ON` clause: in the `WHERE` clause it would discard the unmatched rows the
`LEFT JOIN` exists to keep, hiding exactly the nodes you are looking for.

```sql
SELECT
    n.Caption,
    n.ObjectSubType,
    COUNT(p.PollerID) AS PollerCount
FROM Orion.Nodes n
LEFT JOIN Orion.Pollers p
    ON p.NetObjectID = n.NodeID
   AND p.NetObjectType = 'N'
GROUP BY n.Caption, n.ObjectSubType
ORDER BY COUNT(p.PollerID)
```

### 55. Which interfaces and volumes have no pollers?

The same blind spot one level down, and more common, because interfaces are created in bulk.

```sql
SELECT
    i.InterfaceID,
    i.Caption,
    i.Node.Caption AS NodeCaption
FROM Orion.NPM.Interfaces i
WHERE NOT EXISTS (
    SELECT p.PollerID
    FROM Orion.Pollers p
    WHERE p.NetObjectType = 'I'
      AND p.NetObjectID = i.InterfaceID
)
ORDER BY i.Node.Caption, i.Caption
```

```sql
SELECT
    v.VolumeID,
    v.Caption,
    v.VolumeType,
    v.Node.Caption AS NodeCaption
FROM Orion.Volumes v
WHERE NOT EXISTS (
    SELECT p.PollerID
    FROM Orion.Pollers p
    WHERE p.NetObjectType = 'V'
      AND p.NetObjectID = v.VolumeID
)
ORDER BY v.Node.Caption, v.Caption
```

More poller queries, including "missing a whole category of collection", are in
[../automation/pollers.md](../automation/pollers.md#worked-queries).

### 56. Which poller assignments are switched off?

The third state people forget exists, after assigned and not assigned. A disabled assignment
is indistinguishable from a healthy one in recipes 54 and 55, and it collects nothing.

```sql
SELECT
    p.PollerID,
    p.PollerType,
    p.NetObject,
    p.NetObjectType,
    p.NetObjectID,
    p.Enabled
FROM Orion.Pollers p
WHERE p.Enabled = FALSE
ORDER BY p.NetObjectType, p.PollerType
```

### 57. Which objects stopped reporting?

`MinutesSinceLastSync` is maintained by the platform, which saves you doing date arithmetic
against `LastSync` yourself and sidesteps the UTC pitfalls entirely.

```sql
SELECT
    n.Caption,
    n.IPAddress,
    n.LastSync,
    n.MinutesSinceLastSync,
    n.SkippedPollingCycles,
    n.Engine.ServerName AS EngineName
FROM Orion.Nodes n
WHERE n.MinutesSinceLastSync > 60
  AND n.UnManaged = FALSE
ORDER BY n.MinutesSinceLastSync DESC
```

A node that is Up and has not synced for a day is a stuck poller rather than a dead device,
which is why this is a different query from recipe 9.

### 58. What is still unmanaged after its window closed?

A maintenance window that never closed is invisible: the object is not polled, so it never
goes down, so nothing alerts. This query is worth running on a schedule.

```sql
SELECT
    n.NodeID,
    n.Caption,
    n.UnManageFrom,
    n.UnManageUntil,
    MinuteDiff(n.UnManageUntil, GetUtcDate()) AS MinutesOverdue
FROM Orion.Nodes n
WHERE n.UnManaged = TRUE
  AND n.UnManageUntil < GetUtcDate()
ORDER BY n.UnManageUntil
```

The fix is a `Remanage` call per object; see
[../automation/maintenance-mode.md](../automation/maintenance-mode.md#recipe-remanage-early).
The same shape works for interfaces, volumes and applications, because the three properties
are inherited from `System.ManagedEntity`. To sweep every managed type at once:

```sql
SELECT
    m.DisplayName,
    m.InstanceType,
    m.UnManageFrom,
    m.UnManageUntil
FROM System.ManagedEntity m
WHERE m.UnManaged = TRUE
  AND m.UnManageUntil < GetUtcDate()
ORDER BY m.UnManageUntil
```

That is convenient and expensive: 174 entities inherit from `System.ManagedEntity`, and the
query has to consider all of them. Use the per-entity form for anything scheduled.

### 59. Which groups are empty?

Usually a dynamic query that stopped matching anything, which means a group that silently
covers nothing and a rollup status that means nothing.

```sql
SELECT
    g.ContainerID,
    g.Name,
    g.Owner,
    g.LastChanged
FROM Orion.Groups g
WHERE g.IsDeleted = FALSE
  AND NOT EXISTS (
      SELECT cm.ContainerID
      FROM Orion.ContainerMembers cm
      WHERE cm.ContainerID = g.ContainerID
  )
ORDER BY g.Name
```

Groups with polling disabled are a related silence, since their status stops updating:

```sql
SELECT
    g.Name,
    g.PollingEnabled,
    g.UnManageFrom,
    g.UnManageUntil
FROM Orion.Groups g
WHERE g.PollingEnabled = FALSE
  AND g.IsDeleted = FALSE
ORDER BY g.Name
```

### 60. Which application components are disabled?

A disabled component is silently not monitored and does not appear in any failure report.
`UserNotes` often carries the reason, which is worth reading before re-enabling.

```sql
SELECT
    c.Application.Node.Caption AS NodeName,
    c.Application.Name AS ApplicationName,
    c.Name AS ComponentName,
    c.ComponentType,
    c.UserNotes
FROM Orion.APM.Component c
WHERE c.Disabled = TRUE
ORDER BY c.Application.Node.Caption, c.Application.Name
```

## When a recipe returns nothing

Two causes account for nearly all of it, and neither is a problem with the query.

**Account limitations.** SWIS applies the calling account's limitations to every query and
does not tell you it did. Aggregates are scoped too, so a total node count can legitimately
disagree with the licensing page. Recipe 49 shows which accounts carry one. This is the
first thing to rule out, not the last.

**The module is not installed.** Interfaces need NPM, applications need SAM, `Cirrus.*`
needs NCM, `Orion.VIM.*` needs Virtualization Manager. A query naming an entity your server
does not have fails outright rather than returning zero rows, so a clean empty result points
at limitations and an error points at the module. Recipe 4 settles which.

Everything else, in order of probability, is in
[troubleshooting.md](troubleshooting.md#a-query-returns-no-rows-when-you-expect-some).

## Related pages

- [getting-started.md](getting-started.md) if you have not connected yet
- [troubleshooting.md](troubleshooting.md) when something that worked stops working
- [../../scripts/swql/](../../scripts/swql/) for the subject-grouped query files these draw on
- [../swql/functions.md](../swql/functions.md) for the function reference
- [../swql/performance.md](../swql/performance.md) before you schedule any of these
- [../swql/gotchas.md](../swql/gotchas.md) for the things that produce wrong answers rather
  than errors
- [../reference/entity-index.md](../reference/entity-index.md) to find the entity behind a
  question this page does not cover

# QoE: Quality of Experience

Quality of Experience is the platform's packet-inspection capability. Where
[NTA](nta.md) works from flow records the network devices export, QoE works from the packets
themselves: a probe watches traffic, recognises which application a conversation belongs to,
and measures how long the application took to answer and how much of that time was the
network's fault. The two numbers it reports for every application are `ART` and `NRT`, and
separating them is the point of the feature. A slow application whose `NRT` is low is a
server problem; the same slowness with a high `NRT` is a network problem.

QoE is a smaller module than most, and it is documented less than most. This page states
what the 2026.2 schema actually declares and marks clearly where the schema stops and
inference would begin. That distinction matters more here than on a larger page, because
several QoE columns carry no description at all and there is no SolarWinds SDK page for the
module to fall back on.

## Namespace and how many entities

QoE contributes exactly **14 entities**, all under `Orion.DPI.`, where DPI stands for deep
packet inspection. There is no `Orion.QoE.` namespace, and the module code and the namespace
prefix do not match, which is normal for this platform and explained in
[../platform/modules.md](../platform/modules.md).

| Group | Entities |
|---|---|
| Applications and their catalogue | `Applications`, `ApplicationCategories`, `ApplicationProtocols`, `ApplicationSettings`, `ApplicationAssignments` |
| Probes | `Probes`, `ProbeSettings`, `ProbeProperties`, `ProbeAssignments` |
| Statistics | `QoeStatistics`, `QoeApplicationsStatistics` |
| Thresholds | `ApplicationsThresholds`, `ApplicationsThresholdsForAlerting`, `ApplicationAssignmentsThresholds` |

Check for yourself, and confirm the module is installed at all before relying on any of it:

```bash
python3 tools/schema_query.py find DPI --properties
python3 tools/schema_query.py show Orion.DPI.Applications
python3 tools/schema_query.py verbs --entity Orion.DPI.Probes
```

```sql
SELECT FullName, BaseType, CanCreate, CanUpdate, CanDelete, CanInvoke, IsObsolete
FROM Metadata.Entity
WHERE FullName LIKE 'Orion.DPI.%'
ORDER BY FullName
```

No QoE entity has a NetObject prefix. The
[netobject reference](../reference/netobject-types.md) lists `Orion.DPI.Applications`,
`Orion.DPI.ApplicationAssignments` and `Orion.DPI.Probes` under the module code `QoE` with
display names "QoE Application", "QoE Application (per node)" and "QoE Probes", but the
prefix column is empty for all three. The QoE verbs take bare integer ids, consistent with
that.

## Applications are the centre of the model

`Orion.DPI.Applications` is one row per application QoE knows about, whether it is currently
being observed or not. It supports create, read, update, delete and invoke, all requiring
the `admin` right, with read available to everyone. That is stricter than most modules,
where node management is enough.

It inherits from `System.ManagedEntity` through `System.DashboardEntity`, so it is a
first-class monitored object: it has a `Status`, it can be unmanaged, it appears in
`Orion.AlertObjects`, and `UnManaged`, `UnManageFrom` and `UnManageUntil` are queryable on
it. Unusually, it also declares those three properties itself rather than only inheriting
them.

Its 31 declared properties divide into four groups.

**Identity and classification.** `ApplicationID`, `Name`, `Description`, `ProtocolID` (a
`System.String`, not an integer), `CategoryID`, `RiskLevel` and `RiskLevelDescription`,
`ProductivityRating` and `ProductivityRatingDescription`, `ModernIcon`, `WebUri`. The two
`...Description` columns are the readable forms of the two rating bytes and are what you
should display.

**How the application is recognised.** `Filter`, `FilterSyntax`, `DiscoveryMode`,
`LastDiscoveryDate`, `LastDiscoveryProbeID`. `Filter` is the expression that matches traffic
to this application and `FilterSyntax` presumably names the dialect it is written in, but
neither carries a description in the schema, so the exact grammar is **unverified** here.
Read what your server already holds before writing one:
`SELECT TOP 25 Name, Filter, FilterSyntax FROM Orion.DPI.Applications WHERE Filter IS NOT NULL`.

**Current measurements.** `ART`, `NRT`, `Ingress`, `IngressPerSec`, `Egress`,
`EgressPerSec`, `DataVolume`, `DataVolumePerSec`, `Transactions`, `TransactionsPerMin`.
These are the latest rolled-up values, not a history. The history is in
`Orion.DPI.QoeStatistics`.

**State.** `Status` (`System.Int32`, so it joins cleanly to
[`Orion.StatusInfo`](../reference/status-codes.md)), `AdminStatus`, and the `UnManaged`
trio.

Six navigation properties hang off it: `Category`, `ApplicationProtocol`, `Settings`,
`Thresholds`, `Statistics` and `ApplicationAssignment`.

### The catalogue behind an application

`Orion.DPI.ApplicationCategories` is a two-column lookup, `CategoryID` and `Name`, and it is
how "Business", "Social" or whatever grouping your installation uses gets attached to an
application. `Orion.DPI.Applications.Category` follows it.

`Orion.DPI.ApplicationProtocols` is the richer catalogue: `ProtocolID` (again a string),
`Name`, `Description`, `CategoryID`, `RiskLevel`, `ProductivityRating` and `IsVisible`. It
carries its own `Category` navigation, and an application inherits its defaults from the
protocol it is based on. `IsVisible = FALSE` marks protocols the product does not surface in
its own interface, which is the closest thing the schema gives you to "internal, ignore
this".

`Orion.DPI.ApplicationSettings` is a name/value bag per application: `SettingID`,
`ApplicationID`, `Name`, `Value`. What the valid names are is not in the schema; enumerate
them from a live server.

### Per-node assignment

An application definition is global; watching it on a particular server is an assignment.
`Orion.DPI.ApplicationAssignments` is keyed by `ApplicationID` and `NodeID` together, and it
repeats the measurement columns at the node level: `Status`, `ART`, `NRT`, `Ingress`,
`IngressPerSec`, `Egress`, `EgressPerSec`, `DataVolume`, `DataVolumePerSec`, `Transactions`,
`TransactionsPerMin`, `DetailsUrl`.

Its relationship to `Orion.Nodes` is `System.Hosting`, not a plain reference, which means the
node genuinely owns the assignment and deleting the node takes the assignment with it. From
a node, the navigation property is **`DPIApplicationAssignment`**, singular and prefixed,
which is not a name anyone guesses correctly. From the assignment, `Node` and `Application`
both navigate.

## Probes

A probe is the thing doing the packet inspection. `Orion.DPI.Probes` declares seven
properties: `ProbeID`, `Name`, `Description`, `AgentID`, `Mode`, `Enabled` and `Status`.

The important structural fact is `AgentID`. A QoE probe runs on a deployed agent, which is
why the module has a deployment verb rather than a discovery process, and why probe health
is really agent health. But `Orion.DPI.Probes` has **no navigation property to
`Orion.AgentManagement.Agent`**. The only path the schema offers is through the assignment
and the node:

```bash
python3 tools/schema_query.py path Orion.DPI.Probes Orion.AgentManagement.Agent
```

which returns exactly one route, `Orion.DPI.Probes.ProbeAssignment.Node.Agent`. If you want
to go directly from probe to agent, join `Orion.AgentManagement.Agent` on `AgentID` by hand.

`Orion.DPI.ProbeAssignments` is the pairing of a probe with a node, and declares only
`ProbeID` and `NodeID`. Like the application assignment, it is hosted by the node, and the
navigation property from a node is **`DPIProbeAssignment`**.

`Orion.DPI.ProbeSettings` (`SettingID`, `ProbeID`, `Name`, `Value`) and
`Orion.DPI.ProbeProperties` (`PropertyID`, `ProbeID`, `Name`, `Value`) are two separate
name/value bags attached to the same probe, reached as `Settings` and `Properties`. The
schema does not say what distinguishes a setting from a property, and no valid names are
enumerated, so both are **unverified** in content. They are both readable, so the answer is
one query away on a live server, and that is the honest way to find out:

```sql
SELECT TOP 100
    ps.Probe.Name AS ProbeName,
    ps.Name AS SettingName,
    ps.Value
FROM Orion.DPI.ProbeSettings ps
ORDER BY ps.Probe.Name, ps.Name
```

`Mode` on `Orion.DPI.Probes` is a `System.Byte` with no description. Given that the two
deployment verbs are `DeployLocalTrafficProbe` and `DeploySpanPortProbe`, it is a reasonable
guess that `Mode` distinguishes those two deployment styles, but that is an inference and is
**not verified** by the schema. Check what values your server holds:
`SELECT TOP 10 Mode, COUNT(ProbeID) AS Probes FROM Orion.DPI.Probes GROUP BY Mode`.

## Statistics and thresholds

`Orion.DPI.QoeStatistics` is the history and the only QoE entity that inherits from
`System.StatisticsEntity`. It is keyed in practice by `ApplicationID`, `NodeID`, `ProbeID`
and `ObservationTimestamp`, and it carries min, average and max for every measure rather
than a single value: `AvgART`, `MinART`, `MaxART`, `RecordCountART`, and the same pattern
for `NRT`, `IngressPerSec`, `EgressPerSec` and `TransactionsPerMin`, plus the raw totals
`Ingress`, `Egress`, `Transactions` and `RecordCount`. It navigates to `Application` and
`Probe`, but **not** to `Orion.Nodes` despite declaring `NodeID`.

The `RecordCount*` columns matter more than they look. `AvgART` computed from three
observations and `AvgART` computed from thirty thousand are not the same claim, and dividing
by `RecordCountART` is how you weight an average correctly when you aggregate across rows.

`Orion.DPI.QoeApplicationsStatistics` is a different thing despite the similar name: it does
**not** inherit from `System.StatisticsEntity`, it declares no navigation properties, and it
pre-joins the application catalogue onto the measurements. It carries `Name`, `Description`,
`CategoryID`, `CategoryName`, `RiskLevel`, `ProductivityRating`, `Filter` and
`AssignedNodes` alongside `AvgART`, `AvgNRT`, `Volume`, `Transactions` and the min and max
columns. Use it when you want a readable per-application summary without writing joins.

Three threshold entities exist and they are not interchangeable:

| Entity | Shape | Use |
|---|---|---|
| `Orion.DPI.ApplicationsThresholdsForAlerting` | `ApplicationID`, `ARTWarning`, `ARTCritical`, `NRTWarning`, `NRTCritical`, `DataVolumeWarning`, `DataVolumeCritical`, `TransactionsWarning`, `TransactionsCritical` | The configured limits per application. Navigates to `Application` |
| `Orion.DPI.ApplicationAssignmentsThresholds` | `ApplicationID`, `NodeID`, the measured values, and `ARTStatus`, `NRTStatus`, `DataVolumePerSecStatus`, `TransactionsPerMinStatus` | The evaluated result per application per node. Declares no navigation properties |
| `Orion.DPI.ApplicationsThresholds` | Declares **zero** properties of its own; inherits all 20 from `Orion.Thresholds` | The platform's generic threshold shape applied to QoE |

That third one is the trap. `python3 tools/schema_query.py show Orion.DPI.ApplicationsThresholds`
prints an empty property list, which looks like a broken or unused entity. It is neither: it
inherits `EntityType`, `InstanceId`, `ThresholdType`, `ThresholdOperator`, `Name`,
`CurrentValue`, `Level1Value`, `Level1Formula`, `IsLevel1State`, `Level2Value`,
`Level2Formula`, `IsLevel2State`, `GlobalWarningValue`, `GlobalCriticalValue`,
`WarningPolls`, `WarningPollsInterval`, `CriticalPolls`, `CriticalPollsInterval`,
`WarningEnabled` and `CriticalEnabled` from `Orion.Thresholds`, one of 133 entities that do.
Use `props`, not `show`, whenever a property list comes back empty:

```bash
python3 tools/schema_query.py props Orion.DPI.ApplicationsThresholds
```

## Verbs

QoE publishes five verbs, all on `Orion.DPI.Probes`. The entity requires the **`admin`**
right for create, read, update, delete and invoke, with read also granted to everyone.
Arguments are positional; the names below never travel on the wire.

| Verb | Parameters, in order | Returns |
|---|---|---|
| `DeployLocalTrafficProbe` | `nodeId`, `machineUserName`, `machinePassword`, `probeName`, `probeDescription` | `SolarWinds.DPI.Common.Models.ProbeDeploymentResult` |
| `DeploySpanPortProbe` | `nodeId`, `machineUserName`, `machinePassword`, `probeName`, `probeDescription` | `SolarWinds.DPI.Common.Models.ProbeDeploymentResult` |
| `GetProbeCapabilities` | `probeId` | `SolarWinds.DPI.Common.Models.ProbeCapabilities` |
| `ReloadProbeSettings` | `probeId` | boolean |
| `ReloadAppDefinitions` | `probeId` | boolean |

The two deploy verbs have identical signatures and differ only in the kind of probe they
install: one inspects traffic on the machine itself, the other inspects a mirrored port.
Both take machine credentials as plain positional strings, which means the password is in
the request body. Use HTTPS, which is the only transport SWIS offers anyway, and do not put
those credentials in a script that gets committed. See
[../swis/invoke-verbs.md](../swis/invoke-verbs.md).

Their return type is declared in SolarWinds' Swagger contract with two fields, `ProbeId` and
`DeploymentError`, so the shape of a success check is unambiguous:

```powershell
$swis = Connect-Swis -Hostname orion.example.com -Credential $cred

$result = Invoke-SwisVerb $swis Orion.DPI.Probes DeployLocalTrafficProbe `
    @($nodeId, $machineUser, $machinePassword, 'dc-probe-01', 'Datacenter A local traffic')

if ($result.DeploymentError) {
    Write-Error "Probe deployment failed: $($result.DeploymentError)"
} else {
    Write-Host "Deployed probe $($result.ProbeId)"
}
```

`GetProbeCapabilities` returns `ProbeCapabilities`, which the contract declares as a
`Hardware` object with `CpuCores` and `PhysicalMemoryMb`, plus an `Interfaces` array whose
entries declare `IpAddresses`. That is a thin contract and the real response may carry more;
the fields listed here are the ones the published Swagger actually names.

`ReloadProbeSettings` and `ReloadAppDefinitions` push configuration to a running probe.
After creating or editing an `Orion.DPI.Applications` row through CRUD, the probe is not
necessarily using the new definition yet, and `ReloadAppDefinitions` is the call that makes
it. That sequencing is **inferred from the verb names**, not stated in the schema, so verify
the behaviour on a test probe before building it into a workflow.

Everything else in QoE is CRUD. `Orion.DPI.Applications`, `Orion.DPI.ApplicationSettings`,
`Orion.DPI.ApplicationAssignments`, `Orion.DPI.ProbeSettings`, `Orion.DPI.ProbeProperties`
and `Orion.DPI.ProbeAssignments` all support create, read, update, delete and invoke under
`admin`. Assigning an application to a node, for example, is a plain create:

```powershell
New-SwisObject $swis Orion.DPI.ApplicationAssignments @{
    ApplicationID = $applicationId
    NodeID        = $nodeId
} | Out-Null
```

The five remaining entities, `Orion.DPI.ApplicationCategories`,
`Orion.DPI.ApplicationProtocols`, `Orion.DPI.QoeStatistics`,
`Orion.DPI.QoeApplicationsStatistics`, `Orion.DPI.ApplicationsThresholds`,
`Orion.DPI.ApplicationsThresholdsForAlerting` and
`Orion.DPI.ApplicationAssignmentsThresholds`, declare no operations at all in the schema and
should be treated as read-only views.

## How QoE relates to SAM applications

This is the question the module's naming invites, and the honest answer has two halves.

**What the schema says.** There is no relationship between any `Orion.DPI.*` entity and any
`Orion.APM.*` entity in the 2026.2 data. All 26 relationship edges touching `Orion.DPI.` stay
inside the module except four, and those four go to `Orion.Nodes`:
`Orion.DPI.ApplicationAssignments.Node`, `Orion.DPI.ProbeAssignments.Node`, and the two
reverse edges `Orion.Nodes.DPIApplicationAssignment` and `Orion.Nodes.DPIProbeAssignment`.
Confirm it:

```bash
python3 tools/schema_query.py path Orion.DPI.Applications Orion.APM.Application
```

The shortest routes it finds all go out through `Orion.AlertObjects` or through
`ApplicationAssignment` and back down via `Orion.Nodes`. There is no direct hop.

**What the reference data says.** `data/reference/netobject-types.json`, which is built from
an older community workbook, records `Orion.APM.Application` as a parent entity for both
`Orion.DPI.Applications` and `Orion.DPI.ApplicationAssignments`. The two sources disagree,
and per [CONTRIBUTING.md](../../CONTRIBUTING.md) the disagreement is reported rather than
resolved by picking a winner. Nothing in the 2026.2 schema supports a QoE-to-SAM parentage,
so **treat the workbook's claim as unverified** and do not write a query that assumes a
navigation property exists.

**What to do instead.** Join through the node, which is the only relationship both modules
actually declare. A QoE application and a SAM application are two different measurements of
the same server, and `NodeID` is what they share:

```sql
SELECT TOP 50
    n.Caption AS NodeName,
    qoe.Application.Name AS QoeApplication,
    qoe.ART AS QoeAppResponseMs,
    qoe.NRT AS QoeNetworkResponseMs,
    sam.Name AS SamApplication,
    sam.StatusDescription AS SamStatus
FROM Orion.Nodes n
JOIN Orion.DPI.ApplicationAssignments qoe ON qoe.NodeID = n.NodeID
JOIN Orion.APM.Application sam ON sam.NodeID = n.NodeID
WHERE n.NodeID = @nodeId
ORDER BY qoe.ART DESC
```

That is a cross product of the two application sets on one node, which is exactly what the
data supports and no more: it does not claim that a given QoE application *is* a given SAM
application, because nothing in the schema establishes that. Scope it to a single node, as
above, or you will produce a very large and not very meaningful result. See
[sam.md](sam.md) for the SAM side.

## Worked queries

Every query below has been validated against the 2026.2 schema.

### 1. Slowest applications, with a readable status

`Status` on `Orion.DPI.Applications` is a `System.Int32`, so it joins to `Orion.StatusInfo`
cleanly. Filtering `UnManaged = FALSE` is the difference between "actually slow" and "in a
maintenance window".

```sql
SELECT TOP 50
    a.ApplicationID,
    a.Name AS ApplicationName,
    a.Category.Name AS CategoryName,
    a.RiskLevelDescription,
    a.ProductivityRatingDescription,
    st.StatusName,
    a.ART,
    a.NRT,
    a.TransactionsPerMin,
    a.DataVolumePerSec
FROM Orion.DPI.Applications a
JOIN Orion.StatusInfo st ON st.StatusId = a.Status
WHERE a.UnManaged = FALSE
ORDER BY a.ART DESC
```

### 2. Is it the application or is it the network?

This is the query the module exists for. Two applications on the same node with similar
`ART` but very different `NRT` point at two completely different teams.

```sql
SELECT TOP 100
    aa.Node.Caption AS NodeName,
    aa.Application.Name AS ApplicationName,
    aa.Application.Category.Name AS CategoryName,
    st.StatusName,
    aa.ART,
    aa.NRT,
    aa.DataVolumePerSec,
    aa.TransactionsPerMin
FROM Orion.DPI.ApplicationAssignments aa
JOIN Orion.StatusInfo st ON st.StatusId = aa.Status
WHERE aa.NodeID = @nodeId
ORDER BY aa.ART DESC
```

`aa.Application.Category.Name` walks two references in one expression, from the assignment
to the application to its category.

### 3. Probes, the nodes they watch, and whether they are on

`Orion.DPI.Probes` has no `Node` property of its own; the node comes through
`ProbeAssignment`. A probe row with a null node name is an orphan, which is worth knowing.

```sql
SELECT TOP 100
    p.ProbeID,
    p.Name AS ProbeName,
    p.Description,
    p.AgentID,
    p.Mode,
    p.Enabled,
    p.Status,
    p.ProbeAssignment.Node.Caption AS NodeName,
    p.ProbeAssignment.Node.IPAddress AS NodeIPAddress
FROM Orion.DPI.Probes p
ORDER BY p.Name
```

`p.Status` is a `System.Int16` here, unlike the `System.Int32` on
`Orion.DPI.Applications`, so it is deliberately not joined to `Orion.StatusInfo.StatusId`
in this query.

### 4. Response time trend over a window

`Orion.DPI.QoeStatistics` inherits from `System.StatisticsEntity` and is the one QoE table
that grows without bound, so it always gets an `ObservationTimestamp` predicate.

```sql
SELECT TOP 50
    s.Application.Name AS ApplicationName,
    s.Probe.Name AS ProbeName,
    s.NodeID,
    AVG(s.AvgART) AS MeanART,
    MAX(s.MaxART) AS PeakART,
    AVG(s.AvgNRT) AS MeanNRT,
    SUM(s.Transactions) AS Transactions,
    SUM(s.Ingress) AS IngressBytes,
    SUM(s.Egress) AS EgressBytes
FROM Orion.DPI.QoeStatistics s
WHERE s.ObservationTimestamp >= @startUtc
  AND s.ObservationTimestamp < @endUtc
GROUP BY s.Application.Name, s.Probe.Name, s.NodeID
ORDER BY AVG(s.AvgART) DESC
```

Averaging an average, as `AVG(s.AvgART)` does, weights every interval equally regardless of
how many transactions it saw. That is usually what you want for a trend and usually not what
you want for a service level number. `RecordCountART` is there for when you need the
weighted version.

### 5. Applications currently past their warning threshold

The configured limits live on one entity and the current values on another, and the
`Application` navigation property joins them for you.

```sql
SELECT TOP 50
    t.Application.Name AS ApplicationName,
    t.Application.ART AS CurrentART,
    t.ARTWarning,
    t.ARTCritical,
    t.Application.NRT AS CurrentNRT,
    t.NRTWarning,
    t.NRTCritical
FROM Orion.DPI.ApplicationsThresholdsForAlerting t
WHERE t.Application.ART > t.ARTWarning
ORDER BY t.Application.ART DESC
```

For the already-evaluated per-node version, use the other threshold entity. It has no
navigation properties, so its `ApplicationID` and `NodeID` stay as raw ids unless you join
them yourself.

```sql
SELECT TOP 100
    th.ApplicationID,
    th.NodeID,
    th.ART,
    th.ARTStatus,
    th.NRT,
    th.NRTStatus,
    th.DataVolumePerSecStatus,
    th.TransactionsPerMinStatus,
    th.RecordCount
FROM Orion.DPI.ApplicationAssignmentsThresholds th
WHERE th.ARTStatus <> 1 OR th.NRTStatus <> 1
ORDER BY th.ART DESC
```

### 6. Which nodes have a QoE probe

Starting from `Orion.Nodes` and walking down uses the awkwardly named navigation property,
which is worth seeing written out once.

```sql
SELECT TOP 100
    n.Caption AS NodeName,
    n.DPIProbeAssignment.ProbeID AS ProbeID,
    n.DPIProbeAssignment.Probe.Name AS ProbeName,
    n.DPIProbeAssignment.Probe.Enabled AS ProbeEnabled
FROM Orion.Nodes n
WHERE n.DPIProbeAssignment.ProbeID IS NOT NULL
ORDER BY n.Caption
```

### 7. The protocol catalogue, by category

Useful before defining anything: it shows what QoE can already recognise, and the risk and
productivity defaults it will apply.

```sql
SELECT TOP 100
    pr.ProtocolID,
    pr.Name AS ProtocolName,
    pr.Description,
    pr.Category.Name AS CategoryName,
    pr.RiskLevel,
    pr.ProductivityRating
FROM Orion.DPI.ApplicationProtocols pr
WHERE pr.IsVisible = TRUE
ORDER BY pr.Name
```

### 8. Per-application summary without writing joins

`Orion.DPI.QoeApplicationsStatistics` pre-joins the catalogue onto the measurements, so a
readable overview is a single-entity query. `AssignedNodes` tells you how much of the estate
each number covers.

```sql
SELECT TOP 50
    qs.Name AS ApplicationName,
    qs.CategoryName,
    qs.AssignedNodes,
    qs.ObservationTimestamp,
    qs.AvgART,
    qs.AvgNRT,
    qs.Volume,
    qs.Transactions
FROM Orion.DPI.QoeApplicationsStatistics qs
ORDER BY qs.Volume DESC
```

### 9. Which categories your applications actually fall into

```sql
SELECT TOP 100
    c.CategoryID,
    c.Name AS CategoryName,
    COUNT(a.ApplicationID) AS ApplicationCount
FROM Orion.DPI.ApplicationCategories c
JOIN Orion.DPI.Applications a ON a.CategoryID = c.CategoryID
GROUP BY c.CategoryID, c.Name
ORDER BY COUNT(a.ApplicationID) DESC
```

## Gotchas

**Everything in QoE requires `admin`, not `manageNodes`.** `Orion.DPI.Probes`,
`Orion.DPI.Applications`, `Orion.DPI.ApplicationSettings`,
`Orion.DPI.ApplicationAssignments`, `Orion.DPI.ProbeSettings`, `Orion.DPI.ProbeProperties`
and `Orion.DPI.ProbeAssignments` all declare `create,read,update,delete,invoke requires
admin`. An account that can add nodes and assign pollers all day will be refused here. Read
is granted to everyone on all of them.

**The navigation properties from a node are prefixed and singular.**
`Orion.Nodes.DPIApplicationAssignment` and `Orion.Nodes.DPIProbeAssignment`. Not
`QoEApplications`, not `DPIApplications`, not plural. Both relationships are
`System.Hosting`, so deleting a node removes them.

**A probe has an `AgentID` but no `Agent` navigation property.** The only declared path from
`Orion.DPI.Probes` to `Orion.AgentManagement.Agent` runs through `ProbeAssignment.Node.Agent`.
Join on `AgentID` explicitly if you want to go straight there. See
[agents.md](agents.md).

**`Orion.DPI.QoeStatistics` declares `NodeID` but does not navigate to `Orion.Nodes`.** Its
only navigation properties are `Application` and `Probe`. Join `Orion.Nodes` on `NodeID` when
you need the caption.

**Two entities have similar names and completely different shapes.**
`Orion.DPI.QoeStatistics` is the time series and inherits from `System.StatisticsEntity`;
`Orion.DPI.QoeApplicationsStatistics` is a pre-joined summary that does not, and declares no
navigation properties at all.

**`Orion.DPI.ApplicationsThresholds` looks empty and is not.** It declares zero properties
and inherits twenty from `Orion.Thresholds`. `show` will mislead you; use `props`.

**`Status` is two different types across the module.** `Orion.DPI.Applications.Status` is
`System.Int32` and joins to `Orion.StatusInfo.StatusId`. `Orion.DPI.Probes.Status` is
`System.Int16`. `Orion.DPI.ApplicationAssignments.Status` is `System.Int32`. Check the type
before writing the join.

**`ProtocolID` is a string on both entities that carry it.** On
`Orion.DPI.Applications` and on `Orion.DPI.ApplicationProtocols` it is a `System.String`, not
an integer, so it compares and joins as text.

**Time-bound `Orion.DPI.QoeStatistics`.** It is the only QoE entity below
`System.StatisticsEntity` and it grows per application, per node, per probe, per interval.
It is nowhere near NTA's scale, but the rule is the same and costs nothing to follow.

**Account limitations filter silently.** As everywhere else, two accounts running the same
QoE query can get different rows with no indication that anything was removed.

## What is not verified here

The schema for this module is thin on descriptions, and rather than fill the gaps with
plausible narrative, these are the specific things this page could not confirm and how to
settle each one on your own server.

| Claim | Status | How to check |
|---|---|---|
| `ART` and `NRT` expand to application response time and network response time | Not stated anywhere in the schema; the columns carry no description. The product names are widely used but are not evidence from this data | `SELECT p.Name, p.Type, p.Summary FROM Metadata.Property p WHERE p.Entity.FullName = 'Orion.DPI.Applications' ORDER BY p.Name` |
| `Mode` on `Orion.DPI.Probes` distinguishes local-traffic from SPAN-port probes | Inferred from the two deployment verb names, not declared | `SELECT TOP 10 Mode, COUNT(ProbeID) AS Probes FROM Orion.DPI.Probes GROUP BY Mode` and compare against how each probe was deployed |
| The grammar accepted by `Orion.DPI.Applications.Filter` and the values of `FilterSyntax` | Undocumented | `SELECT TOP 25 Name, Filter, FilterSyntax FROM Orion.DPI.Applications WHERE Filter IS NOT NULL` |
| The valid names in `Orion.DPI.ProbeSettings`, `Orion.DPI.ProbeProperties` and `Orion.DPI.ApplicationSettings` | Undocumented; three separate name/value bags with no enumerated keys | Query each entity and read the `Name` column |
| What distinguishes a probe *setting* from a probe *property* | Undocumented | As above, compare the two key sets |
| The meaning of `DiscoveryMode` and `AdminStatus` on `Orion.DPI.Applications` | Undocumented integers | `SELECT TOP 10 DiscoveryMode, AdminStatus, COUNT(ApplicationID) AS Applications FROM Orion.DPI.Applications GROUP BY DiscoveryMode, AdminStatus` |
| `ReloadAppDefinitions` is required after editing an application definition | Inferred from the verb name | Test on a non-production probe |
| `Orion.APM.Application` is a parent of `Orion.DPI.Applications` | Claimed by the community-sourced netobject reference, contradicted by the 2026.2 relationship data | `SELECT p.Entity.FullName AS EntityName, p.Name, p.Type FROM Metadata.Property p WHERE p.IsNavigable = TRUE AND p.Entity.FullName LIKE 'Orion.DPI.%' ORDER BY p.Entity.FullName, p.Name` |
| The full contents of `ProbeCapabilities` returned by `GetProbeCapabilities` | The Swagger contract declares only `Hardware.CpuCores`, `Hardware.PhysicalMemoryMb` and `Interfaces[].IpAddresses`; the live response may carry more | Invoke it against a real probe and inspect the result |

There is no SolarWinds SDK documentation page for QoE in the published OrionSDK docs, and no
QoE sample script in the SDK samples directory. That absence is itself worth knowing: it
means the schema and your own server are the only sources, and
[`../../scripts/swql/08-schema-introspection.swql`](../../scripts/swql/08-schema-introspection.swql)
is the tool for the job.

## Related pages

- [README.md](README.md) for the module index and how to check what is installed.
- [nta.md](nta.md) for NetFlow Traffic Analyzer, the flow-based view of the same traffic.
- [sam.md](sam.md) for `Orion.APM.Application`, the other kind of application monitoring.
- [agents.md](agents.md) for `Orion.AgentManagement.Agent`, which QoE probes run on.
- [../platform/modules.md](../platform/modules.md) for the whole-schema module map.
- [../swis/invoke-verbs.md](../swis/invoke-verbs.md) for positional verb arguments.
- [../swis/crud.md](../swis/crud.md) for creating application and probe assignments.
- [../reference/status-codes.md](../reference/status-codes.md) for the `Status` integers.
- [../../scripts/swql/08-schema-introspection.swql](../../scripts/swql/08-schema-introspection.swql)
  for asking a live server what it actually has.

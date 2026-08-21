# Standard pollers

This is the concept that catches everyone who automates node creation, and it catches them
silently.

You create a node through the API. The create succeeds, it returns a URI, the node appears in
the web console with a name and an address, and everything looks right. Then it never goes
green, no charts ever have data on them, and no alert ever fires for it. Nothing errored. The
node simply is not being polled, because **creating a node does not create any monitoring. It
creates a row.** What turns a row into monitoring is one `Orion.Pollers` record per thing you
want collected, and nothing creates those for you when you go through CRUD.

The web console hides this. Adding a node there runs a discovery, presents you with a list of
resources it found, and writes the poller assignments for the ones you tick. The API gives you
the two halves separately, and the second half is the one people do not know exists.

```text
Orion.Nodes row          "this machine exists and here is how to reach it"
      +
Orion.Pollers rows       "collect status from it, collect CPU from it, collect memory from it"
      =
monitoring
```

This page is about the second half: what an `Orion.Pollers` assignment is, how to see which
ones an object has, how to create and remove them, and how to let the platform pick them for
you.

`Orion.Pollers` is one of five polling systems, and the other four share none of its
entities. If what you are looking at is keyed on a GUID, or has no `NetObjectType`, it is not
this system. [README.md](README.md) is the map.

## `Orion.Pollers` is an assignment table, not a poller

The entity is six properties wide and that is the whole of it:

```bash
python3 tools/schema_query.py show Orion.Pollers
```

| Property | Type | Notes |
|:---|:---|:---|
| `PollerID` | `System.Int32` | Assigned by the create. Not something you supply. |
| `PollerType` | `System.String` | **Which** poller. A string like `N.Cpu.SNMP.CiscoGen3`. |
| `NetObject` | `System.String` | **What** it polls, as a NetObject string: `"N:42"`. |
| `NetObjectType` | `System.String` | The prefix on its own: `"N"`, `"I"`, `"V"`. |
| `NetObjectID` | `System.Int32` | The bare id on its own: `42`. |
| `Enabled` | `System.Boolean` | Whether the assignment is active. |

Two things follow from how small that is.

**The poller code itself is not in the schema.** `PollerType` is a string naming a piece of
polling logic that lives inside the polling engine. There is no entity for it, no list of valid
values in `data/`, and no foreign key. A typo in `PollerType` is accepted by the create and
produces an assignment that collects nothing, which is the same failure mode as having no
assignment at all and harder to spot.

**`Orion.Pollers` has no navigation properties in either direction.** It does not reach
`Orion.Nodes` and `Orion.Nodes` does not reach it. Every query that combines the two is a
manual join, and every one of those joins must filter on `NetObjectType` as well as
`NetObjectID`, because node 42, interface 42 and volume 42 all exist and all have
`NetObjectID = 42`. Joining on the id alone silently mixes three unrelated objects.

The entity allows full CRUD plus invoke under `manageNodes`, and `read` for `everyone`. It
declares no verbs, so everything you do to a poller assignment is CRUD.

## The poller type string

The convention is `<NetObjectType>.<Category>.<Method>.<Variant>`:

```
N.Cpu.SNMP.CiscoGen3
│ │   │    └── the specific implementation, usually a device family or a MIB
│ │   └─────── how it collects: SNMP, WMI, ICMP, Agent
│ └─────────── what it collects: Status, ResponseTime, Details, Uptime, Cpu, Memory, Topology
└───────────── the NetObject prefix of the thing being polled
```

SolarWinds publishes the catalogue at
[Poller Types](https://solarwinds.github.io/OrionSDK/docs/poller-types/), with a description of
what each one collects and, for the SNMP ones, the exact OIDs it walks. The 2026.2 page lists
**124 distinct poller type strings**: 108 with the `N.` prefix and 16 with `V.`. By collection
method they break down as 97 SNMP, 24 WMI, 2 ICMP and 1 Agent.

The three whole-node status pollers are worth reading, because they explain the shape of the
whole system:

| Type | What the catalogue says |
|:---|:---|
| `N.StatusAndResponseTime.ICMP.SendEcho` | Uses the Win32 `IcmpSendEcho` API to measure response time and node status. |
| `N.StatusAndResponseTime.SNMP.sysObjectID` | GETs `sysObjectID` (`1.3.6.1.2.1.1.2.0`) to see whether the node responds. |
| `N.StatusAndResponseTime.Agent.Native` | "This poller does nothing at all. Node status is based on agent status." |

That last one is the clearest statement of what a poller assignment does. The agent poller
collects nothing; its presence is what tells the platform to derive node status from
`Orion.AgentManagement.Agent.AgentStatus` instead of from a ping. See
[../modules/agents.md](../modules/agents.md).

### The catalogue is not the whole set

This matters enough to state plainly, because it is the first thing that goes wrong when you
copy a type string from one place and validate it against another.

SolarWinds' own
[`CRUD.AddNode.ps1`](https://github.com/solarwinds/OrionSDK/blob/master/Samples/PowerShell/CRUD.AddNode.ps1)
sample assigns `N.Status.ICMP.Native` and `N.ResponseTime.ICMP.Native`. **Neither string
appears anywhere in the published Poller Types catalogue**, which instead lists the combined
`N.StatusAndResponseTime.*` family above. Their own NPM how-to page,
[How To Assign Specific Poller To A Node](https://solarwinds.github.io/OrionSDK/docs/network-performance-monitor/how-to-assign-specific-poller-to-a-node/),
uses `N.Status.SNMP.Native` in its worked example and shows a real query response containing
`N.ResponseTime.ICMP.Native`. So the separate `.Native` status and response-time pollers are
real on live servers and the catalogue does not describe them.

The catalogue also lists **no interface pollers at all**. Every entry is `N.` or `V.`. The
interface types in
[`CRUD.AddInterface.ps1`](https://github.com/solarwinds/OrionSDK/blob/master/Samples/PowerShell/CRUD.AddInterface.ps1)
are `I.Status.SNMP.IfTable`, `I.StatisticsTraffic.SNMP.Universal`,
`I.StatisticsErrors32.SNMP.IfTable` and `I.Rediscovery.SNMP.IfTable`.

So: the catalogue is a good reference and a bad allowlist. **The authoritative list of poller
types for a given server is the set of types already in use on it**, which is one query away:

```sql
SELECT p.NetObjectType, p.PollerType, COUNT(p.PollerID) AS Assignments
FROM Orion.Pollers p
GROUP BY p.NetObjectType, p.PollerType
ORDER BY COUNT(p.PollerID) DESC
```

Run that against a healthy node of the kind you are about to create programmatically, take the
strings it returns, and use those. Copying from a working object beats copying from any
document, including this one.

## Seeing what an object has

Everything a node is having collected from it, in one query:

```sql
SELECT p.PollerID, p.PollerType, p.NetObject, p.NetObjectType, p.NetObjectID, p.Enabled, p.Uri
FROM Orion.Pollers p
WHERE p.NetObjectType = 'N'
  AND p.NetObjectID = @nodeId
ORDER BY p.PollerType
```

`Uri` is inherited from `System.Entity` rather than declared by `Orion.Pollers`, and selecting
it here is not optional if you intend to delete or update any of these rows: URIs are the
handle every write interface takes, and building them by string formatting is the mistake
[../swis/uris.md](../swis/uris.md) exists to prevent.

Prefixes for the `NetObjectType` filter come from
[../reference/netobject-types.md](../reference/netobject-types.md). The three you will use
constantly are `N` for `Orion.Nodes`, `I` for `Orion.NPM.Interfaces` and `V` for
`Orion.Volumes`.

## Adding a poller

A poller assignment is a plain CRUD create. Four properties, three of which are the same
NetObject expressed three ways.

```json
{
  "PollerType": "N.Cpu.SNMP.CiscoGen3",
  "NetObject": "N:42",
  "NetObjectType": "N",
  "NetObjectID": 42
}
```

```text
POST https://orion.example.com:17774/SolarWinds/InformationService/v3/Json/Create/Orion.Pollers
```

The response is the new row's URI. SolarWinds shows the same call on their
[assign a poller](https://solarwinds.github.io/OrionSDK/docs/network-performance-monitor/how-to-assign-specific-poller-to-a-node/)
page; note that their example URL uses port 17778, which was the REST port through 2022.4.1 and
is deprecated. Use **17774** from platform release 2023.1 onward. See
[../swis/connecting.md](../swis/connecting.md).

### The pattern from `CRUD.AddNode.ps1`

The official sample builds the three NetObject properties once and then swaps `PollerType` in a
loop, which is worth copying exactly, because it is the shape that makes the repetition
harmless:

```powershell
$poller = @{
    NetObject     = "N:$nodeId"
    NetObjectType = 'N'
    NetObjectID   = $nodeId
}

foreach ($type in @(
    'N.Status.ICMP.Native',
    'N.ResponseTime.ICMP.Native',
    'N.Details.SNMP.Generic',
    'N.Uptime.SNMP.Generic',
    'N.Cpu.SNMP.CiscoGen3',
    'N.Memory.SNMP.CiscoGen3'
)) {
    $poller['PollerType'] = $type
    New-SwisObject $swis -EntityType 'Orion.Pollers' -Properties $poller | Out-Null
}
```

Those six are the SNMP set from the sample. The WMI set from
[`CRUD.AddWMINode.ps1`](https://github.com/solarwinds/OrionSDK/blob/master/Samples/PowerShell/CRUD.AddWMINode.ps1)
keeps the first two and changes the rest:

| Purpose | SNMP node | WMI node |
|:---|:---|:---|
| Status | `N.Status.ICMP.Native` | `N.Status.ICMP.Native` |
| Response time | `N.ResponseTime.ICMP.Native` | `N.ResponseTime.ICMP.Native` |
| Details | `N.Details.SNMP.Generic` | `N.Details.WMI.Vista` |
| Uptime | `N.Uptime.SNMP.Generic` | `N.Uptime.WMI.XP` |
| CPU | `N.Cpu.SNMP.CiscoGen3` | `N.Cpu.WMI.Windows` |
| Memory | `N.Memory.SNMP.CiscoGen3` | `N.Memory.WMI.Windows` |

**The status and response time pollers stay ICMP in both cases.** Up and down is a ping
question regardless of how the rest of the data is collected. And **the CPU and memory pollers
in the SNMP column are Cisco-specific**: `N.Cpu.SNMP.CiscoGen3` walks `CISCO-PROCESS-MIB` and
returns nothing at all from a Linux host. For a generic SNMP device the catalogue's
`N.Cpu.SNMP.HrProcessorLoad` and `N.Memory.SNMP.HrStorage` walk the host resources MIB
instead. Getting this wrong produces a node that is up, has details, and has no CPU chart,
which is the most common "why is this node half-monitored" ticket there is.

### Make it idempotent

Creating the same assignment twice is not prevented by anything in the entity, so a rerun after
a partial failure accumulates duplicates. Check first:

```powershell
$wanted = @(
    'N.Status.ICMP.Native',
    'N.ResponseTime.ICMP.Native',
    'N.Details.SNMP.Generic',
    'N.Uptime.SNMP.Generic'
)

$existing = Get-SwisData $swis @'
SELECT p.PollerType
FROM Orion.Pollers p
WHERE p.NetObjectType = 'N' AND p.NetObjectID = @nodeId
'@ @{ nodeId = $nodeId }

$poller = @{ NetObject = "N:$nodeId"; NetObjectType = 'N'; NetObjectID = $nodeId }

foreach ($type in $wanted) {
    if ($existing -contains $type) {
        Write-Verbose "$type already assigned to node $nodeId"
        continue
    }
    $poller['PollerType'] = $type
    New-SwisObject $swis -EntityType 'Orion.Pollers' -Properties $poller | Out-Null
}
```

Then poll immediately rather than waiting for the first scheduled cycle, and read the result
back:

```powershell
Invoke-SwisVerb $swis 'Orion.Nodes' 'PollNow' @("N:$nodeId") | Out-Null
```

```sql
SELECT
    n.NodeID, n.Caption, n.Status, n.LastSync, n.MinutesSinceLastSync,
    n.NextPoll, n.IsPollingError, n.SkippedPollingCycles
FROM Orion.Nodes n
WHERE n.NodeID = @nodeId
```

`PollNow` returns `System.Void`, so "it worked" means `LastSync` moved, not that the call
returned 200. See [../swis/invoke-verbs.md](../swis/invoke-verbs.md).

## Removing and disabling a poller

Two different operations with two different consequences.

**Disabling** sets `Enabled = FALSE` and leaves the row and its history in place:

```powershell
$uri = Get-SwisData $swis @'
SELECT TOP 1 p.Uri
FROM Orion.Pollers p
WHERE p.NetObjectType = 'N' AND p.NetObjectID = @nodeId AND p.PollerType = @type
'@ @{ nodeId = 42; type = 'N.Cpu.SNMP.CiscoGen3' }

Set-SwisObject $swis -Uri $uri -Properties @{ Enabled = $false }
```

**Deleting** removes the assignment:

```powershell
Remove-SwisObject $swis -Uri $uri
```

Prefer disabling while you are diagnosing something, because it is one property update to
reverse. Neither official sample sets `Enabled` on create, so what your server defaults it to
is worth reading back once rather than assuming; query 5 below finds the assignments that are
present but switched off, which is a state that looks exactly like healthy monitoring from
every other angle.

## Letting the platform choose the pollers

Hand-picking type strings is right when you know the device and are creating a hundred of the
same thing. It is wrong when you do not know what the device supports. For that, the platform
has two mechanisms that probe the device and assign the appropriate pollers themselves.

### Interfaces: discover, then add with default pollers

`Orion.NPM.Interfaces` carries a two-verb pair for exactly this, and the second one takes the
poller decision as an argument:

| Verb | Signature | Right |
|:---|:---|:---|
| `DiscoverInterfacesOnNode` | `(nodeId)` | `manageNodes` |
| `AddInterfacesOnNode` | `(nodeId, interfacesToAdd, pollers)` | `manageNodes` |

`DiscoverInterfacesOnNode` runs a lite discovery and returns a `LiteDiscoveryResult`:
a `DiscoveredInterfaces` array plus a `Result` code, where SolarWinds documents `0` as success,
`1` as invalid node and `2` as a generic error. Each discovered interface carries `ifIndex`,
`Caption`, `ifType`, `ifSubType`, `InterfaceID`, `Manageable`, `ifSpeed`, `ifAdminStatus` and
`ifOperStatus`. **`InterfaceID` is `0` for an interface that is not yet monitored**, which is
how you tell the new ones from the ones already there.

`AddInterfacesOnNode` takes the subset you want and a `pollers` argument that is an enumeration
with exactly two values, `AddDefaultPollers` or `AddNoPollers`:

```powershell
$discovered = Invoke-SwisVerb $swis 'Orion.NPM.Interfaces' 'DiscoverInterfacesOnNode' @($nodeId)

# Only the interfaces Orion is not already monitoring, and only the ones that are up.
$toAdd = $discovered.DiscoveredInterfaces.DiscoveredLiteInterface |
    Where-Object { $_.InterfaceID -eq 0 -and $_.ifOperStatus -eq 1 }

Write-Host "Adding $($toAdd.Count) interface(s) on node $nodeId"

Invoke-SwisVerb $swis 'Orion.NPM.Interfaces' 'AddInterfacesOnNode' @(
    $nodeId,
    $toAdd,
    'AddDefaultPollers'
) | Out-Null
```

The exact shape the verb result takes when it comes back through `Invoke-SwisVerb` is a
serialisation detail of the PowerShell client rather than a schema fact, and it is
**not verified here**; inspect `$discovered` once interactively before writing the filter, and
adjust the property path. SolarWinds' own
[`NPM.DiscoverAndAddInterfacesOnNode.ps1`](https://github.com/solarwinds/OrionSDK/blob/master/Samples/PowerShell/NPM.DiscoverAndAddInterfacesOnNode.ps1)
sample is the reference for that.

**`AddDefaultPollers` is the important part of this page in one word.** It is the only place in
the API where something else decides the poller set for you, and it is why adding interfaces
through this verb is materially better than creating `Orion.NPM.Interfaces` rows by CRUD and
then guessing at four `I.*` type strings. `AddNoPollers` exists for the case where you want the
interface to exist without being polled, which is rarer than it sounds.

### Nodes: the list resources job

For a node that already exists, `Orion.Nodes` carries a seven-verb job API that runs the same
probe the console's "List Resources" page runs, returns what it found as a selectable tree, and
imports your choices, creating the poller assignments as a side effect.

| Verb | Signature | Purpose |
|:---|:---|:---|
| `ScheduleListResources` | `(nodeId)` | Starts the job. Returns a job id string. |
| `GetScheduledListResourcesStatus` | `(jobId, nodeId)` | Poll until it says `ReadyForImport`. |
| `GetListResourcesResult` | `(jobId, nodeId)` | The tree of what was found. |
| `ImportListResourcesResult` | `(jobId, nodeId)` | Import everything. Returns boolean. |
| `ImportSelectedListResourcesResult` | `(jobId, nodeId, resources)` | Import an edited tree. |
| `GetScheduledListResourcesStatusByEngine` | `(jobId, engineId)` | The engine-wide variants, for |
| `GetListResourcesResultByEngine` | `(jobId, engineId)` | bulk jobs across many nodes. |

All require `manageNodes`. An eighth verb starts the same job against a device that is not a
node yet, so it needs the credentials the node id would otherwise have supplied, and everything
after it is identical:

`ScheduleListResourcesForAddress(ipAddress, port, credentialsType, credentialProperties, engineId, preferredSnmpVersion?)`

The flow, adapted from SolarWinds'
[`ImportSelectedListResources_CPUMemory.ps1`](https://github.com/solarwinds/OrionSDK/blob/master/Samples/PowerShell/ImportSelectedListResources_CPUMemory.ps1),
which turns on CPU and memory monitoring for one node without knowing which poller type that
device needs:

```powershell
$jobId = Invoke-SwisVerb $swis 'Orion.Nodes' 'ScheduleListResources' @($nodeId)

$deadline = (Get-Date).AddMinutes(10)
do {
    Start-Sleep -Seconds 5
    $status = Invoke-SwisVerb $swis 'Orion.Nodes' 'GetScheduledListResourcesStatus' `
        @($jobId.'#text', $nodeId)
    Write-Host "job $($jobId.'#text'): $($status.'#text')"
} while ($status.'#text' -ne 'ReadyForImport' -and (Get-Date) -lt $deadline)

if ($status.'#text' -ne 'ReadyForImport') { throw 'List Resources job did not complete.' }

$results = Invoke-SwisVerb $swis 'Orion.Nodes' 'GetListResourcesResult' @($jobId.'#text', $nodeId)

# Select the branch you want by its display name, set IsSelected, then import that tree.
$branch = $results.DiscoveryResultExportItem.Children.DiscoveryResultExportItem |
    Where-Object { $_.DisplayName.'#text' -eq 'CPU & Memory' }
$branch.IsSelected = 'true'

Invoke-SwisVerb $swis 'Orion.Nodes' 'ImportSelectedListResourcesResult' `
    @($jobId.'#text', $nodeId, $results) | Out-Null
```

Two things about that sample are worth carrying over. The status string to wait for is
`ReadyForImport`, and the loop needs a deadline, which the original does not have. And the tree
it manipulates is XML whose element and display names are runtime data rather than schema, so
the exact `DisplayName` values are **not verified here**; dump `$results` once for the device
family you are automating and read the names off it.

The whole discovery side of this, including network sonar for devices that do not exist in
Orion yet, is in [../automation/discovery.md](../automation/discovery.md).

### What discovery found, before you import it

`Orion.DiscoveredPollers` is the record of poller types a discovery profile turned up. It has
five properties, `read` only, and requires `manageNodes` even to read:

| Property | Type |
|:---|:---|
| `ID` | `System.Int64` |
| `ProfileID` | `System.Int32` |
| `NetObjectID` | `System.Int32` |
| `NetObjectType` | `System.String` |
| `PollerType` | `System.String` |

Its `NetObjectType`, `NetObjectID` and `PollerType` line up exactly with `Orion.Pollers`, which
makes the gap between the two directly queryable. Query 6 below does that, and it is the
cheapest way to answer "what did discovery find on this device that we are not actually
collecting".

## Polling parameters

Assigning a poller says *what* is collected. Three properties on the object say *how often*.
SolarWinds documents the first two on
[How To Set Polling Parameters On A Node](https://solarwinds.github.io/OrionSDK/docs/network-performance-monitor/how-to-set-polling-parameters-on-a-node/),
with the sample values below; the third is a real property on all three entities but that page
does not mention it.

| Property | Unit | Sample value | What it governs |
|:---|:---|---:|:---|
| `PollInterval` | seconds | 120 | How often status is polled |
| `RediscoveryInterval` | minutes | 30 | How often the node is re-examined for what it is |
| `StatCollection` | minutes | not published | How often statistics are collected |

The units come from the schema descriptions on `Orion.NPM.Interfaces`, which are the only ones
of the three sets that carry them: "Interval of polling interface in seconds", "Interval of
rediscovery interface in minutes", "Interval of collecting statistics for interface in
minutes". **`StatCollection`'s default is not recorded in the published schema** and is not
verified here; read it off an existing object before you assume one.

All three are plain properties, so changing them is a CRUD update against the object's URI:

```powershell
Set-SwisObject $swis -Uri $nodeUri -Properties @{
    PollInterval        = 300
    RediscoveryInterval = 60
    StatCollection      = 15
}
```

`Orion.Volumes` and `Orion.NPM.Interfaces` carry the same three properties, so the same update
works per interface and per volume.

Two other places hold polling configuration.

**`Orion.NodeSettings`** is per-node key and value: `NodeSettingID`, `NodeID`, `SettingName`,
`SettingValue`. It is how a node points at a WMI credential
(`SettingName = 'WMICredential'`) and how per-technology settings such as a CLI port are set.
SolarWinds' example is a `CLI.Port` setting with value `22`.

```sql
SELECT ns.NodeSettingID, ns.NodeID, ns.SettingName, ns.SettingValue
FROM Orion.NodeSettings ns
WHERE ns.NodeID = @nodeId
ORDER BY ns.SettingName
```

**`Orion.Settings`** is the global advanced settings table: `SettingID` as a string key, plus
`Name`, `Description`, `Units`, `Minimum`, `Maximum`, `CurrentValue`, `DefaultValue` and
`Hint`. Both value columns are `System.Single`, so every setting is a number even when it is
logically a boolean. Changing one requires `admin`.

```sql
SELECT s.SettingID, s.Name, s.CurrentValue, s.DefaultValue, s.Units, s.Minimum, s.Maximum
FROM Orion.Settings s
WHERE s.SettingID LIKE @pattern
ORDER BY s.SettingID
```

The individual `SettingID` values are installation data rather than schema, and they are
**not recorded in the published schema**. SolarWinds' page names
`NPM_Settings_Routing_VRF_PollInterval` and `WLP_Settings_PollRogues` as examples. Find the
one you want with the `LIKE` query above rather than guessing at it.

## Deciding where the load should go

Every poller assignment is work for the engine that owns the object. Adding monitoring is
adding load, so the two questions to answer before a bulk assignment are how much capacity each
engine has and how much of it is already committed.

**Achieved load** is `Orion.Engines`. `PollingCompletion` should sit in the high 90s; below
that, the engine cannot finish its cycle in the time available.

```sql
SELECT e.EngineID, e.ServerName, e.ServerType, e.Elements, e.Nodes,
       e.Interfaces, e.Volumes, e.Pollers, e.PollingCompletion,
       e.MinutesSinceKeepAlive
FROM Orion.Engines e
ORDER BY e.EngineID
```

`e.Pollers` is the engine's own count of poller assignments, which is the closest thing to a
direct measure of how much this page's subject is costing you.
`MinutesSinceKeepAlive` climbing means the engine is not reporting in at all, which invalidates
everything else in the row.

**Configured load** is `Orion.PollingUsage`, which expresses the same thing as a percentage of
the engine's licensed job weight. Anything over 100 means intervals are being stretched across
the board:

```sql
SELECT pu.EngineID, pu.Engine.ServerName, pu.ScaleFactor, pu.CurrentUsage, pu.IsExceeded
FROM Orion.PollingUsage pu
ORDER BY pu.CurrentUsage DESC
```

Moving a node between engines is a CRUD update of `EngineID` and nothing else; SolarWinds
documents it on
[How To Distribute Load Between Pollers](https://solarwinds.github.io/OrionSDK/docs/network-performance-monitor/how-to-distribute-load-between-pollers/)
and it is covered in full, including the reachability warning that matters more than the
mechanics, in
[../automation/node-management.md](../automation/node-management.md#reassigning-a-node-to-a-different-polling-engine).

The platform can also do this itself. Engine Load Balancing records what it moved and lets you
exclude nodes from being moved:

```sql
SELECT TOP 100 r.Id, r.NodeId, r.SourceEngineId, r.TargetEngineId, r.ReassignmentTimestamp
FROM Orion.ELB.NodeReassignments r
WHERE r.ReassignmentTimestamp >= @startUtc
ORDER BY r.ReassignmentTimestamp DESC
```

`Orion.ELB.NodeExclusions` is the single-column opt-out list (`NodeId`), writable under
`manageNodes`. Whether ELB is switched on is a per-pool setting: see the `ElbEnabled` property
and the `ElbEnable` and `ElbDisable` verbs in
[../automation/high-availability.md](../automation/high-availability.md#load-balancing).

Reducing configured load without moving anything is equally legitimate. Raising `PollInterval`
and `StatCollection` on low-priority nodes, or deleting poller assignments nobody looks at, both
reduce work.

## Worked queries

Every query below was validated against the 2026.2 schema with
`python3 tools/validate_swql.py`.

### 1. Nodes that are not being polled at all

The check to run after any bulk import, and the query that explains the whole page.

```sql
SELECT n.NodeID, n.Caption, n.IPAddress, n.ObjectSubType, n.EngineID
FROM Orion.Nodes n
WHERE NOT EXISTS (
    SELECT p.PollerID
    FROM Orion.Pollers p
    WHERE p.NetObjectType = 'N'
      AND p.NetObjectID = n.NodeID
)
ORDER BY n.Caption
```

`NOT EXISTS` with a correlated subquery rather than a `LEFT JOIN ... IS NULL`, because the
correlated form lets the `NetObjectType` filter sit inside the subquery where it belongs. A node
in this result is invisible monitoring: it exists, it looks configured, and it collects nothing.

The softer version, which finds the half-configured ones, is a count per node:

```sql
SELECT n.Caption, n.ObjectSubType, COUNT(p.PollerID) AS PollerCount
FROM Orion.Nodes n
LEFT JOIN Orion.Pollers p
    ON p.NetObjectID = n.NodeID
   AND p.NetObjectType = 'N'
GROUP BY n.Caption, n.ObjectSubType
ORDER BY COUNT(p.PollerID)
```

Ascending, so the sparsest nodes come first. **The `NetObjectType` predicate has to be in the
`ON` clause**, not the `WHERE` clause: in the `WHERE` clause it would discard the unmatched
rows a `LEFT JOIN` exists to keep, turning the query back into an inner join and hiding exactly
the nodes you are looking for.

### 2. Which pollers one node has

```sql
SELECT p.PollerID, p.PollerType, p.NetObject, p.Enabled, p.Uri
FROM Orion.Pollers p
WHERE p.NetObject = @netObject
ORDER BY p.PollerType
```

Filtering on `NetObject` with a value of `'N:42'` is equivalent to filtering on the type and id
pair, and it is the form to use when you already have a NetObject string in hand from a verb
call or an alert.

### 3. Nodes missing a whole category of collection

The generalisation of "why is there no CPU chart".

```sql
SELECT n.NodeID, n.Caption, n.IPAddress, n.ObjectSubType
FROM Orion.Nodes n
WHERE n.ObjectSubType = 'SNMP'
  AND n.UnManaged = FALSE
  AND NOT EXISTS (
      SELECT p.PollerID
      FROM Orion.Pollers p
      WHERE p.NetObjectType = 'N'
        AND p.NetObjectID = n.NodeID
        AND p.PollerType LIKE 'N.Cpu.%'
  )
ORDER BY n.Caption
```

`LIKE 'N.Cpu.%'` rather than an equality test, because there are 36 CPU poller types and the
right one depends on the device. Any of them satisfies the question.

`UnManaged = FALSE` filters out nodes that are deliberately in a maintenance window, which is
the standard way to keep this kind of report about things that are actually wrong rather than
things that are actually planned. `UnManaged` is inherited from `System.ManagedEntity` and is
queryable on `Orion.Nodes` even though the entity does not declare it. See
[../automation/maintenance-mode.md](../automation/maintenance-mode.md).

Substitute `N.Memory.%`, `N.Uptime.%` or `N.Topology%` for the other categories. Note the last
one has no dot: the topology types split into `N.Topology`, `N.Topology_CDP`,
`N.Topology_Layer2` and six more families, so a dot after `Topology` would miss most of them.

### 4. What is assigned across the estate

```sql
SELECT p.NetObjectType, p.PollerType, COUNT(p.PollerID) AS Assignments
FROM Orion.Pollers p
GROUP BY p.NetObjectType, p.PollerType
ORDER BY COUNT(p.PollerID) DESC
```

This is both an inventory and, as described above, the practical allowlist of poller type
strings that work on this server. A type with an assignment count of one or two, sitting among
types with counts in the hundreds, is usually either a genuine special case or a typo somebody
made once.

### 5. Assignments that exist but are switched off

```sql
SELECT p.PollerID, p.PollerType, p.NetObject, p.NetObjectType, p.NetObjectID, p.Enabled
FROM Orion.Pollers p
WHERE p.Enabled = FALSE
ORDER BY p.NetObjectType, p.PollerType
```

A disabled assignment is indistinguishable from a healthy one in query 1 and in query 3, and it
collects nothing. This is the third state people forget exists, after "assigned" and "not
assigned".

### 6. What discovery found that you are not collecting

```sql
SELECT dp.ID, dp.ProfileID, dp.NetObjectType, dp.NetObjectID, dp.PollerType
FROM Orion.DiscoveredPollers dp
WHERE NOT EXISTS (
    SELECT p.PollerID
    FROM Orion.Pollers p
    WHERE p.NetObjectType = dp.NetObjectType
      AND p.NetObjectID = dp.NetObjectID
      AND p.PollerType = dp.PollerType
)
ORDER BY dp.NetObjectType, dp.PollerType
```

The three columns line up between the two entities, so the anti-join is exact. Every row here is
something a discovery profile determined the device supports and which is not being collected,
usually because somebody unticked it in the import wizard. Reading `Orion.DiscoveredPollers`
requires `manageNodes` even though it is a read.

### 7. Interfaces and volumes with no pollers

The same blind spot as query 1, one level down, and more common because interfaces are usually
created in bulk.

```sql
SELECT i.InterfaceID, i.Caption, i.Node.Caption AS NodeCaption, i.ObjectSubType
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
SELECT v.VolumeID, v.Caption, v.VolumeType, v.Node.Caption AS NodeCaption
FROM Orion.Volumes v
WHERE NOT EXISTS (
    SELECT p.PollerID
    FROM Orion.Pollers p
    WHERE p.NetObjectType = 'V'
      AND p.NetObjectID = v.VolumeID
)
ORDER BY v.Node.Caption, v.Caption
```

An interface created with `AddNoPollers`, or by a CRUD create that forgot the second half, lands
here. `Orion.NPM.Interfaces` and `Orion.Volumes` both navigate to their node through `Node`,
which `Orion.Pollers` cannot do.

## Gotchas

**Creating an object does not monitor it.** A node, an interface or a volume created through
CRUD collects nothing until `Orion.Pollers` rows exist for it. Nothing errors, nothing warns,
and the console shows a perfectly normal-looking object. This is the entire reason this page
exists.

**Always filter `NetObjectType` as well as `NetObjectID`.** Node 42, interface 42 and volume 42
all have `NetObjectID = 42`. A join on the id alone mixes them, and the result looks plausible.

**`Orion.Pollers` has no navigation properties.** It reaches nothing and nothing reaches it, in
either direction. Every combination with `Orion.Nodes`, `Orion.NPM.Interfaces` or
`Orion.Volumes` is a manual join.

**`PollerType` is an unvalidated string.** A typo creates a row that collects nothing and looks
identical to a working assignment in every query on this page. Copy the string from a working
object, not from a document.

**The published catalogue is incomplete.** It lists 124 types, all `N.` or `V.`, and does not
include the `N.Status.*.Native` and `N.ResponseTime.*.Native` pollers that SolarWinds' own
samples and how-to pages use, nor any interface poller. Treat it as a reference, not an
allowlist.

**CPU and memory poller types are device-family specific.** `N.Cpu.SNMP.CiscoGen3` walks
`CISCO-PROCESS-MIB` and returns nothing from a non-Cisco device. The 36 CPU and 37 memory types
in the catalogue exist because there is no generic answer; `HrProcessorLoad` and `HrStorage` are
the host-resources-MIB fallbacks.

**Status and response time stay ICMP even on a WMI or SNMP node.** Both official samples do
this, and it is correct: up and down is a ping question.

**Creating the same assignment twice is not prevented.** Nothing enforces uniqueness, so a
rerun after a partial failure accumulates duplicates. Check before creating.

**`Enabled = FALSE` is a third state.** Neither official sample sets `Enabled` on create. An
assignment that exists and is disabled passes every "does this node have pollers" check and
collects nothing.

**A UnDP is not an `Orion.Pollers` row**, and neither is a Device Studio poller, a
technology polling assignment or an API poller. Four other systems collect against the same
objects through different entities, and a query on this page sees none of them. See
[README.md](README.md).

**Adding pollers adds load.** Check `Orion.Engines.PollingCompletion` and
`Orion.PollingUsage.IsExceeded` before a bulk assignment, not after the polling cycle starts
overrunning.

**Account limitations filter silently.** A service account running query 1 can see fewer nodes
than you do, so "every node has pollers" from one account is not the same statement from
another.


## Related pages

- [README.md](README.md) for the other four polling systems and how to tell them apart.
- [universal-device-pollers.md](universal-device-pollers.md) for UnDPs, the system most often
  mistaken for this one.
- [../automation/node-management.md](../automation/node-management.md) for the first half of
  the operation: creating the node these pollers attach to, and for moving one between engines.
- [../automation/discovery.md](../automation/discovery.md) for network sonar and the full list
  resources treatment.
- [../automation/maintenance-mode.md](../automation/maintenance-mode.md) for `UnManaged`, which
  stops polling without touching poller assignments.
- [../automation/high-availability.md](../automation/high-availability.md) for what happens to
  an engine's polling responsibilities when a pool fails over.
- [../modules/agents.md](../modules/agents.md) for `N.StatusAndResponseTime.Agent.Native` and
  for why `pollerId` on the agent verbs is an engine id rather than a `PollerID`.
- [../modules/npm.md](../modules/npm.md) for `Orion.NPM.Interfaces` in its module context.
- [../platform/architecture.md](../platform/architecture.md) for polling engines, element
  counts and where a poller actually runs.
- [../swis/crud.md](../swis/crud.md) for the create, update and delete mechanics.
- [../swis/uris.md](../swis/uris.md) for why you select `Uri` rather than building it.
- [../swis/invoke-verbs.md](../swis/invoke-verbs.md) for `DiscoverInterfacesOnNode`,
  `AddInterfacesOnNode` and the list resources job verbs.
- [../reference/netobject-types.md](../reference/netobject-types.md) for the `N`, `I` and `V`
  prefixes.

## Official SolarWinds documentation

- [Poller Types](https://solarwinds.github.io/OrionSDK/docs/poller-types/), the catalogue of
  124 poller type strings with their OIDs and WMI queries
- [How To Assign Specific Poller To A Node](https://solarwinds.github.io/OrionSDK/docs/network-performance-monitor/how-to-assign-specific-poller-to-a-node/)
- [How To Set Polling Parameters On A Node](https://solarwinds.github.io/OrionSDK/docs/network-performance-monitor/how-to-set-polling-parameters-on-a-node/)
- [How To Distribute Load Between Pollers](https://solarwinds.github.io/OrionSDK/docs/network-performance-monitor/how-to-distribute-load-between-pollers/)
- [How To Specify Interfaces, Volumes, HW Sensors, Applications and Components To Be Monitored On A Node](https://solarwinds.github.io/OrionSDK/docs/network-performance-monitor/how-to-specify-interfaces-volumes-hw-sensors-applications-components-to-be-monitored-on-a-node/)
- [Polling Engine Load Balancing](https://solarwinds.github.io/OrionSDK/docs/polling-engine-load-balancing/)
- [`CRUD.AddNode.ps1`](https://github.com/solarwinds/OrionSDK/blob/master/Samples/PowerShell/CRUD.AddNode.ps1)
  and [`CRUD.AddInterface.ps1`](https://github.com/solarwinds/OrionSDK/blob/master/Samples/PowerShell/CRUD.AddInterface.ps1),
  the canonical create-then-assign pattern
- [`ImportSelectedListResources_CPUMemory.ps1`](https://github.com/solarwinds/OrionSDK/blob/master/Samples/PowerShell/ImportSelectedListResources_CPUMemory.ps1),
  the list resources job worked end to end

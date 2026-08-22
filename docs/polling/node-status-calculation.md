# How node status is calculated

A node's status is not a reading. It is a **calculation**, and by 2026.2 it combines three
independent inputs: what ICMP says about the node itself, whether the other pollers are
failing, and the state of the node's child objects and thresholds. Two nodes both showing
Critical can be Critical for entirely unrelated reasons.

This matters for automation more than for the console. A report filtered on `Status = 2`
("Down") will not find a node that is Critical because its SNMP credentials broke, and an
alert built on the assumption that status reflects reachability will fire on the wrong things
once enhanced calculation is on — which, on a new installation, it is by default.

**Source.** SolarWinds documents the mechanism in *Calculate node status in the SolarWinds
Platform* and *Status Rollup Mode in the SolarWinds Platform*. What this page adds is the
mapping from that behaviour to the SWIS entities that implement it, which SolarWinds does not
publish. The entity and property names here are checked against the 2026.2 schema like
everything else in this repository; the behaviour is quoted from SolarWinds and marked where
this repository cannot confirm it.

## The three inputs

### 1. The node's own reachability, by ICMP

The default. The platform sends a ping. If no response comes back, the node moves to
**Warning** and is fast-polled for **120 seconds**. If it still does not answer, it is marked
**Down**.

ICMP only tells you a response did not arrive. The device may be fine and something between
you and it may not be — a routing problem, a downed intermediary, a dropped packet. That is
why child objects are polled by SNMP instead: the device itself reports the sub-element state,
which is a stronger claim than silence.

### 2. Polling errors, independent of ICMP

**Sustained SNMP, WMI or WinRM polling errors move a node to Critical even while ICMP reports
it Up.** The usual causes are wrong credentials on the node or a WinRM configuration problem.
The default threshold is **10 minutes** of continuous failure; when polling succeeds again the
status resets and the error clears.

This exists to stop the failure mode where a node sat green for months while the data behind
it was never arriving.

The switch is in Advanced Configuration, not in Polling Settings:

```text
https://<your-server>/Orion/Admin/advancedconfiguration/global.aspx
```

Find **`PollerErrorMonitoringPeriodInMinutes`**. Set it to the number of minutes errors must
persist, or to **`0` to disable the behaviour entirely**.

The state is readable from SWIS, on a property SolarWinds does not document as being connected
to this feature:

```sql
SELECT n.Caption, n.IsPollingError, n.Status, n.StatusDescription
FROM Orion.Nodes n
WHERE n.IsPollingError = 'True'
```

`Orion.Nodes.IsPollingError` is a `System.Boolean` and carries no summary text in the schema.
That it is the flag behind this feature is the obvious reading of the name and is
**unverified here** — confirm by breaking a test node's SNMP credential and watching the
column.

### 3. Child objects and thresholds — "enhanced" calculation

Enhanced node status calculation folds two further things into the node's status:

- **Node thresholds**, both global and per-node — CPU load, percent packet loss, memory usage,
  response time.
- **Child objects** — interfaces, hardware health, applications, volumes, custom pollers,
  virtualization entities, UDT ports.

It is **on by default on new installations**. An installation upgraded from an older version
may still be on classic calculation and has to be switched over deliberately.

```text
Settings > All Settings > Polling Settings > Node Status calculation > Enhanced
```

**Before you enable it, pause alert actions.** SolarWinds recommends
**Alerts & Activity > Alerts > More > Pause actions of all alerts** first, then reviewing what
becomes active, tuning the alerts that should not have fired, and re-enabling actions. Turning
this on changes what a large number of existing alert conditions evaluate to, all at once.

## What the switch changes elsewhere

Enhanced calculation is not confined to the node's own status field. SolarWinds names four
places the change surfaces:

| Where | What changes |
| --- | --- |
| **Intelligent Maps** | Mapped objects show the status of the components that fed the node status |
| **Groups** | Only nodes can form a group, and every child object's status is reflected through them |
| **Alerts** | Thresholds and child entities now move node status, so per-metric and per-child alert definitions become redundant |
| **Node tooltips** | Hovering a Critical node lists the child entities causing it |

The Groups consequence is the one that catches people mid-migration: a group built from
interfaces under classic calculation is not expressible the same way afterwards.

## The two root-cause variables

Because a node can now be Critical for reasons that are nowhere in its own row, SolarWinds
added two alert variables that render the reason:

```text
${N=SwisEntity;M=NodeStatusRootCause}
${N=SwisEntity;M=NodeStatusRootCauseWithLinks}
```

Put either in a trigger action message and the notification carries the thresholds that were
crossed and the child objects in a degraded state. The `WithLinks` variant renders as HTML
with each object hyperlinked, so use it for email and the plain one for anything that is not
going to be rendered.

Both resolve to real properties on `Orion.Nodes`, so the same text is available to a query:

```sql
SELECT n.Caption, n.PolledStatus, n.Status, n.StatusDescription, n.NodeStatusRootCause
FROM Orion.Nodes n
WHERE n.Status <> n.PolledStatus
ORDER BY n.Caption
```

That query is the diagnostic for this whole page: **every row is a node whose calculated
status differs from its own polled status**, which is precisely the set that enhanced
calculation is responsible for. See [../webui/variables.md](../webui/variables.md) for what
`${N=…;M=…}` is doing.

## Reading the root cause structurally

The variables render a string. For automation you want the rows behind it, and there is an
entity for exactly that:

```sql
SELECT d.NodeID, d.Name, d.EntityType, d.Status, d.StatusRanking, d.DetailsUrl
FROM Orion.NodeChildStatusDetail d
WHERE d.NodeID = @nodeId
ORDER BY d.StatusRanking DESC
```

`Orion.NodeChildStatusDetail` is described in the schema as *"Provides list of node child
entities that affect current enhanced node status"* — one row per contributing child, with the
entity type, its status and a link to it. `StatusRanking` orders them by severity, so the
first row is the reason.

**This is the structured form of `NodeStatusRootCause`**, and it is the right thing to call
from an integration that has to route an alert by cause rather than print a sentence.

## Which contributors are switched on

The contributor list is per-installation and depends on which modules are installed:

```text
Settings > All Settings > Thresholds & Polling > Node Child Status Participation
```

SolarWinds recommends keeping the defaults. The settings themselves are a SWIS entity, and an
unusually accessible one:

```sql
SELECT p.ModuleName, p.EntityType, p.Enabled, p.Installed
FROM Orion.NodeChildStatusParticipation p
WHERE p.Installed = 'True'
ORDER BY p.ModuleName, p.EntityType
```

```bash
python3 tools/schema_query.py show Orion.NodeChildStatusParticipation
```

**It declares `update` under `admin`.** So the participation settings are writable through the
API, not only through the console — which makes "the same status contributors on every server"
something you can enforce from a script rather than a checklist. Whether writing `Enabled`
takes effect without a service restart is **not documented and unverified here**; change one
on a test server and watch a node's status before you roll it out.

### The contributors are a single inheritance family

Eight entities inherit from `Orion.NodeChildStatusContributors`, one per contributing
subsystem:

| Entity | Contributes |
| --- | --- |
| `Orion.NPM.NodeChildStatusInterfaces` | Interface status |
| `Orion.NPM.NodeChildStatusCustomPollers` | Custom poller status |
| `Orion.NodeChildStatusThresholds` | Threshold breaches |
| `Orion.NodeChildStatusVolumes` | Volume status |
| `Orion.APM.NodeChildStatusApplications` | SAM application status |
| `Orion.HardwareHealth.NodeChildStatusHardwareHealth` | Hardware health |
| `Orion.UDT.NodeChildStatusPorts` | UDT port status |
| `Orion.VIM.NodeChildStatusEntities` | Virtualization entities |

Because they share a base, **one query against the base entity covers every installed module**
without knowing which ones you have:

```sql
SELECT c.NodeID, c.Name, c.EntityType, c.Status, c.DetailsUrl
FROM Orion.NodeChildStatusContributors c
WHERE c.Status <> 1
```

The base is described as *"Base entity for modules to plug into enhanced node child status"*,
so the list above is what 2026.2 ships and a module you add later joins it. `EntityType` tells
you which subsystem each row came from. See
[../schema/entity-model.md](../schema/entity-model.md) for why querying a base entity returns
its descendants.

## Status rollup mode

Rollup mode decides **how** the inputs combine. Three options, set per node under
**Edit Node**:

| Mode | Result |
| --- | --- |
| **Worst** | The node takes the worst status among the configured contributors |
| **Best** | The node takes the best status among them |
| **Mixed** | *(default)* The contributors are combined by the table below |

### The Mixed truth table

This is SolarWinds' own table, reproduced because it is the only place the combination rule is
written down. Read it as: given the node's own polled status and two children, this is what
the node ends up as.

| Final node status | Polled status | Child 1 | Child 2 |
| --- | --- | --- | --- |
| Critical | Up or Warning | Up | Critical |
| Critical | Up or Warning | Down | Critical |
| Down | Down | any | any |
| Warning | Up or Warning | Up | Warning |
| Warning | Up or Warning | Up | Down |
| Warning | Up or Warning | Up | Unreachable |
| Warning | Warning | Up | Unknown |
| Warning | Up or Warning | Down | Warning |
| Warning | Up or Warning | Down | Unknown |
| Warning | Up or Warning | Down | Down |
| Warning | Warning | Unknown | Unknown |
| Up | Up | Up | Up |
| Up | Up | Up | Unknown |
| Up | Up | Up | Shutdown |
| Up | Up | Unknown | Unknown |
| Unmanaged | Unmanaged | any | any |
| Unreachable | Unreachable | any | any |
| *child status* | External | any | any |

Three things worth extracting from it, because they are easy to miss in a table this size:

- **A down child does not make the node Down.** It makes it **Warning**. Only the node's own
  polled status being Down produces Down. If your alerting assumes "Down means something under
  it failed", it is wrong under Mixed.
- **Critical is reserved for a Critical child.** Nothing else in the table produces it.
- **Unknown is absorbed.** `Up` + `Up` + `Unknown` is still `Up`. An unknown child does not
  degrade a healthy node.

The reproduction is faithful to SolarWinds' published table. The behaviour of combinations it
does not enumerate — more than two children, or children the table does not pair — is **not
documented and unverified here**.

### Where the mode is stored

`Orion.Nodes` declares no rollup-mode property in 2026.2, so the per-node setting is **not
readable from `Orion.Nodes`** and where it lives is **unverified here**. What the schema does
carry is `Orion.StatusCalculators`, a two-column lookup of `StatusCalculatorID` and `Name`,
and `Orion.Container.StatusCalculator` referring to it — which is the group-level rollup
setting rather than the node-level one.

```bash
python3 tools/schema_query.py show Orion.StatusCalculators
```

## Classic calculation, and what child status means there

Under classic calculation the node's status is ICMP alone and the children are shown as a
**sub-icon** rather than folded in. Its rollup setting is separate and global:

```text
Settings > All Settings > Web Console settings > Child Status Rollup Mode
```

| Option | Sub-icon shows |
| --- | --- |
| Show Worst Status | The worst status of all children |
| Show Worst Status (Interfaces only) | The worst status among interfaces |
| Show Only ICMP status | No sub-icon; node status is ICMP only |

**This is what `Orion.Nodes.ChildStatus` is.** The property is declared `System.Int32` with no
summary text in the schema, and it holds the rolled-up child status that the sub-icon renders,
governed by the setting above. `Orion.StatusInfo.ChildStatusMap` is the corresponding mapping
column on the status lookup.

That the setting governs the column is the reading these two documents support and is
**unverified here** in the sense that no SolarWinds page states the connection in those words.
Compare `ChildStatus` against `Status` on your own server before filtering on it.

## Group and map rollup is a different setting again

Do not confuse the node rollup mode with the one that governs how a **collection** displays —
groups, maps and tree widgets:

```text
Settings > All Settings > Web Console Settings
```

| Option | Behaviour | Example |
| --- | --- | --- |
| **Show Best Status** | The collection shows the best member status | Up + Warning + Down → **Up** |
| **Show Worst Status** | The collection shows the worst | Up + Warning + Down → **Down** |
| **Mixed Status shows Warning** | The worst *warning-type* state; a mix of up and down with no warning-type state gives **Mixed Availability** | Up + Down → **Mixed Availability** |

Show Best Status is what you want for a set of redundant or backup devices, where one member
being up is the condition that matters.

## Classifying a status without hard-coding integers

2026.2 added `Orion.Web.LegacyModules.RollupStatusInfo`, and unlike `Orion.StatusInfo` its
properties **carry summary text**. It gives each status a set of boolean classification flags:

```sql
SELECT
    r.StatusId,
    r.StatusName,
    r.ShortDescription,
    r.RollupWorseStatusRank,
    r.IsCritical,
    r.IsWarning,
    r.IsDown,
    r.IsUp,
    r.IsUnknown,
    r.IsUnmanaged,
    r.IsUnreachable,
    r.IsExternal
FROM Orion.Web.LegacyModules.RollupStatusInfo r
ORDER BY r.RollupWorseStatusRank
```

Those eight flags are exactly the eight status names SolarWinds lists for the platform:
critical, down, external, unknown, unmanaged, unreachable, up and warning. `IsInactive` and
`IsDisabled` are two further flags with no counterpart in that list.

**Use the flags instead of an integer literal.** `WHERE r.IsDown = 'True'` survives SolarWinds
adding a status; `WHERE Status = 2` does not. `RollupWorseStatusRank` is described as *"The
rank for rollup status comparison"*, which makes it the ordering that Worst and Best rollup
use.

The entity is new in 2026.2 — see
[../reference/schema-changes-2026.1-to-2026.2.md](../reference/schema-changes-2026.1-to-2026.2.md).
On an earlier version use `Orion.StatusInfo.Ranking` and
[../schema/status-codes.md](../schema/status-codes.md) instead.

## Excluding something from the calculation

**You cannot exclude a specific entity.** SolarWinds states this plainly: there is no
per-object opt-out. The four things you can do instead:

1. **Remove the entity from monitoring.**
2. **Unmanage it** — see [../automation/maintenance-mode.md](../automation/maintenance-mode.md)
   for doing that through the API with a bounded window.
3. **Change the parent node's rollup mode** so that child's status does not reach it.
4. **Remove the whole entity type from participation**, via Node Child Status Participation —
   which is all-or-nothing for that type across every node.

Option 4 is the one to reach for carefully: it is global, and the entity above makes it
scriptable, which makes it easy to apply more widely than intended.

## What this means for a query you already have

If you maintain reports or alerts written before enhanced calculation:

- **`Status` is no longer a reachability claim.** Filter on `PolledStatus` if reachability is
  what you meant. See [../schema/status-codes.md](../schema/status-codes.md#status-versus-polledstatus).
- **`Status = 2` no longer finds everything that is broken.** A node failing SNMP with ICMP
  fine is `14` (Critical), not `2`.
- **A node can be Critical with every property on its own row looking healthy.** The reason is
  in `Orion.NodeChildStatusDetail`, not in `Orion.Nodes`.
- **Counting nodes by status changes meaning across the upgrade**, so a trend line that spans
  the switch is comparing two different measurements.

## See also

- [../schema/status-codes.md](../schema/status-codes.md) — the status integers themselves, and
  the join that turns them into names
- [../webui/variables.md](../webui/variables.md) — the `${N=…;M=…}` form the root-cause macros
  use
- [../automation/alerts.md](../automation/alerts.md) — building alerts on status
- [standard-pollers.md](standard-pollers.md) — the pollers whose failure drives the Critical
  state described above
- [../swql/gotchas.md](../swql/gotchas.md) — including the `Status` versus `PolledStatus` trap

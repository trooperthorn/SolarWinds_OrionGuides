# Status codes

Every monitored object in Orion carries a status, and it is stored as an integer. The web
console paints it as a coloured icon, but a query returns the raw number, so any report,
alert or automation has to map that number back to something a person can act on.

The schema says so itself. `System.DashboardEntity` declares `Status` as `System.Int32`
with this summary:

> An int value denoting the up/down/warning/etc. status of this entity. The interpretation
> of this int will be application-dependent, but for `Orion.*` entities, you can query
> `Orion.StatusInfo` to see what the different numbers mean.

Two consequences follow. First, `Status` is nearly universal: 290 entities in 2026.2
declare a `Status` property themselves and another 94 inherit one, so 384 entities in the
schema answer to it. Second, the interpretation is
**application-dependent**: the same integer does not mean the same thing on an interface
as it does on an application. The table below is the shared vocabulary, and the sections
after it say which parts of that vocabulary apply where.

## The table

26 status codes.

| Status | Name | Rank | Meaning |
| ---: | --- | ---: | --- |
| 0 | **Unknown** | 495 | Has not been polled yet since being added to the system or coming out of Unmanaged status. For IP SLA operations: when we could not contact the router to collect the results of the IP SLA operation. |
| 1 | **Up** | 500 | Responding fine |
| 2 | **Down** | 110 | Not responding |
| 3 | **Warning** | 220 | For Nodes - node is not responding to pings; if this continues for two minutes, node will be marked Down. For Applications - monitored metric exceeds the warning threshold |
| 4 | **Shutdown** | 496 | Applies to network interfaces only |
| 5 | **Testing** | 480 | Applies to network interfaces only |
| 6 | **Dormant** | 560 | Applies to network interfaces only |
| 7 | **Not Present** | 470 | Applies to network interfaces only |
| 8 | **Lower Layer Down** | 130 | Applies to network interfaces only |
| 9 | **Unmanaged** | 499 | The object is unmanaged (in a maintenance window configured in Orion) |
| 10 | **Unplugged** | 498 | For Interfaces - you can set an interface to be "unpluggable". In this case it will either be Up or Unplugged instead of the usual Up or Down. See the doc. |
| 11 | **External** | 440 | For Nodes - you can configure a node as "external". In this case Orion does not ping the node for Up/Down status, but you can still assign other monitors to it. See the doc. |
| 12 | **Unreachable** | 150 | Object status cannot be determined because it is dependent on another node that is currently down. See the doc. |
| 14 | **Critical** | 210 | Nodes - Monitored Metric exceedes Critical threshold. For Applications - monitored metric exceeds the Critical threshold |
| 15 | **Partly Available** | 230 | Not used for individual objects. |
| 16 | **Misconfigured** | 240 | &mdash; |
| 17 | **Could Not Poll** | 250 | &mdash; |
| 19 | **Unconfirmed** | 270 | &mdash; |
| 22 | **Active** | 540 | &mdash; |
| 24 | **Inactive** | 570 | &mdash; |
| 25 | **Expired** | 580 | &mdash; |
| 26 | **Monitoring Disabled** | 450 | &mdash; |
| 27 | **Disabled** | 460 | &mdash; |
| 28 | **Not Licensed** | 490 | SAM: For Applications - there are more component monitors assigned than there are licenses available. |
| 29 | **Other Category** | 1000 | Never to be placed on an object. CategoryStatusMap allows joining back to StatusInfo to place statues into one of several buckets. This status value is the result of a status that is not "relevant" from an "issue" perspective and deserves to be in the "other" bucket. |
| 30 | **Not Running** | 498 | For SAM processes and IIS Application Pools that are not running. This status is not issue (it is expected state) so it is ignored in final application status roll up. |

The wording in the Meaning column is the source's own, typos included, so that it can be
matched against the original. Six rows have no description at all in the source
(16, 17, 19, 22, 24, 25, 27), and the ids 13, 18, 20, 21 and 23 are absent entirely. A
gap does not prove the id is unused on your server: query `Orion.StatusInfo` there before
concluding anything, using the query at the end of this page.

## What Rank is for

Rank orders severity so that a parent object can compute a status from its children.
**A lower rank is worse.** When a group, a node or any other rollup has to reduce several
child statuses to one, the ordering in this column is what decides which child wins.

Sorted by rank, the vocabulary reads as a severity ladder:

| Rank | Status | Name |
| ---: | ---: | --- |
| 110 | 2 | Down |
| 130 | 8 | Lower Layer Down |
| 150 | 12 | Unreachable |
| 210 | 14 | Critical |
| 220 | 3 | Warning |
| 230 | 15 | Partly Available |
| 240 | 16 | Misconfigured |
| 250 | 17 | Could Not Poll |
| 270 | 19 | Unconfirmed |
| 440 | 11 | External |
| 450 | 26 | Monitoring Disabled |
| 460 | 27 | Disabled |
| 470 | 7 | Not Present |
| 480 | 5 | Testing |
| 490 | 28 | Not Licensed |
| 495 | 0 | Unknown |
| 496 | 4 | Shutdown |
| 498 | 10 | Unplugged |
| 498 | 30 | Not Running |
| 499 | 9 | Unmanaged |
| 500 | 1 | Up |
| 540 | 22 | Active |
| 560 | 6 | Dormant |
| 570 | 24 | Inactive |
| 580 | 25 | Expired |
| 1000 | 29 | Other Category |

Three things in that ordering are worth reading closely, because each one explains a
result that looks wrong at first.

**Down (110) beats Critical (210) beats Warning (220).** A group holding one down node and
fifty warning nodes rolls up as down. That is the intent.

**Unknown (495) sits just below Up (500), not near Down.** An object that has never been
polled, or has just come out of a maintenance window, should not drag a group red before
anyone has looked at it. The same reasoning puts Unmanaged (499) and Unplugged (498) up at
the quiet end: they are administrative states, not faults.

**Ranks above Up are not "better than up", they are "not an issue".** Dormant (560),
Inactive (570) and Expired (580) are states that exist and are being reported, and none of
them should pull a rollup downward. Other Category (1000) is the extreme case, and its own
description says it is "never to be placed on an object" and exists so that
`CategoryStatusMap` can bucket a status as not relevant from an issue perspective.

Because rank is a number you can sort and aggregate on, worst-child rollups are expressible
directly in SWQL. `MIN(Ranking)` is the worst status among the joined rows:

```sql
SELECT
    n.Caption,
    MIN(s.Ranking) AS WorstVolumeRanking
FROM Orion.Nodes n
INNER JOIN Orion.Volumes v ON v.NodeID = n.NodeID
INNER JOIN Orion.StatusInfo s ON s.StatusId = v.Status
GROUP BY n.Caption
ORDER BY MIN(s.Ranking)
```

Rank is not the same thing as `Severity`. `Orion.Nodes` and `Orion.NPM.Interfaces` both
declare `Severity` (`System.Int32`), and the interface one is documented as taking the value
1000 when the status is Down, 1 for Unknown or Warning, and 0 otherwise, which is a coarser
scale running in the opposite direction. Do not mix the two in one comparison.

## Which statuses apply to what

The descriptions carry this information, and getting it wrong produces filters that can
never match. There is no `Status = 6` node, because Dormant is an interface concept.

**Interfaces only.** Shutdown (4), Testing (5), Dormant (6), Not Present (7) and
Lower Layer Down (8) are each described as applying to network interfaces only. Unplugged
(10) is also interface-specific: an interface can be marked "unpluggable", after which it
reports Up or Unplugged instead of Up or Down.

The published schema corroborates part of this independently. `Orion.NPM.Interfaces.Status`
documents its own possible values as:

> Status of interface. Status is calculated from the AdminStatus and OperStatus properties.
> Possible Values: `Unknown = 0`, `Up = 1`, `Down = 2`, `Warning = 3`, `Shutdown = 4`,
> `Unmanaged = 9`, `Unplugged = 10`, `Unreachable = 12`.

That is an eight-value subset, and it does not include Testing, Dormant, Not Present or
Lower Layer Down even though the workbook attributes those to interfaces. The likely reason
is visible in the same schema: those four are values of `OperStatus`, not of `Status`.
`Orion.NPM.Interfaces.OperStatus` documents `Up = 1`, `Down = 2`, `Testing = 3`,
`Unknown = 4`, `Dormant = 5`, `NotPresent = 6`, `LowerLayerDown = 7`, which is the SNMP
`ifOperStatus` enumeration. Note that those numbers are **not** the platform status codes:
`Dormant` is 5 in `OperStatus` and 6 in the status table. Treat `AdminStatus` and
`OperStatus` as their own small enumerations and never join them to `Orion.StatusInfo`.

`AdminStatus` is the shorter one: `Unknown = 0`, `Up = 1`, `Down = 2`, `Testing = 3`. The
classic "administratively up but not passing traffic" query filters on the pair:

```sql
SELECT TOP 100
    i.Node.Caption AS NodeName,
    i.Caption AS InterfaceName,
    i.AdminStatus,
    i.OperStatus,
    i.Status
FROM Orion.NPM.Interfaces i
WHERE i.AdminStatus = 1 AND i.OperStatus <> 1
ORDER BY i.Node.Caption, i.Caption
```

**Applications only.** Not Licensed (28) is described as SAM-specific: more component
monitors are assigned than there are licenses available. Not Running (30) covers SAM
processes and IIS application pools that are not running, and its description adds the
detail that matters for reporting: it "is not issue (it is expected state) so it is ignored
in final application status roll up", which is why an application can show Up while a
component under it shows Not Running.

**Nodes.** External (11) is node-specific: a node configured as external is not pinged for
up/down status, though other monitors still apply. Unreachable (12) is the dependency
status, set when an object's state cannot be determined because a node it depends on is
down. See [../automation/dependencies.md](../automation/dependencies.md).

**Shared, but with different meanings.** Warning (3) and Critical (14) both carry two
readings in the source: for nodes they are about ping behaviour and metric thresholds, and
for applications they are about a monitored metric crossing the warning or critical
threshold. A single dashboard that mixes nodes and applications under one "Warning" label
is combining two different conditions.

**Neither.** Partly Available (15) is described as "not used for individual objects", so it
is a rollup-only value.

## Resolving status on a live server

`Orion.StatusInfo` is the lookup table, and it exists in 2026.2 with 12 properties, all
readable by `everyone`:

| Property | Type |
| --- | --- |
| `StatusId` | `System.Int32` |
| `StatusName` | `System.String` |
| `ShortDescription` | `System.String` |
| `RollupType` | `System.Int32` |
| `Ranking` | `System.Int32` |
| `UiOrder` | `System.Int32` |
| `Color` | `System.String` |
| `IconPostfix` | `System.String` |
| `ChildStatusMap` | `System.Int32` |
| `DefaultIconName` | `System.String` |
| `CategoryStatusMap` | `System.Int32` |
| `DisplayProperties` | `System.String` |

The published 2026.2 schema gives no summary text for any of these twelve, so the names and
types above are verified but their meanings beyond the obvious are unverified. `StatusId`,
`StatusName`, `ShortDescription` and `Ranking` line up with the four columns of the table on
this page, which is the pairing you need in practice. `CategoryStatusMap` is named in the
description of status 29 as the mechanism for bucketing statuses, and `Color`,
`IconPostfix` and `DefaultIconName` are presentation fields. Dump the table on your own
server if you need more:

```sql
SELECT
    s.StatusId,
    s.StatusName,
    s.Ranking,
    s.RollupType,
    s.ShortDescription
FROM Orion.StatusInfo s
ORDER BY s.Ranking
```

That query is also the answer to "is this list current for my version". It costs nothing
and it is authoritative for your server, where this page is authoritative only for 2026.2.

### Joining status to a name

Do not hard-code the integers into a report. Join, and the report keeps working if
SolarWinds adds a status.

```sql
SELECT TOP 100
    n.Caption,
    n.Status,
    s.StatusName,
    s.Ranking,
    s.ShortDescription
FROM Orion.Nodes n
INNER JOIN Orion.StatusInfo s ON s.StatusId = n.Status
WHERE n.UnManaged = FALSE
ORDER BY s.Ranking, n.Caption
```

`WHERE n.UnManaged = FALSE` is not decoration. A node reads Down because it is genuinely
unreachable, or Unmanaged because someone opened a maintenance window, and an availability
report that conflates the two will be wrong every maintenance weekend. See
[../swis/uris.md](../swis/uris.md) and the `Unmanage` verbs in
[../swis/invoke-verbs.md](../swis/invoke-verbs.md) for how objects get into that state.

### Counting by status name

The shape most dashboards actually want. Grouping by `Ranking` as well as `StatusName`
lets the result come back in severity order rather than alphabetically:

```sql
SELECT
    s.StatusId,
    s.StatusName,
    s.Ranking,
    COUNT(n.NodeID) AS NodeCount
FROM Orion.Nodes n
INNER JOIN Orion.StatusInfo s ON s.StatusId = n.Status
GROUP BY s.StatusId, s.StatusName, s.Ranking
ORDER BY s.Ranking
```

The same shape works for applications, and it is worth running once on any new server just
to see which statuses your installation actually produces:

```sql
SELECT TOP 100
    a.Node.Caption AS NodeName,
    a.Name AS ApplicationName,
    a.Status,
    s.StatusName
FROM Orion.APM.Application a
INNER JOIN Orion.StatusInfo s ON s.StatusId = a.Status
ORDER BY s.Ranking, a.Name
```

### Ten entities can navigate instead of joining

Some entities declare a relationship to `Orion.StatusInfo`, which turns the join into a
dotted navigation. Exactly ten do so in 2026.2:

| Entity | Navigation |
| --- | --- |
| `Orion.NPM.Interfaces` | `StatusInfo` |
| `Orion.Volumes` | `StatusInfo` |
| `Orion.VIM.Clusters` | `StatusInfo` |
| `Orion.VIM.DataCenters` | `StatusInfo` |
| `Orion.VIM.Datastores` | `StatusInfo` |
| `Orion.VIM.Hosts` | `StatusInfo` |
| `Orion.VIM.VirtualMachines` | `StatusInfo` |
| `Orion.Cman.Container` | `StatusInfo` |
| `Orion.DPA.DatabaseInstance` | `StatusInfo` |
| `Orion.APIPoller.ApiPoller` | `StatusInfo` |

```sql
SELECT TOP 100
    i.Node.Caption AS NodeName,
    i.Caption AS InterfaceName,
    i.Status,
    i.StatusInfo.StatusName,
    i.StatusInfo.Ranking
FROM Orion.NPM.Interfaces i
WHERE i.UnManaged = FALSE
ORDER BY i.StatusInfo.Ranking, i.Node.Caption
```

**`Orion.Nodes` is not on that list.** There is no `Orion.Nodes.StatusInfo` navigation
property, and writing one is a plausible-looking guess that fails on a live server. For
nodes, applications, components, groups and everything else, use the explicit
`ON s.StatusId = <alias>.Status` join. Confirm for any entity with:

```bash
python3 tools/schema_query.py path Orion.Nodes Orion.StatusInfo
```

which reports only indirect routes through `Orion.Volumes` and the virtualization
entities, not a direct one.

## `Status` versus `PolledStatus`

`Orion.Nodes` declares both `Status` and `PolledStatus`, both `System.Int32`. That much is
verified. How the two differ is **not verified**: the published 2026.2 schema attaches no
summary text to either property, and neither the OrionSDK documentation nor any SolarWinds
sample script in this repository's sources explains it. Do not guess, and do not let a
report guess on your behalf.

Two things you can rely on without running anything:

- `PolledStatus` is declared on `Orion.Nodes` alone. It is the only property named
  `PolledStatus` anywhere in the 19328 properties of the 2026.2 schema, so it is not
  available on `System.ManagedEntity`, not available on interfaces or volumes, and not
  selectable from a base-entity query. `Status` is, because it comes from
  `System.DashboardEntity`.
- Whichever you pick, pick one. A report filtered on `Status` and an alert triggered on
  `PolledStatus` will disagree with each other at exactly the moment somebody is looking,
  and the alert engine will get the blame.

[../swql/gotchas.md](../swql/gotchas.md#3-status-versus-polledstatus-on-orionnodes) has the
two queries that settle the difference on your own server in about a minute.

## Other status-shaped properties to know before writing a filter

Several properties look like status and are not, and mistaking one for another is a quiet
way to build a report that is subtly wrong.

| Property | Type | Where | What to watch for |
| --- | --- | --- | --- |
| `Status` | `System.Int32` | `System.DashboardEntity`, inherited widely | The integer this page is about |
| `PolledStatus` | `System.Int32` | `Orion.Nodes` only | Undocumented relationship to `Status` |
| `ChildStatus` | `System.Int32` | `Orion.Nodes` | A rollup of contributors, not the node's own state |
| `CustomStatus` | `System.Boolean` | `Orion.Nodes` | A boolean flag, not a status code |
| `GroupStatus` | `System.String` | `Orion.Nodes` | A string, so it is not a status integer at all |
| `StatusDescription` | `System.String` | `System.ManagedEntity` | "Textual information about the status of this entity" |
| `StatusLED` | `System.String` | `System.ManagedEntity` | Documented as "A legacy property. Ignore this." |
| `Severity` | `System.Int32` | `Orion.Nodes`, `Orion.NPM.Interfaces` | A different, coarser scale running the other way |
| `UiSeverity` | `System.Int32` | `Orion.Nodes` only | Not present on interfaces |
| `AdminStatus`, `OperStatus` | `System.Int16` | `Orion.NPM.Interfaces` | SNMP enumerations; do not join to `Orion.StatusInfo` |
| `UnManaged` | `System.Boolean` | `System.ManagedEntity` | Filter on this, not on `Status = 9`, when excluding maintenance |

`Orion.ContainerMembers.Status` is worth calling out separately: it is a `System.Int32`
holding the member's status, so group membership listings resolve against
`Orion.StatusInfo` the same way everything else does.

## Related pages

- [key-entities.md](key-entities.md) for the entities whose status you will be reading.
- [netobject-types.md](netobject-types.md) for the other lookup table you need constantly.
- [../swql/gotchas.md](../swql/gotchas.md) for `Status` versus `PolledStatus` in full, and
  the rest of the traps.
- [../automation/dependencies.md](../automation/dependencies.md) for how Unreachable (12)
  is produced.
- [../reference/status-codes.md](../reference/status-codes.md) for the generated version of
  the table, rebuilt by `make docs-reference` on every data refresh.
- [entity-model.md](entity-model.md) for why `Status` is queryable on entities that never
  declare it.

<!-- GENERATED FILE. Do not edit by hand.
     Produced by tools/build_reference_docs.py from data/schema/2026.2/.
     Regenerate with: make docs-reference -->

# Status code reference

Status is stored as an integer on every monitored entity. The web console renders it as a coloured icon, but a query returns the raw number, so any report or automation has to map it back to something meaningful.

**Rank orders severity for rollup, and a lower rank is worse.** When a group or a parent object computes its status from its children, the child with the lowest rank wins. That is why Down (110) beats Warning (220), and why Up (500) loses to almost everything. It also explains the statuses that look odd out of context: Unknown sits at 495, just below Up, because an object that has not been polled yet should not drag a group into a red state.

26 status codes.

| Status | Name | Rank | Meaning |
| ---: | --- | ---: | --- |
| 0 | **Unknown** | 495 | Has not been polled yet since being added to the system or coming out of Unmanaged status. For IP SLA operations: when we could not contact the router to collect the results of the IP SLA operation. |
| 1 | **Up** | 500 | Responding fine |
| 2 | **Down** | 110 | Not responding |
| 3 | **Warning** | 220 | For Nodes - node is not responding to pings; if this continues for two minutes, node will be marked Down. For Applications – monitored metric exceeds the warning threshold |
| 4 | **Shutdown** | 496 | Applies to network interfaces only |
| 5 | **Testing** | 480 | Applies to network interfaces only |
| 6 | **Dormant** | 560 | Applies to network interfaces only |
| 7 | **Not Present** | 470 | Applies to network interfaces only |
| 8 | **Lower Layer Down** | 130 | Applies to network interfaces only |
| 9 | **Unmanaged** | 499 | The object is unmanaged (in a maintenance window configured in Orion) |
| 10 | **Unplugged** | 498 | For Interfaces – you can set an interface to be “unpluggable”. In this case it will either be Up or Unplugged instead of the usual Up or Down. See the doc. |
| 11 | **External** | 440 | For Nodes – you can configure a node as “external”. In this case Orion does not ping the node for Up/Down status, but you can still assign other monitors to it. See the doc. |
| 12 | **Unreachable** | 150 | Object status cannot be determined because it is dependent on another node that is currently down. See the doc. |
| 14 | **Critical** | 210 | Nodes - Monitored Metric exceedes Critical threshold. For Applications – monitored metric exceeds the Critical threshold |
| 15 | **Partly Available** | 230 | Not used for individual objects. |
| 16 | **Misconfigured** | 240 |  |
| 17 | **Could Not Poll** | 250 |  |
| 19 | **Unconfirmed** | 270 |  |
| 22 | **Active** | 540 |  |
| 24 | **Inactive** | 570 |  |
| 25 | **Expired** | 580 |  |
| 26 | **Monitoring Disabled** | 450 |  |
| 27 | **Disabled** | 460 |  |
| 28 | **Not Licensed** | 490 | SAM: For Applications – there are more component monitors assigned than there are licenses available. |
| 29 | **Other Category** | 1000 | Never to be placed on an object. CategoryStatusMap allows joining back to StatusInfo to place statues into one of several buckets. This status value is the result of a status that is not "relevant" from an "issue" perspective and deserves to be in the "other" bucket. |
| 30 | **Not Running** | 498 | For SAM processes and IIS Application Pools that are not running. This status is not issue (it is expected state) so it is ignored in final application status roll up. |

## Resolving status in a query

Do not hard-code these numbers into a report. `Orion.StatusInfo` is the lookup table on a live server, and joining it keeps the query correct if SolarWinds adds a status:

```sql
SELECT n.Caption, n.Status, s.StatusName, s.ShortDescription
FROM Orion.Nodes n
JOIN Orion.StatusInfo s ON n.Status = s.StatusId
ORDER BY s.Ranking, n.Caption
```

Counting by status name, the shape most dashboards want:

```sql
SELECT s.StatusName, COUNT(n.NodeID) AS NodeCount
FROM Orion.Nodes n
JOIN Orion.StatusInfo s ON n.Status = s.StatusId
GROUP BY s.StatusName
ORDER BY COUNT(n.NodeID) DESC
```

For what the ranks mean for rollup, which statuses apply only to interfaces or only to applications, and how to reason about them in a report, see [../schema/status-codes.md](../schema/status-codes.md). This page is the table; that page is the explanation.

One caveat when reporting on outages: a node can be Down because it is genuinely unreachable, or Unmanaged because someone opened a maintenance window. Filter `UnManaged = FALSE` when you mean the former.

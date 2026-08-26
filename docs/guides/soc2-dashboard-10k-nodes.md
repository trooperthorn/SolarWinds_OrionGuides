# A SOC 2–style Modern Dashboard for a 10,000-node environment

A recipe: every SWQL query for a customer/vendor-facing trust dashboard, with the Modern
Dashboard widget type called out for each. The layout follows the SOC 2 Trust Services
Criteria that platform data can actually evidence — **Availability**, **Security /
incident response**, **Capacity**, and **Change management** — so the page reads as an
operational trust report rather than a NOC wall.

Every query below validates against the extracted 2026.2 schema
(`python3 tools/validate_swql.py --docs docs/guides/soc2-dashboard-10k-nodes.md`). The
widget-type semantics, the two-places rule for embedding SWQL, and the KPI
one-query-per-tile rule are in
[../webui/modern-dashboard-authoring.md](../webui/modern-dashboard-authoring.md); read that
before turning these queries into a JSON file.

## Design rules at 10k nodes

Four things separate a dashboard that works at 10,000 nodes from one that times out:

1. **Aggregate on the server, never in the widget.** Every KPI and proportional query below
   returns a handful of rows, not 10,000. The database does the counting.
2. **Every table is `TOP`-bounded and exception-scoped.** A customer-facing dashboard shows
   what is *wrong*, not everything. `TOP 50` down nodes is actionable; 10,000 rows is not.
3. **Exclude `UnManaged` nodes from health math.** A node in a maintenance window is not an
   availability failure, and at this scale there are always some.
4. **Time-bound anything that reads a statistics table.** `Orion.ResponseTime` holds
   detail rows per node per poll; an unbounded scan of it at 10k nodes is the single easiest
   way to hang the page. The 24-hour window below follows the UTC pattern in
   [../swql/date-and-time.md](../swql/date-and-time.md) — arithmetic in local time,
   converted at the end.

One structural reminder: **a KPI widget with six tiles is six separate single-row
queries**, and each query's SWQL is written twice in the file (`dataSource` and
`adapter.properties.dataSource`), byte-identical.

---

## Row 1 — Service health scorecard (`kpi` widget, six tiles)

One `kpi` widget, six tiles, one query per tile. Node `Status` values used here: `1` Up,
`2` Down, `3` Warning; `UnManaged` is the maintenance flag inherited from
`System.ManagedEntity`.

**Tile 1 — Managed nodes**

```sql
SELECT COUNT(n.NodeID) AS [Managed Nodes]
FROM Orion.Nodes n
WHERE n.UnManaged = FALSE
```

**Tile 2 — Nodes down**

```sql
SELECT COUNT(n.NodeID) AS [Nodes Down]
FROM Orion.Nodes n
WHERE n.Status = 2 AND n.UnManaged = FALSE
```

**Tile 3 — Nodes in warning**

```sql
SELECT COUNT(n.NodeID) AS [Nodes Warning]
FROM Orion.Nodes n
WHERE n.Status = 3 AND n.UnManaged = FALSE
```

**Tile 4 — In maintenance (excluded from availability)**

```sql
SELECT COUNT(n.NodeID) AS [In Maintenance]
FROM Orion.Nodes n
WHERE n.UnManaged = TRUE
```

**Tile 5 — Active alerts**

```sql
SELECT COUNT(aa.AlertActiveID) AS [Active Alerts]
FROM Orion.AlertActive aa
```

**Tile 6 — Unacknowledged critical alerts**

`Severity` lives on the alert *definition*, reached through the verified navigation chain
`AlertActive → AlertObjects → AlertConfigurations`. `2` is Critical (the values are not in
urgency order — see [../automation/alerts.md](../automation/alerts.md)).

```sql
SELECT COUNT(aa.AlertActiveID) AS [Unacked Critical]
FROM Orion.AlertActive aa
WHERE aa.Acknowledged = FALSE
  AND aa.AlertObjects.AlertConfigurations.Severity = 2
```

To make a tile clickable (e.g. Nodes Down drilling into a filtered dashboard), add a
`Link` column to that tile's query using the `?filters=` grammar and set
`configuration.interactive: true` — the pattern, including the portable dashboard-ID
lookup against `Orion.Dashboards.Instances`, is in
[the authoring guide](../webui/modern-dashboard-authoring.md#kpi-tiles-link-through-the-interaction-handler).

## Row 2 — Availability (the "A" in SOC 2)

**Tile or single big number — 24-hour fleet availability** (`kpi` widget, one tile).
`Orion.ResponseTime` is the per-poll statistics table; the window keeps the scan bounded
and the `ToUtc(...ToLocal(GetUtcDate()))` shape keeps the window actually 24 hours
regardless of the SQL Server's timezone.

```sql
SELECT ROUND(AVG(rt.Availability), 2) AS [Availability 24h]
FROM Orion.ResponseTime rt
WHERE rt.DateTime >= ToUtc(AddHour(-24, ToLocal(GetUtcDate())))
```

**Node status breakdown** (`proportional` widget, donut — `chartOptions.type` selects the
rendering, the widget type stays `proportional`). One row per slice: label and value.

```sql
SELECT
    n.StatusDescription AS [Label],
    COUNT(n.NodeID) AS [Value]
FROM Orion.Nodes n
WHERE n.UnManaged = FALSE
GROUP BY n.StatusDescription
ORDER BY COUNT(n.NodeID) DESC
```

**Down nodes — the actionable list** (`table` widget). The `_URL`/`_Status` columns are
never displayed; they feed the `EntityLinkFormatterComponent` on the `Node` column, per
the [columns-feed-formatters rule](../webui/modern-dashboard-authoring.md#columns-exist-to-feed-formatters).

```sql
SELECT TOP 50
    n.Caption AS [Node],
    n.DetailsUrl AS [Node_URL],
    n.Status AS [Node_Status],
    n.VendorIcon AS [Vendor Icon],
    n.IP_Address AS [IP Address],
    n.MachineType AS [Machine Type],
    n.StatusDescription AS [Status Details]
FROM Orion.Nodes n
WHERE n.Status = 2 AND n.UnManaged = FALSE
ORDER BY n.Caption
```

## Row 3 — Security and incident response

**Active alert triage** (`table` widget). The alert name comes from
`Orion.AlertConfigurations` — there is no name on the active row — and the `CASE` puts
Critical above Serious above Warning, which raw `Severity` ordering does not.

```sql
SELECT TOP 50
    ao.AlertConfigurations.Name AS [Alert],
    ao.EntityCaption AS [Object],
    ao.EntityDetailsUrl AS [Object_URL],
    ao.RelatedNodeCaption AS [Node],
    aa.TriggeredDateTime AS [Triggered (UTC)],
    aa.Acknowledged AS [Acked],
    aa.AcknowledgedBy AS [Acked By],
    CASE WHEN ao.AlertConfigurations.Severity = 2 THEN 1
         WHEN ao.AlertConfigurations.Severity = 3 THEN 2
         WHEN ao.AlertConfigurations.Severity = 1 THEN 3
         WHEN ao.AlertConfigurations.Severity = 4 THEN 4
         WHEN ao.AlertConfigurations.Severity = 0 THEN 5
         ELSE 9 END AS [TriageOrder]
FROM Orion.AlertActive aa
JOIN Orion.AlertObjects ao ON aa.AlertObjectID = ao.AlertObjectID
ORDER BY TriageOrder, aa.TriggeredDateTime
```

Park `TriageOrder` and `Object_URL` with `isActive: false`; wire `Object_URL` into the
`Object` column's link formatter.

**Active alerts by severity** (`proportional` widget, bar). Labels are spelled out because
the schema does not carry the severity mapping.

```sql
SELECT
    CASE WHEN ac.Severity = 2 THEN 'Critical'
         WHEN ac.Severity = 3 THEN 'Serious'
         WHEN ac.Severity = 1 THEN 'Warning'
         WHEN ac.Severity = 4 THEN 'Notice'
         WHEN ac.Severity = 0 THEN 'Informational'
         ELSE 'Other' END AS [Label],
    COUNT(aa.AlertActiveID) AS [Value]
FROM Orion.AlertActive aa
JOIN Orion.AlertObjects ao ON aa.AlertObjectID = ao.AlertObjectID
JOIN Orion.AlertConfigurations ac ON ao.AlertID = ac.AlertID
GROUP BY ac.Severity
ORDER BY COUNT(aa.AlertActiveID) DESC
```

**Hardware health exceptions** (`table` widget). Anything whose hardware sensors are not
reporting Up, joined to the owning node through the verified `Node` navigation property.

```sql
SELECT TOP 50
    hh.Node.Caption AS [Node],
    hh.Node.DetailsUrl AS [Node_URL],
    hh.Node.Status AS [Node_Status],
    hh.Name AS [Sensor],
    hh.StatusDescription AS [Sensor Status]
FROM Orion.HardwareHealth.HardwareItem hh
WHERE hh.Status <> 1
ORDER BY hh.Node.Caption
```

## Row 4 — Capacity hotspots (processing-integrity evidence)

Four `table` widgets, each a bounded top-N of live exceptions.

**Top 10 CPU**

```sql
SELECT TOP 10
    n.Caption AS [Node],
    n.DetailsUrl AS [Node_URL],
    n.Status AS [Node_Status],
    n.CPULoad AS [CPU %]
FROM Orion.Nodes n
WHERE n.Status = 1 AND n.CPULoad >= 0
ORDER BY n.CPULoad DESC
```

**Top 10 memory**

```sql
SELECT TOP 10
    n.Caption AS [Node],
    n.DetailsUrl AS [Node_URL],
    n.Status AS [Node_Status],
    n.PercentMemoryUsed AS [Memory %]
FROM Orion.Nodes n
WHERE n.Status = 1 AND n.PercentMemoryUsed >= 0
ORDER BY n.PercentMemoryUsed DESC
```

Bind these numeric columns to a `ThresholdFormatterComponent` with the platform thresholds
(`Nodes.Stats.CpuLoad`, `Nodes.Stats.PercentMemoryUsed`) rather than hard-coding colours —
see [the authoring guide's gotchas](../webui/modern-dashboard-authoring.md#gotchas).

**Interfaces above 90 % utilisation**

```sql
SELECT TOP 20
    i.Node.Caption AS [Node],
    i.Caption AS [Interface],
    i.DetailsUrl AS [Interface_URL],
    i.Status AS [Interface_Status],
    i.InPercentUtil AS [In %],
    i.OutPercentUtil AS [Out %]
FROM Orion.NPM.Interfaces i
WHERE (i.InPercentUtil > 90 OR i.OutPercentUtil > 90)
  AND i.Status = 1
ORDER BY i.PercentUtil DESC
```

**Volumes above 90 % used** (RAM and virtual-memory pseudo-volumes excluded)

```sql
SELECT TOP 20
    v.Node.Caption AS [Node],
    v.Caption AS [Volume],
    v.DetailsUrl AS [Volume_URL],
    v.Status AS [Volume_Status],
    v.VolumeType AS [Type],
    ROUND(v.VolumePercentUsed, 1) AS [Used %]
FROM Orion.Volumes v
WHERE v.VolumePercentUsed > 90
  AND v.VolumeType NOT IN ('RAM', 'Virtual Memory')
ORDER BY v.VolumePercentUsed DESC
```

## Row 5 — Change management (requires NCM)

Skip this row if NCM is not installed; the `Cirrus.*` entities will not exist. Both
entities are read-only and need at least the WebViewer NCM role.

**Open compliance violations** (`table` widget). `Cirrus.PolicyCacheResults.NodeID` is the
NCM GUID, so the caption comes from `Cirrus.Nodes`. `ErrorLevel`: `0` info, `1` warning,
`2` critical.

```sql
SELECT TOP 50
    cn.NodeCaption AS [Node],
    pcr.PolicyName AS [Policy],
    pcr.RuleName AS [Rule],
    CASE WHEN pcr.ErrorLevel = 2 THEN 'Critical'
         WHEN pcr.ErrorLevel = 1 THEN 'Warning'
         ELSE 'Info' END AS [Severity]
FROM Cirrus.PolicyCacheResults pcr
JOIN Cirrus.Nodes cn ON pcr.NodeID = cn.NodeID
WHERE pcr.IsViolation = TRUE
ORDER BY pcr.ErrorLevel DESC, cn.NodeCaption
```

**Violations by policy** (`proportional` widget, bar) — the auditor's one-glance view.

```sql
SELECT
    pcr.PolicyName AS [Label],
    COUNT(pcr.CacheID) AS [Value]
FROM Cirrus.PolicyCacheResults pcr
WHERE pcr.IsViolation = TRUE
GROUP BY pcr.PolicyName
ORDER BY COUNT(pcr.CacheID) DESC
```

**Config changes in the last 7 days** (`kpi` widget, one tile) — evidence that change
detection is running.

```sql
SELECT COUNT(ca.ConfigID) AS [Config Changes 7d]
FROM Cirrus.ConfigArchive ca
WHERE ca.DownloadTime >= ToUtc(AddDay(-7, ToLocal(GetUtcDate())))
```

Building compliance reports themselves — including importing DISA STIG packages — is
covered in [../automation/disa-stig-import.md](../automation/disa-stig-import.md) and
[../modules/ncm-compliance-reports.md](../modules/ncm-compliance-reports.md).

## Slicing by customer or site

A dashboard "used by customers and vendors" usually needs a per-tenant cut. That is a
custom property on `Orion.NodesCustomProperties` (e.g. `Customer` or `Site`) — the stock
schema has none, so name yours and validate against your own server with
`Metadata.Property` ([../swis/metadata-introspection.md](../swis/metadata-introspection.md)).
The join shape, shown here against a hypothetical `Customer` property, applies to every
node-scoped query above:

```text
SELECT cp.Customer AS [Label], COUNT(n.NodeID) AS [Value]
FROM Orion.Nodes n
JOIN Orion.NodesCustomProperties cp ON n.NodeID = cp.NodeID
WHERE n.Status = 2 AND n.UnManaged = FALSE
GROUP BY cp.Customer
ORDER BY COUNT(n.NodeID) DESC
```

(A `text` block, not `sql`, because `Customer` cannot validate against the stock schema —
which is correct, not a defect.)

For drill-down, link each slice to the dashboard's own URL with
`?filters={InstanceSiteId}_Orion.NodesCustomProperties_Customer:eq:{value}` — the grammar
is in [the authoring guide](../webui/modern-dashboard-authoring.md#the-filters-grammar).

## Assembling and verifying the file

1. Validate the queries: `python3 tools/validate_swql.py --docs docs/guides/soc2-dashboard-10k-nodes.md`
2. Start from [`scripts/dashboards/minimal-dashboard.json`](../../scripts/dashboards/minimal-dashboard.json),
   regenerating every `unique_key` per its README.
3. Remember: SWQL written twice per widget; one query per KPI tile; every
   `dataFields[].id` must be a column the query returns.
4. Check the structure: `python3 tools/check_dashboards.py your-dashboard.json`

## See also

- [../webui/modern-dashboard-authoring.md](../webui/modern-dashboard-authoring.md) — the rules this page assumes
- [../webui/modern-dashboards.md](../webui/modern-dashboards.md) — the file format itself
- [../swql/performance.md](../swql/performance.md) — why the bounded-and-aggregated shapes above matter
- [../automation/alerts.md](../automation/alerts.md) — the severity mapping and alert query patterns reused here

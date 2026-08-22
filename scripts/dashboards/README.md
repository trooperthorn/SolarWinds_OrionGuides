# Modern Dashboard files

Importable dashboard exports for SolarWinds Observability Self-Hosted's Modern Dashboards
(**My Dashboards → Manage Dashboards → Import**).

| File | Contains |
| --- | --- |
| [minimal-dashboard.json](minimal-dashboard.json) | One KPI tile and one table, against stock entities only |

The format itself is documented in
[../../docs/webui/modern-dashboards.md](../../docs/webui/modern-dashboards.md), and how to
produce one — by hand, from a script, or by prompting an AI system — in
[../../docs/webui/modern-dashboard-authoring.md](../../docs/webui/modern-dashboard-authoring.md).

## `minimal-dashboard.json`

The smallest file that exercises every part of the format worth knowing: the
`dashboards`/`widgets` split joined by `unique_key`, the 12-column grid, the SWQL that is
written twice, a `dataFields` list that has to match the query's aliases, a KPI tile declared
in three places, and three column formatters.

It uses two queries and nothing else:

```sql
SELECT COUNT(n.NodeID) AS TheCount
FROM Orion.Nodes n
WHERE n.Status = 2
```

```sql
SELECT
    n.Caption AS [Node],
    n.DetailsUrl AS [Node_URL],
    n.Status AS [Node_Status],
    n.IP_Address AS [IP Address],
    n.StatusDescription AS [Status Details]
FROM Orion.Nodes n
WHERE n.Status <> 1
ORDER BY n.Status DESC
```

Both name only stock `Orion.Nodes` properties, so the file imports on any installation
without needing custom properties to exist. Both are validated against the extracted 2026.2
schema on every build.

The KPI tile here is **not** interactive — it carries no `interactionHandler` and its
`configuration.interactive` is `false`, because making a tile clickable means adding a `Link`
column to its query and there is no portable link to point a stock template at. The pattern
for adding one is in
[modern-dashboard-authoring.md](../../docs/webui/modern-dashboard-authoring.md#kpi-tiles-link-through-the-interaction-handler).

## Using it as a starting point

**Regenerate every GUID before you build on it.** Copying a widget and keeping its
`unique_key` is the most common real defect in dashboard files — both authors whose exports
this repository examined shipped collisions. The keys to replace are the dashboard's own, the
two widget keys, the `kpi_…` tile id (which appears three times), and the three `column_…`
ids.

```bash
python3 - <<'PY'
import json, re, uuid
raw = open("scripts/dashboards/minimal-dashboard.json").read()
for old in set(re.findall(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", raw)):
    raw = raw.replace(old, str(uuid.uuid4()))
json.dump(json.loads(raw), open("my-dashboard.json", "w"), indent=2)
PY
```

Then rename the dashboard, and check the invariants still hold before importing:

```bash
python3 -c "import json,sys,collections; d=json.load(open(sys.argv[1])); c=collections.Counter(w['unique_key'] for w in d['widgets']); print({k:v for k,v in c.items() if v>1} or 'no duplicate widget keys')" my-dashboard.json
```

If you change a query, change **both** copies of it — under
`providers.dataSource.properties.swql` and again under
`providers.adapter.properties.dataSource.properties.swql` — and keep `dataFields` in step with
the aliases it returns. A `dataFields` id that no longer matches a column renders as a blank
column rather than an error, which is why it is worth checking rather than eyeballing.

## Sanitisation

These files contain no hostnames, credentials, node names or any other data from a real
installation. Anything contributed here must be the same — see
[../../CONTRIBUTING.md](../../CONTRIBUTING.md).

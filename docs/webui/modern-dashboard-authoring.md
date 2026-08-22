# Writing a Modern Dashboard file

[modern-dashboards.md](modern-dashboards.md) is the format. This page is how to produce one —
by hand, from a script, or by asking an AI system to generate the whole file.

The format is verbose but shallow. Almost all of the volume is repetition, and once you know
which parts must agree with which, a dashboard is mostly a list of SWQL queries with
presentation hung off each one.

## The five rules that decide whether a file works

Everything else is detail. These are the invariants, all confirmed across nine real exports
from three independent authors:

1. **Every widget `unique_key` is a fresh GUID, and duplicates are a bug.** Copying a widget
   without regenerating its key is the most common defect in real files — see
   [modern-dashboards.md](modern-dashboards.md#unique_key-collisions-and-the-reuse-that-is-fine).
   Note that a `kpi_…` **tile** id is a different thing: it is scoped to its widget, and reusing
   one across widgets is normal.
2. **Every placement resolves to a definition.** `dashboards[].widgets[].unique_key` must
   appear in the top-level `widgets[]` array.
3. **The SWQL is written twice and both copies must match** — under
   `providers.dataSource.properties.swql` and again under
   `providers.adapter.properties.dataSource.properties.swql`. All **146 pairs across all nine
   files** are byte-identical, which makes this the best-attested rule here.
4. **Every `dataFields[].id` is a column the query returns** — the alias if there is one, and
   the bare property name if there is not, so `ONodes.Status` returns `Status`. A mismatch
   renders a blank column rather than raising an error.
5. **Every KPI tile listed in `tiles.properties.nodes` has a sibling configuration block**
   with the same id. Only that much is universal: `componentType`,
   `adapter.providerId` and `adapter.properties.componentId` are each present on 86 of the 100
   tiles seen and absent from working files, so **write them, but do not treat their absence as
   an error**. Where `componentId` is present it always equals its tile's id.

## Build it query-first

The presentation is the easy half. Write and validate the SWQL before you write any JSON:

```bash
python3 tools/validate_swql.py -
```

Then decide, per query, which widget carries it:

| You want | Widget | The query must return |
| --- | --- | --- |
| A grid of objects | `table` | One row per object, plus a column per formatter input |
| A number, or a row of numbers | `kpi` | **One row**, one query per tile |
| A breakdown of a total | `proportional` | One row per slice: a label, a value, optionally a colour, icon and link |

A `kpi` widget with six tiles is six separate single-row queries, not one query with six
columns. That is the most common surprise in the format.

## Columns exist to feed formatters

A table column binds data fields to a rendering component, so the query needs a column for
each input the formatter takes — not just the visible value. The pattern throughout both
authors' files is to select the display value, the link, and the status side by side:

```sql
SELECT
    n.Caption AS [Node],
    n.DetailsUrl AS [Node_URL],
    n.Status AS [Node_Status],
    n.VendorIcon AS [Vendor Icon],
    n.IP_Address AS [IP Address]
FROM Orion.Nodes n
WHERE n.Status <> 1
ORDER BY n.Status DESC
```

`Node_URL` and `Node_Status` are never shown as columns of their own. They are wired into the
`Node` column's formatter:

```json
{
  "id": "column_2f1c6a70-0f22-4e4e-9a1e-2a0f5a5a0001",
  "label": "Node",
  "isActive": true,
  "formatter": {
    "componentType": "EntityLinkFormatterComponent",
    "properties": {
      "dataFieldIds": { "value": "Node", "link": "Node_URL", "status": "Node_Status", "vendor": null },
      "iconFormat": "status",
      "entityIcon": null
    }
  }
}
```

Set `isActive: false` on a column you want to keep in the file but not display — that is how
both authors park a field that only exists to feed something else.

## The self-referencing link pattern

Both authors independently use the same technique for one dashboard to link to another, and it
is the most quietly clever thing in these files. A dashboard's URL contains its numeric id,
which differs per installation — so rather than hard-code it, the query looks it up:

```sql
SELECT TOP 1
    i.InstanceSiteId,
    '/apps/platform/dashboard/' + ToString(i.DashboardID) AS Link
FROM Orion.Dashboards.Instances i
WHERE i.DisplayName = 'Site Summary - System Status'
ORDER BY i.DashboardID
```

That is joined into the widget's real query with `LEFT JOIN (...) D ON 1=1`, a cross join that
attaches the single Link row to every result row. The dashboard is then addressed **by name**,
so the file stays portable between servers.

The trade is that **the dashboard name becomes an API**. Rename a dashboard and every link to
it silently returns `NULL` — which is why the samples wrap the concatenation in
`CASE WHEN D.Link IS NULL THEN NULL ELSE ... END` rather than producing a broken URL.

`Orion.Dashboards.Instances` grants every operation to `everyone`, so this lookup needs no
special rights:

```bash
python3 tools/schema_query.py show Orion.Dashboards.Instances
```

## The `?filters=` grammar

Appending a filter to a dashboard URL is how these dashboards drill down. The grammar, read
off both authors' files:

```text
/apps/platform/dashboard/{DashboardID}?filters={InstanceSiteId}_{Entity}_{Property}:{op}:{value}
```

Several filters are joined by `-`:

```text
?filters=1_Orion.Nodes_Status:ne:0-1_Orion.Nodes_Status:ne:1-1_Orion.Nodes_Status:ne:2
```

| Segment | Value |
| --- | --- |
| `{InstanceSiteId}` | From `Orion.Dashboards.Instances.InstanceSiteId`, selected alongside the id |
| `{Entity}` | A SWIS entity name, e.g. `Orion.Nodes`, `Orion.NodesCustomProperties` |
| `{Property}` | A property of that entity |
| `{op}` | `eq` or `ne` |
| `{value}` | The literal value |

Entities used as filter targets across the four files: `Orion.Nodes`,
`Orion.NodesCustomProperties`, `Orion.NPM.Interfaces`, `Orion.AlertConfigurations`,
`Orion.HardwareHealth.HardwareInfo` and `Orion.Wireless.AccessPoints`.

**Only `eq` and `ne` appear.** Whether the filter engine accepts comparison, `like` or `in`
operators is **not documented and unverified here**. So is whether a value containing a `-` or
a `:` can be escaped — the separators are unescaped in every sample, so a site name containing
a hyphen would be ambiguous.

A companion widget makes the filter clearable: a one-row table whose only column links to the
dashboard's own URL with no `?filters=` on it. Both authors ship one, labelled "Reset".

## KPI tiles link through the interaction handler

A KPI widget has no per-tile link property. Instead the widget root carries a handler that
reads a column from each tile's own result:

```json
"/": {
  "providers": {
    "interactionHandler": {
      "providerId": "NOVA_URL_INTERACTION_HANDLER",
      "properties": { "url": "${data.rowData.Link}", "newWindow": true }
    }
  }
}
```

So every tile query returns a `Link` column, and `properties.configuration.interactive` is set
to `true` on the tile. `${data.rowData.<Field>}` is unrelated to the `${N=…;M=…}` alert
variables in [variables.md](variables.md), despite the shared `${…}` spelling.

## A complete minimal file

This is a whole, importable dashboard: one KPI tile and one table, both against stock entities
so it works on any installation without custom properties.

[`scripts/dashboards/minimal-dashboard.json`](../../scripts/dashboards/minimal-dashboard.json)
is that file, ready to import, with
[its own notes](../../scripts/dashboards/README.md) on regenerating the GUIDs before you
build on it. Its KPI tile is deliberately **not** interactive: making one clickable means
adding a `Link` column to the tile's query, and there is no link a stock template can point at
without knowing your installation.

The two queries it uses, both validated against 2026.2:

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

## Asking an AI to generate one

The format is regular enough that a language model can emit a whole valid file, provided the
prompt pins the parts it cannot infer. A prompt that works has five parts:

**1. Name the format and the version.** "A SolarWinds Modern Dashboard export, `version: 1`,
with top-level `version`, `dashboards`, `widgets` and `remove` keys."

**2. Give the schema, or point at it.** Paste
[modern-dashboards.md](modern-dashboards.md), or the relevant widget-type section of it. A
model that has not seen the format will invent plausible-looking keys.

**3. State the invariants as requirements.** The five rules at the top of this page, verbatim.
The duplication of SWQL between `dataSource` and `adapter` is the one a model is most likely to
drop, because it looks redundant.

**4. Supply the queries, or supply the schema to write them from.** This is where a dashboard
is right or wrong. Either give the SWQL you have already validated, or give the model the
entity and property names — `python3 tools/schema_query.py show Orion.Nodes` — and have it
write them. Do not let it invent property names; that is the failure this whole repository
exists to prevent.

**5. Say what your custom properties are.** A model cannot know that your installation has
`Site` or `Responsible_Group`. If the dashboard filters on one, name it and its entity
(`Orion.NodesCustomProperties`), or the generated SWQL will reference something that does not
exist.

Then verify before importing:

```bash
python3 tools/validate_swql.py -
```

and check the structural invariants, which is what
[`tools/check_dashboards.py`](../../tools/check_dashboards.py) exists for — point it at any
dashboard file, not just the ones in this repository:

```bash
python3 tools/check_dashboards.py scripts/dashboards/minimal-dashboard.json
```

```text
1 dashboard file(s), 2 widget definition(s) and 4 embedded query/queries checked
every shipped dashboard satisfies the invariants in docs/webui/modern-dashboard-authoring.md
```

Give it the path to your own export in place of that one.

It enforces all five rules above plus the column bindings, and it is deliberately quiet about
the things real files legitimately do: an absent `componentId`, an empty `sortBy`, the `""`
placeholders in a threshold column. Every one of those was a false positive it reported before
being run against a wider sample.

For a quick look at just the collision rule, without the repository:

```bash
python3 -c "import json,sys,collections; d=json.load(open(sys.argv[1])); c=collections.Counter(w['unique_key'] for w in d['widgets']); print({k:v for k,v in c.items() if v>1} or 'no duplicate widget keys')" dashboard.json
```

Validating the SWQL catches the errors that matter. A malformed layout is obvious the moment
you look at the page; a query naming a property that does not exist gives you an empty widget
and no reason why.

## Gotchas

**Copying a widget copies its key.** One author's file carries collisions across 27 widgets.
Regenerate the widget key; a `kpi_…` tile id is scoped to its widget and may be reused.

**The SWQL lives in two places.** Edit both.

**A KPI tile is one query.** Six tiles, six queries, each returning one row.

**`proportional` covers bar charts too.** The rendering is `chartOptions.type`, not the widget
type.

**Dashboard names are load-bearing** wherever the self-reference pattern is used. Renaming a
dashboard breaks every link into it, silently.

**Filter values are not escaped.** A value containing `-` or `:` is unverified territory.

**Custom properties will not validate against a stock schema**, and that is correct rather
than a problem — validate against your own server with `Metadata.Property`, per
[../swis/metadata-introspection.md](../swis/metadata-introspection.md).

**`collapsed: true` appears with `collapsible: false`** throughout — 60 of the 69 headers that
declare the pair, with the other 9 setting both true and 6 headers omitting both. `collapsed:
false` appears nowhere in any file. Write the pair the way the console does, or leave both out,
and set `collapsible: true` if you mean the widget to collapse.

**A `ThresholdFormatterComponent` column takes a `thresholdName`**, binding the bar to a
threshold the platform already defines (`Nodes.Stats.CpuLoad` and friends) rather than to
numbers in the file. Its `instanceId` and `siteId` are `""` in every real instance.

**An unaliased select item still names a column.** `ONodes.Status` returns `Status`. But an
unaliased *expression* — a `CONCAT(...)` or `COUNT(...)` — gets a server-assigned name you
cannot predict, so alias those.

## See also

- [modern-dashboards.md](modern-dashboards.md) — the file format, field by field
- [../automation/custom-properties.md](../automation/custom-properties.md) — enumerating the
  custom properties a dashboard can filter on
- [custom-query-widget.md](custom-query-widget.md) — the classic-console equivalent, with its
  own `_LinkFor_` convention
- [../swql/README.md](../swql/README.md) and [../swql/gotchas.md](../swql/gotchas.md) — the
  query language every widget is built on
- [../swis/metadata-introspection.md](../swis/metadata-introspection.md) — validating names
  against your own installation

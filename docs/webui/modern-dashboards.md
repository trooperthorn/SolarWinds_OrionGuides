# Modern Dashboard files

A Modern Dashboard — the console calls the feature **Dashboards**, under `/apps/platform/dashboard/` —
exports as a single JSON file. That file is the whole dashboard: layout, widgets, every SWQL
query, every column formatter and every colour.

Nothing about the format is documented by SolarWinds. This page is derived by parsing **four
real exports from two independent authors** and checking every entity, property and query they
contain against the 2026.2 schema. Where the two authors agree, the rule is stated plainly;
where only one exercises a feature, it says so.
[modern-dashboard-authoring.md](modern-dashboard-authoring.md) is the other half: how to write
one from scratch, including for an AI asked to generate a whole file.

## The envelope

```json
{
  "version": 1,
  "dashboards": [ ... ],
  "widgets":    [ ... ],
  "remove": null
}
```

Four keys, and the split between the last three is the thing to understand first:

| Key | Holds |
| --- | --- |
| `version` | Format version. `1` in every export seen |
| `dashboards` | The **pages**: name, and where each widget sits on the grid |
| `widgets` | The **widget definitions**: type, queries, formatting |
| `remove` | `null` in every export seen; purpose undocumented and **unverified here** |

**A widget is defined once and placed once.** The two arrays are joined by `unique_key`:
`dashboards[].widgets[].unique_key` is a placement referring to a definition in the top-level
`widgets[]` array. That indirection is what lets the same widget appear on several dashboards.

## `dashboards[]` — the page and its layout

```json
{
  "unique_key": "0ecba6a9-a7d1-497a-b6af-5a6a73796069",
  "name": "Site Summary - Overview",
  "parent": null,
  "feature": null,
  "private": null,
  "widgets": [
    { "unique_key": "751bb079-...", "location": { "x": 0, "y": 0, "cols": 10, "rows": 2 }, "reference": false }
  ]
}
```

| Field | Meaning |
| --- | --- |
| `unique_key` | The dashboard's own GUID |
| `name` | The display name. **This string is load-bearing** — see the self-reference pattern below |
| `parent` | `null` in every export seen. Presumably the clone source, matching `Orion.Dashboards.Instances.ParentID` — **unverified** |
| `feature` | `null` in every export seen; matches `Orion.Dashboards.Instances.Feature` |
| `private` | `null` on the dashboard, `false` on widgets. Visibility; **unverified** |
| `widgets[]` | Placements, not definitions |

### The grid is 12 columns

`location` is `{x, y, cols, rows}` in grid cells, with `x` and `y` zero-based from the top
left. Across three real dashboards, every layout fills exactly **12 columns**:

```text
 x=0                                    x=10
 +--------------------------------------+-----+
 | Sites by Status      cols=10 rows=2   | R 2 |   y=0
 |                                       +-----+
 |                                       | F   |   y=1
 +---------------------------------------+  2  |
 | Devices Not Up       cols=10 rows=2   |     |   y=2
 |                                       |     |
 +---------------------------------------+-----+
 | All Active Alerts    cols=10 rows=3         |   y=4
 |                                             |
 +---------------------------------------+-----+
```

Rows have no fixed height in the file; `rows` is a proportion of the grid. Gaps are legal —
one of the sample dashboards leaves `x=10, y=3..4` empty.

`reference` is `false` on every placement seen. What `true` would mean is **undocumented and
unverified here**; the plausible reading is a link to a widget owned by another dashboard
rather than an embedded copy.

## `widgets[]` — the definitions

Every widget definition has the same outer shape regardless of type:

```json
{
  "type": "table",
  "unique_key": "f4c74926-35af-4044-b921-dc2468e81c58",
  "name": "All Active Alerts",
  "subtitle": "Order by oldest outage",
  "description": "All active alerts with search",
  "private": false,
  "configuration": { ... }
}
```

`name`, `subtitle` and `description` are duplicated inside
`configuration.header.properties` as `title`, `subtitle` and `description`. Both copies appear
in every export; keep them in sync.

### The three widget types seen

| `type` | Renders | Data provider |
| --- | --- | --- |
| `table` | A sortable, searchable grid | `TableSwqlDatasourceService` |
| `kpi` | A row of coloured number tiles | `KpiSwqlDatasourceService` |
| `proportional` | A chart of parts against a whole | `ProportionalSwqlDatasourceService` |

All four files use only these three, with the same three provider ids. Other widget types
certainly exist in the product and the list here is **not complete**.

**`proportional` is not "a donut".** It is the part-to-whole chart widget, and
`chartOptions.type` picks the rendering. Across the four files that field takes `DonutChart`,
`PieChart` and `HorizontalBarChart` — so a horizontal bar chart is also a `proportional`
widget, which is not something the type name suggests.

### The header block, common to all types

```json
"header": {
  "properties": {
    "title": "All Active Alerts",
    "subtitle": "Order by oldest outage",
    "url": "/orion/netperfmon/alerts.aspx",
    "description": "",
    "collapsible": false,
    "collapsed": true
  }
}
```

`url` makes the widget title a hyperlink. Note that `collapsed: true` appears together with
`collapsible: false` throughout the samples, which suggests `collapsed` is ignored unless
`collapsible` is set — **unverified here**.

### The refresher and interaction handler

Both live under the oddly named `"/"` key, which is the widget-root configuration node:

```json
"/": {
  "providers": {
    "refresher": {
      "properties": { "enabled": true, "interval": 45, "overrideDefaultSettings": false }
    },
    "interactionHandler": {
      "providerId": "NOVA_URL_INTERACTION_HANDLER",
      "properties": { "url": "${data.rowData.Link}", "newWindow": true }
    }
  }
}
```

`interval` is in **seconds**. `${data.rowData.<Field>}` is a template referring to a column of
the widget's own result set — that is how a KPI tile becomes clickable, with `Link` being an
ordinary aliased column in the SWQL.

## The data source, and the duplication that will catch you

Every widget carries its query under `providers.dataSource.properties`:

```json
"providers": {
  "dataSource": {
    "providerId": "TableSwqlDatasourceService",
    "properties": {
      "swql": "SELECT ...",
      "dataFields": [ { "id": "Caption", "label": "Caption", "dataType": "System.String" } ],
      "type": "hand-edit"
    }
  },
  "adapter": {
    "properties": {
      "dataSource": { "properties": { "swql": "SELECT ...", "dataFields": [ ... ] } }
    }
  }
}
```

**The SWQL and `dataFields` appear twice**, once under `dataSource` and again nested inside
`adapter.properties.dataSource`. In all three sample files, across **32 such pairs, the two
copies are byte-identical**. Treat that as an invariant: edit one and you must edit the other.
It is the single easiest way to produce a file that imports and then behaves inconsistently.

`type: "hand-edit"` marks a query typed by a person rather than built by the console's query
builder. Every query in the samples is `hand-edit`.

### `dataFields` declares the result shape

Each entry is `{id, label, dataType}`, where `id` must match a column name the SWQL returns.
Checked across all three files: **every `dataField` id appears in its own query**. The widget
uses these ids to wire columns to formatters, so a mismatch means a blank column rather than
an error.

`dataType` values seen are `System.String`, `System.Int32` and `System.DateTime`.

## Table configuration

```json
"table": {
  "properties": {
    "configuration": {
      "columns": [ ... ],
      "sorterConfiguration": { "sortBy": "column_742e4002-...", "descendantSorting": false },
      "hasVirtualScroll": true,
      "searchConfiguration": { "enabled": true }
    }
  }
}
```

`sortBy` refers to a **column id**, not a data field. Columns carry their own generated ids of
the form `column_<uuid>`.

### Column formatters

A column binds one or more data fields to a rendering component:

```json
{
  "id": "column_a70f1623-afdd-4ba0-92da-185c26ed3372",
  "label": "Object",
  "isActive": true,
  "width": 200,
  "formatter": {
    "componentType": "EntityLinkFormatterComponent",
    "properties": {
      "dataFieldIds": { "status": "Object_Status", "vendor": null, "link": "Object_URL", "value": "Object" },
      "iconFormat": "status",
      "entityIcon": null
    }
  }
}
```

| `componentType` | Renders | `dataFieldIds` keys |
| --- | --- | --- |
| `RawFormatterComponent` | Plain text | `value` |
| `LinkFormatterComponent` | A hyperlink | `value`, `link` (+ `targetSelf`) |
| `EntityLinkFormatterComponent` | Link with a status or vendor icon | `value`, `link`, `status`, `vendor` |
| `StatusFormatterComponent` | A status indicator | `value` |
| `SeverityFormatterComponent` | A severity icon and label | `value` (+ `visualization`) |
| `DatetimeFormatterComponent` | A formatted timestamp | `value` (+ `option`, `replaceDate`) |
| `ThresholdFormatterComponent` | A value rendered against thresholds | `value` |
| `GenericValueFormatterComponent` | Used as a chart legend formatter | — |

`isActive: false` keeps a column in the file but hides it — useful when a field is only there
to feed another column's formatter.

`iconFormat` values seen: `status`, `vendor`, `entityTypeWithStatus`. With the last one,
`entityIcon` names the glyph — `network-device` and `network-interface` across the four files.
`targetSelf: true` opens in the same tab; `false` opens a new one. `visualization` takes
`iconWithLabel` and `barChart`.

The complete value sets for `iconFormat`, `entityIcon`, `visualization` and the
`DatetimeFormatterComponent` `option` field are **not documented and unverified here**.

## KPI configuration

A KPI widget is a container of tiles. The tile order is an explicit list:

```json
"tiles": { "properties": { "nodes": [ "kpi_4eb21f86-...", "kpi_556516af-..." ] } }
```

Each id in `nodes` must have a matching sibling key on `configuration`:

```json
"kpi_4eb21f86-b256-45c4-9746-a335fe0b0181": {
  "id": "kpi_4eb21f86-b256-45c4-9746-a335fe0b0181",
  "componentType": "KpiComponent",
  "providers": {
    "dataSource": { "providerId": "KpiSwqlDatasourceService", "properties": { "swql": "...", "dataFields": [ ... ] } },
    "adapter": {
      "providerId": "NOVA_KPI_DATASOURCE_ADAPTER",
      "properties": {
        "componentId": "kpi_4eb21f86-b256-45c4-9746-a335fe0b0181",
        "propertyPath": "widgetData",
        "dataSource": { "properties": { "swql": "...", "dataFields": [ ... ] } },
        "thresholds": { "criticalThresholdValue": 0, "warningThresholdValue": null, "showThresholds": false, "reversedThresholds": false }
      }
    }
  },
  "properties": {
    "configuration": { "interactive": true },
    "widgetData": { "label": " ", "backgroundColor": "var(--nui-color-semantic-down)", "units": "Sites Down" }
  }
}
```

**One tile is one query.** Six tiles means six queries, each returning a single row. `units` is
the caption under the number; `label` is a separate string, blank in every sample.

`adapter.properties.componentId` repeats the tile's own id — a third place the same GUID
appears, after the object key and `id`.

### The colour tokens

`backgroundColor` takes a CSS custom property from the console's own theme, so tiles match the
platform's semantics in both light and dark:

| Token | Used for |
| --- | --- |
| `var(--nui-color-semantic-ok)` | Up |
| `var(--nui-color-semantic-down)` | Down |
| `var(--nui-color-semantic-critical)` | Critical |
| `var(--nui-color-semantic-warning)` | Warning |
| `var(--nui-color-semantic-info)` | Informational, maintenance |
| `var(--nui-color-semantic-unknown-bg)` | Unknown |
| `var(--nui-color-chart-ten-light)`, `var(--nui-color-chart-eight-light)` | Neutral chart colours, used for "other" and "unknown" |

Using a token rather than a hex value is what keeps a dashboard readable when the console
theme changes. The full token set is **not documented and unverified here**.

## Proportional (donut) configuration

```json
"chart": {
  "providers": { "dataSource": { "providerId": "ProportionalSwqlDatasourceService", "properties": {
      "swql": "...",
      "categoryField": "Severity",
      "valueField": "TheCount",
      "colorMappingField": "Color",
      "iconMappingField": "StatusIcon",
      "linkMappingField": "Link",
      "dataFormat": "custom",
      "dataFields": [ ... ]
  } } },
  "properties": { "configuration": { "chartOptions": {
      "type": "DonutChart",
      "legendPlacement": "Bottom",
      "legendFormatter": { "componentType": "GenericValueFormatterComponent" }
  } } }
}
```

The five `*Field` properties are the whole binding: each names a **column of the query**.
`colorMappingField` is why the sample query computes a hex colour per row with a `CASE`, and
`linkMappingField` is what makes each slice clickable.

`dataFormat: "custom"` accompanies that per-row mapping, and is the only value in all four
files.

`chartOptions.type` takes `DonutChart`, `PieChart` or `HorizontalBarChart`.
`legendPlacement` takes `Bottom`, `Right` or `None`. Neither list is necessarily complete and
both are **unverified here** beyond what the samples exercise.

## `unique_key` collisions, which both authors produced

`unique_key` is the only thing joining a placement to a definition, and **nothing enforces
that it is unique.** Both authors' files break it, in two different ways, and neither break is
visible from the console.

**Within one file.** In the second author's 27-widget dashboard, there are only **14 distinct
`unique_key` values**. One key is used for seven separate widget definitions:

```text
4be6054c-f059-4d5c-826f-a357820aa54b   x7
   "Network Nodes - Status"   "Security Nodes - Status"   "SDWAN Nodes - Status"
   "SIEM Nodes - Status"      "Voice Nodes - Status"      "Storage Nodes - Status"
   "All Nodes - Status"
```

Seven different names, seven different queries, one key — and seven placements referring to
it. Another key covers seven interface widgets the same way, and a third covers two. The
pattern is unmistakable: the widget was copied in the editor and the key came with it.

**Across files.** In the first author's three dashboards, the widget
`f4c74926-35af-4044-b921-dc2468e81c58` ("All Active Alerts") appears in all three with the
**same key and different content** — the Alert Status copy links its Site column to the System
Status dashboard, while the other two link to Alert Status.

What the platform does with a duplicate key is **not documented and unverified here**. The two
readings are that the last definition wins or that the first does; either way the other
definitions are silently discarded, and on the cross-file case importing the three dashboards
in a different order gives a different result.

**So: regenerate `unique_key` whenever you copy a widget**, and treat a repeated key as a bug
rather than as reuse. Genuine reuse — the same widget deliberately shown on several pages — is
what the first author's `751bb079` and `52ad9838` do correctly: same key, and the definition is
**byte-identical** in all three files.

A one-line check before you import anything:

```bash
python3 -c "import json,sys,collections; d=json.load(open(sys.argv[1])); c=collections.Counter(w['unique_key'] for w in d['widgets']); print({k:v for k,v in c.items() if v>1} or 'no duplicate widget keys')" dashboard.json
```

## What this repository verified

Four exports from two independent authors, parsed and checked against the extracted 2026.2
schema:

| Check | Author A (3 files) | Author B (1 file) |
| --- | --- | --- |
| Envelope keys and `version` | `1`, four keys | identical |
| Grid width | 12 columns | 12 columns |
| `dataSource` / `adapter` SWQL byte-identical | 32 of 32 | **69 of 69** |
| `dataField` ids present in their own query | all | all, across 138 data sources |
| Placements resolving to a definition | all | all |
| KPI `tiles.nodes` ids having a config block | all | all |
| Distinct SWQL statements | 17 | 69 |
| Statements using only platform names that exist | 17 of 17 | 12 clean, 57 naming a custom property |

**Every unresolved name in either author's file is a custom property**, not a mistake:
`Site` for author A, and `Responsible_Group`, `Device_Type` and `Link_Type` for author B.
Custom properties are columns each customer adds to extend the product, so no extracted schema
can contain them — that is the point of them. See
[../automation/custom-properties.md](../automation/custom-properties.md) for enumerating the
ones your own server has, which is how you would validate a dashboard against your
installation rather than against the stock schema.

Every *platform* entity used checks out, including `Orion.Dashboards.Instances`, whose
`DisplayName` and `InstanceSiteId` are inherited from `System.Entity` and
`Orion.Dashboards.Entity` rather than declared on it.

## See also

- [modern-dashboard-authoring.md](modern-dashboard-authoring.md) — writing one, the filter URL
  grammar, and the contract for asking an AI to generate a whole file
- [../automation/custom-properties.md](../automation/custom-properties.md) — the custom
  properties these dashboards filter on
- [variables.md](variables.md) — the other `${...}` system, which is unrelated to
  `${data.rowData.…}`
- [../swql/README.md](../swql/README.md) — the query language every widget is built on

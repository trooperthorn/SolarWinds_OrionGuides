# Modern Dashboard files

A Modern Dashboard — the console calls the feature **Dashboards**, under `/apps/platform/dashboard/` —
exports as a single JSON file. That file is the whole dashboard: layout, widgets, every SWQL
query, every column formatter and every colour.

Nothing about the format is documented by SolarWinds. This page is derived by parsing **nine
real exports from three independent authors** and checking every entity, property and query
they contain against the 2026.2 schema. Where all three authors agree, the rule is stated
plainly; where only one exercises a feature, it says so.
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
| `name` | The display name. **This string is load-bearing**: other dashboards look one up by name to build links to it, so a rename breaks those links silently — see [the self-referencing link pattern](modern-dashboard-authoring.md#the-self-referencing-link-pattern) |
| `parent` | `null` in every export seen. Presumably the clone source, matching `Orion.Dashboards.Instances.ParentID` — **unverified** |
| `feature` | `null` in every export seen; matches `Orion.Dashboards.Instances.Feature` |
| `private` | `null` on the dashboard, `false` on widgets. Visibility; **unverified** |
| `widgets[]` | Placements, not definitions |

One author's export carries eight further dashboard-level keys, all empty:

```json
"groupId": null, "groupRank": null, "groupMemberName": null, "groupName": null,
"dashboardType": null, "routeId": "", "dashboardRoutes": [], "configuration": null
```

The other two authors' files omit them entirely and import the same way, so they are optional.
`groupId`/`groupRank`/`groupName` read as dashboard grouping and `routeId`/`dashboardRoutes` as
custom URL routing, but every value seen is empty, so what they do is **undocumented and
unverified here**.

### The grid is 12 columns wide

`location` is `{x, y, cols, rows}` in grid cells, with `x` and `y` zero-based from the top
left. Across all nine dashboards, **`x + cols` never exceeds 12** — that is the invariant. It
is not that every row is full: trailing rows are frequently partial, and the samples end rows
at 10, 8, 6 and 2 columns. So 12 is the width of the canvas, not a sum each row has to reach.

A typical layout, with a partial final row:

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

All nine files use only these three, with the same three provider ids. Other widget types
certainly exist in the product and the list here is **not complete**.

**`proportional` is not "a donut".** It is the part-to-whole chart widget, and
`chartOptions.type` picks the rendering. Across the nine files that field takes `DonutChart`,
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

All 75 widgets across the nine files carry a header block, but not all of its keys.

`url` makes the widget title a hyperlink. Only six headers set it, all to
`/orion/netperfmon/alerts.aspx`; the other 69 leave it `""`.

`collapsible` and `collapsed` are **omitted together on 6 headers**, so both are optional. On
the 69 that declare them, `collapsed` is `true` every single time, while `collapsible` is
`false` on 60 and `true` on 9. So `collapsed: false` is never written by the console at all,
and `collapsed: true` alongside `collapsible: false` is the ordinary case rather than a
mistake. The reading that `collapsed` is inert unless `collapsible` is set fits the evidence
but is still **unverified here**; what is now clear is that you should write the pair the way
the console does, or omit both, rather than inventing `collapsed: false`.

### The `content` node

One file carries a further sibling of `header`, on a KPI widget:

```json
"content": { "properties": { "isEditable": true } }
```

It appears five times in one author's export and nowhere else, and the other files' KPI widgets
render without it. What it enables is **undocumented and unverified here**.

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

`interval` is in **seconds**. Fourteen refreshers appear across the nine files: thirteen at
`45` with `overrideDefaultSettings: false`, and one at `90` with `overrideDefaultSettings:
true` — so the flag does get set, and it reads as "use my interval rather than the console
default". Three refreshers carry `enabled: false`, which keeps the block but stops the widget
polling.

`${data.rowData.<Field>}` is a template referring to a column of the widget's own result set —
that is how a KPI tile becomes clickable, with `Link` being an ordinary aliased column in the
SWQL. All 25 interaction handlers in all nine files use the identical url
`${data.rowData.Link}`, so the column name `Link` is a convention worth keeping.

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
`adapter.properties.dataSource`. In all nine sample files, across **146 such pairs, the two
copies are byte-identical**. Treat that as an invariant: edit one and you must edit the other.
It is the single easiest way to produce a file that imports and then behaves inconsistently.

`type: "hand-edit"` marks a query typed by a person rather than built by the console's query
builder. Every query in the samples is `hand-edit`.

### `dataFields` declares the result shape

Each entry is `{id, label, dataType}`, where `id` must match a column name the SWQL returns.
Checked across all nine files: **every `dataField` id is a column of its own query**. The
widget uses these ids to wire columns to formatters, so a mismatch means a blank column rather
than an error.

**The returned column name is the alias if there is one and the bare property name if there is
not.** `ONodes.Status` with no `AS` returns a column called `Status`, and one author writes
whole queries in that style:

```sql
SELECT ONodes.Status, ONodes.DetailsUrl, NNodes.Vendor, NNodes.NodeCaption
FROM Orion.Nodes AS ONodes
INNER JOIN NCM.Nodes AS NNodes ON NNodes.CoreNodeID = ONodes.NodeID
```

with `dataFields` of exactly `Status`, `DetailsUrl`, `Vendor`, `NodeCaption`. An expression
without an alias — a `CONCAT(...)` or `COUNT(...)` — gets a server-assigned name that cannot
be read off the text, so always alias those.

`dataType` values seen, in frequency order: `System.String`, `System.Int32`, `System.Double`,
`System.DateTime`, `System.Single`, `System.Int64`, `System.Byte`, `System.Decimal`.

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
the form `column_<uuid>`. A table left unsorted writes `sortBy: ""` rather than omitting it,
and `descendantSorting` is written as `true` (10), `false` (5) **or `""`** (13) — an empty
string where a boolean belongs, which the console evidently reads as false. Treat `""` in
either field as "not set" rather than as a broken reference.

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

Nine `componentType`s appear across the nine files, in frequency order:

| `componentType` | Uses | Renders | `dataFieldIds` keys |
| --- | --- | --- | --- |
| `RawFormatterComponent` | 50 | Plain text | `value` |
| `EntityLinkFormatterComponent` | 34 | Link with a status, vendor or entity-type icon | `value`, `link`, `status`, `vendor` (+ `label`) |
| `ThresholdFormatterComponent` | 22 | A value against a named platform threshold | `value`, `instanceId`, `siteId` (+ `thresholdName`, `visualization`) |
| `LinkFormatterComponent` | 21 | A hyperlink | `value`, `link` (+ `targetSelf`) |
| `GenericValueFormatterComponent` | 18 | Used as a chart legend formatter | — |
| `SimpleNumberFormatterComponent` | 11 | A bare number | `value` (+ `prefixIcon`, `suffixText`) |
| `DatetimeFormatterComponent` | 4 | A formatted timestamp | `value` (+ `option`, `replaceDate`) |
| `SeverityFormatterComponent` | 3 | A severity icon and label | `value` (+ `visualization`) |
| `StatusFormatterComponent` | 2 | A status indicator | `value` |

The list is still **not complete** — these are the types nine files happened to use.

`isActive: false` keeps a column in the file but hides it — useful when a field is only there
to feed another column's formatter.

### Formatter property values

`iconFormat` takes four values: `status` (17), `entityTypeWithStatus` (9), `vendor` (6) and
`entityType` (2). With either of the `entityType` forms, `entityIcon` names the glyph —
`network-device`, `rule`, `network-interface`, `policy` and `network-path` across the nine
files. `targetSelf: true` opens in the same tab; `false` opens a new one.

`visualization` takes `barChart` (22, always on a threshold column) and `iconWithLabel` (3, on
a severity column).

**`ThresholdFormatterComponent` binds to a threshold the platform already defines**, by name,
rather than to numbers in the file:

```json
"formatter": {
  "componentType": "ThresholdFormatterComponent",
  "properties": {
    "dataFieldIds": { "value": "CPULoad", "instanceId": "", "siteId": "" },
    "thresholdName": "Nodes.Stats.CpuLoad",
    "visualization": "barChart"
  }
}
```

That is what makes a dashboard bar turn amber at the same point the rest of the console does.
The names seen are `Nodes.Stats.CpuLoad`, `Nodes.Stats.PercentMemoryUsed`,
`Nodes.Stats.ResponseTime`, `Nodes.Stats.PercentLoss`,
`NPM.Interfaces.Stats.InPercentUtilization`, `NPM.Interfaces.Stats.OutPercentUtilization` and
`SRM.StorageControllers.Stats.Utilization`. `instanceId` and `siteId` are `""` in **every one
of the 22 instances** — an unset slot rather than a field binding, presumably for scoping a
per-object threshold override. The full set of valid threshold names is **not documented and
unverified here**.

`EntityLinkFormatterComponent` also accepts a `label` key, which two columns use to separate
the text from the value:

```json
"dataFieldIds": { "status": "NodeStatus", "vendor": null,
                  "label": "NodeName", "value": "NodeDetailsUrl", "link": "NodeDetailsUrl" }
```

Here `value` and `link` are both the URL and `label` carries what the reader sees. Whether
`label` is honoured by the other link formatters is **unverified here**.

`DatetimeFormatterComponent`'s `option` is written **both as a string and as an integer** —
`"0"` twice, `0` once and `1` once — so the console evidently accepts either. What the values
select is **not documented and unverified here**.

The complete value sets for `iconFormat`, `entityIcon`, `visualization` and `option` are
**not documented and unverified here**.

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
the caption under the number, and `label` is a separate string — blank in one author's files,
but the tile's name (`"Down"`, `"Warning"`) in another's.

### Most of a tile block is optional

The block above is the fullest form. Counting all **100 tile blocks** across the nine files
shows how much of it the console will do without:

| Key | Present |
| --- | --- |
| `properties.widgetData` | 100 / 100 |
| `providers.adapter.properties.thresholds` | 88 / 100 |
| `componentType` | 86 / 100 |
| `providers.adapter.providerId` | 86 / 100 |
| `providers.adapter.properties.componentId` | 86 / 100 |
| `providers.adapter.properties.propertyPath` | 86 / 100 |
| `properties.configuration` | 80 / 100 |

Only `widgetData` — the label, colour and units — is universal. Fourteen tiles across two
authors' working exports carry an adapter with nothing but a nested `dataSource`, no
`providerId`, no `componentId`, no `componentType` on the block:

```json
"kpi_3d1205d9-595a-49b3-b1a6-04d50ea1be4d": {
  "id": "kpi_3d1205d9-595a-49b3-b1a6-04d50ea1be4d",
  "providers": {
    "dataSource": { "providerId": "KpiSwqlDatasourceService", "properties": { "swql": "...", "dataFields": [ ... ] } },
    "adapter": { "properties": { "dataSource": { "properties": { "swql": "...", "dataFields": [ ... ] } } } }
  },
  "properties": { "widgetData": { "label": "100% Availability", "backgroundColor": "var(--nui-color-semantic-ok)", "units": "" } }
}
```

That is the same minimal adapter shape a `table` widget uses. So write the full form — it is
what the console emits when you build a tile in the UI — but **the absence of `componentId` is
not a defect**, and a checker that insists on it will reject working files. Where `componentId`
*is* present it always equals the tile's own id, in all 86 cases.

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
`linkMappingField` is what makes each slice clickable. `categoryField`, `valueField`,
`dataFormat`, `iconMappingField` and `colorMappingField` are on all 18 proportional widgets;
`linkMappingField` on 13 of them, so a chart without clickable slices simply omits it.

`dataFormat: "custom"` accompanies that per-row mapping, and is the only value in all nine
files. An empty `"editor": {}` sits alongside it on all 18, purpose **unverified here**.

`chartOptions.type` takes `DonutChart` (12), `PieChart` (5) or `HorizontalBarChart` (1).
`legendPlacement` takes `Right` (14), `Bottom` (3) or `None` (1), and `legendFormatter` is
present on all 18, always `GenericValueFormatterComponent`. None of these lists is necessarily
complete and all are **unverified here** beyond what the samples exercise.

Unlike a table, a proportional widget's adapter is a full one, with its own provider id:

```json
"adapter": {
  "providerId": "NOVA_DATASOURCE_ADAPTER",
  "properties": {
    "componentId": "chart",
    "propertyPath": "widgetData",
    "dataSource": { "properties": { "swql": "...", "dataFields": [ ... ] } }
  }
}
```

`componentId` is the literal string `"chart"` — the node's own key — rather than a GUID, on
all 18. That makes three distinct adapter shapes in the format: `NOVA_KPI_DATASOURCE_ADAPTER`
for a KPI tile, `NOVA_DATASOURCE_ADAPTER` for a chart, and an anonymous
`{"properties": {"dataSource": ...}}` for a table.

## `unique_key` collisions, and the reuse that is fine

`unique_key` is the only thing joining a placement to a definition, and **nothing enforces
that it is unique.** One author's file breaks it, in two different ways, and neither break is
visible from the console. A third author's five files are clean — 43 definitions, 43 distinct
keys — so this is a defect a careful author avoids, not something the format forces on you.

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

**Across files.** In another author's three dashboards, the widget
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

### A KPI tile id is not a `unique_key`, and reusing one is normal

This is the distinction to get right, because the two look alike and only one of them matters.

A `kpi_…` id keys an object *inside one widget's* `configuration`, so it only has to be unique
within that widget. Reuse across widgets is common and evidently harmless: one author uses the
same four tile ids in **fourteen different KPI widgets**, and another uses
`kpi_3d1205d9-595a-49b3-b1a6-04d50ea1be4d` for the single tile in **all six** of a dashboard's
widgets — six different queries, six different labels, one id, and the dashboard works.

So the rule is narrower than "regenerate every GUID": a **widget** `unique_key` must be unique
across the file, while a **tile** id only has to be unique within its widget. Regenerating both
on a copy still costs nothing and removes the need to remember which is which.

## Exporting and importing

The console's export button is one route; `Orion.Dashboards.Instances` is the other. The
entity publishes sixteen verbs in the 2026.2 contract and grants every operation, `invoke`
included, to `everyone`, and three of the verbs are the whole file story:

```bash
python3 tools/schema_query.py verb Orion.Dashboards.Instances Export
```

```text
Orion.Dashboards.Instances.Export
  returns: string
  REST:    POST /Invoke/Orion.Dashboards.Instances/Export
  parameters (1):
    dashboardId: number (required)
```

`Export(dashboardId)` takes the numeric `DashboardID` and returns the JSON this page
documents, as one string. `Import(definition)` is the reverse — the whole file travels as
the single string argument, so over REST the body is a JSON array whose one element is the
file serialised as a string, not the file spliced in as an object. The round trip in
PowerShell has the same two traps as any string-returning verb:

```powershell
# Invoke-SwisVerb returns XML; .InnerText is the JSON string you want.
$exported = Invoke-SwisVerb $swis 'Orion.Dashboards.Instances' 'Export' @(42)
Set-Content 'dashboard.json' $exported.InnerText

# Get-Content splits into lines by default. -Raw gives you one string.
$definition = Get-Content 'dashboard.json' -Raw
Invoke-SwisVerb $swis 'Orion.Dashboards.Instances' 'Import' @($definition)
```

**`Import` returns `System.Void`**, so a clean return tells you nothing about what arrived.
The file's `dashboards[].unique_key` is the same value as the server-side
`Orion.Dashboards.Instances.UniqueKey` property — inherited from `Orion.Dashboards.Entity`
along with `Owner`, `Private`, `IsSystem` and `LastUpdate` — which is what makes arrival
checkable:

```sql
SELECT DashboardID, DisplayName
FROM Orion.Dashboards.Instances
WHERE UniqueKey = @key
```

Run the same query **before** importing, as a collision check. What `Import` does when the
`UniqueKey` already exists on the server — update in place or a second dashboard — is
**unverified here**, so find out whether you are about to collide and decide deliberately
rather than learning the answer from a production server. To land a copy next to a
still-present original, rewrite the file first — see
[duplicating a dashboard onto the same server](modern-dashboard-authoring.md#duplicating-a-dashboard-onto-the-same-server).

`Clone(dashboardID, displayName, asPrivate)` is the server-side copy of a single dashboard,
no file involved, and it corroborates the `parent` reading above: the contract documents
`ParentID` as "ID of the dashboard from which given dashboard was cloned". Note the
contract's own inconsistency while you are here — `Export` declares `dashboardId` as a
number, while `Clone` and the widget-editing verbs declare `dashboardID` as a string.

The other thirteen verbs (`AddWidget`, `RemoveWidget`, `UpdateWidgetLocation`,
`SetVisibility`, `DereferenceWidget`, `WidgetToReference`, `RestoreToOriginal` and the rest)
edit a dashboard in place. Their signatures are in the contract —
`python3 tools/schema_query.py verbs --entity Orion.Dashboards.Instances` — but their
semantics are undocumented and **unverified here**.

## What this repository verified

Nine exports from three independent authors, parsed and checked against the extracted 2026.2
schema:

| | Author A | Author B | Author C |
| --- | --- | --- | --- |
| Files | 3 | 1 | 5 |
| Widget definitions | 17 | 27 | 31 |
| Embedded SWQL strings | 64 | 138 | 90 |
| Envelope: `version: 1` and the four keys | yes | yes | yes |
| `x + cols` never exceeding 12 | yes | yes | yes |
| `dataSource` / `adapter` copies byte-identical | 32 / 32 | **69 / 69** | 45 / 45 |
| `dataField` ids present in their own query | all | all | all |
| Placements resolving to a definition | all | all | all |
| KPI `tiles.nodes` ids having a config block | all | all | all |
| Distinct widget `unique_key`s | 17 / 17 | **14 / 27** | 31 / 31 |

**146 of 146 dataSource/adapter pairs are byte-identical** across all nine files. That is the
strongest single result here: the duplication is not decorative, and nothing in three authors'
independent work ever lets the two copies drift.

The one defect that shows up is the `unique_key` collision in author B's file, described above.
Author C's five files are clean on every check.

**Every unresolved name in any author's file is a custom property**, not a mistake: `Site` for
author A, and `Responsible_Group`, `Device_Type` and `Link_Type` for author B. Custom
properties are columns each customer adds to extend the product, so no extracted schema can
contain them — that is the point of them. See
[../automation/custom-properties.md](../automation/custom-properties.md) for enumerating the
ones your own server has, which is how you would validate a dashboard against your
installation rather than against the stock schema.

Every *platform* entity used checks out, including `Orion.Dashboards.Instances`, whose
`DisplayName` and `InstanceSiteId` are inherited from `System.Entity` and
`Orion.Dashboards.Entity` rather than declared on it. Author C's files widen the entity
surface considerably, reaching `NCM.Nodes`, `NCM.NodesView`, `NCM.ConfigArchive`,
`NCM.LatestTransferJobStatus`, `NCM.NodeProperties`, `Cirrus.CacheDiffResults`,
`Cirrus.NCM_NCMJobs`, `Orion.NetPath.ServiceAssignments`, `Orion.NetPath.Tests`,
`Orion.StatusInfo` and `Orion.ResponseTime` — all of which resolve.

### One name that does not resolve

`NCM.NodesView` is used by a working dashboard — selecting `CoreNodeID`, `NodeName`,
`NodeStatus`, `LeftConfigID`, `RightConfigID` and `RunningVsStartupStatus` from it to show
running-versus-startup config conflicts — and **it is not in the published 2026.2 schema**. It
is not a custom property either: custom properties are columns on an existing entity, and this
is an entity name.

The schema has 72 `NCM.*` entities, including `NCM.Nodes` and `NCM.FirmwareOperationsView`, so
both the namespace and the `…View` suffix convention are real. The likely readings are that it
exists on the author's version but is absent from the SDK's published metadata, or that it was
added or removed between versions. Which one is **unverified here**. Check your own server
before relying on it:

```sql
SELECT e.FullName, e.BaseType
FROM Metadata.Entity e
WHERE e.FullName LIKE 'NCM.%View'
```

That is the general lesson rather than a one-off: the extracted schema in this repository is
one published version, and a working dashboard can legitimately name something it does not
contain. See [../swis/metadata-introspection.md](../swis/metadata-introspection.md).

### Two artefacts worth knowing about

**Stray line-continuation backslashes.** One widget in author B's file carries a `\` at the end
of most lines of its SWQL, including after a column alias (`AS [Day]\`), left behind by
whatever it was pasted from. Whether the console tolerates them is **unverified here**, but
they are worth removing before you copy such a query.

**`_LinkFor_` and `_IconFor_` column names in a Modern Dashboard.** Author C's NetPath query
aliases columns `[_LinkFor_Destination]` and `[_IconFor_Destination]`. Those names are the
*classic* console's Custom Query widget convention — see
[custom-query-widget.md](custom-query-widget.md) — and mean nothing to a Modern Dashboard,
which binds columns explicitly through `dataFieldIds`. The query works because the formatter
names those columns, not because of what they are called. It is a habit carried across from
the old widget, and harmless, but do not expect the naming alone to create a link here.

One consequence worth stating, because it cuts the other way from the usual advice: in the
classic widget both halves of `[_LinkFor_X]` are case-sensitive and a mismatch fails silently
(see [custom-query-widget.md](custom-query-widget.md#the-naming-convention)). In a Modern
Dashboard the string is just an alias, so its casing is free — but it must then match the
`dataFieldIds` entry exactly, which is the same discipline arriving through a different door.

## See also

- [modern-dashboard-authoring.md](modern-dashboard-authoring.md) — writing one, the filter URL
  grammar, and the contract for asking an AI to generate a whole file
- [../automation/custom-properties.md](../automation/custom-properties.md) — the custom
  properties these dashboards filter on
- [variables.md](variables.md) — the other `${...}` system, which is unrelated to
  `${data.rowData.…}`
- [../swql/README.md](../swql/README.md) — the query language every widget is built on
- [../swis/invoke-verbs.md](../swis/invoke-verbs.md) — how `Export`, `Import` and `Clone`
  are called, REST and PowerShell

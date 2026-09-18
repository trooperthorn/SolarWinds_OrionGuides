# Modern Dashboard authoring: evidence from the 2026.4 export

This audit turns a real Observability Self-Hosted export into guidance for creating and modifying dashboards. It is a versioned evidence supplement, not an importable dashboard or a claim that every exported setting has been tested independently.

## Evidence and scope

- Package: `dashboards-pkg_SWOSH-SVR_2026-09-18_140510.zip`.
- Package SHA-256: `4fe913780f264bb750fda8314d678541f8863f3615ad2c88f1f2aeb1110219af`.
- Manifest platform: **SolarWinds Platform 2026.4.0.3320**, SWIS v3; exporter: DashboardPorter 0.1.
- Export timestamp: `2026-09-18T19:05:10.3061800Z`.
- All **127** manifest item hashes match the archived JSON bytes. All widget placements resolve to definitions in their respective files.
- The owner identifies **124 dashboards as supplied with the product** and three as custom: **ERCOT Texas Power Grid**, **Minimal Dashboard Template**, and **SOC2**. This is owner-reported provenance, not independent verification against a pristine vendor installation.
- The package contains dashboard configuration, not proof that every widget currently renders useful data. No commands, queries, imports, or actions contained in the attachment were executed against a server.
- Comparison baseline: `trooperthorn/SolarWinds_OrionGuides` commit `fcec2e3bc61244f0afeb1088fb810c38a940789d`. Its extracted schema is **2026.2**, earlier than this export.

Evidence references below use the archive-relative filename and a JSON Pointer. A `~1` segment represents the literal `/` configuration key. Where noted, dashboard-level `configuration` must be JSON-decoded a second time.

## What the package adds

| Widget type | Definitions | Practical use |
|---|---:|---|
| `multicharttimeseries` | 239 | Metric history through the PerfStack data provider |
| `table` | 222 | Inventory, alerts, history, formatted measurements |
| `proportional` | 192 | Donuts, pies, vertical bars, horizontal bars |
| `kpi` | 136 | Current metrics, counts, costs, and text labels |
| `drilldown` | 4 | A hierarchy such as region → availability zone → network → subnet |
| `entityPropertyDetails` | 3 | Selected properties of the entity in context |
| `entityDrilldown` | 2 | Entity/group navigation backed by content-model metadata |
| `risk-score` | 1 | Specialized vulnerability risk presentation |
| **Total** | **799** | **798 distinct widget keys across the package** |

The totals count definitions as exported, including a repeated Interfaces widget in two files. They are not counts of independent rendered components. KPI tiles are nested within a KPI widget and are counted separately from widget definitions.

The three custom dashboards contain 23 definitions: ERCOT has 12, Minimal has 2, and SOC2 has 9. All eight widget types occur in the owner-reported vendor group; the custom group uses only table, proportional, and KPI widgets.

## 1. Time-series charts are now evidenced in JSON

The older guide describes a `timeseries` widget from a demonstration but lacks an exported example. This package supplies **239 instances of the exact serialized type `multicharttimeseries`**. Every one uses `TimeseriesPerfstackDatasourceService` with `configType: "json"`.

The root is:

```text
widgets[i].configuration["/"].providers.dataSource
```

For `AKS_Cluster_Instance_Details.json`, widget 1, the provider properties include:

```json
{
  "presetTime": "last12Hours",
  "configType": "json",
  "metricId": "Orion.Cloud.Azure.KubernetesClusterStatistics.ApiserverCpuUsagePercentage",
  "instanceType": "Orion.Cloud.Azure.KubernetesCluster",
  "swql": "SELECT TOP 1 InstanceSiteId, InstanceType as EntityType, ID as EntityId FROM Orion.Cloud.Azure.KubernetesCluster"
}
```

This is an observed vendor configuration fragment, not a standalone query recommendation. The SWQL selects **entity identity** (`InstanceSiteId`, `EntityType`, `EntityId`); `metricId` selects the metric. It is not an arbitrary SWQL result with time/value columns. Copying it onto a context-free dashboard could select an unintended first entity.

`timeframeSelection.properties.timeframe.selectedPresetId` separately carries `last12Hours`. Preserve both the provider and selection configuration when modifying an example. Precedence when they disagree is not established by the export.

Widget 7 in the same file has five comma-separated metric identifiers for pod states. This provides a concrete multiple-metric configuration pattern. It does not prove that an arbitrary calculated SWQL column can be registered as a PerfStack metric.

Some time-series definitions retain `startTime` and `endTime` strings together with a relative preset. Some `id` values are `"UNUSED"`. Do not interpret every nonempty id as a saved PerfStack project, or assume stale absolute dates override the preset. Every observed `configType` is `json`; this package does not establish the saved-project mode contract.

**Repository change:** add a dedicated time-series section using the exact type and provider above. Keep the older saved-project workflow as a separate, differently sourced mode.

## 2. Dashboard identity, groups, routes, and context form a view hierarchy

The files are not simply independent pages with different names. **70 pages carry a groupId**, and **113 carry routeId and dashboardRoutes values**.

For example, `AWS_Costs.json` and `AWS_Costs (2).json` both have the dashboard name `AWS Costs`, but:

| Property | Month page | Year page |
|---|---|---|
| `groupId` | `AwsCostsDashboard` | `AwsCostsDashboard` |
| `groupRank` | 1 | 2 |
| `groupMemberName` | `Month` | `Year` |
| `groupName` | `AWS Costs` | `AWS Costs` |
| `routeId` | `aws-monthly-costs` | `aws-yearly-costs` |
| `unique_key` | `CLM-Aws-Monthly-Costs` | `CLM-Aws-Yearly-Costs` |

The filename suffix `(2)` is not enough to identify a duplicate that should be discarded. Group membership, route, key, and tab label distinguish the views.

There are **545 named widget keys** and **254 GUID-shaped widget keys**. `CLM-Aws-DatabaseCpuUtilizationChart` is a normal vendor key in this corpus. Therefore “every widget key must be a GUID” is an authoring convention, not a format requirement. Fresh GUIDs remain a convenient way to avoid collisions for newly authored copies.

**Repository change:** document separate clone/update behavior. Preserve identity when deliberately updating an existing view. When cloning, remap dashboard/widget identities and review routes, group membership, navigation links, and any shared widget references together. Do not regenerate arbitrary metric ids, column ids, or entity references indiscriminately.

## 3. Decode the dashboard-level configuration string

In these exports, `dashboards[i].configuration` can contain a JSON string; it is not always an already-decoded object. One value decodes to `null`. A parser that inspects only the outer document misses most view-level options.

Observed decoded keys:

| Key | Pages | What it lets an author investigate |
|---|---:|---|
| `globalFilter` | 78 | Entity filter configuration and groupable properties |
| `urlTabs` | 18 | Tab navigation to URL destinations |
| `messages` | 14 | Conditional notices within the view |
| `toolbarItems` | 11 | View-level toolbar configuration |
| `nocView` | 11 | NOC view settings, refresh cadence, dark theme |
| `preserveTimeFrameAcrossTabs` | 6 | Whether a time selection is preserved between tabs |
| `customToolbarMenuItems` | 1 | Custom menus and command sequences |
| `hideDefaultMenuItemsGroup` | 1 | Suppression of the default menu group |

These counts establish presence, not that an empty list activates a feature. For example, `toolbarItems` can be empty.

The custom ERCOT page has this decoded configuration:

```json
{
  "nocView": {
    "enabled": true,
    "refreshInterval": 15,
    "unit": "seconds",
    "darkThemeEnabled": true
  }
}
```

Widget refresher settings remain separate. A 15-second NOC refresh does not prove that the API Poller collects every 15 seconds. Polling, widget refreshing, time selection, and screen rotation/refresh are distinct controls.

## 4. Global filtering and contextual detail pages need their surrounding configuration

`AWS_Costs (2).json` names account, service, region, and category as groupable properties. Other cloud pages configure account filtering and provider-specific restrictions. `APIC_Members.json` binds a condition argument from `${opid.entityIds[0]}`.

Cloud detail widgets often query a dashboard-specific entity without a visible `WHERE` on an object id. That does not establish an unfiltered query contract. Routes, view context, entity metadata, provider behavior, and the surrounding page may supply the scope.

Links also carry filters, for example a compute cost tile directs to a cost page with a `filters=` expression. A useful dashboard can therefore progress from estate summary → category → entity → metric history instead of adding ever more columns to one table.

**Authoring rule:** transplant the context and filters with the widget, or replace them with an explicit, verified scope. Test the destination with two different entities/accounts to prove the view is scoped correctly. Do not assume that appending an arbitrary filter string makes every provider honor it.

## 5. ERCOT proves the hidden timestamp sort pattern precisely

The relevant source is `ERCOT_Texas_Power_Grid.json`, widget 4, under:

```text
/widgets/4/configuration/table/properties/configuration
```

The query returns a single DateTime field, `Observed`. **Both display columns bind to it.** The export no longer needs a separate Hour string from SWQL:

```json
{
  "columns": [
    {
      "id": "column_092154af-31b7-4b19-9848-28436913ac23",
      "label": "Hour",
      "isActive": true,
      "formatter": {
        "componentType": "DatetimeFormatterComponent",
        "properties": {
          "dataFieldIds": {"value": "Observed"},
          "option": "0",
          "isUtc": true,
          "replaceDate": true,
          "replaceEmptyValue": false,
          "emptyValueDisplay": "(Unknown)"
        }
      }
    },
    {
      "id": "column_3238dd52-d57b-45e3-afef-6e0e3b087d86",
      "label": "HIDE ME",
      "isActive": false,
      "formatter": {
        "componentType": "DatetimeFormatterComponent",
        "properties": {
          "dataFieldIds": {"value": "Observed"},
          "option": "0",
          "isUtc": true,
          "replaceDate": false,
          "replaceEmptyValue": false,
          "emptyValueDisplay": "(Unknown)"
        }
      }
    }
  ],
  "sorterConfiguration": {
    "sortBy": "column_3238dd52-d57b-45e3-afef-6e0e3b087d86",
    "descendantSorting": true
  }
}
```

This is a partial configuration excerpt; the three frequency columns are omitted. It is not a complete import file.

The contributor separately confirmed that this sort behavior works. `sortBy` names a **column configuration id**, not the query field alias. An inactive display column can retain its role as the sorter.

The exported query applies `ToLocal()` while these formatters carry `isUtc: true`. Preserve this observed combination when documenting the working example; the flag's exact conversion semantics are not proven by its name. Verify on the target server/browser before applying an extra timezone conversion.

## 6. Numeric formatting, text KPIs, and thresholds need distinct rules

There are **131 SimpleNumberFormatterComponent** definitions. All bind a `value` and carry `suffixText`; 125 also carry `prefixIcon`. The ERCOT frequency columns use:

```json
{
  "componentType": "SimpleNumberFormatterComponent",
  "properties": {
    "dataFieldIds": {"value": "Min Hz"},
    "prefixIcon": "",
    "suffixText": "Hz",
    "replaceEmptyValue": false,
    "emptyValueDisplay": "(Unknown)"
  }
}
```

This keeps the SWQL result numeric. The same pattern appears with MW, GB, MB/s, dollars, and other suffixes. `prefixIcon` is an icon setting, not evidence of a currency-text prefix control.

**Fixed trailing zeros remain unproven.** No widget configuration key matching decimal, precision, fraction, digits, or numberFormat was found. No such control appears in the 131 simple-number formatter property sets. Earlier advice to set a fixed-decimal option was not supported by this export. `ROUND()` still only changes the numeric value; it does not guarantee `60.000` in the UI.

Text KPIs are also present in the vendor group, including cost strings and `N/A` values. A blanket claim that KPI widgets only accept numeric values is too strong. However, a text-capable display does not establish that numeric threshold comparison works on values such as `60.01 Hz` or `$42.75`.

**ERCOT review items:** its frequency KPI returns `System.String` while numeric thresholds are enabled, and its highest settlement-price KPI also returns `System.String` with thresholds enabled. Keep a numeric query and use unit presentation when threshold coloring matters. Verify high-side and low-side behavior deliberately. `reversedThresholds: true` is recorded for the low-frequency tile; that alone does not create a two-sided acceptable frequency band.

The package also contains 56 threshold formatters, with metric threshold names, instance/site field bindings, and visualization options. Copy a known compatible threshold family and verify its bindings, rather than applying a generic color to all numbers.

## 7. A proportional widget has several chart forms

Observed `chartOptions.type` values:

- `DonutChart`: 111.
- `VerticalBarChart`: 67.
- `PieChart`: 8.
- `HorizontalBarChart`: 6.

Legend placements include Right, None, and Bottom. Labels, numerical value fields, colors, links, legend formatters, and interaction handlers are independent choices.

For a useful bar chart, keep the chart value numeric, return the intended category grain, and document the unit and time window. Adding `$` or `MW` in SWQL turns the chart measure into text. The export does not establish how all chart variants handle negative DC tie values; that remains a rendering test, not a JSON inference.

## 8. Tables can be navigators and operational views

The 222 tables include more than raw grids:

- `EntityLinkFormatterComponent` and `LinkFormatterComponent` connect rows to entity/detail views.
- Status, severity, duration, color, threshold, and HTML formatters carry different data-field contracts.
- Multiple visible or hidden columns can bind to the same source field.
- `selectionConfiguration` can specify multiple selection, row clicking, and a stable `trackByProperty`.
- `scrollType`, `paginatorConfiguration`, `hasVirtualScroll`, and `searchConfiguration` coexist. The package includes `scrollType: "virtual"` beside `hasVirtualScroll: false`, so precedence should be tested rather than inferred from one property.
- `descendantSorting` appears as booleans and strings such as `"desc"` and `""`. New custom examples should use a demonstrated configuration rather than normalize every vendor export blindly.

`All_Active_Alerts.json` demonstrates multi-selection with `AlertActiveID`, a paginator with 10/20/50/100 choices, and a configured sort column. Some toolbar commands invoke write operations. Those serialized actions are evidence of UI capability, not authorization to execute them or proof that their web endpoints are a stable public automation API.

## 9. Drilldown and entity detail widgets are separate authoring patterns

`AWS_Compute.json`, widget 13, uses `DrilldownSwqlDatasourceService` and `NOVA_DRILLDOWN_DATASOURCE_ADAPTER`. Its `groupBy` contains region, availability zone, virtual network, and subnet; the leaf carries the entity name and link. It supplies group and leaf component mappings, not an ordinary table column collection.

`Home_Summary_-_Overview.json` includes two `entityDrilldown` widgets. Their definitions include content-view queries, property path metadata, grouping, and content-type bindings. `entityPropertyDetails` likewise uses selected property definitions and composite formatter mappings. These are not safely generated by changing a table's `type` string.

`risk-score` is a separate specialized widget in `Vulnerability_and_Risk_Dashboard.json`; it records a 0–10 range and risk-oriented labels. Its presence does not establish a generic gauge contract or universal module availability.

**Repository change:** use separate recipes for ordinary SWQL widgets, metric time-series widgets, hierarchical widgets, and module-specific widgets. Begin specialized examples from an exported working configuration and preserve their context dependencies.

## 10. Query duplication is an authoring policy, not a universal export invariant

The audit found **642 blocks** with a data source and adapter where at least one side contained SWQL:

- 635 have a query on both sides.
- 626 of those are byte-identical.
- 9 have differing queries; some differences are whitespace/case, while others affect selected columns or null handling.
- 7 have only the source-side query; these include four drilldown adapters and three proportional adapters.
- Among the 635 two-query blocks, 8 also have unequal `dataFields` arrays.

Concrete differences include `GCP_Cloud_Router_Details.json` widget 4 (BGP status projection) and `GCP_Database_Details.json` widget 2 (TOP selection versus CASE null handling). Do not infer which copy wins at runtime, and do not silently reconcile a vendor export without checking it in the console.

The repository should still require matching query copies for newly authored ordinary widgets when their adapter stores a copy. It should distinguish **strict authoring validation** from **evidence inspection**. Otherwise a tool will reject useful vendor evidence or teach an AI that every difference is necessarily the root cause of a failure.

## 11. Graphical query metadata is present

Four serialized data-source property blocks use `type: "graphical"`; these include duplicated source/adapter blocks, not four independent widgets. `GKE_Entities.json` widget 1 carries `editor.entity` and `editor.state` alongside its SWQL and field metadata.

A change to the SWQL alone can leave graphical editor state describing a different query. For generated custom work, either keep the editor model consistent or use a tested hand-edit workflow. “All exports are hand-edit” only described the older sample set.

## 12. Version and validation boundaries

The audit extracted **750 distinct SELECT strings** from the outer documents and decoded dashboard configuration. The repository's 2026.2 static checker produced findings for 453 of them, including 136 distinct unknown entity names. Many are module-specific dashboard/content-model entities in this 2026.4 export.

This does **not** prove 453 broken queries. It shows why an older public schema and a partial static parser cannot certify every product dashboard. No-findings also does not prove runtime success. A repository should record the source platform version, module/provider dependency, query provenance, and target-server validation separately.

The existing query extractor should eventually cover `swqlQuery` and conditional `query` fields inside decoded configuration as well as ordinary `swql`. It must never execute exported actions while inspecting them.

## Specific improvements for the three custom dashboards

### ERCOT Texas Power Grid

1. Adopt the exact exported hidden timestamp/date formatter configuration as the canonical compact-time example.
2. Keep numeric frequency and price KPI outputs wherever numeric thresholds are enabled; reserve concatenated labels for presentation-only values.
3. Update the frequency subtitle from “per observation” to “per local clock hour,” matching the actual query.
4. Teach three different measurements explicitly: latest value, hourly summary, and a six-hour settlement summary. Preserve UTC filters and local display conversion as separate concerns.
5. Investigate a metric-backed capacity/demand chart using an API Poller metric supported by the target server's PerfStack registry. The package provides the general serialization pattern but not the API Poller metric registration needed to claim this chart is ready.
6. Keep unused capacity distinct from ERCOT operating reserves; signed tie flows should retain their documented meaning and numerical values.

### Minimal Dashboard Template

Keep it minimal: one numeric KPI and one table with a timestamp, numeric measurement, status/link mappings, and clear data-source duplication. Use the richer vendor patterns as optional recipes instead of packing them all into the starter file.

### SOC2

Use tables and navigation to expose evidence scope, exceptions, observation age, and entity links. Operational status and configured thresholds do not themselves establish compliance. A useful next iteration is summary counts → exceptions → supporting object detail, with clearly bounded observation windows.

These are design recommendations. The source dashboards have not been edited or re-imported by this audit.

## Authoring implications and follow-up work

1. **Use the corrected authoring rules:** identifiers need not be GUIDs; query-copy equality is a safe rule for authored widgets, not universal vendor evidence; graphical mode exists; KPI display can be text; multiple time-series/provider modes must be distinguished.
2. **Keep versioned evidence separate from universal format claims.** This supplement records archive files/pointers and owner-reported provenance; the older guides retain their nine-file baseline.
3. **Retain a machine-readable evidence index.** The [evidence index](../../reference/dashboard-evidence/2026-09-18.json) records archive/item hashes, counts, selected excerpts, provider types, and exceptions. Raw site-specific exports are not part of the shipped examples.
4. **Build further complete recipes from the evidenced fragments:** hidden date sorting, numeric suffixes, low-side thresholds, metric time series, context-filtered drilldown, grouped tabs/routes, NOC refresh, and conditional notices.
5. **Extend an audit tool before relaxing the strict validator:** decode nested configuration, inventory unknown providers without rejecting them, check references and query copies, flag numeric-threshold/text-value combinations, and report schema-version gaps separately.
6. **Keep acceptance tests explicit:** verify two entity contexts, midnight ordering, empty/unknown values, signed chart values, threshold direction, time presets, and the actual rendered result after import. A valid JSON file is only the first check.

The practical change for AI-assisted authoring is to choose the data grain, entity scope, widget/provider contract, and field types first. Then bind presentation, sorting, navigation, and refresh behavior using an evidenced recipe. Fragments establish field shapes, but complete imports and provider behavior still require target-server testing.

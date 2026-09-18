# An ERCOT Texas power grid dashboard from API Pollers

A public Datadog dashboard, [ERCOT (Texas Power Grid) by @danopia](https://p.datadoghq.com/sb/5c2fc00be-393be929c9c55c3b80b557d08c30787a),
has tracked the Texas grid since the February 2021 winter storm: capacity against demand,
frequency, time error, inertia, DC tie flows, ancillary reserves, settlement point prices, the
Energy Emergency Alert level, weather at fourteen airports, and county outage counts. Its
collector is a
[small Deno program](https://gist.github.com/danopia/c0c4313b4809d565af7c7738bcdbeec7) that
scrapes ERCOT's HTML pages and posts gauges to Datadog.

This page rebuilds that dashboard on SolarWinds Observability Self-Hosted with nothing but
the platform's own pieces: five [API Poller](../polling/api-pollers.md) templates that read the
sources directly, one Modern Dashboard file whose widgets query the values those pollers store,
and one SAM template held in reserve for the numbers an API Poller cannot reach. There is no
intermediary process to run, which is the point
[api-poller-unifi-network.md](../polling/api-poller-unifi-network.md#why-build-a-multi-metric-poller-against-a-public-api-at-all)
makes about this exact dashboard: reaching the source removes a dependency rather than adding
one.

Every entity and property name below is checked against the extracted 2026.2 schema on each
build, and every query is run through `tools/validate_swql.py`. Every endpoint and every
response shape was read live on 2026-09-17. The original files were not imported into a server during construction. Subsequent
contributor query and widget observations are recorded below; they do not verify a fresh
import of the shipped files, and the last section is precise about what remains open.

The files:

| File | What it is |
| --- | --- |
| [scripts/api-pollers/ercot-grid-conditions.apipoller.template](../../scripts/api-pollers/ercot-grid-conditions.apipoller.template) | EEA level and grid condition, frequency, inertia, DC ties, demand and capacity, every minute |
| [scripts/api-pollers/ercot-ancillary-services.apipoller.template](../../scripts/api-pollers/ercot-ancillary-services.apipoller.template) | Physical Responsive Capability and the reserve and regulation capacities, every five minutes |
| [scripts/api-pollers/ercot-settlement-point-prices.apipoller.template](../../scripts/api-pollers/ercot-settlement-point-prices.apipoller.template) | Real-time settlement point prices for seven hubs and eight load zones, every fifteen minutes |
| [scripts/api-pollers/metar-texas-airports.apipoller.template](../../scripts/api-pollers/metar-texas-airports.apipoller.template) | Temperature, dewpoint, wind, gust and altimeter at fourteen airports, every thirty minutes |
| [scripts/api-pollers/poweroutage-us-texas.apipoller.template](../../scripts/api-pollers/poweroutage-us-texas.apipoller.template) | County outage counts, experimental: the API now needs a paid key |
| [scripts/sam-templates/ercot-system-conditions-html.apmtemplate](../../scripts/sam-templates/ercot-system-conditions-html.apmtemplate) | The fallback: two PowerShell components that parse ERCOT's HTML page, with the script standalone as [ercot-system-conditions-html.ps1](../../scripts/sam-templates/ercot-system-conditions-html.ps1) |
| [scripts/dashboards/ercot-texas-power-grid.json](../../scripts/dashboards/ercot-texas-power-grid.json) | The Modern Dashboard: one KPI row, seven tables, three bar charts, and a poller health table |
| [scripts/swql/18-ercot-grid.swql](../../scripts/swql/18-ercot-grid.swql) | The queries, with the ones that confirm an import and find values that never produced a number |

## What changed since 2021

The Datadog collector's six sources are the starting point, and three of them no longer exist
in the form it read. Checked on 2026-09-17:

| Source the collector read | Now | Read here instead |
| --- | --- | --- |
| `ercot.com/content/cdr/html/real_time_system_conditions.html` | Still served, same table layout | `api/1/services/read/dashboards/dc-tie-flows.json` and `supply-demand.json` for the API Poller; the page itself for the SAM fallback |
| `ercot.com/content/cdr/html/as_capacity_monitor.html` | **404** | `ancillary-service-capacity-monitor.json`, which carries the same numbers under short keys |
| `ercot.com/content/cdr/html/real_time_spp` | Redirects to `real_time_spp.html`, same table | `system-wide-prices.json`, one row per 15-minute interval |
| `ercot.com/content/alerts/conservation_state.js` | **404**; the Datadog page itself notes the EEA level stopped in 2022 | `daily-prc.json`, whose `current_condition.eea_level` is the same integer |
| `aviationweather.gov/metar/data?format=decoded` | **No longer answers**; the Aviation Weather Center replaced its HTML forms with a JSON API in 2023 | `aviationweather.gov/api/data/metar?ids=KAUS&format=json` |
| `poweroutage.us/api/web/counties?key=...` | **401** with the key the collector embedded; poweroutage.us now sells API access | The same URL with an assign-time `${POWEROUTAGE_KEY}` placeholder, unverified |

The ERCOT JSON endpoints are the ones ERCOT's own grid-conditions pages fetch, under
`https://www.ercot.com/api/1/services/read/dashboards/`. They answered a plain `curl` with no
browser user agent and no cookie, which is what makes them pollable. Two things about them
shape everything below:

- **Most of them are the whole operating day, not the current reading.** `dc-tie-flows.json`
  is an array of one row per ten seconds since midnight, `daily-prc.json` the same, and
  `supply-demand.json` one row per five minutes with the rest of the day filled in as forecast
  rows. Only `ancillary-service-capacity-monitor.json` and the `current_condition` object of
  `daily-prc.json` hand back a single current value. So "the latest reading" has to be a
  JSONPath that selects the last element of an array, and that is the one thing about these
  templates this repository could not verify offline. The next section says what to do about it.
- **They are not small.** By evening the two ten-second files are each over 1 MB. A one-minute
  poll of the grid template moves on the order of 3 GB a day. That is fine on a server link and
  worth knowing before assigning it to a remote polling engine.

The METAR API and the poweroutage.us API return single-object or single-array responses and
have no such problem.

## Why API Pollers, and the two places they stop

An API Poller is the right tool for this because the sources are JSON over HTTPS with no
authentication, each value is one number at one path, and the platform then owns the
history, the thresholds and the status. Nothing has to run anywhere. It falls short in two
specific places, and both are handled rather than ignored.

**Selecting the newest row.** The templates use the JSONPath slice `[-1:]` for the last
element of an array, and `[?(@.forecast==0)]` to skip forecast rows first, so a demand path
reads `$.['data'].[?(@.forecast==0)].[-1:].['demand']`. The platform's JSONPath dialect is
not published. [api-poller-vendor-templates.md](../polling/api-poller-vendor-templates.md#header-a-jsonpath-over-the-response-headers)
establishes from SolarWinds' own ServiceNow template that filters and recursive descent are
accepted, but that was a filter against response headers, and no shipped template uses a
slice. **Whether `[-1:]` and a body filter resolve is unverified here.** The `$.['name']`
bracket form the platform writes is what Json.NET's `SelectToken` produces, and Json.NET
accepts both constructs, which is the reason to expect them to work and not a reason to
assume it. If those values sit at Unknown after assignment while the `current_condition` values
on the same poller read normally, the paths are the problem, not the endpoint, and the
fallback below covers every number they carry.

**Values only the HTML page has.** Instantaneous Time Error, the BAAL exceedance count,
Average Net Load, wind and PVGR output, and the fifth DC tie (DC_S, Eagle Pass) appear on the
Real-Time System Conditions page and in none of the JSON files in a form a path can reach
(wind and solar are in `fuel-mix.json`, keyed by timestamp string, which no JSONPath can
select the newest of). A [SAM template](../modules/sam-templates.md) with a `PowerShell`
component parses the page instead. It is shaped against the same real 2026.4 export
[sam-udp-port-exhaustion-template.md](../modules/sam-udp-port-exhaustion-template.md#what-is-verified-and-what-is-not)
documents, runs on the polling engine in Local Host mode so it needs no WinRM and no
credential, and emits the `Message.<Name>` / `Statistic.<Name>` pairs that
[sam-templates.md](../modules/sam-templates.md#dynamic-script-columns-dynamiccolumnsettings-and-the-statisticname-output-contract)
proves from SolarWinds' MongoDB template. The page is split across two components,
`conditions` (nine values) and `dcties` (five), because a script component carries at most
ten pairs. The script was run on a Windows 11 host against the live page in both modes on
2026-09-17 and returned every row.

The dashboard reads the API Poller values. If you end up on the SAM template for the grid
numbers, the last two queries in
[18-ercot-grid.swql](../../scripts/swql/18-ercot-grid.swql) read its values and history, and
the widget queries change from `Orion.APIPoller.ValueToMonitor` to
`Orion.APM.DynamicEvidenceCurrent` in the way those two show.

A third limit is the dashboard's rather than the poller's: **a Modern Dashboard has no
SWQL-driven time-series widget.** Every line chart on the Datadog page becomes a windowed
history table here, and the way to get an actual chart is the `timeseries` widget backed by a
saved PerfStack project, which [modern-dashboards.md](../webui/modern-dashboards.md#a-fourth-type-timeseries)
describes and this repository has no export of.

## The five pollers

All five poll `GET` with an `Accept: application/json` header and no credential. The
`PollingInterval` on each is in minutes, and follows the interval the Datadog collector used
for the same source.

### ERCOT Grid Conditions, every minute

Three requests, eleven values.

| Request | Endpoint | Values | Path form |
| --- | --- | --- | --- |
| 0 | `daily-prc.json` | EEA Level (warn above 0, critical above 1); Grid Condition State (`normal` mapped to 0, anything else to the fallback 5, so a new vocabulary alerts); Energy Level Index | `$.['current_condition'].['eea_level']`, a scalar; verified shape |
| 1 | `dc-tie-flows.json` | Grid Frequency (Hz), System Inertia (MW-s), DC_E, DC_N, DC_L, DC_R tie flows (MW) | `$.['data'].[-1:].['currentFrequency']`; slice unverified |
| 2 | `supply-demand.json` | Actual System Demand (MW), Total System Capacity (MW) | `$.['data'].[?(@.forecast==0)].[-1:].['demand']`; filter and slice unverified |

`current_condition` also carries `prc_value`, the Physical Responsive Capability, but as a
string with a thousands separator (`"11,490"`), and whether the poller parses that as a
number is unverified, so PRC is read as a number from the ancillary endpoint instead. The
grid condition vocabulary beyond `normal` is not published; ERCOT's page shows titles such as
"Normal Conditions", and the `state` values behind the other levels were not observable on a
normal day. Mapping only `normal` and letting everything else fall to a value above critical
is deliberate: the day the state changes is the day you want to hear about it, and you learn
the new string from `Metric` reading 5.

### ERCOT Ancillary Services, every five minutes

One request, fourteen values from `ancillary-service-capacity-monitor.json`. The response is a
dozen groups, each an array of `[key, value]` pairs whose first element is the header
`["key","value"]`, so every path is positional: `$.['data'].['regulationCapacityGroup'].[1].[1]`
is the value of the first data row. That is the same coupling
[api-poller-vendor-templates.md](../polling/api-poller-vendor-templates.md#path-a-jsonpath-into-the-response-body)
describes for SolarWinds' Azure template, with the same consequence: reorder the group and the
metric keeps reporting under the old label. To make that checkable, the key each position held
on 2026-09-17 is written into the value's `DisplayName` in square brackets, so `Regulation Up
Capacity (MW) [regUpCap]` can be compared against a fresh response in one glance.

The values, and the Datadog widgets they correspond to:

| Value | Key | Datadog widget |
| --- | --- | --- |
| Physical Responsive Capability PRC (MW) | `prc` | Unused Capacity and "Operating Reserves" |
| Regulation Up / Down Capacity, Up / Down Deployed (MW) | `regUpCap`, `regDownCap`, `regUpDeployed`, `regDownDeployed` | Supply Regulation |
| Non-Spin Off-Line Generation Capacity, Quick Start Awards (MW) | `nsrCapOffGen`, `nsrAwdQs` | Offline generation, minus Quick Start |
| RT Reserve On-Line, On-Line and Off-Line (MW) | `rtReserveOnline`, `rtReserveOnOffline` | On_Line_reserve_capacity, On_Line_and_Off_Line_reserve_capacity |
| Capacity Available to Increase / Decrease Generation (MW) | `capIncreaseGenBp`, `capDecreaseGenBp` | ERCOT Ancillary Real Time |
| Total Reserve Capacity RegUp+RRS+ECRS+NSR (MW) | `sumCapResRegUpRrsEcrsNsr` | ERCOT Ancillary Real Time |
| Responsive Reserve Awards Generation, ECRS Awards Generation (MW) | `rrAwdGen`, `ecrsAwdGen` | ERCOT Ancillary Real Time |

ERCOT's own PRC thresholds are the ones worth setting after import: an EEA 1 is declared when
PRC falls below 3,000 MW and EEA 2 below 2,000 MW, but those are low-side alerts, and whether a
`ThresholdRule` other than `GreaterThan` exists is
[still unverified here](../polling/api-pollers.md#the-threshold-boundary), so the template
leaves them nil rather than shipping a rule that reads backwards.

### ERCOT Settlement Point Prices, every fifteen minutes

One request, fifteen values from `system-wide-prices.json`: `rtSppData` holds one row per
15-minute interval of the operating day with the seven hubs (`HB_BUSAVG`, `HB_HOUSTON`,
`HB_HUBAVG`, `HB_NORTH`, `HB_PAN`, `HB_SOUTH`, `HB_WEST`) and eight load zones (`LZ_AEN`,
`LZ_CPS`, `LZ_HOUSTON`, `LZ_LCRA`, `LZ_NORTH`, `LZ_RAYBN`, `LZ_SOUTH`, `LZ_WEST`) as camel-case
keys, so every path is `$.['rtSppData'].[-1:].['hbHouston']` and the slice caveat applies. The
same file carries `damSppData`, the day-ahead hourly prices, which the Datadog page did not
show and this template does not read. Prices include the Real-Time Reliability Deployment Price
Adders, as ERCOT's page says in its footnote. Thresholds are nil: the right alert level is a
market judgement, and for scale the 2021 event cleared at the then cap of $9,000/MWh.

### Texas Airport Weather (METAR), every thirty minutes

Fourteen requests, seventy values. The Aviation Weather Center's data API returns a JSON
array, and asking for one station per request (`?ids=KAUS&format=json`) makes `$.[0]` that
station by construction rather than by the positional luck
[api-poller-unifi-network.md](../polling/api-poller-unifi-network.md#what-the-variable-mechanism-cannot-do)
warns about. Each request reads `temp`, `dewp`, `wspd`, `wgst` and `altim`.

Two differences from the Datadog page. The API's units are Celsius, knots and hectopascals,
where the decoded page gave MPH and inches of mercury; the dashboard converts in SWQL. And
`wgst` is simply absent from a METAR that reports no gust, which most do. What the poller
records for a path that does not resolve is unverified here; if the gust values sit at Unknown
on a calm day, delete those values and keep the requests.

The stations are the collector's fourteen: KABI, KAUS, KDFW, KEFD, KGLS, KHOU, KIAH, KLBX,
KLRD, KLVJ, KMAF, KSAT, KSGR and KTKI, chosen (its comments say) for proximity to wind farms
and the big load centres.

### PowerOutage.us Texas Counties, every thirty minutes: experimental

One request, ten values, **none verified**. The collector called
`https://poweroutage.us/api/web/counties?key=...&countryid=us&statename=Texas` with a key
lifted from the site's own JavaScript. On 2026-09-17 that key returns `401 Unauthorized`, and
the site's API page says programmatic access is a paid subscription. The template keeps the
URL with `${POWEROUTAGE_KEY}` in place of the key, which is the assign-time placeholder form
[api-poller-vendor-templates.md](../polling/api-poller-vendor-templates.md#parameters-in-the-url-are-not-request-variables)
reads off SolarWinds' own templates, and assumes the response shape the collector parsed: a
`WebCountyRecord` array of `CountyName`, `OutageCount` and `CustomerCount`. It reads an
`ArrayCount` of the array (counties reporting), an `ArrayCount` of
`$.['WebCountyRecord'].[?(@.OutageCount>1000)]` (counties with more than a thousand customers
out, warning above 0 and critical above 5), and `OutageCount` for eight named counties by
filter. Confirm the shape with a single `GET` before assigning; a JSON dump of the counties
page is the thing that would move this template out of experimental.

## Importing and assigning

Import each template into the library, then assign it to a node. The node is a formality
for these pollers, since nothing about them is per-device; the polling engine's own node is
the natural home, and it is also the machine that has to reach the internet.

```powershell
$swis = Connect-Swis -Hostname orion.example.com -Trusted

foreach ($file in Get-ChildItem '.\scripts\api-pollers\ercot-*.apipoller.template',
                                '.\scripts\api-pollers\metar-texas-airports.apipoller.template') {
    $xml = Get-Content -Raw $file.FullName
    $templateId = Invoke-SwisVerb $swis 'Orion.APIPoller.Templates' 'ImportTemplate' @($xml)
    Write-Host "$($file.Name) -> template $($templateId.InnerText)"
}
```

Then `AssignTemplate` with the node, an empty `configuration` and an empty `parameters` array,
since no credential, proxy or SSL setting is needed:

```powershell
$nodeId = Get-SwisData $swis "SELECT TOP 1 n.NodeID FROM Orion.Nodes n WHERE n.Caption = @c" @{ c = 'orion-primary' }

Invoke-SwisVerb $swis 'Orion.APIPoller.ApiPoller' 'AssignTemplate' @(
    'Orion.Nodes', $nodeId, $templateId, @(), @()
)
```

The poweroutage template needs `${POWEROUTAGE_KEY}` supplied at that step, and which of
`configuration` and `parameters` carries an assign-time placeholder is
[not documented](../polling/api-pollers.md#the-verbs). The console's assign dialog fills it in
for you; over the API, try `parameters` first and read the resulting `Url` back from
`Orion.APIPoller.RequestDetails`.

Both signatures are in the contract. Check them before writing a call, since the arguments are
positional:

```bash
python3 tools/schema_query.py verb Orion.APIPoller.Templates ImportTemplate
python3 tools/schema_query.py verb Orion.APIPoller.ApiPoller AssignTemplate
```

**Keep the poller names.** The dashboard's queries find each poller by the `Name` it was
assigned under (`ERCOT Grid Conditions`, `ERCOT Ancillary Services`, `ERCOT Settlement Point
Prices`, `Texas Airport Weather (METAR)`, `PowerOutage.us Texas Counties (experimental)`),
and the KPI tiles find values by `DisplayName`. Rename either and the widget goes blank
without an error, the same silent failure a renamed dashboard causes in
[the self-referencing link pattern](../webui/modern-dashboard-authoring.md#the-self-referencing-link-pattern).

After the first poll, two queries settle whether the paths worked. Confirm the library has
the request and metric counts the files declare (3 and 11, 1 and 14, 1 and 15, 14 and 70,
1 and 10):

```sql
SELECT
    t.DisplayName,
    t.RequestsCount,
    t.MetricsCount
FROM Orion.APIPoller.Templates t
WHERE t.DisplayName LIKE 'ERCOT%'
   OR t.DisplayName LIKE 'Texas Airport%'
   OR t.DisplayName LIKE 'PowerOutage%'
ORDER BY t.DisplayName
```

Then list every value that has never produced a number. A path the platform's JSONPath did
not accept lands here, and so does a `wgst` key absent from a calm-day METAR:

```sql
SELECT
    v.ApiPoller.Name AS [Poller],
    v.DisplayName,
    v.Path,
    v.StatusDescription
FROM Orion.APIPoller.ValueToMonitor v
WHERE v.ApiPoller.Name LIKE 'ERCOT%'
  AND v.Metric IS NULL
ORDER BY v.ApiPoller.Name, v.DisplayName
```

If the `[-1:]` rows on the grid poller are the ones listed, import
`ercot-system-conditions-html.apmtemplate` through SAM's `ImportTemplate`, assign it to the
same node, and test it with `StartTestComponents` as
[sam-templates.md](../modules/sam-templates.md#test-before-you-assign) describes.

## The dashboard, row by row

[ercot-texas-power-grid.json](../../scripts/dashboards/ercot-texas-power-grid.json) imports
from **My Dashboards > Manage Dashboards > Import**, and passes `tools/check_dashboards.py`.
The Datadog page's groups map onto its rows as follows. Every table query below returns the
`_URL` and `_Status` columns an `EntityLinkFormatterComponent` needs, per
[modern-dashboard-authoring.md](../webui/modern-dashboard-authoring.md#columns-exist-to-feed-formatters),
so the metric name in each table is a link into the value's own page with its status icon.

### Row 1: Big Honkin' Numbers (`kpi` widget, six tiles)

One single-row query per tile. The Datadog row is Generation Capacity, Grid Frequency, Unused
System Capacity, DC ties, Highest Settlement Point Price and Outages; the sixth tile here is
EEA Level, since outages are unverified and have a section of their own.

**Generation Capacity**, and the same shape for Grid Frequency and EEA Level with the
`DisplayName` changed:

```sql
SELECT TOP 1 v.Metric AS [Value]
FROM Orion.APIPoller.ValueToMonitor v
WHERE v.ApiPoller.Name = 'ERCOT Grid Conditions'
  AND v.DisplayName = 'Total System Capacity (MW)'
```

**Unused Capacity**, capacity minus demand. The poller cannot subtract; the query can, by
joining two values on the same poller:

```sql
SELECT TOP 1 c.Metric - d.Metric AS [Value]
FROM Orion.APIPoller.ValueToMonitor c
JOIN Orion.APIPoller.ValueToMonitor d ON d.ApiPollerId = c.ApiPollerId
WHERE c.ApiPoller.Name = 'ERCOT Grid Conditions'
  AND c.DisplayName = 'Total System Capacity (MW)'
  AND d.DisplayName = 'Actual System Demand (MW)'
```

**DC Tie Net Flow**, the sum of the four ties, positive when ERCOT is exporting:

```sql
SELECT SUM(v.Metric) AS [Value]
FROM Orion.APIPoller.ValueToMonitor v
WHERE v.ApiPoller.Name = 'ERCOT Grid Conditions'
  AND v.DisplayName LIKE 'DC Tie Flow%'
```

**Highest Settlement Point Price** across every hub and zone in the latest interval:

```sql
SELECT MAX(v.Metric) AS [Value]
FROM Orion.APIPoller.ValueToMonitor v
WHERE v.ApiPoller.Name = 'ERCOT Settlement Point Prices'
```

### Row 2: Real-Time Grid Conditions (`table`) and DC Tie Flows (`proportional`, horizontal bar)

The table is every value on the grid poller with its status and the poll time. The same query
with the poller name changed drives the Ancillary Services, Settlement Point Prices and
Outages tables:

```sql
SELECT
    v.DisplayName AS [Metric],
    v.DetailsUrl AS [Metric_URL],
    v.Status AS [Metric_Status],
    v.Metric AS [Reading],
    v.StatusDescription AS [State],
    v.ApiPoller.LastPollTimestamp AS [Last Poll]
FROM Orion.APIPoller.ValueToMonitor v
WHERE v.ApiPoller.Name = 'ERCOT Grid Conditions'
ORDER BY v.DisplayName
```

The bar chart is the Datadog "Energy Flow with other grids" panel: one row per tie, coloured
blue when importing and amber when exporting, `Replace()` trimming the label down to the tie
name. `Color` and `Link` are the `colorMappingField` and `linkMappingField` of the
[proportional widget](../webui/modern-dashboards.md#proportional-donut-configuration), and
`chartOptions.type` is `HorizontalBarChart`:

```sql
SELECT
    Replace(Replace(v.DisplayName, 'DC Tie Flow ', ''), ' (MW)', '') AS [Tie],
    v.Metric AS [MW],
    CASE WHEN v.Metric < 0 THEN '#2e7dd1' ELSE '#e0a82e' END AS [Color],
    v.DetailsUrl AS [Link]
FROM Orion.APIPoller.ValueToMonitor v
WHERE v.ApiPoller.Name = 'ERCOT Grid Conditions'
  AND v.DisplayName LIKE 'DC Tie Flow%'
ORDER BY v.DisplayName
```

### Row 3: Ancillary Services (`table`) and two history tables

The Datadog "Grid Frequency" and "Capacity & Demand" line charts become windowed reads of
`Orion.APIPoller.ValueToMonitor.Metrics`, newest first. Frequency is aggregated by local clock
hour. UTC observations are compared against UTC bounds, with date arithmetic performed in
local time before `ToUtc()`, per [date-and-time.md](../swql/date-and-time.md). The one-minute
poller does not justify a `TOP 288` limit: that could truncate a day of detailed readings.
The rolling day can cover 25 clock hours because its first and last hours are partial:

```sql
SELECT
    DateTrunc('hour', ToLocal(m.ObservationTimestamp)) AS [Observed],
    ROUND(MIN(m.MinMetric), 3) AS [Min Hz],
    ROUND(AVG(m.AvgMetric), 3) AS [Avg Hz],
    ROUND(MAX(m.MaxMetric), 3) AS [Max Hz]
FROM Orion.APIPoller.ValueToMonitor.Metrics m
WHERE m.ValueToMonitor.ApiPoller.Name = 'ERCOT Grid Conditions'
  AND m.ValueToMonitor.DisplayName = 'Grid Frequency (Hz)'
  AND m.ObservationTimestamp > ToUtc(AddHour(-24, GetDate()))
  AND m.ObservationTimestamp <= GetUTCDate()
GROUP BY DateTrunc('hour', ToLocal(m.ObservationTimestamp))
ORDER BY DateTrunc('hour', ToLocal(m.ObservationTimestamp)) DESC
```

Capacity and demand side by side, joined on the observation timestamp, with the unused margin
labelled here as unused capacity. This subtraction does not establish an ERCOT operating-reserve measurement:

```sql
SELECT
    ToLocal(d.ObservationTimestamp) AS [Observed],
    d.AvgMetric AS [Demand MW],
    c.AvgMetric AS [Capacity MW],
    c.AvgMetric - d.AvgMetric AS [Unused MW]
FROM Orion.APIPoller.ValueToMonitor.Metrics d
JOIN Orion.APIPoller.ValueToMonitor.Metrics c
    ON c.ObservationTimestamp = d.ObservationTimestamp
WHERE d.ValueToMonitor.ApiPoller.Name = 'ERCOT Grid Conditions'
  AND d.ValueToMonitor.DisplayName = 'Actual System Demand (MW)'
  AND c.ValueToMonitor.DisplayName = 'Total System Capacity (MW)'
  AND c.ValueToMonitor.ApiPollerId = d.ValueToMonitor.ApiPollerId
  AND d.ObservationTimestamp > ToUtc(AddHour(-24, GetDate()))
  AND d.ObservationTimestamp <= GetUTCDate()
ORDER BY d.ObservationTimestamp DESC
```

Whether two values on one poller are observed with the identical timestamp, so that the join
matches, is unverified here. If it returns nothing, the two-table form of the frequency query
run twice is the fallback.

### Row 4: Settlement Point Prices (`proportional` bar, `table`, and a six-hour history)

The Datadog "Latest Settlement Point Prices (Top)" toplist is a horizontal bar chart ordered
by price, green under $200, amber to $1,000, red above:

```sql
SELECT
    Replace(v.DisplayName, ' ($/MWh)', '') AS [Settlement Point],
    v.Metric AS [Price],
    CASE
        WHEN v.Metric >= 1000 THEN '#d13b3b'
        WHEN v.Metric >= 200 THEN '#e0a82e'
        ELSE '#3c9a5f'
    END AS [Color],
    v.DetailsUrl AS [Link]
FROM Orion.APIPoller.ValueToMonitor v
WHERE v.ApiPoller.Name = 'ERCOT Settlement Point Prices'
ORDER BY v.Metric DESC
```

The history table keeps four hubs over the last six hours without an arbitrary row cap.
It retains interval rows; the summary example below instead returns one row per hub:

```sql
SELECT
    ToLocal(m.ObservationTimestamp) AS [Observed],
    m.ValueToMonitor.DisplayName AS [Settlement Point],
    m.AvgMetric AS [$/MWh]
FROM Orion.APIPoller.ValueToMonitor.Metrics m
WHERE m.ValueToMonitor.ApiPoller.Name = 'ERCOT Settlement Point Prices'
  AND m.ValueToMonitor.DisplayName IN ('HB_HUBAVG ($/MWh)', 'HB_HOUSTON ($/MWh)', 'HB_NORTH ($/MWh)', 'HB_WEST ($/MWh)')
  AND m.ObservationTimestamp > ToUtc(AddHour(-6, GetDate()))
  AND m.ObservationTimestamp <= GetUTCDate()
ORDER BY m.ObservationTimestamp DESC, m.ValueToMonitor.DisplayName
```

### Row 5: Nearby Weather (`table`) and Temperature by Airport (`proportional` bar)

The poller stores seventy values named `<ICAO> <metric>`. One row per station is a pivot: the
temperature rows are the base set, and the other four metrics are self-joined by rebuilding
their `DisplayName` from the station's four-letter prefix with `SubString()`. Knots become MPH,
hectopascals become inches of mercury and Celsius gains a Fahrenheit column, so the table
shows the units the Datadog page did. `LEFT JOIN` rather than `JOIN` so a station with no gust
still appears:

```sql
SELECT
    SubString(t.DisplayName, 1, 4) AS [Station],
    t.DetailsUrl AS [Station_URL],
    t.Metric AS [Temp C],
    Round(t.Metric * 1.8 + 32, 1) AS [Temp F],
    d.Metric AS [Dewpoint C],
    Round(w.Metric * 1.15078, 1) AS [Wind MPH],
    Round(g.Metric * 1.15078, 1) AS [Gust MPH],
    Round(p.Metric / 33.8639, 2) AS [Pressure inHg],
    MinuteDiff(t.ApiPoller.LastPollTimestamp, GetDate()) AS [Age Min]
FROM Orion.APIPoller.ValueToMonitor t
LEFT JOIN Orion.APIPoller.ValueToMonitor d ON d.ApiPollerId = t.ApiPollerId AND d.DisplayName = SubString(t.DisplayName, 1, 4) + ' Dewpoint (C)'
LEFT JOIN Orion.APIPoller.ValueToMonitor w ON w.ApiPollerId = t.ApiPollerId AND w.DisplayName = SubString(t.DisplayName, 1, 4) + ' Wind Speed (kt)'
LEFT JOIN Orion.APIPoller.ValueToMonitor g ON g.ApiPollerId = t.ApiPollerId AND g.DisplayName = SubString(t.DisplayName, 1, 4) + ' Wind Gust (kt)'
LEFT JOIN Orion.APIPoller.ValueToMonitor p ON p.ApiPollerId = t.ApiPollerId AND p.DisplayName = SubString(t.DisplayName, 1, 4) + ' Altimeter (hPa)'
WHERE t.ApiPoller.Name = 'Texas Airport Weather (METAR)'
  AND t.DisplayName LIKE '% Temperature (C)'
ORDER BY t.DisplayName
```

The bar chart is temperature per station, warmest first, red at or above 35 C and blue at or
below freezing, which is the reading the February 2021 dashboard was built to watch.

### Row 6: Outage Reports (`kpi`, one tile) and Outages by County (`table`)

Both read the experimental poller and stay blank until it is assigned with a working key. The
tile counts counties with more than a thousand customers out.

### Row 7: Metrics Scrapers (`table`)

The Datadog page's last panel is its collector's duty cycle. The equivalent here is the
pollers themselves, and the number to watch is minutes since the last poll, because an API
poller whose endpoint has moved stops quietly:

```sql
SELECT
    p.Name AS [Poller],
    p.DetailsUrl AS [Poller_URL],
    p.Status AS [Poller_Status],
    p.StatusDescription AS [State],
    p.LastPollTimestamp AS [Last Poll],
    MinuteDiff(p.LastPollTimestamp, GetDate()) AS [Minutes Since Poll],
    p.Node.Caption AS [Assigned To]
FROM Orion.APIPoller.ApiPoller p
WHERE p.Name IN ('ERCOT Grid Conditions', 'ERCOT Ancillary Services', 'ERCOT Settlement Point Prices', 'Texas Airport Weather (METAR)', 'PowerOutage.us Texas Counties (experimental)')
ORDER BY p.Name
```

### What is not on it

The Datadog page has a scatter plot of wind against temperature by station, a heat map of
pressure, and a `diff()` of the time error. None of those is a widget type this repository has
seen in an export, and the time error is a SAM-only value. Wind and PVGR generation, the
"Wind & Solar Generation" chart, are also SAM-only, so they appear in the fallback template's
values and not on the dashboard as shipped.

## Live query lessons from 2026-09-18

These observations came from a contributor running queries through the Web Console on one
installation. The platform version was not captured. They supplement schema checks; they
do not establish behavior across all releases or verify a fresh import of this dashboard.

### UTC bounds and local labels

The diagnostic returned a stored timestamp of `2026-09-18T17:56:00.7214769` and a local
timestamp of `2026-09-18T12:56:00.7214769`. Stored Hour was 17; Local Hour and Grouped Local
Hour were both 12, as was Server Current Hour. The conversion worked. Comparing the UTC
observations against `GetDate()` instead selected older records. Correcting the bounds
restored the current local hour. This evidence concerns `ObservationTimestamp`, not
`LastPollTimestamp` or the separate SAM history timestamp. Verify clocks on other installations.

`ToLocal()` uses the server's local timezone, not the browser's. Do not hard-code a five-hour
offset. The date arithmetic follows SolarWinds' documented
[timezone guidance](https://solarwinds.github.io/OrionSDK/docs/swql-functions/possible-issues/).
A rolling local-day window can span a different elapsed duration at a daylight-saving change.

### Hourly aggregation and widget sorting

At individual polls the stored minimum, average and maximum may be identical. Group by
the hourly timestamp and aggregate across the polls, as the frequency query above does.
`AVG(AvgMetric)` averages the stored averages; unequal sample counts or interval durations
would require weighting for a true raw-sample or time-weighted mean. Missing intervals are
not zero readings. Local clock-hour grouping can merge repeated hours at the autumn clock
change; group by UTC hour when those intervals must remain distinct.

For a compact label, add this expression alongside the full `Observed` timestamp:

```sql
SELECT
    DateTrunc('hour', ToLocal(m.ObservationTimestamp)) AS [Observed],
    Concat(
        CASE WHEN Hour(DateTrunc('hour', ToLocal(m.ObservationTimestamp))) < 10
            THEN '0' ELSE '' END,
        ToString(Hour(DateTrunc('hour', ToLocal(m.ObservationTimestamp)))),
        ':00'
    ) AS [Hour],
    ROUND(MIN(m.MinMetric), 3) AS [Min Hz],
    ROUND(AVG(m.AvgMetric), 3) AS [Avg Hz],
    ROUND(MAX(m.MaxMetric), 3) AS [Max Hz]
FROM Orion.APIPoller.ValueToMonitor.Metrics m
WHERE m.ValueToMonitor.ApiPoller.Name = 'ERCOT Grid Conditions'
  AND m.ValueToMonitor.DisplayName = 'Grid Frequency (Hz)'
  AND m.ObservationTimestamp > ToUtc(AddHour(-24, GetDate()))
  AND m.ObservationTimestamp <= GetUTCDate()
GROUP BY DateTrunc('hour', ToLocal(m.ObservationTimestamp))
ORDER BY DateTrunc('hour', ToLocal(m.ObservationTimestamp)) DESC
```

The contributor confirmed that sorting by **Observed descending**, then hiding that column,
kept the visible Hour labels chronological. Sorting Hour as text placed 10 before 6;
zero-padding fixed that within a day but still put yesterday's 23:00 above today's 13:00.
Remove the Hour sort. The shipped JSON retains its existing Observed column and field
contract; the hidden-column configuration has not been exported and is not guessed here.

### History joins and static validation

The original capacity query failed with navigation-property filters in its `ON` clause.
The contributor reported that removing those filters allowed execution. The revised query
puts them in `WHERE` and also requires the same `ApiPollerId`, avoiding cross-instance
matches. This does not prove that `AND` is generally unsupported in joins. Full execution
of the revised same-poller query remains unverified, and timestamp equality must still be
checked on the target installation. Do not replace missing samples with zeros.

A separate 12-hour label expression passed the static checker but failed on the server with
`mismatched input '-' expecting 'END' in Select clause` when subtraction appeared in a
`CASE` result. The working examples use 24-hour labels. Static schema validation checks
names and references; it does not prove full grammar acceptance, timestamps, widget behavior
or live execution. The exact syntax boundary behind that error remains unverified.

### Current values, units and formatting

Use `ValueToMonitor.Metric` for a current reading and the Metrics history for interval
aggregates. Name filters assume one matching poller; select a specific `ApiPollerId` when
multiple assignments have the same name. `TOP 1` alone does not choose the newest assignment.

Keep the stored name in filters even when converting the output. The contributor confirmed
that filtering on `Total System Capacity (GW)` returned nothing; the stored name is
`Total System Capacity (MW)`. A GW tile can use:

```sql
SELECT TOP 1 ROUND(v.Metric / 1000.0, 2) AS [Value]
FROM Orion.APIPoller.ValueToMonitor v
WHERE v.ApiPoller.Name = 'ERCOT Grid Conditions'
  AND v.DisplayName = 'Total System Capacity (MW)'
```

For unused capacity in GW, divide the parenthesized difference `(c.Metric - d.Metric)` by
`1000.0`. The DC tie values already use MW; removing `(MW)` from a label does not rescale them.
Keep chart values numeric and set their units in the widget.

`ROUND(value, 2)` limits precision but does not force trailing zeros. Screenshots showed
`60` and `60.01` despite rounding to three places. Fixed decimal display belongs in a
supported widget formatter; its exact settings and serialized configuration remain
unverified here. `Concat('$', ToString(ROUND(v.Metric, 2)), '')` or a ` Hz` suffix yields text,
which can sort lexically and cannot replace a numeric chart value. It still does not force
two trailing decimal places. Preserve numeric values when sorting, thresholds or charts need them.

### Six-hour settlement summary

This additional example returns minimum, average and high per hub, rather than one row per
observation. It is schema-checked, not confirmed by a live result in the contributor's report.
The shipped dashboard keeps its existing interval-history layout.

```sql
SELECT
    m.ValueToMonitor.DisplayName AS [Settlement Point],
    MIN(m.MinMetric) AS [Minimum $/MWh],
    AVG(m.AvgMetric) AS [Average $/MWh],
    MAX(m.MaxMetric) AS [High $/MWh]
FROM Orion.APIPoller.ValueToMonitor.Metrics m
WHERE m.ValueToMonitor.ApiPoller.Name = 'ERCOT Settlement Point Prices'
  AND m.ValueToMonitor.DisplayName IN (
      'HB_HUBAVG ($/MWh)',
      'HB_HOUSTON ($/MWh)',
      'HB_NORTH ($/MWh)',
      'HB_WEST ($/MWh)'
  )
  AND m.ObservationTimestamp > ToUtc(AddHour(-6, GetDate()))
  AND m.ObservationTimestamp <= GetUTCDate()
GROUP BY m.ValueToMonitor.DisplayName
ORDER BY m.ValueToMonitor.DisplayName
```

An EEA text label also needs Grid Condition State: EEA 0 alone cannot distinguish normal
operation from conservation. The template maps `normal` to 0 and every other state string
to 5, so that fallback cannot distinguish a known conservation state from an unrecognized
one. The proposed text mapping was not confirmed live and is not shipped as an authoritative
emergency-status interpretation.

## Making it yours

Regenerate every GUID before building on the file, as
[scripts/dashboards/README.md](../../scripts/dashboards/README.md#using-it-as-a-starting-point)
shows, and the template `Guid`s likewise if you fork a poller template. To add a value, add a
`ValueToMonitor` to the right request, then a row to the relevant table appears on its own,
since the table queries select by poller rather than by name; a new KPI tile is a new
single-row query in three places, per
[modern-dashboard-authoring.md](../webui/modern-dashboard-authoring.md#the-five-rules-that-decide-whether-a-file-works).

To chart rather than tabulate, build a PerfStack project over the `ValueToMonitor` metrics
you want, save it, and place a `timeseries` widget pointing at it, as
[modern-dashboards.md](../webui/modern-dashboards.md#a-fourth-type-timeseries) describes from
SolarWinds' own walkthrough. An export of a dashboard containing one would let this page ship
the chart too.

## What is verified and what is not

**Verified on 2026-09-17:**

- Every ERCOT endpoint the templates name answers `200` with `application/json` to a plain
  `curl` with no user agent, cookie or referrer, and the paths for `current_condition`, every
  ancillary group position, `rtSppData` keys, and `dc-tie-flows` and `supply-demand` row keys
  were read off those responses.
- The Aviation Weather Center API returns all fourteen stations with `temp`, `dewp`, `wspd`,
  `altim` on every record and `wgst` on three of them.
- `as_capacity_monitor.html`, `conservation_state.js` and the decoded METAR page return `404`
  or nothing; `real_time_spp` redirects to `real_time_spp.html`; the poweroutage.us key returns
  `401`.
- The five `.apipoller.template` files pass `tools/check_api_poller_templates.py`, the dashboard
  passes `tools/check_dashboards.py`, and every query on this page and in the two files is
  validated against the 2026.2 schema.
- The SAM template's two `PowerShell` components match the real 2026.4 export documented in
  [sam-udp-port-exhaustion-template.md](../modules/sam-udp-port-exhaustion-template.md) in every
  setting key, its order and type, the `DynamicEvidenceColumnSchema` structure and the
  trailer, by a structural diff that ignores only ids, names and values; and the script
  returned every row of the live page in both modes on Windows PowerShell 5.1.

**Not verified, in the order it matters:**

- That the platform's JSONPath accepts `[-1:]` and `[?(@.forecast==0)]` against a response
  body. This decides whether eight of the eleven grid values and all fifteen prices work as
  API Poller values. The `Metric IS NULL` query above answers it after one poll.
- Import and assignment of any of the six template files, and import of the dashboard.
- What a `ValueToMonitor` records when its path does not resolve (`wgst` on a calm day).
- The poweroutage.us response shape and everything in that template.
- That two values on one poller share an `ObservationTimestamp`, which the capacity and demand
  history join relies on.
- Whether ERCOT's dashboard endpoints are a stable interface. They are what ERCOT's own pages
  fetch, not a documented API; the HTML pages the 2021 collector read lasted five years, and
  two of them are gone.

## See also

- [../polling/api-pollers.md](../polling/api-pollers.md) for the entity model, the six verbs and the template format
- [../polling/api-poller-vendor-templates.md](../polling/api-poller-vendor-templates.md) for the `Path` and `ArrayCount` value types and the assign-time placeholders
- [../polling/api-poller-unifi-network.md](../polling/api-poller-unifi-network.md) for a poller verified end to end, and the limits of chaining
- [../modules/sam-udp-port-exhaustion-template.md](../modules/sam-udp-port-exhaustion-template.md) for the export the fallback template is shaped against
- [../webui/modern-dashboard-authoring.md](../webui/modern-dashboard-authoring.md) and [../webui/modern-dashboards.md](../webui/modern-dashboards.md) for the dashboard file
- [soc2-dashboard-10k-nodes.md](soc2-dashboard-10k-nodes.md) and [layer2-switching-dashboard.md](layer2-switching-dashboard.md) for the other two dashboard guides
- [../swql/date-and-time.md](../swql/date-and-time.md) for the local-time windowing the history queries use

# PerfStack (Performance Analysis)

PerfStack — the Performance Analysis dashboard — puts metrics from different objects on a
shared time axis so you can see whether the interface saturating and the application slowing
happened together. In the console it is a drag-and-drop tool.

The part worth documenting is that **its entire state lives in the URL**. Charts, metrics,
objects and time range are all query-string parameters, so a PerfStack view can be *generated*
— from an alert action, from a report column, from a script — pointing at whichever object is
actually in trouble. That is the feature this page is about, and SolarWinds has never
documented it outside community threads.

## The URL grammar

```text
/ui/perfstack/?presetTime=last12Hours&charts=0_Orion.Nodes_1234-Orion.CPULoad.AvgLoad;
```

The `charts` parameter is a list of metric selections. One selection looks like this:

```text
0_Orion.Nodes_1234-Orion.CPULoad.AvgLoad
│ │           │    └── metric: a statistics entity and one of its properties
│ │           └─────── the object's own id
│ └─────────────────── the entity the object belongs to
└───────────────────── chart index
```

Two separators do the grouping, and the distinction between them is the thing nobody writes
down:

| Separator | Effect |
| --- | --- |
| `,` | Keeps metrics **in the same chart** |
| `;` | **Ends a chart** and starts the next |

So this is three separate charts:

```text
charts=0_Orion.Nodes_1234-Orion.CPULoad.AvgLoad;0_Orion.Nodes_1234-Orion.CPULoad.MinLoad;0_Orion.Nodes_1234-Orion.CPULoad.MaxLoad;
```

and this is one chart with three lines on it:

```text
charts=0_Orion.Nodes_1234-Orion.CPULoad.AvgLoad,0_Orion.Nodes_1234-Orion.CPULoad.MinLoad,0_Orion.Nodes_1234-Orion.CPULoad.MaxLoad;
```

That is the difference between "three graphs I have to compare by eye" and "one graph with a
band on it", and it is one character.

**The relationship between the leading index and the semicolon is not settled** by the
community material this repository has seen: the sources describe both the `0_`/`1_` prefix
and the semicolon as determining which chart a metric lands in, and those cannot both be the
whole story. This is **unverified here**. The way to settle it is in the next section, and it
takes about a minute.

### Everything above is community-sourced

The grammar is reported from THWACK threads and from third-party write-ups, not from
SolarWinds' product documentation, and **this repository cannot verify any of it**. The
console URLs, the parameter names and the separators are product behaviour, not schema, and
nothing in `data/` describes them.

`presetTime` is attested with `last12Hours` and `last7Days`. **The complete list of accepted
values is not published anywhere this repository could reach**, and whether explicit start and
end timestamps are supported is likewise unverified.

## Settle the grammar against your own server

You do not have to trust any of the above. PerfStack saves projects, and a saved project is a
row you can read:

```bash
python3 tools/schema_query.py show Orion.PerfStack.Projects
```

```sql
SELECT
    p.ProjectID,
    p.AccountID,
    p.ChartCount,
    p.MetricCount,
    p.MetricTypes,
    p.UpdateDateTime
FROM Orion.PerfStack.Projects p
ORDER BY p.UpdateDateTime DESC
```

`Data` is the project itself, serialised:

```sql
SELECT TOP 5
    p.ProjectID,
    p.ChartCount,
    p.MetricCount,
    p.Data
FROM Orion.PerfStack.Projects p
ORDER BY p.UpdateDateTime DESC
```

**Build the view you want in the console, save it, then read `Data` and the browser's address
bar.** Between them they are the authoritative grammar for the version you are running, and
they answer the chart-index question above directly. `ChartCount` and `MetricCount` are
denormalised on the row, so you can confirm your reading of a `Data` blob against the numbers
the platform itself derived from it.

What `Data` contains is **not recorded in the schema** and is unverified here — it is a
`System.String` and the column summary says nothing.

Note the access control. `Orion.PerfStack.Projects` grants `read` to `everyone` and every
other operation to **`admin`**, so a saved project is readable by anyone who can query and
writable only by an administrator.

## Which metrics are valid for an object

This is the half the schema *can* answer, and it is the half that changes with your modules.

The metric segment is `<StatisticsEntity>.<Property>`, and **236 entities in 2026.2 inherit
`System.StatisticsEntity`** — those are the chartable ones. Which of them apply to a given
object is a navigation question:

```bash
python3 tools/schema_query.py show Orion.Nodes
```

`Orion.Nodes` navigates to 20 statistics entities, `Orion.NPM.Interfaces` to 24, and
`Orion.Volumes` to 2. Each navigation is a family of candidate metrics:

| From `Orion.Nodes` | Reaches | Gives metrics like |
| --- | --- | --- |
| `CPULoadHistory` | `Orion.CPULoad` | `Orion.CPULoad.AvgLoad`, `MinLoad`, `MaxLoad` |
| `CPUMultiLoadHistory` | `Orion.CPUMultiLoad` | Per-CPU load |
| `ResponseTimeHistory` | `Orion.ResponseTime` | `Orion.ResponseTime.AvgResponseTime`, `PercentLoss` |
| `CiscoBuffersHistory` | `Orion.CiscoBuffers` | Buffer miss counters |
| `Flows` | `Orion.Netflow.Flows` | NetFlow volumes, when NTA is installed |

And the properties of any one of them are the metric names:

```bash
python3 tools/schema_query.py props Orion.CPULoad
```

`AvgLoad`, `MinLoad` and `MaxLoad` are all declared members of `Orion.CPULoad`, which is what
makes `Orion.CPULoad.AvgLoad` a well-formed metric segment. Every metric in the community
examples this page quotes resolves that way, checked against the extracted schema.

**Only the numeric ones are chartable.** The main PerfStack view is a time-series chart
surface and nothing else: every metric you add is drawn as a numeric series against the shared
timeline, which is the entire point of the tool — putting unrelated KPIs on one time axis so a
human can see which moved first.

So a statistics entity's `ObservationTimestamp` is the x-axis rather than a series, and an id
column is not a metric at all. Neither is addressable as a metric segment. When you enumerate
`props` on a statistics entity to find metric names, **the numeric properties are the
candidate list**; the timestamp and the ids are structural.

*Source: reported from practice by a long-time SolarWinds administrator.*

### Non-numeric data lives in the Data Explorer tab

The PerfStack page carries a second tab, **Data Explorer**, and that is where anything that is
not a time series goes. It lists entries — alerts, syslog messages and similar event data — as
a **table** rather than a chart, on the same page and against the same time range.

That is the answer to "how do I get alerts onto my PerfStack view": you do not chart them, you
read them in Data Explorer alongside the charts. Correlating a spike with the alert that fired
at the same moment is the workflow, and both halves share the timeline.

Whether the Data Explorer tab can be pre-loaded from the URL the way the chart surface can —
and if so, with what segment grammar — is **not documented and unverified here**. Everything in
[the URL grammar](#the-url-grammar) above concerns the chart surface. If you have found a URL
form that opens Data Explorer with a selection already made, that is exactly the gap this page
would most like closed.

## Generating a link from an alert

This is the use case the feature exists for: an alert fires, and the notification carries a
link to a PerfStack view already loaded with the right object.

Alert variables supply the id. `${N=SwisEntity;M=NodeID}` on a node alert is the node's
`NodeID`, which is exactly the id segment the URL wants:

```text
https://orion.example.com/ui/perfstack/?presetTime=last12Hours&charts=0_Orion.Nodes_${N=SwisEntity;M=NodeID}-Orion.CPULoad.AvgLoad,0_Orion.Nodes_${N=SwisEntity;M=NodeID}-Orion.ResponseTime.AvgResponseTime;
```

That is one chart with CPU and response time on the same axis for the node that triggered,
which is usually the first question anyone asks.

Two things to get right. **The variable must match the alert's trigger entity** — on an
interface alert `${N=SwisEntity;M=InterfaceID}` is the id and `Orion.NPM.Interfaces` is the
entity segment, and a node-shaped URL will not resolve. See
[variables.md](variables.md#the-member-list-is-the-property-list).

And **the whole thing is a URL in an email**, so whatever renders it may mangle a long
unbroken string. Test the actual notification rather than the variable.

## Generating a link from a report

A Custom Query widget can carry a PerfStack link per row, using the `_LinkFor_` convention
from [custom-query-widget.md](custom-query-widget.md). The URL is built by string
concatenation, with `ToString()` around the id because SWQL will not concatenate an integer to
a string:

```sql
SELECT
    n.Caption AS [Node],
    n.CPULoad AS [CPU],
    '/ui/perfstack/?presetTime=last12Hours&charts=0_Orion.Nodes_' + ToString(n.NodeID)
        + '-Orion.CPULoad.AvgLoad;' AS [_LinkFor_CPU]
FROM Orion.Nodes n
WHERE n.CPULoad > 80
ORDER BY n.CPULoad DESC
```

Every row is a node over 80% CPU, and clicking its CPU figure opens the history for that node.
The link column is consumed by the widget rather than displayed — that is the whole point of
the naming convention.

The same shape works for interfaces, with the entity and id segments changed:

```sql
SELECT
    i.Caption AS [Interface],
    i.InPercentUtil AS [Utilisation],
    '/ui/perfstack/?presetTime=last12Hours&charts=0_Orion.NPM.Interfaces_' + ToString(i.InterfaceID)
        + '-Orion.NPM.InterfaceTraffic.InAveragebps,0_Orion.NPM.Interfaces_' + ToString(i.InterfaceID)
        + '-Orion.NPM.InterfaceTraffic.OutAveragebps;' AS [_LinkFor_Utilisation]
FROM Orion.NPM.Interfaces i
ORDER BY i.InPercentUtil DESC
```

Comma rather than semicolon between the two metrics, so in and out traffic land on one chart.

**Confirm the metric entity before shipping either of these.** `Orion.NPM.InterfaceTraffic`
and its properties are real in 2026.2 — check yours:

```bash
python3 tools/schema_query.py props Orion.NPM.InterfaceTraffic
```

## Gotchas

**The entity segment and the id segment must agree.** `Orion.Nodes` with an `InterfaceID`
produces a URL that loads and charts nothing, because the id resolves to a different object or
to none.

**A wrong metric name fails quietly.** The chart is empty rather than the page erroring, which
looks identical to a metric that simply has no data for the window.

**`Orion.PerfStack.Projects` needs `admin` to write.** Anyone can read saved projects,
including other people's — `AccountID` is on the row.

**The URL is long, and it grows linearly.** Every metric repeats the entity and id. A view
with four objects and three metrics each is over a thousand characters, which is fine in a
browser and not always fine in whatever is relaying your alert.

**Nothing here is in the schema.** The grammar can change in a release without anything in
`data/` moving, so a generated link is a thing to re-test after an upgrade. `Data` on a saved
project is the canary: if the grammar changed, the shape of that column changed with it.

## Sources, and what is missing

SolarWinds documents PerfStack as a console feature and does not publish the URL grammar. What
this page reports comes from:

- [Perfstack URL questions](https://thwack.solarwinds.com/product-forums/server-application-monitor-sam/f/forum/64340/perfstack-url-questions) on THWACK
- [Creating dynamic Performance Analysis for Node and Interface Details Views](https://thwack.solarwinds.com/products/network-performance-monitor-npm/f/forum/102255/creating-dynamic-performance-analysis-for-node-and-interface-details-views)
- [Building Simple PerfStack Templates With SWQL](https://thwack.solarwinds.com/products/network-performance-monitor-npm/f/forum/39939/building-simple-perfstack-templates-with-swql)
- [Multiple Data Sources on one graph (PerfStack)](https://thwack.solarwinds.com/product-forums/the-orion-platform/f/forum/90007/multiple-data-sources-on-one-graph-perfstack), which is where the comma-versus-semicolon rule comes from
- [How to Automate Link to PerfStack in a SolarWinds Alert](https://prosperon.co.uk/insights/how-to-automate-link-to-perfstack-in-a-solarwinds-alert/), a third-party write-up of the alert-action case

Two points on this page — that the chart surface is numeric-only, and that the Data Explorer
tab carries alerts and syslog as a table — come from a long-time SolarWinds administrator
reporting from practice rather than from any of the sources above.

Still missing, and named so the gap is explicit: the complete `presetTime` value list, whether
explicit start and end timestamps are accepted, the exact role of the chart index against the
semicolon, the structure of `Orion.PerfStack.Projects.Data`, whether any parameter controls
chart type or axis scaling, and whether the Data Explorer tab can be addressed from the URL.
`PRINTABLE=TRUE` is reported as removing the console chrome and is unverified here.

## See also

- [variables.md](variables.md) — the alert variables that supply the id segment
- [custom-query-widget.md](custom-query-widget.md) — `_LinkFor_`, which turns a generated URL
  into a clickable column
- [README.md](README.md) — the rest of this section, and why the schema cannot verify console
  behaviour
- [../swql/functions.md](../swql/functions.md) — `ToString()` and string concatenation
- [../modules/npm.md](../modules/npm.md) — the interface statistics entities

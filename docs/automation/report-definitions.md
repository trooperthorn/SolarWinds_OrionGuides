# The report definition format

A report exports from **Reports > Manage Reports > Export/Import** as one XML document, and the
same document is the value of `Orion.Report.Definition`. So a report is readable with a plain
query and writable with a verb, and the file on disk, the column in the database and the thing
the console edits are one artefact.

**Source.** Derived by parsing four real exports — two SolarWinds-shipped and two hand-built —
against the 2026.2 schema. SolarWinds does not publish the format. Element names are quoted
from those documents; every entity and property they name is checked against the extracted
schema like everything else here.

[reporting.md](reporting.md) covers the entities, the verbs and scheduling. This page is the
document itself.

## The skeleton

Fifteen top-level elements, all present in all four samples:

```xml
<Report xmlns="http://schemas.datacontract.org/2004/07/SolarWinds.Reporting.Models"
        xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
  <Category>SD-WAN Reports</Category>
  <Configs>…</Configs>
  <DataSources>…</DataSources>
  <Description>Displays the status of WAN uplinks on orchestrator devices.</Description>
  <Footer>…</Footer>
  <Header>…</Header>
  <LicenseFeatureName>NPM</LicenseFeatureName>
  <LimitationCategory>Default Folder</LimitationCategory>
  <ModuleTitle>SD-WAN Reports</ModuleTitle>
  <Name>WAN UpLinks</Name>
  <OrionFeatureName i:nil="true"/>
  <PageLayout>…</PageLayout>
  <ReportGuid>c52eadff-…</ReportGuid>
  <Sections>…</Sections>
  <TimeFrames>…</TimeFrames>
</Report>
```

The `datacontract.org` namespaces mark this as WCF `DataContractSerializer` output, so the
document is a serialised object graph. Two consequences follow throughout: **elements appear in
alphabetical order within each type**, and **an unset value is written `i:nil="true"` rather
than omitted**.

| Element | Maps to `Orion.Report` | Notes |
| --- | --- | --- |
| `Name` | `Name` | The report's identity in Manage Reports |
| `Category` | `Category` | The grouping in the report list |
| `Description` | `Description` | |
| `LimitationCategory` | `LimitationCategory` | `Default Folder` in all four |
| `ModuleTitle` | `ModuleTitle` | The module heading; `i:nil` on a core report |
| `LicenseFeatureName` | `LicenseFeatureName` | `NPM`, `HardwareHealth` — gates the report on a licensed module |
| `OrionFeatureName` | `OrionFeatureName` | `i:nil` in all four |
| `ReportGuid` | — | Identity across servers. **Not** `ReportID`, which is local. Reissued on import if it collides — see [Importing a definition that is already there](#importing-a-definition-that-is-already-there) |

`ReportID`, `Owner`, `Type`, `LegacyPath`, `RecipientList` and `LastRenderDuration` are columns
on `Orion.Report` with no element in the file. They are installation state rather than report
content, which is why the document travels between servers.

## The three-part indirection

This is the part to understand first, because everything else hangs off it. A report is not a
tree of widgets — it is **three flat lists joined by GUID**:

```text
  Sections          the layout: rows, columns, cells
      |  ConfigId ──────────────► Configs        what each cell renders
      |  DataSelectionRefId ────► DataSources    where its rows come from
      |  TimeframeRefId ────────► TimeFrames     over what period
```

A `SectionCell` names all three:

```xml
<a:SectionCell>
  <a:ConfigId>2941fe59-9b92-45dc-8b4c-7e895d7018ee</a:ConfigId>
  <a:DataSelectionRefId>fd6eb596-8561-43ab-aad3-a66086389389</a:DataSelectionRefId>
  <a:DisplayName>Custom Table</a:DisplayName>
  <a:RefId>ea365a3a-d920-4f72-bc21-4304f09a3080</a:RefId>
  <a:RenderProvider>SolarWinds.Reporting,Table</a:RenderProvider>
  <a:TimeframeRefId>ffffffff-ffff-ffff-ffff-ffffffffffff</a:TimeframeRefId>
</a:SectionCell>
```

Two sentinel GUIDs carry meaning:

- **`ffffffff-ffff-ffff-ffff-ffffffffffff`** as `TimeframeRefId` means *no timeframe* — a
  current-state report rather than a historical one. All four samples use it, even though each
  still declares a `TimeFrames` entry.
- **`00000000-0000-0000-0000-000000000000`** as `DataSelectionRefId` means *no data source*,
  used by a cell whose content fetches its own data.

**This mirrors the Modern Dashboard format's `unique_key` indirection**, and carries the same
hazard: a `ConfigId` that resolves to nothing is a cell that renders nothing, with no error.
See [../webui/modern-dashboards.md](../webui/modern-dashboards.md).

### Layout

`Sections` is a list of `Section`, each with `Columns` of `SectionColumn`, each with `Cells`.
Width is proportional:

```xml
<a:SectionColumn>
  <a:PercentWidth>50</a:PercentWidth>
  <a:PixelWidth i:nil="true"/>
  …
</a:SectionColumn>
```

A section with two 50% columns is a two-up row. `PageLayout` sets the canvas — `Width` of `960`
or `1200` across the samples, `Height` of `0`, and `PublishingType` of `web`. An empty section
(a `SectionColumn` with `<a:Cells/>`) is legal and appears in one sample; the console leaves
one behind as a spare row.

## `DataSources` — three ways to choose rows

```xml
<a:DataSource>
  <a:CommandText>SELECT …</a:CommandText>
  <a:DynamicSelectionType>Undefined</a:DynamicSelectionType>
  <a:EntityUri/>
  <a:Filter i:nil="true"/>
  <a:MasterEntity>Orion.Nodes</a:MasterEntity>
  <a:Name>SD-WAN Datasource</a:Name>
  <a:NetObjectId/>
  <a:RefId>fd6eb596-…</a:RefId>
  <a:Type>CustomSWQL</a:Type>
</a:DataSource>
```

`Type` decides which of the other elements matter:

| `Type` | Means | Carries |
| --- | --- | --- |
| `Dynamic` | Every object of an entity, optionally filtered | `MasterEntity`, `DynamicSelectionType` of `Simple` |
| `Entities` | An explicit list of objects | `EntityUri`, a list of `swis://` URIs |
| `CustomSWQL` | A query you wrote | `CommandText` |

**`CustomSWQL` is the interesting one**, because it puts arbitrary SWQL inside the report and is
how the two hand-built samples work. The query is stored as text with XML entity escaping, so a
`<` in the SWQL — including inside an HTML string being built for a column — appears as `&lt;`.

`MasterEntity` is still set on a `CustomSWQL` source (`Orion.Nodes` in both samples). What it
governs when the query is arbitrary is **not documented and unverified here**; the plausible
reading is that it supplies the account-limitation context, which would make it
security-relevant rather than cosmetic. See
[accounts-and-permissions.md](accounts-and-permissions.md).

An `Entities` source names objects by URI:

```xml
<a:EntityUri>
  <b:string>swis://YOUR-SERVER/Orion/Orion.Nodes/NodeID=3</b:string>
</a:EntityUri>
```

**Those URIs contain your server's hostname and local object ids.** A report exported with an
`Entities` data source is bound to the server it came from and leaks its name — see
[Before you share one](#before-you-share-one).

## `Configs` — what a cell renders

`Configs` holds `ConfigurationData` elements, discriminated by `i:type`:

| `i:type` | Renders | `RenderProvider` on the cell |
| --- | --- | --- |
| `TableConfiguration` | A table of rows | `SolarWinds.Reporting,Table` |
| `WebResourceConfiguration` | A classic console resource, embedded | `SolarWinds.Orion.Web.Reporting,WebResource` |

Both appear across the samples; the list is **not necessarily complete**, since chart and gauge
configurations plainly exist in the product and none of the four exercises them.

### `WebResourceConfiguration` is a console resource in a report

This is where reports meet `Orion.Views` and `Orion.Resources`:

```xml
<a:ConfigurationData i:type="b:WebResourceConfiguration">
  <a:DisplayTitle>Percent Availability</a:DisplayTitle>
  <a:RefId>22afaea2-…</a:RefId>
  <b:ParentViewType i:nil="true"/>
  <b:ResourceFile>/Orion/NetPerfMon/Resources/NodeChartsV2/NodeChart.ascx</b:ResourceFile>
  <b:Settings>
    <a:ContextValue><a:Name>ChartName</a:Name><a:Value>Availability</a:Value></a:ContextValue>
    <a:ContextValue><a:Name>ChartTitle</a:Name><a:Value>${Caption}</a:Value></a:ContextValue>
    <a:ContextValue><a:Name>Calculate95thPercentile</a:Name><a:Value>1</a:Value></a:ContextValue>
  </b:Settings>
  <b:Title>Percent Availability</b:Title>
</a:ConfigurationData>
```

`ResourceFile` is an `.ascx` path, and it is **the same value `Orion.Resources.ResourceFile`
holds** for a resource placed on a view. So the catalogue of what you can embed in a report is
discoverable by looking at what is already on your views:

```sql
SELECT DISTINCT r.ResourceFile, r.ResourceName
FROM Orion.Resources r
ORDER BY r.ResourceFile
```

```bash
python3 tools/schema_query.py show Orion.Resources
```

`Orion.Resources` also carries `ResourceID`, `ViewID`, `ViewColumn`, `Position`,
`ResourceName`, `ResourceTitle` and `ResourceSubTitle`, and grants `read` and `invoke` to
`everyone` with the rest to `admin`. `Orion.Views` is the view those resources sit on, with
`ViewKey`, `ViewType`, `Columns` and per-column widths.

**That a `ResourceFile` valid on a view is valid in a report is the obvious reading and is
unverified here.** The three in the samples — `XuiWrapper.ascx`, `NodeChart.ascx` and
`WorldMapView.ascx` — are certainly usable; whether an arbitrary resource works, and which
`Settings` each expects, is not documented anywhere this repository has seen. The practical
route is to place the resource on a view, get it working there, then copy its `ResourceFile`
and settings across.

`Settings` are free-form `Name`/`Value` pairs, and they accept the `${…}` variables the classic
console uses — `${Caption}` and `${ZoomRange}` both appear. Those are the console's own tokens
rather than the alert-variable grammar in [../webui/variables.md](../webui/variables.md),
despite the shared spelling.

One sample embeds a modern widget through a wrapper, which is worth recognising:

```xml
<b:ResourceFile>/Orion/NetPerfMon/Resources/Misc/XuiWrapper.ascx</b:ResourceFile>
<b:Settings>
  <a:ContextValue><a:Name>Selector</a:Name><a:Value>sw-tile-widget</a:Value></a:ContextValue>
  <a:ContextValue><a:Name>FeatureToggle</a:Name><a:Value>SwTileWidget</a:Value></a:ContextValue>
  <a:ContextValue><a:Name>Features</a:Name><a:Value>NPM,EOC</a:Value></a:ContextValue>
</b:Settings>
```

`XuiWrapper.ascx` hosts an Angular component named by `Selector`, gated by `FeatureToggle` and
`Features`. That is how newer widgets reach a classic report surface. The full set of selectors
and toggles is **not documented and unverified here**.

## `TableConfiguration` — columns

Each `TableColumn` binds a field to a display treatment:

```xml
<b:TableColumn>
  <b:CellStyle>…</b:CellStyle>
  <b:DataColumnName i:nil="true"/>
  <b:DisplayName>Hardware Status</b:DisplayName>
  <b:Field>
    <c:DataTypeInfo>…</c:DataTypeInfo>
    <c:DisplayName>Hardware Status</c:DisplayName>
    <c:NavigationPath i:nil="true"/>
    <c:OwnerDisplayName>Overall Hardware Status (Node)</c:OwnerDisplayName>
    <c:RefID><c:Data>Orion.HardwareHealth.HardwareInfo|LastPollStatusName</c:Data></c:RefID>
  </b:Field>
  <b:IsHTMLTagsAllowed>false</b:IsHTMLTagsAllowed>
  <b:IsHidden>false</b:IsHidden>
  <b:PercentWidth>12.909</b:PercentWidth>
  <b:Presenters>…</b:Presenters>
  <b:PropertyName>Overall Hardware Status (Node)/Hardware Status</b:PropertyName>
  <b:RefId>e0c826d1-…</b:RefId>
  <b:Summary><b:Calculation>NotSpecified</b:Calculation></b:Summary>
  <b:TransformId>hardwarehealt.transformer.statusname</b:TransformId>
  <b:ValidRange>NotSpecified</b:ValidRange>
</b:TableColumn>
```

### `RefID/Data` is how a column names its field

This is the single most useful thing in the format. The value is pipe-delimited:

```text
Entity|Property                     Orion.Groups|Name
Entity|Property|NavigationPath      Orion.Nodes|Caption|Node
db|ColumnName|computed              db|OrganizationName|computed
```

- **Two parts** — a property of the data source's own entity.
- **Three parts, third is a navigation** — reached by walking that navigation property.
  `Orion.ContainerMembers|Status|Members` walks `Members` from `Orion.Groups`.
- **`db|…|computed`** — a column produced by a `CustomSWQL` query rather than a schema property.
  The `db` literal means "whatever the query returned", so these cannot be validated against the
  schema and are only as good as the query's aliases.

Checked across the four samples: **all 20 `Entity|Property` references resolve against the
2026.2 schema**, including the navigated ones, and both `CustomSWQL` queries validate with no
errors or warnings. The remaining six references are `db|…|computed` and correspond to aliases
the queries do return.

`PropertyName` is the human-facing path (`Overall Hardware Status (Node)/Hardware Status`) and
`OwnerDisplayName` the group heading the field picker showed. Neither is load-bearing; `RefID`
is.

### `DataTypeInfo` — the field picker's metadata

```xml
<a:ApplicationType>HWH.StatusName</a:ApplicationType>
<a:DataType><a:Data>System.Int32</a:Data></a:DataType>
<a:DeclType>Enumerated</a:DeclType>
<a:IsFilterBy>true</a:IsFilterBy>
<a:IsGroupBy>true</a:IsGroupBy>
<a:IsStatistic>false</a:IsStatistic>
<a:PreviewValue>Critical</a:PreviewValue>
```

`DeclType` takes `Text` and `Enumerated` across the samples. `ApplicationType` names a semantic
type the console understands — `Core.IPAddress`, `Core.VendorType`, `Core.NodeStatus`,
`System.Status`, `HWH.StatusName` — which is what lets the picker offer the right presenter.
The complete set is **not documented and unverified here**.

**`PreviewValue` holds a real value sampled from the server that built the report.** It is
cosmetic, and it is a disclosure risk — see below.

### Presenters and transforms

Two independent mechanisms, easily confused:

- **`TransformId`** changes the *value*. `orion.transformer.status.shortdescription` turns a
  status integer into its short description; `orion.transformer.nodestatus.shortdescription`
  and `hardwarehealt.transformer.statusname` do the same for their own status vocabularies.
  (`hardwarehealt` is spelled that way by SolarWinds. Copy it verbatim.)
- **`Presenters`** changes the *rendering*. A column may carry several:

```xml
<b:Presenters>
  <c:PresenterRef>
    <c:PresenterId>orion.core.link.entity</c:PresenterId>
    <c:Values><a:ContextValue><a:Name>EnabledTooltips</a:Name><a:Value>on</a:Value></a:ContextValue></c:Values>
  </c:PresenterRef>
  <c:PresenterRef>
    <c:PresenterId>orion.core.image.status.watermark</c:PresenterId>
    <c:Values><a:ContextValue><a:Name>imageformat</a:Name><a:Value>/orion/images/statusicons/small-{0}.gif</a:Value></a:ContextValue></c:Values>
  </c:PresenterRef>
</b:Presenters>
```

| `PresenterId` | Renders |
| --- | --- |
| `orion.core.link.entity` | The value as a link to the object's details page |
| `orion.core.image.status.watermark` | A status icon beside the value |
| `orion.core.image.vendor.watermark` | A vendor icon beside the value |

`orion.core.link.entity` is what makes a report column clickable **without writing a URL** — the
report resolves the object itself, which is why it is preferable to concatenating a
`DetailsUrl` by hand. The full presenter list is **not documented and unverified here**.

`imageformat` on the status watermark takes a `{0}` placeholder that the status icon name is
substituted into. `watermarkSource` of `Column` appears on the other samples, selecting the
icon from the column's own value instead.

### `IsHTMLTagsAllowed`, and the pattern it enables

Set `true`, the cell renders its value as HTML. One sample uses it with a `CustomSWQL` query
that builds an `<img>` and an `<a>` per row, which is how you get a linked icon into a column
the presenters do not cover. The SWQL is stored XML-escaped, so `<img` appears as `&lt;img`.

It is a real capability and also an injection surface: the value becomes markup, so a column
carrying anything a user can influence should leave this `false`.

### Sorting, grouping and limits

```xml
<b:Indents>
  <b:TableIndentEntry>
    <b:ColumnId>639e8b69-…</b:ColumnId>
    <b:IncludeSummaryRow>false</b:IncludeSummaryRow>
  </b:TableIndentEntry>
</b:Indents>
<b:Sorts>
  <c:SortEntry><c:Direction>Ascending</c:Direction><c:QFieldRefID>639e8b69-…</c:QFieldRefID></c:SortEntry>
</b:Sorts>
<b:Filter>
  <c:Expression i:nil="true"/>
  <c:Limit><c:Count i:nil="true"/><c:Mode>ShowAll</c:Mode><c:Percentage i:nil="true"/></c:Limit>
</b:Filter>
<b:SummarizeMode>NoDataSummarization</b:SummarizeMode>
```

**`Indents` is grouping.** Each entry names a column the table breaks on, in order, which is how
one sample nests group members under their group and another nests uplinks under vendor,
organisation, network and device. `IncludeSummaryRow` adds a subtotal line.

`Sorts` and `Indents` both reference a **column `RefId`**, not a field. `Limit.Mode` of
`ShowAll` with everything else `i:nil` is "no limit"; `Count` and `Percentage` are the top-N
controls.

## Header, footer, timeframes

```xml
<Header><a:Logo>standard</a:Logo><a:SubTitle/><a:Title>WAN UpLinks</a:Title><a:Visible>true</a:Visible></Header>
<Footer>
  <a:CustomText>© SolarWinds Worldwide, LLC. All Rights Reserved.</a:CustomText>
  <a:ShowCustomText>true</a:ShowCustomText>
  <a:ShowPageNumber>true</a:ShowPageNumber>
  <a:ShowTimestamp>true</a:ShowTimestamp>
  <a:Visible>true</a:Visible>
</Footer>
```

`Footer.CustomText` is free text and is worth setting to something meaningful — a shipped
report's copyright line is a poor label for a report you wrote.

`TimeFrames` declares named periods:

```xml
<a:TimeFrame>
  <a:DisplayName>Past Hour</a:DisplayName>
  <a:IsStatic>false</a:IsStatic>
  <a:RefId>db6e15c8-…</a:RefId>
  <a:Relative><a:NamedTimeFrame>PastHour</a:NamedTimeFrame><a:Unit>Hour</a:Unit><a:UnitCount>1</a:UnitCount></a:Relative>
  <a:Static i:nil="true"/>
</a:TimeFrame>
```

All four samples declare one `PastHour` frame and then reference the
`ffffffff-…` sentinel from every cell, so the declared frame goes unused. The set of valid
`NamedTimeFrame` values, and the shape of `Static` for an absolute range, are **not documented
and unverified here**.

## Moving a report between servers

There is no `ExportReport`/`ImportReport` pair. Reading is a query; writing is a verb.

```powershell
# Read the definition from the source server
$report = Get-SwisData $sourceSwis @'
SELECT TOP 1 r.Name, r.Description, r.Category, r.Title, r.SubTitle,
       r.LimitationCategory, r.Definition
FROM Orion.Report r
WHERE r.Name = @name
'@ @{ name = 'WAN UpLinks' }

# Create it on the target
$newId = Invoke-SwisVerb $targetSwis 'Orion.Report' 'CreateReport' @(
    $report.Name,
    $report.Description,
    $report.LimitationCategory,
    $report.Category,
    $report.Title,
    $report.SubTitle,
    $report.Definition,
    'false',      # isFavorite
    'admin'       # userName
)
```

Both `isFavorite` and `userName` are declared `string`, including the boolean-looking one —
see [../swis/invoke-verbs.md](../swis/invoke-verbs.md) on why a verb's declared types are worth
reading rather than assuming.

`CreateReport` needs `manageReports`. `Orion.Report` declares **no `create` and no `delete`
operation**, so the verbs are the only route and entity-level `invoke` governs them.

### Importing a definition that is already there

**The console duplicates. It never replaces.** Importing a definition whose `ReportGuid`
already exists on the server produces a *second* report: the platform assigns it a **fresh
`ReportGuid`** and prefixes its name with **`Copy of `**. The original is untouched.

*Source: tested by a long-time SolarWinds administrator, importing these same definitions
through **Reports > Manage Reports > Import** on a server that already held them.*

Two things follow, and they matter more than they look:

**Re-import is not an update mechanism.** There is no path by which importing overwrites an
existing report, so a "sync the reports to this server" script built on repeated import does not
converge — it accumulates. Import the same file three times and you have the original, `Copy of
X`, and `Copy of Copy of X`. Use `UpdateReport` against a known `ReportID` to change a report in
place; that is the only way to make the second run of a script idempotent.

**`ReportGuid` is advisory on import, not authoritative.** The value in the file is what the
report *was* on the server that exported it. Once a collision is detected the platform issues a
new one, so you cannot use the GUID in the file to predict what the report will be called on the
target, and you cannot match on it afterwards to find what you just imported. Match on the name
you passed instead, or read back the id `CreateReport` returns.

That the console never replaces is the safe design — a silent overwrite of somebody's edited
report would be far worse than a stray copy — but it does mean cleanup is manual.

**What `CreateReport` does in the same situation is a narrower question, still unverified
here.** The verb is a different entry point from the console's import, and it takes `name`,
`description`, `category`, `title` and `subtitle` as **arguments alongside** the `definition`
document, which contains all five again as elements. Which copy wins, and whether the verb
applies the same `Copy of ` rename, is not documented anywhere this repository has seen. Until
that is settled, treat `CreateReport` as create-only and reach for `UpdateReport` when a report
already exists.

### What breaks on the way across

- **`Entities` data sources.** The `swis://` URIs embed the source server's hostname and its
  local `NodeID`s. On another server those ids belong to different objects, or to none.
- **Custom properties.** A column naming one that the target lacks renders empty. See
  [custom-properties.md](custom-properties.md).
- **Module entities.** A definition naming `Orion.SdWan.NodesInterfaces` needs that module
  installed; `LicenseFeatureName` records the dependency but does not resolve it.
- **`LimitationCategory`** names a folder that has to exist.

## Before you share one

A report definition carries more of your installation than you might expect. All three of these
appear in the samples this page was built from:

- **`EntityUri`** — full `swis://` URIs including the server's fully-qualified hostname.
- **`PreviewValue`** — real values sampled from the source server, sitting in the field
  metadata. Node names and asset tags both appeared.
- **`CommandText`** — your SWQL, including any hard-coded ids, hostnames or thresholds.

None of that is needed for the report to work elsewhere. Read a definition before you publish
it, and prefer a `Dynamic` or `CustomSWQL` source over `Entities` in anything meant to travel.

```bash
python3 -c "import sys,re; d=open(sys.argv[1]).read(); [print(m) for m in re.findall(r'swis://[^<]+', d)]" report.xml
```

## See also

- [reporting.md](reporting.md) — the reporting entities, the verbs, scheduling and export
- [../webui/modern-dashboards.md](../webui/modern-dashboards.md) — the modern equivalent, with
  the same GUID-indirection pattern and a JSON body
- [../polling/api-pollers.md](../polling/api-pollers.md#the-apipollertemplate-file-format) —
  the other exportable XML artefact, which *does* have matched import and export verbs
- [../webui/custom-query-widget.md](../webui/custom-query-widget.md) — the console widget whose
  `_LinkFor_` convention solves the same problem as `orion.core.link.entity`
- [accounts-and-permissions.md](accounts-and-permissions.md) — `manageReports`, and why
  limitations change what a report returns

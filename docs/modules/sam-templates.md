# The `.apmtemplate` file format

A SAM application template exports from **Settings > All Settings > SAM Settings > Manage
Templates > Export** as an XML document with the extension `.apmtemplate`. It is the same
string `Orion.APM.ApplicationTemplate.ExportTemplate` returns and `ImportTemplate` accepts.

**Source.** Derived by parsing three real exports — a SolarWinds-shipped MongoDB template, a
shipped Azure App Service template, and a hand-built one monitoring an Orion polling engine —
against the 2026.2 schema. SolarWinds documents the console workflow but not the document.

[sam.md](sam.md) covers the entities, all thirty-nine SAM verbs, and assigning a template.
This page is the file.

## The root is an array

```xml
<?xml version="1.0" encoding="utf-8"?>
<ArrayOfApplicationTemplate
    xmlns:i="http://www.w3.org/2001/XMLSchema-instance"
    xmlns="http://schemas.solarwinds.com/2007/08/APM">
  <ApplicationTemplate>…</ApplicationTemplate>
</ArrayOfApplicationTemplate>
```

**One file can carry several templates.** All three samples hold exactly one, but the root
element is a collection, so a multi-template export is expressible. Whether `ImportTemplate`
accepts a document with more than one `ApplicationTemplate`, and what it returns if it does —
the verb's return type is a single `number` — is **not documented and unverified here**.

The namespace `http://schemas.solarwinds.com/2007/08/APM` dates the format to 2007, which is
worth knowing: this is one of the oldest serialisation formats still in the product, and it
predates the `datacontract.org` shape used by
[report definitions](../automation/report-definitions.md).

## The template

Sixteen child elements, all present in all three samples:

| Element | Maps to `Orion.APM.ApplicationTemplate` | Notes |
| --- | --- | --- |
| `Id` | `ApplicationTemplateID` | **Local to the source server.** Not meaningful on import |
| `UniqueId` | `UniqueId` | The GUID identity, and what `StartTestComponents` wants |
| `Name` | `Name` | |
| `Description` | — | Not a column on the entity |
| `IsMockTemplate` | `IsMockTemplate` | `false` in all three |
| `Created`, `LastModified` | same | ISO-8601 UTC |
| `CustomApplicationType` | `CustomApplicationType` | Empty in all three |
| `ViewID` | `ViewID` | `0` in all three |
| `ViewXml` | `ViewXml` | The template's custom view; empty or near-empty in all three |
| `Version` | — | `1.0` in all three; not a column |
| `ModuleVersion` | — | Whitespace-only in all three |
| `Tags` | — | Whitespace-only in all three |
| `Settings` | `Orion.APM.ApplicationTemplateSettings` | Template-wide settings |
| `ComponentTemplates` | `Orion.APM.ComponentTemplate` | The monitors |
| `DeletedComponentTemplates` | — | Empty in all three |

`HasImportedView` is a column on the entity with no element in the file.

**`Id` versus `UniqueId` is the distinction to hold onto.** `Id` is the source server's integer
primary key and means nothing on another server. `UniqueId` is the GUID that travels — and it
is what `StartTestComponents` takes, not the integer.

### A fourth sample disagrees with the table above, and is worth recording rather than resolving

A community-sourced export (a SolarWinds Content Exchange "Citrix Hypervisor" template, tagged
`New in 2020.2` in its own `Tags`, with `ModuleVersion._Major` reading `2026`) surfaced during
work on [sam-citrix-hypervisor-template.md](sam-citrix-hypervisor-template.md) and contradicts
several things this page states as universal from the first three samples:

- **Element order is different, and `Settings` and `ComponentTemplates` come first.** This
  sample's `ApplicationTemplate` root reads `Settings`, `ComponentTemplates`,
  `DeletedComponentTemplates`, `Id`, `Name`, `IsMockTemplate`, `Description`, `Tags`, `Created`,
  `LastModified`, `CustomApplicationType`, `Version`, `ViewID`, `ViewXml`, `ModuleVersion`,
  `UniqueId` — the metadata fields trail the payload instead of leading it, which is the
  reverse of the order in the table above.
- **The `Settings` map uses a different XML namespace.** This sample declares
  `xmlns:s="http://schemas.microsoft.com/2003/10/Serialization/Arrays"` on every `Settings`
  element (both the template's and each component's), not
  `http://schemas.datacontract.org/2004/07/System.Collections.Generic` as the three samples
  behind this page use. The element name `KeyValueOfstringSettingValueyR_SGpLPx` is identical
  either way.
- **The inner `Key` element is not always `i:nil="true"`.** At the template level this sample
  matches the three-sample pattern (`<Key i:nil="true" />`), but at the component level every
  setting's inner `Key` repeats the setting's own name instead (`<Key>__Disabled</Key>`).
- **`ModuleVersion` and `Tags` are not whitespace-only here.** `ModuleVersion` carries a real
  `_Build`/`_Major`/`_Minor`/`_Revision` structure, and `Tags` carries a list of `TagInfo`
  elements, each with a `Name` and the template's own `Id` repeated as `TemplateID`.

**This is not resolved into a single corrected table because there is nothing to resolve it
with.** Four real exports now disagree on element order and on one XML namespace, and the two
groups differ by more than one field, which reads like two distinct serialisation paths (an
older XmlSerializer-style export and a newer DataContractSerializer-style one, or simply a
platform-version difference) rather than one group being wrong. Both are reported here as
**working** by the people who supplied them. If you are hand-building a template, the
practically important consequence is: **match the order and namespace of an export from your
own server**, exported with `ExportTemplate` against the version you will import into, rather
than trusting either shape in this page blindly. If you discover which platform version
produces which shape, that is exactly the kind of fact worth adding here.

See [sam-citrix-hypervisor-template.md](sam-citrix-hypervisor-template.md#what-a-fourth-real-export-corrected)
for the full comparison, including the script output contract correction it drove.

### A fifth sample: the `PowerShell` and `PerformanceCounter` key sets

A 2026.4 export of SolarWinds' own *Server Clock Drift (PowerShell)* template (two `PowerShell`
and 25 `PerformanceCounter` components) was supplied on 2026-09-17 while building
[sam-udp-port-exhaustion-template.md](sam-udp-port-exhaustion-template.md). It has the fourth
sample's shape (payload first, `Serialization/Arrays` namespace, inner `Key` repeating the
name, `TagInfo` tags, structured `ModuleVersion`), so that shape is now two-for-two on current
servers. It also settles the two component types this page had only listed:

| `PowerShell` key | Required | ValueType | In the sample |
| --- | --- | --- | --- |
| `__Disabled` | false | Boolean | `False` |
| `__CredentialSetId` | false | String | `0` |
| `__UserDescription`, `__UserNotes` | false | String | |
| `CountAsDifference` | false | Boolean | `false` |
| `ExecutionMode` | false | Option | `LocalHost` |
| `ImpersonateForLocalMode` | false | Boolean | `false` |
| `ScriptArguments` | false | String | `time.nist.gov` |
| `ScriptBody` | true | External | the script |
| `StatusRollupType` | true | Option | `Worst` |
| `WrmPort` | true | Integer | `5985` |
| `WrmUrlPrefix` | true | String | `wsman` |
| `WrmUseSSL` | false | Boolean | `false` |

| `PerformanceCounter` key | Required | ValueType | In the sample |
| --- | --- | --- | --- |
| `__Disabled` | false | Boolean | `False` |
| `__CredentialSetId` | true | String | `0` |
| `__DataTransformCheckedRadioButton` | false | Boolean | `0` |
| `__DataTransformCommonFormulaIndex` | false | Integer | `0` |
| `__DataTransformCommonFormulaOptions` | false | String | `0` |
| `__DataTransformEnabled` | false | Boolean | `false` |
| `__UserDescription`, `__UserNotes` | false | String | |
| `_BB_CanBeDisabled` | false | Boolean | `true` |
| `Category`, `Counter` | true | String | |
| `CountAsDifference` | false | Boolean | `false` |
| `FeatureNameRegex` | false | String | empty |
| `Instance` | false | String | empty |
| `PreferredPollingMethod` | true | Option | `Default` |
| `SkipFallback` | false | Boolean | `true` |
| `TransformExpression` | false | String | empty |
| `WinRmAuthenticationMechanism` | false | Option | `Negotiate` |

Three things this sample corrects or adds:

- **Neither type carries `__Frequency` or `__Timeout` on the component.** The Citrix sample's
  `LinuxScript` components do. Writing them onto a `PowerShell` or `PerformanceCounter`
  component is a plausible way to make an import fail.
- **`PowerShell` does not carry `WinRmAuthenticationMechanism`; `PerformanceCounter` does.**
  The earlier table on this page listed the key without saying which type owns it.
- **A `PowerShell` component reports one unnamed pair**, `Message:` and `Statistic:`, matched
  by two `DynamicEvidenceColumnSchema` entries both named `Statistic`, a `String` column with
  an empty `<DataTransform />` and a `Numeric` column with the nested one, and its
  `<Thresholds />` is empty, the numeric column's own `Threshold` carrying the levels.
  `PerformanceCounter` is the reverse: a `Thresholds` block keyed `StatisticData` and an empty
  `<DynamicColumnSettings />`. `ApplicationItemType` is empty rather than `None`, and
  `ComponentCategoryName` is `i:nil`.

A template built to these two key sets, [sam-udp-port-exhaustion-template.md](sam-udp-port-exhaustion-template.md),
imported on the same 2026.4 server and polled Up on 2026-09-17, which also confirmed
`RemoteHost` as the `ExecutionMode` string for the console's "Remote Host".

### A sixth sample: the `EventLog` key set and its four status modes

A console-built template with four Windows Event Log Monitor components, exported from the
same 2026.4 server the same day, gives the `EventLog` type. Its template-level `Settings`
carried only `__Timeout` and `__Use64Bit`, so the four template keys the first three samples
share are not all mandatory on export.

| `EventLog` key | Required | ValueType | Values seen |
| --- | --- | --- | --- |
| `__Disabled` | false | Boolean | `False` |
| `__CredentialSetId` | true | String | `0` |
| `__DataTransformCheckedRadioButton` | false | Boolean | `0` |
| `__DataTransformCommonFormulaIndex` | false | Integer | `0` |
| `__DataTransformCommonFormulaOptions` | false | String | `0` |
| `__DataTransformEnabled` | false | Boolean | `false` |
| `__UserDescription`, `__UserNotes` | false | String | |
| `CollectDetails` | true | Boolean | `true` |
| `EntryExcludeFilter` | false | String | empty |
| `EntryExcludeOperation` | false | Option | `Match`, `Keywords`, `Disable` |
| `EntryID` | false | String | `0` (none), `16384`, `1023` |
| `EntryIDType` | false | Option | `IncludeIDs` |
| `EntryIncludeFilter` | false | String | quoted phrases, comma-separated |
| `EntryIncludeOperation` | false | Option | `Match`, `Keywords`, `Disable` |
| `EntryMatch` | true | Option | `Custom` |
| `EntrySource` | false | String | the provider name |
| `EntryType` | false | Option | `Information`, `Error` |
| `FetchingMethod` | true | Option | `Wmi` |
| `LogName` | true | Option | `Custom` |
| `LogNameFilter` | false | String | `Application`, `Realtek` |
| `NumberOfFrequencies` | true | **Double** | `1.5` |
| `StatusSetting` | false | Option | `Down`, `Up`, `EventsBased`, `EventCountBased` |
| `TransformExpression` | false | String | empty |
| `Users` | false | String | empty |
| `WinRmAuthenticationMechanism` | false | Option | `Negotiate` |

`Double` is a sixth `ValueType`, absent from the earlier table on this page. The component's
`Thresholds` block is keyed `StatisticData` like a `PerformanceCounter`, and
`DynamicColumnSettings` is empty. `LogName` = `Custom` with the log's own name in
`LogNameFilter` is how the console wrote even the stock `Application` log; whether a
non-`Custom` `LogName` value exists in the file is not shown by this sample. `StatusSetting`
is the console's "If a match is found in a polling period, component is": `Down` and `Up`
are the two fixed answers, `EventsBased` follows the matched events' own levels, and
`EventCountBased` thresholds the count.

## Settings are a typed key/value map

Both the template and each component carry a `Settings` map, serialised as .NET dictionary
entries with a mangled type name:

```xml
<s:KeyValueOfstringSettingValueyR_SGpLPx>
  <s:Key>__DebugLoggingEnabled</s:Key>
  <s:Value>
    <Required>true</Required>
    <SettingLevel>Template</SettingLevel>
    <Value>False</Value>
    <ValueType>Boolean</ValueType>
    <Key i:nil="true"/>
  </s:Value>
</s:KeyValueOfstringSettingValueyR_SGpLPx>
```

`KeyValueOfstringSettingValueyR_SGpLPx` is generated by the serialiser from the type
signature. **Copy it verbatim** — the trailing hash is not decorative and a hand-written
element with a different one will not deserialise.

`ValueType` takes five values across the three samples, and each governs a distinct group of
keys:

| `ValueType` | Used for | Examples |
| --- | --- | --- |
| `String` | Free text and numeric-as-text | `__CredentialSetId`, `__Frequency`, `__Timeout`, `TransformExpression` |
| `Boolean` | Flags, written `True`/`False` | `__Disabled`, `CountAsDifference`, `SkipFallback` |
| `Option` | An enumerated choice | `WinRmAuthenticationMechanism`, `StatusRollupType`, `ExecutionMode` |
| `Integer` | Real integers | `Port`, `PortNumber`, `WrmPort` |
| `External` | A large payload held outside the normal value flow | `ScriptBody` — and nothing else |

`SettingLevel` is `Template` on **all 1,015 settings across all three files**. That the value
can be anything else is an inference from the name and is **unverified here**.

The four template-level keys are the same in all three samples: `__DebugLoggingEnabled`,
`__NumberOfLogFilesToKeep`, `__Timeout` and `__Use64Bit`.

**Keys beginning `__` are platform settings; keys beginning `_BB_` are builder metadata**
(`_BB_CanBeDisabled`, `_BB_CanBeDisabledOnAppItemLevel`); everything else is specific to the
component type.

## Components

`ComponentTemplates` holds one `ComponentTemplate` per monitor. The three samples carry 10, 13
and 44.

```xml
<ComponentTemplate>
  <ComponentOrder>1</ComponentOrder>
  <Id>3105</Id>
  <Name>Server: Global Lock Statistic</Name>
  <Settings>…</Settings>
  <Type>LinuxScript</Type>
  <Thresholds>…</Thresholds>
  <EvidenceType>None</EvidenceType>
  <CategoryDisplayName>None</CategoryDisplayName>
  <ComponentCategoryId/>
  <DynamicColumnSettings>…</DynamicColumnSettings>
  <VisibilityMode>Visible</VisibilityMode>
  <ShortName/>
  <ApplicationItemType>None</ApplicationItemType>
  <ApplicationTemplateId>171</ApplicationTemplateId>
  <UniqueId>5309c609-14be-461c-82da-11fadd0aec1f</UniqueId>
  <ComponentCategoryName/>
  <IsApplicationItemSpecific>false</IsApplicationItemSpecific>
</ComponentTemplate>
```

`ApplicationTemplateId` on a component repeats its parent's local `Id`, so it is stale on
import in the same way. `EvidenceType`, `CategoryDisplayName` and `ApplicationItemType` are
`None` and `VisibilityMode` is `Visible` on **all 67 components** in the three samples; their
other legal values are **not documented and unverified here**.

### The component types seen

| `Type` | Count | Monitors |
| --- | --- | --- |
| `PerformanceCounter` | 19 | A Windows performance counter |
| `WindowsService` | 17 | A service's running state |
| `PowerShell` | 15 | A PowerShell script's output |
| `LinuxScript` | 8 | A script executed over SSH |
| `Process` | 2 | A Windows process |
| `DirectorySize` | 2 | A directory's size on disk |
| `Http` / `Https` | 2 | An HTTP request and its response |
| `TcpPort` | 1 | A TCP port's reachability |
| `ProcessOverSNMP` | 1 | A process, polled by SNMP |

SAM ships far more monitor types than this; the list is **what three templates happened to
use**, not the complete set.

Each type reads a different subset of `Settings`. `WindowsService` uses `ServiceName` and
`NotRunningStatusMode`; `PerformanceCounter` uses `Category`, `Counter`, `Instance` and
`PreferredPollingMethod`; `Http`/`Https` use `Url`, `SearchString`, `FailIfFound`, `FollowRedirect`
and a proxy group.

**Correction to an earlier version of this page:** it stated the script types use `ScriptBody`,
`ScriptArguments` and `ExecutionMode`, inferred from element names the three samples never
actually populated on a `LinuxScript` component. The fourth sample discussed above (63
`LinuxScript` components, all real and reportedly working) uses neither `ScriptArguments` nor
`ExecutionMode` at all, and instead carries `ScriptBody`, `ScriptDirectory` (a working directory,
`/tmp` in every instance), `CommandLineToPass` (the interpreter invocation, with the `${SCRIPT}`
macro and any operator-supplied arguments — see
[sam-citrix-hypervisor-template.md](sam-citrix-hypervisor-template.md#the-commandlinetopass-argument-prompt-mechanism)
for what that argument mechanism does), `AuthenticationType` (`UsernamePassword` in every
instance), `Port` (`22`), `CountAsDifference` (`false`), and `StatusRollupType` (`Worst`). Since
this is now two disagreeing real samples rather than one inferred guess, treat both key sets as
things a `LinuxScript` component *might* need depending on platform version, confirm which one
your server's console writes by building one and exporting it, and do not assume `ExecutionMode`
exists at all without checking.

### Thresholds

44 of the 67 components carry thresholds; the rest have an empty `<Thresholds/>`.

```xml
<s:KeyValueOfstringThresholdyR_SGpLPx>
  <s:Key>CPU</s:Key>
  <s:Value>
    <AreHigherValuesBetter>false</AreHigherValuesBetter>
    <ComputeBaseline>true</ComputeBaseline>
    <CriticalLevel>90</CriticalLevel>
    <CriticalPolls>1</CriticalPolls>
    <CriticalPollsInterval>1</CriticalPollsInterval>
    <IsForParentComponent>false</IsForParentComponent>
    <IsForTemplate>true</IsForTemplate>
    <MaxValue>100</MaxValue>
    <Name>CPU</Name>
    <WarnLevel>80</WarnLevel>
    <WarningPolls>1</WarningPolls>
    <WarningPollsInterval>1</WarningPollsInterval>
    <ThresholdOperator>Greater</ThresholdOperator>
    <CriticalFormula/>
    <WarningFormula/>
  </s:Value>
</s:KeyValueOfstringThresholdyR_SGpLPx>
```

Three things worth extracting:

- **`CriticalPolls` and `CriticalPollsInterval` are the "sustained for N polls" controls**, so
  a threshold can require a breach to persist rather than firing on one bad sample. Both are
  `1` throughout the samples, meaning fire immediately.
- **`ComputeBaseline: true`** opts the metric into baseline calculation, which is what
  `Orion.APM.Component.CalculateBaselineThresholds` acts on — see [sam.md](sam.md).
- **`CriticalFormula` and `WarningFormula` are empty but present**, so a formula-based
  threshold is expressible. Its syntax is **not documented and unverified here**.

`ThresholdOperator` is `Greater` throughout; the other operators are not exercised.

### Dynamic script columns: `DynamicColumnSettings` and the `Statistic.<Name>` output contract

None of the three original samples populate `DynamicColumnSettings` on a script component, so
this page previously left its structure undocumented. The fourth sample described above (the
Citrix Hypervisor community template) does populate it, on every one of its 63 `LinuxScript`
components, and the structure and the script output contract that feeds it are now verified
from that real, working export:

```xml
<DynamicColumnSettings>
  <DynamicEvidenceColumnSchema>
    <Cells />
    <ComponentID>-1</ComponentID>
    <ComponentTemplateID>885</ComponentTemplateID>
    <DataTransform>
      <CommonFormulaOptions>0</CommonFormulaOptions>
      <TransformExpression></TransformExpression>
    </DataTransform>
    <DataTransformOverridden>false</DataTransformOverridden>
    <Disabled>false</Disabled>
    <ID>221</ID>
    <Label>Host Average CPU Utilization</Label>
    <LabelOverridden>false</LabelOverridden>
    <Name>Host_AverageCPU_Utilization</Name>
    <ParentID>-1</ParentID>
    <Threshold>
      <AreHigherValuesBetter>false</AreHigherValuesBetter>
      <BaselineApplyError></BaselineApplyError>
      <ComputeBaseline>true</ComputeBaseline>
      <CriticalFormula></CriticalFormula>
      <CriticalLevel>1.7976931348623157E+308</CriticalLevel>
      <CriticalPolls>1</CriticalPolls>
      <CriticalPollsInterval>1</CriticalPollsInterval>
      <IsForParentComponent>false</IsForParentComponent>
      <IsForTemplate>false</IsForTemplate>
      <MaxValue>100</MaxValue>
      <Name></Name>
      <WarnLevel>1.7976931348623157E+308</WarnLevel>
      <WarningFormula></WarningFormula>
      <WarningPolls>1</WarningPolls>
      <WarningPollsInterval>1</WarningPollsInterval>
      <ThresholdOperator>Greater</ThresholdOperator>
    </Threshold>
    <ThresholdOverridden>false</ThresholdOverridden>
    <Type>Numeric</Type>
  </DynamicEvidenceColumnSchema>
</DynamicColumnSettings>
```

One `DynamicEvidenceColumnSchema` element per reported value. **`ComponentTemplateID` repeats
the owning component's own `Id`** — not `-1` like `ComponentID`, which is a separate,
always-`-1` placeholder in every one of the 63 samples. `ID` is a small integer unique across
the whole file, sequential-ish but not reset per component. `1.7976931348623157E+308` is
`double.MaxValue`, used here as the sentinel for "no threshold set" on both `CriticalLevel` and
`WarnLevel` — a component ships with this default and an operator sets a real number afterward.
`Type` is `String` or `Numeric` in the sample; whether other values are legal is unverified.

**The script's own output is what ties a line of text to one of these columns**, and this is
the second thing the same sample settles: every script prints

```
echo "Statistic.<Name> : <value>";
```

where `<Name>` is exactly the `Name` of one `DynamicEvidenceColumnSchema` entry — not a fixed
numbered slot, and not an arbitrary free-form label. A component reporting `k` values needs `k`
matching `DynamicEvidenceColumnSchema` entries and `k` `echo` lines, one per name; the sample
here never exercises more than one value per component, so how many a single run can carry, and
whether the literal separator (`.` after `Statistic`, ` : ` before the value) tolerates any
variation, remain **unverified beyond what a script emitting exactly one line, matching exactly
one column, has proven**. `sam.md`'s own note that `DynamicEvidence`/`DynamicEvidenceColumnSchema`
carry "the columns a script monitor returned" is confirmed by this sample rather than
superseded by it.

## Credentials do not travel, and neither do secrets

**All 67 components in all three files carry `__CredentialSetId` of `0`.** The export does not
reference a credential set, let alone contain one.

Scripts refer to credentials through **macro placeholders that the platform substitutes at poll
time**:

| Macro | Occurrences | Substituted with |
| --- | --- | --- |
| `${USER}` | 32 | The assigned credential's username |
| `${PASSWORD}` | 8 | Its password |
| `${IP}` | 5 | The target node's address |
| `${PORT}` | 3 | The configured port |
| `${SCRIPT}` | 8 | The script's own path on the target |

So a Perl fragment in the MongoDB template reads:

```perl
if('${USER}' ne ''){
  $pwdEscapeChar = quotemeta(q(${PASSWORD}));
  $connectionCmd = $client_path.' -u '.${USER}.' -p '.$pwdEscapeChar.
                   ' --authenticationDatabase '.$database;
}
```

and the Azure template's PowerShell declares `[Parameter(Mandatory=$True)] $password`, taking
the value as an argument rather than embedding it.

**This makes an `.apmtemplate` markedly safer to share than a
[report definition](../automation/report-definitions.md#before-you-share-one)**, which carries
hostnames and sampled values. The caveat is that `ScriptBody` is still *your script*: it is
exported verbatim, and anything you hard-coded in it — an internal hostname, a database name, a
fallback password — travels with it. Read the scripts before publishing a template you wrote.

## Moving a template between servers

A matched pair of verbs, unlike [reports](../automation/report-definitions.md), where export is
a query and import is a verb.

| Verb | Parameters | Returns | Right |
| --- | --- | --- | --- |
| `ExportTemplate` | `templateId` (the integer `ApplicationTemplateID`) | string | `manageNodes` |
| `ImportTemplate` | `templateData` (the whole XML) | number (new `ApplicationTemplateID`) | `manageNodes` |
| `DeleteTemplate` | `applicationTemplateId` | void | `manageNodes` |

```powershell
$templateId = Get-SwisData $sourceSwis @'
SELECT TOP 1 t.ApplicationTemplateID
FROM Orion.APM.ApplicationTemplate t
WHERE t.Name = @name
'@ @{ name = 'MongoDB 5.0+ (Linux) v2' }

$xml = Invoke-SwisVerb $sourceSwis 'Orion.APM.ApplicationTemplate' 'ExportTemplate' @($templateId)
$newId = Invoke-SwisVerb $targetSwis 'Orion.APM.ApplicationTemplate' 'ImportTemplate' @($xml.InnerText)
```

`ExportTemplate` takes the **integer** id while `StartTestComponents` takes the **GUID**
`UniqueId`. Both are on the same entity and both are called "the template id" in conversation,
so read the parameter name.

`.InnerText` is needed because `Invoke-SwisVerb` returns an XML element rather than a bare
string — see [../swis/invoke-verbs.md](../swis/invoke-verbs.md).

Whether `ImportTemplate` rejects, replaces or duplicates a template whose `UniqueId` already
exists is **not documented and unverified here**. The console's *report* import duplicates and
renames rather than replacing — see
[../automation/report-definitions.md](../automation/report-definitions.md#importing-a-definition-that-is-already-there)
— but that is a different subsystem and the behaviour does not necessarily carry across.

**There is no built-in-versus-custom flag to build an export inventory on.** Unlike
`Orion.AlertConfigurations.Canned` ([../automation/alerts.md](../automation/alerts.md)) or
`Cli.DeviceTemplates.IsDefault` ([ncm-device-templates.md](ncm-device-templates.md)), the
entity carries no built-in indicator: `IsMockTemplate = FALSE` excludes only mock rows, and
`CustomApplicationType` is empty on ordinary template-based rows whoever wrote them. A SWQL
`WHERE` clause cannot restrict the inventory to user-authored templates, so filter
client-side instead — by your own naming convention, or by `Created` and `LastModified`
dates.

### Test before you assign

```powershell
$results = Invoke-SwisVerb $swis 'Orion.APM.ApplicationTemplate' 'StartTestComponents' @(
    $nodeId, $templateUniqueId, $credentialId)
```

`StartTestComponents` runs the template's components against a real node without creating an
application, and returns an array of `TestComponentResult` objects — the same shape
`GetTestComponentStatus` returns. Each element carries `ComponentId`, `JobId`, `Status` and
`Message`; the `JobId` members are the GUID strings to feed back to `GetTestComponentStatus`
as its `jobs` array. `Status` is one of `Undefined`,
`Available`, `NotAvailable`, `PartlyAvailable`, `NotLicensed`, `Warning`, `Critical`,
`IsDisabled`, `Unmanaged`, `Unplugged`, `NotRunning`, `Unreachable`.

**This is the dry run**, and it is worth using: an imported template that references a
credential the target server lacks, or a script interpreter that is not installed, fails at
first poll otherwise.

### What breaks on the way across

- **`Id` and `ApplicationTemplateId` are stale.** Local integers from the source server. The
  import assigns new ones.
- **Credentials.** `__CredentialSetId` is `0`, so every imported component needs a credential
  chosen at assignment. That is deliberate, but it means a template is never ready to poll the
  moment it lands.
- **Component types the target does not support.** A `ProcessOverSNMP` or `LinuxScript`
  component needs the polling method available on the target's engines.
- **`ViewXml`.** Carries the template's custom view. Empty in all three samples, so its
  cross-server behaviour is unexercised here.

## Writing one by hand

Build it in the console and export. The serialiser's mangled type names
(`KeyValueOfstringSettingValueyR_SGpLPx`, `KeyValueOfstringThresholdyR_SGpLPx`), the exact
element order within each type, and the 2007 namespace all have to be right, and none of them
is guessable.

Editing an export is reasonable, and the two safe edits are:

- **`ScriptBody`** — the script is plain text inside the element, with `<` and `&` XML-escaped.
- **Threshold levels** — `WarnLevel` and `CriticalLevel` are plain numbers.

Then import and let the platform validate. If you generate templates programmatically, the
robust approach is to export a known-good one and rewrite values in place rather than
constructing the document from nothing.

## See also

- [sam.md](sam.md) — the SAM entities, all thirty-nine verbs, and assigning a template to a node
- [sam-citrix-hypervisor-template.md](sam-citrix-hypervisor-template.md) — a worked template
  built to this format, monitoring a Citrix Hypervisor host with no AppInsight module
- [sam-udp-port-exhaustion-template.md](sam-udp-port-exhaustion-template.md) — a second worked
  template, `PowerShell` over WinRM plus native counters, for Windows UDP port exhaustion
- [../polling/api-pollers.md](../polling/api-pollers.md#the-apipollertemplate-file-format) —
  the other matched-verb template format, and much simpler
- [../automation/report-definitions.md](../automation/report-definitions.md) — the third
  exportable XML artefact, where export is a query rather than a verb
- [../automation/credentials.md](../automation/credentials.md) — the credential sets a template
  is assigned with
- [apps/porter](../../apps/porter/README.md) — a shipped Windows utility whose SAM provider implements the `ExportTemplate`/`ImportTemplate` round trip documented here, with the script-body review warning

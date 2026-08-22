# API pollers

An API poller collects metrics by calling an HTTP endpoint and reading values out of the
response, rather than by asking a device over SNMP or WMI. That makes it the mechanism for
monitoring anything with a REST interface and no SNMP agent — a SaaS service, an appliance's
management API, an internal application's health endpoint.

It is worth treating as its own subsystem rather than as a kind of poller.
[standard-pollers.md](standard-pollers.md) covers `Orion.Pollers`, which is an assignment table joining a
poller type string to a NetObject. API pollers share none of that: they have no poller type
string, no NetObject, and a model of ten entities of their own.

## The model

Ten entities, and the shape is a chain rather than a table:

| Entity | Holds | Size |
| --- | --- | --- |
| `Orion.APIPoller.ApiPoller` | The poller itself | 14 properties, 3 verbs |
| `Orion.APIPoller.Templates` | The template library it can be created from | 12 properties, 3 verbs |
| `Orion.APIPoller.RequestDetails` | One HTTP request: URL, verb, body, credentials | 11 properties |
| `Orion.APIPoller.RequestHeader` | One header on one request | 4 properties |
| `Orion.APIPoller.RequestVariable` | A value lifted out of one response to use in a later request | 4 properties |
| `Orion.APIPoller.ValueToMonitor` | One metric extracted from a response, with thresholds | 18 properties |
| `Orion.APIPoller.StringToNumberTransformationRule` | A text-to-number mapping for a non-numeric value | 4 properties |
| `Orion.APIPoller.PollingConfiguration` | The polling interval | 2 properties |
| `Orion.APIPoller.ApiPoller.Metrics` | Poller status over time | 3 properties |
| `Orion.APIPoller.ValueToMonitor.Metrics` | Each metric's min, max and average over time | 6 properties |

Read down the chain and the design is clear: a poller owns one or more requests, a request
owns its headers and the values to monitor, and a value owns its history. Every level keys
back with a plain id column and also declares a navigation property, so both join styles
work.

### The rights run the opposite way to most entities

`Orion.APIPoller.ApiPoller` grants `read` to `everyone` and every other operation —
create, read, update, delete and invoke — to **`admin`**. But all six verbs across the two
entities declare **`manageNodes`**:

```bash
python3 tools/schema_query.py verb Orion.APIPoller.ApiPoller AssignTemplate
```

That is the reverse of the usual arrangement, where the verb is the more privileged of the
two (compare [../automation/dependencies.md](../automation/dependencies.md#the-verbs-want-admin-not-managenodes), where
CRUD takes `manageNodes` and the verbs take `admin`). The practical consequence is worth
stating plainly: an account with `manageNodes` can create an API poller from a template and
export one, but cannot edit the resulting rows directly. Automation that builds pollers
through the verbs needs less privilege than automation that writes the entities by hand,
which is a good reason to prefer the verbs.

## The poller

```sql
SELECT
    p.ID,
    p.Name,
    p.DisplayName,
    p.TemplateId,
    p.RelatedEntityType,
    p.RelatedEntityId,
    p.Status,
    p.StatusDescription,
    p.LastPollTimestamp
FROM Orion.APIPoller.ApiPoller p
ORDER BY p.Name
```

`RelatedEntityId` and `RelatedEntityType` are where a NetObject would be on any other
poller. The type is the entity name as a string, so a poller attached to a node carries
`Orion.Nodes` and the node's `NodeID`. There is also a declared navigation straight to the
node, which is the better way to write it:

```sql
SELECT
    p.Name,
    p.Status,
    p.LastPollTimestamp,
    p.Node.Caption,
    p.Node.IPAddress
FROM Orion.APIPoller.ApiPoller p
ORDER BY p.Node.Caption
```

That navigation is a `System.Reliance` rather than a reference, which is the schema saying
the poller depends on the node rather than merely pointing at it.

`Orion.APIPoller.ApiPoller` inherits from `System.ManagedEntity`, so it has the inherited
`Status` and `UnManaged` that a `System.Entity` would not. It is also one of the few entities
with a declared `StatusInfo` navigation, so the status name resolves without a join:

```sql
SELECT
    p.Name,
    p.Status,
    p.StatusInfo.StatusName,
    p.StatusInfo.Ranking
FROM Orion.APIPoller.ApiPoller p
WHERE p.Status <> 1
ORDER BY p.StatusInfo.Ranking
```

Most entities do not have that navigation. See
[../swql/gotchas.md](../swql/gotchas.md) for which do, and for why `Orion.Nodes` is not
among them.

**Pollers that have stopped polling** is the query worth running periodically, since an API
poller whose endpoint has moved fails quietly:

```sql
SELECT
    p.Name,
    p.Node.Caption,
    p.LastPollTimestamp,
    p.StatusDescription,
    MinuteDiff(p.LastPollTimestamp, GetDate()) AS MinutesSincePoll
FROM Orion.APIPoller.ApiPoller p
ORDER BY p.LastPollTimestamp
```

`LastPollTimestamp` carries **no documented timezone** in the schema and its name does not
end in `Utc`, so this is unverified here: settle it with the `MinuteDiff` probe in
[../swql/date-and-time.md](../swql/date-and-time.md#measuring-a-columns-timezone) before
trusting a narrow window.

## The request

One poller can make several requests, and `RequestDetailsOrder` is what makes that useful:

```sql
SELECT
    r.ApiPollerId,
    r.RequestDetailsOrder,
    r.HttpVerb,
    r.Url,
    r.CredentialsType,
    r.CredentialsId,
    r.VerifySslCertificate,
    r.UseProxy,
    r.RequestTimeout
FROM Orion.APIPoller.RequestDetails r
ORDER BY r.ApiPollerId, r.RequestDetailsOrder
```

Requests run in that order, and `Orion.APIPoller.RequestVariable` is how a later one uses an
earlier one's response. A variable names a `Path` into the response and a `DisplayName` to
refer to it by, which is the mechanism for the common case of authenticating first and then
calling the real endpoint with the token:

```sql
SELECT
    v.RequestDetailsId,
    v.DisplayName,
    v.Path
FROM Orion.APIPoller.RequestVariable v
ORDER BY v.RequestDetailsId
```

Headers hang off the request the same way:

```sql
SELECT
    h.RequestDetailsId,
    h.Name,
    h.Value
FROM Orion.APIPoller.RequestHeader h
ORDER BY h.RequestDetailsId, h.Name
```

**Do not export header values into anything shared.** `Value` is a plain
`System.String` and a hand-built poller routinely carries an API key in exactly that column.
Whether the platform redacts any header value on read is not recorded in the schema and is
unverified here; assume it does not. `CredentialsId` with `CredentialsType` is the safer
pattern, since it points at the credential store rather than holding the secret. See
[../automation/credentials.md](../automation/credentials.md).

**Two settings are per request rather than per poller.** `VerifySslCertificate` and
`UseProxy` are columns on `Orion.APIPoller.RequestDetails`, so a poller that authenticates
against one host and reads from another can verify one and not the other. That is useful and
it is also how a poller ends up silently not verifying a certificate:

```sql
SELECT
    r.Url,
    r.VerifySslCertificate,
    r.ApiPoller.Name
FROM Orion.APIPoller.RequestDetails r
WHERE r.VerifySslCertificate = FALSE
ORDER BY r.ApiPoller.Name
```

## The metric

`Orion.APIPoller.ValueToMonitor` is where a response becomes a number:

```sql
SELECT
    v.ApiPollerId,
    v.DisplayName,
    v.Path,
    v.Type,
    v.Metric,
    v.WarningThreshold,
    v.CriticalThreshold,
    v.ThresholdRule,
    v.Status
FROM Orion.APIPoller.ValueToMonitor v
ORDER BY v.ApiPollerId, v.DisplayName
```

`Path` selects the value out of the response body and `Metric` is the last value read.
Thresholds are `System.Double` and live on the value rather than on the poller, so each
metric is judged on its own. What syntax `Path` uses, and what values `Type` and
`ThresholdRule` accept, are **not recorded in the published schema** and are unverified here
— read existing rows on your own server before writing new ones.

A value that is text rather than a number goes through
`Orion.APIPoller.StringToNumberTransformationRule`, which is a lookup table of one `Text` to
one `Number`:

```sql
SELECT
    t.ValueToMonitorId,
    t.Text,
    t.Number
FROM Orion.APIPoller.StringToNumberTransformationRule t
ORDER BY t.ValueToMonitorId, t.Number
```

This is how a status endpoint returning `"healthy"` becomes something you can threshold on.
`StringToNumberTransformationOtherValues` on the value itself is the fallback for text that
matches no rule, which means an endpoint that starts returning a new string does not stop
reporting — it reports the fallback. Worth knowing before trusting a flat line.

### History

Two history entities, at two grains:

```sql
SELECT
    m.ValueToMonitorId,
    m.ObservationTimestamp,
    m.AvgMetric,
    m.MinMetric,
    m.MaxMetric,
    m.Status
FROM Orion.APIPoller.ValueToMonitor.Metrics m
ORDER BY m.ObservationTimestamp DESC
```

`Orion.APIPoller.ApiPoller.Metrics` is the coarser one, carrying only `Status` per
observation, which answers "was the poller working" rather than "what did it read".

Both are statistics tables and grow with every poll, so window them rather than scanning.
See [../swql/performance.md](../swql/performance.md).

### The interval

`Orion.APIPoller.PollingConfiguration` has two columns and one of them is the key, so this
is the whole of it:

```sql
SELECT
    c.ApiPollerId,
    c.PollingInterval,
    c.ApiPollerId AS Id
FROM Orion.APIPoller.PollingConfiguration c
ORDER BY c.PollingInterval DESC
```

`PollingInterval` is documented in the schema as minutes, which is worth noting because the
polling intervals on `Orion.Nodes` are in seconds. A value copied from one to the other is
wrong by a factor of sixty in whichever direction hurts more.

## The verbs

Six, split across the two entities that declare any. All six require `manageNodes`.

| Verb | Entity | Arguments | Returns |
| --- | --- | --- | --- |
| `CreateApiPollerFromTemplate` | `Orion.APIPoller.ApiPoller` | `entityType`, `entityId`, `template`, `configuration`, `parameters` | number |
| `AssignTemplate` | `Orion.APIPoller.ApiPoller` | `entityType`, `entityId`, `templateId`, `configuration`, `parameters` | number |
| `ExportTemplateFromApiPoller` | `Orion.APIPoller.ApiPoller` | `apiPollerId` | string |
| `ImportTemplate` | `Orion.APIPoller.Templates` | `template` | number |
| `ExportTemplate` | `Orion.APIPoller.Templates` | `id` | string |
| `DeleteTemplate` | `Orion.APIPoller.Templates` | `id` | boolean |

The two create verbs differ in one argument and it is the important one.
`CreateApiPollerFromTemplate` takes `template` as a **string**, the template document
itself; `AssignTemplate` takes `templateId` as a **number**, a row in the library. So the
first works from a document you are holding and the second from something already imported.
Passing an id where a document is wanted is not a type error — both coerce — and produces a
poller built from the text "42".

```bash
python3 tools/schema_query.py verb Orion.APIPoller.ApiPoller CreateApiPollerFromTemplate
```

`configuration` and `parameters` are both
`array<System.Collections.Generic.KeyValuePair~System.String_System.String~>`, two separate
string-to-string bags. **What belongs in which is not recorded in the published schema** and
is unverified here. The way to settle it is to build one poller in the console, export it,
and read what comes back:

```powershell
$swis = Connect-Swis -Hostname orion.example.com -Trusted

$pollerId = Get-SwisData $swis @'
SELECT TOP 1 ID FROM Orion.APIPoller.ApiPoller ORDER BY ID
'@

$template = Invoke-SwisVerb $swis 'Orion.APIPoller.ApiPoller' 'ExportTemplateFromApiPoller' @($pollerId)
$template.InnerText | Out-File -FilePath 'api-poller-template.txt' -Encoding utf8
```

### Moving a poller between servers

The export and import verbs are a matched pair, which makes promoting a poller from a test
server to production a two-call operation rather than a rebuild:

```powershell
# On the source server: export the library entry.
$document = Invoke-SwisVerb $sourceSwis 'Orion.APIPoller.Templates' 'ExportTemplate' @($templateId)

# On the target: import it, then build a poller on a node from the id that comes back.
$newTemplateId = Invoke-SwisVerb $targetSwis 'Orion.APIPoller.Templates' 'ImportTemplate' @($document.InnerText)

Invoke-SwisVerb $targetSwis 'Orion.APIPoller.ApiPoller' 'AssignTemplate' @(
    'Orion.Nodes',      # entityType
    $nodeId,            # entityId
    $newTemplateId,     # templateId
    $configuration,     # configuration
    $parameters         # parameters
)
```

`Invoke-SwisVerb` returns an XML element rather than a bare value, so `.InnerText` is what
carries the exported document across. See
[../swis/invoke-verbs.md](../swis/invoke-verbs.md).

Two things this does not carry across. A template holds the request shape, not the
credential: `CredentialsId` refers to a row in the target server's own credential store,
which has to exist there first. And an imported template is a new row with a new id, so
nothing that referenced the old id follows it.

## The template library

```sql
SELECT
    t.ID,
    t.Name,
    t.DisplayName,
    t.Version,
    t.IsCustom,
    t.RequestsCount,
    t.MetricsCount,
    t.Created,
    t.Updated
FROM Orion.APIPoller.Templates t
ORDER BY t.DisplayName
```

`IsCustom` separates what SolarWinds shipped from what someone here built, which is the
first thing to know before deleting anything. `RequestsCount` and `MetricsCount` are
denormalised counts that let you see the shape of a template without parsing it, and
`TemplateData` is the template itself as XML — **the same document `ExportTemplate` returns and
`ImportTemplate` accepts**, so you can read a template's full definition with a query instead
of an Invoke:

```sql
SELECT t.ID, t.DisplayName, t.TemplateData
FROM Orion.APIPoller.Templates t
WHERE t.IsCustom = 'True'
```

The next section documents that document's structure.

Templates nothing is using, which is the safe candidate set for cleanup:

```sql
SELECT
    t.ID,
    t.DisplayName,
    t.IsCustom,
    t.Updated
FROM Orion.APIPoller.Templates t
WHERE t.ID NOT IN (
    SELECT p.TemplateId FROM Orion.APIPoller.ApiPoller p
)
ORDER BY t.Updated
```

`DeleteTemplate` returns a boolean rather than throwing, so read the result. A `false` that
nobody checked looks exactly like a successful delete.

## The `.apipoller.template` file format

The console exports a template as a single-line XML document with the extension
`.apipoller.template`. It is the same string that `ExportTemplate` returns, that
`ImportTemplate` takes, and that sits in `Orion.APIPoller.Templates.TemplateData`. So there is
one document, reachable four ways: the console's export button, an Invoke, a SWQL select, and
a file on disk.

**Source:** derived by parsing a real export from a practitioner's installation and mapping it
against the 2026.2 schema. SolarWinds does not publish the format. Element names below are
quoted from that document; the entity and property names they map onto are checked against the
extracted schema like everything else here.

### The shape

```xml
<Template>
  <Guid>58dbeb34-…</Guid>
  <Name>ERCOT Operating Reserves &amp; Grid Emergency Status</Name>
  <DisplayName>ERCOT Operating Reserves &amp; Grid Emergency Status</DisplayName>
  <Description />
  <Created>2026-08-22T15:00:43.6650422Z</Created>
  <Updated>2026-08-22T15:00:43.6650422Z</Updated>
  <Version>1</Version>
  <RequestDetailsCollection>
    <RequestDetails>
      <Url>https://example.invalid/api/1/status.json</Url>
      <Body />
      <HttpVerb>Get</HttpVerb>
      <RequestHeaders />
      <ValueToMonitorCollection>
        <ValueToMonitor>
          <DisplayName>Operating Reserves (MW)</DisplayName>
          <Path>$.['current_condition'].['prc_value']</Path>
          <ThresholdRule>GreaterThan</ThresholdRule>
          <WarningThresholdValue>1</WarningThresholdValue>
          <CriticalThresholdValue>2</CriticalThresholdValue>
          <Type>Path</Type>
          <StringToNumberTransformationRules>
            <StringToNumberTransformationRule>
              <Text>Normal</Text>
              <Number>0</Number>
            </StringToNumberTransformationRule>
          </StringToNumberTransformationRules>
          <StringToNumberTransformationOtherValues>5</StringToNumberTransformationOtherValues>
        </ValueToMonitor>
      </ValueToMonitorCollection>
      <RequestVariables />
      <RequestDetailsOrder>0</RequestDetailsOrder>
    </RequestDetails>
  </RequestDetailsCollection>
  <PollingInterval>2</PollingInterval>
</Template>
```

The root carries `xmlns:xsd` and `xmlns:xsi` declarations, which is the signature of .NET's
`XmlSerializer` — the document is a serialised object graph rather than a hand-designed
schema. Empty collections serialise as self-closing elements (`<RequestHeaders />`), not as
omitted ones.

### Element by element, against the schema

| XML element | Maps to | Notes |
| --- | --- | --- |
| `Guid` | `Orion.APIPoller.Templates.Guid` | The template's identity **across servers**. `ID` is local and is not in the file |
| `Name`, `DisplayName` | `Name`, `DisplayName` | Both present, both the same string in the sample |
| `Description` | `Description` | Empty is legal |
| `Created`, `Updated` | `Created`, `Updated` | ISO-8601 UTC, sub-microsecond precision |
| `Version` | `Version` | `System.Int32`; `1` in the sample |
| `RequestDetailsCollection/RequestDetails` | `Orion.APIPoller.RequestDetails` | One per HTTP call; a template may make several |
| `Url`, `Body`, `HttpVerb` | same names | `HttpVerb` is title-case (`Get`), not `GET` |
| `RequestHeaders` | `Orion.APIPoller.RequestHeader` | `Name`/`Value` pairs |
| `RequestVariables` | `Orion.APIPoller.RequestVariable` | `Path`/`DisplayName`; values lifted from one response to use in the next |
| `RequestDetailsOrder` | `RequestDetailsOrder` | Zero-based; the order multi-request templates run in |
| `ValueToMonitorCollection/ValueToMonitor` | `Orion.APIPoller.ValueToMonitor` | One per metric |
| `Path` | `Path` | A JSONPath expression |
| `ThresholdRule` | `ThresholdRule` | `GreaterThan` in the sample |
| `WarningThresholdValue` | **`WarningThreshold`** | The names differ between file and schema |
| `CriticalThresholdValue` | **`CriticalThreshold`** | Likewise. `System.Double` in the schema, written as bare integers here |
| `Type` | `Type` | `Path` in the sample |
| `StringToNumberTransformationRule` | `Orion.APIPoller.StringToNumberTransformationRule` | `Text`/`Number` pairs |
| `StringToNumberTransformationOtherValues` | same name | The fallback for text no rule matches |
| `PollingInterval` | `Orion.APIPoller.PollingConfiguration.PollingInterval` | **Minutes.** `2` is a two-minute poll |

**Five runtime properties have no element in the file.** `Orion.APIPoller.RequestDetails`
declares `CredentialsId`, `CredentialsType`, `VerifySslCertificate`, `UseProxy` and
`RequestTimeout`, and none of them appears in the export.

That credentials do not travel is correct and deliberate — a template is meant to be shared.
But it means **an imported template is not a complete poller**: SSL verification, proxy use,
timeout and any credential have to be supplied when the template is assigned, which is what
the `configuration` and `parameters` arrays on `AssignTemplate` and
`CreateApiPollerFromTemplate` are for. Import a template that polls an authenticated endpoint,
assign it with empty arrays, and it will fail at the first poll with an authentication error
rather than an import error. Whether those two arrays are the only route, and which keys they
accept, is **not documented and unverified here**.

### Writing one by hand

You do not have to. The supported path is to build the poller once in the console —
**Settings > All Settings > API Poller**, or the API Poller tab on a node — and export it. The
console writes the GUID, the timestamps and the serialisation details for you.

Authoring the XML directly is still reasonable for a template you want to generate, and the
rules that matter are:

- **A fresh `Guid` per template.** It is the cross-server identity. Two templates sharing one
  is the same class of mistake as a duplicated dashboard `unique_key` — see
  [../webui/modern-dashboards.md](../webui/modern-dashboards.md#unique_key-collisions-and-the-reuse-that-is-fine).
  What the platform does on import when the GUID already exists — replace, duplicate or
  reject — is **not documented and unverified here**. Test on a lab server before you rely on
  re-import as an update mechanism.
- **Escape XML properly.** The sample's name contains `&amp;` for a literal ampersand, and the
  transformation text contains an em dash and a `&lt;`. A template whose thresholds describe
  `Reserve < 1,750 MW` will not parse if that `<` is written raw.
- **Do not omit empty elements.** Write `<Description />` and `<RequestHeaders />` rather than
  leaving them out, matching what the serialiser emits.
- **`RequestDetailsOrder` starts at 0** and is what sequences a multi-call template.
- **`PollingInterval` is minutes**, and lives on the template root rather than inside
  `RequestDetails`, so it applies to the whole poller.

Then import it and let the platform validate:

```powershell
$xml = Get-Content -Raw '.\my-poller.apipoller.template'
$newTemplateId = Invoke-SwisVerb $swis 'Orion.APIPoller.Templates' 'ImportTemplate' @($xml)
```

### Numeric thresholds against text values

The `StringToNumberTransformation` pair is the part worth understanding, because it is what
lets a poller alert on an API that returns words.

The platform thresholds on numbers. When the value at `Path` is text, each
`StringToNumberTransformationRule` maps one exact string to one number, and
`StringToNumberTransformationOtherValues` catches everything unmatched. The thresholds then
apply to the mapped number.

In the sample, four rules map an emergency-status vocabulary to `0`–`3`, the fallback is `5`,
and the rule is `GreaterThan` with warning `1` and critical `2`. So: normal is `0`, the first
alert level is warning, the second and third are critical — **and any string the rules do not
recognise becomes `5`, which is also critical.**

That fallback choice is the design decision to copy. Setting it above the critical threshold
means *an unrecognised response pages someone*, which is almost always what you want: an API
that starts returning a new status string is a change you need to hear about, and a fallback
of `0` would hide it as "normal" forever.

**Matching is exact-string** — the rules in the sample carry an em dash and parenthesised
detail, all of which must match the response byte for byte. That is a real fragility: a
provider rewording `EEA 2 (Reserve < 1,750 MW — emergency generation deployed)` breaks the
mapping. With a fallback above critical, it breaks loudly, which is the mitigation.

Whether matching is case-sensitive, trims whitespace, or supports any wildcard is **not
documented and unverified here**.

### One thing to check in a template you are given

A `ValueToMonitor` has both a `Path` and a set of string rules, and nothing makes them agree.
If the path resolves to a **number**, the string rules cannot match and every poll takes the
fallback; if it resolves to **text**, the thresholds apply to the mapped number and the
`DisplayName` should describe the mapping rather than the raw value.

The sample shows the tension: its `DisplayName` is `Operating Reserves (MW)` and its `Path`
ends in `prc_value`, both suggesting a megawatt figure, while its rules and its warning-at-1
threshold are built for a small ordinal status. Those readings cannot both be right — a
megawatt reading would exceed a critical threshold of `2` on every poll. Establish which the
endpoint actually returns before trusting the alert, and align `DisplayName` with whichever it
is. This is not a flaw in the format; it is the format faithfully recording two different
intentions.

## Practical notes

**Prefer the verbs to CRUD.** Building a poller by writing `Orion.APIPoller.ApiPoller`,
then its `RequestDetails`, then the headers, then the values to monitor is four levels of
rows that have to be consistent, and it needs `admin`. `CreateApiPollerFromTemplate` does it
in one call with `manageNodes`.

**The related entity is not a NetObject.** `RelatedEntityType` is an entity name and
`RelatedEntityId` is that entity's own key, so nothing here takes `N:42`. See
[../reference/netobject-types.md](../reference/netobject-types.md) for where NetObject
strings do apply.

**A poller with no values to monitor polls and reports nothing.** The poller row, the
request and the metric are separate entities, and nothing in the schema requires the third to
exist. Check the chain rather than the poller when a new poller produces no data:

```sql
SELECT
    p.Name,
    COUNT(v.ID) AS ValuesToMonitor
FROM Orion.APIPoller.ApiPoller p
LEFT JOIN Orion.APIPoller.ValueToMonitor v ON v.ApiPollerId = p.ID
GROUP BY p.Name
ORDER BY COUNT(v.ID)
```

## See also

- [README.md](README.md) for the other four polling systems and how to tell them apart
- [standard-pollers.md](standard-pollers.md) for `Orion.Pollers`, the built-in poller assignments
- [../automation/credentials.md](../automation/credentials.md) for the credential store `CredentialsId` points at
- [../swis/invoke-verbs.md](../swis/invoke-verbs.md) for the Invoke contract and array arguments
- [../swql/gotchas.md](../swql/gotchas.md) for the `StatusInfo` navigation
- [../swql/performance.md](../swql/performance.md) for windowing the statistics tables
- [../schema/status-codes.md](../schema/status-codes.md) for what the status integers mean

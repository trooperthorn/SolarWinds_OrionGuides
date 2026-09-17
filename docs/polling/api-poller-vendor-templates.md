# Reading a vendor-shipped API Poller template

[api-pollers.md](api-pollers.md#the-apipollertemplate-file-format) documents the
`.apipoller.template` format from a single export. That export used one `Type` value and
filled in both thresholds, which is what a poller built for one specific target looks like.
A template SolarWinds ships is built for every target, and it is shaped differently in ways
that matter when you read one or generate one.

This page is read off three templates from SolarWinds' own published template library,
unmodified: **Microsoft Azure Virtual Machine**, **ServiceNow**, and **Microsoft 365 Exchange
Mailboxes**. The files are kept in
[scripts/api-pollers/vendor-examples/](../../scripts/api-pollers/vendor-examples/) as
reference material. They are not build-validated, for a reason this page explains.

**Source:** official `.apipoller.template` exports from the SolarWinds template library. The
XML below is transcribed from those files. The entity and property names the elements map onto
are checked against the extracted 2026.2 schema like everything else here.

## Three `Type` values, from real exports

`Orion.APIPoller.ValueToMonitor.Type` is a `System.String` and the published schema records
nothing about what it accepts, which is why
[api-pollers.md](api-pollers.md#the-metric) marks it unverified. The three vendor templates
between them use three distinct values, so those three are now observed rather than guessed.
Whether any others exist is still unverified here.

### `Path`: a JSONPath into the response body

The common case, and the only one the earlier export showed. Azure's template pulls nine
named metrics out of one Azure Monitor response, addressing each by its position in the
returned array:

```xml
<ValueToMonitor>
  <DisplayName>CPU Percentage</DisplayName>
  <Path>$.['value'].[0].['timeseries'].[0].['data'].[0].['average']</Path>
  <ThresholdRule>GreaterThan</ThresholdRule>
  <WarningThresholdValue xsi:nil="true" />
  <CriticalThresholdValue xsi:nil="true" />
  <Type>Path</Type>
  <StringToNumberTransformationRules />
  <StringToNumberTransformationOtherValues xsi:nil="true" />
</ValueToMonitor>
```

The positional addressing is worth pausing on. `[0]` is CPU only because `Percentage CPU` is
first in the `metricnames` list in the request URL, and `[7]` is `CPU Credits Remaining`
only because it is eighth. Reorder that query string and every one of the nine paths now reads
a different metric, with no error anywhere. One request carrying an ordered array of metrics is
efficient and it couples the paths to the URL, which is a coupling nothing in the file records.

### `Header`: a JSONPath over the response headers

The ServiceNow template is the interesting one, because six of its requests do not read the
body at all. ServiceNow returns the row count of a filtered query in an `X-Total-Count`
response header, and the template reads it there:

```xml
<ValueToMonitor>
  <DisplayName>Active Incidents Count</DisplayName>
  <Path>$..[?(@.Key=='X-Total-Count')].Value</Path>
  <ThresholdRule>GreaterThan</ThresholdRule>
  <WarningThresholdValue xsi:nil="true" />
  <CriticalThresholdValue xsi:nil="true" />
  <Type>Header</Type>
  <StringToNumberTransformationRules />
  <StringToNumberTransformationOtherValues>0</StringToNumberTransformationOtherValues>
</ValueToMonitor>
```

Two things to take from that expression. `Type` selects **what `Path` is evaluated against**,
not a different path language: the syntax is still JSONPath, and it is applied to the headers
presented as a list of `Key`/`Value` objects. And the filter is a JSONPath filter expression,
`[?(@.Key=='...')]`, which is well past the plain dotted paths the earlier export used. So the
platform's JSONPath implementation supports filters and recursive descent (`$..`), which is
useful to know before writing a path by hand.

The header name is matched exactly, inside single quotes, and HTTP header names are
case-insensitive on the wire. Whether this comparison is too is **not documented and
unverified here**.

This is also the pattern for the common REST idiom of a paged endpoint that reports its total
out of band. ServiceNow's requests ask for `sysparm_limit=1` or `sysparm_limit=10` precisely
because the body is not wanted: the count is in the header, so the smallest page that still
produces headers is the cheapest way to get it.

### `ArrayCount`: the length of an array, not a value in it

The Microsoft 365 template counts mailboxes by counting the elements of the Graph report's
`value` array:

```xml
<ValueToMonitor>
  <DisplayName>All Mailboxes Count</DisplayName>
  <Path>$.['value']</Path>
  <Key>value</Key>
  <ThresholdRule>GreaterThan</ThresholdRule>
  <WarningThresholdValue xsi:nil="true" />
  <CriticalThresholdValue xsi:nil="true" />
  <Type>ArrayCount</Type>
  <StringToNumberTransformationRules />
  <StringToNumberTransformationOtherValues>0</StringToNumberTransformationOtherValues>
</ValueToMonitor>
```

`Path` here points at the array rather than at a scalar inside it, and `Type` is what turns
that into a number. Without this, counting rows means either an endpoint that reports its own
count or a `Header` value like ServiceNow's.

It also answers a limit stated in
[api-poller-unifi-network.md](api-poller-unifi-network.md#what-the-variable-mechanism-cannot-do):
a poller cannot iterate an array, but it can measure one.

## `Key` is in the file and not in the schema

The Microsoft 365 template writes a `<Key>` element on every `ValueToMonitor`, holding the last
path segment: `value` for `$.['value']`, `storageUsedInBytes` for
`$.['value'].[0].['storageUsedInBytes']`.

`Orion.APIPoller.ValueToMonitor` declares no `Key` property. Nor do the Azure or ServiceNow
templates write the element, and neither did the export
[api-pollers.md](api-pollers.md#the-shape) was derived from. So it is an element the
deserialiser accepts and the schema does not persist, which is consistent with .NET's
`XmlSerializer` tolerating a member that was dropped from the class. What it was for, and
whether writing it has any effect, is **not documented and unverified here**; the safe reading
is that it is redundant with `Path` and should be omitted from anything you generate.

## Vendor templates leave the thresholds blank on purpose

Every `ValueToMonitor` in all three templates carries:

```xml
<WarningThresholdValue xsi:nil="true" />
<CriticalThresholdValue xsi:nil="true" />
```

`xsi:nil="true"` on an empty element is how `XmlSerializer` writes a nullable value that is
null, which is why the root declares `xmlns:xsi` at all. The element is present and the value
is absent, and the two are not the same thing.

**This is correct for a template and wrong for a poller.** A template is meant to be assigned
to many targets whose baselines differ, and there is no number that is a sensible warning
level for "Storage Used (Bytes)" across every tenant. So the vendor ships the paths, the
requests and the labels, and the operator supplies the thresholds. The same reasoning is why
[credentials and SSL settings are not in the file either](api-pollers.md#element-by-element-against-the-schema):
a template holds the shape, not the installation.

The consequence to plan for is that **an imported vendor template alerts on nothing until
somebody fills those in.** It polls, it graphs, and it sits at Up regardless of what it reads.
Find them with a query rather than by clicking through each poller:

```sql
SELECT
    v.ApiPollerId,
    v.DisplayName,
    v.Path,
    v.Type,
    v.Metric,
    v.WarningThreshold,
    v.CriticalThreshold
FROM Orion.APIPoller.ValueToMonitor v
WHERE v.WarningThreshold IS NULL OR v.CriticalThreshold IS NULL
ORDER BY v.ApiPollerId, v.DisplayName
```

`PollingInterval` is nil in all three files too, even though each one's `Description` states
an interval in prose: "Data is polled every 2 minutes by default" in Azure's, "Data polled
once per day" in the Microsoft 365 one. So the interval a vendor template documents is not the
interval the file carries, and what the platform uses when the element is nil is **not
documented and unverified here**. Read
`Orion.APIPoller.PollingConfiguration.PollingInterval` after assigning one rather than
trusting the description.

## Parameters in the URL are not request variables

All three templates put `${NAME}` placeholders in their URLs:

```text
https://management.azure.com/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${USERGROUP_ID}/providers/Microsoft.Compute/virtualMachines/${VM_NAME}/providers/microsoft.insights/metrics?...
https://${INSTANCE}.service-now.com/api/now/pa/scorecards?sysparm_limit=1
```

`RequestVariables` is self-closing in every request in all three files. These placeholders are
therefore **not** the request-variable mechanism, which lifts a value out of one response for a
later request. They are values supplied when the template is assigned, which is what
`AssignTemplate` and `CreateApiPollerFromTemplate` take their `configuration` and `parameters`
arrays for.

The two mechanisms share one syntax, which is the trap. `${siteId}` set by an earlier request
and `${INSTANCE}` filled in at assign time look identical in a URL and are resolved by
different things at different times.
[api-poller-unifi-network.md](api-poller-unifi-network.md#chaining-requests-with-variables)
covers the first from a poller built in the console; the vendor templates are the evidence for
the second. Which of `configuration` and `parameters` a placeholder like `${INSTANCE}` is
supplied through remains **not documented and unverified here**, as
[api-pollers.md](api-pollers.md#the-verbs) already says.

## Where these three disagree with the documented format

Reading real vendor output corrects two things the single-export derivation got slightly wrong.

**Empty elements are not always written.** The Microsoft 365 template omits `<Body />`
entirely from all four of its requests, while Azure and ServiceNow write it. So "do not omit
empty elements" in
[api-pollers.md](api-pollers.md#writing-one-by-hand) is good advice for matching what the
serialiser emits, and not a hard requirement of the deserialiser: a template SolarWinds
publishes and supports is missing that element. Write it anyway, because a missing element is
a difference you then have to reason about.

**`Created` and `Updated` are not necessarily high-precision UTC.** The earlier export carried
`2026-08-22T15:00:43.6650422Z`. All three vendor templates carry a date with a zero time and no
zone at all:

```xml
<Created>2021-04-30T00:00:00</Created>
<Updated>2021-04-30T00:00:00</Updated>
```

Which is what a human-authored release date looks like rather than a serialised timestamp. The
format tolerates both, so neither the precision nor the trailing `Z` is load-bearing.

## Why these files are not build-validated

`tools/check_api_poller_templates.py` globs `scripts/api-pollers/*.apipoller.template`,
non-recursively, so the copies in `vendor-examples/` are outside it by construction. Pointing
it at them deliberately is the useful thing to do:

```bash
python3 tools/check_api_poller_templates.py scripts/api-pollers/vendor-examples/*.apipoller.template
```

It reports four problems, all the same problem and all real: one `missing <Body>` per request
in the Microsoft 365 template, which is the omission documented above. The Azure and ServiceNow
files pass unchanged.

Two things the checker does **not** report on them, and both are by design. The nil thresholds
pass, because it checks that the elements are present rather than that they hold values, which
is the right rule for a file format where absent and blank are different. And the
`StringToNumberTransformationOtherValues` of `0` in the ServiceNow and Microsoft 365 templates
passes, because the fallback check only fires when there is at least one
`StringToNumberTransformationRule` for it to be the fallback of. With no rules there is no text
to fall back from, so the value is inert.

The files stay under `vendor-examples/` rather than in the validated set for a plainer reason:
they are SolarWinds' published work kept verbatim as evidence for this page, not samples this
repository maintains. Editing one to satisfy a check would destroy the thing that makes it
worth keeping. [scripts/api-pollers/example-service-status.apipoller.template](../../scripts/api-pollers/example-service-status.apipoller.template)
is the maintained, validated, importable sample.

## See also

- [api-pollers.md](api-pollers.md) for the ten `Orion.APIPoller.*` entities, the six verbs, and the format these three are instances of
- [api-poller-unifi-network.md](api-poller-unifi-network.md) for a poller built and verified first-hand, including the request-variable chain and its limits
- [../../scripts/api-pollers/vendor-examples/](../../scripts/api-pollers/vendor-examples/) for the three files themselves
- [../../scripts/api-pollers/](../../scripts/api-pollers/) for the validated, importable sample
- [../automation/credentials.md](../automation/credentials.md) for the OAuth 2.0 credential rows all three of these templates require
- [../modules/cloud.md](../modules/cloud.md) for the native Azure monitoring the Azure template sits alongside
- [../swis/invoke-verbs.md](../swis/invoke-verbs.md) for passing the `configuration` and `parameters` arrays

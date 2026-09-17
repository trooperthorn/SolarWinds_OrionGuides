# A worked API Poller: the UniFi Network Integration API

[api-pollers.md](api-pollers.md) describes the API Poller subsystem from the schema. This page
describes one poller that works, built and verified against **SolarWinds Platform 2026.4.0**
and **UniFi Network 10.6.106** running on a UniFi OS console, on 2026-09-17. It is here because
the parts of an API Poller the schema cannot describe are exactly the parts that decide whether
a poller works: which authentication mode the builder needs, what a chained request can and
cannot carry, and which JSONPath expression survives a device being added.

Note the platform version. The rest of this repository documents the **2026.2** schema, and the
entity and property names used below are checked against that. Nothing here depends on a
2026.4-only entity, but the console layout described is 2026.4's.

## Why the Integration API and not the legacy one

UniFi has two HTTP interfaces and only one of them is usable from an API Poller.

The legacy interface authenticates with `POST /api/auth/login`, returns a session cookie and a
CSRF token, and expects both on every later call. **An API Poller cannot do this.** Each
request in a poller is independent: `Orion.APIPoller.RequestVariable` carries a value lifted out
of a response body into a later request's URL, header or body, and nothing in the model carries
a `Set-Cookie` into a later request's cookie jar. Attempting the login flow produces a poller
whose first request succeeds and whose second is unauthenticated.

The **Network Integration API** authenticates with a static API key in a request header, which
is stateless and therefore pollable. Everything below uses it.

This is the same wall the Citrix Hypervisor sketch ran into from the other side. See
[../modules/sam-citrix-hypervisor-template.md](../modules/sam-citrix-hypervisor-template.md#the-api-poller-alternative):
that template chains a login into later requests and its handoff has never been confirmed
against a real export. A session-based API is the hard case, and preferring a key-based
interface where the vendor offers one avoids the whole question.

## The credential

The key is created in the UniFi console under **Settings > Control Plane > Integrations**. The
exact menu path moves between UniFi OS releases, so treat that as the 10.6 location rather than
a stable one.

Two properties of the key matter for monitoring design:

- **It is per-admin**, and it inherits that admin's site access. A key made from a
  limited-site admin account sees only those sites, and `/sites` will return fewer rows than a
  console operator expects. Create it from an account whose visibility matches what the poller
  should see, and prefer a dedicated read-only admin over a personal one.
- **It does not appear again.** Copy it into the SolarWinds credential store when it is created.

In SolarWinds, store it as a credential rather than typing it into a header value. A header
value is a plain `System.String` on `Orion.APIPoller.RequestHeader` and shows up in any query
against that entity, which
[api-pollers.md](api-pollers.md#the-request) covers, along with why `CredentialsId` is the
safer column. See [../automation/credentials.md](../automation/credentials.md).

In the API Poller builder:

| Setting | Value |
| --- | --- |
| Authorization type | **API Key** |
| Key name | `X-API-KEY` |
| Choose credential | the credential holding the key, selected explicitly |
| Verify SSL certificate | off, unless the console's certificate is trusted by the SolarWinds server |

**`401 Unauthorized` is almost always one of two mistakes.** UniFi answers a failed request
with `{"code":401,"message":"Unauthorized"}` and nothing more specific, and in practice it
means either that the credential exists but was never selected in the builder's "Choose
credential" dropdown, or that Authorization was left at the builder's Basic default. UniFi
rejects Basic outright. Both leave a poller that looks configured.

SSL verification is per request rather than per poller, so a console with a self-signed
certificate means turning it off on every request in the chain rather than once. That is also
how a poller ends up not verifying a certificate it could have verified, and
[api-pollers.md](api-pollers.md#the-request) has the query that finds those.

## The base path depends on how Network is deployed

On a **UniFi OS console** (UDM, UCG, UNVR, Cloud Key Gen2 and later) the Network application
sits behind UniFi OS's reverse proxy, and every Integration API URL is prefixed
`/proxy/network`:

```text
https://<console>/proxy/network/integration/v1
```

That is the form verified here. Ubiquiti's documentation indicates that a **self-hosted Network
application** (the Docker image or the Debian package) serves the API without that prefix, at
`https://<host>:8443/integration/v1`. **That second form is unverified here**: no self-hosted
controller was available to test against. Confirm it with a single `GET` to `/integration/v1/info`
before building a poller around it.

## The endpoints

Four were exercised, all `GET`:

| Path | Returns |
| --- | --- |
| `/info` | `applicationVersion`, the Network application's version |
| `/sites` | Paged. Each site's `id` (a UUID), `internalReference`, `name` |
| `/sites/{siteId}/devices` | Paged. Adopted devices with their identity, model and state |
| `/sites/{siteId}/devices/{deviceId}/statistics/latest` | Live counters for one device |

Two more are documented by Ubiquiti and were **not exercised here**, so what they return is
unverified in this repository: `/sites/{siteId}/clients`, and
`/sites/{siteId}/devices/{deviceId}` for full single-device detail.

### Everything is addressed by UUID

The Integration API identifies sites and devices by UUID. The legacy short site name that
appears throughout the old API and in console URLs, typically `default`, appears here only as
`internalReference` on the site record, and is not accepted in a path.

**So `/sites` is always the first call against a controller you have not polled before.** There
is no way to construct or guess a site UUID, and the same is true of a device UUID. This is the
constraint that makes the poller a chain rather than three independent requests.

### The paged envelope, and the paging the poller will not do

`/sites` and `/devices` wrap their results:

```json
{
  "offset": 0,
  "limit": 25,
  "count": 6,
  "totalCount": 6,
  "data": [ { "id": "…", "internalReference": "default", "name": "Default" } ]
}
```

`count` is the rows in this response and `totalCount` is the rows available. **The poller does
not follow paging.** It issues the request it is given and reads the response it gets, so a
site with more devices than the default `limit` of 25 silently returns the first 25 and a
`count` of 25. Pass the page explicitly when that is possible:

```text
/sites/{siteId}/devices?limit=200
```

And monitor `totalCount` rather than `count` if what you want is "how many devices does this
site have", because `count` stops being that answer at exactly the point it starts to matter.

### Device list fields

Each element of `data` from `/devices` carries `id`, `macAddress`, `ipAddress`, `name`,
`model`, `state`, `supported`, `firmwareVersion`, `firmwareUpdatable`, `features` and
`interfaces`. `state` was observed as `ONLINE` and `OFFLINE`; whether other values exist is
unverified here.

On the console tested, the gateway was `data[0]`. **Ubiquiti documents no ordering for this
array**, so that is an observation and not a contract. It is also the single most fragile thing
about the poller below, and the section on variable limits says what to do about it.

### The gateway statistics

`/statistics/latest` for a gateway returned `uptimeSec`, `lastHeartbeatAt`, `nextHeartbeatAt`,
`loadAverage1Min`, `loadAverage5Min`, `loadAverage15Min`, `cpuUtilizationPct`,
`memoryUtilizationPct`, an `uplink` object with `txRateBps` and `rxRateBps`, and an
`interfaces` object. The set is device-class dependent, so read it from the device you intend to
poll rather than assuming a switch or an access point answers with the same fields.

## Chaining requests with variables

The builder's value picker, reached from "Configure a value to monitor" on any field in a test
response, offers two things to do with that field, and the distinction is the whole design:

| Choice | What it becomes | Cost |
| --- | --- | --- |
| **New monitored value** | An `Orion.APIPoller.ValueToMonitor`: a time series with thresholds, history, and a status | Consumes a monitored-element licence |
| **Use as a variable in subsequent request** | An `Orion.APIPoller.RequestVariable`: held in memory for this poll only, referenced as `${name}` | None |

A variable is not stored, not graphed and not licensed. It exists so that a later request can be
addressed by something only an earlier response knows, which for this API is every UUID in
every URL.

### The verified three-request template

| Order | Request | Reads |
| --- | --- | --- |
| 0 | `GET <base>/sites` | variable `siteId` from `data[0].id` |
| 1 | `GET <base>/sites/${siteId}/devices` | monitored value **UniFi Device Count** from `count`; variable `gatewayId` from `data[0].id` |
| 2 | `GET <base>/sites/${siteId}/devices/${gatewayId}/statistics/latest` | monitored values below |

The three metrics on the last request:

| Metric | Path | Warning | Critical |
| --- | --- | --- | --- |
| Gateway CPU | `cpuUtilizationPct` | 80 | 90 |
| Gateway memory | `memoryUtilizationPct` | 85 | 95 |
| Gateway uptime | `uptimeSec` | 600 | |

`uptimeSec` is the one that reads oddly and is worth keeping. Thresholded so that a **low**
value alerts, it reports a reboot: an uptime under 600 seconds means the gateway restarted
within the last ten minutes. Whether the comparison direction is available as a
`ThresholdRule` other than `GreaterThan`, which is the only value seen in an export anywhere in
this repository, is
[unverified here](api-pollers.md#the-threshold-boundary). Check what the builder's dropdown
offers on your own version before relying on a low-side threshold.

Note that request 1 does both jobs: `count` is licensed and graphed, `data[0].id` is not. One
response can feed both mechanisms at once.

### Working in the builder

- **Testing a later request re-runs the earlier ones.** The builder resolves `${siteId}` by
  actually issuing request 0, so the whole chain can be tested before the poller is saved.
  There is no need to save a half-built poller to find out whether the substitution works.
- **Order is changed from the kebab menu** on each request's header: Duplicate, Move up, Move
  down, Delete. Order is what
  `Orion.APIPoller.RequestDetails.RequestDetailsOrder` records, and it is what decides which
  variables a request can see.
- **Duplicate copies the stored values too.** Duplicating request 2 to poll a second device
  gives you a request with the first device's monitored values attached, and the URL still
  pointing at the first device. Remove the copied values before repointing the URL, or you get
  two metrics with the same label reading the same device.

### Moving this poller to another controller

Only two things change: the host in each of the three URLs, and the credential. Every site and
device UUID is resolved at poll time by request 0 and request 1, so nothing controller-specific
is embedded in the template. That is the practical payoff of chaining, and it is worth
accepting the fragility below to get it.

## What the variable mechanism cannot do

These are the rules that decide whether a given monitoring idea is buildable as an API Poller
at all, and each one is a thing that was tried.

- **Substitution is literal text replacement.** There is no arithmetic, no concatenation and no
  conditional. `${a}+${b}` in a URL is sent as the three characters between two substituted
  values, not as a sum.
- **A variable holds one scalar.** An array or an object cannot be stored in one. So polling
  statistics for N devices means N explicit requests, each with its own variable read from its
  own `data[N].id`, and each request costing its own metrics. There is no loop.
- **A variable is visible only below the request that sets it.** Reorder the requests and a
  substitution that used to resolve now does not.
- **Array index paths are positional, not stable.** `data[0].id` is whichever device the
  controller listed first on this poll. Adopt a device, remove one, or hit an ordering the
  vendor never promised, and the same path now names a different device, with the metric
  continuing to report under the old label. For anything alertable, prefer a request whose URL
  embeds the device UUID literally, accepting that the template is then controller-specific.
  Ubiquiti documents a `filter` query parameter on the collection endpoints that should let
  `data[0]` be pinned to a known model or name; **that is unverified here**, and is the first
  thing to test if you need both stability and portability.
- **Text has to be mapped before it can be thresholded.** `state` returns `ONLINE`, so it is
  not thresholdable as it stands. It becomes monitorable through the string-to-number
  mapping, `ONLINE` to `1` and everything else to the fallback, which is
  `Orion.APIPoller.StringToNumberTransformationRule` and the pipeline described in
  [api-pollers.md](api-pollers.md#how-a-polled-value-becomes-a-status). Put the fallback above
  critical, for the reason that page gives: a firmware release that starts answering
  `CONNECTED` should alert rather than read as healthy.
- **Nothing is computed in the poller.** "Percent of devices online", or the delta between two
  counters, cannot be expressed here. Those are downstream work: a
  [custom query widget](../webui/custom-query-widget.md) over the stored values, or a SAM
  script component that reads them and publishes a derived statistic. The poller's job ends at
  one number per `ValueToMonitor`.

## Reading what the poller collected

The poller's own rows, once it exists:

```sql
SELECT
    p.Name,
    p.Status,
    p.StatusDescription,
    p.LastPollTimestamp,
    p.Node.Caption
FROM Orion.APIPoller.ApiPoller p
WHERE p.Node.Caption LIKE '%unifi%'
```

The chain of requests, in the order they run, which is the quickest way to confirm the
substitution survived an import:

```sql
SELECT
    r.RequestDetailsOrder,
    r.HttpVerb,
    r.Url,
    r.CredentialsType,
    r.VerifySslCertificate
FROM Orion.APIPoller.RequestDetails r
WHERE r.ApiPoller.Name LIKE '%UniFi%'
ORDER BY r.RequestDetailsOrder
```

The variables, which are the rows that do not appear anywhere in the web console's metric
lists:

```sql
SELECT
    v.RequestDetailsId,
    v.DisplayName,
    v.Path
FROM Orion.APIPoller.RequestVariable v
WHERE v.RequestDetails.ApiPoller.Name LIKE '%UniFi%'
ORDER BY v.RequestDetailsId
```

The metrics with their last reading:

```sql
SELECT
    v.DisplayName,
    v.Path,
    v.Type,
    v.Metric,
    v.Status,
    v.WarningThreshold,
    v.CriticalThreshold
FROM Orion.APIPoller.ValueToMonitor v
WHERE v.ApiPoller.Name LIKE '%UniFi%'
ORDER BY v.DisplayName
```

### A note on where these values live

There is no `Orion.APIPoller.Value` entity, and there is no `Orion.APIPoller.ValueHistory`
entity either, although both are plausible names for the current and historical readings and
both get proposed. The real entities are
`Orion.APIPoller.ValueToMonitor` for the metric with its last reading in `Metric`, and
`Orion.APIPoller.ValueToMonitor.Metrics` for the min, max and average per observation.
[api-pollers.md](api-pollers.md#history) documents both, checked against the extracted schema.

That is worth stating explicitly rather than quietly using the right names, because the wrong
pair is the exact failure mode
[AGENTS.md](../../AGENTS.md#the-one-rule) describes: a name that looks right, is not in the
schema, and fails on a live server. Confirm either way in one command:

```bash
python3 tools/schema_query.py find api poller value --properties
```

History is a statistics table and grows with every poll, so window it:

```sql
SELECT
    m.ValueToMonitorId,
    m.ObservationTimestamp,
    m.AvgMetric,
    m.MaxMetric
FROM Orion.APIPoller.ValueToMonitor.Metrics m
WHERE m.ObservationTimestamp > AddHour(-24, GetDate())
ORDER BY m.ObservationTimestamp DESC
```

## Exporting it

Once the poller works, export it and keep the file, because the export is the only artefact
that survives a rebuild:

```powershell
$swis = Connect-Swis -Hostname orion.example.com -Trusted

$pollerId = Get-SwisData $swis @'
SELECT p.ID FROM Orion.APIPoller.ApiPoller p WHERE p.Name = @name
'@ @{ name = 'UniFi Network Integration' }

$export = Invoke-SwisVerb $swis 'Orion.APIPoller.ApiPoller' 'ExportTemplateFromApiPoller' @($pollerId)
$export.InnerText | Out-File -FilePath '.\unifi-network.apipoller.template' -Encoding utf8
```

The credential does not travel with it and neither do the SSL, proxy and timeout settings, so
the file is a shape rather than a working poller. See
[api-pollers.md](api-pollers.md#moving-a-poller-between-servers).

No such export is checked into this repository yet. Doing so would settle the remaining
question about the request-variable format: whether `${name}` is what the exported XML writes
into a `Url`, or whether the builder's syntax is rendered differently in the file. Until an
export is read, **the file-level representation of the substitution is unverified here**, which
is the same gap the Citrix sketch is blocked on.

## What is unverified here

Collected, because this page asserts a lot from one installation:

- The self-hosted Network application serving the API without the `/proxy/network` prefix.
- `/sites/{siteId}/clients` and the single-device detail endpoint, neither exercised.
- The `filter` query parameter, which is the documented fix for positional array paths.
- Whether an API key survives a Network application upgrade. It worked across the 10.6.x builds
  seen here, which is one data point and not a guarantee.
- Whether `data[0]` is reliably the gateway. It was on the console tested, and Ubiquiti
  documents no ordering.
- What the exported template writes for a request variable.

## Why build a multi-metric poller against a public API at all

The same three-request shape works anywhere a vendor or a public service publishes JSON and an
identifier has to be discovered before it can be used, and it is often the cheaper answer than
an intermediary. A public Datadog dashboard tracking the ERCOT grid, for example, is assembled
from ERCOT's own public pages: system conditions, settlement point prices, and a JSON weather
API. The pages that answer JSON are directly pollable here, with a
[`Header` or `ArrayCount` value](api-poller-vendor-templates.md#three-type-values-from-real-exports)
where the number wanted is a count rather than a field, and the ones that answer HTML need a SAM
script component instead. Reaching the source removes a dependency rather than adding one.

## See also

- [api-pollers.md](api-pollers.md) for the entity model, the six verbs, and the `.apipoller.template` format
- [api-poller-vendor-templates.md](api-poller-vendor-templates.md) for the three `ValueToMonitor` `Type` values, read off SolarWinds' own shipped templates
- [../modules/sam-citrix-hypervisor-template.md](../modules/sam-citrix-hypervisor-template.md#the-api-poller-alternative) for the session-based API this one deliberately avoids
- [../automation/credentials.md](../automation/credentials.md) for the credential store the API key belongs in
- [../webui/custom-query-widget.md](../webui/custom-query-widget.md) for computing the derived figures the poller cannot
- [../swql/performance.md](../swql/performance.md) for windowing the metrics history
- [../swql/date-and-time.md](../swql/date-and-time.md) for why `AddHour(-24, GetDate())` and not `GetUtcDate()`

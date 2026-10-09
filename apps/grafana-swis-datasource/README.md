# SolarWinds SWIS data source for Grafana

A native Grafana data source plugin for SolarWinds Observability Self-Hosted (Orion). You
type SWQL in the panel editor, Grafana's time range and dashboard variables are applied
for you, the result comes back as a typed data frame, and verbs can be invoked from a
dashboard through an allowlist the administrator controls. It works the same on Grafana
OSS and Grafana Enterprise, because it uses nothing beyond the open plugin SDK.

```text
Grafana (any panel, alert rule, or variable)
   │  SWQL + time range           Grafana's plugin protocol (gRPC, local)
   ▼
gpx_swis  (this plugin's backend, a Go process Grafana starts)
   │  POST /Query with bound parameters      HTTPS, port 17774
   │  POST /Invoke/{Entity}/{Verb}           only for allowlisted verbs
   ▼
SWIS on the SolarWinds Platform server
```

The Orion credential lives in Grafana's encrypted secure settings and only the backend
process ever sees it. Nothing runs between Grafana and SWIS.

## What you get

| Feature | How |
| --- | --- |
| SWQL query editor with syntax highlighting | The panel editor is a code editor; Ctrl+S or leaving the editor runs the query |
| Time range applied to the query | `$__timeFilter(alias.Column)`, `$__timeFrom()` and `$__timeTo()` expand to **bound parameters**, so the range never becomes literal text. `$__timeFilter` is a half-open window, `>=` and `<` |
| Dashboard variables | `$node`, `${node}`, `[[node]]` become **bound parameters** (`@node`), and `IN (${ifaces:csv})` becomes `IN @ifaces` with an array. `${var:raw}` is the one explicit text-substitution escape hatch |
| Variables driven by SWQL | A variable's query is a SWQL statement; alias the label `__text` and the value `__value` |
| Table and time series formats | Table returns rows as-is. Time series needs a `DateTime` column; string columns become series labels, one series per distinct value |
| Typed columns | Numbers, booleans, timestamps and strings come back as their own field types, in SELECT-list order, with SWIS's zoneless timestamps read on the data source's [time basis](#server-time-basis) (UTC unless you change it) |
| Alerting | Grafana alert rules can be built on any query, because the plugin is a backend data source |
| Health check | "Save & test" runs one query against `Orion.Engines` and reports the polling engine's server name and its `EngineVersion`, which is an engine version, not the platform release |
| Invoke | `POST /api/datasources/uid/<uid>/resources/invoke/<Entity>/<Verb>` with a positional JSON array, gated three ways (below) |
| Example queries | The editor offers ten starting points; every one is validated against the extracted 2026.2 schema on each build of this repository |
| Sample dashboard | [dashboards/solarwinds-overview.json](dashboards/solarwinds-overview.json): status, down nodes, alerts, alert rate, fullest volumes, and per-node CPU, latency and interface traffic |

## Install

The plugin is not in the Grafana catalogue and is not signed. Both Grafana OSS and
Enterprise load an unsigned plugin only when its id is listed in the
`allow_loading_unsigned_plugins` setting. That is the one configuration step that differs
from a catalogue plugin, and it is the same on both editions.

### 1. Build

Needs Go 1.26.5 or newer (`go.mod` states it) and Node. CI builds with Node 24, the
version in `.nvmrc`; `package.json` declares `>=22` as the minimum, and only 24 is
exercised. From this directory:

```bash
go test ./pkg/...
npm ci
npm run build
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o dist/gpx_swis_linux_amd64 ./pkg
```

or, from the repository root, `make grafana-plugin`. The result is `dist/`: `plugin.json`,
`module.js`, the logo and the backend binary. Build the binary for the platform Grafana
runs on; the name pattern is `gpx_swis_<os>_<arch>`, so a Windows host wants
`GOOS=windows GOARCH=amd64 go build -o dist/gpx_swis_windows_amd64.exe ./pkg`, and an ARM
Linux host wants `GOARCH=arm64`. Grafana picks the binary that matches its own platform.

### 2. Put it where Grafana looks

Copy `dist/` to `<plugins directory>/trooperthorn-swis-datasource/`. The plugins directory
is `/var/lib/grafana/plugins` on the packaged builds and in the official container.

### 3. Allow it to load

Configuration file (`grafana.ini` or `/etc/grafana/grafana.ini`):

```ini
[plugins]
allow_loading_unsigned_plugins = trooperthorn-swis-datasource
```

Container:

```bash
docker run -d -p 3000:3000 \
  -v "$PWD/dist:/var/lib/grafana/plugins/trooperthorn-swis-datasource" \
  -e GF_PLUGINS_ALLOW_LOADING_UNSIGNED_PLUGINS=trooperthorn-swis-datasource \
  grafana/grafana
```

`grafana/grafana` is the OSS image. `grafana/grafana-enterprise` takes the same flag and
the same volume. Restart Grafana after either change; it lists the plugin under
Administration, Plugins and data, as "SolarWinds SWIS".

If you would rather not carry the unsigned-plugin setting, Grafana's
[private plugin signing](https://grafana.com/developers/plugin-tools/publish-a-plugin/sign-a-plugin)
signs a plugin for the root URLs you name. It needs a Grafana Cloud account for the
signing key, but the signed plugin then loads on any OSS or Enterprise instance whose
root URL matches. `npm run sign` in this directory runs it.

### Home Assistant

[trooperthorn/ha_app_grafana](https://github.com/trooperthorn/ha_app_grafana) ships this
plugin inside a hardened Grafana for Home Assistant, built from a pinned commit of this
repository, with no unsigned-plugin setting to manage.

## Configure the data source

Connections, Data sources, Add data source, "SolarWinds SWIS".

| Field | Notes |
| --- | --- |
| Orion server | Hostname or IP, nothing else |
| REST port | 17774 from platform release 2023.1 onward. 17778 is the legacy REST port: deprecated in 2023.1, it stops listening by default in 2024.2 ([connecting.md](../../docs/swis/connecting.md#endpoints-and-ports)). 17777 is SOAP and will not answer |
| Username, Password | An Orion account. Give Grafana its own read-only account with the narrowest limitation that still shows what the dashboards need; account limitations apply to everything it reads |
| CA certificate | SWIS ships with a self-signed certificate. Paste that certificate (or the CA that issued it) here and verification stays on. `openssl s_client -connect orion.example.com:17774 -showcerts </dev/null` prints it |
| Ignore certificate name | Needed when the pinned certificate's names do not cover the host you entered, see below. The chain is still verified against the pasted certificate; only the name check is dropped |
| Skip TLS verification | Lab only. It lets anything on the network path read the credentials Grafana sends |
| Max rows per query | Rows beyond this are dropped and the panel shows a warning. Default 10000. It is a safety net, not a substitute for `TOP n` |
| Timeout | Seconds per request. Default 60 |
| Allowed verbs | One `Entity.Verb` per line. Empty means Invoke is off, which is the default |
| Server time basis | UTC (the default) or server local, with an IANA zone name or a fixed UTC offset in minutes. Read [Server time basis](#server-time-basis) before changing it |

### The self-signed certificate

SWIS presents a self-signed certificate by default
([connecting.md](../../docs/swis/connecting.md#tls-and-the-self-signed-certificate)).
Pasting it into the CA field may not be enough on its own, and the reason is worth
knowing because it looks like the pin is being ignored. A verifier that trusts the
certificate still makes the second check every TLS client makes: that a name on the
certificate matches the host it was asked to connect to. Go, which this backend is written
in, checks only subject alternative names and ignores the common name, so a certificate
with no subject alternative name for that host fails the check whatever its common name
says.

**Unverified:** which names the certificate SWIS generates carries. Nothing in
OrionGuides documents its subject or subject alternative names, so whether the name check
fails against your server is something to look at rather than assume. After exporting it
as [connecting.md](../../docs/swis/connecting.md#tls-and-the-self-signed-certificate)
shows, `openssl x509 -in orion-swis.pem -noout -subject -ext subjectAltName` prints both.
If the host you enter in the data source is not among the subject alternative names, the
name check fails.

So there are three settings, and they are not the same:

| Setting | Chain checked | Name checked | Refuses a different certificate on the same host |
| --- | --- | --- | --- |
| CA certificate only | Yes | Yes | Yes. Fails when the certificate's names do not cover the host |
| CA certificate + Ignore certificate name | Yes | No | **Yes** |
| Skip TLS verification | No | No | No |

The middle row is certificate pinning, and it is what a certificate whose names do not
match needs. It is
not "verification off": the server has to present the exact certificate you pasted (or
one issued by it), so an interception between Grafana and the Orion server, which is the
host holding credentials for the rest of the estate, still fails loudly. Turn on the
third row only in a lab. The same ordering, and the OpenSSL commands to export and
fingerprint the certificate before trusting it, are in
[connecting.md](../../docs/swis/connecting.md#tls-and-the-self-signed-certificate).

If the health check fails on the name with the pin in place, the message says which
switch to turn on. If it fails with "not the pinned one", the server is presenting a
different certificate from the one you pasted: either it was replaced, or something is in
the path.

"Save & test" runs
`SELECT TOP 1 e.EngineID, e.ServerName, e.EngineVersion FROM Orion.Engines e ORDER BY e.EngineID`
and shows the server name and `EngineVersion` it found. That is the polling engine's
version, which is numbered separately from the platform release; `Orion.InstalledModule`
lists the installed modules and their versions
([versions-and-naming.md](../../docs/platform/versions-and-naming.md#finding-out-what-you-actually-have)).
If it authenticates but sees no engine, the message says so and points at the account
limitation, because that is the usual cause.

### Server time basis

SWIS returns `System.DateTime` values without a zone designator, and the schema does not
say which clock they are on. `System.DateTime` alone does not declare UTC
([date-and-time.md](../../docs/swql/date-and-time.md#which-columns-are-utc-and-which-are-local)).
A practitioner reports that most platform timestamps are UTC, and that is the working
hypothesis this plugin defaults to, not a documented property. The setting decides two
things together, so a window and the timestamps it returns stay on one clock:

| Setting | `$__timeFrom` and `$__timeTo` are bound as | A zoneless result timestamp is read as |
| --- | --- | --- |
| UTC (default) | ISO 8601 in UTC with `Z`, `2026-09-15T08:00:00Z` | UTC |
| Server local | Wall-clock time in the server's zone, no designator, `2026-09-15T03:00:00` | Time in the server's zone |

For server local, give an IANA zone name (`America/Chicago`), which follows daylight
saving, or leave it empty and give a fixed offset in minutes east of UTC (`-300` for
UTC-05:00), which does not. A timestamp that carries its own designator keeps its own
offset either way.

**Unverified:**

- The time basis of the columns you query. `Orion.CPULoad.DateTime`, like most
  `DateTime` columns, carries no statement either way; `Orion.Events.EventTime` is documented
  as displayed in local time, which may describe presentation rather than what a query
  returns ([the EventTime exception](../../docs/swql/date-and-time.md#the-eventtime-exception));
  `Orion.AlertHistory.TimeStamp` has no documented timezone. Measure a column before
  trusting a window on it, with the `MinuteDiff` probe in
  [Measuring a column's timezone](../../docs/swql/date-and-time.md#measuring-a-columns-timezone).
- How SWIS parses either bound form. OrionGuides records ISO 8601 acceptance by SWIS as
  unverified, and documents that a zoneless `DateTime` literal is read on the SQL Server's
  clock; neither statement is about a bound parameter
  ([DateTime literals and parameters](../../docs/swql/date-and-time.md#datetime-literals-and-parameters)).
  A window that is off by exactly the server's UTC offset is the symptom to look for.

The setting applies to every query on the data source. A server whose columns are on
different clocks (a `...Utc` column next to a local one) needs `ToUtc` or `ToLocal` in the
query, or two data sources with different settings. The default is unchanged from 1.0.0.

### Provisioning

For a Grafana that is configured from files, the same settings go in a provisioning file.
Values are read from Grafana's environment so nothing real is committed:

```yaml
apiVersion: 1
datasources:
  - name: SolarWinds SWIS
    uid: swis
    type: trooperthorn-swis-datasource
    access: proxy
    jsonData:
      host: ${SWIS_HOST}
      port: 17774
      username: ${SWIS_USER}
      tlsSkipVerify: false
      tlsIgnoreHostname: true
      maxRows: 10000
      timeoutSeconds: 60
      timeBasis: utc            # or serverLocal, with serverTimeZone or serverUtcOffsetMinutes
      invokeAllow:
        - Orion.Nodes.PollNow
    secureJsonData:
      password: ${SWIS_PASSWORD}
      caCert: ${SWIS_CACERT_PEM}
```

The sample dashboard expects the data source uid `swis`; import it through Dashboards,
New, Import, or provision the `dashboards/` directory the way
[provisioning/README.md](provisioning/README.md) shows.

## Writing queries

Everything in [the SWQL guides](../../docs/swql/README.md) applies. Three things are specific
to Grafana.

**Bound the query.** Statistics and history entities (`Orion.CPULoad`,
`Orion.ResponseTime`, `Orion.NPM.InterfaceTraffic`, `Orion.AlertHistory`, `Orion.Events`)
are the largest tables on the server, and a dashboard refreshes every panel on a timer.
Keep `TOP n` and `$__timeFilter(...)` on every query against them.

```sql
SELECT TOP 10000
    c.DateTime,
    c.AvgLoad,
    c.AvgPercentMemoryUsed
FROM Orion.CPULoad c
WHERE c.NodeID = ${node}
  AND $__timeFilter(c.DateTime)
ORDER BY c.DateTime
```

The plugin sends SWIS this. The frontend rewrites `${node}` to `@node` and binds the
variable's value; the backend binds `@__timeFrom` and `@__timeTo` on the data source's
time basis, as UTC ISO 8601 strings by default:

```sql
SELECT TOP 10000
    c.DateTime,
    c.AvgLoad,
    c.AvgPercentMemoryUsed
FROM Orion.CPULoad c
WHERE c.NodeID = @node
  AND c.DateTime >= @__timeFrom AND c.DateTime < @__timeTo
ORDER BY c.DateTime
```

```json
{"node": 42, "__timeFrom": "2026-09-15T08:00:00Z", "__timeTo": "2026-09-16T08:00:00Z"}
```

The window is half open, `>=` and `<`, so consecutive windows neither double count nor drop
a row on the boundary
([the checklist](../../docs/swql/date-and-time.md#a-checklist-before-you-save-a-time-bounded-query)).
**Unverified:** that SWIS accepts the ISO 8601 string form for a bound `DateTime`, and
which clock `Orion.CPULoad.DateTime` is on. The UTC default is a working hypothesis; see
[Server time basis](#server-time-basis) for what the documentation does and does not
establish, and for the setting that changes it.

**One series per label.** For the time series format, every string column in the SELECT
list becomes a label, and each distinct combination becomes its own series. This query
draws one line per interface on the node:

```sql
SELECT TOP 10000
    t.DateTime,
    t.Interface.FullName AS Interface,
    t.InAveragebps,
    t.OutAveragebps
FROM Orion.NPM.InterfaceTraffic t
WHERE t.NodeID = ${node}
  AND $__timeFilter(t.DateTime)
ORDER BY t.DateTime
```

**Variables.** A dashboard variable of type Query, using this data source, runs a SWQL
statement. Alias the label `__text` and the value `__value`:

```sql
SELECT TOP 5000
    n.Caption AS __text,
    n.NodeID AS __value
FROM Orion.Nodes n
ORDER BY n.Caption
```

A dashboard variable referenced in a statement is **bound, not pasted**. OrionGuides asks
every integration to bind its values
([building-integrations.md, section 5](../../docs/guides/building-integrations.md#5-bind-every-parameter-every-time)),
and a node caption such as `O'Brien-DC1` is then data rather than a syntax error. The
rules:

- `$node`, `${node}`, `${node:format}` and `[[node]]` all become `@node`, and the
  variable's current value is sent as the parameter `node`. A variable name that SWQL
  cannot take as a parameter name is adjusted (a leading digit gets a `_` prefix).
- A multi-value variable goes in an `IN` list as `IN $nodes` or `IN (${nodes:csv})`, in
  any of the syntaxes above, provided it is the whole list. Either becomes `IN @nodes`
  with the selected values as an array, even when one is selected; the
  parentheses are dropped, because the documented form is `IN @ids`
  ([rest-api.md](../../docs/swis/rest-api.md#multi-valued-parameters-for-in-clauses)).
  Selecting All binds every value; a custom All value is bound as one string, so leave it
  unset on a variable used this way.
- An unquoted value that is a plain decimal number (`42`, not `007`) is bound as a number,
  matching the numeric literal text substitution used to produce. A reference written as
  the whole of a string literal, `'${caption}'`, or with `:singlequote`, `:doublequote` or
  `:sqlstring`, is bound as a string. **Unverified:** how SWIS compares a bound string with
  a numeric column, or a number with a string column; keep the quoting that matches the
  column's type.
- A reference inside a longer string literal (`'%$name%'`) or a `--` comment is left as
  written. Put the wildcards in the variable's value and compare with `LIKE @name`.
- `${var:raw}` (or `[[var:raw]]`) is **text substitution**, kept for positions SWQL does
  not take a parameter in, such as an entity or column name. Whatever the variable holds
  becomes part of the statement, so use it only with a variable whose values you control
  (a Custom variable, not one a viewer can type into).
- Names starting with `__` are never bound. The three time macros above are expanded by
  the backend. Grafana's numeric built-ins `$__interval_ms`, `$__range_s` and
  `$__range_ms` (written `$__x` or `${__x}`) are substituted as text, and only when the
  value Grafana supplies is all digits, so the statement can only gain an integer
  literal. Every other built-in (`$__interval`, which renders like
  `1m`, `$__user.login`, `$__dashboard`, and the `[[...]]` or formatted forms of the
  numeric ones) is left as written, and the backend refuses it with an error naming what
  is supported.

Parameter names starting with `__` are reserved for the time macros, and the backend
refuses a query that sets one, so a variable can never replace the bound time range.

## Invoking verbs from a dashboard

Reading is safe. Invoking changes the monitored estate, so the plugin gates it three
times, and all three have to pass:

1. **The allowlist.** Only an `Entity.Verb` written into the data source settings can be
   called. The default is an empty list, which refuses everything, including for admins.
2. **The Grafana role.** The caller must be an Editor or Admin in the Grafana
   organisation. Viewers get 403. The role comes from Grafana's own session, not from the
   request.
3. **The Orion account.** SWIS still enforces the right the verb requires (`manageNodes`
   for `PollNow`, `allowUnmanage` for `Unmanage`, `clearEvents` for `Acknowledge`), so the
   Grafana service account needs that right too. If you want a read-only Grafana, do not
   grant it, and the allowlist becomes a second lock rather than the only one.

Every invocation is written to Grafana's server log with the Grafana user, the verb and
the arguments, so a change made from a dashboard is as traceable as one made from
PowerShell.

The call is an HTTP POST to the data source's resource endpoint with a **positional** JSON
array. Names appear in documentation but never on the wire; the order is the whole
contract, so look it up first:

```bash
python3 tools/schema_query.py verb Orion.Nodes PollNow
```

```bash
curl -sS -X POST "https://grafana.example.com/api/datasources/uid/swis/resources/invoke/Orion.Nodes/PollNow" \
  -H "Authorization: Bearer $GRAFANA_SERVICE_ACCOUNT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '["N:42"]'
```

```json
{"invoked": "Orion.Nodes.PollNow", "result": null}
```

`GET .../resources/verbs` returns the allowlist, so a panel can find out what it may offer.

From a panel, the plugin's `DataSource.invoke(entity, verb, args)` method does the same
call through Grafana's own HTTP client. Grafana ships no button panel; the community
"Business Forms" and "Button" panels can POST to a data source resource and are the usual
way to put an acknowledge or poll-now button on a dashboard. Their configuration is
theirs, not this plugin's, and was not exercised here.

An acknowledge button is the common case. The active-alerts example selects
`AlertObjectID` for exactly this reason: it is what `Orion.AlertActive.Acknowledge` takes,
as an array, followed by the note:

```json
["Orion.AlertActive", "Acknowledge", [[12345], "Acknowledged from Grafana"]]
```

## What was verified, and what was not

Verified here, on every build of this repository:

- Every SWQL statement in [src/examples.ts](src/examples.ts) and in the sample dashboard
  resolves against the extracted 2026.2 schema (`make validate` reads both, rewriting
  the Grafana macros the way the backend does first).
- The backend's Go tests run it against a stub SWIS over TLS with a self-signed
  certificate: macro expansion, the half-open window and refusal of malformed macros,
  binding of the time range on both time bases (UTC, and server local by fixed offset and
  by IANA zone), parsing zoneless timestamps on both, refusal of reserved parameter names,
  column typing and order, row truncation, the long-to-wide pivot for time series, SWIS
  error messages reaching the panel, the health check's three outcomes, TLS verification
  staying on by default, certificate pinning against a self-signed certificate with a
  fixed name and no subject alternative names with the name check off and a different
  certificate still refused, and the invoke gates.
- The frontend's jest tests cover the variable binding: every reference syntax, `IN`
  lists, string and number typing, `:raw`, comments, string literals, and name
  collisions.
- The frontend typechecks, lints and bundles with Grafana's own build configuration.

Not verified here, because this repository's build environment has no Grafana:

- The plugin loading and rendering in a live Grafana. The code uses the plugin SDK the
  way Grafana's `create-plugin` scaffold does, and the SDK versions pinned in `go.mod` and
  `package.json` are the ones that scaffold produced, but nobody has clicked "Save & test"
  on this build yet. `docker compose up` in this directory starts a development Grafana
  OSS with the plugin mounted and provisioned from the `SWIS_*` environment variables, and
  is the fastest way to do that.
- The minimum Grafana version. The frontend builds against the `@grafana/*` 13.1.0
  packages and `docker compose up` runs Grafana 13.1.0; that is the only build and
  development target. `plugin.json` declares 11.0.0 because every frontend component and
  SDK call used here existed by then, but that is a reading of the changelogs, not a test:
  11.x and 12.x are untested.
- How SWIS treats the bound values: the ISO 8601 and zoneless time strings, a string bound
  against a numeric column, and an array bound to `IN @name` from this plugin.
- Anything about a specific SWIS installation: which entities are present, what the
  service account can see, which clock its `DateTime` columns are on, and which names its
  certificate carries.

## Development

Release notes are in [CHANGELOG.md](CHANGELOG.md).

```bash
npm run dev          # rebuild the frontend on change
npm run test:ci      # frontend tests (variable binding)
go test ./pkg/...    # backend tests
docker compose up    # Grafana OSS 13.1.0 on :3000 with the plugin mounted (needs SWIS_* set)
```

`.config/` is Grafana's generated build configuration and is updated by
`npx @grafana/create-plugin@latest update`, not by hand. One consequence: its
`Dockerfile` still sets `GO_VERSION=1.21.6`, older than the Go 1.26.5 that `go.mod`
requires. It matters only when the development image is built with `DEVELOPMENT=true`,
which installs that Go inside the container; the default `docker compose up` mounts the
`dist/` you built on the host and is unaffected. Until the scaffold is updated, build the
development image with `docker compose build --build-arg GO_VERSION=1.26.5`.

## Layout

```text
pkg/main.go              registers the plugin with Grafana
pkg/plugin/settings.go   data source settings and defaults
pkg/plugin/swis.go       the REST client: Query and Invoke, TLS, error envelope
pkg/plugin/macros.go     $__timeFilter, $__timeFrom, $__timeTo
pkg/plugin/frames.go     SWIS JSON rows to typed Grafana frames
pkg/plugin/datasource.go QueryData, CheckHealth, CallResource
pkg/plugin/plugin_test.go
src/datasource.ts        the frontend class: variables, invoke() helper
src/bindVariables.ts     dashboard variables to bound SWQL parameters
src/components/          the configuration and query editors
src/examples.ts          the validated example queries
dashboards/              the sample dashboard
provisioning/            development provisioning for docker compose
```

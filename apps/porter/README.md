# Porter

A Windows utility that moves SolarWinds Observability Self-Hosted configuration between
installations over the SWIS API. **v0.2 implements eight areas end-to-end** behind one
generic Connect → Direction → Constellation → Select/Stage → Run workflow: Modern
Dashboards, Alerts, Reports, SAM Templates, WPM Recordings, NCM Device Templates,
Nodes + Custom Properties, and NCM Compliance Reports. Every area is a provider behind
the same contract (list, export, validate, collide, import, verify), so the selection
grid, the Airlock staging, the GO/NO-GO dry run, and the packaging pipeline are shared.

Every SWIS route used here was verified against the extracted 2026.2 contract in this
repository before it was coded.

## Build (on Windows)

Requires the [.NET 8 SDK](https://dotnet.microsoft.com/download/dotnet/8.0). WPF is
Windows-only: build on Windows, not WSL.

```text
cd apps\porter
dotnet publish Porter\Porter.csproj -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true
```

The executable lands in `Porter\bin\Release\net8.0-windows\win-x64\publish\Porter.exe` —
a single file, no runtime install needed on the target machine (air-gap friendly).

**Elevation:** `app.manifest` bakes `requireAdministrator` into the binary (DISA STIG
requirement). Windows refuses an un-elevated launch; the exe carries the UAC shield.

## The v0.1 verification round-trip

1. Run Porter (accept the UAC prompt), connect to server A — username/password or
   "connect as my current Windows account". **TLS verification defaults to on.** SWIS
   ships with the self-signed `SolarWinds-Orion` certificate; with verification on it is
   trusted when that exact certificate is installed in a Windows certificate store, or by
   a one-time SHA-256 thumbprint pin on first contact — and the accepted certificate's
   fingerprint is recorded in the session log either way, so an unexpected endpoint
   leaves evidence. Binding a domain-trusted certificate to SWIS (procedure below)
   removes even the pin step. Note: the documented SWIS REST contract
   offers basic auth only — if the server rejects your Windows session
   with a 401, Porter says so plainly and asks for a username/password (Windows-session
   auth over the SOAP endpoint on 17777 is a pinned item).
2. Export → Modern Dashboards → select with the checkboxes (Space, Shift+Click,
   Ctrl+A / Ctrl+Shift+A all work) → Raw files, Package (.zip + manifest), or encrypted
   package (.zip.aes, AES-256-GCM).
3. Reconnect to server B (the Docking screen comes back prefilled from your last
   connect — change the server name and re-enter the password) → Import → Modern
   Dashboards → drop the files or the package.
   Every file is validated locally before any API call (envelope, placements,
   duplicate widget keys, the SWQL-stored-twice check).
4. Pick the collision policy: **Skip** (skips are reported by name) or **Import as copy**
   (all GUIDs regenerated, renamed "… (Copy)", new names shown in the results).
5. Dry run first if you like — full validation plus collision checks, zero writes.
6. Import. The dashboards verb returns void, so Porter verifies each import by re-querying
   the dashboard `unique_key` and reports the new DashboardIDs.

Everything is logged as JSONL in `%ProgramData%\Porter\logs`, written before the UI
reports success. Certificate pins live in `%ProgramData%\Porter\pins.json` — delete a
line to un-pin. On startup Porter **hardens `%ProgramData%\Porter`** to Administrators +
SYSTEM only (inheritance off), refuses to operate through a junction/symlink, and logs
every connection that is accepted via a pin — so a pre-planted pin cannot act silently.
Encrypted packages are assembled entirely in memory: plaintext never touches the
destination disk. Hostile input is bounded — 64 MB per dashboard file or zip entry
(counted as it decompresses, since a zip's directory can lie), 256 MB per package.

## What is deliberately NOT here

- **Passwords are never stored.** Porter remembers the last successful connection —
  server, port, auth mode, username, and the TLS choice — in
  `%ProgramData%\Porter\connection.json`, and prefills the Docking screen from it.
  The password is always re-entered.
- **TLS is never silent.** Verification defaults on, trusting the `SolarWinds-Orion`
  certificate through the Windows certificate store or an explicit thumbprint pin.
  Turning it off is a deliberate lab-only choice, and even then every connection logs
  the presented certificate's fingerprint.
- No telemetry, no network egress except the SWIS host you name.

## The SWIS calls executed on import

Every import lands through one of these documented routes (all verified against the
2026.2 contract; queries for collision checks and read-back verification accompany
them):

| Area | Import call |
| --- | --- |
| Modern Dashboards | `Orion.Dashboards.Instances.Import(dashboard)` (export: `Export`) |
| Alerts | `Orion.AlertConfigurations.Import(alertXml)` (export: `Export`) |
| Reports | `Orion.Report.CreateReport(definition)` |
| SAM templates | `Orion.APM.ApplicationTemplate.ImportTemplate(template)` (export: `ExportTemplate`) |
| NCM compliance | `Cirrus.PolicyReports.AddPolicyReport(report, importFlag)` then `Cirrus.PolicyReports.StartCaching([newId])` (export: `GetPolicyReport`) |
| NCM device templates | CRUD `Create` on `Cli.DeviceTemplates` |
| WPM recordings | `Orion.SEUM.Recordings.Import(recording)` (export: `Export`) |
| Node custom properties | `Orion.NodesCustomProperties.CreateCustomProperty` / `CreateCustomPropertyWithValues` (validated first with `ValidateCustomProperty`), values via CRUD update on `…/CustomProperties` |

An import whose verification query returns nothing is reported as **No data
returned** for that item, never as success.

## TLS: living with — or replacing — the SolarWinds-Orion certificate

SWIS answers on 17774 with a self-signed certificate issued as `SolarWinds-Orion`. No
Windows machine trusts it out of the box. Porter's **Verify TLS certificate** checkbox
defaults to **on**, and the self-signed certificate is accepted two ways: install that
exact certificate in a Windows certificate store (CurrentUser or LocalMachine — Root,
CA, TrustedPeople or Personal), or pin it once by SHA-256 thumbprint at First Contact.
Turning verification off is lab-only and is not silent: each session logs the presented
certificate's subject and
SHA-256 fingerprint to the Captain's Log (`%ProgramData%\Porter\logs`), so a
man-in-the-middle still leaves a trail you can diff between sessions.

The better fix is to give SWIS a domain-trusted certificate, then turn verification on.
On the Orion server (elevated PowerShell / cmd):

1. **Get a certificate the domain trusts** — from your AD CS enterprise CA or another
   internal CA — with the server's **FQDN in the Subject Alternative Name** (add the
   short hostname and IP as extra SANs if operators connect that way). It needs the
   Server Authentication EKU; install it into `LocalMachine\My` (Personal →
   Certificates) and note its **thumbprint** as certutil/netsh display it.
2. **Find the current SWIS binding** — SWIS registers an HTTP.SYS SSL binding:

   ```text
   netsh http show sslcert
   ```

   Locate the entry for port `17774`. Copy its **Application ID** GUID exactly — the
   new binding must re-use it, or SolarWinds will not recognise the binding as its own.
3. **Swap the certificate on the binding**:

   ```text
   netsh http delete sslcert ipport=0.0.0.0:17774
   netsh http add sslcert ipport=0.0.0.0:17774 certhash=<new-cert-thumbprint> appid={<same-appid>} certstorename=MY
   ```
4. **Restart the SolarWinds Information Service V3** (Orion Service Manager, or the
   service directly) and confirm the certificate being served: browse
   `https://<fqdn>:17774/SolarWinds/InformationService/v3/Json/` — the padlock should
   validate with no warning.
5. In Porter, tick **Verify TLS certificate** and connect by the **FQDN on the
   certificate** (a raw IP fails name-matching unless the IP is a SAN). From then on
   verification is real, and any future unknown certificate raises the First Contact
   pin dialog instead of being accepted.

An Orion platform upgrade or repair can silently re-bind the self-signed certificate —
if a verified connect suddenly fails, re-run step 2 and check the binding before
blaming the network.

## Mission dictionary

The UI wears SolarWinds' space heritage (Orion, Cirrus, Hubble) — always as a **dual
label** beside the functional name, never instead of it. The JSONL audit log and every
error sentence stay plain. For the record:

| Callsign | Means | Where |
| --- | --- | --- |
| HERMES | The app's callsign — the ferry between two worlds | Title bar |
| Docking · Pathfinder · Dock | Connect screen · test · connect | Screen 1 |
| Orion Transit | Export | Direction card |
| Project Genesis | Import | Direction card |
| Cryogenic Stasis (Freeze / Revive) | Backup & Restore (snapshot / rollback), pinned v2 | Direction card |
| Constellations | The configuration areas | Screen 3 |
| Flight-ready / On the Launch Pad / In Dry Dock / Uncharted | Implemented / next build / pinned v2 / no SWIS route | Area phase tags |
| Cargo Manifest | The export selection list | Screen 4 |
| Cargo pod / Cloaked cargo pod | .zip package / AES-encrypted .zip.aes | Output formats |
| Landing site | Destination folder | Export panel |
| Begin Transit | The export button | Screen 4 |
| The Airlock · Pre-flight checks | Import staging · per-file validation | Screen 5 |
| Prime Directive | Collision policy: skip what already exists | Import panel |
| Replicate | Collision policy: import as a copy (new GUIDs) | Import panel |
| Simulation — Go / No-Go | Dry run; each staged file reports GO or NO-GO | Screen 5 |
| Energize | The import button | Screen 5 |
| Tricorder | The re-query that verifies each import landed | Run log |
| Mission Control · Telemetry · Hubble feed | The run screen and its live log | Screen 6 |
| Captain's Log | The JSONL session log (content stays plain) | Run screen |
| First Contact | The unknown-certificate pin dialog | Verified mode |

## Area status (v0.1)

| Area | Mechanism (verified 2026.2) | Status |
| --- | --- | --- |
| Modern Dashboards | `Orion.Dashboards.Instances.Export/Import` verb pair · client-side copy rewrite | **Flight-ready** |
| Alerts | `Export(id, stripSensitiveData)` / `Import` → `AlertImportResult` · needs manageAlerts | **Flight-ready** |
| Reports | `SELECT Definition` + `CreateReport` (9 positional params, `limitationCategory` third) | **Flight-ready** |
| SAM Templates | `ExportTemplate(int)` / `ImportTemplate` — `.apmtemplate`, UniqueId collision key | **Flight-ready** |
| WPM Recordings | `Export(id, password)` / `Import(content, name, password)` — cipher password mandatory | **Flight-ready** |
| NCM Device Templates | `TemplateXml` column out · SWIS CRUD Create in · built-ins read-only | **Flight-ready** |
| Nodes + Custom Properties | one CSV · `CreateCustomProperty` (admin) + per-node `…/CustomProperties` update | **Flight-ready** |
| NCM Compliance Reports | `GetPolicyReport(id, true)` / `AddPolicyReport(report, true)` + `StartCaching` | **Flight-ready** |
| Discovery + Credentials | partial by design — secrets never leave a server | In Dry Dock (v2) |
| Universal Device Pollers | export-only; definitions have no SWIS create | In Dry Dock (v2) |
| Device Studio | no SWIS route in 2026.2 | Uncharted |

### Per-area behavior worth knowing

- **Alerts** — "Remove sensitive data" is ON by default (accounts, passwords, tokens
  stripped at export). Import always *creates*; a same-name alert on the target means
  the file is skipped and reported. A partial import (the server's `MigrationMessage`,
  e.g. a referenced custom property missing) lands as a warning, not a success.
- **Reports** — export is the `Definition` column, byte-for-byte what the console's
  export button writes. Import is `CreateReport` (create-only); name collisions skip.
  Report *schedules* have no SWIS route anywhere — they never travel.
- **SAM Templates** — the `.apmtemplate` XML travels verbatim, including every script
  monitor's `ScriptBody` — Porter warns per file so embedded secrets get reviewed.
  Assigned credentials never travel; re-choose them after import.
- **WPM Recordings** — the platform itself demands a cipher password on export and the
  same one on import (this is the API's own file encryption, separate from Porter's
  optional `.zip.aes` packaging). Porter wraps the ciphered blob in a small envelope
  carrying the recording's real name and GUID, so collisions match the true name and
  the import is never renamed by a sanitized filename; a bare blob from another tool
  still imports, named after its file. Transactions/monitors have no export route:
  after importing a recording, re-create its monitors on the target.
- **NCM Device Templates** — built-ins (`IsDefault`) are listed under "Show built-in"
  and are read-only server-side; a collision against one is reported as such. Imports
  land with **auto-detect OFF** — enabling *Use for Auto Detect* is a deliberate
  console step, so an imported template can never silently re-route existing nodes.
- **Nodes + Custom Properties** — one CSV: `Caption`, `IPAddress`, then every node
  custom property, plus annotation rows (`#datatype`, `#allowedvalues`, `#mandatory`,
  `#default`) so definitions are recreated faithfully — restricted-value lists included.
  Import pre-flights each new definition with `ValidateCustomProperty`, creates it
  (admin needed), then writes values matching nodes by IP with Caption fallback.
  Ambiguous matches are skipped and named, never guessed; every row fails individually
  and the outcome accounts for all of it. Values with embedded newlines round-trip.
  SNMP community strings are deliberately not exported.
- **NCM Compliance Reports** — Porter writes the console's own XML format (UTF-16),
  so files interchange with the WebUI both ways. Import validation raises a **blocking
  security flag** for every rule with `ExecuteScriptAutomatically=true` (those rules
  push configuration to failing devices once cached); the file cannot be imported
  until the operator ticks the acknowledgement. After import Porter starts compliance
  caching for just that report. See
  [docs/modules/ncm-compliance-reports.md](../../docs/modules/ncm-compliance-reports.md).

## Layout

```text
Porter/
├─ app.manifest            requireAdministrator (STIG)
├─ Core/                   SwisSession (REST), cert pinning, JSONL log, package writer, AES-GCM
├─ Areas/                  AreaProvider contract + registry · one provider per area · validators
└─ Views/                  Connect · Mode · Area · Export · Import · Run · PasswordDialog
```

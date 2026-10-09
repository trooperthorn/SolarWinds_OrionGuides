# Porter

A Windows utility that moves SolarWinds Observability Self-Hosted configuration between
installations over the SWIS API. **v0.3 provides eight configuration providers** behind one
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

Tests and CI: `dotnet test Porter.sln -c Release` runs the xUnit suite in `Porter.Tests`
(validators, copy rewrite, CSV round trip, package reader and encoding detection, crypto,
run reports, SAM collision keys against the real samples, NCM tree comparison).
`.github/workflows/porter.yml` builds and tests on `windows-latest` for any change under
`apps/porter/`.

**Elevation:** `app.manifest` requests `requireAdministrator`. This is an application
design choice, not a substantiated universal DISA STIG requirement. No benchmark, version,
or rule ID is cited for that earlier claim. The executable requests UAC elevation.

## The verification round-trip

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
   (dashboard and widget identity keys remapped, dashboards renamed "… (Copy)").
   A file collides when its dashboard key **or any of its widget keys** already exists on
   the target, because a same-key import overwrites the existing widget wherever it is
   placed. Embedded object GUIDs are preserved; see the identity limits below.
5. Dry run first if you like — full validation plus collision checks, zero writes. Each
   GO file also logs a read-only `plan:` — dashboards it would create, custom properties
   it would create and how each node row resolves (one match / not found / ambiguous;
   first 50 rows listed), and each report's limitation-category check.
6. Import. The dashboards verb returns void, so Porter verifies each import by re-querying
   the dashboard `unique_key` and reports the new DashboardIDs.

**Abort** stops a run between items (the item in flight finishes). A package export
writes once at the end, so aborting one saves nothing; raw exports write each file as it
completes and keep what was written. After every run — completed, aborted, or failed —
Porter writes `porter-run_<export|import>_<timestamp>.json` (tool version, area, server,
UTC start/finish, outcome, counts, one line per item; never passwords or payloads): next
to the output for an export, in `%ProgramData%\Porter\logs` for an import. The path is
logged.

**Package verification.** A Porter package carries `manifest.json` (now with
`manifestVersion`). On import, files are chosen by the manifest's `area` — not by file
extension, which cannot tell alerts from reports — and each one's SHA-256 is checked; a
modified file, or a file in the area's folder the manifest does not list, is staged with
an error and cannot be imported. The source server, platform, and export time are shown
on each staged row. A raw file or a zip without a Porter manifest still imports, but
carries an "unverified origin" warning. A manifest newer than this build is refused.
"Import files that carry warnings" is **off** by default, so unverified files need that
box ticked deliberately.

Everything is logged as JSONL in `%ProgramData%\Porter\logs`, written before the UI
reports success. Certificate pins live in `%ProgramData%\Porter\pins.json` — delete a
line to un-pin (pins are written atomically). On startup Porter **hardens
`%ProgramData%\Porter`** — owner reset to Administrators, then Administrators + SYSTEM
only (inheritance off), recursively, with the outcome logged as `appdirs` — refuses to operate through a junction/symlink, and logs
every connection that is accepted via a pin — so a pre-planted pin cannot act silently.
Encrypted packages are assembled entirely in memory: plaintext never touches the
destination disk. Hostile input is bounded — 64 MB per dashboard file or zip entry
(counted as it decompresses, since a zip's directory can lie), 256 MB decompressed per
package, and at most 5,000 entries per archive.

## Identity and verification limits

Code review on 2026-09-18 found the limits this section originally listed; Porter 0.3.0
changed the behavior as described below. Neither the review nor the 0.3.0 change performed
a live import.

- **Collisions (0.3.0).** Dashboard keys are checked in `Orion.Dashboards.Instances` and
  every widget key in `Orion.Dashboards.Widgets.UniqueKey`, with UUID spelling normalized
  and named keys compared case-insensitively. A widget key already on the target is a
  collision: under Skip the file is skipped and the run report names the widget key and
  the dashboards that place it (`Orion.Dashboards.Links`). A target whose widget keys
  cannot be read fails the file instead of importing it unchecked.
- **Copy (0.3.0).** New keys avoid every dashboard and widget key on the target, and
  dashboard and widget keys are mapped separately. A widget key carrying different
  definitions inside one file is refused (placements cannot say which one they mean);
  identical duplicates keep one new key. Each file gets its own key map, so two files
  that shared a widget become independent copies. A widget placed on several dashboards
  in one file stays shared within the copy, detached from the original. Embedded GUIDs
  are not regenerated.
- **Groups and routes on copy (0.3.0).** `groupId` moves to a new group (copies grouped
  together in one file stay together; the tab labels are kept) and `routeId` and
  `dashboardRoutes` are cleared to the empty forms seen in other exports, so a copy does
  not join the original's tabs or share its route. A warning in the run log says what
  changed; links that target the original's route still reach the original.
- **Self-references on copy (0.3.0).** Quoted dashboard-name literals are rewritten in
  `swql` and `swqlQuery` fields, and in `swql`, `swqlQuery` and conditional `query` fields
  inside the dashboard-level `configuration`, which can be a JSON-encoded string and is
  decoded and re-encoded for the purpose.
- Local duplicate-widget findings are warnings. Inspect them before import. When the
  two stored copies of a widget's SWQL differ, Porter warns and does not claim which one
  runs. A dry run covers the implemented validation and collision checks, not every
  server-side conflict.
- Collision checks run per file against the live target, not across every file of a
  batch before the first import. There is no update mode.
- Post-import dashboard-key lookup establishes that matching dashboard rows exist. It
  does not verify every resource property, query result, rendered widget, or whether an
  existing dashboard's shared widget changed.

Before using these tools for modified shared dashboards, follow the
[widget identity audit](../../docs/webui/modern-dashboard-widget-identity-audit.md).
Still open: package-wide identity comparison before import, an explicit update mode, and
content-level read-back.

Source: [DashboardsArea.cs](Porter/Areas/DashboardsArea.cs), [DashboardValidator.cs](Porter/Areas/DashboardValidator.cs), and [DashboardsProvider.cs](Porter/Areas/DashboardsProvider.cs).

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
| NCM compliance | `Cirrus.PolicyReports.AddPolicyReport(report, importFlag)` (created `Disabled`), `UpdateReportStatus`, read-back with `GetPolicyReport(id, true)`; `StartCaching([newId])` only when the operator keeps an `Enabled` status (export: `GetPolicyReport`) |
| NCM device templates | CRUD `Create` on `Cli.DeviceTemplates` |
| WPM recordings | `Orion.SEUM.Recordings.Import(recording)` (export: `Export`) |
| Node custom properties | `Orion.NodesCustomProperties.CreateCustomProperty` / `CreateCustomPropertyWithValues` (validated first with `ValidateCustomProperty`), values via CRUD update on `…/CustomProperties` |

An import whose verification query returns nothing is reported as **No data
returned** for that item, never as success. An import that wrote something but read back
incomplete (an NCM report without all its policies and rules) is reported as **partial**
and counted as a failure.

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

## Area status (v0.3)

| Area | Mechanism (verified 2026.2) | Status |
| --- | --- | --- |
| Modern Dashboards | `Orion.Dashboards.Instances.Export/Import` verb pair · client-side copy rewrite | **Flight-ready** |
| Alerts | `Export(id, stripSensitiveData)` / `Import` → `AlertImportResult` · the 2026.2 schema declares `admin` and `manageAlerts` on both verbs | **Flight-ready** |
| Reports | `SELECT Definition` + `CreateReport` (9 positional params, `limitationCategory` third) | **Flight-ready** |
| SAM Templates | `ExportTemplate(int)` / `ImportTemplate` — `.apmtemplate`, the template's own UniqueId as collision key | **Flight-ready** |
| WPM Recordings | `Export(id, password)` / `Import(content, name, password)` — cipher password mandatory | **Flight-ready** |
| NCM Device Templates | `TemplateXml` column out · SWIS CRUD Create in · built-ins read-only | **Flight-ready** |
| Nodes + Custom Properties | one CSV · `CreateCustomProperty` (admin) + per-node `…/CustomProperties` update | **Flight-ready** |
| NCM Compliance Reports | `GetPolicyReport(id, true)` / `AddPolicyReport(report, true)`, imported `Disabled`, tree read back; `StartCaching` on opt-in | Implemented; nested read-back added in 0.3.0, not live-tested (see the [audit](../../docs/modules/ncm-compliance-portability-audit.md)) |
| Discovery + Credentials | partial by design — secrets never leave a server | In Dry Dock (v2) |
| Universal Device Pollers | export-only; definitions have no SWIS create | In Dry Dock (v2) |
| Device Studio | no SWIS route in 2026.2 | Uncharted |

### Per-area behavior worth knowing

- **Alerts** — "Remove sensitive data" is ON by default (accounts, passwords, tokens
  stripped at export). Import always *creates*; a same-name alert on the target means
  the file is skipped and reported. The name is read from the definition's own `<Name>`
  (root, then the `AlertDefinition`/`AlertConfiguration` wrapper); a name found only in a
  nested element is flagged. A file whose root is not an alert definition is an error. A partial import (the server's `MigrationMessage`,
  e.g. a referenced custom property missing) lands as a warning, not a success.
- **Reports** — export is the `Definition` column, byte-for-byte what the console's
  export button writes. Import is `CreateReport` (create-only); name collisions skip. A
  file whose root is not `<Report>` is an error, not a warning. The definition's
  `LimitationCategory` names a folder that has to exist on the target; there is no
  entity listing those folders, so the dry run and the import check whether any report
  the account can see already uses it. If none does, the item is reported as a warning
  to confirm the folder (absence cannot be proven that way). With a Windows-session
  connection `CreateReport`'s `userName` is sent empty, because the session never learns
  the account name.
  Report *schedules* have no SWIS route anywhere — they never travel.
- **SAM Templates** — the `.apmtemplate` XML travels verbatim, including every script
  monitor's `ScriptBody` — Porter warns per file so embedded secrets get reviewed.
  Assigned credentials never travel; re-choose them after import. The collision key is
  the `UniqueId` that is a direct child of `<ApplicationTemplate>`; every component
  carries its own `UniqueId`, and current exports list components first, so the first
  `UniqueId` in the file is a component's (fixed in 0.3.0).
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
  `Author` is empty for a Windows-session connection, which never learns the account
  name.
- **Nodes + Custom Properties** — one CSV: `Caption`, `IPAddress`, then every node
  custom property, plus annotation rows (`#datatype`, `#allowedvalues`, `#mandatory`,
  `#default`) so definitions are recreated faithfully — restricted-value lists included.
  Import pre-flights each new definition with `ValidateCustomProperty` and reads its
  `CustomPropertyValidationResult`: only `Status` `Valid` goes on to create the
  definition (admin needed). `Exists` reuses the definition, as for one already on the
  target, with a note; `IsSystem`, `IsReserved`, `Error` or an unreadable result stop
  that definition and are reported with the status and `ErrorMessage`. `Status` is read
  as a name or a number. Values are then written matching nodes by IP with Caption
  fallback.
  Ambiguous matches are skipped and named, never guessed; every row fails individually
  and the outcome accounts for all of it. Values with embedded newlines round-trip.
  Cells starting with `=`, `+`, `-`, `@`, tab or CR are exported with a leading `'` so
  Excel cannot run them as formulas; import removes exactly that one quote. Boolean
  cells accept true/false/1/0/yes/no; anything else is reported and that cell is not
  written. SNMP community strings are deliberately not exported.
- **NCM Compliance Reports** — Porter writes the observed element structure as UTF-16
  with a matching declaration. Validate interchange on the target console. On import a
  BOM-less UTF-16 file is detected and read as UTF-16, and a UTF-8 file that declares
  `utf-16` is read as UTF-8 with the fallback shown on the staged row and in the run log.
  Import validation raises a **blocking security flag** for every rule with
  `ExecuteScriptAutomatically=true` (those rules push configuration to failing devices
  once cached); the file cannot be imported until the operator ticks the acknowledgement.
  Imported reports would start evaluating on their own (the policy cache refreshes daily
  and report jobs can be scheduled), so **reports import `Disabled` by default**: Porter
  creates the report disabled, confirms it with `UpdateReportStatus`, and does not start
  caching. The opt-in checkbox "Keep each NCM report's exported status" keeps the file's
  status; an `Enabled` report is then enabled and compliance caching starts for just that
  report. Either way the report is enabled only after Porter reads the stored tree back
  with `GetPolicyReport(id, true)` and the policy and rule counts and names match the
  file. A mismatch is reported as a **partial** import with both counts, and the report
  stays disabled. The chosen and stored status are recorded per item in the run report.
  See the [portability audit](../../docs/modules/ncm-compliance-portability-audit.md) and
  [docs/modules/ncm-compliance-reports.md](../../docs/modules/ncm-compliance-reports.md).

## Layout

```text
Porter/
├─ app.manifest            requireAdministrator (application elevation setting)
├─ Core/                   SwisSession (REST), cert pinning, JSONL log, package writer/reader, AES-GCM, run reports
├─ Areas/                  AreaProvider contract + registry · one provider per area · validators
└─ Views/                  Connect · Mode · Area · Export · Import · Run · PasswordDialog
Porter.Tests/              xUnit tests (run in CI)
```

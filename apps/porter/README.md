# Porter

A Windows utility that moves SolarWinds Observability Self-Hosted configuration between
installations over the SWIS API. **v0.1 is the verification build**: the full
Connect → Direction → Area → Select/Stage → Run workflow, with **Modern Dashboards**
implemented end-to-end. The other areas are visible in the app with their real SWIS
mechanism and phase — see the concept document for the plan.

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
   "connect as my current Windows account". **TLS verification defaults to off** because
   SWIS ships with the self-signed `SolarWinds-Orion` certificate; Porter still records
   the presented certificate's SHA-256 fingerprint in the session log, so an unexpected
   endpoint leaves evidence. Tick **Verify TLS certificate** once a domain-trusted
   certificate is bound to SWIS (procedure below) — then unknown certificates are pinned
   by SHA-256 thumbprint on first contact. Note: the documented SWIS REST contract
   offers basic auth only — if the server rejects your Windows session
   with a 401, Porter says so plainly and asks for a username/password (Windows-session
   auth over the SOAP endpoint on 17777 is a pinned item).
2. Export → Modern Dashboards → select with the checkboxes (Space, Shift+Click,
   Ctrl+A / Ctrl+Shift+A all work) → Raw files, Package (.zip + manifest), or encrypted
   package (.zip.aes, AES-256-GCM).
3. Reconnect to server B → Import → Modern Dashboards → drop the files or the package.
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

- **Passwords are never stored.** Profiles (when they arrive) hold server + username only.
- **TLS is never silent.** Verification defaults off (the platform's own certificate is
  self-signed), but every unverified connection logs the certificate fingerprint, and one
  checkbox turns on full verification with pin-by-thumbprint.
- No telemetry, no network egress except the SWIS host you name.

## TLS: living with — or replacing — the SolarWinds-Orion certificate

SWIS answers on 17774 with a self-signed certificate issued as `SolarWinds-Orion`. No
Windows machine trusts it, so Porter's **Verify TLS certificate** checkbox defaults to
**off**. Off is not silent: each session logs the presented certificate's subject and
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
| Modern Dashboards | `Orion.Dashboards.Instances.Export/Import` verb pair | **Flight-ready** (implemented) |
| Alerts | verb pair with strip-sensitive / password-protect options | On the Launch Pad (next build) |
| Reports | `SELECT Definition` + `CreateReport` | On the Launch Pad (next build) |
| SAM Templates | `ExportTemplate`/`ImportTemplate` + `StartTestComponents` dry run | On the Launch Pad (next build) |
| WPM Transactions | recording verb pair (cipher password) + `Exists(guid)` | On the Launch Pad (next build) |
| NCM Device Templates | `TemplateXml` query + CRUD | On the Launch Pad (next build) |
| Nodes + Custom Properties | query + `ValidateCustomProperty`/`CreateCustomProperty` + CRUD | On the Launch Pad (next build) |
| NCM Compliance | deep verb pair — pinned: remediation-script safety gate | In Dry Dock (v2) |
| Discovery + Credentials | partial by design — secrets never leave a server | In Dry Dock (v2) |
| Universal Device Pollers | export-only; definitions have no SWIS create | In Dry Dock (v2) |
| Device Studio | no SWIS route in 2026.2 | Uncharted |

## Layout

```text
Porter/
├─ app.manifest            requireAdministrator (STIG)
├─ Core/                   SwisSession (REST), cert pinning, JSONL log, package writer, AES-GCM
├─ Areas/                  AreaCatalog (the 11 areas + status) · DashboardsArea · DashboardValidator
└─ Views/                  Connect · Mode · Area · Export · Import · Run · PasswordDialog
```

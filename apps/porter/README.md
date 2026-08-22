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
   "connect as my current Windows account". Self-signed certificates are pinned by SHA-256
   thumbprint on first connect; verification is never switched off. Note: the documented
   SWIS REST contract offers basic auth only — if the server rejects your Windows session
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
- **TLS verification is never disabled.** Pin-by-thumbprint is the only accommodation.
- No telemetry, no network egress except the SWIS host you name.

## Area status (v0.1)

| Area | Mechanism (verified 2026.2) | Status |
| --- | --- | --- |
| Modern Dashboards | `Orion.Dashboards.Instances.Export/Import` verb pair | **Implemented** |
| Alerts | verb pair with strip-sensitive / password-protect options | next build |
| Reports | `SELECT Definition` + `CreateReport` | next build |
| SAM Templates | `ExportTemplate`/`ImportTemplate` + `StartTestComponents` dry run | next build |
| WPM Transactions | recording verb pair (cipher password) + `Exists(guid)` | next build |
| NCM Device Templates | `TemplateXml` query + CRUD | next build |
| Nodes + Custom Properties | query + `ValidateCustomProperty`/`CreateCustomProperty` + CRUD | next build |
| NCM Compliance | deep verb pair — pinned: remediation-script safety gate | v2 |
| Discovery + Credentials | partial by design — secrets never leave a server | v2 |
| Universal Device Pollers | export-only; definitions have no SWIS create | v2 |
| Device Studio | no SWIS route in 2026.2 | pinned |

## Layout

```text
Porter/
├─ app.manifest            requireAdministrator (STIG)
├─ Core/                   SwisSession (REST), cert pinning, JSONL log, package writer, AES-GCM
├─ Areas/                  AreaCatalog (the 11 areas + status) · DashboardsArea · DashboardValidator
└─ Views/                  Connect · Mode · Area · Export · Import · Run · PasswordDialog
```

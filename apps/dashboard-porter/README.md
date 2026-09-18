# DashboardPorter

A Windows utility that moves SolarWinds Observability Self-Hosted **Modern Dashboards**
between installations over the SWIS API. It is a focused derivative of
[Porter](../porter/README.md), Sean's general configuration-porting tool: same connection,
packaging, and audit-logging core, narrowed to one area and one screen — Connect, then a
single tabbed Export / Import view.

Every SWIS route used here was verified against the extracted 2026.2 contract in this
repository before it was coded.

## Build (on Windows)

Requires the [.NET 8 SDK](https://dotnet.microsoft.com/download/dotnet/8.0). WPF is
Windows-only: build on Windows, not WSL.

```text
cd apps\dashboard-porter
dotnet publish DashboardPorter\DashboardPorter.csproj -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true
```

The executable lands in
`DashboardPorter\bin\Release\net8.0-windows\win-x64\publish\DashboardPorter.exe` — a single
file, no runtime install needed on the target machine (air-gap friendly).

**Elevation:** `app.manifest` bakes `requireAdministrator` into the binary (DISA STIG
requirement, matching Porter). Windows refuses an un-elevated launch; the exe carries the
UAC shield.

## Using it

1. Run DashboardPorter (accept the UAC prompt), connect to server A — username/password or
   "connect as my current Windows account". **TLS verification defaults to on.** SWIS
   ships with the self-signed `SolarWinds-Orion` certificate; with verification on it is
   trusted when that exact certificate is installed in a Windows certificate store, or by
   a one-time SHA-256 thumbprint pin on first contact — and the accepted certificate's
   fingerprint is recorded in the session log either way, so an unexpected endpoint leaves
   evidence.
2. **Export tab** — select dashboards with the checkboxes (Space, Shift+Click, Ctrl+A /
   Ctrl+Shift+A all work; built-in dashboards stay hidden until you ask for them), pick an
   output format (raw `.json` files, a `.zip` package with a manifest, or an AES-256-GCM
   encrypted `.zip.aes`), and click Export.
3. Reconnect to server B (the Connect screen comes back prefilled from your last connect —
   change the server name and re-enter the password), open the **Import tab**, and drop the
   files, the `.zip`, or the `.zip.aes` package. Every file is validated locally before any
   API call (envelope, placements, duplicate widget keys, the SWQL-stored-twice check).
4. Pick the collision policy: **Skip** (skips are reported by name) or **Import as copy**
   (all GUIDs regenerated, renamed "… (Copy)", new names shown in the results).
5. Dry run first if you like — full validation plus collision checks, zero writes.
6. Import. The dashboards verb returns void, so DashboardPorter verifies each import by
   re-querying the dashboard `unique_key` and reports the new DashboardIDs.

Everything is logged as JSONL in `%ProgramData%\DashboardPorter\logs`, written before the UI
reports success. Certificate pins live in `%ProgramData%\DashboardPorter\pins.json` — delete
a line to un-pin. On startup DashboardPorter **hardens `%ProgramData%\DashboardPorter`** to
Administrators + SYSTEM only (inheritance off), refuses to operate through a
junction/symlink, and logs every connection that is accepted via a pin — so a pre-planted
pin cannot act silently. Encrypted packages are assembled entirely in memory: plaintext
never touches the destination disk. Hostile input is bounded — 64 MB per dashboard file or
zip entry (counted as it decompresses, since a zip's directory can lie), 256 MB per package.

## What is deliberately NOT here

- **Passwords are never stored.** DashboardPorter remembers the last successful
  connection — server, port, auth mode, username, and the TLS choice — in
  `%ProgramData%\DashboardPorter\connection.json`, and prefills the Connect screen from it.
  The password is always re-entered.
- **TLS is never silent.** Verification defaults on, trusting the `SolarWinds-Orion`
  certificate through the Windows certificate store or an explicit thumbprint pin. Turning
  it off is a deliberate lab-only choice, and even then every connection logs the presented
  certificate's fingerprint.
- **No other configuration areas.** Alerts, Reports, SAM Templates, NCM, Nodes, and the
  rest stay in Porter — this tool only moves Modern Dashboards, on purpose, so the export
  grid, the collision policy, and the run screen have one job each and nothing to select.
- No telemetry, no network egress except the SWIS host you name.

## The SWIS calls

| Call | Purpose |
| --- | --- |
| `Orion.Dashboards.Instances.Export(dashboardId)` | Export one dashboard's JSON definition |
| `Orion.Dashboards.Instances.Import(definition)` | Import a definition (returns void) |
| `SELECT … FROM Orion.Dashboards.Instances WHERE UniqueKey = @k` | Collision check and post-import verification |

An import whose verification query returns nothing is reported as **No data returned**,
never as success.

### The copy transform

Import-as-copy is a structural rewrite, not a text substitution: only the identity fields
the format defines are regenerated (`dashboards[].unique_key` and `widgets[].unique_key`,
with placements remapped through the same old→new map), so GUIDs inside embedded SWQL and
URLs that reference other server-side objects are left alone. Each dashboard is renamed
"… (Copy)", and where a widget's SWQL addresses a dashboard by its original name (the
documented self-referencing link pattern), the quoted literal is rewritten to the new name
so the copy points at itself. A query that mentions the old name outside a quoted literal is
left unchanged and flagged in the run report for manual review.

## Layout

```text
DashboardPorter/
├─ app.manifest            requireAdministrator (STIG)
├─ Core/                   SwisSession (REST), cert pinning, JSONL log, package writer, AES-GCM,
│                          and the Modern Dashboards export/import/validate/copy logic
└─ Views/                  Connect · Export/Import (tabbed) · Run · PasswordDialog
```

This is the same `Core/` shape as Porter's, minus the multi-area `AreaProvider` contract:
with one area there is nothing to abstract over, so `DashboardsCore` and
`DashboardValidator` are called directly from the view.

# DashboardPorter

A Windows utility that moves SolarWinds Observability Self-Hosted **Modern Dashboards**
between installations over the SWIS API. It is a focused derivative of
[Porter](../porter/README.md), Sean's general configuration-porting tool: same connection,
packaging, and audit-logging core, narrowed to one area and one screen — Connect, then a
single tabbed Export / Import view.

Every SWIS route used here was verified against the extracted 2026.2 contract in this
repository before it was coded.

## Build (on Windows)

Requires the [.NET 10 SDK](https://dotnet.microsoft.com/download/dotnet/10.0). WPF is
Windows-only: build on Windows, not WSL.

```text
cd apps\dashboard-porter
dotnet publish DashboardPorter\DashboardPorter.csproj -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true
```

The executable lands in
`DashboardPorter\bin\Release\net10.0-windows\win-x64\publish\DashboardPorter.exe` — one file
(~59 MB; the .NET runtime and WPF's native interop libraries are bundled in), no install
and no separate runtime needed on the target machine (air-gap friendly). No `.pdb` ships
with it — Release builds carry no debug symbols. On first launch it self-extracts to a
per-version cache (native libraries plus the compressed bundle above); nothing is written
next to the exe itself, so it can be run straight from a USB stick or a read-only share.

The project enables single-file compression, English satellite resources, and no
Release debug symbols. The size figures above describe an earlier build, not a size
contract. Native AOT and trimming remain disabled in the project. A successful publish
is not evidence that the elevated GUI, authentication, or imports work on a target PC.
See [DashboardPorter.csproj](DashboardPorter/DashboardPorter.csproj) for the actual settings.

**Elevation:** `app.manifest` requests `requireAdministrator`, matching Porter. This is
an application design choice. The earlier DISA STIG attribution had no benchmark/version
or rule ID and is unverified; it is not a general compliance requirement.

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
   (dashboard and widget identity keys remapped, dashboards renamed "… (Copy)").
   Embedded object GUIDs are preserved; see the identity limits below.
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

## Identity and verification limits

Code review on 2026-09-18 found these limits; this review did not perform a live import:

- Collision queries inspect dashboard keys in `Orion.Dashboards.Instances`. They do not
  inventory all target widget identities, so a different dashboard can still reuse a
  widget key. "Skip" is not complete protection against shared-widget changes.
- `AsCopy` builds one old-to-new key map per input document. Duplicate old widget keys
  remain duplicate after remapping; it does not split conflicting definitions or provide
  an explicit per-dashboard sharing policy. Embedded GUIDs are not all regenerated.
- Local duplicate-widget findings are warnings. Inspect them before import. A dry run
  covers the implemented validation and collision checks, not every server-side conflict.
- Post-import dashboard-key lookup establishes that matching dashboard rows exist. It
  does not verify every resource property, query result, rendered widget, or whether an
  existing dashboard's shared widget changed.

Before using these tools for modified shared dashboards, follow the
[widget identity audit](../../docs/webui/modern-dashboard-widget-identity-audit.md).
Required follow-up: target widget inventory, package-wide identity comparison, explicit
sharing/isolation choice, and content-level read-back. These are documented gaps, not
features implemented by this documentation update.

Source: [DashboardsCore.cs](DashboardPorter/Core/DashboardsCore.cs).

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
├─ app.manifest            requireAdministrator (application elevation setting)
├─ Core/                   SwisSession (REST), cert pinning, JSONL log, package writer, AES-GCM,
│                          and the Modern Dashboards export/import/validate/copy logic
└─ Views/                  Connect · Export/Import (tabbed) · Run · PasswordDialog
```

This is the same `Core/` shape as Porter's, minus the multi-area `AreaProvider` contract:
with one area there is nothing to abstract over, so `DashboardsCore` and
`DashboardValidator` are called directly from the view.

# DashboardPorter

> **Porter is the maintained successor.** [Porter](../porter/README.md) (`apps/porter`)
> moves Modern Dashboards and seven other configuration areas and is where new work
> lands. DashboardPorter stays as the single-screen, dashboards-only tool and is kept at
> Porter's security level, but it is not where features are added first. Its packages
> import into Porter: a plain `.zip` through the shared manifest format, and an encrypted
> `.zip.aes` because Porter now also reads DashboardPorter's `DBPORTA1` encryption header
> (added alongside DashboardPorter 0.2.0; older Porter builds reject it).

A Windows utility that moves SolarWinds Observability Self-Hosted **Modern Dashboards**
between installations over the SWIS API, on one screen — Connect, then a single tabbed
Export / Import view.

It began as a narrowed copy of Porter's code, and it still is a copy rather than a shared
library: `SessionLog` and `ConnectionMemory` are the same code as Porter's (names
aside), `SwisSession` is Porter's minus the CRUD calls only Porter's other areas use,
`DashboardsCore` is Porter's `DashboardsArea` plus `DashboardValidator`, and as
of 0.2.0 `AppDirs`, the pin write, `PackageReader`, `RunReport`, and the dry-run widget
check are ported from Porter too. The two projects build separately and share no
assembly, so a fix in one has to be copied to the other. What they genuinely share is the
**package format**: the same `manifest.json` (`manifestVersion`, `area`, per-file SHA-256)
and the same AES-GCM layout, which differs only in its 8-byte header (`DBPORTA1` here,
`PORTERA1` in Porter). Each tool writes its own header and reads both.

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

Tests and CI: `dotnet test DashboardPorter.sln -c Release` runs the xUnit suite in
`DashboardPorter.Tests` (package reader verification and caps, encryption round trip
and cross-format decrypt, atomic pin writes, the dry-run widget-key plan, the manifest
and run report). `.github/workflows/dashboard-porter.yml` builds and tests on
`windows-latest` for any change under `apps/dashboard-porter/`.

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
   files, the `.zip`, or the `.zip.aes` package (DashboardPorter's or Porter's). Every file
   is validated locally before any API call (envelope, placements, duplicate widget keys,
   the SWQL-stored-twice check), after the package checks described below.
4. Pick the collision policy: **Skip** (skips are reported by name) or **Import as copy**
   (dashboard and widget identity keys remapped, dashboards renamed "… (Copy)").
   Embedded object GUIDs are preserved; see the identity limits below.
5. Dry run first if you like — full validation plus collision checks, zero writes. Each
   GO file also logs a read-only `plan:` — the dashboards it would create, and any of its
   widget `unique_key`s that already exist on the target (first 20 listed, as warnings).
   **Import Now** on the dry-run screen is offered only when the dry run completed.
6. Import. The dashboards verb returns void, so DashboardPorter verifies each import by
   re-querying the dashboard `unique_key` and reports the new DashboardIDs.

**Abort** stops a run between dashboards (the one in flight finishes). An export first
checks that the destination folder is a full path that accepts a write, before anything
is fetched. A package export (`.zip` / `.zip.aes`) writes once at the end, and its
dashboards are only logged as exported once the package is on disk — aborting one, or a
failed write, saves nothing and records every dashboard as not exported. A raw export
writes each file as soon as it is fetched and keeps what was written. After every run —
completed, aborted, or failed, dry runs included — DashboardPorter writes
`dashboardporter-run_<export|import>_<timestamp>.json` (tool version, server, UTC
start/finish, outcome, counts, one line per dashboard; never passwords or payloads; the
same fields as Porter's run report): next to the output for an export, in
`%ProgramData%\DashboardPorter\logs` for an import. The path is logged and shown on the
run screen.

**Package verification.** A package's `manifest.json` now carries `manifestVersion` and
the tool version read from the executable (for example `DashboardPorter 0.2.0`). On
import, files are chosen by the manifest's `area` (`dashboards`), so a mixed Porter
package stages only its dashboards, and each file's SHA-256 is checked against the
manifest. A modified file, a listed file missing from the package, or a file in the
`dashboards/` folder the manifest does not list (added after export) is staged with an
error and cannot be imported. The source server, platform, and export time are shown on
each staged row. A raw `.json` file or a zip without a manifest still imports, but carries
an "unverified origin" warning. A manifest newer than this build understands is refused.
"Import files that carry warnings" is **off** by default (it was on before 0.2.0), so
unverified files and files with validator warnings need that box ticked deliberately.

Everything is logged as JSONL in `%ProgramData%\DashboardPorter\logs`, written before the UI
reports success. Certificate pins live in `%ProgramData%\DashboardPorter\pins.json` — delete
a line to un-pin. Pins are written atomically (temporary file, then a move), and a
`pins.json` that is a junction or symlink is refused. On startup DashboardPorter **hardens
`%ProgramData%\DashboardPorter`** with `icacls`: owner reset to Administrators, then
Administrators + SYSTEM only (inheritance off), both recursively so anything planted
inside is covered. Each `icacls` exit code is checked and the outcome (`hardened`, or
`hardening-failed` with the reason) is written to the session log as the first `appdirs`
line; a failure is logged, not fatal. It refuses to operate through a junction/symlink,
and logs every connection that is accepted via a pin — so a pre-planted pin cannot act
silently. Encrypted packages are assembled entirely in memory: plaintext never touches
the destination disk.

Hostile input is bounded, counting bytes as they decompress (a zip's directory can lie):

| Limit | Applies to |
| --- | --- |
| 64 MB | each raw `.json` file (file size), and each zip entry that is read |
| 256 MB | total decompressed bytes read from one `.zip` or `.zip.aes`, manifest included |
| 256 MB | the encrypted `.zip.aes` file on disk, checked before decryption |
| 5,000 | entries in one archive, checked before any entry is read |

Entries the reader never opens (for example another area's files in a Porter package) do
not count toward the 256 MB total; they do count toward the 5,000-entry limit.

## Identity and verification limits

Code review on 2026-09-18 found these limits; this review did not perform a live import:

- Collision queries inspect dashboard keys in `Orion.Dashboards.Instances`. Widget keys
  are only checked in the dry-run plan (`Orion.Dashboards.Widgets.UniqueKey`, listed as
  warnings), not treated as collisions, so a different dashboard can still reuse a
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
| `SELECT UniqueKey FROM Orion.Dashboards.Widgets` | Dry run only: widget keys already on the target |

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
├─ Core/                   SwisSession (REST), cert pinning, JSONL log, package writer/reader,
│                          AES-GCM, run reports, and the Modern Dashboards
│                          export/import/validate/copy/plan logic
└─ Views/                  Connect · Export/Import (tabbed) · Run · PasswordDialog
DashboardPorter.Tests/     xUnit tests (run in CI)
```

This is the same `Core/` shape as Porter's, minus the multi-area `AreaProvider` contract:
with one area there is nothing to abstract over, so `DashboardsCore` and
`DashboardValidator` are called directly from the view.

## Changes in 0.2.0

Brought up to the hardening Porter received on 2026-09-29; documented above, listed here:

- `%ProgramData%\DashboardPorter` hardening resets the owner, recurses, checks `icacls`
  exit codes, and logs the outcome at startup (before 0.2.0 it set the DACL only and
  ignored failures, although this page said it logged the outcome).
- `pins.json` is written atomically and refused if it is a reparse point.
- Import reads the package manifest: SHA-256 per file, unlisted and missing files are
  errors, manifest-less input is "unverified origin", 5,000-entry and 256 MB
  decompressed caps per archive. Before 0.2.0 the manifest was ignored and only a
  64 MB per-entry cap applied.
- "Import files that carry warnings" defaults to off.
- Runs can be aborted between dashboards.
- Export probes the destination first, logs a dashboard as exported only once its output
  exists, and writes raw files one by one.
- The dry run also reports widget keys already on the target.
- The manifest records `manifestVersion` and the real tool version; the project version
  is 0.2.0; every run writes a JSON run report.
- Decryption accepts Porter's `PORTERA1` packages as well as `DBPORTA1`; DashboardPorter
  still writes `DBPORTA1`.

Not ported because DashboardPorter has no such areas: Porter's cross-area XML blocking,
CSV formula-injection guard, strict boolean parsing, and alert-name extraction.

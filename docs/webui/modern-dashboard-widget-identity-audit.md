# Modern Dashboard widget identity and import collisions

The import identity to check is **`widgets[].unique_key`**, together with the matching
**`dashboards[].widgets[].unique_key`** placement references. Changing a dashboard name,
dashboard key, widget title, or query does not give an existing widget key a new identity.
Independent copies need independent widget keys. Deliberate updates retain their keys.

This audit compares the owner-supplied `ecmel-ModernDashboards.zip` and
`Sean-ModernDashboards.zip`, read on 2026-09-18. The owner attributes the original dashboards
to emcel and the modified copies to Sean; the archive filename spells the first name
`ecmel`. Product/export versions and the exact files installed by affected customers were
not supplied. The archives were parsed as data, without importing or executing their queries.

## What the two packages actually establish

**There are no common dashboard or widget keys between these two ZIPs.** The demonstrable
conflict is inside Sean's package: three dashboard files define **All Active Alerts** under
one key but with different configuration. This is an import overwrite hazard consistent
with the reported symptom; these files alone do not prove which pre-existing customer
widget was overwritten or establish an emcel-to-Sean collision.

| Package | JSON files / dashboards | Widget definitions | Distinct widget keys |
| --- | --- | --- | --- |
| `ecmel-ModernDashboards.zip` | 3 | 3 | 3 |
| `Sean-ModernDashboards.zip` | 3 | 17 | 11 |
| Combined | 6 | 20 | 14 |

All six dashboard keys are distinct. Every placement resolves to a definition in its own
file. All 20 placements have `reference: false`; all six dashboard `parent` values are null,
and all 20 widget definitions omit `parent`. **A false `reference` flag, null dashboard
parent, or absent widget parent does not rule out identity collisions.**

The reproducible [JSON evidence](../../reference/dashboard-evidence/2026-09-18-widget-identities.json)
records archive/member SHA-256 hashes, JSON pointers, canonical definition hashes, every
occurrence, placement locations and pairwise changed paths. It excludes full embedded queries.

| Source ZIP | Bytes | SHA-256 |
| --- | --- | --- |
| `ecmel-ModernDashboards.zip` | 5231 | `1732cea3b8474f7eceea717babf309ae41d7302c39189cad04bec7b530e08130` |
| `Sean-ModernDashboards.zip` | 15056 | `2fb4c528e4f15c6ca12daa01e102cbfd3b00d1933b3015fdf6e8fd59c4cd65be` |

## The conflicting widget and its resources

**Flag `f4c74926-35af-4044-b921-dc2468e81c58`: same key, different definition.**
All three instances are table widgets named **All Active Alerts**. The relevant resource
difference is the dashboard lookup used to build the Site-column navigation link.

| Sean ZIP member | Definition pointer | Matching placement pointer | Query's `DisplayName` target |
| --- | --- | --- | --- |
| `Site Summary - Alert Status.json` | `/widgets/1` | `/dashboards/0/widgets/1` | `Site Summary - System Status` |
| `Site Summary - Overview.json` | `/widgets/3` | `/dashboards/0/widgets/3` | `Site Summary - Alert Status` |
| `Site Summary - System Status.json` | `/widgets/3` | `/dashboards/0/widgets/3` | `Site Summary - Alert Status` |

The changed query appears at both of these paths relative to each widget:

```text
/configuration/table/providers/dataSource/properties/swql
/configuration/table/providers/adapter/properties/dataSource/properties/swql
```

The two query copies agree within each file. Across the files their only query-text
difference is the quoted destination dashboard name above. Overview also has a different
subtitle, both at `/subtitle` and `/configuration/header/properties/subtitle`:

| Member | Subtitle |
| --- | --- |
| Alert Status and System Status | `Order by Oldest Outage. Links go to Site - Alert Summary Dashboard` |
| Overview | `Order by Oldest Outage. Links go to Site Summary - Alert Status Dashboard` |

There are three distinct complete definitions under this key, even though Overview and
System Status have the same query. An AI must compare the whole definition, including
presentation and navigation, rather than comparing only the title or data-source query.
The different grid positions are separate placement data and do not create new widgets.

## Repeated keys with identical definitions

Two more keys occur on all three Sean dashboards with equal parsed JSON definitions:

| Widget | Repeated `unique_key` | Classification |
| --- | --- | --- |
| Active Site Alerts | `52ad9838-b1f9-4ee9-8a06-3a74c5743d0f` | Same identity, identical definition |
| Sites by Status | `751bb079-62d7-4cf3-827b-5e42dd393568` | Same identity, identical definition |

These are possible deliberate sharing, not current content conflicts. They still create
coupling: future independent edits must first receive new identities. Equality is based on
parsed JSON with object keys sorted, not a claim that whole source files are byte-identical.

For comparison, the three emcel widget identities are distinct from every Sean identity:

| emcel dashboard | Widget | `unique_key` |
| --- | --- | --- |
| Servers Summary - Alert Status | Alerts | `988f6809-bb8b-470d-b8d3-3a8bb6520f08` |
| Servers Summary - API Poller Status | API Pollers | `243bdf3c-6ed5-46a2-929c-748eb1233b18` |
| Servers Summary - Application Status | Applications | `f9498393-adf3-46c2-8e0f-8d04d40b7508` |

## Import behavior and the evidence boundary

SolarWinds documents keys as dashboard/widget identities for distributing updates, and
states that an imported dashboard with an existing key overwrites the original. Its
[import/export documentation](https://documentation.solarwinds.com/en/success_center/orionplatform/content/core-fusion-dashboard-import-export.htm)
supports treating key reuse as an update operation rather than a safe independent copy.

SolarWinds also documents linked widgets that follow their base widget and says dashboard
duplication creates linked widgets by default. Its
[clone/duplicate documentation](https://documentation.solarwinds.com/en/success_center/orionplatform/content/core-fusion-dashboard-clone-duplicate.htm)
describes **Unlink Widget** for independence. Do not assume every console copy operation
creates an independent widget.

The static files prove identity reuse and conflicting content. Exact widget overwrite
ordering, transaction behavior, and outcomes on affected customer versions are
**unverified here**. The archive ordering is not evidence of actual import ordering.
Do not claim a particular file won without before/after exports or live evidence.

## Rules for AI authors and import preflight

1. Build separate dashboard and widget identity registries across **all input files**, all
   ZIPs in the import batch, and exported target definitions. A per-file uniqueness check
   misses the All Active Alerts defect because each file is internally unique.
2. Index widget definitions by `widgets[].unique_key`; resolve every placement through that
   registry while retaining its source file and dashboard. Compare complete parsed payloads
   excluding only the identity field. Preserve array order, query text, missing versus null
   fields, data-field metadata, formatter bindings, refresh settings and links.
3. Classify repeated identities as **same key / different definition** (block a copy until
   resolved) or **same key / same definition** (require an explicit sharing decision).
   Check dashboard-key collisions separately. A new page key does not isolate its widgets.
4. For independent dashboard copies, assign new widget UUIDs per dashboard-owned definition
   and remap the associated placements. For these three Sean dashboards, full independence
   means 17 distinct widget keys instead of 11. To detach all copies from pre-existing
   versions, regenerate all 17, including the currently non-colliding widgets.
5. Use a mapping scoped by source document, dashboard and resolved definition occurrence
   when definitions under an old key differ. One package-wide `old_key -> new_key` map
   would give all three conflicting definitions the same new key and preserve the defect.
   If duplicate definitions inside a single file make placement resolution ambiguous,
   stop for an explicit placement-to-definition mapping; never guess by array order.
6. When intentional sharing is required, use one canonical definition and one key for it.
   Keep that identity stable for future updates. Generate keys when creating an independent
   object, not afresh on every import. Save a remapping manifest outside the import payload.
7. Preserve widget-local `kpi_...` component IDs and their internal references. They are not
   global widget identities. Do not replace GUIDs indiscriminately inside SWQL or URLs.
   Rename new dashboards and adjust intended dashboard-name navigation references together.
8. Compare against the target before import, then re-export both imported dashboards and
   any existing dashboards using affected widget keys. Confirm configuration and navigation,
   not just that a page exists. No offline UUID generator can certify absence on an unseen target.

A minimal repair separates the three All Active Alerts definitions and their placement
references. Fully independent publication additionally separates the two identical shared
widgets. These are different sharing policies; the audit does not silently choose one or
modify the supplied archives.

## Reproduce the package check

Run the read-only [identity auditor](../../tools/audit_dashboard_identities.py) against both
archives together. It accepts standalone JSON files too, including target exports:

```bash
python3 tools/audit_dashboard_identities.py ecmel-ModernDashboards.zip Sean-ModernDashboards.zip > identity-report.json
```

For these inputs the expected exit code is **1**, with three repeated widget keys, one
conflicting key, no cross-package repeats, and no unresolved placements. Exit 0 means no
conflicting definitions or unresolved placements in the supplied inputs; identical sharing
is still reported. Exit 2 means invalid input. The tool normalizes UUID spelling, compares
named keys exactly, rejects duplicate JSON object members and duplicate ZIP member names,
and never extracts archive files or contacts SWIS. Named-key collation on a target remains
**unverified here**. Query semantics, access permissions and runtime rendering are outside
this identity check.

The existing [dashboard validator](../../tools/check_dashboards.py) covers within-file
structure; use both tools. The identity auditor reports JSON pointers and hashes rather
than copying full query bodies or private source content into its report.

## Read-only target checks

The 2026.2 schema exposes widget `UniqueKey` through `Orion.Dashboards.Entity` and links
through `Orion.Dashboards.Links`. Bind `@widgetKeys` to the incoming key list:

```sql
SELECT TOP 1000 w.WidgetID, w.UniqueKey, w.DisplayName, w.Type, w.Configuration
FROM Orion.Dashboards.Widgets w
WHERE w.UniqueKey IN @widgetKeys
ORDER BY w.UniqueKey, w.WidgetID
```

To identify existing dashboard consumers of those widgets:

```sql
SELECT TOP 1000 l.DashboardID, l.Dashboards.DisplayName AS [Dashboard],
    l.WidgetID, l.Widgets.UniqueKey AS [WidgetKey],
    l.Widgets.DisplayName AS [Widget], l.IsReference
FROM Orion.Dashboards.Links l
WHERE l.Widgets.UniqueKey IN @widgetKeys
ORDER BY l.DashboardID, l.WidgetID
```

These queries are schema-validated, not live-tested. Page or batch results if the bound is
reached, and use an account with visibility over affected dashboards. Export those dashboards
for complete definition comparison; a configuration column alone omits other widget fields.

## Gaps in the repository import applications

At baseline commit `614cbb7`, Dashboard Porter's
[`FindCollisionsAsync`](../../apps/porter/Porter/Areas/DashboardsArea.cs)
checks dashboard keys only. (2026-10-08: the link now points at Porter's copy of the same
dashboards code, the maintained one, where
[`DashboardsProvider`](../../apps/porter/Porter/Areas/DashboardsProvider.cs) also lists
target widget keys in its dry-run plan.) Its `VerifyAsync` confirms dashboard presence, not widget
isolation. Its `AsCopy` remaps widget and dashboard keys within one definition string, but
one old widget key receives only one new key. That does not resolve ambiguous conflicting
definitions already consolidated into one payload. Batch behavior must also declare whether
identical widgets remain shared across files.

The improvement is a widget-level, batch-wide and target-aware preflight, an explicit copy
versus update mode, and post-import definition comparison. This audit adds offline detection
and documentation; it does not claim those application changes or live acceptance tests are
implemented. Test a corrected copy in a non-production target by exporting the original
dashboards before and after import and confirming their widget definitions remain unchanged.

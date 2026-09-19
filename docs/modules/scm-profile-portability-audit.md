# SCM PowerShell profiles: portability, coverage, and parser improvements

These three employee-authored profiles are collection definitions for configuration
change monitoring. They are not the tagged YAML compliance policies reviewed earlier,
and they do not contain DISA rule identities, applicability conditions, or compliance
evaluators. An importer must preserve that distinction instead of treating collected
text as a compliance result.

Prepared 2026-09-18 against repository baseline
`aec7d463c937d3a85e99ef00dcaa9590c88ab337`. Employee authorship is owner-reported;
individual authors, original SCM releases, and live results are not established.
The supplied profiles were not modified or imported, and their PowerShell was not executed.

## Evidence and inventory

[Machine-readable evidence](../../reference/scm-profile-evidence/2026-09-18.json) preserves input hashes, source
fields, field absence versus null, decoded settings, script fingerprints, and JSON
round-trip checks. [Syntax validation](../../reference/scm-profile-evidence/2026-09-18-syntax.json) records inert
PowerShell parsing; all three scripts have zero syntax errors in the local parser.
This does not prove compatibility with a particular SCM agent or PowerShell version.

| Profile | Element alias | Collection | Interval / timeout interpretation |
|---|---|---|---|
| Utility Folder Versions | File Versions | EXE version metadata beneath `C:\UTILS` | 30 minutes / 3 minutes |
| CVE-2021-44228 | Jar File Check | Text-pattern search of discovered JAR files | 12 hours / 30 minutes |
| Scheduled Task Profile | Tasks Name | Registered tasks excluding `\Microsoft\*` | 5 minutes / 1 minute |

All three files have a **UTF-16LE byte-order mark**, including the single
`Scheduled_Task_Profile.scm-profile` member of `scheduled-task-profile.zip`.
All contain one `powershell` element. Each has a distinct profile `uniqueId`:

| Profile | `uniqueId` |
|---|---|
| Utility Folder Versions | `a1b45b5f-dbe0-43cb-82e0-f532a536d9d5` |
| CVE-2021-44228 | `56ec984f-b8a7-44b3-80b2-09cc7e98829e` |
| Scheduled Task Profile | `ce741ac1-d041-49cb-bb86-613ef130b6bf` |

Utility has `version: 1` and omits `builtIn` and the element's `uniqueId`.
The other two have `version: null`, `builtIn: false`, and element `uniqueId: null`.
All have `templateMappingRules: null`. Scheduled Task has an empty profile description
and a null element description. Preserve these distinctions; do not infer defaults
from one example or interpret `version: 1` as the product release.

## Published provenance

The [Utility Folder Versions THWACK article](https://thwack.solarwinds.com/kb/articles/2104-utility-folder-versions)
describes the same purpose and links a matching filename. Its attachment returned HTTP
403 when downloaded, so byte identity with the supplied file is unverified.

Search located [Check for JAR Files (possibly) affected by CVE-2021-44228](https://thwack.solarwinds.com/kb/articles/2989-check-for-jar-files-possibly-affected-by-cve-2021-44228).
The article fetch failed and a direct request returned HTTP 403. Its publication title
is consistent with a heuristic detector, but its attachment was not compared.
No matching scheduled-task publication was found in the targeted searches.
These limits do not prevent analysis of the complete user-supplied bytes.

## Parser and import/export requirements

1. Detect encoding from the bytes, including UTF-16LE BOM. Assuming UTF-8 fails on
   all three examples. Read each complete document, rather than passing an array of
   lines to an API expecting a string. Inspect ZIP members without executing content.
2. Parse the outer JSON. `profileElements[].settings` is a **string containing JSON**,
   not an object in these files. Parse that string separately. Within it, `path`
   contains PowerShell source, despite the field's filesystem-sounding name.
3. Stop after those two JSON layers. The decoded Utility script has one actual newline;
   the CVE script has twelve. Neither has a remaining literal backslash-plus-`n`.
   Repeated unescaping or replacing backslashes can corrupt paths, quotes, and scripts.
4. Preserve the raw bytes and raw settings string alongside a parsed working model.
   Serialize edited settings back to a JSON string, then serialize the outer document.
   Retain unknown fields, nulls, missing fields, array order, and original identities.
   Reject duplicate JSON property names instead of silently discarding one value.
5. Preserve the duration strings. The observed forms are `0.0:30:0.0`, `0.0:3:0.0`,
   `0.12:0:0.0`, `0.0:5:0.0`, and `0.0:1:0.0`; their day/hour/minute/second interpretation
   gives the table above. Target acceptance of alternative spellings remains unverified.
6. Keep profile and element identifiers separate. Do not populate absent/null element
   IDs with guessed profile IDs. Compare target identities and definitions before
   deciding whether the operation is an update or a separate copy.

The repository's 2026.2 schema confirms:

| Operation | Entity | Single positional argument | Return type |
|---|---|---|---|
| `ImportProfile` | `Orion.SCM.Profiles` | `profileJson`: string | number |
| `ExportProfile` | `Orion.SCM.Profiles` | `profileId`: number | string |

`UniqueId` identifies profiles across environments. The schema describes `Version` as
the out-of-the-box profile definition version. Neither these declarations nor the
examples prove the exact overwrite behavior for every combination of same/different
name and GUID.

SolarWinds documents a copy prompt for an existing profile name in its
[UI import workflow](https://documentation.solarwinds.com/en/success_center/scm/content/scm-import-and-export-profile.htm).
Do not assume that interactive behavior applies to the API. The
[automation article](https://documentation.solarwinds.com/en/success_center/scm/content/scm-automate-scm-profile-import-or-export.htm)
uses a singular profile entity name in introductory prose; its script and the
verified schema use plural `Orion.SCM.Profiles`. Its complete demonstration also assigns
and deletes profiles, so it should not be executed as an import-only recipe.

## Utility Folder Versions: what it sees and misses

The script recursively discovers `*.exe` under a hard-coded folder, sorts by `Name`,
and selects `Name`, `FullName`, `ProductVersion`, and `FileVersion`.
It does not inventory all installed software, DLLs, signatures, hashes, or application
dependencies. A changed binary can retain the same version strings. Blank version
metadata is possible and should not be converted into a made-up version or a pass.

Documentation should require customers to choose the folder explicitly and explain
whether hidden files, reparse points, and inaccessible subfolders are in scope.
The script lacks `-Force` and explicit error reporting. Missing folders or partial
enumeration need a distinct collection status, rather than an empty baseline.
Sorting solely by filename is insufficient when different subfolders contain the same
filename. Sort by the complete path and serialize a fixed set of fields deterministically.
If integrity is the requirement, add a separately scoped hash/signature collection
design; version metadata alone does not establish integrity or authenticity.

## CVE-2021-44228: a candidate finder, not a vulnerability verdict

The script enumerates filesystem PowerShell drive roots, recursively searches for JARs,
and runs `Select-String -Pattern 'JndiLookup.class'`. The source comment calls them local
drives, but the code does not filter by drive type: provider-visible roots may include
mapped or other non-local drives, depending on the execution account.

The following limitations follow directly from the code:

- `Select-String` searches text with a regular expression. The unescaped dot matches
  another character as well as a literal period. A synthetic `JndiLookupXclass` file
  matched the original pattern. `-SimpleMatch` removes that particular false match;
  it does not make the method an archive-aware detector.
- ZIP entry names can expose the class name even when entry content is compressed.
  Therefore raw searching can find ordinary JAR candidates. It does not recursively
  inspect compressed nested JARs. Our synthetic outer JAR containing an inner JAR with
  the class did not match. WAR/EAR files are also outside the `*.jar` enumeration.
- A class-name match does not establish artifact version, vulnerable configuration,
  runtime loading, exploitability, or successful exploitation. The script never reads
  Log4j version metadata or compares affected-version ranges.
- Enumeration uses `-ErrorAction SilentlyContinue`; failures are not counted in the
  result. Content-read failures are not summarized either. A no-match message can
  accompany incomplete access. Timeouts, skipped paths, and read failures must remain
  distinct from a completed scan with no candidates.
- Full-drive scans have workload and timeout implications. Restrict roots and record
  coverage; do not respond to every incomplete scan by merely increasing its timeout.

[Synthetic probe results](../../reference/scm-profile-evidence/2026-09-18-probes.json) demonstrate the regex and
nested-archive cases using inert fixture files, not real vulnerable code or target scans.
Microsoft documents the text/regex behavior of
[Select-String](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.utility/select-string?view=powershell-7.6).

Apache's [security advisory](https://logging.apache.org/security.html) identifies
`log4j-core` and version-dependent applicability. A future collector should inspect
archive entry names and available artifact metadata, retain archive nesting paths,
and report candidate evidence separately from version classification. Bound nesting,
entry counts, bytes, and elapsed time, and record encrypted/corrupt/unreadable archives.
Use maintained vendor guidance for remediation; historical fixes for this single CVE
are not a current all-CVE upgrade recommendation. An unknown version stays unknown.

## Scheduled Task Profile: identity, configuration, and runtime are different

The decoded script is:

```powershell
Get-ScheduledTask | Where-Object { $_.TaskPath -notlike "\Microsoft\*" }
```

This excludes a folder namespace, not tasks verified to be authored or signed by
Microsoft. A custom task in that namespace is also excluded; a Microsoft task elsewhere
can remain included. The alias `Tasks Name` does not select only task names. The script
returns task objects with no explicit projection, sorting, or serialization.

Microsoft's [Get-ScheduledTask documentation](https://learn.microsoft.com/en-us/powershell/module/scheduledtasks/get-scheduledtask?view=windowsserver2025-ps)
describes task-definition objects. What SCM ultimately renders from these objects must
be verified on the target. Do not claim that the default display captures every action,
argument, trigger, principal, and setting. Names alone are not unique across task folders.

For configuration monitoring, identify each task by `TaskPath` plus `TaskName`, sort
by that pair, and explicitly capture actions, arguments, working directories, triggers,
principal, run level, and settings. Consider
[Export-ScheduledTask](https://learn.microsoft.com/en-us/powershell/module/scheduledtasks/export-scheduledtask?view=windowsserver2025-ps)
for XML definitions, with deterministic serialization and output-size checks.
Separate transient state and execution history from configuration drift.
[Get-ScheduledTaskInfo](https://learn.microsoft.com/en-us/powershell/module/scheduledtasks/get-scheduledtaskinfo?view=windowsserver2025-ps)
provides run-time information if that is an additional requirement.
Document the Windows ScheduledTasks module and execution account's visibility as prerequisites.

## Shared output contract and live acceptance tests

SCM monitors changes in collected script output, as described in
[profile element types](https://documentation.solarwinds.com/en/success_center/scm/content/scm-element-types.htm).
Use stable ordering and explicit fields so that formatting or enumeration order does not
produce false changes. Keep scan timestamps and volatile execution values out of the
configuration payload when they would cause a change on every poll.

SolarWinds' [PowerShell support page](https://documentation.solarwinds.com/en/success_center/scm/content/scm-powershell-script.htm)
states that overlapping execution of the same element is skipped and mentions preserving
4,096 output characters. Treat this as a documented capacity concern to test, not proof
of a universal hard limit across releases. Test long paths, large inventories, and output
near and beyond that size. Verify host versus success-stream capture, especially the
CVE script's `Write-Host` messages. Explicitly serialize data instead of trusting default
table width, which may hide or truncate fields.

Proposed acceptance matrix before shipping an importer or revised profile:

| Area | Required observation |
|---|---|
| Import/export | Preserve both JSON layers, missing/null fields, script text, and settings through target re-export |
| Identity | Test same name/same GUID, same name/new GUID, new name/same GUID, and deliberate copy; inspect returned and exported IDs |
| Collection | Verify actual SCM agent PowerShell version, account, prerequisites, and supported durations |
| Errors | Distinguish successful empty result, missing folder/module, access denial, partial scan, timeout, and truncation |
| Versions | Same EXE filename in two folders, absent metadata, version change, and binary change with unchanged version |
| JAR detection | Direct class entry, similar text, nested JAR, WAR/EAR, corrupt/unreadable archive, unknown version, and known fixed artifact |
| Tasks | Duplicate names in different folders, action/argument/trigger/principal changes, excluded namespace, and transient state change |
| Stable output | Two unchanged polls produce identical configuration content; one intended configuration change produces a meaningful diff |

## Guidance for AI authors and importers

Route these JSON collection profiles separately from the
[SCM compliance policies](scm-compliance-policies.md) and the
[earlier tagged-YAML audit](scm-policy-portability-audit.md).
Preserve the source evidence and both JSON layers. Do not turn a no-match message,
an incomplete collection, or unchanged output into a compliance pass. Changes to the
collector's scope or output fields change what its baseline means; document them and
validate the resulting diff before customers adopt a new baseline.

The [SCM module guide](scm.md) supplies the broader entity and result model.
Keep unverified runtime behavior explicit when generating import code or revised profiles.

The offline checks completed here establish valid structure, distinct supplied profile
IDs, syntactically valid scripts, and two specific detector limitations. Target imports,
output rendering, identity conflict behavior, and live assessment accuracy remain unverified.

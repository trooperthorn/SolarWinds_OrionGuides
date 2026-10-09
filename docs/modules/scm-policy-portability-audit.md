# SCM policy portability and DISA comparison: three-policy audit

The supplied SCM policies contain authored collection and evaluation logic that cannot be
reconstructed merely by copying a STIG title, check, and fix. Preserve that logic as a
typed YAML graph, retain historical DISA identities, and report manual or partial checks
without converting them into a pass. Importing a policy and validating its assessment
behavior are separate operations.

## Evidence and validation boundary

This audit reads the owner-supplied `SCM-Policies.zip`, SHA-256
`52efdebf42f85b80155dc8affa390d62bb90967248d929e442ddf625086db7a8`.
Its three filenames and policy names identify historical STIG releases. They do not
identify the exporting SCM version; that version was not supplied. Follow-up comparison
confirmed that all three files are byte-identical to the YAML attachments on SolarWinds'
THWACK policy pages. The supplied bytes therefore match those published artifacts;
this does not establish a customer's deployment history or runtime results.
The repository baseline is `2e36a2d4c3e4beb3f8622a839bbdb30c1ef2967a`.
Schema claims were checked against the repository's 2026.2 contract.

[Policy evidence](../../reference/scm-policy-evidence/2026-09-18.json) contains hashes,
field/tag inventories, rule paths, dependency references, status translations, collection
source fingerprints, and offline converter probes.
[Source crosswalk](../../reference/scm-policy-evidence/2026-09-18-disa-crosswalk.json)
contains package provenance, benchmark metadata and every policy rule's identity match.
Paths such as `/rules/0` are zero-based YAML traversal paths, not SWIS identifiers.

YAML was composed using inert tagged nodes; no custom constructors, exported PowerShell,
database queries, import verbs, assignments, or live rule evaluations were run. All three
documents passed a serialize/compose comparison preserving node tags, scalar values and
types, ordering, and alias-sharing relationships. This is structural evidence, not a
live SCM import/export certification. The official packages were parsed independently
and with the current Python loader; benchmark/rule counts agreed for all three packages.

## Policy inventory and intentional coverage limits

| Policy label | Rules | Preconditions | Explicitly disabled | Named exclusions in policy description | Direct matches to downloaded source |
|---|---:|---:|---:|---:|---:|
| IIS 8.5 Server STIG V1R10 | 18 | 1 | 0 | 26 | 18 |
| SQL Server 2016 Instance STIG V1R9 | 79 | 1 | 0 | 38 | 51 |
| Windows Server 2016 STIG V1R10 | 236 | 97 | 4 | 36 | 234 |
| Total | 333 | 99 | 4 | 100 | 303 |

The 100 exclusion IDs are extracted from the policy descriptions. None also appears as
a top-level rule in the same supplied policy. Preserve these declarations separately from
assessment results; neither an omitted requirement nor a disabled rule proves compliance.
Exact coverage against the stated V1 releases remains unverified pending those releases.

### Published policy provenance and coverage

The owner supplied the three THWACK publication URLs. On 2026-09-18, all three linked
YAML attachments were downloaded and their SHA-256 hashes matched the corresponding
files in `SCM-Policies.zip` exactly. Each article explicitly lists rules **not included**;
those lists match the YAML descriptions with no additions or omissions:

| Published SCM policy | Included rules in identical YAML | Published exclusions |
|---|---:|---:|
| [Windows Server 2016 V1R10](https://thwack.solarwinds.com/kb/articles/2101-windows-server-2016-stig-version-1-rel-10) | 236 | 36 |
| [IIS 8.5 Server V1R10](https://thwack.solarwinds.com/kb/articles/2103-iis-8-5-server-stig-version-1-rel-10) | 18 | 26 |
| [SQL Server 2016 Instance V1R9](https://thwack.solarwinds.com/kb/articles/2102-microsoft-sql-server-2016-instance-stig-version-1-rel-9) | 79 | 38 |

This closes the publication-provenance gap and corroborates the 100 declared exclusions.
The article lists are exclusions, not a list of checks the policy performs. Use the
attached YAML's actual rule graph as the implementation source, retaining disabled rules,
preconditions and manual-review translations. Preserve article/attachment URLs and hashes
in the parser's source manifest. Publication provenance does not make an old policy
equivalent to a newer DISA benchmark or guarantee that every included rule is automated.

SolarWinds documents its policies as selected automatable subsets. Preconditions determine
applicability; Unknown may represent partial/manual evaluation even without a polling
error. Disabled and Not Applicable rules are excluded from some compliance summaries.
These distinctions explain why a single pass/fail Boolean is insufficient.
[SolarWinds policy-engine documentation](https://documentation.solarwinds.com/en/success_center/scm/content/scm-monitor-compliance-using-the-scm-policy-engine.htm).

## Matching official sources and historical identities

The live [DISA catalog](https://www.cyber.mil/stigs/downloads/) was accessed on 2026-09-18
using its browser search and Download controls. The text-only web fetch returned an empty
application shell. SQL Server and Windows Server packages downloaded successfully.
The IIS search returned IIS 10.0, which is not a substitute for IIS 8.5.

| Policy family | Downloaded reference | Provenance and limitation |
|---|---|---|
| SQL Server 2016 Instance | [DISA SQL Server 2016 Y26M04 ZIP](https://dl.dod.cyber.mil/wp-content/uploads/stigs/zip/U_MS_SQL_Server_2016_Y26M04_STIG.zip): Instance V3R6, 84 rules | Catalog upload 2026-04-07; Instance benchmark date 2026-01-05. The same ZIP includes Database V3R5, 23 rules. Keep Instance and Database identities separate. |
| Windows Server 2016 | [DISA Windows Server 2016 V2R10 ZIP](https://dl.dod.cyber.mil/wp-content/uploads/stigs/zip/U_MS_Windows_Server_2016_V2R10_STIG.zip): 273 rules | Catalog labels it Sunset, uploaded 2025-01-23; benchmark date 2025-01-15. Preserve lifecycle status independently of benchmark identity. |
| IIS 8.5 Server | [NIST-listed NIWC Atlantic download](https://ncp.nist.gov/checklist/774/download/18738): IIS Server V2R7 enhanced SCAP 1.4, 43 rules | Government-authored supplemental SCAP, not the original DISA manual package. Source reports enhanced version `002.007.013`, date 2026-08-26, based on DISA V2R7 dated 2023-10-25. |

The NIWC ZIP SHA-256 matches the hash displayed by NIST:
`3b2f7aa396dbfc647b73de8f7506a5bca1578ff5b79f96d40d13859da57613e4`.
Its content was parsed but its embedded signature was not cryptographically validated.
The 43 IIS rules plus the other three benchmark components total 423 source rules.

All 303 matched policy rules resolve through explicit `ident` values with the source
system ending in `/legacy`, within the correct product benchmark. The crosswalk records
the legacy display ID, current Group/Rule identifiers, STIG ID, severity, CCIs, package
and member. It does not guess from titles or reuse a V-number across product families.
Seven matched SQL rules differ in severity from the later source; preserve both versions
and require review before updating customer policies.

Thirty supplied rules do not match identifiers in these later references: 28 SQL Server
and two Windows Server rules (`V-73441`, `V-73443`). Absence from a later release does not
establish retirement, a merge, or incorrect SCM logic. The machine-readable crosswalk
lists every unmatched ID; none is silently discarded or assigned a guessed successor.

### Owner-supplied newer packages and migration coverage

The owner could find only newer DISA editions. The supplied SQL Server Y26M04 and Windows
Server V2R10 ZIPs are byte-identical to the previously downloaded packages above, so the
303 matches and 30 unmatched original rules are unchanged. Historical packages are optional
additional evidence; their absence does not block documenting or preserving published SCM
logic. Keep the exact historical-source comparison explicitly unresolved.

The supplied `U_MS_IIS_10-0_Y26M07_STIG.zip` contains two distinct benchmarks:

| Benchmark | Version/release | Benchmark date | Rules |
|---|---|---|---:|
| IIS 10.0 Server | V3R7 | 2026-04-01 | 40 |
| IIS 10.0 Site | V2R16 | 2026-07-01 | 44 |

These are migration references for a different IIS product version. Neither contains an
explicit legacy-ID link to any of the 18 included IIS 8.5 rules. Do not insert them into
the same-family crosswalk or reuse executable IIS 8.5 checks based on similar titles or
shared CCIs. Select Server versus Site explicitly; review platform applicability, check
and fix instructions, collection paths and evaluation behavior before producing a new
SCM policy. The package filename's quarterly label is not each inner benchmark's date.

A reverse coverage view of the existing same-family references reveals requirements that
need review beyond merely updating the included legacy rules:

| Later reference | Linked to included SCM rules | Linked to declared exclusions | Neither |
|---|---:|---:|---:|
| NIWC enhanced IIS 8.5 Server V2R7 | 18 | 23 | 2 |
| DISA SQL Server 2016 Instance V3R6 | 51 | 31 | 2 |
| DISA Windows Server 2016 V2R10 | 234 | 36 | 3 |

These counts classify later-reference rules by explicit legacy identifiers. No rule maps
to both categories in these inputs. The seven entries in Neither are review gaps, not
proof of newly introduced requirements; missing history can also explain missing links.
The crosswalk records every later-reference rule and its category. Keep source policy
inclusion/exclusion, target-reference coverage and actual assessment status separate.

### Historical-source limitation

The [NIST historical IIS download record](https://ncp.nist.gov/checklist/774/download/5925)
points to `U_MS_IIS_8-5_Y20M04_STIG.zip`; a direct request to that official DISA URL returned
HTTP 404. The archive itself was unavailable, so its precise contained release was not
verified. Exact comparison against the policy labels would require these manual STIG
ZIPs containing XCCDF, preferably with revision histories, if they become available:

- Microsoft IIS 8.5 **Server** STIG, Version 1, Release 10.
- Microsoft SQL Server 2016 **Instance** STIG, Version 1, Release 9.
- Microsoft Windows Server 2016 STIG, Version 1, Release 10.

The THWACK provenance and later-reference comparisons can be used while these remain unavailable.
Do not substitute IIS Site for Server, SQL Database for Instance, or enhanced SCAP for
an exact historical manual baseline without recording the distinction.

## Observed YAML grammar and portability requirements

All three inputs are UTF-16LE with a BOM and have the root tag `!policy`. Their top-level
fields are exactly `name`, `uniqueId`, `pluginName`, `description`, and `rules`.
They omit top-level `version` and `builtIn`; every rule omits `checkText`.
Do not confuse the STIG version embedded in the name with the policy serialization/version
field, or fill missing fields with values copied from a different export.

There are 292 alias references: 16 IIS, 174 SQL, and 102 Windows. Count distinct graph nodes
separately from references to them. Preserve shared nodes when exporting; do not promise
that a YAML alias alone establishes a particular runtime collection count or schedule.

| Observed tags | Meaning to preserve and validate |
|---|---|
| `!policy` | Root policy identity and ordered rule list. Preserve original policy and rule GUIDs during archival round trips. |
| `!all`, `!any`, `!none` | Nested combinators with sequence-valued `of`. Preserve order and every nested condition; validate evaluation against the target engine. |
| `!equals`, `!notEquals`, `!matches`, `!exists`, `!notExists` | Typed expected values, expressions and source relationships. Keep empty string, absent value, Boolean, integer, and string distinct. Do not normalize all scalars to strings. |
| `!isLessOrEquals`, `!isGreaterOrEquals`, `!isGreaterThan` | Numeric comparison operators omitted from the earlier IIS-only guidance. Conversion/coercion behavior requires live fixtures. |
| `!translate` | Mapping-valued `of` containing a child condition, plus an ordered `status` sequence of `when`, `then`, and optional `statusDescription`. This differs from combinator `of` lists. |
| `!rule` | A dependency referring to another rule by `displayId`; resolve within the policy and retain ordering/dependency information. |
| `!scm.registry` | Full registry key and value name. Preserve path spelling and scalar types. |
| `!scm.powershell` | Script and description. Preserve scripts byte-for-byte at the decoded-text level, with raw-file hashing for archival fidelity. Do not execute them during parsing. |
| `!scm.databaseQuery` | Query, description, and connection string. Preserve macros and SQL result-shape assumptions; resolve target credentials separately. |

There are 332 distinct PowerShell source nodes, 95 registry source nodes, and 112 database
query source nodes across the three documents. All 112 database connection strings include
the macros `${NodeIP}`, `${Username}`, and `${Password}`. Preserve these placeholders;
do not expand them into exported credentials. The archive does not establish a customer's
credential assignment or prove that a database query runs through a node agent.
[SolarWinds database collection documentation](https://documentation.solarwinds.com/en/success_center/scm/content/scm-gsg-monitor-sql-database.htm).

### Status translations and rule dependencies

The 69 translation nodes contain 70 transitions: 62 Failed-to-Unknown, seven
Passed-to-Unknown, and one Failed-to-Passed. One SQL translation has two mappings.
These are explicit source semantics, not universal remappings of policy statuses.

For SQL rule `V-79213`, the underlying condition matches a volume-management privilege
assignment. Its translation maps a match to Unknown and a nonmatch to Passed. Removing
the wrapper would change the assessment meaning. Windows translations can attach a
specific explanation of the manual review still required. Retain `statusDescription`.

The five rule references are all resolvable in the supplied Windows policy:
`V-73299` references `V-78125`; `V-78123` references `V-73299`; and `V-73249`, `V-73251`,
and `V-73253` reference `V-73673`. Renumbering display IDs therefore also requires an
explicit dependency migration. Validate missing references and cycles in future input;
do not treat an unresolved reference as an inapplicable or passing rule.

## Verified gaps in the current conversion tool

The existing Python path correctly reads each supplied UTF-16 file and its preview counts
18, 79, and 236 top-level rules. Individual policy import passes the text through without
rebuilding the condition tree. That preservation is useful and should remain available.
The following observations do not imply that every current import loses logic.

| Gap | Evidence and required change |
|---|---|
| A ZIP of SCM YAML is treated as an XCCDF package | Offline `load_benchmarks` on this archive raises `no XCCDF benchmark found inside`. Detect member formats and plan individual SCM policy imports; reject or explicitly separate mixed module bundles. |
| Preview uses regular expressions rather than a YAML tree | A valid indented rule sequence reports zero rules; an escaped quoted policy name is not decoded correctly. Use an inert tagged-node parser for names, identities, counts and validation. |
| Collision preflight checks only Name (addressed, see the 2026-10-08 status below) | `import_scm_policy` queries Name, not UniqueId; the PowerShell YAML path does the same. SolarWinds documents rejection when either matches. Check both and report conflicts without automatically deleting existing policies. |
| Import return value is not sufficient verification (partly addressed, see below) | A mocked numeric zero is accepted because Python checks only `None`; no exported content is read back. Require a valid returned identity and verify the resulting policy/rule graph with server data before reporting complete import. |
| Generated XCCDF policies are manual-review sentinels | `xccdf_to_scm_yaml` creates a PowerShell probe printing False and a condition expecting True. It does not compile the authored registry/database/translation/dependency graphs in these policies or execute OVAL. Preserve the distinction between a draft review task and an automated check. |
| Source identity and revision model is incomplete | Generated rule GUIDs derive from revision-bearing XCCDF Rule IDs; a source revision can produce new IDs. Preserve legacy aliases and reviewed old-to-new mappings instead of relying on GUID regeneration. |
| SCAP parsing is lossy | The IIS SCAP rule counts load, but existing XCCDF parsing retains only a limited check/reference representation. Preserve check systems, references, profiles, data-stream components and supplemental author/version before deciding what is supported. |

Python failures above were reproduced offline using fake SWIS responses, with no network
mutation. PowerShell collision behavior is from source inspection. No claim is made that
the server itself returns zero or that the current supplied YAML triggers the preview
formatting bug. Source: `apps/disa-stig-conversion-tool/disa_stig_tool.py` functions
`scan_scm_policy`, `load_scm_policy`, `import_scm_policy`, `load_benchmarks`, and
`xccdf_to_scm_yaml`; PowerShell's existing-YAML import branch.

**Status on 2026-10-08.** The table above records the tool as audited. Two rows have
since changed:

- Both editions now query `Name` **and** `UniqueId` before `ImportPolicy` and refuse
  either match without touching the existing policy. The PowerShell `uniqueId` match
  missed files with CRLF line endings until 2026-10-08, when it began normalizing line
  endings first; it also now refuses text that is not a `!policy` document.
- Both editions read the rule count back from `Orion.PolicyEngine.Rule` after
  `ImportPolicy` and fail when it is zero, so a returned id of 0 fails the same way
  unless a policy with that id exists. This is not the full verification the row asks
  for: the count is not compared with the file and no exported content is read back.

**Status on 2026-10-09 (DISA STIG tool 2.0.0).** For generated XCCDF policies:

- The "Generated XCCDF policies are manual-review sentinels" row stands. The tool still
  does not emit `!translate`: this audit describes the node's structure in prose (above)
  but records no exact serialized example, so a generated Failed-to-Unknown wrapper would
  be untested guesswork, and an un-reviewed generated rule keeps reporting Failed.
- The "Source identity and revision model" row is partly addressed: each generated rule
  now keeps its legacy V- and SV- identifiers, its Group's SRG id and every description
  pseudo-section in the rule description, and every Rule of a multi-rule Group is
  converted. Generated uniqueIds still derive from the revision-bearing rule id plus the
  version suffix; reviewed old-to-new mappings remain open.
- The "SCAP parsing is lossy" row is unchanged, apart from deduplication: one benchmark
  keeps its highest release, and a benchmark present only in its SCAP edition is a
  logged warning.
- Generated YAML now escapes DEL, the C1 controls, U+2028, U+2029, U+FEFF, U+FFFE and
  U+FFFF inside quoted scalars, and both editions write it with LF line endings.

The offline tests in `apps/disa-stig-conversion-tool/test_disa_stig_tool.py` cover the
CRLF case and the refusal of SCM collection profiles (`.scm-profile` JSON), which the
tool previously routed to `ImportPolicy` by extension. The remaining rows stand.

**Status on 2026-10-09 (DISA STIG tool 2.0.0).** Two more rows have changed in part:

- *Source identity and revision model.* The generated policy and rule `uniqueId`s are
  still uuid5 values of the benchmark id and the revision-bearing XCCDF Rule ID, now
  followed by a version suffix (`--suffix`, `_v1` by default) that also ends the policy
  name. Before importing converted STIGs, both editions refuse when a policy name, policy
  `uniqueId` or any rule `uniqueId` already exists and suggest the next free suffix, so a
  new release is imported next to the old one with fresh identities. Whether SCM itself
  rejects a rule `uniqueId` used by another policy remains **Unverified**; the tool checks
  it anyway. This does not provide the legacy-alias mapping the row asks for.
- *Manual-review sentinels.* The probe now comes from a per-OS table. Windows STIGs keep
  the `!scm.powershell` attestation; Linux STIGs stay routed to SCM with the same probe,
  labeled **Unverified** because no SCM policy source for Linux nodes is documented here,
  with a logged warning and a test procedure in the tool README. `--scm-probe-template`
  replaces the source block per run; the template is validated as a small tagged-YAML
  fragment, and its `{id}` placeholder receives only the validated vulnerability id,
  inside a quoted value. Generated policies are still draft review tasks, not compiled
  automated checks.

## Field mapping and import acceptance contract

| Input / source field | Parser and target handling |
|---|---|
| SCM `uniqueId`; DISA benchmark and rule identities | Keep portable SCM GUIDs separate from destination `PolicyID`/`RuleID`. Retain original and legacy DISA IDs in a sidecar manifest. |
| SCM `displayId` | Maps to the rule's display identifier and is also used by `!rule`; do not rewrite it without migrating dependencies. |
| SCM `name`, `description`, `remediationDescription`, optional `checkText` | Preserve source fields and absence. XCCDF title/discussion/fix/check are candidates for new policy prose, not instructions to overwrite an existing authored rule. |
| SCM `severity` | Retain High/Medium/Low words in YAML; schema values are 300/200/100. Flag source-version differences for review. |
| SCM `precondition`, `condition` | Retain the full tagged graph; the schema exposes `PreconditionYAML` and `ConditionYAML` as strings. Those columns do not by themselves specify all tag semantics. |
| SCM `enabled` and status translations | Preserve explicit false and omitted values separately; do not infer runtime defaults without a target export/read-back. Preserve manual/Unknown reasons. |
| XCCDF check, fix, profile and referenced component data | Preserve all source content first; use reviewed collection/evaluation adapters and fixtures for any supported automation. Unsupported checks remain explicit manual work. |
| Policy assignment and credentials | Separate deployment configuration from portable rule content. Do not infer a node assignment from the policy's product name. |

The documented 2026.2 verbs are `ExportPolicy(policyId)` returning a YAML string and
`ImportPolicy(yaml)` returning a numeric policy ID on `Orion.PolicyEngine.Policy`.
Use the document text as the import parameter. SolarWinds documents that duplicate name
or unique ID prevents import; the earlier claim that ImportPolicy simply creates duplicates
should not guide a converter. Server behavior for optional fields and custom logic still
requires target-version verification.

Before implementation is considered complete:

1. Reproduce the three-policy, 333-rule inventory, 292 aliases, 69 translations and five
   dependencies. Preserve the 100 declared exclusions separately from rules.
2. Round-trip tagged graphs including scalar types and absence, and verify duplicate-key,
   unknown-tag, cyclic-alias, unresolved-reference and archive-path rejection behavior.
3. Test registry values, missing values, script errors, SQL connection failures, zero/multiple
   result rows, manual/Unknown translations and rule dependencies on a nonproduction target.
4. Verify duplicate Name and UniqueId handling, exported rule identities and content, and
   partial-failure reporting. Do not assign or evaluate automatically merely to test parsing.
5. Pin historical source packages before claiming exact release coverage. Preserve the
   Windows sunset label and separate NIWC enhanced IIS content from DISA manual guidance.
6. Reproduce the three THWACK attachment hashes and exclusion lists. Preserve later-reference
   coverage categories, and require a reviewed migration plan for IIS 8.5 to IIS 10.0
   rather than treating a product-version change as a source-release refresh.

This proposal changes documentation and evidence only. The structural round trips and
offline probes passed or reproduced the stated gaps; target-server tests and parser
implementation remain outstanding.

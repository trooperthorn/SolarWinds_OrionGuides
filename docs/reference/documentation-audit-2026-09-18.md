# Documentation audit and evidence rules: 2026-09-18

This audit corrects stale and overconfident guidance, reduces repeated explanations,
and makes unresolved behavior easier for people and AI systems to identify.
The starting commit is `135480f265ac91cb065e5f06c5733730273ebe52`.

## Coverage and limits

The baseline inventory contains 144 tracked Markdown/text files, excluding the generated
`llms-full.txt` duplicate. Nine have generated content; 135 are authored or supporting
prose. Every inventoried file received a wording/version/uncertainty scan. Selected
claims were then inspected in context against local code, the 2026.2 schema, supplied
export audits, or primary documentation. The per-file record is in
[the coverage manifest](../../reference/documentation-audit/2026-09-18.json).

This is repository-wide screening plus targeted verification, not independent proof of
every sentence. Generated reference data is checked through the repository gate. Source
workbooks and historical evidence remain attributed to their original sources. This
review did not run a SolarWinds server, import packages, execute device checks, rebuild
all desktop apps, or re-fetch every external link. Pages without edits are not thereby
certified current. The static schema baseline remains 2026.2.

## Evidence rules for AI answers

| Evidence | What it supports | What it does not establish |
| --- | --- | --- |
| Versioned schema/Swagger | Names, types, declared operations, rights, positional signatures | Successful invocation, payload semantics, side effects, installed licenses |
| Official feature documentation/release notes | Behavior or support stated for the named release and feature | Every release, every provider, or undocumented boundary cases |
| Supplied export | The exact observed structure, identifiers, values, and relationships | A universal file specification, importer collision behavior, or safe execution |
| Local source code | What that implementation checks or attempts | That its UI/API calls succeeded on a target installation |
| Recorded runtime test | Observed result for its version, account, inputs, and environment | Other versions, accounts, devices, or untested failure paths |
| Community report | An attributed example or practitioner observation | A vendor contract or universal default |
| Inference | A hypothesis with its reasoning and scope stated | A verified fact |

Use **Unverified:** for a material unresolved claim. State what is unknown, why the
available evidence does not settle it, and what observation would settle it. Reserve
**Unknown:** and **Not tested:** for explicit evidence labels; a status enum named
Unknown is not itself an uncertainty claim. Do not use "always", "never", "silently",
"safe", or "fully verified" unless the cited evidence supports that scope.

A missing schema relationship does not prove missing database constraints. A missing
verb does not prove no UI/private implementation exists. An exposed entity does not
prove a license entitlement. Static validation, import success, content read-back, and
correct runtime evaluation are separate checks.

## Findings addressed

| ID | Finding | Correction and reference |
| --- | --- | --- |
| DOC-01 | REST migration compressed into a single date; connection failure treated as a version diagnosis | Distinguish 17774 introduction in 2023.1 from default 17778 listener cessation in 2024.2; retain service/network alternatives in [connecting](../swis/connecting.md) and troubleshooting |
| DOC-02 | Selected timestamp offset evidence generalized into a guaranteed predicate bug | Rewrote [date/time](../swql/date-and-time.md), separated serialization from filtering, removed count-only proof, and qualified repeated advice in module/automation pages |
| DOC-03 | Local calendar subtraction presented as guaranteed elapsed hours | Marked daylight-saving boundaries and recommended fixed UTC parameters for exact elapsed windows; preserved existing heading links |
| DOC-04 | Missing URI claimed to prohibit reporting; read-only writes claimed to fail silently | Scoped URI restrictions to URI-addressed operations and removed undocumented failure behavior in [entity model](../schema/entity-model.md), CRUD, and metadata guidance |
| DOC-05 | Missing navigation claimed to prove credential orphaning or module absence | Marked deletion/cascade behavior unverified; separated provider registration, installation, and entitlement in credential and relationship guides |
| DOC-06 | SCM overview still said no real exports were available | Linked the observed JSON profile and tagged-YAML policy audits in [SCM](../modules/scm.md); preserved the unresolved import-format contract conflict |
| DOC-07 | Dashboard tools' README overstated identity isolation and read-back | Documented dashboard-only target collision queries, per-document remapping, duplicate warnings, and incomplete resource verification in both [Porter](../../apps/porter/README.md) and [DashboardPorter](../../apps/dashboard-porter/README.md) |
| DOC-08 | Administrator elevation attributed to an unspecified DISA STIG | Described the manifests as application choices; removed unsupported compliance authority |
| DOC-09 | Product deprecations and a patch-specific scheduler fix omitted | Added [release support notes](../platform/versions-and-naming.md#release-specific-support-notes) and [scheduling](../automation/scheduling.md#release-specific-scheduling-behavior) guidance |
| DOC-10 | Community status values described as authoritative for 2026.2 | Restored [status table provenance](../schema/status-codes.md) and distinguished shared status names from module-specific enums |
| DOC-11 | Historical IPAM CRUD prefix range generalized to every current creation path | Attributed the 4.7 source and marked its conflict with the /21 verb example and current behavior unresolved in [IPAM](../modules/ipam.md) |
| DOC-12 | Inline exported password claimed to avoid shell history | Replaced it with an interactive read and stated environment-variable limits in [curl examples](../../scripts/curl/README.md) |
| DOC-13 | Deterministic sorting implied stable pagination during concurrent writes | Added the lack-of-snapshot caveat to [REST paging](../swis/rest-api.md) |
| DOC-14 | Global claims of exhaustive schema/prose verification; outdated contribution instructions | Updated the root/AI indexes and contribution guide to describe actual check coverage and authorized export evidence |
| DOC-15 | Uncertainty index collected headings and missed explicit evidence labels | Removed heading-only findings, recognized explicit labels, and added regression tests; documented collection boundaries in [unverified](unverified.md) |
| DOC-16 | Verbose introductions and repeated universal explanations obscured scope | Shortened date/time, web-console, contribution, IPAM, and app packaging prose while retaining signatures, examples, and provenance |
| DOC-17 | Namespace presence treated as a licensing answer; polling described as universally pull-based | Scoped cloud/SRM availability claims and corrected the agent introduction |

## Primary sources rechecked

Accessed 2026-09-18. Use the linked pages for their complete version scope.

- [SolarWinds SDK REST reference](https://solarwinds.github.io/OrionSDK/docs/rest/): endpoint introduction and legacy port context.
- [SAM 2024.2 release advisory](https://documentation.solarwinds.com/en/success_center/sam/content/release_notes/sam_2024-2_release_notes.htm): default 17774 migration and 17778 listener change. Its older deprecation paragraph should be read with that specific advisory.
- [SDK date-function issue](https://solarwinds.github.io/OrionSDK/docs/swql-functions/possible-issues/): selected-value serialization example and conversion workaround; no predicate comparison experiment or affected-version matrix.
- [Microsoft DATEADD](https://learn.microsoft.com/en-us/sql/t-sql/functions/dateadd-transact-sql) and [datetimeoffset](https://learn.microsoft.com/en-us/sql/t-sql/data-types/datetimeoffset-transact-sql): arithmetic and timezone type distinctions. These do not establish SWQL provider behavior or add T-SQL syntax to SWQL.
- [Platform 2026.2 release notes](https://documentation.solarwinds.com/en/success_center/orionplatform/content/release_notes/solarwinds_platform_2026-2_release_notes.htm): product deprecations, separate from schema obsolescence flags.
- [Platform 2026.2.2 release notes](https://documentation.solarwinds.com/en/success_center/orionplatform/content/release_notes/solarwinds_platform_2026-2-2_release_notes.htm): maintenance-schedule restart fix, case 02159789.
- [IPAM 4.7 API](https://solarwinds.github.io/OrionSDK/docs/ipam-4-7-api/): historical CRUD restriction and differing verb example.
- [Cloud monitoring requirements](https://documentation.solarwinds.com/en/success_center/orionplatform/content/core-cloud-requirements.htm): feature-specific prerequisites, including the listed Self-Hosted license for GCP.

Local evidence includes `data/schema/2026.2/`, [data provenance](../../data/README.md),
[the Makefile](../../Makefile), and the source files linked in the application READMEs.
No source document's embedded instructions were treated as authorization to execute code.

## Unresolved areas and how to close them

| Area | Evidence still needed |
| --- | --- |
| Timestamp semantics | Known event instants, raw timestamps, fixed bounds, and DST boundary tests on the target release/provider |
| Shared dashboard widgets | Target widget inventory and before/after exported resource comparison, including dashboards outside the import package |
| SCM policy/profile import | Target-version JSON/YAML acceptance, identity collision tests, assignment and evaluation read-back |
| NCM/STIG conversion | Full rule semantics and dependency preservation, valid device/config scope, manual-check handling, and evaluation against known passing/failing configs |
| Device Studio | Export/import acceptance and discovery matching on supported firmware; no published 2026.2 SWIS file import/export contract was established by the earlier audit |
| Credential deletion | Lab tests for each consumer's deletion guards, cascades, and dangling-reference behavior |
| IPAM creation limits | Separate CRUD/verb tests for the intended prefix and installed release |
| UI conventions and licensing | Product-version documentation and target tests; schema presence alone is insufficient |
| External API templates | Vendor endpoint/auth/schema checks against the actual tenant/version; experimental templates retain that designation |

**Unverified:** these runtime outcomes remain unresolved by this documentation audit.
The [uncertainty index](unverified.md) retains the narrower per-page questions and probes.

## Validation boundary

The repository's `make check` is the acceptance gate for this change. It checks local
artifacts and examples, not a connected platform. Review the final audit report for the
recorded result. Do not translate a green static gate into "tested live" or "all claims
verified". This update documents application gaps; it does not implement the missing
importer safeguards or change the shipped applications.

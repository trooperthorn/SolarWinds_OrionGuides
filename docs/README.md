# Documentation

Guidance for SolarWinds Orion / Observability Self-Hosted, organized by what you are
trying to do.

If you are new to the platform's API, read [swis/README.md](swis/README.md) then
[swql/README.md](swql/README.md), in that order. If you are here to look something up,
jump to [reference/](reference/README.md).

The full section-by-section index (every page, organized by topic) lives in
[llms.txt](../llms.txt) at the repository root. It is kept there rather than duplicated
here so there is one index to update, not two, and so AI systems reading this repository
find the same map a person browsing `docs/` does. [TOC.md](TOC.md) goes one level deeper:
every heading on every page with a one-sentence summary, generated from the pages
themselves, for jumping to a section rather than a file.

## Sections

| Section | Covers |
| --- | --- |
| [platform/](platform/README.md) | What the product is: architecture, modules, versions and naming |
| [swis/](swis/README.md) | The API: connecting, REST, CRUD, URIs, Invoke, introspection |
| [swql/](swql/README.md) | The query language: reference, functions, joins, date/time, gotchas |
| [schema/](schema/README.md) | The data model: entities, inheritance, relationships, key entities |
| [modules/](modules/README.md) | One page per module: NPM, SAM, NCM, NTA, IPAM, VMAN and the rest |
| [automation/](automation/README.md) | Task guides: node lifecycle, maintenance, alerts, discovery, pollers |
| [polling/](polling/README.md) | The five polling systems, and why a new node monitors nothing |
| [webui/](webui/README.md) | The web console: variables, widgets, dashboards, change templates |
| [guides/](guides/getting-started.md) | Start to finish: getting started, cookbook, troubleshooting, integrations |
| [reference/](reference/README.md) | Generated enumerations: every entity, verb, prefix, status, function |

## Working examples

Runnable code lives outside `docs/`: [../scripts/swql/](../scripts/swql/) has 239 verified
sample queries, [../scripts/powershell/](../scripts/powershell/),
[../scripts/python/](../scripts/python/) and [../scripts/curl/](../scripts/curl/) cover the
three clients, and [../tools/](../tools/README.md) explores the schema offline and
validates SWQL.

## A note on trust

The build checks extracted data consistency, recognized schema references, selected
command examples, and SWQL within its supported grammar and configured paths. It is not
a live-server test or a proof of every prose claim. Use the
[evidence rules and audit](reference/documentation-audit-2026-09-18.md) to distinguish
contract facts, export observations, runtime evidence, and unresolved assumptions.
[reference/unverified.md](reference/unverified.md) collects explicitly marked gaps.

The version documented here is **2026.2**. The schema changes between releases and also
depends on which modules are licensed, so for a specific server the authority is that
server: see [swis/metadata-introspection.md](swis/metadata-introspection.md).

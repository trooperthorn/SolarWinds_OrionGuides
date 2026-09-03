# Documentation

Guidance for SolarWinds Orion / Observability Self-Hosted, organized by what you are
trying to do.

If you are new to the platform's API, read [swis/README.md](swis/README.md) then
[swql/README.md](swql/README.md), in that order. If you are here to look something up,
jump to [reference/](reference/README.md).

The full section-by-section index (every page, organized by topic) lives in
[llms.txt](../llms.txt) at the repository root. It is kept there rather than duplicated
here so there is one index to update, not two, and so AI systems reading this repository
find the same map a person browsing `docs/` does.

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

Runnable code lives outside `docs/`: [../scripts/swql/](../scripts/swql/) has 207 verified
sample queries, [../scripts/powershell/](../scripts/powershell/),
[../scripts/python/](../scripts/python/) and [../scripts/curl/](../scripts/curl/) cover the
three clients, and [../tools/](../tools/README.md) explores the schema offline and
validates SWQL.

## A note on trust

Every entity, property, verb and parameter named in these pages was checked against the
extracted schema before it was written, and every SWQL example is re-validated on each
build. Where a claim could not be verified, it says so rather than asserting quietly; see
[reference/unverified.md](reference/unverified.md).

The version documented here is **2026.2**. The schema changes between releases and also
depends on which modules are licensed, so for a specific server the authority is that
server: see [swis/metadata-introspection.md](swis/metadata-introspection.md).

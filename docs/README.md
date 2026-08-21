# Documentation

Guidance for SolarWinds Orion / Observability Self-Hosted, organized by what you are
trying to do.

If you are new to the platform's API, read [swis/README.md](swis/README.md) then
[swql/README.md](swql/README.md), in that order. If you are here to look something up,
jump to [reference/](reference/README.md).

## The platform

What the product is and how the pieces fit together.

| Page | Covers |
| --- | --- |
| [platform/README.md](platform/README.md) | Orientation and how to navigate this section |
| [platform/architecture.md](platform/architecture.md) | Primary server, polling engines, additional web servers, database, HA |
| [platform/modules.md](platform/modules.md) | Which product owns which entity namespace, with entity counts |
| [platform/versions-and-naming.md](platform/versions-and-naming.md) | Orion to SolarWinds Platform to Observability Self-Hosted, and why the API still says Orion |

## The API

The SolarWinds Information Service: how to reach it and what it offers.

| Page | Covers |
| --- | --- |
| [swis/README.md](swis/README.md) | What SWIS is, why to use it over the database, and its four interfaces |
| [swis/connecting.md](swis/connecting.md) | Ports, endpoints, authentication modes, TLS, first connection |
| [swis/rest-api.md](swis/rest-api.md) | The REST contract: query, parameters, paging, response shapes |
| [swis/crud.md](swis/crud.md) | Create, read, update and delete against entity URIs |
| [swis/bulk-operations.md](swis/bulk-operations.md) | BulkUpdate and BulkDelete, and when not to use them |
| [swis/uris.md](swis/uris.md) | The URI format, the system identifier, and entities that have none |
| [swis/invoke-verbs.md](swis/invoke-verbs.md) | Calling verbs, and how to set parameters in every client |
| [swis/verb-catalog.md](swis/verb-catalog.md) | The verbs worth knowing, grouped by task |
| [swis/metadata-introspection.md](swis/metadata-introspection.md) | Asking a live server about its own schema |

## The query language

| Page | Covers |
| --- | --- |
| [swql/README.md](swql/README.md) | What SWQL is and how it differs from T-SQL |
| [swql/language-reference.md](swql/language-reference.md) | Every clause, operator, and data type |
| [swql/joins-and-navigation.md](swql/joins-and-navigation.md) | Navigation properties, explicit joins, and querying base entities |
| [swql/functions.md](swql/functions.md) | The complete function reference with worked examples |
| [swql/date-and-time.md](swql/date-and-time.md) | The single most common source of wrong answers |
| [swql/gotchas.md](swql/gotchas.md) | Things that silently produce wrong results |
| [swql/performance.md](swql/performance.md) | Writing queries that do not hurt the database |

## The data model

| Page | Covers |
| --- | --- |
| [schema/README.md](schema/README.md) | How the schema is organized and how to look things up |
| [schema/entity-model.md](schema/entity-model.md) | Inheritance, key properties, access control |
| [schema/relationships.md](schema/relationships.md) | Relationship kinds and navigating between entities |
| [schema/key-entities.md](schema/key-entities.md) | Deep reference for the entities you will actually use |
| [schema/netobject-types.md](schema/netobject-types.md) | What a NetObject prefix is and where `N:42` is required |
| [schema/status-codes.md](schema/status-codes.md) | What the status integers mean and how rollup ranking works |
| [schema/using-the-data.md](schema/using-the-data.md) | The generated JSON under `data/`, and how to query it |

## Modules

Per-product deep dives. An entity only exists if its module is licensed and installed.

| Page | Module |
| --- | --- |
| [modules/README.md](modules/README.md) | Index, with entity counts and how to detect what is installed |
| [modules/npm.md](modules/npm.md) | Network Performance Monitor |
| [modules/sam.md](modules/sam.md) | Server and Application Monitor |
| [modules/ncm.md](modules/ncm.md) | Network Configuration Manager |
| [modules/nta.md](modules/nta.md) | NetFlow Traffic Analyzer |
| [modules/srm.md](modules/srm.md) | Storage Resource Monitor |
| [modules/vman.md](modules/vman.md) | Virtualization Manager |
| [modules/ipam.md](modules/ipam.md) | IP Address Manager |
| [modules/udt.md](modules/udt.md) | User Device Tracker |
| [modules/vnqm.md](modules/vnqm.md) | VoIP and Network Quality Manager |
| [modules/wpm.md](modules/wpm.md) | Web Performance Monitor |
| [modules/dpa.md](modules/dpa.md) | Database Performance Analyzer |
| [modules/log-analyzer.md](modules/log-analyzer.md) | Log Analyzer |
| [modules/qoe.md](modules/qoe.md) | Quality of Experience |
| [modules/hardware-health.md](modules/hardware-health.md) | Hardware sensors |
| [modules/cloud.md](modules/cloud.md) | AWS, Azure and GCP monitoring |
| [modules/agents.md](modules/agents.md) | The SolarWinds agent |

## Automation

Task guides that combine query, CRUD and Invoke.

| Page | Task |
| --- | --- |
| [automation/README.md](automation/README.md) | How to approach automation against SWIS |
| [automation/node-management.md](automation/node-management.md) | The node lifecycle, from add to delete |
| [automation/maintenance-mode.md](automation/maintenance-mode.md) | Unmanaging and remanaging |
| [automation/custom-properties.md](automation/custom-properties.md) | Creating, populating and querying custom properties |
| [automation/alerts.md](automation/alerts.md) | Active alerts, acknowledgement, definitions, suppression |
| [automation/events-and-auditing.md](automation/events-and-auditing.md) | What happened, and who changed it |
| [automation/discovery.md](automation/discovery.md) | Network sonar discovery and list resources |
| [automation/dependencies.md](automation/dependencies.md) | Suppressing downstream alerts during an outage |
| [automation/credentials.md](automation/credentials.md) | Credential entities and their security posture |
| [automation/accounts-and-permissions.md](automation/accounts-and-permissions.md) | Accounts, roles, rights, and account limitations |
| [automation/reporting.md](automation/reporting.md) | Building reports and scheduled exports |
| [automation/scheduling.md](automation/scheduling.md) | Scheduled tasks and maintenance plans |
| [automation/high-availability.md](automation/high-availability.md) | HA pools |

## Polling

Five separate polling systems that share no entities and reuse each other's column names.

| Page | Covers |
| --- | --- |
| [polling/README.md](polling/README.md) | The map: which system is which, and how to tell them apart |
| [polling/standard-pollers.md](polling/standard-pollers.md) | `Orion.Pollers`: why a new node monitors nothing until pollers are assigned |
| [polling/universal-device-pollers.md](polling/universal-device-pollers.md) | UnDPs: an SNMP OID you defined yourself |
| [polling/device-studio.md](polling/device-studio.md) | The read-only `Orion.DeviceStudio.*` entities |
| [polling/technology-polling.md](polling/technology-polling.md) | Technology polling and the declarative poller templates |
| [polling/api-pollers.md](polling/api-pollers.md) | Collecting from an HTTP endpoint |

## Guides

| Page | Covers |
| --- | --- |
| [guides/getting-started.md](guides/getting-started.md) | From nothing to a working query and a first safe change |
| [guides/cookbook.md](guides/cookbook.md) | Task to query, indexed by the question you are asking |
| [guides/troubleshooting.md](guides/troubleshooting.md) | Diagnosing SWIS problems by symptom |
| [guides/building-integrations.md](guides/building-integrations.md) | Writing software against SWIS rather than running ad hoc queries |

## Reference

Lookup tables. Most are generated from the extracted data and must not be edited by hand.

| Page | Contents |
| --- | --- |
| [reference/README.md](reference/README.md) | What is generated, what is written, and which to use when |
| [reference/entity-index.md](reference/entity-index.md) | All 2067 entities with base type, operations and counts |
| [reference/verb-index.md](reference/verb-index.md) | All 958 verbs with positional signatures and required rights |
| [reference/netobject-types.md](reference/netobject-types.md) | NetObject prefixes, key properties, parent entities |
| [reference/status-codes.md](reference/status-codes.md) | Status ids, names, ranks and meanings |
| [reference/swql-function-index.md](reference/swql-function-index.md) | Every SWQL function with signature and example |
| [reference/glossary.md](reference/glossary.md) | The vocabulary, defined |
| [reference/unverified.md](reference/unverified.md) | Every statement these guides decline to assert, collected |
| [reference/schema-changes-2026.1-to-2026.2.md](reference/schema-changes-2026.1-to-2026.2.md) | What changed, and what breaks |
| [reference/schema-changes-2025.4-to-2026.2.md](reference/schema-changes-2025.4-to-2026.2.md) | The same across two releases |

## Working examples

Runnable code lives outside `docs/`:

- [../scripts/swql/](../scripts/swql/) has 207 verified sample queries by subject
- [../scripts/powershell/](../scripts/powershell/), [../scripts/python/](../scripts/python/)
  and [../scripts/curl/](../scripts/curl/) cover the three clients
- [../tools/](../tools/README.md) explores the schema offline and validates SWQL

## A note on trust

Every entity, property, verb and parameter named in these pages was checked against the
extracted schema before it was written, and every SWQL example is re-validated on each
build. Where a claim could not be verified, it says so rather than asserting quietly.

The version documented here is **2026.2**. The schema changes between releases and also
depends on which modules are licensed, so for a specific server the authority is that
server: see [swis/metadata-introspection.md](swis/metadata-introspection.md).

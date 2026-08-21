# Module Guides

The platform is one installation, one database, and one API, but the data model is built up
by many products. Install the platform and you get nodes, volumes, groups, alerts, events,
credentials and pollers. Install Network Performance Monitor on top of it and 139 more
entity types appear in the same schema, joinable to the ones already there. Install Server
and Application Monitor and 140 more appear. Nothing is federated, nothing needs a second
connection, and a single SWQL statement can walk from a node to its interfaces, to the
applications running on it, to the configuration backup taken from it last night.

This section has one page per module. Each page covers what the module monitors, which
namespaces it contributes, the few entities that carry most of the weight, the verbs it
exposes, worked queries, and the traps specific to it.

For the one-screen version of the same map, plus the platform core entities that exist
regardless of licensing, see [../platform/modules.md](../platform/modules.md).

## The modules

Entity counts are exact for the 2026.2 extraction in
[`data/schema/2026.2/index.json`](../../data/schema/2026.2/index.json): they count every
entity whose name equals the listed prefix or begins with that prefix plus a dot.

| Module | Product name | What it monitors | Namespace prefix | Entities |
|---|---|---|---|---|
| [npm](npm.md) | Network Performance Monitor | Interfaces, wireless, routing, NetPath, multicast | `Orion.NPM.`, `Orion.Routing.`, `Orion.Packages.Wireless.`, `Orion.WirelessHeatMap.`, `Orion.NetPath.` | 139 |
| [sam](sam.md) | Server and Application Monitor | Template-based application monitoring, components, AppInsight for SQL, IIS and Exchange | `Orion.APM.` | 140 |
| [ncm](ncm.md) | Network Configuration Manager | Device configuration backup, compliance policies, config transfer, firmware, inventory | `Cirrus.` and `NCM.` | 129 |
| [nta](nta.md) | NetFlow Traffic Analyzer | Flow records, applications, protocols, conversations, CBQoS | `Orion.Netflow.` | 49 |
| [ipam](ipam.md) | IP Address Manager | Subnets, IP addresses, conflicts, DHCP scopes and leases, DNS zones and records | `IPAM.` | 77 |
| [udt](udt.md) | User Device Tracker | Switch ports, endpoints, MAC and IP history, users, watch lists | `Orion.UDT.` | 85 |
| [srm](srm.md) | Storage Resource Monitor | Storage arrays, LUNs, pools, NAS volumes, file shares, providers | `Orion.SRM.` | 135 |
| [vman](vman.md) | Virtualization Manager | vCenters, datacenters, clusters, hosts, virtual machines, datastores | `Orion.VIM.` | 90 |
| [vnqm](vnqm.md) | VoIP and Network Quality Manager | IP SLA operations, sites, call managers, phones, call detail records | `Orion.IpSla.` | 140 |
| [wpm](wpm.md) | Web Performance Monitor | Recorded browser transactions, steps, requests, playback locations | `Orion.SEUM.` | 31 |
| [dpa](dpa.md) | Database Performance Analyzer | Database instances, wait times, blocking, deadlocks, expensive queries | `Orion.DPA.` and `DPA.` | 27 |
| [log-analyzer](log-analyzer.md) | Log Analyzer | Syslog messages, SNMP traps, log file entries, processing rules | `Orion.OLM.` | 21 |
| [hardware-health](hardware-health.md) | Hardware Health | Fans, power supplies, temperature sensors, chassis, blades, racks | `Orion.HardwareHealth.` | 33 |
| [qoe](qoe.md) | Quality of Experience | Packet-inspection applications, categories, probes and probe assignments | `Orion.DPI.` | 14 |
| [cloud](cloud.md) | Cloud monitoring | AWS and Azure accounts, instances, volumes, cloud metrics | `Orion.Cloud.` | 148 |
| [agents](agents.md) | Agent management | Deployed agents, plugins, versions, agent-based polling | `Orion.AgentManagement.` | 16 |

The namespace prefixes and entity counts come from the extracted schema. The Module column is
this section's page name rather than a code the data defines: eleven of the sixteen match the
`module` field in
[`data/reference/netobject-types.json`](../../data/reference/netobject-types.json), which
spells Virtualization Manager `VIM` and agent management `Agent`, and carries no rows at all
for Log Analyzer, Hardware Health or Cloud. The full product names are spelled out here for
orientation; SolarWinds' own SDK documentation names some of them in full and refers to others
only by their code, as [../platform/modules.md](../platform/modules.md) explains.

Several modules contribute entities outside their headline prefix, and the individual
pages say so. NPM is the clearest case: beyond the 139 entities above it also owns the F5
family (`Orion.F5.`, 24 entities), the Cisco UCS family (`Orion.UCS.`, 8), and an older
wireless shape under `Orion.Wireless.` (14).

## Prefixes are engineering names, not product names

Do not derive an entity name from a product name. The prefixes were fixed long before the
current marketing names existed and almost none of them line up:

- Server and Application Monitor is `Orion.APM.`, and there is no `Orion.SAM.` namespace.
- Virtualization Manager is `Orion.VIM.`, and there is no `Orion.VMAN.` namespace.
- Network Configuration Manager is both `Cirrus.` and `NCM.`.
- VoIP and Network Quality Manager is `Orion.IpSla.`.
- Web Performance Monitor is `Orion.SEUM.`.
- NetFlow Traffic Analyzer is `Orion.Netflow.`, with a lowercase `f`.
- IP Address Manager is a bare `IPAM.` with no `Orion.` in front of it.

Look the name up rather than guessing it:

```bash
python3 tools/schema_query.py find wireless controller --properties
python3 tools/schema_query.py show Orion.Packages.Wireless.Controllers
```

## An entity only exists if its module does

This is the single most important thing to understand about this section. The schema you
get from a server is assembled from the modules that are licensed and installed on that
server. An entity documented here can be entirely absent from the server in front of you,
and the failure looks different depending on how you reach it:

- A **query** against a missing entity fails outright, with an error naming the entity
  rather than returning an empty result.
- A **query that returns no rows** is the more confusing case, because it looks the same
  whether the module is missing its data, the module is not installed at all and you
  happened to query a base entity that survives, or your account limitations filtered every
  row away. Account limitations apply silently and per account, so two people running the
  same query legitimately get different answers.

Before concluding that a module is broken, confirm it is there. The `Metadata.*` entities
describe the schema the server actually loaded, so this works on any version:

```sql
SELECT FullName, BaseType, CanCreate, CanUpdate, CanDelete, CanInvoke, IsObsolete
FROM Metadata.Entity
WHERE FullName LIKE 'Orion.NPM.%'
ORDER BY FullName
```

An empty result means the module is not installed. A populated result means the entity
types exist, and any emptiness after that is data or permissions, not licensing. Select
`IsObsolete` while you are there: some entities remain queryable while formally deprecated,
and building on one is a slow way to break later.

To count what a namespace contributes on your own server rather than trusting the table
above:

```sql
SELECT COUNT(FullName) AS EntityCount
FROM Metadata.Entity
WHERE FullName LIKE 'Orion.SRM.%'
```

For the licensing view of the same question, ask which modules the platform believes are
installed:

```sql
SELECT Name, LicenseName, Version, Family, IsEval, IsExpired, DaysRemaining
FROM Orion.InstalledModule
ORDER BY Name
```

`Orion.InstalledModule` declares no access restrictions in the schema, so a read-only
account can run it. `Orion.Licensing.Licenses`, which carries the fuller licensing detail,
requires the `admin` right and will return nothing to a limited account.

## Checking offline instead

Everything in the table came from the extracted data, and you can interrogate it the same
way without a server:

```bash
python3 tools/schema_query.py stats
python3 tools/schema_query.py find Orion.Routing
python3 tools/schema_query.py show Orion.NPM.Interfaces
python3 tools/schema_query.py verbs --entity Orion.NPM.Interfaces
```

The full generated enumeration of all 2067 entities is in
[../reference/entity-index.md](../reference/entity-index.md), and every verb with its
ordered parameters is in [../reference/verb-index.md](../reference/verb-index.md).

## Related pages

| Page | What it gives you |
|---|---|
| [../platform/modules.md](../platform/modules.md) | The whole module map on one page, including the platform core and the prefixes that are not modules at all |
| [../platform/architecture.md](../platform/architecture.md) | Which server polls what, and why a module can be installed but idle |
| [../platform/versions-and-naming.md](../platform/versions-and-naming.md) | Why entity names drift between releases and how to write queries that survive it |
| [../reference/netobject-types.md](../reference/netobject-types.md) | The NetObject prefix each entity uses, which verbs need |
| [../reference/status-codes.md](../reference/status-codes.md) | What the `Status` integers mean |
| [../../scripts/swql/](../../scripts/swql/) | Verified sample queries grouped by subject |

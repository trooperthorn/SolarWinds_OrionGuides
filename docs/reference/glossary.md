# Glossary

The platform uses a lot of ordinary words in a specific way. "Element" is a licensing
unit, "unmanaged" is a scheduled state rather than a mistake, "container" and "group" are
the same thing seen from two levels of the schema, and "discovery" is two unrelated
features. Reading a SolarWinds page or a SWQL query with the general-English meaning in
mind is a reliable way to misunderstand it.

Every entity, property and verb named below was checked against the extracted 2026.2
schema. Each entry links to the page that covers the term properly; this page is the
one-paragraph version.

This is the only hand-written file in `docs/reference/`. Everything else here is generated
from `data/`; see [README.md](README.md).

## Account limitation

A restriction attached to an Orion account that narrows the set of objects that account
can see. SWIS applies it to **query results**, silently, so two accounts running identical
SWQL against the same server legitimately get different rows and neither is told why. It
is stored in `Orion.Limitations` with its type in `Orion.LimitationTypes`, and an account
has exactly three slots for one: `LimitationID1`, `LimitationID2` and `LimitationID3` on
`Orion.Accounts`. See
[../automation/accounts-and-permissions.md](../automation/accounts-and-permissions.md#account-limitations-silently-change-query-results).

## Additional web server

A second (or third) machine running the Orion Web Console against the same database, added
for capacity or for placing the console closer to its users. Web console instances are
recorded in `Orion.Websites`, which carries `ServerName`, `IPAddress`, `Port`, `Type` and
`FQDN`, and they are separate from polling engines: a web server presents data, it does
not collect any. See [../platform/architecture.md](../platform/architecture.md).

## Cipher password

The password the WPM recording verbs use to encrypt and decrypt an exported recording
file: `Orion.SEUM.Recordings.Export(recordingId, password)` ciphers the file it returns,
and `Import` and `Update` take the same value to decipher it. It is a key for the file
rather than a site credential, so the same value must be supplied on both sides of a
transfer, and getting it wrong produces a failed import rather than a corrupted
recording. See [../modules/wpm.md](../modules/wpm.md).

## Container

The base entity behind groups. `Orion.Container` inherits from `System.ManagedEntity` and
holds the group's name, owner, status calculator and rollup type, while `Orion.Groups`
inherits from `Orion.Container` and adds almost nothing of its own. Membership lives in
`Orion.ContainerMembers`, and the verbs (`CreateContainer`, `UpdateContainer`,
`DeleteContainer`, `AddDefinition`) are declared on `Orion.Container` rather than on
`Orion.Groups`. See [Group](#group) and
[../automation/dependencies.md](../automation/dependencies.md).

## CRUD

Create, read, update and delete: the SWIS interface for working with one entity instance
at a time. Create takes an entity type name and a property bag and returns the new
instance's URI; read, update and delete take a URI. Not every entity supports every
operation, and an entity that does not declare create cannot be created no matter how the
request is shaped. See [../swis/crud.md](../swis/crud.md).

## Custom property

A user-defined column added to a monitored object type, stored on a companion entity
rather than on the object itself: node custom properties live on
`Orion.NodesCustomProperties`, reached from a node through the `CustomProperties`
navigation property. The catalogue of definitions is `Orion.CustomProperty`, whose `Table`,
`Field`, `DataType` and `TargetEntity` describe each one. Because they are installation
data, custom property columns do not appear in this repository's extracted schema; your own
server is the authority. See
[../automation/custom-properties.md](../automation/custom-properties.md).

## Dependency

A declared parent/child relationship between two monitored objects, used so that an outage
on the parent suppresses alerts on everything behind it. `Orion.Dependencies` stores each
one as a `ParentUri` and a `ChildUri` plus `AutoManaged` and
`IncludeInStatusCalculation` flags, so the dependency is expressed in URIs rather than
ids. It is a different mechanism from a group, which rolls status up, and from a
maintenance window, which stops polling. See
[../automation/dependencies.md](../automation/dependencies.md).

## Discovery

Two different features share the name. **Network Sonar discovery** scans addresses and
subnets for devices that are not monitored yet and can create nodes from what it finds; it
is driven by the twelve verbs on `Orion.Discovery`, starting with `StartDiscovery`, and
its job handle is an integer profile id. **List Resources** asks a node you already monitor
what else it can report and turns those on; see [List Resources](#list-resources). Picking
the wrong one is the usual reason a discovery script does nothing useful. See
[../automation/discovery.md](../automation/discovery.md).

## DisplayName

One of the five properties every entity inherits from `System.Entity`, alongside
`Description`, `InstanceType`, `Uri` and `InstanceSiteId`. It is the human-readable name
for an instance whatever its type, which is what lets a tool list nodes, interfaces and
applications in one result set without knowing which is which. Entities map it onto
whichever of their own columns makes sense, so `DisplayName` on a node is not a separate
value from its caption. See [../schema/entity-model.md](../schema/entity-model.md).

## DPA

Database Performance Analyzer, which monitors database instances, waits, blocking and
expensive queries. It is unusual among the modules in being a separate product with its own
server that integrates with the platform, and it contributes two namespaces: `DPA.` and
`Orion.DPA.`. See [../modules/dpa.md](../modules/dpa.md).

## Element

The platform's licensing unit: roughly, one monitored thing that counts against a licence.
`Orion.Engines` reports `Elements` and `LicensedElements` per polling engine, and
`Orion.Nodes.GetCountOfElementsPerEngineForLicensing()` returns, in its own words, the
"count of used elements (per engine) for licensing". Exactly which object types count as an
element for which licence is a licensing question rather than a schema one, and is not
recorded in the published schema. See
[../platform/architecture.md](../platform/architecture.md).

## Entity

A type in the SWIS schema: `Orion.Nodes`, `Orion.NPM.Interfaces`, `Metadata.Verb`. Entities
have properties, relationships and sometimes verbs, and they inherit from one another in a
tree rooted at `System.Entity`, so a query against a base type returns rows from every type
beneath it. The 2026.2 schema publishes 2067 of them across 16 namespaces. See
[../schema/entity-model.md](../schema/entity-model.md) and the full list in
[entity-index.md](entity-index.md).

## Group

A user-defined collection of monitored objects whose status rolls up from its members, and
which can be alerted on, reported on and used as an alert-suppression boundary. In the
schema a group is a container: `Orion.Groups` inherits from `Orion.Container`, and its
members are rows in `Orion.ContainerMembers` identified by `MemberUri` and
`MemberEntityType` rather than by a typed foreign key, which is what lets one group mix
nodes, interfaces and applications. See [Container](#container) and
[Rollup](#rollup).

## InstanceType

One of the five properties inherited from `System.Entity`. It names the concrete entity
type a row came from, which is what makes querying a base type useful: select from
`System.ManagedEntity` and `InstanceType` tells you whether each row is a node, an
interface, an application or something else. SWIS fills it in itself, so it is never
something you map or set. See [../schema/entity-model.md](../schema/entity-model.md#instancetype).

## Interface

A network interface on a node, monitored by NPM and held in `Orion.NPM.Interfaces`. It is
hosted by its node, so `Orion.Nodes.Interfaces` navigates down and
`Orion.NPM.Interfaces.Node` navigates back, and its NetObject prefix is `I`, as in `I:7`.
One node contributes many interfaces, so an installation has far more of them than nodes,
and the traffic statistics hanging off them are among the largest tables on the system. See
[../modules/npm.md](../modules/npm.md).

## Invoke

The SWIS interface for calling a verb: `POST /Invoke/{Entity}/{Verb}` with a JSON array as
the body. **Arguments are positional**, so the order in the schema is the entire contract;
names appear in documentation and in the Swagger contract but never travel on the wire.
Sending an object keyed by parameter name does not work. See
[../swis/invoke-verbs.md](../swis/invoke-verbs.md).

## IPAM

IP Address Manager, which manages subnets, IP address assignments, DHCP scopes and DNS
zones. Its entities sit outside the `Orion.` namespace altogether, under `IPAM.`, so there
is no `Orion.IPAM` namespace to search for. It also keeps its own per-account role model in
`IPAM.AccountRoles` rather than relying on core rights alone. See
[../modules/ipam.md](../modules/ipam.md).

## Key property

The property or properties that form an entity's primary key. Keys are what a SWIS URI is
built from and what CRUD addresses, so an entity with no key has no URI and cannot be
updated or deleted individually. The rendered schema does not mark keys, so this
repository recovers them from prose and from a community workbook;
`Metadata.Property.IsKey` on your own server is the authoritative answer. See
[../schema/entity-model.md](../schema/entity-model.md#key-properties).

## LA

Log Analyzer, which collects syslog messages, SNMP traps and log entries and applies
processing rules to them. Its entities are prefixed `Orion.OLM.`, which is one of the
several module prefixes that cannot be guessed from the product name. See
[../modules/log-analyzer.md](../modules/log-analyzer.md).

## List Resources

The operation behind the "List Resources" button in node management: ask a node that is
already monitored what else it can report, then turn on the pollers, interfaces and volumes
you want. It is a job-based flow on `Orion.Nodes`, beginning with
`ScheduleListResources(nodeId)`, which returns a string job id you poll for status. It is
not Network Sonar discovery, which finds devices that are not monitored yet. See
[../automation/discovery.md](../automation/discovery.md#list-resources-on-an-existing-node).

## Maintenance window

A scheduled period during which an object is unmanaged, so that planned work does not
generate alerts or gaps that look like faults. It is opened with
`Orion.Nodes.Unmanage(netObjectId, unmanageTime, remanageTime, isRelative, allowOverlapping)`
and closed early with `Orion.Nodes.Remanage(netObjectId)`, both of which require the
`allowUnmanage` right. Unmanaging stops polling; if you want alerts suppressed while
collection continues, that is alert suppression instead. See
[../automation/maintenance-mode.md](../automation/maintenance-mode.md).

## Managed entity

`System.ManagedEntity`, described in the schema as "something that has an
externally-determined up/down status", and the base type for everything the platform
monitors: nodes, interfaces, volumes, applications, groups and more. It contributes
`StatusDescription`, `UnManaged`, `UnManageFrom`, `UnManageUntil` and
`AncestorDisplayNames` to every descendant, which is why those properties are queryable on
entities that do not declare them. See
[../schema/entity-model.md](../schema/entity-model.md#the-base-types-worth-knowing).

## Module

A licensed product that extends the platform with its own entities, pollers and web
console pages: NPM, SAM, NCM and the rest. Modules share one database, one API and one
account model, so an entity only exists on a server where its module is installed and
licensed, and "unknown entity" is far more often a missing module than a typo.
`Orion.InstalledModule` lists what a given server believes it has. See
[../platform/modules.md](../platform/modules.md).

## Navigation property

A named, pre-declared join between two entities that you write as a dotted path instead of
an `ON` clause: `n.Interfaces.Caption`, `i.Node.Caption`. Every relationship produces one
on each end, and both are usable from the entity they are listed on, so "source" and
"target" describe the declaration rather than a permitted direction of travel. Navigation
properties are inherited like any other member. See
[../swql/joins-and-navigation.md](../swql/joins-and-navigation.md).

## NCM

Network Configuration Manager, which backs up and compares device configurations, runs
compliance policies and pushes changes. It is the module whose entities are hardest to
guess: they live under **two** prefixes, `Cirrus.` and `NCM.`, and its node ids are GUIDs
rather than the integers used elsewhere. See [../modules/ncm.md](../modules/ncm.md).

## NetObject

The platform's own way of identifying one monitored object across types, written as a type
prefix, a colon and an id: `N:42` is node 42, `I:7` is interface 7. It appears in alert
macros, in web console URLs, in `Orion.Pollers.NetObject`, and as the `netObjectId`
argument that verbs such as `Unmanage` and `PollNow` expect. Passing a bare `42` where
`N:42` is required is one of the most common automation mistakes, and it usually fails
quietly. See [../schema/netobject-types.md](../schema/netobject-types.md).

## NetObject prefix

The short type code at the front of a NetObject string: `N` for a node, `I` for an
interface, `V` for a volume, `AA` for a SAM application. It is a property of the object
type rather than of the entity name, so it cannot be derived from the entity and has to be
looked up. The full table is [netobject-types.md](netobject-types.md), and
`Orion.Pollers.NetObjectType` stores the prefix on its own.

## Node

A monitored device: a server, switch, router, firewall or anything else the platform polls
as a whole machine. `Orion.Nodes` is the centre of gravity of the schema, with more
navigation properties than any other entity, and its NetObject prefix is `N`. Creating a
node through CRUD creates a row and nothing more: without `Orion.Pollers` rows it is
monitored by nothing. See [../automation/node-management.md](../automation/node-management.md).

## NPM

Network Performance Monitor, the module that monitors interfaces, wireless, routing, fibre
channel and NetPath. Its entities are prefixed `Orion.NPM.`, with the headline one being
`Orion.NPM.Interfaces`, although several of its subsystems use prefixes of their own such
as `Orion.Routing.` and `Orion.NetPath.`. See [../modules/npm.md](../modules/npm.md).

## NTA

NetFlow Traffic Analyzer, which stores and reports on flow records exported by network
devices. Its entities are prefixed `Orion.Netflow.`, with a lowercase `f`, and its tables
are among the largest on any installation, so every query against them needs a time bound.
See [../modules/nta.md](../modules/nta.md).

## Orion Platform

The original and longest-lived name for the product, renamed to SolarWinds Platform around
the 2022.4 releases and then to SolarWinds Observability Self-Hosted for the self-hosted
edition. The API kept the `Orion` identifier throughout, because renaming a product is a
marketing decision and renaming an API is a breaking change: entity names, SWIS URIs and
the SDK all still say `Orion`. Read `Orion.` as "the platform" rather than as the name of
a product, and treat all three names as the same thing when searching documentation. See
[../platform/versions-and-naming.md](../platform/versions-and-naming.md).

## Policy report

An NCM compliance artifact with three tiers: one report groups policies, each policy
names the nodes and config type its rules apply to, and each rule is a test with optional
remediation. The console exports a whole report — policies and rules included — as one
`PolicyReport` XML file, and the API round trip is `GetPolicyReport` and `AddPolicyReport`
on `Cirrus.PolicyReports`. See
[../modules/ncm-compliance-reports.md](../modules/ncm-compliance-reports.md).

## Poller

A named piece of collection logic, and by extension the assignment that points one at an
object. `Orion.Pollers` is the assignment table: `PollerType` says which poller,
`NetObject` says what it polls, and `Enabled` says whether it is active. The poller code
itself is not in the schema, so there is no entity to join to and no foreign key to
validate a `PollerType` against. See [../polling/standard-pollers.md](../polling/standard-pollers.md).

## Poller type

The string that names a poller, following the convention
`<NetObjectType>.<Category>.<Method>.<Variant>`, as in `N.Cpu.SNMP.CiscoGen3`. Because it
is a free string with nothing to validate it against, a typo produces an assignment that
collects nothing and looks exactly like a correct one. SolarWinds publishes the catalogue
at [Poller Types](https://solarwinds.github.io/OrionSDK/docs/poller-types/). See
[../polling/standard-pollers.md](../polling/standard-pollers.md#the-poller-type-string).

## Polling engine

A server that runs collection jobs against monitored devices. The primary server is one,
and additional polling engines are added for capacity or for reach into networks the
primary cannot see. Engines are listed in `Orion.Engines` with their load and health
(`Elements`, `Nodes`, `Interfaces`, `PollingCompletion`), and each node is statically
assigned to one through `Orion.Nodes.EngineID`, so every job for that node runs there. See
[../platform/architecture.md](../platform/architecture.md).

## Property

A named, typed value on an entity, such as `Orion.Nodes.Caption`. Properties are inherited
down the entity tree, so a member declared on `System.Entity` or `System.ManagedEntity` is
queryable on every descendant even though it is not listed on that descendant's own page.
Some are readable but not writable, which `Metadata.Property.CanUpdate` will tell you
before an update silently changes nothing. See
[../schema/entity-model.md](../schema/entity-model.md).

## QoE

Quality of Experience, which uses deep packet inspection to measure application and network
response for traffic seen by a probe. Its entities are prefixed `Orion.DPI.`, after the
inspection technology rather than the product name. See [../modules/qoe.md](../modules/qoe.md).

## Rank

The severity ordering used when statuses are combined, exposed as
`Orion.StatusInfo.Ranking`. **A lower rank is worse**, so Down (110) beats Warning (220)
and Up (500) loses to almost everything; when a parent computes its status from its
children, the child with the lowest rank wins. Rank is not the status number itself, and
sorting a report by status id rather than by ranking produces an order that looks
arbitrary. See [../schema/status-codes.md](../schema/status-codes.md).

## Relationship

A declared connection between two entities, which SWIS turns into a navigation property on
each end. The 2026.2 schema has 1501 relationship definitions producing 2992 navigable
edges, and each definition has exactly one of three base kinds: `System.Hosting` for
containment, where the target belongs to the source and dies with it; `System.Reference`
for a plain association between independently-lived entities; and `System.Reliance` for a
dependency across a boundary the two do not share, whose navigation properties usually
start with `Rely`. See [../schema/relationships.md](../schema/relationships.md).

## Rollup

Computing one object's status from the statuses of the things beneath it, which is what
makes a group or a parent object go red when a member does. The rule is driven by rank
rather than by the status number, and the group's own choice of rule is stored in
`Orion.Container.RollupType` and `Orion.Container.StatusCalculator`;
`Orion.StatusInfo.ChildStatusMap` and `Orion.StatusInfo.RollupType` describe how each
status participates. See [../schema/status-codes.md](../schema/status-codes.md) and
[Rank](#rank).

## SAM

Server and Application Monitor, which monitors applications and their components through
templates, including the AppInsight applications for SQL Server, IIS and Exchange. Its
entities are prefixed `Orion.APM.`, the original engineering name, and deriving
`Orion.SAM.Application` from the product name is the single most common query mistake
against this module. See [../modules/sam.md](../modules/sam.md).

## SCM

Server Configuration Monitor, which polls servers for their configuration and reports when
it drifts from a baseline. Its entities are prefixed `Orion.SCM.`:
`Orion.SCM.ServerConfiguration` holds the nodes it monitors, `Orion.SCM.Profiles` and
`Orion.SCM.ProfileElements` say what to collect from them, and `Orion.SCM.Baseline` is the
comparison point. See [../modules/scm.md](../modules/scm.md).

## SolarWinds Observability Self-Hosted

The current name for the self-hosted product, distinguishing it from SolarWinds' SaaS
observability offering. It is a product-name change rather than a technology change: the
SDK, the entity namespaces and the URIs are unchanged. See
[Orion Platform](#orion-platform).

## SolarWinds Platform

The middle name in the product's history, introduced around the 2022.4 releases and still
used throughout SolarWinds' own SDK documentation in phrases such as "Supported since:
SolarWinds Platform 2023.2". See [Orion Platform](#orion-platform).

## SRM

Storage Resource Monitor, which monitors storage arrays, pools, LUNs, file shares and NAS
volumes. Its entities are prefixed `Orion.SRM.`, and `Orion.SRM.Volumes` is a different
thing from the core `Orion.Volumes`: the first is a storage-array volume, the second is a
filesystem or disk on a monitored node. See [../modules/srm.md](../modules/srm.md).

## Status

An integer stored on every monitored entity that encodes its health, rendered in the web
console as a coloured icon. The numbers are not self-explanatory and are not fully
consistent across entity types, so join `Orion.StatusInfo` to get a name rather than
hard-coding integers. The 2026.2 reference data documents 26 status codes; note that
Unmanaged is one of them, so "not Up" is not the same as "broken". See
[status-codes.md](status-codes.md) and
[../schema/status-codes.md](../schema/status-codes.md).

## SWIS

The SolarWinds Information Service: the data access layer and API that sits in front of
the Orion database, exposing a hybrid object-oriented and relational model with its own
query language. Everything supported goes through it, including the web console itself.
Its REST endpoint is `https://<server>:17774/SolarWinds/InformationService/v3/Json`, and
its four interfaces are query, CRUD, invoke and bulk. See
[../swis/README.md](../swis/README.md).

## SWQL

SolarWinds Query Language, the SQL-like language SWIS queries are written in. It is **read
only**: there is no `INSERT`, `UPDATE` or `DELETE`, and no `SELECT *`. It adds navigation
properties and `WITH ROWS`/`WITH TOTALROWS` paging to a broadly T-SQL-shaped syntax, and it
differs from T-SQL in enough small ways to be worth reading about before writing much of
it. See [../swql/README.md](../swql/README.md).

## SWQL Studio

The graphical query tool shipped with the Orion SDK: an object explorer built from the
`Metadata.*` entities, a query editor and an invoke-verb tab. It is the fastest way to
explore a schema interactively and to confirm what a server actually has, and its
connection dialog is where the various authentication modes are easiest to try. See
[../swis/connecting.md](../swis/connecting.md) and SolarWinds'
[Connecting to SWIS](https://solarwinds.github.io/OrionSDK/docs/connecting-to-swis/).

## UDT

User Device Tracker, which records which endpoints are connected to which switch ports and
keeps the MAC, IP and user history behind that. Its entities are prefixed `Orion.UDT.`, and
it is the module to reach for when the question is "where is this device plugged in". See
[../modules/udt.md](../modules/udt.md).

## Unmanaged

The state an object is in while a maintenance window is open: polling stops, alerts do not
fire, and the object's status shows as unmanaged rather than down.
`System.ManagedEntity` contributes `UnManaged`, `UnManageFrom` and `UnManageUntil` to every
monitored entity, so filtering `UnManaged = FALSE` is how a report distinguishes "actually
broken" from "in a maintenance window". Note the capitalisation: the property is
`UnManaged`. See [../automation/maintenance-mode.md](../automation/maintenance-mode.md).

## URI

A SWIS URI uniquely identifies one entity instance and looks like
`swis://<system-identifier>/Orion/Orion.Nodes/NodeID=42`. It is what CRUD, `BulkUpdate` and
`BulkDelete` address, and it is available as the inherited `Uri` property on every entity,
so the reliable way to get one is to select it rather than to build it. The system
identifier is tattooed into the database and is frequently not the hostname you connected
to. See [../swis/uris.md](../swis/uris.md).

## Verb

A named operation an entity publishes, invoked rather than queried: `Unmanage`, `PollNow`,
`Acknowledge`, `CreateCustomProperty`. Verbs exist because some changes are more than a
property assignment, and going through one means the platform can check rights and record
who did what. Of the 1021 verbs in 2026.2, 848 publish typed, ordered parameters, and many
declare the right they require, such as `manageNodes` or `allowUnmanage`. See
[../swis/invoke-verbs.md](../swis/invoke-verbs.md) and the full list in
[verb-index.md](verb-index.md).

## VMAN

Virtualization Manager, which monitors vCenters, hosts, clusters, datastores and virtual
machines. Its entities are prefixed `Orion.VIM.`, and there is no `Orion.VMAN` namespace at
all, which makes it another module you cannot name from the product. See
[../modules/vman.md](../modules/vman.md).

## VNQM

VoIP and Network Quality Manager, which monitors IP SLA operations, call managers, phones
and call detail records. Its entities are prefixed `Orion.IpSla.`, after the underlying
Cisco technology rather than the product. See [../modules/vnqm.md](../modules/vnqm.md).

## Volume

A storage object on a monitored node, held in `Orion.Volumes` with the NetObject prefix
`V`: a fixed disk, a network share, a RAM disk and so on, as `VolumeType` records. Volumes
are hosted by their node, so they are deleted with it, and they carry their own status and
their own pollers. Do not confuse them with
`Orion.SRM.Volumes`, which are array volumes from Storage Resource Monitor. See
[../schema/key-entities.md](../schema/key-entities.md).

## WPM

Web Performance Monitor, which plays back recorded browser transactions from chosen
locations and reports on their steps and timings. Its entities are prefixed `Orion.SEUM.`,
from "synthetic end user monitoring". See [../modules/wpm.md](../modules/wpm.md).

## Related pages

- [README.md](README.md) explains what else is in this directory and what generates it
- [../schema/entity-model.md](../schema/entity-model.md) for entities, properties,
  inheritance and keys
- [../schema/relationships.md](../schema/relationships.md) for relationship kinds and
  navigation
- [../platform/modules.md](../platform/modules.md) for the full module-to-namespace map
- [../swis/README.md](../swis/README.md) for the four interfaces
- [unverified.md](unverified.md) for everything these guides decline to assert

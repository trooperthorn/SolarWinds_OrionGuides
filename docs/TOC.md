<!-- GENERATED FILE. Do not edit by hand.
     Produced by tools/build_llms_index.py from the headings under docs/.
     Regenerate with: make docs-index -->

# Table of contents

Every page under `docs/`, every second-level heading on it, and the first sentence written under that heading. [llms.txt](../llms.txt) is the page-level map; this is the section-level one, for jumping to the right heading rather than the right file. Anchors are the ones GitHub renders, so every link below opens at its heading.

Everything in this repository was assembled from resources SolarWinds publishes on the public internet: the OrionSDK repository and its rendered schema pages, the public SDK documentation, the Swagger contract shipped with the SDK, and a community SWQL examples workbook. It contains no SolarWinds internal documentation, no non-public material, and no method of access to any SolarWinds system beyond the documented, customer-facing API. It is community documentation, not a SolarWinds publication.

## Top level

### [Documentation](README.md)

Guidance for SolarWinds Orion / Observability Self-Hosted, organized by what you are trying to do.

- [Sections](README.md#sections)
- [Working examples](README.md#working-examples): Runnable code lives outside docs/: ../scripts/swql/ has 224 verified sample queries, ../scripts/powershell/, ../scripts/python/ and ../scripts/curl/ cover the three clients, and ../tools/ explores the schema offline a...
- [A note on trust](README.md#a-note-on-trust): Every entity, property, verb and parameter named in these pages was checked against the extracted schema before it was written, and every SWQL example is re-validated on each build.

## docs/platform/

### [The SolarWinds Platform: Orientation](platform/README.md)

This section explains what the product actually is, how a deployment is put together, which modules contribute which parts of the data model, and why almost everything you touch through the API is still called Orion.*...

- [What the product is](platform/README.md#what-the-product-is): SolarWinds sells a self-hosted monitoring suite that you install on your own Windows servers against your own SQL Server database.
- [How to navigate this section](platform/README.md#how-to-navigate-this-section)
- [The numbers, for the version documented here](platform/README.md#the-numbers-for-the-version-documented-here): This repository documents SWIS schema version 2026.2.
- [The API surface in one table](platform/README.md#the-api-surface-in-one-table): The port change is the single most common cause of "the API used to work and now it does not".
- [Your first query](platform/README.md#your-first-query): Every SWIS deployment has polling engines, so this query works on any server and tells you something immediately useful:
- [Verify before you trust](platform/README.md#verify-before-you-trust): Entity names, property names, and verb signatures differ between platform versions and between servers with different modules installed.
- [Where to go after this section](platform/README.md#where-to-go-after-this-section)
- [Related official documentation](platform/README.md#related-official-documentation)

### [Deployment Architecture](platform/architecture.md)

A SolarWinds deployment is a small distributed system, not a single application.

- [The parts](platform/architecture.md#the-parts): High Availability pools (Orion.HA.Pools) sit alongside this picture: they pair a server with a standby that can take over its role.
- [SWIS, the data access layer](platform/architecture.md#swis-the-data-access-layer): SWIS is the component that every supported integration talks to.
- [Primary server, additional polling engines, additional web servers](platform/architecture.md#primary-server-additional-polling-engines-additional-web-servers): Orion.OrionServers is the entity that enumerates the servers in a deployment.
- [How nodes are assigned to polling engines](platform/architecture.md#how-nodes-are-assigned-to-polling-engines): Assignment is static: every node carries an EngineID naming exactly one engine, and all of that node's related monitoring work runs from that engine.
- [The polling job engine](platform/architecture.md#the-polling-job-engine): Polling work is scheduled and executed as jobs on the assigned engine.
- [The SQL Server database](platform/architecture.md#the-sql-server-database): There is exactly one database behind the whole deployment, shared by every server and every module.
- [High Availability pools](platform/architecture.md#high-availability-pools): An HA pool pairs servers of the same type so one can take over from the other.
- [Putting it together: a deployment health query](platform/architecture.md#putting-it-together-a-deployment-health-query): An engine whose MinutesSinceKeepAlive is climbing is not reporting in, whatever its PollingCompletion last said.
- [Next](platform/architecture.md#next): differ from the 2026.2 schema documented here.

### [Module Map: Which Product Owns Which Entities](platform/modules.md)

The platform is one installation with one database and one API, but the data model is contributed by many products.

- [Read the prefixes literally, not as product names](platform/modules.md#read-the-prefixes-literally-not-as-product-names): The single most confusing thing about this schema is that entity prefixes are historical engineering names, not marketing names.
- [The map](platform/modules.md#the-map): Beyond that table the schema also carries namespaces for cloud monitoring (Orion.Cloud., 148 entities), agent management (Orion.AgentManagement., 16), asset inventory (Orion.AssetInventory., 23), Server Configuration...
- [Platform core](platform/modules.md#platform-core): Everything that exists regardless of which modules you licensed.
- [NPM: Network Performance Monitor](platform/modules.md#npm-network-performance-monitor): Interfaces are the headline entity, but NPM contributes considerably more than that: wireless (Orion.NPM.WL.
- [SAM: Server and Application Monitor](platform/modules.md#sam-server-and-application-monitor): Orion.APM.
- [NCM: Network Configuration Manager](platform/modules.md#ncm-network-configuration-manager): NCM is the one module with two live namespaces, and knowing which to use matters.
- [NTA: NetFlow Traffic Analyzer](platform/modules.md#nta-netflow-traffic-analyzer): Orion.Netflow.Flows is the raw flow record at the finest granularity available.
- [SRM: Storage Resource Monitor](platform/modules.md#srm-storage-resource-monitor): 135 entities covering block and file storage.
- [VMAN: Virtualization, under the VIM prefix](platform/modules.md#vman-virtualization-under-the-vim-prefix): The SDK confirms the naming: Virtualization Manager (VMAN) "has fully transitioned to just being an Orion module".
- [IPAM: IP Address Manager](platform/modules.md#ipam-ip-address-manager): One of only three modules whose namespace is a bare top-level prefix rather than Orion.something; the other two are NCM (Cirrus.
- [UDT: User Device Tracker](platform/modules.md#udt-user-device-tracker): Answers "where is this MAC address plugged in, and who was using it".
- [VNQM: VoIP and Network Quality Manager, under the IpSla prefix](platform/modules.md#vnqm-voip-and-network-quality-manager-under-the-ipsla-prefix): 140 entities, tied with SAM (Orion.APM.) for the largest module namespace in the table above.
- [WPM: Web Performance Monitor, under the SEUM prefix](platform/modules.md#wpm-web-performance-monitor-under-the-seum-prefix): Records and replays browser transactions from playback locations.
- [DPA: Database Performance Analyzer](platform/modules.md#dpa-database-performance-analyzer): DPA is unusual because it is a separate product that integrates with the platform rather than a module installed into it, and the schema reflects that with two namespaces:
- [Log Analyzer, under the OLM prefix](platform/modules.md#log-analyzer-under-the-olm-prefix): Syslog messages, SNMP traps, and log file entries land in Orion.OLM.LogEntry, with Orion.OLM.LogEntryType naming the source type and Orion.OLM.LogEntryLevel the severity.
- [Hardware Health](platform/modules.md#hardware-health): Not a standalone product.
- [Cortex and Cirrus: two names that are not modules](platform/modules.md#cortex-and-cirrus-two-names-that-are-not-modules): Two prefixes look like products but are not.
- [Which modules are installed on this server](platform/modules.md#which-modules-are-installed-on-this-server): Rather than inferring from which queries succeed, ask directly:
- [A caution about older entity lists](platform/modules.md#a-caution-about-older-entity-lists): Entity lists that circulate in the community were often written against much older versions, and some of the names in them no longer resolve.
- [Next](platform/modules.md#next): history.

### [Versions and Naming](platform/versions-and-naming.md)

The product has been renamed twice.

- [The naming history](platform/versions-and-naming.md#the-naming-history): You can watch the first rename happen in SolarWinds' own SDK documentation.
- [Why "Orion" is still everywhere in the API](platform/versions-and-naming.md#why-orion-is-still-everywhere-in-the-api): Renaming a product is a marketing decision.
- [How version numbers work](platform/versions-and-naming.md#how-version-numbers-work): Platform versions are year.release, sometimes with a patch component:
- [The SDK publishes a schema per version](platform/versions-and-naming.md#the-sdk-publishes-a-schema-per-version): SolarWinds publishes full SWIS schema documentation for each platform version.
- [The schema genuinely differs between versions](platform/versions-and-naming.md#the-schema-genuinely-differs-between-versions): This is not a theoretical concern.
- [Finding out what you actually have](platform/versions-and-naming.md#finding-out-what-you-actually-have): Never infer a version from a name.
- [Writing automation that survives an upgrade](platform/versions-and-naming.md#writing-automation-that-survives-an-upgrade): record that in a comment.
- [Related](platform/versions-and-naming.md#related): this repository was generated from.

## docs/swis/

### [The SolarWinds Information Service (SWIS)](swis/README.md)

The SolarWinds Information Service is the API for SolarWinds Orion, now shipped as SolarWinds Observability Self-Hosted.

- [Why SWIS instead of the SQL database](swis/README.md#why-swis-instead-of-the-sql-database): You can technically read the Orion database with a SQL client.
- [The entity inheritance hierarchy](swis/README.md#the-entity-inheritance-hierarchy): Every SWIS entity type has a parent type, and the root of the tree is System.Entity.
- [The four interfaces](swis/README.md#the-four-interfaces): SWIS exposes four distinct interfaces.
- [Which interface for which task](swis/README.md#which-interface-for-which-task)
- [Where to go next](swis/README.md#where-to-go-next): connection snippets for PowerShell, Python and curl.
- [Verifying anything in this guide](swis/README.md#verifying-anything-in-this-guide): Every entity name, property name, verb name and parameter in these documents was checked against the extracted schema in data/schema/2026.2/.

### [Bulk operations](swis/bulk-operations.md)

BulkUpdate and BulkDelete apply one change to many entities in a single request.

- [The contract](swis/bulk-operations.md#the-contract): Two routes, both POST, both taking a JSON body:
- [Because there is no per-item result, verify afterwards](swis/bulk-operations.md#because-there-is-no-per-item-result-verify-afterwards): A bulk call that succeeds tells you the request was accepted.
- [Building the URI list](swis/bulk-operations.md#building-the-uri-list): Get the URIs from the same query that defines your target set.
- [PowerShell](swis/bulk-operations.md#powershell): The SwisPowerShell module does not wrap the bulk routes as their own cmdlets, so the usual pattern is to select the URIs and pipe them into Set-SwisObject, which issues one update per entity:
- [Python](swis/bulk-operations.md#python): To use the bulk routes properly, call them directly:
- [Batch size](swis/bulk-operations.md#batch-size): There is no documented maximum, and that is not the same as there being none.
- [When not to use bulk](swis/bulk-operations.md#when-not-to-use-bulk): Setting UnManaged = true through BulkUpdate is not the same as unmanaging a node.
- [Permissions](swis/bulk-operations.md#permissions): Bulk operations respect the same access control as the equivalent single-entity operations, and account limitations still apply.
- [See also](swis/bulk-operations.md#see-also)

### [Connecting to SWIS](swis/connecting.md)

Before you can query or change anything, you need to reach the SolarWinds Information Service and authenticate.

- [Endpoints and ports](swis/connecting.md#endpoints-and-ports): There are two transports into SWIS, and they listen on different ports.
- [Authentication modes](swis/connecting.md#authentication-modes): SWIS accepts three kinds of identity.
- [The local connection limitation](swis/connecting.md#the-local-connection-limitation): This one catches people out, so it is worth quoting directly.
- [PowerShell](swis/connecting.md#powershell): Install the module from the PowerShell Gallery.
- [Python](swis/connecting.md#python): SolarWinds publishes an official Python client, orionsdk, on PyPI.
- [curl](swis/connecting.md#curl): Every REST call is HTTPS with basic auth.
- [TLS and the self-signed certificate](swis/connecting.md#tls-and-the-self-signed-certificate): By default SWIS presents a self-signed certificate.
- [Troubleshooting a failed connection](swis/connecting.md#troubleshooting-a-failed-connection)
- [Next](swis/connecting.md#next)

### [CRUD: creating, reading, updating and deleting entities](swis/crud.md)

The SWIS query interface is read only.

- [The four operations](swis/crud.md#the-four-operations): The asymmetry is the important part:
- [Not every entity supports CRUD](swis/crud.md#not-every-entity-supports-crud): Again from the official documentation:
- [Worked example: PowerShell](swis/crud.md#worked-example-powershell): SwisPowerShell maps the four operations onto four cmdlets:
- [Worked example: Python](swis/crud.md#worked-example-python): The official orionsdk client exposes the four operations as create, read, update and delete, plus bulkupdate and bulkdelete.
- [Common mistakes](swis/crud.md#common-mistakes): There is no UPDATE statement in SWQL.
- [Next](swis/crud.md#next)

### [Invoke at scale, and how it goes wrong](swis/invoke-at-scale.md)

invoke-verbs.md is the contract: how a verb is called, how arguments serialise, how to discover a signature.

- [The shape of the surface](swis/invoke-at-scale.md#the-shape-of-the-surface): The widest verb takes 23 parameters, all positional.
- [Authorization is thinner than it looks](swis/invoke-at-scale.md#authorization-is-thinner-than-it-looks): That does not mean they are open, and it does not mean they are closed — it means the answer is somewhere else, and you have to look at two levels to find it.
- [The four dangerous shapes](swis/invoke-at-scale.md#the-four-dangerous-shapes): A verb is worth extra care when it has any of these, and needs a review when it has several.
- [The verb that deletes nodes over licence](swis/invoke-at-scale.md#the-verb-that-deletes-nodes-over-licence): One verb deserves its own section, because it is the clearest example of every property above in one place:
- [Automation runaways](swis/invoke-at-scale.md#automation-runaways): These are the failure modes that turn a working script into an incident.
- [Scaling a script for an external tool](swis/invoke-at-scale.md#scaling-a-script-for-an-external-tool): BulkUpdate and BulkDelete exist for CRUD; see bulk-operations.md.
- [Gotchas](swis/invoke-at-scale.md#gotchas): Check both, in both directions.
- [See also](swis/invoke-at-scale.md#see-also): access control - verb-catalog.md — the verbs worth knowing, grouped by task - bulk-operations.md — BulkUpdate and BulkDelete, which are CRUD and not Invoke - ../guides/building-integrations.md — accounts, secrets, ret...

### [Invoking verbs](swis/invoke-verbs.md)

The SWIS query interface is read only and the CRUD interface can only set property values on one entity instance at a time.

- [What a verb is, and why it exists](swis/invoke-verbs.md#what-a-verb-is-and-why-it-exists): A verb is a named operation that an entity type declares, with a typed parameter list, a return type, and optionally a required user right.
- [The contract, in one paragraph](swis/invoke-verbs.md#the-contract-in-one-paragraph): Names appear in the schema documentation, in the Swagger contract and in this repository's data, but they never travel on the wire.
- [REST](swis/invoke-verbs.md#rest): The body is a JSON array of positional arguments.
- [PowerShell](swis/invoke-verbs.md#powershell): Invoke-SwisVerb from the SwisPowerShell module takes four mandatory arguments: the connection, the entity name, the verb name, and an array of argument values.
- [Python](swis/invoke-verbs.md#python): SolarWinds publishes orionsdk on PyPI.
- [Three ways to discover a verb's parameters](swis/invoke-verbs.md#three-ways-to-discover-a-verbs-parameters): Use whichever matches where you are working.
- [Access control](swis/invoke-verbs.md#access-control): Verbs declare the right the caller must hold.
- [Worked examples](swis/invoke-verbs.md#worked-examples): Each of these was checked with python3 tools/schema_query.py verb <Entity> <Verb> against schema 2026.2 before it was written down.
- [Common failure modes](swis/invoke-verbs.md#common-failure-modes)
- [Where to go next](swis/invoke-verbs.md#where-to-go-next): Before running any of this unattended, read invoke-at-scale.md: the risk surface derived from the contract, the failure modes that turn a working script into an incident, and how to scale one safely.

### [Schema introspection with the Metadata namespace](swis/metadata-introspection.md)

SWIS describes itself.

- [The eleven Metadata entities](swis/metadata-introspection.md#the-eleven-metadata-entities): Property counts below are the members each entity declares itself.
- [Metadata.Entity: what exists and what you can do to it](swis/metadata-introspection.md#metadataentity-what-exists-and-what-you-can-do-to-it): The capability flags are the reason to start here.
- [Metadata.Property: what the columns are called](swis/metadata-introspection.md#metadataproperty-what-the-columns-are-called): Every property of one entity, with the flags that decide how you can use each one:
- [Metadata.Verb and Metadata.VerbArgument: how to call things](swis/metadata-introspection.md#metadataverb-and-metadataverbargument-how-to-call-things): This is the pair that matters most, because verb arguments are positional and the order is the entire contract.
- [Metadata.Relationship: how to join A to B](swis/metadata-introspection.md#metadatarelationship-how-to-join-a-to-b): Metadata.Relationship is the only place that tells you both navigation property names and the cardinality on each end.
- [Aliases, entity arguments and metadata bags](swis/metadata-introspection.md#aliases-entity-arguments-and-metadata-bags): Metadata.EntityAlias lists alternative names an entity answers to.
- [Metadata.Functions: which SWQL functions this server has](swis/metadata-introspection.md#metadatafunctions-which-swql-functions-this-server-has): One property, Name.
- [Obsolete and internal members](swis/metadata-introspection.md#obsolete-and-internal-members): IsObsolete, ObsolescenceReason and IsInternal appear on Metadata.Entity, Metadata.Property, Metadata.Verb, Metadata.Relationship and Metadata.EntityAlias.
- [Comparing your server against this repository](swis/metadata-introspection.md#comparing-your-server-against-this-repository): If an entity, property or verb in data/schema/2026.2/ does not exist on your server, the usual explanations, in order of likelihood, are: a different platform version; a module that is not installed or not licensed; o...
- [Practical notes](swis/metadata-introspection.md#practical-notes): than concatenating strings, and bound the result set with TOP n or WITH ROWS a TO b WITH TOTALROWS when you are exploring.
- [Where to go next](swis/metadata-introspection.md#where-to-go-next): call.

### [The SWIS REST/JSON API](swis/rest-api.md)

This is the HTTP contract for the SolarWinds Information Service.

- [Base URL and transport](swis/rest-api.md#base-url-and-transport): 2022.4.1 and is deprecated.
- [The path surface](swis/rest-api.md#the-path-surface): The Swagger contract for 2026.2 publishes 1319 paths.
- [Query](swis/rest-api.md#query): The simplest form.
- [Parameter binding](swis/rest-api.md#parameter-binding): A SWQL parameter is written @name in the query text and supplied as a member called name in the parameters object.
- [Paging with WITH ROWS and WITH TOTALROWS](swis/rest-api.md#paging-with-with-rows-and-with-totalrows): Both clauses are trailing modifiers on the SWQL statement, not REST parameters.
- [The response envelope](swis/rest-api.md#the-response-envelope): The Swagger response schema for both GET /Query and POST /Query:
- [Invoke](swis/rest-api.md#invoke): Verbs are called by POSTing to /Invoke/{Entity}/{Verb}.
- [Create](swis/rest-api.md#create): POST /Create/{Entity} with a JSON object of property values.
- [Read, Update and Delete on /{uri}](swis/rest-api.md#read-update-and-delete-on-uri): The URI goes directly into the path, unencoded, exactly as the official examples show.
- [BulkUpdate](swis/rest-api.md#bulkupdate): Applies one property bag to many URIs in a single request.
- [BulkDelete](swis/rest-api.md#bulkdelete): A natural pattern is to build the URI list from a query, since Uri is available on every entity:
- [Errors](swis/rest-api.md#errors): Successful responses are 200.
- [Next](swis/rest-api.md#next): examples.

### [SWIS URIs](swis/uris.md)

A SWIS URI is the identity of a single entity instance.

- [Finding a URI](swis/uris.md#finding-a-uri): Every entity type inherits a Uri property from System.Entity, so the easiest way to get one is to select it:
- [The format](swis/uris.md#the-format): Worked through with a real example:
- [The system identifier](swis/uris.md#the-system-identifier): This is the segment people get wrong, and it is worth understanding exactly.
- [The key filter](swis/uris.md#the-key-filter): The key filter names the entity's key properties and their values.
- [Entities without key properties have no URI](swis/uris.md#entities-without-key-properties-have-no-uri): Not every entity has a URI.
- [Navigating into a nav property](swis/uris.md#navigating-into-a-nav-property): Appending a navigation property name walks the relationship, and appending a key filter after it selects one instance from the other side.
- [Navigating into CustomProperties](swis/uris.md#navigating-into-customproperties): Custom property values live in a separate entity that hangs off the object, reached through a navigation property called CustomProperties.
- [Using URIs in REST paths](swis/uris.md#using-uris-in-rest-paths): The URI goes straight into the path after the base path, unencoded, exactly as the official examples show it:
- [Escaping values inside a URI](swis/uris.md#escaping-values-inside-a-uri): SWQL has an EscapeSWISUriValue(a) function, documented as returning the argument "with certain characters escaped".
- [Worked example: from a query to a change](swis/uris.md#worked-example-from-a-query-to-a-change): The whole pattern, end to end, without ever hand-building a URI:
- [Common mistakes](swis/uris.md#common-mistakes): Covered above.
- [Next](swis/uris.md#next)

### [Verb catalog](swis/verb-catalog.md)

SWIS schema 2026.2 declares 1021 verbs across 191 entities (186 with schema pages plus 5 contract-only entities such as Orion.SRM.BusinessLayer).

- [How to read these tables](swis/verb-catalog.md#how-to-read-these-tables): as a positional array and the names never go on the wire.
- [Node and object lifecycle](swis/verb-catalog.md#node-and-object-lifecycle): Adding a node is Create Orion.Nodes through CRUD, not a verb.
- [On-demand polling](swis/verb-catalog.md#on-demand-polling): Every one of these asks for polling work to happen now instead of at the next scheduled cycle.
- [Maintenance: unmanaging and suppressing alerts](swis/verb-catalog.md#maintenance-unmanaging-and-suppressing-alerts): Two different things, often confused.
- [Custom properties](swis/verb-catalog.md#custom-properties): These verbs manage custom property definitions.
- [Alerts and events](swis/verb-catalog.md#alerts-and-events): All four Orion.AlertActive verbs take AlertObjectID values.
- [Discovery and credentials](swis/verb-catalog.md#discovery-and-credentials): No Orion.Discovery verb declares a right of its own, but the entity declares invoke for manageNodes, so that is the right you actually need for all twelve.
- [NCM](swis/verb-catalog.md#ncm): NCM lives in the Cirrus namespace (72 entities in NCM plus 57 in Cirrus in 2026.2), and its verbs enforce NCM's own role model on top of the Orion right.
- [Agents](swis/verb-catalog.md#agents): Orion.AgentManagement.Agent declares 20 verbs, more than Orion.Nodes itself.
- [High availability](swis/verb-catalog.md#high-availability): Every Orion.HA.Pools verb requires admin and returns an OperationResult carrying a Code, a Result and a Message.
- [Groups, dependencies and accounts](swis/verb-catalog.md#groups-dependencies-and-accounts): Groups are Orion.Container at the verb level and Orion.Groups at the query level.
- [Hardware health and flow sources](swis/verb-catalog.md#hardware-health-and-flow-sources): The hardware health verbs are declared on the base entities HardwareInfoBase, HardwareItemBase and HardwareItemThreshold, not on the vendor-specific descendants.
- [Dashboards](swis/verb-catalog.md#dashboards): Orion.Dashboards.Instances declares 16 verbs.
- [Schema and service verbs](swis/verb-catalog.md#schema-and-service-verbs): Metadata.Entity.GetAliases is the verb SolarWinds uses as the official REST Invoke example: posting ["SELECT B.Caption FROM Orion.Nodes B"] returns {"B":"Orion.Nodes"}.
- [Querying the full set of 1021](swis/verb-catalog.md#querying-the-full-set-of-1021): The catalog above is curated.
- [Where to go next](swis/verb-catalog.md#where-to-go-next): invoke-at-scale.md covers what these verbs look like in aggregate -- which return nothing, which take an array and so let the caller choose the blast radius, and which declare no right at all.

## docs/swql/

### [SolarWinds Query Language (SWQL)](swql/README.md)

SWQL is the query language of the SolarWinds Information Service.

- [What SWQL actually queries](swql/README.md#what-swql-actually-queries): SWQL does not query tables.
- [The differences from T-SQL that actually bite](swql/README.md#the-differences-from-t-sql-that-actually-bite): There is no INSERT, UPDATE, DELETE or MERGE.
- [Where to run a query](swql/README.md#where-to-run-a-query)
- [This section](swql/README.md#this-section): Related reading elsewhere in this repository:
- [Checking a query before you run it](swql/README.md#checking-a-query-before-you-run-it): Two commands, no server required.
- [Official sources](swql/README.md#official-sources): possible issues - REST - Schema reference - Orion SDK wiki

### [SWQL date and time](swql/date-and-time.md)

Time-bounded queries are where SWQL most often returns a confident wrong answer.

- [The short version](swql/date-and-time.md#the-short-version): the Orion server or your browser.
- [How a SWQL date query actually runs](swql/date-and-time.md#how-a-swql-date-query-actually-runs): SWIS does not evaluate SWQL itself.
- [The trap: GetUtcDate() plus AddX](swql/date-and-time.md#the-trap-getutcdate-plus-addx): Run that query and look at what comes back over the wire.
- [The fix: convert, add, convert back](swql/date-and-time.md#the-fix-convert-add-convert-back): Convert the value into the timezone DATEADD is going to assume anyway, do the arithmetic there, then convert the result back.
- [The four functions that read or move the clock](swql/date-and-time.md#the-four-functions-that-read-or-move-the-clock): The four runs recorded in the community workbook were made minutes apart on one server, and together they show the shape clearly:
- [Which columns are UTC and which are local](swql/date-and-time.md#which-columns-are-utc-and-which-are-local): Datetime values are almost always stored in UTC, regardless of the SQL Server's timezone, the SolarWinds server's timezone, or the browser's.
- [The AddX family](swql/date-and-time.md#the-addx-family): Nine functions, and for eight of them one shape: the count comes first, the date second.
- [The XDiff family](swql/date-and-time.md#the-xdiff-family): Eight functions, all of the form XDiff(a, b): how much later b is than a, rounded to the nearest whole unit.
- [DateTrunc and its dateparts](swql/date-and-time.md#datetrunc-and-its-dateparts): DateTrunc('datepart', d) returns d with everything finer than datepart zeroed.
- [Downsample for arbitrary buckets](swql/date-and-time.md#downsample-for-arbitrary-buckets): Downsample(d, p) rounds the timestamp d to the period p, so '00:15:00' gives 15 minute buckets.
- [Relative time filtering](swql/date-and-time.md#relative-time-filtering): These are the patterns worth memorising.
- [DateTime literals and parameters](swql/date-and-time.md#datetime-literals-and-parameters): A string is converted to a date automatically when the context needs a date.
- [A checklist before you save a time-bounded query](swql/date-and-time.md#a-checklist-before-you-save-a-time-bounded-query): ToLocal and the whole thing in ToUtc.
- [See also](swql/date-and-time.md#see-also): recorded version baseline, plus the rest of the function library.

### [SWQL functions](swql/functions.md)

The complete built-in function library of SolarWinds Query Language, with a runnable example for every function.

- [How to read an entry](swql/functions.md#how-to-read-an-entry): Each entry gives the signature, what the function returns, and an example you can paste into SWQL Studio or POST to /Query.
- [Contents](swql/functions.md#contents): part extraction, DateTrunc, Downsample, DateTime - Aggregate functions: Avg, Count, Max, Min, Sum, String_Agg - Array functions: ArrayContains, ArrayLength, ArrayValueAt, SplitStringToArray - String functions: Concat,...
- [General functions](swql/functions.md#general-functions): Returns a unless it is NULL, else returns b.
- [Numeric functions](swql/functions.md#numeric-functions): Returns the absolute value of n.
- [Date/time functions](swql/functions.md#datetime-functions): Thirty-five functions, and the place where correct-looking SWQL most often returns wrong answers.
- [Aggregate functions](swql/functions.md#aggregate-functions): SolarWinds states the grouping rule directly: "Aggregate functions operate on a whole group of values at once.
- [Array functions](swql/functions.md#array-functions): A small number of SWIS properties are arrays rather than scalars: 17 properties in the 2026.2 schema are typed System.String[] and two are System.Int32[].
- [String functions](swql/functions.md#string-functions): Takes one or more arguments and returns a single string that is the concatenation of the values of the arguments.
- [Reconciliation: where the sources disagree](swql/functions.md#reconciliation-where-the-sources-disagree): Three discrepancies between the official reference and the community workbook show up in the function data.
- [What is not in the function library](swql/functions.md#what-is-not-in-the-function-library): The official reference is a closed list, and several things people reach for out of T-SQL habit are simply not on it:
- [See also](swql/functions.md#see-also): plus AddX trap, and the relative-time filtering patterns.

### [SWQL gotchas](swql/gotchas.md)

A SWQL error is cheap.

- [1. The empty result set is usually a permissions answer](swql/gotchas.md#1-the-empty-result-set-is-usually-a-permissions-answer): Start here, because it is the single most common wrong conclusion drawn from a SWQL result.
- [2. Status is an integer, and the integer means different things on different entities](swql/gotchas.md#2-status-is-an-integer-and-the-integer-means-different-things-on-different-entities): Status is declared on System.DashboardEntity, and its own schema summary is the warning:
- [3. Status versus PolledStatus on Orion.Nodes](swql/gotchas.md#3-status-versus-polledstatus-on-orionnodes): Both properties exist on Orion.Nodes and both are System.Int32.
- [4. UTC, DATEADD and the timestamp that quietly shifts](swql/gotchas.md#4-utc-dateadd-and-the-timestamp-that-quietly-shifts): This one has its own page, date-and-time.md, because it is the trap that produces the most convincing wrong numbers.
- [5. NULL, IsNull, and the rows that disappear instead of going null](swql/gotchas.md#5-null-isnull-and-the-rows-that-disappear-instead-of-going-null): Nothing equals NULL, including NULL.
- [6. To-many navigation multiplies rows and poisons aggregates](swql/gotchas.md#6-to-many-navigation-multiplies-rows-and-poisons-aggregates): Orion.Nodes.Interfaces is a System.Hosting relationship in the source-to-target direction, which means one node leads to many interfaces.
- [7. Averaging statistics rows without Weight](swql/gotchas.md#7-averaging-statistics-rows-without-weight): System.StatisticsEntity is the base type for 236 entities in 2026.2, and it declares three properties that most people never notice.
- [8. Entities that look like the same thing and are not](swql/gotchas.md#8-entities-that-look-like-the-same-thing-and-are-not): Four real pairs from the 2026.2 schema.
- [9. Columns that look boolean and are not](swql/gotchas.md#9-columns-that-look-boolean-and-are-not): 2026.2 has 942 System.Boolean properties and 24 System.Char properties, and the Char ones are where the trouble is.
- [10. String comparison, collation and case](swql/gotchas.md#10-string-comparison-collation-and-case): SWIS hands string comparison to SQL Server, so =, !=, LIKE, ORDER BY and DISTINCT all behave according to the collation the Orion database was created with.
- [11. The query interface cannot write, and some entities cannot be written at all](swql/gotchas.md#11-the-query-interface-cannot-write-and-some-entities-cannot-be-written-at-all): There is no INSERT, UPDATE, DELETE or MERGE in SWQL.
- [12. Port 17778 is deprecated](swql/gotchas.md#12-port-17778-is-deprecated): The REST endpoint moved.
- [13. Entity names change between versions](swql/gotchas.md#13-entity-names-change-between-versions): An entity name that was correct three versions ago can be gone, and a SWQL query naming a missing entity fails outright rather than returning zero rows, which is at least honest.
- [14. Types change between versions too](swql/gotchas.md#14-types-change-between-versions-too): A property that keeps its name but changes its type does not break SWQL.
- [15. Legacy properties the schema tells you to ignore](swql/gotchas.md#15-legacy-properties-the-schema-tells-you-to-ignore): Some properties exist only for backward compatibility and their own schema summaries say so.
- [A ten-minute audit for a query you inherited](swql/gotchas.md#a-ten-minute-audit-for-a-query-you-inherited): Run down this list before trusting a number that came out of a SWQL query.
- [Next](swql/gotchas.md#next): server what exists.

### [Joins, navigation and inheritance in SWQL](swql/joins-and-navigation.md)

This is the highest leverage page in the SWQL section.

- [Navigation properties are declared joins](swql/joins-and-navigation.md#navigation-properties-are-declared-joins): The schema does not just record which properties an entity has.
- [Cardinality: the thing that decides your row count](swql/joins-and-navigation.md#cardinality-the-thing-that-decides-your-row-count): A navigation is either to-one or to-many, and it matters enormously.
- [Finding a navigation path](swql/joins-and-navigation.md#finding-a-navigation-path): You rarely need to read a relationship list by hand.
- [Querying a base entity](swql/joins-and-navigation.md#querying-a-base-entity): SWIS entity types form an inheritance tree rooted at System.Entity, and SolarWinds states the consequence directly: "If you write a query against a base entity type, data from all entity types that have that base enti...
- [Ten worked joins](swql/joins-and-navigation.md#ten-worked-joins): Navigation form, one row per node and interface pair:
- [Choosing between navigation and an explicit join](swql/joins-and-navigation.md#choosing-between-navigation-and-an-explicit-join): Navigation and explicit joins mix freely in one query.
- [Common mistakes](swql/joins-and-navigation.md#common-mistakes): Orion.Nodes.StatusInfo does not exist even though Orion.NPM.Interfaces.StatusInfo does.
- [Verifying every name on this page](swql/joins-and-navigation.md#verifying-every-name-on-this-page): Against your own server, Metadata.Relationship is the authority, and it publishes the cardinalities the extracted data does not:
- [Next](swql/joins-and-navigation.md#next): statistics entities usually go wrong.

### [SWQL language reference](swql/language-reference.md)

A clause-by-clause reference for SolarWinds Query Language, with runnable examples against the 2026.2 schema.

- [How this page marks its evidence](swql/language-reference.md#how-this-page-marks-its-evidence): SolarWinds does not publish a formal SWQL grammar.
- [Statement shape](swql/language-reference.md#statement-shape): WITH is a trailing modifier here, not the leading WITH of a T-SQL common table expression.
- [SELECT](swql/language-reference.md#select): There is no SELECT *.
- [FROM and aliases](swql/language-reference.md#from-and-aliases): One entity name, optionally followed by an alias, optionally with AS.
- [Joins](swql/language-reference.md#joins): INNER, LEFT, RIGHT, FULL and OUTER are all SWQL keywords, recognised by SWQL Studio and used in SolarWinds' own samples (JOIN Orion.VolumesCustomProperties vcp ON v.VolumeID = vcp.VolumeID in SetVolumeCustomProperty.p...
- [WHERE](swql/language-reference.md#where): Status = 1 is Up and Status = 2 is Down.
- [GROUP BY and HAVING](swql/language-reference.md#group-by-and-having): Aggregates are Avg, Count, Max, Min, Sum and String_Agg.
- [ORDER BY](swql/language-reference.md#order-by): ASC is the default and may be omitted.
- [WITH ROWS and WITH TOTALROWS](swql/language-reference.md#with-rows-and-with-totalrows): WITH clauses trail the whole statement, after ORDER BY.
- [WITH LOGS](swql/language-reference.md#with-logs): Appends server-side diagnostic logging for the query to the result.
- [Other WITH options](swql/language-reference.md#other-with-options): To check any of these on your server, run the statement in SWQL Studio.
- [UNION](swql/language-reference.md#union): The official function reference documents UNION(q) as "adds the results of an additional query q directly below the former"; the column counts must match.
- [CASE](swql/language-reference.md#case): The official reference gives the form as Case when c then a else b end.
- [Subqueries](swql/language-reference.md#subqueries): The subquery must return exactly one column.
- [Query parameters](swql/language-reference.md#query-parameters): Bind values; do not concatenate them into query text.
- [Data types in results](swql/language-reference.md#data-types-in-results): SWIS property types are .NET type names, and the schema records the exact type for each of the 19328 properties.
- [Comments](swql/language-reference.md#comments): -- introduces a line comment.
- [Reserved words](swql/language-reference.md#reserved-words): The words SWQL Studio recognises as language keywords, and therefore the ones to avoid as bare identifiers or aliases:
- [Verifying anything on this page](swql/language-reference.md#verifying-anything-on-this-page): Offline, against the extracted schema:
- [Next](swql/language-reference.md#next): and worked joins across the common entity pairings.

### [SWQL performance](swql/performance.md)

A SWQL query is not free and it is not isolated.

- [Where the size is](swql/performance.md#where-the-size-is): Not all 2067 entities are the same size.
- [1. Bound every result set](swql/performance.md#1-bound-every-result-set): Bounding the result is the caller's job, and SolarWinds' own samples do it as a matter of course: SELECT TOP 3 URI FROM Orion.Nodes in the Go BulkCustomPropertyUpdate sample, SELECT TOP 2 Uri FROM Orion.Nodes in Alert...
- [2. Select only the columns you need](swql/performance.md#2-select-only-the-columns-you-need): There is no SELECT * in SWQL.
- [3. Filter on keys, not on captions](swql/performance.md#3-filter-on-keys-not-on-captions): Key columns are the identifiers SWIS itself works in.
- [4. Never wrap a filtered column in a function](swql/performance.md#4-never-wrap-a-filtered-column-in-a-function): This is the single highest-value rewrite on the page, and it is worth understanding why rather than memorising it.
- [5. Time-bound everything historical](swql/performance.md#5-time-bound-everything-historical): 236 entities in 2026.2 inherit from System.StatisticsEntity.
- [6. Filter before you aggregate](swql/performance.md#6-filter-before-you-aggregate): WHERE runs before grouping and reduces the rows the aggregate has to touch.
- [7. Dot-walking is joining, and deep chains join repeatedly](swql/performance.md#7-dot-walking-is-joining-and-deep-chains-join-repeatedly): A navigation property is a declared join.
- [8. Page with WITH ROWS, do not pull everything](swql/performance.md#8-page-with-with-rows-do-not-pull-everything): If a result set can be large, page it.
- [9. Bind parameters instead of building query text](swql/performance.md#9-bind-parameters-instead-of-building-query-text): Bind values.
- [Six rewrites](swql/performance.md#six-rewrites): Each pair is the same question asked twice.
- [Measuring rather than guessing](swql/performance.md#measuring-rather-than-guessing): Every claim on this page is about the shape of a query, not about how many milliseconds it will take on your hardware.
- [Checklist](swql/performance.md#checklist): Before a SWQL query goes into a report, an alert, a dashboard or a script:
- [Next](swql/performance.md#next): all.

## docs/schema/

### [The SWIS schema](schema/README.md)

Everything SWIS exposes is described by a schema: a set of entity types, each with properties, relationships to other entity types, verbs that can be invoked on it, and access control rules saying which Orion right is...

- [What version this documents](schema/README.md#what-version-this-documents): The schema changes between platform releases, and it also changes on a single release depending on which modules are licensed and installed, because each module adds its own entities.
- [Namespaces](schema/README.md#namespaces): An entity name is a namespace followed by one or more dotted segments, for example Orion.NPM.Interfaces.
- [The published schema browser versus this extract](schema/README.md#the-published-schema-browser-versus-this-extract): SolarWinds publishes the same schema as a browsable site at <https://solarwinds.github.io/OrionSDK/2026.2/schema/index.html>, one HTML page per entity, with a URL you can guess: Orion.Nodes is at <https://solarwinds.g...
- [Looking something up](schema/README.md#looking-something-up): tools/schema_query.py reads the extract, needs no network and no server, and answers the questions people actually have.
- [Then check your work](schema/README.md#then-check-your-work): Looking a name up is half of it.
- [Where to go next](schema/README.md#where-to-go-next): that require N:42 rather than 42.

### [The entity model](schema/entity-model.md)

SWIS is described by SolarWinds as "a hybrid of object-oriented and relational features" (About SWIS).

- [The tree is rooted at System.Entity](schema/entity-model.md#the-tree-is-rooted-at-systementity): The summary says four properties; the page lists five.
- [Properties are inherited](schema/entity-model.md#properties-are-inherited): From the official documentation:
- [The chain for a real entity](schema/entity-model.md#the-chain-for-a-real-entity): Reading the chain left to right tells you what a node is, in the schema's own terms:
- [The base types worth knowing](schema/entity-model.md#the-base-types-worth-knowing): Counts are the number of entity types with that base type anywhere in their chain.
- [Querying a base entity returns every descendant](schema/entity-model.md#querying-a-base-entity-returns-every-descendant): This is the payoff of the whole arrangement, and it is stated plainly in the official documentation:
- [The four cross-entity properties](schema/entity-model.md#the-four-cross-entity-properties): Four properties are on effectively every entity, and each answers a different question.
- [Key properties](schema/entity-model.md#key-properties): A key property is what identifies one instance.
- [Why some entities have no URI](schema/entity-model.md#why-some-entities-have-no-uri): Every entity inherits Uri, so every entity has the column.
- [Access control](schema/entity-model.md#access-control): Every entity page carries an Access control table mapping a set of operations to the Orion right that grants them, and every verb carries its own.
- [Where to go next](schema/entity-model.md#where-to-go-next): them.

### [Key entities](schema/key-entities.md)

The 2026.2 schema has 2067 entities.

- [Orion.Nodes](schema/key-entities.md#orionnodes): The device record.
- [Orion.NPM.Interfaces](schema/key-entities.md#orionnpminterfaces): One row per monitored interface.
- [Orion.Volumes](schema/key-entities.md#orionvolumes): Disks and logical volumes on a node, including the space and IOPS figures that capacity reports live on.
- [Orion.Engines](schema/key-entities.md#orionengines): The polling engines.
- [Orion.APM.Application](schema/key-entities.md#orionapmapplication): One monitored application instance, meaning one SAM template applied to one node.
- [Orion.APM.Component](schema/key-entities.md#orionapmcomponent): One monitored thing inside an application: a process, a port check, a performance counter, a script.
- [Orion.Groups and Orion.ContainerMembers](schema/key-entities.md#oriongroups-and-orioncontainermembers): Arbitrary collections of monitored objects that track an aggregate status.
- [Orion.Events](schema/key-entities.md#orionevents): The event log.
- [Orion.AuditingEvents](schema/key-entities.md#orionauditingevents): Who changed what, and when.
- [The alerting entities](schema/key-entities.md#the-alerting-entities): There are six, and picking the wrong one is the usual reason an alert query returns nothing.
- [Custom property entities](schema/key-entities.md#custom-property-entities): User-defined columns bolted onto a monitored object.
- [Cirrus.Nodes](schema/key-entities.md#cirrusnodes): Network Configuration Manager's own node record.
- [Orion.VIM.VirtualMachines](schema/key-entities.md#orionvimvirtualmachines): Virtual machines from Virtualization Manager.
- [Where to go next](schema/key-entities.md#where-to-go-next): does to your row count.

### [NetObject types and prefixes](schema/netobject-types.md)

A NetObject is Orion's short, type-tagged handle for one monitored object.

- [Where a NetObject string shows up](schema/netobject-types.md#where-a-netobject-string-shows-up): Any verb parameter named netObjectId typed as a string takes the prefixed form.
- [Building the string in SWQL](schema/netobject-types.md#building-the-string-in-swql): Fifteen entities in 2026.2 publish their own prefix as a queryable property, OrionIdPrefix.
- [A NetObject is not a SWIS URI](schema/netobject-types.md#a-netobject-is-not-a-swis-uri): They solve the same problem at different layers and are not interchangeable.
- [The table](schema/netobject-types.md#the-table): The full table (115 entries, sorted by module then entity) lives in ../reference/netobject-types.md, generated straight from data/reference/netobject-types.json by make docs-reference so it cannot drift from the data...
- [Confirming any of this on your own server](schema/netobject-types.md#confirming-any-of-this-on-your-own-server): Your server is the authority for your version and your licensed modules.
- [Related pages](schema/netobject-types.md#related-pages): the wire, and why argument order is the whole contract.

### [Relationships and navigation](schema/relationships.md)

The schema does not only record what properties an entity has.

- [The three relationship kinds](schema/relationships.md#the-three-relationship-kinds): Every relationship in 2026.2 has one of exactly three base types.
- [Both relationship tables are navigable](schema/relationships.md#both-relationship-tables-are-navigable): This is the single most common misunderstanding about the SWIS schema, so it is worth being blunt about.
- [Relationship coverage across the schema](schema/relationships.md#relationship-coverage-across-the-schema): Navigation is not evenly distributed, and knowing the shape saves time.
- [The navigations from Orion.Nodes worth memorising](schema/relationships.md#the-navigations-from-orionnodes-worth-memorising): All 161 are in python3 tools/schema_query.py show Orion.Nodes.
- [Finding a path](schema/relationships.md#finding-a-path): When you know the two ends but not the route, let the tool search.
- [Asking a live server instead](schema/relationships.md#asking-a-live-server-instead): Metadata.Relationship is the same information on your own installation, including modules this repository's extract does not cover, and it carries two things the published pages do not: cardinality, and the primary an...
- [Building automations on relationships.json](schema/relationships.md#building-automations-on-relationshipsjson): relationships.json is a flat edge list, which makes it directly usable as a graph.
- [Four things in the data that will surprise you](schema/relationships.md#four-things-in-the-data-that-will-surprise-you): These are all verified properties of the published 2026.2 schema, not bugs in the extraction.
- [Where to go next](schema/relationships.md#where-to-go-next): and ten worked examples.

### [Status codes](schema/status-codes.md)

Every monitored object in Orion carries a status, and it is stored as an integer.

- [The table](schema/status-codes.md#the-table): 26 status codes.
- [What Rank is for](schema/status-codes.md#what-rank-is-for): Rank orders severity so that a parent object can compute a status from its children.
- [Which statuses apply to what](schema/status-codes.md#which-statuses-apply-to-what): The descriptions carry this information, and getting it wrong produces filters that can never match.
- [Resolving status on a live server](schema/status-codes.md#resolving-status-on-a-live-server): Orion.StatusInfo is the lookup table, and it exists in 2026.2 with 12 properties, all readable by everyone:
- [Classifying a status without hard-coding an integer](schema/status-codes.md#classifying-a-status-without-hard-coding-an-integer): 2026.2 added Orion.Web.LegacyModules.RollupStatusInfo, and unlike Orion.StatusInfo every one of its 16 properties carries summary text.
- [Status versus PolledStatus](schema/status-codes.md#status-versus-polledstatus): Orion.Nodes declares both Status and PolledStatus, both System.Int32.
- [Other status-shaped properties to know before writing a filter](schema/status-codes.md#other-status-shaped-properties-to-know-before-writing-a-filter): Several properties look like status and are not, and mistaking one for another is a quiet way to build a report that is subtly wrong.
- [Related pages](schema/status-codes.md#related-pages): the rest of the traps.

### [Using the extracted data](schema/using-the-data.md)

Everything under data/ is generated.

- [What is in data/](schema/using-the-data.md#what-is-in-data): Provenance decides how much weight a claim deserves.
- [jq recipes](schema/using-the-data.md#jq-recipes): Every command below was run against the checked-in 2026.2 data and the output is real.
- [The tools](schema/using-the-data.md#the-tools): Everything lives in tools/, and nothing there needs anything beyond the Python standard library except openpyxl, which is used only to read the source workbook.
- [Regenerating for a different platform version](schema/using-the-data.md#regenerating-for-a-different-platform-version): The published SDK site carries several versions side by side, and this repository documents one at a time.
- [Before you commit anything](schema/using-the-data.md#before-you-commit-anything): That runs the toolchain unit tests, validates every sample query and every sql block in the documentation, asserts the extracted data is intact, confirms every entity name mentioned in prose actually exists, checks th...
- [Where to go next](schema/using-the-data.md#where-to-go-next): data means.

## docs/modules/

### [Module Guides](modules/README.md)

The platform is one installation, one database, and one API, but the data model is built up by many products.

- [The modules](modules/README.md#the-modules): Entity counts are exact for the 2026.2 extraction in data/schema/2026.2/index.json: they count every entity whose name equals the listed prefix or begins with that prefix plus a dot.
- [Prefixes are engineering names, not product names](modules/README.md#prefixes-are-engineering-names-not-product-names): Do not derive an entity name from a product name.
- [An entity only exists if its module does](modules/README.md#an-entity-only-exists-if-its-module-does): This is the single most important thing to understand about this section.
- [Checking offline instead](modules/README.md#checking-offline-instead): Everything in the table came from the extracted data, and you can interrogate it the same way without a server:
- [Related pages](modules/README.md#related-pages)

### [Agents: the SolarWinds agent](modules/agents.md)

Every other way the platform collects data is a pull from the outside.

- [When to use an agent instead of SNMP or WMI](modules/agents.md#when-to-use-an-agent-instead-of-snmp-or-wmi): The schema itself tells you most of what the trade is.
- [Namespaces and how many entities](modules/agents.md#namespaces-and-how-many-entities): Agent management contributes 16 entities, all under Orion.AgentManagement..
- [The agent record](modules/agents.md#the-agent-record): Orion.AgentManagement.Agent inherits directly from System.Entity, so it gets Uri, DisplayName, Description and InstanceType and nothing else.
- [The two status columns, and why they disagree with each other](modules/agents.md#the-two-status-columns-and-why-they-disagree-with-each-other): This is the part of the module that produces the most confused tickets, so it is worth being precise.
- [Plugins](modules/agents.md#plugins): A plugin is what makes an agent useful.
- [Proxies](modules/agents.md#proxies): Orion.AgentManagement.Proxy is four properties describing an HTTP proxy that agent-to-AMS traffic goes through:
- [The agent lifecycle](modules/agents.md#the-agent-lifecycle): Four phases, and each one is a different set of verbs.
- [The verbs, in full](modules/agents.md#the-verbs-in-full): All 20, with the parameter order that is the entire contract.
- [Worked queries](modules/agents.md#worked-queries): Every query below was validated against the 2026.2 schema with python3 tools/validate_swql.py.
- [Gotchas](modules/agents.md#gotchas): ConnectionStatus says whether AMS can talk to the agent; AgentStatus says whether the agent software is healthy and current.
- [Related pages](modules/agents.md#related-pages): is attached to, and for DeployToNode's starting point.
- [Official SolarWinds documentation](modules/agents.md#official-solarwinds-documentation): ConnectionStatus and AgentStatus value tables, the C# verb signatures, and the ValidateDeploymentCredentials return tuple - DeployAgentViaVerb.ps1, the annotated catalogue of Deploy argument combinations - ImportListR...

### [Cloud monitoring: AWS, Azure and GCP](modules/cloud.md)

Cloud monitoring is how the platform watches infrastructure it cannot reach with SNMP or WMI.

- [Namespace and how it divides](modules/cloud.md#namespace-and-how-it-divides): Forty-four of the 148 are *Statistics entities, which is the clearest sign of the repeating shape: nearly every monitored service type has a sibling holding its time series.
- [Accounts, providers and regions](modules/cloud.md#accounts-providers-and-regions): One row per cloud account or subscription being monitored.
- [Scope: job settings, selected regions and tag filters](modules/cloud.md#scope-job-settings-selected-regions-and-tag-filters): Three small entities decide what a cloud account actually polls, and they chain together.
- [Instances, volumes, and becoming a node](modules/cloud.md#instances-volumes-and-becoming-a-node): The generic compute instance, and the entity that carries the module's verbs.
- [The Local. entities in the CRUD surface](modules/cloud.md#the-local-entities-in-the-crud-surface): If you read SolarWinds' Swagger contract for 2026.2 rather than the rendered schema, you will find fifteen /Create/Local.Orion.Cloud.* paths alongside the ordinary ones: an Accounts form for each of the three provider...
- [Verbs](modules/cloud.md#verbs): Fourteen verbs across five entities.
- [Worked queries](modules/cloud.md#worked-queries): Every query below has been validated against the 2026.2 schema with python3 tools/validate_swql.py.
- [Gotchas](modules/cloud.md#gotchas): Orion.Cloud.ResourseTags, Orion.Cloud.Aws.ResourseTags, Orion.Cloud.Azure.ResourseTags.
- [What is not verified here](modules/cloud.md#what-is-not-verified-here)
- [Related pages](modules/cloud.md#related-pages): inherit from, and for on-premises virtualisation.

### [DPA: Database Performance Analyzer](modules/dpa.md)

Database Performance Analyzer answers a question the rest of the platform cannot: not "is the database server up" but "what is the database waiting on".

- [Two namespaces, and the split is the important part](modules/dpa.md#two-namespaces-and-the-split-is-the-important-part): DPA contributes 27 entities in 2026.2, divided unevenly across two namespaces, and the division is not cosmetic.
- [Orion.DPA.DatabaseInstance is the hinge](modules/dpa.md#oriondpadatabaseinstance-is-the-hinge): Everything in DPA is anchored on one entity.
- [How an instance relates to a node, an application and a LUN](modules/dpa.md#how-an-instance-relates-to-a-node-an-application-and-a-lun): This is the part of DPA that most affects how you write queries, because a DPA database instance is not automatically the same object as the node you already monitor.
- [The DPA entities are requests, not tables](modules/dpa.md#the-dpa-entities-are-requests-not-tables): This is the trap that costs the most time.
- [Verbs](modules/dpa.md#verbs): DPA publishes exactly one verb in 2026.2, and it is an integration control rather than a monitoring action.
- [Worked queries](modules/dpa.md#worked-queries): Every query below has been validated against the 2026.2 schema with python3 tools/validate_swql.py.
- [Gotchas](modules/dpa.md#gotchas): Orion.DPA.DatabaseInstance declares read only.
- [What is not verified here](modules/dpa.md#what-is-not-verified-here): There is no DPA page in SolarWinds' published OrionSDK documentation and no DPA sample script in the SDK samples, so the schema, the Swagger contract and your own server are the only sources.
- [Related pages](modules/dpa.md#related-pages): platform watches a database.

### [Hardware Health: sensors on physical machines](modules/hardware-health.md)

Hardware health is the sensor layer: fan speeds, power supply state, inlet and exhaust temperatures, physical and logical disk state, RAID controller battery status, memory module errors, and whatever else the vendor'...

- [It is not a module you buy](modules/hardware-health.md#it-is-not-a-module-you-buy): This is the first thing to get straight, because it changes how you reason about whether the entities will be there.
- [Namespace and size](modules/hardware-health.md#namespace-and-size): Everything lives under Orion.HardwareHealth., which holds 33 entities in the 2026.2 schema, with 9 verbs declared across four of them.
- [The three-level model](modules/hardware-health.md#the-three-level-model): Hardware health has exactly three levels, and each has a *Base entity that declares the properties plus per-parent subtypes that add little beyond the parent's key.
- [Sensors are typed by category](modules/hardware-health.md#sensors-are-typed-by-category): A sensor's type is not a string on the sensor.
- [Reading a sensor's state](modules/hardware-health.md#reading-a-sensors-state): A sensor row carries four different things that all look like status, and they are not interchangeable:
- [Thresholds](modules/hardware-health.md#thresholds): Orion.HardwareHealth.HardwareItemThreshold is a small entity keyed by the sensor's ID, with Warning and Critical.
- [Historical data](modules/hardware-health.md#historical-data): Three statistics entities hang off HardwareItemBase, all inheriting ObservationTimestamp and ObservationFrequency from System.StatisticsEntity.
- [The BMC family](modules/hardware-health.md#the-bmc-family): Eight entities under Orion.HardwareHealth.BMC.
- [Verbs](modules/hardware-health.md#verbs): Nine verbs.
- [Worked queries](modules/hardware-health.md#worked-queries): Every query below has been validated against the 2026.2 schema with tools/validate_swql.py.
- [Gotchas](modules/hardware-health.md#gotchas): HardwareItemValueStatistics.HardwareItem navigates to Orion.HardwareHealth.HardwareItemBase, which has no Node property, because a base row might belong to a chassis or a storage array.
- [See also](modules/hardware-health.md#see-also): with them.

### [IPAM: IP Address Manager](modules/ipam.md)

IP Address Manager is the module that replaces the spreadsheet.

- [Namespaces and how many entities](modules/ipam.md#namespaces-and-how-many-entities): IPAM contributes 77 entities, all under a bare IPAM.
- [The API changed shape across versions, and SolarWinds documents it that way](modules/ipam.md#the-api-changed-shape-across-versions-and-solarwinds-documents-it-that-way): This matters more for IPAM than for any other module.
- [The hierarchy: groups, supernets, subnets](modules/ipam.md#the-hierarchy-groups-supernets-subnets): Everything in IPAM's tree is a row in IPAM.GroupNode, and GroupType says which kind of thing it is.
- [IP nodes and their status](modules/ipam.md#ip-nodes-and-their-status): IPAM.IPNode is one row per address, not one row per device.
- [Conflicts](modules/ipam.md#conflicts): Conflict detection is the reason people buy IPAM rather than keeping the spreadsheet, and there are five separate conflict entities covering three different kinds of conflict: three views of an address-level conflict,...
- [DHCP integration](modules/ipam.md#dhcp-integration): IPAM does not just record what your DHCP servers do.
- [DNS integration](modules/ipam.md#dns-integration): The DNS side is smaller and reads the same way.
- [Scanning](modules/ipam.md#scanning): IPAM finds out what is really on an address by scanning it, and the scan queue is visible.
- [The address request workflow](modules/ipam.md#the-address-request-workflow): IPAM has a built-in request queue so that people who need an address ask for one instead of picking one.
- [Custom properties](modules/ipam.md#custom-properties): IPAM has two custom property mechanisms, from two different eras, and both are live in 2026.2.
- [Verbs](modules/ipam.md#verbs): IPAM declares 67 verbs, an unusually rich surface for a module of 77 entities, and they are concentrated on eight entities:
- [Worked queries](modules/ipam.md#worked-queries): Every query below was validated against the 2026.2 schema with python3 tools/validate_swql.py.
- [Gotchas](modules/ipam.md#gotchas): IPAM.Subnet.SubnetId and IPAM.GroupNode.GroupId are both System.Int32 and both look like a subnet id, so passing the wrong one produces an error about a subnet that does not exist rather than a type failure.
- [Related pages](modules/ipam.md#related-pages): address, UDT says which switch port it is plugged into.
- [Official SolarWinds documentation](modules/ipam.md#official-solarwinds-documentation): which links all seven per-version pages - IPAM vNext API, the closest match to 2026.2 for the range, group and IPv6 reservation verbs - IPAM Observability 2022.2 API, which carries the fullest AddDhcpScope documentati...

### [Log Analyzer: syslog, traps and log files](modules/log-analyzer.md)

Log Analyzer is where messages the platform did not ask for arrive.

- [Read this before you write a query](modules/log-analyzer.md#read-this-before-you-write-a-query): Orion.OLM.LogEntry is almost certainly the largest thing you can query on the installation.
- [Namespace and how many entities](modules/log-analyzer.md#namespace-and-how-many-entities): Everything is under Orion.OLM., which holds 21 entities in 2026.2.
- [Orion.OLM.LogEntry is the module](modules/log-analyzer.md#orionolmlogentry-is-the-module): "Stored messages or events", ten properties, read-only for everyone.
- [Message sources, nodes and licensing](modules/log-analyzer.md#message-sources-nodes-and-licensing): This is the part of the module people get wrong, and the schema explains it clearly if you read the two entity descriptions together.
- [Log profiles and agents](modules/log-analyzer.md#log-profiles-and-agents): Syslog and traps arrive on their own.
- [Rule processing and the alerting integration](modules/log-analyzer.md#rule-processing-and-the-alerting-integration): Log Analyzer does not have its own alert engine.
- [Verbs](modules/log-analyzer.md#verbs): Eleven verbs across three entities.
- [The rule export format](modules/log-analyzer.md#the-rule-export-format): ExportRules returns JSON and ImportRules takes it.
- [Worked queries](modules/log-analyzer.md#worked-queries): Every query below has been validated against the 2026.2 schema with python3 tools/validate_swql.py.
- [Gotchas](modules/log-analyzer.md#gotchas): This is the largest table on most installations.
- [What is not verified here](modules/log-analyzer.md#what-is-not-verified-here)
- [Related pages](modules/log-analyzer.md#related-pages): source mappings.

### [NCM compliance policy reports: the export file and its round trip](modules/ncm-compliance-reports.md)

A policy report checks device configurations against rules and reports the violations.

- [The three-tier structure](modules/ncm-compliance-reports.md#the-three-tier-structure): The same rule can appear in several policies and the same policy in several reports — the file denormalizes that: each export carries complete copies of everything it uses.
- [The file](modules/ncm-compliance-reports.md#the-file): All three sample files declare encoding="utf-16" in the XML prolog while the bytes on disk are UTF-8.
- [The SWIS round trip (2026.2, verified)](modules/ncm-compliance-reports.md#the-swis-round-trip-20262-verified): All writes are Invoke verbs on Cirrus.PolicyReports — the Cirrus.Policy* SWQL entities are read-only.
- [Porter](modules/ncm-compliance-reports.md#porter): The Porter utility in this repository (apps/porter) implements this round trip as its NCM Compliance area: console-compatible XML out (UTF-16, matching element order), AddPolicyReport with importFlag true in, name-col...
- [From a DISA STIG package](modules/ncm-compliance-reports.md#from-a-disa-stig-package): Reports in this format can also be generated from DISA's own XCCDF STIG downloads rather than a console export — one policy per benchmark, one rule per requirement, fix text as never-auto-executed remediation.

### [NCM device templates: the .ConfigMgmtCommands format](modules/ncm-device-templates.md)

A device template tells NCM how to talk to one kind of device over Telnet or SSH: which command shows the running config, how to get into configuration mode, what the prompt looks like when the session is privileged,...

- [The file](modules/ncm-device-templates.md#the-file): No namespace, no schema declaration — this is the oldest and simplest of the platform's export formats, and the 2007 copyright header on the shipped ones says so.
- [The commands](modules/ncm-device-templates.md#the-commands): Every entry is <Command Name="…" Value="…" />.
- [The macros](modules/ncm-device-templates.md#the-macros): Values are templates, and ${…} substitutions come from three places.
- [The three execution modes](modules/ncm-device-templates.md#the-three-execution-modes): The console offers three levels when running a script against a device, and they map onto different verbs and different NCM roles:
- [Import and export through SWIS](modules/ncm-device-templates.md#import-and-export-through-swis): Unlike API poller templates, SAM templates and Log Analyzer rules, Cli.DeviceTemplates is a plain CRUD entity — the document lives in a column and you read and write it like any other row.
- [Writing one](modules/ncm-device-templates.md#writing-one): Start from a shipped template for a device of the same family and edit it.
- [What this repository has not verified](modules/ncm-device-templates.md#what-this-repository-has-not-verified)
- [See also](modules/ncm-device-templates.md#see-also): queue - ../webui/ncm-change-templates.md — change templates, which are a different artefact: what to send, rather than how to talk to the device - ../webui/ncm-change-template-language.md — the change template scripti...

### [NCM: Network Configuration Manager](modules/ncm.md)

Network Configuration Manager is the module that logs in to a device rather than polling it.

- [Namespaces and how many entities](modules/ncm.md#namespaces-and-how-many-entities): NCM contributes 129 entities split across two prefixes, and the split confuses everybody who meets it for the first time:
- [Cirrus.Nodes and its relationship to Orion.Nodes](modules/ncm.md#cirrusnodes-and-its-relationship-to-orionnodes): NCM keeps its own node table, and it is not Orion.Nodes.
- [Configuration archives](modules/ncm.md#configuration-archives): Cirrus.ConfigArchive is one row per captured configuration revision, and it is where NCM's value actually sits.
- [Transfers: how NCM reports what it did to a device](modules/ncm.md#transfers-how-ncm-reports-what-it-did-to-a-device): Every download, upload and script execution is a transfer, and every transfer produces a ticket.
- [Comparison and diff results](modules/ncm.md#comparison-and-diff-results): NCM compares configurations continuously and caches the answers rather than diffing on demand.
- [Baselines](modules/ncm.md#baselines): There are two different things called a baseline, and they are not the same feature.
- [Compliance: policies, rules, reports and violations](modules/ncm.md#compliance-policies-rules-reports-and-violations): Compliance is a four-level structure, and the names are easy to mix up because the noun "policy" appears at three of the four levels.
- [Config change templates and snippets](modules/ncm.md#config-change-templates-and-snippets): What the web console calls a config change template is Cirrus.ConfigSnippets in the API.
- [Connection profiles](modules/ncm.md#connection-profiles): A connection profile is a named bundle of CLI credentials and protocol choices that many nodes share, so you are not storing the same password on 400 node rows.
- [The approval queue](modules/ncm.md#the-approval-queue): If approvals are switched on, a config upload or a script execution does not run when it is requested.
- [Firmware upgrade](modules/ncm.md#firmware-upgrade): Firmware upgrade is NCM.* only, and it is a two-phase operation by design: you prepare, you review, then you start.
- [End of life, end of sales, end of support](modules/ncm.md#end-of-life-end-of-sales-end-of-support): The EoS block on Cirrus.Nodes (EndOfSupport, EndOfSales, EndOfSoftware, ReplacementPartNumber) is populated by a matching process, and EosType records how each row got its values: 0 not assigned, 1 user, 2 manual, 3 a...
- [Jobs](modules/ncm.md#jobs): NCM schedules its own work rather than using the platform's scheduler.
- [Inventory and parsed configuration](modules/ncm.md#inventory-and-parsed-configuration): Beyond configuration text, NCM runs an inventory that fills a wide set of read-only tables.
- [Verbs](modules/ncm.md#verbs): NCM declares 160 verbs, 132 in Cirrus.
- [Worked queries](modules/ncm.md#worked-queries): Every query below was validated against the 2026.2 schema with python3 tools/validate_swql.py.
- [Worked verb examples](modules/ncm.md#worked-verb-examples): All of these use SwisPowerShell.
- [Gotchas](modules/ncm.md#gotchas): Cirrus.Nodes.NodeID is a System.Guid.
- [Related pages](modules/ncm.md#related-pages): what NCM does for device configuration — profiles, change records and baselines.
- [Official SolarWinds documentation](modules/ncm.md#official-solarwinds-documentation): including NCM.ExecuteScript.ps1, NCMProfile.ps1 and NTA.DownloadRouterConfigFromNCM.ps1

### [NPM: Network Performance Monitor](modules/npm.md)

Network Performance Monitor is the module that turns a monitored node into a monitored network.

- [Namespaces and how many entities](modules/npm.md#namespaces-and-how-many-entities): NPM's headline entities live under five prefixes.
- [Interfaces are the core entity](modules/npm.md#interfaces-are-the-core-entity): Orion.NPM.Interfaces is where most NPM work starts and where most of it ends.
- [Universal device pollers](modules/npm.md#universal-device-pollers): Universal Device Pollers, called UnDP in the product and "custom pollers" in the schema, are NPM's mechanism for collecting arbitrary SNMP OIDs.
- [Wireless](modules/npm.md#wireless): Wireless is the part of NPM where guessing an entity name is most likely to fail, because four families with overlapping names coexist in 2026.2.
- [Routing](modules/npm.md#routing): Orion.Routing.
- [NetPath](modules/npm.md#netpath): NetPath probes a service from a location and reconstructs the path, hop by hop, including hops you do not own.
- [Multicast](modules/npm.md#multicast): Orion.NPM.MulticastRouting.
- [F5 and Cisco UCS](modules/npm.md#f5-and-cisco-ucs): Both families were reorganised, and old entity names that circulate in the community no longer resolve.
- [Smaller families in the NPM namespace](modules/npm.md#smaller-families-in-the-npm-namespace): Two entities are named misleadingly and worth flagging.
- [Verbs](modules/npm.md#verbs): NPM is a read-heavy module.
- [Worked queries](modules/npm.md#worked-queries): Every query below has been validated against the 2026.2 schema.
- [Gotchas](modules/npm.md#gotchas): Unmanage and Remanage type it as a string and document the example 'I:1', so they want the NetObject form.
- [Related pages](modules/npm.md#related-pages): prefixes the verbs need.
- [Official SolarWinds documentation](modules/npm.md#official-solarwinds-documentation): NPM.DiscoverAndAddInterfacesOnNode.ps1 and Interface.Cleanup.ps1

### [NTA: NetFlow Traffic Analyzer](modules/nta.md)

Every other monitoring module tells you how much traffic crossed an interface.

- [Namespaces and how many entities](modules/nta.md#namespaces-and-how-many-entities): All 49 NTA entities live under a single prefix, Orion.Netflow., spelled with a lowercase f.
- [Flow sources: what NTA is allowed to receive](modules/nta.md#flow-sources-what-nta-is-allowed-to-receive): A device sends flow records to the collector whether or not NTA is expecting them, because flow export is one-way UDP.
- [Flow records: one table and eleven views over it](modules/nta.md#flow-records-one-table-and-eleven-views-over-it): Orion.Netflow.Flows exposes flows as NTA received them, at the finest granularity available, which is how SolarWinds' own NTA 4.0 Entity Model describes it.
- [CBQoS](modules/nta.md#cbqos): Class-based QoS answers a different question from flow: not "what is on the wire" but "what did the router's own queueing do with it".
- [Verbs](modules/nta.md#verbs): NTA publishes 12 verbs across four entities.
- [Flow tables are enormous, and TOP does not save you](modules/nta.md#flow-tables-are-enormous-and-top-does-not-save-you): This is the section to read before writing any query on this page.
- [Worked queries](modules/nta.md#worked-queries): Every query below has been validated against the 2026.2 schema.
- [Gotchas](modules/nta.md#gotchas): Covered above, and it is the single most expensive misunderstanding in this module.
- [Related pages](modules/nta.md#related-pages): packet inspection rather than flow export.
- [Official SolarWinds documentation](modules/nta.md#official-solarwinds-documentation): which is the authoritative explanation of the duplicating views and of the relative-date performance warning.

### [QoE: Quality of Experience](modules/qoe.md)

Quality of Experience is the platform's packet-inspection capability.

- [Namespace and how many entities](modules/qoe.md#namespace-and-how-many-entities): QoE contributes exactly 14 entities, all under Orion.DPI., for deep packet inspection, which is how ../platform/modules.md describes the prefix.
- [Applications are the centre of the model](modules/qoe.md#applications-are-the-centre-of-the-model): Orion.DPI.Applications is one row per application QoE knows about, whether it is currently being observed or not.
- [Probes](modules/qoe.md#probes): A probe is the thing doing the packet inspection.
- [Statistics and thresholds](modules/qoe.md#statistics-and-thresholds): Orion.DPI.QoeStatistics is the history and the only QoE entity that inherits from System.StatisticsEntity.
- [Verbs](modules/qoe.md#verbs): QoE publishes five verbs, all on Orion.DPI.Probes.
- [How QoE relates to SAM applications](modules/qoe.md#how-qoe-relates-to-sam-applications): This is the question the module's naming invites, and the honest answer has two halves.
- [Worked queries](modules/qoe.md#worked-queries): Every query below has been validated against the 2026.2 schema.
- [Gotchas](modules/qoe.md#gotchas): Orion.DPI.Probes, Orion.DPI.Applications, Orion.DPI.ApplicationSettings, Orion.DPI.ApplicationAssignments, Orion.DPI.ProbeSettings, Orion.DPI.ProbeProperties and Orion.DPI.ProbeAssignments all declare create,read,upda...
- [What is not verified here](modules/qoe.md#what-is-not-verified-here): The schema for this module is thin on descriptions, and rather than fill the gaps with plausible narrative, these are the specific things this page could not confirm and how to settle each one on your own server.
- [Related pages](modules/qoe.md#related-pages): for asking a live server what it actually has.

### [A SAM template for Citrix Hypervisor (XenServer)](modules/sam-citrix-hypervisor-template.md)

SolarWinds does not ship an AppInsight application for Citrix Hypervisor (formerly XenServer, and the commercial counterpart of XCP-ng), but a real, community-sourced template for it exists on SolarWinds' Content Exch...

- [Supported versions](modules/sam-citrix-hypervisor-template.md#supported-versions): Its own Description states "Prerequisites: Hypervisor 8.0" in as many words, and its Tags list includes 8.0 alongside Citrix and Hypervisor.
- [What a fourth real export corrected](modules/sam-citrix-hypervisor-template.md#what-a-fourth-real-export-corrected): An earlier version of both this template and this page assumed several things about SAM script components that turned out to be wrong once a real, working Citrix Hypervisor export was available to check them against.
- [Two templates, not one](modules/sam-citrix-hypervisor-template.md#two-templates-not-one): Rather than try to reproduce the reference template's 63 components, this repository ships a smaller, complementary template: citrix-hypervisor-monitoring.apmtemplate, six components covering pool-wide inventory facts...
- [The CommandLineToPass argument-prompt mechanism](modules/sam-citrix-hypervisor-template.md#the-commandlinetopass-argument-prompt-mechanism): This is the mechanism that makes a single-component, single-metric template usable across different hosts and VMs without hand-editing the .apmtemplate file per target, and it was missed entirely in this template's fi...
- [xe commands and data source names](modules/sam-citrix-hypervisor-template.md#xe-commands-and-data-source-names): Every xe invocation and RRD data source name in this template's host-level components (cpu_avg, memory_free_kib, memory_total_kib, pif_<interface>_rx/_tx, and the xe host-data-source-query hostname=$Hostname data-sour...
- [Assign it like any other template](modules/sam-citrix-hypervisor-template.md#assign-it-like-any-other-template): Nothing about assignment is Citrix-specific; it is exactly the flow in sam.md.
- [What is verified here and what is not](modules/sam-citrix-hypervisor-template.md#what-is-verified-here-and-what-is-not): namespace, the LinuxScript setting keys (AuthenticationType, CommandLineToPass, CountAsDifference, Port, ScriptBody, ScriptDirectory, StatusRollupType), the TcpPort keys (PortNumber and the Response threshold), and th...
- [Known limitations](modules/sam-citrix-hypervisor-template.md#known-limitations): (CPU, memory, disk, network, per-vCPU run states) already cover this territory in detail, one component per metric with a VirtualMachineUuid (and sometimes a second identifier such as CPU Name) prompt at assignment time.
- [The API Poller alternative](modules/sam-citrix-hypervisor-template.md#the-api-poller-alternative): scripts/api-pollers/citrix-hypervisor-xenapi.apipoller.template remains in this repository as an experimental sketch of reaching XenAPI's JSON-RPC endpoint directly over HTTPS instead of through SSH and xe.
- [Status and open questions for whoever picks this up next](modules/sam-citrix-hypervisor-template.md#status-and-open-questions-for-whoever-picks-this-up-next): component.
- [See also](modules/sam-citrix-hypervisor-template.md#see-also): sample's corrections to element order, the Settings namespace, and DynamicColumnSettings - sam.md — SAM entities, verbs, and assigning a template to a node - ../../scripts/sam-templates/ — the template file itself - ....

### [The .apmtemplate file format](modules/sam-templates.md)

A SAM application template exports from Settings > All Settings > SAM Settings > Manage Templates > Export as an XML document with the extension .apmtemplate.

- [The root is an array](modules/sam-templates.md#the-root-is-an-array): All three samples hold exactly one, but the root element is a collection, so a multi-template export is expressible.
- [The template](modules/sam-templates.md#the-template): Sixteen child elements, all present in all three samples:
- [Settings are a typed key/value map](modules/sam-templates.md#settings-are-a-typed-keyvalue-map): Both the template and each component carry a Settings map, serialised as .NET dictionary entries with a mangled type name:
- [Components](modules/sam-templates.md#components): ComponentTemplates holds one ComponentTemplate per monitor.
- [Credentials do not travel, and neither do secrets](modules/sam-templates.md#credentials-do-not-travel-and-neither-do-secrets): The export does not reference a credential set, let alone contain one.
- [Moving a template between servers](modules/sam-templates.md#moving-a-template-between-servers): A matched pair of verbs, unlike reports, where export is a query and import is a verb.
- [Writing one by hand](modules/sam-templates.md#writing-one-by-hand): Build it in the console and export.
- [See also](modules/sam-templates.md#see-also): built to this format, monitoring a Citrix Hypervisor host with no AppInsight module - sam-udp-port-exhaustion-template.md — a second worked template, PowerShell over WinRM plus native counters, for Windows UDP port ex...

### [A SAM template for Windows UDP ephemeral port exhaustion](modules/sam-udp-port-exhaustion-template.md)

Windows hands every outbound UDP socket a port from one dynamic range (49152–65535 by default, 16,384 ports).

- [Why a script and not a counter](modules/sam-udp-port-exhaustion-template.md#why-a-script-and-not-a-counter): The candidates, against the SAM component types:
- [The components](modules/sam-udp-port-exhaustion-template.md#the-components): Components 1 and 2 run the same script; the argument in ScriptArguments picks which number it reports, the way SolarWinds' own clock-drift template passes its time server.
- [The event log components](modules/sam-udp-port-exhaustion-template.md#the-event-log-components): Components 7 and 8 are Windows Event Log Monitors with LogName = Custom, LogNameFilter = System, EntrySource = Tcpip, EntryIDType = IncludeIDs with the one id, EntryType = Warning (the level Windows assigns to both ev...
- [Assigning it](modules/sam-udp-port-exhaustion-template.md#assigning-it): The PowerShell component needs a credential that can open a WinRM session on the target and has rights to read the socket table, which any local administrator has.
- [Finding the culprit once it fires](modules/sam-udp-port-exhaustion-template.md#finding-the-culprit-once-it-fires): The Message: line names the processes.
- [What is verified and what is not](modules/sam-udp-port-exhaustion-template.md#what-is-verified-and-what-is-not): Verified against a real export (SolarWinds' Server Clock Drift (PowerShell) template, exported from a 2026.4 server on 2026-09-17):
- [See also](modules/sam-udp-port-exhaustion-template.md#see-also): in this repository, and the real export both are shaped against - sam.md — assigning a template and testing components

### [SAM: Server and Application Monitor](modules/sam.md)

Server and Application Monitor is the module that monitors what runs on a node rather than the node itself: Windows services, Linux processes, listening ports, HTTP endpoints, SQL queries, PowerShell and Perl scripts,...

- [Namespace and size](modules/sam.md#namespace-and-size): Everything SAM contributes lives under Orion.APM., which holds 140 entities in the 2026.2 schema.
- [The template, application, component model](modules/sam.md#the-template-application-component-model): This is the model everything else in SAM hangs off, and it is worth getting exactly right because the four levels have four different entities and it is easy to reach for the wrong one.
- [Applications and components in detail](modules/sam.md#applications-and-components-in-detail): Twenty-five properties, seven verbs, and six entities inherit from it.
- [AppInsight applications](modules/sam.md#appinsight-applications): AppInsight monitors are, in SolarWinds' own words from SAM AppInsight Applications, "considered templates until applied" and are "a member of the Application Monitor Templates collection".
- [Windows scheduled tasks](modules/sam.md#windows-scheduled-tasks): Orion.APM.Wstm.Task is populated by the stock "Windows Scheduled Tasks" template.
- [TCP connections and application dependencies](modules/sam.md#tcp-connections-and-application-dependencies): SAM's connection mapping produces three related entities:
- [Verbs](modules/sam.md#verbs): All thirty-nine SAM verbs, with parameters in the order they must be passed.
- [Worked queries](modules/sam.md#worked-queries): Each of these has been validated against the 2026.2 schema with tools/validate_swql.py.
- [Assigning a template from PowerShell](modules/sam.md#assigning-a-template-from-powershell): Adapted from SolarWinds' Samples/PowerShell/SAM.Application.ps1.
- [Gotchas](modules/sam.md#gotchas): Orion.APM.Application.Unmanage misspells its first parameter as netObjetId, missing the c.
- [See also](modules/sam.md#see-also): template covering Citrix Hypervisor, a platform with no stock SAM template or AppInsight - sam-udp-port-exhaustion-template.md — a hand-built template for Windows UDP ephemeral port exhaustion, the condition behind Tc...

### [SCM compliance policies: the YAML format and its round trip](modules/scm-compliance-policies.md)

Server Configuration Monitor's compliance side answers a different question than its drift-detection side.

- [The entity model](modules/scm-compliance-policies.md#the-entity-model): Orion.PolicyEngine.
- [The file](modules/scm-compliance-policies.md#the-file): A policy is one YAML document using application-specific tags.
- [The SWIS round trip (2026.2, verified)](modules/scm-compliance-policies.md#the-swis-round-trip-20262-verified): The verbs live on Orion.PolicyEngine.Policy.
- [DISA STIGs, two modules, one repository](modules/scm-compliance-policies.md#disa-stigs-two-modules-one-repository): The same STIG exists in two shapes in this repository's world: DISA's own XCCDF zip (imported into NCM compliance for network devices) and SolarWinds' SCM policy YAML (evaluated agent-side on servers).

### [SCM: Server Configuration Monitor](modules/scm.md)

Server Configuration Monitor watches the configuration of servers the way NCM watches the configuration of network devices: it collects files, registry keys, script output and query results from monitored nodes on a s...

- [Namespace and size](modules/scm.md#namespace-and-size): SCM contributes 23 entities, all under Orion.SCM., and 10 verbs across three of them.
- [The model, from profile to change record](modules/scm.md#the-model-from-profile-to-change-record): One row per node SCM monitors, keyed by NodeID and hosted by Orion.Nodes — from the platform side the navigation is Orion.Nodes.SCMNode, from this side it is Node.
- [Verbs](modules/scm.md#verbs): SCM publishes 10 verbs across three entities: five on Orion.SCM.Profiles, four on Orion.SCM.ServerConfiguration, one on Orion.SCM.Baseline.
- [Worked queries](modules/scm.md#worked-queries): Every query below has been validated against the 2026.2 schema with tools/validate_swql.py.
- [Gotchas](modules/scm.md#gotchas): Orion.SCM.Results.ElementContents declares read for admin and nothing for anyone else, so every other account sees the metadata but an empty result for content — a permissions effect that looks like missing data.
- [Related pages](modules/scm.md#related-pages): poll-now shapes.

### [SRM: Storage Resource Monitor](modules/srm.md)

Every other part of the platform sees storage the way a server sees it: a drive letter, a mount point, a percentage full.

- [Namespace and size](modules/srm.md#namespace-and-size): All 135 SRM entities live under one prefix, Orion.SRM., with the module code spelled in capitals.
- [SRM volumes are not Orion volumes](modules/srm.md#srm-volumes-are-not-orion-volumes): This deserves its own section because conflating the two is the classic SRM error, and the symptom is a report that looks plausible and is wrong.
- [The storage hierarchy](modules/srm.md#the-storage-hierarchy): SRM models two paths through an array, block and file, that share the top of the tree and diverge below the pool.
- [Statistics](modules/srm.md#statistics): Twelve statistics entities cover seven of the object types.
- [Thresholds](modules/srm.md#thresholds): SRM's thresholds are the most numerous part of the namespace and the least interesting per entity, because they are all the same shape.
- [Verbs](modules/srm.md#verbs): SRM publishes 108 verbs across 13 entities, and they split into two very different groups.
- [Worked queries](modules/srm.md#worked-queries): Every query below has been validated against the 2026.2 schema with tools/validate_swql.py.
- [Gotchas](modules/srm.md#gotchas): Different layer, different id space, same column name for the key.
- [See also](modules/srm.md#see-also): joins.

### [UDT: User Device Tracker](modules/udt.md)

User Device Tracker exists to answer one question: where is this device plugged in?

- [Namespaces and how many entities](modules/udt.md#namespaces-and-how-many-entities): UDT contributes 85 entities, all under Orion.UDT..
- [The current and history pattern](modules/udt.md#the-current-and-history-pattern): This is the structural idea in UDT and it repeats four times.
- [The correlation chain](modules/udt.md#the-correlation-chain): Four entities and three joins get you from a name to a port.
- [Ports](modules/udt.md#ports): Orion.UDT.Port is a physical switch port, and it is not an NPM interface.
- [The other entities that carry the whole load](modules/udt.md#the-other-entities-that-carry-the-whole-load): Beyond the chain and the ports, five denormalised views do most of the real work, and it is worth knowing which one has which columns because their names are nearly identical.
- [Rogue devices](modules/udt.md#rogue-devices): A rogue in UDT is not a device that broke in.
- [Watch lists](modules/udt.md#watch-lists): A watch list is the opposite of a rogue list: a set of specific things you want to be told about when they appear.
- [Users](modules/udt.md#users): If UDT is configured with Active Directory credentials it also tracks which account is logged on to which address.
- [Topology and inventory](modules/udt.md#topology-and-inventory): Orion.UDT.CdpEntry and Orion.UDT.LldpEntry hold the neighbour tables UDT reads to work out which ports are uplinks to other switches rather than access ports with devices on them.
- [Operations and polling health](modules/udt.md#operations-and-polling-health): Orion.UDT.NodeCapability is the entity to watch if UDT stops being right.
- [Verbs](modules/udt.md#verbs): UDT declares three verbs in total, which is the smallest verb surface of any major module and reflects what UDT is: a reader, not a controller.
- [Worked queries](modules/udt.md#worked-queries): Every query below was validated against the 2026.2 schema with python3 tools/validate_swql.py.
- [Gotchas](modules/udt.md#gotchas): They describe the same physical thing from different modules with different ids and no navigation property between them.
- [Related pages](modules/udt.md#related-pages): device is on, IPAM says who the address belongs to.
- [Official SolarWinds documentation](modules/udt.md#official-solarwinds-documentation): documents the Orion.UDT.Port create, update and delete contract and the enumerated values for Duplex, TrunkMode, OperationalStatus and AdministrativeStatus - UDT.PortShutdown.ps1, the only published example of calling...

### [VMAN: Virtualization Manager](modules/vman.md)

Virtualization Manager is the module that lets the platform see inside a hypervisor.

- [Namespace and size](modules/vman.md#namespace-and-size): There are 90 entities under Orion.VIM., and three more namespaces carry virtualization data alongside it.
- [The hierarchy](modules/vman.md#the-hierarchy): vSphere's own object model maps onto the schema almost exactly, and the id columns make each level joinable in both directions.
- [A virtual host is also an Orion node](modules/vman.md#a-virtual-host-is-also-an-orion-node): Orion.VIM.Hosts.NodeID is the single most useful column in this module, because it is the bridge between the virtualization world and everything else the platform does.
- [Virtual machines](modules/vman.md#virtual-machines): Orion.VIM.VirtualMachines is the widest of the module's monitored objects: 76 declared properties on top of eight inherited from Orion.Virtualization.Instance and the usual System.ManagedEntity set.
- [Hosts, clusters, datacenters and vCenters](modules/vman.md#hosts-clusters-datacenters-and-vcenters): Orion.VIM.Hosts (62 properties) is the hypervisor.
- [Datastores, LUNs, NAS and virtual disks](modules/vman.md#datastores-luns-nas-and-virtual-disks): Orion.VIM.Datastores (34 properties) is where virtualization meets storage.
- [Snapshots](modules/vman.md#snapshots): Orion.VIM.Snapshots exists and is small: SnapshotID, VirtualMachineID, SnapshotIdentifier, Name, Description, DateCreated, PowerState.
- [Statistics and capacity planning](modules/vman.md#statistics-and-capacity-planning): Seven statistics entities hold the rolled-up history.
- [Alarms](modules/vman.md#alarms): Virtualization Manager surfaces the hypervisor's own alarms, which are separate from the platform's own alerting.
- [Tags](modules/vman.md#tags): Orion.VIM.Tags and Orion.VIM.TagCategories mirror vSphere tags into the schema, and Orion.VIM.Tags navigates to all six monitored object types plus Orion.CustomProperty.
- [Verbs](modules/vman.md#verbs): Virtualization Manager publishes 34 verbs.
- [Worked queries](modules/vman.md#worked-queries): Every query below has been validated against the 2026.2 schema with tools/validate_swql.py.
- [Gotchas](modules/vman.md#gotchas): The all-capitals form appears throughout older references.
- [See also](modules/vman.md#see-also): datastore joins.

### [VNQM: VoIP and Network Quality Manager](modules/vnqm.md)

VoIP and Network Quality Manager answers two different questions with two completely different mechanisms, and almost every surprise in its schema comes from not knowing which half you are looking at.

- [Namespace and how many entities](modules/vnqm.md#namespace-and-how-many-entities): VNQM contributes 140 entities, all under Orion.IpSla..
- [IP SLA operations](modules/vnqm.md#ip-sla-operations): Orion.IpSla.Operations is the centre of the synthetic half.
- [Where the numbers actually live](modules/vnqm.md#where-the-numbers-actually-live): This is the part that costs people the most time.
- [MOS, jitter and the other quality metrics](modules/vnqm.md#mos-jitter-and-the-other-quality-metrics): These are the numbers people come to this module for, so the exact spellings matter.
- [The call manager side](modules/vnqm.md#the-call-manager-side): Orion.IpSla.CCMMonitoring is one row per monitored call manager and it is the hub of the passive half.
- [Calls and call detail records](modules/vnqm.md#calls-and-call-detail-records): Four entities describe calls and they answer different questions.
- [Gateways, PRI trunks and SIP trunks](modules/vnqm.md#gateways-pri-trunks-and-sip-trunks): The polled side of gateway monitoring is a three-level hierarchy.
- [Sites, call paths and hops](modules/vnqm.md#sites-call-paths-and-hops): Orion.IpSla.Sites is VNQM's own site model, separate from the platform's group and container features: SiteID, Name, IPAddress, NodeID, RegionID, IsHub and IsAutoConfigured.
- [Verbs](modules/vnqm.md#verbs)
- [Worked queries](modules/vnqm.md#worked-queries): Every query below has been validated against the 2026.2 schema with tools/validate_swql.py.
- [Gotchas](modules/vnqm.md#gotchas): Orion.IpSla.CCMGateways is the call manager's view, keyed by GatewayID and carrying registration state.
- [What is not verified here](modules/vnqm.md#what-is-not-verified-here): The Orion.IpSla.
- [Related pages](modules/vnqm.md#related-pages): match its product name.

### [WPM: Web Performance Monitor](modules/wpm.md)

- [Nothing in the schema is called WPM](modules/wpm.md#nothing-in-the-schema-is-called-wpm): Start here, because this is where most people lose twenty minutes.
- [What the module actually does](modules/wpm.md#what-the-module-actually-does): WPM records a browser session as a script, then replays that script on a schedule from one or more machines and times every action.
- [Namespace and how many entities](modules/wpm.md#namespace-and-how-many-entities): WPM contributes 31 entities, all under Orion.SEUM..
- [The recording, and the transactions made from it](modules/wpm.md#the-recording-and-the-transactions-made-from-it): A recording is the script.
- [Steps: two entities for one idea](modules/wpm.md#steps-two-entities-for-one-idea): This is the part of the model that surprises people.
- [Requests: what the browser actually did](modules/wpm.md#requests-what-the-browser-actually-did): Orion.SEUM.TransactionStepRequests is one row per HTTP request issued while performing a step, and it is the richest entity in the module.
- [How timings roll up](modules/wpm.md#how-timings-roll-up): Three levels of measurement, three retention tiers, and a naming convention that repeats exactly.
- [Locations, which the schema calls agents](modules/wpm.md#locations-which-the-schema-calls-agents): Orion.SEUM.Agents has 31 properties and inherits System.ManagedEntity.
- [Verbs](modules/wpm.md#verbs): WPM publishes 16 verbs across five entities, which is a lot for a 31-entity module and reflects that recordings really are managed through the API.
- [Worked queries](modules/wpm.md#worked-queries): Every query below has been validated against the 2026.2 schema.
- [Gotchas](modules/wpm.md#gotchas): The namespace is Orion.SEUM., for synthetic end user monitoring.
- [What is not verified here](modules/wpm.md#what-is-not-verified-here): The Orion.SEUM.
- [Related pages](modules/wpm.md#related-pages): does not match its product name, and the other place this platform does synthetic testing.

## docs/automation/

### [Automation against SWIS](automation/README.md)

The pages in this section are task guides.

- [Pick the interface before you write anything](automation/README.md#pick-the-interface-before-you-write-anything): SWIS exposes four ways to touch data, and choosing the wrong one is the most common reason an automation ends up complicated.
- [Look the names up. Every time.](automation/README.md#look-the-names-up-every-time): Entity names, property names, verb names and verb argument order are the four things that are easiest to get plausibly wrong.
- [Write the SELECT first, and make it the scope](automation/README.md#write-the-select-first-and-make-it-the-scope): This is the single habit that separates an automation you can run on a Friday from one you cannot.
- [Bind parameters, do not concatenate](automation/README.md#bind-parameters-do-not-concatenate): Every query above uses @name placeholders.
- [Be careful in a specific way, not a general way](automation/README.md#be-careful-in-a-specific-way-not-a-general-way): "Be careful with writes" is not actionable.
- [Verb arguments are positional](automation/README.md#verb-arguments-are-positional): Names appear in the schema, in the Swagger contract and in this repository's data.
- [Permission failures usually are not bugs](automation/README.md#permission-failures-usually-are-not-bugs): Verbs declare the right they require, and the schema records it.
- [Read errors before retrying](automation/README.md#read-errors-before-retrying): that will not coerce to the declared type, or a property name that does not exist on the entity.
- [Validate your SWQL before you ship it](automation/README.md#validate-your-swql-before-you-ship-it): This repository ships a parser that resolves every dotted reference against the schema:
- [The guides](automation/README.md#the-guides): Polling has a section of its own, because five separate systems collect against the same objects through different entities: ../polling/README.md.
- [Official sources](automation/README.md#official-sources): SolarWinds publishes the SDK documentation and the sample scripts that these guides adapt:

### [Accounts, rights and account limitations](automation/accounts-and-permissions.md)

Everything you read or write through SWIS happens as some account, and that account changes what the same query returns.

- [The account model](automation/accounts-and-permissions.md#the-account-model): The platform recognises three categories of account, and the distinction is about where the identity lives rather than about what it can do.
- [Orion.Accounts](automation/accounts-and-permissions.md#orionaccounts): One entity holds every account, of every category.
- [The account verbs](automation/accounts-and-permissions.md#the-account-verbs): All ten verbs on Orion.Accounts require the admin right.
- [The rights that gate verbs](automation/accounts-and-permissions.md#the-rights-that-gate-verbs): Verbs declare the right they require, and a permission failure is far more often a missing right than a bug in the call.
- [Account limitations silently change query results](automation/accounts-and-permissions.md#account-limitations-silently-change-query-results): An account limitation restricts the set of objects an account can see.
- [Worked queries](automation/accounts-and-permissions.md#worked-queries): The provisioning inventory.
- [Gotchas](automation/accounts-and-permissions.md#gotchas): Look the verb up before you debug the call: python3 tools/schema_query.py verb <Entity> <Verb> prints the right on the requires: line.
- [See also](automation/accounts-and-permissions.md#see-also): different thing from accounts - reporting.md for why a scheduled export's account decides its contents - README.md for the automation method these pages follow - ../swis/invoke-verbs.md for how verb arguments are enco...

### [Alerts](automation/alerts.md)

Alerting is the part of the platform people most often want to drive from a script, and it is also the part with the most entities that sound like they do the same thing.

- [The entities that exist](automation/alerts.md#the-entities-that-exist): All nine entities named in this repository's brief are present in 2026.2.
- [How the current entities join](automation/alerts.md#how-the-current-entities-join): Read that top to bottom and the model is simple:
- [Listing active alerts with the object that triggered them](automation/alerts.md#listing-active-alerts-with-the-object-that-triggered-them): This is the query that goes on the wall.
- [Acknowledging an alert](automation/alerts.md#acknowledging-an-alert): Four verbs, all on Orion.AlertActive, all requiring the clearEvents right:
- [Listing alert definitions, and whether they are enabled](automation/alerts.md#listing-alert-definitions-and-whether-they-are-enabled): Enabled = FALSE is the first thing to check when the complaint is "nobody was paged":
- [Enabling and disabling an alert](automation/alerts.md#enabling-and-disabling-an-alert): There is no Enable or Disable verb.
- [What fired in a window: alert history](automation/alerts.md#what-fired-in-a-window-alert-history): Orion.AlertHistory is the only entity that survives a reset, so every "what happened overnight" question goes here.
- [Suppressing alerts](automation/alerts.md#suppressing-alerts): Suppression mutes alerting for an entity over a time window while polling continues.
- [Alert actions](automation/alerts.md#alert-actions): An action is the thing that happens when an alert fires.
- [Variables in alert messages](automation/alerts.md#variables-in-alert-messages): AlertMessage and the notification action bodies carry variables — ${N=SwisEntity;M=Caption} and the previous-generation ${NodeName} form.
- [Alert schedules](automation/alerts.md#alert-schedules): Orion.AlertSchedules has exactly two columns and no declared relationships:
- [Things that go wrong](automation/alerts.md#things-that-go-wrong): the active row.
- [What is not verified here](automation/alerts.md#what-is-not-verified-here)
- [Related pages](automation/alerts.md#related-pages)

### [Credential storage across modules](automation/credential-integration.md)

The platform has a shared credential store, and not every module uses it.

- [Two architectures, side by side](automation/credential-integration.md#two-architectures-side-by-side): The entity carries an integer pointing at Orion.Credential.ID and holds no secret of its own.
- [The reference is a convention, not a relationship](automation/credential-integration.md#the-reference-is-a-convention-not-a-relationship): 28 columns across the schema name a credential id.
- [Orion.CredentialRelation is the mechanism nobody mentions](automation/credential-integration.md#orioncredentialrelation-is-the-mechanism-nobody-mentions): The schema describes it in one sentence, and the sentence is the answer to "how do I share a credential across modules":
- [Module by module](automation/credential-integration.md#module-by-module): Orion.IpSla.AxlConnectionInfo, Orion.IpSla.CliConnectionInfo and Orion.IpSla.FtpConnectionInfo each carry NodeID and a CredentialID, and:
- [Auditing what you have](automation/credential-integration.md#auditing-what-you-have): Every credential and what claims to use it, as far as the declared graph goes:
- [What can actually be synced](automation/credential-integration.md#what-can-actually-be-synced): That last row is the one that makes central storage worth the effort.
- [Gotchas](automation/credential-integration.md#gotchas): 25 of the 28 columns have nothing behind them.
- [See also](automation/credential-integration.md#see-also): the whole Invoke risk surface - ../modules/vnqm.md, ../modules/ipam.md, ../modules/srm.md, ../modules/vman.md — the modules themselves - ../modules/ncm.md — connection profiles, NCM's own answer - ../swql/gotchas.md —...

### [Credentials](automation/credentials.md)

Discovery and polling need credentials, and the platform keeps them in one shared store so that a community string or a service account is defined once and referenced by everything that needs it.

- [Orion.Credential](automation/credentials.md#orioncredential): Five properties.
- [Orion.CredentialRelation](automation/credentials.md#orioncredentialrelation): A credential on its own does nothing.
- [Credential types](automation/credentials.md#credential-types): CredentialType is a fully qualified .NET type name.
- [The verbs](automation/credentials.md#the-verbs): Orion.Credential exposes ten verbs.
- [How credentials are referenced](automation/credentials.md#how-credentials-are-referenced): There are three distinct mechanisms, and conflating them is the usual reason a script sets a credential and polling does not change.
- [Security posture](automation/credentials.md#security-posture): Orion.Credential declares ID, Name, Description, CredentialType and CredentialOwner.
- [Worked queries](automation/credentials.md#worked-queries): The starting point for any credential audit, and safe to run as any account, since the store exposes no secret material.
- [Gotchas](automation/credentials.md#gotchas): Looking a credential up by name alone can return the wrong one.
- [Across modules](automation/credentials.md#across-modules): Not every module uses this store.
- [See also](automation/credentials.md#see-also): Credential Management page, which carries the full property key list for every shared credential type

### [Custom properties](automation/custom-properties.md)

A custom property is an extra column you add to an Orion object type: DataCentre on nodes, Owner on applications, Bitlocker_Enabled on volumes.

- [The one structural fact to hold on to](automation/custom-properties.md#the-one-structural-fact-to-hold-on-to)
- [The entities](automation/custom-properties.md#the-entities): Twenty-five entities inherit from System.CustomPropertiesEntity in 2026.2, one per object type that supports custom properties.
- [Defining a property](automation/custom-properties.md#defining-a-property): Sixteen parameters in 2026.2, the first ten required, and six of those ten documented as unused.
- [Discovering what is defined](automation/custom-properties.md#discovering-what-is-defined): Three entities describe the definitions themselves, and all three are readable through plain SWQL.
- [Setting values](automation/custom-properties.md#setting-values): A value is a CRUD update against the object's CustomProperties URI.
- [Querying and filtering on custom properties](automation/custom-properties.md#querying-and-filtering-on-custom-properties): Two spellings, and they mean the same thing.
- [Things that go wrong](automation/custom-properties.md#things-that-go-wrong): create operation at all.
- [Related pages](automation/custom-properties.md#related-pages)

### [Dependencies](automation/dependencies.md)

A dependency tells the platform that one object's availability depends on another's.

- [The entities](automation/dependencies.md#the-entities): Orion.Dependencies and Orion.DeletedAutoDependencies declare the same sixteen properties and carry the same operations: create, read, update, delete and invoke, gated on the manageNodes right for everything except read.
- [Which objects can take part](automation/dependencies.md#which-objects-can-take-part): Not every entity type can be either end of a dependency, and the two ends are gated separately.
- [How a dependency is expressed](automation/dependencies.md#how-a-dependency-is-expressed): Parent and child are identified two ways at once, and knowing which to use matters:
- [Listing what exists](automation/dependencies.md#listing-what-exists): Manually created dependencies only, which is the set a person is responsible for:
- [Dependencies that are not doing anything](automation/dependencies.md#dependencies-that-are-not-doing-anything): This is the query worth running periodically.
- [Finding what depends on a node](automation/dependencies.md#finding-what-depends-on-a-node): Because the decomposed columns exist, this is a plain filter rather than a URI comparison:
- [Objects currently suppressed by a dependency](automation/dependencies.md#objects-currently-suppressed-by-a-dependency): Status 12 is Unreachable, which means the object is not being reported as down because something it depends on already is.
- [Creating a dependency](automation/dependencies.md#creating-a-dependency): Dependencies are created through CRUD rather than through a verb.
- [Dismissing an automatic dependency](automation/dependencies.md#dismissing-an-automatic-dependency): Automatic dependencies are discovered from topology and are sometimes wrong.
- [Undoing a dismissal](automation/dependencies.md#undoing-a-dismissal): A dismissal is reversible, and the verb that reverses it lives on the other entity.
- [How automatic discovery is scoped](automation/dependencies.md#how-automatic-discovery-is-scoped): Orion.AutoDependencyRoot is the working state of the automatic discovery process, one row per root it calculates outward from:
- [Application dependencies from SAM](automation/dependencies.md#application-dependencies-from-sam): Topology is not the only source of dependencies.
- [Practical notes](automation/dependencies.md#practical-notes): A group rolls child status up into a container status.
- [See also](automation/dependencies.md#see-also)

### [Importing DISA STIGs: from cyber.mil to NCM and SCM compliance](automation/disa-stig-import.md)

A DISA Security Technical Implementation Guide is a list of requirements — check text, fix text, severity — for hardening one product.

- [What DISA actually publishes](automation/disa-stig-import.md#what-disa-actually-publishes): Every package on the downloads page resolves to one URL shape:
- [Path one: network STIGs into NCM](automation/disa-stig-import.md#path-one-network-stigs-into-ncm): The target format is the three-tier NCM policy report — report → policies → rules — whose file format and verbs ../modules/ncm-compliance-reports.md documents in full.
- [Path two: server STIGs into SCM](automation/disa-stig-import.md#path-two-server-stigs-into-scm): SolarWinds ships server STIGs as SCM compliance policies — YAML documents tagged !policy with pluginName: SCM, whose rules carry actual machine checks (!scm.registry and !scm.powershell sources under !all/!any/!none c...
- [The tool that does all of this](automation/disa-stig-import.md#the-tool-that-does-all-of-this): apps/disa-stig-conversion-tool/ implements both paths with format auto-detection — zip, *-xccdf.xml or .xsl (it silently reads the benchmark next to the stylesheet) goes to NCM; .yaml goes to SCM — as a stdlib-only CL...

### [Discovery](automation/discovery.md)

Discovery is the most intricate workflow in SWIS.

- [Two things are called discovery](automation/discovery.md#two-things-are-called-discovery): They solve different problems and share almost no API surface.
- [The entities and verbs, verified](automation/discovery.md#the-entities-and-verbs-verified): That is not an extraction gap.
- [Network Sonar discovery, end to end](automation/discovery.md#network-sonar-discovery-end-to-end): Five phases:
- [List Resources on an existing node](automation/discovery.md#list-resources-on-an-existing-node): This is the flow behind "List Resources" in the node management UI: ask a node that is already monitored what else it can report, then turn those on.
- [Lite interface discovery](automation/discovery.md#lite-interface-discovery): The simplest of the three flows, and synchronous.
- [Things that go wrong](automation/discovery.md#things-that-go-wrong): by StartDiscovery.
- [What is not verified here](automation/discovery.md#what-is-not-verified-here)
- [Related pages](automation/discovery.md#related-pages)

### [Events and auditing](automation/events-and-auditing.md)

Two different questions look the same at three in the morning:

- [The entities](automation/events-and-auditing.md#the-entities): Eight declared properties, plus three inherited from Orion.MixedObjectType that do most of the work:
- [Event or audit event: how to decide](automation/events-and-auditing.md#event-or-audit-event-how-to-decide): The rule of thumb: if a human could have done it, look in auditing first.
- [Joining events to their type and to the node](automation/events-and-auditing.md#joining-events-to-their-type-and-to-the-node): Two ways to get the type name, both valid:
- [Filtering by time window, correctly](automation/events-and-auditing.md#filtering-by-time-window-correctly): This is where these two entities differ and where the errors are silent.
- [Investigation 1: what happened to this node in the last 24 hours](automation/events-and-auditing.md#investigation-1-what-happened-to-this-node-in-the-last-24-hours): Start with everything, typed and ordered.
- [Investigation 2: which nodes went down overnight](automation/events-and-auditing.md#investigation-2-which-nodes-went-down-overnight): There is no "node down" boolean to filter on.
- [Investigation 3: who unmanaged this node](automation/events-and-auditing.md#investigation-3-who-unmanaged-this-node): This is the archetypal audit question, and it has three levels of precision.
- [Acknowledging events](automation/events-and-auditing.md#acknowledging-events): One argument, and it is an array, so this is the PowerShell case that needs the leading-comma idiom:
- [Things that go wrong](automation/events-and-auditing.md#things-that-go-wrong): the offset label is wrong, and the window silently shifts by your UTC offset.
- [What is not verified here](automation/events-and-auditing.md#what-is-not-verified-here)
- [Related pages](automation/events-and-auditing.md#related-pages)

### [High availability](automation/high-availability.md)

High availability in Orion is not database clustering and it is not a load balancer.

- [Namespaces and how many entities](automation/high-availability.md#namespaces-and-how-many-entities): High availability contributes 9 entities, all under Orion.HA..
- [The pool](automation/high-availability.md#the-pool): Orion.HA.Pools declares 19 properties and they fall into four groups.
- [Pool members](automation/high-availability.md#pool-members): Orion.HA.PoolMembers is one row per server.
- [Resources and facilities](automation/high-availability.md#resources-and-facilities): These two entities are the mechanism, and the distinction between them is the thing worth understanding.
- [Reachability and the virtual address](automation/high-availability.md#reachability-and-the-virtual-address): Orion.HA.ReachabilityInfo is described in the schema as an extension of Orion.ReachabilityInfo, and it exists to answer "what names and addresses can I use to reach each Orion server, and which of them are virtual".
- [What a failover looks like from the API](automation/high-availability.md#what-a-failover-looks-like-from-the-api): Nothing about a failover changes the pool's membership or its configuration.
- [The verbs](automation/high-availability.md#the-verbs): Thirteen verbs, all on Orion.HA.Pools, all requiring admin, and all returning SolarWinds.Orion.HighAvailability.Common.Model.OperationResult.
- [What is safe to automate, and what is not](automation/high-availability.md#what-is-safe-to-automate-and-what-is-not): The verbs divide cleanly into three groups, and treating them as one group is how HA automation goes wrong.
- [Load balancing](automation/high-availability.md#load-balancing): ElbEnabled on the pool, plus the ElbEnable and ElbDisable verbs, control Engine Load Balancing for that pool.
- [Worked queries](automation/high-availability.md#worked-queries): Every query below was validated against the 2026.2 schema with python3 tools/validate_swql.py.
- [Gotchas](automation/high-availability.md#gotchas): There is no CRUD path into pool membership at all.
- [Related pages](automation/high-availability.md#related-pages): main-versus-additional distinction, and where HA sits in the deployment picture.
- [Official SolarWinds documentation](automation/high-availability.md#official-solarwinds-documentation): the only published worked example of the pool verbs, and the source for the properties argument shape, the read-modify-write requirement on EditPool, and the statement that pool members cannot be updated - Polling Eng...

### [Maintenance mode: unmanaging and remanaging](automation/maintenance-mode.md)

"Put these nodes in maintenance for the change window" is the most common thing anyone asks an Orion automation to do.

- [What unmanaging does, and what it costs](automation/maintenance-mode.md#what-unmanaging-does-and-what-it-costs): An unmanaged object is not polled.
- [The verb, exactly as the schema declares it](automation/maintenance-mode.md#the-verb-exactly-as-the-schema-declares-it): Remanage is the other half and takes one argument:
- [Recipe: a fixed window for planned work](automation/maintenance-mode.md#recipe-a-fixed-window-for-planned-work): The change starts at 22:00 local and ends at 02:00 the next morning.
- [Recipe: unmanage now, for N hours](automation/maintenance-mode.md#recipe-unmanage-now-for-n-hours): The common interactive case.
- [Recipe: remanage early](automation/maintenance-mode.md#recipe-remanage-early): The change finished ahead of schedule.
- [Recipe: bulk unmanage driven by a query](automation/maintenance-mode.md#recipe-bulk-unmanage-driven-by-a-query): There is no bulk unmanage verb.
- [Finding what is currently unmanaged](automation/maintenance-mode.md#finding-what-is-currently-unmanaged): The three properties come from System.ManagedEntity and are inherited by every managed object type, so the same shape works everywhere:
- [Which entity types can be unmanaged](automation/maintenance-mode.md#which-entity-types-can-be-unmanaged): Only some.
- [Things that go wrong](automation/maintenance-mode.md#things-that-go-wrong): release this either errors or silently targets nothing.
- [Related pages](automation/maintenance-mode.md#related-pages)

### [Node management](automation/node-management.md)

A node is the root object of the Orion data model.

- [Adding a node](automation/node-management.md#adding-a-node): Creating a node is a CRUD create against Orion.Nodes, followed by creating one Orion.Pollers row per thing you want polled.
- [Finding nodes](automation/node-management.md#finding-nodes): The inventory query, which is the starting point for most of the rest of this page:
- [Updating node properties](automation/node-management.md#updating-node-properties): An update is a CRUD POST to the node's URI carrying only the properties you are changing.
- [Changing polling method and SNMP version](automation/node-management.md#changing-polling-method-and-snmp-version): ObjectSubType decides how the node is polled.
- [Reassigning a node to a different polling engine](automation/node-management.md#reassigning-a-node-to-a-different-polling-engine): Nodes are statically assigned to polling engines, and everything related to a node, including its interfaces, applications and configs, runs from that engine.
- [Forcing a poll or a rediscovery](automation/node-management.md#forcing-a-poll-or-a-rediscovery): Three verbs, all taking a single netObjectId and all requiring manageNodes:
- [Deleting a node](automation/node-management.md#deleting-a-node): Deletion is a CRUD DELETE against the node's URI.
- [The verbs on Orion.Nodes, in full](automation/node-management.md#the-verbs-on-orionnodes-in-full): Seventeen in 2026.2.
- [Related pages](automation/node-management.md#related-pages)

### [The report definition format](automation/report-definitions.md)

A report exports from Reports > Manage Reports > Export/Import as one XML document, and the same document is the value of Orion.Report.Definition.

- [The skeleton](automation/report-definitions.md#the-skeleton): Fifteen top-level elements, all present in all four samples:
- [The three-part indirection](automation/report-definitions.md#the-three-part-indirection): This is the part to understand first, because everything else hangs off it.
- [DataSources — three ways to choose rows](automation/report-definitions.md#datasources-three-ways-to-choose-rows): Type decides which of the other elements matter:
- [Configs — what a cell renders](automation/report-definitions.md#configs-what-a-cell-renders): Configs holds ConfigurationData elements, discriminated by i:type:
- [TableConfiguration — columns](automation/report-definitions.md#tableconfiguration-columns): Each TableColumn binds a field to a display treatment:
- [Header, footer, timeframes](automation/report-definitions.md#header-footer-timeframes): Header/Title and Header/SubTitle are what Orion.Report.Title and Orion.Report.SubTitle hold, and what the title and subtitle arguments of CreateReport/UpdateReport correspond to — neither has a top-level element of it...
- [Moving a report between servers](automation/report-definitions.md#moving-a-report-between-servers): There is no ExportReport/ImportReport pair.
- [Before you share one](automation/report-definitions.md#before-you-share-one): A report definition carries more of your installation than you might expect.
- [See also](automation/report-definitions.md#see-also): the same GUID-indirection pattern and a JSON body - ../polling/api-pollers.md — the other exportable XML artefact, which does have matched import and export verbs - ../webui/custom-query-widget.md — the console widget...

### [Reports and scheduled exports](automation/reporting.md)

"Reporting" against SWIS means two related but separate things, and knowing which one you are doing saves a lot of wasted effort.

- [The reporting entities](automation/reporting.md#the-reporting-entities): Note the access control on Orion.Report: it declares read, update and invoke but no create and no delete operation, and the four verbs it exposes carry no right of their own, so entity-level invoke governs them and th...
- [How a SWQL query becomes a report](automation/reporting.md#how-a-swql-query-becomes-a-report): For a platform report, the path is through the console: create a report, add a custom table resource, choose the advanced SWQL data source, paste the query.
- [Paging with WITH ROWS and WITH TOTALROWS](automation/reporting.md#paging-with-with-rows-and-with-totalrows): SWQL has no OFFSET/FETCH.
- [Exporting from PowerShell](automation/reporting.md#exporting-from-powershell): Get-SwisData returns objects, so Export-Csv is a one-liner:
- [Exporting from Python](automation/reporting.md#exporting-from-python): The REST envelope carries totalRows, so paging is explicit and readable:
- [A complete scheduled export](automation/reporting.md#a-complete-scheduled-export): This is the shape to copy: parameters, no hard-coded secrets, paging, a real failure path, and an atomic write so a consumer never reads a half-finished file.
- [Practical constraints](automation/reporting.md#practical-constraints): Statistics, events and alert history are the largest tables on the system, and a query over "all time" is a scan of the biggest thing in the database.
- [Worked queries](automation/reporting.md#worked-queries): These are shaped for exports: named columns, bounded, and readable by whoever receives the output rather than only by the person who wrote them.
- [Gotchas](automation/reporting.md#gotchas): Account limitations filter silently.
- [See also](automation/reporting.md#see-also): decide what any export contains - alerts.md for alert history and its EventType values - custom-properties.md for grouping output by your own metadata - ../swql/performance.md for bounding, paging and aggregation - .....

### [Scheduled tasks and maintenance plans](automation/scheduling.md)

Two related capabilities let the platform do something later without anyone driving it: scheduled tasks, which run an action on a recurring frequency, and maintenance plans, which open a maintenance window at a planne...

- [The entities](automation/scheduling.md#the-entities): Only Orion.Frequencies declares verbs, and they exist for a reason covered below.
- [What is scheduled right now](automation/scheduling.md#what-is-scheduled-right-now): The first query to run, and the one that answers "is something already doing this":
- [Tasks that are failing or disabled](automation/scheduling.md#tasks-that-are-failing-or-disabled): A scheduled task that is switched off looks identical to one that never existed, from the point of view of the work not getting done:
- [What a task acts on](automation/scheduling.md#what-a-task-acts-on): Assignments name their target either as a specific URI or as an expression that resolves to a set at run time.
- [The recurrence](automation/scheduling.md#the-recurrence): Orion.Frequencies carries the actual schedule, including a cron expression, which is the readable form of "when does this run":
- [Maintenance plans](automation/scheduling.md#maintenance-plans): A maintenance plan is a scheduled unmanage.
- [Before you automate a schedule of your own](automation/scheduling.md#before-you-automate-a-schedule-of-your-own): Unmanaging on a schedule from a script, while a maintenance plan covers the same objects, produces overlapping windows.
- [See also](automation/scheduling.md#see-also)

## docs/polling/

### [Polling](polling/README.md)

Creating an object does not monitor it.

- [The five systems](polling/README.md#the-five-systems): Read the last column before planning any automation.
- [Telling them apart](polling/README.md#telling-them-apart): The fastest way to identify what you are looking at is the shape of its key:
- [What a single object is actually collecting](polling/README.md#what-a-single-object-is-actually-collecting): There is no one query for this, and that is the point of the map.
- [The one gotcha that spans all five](polling/README.md#the-one-gotcha-that-spans-all-five): Every system distinguishes an assignment that does not exist from one that exists and is switched off, and the second passes every "does this object have pollers" check while collecting nothing.
- [The pages](polling/README.md#the-pages)
- [Related pages](polling/README.md#related-pages): pick the interface, look the names up, write the SELECT first - ../automation/node-management.md for creating the node a poller attaches to - ../automation/discovery.md for network sonar and list resources - ../automa...

### [A worked API Poller: the UniFi Network Integration API](polling/api-poller-unifi-network.md)

api-pollers.md describes the API Poller subsystem from the schema.

- [Why the Integration API and not the legacy one](polling/api-poller-unifi-network.md#why-the-integration-api-and-not-the-legacy-one): UniFi has two HTTP interfaces and only one of them is usable from an API Poller.
- [The credential](polling/api-poller-unifi-network.md#the-credential): The key is created in the UniFi console under Settings > Control Plane > Integrations.
- [The base path depends on how Network is deployed](polling/api-poller-unifi-network.md#the-base-path-depends-on-how-network-is-deployed): On a UniFi OS console (UDM, UCG, UNVR, Cloud Key Gen2 and later) the Network application sits behind UniFi OS's reverse proxy, and every Integration API URL is prefixed /proxy/network:
- [The endpoints](polling/api-poller-unifi-network.md#the-endpoints): Four were exercised, all GET:
- [Chaining requests with variables](polling/api-poller-unifi-network.md#chaining-requests-with-variables): The builder's value picker, reached from "Configure a value to monitor" on any field in a test response, offers two things to do with that field, and the distinction is the whole design:
- [What the variable mechanism cannot do](polling/api-poller-unifi-network.md#what-the-variable-mechanism-cannot-do): These are the rules that decide whether a given monitoring idea is buildable as an API Poller at all, and each one is a thing that was tried.
- [Reading what the poller collected](polling/api-poller-unifi-network.md#reading-what-the-poller-collected): The poller's own rows, once it exists:
- [Exporting it](polling/api-poller-unifi-network.md#exporting-it): Once the poller works, export it and keep the file, because the export is the only artefact that survives a rebuild:
- [What is unverified here](polling/api-poller-unifi-network.md#what-is-unverified-here): Collected, because this page asserts a lot from one installation:
- [Why build a multi-metric poller against a public API at all](polling/api-poller-unifi-network.md#why-build-a-multi-metric-poller-against-a-public-api-at-all): The same three-request shape works anywhere a vendor or a public service publishes JSON and an identifier has to be discovered before it can be used, and it is often the cheaper answer than an intermediary.
- [See also](polling/api-poller-unifi-network.md#see-also)

### [Reading a vendor-shipped API Poller template](polling/api-poller-vendor-templates.md)

api-pollers.md documents the .apipoller.template format from a single export.

- [Three Type values, from real exports](polling/api-poller-vendor-templates.md#three-type-values-from-real-exports): Orion.APIPoller.ValueToMonitor.Type is a System.String and the published schema records nothing about what it accepts, which is why api-pollers.md marks it unverified.
- [Key is in the file and not in the schema](polling/api-poller-vendor-templates.md#key-is-in-the-file-and-not-in-the-schema): The Microsoft 365 template writes a <Key> element on every ValueToMonitor, holding the last path segment: value for $.['value'], storageUsedInBytes for $.['value'].[0].['storageUsedInBytes'].
- [Vendor templates leave the thresholds blank on purpose](polling/api-poller-vendor-templates.md#vendor-templates-leave-the-thresholds-blank-on-purpose): Every ValueToMonitor in all three templates carries:
- [Parameters in the URL are not request variables](polling/api-poller-vendor-templates.md#parameters-in-the-url-are-not-request-variables): All three templates put ${NAME} placeholders in their URLs:
- [Where these three disagree with the documented format](polling/api-poller-vendor-templates.md#where-these-three-disagree-with-the-documented-format): Reading real vendor output corrects two things the single-export derivation got slightly wrong.
- [Why these files are not build-validated](polling/api-poller-vendor-templates.md#why-these-files-are-not-build-validated): tools/check_api_poller_templates.py globs scripts/api-pollers/*.apipoller.template, non-recursively, so the copies in vendor-examples/ are outside it by construction.
- [See also](polling/api-poller-vendor-templates.md#see-also)

### [API pollers](polling/api-pollers.md)

An API poller collects metrics by calling an HTTP endpoint and reading values out of the response, rather than by asking a device over SNMP or WMI.

- [The model](polling/api-pollers.md#the-model): Ten entities, and the shape is a chain rather than a table:
- [The poller](polling/api-pollers.md#the-poller): RelatedEntityId and RelatedEntityType are where a NetObject would be on any other poller.
- [The request](polling/api-pollers.md#the-request): One poller can make several requests, and RequestDetailsOrder is what makes that useful:
- [The metric](polling/api-pollers.md#the-metric): Orion.APIPoller.ValueToMonitor is where a response becomes a number:
- [The verbs](polling/api-pollers.md#the-verbs): Six, split across the two entities that declare any.
- [The template library](polling/api-pollers.md#the-template-library): IsCustom separates what SolarWinds shipped from what someone here built, which is the first thing to know before deleting anything.
- [The .apipoller.template file format](polling/api-pollers.md#the-apipollertemplate-file-format): The console exports a template as a single-line XML document with the extension .apipoller.template.
- [Practical notes](polling/api-pollers.md#practical-notes): Building a poller by writing Orion.APIPoller.ApiPoller, then its RequestDetails, then the headers, then the values to monitor is four levels of rows that have to be consistent, and it needs admin.
- [See also](polling/api-pollers.md#see-also): first-hand against the UniFi Network Integration API: the credential, a three-request variable chain, and what that chaining cannot express - api-poller-vendor-templates.md for the Type values, blank thresholds and as...

### [Device Studio pollers](polling/device-studio.md)

Device Studio is the console feature for building a vendor-specific poller without writing an OID by hand.

- [The three entities](polling/device-studio.md#the-three-entities): They form a straight chain.
- [The technologies](polling/device-studio.md#the-technologies): Three columns, and Enabled is the one worth noticing: a technology that is switched off takes its pollers with it, so a poller can be Enabled = TRUE and collecting nothing because the technology above it is not.
- [The poller definitions](polling/device-studio.md#the-poller-definitions): Vendor and Tags are how the console groups these, and Author is the closest thing to a record of who built one — worth selecting before deleting anything in the console, since the API cannot.
- [The assignments](polling/device-studio.md#the-assignments): NetObjectType and NetObjectID are the same two columns Orion.Pollers uses, holding the same values — N and a node id, I and an interface id.
- [TechnologyID is a GUID here and a string elsewhere](polling/device-studio.md#technologyid-is-a-guid-here-and-a-string-elsewhere): Orion.DeviceStudio.Pollers carries two ids that look like they point into the neighbouring technology polling system, and only one of them does:
- [Gotchas](polling/device-studio.md#gotchas): All three entities declare no operations, so a Device Studio poller cannot be created, assigned, enabled or deleted through SWIS.
- [Related pages](polling/device-studio.md#related-pages): TechnologyPollingID joins to - standard-pollers.md for the Orion.Pollers system these share NetObjectType and NetObjectID with - ../reference/netobject-types.md for the prefixes - ../swql/joins-and-navigation.md for n...

### [How node status is calculated](polling/node-status-calculation.md)

A node's status is not a reading.

- [The three inputs](polling/node-status-calculation.md#the-three-inputs): The default.
- [What the switch changes elsewhere](polling/node-status-calculation.md#what-the-switch-changes-elsewhere): Enhanced calculation is not confined to the node's own status field.
- [The two root-cause variables](polling/node-status-calculation.md#the-two-root-cause-variables): Because a node can now be Critical for reasons that are nowhere in its own row, SolarWinds added two alert variables that render the reason:
- [Reading the root cause structurally](polling/node-status-calculation.md#reading-the-root-cause-structurally): The variables render a string.
- [Which contributors are switched on](polling/node-status-calculation.md#which-contributors-are-switched-on): The contributor list is per-installation and depends on which modules are installed:
- [Status rollup mode](polling/node-status-calculation.md#status-rollup-mode): Rollup mode decides how the inputs combine.
- [Classic calculation, and what child status means there](polling/node-status-calculation.md#classic-calculation-and-what-child-status-means-there): Under classic calculation the node's status is ICMP alone and the children are shown as a sub-icon rather than folded in.
- [Group and map rollup is a different setting again](polling/node-status-calculation.md#group-and-map-rollup-is-a-different-setting-again): Do not confuse the node rollup mode with the one that governs how a collection displays — groups, maps and tree widgets:
- [Classifying a status without hard-coding integers](polling/node-status-calculation.md#classifying-a-status-without-hard-coding-integers): 2026.2 added Orion.Web.LegacyModules.RollupStatusInfo, and unlike Orion.StatusInfo its properties carry summary text.
- [Excluding something from the calculation](polling/node-status-calculation.md#excluding-something-from-the-calculation): SolarWinds states this plainly: there is no per-object opt-out.
- [What this means for a query you already have](polling/node-status-calculation.md#what-this-means-for-a-query-you-already-have): If you maintain reports or alerts written before enhanced calculation:
- [See also](polling/node-status-calculation.md#see-also): the join that turns them into names - ../webui/variables.md — the ${N=…;M=…} form the root-cause macros use - ../automation/alerts.md — building alerts on status - standard-pollers.md — the pollers whose failure drive...

### [Standard pollers](polling/standard-pollers.md)

This is the concept that catches everyone who automates node creation, and it catches them silently.

- [Orion.Pollers is an assignment table, not a poller](polling/standard-pollers.md#orionpollers-is-an-assignment-table-not-a-poller): The entity is six properties wide and that is the whole of it:
- [The poller type string](polling/standard-pollers.md#the-poller-type-string): The convention is <NetObjectType>.<Category>.<Method>.<Variant>:
- [Seeing what an object has](polling/standard-pollers.md#seeing-what-an-object-has): Everything a node is having collected from it, in one query:
- [Adding a poller](polling/standard-pollers.md#adding-a-poller): A poller assignment is a plain CRUD create.
- [Removing and disabling a poller](polling/standard-pollers.md#removing-and-disabling-a-poller): Two different operations with two different consequences.
- [Letting the platform choose the pollers](polling/standard-pollers.md#letting-the-platform-choose-the-pollers): Hand-picking type strings is right when you know the device and are creating a hundred of the same thing.
- [Polling parameters](polling/standard-pollers.md#polling-parameters): Assigning a poller says what is collected.
- [Deciding where the load should go](polling/standard-pollers.md#deciding-where-the-load-should-go): Every poller assignment is work for the engine that owns the object.
- [Worked queries](polling/standard-pollers.md#worked-queries): Every query below was validated against the 2026.2 schema with python3 tools/validate_swql.py.
- [Gotchas](polling/standard-pollers.md#gotchas): A node, an interface or a volume created through CRUD collects nothing until Orion.Pollers rows exist for it.
- [Related pages](polling/standard-pollers.md#related-pages): collect become a node status, and why IsPollingError can turn a pinging node Critical.
- [Official SolarWinds documentation](polling/standard-pollers.md#official-solarwinds-documentation): 124 poller type strings with their OIDs and WMI queries - How To Assign Specific Poller To A Node - How To Set Polling Parameters On A Node - How To Distribute Load Between Pollers - How To Specify Interfaces, Volumes...

### [Technology polling](polling/technology-polling.md)

Technology polling is the newest of the five systems and the least visible.

- [The four entities](polling/technology-polling.md#the-four-entities): The first three are a hosting chain: Orion.Technology navigates down through TechnologyPollings, Orion.TechnologyPolling navigates down through Assignments and back up through Technology, and the assignment navigates...
- [What technologies exist](polling/technology-polling.md#what-technologies-exist): Two columns and both are worth explaining.
- [What it is assigned to](polling/technology-polling.md#what-it-is-assigned-to): InstanceID is the id of the object within whatever TargetEntity names, so it is a node id when TargetEntity is Orion.Nodes and a volume id when it is Orion.Volumes.
- [The four verbs](polling/technology-polling.md#the-four-verbs): All four require admin, all four take technologyPollingID as a string first, and all four return an array.
- [The declarative templates](polling/technology-polling.md#the-declarative-templates): Orion.Declarative.PollerTemplates is the template library the declarative polling engine works from:
- [Gotchas](polling/technology-polling.md#gotchas): Orion.Technology.TechnologyID and Orion.TechnologyPolling.TechnologyID are System.String; Orion.DeviceStudio.Technologies.TechnologyID and Orion.DeviceStudio.Pollers.TechnologyID are System.Guid.
- [Related pages](polling/technology-polling.md#related-pages): far more thoroughly by the schema - ../automation/credentials.md for the credential store credentialId points at - ../swis/invoke-verbs.md for the Invoke contract and array arguments - ../swis/metadata-introspection.m...

### [Universal Device Pollers](polling/universal-device-pollers.md)

A universal device poller, or UnDP, is an SNMP OID you defined yourself.

- [Worked queries](polling/universal-device-pollers.md#worked-queries): a.CustomPoller navigates to Orion.NPM.NodeCustomPollers, which declares no properties of its own and inherits every one of them from Orion.NPM.CustomPollers, so UniqueName and OID resolve through it.
- [Gotchas](polling/universal-device-pollers.md#gotchas): It is Orion.NPM.CustomPollerAssignmentOnNode or ...OnInterface, keyed on a GUID CustomPollerID, and its definition is created in a Windows application rather than through the API.
- [Related pages](polling/universal-device-pollers.md#related-pages): often confused with - ../modules/npm.md for universal device pollers in their module context - ../swis/crud.md for the assignment create and delete mechanics - ../reference/netobject-types.md for the UNDPN and UNDPI p...
- [Official SolarWinds documentation](polling/universal-device-pollers.md#official-solarwinds-documentation)

## docs/webui/

### [The web console](webui/README.md)

Most of this repository is about SWIS: the API, the schema, and automating against them.

- [A caveat that applies to the whole section](webui/README.md#a-caveat-that-applies-to-the-whole-section): Everywhere else in this repository, a claim is checked against the extracted contract before it is written down, and make check fails if it drifts.
- [The pages](webui/README.md#the-pages): custom-query-widget.md and modern-dashboards.md cover two separate widget systems, not an old and a new version of the same one: a Modern Dashboard widget cannot be placed on a classic dashboard, in either direction —...
- [Where these come from](webui/README.md#where-these-come-from): Community material, chiefly THWACK, which is where the conventions on these pages were worked out and written down by the people who found them.
- [See also](webui/README.md#see-also): prefixes that appear in console URLs - ../automation/accounts-and-permissions.md for why two users can see different rows in the same widget

### [The Custom Query widget](webui/custom-query-widget.md)

The Custom Query widget renders a SWQL query as a table on any view.

- [The naming convention](webui/custom-query-widget.md#the-naming-convention): A column aliased [_LinkFor_X] is not displayed.
- [Where the link value comes from](webui/custom-query-widget.md#where-the-link-value-comes-from): DetailsUrl is a System.String declared on 254 entities, and on most of them it is exactly the value this convention wants.
- [Where the icon value comes from](webui/custom-query-widget.md#where-the-icon-value-comes-from): _IconFor_ wants an image path.
- [A worked widget](webui/custom-query-widget.md#a-worked-widget): This is the community's canonical example, and it is worth reading as a whole because it applies six directives to five visible columns.
- [Practical notes](webui/custom-query-widget.md#practical-notes): The queries on this page are validated against the extracted schema like every other query in this repository.
- [See also](webui/custom-query-widget.md#see-also): prefixes the console URLs use - ../swql/functions.md for ToString() and string concatenation - ../swql/performance.md for what a widget query costs on every page load - ../modules/sam.md for the SAM entities in the wo...

### [Writing a Modern Dashboard file](webui/modern-dashboard-authoring.md)

modern-dashboards.md is the format.

- [The five rules that decide whether a file works](webui/modern-dashboard-authoring.md#the-five-rules-that-decide-whether-a-file-works): Everything else is detail.
- [Build it query-first](webui/modern-dashboard-authoring.md#build-it-query-first): The presentation is the easy half.
- [Building a widget from the console](webui/modern-dashboard-authoring.md#building-a-widget-from-the-console): Everything above describes the JSON.
- [Reusing another dashboard's widget from the console](webui/modern-dashboard-authoring.md#reusing-another-dashboards-widget-from-the-console): The widget picker's "finish configuring" step (step 1 above) carries a Source field that defaults to the current dashboard but can be set to "any dashboard" — SolarWinds Lab #93 (34:47-35:37) uses it to browse a colle...
- [Adding a dashboard to console navigation](webui/modern-dashboard-authoring.md#adding-a-dashboard-to-console-navigation): A Modern Dashboard is reachable at /apps/platform/dashboard/{DashboardID} (the same URL the filter grammar below extends), but nothing places it in the console's own menu automatically.
- [Columns exist to feed formatters](webui/modern-dashboard-authoring.md#columns-exist-to-feed-formatters): A table column binds data fields to a rendering component, so the query needs a column for each input the formatter takes — not just the visible value.
- [The self-referencing link pattern](webui/modern-dashboard-authoring.md#the-self-referencing-link-pattern): Two of the three authors independently use the same technique for one dashboard to link to another, and it is the most quietly clever thing in these files.
- [Duplicating a dashboard onto the same server](webui/modern-dashboard-authoring.md#duplicating-a-dashboard-onto-the-same-server): Import creates whatever the file says, so re-importing an unmodified export next to its original offers the server a dashboard with the same name and the same unique_keys it already has — the duplicate-key situation w...
- [The ?filters= grammar](webui/modern-dashboard-authoring.md#the-filters-grammar): Appending a filter to a dashboard URL is how these dashboards drill down.
- [KPI tiles link through the interaction handler](webui/modern-dashboard-authoring.md#kpi-tiles-link-through-the-interaction-handler): A KPI widget has no per-tile link property.
- [A complete minimal file](webui/modern-dashboard-authoring.md#a-complete-minimal-file): This is a whole, importable dashboard: one KPI tile and one table, both against stock entities so it works on any installation without custom properties.
- [Asking an AI to generate one](webui/modern-dashboard-authoring.md#asking-an-ai-to-generate-one): The format is regular enough that a language model can emit a whole valid file, provided the prompt pins the parts it cannot infer.
- [Gotchas](webui/modern-dashboard-authoring.md#gotchas): One author's file carries collisions across 27 widgets.
- [See also](webui/modern-dashboard-authoring.md#see-also): custom properties a dashboard can filter on - custom-query-widget.md — the classic-console equivalent, with its own _LinkFor_ convention - ../swql/README.md and ../swql/gotchas.md — the query language every widget is...

### [Modern Dashboard files](webui/modern-dashboards.md)

A Modern Dashboard — the console calls the feature Dashboards, under /apps/platform/dashboard/ — exports as a single JSON file.

- [The envelope](webui/modern-dashboards.md#the-envelope): Four keys, and the split between the last three is the thing to understand first:
- [dashboards[] — the page and its layout](webui/modern-dashboards.md#dashboards-the-page-and-its-layout): One author's export carries eight further dashboard-level keys, all empty:
- [widgets[] — the definitions](webui/modern-dashboards.md#widgets-the-definitions): Every widget definition has the same outer shape regardless of type:
- [The data source, and the duplication that will catch you](webui/modern-dashboards.md#the-data-source-and-the-duplication-that-will-catch-you): Every widget carries its query under providers.dataSource.properties:
- [Table configuration](webui/modern-dashboards.md#table-configuration): sortBy refers to a column id, not a data field.
- [KPI configuration](webui/modern-dashboards.md#kpi-configuration): A KPI widget is a container of tiles.
- [Proportional (donut) configuration](webui/modern-dashboards.md#proportional-donut-configuration): The five *Field properties are the whole binding: each names a column of the query.
- [unique_key collisions, and the reuse that is fine](webui/modern-dashboards.md#unique_key-collisions-and-the-reuse-that-is-fine): unique_key is the only thing joining a placement to a definition, and nothing enforces that it is unique.
- [Exporting and importing](webui/modern-dashboards.md#exporting-and-importing): The console's export button is one route; Orion.Dashboards.Instances is the other.
- [What this repository verified](webui/modern-dashboards.md#what-this-repository-verified): Nine exports from three independent authors, parsed and checked against the extracted 2026.2 schema:
- [Modern Dashboard widgets do not work on classic dashboards](webui/modern-dashboards.md#modern-dashboard-widgets-do-not-work-on-classic-dashboards): Asked directly in SolarWinds Lab #93 (39:53-39:57), the presenter confirms the boundary runs one way only: a Modern Dashboard widget cannot be placed on a classic console dashboard.
- [See also](webui/modern-dashboards.md#see-also): grammar, and the contract for asking an AI to generate a whole file - ../automation/custom-properties.md — the custom properties these dashboards filter on - variables.md — the other ${...} system, which is unrelated...

### [The change template language](webui/ncm-change-template-language.md)

The scripting language inside an NCM config change template is small, specific to NCM, and documented in fragments across SolarWinds' product guide and a handful of THWACK posts.

- [What language is this?](webui/ncm-change-template-language.md#what-language-is-this): It reads like something you have seen before, and that is not an accident, but it is not any existing language.
- [Two kinds of variable, and they are not interchangeable](webui/ncm-change-template-language.md#two-kinds-of-variable-and-they-are-not-interchangeable): This is the first thing to get straight, because the two look similar and behave nothing alike.
- [Declaring and assigning](webui/ncm-change-template-language.md#declaring-and-assigning): string is the type.
- [Operators](webui/ncm-change-template-language.md#operators): Use any of these in a parenthesised condition:
- [String functions](webui/ncm-change-template-language.md#string-functions): GetOctet and SetOctet exist because manipulating addresses by hand with SubString and IndexOf is where ACL templates go wrong.
- [Control flow](webui/ncm-change-template-language.md#control-flow): Whether a chained else if works is where two SolarWinds sources read differently, so treat it as unverified.
- [CLI blocks](webui/ncm-change-template-language.md#cli-blocks): A CLI { ...
- [Custom properties](webui/ncm-change-template-language.md#custom-properties): Custom properties are attached to nodes, so a template reads them through the node parameter, by name, with no declaration:
- [A worked template](webui/ncm-change-template-language.md#a-worked-template): Putting the pieces together.
- [Gotchas](webui/ncm-change-template-language.md#gotchas): Two SolarWinds sources read differently and no example uses a chain.
- [See also](webui/ncm-change-template-language.md#see-also): managing them through Cirrus.ConfigSnippets - ../modules/ncm.md — the NCM module and Cirrus.Nodes.ParseMacros - ../automation/custom-properties.md — defining the properties a template reads - README.md — the rest of t...

### [NCM config change templates](webui/ncm-change-templates.md)

A config change template — a CCT, and Cirrus.ConfigSnippets in the API — is a small script that the NCM console turns into a form.

- [Cirrus, NCM, and which name appears where](webui/ncm-change-templates.md#cirrus-ncm-and-which-name-appears-where): Network Configuration Manager was called Cirrus, and both names survive in the schema as two separate namespaces.
- [Anatomy](webui/ncm-change-templates.md#anatomy): A template has three parts, in order: an optional comment block, a directive block, and the script itself.
- [The directives](webui/ncm-change-templates.md#the-directives): .PARAMETER_DISPLAY_TYPE is the one worth dwelling on.
- [The signature decides what the user sees](webui/ncm-change-templates.md#the-signature-decides-what-the-user-sees): Four rules govern this line, and between them they explain most templates that "do not work":
- [The parameter types are SWIS entities](webui/ncm-change-templates.md#the-parameter-types-are-swis-entities): This is the part that makes templates worth writing, and it is barely mentioned in SolarWinds' material: NCM.Nodes, NCM.Interfaces and NCM.VLANs in a template signature are the same entities the API exposes.
- [Running one, and the preview that makes it safe](webui/ncm-change-templates.md#running-one-and-the-preview-that-makes-it-safe): The console runs a template through a four-step wizard, reached from Configs → Config Change Templates, selecting a template and clicking Define Variables & Run:
- [Sharing](webui/ncm-change-templates.md#sharing): Templates are shareable from inside the product, which is unusual enough to be worth naming.
- [Managing templates through the API](webui/ncm-change-templates.md#managing-templates-through-the-api): Templates are Cirrus.ConfigSnippets rows.
- [What this repository can and cannot check](webui/ncm-change-templates.md#what-this-repository-can-and-cannot-check): Every entity, property, navigation and verb named on this page is checked against the 2026.2 schema, and the SWQL queries are validated like any other query here.
- [See also](webui/ncm-change-templates.md#see-also): functions, macros, control flow and CLI blocks - ../modules/ncm.md — the NCM module, the config archive, compliance, jobs, and Cirrus.Nodes.ParseMacros for previewing macro expansion - README.md — the rest of this sec...

### [PerfStack (Performance Analysis)](webui/perfstack.md)

PerfStack — the Performance Analysis dashboard — puts metrics from different objects on a shared time axis so you can see whether the interface saturating and the application slowing happened together.

- [The URL grammar](webui/perfstack.md#the-url-grammar): The charts parameter is a list of metric selections.
- [Settle the grammar against your own server](webui/perfstack.md#settle-the-grammar-against-your-own-server): You do not have to trust any of the above.
- [Which metrics are valid for an object](webui/perfstack.md#which-metrics-are-valid-for-an-object): This is the half the schema can answer, and it is the half that changes with your modules.
- [Generating a link from an alert](webui/perfstack.md#generating-a-link-from-an-alert): This is the use case the feature exists for: an alert fires, and the notification carries a link to a PerfStack view already loaded with the right object.
- [Generating a link from a report](webui/perfstack.md#generating-a-link-from-a-report): A Custom Query widget can carry a PerfStack link per row, using the _LinkFor_ convention from custom-query-widget.md.
- [Gotchas](webui/perfstack.md#gotchas): Orion.Nodes with an InterfaceID produces a URL that loads and charts nothing, because the id resolves to a different object or to none.
- [Sources, and what is missing](webui/perfstack.md#sources-and-what-is-missing): SolarWinds documents PerfStack as a console feature and does not publish the URL grammar.
- [See also](webui/perfstack.md#see-also): into a clickable column - README.md — the rest of this section, and why the schema cannot verify console behaviour - ../swql/functions.md — ToString() and string concatenation - ../modules/npm.md — the interface stati...

### [Variable reference](webui/variables-reference.md)

The variables SolarWinds publishes, by context.

- [N=Alerting — the alert itself](webui/variables-reference.md#nalerting-the-alert-itself): Properties of the alert, not of the thing it fired on.
- [N=Generic — the installation and the clock](webui/variables-reference.md#ngeneric-the-installation-and-the-clock): That is how SolarWinds publishes it, beside AbbreviatedMonth with two.
- [N=OrionGroup — groups](webui/variables-reference.md#noriongroup-groups): Status identifiers resolve through ../schema/status-codes.md.
- [N=SwisEntity — node variables](webui/variables-reference.md#nswisentity-node-variables): These resolve against Orion.Nodes when the alert's ObjectType is a node.
- [Volume variables](webui/variables-reference.md#volume-variables): SolarWinds publishes these in the previous-generation form, without a context.
- [Syslog alert variables](webui/variables-reference.md#syslog-alert-variables): Previous-generation form, no context.
- [Trap alert variables](webui/variables-reference.md#trap-alert-variables): Previous-generation form.
- [See also](webui/variables-reference.md#see-also): and appear in no published table - ../automation/alerts.md — where these are stored and how alerts are driven through the API - ../schema/status-codes.md — the status integers

### [Variables SolarWinds does not publish](webui/variables-undocumented.md)

SolarWinds publishes no table containing these names.

- [The rule, and why it holds](webui/variables-undocumented.md#the-rule-and-why-it-holds): Every one of the 60 node variables SolarWinds publishes is a declared property of Orion.Nodes.
- [Why this is worth having anyway](webui/variables-undocumented.md#why-this-is-worth-having-anyway): Orion.Nodes declares 102 properties.
- [Orion.Nodes — 43 declared, unpublished](webui/variables-undocumented.md#orionnodes-43-declared-unpublished): The read-only Community is published as a node variable and this is its read/write counterpart.
- [Orion.Volumes — 30 declared, unpublished](webui/variables-undocumented.md#orionvolumes-30-declared-unpublished): That the published volume list is capacity-only and the schema carries five I/O counters is the clearest case on this page: an alert on a volume that is slow rather than full has nothing to say in the published vocabu...
- [Inherited members, which are a different thing](webui/variables-undocumented.md#inherited-members-which-are-a-different-thing): Eight members reachable from Orion.Nodes and twelve from Orion.Volumes are inherited from the platform base entities rather than declared, and most are lowercase where real properties are not:
- [Navigation is the larger unpublished surface](webui/variables-undocumented.md#navigation-is-the-larger-unpublished-surface): Orion.Nodes has 162 navigation properties and SolarWinds publishes three of them — Stats, SNMPv3Credentials and PCUs.
- [Testing a candidate](webui/variables-undocumented.md#testing-a-candidate): distinguishable from a broken alert.
- [See also](webui/variables-undocumented.md#see-also): and the IsInjected and IsInternal flags - ../automation/credentials.md — why RWCommunity and the SNMPv3 keys deserve care

### [Variables and macros](webui/variables.md)

A variable — SolarWinds also calls these macros — is a placeholder the platform substitutes at run time.

- [The three attributes](webui/variables.md#the-three-attributes): F has to correlate with the data.
- [The member list is the property list](webui/variables.md#the-member-list-is-the-property-list): M= on the SwisEntity context is a member of the trigger entity, and this repository has checked that against SolarWinds' own published tables:
- [${SQL:…} runs a query](webui/variables.md#sql-runs-a-query): Any value the database can produce can be a variable:
- [Custom properties are variables too](webui/variables.md#custom-properties-are-variables-too): A custom property is a column on the custom-property entity for its target, so it is reachable the same way as any other member.
- [What is in use on your own server](webui/variables.md#what-is-in-use-on-your-own-server): Alert messages are stored, so the variables actually being used are queryable.
- [Variables by module](webui/variables.md#variables-by-module): Which variables exist for a module is determined by which entities that module contributes, because those are the entities an alert can trigger on.
- [What is published, and what still is not](webui/variables.md#what-is-published-and-what-still-is-not): The tables SolarWinds publishes are in variables-reference.md: the Alerting, Generic and OrionGroup contexts, the node and volume lists, the UPS variables, and the previous-generation syslog and trap lists.
- [See also](webui/variables.md#see-also): behaviour - ../automation/alerts.md — alert definitions, actions and suppression through the API - ../automation/custom-properties.md — creating the properties that become variables - ../swis/metadata-introspection.md...

## docs/guides/

### [Building integrations against SWIS](guides/building-integrations.md)

This page is for software that talks to SWIS on a schedule or in response to events: a CMDB sync, a ticketing bridge, a chatops bot, an inventory exporter, a provisioning pipeline.

- [What an integration has to survive](guides/building-integrations.md#what-an-integration-has-to-survive): Each section below is one of those.
- [1. Choose the interface deliberately, once](guides/building-integrations.md#1-choose-the-interface-deliberately-once): SWIS has four interfaces and they are not interchangeable.
- [2. Give the integration its own account](guides/building-integrations.md#2-give-the-integration-its-own-account): Not a shared admin, not a person's account, and not the account another integration already uses.
- [3. Authentication and secret handling](guides/building-integrations.md#3-authentication-and-secret-handling): SWIS REST is HTTPS with HTTP basic authentication, on port 17774 from platform release 2023.1 onward.
- [4. One client, reused, with explicit timeouts](guides/building-integrations.md#4-one-client-reused-with-explicit-timeouts): Create the client once for the life of the process and share it.
- [5. Bind every parameter, every time](guides/building-integrations.md#5-bind-every-parameter-every-time): A SWQL parameter is written @name in the query text and supplied as a member called name in the parameters object.
- [6. Page large result sets](guides/building-integrations.md#6-page-large-result-sets): WITH ROWS <first> TO <last> takes a window of the result set and WITH TOTALROWS adds a totalRows member to the response envelope carrying the count the query would have returned without the window.
- [7. Retry safely, and know what repeats cleanly](guides/building-integrations.md#7-retry-safely-and-know-what-repeats-cleanly): Because reads and writes are both POSTs, a blanket retry policy configured on the HTTP transport cannot distinguish them.
- [8. Respect the database you are sharing](guides/building-integrations.md#8-respect-the-database-you-are-sharing): There is one SQL Server behind SWIS and the polling engines are writing to it constantly.
- [9. Feature-detect, do not version-check](guides/building-integrations.md#9-feature-detect-do-not-version-check): The obvious design is to read the platform version at startup and branch on it.
- [10. A worked example](guides/building-integrations.md#10-a-worked-example): A skeleton that does the things above: one reused session, explicit timeouts, retries only where they are safe, capability preflight at startup, paged reads, and a write path that resolves state instead of blindly ret...
- [Before you ship](guides/building-integrations.md#before-you-ship): logged every run.
- [Where to go next](guides/building-integrations.md#where-to-go-next): Metadata.* surface, which is what section 9 is built on - ../swis/invoke-verbs.md for the positional argument contract and per-client argument encoding - ../swis/bulk-operations.md for batch sizing and why the read-ba...

### [The SWQL cookbook](guides/cookbook.md)

Sixty questions an operator actually asks, each with a short answer and a query that runs.

- [Contents](guides/cookbook.md#contents)
- [How to run these](guides/cookbook.md#how-to-run-these): Paste one into SWQL Studio, or run it through a client.
- [Rules these queries follow](guides/cookbook.md#rules-these-queries-follow): Each of these prevents a specific failure rather than being a house style:
- [Inventory and audit](guides/cookbook.md#inventory-and-audit): The estate list.
- [Availability and outages](guides/cookbook.md#availability-and-outages): Status 2 is Down.
- [Capacity](guides/cookbook.md#capacity): The most requested report on the platform.
- [Performance](guides/cookbook.md#performance): Latency and loss together, because either alone produces a misleading list.
- [Alerting and noise](guides/cookbook.md#alerting-and-noise): The alerting model has four parts and confusing them is the usual reason an alert query returns nothing.
- [Change and configuration](guides/cookbook.md#change-and-configuration): Orion.Events records what the platform observed.
- [Licensing](guides/cookbook.md#licensing): Elements, not nodes, are what a licence counts.
- [Security posture](guides/cookbook.md#security-posture): Both send the community string in clear text on every poll.
- [Housekeeping](guides/cookbook.md#housekeeping): Two nodes with the same caption make every report ambiguous and every alert message useless.
- [When a recipe returns nothing](guides/cookbook.md#when-a-recipe-returns-nothing): Two causes account for nearly all of it, and neither is a problem with the query.
- [Related pages](guides/cookbook.md#related-pages): than errors - ../reference/entity-index.md to find the entity behind a question this page does not cover

### [Getting started](guides/getting-started.md)

This page takes you from a machine with nothing installed to two things: a query that returns rows from your own server, and a change that you made through the API and then proved was made.

- [Before you start](guides/getting-started.md#before-you-start): Three things, none of which the tools can supply for you.
- [Step 1: install the Orion SDK tools](guides/getting-started.md#step-1-install-the-orion-sdk-tools): The Orion SDK is SolarWinds' own open-source package.
- [Step 2: install a scripting client](guides/getting-started.md#step-2-install-a-scripting-client): Pick one.
- [Step 3: connect](guides/getting-started.md#step-3-connect): Use $hostname, not $host.
- [Step 4: your first query](guides/getting-started.md#step-4-your-first-query): The same query in each client.
- [Step 5: read the result properly](guides/getting-started.md#step-5-read-the-result-properly): You have rows.
- [Step 6: your first safe change](guides/getting-started.md#step-6-your-first-safe-change): Unmanaging and remanaging a node is the right first write, for three reasons: it is reversible in one call, it changes something you can see immediately in the web console, and it exercises the two things that go wron...
- [Where to go next](guides/getting-started.md#where-to-go-next): You now have the two halves of everything else: a read path and a write path.

### [A Layer 2 switching Modern Dashboard for the whole platform](guides/layer2-switching-dashboard.md)

The companion to soc2-dashboard-10k-nodes.md, scoped to the access and distribution layer: switch ports, interfaces, duplex, VLANs, trunks, topology, and the endpoints plugged into it all.

- [Row 1 — Switching health scorecard (kpi widget, six tiles)](guides/layer2-switching-dashboard.md#row-1-switching-health-scorecard-kpi-widget-six-tiles): One query per tile, one row per query.
- [Row 2 — Interface faults (the actionable lists)](guides/layer2-switching-dashboard.md#row-2-interface-faults-the-actionable-lists): Down-but-shouldn't-be interfaces (table widget).
- [Row 3 — VLANs and trunks](guides/layer2-switching-dashboard.md#row-3-vlans-and-trunks): VLAN footprint (proportional widget, bar) — how many switches carry each VLAN.
- [Row 4 — Port capacity (requires UDT)](guides/layer2-switching-dashboard.md#row-4-port-capacity-requires-udt): Fullest access switches (table widget).
- [Row 5 — Who is plugged in (requires UDT)](guides/layer2-switching-dashboard.md#row-5-who-is-plugged-in-requires-udt): Rogue endpoints (table widget) — devices UDT has seen that match no watch/allow rule.
- [Scoping the page to switches only](guides/layer2-switching-dashboard.md#scoping-the-page-to-switches-only): Orion.NPM.Interfaces and Orion.UDT.Port scope themselves — a port implies a switch.
- [Assembling and verifying](guides/layer2-switching-dashboard.md#assembling-and-verifying): Identical to the SOC 2 page: validate (python3 tools/validate_swql.py --docs docs/guides/layer2-switching-dashboard.md), start from scripts/dashboards/minimal-dashboard.json regenerating every unique_key, write each q...
- [See also](guides/layer2-switching-dashboard.md#see-also)

### [A SOC 2–style Modern Dashboard for a 10,000-node environment](guides/soc2-dashboard-10k-nodes.md)

A recipe: every SWQL query for a customer/vendor-facing trust dashboard, with the Modern Dashboard widget type called out for each.

- [Design rules at 10k nodes](guides/soc2-dashboard-10k-nodes.md#design-rules-at-10k-nodes): Four things separate a dashboard that works at 10,000 nodes from one that times out:
- [Row 1 — Service health scorecard (kpi widget, six tiles)](guides/soc2-dashboard-10k-nodes.md#row-1-service-health-scorecard-kpi-widget-six-tiles): One kpi widget, six tiles, one query per tile.
- [Row 2 — Availability (the "A" in SOC 2)](guides/soc2-dashboard-10k-nodes.md#row-2-availability-the-a-in-soc-2): Tile or single big number — 24-hour fleet availability (kpi widget, one tile).
- [Row 3 — Security and incident response](guides/soc2-dashboard-10k-nodes.md#row-3-security-and-incident-response): Active alert triage (table widget).
- [Row 4 — Capacity hotspots (processing-integrity evidence)](guides/soc2-dashboard-10k-nodes.md#row-4-capacity-hotspots-processing-integrity-evidence): Four table widgets, each a bounded top-N of live exceptions.
- [Row 5 — Change management (requires NCM)](guides/soc2-dashboard-10k-nodes.md#row-5-change-management-requires-ncm): Skip this row if NCM is not installed; the Cirrus.* entities will not exist.
- [Slicing by customer or site](guides/soc2-dashboard-10k-nodes.md#slicing-by-customer-or-site): A dashboard "used by customers and vendors" usually needs a per-tenant cut.
- [Assembling and verifying the file](guides/soc2-dashboard-10k-nodes.md#assembling-and-verifying-the-file): regenerating every unique_key per its README.
- [See also](guides/soc2-dashboard-10k-nodes.md#see-also)

### [Troubleshooting SWIS](guides/troubleshooting.md)

Organised by what you are looking at, because that is what you have when something breaks.

- [Triage](guides/troubleshooting.md#triage)
- [The connection never lands](guides/troubleshooting.md#the-connection-never-lands): Connection refused, No connection could be made because the target machine actively refused it, Failed to connect, or a client that hangs until it times out.
- [The TLS handshake fails](guides/troubleshooting.md#the-tls-handshake-fails): The message depends on the client, but they all mean the same thing:
- [401 Unauthorized](guides/troubleshooting.md#401-unauthorized): HTTP 401, or The remote server returned an error: (401) Unauthorized.
- [403, or a permission message](guides/troubleshooting.md#403-or-a-permission-message): HTTP 403, or a message naming a right, or a verb that returns an error mentioning permission.
- [A query fails with 400](guides/troubleshooting.md#a-query-fails-with-400): HTTP 400 with a message that usually names the offending token.
- [A query returns no rows when you expect some](guides/troubleshooting.md#a-query-returns-no-rows-when-you-expect-some): This is a 200 with "results": [], which is not an error and is the most commonly misdiagnosed symptom on the platform.
- [A query is slow or times out](guides/troubleshooting.md#a-query-is-slow-or-times-out): A client timeout, a request that takes minutes, or a noticeable load spike on the database while your report runs.
- [A verb fails with a type or argument error](guides/troubleshooting.md#a-verb-fails-with-a-type-or-argument-error): An error naming an argument type, or complaining about the number of arguments, or a serialisation failure from PowerShell.
- [A verb reports success but nothing changes](guides/troubleshooting.md#a-verb-reports-success-but-nothing-changes): The most expensive symptom on this page, because nothing tells you it happened.
- [CRUD rejects a create](guides/troubleshooting.md#crud-rejects-a-create): A create that is refused, or an error naming a property, or a created entity that does not do anything.
- [Entity not found after an upgrade](guides/troubleshooting.md#entity-not-found-after-an-upgrade): A query or a script that worked before an upgrade now fails naming an entity, a property, or a verb.
- [The numbers disagree with the web console](guides/troubleshooting.md#the-numbers-disagree-with-the-web-console): A count, a total or an average from a query that does not match what the console shows for the same thing.
- [What to capture before asking for help](guides/troubleshooting.md#what-to-capture-before-asking-for-help): Whether you are opening a support case or handing the problem to a colleague, these five things turn a description into something diagnosable:
- [Related pages](guides/troubleshooting.md#related-pages): connection - cookbook.md for the queries themselves - ../swis/connecting.md for ports, authentication modes and TLS - ../swis/rest-api.md for the REST error contract - ../swis/invoke-verbs.md for verb-specific failure...

### [Wireless heat maps](guides/wireless-heatmaps.md)

A heat map is the one part of the wireless model that is not simply polled and displayed.

- [Where the data comes from](guides/wireless-heatmaps.md#where-the-data-comes-from): Three sources feed a map, and they are not equivalent.
- [The shape of the data](guides/wireless-heatmaps.md#the-shape-of-the-data): Four things about this structure are worth knowing before writing any code against it.
- [Reading it](guides/wireless-heatmaps.md#reading-it): The queries are in ../../scripts/swql/17-wireless-heatmaps.swql.
- [Writing it](guides/wireless-heatmaps.md#writing-it): SWQL cannot write.
- [Hardware the feature was not built for](guides/wireless-heatmaps.md#hardware-the-feature-was-not-built-for): Wanting heat maps for non-Cisco wireless is a reasonable thing to want, and it comes up often enough to be worth setting out honestly.
- [What the platform will and will not ingest](guides/wireless-heatmaps.md#what-the-platform-will-and-will-not-ingest): The question behind most heat-map scripting is whether there is any way in — for signal data, or failing that for wireless clients — that does not go through a controller SolarWinds already polls.
- [When a map is wrong](guides/wireless-heatmaps.md#when-a-map-is-wrong): Work down, not across.
- [Related pages](guides/wireless-heatmaps.md#related-pages): four overlapping families - ../swis/invoke-verbs.md — calling verbs, and positional arguments - ../swis/metadata-introspection.md — asking a live server what it actually declares - ../reference/verb-index.md — every v...

## docs/reference/

### [Reference](reference/README.md)

Lookup tables.

- [The generated pages are not to be edited](reference/README.md#the-generated-pages-are-not-to-be-edited): Five pages are produced by tools/build_reference_docs.py from the extracted schema and reference data.
- [Reading a whole page is rarely the fast path](reference/README.md#reading-a-whole-page-is-rarely-the-fast-path): Each page is an enumeration, which makes it the right tool for browsing, for diffing, and for answering "what else is there".
- [The written page](reference/README.md#the-written-page): glossary.md defines the vocabulary: SWIS, SWQL, entity, verb, NetObject, element, rollup, unmanaged, the module acronyms and the three product names.
- [Two more generators](reference/README.md#two-more-generators): Two more of the pages in this directory are generated, by two more generators, from two more kinds of source.
- [Regenerating everything](reference/README.md#regenerating-everything): make data VERSION=2025.4 documents a different release.
- [When the answer is not here](reference/README.md#when-the-answer-is-not-here): This directory documents one platform version, and the schema varies with the release and with which modules are licensed and installed.

### [Entity index](reference/entity-index.md)

Every entity published in the SolarWinds Information Service schema for platform version 2026.2: 2067 entities across 16 namespaces, holding 19328 properties.

- [Namespaces](reference/entity-index.md#namespaces)
- [Orion](reference/entity-index.md#orion): 1705 entities.
- [IPAM](reference/entity-index.md#ipam): 77 entities.
- [NCM](reference/entity-index.md#ncm): 72 entities.
- [Cortex](reference/entity-index.md#cortex): 69 entities.
- [Cirrus](reference/entity-index.md#cirrus): 57 entities.
- [System](reference/entity-index.md#system): 29 entities.
- [DPA](reference/entity-index.md#dpa): 18 entities.
- [Metadata](reference/entity-index.md#metadata): 11 entities.
- [ContentModel](reference/entity-index.md#contentmodel): 8 entities.
- [Cli](reference/entity-index.md#cli): 5 entities.
- [UamsClient](reference/entity-index.md#uamsclient): 5 entities.
- [PlatformConnect](reference/entity-index.md#platformconnect): 3 entities.
- [SWISf](reference/entity-index.md#swisf): 3 entities.
- [SOC](reference/entity-index.md#soc): 2 entities.
- [Vdc](reference/entity-index.md#vdc): 2 entities.
- [PlatformBridge](reference/entity-index.md#platformbridge): 1 entities.

### [Glossary](reference/glossary.md)

The platform uses a lot of ordinary words in a specific way.

- [Account limitation](reference/glossary.md#account-limitation): A restriction attached to an Orion account that narrows the set of objects that account can see.
- [Additional web server](reference/glossary.md#additional-web-server): A second (or third) machine running the Orion Web Console against the same database, added for capacity or for placing the console closer to its users.
- [Cipher password](reference/glossary.md#cipher-password): The password the WPM recording verbs use to encrypt and decrypt an exported recording file: Orion.SEUM.Recordings.Export(recordingId, password) ciphers the file it returns, and Import and Update take the same value to...
- [Container](reference/glossary.md#container): The base entity behind groups.
- [CRUD](reference/glossary.md#crud): Create, read, update and delete: the SWIS interface for working with one entity instance at a time.
- [Custom property](reference/glossary.md#custom-property): A user-defined column added to a monitored object type, stored on a companion entity rather than on the object itself: node custom properties live on Orion.NodesCustomProperties, reached from a node through the Custom...
- [Dependency](reference/glossary.md#dependency): A declared parent/child relationship between two monitored objects, used so that an outage on the parent suppresses alerts on everything behind it.
- [Discovery](reference/glossary.md#discovery): Two different features share the name.
- [DisplayName](reference/glossary.md#displayname): One of the five properties every entity inherits from System.Entity, alongside Description, InstanceType, Uri and InstanceSiteId.
- [DPA](reference/glossary.md#dpa): Database Performance Analyzer, which monitors database instances, waits, blocking and expensive queries.
- [Element](reference/glossary.md#element): The platform's licensing unit: roughly, one monitored thing that counts against a licence.
- [Entity](reference/glossary.md#entity): A type in the SWIS schema: Orion.Nodes, Orion.NPM.Interfaces, Metadata.Verb.
- [Group](reference/glossary.md#group): A user-defined collection of monitored objects whose status rolls up from its members, and which can be alerted on, reported on and used as an alert-suppression boundary.
- [InstanceType](reference/glossary.md#instancetype): One of the five properties inherited from System.Entity.
- [Interface](reference/glossary.md#interface): A network interface on a node, monitored by NPM and held in Orion.NPM.Interfaces.
- [Invoke](reference/glossary.md#invoke): The SWIS interface for calling a verb: POST /Invoke/{Entity}/{Verb} with a JSON array as the body.
- [IPAM](reference/glossary.md#ipam): IP Address Manager, which manages subnets, IP address assignments, DHCP scopes and DNS zones.
- [Key property](reference/glossary.md#key-property): The property or properties that form an entity's primary key.
- [LA](reference/glossary.md#la): Log Analyzer, which collects syslog messages, SNMP traps and log entries and applies processing rules to them.
- [List Resources](reference/glossary.md#list-resources): The operation behind the "List Resources" button in node management: ask a node that is already monitored what else it can report, then turn on the pollers, interfaces and volumes you want.
- [Maintenance window](reference/glossary.md#maintenance-window): A scheduled period during which an object is unmanaged, so that planned work does not generate alerts or gaps that look like faults.
- [Managed entity](reference/glossary.md#managed-entity): System.ManagedEntity, described in the schema as "something that has an externally-determined up/down status", and the base type for everything the platform monitors: nodes, interfaces, volumes, applications, groups a...
- [Module](reference/glossary.md#module): A licensed product that extends the platform with its own entities, pollers and web console pages: NPM, SAM, NCM and the rest.
- [Navigation property](reference/glossary.md#navigation-property): A named, pre-declared join between two entities that you write as a dotted path instead of an ON clause: n.Interfaces.Caption, i.Node.Caption.
- [NCM](reference/glossary.md#ncm): Network Configuration Manager, which backs up and compares device configurations, runs compliance policies and pushes changes.
- [NetObject](reference/glossary.md#netobject): The platform's own way of identifying one monitored object across types, written as a type prefix, a colon and an id: N:42 is node 42, I:7 is interface 7.
- [NetObject prefix](reference/glossary.md#netobject-prefix): The short type code at the front of a NetObject string: N for a node, I for an interface, V for a volume, AA for a SAM application.
- [Node](reference/glossary.md#node): A monitored device: a server, switch, router, firewall or anything else the platform polls as a whole machine.
- [NPM](reference/glossary.md#npm): Network Performance Monitor, the module that monitors interfaces, wireless, routing, fibre channel and NetPath.
- [NTA](reference/glossary.md#nta): NetFlow Traffic Analyzer, which stores and reports on flow records exported by network devices.
- [Orion Platform](reference/glossary.md#orion-platform): The original and longest-lived name for the product, renamed to SolarWinds Platform around the 2022.4 releases and then to SolarWinds Observability Self-Hosted for the self-hosted edition.
- [Policy report](reference/glossary.md#policy-report): An NCM compliance artifact with three tiers: one report groups policies, each policy names the nodes and config type its rules apply to, and each rule is a test with optional remediation.
- [Poller](reference/glossary.md#poller): A named piece of collection logic, and by extension the assignment that points one at an object.
- [Poller type](reference/glossary.md#poller-type): The string that names a poller, following the convention <NetObjectType>.<Category>.<Method>.<Variant>, as in N.Cpu.SNMP.CiscoGen3.
- [Polling engine](reference/glossary.md#polling-engine): A server that runs collection jobs against monitored devices.
- [Property](reference/glossary.md#property): A named, typed value on an entity, such as Orion.Nodes.Caption.
- [QoE](reference/glossary.md#qoe): Quality of Experience, which uses deep packet inspection to measure application and network response for traffic seen by a probe.
- [Rank](reference/glossary.md#rank): The severity ordering used when statuses are combined, exposed as Orion.StatusInfo.Ranking.
- [Relationship](reference/glossary.md#relationship): A declared connection between two entities, which SWIS turns into a navigation property on each end.
- [Rollup](reference/glossary.md#rollup): Computing one object's status from the statuses of the things beneath it, which is what makes a group or a parent object go red when a member does.
- [SAM](reference/glossary.md#sam): Server and Application Monitor, which monitors applications and their components through templates, including the AppInsight applications for SQL Server, IIS and Exchange.
- [SCM](reference/glossary.md#scm): Server Configuration Monitor, which polls servers for their configuration and reports when it drifts from a baseline.
- [SolarWinds Observability Self-Hosted](reference/glossary.md#solarwinds-observability-self-hosted): The current name for the self-hosted product, distinguishing it from SolarWinds' SaaS observability offering.
- [SolarWinds Platform](reference/glossary.md#solarwinds-platform): The middle name in the product's history, introduced around the 2022.4 releases and still used throughout SolarWinds' own SDK documentation in phrases such as "Supported since: SolarWinds Platform 2023.2".
- [SRM](reference/glossary.md#srm): Storage Resource Monitor, which monitors storage arrays, pools, LUNs, file shares and NAS volumes.
- [Status](reference/glossary.md#status): An integer stored on every monitored entity that encodes its health, rendered in the web console as a coloured icon.
- [SWIS](reference/glossary.md#swis): The SolarWinds Information Service: the data access layer and API that sits in front of the Orion database, exposing a hybrid object-oriented and relational model with its own query language.
- [SWQL](reference/glossary.md#swql): SolarWinds Query Language, the SQL-like language SWIS queries are written in.
- [SWQL Studio](reference/glossary.md#swql-studio): The graphical query tool shipped with the Orion SDK: an object explorer built from the Metadata.* entities, a query editor and an invoke-verb tab.
- [UDT](reference/glossary.md#udt): User Device Tracker, which records which endpoints are connected to which switch ports and keeps the MAC, IP and user history behind that.
- [Unmanaged](reference/glossary.md#unmanaged): The state an object is in while a maintenance window is open: polling stops, alerts do not fire, and the object's status shows as unmanaged rather than down.
- [URI](reference/glossary.md#uri): A SWIS URI uniquely identifies one entity instance and looks like swis://<system-identifier>/Orion/Orion.Nodes/NodeID=42.
- [Verb](reference/glossary.md#verb): A named operation an entity publishes, invoked rather than queried: Unmanage, PollNow, Acknowledge, CreateCustomProperty.
- [VMAN](reference/glossary.md#vman): Virtualization Manager, which monitors vCenters, hosts, clusters, datastores and virtual machines.
- [VNQM](reference/glossary.md#vnqm): VoIP and Network Quality Manager, which monitors IP SLA operations, call managers, phones and call detail records.
- [Volume](reference/glossary.md#volume): A storage object on a monitored node, held in Orion.Volumes with the NetObject prefix V: a fixed disk, a network share, a RAM disk and so on, as VolumeType records.
- [WPM](reference/glossary.md#wpm): Web Performance Monitor, which plays back recorded browser transactions from chosen locations and reports on their steps and timings.
- [Related pages](reference/glossary.md#related-pages): inheritance and keys - ../schema/relationships.md for relationship kinds and navigation - ../platform/modules.md for the full module-to-namespace map - ../swis/README.md for the four interfaces - unverified.md for eve...

### [NetObject type reference](reference/netobject-types.md)

A NetObject string identifies one monitored object as a type prefix and an id: node 42 is N:42, interface 7 is I:7.

### [Schema changes: 2025.4 to 2026.2](reference/schema-changes-2025.4-to-2026.2.md)

What changed in the SWIS schema between these two platform versions, and which of those changes can break code that already works.

- [Summary](reference/schema-changes-2025.4-to-2026.2.md#summary)
- [Removed entities](reference/schema-changes-2025.4-to-2026.2.md#removed-entities): 7 entities present in 2025.4 are absent from 2026.2.
- [Verb signature changes that break callers](reference/schema-changes-2025.4-to-2026.2.md#verb-signature-changes-that-break-callers): Invoke arguments are positional.
- [Entities that lost properties or navigation properties](reference/schema-changes-2025.4-to-2026.2.md#entities-that-lost-properties-or-navigation-properties): A query selecting a removed property fails outright.
- [Properties whose type changed](reference/schema-changes-2025.4-to-2026.2.md#properties-whose-type-changed): These do not fail a SWQL query, but they can fail a typed client that binds the column to a field.
- [New verbs](reference/schema-changes-2025.4-to-2026.2.md#new-verbs): 20 verbs are available in 2026.2 that were not in 2025.4.
- [New entities](reference/schema-changes-2025.4-to-2026.2.md#new-entities): 93 entities are new in 2026.2.

### [Schema changes: 2026.1 to 2026.2](reference/schema-changes-2026.1-to-2026.2.md)

What changed in the SWIS schema between these two platform versions, and which of those changes can break code that already works.

- [Summary](reference/schema-changes-2026.1-to-2026.2.md#summary)
- [Removed entities](reference/schema-changes-2026.1-to-2026.2.md#removed-entities): 4 entities present in 2026.1 are absent from 2026.2.
- [Verb signature changes that break callers](reference/schema-changes-2026.1-to-2026.2.md#verb-signature-changes-that-break-callers): Invoke arguments are positional.
- [Entities that lost properties or navigation properties](reference/schema-changes-2026.1-to-2026.2.md#entities-that-lost-properties-or-navigation-properties): A query selecting a removed property fails outright.
- [Properties whose type changed](reference/schema-changes-2026.1-to-2026.2.md#properties-whose-type-changed): These do not fail a SWQL query, but they can fail a typed client that binds the column to a field.
- [New verbs](reference/schema-changes-2026.1-to-2026.2.md#new-verbs): 14 verbs are available in 2026.2 that were not in 2026.1.
- [New entities](reference/schema-changes-2026.1-to-2026.2.md#new-entities): 53 entities are new in 2026.2.

### [Status code reference](reference/status-codes.md)

Status is stored as an integer on every monitored entity.

- [Resolving status in a query](reference/status-codes.md#resolving-status-in-a-query): Do not hard-code these numbers into a report.

### [SWQL function index](reference/swql-function-index.md)

63 functions, of which 62 appear in the official SolarWinds SWQL function reference.

- [Aggregate](reference/swql-function-index.md#aggregate)
- [Array functions](reference/swql-function-index.md#array-functions)
- [Date Time](reference/swql-function-index.md#date-time)
- [Date/time](reference/swql-function-index.md#datetime)
- [General](reference/swql-function-index.md#general)
- [Numeric](reference/swql-function-index.md#numeric)
- [String](reference/swql-function-index.md#string): ---

### [What this repository does not verify](reference/unverified.md)

Everything in these guides was checked against the extracted SolarWinds schema before it was written, and every SWQL statement is re-checked on each build.

- [accounts-and-permissions.md](reference/unverified.md#accounts-and-permissionsmd): AccountType
- [alerts.md](reference/unverified.md#alertsmd): What is not verified here
- [credential-integration.md](reference/unverified.md#credential-integrationmd): Orion.CredentialRelation is the mechanism nobody mentions
- [credentials.md](reference/unverified.md#credentialsmd): Credential types
- [custom-properties.md](reference/unverified.md#custom-propertiesmd): The one structural fact to hold on to
- [dependencies.md](reference/unverified.md#dependenciesmd): How a dependency is expressed
- [discovery.md](reference/unverified.md#discoverymd): Phase 1b: the interfaces plugin configuration
- [events-and-auditing.md](reference/unverified.md#events-and-auditingmd): Down and back up, in one row
- [high-availability.md](reference/unverified.md#high-availabilitymd): High availability
- [maintenance-mode.md](reference/unverified.md#maintenance-modemd): Recipe: bulk unmanage driven by a query
- [node-management.md](reference/unverified.md#node-managementmd): The properties to set on create
- [report-definitions.md](reference/unverified.md#report-definitionsmd): The skeleton
- [reporting.md](reference/unverified.md#reportingmd): Report schedules are not Orion.ScheduleTaskDefinition
- [scheduling.md](reference/unverified.md#schedulingmd): A cron expression without its timezone is ambiguous
- [building-integrations.md](reference/unverified.md#building-integrationsmd): 3.
- [cookbook.md](reference/unverified.md#cookbookmd): Rules these queries follow
- [wireless-heatmaps.md](reference/unverified.md#wireless-heatmapsmd): Writing it
- [agents.md](reference/unverified.md#agentsmd): Namespaces and how many entities
- [cloud.md](reference/unverified.md#cloudmd): Tag filters and resource tags are different entities
- [dpa.md](reference/unverified.md#dpamd): The wait-time entities
- [hardware-health.md](reference/unverified.md#hardware-healthmd): Enabling and disabling individual sensors
- [ipam.md](reference/unverified.md#ipammd): The status values, and how to find out what the numbers are
- [log-analyzer.md](reference/unverified.md#log-analyzermd): Verbs
- [ncm-device-templates.md](reference/unverified.md#ncm-device-templatesmd): The root attributes
- [ncm.md](reference/unverified.md#ncmmd): Gotchas
- [npm.md](reference/unverified.md#npmmd): Wireless
- [nta.md](reference/unverified.md#ntamd): Lookup entities
- [qoe.md](reference/unverified.md#qoemd): Applications are the centre of the model
- [sam-templates.md](reference/unverified.md#sam-templatesmd): The root is an array
- [sam.md](reference/unverified.md#sammd): Gotchas
- [scm-compliance-policies.md](reference/unverified.md#scm-compliance-policiesmd): The SWIS round trip (2026.2, verified)
- [scm.md](reference/unverified.md#scmmd): Profiles
- [srm.md](reference/unverified.md#srmmd): Providers
- [vman.md](reference/unverified.md#vmanmd): Hosts, clusters, datacenters and vCenters
- [vnqm.md](reference/unverified.md#vnqmmd): IP SLA operations
- [wpm.md](reference/unverified.md#wpmmd): What is not verified here
- [modules.md](reference/unverified.md#modulesmd): DPA: Database Performance Analyzer
- [api-poller-unifi-network.md](reference/unverified.md#api-poller-unifi-networkmd): The base path depends on how Network is deployed
- [api-poller-vendor-templates.md](reference/unverified.md#api-poller-vendor-templatesmd): Three Type values, from real exports
- [api-pollers.md](reference/unverified.md#api-pollersmd): The poller
- [device-studio.md](reference/unverified.md#device-studiomd): The poller definitions
- [node-status-calculation.md](reference/unverified.md#node-status-calculationmd): 2.
- [standard-pollers.md](reference/unverified.md#standard-pollersmd): Interfaces: discover, then add with default pollers
- [technology-polling.md](reference/unverified.md#technology-pollingmd): What technologies exist
- [glossary.md](reference/unverified.md#glossarymd): Element
- [entity-model.md](reference/unverified.md#entity-modelmd): The tree is rooted at System.Entity
- [key-entities.md](reference/unverified.md#key-entitiesmd): Orion.AlertStatus
- [netobject-types.md](reference/unverified.md#netobject-typesmd): Entries that no longer resolve in 2026.2
- [status-codes.md](reference/unverified.md#status-codesmd): Resolving status on a live server
- [invoke-at-scale.md](reference/unverified.md#invoke-at-scalemd): Authorization is thinner than it looks
- [invoke-verbs.md](reference/unverified.md#invoke-verbsmd): How arguments are serialised
- [metadata-introspection.md](reference/unverified.md#metadata-introspectionmd): How they connect
- [uris.md](reference/unverified.md#urismd): The key filter
- [date-and-time.md](reference/unverified.md#date-and-timemd): Where the trap does not reach
- [functions.md](reference/unverified.md#functionsmd): UNION(q)
- [gotchas.md](reference/unverified.md#gotchasmd): SWQL gotchas
- [language-reference.md](reference/unverified.md#language-referencemd): How this page marks its evidence
- [performance.md](reference/unverified.md#performancemd): 9.
- [README.md](reference/unverified.md#readmemd): A caveat that applies to the whole section
- [custom-query-widget.md](reference/unverified.md#custom-query-widgetmd): Where the link value comes from
- [modern-dashboard-authoring.md](reference/unverified.md#modern-dashboard-authoringmd): Reusing another dashboard's widget from the console
- [modern-dashboards.md](reference/unverified.md#modern-dashboardsmd): Modern Dashboard files
- [ncm-change-template-language.md](reference/unverified.md#ncm-change-template-languagemd): If you know C#, what does not transfer
- [ncm-change-templates.md](reference/unverified.md#ncm-change-templatesmd): The directives
- [perfstack.md](reference/unverified.md#perfstackmd): The URL grammar
- [variables-reference.md](reference/unverified.md#variables-referencemd): Variable reference
- [variables-undocumented.md](reference/unverified.md#variables-undocumentedmd): Navigation is the larger unpublished surface
- [variables.md](reference/unverified.md#variablesmd): The three attributes

### [Verb index](reference/verb-index.md)

Every invokable verb in platform version 2026.2: 1021 verbs, of which 848 carry typed, named, ordered parameters recovered from the SWIS Swagger contract.

- [Namespaces](reference/verb-index.md#namespaces)
- [Orion](reference/verb-index.md#orion)
- [Cirrus](reference/verb-index.md#cirrus)
- [Cortex](reference/verb-index.md#cortex)
- [IPAM](reference/verb-index.md#ipam)
- [NCM](reference/verb-index.md#ncm)
- [UamsClient](reference/verb-index.md#uamsclient)
- [PlatformConnect](reference/verb-index.md#platformconnect)
- [PlatformBridge](reference/verb-index.md#platformbridge)
- [Cli](reference/verb-index.md#cli)
- [System](reference/verb-index.md#system)
- [Metadata](reference/verb-index.md#metadata)
- [SOC](reference/verb-index.md#soc): ---


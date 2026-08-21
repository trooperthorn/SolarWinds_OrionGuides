<!-- GENERATED FILE. Do not edit by hand.
     Produced by tools/build_unverified_index.py from the documentation itself.
     Regenerate with: make docs-reference -->

# What this repository does not verify

Everything in these guides was checked against the extracted SolarWinds schema before it was written, and every SWQL statement is re-checked on each build. Some things cannot be checked that way: behaviour that only a running server exhibits, values that are installation data rather than schema, and the handful of places where SolarWinds' own documentation and their published contract disagree.

The rule is that those say so rather than being asserted quietly or dropped. This page collects every such statement in one place, because an admission is in the right place on its page and the wrong place when you want the whole picture.

**80 statements across 31 pages.**

Read this before relying on this repository for something load-bearing. If you have a live server, this is also the working list: most entries name the `Metadata.*` query or the experiment that would close the gap. See [../swis/metadata-introspection.md](../swis/metadata-introspection.md).

## [accounts-and-permissions.md](../automation/accounts-and-permissions.md)

**[`AccountType`](../automation/accounts-and-permissions.md#accounttype)**

- The value an Orion-only account carries is **not recorded in the published schema** and is unverified here.
**[`CreateOneTimeLoginToken`](../automation/accounts-and-permissions.md#createonetimelogintoken)**

- What the token is valid for, and for how long, is not recorded in the published schema and is unverified here.
**[Which account column corresponds to which right](../automation/accounts-and-permissions.md#which-account-column-corresponds-to-which-right)**

- The rest of the table below is inferred from the names and is unverified here; confirm it on your own server by granting one right to a test account and seeing which calls start succeeding.
- It gates 21 verbs, including `Orion.Nodes.StartRealTimePolling` and `Orion.Nodes.StopRealTimePolling`, but searching the 2026.2 property data for a matching account column returns nothing, so how it is granted is **not recorded in the published schema** and is unverified here.
**[The limitation verbs](../automation/accounts-and-permissions.md#the-limitation-verbs)**

- Rebinding an existing limitation to a different account means writing the `LimitationIDn` column on `Orion.Accounts`, and whether `UpdateAccount` accepts `LimitationID1` in its properties dictionary is **not recorded in the published schema** and is unverified here.
**[Accounts that carry a limitation](../automation/accounts-and-permissions.md#accounts-that-carry-a-limitation)**

- `IsNull(column, 0) <> 0` covers both ways an unused slot can be represented, because whether an empty slot holds `0` or `NULL` is not recorded in the schema.

## [alerts.md](../automation/alerts.md)

**[Reading suppression state properly](../automation/alerts.md#reading-suppression-state-properly)**

- The extracted schema records the verb as returning `array` without describing the element, so **the exact serialised member names on the wire are not verified here**.
**[What is not verified here](../automation/alerts.md#what-is-not-verified-here)**

- ## What is not verified here

## [credentials.md](../automation/credentials.md)

**[Credential types](../automation/credentials.md#credential-types)**

- The table below is [SolarWinds' published list](https://solarwinds.github.io/OrionSDK/docs/credential-management/), which is the authority for it: these strings are not entity names in the SWIS schema and this repository cannot verify them against the extracted data.
**[Type-specific verbs](../automation/credentials.md#type-specific-verbs)**

- The accepted values for the method arguments are not recorded in the published schema and are unverified here.
**[Credentials cannot be read back](../automation/credentials.md#credentials-cannot-be-read-back)**

- What a query against them actually returns is runtime behaviour and is **not verified here**.

## [custom-properties.md](../automation/custom-properties.md)

**[The one structural fact to hold on to](../automation/custom-properties.md#the-one-structural-fact-to-hold-on-to)**

- They are created per installation, they are not in the published schema, and so this repository cannot verify them.
**[CreateCustomProperty](../automation/custom-properties.md#createcustomproperty)**

- The allowed `ValueType` values and which parameters are ignored are not recorded in the schema data, so that page is where to check them.
- How that serialises over REST is not recorded in the published schema and cannot be verified here, so the safe value is null.
**[ValidateCustomProperty](../automation/custom-properties.md#validatecustomproperty)**

- The shape of `CustomPropertyValidationResult` is not recorded in the published schema, so it is unverified here.

## [discovery.md](../automation/discovery.md)

**[Phase 1b: the interfaces plugin configuration](../automation/discovery.md#phase-1b-the-interfaces-plugin-configuration)**

- `AutoImportExpressionFilter` is present in the 2026.2 contract with members `Prop`, `Op` and `Val`, but no accepted property names or operators are documented and no sample uses it, so **its usage is unverified here**.
**[Importing a staged discovery](../automation/discovery.md#importing-a-staged-discovery)**

- The semantics of `SelectedDiscoveredResources` are unverified here.
**[Checking a credential before you scan with it](../automation/discovery.md#checking-a-credential-before-you-scan-with-it)**

- The keys it expects are not described in the schema or the Swagger contract**, and no SDK sample calls this verb, so the content is unverified here.
**[List Resources on an address that is not a node yet](../automation/discovery.md#list-resources-on-an-address-that-is-not-a-node-yet)**

- Both are unverified here.** Check `Metadata.VerbArgument.XmlTemplate` on your own server.
**[What is not verified here](../automation/discovery.md#what-is-not-verified-here)**

- ## What is not verified here

## [events-and-auditing.md](../automation/events-and-auditing.md)

**[Down and back up, in one row](../automation/events-and-auditing.md#down-and-back-up-in-one-row)**

- The timezone of `DateTimeFrom` is not documented in the schema, so measure it the same way before building a report on it.
**[What is not verified here](../automation/events-and-auditing.md#what-is-not-verified-here)**

- ## What is not verified here

## [node-management.md](../automation/node-management.md)

**[The properties to set on create](../automation/node-management.md#the-properties-to-set-on-create)**

- Which properties are required on create is **not recorded in the published schema**, and the Swagger contract does not mark them either, so the honest statement is: the set below is what SolarWinds' own [`CRUD.AddNode.ps1`](https://github.com/solarwinds/OrionSDK/blob/master/Samples/PowerShell/CRUD.AddNode.ps1) sample sets, and every name in it is a real `Orion.Nodes` property in 2026.2.
**[SNMPv3](../automation/node-management.md#snmpv3)**

- The accepted values for `AuthenticationMethod` and `PrivacyMethod` are not recorded in the published schema; the sample script names `None`, `MD5` and `SHA1` for authentication and `None`, `DES56`, `AES128`, `AES192` and `AES256` for privacy, which is worth treating as indicative rather than authoritative for your release.
- It cannot be verified here for `SNMPv3Credentials` specifically, so treat this URI form as unverified.
**[There is no node-level AssignToEngine verb in 2026.2](../automation/node-management.md#there-is-no-node-level-assigntoengine-verb-in-20262)**

- Searching the verb data for `AssignToEngine` returns `Orion.AgentManagement.Agent.AssignToEngine(agentId, pollerId)`, which moves an *agent*, and a set of `Core.AssignToEngine` verbs on `Cortex.*` entities including `Cortex.Orion.Node`, whose parameter lists are **not recorded in the published schema** and which require the `admin` right.
- Because their signatures cannot be verified here, do not call them from a script on the strength of this page; if you want to know what your server exposes, ask it:
**[Deleting a node](../automation/node-management.md#deleting-a-node)**

- This page does not enumerate exactly which child rows go: that is runtime behaviour and it cannot be verified from the schema.

## [pollers.md](../automation/pollers.md)

**[Nodes: the list resources job](../automation/pollers.md#nodes-the-list-resources-job)**

- And the tree it manipulates is XML whose element and display names are runtime data rather than schema, so the exact `DisplayName` values are **not verified here**; dump `$results` once for the device family you are automating and read the names off it.

## [agents.md](../modules/agents.md)

**[Namespaces and how many entities](../modules/agents.md#namespaces-and-how-many-entities)**

- Whether a query against one of those indication entities returns historical rows, or nothing at all because indications are transient, is **not recorded in the published schema** and is not verified here.
**[The two status columns, and why they disagree with each other](../modules/agents.md#the-two-status-columns-and-why-they-disagree-with-each-other)**

- Which of the two is right for your release **cannot be verified here**, because the Swagger enum is declared as a string enum and does not carry the integers.
**[Plugins](../modules/agents.md#plugins)**

- The `Status` integers for a plugin are **not documented in the published schema** and are not verified here; read `StatusMessage` alongside the number and build the mapping for your release with the same `GROUP BY` shape shown above.
**[1. Deploy](../modules/agents.md#1-deploy)**

- What the integer identifies is **not documented in the published schema**, so this page does not assert that it is the new `AgentId`.
**[Validate credentials before you deploy](../modules/agents.md#validate-credentials-before-you-deploy)**

- The two enums' members are not published in the schema or the Swagger contract and are **not verified here**; the boolean and the string are the parts to act on.
**[2. Connect](../modules/agents.md#2-connect)**

- The `agentPort` value above is an example, not a documented default: the port a passive agent listens on is installation configuration and is **not recorded in the published schema**.
**[4. Move, or remove](../modules/agents.md#4-move-or-remove)**

- What it does to an agent, and whether it is reversible, is **not documented in the published schema** and is not verified here.
**[The verbs, in full](../modules/agents.md#the-verbs-in-full)**

- What the platform does with an agent row written that way, as opposed to one produced by `Deploy` or `AddAgent`, is **not documented in the published schema** and is not verified here.

## [cloud.md](../modules/cloud.md)

**[Tag filters and resource tags are different entities](../modules/cloud.md#tag-filters-and-resource-tags-are-different-entities)**

- For an EC2 instance the obvious candidate is `Orion.Cloud.Instances.InstanceId`, which is also a `System.String`, but the schema does not declare that correspondence and the exact format of `ResourceId` per provider is **unverified here**.
**[The `Local.` entities in the CRUD surface](../modules/cloud.md#the-local-entities-in-the-crud-surface)**

- That reading is unverified.
**[Adding AWS accounts in bulk](../modules/cloud.md#adding-aws-accounts-in-bulk)**

- It appears neither in the rendered schema for 2026.2 nor in the Swagger contract for 2026.2, both of which this repository extracts from, so it is **not verified here**.
**[What is not verified here](../modules/cloud.md#what-is-not-verified-here)**

- ## What is not verified here

## [dpa.md](../modules/dpa.md)

**[2. Which databases are alarming, and on what](../modules/dpa.md#2-which-databases-are-alarming-and-on-what)**

- `WaitTimeCategory` runs -1 to 10 with DOWN(-1) and IDLE(0) at the bottom; the schema description is truncated in the extracted data, so the meaning of the upper values is **unverified** here.
**[What is not verified here](../modules/dpa.md#what-is-not-verified-here)**

- ## What is not verified here

## [hardware-health.md](../modules/hardware-health.md)

**[Enabling and disabling individual sensors](../modules/hardware-health.md#enabling-and-disabling-individual-sensors)**

- The shape of that key object is not described in the schema or the Swagger contract, so *the exact structure to pass is unverified here.* `Metadata.VerbArgument` on your own server carries an `XmlTemplate` column that shows the shape SWIS expects for complex arguments, which is the reliable way to find out:

## [ipam.md](../modules/ipam.md)

**[Just looking, not claiming](../modules/ipam.md#just-looking-not-claiming)**

- It appears in the rendered schema pages with **no parameters and an unknown return type**, and it is absent from the 2026.2 Swagger contract entirely, so its signature is **unverified here**.
**[DHCP and DNS server management](../modules/ipam.md#dhcp-and-dns-server-management)**

- Treat the `credentials` and `propertiesToUpdate` key/value arrays as unverified in content and inspect `Metadata.VerbArgument.XmlTemplate` on your own server for the keys they expect.

## [log-analyzer.md](../modules/log-analyzer.md)

**[Verbs](../modules/log-analyzer.md#verbs)**

- The three `Orion.OLM.LogEntry` verbs are all documented as "For internal use only." Their names and signatures are consistent with `LogEntryID` encoding a timestamp, so that a date range can be turned into an id range without touching the `DateTime` column, but that is an inference from the names and is **not verified**.
**[What is not verified here](../modules/log-analyzer.md#what-is-not-verified-here)**

- ## What is not verified here

## [ncm.md](../modules/ncm.md)

**[Gotchas](../modules/ncm.md#gotchas)**

- Whether `ClearTransfers` is present but undocumented on a given server is **unverified here**; check with `SELECT VerbName FROM Metadata.Verb WHERE EntityName = 'Cirrus.ConfigArchive' ORDER BY VerbName`.

## [npm.md](../modules/npm.md)

**[Gotchas](../modules/npm.md#gotchas)**

- Whether the `Base` entities are present but undocumented on a live server is unverified here; check with `SELECT FullName FROM Metadata.Entity WHERE FullName LIKE 'Orion.NetPath.%'`.

## [nta.md](../modules/nta.md)

**[Lookup entities](../modules/nta.md#lookup-entities)**

- `Multiport` and `MapTo` on `Orion.Netflow.Applications` carry no description in the published schema, so their semantics are **unverified** here.
**[`Orion.Netflow.InterfaceSources`](../modules/nta.md#orionnetflowinterfacesources)**

- Its `FlowExporterConfiguration` type is declared in SolarWinds' Swagger contract as a bare object with **no properties**, so the field names it expects are **unverified**.
**[Gotchas](../modules/nta.md#gotchas)**

- Whether verbs exist there on a live server is **unverified**; check with `SELECT v.Entity.FullName, v.Name FROM Metadata.Verb v WHERE v.Entity.FullName LIKE 'Orion.Netflow.%'`.

## [qoe.md](../modules/qoe.md)

**[Applications are the centre of the model](../modules/qoe.md#applications-are-the-centre-of-the-model)**

- `Filter` is the expression that matches traffic to this application and `FilterSyntax` presumably names the dialect it is written in, but neither carries a description in the schema, so the exact grammar is **unverified** here.
**[The catalogue behind an application](../modules/qoe.md#the-catalogue-behind-an-application)**

- `IsVisible` on the protocol likewise has no description, so what a `FALSE` there suppresses is unverified.
**[Probes](../modules/qoe.md#probes)**

- The schema does not say what distinguishes a setting from a property, and no valid names are enumerated, so both are **unverified** in content.
- Given that the two deployment verbs are `DeployLocalTrafficProbe` and `DeploySpanPortProbe`, it is a reasonable guess that `Mode` distinguishes those two deployment styles, but that is an inference and is **not verified** by the schema.
**[What is not verified here](../modules/qoe.md#what-is-not-verified-here)**

- ## What is not verified here

## [sam.md](../modules/sam.md)

**[Gotchas](../modules/sam.md#gotchas)**

- This behaviour is unverified here*: neither the schema nor the contract records it.
- This verb is not in the extracted 2026.2 schema and not in the Swagger contract*, so it is unverified here.

## [vnqm.md](../modules/vnqm.md)

**[IP SLA operations](../modules/vnqm.md#ip-sla-operations)**

- None of the three carries a description in the schema, so the readings of `LifeTimeUtc` and `IsAutoConfigured` given here are inferences and are listed in [what is not verified here](#what-is-not-verified-here).
**[MOS, jitter and the other quality metrics](../modules/vnqm.md#mos-jitter-and-the-other-quality-metrics)**

- They are listed in [what is not verified here](#what-is-not-verified-here) with a query that shows you the observed range on your own server.
**[What is not verified here](../modules/vnqm.md#what-is-not-verified-here)**

- ## What is not verified here

## [wpm.md](../modules/wpm.md)

**[What is not verified here](../modules/wpm.md#what-is-not-verified-here)**

- ## What is not verified here

## [entity-model.md](../schema/entity-model.md)

**[The tree is rooted at System.Entity](../schema/entity-model.md#the-tree-is-rooted-at-systementity)**

- Treat it as unverified.

## [key-entities.md](../schema/key-entities.md)

**[Orion.AlertStatus](../schema/key-entities.md#orionalertstatus)**

- Their signatures are **unverified**, so confirm them on your own server with `Metadata.VerbArgument` before calling them.

## [netobject-types.md](../schema/netobject-types.md)

**[Entries that no longer resolve in 2026.2](../schema/netobject-types.md#entries-that-no-longer-resolve-in-20262)**

- Which of the two applies cannot be verified from the schema alone, so ask your own server before concluding they are gone:

## [status-codes.md](../schema/status-codes.md)

**[Resolving status on a live server](../schema/status-codes.md#resolving-status-on-a-live-server)**

- The published 2026.2 schema gives no summary text for any of these twelve, so the names and types above are verified but their meanings beyond the obvious are unverified.
**[`Status` versus `PolledStatus`](../schema/status-codes.md#status-versus-polledstatus)**

- How the two differ is **not verified**: the published 2026.2 schema attaches no summary text to either property, and neither the OrionSDK documentation nor any SolarWinds sample script in this repository's sources explains it.

## [uris.md](../swis/uris.md)

**[The key filter](../swis/uris.md#the-key-filter)**

- That sourcing matters because *which* properties make up an entity's key is **not recorded in the published schema** that this repository extracts, so the composite key sets above cannot be verified here.

## [date-and-time.md](../swql/date-and-time.md)

**[`DateTime` literals and parameters](../swql/date-and-time.md#datetime-literals-and-parameters)**

- If you must use a literal, the ISO 8601 form `'2026-01-01T00:00:00'` is the conventional choice for unambiguity, but its acceptance by SWIS is **unverified** here: no published SolarWinds example uses it.

## [functions.md](../swql/functions.md)

**[`UNION(q)`](../swql/functions.md#unionq)**

- `UNION ALL` is **unverified**: only `UNION` is documented.
**[`ChangeTimeZone` is not in the official reference](../swql/functions.md#changetimezone-is-not-in-the-official-reference)**

- Treat it as unverified.

## [gotchas.md](../swql/gotchas.md)

**[SWQL gotchas](../swql/gotchas.md#swql-gotchas)**

- Where something is widely believed but could not be verified from the schema, the official docs or SolarWinds' own samples, it is marked **unverified** and comes with a query you can run on your own server to settle it.
**[1. The empty result set is usually a permissions answer](../swql/gotchas.md#1-the-empty-result-set-is-usually-a-permissions-answer)**

- The schema publishes no summary for either, so what exactly `IsSwisLimitation` gates is **unverified** here; the name and the surrounding entity make it the first thing to look at when a limitation appears to affect the web console but not an API query.
**[6. To-many navigation multiplies rows and poisons aggregates](../swql/gotchas.md#6-to-many-navigation-multiplies-rows-and-poisons-aggregates)**

- Two counts rather than one because `Count(n)` is the only counting signature in SolarWinds' [documented function reference](https://solarwinds.github.io/OrionSDK/docs/swql-functions/); `COUNT(DISTINCT column)` is standard T-SQL and may well work, but it is **unverified** here.

## [language-reference.md](../swql/language-reference.md)

**[How this page marks its evidence](../swql/language-reference.md#how-this-page-marks-its-evidence)**

- Where a construct could not be corroborated at all, it is marked **unverified** with a one-line note on how to confirm it on your own server rather than being quietly dropped or quietly asserted.
**[UNION](../swql/language-reference.md#union)**

- `UNION ALL` is unverified.** The official reference documents only `UNION`.
**[CASE](../swql/language-reference.md#case)**

- Whether the simple form, `CASE Severity WHEN 2 THEN ...`, is also accepted **is unverified here**.

## [performance.md](../swql/performance.md)

**[9. Bind parameters instead of building query text](../swql/performance.md#9-bind-parameters-instead-of-building-query-text)**

- Whether SWIS actually reuses a plan across executions of the same parameterised query is **unverified** here; you can test it on your own server by running the same query with different parameter values and comparing the timings reported by `WITH QUERYSTATS`. 3.

---

An entry here is not a defect. It is a statement that a reader should confirm before depending on it, and that this repository declines to guess about.

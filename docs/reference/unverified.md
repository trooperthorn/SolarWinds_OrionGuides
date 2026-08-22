<!-- GENERATED FILE. Do not edit by hand.
     Produced by tools/build_unverified_index.py from the documentation itself.
     Regenerate with: make docs-reference -->

# What this repository does not verify

Everything in these guides was checked against the extracted SolarWinds schema before it was written, and every SWQL statement is re-checked on each build. Some things cannot be checked that way: behaviour that only a running server exhibits, values that are installation data rather than schema, and the handful of places where SolarWinds' own documentation and their published contract disagree.

The rule is that those say so rather than being asserted quietly or dropped. This page collects every such statement in one place, because an admission is in the right place on its page and the wrong place when you want the whole picture.

**230 statements across 62 pages.**

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

**[What is not verified here](../automation/alerts.md#what-is-not-verified-here)**

- ## What is not verified here

## [credential-integration.md](../automation/credential-integration.md)

**[`Orion.CredentialRelation` is the mechanism nobody mentions](../automation/credential-integration.md#orioncredentialrelation-is-the-mechanism-nobody-mentions)**

- **What values `EntityType` and `Use` take is not recorded in the schema and is unverified here.** Read the existing rows on your own server before writing new ones — the table is generic enough that a wrong `Use` string is accepted and does nothing.

**[IPAM has its own creation path and its own spelling](../automation/credential-integration.md#ipam-has-its-own-creation-path-and-its-own-spelling)**

- **Which id space `credentialId` belongs to — the shared store or an IPAM-local one — is not stated in the schema and is unverified here.** The width matches `Orion.Credential.ID`, which is suggestive and not proof.

**[The contract type and the entity disagree](../automation/credential-integration.md#the-contract-type-and-the-entity-disagree)**

- Reading it means a verb call per credential — `Orion.SRM.BusinessLayer.GetCredential` is one path, though whether it reports the flag for credentials SRM did not create is **unverified here**.

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

## [dependencies.md](../automation/dependencies.md)

**[How a dependency is expressed](../automation/dependencies.md#how-a-dependency-is-expressed)**

- What the `Category` integer classifies is **not recorded in the published schema** and is unverified here.

**[How automatic discovery is scoped](../automation/dependencies.md#how-automatic-discovery-is-scoped)**

- The precise algorithm that selects a root, and what the counts are used for once calculated, are **not recorded in the published schema** and are unverified here.

## [discovery.md](../automation/discovery.md)

**[Phase 1b: the interfaces plugin configuration](../automation/discovery.md#phase-1b-the-interfaces-plugin-configuration)**

- `AutoImportExpressionFilter` is present in the 2026.2 contract with members `Prop`, `Op` and `Val`, but no accepted property names or operators are documented and no sample uses it, so **its usage is unverified here**.

**[Importing a staged discovery](../automation/discovery.md#importing-a-staged-discovery)**

- **The semantics of `SelectedDiscoveredResources` are unverified here.**

**[Checking a credential before you scan with it](../automation/discovery.md#checking-a-credential-before-you-scan-with-it)**

- **The keys it expects are not described in the schema or the Swagger contract**, and no SDK sample calls this verb, so the content is unverified here.

**[List Resources on an address that is not a node yet](../automation/discovery.md#list-resources-on-an-address-that-is-not-a-node-yet)**

- **Both are unverified here.** Check `Metadata.VerbArgument.XmlTemplate` on your own server.

**[What is not verified here](../automation/discovery.md#what-is-not-verified-here)**

- ## What is not verified here

## [events-and-auditing.md](../automation/events-and-auditing.md)

**[Down and back up, in one row](../automation/events-and-auditing.md#down-and-back-up-in-one-row)**

- The timezone of `DateTimeFrom` is not documented in the schema, so measure it the same way before building a report on it.

**[What is not verified here](../automation/events-and-auditing.md#what-is-not-verified-here)**

- ## What is not verified here

## [high-availability.md](../automation/high-availability.md)

**[High availability](../automation/high-availability.md#high-availability)**

- `Orion.HA.ResourcesInstances` and `Orion.HA.PoolMemberInterfacesInfo` do declare CRUD under `admin`, but they are the mechanism's own bookkeeping rather than a supported way to configure anything; what the platform does with a row written directly into either is **not documented in the published schema** and is not verified here.

**[The pool](../automation/high-availability.md#the-pool)**

- The value set behind `CurrentStatus` is **not documented in the published schema**, so treat the integer as opaque and compare pools against each other rather than against a hard-coded number.

**[Pool members](../automation/high-availability.md#pool-members)**

- `Status`, `PreferredStatus` and `RepairStatus` are integers whose value sets are **not documented in the published schema**.
- This page follows that lead in query 2, but treat the mapping as **unverified**: confirm on your own server by reading the number next to `StatusMessage` before you build an alert on a specific value.

**[The result object](../automation/high-availability.md#the-result-object)**

- Read `Message` and treat `ErrorMessage` as **unverified**; if you want to know what your server returns, print the whole object once with `$result.InnerXml`.

**[The `properties` argument](../automation/high-availability.md#the-properties-argument)**

- One of them is wrong, and which one **cannot be verified here**.

**[Safe in a controlled window, with a human deciding](../automation/high-availability.md#safe-in-a-controlled-window-with-a-human-deciding)**

- The schema records **no description** for this verb, so its exact semantics when the two arrays are different lengths, or when a target is not in the same pool, are **not documented in the published schema** and are not verified here.
- What it repairs, and whether it is disruptive, is **not documented in the published schema**.

**[Gotchas](../automation/high-availability.md#gotchas)**

- Which one the server accepts cannot be verified here; find out with `ValidateEditPool` before running the real call.
- SolarWinds' sample joins `Orion.StatusInfo` on member `Status`, which is suggestive but is unverified here.
- **`SelectiveSwitchover` and `RepairPool` have no schema descriptions**, so their exact behaviour is not documented in the published schema and is not verified here.

## [maintenance-mode.md](../automation/maintenance-mode.md)

**[Recipe: bulk unmanage driven by a query](../automation/maintenance-mode.md#recipe-bulk-unmanage-driven-by-a-query)**

- Whether unmanaging a node also flags its interfaces, volumes and applications as unmanaged in their own right is runtime behaviour, not something the schema records, so it is **unverified here**.

## [node-management.md](../automation/node-management.md)

**[The properties to set on create](../automation/node-management.md#the-properties-to-set-on-create)**

- Which properties are required on create is **not recorded in the published schema**, and the Swagger contract does not mark them either, so the honest statement is: the set below is what SolarWinds' own [`CRUD.AddNode.ps1`](https://github.com/solarwinds/OrionSDK/blob/master/Samples/PowerShell/CRUD.AddNode.ps1) sample sets, and every name in it is a real `Orion.Nodes` property in 2026.2.

**[The pollers](../automation/node-management.md#the-pollers)**

- **The two "no" rows are unverified here.** They come from the sample scripts rather than from the reference.

**[SNMPv3](../automation/node-management.md#snmpv3)**

- The accepted values for `AuthenticationMethod` and `PrivacyMethod` are not recorded in the published schema; the sample script names `None`, `MD5` and `SHA1` for authentication and `None`, `DES56`, `AES128`, `AES192` and `AES256` for privacy, which is worth treating as indicative rather than authoritative for your release.
- It cannot be verified here for `SNMPv3Credentials` specifically, so treat this URI form as unverified.

**[There is no node-level AssignToEngine verb in 2026.2](../automation/node-management.md#there-is-no-node-level-assigntoengine-verb-in-20262)**

- Searching the verb data for `AssignToEngine` returns `Orion.AgentManagement.Agent.AssignToEngine(agentId, pollerId)`, which moves an *agent*, and a set of `Core.AssignToEngine` verbs on `Cortex.*` entities including `Cortex.Orion.Node`, whose parameter lists are **not recorded in the published schema** and which require the `admin` right.
- Because their signatures cannot be verified here, do not call them from a script on the strength of this page; if you want to know what your server exposes, ask it:

**[Deleting a node](../automation/node-management.md#deleting-a-node)**

- This page does not enumerate exactly which child rows go: that is runtime behaviour and it cannot be verified from the schema.

## [report-definitions.md](../automation/report-definitions.md)

**[`DataSources` — three ways to choose rows](../automation/report-definitions.md#datasources-three-ways-to-choose-rows)**

- What it governs when the query is arbitrary is **not documented and unverified here**; the plausible reading is that it supplies the account-limitation context, which would make it security-relevant rather than cosmetic.

**[`WebResourceConfiguration` is a console resource in a report](../automation/report-definitions.md#webresourceconfiguration-is-a-console-resource-in-a-report)**

- **That a `ResourceFile` valid on a view is valid in a report is the obvious reading and is unverified here.** The three in the samples — `XuiWrapper.ascx`, `NodeChart.ascx` and `WorldMapView.ascx` — are certainly usable; whether an arbitrary resource works, and which `Settings` each expects, is not documented anywhere this repository has seen.
- The full set of selectors and toggles is **not documented and unverified here**.

**[`DataTypeInfo` — the field picker's metadata](../automation/report-definitions.md#datatypeinfo-the-field-pickers-metadata)**

- The complete set is **not documented and unverified here**.

**[Presenters and transforms](../automation/report-definitions.md#presenters-and-transforms)**

- The full presenter list is **not documented and unverified here**.

**[Header, footer, timeframes](../automation/report-definitions.md#header-footer-timeframes)**

- The set of valid `NamedTimeFrame` values, and the shape of `Static` for an absolute range, are **not documented and unverified here**.

**[Importing a definition that is already there](../automation/report-definitions.md#importing-a-definition-that-is-already-there)**

- **What `CreateReport` does in the same situation is a narrower question, still unverified here.** The verb is a different entry point from the console's import, and it takes `name`, `description`, `category`, `title` and `subtitle` as **arguments alongside** the `definition` document, which contains all five again as elements.

## [reporting.md](../automation/reporting.md)

**[Reports and scheduled exports](../automation/reporting.md#reports-and-scheduled-exports)**

- The report entities are queryable and are worth understanding for inventory and audit, but their `Definition` is an opaque serialisation that this repository cannot verify, so building a report by writing that string is not something to attempt from a script.

**[Report schedules are not `Orion.ScheduleTaskDefinition`](../automation/reporting.md#report-schedules-are-not-orionscheduletaskdefinition)**

- Whether a particular release also surfaces report jobs as rows in `Orion.ScheduleTaskDefinition` is unverified here.

**[`Orion.Reporting.ExecuteSQL`](../automation/reporting.md#orionreportingexecutesql)**

- Whether account limitations are applied to its results is not recorded in the schema and is unverified here, which is another reason to prefer SWQL: with SWQL you know limitations apply, and can reason about it.

**[Practical constraints](../automation/reporting.md#practical-constraints)**

- `Orion.AlertHistory.TimeStamp` and `Orion.ResponseTime.DateTime` carry **no documented timezone** and are unverified here, so measure them once on your own server with the `MinuteDiff` probe in [../swql/date-and-time.md](../swql/date-and-time.md#measuring-a-columns-timezone) before you write a narrow window against either.

**[Alert volume by definition](../automation/reporting.md#alert-volume-by-definition)**

- The parameters are named for UTC because that is the usual answer, but `ah.TimeStamp` carries **no documented timezone** in the schema and its name does not end in `Utc`, so this is unverified here: settle it on your own server with the `MinuteDiff` probe in [alerts.md](../automation/alerts.md#the-timezone-caveat-on-timestamp) before trusting a month boundary, and drop the `Utc` suffixes if the column turns...

**[The report inventory itself](../automation/reporting.md#the-report-inventory-itself)**

- The schema types it `System.String` rather than a number or an interval, and what that string contains is not recorded and is unverified here, so read a few values before you sort on it and expect lexicographic order rather than numeric if you do.

## [scheduling.md](../automation/scheduling.md)

**[A cron expression without its timezone is ambiguous](../automation/scheduling.md#a-cron-expression-without-its-timezone-is-ambiguous)**

- What `ScheduleCondition` may contain is **not recorded in the published schema** and is unverified here.

## [building-integrations.md](../guides/building-integrations.md)

**[3. Authentication and secret handling](../guides/building-integrations.md#3-authentication-and-secret-handling)**

- What it is valid for and for how long is not recorded in the published schema and is unverified here; confirm the behaviour on your own server before building anything on it.

**[Incremental sync beats a full pass](../guides/building-integrations.md#incremental-sync-beats-a-full-pass)**

- Whether `EventID` values are always allocated in ascending order is not recorded in the published schema, so treat any watermarked feed as at-least-once: make the downstream write idempotent, and confirm the ordering on your own server by comparing `EventID` against `EventTime` over a busy period before you rely on it for anything you cannot reconcile later.

**[Which operations survive being repeated](../guides/building-integrations.md#which-operations-survive-being-repeated)**

- CRUD delete, `BulkDelete` — Unverified — Whether a second delete of an already-deleted URI errors or succeeds quietly is not recorded in the published schema. Test it on your own server before relying on either
- `Orion.AlertActive.Acknowledge(alertObjectIds, notes)` — Unverified — Whether re-acknowledging an acknowledged alert is a no-op or an error is not recorded in the published schema; confirm on your own server

**[Ask the schema the question you actually have](../guides/building-integrations.md#ask-the-schema-the-question-you-actually-have)**

- The row values themselves are installation data: which row corresponds to the platform core, and how its `Version` string relates to the release number, are not recorded in the published schema and are unverified here.

## [cookbook.md](../guides/cookbook.md)

**[Rules these queries follow](../guides/cookbook.md#rules-these-queries-follow)**

- Most other date columns, including `Orion.AlertActive.TriggeredDateTime`, `Orion.AlertHistory.TimeStamp` and `Cirrus.ConfigArchive.DownloadTime`, carry **no documented timezone in the schema and are unverified here**: measure them once on your own server with the `MinuteDiff` probe in [../swql/date-and-time.md](../swql/date-and-time.md#measuring-a-columns-timezone) before writing a narrow windo...

**[19. Which interfaces are running hot?](../guides/cookbook.md#19-which-interfaces-are-running-hot)**

- How `Orion.NPM.Interfaces.PercentUtil` combines `InPercentUtil` and `OutPercentUtil` is **not documented in the schema and is unverified here**: the commonly repeated answer is the higher of the two, and selecting all three columns on a link that is busy in one direction only settles it on your own server in one query.

**[31. What is unacknowledged and old?](../guides/cookbook.md#31-what-is-unacknowledged-and-old)**

- The triage list, with the age computed both ways because `Orion.AlertActive.TriggeredDateTime` carries no documented timezone in the schema and is therefore unverified here.

**[49. Which accounts see less than the whole estate?](../guides/cookbook.md#49-which-accounts-see-less-than-the-whole-estate)**

- `IsNull(column, 0) <> 0` because whether an unused slot holds `0` or `NULL` is not recorded in the schema; written this way the query is correct either way.

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

- **That reading is unverified.**

**[Adding AWS accounts in bulk](../modules/cloud.md#adding-aws-accounts-in-bulk)**

- It appears neither in the rendered schema for 2026.2 nor in the Swagger contract for 2026.2, both of which this repository extracts from, so it is **not verified here**.

**[What is not verified here](../modules/cloud.md#what-is-not-verified-here)**

- ## What is not verified here

## [dpa.md](../modules/dpa.md)

**[The wait-time entities](../modules/dpa.md#the-wait-time-entities)**

- See the names in NormalizedDataDimension class." That class is not in the extracted data, so treat the exact strings as **unverified** and read them off your own server before hard-coding one:

**[What is not verified here](../modules/dpa.md#what-is-not-verified-here)**

- ## What is not verified here

## [hardware-health.md](../modules/hardware-health.md)

**[Enabling and disabling individual sensors](../modules/hardware-health.md#enabling-and-disabling-individual-sensors)**

- The shape of that key object is not described in the schema or the Swagger contract, so *the exact structure to pass is unverified here.* `Metadata.VerbArgument` on your own server carries an `XmlTemplate` column that shows the shape SWIS expects for complex arguments, which is the reliable way to find out:

## [ipam.md](../modules/ipam.md)

**[The status values, and how to find out what the numbers are](../modules/ipam.md#the-status-values-and-how-to-find-out-what-the-numbers-are)**

- That is consistent across the file but it is **not verified against 2026.2 schema documentation**; run the query above before you rely on it.

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

- Whether `ClearTransfers` is present but undocumented on a given server is **unverified here**; check with `SELECT Name FROM Metadata.Verb WHERE Entity.FullName = 'Cirrus.ConfigArchive' ORDER BY Name`.

## [npm.md](../modules/npm.md)

**[Wireless](../modules/npm.md#wireless)**

- Which of the other three are deprecated, and in which release, is **not recorded in the published schema**: none of these entities carries a summary, and none is marked obsolete.

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

## [sam-templates.md](../modules/sam-templates.md)

**[The root is an array](../modules/sam-templates.md#the-root-is-an-array)**

- Whether `ImportTemplate` accepts a document with more than one `ApplicationTemplate`, and what it returns if it does — the verb's return type is a single `number` — is **not documented and unverified here**.

**[Settings are a typed key/value map](../modules/sam-templates.md#settings-are-a-typed-keyvalue-map)**

- That the value can be anything else is an inference from the name and is **unverified here**.

**[Components](../modules/sam-templates.md#components)**

- `EvidenceType`, `CategoryDisplayName` and `ApplicationItemType` are `None` and `VisibilityMode` is `Visible` on **all 67 components** in the three samples; their other legal values are **not documented and unverified here**.

**[Thresholds](../modules/sam-templates.md#thresholds)**

- Its syntax is **not documented and unverified here**.

**[Moving a template between servers](../modules/sam-templates.md#moving-a-template-between-servers)**

- Whether `ImportTemplate` rejects, replaces or duplicates a template whose `UniqueId` already exists is **not documented and unverified here**.

## [sam.md](../modules/sam.md)

**[Gotchas](../modules/sam.md#gotchas)**

- *This behaviour is unverified here*: neither the schema nor the contract records it.
- *This verb is not in the extracted 2026.2 schema and not in the Swagger contract*, so it is unverified here.

## [srm.md](../modules/srm.md)

**[Providers](../modules/srm.md#providers)**

- **Unverified:** treat their values as opaque until you have confirmed them on your own server.

**[Pools](../modules/srm.md#pools)**

- **Unverified:** `Type` and `Category` are integers whose enumerations are not in the extracted schema; select `DISTINCT` on your own array before filtering on them.

**[Thresholds](../modules/srm.md#thresholds)**

- **Unverified:** the schema does not say what "application" means in that name; check for rows on your own server before building on it.

## [vman.md](../modules/vman.md)

**[Hosts, clusters, datacenters and vCenters](../modules/vman.md#hosts-clusters-datacenters-and-vcenters)**

- **Unverified:** `PollingTaskTypeID` is an integer whose enumeration is not in the extracted schema, so select `DISTINCT` on your own server before filtering on a specific value.

**[Alarms](../modules/vman.md#alarms)**

- **Unverified:** `AcknowledgedTime` sits beside them but its summary names no zone, so do not assume it matches; acknowledge an alarm at a known wall-clock time on your own server and read the column back before comparing it to either function.

**[The virtual machine verbs change production state](../modules/vman.md#the-virtual-machine-verbs-change-production-state)**

- `storageDestination` is a string and is optional; the schema does not record what form it takes, so **unverified**: confirm against your own server before relying on it, for example by checking the argument type in `Metadata.VerbArgument`.

**[Discovery verbs](../modules/vman.md#discovery-verbs)**

- **Unverified:** whether `CreateDiscoveryJob` accepts 6 in practice.

**[Elsewhere](../modules/vman.md#elsewhere)**

- **Unverified:** the extracted schema records no parameters for any of them, so read the signature from `Metadata.VerbArgument` on your own server before calling one.

**[Orphaned files on datastores](../modules/vman.md#orphaned-files-on-datastores)**

- **Unverified:** the schema documents the column but not the rule behind it.

**[Gotchas](../modules/vman.md#gotchas)**

- **Unverified:** whether a live server resolves it anyway by matching case-insensitively.

## [vnqm.md](../modules/vnqm.md)

**[IP SLA operations](../modules/vnqm.md#ip-sla-operations)**

- None of the three carries a description in the schema, so the readings of `LifeTimeUtc` and `IsAutoConfigured` given here are inferences and are listed in [what is not verified here](../modules/vnqm.md#what-is-not-verified-here).

**[Two different status columns on the same row](../modules/vnqm.md#two-different-status-columns-on-the-same-row)**

- The specific integers each lookup contains are not recorded in the schema, so enumerate them on your own server rather than hard-coding a number.

**[MOS, jitter and the other quality metrics](../modules/vnqm.md#mos-jitter-and-the-other-quality-metrics)**

- They are listed in [what is not verified here](../modules/vnqm.md#what-is-not-verified-here) with a query that shows you the observed range on your own server.

**[What is not verified here](../modules/vnqm.md#what-is-not-verified-here)**

- ## What is not verified here

## [wpm.md](../modules/wpm.md)

**[What is not verified here](../modules/wpm.md#what-is-not-verified-here)**

- ## What is not verified here

## [modules.md](../platform/modules.md)

**[DPA: Database Performance Analyzer](../platform/modules.md#dpa-database-performance-analyzer)**

- Whether SWIS classifies them as federated entities is not recorded in the extracted schema; that claim is unverified here.

## [api-pollers.md](../polling/api-pollers.md)

**[The poller](../polling/api-pollers.md#the-poller)**

- `LastPollTimestamp` carries **no documented timezone** in the schema and its name does not end in `Utc`, so this is unverified here: settle it with the `MinuteDiff` probe in [../swql/date-and-time.md](../swql/date-and-time.md#measuring-a-columns-timezone) before trusting a narrow window.

**[The request](../polling/api-pollers.md#the-request)**

- Whether the platform redacts any header value on read is not recorded in the schema and is unverified here; assume it does not.

**[The metric](../polling/api-pollers.md#the-metric)**

- What syntax `Path` uses, and what values `Type` and `ThresholdRule` accept, are **not recorded in the published schema** and are unverified here — read existing rows on your own server before writing new ones.

**[The verbs](../polling/api-pollers.md#the-verbs)**

- **What belongs in which is not recorded in the published schema** and is unverified here.

**[Element by element, against the schema](../polling/api-pollers.md#element-by-element-against-the-schema)**

- Whether those two arrays are the only route, and which keys they accept, is **not documented and unverified here**.

**[Writing one by hand](../polling/api-pollers.md#writing-one-by-hand)**

- What the platform does on import when the GUID already exists — replace, duplicate or reject — is **not documented and unverified here**.

**[Choosing the fallback](../polling/api-pollers.md#choosing-the-fallback)**

- Whether matching is case-sensitive, trims surrounding whitespace, or supports any wildcard is **not documented and unverified here**.

**[The threshold boundary](../polling/api-pollers.md#the-threshold-boundary)**

- Whether the comparison is strict — whether a mapped value exactly equal to `WarningThresholdValue` reads as Warning or as Up — is **not documented and unverified here**, and it matters when the mapped values are small ordinals, because one step in either direction is the difference between two status levels.

## [device-studio.md](../polling/device-studio.md)

**[The poller definitions](../polling/device-studio.md#the-poller-definitions)**

- What the ordering means when two share a priority is **not recorded in the published schema** and is unverified here.

**[`TechnologyID` is a GUID here and a string elsewhere](../polling/device-studio.md#technologyid-is-a-guid-here-and-a-string-elsewhere)**

- Whether every Device Studio poller has a matching `Orion.TechnologyPolling` row, or only those built on a technology the platform also polls declaratively, is **not recorded in the schema** and is unverified here.

## [node-status-calculation.md](../polling/node-status-calculation.md)

**[2. Polling errors, independent of ICMP](../polling/node-status-calculation.md#2-polling-errors-independent-of-icmp)**

- That it is the flag behind this feature is the obvious reading of the name and is **unverified here** — confirm by breaking a test node's SNMP credential and watching the column.

**[Which contributors are switched on](../polling/node-status-calculation.md#which-contributors-are-switched-on)**

- Whether writing `Enabled` takes effect without a service restart is **not documented and unverified here**; change one on a test server and watch a node's status before you roll it out.

**[The Mixed truth table](../polling/node-status-calculation.md#the-mixed-truth-table)**

- The behaviour of combinations it does not enumerate — more than two children, or children the table does not pair — is **not documented and unverified here**.

**[Where the mode is stored](../polling/node-status-calculation.md#where-the-mode-is-stored)**

- `Orion.Nodes` declares no rollup-mode property in 2026.2, so the per-node setting is **not readable from `Orion.Nodes`** and where it lives is **unverified here**.

**[Classic calculation, and what child status means there](../polling/node-status-calculation.md#classic-calculation-and-what-child-status-means-there)**

- That the setting governs the column is the reading these two documents support and is **unverified here** in the sense that no SolarWinds page states the connection in those words.

## [standard-pollers.md](../polling/standard-pollers.md)

**[Interfaces: discover, then add with default pollers](../polling/standard-pollers.md#interfaces-discover-then-add-with-default-pollers)**

- The exact shape the verb result takes when it comes back through `Invoke-SwisVerb` is a serialisation detail of the PowerShell client rather than a schema fact, and it is **not verified here**; inspect `$discovered` once interactively before writing the filter, and adjust the property path.

**[Nodes: the list resources job](../polling/standard-pollers.md#nodes-the-list-resources-job)**

- And the tree it manipulates is XML whose element and display names are runtime data rather than schema, so the exact `DisplayName` values are **not verified here**; dump `$results` once for the device family you are automating and read the names off it.

**[Polling parameters](../polling/standard-pollers.md#polling-parameters)**

- **`StatCollection`'s default is not recorded in the published schema** and is not verified here; read it off an existing object before you assume one.
- The individual `SettingID` values are installation data rather than schema, and they are **not recorded in the published schema**.

## [technology-polling.md](../polling/technology-polling.md)

**[What technologies exist](../polling/technology-polling.md#what-technologies-exist)**

- What happens when two share a priority is **not recorded in the published schema** and is unverified here.

**[What it is assigned to](../polling/technology-polling.md#what-it-is-assigned-to)**

- Whether `TargetEntity` on the assignment always matches `TargetEntity` on the technology above it, and whether a third target beyond nodes and volumes can appear, are **not recorded in the schema** and are unverified here.

**[The four verbs](../polling/technology-polling.md#the-four-verbs)**

- What the returned array contains is **not recorded in the published schema** and is unverified here.

**[`clientSettings` is the whole configuration](../polling/technology-polling.md#clientsettings-is-the-whole-configuration)**

- And `CredentialID` appears here as well as in the verb's own argument list, with nothing in the schema saying which wins — that is unverified here, so set one deliberately rather than both.
- `CacheStorageScope` and the fields of `MacroValue` beyond `Key`, `Value`, `Values` and `IsExpandable` are **not described in the published schema** and are unverified here.

## [glossary.md](glossary.md)

**[Element](glossary.md#element)**

- Exactly which object types count as an element for which licence is a licensing question rather than a schema one, and is not recorded in the published schema.

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

## [invoke-at-scale.md](../swis/invoke-at-scale.md)

**[Authorization is thinner than it looks](../swis/invoke-at-scale.md#authorization-is-thinner-than-it-looks)**

- **This repository can verify the contract and cannot verify the server.** Where the two might disagree, test on a system you can afford to be wrong about.

**["Random" is misleading, and the real rule is worse](../swis/invoke-at-scale.md#random-is-misleading-and-the-real-rule-is-worse)**

- Both are unverified here.

**[The account that could do more than the task needed](../swis/invoke-at-scale.md#the-account-that-could-do-more-than-the-task-needed)**

- Whether they scope what a verb can *act on* is **not stated in the schema and is unverified here** — do not rely on a limitation as a safety control for Invoke without testing it.

**[Classify every verb you call](../swis/invoke-at-scale.md#classify-every-verb-you-call)**

- The third question has a specific trap: **an empty array is not always a no-op.** Whether a verb given an empty list does nothing or does everything is not stated anywhere in the contract, and it is **unverified here**.
- None of it is stated in the schema; it is inferred from what the verbs do and is **unverified here**.

**[Gotchas](../swis/invoke-at-scale.md#gotchas)**

- **Account limitations scope what an account sees.** Whether they scope what a verb acts on is unverified here.

## [invoke-verbs.md](../swis/invoke-verbs.md)

**[How arguments are serialised](../swis/invoke-verbs.md#how-arguments-are-serialised)**

- That reading is taken from the SDK source rather than from the schema data this repository extracts, so the file path and the "exactly three" are **unverified** here; the three idioms they explain are all visible in SolarWinds' own sample scripts.

## [metadata-introspection.md](../swis/metadata-introspection.md)

**[How they connect](../swis/metadata-introspection.md#how-they-connect)**

- A query of the form `SELECT Name FROM Metadata.Property WHERE Entity.FullName='Metadata.Entity' AND Name IN (...)` is reported to ship in SWQL Studio's own source; that provenance is **unverified** here, because this repository holds no copy of it.

## [uris.md](../swis/uris.md)

**[The key filter](../swis/uris.md#the-key-filter)**

- That sourcing matters because *which* properties make up an entity's key is **not recorded in the published schema** that this repository extracts, so the composite key sets above cannot be verified here.

## [date-and-time.md](../swql/date-and-time.md)

**[Where the trap does not reach](../swql/date-and-time.md#where-the-trap-does-not-reach)**

- That reading is an inference from the generated T-SQL above and is **unverified** here.

**[`DateTime` literals and parameters](../swql/date-and-time.md#datetime-literals-and-parameters)**

- If you must use a literal, the ISO 8601 form `'2026-01-01T00:00:00'` is the conventional choice for unambiguity, but its acceptance by SWIS is **unverified** here: no published SolarWinds example uses it.

## [functions.md](../swql/functions.md)

**[`UNION(q)`](../swql/functions.md#unionq)**

- `UNION ALL` is **unverified**: only `UNION` is documented.

**[`ChangeTimeZone` is not in the official reference](../swql/functions.md#changetimezone-is-not-in-the-official-reference)**

- **Treat it as unverified.**

## [gotchas.md](../swql/gotchas.md)

**[SWQL gotchas](../swql/gotchas.md#swql-gotchas)**

- Where something is widely believed but could not be verified from the schema, the official docs or SolarWinds' own samples, it is marked **unverified** and comes with a query you can run on your own server to settle it.

**[1. The empty result set is usually a permissions answer](../swql/gotchas.md#1-the-empty-result-set-is-usually-a-permissions-answer)**

- The schema publishes no summary for either, so what exactly `IsSwisLimitation` gates is **unverified** here; the name and the surrounding entity make it the first thing to look at when a limitation appears to affect the web console but not an API query.

**[6. To-many navigation multiplies rows and poisons aggregates](../swql/gotchas.md#6-to-many-navigation-multiplies-rows-and-poisons-aggregates)**

- Two counts rather than one because `Count(n)` is the only counting signature in SolarWinds' [documented function reference](https://solarwinds.github.io/OrionSDK/docs/swql-functions/); `COUNT(DISTINCT column)` is standard T-SQL and may well work, but it is **unverified** here.

**[8.4 `Orion.Nodes.Flows` is declared twice](../swql/gotchas.md#84-orionnodesflows-is-declared-twice)**

- **Unverified:** treat `n.Flows` as ambiguous and write the target entity out in an explicit join instead.

**[10. String comparison, collation and case](../swql/gotchas.md#10-string-comparison-collation-and-case)**

- T-SQL's `LIKE` also accepts `[abc]` character classes and SWQL compiles to T-SQL, so those may pass through, but nothing in the SWQL documentation says so and it is **unverified** here: test `WHERE n.Caption LIKE 'core-sw-0[12]'` in SWQL Studio before relying on it. - **Compare Uris with `UriEquals`, not `=`.** The documented description is "Returns true if SWIS Uri `a` refers to the same entit...

## [language-reference.md](../swql/language-reference.md)

**[How this page marks its evidence](../swql/language-reference.md#how-this-page-marks-its-evidence)**

- Where a construct could not be corroborated at all, it is marked **unverified** with a one-line note on how to confirm it on your own server rather than being quietly dropped or quietly asserted.

**[CROSS JOIN](../swql/language-reference.md#cross-join)**

- **Unverified.** `CROSS` does not appear in SolarWinds' documentation, in the SDK samples, or in SWQL Studio's keyword list, and this repository has no evidence that SWQL accepts it.

**[Comparison operators](../swql/language-reference.md#comparison-operators)**

- `<>` — Not equal — **Unverified.** The standard SQL spelling, but it appears in no SolarWinds documentation page, no SDK sample and no SWQL Studio source available here, and SWQL Studio's keyword list covers keywords, not operators. Confirm it on your own server with `SELECT TOP 1 NodeID FROM Orion.Nodes WHERE Status <> 1`; a parse error is the answer. `!=` is the form SolarWinds itself writes

**[Other WITH options](../swql/language-reference.md#other-with-options)**

- `WITH SCHEMAONLY` — **Unverified.** It appears in community usage and in this repository's own validator keyword list, but not in any SolarWinds documentation, sample or source available here. Confirm on your own server by running a query with and without it and comparing the response

**[UNION](../swql/language-reference.md#union)**

- **`UNION ALL` is unverified.** The official reference documents only `UNION`.

**[CASE](../swql/language-reference.md#case)**

- Whether the simple form, `CASE Severity WHEN 2 THEN ...`, is also accepted **is unverified here**.

**[Subqueries in FROM](../swql/language-reference.md#subqueries-in-from)**

- **Unverified.** Nothing in the sources available here shows a derived table (`FROM (SELECT ...) x`).

## [performance.md](../swql/performance.md)

**[9. Bind parameters instead of building query text](../swql/performance.md#9-bind-parameters-instead-of-building-query-text)**

- Whether SWIS actually reuses a plan across executions of the same parameterised query is **unverified** here; you can test it on your own server by running the same query with different parameter values and comparing the timings reported by `WITH QUERYSTATS`.

## [README.md](../webui/README.md)

**[A caveat that applies to the whole section](../webui/README.md#a-caveat-that-applies-to-the-whole-section)**

- So the SWQL is sound and the UI conventions around it are reported, sourced and marked unverified.

## [custom-query-widget.md](../webui/custom-query-widget.md)

**[Where the link value comes from](../webui/custom-query-widget.md#where-the-link-value-comes-from)**

- These console paths are **not part of the SWIS schema and are unverified here**.

**[Where the icon value comes from](../webui/custom-query-widget.md#where-the-icon-value-comes-from)**

- The `Small-` prefix and `.gif` extension are **unverified here**.

**[A worked widget](../webui/custom-query-widget.md#a-worked-widget)**

- What it means for a query that spans several statistics tables is **not documented by SolarWinds and is unverified here**; see [../swql/performance.md](../swql/performance.md) for what a widget query costs and [../swql/gotchas.md](../swql/gotchas.md) for reading uncommitted data.

**[Practical notes](../webui/custom-query-widget.md#practical-notes)**

- They are marked unverified where they appear, or attributed to the practitioner who reported them.

## [modern-dashboard-authoring.md](../webui/modern-dashboard-authoring.md)

**[The `?filters=` grammar](../webui/modern-dashboard-authoring.md#the-filters-grammar)**

- **Only `eq` and `ne` appear.** Whether the filter engine accepts comparison, `like` or `in` operators is **not documented and unverified here**.

**[Gotchas](../webui/modern-dashboard-authoring.md#gotchas)**

- **Filter values are not escaped.** A value containing `-` or `:` is unverified territory.

## [modern-dashboards.md](../webui/modern-dashboards.md)

**[The envelope](../webui/modern-dashboards.md#the-envelope)**

- `remove` — `null` in every export seen; purpose undocumented and **unverified here**

**[`dashboards[]` — the page and its layout](../webui/modern-dashboards.md#dashboards-the-page-and-its-layout)**

- `parent` — `null` in every export seen. Presumably the clone source, matching `Orion.Dashboards.Instances.ParentID` — **unverified**
- `private` — `null` on the dashboard, `false` on widgets. Visibility; **unverified**
- `groupId`/`groupRank`/`groupName` read as dashboard grouping and `routeId`/`dashboardRoutes` as custom URL routing, but every value seen is empty, so what they do is **undocumented and unverified here**.

**[The grid is 12 columns wide](../webui/modern-dashboards.md#the-grid-is-12-columns-wide)**

- What `true` would mean is **undocumented and unverified here**; the plausible reading is a link to a widget owned by another dashboard rather than an embedded copy.

**[The header block, common to all types](../webui/modern-dashboards.md#the-header-block-common-to-all-types)**

- The reading that `collapsed` is inert unless `collapsible` is set fits the evidence but is still **unverified here**; what is now clear is that you should write the pair the way the console does, or omit both, rather than inventing `collapsed: false`.

**[The `content` node](../webui/modern-dashboards.md#the-content-node)**

- What it enables is **undocumented and unverified here**.

**[Formatter property values](../webui/modern-dashboards.md#formatter-property-values)**

- The full set of valid threshold names is **not documented and unverified here**.
- Whether `label` is honoured by the other link formatters is **unverified here**.
- What the values select is **not documented and unverified here**.
- The complete value sets for `iconFormat`, `entityIcon`, `visualization` and `option` are **not documented and unverified here**.

**[The colour tokens](../webui/modern-dashboards.md#the-colour-tokens)**

- The full token set is **not documented and unverified here**.

**[Proportional (donut) configuration](../webui/modern-dashboards.md#proportional-donut-configuration)**

- An empty `"editor": {}` sits alongside it on all 18, purpose **unverified here**.
- None of these lists is necessarily complete and all are **unverified here** beyond what the samples exercise.

**[`unique_key` collisions, and the reuse that is fine](../webui/modern-dashboards.md#unique_key-collisions-and-the-reuse-that-is-fine)**

- What the platform does with a duplicate key is **not documented and unverified here**.

**[One name that does not resolve](../webui/modern-dashboards.md#one-name-that-does-not-resolve)**

- Which one is **unverified here**.

**[Two artefacts worth knowing about](../webui/modern-dashboards.md#two-artefacts-worth-knowing-about)**

- Whether the console tolerates them is **unverified here**, but they are worth removing before you copy such a query.

## [ncm-change-template-language.md](../webui/ncm-change-template-language.md)

**[If you know C#, what does not transfer](../webui/ncm-change-template-language.md#if-you-know-c-what-does-not-transfer)**

- Whether `&&`, `and`, `AND` or anything else works is **unverified here**.

**[Two kinds of variable, and they are not interchangeable](../webui/ncm-change-template-language.md#two-kinds-of-variable-and-they-are-not-interchangeable)**

- Whether `${CRLF}` works inside a change template as opposed to a command script is **unverified**; the community source that lists it flags the same doubt.

**[Declaring and assigning](../webui/ncm-change-template-language.md#declaring-and-assigning)**

- What operations `int` supports is **not documented and is unverified here** — no source this repository has seen performs arithmetic in a template, and the only operator shown on any value is `+` joining strings.

**[String functions](../webui/ncm-change-template-language.md#string-functions)**

- Whether `octetPosition` counts from 0 or from 1 is **not stated in the source and is unverified here** — test it before shipping a template that rewrites addresses.

**[Control flow](../webui/ncm-change-template-language.md#control-flow)**

- **`if` and `else`.** Whether a chained `else if` works is where two SolarWinds sources read differently, so treat it as **unverified**.

**[Special characters need a variable](../webui/ncm-change-template-language.md#special-characters-need-a-variable)**

- Which characters need this treatment beyond `|` and `@` is **not documented and is unverified here**.

**[Gotchas](../webui/ncm-change-template-language.md#gotchas)**

- **`else if` is unverified.** Two SolarWinds sources read differently and no example uses a chain.

## [ncm-change-templates.md](../webui/ncm-change-templates.md)

**[The directives](../webui/ncm-change-templates.md#the-directives)**

- Whether any display type other than `Listbox` is supported is **not documented by SolarWinds and is unverified here**.

**[The signature decides what the user sees](../webui/ncm-change-templates.md#the-signature-decides-what-the-user-sees)**

- Anything beyond those three is **undocumented and unverified here**.

**[The parameter types are SWIS entities](../webui/ncm-change-templates.md#the-parameter-types-are-swis-entities)**

- Whether the template engine accepts a navigation the schema declares but SolarWinds' own examples never use is **unverified here**.

**[Sharing](../webui/ncm-change-templates.md#sharing)**

- The schema types it a plain `System.String` and says only "Snippet description", so this is **observed from the console rather than declared** and unverified here.

**[What this repository can and cannot check](../webui/ncm-change-templates.md#what-this-repository-can-and-cannot-check)**

- Directive names, the `Listbox:` syntax, the signature grammar and everything in [ncm-change-template-language.md](../webui/ncm-change-template-language.md) come from SolarWinds' documentation and from THWACK, and **cannot be verified here**.

## [perfstack.md](../webui/perfstack.md)

**[The URL grammar](../webui/perfstack.md#the-url-grammar)**

- This is **unverified here**.

**[Everything above is community-sourced](../webui/perfstack.md#everything-above-is-community-sourced)**

- The grammar is reported from THWACK threads and from third-party write-ups, not from SolarWinds' product documentation, and **this repository cannot verify any of it**.

**[Settle the grammar against your own server](../webui/perfstack.md#settle-the-grammar-against-your-own-server)**

- What `Data` contains is **not recorded in the schema** and is unverified here — it is a `System.String` and the column summary says nothing.

**[Non-numeric data lives in the Data Explorer tab](../webui/perfstack.md#non-numeric-data-lives-in-the-data-explorer-tab)**

- Whether the Data Explorer tab can be pre-loaded from the URL the way the chart surface can — and if so, with what segment grammar — is **not documented and unverified here**.

**[Sources, and what is missing](../webui/perfstack.md#sources-and-what-is-missing)**

- `PRINTABLE=TRUE` is reported as removing the console chrome and is unverified here.

**[See also](../webui/perfstack.md#see-also)**

- [variables.md](../webui/variables.md) — the alert variables that supply the id segment - [custom-query-widget.md](../webui/custom-query-widget.md) — `_LinkFor_`, which turns a generated URL into a clickable column - [README.md](../webui/README.md) — the rest of this section, and why the schema cannot verify console behaviour - [../swql/functions.md](../swql/functions.md) — `ToString()` and string concatenation - [../modu...

## [variables-reference.md](../webui/variables-reference.md)

**[Variable reference](../webui/variables-reference.md#variable-reference)**

- Where it does not — the `Alerting`, `Generic` and `OrionGroup` contexts, and the syslog and trap lists — the name is reported as published and **cannot be verified here**.

**[`N=Alerting` — the alert itself](../webui/variables-reference.md#nalerting-the-alert-itself)**

- Whether the context reads those entities or its own state is **not documented and unverified here**; the names line up but the mapping is not stated.

**[Node variables that walk a navigation property](../webui/variables-reference.md#node-variables-that-walk-a-navigation-property)**

- Which one the engine prefers is **unverified here**.

**[SNMPv3 credential variables](../webui/variables-reference.md#snmpv3-credential-variables)**

- Whether the platform redacts any of these at render time is **not documented and is unverified here**; assume it does not.

**[Other trap variables](../webui/variables-reference.md#other-trap-variables)**

- Whether `${vbName2}` and beyond exist is **not documented and is unverified here**.

## [variables-undocumented.md](../webui/variables-undocumented.md)

**[Navigation is the larger unpublished surface](../webui/variables-undocumented.md#navigation-is-the-larger-unpublished-surface)**

- Whether the engine walks an arbitrary navigation, whether it walks more than one hop, and what it renders for a to-many navigation that returns several rows, are all **undocumented and unverified here**.

## [variables.md](../webui/variables.md)

**[The three attributes](../webui/variables.md#the-three-attributes)**

- The complete set of format names is **not published in the material this repository has** and is unverified here; the variable picker in the console offers them, which is the practical way to find out what your version accepts.

**[The member list is the property list](../webui/variables.md#the-member-list-is-the-property-list)**

- One qualification remains, marked **unverified here** because the schema does not record it: whether *every* member is exposed to the variable engine, or only a subset.
- The three published examples each walk exactly one hop; whether two hops work, and what a to-many navigation renders when it matches several rows, are **not documented and unverified here**.

**[`${SQL:…}` runs a query](../webui/variables.md#sql-runs-a-query)**

- Two people reading the same alert email see the same number, whatever their limitations would allow them to see in the console. - Whether the query text is escaped or validated in any way is **not documented and is unverified here**.

**[See also](../webui/variables.md#see-also)**

- [README.md](../webui/README.md) — the rest of this section, and why the schema cannot verify console behaviour - [../automation/alerts.md](../automation/alerts.md) — alert definitions, actions and suppression through the API - [../automation/custom-properties.md](../automation/custom-properties.md) — creating the properties that become variables - [../swis/metadata-introspection.md](../swis/metadata-int...

---

An entry here is not a defect. It is a statement that a reader should confirm before depending on it, and that this repository declines to guess about.

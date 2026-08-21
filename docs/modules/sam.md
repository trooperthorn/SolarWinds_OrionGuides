# SAM: Server and Application Monitor

Server and Application Monitor is the module that monitors what runs *on* a node rather
than the node itself: Windows services, Linux processes, listening ports, HTTP endpoints,
SQL queries, PowerShell and Perl scripts, and the deep-dive AppInsight monitors for SQL
Server, IIS, Exchange, and Active Directory.

The first thing to know is the name. **SAM entities are prefixed `Orion.APM.`, never
`Orion.SAM.`.** "APM" is the original engineering name for the module and it survived
every rename, including the product's move to SolarWinds Observability Self-Hosted. The
netobject reference spells the display names out as "APM: Application" and "APM:
Component". Deriving `Orion.SAM.Application` from the product name is the single most
common SAM query failure, and it fails with an unknown-entity error that looks like a
missing licence rather than a typo.

## Namespace and size

Everything SAM contributes lives under `Orion.APM.`, which holds **140 entities** in the
2026.2 schema. That ties with VNQM's `Orion.IpSla.` for the largest namespace belonging to a
single licensed module; only the cloud family (`Orion.Cloud.`, 148 entities) is larger, and
that one is a platform capability rather than a product you buy. Thirty-nine verbs are
declared across eleven of those entities.

```bash
python3 tools/schema_query.py find Orion.APM --properties
python3 tools/schema_query.py show Orion.APM.Application
python3 tools/schema_query.py verbs --entity Orion.APM.ApplicationTemplate
```

The namespace splits roughly into families:

| Family | Entities | What it covers |
|---|---|---|
| `Orion.APM.Application*` | 12 | Applications, their settings, custom properties, status, TCP connections |
| `Orion.APM.Component*` | 15 | Components, component templates, definitions, categories, settings, thresholds |
| `Orion.APM.Sql*` | 19 | AppInsight for SQL: instances, databases, files, indexes, queries, jobs |
| `Orion.APM.Exchange.*` | 21 | AppInsight for Exchange: servers, mailbox databases, copies, mailboxes, DAGs |
| `Orion.APM.IIS.*` | 14 | AppInsight for IIS: sites, application pools, bindings, worker processes |
| `Orion.APM.ActiveDirectory.*` | 10 | AppInsight for Active Directory: domain controllers, sites, replication, trusts |
| `Orion.APM.Wstm.*` | 3 | Windows scheduled tasks |
| Evidence and statistics | ~20 | Per-poll detail behind a component's status |

See [../platform/modules.md](../platform/modules.md) for how SAM sits alongside the other
modules and how to check which of them are installed on a given server.

## The template, application, component model

This is the model everything else in SAM hangs off, and it is worth getting exactly right
because the four levels have four different entities and it is easy to reach for the wrong
one.

A **template** is a reusable definition. Applying a template to a node **creates an
application**, and the application contains **components** cloned from the template's
component definitions. SolarWinds states it plainly in
[SAM Application Monitoring Templates](https://solarwinds.github.io/OrionSDK/docs/server-and-application-monitor/sam-application-monitoring-templates/):
"an application is a collection of component monitors inherited from a template when you
assign the template to a node."

```
Orion.APM.ApplicationTemplate        the definition, e.g. "Apache", "AppInsight for SQL"
    |  ApplicationTemplateID
    |
    +-- Orion.APM.ComponentTemplate  one component definition inside the template
    |        ApplicationTemplateID -> parent template
    |        ID, Name, ComponentType, ComponentCategoryID, ComponentOrder, IsDisabled
    |
    | CreateApplication(nodeId, applicationTemplateId, credentialSetId, ...)
    v
Orion.APM.Application                one instance of the template, running on one node
    |  ApplicationID, NodeID, ApplicationTemplateID
    |
    +-- Orion.APM.Component          one monitored item inside the application
             ComponentID, ApplicationID, TemplateID, ComponentOrder
```

Note that `Orion.APM.ComponentTemplate` is the entity SolarWinds' documentation calls a
"component monitor". Its own note is worth quoting: "In the Orion SDK, entities related to
component monitors have `ComponentTemplate` in their titles."

### Settings exist at all four levels

Each of the four levels has a parallel key/value settings entity with the same shape
(`Key`, `Value`, `ValueType`, `Required`). Which one you write to decides whether a change
affects every future application or only one existing instance:

| Entity | Key column | Scope of a change |
|---|---|---|
| `Orion.APM.ApplicationTemplateSettings` | `ApplicationTemplateID` | The template, so every application created from it afterwards |
| `Orion.APM.ComponentTemplateSetting` | `ComponentTemplateID` | One component monitor in the template |
| `Orion.APM.ApplicationSettings` | `ApplicationID` | One live application |
| `Orion.APM.ComponentSetting` | `ComponentID` | One live component |

The two template settings entities allow `read` and `update` but not `create`. The two
instance settings entities allow `create`, `read`, and `update`. All four require the
`manageNodes` right for anything but reading.

### Navigating between the levels

| From | Navigation property | To |
|---|---|---|
| `Orion.APM.Application` | `Node` | `Orion.Nodes` |
| `Orion.APM.Application` | `Template` | `Orion.APM.ApplicationTemplate` |
| `Orion.APM.Application` | `Components` | `Orion.APM.Component` |
| `Orion.APM.Application` | `CustomProperties` | `Orion.APM.ApplicationCustomProperties` |
| `Orion.APM.Application` | `ScheduledTasks` | `Orion.APM.Wstm.Task` |
| `Orion.APM.Component` | `Application` | `Orion.APM.Application` |
| `Orion.APM.Component` | `ComponentDefinition` | `Orion.APM.ComponentDefinition` |
| `Orion.APM.ApplicationTemplate` | `Applications` | `Orion.APM.Application` |
| `Orion.APM.ComponentTemplate` | `Category` | `Orion.APM.ComponentCategory` |
| `Orion.Nodes` | `Applications` | `Orion.APM.Application` |

**`Orion.APM.Component` has no navigation property to a node.** Reach the node through the
application: `c.Application.Node.Caption`. Writing `c.Node` is the second most common SAM
query mistake after `Orion.SAM.*`.

### NetObject prefixes

Verbs that take a `netObjectId` want a NetObject string, not a bare integer.

| Entity | Prefix | Example |
|---|---|---|
| `Orion.APM.Application` | `AA` | `AA:42` |
| `Orion.APM.Component` | `AM` | `AM:1701` |
| `Orion.APM.SqlServerApplication` | `ABSA` | `ABSA:42` |
| `Orion.APM.IIS.Application` | `ABIA` | `ABIA:42` |
| `Orion.APM.Exchange.Application` | `ABXA` | `ABXA:42` |
| `Orion.APM.Wstm.Task` | `ABTT` | `ABTT:9` |

The full list, including the AppInsight sub-entities such as `ABSD` for a SQL database and
`ABIS` for an IIS site, is in
[../reference/netobject-types.md](../reference/netobject-types.md).

## Applications and components in detail

### Orion.APM.Application

Twenty-five properties, seven verbs, and six entities inherit from it. The ones you use
constantly:

| Property | Type | Notes |
|---|---|---|
| `ApplicationID` | `System.Int32` | Primary key. `ID` is a duplicate of it. |
| `Name` | `System.String` | Usually the template name |
| `DisplayName` | `System.String` | The friendly name shown in the web console |
| `NodeID` | `System.Int32` | The node the template was applied to |
| `ApplicationTemplateID` | `System.Int32` | The template it came from |
| `Status` | `System.Int32` | Join `Orion.StatusInfo` to read it |
| `StatusDescription` | `System.String` | Already-rendered status text |
| `UnManaged`, `UnManageFrom`, `UnManageUntil` | | The maintenance-window trio, declared on this entity rather than inherited |
| `HasCredentials` | `System.Boolean` | Whether a credential set is attached |
| `CustomApplicationType` | `System.String` | Set for AppInsight applications, empty for template-based ones |
| `Created`, `LastModified` | `System.DateTime` | |

`Orion.APM.Application` is the base type, so a query against it returns AppInsight
applications as well as ordinary ones. `Orion.APM.GenericApplication` is the subtype that
excludes them, described in the schema as "common applications (black box applications are
filtered out)".

### Orion.APM.Component

| Property | Type | Notes |
|---|---|---|
| `ComponentID` | `System.Int64` | Primary key, note the 64-bit width |
| `ApplicationID` | `System.Int32` | Parent application |
| `TemplateID` | `System.Int64` | The application template the component came from |
| `Name`, `ShortName`, `ComponentName` | `System.String` | |
| `ComponentType` | `System.Int32` | Numeric monitor type; name it via `ComponentDefinition` |
| `ComponentEvidenceType` | `System.Int32` | Which evidence entity carries this component's detail |
| `ComponentOrder` | `System.Int32` | Display order inside the application |
| `Disabled` | `System.Boolean` | Turned off in the template or on this instance |
| `UnManaged` | `System.Boolean` | In a maintenance window |
| `ApplicationItemID` | `System.Int32` | Links AppInsight components to their application item |

`Disabled` and `UnManaged` mean different things and you almost always want both in a
filter. `Disabled = TRUE` means the component is switched off and is silently not being
monitored at all. `UnManaged = TRUE` means it is monitored but suppressed for a maintenance
window. Filtering only on `Status` catches neither.

`ComponentType` is an integer with no enumeration in the published schema. Rather than
hard-coding numbers, join through the definition, which carries a name:

```sql
SELECT
    c.ComponentDefinition.Name AS ComponentTypeName,
    COUNT(c.ComponentID) AS ComponentCount
FROM Orion.APM.Component c
WHERE c.Disabled = FALSE
GROUP BY c.ComponentDefinition.Name
ORDER BY COUNT(c.ComponentID) DESC
```

### Status, statistics, and evidence

SAM keeps four layers of runtime data, and picking the wrong one is the difference between
a fast query and a table scan of the largest tables in the database.

| Entity | Grain | Use it for |
|---|---|---|
| `Orion.APM.CurrentApplicationStatus` | One row per application | Last poll time, `LastTimeUp`, `LastSuccessfulPoll`, `ErrorMessage` |
| `Orion.APM.CurrentComponentStatus` | One row per component | `ErrorCode`, `ErrorMessage`, `PercentCPU`, `PercentMemory`, `LastTimeUp` |
| `Orion.APM.CurrentStatistics` | One row per component | The last polled numbers: `ComponentResponseTime`, `ComponentStatisticData`, `ComponentPercentCPU`, `ComponentPID`, `InstanceCount` |
| `Orion.APM.ApplicationStatus`, `Orion.APM.ComponentStatus` | Historical, one row per poll | Availability over time. Always time-bound these. |

Both historical entities inherit from `System.StatisticsEntity`, so they also carry
`ObservationTimestamp`, `ObservationFrequency`, and `Weight` alongside their own
`TimeStamp` column.

**Evidence** entities are the per-poll detail behind a component's result, and they hang
off `Orion.APM.ComponentStatus` rather than off the component:

| Entity | Carries |
|---|---|
| `Orion.APM.ProcessEvidence` | Min/max/average CPU, memory, virtual memory and instance count for a process monitor |
| `Orion.APM.PortEvidence` | Port number, response time and statistic data for a port monitor |
| `Orion.APM.DynamicEvidence` | The columns a script monitor returned, with per-column thresholds. The schema describes it as "used to present script monitors statistics". |
| `Orion.APM.ChartEvidence` | Chartable statistic values |

Each has a companion chart entity that hangs off `Orion.APM.Component` directly and is the
one to use for graphing: `Orion.APM.ProcessEvidenceChart`,
`Orion.APM.PortEvidenceChart`, `Orion.APM.DynamicEvidenceChart`, and
`Orion.APM.ChartEvidence2`. `Orion.APM.DynamicEvidenceColumnSchema` describes the columns a
dynamic (script) monitor produces, and its `Name` is what
`Orion.APM.Component.CalculateBaselineThresholds` expects as a threshold name for those
components.

`Orion.APM.WindowsEvent` hangs off `Orion.APM.Component` and holds the Windows event log
records a Windows Event Log monitor matched, with `LogFile`, `EventCode`, `SourceName`,
`User`, `TimeGeneratedUtc`, and `Message`.

### Thresholds

Three entities, for three purposes:

- `Orion.APM.Threshold` is the threshold definition itself: `ThresholdName`, `Warning`,
  `Critical`, `ThresholdOperator`, and the baseline fields (`ComputeBaseline`,
  `UseBaseline`, `BaselineFrom`, `BaselineTo`, `BaselineApplied`, `BaselineApplyError`).
  `IsTemplate` distinguishes a template-level threshold from an instance-level one.
  `ThresholdOperator` is documented in the schema as `0` greater than, `1` greater than or
  equal to, `2` equal to, `3` less than or equal to, `4` less than, `5` not equal to.
- `Orion.APM.ThresholdsByComponent` is the flattened component-to-threshold view, and is
  what you join to a component. **Its key column is `ComponentId` with a lowercase `d`**,
  unlike `ComponentID` everywhere else in the namespace.
- `Orion.APM.ComponentAlertThresholds` is the alerting-oriented view with one column per
  metric (`ThresholdCPUWarning`, `ThresholdResponseTimeCritical`, and so on), reachable
  from a component as `c.ComponentAlertThresholds`.

## AppInsight applications

AppInsight monitors are, in SolarWinds' own words from
[SAM AppInsight Applications](https://solarwinds.github.io/OrionSDK/docs/sam-appinsight-applications/),
"considered templates until applied" and are "a member of the Application Monitor Templates
collection". That has a concrete consequence for automation: **you assign an AppInsight
monitor exactly the way you assign any other template**, with
`Orion.APM.Application.CreateApplication`, passing the AppInsight template's
`ApplicationTemplateID`.

The four families each get a subtype of `Orion.APM.Application`:

| AppInsight | Application entity | Template name | `CustomApplicationType` | NetObject |
|---|---|---|---|---|
| SQL | `Orion.APM.SqlServerApplication` | `AppInsight for SQL` | `ABSA` | `ABSA` |
| IIS | `Orion.APM.IIS.Application` | `AppInsight for IIS` | `ABIA` | `ABIA` |
| Exchange | `Orion.APM.Exchange.Application` | `AppInsight for Exchange` | `ABXA` | `ABXA` |
| Active Directory | `Orion.APM.ActiveDirectory.Application` | `AppInsight for Active Directory` | `ABAA` | not listed |

The template names and `CustomApplicationType` codes come from SolarWinds' AppInsight page.
Template IDs are **not** fixed across installations, so look them up by name rather than
hard-coding the numbers that appear in that page's examples:

```sql
SELECT
    t.ApplicationTemplateID,
    t.Name AS TemplateName,
    t.CustomApplicationType
FROM Orion.APM.ApplicationTemplate t
WHERE t.Name LIKE 'AppInsight%'
ORDER BY t.Name
```

### The shared application item base

Six entities inherit from `Orion.APM.ApplicationItem`, described in the schema as "any
significant AppInsight application's entity (e.g. SQL Database)". It contributes `ItemID`,
`ApplicationID`, `Name`, and `ItemType`:

`Orion.APM.SqlDatabase`, `Orion.APM.IIS.Site`, `Orion.APM.IIS.ApplicationPool`,
`Orion.APM.Exchange.DatabaseCopy`, `Orion.APM.ActiveDirectory.Site`, and
`Orion.APM.ActiveDirectory.NamingContext`.

Those `ItemID` values are what the `ApplicationItemID` column on `Orion.APM.Component`
points at, which is how a component in an AppInsight application is tied to the particular
database, site, or pool it monitors.

### AppInsight for SQL

`Orion.APM.SqlServerApplication` adds `InstanceName`, `ProductVersion`, `ProductLevel`, and
`Edition` to the application, and navigates to `Databases`, `SqlJobInfo`, and
`SqlClusterNodes`. Below the database sit `Orion.APM.SqlDatabaseFile` (with
`UsedSpacePercentage`, `AvailableAutoGrowSpace`, `WhiteSpaceFreePercentage`),
`Orion.APM.SqlDatabaseFileGroup`, `Orion.APM.SqlIndex`, `Orion.APM.SqlTable`,
`Orion.APM.SqlQuery` (the expensive-queries list), and `Orion.APM.SqlDatabaseMirroring`.

Watch the key columns: `Orion.APM.SqlDatabaseFile` links to its database through
`SqlDatabaseID`, not `DatabaseID`. The navigation property `Database` avoids the question
entirely.

The application settings AppInsight for SQL accepts, per SolarWinds' page, are `PortType`
(`default` or `static`) and, when static, `PortNumber`. `InstanceName` may be supplied and
defaults to the default instance when omitted.

### AppInsight for IIS

`Orion.APM.IIS.Application` adds only job-tracking columns of its own but navigates to
`Site` and `ApplicationPool`. `Orion.APM.IIS.Site` carries `State`, `DisplayState`,
`PhysicalPath`, `AverageResponseTime`, `CurrentConnections`, `MaxConnections`, and
`CurrentHttpBindingsUrls`. `Orion.APM.IIS.ApplicationPool` carries `State`,
`ManagedRuntimeVersion`, `ManagedPipelineMode`, `IdentityType`, `MaxProcesses`, and
per-metric statuses such as `TotalWpCPUStatus`. Both expose `Start`, `Stop`, and `Restart`
verbs, and both are `Orion.APM.ApplicationItem` subtypes.

Settings on creation are `NodeIpAddress` and `PsUrlWindowsValue` (the WinRM endpoint).

### AppInsight for Exchange

`Orion.APM.Exchange.Application` adds `ServerIdentity`, `ServerGuid`, `ServerRole`,
`AdminDisplayVersion`, `DatabaseAvailabilityGroupID`, and `HasMessageTrackingLog`.
`Orion.APM.Exchange.Database` is the mailbox database with `LastFullBackup`,
`LastIncrementalBackup`, `CircularLoggingEnabled`, the three quota columns,
`TotalMailboxes`, and `AvgMailBoxSize`. `Orion.APM.Exchange.Mailbox` has 44 properties
covering quota usage and message counts over seven and thirty day windows.
`Orion.APM.Exchange.DatabaseCopy` and `Orion.APM.Exchange.ReplicationStatus` cover DAG
replication.

Settings on creation are `PsUrlWindows` and `PsUrlExchange`, both PowerShell remoting URLs.

### AppInsight for Active Directory

`Orion.APM.ActiveDirectory.Application` adds `DomainName`, `RootDomainName`, and the
`WhenCreated` / `WhenChanged` pair, and navigates to `DomainControllers`, `Sites`, and
`NamingContexts`. The operationally interesting entity is
`Orion.APM.ActiveDirectory.Replication`, which has `SourceNode` and `DestinationNode`
navigation straight to `Orion.Nodes`, plus `ConsecutiveSyncFailureCount`, `LastSuccessTime`
and `LastFailureTime`. `Orion.APM.ActiveDirectory.DomainTrust` records trust direction,
transitivity, and the security-relevant flags such as `IsUsingRC4Encryption` and
`IsQuarantinedDomain`. `Orion.APM.ActiveDirectory.DomainController.Roles` holds the FSMO
role bitmask.

Active Directory is the one family with its own assignment verb, `AssignApplication`, which
takes serialized XML settings instead of a key/value list. SolarWinds' AppInsight page
carries a full worked example of that XML.

## Windows scheduled tasks

`Orion.APM.Wstm.Task` is populated by the stock "Windows Scheduled Tasks" template. It is a
plain `System.Entity` with `ID`, `ComponentID`, `NodeID`, `Name`, `LastRunResult`,
`LastRunTime`, `NextRunTime`, `DateOfCreation`, `Author`, and `State`. The schema documents
`State` explicitly: **0 Failed, 1 Succeeded, 2 Retry, 3 Cancelled.**

It navigates back to both `Application` and `Node`, and forward to
`Orion.APM.Wstm.TaskAlert`, the flattened view used in alert conditions.
`Orion.APM.Wstm.ScheduledTasksStatus` is a subtype of `Orion.APM.Application` representing
the application as a whole.

SolarWinds' own `CreateWindowsScheduledTasks.ps1` sample assigns the template with an
`appSettings` hashtable containing a single key, `NodeIpAddress`, and a `credentialSetId`
of `-3`.

## TCP connections and application dependencies

SAM's connection mapping produces three related entities:

- `Orion.APM.ApplicationTcpConnection` is one client process talking to one server port.
  Thirty-eight properties, with parallel `Client*` and `Server*` columns and navigation to
  `ClientNode`, `ServerNode`, `ClientApplication`, `ServerApplication`,
  `ClientProcessComponent`, `ServerProcessComponent`, `ServerPortComponent`,
  `ClientInterface`, and `ServerInterface`. It carries `Latency`, `PacketLoss`, and
  `LastSeenTimeStamp`.
- `Orion.APM.DependencyTcpStatistics` aggregates those connections into an
  application-to-application dependency and is linked to `Orion.Dependencies`.
- `Orion.APM.NodeToNodeLink` aggregates one level higher, into a single link between two
  nodes, with `ChildNode` and `ParentNode` navigation and worst-of aggregated
  `LatencyStatus` and `PacketLossStatus`. Its thresholds are
  `Orion.APM.NodeToNodeLinkLatencyThreshold` and
  `Orion.APM.NodeToNodeLinkPacketLossThreshold`, both subtypes of `Orion.Thresholds`.

All three allow `create`, `update`, and `delete` with the `manageNodes` right, which is
unusual: most SAM entities are read-only through CRUD.

## Verbs

All thirty-nine SAM verbs, with parameters in the order they must be passed. **Invoke
arguments are positional.** The names below appear in the Swagger contract and in this
table, but they never travel on the wire, so the order is the entire contract.

### Orion.APM.Application

| Verb | Parameters | Returns | Right |
|---|---|---|---|
| `CreateApplication` | `nodeId`, `applicationTemplateId`, `credentialSetId`, `skipIfDuplicate`, `applicationSettings` (optional) | number | `manageNodes` |
| `DeleteApplication` | `applicationId` | void | `manageNodes` |
| `PollNow` | `applicationId` | void | `manageNodes` |
| `Unmanage` | `netObjetId`, `unmanageTime`, `remanageTime`, `isRelative`, `allowOverlapping` (optional) | void | see below |
| `Remanage` | `netObjetId` | void | see below |
| `TriggerInstantTemplateGroupAssignment` | none | void | `manageNodes` |
| `TriggerScheduledTemplateGroupAssignment` | none | void | `manageNodes` |

`Unmanage` and `Remanage` are the two verbs that record no right of their own in the
schema. `Orion.APM.Application` as an entity declares `invoke` against both `manageNodes`
and `allowUnmanage`, and `allowUnmanage` is the right the equivalent `Orion.Nodes.Unmanage`
verb names explicitly, so `allowUnmanage` is very likely the one these two need. *That
attribution is an inference, not a recorded fact.* Confirm it on your own server by
granting an account `allowUnmanage` without `manageNodes` and trying the call, or read the
entity's declaration back with `schema_query.py show Orion.APM.Application`.

`CreateApplication` returns the new `ApplicationID`, or **`-1` when `skipIfDuplicate` is
true and the template is already assigned to that node**. Check for `-1` rather than
assuming success.

`applicationSettings` is typed in the contract as an array of string key/value pairs. From
PowerShell you pass a hashtable; over REST you pass a JSON object. Both of SolarWinds'
sample sets do exactly this.

The two `TriggerTemplateGroupAssignment` verbs kick the automatic assignment engine that
applies templates to the members of a group, configured through
`Orion.APM.TemplateGroupAssignment` (`GroupID`, `TemplateID`, `AutoAssign`, `AutoDelete`,
`ServersOnly`, and the two credential columns).

### Orion.APM.ApplicationTemplate

| Verb | Parameters | Returns |
|---|---|---|
| `ImportTemplate` | `templateData` | number (new template ID) |
| `ExportTemplate` | `templateId` | string |
| `DeleteTemplate` | `applicationTemplateId` | void |
| `UpdateApplicationTemplateSettings` | `applicationTemplateId`, `settings` | void |
| `StartTestComponents` | `nodeId`, `templateUniqueId`, `credentialId` | array of job GUIDs |
| `GetTestComponentStatus` | `jobs` (array of job GUIDs) | array |

`StartTestComponents` and `GetTestComponentStatus` are the pair to reach for when you want
to know whether a template *would* work against a node before committing to assigning it.
`StartTestComponents` takes `templateUniqueId`, which is the template's
`UniqueId` **GUID**, not its integer `ApplicationTemplateID`. It returns job GUIDs that you
feed back into `GetTestComponentStatus` until the test completes.

`DeleteTemplate` is destructive well beyond the template. SolarWinds' own sample notes it:
"Removing the template also removes all applications created from this template." Count the
applications first.

### AppInsight verbs

| Verb | Parameters | Returns |
|---|---|---|
| `Orion.APM.IIS.Application.ScheduleConfiguration` | `applicationId`, `credentialsId` | string (execution key) |
| `Orion.APM.IIS.Application.GetConfigurationResult` | `executionKey` | configuration result |
| `Orion.APM.Exchange.Application.ScheduleConfiguration` | `applicationId`, `credentialsId` | string (execution key) |
| `Orion.APM.Exchange.Application.GetConfigurationResult` | `executionKey` | configuration result |
| `Orion.APM.ActiveDirectory.Application.AssignApplication` | `nodeId`, `serializedSettings` | number |
| `Orion.APM.ActiveDirectory.Application.DisableDomainComponents` | `applicationId` | void |
| `Orion.APM.ActiveDirectory.Application.DeleteDisabledComponentsData` | `applicationId` | void |

All seven require `manageNodes`. The two `ScheduleConfiguration` verbs run the remote
configurator that prepares the target server (WinRM for Exchange, the remote IIS
configurator for IIS) and are asynchronous: they return an execution key, and you poll
`GetConfigurationResult` with it. The result carries `IsFinished`, `ExitCode`, and
`ErrorDescription`.

### Real-time control verbs

| Verb | Parameters | Returns |
|---|---|---|
| `Orion.APM.IIS.Site.Start` / `Stop` / `Restart` | `nodeId`, `applicationId`, `credentialId`, `siteName`, `applicationTypeId` | number |
| `Orion.APM.IIS.ApplicationPool.Start` / `Stop` / `Restart` | `nodeId`, `applicationId`, `credentialId`, `poolName`, `applicationTypeId` | number |
| `Orion.APM.ServerManagement.StartService` / `StopService` / `RestartService` | `nodeId`, `credentialId`, `serviceName` | number |
| `Orion.APM.ServerManagement.RebootNode` | `nodeId` | number |

These act on the monitored server, not on the monitoring database. `RebootNode` restarts
the target machine. Confirm before calling it, and see the note in
[../../CONTRIBUTING.md](../../CONTRIBUTING.md) about destructive operations.

### Remaining verbs

| Verb | Parameters |
|---|---|
| `Orion.APM.Component.CalculateBaselineThresholds` | `componentId`, `thresholdName` |
| `Orion.APM.ApplicationCustomProperties.CreateCustomProperty` | `propertyName`, `description`, `valueType`, `size`, `validRange`, `parser`, `header`, `alignment`, `format`, `units`, `usageFlags`, `mandatory`, `defaultValue`, `sourceId` (optional), `sourceName` (optional) |
| `Orion.APM.ApplicationCustomProperties.CreateCustomPropertyWithValues` | same, with `values` inserted after `units` |
| `Orion.APM.ApplicationCustomProperties.ModifyCustomProperty` | `propertyName`, `description`, `size`, `values`, `usageFlags`, `mandatory`, `defaultValue`, `sourceId` (optional), `sourceName` (optional) |
| `Orion.APM.ApplicationCustomProperties.DeleteCustomProperty` | `propertyName`, `sourceId` (optional), `sourceName` (optional) |
| `Orion.APM.LicenseInfo.GetLicenseLimit` | none |
| `Orion.APM.LicenseInfo.GetLicensedEntitiesCount` | `engineName`, `entityPrefix` |
| `Orion.APM.LicenseInfo.GetLicensedEntityCountFromAllEngines` | `entityPrefix` |
| `Orion.APM.LicenseInfo.RefreshLicenseCache` | none |

`Orion.APM.ApplicationCustomProperties` is the one SAM entity whose declaration names the
`admin` right for `read`, `update` and `invoke`, where the rest of the namespace names
`manageNodes`. The custom property columns themselves are per-installation and therefore
not in the extracted schema; discover them with `Metadata.Property` against
`Orion.APM.ApplicationCustomProperties`, then read them as
`a.CustomProperties.YourColumnName`.

`CalculateBaselineThresholds` needs a threshold name. The verb's own documentation says
where to find one: "for dynamic components it can be taken from
`APM.DynamicEvidenceColumnSchema.Name`, for non dynamic component it can be taken from
`Orion.APM.Threshold.ThresholdName`."

The complete generated table for every module is at
[../reference/verb-index.md](../reference/verb-index.md).

## Worked queries

Each of these has been validated against the 2026.2 schema with
`tools/validate_swql.py`.

### Which components are actually broken, and why

An application turning red tells you nothing about the cause. This joins the component to
its current status so you get the error the poller recorded, and filters out both disabled
components and maintenance windows so the result is "actually broken" rather than "not
green".

```sql
SELECT
    c.Application.Node.Caption AS NodeName,
    c.Application.Name AS ApplicationName,
    c.Name AS ComponentName,
    s.StatusName,
    c.CurrentStatus.ErrorCode,
    c.CurrentStatus.ErrorMessage,
    c.CurrentStatus.LastTimeUp
FROM Orion.APM.Component c
JOIN Orion.StatusInfo s ON c.Status = s.StatusId
WHERE c.Status <> 1
  AND c.Disabled = FALSE
  AND c.UnManaged = FALSE
  AND c.Application.UnManaged = FALSE
ORDER BY s.Ranking, c.Application.Node.Caption, c.ComponentOrder
```

`ORDER BY s.Ranking` puts the worst statuses first, because `Orion.StatusInfo.Ranking` is
ordered by severity while the raw `Status` integers are not.

### Template inventory, including templates nobody uses

A `LEFT JOIN` is what makes this useful. An inner join answers "which templates are in
use"; the left join also surfaces the imported templates that were never assigned to
anything, which are the ones worth cleaning up.

```sql
SELECT
    t.ApplicationTemplateID,
    t.Name AS TemplateName,
    t.CustomApplicationType,
    COUNT(a.ApplicationID) AS AssignedApplications
FROM Orion.APM.ApplicationTemplate t
LEFT JOIN Orion.APM.Application a ON a.ApplicationTemplateID = t.ApplicationTemplateID
GROUP BY t.ApplicationTemplateID, t.Name, t.CustomApplicationType
ORDER BY COUNT(a.ApplicationID) DESC, t.Name
```

### What is inside a template before you assign it

Component monitors live in `Orion.APM.ComponentTemplate`, not `Orion.APM.Component`. This
is how you review a template, and how you find the `ID` you need to enable or disable an
individual monitor by updating its `IsDisabled` property.

```sql
SELECT
    ct.ID AS ComponentTemplateID,
    ct.Name AS ComponentTemplateName,
    ct.ComponentType,
    ct.Category.DisplayName AS CategoryName,
    ct.IsDisabled,
    ct.ComponentOrder
FROM Orion.APM.ComponentTemplate ct
WHERE ct.ApplicationTemplateID = @applicationTemplateId
ORDER BY ct.ComponentOrder
```

### Windows scheduled tasks that did not succeed

`State <> 1` covers Failed, Retry, and Cancelled in one filter, which is what an operator
actually wants; `State = 0` alone would miss the retries.

```sql
SELECT TOP 100
    t.Node.Caption AS NodeName,
    t.Application.Name AS ApplicationName,
    t.Name AS TaskName,
    t.State,
    t.LastRunResult,
    t.LastRunTime,
    t.NextRunTime,
    t.Author
FROM Orion.APM.Wstm.Task t
WHERE t.State <> 1
ORDER BY t.LastRunTime DESC
```

### SQL databases whose last backup is stale

`Orion.APM.SqlDatabase` navigates up through `SqlServer` to the application and on to the
node, so one query gives you the server name as well as the database.

```sql
SELECT TOP 50
    d.SqlServer.Node.Caption AS NodeName,
    d.SqlServer.InstanceName AS SqlInstance,
    d.Name AS DatabaseName,
    d.Status,
    d.DatabaseSize,
    d.TransactionLogSize,
    d.LastBackup,
    d.RecoveryModel
FROM Orion.APM.SqlDatabase d
WHERE d.LastBackup < AddDay(-1, GetDate())
ORDER BY d.LastBackup
```

### SQL data files close to full

`UsedSpacePercentage` is precomputed, so there is no need to divide `UsedSpace` by `Size`
yourself, and `AvailableAutoGrowSpace` tells you whether autogrowth can still save you.

```sql
SELECT TOP 50
    f.Database.SqlServer.Node.Caption AS NodeName,
    f.Database.Name AS DatabaseName,
    f.Name AS FileName,
    f.Size,
    f.UsedSpace,
    f.UsedSpacePercentage,
    f.AvailableAutoGrowSpace
FROM Orion.APM.SqlDatabaseFile f
WHERE f.UsedSpacePercentage > 80
ORDER BY f.UsedSpacePercentage DESC
```

### IIS sites with the pool they run in

The site and its application pool are separate entities, and an unresponsive site is very
often a stopped pool rather than a stopped site. Pull both states together.

```sql
SELECT
    s.Application.Node.Caption AS NodeName,
    s.Name AS SiteName,
    s.DisplayState,
    s.ApplicationPool.Name AS PoolName,
    s.ApplicationPool.DisplayState AS PoolState,
    s.AverageResponseTime,
    s.CurrentConnections
FROM Orion.APM.IIS.Site s
ORDER BY s.Application.Node.Caption, s.Name
```

### Active Directory replication that is failing

`ConsecutiveSyncFailureCount` is the column that distinguishes a transient blip from a
partnership that has genuinely stopped replicating.

```sql
SELECT
    r.SourceDomainControllerFqdn,
    r.DestinationDomainControllerFqdn,
    r.NamingContext.Name AS NamingContextName,
    r.TransportTypeDescription,
    r.ConsecutiveSyncFailureCount,
    r.LastSuccessTime,
    r.LastFailureTime,
    r.StatusDescription
FROM Orion.APM.ActiveDirectory.Replication r
WHERE r.ConsecutiveSyncFailureCount > 0
ORDER BY r.ConsecutiveSyncFailureCount DESC
```

### Application availability over the last week

`Orion.APM.ApplicationStatus` is a historical statistics table and is one of the larger
tables in the database. Time-bound it, always.

```sql
SELECT
    a.Name AS ApplicationName,
    a.Node.Caption AS NodeName,
    AVG(st.PercentAvailability) AS AvgPercentAvailability
FROM Orion.APM.ApplicationStatus st
JOIN Orion.APM.Application a ON a.ApplicationID = st.ApplicationID
WHERE st.TimeStamp >= AddDay(-7, GetDate())
GROUP BY a.Name, a.Node.Caption
ORDER BY AVG(st.PercentAvailability)
```

### Component thresholds as currently applied

```sql
SELECT TOP 50
    c.Application.Node.Caption AS NodeName,
    c.Application.Name AS ApplicationName,
    c.Name AS ComponentName,
    tbc.ThresholdName,
    tbc.Warning,
    tbc.Critical,
    tbc.ThresholdOperator
FROM Orion.APM.ThresholdsByComponent tbc
JOIN Orion.APM.Component c ON c.ComponentID = tbc.ComponentId
ORDER BY c.Application.Name, c.Name, tbc.ThresholdName
```

### TCP connections with the worst latency

```sql
SELECT TOP 50
    conn.ClientNode.Caption AS ClientNode,
    conn.ClientProcessName,
    conn.ServerNode.Caption AS ServerNode,
    conn.ServerProcessName,
    conn.ServerPort,
    conn.Latency,
    conn.PacketLoss,
    conn.LastSeenTimeStamp
FROM Orion.APM.ApplicationTcpConnection conn
WHERE conn.LastSeenTimeStamp >= AddHour(-24, GetDate())
ORDER BY conn.Latency DESC
```

More SAM samples live in
[../../scripts/swql/04-applications.swql](../../scripts/swql/04-applications.swql).

## Assigning a template from PowerShell

Adapted from SolarWinds' `Samples/PowerShell/SAM.Application.ps1`. The structure that
matters is: resolve every ID by name first, invoke on the **base** entity
`Orion.APM.Application`, and check the return value for `-1`.

```powershell
Import-Module SwisPowerShell
$swis = Connect-Swis -Hostname 'orion.example.com' -Credential (Get-Credential)

$nodeId = Get-SwisData $swis `
    "SELECT NodeID FROM Orion.Nodes WHERE IPAddress = @ip" @{ ip = '192.0.2.10' }

$applicationTemplateId = Get-SwisData $swis `
    "SELECT ApplicationTemplateID FROM Orion.APM.ApplicationTemplate WHERE Name = @template" `
    @{ template = 'Apache' }

$credentialSetId = Get-SwisData $swis `
    "SELECT ID FROM Orion.Credential WHERE CredentialOwner = 'APM' AND Name = @credential" `
    @{ credential = 'MyCredential' }

if (-not $nodeId -or -not $applicationTemplateId) { throw 'Node or template not found.' }

$applicationId = (Invoke-SwisVerb $swis 'Orion.APM.Application' 'CreateApplication' @(
    $nodeId,                 # nodeId
    $applicationTemplateId,  # applicationTemplateId
    $credentialSetId,        # credentialSetId
    'false'                  # skipIfDuplicate
)).InnerText

if ($applicationId -eq -1) {
    throw 'Not created: the template is already assigned to this node and duplicates were skipped.'
}

Invoke-SwisVerb $swis 'Orion.APM.Application' 'PollNow' @($applicationId) | Out-Null
```

`credentialSetId` accepts three magic values in addition to a real ID from the SAM
credential library, all documented by SolarWinds:

| Value | Meaning |
|---|---|
| `0` | `<None>` |
| `-3` | `<Inherit Windows credential from node>`, for WMI nodes only |
| `-4` | `<Inherit credentials from template>` |

Credentials from the library have `ID > 0` and are filtered with `CredentialOwner = 'APM'`:

```sql
SELECT ID, Name, CredentialType, CredentialOwner, Description
FROM Orion.Credential
WHERE CredentialOwner = 'APM'
ORDER BY Name
```

To pass AppInsight or template settings, add a fifth positional argument. From PowerShell
that is a hashtable, matching SolarWinds' `SAM.AppInsightAutomation` samples:

```powershell
$appSettings = @{}
$appSettings.Add('PortType', 'static')
$appSettings.Add('PortNumber', '1433')

$applicationId = (Invoke-SwisVerb $swis 'Orion.APM.Application' 'CreateApplication' @(
    $nodeId, $applicationTemplateId, $credentialSetId, 'true', $appSettings
)).InnerText
```

## Gotchas

**`Orion.APM.Application.Unmanage` misspells its first parameter as `netObjetId`,** missing
the `c`. This is real, it is in SolarWinds' own Swagger contract, and it is echoed in their
AppInsight documentation. Positional callers such as `Invoke-SwisVerb` are unaffected;
generated clients that bind by name are not.

**`netObjetId` wants `AA:<ApplicationID>`, not the bare ID.** The same applies to every
verb parameter named `netObjectId` or `netObject` across the platform.

**A component cannot reach its node directly.** Use `c.Application.Node`. There is no
`Orion.APM.Component.Node`.

**`Orion.APM.ThresholdsByComponent.ComponentId` has a lowercase `d`.** Every other
component key column in the namespace is `ComponentID`.

**`Orion.APM.SqlDatabaseFile` links to its database through `SqlDatabaseID`,** not
`DatabaseID`. The `Database` navigation property is safer.

**`Orion.APM.PortEvidence` carries six response-time columns, three of them misspelled.**
`MinResponceTime`, `AvgResponceTime`, and `MaxResponceTime` sit alongside the correctly
spelled `MinResponseTime`, `AvgResponseTime`, and `MaxResponseTime`. The schema documents
the first three as "Misspelling of ..." and keeps them for compatibility. Prefer the
correctly spelled versions.

**Verbs are declared on the base application entity, not on the AppInsight subtypes.**
`Orion.APM.SqlServerApplication`, `Orion.APM.GenericApplication`, and
`Orion.APM.Wstm.ScheduledTasksStatus` declare **zero** verbs of their own in the 2026.2
schema, and the Swagger contract has no `/Invoke/Orion.APM.SqlServerApplication/...` paths.
SolarWinds' AppInsight page nevertheless posts `CreateApplication`, `PollNow`, `Unmanage`
and `Remanage` to the derived entity paths, which implies the server resolves inherited
verbs on subtypes. *This behaviour is unverified here*: neither the schema nor the contract
records it. Invoking on `Orion.APM.Application` is documented and works for every subtype,
so prefer it. To check the derived path on your own server:

```sql
SELECT
    v.Entity.FullName AS EntityName,
    v.Name AS VerbName,
    v.CanInvoke
FROM Metadata.Verb v
WHERE v.Entity.FullName = 'Orion.APM.SqlServerApplication'
ORDER BY v.Name
```

**SolarWinds' AppInsight page contains three transcription errors** worth knowing before
you copy from it: the verb is `ScheduleConfiguration`, not `ScheduleConfiruation`; several
URLs are missing the slash in `/v3/Json/Invoke/`; and the Exchange section's heading says
"AppInsight for Active Directory" over the Exchange example. The verb names in this page
come from the extracted schema and the Swagger contract, not from that page.

**`SetupApplication` appears in a SolarWinds sample but not in the 2026.2 schema.** The
sample `SAM.AppInsightAutomation/SetupAppInsightApplication.ps1` invokes
`Orion.APM.Application.SetupApplication` with six arguments (`nodeName`, `nodeIp`,
`credentialSetId`, `applicationTemplateId`, `nodeId`, and a boolean). *This verb is not in
the extracted 2026.2 schema and not in the Swagger contract*, so it is unverified here. Use
`CreateApplication` unless you have confirmed `SetupApplication` exists on your version:

```sql
SELECT Position, Name, Type, IsOptional
FROM Metadata.VerbArgument
WHERE EntityName = 'Orion.APM.Application' AND VerbName = 'SetupApplication'
ORDER BY Position
```

**`CreateApplication` returns `-1`, not an error, when it skips a duplicate.** A script
that treats any return value as success will happily report creating an application that
does not exist.

**`DeleteTemplate` deletes every application created from the template.** So does deleting
the template through CRUD. Count first:

```sql
SELECT COUNT(a.ApplicationID) AS AffectedApplications
FROM Orion.APM.Application a
WHERE a.ApplicationTemplateID = @applicationTemplateId
```

**AppInsight template IDs are not stable across installations.** The IDs 10, 11, 12 and 13
that appear in SolarWinds' examples are from one lab server. Look them up by `Name` or by
`CustomApplicationType`.

**Account limitations silently filter results.** Two accounts running the same application
query get different rows, with no error and no warning. "The query returns nothing" is
frequently a permissions problem rather than a data problem.

**`Orion.APM.Application` is a base type, so it includes AppInsight applications.** If you
want only ordinary template-based applications, query
`Orion.APM.GenericApplication`, which the schema describes as filtering "black box"
applications out.

## See also

- [hardware-health.md](hardware-health.md) for the sensor data that appears on the same
  nodes SAM monitors, and which SAM is one of the two modules that enables.
- [README.md](README.md) for the index of every module page.
- [../platform/modules.md](../platform/modules.md) for the full module and namespace map.
- [../swis/crud.md](../swis/crud.md) for creating and updating the settings entities.
- [../swis/uris.md](../swis/uris.md) for the SWIS URI format, which is what
  `Set-SwisObject` needs when you edit a template or a setting in place.
- [../reference/verb-index.md](../reference/verb-index.md) for every verb with parameters.
- [../reference/netobject-types.md](../reference/netobject-types.md) for the NetObject
  prefix table.
- SolarWinds:
  [SAM Application Monitoring Templates](https://solarwinds.github.io/OrionSDK/docs/server-and-application-monitor/sam-application-monitoring-templates/)
  and
  [SAM AppInsight Applications](https://solarwinds.github.io/OrionSDK/docs/sam-appinsight-applications/).

# NCM: Network Configuration Manager

Network Configuration Manager is the module that logs in to a device rather than polling it.
Everything else in the platform reads SNMP, WMI, an API or an agent and stores numbers. NCM
opens a CLI session over SSH or Telnet, runs commands, pulls back the running and startup
configuration as text, keeps every revision, tells you what changed between two of them,
checks the text against compliance rules you wrote, and pushes configuration or firmware back
down when you tell it to.

That makes NCM the one module that routinely *writes to your network*. A mistake in an NPM
query produces a wrong graph. A mistake in an NCM script reboots a core switch. The verb
surface reflects that: 160 verbs across the two namespaces, more than any other module, and
almost all of them are gated by NCM's own role model on top of the ordinary Orion rights.

## Namespaces and how many entities

NCM contributes **129 entities** split across two prefixes, and the split confuses everybody
who meets it for the first time:

| Prefix | Entities | Verbs | What is in it |
|---|---|---|---|
| `Cirrus.` | 57 | 132 | The original NCM data model. Nodes, the config archive, compliance policies and reports, the approval queue, jobs, config change templates, comparison results, settings |
| `NCM.` | 72 | 28 | The newer model. A re-presentation of the shared inventory tables with proper identity and navigation, plus every feature added after the split: baselines, firmware upgrades, transfer results, ACL parsing, EoS refresh, config backup status |

`Cirrus` is the engineering codename the product shipped under, and it stayed. Do not read
anything into it beyond age: `Cirrus.*` is not deprecated, it is where most of the data and
almost all of the verbs still live.

```bash
python3 tools/schema_query.py find Cirrus
python3 tools/schema_query.py find "NCM."
python3 tools/schema_query.py show Cirrus.Nodes
```

### Reading the split correctly

Twenty five short names exist in **both** namespaces: `Nodes`, `NodeProperties`,
`ConfigArchive`, `Interfaces`, `IpAddresses`, `ArpTables`, `BridgePorts`, `MacForwarding`,
`RouteTable`, `VLANs`, `PortsTcp`, `PortsUdp`, `EntityLogical`, `EntityPhysical`,
`CatalystCards`, `CiscoCards`, `CiscoCdp`, `CiscoChassis`, `CiscoFlash`, `CiscoFlashFiles`,
`CiscoImageMIB`, `CiscoMemoryPools`, `WindowsAccounts`, `WindowsServices`, `WindowsSoftware`.
So `Cirrus.ArpTables` and `NCM.ArpTables` both exist, and both describe ARP tables.

Three measurable differences tell you which one to reach for, and none of them is arbitrary:

**1. Verbs live only on the `Cirrus.` side of a duplicated pair.** `Cirrus.Nodes` declares 25
verbs and `NCM.Nodes` declares zero. `Cirrus.ConfigArchive` declares 24 and
`NCM.ConfigArchive` declares zero. Across all 25 duplicated names, the `NCM.` copy declares no
verbs at all. If you are *doing* something rather than reading something, you are on the
`Cirrus.` side.

**2. Navigation lives almost entirely on the `NCM.` side.** `Cirrus.*` declares six navigation
properties in total across 57 entities. `NCM.*` declares 148 across 72. That is the real
reason the second namespace exists: the inventory tables were re-declared with a primary key
(`EntityID` on most of them) and wired into the platform's relationship graph, which the
originals never were.

The single most useful consequence is that **`Orion.Nodes` navigates into `NCM.`, not into
`Cirrus.`**:

```bash
python3 tools/schema_query.py path Orion.Nodes NCM.NodeProperties
python3 tools/schema_query.py path Orion.Nodes Cirrus.Nodes
```

The first prints `Orion.Nodes.NodeProperties`. The second prints "no navigation path within
3 hops", because there is none. `Orion.Nodes` declares exactly two navigation properties into
NCM:

| From `Orion.Nodes` | Leads to | Relationship |
|---|---|---|
| `NodeProperties` | `NCM.NodeProperties` | `Orion.NodesHostsNodeProperties` (hosting) |
| `NCMLicenseStatus` | `Cirrus.NCMNodeLicenseStatus` | `Orion.NodeHostLicensedByNCM` (hosting) |

**3. The `Cirrus.` copy of a duplicated entity is usually the wider one, and the `NCM.` copy
sometimes carries columns the original lacks.** `Cirrus.Nodes` has 66 properties and
`NCM.Nodes` has 48, and `NCM.Nodes` has none that `Cirrus.Nodes` lacks: the extra 18 are the
connection profile id, the SSH, Telnet and SNMP ports, the end-of-support block and
`StatusText`. `Cirrus.NodeProperties` has 40 against `NCM.NodeProperties`' 31, the extra nine
being live transfer state (`IsActiveTransfer`, `LastTransferDate`, `LastTransferMessage` and
friends) plus EoS matching columns. But it does not run one way only:
`NCM.Interfaces` adds `InterfaceHighSpeed`, `VLANID`, `VlanType` and `PortStatus` that
`Cirrus.Interfaces` does not have, and `NCM.ConfigArchive` carries `AdditionalCommands`
while `Cirrus.ConfigArchive` carries `BaseConfigID`. Check before you assume.

### The working rule

- Reading inventory, and joining from a platform node: use `NCM.*` and its navigation
  properties.
- Reading NCM's own operational state (nodes, configs, compliance, jobs, approvals): use
  `Cirrus.*`, because that is where the columns are.
- Invoking anything: use `Cirrus.*`, unless the feature is baselines, firmware, EoS refresh,
  config types or vulnerabilities, which are `NCM.*` only.
- Writing through CRUD: `Cirrus.Nodes`, `Cirrus.NodeProperties` and `NCM.Nodes` allow
  `update`; `Cirrus.IgnoredNodes`, `NCM.Baselines`, `NCM.BaselineNodeMap`,
  `NCM.FirmwareOperations`, `NCM.FirmwareOperationNodes`, `NCM.FirmwareUpgradeImages`,
  `NCM.FirmwareUpgradeMachineTypes` and `NCM.ConfigTypeVendors` allow `create` and `delete`.
  Nothing else in either namespace does.

## `Cirrus.Nodes` and its relationship to `Orion.Nodes`

NCM keeps its own node table, and it is not `Orion.Nodes`.

| Fact | Value |
|---|---|
| Key property | `NodeID`, a `System.Guid` |
| Link to the platform | `CoreNodeID`, a `System.Int32` matching `Orion.Nodes.NodeID` |
| NetObject prefix | None. [`netobject-types.json`](../../data/reference/netobject-types.json) records an empty prefix for `Cirrus.Nodes`, so NCM node ids never appear in `N:42` form |
| Caption column | `NodeCaption`, mirroring `Orion.Nodes.Caption` |
| Properties | 66 declared |
| Operations | `read`, `update`, `invoke`. No create and no delete: nodes join and leave NCM through the `AddNodeToNCM` and `RemoveNode` verbs |
| Rights | `read` and `invoke` for everyone; `update` requires `manageNodes`, plus the NCM role stated in each verb summary |

Joining the two id spaces wrongly is the single most common NCM query bug, and it fails
silently: a GUID never equals an integer, so the query returns nothing and no error.
[`../swql/language-reference.md`](../swql/language-reference.md#full-outer-join) says the same
thing from the SWQL side.

Many `Cirrus.Nodes` columns are copies of the `Orion.Nodes` value, and the schema says so
explicitly in each summary: `NodeCaption` is "the Orion.Nodes Caption value", `SysDescr` is
"the Orion.Nodes Description value", `SNMPPort` is "the Orion.Nodes AgentPort value",
`LastUpdateTime` is "the Orion.Nodes LastSync value". Treat those as a cache. The
authoritative value is on the platform node.

The columns that are genuinely NCM's own are the ones about talking to the device:

**Credentials.** `Username`, `Password`, `EnableLevel`, `EnablePassword`, `SNMPUsername`,
`SNMPAuthType`, `SNMPAuthPass`, `SNMPEncryptType`, `SNMPEncryptPass`, `Community`,
`CommunityReadWrite`, `UseUserDeviceCredentials`. These are stored encrypted, and
`Cirrus.Settings.DecryptData(data)` exists. Never select them into a report, a log or a
dashboard.

**Transport.** `ExecProtocol` (used to run commands), `CommandProtocol` (used to request the
configuration) and `TransferProtocol` (used to move the configuration) are three separate
choices, which is why a node can log in fine and still fail a download.
`TelnetPort`, `SSHPort`, `SNMPPort`, `EncryptionAlgorithm`, `UseKeybInteractiveAuth` and
`AllowIntermediary` complete the set. `AllowIntermediary` sends extra CRLF for TACACS and
RADIUS prompts.

**State.** `LoginStatus` is the free-text result of the last connection attempt and is the
first thing to look at when downloads stop working. `LastInventory` is when inventory last
ran. `ConnectionProfile` is the id of the assigned profile, with `-1` and `0` carrying special
meanings covered under [Connection profiles](#connection-profiles).

**End of support.** `EndOfSupport`, `EndOfSales`, `EndOfSoftware`, `EosEntryID`, `EosType`,
`EosMatchDate`, `EosVersion`, `EosLink`, `EosComments`, `ReplacementPartNumber`.

`Cirrus.Nodes` has exactly one navigation property, `Interfaces`, leading to
`Cirrus.Interfaces`. Everything else you reach by joining on `NodeID` or `CoreNodeID`.

## Configuration archives

`Cirrus.ConfigArchive` is one row per captured configuration revision, and it is where NCM's
value actually sits.

| Property | Type | Notes |
|---|---|---|
| `ConfigID` | `System.Guid` | Primary key. This is what every config verb takes |
| `NodeID` | `System.Guid` | The NCM node, not the Orion node |
| `BaseConfigID` | `System.Guid` | The config this one was derived from, for clones |
| `ConfigTitle` | `System.String` | Display title |
| `ConfigType` | `System.String` | `Running`, `Startup` or a custom type, matched by name |
| `Config` | `System.String` | The entire device configuration as text |
| `DownloadTime` | `System.DateTime` | When the capture succeeded |
| `AttemptedDownloadTime` | `System.DateTime` | When the capture was triggered |
| `ModifiedTime` | `System.DateTime` | Last edit to the archived text |
| `Baseline` | `System.Boolean` | Whether this revision is flagged as the baseline |
| `IsBinary`, `IsIndexed`, `Hash`, `Comments` | | Storage and search bookkeeping |

Two things about this entity bite people. First, **`Config` holds the whole configuration**,
so selecting it across a hundred rows is megabytes of text through the API. Never put it in a
listing; select it for one `ConfigID` at a time. Second, **`AttemptedDownloadTime` moving
ahead of `DownloadTime` is the signature of a failed capture**, which is a far more reliable
failure detector than looking at `LoginStatus`.

`Cirrus.ConfigArchive` declares **no supported operations at all**: no create, no update, no
delete. Everything that changes the archive goes through its 24 verbs. `NCM.ConfigArchive` is
the navigable twin, inheriting from `Orion.LogEntity` (so it also carries
`ObservationTimestamp`, `ObservationSeverity` and `ObservationSeverityName`) and reaching the
platform node through `NodeProperties.Nodes`.

Config types themselves are an entity: `NCM.ConfigTypes` has `Id`, `Name` and `IsCustom`, with
`CreateCustom(name)`, `UpdateCustomName(id, newName)` and `DeleteCustom(id)` verbs.
`NCM.ConfigTypeVendors` restricts a type to particular vendors, with an `Operation` of `0` for
EqualsTo and `1` for DifferentFrom.

## Transfers: how NCM reports what it did to a device

Every download, upload and script execution is a **transfer**, and every transfer produces a
ticket. `NCM.TransferResults` is the status table, and it is the entity you poll after
invoking anything that touches a device.

| Property | Notes |
|---|---|
| `TransferID` | `System.Guid`. The verbs return these; this is your handle |
| `NodeID` | NCM node id |
| `Action` | `1` Download, `2` Upload, `3` Execute script |
| `Status` | `0` Queued, `1` Transferring, `2` Complete, `3` Error |
| `ErrorMessage` | Populated only when `Status = 3` |
| `DeviceOutput` | The text the device produced. This is where script output lands |
| `ConfigID` | Populated for downloads: the new row in the config archive |
| `RequestedConfigType`, `RequestedScript`, `RequestedReboot`, `TransferProtocol`, `DateTime`, `UserName` | What was asked for, and by whom |
| `JobId`, `SubJobId`, `FirmwareUpgradeOperationId` | Set when the transfer came from a job or a firmware operation rather than a direct call |

It navigates both ways: `NCM.TransferResults.ConfigArchive` leads to `Cirrus.ConfigArchive`
and `NCM.TransferResults.NodeProperties` leads to `NCM.NodeProperties`, from where
`.Nodes` reaches `Orion.Nodes`. Going the other way, `Cirrus.ConfigArchive.TransferResults`
walks from a config to the transfers that produced or referenced it. Those two are the only
cross-namespace navigation properties in the whole module.

Two summary entities sit on top: `NCM.LatestTransferJobStatus` gives the most recent transfer
state per node and job, and `NCM.ConfigBackupStatus` gives a per node, per config type view
with `BackupStatus` of `1` for success, `14` for failed and `3` for never backed up, plus
`LastSuccessfulBackupDate`. `NCM.ConfigBackupStatistic` and `Cirrus.Backup_vs_AllNodes` hold
the rolled-up coverage numbers behind the dashboard resources.

See the official [NCM Config Transfer](https://solarwinds.github.io/OrionSDK/docs/network-configuration-manager/ncm-config-transfer/)
page, which documents this API from SolarWinds' own side.

## Comparison and diff results

NCM compares configurations continuously and caches the answers rather than diffing on demand.

`Cirrus.CacheDiffResults` is one row per comparison: `NodeID`, `ConfigID`, `DiffFlag` (whether
anything differs at all), `DiffList` (the differing lines), `ConfigTitleBefore` and
`ConfigTitle`, `ConfigTypeBefore` and `ConfigType`, `DiffWidth`, and `ComparisonType`, which
the schema documents as `1` RunningToStartup, `2` RunningToLastBaseline, `3`
MostRecentToLastOfAnyType, `4` MostRecentToLastOfTheSameType.

`Cirrus.LatestComparisonResults` is the current position, one row per node, config type and
comparison type, carrying only `DiffFlag`. Its `ComparisonType` is documented with the **same
four names based at zero rather than one**, which is covered under
[Gotchas](#gotchas). `Cirrus.ComparisonCache` timestamps each cache generation.

`Cirrus.CompareRegExs` holds the patterns that tell the comparer what to ignore, which is how
you stop a timestamp line or an encrypted password hash from showing up as a change every
poll. `RegEx` is the GNU form, `DotNetRegEx` the .NET form, `IsBlock` and `BlockEndRegEx`
handle skipping a whole block, and `Enabled` turns one off. They are managed through
`Cirrus.Settings.SaveRegExPattern`, `GetRegExes`, `GetRegExById`,
`EnableOrDisableRegExPatterns` and `DeleteRegExPatterns`.

For an on-demand comparison there are two verbs on `Cirrus.ConfigArchive`:
`Diff(configId1, configId2)`, which returns a `System.Data.DataTable`, and
`CompareConfigs(configId1, configId2, settings)`, which takes a
`TextDiffEngineSettings` and returns a structured `TextDocumentDiff`.
`Cirrus.Nodes.ExecuteConfigChangeReportAction(nodeId, comparisonType)` runs the change report
for one node; its `comparisonType` argument is the string enum
`RunningToStartup`, `RunningToLastBaseline`, `MostRecentToLastOfAnyType` or
`MostRecentToLastOfTheSameType`.

## Baselines

There are two different things called a baseline, and they are not the same feature.

**Per-config baselines** are the older idea: a flag on a row in the config archive.
`Cirrus.ConfigArchive.Baseline` is that boolean, and
`Cirrus.ConfigArchive.SetClearBaseline(ConfigIds)` toggles it for a set of configs. Comparison
type `RunningToLastBaseline` compares against this.

**Multi-node baselines** are the newer `NCM.*` feature: a block of expected configuration text
that many devices are checked against.

| Entity | Contents |
|---|---|
| `NCM.Baselines` | `Id`, `Name`, `Content` (the expected text), `Description`, `ExactMatching`, `UseComparisonCriterias`, `IgnoredLines`, `Disabled`. Full CRUD, `admin` right |
| `NCM.BaselineNodeMap` | Assignment: `BaselineId`, `NodeId`, `ConfigType`, plus `CacheState` (`0` needs recalculation, `1` calculating, `2` done, `3` error). Full CRUD, `admin` right |
| `NCM.BaselineViolations` | Result: `BaselineId`, `NodeId`, `ConfigID`, `ConfigType`, `IsViolation`. Writable only by the `system` right, so treat it as read-only |

Baselines have no verbs. You create one by creating a row in `NCM.Baselines`, assign it by
creating rows in `NCM.BaselineNodeMap`, and read the answer from `NCM.BaselineViolations`.
That makes them one of the few NCM features that is pure CRUD; see
[../swis/crud.md](../swis/crud.md).

## Compliance: policies, rules, reports and violations

Compliance is a four-level structure, and the names are easy to mix up because the noun
"policy" appears at three of the four levels.

```
Cirrus.PolicyReports          a report: a named collection of policies
  └─ Cirrus.PolicyAssignment  join table: PolicyReportID  <-> PolicyID
      └─ Cirrus.Policies      a policy: which nodes and which config type it applies to
          └─ Cirrus.PolicyRuleAssignment   join table: PolicyID <-> PolicyRuleID
              └─ Cirrus.PolicyRules        a rule: the pattern that must or must not match
```

`Cirrus.PolicyRules` is where the actual test is. `Pattern` holds the text,
`PatternType` is `'Like'` or `'Regex'`, `PatternMustExist` flips the sense of the test, and
`ErrorLevel` sets the severity. The remediation half of the rule is on the same row:
`RemediateScript`, `RemediateScriptType` (normal CLI or a config change template),
`ExecuteScriptAutomatically`, `ExecuteRemediationScriptPerBlock` and
`ExecuteScriptInConfigMode`. A rule that automatically pushes configuration to a device when
it fails is a rule you should know exists before you inherit somebody else's server.

`Cirrus.Policies` carries `NodeSelection`, an XML document describing which nodes the policy
covers, and `ConfigType`, restricting it to one type of configuration.

Results come out in three shapes:

- `Cirrus.PolicyCacheResults` is the detail: one row per node, report, policy and rule, with
  `IsViolation`, `ErrorLevel`, `ConfigID`, `ConfigTitle`, `FoundLine`, `FoundLineNumber` and
  an `XmlResults` blob. This is the entity you query when you want to know *what* is wrong.
- `Cirrus.PolicyReportViolations` is the history: counts of `Error`, `Warning` and `Info` per
  report per `TimeStamp`, with a `Granularity` column. These are tallies, not flags.
- `Cirrus.LatestPolicyReportViolations` is the same counts for the current position only.

Results are cached rather than computed live. `Cirrus.PolicyReports.CacheStatus` tells you
where a report is: `0` not cached, `1` waiting in a queue, `2` caching now, `3` cached, `4`
error, `5` queued but unused. `LastUpdated` is when the cache was last refreshed and
`LastError` carries the failure message. A compliance query that returns stale numbers is
almost always a stale cache rather than a stale device.

## Config change templates and snippets

What the web console calls a **config change template** is `Cirrus.ConfigSnippets` in the API.
The entity summary of `Cirrus.Tags` gives the game away: "Data about tags in config change
templates", and `Cirrus.Tags` joins to `Cirrus.ConfigSnippets` on `SnippetID`.

`Cirrus.ConfigSnippets` carries `ID`, `Name`, `Description`, `AdvancedScript` (the template
body), `Created`, `LastModified` and `PreserveWhiteSpace`. Its 11 verbs cover the whole
lifecycle: `AddSnippet`, `GetSnippet`, `UpdateSnippet`, `SaveSnippetAsCopy`, `CopySnippets`,
`DeleteSnippets`, `ImportSnippets`, plus `AddTags`, `DeleteTags`, `GetTagsList` and
`GetTagsListForSnippets`.

`Cirrus.SnippetArchive` is a different and confusingly named entity: it is an archive of
snippet *configs* keyed by `ConfigID`, with its own `AddSnippet`, `UpdateSnippet` and
`DeleteSnippet` verbs requiring the Administrator NCM role. Do not reach for it when you meant
`Cirrus.ConfigSnippets`.

`Cirrus.Nodes.ParseMacros(nodeId, macro)` expands NCM's macro syntax against one node, which
is how you preview what a template will actually send before you send it.
`Cirrus.Settings.SetCustomMacros`, `DeleteCustomMacros` and `SetGlobalMacroForAllNodes` manage
the macro definitions themselves.

## Connection profiles

A connection profile is a named bundle of CLI credentials and protocol choices that many nodes
share, so you are not storing the same password on 400 node rows. SolarWinds documents this
well in [NCM Connection Profiles](https://solarwinds.github.io/OrionSDK/docs/network-configuration-manager/ncm-connection-profiles/),
and the shape below matches the 2026.2 Swagger contract.

The profile is **not an entity**. There is no `Cirrus.ConnectionProfiles` to query. It exists
only as a contract type moved in and out through five verbs on `Cirrus.Nodes`:

| Verb | Parameters, in order | Returns |
|---|---|---|
| `GetAllConnectionProfiles` | none | array of `ConnectionProfile` |
| `GetConnectionProfile` | `id` | one `ConnectionProfile` |
| `AddConnectionProfile` | `profile` | the new profile id, a number |
| `UpdateConnectionProfile` | `profile` (with `ID` filled in) | void |
| `DeleteConnectionProfile` | `id` | void |

The `ConnectionProfile` type carries `ID`, `Name`, `UserName`, `Password`, `EnableLevel`,
`EnablePassword`, `ExecuteScriptProtocol`, `RequestConfigProtocol`, `TransferConfigProtocol`,
`TelnetPort`, `SSHPort`, `UseForAutoDetect` and a nested `ConnectionData` object. Note that
the three protocol fields on the profile are named differently from the three equivalent
columns on `Cirrus.Nodes`, which are `ExecProtocol`, `CommandProtocol` and `TransferProtocol`.

**Assigning a profile is a CRUD update, not a verb.** Set `Cirrus.Nodes.ConnectionProfile` to
the profile id through `Set-SwisObject` or a REST `POST` to the node's URI. Two values are
special:

- `-1` means no profile is assigned and the node's own credential columns are used.
- `0` means auto detect, which requires at least one profile with `UseForAutoDetect` set.

Auto detection also depends on **device templates**, which live in a third namespace,
`Cli.*`. `Cli.DeviceTemplates` holds `TemplateName`, `SystemOID`, `SystemDescriptionRegex`,
`TemplateXml`, `UseForAutoDetect`, `IsDefault` and `AutoDetectType` (`0` matches on system
OID, `1` on system description). `Cli.DeviceTemplatesNodes` assigns one manually to a node,
and its summary states the consequence plainly: each node can have only one device template,
and a manual assignment disables auto detection for that node. Both support full CRUD under
`manageNodes`. The `deviceTemplateXML` argument that
`Cirrus.ConfigArchive.DownloadConfigOnNodes` and `ExecuteScriptOnNodes` take is
`Cli.DeviceTemplates.TemplateXml`.

## The approval queue

If approvals are switched on, a config upload or a script execution does not run when it is
requested. It becomes a ticket.

`Cirrus.ApproveQueue` is one row per request: `ID`, `UserName`, `RequestType` (one of
`"Execute Config Change Template"`, `"Execute Script"`, `"Upload Config"`,
`"Manage EnergyWise"`), `Script`, `ConfigType`, `Reboot`, `DateTime`, `Comments`, `RunAt`,
`NCMJobID`, `ApprovedBy` and `StatusChangeTime`.

`RequestStatus` is the state machine:

| Value | Meaning |
|---|---|
| 0 | Pending approval |
| 1 | Declined |
| 2 | Approved and returned to the requestor to execute |
| 3 | Approved and scheduled for execution |
| 4 | Already executed |
| 5 | Approved and executing now |
| 6 | Approved by one approver, waiting on a second |

`ExecutionType` controls what happens on approval: `0` execute immediately, `1` return the
ticket to the requestor, `2` wait and then execute. `Cirrus.ApproveQueueNodes` lists the
target nodes for a request, and `Cirrus.NCM_ApproveQueueView` is a view over the same columns.

The 12 verbs are `AddRequest`, `UpdateRequest`, `ApproveRequest`, `DeclineRequest`,
`DeleteRequest`, `GetRequest`, `GetTicketStatus`, `GetApprovalUsers`, `UpdateApprovalUsers`,
`GetUserApproveRole`, `GetApprovalMode` and `SetApprovalMode`. The three that take a `ticket`
want a full `NCMApprovalTicket` object; the rest take a ticket id or a user id as a string.
`GetApprovalMode` and `SetApprovalMode` use the string enum `ApprovalDisabled`, `OneLevel`,
`TwoLevelWebUploader` or `TwoLevelAll`, and `GetTicketStatus` returns `PendingApproval`,
`Declined`, `WaitingForExecution`, `Scheduled`, `Complete`, `Executing` or `NeedConfirmation`.

Note that `Cirrus.ApproveQueue` is flagged read-only in the schema and declares no CRUD
operations, yet exposes twelve verbs. That combination is normal in NCM and means exactly what
it says: you may not `POST` a row, but you may ask the module to create one for you.

## Firmware upgrade

Firmware upgrade is `NCM.*` only, and it is a two-phase operation by design: you prepare, you
review, then you start.

| Entity | Contents |
|---|---|
| `NCM.FirmwareDefinitions` | The recipe: `Name`, `Description`, `DefinitionXml`, `Author`, `Canned`, `LastModified`. Four verbs for the lifecycle |
| `NCM.FirmwareUpgradeImages` | The image files: `FileName`, `RelativePath`, `MD5Hash`, `Size`, `CoreNodeID`, `DateTimeUtc` |
| `NCM.FirmwareUpgradeMachineTypes` | Which `MachineType` each `ImageID` is applicable to |
| `NCM.FirmwareOperations` | One run: `ID`, `Name`, `DefinitionID`, `CreationDate`, `RunAt`, `Status`, `ErrorMessage`, `Log`, `EmailSettings`, `UserName` |
| `NCM.FirmwareOperationNodes` | Per-node state within a run: `OperationID`, `CoreNodeID`, `NodeOptionsXml`, `IsComplete`, `Log` |
| `NCM.FirmwareOperationsView` | The same run with `CompletedOperations` and `AllOperations` counts |
| `NCM.FirmwareStorage` | Verbs only: `ValidateFirmwareStorage`, `UpdateFirmwareImage`, `DeleteFirmwareImages` |

`NCM.FirmwareOperations.Status` runs `0` Unknown, `1` Error, `2` CollectingData, `3`
NeedsReview, `4` Queued, `5` Upgrading, `6` Complete, `7` Scheduled. The `NeedsReview` state
is the pause between the two phases and is the point of the design: `PrepareFirmwareUpgrade`
collects what is on the devices and returns an operation id, and nothing reaches a device
until `StartUpgrade` is called against that id.

```bash
python3 tools/schema_query.py verb NCM.FirmwareOperations PrepareFirmwareUpgrade
python3 tools/schema_query.py verb NCM.FirmwareOperations StartUpgrade
```

`PrepareFirmwareUpgrade(coreNodeIds, firmwareDefinitionId, firmwareOperationName,
imagesToApply)` takes **Orion** node ids as integers. `StartUpgrade(operationId, nodeOptions,
runAt, emailSettings)` takes an array of `UpgradeNodeOptions`, one per node, and a `runAt`
timestamp where null queues the upgrade immediately. `GenerateScriptPreview(nodeOptions)`
renders what will be sent without sending it, `PrepareRollBack(operationId)` and
`PrepareReExecuteFailed(operationId)` create follow-up operations, and
`CancelUpgrade(operationIds)` stops one.

## End of life, end of sales, end of support

The EoS block on `Cirrus.Nodes` (`EndOfSupport`, `EndOfSales`, `EndOfSoftware`,
`ReplacementPartNumber`) is populated by a matching process, and `EosType` records how each
row got its values: `0` not assigned, `1` user, `2` manual, `3` auto, `4` awaiting, `5` node
ignored.

`Cirrus.NCM_EosMatchQueue` is the matching workspace and carries the part that matters when
you are deciding whether to trust an automatic match: `Rank`, and the `Certainty` label
derived from it, documented as `'Good'` above rank 100 and lower labels below. It also carries
`EosModel`, `PartNumber`, `ReplacementPartNumber` and `EosLink`.

Four verbs on `NCM.Eos` drive the refresh: `RefreshNow(nodeIds)` takes **NCM** node GUIDs,
`BeginRefreshAll()` refreshes everything, `IsRefreshingAll()` reports whether one is running,
and `InitSchedule()` sets up the recurring refresh. On `Cirrus.Nodes`,
`AssignEOSEntry(nodeIds, endOfSupport, endOfSales, endOfSoftware, entryId, type, version,
link, comments, replacementPartNumber)` writes a match by hand, `ChangeEOSType(nodeIds, type)`
changes how a set of nodes is classified, and `DeleteEOSData(nodeIds)` clears it. The `type`
argument is the string enum `NotAssigned`, `User`, `Manual`, `Auto`, `Awaiting` or `Ignored`.

Vulnerability data used to live alongside EoS in `NCM.VulnerabilitiesAnnouncements` and
`NCM.VulnerabilitiesAnnouncementsNodes`. **Both are marked obsolete in 2026.2**, and the
schema names the successor: `Orion.SecObs.Vulnerabilities.Cves`. The four verbs
(`StartVulnerabilityMatching`, `IsVulnerabilityMatchingActive`, `InitVulnerabilitySchedule`,
`GetSettings`) and the `Cirrus.Nodes` vulnerability verbs still exist, but do not build
anything new on them.

## Jobs

NCM schedules its own work rather than using the platform's scheduler.
`Cirrus.NCM_NCMJobs` holds the definition (`NCMJobDefinitionXML`, `NCMJobSchedule`,
`NCMJobType`, `Enabled`, `IsHidden`) and carries the nine verbs: `AddJob`, `GetJob`,
`UpdateJob`, `DeleteJobs`, `EnableOrDisableJobs`, `GetJobStatus`, `GetJobLog`, `ClearJobLog`
and `ValidateJobsAccess`. `Cirrus.NCM_NCMJobsView` adds the runtime columns you actually want
to report on: `LastDateRun`, `NextDateRunUtc`, `Status`, `CompletedSubJobs`, `AllSubJobs` and
`JobEndsWithGeneralError`.

`NCMJobType` enumerates what NCM can be told to do on a schedule, and reading the list is the
fastest way to understand the module's scope: `0` command script, `1` execute program, `2`
upload configurations, `3` report, `4` reboot devices, `5` export configurations, `6` NCM
database maintenance, `7` inventory, `8` config change reports, `9` compliance policy reports,
`10` purge configurations, `11` download configurations, `12` real-time notifications, `13`
Orion import, `14` baseline entire network, `15` config change template, `16` error.

`Status` on the view runs `0` unknown, `1` running now, `2` disabled, `3` scheduled for job
engine, `4` not scheduled yet, `5` waiting in job engine, `6` starting now, `7` completed.
`Cirrus.NCM_JobEngineNCMJobs` is the link into the platform job engine.

## Inventory and parsed configuration

Beyond configuration text, NCM runs an inventory that fills a wide set of read-only tables.
The `NCM.` copies are the navigable ones, each reaching `NCM.Nodes` through a `Node`
navigation property and `NCM.NodeProperties` through a `NodeProperties` one.

| Family | Entities |
|---|---|
| Layer 2 and 3 | `Interfaces`, `IpAddresses`, `ArpTables`, `BridgePorts`, `MacForwarding`, `RouteTable`, `VLANs`, `CATOSPorts` |
| Ports and software | `PortsTcp`, `PortsUdp`, `WindowsAccounts`, `WindowsServices`, `WindowsSoftware` |
| Cisco hardware | `CiscoChassis`, `CiscoCards`, `CatalystCards`, `CiscoFlash`, `CiscoFlashFiles`, `CiscoImageMIB`, `CiscoMemoryPools`, `CiscoCdp`, `CiscoBootloadImages`, `CiscoFruPowerStatus`, `CiscoFruFanTrayStatus`, `CiscoFruPowerSupplyGroups` |
| Entity MIB | `EntityPhysical`, `EntityLogical`, `EntityPhysicalJuniper` |
| Vendor specific | `F5System`, `F5LTMVirtualServers`, `F5GTMVirtualServers`, `F5LTMNodeAddresses`, `BrocadeChassis`, `BrocadeChassisUnit`, `BrocadeAgentConfigModule` |

NCM also parses the configuration text it captured. `NCM.AccessList` is one row per detected
ACL with `Name`, `Complexity`, `Interfaces` and a `Hash` that changes when the ACL does.
`NCM.ObjectGroupData` and `NCM.ObjectDefinitionData` hold the parsed object groups.
`NCM.ShadowRuleDetectionResult`, `NCM.AceShadowRuleDetectionResult`, `NCM.RuleDetection` and
`NCM.ShadowRuleDetectionAclStatistics` hold shadow and redundancy analysis, with
`NCM.RuleDetection.OverlappingType` of `0` unique, `1` shadowed and `2` partially overlapping.
`NCM.ParsedConfigData` holds a NETCONF-like XML rendering of a config, and
`NCM.ConfigInterface` links a config back to the interfaces named inside it.

`NCM.RTNAudit` records real-time change notifications, the syslog-triggered "someone just
changed something" events, with `NodeID`, `IP` and `Message`. `Cirrus.RTN` carries the two
verbs behind it, `ExecuteRtn(ipAddress, commandLine)` and `RunRtn(args)`.

## Verbs

NCM declares **160 verbs**, 132 in `Cirrus.` and 28 in `NCM.`. That is the richest verb
surface in the platform, and it is concentrated: nine `Cirrus.` entities and eight `NCM.`
entities carry all of them.

| Entity | Verbs | Theme |
|---|---|---|
| `Cirrus.PolicyReports` | 26 | Compliance policies, rules, reports, caching, remediation |
| `Cirrus.Nodes` | 25 | Membership, connection profiles, EoS, vulnerabilities, macros |
| `Cirrus.ConfigArchive` | 24 | Download, upload, execute, search, diff, import |
| `Cirrus.Settings` | 20 | Module settings, comparison regexes, macros, encryption |
| `Cirrus.ApproveQueue` | 12 | The approval workflow |
| `Cirrus.ConfigSnippets` | 11 | Config change templates and their tags |
| `Cirrus.NCM_NCMJobs` | 9 | Job definitions, status and logs |
| `Cirrus.SnippetArchive` | 3 | Snippet archive |
| `Cirrus.RTN` | 2 | Real-time notification |
| `NCM.FirmwareOperations` | 7 | Firmware upgrade lifecycle |
| `NCM.Eos` | 4 | End-of-support refresh |
| `NCM.FirmwareDefinitions` | 4 | Firmware definitions |
| `NCM.VulnerabilitiesAnnouncements` | 4 | Obsolete; see above |
| `NCM.ConfigTypes` | 3 | Custom config types |
| `NCM.FirmwareStorage` | 3 | Firmware image storage |
| `NCM.OneTimeOperations` | 2 | AI-generated one-time operations |
| `NCM.SecurityPolicy` | 1 | `GetSecurityPolicyAppIds` |

Arguments are positional. Names appear in the schema and in the Swagger contract, never on the
wire, so the order below is the entire contract. Check any verb before calling it:

```bash
python3 tools/schema_query.py verbs --entity Cirrus.ConfigArchive
python3 tools/schema_query.py verb Cirrus.ConfigArchive DownloadConfig
```

### Membership: putting nodes into NCM and taking them out

| Verb | Parameters, in order | Notes |
|---|---|---|
| `Cirrus.Nodes.AddNodeToNCM` | `coreNodeId` (number) | The **Orion** node id. Returns the new NCM `NodeID` as a string |
| `Cirrus.Nodes.AddNodes` | `coreNodeIds` (array of number) | Batch form. Returns a boolean |
| `Cirrus.Nodes.RemoveNode` | `nodeId` (GUID string) | The **NCM** node id. Removes from NCM only, not from Orion |
| `Cirrus.Nodes.RemoveNodes` | `ncmNodeIds` (array of GUID) | Batch form |
| `Cirrus.Nodes.GetNode` | `nodeId` (GUID string) | Returns the `NCMNode` model |
| `Cirrus.Nodes.UpdateNode` | `node` (`NCMNode`) | **Overwrites every property.** `GetNode`, modify, `UpdateNode` |
| `Cirrus.Nodes.AddNode` | `node` (`NCMNode`) | The schema itself says "not recommended, use AddNodeToNCM instead" |
| `Cirrus.Nodes.ValidateLogin` | `engineId`, `node`, `ipAddress`, `deviceTemplate` | Tests credentials from a named polling engine |

The id types alternate deliberately: adding takes Orion integers because the node already
exists on the platform, removing takes NCM GUIDs because by then it has an NCM identity.
`Cirrus.IgnoredNodes` is the opposite list, a create-and-delete entity holding `CoreNodeID`
values that NCM discovery should skip.

`Cirrus.Nodes.CheckAPLicence()` tests the current poller licence and
`DeleteOverLicenseNodes()` deletes random nodes above the licence limit. Read that second one
twice: it is destructive, it chooses for you, and it takes no arguments.

### Config transfer: download, upload, execute

| Verb | Parameters, in order | Returns |
|---|---|---|
| `DownloadConfig` | `nodeId` (array of NCM GUID), `configType` (string) | Array of `TransferID` |
| `DownloadConfigOnNodes` | `nodes` (array of `NCMNode`), `deviceTemplateXML`, `configType` | Array of `TransferID` |
| `UploadConfig` | `nodeId` (array of NCM GUID), `configType`, `ConfigText`, `RebootDevice` (boolean) | Array of `TransferID` |
| `UploadConfigPerNode` | `nodesScript` (array of `NCMNodeScript`), `configType`, `reboot` (optional) | Array of `TransferID` |
| `ExecuteScript` | `nodeId` (array of NCM GUID), `script`, `Reboot` (optional boolean) | Array of `TransferID` |
| `ExecuteScriptOnNodes` | `nodes` (array of `NCMNode`), `deviceTemplateXML`, `script` | Array of `TransferID` |
| `ExecuteScriptPerNode` | `nodesScript` (array of `NCMNodeScript`), `reboot` (optional) | Array of `TransferID` |
| `ReExecute` | `tickets` (array of `TransferID`) | Array of `TransferID` |
| `CancelTransfers` | `TransferTickets` (array of `TransferID`) | void |

All of these are on `Cirrus.ConfigArchive`, all of them are asynchronous, and all of them
return transfer tickets rather than results. `NCMNodeScript` is a two-field object, `NodeId`
and `Script`, which is how the `PerNode` variants send a different script to each device.

The plain forms (`DownloadConfig`, `UploadConfig`, `ExecuteScript`) let NCM look up each
node's stored credentials and device template. The `OnNodes` forms make you supply the
`NCMNode` objects and the device template XML yourself, which is what you want when you are
testing credentials that are not saved yet.

### Archive management

| Verb | Parameters, in order |
|---|---|
| `ImportConfig` | `nodeId` (GUID), `title`, `comments`, `configText` |
| `ImportBinaryConfig` | `nodeId` (GUID), `title`, `comments`, `binaryConfig` (byte array) |
| `CloneConfig` | `parentConfigID`, `title`, `comments`, `configText` |
| `UpdateConfig` | `configID`, `title`, `comments`, `configText`, `updateConfigText` (boolean), `UserName` |
| `DeleteConfigs` | `ConfigIds` (array), `UserName` |
| `SetClearBaseline` | `ConfigIds` (array) |
| `GetConfigTypes` | none |
| `GetInterfaceConfigSnippets` | `coreNodeId` (number) |
| `RunIndexOptimization` | none |
| `ValidateBinaryConfigStorage` | `path`, `networkShareUserName`, `networkSharePassword` |
| `GetPermissionsByRole` | `role`: `None`, `WebViewer`, `WebDownloader`, `WebUploader`, `Engineer` or `Administrator` |

`ImportConfig` writes a configuration into the archive **without touching the device**, which
is how you seed a baseline from a file. `UpdateConfig` takes a separate `updateConfigText`
boolean so you can change the title and comments without rewriting the text.

### Search

`ConfigSearch2(searchTerm)` is the current verb. `ConfigSearch` still exists and its own
summary says it will be removed. Both return an array of `ConfigID` values, which you then
resolve against `Cirrus.ConfigArchive`.

The deprecated form takes seven scalars: `searchString`, `configType`, `coreNodeIdList` (a
comma-separated string of **Orion** node ids), `matchWholeWord`, and optionally
`searchOnlyMostRecent`, `startTime` and `endTime`. SolarWinds documents it on the
[NCM Config Search](https://solarwinds.github.io/OrionSDK/docs/network-configuration-manager/ncm-config-search/)
page.

`ConfigSearch2` replaces all seven with one `ConfigSearchTerm` object, whose fields in the
2026.2 contract are:

| Field | Type |
|---|---|
| `OriginalSearchString` | string |
| `ConfigType` | string |
| `CoreNodeIds` | array of number, so an **array** of Orion ids rather than a comma-separated string |
| `MatchWholeWord` | boolean |
| `UseMostRecentConfigOption` | boolean |
| `StartDate`, `EndDate` | date-time |

That field renaming (`searchString` to `OriginalSearchString`, `searchOnlyMostRecent` to
`UseMostRecentConfigOption`) is the part that catches people migrating off the old verb.

### Compliance

| Verb | Parameters, in order |
|---|---|
| `AddPolicyReport` / `UpdatePolicyReport` | `report` (+ `importFlag` on Add) |
| `AddPolicy` / `UpdatePolicy` | `policy` (+ `importFlag` on Add) |
| `AddPolicyRule` / `UpdatePolicyRule` | `rule` |
| `DeletePolicyReports` / `DeletePolicies` | `ids` (array), `deleteChildren` (boolean) |
| `DeletePolicyRules` | `ruleIds` (array) |
| `GetPolicyReport` / `GetPolicy` | `id`, `exportFlag` (boolean) |
| `GetPolicyRule` | `ruleId` |
| `StartCaching` | `selectedReportsIds` (array, optional; empty or null processes every report) |
| `UpdateReportStatus` | `status` (`Disabled` or `Enabled`), `selectedReportsIds` (array) |
| `GetComplianceDataTable` | `reportId`, `includePolicies` (boolean) |
| `TestRule` | `policyRule`, `config` (the config text) |
| `TestRuleOnBackedUpConfig` | `policyRule`, `configId` |
| `GenerateRemediationScriptForNodes` | `nodeIds` (array of NCM GUID), `reportId`, `policyId`, `ruleId`, `script` |

`TestRule` and `TestRuleOnBackedUpConfig` are the two worth knowing: they evaluate a rule you
have not saved yet against real configuration text, which is how you develop a rule without
publishing a broken one to a live report. `StartCaching` is what makes a report's numbers
current, and everything else in compliance reads a cache.

`GenerateRemediationScriptForNodes` renders the remediation script for a set of nodes but does
not run it. You run it yourself with `Cirrus.ConfigArchive.ExecuteScript`, which is the right
separation given what remediation scripts do.

## Worked queries

Every query below was validated against the 2026.2 schema with
`python3 tools/validate_swql.py`. Time bounds are passed as bound parameters rather than
computed in SWQL, for the reason under [Gotchas](#gotchas).
[`../../scripts/swql/11-ncm-configs.swql`](../../scripts/swql/11-ncm-configs.swql) has the
basic inventory, login-failure, protocol-breakdown and coverage queries; these pick up where
that file stops.

### 1. Which monitored devices NCM is not backing up

The coverage gap is the question NCM exists to answer, and the navigation property makes it a
one-entity query.

```sql
SELECT TOP 100
    n.Caption,
    n.IPAddress,
    n.Vendor,
    n.MachineType
FROM Orion.Nodes n
LEFT JOIN NCM.NodeProperties np ON np.CoreNodeID = n.NodeID
WHERE np.NodeID IS NULL
  AND n.Vendor IS NOT NULL
ORDER BY n.Caption
```

`np.CoreNodeID = n.NodeID` is the join that matters: `NCM.NodeProperties.NodeID` is a GUID and
will never equal an `Orion.Nodes.NodeID` integer. Filtering on `n.Vendor IS NOT NULL` removes
the servers and printers nobody expected NCM to cover.

The same question through the navigation property, which is shorter and reads better once you
know it is there:

```sql
SELECT TOP 100
    n.Caption,
    n.IPAddress,
    n.Vendor,
    n.NodeProperties.LastInventory,
    n.NodeProperties.LoginStatus,
    n.NodeProperties.ConnectionProfile,
    n.NCMLicenseStatus.LicensedByNCM
FROM Orion.Nodes n
WHERE n.NodeProperties.NodeID IS NOT NULL
ORDER BY n.Caption
```

### 2. Config backups that are failing or stale

`NCM.ConfigBackupStatus` is precomputed per node and config type, which makes it much cheaper
than deriving the same answer from the archive.

```sql
SELECT TOP 100
    bs.NodeName,
    bs.Vendor,
    bs.ConfigType,
    bs.BackupStatus,
    bs.LastSuccessfulBackupDate,
    DayDiff(bs.LastSuccessfulBackupDate, GetDate()) AS DaysSinceBackup,
    si.StatusName AS NodeStatus
FROM NCM.ConfigBackupStatus bs
LEFT JOIN Orion.StatusInfo si ON bs.Status = si.StatusId
WHERE bs.BackupStatus <> 1
ORDER BY bs.LastSuccessfulBackupDate
```

`BackupStatus` is `1` for success, `14` for failed and `3` for never backed up, so
`<> 1` is "not currently in a good state". Joining
[`Orion.StatusInfo`](../reference/status-codes.md) turns the node's own status integer into a
name, which matters here because a device that is Down has a very good reason for not being
backed up and should not be in the same triage bucket as one that is Up and failing.

### 3. Recent transfer failures, with the device's own error text

```sql
SELECT TOP 50
    tr.DateTime,
    tr.NodeProperties.Nodes.Caption AS NodeName,
    tr.Action,
    tr.RequestedConfigType,
    tr.TransferProtocol,
    tr.Status,
    tr.ErrorMessage,
    tr.UserName
FROM NCM.TransferResults tr
WHERE tr.Status = 3
  AND tr.DateTime >= @startUtc
ORDER BY tr.DateTime DESC
```

`tr.NodeProperties.Nodes.Caption` walks two hosting relationships in one expression: from the
transfer to NCM's node properties, then from there to the platform node. `Action` is `1`
download, `2` upload, `3` execute script, and `TransferProtocol` is the combination actually
used, such as `Telnet - TFTP`, which is often the thing that explains the failure.

### 4. Configuration drift: running does not match startup

```sql
SELECT TOP 100
    cn.NodeCaption,
    cn.AgentIP,
    dr.ConfigType,
    dr.ConfigTypeBefore,
    dr.ComparisonType,
    dr.DiffWidth,
    dr.ConfigTitle
FROM Cirrus.CacheDiffResults dr
JOIN Cirrus.Nodes cn ON dr.NodeID = cn.NodeID
WHERE dr.DiffFlag = TRUE
ORDER BY cn.NodeCaption
```

Both `Cirrus.CacheDiffResults.NodeID` and `Cirrus.Nodes.NodeID` are the NCM GUID, so this join
is on matching types. Add `AND dr.ComparisonType = 1` to restrict to running-versus-startup,
which is the "somebody made a change and did not save it" case. `DiffList` holds the actual
differing lines and is large; select it for one row, not for a hundred.

### 5. Which compliance rules are failing across the estate

```sql
SELECT TOP 100
    pc.ReportName,
    pc.PolicyName,
    pc.RuleName,
    pc.ErrorLevel,
    COUNT(pc.CacheID) AS ViolationCount
FROM Cirrus.PolicyCacheResults pc
WHERE pc.IsViolation = TRUE
GROUP BY pc.ReportName, pc.PolicyName, pc.RuleName, pc.ErrorLevel
ORDER BY COUNT(pc.CacheID) DESC
```

`Cirrus.PolicyCacheResults` denormalises the report, policy and rule names onto every row, so
this needs no joins at all. A rule at the top of this list with a high count is usually a rule
that is wrong rather than an estate that is broken.

### 6. The same violations, per device, with the offending line

```sql
SELECT TOP 100
    cn.NodeCaption,
    pc.ReportName,
    pc.RuleName,
    pc.ErrorLevel,
    pc.ConfigType,
    pc.FoundLineNumber,
    pc.FoundLine
FROM Cirrus.PolicyCacheResults pc
JOIN Cirrus.Nodes cn ON pc.NodeID = cn.NodeID
WHERE pc.IsViolation = TRUE
  AND pc.ErrorLevel >= 2
ORDER BY cn.NodeCaption, pc.RuleName
```

`FoundLine` and `FoundLineNumber` are what turn a compliance number into an actionable ticket.

### 7. Are the compliance reports themselves healthy

Compliance numbers come from a cache, so a report that failed to cache reports zero violations
and looks like good news.

```sql
SELECT
    pr.Name,
    pr.Grouping,
    pr.ReportStatus,
    pr.CacheStatus,
    pr.LastUpdated,
    pr.LastError,
    lv.Error AS ErrorViolations,
    lv.Warning AS WarningViolations,
    lv.Info AS InfoViolations
FROM Cirrus.PolicyReports pr
LEFT JOIN Cirrus.LatestPolicyReportViolations lv ON pr.PolicyReportID = lv.ReportID
ORDER BY lv.Error DESC
```

`CacheStatus = 4` is an error and `CacheStatus = 0` is never cached. Either one means the
violation counts on that row mean nothing. `ReportStatus` is a boolean saying whether the
report is enabled at all.

### 8. Baseline violations

```sql
SELECT TOP 100
    b.Name AS BaselineName,
    np.Nodes.Caption AS NodeName,
    bv.ConfigType,
    bv.IsViolation,
    bm.CacheState
FROM NCM.BaselineViolations bv
JOIN NCM.Baselines b ON bv.BaselineId = b.Id
JOIN NCM.NodeProperties np ON bv.NodeId = np.NodeID
LEFT JOIN NCM.BaselineNodeMap bm ON bm.BaselineId = bv.BaselineId
    AND bm.NodeId = bv.NodeId
    AND bm.ConfigType = bv.ConfigType
WHERE bv.IsViolation = TRUE
ORDER BY b.Name
```

The `NCM.BaselineNodeMap` join is on all three key columns because the assignment is keyed by
baseline, node **and** config type. `CacheState` of `0` means the answer on this row is
pending recalculation, and `3` means the calculation errored, so both make `IsViolation`
unreliable for that row.

### 9. Requests waiting in the approval queue

```sql
SELECT TOP 50
    aq.DateTime,
    aq.UserName,
    aq.RequestType,
    aq.RequestStatus,
    aq.ExecutionType,
    aq.RunAt,
    aq.Comments,
    COUNT(aqn.NodeID) AS TargetNodeCount
FROM Cirrus.ApproveQueue aq
LEFT JOIN Cirrus.ApproveQueueNodes aqn ON aq.ID = aqn.ApproveQueueID
WHERE aq.RequestStatus IN (0, 6)
GROUP BY aq.DateTime, aq.UserName, aq.RequestType, aq.RequestStatus, aq.ExecutionType,
         aq.RunAt, aq.Comments
ORDER BY aq.DateTime
```

Status `0` is pending and `6` is approved by one person and waiting on a second, so together
they are "somebody is blocked". The `LEFT JOIN` to `Cirrus.ApproveQueueNodes` gives the blast
radius, which is the number an approver actually wants to see before clicking approve.

### 10. End of support, with how much to trust each match

```sql
SELECT TOP 100
    cn.NodeCaption,
    cn.MachineType,
    q.EosModel,
    q.PartNumber,
    q.ReplacementPartNumber,
    q.EndOfSupport,
    q.Rank,
    q.Certainty
FROM Cirrus.NCM_EosMatchQueue q
JOIN Cirrus.Nodes cn ON q.NodeID = cn.NodeID
ORDER BY q.Rank DESC
```

Selecting `Rank` and `Certainty` alongside the dates is the difference between a refresh
budget you can defend and one you cannot. A high-rank `'Good'` match is NCM saying it is
confident; anything lower deserves a human check before it reaches a spreadsheet.

### 11. NCM's own schedule and whether it is working

```sql
SELECT TOP 50
    j.NCMJobName,
    j.NCMJobType,
    j.Enabled,
    j.Status,
    j.LastDateRun,
    j.NextDateRunUtc,
    j.CompletedSubJobs,
    j.AllSubJobs,
    j.JobEndsWithGeneralError
FROM Cirrus.NCM_NCMJobsView j
WHERE j.IsHidden = FALSE
ORDER BY j.NextDateRunUtc
```

`CompletedSubJobs` short of `AllSubJobs` on a job whose `Status` is `7` (completed) means the
job finished but some devices did not. `IsHidden = FALSE` removes the internal jobs NCM
creates for itself.

### 12. Shadowed and redundant ACL rules

Adapted from the example query SolarWinds embeds in the `NCM.RuleDetection` entity summary,
extended to name the device.

```sql
SELECT TOP 100
    c.ConfigTitle,
    c.NodeProperties.Nodes.Caption AS NodeName,
    srdr.AccessListName,
    ace.RuleId,
    r.OverlappingRules,
    r.OverlappingType
FROM NCM.ShadowRuleDetectionResult srdr
JOIN NCM.ConfigArchive c ON srdr.ConfigId = c.ConfigID
JOIN NCM.AceShadowRuleDetectionResult ace ON srdr.SrdrId = ace.SrdrId
JOIN NCM.RuleDetection r ON r.ResultId = ace.ResultId
WHERE r.OverlappingType <> 0
ORDER BY c.ConfigTitle, ace.RuleId
```

`OverlappingType` of `0` is unique, `1` is shadowed (the rule can never match because an
earlier rule catches everything it would) and `2` is partially overlapping.

### 13. Turning search results into rows

`ConfigSearch2` returns config ids and nothing else. This is the follow-up query, and the
multi-valued bound parameter is what makes it one round trip:

```sql
SELECT
    ca.ConfigID,
    ca.ConfigTitle,
    ca.ConfigType,
    ca.DownloadTime,
    ca.Baseline,
    cn.NodeCaption,
    cn.AgentIP
FROM Cirrus.ConfigArchive ca
JOIN Cirrus.Nodes cn ON ca.NodeID = cn.NodeID
WHERE ca.ConfigID IN @configIds
ORDER BY cn.NodeCaption
```

### 14. What has been changed, and by whom

```sql
SELECT TOP 100
    a.DateTime,
    a.UserName,
    a.Action,
    a.Type,
    a.ApprovedBy,
    a.Details
FROM Cirrus.Audit a
WHERE a.DateTime >= @startUtc
ORDER BY a.DateTime DESC
```

`Cirrus.Audit` is NCM's own audit trail and is separate from `Orion.AuditingEvents`. `Type`
records whether the operation succeeded, and `ApprovedBy` with `RequestID` ties an action back
to the approval that authorised it.

## Worked verb examples

All of these use `SwisPowerShell`. The mechanics of `Invoke-SwisVerb`, including how each
argument is serialised and the single-array-argument trap, are in
[../swis/invoke-verbs.md](../swis/invoke-verbs.md).

### Add nodes to NCM and assign a connection profile

Two steps, because they are two different mechanisms: membership is a verb, and the profile
assignment is a CRUD update.

```powershell
Import-Module SwisPowerShell
$swis = Connect-Swis -Hostname orion.example.com -Trusted

$profileId = 3

# Every Cisco node the platform monitors that NCM does not yet manage.
$coreNodeIds = Get-SwisData $swis @"
SELECT TOP 100 n.NodeID
FROM Orion.Nodes n
LEFT JOIN NCM.NodeProperties np ON np.CoreNodeID = n.NodeID
WHERE np.NodeID IS NULL
  AND n.Vendor = @vendor
"@ @{ vendor = 'Cisco' }

foreach ($coreNodeId in $coreNodeIds) {
    # AddNodeToNCM takes the ORION node id and returns the new NCM NodeID as a string.
    $ncmNodeId = (Invoke-SwisVerb $swis Cirrus.Nodes AddNodeToNCM @([int]$coreNodeId)).InnerText
    Write-Host "Added Orion node $coreNodeId to NCM as $ncmNodeId"

    # Assigning the connection profile is an update on Cirrus.Nodes, not a verb.
    $uri = Get-SwisData $swis `
        "SELECT Uri FROM Cirrus.Nodes WHERE CoreNodeID = @id" @{ id = [int]$coreNodeId }
    Set-SwisObject $swis $uri @{ ConnectionProfile = $profileId }
}
```

The batch form avoids a round trip per node, but note the single-array-argument rule: the verb
takes one array parameter, so the argument list needs a leading comma and an explicit cast.

```powershell
Invoke-SwisVerb -SwisConnection $swis -EntityName Cirrus.Nodes -Verb AddNodes `
    -Arguments @( , [int[]] $coreNodeIds ) | Out-Null
```

Profile `-1` clears the assignment and profile `0` requests auto detection, which needs at
least one profile with `UseForAutoDetect` set. `Samples/PowerShell/NCMProfile.ps1` in the
[OrionSDK repository](https://github.com/solarwinds/OrionSDK) is the same idea in four lines.

### Download configurations and wait for the result

Transfers are asynchronous. The verb hands back tickets, and `NCM.TransferResults` is where
you find out what happened.

```powershell
Import-Module SwisPowerShell
$swis = Connect-Swis -Hostname orion.example.com -Trusted

$ncmNodeIds = Get-SwisData $swis @"
SELECT TOP 25 cn.NodeID
FROM Cirrus.Nodes cn
WHERE cn.NodeGroup = @group
"@ @{ group = 'Core' }

# DownloadConfig(nodeId[], configType). The first argument must be a Guid[], and the
# leading comma keeps it as one array argument rather than N separate ones.
$guids = [Guid[]] $ncmNodeIds
$response = Invoke-SwisVerb -SwisConnection $swis -EntityName Cirrus.ConfigArchive `
    -Verb DownloadConfig -Arguments @( , $guids ), 'Running'

# The response is an XmlElement whose children are the transfer tickets. Inspect
# $response.InnerXml once to confirm the element name on your version before relying on it.
$transferIds = $response.ChildNodes | ForEach-Object { $_.InnerText }
Write-Host "Queued $($transferIds.Count) transfers"

do {
    Start-Sleep -Seconds 5
    $pending = Get-SwisData $swis @"
SELECT COUNT(tr.TransferID) AS Pending
FROM NCM.TransferResults tr
WHERE tr.TransferID IN @ids
  AND tr.Status IN (0, 1)
"@ @{ ids = $transferIds }
} while ($pending -gt 0)

Get-SwisData $swis @"
SELECT
    tr.NodeProperties.Nodes.Caption AS NodeName,
    tr.Status,
    tr.ErrorMessage,
    tr.ConfigArchive.ConfigTitle AS ConfigTitle
FROM NCM.TransferResults tr
WHERE tr.TransferID IN @ids
"@ @{ ids = $transferIds } | Format-Table -AutoSize
```

Status `0` is queued and `1` is transferring, so the loop exits when every ticket has reached
`2` (complete) or `3` (error). Polling every five seconds rather than every second is
deliberate: a config download over Telnet and TFTP to a busy device is not a sub-second
operation, and a tight loop just adds load to the SWIS endpoint.

### Execute a script on devices and read the output back

`Samples/PowerShell/NCM.ExecuteScript.ps1` in the OrionSDK repository is the script everyone
starts from, and **it does not work against 2026.2 as published**. It invokes a verb called
`Execute` and polls an entity called `Cirrus.TransferQueue`; neither exists in this schema.
The verb is `ExecuteScript` and the status entity is `NCM.TransferResults`. Here is the same
script corrected:

```powershell
Import-Module SwisPowerShell
$swis = Connect-Swis -Hostname orion.example.com -Trusted

$ip = '192.0.2.10'
$script = 'show clock'

$ncmNodeId = Get-SwisData $swis `
    "SELECT NodeID FROM Cirrus.Nodes WHERE AgentIP = @ip" @{ ip = $ip }

# ExecuteScript(nodeId[], script, Reboot?). Reboot is optional and defaults to no reboot;
# pass it explicitly when the answer matters, because the default is not yours to assume.
$response = Invoke-SwisVerb -SwisConnection $swis -EntityName Cirrus.ConfigArchive `
    -Verb ExecuteScript -Arguments @( , [Guid[]] @($ncmNodeId) ), $script, $false

$transferIds = $response.ChildNodes | ForEach-Object { $_.InnerText }

do {
    Start-Sleep -Seconds 5
    $result = Get-SwisData $swis @"
SELECT TOP 1 tr.Status, tr.ErrorMessage, tr.DeviceOutput
FROM NCM.TransferResults tr
WHERE tr.TransferID IN @ids
"@ @{ ids = $transferIds }
} while ($result.Status -lt 2)

if ($result.Status -eq 3) {
    Write-Warning "Execution failed: $($result.ErrorMessage)"
} else {
    Write-Host $result.DeviceOutput
}
```

`DeviceOutput` is where the device's response lands. To send a **different** script to each
device in one call, use `ExecuteScriptPerNode(nodesScript, reboot)` and pass an array of
`NCMNodeScript` objects, each with a `NodeId` and a `Script` field.

This verb runs arbitrary commands on network hardware. If a script can reload a device, say so
in the script's own comments, support a dry run, and confirm before acting. Approvals exist
precisely so this is not one person's decision; see
[the approval queue](#the-approval-queue).

### Search every archived configuration

The current verb takes one structured argument, so the useful shape is a REST or Python call
where the object is plain JSON:

```python
from orionsdk import SwisClient

swis = SwisClient("orion.example.com", "svc-automation", password,
                  verify="/etc/ssl/certs/orion-swis.pem")

config_ids = swis.invoke("Cirrus.ConfigArchive", "ConfigSearch2", {
    "OriginalSearchString": "snmp-server community",
    "ConfigType": "Running",
    "CoreNodeIds": [11, 12, 13],          # Orion node ids, as integers
    "MatchWholeWord": False,
    "UseMostRecentConfigOption": True,
})

rows = swis.query(
    "SELECT ca.ConfigTitle, ca.DownloadTime, cn.NodeCaption "
    "FROM Cirrus.ConfigArchive ca "
    "JOIN Cirrus.Nodes cn ON ca.NodeID = cn.NodeID "
    "WHERE ca.ConfigID IN @ids",
    ids=config_ids,
)
```

From PowerShell the same argument has to be built as XML, because `Invoke-SwisVerb` serialises
anything that is not a hashtable with the .NET `DataContractSerializer`. Do not guess the
element names. Ask the server for the template:

```sql
SELECT Position, Name, Type, IsOptional, XmlTemplate
FROM Metadata.VerbArgument
WHERE EntityName = 'Cirrus.ConfigArchive'
  AND VerbName = 'ConfigSearch2'
ORDER BY Position
```

### Refresh compliance and read the answer

```powershell
Import-Module SwisPowerShell
$swis = Connect-Swis -Hostname orion.example.com -Trusted

$reportId = Get-SwisData $swis `
    "SELECT TOP 1 PolicyReportID FROM Cirrus.PolicyReports WHERE Name = @name" `
    @{ name = 'Edge hardening' }

# StartCaching(selectedReportsIds). The argument is optional; an empty array or null
# processes every report, which on a large estate is not what you want.
Invoke-SwisVerb -SwisConnection $swis -EntityName Cirrus.PolicyReports -Verb StartCaching `
    -Arguments @( , [Guid[]] @($reportId) ) | Out-Null

do {
    Start-Sleep -Seconds 10
    $status = Get-SwisData $swis `
        "SELECT CacheStatus FROM Cirrus.PolicyReports WHERE PolicyReportID = @id" `
        @{ id = $reportId }
} while ($status -eq 1 -or $status -eq 2)   # 1 queued, 2 caching now

if ($status -ne 3) {
    $err = Get-SwisData $swis `
        "SELECT LastError FROM Cirrus.PolicyReports WHERE PolicyReportID = @id" `
        @{ id = $reportId }
    Write-Warning "Caching did not complete (status $status): $err"
    return
}

Get-SwisData $swis @"
SELECT TOP 100
    cn.NodeCaption,
    pc.RuleName,
    pc.ErrorLevel,
    pc.FoundLineNumber,
    pc.FoundLine
FROM Cirrus.PolicyCacheResults pc
JOIN Cirrus.Nodes cn ON pc.NodeID = cn.NodeID
WHERE pc.ReportID = @id
  AND pc.IsViolation = TRUE
ORDER BY cn.NodeCaption
"@ @{ id = $reportId } | Format-Table -AutoSize
```

Checking `CacheStatus` reaches `3` before reading results is the whole point. Reading
`Cirrus.PolicyCacheResults` while `CacheStatus` is still `1` or `2` gives you the previous
run's numbers, and reading it after status `4` gives you numbers from whenever caching last
succeeded, which could be weeks ago.

## Gotchas

**Two node id spaces, and the verbs mix them deliberately.** `Cirrus.Nodes.NodeID` is a
`System.Guid`. `Orion.Nodes.NodeID` is a `System.Int32`. `Cirrus.Nodes.CoreNodeID` is the
bridge. `AddNodeToNCM(coreNodeId)` and `AddNodes(coreNodeIds)` take Orion integers;
`RemoveNode(nodeId)`, `RemoveNodes(ncmNodeIds)`, `GetNode(nodeId)`, `DownloadConfig(nodeId)`,
`ExecuteScript(nodeId)`, `NCM.Eos.RefreshNow(nodeIds)` and
`GenerateRemediationScriptForNodes(nodeIds)` take NCM GUIDs;
`NCM.FirmwareOperations.PrepareFirmwareUpgrade(coreNodeIds)` and
`Cirrus.ConfigArchive.GetInterfaceConfigSnippets(coreNodeId)` are back to Orion integers.
There is no rule to memorise. Check the verb.

**Joining on the wrong id returns nothing and no error.** A GUID never equals an integer, so
`ON cn.NodeID = n.NodeID` between `Cirrus.Nodes` and `Orion.Nodes` produces an empty result
that looks exactly like "no data". This is the most common NCM query bug there is.

**SolarWinds' own `NCM.ExecuteScript.ps1` sample does not run against 2026.2.** It calls
`Cirrus.ConfigArchive.Execute` and polls `Cirrus.TransferQueue`. Neither the verb nor the
entity exists in this schema. Use `ExecuteScript` and `NCM.TransferResults`, as in
[the corrected example above](#execute-a-script-on-devices-and-read-the-output-back).

**`ClearTransfers` is documented but not in the 2026.2 schema.** SolarWinds'
[NCM Config Transfer](https://solarwinds.github.io/OrionSDK/docs/network-configuration-manager/ncm-config-transfer/)
page documents `void ClearTransfers(Guid[] TransferTickets)` on `Cirrus.ConfigArchive`. The
only transfer verb in the extracted 2026.2 schema is `CancelTransfers`, which has the same
signature but cancels rather than deletes history. Whether `ClearTransfers` is present but
undocumented on a given server is **unverified here**; check with
`SELECT VerbName FROM Metadata.Verb WHERE EntityName = 'Cirrus.ConfigArchive' ORDER BY VerbName`.

**`ComparisonType` is documented with two different bases.** `Cirrus.CacheDiffResults`
enumerates it as `1` RunningToStartup through `4` MostRecentToLastOfTheSameType.
`Cirrus.LatestComparisonResults` enumerates the same four names as `0` through `3`. The
Swagger contract types the `comparisonType` argument of
`Cirrus.Nodes.ExecuteConfigChangeReportAction` as a **string** enum with those four names and
no numbers at all. Read each entity's own documented values rather than carrying a constant
between them, and confirm on your server with a
`SELECT DISTINCT ComparisonType FROM Cirrus.LatestComparisonResults` before writing a filter.

**`UpdateNode` overwrites everything.** It does not merge. Its own summary spells out the only
safe pattern: call `GetNode(nodeId)`, modify the returned model, then call `UpdateNode(node)`.
Constructing an `NCMNode` from scratch and calling `UpdateNode` clears every property you did
not set, including credentials.

**Never select credential columns.** `Cirrus.Nodes` exposes `Password`, `EnablePassword`,
`SNMPAuthPass`, `SNMPEncryptPass`, `Community` and `CommunityReadWrite`. They are stored
encrypted, and `Cirrus.Settings.DecryptData` exists, which is exactly why a query that pulls
them into a report or a log is a problem. The module's own settings enum, readable through
`Cirrus.Settings.GetSetting`, includes `HideCommunityStrings` and `HideUsernames` for a
reason.

**Never select `Config` or `DiffList` in a listing.** `Cirrus.ConfigArchive.Config` is the
entire device configuration and `Cirrus.CacheDiffResults.DiffList` is every differing line.
A hundred rows of either is megabytes over the API. Select them one `ConfigID` at a time.

**`AttemptedDownloadTime` ahead of `DownloadTime` is a failed backup.** It is a more reliable
signal than `LoginStatus`, because a device can authenticate perfectly and still fail the
transfer when `TransferProtocol` cannot reach it.

**Compliance results are a cache, not a live evaluation.** `Cirrus.PolicyReports.CacheStatus`
of `0` (never cached) or `4` (error) means the violation counts on that report are
meaningless, not zero. Check `CacheStatus` and `LastUpdated` before you believe a compliance
number, and call `StartCaching` if you need a current one.

**Three protocols, three failure modes.** `ExecProtocol`, `CommandProtocol` and
`TransferProtocol` are independent. A node can pass `ValidateLogin`, execute scripts happily
over SSH, and still fail every download because its `TransferProtocol` is TFTP and the TFTP
server is unreachable from that polling engine.

**Connection profiles are not queryable.** There is no entity for them, only the five verbs
on `Cirrus.Nodes`. `Cirrus.Nodes.ConnectionProfile` gives you the id a node is using, but
turning that id into a name requires `GetConnectionProfile(id)` or
`GetAllConnectionProfiles()`.

**`NCM.RTNAudit.DateTime` is a `System.String`, not a `System.DateTime`.** Date comparisons
and the date functions will not behave as you expect on it. Every other `DateTime` column in
the module is properly typed.

**`NCM.OneTimeOperations.UpdateOneTimeOperation` changed argument order in 2026.2.** It was
`(id, status, properties)` and is now `(id, status, scriptContent, reboot)`, and the
`Properties` column was removed from the entity. Arguments are positional, so an existing call
still has a plausible-looking argument count and sends the wrong values into the wrong slots.
See [../reference/schema-changes-2026.1-to-2026.2.md](../reference/schema-changes-2026.1-to-2026.2.md).

**`NCM.VulnerabilitiesAnnouncements` and `NCM.VulnerabilitiesAnnouncementsNodes` are
obsolete.** The schema names `Orion.SecObs.Vulnerabilities.Cves` as the replacement. They
still work; do not start anything new on them.

**NCM enforces its own role model on top of Orion rights.** Almost every verb summary says
something like "Valid for Orion manage node users with at least WebUploader NCM role", and
that requirement is real even though it does not appear in the entity's `accessControl`. The
NCM roles are `None`, `WebViewer`, `WebDownloader`, `WebUploader`, `Engineer` and
`Administrator`, in increasing order.
`Cirrus.ConfigArchive.GetPermissionsByRole(role)` reports what a role can do. A permission
error from an NCM verb is usually a missing NCM role, not a missing Orion right. See
[../swis/invoke-verbs.md](../swis/invoke-verbs.md) on layered permissions.

**`DeleteOverLicenseNodes` takes no arguments and deletes nodes it chooses.** It is on
`Cirrus.Nodes`, it is a single call, and there is no dry run. Nothing else in the module is
this easy to fire by accident.

**Do not build time windows with `GetUtcDate()` plus the `AddX` functions.** Those compile to
T-SQL `DATEADD`, which is timezone blind, so the combination is wrong by your server's UTC
offset. Compute the bounds in the client and pass them as bound parameters, which is what the
queries above do.

**Account limitations filter silently.** Two accounts running the same NCM query legitimately
get different rows, and nothing in the response says so. "The query returns nothing" is a
permissions hypothesis before it is a data one.

## Related pages

- [README.md](README.md) for the module index and how to check what is installed.
- [../platform/modules.md](../platform/modules.md) for the whole-schema module map and why the
  namespace prefixes do not match the product names.
- [../swis/invoke-verbs.md](../swis/invoke-verbs.md) for positional arguments, serialisation
  and the single-array-argument trap.
- [../swis/verb-catalog.md](../swis/verb-catalog.md#ncm) for the cross-module verb table.
- [../swis/crud.md](../swis/crud.md) and [../swis/uris.md](../swis/uris.md) for assigning
  connection profiles, creating baselines and everything else that is not a verb.
- [../swis/metadata-introspection.md](../swis/metadata-introspection.md) for asking a live
  server what it actually has, including `Metadata.VerbArgument.XmlTemplate`.
- [../swql/language-reference.md](../swql/language-reference.md#full-outer-join) for the
  `CoreNodeID` join written as a reconciliation query.
- [../reference/status-codes.md](../reference/status-codes.md) for the node `Status` integers.
- [../reference/verb-index.md](../reference/verb-index.md) for all 160 NCM verbs with their
  ordered parameters.
- [../../scripts/swql/11-ncm-configs.swql](../../scripts/swql/11-ncm-configs.swql) for the
  inventory, login-failure, EoS and coverage queries this page builds on.

## Official SolarWinds documentation

- [NCM Config Transfer](https://solarwinds.github.io/OrionSDK/docs/network-configuration-manager/ncm-config-transfer/)
- [NCM Config Search](https://solarwinds.github.io/OrionSDK/docs/network-configuration-manager/ncm-config-search/)
- [NCM Connection Profiles](https://solarwinds.github.io/OrionSDK/docs/network-configuration-manager/ncm-connection-profiles/)
- [Orion SDK documentation index](https://solarwinds.github.io/OrionSDK/)
- [OrionSDK sample scripts](https://github.com/solarwinds/OrionSDK/tree/master/Samples),
  including `NCM.ExecuteScript.ps1`, `NCMProfile.ps1` and
  `NTA.DownloadRouterConfigFromNCM.ps1`

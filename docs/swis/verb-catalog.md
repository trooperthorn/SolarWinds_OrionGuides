# Verb catalog

SWIS schema 2026.2 declares **958 verbs** across **186 entities**. Of those, **794 publish
typed, named, ordered parameters** and **332 return `System.Void`**. This page is not all 958.
It is the subset you are most likely to need, grouped by the task you are trying to do, plus
the commands to query the remaining ones yourself.

If you already know the verb name, [../reference/verb-index.md](../reference/verb-index.md)
lists all 958 with signature, return type and required right. If you do not yet know how to
call one, start with [invoke-verbs.md](invoke-verbs.md).

## How to read these tables

- **Parameters** are listed **in order**, because the order is the contract. Arguments travel
  as a positional array and the names never go on the wire. A trailing `?` marks an optional
  parameter; optional parameters are always at the end of the list, so you may truncate the
  argument array after the last one you want to supply.
- **Requires** is the right the schema declares for `invoke` **on that verb**. `not declared`
  is not the same as "no restriction". Rights are declared at two levels, and the entity often
  carries one when the verb does not. 629 of the 958 verbs declare no verb-level right, and
  363 of those belong to an entity that declares an `invoke` right of its own. Each table
  below states the entity-level right where one exists. NCM and IPAM then enforce their own
  module roles on top of both. See [invoke-verbs.md](invoke-verbs.md#access-control).
- **What it does** reproduces SolarWinds' own summary text where one was published, trimmed
  to fit. Where the schema published no summary, the description here is derived from the
  verb name and its parameter list and says nothing the signature does not already imply.

Every row was generated from `data/schema/2026.2/verbs.json`. Re-verify any single row with:

```bash
python3 tools/schema_query.py verb Orion.Nodes Unmanage
```

## Node and object lifecycle

Adding a node is `Create Orion.Nodes` through CRUD, not a verb. What the verbs cover is
everything after that: finding out what is on the device, importing the resources you want to
monitor, and attaching the object to a module.

| Entity | Verb | Parameters | Requires | What it does |
|:---|:---|:---|:---|:---|
| `Orion.Nodes` | `ScheduleListResources` | `nodeId` | `manageNodes` | Schedule one time List Resources discovery for given NodeId |
| `Orion.Nodes` | `GetScheduledListResourcesStatus` | `jobId, nodeId` | `manageNodes` | Get current result of discovery job |
| `Orion.Nodes` | `GetListResourcesResult` | `jobId, nodeId` | `manageNodes` | Get the result of List Resources discovery |
| `Orion.Nodes` | `ImportListResourcesResult` | `jobId, nodeId` | `manageNodes` | Import all results found during discovery |
| `Orion.Nodes` | `ImportSelectedListResourcesResult` | `jobId, nodeId, resources` | `manageNodes` | Import selected result of discovery |
| `Orion.Nodes` | `ScheduleListResourcesForAddress` | `ipAddress, port, credentialsType, credentialProperties, engineId, preferredSnmpVersion?` | `manageNodes` | Schedule one time List Resources discovery for given ip address |
| `Orion.NPM.Interfaces` | `DiscoverInterfacesOnNode` | `nodeId` | `manageNodes` | Run lite discovery process for search interfaces on node and returns list of interfaces. |
| `Orion.NPM.Interfaces` | `AddInterfacesOnNode` | `nodeId, interfacesToAdd, pollers` | `manageNodes` | Add provided interface to node. |
| `Orion.NPM.Interfaces` | `SetBandwidth` | `netObjectId, inBandwidth, outBandwidth, customBandwidth` | `manageNodes` | Sets the custom bandwidth (`InBandwidth` and `OutBandwidth`) for the interface. |
| `Orion.APM.Application` | `CreateApplication` | `nodeId, applicationTemplateId, credentialSetId, skipIfDuplicate, applicationSettings?` | `manageNodes` | Create new application. |
| `Orion.APM.Application` | `DeleteApplication` | `applicationId` | `manageNodes` | Delete existed application. |
| `Cirrus.Nodes` | `AddNodeToNCM` | `coreNodeId` | `manageNodes` | Enables NCM to monitor and manage the configuration of an Orion node, assuming appropriate credentials are available. |

The `ScheduleListResources` family is a four-step pattern that recurs all over SWIS:
schedule, poll for status, read the result, import a chosen subset. `ScheduleListResources`
returns a job id as a string; you then pass that same `jobId` to the other three.

## On-demand polling

Every one of these asks for polling work to happen now instead of at the next scheduled
cycle. All the `PollNow` variants are declared `System.Void`, so none of them tells you
whether the poll ran or succeeded. Verify by watching the data change, for example
`Orion.Nodes.LastSync` and `Orion.Nodes.MinutesSinceLastSync`.

| Entity | Verb | Parameters | Requires | What it does |
|:---|:---|:---|:---|:---|
| `Orion.Nodes` | `PollStatusNow` | `netObjectId` | `manageNodes` | Polls node status only, the cheapest of the three on-demand polls. Takes `N:<NodeID>`. |
| `Orion.Nodes` | `PollNow` | `netObjectId` | `manageNodes` | Polls the node instance and updates its information. Takes `N:<NodeID>`. |
| `Orion.Nodes` | `RediscoverNow` | `netObjectId` | `manageNodes` | Rediscovers the node and updates its information. The most expensive of the three. Takes `N:<NodeID>`. |
| `Orion.APM.Application` | `PollNow` | `applicationId` | `manageNodes` | Poll existed application. Takes a bare `ApplicationID`. |
| `Orion.ADM.NodeInventory` | `PollNow` | `nodeIds` | `manageNodes` | Poll inventory from set of nodes. |
| `Orion.AssetInventory.Polling` | `PollNow` | `nodeIds` | `manageNodes` | Triggers asset inventory polling for a set of NodeIDs. |
| `Orion.SCM.ServerConfiguration` | `PollNow` | `nodeIds` | not declared | Refreshes watchers and polls file, registry and script elements on the target nodes. |
| `Orion.Nodes` | `GetSupportedMetrics` | `netObjectId` | `allowRealTimePolling`, `admin` | Lists the metrics real-time polling can collect on a node. Takes a bare NodeID number. |
| `Orion.Nodes` | `StartRealTimePolling` | `netObjectId, owner, properties, pollingExpiration?, pollingFrequency?` | `allowRealTimePolling`, `admin` | Starts real-time polling. `netObjectId` here is a bare NodeID number, not `N:<NodeID>`. |
| `Orion.Nodes` | `StopRealTimePolling` | `netObjectId, owner, properties` | `allowRealTimePolling`, `admin` | Stops real-time polling started by the same `owner`. |
| `Orion.NPM.Interfaces` | `StartRealTimePolling` | `netObjectId, owner, properties, pollingExpiration?, pollingFrequency?` | `allowRealTimePolling`, `admin` | Starts realtime polling on Interface entity |
| `Orion.Volumes` | `StartRealTimePolling` | `netObjectId, owner, properties, pollingExpiration?, pollingFrequency?` | `allowRealTimePolling`, `admin` | Starts realtime polling on Volume entity |

Watch the first argument. `Orion.Nodes.PollNow` wants the NetObject string `N:42`;
`Orion.Nodes.StartRealTimePolling` and `Orion.Nodes.GetSupportedMetrics` declare
`netObjectId` as a **number** and document it as "NodeID of target Node", so they want `42`.
Same parameter name, different type, different value. This is the reason to check the
signature rather than pattern-match on names.

## Maintenance: unmanaging and suppressing alerts

Two different things, often confused. **Unmanaging** stops polling, so the object goes to
status `9` (`Unmanaged`) and you get a gap in your charts. **Suppressing alerts** keeps
polling and keeps collecting statistics, and only stops alerts from triggering. Pick
suppression when you want the data but not the pages.

| Entity | Verb | Parameters | Requires | What it does |
|:---|:---|:---|:---|:---|
| `Orion.Nodes` | `Unmanage` | `netObjectId, unmanageTime, remanageTime, isRelative, allowOverlapping?` | `allowUnmanage` | Puts the node into a maintenance window. Times are UTC. |
| `Orion.Nodes` | `Remanage` | `netObjectId` | `allowUnmanage` | Ends the maintenance window immediately. |
| `Orion.NPM.Interfaces` | `Unmanage` | `netObjectId, unmanageTime, remanageTime, isRelative, allowOverlapping?` | `allowUnmanage` | Unmanage interface for specified time. |
| `Orion.NPM.Interfaces` | `Remanage` | `netObjectId` | `allowUnmanage` | Manage interface immediately. |
| `Orion.Volumes` | `Unmanage` | `netObjectId, unmanageTime, remanageTime, isRelative, allowOverlapping?` | `allowUnmanage` | Unmanages specified volume in the specified time range |
| `Orion.Volumes` | `Remanage` | `netObjectId` | `allowUnmanage` | Remanages specified volume |
| `Orion.APM.Application` | `Unmanage` | `netObjetId, unmanageTime, remanageTime, isRelative, allowOverlapping?` | not declared | Unmanage existed application. Note the misspelled first parameter. |
| `Orion.APM.Application` | `Remanage` | `netObjetId` | not declared | Remanage existed application. Note the misspelled first parameter. |
| `Orion.SEUM.Transactions` | `Unmanage` | `netObjectId, unmanageTime, remanageTime, isRelative` | not declared | Verb to unmanage transaction. Four parameters, no `allowOverlapping`. |
| `Orion.SEUM.Transactions` | `Remanage` | `netObjectId` | not declared | Verb to remanage transaction |
| `Orion.Cloud.Instances` | `Unmanage` | `virtualMachineId` | `allowUnmanage` | Unmanages a cloud instance. Takes a `virtualMachineId`, not a NetObject string, and takes no time range. |
| `Orion.Cloud.Instances` | `Remanage` | `virtualMachineId` | `allowUnmanage` | Remanages a cloud instance by `virtualMachineId`. |
| `Orion.AlertSuppression` | `SuppressAlerts` | `entityUris, suppressFrom?, suppressUntil?, allowOverlapping?, reason?` | `allowUnmanage` | Do not trigger any alerts for entities defined in `entityUris` during the suppress window. |
| `Orion.AlertSuppression` | `ResumeAlerts` | `entityUris` | `allowUnmanage` | Alerts for entities defined in `entityUris` will be triggered as usual. |
| `Orion.AlertSuppression` | `GetAlertSuppressionState` | `entityUris` | `everyone` | Get Alert Suppression State for provided list of entities, including suppression inherited from a parent. |

Entity-level `invoke` rights fill several of the gaps in the Requires column here.
`Orion.APM.Application` declares `invoke` for `manageNodes` or `allowUnmanage`, and
`Orion.SEUM.Transactions` declares it for `everyone` or `admin`.

Three traps live in this table and all three are real:

- **`Orion.APM.Application.Unmanage` and `Remanage` name their first parameter `netObjetId`,
  missing the `c`.** Positional callers are unaffected. Code generated from the Swagger
  contract is not, so a generated client will have a misspelled field name.
- **The six `Unmanage` verbs do not share one signature.** `Orion.SEUM.Transactions` has four
  parameters instead of five and `Orion.Cloud.Instances` has one, taking neither a NetObject
  string nor a time range. Do not write one wrapper and assume it covers all of them.
- **`Orion.AlertSuppression` takes URIs, not NetObject strings and not ids.** Suppression is
  inherited, so suppressing a node's URI also suppresses that node's children.

Times for all of these are handled in UTC, and `isRelative` changes what the third argument
means. Both are explained in [invoke-verbs.md](invoke-verbs.md#1-orionnodesunmanage-and-orionnodesremanage).

## Custom properties

These verbs manage custom property **definitions**. Setting a **value** on an object is a
CRUD update against that object's `CustomProperties` URI, or a `BulkUpdate` across many; see
[crud.md](crud.md) and [rest-api.md](rest-api.md).

Twenty-six entities host custom-property verbs in 2026.2, one per object type that supports
custom properties, including `Orion.NodesCustomProperties`,
`Orion.NPM.InterfacesCustomProperties`, `Orion.VolumesCustomProperties`,
`Orion.GroupCustomProperties`, `Orion.APM.ApplicationCustomProperties`, the nine
`Orion.SRM.*CustomProperties`, the five `Orion.VIM.*CustomProperties`, and the IPAM and WPM
variants. The table below shows the node set in full plus the two that break the pattern.

| Entity | Verb | Parameters | Requires | What it does |
|:---|:---|:---|:---|:---|
| `Orion.NodesCustomProperties` | `CreateCustomProperty` | `PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?` | not declared | Creates a node custom property definition. Positions 4 to 9 are documented as unused; pass null. |
| `Orion.NodesCustomProperties` | `CreateCustomPropertyWithValues` | `PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Value, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?` | not declared | As `CreateCustomProperty` plus an allowed-value list. `Value` sits between `Units` and `Usages`, shifting later positions. |
| `Orion.NodesCustomProperties` | `ModifyCustomProperty` | `PropertyName, Description, Size, Values, Usages?, Mandatory?, Default?, SourceId?, SourceName?, propertyDisplayName?` | not declared | Changes a definition. `Values` replaces the allowed-value list; read the current list first. |
| `Orion.NodesCustomProperties` | `DeleteCustomProperty` | `PropertyName` | not declared | Deletes the definition and all of its stored values. |
| `Orion.NodesCustomProperties` | `ValidateCustomProperty` | `PropertyName, Description, ValueType, Size, Value, Usages?, propertyDisplayName?` | not declared | Validates a proposed definition without creating it. |
| `Orion.APM.ApplicationCustomProperties` | `CreateCustomProperty` | `propertyName, description, valueType, size, validRange, parser, header, alignment, format, units, usageFlags, mandatory, defaultValue, sourceId?, sourceName?` | not declared | Same idea for SAM applications with a different signature: 15 parameters, lower-camel names, `usageFlags` and `defaultValue` required. |
| `IPAM.AttrDefine` | `AddCustomProperty` | `propertyName, description, maxStringLength, attributeType?, linkTitle?, addToIpAddress?, addToGroups?` | not declared | Adds an IPAM custom property. IPAM uses its own verb names rather than the `*CustomProperties` pattern. |
| `IPAM.AttrDefine` | `UpdateCustomProperty` | `propertyName, description, maxStringLength, linkTitle, addToIpAddress, addToGroups` | not declared | Updates an IPAM custom property definition. |
| `IPAM.AttrDefine` | `DeleteCustomProperty` | `propertyName` | not declared | Deletes an IPAM custom property definition. |

None of these verbs declares a right of its own, but the entities do.
`Orion.NodesCustomProperties` and `Orion.APM.ApplicationCustomProperties` both declare
`invoke` for `admin`, so creating or changing a custom property definition is an
administrator operation even though setting a custom property **value** only needs
`manageNodes` update rights on the object.

`ValidateCustomProperty` exists on only 14 of the 26 entities, so do not assume it is there.
Check with:

```bash
python3 tools/schema_query.py verbs --entity Orion.VolumesCustomProperties
```

## Alerts and events

| Entity | Verb | Parameters | Requires | What it does |
|:---|:---|:---|:---|:---|
| `Orion.AlertActive` | `Acknowledge` | `alertObjectIds, notes` | `clearEvents` | Acknowledges active alerts. Pass `AlertObjectID` values, not `AlertActiveID` values. |
| `Orion.AlertActive` | `Unacknowledge` | `alertObjectIds` | `clearEvents` | Unacknowledge active alerts. Single array argument. |
| `Orion.AlertActive` | `AppendNote` | `alertObjectIds, note` | `clearEvents` | Appends note to Alert object. |
| `Orion.AlertActive` | `ClearAlert` | `alertObjectIds` | `clearEvents` | Delete active alert from database. Manual alert reset. |
| `Orion.AlertConfigurations` | `Export` | `alertId, stripSensitiveData?, protectionPassword?` | `admin`, `manageAlerts` | This verb exports alert definition |
| `Orion.AlertConfigurations` | `Import` | `alertXml, stripSensitiveInformation?, protectionPassword?` | `admin`, `manageAlerts` | This verb imports alert into system from alert xml |
| `Orion.AlertConfigurations` | `GetComplexPropertiesByAlertID` | `alertId` | `admin`, `manageAlerts` | This verb get parsed alert's addition fields |
| `Orion.Events` | `Acknowledge` | `eventIDs` | `clearEvents` | Marks the specified event as acknowledged, typically used to clear events from active monitoring views. |

All four `Orion.AlertActive` verbs take `AlertObjectID` values. The verb summaries say "alert
active ids", but the parameter is named `alertObjectIds` and the official
[Alerts](https://solarwinds.github.io/OrionSDK/docs/alerts/) page is explicit that
`AlertObjectID` is what to pass. `Export` and `Import` together are how you move an alert
definition between environments.

Note that `Orion.AlertActive` declares no entity-level CRUD access control at all. These
verbs are the supported way to manipulate an active alert, not an Update on its URI.

## Discovery and credentials

| Entity | Verb | Parameters | Requires | What it does |
|:---|:---|:---|:---|:---|
| `Orion.Discovery` | `CreateCorePluginConfiguration` | `context` | not declared | Creates a new configuration for a plugin. Takes a `CorePluginConfigurationContext` XML document. |
| `Orion.Discovery` | `StartDiscovery` | `context` | not declared | Starts a discovery job from a `StartDiscoveryContext`. Returns the discovery profile id. |
| `Orion.Discovery` | `GetDiscoveryProgress` | `profileId` | not declared | Reports progress for a running discovery profile. |
| `Orion.Discovery` | `CancelDiscovery` | `profileId` | not declared | Cancels a running discovery profile. |
| `Orion.Discovery` | `DeleteDiscoveryProfile` | `profileId` | not declared | Deletes discovery profile by its profileId. |
| `Orion.Discovery` | `StartDiscoveryProfile` | `discoveryProfileId, engineId` | not declared | Starts discovery for specified profile ID |
| `Orion.Discovery` | `GetDiscoveryProfileResourcesResult` | `profileId` | not declared | Retrieves the list of discovered resources for a specific discovery profile |
| `Orion.Discovery` | `ImportDiscoveryResults` | `cfg` | not declared | Import discovery results for set of discovered nodes |
| `Orion.Discovery` | `GetImportDiscoveryResultsProgress` | `importId` | not declared | Get the progress of ImportDiscoveryResults |
| `Orion.Discovery` | `ValidateCredentials` | `ipAddress, port, credentialsType, credentialsProperties, engineId, preferredSnmpVersion?` | not declared | Check if provided credential is valid for given SNMP or WMI endpoint |
| `Orion.Discovery` | `ResolveIpFromHostname` | `hostname, preferredAddressFamily, engineId` | not declared | Get IP Address from given hostname |
| `Orion.Discovery` | `ResolveHostnameFromIp` | `ipAddress, engineId` | not declared | Get hostname from given IP address |
| `Orion.Credential` | `CreateSNMPCredentials` | `name, community, owner?` | `manageNodes` | Creates SNMP v1 or v2c credentials |
| `Orion.Credential` | `CreateSNMPv3Credentials` | `name, username, context, authenticationMethodValue, authenticationPassword, authenticationKeyIsPassword, privacyMethodValue, privacyPassword, privacyKeyIsPassword, owner?` | `manageNodes` | Creates SNMP v3 credentials |
| `Orion.Credential` | `CreateUsernamePasswordCredentials` | `name, username, password, owner?` | `manageNodes` | Creates credentials with username and password, these are used for example by WMI polling. |
| `Orion.Credential` | `CreateCredentials` | `type, properties, owner?` | `manageNodes` | Creates credential with provided list of properties |
| `Orion.Credential` | `UpdateCredentials` | `id, properties` | `manageNodes` | Updates credential properties |

No `Orion.Discovery` verb declares a right of its own, but the entity declares `invoke` for
`manageNodes`, so that is the right you actually need for all twelve.

`ResolveIpFromHostname` and `ResolveHostnameFromIp` resolve names **from the polling engine
you name in `engineId`**, not from wherever your script is running. That is the whole point of
them: on a segmented network the answer differs by engine.

The `Orion.Credential` create verbs all return the new credential id as a number, which is
what you feed into a discovery context or into `Orion.Nodes` when adding a node.

## NCM

NCM lives in the `Cirrus` namespace (72 entities in `NCM` plus 57 in `Cirrus` in 2026.2), and
its verbs enforce NCM's own role model on top of the Orion right. The role requirement is
stated in the verb summary rather than in `accessControl`, and it is real.

| Entity | Verb | Parameters | Requires | What it does |
|:---|:---|:---|:---|:---|
| `Cirrus.Nodes` | `AddNodes` | `coreNodeIds` | `manageNodes` | Batch version of `AddNodeToNCM`. |
| `Cirrus.Nodes` | `RemoveNode` | `nodeId` | `manageNodes` | Removes a node from NCM. Does not remove it from Orion, just NCM. |
| `Cirrus.Nodes` | `GetNode` | `nodeId` | not declared | Fetches an NCMNode model object for the given node. |
| `Cirrus.Nodes` | `UpdateNode` | `node` | `manageNodes` | Updates the NCM properties of a node. All properties are overwritten; it does not merge. Call `GetNode` first. |
| `Cirrus.Nodes` | `AddConnectionProfile` | `profile` | `manageNodes` | Creates a new connection profile. |
| `Cirrus.Nodes` | `GetAllConnectionProfiles` | `(none)` | not declared | Retrieve list of all connection profiles created in NCM. |
| `Cirrus.Nodes` | `ValidateLogin` | `engineId, node, ipAddress, deviceTemplate` | `manageNodes` | Tests login credentials. |
| `Cirrus.ConfigArchive` | `DownloadConfig` | `nodeId, configType` | not declared | Downloads config file for the particular node. |
| `Cirrus.ConfigArchive` | `UploadConfig` | `nodeId, configType, ConfigText, RebootDevice` | not declared | Uploads config. |
| `Cirrus.ConfigArchive` | `ExecuteScript` | `nodeId, script, Reboot?` | not declared | Executes script on the particular node. |
| `Cirrus.ConfigArchive` | `ImportConfig` | `nodeId, title, comments, configText` | not declared | Imports a config into the archive without touching the device. |
| `Cirrus.ConfigArchive` | `CompareConfigs` | `configId1, configId2, settings` | not declared | Compares two archived configs. |
| `Cirrus.ConfigArchive` | `ConfigSearch2` | `searchTerm` | not declared | Searches for the config. Replaces the deprecated `ConfigSearch`. |
| `NCM.FirmwareOperations` | `PrepareFirmwareUpgrade` | `coreNodeIds, firmwareDefinitionId, firmwareOperationName, imagesToApply` | not declared | Prepares new firmware upgrade operation. Returns the operation id. |
| `NCM.FirmwareOperations` | `StartUpgrade` | `operationId, nodeOptions, runAt, emailSettings` | not declared | Starts upgrade operation. |
| `NCM.Eos` | `RefreshNow` | `nodeIds` | not declared | Starts refreshing End of Support data for selected nodes. |

`Cirrus.Nodes` declares `invoke` at the entity level for `everyone` or `manageNodes`;
`NCM.FirmwareOperations` declares it for `everyone` or `admin`. `Cirrus.ConfigArchive` and
`NCM.Eos` declare no entity-level invoke right at all, which is exactly where the NCM role
requirement in the summary text is doing all the work.

`UpdateNode` overwrites every property of the NCM node record. The safe pattern, which the
verb summary states outright, is `GetNode`, modify the returned model, then `UpdateNode`.

`Cirrus.ConfigArchive.ConfigSearch` still exists and its own summary says it will be removed;
use `ConfigSearch2`. To find every verb SolarWinds has flagged this way on your server, query
`Metadata.Verb.IsObsolete`; see
[metadata-introspection.md](metadata-introspection.md#obsolete-and-internal-members).

## Agents

`Orion.AgentManagement.Agent` declares 20 verbs, more than `Orion.Nodes` itself. None of them
declares a right, but the entity declares `invoke` for `manageNodes`.

| Entity | Verb | Parameters | Requires | What it does |
|:---|:---|:---|:---|:---|
| `Orion.AgentManagement.Agent` | `Deploy` | `pollingEngineId, agentName, hostname, ipAddress, machineUserName, machinePassword, additionalUsername?, additionalPassword?, passwordIsPrivateKey?, privateKeyPassword?, agentMode?, installPackageFallbackId?` | not declared | Deploys an agent to a machine defined by hostname and/or IP address. |
| `Orion.AgentManagement.Agent` | `DeployToNode` | `nodeId, machineUserName?, machinePassword?, additionalUsername?, additionalPassword?, passwordIsPrivateKey?, privateKeyPassword?, agentMode?, installPackageFallbackId?` | not declared | Deploys an agent to an existing node using the supplied credentials. |
| `Orion.AgentManagement.Agent` | `AddPassiveAgent` | `agentName, agentHostname, agentIpAddress, agentPort, pollingEngineId, sharedSecret, proxyId, autoUpdateEnabled?, testPassiveAgentConnection?` | not declared | Adds passive agent. Uses `AddAgent` internally. |
| `Orion.AgentManagement.Agent` | `ValidateDeploymentCredentials` | `pollingEngineId, hostname, ipAddress, machineUserName, machinePassword, additionalUsername?, additionalPassword?, passwordIsPrivateKey?, privateKeyPassword?, installPackageFallbackId?` | not declared | Validates deployment credentials before you use them with `Deploy`. |
| `Orion.AgentManagement.Agent` | `Uninstall` | `agentId` | not declared | Uninstalls the agent. |
| `Orion.AgentManagement.Agent` | `Delete` | `agentId` | not declared | Deletes the agent record without uninstalling it. |
| `Orion.AgentManagement.Agent` | `RestartAgent` | `agentId` | not declared | Initiate Orion Agent service restart. |
| `Orion.AgentManagement.Agent` | `ApproveUpdate` | `agentId` | not declared | Approval for an agent to be updated. |
| `Orion.AgentManagement.Agent` | `AssignToEngine` | `agentId, pollerId` | not declared | Assigns an agent to a polling engine. |
| `Orion.AgentManagement.Agent` | `DeployPlugin` | `agentId, pluginId` | not declared | Deploys the specified plugin to the agent |
| `Orion.AgentManagement.Agent` | `UninstallPlugin` | `agentId, pluginId` | not declared | Uninstalls the specified plugin from the agent |
| `Orion.AgentManagement.Agent` | `CollectDiagnostics` | `agentId, pathToStoreAgentDiagnostics, diagnosticCollectionTimeoutInMinutes, areAgentLogsSelected?, areEventLogsSelected?, isNetStatSelected?, areRunningProcessesSelected?` | not declared | Collects agent diagnostics and stores them at the given path. |

`Deploy` is the verb where positional arguments hurt most, because it has twelve parameters,
six of them optional, and several are credentials. `passwordIsPrivateKey` changes what
`machinePassword` means: with `true`, `machinePassword` holds a PEM private key rather than a
password. SolarWinds ships an annotated walkthrough of every argument combination in
`Samples/PowerShell/DeployAgentViaVerb.ps1`. Validate first with
`ValidateDeploymentCredentials`, which takes the same credential arguments and does not
install anything.

## High availability

Every `Orion.HA.Pools` verb requires `admin` and returns an `OperationResult` carrying a
`Code`, a `Result` and a `Message`. Check `Code` rather than assuming a `2xx` means success.

| Entity | Verb | Parameters | Requires | What it does |
|:---|:---|:---|:---|:---|
| `Orion.HA.Pools` | `ValidateCreatePool` | `displayName, poolMembersIds, properties` | `admin` | Validates pool (without creating it) based on provided members and resource parameters |
| `Orion.HA.Pools` | `CreatePool` | `displayName, poolMembersIds, properties` | `admin` | Creates pool based on provided members and resource parameters |
| `Orion.HA.Pools` | `EditPool` | `poolId, displayName, properties` | `admin` | Updates pool with a given poolId |
| `Orion.HA.Pools` | `DeletePool` | `poolId` | `admin` | Delete pool with given poolId. |
| `Orion.HA.Pools` | `EnablePool` | `poolId` | `admin` | Enables pool with a given poolId |
| `Orion.HA.Pools` | `DisablePool` | `poolId` | `admin` | Disables pool with a given poolId |
| `Orion.HA.Pools` | `Switchover` | `poolId` | `admin` | Manual failover on a given pool. |
| `Orion.HA.Pools` | `SelectiveSwitchover` | `poolId, poolMemberIdsToFailover, poolMemberIdsToFailoverTo, failoverMessage` | `admin` | Fails over specific pool members to specific targets, with a message recorded against the switchover. |
| `Orion.HA.Pools` | `RepairPool` | `poolId` | `admin` | Repair pool with given poolId. |
| `Orion.HA.Pools` | `ElbEnable` | `poolId` | `admin` | Enables Load Balancing for pool with a given poolId |

`properties` is a nested structure, which in PowerShell means a nested hashtable. There is a
complete worked script in SolarWinds' `Samples/PowerShell/HA.PoolOperations.ps1`, and the
hashtable-to-PropertyBag mechanism is explained in
[invoke-verbs.md](invoke-verbs.md#how-arguments-are-serialised).

## Groups, dependencies and accounts

Groups are `Orion.Container` at the verb level and `Orion.Groups` at the query level. The
verbs that create and reshape a group live on `Orion.Container`.

| Entity | Verb | Parameters | Requires | What it does |
|:---|:---|:---|:---|:---|
| `Orion.Container` | `CreateContainer` | `name, owner, frequency, statusCalculator, description, pollingEnabled, memberDefinitions` | not declared | Creates a group (container) with its member definitions. |
| `Orion.Container` | `CreateContainerWithParent` | `parentId, name, owner, frequency, statusCalculator, description, pollingEnabled, memberDefinitions` | not declared | Creates a group nested under an existing group. |
| `Orion.Container` | `UpdateContainer` | `containerId, name, owner, frequency, statusCalculator, description, pollingEnabled` | not declared | Updates a group's name, owner, refresh frequency, status calculator, description and polling flag. |
| `Orion.Container` | `DeleteContainer` | `containerId` | not declared | Deletes a group. |
| `Orion.Container` | `AddDefinitions` | `containerId, memberDefinitions` | not declared | Adds member definitions to an existing group. |
| `Orion.Container` | `SetDefinitions` | `containerId, memberDefinitions` | not declared | Replaces the group's member definitions wholesale. |
| `Orion.ContainerMemberDefinition` | `GetMembers` | `definition` | not declared | Previews which objects a member definition would select, before you attach it to a group. |
| `Orion.Dependencies` | `RemoveDependencies` | `ids` | `admin` | Ignores dependencies so they are excluded from auto-dependency calculation. |
| `Orion.Accounts` | `CreateAccount` | `accountType, properties` | `admin` | Creates an account of the given type from a property bag. |
| `Orion.Accounts` | `CreateOrionAccount` | `accountID, password` | `admin` | Creates a new Account with provided Account ID and Password. |
| `Orion.Accounts` | `CreateWindowsAccount` | `accountType, userOrGroupName, adminUser?, adminPassword?` | `admin` | Adds Windows User accounts into Orion based on the provided account name search string. |
| `Orion.Accounts` | `UpdateAccount` | `accountID, properties` | `admin` | Updates properties of the specified Account with provided values. |
| `Orion.Accounts` | `ChangePassword` | `accountId, password` | `admin` | Changes password of the specified Account with provided string. |
| `Orion.Accounts` | `DeleteAccount` | `accountID` | `admin` | Deletes specified account. |

`Orion.ContainerMemberDefinition.GetMembers` is the dry run you want before committing a
dynamic group definition, because it answers "what would this actually match" without
creating anything.

The `Orion.Container` verbs declare no right individually, but the entity declares `invoke`
for `manageNodes` or `allowOrionMapsManagement`. The `Orion.Accounts` verbs each declare
`admin` directly, and the official
[Account Management](https://solarwinds.github.io/OrionSDK/docs/account-management/) page
confirms that every operation except querying accounts requires it.

New accounts are created with minimal rights and no limitations. Granting rights is a second
call to `UpdateAccount` with a property bag. The rights properties **read** as `"Y"` and
`"N"` but must be **written** as booleans; see
[invoke-verbs.md](invoke-verbs.md#rights-are-properties-of-the-orion-account).

## Hardware health and flow sources

| Entity | Verb | Parameters | Requires | What it does |
|:---|:---|:---|:---|:---|
| `Orion.HardwareHealth.HardwareInfoBase` | `EnableHardwareHealth` | `netObject, pollingmethod` | `manageNodes` | Enable Hardware Health for given entity. |
| `Orion.HardwareHealth.HardwareInfoBase` | `DisableHardwareHealth` | `netObject` | `manageNodes` | Disable Hardware Health for given entity. |
| `Orion.HardwareHealth.HardwareInfoBase` | `IsHardwareHealthEnabled` | `netObject` | not declared | Check if the Hardware Health is enabled for given entity. |
| `Orion.HardwareHealth.HardwareItemBase` | `EnableSensors` | `hardwareItems` | `manageNodes` | Enable sensors for given Hardware Health Items. |
| `Orion.HardwareHealth.HardwareItemThreshold` | `SetThreshold` | `sensorId, warningThreshold, criticalThreshold` | `manageNodes` | Sets thresholds for given sensors. |
| `Orion.Netflow.NodeSources` | `EnableFlowNodeSources` | `nodeIds` | not declared | Enables NTA flow collection for a set of NodeIDs. |
| `Orion.Netflow.NodeSources` | `DisableFlowNodeSources` | `nodeIds` | not declared | Disables NTA flow collection for a set of NodeIDs. |
| `Orion.Netflow.NodeSources` | `SetManualSamplingRate` | `nodeId, samplingRate` | not declared | Overrides the auto-detected flow sampling rate for one node. |
| `Orion.Netflow.InterfaceSources` | `EnableFlowInterfaceSources` | `interfaceIds` | not declared | Enables NTA flow collection for a set of InterfaceIDs. |

The hardware health verbs are declared on the **base** entities `HardwareInfoBase`,
`HardwareItemBase` and `HardwareItemThreshold`, not on the vendor-specific descendants. In
2026.2 those three plus `Orion.HardwareHealth.BMC.Controllers.TestBmcConnection` are the only
verbs in the `Orion.HardwareHealth.*` family, which is why one call works across vendors.

Both `Orion.Netflow.NodeSources` and `Orion.Netflow.InterfaceSources` declare `invoke` for
`manageNodes` at the entity level, so the `not declared` entries above still need that right.

## Schema and service verbs

| Entity | Verb | Parameters | Requires | What it does |
|:---|:---|:---|:---|:---|
| `Metadata.Entity` | `GetAliases` | `query` | not declared | Returns the table aliases SWIS assigns to a SWQL statement, without running it. |
| `Metadata.Entity` | `GetSchemaLoadTime` | `(none)` | not declared | Returns when the server last loaded its schema. Useful after installing a module. |
| `System.QueryPlanCache` | `Clear` | `(none)` | not declared | Clears the SWIS query plan cache. |

`Metadata.Entity.GetAliases` is the verb SolarWinds uses as the official REST Invoke example:
posting `["SELECT B.Caption FROM Orion.Nodes B"]` returns `{"B":"Orion.Nodes"}`.

## Querying the full set of 958

The catalog above is curated. Everything else is one command away, and there are three ways
to get at it depending on where you are.

### With this repository's CLI

```bash
# every verb on one entity, with signatures and summaries
python3 tools/schema_query.py verbs --entity Orion.AgentManagement.Agent

# search verb names across the whole schema
python3 tools/schema_query.py verbs --grep unmanage
python3 tools/schema_query.py verbs --grep 'poll'

# one verb in full: types, required flags, right, and ready-to-paste call syntax
python3 tools/schema_query.py verb Orion.HA.Pools CreatePool

# machine-readable, for piping into something else
python3 tools/schema_query.py verb Orion.HA.Pools CreatePool --json
```

### With `jq` against `data/schema/2026.2/verbs.json`

The file is a flat JSON array of 958 records. Each record has `entity`, `namespace`, `name`,
`summary`, `parameters` (an ordered array of `{name, type, required}`, some with `items` and
`description`), `returns`, `restPath` and `accessControl`.

```bash
cd /path/to/SolarWinds_OrionGuides
V=data/schema/2026.2/verbs.json
```

Every verb on one entity, rendered as a signature:

```bash
jq -r '.[] | select(.entity == "Orion.Nodes")
       | "\(.name)(\([.parameters[]?.name] | join(", ")))"' "$V"
```

Every entity that declares a verb of a given name, which is how you answer "what else can I
unmanage":

```bash
jq -r '.[] | select(.name | test("^(Un|Re)manage$")) | "\(.entity).\(.name)"' "$V"
```

Every verb requiring a particular right:

```bash
jq -r 'map(select(.accessControl[]?.right == "allowUnmanage"))
       | .[] | "\(.entity).\(.name)"' "$V"
```

Verb counts per namespace:

```bash
jq -r 'group_by(.namespace)[] | "\(.[0].namespace)\t\(length)"' "$V" | sort -k2 -nr
```

Verbs that take an array as their only parameter. There are 55 of them, and they are exactly
the set that needs the PowerShell leading-comma workaround described in
[invoke-verbs.md](invoke-verbs.md#the-single-array-argument-pitfall):

```bash
jq -r '.[] | select((.parameters | length) == 1 and .parameters[0].type == "array")
       | "\(.entity).\(.name)(\(.parameters[0].name))"' "$V"
```

Verbs whose parameter list is empty. **164 records fall into this bucket, and it has two
different meanings**: the verb genuinely takes no arguments, or its signature was not
published in machine-readable form. 84 of the 164 have no `/Invoke/` path in the Swagger
contract at all, 70 of those in the `Cortex` namespace. Treat an empty `parameters` array as
"unknown, go and check the server" rather than "takes nothing":

```bash
jq -r '.[] | select(.parameters == []) | "\(.entity).\(.name)"' "$V"
```

Full record for one verb, when you want the parameter types and descriptions:

```bash
jq '.[] | select(.entity == "Orion.Nodes" and .name == "StartRealTimePolling")' "$V"
```

### Against your own server

This is the authoritative answer, because your server may be a different platform version and
will certainly have a different set of modules installed:

```sql
SELECT v.Entity.FullName AS EntityName, v.Name AS VerbName, v.CanInvoke, v.Summary
FROM Metadata.Verb v
WHERE v.IsInternal = FALSE
ORDER BY v.Entity.FullName, v.Name
```

```sql
SELECT Position, Name, Type, IsOptional, Summary
FROM Metadata.VerbArgument
WHERE EntityName = 'Orion.HA.Pools' AND VerbName = 'CreatePool'
ORDER BY Position
```

Everything the `Metadata` namespace can tell you is in
[metadata-introspection.md](metadata-introspection.md).

## Where to go next

- [invoke-verbs.md](invoke-verbs.md) explains how to call any of these, from REST, PowerShell
  and Python, with six fully worked examples.
- [metadata-introspection.md](metadata-introspection.md) covers live schema introspection.
- [../reference/verb-index.md](../reference/verb-index.md) is the complete generated table of
  all 958 verbs.
- [../reference/netobject-types.md](../reference/netobject-types.md) maps entity types to the
  NetObject prefixes that `netObjectId` arguments expect.

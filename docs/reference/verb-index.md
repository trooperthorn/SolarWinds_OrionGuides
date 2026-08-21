<!-- GENERATED FILE. Do not edit by hand.
     Produced by tools/build_reference_docs.py from data/schema/2026.2/.
     Regenerate with: make docs-reference -->

# Verb index

Every invokable verb in platform version **2026.2**: 1021 verbs, of which 848 carry typed, named, ordered parameters recovered from the SWIS Swagger contract.

**Arguments are positional.** The names below come from the contract and from the documentation, but they never travel on the wire: both the REST body and `Invoke-SwisVerb` send an ordered array. The order in the Signature column is therefore the whole contract, and getting it wrong produces a type error at best and a silent misfire at worst.

For one verb in full, including parameter types, descriptions, required flags and ready-to-paste call syntax:

```bash
python3 tools/schema_query.py verb Orion.Nodes Unmanage
```

On a live server, the same answer comes from `Metadata.VerbArgument`:

```sql
SELECT Position, Name, Type, IsOptional
FROM Metadata.VerbArgument
WHERE EntityName = 'Orion.Nodes' AND VerbName = 'Unmanage'
ORDER BY Position
```

## Namespaces

| Namespace | Verbs |
| --- | ---: |
| [Orion](#orion) | 676 |
| [Cirrus](#cirrus) | 132 |
| [Cortex](#cortex) | 83 |
| [IPAM](#ipam) | 67 |
| [NCM](#ncm) | 29 |
| [UamsClient](#uamsclient) | 11 |
| [PlatformConnect](#platformconnect) | 7 |
| [PlatformBridge](#platformbridge) | 6 |
| [Cli](#cli) | 4 |
| [System](#system) | 3 |
| [Metadata](#metadata) | 2 |
| [SOC](#soc) | 1 |

## Orion

| Entity | Verb | Signature | Returns | Requires | Description |
| --- | --- | --- | --- | --- | --- |
| `Orion.ADM.NodeInventory` | `Disable` | `(nodeIds)` | `System.Void` | `manageNodes` | Disables polling of inventory on set of nodes. |
| `Orion.ADM.NodeInventory` | `Enable` | `(nodeIds)` | `System.Void` | `manageNodes` | Enables polling of inventory on set of nodes. |
| `Orion.ADM.NodeInventory` | `PollNow` | `(nodeIds)` | `System.Void` | `manageNodes` | Poll inventory from set of nodes. |
| `Orion.ADM.NodeInventory` | `ScheduleEnable` | `(jobTag, nodeIds, millisecondsTimeout)` | `System.Void` | `manageNodes` | More intelligent 'enable'. During execution adm plugin is installed if not exists. 'Enable' is… |
| `Orion.ADM.NodeInventory` | `SchedulePollNow` | `(jobTag, nodeIds, millisecondsTimeout)` | `string` | `manageNodes` | More intelligent 'poll now' which can be resolved by its guid. It also triggers an indication w… |
| `Orion.ADM.NodeInventory` | `UninstallConnectionQualityAgentPlugin` | `()` | `System.Void` | `manageNodes` | Uninstall 'ADMConnectionQuality' agent plugin from all nodes with agent where this plugin is in… |
| `Orion.AIIM.AiOpsMetricStatus` | `SaveAiOpsMetricStatus` | `(sourceUri, metricName, timestampUtc, norLowerBounds, norUpperBounds, norValidFromUtc, norValidUntilUtc)` | `System.Void` |  | The verb for saving AiOps metric status |
| `Orion.APIPoller.ApiPoller` | `AssignTemplate` | `(entityType, entityId, templateId, configuration, parameters)` | `number` | `manageNodes` | Assign a new ApiPoller Template |
| `Orion.APIPoller.ApiPoller` | `CreateApiPollerFromTemplate` | `(entityType, entityId, template, configuration, parameters)` | `number` | `manageNodes` | Create new ApiPoller Template |
| `Orion.APIPoller.ApiPoller` | `ExportTemplateFromApiPoller` | `(apiPollerId)` | `string` | `manageNodes` | Export an ApiPoller Template |
| `Orion.APIPoller.Templates` | `DeleteTemplate` | `(id)` | `boolean` | `manageNodes` | Delete ApiPoller Template |
| `Orion.APIPoller.Templates` | `ExportTemplate` | `(id)` | `string` | `manageNodes` | Export an ApiPoller Template |
| `Orion.APIPoller.Templates` | `ImportTemplate` | `(template)` | `number` | `manageNodes` | Import a new ApiPoller Template |
| `Orion.APM.ActiveDirectory.Application` | `AssignApplication` | `(nodeId, serializedSettings)` | `number` | `manageNodes` | Assign Active Directory application to the specified node. |
| `Orion.APM.ActiveDirectory.Application` | `DeleteDisabledComponentsData` | `(applicationId)` | `System.Void` | `manageNodes` | Delete disabled components data from specified Active Directory application. |
| `Orion.APM.ActiveDirectory.Application` | `DisableDomainComponents` | `(applicationId)` | `System.Void` | `manageNodes` | Disable domain components on specified Active Directory application. |
| `Orion.APM.Application` | `CreateApplication` | `(nodeId, applicationTemplateId, credentialSetId, skipIfDuplicate, applicationSettings?)` | `number` | `manageNodes` | Create new application. |
| `Orion.APM.Application` | `DeleteApplication` | `(applicationId)` | `System.Void` | `manageNodes` | Delete existed application. |
| `Orion.APM.Application` | `PollNow` | `(applicationId)` | `System.Void` | `manageNodes` | Poll existed application. |
| `Orion.APM.Application` | `Remanage` | `(netObjetId)` | `System.Void` |  | Remanage existed application. |
| `Orion.APM.Application` | `TriggerInstantTemplateGroupAssignment` | `()` | `System.Void` | `manageNodes` | Trigger instant template group assignment. |
| `Orion.APM.Application` | `TriggerScheduledTemplateGroupAssignment` | `()` | `System.Void` | `manageNodes` | Trigger scheduled template group assignment. |
| `Orion.APM.Application` | `Unmanage` | `(netObjetId, unmanageTime, remanageTime, isRelative, allowOverlapping?)` | `System.Void` |  | Unmanage existed application. |
| `Orion.APM.ApplicationCustomProperties` | `CreateCustomProperty` | `(propertyName, description, valueType, size, validRange, parser, header, alignment, format, units, usageFlags, mandatory, defaultValue, sourceId?, sourceName?)` | `System.Void` |  | Create application custom property. |
| `Orion.APM.ApplicationCustomProperties` | `CreateCustomPropertyWithValues` | `(propertyName, description, valueType, size, validRange, parser, header, alignment, format, units, values, usageFlags, mandatory, defaultValue, sourceId?, sourceName?)` | `System.Void` |  | Create application custom property with values. |
| `Orion.APM.ApplicationCustomProperties` | `DeleteCustomProperty` | `(propertyName, sourceId?, sourceName?)` | `System.Void` |  | Delete application custom property. |
| `Orion.APM.ApplicationCustomProperties` | `ModifyCustomProperty` | `(propertyName, description, size, values, usageFlags, mandatory, defaultValue, sourceId?, sourceName?)` | `System.Void` |  | Modify application custom property. |
| `Orion.APM.ApplicationTemplate` | `DeleteTemplate` | `(applicationTemplateId)` | `System.Void` |  | Delete existed application template. |
| `Orion.APM.ApplicationTemplate` | `ExportTemplate` | `(templateId)` | `string` |  | Export existed application template to stream. |
| `Orion.APM.ApplicationTemplate` | `GetTestComponentStatus` | `(jobs)` | `array` |  | Returns list of status of template components test. |
| `Orion.APM.ApplicationTemplate` | `ImportTemplate` | `(templateData)` | `number` |  | Import application template |
| `Orion.APM.ApplicationTemplate` | `StartTestComponents` | `(nodeId, templateUniqueId, credentialId)` | `array` |  | Start application template components test. |
| `Orion.APM.ApplicationTemplate` | `UpdateApplicationTemplateSettings` | `(applicationTemplateId, settings)` | `System.Void` |  | Update application template settings. |
| `Orion.APM.Component` | `CalculateBaselineThresholds` | `(componentId, thresholdName)` | `SolarWinds.APM.Common.Models.Threshold` |  | Calculates and sets baseline thresholds for component threshold |
| `Orion.APM.Exchange.Application` | `GetConfigurationResult` | `(executionKey)` | `SolarWinds.Data.Providers.APM.Verbs.Applica…` | `manageNodes` | It is getting the result of exchange configuration. As a parameter it require executionKey retu… |
| `Orion.APM.Exchange.Application` | `ScheduleConfiguration` | `(applicationId, credentialsId)` | `string` | `manageNodes` | Schedule configuration existing exchange application for monitoring. It returns executionKey th… |
| `Orion.APM.IIS.Application` | `GetConfigurationResult` | `(executionKey)` | `SolarWinds.Data.Providers.APM.Verbs.Applica…` | `manageNodes` | It is getting the result of IIS configuration. As a parameter it require executionKey returned… |
| `Orion.APM.IIS.Application` | `ScheduleConfiguration` | `(applicationId, credentialsId)` | `string` | `manageNodes` | Schedule configuration existing IIS application for monitoring. It returns executionKey that is… |
| `Orion.APM.IIS.ApplicationPool` | `Restart` | `(nodeId, applicationId, credentialId, poolName, applicationTypeId)` | `number` |  | Restart IIS application pool. |
| `Orion.APM.IIS.ApplicationPool` | `Start` | `(nodeId, applicationId, credentialId, poolName, applicationTypeId)` | `number` |  | Start IIS application pool. |
| `Orion.APM.IIS.ApplicationPool` | `Stop` | `(nodeId, applicationId, credentialId, poolName, applicationTypeId)` | `number` |  | Stop IIS application pool. |
| `Orion.APM.IIS.Site` | `Restart` | `(nodeId, applicationId, credentialId, siteName, applicationTypeId)` | `number` |  | Restart IIS site. |
| `Orion.APM.IIS.Site` | `Start` | `(nodeId, applicationId, credentialId, siteName, applicationTypeId)` | `number` |  | Start IIS site. |
| `Orion.APM.IIS.Site` | `Stop` | `(nodeId, applicationId, credentialId, siteName, applicationTypeId)` | `number` |  | Stop IIS site. |
| `Orion.APM.LicenseInfo` | `GetLicenseLimit` | `()` | `number` |  | Returns license limit of polled elements. |
| `Orion.APM.LicenseInfo` | `GetLicensedEntitiesCount` | `(engineName, entityPrefix)` | `number` |  | Returns number of licensed entities of specific type on particular engine. |
| `Orion.APM.LicenseInfo` | `GetLicensedEntityCountFromAllEngines` | `(entityPrefix)` | `number` |  | Returns number of licensed entity on all engines. |
| `Orion.APM.LicenseInfo` | `RefreshLicenseCache` | `()` | `System.Void` |  | Trigger refresh license cache. |
| `Orion.APM.ServerManagement` | `RebootNode` | `(nodeId)` | `number` |  | Restart the node. |
| `Orion.APM.ServerManagement` | `RestartService` | `(nodeId, credentialId, serviceName)` | `number` |  | Restart windows service. |
| `Orion.APM.ServerManagement` | `StartService` | `(nodeId, credentialId, serviceName)` | `number` |  | Start windows service. |
| `Orion.APM.ServerManagement` | `StopService` | `(nodeId, credentialId, serviceName)` | `number` |  | Stop windows service. |
| `Orion.ARM.Settings` | `DeleteWebApiSettings` | `()` | `boolean` |  |  |
| `Orion.ARM.Settings` | `GetWebApiSettings` | `()` | `SolarWinds.Arm.Common.Models.WebApiSettings` |  |  |
| `Orion.ARM.Settings` | `SetWebApiSettings` | `(baseUrl, username, encryptedPassword)` | `boolean` |  |  |
| `Orion.ARM.Settings` | `TestWebApiSettings` | `(baseUrl, username, encryptedPassword)` | `boolean` |  |  |
| `Orion.ASA.Interfaces` | `RemoveFavorite` | `(entityId)` | `SolarWinds.Orion.NetMan.Firewalls.Common.Mo…` | `manageNodes` |  |
| `Orion.ASA.Interfaces` | `SetFavorite` | `(entityId)` | `SolarWinds.Orion.NetMan.Firewalls.Common.Mo…` | `manageNodes` |  |
| `Orion.ASA.Node` | `ExecuteCliCommand` | `(hostname, username, password, command, enablePassword?)` | `string` | `manageNodes` | Execute CLI command using SSH protocol on port 22 |
| `Orion.Accounts` | `ChangePassword` | `(accountId, password)` | `System.Void` | `admin` | Changes password of the specified Account with provided string. |
| `Orion.Accounts` | `CreateAccount` | `(accountType, properties)` | `System.Void` | `admin` |  |
| `Orion.Accounts` | `CreateOneTimeLoginToken` | `(accountId)` | `string` | `admin` | Creates a one time login token. |
| `Orion.Accounts` | `CreateOrionAccount` | `(accountID, password)` | `System.Void` | `admin` | Creates a new Account with provided Account ID and Password. |
| `Orion.Accounts` | `CreateSamlAccount` | `(accountType, userOrGroupName)` | `System.Void` | `admin` | Adds SAML user account specified by its name into Orion. |
| `Orion.Accounts` | `CreateVirtualAccount` | `(accountID, highestPriorityGroupName, groupAccountTypeId)` | `System.Void` | `admin` | Creates virtual user account. |
| `Orion.Accounts` | `CreateWindowsAccount` | `(accountType, userOrGroupName, adminUser?, adminPassword?)` | `System.Void` | `admin` | Adds Windows User accounts into Orion based on the provided account name search string. |
| `Orion.Accounts` | `DeleteAccount` | `(accountID)` | `System.Void` | `admin` | Deletes specified account. |
| `Orion.Accounts` | `ResetPassword` | `(accountId)` | `System.Void` | `admin` | Resets password to empty password. |
| `Orion.Accounts` | `UpdateAccount` | `(accountID, properties)` | `System.Void` | `admin` | Updates properties of the specified Account with provided values. |
| `Orion.Actions` | `DeleteActionsByAssignments` | `(parentID, environmentType)` | `System.Void` | `admin`, `manageAlerts` |  |
| `Orion.Actions` | `DeleteActionsByAssignmentsAndCategory` | `(parentID, environmentType, categoryType)` | `System.Void` | `admin`, `manageAlerts` |  |
| `Orion.Actions` | `SaveActionsForAssignments` | `(parentID, environmentType, categoryType, actions)` | `boolean` | `admin`, `allowDisableAlert`, `manageAlerts`, `manageReports` |  |
| `Orion.Actions` | `TestAlertingAction` | `(action, context)` | `SolarWinds.Orion.Core.Models.Actions.Action…` | `manageAlerts` |  |
| `Orion.Actions` | `TestReportingAction` | `(action, context)` | `SolarWinds.Orion.Core.Models.Actions.Action…` | `admin` |  |
| `Orion.Actions` | `UpdateAction` | `(action)` | `boolean` | `admin`, `manageAlerts` |  |
| `Orion.Actions` | `UpdateActionsDescriptions` | `(actionsDescriptions)` | `boolean` | `admin`, `manageAlerts` | This verb updates actions descriptions after updating of actions properties. |
| `Orion.Actions` | `UpdateActionsFrequencies` | `(timePeriods, actionsIds)` | `boolean` | `admin`, `manageAlerts` | This verb updates actions frequencies after multi editing of actions |
| `Orion.Actions` | `UpdateActionsProperties` | `(properties, actionsIds)` | `boolean` | `admin`, `manageAlerts` |  |
| `Orion.AgentManagement.Agent` | `AddAgent` | `(agent)` | `number` |  | Creates Agent entry. |
| `Orion.AgentManagement.Agent` | `AddPassiveAgent` | `(agentName, agentHostname, agentIpAddress, agentPort, pollingEngineId, sharedSecret, proxyId, autoUpdateEnabled?, testPassiveAgentConnection?)` | `number` |  | Adds passive agent. This verb exists for usability convenience and uses AddAgent verb internall… |
| `Orion.AgentManagement.Agent` | `ApproveReboot` | `(agentId)` | `boolean` |  | Approval for an agent to reboot. |
| `Orion.AgentManagement.Agent` | `ApproveUpdate` | `(agentId)` | `System.Void` |  | Approval for an agent to be updated. |
| `Orion.AgentManagement.Agent` | `AssignToEngine` | `(agentId, pollerId)` | `boolean` |  | Assigns an agent to a polling engine. |
| `Orion.AgentManagement.Agent` | `CollectDiagnostics` | `(agentId, pathToStoreAgentDiagnostics, diagnosticCollectionTimeoutInMinutes, areAgentLogsSelected?, areEventLogsSelected?, isNetStatSelected?, areRunningProcessesSelected?)` | `boolean` |  | Will try to collect diagnostics for agent identified by AgentId and store it to passed path wai… |
| `Orion.AgentManagement.Agent` | `Delete` | `(agentId)` | `System.Void` |  | Deletes the agent without uninstalling it. |
| `Orion.AgentManagement.Agent` | `Deploy` | `(pollingEngineId, agentName, hostname, ipAddress, machineUserName, machinePassword, additionalUsername?, additionalPassword?, passwordIsPrivateKey?, privateKeyPassword?, agentMode?, installPackageFallbackId?)` | `number` |  | Deploys an agent to a machine defined by hostname and/or IP address. |
| `Orion.AgentManagement.Agent` | `DeployPlugin` | `(agentId, pluginId)` | `System.Void` |  | Deploys the specified plugin to the agent |
| `Orion.AgentManagement.Agent` | `DeployToNode` | `(nodeId, machineUserName?, machinePassword?, additionalUsername?, additionalPassword?, passwordIsPrivateKey?, privateKeyPassword?, agentMode?, installPackageFallbackId?)` | `number` |  | Deploys an agent to an existing node using the supplied credentials. |
| `Orion.AgentManagement.Agent` | `GetLicensedAgentPluginsInAMSRepository` | `(pollingEngineId)` | `System.Collections.Generic.IEnumerable~Syst…` |  | Return list of plugin Ids, which are in AMS repository and are licensed |
| `Orion.AgentManagement.Agent` | `PromoteAgentToRemoteCollector` | `(agentId)` | `System.Void` |  |  |
| `Orion.AgentManagement.Agent` | `RedeployPlugin` | `(agentId, pluginId)` | `System.Void` |  | Redeploys the specified plugin to the agent |
| `Orion.AgentManagement.Agent` | `RestartAgent` | `(agentId)` | `boolean` |  | Initiate Orion Agent service restart. |
| `Orion.AgentManagement.Agent` | `TestPassiveAgentConnection` | `(agent)` | `SolarWinds.AgentManagement.Common.Models.Ag…` |  | Verifies whether connection to passive agent is possible. |
| `Orion.AgentManagement.Agent` | `TestWithEngine` | `(agentId, pollerId)` | `boolean` |  | Tests the connection between the agent and AMS |
| `Orion.AgentManagement.Agent` | `Uninstall` | `(agentId)` | `boolean` |  | Uninstalls the agent. |
| `Orion.AgentManagement.Agent` | `UninstallPlugin` | `(agentId, pluginId)` | `System.Void` |  | Uninstalls the specified plugin from the agent |
| `Orion.AgentManagement.Agent` | `UpdateAgent` | `(agent, updateRemoteSettings)` | `System.Void` |  | Updates Agent entry. |
| `Orion.AgentManagement.Agent` | `ValidateDeploymentCredentials` | `(pollingEngineId, hostname, ipAddress, machineUserName, machinePassword, additionalUsername?, additionalPassword?, passwordIsPrivateKey?, privateKeyPassword?, installPackageFallbackId?)` | `System.Tuple~System.Boolean_System.String_S…` |  | Validates if provided credentials are valid for agent deployment. If credentials pass validatio… |
| `Orion.AgentManagement.Proxy` | `AddProxy` | `(pollingEngineId, proxy)` | `number` |  | Adds a proxy entry. |
| `Orion.AgentManagement.Proxy` | `DeleteProxy` | `(pollingEngineId, proxyId)` | `boolean` |  | Delete a proxy entry. |
| `Orion.AlertActive` | `Acknowledge` | `(alertObjectIds, notes)` | `boolean` | `clearEvents` | Acknowledge active alerts, based on array of alert active ids and desired notes. |
| `Orion.AlertActive` | `AppendNote` | `(alertObjectIds, note)` | `boolean` | `clearEvents` | Appends note to Alert object. |
| `Orion.AlertActive` | `ClearAlert` | `(alertObjectIds)` | `boolean` | `clearEvents` | Delete active alert from database. Manual alert reset |
| `Orion.AlertActive` | `Unacknowledge` | `(alertObjectIds)` | `boolean` | `clearEvents` | Unacknowledge active alerts, based on array of alert active ids. |
| `Orion.AlertConfigurations` | `Export` | `(alertId, stripSensitiveData?, protectionPassword?)` | `string` | `admin`, `manageAlerts` | This verb exports alert definition |
| `Orion.AlertConfigurations` | `GetComplexPropertiesByAlertID` | `(alertId)` | `array` | `admin`, `manageAlerts` | This verb get parsed alert's addition fields |
| `Orion.AlertConfigurations` | `Import` | `(alertXml, stripSensitiveInformation?, protectionPassword?)` | `SolarWinds.Orion.Core.Common.Alerting.Alert…` | `admin`, `manageAlerts` | This verb imports alert into system from alert xml |
| `Orion.AlertConfigurations` | `MigrateAdvancedAlert` | `()` | `unknown` | `admin` |  |
| `Orion.AlertConfigurations` | `MigrateAdvancedAlertFromXML` | `()` | `unknown` | `admin` |  |
| `Orion.AlertConfigurations` | `MigrateAllAdvancedAlerts` | `()` | `unknown` | `admin` |  |
| `Orion.AlertConfigurationsCustomProperties` | `CreateCustomProperty` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.AlertConfigurationsCustomProperties` | `CreateCustomPropertyWithValues` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Value, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.AlertConfigurationsCustomProperties` | `DeleteCustomProperty` | `(PropertyName)` | `System.Void` |  |  |
| `Orion.AlertConfigurationsCustomProperties` | `ModifyCustomProperty` | `(PropertyName, Description, Size, Values, Usages?, Mandatory?, Default?, SourceId?, SourceName?, propertyDisplayName?)` | `System.Void` |  |  |
| `Orion.AlertConfigurationsCustomProperties` | `ValidateCustomProperty` | `(PropertyName, Description, ValueType, Size, Value, Usages?, propertyDisplayName?)` | `SolarWinds.Orion.Core.Common.Models.CustomP…` |  |  |
| `Orion.AlertStatus` | `Acknowledge` | `()` | `unknown` | `clearEvents` |  |
| `Orion.AlertStatus` | `AcknowledgeAlert` | `()` | `unknown` |  |  |
| `Orion.AlertStatus` | `AddNote` | `()` | `unknown` | `clearEvents` |  |
| `Orion.AlertSuppression` | `GetAlertSuppressionState` | `(entityUris)` | `array` | `everyone` | Get Alert Suppression State for provided list of entities. |
| `Orion.AlertSuppression` | `ResumeAlerts` | `(entityUris)` | `System.Void` | `allowUnmanage` | Alerts for entities defined in entityUris array will be triggered as usual. |
| `Orion.AlertSuppression` | `SuppressAlerts` | `(entityUris, suppressFrom?, suppressUntil?, allowOverlapping?, reason?)` | `System.Void` | `allowUnmanage` | Do not trigger any alerts for entities defined in entityUris array during the suppressFrom-supp… |
| `Orion.AssetInventory.Polling` | `DisablePollingForNodes` | `(nodeIds)` | `System.Void` | `manageNodes` |  |
| `Orion.AssetInventory.Polling` | `EnablePollingForNodes` | `(nodeIds)` | `boolean` | `manageNodes` |  |
| `Orion.AssetInventory.Polling` | `PollNow` | `(nodeIds)` | `System.Void` | `manageNodes` |  |
| `Orion.Banners.BannerAccountSettings` | `DismissBanner` | `(bannerId, accountId)` | `System.Void` |  |  |
| `Orion.Banners.BannerAccountSettings` | `IsBannerDismissed` | `(bannerId, accountId)` | `boolean` |  |  |
| `Orion.Banners.Instances` | `DeleteBanner` | `(bannerId)` | `System.Void` |  |  |
| `Orion.Banners.Instances` | `DeleteBannerInternal` | `(bannerIds)` | `System.Void` |  |  |
| `Orion.Banners.Instances` | `GetBannerById` | `(bannerId)` | `string` |  |  |
| `Orion.Banners.Instances` | `GetNotDismissedBannersByAccount` | `(accountId)` | `string` |  |  |
| `Orion.Banners.Instances` | `SetBannerEnabledState` | `(bannerId, enabled)` | `System.Void` |  |  |
| `Orion.Banners.Instances` | `SetBannerEnabledStateInternal` | `(bannerIds, enabled)` | `System.Void` |  |  |
| `Orion.Banners.Instances` | `UpsertBanner` | `(bannerId, message, justification, title, type, status, rank, backgroundColor, icon, link, owner)` | `System.Void` |  |  |
| `Orion.Banners.Instances` | `UpsertBannerInternal` | `(bannerDefinitionAsJson)` | `System.Void` |  |  |
| `Orion.Cloud.Aws.Instances` | `ForceStopInstance` | `(virtualMachineId)` | `SolarWinds.VIM.CloudMonitoring.Common.Model…` | `manageNodes` |  |
| `Orion.Cloud.Aws.Instances` | `TerminateInstance` | `(virtualMachineId)` | `SolarWinds.VIM.CloudMonitoring.Common.Model…` | `manageNodes` |  |
| `Orion.Cloud.Aws.Instances` | `TerminateInstanceAndRemoveNode` | `(virtualMachineId)` | `SolarWinds.VIM.CloudMonitoring.Common.Model…` | `manageNodes` |  |
| `Orion.Cloud.Aws.Regions` | `GetAwsRegions` | `(credentials)` | `SolarWinds.CloudMonitoring.Contract.Models.…` |  |  |
| `Orion.Cloud.Azure.Regions` | `GetAzureRegions` | `(credentials)` | `SolarWinds.CloudMonitoring.Contract.Models.…` |  |  |
| `Orion.Cloud.Gcp.Regions` | `GetGcpRegions` | `(credentials, projectId)` | `SolarWinds.CloudMonitoring.Contract.Models.…` |  |  |
| `Orion.Cloud.Instances` | `DeleteInstance` | `(virtualMachineId)` | `SolarWinds.VIM.CloudMonitoring.Common.Model…` | `manageNodes` |  |
| `Orion.Cloud.Instances` | `DeleteInstanceWithNode` | `(virtualMachineId)` | `SolarWinds.VIM.CloudMonitoring.Common.Model…` | `manageNodes` |  |
| `Orion.Cloud.Instances` | `PollNow` | `(virtualMachineId)` | `SolarWinds.VIM.CloudMonitoring.Common.Model…` | `manageNodes` |  |
| `Orion.Cloud.Instances` | `RebootInstance` | `(virtualMachineId)` | `SolarWinds.VIM.CloudMonitoring.Common.Model…` | `manageNodes` |  |
| `Orion.Cloud.Instances` | `Remanage` | `(virtualMachineId)` | `SolarWinds.VIM.CloudMonitoring.Common.Model…` | `allowUnmanage` |  |
| `Orion.Cloud.Instances` | `StartInstance` | `(virtualMachineId)` | `SolarWinds.VIM.CloudMonitoring.Common.Model…` | `manageNodes` |  |
| `Orion.Cloud.Instances` | `StopInstance` | `(virtualMachineId)` | `SolarWinds.VIM.CloudMonitoring.Common.Model…` | `manageNodes` |  |
| `Orion.Cloud.Instances` | `Unmanage` | `(virtualMachineId)` | `SolarWinds.VIM.CloudMonitoring.Common.Model…` | `allowUnmanage` |  |
| `Orion.Container` | `AddDefinition` | `(containerId, memberDefinition)` | `System.Void` |  |  |
| `Orion.Container` | `AddDefinitions` | `(containerId, memberDefinitions)` | `System.Void` |  |  |
| `Orion.Container` | `CreateContainer` | `(name, owner, frequency, statusCalculator, description, pollingEnabled, memberDefinitions)` | `number` |  |  |
| `Orion.Container` | `CreateContainerWithParent` | `(parentId, name, owner, frequency, statusCalculator, description, pollingEnabled, memberDefinitions)` | `number` |  |  |
| `Orion.Container` | `DeleteContainer` | `(containerId)` | `System.Void` |  |  |
| `Orion.Container` | `DeleteDefinition` | `(definitionId)` | `System.Void` |  |  |
| `Orion.Container` | `DeleteDefinitions` | `(containerId, definitionIds)` | `System.Void` |  |  |
| `Orion.Container` | `GetDefinitionFilterQuery` | `(queryDefinition)` | `string` |  |  |
| `Orion.Container` | `SetDefinitions` | `(containerId, memberDefinitions)` | `System.Void` |  |  |
| `Orion.Container` | `UpdateContainer` | `(containerId, name, owner, frequency, statusCalculator, description, pollingEnabled)` | `System.Void` |  |  |
| `Orion.Container` | `UpdateDefinition` | `(definitionId, memberDefinition)` | `System.Void` |  |  |
| `Orion.ContainerMemberDefinition` | `GetFirstNMembers` | `(definition, topCountForEachDefinition)` | `System.Data.DataTable` |  |  |
| `Orion.ContainerMemberDefinition` | `GetMembers` | `(definition)` | `System.Data.DataTable` |  |  |
| `Orion.Credential` | `CreateCredentials` | `(type, properties, owner?)` | `number` | `manageNodes` | Creates credential with provided list of properties |
| `Orion.Credential` | `CreateSNMPCredentials` | `(name, community, owner?)` | `number` | `manageNodes` | Creates SNMP v1 or v2c credentials |
| `Orion.Credential` | `CreateSNMPv3Credentials` | `(name, username, context, authenticationMethodValue, authenticationPassword, authenticationKeyIsPassword, privacyMethodValue, privacyPassword, privacyKeyIsPassword, owner?)` | `number` | `manageNodes` | Creates SNMP v3 credentials |
| `Orion.Credential` | `CreateUsernamePasswordCredentials` | `(name, username, password, owner?)` | `number` | `manageNodes` | Creates credentials with username and password, these are used for example by WMI polling. |
| `Orion.Credential` | `CreateUsernamePasswordWithContentCredentials` | `(name, username, password, content, owner?)` | `number` | `manageNodes` | Creates credentials with username, password and content, these are used for example by PaloAlto… |
| `Orion.Credential` | `UpdateCredentials` | `(id, properties)` | `System.Void` | `manageNodes` | Updates credential properties |
| `Orion.Credential` | `UpdateSNMPCredentials` | `(credentialId, name, community)` | `System.Void` | `manageNodes` | Updates SNMP v1 or v2c credentials. |
| `Orion.Credential` | `UpdateSNMPv3Credentials` | `(credentialId, name, username, context, authenticationMethodValue, authenticationPassword, authenticationKeyIsPassword, privacyMethodValue, privacyPassword, privacyKeyIsPassword)` | `System.Void` | `manageNodes` | Updates SNMPv3 credentials. |
| `Orion.Credential` | `UpdateUsernamePasswordCredentials` | `(credentialId, name, username, password)` | `System.Void` | `manageNodes` | Updates credentials with username and password. These are used, for example, by WMI polling. |
| `Orion.Credential` | `UpdateUsernamePasswordWithContentCredentials` | `(credentialId, name, username, password, content)` | `System.Void` | `manageNodes` | Updates credentials with username, password and content. These are used for example by PaloAlto… |
| `Orion.DPA.DpaServer` | `RefreshSchema` | `(dpaServerId)` | `boolean` |  | Refresh federation schema of for particular DPA Server |
| `Orion.DPI.Probes` | `DeployLocalTrafficProbe` | `(nodeId, machineUserName, machinePassword, probeName, probeDescription)` | `SolarWinds.DPI.Common.Models.ProbeDeploymen…` |  |  |
| `Orion.DPI.Probes` | `DeploySpanPortProbe` | `(nodeId, machineUserName, machinePassword, probeName, probeDescription)` | `SolarWinds.DPI.Common.Models.ProbeDeploymen…` |  |  |
| `Orion.DPI.Probes` | `GetProbeCapabilities` | `(probeId)` | `SolarWinds.DPI.Common.Models.ProbeCapabilit…` |  |  |
| `Orion.DPI.Probes` | `ReloadAppDefinitions` | `(probeId)` | `boolean` |  |  |
| `Orion.DPI.Probes` | `ReloadProbeSettings` | `(probeId)` | `boolean` |  |  |
| `Orion.Dashboards.Instances` | `AddWidget` | `(dashboardID, widgetID, position, isReference?)` | `System.Void` |  |  |
| `Orion.Dashboards.Instances` | `Clone` | `(dashboardID, displayName, asPrivate)` | `string` |  |  |
| `Orion.Dashboards.Instances` | `DereferenceWidget` | `(dashboardID, widgetID)` | `string` |  |  |
| `Orion.Dashboards.Instances` | `Export` | `(dashboardId)` | `string` |  |  |
| `Orion.Dashboards.Instances` | `ExportForI18N` | `(dashboardId, stringLibrary?)` | `string` |  |  |
| `Orion.Dashboards.Instances` | `GetDashboardBreadcrumbs` | `(routeIdPath)` | `string` |  |  |
| `Orion.Dashboards.Instances` | `GetDashboardGroup` | `(dashboardId, accountId, isAdmin)` | `string` |  |  |
| `Orion.Dashboards.Instances` | `GetDashboardViewPreference` | `(dashboardId, accountId)` | `string` |  |  |
| `Orion.Dashboards.Instances` | `Import` | `(definition)` | `System.Void` |  |  |
| `Orion.Dashboards.Instances` | `RemoveWidget` | `(dashboardID, widgetID)` | `System.Void` |  |  |
| `Orion.Dashboards.Instances` | `RestoreToOriginal` | `(dashboardID)` | `System.Void` |  |  |
| `Orion.Dashboards.Instances` | `SetVisibility` | `(dashboardID, asPrivate)` | `System.Void` |  |  |
| `Orion.Dashboards.Instances` | `UpdateDashboardGroup` | `(dashboardDashboardGroupItemsJson, accountId, isAdmin)` | `boolean` |  |  |
| `Orion.Dashboards.Instances` | `UpdateIsSwitchedToLegacy` | `(dashboardId, accountId, isSwitchedToLegacy)` | `System.Void` |  |  |
| `Orion.Dashboards.Instances` | `UpdateWidgetLocation` | `(dashboardID, widgetID, position)` | `System.Void` |  |  |
| `Orion.Dashboards.Instances` | `WidgetToReference` | `(dashboardID, widgetID, targetWidgetID)` | `string` |  |  |
| `Orion.Dashboards.Widgets` | `Clone` | `(widgetID, asPrivate)` | `string` |  |  |
| `Orion.Dashboards.Widgets` | `Export` | `(widgetID)` | `string` |  |  |
| `Orion.Dashboards.Widgets` | `Import` | `(widgetID, definition)` | `System.Void` |  |  |
| `Orion.Dashboards.Widgets` | `RemoveAllLinks` | `(widgetID)` | `System.Void` |  |  |
| `Orion.Declarative.PollerTemplates` | `Execute` | `(pollerPrefix, clientSettings, credential, engineId)` | `SolarWinds.Orion.Declarative.Contract.Model…` |  |  |
| `Orion.Declarative.PollerTemplates` | `ExecuteWithCreds` | `(pollerPrefix, clientSettings, credentialId, engineId)` | `SolarWinds.Orion.Declarative.Contract.Model…` |  |  |
| `Orion.DeletedAutoDependencies` | `RemoveIgnoredAutoDependencies` | `(ids)` | `number` | `admin` | Removes ignored dependencies. |
| `Orion.Dependencies` | `RemoveDependencies` | `(ids)` | `number` | `admin` | Ignore dependencies. Such dependencies are ingored in Autodependency calculation. |
| `Orion.Discovery` | `CancelDiscovery` | `(profileId)` | `System.Void` |  |  |
| `Orion.Discovery` | `CreateCorePluginConfiguration` | `(context)` | `string` |  | Creates a new configuration for a plugin. |
| `Orion.Discovery` | `DeleteDiscoveryProfile` | `(profileId)` | `System.Void` |  | Deletes discovery profile by its profileId. |
| `Orion.Discovery` | `GetDiscoveryProfileResourcesResult` | `(profileId)` | `array` |  | Retrieves the list of discovered resources for a specific discovery profile |
| `Orion.Discovery` | `GetDiscoveryProgress` | `(profileId)` | `string` |  |  |
| `Orion.Discovery` | `GetImportDiscoveryResultsProgress` | `(importId)` | `SolarWinds.Orion.Core.Models.Discovery.Disc…` |  | Get the progress of ImportDiscoveryResults |
| `Orion.Discovery` | `ImportDiscoveryResults` | `(cfg)` | `string` |  | Import discovery results for set of discovered nodes |
| `Orion.Discovery` | `ResolveHostnameFromIp` | `(ipAddress, engineId)` | `string` |  | Get hostname from given IP address |
| `Orion.Discovery` | `ResolveIpFromHostname` | `(hostname, preferredAddressFamily, engineId)` | `string` |  | Get IP Address from given hostname |
| `Orion.Discovery` | `StartDiscovery` | `(context)` | `number` |  |  |
| `Orion.Discovery` | `StartDiscoveryProfile` | `(discoveryProfileId, engineId)` | `System.Void` |  | Starts discovery for specified profile ID |
| `Orion.Discovery` | `ValidateCredentials` | `(ipAddress, port, credentialsType, credentialsProperties, engineId, preferredSnmpVersion?)` | `boolean` |  | Check if provided credential is valid for given SNMP or WMI endpoint |
| `Orion.EOC.SiteAccess` | `SetEocSiteAccess` | `()` | `unknown` |  |  |
| `Orion.EOC.SiteAccounts` | `CreateAccount` | `(eocSiteID, credentialsType, accountName, password)` | `string` |  |  |
| `Orion.EOC.SiteAccounts` | `SetEocSiteAccount` | `(eocSiteID, credsType, username, password)` | `string` |  |  |
| `Orion.EOC.SiteAccounts` | `UpdateAccount` | `(eocSiteID, uri, accountName, credentialsType)` | `string` |  |  |
| `Orion.EOC.Sites` | `CreateSite` | `(host, userName, password, siteProperties)` | `string` |  |  |
| `Orion.EOC.Sites` | `RefreshSchema` | `(remoteSwisUri)` | `System.Void` |  |  |
| `Orion.ESI.IncidentIntegration` | `SetIncidentIntegrationState` | `(enabled)` | `System.Void` |  | Sets the state of incident integration respectd by Orion web UI. True is enabled, false means d… |
| `Orion.Environment` | `AuthorizeWindowsAccountForDatabase` | `(account)` | `boolean` | `admin` | Adds provided user to Orion database with db_owner permissions. |
| `Orion.Environment` | `CanInstall` | `(productId, productVersion, family, serverRole)` | `array` |  |  |
| `Orion.Environment` | `GetConnectionString` | `()` | `string` | `admin` | Returns connection string |
| `Orion.Environment` | `GetDatabaseAccessCredential` | `()` | `SolarWinds.Orion.Core.Common.Models.Databas…` | `admin` | Returns credential used to access Orion database when system is configured to use Windows authe… |
| `Orion.Environment` | `GetOrionServerCertificate` | `()` | `array` | `admin` | Returns Orion certificate |
| `Orion.Environment` | `GetProxySettings` | `()` | `SolarWinds.Data.Providers.Orion.Models.Prox…` | `admin` | Get the current internet Proxy settings |
| `Orion.Environment` | `GetSqlServerIpAddresses` | `()` | `array` | `admin` | Returns array of IP addresses of current SQL server |
| `Orion.Environment` | `StartPreStaging` | `()` | `System.Void` | `admin` | Pre-download all bits required for upgrade |
| `Orion.Environment` | `UninstallAll` | `()` | `System.Void` | `admin` | Uninstalls all SolarWinds products |
| `Orion.Events` | `Acknowledge` | `(eventIDs)` | `boolean` | `clearEvents` | Marks the specified event as acknowledged, typically used to clear events from active monitorin… |
| `Orion.F5.LTM.Server` | `LinkNode` | `(f5ServerId, nodeId)` | `System.Void` | `manageNodes` |  |
| `Orion.F5.LTM.Server` | `UnlinkNode` | `(f5ServerId)` | `System.Void` | `manageNodes` |  |
| `Orion.F5.System.Device` | `DisableApiPolling` | `(nodeId)` | `System.Void` | `manageNodes` |  |
| `Orion.F5.System.Device` | `EnableApiPolling` | `(nodeId, port, useSsl, userName, password, reservedSslCertificateIdentity?)` | `System.Void` | `manageNodes` |  |
| `Orion.F5.System.Device` | `TestApiPolling` | `(dnsName, ipAddress, port, useSsl, userName, password, reservedSslCertificateIdentity, engineId?)` | `SolarWinds.F5.Common.Models.API.F5ApiTestCo…` |  |  |
| `Orion.Features` | `Refresh` | `()` | `System.Void` | `admin` | Internal verb which enforce system to recalculate orion features |
| `Orion.Firewall.L2LTunnel` | `RemoveFavorite` | `(entityId)` | `SolarWinds.Orion.NetMan.Firewalls.Common.Mo…` | `manageNodes` |  |
| `Orion.Firewall.L2LTunnel` | `SetFavorite` | `(entityId)` | `SolarWinds.Orion.NetMan.Firewalls.Common.Mo…` | `manageNodes` |  |
| `Orion.Frequencies` | `DeleteFrequencies` | `(frequencyIds)` | `boolean` | `admin`, `manageAlerts`, `manageReports` |  |
| `Orion.Frequencies` | `SaveReportFrequencies` | `(frequencies)` | `array` | `admin`, `manageReports` |  |
| `Orion.Frequencies` | `SaveTimePeriodFrequencies` | `(frequencies)` | `array` | `admin`, `manageAlerts` |  |
| `Orion.GroupCustomProperties` | `CreateCustomProperty` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.GroupCustomProperties` | `CreateCustomPropertyWithValues` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Value, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.GroupCustomProperties` | `DeleteCustomProperty` | `(PropertyName)` | `System.Void` |  |  |
| `Orion.GroupCustomProperties` | `ModifyCustomProperty` | `(PropertyName, Description, Size, Values, Usages?, Mandatory?, Default?, SourceId?, SourceName?, propertyDisplayName?)` | `System.Void` |  |  |
| `Orion.GroupCustomProperties` | `ValidateCustomProperty` | `(PropertyName, Description, ValueType, Size, Value, Usages?, propertyDisplayName?)` | `SolarWinds.Orion.Core.Common.Models.CustomP…` |  |  |
| `Orion.HA.Pools` | `CreatePool` | `(displayName, poolMembersIds, properties)` | `SolarWinds.Orion.HighAvailability.Common.Mo…` | `admin` | Creates pool based on provided members and resource parameters |
| `Orion.HA.Pools` | `DeletePool` | `(poolId)` | `SolarWinds.Orion.HighAvailability.Common.Mo…` | `admin` | Delete pool with given poolId. |
| `Orion.HA.Pools` | `DeleteStaleEngine` | `(hostName)` | `SolarWinds.Orion.HighAvailability.Common.Mo…` | `admin` | Deletes OrionServer and related pool memeber with a given hostName. |
| `Orion.HA.Pools` | `DisablePool` | `(poolId)` | `SolarWinds.Orion.HighAvailability.Common.Mo…` | `admin` | Disables pool with a given poolId |
| `Orion.HA.Pools` | `EditPool` | `(poolId, displayName, properties)` | `SolarWinds.Orion.HighAvailability.Common.Mo…` | `admin` | Updates pool with a given poolId |
| `Orion.HA.Pools` | `ElbDisable` | `(poolId)` | `SolarWinds.Orion.HighAvailability.Common.Mo…` | `admin` | Disables Load Balancing for pool with a given poolId |
| `Orion.HA.Pools` | `ElbEnable` | `(poolId)` | `SolarWinds.Orion.HighAvailability.Common.Mo…` | `admin` | Enables Load Balancing for pool with a given poolId |
| `Orion.HA.Pools` | `EnablePool` | `(poolId)` | `SolarWinds.Orion.HighAvailability.Common.Mo…` | `admin` | Enables pool with a given poolId |
| `Orion.HA.Pools` | `RepairPool` | `(poolId)` | `SolarWinds.Orion.HighAvailability.Common.Mo…` | `admin` | Repair pool with given poolId. |
| `Orion.HA.Pools` | `SelectiveSwitchover` | `(poolId, poolMemberIdsToFailover, poolMemberIdsToFailoverTo, failoverMessage)` | `SolarWinds.Orion.HighAvailability.Common.Mo…` | `admin` |  |
| `Orion.HA.Pools` | `Switchover` | `(poolId)` | `SolarWinds.Orion.HighAvailability.Common.Mo…` | `admin` | Manual failover on a given pool. |
| `Orion.HA.Pools` | `ValidateCreatePool` | `(displayName, poolMembersIds, properties)` | `SolarWinds.Orion.HighAvailability.Common.Mo…` | `admin` | Validates pool (without creating it) based on provided members and resource parameters |
| `Orion.HA.Pools` | `ValidateEditPool` | `(poolId, displayName, poolMembersIds, properties)` | `SolarWinds.Orion.HighAvailability.Common.Mo…` | `admin` | Validates pool with given poolId and resource parameters (without actual update) |
| `Orion.HardwareHealth.BMC.Controllers` | `TestBmcConnection` | `(nodeIpAddress, portNumber, userName, password, ssl, engineId)` | `SolarWinds.Orion.HardwareHealth.BMC.Common.…` | `manageNodes` | Check if provided credentials are valid for a given HwH BMC controller. |
| `Orion.HardwareHealth.HardwareInfoBase` | `DeleteHardwareHealth` | `(netObject)` | `System.Void` | `manageNodes` | Delete Hardware Health for given entity. |
| `Orion.HardwareHealth.HardwareInfoBase` | `DisableHardwareHealth` | `(netObject)` | `System.Void` | `manageNodes` | Disable Hardware Health for given entity. |
| `Orion.HardwareHealth.HardwareInfoBase` | `EnableHardwareHealth` | `(netObject, pollingmethod)` | `System.Void` | `manageNodes` | Enable Hardware Health for given entity. |
| `Orion.HardwareHealth.HardwareInfoBase` | `IsHardwareHealthEnabled` | `(netObject)` | `boolean` |  | Check if the Hardware Health is enabled for given entity. |
| `Orion.HardwareHealth.HardwareItemBase` | `DisableSensors` | `(hardwareItems)` | `System.Void` | `manageNodes` | Disable sensors for given Hardware Health Items. |
| `Orion.HardwareHealth.HardwareItemBase` | `EnableSensors` | `(hardwareItems)` | `System.Void` | `manageNodes` | Enable sensors for given Hardware Health Items. |
| `Orion.HardwareHealth.HardwareItemThreshold` | `ClearThresholds` | `(sensorIds)` | `System.Void` | `manageNodes` | Clear thresholds for given sensors. |
| `Orion.HardwareHealth.HardwareItemThreshold` | `SetThreshold` | `(sensorId, warningThreshold, criticalThreshold)` | `System.Void` | `manageNodes` | Sets thresholds for given sensors. |
| `Orion.Licensing.Licenses` | `ActivateOffline` | `(LicenseToActivate)` | `array` |  |  |
| `Orion.Licensing.Licenses` | `ActivateOnline` | `(LicenseKey, LicenseVersion, ProductName, FirstName, LastName, Email, Phone)` | `array` |  |  |
| `Orion.Licensing.Licenses` | `AddLicenseFilter` | `(ProductName, LicenseVersion, Tag, LicenseType, ApplicationMode)` | `boolean` |  |  |
| `Orion.Licensing.Licenses` | `Deactivate` | `(LicenseKey, LicenseVersion, ProductName, ProvideReceipt)` | `array` |  |  |
| `Orion.Licensing.Licenses` | `FindValidAssignments` | `(LicenseKey, LicenseVersion, ProductName)` | `System.Data.DataTable` |  |  |
| `Orion.Licensing.Licenses` | `GetAvailableAssignments` | `(LicenseVersion, ProductName)` | `array` |  |  |
| `Orion.Licensing.Licenses` | `GetEvaluationState` | `(ProductName, LicenseVersion)` | `string` |  |  |
| `Orion.Licensing.Licenses` | `ReAssignExactlyTo` | `(LicenseKey, LicenseVersion, ProductName, ServersOrPools)` | `System.Void` |  |  |
| `Orion.Licensing.Licenses` | `RemoveLicenseFilter` | `(ProductName, LicenseVersion)` | `boolean` |  |  |
| `Orion.Licensing.Licenses` | `UnAssignFromAllServers` | `(LicenseKey, LicenseVersion, ProductName)` | `System.Void` |  |  |
| `Orion.Limitations` | `CreateLimitation` | `(limitationTypeID, selection, checkboxItems, pattern, accountID)` | `number` | `admin` | Creates Limitations and optionally assignes them to Accounts. |
| `Orion.Limitations` | `DeleteLimitation` | `(limitationID)` | `System.Void` | `admin` | Deletes Limitation and removes it from an Account it was assigned to previously. |
| `Orion.Limitations` | `UpdateLimitation` | `(limitationID, selection, checkboxItems, pattern)` | `System.Void` | `admin` | Updates Limitation to a new definition i.e. new set of items it shoud match. |
| `Orion.MapStudioFiles` | `DeleteFile` | `(fileId, user, computerName)` | `System.Object` | `manageMaps` |  |
| `Orion.MapStudioFiles` | `GetMapStyle` | `(FileId)` | `System.Object` | `everyone` | Get map style of the map |
| `Orion.MapStudioFiles` | `InsertFile` | `(path, imageFile, owner, fileType, timeStamp)` | `System.Object` | `manageMaps` |  |
| `Orion.MapStudioFiles` | `LockFile` | `(fileId, user, lockDate, computerName, locked)` | `System.Object` | `manageMaps` |  |
| `Orion.MapStudioFiles` | `LockFileTable` | `(fileId, user, lockDate, computerName, locked)` | `System.Data.DataTable` | `manageMaps` |  |
| `Orion.MapStudioFiles` | `UnlockAllFiles` | `(user, computerName)` | `System.Object` | `manageMaps` |  |
| `Orion.MapStudioFiles` | `UpdateFile` | `(fileId, path, imageFile, updater, timeStamp, computerName)` | `System.Object` | `manageMaps` |  |
| `Orion.Maps.GraphMemberDefinitions` | `GetFirstNMembers` | `(definition, topCountForEachDefinition)` | `System.Data.DataTable` |  |  |
| `Orion.Maps.GraphMemberDefinitions` | `GetMembers` | `(definition)` | `System.Data.DataTable` |  |  |
| `Orion.Maps.Graphs` | `CreateContainer` | `(name, owner, frequency, statusCalculator, description, pollingEnabled, memberDefinitions, projectId)` | `number` |  |  |
| `Orion.Maps.Graphs` | `DeleteContainer` | `(containerId)` | `System.Void` |  |  |
| `Orion.Maps.Graphs` | `UpdateContainer` | `(containerId, name, owner, frequency, statusCalculator, description, pollingEnabled, projectId)` | `System.Void` |  |  |
| `Orion.Maps.Projects` | `CloneMapProjects` | `(mapNamePlaceHolder, mapNamePattern, cloneMapOwner, mapProjectIds)` | `System.Void` | `allowOrionMapsManagement` |  |
| `Orion.Maps.Projects` | `RenameMapProject` | `(oldMapProjectName, newMapProjectName)` | `System.Void` | `allowOrionMapsManagement` |  |
| `Orion.Maps.Projects` | `ReplaceResource` | `(oldResourceId, newResourceName, newResourceFile, newResourceTitle, newResourceSubTitle, newResourceProperties)` | `number` | `allowOrionMapsManagement` |  |
| `Orion.Maps.Projects` | `ReplaceResourceAndMapInLimitations` | `(oldResourceId, newResourceId, newMapProjectId)` | `System.Void` | `allowOrionMapsManagement` |  |
| `Orion.Mibs.Management` | `GetDatabaseState` | `()` | `SolarWinds.Orion.Mibs.Management.Common.Mib…` | `admin` |  |
| `Orion.NPM.Interfaces` | `AddInterfacesOnNode` | `(nodeId, interfacesToAdd, pollers)` | `SolarWinds.Interfaces.Common.Models.Discove…` | `manageNodes` | Add provided interface to node. |
| `Orion.NPM.Interfaces` | `CreateInterfacesPluginConfiguration` | `(context)` | `string` | `manageNodes` | Create interface plugin configuration based on provided input data. |
| `Orion.NPM.Interfaces` | `DiscoverInterfacesOnNode` | `(nodeId)` | `SolarWinds.Interfaces.Common.Models.Discove…` | `manageNodes` | Run lite discovery process for search interfaces on node and returns list of interfaces. |
| `Orion.NPM.Interfaces` | `GetSupportedMetrics` | `(netObjectId)` | `array` | `admin`, `allowRealTimePolling` | Returns list of metrics to poll on Interface entity |
| `Orion.NPM.Interfaces` | `Remanage` | `(netObjectId)` | `System.Void` | `allowUnmanage` | Manage interface immediately. |
| `Orion.NPM.Interfaces` | `SetBandwidth` | `(netObjectId, inBandwidth, outBandwidth, customBandwidth)` | `System.Void` | `manageNodes` | Sets the custom bandwidth (InBandwidth and OutBandwidth) for the interface. When customBandwidt… |
| `Orion.NPM.Interfaces` | `SetPowerLevel` | `(interfaceId, powerLevel)` | `System.Void` | `manageNodes` | Set interface power level. |
| `Orion.NPM.Interfaces` | `StartRealTimePolling` | `(netObjectId, owner, properties, pollingExpiration?, pollingFrequency?)` | `boolean` | `admin`, `allowRealTimePolling` | Starts realtime polling on Interface entity |
| `Orion.NPM.Interfaces` | `StopRealTimePolling` | `(netObjectId, owner, properties)` | `boolean` | `admin`, `allowRealTimePolling` | Stops realtime polling on Interface entity |
| `Orion.NPM.Interfaces` | `Unmanage` | `(netObjectId, unmanageTime, remanageTime, isRelative, allowOverlapping?)` | `System.Void` | `allowUnmanage` | Unmanage interface for specified time. |
| `Orion.NPM.InterfacesCustomProperties` | `CreateCustomProperty` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.NPM.InterfacesCustomProperties` | `CreateCustomPropertyWithValues` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Value, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.NPM.InterfacesCustomProperties` | `DeleteCustomProperty` | `(PropertyName)` | `System.Void` |  |  |
| `Orion.NPM.InterfacesCustomProperties` | `ModifyCustomProperty` | `(PropertyName, Description, Size, Values, Usages?, Mandatory?, Default?, SourceId?, SourceName?, propertyDisplayName?)` | `System.Void` |  |  |
| `Orion.Netflow.IPAddressGroupsManagement` | `DeleteAllIpGroups` | `(autoResolveApplicationConflicts)` | `SolarWinds.Netflow.Contracts.IPGroups.Manag…` |  |  |
| `Orion.Netflow.IPAddressGroupsManagement` | `DeleteIpGroups` | `(ipGroupIds, autoResolveApplicationConflicts)` | `SolarWinds.Netflow.Contracts.IPGroups.Manag…` |  |  |
| `Orion.Netflow.IPAddressGroupsManagement` | `SetIPRanges` | `(ipGroupId, ipRanges, autoResolveApplicationConflicts)` | `SolarWinds.Netflow.Contracts.IPGroups.Manag…` |  |  |
| `Orion.Netflow.IPAddressGroupsManagement` | `SetIpGroupsAsModified` | `()` | `System.Void` |  |  |
| `Orion.Netflow.IPGroupExternalRelation` | `CreateFromIPAMGroup` | `(externalIpGroupId)` | `System.Void` |  |  |
| `Orion.Netflow.InterfaceSources` | `DisableFlowInterfaceSources` | `(interfaceIds)` | `array` |  |  |
| `Orion.Netflow.InterfaceSources` | `EnableFlowInterfaceSources` | `(interfaceIds)` | `array` |  |  |
| `Orion.Netflow.InterfaceSources` | `SetExporterFlowDirection` | `(configurations)` | `boolean` |  |  |
| `Orion.Netflow.NodeSources` | `DisableFlowNodeSources` | `(nodeIds)` | `array` |  |  |
| `Orion.Netflow.NodeSources` | `EnableFlowNodeSources` | `(nodeIds)` | `array` |  |  |
| `Orion.Netflow.NodeSources` | `SetAutoDetectedSamplingRate` | `(nodeId)` | `boolean` |  |  |
| `Orion.Netflow.NodeSources` | `SetManualSamplingRate` | `(nodeId, samplingRate)` | `boolean` |  |  |
| `Orion.NetworkAtlas` | `GetNAVersion` | `()` | `string` |  | Returns version of the installed Network Atlas. |
| `Orion.Nodes` | `GetCountOfElementsPerEngineForLicensing` | `()` | `SolarWinds.Orion.Core.Models.Licensing.Coun…` | `manageNodes` | Returns count of used elements (per engine) for licensing |
| `Orion.Nodes` | `GetListResourcesResult` | `(jobId, nodeId)` | `array` | `manageNodes` | Get the result of List Resources discovery |
| `Orion.Nodes` | `GetListResourcesResultByEngine` | `(jobId, engineId)` | `array` | `manageNodes` | Get the result of List Resources discovery |
| `Orion.Nodes` | `GetScheduledListResourcesStatus` | `(jobId, nodeId)` | `string` | `manageNodes` | Get current result of discovery job |
| `Orion.Nodes` | `GetScheduledListResourcesStatusByEngine` | `(jobId, engineId)` | `string` | `manageNodes` | Get current result of discovery job |
| `Orion.Nodes` | `GetSupportedMetrics` | `(netObjectId)` | `array` | `admin`, `allowRealTimePolling` | Returns list of metrics to poll on Node entity |
| `Orion.Nodes` | `ImportListResourcesResult` | `(jobId, nodeId)` | `boolean` | `manageNodes` | Import all results found during discovery |
| `Orion.Nodes` | `ImportSelectedListResourcesResult` | `(jobId, nodeId, resources)` | `array` | `manageNodes` | Import selected result of discovery |
| `Orion.Nodes` | `PollNow` | `(netObjectId)` | `System.Void` | `manageNodes` | It will poll node instance and update its information |
| `Orion.Nodes` | `PollStatusNow` | `(netObjectId)` | `System.Void` | `manageNodes` | It will poll node status and update it |
| `Orion.Nodes` | `RediscoverNow` | `(netObjectId)` | `System.Void` | `manageNodes` | It will rediscover node instance and update its information |
| `Orion.Nodes` | `Remanage` | `(netObjectId)` | `System.Void` | `allowUnmanage` | Enables polling on node if it was unmanaged before |
| `Orion.Nodes` | `ScheduleListResources` | `(nodeId)` | `string` | `manageNodes` | Schedule one time List Resources discovery for given NodeId |
| `Orion.Nodes` | `ScheduleListResourcesForAddress` | `(ipAddress, port, credentialsType, credentialProperties, engineId, preferredSnmpVersion?)` | `string` | `manageNodes` | Schedule one time List Resources discovery for given ip address |
| `Orion.Nodes` | `StartRealTimePolling` | `(netObjectId, owner, properties, pollingExpiration?, pollingFrequency?)` | `boolean` | `admin`, `allowRealTimePolling` | Starts realtime polling on Node entity |
| `Orion.Nodes` | `StopRealTimePolling` | `(netObjectId, owner, properties)` | `boolean` | `admin`, `allowRealTimePolling` | Stops realtime polling on Node entity |
| `Orion.Nodes` | `Unmanage` | `(netObjectId, unmanageTime, remanageTime, isRelative, allowOverlapping?)` | `System.Void` | `allowUnmanage` | Set the given node into maintenance mode so the node polling is disabled |
| `Orion.NodesCustomProperties` | `CreateCustomProperty` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.NodesCustomProperties` | `CreateCustomPropertyWithValues` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Value, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.NodesCustomProperties` | `DeleteCustomProperty` | `(PropertyName)` | `System.Void` |  |  |
| `Orion.NodesCustomProperties` | `ModifyCustomProperty` | `(PropertyName, Description, Size, Values, Usages?, Mandatory?, Default?, SourceId?, SourceName?, propertyDisplayName?)` | `System.Void` |  |  |
| `Orion.NodesCustomProperties` | `ValidateCustomProperty` | `(PropertyName, Description, ValueType, Size, Value, Usages?, propertyDisplayName?)` | `SolarWinds.Orion.Core.Common.Models.CustomP…` |  |  |
| `Orion.NotificationItemGrouped` | `AcknowledgeAll` | `(userName, createdBefore)` | `System.Void` |  | Sets notification item acknowledgement timestamp and user for all items. |
| `Orion.NotificationItemGrouped` | `AcknowledgeById` | `(notificationId, userName, acknowledgeTime)` | `System.Void` |  | Sets notification item acknowledgement timestamp and user for specific item. |
| `Orion.NotificationItemGrouped` | `AcknowledgeByType` | `(typeId, includeIgnored, userName, acknowledgeTime)` | `System.Void` |  | Sets notification item acknowledgement timestamp and user for items of a specific type. |
| `Orion.NotificationItemGrouped` | `UnAcknowledgeById` | `(notificationId)` | `System.Void` |  | Resets notification item acknowledgement for specific item. |
| `Orion.NotificationItemGrouped` | `UnAcknowledgeByType` | `(typeId, includeIgnored)` | `System.Void` |  | Resets notification item acknowledgement for items of a specific type. |
| `Orion.OLM.LogEntry` | `UidExtractDate` | `(uniqueId)` | `string` |  | For internal use only. |
| `Orion.OLM.LogEntry` | `UidMaxForDate` | `(dateTime)` | `number` |  | For internal use only. |
| `Orion.OLM.LogEntry` | `UidMinForDate` | `(dateTime)` | `number` |  | For internal use only. |
| `Orion.OLM.Nodes` | `DisableLogMonitoring` | `(nodeId)` | `System.Void` |  | Disable Log Analyzer monitoring for given node ID |
| `Orion.OLM.Nodes` | `EnableLogMonitoring` | `(nodeId)` | `System.Void` |  | Enable Log Analyzer monitoring for given node ID |
| `Orion.OLM.ProcessingRule` | `DisableRule` | `(ruleId)` | `System.Void` |  | Disable rule |
| `Orion.OLM.ProcessingRule` | `DisableRules` | `(ruleIds)` | `System.Void` |  | Disable rules |
| `Orion.OLM.ProcessingRule` | `EnableRule` | `(ruleId)` | `System.Void` |  | Enable rule |
| `Orion.OLM.ProcessingRule` | `EnableRules` | `(ruleIds)` | `System.Void` |  | Enable rules |
| `Orion.OLM.ProcessingRule` | `ExportRules` | `(identifiers, separator)` | `string` |  | Export rules, either specified by name, rule ID or all if no identification is provided (separa… |
| `Orion.OLM.ProcessingRule` | `ImportRules` | `(rulesJson)` | `SolarWinds.Orion.LogMgmt.RuleProcessing.Mod…` |  | Import rules from provided json. |
| `Orion.Orchestrators.Info` | `AddAristaWMNode` | `(engineId, caption, baseUrl, apiKeyId, apiKeyValue, enableMetricsPolling, locationId, locationName)` | `string` | `manageNodes` | This method adds Arista Wireless Manager node |
| `Orion.Orchestrators.Info` | `AddArubaCentralNode` | `(engineId, caption, accessTokenUrl, clientId, clientSecret, customerId, username, password, groupId, enableMetricsPolling)` | `string` | `manageNodes` |  |
| `Orion.Orchestrators.Info` | `AddArubaNode` | `(engineId, caption, hostname, username?, password?, apiToken?)` | `string` | `manageNodes` |  |
| `Orion.Orchestrators.Info` | `AddExtremeCloudIQNode` | `(engineId, caption, accessTokenUrl, username, password, locationId, enableMetricsPolling)` | `string` | `manageNodes` |  |
| `Orion.Orchestrators.Info` | `AddFortiEdgeCloudNode` | `(engineId, caption, apiId, password, apiUrl, enableMetricsPolling)` | `string` | `manageNodes` |  |
| `Orion.Orchestrators.Info` | `AddFortinetFortiManagerNode` | `(engineId, caption, hostname, organizationId?, organizationName?, tokenUrl?, username?, password?, appId?, apiPassword?, clientId?, token?)` | `string` | `manageNodes` |  |
| `Orion.Orchestrators.Info` | `AddJuniperMistNode` | `(engineId, caption, accessTokenUrl, organizationId, username, password, ApiToken, siteId, siteName, enableMetricsPolling)` | `string` | `manageNodes` |  |
| `Orion.Orchestrators.Info` | `AddMerakiNode` | `(engineId, caption, apiKey, organizationId, enableMetricsPolling)` | `string` | `manageNodes` |  |
| `Orion.Orchestrators.Info` | `AddPrismaNode` | `(engineId, caption, clientId, clientSecret, tsgId)` | `string` | `manageNodes` |  |
| `Orion.Orchestrators.Info` | `AddRuckusOneNode` | `(engineId, caption, region, tenantId, clientId, clientSecret, enableMetricsPolling, venueName, venueId)` | `string` | `manageNodes` | This method adds Ruckus One node |
| `Orion.Orchestrators.Info` | `AddRuckusSmartZoneNode` | `(engineId, caption, baseUrl, userName, password, enableMetricsPolling, zoneName, zoneId, apiVersion)` | `string` | `manageNodes` | This method adds Ruckus SmartZone node |
| `Orion.Orchestrators.Info` | `AddVeloCloudNode` | `(engineId, caption, hostname, username?, password?, apiToken?)` | `string` | `manageNodes` |  |
| `Orion.Orchestrators.Info` | `AddViptelaNode` | `(engineId, caption, hostname, username, password)` | `string` | `manageNodes` |  |
| `Orion.Orchestrators.Info` | `CreateOrchestratorPluginConfiguration` | `(orchestratorId, productTypes?)` | `string` | `manageNodes` |  |
| `Orion.Orchestrators.Info` | `GetAristaWMLocations` | `(engineId, apiKeyId, apiKeyValue, baseUrl)` | `SolarWinds.Orion.Orchestrators.AristaWM.Com…` | `manageNodes` |  |
| `Orion.Orchestrators.Info` | `GetArubaCentralGroups` | `(engineId, customerId, username, password, clientId, clientSecret, accessTokenUrl)` | `SolarWinds.Orion.Orchestrators.ArubaCentral…` | `manageNodes` |  |
| `Orion.Orchestrators.Info` | `GetJuniperMistSites` | `(engineId, endpointUrl, username, password, apiToken, organizationId)` | `SolarWinds.Orion.Orchestrators.JuniperMist.…` | `manageNodes` |  |
| `Orion.Orchestrators.Info` | `GetMerakiOrganizations` | `(engineId, apiKey)` | `SolarWinds.Orion.Orchestrators.Meraki.Commo…` | `manageNodes` |  |
| `Orion.Orchestrators.Info` | `GetRuckusOneVenues` | `(engineId, region, tenantId, clientId, clientSecret)` | `SolarWinds.Orion.Orchestrators.RuckusOne.Co…` | `manageNodes` |  |
| `Orion.Orchestrators.Info` | `GetRuckusSmartZoneZones` | `(engineId, userName, password, baseUrl)` | `SolarWinds.Orion.Orchestrators.RuckusSZ.Com…` | `manageNodes` |  |
| `Orion.Orchestrators.Info` | `ValidateArubaAuthentication` | `(engineId, endpoint, username?, password?, apiToken?)` | `SolarWinds.Orion.Orchestrators.Common.Model…` | `manageNodes` |  |
| `Orion.Orchestrators.Info` | `ValidateExtremeCloudIqCredentials` | `(engineId, endpointUrl, username, password)` | `SolarWinds.Orion.Orchestrators.Common.Model…` | `manageNodes` |  |
| `Orion.Orchestrators.Info` | `ValidateFortiEdgeCloudAuthentication` | `(engineId, username, password)` | `SolarWinds.Orion.Orchestrators.FortiEdgeClo…` | `manageNodes` |  |
| `Orion.Orchestrators.Info` | `ValidateFortinetFortiManagerCloudApiAuthentication` | `(engineId, endpoint, appId, apiPassword, clientId, tokenUrl)` | `SolarWinds.Orion.Orchestrators.Common.Model…` | `manageNodes` |  |
| `Orion.Orchestrators.Info` | `ValidateFortinetFortiManagerTokenAuthentication` | `(engineId, endpoint, token, certificateThumbprint)` | `SolarWinds.Orion.Orchestrators.Common.Model…` | `manageNodes` |  |
| `Orion.Orchestrators.Info` | `ValidateFortinetFortiManagerUsernamePasswordAuthentication` | `(engineId, endpoint, username, password, certificateThumbprint)` | `SolarWinds.Orion.Orchestrators.Common.Model…` | `manageNodes` |  |
| `Orion.Orchestrators.Info` | `ValidatePrismaAuthentication` | `(engineId, clientId, clientSecret, tsgId)` | `SolarWinds.Orion.Orchestrators.Common.Model…` | `manageNodes` |  |
| `Orion.Orchestrators.Info` | `ValidateVeloCloudAuthentication` | `(engineId, endpoint, username?, password?, apiToken?)` | `SolarWinds.Orion.Orchestrators.Common.Model…` | `manageNodes` |  |
| `Orion.Orchestrators.Info` | `ValidateViptelaAuthentication` | `(engineId, endpoint, username, password, certificateThumbprint)` | `SolarWinds.Orion.Orchestrators.Common.Model…` | `manageNodes` |  |
| `Orion.PM.DatabaseHelper` | `GetAccountsList` | `(serverName, username, password, authenticationType)` | `array` |  |  |
| `Orion.PM.DatabaseHelper` | `GetListOfDatabases` | `(serverName, username, password, authenticationType)` | `array` |  |  |
| `Orion.PM.DatabaseHelper` | `GetLoginNameFromCurrentSqlSession` | `(serverName, account, password, authenticationType)` | `string` |  |  |
| `Orion.PM.DatabaseHelper` | `TestUserAndPassword` | `(serverName, account, password, authenticationType, encryptConnection)` | `string` |  |  |
| `Orion.PM.DatabaseHelper` | `UpdateUserAccount` | `(serverName, database, user, userPassword, authenticationType, encryptConnection, account, accountPassword, accountType)` | `string` | `admin` |  |
| `Orion.PM.DatabaseHelper` | `Validate` | `(serverName, databasename, account, password, authenticationType, encryptConnection)` | `string` |  |  |
| `Orion.PM.Management` | `DeleteDataGridDbSettings` | `()` | `boolean` |  |  |
| `Orion.PM.Management` | `DeleteWebApiSettings` | `()` | `boolean` |  |  |
| `Orion.PM.Management` | `GetCurrentDataGridDbSettings` | `()` | `string` |  |  |
| `Orion.PM.Management` | `GetSpmWebApiCredentials` | `()` | `SolarWinds.PM.Common.Model.SharedNetworkCre…` |  |  |
| `Orion.PM.Management` | `GetSpmWebApiHostSettings` | `()` | `SolarWinds.PM.Common.Model.SpmWebApiHostSet…` |  |  |
| `Orion.PM.Management` | `IsDataGridCredentialAvailable` | `()` | `boolean` |  |  |
| `Orion.PM.Management` | `PasswordCanBeDecrypted` | `()` | `boolean` |  |  |
| `Orion.PM.Management` | `SetCurrentDataGridDbSettings` | `(encryptedConnectionString)` | `boolean` | `admin` |  |
| `Orion.PM.Management` | `SetSpmWebApiCredentials` | `(server, port, useHttps, userFullname, encryptedPassword)` | `boolean` | `admin` |  |
| `Orion.PM.Management` | `TestSpmWebApiCredentials` | `(server, port, useHttps, userFullname, encryptedPassword)` | `boolean` | `admin` |  |
| `Orion.PM.TaskBroker` | `CheckEWDataGridAvailability` | `(performKeepAlive)` | `SolarWinds.PM.Common.Model.EWDataGridEntity` |  |  |
| `Orion.PM.TaskBroker` | `CheckTaskState` | `(taskInfo)` | `SolarWinds.PM.Common.Model.TaskResult` |  |  |
| `Orion.PM.TaskBroker` | `ExecuteWsusServerClearTask` | `(taskInfo)` | `SolarWinds.PM.Common.Model.TaskResult` |  |  |
| `Orion.PM.TaskBroker` | `ExecuteWsusServerParallelTasks` | `(taskInfos)` | `SolarWinds.PM.Common.Model.TaskResult` |  |  |
| `Orion.PM.TaskBroker` | `ExecuteWsusServerTask` | `(taskInfo)` | `SolarWinds.PM.Common.Model.TaskResult` |  |  |
| `Orion.PolicyEngine.Policy` | `AssignToEntity` | `(policyId, entityUri, data)` | `System.Void` |  | Assign a policy to an entity. |
| `Orion.PolicyEngine.Policy` | `ExportPolicy` | `(policyId)` | `string` |  | Export a policy with rules into YAML format. |
| `Orion.PolicyEngine.Policy` | `ImportPolicy` | `(yaml)` | `number` |  | Import a policy from YAML format to database. |
| `Orion.PolicyEngine.Policy` | `PollNowAndEvaluate` | `(policyId, entityUri)` | `System.Void` |  | Execute data source collection and evaluation of all rules in a policy. |
| `Orion.PolicyEngine.Policy` | `UnassignFromEntity` | `(policyId, entityUri)` | `System.Void` |  | Unassign a policy from an entity. |
| `Orion.Report` | `CreateReport` | `(name, description, limitationCategory, category, title, subtitle, definition, isFavorite, userName)` | `number` |  |  |
| `Orion.Report` | `DeleteReport` | `(reportID)` | `System.Void` |  |  |
| `Orion.Report` | `DuplicateReport` | `(reportID, accountID)` | `number` |  |  |
| `Orion.Report` | `UpdateReport` | `(reportId, name, description, limitationCategory, category, title, subtitle, definition, isFavorite, userName)` | `System.Void` |  |  |
| `Orion.ReportFavorites` | `AddReportFavoriteMark` | `(reportID, accountID)` | `System.Void` |  |  |
| `Orion.ReportFavorites` | `DeleteReportFavoriteMark` | `(reportID, accountID)` | `System.Void` |  |  |
| `Orion.Reporting` | `ExecuteSQL` | `(sqlQueryText, sqlQueryParameters?, outputRowsMaxCount?, schemaOnly?)` | `System.Data.DataTable` | `admin` |  |
| `Orion.ReportsCustomProperties` | `CreateCustomProperty` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.ReportsCustomProperties` | `CreateCustomPropertyWithValues` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Value, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.ReportsCustomProperties` | `DeleteCustomProperty` | `(PropertyName)` | `System.Void` |  |  |
| `Orion.ReportsCustomProperties` | `ModifyCustomProperty` | `(PropertyName, Description, Size, Values, Usages?, Mandatory?, Default?, SourceId?, SourceName?, propertyDisplayName?)` | `System.Void` |  |  |
| `Orion.ReportsCustomProperties` | `ValidateCustomProperty` | `(PropertyName, Description, ValueType, Size, Value, Usages?, propertyDisplayName?)` | `SolarWinds.Orion.Core.Common.Models.CustomP…` |  |  |
| `Orion.Resources` | `CheckResourceMigration` | `()` | `boolean` | `admin` | This verb checks, whether it is possible to migrate classic resources (charts) to its modern ve… |
| `Orion.Resources` | `GetModernResourceName` | `(classicChartName)` | `string` |  | Returns new apollo chart name for given classic chart name |
| `Orion.Resources` | `MigrateClassicToModernResources` | `()` | `boolean` | `admin` | This verb migrates classic resources (charts) to its modern version. |
| `Orion.Resources` | `MigrateModernToClassicResources` | `()` | `boolean` | `admin` | This verb reverts migration back to classic resources (charts). |
| `Orion.SCM.Baseline` | `SetBaseline` | `(nodeId, timestamp)` | `number` |  | Create or update baseline and snapshot all related data so that they are not touched by mainten… |
| `Orion.SCM.Profiles` | `AssignToNode` | `(profileId, nodeId, data)` | `System.Void` |  | Assigns profile to node. |
| `Orion.SCM.Profiles` | `ExportProfile` | `(profileId)` | `string` |  | Exports profile to JSON |
| `Orion.SCM.Profiles` | `ImportPolicyProfile` | `(policyId, profileJson)` | `number` |  | Imports policy profile from YAML |
| `Orion.SCM.Profiles` | `ImportProfile` | `(profileJson)` | `number` |  | Imports profile from JSON |
| `Orion.SCM.Profiles` | `UnassignFromNode` | `(profileId, nodeId, keepHistory)` | `System.Void` |  | Unassigns profile from node. |
| `Orion.SCM.ServerConfiguration` | `DisableFimDriverWatching` | `(nodeId)` | `System.Void` |  | On target node disable polling through FIM driver. |
| `Orion.SCM.ServerConfiguration` | `EnableFimDriverWatching` | `(nodeId)` | `System.Void` |  | On target node enable polling through FIM driver if it was previously disabled by DisableFimDri… |
| `Orion.SCM.ServerConfiguration` | `PollNow` | `(nodeIds)` | `System.Void` |  | On target nodes triggers refreshing of watchers, polls the current results of file, registry an… |
| `Orion.SCM.ServerConfiguration` | `PollNowWithNotification` | `(nodeId, elementIds, timeout, state)` | `System.Void` |  | Executes PollNow and triggers Orion.SCM.OneTimePollFinished indication once all results are col… |
| `Orion.SEM.Events` | `GetEventDetails` | `(connectionId, eventId)` | `array` |  |  |
| `Orion.SEM.Settings` | `AddConnection` | `(host, displayName, username, encryptedPassword)` | `number` |  |  |
| `Orion.SEM.Settings` | `AddTrackedTags` | `(tags)` | `boolean` |  |  |
| `Orion.SEM.Settings` | `DeleteConnectionById` | `(id)` | `boolean` |  |  |
| `Orion.SEM.Settings` | `DeleteTrackedTags` | `(tags)` | `boolean` |  |  |
| `Orion.SEM.Settings` | `EditConnection` | `(id, host, displayName, username, encryptedPassword)` | `boolean` |  |  |
| `Orion.SEM.Settings` | `Ping` | `(host)` | `SolarWinds.Sem.Common.Models.TestResult` |  |  |
| `Orion.SEM.Settings` | `TestCredential` | `(host, username, encryptedPassword)` | `SolarWinds.Sem.Common.Models.TestResult` |  |  |
| `Orion.SEM.Settings` | `UpdateConnectionData` | `(id)` | `boolean` |  |  |
| `Orion.SEUM.RecordingCustomProperties` | `CreateCustomProperty` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.SEUM.RecordingCustomProperties` | `CreateCustomPropertyWithValues` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Value, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.SEUM.RecordingCustomProperties` | `DeleteCustomProperty` | `(PropertyName)` | `System.Void` |  |  |
| `Orion.SEUM.RecordingCustomProperties` | `ModifyCustomProperty` | `(PropertyName, Description, Size, Values, Usages?, Mandatory?, Default?, SourceId?, SourceName?, propertyDisplayName?)` | `System.Void` |  |  |
| `Orion.SEUM.Recordings` | `Exists` | `(recordingGuid)` | `boolean` |  | Verb to check if recording exists. |
| `Orion.SEUM.Recordings` | `Export` | `(recordingId, password)` | `SolarWinds.SEUM.Common.Models.RecordingFile…` |  | Verb to export recording to file. |
| `Orion.SEUM.Recordings` | `Import` | `(recordingFileContent, recordingName, password)` | `number` |  | Verb to import recording from file. |
| `Orion.SEUM.Recordings` | `Update` | `(recordingId, recordingFileContent, recordingName, password)` | `number` |  | Verb to update existing recording with recording from file. |
| `Orion.SEUM.RecordingsSettings` | `CheckRecorderCompatibility` | `(recorderVersion)` | `SolarWinds.SEUM.Verbs.v3.VersionCompatibili…` |  | Checks version compatibility |
| `Orion.SEUM.TransactionCustomProperties` | `CreateCustomProperty` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.SEUM.TransactionCustomProperties` | `CreateCustomPropertyWithValues` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Value, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.SEUM.TransactionCustomProperties` | `DeleteCustomProperty` | `(PropertyName)` | `System.Void` |  |  |
| `Orion.SEUM.TransactionCustomProperties` | `ModifyCustomProperty` | `(PropertyName, Description, Size, Values, Usages?, Mandatory?, Default?, SourceId?, SourceName?, propertyDisplayName?)` | `System.Void` |  |  |
| `Orion.SEUM.Transactions` | `Create` | `(recordingId, agentId)` | `number` |  | Verb to create transaction |
| `Orion.SEUM.Transactions` | `Remanage` | `(netObjectId)` | `System.Void` |  | Verb to remanage transaction |
| `Orion.SEUM.Transactions` | `Unmanage` | `(netObjectId, unmanageTime, remanageTime, isRelative)` | `System.Void` |  | Verb to unmanage transaction |
| `Orion.SRM.BusinessLayer` | `AddCredential` | `(credential, credType)` | `number` |  | Adds a new credential for storage array authentication |
| `Orion.SRM.BusinessLayer` | `AddManualE2EMapping` | `(volumeId, netObjectId, netObjectType)` | `number` |  | Adds manual end-to-end mapping between storage and virtualization layers |
| `Orion.SRM.BusinessLayer` | `AddProvider` | `(provider)` | `number` |  | Adds a new storage provider |
| `Orion.SRM.BusinessLayer` | `CheckIfCredentialNameExists` | `(displayName)` | `boolean` |  | Checks if a credential name already exists |
| `Orion.SRM.BusinessLayer` | `DeleteArrays` | `(ids)` | `System.Void` |  | Deletes one or more storage arrays |
| `Orion.SRM.BusinessLayer` | `DeleteCredentials` | `(ids)` | `System.Void` |  | Deletes one or more credentials |
| `Orion.SRM.BusinessLayer` | `DeleteProviders` | `(providerIds)` | `System.Void` |  | Deletes one or more storage providers |
| `Orion.SRM.BusinessLayer` | `DiscoveryImport` | `(engineId, providers, arrays)` | `System.Void` |  | Imports discovered storage arrays into SRM |
| `Orion.SRM.BusinessLayer` | `DiscoveryResponder` | `(ipAddress, port, userName, password, templateId)` | `array` |  | Handles discovery response operations |
| `Orion.SRM.BusinessLayer` | `DropManualE2EMapping` | `(volumeIds)` | `System.Void` |  | Removes manual end-to-end mapping |
| `Orion.SRM.BusinessLayer` | `GetAllArrays` | `()` | `System.Collections.Generic.IEnumerable~Sola…` |  | Gets information about all storage arrays |
| `Orion.SRM.BusinessLayer` | `GetAllEngines` | `()` | `System.Collections.Generic.IEnumerable~Sola…` |  | Gets information about all polling engines |
| `Orion.SRM.BusinessLayer` | `GetArray` | `(storageArrayID)` | `SolarWinds.SRM.Common.Models.ArrayEntity` |  | Gets information about a specific storage array |
| `Orion.SRM.BusinessLayer` | `GetArrayProvider` | `(arrayId)` | `SolarWinds.SRM.Common.Models.ProviderInfo` |  | Gets the provider information for a storage array |
| `Orion.SRM.BusinessLayer` | `GetArraysByVendorId` | `(storageArrayIds)` | `System.Collections.Generic.IEnumerable~Sola…` |  | Gets all arrays from a specific vendor |
| `Orion.SRM.BusinessLayer` | `GetCredential` | `(credentialID, credType)` | `SolarWinds.Orion.Core.SharedCredentials.Cre…` |  | Retrieves credential information by ID |
| `Orion.SRM.BusinessLayer` | `GetCredentialNames` | `(credType)` | `array` |  | Gets the names of all available credentials |
| `Orion.SRM.BusinessLayer` | `GetCredentialType` | `(id)` | `SolarWinds.SRM.Common.Enums.CredentialType` |  | Gets the type of a specific credential |
| `Orion.SRM.BusinessLayer` | `GetDeviceGroup` | `(groupId)` | `SolarWinds.SRM.Common.Models.DeviceGroup` |  | Gets information about a specific device group |
| `Orion.SRM.BusinessLayer` | `GetDiscoveryJobResult` | `(discoveryId)` | `SolarWinds.SRM.Common.Models.DiscoveryResul…` |  | Retrieves the result of a discovery job |
| `Orion.SRM.BusinessLayer` | `GetEngine` | `(engineId)` | `SolarWinds.SRM.Common.Models.PollingEngine` |  | Gets information about a specific polling engine |
| `Orion.SRM.BusinessLayer` | `GetLicenseInfo` | `()` | `SolarWinds.SRM.Common.Models.LicenseEntity` |  | Gets current license information for SRM |
| `Orion.SRM.BusinessLayer` | `GetLicensedObjects` | `()` | `array` |  | Gets the list of licensed objects in SRM |
| `Orion.SRM.BusinessLayer` | `GetNetObjectCaption` | `(tableName, idFieldName, id)` | `string` |  | Gets the caption of a network object |
| `Orion.SRM.BusinessLayer` | `GetPrimaryEngineID` | `()` | `number` |  | Gets the ID of the primary polling engine |
| `Orion.SRM.BusinessLayer` | `GetPropertyAvailability` | `(templateString, templateProperties, categories)` | `array` |  | Gets availability information for object properties |
| `Orion.SRM.BusinessLayer` | `GetProviderArrays` | `(providerId)` | `System.Collections.Generic.IEnumerable~Sola…` |  | Gets all arrays associated with a specific provider |
| `Orion.SRM.BusinessLayer` | `GetProviders` | `(providerIds)` | `array` |  | Gets all configured storage providers |
| `Orion.SRM.BusinessLayer` | `GetRestConfiguration` | `(groupId)` | `string` |  | Gets REST configuration for API communication |
| `Orion.SRM.BusinessLayer` | `GetSetting` | `(field)` | `string` |  | Gets a specific SRM setting value |
| `Orion.SRM.BusinessLayer` | `GetStorageArrayProperty` | `(storageArrayId, propertyName)` | `string` |  | Gets a specific property of a storage array |
| `Orion.SRM.BusinessLayer` | `GetTestConnectionJobResult` | `(testConnectionJobId)` | `SolarWinds.SRM.Common.Models.TestConnection…` |  | Retrieves the result of a test connection job |
| `Orion.SRM.BusinessLayer` | `GetVserver` | `(vserverId)` | `SolarWinds.SRM.Common.Models.VServerEntity` |  | Gets information about a specific virtual server |
| `Orion.SRM.BusinessLayer` | `ImportArrays` | `(engineId, deviceGroupId, providers, arrays)` | `System.Void` |  | Imports specified storage arrays into monitoring |
| `Orion.SRM.BusinessLayer` | `LogOIP` | `(message)` | `System.Void` |  | Logs OIP (Orion Improvement Program) data |
| `Orion.SRM.BusinessLayer` | `RefreshLicense` | `()` | `System.Void` |  | Refreshes license information from the license server |
| `Orion.SRM.BusinessLayer` | `RemanageArrays` | `(ids)` | `System.Void` |  | Sets storage arrays back to managed state |
| `Orion.SRM.BusinessLayer` | `ReportJobDuration` | `(duration)` | `System.Void` |  | Reports the duration of completed jobs |
| `Orion.SRM.BusinessLayer` | `StoreResponderArray` | `(ipAddress, port, snapshotId, storageArrayId, arrayName, vendor, isCluster, templateId, userName, password)` | `System.Void` |  | Stores array information from discovery responder |
| `Orion.SRM.BusinessLayer` | `SubmitDiscoveryJob` | `(connectionInfos, groupId)` | `string` |  | Submits a discovery job for storage array discovery |
| `Orion.SRM.BusinessLayer` | `SubmitTestConnectionJob` | `(connectionInfos)` | `string` |  | Submits a test connection job to verify connectivity to storage provider |
| `Orion.SRM.BusinessLayer` | `TestCredentials` | `(connectionInfo)` | `SolarWinds.SRM.Common.Exceptions.ErrorState` |  | Tests connectivity using specified credentials |
| `Orion.SRM.BusinessLayer` | `UnmanageArrays` | `(ids, from, until)` | `System.Void` |  | Sets storage arrays to unmanaged state |
| `Orion.SRM.BusinessLayer` | `UpdateArray` | `(array)` | `number` |  | Updates storage array information |
| `Orion.SRM.BusinessLayer` | `UpdateArrayPollingIntervals` | `(storageArrayId, statCollection, rediscoveryInterval, topologyInterval, controllerInterval)` | `number` |  | Updates polling intervals for storage arrays |
| `Orion.SRM.BusinessLayer` | `UpdateCredential` | `(credential, credType)` | `System.Void` |  | Updates an existing credential |
| `Orion.SRM.BusinessLayer` | `UpdateEntityCustomProperties` | `(entityUris, customProperties)` | `System.Void` |  | Updates custom properties for SRM entities |
| `Orion.SRM.BusinessLayer` | `UpdateLicenseInfo` | `()` | `System.Void` |  | Updates license information in the system |
| `Orion.SRM.BusinessLayer` | `UpdateNetObjectCaption` | `(tableName, idFieldName, id, caption)` | `number` |  | Updates the caption of a network object |
| `Orion.SRM.BusinessLayer` | `UpdatePollingEngine` | `(objectsTableName, keyColumnName, ids, engineId)` | `number` |  | Updates polling engine configuration |
| `Orion.SRM.BusinessLayer` | `UpdateProvider` | `(provider)` | `System.Void` |  | Updates provider information |
| `Orion.SRM.BusinessLayer` | `UpdateProviderArrays` | `(arrayIds, providerId)` | `System.Void` |  | Updates arrays associated with a provider |
| `Orion.SRM.BusinessLayer` | `UpdateProviderPollingProperties` | `(providerIDs, pollingInterval)` | `System.Void` |  | Updates polling properties for a provider |
| `Orion.SRM.BusinessLayer` | `UpdateStorageArrayProperties` | `(storageArrayId, properties)` | `System.Void` |  | Updates multiple properties of a storage array |
| `Orion.SRM.BusinessLayer` | `UpdateStorageArrayProperty` | `(storageArrayId, propertyName, value)` | `System.Void` |  | Updates a specific property of a storage array |
| `Orion.SRM.BusinessLayer` | `UpdateStorageControllerPollingFeature` | `(storageArrayId, isPollingEnabled)` | `number` |  | Updates polling feature configuration for storage controllers |
| `Orion.SRM.DeviceMigrations` | `RefreshDeviceMigrations` | `()` | `System.Void` |  | Will trigger a refresh SRM Device migrations table with updated info |
| `Orion.SRM.DeviceMigrations` | `TriggerMigration` | `(migrationType, migrationObject, objectID)` | `SolarWinds.SRM.Common.BL.MigrationResults.M…` |  | Will trigger a migration for a particular storage array to new monitoring |
| `Orion.SRM.FileShareCustomProperties` | `CreateCustomProperty` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.SRM.FileShareCustomProperties` | `CreateCustomPropertyWithValues` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Value, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.SRM.FileShareCustomProperties` | `DeleteCustomProperty` | `(PropertyName)` | `System.Void` |  |  |
| `Orion.SRM.FileShareCustomProperties` | `ModifyCustomProperty` | `(PropertyName, Description, Size, Values, Usages?, Mandatory?, Default?, SourceId?, SourceName?, propertyDisplayName?)` | `System.Void` |  |  |
| `Orion.SRM.FileShareCustomProperties` | `ValidateCustomProperty` | `(PropertyName, Description, ValueType, Size, Value, Usages?, propertyDisplayName?)` | `SolarWinds.Orion.Core.Common.Models.CustomP…` |  |  |
| `Orion.SRM.LUNCustomProperties` | `CreateCustomProperty` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.SRM.LUNCustomProperties` | `CreateCustomPropertyWithValues` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Value, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.SRM.LUNCustomProperties` | `DeleteCustomProperty` | `(PropertyName)` | `System.Void` |  |  |
| `Orion.SRM.LUNCustomProperties` | `ModifyCustomProperty` | `(PropertyName, Description, Size, Values, Usages?, Mandatory?, Default?, SourceId?, SourceName?, propertyDisplayName?)` | `System.Void` |  |  |
| `Orion.SRM.LUNCustomProperties` | `ValidateCustomProperty` | `(PropertyName, Description, ValueType, Size, Value, Usages?, propertyDisplayName?)` | `SolarWinds.Orion.Core.Common.Models.CustomP…` |  |  |
| `Orion.SRM.PhysicalDisks` | `GetCountOfElementsPerEngineForLicensing` | `()` | `SolarWinds.Orion.Core.Models.Licensing.Coun…` |  |  |
| `Orion.SRM.PoolCustomProperties` | `CreateCustomProperty` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.SRM.PoolCustomProperties` | `CreateCustomPropertyWithValues` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Value, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.SRM.PoolCustomProperties` | `DeleteCustomProperty` | `(PropertyName)` | `System.Void` |  |  |
| `Orion.SRM.PoolCustomProperties` | `ModifyCustomProperty` | `(PropertyName, Description, Size, Values, Usages?, Mandatory?, Default?, SourceId?, SourceName?, propertyDisplayName?)` | `System.Void` |  |  |
| `Orion.SRM.PoolCustomProperties` | `ValidateCustomProperty` | `(PropertyName, Description, ValueType, Size, Value, Usages?, propertyDisplayName?)` | `SolarWinds.Orion.Core.Common.Models.CustomP…` |  |  |
| `Orion.SRM.ProviderCustomProperties` | `CreateCustomProperty` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.SRM.ProviderCustomProperties` | `CreateCustomPropertyWithValues` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Value, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.SRM.ProviderCustomProperties` | `DeleteCustomProperty` | `(PropertyName)` | `System.Void` |  |  |
| `Orion.SRM.ProviderCustomProperties` | `ModifyCustomProperty` | `(PropertyName, Description, Size, Values, Usages?, Mandatory?, Default?, SourceId?, SourceName?, propertyDisplayName?)` | `System.Void` |  |  |
| `Orion.SRM.ProviderCustomProperties` | `ValidateCustomProperty` | `(PropertyName, Description, ValueType, Size, Value, Usages?, propertyDisplayName?)` | `SolarWinds.Orion.Core.Common.Models.CustomP…` |  |  |
| `Orion.SRM.StorageArrayCustomProperties` | `CreateCustomProperty` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.SRM.StorageArrayCustomProperties` | `CreateCustomPropertyWithValues` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Value, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.SRM.StorageArrayCustomProperties` | `DeleteCustomProperty` | `(PropertyName)` | `System.Void` |  |  |
| `Orion.SRM.StorageArrayCustomProperties` | `ModifyCustomProperty` | `(PropertyName, Description, Size, Values, Usages?, Mandatory?, Default?, SourceId?, SourceName?, propertyDisplayName?)` | `System.Void` |  |  |
| `Orion.SRM.StorageArrayCustomProperties` | `ValidateCustomProperty` | `(PropertyName, Description, ValueType, Size, Value, Usages?, propertyDisplayName?)` | `SolarWinds.Orion.Core.Common.Models.CustomP…` |  |  |
| `Orion.SRM.StorageArrays` | `AddAllArrays` | `(deviceGroupId, providersIds, engineIp?)` | `boolean` |  | Adds all arrays within given provider. Returns true if success |
| `Orion.SRM.StorageArrays` | `AddExternalProvider` | `(ipAddress, credentialsId)` | `number` |  | Adds external provider. Receives credential ID, returns provider ID. |
| `Orion.SRM.StorageArrays` | `AddSmisCredentials` | `(displayName, userName, password, interopNamespace, arrayNamespace, httpPort?, httpsPort?, useSsl?)` | `number` |  | Adds smis credentials. Returns credentials ID |
| `Orion.SRM.StorageArrays` | `GetLicensedArrays` | `()` | `array` |  | Will return list of Storage Array IDs which are licensed. |
| `Orion.SRM.StorageControllerCustomProperties` | `CreateCustomProperty` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.SRM.StorageControllerCustomProperties` | `CreateCustomPropertyWithValues` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Value, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.SRM.StorageControllerCustomProperties` | `DeleteCustomProperty` | `(PropertyName)` | `System.Void` |  |  |
| `Orion.SRM.StorageControllerCustomProperties` | `ModifyCustomProperty` | `(PropertyName, Description, Size, Values, Usages?, Mandatory?, Default?, SourceId?, SourceName?, propertyDisplayName?)` | `System.Void` |  |  |
| `Orion.SRM.StorageControllerCustomProperties` | `ValidateCustomProperty` | `(PropertyName, Description, ValueType, Size, Value, Usages?, propertyDisplayName?)` | `SolarWinds.Orion.Core.Common.Models.CustomP…` |  |  |
| `Orion.SRM.StorageControllerPortCustomProperties` | `CreateCustomProperty` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.SRM.StorageControllerPortCustomProperties` | `CreateCustomPropertyWithValues` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Value, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.SRM.StorageControllerPortCustomProperties` | `DeleteCustomProperty` | `(PropertyName)` | `System.Void` |  |  |
| `Orion.SRM.StorageControllerPortCustomProperties` | `ModifyCustomProperty` | `(PropertyName, Description, Size, Values, Usages?, Mandatory?, Default?, SourceId?, SourceName?, propertyDisplayName?)` | `System.Void` |  |  |
| `Orion.SRM.StorageControllerPortCustomProperties` | `ValidateCustomProperty` | `(PropertyName, Description, ValueType, Size, Value, Usages?, propertyDisplayName?)` | `SolarWinds.Orion.Core.Common.Models.CustomP…` |  |  |
| `Orion.SRM.VServersCustomProperties` | `CreateCustomProperty` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.SRM.VServersCustomProperties` | `CreateCustomPropertyWithValues` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Value, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.SRM.VServersCustomProperties` | `DeleteCustomProperty` | `(PropertyName)` | `System.Void` |  |  |
| `Orion.SRM.VServersCustomProperties` | `ModifyCustomProperty` | `(PropertyName, Description, Size, Values, Usages?, Mandatory?, Default?, SourceId?, SourceName?, propertyDisplayName?)` | `System.Void` |  |  |
| `Orion.SRM.VServersCustomProperties` | `ValidateCustomProperty` | `(PropertyName, Description, ValueType, Size, Value, Usages?, propertyDisplayName?)` | `SolarWinds.Orion.Core.Common.Models.CustomP…` |  |  |
| `Orion.SRM.VolumeCustomProperties` | `CreateCustomProperty` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.SRM.VolumeCustomProperties` | `CreateCustomPropertyWithValues` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Value, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.SRM.VolumeCustomProperties` | `DeleteCustomProperty` | `(PropertyName)` | `System.Void` |  |  |
| `Orion.SRM.VolumeCustomProperties` | `ModifyCustomProperty` | `(PropertyName, Description, Size, Values, Usages?, Mandatory?, Default?, SourceId?, SourceName?, propertyDisplayName?)` | `System.Void` |  |  |
| `Orion.SRM.VolumeCustomProperties` | `ValidateCustomProperty` | `(PropertyName, Description, ValueType, Size, Value, Usages?, propertyDisplayName?)` | `SolarWinds.Orion.Core.Common.Models.CustomP…` |  |  |
| `Orion.SSO` | `ValidateUserToken` | `(token, expiration)` | `array` |  |  |
| `Orion.SecObs.Users` | `CheckPermission` | `(scope)` | `boolean` |  |  |
| `Orion.SecObs.Vulnerabilities.NodeCve` | `SetStates` | `(nodeVulnerabilities, state, comment)` | `string` |  |  |
| `Orion.SecObs.Vulnerabilities.Nodes` | `Add` | `(nodes)` | `string` | `manageNodes` |  |
| `Orion.SecObs.Vulnerabilities.Nodes` | `Remove` | `(nodes)` | `string` | `manageNodes` |  |
| `Orion.SecObs.Vulnerabilities.Settings` | `DeleteAll` | `()` | `SolarWinds.SecObs.Common.Models.Vulnerabili…` |  |  |
| `Orion.SecObs.Vulnerabilities.Settings` | `DeleteMatchBySelection` | `(include, exclude, isAllPages)` | `SolarWinds.SecObs.Common.Models.Vulnerabili…` |  |  |
| `Orion.SecObs.Vulnerabilities.Settings` | `GetImportSettings` | `()` | `SolarWinds.SecObs.Common.Models.Vulnerabili…` |  |  |
| `Orion.SecObs.Vulnerabilities.Settings` | `GetLastImport` | `()` | `SolarWinds.SecObs.Common.Models.Vulnerabili…` |  |  |
| `Orion.SecObs.Vulnerabilities.Settings` | `GetMatchSettings` | `()` | `SolarWinds.SecObs.Common.Models.Vulnerabili…` |  |  |
| `Orion.SecObs.Vulnerabilities.Settings` | `GetVulnerabilitiesDatabaseInfo` | `()` | `SolarWinds.SecObs.Common.Models.Vulnerabili…` |  |  |
| `Orion.SecObs.Vulnerabilities.Settings` | `RunImportNow` | `()` | `SolarWinds.SecObs.Common.Models.Vulnerabili…` |  |  |
| `Orion.SecObs.Vulnerabilities.Settings` | `RunMatchNow` | `()` | `SolarWinds.SecObs.Common.Models.Vulnerabili…` |  |  |
| `Orion.SecObs.Vulnerabilities.Settings` | `SetImportSettings` | `(enableScheduler, schedulerDailyTimeOffset, cpeMatchFeedFile, epssFile, sourcesJsonStr)` | `SolarWinds.SecObs.Common.Models.Vulnerabili…` |  |  |
| `Orion.SecObs.Vulnerabilities.Settings` | `SetMatchSettings` | `(enableScheduler, schedulerDailyTimeOffset, useEpssData, enableHistoryRetentionPeriod, historyRetentionPeriod)` | `SolarWinds.SecObs.Common.Models.Vulnerabili…` |  |  |
| `Orion.SecObs.Vulnerabilities.Settings` | `StopImport` | `()` | `SolarWinds.SecObs.Common.Models.Vulnerabili…` |  |  |
| `Orion.SecObs.Vulnerabilities.Settings` | `StopMatching` | `()` | `SolarWinds.SecObs.Common.Models.Vulnerabili…` |  |  |
| `Orion.SecObs.Vulnerabilities.Settings` | `ValidateSources` | `(model)` | `SolarWinds.SecObs.Common.Models.Vulnerabili…` |  |  |
| `Orion.Sites` | `ApplyServerIDToQuerySelectStatement` | `(swqlQuery, serverIDAlias)` | `string` |  | Extends a specified query with a Site info the data originates from. |
| `Orion.Stacks.Relation` | `ProcessUi` | `(config, includeTracing?)` | `SolarWinds.AppStack.Contract.Models.UiRespo…` |  |  |
| `Orion.Stacks.Relation` | `Traverse` | `(keys, includeRelations?)` | `SolarWinds.AppStack.Contract.Models.Relianc…` |  |  |
| `Orion.SwisFeature` | `HttpsCertificateThumbprint` | `()` | `string` | `admin` | Get thumbprint of Swis RestApi certificate. |
| `Orion.TechnologyPollingAssignments` | `DisableAssignments` | `(technologyPollingID)` | `array` | `admin` |  |
| `Orion.TechnologyPollingAssignments` | `DisableAssignmentsOnNetObjects` | `(technologyPollingID, netObjectIDs)` | `array` | `admin` |  |
| `Orion.TechnologyPollingAssignments` | `EnableAssignments` | `(technologyPollingID)` | `array` | `admin` |  |
| `Orion.TechnologyPollingAssignments` | `EnableAssignmentsOnNetObjects` | `(technologyPollingID, netObjectIDs)` | `array` | `admin` |  |
| `Orion.UDT.NodeCapabilityDashboard` | `PollNow` | `(nodeIdJobType)` | `System.Void` | `manageNodes` |  |
| `Orion.UDT.Port` | `AdministrativeEnable` | `()` | `unknown` | `manageNodes` |  |
| `Orion.UDT.Port` | `AdministrativeShutdown` | `()` | `unknown` | `manageNodes` |  |
| `Orion.VIM.ClustersCustomProperties` | `CreateCustomProperty` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.VIM.ClustersCustomProperties` | `CreateCustomPropertyWithValues` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Value, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.VIM.ClustersCustomProperties` | `DeleteCustomProperty` | `(PropertyName)` | `System.Void` |  |  |
| `Orion.VIM.ClustersCustomProperties` | `ModifyCustomProperty` | `(PropertyName, Description, Size, Values, Usages?, Mandatory?, Default?, SourceId?, SourceName?, propertyDisplayName?)` | `System.Void` |  |  |
| `Orion.VIM.DataCentersCustomProperties` | `CreateCustomProperty` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.VIM.DataCentersCustomProperties` | `CreateCustomPropertyWithValues` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Value, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.VIM.DataCentersCustomProperties` | `DeleteCustomProperty` | `(PropertyName)` | `System.Void` |  |  |
| `Orion.VIM.DataCentersCustomProperties` | `ModifyCustomProperty` | `(PropertyName, Description, Size, Values, Usages?, Mandatory?, Default?, SourceId?, SourceName?, propertyDisplayName?)` | `System.Void` |  |  |
| `Orion.VIM.DatastoresCustomProperties` | `CreateCustomProperty` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.VIM.DatastoresCustomProperties` | `CreateCustomPropertyWithValues` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Value, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.VIM.DatastoresCustomProperties` | `DeleteCustomProperty` | `(PropertyName)` | `System.Void` |  |  |
| `Orion.VIM.DatastoresCustomProperties` | `ModifyCustomProperty` | `(PropertyName, Description, Size, Values, Usages?, Mandatory?, Default?, SourceId?, SourceName?, propertyDisplayName?)` | `System.Void` |  |  |
| `Orion.VIM.Discovery` | `AddNode` | `(entityType, credentialsId, discoveryJobId, ipAddress, hostName?, engineId?, caption?, timeoutInSeconds?)` | `SolarWinds.Data.Providers.VIM.v3.Models.Add…` |  | Creates a node based on discovery job. |
| `Orion.VIM.Discovery` | `CreateDiscoveryJob` | `(entityType, credentialsId, ipAddress, hostName?, engineId?)` | `string` |  | Creates a task to discover a virtualization entity and returns its Id. |
| `Orion.VIM.Discovery` | `CreateVimPluginConfiguration` | `(context)` | `string` |  | Create VIM Plugin Configuration |
| `Orion.VIM.Discovery` | `GetDiscoveryJobResult` | `(discoveryJobId, engineId?, timeoutInSeconds?)` | `SolarWinds.AddNode.Contract.Models.Discover…` |  | Checks whether the discovery task has completed and returns the node type. |
| `Orion.VIM.Discovery` | `ValidateCredentials` | `(hypervisorId, ipAddress, credentialProperties, engineId?)` | `SolarWinds.Data.Providers.VIM.v3.Models.Ver…` |  | Validate credentials for VMware, Hyper-V and Nutanix hypervisors. Returns the entity type and r… |
| `Orion.VIM.Discovery` | `ValidateExistingCredentials` | `(hypervisorId, ipAddress, credentialsId, engineId?)` | `SolarWinds.Data.Providers.VIM.v3.Models.Ver…` |  | Validate the existing credentials for VMware, Hyper-V and Nutanix hypervisors. Returns the enti… |
| `Orion.VIM.HostsCustomProperties` | `CreateCustomProperty` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.VIM.HostsCustomProperties` | `CreateCustomPropertyWithValues` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Value, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.VIM.HostsCustomProperties` | `DeleteCustomProperty` | `(PropertyName)` | `System.Void` |  |  |
| `Orion.VIM.HostsCustomProperties` | `ModifyCustomProperty` | `(PropertyName, Description, Size, Values, Usages?, Mandatory?, Default?, SourceId?, SourceName?, propertyDisplayName?)` | `System.Void` |  |  |
| `Orion.VIM.Tags` | `SynchronizeToCustomProperties` | `()` | `System.Void` |  | Synchronize tags to custom properties |
| `Orion.VIM.VirtualMachines` | `ChangeSettings` | `(virtualMachineId, processorCount, ramInMB, restartRequired?)` | `string` |  | Change VM Settings, including number of processors and RAM size(MB). The verb restarts the VM i… |
| `Orion.VIM.VirtualMachines` | `DeleteSnapshot` | `(virtualMachineId, snapshotId, deleteAllChildren?)` | `string` |  | Delete the snapshot of the given VM. |
| `Orion.VIM.VirtualMachines` | `GetManagementActionBatchResult` | `(batchGuid)` | `string` |  |  |
| `Orion.VIM.VirtualMachines` | `Migrate` | `(virtualMachineId, destinationHostId, restartRequired?, storageDestination?)` | `string` |  | Migrate VM to a different host. storageDestination is optional. A flag 'restartRequired` can al… |
| `Orion.VIM.VirtualMachines` | `PerformBasicAction` | `(virtualMachineId, actionType)` | `string` |  | Perform Basic VM management actions such as PowerOff, PowerOn, Pause, Resume, Suspend, Reboot,… |
| `Orion.VIM.VirtualMachines` | `Relocate` | `(virtualMachineId, destinationDataStoreId)` | `string` |  | Relocate the VM to a different DataStore. |
| `Orion.VIM.VirtualMachines` | `TakeSnapshot` | `(virtualMachineId, snapshotName)` | `string` |  | Take snapshot of the given VM. snapshotName is optional |
| `Orion.VIM.VirtualMachinesCustomProperties` | `CreateCustomProperty` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.VIM.VirtualMachinesCustomProperties` | `CreateCustomPropertyWithValues` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Value, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.VIM.VirtualMachinesCustomProperties` | `DeleteCustomProperty` | `(PropertyName)` | `System.Void` |  |  |
| `Orion.VIM.VirtualMachinesCustomProperties` | `ModifyCustomProperty` | `(PropertyName, Description, Size, Values, Usages?, Mandatory?, Default?, SourceId?, SourceName?, propertyDisplayName?)` | `System.Void` |  |  |
| `Orion.VPN.L2LTunnel` | `RemoveFavorite` | `(entityId)` | `SolarWinds.Orion.NetMan.Firewalls.Common.Mo…` | `manageNodes` |  |
| `Orion.VPN.L2LTunnel` | `SetFavorite` | `(entityId)` | `SolarWinds.Orion.NetMan.Firewalls.Common.Mo…` | `manageNodes` |  |
| `Orion.Views` | `AddResourceToView` | `(viewId, config, moveColliding?)` | `boolean` |  | Adds a resource to existing view by using resource configuration xml fragment |
| `Orion.Views` | `AddViewToGroup` | `(viewID, targetViewID, viewIcon, viewCondition?)` | `System.Void` |  | Adds an existing view as a subview to another view and enables subviews on target if needed |
| `Orion.Views` | `CloneView` | `(sourceViewID, title)` | `number` |  | Creates a clone of an existing view |
| `Orion.Views` | `CloneViewContents` | `(sourceViewID, destinationViewID)` | `System.Void` |  | Creates a copy of all resources including properties of source view to a destination view |
| `Orion.Volumes` | `GetSupportedMetrics` | `(netObjectId)` | `array` | `admin`, `allowRealTimePolling` | Returns list of metrics to poll on Volume entity |
| `Orion.Volumes` | `Remanage` | `(netObjectId)` | `System.Void` | `allowUnmanage` | Remanages specified volume |
| `Orion.Volumes` | `StartRealTimePolling` | `(netObjectId, owner, properties, pollingExpiration?, pollingFrequency?)` | `boolean` | `admin`, `allowRealTimePolling` | Starts realtime polling on Volume entity |
| `Orion.Volumes` | `StopRealTimePolling` | `(netObjectId, owner, properties)` | `boolean` | `admin`, `allowRealTimePolling` | Stops realtime polling on Volume entity |
| `Orion.Volumes` | `Unmanage` | `(netObjectId, unmanageTime, remanageTime, isRelative, allowOverlapping?)` | `System.Void` | `allowUnmanage` | Unmanages specified volume in the specified time range |
| `Orion.VolumesCustomProperties` | `CreateCustomProperty` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.VolumesCustomProperties` | `CreateCustomPropertyWithValues` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Value, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `Orion.VolumesCustomProperties` | `DeleteCustomProperty` | `(PropertyName)` | `System.Void` |  |  |
| `Orion.VolumesCustomProperties` | `ModifyCustomProperty` | `(PropertyName, Description, Size, Values, Usages?, Mandatory?, Default?, SourceId?, SourceName?, propertyDisplayName?)` | `System.Void` |  |  |
| `Orion.VolumesCustomProperties` | `ValidateCustomProperty` | `(PropertyName, Description, ValueType, Size, Value, Usages?, propertyDisplayName?)` | `SolarWinds.Orion.Core.Common.Models.CustomP…` |  |  |
| `Orion.Web.Menu` | `ClearCache` | `()` | `System.Void` | `admin` | Clears menu item cache. |
| `Orion.WirelessHeatMap.Map` | `CloneWirelessHeatMapFromNAMap` | `(naMapId, projectId, name, scale, scaleUnit, lastGenerationStarted, lastGenerationFinished, width, height, points)` | `number` |  |  |
| `Orion.WirelessHeatMap.Map` | `DeleteMap` | `(mapStudioFileGuid)` | `System.Void` |  |  |
| `Orion.WirelessHeatMap.Map` | `DeleteReferencePoints` | `(mapPointIds)` | `boolean` |  |  |
| `Orion.WirelessHeatMap.Map` | `DeleteWirelessHeatMap` | `(mapId)` | `System.Void` |  |  |
| `Orion.WirelessHeatMap.Map` | `FireMapGenerationIndication` | `(mapId)` | `System.Void` |  |  |
| `Orion.WirelessHeatMap.Map` | `GetProgress` | `(keysByEngines)` | `System.Data.DataTable` |  |  |
| `Orion.WirelessHeatMap.Map` | `InsertMap` | `(name, scale, scaleUnit, width, height, mapStudioFileGuid)` | `number` |  |  |
| `Orion.WirelessHeatMap.Map` | `InsertWirelessHeatMap` | `(projectId, name, scale, scaleUnit, width, height)` | `number` |  |  |
| `Orion.WirelessHeatMap.Map` | `PollAPSignalStrengthNow` | `(heatmapId)` | `System.Data.DataTable` |  |  |
| `Orion.WirelessHeatMap.Map` | `PollRPSignalStrengthNow` | `(heatmapId, clientIdVsMapPointIdMap)` | `System.Data.DataTable` |  |  |
| `Orion.WirelessHeatMap.Map` | `SetMapError` | `(mapId, started, errorCode)` | `System.Void` |  |  |
| `Orion.WirelessHeatMap.Map` | `StartClientSignalPoll` | `(heatmapId, clientIdVsMapPointIdMap)` | `array` |  |  |
| `Orion.WirelessHeatMap.Map` | `UpdateMapGenerationProgress` | `(mapId, progress, errorCode)` | `System.Void` |  |  |
| `Orion.WirelessHeatMap.Map` | `UpdateWirelessHeatMap` | `(mapId, projectId, name, scale, scaleUnit, width, height)` | `number` |  |  |
| `Orion.WirelessHeatMap.MapPoint` | `DeleteMapPoint` | `(mapId, entityType, instanceId)` | `System.Void` |  |  |
| `Orion.WirelessHeatMap.MapPoint` | `DeleteMapPoints` | `(wlhmId)` | `System.Void` |  |  |
| `Orion.WirelessHeatMap.MapPoint` | `InsertMapPoint` | `(mapId, entityType, instanceId, x, y)` | `number` |  |  |
| `Orion.WirelessHeatMap.MapPoint` | `SyncMapPoints` | `(mapId, naMapPoints, isAP)` | `System.Void` |  |  |
| `Orion.WirelessHeatMap.ResourceLimitation` | `InsertResourceLimitation` | `(resourceId, mapGuid, mapLimitationCount, apMACAddress, apLimitationCount, clientMACAddress, mapId?)` | `System.Void` | `allowCustomize` |  |

## Cirrus

| Entity | Verb | Signature | Returns | Requires | Description |
| --- | --- | --- | --- | --- | --- |
| `Cirrus.ApproveQueue` | `AddRequest` | `(ticket)` | `string` |  | Adds a new request. For valid Orion user with at least WebUploader NCM role. |
| `Cirrus.ApproveQueue` | `ApproveRequest` | `(ticket)` | `System.Void` |  | Approved the request.             If the request status is waiting for execution then for valid… |
| `Cirrus.ApproveQueue` | `DeclineRequest` | `(ticket)` | `System.Void` |  | Declines the request. For valid Orion user with at least Engineer NCM role. |
| `Cirrus.ApproveQueue` | `DeleteRequest` | `(ticketId)` | `System.Void` |  | Deletes the request. For valid Orion user with at least WebUploader NCM role. |
| `Cirrus.ApproveQueue` | `GetApprovalMode` | `()` | `SolarWinds.NCM.Contracts.InformationService…` |  | Gets the NCM approvals mode. For valid Orion user with at least WebViewer NCM role. |
| `Cirrus.ApproveQueue` | `GetApprovalUsers` | `()` | `array` |  | Gets users who should review operations. For valid Orion user with at least Engineer NCM role. |
| `Cirrus.ApproveQueue` | `GetRequest` | `(requestId)` | `SolarWinds.NCM.Contracts.InformationService…` |  | Gets the request data. For valid Orion user with at least WebViewer NCM role. |
| `Cirrus.ApproveQueue` | `GetTicketStatus` | `(ticketId)` | `SolarWinds.NCM.Contracts.InformationService…` |  | Gets the ticket status. For valid Orion user with at least WebUploader NCM role. |
| `Cirrus.ApproveQueue` | `GetUserApproveRole` | `(userId)` | `SolarWinds.NCM.Contracts.InformationService…` |  | Gets the approval role for the user. For valid Orion user with at least WebViewer NCM role. |
| `Cirrus.ApproveQueue` | `SetApprovalMode` | `(mode)` | `System.Void` |  | Updates NCM approval mode. For valid Orion user with at least Engineer NCM role. |
| `Cirrus.ApproveQueue` | `UpdateApprovalUsers` | `(users)` | `System.Void` |  | Updates users who should review operations. For valid Orion user with at least Engineer NCM rol… |
| `Cirrus.ApproveQueue` | `UpdateRequest` | `(ticket)` | `System.Void` |  | Updates the request. For valid Orion user with at least WebUploader NCM role. |
| `Cirrus.ConfigArchive` | `CancelTransfers` | `(TransferTickets)` | `System.Void` |  | Cancels transfers specified in parameter.             Valid for Orion manage node users with at… |
| `Cirrus.ConfigArchive` | `CloneConfig` | `(parentConfigID, title, comments, configText)` | `System.Void` |  | Clones the config.             Valid for Orion manage node users with at least WebUploader NCM… |
| `Cirrus.ConfigArchive` | `CompareConfigs` | `(configId1, configId2, settings)` | `SolarWinds.Orion.DiffEngine.Contract.Models…` |  | Compares the configs..             Valid for Orion manage node users with at least WebDownloade… |
| `Cirrus.ConfigArchive` | `ConfigSearch` | `(searchString, configType, coreNodeIdList, matchWholeWord, searchOnlyMostRecent?, startTime?, endTime?)` | `array` |  | Searches for the config (Verb ConfigSearch will be removed. Please use the ConfigSearch2 verb i… |
| `Cirrus.ConfigArchive` | `ConfigSearch2` | `(searchTerm)` | `array` |  | Searches for the config.             Valid for Orion manage node users with at least WebViewer… |
| `Cirrus.ConfigArchive` | `DeleteConfigs` | `(ConfigIds, UserName)` | `System.Void` |  | Removes the config.             Valid for Orion manage node users with at least WebUploader NCM… |
| `Cirrus.ConfigArchive` | `Diff` | `(configId1, configId2)` | `System.Data.DataTable` |  | Runs the comparer.             Valid for Orion manage node users with at least WebViewer NCM ro… |
| `Cirrus.ConfigArchive` | `DownloadConfig` | `(nodeId, configType)` | `array` |  | Downloads config file for the particular node.             Valid for Orion manage node users wi… |
| `Cirrus.ConfigArchive` | `DownloadConfigOnNodes` | `(nodes, deviceTemplateXML, configType)` | `array` |  | Downloads config file for the particular nodes.             Valid for Orion manage node users w… |
| `Cirrus.ConfigArchive` | `ExecuteScript` | `(nodeId, script, Reboot?)` | `array` |  | Executes script on the particular node.             Valid for Orion manage node users with at l… |
| `Cirrus.ConfigArchive` | `ExecuteScriptOnNodes` | `(nodes, deviceTemplateXML, script)` | `array` |  | Executes script on the particular nodes.             Valid for Orion manage node users with at… |
| `Cirrus.ConfigArchive` | `ExecuteScriptPerNode` | `(nodesScript, reboot?)` | `array` |  | Executes scripts per nodes.             Valid for Orion manage node users with at least WebUplo… |
| `Cirrus.ConfigArchive` | `GetConfigTypes` | `()` | `string` |  | Gets all available config types.             Valid for Orion manage node users with at least We… |
| `Cirrus.ConfigArchive` | `GetInterfaceConfigSnippets` | `(coreNodeId)` | `array` |  | Gets interface config snippets.             Valid for Orion manage node users with at least Web… |
| `Cirrus.ConfigArchive` | `GetPermissionsByRole` | `(role)` | `array` |  | Gets all permissions for specified role.             Valid for Orion manage node users with at… |
| `Cirrus.ConfigArchive` | `ImportBinaryConfig` | `(nodeId, title, comments, binaryConfig)` | `System.Void` |  | Imports binary config.             Valid for Orion manage node users with at least WebUploader… |
| `Cirrus.ConfigArchive` | `ImportConfig` | `(nodeId, title, comments, configText)` | `System.Void` |  | Imports binary config.             Valid for Orion manage node users with at least WebUploader… |
| `Cirrus.ConfigArchive` | `ReExecute` | `(tickets)` | `array` |  | Re-executes script             Valid for Orion manage node users with at least WebDownloader NC… |
| `Cirrus.ConfigArchive` | `RunIndexOptimization` | `()` | `System.Void` | `system` | Runs index optimization.             Valid for Orion manage node users with at least WebViewer… |
| `Cirrus.ConfigArchive` | `SetClearBaseline` | `(ConfigIds)` | `System.Void` |  | Sets clear baseline.             Valid for Orion manage node users with at least WebUploader NC… |
| `Cirrus.ConfigArchive` | `UpdateConfig` | `(configID, title, comments, configText, updateConfigText, UserName)` | `System.Void` |  | Updates config.             Valid for Orion manage node users with at least WebUploader NCM rol… |
| `Cirrus.ConfigArchive` | `UploadConfig` | `(nodeId, configType, ConfigText, RebootDevice)` | `array` |  | Uploads config.             Valid for Orion manage node users with at least WebUploader NCM rol… |
| `Cirrus.ConfigArchive` | `UploadConfigPerNode` | `(nodesScript, configType, reboot?)` | `array` |  | Uploads config.             Valid for Orion manage node users with at least WebUploader NCM rol… |
| `Cirrus.ConfigArchive` | `ValidateBinaryConfigStorage` | `(path, networkShareUserName, networkSharePassword)` | `SolarWinds.NCM.Contracts.InformationService…` |  | Validates binary config storage.             Valid for Orion manage node users with at least Ad… |
| `Cirrus.ConfigSnippets` | `AddSnippet` | `(snippet)` | `number` |  | Adds snippet.             Valid for Orion manage node users with at least WebUploader NCM role. |
| `Cirrus.ConfigSnippets` | `AddTags` | `(snippetIds, tags)` | `number` |  | Adds tags.             Valid for Orion manage node users with at least WebUploader NCM role. |
| `Cirrus.ConfigSnippets` | `CopySnippets` | `(snippetIds)` | `System.Void` |  | Copies list of snippets.             Valid for Orion manage node users with at least WebUploade… |
| `Cirrus.ConfigSnippets` | `DeleteSnippets` | `(snippetIds)` | `number` |  | Removes specified snippets.             Valid for Orion manage node users with at least WebUplo… |
| `Cirrus.ConfigSnippets` | `DeleteTags` | `(snippetIds, tags)` | `number` |  | Removes specified tags.             Valid for Orion manage node users with at least WebUploader… |
| `Cirrus.ConfigSnippets` | `GetSnippet` | `(snippetId)` | `SolarWinds.NCM.Contracts.InformationService…` |  | Gets snippet.             Valid for Orion manage node users with at least WebUploader NCM role. |
| `Cirrus.ConfigSnippets` | `GetTagsList` | `()` | `array` |  | Gets tag list.             Valid for Orion manage node users with at least WebUploader NCM role. |
| `Cirrus.ConfigSnippets` | `GetTagsListForSnippets` | `(snippetIds)` | `array` |  | Gets tag list for snippet.             Valid for Orion manage node users with at least WebUploa… |
| `Cirrus.ConfigSnippets` | `ImportSnippets` | `(snippets)` | `System.Void` |  | Imports snippets.             Valid for Orion manage node users with at least WebUploader NCM r… |
| `Cirrus.ConfigSnippets` | `SaveSnippetAsCopy` | `(snippet)` | `number` |  | Saves snippet as copy.             Valid for Orion manage node users with at least WebUploader… |
| `Cirrus.ConfigSnippets` | `UpdateSnippet` | `(snippet)` | `number` |  | Updates snippet.             Valid for Orion manage node users with at least WebUploader NCM ro… |
| `Cirrus.NCM_NCMJobs` | `AddJob` | `(job)` | `number` |  | Adds the job definition.             Valid for Orion users with at least WebUploader NCM role.… |
| `Cirrus.NCM_NCMJobs` | `ClearJobLog` | `(jobId)` | `boolean` |  | Clears job logs.             Valid for Orion users with at least WebUploader NCM role.… |
| `Cirrus.NCM_NCMJobs` | `DeleteJobs` | `(jobIds)` | `SolarWinds.NCM.Contracts.Jobs.DeleteNcmJobs…` |  | Deletes job definitions.             Valid for Orion users with at least WebUploader NCM role.… |
| `Cirrus.NCM_NCMJobs` | `EnableOrDisableJobs` | `(jobIds, enableOrDisable)` | `System.Void` |  | Enables or disables job definitions.             Valid for Orion users with at least WebUploade… |
| `Cirrus.NCM_NCMJobs` | `GetJob` | `(jobId)` | `SolarWinds.NCM.Contracts.InformationService…` |  | Get job definition data.             Valid for Orion users with at least WebUploader NCM role.… |
| `Cirrus.NCM_NCMJobs` | `GetJobLog` | `(jobId, checkSize)` | `string` |  | Gets job logs.             Valid for Orion users with at least WebUploader NCM role.… |
| `Cirrus.NCM_NCMJobs` | `GetJobStatus` | `(jobId)` | `SolarWinds.NCM.Contracts.InformationService…` |  | Gets the current job status.             Valid for Orion users with at least WebUploader NCM ro… |
| `Cirrus.NCM_NCMJobs` | `UpdateJob` | `(job)` | `System.Void` |  | Updates the job definition.             Valid for Orion users with at least WebUploader NCM rol… |
| `Cirrus.NCM_NCMJobs` | `ValidateJobsAccess` | `()` | `SolarWinds.NCM.Contracts.InformationService…` |  | Tests access for the invoker. |
| `Cirrus.Nodes` | `AddConnectionProfile` | `(profile)` | `number` | `manageNodes` | Creates a new connection profile.             User needs Orion node management rights with NCM… |
| `Cirrus.Nodes` | `AddNode` | `(node)` | `string` | `manageNodes` | Adds a node to NCM given a complete model. Not recommended - use AddNodeToNCM instead.… |
| `Cirrus.Nodes` | `AddNodeToNCM` | `(coreNodeId)` | `string` | `manageNodes` | Enables NCM to monitor and manage the configuration of an Orion node, assuming appropriate cred… |
| `Cirrus.Nodes` | `AddNodes` | `(coreNodeIds)` | `boolean` | `manageNodes` | A batch version of the Cirrus.Nodes.AddNodeToNCM verb. Enables NCM to monitor and manage the co… |
| `Cirrus.Nodes` | `AssignEOSEntry` | `(nodeIds, endOfSupport, endOfSales, endOfSoftware, entryId, type, version, link, comments, replacementPartNumber)` | `System.Void` |  | Assigns EOS data to provided nodes.             For valid Orion user with at least Engineer NCM… |
| `Cirrus.Nodes` | `ChangeEOSType` | `(nodeIds, type)` | `System.Void` |  | Changes EOS type for provided nodes.             Valid for Orion manage node users with at leas… |
| `Cirrus.Nodes` | `ChangeVulnerabilityStateForAllNodes` | `(entryId, state, comment)` | `System.Void` |  | Changes vulnerability states for all assigned nodes.             Valid for Orion manage node us… |
| `Cirrus.Nodes` | `ChangeVulnerabilityStateForNodes` | `(nodeIds, entryId, state, comment)` | `System.Void` |  | Changes vulnerability states for provided nodes.             Valid for Orion manage node users… |
| `Cirrus.Nodes` | `CheckAPLicence` | `()` | `boolean` |  | Tests the current poller licence.             For valid Orion user with at least WebViewer NCM… |
| `Cirrus.Nodes` | `DeleteAllVulnerabilityData` | `()` | `System.Void` |  | Deletes all vulnerabilities data.             Valid for Orion manage node users with at least E… |
| `Cirrus.Nodes` | `DeleteConnectionProfile` | `(id)` | `System.Void` | `manageNodes` | Deletes existing connection profile.             User needs Orion node management rights with N… |
| `Cirrus.Nodes` | `DeleteEOSData` | `(nodeIds)` | `System.Void` |  | Deletes EOS data from NCM nodes.             Valid for Orion manage node users with at least En… |
| `Cirrus.Nodes` | `DeleteOverLicenseNodes` | `()` | `System.Void` |  | Deletes random nodes which are above the current licence.             For valid Orion user with… |
| `Cirrus.Nodes` | `ExecuteConfigChangeReportAction` | `(nodeId, comparisonType)` | `string` |  | Executes and makes config change report.             Valid for Orion manage node users with at… |
| `Cirrus.Nodes` | `GetAllConnectionProfiles` | `()` | `array` |  | Retrieve list of all connection profiles created in NCM.             User needs Orion node mana… |
| `Cirrus.Nodes` | `GetConnectionProfile` | `(id)` | `SolarWinds.NCM.Contracts.InformationService…` |  | Retrieve single connection profile.             User needs Orion node management rights with NC… |
| `Cirrus.Nodes` | `GetNode` | `(nodeId)` | `SolarWinds.NCM.Contracts.InformationService…` |  | Fetches an NCMNode model object for the given node.             Valid for Orion manage node use… |
| `Cirrus.Nodes` | `GetPageableEosDataTable` | `(nodeIds, startRowNumber, pageSize)` | `System.Data.DataTable` |  | Gets paged EOS data.             Valid for Orion manage node users with at least Engineer NCM r… |
| `Cirrus.Nodes` | `GetPageableEosRowCount` | `(nodeIds)` | `number` |  | Gets number of EOS rows count.             Valid for Orion manage node users with at least Engi… |
| `Cirrus.Nodes` | `ParseMacros` | `(nodeId, macro)` | `string` |  | Processes the provided macro.             Valid for Orion manage node users with at least WebVi… |
| `Cirrus.Nodes` | `RemoveNode` | `(nodeId)` | `boolean` | `manageNodes` | Removes a node from NCM. Does not remove it from Orion, just NCM.             Valid for Orion m… |
| `Cirrus.Nodes` | `RemoveNodes` | `(ncmNodeIds)` | `boolean` | `manageNodes` | Removes a set of nodes from NCM. Does not remove them from Orion, just NCM. Batch version of th… |
| `Cirrus.Nodes` | `UpdateConnectionProfile` | `(profile)` | `System.Void` | `manageNodes` | Updates exisitng connection profile.             User needs Orion node management rights with N… |
| `Cirrus.Nodes` | `UpdateNode` | `(node)` | `boolean` | `manageNodes` | Updates the NCM properties of a node. All properties of the node are overwritten. It does not m… |
| `Cirrus.Nodes` | `ValidateLogin` | `(engineId, node, ipAddress, deviceTemplate)` | `SolarWinds.NCM.Contracts.InformationService…` | `manageNodes` | Tests login credentials.             Valid for Orion manage node users with at least WebViewer… |
| `Cirrus.PolicyReports` | `AddPolicy` | `(policy, importFlag)` | `string` |  | Adds the compliance policy.             If compliance only for administrators option enabled th… |
| `Cirrus.PolicyReports` | `AddPolicyReport` | `(report, importFlag)` | `string` |  | Adds the policy report definition.             If compliance only for administrators option ena… |
| `Cirrus.PolicyReports` | `AddPolicyRule` | `(rule)` | `string` |  | Adds the compliance policy rule.             If compliance only for administrators option enabl… |
| `Cirrus.PolicyReports` | `DeletePolicies` | `(policyIds, deleteChildren)` | `number` |  | Deletes compliance policies.             If compliance only for administrators option enabled t… |
| `Cirrus.PolicyReports` | `DeletePolicyReports` | `(policyReportIds, deleteChildren)` | `number` |  | Deletes policy report definitions.             If compliance only for administrators option ena… |
| `Cirrus.PolicyReports` | `DeletePolicyRules` | `(ruleIds)` | `number` |  | Deletes compliance policy rules.             If compliance only for administrators option enabl… |
| `Cirrus.PolicyReports` | `GenerateRemediationScriptForNodes` | `(nodeIds, reportId, policyId, ruleId, script)` | `array` |  | Generates remediation scripts.             If compliance only for administrators option enabled… |
| `Cirrus.PolicyReports` | `GetComplianceColumnsInJSON` | `(reportId)` | `string` |  | Gets data about compliance reports.             If compliance only for administrators option en… |
| `Cirrus.PolicyReports` | `GetComplianceDataTable` | `(reportId, includePolicies)` | `System.Data.DataTable` |  | Gets data about compliance reports.             If compliance only for administrators option en… |
| `Cirrus.PolicyReports` | `GetPagablePoliciesList` | `(pageSize, startRowNumber, sortColumn, sortDirection, groupByColumn, groupByValue, searchValue)` | `System.Data.DataTable` |  | Gets paged data about compliance policies.             If compliance only for administrators op… |
| `Cirrus.PolicyReports` | `GetPagablePolicyRulesList` | `(pageSize, startRowNumber, sortColumn, sortDirection, groupByColumn, groupByValue, searchValue)` | `System.Data.DataTable` |  | Gets paged data about compliance rules.             If compliance only for administrators optio… |
| `Cirrus.PolicyReports` | `GetPoliciesRowCount` | `(groupByColumn, groupByValue, searchValue)` | `number` |  | Counts all compliance policies based on provided criteria.             If compliance only for a… |
| `Cirrus.PolicyReports` | `GetPoliciesRowNumber` | `(policyId, orderByColumn, orderByDirection)` | `number` |  | Gets index of the compliance policy row based on provided criteria.             Valid for Orion… |
| `Cirrus.PolicyReports` | `GetPolicy` | `(policyId, exportFlag)` | `SolarWinds.NCM.Contracts.Compliance.Policy` |  | Gets a compliance policy data.             If compliance only for administrators option enabled… |
| `Cirrus.PolicyReports` | `GetPolicyReport` | `(reportId, exportFlag)` | `SolarWinds.NCM.Contracts.Compliance.PolicyR…` |  | Gets a policy report definition data.             If compliance only for administrators option… |
| `Cirrus.PolicyReports` | `GetPolicyReportsRowNumber` | `(reportId, orderByColumn, orderByDirection)` | `number` |  | Gets index of the compliance policy report row based on provided criteria.             Valid fo… |
| `Cirrus.PolicyReports` | `GetPolicyRule` | `(ruleId)` | `SolarWinds.NCM.Contracts.Compliance.PolicyR…` |  | Gets a compliance policy rule data.             If compliance only for administrators option en… |
| `Cirrus.PolicyReports` | `GetPolicyRulesRowCount` | `(groupByColumn, groupByValue, searchValue)` | `number` |  | Counts all compliance rules based on provided criteria.             If compliance only for admi… |
| `Cirrus.PolicyReports` | `GetPolicyRulesRowNumber` | `(ruleId, orderByColumn, orderByDirection)` | `number` |  | Gets index of the compliance policy rule row based on provided criteria.             Valid for… |
| `Cirrus.PolicyReports` | `StartCaching` | `(selectedReportsIds?)` | `boolean` |  | Start processing and caching policy reports.             If compliance only for administrators… |
| `Cirrus.PolicyReports` | `TestRule` | `(policyRule, config)` | `string` |  | Evaluates the provided rule on the provided configuration.             If compliance only for a… |
| `Cirrus.PolicyReports` | `TestRuleOnBackedUpConfig` | `(policyRule, configId)` | `string` |  | Evaluates the provided rule on the provided configuration.             If the 'compliance only… |
| `Cirrus.PolicyReports` | `UpdatePolicy` | `(policy)` | `number` |  | Updates the compliance policy.             If compliance only for administrators option enabled… |
| `Cirrus.PolicyReports` | `UpdatePolicyReport` | `(report)` | `number` |  | Updates the policy report definition.             If compliance only for administrators option… |
| `Cirrus.PolicyReports` | `UpdatePolicyRule` | `(rule)` | `number` |  | Updates the compliance policy rule.             If compliance only for administrators option en… |
| `Cirrus.PolicyReports` | `UpdateReportStatus` | `(status, selectedReportsIds)` | `System.Void` |  | Sets status for provided report.             If compliance only for administrators option enabl… |
| `Cirrus.RTN` | `ExecuteRtn` | `(ipAddress, commandLine)` | `System.Void` | `system` | Starts executing RTN. |
| `Cirrus.RTN` | `RunRtn` | `(args)` | `System.Void` | `system` | Starts executing RTN. |
| `Cirrus.Settings` | `CryptPasswords` | `()` | `System.Void` | `admin` | Crypts password.             For valid Orion user with at least Administrator NCM role. |
| `Cirrus.Settings` | `CryptUsernames` | `()` | `System.Void` | `admin` | Crypts usernames.             For valid Orion user with at least Administrator NCM role. |
| `Cirrus.Settings` | `DecryptData` | `(data)` | `string` |  | Decrypts the data.             For valid Orion user with at least Administrator NCM role. |
| `Cirrus.Settings` | `DeleteCustomMacros` | `(name)` | `System.Void` |  | Removes custom macros.             For valid Orion user with at least Administrator NCM role. |
| `Cirrus.Settings` | `DeleteRegExPatterns` | `(regExIDs)` | `System.Void` |  | Removes RegEx patterns.             For valid Orion user with at least Administrator NCM role. |
| `Cirrus.Settings` | `EnableOrDisableRegExPatterns` | `(regExIDs, enableOrDisable)` | `System.Void` |  | Enables or disables RegEx patterns.             For valid Orion user with at least Administrato… |
| `Cirrus.Settings` | `GetAppDataPath` | `()` | `string` | `system` | Gets app data path.             For valid Orion user with at least WebViewer NCM role. |
| `Cirrus.Settings` | `GetCoreInstallPath` | `()` | `string` | `system` | Gets core installation path..             For valid Orion user with at least WebViewer NCM role. |
| `Cirrus.Settings` | `GetDefaultPath` | `()` | `string` | `system` | Gets default path.             For valid Orion user with at least WebViewer NCM role. |
| `Cirrus.Settings` | `GetRegExById` | `(regexId)` | `SolarWinds.NCM.Contracts.ConfigComparison.R…` |  | Gets RegEx by id.             For valid Orion user with at least WebViewer NCM role. |
| `Cirrus.Settings` | `GetRegExes` | `()` | `array` |  | Gets all RegExes.             For valid Orion user with at least WebViewer NCM role. |
| `Cirrus.Settings` | `GetSetting` | `(settingName, defaultValue, engineId)` | `string` |  | Gets settings having value associated with the specified settingName. If the settingName is not… |
| `Cirrus.Settings` | `NetworkingSelfTest` | `()` | `array` | `admin` | Cross tests connection between all pollers. Only for Orion administrators. |
| `Cirrus.Settings` | `SaveRegExPattern` | `(regExId, title, enabled, regExPattern, comment, isBlock, blockEndRegEx)` | `string` |  | Saves RegEx pattern.             For valid Orion user with at least Administrator NCM role. |
| `Cirrus.Settings` | `SaveSetting` | `(settingName, settingValue, engineId)` | `System.Void` |  | Saves settings.             For valid Orion user with at least WebViewer NCM role. |
| `Cirrus.Settings` | `SaveUserLevelLoginCreds` | `(accountId, userName, password, enableLevel, enablePassword)` | `System.Void` |  | Saves user level login credentials.             For valid Orion user with at least WebDownloade… |
| `Cirrus.Settings` | `SetCustomMacros` | `(name, value)` | `System.Void` |  | Sets custom macros.             For valid Orion user with at least Administrator NCM role. |
| `Cirrus.Settings` | `SetGlobalMacroForAllNodes` | `(field, value)` | `System.Void` |  | Sets global macro for all nodes.             For valid Orion user with at least Administrator N… |
| `Cirrus.Settings` | `ValidateADUser` | `(user, password)` | `boolean` | `system` | Validates adding user.             For valid Orion user with at least WebViewer NCM role. |
| `Cirrus.Settings` | `ValidatePathWithoutImpersonation` | `(path)` | `boolean` | `system` | Validates the path without impersonation.             For valid Orion user with at least WebVie… |
| `Cirrus.SnippetArchive` | `AddSnippet` | `(title, config, comments)` | `string` |  | Adds snippet.             For valid Orion user with at least Administrator NCM role. |
| `Cirrus.SnippetArchive` | `DeleteSnippet` | `(snippetId)` | `System.Void` |  | Removes snippet.             For valid Orion user with at least Administrator NCM role. |
| `Cirrus.SnippetArchive` | `UpdateSnippet` | `(snippetId, title, config, comments)` | `System.Void` |  | Updates snippet.             For valid Orion user with at least Administrator NCM role. |

## Cortex

| Entity | Verb | Signature | Returns | Requires | Description |
| --- | --- | --- | --- | --- | --- |
| `Cortex.Orion.CiscoAci.Apic` | `AssignAciPolling` | `(nodeId)` | `System.Void` |  |  |
| `Cortex.Orion.CiscoAci.Apic` | `TestAciCredentials` | `(hostOrIpAddress, userName, password, certificateIdentity)` | `SolarWinds.Orion.Common.Models.CredentialsV…` |  |  |
| `Cortex.Orion.Interface` | `Core.AddToCortex` | `(OrionId)` | `array` | `admin`, `allowRealTimePolling` |  |
| `Cortex.Orion.Interface` | `Core.AssignToEngine` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.Interface` | `Core.GetSupportedMetrics` | `()` | `unknown` | `admin`, `allowRealTimePolling` |  |
| `Cortex.Orion.Interface` | `Core.InventoryNow` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.Interface` | `Core.PollNow` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.Interface` | `Core.SetPolling` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.Interface` | `Core.StartRealTimePolling` | `()` | `unknown` | `admin`, `allowRealTimePolling` |  |
| `Cortex.Orion.Interface` | `Core.StopRealTimePolling` | `()` | `unknown` | `admin`, `allowRealTimePolling` |  |
| `Cortex.Orion.MonitoringElement` | `Core.AssignToEngine` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.MonitoringElement` | `Core.GetSupportedMetrics` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.MonitoringElement` | `Core.InventoryNow` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.MonitoringElement` | `Core.PollNow` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.MonitoringElement` | `Core.SetPolling` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.MonitoringElement` | `Core.StartRealTimePolling` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.MonitoringElement` | `Core.StopRealTimePolling` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.NetMan.CloudMonitoring.CloudAccount` | `Core.AssignToEngine` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.NetMan.CloudMonitoring.CloudAccount` | `Core.GetSupportedMetrics` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.NetMan.CloudMonitoring.CloudAccount` | `Core.InventoryNow` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.NetMan.CloudMonitoring.CloudAccount` | `Core.PollNow` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.NetMan.CloudMonitoring.CloudAccount` | `Core.SetPolling` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.NetMan.CloudMonitoring.CloudAccount` | `Core.StartRealTimePolling` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.NetMan.CloudMonitoring.CloudAccount` | `Core.StopRealTimePolling` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.NetMan.CloudMonitoring.CloudAccount` | `Orion.NetMan.CloudMonitoring.CreateOrUpdateCloudAccount` | `(OrionCloudAccountId, Name, StatisticsPollingInterval, VirtualNetworkGatewaysPollingEnabled, MonitorApiRequestsEnabled, CloudAccountType)` | `array` | `admin` |  |
| `Cortex.Orion.NetMan.CloudMonitoring.CloudAccount` | `Orion.NetMan.CloudMonitoring.GetCloudAccountState` | `(OrionCloudAccountId)` | `array` | `admin` |  |
| `Cortex.Orion.NetMan.CloudMonitoring.CloudAccount` | `Orion.NetMan.CloudMonitoring.RemoveCloudAccount` | `(OrionCloudAccountId)` | `array` | `admin` |  |
| `Cortex.Orion.NetMan.CloudMonitoring.VirtualNetwork` | `Core.AssignToEngine` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.NetMan.CloudMonitoring.VirtualNetwork` | `Core.GetSupportedMetrics` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.NetMan.CloudMonitoring.VirtualNetwork` | `Core.InventoryNow` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.NetMan.CloudMonitoring.VirtualNetwork` | `Core.PollNow` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.NetMan.CloudMonitoring.VirtualNetwork` | `Core.SetPolling` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.NetMan.CloudMonitoring.VirtualNetwork` | `Core.StartRealTimePolling` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.NetMan.CloudMonitoring.VirtualNetwork` | `Core.StopRealTimePolling` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.NetMan.CloudMonitoring.VirtualNetworkConnection` | `Core.AssignToEngine` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.NetMan.CloudMonitoring.VirtualNetworkConnection` | `Core.GetSupportedMetrics` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.NetMan.CloudMonitoring.VirtualNetworkConnection` | `Core.InventoryNow` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.NetMan.CloudMonitoring.VirtualNetworkConnection` | `Core.PollNow` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.NetMan.CloudMonitoring.VirtualNetworkConnection` | `Core.SetPolling` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.NetMan.CloudMonitoring.VirtualNetworkConnection` | `Core.StartRealTimePolling` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.NetMan.CloudMonitoring.VirtualNetworkConnection` | `Core.StopRealTimePolling` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.NetMan.CloudMonitoring.VirtualNetworkGateway` | `Core.AssignToEngine` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.NetMan.CloudMonitoring.VirtualNetworkGateway` | `Core.GetSupportedMetrics` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.NetMan.CloudMonitoring.VirtualNetworkGateway` | `Core.InventoryNow` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.NetMan.CloudMonitoring.VirtualNetworkGateway` | `Core.PollNow` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.NetMan.CloudMonitoring.VirtualNetworkGateway` | `Core.SetPolling` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.NetMan.CloudMonitoring.VirtualNetworkGateway` | `Core.StartRealTimePolling` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.NetMan.CloudMonitoring.VirtualNetworkGateway` | `Core.StopRealTimePolling` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.NetMan.Firewalls.Firewall` | `AssignPaloAltoPolling` | `(nodeId)` | `System.Void` |  |  |
| `Cortex.Orion.NetMan.Firewalls.Firewall` | `Orion.NetMan.Firewalls.DisablePolling` | `(nodeId, firewallType?)` | `System.Void` | `admin` |  |
| `Cortex.Orion.NetMan.Firewalls.Firewall` | `Orion.NetMan.Firewalls.EnablePolling` | `(nodeId, firewallType)` | `System.Void` | `admin` |  |
| `Cortex.Orion.NetMan.Firewalls.Firewall` | `Orion.NetMan.Firewalls.IsPollingEnabled` | `(nodeId, firewallType)` | `boolean` | `admin` |  |
| `Cortex.Orion.NetMan.Firewalls.Firewall` | `TestFirewallCredentials` | `(hostOrIpAddress, userName, password, certificateIdentity)` | `SolarWinds.Orion.Common.Models.CredentialsV…` | `admin` |  |
| `Cortex.Orion.Node` | `Core.AddToCortex` | `(OrionId)` | `array` | `admin`, `allowRealTimePolling` |  |
| `Cortex.Orion.Node` | `Core.AssignToEngine` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.Node` | `Core.GetSupportedMetrics` | `()` | `unknown` | `admin`, `allowRealTimePolling` |  |
| `Cortex.Orion.Node` | `Core.InventoryNow` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.Node` | `Core.PollNow` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.Node` | `Core.SetPolling` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.Node` | `Core.StartRealTimePolling` | `()` | `unknown` | `admin`, `allowRealTimePolling` |  |
| `Cortex.Orion.Node` | `Core.StopRealTimePolling` | `()` | `unknown` | `admin`, `allowRealTimePolling` |  |
| `Cortex.Orion.Virtualization.HypervisorEntity` | `Core.AssignToEngine` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.Virtualization.HypervisorEntity` | `Core.GetSupportedMetrics` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.Virtualization.HypervisorEntity` | `Core.InventoryNow` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.Virtualization.HypervisorEntity` | `Core.PollNow` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.Virtualization.HypervisorEntity` | `Core.SetPolling` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.Virtualization.HypervisorEntity` | `Core.StartRealTimePolling` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.Virtualization.HypervisorEntity` | `Core.StopRealTimePolling` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.Virtualization.VSan` | `Core.AssignToEngine` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.Virtualization.VSan` | `Core.GetSupportedMetrics` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.Virtualization.VSan` | `Core.InventoryNow` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.Virtualization.VSan` | `Core.PollNow` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.Virtualization.VSan` | `Core.SetPolling` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.Virtualization.VSan` | `Core.StartRealTimePolling` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.Virtualization.VSan` | `Core.StopRealTimePolling` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.Volume` | `Core.AddToCortex` | `(OrionId)` | `array` | `admin`, `allowRealTimePolling` |  |
| `Cortex.Orion.Volume` | `Core.AssignToEngine` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.Volume` | `Core.GetSupportedMetrics` | `()` | `unknown` | `admin`, `allowRealTimePolling` |  |
| `Cortex.Orion.Volume` | `Core.InventoryNow` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.Volume` | `Core.PollNow` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.Volume` | `Core.SetPolling` | `()` | `unknown` | `admin` |  |
| `Cortex.Orion.Volume` | `Core.StartRealTimePolling` | `()` | `unknown` | `admin`, `allowRealTimePolling` |  |
| `Cortex.Orion.Volume` | `Core.StopRealTimePolling` | `()` | `unknown` | `admin`, `allowRealTimePolling` |  |

## IPAM

| Entity | Verb | Signature | Returns | Requires | Description |
| --- | --- | --- | --- | --- | --- |
| `IPAM.AttrDefine` | `AddCustomProperty` | `(propertyName, description, maxStringLength, attributeType?, linkTitle?, addToIpAddress?, addToGroups?)` | `boolean` |  |  |
| `IPAM.AttrDefine` | `DeleteCustomProperty` | `(propertyName)` | `boolean` |  |  |
| `IPAM.AttrDefine` | `UpdateCustomProperty` | `(propertyName, description, maxStringLength, linkTitle, addToIpAddress, addToGroups)` | `boolean` |  |  |
| `IPAM.DhcpDnsManagement` | `AddDhcpScope` | `(dhcpServerId, scopeAddress, scopeCidr, scopeName, description?, disabledAtServer?, autoAddIpAddresses?, scopeRangeStart?, scopeRangeEnd?, offerDelay?, defaultLeaseTime?, maxLeaseTime?, preferredLifeTime?, validLifeTime?, preference?, exclusions?, options?, ranges?, sharedNetworkName?, dhcpGroupId?, dhcpGroupName?, vlan?, location?)` | `string` |  |  |
| `IPAM.DhcpDnsManagement` | `AddDhcpServer` | `(nodeId, newHierarchyGroupName, newCredentialName, newCredentialUserName, newCredentialPassword, newCredentialEnablePassword, newCredentialProtocol?, newCredentialClientPort?, newCredentialEnableLevel?, credentialId?, clusterId?, scopesScanInterval?, scanInterval?, serverType?, autoAddNewScopes?, enableSubnetScanning?, newCredentialIpv6Username?, newCredentialIpv6Password?, newCredentialUseAuthentication?, newCredentialEnableIpv4Credentials?, newCredentialEnableIpv6Credentials?, newCredentialIpv6Port?)` | `string` |  |  |
| `IPAM.DhcpDnsManagement` | `AddDnsServer` | `(nodeId, newCredentialName, newCredentialUserName, newCredentialPassword, newCredentialProtocol?, newCredentialClientPort?, credentialId?, enableScanning?, incrementalZoneTransfer?, scanInterval?, serverType?)` | `string` |  |  |
| `IPAM.DhcpDnsManagement` | `CreateDhcpCredentials` | `(dhcpServerType, credentials)` | `number` |  |  |
| `IPAM.DhcpDnsManagement` | `CreateDnsCredentials` | `(dnsServerType, credentials)` | `number` |  |  |
| `IPAM.DhcpDnsManagement` | `CreateIpReservation` | `(ipAddressToReserve, dhcpServerIpAddress, reservationName, reservationMAC, reservationType?)` | `string` |  |  |
| `IPAM.DhcpDnsManagement` | `CreateIpv6Reservation` | `(ipAddressToReserve, dhcpServerIpAddress, reservationName, duid, iaid?)` | `string` |  |  |
| `IPAM.DhcpDnsManagement` | `DeleteDhcpServer` | `(groupId, removeCorrespondingSubnets?, removeScopesFromServer?)` | `string` |  |  |
| `IPAM.DhcpDnsManagement` | `DeleteDnsServer` | `(groupId, removeZonesFromServer?)` | `string` |  |  |
| `IPAM.DhcpDnsManagement` | `GetAandPTRrecordsForDnsZone` | `(zoneName, dnsServerIp)` | `array` |  |  |
| `IPAM.DhcpDnsManagement` | `RemoveIpReservation` | `(ipRemoveReservation, dhcpServerIpAddress)` | `string` |  |  |
| `IPAM.DhcpDnsManagement` | `RemoveIpv6Reservation` | `(ipRemoveReservation, dhcpServerIpAddress)` | `string` |  |  |
| `IPAM.DhcpDnsManagement` | `StartDhcpCredentialsTest` | `(nodeId, dhcpServerType, credentialId, credentials)` | `string` |  |  |
| `IPAM.DhcpDnsManagement` | `StartDnsCredentialsTest` | `(nodeId, dnsServerType, credentialId, credentials)` | `string` |  |  |
| `IPAM.DhcpDnsManagement` | `StartScanDhcpServer` | `(dhcpServerId)` | `string` |  |  |
| `IPAM.DhcpDnsManagement` | `StartScanDnsServer` | `(dnsServerId)` | `string` |  |  |
| `IPAM.DhcpDnsManagement` | `UpdateDhcpServer` | `(dhcpServerId, propertiesToUpdate)` | `string` |  |  |
| `IPAM.DhcpDnsManagement` | `UpdateDnsServer` | `(dnsServerId, propertiesToUpdate)` | `string` |  |  |
| `IPAM.GroupManagement` | `CreateGroup` | `(groupName, comments, parentGroupId)` | `System.Void` |  |  |
| `IPAM.GroupManagement` | `GetAllGroupNodesByName` | `(groupName)` | `array` |  |  |
| `IPAM.GroupManagement` | `GetGroupsByName` | `(groupName)` | `array` |  |  |
| `IPAM.GroupManagement` | `RemoveGroup` | `(groupId)` | `System.Void` |  |  |
| `IPAM.GroupsCustomProperties` | `CreateCustomProperty` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `IPAM.GroupsCustomProperties` | `CreateCustomPropertyWithValues` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Value, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `IPAM.GroupsCustomProperties` | `DeleteCustomProperty` | `(PropertyName)` | `System.Void` |  |  |
| `IPAM.GroupsCustomProperties` | `ModifyCustomProperty` | `(PropertyName, Description, Size, Values, Usages?, Mandatory?, Default?, SourceId?, SourceName?, propertyDisplayName?)` | `System.Void` |  |  |
| `IPAM.IPAddressManagement` | `AddDnsARecord` | `(recordName, nodeIPv4Address, dnsIpAddress, dnsZoneName)` | `string` |  |  |
| `IPAM.IPAddressManagement` | `AddDnsARecordWithPtr` | `(recordName, nodeIPv4Address, dnsIpAddress, dnsZoneName)` | `string` |  |  |
| `IPAM.IPAddressManagement` | `AddDnsAaaaRecord` | `(recordName, nodeIPv6Address, dnsIpAddress, dnsZoneName)` | `string` |  |  |
| `IPAM.IPAddressManagement` | `AddPtrRecord` | `(recordName, recordData, dnsIpAddress, dnsZoneName)` | `string` |  |  |
| `IPAM.IPAddressManagement` | `AddPtrToDnsARecord` | `(recordName, nodeIPv4Address, dnsIpAddress, dnsZoneName)` | `string` |  |  |
| `IPAM.IPAddressManagement` | `ChangeDnsARecord` | `(recordName, nodeIPv4Address, dnsIpAddress, dnsZoneName, nodeIPv4AddressNew)` | `string` |  |  |
| `IPAM.IPAddressManagement` | `ChangeDnsAaaaRecord` | `(recordName, nodeIpV6Address, dnsIpAddress, dnsZoneName, newNodeIpV6Address)` | `string` |  |  |
| `IPAM.IPAddressManagement` | `RemoveDnsARecord` | `(recordName, nodeIPv4Address, dnsIpAddress, dnsZoneName)` | `string` |  |  |
| `IPAM.IPAddressManagement` | `RemoveDnsAaaaRecord` | `(recordName, nodeIpV6Address, dnsIpAddress, dnsZoneName)` | `string` |  |  |
| `IPAM.IPAddressManagement` | `RemovePtrRecord` | `(recordName, dnsIpAddress, dnsZoneName, isRetryingDnsZoneSearch?)` | `string` |  |  |
| `IPAM.NodesCustomProperties` | `CreateCustomProperty` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `IPAM.NodesCustomProperties` | `CreateCustomPropertyWithValues` | `(PropertyName, Description, ValueType, Size, ValidRange, Parser, Header, Alignment, Format, Units, Value, Usages?, Mandatory?, Default?, SourceId?, SourceName?, DisplayName?)` | `System.Void` |  |  |
| `IPAM.NodesCustomProperties` | `DeleteCustomProperty` | `(PropertyName)` | `System.Void` |  |  |
| `IPAM.NodesCustomProperties` | `ModifyCustomProperty` | `(PropertyName, Description, Size, Values, Usages?, Mandatory?, Default?, SourceId?, SourceName?, propertyDisplayName?)` | `System.Void` |  |  |
| `IPAM.SubnetManagement` | `AddIpRange` | `(subnetGroupId, startIp, endIp)` | `System.Void` |  |  |
| `IPAM.SubnetManagement` | `AddIpv6Range` | `(subnetGroupId, startIp, endIp)` | `System.Void` |  |  |
| `IPAM.SubnetManagement` | `CancelIpReservation` | `(reservedIpAddress)` | `System.Void` |  |  |
| `IPAM.SubnetManagement` | `CancelIpReservationForGroup` | `(reservedIpAddress, hierarchyGroup)` | `System.Void` |  |  |
| `IPAM.SubnetManagement` | `ChangeDisableAutoScanning` | `(groupId, disableAutoScanning)` | `System.Void` |  |  |
| `IPAM.SubnetManagement` | `ChangeIpStatus` | `(ipAddress, status, subnetId?)` | `System.Void` |  |  |
| `IPAM.SubnetManagement` | `ChangeIpStatusForGroup` | `(ipAddress, status, hierarchyGroup)` | `System.Void` |  |  |
| `IPAM.SubnetManagement` | `CreateIPv6Subnet` | `(prefix, prefixName, isNewPrefix, subnetAddress, rawCidr)` | `System.Void` |  |  |
| `IPAM.SubnetManagement` | `CreateIPv6SubnetForGroup` | `(prefix, prefixName, isNewPrefix, subnetAddress, rawCidr, hierarchyGroup)` | `System.Void` |  |  |
| `IPAM.SubnetManagement` | `CreateSubnet` | `(subnetAddress, rawCidr)` | `System.Void` |  |  |
| `IPAM.SubnetManagement` | `CreateSubnetForGivenParentNode` | `(subnetAddress, rawCidr, parentGroupId)` | `System.Void` |  |  |
| `IPAM.SubnetManagement` | `CreateSubnetForGroup` | `(subnetAddress, rawCidr, hierarchyGroup)` | `System.Void` |  |  |
| `IPAM.SubnetManagement` | `FinishIpReservation` | `(ipAddress, finalIpStatus)` | `System.Void` |  |  |
| `IPAM.SubnetManagement` | `FinishIpReservationForGroup` | `(ipAddress, finalIpStatus, hierarchyGroup)` | `System.Void` |  |  |
| `IPAM.SubnetManagement` | `GetFirstAvailableIp` | `(subnetAddress, subnetCidr)` | `string` |  |  |
| `IPAM.SubnetManagement` | `GetFirstAvailableIpForGroup` | `(subnetAddress, subnetCidr, hierarchyGroup)` | `string` |  |  |
| `IPAM.SubnetManagement` | `GetFirstAvailableIpViaFriendlyName` | `(friendlyName)` | `string` |  |  |
| `IPAM.SubnetManagement` | `GetFirstAvailableIpv6` | `()` | `unknown` |  |  |
| `IPAM.SubnetManagement` | `RemoveIpRange` | `(subnetGroupId, startIp, endIp)` | `System.Void` |  |  |
| `IPAM.SubnetManagement` | `StartIpReservation` | `(subnetAddress, subnetCidr, reservationTimeInMinutes?, addressToStart?)` | `string` |  |  |
| `IPAM.SubnetManagement` | `StartIpReservationForGroup` | `(subnetAddress, subnetCidr, hierarchyGroup, reservationTimeInMinutes?, addressToStart?)` | `string` |  |  |
| `IPAM.SupernetManagement` | `CreateSupernet` | `(supernetName, address, cidr, description, parentGroupId)` | `System.Void` |  |  |
| `IPAM.SupernetManagement` | `EditSupernet` | `(id, name, cidr, description)` | `System.Void` |  |  |
| `IPAM.SupernetManagement` | `GetSupernetsByName` | `(supernetName)` | `array` |  |  |

## NCM

| Entity | Verb | Signature | Returns | Requires | Description |
| --- | --- | --- | --- | --- | --- |
| `NCM.ConfigTypes` | `CreateCustom` | `(name)` | `SolarWinds.NCM.Contracts.ConfigTypes.Config…` | `manageNodes` | Creates custom config type.             Valid for Orion manage node users with at least Enginee… |
| `NCM.ConfigTypes` | `DeleteCustom` | `(id)` | `System.Void` | `manageNodes` | Removes config type by ID.             Valid for Orion manage node users with at least Engineer… |
| `NCM.ConfigTypes` | `UpdateCustomName` | `(id, newName)` | `SolarWinds.NCM.Contracts.ConfigTypes.Config…` | `manageNodes` | Updates config type.             Valid for Orion manage node users with at least Engineer NCM r… |
| `NCM.Eos` | `BeginRefreshAll` | `()` | `boolean` |  | Starts refreshing End of Support data for all nodes. For valid Orion user with at least Enginee… |
| `NCM.Eos` | `InitSchedule` | `()` | `System.Void` |  | Schedule daily lookup of End of Support data. For valid Orion user with Administrator NCM role. |
| `NCM.Eos` | `IsRefreshingAll` | `()` | `boolean` |  | Checks if data for all nodes is being refreshed. For valid Orion user with at least Engineer NC… |
| `NCM.Eos` | `RefreshNow` | `(nodeIds)` | `System.Void` |  | Starts refreshing End of Support data for selected nodes. For valid Orion user with at least En… |
| `NCM.FirmwareDefinitions` | `AddFirmwareDefinition` | `(firmwareDefinition)` | `number` |  | Adds new firmware definition. For valid Orion user with Administrator NCM role. |
| `NCM.FirmwareDefinitions` | `DeleteFirmwareDefinitions` | `(ids)` | `System.Void` |  | Deletes selected firmware definitions. For valid Orion user with Administrator NCM role. |
| `NCM.FirmwareDefinitions` | `GetFirmwareDefinition` | `(id)` | `SolarWinds.NCM.Contracts.InformationService…` |  | Gets the firmware definition data. For valid Orion user with at least WebViewer NCM role. |
| `NCM.FirmwareDefinitions` | `UpdateFirmwareDefinition` | `(firmwareDefinition)` | `System.Void` |  | Updates the firmware definition data. For valid Orion user with at least Administrator NCM role. |
| `NCM.FirmwareOperations` | `CancelUpgrade` | `(operationIds)` | `System.Void` |  | Cancels upgrade operations. For valid Orion user with at least WebUploader NCM role. |
| `NCM.FirmwareOperations` | `DeleteFirmwareOperations` | `(operationIds)` | `System.Void` |  | Deletes upgrade operations. For valid Orion user with at least WebUploader NCM role. |
| `NCM.FirmwareOperations` | `GenerateScriptPreview` | `(nodeOptions)` | `string` |  | Generates script preview for operation. For valid Orion user with at least WebUploader NCM role. |
| `NCM.FirmwareOperations` | `PrepareFirmwareUpgrade` | `(coreNodeIds, firmwareDefinitionId, firmwareOperationName, imagesToApply)` | `number` |  | Prepares new firmware upgrade operation. For valid Orion user with at least WebUploader NCM rol… |
| `NCM.FirmwareOperations` | `PrepareReExecuteFailed` | `(operationId)` | `number` |  | Prepares new reexecute operation. For valid Orion user with at least WebUploader NCM role. |
| `NCM.FirmwareOperations` | `PrepareRollBack` | `(operationId)` | `number` |  | Prepares new rollback operation. For valid Orion user with at least WebUploader NCM role. |
| `NCM.FirmwareOperations` | `StartUpgrade` | `(operationId, nodeOptions, runAt, emailSettings)` | `System.Void` |  | Starts upgrade operation. For valid Orion user with at least WebUploader NCM role. |
| `NCM.FirmwareStorage` | `DeleteFirmwareImages` | `(imageIds)` | `System.Void` |  | Deletes selected firmware images. For valid Orion user with Administrator NCM role. |
| `NCM.FirmwareStorage` | `UpdateFirmwareImage` | `(imageId, description, machineTypes)` | `System.Void` |  | Update selected firmware image. For valid Orion user with Administrator NCM role. |
| `NCM.FirmwareStorage` | `ValidateFirmwareStorage` | `(path, networkShareUserName, networkSharePassword)` | `SolarWinds.NCM.Contracts.InformationService…` |  | Validates firmware operation storage. For valid Orion user with Administrator NCM role. |
| `NCM.OneTimeOperations` | `BulkDeleteOneTimeOperations` | `(ids)` | `number` |  | Deletes one time operations in bulk. |
| `NCM.OneTimeOperations` | `UpdateOneTimeOperation` | `(id, status, scriptContent, reboot)` | `boolean` |  | Updates one time operation details. |
| `NCM.SecurityPolicy` | `GetSecurityPolicyAppIds` | `(nodeId, policyName)` | `array` |  | Gets list of security policy IDs for the node. |
| `NCM.SwisEntityTemplate` | `Ping` | `()` | `boolean` |  |  |
| `NCM.VulnerabilitiesAnnouncements` | `GetSettings` | `()` | `SolarWinds.SecObs.Common.Models.Vulnerabili…` |  | Gets all vulnerabilities settings.             For valid Orion user with at least Administrator… |
| `NCM.VulnerabilitiesAnnouncements` | `InitVulnerabilitySchedule` | `()` | `System.Void` |  | Initializes vulnerability schedule.             For valid Orion user with at least Administrato… |
| `NCM.VulnerabilitiesAnnouncements` | `IsVulnerabilityMatchingActive` | `()` | `boolean` |  | Checks if vulnerability matching is active.             For valid Orion user with at least WebV… |
| `NCM.VulnerabilitiesAnnouncements` | `StartVulnerabilityMatching` | `()` | `SolarWinds.SecObs.Common.Models.Vulnerabili…` |  | Starts vulnerability matching.             For valid Orion user with at least Administrator NCM… |

## UamsClient

| Entity | Verb | Signature | Returns | Requires | Description |
| --- | --- | --- | --- | --- | --- |
| `UamsClient.InstallationInfo` | `CreateInstallationInfo` | `()` | `System.Void` |  | Creates installation info with success installation result when UAMS client is installed manual… |
| `UamsClient.InstallationInfo` | `GetApiAccessToken` | `()` | `string` |  |  |
| `UamsClient.InstallationInfo` | `GetIngestionToken` | `()` | `string` |  |  |
| `UamsClient.InstallationInfo` | `InstallUamsClient` | `(swoken, endpoint)` | `System.Void` |  | Executed installation of the UAMS client on the main poller. |
| `UamsClient.InstallationInfo` | `UninstallUamsClient` | `()` | `System.Void` |  | Executed uninstallation of the UAMS client on the main poller. |
| `UamsClient.PlatformConnectWizard` | `ActivateBizAppsTenant` | `()` | `unknown` |  | Creates a new tenant in BizApps for the current Orion account. |
| `UamsClient.PlatformConnectWizard` | `CheckAPIAccessTokenValidity` | `()` | `unknown` |  |  |
| `UamsClient.PlatformConnectWizard` | `GetBizAppsDatacenters` | `()` | `string` |  | Retrieves the list of BizApps datacenters available to the current Orion account. |
| `UamsClient.PlatformConnectWizard` | `GetIngestionTokenByAPIAccess` | `()` | `unknown` |  |  |
| `UamsClient.PlatformConnectWizard` | `RetrialBizAppsTenant` | `()` | `string` |  | Initiates a retrial (start of trial) for an existing BizApps tenant whose trial has ended or be… |
| `UamsClient.PlatformConnectWizard` | `SetAccessToken` | `()` | `unknown` |  | Change access token. |

## PlatformConnect

| Entity | Verb | Signature | Returns | Requires | Description |
| --- | --- | --- | --- | --- | --- |
| `PlatformConnect.Wizard` | `CheckSwokenValidity` | `(swoken, swoUrl)` | `string` |  | Validates a swoken token for the provided SWO URL and returns Valid, Invalid, or Unknown. |
| `PlatformConnect.Wizard` | `CompleteConnect` | `(request)` | `string` |  | Finalizes the Platform Connect wizard flow by persisting feature configuration, enabling pollin… |
| `PlatformConnect.Wizard` | `GetBizAppsDatacenters` | `()` | `string` |  | Retrieves the list of BizApps datacenters available to the current Orion account. |
| `PlatformConnect.Wizard` | `RetrialBizAppsTenant` | `()` | `string` |  | Initiates a retrial (start of trial) for an existing BizApps tenant whose trial has ended or be… |
| `PlatformConnect.Wizard` | `StartConnect` | `(request)` | `string` |  | Starts the complete Platform Connect setup via a single backend operation: activates tenant, ma… |
| `PlatformConnect.Wizard` | `StartConnectWithAutoComplete` | `(request, completionRequest)` | `string` |  | Starts the complete Platform Connect setup and schedules an automatic completion once the UAMS… |
| `PlatformConnect.Wizard` | `StartConnectWithToken` | `(apiAccessToken, swoUrl)` | `string` |  | Starts the complete Platform connect setup with explicitly provided API access token: validates… |

## PlatformBridge

| Entity | Verb | Signature | Returns | Requires | Description |
| --- | --- | --- | --- | --- | --- |
| `PlatformBridge.Info` | `DeleteByOrganization` | `(organizationId)` | `System.Void` |  | Deletes all values for an organization identifier. |
| `PlatformBridge.Info` | `DeleteExpiredValues` | `()` | `number` |  | Removes all values that already expired. |
| `PlatformBridge.Info` | `DeleteValue` | `(key)` | `System.Void` |  | Deletes one key. |
| `PlatformBridge.Info` | `GetDecryptedValue` | `(key)` | `string` |  | Returns decrypted value for the key when present and not expired. |
| `PlatformBridge.Info` | `GetOrCreateBridgedOrionId` | `()` | `string` |  | Gets an existing Bridged Orion ID or creates a new stable one. |
| `PlatformBridge.Info` | `SetValue` | `(key, type, value, organizationId?, accountId?, expirationTimeUtc?)` | `System.Void` |  | Encrypts and stores or updates the value. |

## Cli

| Entity | Verb | Signature | Returns | Requires | Description |
| --- | --- | --- | --- | --- | --- |
| `Cli.CliSessionSettings` | `GetCliConnectionTestResult` | `(cliTestConnectionData)` | `SolarWinds.Orion.Cli.Contracts.DataModel.Cl…` |  | Returns current CLI connection status with logs on success. |
| `Cli.CliSessionSettings` | `GetCurrentCliConnectionParameters` | `()` | `SolarWinds.Orion.Cli.Contracts.DataModel.Cl…` |  | Returns current CLI connection parameters. |
| `Cli.CliSessionSettings` | `ValidateCliCredentials` | `(hostName, userName, password, enablePassword, port, useKeyboardInteractiveAuthentication, systemOid, systemDescription, engineId)` | `boolean` |  | Checks whether the provided CLI credentials are valid for the given host. |
| `Cli.CliSessionSettings` | `ValidateCliCredentialsExtended` | `(hostName, userName, password, enablePassword, protocol, port, useKeyboardInteractiveAuthentication, systemOid, systemDescription, engineId)` | `SolarWinds.Orion.Cli.Contracts.DataModel.Op…` |  | Checks whether the provided CLI credentials are valid for the given host using selected protoco… |

## System

| Entity | Verb | Signature | Returns | Requires | Description |
| --- | --- | --- | --- | --- | --- |
| `System.ActiveQuery` | `CancelByClientSessionID` | `(clientSessionID)` | `System.Void` |  |  |
| `System.Indication` | `ReportIndication` | `(indicationType, indicationProperties, sourceInstanceProperties)` | `System.Void` |  |  |
| `System.QueryPlanCache` | `Clear` | `()` | `System.Void` |  |  |

## Metadata

| Entity | Verb | Signature | Returns | Requires | Description |
| --- | --- | --- | --- | --- | --- |
| `Metadata.Entity` | `GetAliases` | `(query)` | `array` |  |  |
| `Metadata.Entity` | `GetSchemaLoadTime` | `()` | `string` |  |  |

## SOC

| Entity | Verb | Signature | Returns | Requires | Description |
| --- | --- | --- | --- | --- | --- |
| `SOC.Settings` | `SetSetting` | `(key, value)` | `System.Void` |  | Set key/value setting into this entity. |

---

A `?` after a parameter name marks it optional. `Requires` is the right an account must hold to invoke the verb; an empty cell means the entity's own access control applies. Verbs recovered from the Swagger contract but absent from the rendered schema pages have no access control listed.

<!-- GENERATED FILE. Do not edit by hand.
     Produced by tools/diff_schema.py. -->

# Schema changes: 2025.4 to 2026.2

What changed in the SWIS schema between these two platform versions, and which of those changes can break code that already works.

Read the removals first. Additions cannot break anything you have already written; removals and reordered verb arguments can, and the second kind fails quietly because Invoke sends a positional array with no names in it.

## Summary

| Change | Count |
| --- | ---: |
| Entities added | 93 |
| Entities removed | 7 |
| Entities renamed | 0 |
| Entities otherwise changed | 95 |
| Entities that lost a property | 20 |
| Entities that lost a navigation property | 8 |
| Verbs added | 20 |
| Verbs removed | 27 |
| Verb signatures changed (breaking) | 1 |
| Verb signatures changed (new required argument) | 0 |
| Verb parameter names recased (no caller impact) | 3 |

## Removed entities

7 entities present in 2025.4 are absent from 2026.2. Some are genuine removals; others belong to a module that was restructured. Check each against your own server before concluding it is gone.

- `Cortex.Orion.NetMan.Firewalls.Firewall.Statistics`
- `Cortex.Orion.NetMan.Firewalls.FirewallCentralizedSettings`
- `Cortex.Orion.NetMan.Firewalls.RemoteAccess.Statistics`
- `Cortex.Orion.NetMan.Firewalls.SiteToSiteTunnel.Statistics`
- `IPAM.Event`
- `IPAM.SNMPCred`
- `IPAM.WindowsCred`

## Verb signature changes that break callers

Invoke arguments are positional. When the order of a shared prefix changes, an existing call still has the right number of arguments and sends them into the wrong slots, so it can fail with a confusing type error or, worse, succeed against the wrong values. Audit every call site for these.

| Entity | Verb | Was | Is now | Why it breaks |
| --- | --- | --- | --- | --- |
| `Orion.Orchestrators.Info` | `AddFortinetFortiManagerNode` | `(engineId, caption, hostname, username, password, clientId)` | `(engineId, caption, hostname, organizationId, organizationName, tokenUrl, username, password, appId, apiPassword, clientId, token)` | positional argument order changed |

## Entities that lost properties or navigation properties

A query selecting a removed property fails outright. A query selecting a removed navigation property fails the same way, but a report built on one may simply go empty, which is easier to miss.

| Entity | Removed properties | Removed navigations |
| --- | --- | --- |
| `Cortex.Orion.NetMan.Firewalls.Firewall` | `AgentId`, `AgentOsType`, `EngineId`, `PollInterval`, `PollState`, `PollState_Value`, `RelatedFirewallCentralizedSettings`, `RequestInventory` | `FirewallCentralizedSettings`, `Statistics` |
| `Cortex.Orion.NetMan.Firewalls.RemoteAccess` | `AgentId`, `AgentOsType`, `EngineId`, `PollState`, `PollState_Value`, `RequestInventory` | `Statistics` |
| `Cortex.Orion.NetMan.Firewalls.SiteToSiteTunnel` | `AgentId`, `AgentOsType`, `EngineId`, `PollState`, `PollState_Value`, `RequestInventory` | `Statistics` |
| `IPAM.IPHistory` | `HistoryId`, `Time` |  |
| `Orion.AllActiveAlerts.Dashboard` | `AlertUrl`, `EntityDetailsUrl`, `Name`, `SeverityName`, `SiteID` |  |
| `Orion.Cloud.Accounts` |  | `AzureStorageAccount` |
| `Orion.Cloud.Aws.CostManagement` | `Name` |  |
| `Orion.Cloud.Azure.AppService` | `HealthCheckStatus` |  |
| `Orion.Cloud.Azure.AppServiceStatistics` | `HealthCheckStatus` |  |
| `Orion.Cloud.Azure.StorageAccount` |  | `RelatedCloudAccount` |
| `Orion.Cloud.Azure.StorageAccountStatistics` | `ObservationTimestamp`, `Weight` |  |
| `Orion.EventTypes` |  | `OrionEventTypes` |
| `Orion.Fortigate.HighAvailability` |  | `PrimaryNode` |
| `Orion.Nodes` |  | `FortigateHighAvailabilityPrimaryMember` |
| `Orion.SEUM.AgentStatus` | `Archive`, `DateTimeUtc`, `RecordCount` |  |
| `Orion.SEUM.AgentStatusReport` | `DateTimeUtc`, `RecordCount` |  |
| `Orion.SEUM.ResponseTime` | `Archive`, `DateTimeUtc`, `RawHtml`, `RecordCount`, `Screenshot` |  |
| `Orion.SEUM.ResponseTimeDetail` | `Archive`, `DateTimeUtc`, `RawHtml`, `Screenshot` |  |
| `Orion.SEUM.ResponseTimeReport` | `DateTimeUtc`, `RecordCount` |  |
| `Orion.SEUM.StepResponseTime` | `Archive`, `DateTimeUtc`, `RecordCount` |  |
| `Orion.SEUM.StepResponseTimeDetail` | `Archive`, `DateTimeUtc`, `ErrorMessage`, `ScreenshotId` |  |
| `Orion.SEUM.StepResponseTimeDetailLargeData` | `DateTimeUtc` |  |
| `Orion.SEUM.StepResponseTimeLargeData` | `DateTimeUtc` |  |
| `Orion.SEUM.StepResponseTimeReport` | `DateTimeUtc`, `RecordCount` |  |
| `Orion.SecObs.Vulnerabilities.LastMatching.NodeScores` | `IsSupported` |  |

## Properties whose type changed

These do not fail a SWQL query, but they can fail a typed client that binds the column to a field.

| Entity | Property | Was | Is now |
| --- | --- | --- | --- |
| `IPAM.Conflict` | `IPNodeID` | `System.Int32` | `System.Int64` |
| `IPAM.ConflictDetail` | `IPNodeID` | `System.Int32` | `System.Int64` |
| `IPAM.DNSMismatch` | `ForwardIPNodeID` | `System.Int32` | `System.Int64` |
| `IPAM.DNSMismatch` | `ReverseIPNodeID` | `System.Int32` | `System.Int64` |
| `IPAM.DhcpServer` | `StatAcks` | `System.Int32` | `System.Int64` |
| `IPAM.DhcpServer` | `StatDeclines` | `System.Int32` | `System.Int64` |
| `IPAM.DhcpServer` | `StatDiscovers` | `System.Int32` | `System.Int64` |
| `IPAM.DhcpServer` | `StatNaks` | `System.Int32` | `System.Int64` |
| `IPAM.DhcpServer` | `StatOffers` | `System.Int32` | `System.Int64` |
| `IPAM.DhcpServer` | `StatReleases` | `System.Int32` | `System.Int64` |
| `IPAM.DhcpServer` | `StatRequests` | `System.Int32` | `System.Int64` |
| `IPAM.IPConflict` | `IPNodeId` | `System.Int32` | `System.Int64` |
| `IPAM.IPHistory` | `IPNodeId` | `System.Int32` | `System.Int64` |
| `IPAM.IPInfo` | `IPNodeId` | `System.Int32` | `System.Int64` |
| `IPAM.IPNode` | `IpNodeId` | `System.Int32` | `System.Int64` |
| `IPAM.IPNodeAttr` | `IPNodeId` | `System.Int32` | `System.Int64` |
| `IPAM.IPNodeDisplayCustomProperties` | `IpNodeId` | `System.Int32` | `System.Int64` |
| `IPAM.IPNodeGrid` | `IpNodeId` | `System.Int32` | `System.Int64` |
| `IPAM.IPNodeReport` | `IPNodeId` | `System.Int32` | `System.Int64` |
| `IPAM.IPNodeWithHistory` | `IpNodeId` | `System.Int32` | `System.Int64` |
| `IPAM.IPRequestAddresses` | `IPNodeId` | `System.Int32` | `System.Int64` |
| `IPAM.IpAddressesForReservation` | `IpNodeId` | `System.Int32` | `System.Int64` |
| `IPAM.NodeMinCorrespondingIps` | `IpNodeId` | `System.Int32` | `System.Int64` |
| `IPAM.NodeMinCorrespondingIps` | `MinN4IPNodeId` | `System.Int32` | `System.Int64` |
| `IPAM.NodeMinCorrespondingIps` | `MinN6IPNodeId` | `System.Int32` | `System.Int64` |
| `IPAM.NodesCustomProperties` | `IPNodeId` | `System.Int32` | `System.Int64` |
| `Orion.GroupMembers` | `IsGroup` | `System.boolean` | `System.Boolean` |
| `Orion.IpSla.VoipGatewaySipStats` | `SipStatsErrClient` | `System.Int32` | `System.Int64` |
| `Orion.IpSla.VoipGatewaySipStats` | `SipStatsErrServer` | `System.Int32` | `System.Int64` |
| `Orion.IpSla.VoipGatewaySipStats` | `SipStatsGlobalFail` | `System.Int32` | `System.Int64` |
| `Orion.IpSla.VoipGatewaySipStats` | `SipStatsRedirect` | `System.Int32` | `System.Int64` |
| `Orion.IpSla.VoipGatewaySipStats` | `SipStatsRetry` | `System.Int32` | `System.Int64` |
| `Orion.IpSla.VoipGatewaySipStats` | `SipStatsSuccess` | `System.Int32` | `System.Int64` |
| `Orion.MemoryMultiLoad` | `Index` | `System.Int16` | `System.Int32` |
| `Orion.MemoryMultiLoadCurrent` | `Index` | `System.Int16` | `System.Int32` |

## New verbs

20 verbs are available in 2026.2 that were not in 2025.4.

- `Cli.CliSessionSettings`: `ValidateCliCredentials`, `ValidateCliCredentialsExtended`
- `Cortex.Orion.NetMan.Firewalls.Firewall`: `AssignPaloAltoPolling`, `TestFirewallCredentials`
- `IPAM.DhcpDnsManagement`: `AddDhcpScope`, `CreateIpv6Reservation`, `RemoveIpv6Reservation`
- `IPAM.SubnetManagement`: `AddIpRange`, `AddIpv6Range`, `RemoveIpRange`
- `Orion.Discovery`: `GetDiscoveryProfileResourcesResult`
- `Orion.Environment`: `GetProxySettings`
- `Orion.HA.Pools`: `ElbDisable`, `ElbEnable`
- `Orion.HardwareHealth.BMC.Controllers`: `TestBmcConnection`
- `Orion.NPM.Interfaces`: `SetBandwidth`
- `Orion.Orchestrators.Info`: `ValidateFortinetFortiManagerCloudApiAuthentication`, `ValidateFortinetFortiManagerTokenAuthentication`, `ValidateFortinetFortiManagerUsernamePasswordAuthentication`
- `Orion.SwisFeature`: `HttpsCertificateThumbprint`

## New entities

93 entities are new in 2026.2.

**ContentModel** (1)

- `ContentModel.OrionNodes`

**IPAM** (1)

- `IPAM.EventType`

**NCM** (1)

- `NCM.OneTimeOperations`

**Orion** (83)

- `Orion.ActivePollingErrors`
- `Orion.Alerts.SeverityInfo`
- `Orion.Azure.CostExpandedStatistics`
- `Orion.Banners.BannerAccountSettings`
- `Orion.Banners.Instances`
- `Orion.CiscoAci.ApicThresholds`
- `Orion.CiscoAci.HealthScoreThreshold`
- `Orion.Cloud.Aws.ElasticBeanstalkEnvironment`
- `Orion.Cloud.Aws.ElasticBeanstalkEnvironmentNode`
- `Orion.Cloud.Aws.ElasticBeanstalkEnvironmentNodeStatistics`
- `Orion.Cloud.Aws.ElasticBeanstalkEnvironmentStatistics`
- `Orion.Cloud.Aws.ElasticKubernetesCluster`
- `Orion.Cloud.Aws.ElasticKubernetesClusterStatistics`
- `Orion.Cloud.Aws.ElasticKubernetesNode`
- `Orion.Cloud.Aws.ElasticKubernetesNodeGroup`
- `Orion.Cloud.Aws.ElasticKubernetesNodeStatistics`
- `Orion.Cloud.Aws.LambdaFunction`
- `Orion.Cloud.Aws.LambdaFunctionStatistics`
- `Orion.Cloud.Aws.TransitGateway`
- `Orion.Cloud.Aws.TransitGatewayAttachment`
- `Orion.Cloud.Aws.TransitGatewayStatistics`
- `Orion.Cloud.Azure.FunctionApp`
- `Orion.Cloud.Azure.FunctionAppStatistics`
- `Orion.Cloud.Azure.StorageAccountBlobContainer`
- `Orion.Cloud.Azure.StorageAccountBlobService`
- `Orion.Cloud.Azure.StorageAccountBlobServiceStatistics`
- `Orion.Cloud.Azure.StorageAccountTable`
- `Orion.Cloud.Azure.StorageAccountTableService`
- `Orion.Cloud.Azure.StorageAccountTableServiceStatistics`
- `Orion.Cloud.Azure.VirtualHub`
- `Orion.Cloud.Azure.VirtualHubConnection`
- `Orion.Cloud.Azure.VirtualHubStatistics`
- `Orion.Cloud.Azure.VirtualHubSubEntities`
- `Orion.Cloud.Azure.VirtualMachineBackupStatus`
- `Orion.Cloud.Azure.VirtualWan`
- `Orion.Cloud.CostEntities`
- `Orion.Cloud.Gcp.BigQueryDataset`
- `Orion.Cloud.Gcp.CostManagement`
- `Orion.Cloud.Gcp.CostManagementStatistics`
- `Orion.Cloud.Gcp.GkeCluster`
- `Orion.Cloud.Gcp.GkeClusterStatistics`
- `Orion.Cloud.Gcp.GkeContainer`
- `Orion.Cloud.Gcp.GkeContainerResourceFormatter`
- `Orion.Cloud.Gcp.GkeContainerStatistics`
- `Orion.Cloud.Gcp.GkeNode`
- `Orion.Cloud.Gcp.GkeNodeStatistics`
- `Orion.Cloud.Gcp.GkePod`
- `Orion.Cloud.Gcp.GkePodStatistics`
- `Orion.Cloud.Gcp.LBBackendService`
- `Orion.Cloud.Gcp.LBBackendServiceStatistics`
- `Orion.Cloud.Gcp.LBForwardingRule`
- `Orion.Cloud.Gcp.LBForwardingRuleStatistics`
- `Orion.Cloud.Gcp.LBTargetProxy`
- `Orion.Cloud.Gcp.LBUrlMap`
- `Orion.Cloud.VirtualNetworkAddressSpaces`
- `Orion.ELB.NodeExclusions`
- `Orion.ELB.NodeReassignments`
- `Orion.EngineLoadBalancingEnabledStatusChanged`
- `Orion.EngineLoadBalancingExecution`
- `Orion.EngineLoadBalancingNodeExcludedStatusChanged`
- `Orion.EngineLoadBalancingNodeReassigned`
- `Orion.FeatureOnboarding.Actions`
- `Orion.FeatureOnboarding.Buttons`
- `Orion.FeatureOnboarding.Capabilities`
- `Orion.FeatureOnboarding.Categories`
- `Orion.FeatureOnboarding.Features`
- `Orion.FeatureOnboarding.Groups`
- `Orion.FeatureOnboarding.UsageDefinitions`
- `Orion.FeatureOnboarding.WhatsNew`
- `Orion.IpSla.OperationStats`
- `Orion.Licensing.ElementSubtypes`
- `Orion.Licensing.ElementTypes`
- `Orion.Licensing.UtilizationDetails`
- `Orion.Licensing.UtilizationSummary`
- `Orion.Maps.HiddenTopologyConnections`
- `Orion.NPM.InterfacesDashboard`
- `Orion.NPM.InterfacesRelationship`
- `Orion.NPM.InterfacesRelationshipType`
- `Orion.NexusVpc.Dashboard`
- `Orion.NodesOtherStatusIds`
- `Orion.PollingErrors`
- `Orion.Routing.NeighborsFlapCount`
- `Orion.Web.LegacyModules.RollupStatusInfo`

**PlatformBridge** (1)

- `PlatformBridge.Info`

**PlatformConnect** (3)

- `PlatformConnect.Info`
- `PlatformConnect.Status`
- `PlatformConnect.Wizard`

**System** (1)

- `System.SubscriptionIncludedProperty`

**UamsClient** (2)

- `UamsClient.PlatformConnectInfo`
- `UamsClient.PlatformConnectWizard`

---

Regenerate with:

```bash
python3 tools/diff_schema.py --from 2025.4 --to 2026.2 --markdown
```

Neither version's schema is the authority for a specific server. Confirm against your own with `Metadata.Entity` and `Metadata.VerbArgument`; see [../../scripts/swql/08-schema-introspection.swql](../../scripts/swql/08-schema-introspection.swql).

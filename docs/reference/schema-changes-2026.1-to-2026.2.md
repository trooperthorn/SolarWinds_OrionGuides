<!-- GENERATED FILE. Do not edit by hand.
     Produced by tools/diff_schema.py. -->

# Schema changes: 2026.1 to 2026.2

What changed in the SWIS schema between these two platform versions, and which of those changes can break code that already works.

Read the removals first. Additions cannot break anything you have already written; removals and reordered verb arguments can, and the second kind fails quietly because Invoke sends a positional array with no names in it.

## Summary

| Change | Count |
| --- | ---: |
| Entities added | 53 |
| Entities removed | 4 |
| Entities renamed | 0 |
| Entities otherwise changed | 52 |
| Entities that lost a property | 17 |
| Entities that lost a navigation property | 7 |
| Verbs added | 14 |
| Verbs removed | 24 |
| Verb signatures changed (breaking) | 6 |
| Verb signatures changed (new required argument) | 0 |
| Verb parameter names recased (no caller impact) | 3 |

## Removed entities

4 entities present in 2026.1 are absent from 2026.2. Some are genuine removals; others belong to a module that was restructured. Check each against your own server before concluding it is gone.

- `Cortex.Orion.NetMan.Firewalls.Firewall.Statistics`
- `Cortex.Orion.NetMan.Firewalls.FirewallCentralizedSettings`
- `Cortex.Orion.NetMan.Firewalls.RemoteAccess.Statistics`
- `Cortex.Orion.NetMan.Firewalls.SiteToSiteTunnel.Statistics`

## Verb signature changes that break callers

Invoke arguments are positional. When the order of a shared prefix changes, an existing call still has the right number of arguments and sends them into the wrong slots, so it can fail with a confusing type error or, worse, succeed against the wrong values. Audit every call site for these.

| Entity | Verb | Was | Is now | Why it breaks |
| --- | --- | --- | --- | --- |
| `NCM.OneTimeOperations` | `UpdateOneTimeOperation` | `(id, status, properties)` | `(id, status, scriptContent, reboot)` | positional argument order changed |
| `Orion.Orchestrators.Info` | `AddFortinetFortiManagerNode` | `(engineId, caption, hostname, username, password, clientId)` | `(engineId, caption, hostname, organizationId, organizationName, tokenUrl, username, password, appId, apiPassword, clientId, token)` | positional argument order changed |
| `UamsClient.PlatformConnectWizard` | `ActivateBizAppsTenant` | `(request)` | `()` | argument removed |
| `UamsClient.PlatformConnectWizard` | `CheckAPIAccessTokenValidity` | `(token, swoUrl)` | `()` | argument removed |
| `UamsClient.PlatformConnectWizard` | `GetIngestionTokenByAPIAccess` | `(token, swoUrl)` | `()` | argument removed |
| `UamsClient.PlatformConnectWizard` | `SetAccessToken` | `(swoken)` | `()` | argument removed |

## Entities that lost properties or navigation properties

A query selecting a removed property fails outright. A query selecting a removed navigation property fails the same way, but a report built on one may simply go empty, which is easier to miss.

| Entity | Removed properties | Removed navigations |
| --- | --- | --- |
| `Cortex.Orion.NetMan.Firewalls.Firewall` | `AgentId`, `AgentOsType`, `EngineId`, `PollInterval`, `PollState`, `PollState_Value`, `RelatedFirewallCentralizedSettings`, `RequestInventory` | `FirewallCentralizedSettings`, `Statistics` |
| `Cortex.Orion.NetMan.Firewalls.RemoteAccess` | `AgentId`, `AgentOsType`, `EngineId`, `PollState`, `PollState_Value`, `RequestInventory` | `Statistics` |
| `Cortex.Orion.NetMan.Firewalls.SiteToSiteTunnel` | `AgentId`, `AgentOsType`, `EngineId`, `PollState`, `PollState_Value`, `RequestInventory` | `Statistics` |
| `NCM.OneTimeOperations` | `Properties` |  |
| `Orion.Cloud.Accounts` |  | `AzureStorageAccount` |
| `Orion.Cloud.Aws.CostManagement` | `Name` |  |
| `Orion.Cloud.Azure.StorageAccount` |  | `RelatedCloudAccount` |
| `Orion.Cloud.Azure.StorageAccountStatistics` | `ObservationTimestamp`, `Weight` |  |
| `Orion.Fortigate.HighAvailability` |  | `PrimaryNode` |
| `Orion.Licensing.UtilizationSummary` | `LicenseSizeNormalized`, `RemainingNormalized` |  |
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

## Properties whose type changed

These do not fail a SWQL query, but they can fail a typed client that binds the column to a field.

| Entity | Property | Was | Is now |
| --- | --- | --- | --- |
| `Orion.IpSla.VoipGatewaySipStats` | `SipStatsErrClient` | `System.Int32` | `System.Int64` |
| `Orion.IpSla.VoipGatewaySipStats` | `SipStatsErrServer` | `System.Int32` | `System.Int64` |
| `Orion.IpSla.VoipGatewaySipStats` | `SipStatsGlobalFail` | `System.Int32` | `System.Int64` |
| `Orion.IpSla.VoipGatewaySipStats` | `SipStatsRedirect` | `System.Int32` | `System.Int64` |
| `Orion.IpSla.VoipGatewaySipStats` | `SipStatsRetry` | `System.Int32` | `System.Int64` |
| `Orion.IpSla.VoipGatewaySipStats` | `SipStatsSuccess` | `System.Int32` | `System.Int64` |
| `Orion.Licensing.UtilizationSummary` | `Used` | `System.Double` | `System.Int32` |
| `Orion.MemoryMultiLoad` | `Index` | `System.Int16` | `System.Int32` |
| `Orion.MemoryMultiLoadCurrent` | `Index` | `System.Int16` | `System.Int32` |

## New verbs

14 verbs are available in 2026.2 that were not in 2026.1.

- `Cli.CliSessionSettings`: `ValidateCliCredentialsExtended`
- `Cortex.Orion.NetMan.Firewalls.Firewall`: `AssignPaloAltoPolling`, `TestFirewallCredentials`
- `IPAM.DhcpDnsManagement`: `AddDhcpScope`, `CreateIpv6Reservation`, `RemoveIpv6Reservation`
- `IPAM.SubnetManagement`: `AddIpRange`, `AddIpv6Range`, `RemoveIpRange`
- `Orion.HardwareHealth.BMC.Controllers`: `TestBmcConnection`
- `Orion.NPM.Interfaces`: `SetBandwidth`
- `Orion.Orchestrators.Info`: `ValidateFortinetFortiManagerCloudApiAuthentication`, `ValidateFortinetFortiManagerTokenAuthentication`, `ValidateFortinetFortiManagerUsernamePasswordAuthentication`

## New entities

53 entities are new in 2026.2.

**ContentModel** (1)

- `ContentModel.OrionNodes`

**Orion** (48)

- `Orion.Azure.CostExpandedStatistics`
- `Orion.Cloud.Aws.ElasticBeanstalkEnvironment`
- `Orion.Cloud.Aws.ElasticBeanstalkEnvironmentNode`
- `Orion.Cloud.Aws.ElasticBeanstalkEnvironmentNodeStatistics`
- `Orion.Cloud.Aws.ElasticBeanstalkEnvironmentStatistics`
- `Orion.Cloud.Aws.TransitGateway`
- `Orion.Cloud.Aws.TransitGatewayAttachment`
- `Orion.Cloud.Aws.TransitGatewayStatistics`
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
- `Orion.Cloud.VirtualNetworkAddressSpaces`
- `Orion.ELB.NodeExclusions`
- `Orion.ELB.NodeReassignments`
- `Orion.EngineLoadBalancingEnabledStatusChanged`
- `Orion.EngineLoadBalancingNodeExcludedStatusChanged`
- `Orion.FeatureOnboarding.Actions`
- `Orion.FeatureOnboarding.Buttons`
- `Orion.FeatureOnboarding.Capabilities`
- `Orion.FeatureOnboarding.Categories`
- `Orion.FeatureOnboarding.Features`
- `Orion.FeatureOnboarding.Groups`
- `Orion.FeatureOnboarding.UsageDefinitions`
- `Orion.FeatureOnboarding.WhatsNew`
- `Orion.IpSla.OperationStats`
- `Orion.NPM.InterfacesDashboard`
- `Orion.Web.LegacyModules.RollupStatusInfo`

**PlatformBridge** (1)

- `PlatformBridge.Info`

**PlatformConnect** (3)

- `PlatformConnect.Info`
- `PlatformConnect.Status`
- `PlatformConnect.Wizard`

---

Regenerate with:

```bash
python3 tools/diff_schema.py --from 2026.1 --to 2026.2 --markdown
```

Neither version's schema is the authority for a specific server. Confirm against your own with `Metadata.Entity` and `Metadata.VerbArgument`; see [../../scripts/swql/08-schema-introspection.swql](../../scripts/swql/08-schema-introspection.swql).

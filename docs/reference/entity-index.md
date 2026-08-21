<!-- GENERATED FILE. Do not edit by hand.
     Produced by tools/build_reference_docs.py from data/schema/2026.2/.
     Regenerate with: make docs-reference -->

# Entity index

Every entity published in the SolarWinds Information Service schema for platform version **2026.2**: 2067 entities across 16 namespaces, holding 19328 properties.

The columns are worth reading carefully. **Base** is the entity this one inherits from, and inherited properties are queryable on the child even though they are not listed on its own page. **Ops** are the operations the entity declares: an entity without `create` cannot be created through CRUD no matter how the request is shaped. **P/R/V** counts properties, relationships and verbs, which is a quick way to tell a substantial entity from a thin lookup table.

To see any entity in full, including its properties and verb signatures:

```bash
python3 tools/schema_query.py show Orion.Nodes
```

## Namespaces

| Namespace | Entities | Jump |
| --- | ---: | --- |
| `Orion` | 1705 | [Orion](#orion) |
| `IPAM` | 77 | [IPAM](#ipam) |
| `NCM` | 72 | [NCM](#ncm) |
| `Cortex` | 69 | [Cortex](#cortex) |
| `Cirrus` | 57 | [Cirrus](#cirrus) |
| `System` | 29 | [System](#system) |
| `DPA` | 18 | [DPA](#dpa) |
| `Metadata` | 11 | [Metadata](#metadata) |
| `ContentModel` | 8 | [ContentModel](#contentmodel) |
| `Cli` | 5 | [Cli](#cli) |
| `UamsClient` | 5 | [UamsClient](#uamsclient) |
| `PlatformConnect` | 3 | [PlatformConnect](#platformconnect) |
| `SWISf` | 3 | [SWISf](#swisf) |
| `SOC` | 2 | [SOC](#soc) |
| `Vdc` | 2 | [Vdc](#vdc) |
| `PlatformBridge` | 1 | [PlatformBridge](#platformbridge) |

## Orion

1705 entities.

| Entity | Base | Ops | P/R/V | Summary |
| --- | --- | --- | --- | --- |
| `Orion.ADM.NodeInventory` | `System.ManagedEntity` | - | 13/1/6 | This entity represents inventory of nodes. |
| `Orion.ADM.PollNowIndication` | `System.Indication` | - | 4/0/0 | This entity represents indication information for Scheduled poll now. |
| `Orion.ADM.ScheduleEnableIndication` | `System.Indication` | - | 3/0/0 |  |
| `Orion.AIIM.AlertConditionEntityProperty` | `System.Entity` | r | 6/0/0 | This entity provides a list of the properties used in the conditions defining each Orion alert. |
| `Orion.AIIM.AnomalyBasedAlertSettings` | `System.Entity` | c,d,r,u | 3/0/0 | This entity saves Anomaly Based Alerts settings. |
| `Orion.AIIM.AnomalyBasedAlertSourcesLimited` | `System.Entity` | r | 4/0/0 | This entity provides list of managed entities and metrics used in Anomaly Based Alerts. |
| `Orion.AIIM.AnomalyHistory` | `Orion.MixedObjectType` | c,d,r | 18/0/0 | This entity presents detected anomalies |
| `Orion.AIIM.BasicMetricMetadata` | `System.Entity` | c,d,r,u | 8/0/0 | This entity provides a list of Basic KPI Metrics, Thresholds and Entity Properties, this is a link table. |
| `Orion.AIIM.IssueHistoryLimited` | `System.Entity` | r | 13/0/0 | This entity provides the historical snapshots of Orion Issues, automatically taken while the issue is active.… |
| `Orion.AIIM.IssuesLimited` | `System.Entity` | r | 15/0/0 | This entity provides root information for an Orion Issue created by the AIIM BusinessLayer. Account limitatio… |
| `Orion.AIIM.OccurrencesLimited` | `System.Entity` | r | 18/0/0 | This entity provides a list of the event occurrences that contributed to this issue. Account limitation is ap… |
| `Orion.AIIM.Orion_NPM_Interfaces_Anomalies` | `Orion.MixedObjectType` | c,d,r,u | 25/1/0 |  |
| `Orion.AIIM.Orion_Nodes_Anomalies` | `Orion.MixedObjectType` | c,d,r,u | 17/1/0 |  |
| `Orion.AIIM.Orion_VIM_Clusters_Anomalies` | `Orion.MixedObjectType` | c,d,r,u | 9/1/0 |  |
| `Orion.AIIM.Orion_VIM_Hosts_Anomalies` | `Orion.MixedObjectType` | c,d,r,u | 13/1/0 |  |
| `Orion.AIIM.Orion_VIM_VirtualMachines_Anomalies` | `Orion.MixedObjectType` | c,d,r,u | 25/1/0 |  |
| `Orion.AIIM.Orion_Volumes_Anomalies` | `Orion.MixedObjectType` | c,d,r,u | 5/1/0 |  |
| `Orion.AIIM.SourceStatus` | `Orion.MixedObjectType` | c,d,r,u | 8/0/0 | This entity provides current status of anomaly detection for a specific ManagedEntity. |
| `Orion.AIIM.UsageStatistics` | `System.Entity` | c,d,r,u | 5/0/0 | This entity provides a simple statistics about resource usage. |
| `Orion.APIPoller.ApiPoller` | `System.ManagedEntity` | c,d,i,r,u | 14/6/3 | This entity presents Api Poller properties |
| `Orion.APIPoller.ApiPoller.Metrics` | `System.StatisticsEntity` | r | 3/1/0 | This entity presents Api Poller metrics |
| `Orion.APIPoller.PollingConfiguration` | `System.Entity` | c,d,i,r,u | 2/0/0 | This entity presents Api Poller Polling Configuraton properties |
| `Orion.APIPoller.RequestDetails` | `System.Entity` | c,d,i,r,u | 11/4/0 | This entity presents request details used by Api Poller |
| `Orion.APIPoller.RequestHeader` | `System.Entity` | c,d,i,r,u | 4/1/0 | This entity presents request header used by Api Poller |
| `Orion.APIPoller.RequestVariable` | `System.Entity` | c,d,i,r,u | 4/1/0 | This entity presents request variable used by Api Poller |
| `Orion.APIPoller.StringToNumberTransformationRule` | `System.Entity` | c,d,i,r,u | 4/1/0 | This entity presents string to number transformation rule used by Api Poller |
| `Orion.APIPoller.Templates` | `System.Entity` | c,d,i,r,u | 12/1/3 | This entity presents template details used by API Poller |
| `Orion.APIPoller.ValueToMonitor` | `System.ManagedEntity` | c,d,i,r,u | 18/4/0 | This entity presents value to monitor details used by Api Poller |
| `Orion.APIPoller.ValueToMonitor.Metrics` | `System.StatisticsEntity` | r | 6/1/0 | This entity presents value to monitor metrics used by Api Poller |
| `Orion.APM.ActiveDirectory.Application` | `Orion.APM.Application` | - | 6/3/3 | This entity represents Active Directory BlackBox Application. |
| `Orion.APM.ActiveDirectory.DomainController` | `System.Entity` | - | 9/1/0 | This entity represents Active Directory Domain Controller. |
| `Orion.APM.ActiveDirectory.DomainTrust` | `System.Entity` | - | 16/0/0 | This entity represents Active Directory trust information. |
| `Orion.APM.ActiveDirectory.Link` | `System.Entity` | - | 2/1/0 | This entity represents Active Directory Link. |
| `Orion.APM.ActiveDirectory.NamingContext` | `Orion.APM.ApplicationItem` | - | 11/3/0 | This entity represents Active Directory Naming Context information. |
| `Orion.APM.ActiveDirectory.NamingContextStatus` | `System.StatisticsEntity` | - | 6/1/0 | This entity represents Active Directory Naming Context Status information. |
| `Orion.APM.ActiveDirectory.Replication` | `System.Entity` | - | 14/3/0 | This entity represents Active Directory replication information. |
| `Orion.APM.ActiveDirectory.Site` | `Orion.APM.ApplicationItem` | - | 11/4/0 | This entity represents Active Directory site. |
| `Orion.APM.ActiveDirectory.SiteStatus` | `System.StatisticsEntity` | - | 6/1/0 | This entity presents details of Active Directory site's status. |
| `Orion.APM.ActiveDirectory.Subnet` | `System.Entity` | - | 3/1/0 | This entity represents Active Directory subnet. |
| `Orion.APM.Application` | `System.ManagedEntity` | i,r,u | 25/18/7 | This entity presents all applications. |
| `Orion.APM.ApplicationAlert` | `System.Entity` | - | 12/1/0 | This entity presents all applications. Used in alerting |
| `Orion.APM.ApplicationCustomProperties` | `System.CustomPropertiesEntity` | i,r,u | 0/1/4 | This entity presents application custom properties. |
| `Orion.APM.ApplicationGroup` | `System.Entity` | - | 2/0/0 | This entity groups applications. |
| `Orion.APM.ApplicationItem` | `System.ManagedEntity` | - | 5/0/0 | This entity represents any significant AppInsight application's entity (e.g. SQL Database). |
| `Orion.APM.ApplicationSettings` | `System.Entity` | c,r,u | 5/0/0 | This entity represents application settings. |
| `Orion.APM.ApplicationStatus` | `System.StatisticsEntity` | - | 8/1/0 | This entity presents application status. |
| `Orion.APM.ApplicationTcpConnection` | `System.ManagedEntity` | c,d,i,r,u | 38/11/0 | This entity aggregates application connections from one process to another. |
| `Orion.APM.ApplicationTemplate` | `System.Entity` | i,r,u | 10/1/6 | This entity presents application template. |
| `Orion.APM.ApplicationTemplateSettings` | `System.Entity` | r,u | 5/0/0 | This entity represents application template settings. |
| `Orion.APM.ApplicationWebUri` | `System.ExtensionEntity` | - | 3/1/0 | This entity presents application web Uri. |
| `Orion.APM.ApplicationsOtherStatusCount` | `System.Entity` | - | 2/0/0 | Calculates the number of applications in other status categories for Application Status KPI widget in New Hom… |
| `Orion.APM.ChartEvidence` | `System.ExtensionEntity` | - | 11/1/0 | This entity presents chart evidence statistic. |
| `Orion.APM.ChartEvidence2` | `System.StatisticsEntity` | - | 7/1/0 | This entity presents chart evidence statistic. |
| `Orion.APM.Component` | `System.ManagedEntity` | d,i,r,u | 22/22/1 | This entity presents component. |
| `Orion.APM.ComponentAlert` | `System.Entity` | - | 29/1/0 | This entity presents component. Used in alerting. |
| `Orion.APM.ComponentAlertThresholds` | `System.Entity` | - | 18/1/0 | This entity presents component thresholds. Used in alerting. |
| `Orion.APM.ComponentCategory` | `System.Entity` | - | 3/1/0 | This entity represents component category. |
| `Orion.APM.ComponentDefinition` | `System.Entity` | - | 4/1/0 | This entity presents component definition. |
| `Orion.APM.ComponentDefinitionCategory` | `System.Entity` | - | 2/0/0 | This entity represents component definition category. |
| `Orion.APM.ComponentDefinitionCategoryMembership` | `System.Entity` | - | 2/0/0 | This entity represents component definition category membership. |
| `Orion.APM.ComponentDefinitionSetting` | `System.Entity` | - | 5/0/0 | This entity represents component definition settings. |
| `Orion.APM.ComponentExt` | `System.Entity` | - | 9/0/0 | This entity presents extended component. |
| `Orion.APM.ComponentSetting` | `System.Entity` | c,r,u | 5/0/0 | This entity represents component settings. |
| `Orion.APM.ComponentStatus` | `System.StatisticsEntity` | - | 8/5/0 | This entity presents component status. |
| `Orion.APM.ComponentTemplate` | `System.Entity` | r,u | 10/1/0 | This entity represents component template. |
| `Orion.APM.ComponentTemplateSetting` | `System.Entity` | r,u | 5/0/0 | This entity represents component template settings. |
| `Orion.APM.ComponentTypeMappingStrategy` | `System.Entity` | - | 3/0/0 |  |
| `Orion.APM.ComponentWebUri` | `System.ExtensionEntity` | - | 3/1/0 | This entity presents component web Uri. |
| `Orion.APM.Config` | `System.Entity` | - | 3/0/0 | This entity represents SAM configuration settings. |
| `Orion.APM.CurrentApplicationStatus` | `System.StatisticsEntity` | - | 6/1/0 | This entity presents current application status. |
| `Orion.APM.CurrentComponentStatus` | `System.StatisticsEntity` | - | 13/1/0 | This entity presents component status. |
| `Orion.APM.CurrentStatistics` | `System.Entity` | - | 24/1/0 | This entity presents component statistics. |
| `Orion.APM.DependencyTcpStatistics` | `System.ManagedEntity` | c,d,i,r,u | 19/5/0 |  |
| `Orion.APM.DynamicEvidence` | `System.ExtensionEntity` | - | 21/1/0 | This entity presents dynamic evidence statistics. Used to present script monitors statistics. |
| `Orion.APM.DynamicEvidenceChart` | `System.StatisticsEntity` | - | 11/1/0 | This entity presents dynamic evidence statistics. Used in charts. |
| `Orion.APM.DynamicEvidenceColumnSchema` | `System.ExtensionEntity` | - | 31/0/0 | This entity presents dynamic evidence column schema. Used to present script monitors output. |
| `Orion.APM.DynamicEvidenceCurrent` | `System.ExtensionEntity` | - | 6/0/0 | This entity presents dynamic evidence last polled data. |
| `Orion.APM.DynamicEvidenceDetail` | `System.ExtensionEntity` | - | 6/0/0 | This entity presents dynamic evidence statistic details. |
| `Orion.APM.DynamicEvidenceDetailData` | `System.ExtensionEntity` | - | 5/0/0 | This entity presents dynamic evidence detail data. |
| `Orion.APM.ErrorCode` | `System.Entity` | - | 3/0/0 | This entity represents SAM error code. |
| `Orion.APM.EventType` | `System.Entity` | - | 1/0/0 | This entity represents SAM event types. |
| `Orion.APM.Exchange.Application` | `Orion.APM.Application` | - | 8/3/2 | This entity presents the Exchange application information. |
| `Orion.APM.Exchange.ApplicationAlert` | `System.Entity` | - | 8/1/0 | This entity presents the exchange application information. Used in alerting. |
| `Orion.APM.Exchange.Database` | `System.ManagedEntity` | - | 25/5/0 | This entity presents the mailbox database information. |
| `Orion.APM.Exchange.DatabaseAlert` | `System.Entity` | - | 18/1/0 | This entity presents the mailbox database information. Used in alerting. |
| `Orion.APM.Exchange.DatabaseAvailabilityGroup` | `System.Entity` | - | 8/0/0 | This entity presents the Exchange database availability group information. |
| `Orion.APM.Exchange.DatabaseCopy` | `Orion.APM.ApplicationItem` | - | 21/7/0 | This entity presents the mailbox database copy information. |
| `Orion.APM.Exchange.DatabaseCopyAlert` | `System.Entity` | - | 19/1/0 | This entity presents the mailbox database copy information. Used in alerting. |
| `Orion.APM.Exchange.DatabaseCopyStatistics` | `System.StatisticsEntity` | - | 8/1/0 | This entity presents the database copy statistics. |
| `Orion.APM.Exchange.DatabaseFile` | `System.Entity` | - | 13/2/0 | This entity presents the database file information. |
| `Orion.APM.Exchange.DatabaseFileStatistics` | `System.StatisticsEntity` | - | 6/1/0 | This entity presents the database file statistics. |
| `Orion.APM.Exchange.DatabaseStatistics` | `System.StatisticsEntity` | - | 4/1/0 | This entity presents the database statistics. |
| `Orion.APM.Exchange.Domain` | `System.Entity` | - | 2/0/0 | This entity presents the Exchange server domain information. |
| `Orion.APM.Exchange.EntityStatistics` | `System.ExtensionEntity` | - | 9/0/0 | This entity presents the exchange entity statistics. |
| `Orion.APM.Exchange.Mailbox` | `System.ManagedEntity` | - | 44/2/0 | This entity presents the mailbox information. |
| `Orion.APM.Exchange.MailboxAccountDetails` | `System.StatisticsEntity` | - | 10/0/0 | This entity presents the mailbox account details. |
| `Orion.APM.Exchange.MailboxAlert` | `System.Entity` | - | 12/1/0 | This entity presents the mailbox information. Used in alerting. |
| `Orion.APM.Exchange.MailboxStatistics` | `System.StatisticsEntity` | - | 9/0/0 | This entity presents the mailbox statistics. |
| `Orion.APM.Exchange.ReplicationStatus` | `System.Entity` | - | 7/2/0 | This entity presents the Exchange server replication status information. |
| `Orion.APM.Exchange.ReplicationStatusAlert` | `System.Entity` | - | 6/1/0 | This entity presents the Exchange server replication status information. Used in alerting. |
| `Orion.APM.Exchange.SyncedDevices` | `System.Entity` | - | 5/0/0 | This entity presents the exchange synced devices. |
| `Orion.APM.Exchange.TransactionLogDir` | `System.Entity` | - | 8/1/0 | This entity presents the transaction log directory. |
| `Orion.APM.ExternalSetting` | `System.Entity` | - | 2/0/0 | This entity represents external settings for components. |
| `Orion.APM.GenericApplication` | `Orion.APM.Application` | - | 1/0/0 | This entity presents common applications(black box applications are filtered out). |
| `Orion.APM.HistoricalCPULoad` | `System.StatisticsEntity` | - | 9/1/0 | This entity represents historical data for CPU load. |
| `Orion.APM.HistoricalIOOperations` | `System.StatisticsEntity` | - | 12/1/0 | This entity represents historical data for IO operations. |
| `Orion.APM.HistoricalMemory` | `System.StatisticsEntity` | - | 18/1/0 | This entity represents historical data for memory usage. |
| `Orion.APM.IIS.Application` | `Orion.APM.Application` | - | 3/2/2 | This entity presents SAM application. |
| `Orion.APM.IIS.ApplicationPool` | `Orion.APM.ApplicationItem` | - | 25/4/3 | This entity presents IIS application pool. |
| `Orion.APM.IIS.ApplicationPoolStatus` | `System.StatisticsEntity` | - | 3/1/0 | This entity presents details of application pool's status. |
| `Orion.APM.IIS.Request` | `System.Entity` | - | 8/2/0 | This entity presents request to Site. |
| `Orion.APM.IIS.RequestDetails` | `System.Entity` | - | 11/1/0 | This entity presents details of the request. |
| `Orion.APM.IIS.Site` | `Orion.APM.ApplicationItem` | - | 25/8/3 | This entity presents IIS site. |
| `Orion.APM.IIS.SiteBinding` | `System.Entity` | - | 16/1/0 | This entity presents details of site's bindings. |
| `Orion.APM.IIS.SiteConnectionStatistics` | `System.StatisticsEntity` | - | 5/1/0 | This entity presents historical statistics of site connections. |
| `Orion.APM.IIS.SiteDirectory` | `System.Entity` | - | 11/2/0 | This entity presents details of site's file's. |
| `Orion.APM.IIS.SiteDirectoryStatistics` | `System.Entity` | - | 7/1/0 | This entity presents historical statistics of site's directory. |
| `Orion.APM.IIS.SiteLogDirectory` | `System.Entity` | - | 12/2/0 | This entity presents details of site's log file's. |
| `Orion.APM.IIS.SiteLogDirectoryStatistics` | `System.Entity` | - | 7/1/0 | This entity presents historical statistics of site's logs directory. |
| `Orion.APM.IIS.SiteStatus` | `System.StatisticsEntity` | - | 3/1/0 | This entity presents details of site's status. |
| `Orion.APM.IIS.WorkerProcess` | `System.Entity` | - | 12/1/0 | This entity presents details of worker process. |
| `Orion.APM.LicenseInfo` | `System.Entity` | - | 2/0/4 | This entity presents License Information. |
| `Orion.APM.MultipleStatisticData` | `System.Entity` | - | 5/1/0 | This entity presents multiple statistic data. |
| `Orion.APM.NodeChildStatusApplications` | `Orion.NodeChildStatusContributors` | - | 0/0/0 | List of all node child entities that affect current node (child) status |
| `Orion.APM.NodeRebooted` | `System.Indication` | - | 2/0/0 | This entity presents the indication information for rebooted node. |
| `Orion.APM.NodeToNodeLink` | `System.ManagedEntity` | c,d,i,r,u | 17/5/0 | This entity aggregates all connections between two nodes. |
| `Orion.APM.NodeToNodeLinkLatencyThreshold` | `Orion.APM.NodeToNodeLinkThresholds` | - | 0/1/0 |  |
| `Orion.APM.NodeToNodeLinkPacketLossThreshold` | `Orion.APM.NodeToNodeLinkThresholds` | - | 0/1/0 |  |
| `Orion.APM.NodeToNodeLinkThresholds` | `Orion.Thresholds` | - | 1/0/0 |  |
| `Orion.APM.PortEvidence` | `System.ExtensionEntity` | - | 21/1/0 | This entity presents port evidence statistics. |
| `Orion.APM.PortEvidenceChart` | `System.StatisticsEntity` | - | 12/1/0 | This entity presents port evidence statistics. Used in charts. |
| `Orion.APM.ProcessEvidence` | `System.ExtensionEntity` | - | 28/1/0 | This entity presents process evidence statistics. |
| `Orion.APM.ProcessEvidenceChart` | `System.StatisticsEntity` | - | 27/1/0 | This entity presents process evidence statistics. Used in charts. |
| `Orion.APM.ProcessTerminated` | `System.Indication` | - | 3/0/0 | This entity presents the indication information for terminated process. |
| `Orion.APM.ReportApplicationChanged` | `System.Indication` | - | 0/0/0 | This entity presents indication information for application. |
| `Orion.APM.ResponseTime` | `System.StatisticsEntity` | - | 8/1/0 | This entity represents response time. |
| `Orion.APM.ServerManagement` | `System.Entity` | - | 0/0/4 | This entity represents server management verbs. |
| `Orion.APM.ServiceStateChanged` | `System.Indication` | - | 4/0/0 | This entity presents the indication information for windows service state. |
| `Orion.APM.SqlClusterNode` | `System.Entity` | - | 3/1/0 | This entity presents SQL cluster node. |
| `Orion.APM.SqlConnection` | `System.Entity` | - | 15/0/0 | This entity presents SQL connection. |
| `Orion.APM.SqlDatabase` | `Orion.APM.ApplicationItem` | - | 18/10/0 | This entity presents SQL database. |
| `Orion.APM.SqlDatabaseAlert` | `System.Entity` | - | 19/2/0 | This entity presents SQL database. Used in alerting. |
| `Orion.APM.SqlDatabaseFile` | `System.Entity` | - | 20/3/0 | This entity presents SQL database file information. |
| `Orion.APM.SqlDatabaseFileAlert` | `System.Entity` | - | 26/2/0 | This entity presents SQL database file. Used in alerting. |
| `Orion.APM.SqlDatabaseFileGroup` | `System.Entity` | - | 4/1/0 | This entity presents SQL database file group information. |
| `Orion.APM.SqlDatabaseFileStatistic` | `System.StatisticsEntity` | - | 5/1/0 | This entity presents SQL database file statistic. |
| `Orion.APM.SqlDatabaseMirroring` | `System.Entity` | - | 6/1/0 | This entity presents SQL database mirroring information. |
| `Orion.APM.SqlDatabaseStatus` | `System.StatisticsEntity` | - | 4/1/0 | This entity presents SQL database status. |
| `Orion.APM.SqlIndex` | `System.Entity` | - | 11/1/0 | This entity presents SQL index. |
| `Orion.APM.SqlJobInfo` | `System.Entity` | - | 8/2/0 | This entity presents SQL agent job information. |
| `Orion.APM.SqlJobInfoAlert` | `System.Entity` | - | 8/1/0 | This entity presents SQL agent job information. Used in alerting. |
| `Orion.APM.SqlQuery` | `System.Entity` | - | 21/2/0 | This entity presents SQL query information. |
| `Orion.APM.SqlQueryAlert` | `System.Entity` | - | 19/2/0 | This entity presents SQL query information. Used in alerting. |
| `Orion.APM.SqlServerApplication` | `Orion.APM.Application` | - | 5/4/0 | This entity presents AppInsight for SQL application. |
| `Orion.APM.SqlServerApplicationAlert` | `System.Entity` | - | 12/5/0 | This entity presents AppInsight for SQL application. Used in alerting. |
| `Orion.APM.SqlServerErrorLog` | `System.Entity` | - | 3/0/0 | This entity presents SQL server error log information. |
| `Orion.APM.SqlTable` | `System.Entity` | - | 11/1/0 | This entity presents SQL table information. |
| `Orion.APM.StatisticsUsage` | `System.StatisticsEntity` | - | 10/1/0 | This entity represents statistic usage. |
| `Orion.APM.StatusMetadata` | `System.Entity` | - | 4/0/0 | This entity represents SAM status meta data. |
| `Orion.APM.Tag` | `System.Entity` | - | 2/0/0 | This entity represents template tags. |
| `Orion.APM.TemplateGroupAssignment` | `System.Entity` | - | 8/0/0 | This entity represents connection between Orion group and application templates. |
| `Orion.APM.TemplateGroupAssignmentsBlacklist` | `System.Entity` | - | 2/0/0 | This entity represents set of blacklisted node/template pairs. |
| `Orion.APM.Threshold` | `System.Entity` | - | 18/0/0 | This entity represents SAM thresholds defined for components and their templates |
| `Orion.APM.ThresholdsByComponent` | `System.Entity` | - | 5/0/0 | This entity represents threshold to component relation. |
| `Orion.APM.WindowsEvent` | `System.ExtensionEntity` | - | 11/1/0 | This entity presents windows event. |
| `Orion.APM.WsdlSchema` | `System.Entity` | - | 4/0/0 | This entity represents Wsdl schema. |
| `Orion.APM.Wstm.ScheduledTasksStatus` | `Orion.APM.Application` | - | 1/0/0 | This entity presents the windows scheduler task status. |
| `Orion.APM.Wstm.Task` | `System.Entity` | - | 12/3/0 | This entity presents the windows scheduler task. |
| `Orion.APM.Wstm.TaskAlert` | `System.Entity` | - | 11/1/0 | This entity presents the windows scheduler task. Used in alerting. |
| `Orion.ARM.Dashboard.NodeRisk` | `System.Entity` | - | 12/0/0 |  |
| `Orion.ARM.Dashboard.NodeRiskShares` | `System.Entity` | - | 5/0/0 |  |
| `Orion.ARM.Node` | `System.Entity` | - | 4/0/0 |  |
| `Orion.ARM.NodeAdCommonDetails` | `System.Entity` | - | 23/0/0 |  |
| `Orion.ARM.NodeAdTopOldestLogon` | `System.Entity` | - | 5/0/0 |  |
| `Orion.ARM.NodeRisk` | `System.Entity` | - | 12/0/0 |  |
| `Orion.ARM.NodeRiskShares` | `System.Entity` | - | 5/0/0 |  |
| `Orion.ARM.SecurityNode` | `System.Entity` | - | 4/0/0 |  |
| `Orion.ARM.Settings` | `System.Entity` | - | 0/0/4 |  |
| `Orion.ASA.ConnectionStatistics` | `System.StatisticsEntity` | - | 5/1/0 | Connection statistics for ASA Node |
| `Orion.ASA.Context` | `System.Entity` | - | 5/2/0 |  |
| `Orion.ASA.Favorite` | `System.Entity` | - | 2/0/0 |  |
| `Orion.ASA.FavoriteInterfaceTraffic` | `System.StatisticsEntity` | - | 7/1/0 |  |
| `Orion.ASA.FavoriteInterfaces` | `System.ManagedEntity` | - | 9/2/0 |  |
| `Orion.ASA.Interfaces` | `System.Entity` | - | 6/1/2 |  |
| `Orion.ASA.Node` | `System.ManagedEntity` | - | 27/6/1 | List of ASA Nodes |
| `Orion.ASA.RemoteAccessDetail` | `System.StatisticsEntity` | - | 13/2/0 |  |
| `Orion.ASA.RemoteAccessSessionDetail` | `System.StatisticsEntity` | - | 10/1/0 |  |
| `Orion.ASA.RemoteAccessSessions` | `System.Entity` | - | 23/3/0 | List of Remote Access Tunnels on VPN device |
| `Orion.ASA.System` | `System.Entity` | - | 14/2/0 |  |
| `Orion.AccessDeniedLoadingView` | `System.Indication` | - | 2/0/0 | Occurs when user performs view request without permission |
| `Orion.Accounts` | `System.Entity` | - | 39/5/10 |  |
| `Orion.ActionAssignmentProperties` | `System.Entity` | c,d,i,r,u | 4/1/0 | Action properties per assignment to store values for shared actions |
| `Orion.ActionSchedules` | `System.Entity` | c,d,i,r,u | 2/0/0 | Cross-reference entity between Frequencies and Actions |
| `Orion.Actions` | `System.Entity` | c,d,i,r,u | 7/3/9 |  |
| `Orion.ActionsAssignments` | `System.Entity` | c,d,i,r,u | 5/2/0 |  |
| `Orion.ActionsProperties` | `System.Entity` | c,d,i,r,u | 3/1/0 |  |
| `Orion.ActiveAlerts` | `System.Entity` | - | 16/1/0 |  |
| `Orion.ActiveDiagnosticsDetail` | `System.Entity` | - | 8/0/0 | Active diagnostics results |
| `Orion.ActivePollingErrors` | `System.Entity` | - | 7/1/0 | Entity that displays data about active polling errors |
| `Orion.AgentManagement.Agent` | `System.Entity` | c,d,i,r,u | 37/5/20 | This entity represents an agent. |
| `Orion.AgentManagement.AgentGlobalSettingChanged` | `System.Indication` | - | 3/0/0 |  |
| `Orion.AgentManagement.AgentIndication` | `System.Indication` | - | 6/0/0 |  |
| `Orion.AgentManagement.AgentLogLevelChanged` | `Orion.AgentManagement.AgentIndication` | - | 0/0/0 | Used to track Agent log level changed audit event |
| `Orion.AgentManagement.AgentMachineRebootInitiated` | `Orion.AgentManagement.AgentIndication` | - | 0/0/0 | Used to track Agent machine reboot initiated audit event |
| `Orion.AgentManagement.AgentManualDeploymentInitiated` | `Orion.AgentManagement.AgentIndication` | - | 0/0/0 |  |
| `Orion.AgentManagement.AgentManualDeploymentInitiatedUsingCertificate` | `Orion.AgentManagement.AgentIndication` | - | 0/0/0 |  |
| `Orion.AgentManagement.AgentPlugin` | `System.Entity` | c,d,i,r,u | 6/1/0 | A representation of the plugin on a particular agent. |
| `Orion.AgentManagement.AgentPromoteToRemoteCollectorInitiated` | `Orion.AgentManagement.AgentIndication` | - | 0/0/0 | Used to track Agent promotion to Remote Collector initiated audit event |
| `Orion.AgentManagement.AgentRemoteDeploymentInitiated` | `Orion.AgentManagement.AgentIndication` | - | 0/0/0 |  |
| `Orion.AgentManagement.AgentRemoteDeploymentInitiatedUsingCertificate` | `Orion.AgentManagement.AgentIndication` | - | 0/0/0 |  |
| `Orion.AgentManagement.AgentServiceRestartInitiated` | `Orion.AgentManagement.AgentIndication` | - | 0/0/0 | Used to track Agent service restart initiated audit event |
| `Orion.AgentManagement.AgentUninstallInitiated` | `Orion.AgentManagement.AgentIndication` | - | 0/0/0 |  |
| `Orion.AgentManagement.AgentUninstallInitiatedFromAgent` | `Orion.AgentManagement.AgentIndication` | - | 0/0/0 | Used to track audit event of Agent uninstallation initiated from agent monitored machine |
| `Orion.AgentManagement.InstallPackage` | `System.Entity` | r | 8/0/0 | The types of install packages for Linux distributions |
| `Orion.AgentManagement.Proxy` | `System.Entity` | c,d,i,r,u | 4/0/2 | Proxy settings used in agent to AMS communications. |
| `Orion.AlertActionExecuted` | `Orion.AlertIndication` | - | 0/0/0 | Indication which is sent when alert action is executed (including simulation). |
| `Orion.AlertActive` | `System.Entity` | - | 11/3/4 | Contains information about all currently triggered alerts for individual swis entities. |
| `Orion.AlertActiveObjects` | `System.Entity` | - | 10/1/0 | Contains objects, which triggered active alert. |
| `Orion.AlertCleared` | `Orion.AlertIndication` | - | 2/0/0 | Indication which is sent when user manually clear alert. |
| `Orion.AlertConfigurations` | `System.Entity` | c,d,i,r,u | 20/2/6 |  |
| `Orion.AlertConfigurationsChangeCompleted` | `System.Indication` | - | 2/0/0 | Indication which is sent when alert configuration is added/udated/deleted completely. |
| `Orion.AlertConfigurationsCustomProperties` | `System.CustomPropertiesEntity` | i,r,u | 0/2/5 |  |
| `Orion.AlertDefinitions` | `System.Entity` | c,d,i,r,u | 23/0/0 |  |
| `Orion.AlertHistory` | `System.Entity` | - | 8/1/0 | Information about all actions done for active alerts such as Alert reset, Alert triggered and so on. |
| `Orion.AlertIndication` | `System.Indication` | - | 10/0/0 |  |
| `Orion.AlertObjects` | `System.Entity` | - | 18/7/0 | Serve for tie Orion.AlertHistory and Orion.AlertActive with triggered entity and Orion.AlertConfiguration. |
| `Orion.AlertReset` | `Orion.AlertIndication` | - | 2/0/0 |  |
| `Orion.AlertSchedules` | `System.Entity` | c,d,i,r,u | 2/0/0 |  |
| `Orion.AlertStatus` | `Orion.MixedObjectType` | c,d,i,r,u | 18/0/3 |  |
| `Orion.AlertSuppression` | `System.Entity` | - | 4/0/3 | Contains entities which do not trigger any alerts during the SuppressFrom-SuppressUntil time period. |
| `Orion.AlertTriggered` | `Orion.AlertIndication` | - | 0/0/0 |  |
| `Orion.AlertUpdated` | `Orion.AlertIndication` | - | 4/0/0 |  |
| `Orion.Alerts.SeverityInfo` | `Orion.SeverityInfo` | - | 0/0/0 | Contains Severity Info for alerts. |
| `Orion.AllActiveAlerts.AggregatedSeverity` | `System.Entity` | - | 5/0/0 | Contains All Active Alerts aggregated by their severity. |
| `Orion.AllActiveAlerts.Dashboard` | `System.Entity` | - | 30/2/0 | Contains All Active Alerts dashboard related information. |
| `Orion.AssetInventory.Driver` | `System.Entity` | - | 6/1/0 |  |
| `Orion.AssetInventory.Firmware` | `System.Entity` | - | 5/1/0 |  |
| `Orion.AssetInventory.HardDrive` | `System.Entity` | - | 4/1/0 |  |
| `Orion.AssetInventory.LogicalDrive` | `System.Entity` | - | 11/1/0 |  |
| `Orion.AssetInventory.MemoryModule` | `System.Entity` | - | 5/1/0 |  |
| `Orion.AssetInventory.Monitor` | `System.Entity` | - | 6/1/0 |  |
| `Orion.AssetInventory.NetworkInterface` | `System.Entity` | - | 12/1/0 |  |
| `Orion.AssetInventory.NodeWarrantyAlert` | `System.Entity` | - | 17/1/0 |  |
| `Orion.AssetInventory.OSUpdates` | `System.Entity` | - | 6/1/0 |  |
| `Orion.AssetInventory.OutOfBandManagement` | `System.Entity` | - | 6/1/0 |  |
| `Orion.AssetInventory.Peripherals` | `System.Entity` | - | 3/1/0 |  |
| `Orion.AssetInventory.Polling` | `System.Entity` | - | 4/20/3 |  |
| `Orion.AssetInventory.PollingDescription` | `System.Entity` | - | 5/0/0 |  |
| `Orion.AssetInventory.Processor` | `System.Entity` | - | 9/1/0 |  |
| `Orion.AssetInventory.RemovableMedia` | `System.Entity` | - | 4/1/0 |  |
| `Orion.AssetInventory.ServerInformation` | `System.Entity` | - | 42/1/0 |  |
| `Orion.AssetInventory.Software` | `System.Entity` | - | 5/1/0 |  |
| `Orion.AssetInventory.SoundCard` | `System.Entity` | - | 2/1/0 |  |
| `Orion.AssetInventory.Status` | `System.Entity` | - | 3/0/0 |  |
| `Orion.AssetInventory.StorageController` | `System.Entity` | - | 6/1/0 |  |
| `Orion.AssetInventory.USBController` | `System.Entity` | - | 2/1/0 |  |
| `Orion.AssetInventory.VideoCard` | `System.Entity` | - | 4/1/0 |  |
| `Orion.AssetInventory.WindowsUpdates` | `System.Entity` | - | 9/1/0 |  |
| `Orion.AuditingActionTypes` | `System.Entity` | - | 4/1/0 |  |
| `Orion.AuditingArguments` | `System.Entity` | - | 3/1/0 |  |
| `Orion.AuditingEvents` | `Orion.LogEntity` | - | 10/3/0 |  |
| `Orion.AutoDependencyRoot` | `System.Entity` | c,d,i,r,u | 6/0/0 |  |
| `Orion.Azure.CostExpandedStatistics` | `System.Entity` | - | 12/0/0 |  |
| `Orion.Banners.BannerAccountSettings` | `System.Entity` | c,d,i,r,u | 3/1/2 | Provides details about banner settings for an account. |
| `Orion.Banners.Instances` | `System.Entity` | c,d,i,r,u | 11/1/8 | An Orion banner. |
| `Orion.Batching.ActionExecutionChanged` | `System.Indication` | - | 0/0/0 | Indication reported when action execution state has changed. |
| `Orion.Batching.Actions` | `System.Entity` | - | 9/1/0 | Entity which provides access to all actions which belong to batches. |
| `Orion.Batching.BatchExecutionChanged` | `System.Indication` | - | 0/0/0 | Indication reported when batch execution state has changed. |
| `Orion.Batching.Batches` | `System.Entity` | - | 12/2/0 | Entity which provides access to batches (running, scheduled, finished, cancelled). |
| `Orion.CPULoad` | `System.StatisticsEntity` | - | 12/1/0 |  |
| `Orion.CPULoadAverageByDays` | `Orion.UsageByDays` | - | 1/0/0 | Node CPU load history by days . |
| `Orion.CPUMemoryAverageUsageByDays` | `Orion.UsageByDays` | - | 1/0/0 | Node Memory load history by days . |
| `Orion.CPUMultiLoad` | `System.StatisticsEntity` | - | 6/1/0 |  |
| `Orion.CPUMultiLoadCurrent` | `System.StatisticsEntity` | - | 6/0/0 | This entity contains current multi memory data |
| `Orion.CiscoAci.ApicMembers` | `System.DashboardEntity` | - | 12/0/0 |  |
| `Orion.CiscoAci.ApicThresholds` | `Orion.Thresholds` | - | 0/0/0 |  |
| `Orion.CiscoAci.HealthScoreThreshold` | `Orion.CiscoAci.ApicThresholds` | - | 0/1/0 |  |
| `Orion.CiscoBuffers` | `System.StatisticsEntity` | - | 10/1/0 |  |
| `Orion.Cloud.AccountCounters` | `System.Entity` | - | 3/1/0 | This entity presents the CloudWatch requests statistics for cloud accound in given month. |
| `Orion.Cloud.Accounts` | `System.Entity` | c,d,i,r,u | 11/39/0 | This entity presents the Cloud account information. |
| `Orion.Cloud.Aws.Accounts` | `Orion.Cloud.Accounts` | - | 2/2/0 | This entity presents the Aws Cloud account information. |
| `Orion.Cloud.Aws.BucketStorage` | `System.ManagedEntity` | - | 49/2/0 |  |
| `Orion.Cloud.Aws.BucketStorageStatistics` | `System.StatisticsEntity` | - | 39/1/0 |  |
| `Orion.Cloud.Aws.CostManagement` | `System.ManagedEntity` | - | 16/3/0 |  |
| `Orion.Cloud.Aws.CostManagementStatistics` | `System.StatisticsEntity` | - | 2/1/0 |  |
| `Orion.Cloud.Aws.DirectConnect` | `System.ManagedEntity` | - | 25/2/0 |  |
| `Orion.Cloud.Aws.DirectConnectStatistics` | `System.StatisticsEntity` | - | 10/1/0 |  |
| `Orion.Cloud.Aws.DynamoDb` | `System.ManagedEntity` | - | 24/2/0 |  |
| `Orion.Cloud.Aws.DynamoDbStatistics` | `System.StatisticsEntity` | - | 11/1/0 |  |
| `Orion.Cloud.Aws.Ec2PollingCounters` | `System.Entity` | - | 3/1/0 |  |
| `Orion.Cloud.Aws.ElasticBeanstalkEnvironment` | `System.ManagedEntity` | - | 22/3/0 |  |
| `Orion.Cloud.Aws.ElasticBeanstalkEnvironmentNode` | `System.ManagedEntity` | - | 16/2/0 |  |
| `Orion.Cloud.Aws.ElasticBeanstalkEnvironmentNodeStatistics` | `System.StatisticsEntity` | - | 5/1/0 |  |
| `Orion.Cloud.Aws.ElasticBeanstalkEnvironmentStatistics` | `System.StatisticsEntity` | - | 6/1/0 |  |
| `Orion.Cloud.Aws.ElasticKubernetesCluster` | `System.ManagedEntity` | - | 25/4/0 |  |
| `Orion.Cloud.Aws.ElasticKubernetesClusterStatistics` | `System.StatisticsEntity` | - | 7/1/0 |  |
| `Orion.Cloud.Aws.ElasticKubernetesNode` | `System.Entity` | - | 21/2/0 |  |
| `Orion.Cloud.Aws.ElasticKubernetesNodeGroup` | `System.Entity` | - | 17/1/0 |  |
| `Orion.Cloud.Aws.ElasticKubernetesNodeStatistics` | `System.StatisticsEntity` | - | 8/1/0 |  |
| `Orion.Cloud.Aws.ElasticLoadBalancer` | `System.ManagedEntity` | - | 34/2/0 |  |
| `Orion.Cloud.Aws.ElasticLoadBalancerStatistics` | `System.StatisticsEntity` | - | 23/1/0 |  |
| `Orion.Cloud.Aws.InstanceStatistics` | `Orion.Cloud.InstanceStatistics` | - | 0/0/0 |  |
| `Orion.Cloud.Aws.InstanceThresholds` | `Orion.Cloud.InstanceThresholds` | - | 0/0/0 |  |
| `Orion.Cloud.Aws.Instances` | `Orion.Cloud.Instances` | - | 25/2/3 |  |
| `Orion.Cloud.Aws.LambdaFunction` | `System.ManagedEntity` | - | 34/2/0 |  |
| `Orion.Cloud.Aws.LambdaFunctionStatistics` | `System.StatisticsEntity` | - | 14/1/0 |  |
| `Orion.Cloud.Aws.Management` | `System.Indication` | - | 0/0/0 |  |
| `Orion.Cloud.Aws.Regions` | `Orion.Cloud.Regions` | - | 0/2/1 | This entity presents the AWS region. |
| `Orion.Cloud.Aws.ResourseTags` | `Orion.Cloud.ResourseTags` | - | 0/0/0 | This entity presents the tags associated with AWS resources. |
| `Orion.Cloud.Aws.SqlDatabase` | `System.ManagedEntity` | - | 51/2/0 |  |
| `Orion.Cloud.Aws.SqlDatabaseStatistics` | `System.StatisticsEntity` | - | 93/1/0 |  |
| `Orion.Cloud.Aws.TransitGateway` | `System.ManagedEntity` | - | 27/3/0 |  |
| `Orion.Cloud.Aws.TransitGatewayAttachment` | `System.ManagedEntity` | - | 14/1/0 |  |
| `Orion.Cloud.Aws.TransitGatewayStatistics` | `System.StatisticsEntity` | - | 10/1/0 |  |
| `Orion.Cloud.Aws.UnmonitoredInstances` | `System.Entity` | r | 36/0/0 |  |
| `Orion.Cloud.Aws.VolumeStatistics` | `System.StatisticsEntity` | - | 13/1/0 |  |
| `Orion.Cloud.Aws.VolumeStatus` | `System.Entity` | - | 2/1/0 |  |
| `Orion.Cloud.Aws.Volumes` | `Orion.Cloud.Volumes` | - | 20/3/0 | Cloud volume from Amazon Elastic Compute Cloud Web Service. |
| `Orion.Cloud.Aws.Vpcs` | `Orion.Cloud.Vpcs` | r | 12/1/0 |  |
| `Orion.Cloud.Azure.Accounts` | `Orion.Cloud.Accounts` | - | 1/2/0 | This entity presents the Azure Cloud account information. |
| `Orion.Cloud.Azure.AppService` | `System.ManagedEntity` | - | 28/2/0 |  |
| `Orion.Cloud.Azure.AppServicePlan` | `System.ManagedEntity` | - | 20/3/0 |  |
| `Orion.Cloud.Azure.AppServicePlanStatistics` | `System.StatisticsEntity` | - | 7/1/0 |  |
| `Orion.Cloud.Azure.AppServiceStatistics` | `System.StatisticsEntity` | - | 14/1/0 |  |
| `Orion.Cloud.Azure.ApplicationGateway` | `System.ManagedEntity` | - | 27/2/0 |  |
| `Orion.Cloud.Azure.ApplicationGatewayStatistics` | `System.StatisticsEntity` | - | 11/1/0 |  |
| `Orion.Cloud.Azure.AzurePollingCounters` | `System.Entity` | - | 3/1/0 |  |
| `Orion.Cloud.Azure.CosmosDBAccount` | `System.ManagedEntity` | - | 23/4/0 |  |
| `Orion.Cloud.Azure.CosmosDBAccountStatistics` | `System.StatisticsEntity` | - | 8/1/0 |  |
| `Orion.Cloud.Azure.CosmosDBContainer` | `System.ManagedEntity` | - | 20/3/0 |  |
| `Orion.Cloud.Azure.CosmosDBContainerStatistics` | `System.StatisticsEntity` | - | 7/1/0 |  |
| `Orion.Cloud.Azure.CosmosDBDatabase` | `System.ManagedEntity` | - | 16/5/0 |  |
| `Orion.Cloud.Azure.CosmosDBDatabaseStatistics` | `System.StatisticsEntity` | - | 7/1/0 |  |
| `Orion.Cloud.Azure.CostManagement` | `System.ManagedEntity` | - | 10/2/0 |  |
| `Orion.Cloud.Azure.CostManagementDatabase` | `System.StatisticsEntity` | - | 2/0/0 |  |
| `Orion.Cloud.Azure.CostManagementStatistics` | `System.StatisticsEntity` | - | 2/1/0 |  |
| `Orion.Cloud.Azure.ExpressRouteCircuit` | `System.ManagedEntity` | - | 28/2/0 |  |
| `Orion.Cloud.Azure.ExpressRouteCircuitStatistics` | `System.StatisticsEntity` | - | 12/1/0 |  |
| `Orion.Cloud.Azure.FunctionApp` | `System.ManagedEntity` | - | 42/1/0 |  |
| `Orion.Cloud.Azure.FunctionAppStatistics` | `System.StatisticsEntity` | - | 25/1/0 |  |
| `Orion.Cloud.Azure.InstanceStatistics` | `Orion.Cloud.InstanceStatistics` | - | 0/0/0 |  |
| `Orion.Cloud.Azure.InstanceThresholds` | `Orion.Cloud.InstanceThresholds` | - | 0/0/0 |  |
| `Orion.Cloud.Azure.Instances` | `Orion.Cloud.Instances` | - | 9/1/0 |  |
| `Orion.Cloud.Azure.KubernetesCluster` | `System.ManagedEntity` | - | 30/3/0 |  |
| `Orion.Cloud.Azure.KubernetesClusterStatistics` | `System.StatisticsEntity` | - | 13/1/0 |  |
| `Orion.Cloud.Azure.KubernetesNode` | `System.Entity` | - | 18/2/0 |  |
| `Orion.Cloud.Azure.KubernetesNodePool` | `System.Entity` | - | 7/2/0 |  |
| `Orion.Cloud.Azure.KubernetesNodeStatistics` | `System.StatisticsEntity` | - | 11/1/0 |  |
| `Orion.Cloud.Azure.Management` | `System.Indication` | - | 0/0/0 |  |
| `Orion.Cloud.Azure.RegionalLoadBalancer` | `System.ManagedEntity` | - | 33/2/0 |  |
| `Orion.Cloud.Azure.RegionalLoadBalancerStatistics` | `System.StatisticsEntity` | - | 17/1/0 |  |
| `Orion.Cloud.Azure.Regions` | `Orion.Cloud.Regions` | - | 0/0/1 | This entity presents the Azure region. |
| `Orion.Cloud.Azure.ResourseTags` | `Orion.Cloud.ResourseTags` | - | 0/0/0 | This entity presents the tags associated with Azure resources. |
| `Orion.Cloud.Azure.SqlDatabase` | `System.ManagedEntity` | - | 39/2/0 |  |
| `Orion.Cloud.Azure.SqlDatabaseStatistics` | `System.StatisticsEntity` | - | 47/1/0 |  |
| `Orion.Cloud.Azure.SqlServer` | `System.Entity` | - | 11/2/0 |  |
| `Orion.Cloud.Azure.StorageAccount` | `System.ManagedEntity` | - | 23/5/0 |  |
| `Orion.Cloud.Azure.StorageAccountBlobContainer` | `System.ManagedEntity` | - | 16/1/0 |  |
| `Orion.Cloud.Azure.StorageAccountBlobService` | `System.ManagedEntity` | - | 18/2/0 |  |
| `Orion.Cloud.Azure.StorageAccountBlobServiceStatistics` | `System.StatisticsEntity` | - | 10/1/0 |  |
| `Orion.Cloud.Azure.StorageAccountStatistics` | `System.StatisticsEntity` | - | 7/1/0 |  |
| `Orion.Cloud.Azure.StorageAccountTable` | `System.ManagedEntity` | - | 9/1/0 |  |
| `Orion.Cloud.Azure.StorageAccountTableService` | `System.ManagedEntity` | - | 17/2/0 |  |
| `Orion.Cloud.Azure.StorageAccountTableServiceStatistics` | `System.StatisticsEntity` | - | 9/1/0 |  |
| `Orion.Cloud.Azure.VirtualHub` | `System.ManagedEntity` | - | 23/4/0 |  |
| `Orion.Cloud.Azure.VirtualHubConnection` | `System.ManagedEntity` | - | 13/2/0 |  |
| `Orion.Cloud.Azure.VirtualHubStatistics` | `System.StatisticsEntity` | - | 7/1/0 |  |
| `Orion.Cloud.Azure.VirtualHubSubEntities` | `System.ManagedEntity` | - | 15/3/0 |  |
| `Orion.Cloud.Azure.VirtualMachineBackupStatus` | `System.ManagedEntity` | - | 6/0/0 |  |
| `Orion.Cloud.Azure.VirtualWan` | `System.ManagedEntity` | - | 16/3/0 |  |
| `Orion.Cloud.Azure.Volumes` | `Orion.Cloud.Volumes` | - | 6/1/0 |  |
| `Orion.Cloud.Azure.Vpcs` | `Orion.Cloud.Vpcs` | r | 12/1/0 |  |
| `Orion.Cloud.CloudJobSettings` | `System.Entity` | c,d,i,r,u | 9/3/0 | This entity presents cloud job setting. |
| `Orion.Cloud.Compute.NetObjectTypesView` | `System.Entity` | - | 5/0/0 |  |
| `Orion.Cloud.CostEntities` | `System.Entity` | - | 11/0/0 |  |
| `Orion.Cloud.DatabaseAliases` | `System.Entity` | - | 2/0/0 | This entity is creates association between cloud database type and its user-friendly name to be displayed on… |
| `Orion.Cloud.EventsView` | `System.Entity` | - | 14/0/0 |  |
| `Orion.Cloud.Gcp.Accounts` | `Orion.Cloud.Accounts` | - | 3/1/0 | This entity presents the GCP Cloud account information. |
| `Orion.Cloud.Gcp.BigQueryDataset` | `System.Entity` | c,d,i,r,u | 4/1/0 | This entity presents the Gcp BigQuery Dataset. |
| `Orion.Cloud.Gcp.CloudStorage` | `System.ManagedEntity` | - | 20/2/0 | This entity presents the GCP Cloud Storage information. |
| `Orion.Cloud.Gcp.CloudStorageStatistics` | `System.StatisticsEntity` | - | 6/1/0 | This entity presents the GCP Cloud Storage Statistics information. |
| `Orion.Cloud.Gcp.CloudVPNGateway` | `Orion.CloudMonitoring.CloudVPNGateway` | r | 1/0/0 | This entity presents the GCP Virtual Network Gateways information. |
| `Orion.Cloud.Gcp.CostManagement` | `System.ManagedEntity` | - | 14/2/0 |  |
| `Orion.Cloud.Gcp.CostManagementStatistics` | `System.StatisticsEntity` | - | 2/1/0 |  |
| `Orion.Cloud.Gcp.GkeCluster` | `System.ManagedEntity` | - | 31/3/0 |  |
| `Orion.Cloud.Gcp.GkeClusterStatistics` | `System.StatisticsEntity` | - | 5/1/0 |  |
| `Orion.Cloud.Gcp.GkeContainer` | `System.ManagedEntity` | - | 29/4/0 |  |
| `Orion.Cloud.Gcp.GkeContainerResourceFormatter` | `System.ManagedEntity` | - | 6/0/0 |  |
| `Orion.Cloud.Gcp.GkeContainerStatistics` | `System.StatisticsEntity` | - | 6/1/0 |  |
| `Orion.Cloud.Gcp.GkeNode` | `System.ManagedEntity` | - | 29/5/0 |  |
| `Orion.Cloud.Gcp.GkeNodeStatistics` | `System.StatisticsEntity` | - | 8/1/0 |  |
| `Orion.Cloud.Gcp.GkePod` | `System.ManagedEntity` | - | 23/4/0 |  |
| `Orion.Cloud.Gcp.GkePodStatistics` | `System.StatisticsEntity` | - | 6/1/0 |  |
| `Orion.Cloud.Gcp.InstanceStatistics` | `Orion.Cloud.InstanceStatistics` | - | 0/0/0 | This entity presents the GCP Cloud instances's statistics information. |
| `Orion.Cloud.Gcp.InstanceThresholds` | `Orion.Cloud.InstanceThresholds` | - | 0/0/0 | This entity presents the GCP Cloud instance's threshold information. |
| `Orion.Cloud.Gcp.Instances` | `Orion.Cloud.Instances` | - | 10/2/0 | This entity presents the GCP instances. |
| `Orion.Cloud.Gcp.LBBackendService` | `System.ManagedEntity` | - | 23/2/0 | This entity presents the GCP Load Balancer Backend Service information. |
| `Orion.Cloud.Gcp.LBBackendServiceStatistics` | `System.StatisticsEntity` | - | 6/1/0 | This entity presents the GCP Load Balancer Backend Service Statistics information. |
| `Orion.Cloud.Gcp.LBForwardingRule` | `System.ManagedEntity` | - | 37/2/0 | This entity presents the GCP Load Balancer Forwarding Rule information. |
| `Orion.Cloud.Gcp.LBForwardingRuleStatistics` | `System.StatisticsEntity` | - | 16/1/0 | This entity presents the GCP Load Balancer Forwarding Rule Statistics information. |
| `Orion.Cloud.Gcp.LBTargetProxy` | `System.ManagedEntity` | - | 15/1/0 | This entity presents the GCP Load Balancer Target Proxy information. |
| `Orion.Cloud.Gcp.LBUrlMap` | `System.ManagedEntity` | - | 13/1/0 | This entity presents the GCP Load Balancer Url Map information. |
| `Orion.Cloud.Gcp.Management` | `System.Indication` | - | 0/0/0 |  |
| `Orion.Cloud.Gcp.ProjectDetails` | `System.Entity` | c,d,i,r,u | 4/1/0 | This entity presents the Gcp ProjectDetails. |
| `Orion.Cloud.Gcp.Regions` | `Orion.Cloud.Regions` | - | 0/1/1 | This entity presents the Gcp region. |
| `Orion.Cloud.Gcp.SqlDatabase` | `System.ManagedEntity` | - | 73/2/0 | This entity presents the GCP SQL Instance Database information. |
| `Orion.Cloud.Gcp.SqlDatabaseStatistics` | `System.StatisticsEntity` | - | 129/1/0 | This entity presents the GCP SQL Instance Database Statistics information. |
| `Orion.Cloud.Gcp.VolumeStatistics` | `System.StatisticsEntity` | - | 6/1/0 | This entity presents the GCP Cloud Persistent disk's statistics information. |
| `Orion.Cloud.Gcp.VolumeStatus` | `System.Entity` | - | 2/1/0 | This entity presents the GCP Cloud Persistent disk's status information. |
| `Orion.Cloud.Gcp.Volumes` | `Orion.Cloud.Volumes` | - | 14/3/0 | This entity presents the GCP Cloud Persistent disk's information. |
| `Orion.Cloud.Gcp.Vpcs` | `Orion.Cloud.Vpcs` | - | 1/1/0 | This entity presents the GCP VPC information. |
| `Orion.Cloud.InstanceStatistics` | `Orion.Virtualization.Statistics` | - | 15/1/0 |  |
| `Orion.Cloud.InstanceStatus` | `System.Entity` | - | 11/1/0 | Cloud vritual machine from Azure and Amazon Elastic Compute Cloud Web Service partial statuses of an instance. |
| `Orion.Cloud.InstanceStatusMacro` | `System.Entity` | - | 15/1/0 |  |
| `Orion.Cloud.InstanceThresholds` | `Orion.Virtualization.InstanceThresholds` | - | 0/1/0 |  |
| `Orion.Cloud.Instances` | `Orion.Virtualization.Instance` | - | 27/6/8 |  |
| `Orion.Cloud.NetworkInterfaces` | `System.Entity` | - | 4/0/0 |  |
| `Orion.Cloud.Providers` | `System.Entity` | - | 3/2/0 |  |
| `Orion.Cloud.Regions` | `System.Entity` | c,d,i,r,u | 5/2/0 | This entity presents the region. |
| `Orion.Cloud.ResourseTags` | `System.Entity` | c,d,i,r,u | 6/0/0 | This entity presents the tags associated with cloud resources |
| `Orion.Cloud.SecurityGroups` | `System.Entity` | - | 3/0/0 |  |
| `Orion.Cloud.SelectedCloudRegions` | `System.Entity` | c,d,i,r,u | 3/2/0 | This entity presents selected cloud regions. |
| `Orion.Cloud.TagFilter` | `System.Entity` | c,d,i,r,u | 4/1/0 | Tags are assigned to cloud job settings to filter polled cloud resources. |
| `Orion.Cloud.VirtualNetworkAddressSpaces` | `System.Entity` | - | 3/0/0 |  |
| `Orion.Cloud.Volumes` | `System.ManagedEntity` | - | 9/0/0 |  |
| `Orion.Cloud.Vpcs` | `System.ManagedEntity` | r | 13/2/0 |  |
| `Orion.CloudEntitiesView` | `System.Entity` | - | 13/0/0 |  |
| `Orion.CloudMonitoring.CloudVPNConnection` | `System.ManagedEntity` | r | 29/3/0 | Entity which provides access to cloud site to site connections |
| `Orion.CloudMonitoring.CloudVPNConnection.AvailabilityMetrics` | `System.StatisticsEntity` | r | 4/1/0 |  |
| `Orion.CloudMonitoring.CloudVPNConnection.Metrics` | `System.StatisticsEntity` | r | 7/1/0 |  |
| `Orion.CloudMonitoring.CloudVPNGateway` | `System.ManagedEntity` | r | 17/6/0 |  |
| `Orion.CloudMonitoring.CloudVPNGateway.AWS` | `Orion.CloudMonitoring.CloudVPNGateway` | r | 1/0/0 |  |
| `Orion.CloudMonitoring.CloudVPNGateway.AvailabilityMetrics` | `System.StatisticsEntity` | r | 4/1/0 |  |
| `Orion.CloudMonitoring.CloudVPNGateway.Azure` | `Orion.CloudMonitoring.CloudVPNGateway` | r | 1/0/0 |  |
| `Orion.CloudMonitoring.CloudVPNGateway.Metrics` | `System.StatisticsEntity` | r | 7/1/0 |  |
| `Orion.Cman.Container` | `System.ManagedEntity` | c,d,i,r,u | 21/7/0 | This entity presents Container properties |
| `Orion.Cman.ContainerAgent` | `System.Entity` | c,d,i,r,u | 11/1/0 | This entity presents Container Agent properties |
| `Orion.Cman.ContainerCpuMetrics` | `System.StatisticsEntity` | r | 5/1/0 | This entity presents Container Cpu Metrics properties |
| `Orion.Cman.ContainerImage` | `System.Entity` | c,d,i,r,u | 8/1/0 | This entity presents Container Image properties |
| `Orion.Cman.ContainerMemoryMetrics` | `System.StatisticsEntity` | r | 5/1/0 | This entity presents Container Memory Metrics properties |
| `Orion.ConfigurationChanged` | `System.Indication` | - | 3/0/0 | Occurs when a setting is changed but not via SWIS api. Thus subscription on that setting's entity is not rece… |
| `Orion.Container` | `System.ManagedEntity` | i,r | 13/5/11 |  |
| `Orion.ContainerMemberDefinition` | `System.Entity` | - | 7/0/2 |  |
| `Orion.ContainerMemberSnapshots` | `System.Entity` | - | 13/1/0 |  |
| `Orion.ContainerMembers` | `System.Entity` | - | 12/1/0 |  |
| `Orion.ContainerMembersNodes` | `System.Entity` | - | 12/0/0 |  |
| `Orion.ContainerStatus` | `System.StatisticsEntity` | - | 5/1/0 |  |
| `Orion.CpuLoadThreshold` | `Orion.NodesThresholds` | - | 0/1/0 |  |
| `Orion.Credential` | `System.Entity` | c,d,i,r,u | 5/3/10 | Entity represents Orion Credential objects that are used in discovery and polling processes |
| `Orion.CredentialRelation` | `System.Entity` | c,d,i,r,u | 7/1/0 | Relation to Orion.Credential. Serve for reuse same credentials for different Entity type. |
| `Orion.CustomProperty` | `System.Entity` | - | 10/3/0 |  |
| `Orion.CustomPropertyAssignValues` | `System.Indication` | - | 4/0/0 |  |
| `Orion.CustomPropertySources` | `System.Entity` | - | 4/1/0 |  |
| `Orion.CustomPropertyUsage` | `System.Entity` | - | 0/1/0 |  |
| `Orion.CustomPropertyValues` | `System.Entity` | - | 3/0/0 |  |
| `Orion.DPA.DatabaseInstance` | `System.ManagedEntity` | r | 26/17/0 | Represents single monitored database instance |
| `Orion.DPA.DatabaseInstanceApplication` | `Orion.DPA.DatabaseInstanceApplicationRelationship` | - | 0/2/0 | All relationships between Orion Application and Database Instance, where both are monitoring the same db inst… |
| `Orion.DPA.DatabaseInstanceApplicationNoRelationship` | `Orion.DPA.DatabaseInstanceApplicationRelationship` | - | 0/0/0 | All removed relationships between Orion Application and Database Instance |
| `Orion.DPA.DatabaseInstanceApplicationRelationship` | `System.Entity` | c,d,i,r,u | 8/0/0 | All relationships between Orion Application and Database Instance |
| `Orion.DPA.DatabaseInstanceClientApplication` | `Orion.DPA.DatabaseInstanceApplicationRelationship` | - | 0/2/0 | All relationships between Orion Application and Database Instance, where application is client and database i… |
| `Orion.DPA.DatabaseInstanceData` | `System.ExtensionEntity` | c,d,i,r,u | 5/2/0 | Relationship between DPA Database Instance and Orion Node |
| `Orion.DPA.DatabaseInstanceLun` | `System.Entity` | c,d,i,r,u | 3/2/0 | All relationships between Orion LUN and Database Instance |
| `Orion.DPA.DpaServer` | `System.ManagedEntity` | c,d,i,r,u | 15/3/1 | Integrated DPA server |
| `Orion.DPA.ServerApplicationTemplate` | `System.Entity` | r | 2/0/0 | Templates of SAM Application which can be in relationship with Database Instance monitoring the same database |
| `Orion.DPE.WorkAvailable` | `System.Indication` | - | 1/0/0 |  |
| `Orion.DPI.ApplicationAssignments` | `System.Entity` | c,d,i,r,u | 14/2/0 |  |
| `Orion.DPI.ApplicationAssignmentsThresholds` | `System.Entity` | - | 17/0/0 |  |
| `Orion.DPI.ApplicationCategories` | `System.Entity` | - | 2/2/0 |  |
| `Orion.DPI.ApplicationProtocols` | `System.Entity` | - | 7/2/0 |  |
| `Orion.DPI.ApplicationSettings` | `System.Entity` | c,d,i,r,u | 4/1/0 |  |
| `Orion.DPI.Applications` | `System.ManagedEntity` | c,d,i,r,u | 31/6/0 |  |
| `Orion.DPI.ApplicationsThresholds` | `Orion.Thresholds` | - | 0/0/0 |  |
| `Orion.DPI.ApplicationsThresholdsForAlerting` | `System.Entity` | - | 10/1/0 |  |
| `Orion.DPI.ProbeAssignments` | `System.Entity` | c,d,i,r,u | 2/2/0 |  |
| `Orion.DPI.ProbeProperties` | `System.Entity` | c,d,i,r,u | 4/1/0 |  |
| `Orion.DPI.ProbeSettings` | `System.Entity` | c,d,i,r,u | 4/1/0 |  |
| `Orion.DPI.Probes` | `System.Entity` | c,d,i,r,u | 7/4/5 |  |
| `Orion.DPI.QoeApplicationsStatistics` | `System.Entity` | - | 33/0/0 |  |
| `Orion.DPI.QoeStatistics` | `System.StatisticsEntity` | - | 25/2/0 |  |
| `Orion.Dashboards.DashboardGroup` | `System.Entity` | c,d,i,r,u | 2/1/0 | Provides details about dashboard group |
| `Orion.Dashboards.DashboardViewPreference` | `System.Entity` | c,d,i,r,u | 6/1/0 | Provides details about dashboard view preferences |
| `Orion.Dashboards.Entity` | `System.Entity` | - | 5/0/0 |  |
| `Orion.Dashboards.Instances` | `Orion.Dashboards.Entity` | c,d,i,r,u | 13/5/16 | An Orion dashboard instance. |
| `Orion.Dashboards.Links` | `System.Entity` | - | 4/2/0 | Provide link between dashboards and widgets |
| `Orion.Dashboards.Widgets` | `Orion.Dashboards.Entity` | c,d,i,r,u | 4/1/4 | A Widget which can be displayed on a Dashboard. |
| `Orion.Declarative.PollerTemplates` | `System.Entity` | i,r | 3/0/2 |  |
| `Orion.DeletedAutoDependencies` | `System.Entity` | c,d,i,r,u | 16/0/1 | This entity contains Auto Dependencies ignored by user |
| `Orion.Dependencies` | `System.Entity` | c,d,i,r,u | 16/2/1 | This entity contains dependencies defined by user and generated automatically |
| `Orion.DependencyEntities` | `System.Entity` | - | 3/0/0 |  |
| `Orion.DeviceStudio.PollerAssignments` | `System.Entity` | - | 5/1/0 |  |
| `Orion.DeviceStudio.Pollers` | `System.Entity` | - | 10/2/0 |  |
| `Orion.DeviceStudio.Technologies` | `System.Entity` | - | 3/1/0 |  |
| `Orion.DiscoveredNodeChildEntities` | `System.Entity` | r | 6/1/0 |  |
| `Orion.DiscoveredNodes` | `System.Entity` | r | 20/1/0 |  |
| `Orion.DiscoveredPollers` | `System.Entity` | r | 5/0/0 |  |
| `Orion.DiscoveredVolumes` | `System.Entity` | r | 6/0/0 |  |
| `Orion.Discovery` | `System.Entity` | i | 0/0/12 |  |
| `Orion.DiscoveryIgnoredInterfaces` | `System.Entity` | r | 8/0/0 |  |
| `Orion.DiscoveryIgnoredNodes` | `System.Entity` | r | 6/0/0 |  |
| `Orion.DiscoveryIgnoredVolumes` | `System.Entity` | r | 5/0/0 |  |
| `Orion.DiscoveryLogItems` | `System.Entity` | r | 4/1/0 |  |
| `Orion.DiscoveryLogNodes` | `System.Entity` | - | 4/1/0 |  |
| `Orion.DiscoveryLogs` | `System.Entity` | c,r | 8/2/0 |  |
| `Orion.DiscoveryNodesStatuses` | `System.Entity` | r | 5/0/0 |  |
| `Orion.DiscoveryProfiles` | `System.Entity` | r | 32/1/0 |  |
| `Orion.ELB.NodeExclusions` | `System.Entity` | c,d,i,r,u | 1/0/0 | Nodes that are excluded from Engine Load Balancing. |
| `Orion.ELB.NodeReassignments` | `System.Entity` | c,d,i,r,u | 5/0/0 | History of node reassignments performed by Engine Load Balancing (ELB). |
| `Orion.EOC.SiteAccess` | `System.Entity` | c,d,i,r,u | 6/1/1 |  |
| `Orion.EOC.SiteAccounts` | `System.Entity` | c,d,i,r,u | 7/2/3 |  |
| `Orion.EOC.Sites` | `System.Entity` | c,d,i,r,u | 9/2/2 |  |
| `Orion.ESI.AlertIncident` | `System.Entity` | - | 15/3/0 | Abstract entity aggregating incidents provided by integrated incident services and related to Orion alerts. |
| `Orion.ESI.AlertIncidentInfo` | `System.Entity` | - | 4/1/0 | Abstract entity aggregating incidents provided by integrated incidents services info grouped by Orion alert o… |
| `Orion.ESI.ClusterIncident` | `System.Entity` | - | 9/1/0 | Abstract entity aggregating incidents provided by integrated incident services and related to Orion AlertStac… |
| `Orion.ESI.IncidentIntegration` | `System.Entity` | - | 0/0/1 | Management entity providing capability to modify current incident integration features configuration. |
| `Orion.ESI.IncidentService` | `System.Entity` | c,d,i,r,u | 9/3/0 | Holds the information about integrated incident management services. |
| `Orion.ElementInfo` | `System.Entity` | - | 2/0/0 |  |
| `Orion.EnabledFeatures` | `System.Entity` | - | 1/0/0 |  |
| `Orion.EngineLoadBalancingEnabledStatusChanged` | `System.Indication` | - | 2/0/0 | Indication raised when engine load balancing enabled status changed. |
| `Orion.EngineLoadBalancingExecution` | `System.Indication` | - | 1/0/0 | Indication raised when engine load balancing execution occurs. |
| `Orion.EngineLoadBalancingNodeExcludedStatusChanged` | `System.Indication` | - | 3/0/0 | Indication raised when a node's included/excluded status in engine load balancing has changed. |
| `Orion.EngineLoadBalancingNodeReassigned` | `System.Indication` | - | 5/0/0 | Indication raised when a node is reassigned to a different polling engine as a result of engine load balancin… |
| `Orion.EngineProperties` | `System.Entity` | c,d,r,u | 4/1/0 | Property and their values for each engine. |
| `Orion.Engines` | `System.Entity` | c,d,r,u | 51/12/0 | This entity contains main poller and all additional pollers list. |
| `Orion.EntityUnmanaged` | `System.Indication` | - | 5/0/0 |  |
| `Orion.Environment` | `System.Entity` | c,d,i,r,u | 6/0/9 |  |
| `Orion.EventTypes` | `System.Entity` | - | 13/2/0 |  |
| `Orion.Events` | `Orion.MixedObjectType` | c,i,r | 8/3/1 | Contains event records generated by the Orion monitoring system, including network events, status changes, an… |
| `Orion.ExpandedLimitations` | `System.Entity` | - | 5/0/0 |  |
| `Orion.F5.GTM.Pool` | `System.Entity` | - | 6/2/0 |  |
| `Orion.F5.GTM.PoolMember` | `System.Entity` | - | 4/2/0 |  |
| `Orion.F5.GTM.Server` | `System.Entity` | - | 3/1/0 |  |
| `Orion.F5.GTM.VirtualServer` | `System.Entity` | - | 8/3/0 |  |
| `Orion.F5.GTM.WideIP` | `System.Entity` | - | 18/3/0 |  |
| `Orion.F5.GTM.WideIPPool` | `System.Entity` | - | 4/2/0 |  |
| `Orion.F5.GTM.WideIPStats` | `System.Entity` | - | 6/1/0 |  |
| `Orion.F5.LTM.Monitor` | `System.Entity` | - | 15/2/0 |  |
| `Orion.F5.LTM.Pool` | `System.Entity` | - | 21/3/0 |  |
| `Orion.F5.LTM.PoolMember` | `System.Entity` | r,u | 26/4/0 |  |
| `Orion.F5.LTM.PoolMemberStats` | `System.Entity` | - | 12/1/0 |  |
| `Orion.F5.LTM.Server` | `System.Entity` | - | 16/3/2 |  |
| `Orion.F5.LTM.VirtualIPAddress` | `System.Entity` | - | 14/3/0 |  |
| `Orion.F5.LTM.VirtualServer` | `System.Entity` | - | 28/5/0 |  |
| `Orion.F5.LTM.VirtualServerStats` | `System.Entity` | - | 10/1/0 |  |
| `Orion.F5.Map.VirtualServer` | `System.Entity` | - | 7/2/0 |  |
| `Orion.F5.System.Device` | `System.Entity` | - | 28/10/3 |  |
| `Orion.F5.System.DeviceStats` | `System.StatisticsEntity` | - | 48/1/0 |  |
| `Orion.F5.System.Failover` | `System.Entity` | - | 9/1/0 |  |
| `Orion.F5.System.Module` | `System.Entity` | - | 9/1/0 |  |
| `Orion.F5.System.ModuleGTM` | `Orion.F5.System.Module` | - | 0/0/0 |  |
| `Orion.F5.System.ModuleLTM` | `Orion.F5.System.Module` | - | 0/1/0 |  |
| `Orion.F5.System.ModuleOther` | `Orion.F5.System.Module` | - | 0/0/0 |  |
| `Orion.F5.System.VLAN` | `System.Entity` | - | 7/1/0 |  |
| `Orion.FavoriteMacroVariables` | `System.Entity` | c,d,i,r,u | 2/0/0 | Favorite macro variables. |
| `Orion.FavoriteProperties` | `System.Entity` | c,d,i,r,u | 3/0/0 | Selected favorite user properties entity |
| `Orion.FeatureOnboarding.Actions` | `System.Entity` | - | 8/1/0 | Actions displayed under a button. |
| `Orion.FeatureOnboarding.Buttons` | `System.Entity` | - | 9/2/0 | Buttons shown for a feature. |
| `Orion.FeatureOnboarding.Capabilities` | `System.Entity` | - | 4/1/0 |  |
| `Orion.FeatureOnboarding.Categories` | `System.Entity` | - | 3/0/0 | Feature onboarding categories with optional modern icons. |
| `Orion.FeatureOnboarding.Features` | `System.Entity` | - | 15/4/0 | Feature onboarding definitions including metadata, recommendations, and category linkage. |
| `Orion.FeatureOnboarding.Groups` | `System.Entity` | - | 5/1/0 |  |
| `Orion.FeatureOnboarding.UsageDefinitions` | `System.Entity` | - | 4/1/0 | Usage metrics associated with a feature. |
| `Orion.FeatureOnboarding.WhatsNew` | `System.Entity` | - | 7/2/0 |  |
| `Orion.Features` | `System.Entity` | - | 2/3/1 | Represents available orion features on orion installation. |
| `Orion.Firewall.L2LTunnel` | `System.ManagedEntity` | - | 21/4/2 |  |
| `Orion.Firewall.L2LTunnelStatistics` | `System.StatisticsEntity` | - | 4/1/0 |  |
| `Orion.Firewall.L2LTunnelStatistics2` | `System.StatisticsEntity` | - | 2/1/0 |  |
| `Orion.Firewall.L2LTunnelTrafficSelector` | `System.ManagedEntity` | - | 29/3/0 |  |
| `Orion.Firewall.L2LTunnelTrafficSelectorStatistics` | `System.StatisticsEntity` | - | 6/1/0 |  |
| `Orion.Firewall.L2LTunnelTrafficSelectorStatistics2` | `System.StatisticsEntity` | - | 2/1/0 |  |
| `Orion.Firewall.RemoteAccessTunnel` | `System.ManagedEntity` | - | 29/2/0 |  |
| `Orion.Firewall.RemoteAccessTunnelStatistics` | `System.StatisticsEntity` | - | 5/1/0 |  |
| `Orion.ForecastCapacity` | `System.Entity` | - | 26/1/0 | Top level entity for Capacity Forecasting, which contains general information such as forecasting coeffiecien… |
| `Orion.ForecastCapacitySettings` | `System.Entity` | c,r,u | 7/0/0 | Per NetObject settings for forecasting entities. These takes precedence over the global settings from Forecas… |
| `Orion.ForecastMetrics` | `System.Entity` | c,r,u | 11/1/0 | Global settings for forecasting entities (e.g. CPULoad). Global settings include global thresholds, UsePeakVa… |
| `Orion.Fortigate.HighAvailability` | `System.ManagedEntity` | - | 30/2/0 |  |
| `Orion.Fortigate.HighAvailabilityStatistics` | `System.StatisticsEntity` | - | 11/1/0 |  |
| `Orion.Fortigate.VirtualDomain` | `System.ManagedEntity` | - | 19/2/0 |  |
| `Orion.Fortigate.VirtualDomainStatistics` | `System.StatisticsEntity` | - | 7/1/0 |  |
| `Orion.Frequencies` | `System.Entity` | c,d,i,r,u | 14/0/3 |  |
| `Orion.GroupCustomProperties` | `System.CustomPropertiesEntity` | i,r,u | 0/1/5 |  |
| `Orion.GroupMembers` | `System.DashboardEntity` | - | 11/2/0 |  |
| `Orion.Groups` | `Orion.Container` | - | 1/2/0 |  |
| `Orion.GroupsWebUri` | `System.Entity` | - | 2/1/0 |  |
| `Orion.HA.FacilitiesInstances` | `System.Entity` | - | 4/1/0 | Facilities which belongs to pool members. Facility can be imagined e.g. as a service (e.g. MSMQ) which indica… |
| `Orion.HA.PoolAdded` | `System.Indication` | - | 2/0/0 |  |
| `Orion.HA.PoolDeleted` | `System.Indication` | - | 2/0/0 |  |
| `Orion.HA.PoolEdited` | `System.Indication` | - | 4/0/0 |  |
| `Orion.HA.PoolMemberInterfacesInfo` | `System.Entity` | c,d,i,r,u | 5/1/0 | IP addresses present on interfaces of pool members. |
| `Orion.HA.PoolMembers` | `System.Entity` | r | 14/6/0 | Pool members (Orion polling engines and backup servers) present in Orion deployment. |
| `Orion.HA.Pools` | `System.Entity` | c,d,i,r,u | 19/3/13 | High Availability pools. Pool unites pool members of the same type to provide high availability of Orion serv… |
| `Orion.HA.ReachabilityInfo` | `System.Entity` | - | 8/0/0 | Host names and IP addresses of pool members. It is an extension of Orion.ReachabilityInfo. |
| `Orion.HA.ResourcesInstances` | `System.Entity` | c,d,i,r,u | 7/2/0 | Resources which belongs to pool members. Resource is a responsibility of Orion server which can be switched t… |
| `Orion.HardwareHealth.BMC.Blades` | `System.Entity` | - | 12/2/0 | This entity presents the Blades. |
| `Orion.HardwareHealth.BMC.Chassis` | `System.ManagedEntity` | - | 15/7/0 | This entity presents the Chassis. |
| `Orion.HardwareHealth.BMC.Controllers` | `System.Entity` | - | 10/6/1 | This entity presents the Controllers. |
| `Orion.HardwareHealth.BMC.Fans` | `System.Entity` | - | 14/1/0 | This entity presents the Fans. |
| `Orion.HardwareHealth.BMC.FansOnChassis` | `Orion.HardwareHealth.BMC.Fans` | - | 0/1/0 | This entity presents the Fans related to Chassis. |
| `Orion.HardwareHealth.BMC.PSUs` | `System.Entity` | - | 13/1/0 | This entity presents Power Supply Unit. |
| `Orion.HardwareHealth.BMC.PSUsOnChassis` | `Orion.HardwareHealth.BMC.PSUs` | - | 0/1/0 | This entity presents the Power Supply Unit related to Chassis. |
| `Orion.HardwareHealth.BMC.Racks` | `System.Entity` | - | 13/2/0 | This entity presents the Racks. |
| `Orion.HardwareHealth.HardwareCategory` | `System.Entity` | - | 4/3/0 | This entity presents the Hardware Category. |
| `Orion.HardwareHealth.HardwareCategoryStatus` | `Orion.HardwareHealth.HardwareCategoryStatusBase` | - | 2/4/0 | This entity presents the Hardware Category Status For Nodes. |
| `Orion.HardwareHealth.HardwareCategoryStatusBase` | `System.ManagedEntity` | - | 16/1/0 | This entity presents the Hardware Category Status Base. |
| `Orion.HardwareHealth.HardwareCategoryStatusForArray` | `Orion.HardwareHealth.HardwareCategoryStatusBase` | - | 2/2/0 | HardwareCategory status for Storage arrays |
| `Orion.HardwareHealth.HardwareCategoryStatusForChassis` | `Orion.HardwareHealth.HardwareCategoryStatusBase` | - | 1/3/0 | This entity presents the Hardware Category Status For Chassis. |
| `Orion.HardwareHealth.HardwareCategoryStatusWebUri` | `System.Entity` | - | 2/1/0 | This entity presents the Hardware Category Web Uri For Nodes. |
| `Orion.HardwareHealth.HardwareHierarchy` | `System.Entity` | - | 6/2/0 | This entity presents the Hardware Hierarchy. |
| `Orion.HardwareHealth.HardwareHierarchyForArray` | `Orion.HardwareHealth.HardwareHierarchy` | - | 1/0/0 | HardwareHierarchyForArray overrides HardwareHierarchy entity for SRM |
| `Orion.HardwareHealth.HardwareInfo` | `Orion.HardwareHealth.HardwareInfoBase` | - | 2/4/0 | This entity presents the Hardware Info For Nodes. |
| `Orion.HardwareHealth.HardwareInfoBase` | `System.ManagedEntity` | - | 32/0/4 | This entity presents the Hardware Info Base. |
| `Orion.HardwareHealth.HardwareInfoForArray` | `Orion.HardwareHealth.HardwareInfoBase` | - | 2/2/0 | HardwareInfo entity for Storage arrays |
| `Orion.HardwareHealth.HardwareInfoForChassis` | `Orion.HardwareHealth.HardwareInfoBase` | - | 4/3/0 | This entity presents the Hardware Info For Chassis. |
| `Orion.HardwareHealth.HardwareInfoForUCSChassis` | `Orion.HardwareHealth.HardwareInfoForChassis` | - | 1/0/0 | This entity presents the HardwareHealth Info related to UCS Chassis. |
| `Orion.HardwareHealth.HardwareInfoWebUri` | `System.Entity` | - | 2/1/0 | This entity presents the Hardware Info Web Uri For Nodes. |
| `Orion.HardwareHealth.HardwareItem` | `Orion.HardwareHealth.HardwareItemBase` | - | 2/4/0 | This entity presents the Hardware Item For Nodes. |
| `Orion.HardwareHealth.HardwareItemBase` | `System.ManagedEntity` | - | 25/7/2 | This entity presents the Hardware Item Base. |
| `Orion.HardwareHealth.HardwareItemForArray` | `Orion.HardwareHealth.HardwareItemBase` | - | 2/1/0 | HardwareItem entity for Storage arrays |
| `Orion.HardwareHealth.HardwareItemForChassis` | `Orion.HardwareHealth.HardwareItemBase` | - | 1/3/0 | This entity presents the Hardware Item For Chassis. |
| `Orion.HardwareHealth.HardwareItemStatistics` | `System.StatisticsEntity` | - | 7/1/0 | This entity presents the Hardware Item Statistics. |
| `Orion.HardwareHealth.HardwareItemStatusStatistics` | `System.StatisticsEntity` | - | 3/1/0 | This entity presents the Hardware Item Status Statistics. |
| `Orion.HardwareHealth.HardwareItemThreshold` | `System.Entity` | - | 3/1/2 | This entity presents the Hardware Item Thresholds. |
| `Orion.HardwareHealth.HardwareItemValueStatistics` | `System.StatisticsEntity` | - | 6/1/0 | This entity presents the Hardware Item Value Statistics. |
| `Orion.HardwareHealth.HardwareItemWebUri` | `System.Entity` | - | 2/1/0 | This entity presents the Hardware Item Web Uri For Nodes. |
| `Orion.HardwareHealth.HardwareUnit` | `System.Entity` | - | 3/1/0 | This entity presents the Hardware Unit. |
| `Orion.HardwareHealth.NodeChildStatusHardwareHealth` | `Orion.NodeChildStatusContributors` | - | 0/0/0 | This entity presents the Node Chisd Stats Hardware Health. |
| `Orion.IdentityProviders` | `System.Entity` | c,d,i,r,u | 7/0/0 | Defines settings of configured Single Sign-On identity providers. |
| `Orion.InInterfaceAverageTrafficUtilizationByDays` | `Orion.UsageByDays` | - | 1/0/0 |  |
| `Orion.InformationServiceAccessDenied` | `System.Indication` | - | 3/0/0 | Occurs when user triggers Access denied exception by reading or modifying data using SWIS without permission |
| `Orion.InformationServiceRestLogin` | `System.Indication` | - | 1/0/0 | Occurs when user performs login to SWIS REST API |
| `Orion.InstalledModule` | `System.Entity` | - | 12/0/0 |  |
| `Orion.IpSla.AlertQos` | `System.Entity` | - | 22/0/0 |  |
| `Orion.IpSla.AlertTypes` | `System.Entity` | - | 4/0/0 |  |
| `Orion.IpSla.AxlConnectionInfo` | `System.Entity` | - | 5/0/0 |  |
| `Orion.IpSla.CCMGateways` | `System.Entity` | - | 16/4/0 |  |
| `Orion.IpSla.CCMH323Devices` | `System.Entity` | - | 13/0/0 |  |
| `Orion.IpSla.CCMMonitoring` | `System.ManagedEntity` | - | 23/16/0 |  |
| `Orion.IpSla.CCMMonitoringData` | `System.Entity` | - | 4/0/0 |  |
| `Orion.IpSla.CCMMonitoringType` | `System.Entity` | - | 3/1/0 |  |
| `Orion.IpSla.CCMMonitoringWebUri` | `System.ExtensionEntity` | - | 2/1/0 |  |
| `Orion.IpSla.CCMPhoneDetails` | `System.ExtensionEntity` | - | 5/1/0 |  |
| `Orion.IpSla.CCMPhoneStats` | `System.Entity` | - | 8/0/0 |  |
| `Orion.IpSla.CCMPhoneStatsDaily` | `System.Entity` | - | 7/0/0 |  |
| `Orion.IpSla.CCMPhoneStatsDetail` | `System.Entity` | - | 5/0/0 |  |
| `Orion.IpSla.CCMPhoneStatsHourly` | `System.Entity` | - | 7/0/0 |  |
| `Orion.IpSla.CCMPhones` | `System.Entity` | - | 16/3/0 |  |
| `Orion.IpSla.CCMPhonesAvayaData` | `System.Entity` | - | 5/0/0 |  |
| `Orion.IpSla.CCMPhonesCiscoData` | `System.Entity` | - | 6/0/0 |  |
| `Orion.IpSla.CCMRegions` | `System.Entity` | - | 5/4/0 |  |
| `Orion.IpSla.CCMSipTrunk` | `System.ManagedEntity` | - | 16/4/0 |  |
| `Orion.IpSla.CCMSipTrunkAvailability` | `System.StatisticsEntity` | - | 3/1/0 |  |
| `Orion.IpSla.CCMSipTrunkCallActivity` | `System.StatisticsEntity` | - | 8/1/0 |  |
| `Orion.IpSla.CCMSipTrunkCurrentCallActivity` | `System.Entity` | - | 10/1/0 |  |
| `Orion.IpSla.CCMSipTrunkDestinations` | `System.Entity` | - | 5/0/0 |  |
| `Orion.IpSla.CCMSipTrunksStatusesTotalDurations` | `System.Entity` | - | 10/0/0 |  |
| `Orion.IpSla.CCMStats` | `System.Entity` | - | 20/0/0 |  |
| `Orion.IpSla.CCMStatsType` | `System.Entity` | - | 3/0/0 |  |
| `Orion.IpSla.CDRDetails` | `System.Entity` | - | 29/0/0 |  |
| `Orion.IpSla.CallManagerCurrentStats` | `System.Entity` | - | 20/1/0 |  |
| `Orion.IpSla.CallManagerStats` | `System.StatisticsEntity` | - | 17/1/0 |  |
| `Orion.IpSla.CallPathMetrics` | `System.Entity` | - | 9/0/0 |  |
| `Orion.IpSla.CliConnectionInfo` | `System.Entity` | - | 4/1/0 |  |
| `Orion.IpSla.CliConnectionProtocol` | `System.Entity` | - | 2/1/0 |  |
| `Orion.IpSla.Config` | `System.Entity` | - | 3/0/0 |  |
| `Orion.IpSla.ConnectedCCMGateways` | `System.Entity` | - | 8/0/0 |  |
| `Orion.IpSla.ConnectedPhonesReport` | `System.Entity` | - | 12/0/0 |  |
| `Orion.IpSla.DataTypes` | `System.Entity` | - | 2/0/0 |  |
| `Orion.IpSla.Engines` | `System.Entity` | - | 3/0/0 |  |
| `Orion.IpSla.Events` | `System.Entity` | - | 1/0/0 |  |
| `Orion.IpSla.FtpConnectionInfo` | `System.Entity` | - | 9/0/0 |  |
| `Orion.IpSla.HttpFtpOperationResults` | `System.Entity` | - | 26/0/0 |  |
| `Orion.IpSla.HttpFtpOperationResultsDaily` | `System.Entity` | - | 14/0/0 |  |
| `Orion.IpSla.HttpFtpOperationResultsDetail` | `System.Entity` | - | 6/0/0 |  |
| `Orion.IpSla.HttpFtpOperationResultsHourly` | `System.Entity` | - | 14/0/0 |  |
| `Orion.IpSla.ICMPPathMonthReport` | `System.Entity` | - | 24/0/0 |  |
| `Orion.IpSla.ICMPPathReport` | `System.Entity` | - | 24/0/0 |  |
| `Orion.IpSla.IcmpPathJitterOperationStats` | `System.StatisticsEntity` | - | 15/1/0 |  |
| `Orion.IpSla.InfrastructureInterfaces` | `System.Entity` | - | 2/0/0 |  |
| `Orion.IpSla.InfrastructureNodes` | `System.Entity` | - | 5/2/0 |  |
| `Orion.IpSla.JitterMosOperationResults` | `System.Entity` | - | 38/0/0 |  |
| `Orion.IpSla.JitterOperationResults` | `System.Entity` | - | 35/0/0 |  |
| `Orion.IpSla.JitterOperationResultsDaily` | `System.Entity` | - | 29/0/0 |  |
| `Orion.IpSla.JitterOperationResultsDetail` | `System.Entity` | - | 9/0/0 |  |
| `Orion.IpSla.JitterOperationResultsHourly` | `System.Entity` | - | 23/0/0 |  |
| `Orion.IpSla.MosOperationResultsDaily` | `System.Entity` | - | 5/0/0 |  |
| `Orion.IpSla.MosOperationResultsDetail` | `System.Entity` | - | 3/0/0 |  |
| `Orion.IpSla.MosOperationResultsHourly` | `System.Entity` | - | 5/0/0 |  |
| `Orion.IpSla.NodesAvailabilityReport` | `System.Entity` | - | 6/0/0 |  |
| `Orion.IpSla.NonMOSUdpJitterOperationStats` | `System.StatisticsEntity` | - | 15/1/0 |  |
| `Orion.IpSla.NonPathOperationStats` | `System.StatisticsEntity` | - | 6/1/0 |  |
| `Orion.IpSla.NumberTable` | `System.Entity` | - | 1/0/0 |  |
| `Orion.IpSla.OneWayDelayOperationResults` | `System.Entity` | - | 20/0/0 |  |
| `Orion.IpSla.OneWayDelayOperationResultsDaily` | `System.Entity` | - | 8/0/0 |  |
| `Orion.IpSla.OneWayDelayOperationResultsDetail` | `System.Entity` | - | 4/0/0 |  |
| `Orion.IpSla.OneWayDelayOperationResultsHourly` | `System.Entity` | - | 8/0/0 |  |
| `Orion.IpSla.OperationAvailability` | `System.Entity` | - | 5/0/0 |  |
| `Orion.IpSla.OperationCurrentBasicMetrics` | `System.StatisticsEntity` | - | 13/0/0 |  |
| `Orion.IpSla.OperationCurrentHttpMetrics` | `System.StatisticsEntity` | - | 9/0/0 |  |
| `Orion.IpSla.OperationCurrentJitterLatencyPacketLoss` | `System.StatisticsEntity` | - | 12/0/0 |  |
| `Orion.IpSla.OperationCurrentMos` | `System.StatisticsEntity` | - | 6/0/0 |  |
| `Orion.IpSla.OperationCurrentOneWayDelay` | `System.StatisticsEntity` | - | 7/0/0 |  |
| `Orion.IpSla.OperationCurrentPathJitterLatencyPacketLoss` | `System.StatisticsEntity` | - | 8/0/0 |  |
| `Orion.IpSla.OperationCurrentStats` | `System.StatisticsEntity` | - | 22/1/0 |  |
| `Orion.IpSla.OperationLastRoundTripTime` | `System.Entity` | - | 2/0/0 |  |
| `Orion.IpSla.OperationParameterTypes` | `System.Entity` | - | 3/0/0 |  |
| `Orion.IpSla.OperationParameters` | `System.Entity` | - | 6/0/0 |  |
| `Orion.IpSla.OperationResultHealthStatsDaily` | `System.Entity` | - | 4/0/0 |  |
| `Orion.IpSla.OperationResultHealthStatsHourly` | `System.Entity` | - | 4/0/0 |  |
| `Orion.IpSla.OperationResultTypes` | `System.Entity` | - | 2/0/0 |  |
| `Orion.IpSla.OperationResults` | `System.Entity` | - | 9/0/0 |  |
| `Orion.IpSla.OperationResultsDaily` | `System.Entity` | - | 5/0/0 |  |
| `Orion.IpSla.OperationResultsDetail` | `System.Entity` | - | 6/0/0 |  |
| `Orion.IpSla.OperationResultsHourly` | `System.Entity` | - | 5/0/0 |  |
| `Orion.IpSla.OperationStates` | `System.Entity` | - | 2/1/0 |  |
| `Orion.IpSla.OperationStats` | `System.StatisticsEntity` | - | 47/1/0 |  |
| `Orion.IpSla.OperationStatuses` | `System.Entity` | - | 2/1/0 |  |
| `Orion.IpSla.OperationStdDevResultsDaily` | `System.Entity` | - | 8/0/0 |  |
| `Orion.IpSla.OperationStdDevResultsDetail` | `System.Entity` | - | 4/0/0 |  |
| `Orion.IpSla.OperationStdDevResultsHourly` | `System.Entity` | - | 8/0/0 |  |
| `Orion.IpSla.OperationThresholds` | `System.Entity` | - | 8/0/0 |  |
| `Orion.IpSla.OperationTypes` | `System.Entity` | - | 3/1/0 |  |
| `Orion.IpSla.OperationTypesThresholds` | `System.Entity` | - | 9/0/0 |  |
| `Orion.IpSla.OperationWebUri` | `System.ExtensionEntity` | - | 2/1/0 |  |
| `Orion.IpSla.Operations` | `System.ManagedEntity` | - | 26/17/0 |  |
| `Orion.IpSla.OperationsDHCP` | `System.Entity` | - | 10/0/0 |  |
| `Orion.IpSla.OperationsDNS` | `System.Entity` | - | 11/0/0 |  |
| `Orion.IpSla.OperationsFTP` | `System.Entity` | - | 11/0/0 |  |
| `Orion.IpSla.OperationsHTTP` | `System.Entity` | - | 15/0/0 |  |
| `Orion.IpSla.OperationsJitter` | `System.Entity` | - | 12/0/0 |  |
| `Orion.IpSla.OperationsMOS` | `System.Entity` | - | 9/0/0 |  |
| `Orion.IpSla.OperationsTCP` | `System.Entity` | - | 10/0/0 |  |
| `Orion.IpSla.OperationsUDPJitter` | `System.Entity` | - | 17/0/0 |  |
| `Orion.IpSla.OperationsVoIpUDPJitter` | `System.Entity` | - | 23/0/0 |  |
| `Orion.IpSla.PRIGatewayUtilization` | `System.Entity` | - | 9/1/0 |  |
| `Orion.IpSla.PacketLoss` | `System.Entity` | - | 9/0/0 |  |
| `Orion.IpSla.PathHopOperationCurrentStats` | `System.Entity` | - | 10/2/0 |  |
| `Orion.IpSla.PathHopOperationResults` | `System.Entity` | - | 19/1/0 |  |
| `Orion.IpSla.PathHops` | `System.Entity` | - | 4/2/0 |  |
| `Orion.IpSla.Paths` | `System.Entity` | - | 3/1/0 |  |
| `Orion.IpSla.RpmOperationStats` | `System.StatisticsEntity` | - | 12/1/0 |  |
| `Orion.IpSla.RpmTimestampOperationStats` | `System.StatisticsEntity` | - | 33/1/0 |  |
| `Orion.IpSla.Sites` | `System.Entity` | - | 7/1/0 |  |
| `Orion.IpSla.ThresholdTypes` | `System.Entity` | - | 3/0/0 |  |
| `Orion.IpSla.UdpJitterOperationStats` | `System.StatisticsEntity` | - | 18/1/0 |  |
| `Orion.IpSla.VoipCallDetails` | `System.StatisticsEntity` | - | 67/7/0 |  |
| `Orion.IpSla.VoipCallDetailsHist` | `System.StatisticsEntity` | - | 67/0/0 |  |
| `Orion.IpSla.VoipCallJitterMMA` | `System.StatisticsEntity` | - | 6/1/0 |  |
| `Orion.IpSla.VoipCallLatencyMMA` | `System.StatisticsEntity` | - | 6/1/0 |  |
| `Orion.IpSla.VoipCallMosMMA` | `System.StatisticsEntity` | - | 6/1/0 |  |
| `Orion.IpSla.VoipCallPacketLossMMA` | `System.StatisticsEntity` | - | 6/1/0 |  |
| `Orion.IpSla.VoipCalls` | `System.Entity` | - | 17/0/0 |  |
| `Orion.IpSla.VoipGatewayChannelStats` | `System.Entity` | - | 5/0/0 |  |
| `Orion.IpSla.VoipGatewayChannels` | `System.Entity` | - | 5/0/0 |  |
| `Orion.IpSla.VoipGatewayDetailCurrentStats` | `System.StatisticsEntity` | - | 21/1/0 |  |
| `Orion.IpSla.VoipGatewayDetailStats` | `System.StatisticsEntity` | - | 21/1/0 |  |
| `Orion.IpSla.VoipGatewayEndpointCurrentStats` | `System.StatisticsEntity` | - | 20/1/0 |  |
| `Orion.IpSla.VoipGatewayEndpointStats` | `System.StatisticsEntity` | - | 20/1/0 |  |
| `Orion.IpSla.VoipGatewayEndpointWebUri` | `System.ExtensionEntity` | - | 2/1/0 |  |
| `Orion.IpSla.VoipGatewayEndpoints` | `System.Entity` | - | 8/4/0 |  |
| `Orion.IpSla.VoipGatewaySipStats` | `System.StatisticsEntity` | - | 8/1/0 |  |
| `Orion.IpSla.VoipGatewaySipTrunkCallActivity` | `System.StatisticsEntity` | - | 4/1/0 |  |
| `Orion.IpSla.VoipGatewaySipTrunkStatusStats` | `System.StatisticsEntity` | - | 3/1/0 |  |
| `Orion.IpSla.VoipGatewaySipTrunkUtilization` | `System.StatisticsEntity` | - | 3/1/0 |  |
| `Orion.IpSla.VoipGatewaySipTrunks` | `System.ManagedEntity` | - | 9/4/0 |  |
| `Orion.IpSla.VoipGatewayStats` | `System.Entity` | - | 4/0/0 |  |
| `Orion.IpSla.VoipGatewayWebUri` | `System.ExtensionEntity` | - | 2/1/0 |  |
| `Orion.IpSla.VoipGateways` | `System.ManagedEntity` | - | 15/8/0 |  |
| `Orion.IpSla.VoipOperationParameterInfo` | `System.Entity` | - | 6/1/0 |  |
| `Orion.IpSla.VoipOperationsICMPEcho` | `System.Entity` | - | 10/0/0 |  |
| `Orion.IpSla.VoipOperationsUDPEcho` | `System.Entity` | - | 11/0/0 |  |
| `Orion.IpSla.VoipSuccessFailedCalls` | `System.StatisticsEntity` | - | 5/1/0 |  |
| `Orion.LazyUpgradeErrors` | `System.Entity` | - | 4/0/0 |  |
| `Orion.LazyUpgradeStatus` | `System.Entity` | - | 10/0/0 |  |
| `Orion.LicenseActivated` | `System.Indication` | r | 1/0/0 |  |
| `Orion.LicenseDeactivated` | `System.Indication` | r | 1/0/0 |  |
| `Orion.LicenseRemoved` | `System.Indication` | r | 1/0/0 |  |
| `Orion.LicenseSaturation` | `System.Entity` | - | 7/0/0 | Entity contains information about licensed elements and utilization of licenses. |
| `Orion.Licensing.ElementSubtypes` | `System.ManagedEntity` | r | 6/1/0 |  |
| `Orion.Licensing.ElementTypes` | `System.ManagedEntity` | r | 6/1/0 |  |
| `Orion.Licensing.Features` | `System.Entity` | r | 1/2/0 |  |
| `Orion.Licensing.LeaseChanged` | `System.Indication` | r | 2/0/0 |  |
| `Orion.Licensing.LicenseAssignments` | `System.Entity` | r | 6/2/0 |  |
| `Orion.Licensing.LicenseFilters` | `System.Entity` | c,d,r | 6/0/0 |  |
| `Orion.Licensing.Licenses` | `System.Entity` | i,r | 12/0/10 |  |
| `Orion.Licensing.SettingChanging` | `System.Indication` | r | 6/0/0 |  |
| `Orion.Licensing.UtilizationDetails` | `System.StatisticsEntity` | r | 6/1/0 |  |
| `Orion.Licensing.UtilizationSummary` | `System.StatisticsEntity` | r | 13/1/0 |  |
| `Orion.LimitationSnapshots` | `System.Entity` | - | 5/0/0 | Entity contains pre-eveluated informations about all objects which are involved by one limitations. |
| `Orion.LimitationTypes` | `System.Entity` | - | 11/0/0 | All types of limitation in Orion. (e.g."Group of Nodes", "Simple interface"). |
| `Orion.Limitations` | `System.Entity` | - | 4/0/3 | All defined limitations in Orion. |
| `Orion.LoadAverage` | `System.StatisticsEntity` | - | 12/1/0 | This entity contains historical load average data |
| `Orion.LogEntity` | `System.Entity` | - | 4/0/0 | Base class for SWIS entities which supposed to be indexed in Elasticsearch. |
| `Orion.MacPrefixes` | `System.Entity` | - | 4/0/0 | List of known MAC addresses prefixes, assigned to Organizations (a.k.a OUI) from IEEE standard |
| `Orion.MaintenancePlan` | `System.Entity` | c,d,r,u | 9/1/0 | Plan defining maintenance schedule for entities being unmanaged. |
| `Orion.MaintenancePlanAssignment` | `System.Entity` | c,d,r,u | 6/1/0 | Defines entity which is included in maintenance plan. |
| `Orion.Map` | `System.Entity` | - | 4/2/0 | Abstract entity for generic Map object. |
| `Orion.Map.Point` | `System.Entity` | - | 4/1/0 | Abstract entity for generic Map Point object. |
| `Orion.MapStudioFiles` | `System.Entity` | c,d,i,r,u | 11/1/7 |  |
| `Orion.Maps.Assets` | `System.Entity` | c,d,i,r,u | 15/0/0 | This entity represents the images uploaded by users using Maps editor. Each image asset can be used as the ba… |
| `Orion.Maps.Edges` | `System.Entity` | c,d,i,r,u | 16/0/0 | This entity represents the manual edges created from Orion Maps Editor between two managed entities. Each edg… |
| `Orion.Maps.GraphHistory` | `System.Entity` | c,d,i,r,u | 9/0/0 | This entity tracks changes to the underlying graph for an Orion Map. |
| `Orion.Maps.GraphMemberDefinitions` | `System.Entity` | - | 7/0/2 |  |
| `Orion.Maps.Graphs` | `Orion.Container` | i,r | 7/1/3 | This entity represents the data model for an Orion Map, that the user can store, reload or share with others,… |
| `Orion.Maps.HiddenTopologyConnections` | `System.Entity` | c,d,i,r,u | 10/0/0 |  |
| `Orion.Maps.ProjectHistory` | `System.Entity` | c,d,i,r,u | 10/0/0 | This entity tracks the edit history for a Project. |
| `Orion.Maps.Projects` | `System.Entity` | c,d,i,r,u | 13/1/4 | This entity represents the view of a Orion Maps Project, that the user can store, reload or share with others… |
| `Orion.Maps.TopologyConnections` | `Orion.TopologyConnections` | r | 0/0/0 | This entity represents the manual topology connections created from Orion Maps Editor between two orion nodes… |
| `Orion.Maps.TopologyEdges` | `System.Entity` | r | 17/0/0 | This entity represents the manual topology edges created from Orion Maps Editor between two managed entities.… |
| `Orion.MediaActionsProperties` | `System.Entity` | r | 4/0/0 | Some properties of "Play sound" and "Read message" actions that are used by Desktop Notification Tool. |
| `Orion.MemoryMultiLoad` | `System.StatisticsEntity` | - | 8/1/0 | This entity contains historical multi memory data |
| `Orion.MemoryMultiLoadCurrent` | `System.StatisticsEntity` | - | 8/0/0 |  |
| `Orion.Mibs.Management` | `System.Entity` | - | 0/0/1 |  |
| `Orion.MixedObjectType` | `System.Entity` | - | 3/0/0 | Base class for SWIS entities that contains records from multiple netobject types. E.g. Orion.Events |
| `Orion.NPM.CustomPollerAssignment` | `System.ManagedEntity` | - | 17/2/0 |  |
| `Orion.NPM.CustomPollerAssignmentOnInterface` | `Orion.NPM.CustomPollerAssignment` | c,d,i,r,u | 5/3/0 |  |
| `Orion.NPM.CustomPollerAssignmentOnNode` | `Orion.NPM.CustomPollerAssignment` | c,d,i,r,u | 5/4/0 |  |
| `Orion.NPM.CustomPollerAssignmentWebUri` | `System.Entity` | - | 2/1/0 |  |
| `Orion.NPM.CustomPollerLabels` | `System.Entity` | - | 3/0/0 |  |
| `Orion.NPM.CustomPollerStatistics` | `System.StatisticsEntity` | - | 10/1/0 |  |
| `Orion.NPM.CustomPollerStatus` | `System.Entity` | - | 8/0/0 |  |
| `Orion.NPM.CustomPollerStatusOnInterface` | `System.Entity` | - | 11/1/0 |  |
| `Orion.NPM.CustomPollerStatusOnNode` | `System.Entity` | - | 14/1/0 |  |
| `Orion.NPM.CustomPollerStatusOnNodeScalar` | `Orion.NPM.CustomPollerStatusOnNode` | - | 0/1/0 |  |
| `Orion.NPM.CustomPollerStatusOnNodeTabular` | `Orion.NPM.CustomPollerStatusOnNode` | - | 3/0/0 |  |
| `Orion.NPM.CustomPollerThresholds` | `System.Entity` | - | 3/0/0 |  |
| `Orion.NPM.CustomPollers` | `System.Entity` | - | 20/0/0 |  |
| `Orion.NPM.DiscoveredInterfaces` | `System.Entity` | r | 15/0/0 |  |
| `Orion.NPM.EW.Device` | `System.Entity` | - | 24/4/0 |  |
| `Orion.NPM.EW.DeviceDaily` | `System.Entity` | - | 18/0/0 |  |
| `Orion.NPM.EW.DeviceDetail` | `System.Entity` | - | 18/0/0 |  |
| `Orion.NPM.EW.DeviceHourly` | `System.Entity` | - | 18/0/0 |  |
| `Orion.NPM.EW.DeviceStats` | `System.StatisticsEntity` | - | 25/2/0 |  |
| `Orion.NPM.EW.Entity` | `System.Entity` | - | 43/4/0 |  |
| `Orion.NPM.EW.EntityDaily` | `System.Entity` | - | 20/0/0 |  |
| `Orion.NPM.EW.EntityDetail` | `System.Entity` | - | 19/0/0 |  |
| `Orion.NPM.EW.EntityHourly` | `System.Entity` | - | 20/0/0 |  |
| `Orion.NPM.EW.EntityStats` | `System.StatisticsEntity` | - | 26/1/0 |  |
| `Orion.NPM.EW.Event` | `System.Entity` | - | 17/1/0 |  |
| `Orion.NPM.EW.Neighbor` | `System.Entity` | - | 17/1/0 |  |
| `Orion.NPM.EW.Nodes` | `System.Entity` | - | 2/0/0 |  |
| `Orion.NPM.EW.Readiness` | `System.Entity` | - | 4/0/0 |  |
| `Orion.NPM.FCPorts` | `System.Entity` | - | 14/3/0 |  |
| `Orion.NPM.FCRevisions` | `System.Entity` | - | 8/1/0 |  |
| `Orion.NPM.FCSensors` | `System.Entity` | - | 14/1/0 |  |
| `Orion.NPM.FCUnits` | `System.Entity` | - | 13/4/0 |  |
| `Orion.NPM.InErrorsDiscardsThreshold` | `Orion.NPM.InterfacesThresholds` | - | 0/1/0 |  |
| `Orion.NPM.InPercentUtilizationThreshold` | `Orion.NPM.InterfacesThresholds` | - | 0/1/0 |  |
| `Orion.NPM.InterfaceAvailability` | `System.StatisticsEntity` | - | 6/1/0 |  |
| `Orion.NPM.InterfaceCustomPollers` | `Orion.NPM.CustomPollers` | - | 0/1/0 |  |
| `Orion.NPM.InterfaceErrors` | `System.StatisticsEntity` | - | 17/2/0 |  |
| `Orion.NPM.InterfaceNetObjectDowntime` | `System.Entity` | - | 8/1/0 |  |
| `Orion.NPM.InterfacePercentiles` | `System.Entity` | - | 11/0/0 |  |
| `Orion.NPM.InterfaceSettings` | `System.Entity` | - | 4/0/0 |  |
| `Orion.NPM.InterfaceTraffic` | `System.StatisticsEntity` | - | 33/2/0 |  |
| `Orion.NPM.InterfaceWebUri` | `System.Entity` | - | 4/1/0 |  |
| `Orion.NPM.Interfaces` | `System.ManagedEntity` | c,d,i,r,u | 92/58/10 | This entity presents information about Node interfaces |
| `Orion.NPM.InterfacesCustomProperties` | `System.CustomPropertiesEntity` | i,r,u | 1/1/4 |  |
| `Orion.NPM.InterfacesDashboard` | `System.Entity` | - | 21/0/0 |  |
| `Orion.NPM.InterfacesForecastCapacity` | `Orion.ForecastCapacity` | - | 3/1/0 |  |
| `Orion.NPM.InterfacesRelationship` | `System.Entity` | - | 6/3/0 |  |
| `Orion.NPM.InterfacesRelationshipType` | `System.Entity` | - | 2/1/0 |  |
| `Orion.NPM.InterfacesThresholds` | `Orion.Thresholds` | - | 1/0/0 |  |
| `Orion.NPM.MulticastRouting.DataHistory` | `System.StatisticsEntity` | - | 6/2/0 |  |
| `Orion.NPM.MulticastRouting.GroupNodeInterfaces` | `System.Entity` | - | 8/2/0 |  |
| `Orion.NPM.MulticastRouting.GroupNodes` | `System.Entity` | - | 12/5/0 |  |
| `Orion.NPM.MulticastRouting.GroupTranslation` | `System.Entity` | - | 4/1/0 |  |
| `Orion.NPM.MulticastRouting.GroupWebUri` | `System.Entity` | - | 2/1/0 |  |
| `Orion.NPM.MulticastRouting.Groups` | `System.Entity` | - | 10/3/0 |  |
| `Orion.NPM.MulticastRouting.Interfaces` | `System.Entity` | - | 17/2/0 |  |
| `Orion.NPM.MulticastRouting.MulticastRoutingProtocol` | `System.Entity` | - | 2/0/0 |  |
| `Orion.NPM.MulticastRouting.MulticastRoutingTableChanges` | `System.Entity` | - | 17/2/0 |  |
| `Orion.NPM.MulticastRouting.MulticastRoutingTableReport` | `System.Entity` | - | 27/5/0 |  |
| `Orion.NPM.MulticastRouting.PIMNeighbors` | `System.Entity` | - | 10/1/0 |  |
| `Orion.NPM.MulticastRouting.RendezvousPoints` | `System.Entity` | - | 9/1/0 |  |
| `Orion.NPM.MulticastRouting.RoutingTable` | `System.Entity` | - | 27/5/0 |  |
| `Orion.NPM.MulticastRouting.Sources` | `System.Entity` | - | 6/2/0 |  |
| `Orion.NPM.NodeChildStatusCustomPollers` | `Orion.NodeChildStatusContributors` | - | 0/0/0 |  |
| `Orion.NPM.NodeChildStatusInterfaces` | `Orion.NodeChildStatusContributors` | - | 0/0/0 |  |
| `Orion.NPM.NodeCustomPollers` | `Orion.NPM.CustomPollers` | - | 0/1/0 |  |
| `Orion.NPM.Nodes` | `System.Entity` | - | 13/1/0 |  |
| `Orion.NPM.OrionSwitchPortMapping` | `System.Entity` | - | 27/4/0 |  |
| `Orion.NPM.OutErrorsDiscardsThreshold` | `Orion.NPM.InterfacesThresholds` | - | 0/1/0 |  |
| `Orion.NPM.OutPercentUtilizationThreshold` | `Orion.NPM.InterfacesThresholds` | - | 0/1/0 |  |
| `Orion.NPM.RealTime.Interfaces.Statistics` | `System.StatisticsEntity` | r | 10/0/0 | Entity to publish results of real time polling for Orion.NPM.Interfaces entity. Used in SWIS (SUBSCRIBE CHANG… |
| `Orion.NPM.SwitchStack` | `System.Entity` | - | 15/3/0 |  |
| `Orion.NPM.SwitchStackMember` | `System.Entity` | - | 18/2/0 |  |
| `Orion.NPM.SwitchStackMemberPort` | `System.Entity` | - | 6/1/0 |  |
| `Orion.NPM.SwitchStackPower` | `System.Entity` | - | 10/2/0 |  |
| `Orion.NPM.SwitchStackPowerPort` | `System.Entity` | - | 10/1/0 |  |
| `Orion.NPM.VSANs` | `System.Entity` | - | 14/4/0 |  |
| `Orion.NPM.VsanCurrentStats` | `System.Entity` | - | 13/1/0 |  |
| `Orion.NPM.VsanErrors` | `System.StatisticsEntity` | - | 6/1/0 |  |
| `Orion.NPM.VsanTraffic` | `System.StatisticsEntity` | - | 8/1/0 |  |
| `Orion.NPM.WL.APs` | `System.Entity` | - | 15/0/0 |  |
| `Orion.NPM.WL.Clients` | `System.Entity` | - | 23/0/0 |  |
| `Orion.NPM.WL.Controllers` | `System.Entity` | - | 12/0/0 |  |
| `Orion.NPM.WL.Interfaces` | `System.Entity` | - | 16/0/0 |  |
| `Orion.NPM.Wireless.Clients` | `System.Entity` | - | 22/0/0 |  |
| `Orion.NPM.Wireless.Interface` | `System.Entity` | - | 22/0/0 |  |
| `Orion.NetObjectDowntime` | `System.Entity` | c,d,i,r,u | 8/1/0 | Downtime object for Downtime Monitoring. |
| `Orion.NetObjectTypes` | `System.Entity` | - | 6/0/0 | Entity provides all needed information about unique mapping between entity and netobject. |
| `Orion.NetObjectTypesExt` | `System.Entity` | - | 7/0/0 | Entity provides all needed information about mapping between entity and netobject. It allows multiple mapping… |
| `Orion.NetPath.EndpointServiceAssignments` | `System.Entity` | c,d,i,r,u | 6/5/0 | Contains the assignments between probes and the services they monitor. A probe can monitor multiple services,… |
| `Orion.NetPath.EndpointServiceProperties` | `System.Entity` | c,d,i,r,u | 5/2/0 | Table holds settings for Probe and particular EndpointService if specified. Values are inherited from less sp… |
| `Orion.NetPath.EndpointServices` | `System.ManagedEntity` | r | 14/2/0 | Contains configuration information for NPM NetPath services to monitor. |
| `Orion.NetPath.Networks` | `System.Entity` | c,d,i,r,u | 7/0/0 | Contains BGP information about the nodes and endpoints discovered during probing. This includes the autonomou… |
| `Orion.NetPath.Performances` | `System.Entity` | - | 19/1/0 | Contains packet loss and latency information for nodes and edges. |
| `Orion.NetPath.Probes` | `System.Entity` | r | 8/6/0 | Contains NPM NetPath probe information. The probing is done from probes. A user can install multiple probes a… |
| `Orion.NetPath.ServiceAssignments` | `Orion.NetPath.ServiceAssignmentsBase` | r | 1/6/0 | Designed to use in Alerting. Contains the assignments between NPM NetPath probes and the NPM NetPath services… |
| `Orion.NetPath.ServiceAssignmentsBase` | `System.ManagedEntity` | - | 19/0/0 | Designed to use in Alerting. Contains the assignments between all NetPath probes and all NetPath services the… |
| `Orion.NetPath.Tests` | `System.Entity` | - | 22/1/0 | Contains probing results, including the summary and graph displayed to the user. |
| `Orion.NetPath.ThresholdTypes` | `System.Entity` | - | 7/1/0 | The set of threshold types used to determine the status of a monitored service. |
| `Orion.NetPath.Thresholds` | `System.Entity` | c,d,i,r,u | 7/3/0 | Contains custom status threshold values for a probe and service assignment. |
| `Orion.NetPath.Traces` | `System.Entity` | - | 4/1/0 | Contains the path details as compressed Json. Each entry contains all traces for an associated test. There is… |
| `Orion.Netflow.AdvancedApplications` | `System.Entity` | - | 7/9/0 |  |
| `Orion.Netflow.Applications` | `System.Entity` | - | 9/8/0 |  |
| `Orion.Netflow.AutonomousSystems` | `System.Entity` | - | 5/16/0 |  |
| `Orion.Netflow.CBQoSClassMap` | `System.Entity` | - | 3/1/0 |  |
| `Orion.Netflow.CBQoSConfigurationDetails` | `System.Entity` | - | 20/0/0 |  |
| `Orion.Netflow.CBQoSDetail` | `System.Entity` | - | 4/0/0 |  |
| `Orion.Netflow.CBQoSDirectionDescription` | `System.Entity` | - | 2/1/0 |  |
| `Orion.Netflow.CBQoSPolicy` | `System.Entity` | - | 16/8/0 |  |
| `Orion.Netflow.CBQoSPolicyAction` | `System.Entity` | - | 4/2/0 |  |
| `Orion.Netflow.CBQoSPolicyClassPaths` | `System.Entity` | - | 5/0/0 |  |
| `Orion.Netflow.CBQoSPolicyMap` | `System.Entity` | - | 3/1/0 |  |
| `Orion.Netflow.CBQoSPolicyMetric` | `System.Entity` | - | 6/3/0 |  |
| `Orion.Netflow.CBQoSSource` | `System.Entity` | c,d,r,u | 8/2/0 |  |
| `Orion.Netflow.CBQoSStatistics` | `System.StatisticsEntity` | - | 6/3/0 |  |
| `Orion.Netflow.CBQoSStatisticsDescription` | `System.Entity` | - | 2/2/0 |  |
| `Orion.Netflow.CBQoSTop` | `System.Entity` | - | 15/0/0 |  |
| `Orion.Netflow.CorrelationPostDNS` | `System.Entity` | - | 7/0/0 |  |
| `Orion.Netflow.Countries` | `System.Entity` | - | 2/17/0 |  |
| `Orion.Netflow.Diagnostics.Database` | `System.Entity` | c,d,r,u | 4/0/0 |  |
| `Orion.Netflow.Diagnostics.Partitions` | `System.Entity` | c,d,r,u | 3/0/0 |  |
| `Orion.Netflow.Diagnostics.Tables` | `System.Entity` | c,d,r,u | 5/0/0 |  |
| `Orion.Netflow.FlowEngines` | `System.Entity` | - | 4/1/0 |  |
| `Orion.Netflow.Flows` | `System.StatisticsEntity` | - | 43/14/0 |  |
| `Orion.Netflow.FlowsByAS` | `System.StatisticsEntity` | - | 43/13/0 |  |
| `Orion.Netflow.FlowsByAdvancedApplication` | `System.StatisticsEntity` | - | 18/3/0 |  |
| `Orion.Netflow.FlowsByApplication` | `System.StatisticsEntity` | - | 21/3/0 |  |
| `Orion.Netflow.FlowsByConversation` | `System.StatisticsEntity` | - | 42/13/0 |  |
| `Orion.Netflow.FlowsByCountryCode` | `System.StatisticsEntity` | - | 43/14/0 |  |
| `Orion.Netflow.FlowsByDomain` | `System.StatisticsEntity` | - | 44/13/0 |  |
| `Orion.Netflow.FlowsByHostname` | `System.StatisticsEntity` | - | 51/14/0 |  |
| `Orion.Netflow.FlowsByIP` | `System.StatisticsEntity` | - | 51/14/0 |  |
| `Orion.Netflow.FlowsByInterface` | `System.StatisticsEntity` | - | 44/14/0 |  |
| `Orion.Netflow.FlowsByInterfaceByConversation` | `System.StatisticsEntity` | - | 44/0/0 |  |
| `Orion.Netflow.FlowsWLC` | `System.StatisticsEntity` | - | 17/3/0 |  |
| `Orion.Netflow.Hostnames` | `System.Entity` | - | 2/0/0 |  |
| `Orion.Netflow.IP2Country` | `System.Entity` | - | 3/0/0 |  |
| `Orion.Netflow.IPAddressGroupRanges` | `System.Entity` | - | 10/0/0 |  |
| `Orion.Netflow.IPAddressGroups` | `System.Entity` | - | 3/20/0 |  |
| `Orion.Netflow.IPGroupSegments` | `System.Entity` | - | 3/1/0 |  |
| `Orion.Netflow.IPGroupsBySegments` | `System.Entity` | - | 3/1/0 |  |
| `Orion.Netflow.InterfaceSources` | `System.Entity` | i,r | 12/0/3 |  |
| `Orion.Netflow.NetFlowEnginesStatistics` | `System.Entity` | - | 3/0/0 |  |
| `Orion.Netflow.NodeProperties` | `System.Entity` | c,i,r,u | 7/0/0 |  |
| `Orion.Netflow.NodeSources` | `System.Entity` | i,r | 6/2/4 |  |
| `Orion.Netflow.NodeStatistics` | `System.StatisticsEntity` | - | 5/1/0 |  |
| `Orion.Netflow.Protocols` | `System.Entity` | - | 4/8/0 |  |
| `Orion.Netflow.Source` | `System.Entity` | i,r | 16/2/0 |  |
| `Orion.Netflow.TrafficClass` | `System.Entity` | - | 2/1/0 |  |
| `Orion.Netflow.TypesOfService` | `System.Entity` | - | 4/9/0 |  |
| `Orion.NetworkAtlas` | `System.Entity` | - | 0/0/1 | Information about installed Network Atlas application. |
| `Orion.Nexus.VirtualPortChannel` | `System.Entity` | - | 11/5/0 | List of Nexus Virtual Port Channels |
| `Orion.Nexus.VirtualPortChannelInterfaces` | `System.Entity` | - | 4/2/0 |  |
| `Orion.NexusVpc.Dashboard` | `System.DashboardEntity` | - | 26/0/0 |  |
| `Orion.NodeCategories` | `System.Entity` | r | 2/0/0 | Lists possible Node categories such as Server, Network device. |
| `Orion.NodeCdpEntry` | `System.Entity` | - | 6/0/0 |  |
| `Orion.NodeChildStatusContributors` | `System.Entity` | - | 6/0/0 | Base entity for modules to plug into enhanced node child status - list of current status contributors. |
| `Orion.NodeChildStatusDetail` | `System.Entity` | - | 7/0/0 | Provides list of node child entities that affect current enhanced node status. |
| `Orion.NodeChildStatusParticipation` | `System.Entity` | r,u | 4/0/0 |  |
| `Orion.NodeChildStatusThresholds` | `Orion.NodeChildStatusContributors` | - | 0/0/0 |  |
| `Orion.NodeChildStatusVolumes` | `Orion.NodeChildStatusContributors` | - | 0/0/0 | Plugin into enhanced node child status for volumes - list of current status contributors. |
| `Orion.NodeIPAddresses` | `System.Entity` | - | 6/2/0 |  |
| `Orion.NodeL2Connections` | `System.Entity` | - | 5/0/0 |  |
| `Orion.NodeL3Entries` | `System.Entity` | - | 5/0/0 |  |
| `Orion.NodeL3RoutingData` | `System.Entity` | - | 6/0/0 |  |
| `Orion.NodeLldpEntry` | `System.Entity` | - | 7/0/0 |  |
| `Orion.NodeMACAddresses` | `System.Entity` | - | 3/0/0 |  |
| `Orion.NodeNotes` | `System.Entity` | c,d,i,r,u | 5/0/0 | Notes associated to the nodes. |
| `Orion.NodePortInterfaceMap` | `System.Entity` | - | 6/2/0 |  |
| `Orion.NodeSettings` | `System.Entity` | c,d,i,r,u | 4/0/0 |  |
| `Orion.NodeVlans` | `System.Entity` | - | 10/2/0 |  |
| `Orion.NodeWebUri` | `System.Entity` | - | 2/1/0 |  |
| `Orion.Nodes` | `System.ManagedEntity` | c,d,i,r,u | 102/161/17 |  |
| `Orion.NodesCustomProperties` | `System.CustomPropertiesEntity` | i,r,u | 1/1/5 |  |
| `Orion.NodesForecastCapacity` | `Orion.ForecastCapacity` | - | 3/1/0 | Capacity Forecasting for Nodes. |
| `Orion.NodesOtherStatusCount` | `System.Entity` | - | 2/0/0 | Calculates the number of nodes in other status categories for Nodes KPI widget in New Home Summary |
| `Orion.NodesOtherStatusIds` | `System.Entity` | - | 1/0/0 | Single row value of joined other status IDs for Nodes KPI widget in New Home Summary. Used as URL parameter t… |
| `Orion.NodesStats` | `System.ExtensionEntity` | - | 28/1/0 |  |
| `Orion.NodesThresholds` | `Orion.Thresholds` | - | 0/0/0 |  |
| `Orion.NodesWebCommunityStrings` | `System.ExtensionEntity` | - | 2/1/0 | Node web community strings. |
| `Orion.NotificationItemGrouped` | `System.Entity` | i,r | 11/0/5 | This entity contains grouped notification item data. |
| `Orion.NotificationTypePermission` | `System.Entity` | - | 2/0/0 | This entity contains mapping between notification item types and required role ids. |
| `Orion.Nutanix.DiscoveryMetadata` | `System.Entity` | r | 12/4/0 | Nutanix Discovery Metadata - contains significant information about Nutanix element, mainly for polling. |
| `Orion.Nutanix.DiscoveryMetadataMapping` | `System.Entity` | r | 3/0/0 | Nutanix Discovery Metadata Entity Mapping |
| `Orion.OLM.AlertMessage` | `System.Indication` | - | 11/1/0 | Indication sent to Orion alerting when a message meets rule conditions. |
| `Orion.OLM.HealthIssues` | `System.Entity` | c,d,r,u | 7/0/0 | Stores health information related to Log node, agent assigned to node and Log profile on that node. |
| `Orion.OLM.LicenseExpiration` | `System.Indication` | - | 0/0/0 | Indication, which informs log services about license expiration. |
| `Orion.OLM.LicenseReset` | `System.Indication` | - | 0/0/0 | Indication, which informs log services about license reset. |
| `Orion.OLM.LogEntry` | `System.Entity` | r | 10/5/3 | Stored messages or events. |
| `Orion.OLM.LogEntryFieldValue` | `System.Entity` | r | 7/1/0 | Values of log entry fields. |
| `Orion.OLM.LogEntryLevel` | `System.Entity` | - | 3/0/0 | Log entry levels defining severity. The list is unified across various log types. |
| `Orion.OLM.LogEntrySecondarySourceAssignment` | `System.Entity` | - | 2/0/0 | Relation between log entries and secondary sources. |
| `Orion.OLM.LogEntrySecondarySources` | `System.Entity` | - | 3/1/0 | Secondary sources for messages. Messages have relation to Orion nodes and in some cases they can also have se… |
| `Orion.OLM.LogEntryTagAssignment` | `System.Entity` | - | 2/0/0 | Relation between log entries and tags. |
| `Orion.OLM.LogEntryType` | `System.Entity` | r,u | 5/1/0 | Types of log sources, for example Syslog, Trap ... Each type has retention period after which messages are de… |
| `Orion.OLM.LogProfile` | `System.Entity` | c,d,r,u | 4/1/0 | Profiles used for configuring log file collection. |
| `Orion.OLM.LogProfileAgentAssignment` | `System.Entity` | c,d,r,u | 2/0/0 | Relation between log profiles and agents. |
| `Orion.OLM.MessageSources` | `System.Entity` | c,d,r,u | 9/2/0 | Message sources are IP addresses from which Log Viewer received a message or event. They can be licensed, unl… |
| `Orion.OLM.NodeInfosChanged` | `System.Indication` | - | 1/0/0 | Indication informs when node infos were updated in business layer. |
| `Orion.OLM.NodeLicensingChange` | `System.Indication` | - | 0/0/0 | Indication, which informs log services about changes in node licensed for log monitoring. |
| `Orion.OLM.Nodes` | `System.Entity` | i,r | 3/1/2 | Orion nodes licensed for gathering messages and events. If there is more message sources with the same NodeID… |
| `Orion.OLM.ProcessingRule` | `System.Entity` | i,r | 4/1/6 | Rules used for processing log entries. |
| `Orion.OLM.ProcessingRuleActions` | `System.Entity` | r | 4/1/0 | Actions triggered when rule conditions are met. |
| `Orion.OLM.RuleProcessingDefinitions` | `System.Entity` | r | 3/0/0 | Rule processing definitions in JSON format. You can subscribe to this entity to be notified about changes. |
| `Orion.OLM.Tags` | `System.Entity` | - | 3/1/0 | Custom and out of the box tags which can be assigned to log entries. |
| `Orion.Orchestrators.Devices` | `System.Entity` | - | 12/1/0 |  |
| `Orion.Orchestrators.Info` | `System.ManagedEntity` | - | 15/4/29 | Orion Orchestrator Info |
| `Orion.Orchestrators.Nodes` | `System.Entity` | - | 10/2/0 |  |
| `Orion.OrionServers` | `System.Entity` | c,d,i,r,u | 12/5/0 | Represents Orion servers (MPE, APE, AW). |
| `Orion.OtherEvent` | `System.Indication` | - | 1/0/0 | Used to track various audit events |
| `Orion.OutInterfaceAverageTrafficUtilizationByDays` | `Orion.UsageByDays` | - | 1/0/0 |  |
| `Orion.PM.DatabaseHelper` | `System.Entity` | - | 0/0/6 |  |
| `Orion.PM.InstalledProducts` | `System.Entity` | - | 31/0/0 |  |
| `Orion.PM.Management` | `System.Entity` | - | 0/0/10 |  |
| `Orion.PM.PAS.Tasks` | `System.Entity` | - | 7/0/0 |  |
| `Orion.PM.PAS.UpdatesOrionEntities` | `System.Entity` | - | 12/0/0 |  |
| `Orion.PM.PAS.WsusNodesOrionNodes` | `System.Entity` | - | 27/0/0 |  |
| `Orion.PM.PAS.WsusServerNodes` | `System.Entity` | - | 12/0/0 |  |
| `Orion.PM.PAS.WsusServers` | `System.Entity` | - | 20/0/0 |  |
| `Orion.PM.TaskBroker` | `System.Entity` | - | 0/0/5 |  |
| `Orion.PM.UpdateServicesServer` | `System.Entity` | - | 7/0/0 |  |
| `Orion.PM.Updates` | `System.Entity` | - | 32/0/0 |  |
| `Orion.PM.WMI_InstalledProducts` | `System.Entity` | - | 34/0/0 |  |
| `Orion.PM.WSUS_ApprovedUpdatesInstallationSummaryInfo` | `System.Entity` | - | 83/0/0 |  |
| `Orion.PM.WSUS_ApprovedUpdatesInstallationSummaryInfoWithApprovalDetails` | `System.Entity` | - | 94/0/0 |  |
| `Orion.PM.WSUS_ComputerToUpdatesWithStatusAndDetails` | `System.Entity` | - | 89/0/0 |  |
| `Orion.PM.WSUS_ComputerUpdateStatusToComputerView` | `System.Entity` | - | 37/0/0 |  |
| `Orion.PM.WSUS_ComputerUpdateStatusToUpdatesView` | `System.Entity` | - | 72/0/0 |  |
| `Orion.PM.WSUS_ComputerUpdateStatusWithApprovals` | `System.Entity` | - | 98/0/0 |  |
| `Orion.PM.WSUS_UpdatesWithEffectiveApprovalsByGroup` | `System.Entity` | - | 72/0/0 |  |
| `Orion.PM.WsusGroups` | `System.Entity` | - | 6/0/0 |  |
| `Orion.PM.WsusNodes` | `System.Entity` | - | 22/0/0 |  |
| `Orion.PM.WsusNodesUpdates` | `System.Entity` | - | 6/0/0 |  |
| `Orion.PM.WsusServers` | `System.Entity` | - | 28/0/0 |  |
| `Orion.PM.device` | `System.Entity` | - | 17/0/0 |  |
| `Orion.PM.dt_wsus_computers` | `System.Entity` | - | 52/0/0 |  |
| `Orion.PM.dt_wsus_updates` | `System.Entity` | - | 43/0/0 |  |
| `Orion.PM.dt_wsus_updates_installinfo_details` | `System.Entity` | - | 5/0/0 |  |
| `Orion.PM.ewTaskViewHistory` | `System.Entity` | - | 29/0/0 |  |
| `Orion.PM.ewtasks` | `System.Entity` | - | 8/1/0 |  |
| `Orion.PM.ewtasksresults` | `System.Entity` | - | 12/1/0 |  |
| `Orion.Package` | `System.Entity` | - | 2/0/0 |  |
| `Orion.Packages.Wireless.AccessPoints` | `Orion.Packages.Wireless.Entity` | - | 20/3/0 |  |
| `Orion.Packages.Wireless.AccessPoints.Autonomous` | `Orion.Packages.Wireless.Entity` | - | 12/0/0 |  |
| `Orion.Packages.Wireless.AccessPoints.Thin` | `Orion.Packages.Wireless.Entity` | - | 16/1/0 |  |
| `Orion.Packages.Wireless.AccessPoints.Thin.WebUri` | `System.Entity` | - | 2/1/0 |  |
| `Orion.Packages.Wireless.Clients` | `Orion.Packages.Wireless.Entity` | - | 22/2/0 |  |
| `Orion.Packages.Wireless.ClientsSessionHistory` | `System.Entity` | - | 16/0/0 |  |
| `Orion.Packages.Wireless.Controllers` | `Orion.Packages.Wireless.Entity` | - | 9/3/0 |  |
| `Orion.Packages.Wireless.Entity` | `System.Entity` | - | 8/0/0 |  |
| `Orion.Packages.Wireless.HistoricalAccessPoints` | `Orion.Packages.Wireless.StatisticsHistoryEntity` | - | 1/1/0 |  |
| `Orion.Packages.Wireless.HistoricalClients` | `Orion.Packages.Wireless.HistoryEntity` | - | 30/1/0 |  |
| `Orion.Packages.Wireless.HistoricalInterfaces` | `Orion.Packages.Wireless.StatisticsHistoryEntity` | - | 1/1/0 |  |
| `Orion.Packages.Wireless.HistoricalRogues` | `Orion.Packages.Wireless.HistoryEntity` | - | 5/1/0 |  |
| `Orion.Packages.Wireless.HistoryEntity` | `System.StatisticsEntity` | - | 6/0/0 |  |
| `Orion.Packages.Wireless.Indexes` | `System.Entity` | - | 6/0/0 |  |
| `Orion.Packages.Wireless.Interfaces` | `Orion.Packages.Wireless.Entity` | - | 18/3/0 |  |
| `Orion.Packages.Wireless.Rogues` | `Orion.Packages.Wireless.Entity` | - | 5/2/0 |  |
| `Orion.Packages.Wireless.SSIDs` | `System.Entity` | - | 3/0/0 |  |
| `Orion.Packages.Wireless.StatisticsHistoryEntity` | `Orion.Packages.Wireless.HistoryEntity` | - | 23/0/0 |  |
| `Orion.Packages.Wireless.SwitchPortMapping` | `System.Entity` | - | 24/1/0 |  |
| `Orion.PasswordHistory` | `System.Entity` | c,d,i,r,u | 6/0/0 | This entity represents password history for user accounts |
| `Orion.PercentDiskUsedThreshold` | `Orion.VolumesThresholds` | - | 0/1/0 |  |
| `Orion.PercentLossThreshold` | `Orion.NodesThresholds` | - | 0/1/0 |  |
| `Orion.PercentMemoryUsedThreshold` | `Orion.NodesThresholds` | - | 0/1/0 |  |
| `Orion.PerfStack.Projects` | `System.Entity` | c,d,i,r,u | 9/0/0 | This entity represents the view of a Performance Analysis Project, that the user can store, reload or share w… |
| `Orion.PerfStack.StatisticsEntity` | `System.StatisticsEntity` | c,d,i,r,u | 4/0/0 |  |
| `Orion.PerformanceCounters` | `System.Entity` | - | 4/0/0 |  |
| `Orion.Poe.DeviceGroup` | `System.Entity` | - | 10/1/0 |  |
| `Orion.Poe.DeviceGroupStatistics` | `System.StatisticsEntity` | - | 7/1/0 |  |
| `Orion.Poe.Port` | `System.Entity` | - | 14/0/0 |  |
| `Orion.PolicyEngine.AssignedPolicy` | `System.Entity` | r | 11/2/0 | This entity represents one assignment of a policy to an entity. |
| `Orion.PolicyEngine.AssignedRule` | `System.Entity` | r | 19/7/0 | This entity represents one assignment of a rule to an entity. |
| `Orion.PolicyEngine.AssignedRuleDataSource` | `System.Entity` | r | 7/2/0 | This entity represents one assignment of a datasource to an entity. |
| `Orion.PolicyEngine.AssignedRuleError` | `System.Entity` | r | 10/3/0 | This entity represents errors after last evaluation of an assigned rule. |
| `Orion.PolicyEngine.AssignedRuleFailed` | `System.Indication` | - | 5/1/0 | This indication is triggered when status of a rule is changed to Failed. |
| `Orion.PolicyEngine.AssignedRuleStatistics` | `System.StatisticsEntity` | r | 6/1/0 | This entity contains the status history of Orion.PolicyEngine.AssignedRule |
| `Orion.PolicyEngine.DataSource` | `System.Entity` | r | 4/0/0 | This entity represents a source of data to be collected for evaluation of a rule. |
| `Orion.PolicyEngine.ErrorType` | `System.Entity` | r | 3/1/0 | This entity represents a category of an error. |
| `Orion.PolicyEngine.Policy` | `System.ManagedEntity` | d,i,r,u | 10/4/5 | This entity represents a policy, which is a group of rules. |
| `Orion.PolicyEngine.PolicyCompliance` | `System.Entity` | d,i,r,u | 4/1/0 | This entity groups together all policy assignments by their policy. It can be used in alerting and reporting. |
| `Orion.PolicyEngine.PolicyComplianceChange` | `System.Indication` | - | 2/1/0 | This indication is triggered when number of evaluated, passed or failed rules are changed after evaluation. |
| `Orion.PolicyEngine.Rule` | `System.Entity` | r,u | 15/2/0 | This entity represents a rule. |
| `Orion.PollNow` | `System.Indication` | - | 0/0/0 |  |
| `Orion.Pollers` | `System.Entity` | c,d,i,r,u | 6/0/0 |  |
| `Orion.PollingErrors` | `System.Entity` | c,d,i,r,u | 7/1/0 | Entity that stores data about polling errors |
| `Orion.PollingUsage` | `System.Entity` | - | 4/1/0 | Entity contains information about each polling usage (in percent). |
| `Orion.PortItems` | `System.Entity` | - | 11/0/0 |  |
| `Orion.ProcessDiscoveryResults` | `System.Indication` | - | 0/0/0 |  |
| `Orion.QBM.EntityMetrics` | `Orion.QBM.Metrics` | - | 0/0/0 |  |
| `Orion.QBM.Keys` | `System.Entity` | - | 5/1/0 |  |
| `Orion.QBM.Metrics` | `System.Entity` | - | 5/1/0 |  |
| `Orion.QBM.Queries` | `System.ManagedEntity` | - | 9/2/0 |  |
| `Orion.QBM.SummaryMetrics` | `Orion.QBM.Metrics` | - | 0/0/0 |  |
| `Orion.ReachabilityInfo` | `System.Entity` | - | 7/2/0 | List of host names and IP addresses of all polling engines. |
| `Orion.RealTime.Nodes.Statistics` | `System.StatisticsEntity` | r | 3/0/0 | Entity to publish results of real time polling for Orion.Nodes entity. Used in SWIS (SUBSCRIBE CHANGES TO Ori… |
| `Orion.RealTime.Volumes.Statistics` | `System.StatisticsEntity` | r | 7/0/0 | Entity to publish results of real time polling for Orion.Volumes entity. Used in SWIS (SUBSCRIBE CHANGES TO O… |
| `Orion.Recommendations.Actions` | `System.Entity` | - | 13/1/0 | Entity which provides access to all actions which belong to recommendations. |
| `Orion.Recommendations.ActiveRecommendations` | `Orion.Recommendations.RecommendationsBase` | - | 0/2/0 | Entity which provides access to all recommendation in system (active, predictive, scheduled, finished). |
| `Orion.Recommendations.ConstraintChanged` | `System.Indication` | - | 0/0/0 | Indication reported when any constraint has changed. |
| `Orion.Recommendations.ConstraintObjects` | `System.Entity` | - | 4/1/0 | Entity which provides access to constraint objects. |
| `Orion.Recommendations.ConstraintParameters` | `System.Entity` | - | 2/1/0 | Entity which provides access to constraint objects parameters. |
| `Orion.Recommendations.Constraints` | `System.Entity` | - | 9/2/0 | Entity which provides access to configured constraints. |
| `Orion.Recommendations.DataGroupInfo` | `System.Entity` | - | 4/2/0 | Entity which provides information about data groups available in the environment. |
| `Orion.Recommendations.Dependencies` | `System.Entity` | - | 4/1/0 | Entity which provides information about recommendation dependencies. |
| `Orion.Recommendations.GroupChanged` | `System.Indication` | - | 0/0/0 | Indication reported when data group for recommendations computation changed. |
| `Orion.Recommendations.JobCanceled` | `System.Indication` | - | 0/0/0 | Indication reported when computation job is canceled. |
| `Orion.Recommendations.JobCreated` | `System.Indication` | - | 0/0/0 | Indication reported when computation job was created. |
| `Orion.Recommendations.JobFinished` | `System.Indication` | - | 0/0/0 | Indication reported when computation job finished. |
| `Orion.Recommendations.JobStarted` | `System.Indication` | - | 0/0/0 | Indication reported when computation job started. |
| `Orion.Recommendations.Jobs` | `System.Entity` | - | 6/1/0 | Entity which provides information about computation jobs. |
| `Orion.Recommendations.Justifications` | `System.Entity` | - | 5/1/0 | Entity which provides access to recommendations justifications. |
| `Orion.Recommendations.RecommendationChanged` | `System.Indication` | - | 0/0/0 | Indication reported when recommendation has changed. |
| `Orion.Recommendations.RecommendationsBase` | `System.Entity` | - | 12/4/0 | Base entity holding recommendations information. |
| `Orion.Recommendations.Strategies` | `System.Entity` | - | 5/2/0 | Entity which provides information about strategies configured by available modules. |
| `Orion.Recommendations.StrategiesGroup` | `System.Entity` | - | 3/1/0 | Entity which provides information about strategy groups configured by available modules. |
| `Orion.Rediscovery` | `System.Indication` | - | 0/0/0 |  |
| `Orion.Report` | `System.Entity` | i,r,u | 16/2/4 |  |
| `Orion.ReportFavorites` | `System.Entity` | i,r,u | 2/0/2 |  |
| `Orion.ReportGenerated` | `System.Indication` | - | 1/0/0 | Occurs when user generates report |
| `Orion.ReportJobData` | `System.Entity` | - | 3/0/0 |  |
| `Orion.ReportJobDefinitions` | `System.Entity` | - | 2/0/0 |  |
| `Orion.ReportJobExecuted` | `System.Indication` | - | 2/0/0 | Occurs when user executes report schedule |
| `Orion.ReportJobUrls` | `System.Entity` | - | 2/0/0 |  |
| `Orion.ReportJobs` | `System.Entity` | - | 14/0/0 |  |
| `Orion.ReportSchedules` | `System.Entity` | - | 2/0/0 |  |
| `Orion.Reporting` | `System.Entity` | - | 0/0/1 |  |
| `Orion.ReportsCustomProperties` | `System.CustomPropertiesEntity` | i,r,u | 0/1/5 |  |
| `Orion.ResourceProperties` | `System.Entity` | c,d,i,r,u | 3/0/0 | All properties of resources added to the Orion views. |
| `Orion.Resources` | `System.Entity` | c,d,i,r,u | 8/0/4 | All resources added to the Orion views. |
| `Orion.ResponseTime` | `System.StatisticsEntity` | - | 9/1/0 |  |
| `Orion.ResponseTimeThreshold` | `Orion.NodesThresholds` | - | 0/1/0 |  |
| `Orion.Routing.DefaultRouteChange` | `System.Entity` | - | 9/2/0 |  |
| `Orion.Routing.Neighbors` | `System.Entity` | - | 27/5/0 |  |
| `Orion.Routing.NeighborsFlapCount` | `System.Entity` | - | 6/1/0 |  |
| `Orion.Routing.Router` | `System.Entity` | - | 3/6/0 |  |
| `Orion.Routing.RoutingDetails` | `System.Entity` | - | 7/1/0 |  |
| `Orion.Routing.RoutingProtocol` | `System.Entity` | - | 3/0/0 |  |
| `Orion.Routing.RoutingProtocolStateMapping` | `System.Entity` | - | 4/0/0 |  |
| `Orion.Routing.RoutingTable` | `System.Entity` | - | 28/5/0 |  |
| `Orion.Routing.RoutingTableFlap` | `System.Entity` | - | 12/2/0 |  |
| `Orion.Routing.VRF` | `System.Entity` | - | 8/5/0 |  |
| `Orion.Routing.VRFInterface` | `System.Entity` | - | 6/2/0 |  |
| `Orion.SCM.ApplicationTemplateToProfileMapping` | `System.Entity` | r | 7/0/0 | This entity provides mapping between SAM application templates and SCM profiles. It allows to recommend SCM p… |
| `Orion.SCM.Baseline` | `System.Entity` | i,r | 3/1/1 | This entity represents base line. Base line serves as base compare point. |
| `Orion.SCM.DismissedCandidates` | `System.Entity` | c,d,r | 4/0/0 | This entity provides Agent and Profile candidates the user does not want to see in the Candidates for monitor… |
| `Orion.SCM.FimDisabledNodes` | `System.Entity` | c,d,r | 1/1/0 | This entity contains explicit list of nodes where FIM is forcibly disabled. |
| `Orion.SCM.NodesProfiles` | `System.Entity` | c,d,r | 3/2/0 | This entity represents mapping table for M:N relationship between SCM Nodes and SCM Profiles. |
| `Orion.SCM.NodesProfilesArchive` | `System.Entity` | r | 4/0/0 | Unlike "Orion.SCM.NodesProfilesHistory", this entity contains only the most recent record of a Profile unassi… |
| `Orion.SCM.NodesProfilesHistory` | `System.Entity` | r | 5/0/0 | This entity represents history of assigned profiles. |
| `Orion.SCM.OneTimePollFinished` | `System.Indication` | - | 4/0/0 | This entity represents indication containing info about a one time poll result. |
| `Orion.SCM.PollEntries` | `System.Entity` | r | 4/1/0 | This entity represents poll on particular SCM node, recorded. |
| `Orion.SCM.ProfileElementPolicyDataSources` | `System.Entity` | c,d,r | 2/0/0 | This entity represents a Profile Element relation to PolicyEngine. |
| `Orion.SCM.ProfileElements` | `System.Entity` | c,d,r,u | 8/3/0 | This entity represents monitored element for SCM profile, which could be set and maintained by a user. Monito… |
| `Orion.SCM.ProfileToApplicationTemplateMapping` | `System.Entity` | r | 6/0/0 | This entity provides mapping between SCM profiles and SAM application templates. It allows to recommend SAM a… |
| `Orion.SCM.Profiles` | `System.Entity` | c,d,i,r,u | 13/4/5 | This entity represents profiles, which could be set and maintained by a user. |
| `Orion.SCM.Results.ElementContents` | `System.Entity` | r | 4/1/0 | This entity provides content of polled element. For security reason this entity is available only for "admin"… |
| `Orion.SCM.Results.ElementErrors` | `System.Entity` | r | 5/0/0 | This entity represents polling errors which occur while discovering and polling Profile Elements. |
| `Orion.SCM.Results.ElementMetadata` | `System.Entity` | r | 22/3/0 | This entity represents metadata retrieved from remote server, marked with version and timestamp. |
| `Orion.SCM.Results.NodesPollingErrors` | `System.Entity` | c,d,r | 3/0/0 | This entity represents polling errors for SCM node / server configuration. Contains only current errors, does… |
| `Orion.SCM.Results.PolledElementDetails` | `System.Entity` | r | 8/1/0 | This entity represents some extending details for PolledElements. |
| `Orion.SCM.Results.PolledElementErrors` | `System.Entity` | r | 6/0/0 | This entity represents polling errors for PolledElements. |
| `Orion.SCM.Results.PolledElements` | `System.Entity` | r | 7/5/0 | This entity represents Discovered Elements matching Profile Element settings. |
| `Orion.SCM.ServerConfiguration` | `System.ManagedEntity` | i,r | 14/10/4 | This entity represents nodes, which are monitored by SCM product. Every SCM node, can be polled for configura… |
| `Orion.SCM.ServerConfigurationChange` | `System.Indication` | - | 11/2/0 | This entity represents indication containing info about configuration change on server. |
| `Orion.SCM.ServerConfigurationDiffersFromBaseline` | `System.Indication` | - | 3/1/0 | This entity represents indication server configuration differs from baseline. |
| `Orion.SEM.Connection` | `System.Indication` | - | 3/0/0 |  |
| `Orion.SEM.EventSourceCategories` | `System.Entity` | - | 4/0/0 |  |
| `Orion.SEM.EventSourceTags` | `System.Entity` | - | 5/0/0 |  |
| `Orion.SEM.EventSources` | `System.Entity` | - | 4/0/0 |  |
| `Orion.SEM.Events` | `System.Entity` | - | 11/0/1 |  |
| `Orion.SEM.Facets` | `System.Entity` | - | 3/0/0 |  |
| `Orion.SEM.Licenses` | `System.Entity` | - | 11/0/0 |  |
| `Orion.SEM.Nodes` | `System.Entity` | - | 5/0/0 |  |
| `Orion.SEM.ScheduledSearchExecutions` | `System.Entity` | - | 14/1/0 |  |
| `Orion.SEM.SemConnections` | `System.DashboardEntity` | - | 14/2/0 |  |
| `Orion.SEM.Settings` | `System.Entity` | - | 0/0/8 |  |
| `Orion.SEM.Tags` | `System.Entity` | - | 4/0/0 |  |
| `Orion.SEM.TrackedScheduledSearchExecutions` | `System.Entity` | - | 14/1/0 |  |
| `Orion.SEM.TrackedTags` | `System.Entity` | - | 4/0/0 |  |
| `Orion.SEUM.AgentConnectionStatus` | `System.Entity` | - | 2/1/0 | This entity represents the Agent connection status information. |
| `Orion.SEUM.AgentStatus` | `System.StatisticsEntity` | - | 14/1/0 | This entity represents the Agent status information. |
| `Orion.SEUM.AgentStatusReport` | `System.StatisticsEntity` | - | 13/1/0 | This entity represents the Agent status report information. |
| `Orion.SEUM.AgentWebUri` | `System.ExtensionEntity` | - | 2/1/0 | This entity represents the Agent web uri information. |
| `Orion.SEUM.Agents` | `System.ManagedEntity` | c,d,i,r,u | 31/6/0 | This entity represents the Agent information. |
| `Orion.SEUM.RecordingAuthentications` | `System.Entity` | c,d,i,r,u | 5/1/0 | This entity represents username and password credentials stored in the recording. |
| `Orion.SEUM.RecordingCertificates` | `System.Entity` | c,d,i,r,u | 4/1/0 | This entity represents the certificates information used within recording. |
| `Orion.SEUM.RecordingCustomProperties` | `System.CustomPropertiesEntity` | c,d,i,r,u | 0/1/4 | Allows to create, modify and delete custom properties for recordings. |
| `Orion.SEUM.RecordingSteps` | `System.Entity` | c,d,i,r,u | 10/2/0 | This entity represents the Recordings steps information. |
| `Orion.SEUM.Recordings` | `System.Entity` | c,d,i,r,u | 8/5/4 | This entity represents the Recordings information. |
| `Orion.SEUM.RecordingsSettings` | `System.Entity` | c,d,i,r,u | 0/0/1 | Provides metadata for recordings package. |
| `Orion.SEUM.ResponseTime` | `System.StatisticsEntity` | - | 7/2/0 | This entity represents the Response times information. |
| `Orion.SEUM.ResponseTimeDetail` | `System.StatisticsEntity` | - | 5/2/0 | This entity represents the Response time detail information. |
| `Orion.SEUM.ResponseTimeReport` | `System.StatisticsEntity` | - | 8/1/0 | This entity represents the Response time report information. |
| `Orion.SEUM.Settings` | `System.Entity` | c,d,i,r,u | 2/0/0 | This entity represents the Settings information. |
| `Orion.SEUM.StepResponseTime` | `System.StatisticsEntity` | - | 11/3/0 | This entity represents the Step response time information. |
| `Orion.SEUM.StepResponseTimeDetail` | `System.StatisticsEntity` | - | 6/3/0 | This entity represents the Step response time detail information. |
| `Orion.SEUM.StepResponseTimeDetailLargeData` | `System.ExtensionEntity` | - | 5/1/0 | This entity represents the Step response time detail for large data information. |
| `Orion.SEUM.StepResponseTimeLargeData` | `System.ExtensionEntity` | - | 5/1/0 | This entity represents the Steps response time for large data information. |
| `Orion.SEUM.StepResponseTimeReport` | `System.StatisticsEntity` | - | 8/1/0 | This entity represents the Steps response time report information. |
| `Orion.SEUM.TransactionCustomProperties` | `System.CustomPropertiesEntity` | c,d,i,r,u | 0/1/4 | Allows to create, modify and delete custom properties for transactions. |
| `Orion.SEUM.TransactionRunParameters` | `System.Entity` | c,d,i,r,u | 4/1/0 | This entity represents the Response times information. |
| `Orion.SEUM.TransactionStepLargeData` | `System.ExtensionEntity` | - | 4/1/0 | This entity represents the Transactions steps for large data information. |
| `Orion.SEUM.TransactionStepRequests` | `System.Entity` | - | 23/1/0 | This entity represents the Transaction step requests information. |
| `Orion.SEUM.TransactionStepWebUri` | `System.ExtensionEntity` | - | 2/1/0 | This entity represents the Transaction step web uri information. |
| `Orion.SEUM.TransactionSteps` | `System.ManagedEntity` | c,d,i,r,u | 16/9/0 | This entity represents the Transaction steps information. |
| `Orion.SEUM.TransactionWebUri` | `System.ExtensionEntity` | - | 2/1/0 | This entity represents the Transaction web uri information. |
| `Orion.SEUM.Transactions` | `System.ManagedEntity` | c,d,i,r,u | 17/10/3 | This entity represents the Transactions information. |
| `Orion.SEUM.WebSettings` | `System.Entity` | - | 2/0/0 | This entity represents the Web settings information. |
| `Orion.SEUM.WebUserPermissions` | `System.Entity` | - | 3/0/0 | This entity represents the Web user permissions information. |
| `Orion.SEUM.Websites` | `System.Entity` | - | 6/0/0 | This entity represents the Websites information. |
| `Orion.SMTPServers` | `System.Entity` | c,d,r,u | 10/0/0 |  |
| `Orion.SNMPv3Credentials` | `System.ExtensionEntity` | r,u | 17/1/0 |  |
| `Orion.SRM.ApplicationThresholds` | `System.Entity` | - | 14/0/0 |  |
| `Orion.SRM.DeviceGroupProperties` | `System.Entity` | - | 3/0/0 | Contains specific device group properties |
| `Orion.SRM.DeviceGroups` | `System.Entity` | - | 7/3/0 | Contains info about supported device groups |
| `Orion.SRM.DeviceMigrations` | `System.Entity` | - | 7/0/2 | Information about possible and running SRM device migrations |
| `Orion.SRM.Engines` | `System.Entity` | - | 48/2/0 | Contains information about all Engines added |
| `Orion.SRM.EventType` | `System.Entity` | - | 1/0/0 | Entity used for filtering events related to SRM entities only. |
| `Orion.SRM.FileServerIdentification` | `System.Entity` | - | 5/1/0 | Contains other information about each of the File Servers - mainly for storing additional IP addresses |
| `Orion.SRM.FileServers` | `System.Entity` | - | 5/2/0 | Contains information about all File Servers |
| `Orion.SRM.FileShareCustomProperties` | `System.CustomPropertiesEntity` | i,r,u | 0/1/5 | Contains custom properties of File Shares |
| `Orion.SRM.FileShares` | `System.ManagedEntity` | - | 21/8/0 | Contains information about all File Shares |
| `Orion.SRM.FileSharesToVIMNas` | `System.Entity` | - | 4/0/0 | Defines mapping between SRM File Shares and VIM NAS Volumes |
| `Orion.SRM.LUNBytesPSReadThreshold` | `Orion.SRM.LUNThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.LUNBytesPSTotalThreshold` | `Orion.SRM.LUNThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.LUNBytesPSWriteThreshold` | `Orion.SRM.LUNThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.LUNCapacityStatistics` | `System.StatisticsEntity` | - | 6/1/0 | Stores capacity statistics for all LUNs |
| `Orion.SRM.LUNCustomProperties` | `System.CustomPropertiesEntity` | i,r,u | 0/1/5 | Contains custom properties of LUNs |
| `Orion.SRM.LUNIOLatencyOtherThreshold` | `Orion.SRM.LUNThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.LUNIOLatencyReadThreshold` | `Orion.SRM.LUNThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.LUNIOLatencyTotalThreshold` | `Orion.SRM.LUNThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.LUNIOLatencyWriteThreshold` | `Orion.SRM.LUNThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.LUNIOPSOtherThreshold` | `Orion.SRM.LUNThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.LUNIOPSReadThreshold` | `Orion.SRM.LUNThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.LUNIOPSTotalThreshold` | `Orion.SRM.LUNThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.LUNIOPSWriteThreshold` | `Orion.SRM.LUNThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.LUNIOSizeReadThreshold` | `Orion.SRM.LUNThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.LUNIOSizeTotalThreshold` | `Orion.SRM.LUNThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.LUNIOSizeWriteThreshold` | `Orion.SRM.LUNThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.LUNStatistics` | `System.StatisticsEntity` | - | 31/1/0 | Stores LUNs statistics. |
| `Orion.SRM.LUNThresholds` | `Orion.SRM.Thresholds` | - | 0/0/0 | Base entity for all LUN thresholds |
| `Orion.SRM.LUNs` | `System.ManagedEntity` | - | 62/31/0 | Contains information about all LUNs |
| `Orion.SRM.LunMasking` | `System.Entity` | - | 8/1/0 | Defines LUN masking |
| `Orion.SRM.LunsToVIMLuns` | `System.Entity` | - | 4/0/0 | Defines mapping between SRM LUNs and VIM LUNs |
| `Orion.SRM.PhysicalDisks` | `System.Entity` | - | 16/1/1 | Contains information about all physical disks |
| `Orion.SRM.PoolBytesPSReadThreshold` | `Orion.SRM.PoolThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.PoolBytesPSTotalThreshold` | `Orion.SRM.PoolThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.PoolBytesPSWriteThreshold` | `Orion.SRM.PoolThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.PoolCapacityStatistics` | `System.StatisticsEntity` | - | 9/1/0 | Stores capacity statistics for all Pools |
| `Orion.SRM.PoolCustomProperties` | `System.CustomPropertiesEntity` | i,r,u | 0/1/5 | Contains custom properties of Pools |
| `Orion.SRM.PoolIOPSOtherThreshold` | `Orion.SRM.PoolThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.PoolIOPSReadThreshold` | `Orion.SRM.PoolThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.PoolIOPSTotalThreshold` | `Orion.SRM.PoolThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.PoolIOPSWriteThreshold` | `Orion.SRM.PoolThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.PoolIOSizeReadThreshold` | `Orion.SRM.PoolThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.PoolIOSizeTotalThreshold` | `Orion.SRM.PoolThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.PoolIOSizeWriteThreshold` | `Orion.SRM.PoolThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.PoolStatistics` | `System.StatisticsEntity` | - | 30/1/0 | Stores Pool statistics. |
| `Orion.SRM.PoolThresholds` | `Orion.SRM.Thresholds` | - | 0/0/0 | Base entity for all Pool thresholds |
| `Orion.SRM.PoolToPoolsMapping` | `System.Entity` | - | 3/0/0 | Stores a relation between pools. This was introduced because of hierarchical pools feature. |
| `Orion.SRM.Pools` | `System.ManagedEntity` | - | 52/22/0 | Contains information about all Pools |
| `Orion.SRM.ProviderCustomProperties` | `System.CustomPropertiesEntity` | i,r,u | 0/1/5 | Contains custom properties of Providers |
| `Orion.SRM.Providers` | `System.ManagedEntity` | - | 28/4/0 | Contains information about all providers added to the platform |
| `Orion.SRM.RESTConfigurations` | `System.Entity` | - | 2/1/0 | Contains configurations for generc REST clients |
| `Orion.SRM.StorageArrayBytesPSReadThreshold` | `Orion.SRM.StorageArrayThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.StorageArrayBytesPSTotalThreshold` | `Orion.SRM.StorageArrayThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.StorageArrayBytesPSWriteThreshold` | `Orion.SRM.StorageArrayThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.StorageArrayCapacityStatistics` | `System.StatisticsEntity` | - | 10/1/0 | Stores capacity statistics for all storage arrays |
| `Orion.SRM.StorageArrayCustomProperties` | `System.CustomPropertiesEntity` | i,r,u | 0/1/5 | Contains custom properties of Storage Arrays |
| `Orion.SRM.StorageArrayIOPSOtherThreshold` | `Orion.SRM.StorageArrayThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.StorageArrayIOPSReadThreshold` | `Orion.SRM.StorageArrayThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.StorageArrayIOPSTotalThreshold` | `Orion.SRM.StorageArrayThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.StorageArrayIOPSWriteThreshold` | `Orion.SRM.StorageArrayThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.StorageArrayIOSizeReadThreshold` | `Orion.SRM.StorageArrayThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.StorageArrayIOSizeTotalThreshold` | `Orion.SRM.StorageArrayThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.StorageArrayIOSizeWriteThreshold` | `Orion.SRM.StorageArrayThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.StorageArrayIPs` | `System.Entity` | - | 3/1/0 | Contains information about all IP addresses used by all storage arrays |
| `Orion.SRM.StorageArrayProperties` | `System.Entity` | - | 3/0/0 | Contains additional properties which belong to Storage Array |
| `Orion.SRM.StorageArrayStatistics` | `System.StatisticsEntity` | - | 26/1/0 | Stores storage array statistics. |
| `Orion.SRM.StorageArrayThresholds` | `Orion.SRM.Thresholds` | - | 0/0/0 | Base entity for all Storage Array thresholds |
| `Orion.SRM.StorageArrayWebUri` | `System.Entity` | - | 2/1/0 | Contains information used for building link to Storage Array in the Network Atlas. |
| `Orion.SRM.StorageArrays` | `System.ManagedEntity` | - | 65/31/4 | Contains information about all storage arrays added to the platform |
| `Orion.SRM.StorageControllerBytesPSDistributionThreshold` | `Orion.SRM.StorageControllerThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.StorageControllerBytesPSReadThreshold` | `Orion.SRM.StorageControllerThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.StorageControllerBytesPSTotalThreshold` | `Orion.SRM.StorageControllerThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.StorageControllerBytesPSWriteThreshold` | `Orion.SRM.StorageControllerThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.StorageControllerCustomProperties` | `System.CustomPropertiesEntity` | i,r,u | 0/1/5 | Contains custom properties of Pools |
| `Orion.SRM.StorageControllerIOLatencyReadThreshold` | `Orion.SRM.StorageControllerThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.StorageControllerIOLatencyTotalThreshold` | `Orion.SRM.StorageControllerThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.StorageControllerIOLatencyWriteThreshold` | `Orion.SRM.StorageControllerThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.StorageControllerIOPSDistributionThreshold` | `Orion.SRM.StorageControllerThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.StorageControllerIOPSReadThreshold` | `Orion.SRM.StorageControllerThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.StorageControllerIOPSTotalThreshold` | `Orion.SRM.StorageControllerThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.StorageControllerIOPSWriteThreshold` | `Orion.SRM.StorageControllerThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.StorageControllerIOSizeReadThreshold` | `Orion.SRM.StorageControllerThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.StorageControllerIOSizeTotalThreshold` | `Orion.SRM.StorageControllerThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.StorageControllerIOSizeWriteThreshold` | `Orion.SRM.StorageControllerThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.StorageControllerIPs` | `System.Entity` | - | 2/1/0 | Contains information IP adresses for storage controllers |
| `Orion.SRM.StorageControllerPortBytesPSDistributionThreshold` | `Orion.SRM.StorageControllerPortThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.StorageControllerPortBytesPSTotalThreshold` | `Orion.SRM.StorageControllerPortThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.StorageControllerPortCustomProperties` | `System.CustomPropertiesEntity` | i,r,u | 0/1/5 | Contains custom properties of Pools |
| `Orion.SRM.StorageControllerPortIOPSDistributionThreshold` | `Orion.SRM.StorageControllerPortThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.StorageControllerPortIOPSTotalThreshold` | `Orion.SRM.StorageControllerPortThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.StorageControllerPortStatistics` | `System.StatisticsEntity` | - | 8/1/0 | Stores storage controller port statistics. |
| `Orion.SRM.StorageControllerPortThresholds` | `Orion.SRM.Thresholds` | - | 0/0/0 | Base entity for all Storage Controller Port thresholds. |
| `Orion.SRM.StorageControllerPorts` | `System.ManagedEntity` | - | 20/8/0 | Contains information about port elements on a storage controller |
| `Orion.SRM.StorageControllerStatistics` | `System.StatisticsEntity` | - | 24/1/0 | Stores storage controller statistics. |
| `Orion.SRM.StorageControllerThresholds` | `Orion.SRM.Thresholds` | - | 0/0/0 | Base entity for all Storage Controller thresholds. |
| `Orion.SRM.StorageControllerUtilizationThreshold` | `Orion.SRM.StorageControllerThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.StorageControllers` | `System.ManagedEntity` | - | 43/22/0 | Contains information about all Storage Controllers |
| `Orion.SRM.Templates` | `System.Entity` | - | 6/2/0 | Contains all supported device polling templates and associated info |
| `Orion.SRM.Thresholds` | `Orion.Thresholds` | - | 0/0/0 | Base entity for all SRM thresholds. Implements Orion.Thresholds |
| `Orion.SRM.Topology` | `System.Entity` | - | 6/2/0 | Stores topology info |
| `Orion.SRM.VServerBytesPSReadThreshold` | `Orion.SRM.VServerThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.VServerBytesPSTotalThreshold` | `Orion.SRM.VServerThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.VServerBytesPSWriteThreshold` | `Orion.SRM.VServerThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.VServerCapacityStatistics` | `System.StatisticsEntity` | - | 5/1/0 | Stores capacity statistics for all VServers |
| `Orion.SRM.VServerIOPSOtherThreshold` | `Orion.SRM.VServerThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.VServerIOPSReadThreshold` | `Orion.SRM.VServerThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.VServerIOPSTotalThreshold` | `Orion.SRM.VServerThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.VServerIOPSWriteThreshold` | `Orion.SRM.VServerThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.VServerIOSizeReadThreshold` | `Orion.SRM.VServerThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.VServerIOSizeTotalThreshold` | `Orion.SRM.VServerThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.VServerIOSizeWriteThreshold` | `Orion.SRM.VServerThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.VServerStatistics` | `System.StatisticsEntity` | - | 25/1/0 | Stores VServer statistics. |
| `Orion.SRM.VServerThresholds` | `Orion.SRM.Thresholds` | - | 0/0/0 | Base entity for all VServer thresholds |
| `Orion.SRM.VServers` | `System.ManagedEntity` | - | 35/19/0 | Contains information about all VServers |
| `Orion.SRM.VServersCustomProperties` | `System.CustomPropertiesEntity` | i,r,u | 0/1/5 | Contains custom properties of VServers |
| `Orion.SRM.VolumeBytesPSReadThreshold` | `Orion.SRM.VolumeThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.VolumeBytesPSTotalThreshold` | `Orion.SRM.VolumeThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.VolumeBytesPSWriteThreshold` | `Orion.SRM.VolumeThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.VolumeCapacityStatistics` | `System.StatisticsEntity` | - | 7/1/0 | Stores capacity statistics for all Volumes |
| `Orion.SRM.VolumeCustomProperties` | `System.CustomPropertiesEntity` | i,r,u | 0/1/5 | Contains custom properties of Volumes |
| `Orion.SRM.VolumeIOLatencyOtherThreshold` | `Orion.SRM.VolumeThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.VolumeIOLatencyReadThreshold` | `Orion.SRM.VolumeThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.VolumeIOLatencyTotalThreshold` | `Orion.SRM.VolumeThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.VolumeIOLatencyWriteThreshold` | `Orion.SRM.VolumeThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.VolumeIOPSOtherThreshold` | `Orion.SRM.VolumeThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.VolumeIOPSReadThreshold` | `Orion.SRM.VolumeThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.VolumeIOPSTotalThreshold` | `Orion.SRM.VolumeThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.VolumeIOPSWriteThreshold` | `Orion.SRM.VolumeThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.VolumeIOSizeReadThreshold` | `Orion.SRM.VolumeThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.VolumeIOSizeTotalThreshold` | `Orion.SRM.VolumeThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.VolumeIOSizeWriteThreshold` | `Orion.SRM.VolumeThresholds` | - | 0/1/0 | Concrete threshold, contains properties from Orion.Thresholds entity. |
| `Orion.SRM.VolumeStatistics` | `System.StatisticsEntity` | - | 31/1/0 | Stores Volume statistics. |
| `Orion.SRM.VolumeThresholds` | `Orion.SRM.Thresholds` | - | 0/0/0 | Base entity for all Volume thresholds |
| `Orion.SRM.Volumes` | `System.ManagedEntity` | - | 54/27/0 | Contains information about all Volumes |
| `Orion.SSH.Audit` | `System.Entity` | c,d,i,r,u | 5/0/0 |  |
| `Orion.SSH.Key` | `System.Entity` | c,d,i,r,u | 4/0/0 |  |
| `Orion.SSH.Session` | `System.Entity` | c,d,i,r,u | 7/0/0 |  |
| `Orion.SSO` | `System.Entity` | - | 0/0/1 |  |
| `Orion.STPRecords` | `System.Entity` | - | 8/0/0 |  |
| `Orion.ScheduleEntityAssignment` | `System.Entity` | c,d,i,r,u | 6/1/0 |  |
| `Orion.ScheduleExecuted` | `System.Indication` | - | 3/0/0 |  |
| `Orion.ScheduleTaskDefinition` | `System.Entity` | c,d,i,r,u | 12/1/0 |  |
| `Orion.SdWan.Nodes` | `System.ManagedEntity` | - | 23/6/0 |  |
| `Orion.SdWan.Nodes.Failover` | `System.Indication` | - | 3/1/0 |  |
| `Orion.SdWan.NodesInterfaces` | `System.ManagedEntity` | - | 11/2/0 |  |
| `Orion.SdWan.NodesPerformance` | `System.StatisticsEntity` | - | 3/1/0 |  |
| `Orion.SdWan.TopologyConnections` | `Orion.TopologyConnections` | r | 12/1/0 |  |
| `Orion.SdWan.TopologyEdges` | `Orion.Maps.TopologyEdges` | r | 0/0/0 |  |
| `Orion.SdWan.Tunnels` | `System.ManagedEntity` | - | 17/2/0 |  |
| `Orion.SdWan.TunnelsStatistics` | `System.StatisticsEntity` | - | 28/1/0 |  |
| `Orion.SecObs.DatabaseUpdateUserAccount` | `System.Indication` | - | 3/0/0 |  |
| `Orion.SecObs.ModuleSettings` | `System.Entity` | - | 5/0/0 |  |
| `Orion.SecObs.PatchManagerSettings` | `System.Indication` | - | 9/0/0 |  |
| `Orion.SecObs.Users` | `System.Entity` | - | 0/0/1 |  |
| `Orion.SecObs.Vulnerabilities.Cves` | `System.Entity` | - | 11/1/0 |  |
| `Orion.SecObs.Vulnerabilities.LastMatching.NodeScores` | `System.Entity` | - | 16/2/0 |  |
| `Orion.SecObs.Vulnerabilities.LastMatching.Result` | `System.Entity` | - | 17/2/0 |  |
| `Orion.SecObs.Vulnerabilities.Matchings` | `System.Entity` | - | 13/0/0 |  |
| `Orion.SecObs.Vulnerabilities.NodeCve` | `System.Entity` | - | 0/0/1 |  |
| `Orion.SecObs.Vulnerabilities.Nodes` | `System.Entity` | - | 0/0/2 |  |
| `Orion.SecObs.Vulnerabilities.Settings` | `System.Entity` | - | 0/0/13 |  |
| `Orion.SecObs.VulnerabilityScore.Execution` | `System.Indication` | - | 2/0/0 |  |
| `Orion.SecObs.VulnerabilityScore.ManageNode` | `System.Indication` | - | 3/0/0 |  |
| `Orion.SecObs.VulnerabilityScore.NodeVulnerabilityState` | `System.Indication` | - | 4/0/0 |  |
| `Orion.SecObs.VulnerabilityScore.Settings` | `System.Indication` | - | 3/0/0 |  |
| `Orion.ServiceDesk.AlertIncident` | `Orion.ESI.AlertIncident` | d,r | 2/0/0 | Represents Service Desk incidents related to Orion alerts. |
| `Orion.ServiceDesk.ClusterIncident` | `Orion.ESI.ClusterIncident` | d,r | 2/0/0 | Represents Service Desk incidents related to AlertStack clusters. |
| `Orion.ServiceNow.AlertIncident` | `Orion.ESI.AlertIncident` | d,r | 2/0/0 | Represents ServiceNow incidents related to Orion alerts. |
| `Orion.ServiceNow.ClusterIncident` | `Orion.ESI.ClusterIncident` | d,r | 2/0/0 | Represents ServiceNow incidents related to AlertStack clusters. |
| `Orion.ServiceRestarted` | `System.Indication` | - | 2/0/0 | Occurs when user performs restarting of an Orion Service |
| `Orion.ServiceStarted` | `System.Indication` | - | 2/0/0 | Occurs when user performs starting of an Orion Service |
| `Orion.ServiceStopped` | `System.Indication` | - | 2/0/0 | Occurs when user performs stopping of an Orion Service |
| `Orion.Services` | `System.Entity` | - | 4/0/0 |  |
| `Orion.SessionEnd` | `System.Indication` | - | 1/0/0 | Occurs when session ends |
| `Orion.Setting` | `System.Entity` | r,u | 12/1/0 |  |
| `Orion.SettingOverride` | `System.Entity` | c,d,r,u | 3/2/0 |  |
| `Orion.Settings` | `System.Entity` | c,d,i,r,u | 9/0/0 |  |
| `Orion.ShadowNodes` | `System.Entity` | - | 7/0/0 |  |
| `Orion.Sites` | `System.Entity` | c,d,i,r,u | 9/2/1 | Represents Sites to be used by SWIS(f) to fetch data from. |
| `Orion.Stacks.FilterProperty` | `System.Entity` | - | 7/0/0 |  |
| `Orion.Stacks.Participation` | `System.Entity` | - | 12/0/0 |  |
| `Orion.Stacks.Relation` | `System.Entity` | - | 5/0/2 |  |
| `Orion.StatusCalculators` | `System.Entity` | - | 2/1/0 |  |
| `Orion.StatusInfo` | `System.Entity` | - | 12/10/0 |  |
| `Orion.Stencil.ModelSpecAssignments` | `System.Entity` | - | 4/2/0 |  |
| `Orion.Stencil.ModelSpecs` | `System.Entity` | - | 3/1/0 |  |
| `Orion.Stencil.NodeSpecAssignments` | `System.Entity` | - | 3/2/0 |  |
| `Orion.SwisFeature` | `System.Feature` | - | 0/0/1 | Lists all supported features. |
| `Orion.SysLogFacilities` | `System.Entity` | - | 2/0/0 |  |
| `Orion.SysLogSeverities` | `System.Entity` | - | 2/0/0 |  |
| `Orion.Technology` | `System.Entity` | - | 2/1/0 |  |
| `Orion.TechnologyPolling` | `System.Entity` | - | 3/2/0 |  |
| `Orion.TechnologyPollingAssignments` | `System.Entity` | - | 4/3/4 |  |
| `Orion.Thresholds` | `System.Entity` | - | 20/1/0 |  |
| `Orion.ThresholdsLevelSettings` | `System.Entity` | - | 4/1/0 |  |
| `Orion.ThresholdsNames` | `System.Entity` | - | 8/2/0 |  |
| `Orion.Toolset.AutocompleteHistory` | `System.Entity` | - | 5/0/0 |  |
| `Orion.Toolset.BusinessLayer` | `System.Entity` | - | 3/0/0 |  |
| `Orion.Toolset.ConnectionProfiles` | `System.Entity` | c,d,i,r,u | 6/0/0 |  |
| `Orion.Toolset.GlobalSettings` | `System.Entity` | i,r | 2/0/0 |  |
| `Orion.Toolset.LicenseSettings` | `System.Entity` | - | 3/0/0 |  |
| `Orion.Toolset.NodesProperties` | `System.Entity` | c,d,i,r,u | 3/0/0 |  |
| `Orion.Toolset.ResultTypes` | `System.Entity` | - | 2/1/0 |  |
| `Orion.Toolset.SSH` | `System.Entity` | - | 5/0/0 |  |
| `Orion.Toolset.SSHActiveData` | `System.Entity` | c,d,i,r,u | 6/0/0 |  |
| `Orion.Toolset.ToolLaunchDetail` | `System.Entity` | - | 3/1/0 |  |
| `Orion.Toolset.ToolSettings` | `System.Entity` | - | 4/1/0 |  |
| `Orion.Toolset.Tools` | `System.Entity` | - | 4/3/0 |  |
| `Orion.Toolset.UserCredentialMapping` | `System.Entity` | - | 2/0/0 |  |
| `Orion.Top100NodeEventsForYear` | `System.Entity` | - | 12/0/0 | Top 100 node events for use in Dashboards. |
| `Orion.Top5000EventsForYear` | `System.Entity` | - | 14/0/0 | Top 5000 events for use in Cloud Dashboards |
| `Orion.Topology.TopologyConnections` | `Orion.TopologyConnections` | - | 0/0/0 |  |
| `Orion.TopologyConnections` | `System.Entity` | - | 12/0/0 |  |
| `Orion.TopologyData` | `System.Entity` | - | 9/0/0 |  |
| `Orion.TopologyEntities` | `System.Entity` | - | 1/0/0 |  |
| `Orion.TwoLevelThreshold` | `System.TwoLevelTheshold` | - | 0/0/0 |  |
| `Orion.UCS.Blades` | `Orion.HardwareHealth.BMC.Blades` | - | 0/0/0 | This entity presents the UCS Blades. |
| `Orion.UCS.Chassis` | `Orion.HardwareHealth.BMC.Chassis` | - | 1/4/0 | This entity presents the UCS Chassis. |
| `Orion.UCS.Events` | `System.Entity` | - | 9/1/0 | This entity presents the UCS Events. |
| `Orion.UCS.Fabrics` | `System.Entity` | - | 13/5/0 | This entity presents the UCS Fabrics. |
| `Orion.UCS.FansOnChassis` | `Orion.HardwareHealth.BMC.FansOnChassis` | - | 0/0/0 | This entity presents the Fans related to UCS Chassis. |
| `Orion.UCS.FansOnFabrics` | `Orion.HardwareHealth.BMC.Fans` | - | 0/1/0 | This entity presents the Fans related to UCS Fabrics. |
| `Orion.UCS.PSUsOnChassis` | `Orion.HardwareHealth.BMC.PSUsOnChassis` | - | 0/0/0 | This entity presents the Power Supply Unit related to UCS Chassis. |
| `Orion.UCS.PSUsOnFabrics` | `Orion.HardwareHealth.BMC.PSUs` | - | 0/1/0 | This entity presents the Power Supply Unit related to UCS Fabrics. |
| `Orion.UDT.AccessPortEndpointCount` | `System.Entity` | - | 5/0/0 |  |
| `Orion.UDT.AllDnsEndpointConnections` | `System.Entity` | - | 13/0/0 |  |
| `Orion.UDT.AllEndpoints` | `System.Entity` | - | 14/2/0 |  |
| `Orion.UDT.AllIPEndpointConnections` | `System.Entity` | - | 13/0/0 |  |
| `Orion.UDT.AllMACEndpointConnections` | `System.Entity` | - | 13/0/0 |  |
| `Orion.UDT.AllWirelessEndpoints` | `System.Entity` | - | 10/1/0 |  |
| `Orion.UDT.CdpEntry` | `System.Entity` | - | 6/0/0 |  |
| `Orion.UDT.ConnectedMACsAndIPs` | `System.Entity` | - | 8/1/0 |  |
| `Orion.UDT.DNSName` | `System.Entity` | - | 5/0/0 |  |
| `Orion.UDT.DNSNameCurrent` | `System.Entity` | - | 7/2/0 |  |
| `Orion.UDT.DNSNameHistory` | `System.Entity` | - | 7/2/0 |  |
| `Orion.UDT.DeviceInventory` | `System.Entity` | - | 17/1/0 |  |
| `Orion.UDT.EmptyDNSRogue` | `System.Entity` | - | 6/0/0 |  |
| `Orion.UDT.Endpoint` | `System.Entity` | - | 6/4/0 |  |
| `Orion.UDT.EndpointDNS` | `System.Entity` | - | 5/0/0 |  |
| `Orion.UDT.EndpointIP` | `System.Entity` | - | 5/0/0 |  |
| `Orion.UDT.IPAddress` | `System.Entity` | - | 7/0/0 |  |
| `Orion.UDT.IPAddressCurrent` | `System.Entity` | - | 8/7/0 |  |
| `Orion.UDT.IPAddressHistory` | `System.Entity` | - | 9/7/0 |  |
| `Orion.UDT.IPv6List` | `System.Entity` | - | 2/0/0 |  |
| `Orion.UDT.IpEndpointCurrentConnections` | `System.Entity` | - | 7/0/0 |  |
| `Orion.UDT.IpEndpointHistoryConnections` | `System.Entity` | - | 8/0/0 |  |
| `Orion.UDT.Job` | `System.Entity` | - | 4/0/0 |  |
| `Orion.UDT.LatestDNSAddressHistoryForWatchID` | `System.Entity` | - | 7/0/0 |  |
| `Orion.UDT.LatestIPAddressHistoryForWatchID` | `System.Entity` | - | 8/0/0 |  |
| `Orion.UDT.LatestPortToEndpointHistoryForWatchID` | `System.Entity` | - | 8/0/0 |  |
| `Orion.UDT.LldpEntry` | `System.Entity` | - | 7/0/0 |  |
| `Orion.UDT.MACAddressInfo` | `System.Entity` | - | 30/1/0 |  |
| `Orion.UDT.MACCurrentInfo` | `System.Entity` | - | 27/1/0 |  |
| `Orion.UDT.MACCurrentInformation` | `System.Entity` | - | 27/1/0 |  |
| `Orion.UDT.MacEndpointCurrentConnections` | `System.Entity` | - | 7/0/0 |  |
| `Orion.UDT.MacEndpointHistoryConnections` | `System.Entity` | - | 8/0/0 |  |
| `Orion.UDT.MonitoredPortRule` | `System.Entity` | - | 4/0/0 |  |
| `Orion.UDT.MonitoredPortsCount` | `System.Entity` | - | 1/0/0 |  |
| `Orion.UDT.MovedMACAlert` | `System.Entity` | - | 5/0/0 |  |
| `Orion.UDT.NewMACAlert` | `System.Entity` | - | 9/0/0 |  |
| `Orion.UDT.NewMACVendorAlert` | `System.Entity` | - | 7/0/0 |  |
| `Orion.UDT.NodeCapability` | `System.Entity` | - | 11/1/0 |  |
| `Orion.UDT.NodeCapabilityDashboard` | `System.Entity` | - | 16/0/1 |  |
| `Orion.UDT.NodeChildStatusPorts` | `Orion.NodeChildStatusContributors` | - | 0/0/0 |  |
| `Orion.UDT.OUIReport` | `System.Entity` | - | 6/2/0 |  |
| `Orion.UDT.OUISummary` | `System.Entity` | - | 2/0/0 |  |
| `Orion.UDT.Port` | `System.ManagedEntity` | c,d,i,r,u | 22/8/2 |  |
| `Orion.UDT.PortCapacity` | `System.Entity` | - | 6/0/0 |  |
| `Orion.UDT.PortDisplayData` | `System.Entity` | - | 6/0/0 |  |
| `Orion.UDT.PortDisplayDataCount` | `System.Entity` | - | 2/0/0 |  |
| `Orion.UDT.PortHistoryCurrent` | `System.Entity` | - | 8/0/0 |  |
| `Orion.UDT.PortHistoryHistory` | `System.Entity` | - | 8/0/0 |  |
| `Orion.UDT.PortToEndpoint` | `System.Entity` | - | 6/0/0 |  |
| `Orion.UDT.PortToEndpointCounts` | `System.Entity` | - | 4/0/0 |  |
| `Orion.UDT.PortToEndpointCurrent` | `System.Entity` | - | 6/2/0 |  |
| `Orion.UDT.PortToEndpointHistory` | `System.Entity` | - | 7/2/0 |  |
| `Orion.UDT.PortToPort` | `System.Entity` | - | 5/0/0 |  |
| `Orion.UDT.PortToPortCurrent` | `System.Entity` | - | 5/0/0 |  |
| `Orion.UDT.PortToPortHistory` | `System.Entity` | - | 6/0/0 |  |
| `Orion.UDT.PortTypes` | `System.Entity` | - | 1/0/0 |  |
| `Orion.UDT.PortUsage` | `System.Entity` | - | 5/0/0 |  |
| `Orion.UDT.PortUsage.Daily` | `System.Entity` | - | 5/0/0 |  |
| `Orion.UDT.PortUsage.Detail` | `System.Entity` | - | 5/0/0 |  |
| `Orion.UDT.PortUsage.Hourly` | `System.Entity` | - | 5/0/0 |  |
| `Orion.UDT.PortWebUri` | `System.Entity` | - | 3/1/0 |  |
| `Orion.UDT.RogueDNSAlert` | `System.Entity` | - | 7/0/0 |  |
| `Orion.UDT.RogueEmptyDNSAlert` | `System.Entity` | - | 7/0/0 |  |
| `Orion.UDT.RogueEndpoints` | `System.Entity` | - | 5/0/0 |  |
| `Orion.UDT.RogueIPAlert` | `System.Entity` | - | 7/0/0 |  |
| `Orion.UDT.RogueMACAlert` | `System.Entity` | - | 11/0/0 |  |
| `Orion.UDT.RoutingEndpoints` | `System.Entity` | - | 1/0/0 |  |
| `Orion.UDT.Setting` | `System.Entity` | - | 3/0/0 |  |
| `Orion.UDT.UnusedPorts` | `System.Entity` | - | 9/1/0 |  |
| `Orion.UDT.User` | `System.Entity` | - | 21/2/0 |  |
| `Orion.UDT.UserDisplayData` | `System.Entity` | - | 4/0/0 |  |
| `Orion.UDT.UserDisplayDataCount` | `System.Entity` | - | 2/0/0 |  |
| `Orion.UDT.UserHistory` | `System.Entity` | - | 7/0/0 |  |
| `Orion.UDT.UserInventory.Results` | `System.Entity` | - | 9/0/0 |  |
| `Orion.UDT.UserLastActivity` | `System.Entity` | - | 6/0/0 |  |
| `Orion.UDT.UserToIPAddress` | `System.Entity` | - | 5/0/0 |  |
| `Orion.UDT.UserToIPAddressCurrent` | `System.Entity` | - | 5/3/0 |  |
| `Orion.UDT.UserToIPAddressHistory` | `System.Entity` | - | 6/3/0 |  |
| `Orion.UDT.VLAN` | `System.Entity` | - | 3/1/0 |  |
| `Orion.UDT.VLANDevice` | `System.Entity` | - | 9/0/0 |  |
| `Orion.UDT.Vrf` | `System.Entity` | - | 5/0/0 |  |
| `Orion.UDT.WatchList` | `System.Entity` | - | 6/0/0 |  |
| `Orion.UDT.WatchListAggregated` | `System.Entity` | - | 27/0/0 |  |
| `Orion.UDT.WatchListPresent` | `System.Entity` | - | 8/0/0 |  |
| `Orion.UDT.Wireless_Clients_Session_History_View_Data` | `System.Entity` | - | 16/0/0 |  |
| `Orion.UsageByDays` | `System.Entity` | - | 4/0/0 | Usage resources history by Days . |
| `Orion.UserLockedOut` | `System.Indication` | - | 3/0/0 | Occurs when user performs several login attempts with invalid credentials |
| `Orion.UserLogin` | `System.Indication` | - | 1/0/0 | Occurs when user performs login |
| `Orion.UserLoginUnsuccessful` | `System.Indication` | - | 1/0/0 | Occurs when user login fails |
| `Orion.UserLogout` | `System.Indication` | - | 1/0/0 | Occurs when user performs logout |
| `Orion.UserPasswordChangeByAdminFailed` | `System.Indication` | - | 2/0/0 | Occurs when user password reset performed by admin failed |
| `Orion.UserPasswordChangeByAdminSucceeded` | `System.Indication` | - | 2/0/0 | Occurs when user password reset performed by admin completed successfully |
| `Orion.UserPasswordChangeFailed` | `System.Indication` | - | 3/0/0 | Occurs when user password reset failed |
| `Orion.UserPasswordChangeSucceeded` | `System.Indication` | - | 3/0/0 | Occurs when user password reset completed successfully |
| `Orion.UserSettings` | `System.Entity` | c,d,r,u | 4/0/0 | There are important setting which belongs to orion user and they are store per orion site. |
| `Orion.UserUnlocked` | `System.Indication` | - | 1/0/0 | Occurs when user with the administrative rights unlocks another user |
| `Orion.VIM.Alarm` | `System.Entity` | c,d,i,r,u | 9/3/0 | VMware Alarm Definition |
| `Orion.VIM.AlertsRecommendations` | `System.Entity` | - | 3/0/0 | Alert Recommendation |
| `Orion.VIM.CapacityPlanning.HostProfiles` | `System.Entity` | - | 8/1/0 | Host profile used for resources simulation. It can be existing host or custom host profile. |
| `Orion.VIM.CapacityPlanning.ReportDefinitions` | `System.Entity` | - | 13/3/0 | Capacity Planning report definition containing necessary data for calculation |
| `Orion.VIM.CapacityPlanning.ReportResults` | `System.Entity` | - | 7/1/0 | Capacity Planning report result containing all computed data |
| `Orion.VIM.CapacityPlanning.VMProfiles` | `System.Entity` | - | 6/1/0 | Virtual machine profile used for workload simulation. It can be existing virtual machine or custom virtual ma… |
| `Orion.VIM.ChargebackReportChanged` | `System.Indication` | - | 0/0/0 | Chargeback Report Changed |
| `Orion.VIM.ChargebackReports` | `System.Entity` | r | 16/1/0 | Chargeback Report |
| `Orion.VIM.ClusterCpuLoadThreshold` | `Orion.Thresholds` | - | 0/1/0 | CPU Load Threshold |
| `Orion.VIM.ClusterMemUsageThreshold` | `Orion.Thresholds` | - | 0/1/0 | Memory Usage Threshold |
| `Orion.VIM.ClusterStatistics` | `System.StatisticsEntity` | - | 15/1/0 | Cluster Statistics History |
| `Orion.VIM.ClusterStorageStatistics` | `System.StatisticsEntity` | - | 14/1/0 | Storage Statistics |
| `Orion.VIM.ClusterThresholds` | `Orion.Thresholds` | - | 0/1/0 |  |
| `Orion.VIM.Clusters` | `System.ManagedEntity` | i,r,u | 41/22/0 | Virtual Cluster |
| `Orion.VIM.ClustersCustomProperties` | `System.CustomPropertiesEntity` | c,d,i,r,u | 1/1/4 | Custom Properties |
| `Orion.VIM.DataCenters` | `System.ManagedEntity` | - | 14/10/0 | Virtual Datacenter |
| `Orion.VIM.DataCentersCustomProperties` | `System.CustomPropertiesEntity` | c,d,i,r,u | 1/1/4 | Custom Properties |
| `Orion.VIM.DatastoreIOPSReadThreshold` | `Orion.Thresholds` | - | 0/1/0 | Read IOPS Threshold |
| `Orion.VIM.DatastoreIOPSTotalThreshold` | `Orion.Thresholds` | - | 0/1/0 | Total IOPS Threshold |
| `Orion.VIM.DatastoreIOPSWriteThreshold` | `Orion.Thresholds` | - | 0/1/0 | Write IOPS Threshold |
| `Orion.VIM.DatastoreLatencyReadThreshold` | `Orion.Thresholds` | - | 0/1/0 | Read Latency Threshold |
| `Orion.VIM.DatastoreLatencyTotalThreshold` | `Orion.Thresholds` | - | 0/1/0 | Total Latency Threshold |
| `Orion.VIM.DatastoreLatencyWriteThreshold` | `Orion.Thresholds` | - | 0/1/0 | Write Latency Threshold |
| `Orion.VIM.DatastoreStatistics` | `System.StatisticsEntity` | - | 33/1/0 | Datastore Statistics History |
| `Orion.VIM.DatastoreThresholds` | `Orion.Thresholds` | - | 0/1/0 |  |
| `Orion.VIM.Datastores` | `System.ManagedEntity` | - | 34/22/0 | Virtual Datastore |
| `Orion.VIM.DatastoresCustomProperties` | `System.CustomPropertiesEntity` | c,d,i,r,u | 1/1/4 | Custom Properties |
| `Orion.VIM.Discovery` | `System.Entity` | i,r | 0/0/6 | Discovery |
| `Orion.VIM.DiskFiles` | `System.Entity` | - | 8/1/0 | Disk File |
| `Orion.VIM.GroupingMapping` | `System.Entity` | - | 3/0/0 | Grouping Mapping |
| `Orion.VIM.HostCpuLoadThreshold` | `Orion.Thresholds` | - | 0/1/0 | CPU Load Threshold |
| `Orion.VIM.HostIPAddresses` | `System.Entity` | - | 2/1/0 | Host IP Addresses |
| `Orion.VIM.HostMACAddresses` | `System.Entity` | - | 2/1/0 | MAC Addresses of Host |
| `Orion.VIM.HostMemUsageThreshold` | `Orion.Thresholds` | - | 0/1/0 | Memory Usage Threshold |
| `Orion.VIM.HostNetworkUtilizationThreshold` | `Orion.Thresholds` | - | 0/1/0 | Network Utilization Threshold |
| `Orion.VIM.HostStatistics` | `System.StatisticsEntity` | - | 37/1/0 | Host Statistics History |
| `Orion.VIM.HostStorageStatistics` | `System.StatisticsEntity` | - | 14/1/0 | Storage Statistics |
| `Orion.VIM.HostThresholds` | `Orion.Thresholds` | - | 0/1/0 |  |
| `Orion.VIM.Hosts` | `System.ManagedEntity` | i,r,u | 62/30/0 | Virtual Host |
| `Orion.VIM.HostsCustomProperties` | `System.CustomPropertiesEntity` | c,d,i,r,u | 1/1/4 | Custom Properties |
| `Orion.VIM.HyperVDiscovered` | `System.Indication` | - | 0/0/0 | HyperV Discovered |
| `Orion.VIM.LicenseInfo` | `System.Entity` | - | 3/0/0 | License Info |
| `Orion.VIM.LunStoragePaths` | `System.Entity` | - | 5/0/0 | LUN Storage Path |
| `Orion.VIM.Luns` | `System.Entity` | - | 7/4/0 | LUN |
| `Orion.VIM.Nas` | `System.Entity` | - | 7/3/0 | NAS |
| `Orion.VIM.NodeChildStatusEntities` | `Orion.NodeChildStatusContributors` | - | 0/0/0 | List of entities that affect child status |
| `Orion.VIM.NutanixClusterDeleted` | `System.Indication` | - | 0/0/0 | Nutanix Cluster Deleted |
| `Orion.VIM.NutanixDiscovered` | `System.Indication` | - | 0/0/0 | Nutanix Discovered |
| `Orion.VIM.Platform` | `System.Entity` | - | 2/1/0 | Platform |
| `Orion.VIM.PollingSettingsChanged` | `System.Indication` | - | 0/0/0 | Polling Settings Changed |
| `Orion.VIM.PollingTasks` | `System.Entity` | - | 10/2/0 |  |
| `Orion.VIM.ProxmoxVEDiscovered` | `System.Indication` | - | 0/0/0 | ProxmoxVE Discovered |
| `Orion.VIM.Recommendations` | `Orion.Recommendations.RecommendationsBase` | - | 2/0/0 | VIM Recommendation |
| `Orion.VIM.Recommendations.DataGroupInfo` | `System.Entity` | - | 3/0/0 | VIM Data Group |
| `Orion.VIM.ResourcePools` | `System.Entity` | - | 29/2/0 | VMResource Pool |
| `Orion.VIM.ServiceStarted` | `System.Indication` | - | 0/0/0 | Service Started |
| `Orion.VIM.Snapshots` | `System.Entity` | - | 7/1/0 | Virtual Machine Snapshot |
| `Orion.VIM.TagCategories` | `System.Entity` | - | 3/1/0 | Hypervisor Tags |
| `Orion.VIM.TagCustomPropertiesMapping` | `System.Entity` | - | 4/0/0 | Tag Custom Properties Mapping |
| `Orion.VIM.Tags` | `System.Entity` | i,r | 3/8/1 | Hypervisor Tags |
| `Orion.VIM.ThresholdTypes` | `System.Entity` | - | 8/1/0 | VMware Threshold Type |
| `Orion.VIM.Thresholds` | `System.Entity` | - | 5/1/0 | VMware Threshold |
| `Orion.VIM.TriggeredAlarmState` | `System.Entity` | c,d,i,r,u | 16/6/0 | VMware Triggered Alarm |
| `Orion.VIM.VCenters` | `System.ManagedEntity` | - | 26/10/0 | VMware vCenter |
| `Orion.VIM.VMConfigDataChanges` | `System.Entity` | - | 10/0/0 | VM Config Data Changes |
| `Orion.VIM.VMStatistics` | `Orion.Virtualization.Statistics` | - | 80/1/0 | VM Statistics History |
| `Orion.VIM.VMwareManagedStatusChanged` | `System.Indication` | - | 0/0/0 | VMware Managed Status Changed |
| `Orion.VIM.VMwareNodes` | `System.Entity` | - | 17/0/0 | VMware Nodes |
| `Orion.VIM.VMwareThresholdChanged` | `System.Indication` | - | 0/0/0 | VMware Threshold Changed |
| `Orion.VIM.VirtualDiskVolumeMapping` | `System.Entity` | - | 2/0/0 | Virtual Disk Volume Mapping |
| `Orion.VIM.VirtualDisks` | `System.Entity` | - | 30/5/0 | Virtual Disk |
| `Orion.VIM.VirtualDisksStatistics` | `System.StatisticsEntity` | - | 28/1/0 | Virtual Disks Statistics History |
| `Orion.VIM.VirtualMachineCpuLoadThreshold` | `Orion.Thresholds` | - | 0/1/0 | CPU Load Threshold |
| `Orion.VIM.VirtualMachineCpuReadyThreshold` | `Orion.Thresholds` | - | 0/1/0 | CPU Ready Threshold |
| `Orion.VIM.VirtualMachineIOPSReadThreshold` | `Orion.Thresholds` | - | 0/1/0 | Read IOPS Threshold |
| `Orion.VIM.VirtualMachineIOPSTotalThreshold` | `Orion.Thresholds` | - | 0/1/0 | Total IOPS Threshold |
| `Orion.VIM.VirtualMachineIOPSWriteThreshold` | `Orion.Thresholds` | - | 0/1/0 | Write IOPS Threshold |
| `Orion.VIM.VirtualMachineIPAddresses` | `System.Entity` | - | 4/1/0 | Virtual Machine IP Addresses |
| `Orion.VIM.VirtualMachineLatencyReadThreshold` | `Orion.Thresholds` | - | 0/1/0 | Read Latency Threshold |
| `Orion.VIM.VirtualMachineLatencyTotalThreshold` | `Orion.Thresholds` | - | 0/1/0 | Total Latency Threshold |
| `Orion.VIM.VirtualMachineLatencyWriteThreshold` | `Orion.Thresholds` | - | 0/1/0 | Write Latency Threshold |
| `Orion.VIM.VirtualMachineMACAddresses` | `System.Entity` | - | 2/1/0 | MAC Addresses of Virtual Machine |
| `Orion.VIM.VirtualMachineMediaDevices` | `System.Entity` | - | 3/1/0 | Virtual Media Device |
| `Orion.VIM.VirtualMachineMemUsageThreshold` | `Orion.Thresholds` | - | 0/1/0 | Memory Usage Threshold |
| `Orion.VIM.VirtualMachineNetworkUsageRateThreshold` | `Orion.Thresholds` | - | 0/1/0 | Network Usage Rate Threshold |
| `Orion.VIM.VirtualMachineThresholds` | `Orion.Virtualization.InstanceThresholds` | - | 0/1/0 |  |
| `Orion.VIM.VirtualMachineVolumes` | `System.Entity` | - | 5/1/0 | Virtual Machine Volume |
| `Orion.VIM.VirtualMachines` | `Orion.Virtualization.Instance` | - | 76/34/7 | Virtual Machine |
| `Orion.VIM.VirtualMachinesCustomProperties` | `System.CustomPropertiesEntity` | c,d,i,r,u | 1/1/4 | Custom Properties |
| `Orion.VIM.VmManagement` | `System.Indication` | - | 0/0/0 | VM Management |
| `Orion.VPN.L2LTunnel` | `System.Entity` | - | 24/3/2 | List of Site-to-Site Tunnels on VPN device |
| `Orion.VPN.L2LTunnelStatistics` | `System.StatisticsEntity` | - | 5/1/0 |  |
| `Orion.Vendors` | `System.ExtensionEntity` | - | 2/1/0 |  |
| `Orion.Views` | `System.Entity` | c,d,i,r,u | 22/1/4 | Orion's UI Views |
| `Orion.ViewsByDeviceType` | `System.Entity` | - | 3/0/0 | Orion's UI Views by device type |
| `Orion.Virtualization.Instance` | `System.ManagedEntity` | - | 9/0/0 | Virtualization Instance |
| `Orion.Virtualization.InstanceThresholds` | `Orion.Thresholds` | - | 0/0/0 |  |
| `Orion.Virtualization.Statistics` | `System.StatisticsEntity` | - | 15/0/0 | Virtualization Instance Statistics History |
| `Orion.VolumeAverageUsageByDays` | `Orion.UsageByDays` | - | 1/0/0 | Volume Memory load history by days . |
| `Orion.VolumePerformanceHistory` | `System.StatisticsEntity` | - | 15/1/0 |  |
| `Orion.VolumeUsageHistory` | `System.StatisticsEntity` | - | 9/1/0 |  |
| `Orion.VolumeWebUri` | `System.Entity` | - | 3/1/0 |  |
| `Orion.Volumes` | `System.ManagedEntity` | c,d,i,r,u | 53/22/5 |  |
| `Orion.VolumesCustomProperties` | `System.CustomPropertiesEntity` | i,r,u | 1/1/5 |  |
| `Orion.VolumesForecastCapacity` | `Orion.ForecastCapacity` | - | 3/1/0 | Capacity Forecasting for Volumes. |
| `Orion.VolumesStats` | `System.ExtensionEntity` | - | 10/1/0 |  |
| `Orion.VolumesThresholds` | `Orion.Thresholds` | - | 0/0/0 |  |
| `Orion.Web.Cloud.MenuItemChanges` | `Orion.Web.MenuItemChanges` | - | 0/0/0 | This entity represents megamenu item customizations. |
| `Orion.Web.DPA.MenuBarChanges` | `Orion.Web.MenuBarChanges` | - | 0/0/0 | This entity represents the changes in website menu bar. |
| `Orion.Web.EOC.MenuBarChanges` | `Orion.Web.MenuBarChanges` | - | 0/0/0 |  |
| `Orion.Web.FavoriteResource` | `System.Entity` | c,d,i,r,u | 3/1/0 | All resources marked as favorite by a user account. |
| `Orion.Web.LegacyModules.MenuBarChanges` | `Orion.Web.MenuBarChanges` | - | 0/0/0 | Implementation of legacy menu plugins for old version od modules. New module versions should use Orion.Web.Me… |
| `Orion.Web.LegacyModules.MenuItemChanges` | `Orion.Web.MenuItemChanges` | - | 0/0/0 | Implementation of legacy menu plugins for old version od modules. New module versions should use Orion.Web.Me… |
| `Orion.Web.LegacyModules.RollupStatusInfo` | `System.Entity` | - | 16/1/0 | Represents legacy rollup status information for modules. |
| `Orion.Web.Menu` | `System.Entity` | - | 9/0/1 | Orion mega menu entity holding final data for menu presentation. |
| `Orion.Web.MenuBarChanges` | `System.Entity` | - | 4/0/0 | Abstract entity for mega menu pluggability. |
| `Orion.Web.MenuBars` | `System.Entity` | - | 3/1/0 | Connects MenuItems into MenuBars, specifies item positions. |
| `Orion.Web.MenuItemChanges` | `System.Entity` | - | 8/0/0 | Abstract entity for mega menu pluggability. |
| `Orion.Web.MenuItems` | `System.Entity` | - | 8/1/0 | Contains data for menu items. |
| `Orion.Web.OLM.MenuBarChanges` | `Orion.Web.MenuBarChanges` | - | 0/0/0 | Indication triggered when menu bar changes. |
| `Orion.Web.Resource` | `System.Entity` | c,d,i,r,u | 2/3/0 | Defines web site resource types |
| `Orion.Web.ResourceSetting` | `System.Entity` | c,d,i,r,u | 4/1/0 | Defines web site resource default configuration |
| `Orion.Web.ResourceUserSetting` | `System.Entity` | c,d,i,r,u | 5/2/0 | Defines web site resource user configuration |
| `Orion.Web.UserWebView` | `System.Entity` | c,d,i,r,u | 2/0/0 | Represents relation between Users and WebViews. |
| `Orion.Web.VIM.MenuBarChanges` | `Orion.Web.MenuBarChanges` | - | 4/0/0 |  |
| `Orion.Web.VIM.MenuItemChanges` | `Orion.Web.MenuItemChanges` | - | 8/0/0 |  |
| `Orion.Web.View` | `System.Entity` | c,d,i,r,u | 13/3/0 | Defines web site view types |
| `Orion.Web.ViewGroup` | `System.Entity` | c,d,i,r,u | 6/2/0 | Defines web site view group types |
| `Orion.WebCommunityStrings` | `System.Entity` | r | 2/0/0 |  |
| `Orion.WebSettings` | `System.Entity` | - | 2/0/0 | There are important setting which belongs to Web Console. |
| `Orion.WebUserSettings` | `System.Entity` | c,d,r,u | 3/0/0 | There are important setting which belongs to Web Console and some user. |
| `Orion.Websites` | `System.Entity` | - | 8/0/0 | Entity contains informations about all existing Web Console instances. |
| `Orion.Wireless.AccessPoints` | `Orion.Wireless.Entity` | - | 6/0/0 |  |
| `Orion.Wireless.AccessPoints.Autonomous` | `Orion.Wireless.AccessPoints` | - | 0/0/0 |  |
| `Orion.Wireless.AccessPoints.Thin` | `Orion.Wireless.AccessPoints` | - | 0/0/0 |  |
| `Orion.Wireless.Clients` | `Orion.Wireless.Entity` | - | 17/0/0 |  |
| `Orion.Wireless.ClientsSessionHistory` | `System.Entity` | - | 16/0/0 |  |
| `Orion.Wireless.Controllers` | `Orion.Wireless.Entity` | - | 2/0/0 |  |
| `Orion.Wireless.Entity` | `System.Entity` | - | 7/0/0 |  |
| `Orion.Wireless.HistoricalAccessPoints` | `Orion.Wireless.Entity` | - | 4/0/0 |  |
| `Orion.Wireless.HistoricalAccessPoints.Autonomous` | `Orion.Wireless.HistoricalAccessPoints` | - | 0/0/0 |  |
| `Orion.Wireless.HistoricalAccessPoints.Thin` | `Orion.Wireless.HistoricalAccessPoints` | - | 0/0/0 |  |
| `Orion.Wireless.HistoricalClients` | `Orion.Wireless.Entity` | - | 14/0/0 |  |
| `Orion.Wireless.HistoricalInterfaces` | `Orion.Wireless.Entity` | - | 5/0/0 |  |
| `Orion.Wireless.Interfaces` | `Orion.Wireless.Entity` | - | 20/0/0 |  |
| `Orion.Wireless.Rogue` | `Orion.Wireless.Entity` | - | 5/0/0 |  |
| `Orion.WirelessHeatMap.AccessPoints` | `System.ManagedEntity` | - | 23/2/0 |  |
| `Orion.WirelessHeatMap.AccessPoints.WebUri` | `System.Entity` | - | 2/1/0 |  |
| `Orion.WirelessHeatMap.ClientLocation` | `System.Entity` | - | 7/1/0 |  |
| `Orion.WirelessHeatMap.ErrorCode` | `System.Entity` | - | 1/0/0 |  |
| `Orion.WirelessHeatMap.Map` | `Orion.Map` | c,d,i,r,u | 13/1/14 |  |
| `Orion.WirelessHeatMap.MapPoint` | `Orion.Map.Point` | i,r | 2/2/4 |  |
| `Orion.WirelessHeatMap.Measurement` | `System.Entity` | - | 5/1/0 |  |
| `Orion.WirelessHeatMap.PollingStatus` | `System.Entity` | - | 6/0/0 |  |
| `Orion.WirelessHeatMap.ResourceClientLimitation` | `System.Entity` | - | 3/0/0 |  |
| `Orion.WirelessHeatMap.ResourceLimitation` | `System.Entity` | - | 5/0/1 |  |
| `Orion.WirelessHeatMap.SignalIdentification` | `System.Entity` | - | 6/1/0 |  |
| `Orion.WorldMap.Point` | `System.Entity` | c,d,i,r,u | 7/3/0 |  |
| `Orion.WorldMap.PointLabel` | `System.Entity` | c,d,i,r,u | 2/1/0 | Location name for World Map point. |

## IPAM

77 entities.

| Entity | Base | Ops | P/R/V | Summary |
| --- | --- | --- | --- | --- |
| `IPAM.AccountRoles` | `System.Entity` | - | 10/0/0 |  |
| `IPAM.AttrDefine` | `System.Entity` | - | 2/0/3 |  |
| `IPAM.CidrMaskDefinition` | `System.Entity` | - | 2/0/0 |  |
| `IPAM.CloudAccountSettings` | `System.Entity` | - | 6/0/0 |  |
| `IPAM.CloudDnsRecords` | `System.Entity` | - | 21/0/0 |  |
| `IPAM.CloudDnsZones` | `System.Entity` | - | 10/0/0 |  |
| `IPAM.Conflict` | `System.Entity` | - | 27/0/0 |  |
| `IPAM.ConflictDetail` | `System.Entity` | - | 33/0/0 |  |
| `IPAM.DHCPFailover` | `System.Entity` | - | 16/0/0 |  |
| `IPAM.DHCPScopeOverlapping` | `System.Entity` | - | 8/1/0 |  |
| `IPAM.DHCPView` | `System.Entity` | - | 40/1/0 |  |
| `IPAM.DNSMismatch` | `System.Entity` | - | 12/0/0 |  |
| `IPAM.DhcpDnsManagement` | `System.Entity` | - | 0/0/18 |  |
| `IPAM.DhcpExclusions` | `System.Entity` | - | 7/1/0 |  |
| `IPAM.DhcpGroup` | `System.Entity` | - | 3/0/0 |  |
| `IPAM.DhcpLease` | `System.Entity` | - | 14/1/0 |  |
| `IPAM.DhcpOptionServerMeta` | `System.Entity` | - | 6/0/0 |  |
| `IPAM.DhcpOptionWebMeta` | `System.Entity` | - | 13/0/0 |  |
| `IPAM.DhcpOptions` | `System.Entity` | - | 5/1/0 |  |
| `IPAM.DhcpOptionsValue` | `System.Entity` | - | 3/1/0 |  |
| `IPAM.DhcpPool` | `System.Entity` | - | 4/0/0 |  |
| `IPAM.DhcpRange` | `System.Entity` | - | 8/1/0 |  |
| `IPAM.DhcpScope` | `System.Entity` | - | 33/5/0 |  |
| `IPAM.DhcpScopeProperties` | `System.Entity` | - | 10/0/0 |  |
| `IPAM.DhcpServer` | `System.Entity` | - | 42/2/0 |  |
| `IPAM.DhcpServerType` | `System.Entity` | - | 2/0/0 |  |
| `IPAM.DhcpSharedNetwork` | `System.Entity` | - | 5/0/0 |  |
| `IPAM.DiscoveredSubnets` | `System.Entity` | - | 23/0/0 |  |
| `IPAM.DnsMasterServerView` | `System.Entity` | - | 3/0/0 |  |
| `IPAM.DnsRecord` | `System.Entity` | - | 6/2/0 |  |
| `IPAM.DnsRecordReport` | `System.Entity` | - | 6/0/0 |  |
| `IPAM.DnsRecordType` | `System.Entity` | - | 3/0/0 |  |
| `IPAM.DnsServer` | `System.Entity` | - | 19/2/0 |  |
| `IPAM.DnsServerType` | `System.Entity` | - | 2/0/0 |  |
| `IPAM.DnsView` | `System.Entity` | - | 3/0/0 |  |
| `IPAM.DnsZone` | `System.Entity` | - | 15/4/0 |  |
| `IPAM.DnsZoneType` | `System.Entity` | - | 2/0/0 |  |
| `IPAM.EventType` | `System.Entity` | - | 1/0/0 |  |
| `IPAM.FailoverMode` | `System.Entity` | - | 2/0/0 |  |
| `IPAM.GroupAncestors` | `System.Entity` | - | 3/0/0 |  |
| `IPAM.GroupManagement` | `System.Entity` | - | 0/0/4 |  |
| `IPAM.GroupNode` | `System.Entity` | - | 63/11/0 |  |
| `IPAM.GroupNodeAttr` | `System.Entity` | c,d,i,r,u | 1/2/0 |  |
| `IPAM.GroupNodeDisplayCustomProperties` | `System.Entity` | - | 6/1/0 |  |
| `IPAM.GroupReport` | `System.Entity` | - | 50/8/0 |  |
| `IPAM.GroupRole` | `System.Entity` | - | 4/0/0 |  |
| `IPAM.GroupRoleNode` | `System.Entity` | - | 43/0/0 |  |
| `IPAM.GroupsCustomProperties` | `System.CustomPropertiesEntity` | c,d,i,r,u | 1/5/4 |  |
| `IPAM.IPAddressManagement` | `System.Entity` | - | 0/0/10 |  |
| `IPAM.IPConflict` | `System.Entity` | - | 12/1/0 |  |
| `IPAM.IPHistory` | `System.Entity` | - | 17/3/0 |  |
| `IPAM.IPHistorySubnetInfo` | `System.Entity` | - | 4/0/0 |  |
| `IPAM.IPInfo` | `System.Entity` | - | 31/0/0 |  |
| `IPAM.IPNode` | `System.Entity` | c,d,i,r,u | 34/4/0 |  |
| `IPAM.IPNodeAttr` | `System.Entity` | c,d,i,r,u | 1/1/0 |  |
| `IPAM.IPNodeDisplayCustomProperties` | `System.Entity` | - | 1/1/0 |  |
| `IPAM.IPNodeGrid` | `System.Entity` | - | 40/2/0 |  |
| `IPAM.IPNodeReport` | `System.Entity` | - | 30/3/0 |  |
| `IPAM.IPNodeWithHistory` | `System.Entity` | - | 35/1/0 |  |
| `IPAM.IPRequestAddresses` | `System.Entity` | c,d,i,r,u | 11/0/0 |  |
| `IPAM.IPRequests` | `System.Entity` | c,d,i,r,u | 17/0/0 |  |
| `IPAM.ImportStarted` | `System.Indication` | - | 0/0/0 |  |
| `IPAM.IpAddressesForReservation` | `System.Entity` | - | 21/0/0 |  |
| `IPAM.ManageSubnetsAndIps` | `System.Entity` | - | 17/1/0 |  |
| `IPAM.NodeMinCorrespondingIps` | `System.Entity` | - | 8/0/0 |  |
| `IPAM.NodesCustomProperties` | `System.CustomPropertiesEntity` | c,d,i,r,u | 1/4/4 |  |
| `IPAM.PrefixAggregate` | `System.Entity` | - | 6/1/0 |  |
| `IPAM.RequesterDetailsFieldsMetadata` | `System.Entity` | c,d,i,r,u | 5/0/0 |  |
| `IPAM.RequesterDetailsFieldsValues` | `System.Entity` | c,d,i,r,u | 4/0/0 |  |
| `IPAM.ScanInstance` | `System.Entity` | - | 7/1/0 |  |
| `IPAM.Setting` | `System.Entity` | c,d,i,r,u | 5/0/0 |  |
| `IPAM.Subnet` | `System.Entity` | c,d,i,r,u | 33/1/0 |  |
| `IPAM.SubnetManagement` | `System.Entity` | - | 0/0/21 |  |
| `IPAM.SubnetStructureChanged` | `System.Indication` | - | 2/0/0 |  |
| `IPAM.SupernetManagement` | `System.Entity` | - | 0/0/3 |  |
| `IPAM.TopUtilDHCPScopes` | `System.Entity` | - | 45/0/0 |  |
| `IPAM.UIJob` | `System.Entity` | - | 18/0/0 |  |

## NCM

72 entities.

| Entity | Base | Ops | P/R/V | Summary |
| --- | --- | --- | --- | --- |
| `NCM.AccessList` | `System.Entity` | - | 5/0/0 | Detected and parsed access lists from config files. For valid Orion user with at least WebViewer NCM role. Re… |
| `NCM.AceShadowRuleDetectionResult` | `System.Entity` | - | 4/0/0 | Shadow rule detection result for one access control list entry. For valid Orion user with at least WebViewer… |
| `NCM.ArpTables` | `System.Entity` | - | 12/3/0 | ARP tables inventory data. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `NCM.BaselineNodeMap` | `System.Entity` | c,d,i,r,u | 4/0/0 | Assignment of baselines to nodes. Reading valid for Orion users with at least WebViewer NCM role. Creating, u… |
| `NCM.BaselineViolations` | `System.Entity` | c,d,i,r,u | 5/0/0 | Baseline violations latest data. Reading valid for Orion users with at least WebViewer NCM role. Read-only. |
| `NCM.Baselines` | `System.Entity` | c,d,i,r,u | 8/0/0 | Multinode baselines. Reading valid for Orion users with at least WebViewer NCM role. Creating, updating and d… |
| `NCM.BridgePorts` | `System.Entity` | - | 12/4/0 | Bridge ports inventory data. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `NCM.BrocadeAgentConfigModule` | `System.Entity` | - | 7/1/0 | Brocade Agent Config Module data. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `NCM.BrocadeChassis` | `System.Entity` | - | 3/1/0 | Brocade Chassis Serial Number data. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `NCM.BrocadeChassisUnit` | `System.Entity` | - | 3/1/0 | Brocade Chassis Unit Serial Number data. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `NCM.CATOSPorts` | `System.Entity` | - | 7/2/0 | The list of CATOS ports. For valid Orion user with at least WebViewer NCM role. |
| `NCM.CatalystCards` | `System.Entity` | - | 17/2/0 | The list of catalyst cards. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `NCM.CiscoBootloadImages` | `System.Entity` | - | 8/3/0 | Data about Cisco bootload images. For valid Orion user with at least WebViewer NCM role. |
| `NCM.CiscoCards` | `System.Entity` | - | 16/2/0 | The list of Cisco cards. For valid Orion user with at least WebViewer NCM role. |
| `NCM.CiscoCdp` | `System.Entity` | - | 15/3/0 | The list of information about directly connected devices found by Cisco CDP. For valid Orion user with at lea… |
| `NCM.CiscoChassis` | `System.Entity` | - | 19/2/0 | The list of Cisco devices. For valid Orion user with at least WebViewer NCM role. |
| `NCM.CiscoFlash` | `System.Entity` | - | 15/2/0 | The list of Cisco flashes. For valid Orion user with at least WebViewer NCM role. |
| `NCM.CiscoFlashFiles` | `System.Entity` | - | 9/2/0 | Data about Cisco flash files. For valid Orion user with at least WebViewer NCM role. |
| `NCM.CiscoFruFanTrayStatus` | `System.Entity` | - | 7/3/0 | Data about Cisco field replaceable unit tray status. For valid Orion user with at least WebViewer NCM role. |
| `NCM.CiscoFruPowerStatus` | `System.Entity` | - | 8/3/0 | Data about Cisco field replaceable unit power status. For valid Orion user with at least WebViewer NCM role. |
| `NCM.CiscoFruPowerSupplyGroups` | `System.Entity` | - | 11/3/0 | Data about Cisco field replaceable unit power supply groups. For valid Orion user with at least WebViewer NCM… |
| `NCM.CiscoImageMIB` | `System.Entity` | - | 8/2/0 | Data about Cisco Images of the Management Information Base. For valid Orion user with at least WebViewer NCM… |
| `NCM.CiscoMemoryPools` | `System.Entity` | - | 9/2/0 | Data about Cisco memory pools. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `NCM.ConfigArchive` | `Orion.LogEntity` | - | 14/1/0 | Data about downloaded configs. For valid Orion user with at least WebViewer NCM role. |
| `NCM.ConfigBackupStatistic` | `System.Entity` | - | 4/0/0 | Config backup statistics. Read-only. |
| `NCM.ConfigBackupStatus` | `System.Entity` | - | 8/0/0 | Data about config backup status. Read-only. |
| `NCM.ConfigInterface` | `System.Entity` | - | 4/0/0 | Data about config interfaces. For valid Orion user with at least WebViewer NCM role. |
| `NCM.ConfigInterfaceIpAddress` | `System.Entity` | - | 3/0/0 | Data about config interface IP addresses. For valid Orion user with at least WebViewer NCM role. |
| `NCM.ConfigTypeVendors` | `System.Entity` | c,d,r,u | 3/0/0 | Data about available config type vendors. Valid for Orion manage node users with at least WebUploader NCM rol… |
| `NCM.ConfigTypes` | `System.Entity` | r | 3/0/3 | Data about available config types. Valid for Orion manage node users with at least WebUploader NCM role. |
| `NCM.EntityLogical` | `System.Entity` | - | 10/2/0 | Logical entities data. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `NCM.EntityPhysical` | `System.Entity` | - | 21/6/0 | Physical entities data. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `NCM.EntityPhysicalJuniper` | `System.Entity` | - | 12/1/0 | Documentation from https://www.juniper.net/documentation/en_US/junos/topics/reference/mibs/mib-jnx-chassis.tx… |
| `NCM.Eos` | `System.Entity` | - | 0/0/4 | Operations related to End of Support. |
| `NCM.F5GTMVirtualServers` | `System.Entity` | - | 4/1/0 | F5 BIG‑IP Global Traffic Manager Data This entity is obsolete - data in this entry is no longer updated. For… |
| `NCM.F5LTMNodeAddresses` | `System.Entity` | - | 7/1/0 | F5 BIG‑IP Local Traffic Manager node addresses data. For valid Orion user with at least WebViewer NCM role. R… |
| `NCM.F5LTMVirtualServers` | `System.Entity` | - | 3/1/0 | F5 BIG‑IP Local Traffic Manager virtual servers data. For valid Orion user with at least WebViewer NCM role.… |
| `NCM.F5System` | `System.Entity` | - | 28/1/0 | F5 system data. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `NCM.FirmwareDefinitions` | `System.Entity` | - | 7/0/4 | Firmware definitions data. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `NCM.FirmwareOperationNodes` | `System.Entity` | c,d,r,u | 5/0/0 | Nodes associated with firmware operations. Reading valid for Orion users with at least WebViewer NCM role. Cr… |
| `NCM.FirmwareOperations` | `System.Entity` | c,d,i,r,u | 10/0/7 | Firmware operations data. Reading valid for Orion users with at least WebViewer NCM role. Creating, updating… |
| `NCM.FirmwareOperationsView` | `System.Entity` | - | 10/0/0 | Firmware operations view with operation history |
| `NCM.FirmwareStorage` | `System.Entity` | - | 0/0/3 | Verbs related to Firmware storage |
| `NCM.FirmwareUpgradeImages` | `System.Entity` | c,d,r,u | 8/0/0 | Firmware upgrade images data. Reading valid for Orion users with at least WebViewer NCM role. Creating, updat… |
| `NCM.FirmwareUpgradeMachineTypes` | `System.Entity` | c,d,r,u | 2/0/0 | Data indicating which images may be applicable for which machine types. Reading valid for Orion users with at… |
| `NCM.Interfaces` | `System.Entity` | - | 24/8/0 | Interfaces data For valid Orion user with at least WebViewer NCM role. Read-only. |
| `NCM.InventoryStatistic` | `System.Entity` | - | 2/0/0 | NCM Inventory statistics. Read-only. |
| `NCM.IpAddresses` | `System.Entity` | - | 14/2/0 | IP addresses data. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `NCM.LatestTransferJobStatus` | `System.Entity` | - | 5/0/0 | Status data about latest transfer jobs. Read-only. |
| `NCM.MacForwarding` | `System.Entity` | - | 8/3/0 | MAC forwarding data. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `NCM.NodeProperties` | `System.Entity` | - | 31/40/0 | Data about NCM nodes. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `NCM.Nodes` | `System.Entity` | i,r,u | 48/22/0 | Data about NCM nodes. For valid Orion user with at least WebViewer NCM role. Updates possible only by users w… |
| `NCM.ObjectDefinitionData` | `System.Entity` | - | 5/0/0 | Data about parsed ACL objects. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `NCM.ObjectDefinitionDataValue` | `System.Entity` | - | 3/0/0 | Parsed ACL object values. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `NCM.ObjectGroupData` | `System.Entity` | - | 6/0/0 | Parsed ACL object group data. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `NCM.OneTimeOperations` | `System.Entity` | - | 12/0/2 | Data about one time operations generated by AI. |
| `NCM.ParsedConfigData` | `System.Entity` | - | 5/0/0 | Parsed config data. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `NCM.PortsTcp` | `System.Entity` | - | 12/2/0 | TCP ports inventory data. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `NCM.PortsUdp` | `System.Entity` | - | 8/2/0 | UDP ports inventory data. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `NCM.RTNAudit` | `System.Entity` | - | 6/1/0 | Historical event raised by the Real-Time change detection. For valid Orion user with at least WebViewer NCM r… |
| `NCM.RouteTable` | `System.Entity` | - | 19/3/0 | Route tables inventory data. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `NCM.RuleDetection` | `System.Entity` | - | 4/0/0 | Shadow rule detection results. For valid Orion user with at least WebViewer NCM role. Read-only. Example: SEL… |
| `NCM.SecurityPolicy` | `System.Entity` | - | 0/0/1 | Data of the security policies. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `NCM.ShadowRuleDetectionAclStatistics` | `System.Entity` | - | 8/0/0 | Acl statistics of shadow rule detections. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `NCM.ShadowRuleDetectionResult` | `System.Entity` | - | 4/0/0 | Results of shadow rule detection. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `NCM.TransferResults` | `System.Entity` | - | 16/2/0 | Data about all transfer results. |
| `NCM.VLANs` | `System.Entity` | - | 10/2/0 | Data about VLANs. For valid Orion user with at least WebViewer NCM role. |
| `NCM.VulnerabilitiesAnnouncements` | `System.Entity` | - | 9/1/4 | Vulnerability announcements. For valid Orion user with at least WebViewer NCM role. This entity is obsolete a… |
| `NCM.VulnerabilitiesAnnouncementsNodes` | `System.Entity` | - | 5/2/0 | Vulnerability announcements' nodes. For valid Orion user with at least WebViewer NCM role. This entity is obs… |
| `NCM.WindowsAccounts` | `System.Entity` | - | 5/1/0 | Data about used Windows accounts. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `NCM.WindowsServices` | `System.Entity` | - | 9/1/0 | Data about used Windows services. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `NCM.WindowsSoftware` | `System.Entity` | - | 6/1/0 | Data about used Windows software. For valid Orion user with at least WebViewer NCM role. Read-only. |

## Cortex

69 entities.

| Entity | Base | Ops | P/R/V | Summary |
| --- | --- | --- | --- | --- |
| `Cortex.Orion.CiscoAci.Apic` | `System.ManagedEntity` | c,d,i,r,u | 14/7/2 |  |
| `Cortex.Orion.CiscoAci.ApplicationProfile` | `System.ManagedEntity` | c,d,i,r,u | 14/4/0 |  |
| `Cortex.Orion.CiscoAci.ApplicationProfile.Metrics` | `System.StatisticsEntity` | r | 5/1/0 |  |
| `Cortex.Orion.CiscoAci.EndpointGroup` | `System.ManagedEntity` | c,d,i,r,u | 14/3/0 |  |
| `Cortex.Orion.CiscoAci.EndpointGroup.Metrics` | `System.StatisticsEntity` | r | 5/1/0 |  |
| `Cortex.Orion.CiscoAci.Fabric` | `System.ManagedEntity` | c,d,i,r,u | 13/3/0 |  |
| `Cortex.Orion.CiscoAci.Fabric.Metrics` | `System.StatisticsEntity` | r | 5/1/0 |  |
| `Cortex.Orion.CiscoAci.PhysicalEntity` | `System.ManagedEntity` | c,d,i,r,u | 16/3/0 |  |
| `Cortex.Orion.CiscoAci.PhysicalEntity.Metrics` | `System.StatisticsEntity` | r | 5/1/0 |  |
| `Cortex.Orion.CiscoAci.Tenant` | `System.ManagedEntity` | c,d,i,r,u | 13/3/0 |  |
| `Cortex.Orion.CiscoAci.Tenant.Metrics` | `System.StatisticsEntity` | r | 5/1/0 |  |
| `Cortex.Orion.Cpu` | `Cortex.System.ElementInstance` | c,d,i,r,u | 3/3/0 |  |
| `Cortex.Orion.Cpu.Metrics` | `System.StatisticsEntity` | r | 4/1/0 |  |
| `Cortex.Orion.Cpu.Statistics` | `System.StatisticsEntity` | r | 2/1/0 |  |
| `Cortex.Orion.Credential` | `Cortex.System.ElementInstance` | d,i,r,u | 2/1/0 |  |
| `Cortex.Orion.Interface` | `Cortex.Orion.MonitoringElement` | c,d,i,r,u | 20/3/8 |  |
| `Cortex.Orion.Interface.Metrics` | `System.StatisticsEntity` | r | 27/1/0 |  |
| `Cortex.Orion.Interface.Statistics` | `System.StatisticsEntity` | r | 10/1/0 |  |
| `Cortex.Orion.MonitoringElement` | `Cortex.Orion.PartitionedInstance` | d,i,r,u | 5/0/7 |  |
| `Cortex.Orion.NetMan.CloudMonitoring.AzureMonitoringCredential` | `Cortex.Orion.Credential` | c,d,i,r,u | 5/1/0 |  |
| `Cortex.Orion.NetMan.CloudMonitoring.CloudAccount` | `System.ManagedEntity` | c,d,i,r,u | 21/6/10 |  |
| `Cortex.Orion.NetMan.CloudMonitoring.CloudMonitoringCentralizedSettings` | `Cortex.System.ElementInstance` | c,d,i,r,u | 3/1/0 |  |
| `Cortex.Orion.NetMan.CloudMonitoring.VirtualNetwork` | `System.ManagedEntity` | c,d,i,r,u | 14/2/7 |  |
| `Cortex.Orion.NetMan.CloudMonitoring.VirtualNetworkConnection` | `System.ManagedEntity` | c,d,i,r,u | 28/3/7 |  |
| `Cortex.Orion.NetMan.CloudMonitoring.VirtualNetworkConnection.AvailabilityMetrics` | `System.StatisticsEntity` | r | 4/1/0 |  |
| `Cortex.Orion.NetMan.CloudMonitoring.VirtualNetworkConnection.Metrics` | `System.StatisticsEntity` | r | 7/1/0 |  |
| `Cortex.Orion.NetMan.CloudMonitoring.VirtualNetworkGateway` | `System.ManagedEntity` | c,d,i,r,u | 25/5/7 |  |
| `Cortex.Orion.NetMan.CloudMonitoring.VirtualNetworkGateway.AvailabilityMetrics` | `System.StatisticsEntity` | r | 4/1/0 |  |
| `Cortex.Orion.NetMan.CloudMonitoring.VirtualNetworkGateway.Metrics` |  | r | 7/1/0 |  |
| `Cortex.Orion.NetMan.Firewalls.Firewall` | `System.ManagedEntity` | c,d,i,r,u | 8/5/5 |  |
| `Cortex.Orion.NetMan.Firewalls.Firewall.Metrics` | `System.StatisticsEntity` | r | 4/1/0 |  |
| `Cortex.Orion.NetMan.Firewalls.RemoteAccess` | `System.ManagedEntity` | c,d,i,r,u | 24/2/0 |  |
| `Cortex.Orion.NetMan.Firewalls.RemoteAccess.Metrics` | `System.StatisticsEntity` | r | 13/1/0 |  |
| `Cortex.Orion.NetMan.Firewalls.SiteToSiteTunnel` | `System.ManagedEntity` | c,d,i,r,u | 23/2/0 |  |
| `Cortex.Orion.NetMan.Firewalls.SiteToSiteTunnel.Metrics` | `System.StatisticsEntity` | r | 16/1/0 |  |
| `Cortex.Orion.Node` | `Cortex.Orion.MonitoringElement` | c,d,i,r,u | 19/5/8 |  |
| `Cortex.Orion.Node.HealthMetrics` | `System.StatisticsEntity` | r | 6/1/0 |  |
| `Cortex.Orion.Node.Statistics` | `System.StatisticsEntity` | r | 3/1/0 |  |
| `Cortex.Orion.PartitionedInstance` | `Cortex.System.ElementInstance` | d,i,r,u | 1/0/0 |  |
| `Cortex.Orion.PowerControlUnit` | `System.ManagedEntity` | c,d,i,r,u | 34/4/0 |  |
| `Cortex.Orion.PowerControlUnit.Metrics` | `System.StatisticsEntity` | r | 29/1/0 |  |
| `Cortex.Orion.PowerControlUnit.Statistics` | `System.StatisticsEntity` | r | 12/1/0 |  |
| `Cortex.Orion.ScsiInformation` | `Cortex.System.ElementInstance` | c,d,i,r,u | 6/1/0 |  |
| `Cortex.Orion.SnmpCredential` | `Cortex.Orion.Credential` | d,i,r,u | 0/0/0 |  |
| `Cortex.Orion.UsernamePasswordCredential` | `Cortex.Orion.Credential` | d,i,r,u | 2/0/0 |  |
| `Cortex.Orion.Virtualization.Alarm` | `System.Entity` | r | 9/0/0 |  |
| `Cortex.Orion.Virtualization.Cluster.StorageMetrics` | `System.StatisticsEntity` | r | 28/0/0 |  |
| `Cortex.Orion.Virtualization.Host.ResourceMetrics` | `System.StatisticsEntity` | r | 7/0/0 |  |
| `Cortex.Orion.Virtualization.Host.Statistics` | `System.StatisticsEntity` | r | 36/0/0 |  |
| `Cortex.Orion.Virtualization.Host.StorageMetrics` | `System.StatisticsEntity` | r | 30/0/0 |  |
| `Cortex.Orion.Virtualization.HypervisorEntity` | `Cortex.Orion.MonitoringElement` | d,i,r,u | 1/0/7 |  |
| `Cortex.Orion.Virtualization.PhysicalDisk` | `Cortex.System.ElementInstance` | c,d,i,r,u | 8/1/0 |  |
| `Cortex.Orion.Virtualization.StoragePool` | `Cortex.System.ElementInstance` | c,d,i,r,u | 6/1/0 |  |
| `Cortex.Orion.Virtualization.TriggeredAlarmState` | `System.Entity` | r | 16/0/0 |  |
| `Cortex.Orion.Virtualization.VSan` | `Cortex.Orion.MonitoringElement` | c,d,i,r,u | 27/9/7 |  |
| `Cortex.Orion.Virtualization.VSan.Statistics` | `System.StatisticsEntity` | r | 12/1/0 |  |
| `Cortex.Orion.Virtualization.VSan.VSanMetrics` | `System.StatisticsEntity` | r | 12/1/0 |  |
| `Cortex.Orion.Virtualization.VSanDiskGroup` | `Cortex.System.ElementInstance` | c,d,i,r,u | 5/3/0 |  |
| `Cortex.Orion.Virtualization.VSanHealthGroup` | `Cortex.System.ElementInstance` | c,d,i,r,u | 5/1/0 |  |
| `Cortex.Orion.Virtualization.VSanObjectSpaceSummary` | `Cortex.System.ElementInstance` | c,d,i,r,u | 4/1/0 |  |
| `Cortex.Orion.Virtualization.VSanResyncInfo` | `Cortex.System.ElementInstance` | c,d,i,r,u | 5/3/0 |  |
| `Cortex.Orion.Virtualization.VirtualMachineDisk.Statistics` | `System.StatisticsEntity` | r | 4/0/0 |  |
| `Cortex.Orion.Virtualization.VirtualMachineDisk.VSanMetrics` | `System.StatisticsEntity` | r | 4/1/0 |  |
| `Cortex.Orion.Volume` | `Cortex.Orion.MonitoringElement` | c,d,i,r,u | 23/5/8 |  |
| `Cortex.Orion.Volume.CapacityMetrics` | `System.StatisticsEntity` | r | 7/1/0 |  |
| `Cortex.Orion.Volume.PerformanceMetrics` | `System.StatisticsEntity` | r | 13/1/0 |  |
| `Cortex.Orion.Volume.Statistics` | `System.StatisticsEntity` | r | 7/1/0 |  |
| `Cortex.System.ElementInstance` |  | d,i,r,u | 1/0/0 |  |
| `Cortex.System.Policy` | `Cortex.System.ElementInstance` | c,d,i,r,u | 6/0/0 |  |

## Cirrus

57 entities.

| Entity | Base | Ops | P/R/V | Summary |
| --- | --- | --- | --- | --- |
| `Cirrus.ApproveQueue` | `System.Entity` | - | 14/0/12 | A queue with request to approve or decline. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.ApproveQueueNodes` | `System.Entity` | - | 3/0/0 | A queue with request to specfic nodes. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.ArpTables` | `System.Entity` | - | 11/0/0 | ARP tables inventory data. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.Audit` | `System.Entity` | - | 10/0/0 | User activity events. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.Backup_vs_AllNodes` | `System.Entity` | - | 4/0/0 | Backup vs all nodes report data For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.BridgePorts` | `System.Entity` | - | 11/0/0 | Bridge ports inventory data. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.CacheDiffResults` | `System.Entity` | - | 13/0/0 | The results of the config comparisons. For valid Orion user with at least WebViewer NCM role. |
| `Cirrus.CatalystCards` | `System.Entity` | - | 16/0/0 | The list of catalyst cards. For valid Orion user with at least WebViewer NCM role. |
| `Cirrus.CiscoCards` | `System.Entity` | - | 15/0/0 | The list of Cisco cards. For valid Orion user with at least WebViewer NCM role. |
| `Cirrus.CiscoCdp` | `System.Entity` | - | 14/0/0 | The list of information about directly connected devices found by Cisco CDP. For valid Orion user with at lea… |
| `Cirrus.CiscoChassis` | `System.Entity` | - | 18/0/0 | The list of Cisco devices. For valid Orion user with at least WebViewer NCM role. |
| `Cirrus.CiscoFlash` | `System.Entity` | - | 14/0/0 | The list of Cisco flashes. For valid Orion user with at least WebViewer NCM role. |
| `Cirrus.CiscoFlashFiles` | `System.Entity` | - | 8/0/0 | Data about Cisco flash files. For valid Orion user with at least WebViewer NCM role. |
| `Cirrus.CiscoImageMIB` | `System.Entity` | - | 7/0/0 | Data about Cisco Images of Management Information Base. For valid Orion user with at least WebViewer NCM role… |
| `Cirrus.CiscoMemoryPools` | `System.Entity` | - | 8/0/0 | Data about Cisco memory pools. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.CompareRegExs` | `System.Entity` | - | 8/0/0 | Data about RegExes used in comparison. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.ComparisonCache` | `System.Entity` | - | 2/0/0 | Comparison cache data. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.ConfigArchive` | `System.Entity` | - | 14/1/24 | Data about downloaded configs. For valid Orion user with at least WebViewer NCM role. |
| `Cirrus.ConfigSnippets` | `System.Entity` | - | 7/0/11 | Data about config snippets. For valid Orion user with at least WebViewer NCM role. |
| `Cirrus.EntityLogical` | `System.Entity` | - | 9/0/0 | Logical entities data. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.EntityPhysical` | `System.Entity` | - | 19/0/0 | Physical entities data. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.GlobalSettings` | `System.Entity` | - | 2/0/0 | Global settings data. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.IgnoredNodes` | `System.Entity` | c,d,i,r | 1/0/0 | Nodes to be ignored during discovery. Creating, reading and deleting valid for Orion users with manage node p… |
| `Cirrus.Interfaces` | `System.Entity` | - | 20/2/0 | Interfaces data For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.IpAddresses` | `System.Entity` | - | 13/1/0 | IP addresses data. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.LatestComparisonResults` | `System.Entity` | - | 4/0/0 | Data about latest config comparison results. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.LatestPolicyReportViolations` | `System.Entity` | - | 4/0/0 | Data about latest policy report violations. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.MacForwarding` | `System.Entity` | - | 7/0/0 | MAC forwarding data. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.MatrixTargets` | `System.Entity` | - | 7/0/0 | Matrix targets data. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.NCMNodeLicenseStatus` | `System.Entity` | - | 2/1/0 | Data about licensed NCM nodes. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.NCM_ApproveQueueView` | `System.Entity` | - | 14/0/0 | A queue with request to approve or decline. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.NCM_EosMatchQueue` | `System.Entity` | - | 14/0/0 | Queue data for NCM EOS functionality. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.NCM_JobEngineNCMJobs` | `System.Entity` | - | 4/0/0 | Data used by the JobEngine for processing NCM jobs. For valid Orion user with at least WebViewer NCM role. Re… |
| `Cirrus.NCM_NCMJobs` | `System.Entity` | - | 10/0/9 | NCM jobs definitions. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.NCM_NCMJobsView` | `System.Entity` | - | 15/0/0 | NCM jobs definitions. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.NodeProperties` | `System.Entity` | i,r,u | 40/0/0 | Data about NCM nodes. For valid Orion user with at least WebViewer NCM role. Updates possible only by users w… |
| `Cirrus.Nodes` | `System.Entity` | i,r,u | 66/1/25 | Data about NCM nodes. For valid Orion user with at least WebViewer NCM role. Updates possible only by users w… |
| `Cirrus.Options` | `System.Entity` | - | 2/0/0 | Obsolete settings. Not used anymore. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.Policies` | `System.Entity` | - | 7/0/0 | Policies used in NCM compliance. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.PolicyAssignment` | `System.Entity` | - | 2/0/0 | Link between policies and policy reports. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.PolicyCache` | `System.Entity` | - | 2/0/0 | Root data about compliance policy cache. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.PolicyCacheResults` | `System.Entity` | - | 18/0/0 | Cached compliance data. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.PolicyReportViolations` | `System.Entity` | - | 6/0/0 | Violatations displayed in the compliance policy reports. For valid Orion user with at least WebViewer NCM rol… |
| `Cirrus.PolicyReports` | `System.Entity` | - | 11/0/26 | Reports used in NCM compliance. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.PolicyRuleAssignment` | `System.Entity` | - | 2/0/0 | Link between policies and rules. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.PolicyRules` | `System.Entity` | - | 15/0/0 | Data about compliance policy rules. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.PortsTcp` | `System.Entity` | - | 11/0/0 | TCP ports inventory data. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.PortsUdp` | `System.Entity` | - | 7/0/0 | UDP ports inventory data. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.RTN` | `System.Entity` | - | 0/0/2 | Internal methods for handling RTN. Without user access. |
| `Cirrus.RouteTable` | `System.Entity` | - | 18/0/0 | Route tables inventory data. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.Settings` | `System.Entity` | - | 0/0/20 | Verbs connected with settings management. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.SnippetArchive` | `System.Entity` | - | 6/0/3 | Config snippets archive. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.Tags` | `System.Entity` | - | 2/0/0 | Data about tags in config change templates. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.VLANs` | `System.Entity` | - | 9/0/0 | Data about VLANs. For valid Orion user with at least WebViewer NCM role. |
| `Cirrus.WindowsAccounts` | `System.Entity` | - | 5/0/0 | Data about used Windows accounts. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.WindowsServices` | `System.Entity` | - | 9/0/0 | Data about used Windows services. For valid Orion user with at least WebViewer NCM role. Read-only. |
| `Cirrus.WindowsSoftware` | `System.Entity` | - | 6/0/0 | Data about used Windows software. For valid Orion user with at least WebViewer NCM role. Read-only. |

## System

29 entities.

| Entity | Base | Ops | P/R/V | Summary |
| --- | --- | --- | --- | --- |
| `System.ActiveQuery` | `System.Entity` | d,i,r | 11/0/1 |  |
| `System.ComputerSystem` | `System.ManagedEntity` | - | 4/0/0 |  |
| `System.CustomPropertiesEntity` | `System.ExtensionEntity` | - | 0/0/0 | Inherits from System.ExtensionEntity and defines no additional properties. If you support user-defined proper… |
| `System.DashboardEntity` | `System.Entity` | - | 4/0/0 | System.DashboardEntity was created for use in Modern Dashboard which require for properties defined in System… |
| `System.Diagnostic` | `System.Entity` | - | 2/0/0 |  |
| `System.Entity` |  | - | 5/1/0 | System.Entity is the root of the SWIS type hierarchy. It carries no particular meaning or semantics. Choose S… |
| `System.EntityTypeStatistics` | `System.Entity` | r | 2/0/0 |  |
| `System.ExtensionEntity` | `System.Entity` | - | 0/0/0 | Inherits from System.Entity and defines no additional properties. ExtensionEntity types are for providing add… |
| `System.Feature` | `System.Entity` | - | 1/0/0 |  |
| `System.Indication` | `System.Entity` | i,r | 4/0/1 |  |
| `System.InstanceCreated` | `System.InstanceIndication` | - | 0/0/0 |  |
| `System.InstanceDeleted` | `System.InstanceIndication` | - | 0/0/0 |  |
| `System.InstanceIndication` | `System.Indication` | - | 2/0/0 |  |
| `System.InstanceModified` | `System.InstanceIndication` | - | 0/0/0 |  |
| `System.LoadedAssembly` | `System.Entity` | r | 3/0/0 |  |
| `System.ManagedEntity` | `System.DashboardEntity` | - | 9/1/0 | A ManagedEntity is basically "something that has an externally-determined up/down status". These entities rep… |
| `System.NativeFeature` | `System.Feature` | - | 1/0/0 |  |
| `System.NullEntity` | `System.Entity` | - | 0/0/0 |  |
| `System.QueryExecuted` | `System.Indication` | - | 9/0/0 |  |
| `System.QueryPlanCache` | `System.Entity` | r | 3/0/1 |  |
| `System.SchemaChanged` | `System.Indication` | - | 0/0/0 |  |
| `System.StatisticsEntity` | `System.ExtensionEntity` | - | 3/0/0 | A sub-type of System.ExtensionEntity for statistical data |
| `System.Subscription` | `System.Entity` | c,d,r | 13/0/0 |  |
| `System.SubscriptionIncludedProperty` | `System.Entity` | c,d,r | 2/0/0 |  |
| `System.SubscriptionProperty` | `System.Entity` | c,d,r | 3/0/0 |  |
| `System.SystemIdentifier` | `System.Entity` | - | 2/0/0 |  |
| `System.ThreeLevelTheshold` | `System.Threshold` | - | 6/0/0 |  |
| `System.Threshold` | `System.Entity` | - | 1/0/0 |  |
| `System.TwoLevelTheshold` | `System.Threshold` | - | 4/0/0 |  |

## DPA

18 entities.

| Entity | Base | Ops | P/R/V | Summary |
| --- | --- | --- | --- | --- |
| `DPA.BlockingChain` | `System.ExtensionEntity` | r | 7/0/0 | The entity represents trees of blocker-blockee relationship as in the "Blockers" tab in the UI |
| `DPA.BlockingOverview` | `System.ExtensionEntity` | r | 8/0/0 | Blocking/Blocked time data |
| `DPA.DatabaseClient` | `System.ExtensionEntity` | r | 4/0/0 | Provides mapping between machine (client) (identified by its address) and monitored DB instance (identified b… |
| `DPA.Deadlock` | `System.Entity` | r | 11/0/0 | Collected deadlock information |
| `DPA.DetailDataDimension` | `System.ExtensionEntity` | r | 15/1/0 | Detail Wait Time statistics for DB instance |
| `DPA.ExpertAdviceInfo` | `System.ExtensionEntity` | r | 4/0/0 | The entity represents advises given on the "Waits" tab in the UI |
| `DPA.PerformanceOverview` | `System.ExtensionEntity` | r | 12/1/0 | High level overview across monitored databases |
| `DPA.ProblemSQLStatement` | `System.ExtensionEntity` | r | 8/0/0 | Single problem related to SQL Statement execution |
| `DPA.ProblemSummary` | `System.ExtensionEntity` | r | 13/1/0 | Represents single problem summary in relation to analysis (Advisors) |
| `DPA.ProductInfo` | `System.Entity` | - | 6/1/0 | Information about DPA, version, SWIP ID, SWIS schema version, http(s) port(s) |
| `DPA.ResourceData` | `System.ExtensionEntity` | r | 8/0/0 | Provides data-points of DB resources. It has single parameter that is required (DatabaseId) and two more that… |
| `DPA.ResourceDefinition` | `System.ExtensionEntity` | r | 8/1/0 | Provides definition of DB resources (metrics grouped in categories). It provides no dynamic values (in terms… |
| `DPA.SQLQueryInfo` | `System.Entity` | r | 5/0/0 | The entity provides the full formatted sql text and custom name for given sqlhash. DatabaseId and Hash are ma… |
| `DPA.SqlServerQueryHash` | `System.ExtensionEntity` | r | 4/0/0 | Provides mapping between SQL Handle and its Hash in scope of the given database instance. Both DatabaseId and… |
| `DPA.TimeSeriesData` | `System.StatisticsEntity` | r | 9/1/0 | PerfStack compatible metric data |
| `DPA.TimeSeriesDefinition` | `System.ExtensionEntity` | r | 11/1/0 | Definition of PerfStack compatible metrics available for specific Database Instance |
| `DPA.TrendDataDimension` | `System.ExtensionEntity` | r | 12/1/0 | Trend data for DB instance per dimension |
| `DPA.WaitData` | `System.Entity` | r | 17/0/0 | PerfStack data explorer data for waits |

## Metadata

11 entities.

| Entity | Base | Ops | P/R/V | Summary |
| --- | --- | --- | --- | --- |
| `Metadata.Entity` | `System.Entity` | - | 22/7/2 |  |
| `Metadata.EntityAlias` | `System.Entity` | - | 5/1/0 |  |
| `Metadata.EntityArgument` | `System.Entity` | - | 3/1/0 |  |
| `Metadata.EntityMetadata` | `System.Entity` | - | 4/1/0 |  |
| `Metadata.Functions` | `System.Entity` | - | 1/0/0 |  |
| `Metadata.Property` | `System.Entity` | - | 23/2/0 |  |
| `Metadata.PropertyMetadata` | `System.Entity` | - | 5/1/0 |  |
| `Metadata.Relationship` | `System.Entity` | - | 20/3/0 |  |
| `Metadata.RelationshipMetadata` | `System.Entity` | - | 4/1/0 |  |
| `Metadata.Verb` | `System.Entity` | - | 8/2/0 |  |
| `Metadata.VerbArgument` | `System.Entity` | - | 9/1/0 |  |

## ContentModel

8 entities.

| Entity | Base | Ops | P/R/V | Summary |
| --- | --- | --- | --- | --- |
| `ContentModel.ContentEntityCategory` | `System.Entity` | - | 3/0/0 |  |
| `ContentModel.ContentEntityCategoryGroupMembers` | `System.Entity` | - | 9/0/0 |  |
| `ContentModel.ContentEntityCategoryGroups` | `System.Entity` | - | 5/0/0 |  |
| `ContentModel.ContentEntityTypes` | `System.Entity` | - | 5/0/0 |  |
| `ContentModel.ContentFormatField` | `System.Entity` | - | 11/0/0 | The ContentFormatField entity provides a way for developers to map existing or new ContentTypes to existing o… |
| `ContentModel.ContentType` | `System.Entity` | - | 6/0/0 | A ContentType describes the underlying data associated with an entity property at a higher level that the nat… |
| `ContentModel.EntityNameSpaceCategoryGroups` | `System.Entity` | - | 5/0/0 |  |
| `ContentModel.OrionNodes` | `System.DashboardEntity` | - | 6/0/0 |  |

## Cli

5 entities.

| Entity | Base | Ops | P/R/V | Summary |
| --- | --- | --- | --- | --- |
| `Cli.CliSessionSettings` | `System.Entity` | c,d,i,r,u | 2/0/4 | Settings used by the CLI component. For valid Orion Platform users with manage node permissions. Some setting… |
| `Cli.CliSessionTrace` | `System.Entity` | r | 7/0/0 | Session trace used by the CLI component. For valid Orion Platform users with manage node permissions. |
| `Cli.Credentials` | `System.Entity` | - | 0/0/0 |  |
| `Cli.DeviceTemplates` | `System.Entity` | c,d,r,u | 10/0/0 | Device templates. For valid Orion Platform users with manage node permissions. |
| `Cli.DeviceTemplatesNodes` | `System.Entity` | c,d,r,u | 2/0/0 | Manually assign device templates to nodes. Each node can have only one device template assigned. When a devic… |

## UamsClient

5 entities.

| Entity | Base | Ops | P/R/V | Summary |
| --- | --- | --- | --- | --- |
| `UamsClient.ClientRuntimeInfo` | `System.Entity` | r | 7/0/0 | This entity returns runtime information about UAMS client available through REST API. |
| `UamsClient.InstallationInfo` | `System.Entity` | i,r | 7/0/5 | This entity returns information about last installation of UAMS client service on the main poller. |
| `UamsClient.PlatformConnectInfo` | `System.Entity` | c,d,r,u | 3/0/0 | This entity stores Platform Connect activation data as key-value pairs for tenant reactivation scenarios. |
| `UamsClient.PlatformConnectWizard` | `System.Entity` | i,r | 0/0/6 | This entity exposes Cloud Connected wizard operations used by the onboarding flow. |
| `UamsClient.PluginsRuntimeInfo` | `System.Entity` | r | 8/0/0 | This entity returns runtime information about plugins deployed in UAMS client available through REST API. |

## PlatformConnect

3 entities.

| Entity | Base | Ops | P/R/V | Summary |
| --- | --- | --- | --- | --- |
| `PlatformConnect.Info` | `System.Entity` | c,d,r,u | 3/0/0 | This entity stores Platform Connect activation data as key-value pairs for tenant reactivation scenarios. |
| `PlatformConnect.Status` | `System.Entity` | r | 4/0/0 | Aggregated Platform Connect status combining activation metadata with the current UAMS client installation st… |
| `PlatformConnect.Wizard` | `System.Entity` | i,r | 0/0/7 | This entity exposes Cloud Connected wizard operations used by the onboarding flow. |

## SWISf

3 entities.

| Entity | Base | Ops | P/R/V | Summary |
| --- | --- | --- | --- | --- |
| `SWISf.EntitySubscriptions` | `System.Entity` | r | 4/0/0 |  |
| `SWISf.ProviderSubscriptions` | `System.Entity` | r | 4/0/0 |  |
| `SWISf.RemoteSWIS` | `System.Entity` | c,d,r,u | 5/1/0 |  |

## SOC

2 entities.

| Entity | Base | Ops | P/R/V | Summary |
| --- | --- | --- | --- | --- |
| `SOC.EntityMapping` | `System.Entity` | c,d,i,r,u | 2/0/0 | This entity contains mapping of HCO and SWO identifiers. E.g., Uri to CloudId. This is used by UAMS plugins t… |
| `SOC.Settings` | `System.Entity` | i,r | 2/0/1 | This entity contains settings for configuring SOC plugin of UAMS Client. |

## Vdc

2 entities.

| Entity | Base | Ops | P/R/V | Summary |
| --- | --- | --- | --- | --- |
| `Vdc.Contexts` | `System.Entity` | - | 5/0/0 | Virtual device contexts. For valid Orion user with at least WebViewer NCM role. |
| `Vdc.System` | `System.Entity` | - | 2/0/0 | VDC systems. For valid Orion user with at least WebViewer NCM role. |

## PlatformBridge

1 entities.

| Entity | Base | Ops | P/R/V | Summary |
| --- | --- | --- | --- | --- |
| `PlatformBridge.Info` | `System.Entity` | i,r | 6/0/6 | Encrypted persistent and temporary Platform Bridge data store. |

---

`Ops` abbreviates the declared operations by first letter: `c` create, `r` read, `u` update, `d` delete, `i` invoke.

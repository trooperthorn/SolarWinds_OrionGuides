<!-- GENERATED FILE. Do not edit by hand.
     Produced by tools/build_reference_docs.py from data/schema/2026.2/.
     Regenerate with: make docs-reference -->

# NetObject type reference

A NetObject string identifies one monitored object as a type prefix and an id: node 42 is `N:42`, interface 7 is `I:7`. The prefix is not decorative. It appears in alert macros, in web console URLs, in report definitions, and as the `netObjectId` argument that verbs such as `Unmanage` and `PollNow` expect. Passing a bare `42` where `N:42` is required is one of the most common automation mistakes.

**Key properties** are the columns that form the entity's primary key, which is what a SWIS URI is built from and what CRUD operations address. **Parent** is the entity this one hangs off, which tells you where to look for the owning node.

This table comes from a community reference workbook that predates the current schema, so it is checked against the published entity list on every build. Rows marked in the Status column no longer exist under that name in **2026.2**; where a successor could be identified with confidence it is named.

115 entries across 16 modules; 12 no longer resolve in 2026.2.

| Module | Entity | Display name | Prefix | Key properties | Parent | Status |
| --- | --- | --- | --- | --- | --- | --- |
| Agent | `Orion.AgentManagement.Agent` | Core Agents |  | `AgentId`, `AgentGuid`, `NodeId`, `PollingEngineID` | `Orion.Nodes` | current |
| Core | `Orion.AlertStatus` | Core Alerts |  | `AlertDefID`, `ActiveObject`, `AlertObjectID` |  | current |
| Core | `Orion.AssetInventory.NodeWarrantyAlert` | Node Warranty | `NWA` | `NodeID` | `Orion.Nodes` | current |
| Core | `Orion.AuditingEvents` | Auditing Events |  | `AuditEventID` |  | current |
| Core | `Orion.ContainerMembers` | Group Member | `GM` | `ContainerID`, `MemberEntityType`, `MemberPrimaryID` |  | current |
| Core | `Orion.EventTypes` | Core Event Types |  | `EventType` | `Orion.Events` | current |
| Core | `Orion.Events` | Core Events |  | `EventID` |  | current |
| Core | `Orion.Groups` | Group | `C` | `ContainerID` |  | current |
| Core | `Orion.NodeVlans` | VLAN | `NVLAN` | `NodeID`, `VlanId` | `Orion.Nodes` | current |
| Core | `Orion.Nodes` | Node | `N` | `NodeID` | `Orion.Engines` | current |
| Core | `Orion.Volumes` | Volume | `V` | `VolumeID` |  | current |
| DPA | `Orion.DPA.DatabaseInstance` | Database Instance | `DBI` | `DatabaseInstanceID` |  | current |
| IPAM | `IPAM.DHCPScopeOverlapping` | IPAM DHCPScopes Overlapping | `IPAM-DSO` | `ScopeId` |  | current |
| IPAM | `IPAM.GroupReport` | IPAM Networks | `IPAMG` | `GroupId` |  | current |
| IPAM | `IPAM.IPConflict` | IPAM IPAddress Conflict | `IPAMN` | `IPNodeId` |  | current |
| IPAM | `IPAM.IPNodeReport` | IPAM Nodes | `IPAMN` | `IPNodeId` |  | current |
| NCM | `Cirrus.Nodes` | NCM Nodes |  | `NodeID`, `CoreNodeID`, `EngineID` |  | current |
| NPM | `Orion.F5.Device` | F5 Devices | `F5` | `ID` |  | renamed to `Orion.F5.System.Device` |
| NPM | `Orion.F5.Nodes` | F5 Nodes | `FN` | `ID` |  | not in this version |
| NPM | `Orion.F5.Pools` | F5 Pools | `FP` | `ID` |  | renamed to `Orion.F5.GTM.Pool` |
| NPM | `Orion.F5.VirtualServers` | F5 Virtual Servers | `FVS` | `ID` |  | renamed to `Orion.F5.GTM.VirtualServer` |
| NPM | `Orion.NPM.CustomPollerAssignmentOnInterface` | Custom Interface Poller | `UNDPI` | `CustomPollerAssignmentID` |  | current |
| NPM | `Orion.NPM.CustomPollerAssignmentOnNode` | Custom Node Poller | `UNDPN` | `CustomPollerAssignmentID` |  | current |
| NPM | `Orion.NPM.CustomPollerStatusOnNodeTabular` | Custom Node Table Poller | `UNDPT` | `CompressedRowID`, `CustomPollerAssignmentID` |  | current |
| NPM | `Orion.NPM.EW.Entity` | EnergyWise Entity | `EWE` | `ID` |  | current |
| NPM | `Orion.NPM.FCPorts` | Fibre Channel Port | `FCP` | `Index`, `UnitID` |  | current |
| NPM | `Orion.NPM.FCRevisions` | Fibre Channel Revision | `FCR` | `Index`, `UnitID` |  | current |
| NPM | `Orion.NPM.FCSensors` | Fibre Channel Sensor | `FCS` | `Index`, `UnitID` |  | current |
| NPM | `Orion.NPM.FCUnits` | Fibre Channel Unit | `FCU` | `ID` |  | current |
| NPM | `Orion.NPM.Interfaces` | Interface | `I` | `InterfaceID` |  | current |
| NPM | `Orion.NPM.MulticastRouting.GroupNodes` | Multicast Routing | `MCGN` | `MulticastGroupNodeID` |  | current |
| NPM | `Orion.NPM.MulticastRouting.Groups` | Multicast Routing Group | `MCG` | `MulticastGroupID` |  | current |
| NPM | `Orion.NPM.UCSBlades` | UCS Blade | `UCSB` | `ID` |  | renamed to `Orion.UCS.Blades` |
| NPM | `Orion.NPM.UCSChassis` | UCS Chassis | `NCH` | `ID` |  | renamed to `Orion.UCS.Chassis` |
| NPM | `Orion.NPM.UCSFabrics` | UCS Fabric | `UCSF` | `ID` |  | renamed to `Orion.UCS.Fabrics` |
| NPM | `Orion.NPM.UCSFans` | UCS Fan | `UCSFAN` | `ID` |  | not in this version |
| NPM | `Orion.NPM.UCSManagers` | UCS Manager | `UCSM` | `NodeID` | `Orion.Nodes` | not in this version |
| NPM | `Orion.NPM.UCSPSUs` | UCS Psu | `UCSPSU` | `ID` |  | not in this version |
| NPM | `Orion.NPM.VSANs` | VSAN | `NVS` | `ID` |  | current |
| NPM | `Orion.Packages.Wireless.AccessPoints` | Wireless Access Point | `WLAP` | `ID` |  | current |
| NPM | `Orion.Packages.Wireless.Controllers` | Wireless Controller | `WLC` | `NodeID` | `Orion.Nodes` | current |
| NPM | `Orion.Routing.Neighbors` | Routing Neighbors | `NBR` | `NeighborID` |  | current |
| NPM | `Orion.Routing.VRF` | VRF | `VRF` | `VrfIndex` |  | current |
| NPM | `Orion.WirelessHeatMap.Map` | Wireless Heatmap | `WLHM` | `MapID` |  | current |
| NPM / SAM | `Orion.HardwareHealth.HardwareCategoryStatus` | Hardware Type | `HWHT` | `ID` |  | current |
| NPM / SAM | `Orion.HardwareHealth.HardwareInfo` | Hardware | `HWH` | `ID` |  | current |
| NPM / SAM | `Orion.HardwareHealth.HardwareItem` | Hardware Sensor | `HWHS` | `ID` |  | current |
| NTA | `Orion.Netflow.CBQoSPolicyMetric` | NTA: CBQoS Class Map | `CCM` | `MetricID` |  | current |
| QOE | `Orion.DPI.Probes` | QoE Probes |  | `ProbeID`, `AgentID` | `Orion.AgentManagement.Agent (AgentID) Orion.DPI.ProbeAssignments (ProbeID)` | current |
| QoE | `Orion.DPI.ApplicationAssignments` | QoE Application (per node) |  | `ApplicationID`, `NodeID` | `Orion.APM.Application`, `Orion.Nodes` | current |
| QoE | `Orion.DPI.Applications` | QoE Application |  | `ApplicationID` | `Orion.APM.Application` | current |
| QoE | `Orion.Engines` | Core Servers |  | `EngineID` |  | current |
| SAM | `Orion.APM.Application` | APM: Application | `AA` | `ApplicationID` | `Orion.Nodes` | current |
| SAM | `Orion.APM.Component` | APM: Component | `AM` | `ComponentID` | `Orion.APM.Application` | current |
| SAM | `Orion.APM.Exchange.Application` | AppInsight for Exchange: Application | `ABXA` | `ApplicationID` | `Orion.APM.Application` | current |
| SAM | `Orion.APM.Exchange.Database` | AppInsight for Exchange: Database | `ABXD` | `ID` |  | current |
| SAM | `Orion.APM.Exchange.DatabaseCopy` | AppInsight for Exchange: Database Copy | `ABXDC` | `ItemID` |  | current |
| SAM | `Orion.APM.Exchange.DatabaseFile` | AppInsight for Exchange: Database File | `ABXF` | `DatabaseFileID` |  | current |
| SAM | `Orion.APM.Exchange.Mailbox` | AppInsight for Exchange: Mailboxes | `ABXMB` | `ID` |  | current |
| SAM | `Orion.APM.Exchange.ReplicationStatus` | AppInsight for Exchange: Replication Status | `ABXR` | `ID` |  | current |
| SAM | `Orion.APM.GenericApplication` | Application | `AA` | `ApplicationID` | `Orion.APM.Application` | current |
| SAM | `Orion.APM.IIS.Application` | AppInsight for IIS: Application | `ABIA` | `ApplicationID` | `Orion.APM.Application` | current |
| SAM | `Orion.APM.IIS.ApplicationPool` | AppInsight for IIS: Application Pool | `ABIP` | `ItemID` |  | current |
| SAM | `Orion.APM.IIS.Request` | AppInsight for IIS: Request | `ABIR` | `ID` |  | current |
| SAM | `Orion.APM.IIS.RequestDetails` | AppInsight for IIS: Request Details | `ABIRD` | `ID` |  | current |
| SAM | `Orion.APM.IIS.Site` | AppInsight for IIS: Site | `ABIS` | `ItemID` |  | current |
| SAM | `Orion.APM.IIS.SiteBinding` | AppInsight for IIS: Site Binding | `ABISB` | `ID` |  | current |
| SAM | `Orion.APM.SqlDatabase` | AppInsight for SQL: Database | `ABSD` | `ItemID` |  | current |
| SAM | `Orion.APM.SqlDatabaseFile` | AppInsight for SQL: Database File | `ABSF` | `DatabaseFileID` |  | current |
| SAM | `Orion.APM.SqlJobInfo` | AppInsight for SQL: Job Info | `ABSJ` | `JobInfoID` |  | current |
| SAM | `Orion.APM.SqlQuery` | AppInsight for SQL: Expensive Queries Info | `ABSQ` | `QueryID` |  | current |
| SAM | `Orion.APM.SqlServerApplication` | AppInsight for SQL: Application | `ABSA` | `ApplicationID` | `Orion.APM.Application` | current |
| SAM | `Orion.APM.Wstm.Task` | APM: Windows Scheduled Tasks | `ABTT` | `ID` |  | current |
| SRM | `Orion.SRM.Engines` | Polling Engines |  | `EngineID` |  | current |
| SRM | `Orion.SRM.FIleServerIdentification` | SRM File Server ID |  |  | `Orion.SRM.Volumes` | renamed to `Orion.SRM.FileServerIdentification` |
| SRM | `Orion.SRM.FileServers` | SRM File Server |  |  | `Orion.SRM.Volumes` | current |
| SRM | `Orion.SRM.FileShares` | FileShare | `SMS` | `FileShareID` | `Orion.SRM.Volumes` | current |
| SRM | `Orion.SRM.LUNs` | Lun | `SML` | `LUNID` | `Orion.SRM.Pools` | current |
| SRM | `Orion.SRM.PhysicalDisks` | SRM Physical Disks |  |  | `Orion.SRM.StorageArrays` | current |
| SRM | `Orion.SRM.Pools` | Pool | `SMSP` | `PoolID` | `Orion.SRM.StorageArrays` | current |
| SRM | `Orion.SRM.Providers` | Provider | `SMP` | `ProviderID` |  | current |
| SRM | `Orion.SRM.StorageArrays` | StorageArray | `SMSA` | `StorageArrayID`, `ArrayID` |  | current |
| SRM | `Orion.SRM.VServers` | VServer | `SMVS` | `VServerID` |  | current |
| SRM | `Orion.SRM.Volumes` | NAS Volume | `SMV` | `VolumeID` | `Orion.SRM.Pools` | current |
| UDT | `Orion.UDT.AccessPortEndpointCount` | AccessPort | `UP` | `PortID` |  | current |
| UDT | `Orion.UDT.DNSNameCurrent` | UDT: Hostname | `UE-DNS` | `ID` |  | current |
| UDT | `Orion.UDT.MovedMACAlert` | Moved MAC | `UE-MAC` | `ID` |  | current |
| UDT | `Orion.UDT.NewMACAlert` | New MACAddress | `UE-MAC` | `ID` |  | current |
| UDT | `Orion.UDT.NewMACVendorAlert` | New MAC Vendor | `UE-MAC` | `ID` |  | current |
| UDT | `Orion.UDT.Port` | UDT Port |  | `NodeID`, `PortID`, `PortIndex` | `Orion.Nodes` | current |
| UDT | `Orion.UDT.RogueDNSAlert` | Rogue DNSName | `UE-DNS` | `DNSNameID` |  | current |
| UDT | `Orion.UDT.RogueEmptyDNSAlert` | Rogue EmptyDNSName | `UE-IP` | `IPAddressID` |  | current |
| UDT | `Orion.UDT.RogueIPAlert` | Rogue IPAddress | `UE-IP` | `IPAddressID` |  | current |
| UDT | `Orion.UDT.RogueMACAlert` | Rogue MACAddress | `UE-MAC` | `EndpointID` |  | current |
| UDT | `Orion.UDT.WatchListPresent` | Watch List | `UW` | `WatchID` |  | current |
| VIM | `Orion.VIM.Clusters` | Virtual Cluster | `VMC` | `ClusterID` |  | current |
| VIM | `Orion.VIM.DataCenters` | Virtual DataCenter | `VMD` | `DataCenterID` |  | current |
| VIM | `Orion.VIM.Datastores` | Virtual Datastore | `VMS` | `DataStoreID` | `Orion.VIM.LUNs` | current |
| VIM | `Orion.VIM.Hosts` | Virtual Host | `VH` | `HostID`, `NodeID`, `CluserID`, `DatacenterID` |  | current |
| VIM | `Orion.VIM.LUNs` | Virtual LUN |  | `LunID`, `DatastoreID` |  | renamed to `Orion.VIM.Luns` |
| VIM | `Orion.VIM.VCenters` | Virtual Center | `VVC` | `VCenterID` |  | current |
| VIM | `Orion.VIM.VirtualMachines` | Virtual Machine | `VVM` | `VirtualMachineID`, `HostID`, `NodeID` |  | current |
| VNQM | `Orion.IpSla.CCMGateways` | VoIP Gateway | `VG` | `GatewayID` |  | current |
| VNQM | `Orion.IpSla.CCMMonitoring` | VoIP CallManager | `VCCM` | `NodeID` | `Orion.Nodes` | current |
| VNQM | `Orion.IpSla.CCMPhones` | VoIP Phone | `VCCMP` | `ID` |  | current |
| VNQM | `Orion.IpSla.CCMRegions` | VoIP Region | `VR` | `RegionID` |  | current |
| VNQM | `Orion.IpSla.InfrastructureNodes` | VoIP Infrastructure | `P` | `InfrastructureNodeID` |  | current |
| VNQM | `Orion.IpSla.Operations` | IP SLA QoS | `ISOP` | `OperationInstanceID` |  | current |
| VNQM | `Orion.IpSla.VoipCallDetails` | VoIP Call Details | `VCDS` | `ID` |  | current |
| VNQM | `Orion.IpSla.VoipGatewayEndpoints` | VoIP PRI Trunk | `VVGT` | `VoipGatewayEndpointID` |  | current |
| VNQM | `Orion.IpSla.VoipGateways` | VoIP PRI Gateway | `VVG` | `VoipGatewayID` |  | current |
| WPM | `Orion.SEUM.Agents` | Location | `L` | `AgentId` |  | current |
| WPM | `Orion.SEUM.TransactionStepRequests` | Step Request | `TSR` | `TransactionStepRequestId` |  | current |
| WPM | `Orion.SEUM.TransactionSteps` | Step | `TS` | `TransactionStepId` |  | current |
| WPM | `Orion.SEUM.Transactions` | Transaction | `T` | `TransactionId` |  | current |

---

For what a NetObject prefix is, where it is required, and how it differs from a bare id, see [../schema/netobject-types.md](../schema/netobject-types.md). This page is the table; that page is the explanation.

To confirm an entity's key properties against your own server, which is the authoritative answer for your version:

```sql
SELECT Name, Type FROM Metadata.Property
WHERE Entity.FullName = 'Orion.Nodes' AND IsKey = true
```

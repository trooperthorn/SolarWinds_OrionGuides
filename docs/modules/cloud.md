# Cloud monitoring: AWS, Azure and GCP

Cloud monitoring is how the platform watches infrastructure it cannot reach with SNMP or
WMI. Instead of polling a device, it authenticates to a provider's management API with a
stored credential and reads back what that provider says about your account: which
instances exist, what state they are in, what their volumes are doing, what they cost. The
model is account, then region, then resource, and it repeats three times, once per provider.

It is also the largest single family in the schema. **148 entities under `Orion.Cloud.`**,
more than [SAM](sam.md) or [NPM](npm.md) contribute, and it is not a module you buy
separately: cloud monitoring is a platform capability rather than a licensed product with
its own prefix table. That size comes from breadth rather than depth. Most of the 148 are
one service type plus its statistics entity, repeated across the provider catalogue.

## Namespace and how it divides

```bash
python3 tools/schema_query.py find Orion.Cloud
python3 tools/schema_query.py show Orion.Cloud.Accounts
python3 tools/schema_query.py show Orion.Cloud.Instances
python3 tools/schema_query.py verbs --entity Orion.Cloud.Instances
```

| Family | Entities | What it holds |
|---|---:|---|
| `Orion.Cloud.` (no provider segment) | 22 | The generic model: accounts, providers, regions, instances, volumes, tags, job settings, statistics, events, cost |
| `Orion.Cloud.Aws.` | 39 | EC2 instances and volumes, S3, RDS, DynamoDB, Lambda, EKS, ELB, Direct Connect, Transit Gateway, Elastic Beanstalk, cost |
| `Orion.Cloud.Azure.` | 53 | Virtual machines and volumes, App Service, Cosmos DB, SQL, Storage Accounts, AKS, Application Gateway, ExpressRoute, Virtual WAN, cost |
| `Orion.Cloud.Gcp.` | 34 | Compute instances and volumes, GKE, Cloud Storage, BigQuery, Cloud SQL, load balancing, cost |

Forty-four of the 148 are `*Statistics` entities, which is the clearest sign of the
repeating shape: nearly every monitored service type has a sibling holding its time series.

A separate, smaller family sits alongside it. `Orion.CloudMonitoring.` holds 8 entities for
site-to-site VPN, headed by `Orion.CloudMonitoring.CloudVPNGateway` and
`Orion.CloudMonitoring.CloudVPNConnection`, and `Orion.Cloud.Vpcs` navigates into it as
`VirtualNetworkGateways` and `CloudVPNGateways`. Do not assume an entity is under
`Orion.Cloud.` just because it is about cloud.

Confirm what your own installation has, since which service types appear depends on which
pollers were enabled when the account was added:

```sql
SELECT FullName, BaseType, CanCreate, CanUpdate, CanDelete, CanInvoke, IsObsolete
FROM Metadata.Entity
WHERE FullName LIKE 'Orion.Cloud.%'
ORDER BY FullName
```

Cloud entities have no rows in
[`data/reference/netobject-types.json`](../../data/reference/netobject-types.json), but the
module publishes its own equivalent. `Orion.Cloud.Compute.NetObjectTypesView` carries
`EntityType`, `Name`, `Prefix`, `KeyProperty` and `KeyPropertyIndex`, so a live server can
tell you the NetObject prefix for each cloud entity type directly:

```sql
SELECT EntityType, Name, Prefix, KeyProperty, KeyPropertyIndex
FROM Orion.Cloud.Compute.NetObjectTypesView
ORDER BY EntityType
```

## Accounts, providers and regions

### `Orion.Cloud.Accounts` is the root

One row per cloud account or subscription being monitored. It supports create, read,
update, delete and invoke, with read for everyone and everything else requiring **`admin`**.

| Property | What it is |
|---|---|
| `Id` | The key |
| `Name` | The account's name in the platform, not at the provider |
| `CredentialId` | Points at `Orion.Credential`, navigable as `Credential` |
| `ProviderId` | Points at `Orion.Cloud.Providers`, navigable as `Provider` |
| `AutoMonitoring` | Whether newly discovered resources are monitored automatically |
| `DisableMonitorApiRequests` | Whether polling for this account is switched off |
| `PollingIntervalInSeconds` | How often the provider API is called |
| `MonitorResourceType` | Which resources are in scope. See below |
| `MonitorApiRequestsMadePerMonth` | "Approximate amount of free requests made by our polling using given account in current month" |
| `Description`, `DetailsUrl` | Display |

`MonitorApiRequestsMadePerMonth` deserves attention that a counter usually does not: cloud
providers bill for API calls, and `PollingIntervalInSeconds` multiplied by the number of
monitored resources is what drives it. `Orion.Cloud.AccountCounters` carries the AWS
CloudWatch equivalent, `CloudWatchRequestsMadeThisMonth`, and is reached from the account as
`Counters`. Shortening the polling interval on a large account is a cost decision, not just
a freshness decision.

`MonitorResourceType` is an integer whose values SolarWinds documents on the
[BulkAddAwsAccounts](https://solarwinds.github.io/OrionSDK/docs/sam-bulk-add-aws-accounts/)
page as **0 = all resources, 1 = monitor selected entities, 2 = monitor by tags**. The
schema itself gives no description for the column, so that mapping comes from the SDK
documentation rather than from the extracted data.

### Provider subtypes add almost nothing

`Orion.Cloud.Aws.Accounts`, `Orion.Cloud.Azure.Accounts` and `Orion.Cloud.Gcp.Accounts` all
inherit from `Orion.Cloud.Accounts` and declare only what is provider-specific:

| Entity | Declares |
|---|---|
| `Orion.Cloud.Aws.Accounts` | `DisableCloudWatch`, `CloudWatchRequestsMadeThisMonth` |
| `Orion.Cloud.Azure.Accounts` | `SubscriptionName` |
| `Orion.Cloud.Gcp.Accounts` | `AutoMonitoring`, `DisableMonitorApiRequests`, `MonitorApiRequestsMadePerMonth` (re-declared) |

Everything else, `Name`, `CredentialId`, `PollingIntervalInSeconds` and the rest, is
inherited and queryable on the subtype. This is the single most common mistake with this
family: `python3 tools/schema_query.py show Orion.Cloud.Azure.Accounts` prints one property
and looks broken. Use `props`, which includes inherited members:

```bash
python3 tools/schema_query.py props Orion.Cloud.Azure.Accounts
```

The three subtypes declare **no access control table** in the rendered schema while the
Swagger contract publishes a `/Create` path for each. They are three of the eleven entities
where the two sources disagree, described in
[using-the-data.md](../schema/using-the-data.md). Create against `Orion.Cloud.Accounts`, or
check `Metadata.Entity` on your own server first.

### Providers and regions

`Orion.Cloud.Providers` is a three-column catalogue, `Id`, `Name` and
`MonitorDescription`, with `Accounts` and `AllRegions` navigating out of it. It declares no
operations, so the provider list is fixed by the installation.

`Orion.Cloud.Regions` is `Id`, `SystemName`, `DisplayName`, `Enabled` and `ProviderID`.
`SystemName` is the provider's own identifier, `us-east-1` and its equivalents;
`DisplayName` is the readable form. The provider subtypes `Orion.Cloud.Aws.Regions`,
`Orion.Cloud.Azure.Regions` and `Orion.Cloud.Gcp.Regions` again declare nothing of their
own and inherit all five columns. SolarWinds' bulk-add page confirms the practical point:
when you name regions in an API call you pass `SystemName` values, and it gives
`SELECT SystemName, DisplayName FROM Orion.Cloud.Aws.Regions ORDER BY SystemName` as the
way to list the legal ones.

`Enabled` on a region is installation-wide: it says whether the platform will monitor that
region at all. Choosing regions **per account** is a different entity, covered next.

## Scope: job settings, selected regions and tag filters

Three small entities decide what a cloud account actually polls, and they chain together.

**`Orion.Cloud.CloudJobSettings`** is one row of scan configuration per account:
`CloudAccountId`, `NetworkScanEnabled` and `NetworkScanInterval`, `DnsScanEnabled` and
`DnsScanInterval`, `VirtualNetworkGatewaysPollingEnabled`, `SelectedAllRegions` and
`RunCostManagementAtTime`. It navigates to `CloudAccounts`, `SelectedRegions` and
`TagFilter`.

**`Orion.Cloud.SelectedCloudRegions`** is the per-account region list: `Id`,
`CloudJobSettingId`, `CloudRegionId`. It navigates to `CloudJobSettings` and, as
`AllRegions`, to `Orion.Cloud.Regions`. When `SelectedAllRegions` on the job settings is
true this list is not consulted.

**`Orion.Cloud.TagFilter`** is "Tags are assigned to cloud job settings to filter polled
cloud resources": `Id`, `CloudJobSettingId`, `Key`, `Value`. This is the entity behind
`MonitorResourceType = 2`. Every row is one key/value pair a resource must carry to be
polled at all.

All three allow create, read, update, delete and invoke under **`admin`**, so narrowing an
account's scope is ordinary CRUD:

```powershell
$swis = Connect-Swis -Hostname orion.example.com -Credential $cred

$jobSettingId = Get-SwisData $swis @"
SELECT TOP 1 js.Id
FROM Orion.Cloud.CloudJobSettings js
WHERE js.CloudAccounts.Name = @accountName
"@ @{ accountName = 'prod-account-us' }

New-SwisObject $swis Orion.Cloud.TagFilter @{
    CloudJobSettingId = $jobSettingId
    Key               = 'Environment'
    Value             = 'Production'
} | Out-Null
```

### Tag filters and resource tags are different entities

This pair of names causes real confusion, so it is worth stating flatly.

`Orion.Cloud.TagFilter` is **configuration**: the tags you told the platform to filter on.

`Orion.Cloud.ResourseTags` is **data**: the tags the provider says a resource actually
carries. Note the spelling, `ResourseTags` with an s, which is a typo baked into the entity
name and will not be corrected by guessing. Its columns are `Id`, `ResourceType`,
`ResourceId`, `Key`, `Value` and `ProviderId`, and `Orion.Cloud.Aws.ResourseTags` and
`Orion.Cloud.Azure.ResourseTags` are subtypes that add nothing.

`Orion.Cloud.ResourseTags` declares **no navigation properties**, so joining a tag to the
thing it is on is manual and depends on matching `ResourceId` against the right column on
the resource. For an EC2 instance the obvious candidate is
`Orion.Cloud.Instances.InstanceId`, which is also a `System.String`, but the schema does not
declare that correspondence and the exact format of `ResourceId` per provider is
**unverified here**. Inspect a few rows before relying on the join:

```sql
SELECT TOP 25 t.ResourceType, t.ResourceId, t.Key, t.Value, t.ProviderId
FROM Orion.Cloud.ResourseTags t
ORDER BY t.ResourceType
```

## Instances, volumes, and becoming a node

### `Orion.Cloud.Instances`

The generic compute instance, and the entity that carries the module's verbs. Its
inheritance chain explains most of its behaviour:

```text
System.Entity -> System.DashboardEntity -> System.ManagedEntity
              -> Orion.Virtualization.Instance -> Orion.Cloud.Instances
```

It is a virtualisation instance first and a cloud instance second, which is why it shares
`VirtualMachineID`, `NodeID`, `CpuLoad`, `NetworkUsageRate`, `NetworkTransmitRate` and
`NetworkReceiveRate` with [VMAN](vman.md), and why its verbs are keyed on
`virtualMachineId` rather than on a cloud instance id.

It declares 27 properties of its own. Twenty-five of them fall into four groups: identity
(`Name`, `InstanceId`, `Type`, `Image`, `ImageId`, `Platform`, `Provider`, `Region`,
`CloudAccountId`), placement (`SubnetId`, `VpcId`, `VnetId`, `KeyPairName`,
`AutoScalingGroupName`, `PublicDNSName`, `PrivateDNSName`), state (`State`, `StatusLED`,
`LastPoll`, `LastSuccessfulPoll`) and performance (`IOPSTotal`, `IOPSRead`, `IOPSWrite`,
`DiskReadInBytesPerSecond`, `DiskWriteInBytesPerSecond`). The remaining two,
`OrionIdColumn` and `ModernIcon`, are presentation details.

**`InstanceId` and `VirtualMachineID` are not the same id.** `InstanceId` is the provider's
string, the `i-0abc...` form. `VirtualMachineID` is the platform's integer, inherited from
`Orion.Virtualization.Instance`, and it is what every cloud verb takes. Passing the wrong
one is the single most likely automation bug in this module.

**`State` is the provider's own state string**, and `Status` is the platform's integer.
`State` values like `running` come from AWS vocabulary and are not normalised across
providers; `Status` joins to [`Orion.StatusInfo`](../reference/status-codes.md) as usual.

Four entities hang off an instance by `System.Hosting`, so they die with it:

| Navigation | Target | Contents |
|---|---|---|
| `Statistics` | `Orion.Cloud.InstanceStatistics` | Min, max and average for IOPS and disk throughput, per interval |
| `MetricsStatus` | `Orion.Cloud.InstanceStatus` | A separate status integer per metric: `CpuLoadStatus`, `MemoryStatus`, `IOPSTotalStatus`, `DiskReadStatus` and six more |
| `MetricsStatusMacro` | `Orion.Cloud.InstanceStatusMacro` | The same set as readable names, plus `MetricsWithStatusFormatted` |
| `Thresholds` | `Orion.Cloud.InstanceThresholds` | Declares nothing; inherits the generic threshold shape through `Orion.Virtualization.InstanceThresholds` and `Orion.Thresholds` |

`Orion.Cloud.InstanceStatus.MemoryStatus` carries a description worth reading twice:
"Managed status calculated from related Node `PercentMemoryUsed`, if this instance is
mapped to a node". Memory is not something a cloud provider reports for a VM by default, so
this metric only exists when the instance has been paired with a monitored node.

### How a cloud instance becomes a node

They are two objects, joined by one relationship. `Orion.Cloud.Instances.Node` navigates to
`Orion.Nodes` over a `System.Reliance` edge named `Orion.Cloud.NodesToInstances`, and
`Orion.Nodes.CloudInstance` navigates back. `Orion.Cloud.Instances.NodeID` is the column
behind it, inherited from `Orion.Virtualization.Instance`.

From the node side, three string columns record the pairing:
`Orion.Nodes.CloudInstanceID`, `Orion.Nodes.CloudAccountID` and
`Orion.Nodes.CloudZoneID`. All three are `System.String`, matching the provider's own
identifiers rather than the platform's integers.

The practical shape is:

1. The account is polled and the instance appears as an `Orion.Cloud.Instances` row. At this
   point it has cloud metrics only: state, IOPS, network rates, whatever the provider
   reports.
2. Separately, the machine is added as a node, by discovery or by CRUD, with whatever
   polling method reaches it.
3. The two are paired, and the node's own metrics, memory in particular, start feeding the
   cloud instance's status.

An instance with a null `NodeID` is monitored from the outside only. That is a legitimate
state, not necessarily a fault, but it is the state where `MemoryStatus` will be empty and
where nothing inside the guest is being watched. See
[../automation/node-management.md](../automation/node-management.md) for the node half.

`Orion.Cloud.Aws.UnmonitoredInstances` is the step before all of this: 36 properties
describing EC2 instances the platform can see in the account but is not monitoring. It is
read-only, and it is the list to work from when `AutoMonitoring` is off.

### Volumes

`Orion.Cloud.Volumes` is the generic disk: `Id`, `DiskIdentifier`, `Type`, `Size`, `State`,
`Name`, `StatusDescription` and `VirtualMachineId`. It inherits from `System.ManagedEntity`,
so it has a status and can be unmanaged.

The provider subtypes are where the measurements live, and `Orion.Cloud.Aws.Volumes` is the
richest: `ReadLatencyInMilliseconds`, `WriteLatencyInMilliseconds`,
`ReadOperationsPerSecond`, `WriteOperationsPerSecond`, `QueuedOperations`,
`IdleTimePercentage`, `ThroughputPercentage`, `ReadBandwidthInKibibytesPerSecond`,
`WriteBandwidthInKibibytesPerSecond`, `AverageReadOperationSizeInKibibytes`,
`AverageWriteOperationSizeInKibibytes` and `ConsumedIOPS`. It is hosted by
`Orion.Cloud.Aws.Instances`, reachable as `Volumes` from the instance and `CloudInstance`
from the volume, and it hosts `Orion.Cloud.Aws.VolumeStatus` and
`Orion.Cloud.Aws.VolumeStatistics` in turn.

`Orion.Cloud.Azure.Volumes` and `Orion.Cloud.Gcp.Volumes` are hosted the same way by their
own instance types.

### Networking

`Orion.Cloud.Vpcs` is the virtual network: `Name`, `Region`, `Status`, `InternalId`,
`RequestInventory`, `PollState_Value`, `AgentId`, `AgentOsType`, `EngineId`, `Id`,
`RelatedCloudAccount` and `Provider`. `Orion.Cloud.VirtualNetworkAddressSpaces` holds its
prefixes, `Orion.Cloud.NetworkInterfaces` maps a `VirtualMachineId` to a `SubnetId` and
`AddressSpace`, and `Orion.Cloud.SecurityGroups` maps a `VirtualMachineId` to a
`SecurityGroupId` and `SecurityGroupName`. The last three declare no navigation properties,
so join them on `VirtualMachineId` yourself.

### Cost and events

`Orion.Cloud.CostEntities` is the cross-provider cost view: `Category`,
`CategoryEntityType`, `ProviderId`, `ProviderName`, `AccountName`, `ResourceId`, `Region`,
`TotalDailyCost`, `ID` and `ObservationTimestamp`. Each provider also has its own richer
pair, `Orion.Cloud.Aws.CostManagement` and `Orion.Cloud.Aws.CostManagementStatistics` and
their Azure and GCP equivalents, carrying `ServiceName`, `DailyCost` and `PollDate`.

`Orion.Cloud.EventsView` is a pre-joined event list: `EventID`, `EventTime`,
`ProviderName`, `AccountName`, `NetObjectType`, `NetObjectID`, `EventType`, `Message`,
`Acknowledged`, `EntityDetailsUrl` and `EntityStatus`. Both are time series in practice,
so both get an explicit time bound.

## The `Local.` entities in the CRUD surface

If you read SolarWinds' Swagger contract for 2026.2 rather than the rendered schema, you
will find fifteen `/Create/Local.Orion.Cloud.*` paths alongside the ordinary ones: an
`Accounts` form for each of the three providers, `Local.Orion.Cloud.Regions` plus its three
provider forms, `Local.Orion.Cloud.ResourseTags` plus its Aws and Azure forms,
`Local.Orion.Cloud.SelectedCloudRegions`, `Local.Orion.Cloud.CloudJobSettings`,
`Local.Orion.Cloud.TagFilter`, `Local.Orion.Cloud.Gcp.ProjectDetails` and
`Local.Orion.Cloud.Gcp.BigQueryDataset`.

Here is what this repository can verify about them.

- They exist only in the Swagger contract. **None of them appears in the rendered schema
  reference**, so `python3 tools/schema_query.py show` will not find one, and they are not
  among the 148 counted above.
- The prefix is not specific to cloud. The contract carries 113 `/Create/Local.*` paths in
  total, spanning `Local.IPAM.*`, `Local.NCM.*`, `Local.Cirrus.*`, `Local.Orion.Actions`,
  `Local.Orion.AlertDefinitions` and many more. That total is recorded in
  [using-the-data.md](../schema/using-the-data.md), which is also why the repository's
  creatable-entity count is 250 rather than 378.
- The request body schemas are **structurally identical** to the unprefixed forms. Compare
  `Local.Orion.Cloud.Regions` against `Orion.Cloud.Regions` in the contract and you get the
  same six fields, `Id`, `SystemName`, `DisplayName`, `Enabled`, `ProviderID`,
  `Description`, differing only in that the `Local.` copy carries no property descriptions.
- Both forms coexist. Every `Local.Orion.Cloud.*` create path has an unprefixed twin.

What the prefix **means** is not stated anywhere in the extracted data, and this page will
not invent it. The reading that fits the evidence is that `Local.` addresses this server's
own copy of an entity type as opposed to the federated view that a SWIS federation presents
under the plain name. The platform does federate: `SWISf.RemoteSWIS` exists, and
[dpa.md](dpa.md) shows a whole product plugged in that way. **That reading is unverified.**

Practically, none of this should change what you write. **Use the unprefixed entity names.**
They are the ones with published property descriptions, published access control, and a
rendered schema page. If you find yourself needing a `Local.` form, settle the question on
your own server first:

```sql
SELECT FullName, BaseType, CanCreate, CanUpdate, CanDelete, CanInvoke
FROM Metadata.Entity
WHERE FullName LIKE '%Orion.Cloud.Regions'
ORDER BY FullName
```

If the `Local.` name is absent from `Metadata.Entity`, it is not an entity you can address
on that server at all.

## Verbs

Fourteen verbs across five entities. Every one of them takes a single argument except the
GCP region lookup, and arguments are positional as everywhere in SWIS.

### Instance management

| Entity | Verb | Parameters | Returns |
|---|---|---|---|
| `Orion.Cloud.Instances` | `Unmanage` | `virtualMachineId` | `ManagementActionResult` |
| `Orion.Cloud.Instances` | `Remanage` | `virtualMachineId` | `ManagementActionResult` |
| `Orion.Cloud.Instances` | `PollNow` | `virtualMachineId` | `ManagementActionResult` |
| `Orion.Cloud.Instances` | `StartInstance` | `virtualMachineId` | `ManagementActionResult` |
| `Orion.Cloud.Instances` | `StopInstance` | `virtualMachineId` | `ManagementActionResult` |
| `Orion.Cloud.Instances` | `RebootInstance` | `virtualMachineId` | `ManagementActionResult` |
| `Orion.Cloud.Instances` | `DeleteInstance` | `virtualMachineId` | `ManagementActionResult` |
| `Orion.Cloud.Instances` | `DeleteInstanceWithNode` | `virtualMachineId` | `ManagementActionResult` |
| `Orion.Cloud.Aws.Instances` | `ForceStopInstance` | `virtualMachineId` | `ManagementActionResult` |
| `Orion.Cloud.Aws.Instances` | `TerminateInstance` | `virtualMachineId` | `ManagementActionResult` |
| `Orion.Cloud.Aws.Instances` | `TerminateInstanceAndRemoveNode` | `virtualMachineId` | `ManagementActionResult` |

Three things about this table matter more than the names.

**`Unmanage` here does not look like `Unmanage` anywhere else.**
`Orion.Nodes.Unmanage` takes a NetObject string plus a start and end time.
`Orion.Cloud.Instances.Unmanage` takes one number, `virtualMachineId`, and there is no
window. Verify before calling:
`python3 tools/schema_query.py verb Orion.Cloud.Instances Unmanage`.

**Half of these act on the cloud provider, not on the platform.** `StartInstance`,
`StopInstance`, `RebootInstance`, `ForceStopInstance` and `TerminateInstance` change the
real machine. `Unmanage`, `Remanage` and `PollNow` change monitoring. `DeleteInstance` and
`TerminateInstance` are not synonyms, and neither name says clearly which side of the line
it falls on. Read the return value: `ManagementActionResult` carries `Success`,
`ErrorMessage`, `InstanceId`, `PreviousState` and `CurrentState`, and a state transition is
the evidence that a provider-side action happened.

**The `*AndRemoveNode` and `*WithNode` variants delete the platform object too.**
`DeleteInstanceWithNode` and `TerminateInstanceAndRemoveNode` take the paired
`Orion.Nodes` row with them. That is destructive on both sides at once. Confirm before
acting, and see [CONTRIBUTING.md](../../CONTRIBUTING.md) on how destructive operations
should be presented.

```powershell
$swis = Connect-Swis -Hostname orion.example.com -Credential $cred

# Look up the platform integer, not the provider string.
$vmId = Get-SwisData $swis @"
SELECT TOP 1 i.VirtualMachineID
FROM Orion.Cloud.Instances i
WHERE i.InstanceId = @instanceId
"@ @{ instanceId = 'i-0123456789abcdef0' }

$result = Invoke-SwisVerb $swis Orion.Cloud.Instances StopInstance @($vmId)

if ($result.Success -eq 'true') {
    Write-Host "$($result.InstanceId): $($result.PreviousState) -> $($result.CurrentState)"
} else {
    Write-Error $result.ErrorMessage
}
```

### Region discovery

| Entity | Verb | Parameters, in order | Returns |
|---|---|---|---|
| `Orion.Cloud.Aws.Regions` | `GetAwsRegions` | `credentials` | `RegionsResult` |
| `Orion.Cloud.Azure.Regions` | `GetAzureRegions` | `credentials` | `RegionsResult` |
| `Orion.Cloud.Gcp.Regions` | `GetGcpRegions` | `credentials`, `projectId` | `RegionsResult` |

These ask the provider which regions a given credential can reach, which is what the console
does while you are adding an account and before any row exists to query. The credential
argument is a typed object rather than an id, and the three types differ:

| Verb | Credential object fields, per the Swagger contract |
|---|---|
| `GetAwsRegions` | `AccessKeyId`, `SecretAccessKey`, `SecretAccessKeyChanged`, `CredentialsId`, `ID`, `Name`, `Description`, `Owner`, `IsBroken` |
| `GetAzureRegions` | `SubscriptionId`, `TenantId`, `ClientId`, `ApplicationSecretKey`, `ApplicationSecretKeyChanged`, `CredentialsId`, `ID`, `Name`, `Description`, `Owner`, `IsBroken` |
| `GetGcpRegions` | `Issuer`, `KeyId`, `PrivateKey`, `Scopes`, `Url`, `ID`, `Name`, `Description`, `Owner`, `IsBroken` |

`RegionsResult` returns `Success`, `ErrorMessage` and a `Regions` array whose entries carry
`Id`, `SystemName`, `DisplayName`, `AlternativeServiceUrl`, `Enabled`, `CloudProvider` and
`Zones`. Note `Zones`, which the stored `Orion.Cloud.Regions` entity does not have.

All three verbs put provider secrets in the request body, so use HTTPS, which is the only
transport SWIS offers, and do not commit a script with the keys inline. Every one of the
credential objects also accepts an `ID` or `CredentialsId`, which is the route that avoids
sending a secret at all: store the credential once through
[credential management](https://solarwinds.github.io/OrionSDK/docs/credential-management/)
and reference it. Whether passing only the id is sufficient for these three verbs is
**not stated** in the contract; test it before relying on it.

### Adding AWS accounts in bulk

SolarWinds documents a verb this repository's 2026.2 extraction does not contain:
**`Orion.Cloud.Aws.Accounts.BulkAddAwsAccounts`**, described in full on the
[BulkAddAwsAccounts](https://solarwinds.github.io/OrionSDK/docs/sam-bulk-add-aws-accounts/)
page. It appears neither in the rendered schema for 2026.2 nor in the Swagger contract for
2026.2, both of which this repository extracts from, so it is **not verified here**. That
absence is worth knowing rather than glossing over: it means the verb may be newer than the
published schema, or served only when a particular module version is installed. Confirm on
your own server before writing against it:

```sql
SELECT v.Name, v.CanInvoke, v.Summary
FROM Metadata.Verb v
WHERE v.Entity.FullName = 'Orion.Cloud.Aws.Accounts'
ORDER BY v.Name
```

```sql
SELECT va.Position, va.Name, va.Type, va.IsOptional
FROM Metadata.VerbArgument va
WHERE va.EntityName = 'Orion.Cloud.Aws.Accounts'
  AND va.VerbName = 'BulkAddAwsAccounts'
ORDER BY va.Position
```

If it is there, SolarWinds' page is the specification and is unusually complete. The shape
of the call is one JSON string:

```powershell
$json = '[{"Name":"prod-account-1","AccessKeyId":"AKIAIOSFODNN7EXAMPLE","SecretAccessKey":"wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"}]'

$result = Invoke-SwisVerb $swis Orion.Cloud.Aws.Accounts BulkAddAwsAccounts @(, $json)
```

The `@(, $json)` is not a typo. It forces PowerShell to pass a one-element array rather than
unrolling the string, which matters because SWIS verb arguments are positional and a bare
string would be splatted. The points from SolarWinds' page worth carrying over here:

- **Partial success.** Failed accounts are reported in the response while the rest are
  created. The result splits into `Succeeded` and `Failed` lists.
- **Hard limits, rejected before anything is created:** at most 100 accounts per call and at
  most 1 MB of JSON. `Name` is required, at most 255 characters, and duplicates within one
  request lose to the first occurrence.
- **The fields map onto the entities on this page.** `AutoMonitoring`,
  `PollingIntervalInSeconds` and `MonitorResourceType` are `Orion.Cloud.Accounts` columns.
  `SelectedRegions` takes `SystemName` strings and lands in
  `Orion.Cloud.SelectedCloudRegions`. `JobSettings` maps to `Orion.Cloud.CloudJobSettings`,
  including its `Tags` array, which becomes `Orion.Cloud.TagFilter` rows and is only applied
  when `MonitorResourceType` is 2. `ExistingCredentialsId` is `Orion.Cloud.Accounts.CredentialId`.
- **`RoleArn` supports AssumeRole chaining**, semicolon between hops and a pipe before an
  external id.

To reuse a stored credential rather than sending keys, SolarWinds' page gives the lookup
directly, and both halves are ordinary SWQL:

```sql
SELECT ID, Name
FROM Orion.Credential
WHERE CredentialOwner = 'CloudMonitoring'
  AND CredentialType LIKE '%AwsCredentials%'
ORDER BY Name
```

## Worked queries

Every query below has been validated against the 2026.2 schema with
`python3 tools/validate_swql.py`. For more, see
[`../../scripts/swql/16-cloud-and-appinsight.swql`](../../scripts/swql/16-cloud-and-appinsight.swql).

### 1. Accounts, their credentials, and what polling costs

The account overview, with both API request counters selected. The counters are the reason
to look at `PollingIntervalInSeconds` next to them.

```sql
SELECT TOP 100
    a.Id,
    a.Name,
    a.Provider.Name AS ProviderName,
    a.Credential.Name AS CredentialName,
    a.AutoMonitoring,
    a.DisableMonitorApiRequests,
    a.PollingIntervalInSeconds,
    a.MonitorResourceType,
    a.MonitorApiRequestsMadePerMonth,
    a.Counters.CloudWatchRequestsMadeThisMonth AS CloudWatchRequests
FROM Orion.Cloud.Accounts a
ORDER BY a.Name
```

`CloudWatchRequests` is populated for AWS accounts only, because
`Orion.Cloud.AccountCounters` is the CloudWatch counter. A null there on an Azure account is
correct, not missing data.

### 2. Instance inventory, with the node each one maps to

The cross-provider view, joined to both the account and the paired node. A null
`NodeCaption` is an instance nobody is monitoring from the inside.

```sql
SELECT TOP 200
    i.Name,
    i.InstanceId,
    i.Provider,
    i.Region,
    i.Type,
    i.State,
    i.Platform,
    i.CloudAccount.Name AS AccountName,
    i.Node.Caption AS NodeCaption,
    i.Node.NodeID AS NodeID,
    st.StatusName
FROM Orion.Cloud.Instances i
JOIN Orion.StatusInfo st ON st.StatusId = i.Status
WHERE i.UnManaged = FALSE
ORDER BY i.Provider, i.Region, i.Name
```

`UnManaged` is inherited from `System.ManagedEntity` and is queryable here even though
`Orion.Cloud.Instances` does not declare it. Filtering it out is the difference between "in
trouble" and "in a maintenance window".

### 3. Cloud instances that are not paired with a node

The gap list. These have provider metrics and nothing from inside the guest, which is why
`MemoryStatus` will be empty for every one of them. `VirtualMachineID` is selected because
it is the id every verb wants.

```sql
SELECT TOP 200
    i.Name,
    i.InstanceId,
    i.VirtualMachineID,
    i.Provider,
    i.Region,
    i.State,
    i.LastSuccessfulPoll
FROM Orion.Cloud.Instances i
WHERE i.NodeID IS NULL
ORDER BY i.Provider, i.Name
```

The step before that, for AWS, is instances the account can see but is not monitoring at
all:

```sql
SELECT TOP 200
    u.InstanceId,
    u.Name,
    u.Type,
    u.State,
    u.AvailabilityZone,
    u.Platform,
    u.VpcId,
    u.InstanceLaunchTime,
    u.StatusDescription
FROM Orion.Cloud.Aws.UnmonitoredInstances u
WHERE u.CloudAccountId = @cloudAccountId
ORDER BY u.InstanceLaunchTime DESC
```

### 4. Slow EBS volumes, with the instance they belong to

Latency is the number that turns "the database is slow" into a storage conversation, and
`QueuedOperations` alongside it distinguishes a slow disk from an overloaded one.

```sql
SELECT TOP 100
    v.Name,
    v.DiskIdentifier,
    v.Type,
    v.Size,
    v.State,
    v.CloudInstance.Name AS InstanceName,
    v.ReadLatencyInMilliseconds,
    v.WriteLatencyInMilliseconds,
    v.ConsumedIOPS,
    v.QueuedOperations
FROM Orion.Cloud.Aws.Volumes v
ORDER BY v.WriteLatencyInMilliseconds DESC
```

### 5. What each account is actually scoped to poll

Job settings joined to their tag filters. A row with a `TagKey` means the account is
filtering by tag; several rows for one account mean several filters.

```sql
SELECT TOP 200
    js.CloudAccounts.Name AS AccountName,
    js.NetworkScanEnabled,
    js.NetworkScanInterval,
    js.DnsScanEnabled,
    js.DnsScanInterval,
    js.VirtualNetworkGatewaysPollingEnabled,
    js.SelectedAllRegions,
    js.RunCostManagementAtTime,
    js.TagFilter.Key AS TagKey,
    js.TagFilter.Value AS TagValue
FROM Orion.Cloud.CloudJobSettings js
ORDER BY js.CloudAccounts.Name
```

And the region half of the same question, walking from the selection back up to the account
and down to the region catalogue:

```sql
SELECT TOP 200
    sr.CloudJobSettings.CloudAccounts.Name AS AccountName,
    sr.AllRegions.SystemName AS RegionSystemName,
    sr.AllRegions.DisplayName AS RegionDisplayName,
    sr.AllRegions.Enabled AS RegionEnabled,
    sr.AllRegions.CloudProviders.Name AS ProviderName
FROM Orion.Cloud.SelectedCloudRegions sr
ORDER BY sr.AllRegions.SystemName
```

`sr.CloudJobSettings.CloudAccounts.Name` walks three references in one expression, from the
selected region to the job settings to the account.

### 6. Resources carrying a given tag

The tags the provider reports, not the tags you filter on. `ResourceType` tells you what
kind of thing each `ResourceId` refers to.

```sql
SELECT TOP 200
    t.ResourceType,
    t.ResourceId,
    t.Key,
    t.Value,
    t.ProviderId
FROM Orion.Cloud.ResourseTags t
WHERE t.Key = @tagKey
ORDER BY t.Value, t.ResourceId
```

Joining tags to instances has to be done on the string ids, because
`Orion.Cloud.ResourseTags` declares no navigation properties. Check that
`ResourceId` and `InstanceId` really are the same form on your provider before trusting
this one, as noted [above](#tag-filters-and-resource-tags-are-different-entities):

```sql
SELECT TOP 100
    i.Name,
    i.InstanceId,
    i.Provider,
    i.Region,
    t.Key AS TagKey,
    t.Value AS TagValue
FROM Orion.Cloud.Instances i
JOIN Orion.Cloud.ResourseTags t ON t.ResourceId = i.InstanceId
WHERE t.Key = @tagKey
ORDER BY i.Name
```

### 7. IO trend for cloud instances over a window

`Orion.Cloud.InstanceStatistics` inherits from `System.StatisticsEntity`, so it has
`ObservationTimestamp` and it grows without bound. It always gets a time predicate.

```sql
SELECT TOP 100
    s.Instance.Name AS InstanceName,
    s.Instance.Provider AS Provider,
    AVG(s.AvgIOPSTotal) AS MeanIOPS,
    MAX(s.MaxIOPSTotal) AS PeakIOPS,
    AVG(s.AvgDiskReadInBytesPerSecond) AS MeanDiskRead,
    AVG(s.AvgDiskWriteInBytesPerSecond) AS MeanDiskWrite
FROM Orion.Cloud.InstanceStatistics s
WHERE s.ObservationTimestamp >= @startUtc
  AND s.ObservationTimestamp < @endUtc
GROUP BY s.Instance.Name, s.Instance.Provider
ORDER BY AVG(s.AvgIOPSTotal) DESC
```

Averaging an average weights every interval equally regardless of how busy it was. That is
usually right for a trend and usually wrong for a service level number.

### 8. Daily cost, worst first

```sql
SELECT TOP 100
    c.ProviderName,
    c.AccountName,
    c.Category,
    c.Region,
    c.ResourceId,
    c.TotalDailyCost,
    c.ObservationTimestamp
FROM Orion.Cloud.CostEntities c
WHERE c.ObservationTimestamp >= @startUtc
  AND c.ObservationTimestamp < @endUtc
ORDER BY c.TotalDailyCost DESC
```

Cost is polled on a schedule set by `Orion.Cloud.CloudJobSettings.RunCostManagementAtTime`,
once a day, so a window narrower than a day can legitimately return nothing.

### 9. Which metric is red on an instance

`Orion.Cloud.InstanceStatus` gives one status integer per metric instead of one for the
whole instance, which is what turns "warning" into "warning because of disk".

```sql
SELECT TOP 100
    ms.Instance.Name AS InstanceName,
    ms.CpuLoadStatus,
    ms.MemoryStatus,
    ms.IOPSTotalStatus,
    ms.DiskReadStatus,
    ms.DiskWriteStatus,
    ms.NetworkUsageRateStatus
FROM Orion.Cloud.InstanceStatus ms
WHERE ms.CpuLoadStatus <> 1
   OR ms.MemoryStatus <> 1
ORDER BY ms.Instance.Name
```

For the same information already rendered as names, read `Orion.Cloud.InstanceStatusMacro`,
which carries `CpuLoadStatusName`, `MemoryStatusName` and the rest, plus a single
`MetricsWithStatusFormatted` string.

### 10. Cloud events in a window

```sql
SELECT TOP 200
    e.EventTime,
    e.ProviderName,
    e.AccountName,
    e.NetObjectType,
    e.NetObjectID,
    e.EventType,
    e.Acknowledged,
    e.Message
FROM Orion.Cloud.EventsView e
WHERE e.EventTime >= @startUtc
  AND e.EventTime < @endUtc
ORDER BY e.EventTime DESC
```

### 11. Nodes that are cloud instances, from the node side

The reverse of query 2, and the shape a node-centric report needs. The three `Cloud*ID`
columns on the node are the provider's own strings.

```sql
SELECT TOP 100
    n.Caption,
    n.CloudInstanceID,
    n.CloudAccountID,
    n.CloudZoneID,
    n.CloudInstance.Provider AS Provider,
    n.CloudInstance.Region AS Region,
    n.CloudInstance.Type AS InstanceType,
    n.CloudInstance.State AS InstanceState
FROM Orion.Nodes n
WHERE n.CloudInstance.InstanceId IS NOT NULL
ORDER BY n.Caption
```

### 12. The enabled region catalogue

Useful before adding an account, because a region that is disabled installation-wide cannot
be selected for one. SolarWinds' bulk-add page lists exactly this failure:
"AWS region(s) not available for monitoring".

```sql
SELECT r.Id, r.SystemName, r.DisplayName, r.Enabled, r.CloudProviders.Name AS ProviderName
FROM Orion.Cloud.Regions r
WHERE r.Enabled = TRUE
ORDER BY r.CloudProviders.Name, r.SystemName
```

## Gotchas

**`ResourseTags` is spelled wrong, and that spelling is the entity name.**
`Orion.Cloud.ResourseTags`, `Orion.Cloud.Aws.ResourseTags`,
`Orion.Cloud.Azure.ResourseTags`. There is no `Orion.Cloud.ResourceTags`. Look it up rather
than typing what you expect.

**`Orion.Cloud.TagFilter` and `Orion.Cloud.ResourseTags` are unrelated entities.** One is
the filter you configured, the other is what the provider reports. Neither navigates to the
other.

**Provider subtypes look empty and are not.** `Orion.Cloud.Aws.Regions` declares zero
properties, `Orion.Cloud.Azure.Accounts` declares one, `Orion.Cloud.Aws.ResourseTags`
declares zero. They inherit everything. Use
`python3 tools/schema_query.py props <Entity>`, not `show`, whenever a property list comes
back short.

**`InstanceId` is the provider's string, `VirtualMachineID` is the platform's integer.**
Every cloud verb takes `virtualMachineId`. Passing the `i-0abc...` form will fail, and
passing an id from the wrong entity will act on the wrong machine.

**`Orion.Cloud.Instances.Unmanage` has a different signature from every other `Unmanage`.**
One argument, no time window, no NetObject string. Check the signature.

**Some verbs change the real machine.** `StopInstance`, `RebootInstance`,
`ForceStopInstance` and `TerminateInstance` act at the provider.
`DeleteInstanceWithNode` and `TerminateInstanceAndRemoveNode` additionally delete the
platform's node. Nothing in the verb name warns you.

**`State` is the provider's vocabulary and is not normalised.** Compare it against values
you have actually seen in your own data, not against a value you assume. `Status` is the
platform integer and joins to `Orion.StatusInfo`.

**Polling interval is a billing decision.** `MonitorApiRequestsMadePerMonth` and
`CloudWatchRequestsMadeThisMonth` exist because provider API calls cost money. Halving
`PollingIntervalInSeconds` doubles them.

**`MemoryStatus` requires a paired node.** It is "calculated from related Node
`PercentMemoryUsed`, if this instance is mapped to a node". An unpaired instance will never
have it.

**Not everything cloud is under `Orion.Cloud.`.** `Orion.CloudMonitoring.` holds the VPN
gateway and connection family, and `Orion.Virtualization.Instance` is the base type that
cloud instances share with [VMAN](vman.md).

**44 of the 148 entities are statistics.** Every one inherits `System.StatisticsEntity` and
grows per resource, per interval. Time-bound all of them.

**Account limitations filter silently.** Two accounts running the same cloud query can get
different rows with no indication that anything was removed.

## What is not verified here

| Claim | Status | How to check on your server |
|---|---|---|
| What the `Local.Orion.Cloud.*` prefix means | The paths exist in the Swagger contract with schemas identical to the unprefixed forms, and the entities have no rendered schema page. The federation reading offered above is an inference | `SELECT FullName, CanCreate FROM Metadata.Entity WHERE FullName LIKE '%Orion.Cloud.Regions'` |
| A verb the 2026.2 extraction does not have, `Orion.Cloud.Aws.Accounts.BulkAddAwsAccounts` | Documented in full by SolarWinds but absent from both the 2026.2 rendered schema and the 2026.2 Swagger contract that this repository extracts | `SELECT v.Name, v.CanInvoke FROM Metadata.Verb v WHERE v.Entity.FullName = 'Orion.Cloud.Aws.Accounts'` |
| `MonitorResourceType` values 0, 1 and 2 | The mapping comes from SolarWinds' bulk-add page; the schema gives the column no description | `SELECT MonitorResourceType, COUNT(Id) AS Accounts FROM Orion.Cloud.Accounts GROUP BY MonitorResourceType`, and compare against how each account is configured in the console |
| That `Orion.Cloud.ResourseTags.ResourceId` matches `Orion.Cloud.Instances.InstanceId` | Both are `System.String` and the join is the obvious one, but no relationship declares it and the format may differ per provider and per resource type | `SELECT TOP 25 ResourceType, ResourceId FROM Orion.Cloud.ResourseTags ORDER BY ResourceType`, then compare against `SELECT TOP 25 InstanceId FROM Orion.Cloud.Instances` |
| Whether the region-discovery verbs accept a credential id alone | The credential objects declare `ID` and `CredentialsId` alongside the secret fields, but the contract does not say the secrets are optional | Invoke `GetAwsRegions` with only `ID` populated against a test installation |
| The `EventType` integers on `Orion.Cloud.EventsView` | Not enumerated | `SELECT EventType, COUNT(EventID) AS Events FROM Orion.Cloud.EventsView WHERE EventTime >= @startUtc GROUP BY EventType` |
| The `PollState_Value` integers on `Orion.Cloud.Vpcs` | Undocumented | `SELECT PollState_Value, COUNT(Id) AS Vpcs FROM Orion.Cloud.Vpcs GROUP BY PollState_Value` |
| Whether `Orion.Cloud.Aws.Accounts`, `Orion.Cloud.Azure.Accounts` and `Orion.Cloud.Gcp.Accounts` really accept `create` | Their `/Create` paths exist in the contract while the rendered schema publishes no access control table for them | `SELECT FullName, CanCreate, CanUpdate, CanDelete FROM Metadata.Entity WHERE FullName LIKE 'Orion.Cloud.%Accounts'` |

## Related pages

- [README.md](README.md) for the module index and how to check what is installed.
- [vman.md](vman.md) for `Orion.Virtualization.Instance`, the base type cloud instances
  inherit from, and for on-premises virtualisation.
- [dpa.md](dpa.md) for `CloudResourceId` and `CloudResourceType`, which tie a cloud database
  resource to a monitored database instance.
- [sam.md](sam.md) for AppInsight, the other way to watch what runs on a cloud machine.
- [../automation/node-management.md](../automation/node-management.md) for adding the node
  half of a cloud instance and assigning its pollers.
- [../swis/invoke-verbs.md](../swis/invoke-verbs.md) for positional verb arguments.
- [../swis/crud.md](../swis/crud.md) for creating accounts, job settings and tag filters.
- [../schema/using-the-data.md](../schema/using-the-data.md) for the contract and schema
  disagreements this page refers to, including the `Local.` count.
- [../reference/status-codes.md](../reference/status-codes.md) for the `Status` integers.
- [`../../scripts/swql/16-cloud-and-appinsight.swql`](../../scripts/swql/16-cloud-and-appinsight.swql)
  for more verified cloud queries.
- SolarWinds'
  [BulkAddAwsAccounts](https://solarwinds.github.io/OrionSDK/docs/sam-bulk-add-aws-accounts/)
  and
  [credential management](https://solarwinds.github.io/OrionSDK/docs/credential-management/)
  pages.

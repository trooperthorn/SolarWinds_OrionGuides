# Node management

A node is the root object of the Orion data model. Interfaces, volumes, applications,
hardware sensors, configs and flow sources all hang off one, and almost every other
automation in this section starts by finding one. This page covers the whole lifecycle:
create, find, update, repoll, move between polling engines, and delete.

Everything here uses `Orion.Nodes`. Confirm the shape on your own version with:

```bash
python3 tools/schema_query.py show Orion.Nodes
```

In 2026.2 that entity declares 102 properties of its own, inherits `UnManaged`,
`UnManageFrom`, `UnManageUntil` from `System.ManagedEntity` and `Uri` and `InstanceType`
from `System.Entity`, supports full CRUD plus invoke, and declares 17 verbs. Its key
property is `NodeID` and its NetObject prefix is `N`, so node 42 is `N:42` wherever a verb
asks for a `netObjectId`.

Access control on the entity, from the schema:

| Operations | Required right |
|:---|:---|
| `read` | `everyone` |
| `read`, `invoke` | `allowRealTimePolling` |
| `create`, `read`, `update`, `delete`, `invoke` | `manageNodes` |

## Adding a node

Creating a node is a CRUD create against `Orion.Nodes`, followed by creating one
`Orion.Pollers` row per thing you want polled. **Both halves are required.** A node created
without pollers appears in the console and collects nothing, which is the single most common
surprise in Orion automation.

### The properties to set on create

The schema does not publish a "required on create" flag, and neither does the Swagger
contract, so the honest statement is: the set below is what SolarWinds' own
[`CRUD.AddNode.ps1`](https://github.com/solarwinds/OrionSDK/blob/master/Samples/PowerShell/CRUD.AddNode.ps1)
sample sets, and every name in it is a real `Orion.Nodes` property in 2026.2.

| Property | Type | Why it is there |
|:---|:---|:---|
| `IPAddress` | `System.String` | The address the polling engine will talk to. |
| `EngineID` | `System.Int32` | Which polling engine owns the node. `1` is the primary. |
| `ObjectSubType` | `System.String` | How the node is polled. The samples use `ICMP`, `SNMP` and `WMI`. |
| `SNMPVersion` | `System.Int16` | `2` for SNMPv2c, `3` for SNMPv3. Only meaningful when `ObjectSubType` is `SNMP`. |
| `Community` | `System.String` | SNMPv2c read community. `RWCommunity` is the read/write one. |
| `DNS` | `System.String` | Set explicitly, even to an empty string, rather than leaving it out. |
| `SysName` | `System.String` | Same. Polling fills it in later. |
| `Caption` | `System.String` | Display name. The sample notes that it defaults to an empty string. |
| `DynamicIP` | `System.Boolean` | Whether the address is expected to change. |
| `PollInterval` | `System.Int32` | Status poll interval in seconds. The sample notes 120 as the default. |
| `RediscoveryInterval` | `System.Int32` | Minutes between rediscoveries. The sample notes 30. |
| `StatCollection` | `System.Int32` | Statistics collection interval in minutes. The sample notes 10. |

The sample also comments that `EntityType` defaults to `Orion.Nodes`, so you do not set it.

Verify any of these before using them:

```bash
python3 tools/schema_query.py props Orion.Nodes --grep interval
```

### The pollers

`Orion.Pollers` is the assignment table. It has six properties and you set four of them:

| Property | Value |
|:---|:---|
| `PollerType` | The poller's name, for example `N.Status.ICMP.Native` |
| `NetObject` | `"N:" + NodeID` |
| `NetObjectType` | `"N"` for a node |
| `NetObjectID` | The `NodeID` |

`PollerID` is assigned by the create. The sixth property, `Enabled`, is a
`System.Boolean` that neither official sample sets; read it back after creating a poller to
see what your server defaulted it to, and set it explicitly if you care.

The poller type names are not entities and are not in the schema data. They come from
SolarWinds' [Poller Types](https://solarwinds.github.io/OrionSDK/docs/poller-types/)
reference, which lists every one with a description. The six from the official SNMP and WMI
samples are:

| Purpose | SNMP sample | WMI sample |
|:---|:---|:---|
| Status | `N.Status.ICMP.Native` | `N.Status.ICMP.Native` |
| Response time | `N.ResponseTime.ICMP.Native` | `N.ResponseTime.ICMP.Native` |
| Details | `N.Details.SNMP.Generic` | `N.Details.WMI.Vista` |
| Uptime | `N.Uptime.SNMP.Generic` | `N.Uptime.WMI.XP` |
| CPU | `N.Cpu.SNMP.CiscoGen3` | `N.Cpu.WMI.Windows` |
| Memory | `N.Memory.SNMP.CiscoGen3` | `N.Memory.WMI.Windows` |

The CPU and memory pollers in the SNMP column are Cisco-specific; pick the ones that match
the device. See [pollers.md](pollers.md) for the fuller story of why this step exists.

### PowerShell: add an SNMPv2c node

Adapted from `CRUD.AddNode.ps1`.

```powershell
Import-Module SwisPowerShell
$swis = Connect-Swis -Hostname 'orion.example.com' -Trusted

# Refuse to create a duplicate. Orion will happily hold two nodes with one address.
$existing = Get-SwisData $swis `
    'SELECT NodeID, Caption FROM Orion.Nodes WHERE IPAddress = @ip' `
    @{ ip = '10.0.0.1' }
if ($existing) {
    throw "NodeID $($existing.NodeID) already monitors 10.0.0.1"
}

$newNodeProps = @{
    IPAddress           = '10.0.0.1'
    EngineID            = 1
    ObjectSubType       = 'SNMP'
    SNMPVersion         = 2
    Community           = 'public'
    DNS                 = ''
    SysName             = ''
    Caption             = 'core-sw-01'
    PollInterval        = 120
    RediscoveryInterval = 30
    StatCollection      = 10
}

$nodeUri   = New-SwisObject $swis -EntityType 'Orion.Nodes' -Properties $newNodeProps
$nodeProps = Get-SwisObject $swis -Uri $nodeUri
$nodeId    = $nodeProps['NodeID']
Write-Information "Created NodeID $nodeId at $nodeUri" -InformationAction Continue

# Now the pollers. Without these the node exists and collects nothing.
$poller = @{
    NetObject     = "N:$nodeId"
    NetObjectType = 'N'
    NetObjectID   = $nodeId
}

foreach ($type in @(
    'N.Status.ICMP.Native',
    'N.ResponseTime.ICMP.Native',
    'N.Details.SNMP.Generic',
    'N.Uptime.SNMP.Generic'
)) {
    $poller['PollerType'] = $type
    New-SwisObject $swis -EntityType 'Orion.Pollers' -Properties $poller | Out-Null
}

# Poll immediately rather than waiting for the first scheduled cycle.
Invoke-SwisVerb $swis 'Orion.Nodes' 'PollNow' @("N:$nodeId") | Out-Null
```

Confirm it worked, which for a create means "the node is there and it has pollers":

```sql
SELECT
    n.NodeID,
    n.Caption,
    n.IPAddress,
    n.ObjectSubType,
    n.SNMPVersion,
    n.EngineID,
    n.Status,
    n.LastSync
FROM Orion.Nodes n
WHERE n.NodeID = @nodeId
```

```sql
SELECT p.PollerID, p.PollerType, p.NetObject, p.Enabled
FROM Orion.Pollers p
WHERE p.NetObjectType = 'N'
  AND p.NetObjectID = @nodeId
ORDER BY p.PollerType
```

### Python: the same flow

```python
from orionsdk import SwisClient

swis = SwisClient(
    "orion.example.com", "svc-automation", password,
    verify="/etc/ssl/certs/orion-swis.pem",
)

ip = "10.0.0.1"

existing = swis.query(
    "SELECT NodeID, Caption FROM Orion.Nodes WHERE IPAddress = @ip", ip=ip
)["results"]
if existing:
    raise SystemExit(f"NodeID {existing[0]['NodeID']} already monitors {ip}")

node_uri = swis.create(
    "Orion.Nodes",
    IPAddress=ip,
    EngineID=1,
    ObjectSubType="SNMP",
    SNMPVersion=2,
    Community="public",
    DNS="",
    SysName="",
    Caption="core-sw-01",
    PollInterval=120,
    RediscoveryInterval=30,
    StatCollection=10,
)
node_id = swis.read(node_uri)["NodeID"]

for poller_type in (
    "N.Status.ICMP.Native",
    "N.ResponseTime.ICMP.Native",
    "N.Details.SNMP.Generic",
    "N.Uptime.SNMP.Generic",
):
    swis.create(
        "Orion.Pollers",
        PollerType=poller_type,
        NetObject=f"N:{node_id}",
        NetObjectType="N",
        NetObjectID=node_id,
    )

swis.invoke("Orion.Nodes", "PollNow", f"N:{node_id}")

print(swis.query(
    "SELECT NodeID, Caption, IPAddress, EngineID, Status FROM Orion.Nodes WHERE NodeID = @id",
    id=node_id,
)["results"])
```

### A WMI node needs a credential association

An SNMPv2c node carries its community string on the node row. A WMI node does not carry a
credential; it points at one in the credential store through `Orion.NodeSettings`. That is
what SolarWinds'
[`CRUD.AddWMINode.ps1`](https://github.com/solarwinds/OrionSDK/blob/master/Samples/PowerShell/CRUD.AddWMINode.ps1)
sample does, and it is the part people miss.

`Orion.NodeSettings` has four properties: `NodeSettingID`, `NodeID`, `SettingName` and
`SettingValue`. The sample uses `SettingName = "WMICredential"` with the credential's `ID`
as the value.

```powershell
$credentialName = 'Domain WMI account'   # as shown in Manage Windows Credentials

$credentialId = Get-SwisData $swis `
    'SELECT ID FROM Orion.Credential WHERE Name = @name' `
    @{ name = $credentialName }
if (-not $credentialId) { throw "No credential named '$credentialName'" }

$nodeUri = New-SwisObject $swis -EntityType 'Orion.Nodes' -Properties @{
    IPAddress     = '10.100.1.1'
    EngineID      = 1
    ObjectSubType = 'WMI'
    DNS           = ''
    SysName       = ''
}
$nodeId = (Get-SwisObject $swis -Uri $nodeUri)['NodeID']

New-SwisObject $swis -EntityType 'Orion.NodeSettings' -Properties @{
    NodeID       = $nodeId
    SettingName  = 'WMICredential'
    SettingValue = "$credentialId"
} | Out-Null

$poller = @{ NetObject = "N:$nodeId"; NetObjectType = 'N'; NetObjectID = $nodeId }
foreach ($type in @(
    'N.Status.ICMP.Native',
    'N.ResponseTime.ICMP.Native',
    'N.Details.WMI.Vista',
    'N.Uptime.WMI.XP',
    'N.Cpu.WMI.Windows',
    'N.Memory.WMI.Windows'
)) {
    $poller['PollerType'] = $type
    New-SwisObject $swis -EntityType 'Orion.Pollers' -Properties $poller | Out-Null
}
```

Read back what settings a node carries:

```sql
SELECT ns.NodeSettingID, ns.NodeID, ns.SettingName, ns.SettingValue
FROM Orion.NodeSettings ns
WHERE ns.NodeID = @nodeId
ORDER BY ns.SettingName
```

And the credentials available to point at:

```sql
SELECT c.ID, c.Name, c.CredentialType, c.CredentialOwner, c.Description
FROM Orion.Credential c
ORDER BY c.Name
```

`Orion.Credential` exposes no secret material through the query interface. See
[credentials.md](credentials.md).

### When to use discovery instead

Creating a node by hand means you decide the pollers. Running a discovery means the platform
probes the device and tells you what it found, which is what you want for a device whose
capabilities you do not already know. `Orion.Nodes` carries a "list resources" verb set for
exactly this, for a node that already exists:

| Verb | Signature |
|:---|:---|
| `ScheduleListResources` | `(nodeId)` returns a job id string |
| `ScheduleListResourcesForAddress` | `(ipAddress, port, credentialsType, credentialProperties, engineId, preferredSnmpVersion)` |
| `GetScheduledListResourcesStatus` | `(jobId, nodeId)` |
| `GetListResourcesResult` | `(jobId, nodeId)` returns an array |
| `ImportListResourcesResult` | `(jobId, nodeId)` returns boolean |
| `ImportSelectedListResourcesResult` | `(jobId, nodeId, resources)` returns an array |

All six require `manageNodes`. Full treatment, including network sonar discovery for nodes
that do not exist yet, is in [discovery.md](discovery.md).

## Finding nodes

The inventory query, which is the starting point for most of the rest of this page:

```sql
SELECT
    n.NodeID,
    n.Caption,
    n.IPAddress,
    n.DNS,
    n.SysName,
    n.Vendor,
    n.MachineType,
    n.ObjectSubType,
    n.EngineID,
    n.Status,
    n.Uri
FROM Orion.Nodes n
ORDER BY n.Caption
```

Status is an integer. Join `Orion.StatusInfo` when a human is going to read the output:

```sql
SELECT
    n.NodeID,
    n.Caption,
    n.Status,
    si.StatusName,
    n.LastSync,
    n.MinutesSinceLastSync,
    n.IsPollingError
FROM Orion.Nodes n
JOIN Orion.StatusInfo si ON n.Status = si.StatusId
WHERE n.Status <> 1
ORDER BY si.Ranking, n.Caption
```

The status values are in [../reference/status-codes.md](../reference/status-codes.md). The
ones that matter here are `1` Up, `2` Down, `9` Unmanaged and `11` External.

By address, by name pattern, and by id set:

```sql
SELECT n.NodeID, n.Caption, n.Uri
FROM Orion.Nodes n
WHERE n.IPAddress = @ip
```

```sql
SELECT n.NodeID, n.Caption, n.Uri
FROM Orion.Nodes n
WHERE n.Caption LIKE @pattern
ORDER BY n.Caption
```

```sql
SELECT n.NodeID, n.Caption, n.Uri
FROM Orion.Nodes n
WHERE n.NodeID IN @ids
```

By group membership, which is usually how a change window is defined:

```sql
SELECT cm.MemberPrimaryID AS NodeID, cm.Name, cm.MemberUri
FROM Orion.ContainerMembers cm
WHERE cm.Container.Name = @groupName
  AND cm.MemberEntityType = 'Orion.Nodes'
ORDER BY cm.Name
```

Nodes with no pollers at all, which is the check to run after any bulk import:

```sql
SELECT n.NodeID, n.Caption, n.IPAddress, n.ObjectSubType
FROM Orion.Nodes n
WHERE NOT EXISTS (
    SELECT p.PollerID
    FROM Orion.Pollers p
    WHERE p.NetObjectType = 'N'
      AND p.NetObjectID = n.NodeID
)
ORDER BY n.Caption
```

## Updating node properties

An update is a CRUD `POST` to the node's URI carrying only the properties you are changing.
Everything you do not name is left alone.

### Renaming

Adapted from SolarWinds'
[`Update.Captions.ps1`](https://github.com/solarwinds/OrionSDK/blob/master/Samples/PowerShell/Update.Captions.ps1),
which strips a domain suffix from every caption. Note that the sample ships with the write
line commented out, and that it skips nodes already in the desired state so a rerun is a
no-op.

```powershell
$nodes = Get-SwisData $swis @'
SELECT n.NodeID, n.Caption, n.Uri
FROM Orion.Nodes n
WHERE n.Caption LIKE '%.example.com'
ORDER BY n.Caption
'@

foreach ($node in $nodes) {
    $newName = $node.Caption.Replace('.example.com', '')

    # Case-sensitive comparison: skip if it is already right.
    if ($node.Caption -ceq $newName) { continue }

    Write-Output "Renaming [$($node.Caption)] to [$newName]"

    # Uncomment once the preview above looks correct.
    # Set-SwisObject $swis -Uri $node.Uri -Properties @{ Caption = $newName }
}
```

### Descriptive properties across many nodes

`Location` and `Contact` are ordinary `System.String` properties, so the same value across a
set is a `BulkUpdate`. Scope it with a query you have run first:

```sql
SELECT n.NodeID, n.Caption, n.Location, n.Uri
FROM Orion.Nodes n
WHERE n.Location = @oldLocation
ORDER BY n.Caption
```

```python
targets = swis.query(
    "SELECT NodeID, Uri FROM Orion.Nodes WHERE Location = @old",
    old="DC1",
)["results"]

uris = [r["Uri"] for r in targets]
print(f"about to relabel {len(uris)} nodes")     # look at this number

for i in range(0, len(uris), 200):
    swis.bulkupdate(uris[i:i + 200], Location="DC1 (decommissioned)")

check = swis.query(
    "SELECT NodeID, Caption, Location FROM Orion.Nodes WHERE NodeID IN @ids",
    ids=[r["NodeID"] for r in targets],
)["results"]
```

`BulkUpdate` returns an empty body with no per-item result, so the read-back is not optional.
See [../swis/bulk-operations.md](../swis/bulk-operations.md).

### Polling intervals

```powershell
Set-SwisObject $swis -Uri $nodeUri -Properties @{
    PollInterval        = 300   # seconds between status polls
    RediscoveryInterval = 60    # minutes between rediscoveries
    StatCollection      = 15    # minutes between statistics collections
}
```

Raising intervals is the cheapest way to reduce configured polling load on an engine that is
over its licensed job weight. See [Rebalancing polling
engines](#reassigning-a-node-to-a-different-polling-engine) below.

## Changing polling method and SNMP version

`ObjectSubType` decides how the node is polled. Changing it is a property update, but it is
not sufficient on its own: the pollers assigned to the node are method-specific, so a node
moved from `SNMP` to `WMI` keeps SNMP pollers that will now fail. Plan on replacing the
`Orion.Pollers` rows in the same operation.

```sql
SELECT n.NodeID, n.Caption, n.ObjectSubType, n.SNMPVersion, n.Community
FROM Orion.Nodes n
WHERE n.ObjectSubType = 'SNMP'
  AND n.SNMPVersion = 2
ORDER BY n.Caption
```

### SNMPv2c

Both `SNMPVersion` and `Community` are `Orion.Nodes` properties, so this is one update:

```powershell
$nodeUri = Get-SwisData $swis `
    'SELECT Uri FROM Orion.Nodes WHERE IPAddress = @ip' @{ ip = '192.0.2.10' }

Set-SwisObject $swis -Uri $nodeUri -Properties @{
    SNMPVersion = 2
    Community   = 'newcommunity'
}
```

### SNMPv3

SolarWinds'
[`ChangeSNMPVersion.ps1`](https://github.com/solarwinds/OrionSDK/blob/master/Samples/PowerShell/ChangeSNMPVersion.ps1)
sample sets `SNMPV3Context`, `SNMPV3Username`, `SNMPV3PrivMethod`, `SNMPV3PrivKey`,
`SNMPV3AuthMethod` and `SNMPV3AuthKey` directly on `Orion.Nodes`. **Those property names are
not present on `Orion.Nodes` in the 2026.2 schema.** The only SNMP property the entity
declares in this release is `SNMPVersion`.

In 2026.2 the credential material lives on a separate hosted entity,
`Orion.SNMPv3Credentials`, reached from a node through the `SNMPv3Credentials` navigation
property. It declares 17 properties and supports `read` and `update` (no create, no delete),
gated on `manageNodes`:

| Read community | Read/write community | Type |
|:---|:---|:---|
| `Username` | `RWUsername` | `System.String` |
| `Context` | `RWContext` | `System.String` |
| `AuthenticationMethod` | `RWAuthenticationMethod` | `System.String` |
| `AuthenticationKey` | `RWAuthenticationKey` | `System.String` |
| `AuthenticationKeyIsPassword` | `RWAuthenticationKeyIsPassword` | `System.Boolean` |
| `PrivacyMethod` | `RWPrivacyMethod` | `System.String` |
| `PrivacyKey` | `RWPrivacyKey` | `System.String` |
| `PrivacyKeyIsPassword` | `RWPrivacyKeyIsPassword` | `System.Boolean` |

It also carries `NodeID`. The accepted values for `AuthenticationMethod` and `PrivacyMethod`
are not published in the schema; the sample script names `None`, `MD5` and `SHA1` for
authentication and `None`, `DES56`, `AES128`, `AES192` and `AES256` for privacy, which is
worth treating as indicative rather than authoritative for your release. Confirm what your
server accepts from the web console's credential editor before scripting it.

Read the current configuration:

```sql
SELECT
    n.NodeID,
    n.Caption,
    n.SNMPVersion,
    n.SNMPv3Credentials.Username,
    n.SNMPv3Credentials.Context,
    n.SNMPv3Credentials.AuthenticationMethod,
    n.SNMPv3Credentials.PrivacyMethod
FROM Orion.Nodes n
WHERE n.SNMPVersion = 3
ORDER BY n.Caption
```

Because `Orion.SNMPv3Credentials` is hosted by `Orion.Nodes`, its URI is the node URI plus
the navigation property, in the same way custom properties work:

```powershell
$nodeUri = Get-SwisData $swis `
    'SELECT Uri FROM Orion.Nodes WHERE IPAddress = @ip' @{ ip = '192.0.2.10' }

Set-SwisObject $swis -Uri $nodeUri -Properties @{ SNMPVersion = 3 }

Set-SwisObject $swis -Uri "$nodeUri/SNMPv3Credentials" -Properties @{
    Username                    = 'orion-poller'
    Context                     = ''
    AuthenticationMethod        = 'SHA1'
    AuthenticationKey           = $authKey
    AuthenticationKeyIsPassword = $true
    PrivacyMethod               = 'AES128'
    PrivacyKey                  = $privKey
    PrivacyKeyIsPassword        = $true
}
```

The URI composition is standard for a hosted entity and matches the `CustomProperties`
pattern documented on the official [URIs](https://solarwinds.github.io/OrionSDK/docs/uris/)
page, but this repository has no live server to confirm it against for
`SNMPv3Credentials` specifically. If your server rejects it, address the entity by its own
key instead, and confirm the exact form the same way you would confirm anything else about
your server:

```sql
SELECT c.NodeID, c.Username, c.Uri
FROM Orion.SNMPv3Credentials c
WHERE c.NodeID = @nodeId
```

Then update that `Uri`. Nothing about the property names changes; only how you address the
row.

## Reassigning a node to a different polling engine

Nodes are statically assigned to polling engines, and everything related to a node,
including its interfaces, applications and configs, runs from that engine. Rebalancing is
the administrator's job, and SolarWinds documents it on the [Polling Engine Load
Balancing](https://solarwinds.github.io/OrionSDK/docs/polling-engine-load-balancing/) page.

### There is no node-level AssignToEngine verb in 2026.2

Searching the verb data for `AssignToEngine` returns `Orion.AgentManagement.Agent.AssignToEngine(agentId, pollerId)`,
which moves an *agent*, and a set of `Core.AssignToEngine` verbs on `Cortex.*` entities
including `Cortex.Orion.Node`, which publish **no parameter list** in the extracted schema and
require the `admin` right. Because their signatures are not published, do not call them from
a script on the strength of this page; if you want to know what your server exposes, ask it:

```sql
SELECT Position, Name, Type, IsOptional
FROM Metadata.VerbArgument
WHERE VerbName = 'Core.AssignToEngine'
ORDER BY EntityName, Position
```

**The documented, supported way to move a node is to set its `EngineID`.** That is what the
official page shows, and it is a plain CRUD update:

```powershell
$swis = Connect-Swis -Hostname 'orion.example.com' -Trusted

$nodeIdToMove   = 1234
$targetEngineId = 4

$nodeUri = Get-SwisData $swis `
    'SELECT Uri FROM Orion.Nodes WHERE NodeID = @nodeId' `
    @{ nodeId = $nodeIdToMove }

Set-SwisObject $swis $nodeUri @{ EngineID = $targetEngineId }
```

```python
uri = swis.query(
    "SELECT Uri FROM Orion.Nodes WHERE NodeID = @id", id=1234
)["results"][0]["Uri"]
swis.update(uri, EngineID=4)
```

### Before you move anything, check reachability

The official page is blunt about this and it is worth repeating: if the new polling engine
cannot reach the node because of address space, firewall rules or SNMP ACLs on the device,
you will silently lose visibility. Reassignment is a database change; it does not test
anything. Move one node, confirm it polls, then move the rest.

### Deciding what to move

Two different questions, two different queries.

Is an engine failing to complete its work on schedule? `PollingCompletion` should sit in the
high 90s:

```sql
SELECT
    e.EngineID,
    e.ServerName,
    e.ServerType,
    e.Nodes,
    e.Interfaces,
    e.Volumes,
    e.Elements,
    e.LicensedElements,
    e.PollingCompletion,
    e.MinutesSinceKeepAlive
FROM Orion.Engines e
ORDER BY e.EngineID
```

Is an engine configured beyond its licensed job weight? Anything over 100 means polling
intervals are being stretched across the board:

```sql
SELECT
    pu.EngineID,
    MAX(pu.CurrentUsage) AS CurrentUsage,
    MAX(pu.IsExceeded) AS IsExceeded
FROM Orion.PollingUsage pu
GROUP BY pu.EngineID
```

Then find the nodes on the overloaded engine, biggest contributors first:

```sql
SELECT
    n.NodeID,
    n.Caption,
    n.IPAddress,
    n.PollInterval,
    n.StatCollection,
    n.EngineID
FROM Orion.Nodes n
WHERE n.EngineID = @engineId
ORDER BY n.PollInterval, n.Caption
```

And confirm the distribution afterwards:

```sql
SELECT e.ServerName, COUNT(n.NodeID) AS NodeCount
FROM Orion.Nodes n
JOIN Orion.Engines e ON n.EngineID = e.EngineID
GROUP BY e.ServerName
ORDER BY e.ServerName
```

Reducing configured load without moving anything is also legitimate: raise `PollInterval` and
`StatCollection` on low-priority nodes, or remove monitoring you do not use.

## Forcing a poll or a rediscovery

Three verbs, all taking a single `netObjectId` and all requiring `manageNodes`:

| Verb | Signature | Description from the schema |
|:---|:---|:---|
| `Orion.Nodes.PollNow` | `(netObjectId)` | "It will poll node instance and update its information" |
| `Orion.Nodes.PollStatusNow` | `(netObjectId)` | "It will poll node status and update it" |
| `Orion.Nodes.RediscoverNow` | `(netObjectId)` | "It will rediscover node instance and update its information" |

The difference in practice:

- **`PollStatusNow`** is the cheapest. It refreshes up/down status only. Use it when you have
  fixed something and want the console to stop showing red without waiting for the next
  cycle.
- **`PollNow`** collects the node's regular metrics as well.
- **`RediscoverNow`** re-examines what the device *is*, which is what you want after changing
  a credential, an SNMP version, or the device's own configuration. It is the most expensive
  of the three, so do not loop it over a thousand nodes.

```powershell
Invoke-SwisVerb $swis 'Orion.Nodes' 'PollNow'        @('N:42') | Out-Null
Invoke-SwisVerb $swis 'Orion.Nodes' 'PollStatusNow'  @('N:42') | Out-Null
Invoke-SwisVerb $swis 'Orion.Nodes' 'RediscoverNow'  @('N:42') | Out-Null
```

```python
swis.invoke("Orion.Nodes", "PollNow", "N:42")
swis.invoke("Orion.Nodes", "PollStatusNow", "N:42")
swis.invoke("Orion.Nodes", "RediscoverNow", "N:42")
```

```bash
curl -sS -X POST \
  -u 'svc-automation:...' \
  --cacert /etc/ssl/certs/orion-swis.pem \
  -H 'Content-Type: application/json' \
  -d '["N:42"]' \
  'https://orion.example.com:17774/SolarWinds/InformationService/v3/Json/Invoke/Orion.Nodes/PollNow'
```

All three return `System.Void`, so a `2xx` means "the request was accepted", not "the poll
finished". They queue work on the node's polling engine. Confirm by watching the timestamp
move rather than by parsing the response:

```sql
SELECT
    n.NodeID,
    n.Caption,
    n.Status,
    n.LastSync,
    n.MinutesSinceLastSync,
    n.NextPoll,
    n.NextRediscovery,
    n.IsPollingError,
    n.SkippedPollingCycles
FROM Orion.Nodes n
WHERE n.NodeID IN @ids
```

A node that is unmanaged will not poll. If `PollNow` appears to do nothing, check
`UnManaged` first: see [maintenance-mode.md](maintenance-mode.md).

## Deleting a node

Deletion is a CRUD `DELETE` against the node's URI. It is not reversible and it takes the
node's history with it, so almost every time someone reaches for it during an incident,
[unmanaging](maintenance-mode.md) is what they actually wanted.

Select first, look at what came back, then delete exactly that set:

```sql
SELECT n.NodeID, n.Caption, n.IPAddress, n.Status, n.LastSync, n.Uri
FROM Orion.Nodes n
WHERE n.Caption LIKE @pattern
ORDER BY n.Caption
```

```powershell
$doomed = Get-SwisData $swis @'
SELECT n.NodeID, n.Caption, n.Uri
FROM Orion.Nodes n
WHERE n.Caption LIKE @pattern
'@ @{ pattern = 'lab-decom-%' }

$doomed | Format-Table NodeID, Caption
Write-Warning "About to delete $($doomed.Count) node(s)."

foreach ($node in $doomed) {
    if ($PSCmdlet.ShouldProcess($node.Caption, 'Remove-SwisObject')) {
        Remove-SwisObject $swis -Uri $node.Uri
    }
}
```

```python
doomed = swis.query(
    "SELECT NodeID, Caption, Uri FROM Orion.Nodes WHERE Caption LIKE @p",
    p="lab-decom-%",
)["results"]

print(f"about to delete {len(doomed)} nodes")
for row in doomed:
    print(" ", row["NodeID"], row["Caption"])

# Only after reading that list:
swis.bulkdelete([r["Uri"] for r in doomed])
```

`BulkDelete` takes the same `uris` list as `BulkUpdate` and returns the same empty body, so
verify by asking for the nodes again and expecting nothing:

```sql
SELECT n.NodeID, n.Caption
FROM Orion.Nodes n
WHERE n.NodeID IN @ids
```

The platform removes a node's dependent objects along with it rather than leaving orphans,
which is why the operation is worth respecting. This page does not enumerate exactly which
child rows go, because that is server behaviour rather than a schema fact; if it matters for
your case, count the children before and after on a single test node:

```sql
SELECT
    (SELECT COUNT(i.InterfaceID) FROM Orion.NPM.Interfaces i WHERE i.NodeID = @nodeId) AS Interfaces,
    (SELECT COUNT(v.VolumeID) FROM Orion.Volumes v WHERE v.NodeID = @nodeId) AS Volumes,
    (SELECT COUNT(p.PollerID) FROM Orion.Pollers p WHERE p.NetObjectType = 'N' AND p.NetObjectID = @nodeId) AS Pollers
FROM Orion.Nodes n
WHERE n.NodeID = @nodeId
```

## The verbs on Orion.Nodes, in full

Seventeen in 2026.2. Regenerate this list for your version with
`python3 tools/schema_query.py verbs --entity Orion.Nodes`.

| Verb | Signature | Right |
|:---|:---|:---|
| `Unmanage` | `(netObjectId, unmanageTime, remanageTime, isRelative, allowOverlapping)` | `allowUnmanage` |
| `Remanage` | `(netObjectId)` | `allowUnmanage` |
| `PollNow` | `(netObjectId)` | `manageNodes` |
| `PollStatusNow` | `(netObjectId)` | `manageNodes` |
| `RediscoverNow` | `(netObjectId)` | `manageNodes` |
| `GetSupportedMetrics` | `(netObjectId)` returns array | `allowRealTimePolling` or `admin` |
| `StartRealTimePolling` | `(netObjectId, owner, properties, pollingExpiration, pollingFrequency)` returns boolean | `allowRealTimePolling` or `admin` |
| `StopRealTimePolling` | `(netObjectId, owner, properties)` returns boolean | `allowRealTimePolling` or `admin` |
| `GetCountOfElementsPerEngineForLicensing` | `()` | `manageNodes` |
| `ScheduleListResources` | `(nodeId)` returns string | `manageNodes` |
| `ScheduleListResourcesForAddress` | `(ipAddress, port, credentialsType, credentialProperties, engineId, preferredSnmpVersion)` returns string | `manageNodes` |
| `GetScheduledListResourcesStatus` | `(jobId, nodeId)` returns string | `manageNodes` |
| `GetScheduledListResourcesStatusByEngine` | `(jobId, engineId)` returns string | `manageNodes` |
| `GetListResourcesResult` | `(jobId, nodeId)` returns array | `manageNodes` |
| `GetListResourcesResultByEngine` | `(jobId, engineId)` returns array | `manageNodes` |
| `ImportListResourcesResult` | `(jobId, nodeId)` returns boolean | `manageNodes` |
| `ImportSelectedListResourcesResult` | `(jobId, nodeId, resources)` returns array | `manageNodes` |

Where two rights are listed, the schema records the verb as invokable by either.

## Related pages

- [pollers.md](pollers.md) explains the poller model that step two of "add a node" depends on
- [maintenance-mode.md](maintenance-mode.md) for unmanaging instead of deleting
- [custom-properties.md](custom-properties.md) for the extra columns you will want on nodes
- [discovery.md](discovery.md) for finding devices instead of declaring them
- [../swis/crud.md](../swis/crud.md) for the create, update and delete mechanics
- [../swis/invoke-verbs.md](../swis/invoke-verbs.md) for calling verbs from every client
- [../reference/netobject-types.md](../reference/netobject-types.md) for the `N:` prefix table
- [../reference/status-codes.md](../reference/status-codes.md) for what `Status` means

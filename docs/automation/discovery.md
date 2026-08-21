# Discovery

Discovery is the most intricate workflow in SWIS. Almost everything else is one verb call or
one property write. Discovery is a multi-phase job: you build a nested configuration
document, hand it to a verb that returns an id, poll a table until the job finishes, read the
outcome from a second table, and then optionally run a second asynchronous job to import the
results. Nothing about it is a single call, and nothing about it fails loudly.

It is worth the effort, because the alternative is declaring every node and every poller by
hand. Discovery is how the platform decides what a device can tell it and assigns the right
pollers automatically. See [node-management.md](node-management.md) for the by-hand route and
why it produces a node that monitors nothing until you fix that.

SolarWinds' own walkthrough is
[Discovery](https://solarwinds.github.io/OrionSDK/docs/discovery/), and the sample scripts
this page adapts are
[`DiscoverSnmpV3Node.ps1`](https://github.com/solarwinds/OrionSDK/blob/master/Samples/PowerShell/DiscoverSnmpV3Node.ps1),
[`DiscoverWmiNode.ps1`](https://github.com/solarwinds/OrionSDK/blob/master/Samples/PowerShell/DiscoverWmiNode.ps1),
[`ImportListResources.ps1`](https://github.com/solarwinds/OrionSDK/blob/master/Samples/PowerShell/ImportListResources.ps1)
and
[`NPM.DiscoverAndAddInterfacesOnNode.ps1`](https://github.com/solarwinds/OrionSDK/blob/master/Samples/PowerShell/NPM.DiscoverAndAddInterfacesOnNode.ps1).

## Two things are called discovery

They solve different problems and share almost no API surface. Pick the right one first.

| | **Network Sonar discovery** | **List Resources** |
|:---|:---|:---|
| Question | What devices are out there on these subnets? | What can this node I already monitor tell me? |
| Entity | `Orion.Discovery` | `Orion.Nodes` |
| Input | IP addresses, ranges, subnets, credentials | A `NodeID`, or an IP plus credentials |
| Creates | Nodes (and their children) | Pollers, interfaces, volumes on an existing node |
| Job handle | An integer `ProfileID` | A string `jobId` (a GUID) |
| Status from | A query against `Orion.DiscoveryProfiles` | A verb, `GetScheduledListResourcesStatus` |
| Sample | `DiscoverSnmpV3Node.ps1` | `ImportListResources.ps1` |

There is a third, narrower one: **lite interface discovery**, `DiscoverInterfacesOnNode` on
`Orion.NPM.Interfaces`, which finds interfaces on an existing node and adds selected ones in
two synchronous calls. It is the simplest of the three and is covered at the end.

## The entities and verbs, verified

```bash
python3 tools/schema_query.py find discovery
python3 tools/schema_query.py verbs --grep Discover
python3 tools/schema_query.py verbs --entity Orion.Discovery
```

### `Orion.Discovery` has no properties

```bash
python3 tools/schema_query.py show Orion.Discovery
```

```text
Orion.Discovery   [2026.2]
  operations: invoke
    invoke                                 requires manageNodes
  properties (0)
  verbs (12)
```

That is not an extraction gap. `Orion.Discovery` is a **verb-only entity**: it exists to
carry the twelve discovery operations and holds no rows. `SELECT * FROM Orion.Discovery`
would return nothing useful even if it parsed. Everything you read about a discovery comes
from the profile and log entities instead.

| Verb | Signature | Returns |
|:---|:---|:---|
| `CreateCorePluginConfiguration` | `(context)` | string |
| `StartDiscovery` | `(context)` | number (the `ProfileID`) |
| `StartDiscoveryProfile` | `(discoveryProfileId, engineId)` | `System.Void` |
| `GetDiscoveryProgress` | `(profileId)` | string |
| `CancelDiscovery` | `(profileId)` | `System.Void` |
| `DeleteDiscoveryProfile` | `(profileId)` | `System.Void` |
| `GetDiscoveryProfileResourcesResult` | `(profileId)` | array |
| `ImportDiscoveryResults` | `(cfg)` | string (an import id) |
| `GetImportDiscoveryResultsProgress` | `(importId)` | `DiscoveryImportProgressInfo` |
| `ValidateCredentials` | `(ipAddress, port, credentialsType, credentialsProperties, engineId, preferredSnmpVersion?)` | boolean |
| `ResolveHostnameFromIp` | `(ipAddress, engineId)` | string |
| `ResolveIpFromHostname` | `(hostname, preferredAddressFamily, engineId)` | string |

**All twelve require `manageNodes`.** A `403` on any of them is that right, not a discovery
problem.

### The tables you read

| Entity | Operations | Right | Holds |
|:---|:---|:---|:---|
| `Orion.DiscoveryProfiles` | read | `manageNodes` | One row per profile: `ProfileID`, `Name`, `Status`, `EngineID`, `LastRun`, schedule |
| `Orion.DiscoveryLogs` | read, create | read `manageNodes`, create `admin` | Outcome of a run: `Result`, `ResultDescription`, `ErrorMessage`, `BatchID` |
| `Orion.DiscoveryLogItems` | read | `manageNodes` | What a run imported, keyed on `BatchID` |
| `Orion.DiscoveredNodes` | read | `manageNodes` | Devices a profile found, before import |
| `Orion.DiscoveredNodeChildEntities` | read | `everyone` | Child objects found on a discovered node |
| `Orion.NPM.DiscoveredInterfaces` | read | `manageNodes` | Interfaces found, keyed on `ProfileID` |
| `Orion.DiscoveredVolumes` | read | `manageNodes` | Volumes found |
| `Orion.DiscoveredPollers` | read | `manageNodes` | Pollers the discovery decided apply |
| `Orion.DiscoveryNodesStatuses` | read | `manageNodes` | Per-object import status for a profile |
| `Orion.DiscoveryLogNodes` | none declared | none declared | Which nodes came from which profile, and when |
| `Orion.DiscoveryIgnoredNodes` | read | `manageNodes` | Addresses excluded from future discoveries |

"None declared" means the schema publishes no access control table for that entity, which is
common for entities the platform treats as views. They are queryable; they simply do not
advertise a right.

**`Orion.DiscoveryProfiles` is read-only.** You cannot create a discovery profile with CRUD:

```bash
python3 tools/schema_query.py show Orion.DiscoveryProfiles
```

```text
  operations: read
    read                                   requires manageNodes
```

A profile comes into existence as a side effect of `StartDiscovery`. That is the single
most important structural fact on this page, because the instinct on seeing a table full of
profiles is to insert into it, and that route does not exist.

## Network Sonar discovery, end to end

Five phases:

```text
  1. Build plugin configurations       CreateCorePluginConfiguration     -> XML string
     (core, and optionally interfaces)  CreateInterfacesPluginConfiguration
                                                  |
  2. Wrap them in a discovery context   (built client side, embeds phase 1 as text)
                                                  |
  3. Start                              StartDiscovery(context)          -> ProfileID (int)
                                                  |
  4. Poll                               SELECT Status FROM Orion.DiscoveryProfiles
                                        WHERE ProfileID = @profileId     -> loop while 1
                                                  |
  5. Read the outcome                   SELECT Result, ResultDescription, ErrorMessage,
                                               BatchID FROM Orion.DiscoveryLogs
                                                  |
                                     +------------+------------+
                          IsAutoImport=true            IsAutoImport=false
                                     |                         |
                        Orion.DiscoveryLogItems      ImportDiscoveryResults(cfg)
                        lists what was imported      -> importId, then poll
                                                     GetImportDiscoveryResultsProgress
```

### Phase 1: the core plugin configuration

`CreateCorePluginConfiguration` takes one argument, a `CorePluginConfigurationContext`. The
Swagger contract for 2026.2 declares exactly these members:

| Member | Type | Notes |
|:---|:---|:---|
| `BulkList` | array of `{ Address }` | Individual IP addresses |
| `IpRanges` | array of `{ StartAddress, EndAddress }` | Ranges, which may span subnets |
| `Subnets` | array of `{ SubnetIP, SubnetMask }` | **Mask syntax, not CIDR**: `255.255.255.0` |
| `ActiveDirectories` | array of `{ ADName, OrganizationalUnits, Credentials }` | Discovery from AD |
| `Credentials` | array of `{ CredentialID, Order }` | Tried in ascending `Order` |
| `WmiRetriesCount` | number | |
| `WmiRetryIntervalMiliseconds` | number | Spelled with one `l`, as in the contract |
| `PreferredPollingMethod` | enum | `SNMP` or `WMI` |

At least one of `BulkList`, `IpRanges`, `Subnets` or `ActiveDirectories` must be populated or
there is nothing to scan. SolarWinds advises against scanning a `/8`.

`CredentialID` values come from `Orion.Credential`:

```sql
SELECT c.ID, c.Name, c.Description, c.CredentialType, c.CredentialOwner
FROM Orion.Credential c
ORDER BY c.CredentialType, c.Name
```

`Order` decides the sequence credentials are tried against each discovered device. Values need
not be consecutive but must not repeat. Put the credential most devices use first: every
device is tried against every credential in turn until one works, so a bad order turns a ten
minute discovery into an hour.

The `Credentials` list is a set of **references** to credentials that already exist.
`Orion.Credential` has verbs to create them (`CreateSNMPCredentials`,
`CreateSNMPv3Credentials`, `CreateUsernamePasswordCredentials`), which is covered in
[credentials.md](credentials.md).

### Phase 1b: the interfaces plugin configuration

Optional. Without it, discovery uses the default interface filter. With it, you control which
interfaces are imported. `Orion.NPM.Interfaces.CreateInterfacesPluginConfiguration` takes an
`InterfacesDiscoveryPluginContext`:

| Member | Type | Notes |
|:---|:---|:---|
| `UseDefaults` | boolean | `true` overrides every other filter here |
| `AutoImportStatus` | array of string | SolarWinds' sample uses `Up`, `Down`, `Shutdown` |
| `AutoImportVirtualTypes` | array of string | sample uses `Virtual`, `Physical` |
| `AutoImportVlanPortTypes` | array of string | sample uses `Trunk`, `Access`, `Unknown` |
| `AutoImportExpressionFilter` | array of `{ Prop, Op, Val }` | |

The three string arrays are typed as free strings in the contract, so the accepted values are
not enumerated there. The values listed above are the ones SolarWinds' documentation uses,
and SolarWinds describes them as "all available values" for those three members. Default
behaviour, per the same page, is to import all `Up` interfaces regardless of type.

`AutoImportExpressionFilter` is present in the 2026.2 contract with members `Prop`, `Op` and
`Val`, but no accepted property names or operators are documented and no sample uses it, so
**its usage is unverified here**.

### Phase 2: the discovery context

`StartDiscoveryContext`, from the Swagger contract:

| Member | Type | Notes |
|:---|:---|:---|
| `Name` | string | Display only |
| `EngineId` | number | The discovery runs on **one** polling engine |
| `JobTimeoutSeconds` | number | |
| `SearchTimeoutMiliseconds` | number | |
| `SnmpTimeoutMiliseconds` | number | |
| `SnmpRetries` | number | |
| `RepeatIntervalMiliseconds` | number | |
| `SnmpPort` | number | |
| `HopCount` | number | `0` means do not walk out from what you find |
| `PreferredSnmpVersion` | enum | `None`, `SNMP1`, `SNMP2c`, `SNMP3` |
| `DisableIcmp` | boolean | |
| `AllowDuplicateNodes` | boolean | |
| `IsAutoImport` | boolean | `true` imports what it finds; `false` leaves it staged |
| `IsHidden` | boolean | `true` deletes the profile when the discovery completes |
| `PluginConfigurations` | array of `{ PluginConfigurationItem }` | The phase 1 outputs, **as strings** |

Pick engine ids from:

```sql
SELECT e.EngineID, e.ServerName, e.ServerType, e.KeepAlive
FROM Orion.Engines e
ORDER BY e.EngineID
```

Two members decide the shape of everything after this:

- **`IsAutoImport`.** `true` and the discovery adds what it finds, and phase 5 is a read.
  `false` and the results are staged in `Orion.DiscoveredNodes` for a later
  `ImportDiscoveryResults` call, which is a whole second asynchronous job.
- **`IsHidden`.** `true` and the profile is deleted when the discovery finishes, so the
  polling loop in phase 4 must tolerate the row disappearing. `false` and the profile stays
  and can be re-run from the console or with `StartDiscoveryProfile`.

### The nesting trap

`PluginConfigurationItem` is typed **`string`** in the contract, and the values you put in it
are the XML documents phase 1 returned. So you are embedding XML inside XML as text, which
means the inner document must be escaped: `<` becomes `&lt;`, `&` becomes `&amp;`.

In PowerShell, `.InnerXml` on the returned element plus string interpolation into an `[xml]`
cast does the escaping for you, which is why every SolarWinds sample looks the way it does.
In any other language, escape deliberately. This is the single most common reason a
hand-built discovery context is rejected with an unhelpful error.

### Phase 3 to 5, in one script

```powershell
Import-Module SwisPowerShell

$swis     = Connect-Swis -Hostname orion.example.com -Trusted
$engineId = 1
$ip       = '10.199.4.3'

# ---- Credentials: look up ids by name, never hard-code them ----
$credentialNames = @('Core network SNMPv3', 'Fallback SNMPv2c')
$credentials = foreach ($name in $credentialNames) {
    $id = Get-SwisData $swis 'SELECT ID FROM Orion.Credential WHERE Name = @name' @{ name = $name }
    if (-not $id) { throw "No credential named '$name'." }
    [pscustomobject]@{ Name = $name; ID = $id }
}
$credentialXml = ($credentials | ForEach-Object -Begin { $i = 0 } -Process {
    $i++
    "<SharedCredentialInfo><CredentialID>$($_.ID)</CredentialID><Order>$i</Order></SharedCredentialInfo>"
}) -join ''

# ---- Phase 1: core plugin configuration ----
$corePluginContext = ([xml]"
<CorePluginConfigurationContext xmlns='http://schemas.solarwinds.com/2012/Orion/Core'
                                xmlns:i='http://www.w3.org/2001/XMLSchema-instance'>
    <BulkList>
        <IpAddress><Address>$ip</Address></IpAddress>
    </BulkList>
    <Credentials>$credentialXml</Credentials>
    <WmiRetriesCount>1</WmiRetriesCount>
    <WmiRetryIntervalMiliseconds>1000</WmiRetryIntervalMiliseconds>
</CorePluginConfigurationContext>
").DocumentElement

$corePluginConfiguration =
    Invoke-SwisVerb $swis 'Orion.Discovery' 'CreateCorePluginConfiguration' @($corePluginContext)

# ---- Phase 1b: interfaces plugin configuration (optional; omit for defaults) ----
$interfacesPluginContext = ([xml]"
<InterfacesDiscoveryPluginContext xmlns='http://schemas.solarwinds.com/2008/Interfaces'
                                  xmlns:a='http://schemas.microsoft.com/2003/10/Serialization/Arrays'>
    <AutoImportStatus>
        <a:string>Up</a:string>
    </AutoImportStatus>
    <AutoImportVirtualTypes>
        <a:string>Physical</a:string>
    </AutoImportVirtualTypes>
    <UseDefaults>false</UseDefaults>
</InterfacesDiscoveryPluginContext>
").DocumentElement

$interfacesPluginConfiguration =
    Invoke-SwisVerb $swis 'Orion.NPM.Interfaces' 'CreateInterfacesPluginConfiguration' @($interfacesPluginContext)

# ---- Phase 2: the discovery context. Inner XML is embedded as escaped text. ----
$startContext = ([xml]"
<StartDiscoveryContext xmlns='http://schemas.solarwinds.com/2012/Orion/Core'
                       xmlns:i='http://www.w3.org/2001/XMLSchema-instance'>
    <Name>API discovery $([DateTime]::UtcNow.ToString('u'))</Name>
    <EngineId>$engineId</EngineId>
    <JobTimeoutSeconds>3600</JobTimeoutSeconds>
    <SearchTimeoutMiliseconds>2000</SearchTimeoutMiliseconds>
    <SnmpTimeoutMiliseconds>2000</SnmpTimeoutMiliseconds>
    <SnmpRetries>1</SnmpRetries>
    <RepeatIntervalMiliseconds>1500</RepeatIntervalMiliseconds>
    <SnmpPort>161</SnmpPort>
    <HopCount>0</HopCount>
    <PreferredSnmpVersion>SNMP2c</PreferredSnmpVersion>
    <DisableIcmp>false</DisableIcmp>
    <AllowDuplicateNodes>false</AllowDuplicateNodes>
    <IsAutoImport>true</IsAutoImport>
    <IsHidden>false</IsHidden>
    <PluginConfigurations>
        <PluginConfiguration>
            <PluginConfigurationItem>$($corePluginConfiguration.InnerXml)</PluginConfigurationItem>
            <PluginConfigurationItem>$($interfacesPluginConfiguration.InnerXml)</PluginConfigurationItem>
        </PluginConfiguration>
    </PluginConfigurations>
</StartDiscoveryContext>
").DocumentElement

# ---- Phase 3: start. The int comes back wrapped in an XML element. ----
$profileId = [int] (Invoke-SwisVerb $swis 'Orion.Discovery' 'StartDiscovery' @($startContext)).InnerText
Write-Host "Discovery profile $profileId started on engine $engineId."

# ---- Phase 4: poll. Bound, so a stuck job does not hang the script forever. ----
$deadline = (Get-Date).AddMinutes(30)
do {
    Start-Sleep -Seconds 5
    $status = Get-SwisData $swis `
        'SELECT Status FROM Orion.DiscoveryProfiles WHERE ProfileID = @profileId' `
        @{ profileId = $profileId }

    if ((Get-Date) -gt $deadline) {
        Invoke-SwisVerb $swis 'Orion.Discovery' 'CancelDiscovery' @($profileId) | Out-Null
        throw "Discovery $profileId did not finish within 30 minutes; cancel requested."
    }
} while ($status -eq 1)   # 1 = InProgress

# ---- Phase 5: the outcome. Survives IsHidden deleting the profile. ----
$log = Get-SwisData $swis @'
SELECT TOP 1 l.Result, l.ResultDescription, l.ErrorMessage, l.BatchID, l.FinishedTimeStamp
FROM Orion.DiscoveryLogs l
WHERE l.ProfileID = @profileId
ORDER BY l.FinishedTimeStamp DESC
'@ @{ profileId = $profileId }

$resultName = switch ($log.Result) {
    0 { 'Unknown' }        1 { 'InProgress' }   2 { 'Finished' }
    3 { 'Error' }          4 { 'NotScheduled' } 5 { 'Scheduled' }
    6 { 'NotCompleted' }   7 { 'Canceling' }    8 { 'ReadyForImport' }
    default { "Unrecognised ($($log.Result))" }
}
"Result: $resultName. $($log.ResultDescription) $($log.ErrorMessage)"

if ($log.Result -eq 2) {
    Get-SwisData $swis @'
SELECT i.EntityType, i.DisplayName, i.NetObjectID
FROM Orion.DiscoveryLogItems i
WHERE i.BatchID = @batchId
ORDER BY i.EntityType, i.DisplayName
'@ @{ batchId = $log.BatchID } | Format-Table
}
```

Differences from SolarWinds' sample, and why:

- **The poll loop is bounded and cancels on timeout.** The sample loops on `Status -eq 1`
  with no deadline, which hangs forever if the job wedges. `CancelDiscovery(profileId)` is the
  cleanup.
- **`Start-Sleep -Seconds 5` rather than 1.** Each iteration is a full round trip. Five
  seconds is plenty for a job measured in minutes.
- **`TOP 1 ... ORDER BY FinishedTimeStamp DESC` on the log query.** A profile that has run
  more than once has more than one log row, and `Get-SwisData` returning two rows makes
  `$log.Result` an array, which then fails the `switch` silently.
- **Credential ids looked up by name.** Ids differ between servers; names are what a human
  wrote down.

### The `Result` values

From SolarWinds'
[discovery page](https://solarwinds.github.io/OrionSDK/docs/discovery/). These are **not** in
the extracted schema:

| `Result` | Meaning |
|---:|:---|
| 0 | Unknown |
| 1 | InProgress |
| 2 | Finished |
| 3 | Error |
| 4 | NotScheduled |
| 5 | Scheduled |
| 6 | NotCompleted (cancelled) |
| 7 | Canceling |
| 8 | ReadyForImport (finished without auto-import) |

The polling loop in phase 4 compares `Orion.DiscoveryProfiles.Status` against `1`, which
SolarWinds' own samples do as well. The schema types `Status` as `System.Int32` and
`StatusDescription` as `System.String` but **does not state that `Status` uses the same
enumeration as `Result`**. Select `StatusDescription` alongside `Status` if you want a name
you can trust:

```sql
SELECT
    p.ProfileID,
    p.Name,
    p.Status,
    p.StatusDescription,
    p.EngineID,
    p.LastRun,
    p.RunTimeInSeconds,
    p.Active,
    p.IsAutoImport,
    p.IsHidden,
    p.ChangedNodesCount,
    p.NotImportedNodesCount
FROM Orion.DiscoveryProfiles p
ORDER BY p.LastRun DESC
```

### What the run found

With `IsAutoImport = true`, `Orion.DiscoveryLogItems` lists what was imported, keyed on the
`BatchID` from the log row:

```sql
SELECT
    i.BatchID,
    i.EntityType,
    i.DisplayName,
    i.NetObjectID
FROM Orion.DiscoveryLogItems i
WHERE i.BatchID = @batchId
ORDER BY i.EntityType, i.DisplayName
```

`Orion.DiscoveryLogs` also declares a hosting relationship to its items, so this works too:

```sql
SELECT
    l.ProfileID,
    l.FinishedTimeStamp,
    l.Result,
    l.Items.EntityType AS EntityType,
    l.Items.DisplayName AS DisplayName
FROM Orion.DiscoveryLogs l
WHERE l.ProfileID = @profileId
```

Regardless of import mode, the devices the scan found are in `Orion.DiscoveredNodes`:

```sql
SELECT
    dn.NodeID,
    dn.ProfileID,
    dn.IPAddress,
    dn.Hostname,
    dn.DNS,
    dn.SysName,
    dn.SysDescription,
    dn.Vendor,
    dn.MachineType,
    dn.SnmpVersion,
    dn.CredentialID,
    dn.Category,
    dn.Status
FROM Orion.DiscoveredNodes dn
WHERE dn.ProfileID = @profileId
ORDER BY dn.IPAddress
```

The `NodeID` on `Orion.DiscoveredNodes` is the **discovered** node id, scoped to the profile.
It is not an `Orion.Nodes.NodeID`, and joining the two on it is wrong. The mapping from a
discovered object to the managed object it became is in `Orion.DiscoveryNodesStatuses`:

```sql
SELECT
    s.ProfileID,
    s.DiscoveredObjectID,
    s.DiscoveredObjectType,
    s.ImportStatus,
    s.ManagedNetObjectID
FROM Orion.DiscoveryNodesStatuses s
WHERE s.ProfileID = @profileId
```

Children found on those devices, before import:

```sql
SELECT
    di.DiscoveredNodeID,
    di.InterfaceName,
    di.IfName,
    di.InterfaceAlias,
    di.InterfaceTypeName,
    di.OperStatus,
    di.AdminStatus
FROM Orion.NPM.DiscoveredInterfaces di
WHERE di.ProfileID = @profileId
ORDER BY di.DiscoveredNodeID, di.InterfaceIndex
```

```sql
SELECT
    ce.NodeID,
    ce.ChildEntityId,
    ce.Type,
    ce.Status,
    ce.Description
FROM Orion.DiscoveredNodeChildEntities ce
WHERE ce.ProfileID = @profileId
```

And afterwards, which nodes in the database came from a discovery at all:

```sql
SELECT
    dln.NodeID,
    dln.Node.Caption AS NodeCaption,
    dln.DiscoveryProfileName,
    dln.AutoImported,
    dln.NodeCreatedAt
FROM Orion.DiscoveryLogNodes dln
ORDER BY dln.NodeCreatedAt DESC
```

### Importing a staged discovery

With `IsAutoImport = false`, the run finishes with `Result = 8` (ReadyForImport) and nothing
is added. `ImportDiscoveryResults` takes one argument, a `DiscoveryImportConfiguration`. The
2026.2 contract declares five members:

| Member | Type | Notes |
|:---|:---|:---|
| `ProfileID` | number | Which discovery's results to import |
| `NodeIDs` | array of number | Discovered node ids. **Empty means all.** |
| `DeleteProfileAfterImport` | boolean | |
| `NewNodesCustomCategory` | enum | `Other`, `Network`, `Server` |
| `SelectedDiscoveredResources` | array of `KeyValuePair<int, DiscoveryResultExportItem>` | |

The ids in `NodeIDs` are `Orion.DiscoveredNodes.NodeID` values for that profile, which is why
the query above is the step before this one.

```powershell
# Choose what to import from what the scan staged.
$discovered = Get-SwisData $swis @'
SELECT dn.NodeID, dn.IPAddress, dn.SysName, dn.Vendor, dn.MachineType
FROM Orion.DiscoveredNodes dn
WHERE dn.ProfileID = @profileId
ORDER BY dn.IPAddress
'@ @{ profileId = $profileId }

$discovered | Format-Table
$wanted = $discovered | Where-Object { $_.Vendor -eq 'Cisco' }
"Importing $($wanted.Count) of $($discovered.Count) discovered node(s)."

$nodeIdXml = ($wanted | ForEach-Object { "<a:int>$($_.NodeID)</a:int>" }) -join ''

$importConfiguration = ([xml]"
<DiscoveryImportConfiguration xmlns='http://schemas.solarwinds.com/2008/Core'>
    <ProfileID>$profileId</ProfileID>
    <NodeIDs xmlns:a='http://schemas.microsoft.com/2003/10/Serialization/Arrays'>$nodeIdXml</NodeIDs>
    <DeleteProfileAfterImport>false</DeleteProfileAfterImport>
</DiscoveryImportConfiguration>
").DocumentElement

$importId = (Invoke-SwisVerb $swis 'Orion.Discovery' 'ImportDiscoveryResults' @($importConfiguration)).InnerText

# The import is asynchronous too. Poll it.
do {
    Start-Sleep -Seconds 3
    $progress = Invoke-SwisVerb $swis 'Orion.Discovery' 'GetImportDiscoveryResultsProgress' @($importId)
    "$($progress.PhaseName): overall $($progress.OverallProgress)%, phase $($progress.PhaseProgress)%"
} while ($progress.Finished -ne 'true')
```

`GetImportDiscoveryResultsProgress` returns a `DiscoveryImportProgressInfo`, whose members
the contract declares as `Finished`, `OverallProgress`, `PhaseProgress`, `PhaseName`,
`NewLogText` and `LogBuilder`. SolarWinds notes that `NewLogText` is capped at 128 kB per
call and that subsequent calls page through the rest, so accumulate it rather than replacing
it if you want the whole log.

Two limitations to know before choosing `IsAutoImport = false`:

- SolarWinds states that passing an **empty** `NodeIDs` array "import[s] all discovered nodes
  but does not import child objects (e.g. interfaces)". If you want interfaces, either list
  the node ids explicitly or use auto-import.
- SolarWinds states it "is currently not possible to filter node child objects ... when using
  IsAutoImport=FALSE"; interface filtering is only available through the interfaces plugin
  configuration with `IsAutoImport = true`. The 2026.2 contract does carry a
  `SelectedDiscoveredResources` member on the import configuration that is not described in
  that guidance, so this limitation may have narrowed. **The semantics of
  `SelectedDiscoveredResources` are unverified here.**

### Re-running and cleaning up

```powershell
# Re-run a saved (IsHidden = false) profile. Note it takes the engine id as well.
Invoke-SwisVerb $swis 'Orion.Discovery' 'StartDiscoveryProfile' @($profileId, $engineId) | Out-Null

# Cancel one that is running.
Invoke-SwisVerb $swis 'Orion.Discovery' 'CancelDiscovery' @($profileId) | Out-Null

# Delete a profile you no longer want.
Invoke-SwisVerb $swis 'Orion.Discovery' 'DeleteDiscoveryProfile' @($profileId) | Out-Null
```

`StartDiscoveryProfile` returns `System.Void`, so verify by querying `Status` and `LastRun`
on the profile rather than by reading the response.

### Checking a credential before you scan with it

`ValidateCredentials` answers "will this credential work against this device" without running
a discovery, which turns a failed hour-long scan into a two second check:

```bash
python3 tools/schema_query.py verb Orion.Discovery ValidateCredentials
```

```text
Orion.Discovery.ValidateCredentials
  Check if provided credential is valid for given SNMP or WMI endpoint
  returns: boolean
  parameters (6):
    ipAddress: string (required)
    port: number (required)
    credentialsType: string (required)
    ...
    engineId: number (required)
    preferredSnmpVersion: SolarWinds.Orion.Core.Models.Credentials.SNMPVersion (optional)
        one of: None, SNMP1, SNMP2c, SNMP3
```

The elided line is `credentialsProperties`, typed as an array of .NET
`KeyValuePair<string,string>`. It is elided here only because its fully qualified type name
is long enough to wrap; the tool prints it in full.

`credentialsProperties` is a key/value array. **The keys it expects are not described in the
schema or the Swagger contract**, and no SDK sample calls this verb, so the content is
unverified here. `Metadata.VerbArgument` on a live server carries an `XmlTemplate` column
that shows the shape SWIS expects for complex arguments:

```sql
SELECT Position, Name, Type, IsOptional
FROM Metadata.VerbArgument
WHERE EntityName = 'Orion.Discovery' AND VerbName = 'ValidateCredentials'
ORDER BY Position
```

See [../swis/metadata-introspection.md](../swis/metadata-introspection.md).

`ResolveIpFromHostname(hostname, preferredAddressFamily, engineId)` and
`ResolveHostnameFromIp(ipAddress, engineId)` resolve names using the **polling engine's**
resolver rather than your workstation's, which is the useful part: an engine in a different
DNS view resolves differently, and that is often the reason a discovery finds nothing.
`preferredAddressFamily` is a `System.Net.Sockets.AddressFamily`; the practical values are
`InterNetwork` for IPv4 and `InterNetworkV6` for IPv6.

## List Resources on an existing node

This is the flow behind "List Resources" in the node management UI: ask a node that is
already monitored what else it can report, then turn those on. It is asynchronous, it is
job-based, and the job id is a string rather than an integer.

```text
  ScheduleListResources(nodeId)                       -> jobId (string GUID)
                    |
  GetScheduledListResourcesStatus(jobId, nodeId)      -> status string
                    |    loop until "ReadyForImport"
                    |
        +-----------+------------------------------+
        |                                          |
  ImportListResourcesResult(jobId, nodeId)   GetListResourcesResult(jobId, nodeId)
        -> boolean, imports everything            -> array of DiscoveryResultExportItem
                                                            |
                                              edit IsSelected on the tree
                                                            |
                          ImportSelectedListResourcesResult(jobId, nodeId, resources)
                                                            -> array
```

All eight verbs live on `Orion.Nodes` and all eight require `manageNodes`:

| Verb | Parameters | Returns |
|:---|:---|:---|
| `ScheduleListResources` | `(nodeId)` | string |
| `ScheduleListResourcesForAddress` | `(ipAddress, port, credentialsType, credentialProperties, engineId, preferredSnmpVersion?)` | string |
| `GetScheduledListResourcesStatus` | `(jobId, nodeId)` | string |
| `GetScheduledListResourcesStatusByEngine` | `(jobId, engineId)` | string |
| `GetListResourcesResult` | `(jobId, nodeId)` | array |
| `GetListResourcesResultByEngine` | `(jobId, engineId)` | array |
| `ImportListResourcesResult` | `(jobId, nodeId)` | boolean |
| `ImportSelectedListResourcesResult` | `(jobId, nodeId, resources)` | array |

### Why `nodeId` appears on every call

The parameter descriptions in the schema say it outright:

```bash
python3 tools/schema_query.py verb Orion.Nodes GetScheduledListResourcesStatus
```

```text
Orion.Nodes.GetScheduledListResourcesStatus
  Get current result of discovery job
  returns: string
  requires: manageNodes
  parameters (2):
    jobId: string (required)
        Job identifier to get status for
    nodeId: number (required)
        Provide node id to identify engine running the discovery
```

The job runs on a specific polling engine, and the `nodeId` is how SWIS works out which. That
is also why the `ByEngine` variants exist: pass `engineId` directly when you know it, which
is the only option for `ScheduleListResourcesForAddress`, because there is no node yet.

### The status strings

`GetScheduledListResourcesStatus` returns a **string**, per the Swagger contract. SolarWinds'
samples show three values in use: `Unknown` immediately after scheduling, `InProgress` while
it runs, and `ReadyForImport` when the result can be fetched. **The full enumeration is not
published**, so treat any value you do not recognise as "keep waiting, but time out", never
as success.

`ImportListResources.ps1` documents a real behaviour worth reproducing: the job stays in
`Unknown` for a few seconds after `ScheduleListResources` returns, and calling
`ScheduleListResources` again for the same node too soon does not help. Its comment is
"This is probably caused by calling this script with same nodeId. Please wait few minutes or
extend timeout."

### The whole flow, importing everything

Adapted from
[`ImportListResources.ps1`](https://github.com/solarwinds/OrionSDK/blob/master/Samples/PowerShell/ImportListResources.ps1):

```powershell
[CmdletBinding()]
param(
    [Parameter(Mandatory)] [object] $swis,
    [Parameter(Mandatory)] [int]    $nodeId,
    [int] $timeoutSeconds     = 300,
    [int] $pollIntervalSeconds = 5
)

# Confirm the node exists and note which engine it is on, for the error message later.
$node = Get-SwisData $swis @'
SELECT n.NodeID, n.Caption, n.IPAddress, n.EngineID, n.ObjectSubType, n.Status
FROM Orion.Nodes n
WHERE n.NodeID = @nodeId
'@ @{ nodeId = $nodeId }

if (-not $node) { throw "No node with NodeID $nodeId." }
"List Resources on $($node.Caption) ($($node.IPAddress)), engine $($node.EngineID)."

$sw = [Diagnostics.Stopwatch]::StartNew()

# 1. Schedule. The job id arrives as text inside an XML element.
$jobId = (Invoke-SwisVerb $swis 'Orion.Nodes' 'ScheduleListResources' @($nodeId)).'#text'
Write-Verbose "Job $jobId"

# 2. Wait out the Unknown phase, then poll for ReadyForImport.
do {
    Start-Sleep -Seconds $pollIntervalSeconds
    $status = (Invoke-SwisVerb $swis 'Orion.Nodes' 'GetScheduledListResourcesStatus' `
        @($jobId, $nodeId)).'#text'
    Write-Verbose "Status: $status"

    if ($sw.Elapsed.TotalSeconds -gt $timeoutSeconds) {
        throw "Job $jobId on node $nodeId stuck at '$status' after $timeoutSeconds s."
    }
} while ($status -ne 'ReadyForImport')

# 3. Import everything the job found.
$imported = (Invoke-SwisVerb $swis 'Orion.Nodes' 'ImportListResourcesResult' @($jobId, $nodeId)).'#text'

if (-not [System.Convert]::ToBoolean($imported)) {
    throw "Import of List Resources for node $nodeId finished with errors."
}

# 4. Verify by looking at what the node now monitors.
Get-SwisData $swis @'
SELECT p.PollerType, p.Enabled
FROM Orion.Pollers p
WHERE p.NetObject = @netObject
ORDER BY p.PollerType
'@ @{ netObject = "N:$nodeId" } | Format-Table
```

`.'#text'` and `.InnerText` are equivalent here. The samples use `.'#text'`; either works.

### Importing only some of what was found

`ImportListResourcesResult` turns on everything. To be selective, fetch the result tree,
flip `IsSelected` on the items you want, and pass the tree back. Each item is a
`DiscoveryResultExportItem`, whose members the contract declares as `DisplayName`,
`TypeName`, `IsSelected`, `Children` (a nested array of the same type), `Metadata` (a
key/value array) and `IsImported`.

```powershell
$jobResults = Invoke-SwisVerb $swis 'Orion.Nodes' 'GetListResourcesResult' @($jobId, $nodeId)

# Look at the tree before changing anything. Top level is categories.
$jobResults.DiscoveryResultExportItem.Children.DiscoveryResultExportItem |
    Select-Object @{n='Name';e={$_.DisplayName.'#text'}}, TypeName, IsSelected |
    Format-Table

# Select one category and one poller under it.
$category = $jobResults.DiscoveryResultExportItem.Children.DiscoveryResultExportItem |
    Where-Object { $_.DisplayName.'#text' -eq 'CPU & Memory' }
$category.IsSelected = 'true'

$poller = $category.Children.DiscoveryResultExportItem |
    Where-Object { $_.DisplayName.'#text' -eq 'CPU & Memory by SolarWinds' }
$poller.IsSelected = 'true'

Invoke-SwisVerb $swis 'Orion.Nodes' 'ImportSelectedListResourcesResult' @($jobId, $nodeId, $jobResults)
```

The tree comes back as XML, and manipulating it is fiddly. SolarWinds' own
[`ImportSelectedListResources_CPUMemory.ps1`](https://github.com/solarwinds/OrionSDK/blob/master/Samples/PowerShell/ImportSelectedListResources_CPUMemory.ps1)
sample includes a step that is easy to miss and worth understanding: after setting
`IsSelected`, it **re-assigns the display name with the ampersand re-escaped**
(`$XMLElementBranch.DisplayName.'#text' = 'CPU &amp; Memory'`). PowerShell's XML DOM
un-escapes entities on read, and the value has to go back as it came. If your target names
contain `&`, `<` or `>`, expect to do the same. Names without those characters need no such
handling.

Do not hard-code the display names from the sample. Print the tree on your own node first,
because the categories and poller names depend on what the device supports and which modules
are installed.

### List Resources on an address that is not a node yet

`ScheduleListResourcesForAddress` runs the same job against a bare IP, so there is no node id
to identify the engine and you supply one:

```bash
python3 tools/schema_query.py verb Orion.Nodes ScheduleListResourcesForAddress
```

```text
Orion.Nodes.ScheduleListResourcesForAddress
  Schedule one time List Resources discovery for given ip address
  returns: string
  requires: manageNodes
  parameters (6):
    ipAddress: string (required)
        IP address of a target device to list resources for
    port: number (required)
        Port
    credentialsType: string (required)
        Credentials type
    ...
    engineId: number (required)
        Define engine to be used for the discovery
    preferredSnmpVersion: SolarWinds.Orion.Core.Models.Credentials.SNMPVersion (optional)
        one of: None, SNMP1, SNMP2c, SNMP3
```

The elided line is `credentialProperties`, an array of .NET `KeyValuePair<string,string>`,
same as on `ValidateCredentials`.

Track it with the `ByEngine` variants, since there is still no node:

```powershell
$jobId = (Invoke-SwisVerb $swis 'Orion.Nodes' 'ScheduleListResourcesForAddress' `
    @($ipAddress, 161, $credentialsType, $credentialProperties, $engineId, 'SNMP2c')).'#text'

do {
    Start-Sleep -Seconds 5
    $status = (Invoke-SwisVerb $swis 'Orion.Nodes' 'GetScheduledListResourcesStatusByEngine' `
        @($jobId, $engineId)).'#text'
} while ($status -ne 'ReadyForImport')

$result = Invoke-SwisVerb $swis 'Orion.Nodes' 'GetListResourcesResultByEngine' @($jobId, $engineId)
```

Note the asymmetry: there are `ByEngine` variants for **status** and **result**, but not for
either import verb. Both `ImportListResourcesResult` and
`ImportSelectedListResourcesResult` take a `nodeId`. So this flow is for **inspecting** an
address before adding it, not for adding it. Create the node first
([node-management.md](node-management.md)), then run the `nodeId` flow.

`credentialsType` and `credentialProperties` have the same problem as
`Orion.Discovery.ValidateCredentials`: the schema names the parameters and their types but
does not enumerate the accepted type strings or the expected keys, and no SDK sample calls
this verb. **Both are unverified here.** Check `Metadata.VerbArgument.XmlTemplate` on your own
server.

## Lite interface discovery

The simplest of the three flows, and synchronous. Two verbs, both on `Orion.NPM.Interfaces`,
both requiring `manageNodes`:

```bash
python3 tools/schema_query.py verbs --entity Orion.NPM.Interfaces
```

```text
  Orion.NPM.Interfaces.AddInterfacesOnNode(nodeId, interfacesToAdd, pollers) -> SolarWinds.Interfaces.Common.Models.Discovery.LiteDiscoveryResult
      Add provided interface to node.
  Orion.NPM.Interfaces.DiscoverInterfacesOnNode(nodeId) -> SolarWinds.Interfaces.Common.Models.Discovery.LiteDiscoveryResult
      Run lite discovery process for search interfaces on node and returns list of interfaces.
```

The Swagger contract declares `LiteDiscoveryResult` as `{ DiscoveredInterfaces, Result }`,
with `Result` being one of `Succeed`, `InvalidNode` or `GenericError`, and each
`DiscoveredLiteInterface` carrying `ifIndex`, `Caption`, `ifType`, `ifSubType`,
`InterfaceID`, `Manageable`, `ifSpeed`, `ifAdminStatus` and `ifOperStatus`. The `pollers`
argument is an enum with exactly two values: `AddDefaultPollers` or `AddNoPollers`.

Adapted from
[`NPM.DiscoverAndAddInterfacesOnNode.ps1`](https://github.com/solarwinds/OrionSDK/blob/master/Samples/PowerShell/NPM.DiscoverAndAddInterfacesOnNode.ps1):

```powershell
$discovered = Invoke-SwisVerb $swis 'Orion.NPM.Interfaces' 'DiscoverInterfacesOnNode' @($nodeId)

if ($discovered.Result -ne 'Succeed') {
    throw "Interface discovery on node $nodeId returned '$($discovered.Result)'."
}

# Look before filtering.
$discovered.DiscoveredInterfaces.DiscoveredLiteInterface |
    Select-Object @{n='Name';e={$_.Caption.'#text'}}, ifIndex, ifType, ifSpeed,
                  ifAdminStatus, ifOperStatus, Manageable |
    Format-Table

# Remove the ones you do not want, in place, from the XML the verb returned.
$discovered.DiscoveredInterfaces.DiscoveredLiteInterface |
    Where-Object { $_.Caption.'#text' -eq 'lo' } |
    ForEach-Object { $discovered.DiscoveredInterfaces.RemoveChild($_) | Out-Null }

Invoke-SwisVerb $swis 'Orion.NPM.Interfaces' 'AddInterfacesOnNode' `
    @($nodeId, $discovered.DiscoveredInterfaces, 'AddDefaultPollers') | Out-Null

# Verify.
Get-SwisData $swis @'
SELECT i.InterfaceID, i.Caption, i.InterfaceName, i.Status
FROM Orion.NPM.Interfaces i
WHERE i.NodeID = @nodeId
ORDER BY i.InterfaceIndex
'@ @{ nodeId = $nodeId } | Format-Table
```

The filtering pattern is **removal from the returned document**, not construction of a new
list. You pass back the same `DiscoveredInterfaces` element with the unwanted children
deleted. Building your own element from scratch is a much longer road because the
serialisation has to match exactly.

`AddNoPollers` adds the interfaces but attaches no pollers, so they appear in the database and
report nothing. That is occasionally what you want (inventory without polling load), and it
is very often an accident. See [pollers.md](pollers.md).

## Things that go wrong

- **Trying to insert into `Orion.DiscoveryProfiles`.** It is read-only. Profiles are created
  by `StartDiscovery`.
- **Trying to `SELECT` from `Orion.Discovery`.** It has zero properties and only `invoke`.
- **Inner XML not escaped.** `PluginConfigurationItem` is typed `string`, so the plugin
  configuration goes in as escaped text. `.InnerXml` interpolated into an `[xml]` cast does
  this in PowerShell; other languages must escape deliberately.
- **CIDR in `SubnetMask`.** The contract wants mask syntax, `255.255.255.0`, not `/24`.
- **Duplicate `Order` values in `Credentials`.** They must be unique. They need not be
  consecutive.
- **Reading the verb's return value directly in PowerShell.** `Invoke-SwisVerb` returns an
  XML element. Use `.InnerText` or `.'#text'`, and cast: `[int] (...).InnerText`.
- **An unbounded poll loop.** SolarWinds' sample loops on `Status -eq 1` forever. Add a
  deadline and call `CancelDiscovery` when you hit it.
- **`IsHidden = true` plus a status query.** The profile row is deleted when the discovery
  finishes, so the loop must tolerate a null status. `Orion.DiscoveryLogs` survives, which is
  why the outcome is read from there.
- **`Get-SwisData` returning several log rows.** A profile that has run more than once has
  more than one row in `Orion.DiscoveryLogs`. Use `TOP 1` with an `ORDER BY`.
- **Joining `Orion.DiscoveredNodes.NodeID` to `Orion.Nodes.NodeID`.** Different id spaces.
  `Orion.DiscoveryNodesStatuses.ManagedNetObjectID` is the mapping.
- **Empty `NodeIDs` on import, then wondering where the interfaces went.** SolarWinds
  documents that the empty case imports nodes without child objects.
- **Calling `ScheduleListResources` twice for the same node in quick succession.** The job
  stays in `Unknown`. Wait, or extend the timeout; do not re-schedule.
- **Treating an unrecognised List Resources status as success.** The enumeration is not
  published. Only `ReadyForImport` means ready.
- **Hard-coding the List Resources display names from the sample.** They depend on the device
  and the installed modules. Print the tree first.
- **Losing XML entity escaping when editing the result tree.** PowerShell un-escapes on read.
  SolarWinds' sample re-escapes `&` on write.
- **`AddNoPollers` by accident.** Interfaces appear and report nothing.
- **A `403` anywhere in here.** Every discovery and List Resources verb requires
  `manageNodes`.

## What is not verified here

| Claim | Status | How to check on your server |
|---|---|---|
| The `Result` values 0 to 8 on `Orion.DiscoveryLogs` | From SolarWinds' discovery page, not from the extracted schema | [Discovery](https://solarwinds.github.io/OrionSDK/docs/discovery/); or read `Result` and `ResultDescription` together across your own log rows |
| That `Orion.DiscoveryProfiles.Status` uses the same enumeration as `Orion.DiscoveryLogs.Result` | Implied by SolarWinds' samples polling `Status -eq 1` for "in progress"; not stated in the schema | `SELECT DISTINCT Status, StatusDescription FROM Orion.DiscoveryProfiles` |
| The complete set of List Resources status strings | Only `Unknown`, `InProgress` and `ReadyForImport` are attested, from SolarWinds' samples | Log every distinct value your own jobs return |
| Accepted values for `AutoImportStatus`, `AutoImportVirtualTypes`, `AutoImportVlanPortTypes` | Typed as free strings in the contract; the listed values come from SolarWinds' documentation | Compare a UI-built discovery profile's behaviour against a scripted one |
| Usage of `AutoImportExpressionFilter` (`Prop`, `Op`, `Val`) | Members exist in the 2026.2 contract; no accepted values documented, no sample uses it | `SELECT Position, Name, Type, IsOptional, XmlTemplate FROM Metadata.VerbArgument WHERE EntityName = 'Orion.NPM.Interfaces' AND VerbName = 'CreateInterfacesPluginConfiguration'` |
| Semantics of `DiscoveryImportConfiguration.SelectedDiscoveredResources` | Present in the 2026.2 contract; SolarWinds' guidance that child objects cannot be filtered on a staged import predates it | Stage a discovery with `IsAutoImport = false`, then compare an import with and without the member populated |
| Keys expected in `credentialsProperties` / `credentialProperties` on `ValidateCredentials` and `ScheduleListResourcesForAddress` | Typed as `KeyValuePair<string,string>` arrays with no key names anywhere | `Metadata.VerbArgument.XmlTemplate` for those verbs |
| Accepted values for the `credentialsType` string | Not enumerated in the schema or the contract | `SELECT DISTINCT CredentialType FROM Orion.Credential` is the closest starting point, but the correspondence is unconfirmed |
| The meaning of `Orion.DiscoveredNodes.Status`, `Orion.DiscoveryNodesStatuses.ImportStatus` and `Orion.DiscoveredNodeChildEntities.Status` | Typed `System.Int32` with no description | Run one discovery you control end to end and record the values at each stage |

## Related pages

- [README.md](README.md) for the query-first method these flows follow
- [node-management.md](node-management.md) for adding a node by hand and for `RediscoverNow`
- [pollers.md](pollers.md) for why an imported node still needs the right pollers
- [credentials.md](credentials.md) for creating the credentials a discovery references
- [../modules/npm.md](../modules/npm.md) for interfaces once they are monitored
- [../swis/invoke-verbs.md](../swis/invoke-verbs.md) for complex verb arguments in each client
- [../swis/metadata-introspection.md](../swis/metadata-introspection.md) for `Metadata.VerbArgument.XmlTemplate`
- [../reference/verb-index.md](../reference/verb-index.md) for the full verb catalogue

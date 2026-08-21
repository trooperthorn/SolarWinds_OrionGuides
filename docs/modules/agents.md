# Agents: the SolarWinds agent

Every other way the platform collects data is a **pull from the outside**. A polling engine
opens SNMP, WMI or ICMP to a device and asks it questions. That works until something sits
between the engine and the device: a NAT boundary, a firewall that only allows outbound
traffic, a cloud subnet with no route back, a Windows host where remote WMI is disabled by
policy, or a Linux box where you would rather not expose an SNMP daemon at all.

The agent inverts that. A small service runs **on** the monitored machine, collects locally,
and moves the results over one connection to the Agent Management Service (AMS) on a polling
engine. Because the agent chooses which direction that connection is opened, it can reach
places a poller cannot, and because it runs locally it can collect things no remote protocol
exposes.

The API surface for all of this is `Orion.AgentManagement.Agent` and a small supporting cast,
and it is unusual in one way worth knowing up front: **almost everything you do to an agent is
a verb, not a property write.** The entity declares 20 verbs, which is more than `Orion.Nodes`
itself declares. Deployment, plugin installation, update approval, engine reassignment, restart
and uninstall are all invocations. That is the opposite of the shape you learn from
[../automation/node-management.md](../automation/node-management.md), and it is why this page
spends most of its length on verbs.

## When to use an agent instead of SNMP or WMI

The schema itself tells you most of what the trade is.

**Use an agent when the network will not let you poll.** `Orion.AgentManagement.Agent.Mode`
is documented in the schema as "1 if the agent is in active mode (Agent-initiated
communication), 2 if the agent is in passive (Server-initiated communication) mode, 0 if agent
mode will be automatically detected during installation". Active mode means the monitored
machine dials out to the polling engine. Nothing has to be able to reach *in*, so a host behind
NAT, in a DMZ, or in another organisation's cloud account becomes monitorable without a
firewall change in the inbound direction. `Orion.AgentManagement.Proxy` extends that further:
the outbound connection can go through an HTTP proxy with its own credential.

**Use an agent when one channel has to carry many modules.**
`Orion.AgentManagement.AgentPlugin` is one row per plugin per agent, each with its own
`Version`, `Status` and `StatusMessage`. A single agent connection carries SAM component
polling, Log Analyzer file collection (`Orion.OLM.LogProfile` navigates to agents through
`Agents`), NetPath probing (`Orion.NetPath.Probes` navigates through `Agent`) and QoE packet
inspection. Doing the same thing without an agent means several protocols, several credentials
and several firewall rules.

**Use an agent when the credential is the problem.** A WMI node needs a Windows account with
remote access rights, stored centrally and pointed at from `Orion.NodeSettings`. See
[../automation/node-management.md](../automation/node-management.md#a-wmi-node-needs-a-credential-association).
An agent needs a credential exactly once, at deployment, and after that the agent authenticates
itself. That is a materially smaller standing privilege.

**Stay with SNMP when the target is not a general-purpose computer.** There is no agent for a
switch, a router, a firewall, a UPS or a storage array. The agent runs on Windows and Linux, as
`Orion.AgentManagement.Agent.OSType` and `Orion.AgentManagement.InstallPackage.OsType` show;
`Orion.AgentManagement.InstallPackage` covers the Linux distributions with prebuilt packages.

**Stay with agentless when you are counting elements.** An agent is software you now own on
every monitored host: it has a version, it needs updating, and
`Orion.AgentManagement.Agent.AgentStatus` gives you a whole new class of thing that can be
broken. Query 4 below exists because that class of thing does break.

## Namespaces and how many entities

Agent management contributes **16 entities**, all under `Orion.AgentManagement.`.

```bash
python3 tools/schema_query.py find AgentManagement --properties
python3 tools/schema_query.py show Orion.AgentManagement.Agent
python3 tools/schema_query.py verbs --entity Orion.AgentManagement.Agent
```

Only four of them carry data you will query:

| Entity | Properties | Verbs | What it is |
|---|---:|---:|---|
| `Orion.AgentManagement.Agent` | 37 | 20 | One row per agent. The whole module, effectively. |
| `Orion.AgentManagement.AgentPlugin` | 6 | 0 | One row per plugin per agent, with its own version and status. |
| `Orion.AgentManagement.Proxy` | 4 | 2 | HTTP proxy definitions for agent-to-AMS traffic. |
| `Orion.AgentManagement.InstallPackage` | 8 | 0 | The Linux install packages AMS holds, keyed by `PackageId`. Read-only. |

The other twelve are `System.Indication` types, which is to say they are events SWIS publishes
rather than tables you select from. `Orion.AgentManagement.AgentIndication` is the base of ten
of them and declares the fields they share (`AgentId`, `AgentGuid`, `AgentName`, `IP`,
`DNSName`, `PollingEngineId`); the leaves add nothing of their own and exist so that a
subscriber or an audit trail can name the specific action:
`AgentRemoteDeploymentInitiated`, `AgentManualDeploymentInitiated`, the two
`...UsingCertificate` variants, `AgentUninstallInitiated`,
`AgentUninstallInitiatedFromAgent`, `AgentServiceRestartInitiated`,
`AgentMachineRebootInitiated`, `AgentLogLevelChanged` and
`AgentPromoteToRemoteCollectorInitiated`. `Orion.AgentManagement.AgentGlobalSettingChanged` is
the twelfth and sits directly on `System.Indication` with `SettingName`, `PreviousValue` and
`CurrentValue`.

Whether a query against one of those indication entities returns historical rows, or nothing
at all because indications are transient, is **not recorded in the published schema** and is
not verified here. For a history of who deployed or uninstalled what, use
`Orion.AuditingEvents`, which is a real table. Query 9 below does that.

## The agent record

`Orion.AgentManagement.Agent` inherits directly from `System.Entity`, so it gets `Uri`,
`DisplayName`, `Description` and `InstanceType` and nothing else. In particular it is **not** a
`System.ManagedEntity`, so it has no `UnManaged`, `UnManageFrom` or `UnManageUntil`: you cannot
put an agent into a maintenance window. The node it monitors can be unmanaged, and that is the
lever you actually have. See [../automation/maintenance-mode.md](../automation/maintenance-mode.md).

Identity and location:

| Property | Type | Notes |
|---|---|---|
| `AgentId` | `System.Int32` | The key, and the argument almost every verb takes. |
| `AgentGuid` | `System.Guid` | Stable identity of the agent installation itself. |
| `NodeId` | `System.Int32` | The node this agent monitors. Navigate with `Node`. |
| `Name` | `System.String` | Display name, chosen at deploy time. |
| `Hostname`, `DNSName`, `IP` | `System.String` | The machine the agent runs on. |
| `SID` | `System.String` | The Windows security identifier of the host, or "a unique-like identifier of the server in case of Linux system". This is how AMS recognises a machine it has seen before. |
| `PollingEngineId` | `System.Int32` | Which engine's AMS the agent talks to. Navigate with `Engine`. |
| `RegisteredOn` | `System.DateTime` | When the agent first registered. |

Connection mode:

| Property | Type | Notes |
|---|---|---|
| `Mode` | `System.Int32` | `0` auto-detect at install, `1` active (agent-initiated), `2` passive (server-initiated). |
| `IsActiveAgent` | `System.Boolean` | True when the agent is in active mode. Derived from `Mode`, and easier to filter on. |
| `PassiveAgentHostname` | `System.String` | Where AMS connects **to** in passive mode. |
| `PassiveAgentPort` | `System.String` | The listening port in passive mode. Note the type: it is a string, not an integer. |
| `ProxyId` | `System.Int32` | The `Orion.AgentManagement.Proxy` used for the outbound connection. |

Health and version:

| Property | Type | Notes |
|---|---|---|
| `ConnectionStatus` | `System.Int32` | Is AMS talking to the agent right now. |
| `ConnectionStatusMessage` | `System.String` | The readable form. Select it. |
| `ConnectionStatusTimestamp` | `System.DateTime` | When the connection status last changed. |
| `AgentStatus` | `System.Int32` | Is the agent software itself healthy and current. |
| `AgentStatusMessage`, `AgentStatusTimestamp` | | The readable form and its timestamp. |
| `AgentVersion` | `System.String` | Full version of the agent binaries. |
| `AutoUpdateEnabled` | `System.Boolean` | Whether the agent may be updated without an explicit approval. |
| `ResponseTime` | `System.Int32` | Milliseconds for a data message to go from AMS to the agent and back. |

Platform description, which is what you group by when planning an upgrade:

`OSType`, `OSDistro`, `OSVersion`, `OSArch`, `OSLabel`, `CPUArch`, `Is64Windows`,
`NetFrameworkRelease`, and the three `Runtime...` variants `RuntimeOSDistro`,
`RuntimeOSVersion` and `RuntimeOSLabel`. The distinction matters on Linux: the schema says
`OSVersion` is "version of the operating system Linux agent binaries were built for; for a
Windows Agent same as RuntimeOSVersion", while `RuntimeOSVersion` is the OS the agent is
actually running on. An agent built for one distribution and running on another is exactly
what the `installPackageFallbackId` deploy argument produces, and these two columns are how you
find those hosts later.

`Type` is documented as "currently not used and always 0". SolarWinds' Swagger contract
defines an `AgentType` enum with `FullFeaturedAgent`, `LinuxDPIProbe` and `RemoteCollector`,
so the column looks like a placeholder for a distinction the `PromoteAgentToRemoteCollector`
verb makes. Do not filter on it.

`OrionIdColumn` is internal presentation plumbing.

### Relationships

```
Orion.Nodes  --Agent-->  Orion.AgentManagement.Agent  --Plugins-->  Orion.AgentManagement.AgentPlugin
Orion.Engines --Agents-->               |
                                        +--Probe-->      Orion.NetPath.Probes
                                        +--Engine-->     Orion.Engines
                                        +--Node-->       Orion.Nodes
                                        +--LogProfiles-> Orion.OLM.LogProfile
```

`Plugins` is a `System.Hosting` relationship, so plugins belong to the agent and are addressed
underneath it. `Node` and `Engine` are references, and both are navigable from the agent even
though the schema lists them under target relationships: see
[../swql/joins-and-navigation.md](../swql/joins-and-navigation.md).

`Orion.Nodes.Agent` is the reverse, and it is the join most reports actually want, because it
lets one query show the node's status and the agent's status side by side. Query 6 does that.

## The two status columns, and why they disagree with each other

This is the part of the module that produces the most confused tickets, so it is worth being
precise. There are **two** independent integers, and they answer different questions.

**`ConnectionStatus` answers "can AMS talk to this agent".** SolarWinds documents the values on
the [Agents](https://solarwinds.github.io/OrionSDK/docs/agents/) page:

| Value | Meaning |
|---:|---|
| 0 | Unknown |
| 1 | Ok |
| 2 | ServiceNotResponding |
| 3 | DeploymentPending |
| 4 | DeploymentInProgress |
| 5 | DeploymentFailed |
| 6 | InvalidResponse |
| 7 | WaitingForConnection |

The 2026.2 Swagger contract lists the same names in the same order and adds one more,
`Connecting`, at the end, which is consistent with `8` being that value.

**`AgentStatus` answers "is the agent software healthy and current".** The same SolarWinds page
gives:

| Value | Meaning |
|---:|---|
| 0 | Unknown |
| 1 | Ok |
| 2 | UpdateAvailable |
| 3 | UpdateInProgress |
| 4 | UpdateFailed |
| 5 | RebootRequired |
| 6 | RebootInProgress |
| 7 | RebootFailed |
| 8 | PluginUpdatePending |

**The published documentation and the published contract disagree on this one.** The 2026.2
Swagger `AgentStatus` enum lists, in order: `Unknown`, `Ok`, `UpdateAvailable`,
`UpdateInProgress`, `RebootRequired`, `RebootInProgress`, `RebootFailed`,
`PluginUpdatePending`, `UninstallInProgress`, `AgentUninstalled`, `PluginErrorOccurred`,
`AgentRestartInProgress`, `AgentRestartFailed`. It has no `UpdateFailed` at all, and it carries
five states the docs page does not mention. If the contract's order is the integer order, then
everything from `4` upward is shifted by one relative to the table above. Which of the two is
right for your release **cannot be verified here**, because the Swagger enum is declared as a
string enum and does not carry the integers.

Resolve it on your own server rather than guessing, by reading the number next to the message
the platform itself renders:

```sql
SELECT a.AgentStatus, a.AgentStatusMessage, COUNT(a.AgentId) AS Agents
FROM Orion.AgentManagement.Agent a
GROUP BY a.AgentStatus, a.AgentStatusMessage
ORDER BY a.AgentStatus
```

That query is the general answer to every "what does this integer mean" question in this
module, and it is why `ConnectionStatusMessage` and `AgentStatusMessage` are worth selecting in
every report. The safe filters are the ones that do not depend on the disputed range:
`ConnectionStatus <> 1` for "not connected", and `AgentStatus NOT IN (0, 1)` for "the agent
itself has something to say".

Note that neither column is a platform status code. Do not join `Orion.StatusInfo` to them;
that table maps the node and interface status values documented in
[../reference/status-codes.md](../reference/status-codes.md), and the numbers happen to
overlap while meaning something completely different.

## Plugins

A plugin is what makes an agent useful. The agent binary itself moves messages; the plugins
collect. `Orion.AgentManagement.AgentPlugin` is one row per plugin per agent:

| Property | Type | Notes |
|---|---|---|
| `AgentId` | `System.Int32` | The agent. Navigate back with `Agent`. |
| `PluginId` | `System.String` | The plugin's type identifier, not a number. |
| `Version` | `System.String` | Plugin version, which drifts independently of `AgentVersion`. |
| `Status` | `System.Int32` | Plugin status. |
| `StatusMessage` | `System.String` | The readable form. |
| `LastChange` | `System.DateTime` | When the plugin's state last changed. |

The `Status` integers for a plugin are **not documented in the published schema** and are not
verified here; read `StatusMessage` alongside the number and build the mapping for your release
with the same `GROUP BY` shape shown above.

**The valid `PluginId` values are installation data, not schema.** They depend on which modules
are licensed and which packages the AMS repository holds, so this repository cannot enumerate
them. The platform will tell you:

```powershell
Invoke-SwisVerb $swis 'Orion.AgentManagement.Agent' `
    'GetLicensedAgentPluginsInAMSRepository' @($pollingEngineId)
```

That verb returns the list of plugin ids in the AMS repository on that engine that are licensed,
which is precisely the set `DeployPlugin` will accept. Calling it first turns three plugin verbs
from guesswork into a lookup. The alternative, if you already have agents doing what you want,
is to read the ids off them:

```sql
SELECT p.PluginId, p.Version, COUNT(p.AgentId) AS AgentCount
FROM Orion.AgentManagement.AgentPlugin p
GROUP BY p.PluginId, p.Version
ORDER BY p.PluginId, p.Version
```

Three verbs operate on plugins, all taking `(agentId, pluginId)` and all returning
`System.Void`: `DeployPlugin`, `RedeployPlugin` and `UninstallPlugin`. `RedeployPlugin` is the
repair operation for a plugin that installed but is not working, and it is the one to reach for
before uninstalling and reinstalling, because it does not disturb the agent's registration.

## Proxies

`Orion.AgentManagement.Proxy` is four properties describing an HTTP proxy that agent-to-AMS
traffic goes through:

| Property | Type | Notes |
|---|---|---|
| `ProxyId` | `System.Int32` | The key. `Orion.AgentManagement.Agent.ProxyId` points at it. |
| `ProxyUrl` | `System.String` | The proxy URL. |
| `UseProxyAuthentication` | `System.Boolean` | Whether the proxy needs credentials. |
| `ProxyCredentialId` | `System.Int32` | The `Orion.Credential` row holding them. |

There is no navigation property between an agent and its proxy in either direction, so joining
them is a manual join on `ProxyId`. The entity carries two verbs of its own, and both take the
engine as their first argument because a proxy is defined per polling engine:

| Verb | Signature | Returns |
|---|---|---|
| `AddProxy` | `(pollingEngineId, proxy)` | number |
| `DeleteProxy` | `(pollingEngineId, proxyId)` | boolean |

The `proxy` argument is a `SolarWinds.AgentManagement.Common.Models.ProxySetting` object,
which the Swagger contract defines as exactly the four properties above. In PowerShell that is
a hashtable:

```powershell
$newProxyId = Invoke-SwisVerb $swis 'Orion.AgentManagement.Proxy' 'AddProxy' @(
    1,
    @{
        ProxyId                = 0
        ProxyUrl               = 'http://proxy.example.com:3128'
        UseProxyAuthentication = $true
        ProxyCredentialId      = $credentialId
    }
)
```

`ProxyCredentialId` refers to a row in `Orion.Credential`, which exposes no secret material
through the query interface. See [../automation/credentials.md](../automation/credentials.md).

## The agent lifecycle

Four phases, and each one is a different set of verbs.

### 1. Deploy

Three ways in, and the choice is about what you already have.

| Verb | Use it when | Signature |
|---|---|---|
| `Deploy` | The machine is not in Orion yet. This creates the node too. | `(pollingEngineId, agentName, hostname, ipAddress, machineUserName, machinePassword, additionalUsername?, additionalPassword?, passwordIsPrivateKey?, privateKeyPassword?, agentMode?, installPackageFallbackId?)` |
| `DeployToNode` | The node already exists and you are converting it from SNMP or WMI. | `(nodeId, machineUserName?, machinePassword?, additionalUsername?, additionalPassword?, passwordIsPrivateKey?, privateKeyPassword?, agentMode?, installPackageFallbackId?)` |
| `AddPassiveAgent` | The agent was installed by hand or by your configuration management, and now has to be registered. | `(agentName, agentHostname, agentIpAddress, agentPort, pollingEngineId, sharedSecret, proxyId, autoUpdateEnabled?, testPassiveAgentConnection?)` |

Both `Deploy` and `DeployToNode` return a number. SolarWinds' page declares the C# signature as
returning `int`. What the integer identifies is **not documented in the published schema**, so
this page does not assert that it is the new `AgentId`. Confirm the result by querying for the
agent rather than by trusting the return value; query 2 below is written for exactly that.

Six of `Deploy`'s twelve arguments are optional, four of them covering Linux authentication and
the last two the connection mode and the install package, and they only make sense together.
SolarWinds'
[`DeployAgentViaVerb.ps1`](https://github.com/solarwinds/OrionSDK/blob/master/Samples/PowerShell/DeployAgentViaVerb.ps1)
sample documents each one; the combinations it shows are:

| Scenario | Arguments beyond the first six |
|---|---|
| Windows or Linux with a password | none |
| Linux needing `sudo` under a different account | `additionalUsername`, `additionalPassword` |
| Linux with an SSH key, unprotected | `additionalUsername`, `additionalPassword`, `passwordIsPrivateKey = $true`, with the PEM key passed as `machinePassword` |
| Linux with an SSH key, passphrase protected | the above plus `privateKeyPassword` |
| Force a connection mode | the above plus `agentMode` |
| Unsupported Linux distribution | the above plus `installPackageFallbackId` |

Two of those deserve expanding.

**`passwordIsPrivateKey` changes what `machinePassword` means.** When it is `$true`, the
`machinePassword` argument is not a password: it is the private key itself, in PEM format,
newlines and all. `privateKeyPassword` is then the passphrase protecting that key, and is only
consulted when `passwordIsPrivateKey` is true.

**`installPackageFallbackId` is a real lookup, not a guess.** The sample tells you to find the
value in the `AgentManagement_InstallPackages` database table, which you should not be reading
directly. SWIS exposes the same data as `Orion.AgentManagement.InstallPackage`, so ask for it
properly:

```sql
SELECT
    ip.PackageId, ip.Name, ip.OsType, ip.OsDistro, ip.OsVersion,
    ip.OsArchitecture, ip.PackageType, ip.PackageManagementTool
FROM Orion.AgentManagement.InstallPackage ip
WHERE ip.OsDistro = @distro
ORDER BY ip.OsVersion, ip.OsArchitecture
```

The sample's example value, `centos-7.1-x64`, shows the `<distro>-<version>-<arch>` shape, and
the query above returns the ones your AMS actually holds.

**`agentMode` takes the same integers as the `Mode` property**: `0` auto-detect, `1` force
active, `2` force passive. The Swagger contract's `AgentMode` enum is `Auto`, `Active`,
`Passive` in that order, which agrees with both the schema property description and the
sample's comment.

### Validate credentials before you deploy

`ValidateDeploymentCredentials` takes the same arguments as `Deploy` minus `agentName` and
`agentMode`, and does the connection test without installing anything. It is the cheap way to
find out that the sudo password is wrong before you have half-deployed to two hundred hosts.

It returns a four-value tuple. SolarWinds documents the members on the
[Agents](https://solarwinds.github.io/OrionSDK/docs/agents/) page: a boolean saying whether
the credentials are valid, a string carrying the error message when they are not, an integer
saying whether an agent is already installed on that machine (values from their
`AgentDetectionInfo` enum), and an integer failure code (from their `DeploymentFailureReason`
enum). The two enums' members are not published in the schema or the Swagger contract and are
**not verified here**; the boolean and the string are the parts to act on.

The third value is the one worth checking even on success, because it tells you the machine is
already monitored by *some* Orion server, possibly not yours.

### A deployment script with the checks the sample leaves out

SolarWinds' sample is deliberately a catalogue of argument combinations rather than a runnable
script. This is one scenario, end to end, with the parts that keep it safe to run unattended:
a duplicate check, credential validation, a confirmation prompt, and a wait that watches the
agent appear rather than assuming it did.

```powershell
# Deploy an agent to one Linux host and wait for it to connect.
# Requires manageNodes. Credentials travel in the verb arguments, so use HTTPS
# and do not write the argument array to a log.
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
    [Parameter(Mandatory)][string]$AgentName,
    [Parameter(Mandatory)][string]$Hostname,
    [Parameter(Mandatory)][string]$IPAddress,
    [Parameter(Mandatory)][pscredential]$MachineCredential,
    [int]$EngineId = 1,
    [string]$SudoUser,
    [string]$SudoPassword,
    [int]$AgentMode = 0,
    [string]$InstallPackageFallbackId,
    [string]$OrionHost = 'orion.example.com'
)

Import-Module SwisPowerShell
$swis = Connect-Swis -Hostname $OrionHost -Credential (Get-Credential)

# 1. Refuse to deploy on top of an agent that is already there.
$existing = Get-SwisData $swis @'
SELECT a.AgentId, a.Name, a.Hostname, a.IP, a.ConnectionStatusMessage
FROM Orion.AgentManagement.Agent a
WHERE a.Hostname = @hostname OR a.IP = @ip
'@ @{ hostname = $Hostname; ip = $IPAddress }

if ($existing) {
    throw "AgentId $($existing.AgentId) already covers $Hostname / $IPAddress."
}

$user = $MachineCredential.UserName
$pass = $MachineCredential.GetNetworkCredential().Password

# 2. Test the credentials before installing anything.
$check = Invoke-SwisVerb $swis 'Orion.AgentManagement.Agent' 'ValidateDeploymentCredentials' @(
    $EngineId, $Hostname, $IPAddress, $user, $pass,
    $SudoUser, $SudoPassword, $false, $null, $InstallPackageFallbackId
)
Write-Host "Credential check returned: $($check.InnerXml)"

# 3. Deploy, with -WhatIf support so a dry run prints the target and stops.
if (-not $PSCmdlet.ShouldProcess("$AgentName ($Hostname / $IPAddress)", 'Deploy agent')) {
    return
}

Invoke-SwisVerb $swis 'Orion.AgentManagement.Agent' 'Deploy' @(
    $EngineId,                  # pollingEngineId
    $AgentName,                 # agentName
    $Hostname,                  # hostname
    $IPAddress,                 # ipAddress
    $user,                      # machineUserName
    $pass,                      # machinePassword
    $SudoUser,                  # additionalUsername
    $SudoPassword,              # additionalPassword
    $false,                     # passwordIsPrivateKey
    $null,                      # privateKeyPassword
    $AgentMode,                 # agentMode
    $InstallPackageFallbackId   # installPackageFallbackId
) | Out-Null

# 4. Watch the agent appear and connect. Deploy is asynchronous.
$deadline = (Get-Date).AddMinutes(15)
do {
    Start-Sleep -Seconds 15
    $agent = Get-SwisData $swis @'
SELECT TOP 1
    a.AgentId, a.Name, a.AgentVersion,
    a.ConnectionStatus, a.ConnectionStatusMessage,
    a.AgentStatus, a.AgentStatusMessage, a.NodeId
FROM Orion.AgentManagement.Agent a
WHERE a.Hostname = @hostname OR a.IP = @ip
'@ @{ hostname = $Hostname; ip = $IPAddress }

    if ($agent) {
        Write-Host "AgentId $($agent.AgentId): $($agent.ConnectionStatusMessage)"
    } else {
        Write-Host 'no agent record yet'
    }
} while ((-not $agent -or $agent.ConnectionStatus -ne 1) -and (Get-Date) -lt $deadline)

if (-not $agent -or $agent.ConnectionStatus -ne 1) {
    throw "Agent did not reach connected state within the timeout."
}

Write-Host "Deployed AgentId $($agent.AgentId) on NodeID $($agent.NodeId), version $($agent.AgentVersion)."
```

Two details in there are not cosmetic. **The positional array is padded with `$null` for the
optional arguments you are not using**, because these are positional slots and skipping one
shifts every later value into the wrong parameter. And **the wait loop polls the entity rather
than the return value**, because `Deploy` queues work on the polling engine: a successful
response means the request was accepted, not that an agent exists.

The same flow in Python, for an existing node being converted from WMI:

```python
import time
from orionsdk import SwisClient

swis = SwisClient(
    "orion.example.com", "svc-automation", password,
    verify="/etc/ssl/certs/orion-swis.pem",
)

node_id = 42

already = swis.query(
    "SELECT AgentId, Name FROM Orion.AgentManagement.Agent WHERE NodeId = @id",
    id=node_id,
)["results"]
if already:
    raise SystemExit(f"NodeID {node_id} already has AgentId {already[0]['AgentId']}")

swis.invoke(
    "Orion.AgentManagement.Agent", "DeployToNode",
    node_id,          # nodeId
    "EXAMPLE\\svc-agent",  # machineUserName
    machine_password, # machinePassword
    None,             # additionalUsername
    None,             # additionalPassword
    False,            # passwordIsPrivateKey
    None,             # privateKeyPassword
    0,                # agentMode: auto-detect
    None,             # installPackageFallbackId
)

deadline = time.time() + 900
while time.time() < deadline:
    time.sleep(15)
    rows = swis.query(
        "SELECT AgentId, ConnectionStatus, ConnectionStatusMessage, AgentVersion "
        "FROM Orion.AgentManagement.Agent WHERE NodeId = @id",
        id=node_id,
    )["results"]
    if rows:
        print(rows[0]["ConnectionStatusMessage"])
        if rows[0]["ConnectionStatus"] == 1:
            break
else:
    raise SystemExit("agent did not connect in time")
```

### 2. Connect

Once deployed, the connection is either agent-initiated or server-initiated, and that decision
changes which of your firewall rules matters.

**Active, or agent-initiated.** `Mode = 1`, `IsActiveAgent = TRUE`. The agent opens the
connection to AMS on its assigned polling engine, optionally through `ProxyId`. Nothing needs
to reach in. This is the mode that makes agents useful across NAT and into cloud accounts.

**Passive, or server-initiated.** `Mode = 2`, `IsActiveAgent = FALSE`. AMS connects to
`PassiveAgentHostname` on `PassiveAgentPort`. You need an inbound rule and a stable address for
the agent, and in exchange the agent holds no outbound connection.

Passive agents are also the ones you register rather than deploy. `AddPassiveAgent` exists for
the case where the agent software was installed by your configuration management system and now
has to be introduced to Orion. Its `sharedSecret` argument is the value configured on the agent
side, and `testPassiveAgentConnection` makes the call verify reachability before it commits:

```powershell
$agentId = Invoke-SwisVerb $swis 'Orion.AgentManagement.Agent' 'AddPassiveAgent' @(
    'app-server-07',        # agentName
    'app-server-07.example.com',  # agentHostname
    '10.20.30.40',          # agentIpAddress
    17790,                  # agentPort
    1,                      # pollingEngineId
    $sharedSecret,          # sharedSecret
    0,                      # proxyId: 0 for none
    $true,                  # autoUpdateEnabled
    $true                   # testPassiveAgentConnection
)
```

The `agentPort` value above is an example, not a documented default: the port a passive agent
listens on is installation configuration and is **not recorded in the published schema**. Read
it off an existing passive agent's `PassiveAgentPort`, or from the agent's own configuration,
before you script this.

`TestPassiveAgentConnection(agent)` does the same reachability test on its own. It takes a
whole `AgentRecord` object rather than an id, and returns an `AgentPingResult` which the
Swagger contract defines as `Success`, `ResponseTime`, `Agent`, `ErrorMessage`,
`RebootPending`, `NetFrameworkRelease`, `PkgOsDistro` and `PkgOsVersion`.

**`AddAgent(agent)` and `UpdateAgent(agent, updateRemoteSettings)` are the low-level pair
underneath `AddPassiveAgent`.** Both take a full
`SolarWinds.AgentManagement.Contract.Models.AgentRecord`, whose fields the Swagger contract
lists and which is close to, but not identical with, the entity's property set. It adds
thirteen fields the entity does not have — `PollingEngineName`, `PollingEngineIP`,
`PollingEnginePort`, `LogLevel`, `AgentStatusData`, `PkgOsDistro`, `PkgOsVersion`, `Password`,
`JobTimeout`, `JobFrequency`, `DetailsUrl`, `OrionStatus` and `AgentEndpointId` — and it spells
the timestamps `ConnectionStatusTimeStamp` and `AgentStatusTimeStamp` with a capital S where
the entity uses `ConnectionStatusTimestamp` and `AgentStatusTimestamp`.
Prefer `AddPassiveAgent`, which SolarWinds describes as existing "for usability convenience".

### 3. Update

An agent has a version, and keeping several hundred of them current is the ongoing cost of
choosing agents. Two properties and one verb govern it.

`AutoUpdateEnabled` decides whether the platform may update the agent without asking.
`AgentStatus` reports where an agent is in the update cycle. `ApproveUpdate(agentId)` is the
approval, and it returns `System.Void`, so as always you confirm by watching the entity rather
than by reading the response.

```powershell
# Approve every agent that is reporting an available update.
$pending = Get-SwisData $swis @'
SELECT a.AgentId, a.Name, a.AgentVersion, a.AgentStatusMessage
FROM Orion.AgentManagement.Agent a
WHERE a.AgentStatus = 2
'@

$pending | Format-Table AgentId, Name, AgentVersion, AgentStatusMessage
Write-Warning "About to approve updates on $($pending.Count) agent(s)."

foreach ($a in $pending) {
    if ($PSCmdlet.ShouldProcess($a.Name, 'ApproveUpdate')) {
        Invoke-SwisVerb $swis 'Orion.AgentManagement.Agent' 'ApproveUpdate' @($a.AgentId) | Out-Null
    }
}
```

The `AgentStatus = 2` filter is `UpdateAvailable` under SolarWinds' published table, and `2` is
the same value under the Swagger ordering too, which is why this particular filter is safe
despite the disagreement described above. Anything above `3` is not.

`ApproveReboot(agentId)` is the sibling for the case where the update needs the machine
restarted, and it returns a boolean. Treat it with more care than `ApproveUpdate`: approving a
reboot reboots a production server. `RestartAgent(agentId)` restarts only the agent service,
which is the far smaller hammer and the right first thing to try when an agent is connected but
a plugin is misbehaving.

`CollectDiagnostics` is the escalation path before you open a support case:

| Parameter | Type | Notes |
|---|---|---|
| `agentId` | number | required |
| `pathToStoreAgentDiagnostics` | string | required. A path the **Orion server** can write to, not the agent. |
| `diagnosticCollectionTimeoutInMinutes` | number | required. The call waits up to this long. |
| `areAgentLogsSelected` | boolean | optional |
| `areEventLogsSelected` | boolean | optional |
| `isNetStatSelected` | boolean | optional |
| `areRunningProcessesSelected` | boolean | optional |

It returns a boolean and it blocks, so give the timeout a realistic value and do not put it in
a tight loop over every agent.

### 4. Move, or remove

**Moving an agent between polling engines is a two-call sequence, and skipping the first call
is how you lose an agent.** SolarWinds says this plainly on the Agents page: if you reassign an
agent and a firewall blocks the new path, Orion cannot undo the change, because it can no longer
talk to the agent.

```powershell
$agentId  = 17
$targetEngineId = 3

if (-not (Invoke-SwisVerb $swis 'Orion.AgentManagement.Agent' 'TestWithEngine' `
            @($agentId, $targetEngineId))) {
    throw "Agent $agentId cannot reach engine $targetEngineId. Not moving it."
}

Invoke-SwisVerb $swis 'Orion.AgentManagement.Agent' 'AssignToEngine' `
    @($agentId, $targetEngineId) | Out-Null
```

Both verbs name their second parameter `pollerId`, and it is an **engine id**, matching
`Orion.Engines.EngineID` and `Orion.AgentManagement.Agent.PollingEngineId`. It is not a
`Orion.Pollers.PollerID`. The two are unrelated and the name collision is a genuine trap; see
[../automation/pollers.md](../automation/pollers.md) for what `Orion.Pollers` actually is.

SolarWinds also documents one behaviour of `TestWithEngine` that matters for scripting it:
**it returns `true` immediately if you pass the engine the agent is already assigned to**,
whether or not the agent is currently reachable. So it is a test of a *prospective* path, not a
health check. For health, read `ConnectionStatus` and `AgentStatus`.

`AssignToEngine` is also the closest thing the platform has to a node-level engine reassignment
verb. For a node that is not agent-managed, moving it is a CRUD update of `EngineID`:
[../automation/node-management.md](../automation/node-management.md#reassigning-a-node-to-a-different-polling-engine).

**Removal is two different verbs and they are not interchangeable.**

| Verb | What it does | Returns |
|---|---|---|
| `Uninstall(agentId)` | Removes the agent software from the target machine. | boolean |
| `Delete(agentId)` | Makes Orion forget the agent. The software stays installed on the target. | `System.Void` |

SolarWinds' own wording for `Delete` is that it "causes the Orion server to abandon and forget
about the specified agent". Use it when the machine is already gone, or when the agent is
being handed to another Orion deployment. Use `Uninstall` when the machine is staying and the
monitoring is not. Calling `Delete` on a live machine leaves a running agent with nowhere to
report, which is the state that produces a mystery service on a server two years later.

`PromoteAgentToRemoteCollector(agentId)` is the fifth lifecycle operation and the schema
records no description for it. It returns `System.Void`. What it does to an agent, and whether
it is reversible, is **not documented in the published schema** and is not verified here. Do not
call it from a script on the strength of this page.

## The verbs, in full

All 20, with the parameter order that is the entire contract. Regenerate for your version with
`python3 tools/schema_query.py verbs --entity Orion.AgentManagement.Agent`.

| Verb | Signature | Returns |
|---|---|---|
| `Deploy` | `(pollingEngineId, agentName, hostname, ipAddress, machineUserName, machinePassword, additionalUsername?, additionalPassword?, passwordIsPrivateKey?, privateKeyPassword?, agentMode?, installPackageFallbackId?)` | number |
| `DeployToNode` | `(nodeId, machineUserName?, machinePassword?, additionalUsername?, additionalPassword?, passwordIsPrivateKey?, privateKeyPassword?, agentMode?, installPackageFallbackId?)` | number |
| `ValidateDeploymentCredentials` | `(pollingEngineId, hostname, ipAddress, machineUserName, machinePassword, additionalUsername?, additionalPassword?, passwordIsPrivateKey?, privateKeyPassword?, installPackageFallbackId?)` | `Tuple<bool, string, int, int>` |
| `AddAgent` | `(agent)` | number |
| `AddPassiveAgent` | `(agentName, agentHostname, agentIpAddress, agentPort, pollingEngineId, sharedSecret, proxyId, autoUpdateEnabled?, testPassiveAgentConnection?)` | number |
| `UpdateAgent` | `(agent, updateRemoteSettings)` | `System.Void` |
| `TestPassiveAgentConnection` | `(agent)` | `AgentPingResult` |
| `TestWithEngine` | `(agentId, pollerId)` | boolean |
| `AssignToEngine` | `(agentId, pollerId)` | boolean |
| `DeployPlugin` | `(agentId, pluginId)` | `System.Void` |
| `RedeployPlugin` | `(agentId, pluginId)` | `System.Void` |
| `UninstallPlugin` | `(agentId, pluginId)` | `System.Void` |
| `GetLicensedAgentPluginsInAMSRepository` | `(pollingEngineId)` | array of string |
| `ApproveUpdate` | `(agentId)` | `System.Void` |
| `ApproveReboot` | `(agentId)` | boolean |
| `RestartAgent` | `(agentId)` | boolean |
| `CollectDiagnostics` | `(agentId, pathToStoreAgentDiagnostics, diagnosticCollectionTimeoutInMinutes, areAgentLogsSelected?, areEventLogsSelected?, isNetStatSelected?, areRunningProcessesSelected?)` | boolean |
| `PromoteAgentToRemoteCollector` | `(agentId)` | `System.Void` |
| `Uninstall` | `(agentId)` | boolean |
| `Delete` | `(agentId)` | `System.Void` |

**None of the 20 declares a required right of its own.** The rights come from the entity's
access control, where `invoke` appears in exactly one row:

| Operations | Required right |
|---|---|
| `read` | `everyone` |
| `create`, `read`, `update`, `delete` | `admin` |
| `create`, `read`, `update`, `delete`, `invoke` | `manageNodes` |

So **invoking any agent verb requires `manageNodes`**. An account with `admin` but without
`manageNodes` can read and write agent rows through CRUD and cannot deploy anything, which is
a distinction worth knowing before you debug a 403. `Orion.AgentManagement.AgentPlugin` and
`Orion.AgentManagement.Proxy` declare the same three rows;
`Orion.AgentManagement.InstallPackage` is read-only for `everyone`.

Note also that the entity declares full CRUD, so a create or an update against
`Orion.AgentManagement.Agent` will be accepted. What the platform does with an agent row
written that way, as opposed to one produced by `Deploy` or `AddAgent`, is **not documented in
the published schema** and is not verified here. Use the verbs.

## Worked queries

Every query below was validated against the 2026.2 schema with
`python3 tools/validate_swql.py`.

### 1. The agent inventory

```sql
SELECT
    a.AgentId, a.Name, a.Hostname, a.DNSName, a.IP, a.AgentVersion,
    a.Mode, a.IsActiveAgent, a.ConnectionStatus, a.ConnectionStatusMessage,
    a.AgentStatus, a.AgentStatusMessage, a.RegisteredOn,
    a.Node.Caption AS NodeCaption, a.Engine.ServerName AS PollingEngine
FROM Orion.AgentManagement.Agent a
ORDER BY a.Name
```

The two navigation properties are what make this useful: `a.Node.Caption` gives you the name the
rest of Orion knows the machine by, which is often not `a.Name`, and `a.Engine.ServerName` names
the AMS the agent is talking to. Both status integers are selected next to their message
columns, for the reason described above.

### 2. Agents that are not connected

The query to put on a dashboard, because an agent that is not connected is a monitoring gap
that nothing else reports.

```sql
SELECT
    a.AgentId, a.Name, a.Hostname, a.IP,
    a.ConnectionStatus, a.ConnectionStatusMessage, a.ConnectionStatusTimestamp,
    a.AgentStatus, a.AgentStatusMessage,
    a.PollingEngineId, a.Engine.ServerName AS PollingEngine,
    a.Node.NodeID, a.Node.Caption AS NodeCaption, a.Node.Status AS NodeStatus
FROM Orion.AgentManagement.Agent a
WHERE a.ConnectionStatus <> 1
ORDER BY a.ConnectionStatusTimestamp
```

`<> 1` rather than a list of bad values, because the disputed enum makes an exclusion filter
safer than an inclusion one: `1` is `Ok` in both the documentation and the contract, so
"anything else" is correct under either reading. `ORDER BY ConnectionStatusTimestamp` ascending
puts the longest-standing failures first, which is the opposite of what a freshness sort would
do and the right order for a work queue.

Selecting `a.Node.Status` alongside is the fastest triage step there is. If the node is down
too, the machine is off and the agent is a symptom. If the node is up and the agent is not
connected, the machine is fine and something between the agent and AMS is not.

Grouping the same set by engine tells you whether the problem is one host or one AMS:

```sql
SELECT
    a.Engine.ServerName AS PollingEngine,
    a.ConnectionStatusMessage,
    COUNT(a.AgentId) AS Agents
FROM Orion.AgentManagement.Agent a
WHERE a.ConnectionStatus <> 1
GROUP BY a.Engine.ServerName, a.ConnectionStatusMessage
ORDER BY COUNT(a.AgentId) DESC
```

Every agent on one engine failing at once is an AMS or firewall problem on that engine, not two
hundred host problems.

### 3. Agents needing an update

```sql
SELECT
    a.AgentId, a.Name, a.AgentVersion, a.AutoUpdateEnabled,
    a.AgentStatus, a.AgentStatusMessage, a.AgentStatusTimestamp,
    a.OSType, a.OSLabel, a.RuntimeOSLabel, a.Engine.ServerName AS PollingEngine
FROM Orion.AgentManagement.Agent a
WHERE a.AgentStatus = 2
ORDER BY a.AgentStatusTimestamp
```

This is the input to the `ApproveUpdate` loop above. `AutoUpdateEnabled` is the column that
explains why a given agent is sitting here: an agent with auto-update on should not linger in
`UpdateAvailable`, so one that does is telling you the update is failing rather than waiting.

`AgentStatusTimestamp` ascending again puts the oldest first. An agent that has been
`UpdateAvailable` for a month is a different problem from one that noticed an update this
morning.

### 4. Version and platform spread

The planning query before an upgrade.

```sql
SELECT a.AgentVersion, a.OSType, a.CPUArch, COUNT(a.AgentId) AS AgentCount
FROM Orion.AgentManagement.Agent a
GROUP BY a.AgentVersion, a.OSType, a.CPUArch
ORDER BY COUNT(a.AgentId) DESC
```

`AgentVersion` is a `System.String`, so it sorts lexically and `10.2` sorts before `9.1`. Group
and count rather than trying to find "the oldest version" with `MIN`.

For the Linux estate specifically, the build-target versus runtime distinction is the one that
catches people:

```sql
SELECT
    a.AgentId, a.Name, a.OSDistro, a.OSVersion,
    a.RuntimeOSDistro, a.RuntimeOSVersion, a.RuntimeOSLabel, a.AgentVersion
FROM Orion.AgentManagement.Agent a
WHERE a.OSType = 'Linux'
ORDER BY a.RuntimeOSDistro, a.RuntimeOSVersion
```

Rows where `OSDistro` and `RuntimeOSDistro` differ are hosts deployed with an
`installPackageFallbackId`, running a package built for something else. They work, and they are
the first ones to break on a distribution upgrade.

### 5. Plugins on one agent, and plugin spread across the estate

```sql
SELECT
    p.AgentId, p.Agent.Name AS AgentName, p.PluginId, p.Version,
    p.Status, p.StatusMessage, p.LastChange
FROM Orion.AgentManagement.AgentPlugin p
WHERE p.AgentId = @agentId
ORDER BY p.PluginId
```

When an agent is connected but one module's data has stopped, this is the query that says which
plugin. `LastChange` is the tell: a plugin whose state changed at the moment the data stopped is
the cause, and one that has not changed in months is not.

Across the estate, an outlier version is usually the explanation for one host behaving
differently:

```sql
SELECT p.PluginId, p.Version, COUNT(p.AgentId) AS AgentCount
FROM Orion.AgentManagement.AgentPlugin p
GROUP BY p.PluginId, p.Version
ORDER BY p.PluginId, p.Version
```

### 6. Agent-managed nodes, with node and agent health together

```sql
SELECT
    n.NodeID, n.Caption, n.IPAddress, n.ObjectSubType, n.Status, si.StatusName,
    n.Agent.AgentId, n.Agent.ConnectionStatus, n.Agent.AgentVersion
FROM Orion.Nodes n
JOIN Orion.StatusInfo si ON n.Status = si.StatusId
WHERE n.ObjectSubType = 'Agent'
ORDER BY n.Caption
```

`Orion.Nodes.ObjectSubType` carries no documented value set of its own, but the sibling property
`Orion.NPM.Interfaces.ObjectSubType` is documented in the schema as "String representation of
object sub type: None, SNMP, WMI, ICMP, Agent", and the samples confirm `SNMP`, `WMI` and
`ICMP` on nodes. `Agent` on a node is therefore inferred from the sibling entity rather than
verified directly; if it returns nothing on your server, check what the values actually are
with `SELECT ObjectSubType, COUNT(NodeID) FROM Orion.Nodes GROUP BY ObjectSubType`.

The `Orion.StatusInfo` join is there because `n.Status` is a platform status code and does map
to that table, unlike the two agent status columns.

### 7. Agents per polling engine

Run this before `AssignToEngine`, so you are moving agents toward the engine with room rather
than away from it.

```sql
SELECT e.EngineID, e.ServerName, COUNT(a.AgentId) AS AgentCount
FROM Orion.AgentManagement.Agent a
JOIN Orion.Engines e ON a.PollingEngineId = e.EngineID
GROUP BY e.EngineID, e.ServerName
ORDER BY COUNT(a.AgentId) DESC
```

The join is on `PollingEngineId`, not `EngineID`: the agent entity spells it with a lowercase
`d`, and `Orion.Engines` spells its key `EngineID`. Pair this with the engine load queries in
[../automation/pollers.md](../automation/pollers.md#deciding-where-the-load-should-go), because
agent count on its own is not load.

### 8. Passive agents and the proxies they use

```sql
SELECT
    a.AgentId, a.Name, a.Mode, a.IsActiveAgent,
    a.PassiveAgentHostname, a.PassiveAgentPort, a.ProxyId,
    a.ConnectionStatus, a.ConnectionStatusMessage
FROM Orion.AgentManagement.Agent a
WHERE a.IsActiveAgent = FALSE
ORDER BY a.Name
```

These are the agents whose firewall requirements run inbound, so they are the ones a network
change is most likely to break. `IsActiveAgent = FALSE` rather than `Mode = 2`, because an
agent deployed with `agentMode = 0` settles into a mode at install time and the boolean reflects
where it ended up.

The proxies themselves:

```sql
SELECT x.ProxyId, x.ProxyUrl, x.UseProxyAuthentication, x.ProxyCredentialId
FROM Orion.AgentManagement.Proxy x
ORDER BY x.ProxyId
```

There is no navigation between the two entities, so match `a.ProxyId` to `x.ProxyId` yourself.

### 9. Who deployed or removed an agent, and when

```sql
SELECT TOP 100
    ae.AuditEventID, ae.TimeLoggedUtc, ae.AccountID, ae.AuditEventMessage,
    ae.NetObjectType, ae.NetObjectID
FROM Orion.AuditingEvents ae
WHERE ae.TimeLoggedUtc >= @startUtc
ORDER BY ae.TimeLoggedUtc DESC
```

`Orion.AuditingEvents` is a real table, unlike the `Orion.AgentManagement.Agent*Initiated`
indication types, so this is where the history lives. Time-bound it, because auditing is one of
the larger tables on the system. Add a `ae.AuditEventMessage LIKE '%agent%'` predicate to narrow
it, and see [../automation/events-and-auditing.md](../automation/events-and-auditing.md) for
joining `Orion.AuditingActionTypes` to get a structured action rather than a message string.

### 10. NetPath probes running on agents

```sql
SELECT pr.ProbeID, pr.Name, pr.AgentID, pr.EngineID, pr.Enabled, pr.Status,
       pr.Agent.Name AS AgentName
FROM Orion.NetPath.Probes pr
ORDER BY pr.Name
```

Worth knowing before you uninstall an agent: `Orion.NetPath.Probes` navigates to the agent
through `Agent`, so an agent that looks idle may be the only probe for a NetPath service. See
[npm.md](npm.md) for NetPath, [qoe.md](qoe.md) for QoE probes, which hang off agents the same
way, and [log-analyzer.md](log-analyzer.md) for `Orion.OLM.LogProfile`, which the agent entity
reaches through `LogProfiles`.

## Gotchas

**Two status columns, and neither is a platform status code.** `ConnectionStatus` says whether
AMS can talk to the agent; `AgentStatus` says whether the agent software is healthy and
current. Joining `Orion.StatusInfo` to either produces plausible nonsense, because the numbers
overlap with the node status codes while meaning something else entirely.

**The `AgentStatus` mapping is disputed between SolarWinds' own two sources.** The docs page
gives nine values ending at `8` PluginUpdatePending and includes `UpdateFailed` at `4`; the
2026.2 Swagger enum omits `UpdateFailed`, adds five states at the end, and would shift
everything from `4` upward by one. `0`, `1`, `2` and `3` agree in both. Above that, resolve it
against your own server by grouping `AgentStatus` with `AgentStatusMessage` before you build a
filter or an alert on it.

**`pollerId` on `TestWithEngine` and `AssignToEngine` is an engine id.** It matches
`Orion.Engines.EngineID`, not `Orion.Pollers.PollerID`. The two have nothing to do with each
other and the parameter name is the trap.

**Always call `TestWithEngine` before `AssignToEngine`.** SolarWinds' own documentation warns
that a failed reassignment cannot be undone, because the platform can no longer reach the agent
to move it back. And remember that `TestWithEngine` returns `true` immediately when you pass
the agent's current engine, so a test against the engine it is already on proves nothing.

**`Uninstall` and `Delete` are not synonyms.** `Uninstall` removes the software from the
machine. `Delete` removes the record and leaves the software running on a machine that no
longer has anywhere to report.

**`ApproveReboot` reboots a production server.** `ApproveUpdate` does not, and `RestartAgent`
restarts only the agent service. Reach for them in that order.

**Optional verb arguments are positional slots, not omissible.** `Deploy` has six optional
parameters after the first six. If you want to set `agentMode`, which is eleventh, you must
pass `$null` for `additionalUsername`, `additionalPassword`, `passwordIsPrivateKey` and
`privateKeyPassword` first. Passing fewer arguments does not skip to the one you meant; it
fills the earlier slots. See [../swis/invoke-verbs.md](../swis/invoke-verbs.md).

**Deployment credentials travel in the verb argument array.** They are not stored in
`Orion.Credential` and they are not redacted anywhere. Use HTTPS, which SWIS requires anyway,
and do not log the argument array or pass a password on a command line.

**`passwordIsPrivateKey = $true` changes the meaning of `machinePassword`.** It stops being a
password and becomes the PEM private key itself. `privateKeyPassword` is the passphrase for
that key and is ignored otherwise.

**`PassiveAgentPort` is a `System.String`.** It will not sort or compare numerically, and a
`> 1024` filter on it does something surprising rather than something useful.

**`Deploy` is asynchronous and returns before anything is installed.** A success means the
request was accepted. Confirm by polling `Orion.AgentManagement.Agent` for the hostname or IP
until `ConnectionStatus` reaches `1`, with a deadline.

**An agent is not a `System.ManagedEntity`.** There is no `UnManaged` column and no way to put
an agent into a maintenance window. Unmanage the node instead; see
[../automation/maintenance-mode.md](../automation/maintenance-mode.md).

**The twelve indication entities are events, not tables.** For history, query
`Orion.AuditingEvents`.

**Valid `pluginId` values are installation data.** They depend on licensing and on what the AMS
repository holds, so they are not in the schema. Call
`GetLicensedAgentPluginsInAMSRepository(pollingEngineId)` or read them off existing agents.

**`Orion.SEUM.Agents` is a different thing entirely.** That is the Web Performance Monitor
player, which carries the `L` NetObject prefix and is documented in [wpm.md](wpm.md).
`Orion.Cman.ContainerAgent` is a third unrelated agent concept. `Orion.AgentManagement.Agent`
has **no NetObject prefix at all**, which is why no verb on it takes a `netObjectId`: the twelve
that address an existing agent take a bare `agentId` instead, and the rest identify the target
by hostname, node id, engine id or a whole `AgentRecord`. See
[../reference/netobject-types.md](../reference/netobject-types.md).

**Account limitations filter agents silently.** Two accounts running query 1 legitimately see
different agents, and nothing in the response says so. "The agent is not there" is a
permissions hypothesis before it is a deployment one.

## Related pages

- [../automation/node-management.md](../automation/node-management.md) for the node the agent
  is attached to, and for `DeployToNode`'s starting point.
- [../automation/pollers.md](../automation/pollers.md) for `Orion.Pollers`, which is not what
  the `pollerId` argument means, and for the `N.StatusAndResponseTime.Agent.Native` poller that
  derives node status from agent status.
- [../automation/maintenance-mode.md](../automation/maintenance-mode.md) for unmanaging the
  node, since the agent itself cannot be unmanaged.
- [../automation/credentials.md](../automation/credentials.md) for `Orion.Credential`, which
  `ProxyCredentialId` points at.
- [../automation/events-and-auditing.md](../automation/events-and-auditing.md) for the audit
  trail of deployments and removals.
- [../automation/high-availability.md](../automation/high-availability.md) for what happens to
  an agent's engine assignment when a pool fails over.
- [../swis/invoke-verbs.md](../swis/invoke-verbs.md) for positional arguments and the optional
  parameter trap.
- [../swis/verb-catalog.md](../swis/verb-catalog.md) for the agent verbs alongside every other
  verb in the platform.
- [../swis/metadata-introspection.md](../swis/metadata-introspection.md) for confirming a verb
  signature on a server that is not 2026.2.
- [log-analyzer.md](log-analyzer.md), [qoe.md](qoe.md) and [npm.md](npm.md) for the three
  modules that ride on agent plugins.
- [../reference/verb-index.md](../reference/verb-index.md) for the generated verb table.

## Official SolarWinds documentation

- [Agents](https://solarwinds.github.io/OrionSDK/docs/agents/), which documents the
  `ConnectionStatus` and `AgentStatus` value tables, the C# verb signatures, and the
  `ValidateDeploymentCredentials` return tuple
- [`DeployAgentViaVerb.ps1`](https://github.com/solarwinds/OrionSDK/blob/master/Samples/PowerShell/DeployAgentViaVerb.ps1),
  the annotated catalogue of `Deploy` argument combinations
- [`ImportListResources.ps1`](https://github.com/solarwinds/OrionSDK/blob/master/Samples/PowerShell/ImportListResources.ps1),
  which the Agents page recommends for bulk-updating the resources monitored on agent nodes
- [Orion SDK documentation index](https://solarwinds.github.io/OrionSDK/)

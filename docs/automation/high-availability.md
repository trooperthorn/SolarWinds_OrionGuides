# High availability

High availability in Orion is not database clustering and it is not a load balancer. It is a
much narrower idea: **a pool pairs two servers of the same type so that if one stops being able
to do its job, the other picks up that job.** The job in question is a set of named
responsibilities, and moving them is what a failover is.

The API view of this is unusually clean, because the model is small. There is a pool, there are
members, and there are resources that belong to whichever member is currently active. A
failover is a change of which member holds the resources, and everything else, including the
virtual IP address and the virtual host name that clients follow, is one of those resources.

The other thing worth knowing before you write any of this down: **`Orion.HA.PoolMembers` is
read-only, and every write that configures a pool is a verb on `Orion.HA.Pools` requiring
`admin`.** There is no CRUD path into a pool's membership at all.
`Orion.HA.ResourcesInstances` and `Orion.HA.PoolMemberInterfacesInfo` do declare CRUD under
`admin`, but they are the mechanism's own bookkeeping rather than a supported way to configure
anything; what the platform does with a row written directly into either is **not documented in
the published schema** and is not verified here. Use the verbs. That shape is deliberate, and it
shapes everything on this page.

## Namespaces and how many entities

High availability contributes **9 entities**, all under `Orion.HA.`.

```bash
python3 tools/schema_query.py find "Orion.HA"
python3 tools/schema_query.py show Orion.HA.Pools
python3 tools/schema_query.py verbs --entity Orion.HA.Pools
```

| Entity | Properties | Verbs | Writable | What it is |
|---|---:|---:|---|---|
| `Orion.HA.Pools` | 19 | 13 | `admin` | The pool: its type, its master, its virtual address, its timers |
| `Orion.HA.PoolMembers` | 14 | 0 | **read only** | The servers in a pool and their heartbeat state |
| `Orion.HA.ResourcesInstances` | 7 | 0 | `admin` | The responsibilities that move on failover |
| `Orion.HA.FacilitiesInstances` | 4 | 0 | none declared | The local health signals a member reports |
| `Orion.HA.ReachabilityInfo` | 8 | 0 | none declared | How to reach each server, including virtual names |
| `Orion.HA.PoolMemberInterfacesInfo` | 5 | 0 | `admin` | The IP addresses on each member's interfaces |
| `Orion.HA.PoolAdded` | 2 | 0 | indication | Event: a pool was created |
| `Orion.HA.PoolEdited` | 4 | 0 | indication | Event: a pool was changed, with the members added and removed |
| `Orion.HA.PoolDeleted` | 2 | 0 | indication | Event: a pool was deleted |

The three `...Added`, `...Edited` and `...Deleted` types inherit from `System.Indication`, so
they are events SWIS publishes rather than tables with history in them.
`Orion.HA.PoolEdited` is the most informative of the three, carrying `AddedPoolMembers` and
`DeletedPoolMembers` as strings alongside `PoolId` and `PoolName`. For a durable record of who
changed a pool, use `Orion.AuditingEvents`, which is a real table; see
[events-and-auditing.md](events-and-auditing.md).

Each of the six data entities inherits `Uri`, `DisplayName`, `Description`, `InstanceType` and
`InstanceSiteId` from `System.Entity` on top of what it declares. None of them is a
`System.ManagedEntity`, so nothing in this module can be put into a maintenance window.

## The pool

`Orion.HA.Pools` declares 19 properties and they fall into four groups.

**Identity and type:**

| Property | Type | Notes |
|---|---|---|
| `PoolId` | `System.Int32` | The key, and the argument almost every verb takes. |
| `DisplayName` | `System.String` | The pool's name. What you look it up by. |
| `PoolType` | `System.String` | Documented as "0 - main poller, 1 - additional poller". **The declared type is `System.String`, not an integer**, so compare it as `'0'` and `'1'`. |
| `Enabled` | `System.Boolean` | Whether the pool is providing protection at all. |

**Current state:**

| Property | Type | Notes |
|---|---|---|
| `PoolMasterMemberId` | `System.Int32` | Which `Orion.HA.PoolMembers.PoolMemberId` is currently the master. |
| `CurrentStatus` | `System.Int32` | Pool status. See the note below the table. |
| `CurrentStatusTimestamp` | `System.DateTime` | When that status last changed. |
| `PoolMasterChangeTimestamp` | `System.DateTime` | When the master role last moved. |
| `FailoverTimestamp` | `System.DateTime` | The latest failover. |
| `RepairTimestamp` | `System.DateTime` | The latest repair. |

The value set behind `CurrentStatus` is **not documented in the published schema**, so treat
the integer as opaque and compare pools against each other rather than against a hard-coded
number.

**The virtual address, which is the point of the whole thing:**

| Property | Type | Notes |
|---|---|---|
| `VirtualIpAddress` | `System.String` | The address that follows the active member. |
| `VirtualHostName` | `System.String` | The name that follows the active member. |
| `DnsIpAddress` | `System.String` | The DNS server hosting the primary zone for that name. |
| `DnsZone` | `System.String` | The forward lookup zone the record lives in. |
| `DnsType` | `System.String` | One of `Microsoft`, `BIND`, `Other`. |

A pool can have a virtual IP, a virtual host name, both, or neither. They are configured
independently, and each is implemented as a separate resource, which is why removing one from
an `EditPool` call removes it from the pool. More on that below.

**The timers that decide when a failover happens:**

| Property | Type | Schema description |
|---|---|---|
| `IntervalMemberDown` | `System.Int32` | "Interval after which is member considered as down" |
| `IntervalPoolTask` | `System.Int32` | "Pool task interval in seconds. In this interval HA service performs regular tasks" |
| `IntervalSuicideRule` | `System.Int32` | "Interval after which member releases its resource if it cannot reach other member of a pool" |

`IntervalSuicideRule` is the split-brain guard and the most interesting of the three. A member
that has lost contact with its partner cannot tell whether the partner is dead or whether it is
itself isolated. Holding on to the resources in the second case gives you two servers both
claiming the same virtual IP. The suicide rule resolves it by having an isolated member give the
resources up, which is why `ReasonOfFail = 3` on a member is a network symptom rather than a
server one.

**Load balancing:** `ElbEnabled` is a `System.Boolean` saying whether Engine Load Balancing is
on for this pool. See [Load balancing](#load-balancing) below.

Pools navigate to their `Members`, their `ResourcesInstances`, and their
`LicenseAssignments` in `Orion.Licensing.LicenseAssignments`. That last one is the pool-level
licensing view: a licence assigned to a pool rather than to one server is what lets the standby
run without a second licence.

## Pool members

`Orion.HA.PoolMembers` is one row per server. It declares 14 properties, and it is the entity
you watch rather than the one you change.

| Property | Type | Notes |
|---|---|---|
| `PoolMemberId` | `System.Int32` | The key. What `CreatePool` and `SelectiveSwitchover` take. |
| `PoolId` | `System.Int32` | The pool. Navigate with `Pool`. |
| `PoolMemberType` | `System.String` | `MainPoller`, `MainPollerStandby`, `AdditionalPoller`, `AdditionalPollerStandby`. |
| `HostName` | `System.String` | The server's host name. This is the identity `DeleteStaleEngine` takes. |
| `PrimaryIpAddress` | `System.String` | Its primary address. |
| `Status` | `System.Int32` | Current member status. |
| `PreferredStatus` | `System.Int32` | "The status HA service or user want member to be". |
| `RepairStatus` | `System.Int32` | Repair state. |
| `ReasonOfFail` | `System.Int32` | Why it last failed. Values below. |
| `StatusMessage` | `System.String` | Description of the last failure, in text. Select it. |
| `LastHeartBeatTimestamp` | `System.DateTime` | The liveness signal. |
| `ElectionPriority` | `System.Int32` | Pool master election priority. |
| `Priority` | `System.Int32` | "Pool member preference". The sample script treats `Priority = 0` as the preferred member. |
| `DetailsUrl` | `System.String` | Console link. |

`ReasonOfFail` is one of the few integer columns in this module whose values the schema
documents outright:

| Value | Meaning |
|---:|---|
| 0 | ResourceFail |
| 1 | FacilityFail |
| 2 | NotResponding |
| 3 | SuicideRule |
| 4 | Switchover |
| 5 | Failback |

**`4` and `5` are deliberate operations, not faults.** A member with `ReasonOfFail = 4` was
failed over on purpose, most likely by somebody calling `Switchover`. An alert built on
"`ReasonOfFail` is not zero" will fire on every planned maintenance window you ever run.

`Status`, `PreferredStatus` and `RepairStatus` are integers whose value sets are
**not documented in the published schema**. SolarWinds' own
[`HA.PoolOperations.ps1`](https://github.com/solarwinds/OrionSDK/blob/master/Samples/PowerShell/HA.PoolOperations.ps1)
sample joins `Orion.StatusInfo` on `PoolMembers.Status`, which is evidence that member status
uses the platform status codes documented in
[../reference/status-codes.md](../reference/status-codes.md). This page follows that lead in
query 2, but treat the mapping as **unverified**: confirm on your own server by reading the
number next to `StatusMessage` before you build an alert on a specific value.

Members navigate to `Orion.Engines` through `Engine`, to `Orion.OrionServers` through
`OrionServer`, to their `FacilitiesInstances`, `ResourcesInstances` and
`PoolMemberInterfacesInfo`, and back to the pool through `Pool`.

**`Engine` is the one that tells you which member is live.** A standby member has no engine
attached to it, so `WHERE m.Engine.EngineID IS NOT NULL` is how SolarWinds' own sample finds the
active server in a pool. Query 3 below uses the same test.

## Resources and facilities

These two entities are the mechanism, and the distinction between them is the thing worth
understanding.

**A resource is a responsibility that moves.** The schema describes
`Orion.HA.ResourcesInstances` as "Resources which belongs to pool members. Resource is a
responsibility of Orion server which can be switched to another server in a pool e.g. 'Main
poller responsibility' or 'Virtual IP'."

| Property | Type | Notes |
|---|---|---|
| `PoolId` | `System.Int32` | The pool. |
| `RefId` | `System.String` | Reference id of the resource. This is what names it. |
| `PoolMemberId` | `System.Int32` | **Which member currently holds it.** This column moving is what a failover is. |
| `CurrentStatus` | `System.Int32` | Resource status. |
| `PreferredStatus` | `System.Int32` | "The status HA service want resource to be". |
| `Config` | `System.String` | Resource configuration, as a string. |
| `ActionExecutionParameters` | `System.String` | Resource action execution arguments. |

**A facility is a local health signal that decides whether a member is eligible to hold
resources.** The schema describes `Orion.HA.FacilitiesInstances` as "Facilities which belongs to
pool members. Facility can be imagined e.g. as a service (e.g. MSMQ) which indicates health
(ability to takeover resources) of a pool member." It has four properties: `RefId`,
`PoolMemberId`, `CurrentStatus` and `Config`, and it is hosted by the member rather than
referenced by it.

So the causal chain, entirely visible in the data, is:

```
facility unhealthy on a member
        -> member is not eligible to hold resources
        -> ReasonOfFail = 1 (FacilityFail)
        -> resources move: ResourcesInstances.PoolMemberId changes
        -> pool records FailoverTimestamp, and PoolMasterMemberId may change
        -> virtual IP and virtual host name follow, because they are resources
```

The `RefId` values that identify individual resources and facilities are **not enumerated in
the published schema**; they are installation data. Read them off your own pool with query 4,
which is also the fastest way to see what a given pool is actually protecting.

Neither entity has a documented value set for `CurrentStatus`. Both carry `Config` as an opaque
string. Do not parse it; its format is not part of the published contract.

## Reachability and the virtual address

`Orion.HA.ReachabilityInfo` is described in the schema as an extension of
`Orion.ReachabilityInfo`, and it exists to answer "what names and addresses can I use to reach
each Orion server, and which of them are virtual".

| Property | Type | Notes |
|---|---|---|
| `IP`, `HostName` | `System.String` | Either can be null. |
| `OrionServerId` | `System.Int32` | The `Orion.OrionServers` row. |
| `EngineId` | `System.Int32` | The engine, which can be null. |
| `CanActAsEngines` | `System.Int32[]` | "Array of possible EngineIds which can Orion stand for i.e. they are in the same HA pool". |
| `IsMyOwn` | `System.Boolean` | The IP or hostname belongs to the Orion you are connected to. |
| `IsPreferred` | `System.Boolean` | The preferred way to connect, set for one row per server. |
| `IsVirtual` | `System.Boolean` | **True for the pool's virtual IP or virtual host name.** |

`CanActAsEngines` is an array-typed column, which is unusual in this schema and awkward to
select. This page's queries leave it out; if you need it, expect an array rather than a scalar
in the result.

`IsVirtual = TRUE` is the row a client should be pointed at. **This is the practical answer to
"what address should my integration connect to".** Connecting an automation to a specific
member's host name works right up until that member is the one that failed, at which point your
integration is talking to a standby. Connect to the virtual name.

`Orion.HA.PoolMemberInterfacesInfo` is the lower-level view: every IP address on every
interface of every member, with `InterfaceType` documented as "1 - primary, 2 - other", plus
`SubnetPrefixLength` (a `System.String`, oddly) and `IsDynamic`. It matters because a virtual
IP has to live in a subnet that both members can hold, and this is where you check that they
share one.

## What a failover looks like from the API

Nothing about a failover changes the pool's membership or its configuration. What changes is a
small number of column values, and knowing which ones lets you detect a failover after the fact
without any event subscription.

| Where | What changes |
|---|---|
| `Orion.HA.ResourcesInstances.PoolMemberId` | The resources are now held by the other member. This is the failover. |
| `Orion.HA.Pools.FailoverTimestamp` | Set to the time of the failover. |
| `Orion.HA.Pools.PoolMasterMemberId` | Points at the new master, if the master role moved too. |
| `Orion.HA.Pools.PoolMasterChangeTimestamp` | Set when that happens. |
| `Orion.HA.PoolMembers.Status` and `StatusMessage` | The failed member's state and the reason in text. |
| `Orion.HA.PoolMembers.ReasonOfFail` | Why: resource, facility, unreachable, suicide rule, or a deliberate switchover or failback. |
| `Orion.HA.PoolMembers.LastHeartBeatTimestamp` | Stops advancing on the member that is gone. |
| `Orion.Engines` | The engine identity follows the active member, which is why `PoolMembers.Engine` is null on the standby. |

The consequence people miss is the last one. **Nodes are assigned to engines, and the engine
moves with the pool.** A node's `EngineID` does not change during a failover, because the
surviving server takes over that engine's identity. So a failover is invisible in
`Orion.Nodes`, and a query grouping nodes by engine gives the same answer before and after. See
[../platform/architecture.md](../platform/architecture.md) for the engine model and
[../polling/standard-pollers.md](../polling/standard-pollers.md#deciding-where-the-load-should-go) for engine load.

## The verbs

Thirteen verbs, all on `Orion.HA.Pools`, all requiring `admin`, and all returning
`SolarWinds.Orion.HighAvailability.Common.Model.OperationResult`. Regenerate the list for your
version with `python3 tools/schema_query.py verbs --entity Orion.HA.Pools`.

| Verb | Signature | What it does |
|---|---|---|
| `ValidateCreatePool` | `(displayName, poolMembersIds, properties)` | Checks a create without doing it |
| `CreatePool` | `(displayName, poolMembersIds, properties)` | Creates the pool |
| `ValidateEditPool` | `(poolId, displayName, poolMembersIds, properties)` | Checks an edit without doing it |
| `EditPool` | `(poolId, displayName, properties)` | Updates name and resource configuration |
| `EnablePool` | `(poolId)` | Turns protection on |
| `DisablePool` | `(poolId)` | Turns protection off |
| `Switchover` | `(poolId)` | Manual failover of the whole pool |
| `SelectiveSwitchover` | `(poolId, poolMemberIdsToFailover, poolMemberIdsToFailoverTo, failoverMessage)` | Fails over chosen members to chosen targets |
| `RepairPool` | `(poolId)` | Repairs the pool |
| `ElbEnable` | `(poolId)` | Turns Engine Load Balancing on for the pool |
| `ElbDisable` | `(poolId)` | Turns it off |
| `DeletePool` | `(poolId)` | Deletes the pool |
| `DeleteStaleEngine` | `(hostName)` | Deletes an `Orion.OrionServers` row and its pool member, by host name |

Note the asymmetry between `ValidateEditPool` and `EditPool`: **the validator takes
`poolMembersIds` and the real call does not.** That is not a documentation slip in this
repository; it is what both the rendered schema and the 2026.2 Swagger contract say. Since the
arguments are positional, a call written by copying the validator's argument list into
`EditPool` sends `poolMembersIds` where `properties` is expected. See
[../swis/invoke-verbs.md](../swis/invoke-verbs.md).

### The result object

Every one of the thirteen returns the same shape, which the Swagger contract defines as four
fields: `IsError` (boolean), `Code` (number), `Message` (string) and `Result` (string).
SolarWinds' sample tests `Code -eq 0` for success and reads `Result` on success and `Message`
on failure:

```powershell
$operationResult = Invoke-SwisVerb $swis 'Orion.HA.Pools' 'EnablePool' @($poolId)
if ($operationResult.Code -eq 0) {
    Write-Host $operationResult.Result.'#text'
} else {
    Write-Warning "Operation failed: $($operationResult.Message.'#text')"
}
```

One inconsistency to be aware of: in the same sample, the `Switchover` error path reads
`$failOverResult.ErrorMessage.'#text'` rather than `Message`. There is no `ErrorMessage` field
in the contract's `OperationResult`, so that line looks like a bug in the sample. Read `Message`
and treat `ErrorMessage` as **unverified**; if you want to know what your server returns, print
the whole object once with `$result.InnerXml`.

The `.'#text'` accessor is a PowerShell XML detail rather than a schema fact: `Invoke-SwisVerb`
returns the deserialised object, and scalar members come back as XML elements.

### The `properties` argument

`CreatePool`, `ValidateCreatePool`, `EditPool` and `ValidateEditPool` all take a `properties`
argument typed as an array of string-to-object key/value pairs. That tells you the shape but not
the keys, and the keys are **not enumerated in the published schema**. The only published source
for them is SolarWinds' `HA.PoolOperations.ps1` sample, which uses three:

| Key | Nested keys | What it configures |
|---|---|---|
| `poolConfiguration` | `preferredMemberId` | Which member the pool prefers to run on |
| `virtualIpResource` | `ipAddress` | The virtual IP resource |
| `virtualHostNameResource` | `hostName`, `dnsIp`, `dnsType`, `dnsZone`, `dnsUserName`, `dnsPassword` | The virtual host name resource and the DNS server that has to be updated to move it |

In PowerShell that is a nested hashtable:

```powershell
$poolMemberIds = [int[]]@( $primaryMemberId, $standbyMemberId )

$properties = @{
    poolConfiguration = @{ preferredMemberId = $primaryMemberId }
    virtualIpResource = @{ ipAddress = '10.0.0.250' }
    virtualHostNameResource = @{
        hostName = 'orion-ha'
        dnsIp    = '10.0.0.10'
        dnsType  = 'Microsoft'
        dnsZone  = 'example.com'
    }
}

# Validate first. Same arguments, no side effects.
$check = Invoke-SwisVerb $swis 'Orion.HA.Pools' 'ValidateCreatePool' `
    @('Main Pool', $poolMemberIds, $properties)

if ($check.Code -ne 0) {
    throw "Pool configuration rejected: $($check.Message.'#text')"
}

$created = Invoke-SwisVerb $swis 'Orion.HA.Pools' 'CreatePool' `
    @('Main Pool', $poolMemberIds, $properties)
```

Two warnings about that hashtable, both from SolarWinds' own comments in the sample.

**The DNS key is spelled differently in the two halves of the sample.** The create block uses
`dnsIp` and the edit block uses `dnsIP`. One of them is wrong, and which one **cannot be
verified here**. Test against a non-production pool, or use `ValidateEditPool` to find out
which spelling your server accepts before you run the real call.

**`dnsUserName` and `dnsPassword` cannot be read back.** The sample says so directly:
"Credentials must be always provided, cannot be retrieved via SWIS query". So a
read-modify-write cycle on a pool with a virtual host name always requires you to supply the
DNS credentials again from wherever you keep them, because the query interface will not give
them to you.

### `EditPool` drops what you leave out

This is the sharpest edge in the module and it is stated plainly in SolarWinds' sample:

> If either of these three configurations are removed from `$properties` corresponding plugin
> will be removed from pool after update.

`EditPool` is not a patch. **It is a replacement of the pool's resource configuration.** Calling
it with only `virtualHostNameResource` set, on a pool that also has a virtual IP, removes the
virtual IP. Every client following that address loses it.

So an edit is always read, merge, write. The sample does exactly this, and it is the pattern to
copy:

```powershell
$pool = Get-SwisData $swis @'
SELECT TOP 1 p.VirtualIpAddress, p.VirtualHostName, p.DnsZone, p.DnsIpAddress, p.DnsType
FROM Orion.HA.Pools p
WHERE p.PoolId = @poolId
'@ @{ poolId = $poolId }

$preferredMemberId = Get-SwisData $swis @'
SELECT TOP 1 m.PoolMemberId
FROM Orion.HA.PoolMembers m
WHERE m.PoolId = @poolId AND m.Priority = 0
'@ @{ poolId = $poolId }

$properties = @{}

# Re-supply every resource the pool already has, or EditPool removes it.
if ($pool.VirtualHostName) {
    $properties['virtualHostNameResource'] = @{
        hostName    = $pool.VirtualHostName
        dnsIp       = $pool.DnsIpAddress
        dnsType     = $pool.DnsType
        dnsZone     = $pool.DnsZone
        dnsUserName = $dnsUser       # not readable through SWIS
        dnsPassword = $dnsPassword   # not readable through SWIS
    }
}
if ($pool.VirtualIpAddress) {
    $properties['virtualIpResource'] = @{ ipAddress = $pool.VirtualIpAddress }
}
if ($preferredMemberId) {
    $properties['poolConfiguration'] = @{ preferredMemberId = $preferredMemberId }
}

$result = Invoke-SwisVerb $swis 'Orion.HA.Pools' 'EditPool' @($poolId, $poolName, $properties)
```

**Pool membership cannot be edited at all.** The sample says "Pool members cannot be updated
(user must perform delete/create sequence to select different members)". Changing which servers
are in a pool means `DeletePool` then `CreatePool`, and during the gap between them the pool is
providing no protection.

## What is safe to automate, and what is not

The verbs divide cleanly into three groups, and treating them as one group is how HA automation
goes wrong.

### Safe to automate freely

**Everything read-only.** Pool state, member state, resource ownership, reachability and
licence assignment are all ordinary queries. Poll them, alert on them, put them on a dashboard.
The queries below are the ones worth having.

**`ValidateCreatePool` and `ValidateEditPool`.** They take the same arguments as the real calls
and do not apply anything. There is no reason for a script that calls `CreatePool` or
`EditPool` not to call the validator first and stop on a non-zero `Code`.

### Safe in a controlled window, with a human deciding

**`Switchover`** is a deliberate failover, and it is genuinely useful: it is how you patch the
active server, and it is how you find out whether your HA configuration works before you need
it to. But it interrupts polling while resources move, and it moves the virtual IP, so anything
connected to that address reconnects. Run it in a window, one pool at a time, with the result
checked before you touch the next pool.

SolarWinds' sample prompts for confirmation before calling it, which is the right default:

```powershell
$confirmation = Read-Host "Manually fail over pool '$poolName'? (y = yes)"
if ($confirmation -ne 'y') { return }

$result = Invoke-SwisVerb $swis 'Orion.HA.Pools' 'Switchover' @($poolId)
if ($result.Code -ne 0) {
    Write-Warning "Failover failed: $($result.Message.'#text')"
    return
}
```

Then confirm it actually happened, because the verb returning `Code = 0` means the request was
accepted:

```sql
SELECT
    p.PoolId, p.DisplayName, p.PoolMasterMemberId, p.PoolMasterChangeTimestamp,
    p.FailoverTimestamp, p.CurrentStatus, p.CurrentStatusTimestamp
FROM Orion.HA.Pools p
WHERE p.PoolId = @poolId
```

**`SelectiveSwitchover`** is the finer-grained version, taking arrays of member ids to fail over
and member ids to fail over to, plus a `failoverMessage` string that is recorded with the
operation. The schema records **no description** for this verb, so its exact semantics when the
two arrays are different lengths, or when a target is not in the same pool, are **not documented
in the published schema** and are not verified here. Use `Switchover` unless you specifically
need per-member control, and test `SelectiveSwitchover` on a lab pool first.

**`ElbEnable` and `ElbDisable`** change whether the platform moves nodes between engines on its
own. Turning ELB on will start rebalancing your estate; see
[../polling/standard-pollers.md](../polling/standard-pollers.md#deciding-where-the-load-should-go) for what that looks like in
`Orion.ELB.NodeReassignments`.

**`RepairPool`** is described only as "Repair pool with given poolId". What it repairs, and
whether it is disruptive, is **not documented in the published schema**. It is the right thing
to try when `RepairStatus` on a member is non-zero, and it is not something to put in a retry
loop.

### Do not automate without a person in the loop

**`DisablePool`** turns off the protection. A pool that is disabled does not fail over, and
nothing else in the system will tell you that during the incident where it mattered. If a
script disables a pool, the same script must re-enable it, and something must alert if the pool
is still disabled an hour later. Query 1 below selects `Enabled` for exactly this reason.

**`DeletePool`** destroys the pool. Combined with the fact that membership cannot be edited,
this is also the first half of the only supported way to change which servers are in a pool,
which means the dangerous call and the routine one are the same call.

**`DeleteStaleEngine(hostName)`** deletes an `Orion.OrionServers` row and its pool member,
identified by host name rather than by id. It exists for a server that is genuinely gone and
will not come back. Identifying the target by a string, in a verb whose effect is deletion, is
worth a second look at the value you are passing: confirm it against a query first.

```sql
SELECT os.OrionServerID, os.HostName, os.FQDN, os.ServerType, os.Status,
       os.SWAVersion, os.SWAKeepAlive, os.AgentAutoDeploy,
       os.PoolMember.PoolMemberId AS PoolMemberId,
       os.PoolMember.PoolMemberType AS PoolMemberType
FROM Orion.OrionServers os
ORDER BY os.OrionServerID
```

**`CreatePool` and `EditPool`**, for the reasons in the previous section: an edit silently
removes resources you did not re-supply, the DNS credentials cannot be read back so a
round-trip needs them from elsewhere, and one of the two DNS key spellings in SolarWinds' own
sample must be wrong.

There is a general principle underneath all of this. **HA exists to survive the failure of the
thing your automation runs on.** A script that reconfigures pools is a script whose own
availability depends on the pools being configured correctly, and an automated remediation loop
that reacts to a failover by changing the pool is a way to turn one failed server into two. Read
continuously; write deliberately.

## Load balancing

`ElbEnabled` on the pool, plus the `ElbEnable` and `ElbDisable` verbs, control Engine Load
Balancing for that pool. ELB moves nodes between polling engines automatically rather than
leaving the distribution to an administrator, and it records what it did:

```sql
SELECT TOP 100 r.Id, r.NodeId, r.SourceEngineId, r.TargetEngineId, r.ReassignmentTimestamp
FROM Orion.ELB.NodeReassignments r
WHERE r.ReassignmentTimestamp >= @startUtc
ORDER BY r.ReassignmentTimestamp DESC
```

`Orion.ELB.NodeExclusions` is the opt-out list: a single `NodeId` column, writable under
`manageNodes`. Put a node there when it must stay on a specific engine, usually because only
that engine can reach it.

Note that ELB and HA are separate mechanisms that happen to share a switch. ELB decides which
engine polls a node; HA decides which server is that engine. A pool can have ELB off and still
fail over, and a deployment can have ELB on without any pools.

## Worked queries

Every query below was validated against the 2026.2 schema with
`python3 tools/validate_swql.py`.

### 1. Every pool, with the state that matters

```sql
SELECT
    p.PoolId, p.DisplayName, p.PoolType, p.Enabled,
    p.CurrentStatus, p.CurrentStatusTimestamp,
    p.PoolMasterMemberId, p.PoolMasterChangeTimestamp,
    p.VirtualHostName, p.VirtualIpAddress, p.DnsType, p.DnsZone, p.DnsIpAddress,
    p.ElbEnabled, p.FailoverTimestamp, p.RepairTimestamp,
    p.IntervalMemberDown, p.IntervalPoolTask, p.IntervalSuicideRule
FROM Orion.HA.Pools p
ORDER BY p.PoolId
```

Run this first, every time. **`Enabled` is the column people forget**: a pool that exists,
looks configured, and is disabled provides exactly as much protection as no pool at all, and
nothing else on this page distinguishes the two.

`FailoverTimestamp` is the other one to read. A pool that failed over last night and that
nobody noticed is running on its standby, which means the next failure has nowhere to go.

### 2. Members and their heartbeat state

```sql
SELECT
    m.PoolId, m.Pool.DisplayName AS PoolName, m.PoolMemberId, m.HostName,
    m.PoolMemberType, m.Status, si.StatusName, m.PreferredStatus, m.RepairStatus,
    m.ReasonOfFail, m.StatusMessage, m.LastHeartBeatTimestamp,
    m.PrimaryIpAddress, m.ElectionPriority, m.Priority
FROM Orion.HA.PoolMembers m
JOIN Orion.StatusInfo si ON m.Status = si.StatusId
ORDER BY m.PoolId, m.PoolMemberId
```

The `Orion.StatusInfo` join follows SolarWinds' own sample, and it is the part of this query to
sanity-check on your server before trusting: if `StatusName` comes back as something that makes
no sense for a server, the mapping does not hold on your version and you should drop the join
and read `StatusMessage` instead.

`LastHeartBeatTimestamp` is the liveness signal that does not lie. A member whose heartbeat has
stopped advancing is gone regardless of what its `Status` integer still says, and comparing the
two members' heartbeats in one glance is why this query does not filter.

For the alerting version, restrict to members that are not healthy and bring the pool's state
along:

```sql
SELECT
    m.PoolMemberId, m.HostName, m.PoolMemberType, m.Status, m.StatusMessage,
    m.ReasonOfFail, m.LastHeartBeatTimestamp,
    m.Pool.DisplayName AS PoolName, m.Pool.Enabled AS PoolEnabled,
    m.Pool.CurrentStatus AS PoolStatus
FROM Orion.HA.PoolMembers m
WHERE m.Status <> 1
ORDER BY m.LastHeartBeatTimestamp
```

Remember that `ReasonOfFail` values `4` and `5` are a deliberate switchover and a failback, so
filter them out of an alert unless you want to be paged by your own maintenance.

### 3. Which member is actually live

```sql
SELECT
    m.PoolId, m.Pool.DisplayName AS PoolName, m.PoolMemberId, m.HostName,
    m.PoolMemberType, m.Status,
    m.Engine.EngineID, m.Engine.ServerName, m.Engine.PollingCompletion,
    m.Engine.MinutesSinceKeepAlive,
    m.OrionServer.OrionServerID, m.OrionServer.ServerType
FROM Orion.HA.PoolMembers m
WHERE m.Engine.EngineID IS NOT NULL
ORDER BY m.PoolId
```

`Engine.EngineID IS NOT NULL` is SolarWinds' own test for the active member, and it works
because the engine identity follows the resources rather than the hardware. Selecting
`PollingCompletion` and `MinutesSinceKeepAlive` from the engine at the same time answers the
follow-up question: the pool failed over, but is the surviving server actually keeping up with
the work it inherited?

Compare `m.PoolMemberType` in the result against what you expect. A row saying
`MainPollerStandby` here means the pool is running on its standby right now.

### 4. Where the resources are, and what a pool is protecting

```sql
SELECT
    r.PoolId, r.Pool.DisplayName AS PoolName, r.RefId,
    r.PoolMemberId, r.PoolMember.HostName AS HeldBy,
    r.CurrentStatus, r.PreferredStatus, r.Config
FROM Orion.HA.ResourcesInstances r
ORDER BY r.PoolId, r.RefId
```

This is the ground truth of a failover: `PoolMemberId` is the member currently holding each
responsibility. Two resources in the same pool held by two different members is a state worth
looking at closely, because a partial failover is usually a resource that could not be taken
over.

`RefId` names the resource, and reading the values here is how you find out what your pools
actually protect, since the schema does not enumerate them.

The facilities that decide eligibility:

```sql
SELECT
    f.RefId, f.PoolMemberId, f.PoolMember.HostName AS MemberHostName,
    f.PoolMember.PoolId AS PoolId, f.CurrentStatus, f.Config
FROM Orion.HA.FacilitiesInstances f
ORDER BY f.PoolMemberId, f.RefId
```

Run this when a member has `ReasonOfFail = 1` (FacilityFail). It names the local service whose
health took the member out, which is a considerably more useful answer than "it failed over".

### 5. The address a client should connect to

```sql
SELECT ri.OrionServerId, ri.EngineId, ri.HostName, ri.IP,
       ri.IsMyOwn, ri.IsPreferred, ri.IsVirtual
FROM Orion.HA.ReachabilityInfo ri
ORDER BY ri.OrionServerId
```

`IsVirtual = TRUE` marks the pool's virtual IP and virtual host name. Point integrations at
those, not at a member's own name. `IsPreferred` is set for one row per server and is the answer
for the non-virtual case.

The addresses available on each member's interfaces, which is what a virtual IP has to fit
into:

```sql
SELECT i.PoolMemberId, i.PoolMember.HostName AS MemberHostName,
       i.InterfaceType, i.IPAddress, i.SubnetPrefixLength, i.IsDynamic
FROM Orion.HA.PoolMemberInterfacesInfo i
ORDER BY i.PoolMemberId, i.InterfaceType
```

`InterfaceType` is documented as "1 - primary, 2 - other". `SubnetPrefixLength` is a
`System.String` despite being a number, so it will not compare numerically. `IsDynamic = TRUE`
on a member's primary address is worth knowing about before you build a pool on it.

### 6. Pools with their member counts, for a health summary

```sql
SELECT
    p.PoolId, p.DisplayName, p.Enabled, p.CurrentStatus,
    p.FailoverTimestamp, p.PoolMasterChangeTimestamp, p.RepairTimestamp,
    p.PoolMasterMemberId,
    COUNT(m.PoolMemberId) AS MemberCount
FROM Orion.HA.Pools p
LEFT JOIN Orion.HA.PoolMembers m ON m.PoolId = p.PoolId
GROUP BY p.PoolId, p.DisplayName, p.Enabled, p.CurrentStatus,
         p.FailoverTimestamp, p.PoolMasterChangeTimestamp, p.RepairTimestamp,
         p.PoolMasterMemberId
ORDER BY p.PoolId
```

A `LEFT JOIN` rather than an inner one, because a pool with no members is precisely the
degenerate case you want this query to surface. A `MemberCount` of one is a pool with nothing to
fail over to.

### 7. What a failover would move

The blast radius question, answered before you call `Switchover` rather than after.

```sql
SELECT
    e.EngineID, e.ServerName, e.ServerType,
    e.PoolMember.PoolId AS PoolId,
    e.PoolMember.Pool.DisplayName AS PoolName,
    e.PoolMember.PoolMemberType AS MemberType,
    COUNT(n.NodeID) AS NodeCount
FROM Orion.Engines e
LEFT JOIN Orion.Nodes n ON n.EngineID = e.EngineID
GROUP BY e.EngineID, e.ServerName, e.ServerType,
         e.PoolMember.PoolId, e.PoolMember.Pool.DisplayName,
         e.PoolMember.PoolMemberType
ORDER BY e.EngineID
```

`Orion.Engines` navigates to its pool member through `PoolMember`, and from there to the pool,
so one query gives you engine, pool and node count together. The `NodeCount` is what stops
polling briefly while the resources move.

Engines with a null `PoolId` in this result are not protected by any pool at all, which is
usually more interesting than the ones that are.

### 8. Licences assigned to a pool rather than a server

```sql
SELECT la.Id, la.ProductName, la.LicenseVersion, la.OrionServerID, la.OrionPoolID,
       la.OrionPool.DisplayName AS PoolName, la.OrionServer.HostName AS ServerHostName
FROM Orion.Licensing.LicenseAssignments la
ORDER BY la.ProductName
```

`Orion.Licensing.LicenseAssignments` requires the `admin` right even to read, so a limited
account gets nothing back rather than an error. A licence with an `OrionPoolID` set belongs to
the pool, which is what lets the standby run without consuming a second licence; one with only
an `OrionServerID` is pinned to one server.

### 9. Who changed a pool

```sql
SELECT TOP 100
    ae.AuditEventID, ae.TimeLoggedUtc, ae.AccountID, ae.AuditEventMessage
FROM Orion.AuditingEvents ae
WHERE ae.TimeLoggedUtc >= @startUtc
ORDER BY ae.TimeLoggedUtc DESC
```

`Orion.HA.PoolAdded`, `Orion.HA.PoolEdited` and `Orion.HA.PoolDeleted` are indications, not
tables, so this is where the durable record is. Time-bound it, because auditing is one of the
largest tables on the system, and see
[events-and-auditing.md](events-and-auditing.md) for joining `Orion.AuditingActionTypes` to get
a structured action rather than a message string.

## Gotchas

**`Orion.HA.PoolMembers` is read-only.** There is no CRUD path into pool membership at all.
Everything goes through verbs on `Orion.HA.Pools`, and every one of them requires `admin`.

**`EditPool` replaces the resource configuration, it does not patch it.** Anything you leave out
of `properties` is removed from the pool, including the virtual IP that clients are following.
Always read the current configuration and re-supply it.

**Pool membership cannot be edited.** Changing which servers are in a pool means `DeletePool`
then `CreatePool`, and the pool protects nothing in between.

**`ValidateEditPool` and `EditPool` take different argument lists.** The validator takes
`poolMembersIds` as its third argument; `EditPool` does not have that parameter at all. Since
arguments are positional, copying one call into the other puts the member array where
`properties` belongs.

**The DNS credentials cannot be read back.** SolarWinds' sample states it: `dnsUserName` and
`dnsPassword` must be supplied on every edit and cannot be retrieved through a query. Keep them
wherever you keep secrets, not in Orion.

**SolarWinds' sample spells the DNS IP key two different ways.** `dnsIp` in the create block and
`dnsIP` in the edit block. Which one the server accepts cannot be verified here; find out with
`ValidateEditPool` before running the real call.

**`PoolType` is a `System.String` holding what looks like an integer.** Compare it with `'0'`
and `'1'`, not `0` and `1`.

**`ReasonOfFail` of `4` or `5` is not a fault.** They are a deliberate switchover and a
failback. Alerting on "not zero" pages you for your own maintenance.

**`ReasonOfFail = 3` is a network problem, not a server one.** The suicide rule fires when a
member cannot reach its partner and releases its resources to avoid two servers holding the same
virtual IP.

**Member `Status`, `PreferredStatus`, `RepairStatus`, pool `CurrentStatus` and resource
`CurrentStatus` have no documented value sets.** Only `ReasonOfFail` is documented, along with
`PoolMemberType`, `DnsType` and `PoolType`. SolarWinds' sample joins `Orion.StatusInfo` on
member `Status`, which is suggestive but is unverified here. Read `StatusMessage`.

**A failover does not change `Orion.Nodes.EngineID`.** The engine identity moves with the pool,
so a node stays on "engine 2" while the physical server behind engine 2 changes. A query
grouping nodes by engine looks identical before and after a failover.

**A pool that is disabled looks exactly like a pool that is working.** `Enabled = FALSE` is the
only difference and nothing else surfaces it. Select it in every pool query.

**`DeleteStaleEngine` identifies its target by host name string.** It deletes an
`Orion.OrionServers` row and its pool member. Confirm the value against a query before you pass
it.

**`SelectiveSwitchover` and `RepairPool` have no schema descriptions**, so their exact behaviour
is not documented in the published schema and is not verified here. Prefer `Switchover`, and
test the other two on a lab pool.

**Nothing in this module can be unmanaged.** None of the nine entities is a
`System.ManagedEntity`, so there is no maintenance window for a pool or a member. Suppressing
alerts during planned HA work is a job for alert suppression or dependencies; see
[dependencies.md](dependencies.md).

**Every verb returns "accepted", not "finished".** `Code = 0` means the request was taken.
Confirm a switchover by watching `PoolMasterMemberId`, `FailoverTimestamp` and
`ResourcesInstances.PoolMemberId` move.

**Connect your automation to the virtual name.** An integration pointed at a member's own host
name works until that member is the one that failed. `Orion.HA.ReachabilityInfo` with
`IsVirtual = TRUE` is the address to use.

## Related pages

- [../platform/architecture.md](../platform/architecture.md) for polling engines, the
  main-versus-additional distinction, and where HA sits in the deployment picture.
- [../polling/standard-pollers.md](../polling/standard-pollers.md) for engine load, `Orion.PollingUsage` and the ELB reassignment
  history that `ElbEnable` starts producing.
- [node-management.md](node-management.md) for `EngineID` and why moving a node between engines
  is a different operation from a failover.
- [../modules/agents.md](../modules/agents.md) for agents, whose engine assignment is a verb
  rather than a property and which follow the same engine identity across a failover.
- [events-and-auditing.md](events-and-auditing.md) for the durable record of pool changes.
- [dependencies.md](dependencies.md) for suppressing downstream alerts during planned work.
- [../swis/invoke-verbs.md](../swis/invoke-verbs.md) for positional arguments, which is what
  makes the `ValidateEditPool` and `EditPool` difference dangerous.
- [../swis/verb-catalog.md](../swis/verb-catalog.md) for the HA verbs alongside the rest of the
  platform.
- [../swis/metadata-introspection.md](../swis/metadata-introspection.md) for confirming a verb
  signature on a version other than 2026.2.
- [../reference/status-codes.md](../reference/status-codes.md) for the platform status codes
  that member `Status` may or may not use.
- [../reference/verb-index.md](../reference/verb-index.md) for the generated verb table.

## Official SolarWinds documentation

- [`HA.PoolOperations.ps1`](https://github.com/solarwinds/OrionSDK/blob/master/Samples/PowerShell/HA.PoolOperations.ps1),
  the only published worked example of the pool verbs, and the source for the `properties`
  argument shape, the read-modify-write requirement on `EditPool`, and the statement that pool
  members cannot be updated
- [Polling Engine Load Balancing](https://solarwinds.github.io/OrionSDK/docs/polling-engine-load-balancing/)
  for the engine side of what a pool is protecting
- [Orion SDK documentation index](https://solarwinds.github.io/OrionSDK/)

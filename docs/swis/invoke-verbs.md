# Invoking verbs

The SWIS query interface is read only and the CRUD interface can only set property values on
one entity instance at a time. Neither of those can express "poll this node right now",
"acknowledge these twelve alerts with a note", "deploy an agent to this host" or "create a
custom property definition". Those are **verbs**, and `Invoke` is how you call them.

In SWIS schema 2026.2 there are **958 verbs**, of which **794 publish typed, named, ordered
parameters**. This page is the complete guide to calling them. The per-task shortlist is in
[verb-catalog.md](verb-catalog.md); the exhaustive machine-generated table is in
[../reference/verb-index.md](../reference/verb-index.md).

## What a verb is, and why it exists

A verb is a named operation that an entity type declares, with a typed parameter list, a
return type, and optionally a required user right. It runs inside SWIS, on the Orion server,
with the caller's identity attached.

That last part is the point. `Orion.Nodes.Unmanage` is not "set `UnManaged = true` on a
row". Unmanaging a node has to write the unmanage window, change the node's status, stop the
pollers on the right polling engine, and make the same change consistent for the objects
underneath the node. Expressing that as a CRUD update would mean re-implementing Orion's
internals in every client, and getting it subtly wrong in each one. Going through a verb
means the platform does it, checks that the caller holds the `allowUnmanage` right first,
and records that it happened.

So the rule of thumb is: if the change you want has a name in the Orion web console
("Unmanage", "Poll Now", "Acknowledge", "Rediscover", "Deploy Agent"), look for a verb before
you reach for CRUD. If you cannot find one,
[crud.md](crud.md) covers the alternative.

## The contract, in one paragraph

**Verb arguments are positional.** Names appear in the schema documentation, in the Swagger
contract and in this repository's data, but they never travel on the wire. Both the REST body
and `Invoke-SwisVerb` send an ordered array. The order of the parameter list is therefore the
entire contract, and passing the right values in the wrong order is a bug that no client can
detect for you. Look up the order before every call you have not made before:

```bash
python3 tools/schema_query.py verb Orion.Nodes Unmanage
```

## REST

```text
POST https://<orion-server>:17774/SolarWinds/InformationService/v3/Json/Invoke/{Entity}/{Verb}
Authorization: Basic <base64 user:password>
Content-Type: application/json

[ <arg0>, <arg1>, ... ]
```

The body is a **JSON array of positional arguments**. This is what the official
[REST](https://solarwinds.github.io/OrionSDK/docs/rest/) page shows, using a verb that takes a
single string:

```text
POST https://localhost:17774/SolarWinds/InformationService/v3/Json/Invoke/Metadata.Entity/GetAliases HTTP/1.1
Authorization: Basic YWRtaW46
Host: localhost:17774
Accept: */*
Content-Type: application/json
Content-Length: 39

["SELECT B.Caption FROM Orion.Nodes B"]
```

```text
HTTP/1.1 200 OK
Content-Type: application/json

{"B":"Orion.Nodes"}
```

The response body is the JSON serialisation of the verb's return value. `Metadata.Entity`
`GetAliases` returns a property bag, so the body is a JSON object. A verb declared as
returning `System.Void` has no meaningful value to send back, so treat a `2xx` as success and
confirm the effect with a follow-up query rather than by parsing the body.

A real call with curl, unmanaging node 42 for a four hour window:

```bash
curl -sS -X POST \
  -u 'svc-automation:...' \
  --cacert /etc/ssl/certs/orion-swis.pem \
  -H 'Content-Type: application/json' \
  -d '["N:42","2026-08-21T22:00:00Z","2026-08-22T02:00:00Z",false,false]' \
  'https://myorion.example.com:17774/SolarWinds/InformationService/v3/Json/Invoke/Orion.Nodes/Unmanage'
```

Notice that the JSON types match the declared parameter types: `netObjectId` is a string,
`unmanageTime` and `remanageTime` are strings holding ISO-8601 timestamps, and `isRelative`
and `allowOverlapping` are JSON booleans, not the strings `"false"`.

### Optional trailing arguments may be omitted

The 794 verbs with typed parameters mark each parameter required or optional. Optional
parameters are always at the end of the list, so you can truncate the array after the last
argument you want to supply. The official
[Managing Custom Properties](https://solarwinds.github.io/OrionSDK/docs/managing-custom-properties/)
example does exactly this: `Orion.NodesCustomProperties.CreateCustomProperty` declares 16
parameters in 2026.2, the first 10 of which are required, and the official example passes 10.

You cannot skip an argument in the middle. If you want to set the twelfth parameter you must
supply the eleventh, using `null` where the value does not matter.

### A note on the Swagger contract

The published Swagger 2.0 contract models each Invoke body as an object with named
properties, for example `OrionNodesUnmanageRequest` with `netObjectId`, `unmanageTime`,
`remanageTime`, `isRelative` and `allowOverlapping`. That definition is where the parameter
names, types, order and required flags in this repository come from, and it is the reason
`data/schema/2026.2/verbs.json` can be trusted about the signature.

Send the positional array anyway. Every official client and the official REST documentation
example use the array form. Whether the object form is also accepted on the wire is not
something this repository has verified; do not depend on it.

## PowerShell

`Invoke-SwisVerb` from the `SwisPowerShell` module takes four mandatory arguments:
the connection, the entity name, the verb name, and an array of argument values.

```powershell
Import-Module SwisPowerShell
$swis = Connect-Swis -Hostname orion.example.com -Trusted

Invoke-SwisVerb $swis 'Orion.Nodes' 'PollNow' @('N:42')
```

Positionally, `Invoke-SwisVerb $swis <EntityName> <Verb> <Arguments>`; or spelled out,
`Invoke-SwisVerb -SwisConnection $swis -EntityName 'Orion.Nodes' -Verb 'PollNow' -Arguments @('N:42')`.

The `Arguments` array is **positional and ordered**. It is a `List<object>`, so PowerShell
will happily let you pass five values where the verb wants four, or swap two of them.
Nothing checks the shape until the server rejects it, and some mistakes do not get rejected
at all. This is the single most common source of Invoke bugs.

### How arguments are serialised

`Invoke-SwisVerb` serialises each element of the array independently before sending it:

| What you pass | How it is serialised |
|:---|:---|
| A scalar (`string`, `int`, `bool`, `DateTime`) | .NET `DataContractSerializer` on its runtime type |
| A `Hashtable` or any `IDictionary` | A SWIS `PropertyBag` XML document |
| An `XmlElement` (typically `([xml]"...").DocumentElement`) | Sent as the argument element |
| A `PSObject` wrapper | Unwrapped to its `BaseObject`, then one of the above |

That table is why three distinct idioms show up in SolarWinds' own sample scripts, and why
each of them exists.

**Scalars.** Nothing special. `@('N:42', $start, $end, $false)`.

**Hashtables for structured arguments.** Any verb parameter whose declared type is a
dictionary or a settings bag takes a PowerShell hashtable, and nested hashtables work.
SolarWinds' `HA.PoolOperations.ps1` sample builds the `properties` argument of
`Orion.HA.Pools.CreatePool` this way:

```powershell
$properties = @{
    poolConfiguration       = @{ preferredMemberId = $firstPoolMemberId }
    virtualIpResource       = @{ ipAddress = '1.1.0.2' }
    virtualHostNameResource = @{
        hostName = 'TestHostName'
        dnsIp    = '10.140.100.101'
        dnsType  = 'Other'
        dnsZone  = 'fake.com'
    }
}

$result = Invoke-SwisVerb $swis 'Orion.HA.Pools' 'CreatePool' @($mainPoolName, $poolMemberIds, $properties)
```

**XML elements for complex contract types.** Some verbs declare a parameter whose type is a
.NET contract class rather than a scalar, an array or a dictionary. `Orion.Discovery`
`StartDiscovery` takes a single `context` parameter of type
`SolarWinds.Data.Providers.Orion.Verbs.Discovery-StartDiscoveryContext`. For these you build
the XML yourself and pass the document element:

```powershell
$CorePluginConfigurationContext = ([xml]"
<CorePluginConfigurationContext xmlns='http://schemas.solarwinds.com/2012/Orion/Core' xmlns:i='http://www.w3.org/2001/XMLSchema-instance'>
    <BulkList>
        <IpAddress><Address>$ip</Address></IpAddress>
    </BulkList>
    <Credentials>
        <SharedCredentialInfo>
            <CredentialID>$credentialId</CredentialID>
            <Order>1</Order>
        </SharedCredentialInfo>
    </Credentials>
    <WmiRetriesCount>1</WmiRetriesCount>
    <WmiRetryIntervalMiliseconds>1000</WmiRetryIntervalMiliseconds>
</CorePluginConfigurationContext>
").DocumentElement

$CorePluginConfiguration = Invoke-SwisVerb $swis Orion.Discovery CreateCorePluginConfiguration @($CorePluginConfigurationContext)
```

You do not have to guess the element names. `Metadata.VerbArgument` publishes an
`XmlTemplate` for exactly this purpose, and SWQL Studio's Invoke Verb tab renders it. See
[Discovering the XML shape of a complex argument](#discovering-the-xml-shape-of-a-complex-argument).

### The single-array-argument pitfall

This one bites everybody once. When a verb takes exactly one argument and that argument is
itself an array, the obvious PowerShell code does the wrong thing:

```powershell
# WRONG. $uris is already an array, so @($uris) flattens to an array of strings and
# PowerShell hands the verb N arguments instead of one array argument.
Invoke-SwisVerb $swis Orion.AlertSuppression ResumeAlerts @($uris)
```

The fix, which SolarWinds documents in the official
[Alerts](https://solarwinds.github.io/OrionSDK/docs/alerts/) page, is a leading comma plus an
explicit cast:

```powershell
# RIGHT. The leading comma makes a one-element array whose single element is $uris.
Invoke-SwisVerb -SwisConnection $swis -EntityName Orion.AlertSuppression -Verb ResumeAlerts `
    -Arguments @( , [string[]] $uris )
```

The `[string[]]` cast matters too. `Get-SwisData` returns values wrapped in `PSObject`, and
although those print like strings they are not `System.String` at serialisation time.

The same shape applies to `Orion.AlertActive.ClearAlert(alertObjectIds)`,
`Orion.AlertActive.Unacknowledge(alertObjectIds)`, `Orion.Events.Acknowledge(eventIDs)`,
`Orion.ADM.NodeInventory.PollNow(nodeIds)` and every other one-parameter verb whose parameter
is an array. The catalog marks these; you can also find them with:

```bash
python3 tools/schema_query.py verb Orion.AlertSuppression ResumeAlerts
```

### The return value

`Invoke-SwisVerb` returns an `XmlElement` representing the complete response, not a
deserialised object. Read into it with normal PowerShell XML property access, and remember
that a text node is reached through `'#text'`:

```powershell
$operationResult = Invoke-SwisVerb $swis 'Orion.HA.Pools' 'CreatePool' @($name, $memberIds, $properties)
if ($operationResult.Code -eq 0) {
    Write-Host $operationResult.Result.'#text'
} else {
    Write-Warning "Operation failed: $($operationResult.Message.'#text')"
}
```

For a verb that returns a scalar, `.InnerText` is usually what you want:

```powershell
$DiscoveryProfileID = (Invoke-SwisVerb $swis Orion.Discovery StartDiscovery @($StartDiscoveryContext)).InnerText
```

Verbs declared `System.Void` write nothing to the pipeline. Piping them to `Out-Null` keeps
scripts quiet and makes the intent explicit.

## Python

SolarWinds publishes [`orionsdk`](https://github.com/solarwinds/orionsdk-python) on PyPI. Its
`invoke` method takes the entity, the verb, and then the arguments as ordinary positional
Python arguments:

```python
from orionsdk import SwisClient

swis = SwisClient("myorion.example.com", "svc-automation", password,
                  verify="/etc/ssl/certs/orion-swis.pem")

swis.invoke("Orion.Nodes", "PollNow", "N:42")
```

Under the hood that is the same REST call: the client `POST`s
`Invoke/Orion.Nodes/PollNow` with `["N:42"]` as the body and returns the parsed JSON
response. This repository's dependency-light client in
`scripts/python/swis_client.py` implements the same signature, and its whole `invoke`
method is three lines, which is a good way to see that there is nothing else going on:

```python
def invoke(self, entity, verb, *args):
    """Invoke a verb. Arguments are positional; order is the contract."""
    return self._request("POST", f"Invoke/{entity}/{verb}", list(args))
```

Because Python's argument list maps one-to-one onto the JSON array, arrays and structures are
just Python lists and dicts:

```python
# Orion.AlertActive.Acknowledge(alertObjectIds, notes)
swis.invoke("Orion.AlertActive", "Acknowledge", [1042, 1043, 1051],
            "Acknowledged by change CHG0041288")

# Orion.Nodes.Unmanage(netObjectId, unmanageTime, remanageTime, isRelative, allowOverlapping)
from datetime import datetime, timedelta, timezone
start = datetime.now(timezone.utc)
end = start + timedelta(hours=4)
swis.invoke("Orion.Nodes", "Unmanage", "N:42",
            start.isoformat(), end.isoformat(), False, False)
```

Python has no equivalent of the PowerShell single-array pitfall: `swis.invoke(e, v, [1, 2, 3])`
passes one array argument, which is what you meant.

## Three ways to discover a verb's parameters

Use whichever matches where you are working. They agree, because the first two are built from
the third.

### 1. This repository's data, offline

```bash
python3 tools/schema_query.py verb Orion.Nodes Unmanage
```

```text
Orion.Nodes.Unmanage
  Set the given node into maintenance mode so the node polling is disabled
  returns: System.Void
  REST:    POST /Invoke/Orion.Nodes/Unmanage
  requires: allowUnmanage
  parameters (5):
    netObjectId: string (required)
    unmanageTime: string (required)
    remanageTime: string (required)
    isRelative: boolean (required)
    allowOverlapping: boolean (optional)

  PowerShell:
    Invoke-SwisVerb $swis 'Orion.Nodes' 'Unmanage' @($netObjectId, $unmanageTime, $remanageTime, $isRelative, $allowOverlapping)

  REST body (positional array):
    ["<netObjectId>", "<unmanageTime>", "<remanageTime>", "<isRelative>", "<allowOverlapping>"]
```

Related commands, all offline and all reading `data/schema/2026.2/`:

```bash
python3 tools/schema_query.py verbs --entity Orion.AlertActive   # every verb on one entity
python3 tools/schema_query.py verbs --grep unmanage              # search verbs by name
python3 tools/schema_query.py show Orion.Nodes                   # entity, including its verbs
python3 tools/schema_query.py verb Orion.Nodes Unmanage --json   # machine-readable
```

### 2. The Swagger contract

The contract published alongside the schema declares one path per verb, tagged `Verbs`, with
a request definition naming and typing every parameter. For `Orion.Nodes.Unmanage`:

```json
{
  "required": ["netObjectId", "unmanageTime", "remanageTime", "isRelative"],
  "type": "object",
  "properties": {
    "netObjectId":      { "type": "string" },
    "unmanageTime":     { "format": "date-time", "type": "string" },
    "remanageTime":     { "format": "date-time", "type": "string" },
    "isRelative":       { "type": "boolean" },
    "allowOverlapping": { "type": "boolean" }
  }
}
```

The `required` array is the authoritative required-versus-optional split, and `format:
date-time` is how you learn that a `string` parameter is really a timestamp. Read it from a
local copy with `jq`:

```bash
jq '.paths["/Invoke/Orion.Nodes/Unmanage"], .definitions.OrionNodesUnmanageRequest' swagger.json
```

The contract is not perfectly aligned with the rendered schema pages, and both are published
by SolarWinds. In 2026.2 the Swagger contract declares **937** `/Invoke/` paths while the
schema pages document **958** verbs; **84** verbs appear only in the schema pages (70 of them
in the `Cortex` namespace) and **63** Invoke paths appear only in the contract. When they
disagree, your own server is the tiebreaker, which is the next method.

### 3. Live introspection through `Metadata.*`

This is authoritative for *your* server at *your* version, and it is what SWQL Studio itself
queries to populate its Invoke Verb tab.

```sql
SELECT Position, Name, Type, IsOptional, Summary
FROM Metadata.VerbArgument
WHERE EntityName = 'Orion.Nodes' AND VerbName = 'Unmanage'
ORDER BY Position
```

`ORDER BY Position` is not decoration. Position is the argument order, which is the contract,
so a result set in arbitrary order is worse than useless.

Every verb the server exposes on one entity:

```sql
SELECT v.Name, v.CanInvoke, v.IsObsolete, v.Summary
FROM Metadata.Verb v
WHERE v.Entity.FullName = 'Orion.Nodes'
ORDER BY v.Name
```

Note that `Metadata.Verb` does not carry an `EntityName` property in 2026.2; it reaches its
owning entity through the `Entity` navigation property. `Metadata.VerbArgument` does carry
flat `EntityName` and `VerbName` strings, which is why the argument query above needs no
join. [metadata-introspection.md](metadata-introspection.md) covers the whole namespace.

### Discovering the XML shape of a complex argument

When a parameter's type is a .NET contract class rather than a scalar, array or dictionary,
`Metadata.VerbArgument.XmlTemplate` gives you the skeleton to fill in, and `XmlSchemas` gives
the schemas it validates against:

```sql
SELECT Position, Name, Type, XmlTemplate
FROM Metadata.VerbArgument
WHERE EntityName = 'Orion.Discovery' AND VerbName = 'StartDiscovery'
ORDER BY Position
```

To find every verb argument on the server that needs this treatment:

```sql
SELECT EntityName, VerbName, Position, Name, Type
FROM Metadata.VerbArgument
WHERE XmlTemplate IS NOT NULL
ORDER BY EntityName, VerbName, Position
```

## Access control

Verbs declare the right the caller must hold. In the extracted data this is the
`accessControl` array on each verb record in `data/schema/2026.2/verbs.json`:

```json
{
  "entity": "Orion.Nodes",
  "name": "Unmanage",
  "returns": "System.Void",
  "restPath": "/Invoke/Orion.Nodes/Unmanage",
  "accessControl": [
    { "operations": ["invoke"], "right": "allowUnmanage" }
  ]
}
```

Entities carry the same structure for their CRUD operations. `Orion.Nodes` itself declares:

```json
"accessControl": [
  { "operations": ["read"], "right": "everyone" },
  { "operations": ["read", "invoke"], "right": "allowRealTimePolling" },
  { "operations": ["create", "read", "update", "delete", "invoke"], "right": "manageNodes" }
]
```

Several entries mean any one of those rights grants the listed operations, which is why
`Orion.Nodes.StartRealTimePolling` lists both `allowRealTimePolling` and `admin`.

329 of the 958 verbs in 2026.2 declare a right. The complete set of rights that appear, with
how many verbs require each:

| Right | Verbs |
|:---|---:|
| `admin` | 161 |
| `manageNodes` | 129 |
| `allowRealTimePolling` | 21 |
| `manageAlerts` | 13 |
| `allowUnmanage` | 10 |
| `system` | 8 |
| `clearEvents` | 7 |
| `manageMaps` | 6 |
| `allowOrionMapsManagement` | 4 |
| `manageReports` | 3 |
| `everyone` | 2 |
| `allowDisableAlert` | 1 |
| `allowCustomize` | 1 |

(`admin` totals 161 because one verb,
`Orion.DeletedAutoDependencies.RemoveIgnoredAutoDependencies`, declares it for `delete` and
`invoke` together rather than for `invoke` alone.)

### Rights are declared at two levels, so check both

A verb with an empty `accessControl` array does not mean "anybody can call it". Rights are
declared on the verb **and** on the entity, and when the verb declares nothing the entity's
`invoke` entry is what applies. **629 of the 958 verbs declare no right of their own, and 363
of those belong to an entity that does declare an `invoke` right.**

That is not a technicality. It is the difference between reading the table and knowing what
your automation account needs:

| Entity | Verb-level rights | Entity-level `invoke` rights |
|:---|:---|:---|
| `Orion.Discovery` | none on any of its 12 verbs | `manageNodes` |
| `Orion.AgentManagement.Agent` | none on any of its 20 verbs | `manageNodes` |
| `Orion.NodesCustomProperties` | none on any of its 5 verbs | `admin` |
| `Orion.Container` | none on any of its 11 verbs | `manageNodes` or `allowOrionMapsManagement` |
| `Orion.APM.Application` | none on `Unmanage` / `Remanage` | `manageNodes` or `allowUnmanage` |
| `Orion.Netflow.NodeSources` | none | `manageNodes` |

So creating a node custom property definition needs `admin`, even though nothing in the
verb's own record says so.

Check the entity as well as the verb:

```bash
python3 tools/schema_query.py verb Orion.NodesCustomProperties CreateCustomProperty
python3 tools/schema_query.py show Orion.NodesCustomProperties      # look at "operations" / access control
```

When neither level declares anything, the operation can still be gated further down. NCM in
particular enforces its own role model on top: many `Cirrus.*` and `NCM.*` verb summaries say
things like "Valid for Orion manage node users with at least WebUploader NCM role", and that
requirement is real even though it is prose rather than an `accessControl` entry.

### Rights are properties of the Orion account

The rights in the table correspond by name to the `Allow...` and `Can...` properties of
`Orion.Accounts`:

```sql
SELECT AccountID, AllowNodeManagement, AllowUnmanage, AllowAdmin, CanClearEvents, AllowAlertManagement
FROM Orion.Accounts
WHERE AccountID = @account
```

Two things about that query trip people up, and both come from the official
[Account Management](https://solarwinds.github.io/OrionSDK/docs/account-management/) page.
First, these properties **read** as the strings `"Y"` and `"N"`, not as booleans. Second, when
you **set** them through `Orion.Accounts.UpdateAccount` you must pass real booleans (`true` /
`false` in JSON, `$true` / `$false` in PowerShell). All account-management verbs themselves
require `AllowAdmin`.

The property names are close to but not identical to the right names in the schema
(`manageNodes` corresponds to `AllowNodeManagement`, `clearEvents` to `CanClearEvents`), and
`Orion.Accounts` in 2026.2 has no property matching `allowRealTimePolling` or `system`. Treat
the name correspondence as a strong hint rather than a lookup table, and confirm on your
server by trying the verb with a test account.

### When you get a permission error

A `403`-style failure from Invoke is almost always a missing right, not a broken call. Check,
in this order:

1. The right the verb declares (`python3 tools/schema_query.py verb <Entity> <Verb>`).
2. Whether the calling account holds it (the `Orion.Accounts` query above).
3. Whether an **account limitation** is hiding the target object. Limitations filter query
   results silently, so an automation that resolves a NodeID by query and then invokes a verb
   on it can fail at either step for the same underlying reason. Two accounts running the same
   query legitimately get different rows.
4. For NCM and IPAM verbs, the module's own role on top of the Orion right.

## Worked examples

Each of these was checked with `python3 tools/schema_query.py verb <Entity> <Verb>` against
schema 2026.2 before it was written down.

### 1. `Orion.Nodes.Unmanage` and `Orion.Nodes.Remanage`

```text
Orion.Nodes.Unmanage(netObjectId, unmanageTime, remanageTime, isRelative, allowOverlapping?)
  -> System.Void        requires allowUnmanage
Orion.Nodes.Remanage(netObjectId)
  -> System.Void        requires allowUnmanage
```

| Position | Name | Type | Required | Meaning |
|---:|:---|:---|:---|:---|
| 0 | `netObjectId` | `string` | yes | The NetObject string for the node, `N:<NodeID>`. Node 42 is `N:42`. |
| 1 | `unmanageTime` | `string` (`date-time`) | yes | When the window opens. A time in the past means "immediately". |
| 2 | `remanageTime` | `string` (`date-time`) | yes | When the window closes. |
| 3 | `isRelative` | `boolean` | yes | See below. Pass `false` unless you specifically want the other behaviour. |
| 4 | `allowOverlapping` | `boolean` | no | Permit a new window when one is already open for this node. |

**`netObjectId` is a NetObject string, not a bare id.** The prefix is per entity type:
`N` for `Orion.Nodes`, `I` for `Orion.NPM.Interfaces`, `V` for `Orion.Volumes`,
`AA` for `Orion.APM.Application`. The full table is in
[../reference/netobject-types.md](../reference/netobject-types.md).

**`isRelative` changes what `remanageTime` means.** From the official
[Unmanaging Entities](https://solarwinds.github.io/OrionSDK/docs/unmanaging-entities/) page:
with `isRelative = true` the date portion of the third argument is ignored and the time
portion is treated as a *duration*. So `isRelative = true` with a third argument of
`0001-01-01T04:00:00` means "four hours", not "4am on the first of January". SolarWinds
recommends passing `false` and using two absolute timestamps, and so does this guide, because
a script that says `$start` and `$start.AddHours(4)` is readable by the next person and a
duration smuggled into a date field is not.

**Times are handled in UTC.** The official documentation describes both timestamps as being
"in UTC". Passing a local `DateTime` is the most common cause of a maintenance window that
opens at the wrong hour, and the failure is silent: the call succeeds, and the window is
simply wrong. Convert explicitly at the call site rather than relying on the client's locale.
This applies to `Orion.NPM.Interfaces.Unmanage`, `Orion.Volumes.Unmanage`,
`Orion.APM.Application.Unmanage` and `Orion.AlertSuppression.SuppressAlerts` equally.

Note also that the official documentation describes a four-parameter signature with the
parameters called `unmanageFrom` and `unmanageUntil`. In 2026.2 the schema names them
`unmanageTime` and `remanageTime` and adds the optional fifth `allowOverlapping`. Positions
0 to 3 are unchanged, so existing four-argument calls keep working.

PowerShell:

```powershell
Import-Module SwisPowerShell
$swis = Connect-Swis -Hostname orion.example.com -Trusted

$nodeId  = 42
$startUtc = [datetime]::UtcNow
$endUtc   = $startUtc.AddHours(4)

Invoke-SwisVerb $swis 'Orion.Nodes' 'Unmanage' @("N:$nodeId", $startUtc, $endUtc, $false, $false) | Out-Null

# End the window early.
Invoke-SwisVerb $swis 'Orion.Nodes' 'Remanage' @("N:$nodeId") | Out-Null
```

Python:

```python
from datetime import datetime, timedelta, timezone

start = datetime.now(timezone.utc)
end = start + timedelta(hours=4)
swis.invoke("Orion.Nodes", "Unmanage", "N:42", start.isoformat(), end.isoformat(), False, False)
swis.invoke("Orion.Nodes", "Remanage", "N:42")
```

REST:

```json
["N:42", "2026-08-21T22:00:00Z", "2026-08-22T02:00:00Z", false, false]
```

Always verify the result, because a void verb tells you nothing:

```sql
SELECT Caption, UnManaged, UnManageFrom, UnManageUntil, Status
FROM Orion.Nodes
WHERE NodeID IN @ids
```

`UnManaged`, `UnManageFrom` and `UnManageUntil` are inherited from `System.ManagedEntity`, so
the same three columns work for interfaces, volumes, applications and everything else that
can be unmanaged. `Status` becomes `9` (`Unmanaged`); see
[../reference/status-codes.md](../reference/status-codes.md).

A production-shaped wrapper for this verb, with confirmation prompts and UTC conversion, is
in `scripts/powershell/Set-NodeMaintenanceWindow.ps1`.

### 2. `Orion.Nodes.PollNow`

```text
Orion.Nodes.PollNow(netObjectId) -> System.Void        requires manageNodes
```

One argument, the same `N:<NodeID>` NetObject string. It asks the polling engine that owns
the node to poll it now rather than waiting for the next scheduled cycle.

```powershell
Invoke-SwisVerb $swis 'Orion.Nodes' 'PollNow' @('N:42') | Out-Null
```

```bash
curl -sS -X POST -u "$ORION_USER:$ORION_PASS" --cacert "$ORION_CA" \
  -H 'Content-Type: application/json' -d '["N:42"]' \
  'https://myorion.example.com:17774/SolarWinds/InformationService/v3/Json/Invoke/Orion.Nodes/PollNow'
```

`PollNow` returns `System.Void` and returns as soon as the request is queued, so it tells you
nothing about whether the poll happened. Confirm by watching the sync timestamps move:

```sql
SELECT Caption, LastSync, MinutesSinceLastSync, NextPoll
FROM Orion.Nodes
WHERE NodeID = @id
```

Three related verbs on the same entity do different amounts of work, and picking the smallest
one that solves your problem matters on a large estate:

| Verb | Signature | What it does |
|:---|:---|:---|
| `PollStatusNow` | `(netObjectId)` | Polls status only. The cheapest. |
| `PollNow` | `(netObjectId)` | Polls the node instance and updates its information. |
| `RediscoverNow` | `(netObjectId)` | Rediscovers the node, which is the most expensive. |

All three take the `N:<NodeID>` string and all three require `manageNodes`.

Be careful with the closely related real-time polling verbs, because their first argument is
**not** a NetObject string:

```text
Orion.Nodes.StartRealTimePolling(netObjectId, owner, properties, pollingExpiration?, pollingFrequency?)
  -> boolean            requires allowRealTimePolling or admin
```

Here `netObjectId` is declared `number` and documented as "NodeID of target Node", so you pass
`42`, not `"N:42"`. The same is true of `Orion.Nodes.GetSupportedMetrics`. A parameter called
`netObjectId` is not automatically a NetObject string, which is exactly why you check the type
before every unfamiliar call.

### 3. `Orion.AlertActive.Acknowledge`

```text
Orion.AlertActive.Acknowledge(alertObjectIds, notes) -> boolean   requires clearEvents
```

| Position | Name | Type | Required |
|---:|:---|:---|:---|
| 0 | `alertObjectIds` | `array<number>` | yes |
| 1 | `notes` | `string` | yes |

**Pass `AlertObjectID` values, not `AlertActiveID` values.** The verb's own summary text says
"based on array of alert active ids", but the parameter is named `alertObjectIds` and the
official [Alerts](https://solarwinds.github.io/OrionSDK/docs/alerts/) page is explicit: "To
acknowledge alerts, pass the AlertObjectID values and a note to
`Orion.AlertActive.Acknowledge`". Both ids exist on `Orion.AlertActive`, they are different
numbers, and passing the wrong one silently acknowledges nothing or the wrong thing.

Find the ids first:

```sql
SELECT aa.AlertActiveID, ao.AlertObjectID, ac.Name AS AlertName, ao.EntityCaption, aa.TriggeredDateTime
FROM Orion.AlertActive aa
JOIN Orion.AlertObjects ao ON aa.AlertObjectID = ao.AlertObjectID
JOIN Orion.AlertConfigurations ac ON ao.AlertID = ac.AlertID
WHERE aa.Acknowledged = FALSE
ORDER BY aa.TriggeredDateTime DESC
```

PowerShell. Note the `[int[]]` cast, which turns the `PSObject`-wrapped query results into a
real integer array, and note that because this verb has a second argument the leading-comma
trick is not needed:

```powershell
[int[]]$alertObjectIds = Get-SwisData $swis @'
SELECT ao.AlertObjectID
FROM Orion.AlertActive aa
JOIN Orion.AlertObjects ao ON aa.AlertObjectID = ao.AlertObjectID
WHERE aa.Acknowledged = FALSE
  AND ao.RelatedNodeCaption = @caption
'@ @{ caption = 'edge-rtr-01' }

$ok = Invoke-SwisVerb $swis 'Orion.AlertActive' 'Acknowledge' @($alertObjectIds, 'Ack by CHG0041288')
```

Python:

```python
swis.invoke("Orion.AlertActive", "Acknowledge", [1042, 1043, 1051], "Ack by CHG0041288")
```

REST:

```json
[[1042, 1043, 1051], "Ack by CHG0041288"]
```

The outer array is the argument list and the inner array is the first argument. Getting this
nesting wrong is the REST equivalent of the PowerShell leading-comma problem.

The three sibling verbs follow the same rules and the same id:

| Verb | Signature | Note |
|:---|:---|:---|
| `Unacknowledge` | `(alertObjectIds)` | Single array argument. Use `@( , [int[]] $ids )` in PowerShell. |
| `AppendNote` | `(alertObjectIds, note)` | Adds a note without acknowledging. |
| `ClearAlert` | `(alertObjectIds)` | Clears without running reset actions. If the trigger condition still holds, the alert fires again on the next evaluation. |

All four require `clearEvents` and all four return `boolean`.

### 4. `Orion.NodesCustomProperties.CreateCustomProperty`

```text
Orion.NodesCustomProperties.CreateCustomProperty(
    PropertyName, Description, ValueType, Size, ValidRange, Parser, Header,
    Alignment, Format, Units, Usages?, Mandatory?, Default?, SourceId?,
    SourceName?, DisplayName?) -> System.Void
```

Sixteen parameters, the first ten required. This is the verb that most rewards checking the
signature, because six of the ten required parameters are documented as unused and simply
have to be present.

| Position | Name | Type | Required | What to pass |
|---:|:---|:---|:---|:---|
| 0 | `PropertyName` | `string` | yes | The property name. |
| 1 | `Description` | `string` | yes | Shown in the editing UI. |
| 2 | `ValueType` | `string` | yes | One of `string`, `integer`, `datetime`, `single`, `double`, `boolean`. |
| 3 | `Size` | `number` | yes | Maximum length in characters for `string`. Ignored otherwise. |
| 4 | `ValidRange` | `string` | yes | Unused. Pass null. |
| 5 | `Parser` | `string` | yes | Unused. Pass null. |
| 6 | `Header` | `string` | yes | Unused. Pass null. |
| 7 | `Alignment` | `string` | yes | Unused. Pass null. |
| 8 | `Format` | `string` | yes | Unused. Pass null. |
| 9 | `Units` | `string` | yes | Unused. Pass null. |
| 10 | `Usages` | `array<KeyValuePair<string,bool>>` | no | Which parts of the product may use the property. |
| 11 | `Mandatory` | `boolean` | no | Require a value in the Add Node wizard. |
| 12 | `Default` | `string` | no | Default value for new nodes. |
| 13 | `SourceId` | `string` | no | |
| 14 | `SourceName` | `string` | no | |
| 15 | `DisplayName` | `string` | no | |

The "unused, pass null" descriptions for positions 4 to 9 come from the official
[Managing Custom Properties](https://solarwinds.github.io/OrionSDK/docs/managing-custom-properties/)
page, which also supplies this example. It stops after position 9 because everything from
position 10 on is optional:

```powershell
Invoke-SwisVerb $swis Orion.NodesCustomProperties CreateCustomProperty `
    @("DataCentre", "Physical datacentre the node lives in", "string", 128, $null, $null, $null, $null, $null, $null)
```

REST, the same call:

```json
["DataCentre", "Physical datacentre the node lives in", "string", 128, null, null, null, null, null, null]
```

To restrict the property to a list of allowed values, use `CreateCustomPropertyWithValues`
instead. It is the same list with one extra parameter, `Value`, inserted **between `Units`
and `Usages`**, which shifts every optional parameter by one position:

```text
CreateCustomPropertyWithValues(PropertyName, Description, ValueType, Size, ValidRange,
    Parser, Header, Alignment, Format, Units, Value, Usages?, Mandatory?, Default?,
    SourceId?, SourceName?, DisplayName?)
```

```powershell
$values = [string[]]@('London', 'Frankfurt', 'Singapore')
Invoke-SwisVerb $swis Orion.NodesCustomProperties CreateCustomPropertyWithValues `
    @("DataCentre", "Physical datacentre", "string", 128, $null, $null, $null, $null, $null, $null, $values)
```

Confirm the definition landed, and check the allowed values:

```sql
SELECT Table, Field, DataType, MaxLength, Description, Mandatory
FROM Orion.CustomProperty
WHERE Table = 'NodesCustomProperties'
ORDER BY Field
```

```sql
SELECT Value
FROM Orion.CustomPropertyValues
WHERE Table = 'NodesCustomProperties' AND Field = @property
```

**`ModifyCustomProperty` replaces the value list, it does not add to it.** Its signature is
`(PropertyName, Description, Size, Values, Usages?, Mandatory?, Default?, SourceId?,
SourceName?, propertyDisplayName?)`, and `Values` is the complete new list. To add one value
you must read the current list, append, and send the whole thing back:

```powershell
$propertyName = 'DataCentre'
$existing = Get-SwisData $swis @'
SELECT Description, MaxLength FROM Orion.CustomProperty
WHERE Table = 'NodesCustomProperties' AND Field = @property
'@ @{ property = $propertyName }

[array]$values = Get-SwisData $swis @'
SELECT Value FROM Orion.CustomPropertyValues
WHERE Table = 'NodesCustomProperties' AND Field = @property
'@ @{ property = $propertyName }

$values += 'Dublin'
Invoke-SwisVerb $swis Orion.NodesCustomProperties ModifyCustomProperty `
    @($propertyName, $existing.Description, $existing.MaxLength, [string[]]$values)
```

Finally, these verbs manage the custom property **definition**. Setting a **value** on a
particular node is a CRUD update against that node's `CustomProperties` URI, and setting the
same value on many nodes is a `BulkUpdate`. See [crud.md](crud.md) and
[rest-api.md](rest-api.md).

Twenty-six entities host custom-property verbs in 2026.2, one per object type that supports
custom properties. Do not assume the signature is identical across all of them.
`Orion.APM.ApplicationCustomProperties.CreateCustomProperty` uses lower-camel parameter names
(`propertyName`, `description`, ...), calls position 10 `usageFlags` and position 12
`defaultValue`, has only 15 parameters, and marks `usageFlags`, `mandatory` and `defaultValue`
as required. Check each one:

```bash
python3 tools/schema_query.py verb Orion.APM.ApplicationCustomProperties CreateCustomProperty
```

### 5. `Orion.AlertSuppression.SuppressAlerts`

```text
Orion.AlertSuppression.SuppressAlerts(entityUris, suppressFrom?, suppressUntil?,
    allowOverlapping?, reason?) -> System.Void      requires allowUnmanage
Orion.AlertSuppression.ResumeAlerts(entityUris) -> System.Void          requires allowUnmanage
Orion.AlertSuppression.GetAlertSuppressionState(entityUris) -> array    requires everyone
```

Suppressing alerts is not the same as unmanaging. Unmanaging stops polling, so you get a gap
in your charts. Suppressing keeps polling and collecting statistics but stops alerts from
triggering. If your goal is "do not page me during the change window" and you still want the
data, this is the verb you want, not `Unmanage`.

The first argument is an array of **URIs**, not NetObject strings and not ids. Suppression is
inherited: suppressing a node's URI also suppresses the children of that node.

```powershell
$uris = Get-SwisData $swis @'
SELECT n.Uri FROM Orion.Nodes n WHERE n.Vendor = @vendor ORDER BY n.Caption
'@ @{ vendor = 'Cisco' }
$uris = @( $uris | ForEach-Object { [string]$_ } )

$fromUtc  = [datetime]::UtcNow
$untilUtc = $fromUtc.AddHours(2)

Invoke-SwisVerb $swis Orion.AlertSuppression SuppressAlerts @($uris, $fromUtc, $untilUtc) | Out-Null

# One argument, and that argument is an array: leading comma and explicit cast.
Invoke-SwisVerb -SwisConnection $swis -EntityName Orion.AlertSuppression -Verb ResumeAlerts `
    -Arguments @( , [string[]] $uris )
```

Omitting `suppressFrom` means "now"; omitting `suppressUntil` means "forever", and forever
really is forever until something calls `ResumeAlerts`. Both timestamps follow the same UTC
rule as `Unmanage`.

`GetAlertSuppressionState` is the safe read-only call, and it is the only alert-suppression
verb whose declared right is `everyone`. It accounts for suppression inherited from a parent,
which a plain query of `Orion.AlertSuppression` does not:

```powershell
$state = Invoke-SwisVerb $swis Orion.AlertSuppression GetAlertSuppressionState @( , [string[]] $uris )
$state.EntityAlertSuppressionState
```

The current suppression records are also queryable directly:

```sql
SELECT ID, EntityUri, SuppressFrom, SuppressUntil
FROM Orion.AlertSuppression
ORDER BY SuppressFrom DESC
```

Note that the official documentation describes a three-parameter `SuppressAlerts`. In 2026.2
the schema declares five, adding optional `allowOverlapping` and `reason` at the end, so
three-argument calls written against the older documentation still work.

### 6. `Orion.Discovery.CreateCorePluginConfiguration` and `StartDiscovery`

```text
Orion.Discovery.CreateCorePluginConfiguration(context) -> string
Orion.Discovery.StartDiscovery(context) -> number
Orion.Discovery.GetDiscoveryProgress(profileId) -> string
Orion.Discovery.ImportDiscoveryResults(cfg) -> string
```

This is the standard example of a verb whose argument is a complex contract type rather than
a scalar. `CreateCorePluginConfiguration` takes one parameter, `context`, of type
`SolarWinds.Data.Providers.Orion.Verbs.Discovery-CorePluginConfigurationContext`.

The shape is best taken from `Metadata.VerbArgument.XmlTemplate` on your own server, or from
SolarWinds' own working sample scripts. This is the flow from
`Samples/PowerShell/DiscoverWmiNode.ps1`, condensed:

```powershell
$credentialId = Get-SwisData $swis 'SELECT ID FROM Orion.Credential WHERE Name = @name' @{ name = 'wmi-admin' }

$CorePluginConfigurationContext = ([xml]"
<CorePluginConfigurationContext xmlns='http://schemas.solarwinds.com/2012/Orion/Core' xmlns:i='http://www.w3.org/2001/XMLSchema-instance'>
    <BulkList><IpAddress><Address>$ip</Address></IpAddress></BulkList>
    <Credentials><SharedCredentialInfo><CredentialID>$credentialId</CredentialID><Order>1</Order></SharedCredentialInfo></Credentials>
    <WmiRetriesCount>1</WmiRetriesCount>
    <WmiRetryIntervalMiliseconds>1000</WmiRetryIntervalMiliseconds>
</CorePluginConfigurationContext>
").DocumentElement

$CorePluginConfiguration = Invoke-SwisVerb $swis Orion.Discovery CreateCorePluginConfiguration @($CorePluginConfigurationContext)

$StartDiscoveryContext = ([xml]"
<StartDiscoveryContext xmlns='http://schemas.solarwinds.com/2012/Orion/Core' xmlns:i='http://www.w3.org/2001/XMLSchema-instance'>
    <Name>Script Discovery $([DateTime]::Now)</Name>
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
    <IsHidden>true</IsHidden>
    <PreferredPollingMethod>1</PreferredPollingMethod>
    <PluginConfigurations>
        <PluginConfiguration>
            <PluginConfigurationItem>$($CorePluginConfiguration.InnerXml)</PluginConfigurationItem>
        </PluginConfiguration>
    </PluginConfigurations>
</StartDiscoveryContext>
").DocumentElement

$DiscoveryProfileID = (Invoke-SwisVerb $swis Orion.Discovery StartDiscovery @($StartDiscoveryContext)).InnerText
```

Three things generalise from this beyond discovery:

- The output of one verb feeds the input of the next. `CreateCorePluginConfiguration` returns
  a string of XML which is embedded verbatim as `$($CorePluginConfiguration.InnerXml)`.
- Long-running verbs return a job or profile id immediately and you poll for completion. Here
  that is `Orion.DiscoveryProfiles.Status`, or `Orion.Discovery.GetDiscoveryProgress`.
- The `xmlns` on the root element is part of the contract. Dropping it produces a
  deserialisation failure that reads as a generic fault.

The `Orion.Nodes` list-resources verbs follow the same schedule-then-poll-then-import shape
without needing XML at all: `ScheduleListResources(nodeId)` returns a job id,
`GetScheduledListResourcesStatus(jobId, nodeId)` reports progress,
`GetListResourcesResult(jobId, nodeId)` returns what was found and
`ImportSelectedListResourcesResult(jobId, nodeId, resources)` commits a subset.

## Common failure modes

| Symptom | Likely cause |
|:---|:---|
| Call succeeds, nothing changes | Wrong id kind. `N:42` where a bare `42` was wanted, or `AlertActiveID` where `AlertObjectID` was wanted. |
| Maintenance window opens at the wrong hour | Local time passed where UTC was expected. |
| Type error on the first argument | Arguments in the wrong order. Re-check with `schema_query.py verb`. |
| PowerShell: "expected 1 argument, got N" | Single array argument flattened. Use `@( , [type[]] $array )`. |
| PowerShell: serialisation error on a query result | `PSObject` wrappers. Cast with `[string[]]` or `[int[]]`. |
| Permission denied | Missing right, or an account limitation hiding the target. |
| Verb not found on your server | Module not installed or licensed, or a different platform version. Check `Metadata.Verb`. |
| Works in the lab, fails in production | Different schema version. The 2026.2 signature is not the 2020.2 signature. |

## Where to go next

- [verb-catalog.md](verb-catalog.md) groups the most useful verbs by task and shows how to
  query the full set of 958.
- [metadata-introspection.md](metadata-introspection.md) is the authoritative way to answer
  schema questions against your own server.
- [../reference/verb-index.md](../reference/verb-index.md) lists every verb with its
  signature, return type and required right.
- [crud.md](crud.md) covers the operations Invoke is not for.
- [rest-api.md](rest-api.md) has the full REST contract, including `BulkUpdate` and
  `BulkDelete`.
- [../reference/netobject-types.md](../reference/netobject-types.md) maps entity types to
  their NetObject prefixes.

Official upstream sources used on this page:

- [REST](https://solarwinds.github.io/OrionSDK/docs/rest/)
- [PowerShell](https://solarwinds.github.io/OrionSDK/docs/powershell/)
- [Unmanaging Entities](https://solarwinds.github.io/OrionSDK/docs/unmanaging-entities/)
- [Alerts](https://solarwinds.github.io/OrionSDK/docs/alerts/)
- [Managing Custom Properties](https://solarwinds.github.io/OrionSDK/docs/managing-custom-properties/)
- [Account Management](https://solarwinds.github.io/OrionSDK/docs/account-management/)
- [Orion SDK wiki](https://github.com/solarwinds/OrionSDK/wiki)

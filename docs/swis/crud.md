# CRUD: creating, reading, updating and deleting entities

The SWIS query interface is read only. Everything that changes data goes through the CRUD
interface, the Invoke interface, or the bulk operations. This page covers CRUD.

CRUD is a *generic* interface. The same four operations work against any entity type that
supports them, which is what makes it possible to write tooling that manipulates entity
types it was never specifically written for. From the official
[About SWIS](https://solarwinds.github.io/OrionSDK/docs/about-swis/) page:

> These create, read, update, and delete (CRUD) operations comprise a generic interface
> through which you can access any entity type exposed by SWIS and manipulate the entity in
> a uniform fashion.

## The four operations

| Operation | REST | Takes | Returns |
|:---|:---|:---|:---|
| Create | `POST /Create/{Entity}` | Entity type name, JSON object of property values | The URI of the new entity, as a JSON string |
| Read | `GET /{uri}` | A URI | A JSON object of the entity's properties |
| Update | `POST /{uri}` | A URI, JSON object of the properties to change | Empty `200` |
| Delete | `DELETE /{uri}` | A URI | Empty `200` |

The asymmetry is the important part:

- **Create is the only operation that does not take a URI**, because the entity does not
  exist yet and so has no identity to address. It takes the entity *type* name in the path
  and returns the URI of the instance it created.
- **Read, Update and Delete all take URIs.** Whatever creates a URI for you, whether that is
  a Create response or a `SELECT Uri FROM ...` query, is what feeds the other three.

That is why [uris.md](uris.md) matters so much: the URI is the handle for three quarters of
this interface.

Update is a partial update. You send only the properties you are changing, and everything
else is left alone. The official example changes exactly one property on a poller:

```text
POST .../Json/swis://tdanner-dev.swdev.local/Orion/Orion.Pollers/PollerID=6
Content-Type: application/json

{"PollerType":"hi from curl"}
```

## Not every entity supports CRUD

Again from the official documentation:

> However, there may be entity types that do not support this interface or provide only
> limited support due to technical or design reasons. In these cases, the operations may
> reject requests.

Support is per operation, not all-or-nothing. Several common patterns exist:

- **Full CRUD.** `Orion.Nodes`, `Orion.NPM.Interfaces`, `Orion.Volumes` and `Orion.Pollers`
  all declare create, read, update, delete and invoke in 2026.2.
- **Read and update only.** `Orion.NodesCustomProperties` declares read, update and invoke,
  and no create or delete. The row of custom property *values* exists because the node
  exists; you do not create or destroy it independently. Adding or removing a custom
  property *definition* is a different operation entirely, done through the verbs
  `CreateCustomProperty`, `ModifyCustomProperty` and `DeleteCustomProperty` on that same
  entity.
- **Read only in practice, even when write operations exist.** `Orion.Engines` declares
  read for `everyone` but restricts create, update and delete to the `system` right, which
  an ordinary administrator account does not hold.
- **Computed and metadata entities.** `Metadata.Entity` and `Orion.AlertActive` declare no
  entity-level CRUD access control at all. `Orion.AlertActive` is manipulated through its
  verbs (`Acknowledge`, `Unacknowledge`, `AppendNote`, `ClearAlert`), not through Update.

### How to check a specific entity, at runtime

The authoritative answer for *your* server is the `Metadata` namespace, which SWIS exposes
as queryable entities. `Metadata.Entity` carries a boolean per operation:

```sql
SELECT FullName, CanCreate, CanRead, CanUpdate, CanDelete, CanInvoke
FROM Metadata.Entity
WHERE FullName = 'Orion.Nodes'
```

`CanCreate`, `CanRead`, `CanUpdate`, `CanDelete` and `CanInvoke` are all real
`Metadata.Entity` properties in 2026.2. To list everything you can create:

```sql
SELECT FullName
FROM Metadata.Entity
WHERE CanCreate = true
ORDER BY FullName
```

Property-level support is available too. `Metadata.Property` carries `CanCreate`, `CanRead`
and `CanUpdate` per property, which is how you find out that a property is readable but not
settable before your update silently does nothing:

```sql
SELECT Name, Type, IsKey, IsNullable, CanCreate, CanRead, CanUpdate
FROM Metadata.Property
WHERE Entity.FullName = 'Orion.Nodes'
ORDER BY Name
```

`Metadata.Property.Entity` is a real navigation property leading back to `Metadata.Entity`.

### How to check a specific entity, offline

This repository ships the extracted schema, so you can answer the question without a server.
Every record in `data/schema/2026.2/index.json` carries a `canCreate` boolean, derived from
whether the SWIS Swagger contract publishes a `/Create/{Entity}` path for that entity:

```bash
python3 - <<'PY'
import json
idx = json.load(open("data/schema/2026.2/index.json"))
by_name = {e["entity"]: e for e in idx}
e = by_name["Orion.Nodes"]
print(e["entity"], "canCreate:", e["canCreate"], "operations:", e["operations"])
PY
```

which prints:

```
Orion.Nodes canCreate: True operations: ['create', 'delete', 'invoke', 'read', 'update']
```

Or list all creatable entities:

```bash
python3 -c "
import json
idx = json.load(open('data/schema/2026.2/index.json'))
names = sorted(e['entity'] for e in idx if e['canCreate'])
print(len(names))
print('\n'.join(names[:20]))
"
```

**250 of the 2067 documented entities in 2026.2 have `canCreate` set to true.** That is the
`creatableEntities` count in `data/schema/2026.2/manifest.json`, and you can confirm it with
`python3 tools/schema_query.py stats`.

Two reconciliation details worth knowing, because the numbers do not line up naively:

- The Swagger contract publishes **378** `/Create/{Entity}` paths in total. 128 of those name
  entities that do not appear in the rendered schema reference at all, including
  internal-looking aliases such as `Local.Orion.APM.ComponentSetting` and entities such as
  `Orion.AIIM.Issues`. Those are excluded from the 250 because there is no documented entity
  to attach them to. If you need one of them, verify it against your own server with
  `Metadata.Entity` rather than trusting the count here.
- The `operations` list on each index record comes from the entity's own access control table
  in the schema reference. 239 entities declare `create` there. Exactly 11 entities have
  `canCreate` true while `operations` omits `create`: the eight `Orion.Cloud.Aws.*`,
  `Orion.Cloud.Azure.*` and `Orion.Cloud.Gcp.*` `Accounts`, `Regions` and `ResourseTags`
  types, plus `Orion.DPA.DatabaseInstanceApplication`,
  `Orion.DPA.DatabaseInstanceApplicationNoRelationship` and
  `Orion.DPA.DatabaseInstanceClientApplication`. Those have a `/Create` path in the contract
  but no published access control table. When the two sources disagree,
  `Metadata.Entity` on your server is the tiebreaker.

### Access control

Even when an entity supports an operation, the calling account needs the right. The access
control table for `Orion.Nodes` in 2026.2:

| Operations | Required right |
|:---|:---|
| read | everyone |
| read, invoke | allowRealTimePolling |
| create, read, update, delete, invoke | manageNodes |

So an account with no special rights can read nodes (subject to its limitations), but it
needs `manageNodes` to add, change or remove one. Check any entity with:

```bash
python3 tools/schema_query.py show Orion.Nodes
```

A `401` means authentication failed. An operation refused because of a missing right is an
authorization failure, and the message will say so; do not chase credentials when the
account is simply not entitled.

## Worked example: PowerShell

`SwisPowerShell` maps the four operations onto four cmdlets:

| Operation | Cmdlet |
|:---|:---|
| Create | `New-SwisObject` |
| Read | `Get-SwisObject` |
| Update | `Set-SwisObject` |
| Delete | `Remove-SwisObject` |

Adding a node is the canonical example, and it shows why Create returning a URI matters: the
node's `NodeID` is assigned by the server, and you need it to attach pollers.

```powershell
Import-Module SwisPowerShell

$hostname = 'myorion.example.com'
$creds = Get-Credential
$swis  = Connect-Swis -Hostname $hostname -Credential $creds

# 1. Create the node. EngineID 1 is the primary polling engine.
$newNodeProps = @{
    IPAddress     = '10.0.0.1'
    EngineID      = 1
    ObjectSubType = 'SNMP'
    SNMPVersion   = 2
    DNS           = ''
    SysName       = ''
}
$newNodeUri = New-SwisObject $swis -EntityType 'Orion.Nodes' -Properties $newNodeProps
$newNodeUri
# swis://<system-identifier>/Orion/Orion.Nodes/NodeID=42
# The system identifier is whatever was tattooed into this Orion database when it was
# created, which is often not the hostname you connected to. See uris.md.

# 2. Read it back to get the server-assigned NodeID.
$nodeProps = Get-SwisObject $swis -Uri $newNodeUri
$nodeId = $nodeProps['NodeID']

# 3. Attach pollers. Orion.Pollers rows are what actually make Orion poll anything.
$poller = @{
    NetObject     = "N:$nodeId"
    NetObjectType = 'N'
    NetObjectID   = $nodeId
}

foreach ($type in @(
    'N.StatusAndResponseTime.ICMP.SendEcho',
    'N.Details.SNMP.Generic',
    'N.Uptime.SNMP.Generic'
)) {
    $poller['PollerType'] = $type
    New-SwisObject $swis -EntityType 'Orion.Pollers' -Properties $poller | Out-Null
}

# 4. Update a property on the node.
Set-SwisObject $swis -Uri $newNodeUri -Properties @{ Caption = 'core-sw-01' }

# 5. Delete it again.
Remove-SwisObject $swis -Uri $newNodeUri
```

Notes on what is verified and what is yours to choose:

- `IPAddress`, `EngineID`, `ObjectSubType`, `SNMPVersion`, `DNS`, `SysName` and `Caption`
  are all real `Orion.Nodes` properties in 2026.2. `PollerType`, `NetObject`,
  `NetObjectType` and `NetObjectID` are all real `Orion.Pollers` properties.
- `NetObjectType = 'N'` is the NetObject prefix for `Orion.Nodes`, which is why the
  `NetObject` string is `N:<NodeID>`. Interfaces use `I`, volumes use `V`.
- The three poller type strings appear in the official
  [Poller Types](https://solarwinds.github.io/OrionSDK/docs/poller-types/) reference. Which
  pollers a given device needs depends on the device; that reference is the list to work
  from. Older sample scripts use `N.Status.ICMP.Native` and `N.ResponseTime.ICMP.Native`,
  which do not appear in the current reference, so prefer the names above.
- Deleting the node in step 5 removes the test object. Leave that line out if you meant to
  keep it.

`Set-SwisObject` and `Remove-SwisObject` also accept URIs from the pipeline, which is the
easy way to apply one change across a query result:

```powershell
Get-SwisData $swis 'SELECT Uri FROM Orion.Nodes WHERE PollInterval = 300' |
    Set-SwisObject $swis -Properties @{ PollInterval = 120 }
```

`PollInterval` is a real `Orion.Nodes` property. For large sets, prefer the
[`BulkUpdate`](rest-api.md#bulkupdate) operation, which does the same job in one request
rather than one per URI.

## Worked example: Python

The official `orionsdk` client exposes the four operations as `create`, `read`, `update` and
`delete`, plus `bulkupdate` and `bulkdelete`.

```python
from orionsdk import SwisClient

swis = SwisClient(
    "myorion.example.com",
    "admin",
    "swordfish",
    verify="/etc/ssl/certs/orion-swis.pem",
)

# --- Read: find a node and its URI -------------------------------------------
rows = swis.query(
    "SELECT NodeID, Caption, Uri FROM Orion.Nodes WHERE IPAddress = @ip",
    ip="10.0.0.1",
)["results"]
if not rows:
    raise SystemExit("no such node")
node = rows[0]
node_uri = node["Uri"]
node_id = node["NodeID"]

# --- Create: attach a poller to that node ------------------------------------
poller_uri = swis.create(
    "Orion.Pollers",
    PollerType="N.Uptime.SNMP.Generic",
    NetObject=f"N:{node_id}",
    NetObjectType="N",
    NetObjectID=node_id,
)
print("created", poller_uri)
# created swis://<system-identifier>/Orion/Orion.Pollers/PollerID=7105

# --- Read: fetch the new poller's full property bag --------------------------
print(swis.read(poller_uri))
# The members are the entity's own properties (PollerID, PollerType, NetObject,
# NetObjectType, NetObjectID, Enabled) plus the ones inherited from System.Entity,
# which the official read example shows as DisplayName, Description, InstanceType
# and Uri.

# --- Update: partial, only the properties you name ---------------------------
swis.update(poller_uri, Enabled=False)

# --- Update through a navigation property: custom properties -----------------
swis.update(node_uri + "/CustomProperties", City="Serenity Valley")

# --- Delete ------------------------------------------------------------------
swis.delete(poller_uri)
```

`swis.create()` returns the parsed JSON body, which for a create is the URI string. `read()`
returns the property bag as a dict. `update()` and `delete()` return `None`, because SWIS
returns an empty `200` for both.

`Enabled` is a real `Orion.Pollers` property in 2026.2. `City` is a user-defined custom
property, so substitute one that exists on your server; a custom property must be created as
a definition before any node can carry a value for it.

## Common mistakes

**Trying to change data with a query.** There is no `UPDATE` statement in SWQL. If a
tutorial shows one, it is wrong.

**Sending the whole property bag back on update.** Read the entity, change one value, send
the whole dict back, and you will attempt to write read-only and server-computed properties
such as `Uri`, `InstanceType` and status fields. Send only what you are changing.

**Assuming a URI you built by hand is right.** Build URIs from `SELECT Uri` or from a Create
response wherever you can. See [uris.md](uris.md) for the format and its traps.

**Creating an entity when a verb is the real operation.** Putting a node into a maintenance
window is `Orion.Nodes.Unmanage`, not an update to `UnManaged`. Acknowledging an alert is
`Orion.AlertActive.Acknowledge`, not an update to `Orion.AlertActive`. Verbs exist precisely
because these operations have side effects, permission checks and audit trails that a
property write does not.

**One request per object.** If you are looping over hundreds of URIs applying the same
change, use `BulkUpdate` or `BulkDelete` instead. See
[rest-api.md](rest-api.md#bulkupdate).

## Next

- [uris.md](uris.md) for the URI format that three of these four operations depend on.
- [rest-api.md](rest-api.md) for the wire-level contract and the bulk operations.
- [connecting.md](connecting.md) for authentication and TLS.

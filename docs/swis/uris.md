# SWIS URIs

A SWIS URI is the identity of a single entity instance. It is the handle that the Read,
Update and Delete operations take, the value that `BulkUpdate` and `BulkDelete` accept in
their `uris` arrays, and the way Orion itself stores references to objects inside alerts,
reports and groups.

Grounded in the official [URIs](https://solarwinds.github.io/OrionSDK/docs/uris/) page.

## Finding a URI

Every entity type inherits a `Uri` property from `System.Entity`, so the easiest way to get
one is to select it:

```sql
SELECT Uri
FROM Orion.Nodes
WHERE IP = '8.8.8.8'
```

| Uri |
|:---|
| `swis://abcdef/Orion/Orion.Nodes/NodeID=1` |

`IP` is a real `Orion.Nodes` property. The other reliable source is the Create operation,
which returns the URI of the entity it just created; see [crud.md](crud.md).

Prefer both of those over building URIs by hand. A URI you selected is correct by
construction; a URI you assembled from string parts is correct only if every assumption you
made about the system identifier, the entity name and the key properties happens to hold.

## The format

```
swis://<system-identifier>/<endpoint>/<entity type>/<key filter>[/<nav property>[/<key filter>][…]]
```

Worked through with a real example:

```
swis://abcdef/Orion/Orion.Nodes/NodeID=1/Interfaces/InterfaceID=2
```

| Segment | Value in the example | What it is |
|:---|:---|:---|
| scheme | `swis` | Always `swis` |
| system identifier | `abcdef` | Identifies the Orion installation. See below. |
| endpoint | `Orion` | The SWIS endpoint. `Orion` in every example published by SolarWinds, including for IPAM and NCM entities. |
| entity type | `Orion.Nodes` | The fully qualified entity name |
| key filter | `NodeID=1` | The values of the entity's key properties |
| nav property | `Interfaces` | A navigation property on the preceding entity |
| key filter | `InterfaceID=2` | Selects one instance from the navigation |

The nav property and key filter pair can repeat, so a URI can walk several relationships
deep.

## The system identifier

This is the segment people get wrong, and it is worth understanding exactly.

From the official documentation:

> When you create a new Orion database, the system identifier is set to the FQDN of the
> server you are installing on and saved in the database. Even if that server is later
> renamed or replaced with a different one, this Orion database has been permanently
> tattooed with the system identifier that was set when it was created.

Three consequences follow, and all three matter in practice.

**It is not an address.** SWIS does not resolve or connect to the system identifier. You
reach SWIS by connecting to the host and port you chose in
[connecting.md](connecting.md); the URI's system identifier plays no part in routing. The
official documentation is explicit: "The system identifier is not used for addressing."

**It does not change, ever.** Rename the server, migrate the database to new hardware,
change the domain, and every existing URI still has the old identifier and still works. This
is deliberate. Alerts, reports and group definitions store URIs, so if the identifier tracked
the current hostname, every one of those saved references would break the day someone
renamed a server.

**Therefore, do not construct it from the hostname you connected to.** This is the classic
bug:

```python
# WRONG: assumes the system identifier equals the host you dialled
uri = f"swis://{hostname}/Orion/Orion.Nodes/NodeID={node_id}"
```

On a server that was renamed after installation, or that you reach by a CNAME, a load
balancer name or an IP address, this produces a URI that does not match anything. Select the
real one instead:

```python
rows = swis.query(
    "SELECT Uri FROM Orion.Nodes WHERE NodeID = @id", id=node_id
)["results"]
uri = rows[0]["Uri"]
```

If you genuinely need the identifier once, so you can build many URIs cheaply, derive it
from a URI you selected rather than from your connection settings:

```python
sample = swis.query("SELECT TOP 1 Uri FROM Orion.Nodes")["results"][0]["Uri"]
system_identifier = sample.split("/")[2]
```

You will notice in the official examples that the identifier is sometimes an FQDN with a
trailing dot (`dev-che-mjag-01.`) and sometimes an opaque string (`abcdef`). Treat it as an
opaque token.

## The key filter

The key filter names the entity's key properties and their values. For most entities that is
a single property:

```
swis://abcdef/Orion/Orion.Nodes/NodeID=1
swis://abcdef/Orion/Orion.Pollers/PollerID=6
swis://abcdef/Orion/Orion.Groups/ContainerID=9
```

`NodeID` is a real `Orion.Nodes` property, `PollerID` a real `Orion.Pollers` property, and
`ContainerID` a real `Orion.Groups` property (inherited from `Orion.Container`).

Composite keys are comma separated, with no spaces:

```
swis://abcdef/Orion/IPAM.Subnet/SubnetId=100,ParentId=2
swis://abcdef/Orion/Orion.APM.ComponentTemplateSetting/ComponentTemplateID=17,Key=<setting-key>
```

`SubnetId` and `ParentId` are both real `IPAM.Subnet` properties; `ComponentTemplateID` and
`Key` are both real `Orion.APM.ComponentTemplateSetting` properties, where `Key` is
described in the schema as "Unique string representation of the setting". The setting keys
themselves come from the template, so select them rather than guessing.

## Entities without key properties have no URI

Not every entity has a URI. From the official documentation:

> Not all SWIS entities have a Uri. SWIS does not define a URI for entity types without at
> least one key property defined, so you cannot use these entities with CRUD operations.

The schema says the same thing from the other direction. The summary of `System.Entity.Uri`
in 2026.2 reads: "All entity types have the Uri property which value is uniquely identifying
an entity instance in the system. The value may be blank if the entity type doesn't define
an identity for its instances."

So the `Uri` column always exists in a `SELECT`, and it comes back blank for entity types
that have no identity. That is the cheapest possible check on your own server:

```sql
SELECT TOP 1 Uri, InstanceType
FROM <SomeEntity>
```

If `Uri` is blank, that entity type cannot be addressed and therefore cannot be read,
updated or deleted through CRUD. Aggregate, statistical and reporting entities are the usual
cases.

### Finding an entity's key properties

The official documentation points at SWQL Studio: "You can view the key properties for an
entity type in the tree pane of SWQL Studio." That works, but it is not scriptable.

The scriptable answer is `Metadata.Property`, which carries an `IsKey` boolean:

```sql
SELECT Name, Type, IsKey
FROM Metadata.Property
WHERE Entity.FullName = 'Orion.Nodes' AND IsKey = true
```

`Name`, `Type` and `IsKey` are real `Metadata.Property` properties, and `Entity` is a real
navigation property on `Metadata.Property` leading to `Metadata.Entity`, whose `FullName` is
also real. That query tells you both how many key segments the URI will have and what order
to think about them in.

For the subset of entities that are also NetObject types, this repository ships their key
properties offline in `data/reference/netobject-types.json`, which records the key
properties for 112 of its 115 entries:

```bash
python3 -c "
import json
rows = json.load(open('data/reference/netobject-types.json'))
for r in rows:
    if r['entity'] == 'Orion.Nodes':
        print(r['entity'], r['netObjectPrefix'], r['keyProperties'])
"
# Orion.Nodes N ['NodeID']
```

## Navigating into a nav property

Appending a navigation property name walks the relationship, and appending a key filter
after it selects one instance from the other side.

```
swis://abcdef/Orion/Orion.Nodes/NodeID=1/Interfaces/InterfaceID=2
```

`Orion.Nodes.Interfaces` is a real navigation property in 2026.2, a `System.Hosting`
relationship leading to `Orion.NPM.Interfaces`, whose key property is `InterfaceID`. Confirm
any hop before you build a URI from it:

```bash
python3 tools/schema_query.py path Orion.Nodes Orion.NPM.Interfaces
```

which prints:

```
Orion.Nodes.Interfaces
  Orion.Nodes --Interfaces--> Orion.NPM.Interfaces
```

The same pattern works for volumes, which is what the official `BulkUpdate` example uses:

```
swis://dev-che-mjag-01./Orion/Orion.Nodes/NodeID=4/Volumes/VolumeID=1
```

`Orion.Nodes.Volumes` is a real navigation property leading to `Orion.Volumes`, whose key
property is `VolumeID`.

An important consequence: **the same entity instance can be named by more than one URI.**
Interface 2 on node 1 is reachable both directly and through its host node. SWQL provides
`UriEquals(a, b)` for exactly this, described in the official function reference as
"Returns true if SWIS Uri a refers to the same entity instance as SWIS Uri b." Use it rather
than comparing URI strings, because string equality will tell you two names for the same
object are different.

Note also that both directions of a relationship are navigable in SWQL.
`Orion.Nodes.Interfaces` goes from node to interfaces, and `Orion.NPM.Interfaces.Node` goes
from an interface back to its node. Both are real navigation properties.

## Navigating into CustomProperties

Custom property *values* live in a separate entity that hangs off the object, reached through
a navigation property called `CustomProperties`. To read or write them, address that:

```
swis://abcdef/Orion/Orion.Nodes/NodeID=1/CustomProperties
```

`Orion.Nodes.CustomProperties` is a real navigation property, a `System.Hosting` relationship
leading to `Orion.NodesCustomProperties`. The pattern nests, so an interface's custom
properties are reached by walking the node, then the interface, then `CustomProperties`:

```
swis://abcdef/Orion/Orion.Nodes/NodeID=8/Interfaces/InterfaceID=58/CustomProperties
```

`Orion.NPM.Interfaces.CustomProperties` is a real navigation property leading to
`Orion.NPM.InterfacesCustomProperties`. `Orion.Volumes.CustomProperties` exists too, leading
to `Orion.VolumesCustomProperties`.

Setting a value is an ordinary CRUD Update against that URI:

```powershell
$nodeId = 8
$uri = "swis://abcdef/Orion/Orion.Nodes/NodeID=$($nodeId)/CustomProperties"
Set-SwisObject $swis -Uri $uri -Properties @{ Comments = 'Custom comment' }
```

```python
swis.update(node_uri + "/CustomProperties", Comments="Custom comment")
```

The property names in that hash table are whatever custom properties your installation
defines, so they are not schema facts you can look up here. `Orion.NodesCustomProperties`
declares only `NodeID` in the published schema, because the rest are added per installation.
Query what exists on your server before you write:

```sql
SELECT Name, Type
FROM Metadata.Property
WHERE Entity.FullName = 'Orion.NodesCustomProperties'
ORDER BY Name
```

Note that `Orion.NodesCustomProperties` supports read, update and invoke, but not create or
delete. You cannot create a custom property value row, because it exists as long as the node
does. See [crud.md](crud.md#not-every-entity-supports-crud).

## Using URIs in REST paths

The URI goes straight into the path after the base path, unencoded, exactly as the official
examples show it:

```text
GET https://localhost:17774/SolarWinds/InformationService/v3/Json/swis://tdanner-dev.swdev.local/Orion/Orion.Pollers/PollerID=6
```

The result is a URL with `swis://` embedded in its path. That looks wrong and is not; it is
what the service expects. Some HTTP clients and proxies normalise consecutive slashes or
percent-encode path segments, which will break these requests. If Read, Update or Delete
fail while `/Query` works, the URI handling in your HTTP layer is the first thing to check.

For bulk operations the URIs go into a JSON array in the body instead, where no encoding
question arises:

```json
{
  "uris": [
    "swis://abcdef/Orion/Orion.Nodes/NodeID=81/CustomProperties",
    "swis://abcdef/Orion/Orion.Nodes/NodeID=82/CustomProperties"
  ],
  "properties": { "City": "Serenity Valley" }
}
```

## Escaping values inside a URI

SWQL has an `EscapeSWISUriValue(a)` function, documented as returning the argument "with
certain characters escaped". The official function reference marks it "Intended for internal
use only", so do not build a URI-escaping strategy around it. If a key value contains
characters that need escaping, select the entity's `Uri` and use what SWIS gives you rather
than assembling one yourself.

## Worked example: from a query to a change

The whole pattern, end to end, without ever hand-building a URI:

```python
from orionsdk import SwisClient

swis = SwisClient("myorion.example.com", "admin", "swordfish",
                  verify="/etc/ssl/certs/orion-swis.pem")

# 1. Select the URIs of the objects you care about.
rows = swis.query("""
    SELECT NodeID, Caption, Uri
    FROM Orion.Nodes
    WHERE Vendor = @vendor AND Status = @status
    ORDER BY NodeID
""", vendor="Cisco", status=2)["results"]

# 2. Derive the CustomProperties URIs by appending the navigation property.
cp_uris = [r["Uri"] + "/CustomProperties" for r in rows]

# 3. Apply one change to all of them in a single request.
if cp_uris:
    swis.bulkupdate(cp_uris, Comments="Reviewed 2026-08-21")
```

Step 2 is the one place a URI is extended by hand, and it is safe because the only thing
being appended is a navigation property name verified against the schema. The system
identifier, entity type and key filter all came from the server.

## Common mistakes

**Building the system identifier from the connection hostname.** Covered above. It is the
single most common URI bug.

**Comparing URIs as strings.** Use `UriEquals(a, b)` when you need to know whether two URIs
name the same instance.

**Assuming a single key property.** Composite keys are comma separated. Check with
`Metadata.Property` and `IsKey` before assuming.

**Assuming every entity has a URI.** Entities with no key properties return a blank `Uri`
and cannot be used with CRUD.

**Percent-encoding the URI in a REST path.** The official examples pass it raw.

## Next

- [crud.md](crud.md) for the operations that consume these URIs.
- [rest-api.md](rest-api.md) for the wire format, including the bulk operations.
- [README.md](README.md) for how the four SWIS interfaces fit together.

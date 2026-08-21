# Bulk operations

`BulkUpdate` and `BulkDelete` apply one change to many entities in a single request. They
are the right tool when you are setting the same property across hundreds of objects, or
cleaning up a large set, and the wrong tool almost everywhere else.

Both are part of the CRUD surface and both address entities by [URI](uris.md).

## The contract

Two routes, both POST, both taking a JSON body:

```text
POST /SolarWinds/InformationService/v3/Json/BulkUpdate
{
  "uris": ["swis://orion./Orion/Orion.Nodes/NodeID=1", "..."],
  "properties": { "Location": "Datacentre B" }
}
```

```text
POST /SolarWinds/InformationService/v3/Json/BulkDelete
{
  "uris": ["swis://orion./Orion/Orion.Nodes/NodeID=1", "..."]
}
```

`uris` and `properties` are both required for `BulkUpdate`; `uris` alone for `BulkDelete`.
The properties you send must match the properties of the entity type being updated, which
means a single bulk call cannot span entity types that do not share the property you are
setting.

A successful call to either returns an **empty response**. There is no per-URI result, no
count, and no partial-success report. That absence shapes how you should use them, and it
is the single most important thing on this page.

## Because there is no per-item result, verify afterwards

A bulk call that succeeds tells you the request was accepted. It does not tell you that
every URI in it was valid, or that every entity actually changed. Treat the read-back as
part of the operation rather than as an optional check:

```sql
SELECT NodeID, Caption, Location
FROM Orion.Nodes
WHERE NodeID IN @ids
```

If the count or the values do not match what you sent, you know now rather than in a
month when someone asks why the report is wrong.

## Building the URI list

Get the URIs from the same query that defines your target set. Do not construct them by
string formatting: the system identifier component is fixed per installation and is not
something to guess.

```sql
SELECT Uri
FROM Orion.Nodes
WHERE Location = 'Datacentre A'
  AND Vendor = 'Cisco'
```

`Uri` is inherited from `System.Entity`, so it is available on any entity that has key
properties. Entities without key properties have no URI and therefore cannot take part in
CRUD or bulk operations at all. See [uris.md](uris.md).

## PowerShell

The `SwisPowerShell` module does not wrap the bulk routes as their own cmdlets, so the
usual pattern is to select the URIs and pipe them into `Set-SwisObject`, which issues one
update per entity:

```powershell
$swis = Connect-Swis -Hostname orion.example.com -Trusted

# Confirm the target set BEFORE changing anything. This is not optional ceremony:
# a bulk update against the wrong filter is tedious to reverse.
$targets = Get-SwisData $swis @'
SELECT Uri, Caption, Location
FROM Orion.Nodes
WHERE Location = 'Datacentre A'
'@

$targets | Format-Table Caption, Location
Read-Host "Press enter to update $($targets.Count) node(s), or Ctrl-C to stop"

foreach ($node in $targets) {
    Set-SwisObject $swis -Uri $node.Uri -Properties @{ Location = 'Datacentre B' }
}
```

That is one request per node rather than one request in total, which is slower but gives
you a failure at the exact entity that rejected the change. For a few hundred objects the
clarity is usually worth more than the round trips.

## Python

To use the bulk routes properly, call them directly:

```python
from orionsdk import SwisClient

swis = SwisClient("orion.example.com", "admin", password)

targets = swis.query(
    "SELECT Uri, Caption FROM Orion.Nodes WHERE Location = @loc",
    loc="Datacentre A",
)["results"]

uris = [row["Uri"] for row in targets]
print(f"about to update {len(uris)} node(s)")

# One request for the whole set.
swis.bulkupdate(uris, Location="Datacentre B")

# Verify, because the response told you nothing about individual entities.
check = swis.query(
    "SELECT Caption, Location FROM Orion.Nodes WHERE Uri IN @uris",
    uris=uris,
)["results"]
wrong = [r for r in check if r["Location"] != "Datacentre B"]
print(f"{len(check)} read back, {len(wrong)} did not take the change")
```

The repository's own [swis_client.py](../../scripts/python/swis_client.py) exposes
`bulk_update` and `bulk_delete` against the raw routes if you would rather not add a
dependency.

## Batch size

There is no documented maximum, and that is not the same as there being none. A very
large `uris` array becomes a large request body, a long-running transaction, and a large
amount of work the database does with your lock. Batch in the low hundreds and iterate:

```python
def chunks(items, size=250):
    for i in range(0, len(items), size):
        yield items[i:i + size]

for batch in chunks(uris):
    swis.bulkupdate(batch, Location="Datacentre B")
```

Smaller batches also mean a failure costs less. If batch seven of twenty fails you have
six batches applied and thirteen untouched, which is a much easier position to reason
about than one opaque failure across the whole set.

## When not to use bulk

**When a verb exists for what you are doing.** Setting `UnManaged = true` through
`BulkUpdate` is not the same as unmanaging a node. `Orion.Nodes.Unmanage` writes the
maintenance window, stops the pollers on the right engine, and applies the change
consistently to the objects underneath. The property update writes one column. Reach for
[invoke-verbs.md](invoke-verbs.md) first and use CRUD only when no verb covers the change.

**When the entities are different types.** The `properties` object is applied to every
URI, so mixing `Orion.Nodes` and `Orion.NPM.Interfaces` in one call only works for a
property both declare. Split by type instead.

**When you need to know which items failed.** The empty response makes bulk a poor fit
for anything where per-item outcome matters. Loop and handle errors individually.

**When you are deleting.** `BulkDelete` works, and that is exactly the problem. There is
no undo, no confirmation, and no report of what went. Read the set first, keep a record of
what you are about to remove, and be certain the filter is right:

```sql
SELECT NodeID, Caption, IPAddress, Uri
FROM Orion.Nodes
WHERE Caption LIKE 'decom-%'
```

Export that result before you act on it. A deleted node takes its historical statistics
with it.

## Permissions

Bulk operations respect the same access control as the equivalent single-entity
operations, and account limitations still apply. An account that cannot see a node cannot
bulk-update it, and a URI it cannot reach is not an error you will necessarily be told
about, given the empty response. Run the read-back as the same account.

## See also

- [crud.md](crud.md) for single-entity create, read, update and delete
- [uris.md](uris.md) for the URI format and how to obtain one
- [invoke-verbs.md](invoke-verbs.md) for changes that need a verb rather than a property write
- [../automation/README.md](../automation/README.md) for task-level automation guides

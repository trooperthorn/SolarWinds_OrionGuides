# Automation against SWIS

The pages in this section are task guides. Each one takes something an operator does by
hand in the web console, works out which SWIS interface expresses it, and shows the whole
flow: the query that defines the scope, the write that makes the change, and the query that
proves it happened.

This page is the method those guides follow. Read it once; it is the part that keeps a
script from doing something expensive to the wrong three hundred nodes.

## Pick the interface before you write anything

SWIS exposes four ways to touch data, and choosing the wrong one is the most common reason
an automation ends up complicated.

| Interface | Route | Use it for | Cannot |
|:---|:---|:---|:---|
| Query | `POST /Query` | Reading anything, including the scope of a change | Change anything. It is read only. |
| CRUD | `POST /Create/{Entity}`, then `GET`, `POST` or `DELETE` on `/{uri}` | Setting property values on one entity instance, creating and deleting instances | Express an operation that is more than a set of property assignments |
| Invoke | `POST /Invoke/{Entity}/{Verb}` | Named operations: `Unmanage`, `PollNow`, `Acknowledge`, `CreateCustomProperty` | Be discovered by guessing. Verb names and argument order must be looked up. |
| Bulk | `POST /BulkUpdate`, `POST /BulkDelete` | The same property change or deletion across many URIs in one request | Report per-item results. A success means "accepted", not "all applied". |

The decision procedure is short:

1. **Does the thing you want have a name in the web console?** "Unmanage", "Poll Now",
   "Rediscover", "Acknowledge", "Add Custom Property". If so, there is probably a verb, and
   the verb does work that a property assignment cannot. Look first:
   `python3 tools/schema_query.py verbs --entity Orion.Nodes`.
2. **Otherwise, is it a property value?** Then it is CRUD, against the entity's URI.
3. **Are you doing step 2 to many objects with the same value?** Then it is `BulkUpdate`,
   with the read-back treated as part of the operation.

`Orion.Nodes.Unmanage` is the example worth internalising. Unmanaging a node is not "set
`UnManaged = true`". One call has to set `UnManaged`, `UnManageFrom` and `UnManageUntil`,
move the node to status `9`, and stop collection for the window. Doing that through CRUD
means reimplementing part of the platform, and getting it subtly wrong. See
[maintenance-mode.md](maintenance-mode.md).

Full mechanics for each interface: [../swis/rest-api.md](../swis/rest-api.md),
[../swis/crud.md](../swis/crud.md), [../swis/invoke-verbs.md](../swis/invoke-verbs.md),
[../swis/bulk-operations.md](../swis/bulk-operations.md).

## Look the names up. Every time.

Entity names, property names, verb names and verb argument order are the four things that
are easiest to get plausibly wrong. `Orion.Node` instead of `Orion.Nodes`. A property that
exists on a sibling entity but not this one. An argument list that is off by one because a
release inserted a parameter.

Everything is in `data/`, and each lookup is one command:

```bash
python3 tools/schema_query.py find snmp version --properties
python3 tools/schema_query.py show Orion.Nodes
python3 tools/schema_query.py props Orion.Nodes --grep unmanage
python3 tools/schema_query.py verbs --entity Orion.Nodes
python3 tools/schema_query.py verb Orion.Nodes Unmanage
```

Against a live server that is on some other version, the same answers come from the
`Metadata` namespace, which is the authority for that server:

```sql
SELECT FullName, CanCreate, CanRead, CanUpdate, CanDelete, CanInvoke
FROM Metadata.Entity
WHERE FullName = 'Orion.Nodes'
```

```sql
SELECT Position, Name, Type, IsOptional
FROM Metadata.VerbArgument
WHERE EntityName = 'Orion.Nodes' AND VerbName = 'Unmanage'
ORDER BY Position
```

See [../swis/metadata-introspection.md](../swis/metadata-introspection.md).

## Write the SELECT first, and make it the scope

This is the single habit that separates an automation you can run on a Friday from one you
cannot. **The set of objects a script changes must be produced by a query you have already
run and read.**

Do it in this order:

```sql
-- 1. The scope, as a query. Run it. Look at the rows. Count them.
SELECT n.NodeID, n.Caption, n.IPAddress, n.Vendor, n.Location
FROM Orion.Nodes n
WHERE n.Vendor = @vendor
  AND n.Location = @location
ORDER BY n.Caption
```

```sql
-- 2. The same filter, returning URIs, because URIs are what the write interfaces take.
SELECT n.Uri
FROM Orion.Nodes n
WHERE n.Vendor = @vendor
  AND n.Location = @location
```

```sql
-- 3. After the write, the same filter again, returning the property you changed.
SELECT n.NodeID, n.Caption, n.Location
FROM Orion.Nodes n
WHERE n.NodeID IN @ids
```

Two things make this work rather than just feel careful:

- **Never build URIs by string formatting.** The system identifier component of a URI is
  fixed per installation when the database is created and does not necessarily match the
  server's current name. Ask for `Uri` in the same query that defines the scope. See
  [../swis/uris.md](../swis/uris.md).
- **Never re-derive the scope between the SELECT and the write.** If the script queries for
  captions, then separately queries for URIs with a slightly different `WHERE`, the two sets
  can differ. Select the identifying columns and the `Uri` together, in one pass.

## Bind parameters, do not concatenate

Every query above uses `@name` placeholders. Both the REST `Query` route and the PowerShell
and Python clients carry a parameter map alongside the query text.

```python
rows = swis.query(
    "SELECT NodeID, Caption, Uri FROM Orion.Nodes WHERE Vendor = @vendor",
    vendor="Cisco",
)["results"]
```

```powershell
Get-SwisData $swis 'SELECT NodeID, Caption, Uri FROM Orion.Nodes WHERE Vendor = @vendor' `
    @{ vendor = 'Cisco' }
```

Binding is not only about injection, although a caption containing an apostrophe will break
a concatenated query on the first day you run it. Bound queries reuse the SQL Server
execution plan, so a script that runs the same shape a thousand times with different values
compiles once instead of a thousand times.

SWQL also binds a **multi-valued** parameter, which is how you feed the output of step 1
back into step 3 without building a comma-separated list:

```sql
SELECT n.NodeID, n.Caption, n.Location
FROM Orion.Nodes n
WHERE n.NodeID IN @ids
```

## Be careful in a specific way, not a general way

"Be careful with writes" is not actionable. These are:

- **Dry run by default.** Make the destructive step opt-in. SolarWinds' own
  `Update.Captions.ps1` sample ships with the `Set-SwisObject` line commented out and tells
  you to uncomment it once the preview output looks right. That is a good default for
  anything you write. In PowerShell, `[CmdletBinding(SupportsShouldProcess)]` gives you
  `-WhatIf` for free.
- **Bound the blast radius numerically.** If the scope query returns more rows than you
  expected, stop. A script that changes every node because a `WHERE` clause matched `NULL`
  differently than you assumed is the normal way this goes wrong.
- **Prefer the reversible operation.** Unmanaging a node is reversible with one call.
  Deleting it is not, and it takes its history with it. When the goal is "stop this thing
  alerting", the answer is almost never `DELETE`.
- **Verify with a query, not with the response body.** A verb declared as returning
  `System.Void` gives you nothing to parse, and a bulk call returns an empty body with no
  per-item result. Treat the read-back as part of the operation.
- **Make it idempotent where you can.** Re-running should converge, not accumulate. Check
  the current value before setting it, so a rerun after a partial failure is safe.
- **Batch, do not blast.** Bulk routes accept large URI lists, but a very large single
  request is one transaction that either takes a long time or fails as a unit. Chunking into
  batches of a few hundred gives you partial progress and a smaller thing to retry.

## Verb arguments are positional

Names appear in the schema, in the Swagger contract and in this repository's data. They
never travel on the wire. Both the REST body and `Invoke-SwisVerb` send an ordered array, so
**argument order is the entire contract**, and passing the right values in the wrong slots is
a bug no client can detect for you.

```bash
python3 tools/schema_query.py verb Orion.Nodes Unmanage
```

```text
Orion.Nodes.Unmanage
  requires: allowUnmanage
  parameters (5):
    netObjectId: string (required)
    unmanageTime: string (required)
    remanageTime: string (required)
    isRelative: boolean (required)
    allowOverlapping: boolean (optional)
```

This matters most across upgrades. A release that inserts a parameter in the middle of a
list leaves your call with the right *number* of arguments going into the wrong slots. The
generated change reports flag exactly this:
[../reference/schema-changes-2026.1-to-2026.2.md](../reference/schema-changes-2026.1-to-2026.2.md).

Two related details that bite:

- **`netObjectId` usually wants a NetObject string, but read the declared type.** Node 42
  is `N:42`, interface 58 is `I:58`, volume 9 is `V:9`, and the prefix table is
  [../reference/netobject-types.md](../reference/netobject-types.md). The name is not the
  contract, though: of the 21 verbs taking a `netObjectId`, 12 declare it `string` and want
  that form, while nine declare it `number` and want the bare integer key. The nine are
  `GetSupportedMetrics`, `StartRealTimePolling` and `StopRealTimePolling` on each of
  `Orion.Nodes`, `Orion.NPM.Interfaces` and `Orion.Volumes`, so the same entity can take
  both forms depending on the verb. Check with
  `python3 tools/schema_query.py verb <Entity> <Verb>`.
- **Times are handled in UTC.** Convert explicitly rather than relying on the caller's
  locale. See [../swql/date-and-time.md](../swql/date-and-time.md).

## Permission failures usually are not bugs

Verbs declare the right they require, and the schema records it. `Orion.Nodes.Unmanage`
requires `allowUnmanage`; `PollNow`, `PollStatusNow` and `RediscoverNow` require
`manageNodes`; the custom property verbs on `Orion.NodesCustomProperties` are gated on
`admin` at the entity level. When a call fails with a permission error, check the right
before you check your code.

The subtler one is **account limitations**, which silently filter query *results*. Two
accounts running the same query get different rows. "The query returns nothing" is often a
permissions problem rather than a data problem, and it will not raise an error. When a
service account sees fewer rows than your admin session, that is the first thing to check.

## Read errors before retrying

- **401** is authentication. Wrong credentials, or the account is disabled.
- **403** is authorisation. The account authenticated but lacks the right the verb declares.
- **400** with a message body is usually a contract problem: a wrong argument count, a value
  that will not coerce to the declared type, or a property name that does not exist on the
  entity. SWIS returns its error text in a JSON `Message` field, so surface it rather than
  swallowing it.
- **A connection failure** on port 17778 means you are on the deprecated port. REST is
  **17774** from platform release 2023.1 onward. See
  [../swis/connecting.md](../swis/connecting.md).

## Validate your SWQL before you ship it

This repository ships a parser that resolves every dotted reference against the schema:

```bash
echo "SELECT n.Caption, n.Node.Foo FROM Orion.Nodes n" | python3 tools/validate_swql.py -
```

```text
<stdin>
  ERROR: Orion.Nodes has no property or navigation property named 'Node'. Closest members: nodeid, asanode, npmnode.
      in: n.Node.Foo
```

It reads `.swql`, `.md`, `.ps1`, `.py` and `.sh`, so a query embedded in a script is checked
too. One caveat that comes up constantly in this section: **custom property names cannot be
validated**, because they are created per installation and are not in the published schema.
Queries in these pages that use example custom property names are shown as plain text for
that reason.

## The guides

| Page | Task |
|:---|:---|
| [node-management.md](node-management.md) | Add, find, update, repoll, move and delete nodes |
| [maintenance-mode.md](maintenance-mode.md) | Unmanage and remanage, for planned work |
| [custom-properties.md](custom-properties.md) | Define, populate and query custom properties |
| [pollers.md](pollers.md) | Why a new node monitors nothing until pollers are assigned |
| [alerts.md](alerts.md) | Active alerts, acknowledgement, definitions, suppression |
| [dependencies.md](dependencies.md) | Suppressing downstream alerts during an outage |
| [discovery.md](discovery.md) | Network sonar discovery and list resources |
| [events-and-auditing.md](events-and-auditing.md) | What happened, and who changed it |
| [credentials.md](credentials.md) | Credential entities and their security posture |
| [accounts-and-permissions.md](accounts-and-permissions.md) | Accounts, roles, rights, account limitations |
| [reporting.md](reporting.md) | Reports and scheduled exports |
| [scheduling.md](scheduling.md) | Scheduled tasks and maintenance plans |
| [high-availability.md](high-availability.md) | HA pools |

Runnable versions of several of these flows live in
[../../scripts/powershell/](../../scripts/powershell/README.md),
[../../scripts/python/](../../scripts/python/README.md) and
[../../scripts/curl/](../../scripts/curl/README.md).

## Official sources

SolarWinds publishes the SDK documentation and the sample scripts that these guides adapt:

- [OrionSDK documentation](https://solarwinds.github.io/OrionSDK/)
- [OrionSDK wiki](https://github.com/solarwinds/OrionSDK/wiki)
- [Sample scripts](https://github.com/solarwinds/OrionSDK/tree/master/Samples)

Where a sample script and this schema data disagree, the data wins for 2026.2 and the page
says so. The samples are maintained across many releases, so a property they set may have
moved to a different entity since.

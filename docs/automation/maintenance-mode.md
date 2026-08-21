# Maintenance mode: unmanaging and remanaging

"Put these nodes in maintenance for the change window" is the most common thing anyone asks
an Orion automation to do. It maps to two verbs, `Unmanage` and `Remanage`, and to three
inherited properties, `UnManaged`, `UnManageFrom` and `UnManageUntil`.

The mechanics are simple. The parts that go wrong are the argument format, the timezone, and
choosing unmanage when you actually wanted alert suppression.

## What unmanaging does, and what it costs

An unmanaged object is not polled. SolarWinds' own
[Unmanaging Entities](https://solarwinds.github.io/OrionSDK/docs/unmanaging-entities/) page
puts it plainly:

> During this period no data will be collected for that entity - no up/down status, no
> response time, etc. There will be a gap in charts for this time.

That gap is the cost, and it is the reason to think for a second before reaching for
unmanage. The object moves to status `9`, `Unmanaged`, whose rank in `Orion.StatusInfo` is
`499`, and it stops producing the data that availability and response-time charts are drawn
from.

**If you want data but not alerts, use alert suppression instead.** `Orion.AlertSuppression`
exists for exactly this. It takes entity **URIs** rather than NetObject ids, which is the
first thing to notice when switching between the two:

| Verb | Signature | Right |
|:---|:---|:---|
| `Orion.AlertSuppression.SuppressAlerts` | `(entityUris, suppressFrom?, suppressUntil?, allowOverlapping?, reason?)` | `allowUnmanage` |
| `Orion.AlertSuppression.ResumeAlerts` | `(entityUris)` | `allowUnmanage` |
| `Orion.AlertSuppression.GetAlertSuppressionState` | `(entityUris)` | `everyone` |

Only `entityUris` is required on `SuppressAlerts` in 2026.2; the other four are optional.
SolarWinds'
[`AlertSuppression.ps1`](https://github.com/solarwinds/OrionSDK/blob/master/Samples/PowerShell/AlertSuppression.ps1)
sample calls it with two arguments, `@($entityUris, [DateTime]::UtcNow)`, which still works
because positions 2 to 4 are optional.

The trade is exact: unmanage stops polling and therefore stops alerts as a side effect;
suppression stops alerts and keeps polling. Choose by whether you want the chart to have a
hole in it. See [alerts.md](alerts.md).

## The verb, exactly as the schema declares it

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
```

| # | Parameter | Type | What to pass |
|---:|:---|:---|:---|
| 0 | `netObjectId` | string | The NetObject string. Node 42 is `N:42`. Not a bare integer. |
| 1 | `unmanageTime` | string | When the window opens. Handled as UTC. A time in the past takes effect immediately. |
| 2 | `remanageTime` | string | When the window closes. Meaning depends on `isRelative`. |
| 3 | `isRelative` | boolean | `false` for two absolute times. `true` reinterprets `remanageTime` as a duration. |
| 4 | `allowOverlapping` | boolean | Optional. Whether to accept a window that overlaps one already scheduled. |

`Remanage` is the other half and takes one argument:

```text
Orion.Nodes.Remanage(netObjectId) -> System.Void
  Enables polling on node if it was unmanaged before
  requires: allowUnmanage
```

Both require the **`allowUnmanage`** right. A `403` here is almost always a missing right
rather than a broken call.

Note that the official SDK page documents a four-argument form,
`Unmanage(netObjectId, unmanageFrom, unmanageUntil, isRelative)`. In 2026.2 the schema
declares a fifth, optional parameter, `allowOverlapping`. Since it is optional, four-argument
calls written against the older documentation still work.

### netObjectId is a NetObject string

This is the most frequent single mistake. The prefix comes from the object type, not from the
entity name:

| Entity | Prefix | Key property | Example |
|:---|:---|:---|:---|
| `Orion.Nodes` | `N` | `NodeID` | `N:42` |
| `Orion.NPM.Interfaces` | `I` | `InterfaceID` | `I:58` |
| `Orion.Volumes` | `V` | `VolumeID` | `V:9` |
| `Orion.APM.Application` | `AA` | `ApplicationID` | `AA:317` |
| `Orion.SEUM.Transactions` | `T` | `TransactionId` | `T:4` |

The schema documentation for `Orion.NPM.Interfaces.Unmanage` states the format in its own
parameter description: "Id of net object (interface) to unmanage. Example:'I:1'." The full
prefix table is [../reference/netobject-types.md](../reference/netobject-types.md).

### The times are UTC

`unmanageTime` and `remanageTime` are handled in UTC. The official example builds them from
`[DateTime]::UtcNow`, and the SDK page describes both as "the date and time (in UTC)".

Convert explicitly in your own code rather than relying on the caller's locale. A window that
opens at the wrong hour, in the wrong direction, discovered the morning after a change, is
the normal failure:

```powershell
# Right: explicit conversion.
$startUtc = [datetime]::UtcNow
$endUtc   = $startUtc.AddHours(4)

# Also right: a local wall-clock time converted at the boundary.
$endUtc = ([datetime]'2026-09-02 02:00').ToUniversalTime()

# Wrong: local time sent as if it were UTC.
$endUtc = [datetime]'2026-09-02 02:00'
```

```python
from datetime import datetime, timedelta, timezone

start = datetime.now(timezone.utc)
end = start + timedelta(hours=4)
swis.invoke("Orion.Nodes", "Unmanage", "N:42", start.isoformat(), end.isoformat(), False, False)
```

The PowerShell client serialises a `[datetime]` for you, so passing the object is fine.
Over raw REST, send an ISO 8601 string.

### What isRelative changes

With `isRelative = false`, which is what you want almost always, `unmanageTime` and
`remanageTime` are two absolute instants and the window is the span between them.

With `isRelative = true`, `remanageTime` stops being an instant. The schema's own description
on `Orion.NPM.Interfaces.Unmanage` is precise: "If is true that remanageTime will be
unmanageTime + remanageTime.TimeOfDay." The official page says the same thing from the other
side: "the date portion will be ignored and the time portion will be treated as a
*duration*."

So `isRelative = true` with a `remanageTime` of `2026-01-01T04:30:00Z` means "four hours and
thirty minutes after the start", and the `2026-01-01` is thrown away. It follows from that
description, rather than from any separately documented limit, that a duration expressed this
way cannot exceed 24 hours: it is carried in a time-of-day, and a time-of-day does not go past
23:59:59.

SolarWinds' own recommendation, from the same page, is to avoid it: "I recommend passing
`false` for `isRelative` - it makes the scripts more clear and consistent." Compute the end
time yourself and pass two absolute UTC values. Every example below does that.

### What allowOverlapping is for

Scheduling a second window over an existing one is refused unless you pass `true`. Leave it
`false` so that a rerun of a script does not quietly stack windows on the same node, and set
it deliberately when you genuinely mean to extend a window that is already open.

## Recipe: a fixed window for planned work

The change starts at 22:00 local and ends at 02:00 the next morning. Convert both ends once,
at the boundary, and pass absolute times.

```powershell
Import-Module SwisPowerShell
$swis = Connect-Swis -Hostname 'orion.example.com' -Trusted

$nodeId   = 42
$startUtc = ([datetime]'2026-09-01 22:00').ToUniversalTime()
$endUtc   = ([datetime]'2026-09-02 02:00').ToUniversalTime()

Invoke-SwisVerb $swis 'Orion.Nodes' 'Unmanage' @(
    "N:$nodeId",
    $startUtc,
    $endUtc,
    $false,      # isRelative: two absolute times
    $false       # allowOverlapping
) | Out-Null
```

```python
from datetime import datetime, timezone

start = datetime(2026, 9, 1, 21, 0, tzinfo=timezone.utc)   # 22:00 in UTC+01:00
end = datetime(2026, 9, 2, 1, 0, tzinfo=timezone.utc)

swis.invoke(
    "Orion.Nodes", "Unmanage",
    "N:42", start.isoformat(), end.isoformat(), False, False,
)
```

```bash
curl -sS -X POST \
  -u 'svc-automation:...' \
  --cacert /etc/ssl/certs/orion-swis.pem \
  -H 'Content-Type: application/json' \
  -d '["N:42","2026-09-01T21:00:00Z","2026-09-02T01:00:00Z",false,false]' \
  'https://orion.example.com:17774/SolarWinds/InformationService/v3/Json/Invoke/Orion.Nodes/Unmanage'
```

Then confirm, because the verb returns `System.Void` and tells you nothing:

```sql
SELECT n.NodeID, n.Caption, n.UnManaged, n.UnManageFrom, n.UnManageUntil, n.Status
FROM Orion.Nodes n
WHERE n.NodeID = @nodeId
```

If the window is scheduled but has not opened yet, `UnManaged` is still `false` while
`UnManageFrom` and `UnManageUntil` hold the future window. That is expected, not a failure.

## Recipe: unmanage now, for N hours

The common interactive case. Start "now" so the window opens immediately, and compute the end
rather than using `isRelative`.

```powershell
$hours    = 4
$startUtc = [datetime]::UtcNow
$endUtc   = $startUtc.AddHours($hours)

Invoke-SwisVerb $swis 'Orion.Nodes' 'Unmanage' @(
    "N:$nodeId", $startUtc, $endUtc, $false, $false
) | Out-Null
```

A ready-made version with `-WhatIf`, group input and an automatic read-back is in
[../../scripts/powershell/Set-NodeMaintenanceWindow.ps1](../../scripts/powershell/Set-NodeMaintenanceWindow.ps1).

The `isRelative = true` equivalent, shown so you recognise it in someone else's script rather
than because you should write it:

```powershell
# Same four-hour window, expressed as a duration. The 2000-01-01 is discarded;
# only the 04:00:00 time-of-day is used.
Invoke-SwisVerb $swis 'Orion.Nodes' 'Unmanage' @(
    "N:$nodeId", [datetime]::UtcNow, ([datetime]'2000-01-01 04:00:00'), $true, $false
) | Out-Null
```

## Recipe: remanage early

The change finished ahead of schedule. `Remanage` ends the window immediately, regardless of
what `UnManageUntil` says.

```powershell
Invoke-SwisVerb $swis 'Orion.Nodes' 'Remanage' @("N:$nodeId") | Out-Null
```

```python
swis.invoke("Orion.Nodes", "Remanage", "N:42")
```

Remanaging is idempotent in the sense that matters: calling it on a node that is already
managed is not a state change worth defending against. What is worth doing is polling
immediately afterwards, so the console reflects reality instead of waiting for the next
cycle:

```powershell
Invoke-SwisVerb $swis 'Orion.Nodes' 'Remanage'      @("N:$nodeId") | Out-Null
Invoke-SwisVerb $swis 'Orion.Nodes' 'PollStatusNow' @("N:$nodeId") | Out-Null
```

`PollStatusNow` requires `manageNodes`, which is a different right from `allowUnmanage`. A
service account that can unmanage cannot necessarily poll. See
[node-management.md](node-management.md).

## Recipe: bulk unmanage driven by a query

There is no bulk unmanage verb. `BulkUpdate` cannot substitute, because unmanaging is not a
property assignment. You loop, one `Invoke` per object, over a set that a query defined.

The discipline from [README.md](README.md) applies with full force here: run the SELECT,
read the rows, count them, and only then write.

```powershell
Import-Module SwisPowerShell
$swis = Connect-Swis -Hostname 'orion.example.com' -Trusted

# 1. The scope. Run this on its own first and look at what comes back.
$targets = Get-SwisData $swis @'
SELECT cm.MemberPrimaryID AS NodeID, cm.Name
FROM Orion.ContainerMembers cm
WHERE cm.Container.Name = @groupName
  AND cm.MemberEntityType = 'Orion.Nodes'
ORDER BY cm.Name
'@ @{ groupName = 'DC2 Migration' }

$targets | Format-Table NodeID, Name
Write-Warning "About to unmanage $($targets.Count) node(s)."

# 2. One window, computed once, so every node gets exactly the same one.
$startUtc = [datetime]::UtcNow
$endUtc   = $startUtc.AddHours(8)

# 3. The writes, with per-object error handling so one bad id does not stop the run.
$failed = @()
foreach ($t in $targets) {
    try {
        Invoke-SwisVerb $swis 'Orion.Nodes' 'Unmanage' @(
            "N:$($t.NodeID)", $startUtc, $endUtc, $false, $false
        ) | Out-Null
    }
    catch {
        $failed += [pscustomobject]@{ NodeID = $t.NodeID; Name = $t.Name; Error = $_.Exception.Message }
    }
}

# 4. Verification, from the data rather than from the loop's own bookkeeping.
Get-SwisData $swis @'
SELECT n.NodeID, n.Caption, n.UnManaged, n.UnManageFrom, n.UnManageUntil
FROM Orion.Nodes n
WHERE n.NodeID IN @ids
ORDER BY n.Caption
'@ @{ ids = $targets.NodeID } | Format-Table

if ($failed) { $failed | Format-Table }
```

The Python shape, with the same structure:

```python
from datetime import datetime, timedelta, timezone

targets = swis.query("""
    SELECT cm.MemberPrimaryID AS NodeID, cm.Name
    FROM Orion.ContainerMembers cm
    WHERE cm.Container.Name = @groupName
      AND cm.MemberEntityType = 'Orion.Nodes'
    ORDER BY cm.Name
""", groupName="DC2 Migration")["results"]

print(f"about to unmanage {len(targets)} nodes")
for t in targets:
    print(" ", t["NodeID"], t["Name"])

start = datetime.now(timezone.utc)
end = start + timedelta(hours=8)

failed = []
for t in targets:
    try:
        swis.invoke(
            "Orion.Nodes", "Unmanage",
            f"N:{t['NodeID']}", start.isoformat(), end.isoformat(), False, False,
        )
    except Exception as exc:            # narrow this to your client's exception type
        failed.append((t["NodeID"], str(exc)))

check = swis.query("""
    SELECT NodeID, Caption, UnManaged, UnManageFrom, UnManageUntil
    FROM Orion.Nodes
    WHERE NodeID IN @ids
""", ids=[t["NodeID"] for t in targets])["results"]
```

Other useful scope queries, all runnable as-is:

```sql
SELECT n.NodeID, n.Caption, n.Uri
FROM Orion.Nodes n
WHERE n.Location = @location
  AND n.Vendor = @vendor
ORDER BY n.Caption
```

```sql
SELECT i.InterfaceID, i.Caption, i.Node.Caption AS NodeCaption
FROM Orion.NPM.Interfaces i
WHERE i.NodeID = @nodeId
ORDER BY i.Caption
```

```sql
SELECT a.ApplicationID, a.Name, a.Node.Caption AS NodeCaption
FROM Orion.APM.Application a
WHERE a.Node.NodeID IN @nodeIds
ORDER BY a.Node.Caption, a.Name
```

Whether unmanaging a node also flags its interfaces, volumes and applications as unmanaged in
their own right is runtime behaviour, not something the schema records, so it is **unverified
here**. What the verb is documented to do is stop the node being polled, and that is what
stops collection for everything hanging off it. Confirm the child behaviour on one test node
before relying on either answer: unmanage it, then run the per-type queries below against its
children and see whether `UnManaged` moved. If it did not and you need those objects to read
as unmanaged, unmanage them explicitly with their own verbs.

## Finding what is currently unmanaged

The three properties come from `System.ManagedEntity` and are inherited by every managed
object type, so the same shape works everywhere:

```sql
SELECT
    n.NodeID,
    n.Caption,
    n.IPAddress,
    n.UnManageFrom,
    n.UnManageUntil,
    MinuteDiff(GetUtcDate(), n.UnManageUntil) AS MinutesRemaining
FROM Orion.Nodes n
WHERE n.UnManaged = TRUE
ORDER BY n.UnManageUntil
```

`MinuteDiff(a, b)` returns the minutes that `b` is later than `a`, so a negative value means
the window's end has already passed while the object is still flagged unmanaged. That is the
signature of a stuck window and worth alerting on in its own right.

Windows scheduled but not yet open, which is what you check the day before a change:

```sql
SELECT n.NodeID, n.Caption, n.UnManageFrom, n.UnManageUntil
FROM Orion.Nodes n
WHERE n.UnManaged = FALSE
  AND n.UnManageUntil > GetUtcDate()
ORDER BY n.UnManageFrom
```

Everything unmanaged, across every managed entity type at once, by querying the base entity
rather than each descendant:

```sql
SELECT
    m.DisplayName,
    m.InstanceType,
    m.UnManageFrom,
    m.UnManageUntil
FROM System.ManagedEntity m
WHERE m.UnManaged = TRUE
ORDER BY m.UnManageUntil
```

That is convenient and it is also expensive: 174 entities inherit from
`System.ManagedEntity` in 2026.2, and the query has to consider all of them. Prefer the
per-entity queries for anything you run on a schedule. See
[../swql/joins-and-navigation.md](../swql/joins-and-navigation.md) for how base entity
queries resolve, and [../swql/performance.md](../swql/performance.md) for why this one costs.

The per-type versions:

```sql
SELECT i.InterfaceID, i.Caption, i.Node.Caption AS NodeCaption, i.UnManageUntil
FROM Orion.NPM.Interfaces i
WHERE i.UnManaged = TRUE
ORDER BY i.Node.Caption, i.Caption
```

```sql
SELECT v.VolumeID, v.Caption, v.Node.Caption AS NodeCaption, v.UnManageUntil
FROM Orion.Volumes v
WHERE v.UnManaged = TRUE
ORDER BY v.Node.Caption, v.Caption
```

```sql
SELECT a.ApplicationID, a.Name, a.Node.Caption AS NodeCaption, a.UnManageUntil
FROM Orion.APM.Application a
WHERE a.UnManaged = TRUE
ORDER BY a.Node.Caption, a.Name
```

Cross-checking against status, which catches a node that reports status `9` without the
`UnManaged` flag or the other way round:

```sql
SELECT n.NodeID, n.Caption, n.Status, si.StatusName, n.UnManaged, n.UnManageUntil
FROM Orion.Nodes n
JOIN Orion.StatusInfo si ON n.Status = si.StatusId
WHERE n.Status = 9
   OR n.UnManaged = TRUE
ORDER BY n.Caption
```

## Which entity types can be unmanaged

Only some. Searching the verb data for `Unmanage` in 2026.2 returns seven results across six
entities:

| Entity | `Unmanage` signature | `Remanage` | Right |
|:---|:---|:---|:---|
| `Orion.Nodes` | `(netObjectId, unmanageTime, remanageTime, isRelative, allowOverlapping)` | `(netObjectId)` | `allowUnmanage` |
| `Orion.NPM.Interfaces` | `(netObjectId, unmanageTime, remanageTime, isRelative, allowOverlapping)` | `(netObjectId)` | `allowUnmanage` |
| `Orion.Volumes` | `(netObjectId, unmanageTime, remanageTime, isRelative, allowOverlapping)` | `(netObjectId)` | `allowUnmanage` |
| `Orion.APM.Application` | `(netObjetId, unmanageTime, remanageTime, isRelative, allowOverlapping)` | `(netObjetId)` | see below |
| `Orion.SEUM.Transactions` | `(netObjectId, unmanageTime, remanageTime, isRelative)` | `(netObjectId)` | see below |
| `Orion.Cloud.Instances` | `(virtualMachineId)` | `(virtualMachineId)` | `allowUnmanage` |

The two "see below" rows carry no required right on the verb record itself, so the
entity-level access control governs. `Orion.APM.Application` declares `invoke` for
`allowUnmanage` and for `manageNodes`; `Orion.SEUM.Transactions` declares `read,invoke` for
`everyone` and everything for `admin`. Check with
`python3 tools/schema_query.py show <Entity>`.

Regenerate for your version:

```bash
python3 tools/schema_query.py verbs --grep Unmanage
python3 tools/schema_query.py verbs --grep Remanage
```

Three differences in that table are not cosmetic:

- **`Orion.APM.Application` spells its first parameter `netObjetId`, missing the `c`.** This
  is a real typo in SolarWinds' published contract, in both `Unmanage` and `Remanage`.
  Positional callers are unaffected, because names never travel on the wire. A generated
  client that binds by name is affected, and this is where the mismatch will surface.
- **`Orion.SEUM.Transactions.Unmanage` takes four parameters, not five.** It has no
  `allowOverlapping`. A five-argument call fails.
- **`Orion.Cloud.Instances` is a different shape entirely.** It takes a
  `virtualMachineId` number rather than a NetObject string, and returns a
  `ManagementActionResult` rather than `System.Void`. The id is the
  `VirtualMachineID` property, inherited from `Orion.Virtualization.Instance`.

Calling the interface and volume forms:

```powershell
Invoke-SwisVerb $swis 'Orion.NPM.Interfaces' 'Unmanage' @('I:58', $startUtc, $endUtc, $false, $false) | Out-Null
Invoke-SwisVerb $swis 'Orion.Volumes'        'Unmanage' @('V:9',  $startUtc, $endUtc, $false, $false) | Out-Null
Invoke-SwisVerb $swis 'Orion.APM.Application' 'Unmanage' @('AA:317', $startUtc, $endUtc, $false, $false) | Out-Null

# Four arguments only for transactions.
Invoke-SwisVerb $swis 'Orion.SEUM.Transactions' 'Unmanage' @('T:4', $startUtc, $endUtc, $false) | Out-Null
```

Entity types **not** in that list, which includes most module-specific objects, cannot be
unmanaged individually. Unmanage the node that hosts them, or suppress alerts on them.

## Things that go wrong

- **A bare id instead of a NetObject string.** `42` instead of `"N:42"`. Depending on the
  release this either errors or silently targets nothing.
- **Local time passed as UTC.** The window opens and closes at the wrong hour, and nobody
  notices until an alert fires during the change or fails to fire after it.
- **`isRelative = true` with a full timestamp.** The date is discarded, so an intended
  three-day window becomes a few hours. Pass `false` and compute the end yourself.
- **A duration over 24 hours with `isRelative = true`.** It cannot be expressed, because the
  duration is carried in a time-of-day.
- **Five arguments to `Orion.SEUM.Transactions.Unmanage`.** It takes four.
- **Assuming the response body means something.** `Unmanage` and `Remanage` on nodes,
  interfaces, volumes, applications and transactions all return `System.Void`. Verify with a
  query.
- **A `403` read as a bug.** `Orion.Nodes.Unmanage` requires `allowUnmanage`, which is a
  distinct right from `manageNodes`. Grant it to the service account.
- **A window that never closes.** If `UnManageUntil` is in the past and `UnManaged` is still
  `true`, call `Remanage` explicitly. The scheduled-window query above finds these.
- **Unmanaging when suppression was meant.** You get a gap in the charts you cannot fill in
  later.

## Related pages

- [README.md](README.md) for the query-first method these recipes follow
- [node-management.md](node-management.md) for `PollNow` and `PollStatusNow` after remanaging
- [alerts.md](alerts.md) for `Orion.AlertSuppression`, the alternative
- [dependencies.md](dependencies.md) for suppressing downstream alerts during an unplanned outage
- [../swis/invoke-verbs.md](../swis/invoke-verbs.md) for verb calling mechanics in every client
- [../reference/netobject-types.md](../reference/netobject-types.md) for the prefix table
- [../reference/status-codes.md](../reference/status-codes.md) for status `9`
- [../swql/date-and-time.md](../swql/date-and-time.md) for UTC handling in queries
- [../../scripts/powershell/Set-NodeMaintenanceWindow.ps1](../../scripts/powershell/Set-NodeMaintenanceWindow.ps1), a runnable implementation

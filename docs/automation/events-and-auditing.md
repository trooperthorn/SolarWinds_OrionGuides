# Events and auditing

Two different questions look the same at three in the morning:

- **"What happened to this node?"** The platform observed something. A node stopped
  responding, an interface changed state, an alert triggered. That is an **event**.
- **"Who changed this?"** A person or an API client did something. Somebody unmanaged a node,
  edited a threshold, disabled an alert, logged in. That is an **audit event**.

They live in different entities, they are keyed differently, and the timestamp on one is in
UTC while the timestamp on the other is documented as local. Answering the second question
from the first table is the usual reason an investigation stalls.

This page covers `Orion.Events`, `Orion.EventTypes` and `Orion.AuditingEvents`, the joins
that make them useful, the timezone rule for each, and then three investigations end to end.

## The entities

```bash
python3 tools/schema_query.py show Orion.Events
python3 tools/schema_query.py show Orion.EventTypes
python3 tools/schema_query.py show Orion.AuditingEvents
```

| Entity | Answers | Key | Time column |
|:---|:---|:---|:---|
| `Orion.Events` | What the platform observed | `EventID` | `EventTime`, **local** |
| `Orion.EventTypes` | What an event type integer means | `EventType` | none |
| `Orion.AuditingEvents` | What a person or client did | `AuditEventID` | `TimeLoggedUtc`, **UTC** |
| `Orion.AuditingActionTypes` | What an audit action type integer means | `ActionTypeID` | none |
| `Orion.AuditingArguments` | The structured detail behind one audit entry | `AuditEventID` + `ArgsKey` | none |

### `Orion.Events`

Eight declared properties, plus three inherited from `Orion.MixedObjectType` that do most of
the work:

| Property | Type | Notes |
|:---|:---|:---|
| `EventID` | `System.Int32` | Primary key. Monotonic, so useful for paging. |
| `EventTime` | `System.DateTime` | The schema says: "displayed in local time". |
| `EventType` | `System.Int32` | Join key to `Orion.EventTypes`. |
| `Message` | `System.String` | The rendered text. |
| `NetObjectValue` | `System.String` | Display name of the object involved. |
| `EngineID` | `System.Int32` | Which polling engine recorded it. |
| `Acknowledged` | `System.Boolean` | Cleared from the active views or not. |
| `TimeStamp` | `System.Byte[]` | **Not a date.** A row-version column for concurrency. |
| `NetworkNode` | `System.Int32` | *(from `Orion.MixedObjectType`)* the related node id |
| `NetObjectID` | `System.Int32` | *(from `Orion.MixedObjectType`)* id within its own type |
| `NetObjectType` | `System.String` | *(from `Orion.MixedObjectType`)* which type that is |

`Orion.Events` inherits from `Orion.MixedObjectType`, whose own summary explains the design:
"Base class for SWIS entities that contains records from multiple netobject types. E.g.
Orion.Events". One table holds events about nodes, interfaces, volumes and applications, and
the `NetObjectType` plus `NetObjectID` pair says which. `NetworkNode` is separately populated
with the hosting node id, which is why the node join works for an interface event as well as
a node event.

**`TimeStamp` on `Orion.Events` is a `System.Byte[]`.** Selecting it expecting a date, or
filtering on it, is a real mistake people make because `Orion.AlertHistory.TimeStamp` in the
same problem space genuinely is a date. Use `EventTime`.

`Orion.Events` declares one verb:

```text
Orion.Events.Acknowledge(eventIDs: array<number>) -> boolean
  Marks the specified event as acknowledged, typically used to clear events from active
  monitoring views.
  requires: clearEvents
```

Same right as the alert acknowledgement verbs, and the same caution applies: it returns one
boolean for the whole call, so verify with a read-back.

### `Orion.EventTypes`

The lookup that turns `EventType` into something readable. Thirteen properties, most of them
display concerns (`Icon`, `BackColor`, `Sound`, `Bold`). The ones that matter:

| Property | Notes |
|:---|:---|
| `EventType` | The integer that appears in `Orion.Events.EventType` |
| `Name` | The human-readable name |
| `Record` | Whether events of this type are written at all |
| `Notify` | Whether they raise a notification |
| `OrionFeatureName` | The module that owns the type; navigable to `Orion.Features` |

The numeric values are **not** in the extracted schema, and they are not stable across
installations because modules add their own. Do not hard-code them. Read the table:

```sql
SELECT et.EventType, et.Name, et.Record, et.Notify, et.OrionFeatureName
FROM Orion.EventTypes et
ORDER BY et.EventType
```

That query is worth running once and keeping, because every filter below reads better as a
filter on `Name` than as a magic integer.

### `Orion.AuditingEvents`

Ten declared properties, and it inherits from `Orion.LogEntity` ("Base class for SWIS
entities which supposed to be indexed in Elasticsearch"), which adds four `Observation*`
columns.

| Property | Type | Notes |
|:---|:---|:---|
| `AuditEventID` | `System.Int32` | Primary key |
| `TimeLoggedUtc` | `System.DateTime` | **UTC.** The name says so and it is one of the few that does. |
| `AccountID` | `System.String` | Who. Navigable to `Orion.Accounts`. Blank for the system. |
| `ActionTypeID` | `System.Int32` | What kind of change. Navigable to `Orion.AuditingActionTypes`. |
| `AuditEventMessage` | `System.String` | The rendered description |
| `NetworkNode` | `System.Int32` | The node the change was about, when there is one |
| `NetObjectID` | `System.Int32` | The changed object's id within its type |
| `NetObjectType` | `System.String` | Which type that is |
| `DetailsUrl` | `System.String` | Relative URL to the object in the console |
| `DisplayName` | `System.String` | |
| `ObservationTimestamp` | `System.DateTime` | *(from `Orion.LogEntity`)* |
| `ObservationSeverity`, `ObservationSeverityName`, `ObservationRowVersion` | | *(from `Orion.LogEntity`)* |

Note that `NetworkNode`, `NetObjectID` and `NetObjectType` are declared **directly** on
`Orion.AuditingEvents` rather than inherited from `Orion.MixedObjectType` as they are on
`Orion.Events`. Same names, same meaning, different provenance. It does not change how you
query them, but it does mean you cannot assume the two entities share a base class.

## Event or audit event: how to decide

| Question | Entity | Why |
|:---|:---|:---|
| Why is this node down? | `Orion.Events` | The platform observed the transition |
| When did it recover? | `Orion.Events` | Same |
| Who unmanaged it? | `Orion.AuditingEvents` | A person or client did that |
| Why did nobody get paged? | Both: `Orion.AlertHistory` for the action, `Orion.AuditingEvents` for who disabled the alert | |
| Who changed this threshold? | `Orion.AuditingEvents` | |
| Who acknowledged this alert? | `Orion.AlertHistory` | Alert acknowledgement is logged there, with `AccountID` |
| Who logged in? | `Orion.AuditingEvents` | |

The rule of thumb: **if a human could have done it, look in auditing first.** Events tell you
the state of the world changed; auditing tells you whether one of your colleagues changed it.

## Joining events to their type and to the node

Two ways to get the type name, both valid:

```sql
-- Explicit join on the integer.
SELECT TOP 200
    e.EventTime,
    et.Name AS EventTypeName,
    e.Message,
    e.NetObjectValue
FROM Orion.Events e
JOIN Orion.EventTypes et ON e.EventType = et.EventType
WHERE e.EventTime >= AddDay(-1, GetDate())
ORDER BY e.EventTime DESC
```

```sql
-- The declared navigation property. Same result, fewer lines.
SELECT TOP 200
    e.EventTime,
    e.EventTypeProperties.Name AS EventTypeName,
    e.Message,
    e.NetObjectValue
FROM Orion.Events e
WHERE e.EventTime >= AddDay(-1, GetDate())
ORDER BY e.EventTime DESC
```

The navigation property is called `EventTypeProperties`, not `EventTypes`. That is the kind
of name nobody guesses correctly:

```bash
python3 tools/schema_query.py show Orion.Events
```

```text
  targetRelationships (3) - this entity is the target; property leads back to the source
    Nodes                                      -> Orion.Nodes
    Engine                                     -> Orion.Engines
    EventTypeProperties                        -> Orion.EventTypes
```

The node navigation property is `Nodes`, **plural, resolving to a single node**:

```sql
SELECT TOP 200
    e.EventTime,
    e.EventTypeProperties.Name AS EventTypeName,
    e.Message,
    e.Nodes.Caption AS NodeCaption,
    e.Nodes.IPAddress AS NodeIP,
    e.Nodes.Status AS NodeStatus
FROM Orion.Events e
WHERE e.Nodes.NodeID = @nodeId
  AND e.EventTime >= AddDay(-1, GetDate())
ORDER BY e.EventTime DESC
```

The reverse direction is declared too, which is what you want inside a node report:

```sql
SELECT
    n.Caption,
    n.Events.EventTime AS EventTime,
    n.Events.Message AS Message
FROM Orion.Nodes n
WHERE n.NodeID = @nodeId
```

Navigating through `Nodes` filters out events with no node attached. When you want everything
including engine-level and system events, filter on `NetworkNode` instead, which is a plain
integer column on the event itself:

```sql
SELECT TOP 200
    e.EventTime,
    e.EventTypeProperties.Name AS EventTypeName,
    e.NetObjectType,
    e.NetObjectID,
    e.NetObjectValue,
    e.Message
FROM Orion.Events e
WHERE e.NetworkNode = @nodeId
  AND e.EventTime >= AddDay(-1, GetDate())
ORDER BY e.EventTime DESC
```

The difference is not academic. An interface flap on node 42 has `NetObjectType =
'Orion.NPM.Interfaces'` and `NetworkNode = 42`. Both queries find it, but only the second one
also finds events the platform did not associate with a node object.

Which engine recorded an event is a declared join as well, and it is the fastest way to spot
one polling engine misbehaving:

```sql
SELECT
    e.Engine.ServerName AS EngineName,
    COUNT(e.EventID) AS EventCount
FROM Orion.Events e
WHERE e.EventTime >= AddDay(-1, GetDate())
GROUP BY e.Engine.ServerName
ORDER BY COUNT(e.EventID) DESC
```

## Filtering by time window, correctly

This is where these two entities differ and where the errors are silent.

### `Orion.Events.EventTime` is local

The schema description is explicit: "Date and time when the event occurred, displayed in
local time." "Local" here means the SQL Server's timezone, which is not necessarily the Orion
application server's and is definitely not the reader's. So the last 24 hours of events is:

```sql
WHERE e.EventTime >= AddDay(-1, GetDate())
```

`GetDate()` already returns the SQL Server's local time, so both sides of the comparison are
on the same clock and no conversion is needed.

### `Orion.AuditingEvents.TimeLoggedUtc` is UTC

The name ends in `Utc`, which is the most reliable signal the schema gives. So the last 24
hours of audit entries is **not** `AddDay(-1, GetUtcDate())`:

```sql
WHERE a.TimeLoggedUtc >= ToUtc(AddDay(-1, GetDate()))
```

The reason is the single most consequential SWQL gotcha, and it is worth restating here
because time-bounded audit queries are exactly where it bites. SWIS compiles `AddDay` into
T-SQL `DATEADD`, and SolarWinds documents that `DATEADD` "doesn't work with time zone offset
at all". Hand it a UTC value and it does correct arithmetic, then hands back a plain
`datetime` that SQL Server stamps with the **server's own offset** on the way out. The clock
arithmetic is right and the label is wrong, so the value silently shifts by your UTC offset.

SolarWinds' recommended shape is: do the arithmetic in local time, convert at the end.
`ToUtc(AddDay(-1, GetDate()))` is that shape. Full treatment, with SolarWinds' own recorded
before-and-after output, is in [../swql/date-and-time.md](../swql/date-and-time.md).

Two more rules that apply to both entities:

- **Put the arithmetic on the constant side.** `WHERE e.EventTime >= AddDay(-1, GetDate())`,
  never `WHERE AddDay(1, e.EventTime) >= GetDate()`. Wrapping the column defeats the index
  and turns a fast query into a table scan on a table that grows without bound.
- **Always bound the window.** `Orion.Events` and `Orion.AuditingEvents` are among the
  largest tables in the database. An unbounded `SELECT` against either is how a reporting
  script takes the web console down. Use `TOP` as well, as a second seat belt.

### Bucketing

`DateTrunc` is the right way to build a per-hour or per-day count, because grouping on a raw
timestamp groups on the millisecond:

```sql
SELECT
    DateTrunc('hour', e.EventTime) AS Hour,
    COUNT(e.EventID) AS EventCount
FROM Orion.Events e
WHERE e.EventTime >= AddDay(-7, GetDate())
GROUP BY DateTrunc('hour', e.EventTime)
ORDER BY DateTrunc('hour', e.EventTime) DESC
```

## Investigation 1: what happened to this node in the last 24 hours

Start with everything, typed and ordered. Do not filter by event type on the first pass;
the thing that explains the outage is often a type you would not have thought to include.

```sql
SELECT TOP 500
    e.EventTime,
    e.EventTypeProperties.Name AS EventTypeName,
    e.NetObjectType,
    e.NetObjectValue,
    e.Message,
    e.Acknowledged,
    e.Engine.ServerName AS RecordedByEngine
FROM Orion.Events e
WHERE e.NetworkNode = @nodeId
  AND e.EventTime >= AddDay(-1, GetDate())
ORDER BY e.EventTime DESC
```

Then run the audit trail for the same node over a wider window, because the change that
caused tonight's events was probably made this afternoon:

```sql
SELECT TOP 200
    a.TimeLoggedUtc,
    a.AccountID,
    a.AuditingActionType.ActionType AS ActionType,
    a.AuditingActionType.ActionTypeDisplayName AS ActionDescription,
    a.AuditEventMessage,
    a.NetObjectType,
    a.NetObjectID
FROM Orion.AuditingEvents a
WHERE a.NetworkNode = @nodeId
  AND a.TimeLoggedUtc >= ToUtc(AddDay(-7, GetDate()))
ORDER BY a.TimeLoggedUtc DESC
```

Then check whether the node was in a maintenance window at the time, because an unmanaged
node produces no events at all and "nothing in the log" is a finding, not an absence of one:

```sql
SELECT
    n.NodeID,
    n.Caption,
    n.Status,
    n.StatusDescription,
    n.UnManaged,
    n.UnManageFrom,
    n.UnManageUntil
FROM Orion.Nodes n
WHERE n.NodeID = @nodeId
```

And whether any alert was firing on it, which is the alerting side of the same story:

```sql
SELECT
    ao.AlertConfigurations.Name AS AlertName,
    ao.EntityType,
    ao.EntityCaption,
    aa.TriggeredDateTime,
    aa.Acknowledged,
    aa.AcknowledgedBy
FROM Orion.AlertActive aa
JOIN Orion.AlertObjects ao ON aa.AlertObjectID = ao.AlertObjectID
WHERE ao.RelatedNodeId = @nodeId
ORDER BY aa.TriggeredDateTime DESC
```

If the alert has already reset, that query returns nothing and the history in
[alerts.md](alerts.md) is where to look instead.

Finally, the recorded downtime, which the platform keeps separately from events:

```sql
SELECT
    d.EntityType,
    d.EntityId,
    d.DateTimeFrom,
    d.DateTimeUntil,
    d.TotalDurationMin,
    d.State
FROM Orion.NetObjectDowntime d
WHERE d.NodeId = @nodeId
ORDER BY d.DateTimeFrom DESC
```

## Investigation 2: which nodes went down overnight

There is no "node down" boolean to filter on. The event type is a lookup value whose integer
differs between installations, so filter on the **name** and let the join do the work:

```sql
SELECT
    e.EventTime,
    e.EventTypeProperties.Name AS EventTypeName,
    e.NetObjectValue AS ObjectName,
    e.Nodes.Caption AS NodeCaption,
    e.Nodes.IPAddress AS NodeIP,
    e.Message
FROM Orion.Events e
WHERE e.EventTypeProperties.Name LIKE '%Down%'
  AND e.EventTime >= AddHour(-14, GetDate())
ORDER BY e.EventTime
```

`AddHour(-14, GetDate())` run at 08:00 covers back to 18:00 the previous evening. Adjust to
your shift boundary; the point is to express "overnight" as a real interval rather than
guessing at a calendar day, which would miss everything before midnight.

Before trusting the `LIKE`, look at what type names your installation actually has, because
modules contribute their own and `'%Down%'` may catch more or less than you expect:

```sql
SELECT et.EventType, et.Name, et.OrionFeatureName
FROM Orion.EventTypes et
WHERE et.Name LIKE '%Down%'
ORDER BY et.Name
```

Once you know the integers on your own server, pin them, which is both faster and unambiguous:

```sql
SELECT
    e.EventTime,
    e.NetObjectValue,
    e.Nodes.Caption AS NodeCaption,
    e.Message
FROM Orion.Events e
WHERE e.EventType IN @downEventTypes
  AND e.NetworkNode IS NOT NULL
  AND e.EventTime >= AddHour(-14, GetDate())
ORDER BY e.EventTime
```

Bind `@downEventTypes` as a multi-valued parameter rather than formatting a list into the
query text. See [README.md](README.md).

### Down and back up, in one row

Counting bare down events over-reports, because a node that flapped six times looks like six
outages. Pair each node with its current status and how many transitions it recorded:

```sql
SELECT
    e.Nodes.NodeID AS NodeID,
    e.Nodes.Caption AS NodeCaption,
    e.Nodes.Status AS CurrentStatus,
    e.Nodes.StatusDescription AS CurrentStatusText,
    COUNT(e.EventID) AS DownEvents,
    MIN(e.EventTime) AS FirstDown,
    MAX(e.EventTime) AS LastDown
FROM Orion.Events e
WHERE e.EventTypeProperties.Name LIKE '%Down%'
  AND e.EventTime >= AddHour(-14, GetDate())
GROUP BY e.Nodes.NodeID, e.Nodes.Caption, e.Nodes.Status, e.Nodes.StatusDescription
ORDER BY COUNT(e.EventID) DESC
```

A node with `DownEvents = 14` and `CurrentStatus = 1` flapped and recovered; a node with
`DownEvents = 1` and `CurrentStatus = 2` is still down and is the one to look at first.
Status `1` is Up, `2` is Down, `9` is Unmanaged, `12` is Unreachable. The full table is
[../reference/status-codes.md](../reference/status-codes.md).

`Orion.NetObjectDowntime` answers the same question from the other side, with durations
already computed:

```sql
SELECT
    d.Node.Caption AS NodeCaption,
    d.EntityType,
    d.DateTimeFrom,
    d.DateTimeUntil,
    d.TotalDurationMin,
    d.State
FROM Orion.NetObjectDowntime d
WHERE d.DateTimeFrom >= AddDay(-1, GetDate())
ORDER BY d.TotalDurationMin DESC
```

The timezone of `DateTimeFrom` is not documented in the schema, so measure it the same way
before building a report on it.

## Investigation 3: who unmanaged this node

This is the archetypal audit question, and it has three levels of precision.

### Level 1: the action type

`Orion.AuditingActionTypes` is the lookup. Its contents are installation data, so list them
and find the one you want rather than assuming an integer:

```sql
SELECT
    aat.ActionTypeID,
    aat.ActionType,
    aat.ActionTypeDisplayName,
    aat.OperationStatus
FROM Orion.AuditingActionTypes aat
ORDER BY aat.ActionType
```

```sql
SELECT
    aat.ActionTypeID,
    aat.ActionType,
    aat.ActionTypeDisplayName
FROM Orion.AuditingActionTypes aat
WHERE aat.ActionType LIKE '%nmanage%'
   OR aat.ActionTypeDisplayName LIKE '%nmanage%'
```

Searching for `'%nmanage%'` rather than `'%Unmanage%'` catches both "Unmanage" and
"unmanaged" without depending on the collation being case insensitive.

Then filter the audit trail by the action type name through the declared navigation property,
which is stable across installations in a way the integer is not:

```sql
SELECT TOP 200
    a.TimeLoggedUtc,
    a.AccountID,
    a.AuditingActionType.ActionType AS ActionType,
    a.AuditEventMessage,
    a.NetObjectType,
    a.NetObjectID,
    a.NetworkNode
FROM Orion.AuditingEvents a
WHERE a.AuditingActionType.ActionType LIKE '%nmanage%'
  AND a.TimeLoggedUtc >= ToUtc(AddDay(-30, GetDate()))
ORDER BY a.TimeLoggedUtc DESC
```

### Level 2: narrowed to one node

```sql
SELECT
    a.TimeLoggedUtc,
    a.AccountID,
    a.AuditingActionType.ActionType AS ActionType,
    a.AuditingActionType.ActionTypeDisplayName AS ActionDescription,
    a.AuditEventMessage,
    a.DetailsUrl
FROM Orion.AuditingEvents a
WHERE a.NetworkNode = @nodeId
  AND a.TimeLoggedUtc >= ToUtc(AddDay(-30, GetDate()))
ORDER BY a.TimeLoggedUtc DESC
```

If `NetworkNode` is empty for the entries you care about, fall back to the object identity
pair, which is populated for changes to objects that are not nodes:

```sql
SELECT
    a.TimeLoggedUtc,
    a.AccountID,
    a.AuditEventMessage
FROM Orion.AuditingEvents a
WHERE a.NetObjectType = @netObjectType
  AND a.NetObjectID = @netObjectId
  AND a.TimeLoggedUtc >= ToUtc(AddDay(-30, GetDate()))
ORDER BY a.TimeLoggedUtc DESC
```

And as a last resort, the message text. This is crude, it is sensitive to wording changes
between releases, and it cannot use an index, so keep the time window tight:

```sql
SELECT TOP 100
    a.TimeLoggedUtc,
    a.AccountID,
    a.AuditEventMessage,
    a.NetObjectType,
    a.NetObjectID
FROM Orion.AuditingEvents a
WHERE a.AuditEventMessage LIKE '%nmanage%'
  AND a.TimeLoggedUtc >= ToUtc(AddDay(-7, GetDate()))
ORDER BY a.TimeLoggedUtc DESC
```

### Level 3: the arguments

`AuditEventMessage` is rendered text. The structured version is in `Orion.AuditingArguments`,
a key/value bag keyed on `AuditEventID` and reachable through the declared `Arguments`
navigation property. This is where the *old and new values* of a change live, when the action
type records them:

```sql
SELECT
    a.TimeLoggedUtc,
    a.AccountID,
    a.AuditEventMessage,
    a.Arguments.ArgsKey AS ArgKey,
    a.Arguments.ArgsValue AS ArgValue
FROM Orion.AuditingEvents a
WHERE a.AuditEventID = @auditEventId
ORDER BY a.Arguments.ArgsKey
```

The set of keys is entirely dependent on the action type, so there is nothing general to
document. Run the query against one audit entry of the kind you care about and read the keys
off. That is a one-off discovery step you do once per action type, and then you know.

**The key names in `Orion.AuditingArguments` are not in the extracted schema.** They are
data, not schema, and they vary by action type and by module. Anything a script depends on
here should be checked on the server it will run against.

### Attributing it to a person

`AccountID` is a string, and it navigates to `Orion.Accounts`:

```sql
SELECT
    a.TimeLoggedUtc,
    a.AccountID,
    a.AuditEventMessage,
    a.Account.AccountType AS AccountType,
    a.Account.LastLogin AS AccountLastLogin,
    a.Account.Enabled AS AccountEnabled
FROM Orion.AuditingEvents a
WHERE a.TimeLoggedUtc >= ToUtc(AddDay(-7, GetDate()))
ORDER BY a.TimeLoggedUtc DESC
```

A blank `AccountID` means the platform did it, not a person. Scheduled remanaging at the end
of a maintenance window, automatic dependency discovery and internal housekeeping all show up
that way, and reading a blank as "we could not tell who" is the wrong conclusion.

An `AccountID` that is a service account is the other common answer, and it usually means
"an automation did this, go and read the automation". Which is why every script that writes
should be running as its own named account rather than sharing one.

### Change volume per account

Useful as a monthly review, and useful when you suspect a script is doing more than intended:

```sql
SELECT
    a.AccountID,
    COUNT(a.AuditEventID) AS Changes,
    MIN(a.TimeLoggedUtc) AS FirstChange,
    MAX(a.TimeLoggedUtc) AS LastChange
FROM Orion.AuditingEvents a
WHERE a.TimeLoggedUtc >= ToUtc(AddDay(-30, GetDate()))
GROUP BY a.AccountID
ORDER BY COUNT(a.AuditEventID) DESC
```

```sql
SELECT
    a.AuditingActionType.ActionType AS ActionType,
    COUNT(a.AuditEventID) AS Changes
FROM Orion.AuditingEvents a
WHERE a.AccountID = @accountId
  AND a.TimeLoggedUtc >= ToUtc(AddDay(-30, GetDate()))
GROUP BY a.AuditingActionType.ActionType
ORDER BY COUNT(a.AuditEventID) DESC
```

## Acknowledging events

```bash
python3 tools/schema_query.py verb Orion.Events Acknowledge
```

```text
Orion.Events.Acknowledge
  returns: boolean
  REST:    POST /Invoke/Orion.Events/Acknowledge
  requires: clearEvents
  parameters (1):
    eventIDs: array<number> (required)
```

One argument, and it is an array, so this is the PowerShell case that needs the leading-comma
idiom:

```powershell
# 1. Scope.
$stale = Get-SwisData $swis @'
SELECT TOP 500 e.EventID, e.EventTime, e.EventTypeProperties.Name AS EventTypeName, e.Message
FROM Orion.Events e
WHERE e.Acknowledged = FALSE
  AND e.EventTime < AddDay(-30, GetDate())
ORDER BY e.EventTime
'@

"$($stale.Count) event(s) to acknowledge."
$stale | Select-Object -First 10 | Format-Table

# 2. Act. One argument, and it is an array: the leading comma is required.
$ids = [int[]] $stale.EventID
$ok = Invoke-SwisVerb $swis 'Orion.Events' 'Acknowledge' @( , $ids )
$ok.InnerText

# 3. Verify.
Get-SwisData $swis 'SELECT EventID, Acknowledged FROM Orion.Events WHERE EventID IN @ids' `
    @{ ids = $ids } | Where-Object { -not $_.Acknowledged }
```

The REST equivalent, with the same nesting:

```bash
curl -k -u "$SWIS_USER:$SWIS_PASS" \
  -H 'Content-Type: application/json' \
  -X POST "https://orion.example.com:17774/SolarWinds/InformationService/v3/Json/Invoke/Orion.Events/Acknowledge" \
  -d '[[100234, 100235, 100236]]'
```

Acknowledging an event clears it from the active views. It does not delete it, and it does
not affect alerting. There is no verb to unacknowledge an event, unlike alerts, which have
`Orion.AlertActive.Unacknowledge`.

## Things that go wrong

- **Comparing `TimeLoggedUtc` against `AddDay(-1, GetUtcDate())`.** The arithmetic is right,
  the offset label is wrong, and the window silently shifts by your UTC offset. Use
  `ToUtc(AddDay(-1, GetDate()))`.
- **Comparing `EventTime` against a UTC constant.** `EventTime` is documented as local. Use
  `GetDate()`.
- **Selecting `Orion.Events.TimeStamp` as a date.** It is a `System.Byte[]` row-version
  column. `EventTime` is the date.
- **Guessing that the navigation property is `EventTypes`.** It is `EventTypeProperties`.
- **Hard-coding `EventType` integers.** They are installation data and modules add their own.
  Join to `Orion.EventTypes` and filter on `Name`, or read the integers off the server you
  are targeting.
- **Answering "who changed this" from `Orion.Events`.** It records what the platform observed,
  not who acted. `AccountID` only exists on `Orion.AuditingEvents`.
- **Reading a blank `AccountID` as unknown.** It means the system did it, not a person.
- **Unbounded queries.** Both tables grow without limit. Always constrain by time and add
  `TOP`.
- **Wrapping the column in the date arithmetic.** `WHERE AddDay(1, e.EventTime) >= GetDate()`
  scans the whole table. Put the arithmetic on the constant side.
- **Assuming "no events" means "nothing happened".** An unmanaged node produces none. Check
  `UnManaged`, `UnManageFrom` and `UnManageUntil`.
- **A service account seeing fewer rows than you do.** Account limitations filter query
  results silently, with no error. Compare as both accounts before concluding the data is
  missing.

## What is not verified here

| Claim | Status | How to check on your server |
|---|---|---|
| The numeric values of `Orion.Events.EventType` | Installation data, not schema. Modules contribute their own. | `SELECT EventType, Name, OrionFeatureName FROM Orion.EventTypes ORDER BY EventType` |
| The numeric values of `Orion.AuditingEvents.ActionTypeID` | Installation data, not schema | `SELECT ActionTypeID, ActionType, ActionTypeDisplayName FROM Orion.AuditingActionTypes ORDER BY ActionType` |
| The key names in `Orion.AuditingArguments.ArgsKey` | Depend on the action type; not in the schema | Pick one audit entry of the kind you care about and select its `Arguments.ArgsKey` and `Arguments.ArgsValue` |
| The meaning of `Orion.AuditingActionTypes.OperationStatus` | `System.Int16` with no description in the schema | `SELECT OperationStatus, COUNT(ActionTypeID) FROM Orion.AuditingActionTypes GROUP BY OperationStatus`, then correlate with action types you can reproduce |
| The timezone of `Orion.NetObjectDowntime.DateTimeFrom` and `DateTimeUntil` | Undocumented; the names do not end in `Utc` | `SELECT TOP 5 DateTimeFrom, MinuteDiff(DateTimeFrom, GetDate()), MinuteDiff(DateTimeFrom, GetUtcDate()) FROM Orion.NetObjectDowntime ORDER BY DateTimeFrom DESC` on a row whose age you know |
| Retention of `Orion.Events` and `Orion.AuditingEvents` | A database maintenance setting, not schema | Compare `MIN(EventTime)` and `MIN(TimeLoggedUtc)` against the console's retention settings |
| The exact wording of `AuditEventMessage` for a given action | Rendered text that can change between releases | Reproduce the action once and read the message back; prefer `AuditingActionType.ActionType` for anything a script depends on |

## Related pages

- [README.md](README.md) for the query-first method and multi-valued parameter binding
- [alerts.md](alerts.md) for `Orion.AlertHistory`, which is the alerting equivalent of this page
- [maintenance-mode.md](maintenance-mode.md) for `UnManaged` and why a quiet node may be quiet on purpose
- [node-management.md](node-management.md) for node status and repolling
- [../swql/date-and-time.md](../swql/date-and-time.md) for the UTC rule these queries follow
- [../swql/performance.md](../swql/performance.md) for why the arithmetic goes on the constant side
- [../reference/status-codes.md](../reference/status-codes.md) for the status integers
- [../swis/invoke-verbs.md](../swis/invoke-verbs.md) for the `Acknowledge` call shape
- [../../scripts/swql/06-events-and-auditing.swql](../../scripts/swql/06-events-and-auditing.swql), runnable versions of these queries

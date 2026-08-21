# Log Analyzer: syslog, traps and log files

Log Analyzer is where messages the platform did not ask for arrive. A switch sends a syslog
line, a UPS fires an SNMP trap, an agent tails an application log file: none of those is a
poll, none has a schedule, and the volume is set by the estate rather than by you. The
module's job is to receive them, map each one back to a node, apply processing rules, tag
what matters, and keep the rest for as long as the retention period says.

That makes it the odd module out in two ways. It is the only one whose primary table can
grow by millions of rows a day, and it is the only one where the main API use case is
**getting data out** rather than configuring something. SolarWinds' own SDK page for the
module is called
[Exporting Log Events](https://solarwinds.github.io/OrionSDK/docs/log-analyzer/exporting-log-events/),
and the advice on it is the advice this page starts with.

## Read this before you write a query

`Orion.OLM.LogEntry` is almost certainly the largest thing you can query on the
installation. Two facts from the schema make the scale concrete:

- Its key, `LogEntryID`, is a **`System.Int64`**. So is `LogEntryFieldValueID` on
  `Orion.OLM.LogEntryFieldValue`. Nothing else in the module needs 64 bits, and nothing in
  most modules does.
- `Orion.OLM.LogEntryType` carries `RetentionPeriodInDays` per type, which exists because
  keeping everything forever is not an option.

So every query against `Orion.OLM.LogEntry` gets a `DateTime` predicate and a bounded
result set, without exception. SolarWinds phrases the rule as: "It is important to specify
at least a date range (in UTC) to limit the amount of data to search." Treat the date range
as mandatory rather than as a good habit, and prefer
`WITH ROWS a TO b WITH TOTALROWS` over `TOP n` when you are exporting, so you can page
without re-running the scan. See [../swql/performance.md](../swql/performance.md).

`DateTime` is stored in UTC. Build the window in UTC too, and read
[../swql/date-and-time.md](../swql/date-and-time.md) first: `GetUtcDate()` combined with
`AddHour` and friends produces wrong offsets, because those compile to a timezone-blind
`DATEADD`.

## Namespace and how many entities

Everything is under `Orion.OLM.`, which holds **21 entities** in 2026.2. There is no
`Orion.LogAnalyzer` namespace and no `Orion.LA` namespace: as
[../platform/modules.md](../platform/modules.md) explains, prefixes are engineering names
fixed long before the current product names, and this is one of the cases where the two do
not resemble each other at all.

| Group | Entities |
|---|---|
| Messages | `LogEntry`, `LogEntryType`, `LogEntryLevel`, `LogEntryFieldValue` |
| Where messages came from | `MessageSources`, `Nodes`, `LogEntrySecondarySources`, `LogEntrySecondarySourceAssignment` |
| Classification | `Tags`, `LogEntryTagAssignment` |
| Log file collection | `LogProfile`, `LogProfileAgentAssignment`, `HealthIssues` |
| Rule processing | `ProcessingRule`, `ProcessingRuleActions`, `RuleProcessingDefinitions` |
| Events published to the rest of the platform | `AlertMessage`, `NodeInfosChanged`, `NodeLicensingChange`, `LicenseExpiration`, `LicenseReset` |

Check what your own server has, and confirm the module is installed at all before relying
on any of it:

```bash
python3 tools/schema_query.py find OLM --properties
python3 tools/schema_query.py show Orion.OLM.LogEntry
python3 tools/schema_query.py verbs --entity Orion.OLM.ProcessingRule
```

```sql
SELECT FullName, BaseType, CanCreate, CanUpdate, CanDelete, CanInvoke, IsObsolete
FROM Metadata.Entity
WHERE FullName LIKE 'Orion.OLM.%'
ORDER BY FullName
```

No Log Analyzer entity has a NetObject prefix in
[`data/reference/netobject-types.json`](../../data/reference/netobject-types.json), and the
module's verbs take bare integer and GUID ids rather than NetObject strings, which is
consistent with that.

## `Orion.OLM.LogEntry` is the module

"Stored messages or events", ten properties, read-only for everyone.

| Property | Type | Why it matters |
|---|---|---|
| `LogEntryID` | `System.Int64` | The key, and the reason to think about volume |
| `LogEntryTypeID` | `System.Int32` | Syslog, Trap, and whatever else the installation collects |
| `LogEntryLevelID` | `System.Int32` | Severity, unified across message types |
| `NodeID` | `System.Int32` | "Identifier of mapped node", null when the sender was never recognised |
| `MessageSourceID` | `System.Int32` | The sending IP address as a first-class object |
| `DateTime` | `System.DateTime` | When the message was **received**. This is the column to filter on |
| `MessageDateTime` | `System.DateTime` | When the message says it was **created**, "usually parsed from the message itself" |
| `Message` | `System.String` | The text |
| `Level` | `System.String` | The severity name, translated when the product is installed in another language |
| `LevelKey` | `System.String` | The severity name, untranslated |

Three things follow from that list and each of them changes a query.

**Filter on `DateTime`, report on `MessageDateTime`.** `DateTime` is when your collector saw
the message and is the column that indexes and bounds the scan. `MessageDateTime` is
whatever the sender claimed, which is useful for correlation and unreliable for filtering,
because a device with a wrong clock will fall outside any window you choose.

**Compare `LevelKey`, display `Level`.** `Level` is the localised form. A filter written
against it works on an English installation and quietly returns nothing on a German one.
`Orion.OLM.LogEntryLevel` carries the same pair for the lookup table, plus
`LogEntryLevelID`. There is no navigation property from `LogEntry` to `LogEntryLevel`, so
join on `LogEntryLevelID` if you need the catalogue; most of the time you do not, because
the two strings are already on the entry.

**`NodeID` and `MessageSourceID` are not the same thing.** The message source is an IP
address that sent something. The node is the monitored object it was matched to. A source
can exist with no node, and one node can have several sources.

### Navigation from a log entry

`Orion.OLM.LogEntry` declares four outbound navigations and is the target of one more, and
all five are usable from the entry because both directions of a relationship are navigable:

| From `Orion.OLM.LogEntry` | Reaches |
|---|---|
| `LogType` | `Orion.OLM.LogEntryType` |
| `FieldValues` | `Orion.OLM.LogEntryFieldValue` |
| `Tags` | `Orion.OLM.Tags` |
| `SecondarySources` | `Orion.OLM.LogEntrySecondarySources` |
| `LogMessageSource` | `Orion.OLM.MessageSources` |

`LogMessageSource` is the one SolarWinds' export sample uses, as
`logEntry.LogMessageSource.IPAddress` and `logEntry.LogMessageSource.Caption`, and it is
declared on `Orion.OLM.MessageSources` as `Events` in the other direction. Note that it is
also the navigation property name **from a node**: `Orion.Nodes.LogMessageSource` reaches
`Orion.OLM.MessageSources`, not the log entries.

### Message types and retention

`Orion.OLM.LogEntryType` is small and important: `LogEntryTypeID`, `Type` (the untranslated
name), `Name` (the translated one), `RetentionPeriodInDays` and `DetailPageEnabled`. The
SolarWinds export page names two values for `Type`, **`Syslog`** and **`Traps`**, and says
they are what to pass when filtering to one kind of event. Other types exist on
installations that collect log files or VMware events; enumerate them rather than assuming
the list, because `Orion.OLM.LogEntryType` is a two-row table on some servers and a
six-row table on others.

The entity allows `read` for everyone and `read, update` for `admin`, and `update` is
exactly what you would expect: retention is a per-type setting you can change through SWIS.
It does not allow create or delete, so the set of types is fixed by what the module knows
how to receive.

### Fields, tags and secondary sources

Three satellite entities hang off an entry, and all three are one-row-per-entry-per-thing,
so they are as large as the entry table or larger. Time-bound them through the entry.

`Orion.OLM.LogEntryFieldValue` holds parsed fields: `LogEntryFieldID`,
`LogEntryFieldValueID`, `LogEntryID`, `Name` (translated), and three typed value columns,
`TextValue`, `NumericValue` and `DateTimeValue`, of which one is populated. It navigates
back to the entry as `Event`. What field names exist depends on the parsing rules the
installation has defined, which live in `Orion.OLM.RuleProcessingDefinitions`.

`Orion.OLM.Tags` is the classification vocabulary: `LogEntryTagID` (a `System.Int16`,
so the vocabulary is small by design), `Name` and `ColorIndex`.
`Orion.OLM.LogEntryTagAssignment` is the join table, `LogEntryID` plus `LogEntryTagID`. You
rarely need the join table directly because `Orion.OLM.LogEntry.Tags` walks it for you.
Neither entity declares any operations, so tags are assigned by processing rules rather
than through CRUD.

`Orion.OLM.LogEntrySecondarySources` is for messages that have a more specific origin than
the node: `LogEntrySecondarySourceID`, `Identity` and `Label`, and the schema gives the
concrete example that "in case of VMware event types it can be ESX host name".
`Orion.OLM.LogEntrySecondarySourceAssignment` is its join table.

## Message sources, nodes and licensing

This is the part of the module people get wrong, and the schema explains it clearly if you
read the two entity descriptions together.

**`Orion.OLM.MessageSources`** is "IP addresses from which Log Viewer received a message or
event", carrying `MessageSourceID`, `NodeID`, `EngineID`, `Caption`, `IPAddress`,
`MachineType`, `Vendor`, `Created` ("Date and time when first message was received from
this IP address") and `Status` ("License status of the message source"). The description
adds the crucial sentence: "Message sources can be duplicated for various reasons: If there
is more message sources with the same `NodeID`, they still count as one Orion node."

**`Orion.OLM.Nodes`** is the deduplicated licensing view: `NodeID`, `Status` ("Number
defining license status of the message source") and `LicenseStatus` (its description). It
is "Orion nodes licensed for gathering messages and events".

So a multi-homed switch sending from three addresses produces three
`Orion.OLM.MessageSources` rows and one `Orion.OLM.Nodes` row. Count sources when you care
about senders and nodes when you care about licences, and never `COUNT(NodeID)` on the
source entity expecting a licence number.

`Orion.OLM.MessageSources` supports create, read, update and delete, requiring `admin` or
`manageNodes`. `Caption`, `IPAddress`, `MachineType` and `Vendor` are documented as copies
from the mapped node, so the useful write is setting `NodeID` on a source the receiver
could not match by itself.

From a node, `Orion.Nodes.LogNode` reaches `Orion.OLM.Nodes` and
`Orion.Nodes.LogMessageSource` reaches `Orion.OLM.MessageSources`.

## Log profiles and agents

Syslog and traps arrive on their own. Log **files** have to be collected, and that is done
by an agent reading a path.

`Orion.OLM.LogProfile` is the collection definition: `LogProfileID`, `Name`, `Description`
and `Filepath` ("Filepath or mask to specify monitored files"). It navigates to
`Orion.AgentManagement.Agent` as `Agents`, with `Orion.AgentManagement.Agent.LogProfiles`
navigating back.

`Orion.OLM.LogProfileAgentAssignment` is the join row, `LogProfileID` plus `AgentId`. Note
the inconsistent casing: `LogProfileID` with a capital D, `AgentId` without. Both entities
allow create, read, update and delete, and both require **`admin` or `system`** rather than
`manageNodes`, so an account that can add nodes cannot necessarily assign a log profile.

Assigning a profile to an agent is a plain create:

```powershell
New-SwisObject $swis Orion.OLM.LogProfileAgentAssignment @{
    LogProfileID = $logProfileId
    AgentId      = $agentId
} | Out-Null
```

`Orion.OLM.HealthIssues` is the feedback channel for that arrangement: "Stores health
information related to Log node, agent assigned to node and Log profile on that node." It
carries `ID`, `NodeID`, `LogProfileID`, `MessageKey` ("Identifier of the health message"),
`Message`, `Severity` ("examples: warn, error") and `Priority` ("greater number means more
urgent"). It is where a profile pointing at a path that does not exist, or an agent that
cannot read it, shows up. Note that it declares no navigation properties, so `NodeID` and
`LogProfileID` stay raw ids unless you join them, and that `Severity` is a lowercase string
rather than an integer, so it does not join to
[`Orion.StatusInfo`](../reference/status-codes.md).

Health issues are writable under `admin` or `system`, which is how the collectors publish
into it. Treat it as read-only from your side.

See [agents.md](agents.md) for the agent itself.

## Rule processing and the alerting integration

Log Analyzer does not have its own alert engine. It has a rule engine that decides which
messages are interesting, and one of the things a rule can do is hand the message to the
platform's alerting.

`Orion.OLM.ProcessingRule` is the rule: `RuleDefinitionId` (a `System.Guid`), `Name`,
`ReadOnly` and `Enabled`. It allows `read` and `invoke` only, to `manageAlerts`, `admin` or
`system`, which places it firmly on the alerting side of the permission model rather than
the node-management side. It navigates to `Actions`.

`Orion.OLM.ProcessingRuleActions` is what the rule does when it matches: `RuleActionId`,
`RuleDefinitionId`, `Name` and `ActionType` ("Numeric value identifying the action type
(tag assignment, alerting action, ...)"). The two examples in that description are the two
that matter: a rule either labels the message with a tag or raises it to alerting. The
integer values are not enumerated in the schema, so read them off your own server before
filtering on one.

`Orion.OLM.RuleProcessingDefinitions` is the whole configuration as JSON:
`RuleProcessingDefinitionsId`, `RuleDefinitions` and `FieldDefinitions`. Its description
notes "You can subscribe to this entity to be notified about changes", which makes it the
entity to watch if you are keeping an external copy of the rule set in step.

**`Orion.OLM.AlertMessage` is the bridge to alerting.** It inherits from
`System.Indication`, not from a table type, which means it is an event SWIS publishes rather
than rows you select. Its properties are the payload handed to an alert: `NodeID`,
`RuleDefinitionID`, `Severity` ("Syslog severity"), `EventMessage` ("Message, which
triggered the rule"), `HitCount` ("Number of messages from the node, which met the rule"),
and a set of trap-specific fields, `Community`, `MessageType`, `RawMsg`, `VbName1` and
`VbData1`. `Description` is documented as "Not used". It navigates to `Orion.Nodes` as
`Nodes`, and from the node side as `Orion.Nodes.OLMAlertMessage`.

`HitCount` is the interesting one: the rule engine aggregates, so one indication can stand
for many messages, and an alert built on this will not fire once per line.

The other four indications are lifecycle signals rather than alert content:
`Orion.OLM.NodeLicensingChange`, `Orion.OLM.LicenseExpiration` and
`Orion.OLM.LicenseReset` declare no properties at all, and `Orion.OLM.NodeInfosChanged`
declares only `EngineID`. They exist so that log services on each polling engine learn
about changes made elsewhere.

To find the alerts an installation has built on log messages, filter
`Orion.AlertConfigurations` by `ObjectType`, which holds the entity name an alert triggers
on. There is a worked query for that [below](#7-alerts-that-trigger-on-log-messages). For
alerting generally, see SolarWinds'
[Alerts](https://solarwinds.github.io/OrionSDK/docs/alerts/) page and
[`../../scripts/swql/05-alerts.swql`](../../scripts/swql/05-alerts.swql).

## Verbs

Eleven verbs across three entities. Arguments are positional; the names below document the
order and never travel on the wire.

| Entity | Verb | Parameters, in order | Returns |
|---|---|---|---|
| `Orion.OLM.Nodes` | `EnableLogMonitoring` | `nodeId` | `System.Void` |
| `Orion.OLM.Nodes` | `DisableLogMonitoring` | `nodeId` | `System.Void` |
| `Orion.OLM.ProcessingRule` | `EnableRule` | `ruleId` | `System.Void` |
| `Orion.OLM.ProcessingRule` | `DisableRule` | `ruleId` | `System.Void` |
| `Orion.OLM.ProcessingRule` | `EnableRules` | `ruleIds` (a collection of GUIDs) | `System.Void` |
| `Orion.OLM.ProcessingRule` | `DisableRules` | `ruleIds` (a collection of GUIDs) | `System.Void` |
| `Orion.OLM.ProcessingRule` | `ExportRules` | `identifiers`, `separator` | string |
| `Orion.OLM.ProcessingRule` | `ImportRules` | `rulesJson` | `ImportRuleSummary` |
| `Orion.OLM.LogEntry` | `UidMinForDate` | `dateTime` | number |
| `Orion.OLM.LogEntry` | `UidMaxForDate` | `dateTime` | number |
| `Orion.OLM.LogEntry` | `UidExtractDate` | `uniqueId` | string |

`EnableLogMonitoring` takes a plain node id, not a NetObject string. It is the licensing
switch: it is what puts a node into `Orion.OLM.Nodes`.

```powershell
$swis = Connect-Swis -Hostname orion.example.com -Credential $cred

$nodeId = Get-SwisData $swis @"
SELECT TOP 1 NodeID FROM Orion.Nodes WHERE Caption = @caption
"@ @{ caption = 'core-sw-01' }

Invoke-SwisVerb $swis Orion.OLM.Nodes EnableLogMonitoring @($nodeId)
```

`ExportRules` and `ImportRules` are the pair worth building on, because they are how a rule
set moves between a test installation and production. `ExportRules` takes
`identifiers` and `separator`: "Export rules, either specified by name, rule ID or all if
no identification is provided (separate multiple values by the separator, comma is used if
not specified)." Both parameters are declared required in the contract, so pass an empty
string for `identifiers` when you want everything rather than omitting the argument.

```powershell
# Export the full rule set, then import it somewhere else.
$json = Invoke-SwisVerb $swis Orion.OLM.ProcessingRule ExportRules @('', ',')

$summary = Invoke-SwisVerb $target Orion.OLM.ProcessingRule ImportRules @($json)
```

`ImportRules` returns `SolarWinds.Orion.Core.Common.Models.ImportRuleSummary`, whose fields
are not published in the extracted contract, so inspect the returned object rather than
assuming a shape. Whether an import replaces or merges the existing rules is likewise
**not stated** in the schema; test it against a non-production installation first.

The three `Orion.OLM.LogEntry` verbs are all documented as "For internal use only." Their
names and signatures are consistent with `LogEntryID` encoding a timestamp, so that a
date range can be turned into an id range without touching the `DateTime` column, but that
is an inference from the names and is **not verified**. They are declared internal, so do
not build on them: write the `DateTime` predicate instead.

## Worked queries

Every query below has been validated against the 2026.2 schema with
`python3 tools/validate_swql.py`.

### 1. Export events over a window

This is SolarWinds' own example, extended. It filters on `DateTime` in UTC, narrows to one
message type through the `LogType` navigation, and pages with
`WITH ROWS ... WITH TOTALROWS` so an export can walk a large result without re-running the
scan.

```sql
SELECT
    le.DateTime,
    le.MessageDateTime,
    le.LevelKey,
    le.LogType.Type AS SourceType,
    le.LogMessageSource.IPAddress AS SourceIPAddress,
    le.LogMessageSource.Caption AS NodeName,
    le.Message
FROM Orion.OLM.LogEntry le
WHERE le.DateTime >= @startUtc
  AND le.DateTime < @endUtc
  AND le.LogType.Type = @sourceType
ORDER BY le.DateTime DESC
WITH ROWS 1 TO 5000 WITH TOTALROWS
```

Driven from PowerShell, following the shape SolarWinds publishes on
[Exporting Log Events](https://solarwinds.github.io/OrionSDK/docs/log-analyzer/exporting-log-events/):

```powershell
$swis = Connect-Swis -Hostname orion.example.com -Credential $cred

$endUtc   = [DateTime]::UtcNow
$startUtc = $endUtc.AddHours(-12)

$query = @"
SELECT
    le.DateTime,
    le.MessageDateTime,
    le.LevelKey,
    le.LogType.Type AS SourceType,
    le.LogMessageSource.IPAddress AS SourceIPAddress,
    le.LogMessageSource.Caption AS NodeName,
    le.Message
FROM Orion.OLM.LogEntry le
WHERE le.DateTime >= @startUtc
  AND le.DateTime < @endUtc
  AND le.LogType.Type = @sourceType
ORDER BY le.DateTime DESC
WITH ROWS 1 TO 5000 WITH TOTALROWS
"@

Get-SwisData $swis $query @{
    startUtc   = $startUtc
    endUtc     = $endUtc
    sourceType = 'Syslog'
} | Export-Csv -Path 'LogExport.csv' -NoTypeInformation
```

The window is built in .NET, in UTC, and passed in as a bound parameter. That avoids the
`GetUtcDate()` plus `AddHour` trap described in
[../swql/date-and-time.md](../swql/date-and-time.md) entirely, which is the reason
SolarWinds' sample does it the same way.

Twelve hours is their example, not a recommendation. On a busy installation twelve hours of
syslog is millions of rows; start with one hour and widen only after you have seen
`TOTALROWS`.

### 2. How much is arriving, by type and severity

The query to run before any of the others, because it tells you what a window costs. Group
on `LevelKey` rather than `Level` so the result is stable across localised installations.

```sql
SELECT
    le.LogType.Type AS SourceType,
    le.LevelKey,
    COUNT(le.LogEntryID) AS Messages
FROM Orion.OLM.LogEntry le
WHERE le.DateTime >= @startUtc
  AND le.DateTime < @endUtc
GROUP BY le.LogType.Type, le.LevelKey
ORDER BY COUNT(le.LogEntryID) DESC
```

### 3. The noisiest senders in a window

One device in a retry loop can account for most of a day's volume, and this is how you find
it. Grouping by the source rather than the node keeps multi-homed devices separate, which is
usually what you want when the goal is to silence one interface.

```sql
SELECT TOP 25
    ms.MessageSourceID,
    ms.IPAddress,
    ms.Caption,
    ms.NodeID,
    ms.EngineID,
    ms.Status,
    COUNT(le.LogEntryID) AS Messages
FROM Orion.OLM.MessageSources ms
JOIN Orion.OLM.LogEntry le ON le.MessageSourceID = ms.MessageSourceID
WHERE le.DateTime >= @startUtc
  AND le.DateTime < @endUtc
GROUP BY ms.MessageSourceID, ms.IPAddress, ms.Caption, ms.NodeID, ms.EngineID, ms.Status
ORDER BY COUNT(le.LogEntryID) DESC
```

### 4. Senders that were never matched to a node

A source with a null `NodeID` is a device sending messages that the platform cannot
attribute, which means those messages will never trigger a node-scoped alert. Ordering by
`Created` puts the newest unrecognised sender first, which is usually the one someone just
pointed at the collector.

```sql
SELECT TOP 100
    ms.MessageSourceID,
    ms.IPAddress,
    ms.Caption,
    ms.Created,
    ms.Status,
    ms.MachineType,
    ms.Vendor
FROM Orion.OLM.MessageSources ms
WHERE ms.NodeID IS NULL
ORDER BY ms.Created DESC
```

To fix one, update the source with the node id you want it attributed to. The entity allows
`update` under `admin` or `manageNodes`:

```powershell
Set-SwisObject $swis -Uri $messageSourceUri -Properties @{ NodeID = $nodeId }
```

### 5. Log file collection, and whether it is working

`Orion.OLM.LogProfile` joined to its agents tells you what should be collected and from
where; `Orion.OLM.HealthIssues` tells you where it is not.

```sql
SELECT TOP 200
    p.LogProfileID,
    p.Name,
    p.Description,
    p.Filepath,
    p.Agents.Name AS AgentName,
    p.Agents.NodeID AS AgentNodeID,
    p.Agents.ConnectionStatus AS AgentConnectionStatus
FROM Orion.OLM.LogProfile p
ORDER BY p.Name
```

```sql
SELECT TOP 200
    hi.Priority,
    hi.Severity,
    hi.NodeID,
    hi.LogProfileID,
    hi.MessageKey,
    hi.Message
FROM Orion.OLM.HealthIssues hi
ORDER BY hi.Priority DESC
```

`HealthIssues` has no navigation properties, so pair it with the profile list above rather
than expecting a `LogProfile` hop.

### 6. Rules and what they do

`ActionType` is the column that separates a rule that only tags from a rule that raises an
alert. The integers are not enumerated in the schema, so read them next to the action names
your installation has actually configured.

```sql
SELECT TOP 200
    r.RuleDefinitionId,
    r.Name,
    r.Enabled,
    r.ReadOnly,
    r.Actions.Name AS ActionName,
    r.Actions.ActionType AS ActionType
FROM Orion.OLM.ProcessingRule r
ORDER BY r.Name
```

### 7. Alerts that trigger on log messages

`Orion.AlertConfigurations.ObjectType` holds the entity name an alert is defined against, so
this finds every alert wired to the log module without needing to know which OLM entity was
used.

```sql
SELECT TOP 100
    ac.AlertID,
    ac.Name,
    ac.ObjectType,
    ac.Enabled,
    ac.Severity,
    ac.Frequency
FROM Orion.AlertConfigurations ac
WHERE ac.ObjectType LIKE 'Orion.OLM.%'
ORDER BY ac.Name
```

An empty result does not mean log alerting is off. It means no alert is scoped to an OLM
entity, which is normal when the rules tag messages instead of raising them.

### 8. Retention, per message type

Short, and worth running before anyone asks "how far back can we look".

```sql
SELECT
    t.LogEntryTypeID,
    t.Type,
    t.Name,
    t.RetentionPeriodInDays,
    t.DetailPageEnabled
FROM Orion.OLM.LogEntryType t
ORDER BY t.RetentionPeriodInDays
```

The entity allows `update` under `admin`, so this is also the list you change when
retention needs adjusting. Lengthening it grows the largest table on the system; do the
arithmetic against query 2 first.

### 9. Everything carrying a particular tag

Tags are how a processing rule marks the messages someone decided to care about, which makes
this the closest thing the module has to a saved search. The `DateTime` bound is still
mandatory: a tag filter narrows the result, not the scan.

```sql
SELECT TOP 500
    le.DateTime,
    le.LevelKey,
    le.LogMessageSource.Caption AS NodeName,
    le.Tags.Name AS TagName,
    le.Message
FROM Orion.OLM.LogEntry le
WHERE le.DateTime >= @startUtc
  AND le.DateTime < @endUtc
  AND le.Tags.Name = @tagName
ORDER BY le.DateTime DESC
```

### 10. Parsed field values for a window

When rules have extracted structured fields out of unstructured messages, this is where
they land. Bounding through `fv.Event.DateTime` pushes the time predicate onto the entry,
which is the column worth filtering.

```sql
SELECT TOP 500
    fv.LogEntryID,
    fv.Name,
    fv.TextValue,
    fv.NumericValue,
    fv.DateTimeValue,
    fv.Event.DateTime AS EntryDateTime
FROM Orion.OLM.LogEntryFieldValue fv
WHERE fv.Event.DateTime >= @startUtc
  AND fv.Event.DateTime < @endUtc
  AND fv.Name = @fieldName
ORDER BY fv.LogEntryID DESC
```

### 11. Which nodes are licensed for log collection

```sql
SELECT TOP 100
    n.Caption,
    n.IPAddress,
    n.LogNode.Status AS LogLicenseStatus,
    n.LogNode.LicenseStatus AS LogLicenseStatusText
FROM Orion.Nodes n
WHERE n.LogNode.NodeID IS NOT NULL
ORDER BY n.Caption
```

Nodes absent from this result are not collecting. `EnableLogMonitoring` is how one is added.

## Gotchas

**An unbounded `Orion.OLM.LogEntry` query is a production incident, not a slow query.**
This is the largest table on most installations. Always bound `DateTime`, always bound the
result set, and start narrower than you think you need. The same applies to
`Orion.OLM.LogEntryFieldValue`, which is at least as large.

**`DateTime` and `MessageDateTime` are different columns and only one is safe to filter on.**
`DateTime` is receipt time, in UTC, and is what your window should use. `MessageDateTime`
comes out of the message text and depends on the sender's clock.

**`Level` is translated and `LevelKey` is not.** Filter on `LevelKey`. The same pair appears
on `Orion.OLM.LogEntryLevel`, and `Orion.OLM.LogEntryType` has the same trap with `Name`
(translated) and `Type` (not).

**A message source is not a node.** Several sources can map to one node, and the schema says
so explicitly. Count `Orion.OLM.MessageSources` for senders and `Orion.OLM.Nodes` for
licensed nodes. A source with a null `NodeID` is unattributed traffic.

**Log Analyzer permissions do not follow node permissions.** `Orion.OLM.LogProfile`,
`Orion.OLM.LogProfileAgentAssignment` and `Orion.OLM.HealthIssues` require `admin` or
`system`. `Orion.OLM.ProcessingRule` and its actions require `manageAlerts`, `admin` or
`system`. Only `Orion.OLM.MessageSources` accepts `manageNodes`. An account that manages
nodes all day will be refused almost everywhere in this module.

**`Orion.OLM.AlertMessage` cannot be selected from.** It inherits `System.Indication`: it is
an event published to alerting, not a table. If you want the messages behind an alert, query
`Orion.OLM.LogEntry` for the node and window the alert covers.

**Six entities declare no operations at all.** `Orion.OLM.Tags`,
`Orion.OLM.LogEntryTagAssignment`, `Orion.OLM.LogEntryLevel`,
`Orion.OLM.LogEntrySecondarySources`, `Orion.OLM.LogEntrySecondarySourceAssignment` and the
indications. They are readable through navigation but are not part of the CRUD surface.

**`AgentId` and `LogProfileID` are cased differently on the same entity.**
`Orion.OLM.LogProfileAgentAssignment` declares `LogProfileID` and `AgentId`. SWQL is not
case sensitive about property names, but a CRUD payload assembled from the wrong spelling in
a strongly typed client will be.

**The three `Orion.OLM.LogEntry` verbs are internal.** `UidMinForDate`, `UidMaxForDate` and
`UidExtractDate` all carry the summary "For internal use only." They will change without
notice.

**Account limitations filter silently.** Two accounts running the same export get different
rows, with no indication that anything was removed. A missing message is as often a
permissions problem as a collection problem.

## What is not verified here

| Claim | Status | How to check on your server |
|---|---|---|
| The full list of `Orion.OLM.LogEntryType.Type` values | SolarWinds' export page names `Syslog` and `Traps`; the schema enumerates nothing, and installations that collect log files or VMware events have more | `SELECT LogEntryTypeID, Type, Name, RetentionPeriodInDays FROM Orion.OLM.LogEntryType ORDER BY Type` |
| The `ActionType` integers on `Orion.OLM.ProcessingRuleActions` | The description names "tag assignment, alerting action" without numbering them | `SELECT ActionType, COUNT(RuleActionId) AS Actions FROM Orion.OLM.ProcessingRuleActions GROUP BY ActionType` |
| The `Status` integers on `Orion.OLM.MessageSources` and `Orion.OLM.Nodes` | Documented as "license status" with no value list. `Orion.OLM.Nodes.LicenseStatus` gives the text for its own column; the source entity has no text column | `SELECT Status, COUNT(MessageSourceID) AS Sources FROM Orion.OLM.MessageSources GROUP BY Status`, and the same shape against `Orion.OLM.Nodes` alongside `LicenseStatus` |
| What `ImportRules` does to rules that already exist | Not stated. The verb returns an `ImportRuleSummary` whose fields are not published in the extracted contract | Export first, import into a non-production installation, and compare |
| That `LogEntryID` encodes the receipt date | Inferred from `UidMinForDate`, `UidMaxForDate` and `UidExtractDate` plus the `System.Int64` key. All three verbs are marked internal | `Invoke-SwisVerb $swis Orion.OLM.LogEntry UidExtractDate @($someLogEntryId)` on a test system, and compare against that entry's `DateTime` |
| The field names available in `Orion.OLM.LogEntryFieldValue` | Defined by the installation's parsing rules, not by the schema | `SELECT TOP 50 Name, COUNT(LogEntryFieldValueID) AS Values FROM Orion.OLM.LogEntryFieldValue WHERE Event.DateTime >= @startUtc GROUP BY Name` |
| The severity strings in `Orion.OLM.HealthIssues.Severity` | The description gives "warn, error" as examples, not as the full set | `SELECT Severity, COUNT(ID) AS Issues FROM Orion.OLM.HealthIssues GROUP BY Severity` |

## Related pages

- [README.md](README.md) for the module index and how to check what is installed.
- [agents.md](agents.md) for `Orion.AgentManagement.Agent`, which collects log files.
- [../swql/performance.md](../swql/performance.md) for paging and for why bounding matters.
- [../swql/date-and-time.md](../swql/date-and-time.md) before building any UTC window.
- [../swis/invoke-verbs.md](../swis/invoke-verbs.md) for positional verb arguments.
- [../swis/crud.md](../swis/crud.md) for creating profile assignments and fixing message
  source mappings.
- [../../scripts/swql/05-alerts.swql](../../scripts/swql/05-alerts.swql) for the alerting
  side of the integration.
- [../../scripts/swql/06-events-and-auditing.swql](../../scripts/swql/06-events-and-auditing.swql)
  for `Orion.Events`, which is the platform's own event stream and a different thing from
  a log message.
- SolarWinds'
  [Exporting Log Events](https://solarwinds.github.io/OrionSDK/docs/log-analyzer/exporting-log-events/),
  the module's only published SDK page.

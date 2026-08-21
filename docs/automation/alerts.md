# Alerts

Alerting is the part of the platform people most often want to drive from a script, and it
is also the part with the most entities that sound like they do the same thing. There is an
`Orion.AlertConfigurations` and an `Orion.AlertDefinitions`. There is an `Orion.AlertActive`
and an `Orion.ActiveAlerts` and an `Orion.AlertStatus`. Picking the wrong one gives you a
query that runs, returns zero rows on a system that is visibly alerting, and tells you
nothing about why.

This page settles which entities exist in 2026.2, what each one holds, how they join, and
then works through the tasks: list what is firing, acknowledge it, find and toggle
definitions, read history, and suppress alerts for a window.

SolarWinds' own reference for these entities is
[Alert Entities](https://solarwinds.github.io/OrionSDK/docs/alerts/), and it is the source
for the enumerated values on this page that the schema does not carry.

## The entities that exist

All nine entities named in this repository's brief are present in 2026.2. Confirm any of
them yourself:

```bash
python3 tools/schema_query.py show Orion.AlertActive
python3 tools/schema_query.py show Orion.AlertObjects
python3 tools/schema_query.py find alert
```

| Entity | Props | Verbs | What it holds |
|:---|---:|---:|:---|
| `Orion.AlertConfigurations` | 20 | 6 | The alert **definition**: name, trigger, severity, `Enabled` |
| `Orion.AlertObjects` | 18 | 0 | One row per (definition, triggering object) pair, ever |
| `Orion.AlertActive` | 11 | 4 | One row per alert that is **firing right now** |
| `Orion.AlertActiveObjects` | 10 | 0 | Contributing objects for a **cumulative** alert |
| `Orion.AlertHistory` | 8 | 0 | The log: triggered, reset, acknowledged, action ran |
| `Orion.AlertSuppression` | 4 | 3 | Scheduled muting of alerts for an entity URI |
| `Orion.Actions` | 7 | 9 | Action instances (send email, run script) |
| `Orion.ActionsAssignments` | 5 | 0 | Which action is attached to which alert, and as what |
| `Orion.AlertSchedules` | 2 | 0 | Cross-reference from an alert to an `Orion.Frequencies` row |
| `Orion.AlertDefinitions` | 23 | 0 | The **legacy** advanced-alert definition (see below) |
| `Orion.AlertStatus` | 18 | 3 | The **legacy** active-alert state (see below) |
| `Orion.ActiveAlerts` | 16 | 0 | A legacy-shaped view keyed on `AlertID` and `ObjectID` |

The first nine are the current model. The last three are the older one, and mixing the two
is the single most common way an alerting query goes wrong.

### Current model versus legacy model

The current entities key on an **integer** `AlertID` and hang everything off
`AlertObjectID`. The legacy entities key on a **GUID** `AlertDefID` and carry the trigger as
a SWQL-ish `TriggerQuery` string:

```bash
python3 tools/schema_query.py props Orion.AlertDefinitions
```

```text
Orion.AlertDefinitions properties (27 shown, including inherited)
  AlertDefID                                 System.Guid                 
  Name                                       System.String               
  Description                                System.String               
  Enabled                                    System.Boolean              
  StartTime                                  System.DateTime             
  EndTime                                    System.DateTime             
  DOW                                        System.String               
```

The rest of that list carries `TriggerQuery`, `ResetQuery`, `SuppressionQuery`,
`TriggerSustained`, `ResetSustained`, `ExecuteInterval`, `LastExecuteTime`, `BlockUntil`,
`LastError` and `Reverted`, none of which have counterparts on
`Orion.AlertConfigurations`. `Orion.AlertStatus` is the matching state table and keys on the
same GUID:

```bash
python3 tools/schema_query.py props Orion.AlertStatus
```

```text
Orion.AlertStatus properties (26 shown, including inherited)
  AlertDefID                                 System.Guid                 
  ActiveObject                               System.String               
  ObjectType                                 System.String               
  State                                      System.Byte                 
  WorkingState                               System.Byte                 
```

`Orion.AlertConfigurations` carries three verbs whose names say what that relationship is:
`MigrateAllAdvancedAlerts`, `MigrateAdvancedAlert` and `MigrateAdvancedAlertFromXML`. Those
names, plus the GUID-keyed shape of `Orion.AlertDefinitions`, are consistent with the legacy
entities being the pre-2015 "advanced alerts" model that the current model replaced, and the
verbs being the migration path. That reading is an **inference from the verb names and the
column shapes; the schema does not state it**. What is certain is that all three migration
verbs take no typed parameters in 2026.2, so their calling convention cannot be documented
from the extracted data:

```bash
python3 tools/schema_query.py verb Orion.AlertConfigurations MigrateAdvancedAlert
```

```text
Orion.AlertConfigurations.MigrateAdvancedAlert
  requires: admin
  parameters: none
```

**Write new work against the current model.** Everything after this section does.

## How the current entities join

```text
                 Orion.AlertConfigurations          the definition
                    AlertID (int, PK)
                    Name, Enabled, Severity, ObjectType, Frequency
                          ^
                          | AlertConfigurations   (nav property, source)
                          |
                 Orion.AlertObjects                 definition x triggering object
                    AlertObjectID (int, PK)
                    AlertID, EntityUri, EntityType, EntityCaption,
                    EntityNetObjectId, RelatedNodeId, IsActiveAlert,
                    TriggeredCount, LastTriggeredDateTime
                       ^                       ^                      \
                       | AlertObjects          | AlertObjects          \ Node
                       |                       |                        v
        Orion.AlertActive              Orion.AlertHistory          Orion.Nodes
           AlertActiveID (bigint, PK)     AlertHistoryID (PK)
           AlertObjectID (FK)             EventType, Message, TimeStamp,
           Acknowledged, AcknowledgedBy,  AccountID, AlertActiveID,
           TriggeredDateTime,             AlertObjectID, ActionID
           TriggeredMessage
                       |
                       | AlertActiveObjects
                       v
        Orion.AlertActiveObjects          cumulative alerts only
           AlertActiveID, EntityUri, EntityCaption, EntityType
```

Read that top to bottom and the model is simple:

- **`Orion.AlertConfigurations` is the definition.** It is what you edit in Alert Manager.
  It knows nothing about what has fired.
- **`Orion.AlertObjects` is the join table, and it is the entity that matters.** It is the
  only place that records *which object* an alert is about. It holds one row per
  (definition, object) pair that has **ever** triggered, and the rows survive the reset. Its
  `IsActiveAlert` flag distinguishes currently firing pairs from historical ones.
- **`Orion.AlertActive` is the live set.** A row exists only while the alert is firing.
  Reset or clear the alert and the row disappears. It carries the acknowledgement state.
- **`Orion.AlertHistory` is the durable log.** Rows are not removed on reset, which is why
  it, and not `Orion.AlertActive`, answers "what fired last night".

The navigation properties are declared both ways, so you can join explicitly on the id
columns or walk the dotted path. Both of these are valid SWQL:

```sql
SELECT aa.AlertActiveID, ao.EntityCaption
FROM Orion.AlertActive aa
JOIN Orion.AlertObjects ao ON aa.AlertObjectID = ao.AlertObjectID
```

```sql
SELECT aa.AlertActiveID, aa.AlertObjects.EntityCaption AS EntityCaption
FROM Orion.AlertActive aa
```

The dotted form is shorter; the explicit `JOIN` is easier to read when there are three or
four hops. Neither is faster. See
[../swql/joins-and-navigation.md](../swql/joins-and-navigation.md).

### The properties on `Orion.AlertObjects` worth knowing

```bash
python3 tools/schema_query.py props Orion.AlertObjects
```

| Property | Why you want it |
|:---|:---|
| `EntityUri` | The canonical reference. This is what `SuppressAlerts` takes. |
| `EntityNetObjectId` | The NetObject string, for example `N:42`. This is what `Unmanage` takes. |
| `EntityType` | The SWIS entity name, for example `Orion.Nodes`. Filter on it. |
| `EntityCaption` | The display name. |
| `EntityDetailsUrl` | A **relative** URL. Prefix it with the web console's scheme and host. |
| `RelatedNodeId`, `RelatedNodeCaption`, `RelatedNodeUri` | The hosting node, for interfaces, volumes, applications. Blank for objects that have no node. |
| `RealEntityUri`, `RealEntityType` | Present alongside `EntityUri`. Use `EntityUri` unless you have a reason not to. |
| `IsActiveAlert` | `TRUE` while the pair is firing. |
| `TriggeredCount`, `LastTriggeredDateTime` | Running counters. Good for a noisiest-alerts report without touching history. |

Having both a URI and a NetObject id on one row is the practical reason `Orion.AlertObjects`
is the entity to query when you intend to *act* on what alerted. Suppression wants the URI,
`Unmanage` wants the NetObject id, and both come back in one pass.

## Listing active alerts with the object that triggered them

This is the query that goes on the wall.

```sql
SELECT
    aa.AlertActiveID,
    aa.AlertObjectID,
    ao.AlertConfigurations.Name AS AlertName,
    ao.AlertConfigurations.Severity AS Severity,
    ao.EntityType,
    ao.EntityCaption,
    ao.EntityNetObjectId,
    ao.EntityUri,
    ao.RelatedNodeCaption,
    aa.TriggeredDateTime,
    aa.TriggeredMessage,
    aa.Acknowledged,
    aa.AcknowledgedBy
FROM Orion.AlertActive aa
JOIN Orion.AlertObjects ao ON aa.AlertObjectID = ao.AlertObjectID
ORDER BY aa.TriggeredDateTime DESC
```

Two things about it are deliberate:

- **`AlertObjectID` is selected, not just joined on.** It is the argument every one of the
  four `Orion.AlertActive` verbs takes. Selecting it here means the acknowledgement step does
  not have to re-derive the scope.
- **The name comes from `Orion.AlertConfigurations`, not from `Orion.AlertActive`.** There is
  no alert name on the active row. `TriggeredMessage` is the rendered message, which is
  usually not the definition's name.

`Severity` is an integer. The schema does not carry the mapping;
[SolarWinds' alerts page](https://solarwinds.github.io/OrionSDK/docs/alerts/) does:

| `Severity` | Meaning |
|---:|:---|
| 0 | Information |
| 1 | Warning |
| 2 | Critical |
| 3 | Serious |
| 4 | Notice |

Note that the numbers are not in order of urgency, so `ORDER BY Severity DESC` sorts Notice
above Critical. If you want a triage order, spell it out:

```sql
SELECT
    ao.AlertConfigurations.Name AS AlertName,
    ao.EntityCaption,
    aa.TriggeredDateTime,
    CASE WHEN ao.AlertConfigurations.Severity = 2 THEN 1   -- Critical
         WHEN ao.AlertConfigurations.Severity = 3 THEN 2   -- Serious
         WHEN ao.AlertConfigurations.Severity = 1 THEN 3   -- Warning
         WHEN ao.AlertConfigurations.Severity = 4 THEN 4   -- Notice
         WHEN ao.AlertConfigurations.Severity = 0 THEN 5   -- Information
         ELSE 9 END AS TriageOrder
FROM Orion.AlertActive aa
JOIN Orion.AlertObjects ao ON aa.AlertObjectID = ao.AlertObjectID
WHERE aa.Acknowledged = FALSE
ORDER BY TriageOrder, aa.TriggeredDateTime
```

### Everything firing on one node

`RelatedNodeId` is populated for objects that hang off a node, and `EntityType` tells you
whether the alert is about the node itself:

```sql
SELECT
    ao.AlertConfigurations.Name AS AlertName,
    ao.EntityType,
    ao.EntityCaption,
    aa.TriggeredDateTime,
    aa.Acknowledged
FROM Orion.AlertActive aa
JOIN Orion.AlertObjects ao ON aa.AlertObjectID = ao.AlertObjectID
WHERE ao.RelatedNodeId = @nodeId
   OR (ao.EntityType = 'Orion.Nodes' AND ao.EntityNetObjectId = @netObjectId)
ORDER BY aa.TriggeredDateTime DESC
```

`Orion.AlertObjects` also declares a `Node` navigation property straight to `Orion.Nodes`, so
the same thing reads more directly when you only care about node-related alerts:

```sql
SELECT
    ao.AlertConfigurations.Name AS AlertName,
    ao.EntityCaption,
    ao.Node.Caption AS NodeCaption,
    ao.Node.Status AS NodeStatus,
    ao.LastTriggeredDateTime
FROM Orion.AlertObjects ao
WHERE ao.IsActiveAlert = TRUE
  AND ao.Node.NodeID = @nodeId
```

And the reverse direction is declared too, which is convenient inside a node report:

```sql
SELECT
    n.Caption,
    n.AlertObjects.AlertConfigurations.Name AS AlertName,
    n.AlertObjects.IsActiveAlert AS IsActive
FROM Orion.Nodes n
WHERE n.NodeID = @nodeId
```

### Turning `EntityDetailsUrl` into a link

`EntityDetailsUrl` is relative. `Orion.Websites` holds the console's host and port, so you do
not have to hard-code them:

```sql
SELECT TOP 1 ServerName, FQDN, Port, SSLEnabled, ExternalUrl
FROM Orion.Websites
```

Read that once at the start of a report and concatenate in the client, or in SWQL with
`Concat`. The point is that the host is data, not a constant, and it differs between a
primary and an additional web server.

### Cumulative alerts

A cumulative alert is one whose condition spans several objects, such as "five nodes have
high CPU". For those, SolarWinds' documentation states that `EntityUri`, `EntityDetailsUrl`
and the `RelatedNode...` properties on `Orion.AlertObjects` are blank and `EntityCaption`
reads like "38 interfaces" rather than naming an object. The contributing objects live in
`Orion.AlertActiveObjects` instead, keyed on `AlertActiveID`:

```sql
SELECT
    aa.AlertActiveID,
    aa.AlertObjects.AlertConfigurations.Name AS AlertName,
    aa.AlertObjects.EntityCaption AS Summary,
    aa.AlertActiveObjects.EntityType AS ContributingType,
    aa.AlertActiveObjects.EntityCaption AS ContributingObject,
    aa.AlertActiveObjects.EntityUri AS ContributingUri
FROM Orion.AlertActive aa
ORDER BY aa.AlertActiveID
```

SolarWinds notes that this entity "is used only for cumulative alert resolution and otherwise
is empty", so an empty result here is the normal case, not a fault.

## Acknowledging an alert

Four verbs, all on `Orion.AlertActive`, all requiring the **`clearEvents`** right:

```bash
python3 tools/schema_query.py verbs --entity Orion.AlertActive
```

| Verb | Parameters | Returns |
|:---|:---|:---|
| `Acknowledge` | `(alertObjectIds: array<number>, notes: string)` | boolean |
| `Unacknowledge` | `(alertObjectIds: array<number>)` | boolean |
| `AppendNote` | `(alertObjectIds: array<number>, note: string)` | boolean |
| `ClearAlert` | `(alertObjectIds: array<number>)` | boolean |

Both parameters on `Acknowledge` are **required**, so there is no one-argument form. Pass an
empty string if you genuinely have no note.

### Pass `AlertObjectID`, not `AlertActiveID`

This is the one thing to get right. The parameter is named `alertObjectIds` and
[SolarWinds' documentation](https://solarwinds.github.io/OrionSDK/docs/alerts/) says "pass
the AlertObjectID values". The verb's own summary text in the schema reads "based on array of
alert active ids", which contradicts both:

```bash
python3 tools/schema_query.py verb Orion.AlertActive Acknowledge
```

```text
Orion.AlertActive.Acknowledge
  Acknowledge active alerts, based on array of alert active ids and desired notes.
  returns: boolean
  REST:    POST /Invoke/Orion.AlertActive/Acknowledge
  requires: clearEvents
  parameters (2):
    alertObjectIds: array<number> (required)
    notes: string (required)
```

The parameter name and the published documentation agree with each other, so **pass
`AlertObjectID`**. The summary line is the outlier. The two ids are different columns with
different values, and passing the wrong one either acknowledges nothing or acknowledges
something else, quietly, because the verb returns a single boolean rather than per-item
results. Verify with a read-back, which is the general rule in
[README.md](README.md) and is not optional here.

### PowerShell

```powershell
Import-Module SwisPowerShell
$swis = Connect-Swis -Hostname orion.example.com -Trusted

# 1. Scope. Read it before acting on it.
$targets = Get-SwisData $swis @'
SELECT
    aa.AlertObjectID,
    ao.AlertConfigurations.Name AS AlertName,
    ao.EntityCaption
FROM Orion.AlertActive aa
JOIN Orion.AlertObjects ao ON aa.AlertObjectID = ao.AlertObjectID
WHERE aa.Acknowledged = FALSE
  AND ao.AlertConfigurations.Name = @alertName
'@ @{ alertName = 'Node down' }

$targets | Format-Table
"$($targets.Count) alert(s) to acknowledge."

# 2. Act. The first argument is an array of ints; the second is the note.
$ids = [int[]] $targets.AlertObjectID
$note = "Acknowledged by change CHG0041288 at $([DateTime]::UtcNow.ToString('u'))"

$ok = Invoke-SwisVerb $swis 'Orion.AlertActive' 'Acknowledge' @($ids, $note)
$ok.InnerText

# 3. Verify. The boolean is not proof.
Get-SwisData $swis @'
SELECT aa.AlertObjectID, aa.Acknowledged, aa.AcknowledgedBy, aa.AcknowledgedDateTime
FROM Orion.AlertActive aa
WHERE aa.AlertObjectID IN @ids
'@ @{ ids = $ids } | Format-Table
```

Two PowerShell details that bite:

- **`Invoke-SwisVerb` returns an XML element, not a value.** Use `.InnerText` (or `.'#text'`)
  to get the boolean out. This is the same pitfall SolarWinds documents for
  `Orion.AlertConfigurations.Export`.
- **Cast the id array explicitly.** `Get-SwisData` hands back `PSObject`-wrapped values, and
  `[int[]]` makes the serialiser produce an array of numbers rather than an array of
  something else. For a **single-argument** verb whose argument is itself an array, such as
  `Unacknowledge` or `ClearAlert`, you additionally need the leading-comma idiom or
  PowerShell flattens your one array into N arguments:

```powershell
Invoke-SwisVerb $swis 'Orion.AlertActive' 'Unacknowledge' @( , [int[]] $ids ) | Out-Null
```

### REST

The body is a positional JSON array, in the parameter order above:

```bash
curl -k -u "$SWIS_USER:$SWIS_PASS" \
  -H 'Content-Type: application/json' \
  -X POST "https://orion.example.com:17774/SolarWinds/InformationService/v3/Json/Invoke/Orion.AlertActive/Acknowledge" \
  -d '[[1183, 1184, 1190], "Acknowledged by change CHG0041288"]'
```

The outer array is the argument list; the inner array is the first argument. Getting one
level of nesting wrong is the usual cause of a `400` here. See
[../swis/invoke-verbs.md](../swis/invoke-verbs.md).

### `AppendNote` versus `Acknowledge`

`AppendNote` records the note without changing `Acknowledged`. Use it when a script wants to
annotate an alert ("ticket INC0092331 opened") without claiming ownership of it. Both write a
row into `Orion.AlertHistory` (`EventType` 2 for acknowledge, 3 for a note), so the audit
trail distinguishes them afterwards.

### `ClearAlert` is not a reset

`ClearAlert` deletes the active alert row. SolarWinds is explicit about the consequence: it
"will clear the alerts without running the normal Reset actions and without regards to the
state of the trigger condition", and "if the condition that triggered the alert still holds,
the alert will be triggered again the next time the condition is evaluated". So clearing a
stuck alert whose underlying condition is genuinely still true buys you one evaluation
interval and nothing more. Fix the condition, disable the definition, or suppress the entity.

`AcknowledgedNote` on `Orion.AlertActive` exists as a property but SolarWinds' documentation
states it "is not currently used". The note you pass to `Acknowledge` shows up in
`Orion.AlertHistory.Message`. Read notes from history, not from the active row.

## Listing alert definitions, and whether they are enabled

```sql
SELECT
    ac.AlertID,
    ac.Name,
    ac.Description,
    ac.ObjectType,
    ac.Enabled,
    ac.Severity,
    ac.Frequency,
    ac.Category,
    ac.Canned,
    ac.CreatedBy,
    ac.LastEdit,
    ac.NotifyEnabled,
    ac.LicenseFeatureName,
    ac.Uri
FROM Orion.AlertConfigurations ac
ORDER BY ac.Enabled, ac.Name
```

`Enabled = FALSE` is the first thing to check when the complaint is "nobody was paged":

```sql
SELECT ac.AlertID, ac.Name, ac.ObjectType, ac.Severity, ac.LastEdit, ac.CreatedBy
FROM Orion.AlertConfigurations ac
WHERE ac.Enabled = FALSE
ORDER BY ac.LastEdit DESC
```

A few of these columns are worth a sentence each:

- **`ObjectType`** is the entity the definition is written against, for example
  `Orion.Nodes`. It constrains what the trigger can reference.
- **`Trigger`, `Reset` and `Suppress`** are serialised condition documents, not SWQL you can
  read at a glance. Do not try to parse them in a report. `GetComplexPropertiesByAlertID`
  and `Export` are the supported ways to get at the internals.
- **`Canned`** marks the definitions that shipped with the product. Filtering
  `Canned = FALSE` gives you the ones your organisation actually wrote.
- **`Frequency`** is `System.Int64`. The schema gives no unit, so measure it against a
  definition whose evaluation interval you set yourself rather than assuming seconds.
- **`LicenseFeatureName`** is why a definition can exist and never evaluate: it belongs to a
  module that is not licensed here.

### Which definitions have actually fired

`Orion.AlertObjects` keeps a running counter per (definition, object) pair, which is a much
cheaper way to find dead definitions than scanning history:

```sql
SELECT
    ac.AlertID,
    ac.Name,
    ac.Enabled,
    IsNull(SUM(ao.TriggeredCount), 0) AS TotalTriggers,
    MAX(ao.LastTriggeredDateTime) AS LastFired
FROM Orion.AlertConfigurations ac
LEFT JOIN Orion.AlertObjects ao ON ac.AlertID = ao.AlertID
GROUP BY ac.AlertID, ac.Name, ac.Enabled
ORDER BY MAX(ao.LastTriggeredDateTime) DESC
```

An enabled definition with `TotalTriggers = 0` and no `LastFired` has either never matched
anything or is scoped to objects that do not exist. Both are worth knowing.

### Noisiest definitions right now

```sql
SELECT
    ao.AlertConfigurations.Name AS AlertName,
    COUNT(aa.AlertActiveID) AS ActiveCount
FROM Orion.AlertActive aa
JOIN Orion.AlertObjects ao ON aa.AlertObjectID = ao.AlertObjectID
GROUP BY ao.AlertConfigurations.Name
ORDER BY COUNT(aa.AlertActiveID) DESC
```

## Enabling and disabling an alert

There is **no `Enable` or `Disable` verb**. `Enabled` is a plain `System.Boolean` property on
`Orion.AlertConfigurations`, and the entity supports `update`, so this is a CRUD write
against the definition's URI:

```bash
python3 tools/schema_query.py show Orion.AlertConfigurations
```

```text
  operations: create, delete, invoke, read, update
    read,invoke                            requires everyone
    read,update,invoke                     requires allowDisableAlert
    create,read,update,delete,invoke       requires manageAlerts
```

Note the middle row. **`allowDisableAlert` grants update but not create or delete**, which is
exactly the right the platform expects a "can silence an alert, cannot rewrite it" operator to
hold. If your service account gets a `403` on this and has `manageAlerts`, the problem is
elsewhere; if it has neither right, that is the reason.

```powershell
# 1. Scope: get the URI in the same query that identifies the alert.
$alert = Get-SwisData $swis @'
SELECT ac.AlertID, ac.Name, ac.Enabled, ac.Uri
FROM Orion.AlertConfigurations ac
WHERE ac.Name = @alertName
'@ @{ alertName = 'High CPU on core switches' }

$alert | Format-Table

# 2. Write. One property.
Set-SwisObject $swis -Uri $alert.Uri -Properties @{ Enabled = $false }

# 3. Verify.
Get-SwisData $swis 'SELECT Name, Enabled FROM Orion.AlertConfigurations WHERE AlertID = @id' `
    @{ id = $alert.AlertID }
```

Never build the URI by string formatting. Select `Uri` in the same query that identifies the
alert, for the reasons in [../swis/uris.md](../swis/uris.md).

To disable a set of definitions in one call, `BulkUpdate` takes the URIs:

```python
uris = [r["Uri"] for r in swis.query(
    "SELECT Uri FROM Orion.AlertConfigurations WHERE Category = @cat AND Enabled = @on",
    cat="Capacity", on=True)["results"]]

swis.bulk_update(uris, {"Enabled": False})
```

A bulk call returns no per-item result, so re-run the scope query afterwards and count.
See [../swis/bulk-operations.md](../swis/bulk-operations.md).

### Disabling an alert is usually the wrong lever

Disabling a definition switches it off for **every** object it covers, and it stays off until
somebody remembers to switch it back on. When the real requirement is "not for these three
servers, until Tuesday", the right tools are, in order of preference:

1. **Alert suppression** on the affected entities, which is time-bounded and reversible
   (below).
2. **A dependency**, if the reason is that a parent is down.
   See [dependencies.md](dependencies.md).
3. **Unmanaging**, only if you also want polling stopped.
   See [maintenance-mode.md](maintenance-mode.md).

### Exporting and importing a definition

`Export` gives you the definition as XML, which is the supported route for backup, moving an
alert between servers, or editing it programmatically:

```bash
python3 tools/schema_query.py verb Orion.AlertConfigurations Export
```

```text
Orion.AlertConfigurations.Export
  returns: string
  requires: admin
  requires: manageAlerts
  parameters (3):
    alertId: number (required)
    stripSensitiveData: boolean (optional)
    protectionPassword: string (optional)
```

```bash
python3 tools/schema_query.py verb Orion.AlertConfigurations Import
```

```text
Orion.AlertConfigurations.Import
  This verb imports alert into system from alert xml
  returns: SolarWinds.Orion.Core.Common.Alerting.AlertImportResult
  return shape (5 member(s)):
    AlertId                                      number
    Name                                         string
    MigrationMessage                             string
    IncorrectPasswordForDecryptSensitiveData     boolean
    AlertDefinitionIsNotSupported                boolean
  REST:    POST /Invoke/Orion.AlertConfigurations/Import
  requires: admin
  requires: manageAlerts
  parameters (3):
    alertXml: string (required)
    stripSensitiveInformation: boolean (optional)
    protectionPassword: string (optional)
```

SolarWinds' page documents the one-argument forms, `Export(alertId)` and `Import(alertXml)`.
In 2026.2 both take two further optional parameters covering sensitive data (an action that
carries a password, for instance) and a protection password, so the older one-argument calls
still work unchanged.

The round trip through a file has two PowerShell traps, both of which SolarWinds calls out:

```powershell
# Invoke-SwisVerb returns XML. .InnerText is the string you want.
$exported = Invoke-SwisVerb $swis 'Orion.AlertConfigurations' 'Export' @(42)
Set-Content 'HighCpu.xml' $exported.InnerText

# Get-Content splits into lines by default. -Raw gives you one string.
$alertXml = Get-Content 'HighCpu.xml' -Raw
$result = Invoke-SwisVerb $swis 'Orion.AlertConfigurations' 'Import' @($alertXml)
```

`Import` returns an `AlertImportResult`. SolarWinds' page describes three members; the 2026.2
contract declares five:

| Member | Type | Read it when |
|:---|:---|:---|
| `AlertId` | number | Always — it is the id of what you just created |
| `Name` | string | Always |
| `MigrationMessage` | string | Always. An import that lands on a server missing a referenced custom property or credential succeeds partially and says so here |
| `IncorrectPasswordForDecryptSensitiveData` | boolean | The export carried sensitive data and your `protectionPassword` did not match |
| `AlertDefinitionIsNotSupported` | boolean | The XML is an alert this server will not accept |

The last two are the ones that turn a silent partial import into a diagnosable one, and they
are the reason to read the whole result rather than just `AlertId`.

## What fired in a window: alert history

`Orion.AlertHistory` is the only entity that survives a reset, so every "what happened
overnight" question goes here.

```sql
SELECT TOP 500
    ah.TimeStamp,
    ah.EventType,
    ah.Message,
    ah.AccountID,
    ah.AlertObjectID,
    ah.ActionID,
    ah.AlertObjects.AlertConfigurations.Name AS AlertName,
    ah.AlertObjects.EntityType AS EntityType,
    ah.AlertObjects.EntityCaption AS TriggeringObject,
    ah.AlertObjects.RelatedNodeCaption AS NodeCaption
FROM Orion.AlertHistory ah
WHERE ah.TimeStamp >= ToUtc(AddDay(-1, GetDate()))
ORDER BY ah.TimeStamp DESC
```

`EventType` here is an alert-history event type and has nothing to do with
`Orion.Events.EventType`. The schema carries no lookup for it;
[SolarWinds' alerts page](https://solarwinds.github.io/OrionSDK/docs/alerts/) does:

| `EventType` | Meaning |
|---:|:---|
| 0 | Triggered |
| 1 | Reset |
| 2 | Acknowledged |
| 3 | Note appended |
| 4 | Added to incident (not currently used) |
| 5 | Action failed |
| 6 | Action succeeded |
| 7 | Unacknowledged |
| 8 | Cleared |

That makes the useful filters obvious:

```sql
-- Everything that triggered in the window, most frequent definition first.
SELECT
    ah.AlertObjects.AlertConfigurations.Name AS AlertName,
    COUNT(ah.AlertHistoryID) AS Triggers,
    MIN(ah.TimeStamp) AS FirstFired,
    MAX(ah.TimeStamp) AS LastFired
FROM Orion.AlertHistory ah
WHERE ah.EventType = 0
  AND ah.TimeStamp >= ToUtc(AddDay(-1, GetDate()))
GROUP BY ah.AlertObjects.AlertConfigurations.Name
ORDER BY COUNT(ah.AlertHistoryID) DESC
```

```sql
-- Alert actions that failed. This is why the email nobody received was never sent.
SELECT
    ah.TimeStamp,
    ah.Message,
    ah.ActionID,
    ah.AlertObjects.AlertConfigurations.Name AS AlertName,
    ah.AlertObjects.EntityCaption AS TriggeringObject
FROM Orion.AlertHistory ah
WHERE ah.EventType = 5
  AND ah.TimeStamp >= ToUtc(AddDay(-7, GetDate()))
ORDER BY ah.TimeStamp DESC
```

```sql
-- Who acknowledged what. AccountID is blank for actions the system took.
SELECT
    ah.TimeStamp,
    ah.AccountID,
    ah.Message,
    ah.AlertObjects.AlertConfigurations.Name AS AlertName,
    ah.AlertObjects.EntityCaption AS TriggeringObject
FROM Orion.AlertHistory ah
WHERE ah.EventType IN (2, 3, 7)
  AND ah.TimeStamp >= ToUtc(AddDay(-7, GetDate()))
ORDER BY ah.TimeStamp DESC
```

```sql
-- The full life of one alert instance, trigger through reset.
SELECT
    ah.TimeStamp,
    ah.EventType,
    ah.Message,
    ah.AccountID
FROM Orion.AlertHistory ah
WHERE ah.AlertObjectID = @alertObjectId
ORDER BY ah.TimeStamp
```

### The timezone caveat on `TimeStamp`

`Orion.AlertHistory.TimeStamp` and `Orion.AlertActive.TriggeredDateTime` carry **no
documented timezone** in the schema, and neither name ends in `Utc`. This repository does not
guess. Measure it once on your own server, on a row you know the age of:

```sql
SELECT TOP 5
    ah.AlertHistoryID,
    ah.TimeStamp,
    MinuteDiff(ah.TimeStamp, GetDate())    AS MinutesBehindLocalNow,
    MinuteDiff(ah.TimeStamp, GetUtcDate()) AS MinutesBehindUtcNow
FROM Orion.AlertHistory ah
ORDER BY ah.AlertHistoryID DESC
```

Whichever of the last two columns is near zero for a row you know just happened identifies
the clock. If it is UTC, keep the `ToUtc(AddDay(-1, GetDate()))` form used above. If it is
the SQL Server's local time, drop the `ToUtc` and compare against `AddDay(-1, GetDate())`
directly. Wrapping `GetUtcDate()` in `AddDay` is wrong in either case, for reasons worked
through in [../swql/date-and-time.md](../swql/date-and-time.md).

Do not confuse this `TimeStamp` with `Orion.Events.TimeStamp`, which is a `System.Byte[]`
row-version column and not a date at all.

## Suppressing alerts

Suppression mutes alerting for an entity over a time window while polling continues. That
distinction is the whole reason to prefer it over unmanaging: the charts keep their data.
SolarWinds states it directly: unmanaging "sets the entities status to Unmanaged and pauses
statistics collection", whereas "muting alerts merely causes alerts to not trigger".

```bash
python3 tools/schema_query.py show Orion.AlertSuppression
```

| Property | Type | Meaning |
|:---|:---|:---|
| `ID` | `System.Int32` | Row id |
| `EntityUri` | `System.String` | The entity being muted. **Children are muted too.** |
| `SuppressFrom` | `System.DateTime` | Window start |
| `SuppressUntil` | `System.DateTime` | Window end. `NULL` means until explicitly resumed. |

| Verb | Parameters | Right |
|:---|:---|:---|
| `SuppressAlerts` | `(entityUris, suppressFrom?, suppressUntil?, allowOverlapping?, reason?)` | `allowUnmanage` |
| `ResumeAlerts` | `(entityUris)` | `allowUnmanage` |
| `GetAlertSuppressionState` | `(entityUris)` | `everyone` |

Four things to notice before writing any of this:

- **The right is `allowUnmanage`, not `manageAlerts`.** Suppression is grouped with
  maintenance operations, not with alert authoring. A `403` here is a rights problem in the
  maintenance family.
- **These verbs take entity URIs, not NetObject ids.** The opposite of `Unmanage`. Getting
  this backwards is the most common failure.
- **Only `entityUris` is required.** SolarWinds' published signature is the three-argument
  `SuppressAlerts(entityUris, suppressFrom, suppressUntil)`; 2026.2 adds optional
  `allowOverlapping` and `reason` at positions 4 and 5, so older calls keep working.
- **Suppression is inherited by children.** Suppressing a node's URI mutes its interfaces,
  volumes and applications. That is usually what you want, and it is occasionally a surprise.

### The whole flow in PowerShell

Adapted from SolarWinds'
[`AlertSuppression.ps1`](https://github.com/solarwinds/OrionSDK/blob/master/Samples/PowerShell/AlertSuppression.ps1)
sample, with the scope query and the read-back that the sample leaves to you:

```powershell
Import-Module SwisPowerShell
$swis = Connect-Swis -Hostname orion.example.com -Trusted

# 1. What is already suppressed. Run this first; overlapping windows are rejected by
#    default and this is how you find out why.
Get-SwisData $swis @'
SELECT s.ID, s.EntityUri, s.SuppressFrom, s.SuppressUntil
FROM Orion.AlertSuppression s
ORDER BY s.SuppressFrom DESC
'@ | Format-Table

# 2. Scope. Select Uri in the same query that defines the set.
$targets = Get-SwisData $swis @'
SELECT n.NodeID, n.Caption, n.IPAddress, n.Uri
FROM Orion.Nodes n
WHERE n.Vendor = @vendor AND n.Location = @location
ORDER BY n.Caption
'@ @{ vendor = 'Cisco'; location = 'DC2 Row 4' }

$targets | Format-Table
"$($targets.Count) entity/entities in scope."

# Cast to a real string array. Get-SwisData returns PSObject-wrapped values.
$entityUris = @( $targets.Uri | ForEach-Object { [string] $_ } )

# 3. Check the current state, including suppression inherited from a parent.
$state = Invoke-SwisVerb $swis 'Orion.AlertSuppression' 'GetAlertSuppressionState' `
    @( , [string[]] $entityUris )
$state.EntityAlertSuppressionState

# 4. Suppress for a bounded window. Times are UTC; convert explicitly.
$fromUtc = [DateTime]::UtcNow
$untilUtc = $fromUtc.AddHours(4)

Invoke-SwisVerb $swis 'Orion.AlertSuppression' 'SuppressAlerts' `
    @( [string[]] $entityUris, $fromUtc, $untilUtc, $false, 'CHG0041288 firmware upgrade' ) |
    Out-Null

# 5. Verify with a query, not with the return value: SuppressAlerts returns System.Void.
Get-SwisData $swis @'
SELECT s.ID, s.EntityUri, s.SuppressFrom, s.SuppressUntil
FROM Orion.AlertSuppression s
WHERE s.EntityUri IN @uris
'@ @{ uris = $entityUris } | Format-Table

# 6. End it early if the work finishes ahead of the window.
Invoke-SwisVerb $swis 'Orion.AlertSuppression' 'ResumeAlerts' @( , [string[]] $entityUris ) |
    Out-Null
```

The `@( , [string[]] $uris )` idiom in steps 3 and 6 is not decoration. SolarWinds documents
the reason: when a verb's only argument is itself an array, PowerShell flattens
`@($uris)` into an argument list of N strings rather than a list containing one array. The
leading comma forces a one-element outer array, and the `[string[]]` cast turns
`PSObject`-wrapped values into real strings. Both are needed.

`SuppressAlerts` returns `System.Void`, so there is nothing in the response to check. Step 5
is the check.

### Reading suppression state properly

`GetAlertSuppressionState` exists because querying `Orion.AlertSuppression` directly does not
tell you the whole truth: it shows rows created **for** an entity, not suppression the entity
**inherits** from a parent, and not suppression scheduled to start later.

`schema_query.py` prints the return type as a bare `array`, which is why it is easy to
assume the element is undocumented. It is not. The 2026.2 Swagger contract types the response
as an array of `SolarWinds.Orion.Core.Common.Models.Alerts.EntityAlertSuppressionState`, and
declares **seven** members on it, two more than SolarWinds' prose describes:

| Member | Type |
|:---|:---|
| `EntityUri` | string |
| `SuppressedParentUri` | string — populated only when the suppression is inherited |
| `SuppressionMode` | `EntityAlertSuppressionMode` |
| `SuppressedFrom` | date-time |
| `SuppressedUntil` | date-time |
| `Reason` | string — the `reason` passed to `SuppressAlerts` |
| `ScheduleName` | string |

`SuppressionMode` is a **string** enum in the contract, not an integer, so compare against
the names rather than against ordinals:

| Value | Meaning |
|:---|:---|
| `NotSuppressed` | Alerts trigger normally |
| `SuppressedByItself` | A suppression row exists for this entity and is in effect now |
| `SuppressedByParent` | Inherited; `SuppressedParentUri` names the parent |
| `SuppressionScheduledForItself` | A row exists but its window has not started |
| `SuppressionScheduledForParent` | Inherited, and not started |

What is still worth confirming once is presentation rather than naming: how `Invoke-SwisVerb`
nests the repeated element in the XML it hands back. Call the verb on an entity you have
just suppressed and inspect the response.

### Suppression, dependencies and unmanaging

| Goal | Tool | Polling | Reversal |
|:---|:---|:---|:---|
| Silence alerts for a planned change, keep the data | `Orion.AlertSuppression.SuppressAlerts` | Continues | `ResumeAlerts`, or the window expires |
| Stop polling entirely for a change window | `Orion.Nodes.Unmanage` | Stops, leaving a chart gap | `Remanage`, or the window expires |
| Stop children alerting because a parent is down | `Orion.Dependencies` | Continues | Automatic when the parent recovers |

See [maintenance-mode.md](maintenance-mode.md) and [dependencies.md](dependencies.md).

## Alert actions

An action is the thing that happens when an alert fires. `Orion.Actions` holds the action
instances and `Orion.ActionsAssignments` attaches them to something.

```sql
SELECT
    a.ActionID,
    a.ActionTypeID,
    a.Title,
    a.Description,
    a.Enabled,
    a.Approved,
    a.SortOrder,
    asg.ActionAssignmentID,
    asg.ParentID,
    asg.EnvironmentType,
    asg.CategoryType
FROM Orion.Actions a
JOIN Orion.ActionsAssignments asg ON a.ActionID = asg.ActionID
ORDER BY a.Title
```

`ActionTypeID` is a **string** naming the action plugin, not an integer. The set of values is
installation data (it depends on which modules and integrations are installed), so read them
off your own server rather than assuming:

```sql
SELECT a.ActionTypeID, COUNT(a.ActionID) AS Instances
FROM Orion.Actions a
GROUP BY a.ActionTypeID
ORDER BY COUNT(a.ActionID) DESC
```

Each action's configuration is a key/value bag rather than typed columns, hosted on the
action:

```sql
SELECT
    a.ActionID,
    a.Title,
    a.Properties.PropertyName AS PropertyName,
    a.Properties.PropertyValue AS PropertyValue
FROM Orion.Actions a
WHERE a.ActionID = @actionId
```

Be careful what you print. Action property bags are where an SMTP password or a webhook token
ends up, so a report that dumps every `PropertyValue` is an exfiltration route. Select the
`PropertyName` list first and pick.

On `Orion.ActionsAssignments`, `EnvironmentType` and `CategoryType` distinguish an alert
action from a report action (both kinds live in `Orion.Actions`; note that the entity's access
control lists `manageReports` alongside `manageAlerts`). `ParentID` is the id of the thing the
action is attached to. **The schema declares no navigation property from
`Orion.ActionsAssignments` to `Orion.AlertConfigurations`**, and it does not state that
`ParentID` holds an `AlertID`. Confirm the correlation on your own server before relying on
it, by comparing values you already know:

```sql
SELECT asg.ParentID, asg.EnvironmentType, asg.CategoryType, a.Title
FROM Orion.ActionsAssignments asg
JOIN Orion.Actions a ON asg.ActionID = a.ActionID
WHERE asg.ParentID = @alertId
```

The reliable route from an alert to the actions that ran for it is
`Orion.AlertHistory.ActionID`. Be clear about what that is: a plain `System.Int32` column,
not a navigation property. `Orion.AlertHistory` declares exactly one relationship,
`AlertObjects`, so there is no dotted path from a history row to `Orion.Actions` and you join
on the id explicitly if you want the action's title. What makes it reliable is that the
platform writes the id onto the history row itself, so the correlation is recorded rather
than inferred:

```sql
SELECT
    ah.TimeStamp,
    ah.EventType,
    ah.Message,
    ah.ActionID,
    a.Title AS ActionTitle,
    a.ActionTypeID,
    ah.AlertObjects.AlertConfigurations.Name AS AlertName
FROM Orion.AlertHistory ah
LEFT JOIN Orion.Actions a ON ah.ActionID = a.ActionID
WHERE ah.EventType IN (5, 6)
  AND ah.TimeStamp >= ToUtc(AddDay(-1, GetDate()))
ORDER BY ah.TimeStamp DESC
```

The `LEFT JOIN` is deliberate: an action that has since been deleted leaves its id on the
history row with nothing to join to, and an inner join would silently drop exactly the rows
an incident review wants.

`Orion.Actions` also carries `TestAlertingAction` and `TestReportingAction`, which fire an
action once without waiting for an alert to trigger it. Both take two typed arguments in
2026.2, and they do **not** require the same right:

```bash
python3 tools/schema_query.py verb Orion.Actions TestAlertingAction
```

```text
Orion.Actions.TestAlertingAction
  returns: SolarWinds.Orion.Core.Models.Actions.ActionResult
  REST:    POST /Invoke/Orion.Actions/TestAlertingAction
  requires: manageAlerts
  parameters (2):
    action: SolarWinds.Orion.Core.Models.Actions.ActionDefinition (required)
    context: SolarWinds.Orion.Core.Models.Actions.Contexts.AlertingActionContext (required)
```

`TestReportingAction` has the same two-argument shape with a `ReportingActionContext` in
place of the alerting one, and **requires `admin` rather than `manageAlerts`**. That
asymmetry is worth knowing before you hand a test button to an alert operator.

What the schema does not give you is the *inside* of those two types: it names
`ActionDefinition` and the two context types but does not describe their members, so the
document you have to build is not documented here. `Metadata.VerbArgument` on a live server
carries an `XmlTemplate` column that shows what SWIS expects. See
[../swis/metadata-introspection.md](../swis/metadata-introspection.md).

## Alert schedules

`Orion.AlertSchedules` has exactly two columns and no declared relationships:

```bash
python3 tools/schema_query.py show Orion.AlertSchedules
```

```text
Orion.AlertSchedules   [2026.2]
  inherits: System.Entity -> Orion.AlertSchedules
  operations: create, delete, invoke, read, update
    read                                   requires everyone
    create,read,update,delete,invoke       requires admin
    create,read,update,delete,invoke       requires manageAlerts
    create,read,update,delete,invoke       requires manageReports

  properties (2)
    FrequencyID                                System.Int32                
    AlertConfigurationID                       System.Int32                
```

It is a cross-reference between an alert and an `Orion.Frequencies` row, which is the same
schedule entity reports and maintenance plans use:

```sql
SELECT
    f.FrequencyID,
    f.DisplayName,
    f.Description,
    f.CronExpression,
    f.CronExpressionTimeZoneInfo,
    f.EnabledDuringTimePeriod,
    f.StartTime,
    f.EndTime,
    f.TimeZoneDisplayName,
    f.UtcOffsetInMinutes
FROM Orion.Frequencies f
ORDER BY f.DisplayName
```

Because no navigation property is declared, joining is a plain equality on the id columns.
That `AlertConfigurationID` corresponds to `Orion.AlertConfigurations.AlertID` is the only
sensible reading of the column name, but **the schema does not state it**, so treat this join
as unverified and check it against an alert whose schedule you set yourself:

```sql
SELECT
    ac.Name AS AlertName,
    f.DisplayName AS ScheduleName,
    f.CronExpression,
    f.EnabledDuringTimePeriod
FROM Orion.AlertSchedules sch
JOIN Orion.AlertConfigurations ac ON sch.AlertConfigurationID = ac.AlertID
JOIN Orion.Frequencies f ON sch.FrequencyID = f.FrequencyID
ORDER BY ac.Name
```

`EnabledDuringTimePeriod` is the flag that decides whether the frequency means "only during"
or "except during", which is the difference between an alert that pages at 3am and one that
does not. See [scheduling.md](scheduling.md).

## Things that go wrong

- **Querying `Orion.AlertActive` on its own and finding no alert name.** There is no name on
  the active row. Join `Orion.AlertObjects` and then `Orion.AlertConfigurations`.
- **Passing `AlertActiveID` to `Acknowledge`.** The parameter is `alertObjectIds`. Pass
  `AlertObjectID`, and verify with a read-back, because the verb returns one boolean for the
  whole call.
- **Mixing the two generations.** `Orion.AlertDefinitions` and `Orion.AlertStatus` key on a
  GUID `AlertDefID`; `Orion.AlertConfigurations` keys on an integer `AlertID`. They do not
  join.
- **`Orion.ActiveAlerts` mistaken for `Orion.AlertActive`.** The names differ by word order.
  `Orion.ActiveAlerts` has a legacy shape (`AlertID`, `ObjectType` as a `System.Char`,
  `ObjectID`, `TriggerValue`) and is not the entity the current model populates.
- **Expecting `AcknowledgedNote` to hold the note.** SolarWinds says it is not currently
  used. Read notes from `Orion.AlertHistory.Message`.
- **`ClearAlert` used to fix a stuck alert.** It does not run reset actions and does not
  check the trigger condition, so the alert returns at the next evaluation if the condition
  still holds.
- **NetObject id passed to `SuppressAlerts`.** It takes URIs. `Unmanage` takes NetObject ids.
  They are not interchangeable.
- **A `403` on suppression read as an alerting rights problem.** The two
  `Orion.AlertSuppression` write verbs, `SuppressAlerts` and `ResumeAlerts`, require
  `allowUnmanage`. Only the read verb, `GetAlertSuppressionState`, is `everyone`.
- **`PowerShell` flattening a single array argument.** `Unacknowledge`, `ClearAlert` and
  `ResumeAlerts` each take exactly one argument which is an array. Use
  `@( , [string[]] $uris )`.
- **Reading `Invoke-SwisVerb`'s return value directly.** It is an XML element. Use
  `.InnerText`.
- **Time-window filters on `TimeStamp` and `TriggeredDateTime` written without measuring.**
  Neither column documents its timezone.
- **Disabling a definition when suppression was meant.** It affects every object the
  definition covers, and nothing turns it back on.

## What is not verified here

| Claim | Status | How to check on your server |
|---|---|---|
| `Orion.AlertDefinitions` and `Orion.AlertStatus` are the pre-2015 "advanced alerts" model | Inferred from the `Migrate*AdvancedAlert*` verb names and the GUID-keyed column shapes; the schema does not say so | Compare row counts and `AlertDefID` values against `Orion.AlertConfigurations.AlertID`; a populated `Orion.AlertDefinitions` on a modern server means something migrated it |
| `Orion.AlertSchedules.AlertConfigurationID` refers to `Orion.AlertConfigurations.AlertID` | Inferred from the column name; no navigation property is declared | Set a schedule on one alert in the UI, then `SELECT * FROM Orion.AlertSchedules` and compare with that alert's `AlertID` |
| `Orion.ActionsAssignments.ParentID` refers to an alert id | Not declared; `EnvironmentType` and `CategoryType` imply the entity is shared with reporting | Attach an action to a known alert, then filter `Orion.ActionsAssignments` on that `ActionID` and read `ParentID` |
| The unit of `Orion.AlertConfigurations.Frequency` | `System.Int64` with no unit in the schema | Set a known evaluation interval on a test alert and read the value back |
| How `Invoke-SwisVerb` nests the `GetAlertSuppressionState` response in XML | The member names and the `SuppressionMode` values are in the 2026.2 contract; the XML element nesting a PowerShell caller sees is not | Suppress one entity, call the verb, and inspect the response |
| Argument shapes for `MigrateAdvancedAlert`, `MigrateAllAdvancedAlerts`, `MigrateAdvancedAlertFromXML` | All three are declared with no typed parameters at all in 2026.2 | `SELECT Position, Name, Type, IsOptional, XmlTemplate FROM Metadata.VerbArgument WHERE EntityName = 'Orion.AlertConfigurations'` |
| The members of `ActionDefinition`, `AlertingActionContext` and `ReportingActionContext`, the two arguments to `TestAlertingAction` and `TestReportingAction` | The contract names the parameters and their types but does not describe the types | `SELECT Position, Name, Type, IsOptional, XmlTemplate FROM Metadata.VerbArgument WHERE EntityName = 'Orion.Actions'` |
| Whether `Orion.AlertHistory.TimeStamp` and `Orion.AlertActive.TriggeredDateTime` are UTC | Undocumented in the schema, and neither name ends in `Utc` | The `MinuteDiff` measurement query above |
| The `Severity` and alert-history `EventType` value tables | Taken from SolarWinds' published alerts page, not from the extracted schema. The `SuppressionMode` values are not in this category: they come from the 2026.2 contract | [Alert Entities](https://solarwinds.github.io/OrionSDK/docs/alerts/) |

## Related pages

- [README.md](README.md) for the query-first method these recipes follow
- [maintenance-mode.md](maintenance-mode.md) for unmanaging, the heavier alternative to suppression
- [dependencies.md](dependencies.md) for stopping downstream alerts during an outage
- [events-and-auditing.md](events-and-auditing.md) for what happened and who changed it
- [scheduling.md](scheduling.md) for `Orion.Frequencies` and cron expressions
- [../swis/invoke-verbs.md](../swis/invoke-verbs.md) for verb calling mechanics
- [../swis/crud.md](../swis/crud.md) for the `Enabled` write
- [../swis/uris.md](../swis/uris.md) for why you select `Uri` rather than build it
- [../swql/date-and-time.md](../swql/date-and-time.md) for the UTC handling in the history queries
- [../reference/netobject-types.md](../reference/netobject-types.md) for `EntityNetObjectId` prefixes
- [../../scripts/swql/05-alerts.swql](../../scripts/swql/05-alerts.swql), runnable versions of these queries

# WPM: Web Performance Monitor

## Nothing in the schema is called WPM

Start here, because this is where most people lose twenty minutes.

Web Performance Monitor's entities all live under **`Orion.SEUM.`**, for *synthetic end user
monitoring*. There is no `Orion.WPM.` namespace, no entity with `WPM` in its name, and no
property with `WPM` in its name. Searching the schema for the product name returns nothing at
all:

```bash
python3 tools/schema_query.py find WPM          # nothing
python3 tools/schema_query.py find SEUM         # 31 entities
```

The naming mismatch does not stop at the namespace. Inside `Orion.SEUM.` the vocabulary also
diverges from what the console shows you:

| The console calls it | The schema calls it |
|---|---|
| Location | `Orion.SEUM.Agents` |
| Transaction | `Orion.SEUM.Transactions` |
| Step | `Orion.SEUM.TransactionSteps` |
| Recording | `Orion.SEUM.Recordings` |

"Location" to "agent" is the one that costs real time, because the platform already has a
completely different thing called an agent, `Orion.AgentManagement.Agent`, which is the
deployed polling agent used by [SAM](sam.md) and others. **`Orion.SEUM.Agents` is not
that.** No relationship edge joins the two directly; the only route the schema offers is the
two-hop detour `Orion.SEUM.Agents.Engine.Agents`, which establishes nothing more than that
both are served by the same polling engine. What makes the confusion worse is that the two
look alike on paper: both key on a column called `AgentId`, and both carry `AgentGuid`,
`Hostname`, `DNSName`, `IP` and `OSVersion`. An id from one does not resolve in the other,
and a WPM playback location is a machine running the WPM player, not a machine running the
Orion agent. When a document says "the location is offline" and the schema says
`Orion.SEUM.Agents.ConnectionStatus`, those are the same sentence.

[../platform/modules.md](../platform/modules.md) explains why prefixes and product names
diverge across this platform generally. WPM is the most extreme case of it.

## What the module actually does

WPM records a browser session as a script, then replays that script on a schedule from one or
more machines and times every action. It is synthetic monitoring: nothing here comes from
real users. That is the point, because it means you get a result every few minutes from a
known location whether or not anybody happened to visit the site, and the result is
comparable over time in a way that real user timings are not.

The measurement is nested three levels deep, and every level exists as its own entity with
its own timings and thresholds:

```
Transaction        one recording played back from one location
  Step             one recorded action inside it: click, type, navigate
    Request        one HTTP request the browser made while performing that step
```

A transaction is slow because a step is slow; a step is slow because a request in it is
slow. Being able to walk down those three levels in one query is the reason to use the API
rather than the console for anything analytical.

## Namespace and how many entities

WPM contributes **31 entities**, all under `Orion.SEUM.`. That makes it one of the smallest
modules in the schema, and unusually for a small module almost all of it is useful: there are
very few dead-end views here.

| Group | Count | Entities |
|---|---|---|
| The core model | 5 | `Recordings`, `RecordingSteps`, `Transactions`, `TransactionSteps`, `TransactionStepRequests` |
| Recording attachments | 3 | `RecordingAuthentications`, `RecordingCertificates`, `RecordingCustomProperties` |
| Transaction attachments | 2 | `TransactionCustomProperties`, `TransactionRunParameters` |
| Locations | 5 | `Agents`, `AgentStatus`, `AgentStatusReport`, `AgentConnectionStatus`, `AgentWebUri` |
| Timings | 6 | `ResponseTime`, `ResponseTimeDetail`, `ResponseTimeReport`, `StepResponseTime`, `StepResponseTimeDetail`, `StepResponseTimeReport` |
| Screenshots and HTML | 3 | `StepResponseTimeLargeData`, `StepResponseTimeDetailLargeData`, `TransactionStepLargeData` |
| Console links | 2 | `TransactionWebUri`, `TransactionStepWebUri` |
| Settings and other | 5 | `Settings`, `WebSettings`, `Websites`, `WebUserPermissions`, `RecordingsSettings` |

Confirm the module is installed before relying on any of it, because a query against an
absent entity fails outright rather than returning an empty result:

```sql
SELECT FullName, BaseType, CanCreate, CanUpdate, CanDelete, CanInvoke, IsObsolete
FROM Metadata.Entity
WHERE FullName LIKE 'Orion.SEUM.%'
ORDER BY FullName
```

### NetObject prefixes

Four WPM entities carry a NetObject prefix, and the display names in
[`data/reference/netobject-types.json`](../../data/reference/netobject-types.json) are the
console's vocabulary rather than the schema's:

| Entity | Console name | Prefix | Key |
|---|---|---|---|
| `Orion.SEUM.Transactions` | Transaction | `T` | `TransactionId` |
| `Orion.SEUM.TransactionSteps` | Step | `TS` | `TransactionStepId` |
| `Orion.SEUM.TransactionStepRequests` | Step Request | `TSR` | `TransactionStepRequestId` |
| `Orion.SEUM.Agents` | **Location** | `L` | `AgentId` |

That fourth row is the naming point made concrete: the reference data itself calls
`Orion.SEUM.Agents` a Location. Transaction 17 is the NetObject string `T:17`, which is what
`Orion.SEUM.Transactions.Unmanage` expects, not the bare integer. See
[../reference/netobject-types.md](../reference/netobject-types.md).

## The recording, and the transactions made from it

A **recording** is the script. `Orion.SEUM.Recordings` is deliberately small:
`RecordingId`, `Name`, `Guid`, `CreationDateUtc`, `LastUpdateUtc`, `Version`, `Width` and
`Height`. The last three are more interesting than they look. `Width` and `Height` are the
browser resolution the session was recorded at, which is what a responsive site's layout
depends on and therefore what determines whether a playback finds the button it is looking
for. `Version` is described in the schema as "Version of a recording. Determines if recording
is supported", which is the field that goes stale after a WPM upgrade.

A recording's actions are `Orion.SEUM.RecordingSteps`, keyed by `RecordingId` and `StepId`:
`Name`, `Url`, `StepOrder`, `Guid`, `Description`, `PlaybackCommands`, `WarningThreshold` and
`CriticalThreshold`. `PlaybackCommands` is the actual script content for that step, and
`StepOrder` is the only column that puts the steps in the order a human recorded them.

Two things attach to a recording rather than to a transaction, and both are hosted, so
deleting the recording takes them with it:

- `Orion.SEUM.RecordingAuthentications`: `CredentialsId`, `RecordingId`, `Host`, `UserName`,
  `Password`. Credentials the recorded site asked for, stored per host.
- `Orion.SEUM.RecordingCertificates`: `CertificateId`, `RecordingId`, `CommonName`, `Url`.
  Client certificates the recorded session presented.

A **transaction** is that recording assigned to a location. `Orion.SEUM.Transactions`
inherits `System.ManagedEntity` and declares 17 properties, of which the structurally
important three are `RecordingId`, `AgentId` and `TransactionId`. Everything else is
configuration (`Name`, `Frequency`, `WarningThreshold`, `CriticalThreshold`, `IsEnabled`) or
last-run state (`LastDuration`, `LastDateTimeUtc`, `LastPlayedUtc`, `LastErrorMessage`,
`LastModificationUtc`, `JobId`).

The relationship between the two is the thing to internalise:

```
Orion.SEUM.Recordings  --(one to many, System.Reference)-->  Orion.SEUM.Transactions
```

One recording, many transactions. That is the whole model for multi-location monitoring: you
record the checkout journey once and create a transaction per city, and every transaction
runs the identical script so the numbers are comparable. `Orion.SEUM.Recordings.Transactions`
navigates down, `Orion.SEUM.Transactions.Recording` navigates back, and the edge is
`System.Reference` rather than `System.Hosting`, meaning the recording has an independent
lifetime and can exist with no transaction using it yet.

The transaction's relationship to its **location** is the opposite kind:
`Orion.SEUM.Transactions.Agent` is `System.Hosting` and
`Orion.SEUM.Agents.Transactions` is the reverse. A transaction genuinely belongs to the
location that plays it, and deleting the location takes its transactions with it.

`Orion.SEUM.TransactionRunParameters` (`TransactionId`, `Type`, `Key`, `Value`) is a
name/value bag per transaction, which is how one recording is reused with different inputs
per location.

## Steps: two entities for one idea

This is the part of the model that surprises people. A step exists twice.

`Orion.SEUM.RecordingSteps` is the step **as recorded**: name, URL, order, playback commands.
It belongs to the recording and is shared by every transaction made from that recording.

`Orion.SEUM.TransactionSteps` is the step **as played back by one transaction**. It inherits
`System.ManagedEntity`, has its own `Status`, its own `WarningThreshold`,
`CriticalThreshold` and `OptimalThreshold`, its own `LastDuration`, `LastErrorMessage`,
`LastDateTimeUtc` and `LastPlayedUtc`, and its own `ScreenshotId` and
`ScreenshotDateTimeUtc`.

They are joined by `Orion.SEUM.TransactionSteps.Step`, a `System.Reference` navigation to
`Orion.SEUM.RecordingSteps`. So the readable name and the URL of a step live on the recording
side, and the timings live on the transaction side, and any useful step report follows that
navigation:

```sql
SELECT TOP 20
    ts.Transaction.Name AS TransactionName,
    ts.Step.StepOrder AS StepOrder,
    ts.Step.Name AS StepName,
    ts.Step.Url AS StepUrl,
    ts.LastDuration
FROM Orion.SEUM.TransactionSteps ts
ORDER BY ts.Transaction.Name, ts.Step.StepOrder
```

`ts.Step.Name` reads oddly and is correct: the navigation property is `Step` and the target
entity's caption column is `Name`.

Note also that `Orion.SEUM.TransactionSteps` carries `RecordingId` **and** `StepId`
alongside `TransactionStepId` and `TransactionId`, so you can join to `RecordingSteps` on the
composite key by hand if you prefer not to navigate.

### The `Rely` edges

`Orion.SEUM.Transactions` reaches `Orion.SEUM.TransactionSteps` two ways, and this is a real
trap:

| Navigation | Kind | Meaning |
|---|---|---|
| `Orion.SEUM.Transactions.Steps` | `System.Hosting` | The steps this transaction owns |
| `Orion.SEUM.Transactions.RelySteps` | `System.Reliance` | The steps this transaction's health depends on |

The reverse pair is `Orion.SEUM.TransactionSteps.Transaction` (hosting) and
`Orion.SEUM.TransactionSteps.RelyTransactions` (reliance). Reliance edges exist where one
entity's health depends on another's across a management boundary, and they are not
guaranteed to resolve to the same rows as the hosting edge that sits beside them. Use `Steps`
unless you specifically want the dependency view.
[../schema/relationships.md](../schema/relationships.md) covers the three relationship kinds
and why the `Rely` prefix is a naming convention worth recognising.

## Requests: what the browser actually did

`Orion.SEUM.TransactionStepRequests` is one row per HTTP request issued while performing a
step, and it is the richest entity in the module. Alongside `Url`, `MimeType`, `StatusCode`,
`Size` and `RequestIndex` it carries the full timing breakdown twice: once as offsets from
the start of the step, once as durations.

**Offsets**, in milliseconds from the step's start: `RequestBeginMs`, `DNSBeginMs`,
`ConnectionBeginMs`, `SendBeginMs`, `SendEndMs`, `ReceiveBeginMs`, `ReceiveEndMs`.

**Durations**, in milliseconds: `BlockedDurationMs`, `DNSResolutionDurationMs`,
`ConnectionDurationMs`, `SendDurationMs`, `TimeToFirstByteDurationMs`,
`DownloadDurationMs`, `TotalDurationMs`.

The offsets are what you draw a waterfall chart from, because they place each request on a
common timeline. The durations are what you sort and aggregate on. Having both is why a
question like "is this step slow because of DNS or because of the server" is answerable
directly rather than by inference: `DNSResolutionDurationMs` and
`TimeToFirstByteDurationMs` are separate columns.

`StepFullName` is a denormalised readable name on the request row itself, useful when you do
not want to navigate. The one navigation is
`Orion.SEUM.TransactionStepRequests.TransactionStep`, a `System.Reference` back up to the
step.

Note that `Orion.SEUM.TransactionStepRequests` declares **no access control at all** in the
schema, unlike its parent `Orion.SEUM.TransactionSteps`, which requires `admin` for
everything except read.

## How timings roll up

Three levels of measurement, three retention tiers, and a naming convention that repeats
exactly. Once you see the pattern, the six timing entities stop being confusing.

|  | Per transaction | Per step |
|---|---|---|
| Raw samples | `Orion.SEUM.ResponseTimeDetail` | `Orion.SEUM.StepResponseTimeDetail` |
| Rolled up | `Orion.SEUM.ResponseTime` | `Orion.SEUM.StepResponseTime` |
| Reporting rollup | `Orion.SEUM.ResponseTimeReport` | `Orion.SEUM.StepResponseTimeReport` |

The `Detail` entities carry a single `Duration` per row, because a raw sample is one playback
and has no min or max. The other four carry `MinDuration`, `AvgDuration` and `MaxDuration`
over an interval. All six carry `Timestamp`, `PercentAvailability`, and all six inherit from
`System.StatisticsEntity`, so all six need a time bound in every query.

`Weight` is queryable on all six, and on both agent status entities, and it is what makes an
availability number correct when you aggregate across rows: `AVG(PercentAvailability)`
weights a five-minute bucket the same as an hour-long one, while
`SUM(PercentAvailability * Weight) / SUM(Weight)` does not.

Where `Weight` comes from is worth knowing, because it explains a type difference that will
otherwise look like a bug. `System.StatisticsEntity` declares `ObservationTimestamp`,
`ObservationFrequency` and `Weight` for every descendant, and its `Weight` is a
`System.Double` documented as the collection interval in seconds. Five of the eight WPM
statistics entities redeclare `Weight` themselves as a `System.Int32`:
`Orion.SEUM.ResponseTimeReport`, `Orion.SEUM.StepResponseTime`,
`Orion.SEUM.StepResponseTimeReport`, `Orion.SEUM.AgentStatus` and
`Orion.SEUM.AgentStatusReport`. The remaining three, the two `Detail` entities and
`Orion.SEUM.ResponseTime`, do not redeclare it and so expose the inherited
`System.Double`. The column resolves in a query either way; a typed client binding it to an
`int` does not.

The step timings navigate both up to their step and sideways to the transaction's timing row
for the same interval:

- `Orion.SEUM.StepResponseTime.Step` leads to `Orion.SEUM.TransactionSteps`
- `Orion.SEUM.StepResponseTime.TransactionResponseTime` leads to `Orion.SEUM.ResponseTime`
- `Orion.SEUM.ResponseTime.StepResponseTimes` leads back down

That second one is what makes "which step owned most of this transaction's duration in this
interval" a single query rather than two. `Orion.SEUM.StepResponseTime` also declares
`TransactionId` directly, so you can filter by transaction without navigating.

**Screenshots and HTML are separate entities on purpose.** `Orion.SEUM.StepResponseTime` has
a `ScreenshotId` but not the image. The bytes live in
`Orion.SEUM.StepResponseTimeLargeData` (`Screenshot`, `Thumbnail`, `RawHtml`), reached as
`Orion.SEUM.StepResponseTime.LargeData`, with matching
`Orion.SEUM.StepResponseTimeDetailLargeData` and `Orion.SEUM.TransactionStepLargeData` for
the other two levels. All three inherit from `System.ExtensionEntity`. Selecting
`Screenshot` pulls a `System.Byte[]` per row across the wire, so never put one in a report
query; fetch it for a single step you are actually looking at.

**These entities changed shape in 2026.2.** Per
[../reference/schema-changes-2026.1-to-2026.2.md](../reference/schema-changes-2026.1-to-2026.2.md),
ten `Orion.SEUM.` entities **lost `DateTimeUtc`**: all six timing entities, both agent status
entities, and `Orion.SEUM.StepResponseTimeLargeData` and
`Orion.SEUM.StepResponseTimeDetailLargeData`. Several of them also lost `Archive`,
`RecordCount`, `Screenshot`, `RawHtml`, `ErrorMessage` and `ScreenshotId`. `Timestamp` is the
column that survived, and `ObservationTimestamp` is still there as an inherited member of
`System.StatisticsEntity` on the eight statistics entities. A WPM report written against an
earlier release that selects `DateTimeUtc` fails outright after the upgrade, and that is the
single most likely thing to break here.

`Orion.SEUM.StepResponseTimeDetail` is the one to check first, because it lost
`ErrorMessage` and `ScreenshotId` as well: a step-failure report built on the detail tier
loses two of its columns, while the same report built on `Orion.SEUM.StepResponseTime`,
which kept both, does not.

## Locations, which the schema calls agents

`Orion.SEUM.Agents` has 31 properties and inherits `System.ManagedEntity`. It divides into
four groups.

**Identity and reachability.** `AgentId`, `Name`, `Hostname`, `DNSName`, `IP`, `Url`, `Port`,
`OSVersion`, `AgentVersion`, `AgentGuid`, `IsActiveAgent`, `RDPEnabled`.

**Proxy configuration.** `UseProxy`, `ProxyUrl`, `UseProxyAuthentication`, `ProxyUserName`,
`ProxyPassword`. A location that plays back through a corporate proxy measures the proxy as
well as the site, which is worth knowing when one location is consistently slower than the
rest.

**Connection state.** `ConnectionStatus`, `ConnectionStatusMessage`,
`ConnectionStatusTimeStampUtc`, plus the inherited `Status`.

**Load.** `LoadPercentage`, `AvgLoadPercentageLast30min`, `AvgLoadPercentageLast60min`,
`NumAllTransactions`, `NumManagedTransactions`. A saturated location produces timings that
describe the location rather than the site, so load is not a housekeeping metric here, it is a
data-quality metric.

`ConnectionStatus` resolves through `Orion.SEUM.AgentConnectionStatus`, a two-column lookup
of `StatusId` and `ShortDescription`, navigable as
`Orion.SEUM.Agents.ConnectionStatusInfo`. **That is a WPM lookup, not
`Orion.StatusInfo`**, and the two code sets are unrelated. The inherited `Status` is the
one that joins to `Orion.StatusInfo`.

`PollingEngineId` and the `Orion.SEUM.Agents.Engine` navigation tie a location to an
`Orion.Engines` row, and the reverse edge is `Orion.Engines.SEUMAgents`. That is also the
only declared path between `Orion.Nodes` and `Orion.SEUM.Agents`:

```bash
python3 tools/schema_query.py path Orion.Nodes Orion.SEUM.Agents
```

returns exactly one route, `Orion.Nodes.Engine.SEUMAgents`, which goes through the polling
engine rather than through anything meaningful about the machine. A WPM location is not a
monitored node, and if you want it monitored as one you add it separately.

History is `Orion.SEUM.AgentStatus` and `Orion.SEUM.AgentStatusReport`, carrying min, max
and average of `LoadPercentage`, `NumManagedTransactions` and `QueueLength`, plus
`PercentAvailability` and `Weight`. `MaxQueueLength` climbing is the early warning that a
location has more transactions than it can play at their configured frequencies.

### The credentials problem

Four WPM properties hold secrets and all four are declared readable by **`everyone`**:

- `Orion.SEUM.Agents.Password`
- `Orion.SEUM.Agents.ProxyPassword`
- `Orion.SEUM.RecordingAuthentications.Password`
- `Orion.SEUM.RecordingAuthentications.UserName`

The entity-level access control on both entities grants `read` to `everyone` and reserves
create, update and delete for `admin`. Whether the stored value is returned in the clear is
not something the schema states, and this page does not claim either way. What the schema
does establish is that the columns are selectable by any account that can query, so:

- **Never put them in a report, a dashboard query or a saved view.** There is no `SELECT *`
  in SWQL, which helps, but it only helps if you keep naming columns deliberately.
- **Never log them.** A script that dumps a whole result set for debugging will dump these
  too.
- Treat the fact as an argument for account limitations rather than against them.

The same caution applies to `Orion.SEUM.RecordingCertificates`, which does not store a key
but does tell an attacker exactly which client certificates matter and where they are used.

## Verbs

WPM publishes **16 verbs across five entities**, which is a lot for a 31-entity module and
reflects that recordings really are managed through the API. Arguments are positional; the
names below never travel on the wire. See
[../swis/invoke-verbs.md](../swis/invoke-verbs.md).

### Transactions

| Verb | Parameters, in order | Returns |
|---|---|---|
| `Create` | `recordingId`, `agentId` | `number`, the new transaction id |
| `Unmanage` | `netObjectId`, `unmanageTime`, `remanageTime`, `isRelative` | `System.Void` |
| `Remanage` | `netObjectId` | `System.Void` |

`Orion.SEUM.Transactions.Create` is the verb that does the assignment described earlier: give
it a recording and a location and it makes a transaction. It is the only WPM verb that
creates a monitored object, and the entity also declares plain CRUD create, so both routes
exist. Prefer the verb, because it takes the two ids that actually define a transaction
rather than requiring you to know which of the 17 properties are mandatory.

**`Orion.SEUM.Transactions.Unmanage` takes four parameters, not five.** Every other
`Unmanage` on the platform that takes a NetObject string also takes a fifth
`allowOverlapping` argument. This one does not. A shared wrapper written against
`Orion.Nodes.Unmanage` sends an extra argument and fails here. The
[verb catalogue](../swis/verb-catalog.md) lists all six `Unmanage` verbs side by side, and
they genuinely do not share a signature.

```powershell
$swis = Connect-Swis -Hostname orion.example.com -Credential $cred

# Create a transaction: play recording 8 from location 3.
$transactionId = Invoke-SwisVerb $swis 'Orion.SEUM.Transactions' 'Create' @(8, 3)

# Take it out of alerting for a two hour deployment window.
$from = (Get-Date).ToUniversalTime().ToString('o')
$to   = (Get-Date).ToUniversalTime().AddHours(2).ToString('o')
Invoke-SwisVerb $swis 'Orion.SEUM.Transactions' 'Unmanage' @("T:$transactionId", $from, $to, $false) | Out-Null

# And back early if the deployment finishes ahead of time.
Invoke-SwisVerb $swis 'Orion.SEUM.Transactions' 'Remanage' @("T:$transactionId") | Out-Null
```

`T:` is the NetObject prefix from the table above. Passing a bare `17` where `T:17` is
expected is the most common failure with these two verbs.

### Recordings

| Verb | Parameters, in order | Returns |
|---|---|---|
| `Exists` | `recordingGuid` | `boolean` |
| `Import` | `recordingFileContent`, `recordingName`, `password` | `number`, the new recording id |
| `Update` | `recordingId`, `recordingFileContent`, `recordingName`, `password` | `number`, the recording id |
| `Export` | `recordingId`, `password` | `SolarWinds.SEUM.Common.Models.RecordingFileContent` |

These four are what make recordings portable between installations, which is the reason to
automate WPM at all: record once in a test environment, export, import into production, and
create transactions for each location.

The `password` argument — the **cipher password** — is not a site credential. The schema
describes it as the password used to cipher the file on export and decipher it on import,
so the same value has to be supplied to both. Getting it wrong produces a failed import rather than a corrupted
recording.

Note the asymmetry in `recordingGuid` versus `recordingId`. `Exists` takes the recording's
`Guid`, a `System.Guid` column on `Orion.SEUM.Recordings`, while `Export` and `Update` take
the integer `RecordingId`. Both are on the same row, so fetch both:

```powershell
$rec = Get-SwisData $swis @"
SELECT TOP 1 r.RecordingId, r.Guid, r.Name, r.Version
FROM Orion.SEUM.Recordings r
WHERE r.Name = @name
"@ @{ name = 'Checkout journey' }

if (-not (Invoke-SwisVerb $swis 'Orion.SEUM.Recordings' 'Exists' @($rec.Guid))) {
    Write-Error "Recording $($rec.Name) is not present on this server"
}

$exported = Invoke-SwisVerb $swis 'Orion.SEUM.Recordings' 'Export' @($rec.RecordingId, $filePassword)
```

`Invoke-SwisVerb` returns an `XmlElement` rather than a typed object, so read the fields off
the response rather than assuming a shape. The declared return type is
`SolarWinds.SEUM.Common.Models.RecordingFileContent`, and the contract does enumerate it: two
`string` members, `Content` and `Name`. What encoding `Content` uses is not stated, so inspect
one before building on it:

```bash
python3 tools/schema_query.py verb Orion.SEUM.Recordings Export
```

which prints the return shape alongside the parameters.

**`Import` and `Update` take the `Content` string, not the `RecordingFileContent` object.**
The contract declares Import's `recordingFileContent` parameter as a plain `string`, while
`Export` returns the two-member object, so unwrap before sending — the first argument is the
`Content` member:

```powershell
# On the target server. $exported is the Export result from above.
$newId = Invoke-SwisVerb $swis 'Orion.SEUM.Recordings' 'Import' `
    @($exported.Content, 'Checkout journey', $filePassword)
```

Over REST the body is the same three positional arguments, content string first:

```bash
curl -sS -X POST -u 'svc-automation:...' -H 'Content-Type: application/json' \
  -d '["<content-string>", "Checkout journey", "filePass"]' \
  'https://myorion.example.com:17774/SolarWinds/InformationService/v3/Json/Invoke/Orion.SEUM.Recordings/Import'
```

`Update` wants the same unwrapped string as its second argument:
`@($recordingId, $exported.Content, $recordingName, $filePassword)`.

**`Import` always creates; `Update` is the only overwrite.** `Import` makes a new recording
named `recordingName` and returns its new `RecordingId` even when the target already has a
recording by that name, so a migration script that re-runs `Import` accumulates duplicates.
`Update` rewrites an existing recording under its existing `RecordingId`, and because
transactions reference their recording by that id, the transactions made from it keep
playing the updated script — nothing transaction-side needs recreating. The target-side
decision is therefore `Exists` first:

```powershell
if (Invoke-SwisVerb $swis 'Orion.SEUM.Recordings' 'Exists' @($rec.Guid)) {
    $targetId = Get-SwisData $swis `
        'SELECT RecordingId FROM Orion.SEUM.Recordings WHERE Guid = @guid' @{ guid = $rec.Guid }
    Invoke-SwisVerb $swis 'Orion.SEUM.Recordings' 'Update' `
        @($targetId, $exported.Content, $rec.Name, $filePassword) | Out-Null
} else {
    Invoke-SwisVerb $swis 'Orion.SEUM.Recordings' 'Import' `
        @($exported.Content, $rec.Name, $filePassword) | Out-Null
}
```

Whether `Import` carries the source recording's `Guid` across is not stated in the schema;
the table at the end of this page has the check. If it does not, `Exists` against the source
`Guid` keeps answering false on the target, and the flow above degrades to matching by
`Name`.

**What moves and what does not.** The exported document is the recording alone, and `Import`
lands a recording with no transactions — `Transactions.Create` is still the only WPM verb
that creates a monitored object. Everything configured per transaction stays behind on the
source server: the transactions themselves, their `Frequency`, `WarningThreshold` and
`CriticalThreshold` (columns on `Orion.SEUM.Transactions`), their run parameters
(`Orion.SEUM.TransactionRunParameters`) and their custom-property values
(`Orion.SEUM.TransactionCustomProperties`). After an import, recreate all of it:
`Transactions.Create(recordingId, agentId)` per location, then CRUD for the rest. Whether
the recording's own hosted rows ride inside the ciphered `Content` — `RecordingSteps`, and
the security-relevant `RecordingAuthentications` and `RecordingCertificates` — is not
stated either, and the unverified table has that check too. Do not assume stored credentials
did or did not cross servers until you have run it.

### Recorder compatibility

| Entity | Verb | Parameters | Returns |
|---|---|---|---|
| `Orion.SEUM.RecordingsSettings` | `CheckRecorderCompatibility` | `recorderVersion` | `SolarWinds.SEUM.Verbs.v3.VersionCompatibility` |

The schema documents the returned enumeration explicitly, which is unusual and useful:
`NotCompatible = 0`, `Compatible = 1`, `NewerCompatibleVersionExist = 2`. That third value is
the interesting one, because it means the recording will work but a newer recorder exists,
which is a warning rather than a failure.

`Orion.SEUM.RecordingsSettings` declares **zero properties**, so
`python3 tools/schema_query.py show Orion.SEUM.RecordingsSettings` prints an empty property
list. It is not a broken entity; it exists only to carry this verb.

### Custom properties

`Orion.SEUM.TransactionCustomProperties` and `Orion.SEUM.RecordingCustomProperties` each
publish the platform's standard four custom-property verbs, eight in total. Both inherit from
`System.CustomPropertiesEntity` and both declare zero properties of their own, because the
columns on a custom properties entity are whatever custom properties exist on that server.

| Verb | Parameters, in order |
|---|---|
| `CreateCustomProperty` | `PropertyName`, `Description`, `ValueType`, `Size`, `ValidRange`, `Parser`, `Header`, `Alignment`, `Format`, `Units`, `Usages?`, `Mandatory?`, `Default?`, `SourceId?`, `SourceName?`, `DisplayName?` |
| `CreateCustomPropertyWithValues` | the same ten required arguments, then `Value` (an array of strings), then `Usages?`, `Mandatory?`, `Default?`, `SourceId?`, `SourceName?`, `DisplayName?` |
| `ModifyCustomProperty` | `PropertyName`, `Description`, `Size`, `Values`, `Usages?`, `Mandatory?`, `Default?`, `SourceId?`, `SourceName?`, `propertyDisplayName?` |
| `DeleteCustomProperty` | `PropertyName` |

Two details are worth pinning down because they are the sort of thing that fails at runtime.
`CreateCustomPropertyWithValues` inserts `Value` as the **eleventh** positional argument, so
it is not `CreateCustomProperty` with an extra argument on the end. And
`ModifyCustomProperty` names its last argument `propertyDisplayName`, in camelCase, while the
create verbs name theirs `DisplayName`. Positional callers are unaffected; a client generated
from the Swagger contract is not.

```powershell
Invoke-SwisVerb $swis 'Orion.SEUM.TransactionCustomProperties' 'CreateCustomProperty' `
    @('BusinessService', 'Owning business service', 'string', 128,
      $null, $null, $null, $null, $null, $null) | Out-Null
```

All ten required arguments have to be sent even though `ValidRange`, `Parser`, `Header`,
`Alignment`, `Format` and `Units` are documented as unused and only have to be present. That
is the same shape SolarWinds' own
[Managing Custom Properties](https://solarwinds.github.io/OrionSDK/docs/managing-custom-properties/)
page uses for `Orion.NodesCustomProperties`. The six optional arguments can be omitted
entirely. The parameter-by-parameter walkthrough is in
[../swis/invoke-verbs.md](../swis/invoke-verbs.md), and it applies unchanged here because the
signature is identical.

### Access control

| Entity | `read` | `create` / `update` / `delete` / `invoke` |
|---|---|---|
| `Orion.SEUM.Transactions` | `everyone` (plus `invoke`) | `admin` |
| `Orion.SEUM.Recordings` | `everyone` (plus `invoke`) | `admin` |
| `Orion.SEUM.Settings` | `everyone` (plus `invoke`) | `admin` |
| `Orion.SEUM.TransactionSteps`, `Orion.SEUM.Agents`, `Orion.SEUM.RecordingSteps`, `Orion.SEUM.RecordingAuthentications`, `Orion.SEUM.RecordingCertificates`, `Orion.SEUM.TransactionRunParameters` | `everyone` | `admin` |
| The timing, large-data, web-uri and web-settings entities | not declared | not declared |

The interesting row is the first two. `Orion.SEUM.Transactions` and
`Orion.SEUM.Recordings` grant `invoke` to `everyone` at the entity level, which is looser
than most of the platform. A permission failure calling one of these verbs is therefore more
likely to be an individual right or an account limitation than an entity-level refusal.

## Worked queries

Every query below has been validated against the 2026.2 schema. More live in
[`../../scripts/swql/15-voip-and-web-transactions.swql`](../../scripts/swql/15-voip-and-web-transactions.swql).

### 1. The transaction inventory, with recording and location

The three-way shape of the module in one result: what is being played, where from, and how it
went last time. `Status` is the inherited platform status, so it joins to
[`Orion.StatusInfo`](../reference/status-codes.md).

```sql
SELECT TOP 100
    t.TransactionId,
    t.Name AS TransactionName,
    t.Recording.Name AS RecordingName,
    t.Recording.Version AS RecordingVersion,
    t.Agent.Name AS LocationName,
    st.StatusName,
    t.Frequency,
    t.LastDuration,
    t.WarningThreshold,
    t.CriticalThreshold,
    t.LastPlayedUtc,
    t.IsEnabled,
    t.UnManaged
FROM Orion.SEUM.Transactions t
JOIN Orion.StatusInfo st ON st.StatusId = t.Status
ORDER BY t.Name
```

### 2. Transactions failing right now

`LastErrorMessage` is the first thing to read, before opening a screenshot. Excluding
unmanaged and disabled transactions is what separates "broken" from "deliberately switched
off", and both exclusions are needed because `IsEnabled` and `UnManaged` are different
mechanisms: one is a configuration switch, the other is a maintenance window.

```sql
SELECT TOP 50
    t.Name AS TransactionName,
    t.Agent.Name AS LocationName,
    t.Recording.Name AS RecordingName,
    st.StatusName,
    t.LastErrorMessage,
    t.LastPlayedUtc,
    t.LastDuration
FROM Orion.SEUM.Transactions t
JOIN Orion.StatusInfo st ON st.StatusId = t.Status
WHERE t.IsEnabled = TRUE
  AND t.UnManaged = FALSE
  AND t.LastErrorMessage IS NOT NULL
ORDER BY t.LastPlayedUtc DESC
```

For the step-level version, which tells you *where* in the journey it broke:

```sql
SELECT TOP 50
    ts.Transaction.Name AS TransactionName,
    ts.Transaction.Agent.Name AS LocationName,
    ts.Step.StepOrder AS StepOrder,
    ts.Step.Name AS StepName,
    ts.LastDuration,
    ts.LastErrorMessage,
    ts.ScreenshotId,
    ts.ScreenshotDateTimeUtc
FROM Orion.SEUM.TransactionSteps ts
WHERE ts.LastErrorMessage IS NOT NULL
ORDER BY ts.LastDateTimeUtc DESC
```

`ScreenshotId` being populated tells you an image exists in
`Orion.SEUM.TransactionStepLargeData` for that step. Do not select the image itself here.

### 3. The slowest steps across the estate

This is the query that finds a shared bottleneck: one slow step appearing under several
transactions usually means one slow backend, not several slow journeys. It navigates
`Step.Transaction` for the transaction name, `Step.Step` for the recorded step name and
order, and `Step.Transaction.Agent` for the location, all from one statistics entity.

```sql
SELECT TOP 50
    s.Step.Transaction.Name AS TransactionName,
    s.Step.Step.StepOrder AS StepOrder,
    s.Step.Step.Name AS StepName,
    s.Step.Transaction.Agent.Name AS LocationName,
    COUNT(s.Timestamp) AS Samples,
    AVG(s.AvgDuration) AS MeanDurationMs,
    MAX(s.MaxDuration) AS PeakDurationMs,
    AVG(s.PercentAvailability) AS MeanAvailability
FROM Orion.SEUM.StepResponseTime s
WHERE s.Timestamp >= @startUtc
  AND s.Timestamp < @endUtc
GROUP BY s.Step.Transaction.Name, s.Step.Step.StepOrder, s.Step.Step.Name, s.Step.Transaction.Agent.Name
ORDER BY AVG(s.AvgDuration) DESC
```

### 4. Availability by location

The question a service owner asks. Grouping by location and transaction shows immediately
whether a site is genuinely down or whether one playback location is having a bad day, which
is a distinction the console's per-transaction view makes harder than it should be.

```sql
SELECT TOP 50
    rt.Transaction.Agent.Name AS LocationName,
    rt.Transaction.Name AS TransactionName,
    COUNT(rt.Timestamp) AS Samples,
    AVG(rt.PercentAvailability) AS MeanAvailability,
    AVG(rt.AvgDuration) AS MeanDurationMs,
    MAX(rt.MaxDuration) AS PeakDurationMs
FROM Orion.SEUM.ResponseTime rt
WHERE rt.Timestamp >= @startUtc
  AND rt.Timestamp < @endUtc
GROUP BY rt.Transaction.Agent.Name, rt.Transaction.Name
ORDER BY AVG(rt.PercentAvailability)
```

`AVG(PercentAvailability)` gives every interval equal weight. For a number that goes in front
of a customer, weight it by the sample count instead, which is exactly what `Weight` is for:

```sql
SELECT TOP 50
    rt.Transaction.Agent.Name AS LocationName,
    SUM(rt.PercentAvailability * rt.Weight) / SUM(rt.Weight) AS WeightedAvailability,
    SUM(rt.Weight) AS TotalWeight
FROM Orion.SEUM.ResponseTimeReport rt
WHERE rt.Timestamp >= @startUtc
  AND rt.Timestamp < @endUtc
GROUP BY rt.Transaction.Agent.Name
ORDER BY SUM(rt.PercentAvailability * rt.Weight) / SUM(rt.Weight)
```

### 5. The request waterfall inside one transaction

Where a slow step is finally explained. Sorting by `TotalDurationMs` finds the expensive
request; the individual duration columns say which phase of it was expensive, and that is the
difference between a DNS problem, a TLS handshake problem, a slow server and a large payload.

```sql
SELECT TOP 100
    r.TransactionStep.Transaction.Name AS TransactionName,
    r.StepFullName,
    r.RequestIndex,
    r.Url,
    r.MimeType,
    r.StatusCode,
    r.Size,
    r.BlockedDurationMs,
    r.DNSResolutionDurationMs,
    r.ConnectionDurationMs,
    r.SendDurationMs,
    r.TimeToFirstByteDurationMs,
    r.DownloadDurationMs,
    r.TotalDurationMs
FROM Orion.SEUM.TransactionStepRequests r
WHERE r.TransactionStep.TransactionId = @transactionId
ORDER BY r.TotalDurationMs DESC
```

For the timeline version, select the `...BeginMs` and `...EndMs` offsets instead and order by
`RequestBeginMs`.

### 6. Failing requests by status code

An HTTP error inside a step does not always fail the step, because a recorded journey can
complete perfectly while a tracking pixel or an API call 500s in the background. This finds
those.

```sql
SELECT TOP 100
    ts.Transaction.Name AS TransactionName,
    ts.Step.Name AS StepName,
    r.StatusCode,
    COUNT(r.TransactionStepRequestId) AS Requests,
    SUM(r.Size) AS TotalBytes
FROM Orion.SEUM.TransactionStepRequests r
JOIN Orion.SEUM.TransactionSteps ts ON ts.TransactionStepId = r.TransactionStepId
WHERE r.StatusCode >= 400
GROUP BY ts.Transaction.Name, ts.Step.Name, r.StatusCode
ORDER BY COUNT(r.TransactionStepRequestId) DESC
```

### 7. Playback location health and load

A location above roughly 80 percent load starts adding its own queueing delay to every
timing it reports, which looks exactly like an application getting slower. This is the query
to run before believing a sudden estate-wide regression.

```sql
SELECT TOP 100
    a.AgentId,
    a.Name AS LocationName,
    a.Hostname,
    a.IP,
    a.AgentVersion,
    a.ConnectionStatusInfo.ShortDescription AS ConnectionState,
    a.ConnectionStatusMessage,
    a.ConnectionStatusTimeStampUtc,
    a.LoadPercentage,
    a.AvgLoadPercentageLast30min,
    a.AvgLoadPercentageLast60min,
    a.NumManagedTransactions,
    a.NumAllTransactions,
    a.Engine.ServerName AS PollingEngine
FROM Orion.SEUM.Agents a
ORDER BY a.LoadPercentage DESC
```

Note `ConnectionStatusInfo.ShortDescription` rather than a join to `Orion.StatusInfo`:
`ConnectionStatus` is a WPM-specific code set. The historical view of the same thing, with
the queue length that predicts trouble before load does:

```sql
SELECT TOP 100
    a.Name AS LocationName,
    COUNT(s.Timestamp) AS Samples,
    AVG(s.AvgLoadPercentage) AS MeanLoadPercent,
    MAX(s.MaxLoadPercentage) AS PeakLoadPercent,
    AVG(s.AvgNumManagedTransactions) AS MeanManagedTransactions,
    MAX(s.MaxQueueLength) AS PeakQueueLength,
    AVG(s.PercentAvailability) AS MeanAvailability
FROM Orion.SEUM.AgentStatus s
JOIN Orion.SEUM.Agents a ON a.AgentId = s.AgentId
WHERE s.Timestamp >= @startUtc
  AND s.Timestamp < @endUtc
GROUP BY a.Name
ORDER BY AVG(s.PercentAvailability)
```

### 8. Which recordings are actually in use

A `LEFT JOIN` so that recordings with no transaction show up with a null transaction name.
Those are either work in progress or leftovers, and both are worth knowing about before
somebody deletes a recording that turns out to be load-bearing.

```sql
SELECT TOP 100
    rec.RecordingId,
    rec.Name AS RecordingName,
    rec.Version,
    rec.Width,
    rec.Height,
    rec.LastUpdateUtc,
    t.Name AS TransactionName,
    t.Agent.Name AS LocationName,
    t.IsEnabled
FROM Orion.SEUM.Recordings rec
LEFT JOIN Orion.SEUM.Transactions t ON t.RecordingId = rec.RecordingId
ORDER BY rec.Name, t.Agent.Name
```

### 9. Transactions over their own critical threshold

Comparing against the transaction's configured threshold rather than a fixed number keeps one
query meaningful across a two-second login check and a ninety-second checkout journey.

```sql
SELECT TOP 100
    t.Name AS TransactionName,
    t.Agent.Name AS LocationName,
    t.LastDuration,
    t.WarningThreshold,
    t.CriticalThreshold,
    st.StatusName,
    t.LastPlayedUtc
FROM Orion.SEUM.Transactions t
JOIN Orion.StatusInfo st ON st.StatusId = t.Status
WHERE t.IsEnabled = TRUE
  AND t.UnManaged = FALSE
  AND t.LastDuration > t.CriticalThreshold
ORDER BY t.LastDuration DESC
```

### 10. Raw samples for one transaction

When an average is hiding the shape of the problem, drop to the detail tier.
`Orion.SEUM.StepResponseTimeDetail` has a single `Duration` per row because a raw sample has
no min or max, and it also declares `TransactionId` directly so no navigation is needed for
the filter.

```sql
SELECT TOP 500
    d.Step.Step.StepOrder AS StepOrder,
    d.Step.Step.Name AS StepName,
    d.Timestamp,
    d.Duration,
    d.PercentAvailability,
    d.Status
FROM Orion.SEUM.StepResponseTimeDetail d
WHERE d.TransactionId = @transactionId
  AND d.Timestamp >= @startUtc
  AND d.Timestamp < @endUtc
ORDER BY d.Timestamp DESC
```

Detail data has the shortest retention of the three tiers, so an empty result here does not
mean nothing happened. It usually means the window you asked for has already been rolled up.

## Gotchas

**Searching for "WPM" finds nothing.** The namespace is `Orion.SEUM.`, for synthetic end user
monitoring. Search for `SEUM`, or for `transaction`, or for `recording`.

**`Orion.SEUM.Agents` is a playback location, not a monitoring agent.** The platform's
deployed agent is `Orion.AgentManagement.Agent`, a different entity in a different namespace
with no direct relationship to this one, though both key on a column called `AgentId` and
share several column names besides. The NetObject reference calls `Orion.SEUM.Agents`
"Location", which is the console's word for it.

**A step exists twice.** `Orion.SEUM.RecordingSteps` has the name, URL and order;
`Orion.SEUM.TransactionSteps` has the timings, thresholds and status. Joining them is
`ts.Step`, and forgetting it produces a step report with no step names in it.

**Two navigations from a transaction to its steps.** `Steps` is `System.Hosting` and is what
you want; `RelySteps` is `System.Reliance` and answers a different question. The reverse pair
is `Transaction` and `RelyTransactions`.

**`DateTimeUtc` was removed from ten `Orion.SEUM.` entities in 2026.2.** So were `Archive`,
`RecordCount` and, on some of them, `Screenshot`, `RawHtml`, `ErrorMessage` and
`ScreenshotId`. `Timestamp` is the column that remains. This is the most likely upgrade
breakage in the module and it is recorded in
[../reference/schema-changes-2026.1-to-2026.2.md](../reference/schema-changes-2026.1-to-2026.2.md).

**`Orion.SEUM.Agents.Unmanaged` has a lowercase `m`.** `System.ManagedEntity` declares
`UnManaged`, `UnManageFrom` and `UnManageUntil`, and `Orion.SEUM.Transactions` declares
`UnManaged` itself with that capitalisation. `Orion.SEUM.Agents` declares its own
`Unmanaged` instead, alongside the inherited `UnManageFrom` and `UnManageUntil`. Use the
spelling the entity declares, and do not copy a predicate from a transaction query into a
location query without checking it:

```bash
python3 tools/schema_query.py props Orion.SEUM.Agents --grep manage
```

**`ConnectionStatus` does not join to `Orion.StatusInfo`.** It resolves through
`Orion.SEUM.AgentConnectionStatus`, navigable as `ConnectionStatusInfo`. The inherited
`Status` is the platform one.

**`Orion.SEUM.Transactions.Unmanage` has four parameters where the platform's other unmanage
verbs have five.** No `allowOverlapping`. A generic wrapper will fail against it.

**The unmanage verbs want a NetObject string.** Transaction 17 is `T:17`. A bare integer is
rejected.

**`Recordings.Import` takes the `Content` string and always creates.** Unwrap the
`RecordingFileContent` object `Export` returns, and expect a new `RecordingId` on every
call — `Update` with the target's `RecordingId` is the overwrite path.

**Never select `Password`, `ProxyPassword` or the recording authentication columns.** All
four are declared readable by `everyone` and none of them belongs in a report.

**Never select `Screenshot`, `Thumbnail` or `RawHtml` in a multi-row query.** They are
`System.Byte[]` and `System.String` blobs on `System.ExtensionEntity` types, one per sample.
Fetch them for a single step you are looking at.

**`Orion.SEUM.RecordingsSettings` declares zero properties.** It exists only to host
`CheckRecorderCompatibility`. An empty property list from `show` is not a broken entity here.

**Time-bound every timing query.** All six response-time entities and both agent status
entities inherit from `System.StatisticsEntity`, and a transaction playing every five minutes
from eight locations with twelve steps produces a lot of rows. See
[../swql/performance.md](../swql/performance.md).

**Account limitations filter silently.** Two accounts running the same availability report
can legitimately get different numbers, which is a permissions answer rather than a data
answer.

## What is not verified here

The `Orion.SEUM.` entities are better documented than most, with a real summary on almost
every property, so this list is short. Each row says how to settle the question on your own
server.

| Claim | Status | How to check |
|---|---|---|
| Durations are in milliseconds | Verified for requests, where the column names say so (`TotalDurationMs`, `DNSResolutionDurationMs`). **Not stated** for `LastDuration`, `AvgDuration`, `MinDuration` and `MaxDuration`, whose summaries say only "duration" | Compare `SELECT TOP 5 ts.LastDuration FROM Orion.SEUM.TransactionSteps ts` against the same step's `SUM(r.TotalDurationMs)` from `Orion.SEUM.TransactionStepRequests` |
| A transaction's duration is the sum of its steps' durations | Not stated anywhere. Playback overhead between steps may or may not be included | `SELECT t.LastDuration, SUM(ts.LastDuration) AS StepSum FROM Orion.SEUM.Transactions t JOIN Orion.SEUM.TransactionSteps ts ON ts.TransactionId = t.TransactionId WHERE t.TransactionId = @transactionId GROUP BY t.LastDuration` |
| Whether `Password` and `ProxyPassword` return plaintext or a cipher | Not stated. The schema establishes only that the columns exist and are readable by `everyone` | Read one on a test account and see. Treat the answer as sensitive either way |
| The integers in `Orion.SEUM.AgentConnectionStatus` | Not enumerated in the schema; the lookup entity holds them on a live server | `SELECT c.StatusId, c.ShortDescription FROM Orion.SEUM.AgentConnectionStatus c ORDER BY c.StatusId` |
| The meaning of `Type` on `Orion.SEUM.TransactionRunParameters` | Undocumented `System.Int32` distinguishing kinds of run parameter | `SELECT p.Type, COUNT(p.Key) AS Parameters FROM Orion.SEUM.TransactionRunParameters p GROUP BY p.Type` |
| The valid names in `Orion.SEUM.Settings` and `Orion.SEUM.WebSettings` | Two separate name/value bags with no enumerated keys and no stated difference between them | `SELECT s.Name, s.Value FROM Orion.SEUM.Settings s ORDER BY s.Name` and `SELECT w.SettingName, w.SettingValue FROM Orion.SEUM.WebSettings w ORDER BY w.SettingName` |
| What `Orion.SEUM.Websites` is populated from | Six columns (`WebsiteID`, `ServerName`, `IPAddress`, `Port`, `SSLEnabled`, `Type`) with no relationships to anything else in the module | `SELECT TOP 25 w.WebsiteID, w.ServerName, w.IPAddress, w.Port, w.SSLEnabled, w.Type FROM Orion.SEUM.Websites w` |
| Which `Version` values on `Orion.SEUM.Recordings` a given release supports | The summary says the field "determines if recording is supported" but does not enumerate the supported set | `SELECT r.Version, COUNT(r.RecordingId) AS Recordings FROM Orion.SEUM.Recordings r GROUP BY r.Version` and then `CheckRecorderCompatibility` against your recorder |
| What the `Content` member of `SolarWinds.SEUM.Common.Models.RecordingFileContent` holds | The contract does enumerate the type: two `string` members, `Content` and `Name`. The encoding of the file content itself is not stated | `python3 tools/schema_query.py verb Orion.SEUM.Recordings Export` for the shape, then invoke `Export` once and inspect the returned `XmlElement` |
| Whether `Import` preserves the source recording's `Guid` | Not stated. `Import` takes content, name and password and returns only the new integer id | Export a recording, import it on a second server, then compare `SELECT r.Guid FROM Orion.SEUM.Recordings r WHERE r.RecordingId = @newId` against the source row's `Guid` |
| Whether `RecordingSteps`, `RecordingAuthentications` and `RecordingCertificates` travel inside the exported `Content` | Not stated. All three are hosted by the recording, but the exported file is ciphered and its contents are not enumerated | Export a recording that has stored credentials, import it on a clean server, and query all three entities for the new `RecordingId` |
| The retention windows behind the detail, rolled-up and report tiers | Configured per installation, not in the schema | Compare `SELECT MIN(d.Timestamp) AS Oldest FROM Orion.SEUM.StepResponseTimeDetail d` against the same on `Orion.SEUM.StepResponseTime` and `Orion.SEUM.StepResponseTimeReport` |

There is no WPM page in SolarWinds' published OrionSDK documentation and no WPM sample script
in the SDK samples directory, so the schema, the `Metadata.*` entities and your own data are
the sources. [`../../scripts/swql/08-schema-introspection.swql`](../../scripts/swql/08-schema-introspection.swql)
has the introspection queries.

## Related pages

- [README.md](README.md) for the module index and how to check what is installed.
- [vnqm.md](vnqm.md) for VoIP and Network Quality Manager, the other module whose namespace
  does not match its product name, and the other place this platform does synthetic testing.
- [sam.md](sam.md) for `Orion.APM.Application`, which monitors the servers behind the pages
  WPM plays back, and for the HTTP component monitors that answer a much simpler question
  than a recorded browser journey does.
- [../platform/modules.md](../platform/modules.md) for the whole-schema module map and the
  other prefix-to-product mismatches.
- [../schema/relationships.md](../schema/relationships.md) for `System.Hosting`,
  `System.Reference` and the `System.Reliance` edges behind `RelySteps`.
- [../reference/netobject-types.md](../reference/netobject-types.md) for the `T:`, `TS:`,
  `TSR:` and `L:` prefixes.
- [../reference/status-codes.md](../reference/status-codes.md) for the `Status` integers.
- [../reference/schema-changes-2026.1-to-2026.2.md](../reference/schema-changes-2026.1-to-2026.2.md)
  for the removal of `DateTimeUtc` from the timing entities.
- [../swis/invoke-verbs.md](../swis/invoke-verbs.md) and
  [../swis/verb-catalog.md](../swis/verb-catalog.md) for positional arguments and for the
  six `Unmanage` verbs that do not share a signature.
- [../swql/performance.md](../swql/performance.md) for choosing between the detail, rolled-up
  and report tiers.
- [`../../scripts/swql/15-voip-and-web-transactions.swql`](../../scripts/swql/15-voip-and-web-transactions.swql)
  for more verified sample queries against this module.
- [apps/porter](../../apps/porter/README.md) — a shipped Windows utility whose WPM provider implements the recording Export/Import round trip, cipher password and Content-string unwrap included

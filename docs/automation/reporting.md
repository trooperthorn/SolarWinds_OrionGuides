# Reports and scheduled exports

"Reporting" against SWIS means two related but separate things, and knowing which one you are
doing saves a lot of wasted effort.

1. **Platform reports.** Objects built in the web console's report builder, stored in
   `Orion.Report`, delivered on a schedule by `Orion.ReportJobs`. They render in the console
   and email themselves as PDF or CSV.
2. **Scripted exports.** A SWQL query run from PowerShell, Python or curl, written to a file
   and picked up by whatever consumes it. No console object exists at all.

The second is where automation lives. The report entities are queryable and are worth
understanding for inventory and audit, but their `Definition` is an opaque serialisation that
this repository cannot verify, so building a report by writing that string is not something to
attempt from a script. Building the same output as a scripted export is straightforward, and
the rest of this page is mostly about doing that well.

## The reporting entities

```bash
python3 tools/schema_query.py show Orion.Report
```

```text
Orion.Report   [2026.2]
  inherits: System.Entity -> Orion.Report
  operations: invoke, read, update
    read                                   requires everyone
    read,update                            requires manageReports
    read,update,invoke                     requires manageReports

  properties (16)
    ReportID                                   System.Int32
    Name                                       System.String
    Category                                   System.String
    Title                                      System.String
    Type                                       System.String
    SubTitle                                   System.String
    Description                                System.String
    LegacyPath                                 System.String
    Definition                                 System.String
```

| Entity | Holds |
| --- | --- |
| `Orion.Report` | One report definition: name, title, category, owner, and the serialised `Definition` |
| `Orion.ReportJobs` | One scheduled delivery: name, enabled flag, owning account, last run, and serialised schedule, action and report lists |
| `Orion.ReportJobDefinitions` | Which reports a job renders, as `ReportJobID` to `ReportID` |
| `Orion.ReportSchedules` | Which frequency a job runs on, as `ReportJobID` to `FrequencyID` |
| `Orion.Frequencies` | The recurrence itself, including a cron expression and its time zone |
| `Orion.ReportJobUrls` | Extra URLs a job renders alongside its reports |
| `Orion.ReportJobData` | Per-report view of the jobs that include it |
| `Orion.ReportFavorites` | Which accounts starred which reports |
| `Orion.ReportsCustomProperties` | Custom properties defined on reports |
| `Orion.Reporting` | No properties. One verb, `ExecuteSQL` |

Note the access control on `Orion.Report`: it declares `read`, `update` and `invoke` but **no
`create` and no `delete` operation**, and the four verbs it exposes carry no right of their own,
so entity-level `invoke` governs them and that needs `manageReports`.

`Orion.Report.Definition` is where a report's content lives, including whichever SWQL a custom
table resource in it uses. Its format is **not recorded in the published schema** and is
unverified here. You can read it, and reading it is a reasonable way to find every report that
touches a particular entity, but treat writing it as out of scope for a script.

The verbs, for completeness:

| Verb | Parameters, in order | Returns |
| --- | --- | --- |
| `CreateReport` | `name`, `description`, `limitationCategory`, `category`, `title`, `subtitle`, `definition`, `isFavorite`, `userName` | `number` |
| `UpdateReport` | `reportId`, `name`, `description`, `limitationCategory`, `category`, `title`, `subtitle`, `definition`, `isFavorite`, `userName` | `System.Void` |
| `DuplicateReport` | `reportID`, `accountID` | `number` |
| `DeleteReport` | `reportID` | `System.Void` |

`DuplicateReport` is the one that is genuinely useful from a script, because it does not
require you to construct a `definition`: copy an existing report to another account and let
that account edit it in the console.

### Report schedules are not `Orion.ScheduleTaskDefinition`

Two scheduling mechanisms exist and the schema keeps them apart. Report delivery is
`Orion.ReportJobs` joined through `Orion.ReportSchedules` to `Orion.Frequencies`. The generic
scheduled task framework is `Orion.ScheduleTaskDefinition` with `Orion.ScheduleEntityAssignment`,
which is what [scheduling.md](scheduling.md) covers and what maintenance plans use.

Neither entity declares a relationship to the other, so "my report job should appear in the
scheduled tasks list" is not something this schema supports asserting. Whether a particular
release also surfaces report jobs as rows in `Orion.ScheduleTaskDefinition` is unverified here.
One query settles it on your server:

```sql
SELECT
    t.ScheduleType,
    COUNT(t.ScheduleTaskID) AS Tasks
FROM Orion.ScheduleTaskDefinition t
GROUP BY t.ScheduleType
ORDER BY COUNT(t.ScheduleTaskID) DESC
```

If a `ScheduleType` value looks report-shaped, they are unified on your release. If not, query
both when you want the full picture of "what runs on this server without a person".

### `Orion.Reporting.ExecuteSQL`

```bash
python3 tools/schema_query.py verb Orion.Reporting ExecuteSQL
```

```text
Orion.Reporting.ExecuteSQL
  returns: System.Data.DataTable
  REST:    POST /Invoke/Orion.Reporting/ExecuteSQL
  requires: admin
  parameters (4):
    sqlQueryText: string (required)
    sqlQueryParameters: array<System.Collections.Generic.KeyValuePair~System.String_System.Object~> (optional)
    outputRowsMaxCount: number (optional)
    schemaOnly: boolean (optional)
```

This runs **T-SQL**, not SWQL, against the Orion database, and it requires `admin`. It exists
because a handful of legacy reports were written against tables directly.

Reach for it last, and preferably not at all. SWQL is the supported query surface; the physical
schema behind it is not a contract and changes between releases, so a query written against
tables is a query you will fix after every upgrade. Whether account limitations are applied to
its results is not recorded in the schema and is unverified here, which is another reason to
prefer SWQL: with SWQL you know limitations apply, and can reason about it.

`outputRowsMaxCount` is the only bound available, and `schemaOnly` returns column metadata
without rows, which is the safe way to check a query shape before running it for real.

## How a SWQL query becomes a report

For a **platform report**, the path is through the console: create a report, add a custom
table resource, choose the advanced SWQL data source, paste the query. The query then lives
inside `Orion.Report.Definition`, which is why the automation story stops there.

For a **scripted export**, the path is the one this page recommends, and it is four steps:

1. Write the query and validate it. Bound result set, named columns, time-bounded if it
   touches history.
2. Run it through the client of your choice with bound parameters.
3. Page it if it can be large.
4. Serialise to CSV or JSON and write the file atomically.

The advantages over a platform report are worth stating, because they are the reason to choose
this path deliberately rather than by default. A scripted export is version controlled, it is
diffable, it runs on a schedule you control, its failures are visible to your own monitoring,
and it produces exactly the columns you asked for. What it loses is the console's rendering,
its emailing, and its integration with the report permission model.

## Paging with `WITH ROWS` and `WITH TOTALROWS`

SWQL has no `OFFSET`/`FETCH`. Paging is a trailing clause after `ORDER BY`:

```sql
SELECT
    n.NodeID,
    n.Caption,
    n.IPAddress
FROM Orion.Nodes n
ORDER BY n.NodeID
WITH ROWS 1 TO 500 WITH TOTALROWS
```

Bounds are 1-based and inclusive, so the next page is `501 TO 1000`. `WITH TOTALROWS` adds a
`totalRows` member to the response envelope carrying the count the query would have returned
unwindowed, which is what lets a client work out how many pages there are.

Four rules make paging correct rather than approximately correct:

1. **`ORDER BY` must be a total order.** Order by the key, or by something plus the key as a
   tie-breaker. Without one, page 2 is not guaranteed to continue where page 1 stopped, and
   rows are silently repeated or skipped. A caption is not a key.
2. **Order by an integer key rather than a string where you can.** The sort happens before the
   window is taken, so it is paid on every page.
3. **Ask for `WITH TOTALROWS` once, on the first page.** It is a count over the unwindowed
   result and it is not free.
4. **For a set you already know, do not page at all.** Bind the ids as one multi-valued
   parameter: `WHERE n.NodeID IN @ids`. One round trip beats twenty pages.

Not every client surfaces the envelope. `SwisPowerShell`'s `Get-SwisData` returns the row
objects, so `totalRows` is not directly reachable and a separate `COUNT` query is the practical
substitute. The raw REST route returns the envelope intact, so a Python or curl client can read
`totalRows` directly. Both approaches appear below.

More detail: [../swql/performance.md](../swql/performance.md#8-page-with-with-rows-do-not-pull-everything)
and [../swis/rest-api.md](../swis/rest-api.md#paging-with-with-rows-and-with-totalrows).

## Exporting from PowerShell

`Get-SwisData` returns objects, so `Export-Csv` is a one-liner:

```powershell
$query = @'
SELECT
    n.NodeID,
    n.Caption,
    n.IPAddress,
    n.Vendor,
    n.Location,
    s.StatusName
FROM Orion.Nodes n
JOIN Orion.StatusInfo s ON n.Status = s.StatusId
ORDER BY n.NodeID
WITH ROWS 1 TO 1000
'@

Get-SwisData -SwisConnection $swis -Query $query |
    Export-Csv -Path 'nodes.csv' -NoTypeInformation -Encoding UTF8
```

For JSON, `ConvertTo-Json` needs an explicit `-Depth`, because the default of 2 truncates
nested objects into the string `System.Object[]`:

```powershell
Get-SwisData -SwisConnection $swis -Query $query |
    ConvertTo-Json -Depth 5 |
    Set-Content -Path 'nodes.json' -Encoding UTF8
```

Two PowerShell-specific traps in CSV output. `Export-Csv` writes whatever properties the first
object has, so a query whose first row has a `NULL` in a column still produces the column,
while an empty result set produces an empty file with no header at all. And `-Encoding UTF8`
writes a byte order mark on Windows PowerShell 5.1, which some downstream parsers treat as part
of the first column name; PowerShell 7 defaults to UTF-8 without a BOM.

## Exporting from Python

The REST envelope carries `totalRows`, so paging is explicit and readable:

```python
import csv
import json

PAGE = 1000
BASE = """
SELECT
    n.NodeID,
    n.Caption,
    n.IPAddress,
    n.Vendor,
    n.Location,
    s.StatusName
FROM Orion.Nodes n
JOIN Orion.StatusInfo s ON n.Status = s.StatusId
ORDER BY n.NodeID
"""


def export(swis, path):
    rows, start, total = [], 1, None
    while True:
        window = f"{BASE} WITH ROWS {start} TO {start + PAGE - 1}"
        if total is None:
            window += " WITH TOTALROWS"
        envelope = swis.query(window)
        if total is None:
            total = envelope.get("totalRows", 0)
        page = envelope["results"]
        rows.extend(page)
        if len(page) < PAGE or len(rows) >= total:
            break
        start += PAGE

    if not rows:
        raise SystemExit("no rows returned; check the account limitations before the query")

    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    with open(path.replace(".csv", ".json"), "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2, default=str)

    return len(rows)
```

`default=str` on `json.dump` matters: SWIS returns `System.DateTime` values as ISO-8601 strings
over REST, but a client that parses them into `datetime` objects will then fail to serialise
them without it.

The loop above assumes a client whose `query()` hands back the whole envelope rather than just
the rows, which is precisely what makes `totalRows` reachable. The official `orionsdk` package
does that — its `query()` returns the parsed response, so `envelope["results"]` and
`envelope["totalRows"]` are both there — and it is the one to use in production. This
repository's [`swis_client.py`](../../scripts/python/swis_client.py) unwraps `results` and
returns the row list instead, so against it you take the count from a separate `COUNT` query,
exactly as the PowerShell example below does.

## A complete scheduled export

This is the shape to copy: parameters, no hard-coded secrets, paging, a real failure path, and
an atomic write so a consumer never reads a half-finished file.

```powershell
<#
.SYNOPSIS
    Export a capacity listing to CSV. Intended to run unattended from Task Scheduler.

.DESCRIPTION
    Writes one row per monitored volume above a usage threshold. The query is paged, so
    the size of the estate does not decide whether this succeeds.

    Exit codes: 0 success, 1 connection or query failure, 2 no rows returned.

.EXAMPLE
    .\Export-Capacity.ps1 -Hostname orion.example.com -Trusted -Path C:\exports\capacity.csv
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$Hostname,

    [pscredential]$Credential,

    [switch]$Trusted,

    [Parameter(Mandatory)]
    [string]$Path,

    [ValidateRange(1, 100)]
    [int]$ThresholdPercent = 85,

    [ValidateRange(50, 10000)]
    [int]$PageSize = 1000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Only the columns needed. There is no SELECT * in SWQL, and Orion.Volumes is wide enough
# that naming columns is a real saving on a large estate.
#
# ORDER BY is on the key. Paging on a non-unique sort repeats or skips rows between pages.
$baseQuery = @'
SELECT
    v.VolumeID,
    v.Node.Caption AS NodeName,
    v.Caption AS VolumeName,
    v.VolumeType,
    v.VolumeSize,
    v.VolumeSpaceUsed,
    v.VolumePercentUsed,
    s.StatusName
FROM Orion.Volumes v
JOIN Orion.StatusInfo s ON v.Status = s.StatusId
WHERE v.VolumePercentUsed >= @threshold
  AND v.UnManaged = FALSE
ORDER BY v.VolumeID
'@

# The count is a separate cheap query. SwisPowerShell surfaces rows rather than the
# response envelope, so WITH TOTALROWS is not reachable from Get-SwisData.
$countQuery = @'
SELECT TOP 1 COUNT(v.VolumeID) AS Total
FROM Orion.Volumes v
WHERE v.VolumePercentUsed >= @threshold
  AND v.UnManaged = FALSE
'@

$temp = $null

function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $stamp = (Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss')
    Write-Information "$stamp Z [$Level] $Message" -InformationAction Continue
}

try {
    Import-Module SwisPowerShell -ErrorAction Stop

    # No credentials in the file. -Trusted uses the Windows identity the scheduled task
    # runs as, which is the right answer for an unattended job.
    $swis = if ($Trusted) {
        Connect-Swis -Hostname $Hostname -Trusted
    }
    elseif ($Credential) {
        Connect-Swis -Hostname $Hostname -Credential $Credential
    }
    else {
        throw 'Supply -Trusted or -Credential. This script will not prompt when unattended.'
    }

    $params = @{ threshold = $ThresholdPercent }
    $total = [int](Get-SwisData -SwisConnection $swis -Query $countQuery -Parameters $params)
    Write-Log "$total volume(s) at or above $ThresholdPercent percent"

    if ($total -eq 0) {
        Write-Log 'No rows. If that is unexpected, check the account limitations before the query.' 'WARN'
        exit 2
    }

    $rows = [Collections.Generic.List[object]]::new()
    $start = 1

    while ($rows.Count -lt $total) {
        $end = $start + $PageSize - 1
        $paged = "$baseQuery WITH ROWS $start TO $end"
        $page = @(Get-SwisData -SwisConnection $swis -Query $paged -Parameters $params)

        if ($page.Count -eq 0) { break }

        $rows.AddRange($page)
        Write-Log "fetched $($rows.Count) of $total"
        $start = $end + 1
    }

    # Write to a temporary file in the destination directory, then move it into place.
    # A consumer polling for the file never sees a partial one, and a failure halfway
    # through leaves the previous export intact.
    $directory = Split-Path -Parent $Path
    if ($directory -and -not (Test-Path $directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }

    $temp = "$Path.$PID.tmp"
    $rows | Export-Csv -Path $temp -NoTypeInformation -Encoding UTF8
    Move-Item -Path $temp -Destination $Path -Force
    $temp = $null

    Write-Log "wrote $($rows.Count) row(s) to $Path"
    exit 0
}
catch {
    # Surface the server's own message. SWIS returns its error text in a JSON Message
    # field, and swallowing it turns a one-line contract error into an afternoon.
    Write-Log $_.Exception.Message 'ERROR'
    if ($_.ScriptStackTrace) { Write-Log $_.ScriptStackTrace 'ERROR' }
    exit 1
}
finally {
    if ($temp -and (Test-Path $temp)) {
        Remove-Item $temp -Force -ErrorAction SilentlyContinue
    }
}
```

Four decisions in there are worth naming, because they are the difference between a script that
runs for a year and one that needs attention every month.

**No prompting.** An unattended job that calls `Get-Credential` hangs forever and looks like a
slow query. Requiring `-Trusted` or `-Credential` fails immediately instead.

**Distinct exit codes.** "No rows" is not the same failure as "could not connect", and a
scheduler that treats them alike will wake someone at 3am for an empty capacity listing.

**Atomic write.** Export to a temporary name and move. On most filesystems the move is atomic,
so the consumer sees either the old file or the complete new one.

**The server's message, surfaced.** SWIS puts its error text in a `Message` field. A wrong
argument count, a property that does not exist, or a value that will not coerce all come back
as readable text, and a `catch` block that logs only "export failed" throws that away.

Schedule it with Task Scheduler running as a service account that has been granted only what
the query needs. See
[accounts-and-permissions.md](accounts-and-permissions.md#the-rights-that-gate-verbs) for
scoping that account, and note that a read-only export needs no verb right at all.

A more general version of this, covering nodes, interfaces, volumes and applications, is
[`Export-OrionInventory.ps1`](../../scripts/powershell/Export-OrionInventory.ps1).

## Practical constraints

**Always time-bound a query against history.** Statistics, events and alert history are the
largest tables on the system, and a query over "all time" is a scan of the biggest thing in the
database. Bind the window as parameters rather than embedding a literal, so the same script can
produce yesterday's output and last month's.

**Always bound the result set.** `TOP n` or `WITH ROWS a TO b`. An unbounded query against a
large installation is a genuine production risk, not a style preference.

**Mind the timezone functions.** `GetUtcDate()` combined with `AddDay` and friends produces the
wrong offset, because those compile to T-SQL `DATEADD`, which is timezone blind. The correct
shape is `ToUtc(AddDay(-30, GetDate()))` for a UTC column and `AddDay(-30, GetDate())` for a
local one. Which columns are which matters, and the schema only tells you for some of them:
`Orion.AuditingEvents.TimeLoggedUtc` says UTC in its name, and `Orion.Events.EventTime`
documents itself as local. `Orion.AlertHistory.TimeStamp` and `Orion.ResponseTime.DateTime`
carry **no documented timezone** and are unverified here, so measure them once on your own
server with the `MinuteDiff` probe in
[../swql/date-and-time.md](../swql/date-and-time.md#measuring-a-columns-timezone) before you
write a narrow window against either. See
[../swql/date-and-time.md](../swql/date-and-time.md).

**Run off-peak, or against a replica.** A monthly aggregation over a month of statistics
competes with polling for the same database. Schedule it when polling load is lowest, and if
your installation has a reporting replica, point the export at it. Whether one exists is
installation topology rather than schema, so ask whoever runs the database.

**Prefer `Downsample` to raw statistics rows for trend charts.** Pulling every raw sample to
average it in the client moves the whole table across the wire to compute one number.

**The account decides the contents.** Account limitations silently filter results, so the same
export run by two service accounts produces two different files with no error from either. If a
row count changes without the query changing, check the account before the query. This is the
single most common cause of "the numbers shrank overnight".

**Join `Orion.StatusInfo` rather than hard-coding status integers.** Output that says
`Status = 2` is unreadable and breaks if a status value is added; output that carries
`StatusName` is neither.

## Worked queries

These are shaped for exports: named columns, bounded, and readable by whoever receives the
output rather than only by the person who wrote them.

### Estate inventory

The one people ask for most. One row per node, with the polling engine and a human-readable
status.

```sql
SELECT
    n.NodeID,
    n.Caption,
    n.IPAddress,
    n.Vendor,
    n.MachineType,
    n.Location,
    n.ObjectSubType AS PollingMethod,
    s.StatusName,
    n.UnManaged,
    n.Engine.ServerName AS PollingEngine
FROM Orion.Nodes n
JOIN Orion.StatusInfo s ON n.Status = s.StatusId
ORDER BY n.NodeID
WITH ROWS 1 TO 1000 WITH TOTALROWS
```

`n.Engine.ServerName` is a to-one dot-walk, which is the cheap way to pull one column from a
related entity. `ORDER BY n.NodeID` rather than by caption is what makes the paging correct.

### Capacity: volumes above a threshold

```sql
SELECT
    v.VolumeID,
    v.Node.Caption AS NodeName,
    v.Caption AS VolumeName,
    v.VolumeType,
    v.VolumeSize,
    v.VolumeSpaceUsed,
    v.VolumePercentUsed,
    s.StatusName
FROM Orion.Volumes v
JOIN Orion.StatusInfo s ON v.Status = s.StatusId
WHERE v.VolumePercentUsed >= @threshold
  AND v.UnManaged = FALSE
ORDER BY v.VolumeID
WITH ROWS 1 TO 500 WITH TOTALROWS
```

`UnManaged = FALSE` is doing real work. Without it the output includes volumes on machines that
are deliberately in a maintenance window, whose figures are stale by definition, and a reader
cannot tell the two cases apart.

### Availability and response time over a window

The classic monthly export, and the one that most needs its time bound to be a parameter.

```sql
SELECT
    n.NodeID,
    n.Caption,
    n.IPAddress,
    Round(Avg(rt.Availability), 3) AS AvgAvailabilityPct,
    Round(Avg(rt.AvgResponseTime), 1) AS AvgResponseMs,
    Max(rt.MaxResponseTime) AS WorstResponseMs
FROM Orion.ResponseTime rt
JOIN Orion.Nodes n ON rt.NodeID = n.NodeID
WHERE rt.DateTime >= @start
  AND rt.DateTime <  @end
GROUP BY n.NodeID, n.Caption, n.IPAddress
ORDER BY n.NodeID
WITH ROWS 1 TO 500 WITH TOTALROWS
```

`Orion.ResponseTime` descends from `System.StatisticsEntity` and is one of the largest tables
on the system, so the `WHERE` clause is not optional. `>= @start AND < @end` is a half-open
interval, which means consecutive monthly runs neither overlap nor leave a gap. In PowerShell:
`@{ start = (Get-Date).AddMonths(-1); end = (Get-Date) }`.

The `GROUP BY` includes `NodeID` so the `ORDER BY` can use it, which keeps the paging stable
even when two nodes share a caption.

### Alert volume by definition

What actually fired last month, most frequent first. This is what drives alert tuning, because
the top few rows are almost always the noisy definitions.

```sql
SELECT
    ah.AlertObjects.AlertConfigurations.Name AS AlertName,
    ah.AlertObjects.AlertConfigurations.Severity AS Severity,
    COUNT(ah.AlertHistoryID) AS Triggers,
    MIN(ah.TimeStamp) AS FirstFiredUtc,
    MAX(ah.TimeStamp) AS LastFiredUtc
FROM Orion.AlertHistory ah
WHERE ah.EventType = 0
  AND ah.TimeStamp >= @startUtc
  AND ah.TimeStamp <  @endUtc
GROUP BY ah.AlertObjects.AlertConfigurations.Name,
         ah.AlertObjects.AlertConfigurations.Severity
ORDER BY COUNT(ah.AlertHistoryID) DESC
```

`EventType = 0` is "triggered"; the other values cover reset, acknowledge and action outcomes,
and including them turns a count of incidents into a count of activity. The value table is in
[alerts.md](alerts.md). The parameters are named for UTC because that is the usual answer, but
`ah.TimeStamp` carries **no documented timezone** in the schema and its name does not end in
`Utc`, so this is unverified here: settle it on your own server with the `MinuteDiff` probe in
[alerts.md](alerts.md#the-timezone-caveat-on-timestamp) before trusting a month boundary, and
drop the `Utc` suffixes if the column turns out to be server-local.

### Estate summary by polling engine

A one-page summary rather than a row per object, which is usually what a management audience
wants.

```sql
SELECT
    e.ServerName AS PollingEngine,
    COUNT(n.NodeID) AS Nodes,
    SUM(CASE WHEN n.Status = 2 THEN 1 ELSE 0 END) AS DownNodes,
    SUM(CASE WHEN n.UnManaged = TRUE THEN 1 ELSE 0 END) AS UnmanagedNodes
FROM Orion.Nodes n
JOIN Orion.Engines e ON n.EngineID = e.EngineID
GROUP BY e.ServerName
ORDER BY COUNT(n.NodeID) DESC
```

`SUM(CASE WHEN ... THEN 1 ELSE 0 END)` is how you get several conditional counts in one pass
instead of one query per condition. Status `2` is Down; see
[../reference/status-codes.md](../reference/status-codes.md).

### The report inventory itself

Before adding a report, find out what already exists. `Owner` and `Category` are the columns
that tell you whether a report is maintained or abandoned.

```sql
SELECT
    r.ReportID,
    r.Name,
    r.Title,
    r.Category,
    r.Type,
    r.Owner,
    r.LimitationCategory,
    r.LastRenderDuration
FROM Orion.Report r
ORDER BY r.Category, r.Name
```

`LastRenderDuration` is the column to reach for when the console feels slow: a report that takes
minutes to render is running an expensive query on every view. The schema types it
`System.String` rather than a number or an interval, and what that string contains is not
recorded and is unverified here, so read a few values before you sort on it and expect
lexicographic order rather than numeric if you do.

### What is scheduled, and when

Which jobs exist, which reports each renders, and on what recurrence. Three entities, because
the platform normalises the relationship.

```sql
SELECT
    j.Name AS JobName,
    j.Enabled,
    j.AccountID,
    r.ReportID,
    r.Name AS ReportName,
    r.Title
FROM Orion.ReportJobDefinitions d
JOIN Orion.ReportJobs j ON d.ReportJobID = j.ReportJobID
JOIN Orion.Report r ON d.ReportID = r.ReportID
ORDER BY j.Name, r.Name
```

```sql
SELECT
    j.Name AS JobName,
    j.Enabled,
    f.DisplayName AS Frequency,
    f.CronExpression,
    f.TimeZoneDisplayName,
    j.LastRun
FROM Orion.ReportSchedules s
JOIN Orion.ReportJobs j ON s.ReportJobID = j.ReportJobID
JOIN Orion.Frequencies f ON s.FrequencyID = f.FrequencyID
ORDER BY j.Name
```

`j.AccountID` is the important column in the first query and the reason the second one matters.
A scheduled report renders **as that account**, so its account limitations decide what the
recipients see. A job owned by a departed employee whose account was limited to one site will
quietly deliver a one-site view to a company-wide distribution list.

`f.CronExpression` together with `f.TimeZoneDisplayName` is the readable answer to "when does
this actually run", which is otherwise buried in `j.SchedulesData` as an opaque string.

### Jobs that are disabled or have never run

A scheduled delivery that silently stopped looks exactly like one that was never needed.

```sql
SELECT
    j.ReportJobID,
    j.Name,
    j.Enabled,
    j.AccountID,
    j.LastRun,
    j.FrequencyTitle,
    j.ReportTitles
FROM Orion.ReportJobs j
WHERE j.Enabled = FALSE
   OR j.LastRun IS NULL
ORDER BY j.Name
```

`ReportTitles`, `FrequencyTitle` and `ActionTitles` are pre-rendered display strings, which
makes them convenient for a human-readable export even though the structured answer comes from
the joins above.

## Gotchas

**An empty export is usually a permissions result, not a query result.** Account limitations
filter silently. Check the account before the query, every time.

**Paging without a total order repeats or skips rows.** Order by a key. A caption is not a key.

**`WITH TOTALROWS` is a count over the unwindowed result.** Ask for it once, on the first page.

**`Get-SwisData` does not expose `totalRows`.** It returns rows, not the envelope. Use a
separate `COUNT` query, or go through REST if you need the envelope.

**`Orion.Report.Definition` is opaque here.** Read it to find reports that reference an entity;
do not write it from a script.

**`ExecuteSQL` is raw T-SQL and needs `admin`.** It bypasses SWQL entirely, and the physical
schema it queries is not a contract across releases.

**A scheduled report runs as its owning account.** Changing that account's limitations changes
what it delivers with no other visible cause.

**Report jobs and scheduled tasks are separate lists.** Check both when you want to know
everything that runs unattended. See [scheduling.md](scheduling.md).

**Empty result sets produce headerless CSV files in PowerShell.** `Export-Csv` derives the
header from the first object, so a downstream consumer that expects a header on every run needs
either the exit-code path from the worked example or an explicit header written when the set is
empty.

## See also

- [scheduling.md](scheduling.md) for `Orion.ScheduleTaskDefinition` and maintenance plans
- [accounts-and-permissions.md](accounts-and-permissions.md) for account limitations, which
  decide what any export contains
- [alerts.md](alerts.md) for alert history and its `EventType` values
- [custom-properties.md](custom-properties.md) for grouping output by your own metadata
- [../swql/performance.md](../swql/performance.md) for bounding, paging and aggregation
- [../swql/date-and-time.md](../swql/date-and-time.md) for time-bounding correctly
- [../swis/rest-api.md](../swis/rest-api.md) for the response envelope `totalRows` lives in
- [`Export-OrionInventory.ps1`](../../scripts/powershell/Export-OrionInventory.ps1) and
  [`swis_client.py`](../../scripts/python/swis_client.py) for runnable versions

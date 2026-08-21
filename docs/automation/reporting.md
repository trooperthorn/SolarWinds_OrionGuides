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

The client used here is [`swis_client.py`](../../scripts/python/swis_client.py) in this
repository, whose `query()` returns the whole envelope rather than just the rows, which is
precisely what makes `totalRows` reachable. The official `orionsdk` package is the one to use
in production.

# Scheduled tasks and maintenance plans

Two related capabilities let the platform do something later without anyone driving it:
**scheduled tasks**, which run an action on a recurring frequency, and **maintenance
plans**, which open a maintenance window at a planned time.

Both matter for automation, and for a reason that is easy to miss. If you are writing a
script that unmanages nodes before a change window and remanages them afterwards, the
platform may already be doing that on a plan, and the two will fight. Check before you
build.

## The entities

| Entity | Holds | Size |
| --- | --- | --- |
| `Orion.ScheduleTaskDefinition` | One scheduled task: name, frequency, enabled flag, last and next run | 12 properties |
| `Orion.ScheduleEntityAssignment` | What each task acts on, by URI or by a dynamic expression | 6 properties |
| `Orion.Frequencies` | The recurrence itself, including a cron expression | 14 properties, 3 verbs |
| `Orion.MaintenancePlan` | A planned unmanage window with a start, an end, and a reason | 9 properties |
| `Orion.MaintenancePlanAssignment` | Which objects a maintenance plan covers | 6 properties |

Only `Orion.Frequencies` declares verbs, and they exist for a reason covered below. For the
other four, everything is done through CRUD, which means you need the URI of the row you are
changing. See [../swis/crud.md](../swis/crud.md).

Access control differs across them in ways worth reading before you automate:

| Entity | Read | Write | Invoke |
| --- | --- | --- | --- |
| `Orion.ScheduleTaskDefinition` | `allowUnmanage`, `manageNodes`, `admin` | same three | `admin` only |
| `Orion.ScheduleEntityAssignment` | `allowUnmanage`, `manageNodes`, `admin` | same three | same three |
| `Orion.MaintenancePlan` | `everyone` | `allowUnmanage` | not declared |
| `Orion.MaintenancePlanAssignment` | `everyone` | `allowUnmanage` | not declared |

Two asymmetries follow from that table. `Orion.ScheduleTaskDefinition` reserves `invoke` for
`admin` while the assignment entity beside it does not, so the rights an account needs depend
on which end of the pair it touches. And the maintenance plan entities declare no `invoke`
at all while granting read to `everyone`: any authenticated account can see the whole
maintenance schedule, and changing it needs `allowUnmanage` and nothing else. Verify on your
own version:

```bash
python3 tools/schema_query.py show Orion.ScheduleTaskDefinition
```

`Private` on `Orion.ScheduleTaskDefinition` is the one property whose absence from a query
tends to surprise. It is a `System.Boolean` and it is about visibility in the console rather
than about whether the task runs; a private task belonging to a departed administrator runs
exactly as before and is harder to find. Select it when auditing.

## What is scheduled right now

The first query to run, and the one that answers "is something already doing this":

```sql
SELECT
    t.ScheduleTaskID,
    t.Name,
    t.Description,
    t.ScheduleType,
    t.Enabled,
    t.LastRun,
    t.NextRun,
    t.LastRunResult,
    t.AccountID
FROM Orion.ScheduleTaskDefinition t
ORDER BY t.NextRun
```

`ScheduleType` distinguishes what kind of work the task does. `LastRunResult` is the
outcome of the previous run, and it is the column to check when a task exists but nothing
seems to happen.

## Tasks that are failing or disabled

A scheduled task that is switched off looks identical to one that never existed, from the
point of view of the work not getting done:

```sql
SELECT
    t.Name,
    t.ScheduleType,
    t.Enabled,
    t.LastRun,
    t.LastRunResult,
    t.Reason
FROM Orion.ScheduleTaskDefinition t
WHERE t.Enabled = FALSE
   OR t.LastRunResult <> 'Success'
ORDER BY t.LastRun DESC
```

Tasks that should have run and did not:

```sql
SELECT
    t.Name,
    t.NextRun,
    t.LastRun,
    t.Enabled,
    MinuteDiff(t.NextRun, GetDate()) AS MinutesOverdue
FROM Orion.ScheduleTaskDefinition t
WHERE t.Enabled = TRUE
  AND t.NextRun < GetDate()
ORDER BY t.NextRun
```

## What a task acts on

Assignments name their target either as a specific URI or as an expression that resolves
to a set at run time. The distinction matters: a URI assignment covers exactly one object
forever, and an expression picks up new objects as they appear.

```sql
SELECT
    a.EntityAssignmentID,
    a.ScheduleTask.Name AS TaskName,
    a.EntityType,
    a.EntityUri,
    a.Expression,
    a.AssignedBy
FROM Orion.ScheduleEntityAssignment a
ORDER BY a.ScheduleTask.Name
```

Assignments for one named task, walking from the task side:

```sql
SELECT
    t.Name AS TaskName,
    t.Assignments.EntityType,
    t.Assignments.EntityUri,
    t.Assignments.Expression
FROM Orion.ScheduleTaskDefinition t
WHERE t.Name = @taskName
```

## The recurrence

`Orion.Frequencies` carries the actual schedule, including a cron expression, which is
the readable form of "when does this run":

```sql
SELECT
    f.FrequencyID,
    f.DisplayName,
    f.Description,
    f.CronExpression,
    f.Duration,
    f.StartTime,
    f.EndTime,
    f.EnabledDuringTimePeriod
FROM Orion.Frequencies f
ORDER BY f.DisplayName
```

Joining a task to its frequency gives the complete picture in one row:

```sql
SELECT
    t.Name AS TaskName,
    t.Enabled,
    f.DisplayName AS Frequency,
    f.CronExpression,
    t.NextRun
FROM Orion.ScheduleTaskDefinition t
JOIN Orion.Frequencies f ON t.FrequencyID = f.FrequencyID
ORDER BY t.NextRun
```

Note that this is an id join and has to be. `Orion.Frequencies` declares **no relationships
in either direction**, to anything, so there is no navigation property to reach it by. Every
path into the frequency table is an explicit `FrequencyID` comparison, and a `LEFT JOIN` is
the honest form if you want to see tasks whose frequency row has gone missing.

### A cron expression without its timezone is ambiguous

Six of the fourteen `Orion.Frequencies` columns are not in the query above, and half of them
are about time zones. This matters more than it looks: `CronExpression` says `0 2 * * *` and
nothing about which 2 a.m. that is.

| Property | Type | What it is |
| --- | --- | --- |
| `CronExpressionTimeZoneInfo` | `System.String` | The timezone the cron expression is evaluated in |
| `TimeZoneDisplayName` | `System.String` | That timezone in human-readable form |
| `UtcOffsetInMinutes` | `System.Double` | The offset, in minutes |
| `FrequencyStartTime` | `System.DateTime` | Start of the window the frequency is valid for |
| `FrequencyEndTime` | `System.DateTime` | End of that window |
| `ScheduleCondition` | `System.String` | An additional condition on the schedule |

Select them when you are reconciling a schedule against a change window, or against a
schedule kept in another system:

```sql
SELECT
    f.DisplayName,
    f.CronExpression,
    f.CronExpressionTimeZoneInfo,
    f.TimeZoneDisplayName,
    f.UtcOffsetInMinutes,
    f.FrequencyStartTime,
    f.FrequencyEndTime
FROM Orion.Frequencies f
ORDER BY f.DisplayName
```

`UtcOffsetInMinutes` is a `System.Double` and in minutes rather than hours, which covers the
half-hour and forty-five-minute offsets that exist and catch integer-typed assumptions. Note
also that an offset is a fixed number while a named timezone observes daylight saving, so the
two columns disagree for half the year in most zones — `CronExpressionTimeZoneInfo` is the
one that determines when the job actually fires. What `ScheduleCondition` may contain is
**not recorded in the published schema** and is unverified here.

### Frequencies are shared, which is why they have verbs

`Orion.Frequencies` is the one table both scheduling mechanisms use. Report delivery reaches
it through `Orion.ReportSchedules`, a two-column link table of `FrequencyID` and
`ReportJobID`; the generic task framework reaches it through `Orion.ScheduleTaskDefinition.FrequencyID`.
See [reporting.md](reporting.md#report-schedules-are-not-orionscheduletaskdefinition) for why
the two mechanisms are otherwise separate.

That sharing is why this entity, alone among the five, declares verbs — and why they are
split by which kind of schedule you are writing:

| Verb | Argument | Requires |
| --- | --- | --- |
| `SaveReportFrequencies` | `array<SolarWinds.Orion.Core.Common.Models.ReportSchedule>` | `manageReports` or `admin` |
| `SaveTimePeriodFrequencies` | `array<SolarWinds.Orion.Core.Models.Schedules.TimePeriodSchedule>` | `manageAlerts` or `admin` |
| `DeleteFrequencies` | `array<number>` of frequency ids | `manageAlerts`, `manageReports` or `admin` |

Each takes exactly one array argument, and both `Save` verbs return an array while
`DeleteFrequencies` returns a boolean:

```bash
python3 tools/schema_query.py verb Orion.Frequencies SaveReportFrequencies
```

The two payload types explain the shape of the table. `ReportSchedule` carries
`DisplayName`, `CronExpression`, `CronExpressionTimeZoneInfo`, `CronExpressionTimeZoneInfoId`,
`FrequencyId`, `StartTime` and `EndTime`. `TimePeriodSchedule` carries all seven of those plus
`Duration`, `EnabledDuringTimePeriod` and `ScheduleCondition`. The fourteen columns of
`Orion.Frequencies` are the union of the two, which is why a row written by one mechanism
leaves some of them empty.

Read the rights column before automating. An account with `manageReports` can write report
frequencies and delete any frequency, including one an alert depends on — `DeleteFrequencies`
takes bare ids and does not distinguish what created them. Delete only ids you have just
selected and confirmed:

```sql
SELECT f.FrequencyID, f.DisplayName, f.CronExpression
FROM Orion.Frequencies f
WHERE f.FrequencyID NOT IN (
    SELECT t.FrequencyID FROM Orion.ScheduleTaskDefinition t
)
ORDER BY f.DisplayName
```

Frequencies that no scheduled task references are candidates for cleanup, but that query
alone is **not sufficient evidence** to delete one: a report job can reference the same row
through `Orion.ReportSchedules`, so check both before removing anything.

## Maintenance plans

A maintenance plan is a scheduled unmanage. It does what
[maintenance-mode.md](maintenance-mode.md) describes doing by hand, on a plan, which is
why it is the thing to check before writing a script that unmanages on a schedule.

```sql
SELECT
    m.ID,
    m.Name,
    m.Reason,
    m.Enabled,
    m.UnmanageDate,
    m.RemanageDate,
    m.KeepPolling,
    m.AccountID
FROM Orion.MaintenancePlan m
ORDER BY m.UnmanageDate
```

`KeepPolling` is the property worth understanding. A plan that keeps polling suppresses
alerting but continues collecting data, so the graphs have no gap. One that does not stops
polling entirely, which is cheaper but leaves a hole in the history.

Plans that are about to take effect:

```sql
SELECT
    m.Name,
    m.Reason,
    m.UnmanageDate,
    m.RemanageDate,
    HourDiff(GetDate(), m.UnmanageDate) AS HoursUntilStart
FROM Orion.MaintenancePlan m
WHERE m.Enabled = TRUE
  AND m.UnmanageDate > GetDate()
ORDER BY m.UnmanageDate
```

Plans that have started and not yet ended, which explains objects that are unmanaged
without anyone remembering doing it:

```sql
SELECT
    m.Name,
    m.Reason,
    m.UnmanageDate,
    m.RemanageDate,
    m.KeepPolling
FROM Orion.MaintenancePlan m
WHERE m.Enabled = TRUE
  AND m.UnmanageDate <= GetDate()
  AND m.RemanageDate >= GetDate()
ORDER BY m.RemanageDate
```

What a plan covers:

```sql
SELECT
    a.MaintenancePlanID,
    a.EntityUri,
    a.EntityType,
    a.Enabled
FROM Orion.MaintenancePlanAssignment a
ORDER BY a.MaintenancePlanID
```

`Enabled` is on the assignment as well as on the plan, and that is the trap. A plan can be
enabled, in date, and visible in the console while every one of its assignments is switched
off, in which case it covers nothing and looks exactly like a plan that is working. Check the
two together rather than trusting the plan's own flag:

```sql
SELECT
    m.Name,
    m.Enabled AS PlanEnabled,
    COUNT(a.ID) AS Assignments,
    SUM(CASE WHEN a.Enabled = TRUE THEN 1 ELSE 0 END) AS EnabledAssignments
FROM Orion.MaintenancePlan m
LEFT JOIN Orion.MaintenancePlanAssignment a ON a.MaintenancePlanID = m.ID
GROUP BY m.Name, m.Enabled
ORDER BY m.Name
```

A row with `PlanEnabled = TRUE` and `EnabledAssignments` at zero is a plan that will do
nothing when its window opens. The `LEFT JOIN` matters: a plan with no assignments at all is
the same failure and an inner join hides it.

Both directions navigate, so you can also walk from the plan without an id join —
`Assignments` from `Orion.MaintenancePlan`, and `Plan` back from the assignment:

```sql
SELECT
    a.EntityType,
    a.EntityUri,
    a.Enabled,
    a.Plan.Name,
    a.Plan.UnmanageDate,
    a.Plan.RemanageDate
FROM Orion.MaintenancePlanAssignment a
WHERE a.Plan.Enabled = TRUE
ORDER BY a.Plan.UnmanageDate
```

`Orion.MaintenancePlanAssignment` also carries `EntityID` alongside `EntityUri`, the same
decomposed-and-canonical pairing that `Orion.Dependencies` uses. Filter on `EntityID` with
`EntityType`; build with `EntityUri`. See [dependencies.md](dependencies.md).

## Before you automate a schedule of your own

**Look for an existing plan first.** Unmanaging on a schedule from a script, while a
maintenance plan covers the same objects, produces overlapping windows. `Unmanage` takes
an `allowOverlapping` flag precisely because overlap is a real situation, but two systems
managing the same window is a source of objects that stay unmanaged after the change
finishes.

**Prefer the platform's own scheduling where it fits.** A maintenance plan survives a
restart of whatever host your script runs on, appears in the web console where an operator
can see it, and is recorded against an account in the audit trail. A cron job on a jump
box has none of those properties.

**Reach for a script when the trigger is external.** A plan runs on a clock. If the window
should open when a change ticket moves to In Progress, the trigger lives in the ticketing
system and the script is the right answer. Use
[maintenance-mode.md](maintenance-mode.md) for the verb call.

**Check `LastRunResult` in monitoring.** A scheduled task that quietly starts failing is
invisible until someone notices the work is not being done. It is worth alerting on.

## See also

- [maintenance-mode.md](maintenance-mode.md) for unmanaging directly through verbs
- [reporting.md](reporting.md) for scheduled report delivery
- [../swis/crud.md](../swis/crud.md) for creating and updating these entities
- [../swis/uris.md](../swis/uris.md) for the URIs assignments reference

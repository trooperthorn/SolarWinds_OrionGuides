# Scheduled tasks and maintenance plans

Two related capabilities let the platform do something later without anyone driving it:
**scheduled tasks**, which run an action on a recurring frequency, and **maintenance
plans**, which open a maintenance window at a planned time.

Both matter for automation, and for a reason that is easy to miss. If you are writing a
script that unmanages nodes before a change window and remanages them afterwards, the
platform may already be doing that on a plan, and the two will fight. Check before you
build.

## The entities

| Entity | Holds |
| --- | --- |
| `Orion.ScheduleTaskDefinition` | One scheduled task: name, frequency, enabled flag, last and next run |
| `Orion.ScheduleEntityAssignment` | What each task acts on, by URI or by a dynamic expression |
| `Orion.Frequencies` | The recurrence itself, including a cron expression |
| `Orion.MaintenancePlan` | A planned unmanage window with a start, an end, and a reason |
| `Orion.MaintenancePlanAssignment` | Which objects a maintenance plan covers |

None of these declare verbs. Everything is done through CRUD, which means you need the
URI of the row you are changing. See [../swis/crud.md](../swis/crud.md).

Access control is worth reading before you automate against them.
`Orion.ScheduleTaskDefinition` grants create, read, update and delete to `allowUnmanage`
and to `manageNodes`, but reserves `invoke` for `admin`. Verify on your own version:

```bash
python3 tools/schema_query.py show Orion.ScheduleTaskDefinition
```

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
    a.EntityType
FROM Orion.MaintenancePlanAssignment a
ORDER BY a.MaintenancePlanID
```

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

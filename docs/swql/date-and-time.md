# SWQL date and time

A date query has three separate concerns: the column's time basis, arithmetic used for
the filter, and how the returned timestamp is serialized or displayed. Check each before
changing a query because its chart appears several hours off.

## The short version

1. Establish the queried column's time basis. `System.DateTime` alone does not declare UTC.
2. Keep filtering and presentation separate. A local hour label is not a chronological key.
3. SolarWinds documents an offset problem when selecting `AddX(..., GetUtcDate())`.
   Its suggested workaround is local arithmetic followed by `ToUtc`.
4. For an exact elapsed interval, prefer fixed UTC start/end parameters calculated by
   a timezone-aware client. Local calendar arithmetic can cross a daylight-saving change.
5. Aggregate with `DateTrunc` or `Downsample`; retain a full bucket timestamp for sorting.
6. Apply the window to the timestamp column directly and bound the result size.

## How a SWQL date query actually runs

The SDK's [date-function issue](https://solarwinds.github.io/OrionSDK/docs/swql-functions/possible-issues/)
shows a SWQL query translated into T-SQL, followed by serialization to the client.
That example is evidence about its execution path, not every module's query provider.

## The trap: `GetUtcDate()` plus `AddX`

The published example returns `GetUtcDate()` with `Z`, but calculated `AddX` columns
with the SQL Server's local offset. A client interpreting that offset reads a different
instant. This is a demonstrated **selected-value serialization problem**. It does not
by itself prove that a `WHERE` comparison inside the server selects the wrong rows.
The issue page does not identify all affected or fixed product versions.

## The fix: convert, add, convert back

SolarWinds recommends the following selected-value pattern:

```sql
SELECT TOP 1
    GetUtcDate() AS UtcNow,
    ToUtc(AddMinute(-10, ToLocal(GetUtcDate()))) AS EarlierUtc
FROM Orion.Engines
```

### The shorter equivalent

The same source also recommends using `GetDate()` before the arithmetic:

```sql
SELECT TOP 1
    ToUtc(AddMinute(-10, GetDate())) AS EarlierUtc
FROM Orion.Engines
```

Treat this as the documented serialization workaround. It is not a guarantee that
subtracting one local calendar day always means 24 elapsed hours. Test the server's
local conversions around daylight-saving transitions before relying on that equivalence.

### Where the trap does not reach

**Unverified:** whether the selected-value issue also affects a particular server-side
predicate. The source demonstrates the select list, not a filtered result set.

To investigate, fix one instant and compare event IDs and boundary timestamps using
client-supplied UTC parameters against the candidate expression. Capture raw responses,
server/client timezones, release, and rows near both boundaries. Equal counts alone do
not establish equivalence: two different windows can contain the same number of rows.
Avoid testing against a moving `now` across separate queries.

## The four functions that read or move the clock

| Function | Returns | Notes |
|:---|:---|:---|
| `GetDate()` | Current server-local time | Official reference derives it from SQL Server timezone settings; do not assume browser time |
| `GetUtcDate()` | Current time in **UTC** | The official reference attaches an explicit warning to this one |
| `ToLocal(d)` | `d` converted to server-local time | Confirm the observed offset when database and application servers use different zones |
| `ToUtc(d)` | `d` converted to **UTC** | The outbound half of the fix |

The four runs recorded in the community workbook were made minutes apart on one server, and
together they show the shape clearly:

```sql
SELECT TOP 1
    GetDate()             AS ServerLocalNow,
    GetUtcDate()          AS UtcNow,
    ToLocal(GetUtcDate()) AS UtcConvertedToLocal,
    ToUtc(GetDate())      AS LocalConvertedToUtc
FROM Orion.Engines
```

The recorded values were `2015-09-25 08:52:35` for `GetDate()`, `2015-09-25 15:53:49` for
`GetUtcDate()`, `9/25/2015 8:50:37 AM` for `ToLocal(GetUtcDate())` and `2015-09-25 15:49:54`
for `ToUtc(GetDate())`. The local pair and the UTC pair each agree with one another to within
the few minutes between runs, and the gap between the pairs is about seven hours, which is
what that server's offset was. Running that one query on your own server tells you your
offset immediately, and it is worth doing before you write anything time sensitive.

## Which columns are UTC and which are local

**Do not infer storage or query semantics from the type alone.** A practitioner reports
that most platform timestamps are UTC. Treat that as a working hypothesis for an
undocumented column, not a verified property of every provider.

*Source: reported from practice by a long-time SolarWinds administrator.*

That is the prior to start from, and it changes what the naming means. There is no flag in the
schema that says "this column is UTC", and:

- **1301 properties** in the 2026.2 schema are typed `System.DateTime`.
- **128 of them have `Utc` in the property name** — `Orion.AuditingEvents.TimeLoggedUtc`,
  `Orion.Nodes.LastSystemUpTimePollUtc`, `Orion.APM.WindowsEvent.TimeGeneratedUtc`,
  `Orion.CPUMultiLoad.TimeStampUTC`. The suffix is evidence of UTC intent; its absence does not establish local time
  for the other 1173 properties.
- **Nine of them say UTC in their description**, and for six of those the name does not, so
  the description is the only signal you get. `Orion.VIM.TriggeredAlarmState.Timestamp` is
  one: "The timestamp in UTC indicating when the alarm was fired."
- **One of the most queried date columns documents itself as local.**
  `Orion.Events.EventTime` is described as "Date and time when the event occurred, displayed
  in local time."

Everything else carries no statement either way — `Orion.Nodes.LastBoot`,
`Orion.Nodes.NextPoll`, `Orion.Engines.KeepAlive`, `Orion.AlertActive.TriggeredDateTime`,
`Orion.CPULoad.DateTime`. Their time basis is **unverified here** unless a feature-specific
source establishes it. Many repository examples assume UTC: SolarWinds' own NetPath query carries the
comment *"ExecutedAt is stored in UTC, so we use `GETUTCDATE() - 1` to get last 24 hours only"*
for a column whose name says nothing.

**The exception is the one the schema names.** `Orion.Events.EventTime` documents itself as
local, and it is one of the most queried date columns in the product — see
[the tension below](#the-eventtime-exception).

Measurement is still worth the minute it costs when a query's window looks wrong, because
"almost always" is not "always" and a wrong assumption here is silent.

### The `EventTime` exception

`Orion.Events.EventTime` is described in the schema as *"Date and time when the event occurred,
**displayed in local time**"*. That is the one column the schema explicitly sets against the
UTC rule, and it is heavily queried, so it deserves care rather than a ruling.

**The word to notice is "displayed".** A value stored in UTC and rendered in local time is
consistent with the practitioner observation, and would make the description a statement about
presentation rather than storage. A value genuinely stored in server-local time is the other
reading, and would make this a real exception.

This repository cannot tell the two apart from the contract, so **the tension is left open
rather than resolved**. What is safe either way:

- **Measure it before you build a time-bounded event query.** The technique below settles it in
  a minute on your own server, and the answer is the one that matters.
- **A window that is off by exactly your UTC offset** is the symptom, and it is the reason this
  column is worth checking rather than assuming.

If your measurement shows `EventTime` behaving as UTC like everything else, the schema
description is about rendering and there is no exception at all. That is the outcome the
practitioner rule predicts, and it would be worth reporting.

### Measuring a column's timezone

Pick a column that is being written continuously right now. `Orion.Engines.KeepAlive` is
ideal: every polling engine updates it constantly, so "now" is the correct answer for it.

```sql
SELECT TOP 1
    e.ServerName,
    e.KeepAlive,
    e.MinutesSinceKeepAlive,
    MinuteDiff(e.KeepAlive, GetDate())    AS MinutesBehindLocalNow,
    MinuteDiff(e.KeepAlive, GetUtcDate()) AS MinutesBehindUtcNow
FROM Orion.Engines e
WHERE e.ServerType = 'Primary'
```

A near-zero difference suggests the queried value uses that clock; it does not prove the
physical database storage format. A stale poll, clock skew, a UTC-configured server, or a
provider conversion can make the comparison inconclusive. Compare a known event instant
and inspect the raw API timestamp as well as the UI.
When the probe is conclusive, the other difference should reflect the local offset.
`MinutesSinceKeepAlive` supplies additional context, but it does not prove the storage
representation or validate timestamps on unrelated entities.

For a column that is not continuously updated, cause a write you can time yourself. Acknowledge
an event, unmanage and remanage a test node, or trigger a test alert, then look at the
timestamp the action produced and compare it with what your watch said.

## The `AddX` family

Nine functions, and for eight of them one shape: **the count comes first, the date second**.
`AddDay(7, d)` means "seven days after `d`". A negative count subtracts, and subtracting is
what nearly every real query does. `AddDate` is the exception, taking the unit name in front
of the count.

| Function | Adds |
|:---|:---|
| `AddMillisecond(n, d)` | milliseconds |
| `AddSecond(n, d)` | seconds |
| `AddMinute(n, d)` | minutes |
| `AddHour(n, d)` | hours |
| `AddDay(n, d)` | days |
| `AddWeek(n, d)` | weeks |
| `AddMonth(n, d)` | months |
| `AddYear(n, d)` | years |
| `AddDate(u, n, d)` | the unit named by `u` |

`AddDate` takes the unit as its first argument, one of `'millisecond'`, `'second'`,
`'minute'`, `'hour'`, `'day'`, `'week'`, `'month'` or `'year'`. Two constraints on it:

- **`u` must be a string literal.** The official reference is explicit: "It can't be a query
  parameter or value derived from the data." If you wanted a report where the user picks the
  unit, you have to build the query text, not bind a parameter.
- **There is no `'quarter'` unit**, even though `DateTrunc` accepts `'quarter'` as a
  datepart. Add three months.

```sql
SELECT TOP 1
    KeepAlive,
    AddDate('month', 2, KeepAlive) AS TwoMonthsOn,
    AddMonth(2, KeepAlive)         AS AlsoTwoMonthsOn,
    AddMonth(-3, KeepAlive)        AS OneQuarterBack
FROM Orion.Engines
```

Month and year arithmetic clamps rather than overflowing, in the usual calendar way: adding
one month to 31 January cannot produce 31 February. This follows from `DATEADD`, and it is
worth remembering when a monthly report silently shifts by a day or three near month end.

### Integer addition adds days

**Attested, not documented.** Several workbook examples add a bare integer to a `DateTime`,
as in `KeepAlive + 28`, and the recorded results are all consistent with the integer meaning
whole days:

| Recorded query | Recorded result | Consistent with |
|:---|---:|:---|
| `DayDiff(KeepAlive, KeepAlive+28)` | 28 | 28 days |
| `WeekDiff(KeepAlive, KeepAlive+28)` | 4 | 28 days |
| `HourDiff(KeepAlive, KeepAlive+28)` | 672 | 28 x 24 |
| `MinuteDiff(KeepAlive, KeepAlive+28)` | 40320 | 28 x 1440 |
| `MillisecondDiff(KeepAlive, KeepAlive+24)` | 2073600000 | 24 x 86400000 |

That is the T-SQL `datetime` behaviour showing through, and five independent results agreeing
is decent evidence. It is still not in the official function reference, so do not put it in
anything you have to maintain. `AddDay(28, KeepAlive)` says what it means, survives a reader
who does not know the trick, and is documented.

## The `XDiff` family

Eight functions, all of the form `XDiff(a, b)`: **how much later `b` is than `a`**, rounded
to the nearest whole unit. The order is the opposite of subtraction, so
`DayDiff(earlier, later)` is positive.

| Function | Unit |
|:---|:---|
| `MillisecondDiff(a, b)` | milliseconds |
| `SecondDiff(a, b)` | seconds |
| `MinuteDiff(a, b)` | minutes |
| `HourDiff(a, b)` | hours |
| `DayDiff(a, b)` | days |
| `WeekDiff(a, b)` | weeks |
| `MonthDiff(a, b)` | months |
| `YearDiff(a, b)` | years |

Two things to watch.

**Rounding to a whole unit loses a lot.** The workbook's recorded results for a 28 day span
are `MonthDiff` = 1 and `WeekDiff` = 4. A span of 28 days is not one month and it is not
quite four weeks of anyone's calendar, but that is what whole-unit rounding gives you. When
the answer matters, difference in the smallest unit that fits and divide:

```sql
SELECT TOP 20
    n.Caption,
    n.LastBoot,
    DayDiff(n.LastBoot, GetDate())               AS WholeDaysUp,
    HourDiff(n.LastBoot, GetDate()) / 24.0       AS FractionalDaysUp
FROM Orion.Nodes n
WHERE n.LastBoot IS NOT NULL
ORDER BY WholeDaysUp DESC
```

**`MillisecondDiff` overflows at about 24.8 days.** The workbook notes 24 days as the maximum
usable span, and the arithmetic explains it: 24 days is 2,073,600,000 ms and the largest
32-bit signed integer is 2,147,483,647, so 25 days (2,160,000,000 ms) does not fit. Use
`SecondDiff` and multiply if you need a wider range at millisecond precision.

Both operands need to be on the same clock. `DayDiff(SomeUtcColumn, GetDate())` mixes UTC
with local and is wrong by your offset. Convert one side first.

## `DateTrunc` and its dateparts

`DateTrunc('datepart', d)` returns `d` with everything finer than `datepart` zeroed. It is the
function that makes time-series grouping possible, because grouping on a raw timestamp
produces one group per row.

```sql
SELECT TOP 1 DateTrunc('month', KeepAlive) AS ColumnResult
FROM Orion.Engines
```

**Result:** `2015-09-01 00:00:00`

### Supported dateparts

| Datepart | Status |
|:---|:---|
| `'minute'` | Documented |
| `'hour'` | Documented |
| `'day'` | Documented |
| `'week'` | Documented |
| `'month'` | Documented |
| `'quarter'` | Documented |
| `'year'` | Documented |
| `'dayofyear'` | **Attested, not documented.** Listed in the workbook's note but absent from the official reference |
| `'second'` | **Not supported.** Stated explicitly in the workbook's note |
| `'millisecond'` | **Not supported.** Stated explicitly in the workbook's note |

The two unsupported ones are the interesting entries. If you want per-second or
sub-second buckets, `DateTrunc` cannot give them to you and
[`Downsample`](#downsample-for-arbitrary-buckets) is the function to reach for. If you were
about to truncate to the second in order to join two tables on a timestamp, join on something
else; timestamp equality across tables is fragile in any case.

`DateTrunc('week', d)` inherits `SET DATEFIRST 7` from the generated T-SQL, so weeks start on
Sunday.

### Grouping by day, correctly

```sql
SELECT
    DateTrunc('day', e.EventTime) AS EventDay,
    Count(e.EventID)              AS Events
FROM Orion.Events e
WHERE e.EventTime >= AddDay(-30, GetDate())
GROUP BY DateTrunc('day', e.EventTime)
ORDER BY EventDay
```

This example assumes that the queried `EventTime` uses local time. Confirm that assumption
as described above; its schema description concerns display. Match the bound to the
time basis observed on the target provider.

Repeating the `DateTrunc` expression in `GROUP BY` rather than naming the alias is the
portable form. Aliases in `GROUP BY` are not documented for SWQL.

## `Downsample` for arbitrary buckets

`Downsample(d, p)` rounds the timestamp `d` to the period `p`, so `'00:15:00'` gives 15
minute buckets. The official reference records it as requiring **Orion 2018.3 or later**.

No worked example or observed result is recorded for `Downsample` anywhere in the source data
for this documentation. The query below is constructed from the published signature and uses
verified schema names; confirm the bucket boundaries on your own version before you build a
report on it.

```sql
SELECT
    Downsample(rt.DateTime, '00:15:00') AS Bucket,
    Avg(rt.AvgResponseTime)             AS AvgResponseMs,
    Max(rt.MaxResponseTime)             AS PeakResponseMs
FROM Orion.ResponseTime rt
WHERE rt.NodeID = 1
  AND rt.DateTime >= AddDay(-1, GetDate())
GROUP BY Downsample(rt.DateTime, '00:15:00')
ORDER BY Bucket
```

Choose between the two bucketing functions on granularity: `DateTrunc` gives you fixed
calendar boundaries at seven granularities, `Downsample` takes an arbitrary period string so
5 minute, 15 minute and 6 hour buckets are one argument apart. The statistics entities are
the usual targets, but check the timestamp column's name before you write the query rather
than assuming it is called `DateTime`. 236 entities inherit from `System.StatisticsEntity`
and only 19 of them declare a `DateTime` column. `Orion.ResponseTime`, `Orion.CPULoad` and
`Orion.NPM.InterfaceTraffic` are three of the 19; `Orion.CPUMultiLoad` is not, and calls its
timestamp `TimeStampUTC`.

## Relative time filtering

The examples below retain the historical "last 24 hours" headings for existing links,
but their `AddDay(-1, GetDate())` expression means a previous local calendar day. Around
a daylight-saving transition, that can differ from 24 elapsed hours. For exact elapsed
windows use [parameterised windows](#parameterised-windows) with UTC bounds calculated
outside SWQL. Confirm each column's time basis before selecting an example.

Leaving the column bare can help efficient filtering. Actual plans depend on the provider
and indexes; this repository has not measured a universal index-seek guarantee.

### Last 24 hours, column stored in local time

```sql
SELECT TOP 200
    e.EventTime,
    e.NetObjectValue,
    e.Message
FROM Orion.Events e
WHERE e.EventTime >= AddDay(-1, GetDate())
ORDER BY e.EventTime DESC
```

### Last 24 hours, column stored in UTC

```sql
SELECT TOP 200
    a.TimeLoggedUtc,
    a.AccountID,
    a.AuditEventMessage
FROM Orion.AuditingEvents a
WHERE a.TimeLoggedUtc >= ToUtc(AddDay(-1, GetDate()))
ORDER BY a.TimeLoggedUtc DESC
```

`ToUtc(AddDay(-1, GetDate()))` is the shape from
[the fix](#the-fix-convert-add-convert-back): take the local clock, do the arithmetic where
`DATEADD` expects to be, hand back UTC to compare against a UTC column.

### Last 7 days, grouped by day

```sql
SELECT
    DateTrunc('day', e.EventTime) AS EventDay,
    Count(e.EventID)              AS Events
FROM Orion.Events e
WHERE e.EventTime >= DateTrunc('day', AddDay(-7, GetDate()))
GROUP BY DateTrunc('day', e.EventTime)
ORDER BY EventDay
```

Note the `DateTrunc` around the lower bound as well as around the grouping key. Without it,
the oldest bucket starts partway through its day and reads low, which is how "Mondays are
quiet" gets into a report that runs every Monday afternoon.

### Today so far

```sql
SELECT
    Count(e.EventID) AS EventsToday
FROM Orion.Events e
WHERE e.EventTime >= DateTrunc('day', GetDate())
```

### A closed window: the previous full hour

Use a half-open interval, `>=` on the lower bound and `<` on the upper. A closed interval
double counts any row landing exactly on the boundary when you run the query for consecutive
periods.

```sql
SELECT
    Count(e.EventID) AS EventsInPreviousHour
FROM Orion.Events e
WHERE e.EventTime >= AddHour(-1, DateTrunc('hour', GetDate()))
  AND e.EventTime <  DateTrunc('hour', GetDate())
```

### A rolling window on a statistics table

```sql
SELECT
    rt.Node.Caption          AS NodeName,
    Avg(rt.AvgResponseTime)  AS AvgResponseMs,
    Max(rt.MaxResponseTime)  AS PeakResponseMs,
    Count(rt.NodeID)         AS Samples
FROM Orion.ResponseTime rt
WHERE rt.DateTime >= AddHour(-6, GetDate())
GROUP BY rt.Node.Caption
ORDER BY AvgResponseMs DESC
```

`rt.Node` is the navigation property from `Orion.ResponseTime` back to `Orion.Nodes`, so no
`ON` clause is needed. See
[joins-and-navigation.md](joins-and-navigation.md).

### Parameterised windows

Best of all, let the caller supply the boundary as a typed value and skip literal parsing
entirely:

```sql
SELECT TOP 500
    e.EventTime,
    e.Message
FROM Orion.Events e
WHERE e.EventTime >= @since
  AND e.EventTime <  @until
ORDER BY e.EventTime DESC
```

In PowerShell: `Get-SwisData $swis $query @{ since = (Get-Date).AddDays(-1); until = (Get-Date) }`.
Over REST it is a `POST /Query` with a `parameters` object. Full detail in
[../swis/rest-api.md](../swis/rest-api.md#parameter-binding).

## `DateTime` literals and parameters

A string is converted to a date automatically when the context needs a date. The explicit
form is `DateTime(s)`:

```sql
SELECT KeepAlive
FROM Orion.Engines
WHERE KeepAlive > DateTime('9/25/2015 3:49:54')
```

**Result:** `2015-09-25 15:55:14`

The implicit form works too, which is why this recorded example compares a date column with a
bare string:

```sql
SELECT TOP 1 YearDiff(KeepAlive, '1/01/2020 0:0:0 AM') AS ColumnResult
FROM Orion.Engines
```

**Result:** `5`

Three things follow from those two examples.

**The recorded literals are `M/D/YYYY`.** That format is ambiguous with `D/M/YYYY` for any
day of the month up to 12: `3/4/2026` is either 4 March or 3 April depending on who is
parsing it. Nothing in the published documentation states which format SWIS accepts or
whether it depends on the SQL Server's locale, and this repository has no evidence to settle
it.

**Literals carry no timezone.** The workbook's note on the `DateTime` entry says the result
is "Time derived from SQL Server time zone settings". A literal with no offset in it is
interpreted on the SQL Server's clock, not yours and not UTC. So `DateTime('2026-01-01
00:00:00')` compared against a `...Utc` column is wrong by your offset unless you wrap it:
`ToUtc(DateTime('2026-01-01 00:00:00'))`.

**So bind a parameter instead.** A bound `System.DateTime` keeps its type all the way through
the client library, and there is no format to get wrong and no locale to depend on:

```sql
SELECT n.NodeID, n.Caption, n.LastBoot
FROM Orion.Nodes n
WHERE n.LastBoot < @cutoff
ORDER BY n.LastBoot
```

If you must use a literal, the ISO 8601 form `'2026-01-01T00:00:00'` is the conventional
choice for unambiguity, but its acceptance by SWIS is **unverified** here: no published
SolarWinds example uses it. Test it before depending on it, and the test is one query:

```sql
SELECT TOP 1
    DateTime('2026-03-04T05:06:07') AS IsoForm,
    DateTime('3/4/2026 5:06:07')    AS SlashForm
FROM Orion.Engines
```

If both columns come back as 4 March 2026 at 05:06:07, your server accepts ISO 8601 and reads
`M/D/YYYY`. If the second column reads 3 April, your server reads `D/M/YYYY` and every
slash-format literal in your saved queries needs review. If the first column errors, ISO 8601
is not accepted on your version.

## A checklist before you save a time-bounded query

1. Which clock is the column on? UTC, server local, or unverified and therefore measured?
2. Is the bound on the same clock as the column?
3. Does any `AddX` have `GetUtcDate()` directly inside it? If so, wrap the inner value in
   `ToLocal` and the whole thing in `ToUtc`.
4. Is the column bare on the left of the comparison, with all arithmetic on the right?
5. Is the window half open, `>=` and `<`, so consecutive runs neither double count nor drop
   rows?
6. If it groups, does it group on `DateTrunc` or `Downsample` rather than on a raw timestamp?
7. Are the literal dates parameters yet?

## See also

- [functions.md](functions.md) for every date function's signature, observed result and
  recorded version baseline, plus the rest of the function library.
- [language-reference.md](language-reference.md#query-parameters) for parameter binding and
  the `WITH` clauses.
- [joins-and-navigation.md](joins-and-navigation.md) for reaching a timestamp that lives on a
  related entity.
- [../reference/swql-function-index.md](../reference/swql-function-index.md) for the
  one-table view of all 63 functions.
- SolarWinds'
  [possible issues](https://solarwinds.github.io/OrionSDK/docs/swql-functions/possible-issues/)
  page, which is the primary source for the `DATEADD` behaviour described here and is worth
  reading in full.

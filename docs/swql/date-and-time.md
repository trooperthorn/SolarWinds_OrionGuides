# SWQL date and time

Time-bounded queries are where SWQL most often returns a confident wrong answer. The query
compiles, the result set is the right shape, the timestamps look plausible, and the window is
off by the number of hours between the SQL Server and UTC.

This page explains why that happens, gives the corrected patterns, and covers the whole date
and time surface: which function reads which clock, how the `AddX` and `XDiff` families
behave, what `DateTrunc` will and will not truncate, and how to write "the last 24 hours" so
that it means the last 24 hours.

The per-function signatures and observed results live in [functions.md](functions.md). This
page is about combining them correctly.

## The short version

1. **Work out whether the column you are filtering holds UTC or server local time.** The
   schema will usually tell you in the property name; if it does not, measure it (see
   [Which columns are UTC](#which-columns-are-utc-and-which-are-local)).
2. **Never wrap `GetUtcDate()` directly in an `AddX` function.** `AddMinute(-10,
   GetUtcDate())` returns a value stamped with the SQL Server's local offset, not `Z`.
3. **Do the arithmetic in local time and convert at the end**:
   `ToUtc(AddMinute(-10, ToLocal(GetUtcDate())))`, or equivalently
   `ToUtc(AddMinute(-10, GetDate()))`.
4. **Bucket with `DateTrunc` or `Downsample`**, never by grouping on a raw timestamp.
5. **Bind dates as parameters** instead of formatting literals into the query text.
6. **Put the arithmetic on the constant side of the comparison**, not around the column.

Everything below is why.

## How a SWQL date query actually runs

SWIS does not evaluate SWQL itself. It translates the query into T-SQL and runs it against
the Orion database, then serialises the rows back to the client. SolarWinds publishes the
generated T-SQL for a date query on its
[possible issues](https://solarwinds.github.io/OrionSDK/docs/swql-functions/possible-issues/)
page:

```text
SET DATEFIRST 7;
SET TRANSACTION ISOLATION LEVEL READ COMMITTED;
SELECT [T1].[EngineID] AS C1, [T1].[ServerName] AS C2, [T1].[IP] AS C3, [T1].[ServerType] AS C4,
       GETUTCDATE() AS C5,
       DateAdd(minute,-10,GETUTCDATE()) AS C6,
       DateAdd(second,-10,GETUTCDATE()) AS C7,
       DateAdd(millisecond,-10000,GETUTCDATE()) AS C8,
       DateAdd(hour,-10,GETUTCDATE()) AS C9
FROM dbo.Engines AS T1
WHERE [T1].[ServerType] = 'Primary'
```

Three things in that fragment matter for the rest of this page:

- **`SET DATEFIRST 7`** makes Sunday the first day of the week, which is what `Week(d)` and
  `DateTrunc('week', d)` inherit.
- **`ADDMINUTE`, `ADDSECOND` and the rest all become `DateAdd`.** There is no SWIS-side date
  library doing anything clever; the SWQL name is a thin alias over
  [T-SQL `DATEADD`](https://learn.microsoft.com/en-us/sql/t-sql/functions/dateadd-transact-sql).
- **`DATEADD` is timezone blind.** In SolarWinds' words: "By definition, this function
  doesn't work with time zone offset at all, so it doesn't know that we want the time zone to
  be UTC by `GetUtcDate()` and it counts as it is in the local time zone."

## The trap: `GetUtcDate()` plus `AddX`

Run that query and look at what comes back over the wire. This is SolarWinds' own recorded
response, trimmed to the date columns:

```xml
<row>
  <c4>2024-05-17T10:37:27.8070000Z</c4>
  <c5>2024-05-17T10:27:27.8070000-05:00</c5>
  <c6>2024-05-17T10:37:17.8070000-05:00</c6>
  <c7>2024-05-17T10:37:17.8070000-05:00</c7>
  <c8>2024-05-17T00:37:27.8070000-05:00</c8>
</row>
```

`c4` is `GETUTCDATE()` and it is correctly labelled `Z`. Every other column went through
`DateAdd` and came back labelled `-05:00`, the SQL Server's own offset.

Look closely at what is wrong, because it is subtler than "the value is incorrect":

- **The clock arithmetic is right.** `c5` reads `10:27:27`, which is exactly ten minutes
  before `c4`'s `10:37:27`.
- **The offset label is wrong.** `10:27:27-05:00` is the instant `15:27:27Z`. As a point in
  time, `c5` is five hours *after* `c4`, not ten minutes before it.

So the damage is done at the boundary, not in the calculation. `DATEADD` receives a UTC
value, does correct arithmetic on the numbers, and hands back a plain `datetime` with no
timezone attached. SQL Server then stamps it with the server's own offset on the way out, and
SWIS serialises whatever it was given.

What happens next depends on the client. SolarWinds notes that "SWQL Studio will convert the
values with the offset to the time zone of the machine where it is running and values in UTC
stay the same." Any client that honours the offset, which includes most JSON and .NET date
parsers, does the same. So the value shifts by the SQL Server's UTC offset, and it shifts
silently.

This is why a dashboard built on `AddDay(-1, GetUtcDate())` looks fine in a datacenter that
runs UTC and is wrong by five, seven or eleven hours everywhere else.

## The fix: convert, add, convert back

Convert the value into the timezone `DATEADD` is going to assume anyway, do the arithmetic
there, then convert the result back. SolarWinds' corrected query, verbatim from the same
page:

```sql
SELECT
    EngineID,
    ServerName,
    IP,
    ServerType,
    GETUTCDATE() AS [Time_Now],
    TOUTC(ADDMINUTE(-10, TOLOCAL(GETUTCDATE()))) AS [Time_Past_Minute],
    TOUTC(ADDSECOND(-10, TOLOCAL(GETUTCDATE()))) AS [Time_Past_Second],
    TOUTC(ADDMILLISECOND(-10000, TOLOCAL(GETUTCDATE()))) AS [Time_Past_Milliseond],
    TOUTC(ADDHOUR(-10, TOLOCAL(GETUTCDATE()))) AS [Time_Past_Hour]
FROM Orion.Engines
WHERE ServerType = 'Primary'
WITH LOGS
```

The rule generalises to `ToUtc(AddX(n, ToLocal(<utc value>)))`. SolarWinds states it as: "If
you are using `AddMinute` etc. functions you need to first convert the value to the local
time of the MSSQL server and then convert the result back to UTC time."

### The shorter equivalent

SolarWinds' headline recommendation on the same page is simpler: "leverage the `GETDATE()`
function first to perform any time modifications and then use the `TOUTC()` function at the
end if you are in another timezone."

```sql
SELECT TOP 1
    ToUtc(AddMinute(-10, GetDate())) AS TenMinutesAgoUtc,
    ToUtc(AddDay(-1, GetDate()))     AS OneDayAgoUtc,
    ToUtc(AddDay(-7, GetDate()))     AS SevenDaysAgoUtc
FROM Orion.Engines
```

`GetDate()` already returns the SQL Server's local time, so `ToLocal(GetUtcDate())` and
`GetDate()` are the same instant and this form saves one conversion. Both shapes appear in
SolarWinds' own documentation and both are correct.

One caveat that applies to both: "local" means the SQL Server's timezone. It is not
necessarily the Orion application server's timezone, and it is definitely not the timezone of
whoever is reading the report. If your SQL Server, your Orion server and your users are in
three different timezones, the conversions here get you a correct instant, and presenting it
in the reader's timezone is the client's job.

### Where the trap does not reach

If both sides of a comparison stay inside SQL Server, the arithmetic is done on plain
`datetime` values and the offset labelling never comes into it, so a predicate such as
`WHERE TimeLoggedUtc >= AddDay(-1, GetUtcDate())` should be comparing what you meant even
though selecting that same expression would return a mislabelled value. That reading is an
inference from the generated T-SQL above and is **unverified** here.

SolarWinds' worked example demonstrates the corruption in the select list only, and nothing
in the published material says how the offset is handled inside a predicate. To settle it on
your own server, count the same UTC column twice with the two bounds and compare:

```sql
SELECT
    Count(a.AuditEventID) AS ViaGetUtcDate
FROM Orion.AuditingEvents a
WHERE a.TimeLoggedUtc >= AddDay(-1, GetUtcDate())
```

against the same query with `ToUtc(AddDay(-1, GetDate()))` as the bound. Identical counts mean
the predicate position was never affected on your version; different counts, by roughly your
UTC offset's worth of rows, mean it was.

Until you have run that, it is exactly the kind of gap not worth betting a report on. Use the
convert-add-convert-back form everywhere: it is correct in both positions, it costs one extra
function call, and it means you never have to remember which position you are in.

## The four functions that read or move the clock

| Function | Returns | Notes |
|:---|:---|:---|
| `GetDate()` | Current time in **local time at the Orion server** | "Time derived from SQL Server time zone settings" |
| `GetUtcDate()` | Current time in **UTC** | The official reference attaches an explicit warning to this one |
| `ToLocal(d)` | `d` converted to **local time on the Orion server** | The inbound half of the fix |
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

There is no flag in the schema that says "this column is UTC". What there is:

- **1301 properties** in the 2026.2 schema are typed `System.DateTime`.
- **128 of them have `Utc` in the property name.** That naming is the most reliable signal
  you get: `Orion.AuditingEvents.TimeLoggedUtc`, `Orion.Nodes.LastSystemUpTimePollUtc`,
  `Orion.APM.WindowsEvent.TimeGeneratedUtc`, `Orion.CPUMultiLoad.TimeStampUTC`.
- **Nine of them say UTC in their description**, and for six of those the name does not, so
  the description is the only signal you get. `Orion.VIM.TriggeredAlarmState.Timestamp` is
  one: "The timestamp in UTC indicating when the alarm was fired."
- **One of the most queried date columns documents itself as local.**
  `Orion.Events.EventTime` is described as "Date and time when the event occurred, displayed
  in local time."

Everything else is undocumented, which includes `Orion.Nodes.LastBoot`,
`Orion.Nodes.NextPoll`, `Orion.Engines.KeepAlive`, `Orion.AlertActive.TriggeredDateTime` and
`Orion.CPULoad.DateTime`. Do not guess. Measure.

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

Whichever of the last two columns is near zero identifies the clock the column is stored on.
The other will be off by your UTC offset in minutes. `MinutesSinceKeepAlive` is a computed
property SWIS provides on the same entity, so it gives you an independent third opinion for
free.

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

`Orion.Events.EventTime` is one of the few date columns documented as local, and `GetDate()`
is local, so this pair is consistent with no conversion. That is not luck, it is the point:
match the clock of the bound to the clock of the column, every time.

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

These are the patterns worth memorising. Each one puts all the arithmetic on the constant
side of the comparison and leaves the column bare, which matters for more than tidiness: the
expression on the right is evaluated once, while wrapping the column in a function forces the
generated T-SQL to evaluate it for every row and gives up any chance of an index seek on the
timestamp. On a statistics table with tens of millions of rows that is the difference between
a query and an outage.

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

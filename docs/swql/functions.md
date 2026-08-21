# SWQL functions

The complete built-in function library of SolarWinds Query Language, with a runnable example
for every function.

There are **63 functions** covered here. **62** of them appear in SolarWinds' official
[SWQL function reference](https://solarwinds.github.io/OrionSDK/docs/swql-functions/). One
(`ChangeTimeZone`) is attested only by a community workbook and is marked as unverified. The
signatures and descriptions on this page come from the official reference; the worked
examples and observed results come from the workbook, joined together in
[`data/reference/swql-functions.json`](../../data/reference/swql-functions.json). The
one-line table version of the same data is
[../reference/swql-function-index.md](../reference/swql-function-index.md).

Every entity and property named in a `sql` block below was resolved against the extracted
2026.2 schema before it was written, and all of them are re-checked on every build by
[`tools/validate_swql.py`](../../tools/validate_swql.py).

## How to read an entry

Each entry gives the signature, what the function returns, and an example you can paste into
SWQL Studio or POST to `/Query`.

- **Result:** lines appear only where the source data records an actual observed result.
  Every one of those runs was captured on a 2015-era server, which is why the timestamps in
  them look old. The values are real; the dates are simply when the run happened.
- Examples without a **Result:** line were constructed from the published signature. They are
  shaped correctly and use real schema names, but nobody recorded their output here.
- **Since:** quotes the official reference where it states a minimum platform version.
  **Workbook baseline:** is the earliest version the workbook recorded a successful run on.
  These two are different kinds of evidence and they disagree once; see
  [Reconciliation](#reconciliation-where-the-sources-disagree).

Function names are not case sensitive. SolarWinds' own published material writes
`GETUTCDATE()` in the [possible issues](https://solarwinds.github.io/OrionSDK/docs/swql-functions/possible-issues/)
page and `getdate()` in the workbook, and both run.

## Contents

- [General functions](#general-functions): `IsNull`, `Case`, `UNION`
- [Numeric functions](#numeric-functions): `Abs`, `Ceiling`, `Floor`, `Round`
- [Date/time functions](#datetime-functions): the current time, conversions, `AddX`, `XDiff`,
  part extraction, `DateTrunc`, `Downsample`, `DateTime`
- [Aggregate functions](#aggregate-functions): `Avg`, `Count`, `Max`, `Min`, `Sum`, `String_Agg`
- [Array functions](#array-functions): `ArrayContains`, `ArrayLength`, `ArrayValueAt`, `SplitStringToArray`
- [String functions](#string-functions): `Concat`, `Length`, `CharIndex`, `SubString`, `Replace`, `ToLower`, `ToUpper`, `ToString`, `UriEquals`, `EscapeSWISUriValue`
- [Reconciliation: where the sources disagree](#reconciliation-where-the-sources-disagree)
- [What is not in the function library](#what-is-not-in-the-function-library)

For anything involving a timestamp, read [date-and-time.md](date-and-time.md) as well. The
date functions are individually simple and combine into wrong answers, and that page exists
because the combination is the single most common source of incorrect SWQL.

---

## General functions

### `IsNull(a, b)`

Returns `a` unless it is `NULL`, else returns `b`. The SWQL equivalent of T-SQL's `ISNULL`,
not of `IS NULL`.

**Workbook baseline:** 2011.1

```sql
SELECT Restart, IsNull(Restart, '9/25/2015 3:49:54') AS ColumnResult
FROM Orion.Engines
```

**Result:** `NULL, 9/25/2015 3:49:54 AM`

`Orion.Engines.Restart` is `NULL` on an engine that has not restarted since the row was
created, so the second column shows the substitute. The more common use is making a nullable
string presentable:

```sql
SELECT TOP 20
    n.Caption,
    IsNull(n.Location, '(no location set)') AS Location
FROM Orion.Nodes n
ORDER BY n.Caption
```

`IsNull` is also how you defend a `WHERE` clause against nulls, because in SWQL as in SQL a
comparison with `NULL` is neither true nor false and the row silently disappears.

### `Case when c then a else b end`

Returns `a` if `c` is true, else returns `b`. Multiple `WHEN` branches are evaluated top to
bottom and the first match wins.

The reference records no worked example. This one turns the integer `Status` column into
text using the ids from [../reference/status-codes.md](../reference/status-codes.md):

```sql
SELECT TOP 25
    n.Caption,
    n.Status,
    CASE WHEN n.Status = 1 THEN 'Up'
         WHEN n.Status = 2 THEN 'Down'
         WHEN n.Status = 3 THEN 'Warning'
         WHEN n.Status = 9 THEN 'Unmanaged'
         WHEN n.Status = 12 THEN 'Unreachable'
         ELSE 'Other' END AS StatusText
FROM Orion.Nodes n
ORDER BY n.Status
```

If all you want is the status name, join `Orion.StatusInfo` on `StatusId` instead of writing
a `CASE` ladder; you get every status, including the ones you forgot, and you do not have to
maintain the list. `CASE` earns its place when you are collapsing many statuses into few
buckets, or when the condition is not a simple equality.

### `UNION(q)`

Adds the results of an additional query `q` directly below the former. The number of columns
must match between unioned queries.

Written as a statement it looks like SQL:

```sql
SELECT 'Node' AS ObjectKind, n.Caption AS ObjectName, n.Status AS StatusId
FROM Orion.Nodes n
WHERE n.Status = 2
UNION
SELECT 'Interface' AS ObjectKind, i.Caption AS ObjectName, i.Status AS StatusId
FROM Orion.NPM.Interfaces i
WHERE i.Status = 2
```

Column names come from the first `SELECT`. The literal `ObjectKind` column does double duty:
it tells you which branch a row came from, and because it differs between branches it stops
`UNION` from deduplicating two identically named objects of different kinds.

`UNION ALL` is **unverified**: only `UNION` is documented. Before unioning entity types at
all, check whether a shared base entity already returns the rows you want in one query;
nodes, interfaces, volumes and applications all descend from `System.ManagedEntity`. See
[joins-and-navigation.md](joins-and-navigation.md#querying-a-base-entity) and the fuller
treatment in [language-reference.md](language-reference.md#union).

---

## Numeric functions

### `Abs(n)`

Returns the absolute value of `n`.

**Workbook baseline:** 2011.1

```sql
SELECT TOP 1 Abs(-1) AS ResultColumn
FROM Orion.Engines
```

**Result:** `1`

The workbook records this against a placeholder table; `Orion.Engines` is used here because
it is present on every installation and normally has very few rows, which makes it the
natural scratchpad for expression-only queries. `TOP 1` keeps the output to one row.

### `Ceiling(n)`

Returns the smallest integer that is not less than `n`. Rounds towards positive infinity, so
`Ceiling(-1.2)` is `-1`, not `-2`.

**Workbook baseline:** 2013.1

```sql
SELECT TOP 20
    n.Caption,
    n.PercentLoss,
    Ceiling(n.PercentLoss) AS WholePercentLoss
FROM Orion.Nodes n
WHERE n.PercentLoss > 0
```

The workbook's recorded form is `SELECT ceiling(ResponseTime) as ResultColumn FROM
Orion.Nodes`, which works but rounds a value that is already `System.Int32`.
`Orion.Nodes.PercentLoss` is `System.Double`, so the rounding is visible.

### `Floor(n)`

Returns the largest integer that is not greater than `n`. Rounds towards negative infinity,
so `Floor(-1.2)` is `-2`.

**Workbook baseline:** 2013.1

```sql
SELECT TOP 20
    n.Caption,
    n.PercentLoss,
    Floor(n.PercentLoss) AS WholePercentLoss
FROM Orion.Nodes n
WHERE n.PercentLoss > 0
```

### `Round(n, p)`

Returns `n` rounded to `p` decimal places.

**Workbook baseline:** 2013.1

```sql
SELECT TOP 20
    n.Caption,
    Round(n.PercentLoss, 2) AS PercentLoss
FROM Orion.Nodes n
ORDER BY n.PercentLoss DESC
```

Both arguments are expressions, not just literals; the workbook's recorded example is
`SELECT round(ResponseTime, PercentLoss) as ResultColumn FROM Orion.Nodes`, which is a
strange thing to want but demonstrates that the precision argument can come from a column.

---

## Date/time functions

Thirty-five functions, and the place where correct-looking SWQL most often returns wrong
answers. Each is listed here with its signature and an example. The reasoning about why they
combine badly, and the query patterns that are actually correct, are in
[date-and-time.md](date-and-time.md).

### Reading the current time

#### `GetDate()`

Returns the current date in local time at the Orion server.

**Workbook baseline:** 2011.1

```sql
SELECT TOP 1 GetDate() AS ResultColumn
FROM Orion.Engines
```

**Result:** `2015-09-25 08:52:35`

The workbook's note on this entry is worth keeping in mind: "Time derived from SQL Server
time zone settings." This is the SQL Server's clock and timezone, not the clock of the
machine running your query and not necessarily the clock of the Orion application server.

#### `GetUtcDate()`

Returns the current date and time in UTC.

**Workbook baseline:** 2011.1

```sql
SELECT TOP 1 GetUtcDate() AS ResultColumn
FROM Orion.Engines
```

**Result:** `2015-09-25 15:53:49`

The official reference attaches an explicit warning to this function and links to its
[possible issues](https://solarwinds.github.io/OrionSDK/docs/swql-functions/possible-issues/)
page. Combining `GetUtcDate()` with any `AddX` function produces a value carrying the wrong
timezone offset. Read [date-and-time.md](date-and-time.md#the-trap-getutcdate-plus-addx)
before you use it in arithmetic.

### Converting between local and UTC

#### `ToLocal(d)`

Converts `d` to local time on the Orion server.

**Workbook baseline:** 2011.1

```sql
SELECT TOP 1 ToLocal(GetUtcDate()) AS ResultColumn
FROM Orion.Engines
```

**Result:** `9/25/2015  8:50:37 AM`

#### `ToUtc(d)`

Converts `d` to UTC time. The official reference lists this one with no argument list, as
plain `ToUtc`, but describes it in terms of `d` and every published example passes one
argument.

**Workbook baseline:** 2011.1

```sql
SELECT TOP 1 ToUtc(GetDate()) AS ResultColumn
FROM Orion.Engines
```

**Result:** `2015-09-25 15:49:54`

`ToLocal` and `ToUtc` are the two halves of the fix for the date arithmetic trap: convert to
local, do the arithmetic, convert back. See
[date-and-time.md](date-and-time.md#the-fix-convert-add-convert-back).

### Adding an interval

The eight single-unit `AddX` functions take the count first and the date second: `AddDay(7,
d)` is "seven days after `d`", not "day 7 of `d`". Passing a negative count subtracts.
`AddDate` is the ninth member of the family and puts the unit name in front of the count.

Every one of these compiles to T-SQL `DATEADD`, which ignores timezone offsets entirely.
That is the whole of the trap described in [date-and-time.md](date-and-time.md).

#### `AddDate(u, n, d)`

Returns a date `n` units after `d`, where the unit is given by `u`, which must be one of
`'millisecond'`, `'second'`, `'minute'`, `'hour'`, `'day'`, `'week'`, `'month'` or `'year'`.

**`u` must be a string literal.** It cannot be a query parameter or a value derived from the
data. This is stated explicitly in the official reference and it is the one thing about
`AddDate` that surprises people: you cannot make the unit dynamic.

**Workbook baseline:** 2014.2

```sql
SELECT TOP 1 AddDate('month', 2, KeepAlive) AS ColumnResult
FROM Orion.Engines
```

**Result:** `2015-11-25 16:38:47`

Note that `'quarter'` is not in the list of units, even though `DateTrunc` accepts
`'quarter'` as a datepart. Add three months instead.

#### `AddDay(n, d)`

Returns a date `n` days after `d`.

**Workbook baseline:** 2014.2

```sql
SELECT TOP 1 AddDay(17, KeepAlive) AS ColumnResult
FROM Orion.Engines
```

**Result:** `2015-10-12 16:30:16`

#### `AddHour(n, d)`

Returns a date `n` hours after `d`.

**Workbook baseline:** 2014.2

```sql
SELECT TOP 1 AddHour(1, KeepAlive) AS ColumnResult
FROM Orion.Engines
```

**Result:** `2015-09-25 17:31:16`

#### `AddMinute(n, d)`

Returns a date `n` minutes after `d`.

**Workbook baseline:** 2014.2

```sql
SELECT TOP 1 AddMinute(30, KeepAlive) AS ColumnResult
FROM Orion.Engines
```

**Result:** `2015-09-25 17:02:16`

#### `AddSecond(n, d)`

Returns a date `n` seconds after `d`.

**Workbook baseline:** 2014.2

```sql
SELECT TOP 1 AddSecond(13, KeepAlive) AS ColumnResult
FROM Orion.Engines
```

**Result:** `2015-09-25 16:33:16`

#### `AddMillisecond(n, d)`

Returns a date `n` milliseconds after `d`.

**Workbook baseline:** 2014.2

```sql
SELECT TOP 5 AddMillisecond(1, NextPoll) AS NextPoll
FROM Orion.Nodes
```

No result was recorded for this one.

#### `AddWeek(n, d)`

Returns a date `n` weeks after `d`.

**Workbook baseline:** 2014.2

```sql
SELECT TOP 1 AddWeek(7, KeepAlive) AS ColumnResult
FROM Orion.Engines
```

**Result:** `2015-11-13 16:26:46`

#### `AddMonth(n, d)`

Returns a date `n` months after `d`.

**Workbook baseline:** 2014.2

```sql
SELECT TOP 1 AddMonth(5, KeepAlive) AS ColumnResult
FROM Orion.Engines
```

**Result:** `2016-02-25 16:26:16`

#### `AddYear(n, d)`

Returns a date `n` years after `d`.

**Workbook baseline:** 2014.2

```sql
SELECT TOP 1 AddYear(5, KeepAlive) AS ColumnResult
FROM Orion.Engines
```

**Result:** `2020-09-25 16:25:46`

### Measuring an interval

The eight `XDiff` functions all have the same shape: `XDiff(a, b)` returns how much later
`b` is than `a`, rounded to the nearest whole unit. Order matters, and it is the opposite of
subtraction: `DayDiff(earlier, later)` is positive.

Rounding to the nearest whole unit is what makes `MonthDiff` return `1` for a 28-day span.
If you need precision, difference in the smallest unit you can and divide.

**A note on the examples below.** The workbook recorded these against a second date written
as `KeepAlive + 28`, using bare integer addition to add days. That behaviour is attested by
the recorded results but is not in the official function reference, so the queries here use
the documented `AddDay(28, KeepAlive)` instead. The recorded results are unchanged, and the
arithmetic behind each one is shown so you can check it rather than take it on trust. The
evidence for integer addition itself is laid out in
[date-and-time.md](date-and-time.md#integer-addition-adds-days).

#### `MillisecondDiff(a, b)`

Returns the number of milliseconds (rounded to the nearest integer) that `b` is later than
`a`.

**Workbook baseline:** 2011.1

```sql
SELECT TOP 1 MillisecondDiff(KeepAlive, AddDay(24, KeepAlive)) AS ColumnResult
FROM Orion.Engines
```

**Result:** `2073600000`

The workbook's note says 24 days "is also the max that can used for this query", and the
arithmetic explains why: 24 days is 2,073,600,000 ms, while 25 days is 2,160,000,000 ms,
which is past the largest 32-bit signed integer (2,147,483,647). Spans longer than about
24.8 days overflow the return type. Use `SecondDiff` and multiply if you need a wider range.

#### `SecondDiff(a, b)`

Returns the number of seconds (rounded to the nearest integer) that `b` is later than `a`.

**Workbook baseline:** 2011.1

```sql
SELECT TOP 1 SecondDiff(KeepAlive, AddDay(28, KeepAlive)) AS ColumnResult
FROM Orion.Engines
```

**Result:** `2419200`

A note on the evidence here: the workbook records the query as `SecondDiff(KeepAlive,
KeepAlive + 1)` but records the result as `2419200`, which is exactly 28 days of seconds
(86400 x 28), matching the note attached to the entry rather than the query text. The
recorded pair is internally inconsistent, so the query above has been written to match the
arithmetic. Check the arithmetic, not the transcription.

#### `MinuteDiff(a, b)`

Returns the number of minutes (rounded to the nearest integer) that `b` is later than `a`.

**Workbook baseline:** 2011.1

```sql
SELECT TOP 1 MinuteDiff(KeepAlive, AddDay(28, KeepAlive)) AS ColumnResult
FROM Orion.Engines
```

**Result:** `40320` (28 x 1440)

#### `HourDiff(a, b)`

Returns the number of hours (rounded to the nearest integer) that `b` is later than `a`.

**Workbook baseline:** 2011.1

```sql
SELECT TOP 1 HourDiff(KeepAlive, AddDay(28, KeepAlive)) AS ColumnResult
FROM Orion.Engines
```

**Result:** `672` (28 x 24)

#### `DayDiff(a, b)`

Returns the number of days (rounded to the nearest integer) that `b` is later than `a`.

**Workbook baseline:** 2011.1

```sql
SELECT TOP 1 DayDiff(KeepAlive, AddDay(28, KeepAlive)) AS ColumnResult
FROM Orion.Engines
```

**Result:** `28`

A practical use is age in days, which is one of the most common report columns in Orion:

```sql
SELECT TOP 20
    n.Caption,
    n.LastBoot,
    DayDiff(n.LastBoot, GetDate()) AS DaysSinceBoot
FROM Orion.Nodes n
WHERE n.LastBoot IS NOT NULL
ORDER BY DaysSinceBoot DESC
```

#### `WeekDiff(a, b)`

Returns the number of weeks (rounded to the nearest integer) that `b` is later than `a`.

**Workbook baseline:** 2011.1

```sql
SELECT TOP 1 WeekDiff(KeepAlive, AddDay(28, KeepAlive)) AS ColumnResult
FROM Orion.Engines
```

**Result:** `4`

#### `MonthDiff(a, b)`

Returns the number of months (rounded to the nearest integer) that `b` is later than `a`.

**Workbook baseline:** 2011.1

```sql
SELECT TOP 1 MonthDiff(KeepAlive, AddDay(28, KeepAlive)) AS ColumnResult
FROM Orion.Engines
```

**Result:** `1`

#### `YearDiff(a, b)`

Returns the number of years (rounded to the nearest integer) that `b` is later than `a`.

**Workbook baseline:** 2011.1

```sql
SELECT TOP 1 YearDiff(KeepAlive, '1/01/2020 0:0:0 AM') AS ColumnResult
FROM Orion.Engines
```

**Result:** `5`

This example is also a demonstration that a string literal is converted to a date
automatically when it is compared with or passed alongside a date. See
[`DateTime`](#datetime) below and
[date-and-time.md](date-and-time.md#datetime-literals-and-parameters).

### Extracting a part of a date

These eleven all take a date and return an integer. They are the natural `GROUP BY` keys for
"by hour of day" or "by day of week" reports.

#### `Year(d)`

Returns the year of `d`. **Workbook baseline:** 2011.1

```sql
SELECT TOP 1 Year(KeepAlive) AS ColumnResult
FROM Orion.Engines
```

**Result:** `2015`

#### `QuarterOfYear(d)`

Returns the quarter of the year that contains `d`. January, February and March are 1; April,
May and June are 2, and so on. **Workbook baseline:** 2011.1

```sql
SELECT TOP 1 QuarterOfYear(KeepAlive) AS ColumnResult
FROM Orion.Engines
```

**Result:** `3`

#### `Month(d)`

Returns the month part of `d`. January is 1. The official reference lists this one with no
argument list, as plain `Month`, but describes it in terms of `d` and the published example
passes one argument. **Workbook baseline:** 2011.1

```sql
SELECT TOP 1 Month(KeepAlive) AS ColumnResult
FROM Orion.Engines
```

**Result:** `9`

#### `Week(d)`

Returns the week number of `d`. **Workbook baseline:** 2011.1

```sql
SELECT TOP 1 Week(KeepAlive) AS ColumnResult
FROM Orion.Engines
```

**Result:** `39`

Week numbering depends on which day the server treats as the first day of the week.
SolarWinds' published generated T-SQL begins with `SET DATEFIRST 7;`, which is Sunday, so
weeks break on Sunday nights.

#### `WeekDay(d)`

Returns the day of the week of `d` as a number, with Sunday = 0, Monday = 1, and so on to
Saturday = 6.

**Since:** the official reference says Orion Platform 2016.1 and later.
**Workbook baseline:** 2015.2. Those two disagree; see
[Reconciliation](#reconciliation-where-the-sources-disagree).

```sql
SELECT TOP 1 WeekDay(KeepAlive) AS ColumnResult
FROM Orion.Engines
```

**Result:** `2` (the workbook notes 2 = Tuesday, 4 = Thursday, 6 = Saturday)

Note that this is zero-based with Sunday at 0, unlike T-SQL's `DATEPART(weekday, ...)`,
which is one-based and depends on `SET DATEFIRST`.

#### `DayOfYear(d)`

Returns the day of year of `d`. January 1 is 1, February 1 is 32, and so on.
**Workbook baseline:** 2011.1

```sql
SELECT TOP 1 DayOfYear(KeepAlive) AS ColumnResult
FROM Orion.Engines
```

**Result:** `268`

#### `Day(d)`

Returns the day of the month of `d`. **Workbook baseline:** 2011.1

```sql
SELECT TOP 1 Day(KeepAlive) AS ColumnResult
FROM Orion.Engines
```

**Result:** `25`

#### `Hour(d)`

Returns the hour part of `d`, in 24 hour format. **Workbook baseline:** 2011.1

```sql
SELECT TOP 1 Hour(KeepAlive) AS ColumnResult
FROM Orion.Engines
```

**Result:** `16`

A common shape, counting events by hour of day:

```sql
SELECT
    Hour(e.EventTime) AS HourOfDay,
    Count(e.EventID) AS Events
FROM Orion.Events e
WHERE e.EventTime >= AddDay(-7, GetDate())
GROUP BY Hour(e.EventTime)
ORDER BY HourOfDay
```

#### `Minute(d)`

Returns the minute part of `d`. The official reference lists this one with no argument list,
as plain `Minute`, but describes it in terms of `d` and the published example passes one
argument. **Workbook baseline:** 2011.1

```sql
SELECT TOP 1 Minute(KeepAlive) AS ColumnResult
FROM Orion.Engines
```

**Result:** `15`

#### `Second(d)`

Returns the second part of `d`. **Workbook baseline:** 2011.1

```sql
SELECT TOP 1 Second(KeepAlive) AS ColumnResult
FROM Orion.Engines
```

**Result:** `45`

#### `Millisecond(d)`

Returns the millisecond part of `d`. **Workbook baseline:** 2011.1

```sql
SELECT TOP 1 Millisecond(KeepAlive) AS ColumnResult
FROM Orion.Engines
```

**Result:** `613`

### Truncating and bucketing

#### `DateTrunc('datepart', d)`

Returns a date like `d` but with every component more granular than `datepart` set to zero.
The official reference lists the accepted dateparts as `'minute'`, `'hour'`, `'day'`,
`'week'`, `'month'`, `'quarter'` and `'year'`.

**Workbook baseline:** 2011.1

```sql
SELECT TOP 1 DateTrunc('month', KeepAlive) AS ColumnResult
FROM Orion.Engines
```

**Result:** `2015-09-01 00:00:00`

The workbook's note adds `'dayofyear'` to the accepted list and states explicitly that
`'millisecond'` and `'second'` are **not** supported. That matters: if you want per-second
buckets, `DateTrunc` will not give them to you, and `Downsample` is the function to reach
for. The full datepart table is in
[date-and-time.md](date-and-time.md#datetrunc-and-its-dateparts).

`DateTrunc` is what makes time-series grouping work, because grouping on a raw timestamp
gives one group per row:

```sql
SELECT
    DateTrunc('day', e.EventTime) AS EventDay,
    Count(e.EventID) AS Events
FROM Orion.Events e
WHERE e.EventTime >= AddDay(-30, GetDate())
GROUP BY DateTrunc('day', e.EventTime)
ORDER BY EventDay
```

#### `Downsample(d, p)`

Rounds the supplied timestamp `d` to the defined time period `p`. A period of `'00:15:00'`
rounds to the nearest 15 minute increment.

**Since:** the official reference says Orion 2018.3 or later.

No worked example or observed result is recorded for this function. The following is
constructed from the published signature and uses real schema names; verify the bucket
boundaries on your own version before publishing a report built on it:

```sql
SELECT
    Downsample(c.DateTime, '00:15:00') AS Bucket,
    Avg(c.AvgLoad) AS AvgCpuLoad,
    Max(c.MaxLoad) AS PeakCpuLoad
FROM Orion.CPULoad c
WHERE c.NodeID = 1
  AND c.DateTime >= AddDay(-1, GetDate())
GROUP BY Downsample(c.DateTime, '00:15:00')
ORDER BY Bucket
```

`Downsample` is the right tool where `DateTrunc` is too coarse. `DateTrunc` gives you fixed
calendar boundaries at a handful of granularities; `Downsample` takes an arbitrary period
string, so 5 minute, 15 minute and 6 hour buckets are all one argument change apart.
`Orion.CPULoad`, `Orion.ResponseTime` and `Orion.NPM.InterfaceTraffic` all expose a
`DateTime` column and are the usual targets.

### Parsing a date

#### `DateTime`

Converts a string to a date. In most scenarios this conversion happens automatically when
needed by usage. The official reference lists no argument list for this function; the
published example passes one string argument.

**Workbook baseline:** 2011.1

```sql
SELECT KeepAlive
FROM Orion.Engines
WHERE KeepAlive > DateTime('9/25/2015 3:49:54')
```

**Result:** `2015-09-25 15:55:14`

The workbook's note is the important part: "Time derived from SQL Server time zone
settings". A literal with no offset in it is interpreted in the SQL Server's timezone, not
yours and not UTC. See
[date-and-time.md](date-and-time.md#datetime-literals-and-parameters) for why binding a
parameter is better than formatting a literal.

---

## Aggregate functions

SolarWinds states the grouping rule directly: "Aggregate functions operate on a whole group
of values at once. If a `GROUP BY` clause is present in the query, the aggregate function
will operate on all values for each set of `GROUP BY` keys. If no `GROUP BY` clause is
present, the aggregate function will operate on all values returned by the query."

Filter groups with `HAVING`, not `WHERE`; `WHERE` runs before grouping.

### `Avg(n)`

Returns the average (arithmetic mean) of the values in the group.

**Workbook baseline:** 2011.1

```sql
SELECT
    n.Vendor,
    Avg(n.PercentLoss) AS AvgPercentLoss,
    Count(n.NodeID) AS Nodes
FROM Orion.Nodes n
GROUP BY n.Vendor
ORDER BY AvgPercentLoss DESC
```

`NULL` values are skipped rather than counted as zero, so an average over a mostly empty
column is an average of the rows that had data, not of all rows.

### `Count(n)`

Returns the number of non-`NULL` values in the group.

**Workbook baseline:** 2011.1

```sql
SELECT
    n.Vendor,
    Count(n.NodeID) AS Nodes
FROM Orion.Nodes n
GROUP BY n.Vendor
ORDER BY Nodes DESC
```

`Count(*)` is not in the official reference. Count a column that is never null, such as the
entity's key property, and you get the row count with no ambiguity. Counting a nullable
column deliberately is also useful: `Count(n.Location)` tells you how many nodes have a
location set.

### `Max(n)`

Returns the largest value in the group. Works on dates as well as numbers.

**Workbook baseline:** 2011.1

```sql
SELECT
    Max(n.LastBoot) AS MostRecentBoot,
    Min(n.LastBoot) AS OldestBoot
FROM Orion.Nodes n
```

### `Min(n)`

Returns the smallest value in the group. See the `Max` example above.

**Workbook baseline:** 2011.1

```sql
SELECT
    n.Vendor,
    Min(n.LastBoot) AS OldestBoot
FROM Orion.Nodes n
WHERE n.LastBoot IS NOT NULL
GROUP BY n.Vendor
ORDER BY OldestBoot
```

### `Sum(n)`

Returns the arithmetic sum of the values in the group.

**Workbook baseline:** 2011.1

```sql
SELECT
    n.Vendor,
    Sum(n.TotalMemory) AS TotalMemoryBytes
FROM Orion.Nodes n
GROUP BY n.Vendor
ORDER BY TotalMemoryBytes DESC
```

### `String_Agg(expression, separator [, orderExpression [ASC | DESC]])`

Concatenates the non-`NULL` string values in the group into a single string, separated by
`separator`. Both `expression` and `separator` are required. An optional ordering expression
controls the order in which values are concatenated; its direction is optional and defaults
to ascending. Returns `NULL` when the group has no non-`NULL` values.

No worked example or observed result is recorded for this function, and the reference states
no minimum version. The following is constructed from the published signature:

```sql
SELECT
    n.Vendor,
    Count(n.NodeID) AS Nodes,
    String_Agg(n.Caption, ', ', n.Caption ASC) AS NodeNames
FROM Orion.Nodes n
GROUP BY n.Vendor
ORDER BY Nodes DESC
```

This is the function that turns a one-row-per-child result into one row per parent with the
children listed in a cell, which is usually what an alert message or an exported report
wants. Because the separator is mandatory, there is no accidental run-together form.

If `String_Agg` is not available on your version the query fails to compile immediately,
which is a cheap test. Note that the reference gives no maximum length for the result.

---

## Array functions

A small number of SWIS properties are arrays rather than scalars: 17 properties in the
2026.2 schema are typed `System.String[]` and two are `System.Int32[]`. The most useful are
`System.ManagedEntity.AncestorDisplayNames` and `AncestorDetailsUrls`, inherited by every
managed entity, and the equivalents on `Orion.ContainerMembers`. These four functions are how
you get at their contents.

### `ArrayContains(a, v)`

Returns true if array `a` contains value `v`.

No worked example or observed result is recorded. Constructed from the signature:

```sql
SELECT
    cm.Name,
    cm.MemberEntityType
FROM Orion.ContainerMembers cm
WHERE ArrayContains(cm.MemberAncestorDisplayNames, 'Datacenter A')
```

This is the natural way to ask "is this object underneath that container", because the
ancestor list is already materialised on the row and you do not have to walk the hierarchy
yourself.

### `ArrayLength(a)`

Returns the number of elements in array `a`.

**Workbook baseline:** 2015.1

```sql
SELECT TOP 1 ArrayLength(MemberAncestorDetailsUrls) AS ColumnResult
FROM Orion.ContainerMembers
```

**Result:** `1`

The workbook's note: if the array is `NULL`, the function returns `NULL`, not zero. Guard
with `IsNull(ArrayLength(...), 0)` if you are going to do arithmetic on the result.

### `ArrayValueAt(a, i)`

Returns the array element at position `i` in array `a`, counting from zero.

**Workbook baseline:** 2015.1

```sql
SELECT TOP 1 ArrayValueAt(MemberAncestorDetailsUrls, 0) AS ColumnResult
FROM Orion.ContainerMembers
```

**Result:** `/Orion/NetPerfMon/ContainerDetails.aspx?NetObject=C:8`

Two behaviours from the workbook's note, both worth knowing:

- **Indexes start at zero.** This is the opposite of `SubString`, whose first character is
  position 1.
- **If the array is `NULL` the function returns `NULL`, but if the index is out of range the
  query fails.** An out-of-range index is an error, not a null. Bound it with
  `ArrayLength` in the `WHERE` clause before indexing.

### `SplitStringToArray(a)`

Splits string `a` into an array of substrings.

**Workbook baseline:** 2013.1

The official reference says it splits **on comma separators**. The workbook's recorded
example splits on something else entirely, and both are reproduced here because they cannot
both be right:

```sql
SELECT TOP 1 SplitStringToArray('Hello|§|§|world') AS a
FROM Orion.Engines
```

**Result:** `[Hello, world]`

The delimiter in that recorded input is `|§|§|`, not a comma, and the result shown is the
array rendering rather than a comma-separated string. **Verify the delimiter on your own
version before relying on it.** The cheapest test is to split a known comma string and pull
out the second element:

```sql
SELECT TOP 1 ArrayValueAt(SplitStringToArray('alpha,beta'), 1) AS SecondElement
FROM Orion.Engines
```

If that returns `beta`, the comma behaviour described in the official reference is what your
version implements. See
[Reconciliation](#reconciliation-where-the-sources-disagree).

---

## String functions

### `Concat(a, b, c, ...)`

Takes one or more arguments and returns a single string that is the concatenation of the
values of the arguments.

**Workbook baseline:** 2013.1

```sql
SELECT TOP 1 Concat('The ', 'most ', 'awesome ', 'string') AS ConString
FROM Orion.Engines
```

**Result:** `The most awesome string`

Variadic, so this is the way to build a display string in one call:

```sql
SELECT TOP 20
    Concat(n.Caption, ' (', n.IPAddress, ')') AS NodeLabel
FROM Orion.Nodes n
ORDER BY n.Caption
```

### `Length(s)`

Returns the length of string `s`.

**Workbook baseline:** 2015.2

```sql
SELECT TOP 1 Length(ServerName) AS NameLength
FROM Orion.Engines
```

**Result:** `14`

The workbook's note: "Works just for String properties". Wrap a non-string in
[`ToString`](#tostringa) first.

### `CharIndex(toFind, toSearch [, start])`

Returns the position at which `toFind` occurs within `toSearch`, starting at position
`start` if provided, or zero if `toFind` is not found.

**Since:** the official reference says Orion Platform 2018.2 (NPM 12.3) and later.

No worked example or observed result is recorded. Constructed from the signature:

```sql
SELECT TOP 20
    n.Caption,
    CharIndex('.', n.DNS) AS FirstDot
FROM Orion.Nodes n
WHERE CharIndex('.', n.DNS) > 0
```

Note the argument order: the needle comes first, the haystack second. Because a miss returns
zero rather than `NULL`, `CharIndex(x, y) > 0` is the idiomatic "contains" test, and it
composes with `SubString` for the split-a-string-at-a-character pattern:

```sql
SELECT TOP 20
    n.DNS,
    SubString(n.DNS, 1, CharIndex('.', n.DNS) - 1) AS HostPart
FROM Orion.Nodes n
WHERE CharIndex('.', n.DNS) > 1
```

The `WHERE` clause is not optional decoration there. Without it, rows whose `DNS` has no dot
would ask `SubString` for a length of -1.

### `SubString(s, start, length)`

Returns a substring of `length` characters starting at position `start`. **The first
character is position 1.**

**Workbook baseline:** 2013.1

```sql
SELECT TOP 1 SubString('123456789', 3, 6) AS TestSubString
FROM Orion.Engines
```

**Result:** `345678`

One-based, unlike [`ArrayValueAt`](#arrayvalueata-i), which is zero-based. Mixing the two up
is the classic off-by-one in SWQL.

### `Replace(expression, pattern, replacement)`

Replaces all occurrences of a specified string (`pattern`) value in `expression` with another
string value (`replacement`).

**Since:** the official reference says Orion Platform 2017.3 (NPM 12.2) and later.

No worked example or observed result is recorded. Constructed from the signature:

```sql
SELECT TOP 20
    n.Caption,
    Replace(n.Caption, '.example.com', '') AS ShortName
FROM Orion.Nodes n
```

`Replace` is a plain string substitution, not a regular expression. It is most often used to
normalise captions for grouping, and to strip a domain suffix so a node name matches a name
coming from another system.

### `ToLower(a)`

Converts `a` to all lowercase.

**Workbook baseline:** 2013.1

```sql
SELECT TOP 1 ToLower('TeStStRiNg') AS LowString
FROM Orion.Engines
```

**Result:** `teststring`

Useful for comparisons whose case you do not control. String comparison in SWQL is handed to
SQL Server and behaves according to the collation the Orion database was created with, which
is chosen at install time and is not consistent across installations: do not assume case
insensitivity, and do not assume case sensitivity. Folding both sides is what makes a match
case insensitive regardless of collation, and it costs you the index on the column. See
[gotchas.md](gotchas.md#10-string-comparison-collation-and-case).

### `ToUpper(a)`

Converts `a` to all uppercase.

**Workbook baseline:** 2013.1

```sql
SELECT TOP 1 ToUpper('TeStStRiNg') AS CapString
FROM Orion.Engines
```

**Result:** `TESTSTRING`

### `ToString(a)`

Converts `a` to a string. In most scenarios this conversion happens automatically when
needed by usage.

**Workbook baseline:** 2013.1

```sql
SELECT TOP 1 ToString(101) AS ResultColumn
FROM Orion.Engines
```

**Result:** `101`

Reach for it explicitly when you are concatenating a number or a date into a label, or when
you need [`Length`](#lengths) on something that is not already a string.

### `UriEquals(a, b)`

Returns true if SWIS Uri `a` refers to the same entity instance as SWIS Uri `b`.

No worked example or observed result is recorded. Constructed from the signature:

```sql
SELECT TOP 5 n.Caption, n.IPAddress
FROM Orion.Nodes n
WHERE UriEquals(n.Uri, 'swis://localhost./Orion/Orion.Nodes/NodeID=1')
```

Use it instead of `=` whenever one of the two URIs came from somewhere other than the query
you are writing now, for example an `EntityUri` stored on `Orion.AlertObjects` or a URI
persisted by an earlier script. The function compares what the URIs refer to rather than
comparing the two strings byte for byte. `Uri` itself is declared on `System.Entity`, so
every entity that descends from it has one; the URI format is covered in
[../swis/uris.md](../swis/uris.md).

### `EscapeSWISUriValue(a)`

Returns `a` with certain characters escaped. **Intended for internal use only**, in
SolarWinds' own words, so treat anything you build on it as liable to change.

**Workbook baseline:** 2013.1

```sql
SELECT TOP 1 Uri, EscapeSWISUriValue(Uri) AS c
FROM Orion.Engines
```

**Result:** `swis://Srvname./Orion/Orion.Engines/EngineID=1, "swis://Srvname./Orion/Orion.Engines/EngineID=1"`

The escaped form in that result is the original wrapped in double quotes, which is what
SWIS does to a URI value that has to survive being embedded in another URI.

---

## Reconciliation: where the sources disagree

Three discrepancies between the official reference and the community workbook show up in the
function data. Two of them are recorded explicitly in
[`data/reference/reconciliation.json`](../../data/reference/reconciliation.json): an
`undocumented-function` record for `ChangeTimeZone` and a `version-mismatch` record for
`WeekDay`. That file holds 14 records in all, and the other 12 are workbook entity names that
no longer resolve rather than function disagreements. The third discrepancy, the
`SplitStringToArray` delimiter, is not in that file at all; it is visible only by reading the
official description and the workbook's recorded example side by side in
[`data/reference/swql-functions.json`](../../data/reference/swql-functions.json). None of the
three can be settled from documentation alone, so each one comes with a test you can run on
your own server.

### `ChangeTimeZone` is not in the official reference

`ChangeTimeZone` is used in the community workbook but does not appear anywhere in the
official SWQL function reference. **Treat it as unverified.**

The workbook's description: the second argument must follow the standard timezone offset
format `+/-hh:mm`, the date in the database has its offset changed to the specified timezone
offset, and the `+` must be inside the quotes. The recorded example:

```sql
SELECT TOP 1 ChangeTimeZone(KeepAlive, '+05:00') AS ColumnResult
FROM Orion.Engines
```

**Result:** `2015-09-25 21:21:45` (recorded against a 2011.1 baseline)

**How to test it on your own server:** run that query in SWQL Studio. If the function does
not exist on your version, SWIS rejects the query at compile time with an error naming the
function, so the test is immediate and harmless. If it does return a value, compare it with
`SELECT TOP 1 KeepAlive FROM Orion.Engines` to see whether the offset moved the way you
expect before you build anything on it.

Do not use `ChangeTimeZone` in a saved report, alert or automation without that test.
`ToLocal` and `ToUtc` are documented, do the two conversions almost everyone actually needs,
and are the right default.

### `WeekDay`: 2016.1 or 2015.2?

The official reference says `WeekDay` is "Available in Orion Platform 2016.1 and later". The
community workbook records a successful run with a minimum core version of **2015.2**. Both
statements are in the data, and they cannot both be the first version.

The likeliest explanation is that the function shipped before it was documented, but this
repository has no evidence that settles it. If you are on a platform between 2015.2 and
2016.1 and need `WeekDay`, test it rather than assuming either source:

```sql
SELECT TOP 1 WeekDay(KeepAlive) AS ColumnResult
FROM Orion.Engines
```

On anything from 2016.1 onwards, which is every currently supported release, the question is
moot.

### `SplitStringToArray`: which delimiter?

The official reference says `SplitStringToArray(a)` "splits string `a` on comma separators".
The workbook's recorded example splits `'Hello|§|§|world'` into `[Hello, world]`, which is a
split on `|§|§|`, not on a comma.

These cannot both describe the same behaviour. Possible readings are that the delimiter
changed between versions, that the workbook input suffered a character encoding accident on
its way into the document, or that the function accepts more than one separator. Nothing here
resolves it.

**Verify the delimiter on your own version before relying on it.** The test from the
[`SplitStringToArray`](#splitstringtoarraya) entry above takes ten seconds:

```sql
SELECT TOP 1
    ArrayLength(SplitStringToArray('alpha,beta')) AS Elements,
    ArrayValueAt(SplitStringToArray('alpha,beta'), 1) AS SecondElement
FROM Orion.Engines
```

`Elements = 2` and `SecondElement = beta` means comma splitting, as documented. `Elements = 1`
means your version splits on something else, and you should not use the function until you
know what.

---

## What is not in the function library

The official reference is a closed list, and several things people reach for out of T-SQL
habit are simply not on it:

| Missing | Use instead |
|:---|:---|
| `CAST` / `CONVERT` | [`ToString(a)`](#tostringa) and [`DateTime`](#datetime); most conversions happen implicitly |
| `COALESCE` | [`IsNull(a, b)`](#isnulla-b), nested if you need more than two arguments |
| `Count(*)` | `Count(<key property>)`, for example `Count(NodeID)` |
| `LTRIM` / `RTRIM` | Not documented. `SubString` plus `CharIndex` can do a fixed trim |
| `LEFT` / `RIGHT` | [`SubString(s, start, length)`](#substrings-start-length) |
| `DATEPART(quarter, ...)` | [`QuarterOfYear(d)`](#quarterofyeard) |
| `'quarter'` as an `AddDate` unit | `AddMonth(3 * n, d)`; `'quarter'` is a `DateTrunc` datepart only |
| Regular expressions | Not documented. `LIKE` for pattern matching, `CharIndex` for containment |

That a function is absent from the reference does not prove SWIS rejects it. It proves you
have no supported guarantee, so if you find one that works, treat it the way this page treats
`ChangeTimeZone`: test it, and note in your own documentation that it is undocumented.

## See also

- [date-and-time.md](date-and-time.md) for the date functions in depth, the `GetUtcDate()`
  plus `AddX` trap, and the relative-time filtering patterns.
- [language-reference.md](language-reference.md) for the clauses these functions sit inside:
  `GROUP BY`, `HAVING`, `CASE`, `UNION`, `WITH`.
- [joins-and-navigation.md](joins-and-navigation.md) for reaching the entity whose property
  you want to pass to one of these functions.
- [../reference/swql-function-index.md](../reference/swql-function-index.md) for the same 63
  functions as a scannable table.
- The official [SWQL function reference](https://solarwinds.github.io/OrionSDK/docs/swql-functions/)
  and its [possible issues](https://solarwinds.github.io/OrionSDK/docs/swql-functions/possible-issues/)
  page.

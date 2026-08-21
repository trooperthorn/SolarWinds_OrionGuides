<!-- GENERATED FILE. Do not edit by hand.
     Produced by tools/build_reference_docs.py from data/schema/2026.2/.
     Regenerate with: make docs-reference -->

# SWQL function index

63 functions, of which 62 appear in the official SolarWinds SWQL function reference. The remainder are attested only by a community workbook and are marked accordingly: they may work on your version, but verify before depending on them.

For the narrative version with worked examples and the date/time pitfalls, see [../swql/functions.md](../swql/functions.md) and [../swql/date-and-time.md](../swql/date-and-time.md).

## Aggregate

| Function | Since | Description | Example |
| --- | --- | --- | --- |
| `Avg(n)` | 2011.1 | Returns the average (arithmetic mean) of the values in the group. | `SELECT avg(SWISColumn) as ResultColumn FROM SWISTable` |
| `Count(n)` | 2011.1 | Returns the number of non-NULL values in the group. | `SELECT count(SWISColumn) as ResultColumn FROM SWISTable` |
| `Max(n)` | 2011.1 | Returns the largest value in the group. | `SELECT max(SWISColumn) as ResultColumn FROM SWISTable` |
| `Min(n)` | 2011.1 | Returns the smallest value in the group. | `SELECT min(SWISColumn) as ResultColumn FROM SWISTable` |
| `String_Agg(expression, separator [, orderExpression [ASC \| DESC]])` |  | Concatenates the non-NULL string values in the group into a single string, separated by separator. Both expression and separator… |  |
| `Sum(n)` | 2011.1 | Returns the arithmetic sum of the values in the group. | `SELECT sum(SWISColumn) as ResultColumn FROM SWISTable` |

## Array functions

| Function | Since | Description | Example |
| --- | --- | --- | --- |
| `ArrayContains(a, v)` |  | Returns true if array a contains value v. |  |
| `ArrayLength(a)` | 2015.1 | Returns the number of elements in array a. | `SELECT ArrayLength(MemberAncestorDetailsUrls) AS ColumnResult FROM Orion.Cont…` |
| `ArrayValueAt(a, i)` | 2015.1 | Returns the array element at position i in array a, counting from zero. | `SELECT ArrayValueAt(MemberAncestorDetailsUrls,0) AS ColumnResult FROM Orion.C…` |
| `SplitStringToArray(a)` | 2013.1 | Splits string a on comma separators into an array of substrings. | `SELECT SplitStringToArray('Hello\|§\|§\|world') as a FROM Orion.Engines` |

## Date Time

| Function | Since | Description | Example |
| --- | --- | --- | --- |
| `ChangeTimeZone` ⚠️ | 2011.1 | The second argument needs to follow the standard timezone offset +/-hh:mm . The date in the database will have its offset changed… | `SELECT ChangeTimeZone(KeepAlive,'+05:00') as ColumnResult FROM Orion.Engines` |

## Date/time

| Function | Since | Description | Example |
| --- | --- | --- | --- |
| `AddDate(u, n, d)` | 2014.2 | Returns a date n units after d, where the unit is specified by the first parameter u, which must be one of: 'millisecond', 'secon… | `SELECT AddDate('month', 2, KeepAlive) AS ColumnResult From Orion.Engines` |
| `AddDay(n, d)` | 2014.2 | Returns a date n days after d. | `SELECT AddDay(17, KeepAlive) AS ColumnResult From Orion.Engines` |
| `AddHour(n, d)` | 2014.2 | Returns a date n hours after d. | `SELECT Addhour(1, KeepAlive) AS ColumnResult From Orion.Engines` |
| `AddMillisecond(n, d)` | 2014.2 | Returns a date n milliseconds after d. | `SELECT AddMillisecond(1, NextPoll) AS NextPoll From Orion.Nodes` |
| `AddMinute(n, d)` | 2014.2 | Returns a date n minutes after d. | `SELECT Addminute(30, KeepAlive) AS ColumnResult From Orion.Engines` |
| `AddMonth(n, d)` | 2014.2 | Returns a date n months after d. | `SELECT AddMonth(5, KeepAlive) AS ColumnResult From Orion.Engines` |
| `AddSecond(n, d)` | 2014.2 | Returns a date n seconds after d. | `SELECT AddSecond(13, KeepAlive) AS ColumnResult From Orion.Engines` |
| `AddWeek(n, d)` | 2014.2 | Returns a date n weeks after d. | `SELECT AddWeek(7, KeepAlive) AS ColumnResult From Orion.Engines` |
| `AddYear(n, d)` | 2014.2 | Returns a date n years after d. | `SELECT AddYear(5, KeepAlive) AS ColumnResult From Orion.Engines` |
| `DateTime` | 2011.1 | Converts a string to a date. In most scenarios this conversion will happen automatically when needed by usage. | `SELECT KeepAlive FROM Orion.Engines where KeepAlive > DateTime('9/25/2015 3:4…` |
| `DateTrunc('datepart', 'd')` | 2011.1 | Where 'datepart' is one of the following strings: 'minute', 'hour', 'day', 'week', 'month', 'quarter', 'year'. Returns a date lik… | `SELECT DateTrunc('month', KeepAlive) as ColumnResult FROM Orion.Engines` |
| `Day(d)` | 2011.1 | Returns the day of the month of d. | `SELECT Day(KeepAlive) as ColumnResult from orion.engines` |
| `DayDiff(a, b)` | 2011.1 | Returns the number of days (rounded to the nearest integer) that b is later than a. | `SELECT DayDiff(KeepAlive,KeepAlive+28) as ColumnResult from orion.engines` |
| `DayOfYear(d)` | 2011.1 | Returns the day of year of d. January 1 is 1, February 1 is 32, etc. | `SELECT DayofYear(KeepAlive) as ColumnResult from orion.engines` |
| `Downsample(d, p)` | 2018.3 | Rounds the supplied timestamp d to the defined time period p.  For example, a period of '00:15:00' would round to the nearest 15… |  |
| `GetDate()` | 2011.1 | Returns the current date in local time at the Orion server. | `SELECT getdate() as ResultCoumn FROM Orion.Engines` |
| `GetUtcDate()` | 2011.1 | Returns the current date and time in UTC. Please note possible issues. | `SELECT GetUtcDate() as ResultColumn FROM Orion.Engines` |
| `Hour(d)` | 2011.1 | Returns the hour part of d (in 24 hour format). | `SELECT Hour(KeepAlive) as ColumnResult from orion.engines` |
| `HourDiff(a, b)` | 2011.1 | Returns the number of hours (rounded to the nearest integer) that b is later than a. | `SELECT HourDiff(KeepAlive,KeepAlive+28) as ColumnResult from orion.engines` |
| `Millisecond(d)` | 2011.1 | Returns the millisecond part of d. | `SELECT MilliSecond(KeepAlive) as ColumnResult from orion.engines` |
| `MillisecondDiff(a, b)` | 2011.1 | Returns the number of milliseconds (rounded to the nearest integer) that b is later than a. | `SELECT MillisecondDiff(KeepAlive,KeepAlive+24) as ColumnResult from orion.eng…` |
| `Minute` | 2011.1 | Returns the minute part of d. | `SELECT Minute(KeepAlive) as ColumnResult from orion.engines` |
| `MinuteDiff(a, b)` | 2011.1 | Returns the number of minutes (rounded to the nearest integer) that b is later than a. | `SELECT MinuteDiff(KeepAlive,KeepAlive+28) as ColumnResult from orion.engines` |
| `Month` | 2011.1 | Returns the month part of d. January is 1. | `SELECT Month(KeepAlive) as ColumnResult from orion.engines` |
| `MonthDiff(a, b)` | 2011.1 | Returns the number of months (rounded to the nearest integer) that b is later than a. | `SELECT MonthDiff(KeepAlive,KeepAlive+28) as ColumnResult from orion.engines` |
| `QuarterOfYear(d)` | 2011.1 | Returns the quarter of the year that contains d. January, February, and March are 1; April, May, and June are 2; etc. | `SELECT QuarterofYear(KeepAlive) as ColumnResult from orion.engines` |
| `Second(d)` | 2011.1 | Returns the second part of d. | `SELECT Second(KeepAlive) as ColumnResult from orion.engines` |
| `SecondDiff(a, b)` | 2011.1 | Returns the number of seconds (rounded to the nearest integer) that b is later than a. | `SELECT SecondDiff(KeepAlive, KeepAlive + 1) as a FROM Orion.Engines` |
| `ToLocal(d)` | 2011.1 | Converts d to local time on the Orion server. | `SELECT Tolocal(getutcdate()) as ResultColumn FROM Orion.Engines` |
| `ToUtc` | 2011.1 | Converts d to UTC time. | `SELECT ToUtc(getdate()) as ResultColumn FROM Orion.Engines` |
| `Week(d)` | 2011.1 | Returns the week number of d. | `SELECT Week(KeepAlive) as ColumnResult from orion.engines` |
| `WeekDay(d)` | 2016.1 | Returns the day of the week of d as a number, with Sunday = 0, Monday = 1, ..., Saturday = 6. Available in Orion Platform 2016.1… | `SELECT WeekDay(KeepAlive) as ColumnResult from orion.engines` |
| `WeekDiff(a, b)` | 2011.1 | Returns the number of weeks (rounded to the nearest integer) that b is later than a. | `SELECT WeekDiff(KeepAlive,KeepAlive+28) as ColumnResult from orion.engines` |
| `Year(d)` | 2011.1 | Returns the year of d. | `SELECT Year(KeepAlive) as ColumnResult from orion.engines` |
| `YearDiff(a, b)` | 2011.1 | Returns the number of years (rounded to the nearest integer) that b is later than a. | `SELECT YearDiff(KeepAlive,'1/01/2020 0:0:0 AM') as ColumnResult from orion.en…` |

## General

| Function | Since | Description | Example |
| --- | --- | --- | --- |
| `Case when c then a else b end` |  | Returns a if c is true else returns b. |  |
| `IsNull(a, b)` | 2011.1 | Returns a unless it is NULL, else returns b. | `SELECT Restart, IsNull(restart, '9/25/2015 3:49:54') as ColumnResult FROM Ori…` |
| `UNION(q)` |  | Adds the results of an additional query q directly below the former, the number of columns must match between unioned queries |  |

## Numeric

| Function | Since | Description | Example |
| --- | --- | --- | --- |
| `Abs(n)` | 2011.1 | Returns the absolute value of n. | `SELECT abs(-1) as ResultColumn FROM SWISTable` |
| `Ceiling(n)` | 2013.1 | Returns the smallest integer that is not less than n. | `SELECT ceiling(ResponseTime) as ResultColumn FROM Orion.Nodes` |
| `Floor(n)` | 2013.1 | Returns the largest integer that is not greater than n. | `SELECT floor(ResponseTime) as ResultColumn FROM Orion.Nodes` |
| `Round(n, p)` | 2013.1 | Returns n rounded to the p decimal places. | `SELECT round(ResponseTime, PercentLoss) as ResultColumn FROM Orion.Nodes` |

## String

| Function | Since | Description | Example |
| --- | --- | --- | --- |
| `CharIndex(toFind, toSearch [, start])` | 2018.2 | Returns the position at which toFind occurs within toSearch (starting at position start, if provided) or zero if toFind is not fo… |  |
| `Concat(a, b, c, ...)` | 2013.1 | Takes one or more arguments and returns a single string that is the concatenation of the values of the arguments. | `SELECT Concat ('The ', 'most ','awesome ', 'string') as ConString from Orion.…` |
| `EscapeSWISUriValue(a)` | 2013.1 | Returns a with certain characters escaped. Intended for internal use only. | `SELECT Uri, EscapeSWISUriValue(Uri) as c FROM Orion.Engines` |
| `Length(s)` | 2015.2 | Returns the length of string s. | `SELECT Length(ServerName) as NameLength FROM Orion.Engines` |
| `Replace(expression, pattern, replacement)` | 2017.3 | Replaces all occurrences of a specified string (pattern) value in expression with another string value (replacement). Supported s… |  |
| `SubString(s, start, length)` | 2013.1 | Returns a substring of length characters starting at position start (the first character is position 1). | `SELECT SubString ('123456789', 3, 6) as TestSubString from Orion.Engines` |
| `ToLower(a)` | 2013.1 | Converts a to all lowercase. | `SELECT ToLower ('TeStStRiNg') as LowString from Orion.Engines` |
| `ToString(a)` | 2013.1 | Converts a to a string. In most scenarios this conversion will happen automatically when needed by usage. | `SELECT ToString(101) as ResultColumn FROM SWISTable` |
| `ToUpper(a)` | 2013.1 | Converts a to all uppercase. | `SELECT ToUpper ('TeStStRiNg') as CapString from Orion.Engines` |
| `UriEquals(a, b)` |  | Returns true if SWIS Uri a refers to the same entity instance as SWIS Uri b. |  |

---

⚠️ marks a function that is not in the official reference. `Since` is the earliest version the function is attested in; where the official reference and the workbook disagree, both figures are recorded in [`data/reference/reconciliation.json`](../../data/reference/reconciliation.json).

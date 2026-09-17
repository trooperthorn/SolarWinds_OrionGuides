# Call Queries: VNQM call detail widgets

[custom-query-widget.md](custom-query-widget.md) explains the `_LinkFor_` convention with a
single worked widget. This page is a set of six built for one job: reporting on the call
detail records that VoIP & Network Quality Manager collects from Cisco Unified Communications
Manager. They are the widgets a VoIP team asks for first — who called 911, who talks
longest, who calls most, and which callers present a number that does not fit the dial plan —
and each one links its rows to the phone, the call and the call manager.

The set was built for a customer deployment in September 2026 and every query on this page
validates against the 2026.2 schema with `tools/validate_swql.py`. What the schema cannot
verify is the widget's own behaviour, and that is the second subject of this page: the Custom
Query widget has **three** query boxes, not one, and the other two are documented nowhere in
enough detail to use them.

## The three query boxes

The widget's edit form offers, in order:

| Field | Runs when | What it must return |
| --- | --- | --- |
| **Custom SWQL Query** | every page load | the table: visible columns plus their `_LinkFor_` and `_IconFor_` directives |
| **Auto-hide SWQL Query** | before the main query, if *Auto-hide the resource if there is no data to display* is ticked | anything at all; the widget hides itself when this returns **no rows** |
| **Search SWQL Query** | in place of the main query, when the viewer has typed in the search box (*Enable search* ticked) | the same columns as the main query, with `${SEARCH_STRING}` somewhere in its `WHERE` |

SolarWinds' own page says of the auto-hide box only that you can "enter a query to further
define which data are automatically hidden", and of the search box that `${SEARCH_STRING}` is
"a macro for the string you want to search". The three facts below are what those sentences
leave out, and they are **reported from practice and unverified here**, in the same sense as
everything else in this section: the schema does not describe the widget.

**The search query replaces the main query; it does not filter its output.** When text is in
the search box the widget runs the search query and renders whatever it returns. Two things
follow. The search query has to select the same columns, `_LinkFor_` directives included, or
the links vanish while a search is active. And on an aggregated widget the `${SEARCH_STRING}`
condition belongs in the `WHERE` clause before `GROUP BY`, so the counts are recomputed for
the matching calls rather than filtering a finished top-25 list.

**`${SEARCH_STRING}` is substituted as plain text.** It must sit inside the quotes of a
`LIKE '%${SEARCH_STRING}%'`. A single quote typed in the search box produces a query error
rather than a result, and `%` or `_` typed by the viewer act as wildcards, which for a phone
engineer is usually the point: `55%` finds every number that starts with 55. SWIS is
read-only and the widget runs as the viewing user, so the exposure is a broken widget, not
a changed database. See
[../automation/accounts-and-permissions.md](../automation/accounts-and-permissions.md).

**The auto-hide query is a separate query, so make it cheap.** The edit form's *Add Query*
button copies the main query into the auto-hide box, which means the 67-column read with its
navigation joins runs twice per page load. The pattern used below is a `SELECT TOP 1` of one
column with the main query's `WHERE` clause and nothing else: it stops at the first matching
row and hides the widget under exactly the condition the main query would draw an empty
table. The cost of the pattern is a maintenance rule: when the dial strings or the time window
change, all three queries of that widget change together. If the auto-hide `WHERE` drifts from
the main `WHERE`, the widget either hides while it has rows or shows an empty table.

## The entity and its links

Every widget reads `Orion.IpSla.VoipCallDetails`, one row per call, described in
[../modules/vnqm.md](../modules/vnqm.md#calls-and-call-detail-records). Three of its seven
navigation properties carry the link targets, so no console URL is built by hand and nothing
here depends on a NetObject prefix:

| Visible column | Link source | Console page |
| --- | --- | --- |
| Call Time | `v.DetailsUrl` | VoIP Call Details, NetObject `VCDS` |
| Calling Number, Originating Device | `v.OriginPhone.DetailsUrl` | VoIP Phone, NetObject `VCCMP` |
| Called Number | `v.DestinationPhone.DetailsUrl` | VoIP Phone |
| Call Manager | `v.CCMMonitoring.DetailsUrl` | VoIP CallManager, NetObject `VCCM` |

`OriginPhone` and `DestinationPhone` resolve to `Orion.IpSla.CCMPhones`, and `CCMMonitoring`
to `Orion.IpSla.CCMMonitoring`; both declare `DetailsUrl`. The `Orion.IpSla.VoipCallDetails`
row has its own `DetailsUrl`, which is why the Call Time link works on every row while the
phone links do not: a call that originates on a gateway or a trunk has no `OriginPhone`, the
navigation yields `NULL`, and the widget renders the number as plain text. That the widget
renders an empty link value as text rather than as a dead link is **reported from practice and
unverified here**.

**Aggregated widgets wrap the link in `MAX()`.** SWQL requires every selected column to be
grouped or aggregated, and a `_LinkFor_` column is a selected column like any other. Grouping
by calling number and selecting `MAX(v.OriginPhone.DetailsUrl)` validates and links the number
to a phone. When one calling number is presented by several phones the link goes to whichever
URL sorts last; the count is unaffected.

## Two adjustments before deploying

**Emergency dial strings.** The queries treat `911` and `9911` as emergency calls, checked
against both `FinalCalledPartyNumber` and `OriginalCalledPartyNumber` because a translation
pattern can rewrite the dialed digits before the CDR is written. A site that dials `8911` or
sends `+1911` needs those in every `IN (...)` list, in all three queries of widgets 1 and 6.

**The time window.** Every query looks back 30 days with `AddDay(-30, GetDate())`. The
timestamps on `Orion.IpSla.VoipCallDetails` are in the call manager's local time, as
[../modules/vnqm.md](../modules/vnqm.md#the-call-manager-side) explains under
`UtcOffsetMinutes`, so server-local `GetDate()` is the nearest comparable clock. Do not
substitute `GetUtcDate()`: see [../swql/date-and-time.md](../swql/date-and-time.md) for why
`AddDay(-30, GetUtcDate())` is wrong in a different way as well.

## Widget settings

The same for all six. In the widget's edit form:

| Field | Value |
| --- | --- |
| Title | the widget's heading below |
| Custom SWQL Query | the *Main query* |
| Auto-hide the resource if there is no data to display | ticked, with the *Auto-hide query* in the box that appears |
| Enable search | ticked, with the *Search query* in the box that appears |
| Number of Rows Per Page | 25 |

Auto-hide is supplied for all six but suits four of them. On widgets 1, 4, 5 and 6 an empty
table is the healthy state and a widget that disappears is the right signal. On widgets 2 and
3 an empty table means CDR collection has stopped, which is worth leaving visible.

Do not end any of the queries with a comment: the widget appends clauses of its own, and a
trailing comment swallows them. That much SolarWinds does document.

## 1. Calls placed to 911

The 25 most recent, newest first.

Main query:

```sql
SELECT TOP 25
    v.DateTimeOrigination                    AS [Call Time],
    v.DetailsUrl                             AS [_LinkFor_Call Time],
    v.CallingPartyNumber                     AS [Calling Number],
    v.OriginPhone.DetailsUrl                 AS [_LinkFor_Calling Number],
    IsNull(v.OrigPhoneName, v.OrigDeviceName) AS [Originating Device],
    v.OriginPhone.DetailsUrl                 AS [_LinkFor_Originating Device],
    v.OrigCCMRegionName                      AS [Region],
    v.FinalCalledPartyNumber                 AS [Dialed],
    v.Duration                               AS [Duration (s)],
    CASE WHEN v.CallSuccess = TRUE THEN 'Yes' ELSE 'No' END AS [Connected],
    v.CallManagerName                        AS [Call Manager],
    v.CCMMonitoring.DetailsUrl               AS [_LinkFor_Call Manager]
FROM Orion.IpSla.VoipCallDetails v
WHERE (v.FinalCalledPartyNumber IN ('911', '9911')
    OR v.OriginalCalledPartyNumber IN ('911', '9911'))
  AND v.DateTimeOrigination >= AddDay(-30, GetDate())
ORDER BY v.DateTimeOrigination DESC
```

Auto-hide query:

```sql
SELECT TOP 1 v.CallID
FROM Orion.IpSla.VoipCallDetails v
WHERE (v.FinalCalledPartyNumber IN ('911', '9911')
    OR v.OriginalCalledPartyNumber IN ('911', '9911'))
  AND v.DateTimeOrigination >= AddDay(-30, GetDate())
```

Search query:

```sql
SELECT TOP 25
    v.DateTimeOrigination                    AS [Call Time],
    v.DetailsUrl                             AS [_LinkFor_Call Time],
    v.CallingPartyNumber                     AS [Calling Number],
    v.OriginPhone.DetailsUrl                 AS [_LinkFor_Calling Number],
    IsNull(v.OrigPhoneName, v.OrigDeviceName) AS [Originating Device],
    v.OriginPhone.DetailsUrl                 AS [_LinkFor_Originating Device],
    v.OrigCCMRegionName                      AS [Region],
    v.FinalCalledPartyNumber                 AS [Dialed],
    v.Duration                               AS [Duration (s)],
    CASE WHEN v.CallSuccess = TRUE THEN 'Yes' ELSE 'No' END AS [Connected],
    v.CallManagerName                        AS [Call Manager],
    v.CCMMonitoring.DetailsUrl               AS [_LinkFor_Call Manager]
FROM Orion.IpSla.VoipCallDetails v
WHERE (v.FinalCalledPartyNumber IN ('911', '9911')
    OR v.OriginalCalledPartyNumber IN ('911', '9911'))
  AND v.DateTimeOrigination >= AddDay(-30, GetDate())
  AND (   v.CallingPartyNumber   LIKE '%${SEARCH_STRING}%'
       OR v.OrigPhoneName        LIKE '%${SEARCH_STRING}%'
       OR v.OrigDeviceName       LIKE '%${SEARCH_STRING}%'
       OR v.OrigCCMPhoneIPAddress LIKE '%${SEARCH_STRING}%'
       OR v.OrigCCMRegionName    LIKE '%${SEARCH_STRING}%'
       OR v.CallManagerName      LIKE '%${SEARCH_STRING}%')
ORDER BY v.DateTimeOrigination DESC
```

## 2. Top 25 longest calls

Ranked by `Duration`, with both legs' MOS so a long call that was also a bad one stands out.
`Duration > 0` excludes the zero-duration records CUCM writes for unanswered attempts.

Main query:

```sql
SELECT TOP 25
    v.DateTimeOrigination        AS [Call Time],
    v.DetailsUrl                 AS [_LinkFor_Call Time],
    v.Duration                   AS [Duration (s)],
    v.CallingPartyNumber         AS [Calling Number],
    v.OriginPhone.DetailsUrl     AS [_LinkFor_Calling Number],
    v.FinalCalledPartyNumber     AS [Called Number],
    v.DestinationPhone.DetailsUrl AS [_LinkFor_Called Number],
    v.OrigCCMRegionName          AS [From Region],
    v.DestCCMRegionName          AS [To Region],
    v.OrigMOS                    AS [Orig MOS],
    v.DestMOS                    AS [Dest MOS],
    v.CallManagerName            AS [Call Manager],
    v.CCMMonitoring.DetailsUrl   AS [_LinkFor_Call Manager]
FROM Orion.IpSla.VoipCallDetails v
WHERE v.DateTimeOrigination >= AddDay(-30, GetDate())
  AND v.Duration > 0
ORDER BY v.Duration DESC
```

Auto-hide query:

```sql
SELECT TOP 1 v.CallID
FROM Orion.IpSla.VoipCallDetails v
WHERE v.DateTimeOrigination >= AddDay(-30, GetDate())
  AND v.Duration > 0
```

Search query:

```sql
SELECT TOP 25
    v.DateTimeOrigination        AS [Call Time],
    v.DetailsUrl                 AS [_LinkFor_Call Time],
    v.Duration                   AS [Duration (s)],
    v.CallingPartyNumber         AS [Calling Number],
    v.OriginPhone.DetailsUrl     AS [_LinkFor_Calling Number],
    v.FinalCalledPartyNumber     AS [Called Number],
    v.DestinationPhone.DetailsUrl AS [_LinkFor_Called Number],
    v.OrigCCMRegionName          AS [From Region],
    v.DestCCMRegionName          AS [To Region],
    v.OrigMOS                    AS [Orig MOS],
    v.DestMOS                    AS [Dest MOS],
    v.CallManagerName            AS [Call Manager],
    v.CCMMonitoring.DetailsUrl   AS [_LinkFor_Call Manager]
FROM Orion.IpSla.VoipCallDetails v
WHERE v.DateTimeOrigination >= AddDay(-30, GetDate())
  AND v.Duration > 0
  AND (   v.CallingPartyNumber     LIKE '%${SEARCH_STRING}%'
       OR v.FinalCalledPartyNumber LIKE '%${SEARCH_STRING}%'
       OR v.OrigPhoneName          LIKE '%${SEARCH_STRING}%'
       OR v.DestPhoneName          LIKE '%${SEARCH_STRING}%'
       OR v.OrigCCMRegionName      LIKE '%${SEARCH_STRING}%'
       OR v.DestCCMRegionName      LIKE '%${SEARCH_STRING}%'
       OR v.CallManagerName        LIKE '%${SEARCH_STRING}%')
ORDER BY v.Duration DESC
```

## 3. Top 25 originating phone numbers

Grouped by `CallingPartyNumber`, ranked by call count. The empty-string test matters: CUCM
writes a blank calling party for some gateway-originated calls, and without it the blank
group is usually the top row.

Main query:

```sql
SELECT TOP 25
    v.CallingPartyNumber                AS [Calling Number],
    MAX(v.OriginPhone.DetailsUrl)       AS [_LinkFor_Calling Number],
    MAX(IsNull(v.OrigPhoneName, v.OrigDeviceName)) AS [Device],
    MAX(v.OrigCCMRegionName)            AS [Region],
    COUNT(v.CallID)                     AS [Calls],
    SUM(v.Duration)                     AS [Total Seconds],
    SUM(CASE WHEN v.CallSuccess = TRUE THEN 0 ELSE 1 END) AS [Failed],
    MAX(v.DateTimeOrigination)          AS [Last Call],
    MAX(v.CallManagerName)              AS [Call Manager],
    MAX(v.CCMMonitoring.DetailsUrl)     AS [_LinkFor_Call Manager]
FROM Orion.IpSla.VoipCallDetails v
WHERE v.DateTimeOrigination >= AddDay(-30, GetDate())
  AND v.CallingPartyNumber IS NOT NULL
  AND v.CallingPartyNumber <> ''
GROUP BY v.CallingPartyNumber
ORDER BY COUNT(v.CallID) DESC
```

Auto-hide query:

```sql
SELECT TOP 1 v.CallID
FROM Orion.IpSla.VoipCallDetails v
WHERE v.DateTimeOrigination >= AddDay(-30, GetDate())
  AND v.CallingPartyNumber IS NOT NULL
  AND v.CallingPartyNumber <> ''
```

Search query:

```sql
SELECT TOP 25
    v.CallingPartyNumber                AS [Calling Number],
    MAX(v.OriginPhone.DetailsUrl)       AS [_LinkFor_Calling Number],
    MAX(IsNull(v.OrigPhoneName, v.OrigDeviceName)) AS [Device],
    MAX(v.OrigCCMRegionName)            AS [Region],
    COUNT(v.CallID)                     AS [Calls],
    SUM(v.Duration)                     AS [Total Seconds],
    SUM(CASE WHEN v.CallSuccess = TRUE THEN 0 ELSE 1 END) AS [Failed],
    MAX(v.DateTimeOrigination)          AS [Last Call],
    MAX(v.CallManagerName)              AS [Call Manager],
    MAX(v.CCMMonitoring.DetailsUrl)     AS [_LinkFor_Call Manager]
FROM Orion.IpSla.VoipCallDetails v
WHERE v.DateTimeOrigination >= AddDay(-30, GetDate())
  AND v.CallingPartyNumber IS NOT NULL
  AND v.CallingPartyNumber <> ''
  AND (   v.CallingPartyNumber LIKE '%${SEARCH_STRING}%'
       OR v.OrigPhoneName      LIKE '%${SEARCH_STRING}%'
       OR v.OrigDeviceName     LIKE '%${SEARCH_STRING}%'
       OR v.OrigCCMRegionName  LIKE '%${SEARCH_STRING}%'
       OR v.CallManagerName    LIKE '%${SEARCH_STRING}%')
GROUP BY v.CallingPartyNumber
ORDER BY COUNT(v.CallID) DESC
```

## 4. Calls from non-7-digit originating numbers

The 25 most recent calls whose calling party is not exactly seven characters: internal
extensions, ten- and eleven-digit E.164 numbers, blank and anonymous callers. `Length()` is
the SWQL string function; a `NULL` calling party fails the comparison, hence the explicit
`IS NULL` branch.

Main query:

```sql
SELECT TOP 25
    v.DateTimeOrigination        AS [Call Time],
    v.DetailsUrl                 AS [_LinkFor_Call Time],
    v.CallingPartyNumber         AS [Calling Number],
    v.OriginPhone.DetailsUrl     AS [_LinkFor_Calling Number],
    Length(v.CallingPartyNumber) AS [Digits],
    IsNull(v.OrigPhoneName, v.OrigGatewayName) AS [Originating Device],
    v.OriginPhone.DetailsUrl     AS [_LinkFor_Originating Device],
    v.FinalCalledPartyNumber     AS [Called Number],
    v.DestinationPhone.DetailsUrl AS [_LinkFor_Called Number],
    v.Duration                   AS [Duration (s)],
    v.CallManagerName            AS [Call Manager],
    v.CCMMonitoring.DetailsUrl   AS [_LinkFor_Call Manager]
FROM Orion.IpSla.VoipCallDetails v
WHERE v.DateTimeOrigination >= AddDay(-30, GetDate())
  AND (v.CallingPartyNumber IS NULL OR Length(v.CallingPartyNumber) <> 7)
ORDER BY v.DateTimeOrigination DESC
```

Auto-hide query:

```sql
SELECT TOP 1 v.CallID
FROM Orion.IpSla.VoipCallDetails v
WHERE v.DateTimeOrigination >= AddDay(-30, GetDate())
  AND (v.CallingPartyNumber IS NULL OR Length(v.CallingPartyNumber) <> 7)
```

Search query:

```sql
SELECT TOP 25
    v.DateTimeOrigination        AS [Call Time],
    v.DetailsUrl                 AS [_LinkFor_Call Time],
    v.CallingPartyNumber         AS [Calling Number],
    v.OriginPhone.DetailsUrl     AS [_LinkFor_Calling Number],
    Length(v.CallingPartyNumber) AS [Digits],
    IsNull(v.OrigPhoneName, v.OrigGatewayName) AS [Originating Device],
    v.OriginPhone.DetailsUrl     AS [_LinkFor_Originating Device],
    v.FinalCalledPartyNumber     AS [Called Number],
    v.DestinationPhone.DetailsUrl AS [_LinkFor_Called Number],
    v.Duration                   AS [Duration (s)],
    v.CallManagerName            AS [Call Manager],
    v.CCMMonitoring.DetailsUrl   AS [_LinkFor_Call Manager]
FROM Orion.IpSla.VoipCallDetails v
WHERE v.DateTimeOrigination >= AddDay(-30, GetDate())
  AND (v.CallingPartyNumber IS NULL OR Length(v.CallingPartyNumber) <> 7)
  AND (   v.CallingPartyNumber     LIKE '%${SEARCH_STRING}%'
       OR v.FinalCalledPartyNumber LIKE '%${SEARCH_STRING}%'
       OR v.OrigPhoneName          LIKE '%${SEARCH_STRING}%'
       OR v.OrigGatewayName        LIKE '%${SEARCH_STRING}%'
       OR v.OrigCCMRegionName      LIKE '%${SEARCH_STRING}%'
       OR v.CallManagerName        LIKE '%${SEARCH_STRING}%')
ORDER BY v.DateTimeOrigination DESC
```

## 5. Top 25 non-7-digit calling numbers

Widget 4 rolled up by calling number. The `IsNull(..., '(blank)')` in both the select list
and the `GROUP BY` keeps the blank callers as one visible group rather than dropping them.

Main query:

```sql
SELECT TOP 25
    IsNull(v.CallingPartyNumber, '(blank)') AS [Calling Number],
    MAX(v.OriginPhone.DetailsUrl)           AS [_LinkFor_Calling Number],
    MAX(Length(v.CallingPartyNumber))       AS [Digits],
    MAX(IsNull(v.OrigPhoneName, v.OrigGatewayName)) AS [Device],
    MAX(v.OrigCCMRegionName)                AS [Region],
    COUNT(v.CallID)                         AS [Calls],
    SUM(v.Duration)                         AS [Total Seconds],
    MAX(v.DateTimeOrigination)              AS [Last Call],
    MAX(v.CallManagerName)                  AS [Call Manager],
    MAX(v.CCMMonitoring.DetailsUrl)         AS [_LinkFor_Call Manager]
FROM Orion.IpSla.VoipCallDetails v
WHERE v.DateTimeOrigination >= AddDay(-30, GetDate())
  AND (v.CallingPartyNumber IS NULL OR Length(v.CallingPartyNumber) <> 7)
GROUP BY IsNull(v.CallingPartyNumber, '(blank)')
ORDER BY COUNT(v.CallID) DESC
```

Auto-hide query:

```sql
SELECT TOP 1 v.CallID
FROM Orion.IpSla.VoipCallDetails v
WHERE v.DateTimeOrigination >= AddDay(-30, GetDate())
  AND (v.CallingPartyNumber IS NULL OR Length(v.CallingPartyNumber) <> 7)
```

Search query:

```sql
SELECT TOP 25
    IsNull(v.CallingPartyNumber, '(blank)') AS [Calling Number],
    MAX(v.OriginPhone.DetailsUrl)           AS [_LinkFor_Calling Number],
    MAX(Length(v.CallingPartyNumber))       AS [Digits],
    MAX(IsNull(v.OrigPhoneName, v.OrigGatewayName)) AS [Device],
    MAX(v.OrigCCMRegionName)                AS [Region],
    COUNT(v.CallID)                         AS [Calls],
    SUM(v.Duration)                         AS [Total Seconds],
    MAX(v.DateTimeOrigination)              AS [Last Call],
    MAX(v.CallManagerName)                  AS [Call Manager],
    MAX(v.CCMMonitoring.DetailsUrl)         AS [_LinkFor_Call Manager]
FROM Orion.IpSla.VoipCallDetails v
WHERE v.DateTimeOrigination >= AddDay(-30, GetDate())
  AND (v.CallingPartyNumber IS NULL OR Length(v.CallingPartyNumber) <> 7)
  AND (   v.CallingPartyNumber LIKE '%${SEARCH_STRING}%'
       OR v.OrigPhoneName      LIKE '%${SEARCH_STRING}%'
       OR v.OrigGatewayName    LIKE '%${SEARCH_STRING}%'
       OR v.OrigCCMRegionName  LIKE '%${SEARCH_STRING}%'
       OR v.CallManagerName    LIKE '%${SEARCH_STRING}%')
GROUP BY IsNull(v.CallingPartyNumber, '(blank)')
ORDER BY COUNT(v.CallID) DESC
```

## 6. Top 25 phones placing 911 calls

Widget 1 rolled up by calling number, with the phone's IP address alongside because that is
what the person tracing a misdialled emergency call reaches for next.

Main query:

```sql
SELECT TOP 25
    v.CallingPartyNumber                AS [Calling Number],
    MAX(v.OriginPhone.DetailsUrl)       AS [_LinkFor_Calling Number],
    MAX(IsNull(v.OrigPhoneName, v.OrigDeviceName)) AS [Device],
    MAX(v.OrigCCMPhoneIPAddress)        AS [Phone IP],
    MAX(v.OrigCCMRegionName)            AS [Region],
    COUNT(v.CallID)                     AS [911 Calls],
    SUM(CASE WHEN v.CallSuccess = TRUE THEN 1 ELSE 0 END) AS [Connected],
    MAX(v.DateTimeOrigination)          AS [Last 911 Call],
    MAX(v.CallManagerName)              AS [Call Manager],
    MAX(v.CCMMonitoring.DetailsUrl)     AS [_LinkFor_Call Manager]
FROM Orion.IpSla.VoipCallDetails v
WHERE (v.FinalCalledPartyNumber IN ('911', '9911')
    OR v.OriginalCalledPartyNumber IN ('911', '9911'))
  AND v.DateTimeOrigination >= AddDay(-30, GetDate())
GROUP BY v.CallingPartyNumber
ORDER BY COUNT(v.CallID) DESC
```

Auto-hide query:

```sql
SELECT TOP 1 v.CallID
FROM Orion.IpSla.VoipCallDetails v
WHERE (v.FinalCalledPartyNumber IN ('911', '9911')
    OR v.OriginalCalledPartyNumber IN ('911', '9911'))
  AND v.DateTimeOrigination >= AddDay(-30, GetDate())
```

Search query:

```sql
SELECT TOP 25
    v.CallingPartyNumber                AS [Calling Number],
    MAX(v.OriginPhone.DetailsUrl)       AS [_LinkFor_Calling Number],
    MAX(IsNull(v.OrigPhoneName, v.OrigDeviceName)) AS [Device],
    MAX(v.OrigCCMPhoneIPAddress)        AS [Phone IP],
    MAX(v.OrigCCMRegionName)            AS [Region],
    COUNT(v.CallID)                     AS [911 Calls],
    SUM(CASE WHEN v.CallSuccess = TRUE THEN 1 ELSE 0 END) AS [Connected],
    MAX(v.DateTimeOrigination)          AS [Last 911 Call],
    MAX(v.CallManagerName)              AS [Call Manager],
    MAX(v.CCMMonitoring.DetailsUrl)     AS [_LinkFor_Call Manager]
FROM Orion.IpSla.VoipCallDetails v
WHERE (v.FinalCalledPartyNumber IN ('911', '9911')
    OR v.OriginalCalledPartyNumber IN ('911', '9911'))
  AND v.DateTimeOrigination >= AddDay(-30, GetDate())
  AND (   v.CallingPartyNumber    LIKE '%${SEARCH_STRING}%'
       OR v.OrigPhoneName         LIKE '%${SEARCH_STRING}%'
       OR v.OrigDeviceName        LIKE '%${SEARCH_STRING}%'
       OR v.OrigCCMPhoneIPAddress LIKE '%${SEARCH_STRING}%'
       OR v.OrigCCMRegionName     LIKE '%${SEARCH_STRING}%'
       OR v.CallManagerName       LIKE '%${SEARCH_STRING}%')
GROUP BY v.CallingPartyNumber
ORDER BY COUNT(v.CallID) DESC
```

## When it does not work

| Symptom | Cause |
| --- | --- |
| A column shows URLs instead of links | The `_LinkFor_` suffix does not match the visible alias exactly, spaces and case included |
| Links work until something is typed in the search box | The search query's select list has drifted from the main query's |
| The widget is hidden while calls exist | The auto-hide `WHERE` no longer matches the main `WHERE`, usually after one was edited for a new dial string or window |
| An error after typing in the search box | The text contained a single quote |
| Rows older than a few weeks are missing | Retention has moved them to `Orion.IpSla.VoipCallDetailsHist`, which has the same columns but no navigation properties, so a historical variant would join `Orion.IpSla.CCMPhones` by hand on `OrigCCMPhoneMacAddress = MACAddress` |

## What is not verified here

- Everything in [the three query boxes](#the-three-query-boxes) about how the widget runs
  its auto-hide and search queries and substitutes `${SEARCH_STRING}` is reported from
  practice and **unverified here**; SolarWinds documents the fields but not the behaviour.
- That the widget renders a `NULL` link value as plain text is **unverified here**.
- The queries validate against the 2026.2 schema but were **not executed against a live
  server** before publication. The customer deployment they were written for is the first
  live run.

## See also

- [custom-query-widget.md](custom-query-widget.md) — the `_LinkFor_` convention these widgets
  depend on
- [../modules/vnqm.md](../modules/vnqm.md) — `Orion.IpSla.VoipCallDetails`, its navigation
  properties, and the retention split with `VoipCallDetailsHist`
- [../swql/date-and-time.md](../swql/date-and-time.md) — why the window uses `GetDate()`
- [../swql/performance.md](../swql/performance.md) — what three queries per widget per page
  load cost
- [../reference/netobject-types.md](../reference/netobject-types.md) — `VCDS`, `VCCMP` and
  `VCCM`

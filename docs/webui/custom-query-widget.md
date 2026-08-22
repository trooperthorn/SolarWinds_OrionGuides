# The Custom Query widget

The **Custom Query** widget renders a SWQL query as a table on any view. That much is
documented. What is not documented anywhere in SolarWinds' own material is that the widget
reads the *names of your columns* as instructions: an alias of a particular shape stops being
a column and becomes formatting applied to a different column.

That convention is the whole subject of this page. It is what turns a flat table of text into
the linked, icon-bearing widget the console's own resources use, and nothing tells you it
exists.

## The naming convention

A column aliased `[_LinkFor_X]` is not displayed. Its value becomes the hyperlink target for
the column aliased `X`. A column aliased `[_IconFor_X]` is not displayed either; its value is
treated as an image path and rendered as an icon beside `X`.

```sql
SELECT
    n.Caption,
    n.DetailsUrl AS [_LinkFor_Caption]
FROM Orion.Nodes n
ORDER BY n.Caption
```

That renders one column, `Caption`, with every row a link into the node's details view. The
second column is consumed rather than shown.

**The suffix must match the alias exactly, including case.** If the visible column is aliased
`NODE`, the link column has to be `[_LinkFor_NODE]` and not `[_LinkFor_Node]`. This is the
single most common reason the convention appears not to work: the query runs, the widget
renders, and the extra column simply shows up as a literal column of URLs because nothing
matched it.

Rename the visible column and you must rename the directive with it:

```sql
SELECT
    n.Caption AS [Device],
    n.DetailsUrl AS [_LinkFor_Device]
FROM Orion.Nodes n
ORDER BY n.Caption
```

Whether the `_LinkFor_` and `_IconFor_` prefixes themselves are case-sensitive is **not
documented by SolarWinds and is unverified here** — community examples write both
`[_LinkFor_NODE]` and `[_linkfor_Caption]` and report both working. The suffix is the part
that has to match. Writing the prefix in a consistent case costs nothing and removes the
question.

## Where the link value comes from

`DetailsUrl` is a `System.String` declared on **254 entities**, and on most of them it is
exactly the value this convention wants. Selecting it is easier and more durable than
building the URL yourself:

```sql
SELECT
    i.Caption AS [Interface],
    i.DetailsUrl AS [_LinkFor_Interface],
    n.Caption AS [Node],
    n.DetailsUrl AS [_LinkFor_Node]
FROM Orion.NPM.Interfaces i
JOIN Orion.Nodes n ON n.NodeID = i.NodeID
ORDER BY n.Caption, i.Caption
```

When an entity has no `DetailsUrl`, the URL is built by hand from a NetObject string. The
pattern is a console page plus a `NetObject` query parameter carrying the prefix and the id:

| Object | URL |
| --- | --- |
| Node | `/Orion/NetPerfMon/NodeDetails.aspx?NetObject=N%3a<NodeID>` |
| SAM application | `/Orion/APM/ApplicationDetails.aspx?NetObject=AA%3a<ApplicationID>` |
| SAM component | `/Orion/APM/MonitorDetails.aspx?NetObject=AM%3a<ComponentID>` |

`%3a` is a URL-encoded colon, so `N%3a42` is `N:42`. The prefixes are the same NetObject
prefixes the API uses — see
[../reference/netobject-types.md](../reference/netobject-types.md) for the full table.

Built by hand, that looks like this. Note `ToString()` around the id, because the id is an
integer and SWQL will not concatenate one to a string:

```sql
SELECT
    n.Caption AS [NODE],
    '/Orion/NetPerfMon/NodeDetails.aspx?NetObject=N%3a' + ToString(n.NodeID) AS [_LinkFor_NODE]
FROM Orion.Nodes n
ORDER BY n.Caption
```

These console paths are **not part of the SWIS schema and are unverified here**. They are
observed from the product's own pages and from community material, and a release is free to
move them. `DetailsUrl` is the durable form precisely because the platform maintains it.

## Where the icon value comes from

`_IconFor_` wants an image path. Two sources exist and they are not equally available.

**`StatusIcon`, where the entity has it.** It is a `System.String` holding the icon filename,
and it is declared on only **seven entities**: `Orion.Nodes`, `Orion.NPM.Interfaces`,
`Orion.Volumes`, `Orion.NodeChildStatusContributors`, `Orion.NodeChildStatusDetail`,
`Orion.PM.PAS.WsusNodesOrionNodes` and `Orion.PM.PAS.WsusServerNodes`.

```sql
SELECT
    i.Caption AS [Interface],
    i.StatusIcon AS [_IconFor_Interface],
    i.DetailsUrl AS [_LinkFor_Interface]
FROM Orion.NPM.Interfaces i
ORDER BY i.Caption
```

Note that one visible column takes both directives at once. `Interface` gets an icon from one
hidden column and a link from another.

Whether `StatusIcon` holds a bare filename or a path the widget can use unmodified is **not
recorded in the schema and is unverified here**. Community examples use it directly and also
prefix it with `/Orion/images/StatusIcons/`; read a few values on your own server to see which
form yours holds.

**Built from `StatusDescription` everywhere else.** `StatusDescription` is declared on 78
entities, and the console's status icons are named after it:

```sql
SELECT
    c.ComponentName AS [CMPNT],
    '/Orion/images/StatusIcons/Small-' + c.StatusDescription + '.gif' AS [_IconFor_CMPNT]
FROM Orion.APM.Component c
ORDER BY c.ComponentName
```

That is string concatenation against a value the platform sets, so it breaks if a status
description ever contains a character that is not filename-safe, or if the icon set is
renamed. It is the pattern the community uses because there is no alternative on an entity
without `StatusIcon`. The `Small-` prefix and `.gif` extension are **unverified here**.

## A worked widget

This is the community's canonical example, and it is worth reading as a whole because it
applies six directives to five visible columns. It returns every SAM component that is not up,
with the statistic and the error message each one reported, and makes every cell a link into
the right details page.

```sql
SELECT
    '' AS SEV,
    n.Caption AS NODE,
    a.Name AS APP,
    c.ComponentName AS CMPNT,
    ce.AvgStatisticData AS STAT,
    ce.ErrorMessage AS MSG,
    '/Orion/images/StatusIcons/Small-' + c.StatusDescription + '.gif' AS [_IconFor_SEV],
    '/Orion/NetPerfMon/NodeDetails.aspx?NetObject=N%3a' + ToString(n.NodeID) AS [_LinkFor_NODE],
    '/Orion/APM/ApplicationDetails.aspx?NetObject=AA%3a' + ToString(a.ApplicationID) AS [_LinkFor_APP],
    '/Orion/APM/MonitorDetails.aspx?NetObject=AM%3a' + ToString(c.ComponentID) AS [_LinkFor_CMPNT],
    '/Orion/APM/MonitorDetails.aspx?NetObject=AM%3a' + ToString(c.ComponentID) AS [_LinkFor_STAT],
    '/Orion/APM/MonitorDetails.aspx?NetObject=AM%3a' + ToString(c.ComponentID) AS [_LinkFor_MSG]
FROM Orion.APM.Component(nolock=true) c
JOIN Orion.APM.CurrentComponentStatus(nolock=true) ccs ON c.ComponentID = ccs.ComponentID
JOIN Orion.APM.ChartEvidence(nolock=true) ce ON ce.ComponentStatusID = ccs.ComponentStatusID
JOIN Orion.APM.Application(nolock=true) a ON c.ApplicationID = a.ApplicationID
JOIN Orion.Nodes(nolock=true) n ON a.NodeID = n.NodeID
WHERE ce.AvgStatisticData IS NOT NULL
  AND a.StatusDescription NOT IN ('Unmanaged')
  AND c.StatusDescription NOT IN ('Up')
```

Four things in it are worth naming.

**`'' AS SEV` is a column that exists only to carry an icon.** It selects an empty string, so
the cell has no text, and `[_IconFor_SEV]` fills it with a status image. That is how you get a
column that is nothing but an icon — there is no directive for "icon with no text", so you
make the text empty.

**One hidden column can only serve one visible column**, which is why `_LinkFor_CMPNT`,
`_LinkFor_STAT` and `_LinkFor_MSG` all repeat the same expression. Three columns linking to
the same page need three directives.

**The three-hop join to a component's message is not obvious.** The error message lives on
`Orion.APM.ChartEvidence`, which keys on `ComponentStatusID`, which comes from
`Orion.APM.CurrentComponentStatus`, which keys on `ComponentID`. `Orion.APM.Component` does
not carry the message itself.

**`(nolock=true)` is a table hint**, written directly against the entity name. It is the SWQL
equivalent of a T-SQL `NOLOCK`, and community material uses it throughout on widget queries
because a widget runs on every page load. It permits dirty reads. What it means for a query
that spans several statistics tables is **not documented by SolarWinds and is unverified
here**; see [../swql/performance.md](../swql/performance.md) for what a widget query costs and
[../swql/gotchas.md](../swql/gotchas.md) for reading uncommitted data.

Source: [SWQL link to node](https://thwack.solarwinds.com/products/network-performance-monitor-npm/f/forum/55612/swql-link-to-node)
on THWACK, and the component-status widget thread it grew out of. Credit to the THWACK
community, including Petr Vilem and lukas.belza.

## Practical notes

**Every entity and column above exists in 2026.2.** The queries on this page are validated
against the extracted schema like every other query in this repository. What is *not*
validated, and cannot be, is the widget's behaviour: the directive names, the console URLs and
the icon paths are product UI, not schema, and this repository has no way to check them. They
are marked unverified where they appear.

**Aliases with an underscore need brackets.** `[_LinkFor_NODE]` is bracketed because the
identifier starts with an underscore. Dropping the brackets is a parse error, not a silent
failure, so this one announces itself.

**Test the query in SWQL Studio first, then paste it in.** A widget that returns nothing and a
widget whose query is wrong look identical on the page. See
[../swis/metadata-introspection.md](../swis/metadata-introspection.md) and
`tools/validate_swql.py` in this repository:

```bash
python3 tools/validate_swql.py -
```

**Account limitations apply to the widget.** It runs as the viewing user, so two people on the
same page can see different row counts. See
[../automation/accounts-and-permissions.md](../automation/accounts-and-permissions.md).

## See also

- [README.md](README.md) for the rest of this section
- [../reference/netobject-types.md](../reference/netobject-types.md) for the NetObject
  prefixes the console URLs use
- [../swql/functions.md](../swql/functions.md) for `ToString()` and string concatenation
- [../swql/performance.md](../swql/performance.md) for what a widget query costs on every page
  load
- [../modules/sam.md](../modules/sam.md) for the SAM entities in the worked example

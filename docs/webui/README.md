# The web console

Most of this repository is about SWIS: the API, the schema, and automating against them. This
section is about the other interface — the web console that SolarWinds Observability
Self-Hosted presents to its users — and specifically about the parts of it that take SWQL and
are not documented anywhere official.

That is a narrower subject than "how to use the console", and deliberately so. Navigating the
UI is covered by SolarWinds' product documentation and needs no help from here. What has no
documentation is the set of conventions the console applies to a query you give it: column
names that are read as instructions, URL shapes that link one view to another, values that are
rendered as images rather than text. Those are discoverable only from community threads, and
they are what this section collects.

## A caveat that applies to the whole section

**The schema cannot confirm any of it.** Everywhere else in this repository, a claim is
checked against the extracted contract before it is written down, and `make check` fails if it
drifts. The console's behaviour is not in the contract. A directive name, a console URL, an
icon path — none of these appear in `data/`, so nothing here can verify that the widget still
reads `[_LinkFor_X]` or that `/Orion/NetPerfMon/NodeDetails.aspx` still exists.

What *is* verified is everything a query touches: every entity, property and function named on
these pages is checked against 2026.2 like any other page here, and the queries are run
through `tools/validate_swql.py`. So the SWQL is sound and the UI conventions around it are
reported, sourced and marked unverified. Read
[../reference/unverified.md](../reference/unverified.md) for the collected list.

## The pages

| Page | Covers |
| --- | --- |
| [custom-query-widget.md](custom-query-widget.md) | Turning a SWQL result into a linked, icon-bearing table: the `_LinkFor_` and `_IconFor_` column conventions, console URL shapes, and a worked widget |

## Where these come from

Community material, chiefly [THWACK](https://thwack.solarwinds.com/), which is where the
conventions on these pages were worked out and written down by the people who found them.
Each page names its sources. Where a claim is one person's report rather than something
reproduced widely, it says so.

If you confirm or contradict any of it on your own server, that is exactly the contribution
this section needs — see [../../CONTRIBUTING.md](../../CONTRIBUTING.md).

## See also

- [../swql/README.md](../swql/README.md) for the query language these conventions wrap
- [../swql/functions.md](../swql/functions.md) for string concatenation and `ToString()`
- [../reference/netobject-types.md](../reference/netobject-types.md) for the NetObject
  prefixes that appear in console URLs
- [../automation/accounts-and-permissions.md](../automation/accounts-and-permissions.md) for
  why two users can see different rows in the same widget

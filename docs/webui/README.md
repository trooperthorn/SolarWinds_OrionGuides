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
| [variables.md](variables.md) | `${Value}` and `${N=Namespace;M=Member}`: what resolves them, how to enumerate the valid members for any entity, and the variables by module |
| [variables-reference.md](variables-reference.md) | The published tables: `Alerting`, `Generic`, `OrionGroup`, node, volume, UPS, syslog and trap variables |
| [variables-undocumented.md](variables-undocumented.md) | Schema members that appear in no published table, derived and annotated as inference |
| [perfstack.md](perfstack.md) | Generating a Performance Analysis view from a URL: the chart grammar, and links from alerts and reports |
| [custom-query-widget.md](custom-query-widget.md) | Turning a SWQL result into a linked, icon-bearing table: the `_LinkFor_` and `_IconFor_` column conventions, console URL shapes, and a worked widget |
| [ncm-change-templates.md](ncm-change-templates.md) | What an NCM config change template is, its directives, the parameters that become form fields, and managing them through `Cirrus.ConfigSnippets` |
| [ncm-change-template-language.md](ncm-change-template-language.md) | The template scripting language: variables and macros, operators, string functions, loops, CLI blocks and custom properties |
| [modern-dashboards.md](modern-dashboards.md) | The Modern Dashboard export format, field by field: the envelope, the 12-column grid, the three widget types and the duplication that breaks files |
| [modern-dashboard-authoring.md](modern-dashboard-authoring.md) | Producing a dashboard file by hand, from a script, or by prompting an AI system, with the invariants that decide whether it works; also the console workflow itself — building, reusing and navigating to a widget |

[custom-query-widget.md](custom-query-widget.md) and [modern-dashboards.md](modern-dashboards.md)
cover two separate widget systems, not an old and a new version of the same one: a Modern
Dashboard widget cannot be placed on a classic dashboard, in either direction — see
[the note on modern-dashboards.md](modern-dashboards.md#modern-dashboard-widgets-do-not-work-on-classic-dashboards).
If you are not sure which console you are looking at, that is the question to answer first.

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

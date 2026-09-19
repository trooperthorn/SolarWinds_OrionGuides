# The web console

This section covers query-driven widgets, dashboard export structure, variables, and
console links. Evidence comes from SolarWinds product documentation, supplied exports,
and attributed community reports. A convention absent from the SWIS schema can still
be documented by an authoritative product source.

## A caveat that applies to the whole section

Schema checks can establish referenced entities and properties within the validator's
scope. They cannot establish URL availability, widget rendering, access-control behavior,
or the importer's identity-conflict rules. Keep those separate from syntax validation.
The 2026.4 export audit preserves observed configuration and reports gaps against the
older 2026.2 public schema; it does not certify exported queries on a target server.

Use the [evidence rules](../reference/documentation-audit-2026-09-18.md) and
[unverified index](../reference/unverified.md). Attribute community observations to their
source and version instead of presenting them as either universal facts or worthless
because they are not schema facts.

## The pages

| Page | Covers |
| --- | --- |
| [variables.md](variables.md) | `${Value}` and `${N=Namespace;M=Member}`: what resolves them, how to enumerate the valid members for any entity, and the variables by module |
| [variables-reference.md](variables-reference.md) | The published tables: `Alerting`, `Generic`, `OrionGroup`, node, volume, UPS, syslog and trap variables |
| [variables-undocumented.md](variables-undocumented.md) | Schema members that appear in no published table, derived and annotated as inference |
| [perfstack.md](perfstack.md) | Generating a Performance Analysis view from a URL: the chart grammar, and links from alerts and reports |
| [custom-query-widget.md](custom-query-widget.md) | Turning a SWQL result into a linked, icon-bearing table: the `_LinkFor_` and `_IconFor_` column conventions, console URL shapes, and a worked widget |
| [custom-query-call-queries.md](custom-query-call-queries.md) | Six VNQM call detail widgets for Cisco Unified CM, each with its main, auto-hide and search query, and what the widget's other two query boxes and `${SEARCH_STRING}` actually do |
| [ncm-change-templates.md](ncm-change-templates.md) | What an NCM config change template is, its directives, the parameters that become form fields, and managing them through `Cirrus.ConfigSnippets` |
| [ncm-change-template-language.md](ncm-change-template-language.md) | The template scripting language: variables and macros, operators, string functions, loops, CLI blocks and custom properties |
| [modern-dashboards.md](modern-dashboards.md) | The Modern Dashboard export format, field by field: the envelope, the 12-column grid, the three widget types and the duplication that breaks files |
| [modern-dashboard-2026-4-export-audit.md](modern-dashboard-2026-4-export-audit.md) | 127 exported dashboards: eight widget types, provider contracts, view hierarchy, formatting, context, and version limits |
| [modern-dashboard-widget-identity-audit.md](modern-dashboard-widget-identity-audit.md) | Sean/emcel package identities, conflicting widgets, deliberate sharing, and import preflight |
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
- [../guides/webview-embedding-and-node-mapping.md](../guides/webview-embedding-and-node-mapping.md)
  for embedding an external page with the Custom HTML widget, and for `Orion.WorldMap.Point`

<!-- GENERATED FILE. Do not edit by hand.
     Produced by tools/build_unverified_index.py from the documentation itself.
     Regenerate with: make docs-reference -->

# What this repository does not verify

Everything in these guides was checked against the extracted SolarWinds schema before it was written, and every SWQL statement is re-checked on each build. Some things cannot be checked that way: behaviour that only a running server exhibits, values that are installation data rather than schema, and the handful of places where SolarWinds' own documentation and their published contract disagree.

The rule is that those say so rather than being asserted quietly or dropped. This page collects every such statement in one place, because an admission is in the right place on its page and the wrong place when you want the whole picture.

**30 statements across 16 pages.**

Read this before relying on this repository for something load-bearing. If you have a live server, this is also the working list: most entries name the `Metadata.*` query or the experiment that would close the gap. See [../swis/metadata-introspection.md](../swis/metadata-introspection.md).

## [hardware-health.md](../modules/hardware-health.md)

**[Enabling and disabling individual sensors](../modules/hardware-health.md#enabling-and-disabling-individual-sensors)**

- The shape of that key object is not described in the schema or the Swagger contract, so *the exact structure to pass is unverified here.* `Metadata.VerbArgument` on your own server carries an `XmlTemplate` column that shows the shape SWIS expects for complex arguments, which is the reliable way to find out:

## [ipam.md](../modules/ipam.md)

**[Just looking, not claiming](../modules/ipam.md#just-looking-not-claiming)**

- It appears in the rendered schema pages with **no parameters and an unknown return type**, and it is absent from the 2026.2 Swagger contract entirely, so its signature is **unverified here**.
**[DHCP and DNS server management](../modules/ipam.md#dhcp-and-dns-server-management)**

- Treat the `credentials` and `propertiesToUpdate` key/value arrays as unverified in content and inspect `Metadata.VerbArgument.XmlTemplate` on your own server for the keys they expect.

## [ncm.md](../modules/ncm.md)

**[Gotchas](../modules/ncm.md#gotchas)**

- Whether `ClearTransfers` is present but undocumented on a given server is **unverified here**; check with `SELECT VerbName FROM Metadata.Verb WHERE EntityName = 'Cirrus.ConfigArchive' ORDER BY VerbName`.

## [npm.md](../modules/npm.md)

**[Gotchas](../modules/npm.md#gotchas)**

- Whether the `Base` entities are present but undocumented on a live server is unverified here; check with `SELECT FullName FROM Metadata.Entity WHERE FullName LIKE 'Orion.NetPath.%'`.

## [nta.md](../modules/nta.md)

**[Lookup entities](../modules/nta.md#lookup-entities)**

- `Multiport` and `MapTo` on `Orion.Netflow.Applications` carry no description in the published schema, so their semantics are **unverified** here.
**[`Orion.Netflow.InterfaceSources`](../modules/nta.md#orionnetflowinterfacesources)**

- Its `FlowExporterConfiguration` type is declared in SolarWinds' Swagger contract as a bare object with **no properties**, so the field names it expects are **unverified**.
**[Gotchas](../modules/nta.md#gotchas)**

- Whether verbs exist there on a live server is **unverified**; check with `SELECT v.Entity.FullName, v.Name FROM Metadata.Verb v WHERE v.Entity.FullName LIKE 'Orion.Netflow.%'`.

## [qoe.md](../modules/qoe.md)

**[Applications are the centre of the model](../modules/qoe.md#applications-are-the-centre-of-the-model)**

- `Filter` is the expression that matches traffic to this application and `FilterSyntax` presumably names the dialect it is written in, but neither carries a description in the schema, so the exact grammar is **unverified** here.
**[The catalogue behind an application](../modules/qoe.md#the-catalogue-behind-an-application)**

- `IsVisible` on the protocol likewise has no description, so what a `FALSE` there suppresses is unverified.
**[Probes](../modules/qoe.md#probes)**

- The schema does not say what distinguishes a setting from a property, and no valid names are enumerated, so both are **unverified** in content.
- Given that the two deployment verbs are `DeployLocalTrafficProbe` and `DeploySpanPortProbe`, it is a reasonable guess that `Mode` distinguishes those two deployment styles, but that is an inference and is **not verified** by the schema.
**[What is not verified here](../modules/qoe.md#what-is-not-verified-here)**

- ## What is not verified here

## [sam.md](../modules/sam.md)

**[Gotchas](../modules/sam.md#gotchas)**

- This behaviour is unverified here*: neither the schema nor the contract records it.
- This verb is not in the extracted 2026.2 schema and not in the Swagger contract*, so it is unverified here.

## [vnqm.md](../modules/vnqm.md)

**[MOS, jitter and the other quality metrics](../modules/vnqm.md#mos-jitter-and-the-other-quality-metrics)**

- They are listed in [what is not verified here](#what-is-not-verified-here) with a query that shows you the observed range on your own server.
**[What is not verified here](../modules/vnqm.md#what-is-not-verified-here)**

- ## What is not verified here

## [wpm.md](../modules/wpm.md)

**[What is not verified here](../modules/wpm.md#what-is-not-verified-here)**

- ## What is not verified here

## [entity-model.md](../schema/entity-model.md)

**[The tree is rooted at System.Entity](../schema/entity-model.md#the-tree-is-rooted-at-systementity)**

- Treat it as unverified.

## [status-codes.md](../schema/status-codes.md)

**[Resolving status on a live server](../schema/status-codes.md#resolving-status-on-a-live-server)**

- The published 2026.2 schema gives no summary text for any of these twelve, so the names and types above are verified but their meanings beyond the obvious are unverified.
**[`Status` versus `PolledStatus`](../schema/status-codes.md#status-versus-polledstatus)**

- How the two differ is **not verified**: the published 2026.2 schema attaches no summary text to either property, and neither the OrionSDK documentation nor any SolarWinds sample script in this repository's sources explains it.

## [date-and-time.md](../swql/date-and-time.md)

**[`DateTime` literals and parameters](../swql/date-and-time.md#datetime-literals-and-parameters)**

- If you must use a literal, the ISO 8601 form `'2026-01-01T00:00:00'` is the conventional choice for unambiguity, but its acceptance by SWIS is **unverified** here: no published SolarWinds example uses it.

## [functions.md](../swql/functions.md)

**[`UNION(q)`](../swql/functions.md#unionq)**

- `UNION ALL` is **unverified**: only `UNION` is documented.
**[`ChangeTimeZone` is not in the official reference](../swql/functions.md#changetimezone-is-not-in-the-official-reference)**

- Treat it as unverified.

## [gotchas.md](../swql/gotchas.md)

**[SWQL gotchas](../swql/gotchas.md#swql-gotchas)**

- Where something is widely believed but could not be verified from the schema, the official docs or SolarWinds' own samples, it is marked **unverified** and comes with a query you can run on your own server to settle it.
**[1. The empty result set is usually a permissions answer](../swql/gotchas.md#1-the-empty-result-set-is-usually-a-permissions-answer)**

- The schema publishes no summary for either, so what exactly `IsSwisLimitation` gates is **unverified** here; the name and the surrounding entity make it the first thing to look at when a limitation appears to affect the web console but not an API query.
**[6. To-many navigation multiplies rows and poisons aggregates](../swql/gotchas.md#6-to-many-navigation-multiplies-rows-and-poisons-aggregates)**

- Two counts rather than one because `Count(n)` is the only counting signature in SolarWinds' [documented function reference](https://solarwinds.github.io/OrionSDK/docs/swql-functions/); `COUNT(DISTINCT column)` is standard T-SQL and may well work, but it is **unverified** here.

## [language-reference.md](../swql/language-reference.md)

**[How this page marks its evidence](../swql/language-reference.md#how-this-page-marks-its-evidence)**

- Where a construct could not be corroborated at all, it is marked **unverified** with a one-line note on how to confirm it on your own server rather than being quietly dropped or quietly asserted.
**[UNION](../swql/language-reference.md#union)**

- `UNION ALL` is unverified.** The official reference documents only `UNION`.

## [performance.md](../swql/performance.md)

**[9. Bind parameters instead of building query text](../swql/performance.md#9-bind-parameters-instead-of-building-query-text)**

- Whether SWIS actually reuses a plan across executions of the same parameterised query is **unverified** here; you can test it on your own server by running the same query with different parameter values and comparing the timings reported by `WITH QUERYSTATS`. 3.

---

An entry here is not a defect. It is a statement that a reader should confirm before depending on it, and that this repository declines to guess about.

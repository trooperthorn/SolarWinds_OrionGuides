# Contributing

Contributions must distinguish published contracts, source documentation, observed exports,
and live behavior. State the source and version for a claim; explain what remains unknown.
See [the evidence rules](docs/reference/documentation-audit-2026-09-18.md).

## The one rule

**Do not write a schema fact you have not looked up.**

Entity names, property names, verb names and their parameter order, navigation properties,
status codes and SWQL function signatures are all easy to get subtly wrong from memory.
Look each one up. It costs one command:

```bash
python3 tools/schema_query.py find volume capacity --properties
python3 tools/schema_query.py show Orion.Volumes
python3 tools/schema_query.py props Orion.Nodes --grep unmanage
python3 tools/schema_query.py verb Orion.Nodes Unmanage
python3 tools/schema_query.py path Orion.APM.Component Orion.Nodes
```

If you cannot verify a claim, you can still include it. Mark it explicitly as unverified
and say how a reader can confirm it on their own server. Silence about uncertainty is the
thing to avoid, not uncertainty itself.

## What may be added

Use public vendor documentation, contributor-authored work against the published API,
and owner-authorized exports or derived evidence with explicit provenance. Do not imply
that a supplied customer export is an official vendor contract. Do not add restricted
vendor material from support cases, partner portals, or internal documents, or methods
of access beyond the documented customer-facing API. Owner authorization for an export
does not grant permission to republish unrelated restricted material.

## Before you open a pull request

```bash
make check
```

The gate runs tool tests, static SWQL checks, data/reference consistency checks, selected
command examples, dashboard and API Poller validation, internal links and anchors,
generated-index checks, and mutation checks of the gate itself. See the `check` target
in [Makefile](Makefile) for its current scope. These checks do not execute queries against
a live SolarWinds server, validate every Markdown assertion, or build all applications.

To check one query while you are writing it:

```bash
echo "SELECT n.Caption, n.Engine.ServerName FROM Orion.Nodes n" | python3 tools/validate_swql.py -
```

## What goes where

| Path | Contents | Edit by hand? |
| --- | --- | --- |
| `docs/platform/`, `docs/swis/`, `docs/swql/`, `docs/schema/`, `docs/automation/`, `docs/polling/`, `docs/webui/` | Written guides | Yes |
| `docs/reference/` | Generated enumerations plus authored audit/reference pages | Check the banner: regenerate generated pages; edit authored pages |
| `docs/TOC.md`, `llms-full.txt` | Generated from the pages under `docs/` | **No**, run `make docs-index` |
| `llms.txt` | The page-level index AI systems read first | Yes, and add every new page to it |
| `data/` | Extracted schema and reference data | **No**, run `make data` |
| `scripts/` | Sample queries and client scripts | Yes |
| `tools/` | Extraction, query, validation, generation | Yes |
| `reference/` | The source workbook the reference data is built from | Rarely |

Generated files carry a banner saying so. An edit to one will be overwritten by the next
build, so fix the generator instead. That is usually the better fix anyway: it corrects
every row rather than one.

One of them is generated from the prose rather than from `data/`:
`docs/reference/unverified.md` indexes recognized uncertainty markers in authored docs. If
your change adds, removes or rewords one of those, regenerate it in the same commit:

```bash
make docs-reference
```

CI regenerates and diffs, so a stale index fails the build the way a stale lockfile would.

The same applies to the AI-facing indexes. Adding, renaming or reheading a page under
`docs/` changes `docs/TOC.md` and `llms-full.txt`, so regenerate them in the same commit
with `make docs-index`, and list the new page in `llms.txt` with a one-line summary.
`make check` fails on a page that is missing from `llms.txt`, because a page the index
does not name is a page no AI system will find.

## Adding sample queries

Sample queries live in `scripts/swql/` grouped by subject. Each file opens with a comment
explaining what the entity is for, its key property and NetObject prefix, and any trap
specific to it. Each query gets a comment saying what it answers and why it is written
that way, because the interesting part is usually the reasoning, not the SQL.

Follow the conventions the existing files use, since they encode real constraints:

- Bound the result set with `TOP n` or `WITH ROWS a TO b`. There is no `SELECT *` in SWQL
  and an unbounded query against a large installation is a genuine production risk.
- Use bound parameters (`@name`) rather than string concatenation.
- Always time-bound queries against statistics, events, and history entities.
- Join `Orion.StatusInfo` rather than hard-coding status integers.
- Filter `UnManaged = FALSE` when you mean "actually broken" rather than "in a
  maintenance window".

Then validate:

```bash
python3 tools/validate_swql.py scripts/swql/your-file.swql
```

## Writing prose

Write for an engineer who has to make something work, and for the AI systems that read
this repository as a source of truth. Both are served by the same things: complete
sentences, the reason behind a rule rather than only the rule, and a worked example over
an abstract description.

Specifics:

- Every SWQL example must be runnable, with real verified names.
- Counts are checked. `tools/check_counts.py` reads sentences like "`Orion.Nodes` declares
  102 properties" and compares them against `data/`. If you mean a subset rather than a
  total, say so in the sentence: "two of its verbs", not "two verbs". The checker skips
  subset phrasings, and a reader needs the distinction anyway.
- Verb signatures are checked. `tools/check_signatures.py` reads a form like
  `` `Diff(configId1, configId2)` `` and compares the argument names and their order
  against the contract. Writing only the leading arguments is fine, since prose abbreviates
  a signature to its subject all the time, but the ones you do write must be in contract
  order. Arguments are positional, so this is the error that reaches a reader as a call
  that returns the wrong answer instead of one that fails.
- SWQL function calls are checked by argument count, since the reference gives their
  parameters placeholder names. Naming a function without arguments, `` `Avg()` ``, is
  read as a name rather than a call and is left alone.
- Link the official SolarWinds documentation where it already says something well, rather
  than paraphrasing it loosely.
- Cross-link sibling pages with relative links.
- No em dashes.
- No attribution footers, generation notices, or model names in committed files.

## Updating the schema data

The data is extracted from the `gh-pages` branch of the
[OrionSDK repository](https://github.com/solarwinds/OrionSDK), which is what serves
<https://solarwinds.github.io/OrionSDK/>.

```bash
make data                    # rebuild the default version (2026.2)
make data VERSION=2025.4     # or any version that branch publishes
make docs-reference          # regenerate the tables that depend on it
make check
```

Two sources are joined, because neither is sufficient alone. The docfx HTML carries entity
structure but flattens verb parameters into one run-on paragraph; the Swagger contract
carries typed parameters but no properties or relationships. `tools/build_schema_data.py`
parses both and joins them on the verb name.

If a schema page format changes and extraction breaks, `tools/check_data.py` should catch
it. If it does not, add an assertion there as part of the fix. A check that would have
caught the bug is a better outcome than the fix alone.

## Handling disagreements between sources

The official reference and the community workbook do not always agree. When they conflict,
record both rather than picking a winner: `tools/build_reference_data.py` emits
`data/reference/reconciliation.json` for exactly this, and the prose should surface the
conflict and say how to resolve it on a live server.

Entities renamed between versions are handled the same way. The build proposes a successor
where it can identify one confidently, and the NetObject reference marks the row.

## Scope

In scope: how the platform works, its schema and relationships, SWQL, the SWIS API surface,
and automation recipes.

Out of scope: credentials, hostnames, or any data from a real installation. Sanitize
examples. If you paste output, replace real names and addresses with example ones.

Also out of scope: destructive operations presented without their consequences. If a
script can delete or unmanage at scale, it should say so plainly, support `-WhatIf` or a
dry run where the language allows, and confirm before acting.

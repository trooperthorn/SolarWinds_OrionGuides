# Tools

No dependencies beyond the Python standard library, except `openpyxl` for reading the
source workbook and `mcp` for serving the MCP server. Five tools build, three consume, and
the rest guard.

**Build**

| Script | Purpose |
| --- | --- |
| [build_schema_data.py](build_schema_data.py) | Extract the SWIS schema from the OrionSDK sources into JSON |
| [build_reference_data.py](build_reference_data.py) | Merge the SWQL function reference with the examples workbook |
| [build_reference_docs.py](build_reference_docs.py) | Generate the enumerated tables in `docs/reference/` |
| [build_unverified_index.py](build_unverified_index.py) | Collect every statement the guides decline to assert into one page |
| [build_llms_index.py](build_llms_index.py) | Generate `docs/TOC.md` and `llms-full.txt` from the pages, and check `llms.txt` lists every page |

**Use**

| Script | Purpose |
| --- | --- |
| [schema_query.py](schema_query.py) | Explore the schema offline: entities, properties, verbs, join paths |
| [diff_schema.py](diff_schema.py) | Report what changed between two platform versions, and what breaks |
| [mcp_server.py](mcp_server.py) | Serve the schema lookups, the SWQL validator and the pages to an AI client over MCP |

**Guard**

Accuracy is the product, so most of the toolchain exists to keep it honest. Each of these
was written after a specific mistake got through. `check_counts.py` came from a page that
said six entities declared no operations and then listed five, when the real figure was
ten of twenty-one.

| Script | Catches |
| --- | --- |
| [validate_swql.py](validate_swql.py) | A query naming an entity, property, column or navigation that does not exist |
| [check_entity_references.py](check_entity_references.py) | The same in prose, plus wrong property types and invented NetObject prefixes or rights |
| [check_counts.py](check_counts.py) | A number in a sentence that the extracted data contradicts |
| [check_signatures.py](check_signatures.py) | A verb signature with its arguments wrong or out of order, or a function call with the wrong number |
| [check_examples.py](check_examples.py) | A documented command that does not run, or whose shown output is wrong |
| [check_data.py](check_data.py) | Extraction that degraded quietly, and reference pages that fell behind |
| [check_links.py](check_links.py) | A relative link or #anchor that no longer resolves |
| [check_dashboards.py](check_dashboards.py) | A shipped Modern Dashboard file that breaks one of the format's invariants |
| [audit_dashboard_identities.py](audit_dashboard_identities.py) | Repeated dashboard/widget identities across JSON and ZIP files, conflicting definitions and unresolved placements |
| [check_api_poller_templates.py](check_api_poller_templates.py) | A shipped API Poller template that breaks the export format, or hides unknown values |
| [check_gate.py](check_gate.py) | A check above that has stopped checking, by seeding errors it must catch |
| [test_tools.py](test_tools.py) | Regressions in the judgement above: 222 tests |

`check_gate.py` is the one that watches the others. A checker that quietly stops reading
what it claims to read still exits zero, which makes it indistinguishable from a working
one until something depends on it. So it seeds a real defect of each kind into a real page
-- a renamed entity, a count off by one, an argument inserted mid-signature, a stale
pasted output -- requires the check that owns it to object, and restores the page from
memory rather than from git, so it is safe to run with uncommitted work. Three checks in
this repository were passing over work they never did, and none of them looked any
different from the outside.

Beyond names and links, `check_data.py` also holds the documentation to its own claims:
the entity count each module page quotes for its namespace, the status tables written by
hand, the completeness of the function reference, the sample query count that three
separate files quote, and the PowerShell cmdlet names, which are easy to invent because a
plausible eighth reads exactly like the seven real ones.

Everything runs through the [Makefile](../Makefile):

```bash
make data            # rebuild data/ from the OrionSDK sources
make docs-reference  # regenerate docs/reference/
make schema-diff FROM=2025.4 TO=2026.2
make test            # the toolchain unit tests
make validate        # every sample query and every sql block in the docs
make check           # the whole gate: tests, queries, data, prose, counts, verbs, links
```

`make check` is what CI runs. It is deliberately strict, because the value of this
repository is that a reader does not have to verify it against a live server first.

## How extraction works

The schema comes from the `gh-pages` branch of
[solarwinds/OrionSDK](https://github.com/solarwinds/OrionSDK), which is what serves
<https://solarwinds.github.io/OrionSDK/>. For each published version that branch carries
two artifacts, and **neither is sufficient alone**:

| Artifact | Has | Lacks |
| --- | --- | --- |
| `<version>/schema/<Entity>.html` | Properties, relationships, verbs, access control, inheritance | Verb parameters, which are flattened into one run-on paragraph |
| `<version>/swagger.json` | Typed, named, ordered verb parameters and return types | Properties, relationships, inheritance |

`build_schema_data.py` parses both and joins them on the verb name. That join is what
turns a verb summary reading `"Starts realtime polling on Node entityNodeID of target
NodeOwner identifier that owns this polling..."` into five named, typed, ordered
parameters.

The HTML is parsed with regular expressions rather than an HTML library, because the
docfx output is regular enough and it keeps the tool runnable anywhere with a stock
Python 3. The risk with that choice is silent degradation: a template changes, a selector
stops matching, a section comes back empty, and the output is still valid JSON.
`check_data.py` exists to make that loud, through count floors, required core entities,
and three hand-verified verb signatures.

## Two things the tools know that the raw data does not

**Inherited members.** An entity page lists only the properties that entity declares.
`Uri` and `InstanceType` are on `System.Entity`; `UnManaged`, `UnManageFrom` and
`UnManageUntil` are on `System.ManagedEntity`. All of them are queryable on descendants.
`schema_query.py props` and `validate_swql.py` both resolve the inheritance chain, which
is why `Orion.Nodes.Uri` validates.

**Both relationship directions are navigable.** The schema splits relationships into
"Source" and "Target" tables, but both list navigation properties usable *from* the
declaring entity. `Orion.Nodes.Interfaces` (source) and `Orion.NPM.Interfaces.Node`
(target) are both valid SWQL. `schema_query.py path` walks both, which is what makes
`Orion.NPM.Interfaces.Node` resolve as a single hop rather than a three-hop detour.

## Adding a check

If a schema change breaks extraction and `check_data.py` does not catch it, add the
assertion there as part of the fix. A check that would have caught the bug is a better
outcome than the fix alone.

See [../CONTRIBUTING.md](../CONTRIBUTING.md).

## The MCP server

`schema_query.py` and `validate_swql.py` are what an AI system should run before it states
a schema fact, and only a client with a shell can run them. Claude Desktop, ChatGPT,
Copilot, Cursor and most other assistants speak the Model Context Protocol instead, so
`mcp_server.py` wraps the same commands as MCP tools. It reads the checked-in data and
pages, reaches no network and no SolarWinds server, and speaks to its client over stdio.

```bash
python3 tools/mcp_server.py --list-tools
```

```text
find_entities        Search entities by keyword; with properties=True also search property names.
show_entity          Everything about one entity: properties, relationships, verbs, access control.
entity_properties    List an entity's properties, inherited ones included unless inherited=False.
list_verbs           List Invoke verbs, filtered by entity and/or a keyword.
show_verb            One verb's parameters in positional order, required right, return shape, and call syntax.
entity_children      Entities that inherit from a base entity.
navigation_path      Navigation-property paths from one entity to another, for writing a join.
schema_stats         Counts and provenance of the extracted schema.
validate_query       Validate a SWQL query against the schema. Returns errors and warnings, empty when clean.
read_doc             Read one documentation page, sample script, or reference file by repository path.
search_docs          Find documentation lines containing a keyword (case-insensitive), with page and line number.
```

Serving needs the `mcp` package (`python3 -m pip install "mcp>=2"`; the 1.x package also
works). A client is pointed at the server with a command entry, which in Claude Desktop's
`claude_desktop_config.json`, Cursor's `mcp.json` and Copilot's `mcp.json` all take this
shape:

```json
{
  "mcpServers": {
    "orionguides": {
      "command": "python3",
      "args": ["/path/to/SolarWinds_OrionGuides/tools/mcp_server.py"]
    }
  }
}
```

Every tool returns the same JSON that `schema_query.py --json` prints, because it calls
the same functions. `read_doc` is limited to the documentation, the sample scripts, the
reference data and the root guides; it will not read the tools, the schema JSON, or
anything outside the repository.

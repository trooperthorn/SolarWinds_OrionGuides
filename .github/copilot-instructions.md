# GitHub Copilot

Read [AGENTS.md](../AGENTS.md) and follow it. It is the contract for every AI system working
in this repository, and this file exists only so Copilot finds it without being told.

The short version: never state a schema fact you have not looked up with
`tools/schema_query.py`, validate every SWQL query with `tools/validate_swql.py` before
handing it over, and run `make check` before finishing any change to the repository.

The page-level map is [llms.txt](../llms.txt) and the heading-level one is
[docs/TOC.md](../docs/TOC.md). Everything here derives from resources SolarWinds publishes
on the public internet; there is no SolarWinds internal material to find.

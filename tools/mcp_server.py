#!/usr/bin/env python3
"""Expose this repository's lookup tools to an AI client over the Model Context Protocol.

`schema_query.py` and `validate_swql.py` answer the questions an AI system needs answered
before it states a schema fact, but only a client that can run a shell can call them.
Claude Desktop, ChatGPT, Copilot, Cursor and the rest speak MCP, so this server wraps the
same commands as MCP tools. Nothing here reaches a network or a SolarWinds server: every
tool reads the checked-in data under `data/` and the pages under `docs/`, and the server
speaks to its client over stdio.

    python3 tools/mcp_server.py --list-tools     # what the server offers, no MCP SDK needed
    python3 tools/mcp_server.py                  # serve over stdio (what a client launches)

The `mcp` package is the only dependency, and only for serving:

    python3 -m pip install "mcp>=2"

A client is pointed at it with a command entry such as:

    {"mcpServers": {"orionguides": {"command": "python3",
                                    "args": ["/path/to/SolarWinds_OrionGuides/tools/mcp_server.py"]}}}

Every tool returns the same JSON the `--json` flag of `schema_query.py` prints, so an
answer produced through this server and one produced at a shell are the same answer.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import schema_query  # noqa: E402
import validate_swql  # noqa: E402

SERVER_NAME = "orionguides"
INSTRUCTIONS = (
    "Schema-grounded lookup for SolarWinds Orion / Observability Self-Hosted (SWIS, SWQL, "
    "platform version 2026.2). Never state an entity, property, verb, parameter order, or "
    "navigation property without looking it up here first, and validate every SWQL query "
    "with validate_swql before handing it to a user. All data derives from resources "
    "SolarWinds publishes on the public internet; the server contains no SolarWinds internal "
    "documentation and no access to any SolarWinds system. Start with read_doc('AGENTS.md')."
)

_schema: schema_query.Schema | None = None
_index: validate_swql.SchemaIndex | None = None


def schema() -> schema_query.Schema:
    global _schema
    if _schema is None:
        _schema = schema_query.Schema()
    return _schema


def index() -> validate_swql.SchemaIndex:
    global _index
    if _index is None:
        _index = validate_swql.SchemaIndex()
    return _index


def run_query(fn, **kwargs) -> dict | list:
    """Run one schema_query command in JSON mode and return what it would have printed.

    The commands are written for a terminal: they print, and they sys.exit with a message
    on an unknown name. Capturing both keeps this server a thin wrapper, so the CLI and
    the MCP tool cannot drift apart, and turns the exit into an error the client can show.
    """
    args = SimpleNamespace(json=True, **kwargs)
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            fn(schema(), args)
    except SystemExit as exc:
        return {"error": str(exc)}
    text = out.getvalue().strip()
    return json.loads(text) if text else {}


# --------------------------------------------------------------------------------------
# Tool implementations. Plain functions, so --list-tools and the tests can call them
# without the MCP SDK installed.
# --------------------------------------------------------------------------------------

def find_entities(terms: str, properties: bool = False, limit: int = 40) -> dict | list:
    """Search entities by keyword; with properties=True also search property names.

    terms: space-separated keywords, all of which must match.
    """
    return run_query(schema_query.cmd_find, terms=terms.split(), properties=properties, limit=limit)


def show_entity(entity: str, limit: int = 60) -> dict | list:
    """Everything about one entity: properties, relationships, verbs, access control."""
    return run_query(schema_query.cmd_show, entity=entity, limit=limit)


def entity_properties(entity: str, grep: str | None = None, inherited: bool = True) -> dict | list:
    """List an entity's properties, inherited ones included unless inherited=False."""
    return run_query(schema_query.cmd_props, entity=entity, grep=grep, no_inherited=not inherited)


def list_verbs(entity: str | None = None, grep: str | None = None, limit: int = 60) -> dict | list:
    """List Invoke verbs, filtered by entity and/or a keyword."""
    return run_query(schema_query.cmd_verbs, entity=entity, grep=grep, limit=limit)


def show_verb(entity: str, verb: str) -> dict | list:
    """One verb's parameters in positional order, required right, return shape, and call syntax."""
    return run_query(schema_query.cmd_verb, entity=entity, verb=verb)


def entity_children(entity: str, limit: int = 80) -> dict | list:
    """Entities that inherit from a base entity."""
    return run_query(schema_query.cmd_children, entity=entity, limit=limit)


def navigation_path(source: str, target: str, max_hops: int = 3, max_paths: int = 5) -> dict | list:
    """Navigation-property paths from one entity to another, for writing a join."""
    return run_query(schema_query.cmd_path, source=source, target=target,
                     max_hops=max_hops, max_paths=max_paths)


def schema_stats() -> dict | list:
    """Counts and provenance of the extracted schema."""
    return run_query(schema_query.cmd_stats)


def validate_query(query: str) -> dict:
    """Validate a SWQL query against the schema. Returns errors and warnings, empty when clean."""
    findings = validate_swql.validate(query, index())
    return {
        "ok": not any(f.level == "ERROR" for f in findings),
        "findings": [{"level": f.level, "message": f.message, "in": f.snippet} for f in findings],
    }


READABLE_ROOTS = ("docs/", "scripts/", "data/reference/", "tools/README.md")
READABLE_FILES = ("AGENTS.md", "README.md", "CONTRIBUTING.md", "llms.txt")


def _safe_path(rel: str) -> str | None:
    rel = rel.replace("\\", "/").lstrip("./")
    if ".." in rel.split("/"):
        return None
    if not (rel in READABLE_FILES or rel.startswith(READABLE_ROOTS)):
        return None
    path = os.path.normpath(os.path.join(ROOT, rel))
    if not path.startswith(ROOT + os.sep) or not os.path.isfile(path):
        return None
    return path


def read_doc(path: str) -> dict:
    """Read one documentation page, sample script, or reference file by repository path.

    Readable: AGENTS.md, README.md, CONTRIBUTING.md, llms.txt, anything under docs/,
    scripts/ and data/reference/. Start with docs/TOC.md to find the right section.
    """
    full = _safe_path(path)
    if full is None:
        return {"error": f"{path!r} is not a readable repository path"}
    with open(full, encoding="utf-8", errors="replace") as fh:
        return {"path": path, "content": fh.read()}


def search_docs(keyword: str, limit: int = 40) -> dict:
    """Find documentation lines containing a keyword (case-insensitive), with page and line number."""
    needle = keyword.lower()
    hits = []
    for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, "docs")):
        dirnames.sort()
        for name in sorted(filenames):
            if not name.endswith(".md"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, name), ROOT).replace(os.sep, "/")
            with open(os.path.join(dirpath, name), encoding="utf-8", errors="replace") as fh:
                for n, line in enumerate(fh, 1):
                    if needle in line.lower():
                        hits.append({"path": rel, "line": n, "text": line.rstrip()[:240]})
                        if len(hits) >= limit:
                            return {"keyword": keyword, "truncated": True, "hits": hits}
    return {"keyword": keyword, "truncated": False, "hits": hits}


TOOLS = [
    find_entities, show_entity, entity_properties, list_verbs, show_verb, entity_children,
    navigation_path, schema_stats, validate_query, read_doc, search_docs,
]


def build_server():
    """Construct the MCP server. Imported lazily so --list-tools works without the SDK."""
    try:
        from mcp.server.mcpserver import MCPServer as Server  # mcp 2.x
    except ImportError:
        try:
            from mcp.server.fastmcp import FastMCP as Server  # mcp 1.x
        except ImportError:
            sys.exit("error: the mcp package is not installed; run: python3 -m pip install 'mcp>=2'")
    server = Server(SERVER_NAME, instructions=INSTRUCTIONS)
    for fn in TOOLS:
        server.tool()(fn)
    return server


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list-tools", action="store_true", help="print the tools and exit")
    args = ap.parse_args()
    if args.list_tools:
        for fn in TOOLS:
            first = (fn.__doc__ or "").strip().splitlines()[0]
            print(f"{fn.__name__:<20} {first}")
        return
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()

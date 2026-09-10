from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from freight_second_brain.catalog.sources import SOURCE_CATALOG, list_enabled_extractors
from freight_second_brain.etl.enrich import finalize_warehouse
from freight_second_brain.etl.extractors import EXTRACTORS
from freight_second_brain.etl.pipeline import run_pipeline
from freight_second_brain.tools.mcp_server import harness_warehouse
from freight_second_brain.tools.registry import ToolRegistry


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="freight-sb",
        description="Dry-bulk freight second brain: code ETL, warehouse SQL, and agent tools.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    etl = sub.add_parser("etl", help="Run the public-data batch ingest")
    etl.add_argument("--extractors", nargs="*", help="Extractor names to run (default: enabled catalog set)")
    etl.add_argument("--list", action="store_true", help="List extractor names and exit")

    sub.add_parser("catalog", help="Print the source catalog")
    sub.add_parser("schema", help="Print warehouse SQL tables and columns")
    sub.add_parser("rebuild-sql", help="Rebuild DuckDB from current warehouse files")

    sql = sub.add_parser("sql", help="Run a read-only SQL query against the warehouse")
    sql.add_argument("query")
    sql.add_argument("--limit", type=int, default=200)

    tools = sub.add_parser("tools", help="List or invoke runtime query tools")
    tools.add_argument("name", nargs="?")
    tools.add_argument("--json", dest="payload", help="JSON object of tool arguments")

    agent_p = sub.add_parser(
        "agent",
        help="Run the deployable dry-bulk research agent (LangChain + OpenRouter)",
    )
    agent_p.add_argument("query", nargs="?", help="Research question")
    agent_p.add_argument("-q", "--query", dest="query_flag", help="Research question")
    agent_p.add_argument(
        "--check",
        action="store_true",
        help="Verify imports, runtime tools, and LangChain agent construction",
    )
    agent_p.add_argument("--model", help="OpenRouter model id (overrides OPENROUTER_MODEL)")
    agent_p.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Print the full agent result as JSON",
    )

    sub.add_parser("mcp", help="Serve ToolRegistry over MCP stdio for the Cursor harness")

    preload_p = sub.add_parser(
        "preload",
        help="Run the desk agent and save a static example session for first paint",
    )
    preload_p.add_argument("query", nargs="?", help="Research question to preload")
    preload_p.add_argument("-q", "--query", dest="query_flag", help="Research question to preload")
    preload_p.add_argument(
        "-o",
        "--output",
        type=Path,
        help="JSON path (default: web/public/preload.json)",
    )
    preload_p.add_argument("--model", help="OpenRouter model id (overrides OPENROUTER_MODEL)")

    ui = sub.add_parser("ui", help="Open the research desk chat UI")
    ui.add_argument(
        "--host",
        default=None,
        help="Bind address (default: HOST env or 127.0.0.1; containers set HOST=0.0.0.0)",
    )
    ui.add_argument(
        "--port",
        type=int,
        default=None,
        help="Bind port (default: PORT env or 8787)",
    )
    ui.add_argument("--reload", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "etl":
        if args.list:
            print(json.dumps({"available": sorted(EXTRACTORS), "default": list_enabled_extractors()}, indent=2))
            return
        manifest = run_pipeline(extractors=args.extractors or None)
        print(manifest.model_dump_json(indent=2))
        if manifest.status == "failed":
            sys.exit(1)
        return
    if args.command == "catalog":
        print(json.dumps([row.model_dump(mode="json") for row in SOURCE_CATALOG], indent=2))
        return
    if args.command == "schema":
        print(json.dumps(harness_warehouse().schema(), indent=2, default=str))
        return
    if args.command == "rebuild-sql":
        warehouse = harness_warehouse()
        path = finalize_warehouse(warehouse)
        print(json.dumps({"duckdb": str(path), "tables": warehouse.schema()}, indent=2, default=str))
        return
    if args.command == "sql":
        print(json.dumps(harness_warehouse().sql(args.query, limit=args.limit), indent=2, default=str))
        return
    if args.command == "tools":
        registry = ToolRegistry(harness_warehouse())
        if not args.name:
            print(json.dumps(registry.list_tools(), indent=2))
            return
        payload = json.loads(args.payload) if args.payload else {}
        result = registry.call(args.name, **payload)
        print(json.dumps({"ok": result.ok, "data": result.data, "error": result.error}, indent=2, default=str))
        if not result.ok:
            sys.exit(1)
        return
    if args.command == "agent":
        from freight_second_brain.agent.research import run_research_query, startup_check
        from freight_second_brain.config import get_settings

        settings = get_settings()
        if args.model:
            settings.openrouter_model = args.model
        if args.check:
            report = startup_check(settings=settings)
            print(json.dumps(report, indent=2))
            if not report["ok"]:
                sys.exit(1)
        query = args.query_flag or args.query
        if not query:
            if args.check:
                return
            parser.error("agent requires a query or --check")
        result = run_research_query(query, settings=settings)
        if args.as_json:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(result["answer"])
        return
    if args.command == "preload":
        from freight_second_brain.agent.preload import run_preload
        from freight_second_brain.config import get_settings

        settings = get_settings()
        if args.model:
            settings.openrouter_model = args.model
        query = args.query_flag or args.query
        payload = run_preload(query, output=args.output, settings=settings)
        print(json.dumps({"ok": payload["ok"], "query": payload["query"], "model": payload["model"]}, indent=2))
        return
    if args.command == "mcp":
        from freight_second_brain.tools.mcp_server import serve

        serve()
        return
    if args.command == "ui":
        from freight_second_brain.ui.server import run_ui

        run_ui(host=args.host, port=args.port, reload=args.reload)
        return
    parser.error("unknown command")


if __name__ == "__main__":
    main()

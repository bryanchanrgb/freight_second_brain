from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from freight_second_brain.catalog.sources import SOURCE_CATALOG, list_enabled_extractors
from freight_second_brain.etl.apply import WRITEABLE, load_rows, write_table
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

    etl = sub.add_parser("etl", help="Run the public-data batch ingest (no semantic labeling)")
    etl.add_argument("--extractors", nargs="*", help="Extractor names to run (default: enabled catalog set)")
    etl.add_argument("--list", action="store_true", help="List extractor names and exit")

    sub.add_parser("catalog", help="Print the source catalog")
    sub.add_parser("schema", help="Print warehouse SQL tables and columns")
    sub.add_parser("rebuild-sql", help="Rebuild DuckDB from current warehouse files")

    write = sub.add_parser("write", help="Validate and replace an agent-owned JSONL table")
    write.add_argument("table", choices=sorted(WRITEABLE))
    write.add_argument("--file", required=True, help="JSON array or JSONL file")
    write.add_argument("--rebuild-sql", action="store_true", help="Rebuild DuckDB after writing")

    sql = sub.add_parser("sql", help="Run a read-only SQL query against the warehouse")
    sql.add_argument("query")
    sql.add_argument("--limit", type=int, default=200)

    tools = sub.add_parser("tools", help="List or invoke runtime query tools")
    tools.add_argument("name", nargs="?")
    tools.add_argument("--json", dest="payload", help="JSON object of tool arguments")

    sub.add_parser("mcp", help="Serve ToolRegistry over MCP stdio for the Cursor harness")

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
    if args.command == "write":
        warehouse = harness_warehouse()
        count = write_table(warehouse, args.table, load_rows(Path(args.file)))
        if args.rebuild_sql:
            finalize_warehouse(warehouse)
        print(json.dumps({"table": args.table, "rows": count, "duckdb": str(warehouse.duckdb_path)}, indent=2))
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
    if args.command == "mcp":
        from freight_second_brain.tools.mcp_server import serve

        serve()
        return
    parser.error("unknown command")


if __name__ == "__main__":
    main()

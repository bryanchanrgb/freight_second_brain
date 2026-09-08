# Agent harness

This repo is meant to be driven from Cursor.

**Runtime warehouse tools** are whatever `ToolRegistry` currently exposes
(`schema`, `sql`, `show_source` today). Use that same surface while developing:

1. Prefer MCP tools from the `freight-second-brain` server (`.cursor/mcp.json`).
2. If MCP is not connected, call `uv run freight-sb tools <name> --json '...'`.
3. Do not read warehouse files directly when the task is to test or use agent tools.

Adding a handler in `register_default_tools` is enough: CLI and MCP both list
whatever the registry exposes.

Semantic ETL skills live under `.cursor/skills/` (`freight-etl` and the extract/label
skills). Code ingest is `uv run freight-sb etl`.

# Agent harness

This repo is meant to be driven from Cursor.

**Runtime tools** are whatever `ToolRegistry` currently exposes
(`schema`, `sql`, `show_source` for the warehouse; `web_search`, `rss_feed`,
`fetch_url` for live web research). Use that same surface while developing:

1. Prefer MCP tools from the `freight-second-brain` server (`.cursor/mcp.json`).
2. If MCP is not connected, call `uv run freight-sb tools <name> --json '...'`.
3. Do not read warehouse files directly when the task is to test or use agent tools.

Adding a handler in `register_default_tools` is enough: CLI and MCP both list
whatever the registry exposes.

Code ingest is `uv run freight-sb etl` (skill `freight-etl`). The warehouse holds
tabular series and source snapshots only — not stored claims or RSS events. Live
market sweeps (news, analysis, outlook) use `dry-bulk-freight-research` (Exa, RSS,
Jina). The deployable LangChain agent (`uv run freight-sb agent`) exposes the full
ToolRegistry: warehouse `schema` / `sql` / `show_source` plus `web_search` /
`rss_feed` / `fetch_url`. Pin horizon/date range before searching.
Judge multi-turn desk traces against `evals/` with `freight-eval-judge` (fixed 0–2
rubric and hard fails — not ad hoc scoring).

---
name: freight-runtime-tools
description: >-
  Tests and uses Freight Second Brain runtime agent tools (schema, sql,
  show_source, web_search, rss_feed, fetch_url) through the development harness.
  Use when querying the warehouse, running live web research tools, developing
  ToolRegistry, testing agent tools, or answering questions from observations.
---

# Runtime tools (development harness)

Warehouse query tools and live web research tools live in `ToolRegistry`
(`src/freight_second_brain/tools/registry.py`). Anything registered there is the
product agent's tool surface **and** this Cursor harness.

Web tools match the dry-bulk research skill: `web_search` (Exa MCP free tier,
or REST if `EXA_API_KEY` is set), `rss_feed` (Hellenic dry-bulk feed by
default), `fetch_url` (Jina Reader).

## How to call them

1. **MCP (preferred):** tools from the `freight-second-brain` server. Same names and
   arguments as the runtime agent. Enable via `.cursor/mcp.json`; reload the window
   if they are missing from the tool list.
2. **CLI fallback** (always works in this repo):

```bash
uv run freight-sb tools
uv run freight-sb tools schema
uv run freight-sb tools sql --json '{"query":"SELECT 1 AS n","limit":5}'
uv run freight-sb tools show_source --json '{"source_id":"hellenic_rss"}'
uv run freight-sb tools rss_feed --json '{"limit":5}'
uv run freight-sb tools fetch_url --json '{"url":"https://www.hellenicshippingnews.com/","max_chars":2000}'
```

Do **not** bypass the registry by reading parquet/JSONL when the job is to use or
test agent tools. Adding a tool in `register_default_tools` exposes it on MCP after
reload and on `freight-sb tools` immediately.

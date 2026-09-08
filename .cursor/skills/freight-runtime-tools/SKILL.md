---
name: freight-runtime-tools
description: >-
  Tests and uses Freight Second Brain runtime agent tools (schema, sql,
  show_source) through the development harness. Use when querying the warehouse,
  developing ToolRegistry, testing agent tools, or answering questions from
  observations/claims.
---

# Runtime tools (development harness)

Warehouse query tools live in `ToolRegistry` (`src/freight_second_brain/tools/registry.py`).
Anything registered there is the product agent's tool surface **and** this Cursor harness.

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
```

Do **not** bypass the registry by reading parquet/JSONL when the job is to use or
test agent tools. Adding a tool in `register_default_tools` exposes it on MCP after
reload and on `freight-sb tools` immediately.

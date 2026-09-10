---
name: freight-runtime-tools
description: >-
  Tests and uses Freight Second Brain runtime agent tools (schema, sql,
  show_source, web_search, rss_feed, fetch_url, press_fetch, market_feed)
  through the development harness. Use when querying the warehouse, running
  live web research tools, developing ToolRegistry, testing agent tools, or
  answering questions from observations.
---

# Runtime tools (development harness)

Warehouse query tools and live web research tools live in `ToolRegistry`
(`src/freight_second_brain/tools/registry.py`). Anything registered there is this
Cursor harness (MCP / `freight-sb tools`). The deployable LangChain agent binds
`DEPLOYABLE_TOOL_NAMES` (live web: `market_feed`, `press_catalog`, `press_fetch`,
`web_search`, `fetch_url` — no warehouse SQL, no rss_feed).

Web tools match the dry-bulk research skill: `market_feed` (OilPriceAPI Baltic
and cargo prices; needs `OILPRICE_API_TOKEN`), `web_search` (Exa MCP free tier,
or REST if `EXA_API_KEY` is set), `rss_feed` (Hellenic dry-bulk feed by
default), `press_fetch` (publisher REST/RSS where it exists), `fetch_url` (Jina Reader).

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
uv run freight-sb tools press_catalog
uv run freight-sb tools press_fetch --json '{"site":"hellenic","after":"2026-09-01","limit":8}'
uv run freight-sb tools press_fetch --json '{"site":"hellenic","category":"dry-bulk","query":"Baltic Dry","after":"2026-09-01","limit":8}'
uv run freight-sb tools press_fetch --json '{"site":"telegraph","category":"freight-news","query":"Freight Market","after":"2026-09-01","limit":8}'
uv run freight-sb tools press_fetch --json '{"site":"gcaptain","query":"Capesize","after":"2026-09-01","limit":8}'
uv run freight-sb tools market_feed --json '{"action":"catalog"}'
uv run freight-sb tools market_feed --json '{"action":"latest","codes":"bdi,bci"}'
uv run freight-sb tools market_feed --json '{"action":"history","codes":"bdi","past":"30d"}'
uv run freight-sb tools fetch_url --json '{"url":"https://www.hellenicshippingnews.com/","max_chars":2000}'
```

Do **not** bypass the registry by reading parquet/JSONL when the job is to use or
test agent tools. Adding a tool in `register_default_tools` exposes it on MCP after
reload and on `freight-sb tools` immediately.

`market_feed` is the dated print source (OilPriceAPI). `action=catalog` needs no key.
`latest` / `history` need `OILPRICE_API_TOKEN` or `OILPRICEAPI_KEY` (free signup,
50 req/day). Free history is `past=7d` or `past=30d`. Cite as an OilPriceAPI reprint,
not official Baltic Exchange data.

`press_fetch` defaults to `category=all` (whole site). Pin a desk with `category`
when you need BDI color (`hellenic` `dry-bulk`), weeklies (`weekly-brokers`),
or fixtures (`splash` `dry-cargo` / `telegraph` `freight-news`). `press_catalog`
returns `category_guide` for every site.

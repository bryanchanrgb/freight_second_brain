# Freight Second Brain

Agentic research system for **dry-bulk freight rates**. A provenance-aware public-data
warehouse is built by **code ingest**. Runtime SQL tools read that warehouse; news and
analysis come from **live web tools**. The system does not invent numerical forecasts.

## ETL is code ingest

`uv run freight-sb etl` fetches public sources, stores immutable raw snapshots, parses
**tabular** series into `observations`, writes `sources` + `catalog`, and rebuilds DuckDB.

News, prints, and outlook are **not** stored as claims or events. The deployable agent
uses `rss_feed` / `web_search` / `fetch_url` at question time.

| Stage | Who | What |
|---|---|---|
| 1. Ingest | Code | `uv run freight-sb etl` |
| 2. Rebuild SQL | Code | `uv run freight-sb rebuild-sql` (also runs at end of etl) |

Orchestration: skill `freight-etl`.

Do not add keyword matchers for polarity, entities, or duplicates into extractors.
Series-name maps (`infer_commodity` on Pink Sheet column headers) stay in code because
they are identifiers, not prose.

## Layout

```
.cursor/mcp.json    Cursor harness: same ToolRegistry over MCP
.cursor/skills/     agent skills (ETL, live research, eval judge)
src/freight_second_brain/
  catalog/          source register and canonical entity ids
  etl/              fetch, landing zone, tabular parsers
  warehouse/        parquet + JSONL + read-only DuckDB
  qualitative/      date-based freshness only
  tools/            runtime: schema, sql, show_source, web_search, rss_feed, fetch_url
  agent/            LangChain/OpenRouter research desk (warehouse SQL + live web)
  ui/               FastAPI research desk (SSE chat)
web/                React research-desk frontend
data/               raw snapshots, warehouse, run manifests
```

Raw objects are immutable:

`data/raw/{source}/{dataset}/{YYYY}/{MM}/{DD}/{run_id}/`

## Setup

```bash
uv sync
```

Optional keys live in `.env` (see `.env.example`). Code ingest does **not** require
LLM keys: it uses public files and preview APIs. The agent harness needs whatever
your Cursor/agent runtime already uses.

## Run code ingest

```bash
uv run freight-sb etl --list
uv run freight-sb etl
```

Default extractors (verified public / fallback):

| Extractor | What it stores |
|---|---|
| `world_bank_pink_sheet` | Monthly coal, iron ore, grain, fertilizer, energy prices |
| `world_bank_api` | GDP and trade indicators |
| `fao_fpi` | FAO food/cereal price indices |
| `usda_psd` | Grain/oilseed supply-demand for major exporters/importers |
| `comtrade` | Annual China/Australia/Brazil dry-bulk trade preview |
| `mendeley_bdi` | Daily BCI/BPI/BSI/BHSI, 2012–2019, CC BY 4.0 |
| `trading_economics_bdi` | Current displayed BDI last value (secondary snapshot only) |
| `yahoo_finance` | BDRY ETF plus energy/grain/FX/VIX proxies |
| `noaa_enso` | Oceanic Niño Index |
| `data360_maritime` | UNCTAD port/fleet indicators |
| `eia_coal` | Filtered EIA coal production/trade/price series |
| `hellenic_rss` | Raw feed snapshot (`show_source`); live news is `rss_feed` |
| `qualitative_pages` | Baltic / BIMCO HTML and UNCTAD RMT PDF snapshots |

FRED and IMF extractors are catalogued but disabled by default (timeouts / 403 from this environment). Licensed Baltic, AIS, and broker research stay in the catalog as non-default sources.

A code run is `complete` only when every extractor succeeds. Inspect
`data/metadata/latest.json` and `data/metadata/quality_report.json`.

## Runtime query tools

After ingest:

```bash
uv run freight-sb schema
uv run freight-sb sql "SELECT series_id, observed_at, value FROM observations WHERE series_id ILIKE '%BDI%' ORDER BY observed_at DESC"
uv run freight-sb tools show_source --json '{"source_id":"mendeley_bdi"}'
```

Tables: `observations`, `series`, `sources`, `catalog`. `sql` is read-only (`SELECT` /
`WITH` / `DESCRIBE` / `SHOW` / `EXPLAIN` / `SUMMARIZE` / `FROM`).

The same registry is served to this Cursor workspace over MCP
(`.cursor/mcp.json` → `uv run freight-sb mcp`). After adding a tool in
`register_default_tools`, reload the Cursor window so MCP re-lists tools. If MCP
is not connected, `uv run freight-sb tools` is the same surface:

```bash
uv run freight-sb tools
uv run freight-sb tools sql --json '{"query":"SELECT 1 AS n","limit":5}'
uv run freight-sb tools rss_feed --json '{"limit":5}'
```

## Deployable research agent

The same ToolRegistry as MCP (`schema`, `sql`, `show_source`, `web_search`,
`rss_feed`, `fetch_url`) is wrapped in a LangChain tool-calling agent with
OpenRouter:

```bash
uv run freight-sb agent --check
uv run freight-sb agent "What is the latest Baltic Dry Index print this week?"
```

Set `OPENROUTER_API_KEY`. `web_search` uses Exa's hosted MCP free tier without
`EXA_API_KEY`; set the key to lift rate limits. `rss_feed` and `fetch_url` need
no Exa key. Override the model with `OPENROUTER_MODEL` or `--model`.

## Research desk UI

Multi-turn chat with streamed tool calls, source cards, tables, and charts:

```bash
cd web && npm install && npm run build
uv run freight-sb ui
```

Opens at `http://127.0.0.1:8787`. During frontend development, `npm run dev` in
`web/` proxies `/api` to that server.

## Rules the agents must keep

- Cite URLs, freshness and provenance.
- Do not count syndicated copies as independent evidence.
- Preserve contradictions; do not average them.
- Numerical forecasts come from versioned models, not free-form generation.

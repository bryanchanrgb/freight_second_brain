# Freight Second Brain

Live-web research desk for **dry-bulk freight rates** (BDI, Capesize / Panamax /
Supramax, iron ore, coal, grain). A LangChain agent on OpenRouter pulls dated
prints and maritime sources at question time. It quotes sourced figures and
labelled outlooks; it does not invent numerical forecasts.

The public product is `freight-sb agent` and the research-desk UI. Those bind
**live web tools only**. A local warehouse (code ETL + DuckDB) exists for the
Cursor/MCP harness and is **not** queried by the deployable agent.

## Deployable tools

| Tool | Role |
|---|---|
| `market_feed` | Dated BDI/BCI and related cargo/energy prints (OilPriceAPI). Needs `OILPRICE_API_TOKEN`. Cite as a reprint, not official Baltic Exchange data. BPI/BSI/BHSI are **not** in this catalog — segment splits come from weeklies / Reuters / brokers. |
| `press_catalog` | Category map for Hellenic, Splash 247, Shipping Telegraph, gCaptain. |
| `press_fetch` | Native REST/search on those four sites. Pin a `category` (default `all` is noisy). |
| `web_search` | Exa. Other publishers (Reuters/Baird, BIMCO reprints, Clarksons, BigMint, Mysteel). Free MCP tier without `EXA_API_KEY`; set the key to lift rate limits. |
| `fetch_url` | Jina Reader on one chosen URL or PDF. |

The desk also has `present_report` (right-hand generative report) and
`label_sources`. Warehouse `schema` / `sql` / `show_source` and `rss_feed` stay
on MCP and `freight-sb tools` only.

## Setup

```bash
uv sync
```

Copy `.env.example` to `.env`. For the agent and desk:

| Variable | Required? |
|---|---|
| `OPENROUTER_API_KEY` | Yes |
| `OPENROUTER_MODEL` | Optional (default `openai/gpt-4o-mini`) |
| `OILPRICE_API_TOKEN` | Yes for dated BDI/BCI (`https://www.oilpriceapi.com/auth/signup`) |
| `EXA_API_KEY` | Optional |
| `DESK_ACCESS_TOKEN` | Optional locally; set on a public URL so the desk asks for a password |

```bash
uv run freight-sb agent --check
uv run freight-sb agent "What is the latest Baltic Dry Index print this week?"
```

Override the model with `OPENROUTER_MODEL` or `--model`.

## Research desk

Collapsible **guide** (open on first visit), left-hand **chat** (short pointer),
right-hand **report** (markdown, tables, charts, labelled sources, clickable
`[1]` citations).

```bash
cd web && npm install && npm run build
uv run freight-sb ui
```

Opens at `http://127.0.0.1:8787`. During frontend development, `npm run dev` in
`web/` proxies `/api` to that server.

First paint can hydrate an example session from `web/public/preload.json`
(copied into `web/dist` on build). Reset starts a blank session. Hosted images
skip LangGraph traces so the example is read-only memory; a follow-up is a
fresh agent turn.

```bash
uv run freight-sb preload
uv run freight-sb preload "Identify all predictive claims made in august 2026 regarding short term BDI movements (30 day horizon), by conviction and consensus vs disagreement between analysts. Test these claims against September data."
```

## Hosted desk

Long-running FastAPI + SSE, not a serverless function. Docker on Railway,
Render, Fly.io, or Cloud Run. You pay OpenRouter / OilPriceAPI / Exa with keys
stored as host secrets. No warehouse, no ETL.

```bash
docker build -t freight-sb-desk .
docker run --rm -p 8787:8787 \
  -e OPENROUTER_API_KEY \
  -e OPENROUTER_MODEL \
  -e OILPRICE_API_TOKEN \
  -e DESK_ACCESS_TOKEN \
  freight-sb-desk
```

The image binds `0.0.0.0` and honors `PORT`. With `DESK_ACCESS_TOKEN` set, the
UI asks for a password (same value). Leave it blank and anyone with the URL can
run the agent on your bill. Do not copy `.env` into the image.

Railway uses `railway.toml`; Render uses `render.yaml`. Health check:
`GET /api/health`. Use **one** instance — sessions are in-memory and vanish on
restart.

## Layout

```
src/freight_second_brain/
  agent/     LangChain + OpenRouter desk (live web; generative report)
  ui/        FastAPI + SSE
  tools/     ToolRegistry (web tools on the desk; warehouse tools on MCP/CLI)
web/         React research-desk frontend
```

## Research rules

- Cite URLs, freshness, and provenance.
- Do not count syndicated copies as independent evidence.
- Preserve contradictions; do not average them.
- Numerical forecasts come from sourced outlooks or versioned models, not
  free-form generation.

## Local warehouse (optional)

Not used by `freight-sb agent` or the desk. Cursor MCP (`.cursor/mcp.json`) and
`freight-sb tools` can query a DuckDB warehouse built by code ingest
(`uv run freight-sb etl`). Orchestration: skill `freight-etl`.

```bash
uv run freight-sb etl --list
uv run freight-sb etl
uv run freight-sb schema
uv run freight-sb sql "SELECT series_id, observed_at, value FROM observations WHERE series_id ILIKE '%BDI%' ORDER BY observed_at DESC LIMIT 5"
uv run freight-sb tools rss_feed --json '{"limit":5}'
```

`sql` is read-only (`SELECT` / `WITH` / `DESCRIBE` / `SHOW` / `EXPLAIN` /
`SUMMARIZE` / `FROM`). After adding a tool in `register_default_tools`, reload
the Cursor window so MCP re-lists it.

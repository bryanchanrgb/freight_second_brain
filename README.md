# Freight Second Brain

Agentic research system for **dry-bulk freight rates**. A provenance-aware public-data
warehouse is built by **code ingest plus an agent harness**. Runtime query tools only
read that warehouse. The system does not invent numerical forecasts.

## ETL is code + agent harness

`uv run freight-sb etl` is **not** the full build. It is the deterministic half:

- fetch public sources
- store immutable raw snapshots
- parse **tabular** series into `observations`
- land unlabeled RSS headlines as `events`
- write `sources` + `catalog` and rebuild DuckDB

**Semantic work is not done in Python.** Polarity, claim extraction, entity
resolution, duplicate grouping, contradiction detection, and claim-to-series
links are agent skills under `.cursor/skills/`. Run them in a Cursor agent
(or any harness that loads those skills) after code ingest.

| Stage | Who | What |
|---|---|---|
| 1. Ingest | Code | `uv run freight-sb etl` |
| 2. Extract claims | Agent | skill `extract-claims` |
| 3. Resolve entities | Agent | skill `resolve-entities` |
| 4. Duplicates | Agent | skill `find-duplicates` |
| 5. Contradictions | Agent | skill `find-contradictions` |
| 6. Link to series | Agent | skill `link-claims-to-series` |
| 7. Rebuild SQL | Code | `uv run freight-sb rebuild-sql` |

Orchestration: skill `freight-etl`. Agent writes go through schema validation:

```bash
uv run freight-sb write claims --file /tmp/claims.json
```

A full ingest **clears** `claim_entities`, `contradictions`, and `claim_series`, so
the semantic skills must be re-run after every `etl`.

Do not add keyword matchers for polarity, entities, or duplicates back into
extractors. Series-name maps (`infer_commodity` on Pink Sheet column headers) stay
in code because they are identifiers, not prose.

## Layout

```
.cursor/mcp.json    Cursor harness: same ToolRegistry over MCP
.cursor/skills/     agent harness for semantic ETL
src/freight_second_brain/
  catalog/          source register and canonical entity ids
  etl/              fetch, landing zone, tabular parsers
  warehouse/        parquet + JSONL + read-only DuckDB
  qualitative/      date-based freshness only
  tools/            runtime: schema, sql, show_source
  agent/            query-time system prompt
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
| `hellenic_rss` | Raw feed + unlabeled headlines (claims come from the agent) |
| `qualitative_pages` | Baltic / BIMCO HTML and UNCTAD RMT PDF snapshots |

FRED and IMF extractors are catalogued but disabled by default (timeouts / 403 from this environment). Licensed Baltic, AIS, and broker research stay in the catalog as non-default sources.

A code run is `complete` only when every extractor succeeds. Inspect
`data/metadata/latest.json` and `data/metadata/quality_report.json` before the
semantic pass.

## Runtime query tools

After the harness has written semantic tables:

```bash
uv run freight-sb schema
uv run freight-sb sql "SELECT series_id, observed_at, value FROM observations WHERE series_id ILIKE '%BDI%' ORDER BY observed_at DESC"
uv run freight-sb tools show_source --json '{"source_id":"mendeley_bdi"}'
```

Tables: `observations`, `series`, `claims`, `claim_entities`, `contradictions`,
`claim_series`, `events`, `sources`, `catalog`. `sql` is read-only (`SELECT` /
`WITH` / `DESCRIBE` / `SHOW` / `EXPLAIN` / `SUMMARIZE` / `FROM`).

Wire an LLM by pointing it at `AgentRuntime.system_prompt()` and
`ToolRegistry.openai_tools()`. Without an API key the query tools still run locally.

The same registry is served to this Cursor workspace over MCP
(`.cursor/mcp.json` → `uv run freight-sb mcp`). After adding a tool in
`register_default_tools`, reload the Cursor window so MCP re-lists tools. If MCP
is not connected, `uv run freight-sb tools` is the same surface:

```bash
uv run freight-sb tools
uv run freight-sb tools sql --json '{"query":"SELECT 1 AS n","limit":5}'
```

## Rules the agents must keep

- Cite claim IDs, URLs, freshness and provenance.
- Do not count syndicated copies as independent evidence.
- Preserve contradictions; do not average them.
- Numerical forecasts come from versioned models, not free-form generation.

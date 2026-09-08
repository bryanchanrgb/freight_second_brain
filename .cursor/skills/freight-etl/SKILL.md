---
name: freight-etl
description: >-
  Runs the dry-bulk freight second-brain code ingest. Use when building or
  refreshing the warehouse, running freight-sb etl, or rebuilding DuckDB from
  observations and source snapshots.
---

# Freight ETL (code ingest)

The pipeline is **code ingest only**. News, analysis, and outlook come from live
web tools (`rss_feed`, `web_search`, `fetch_url`) at question time — not from
stored claims or RSS events.

## Code ingest

```bash
uv run freight-sb etl
```

Code only: HTTP fetch, immutable raw snapshots, tabular `observations`, source
records, `catalog`, DuckDB rebuild.

Then query with `schema` / `sql` / `show_source`.

## Rules

- Do not invent numerical observations. Numbers come from extractors.
- Do not write claims, events, polarity, entities, or contradictions into the warehouse.
- Syndicated copies found on the live web are one independence group, not N witnesses.
- Preserve live-web contradictions; never average them.
- Chunk the UNCTAD PDF if `show_source` / `fetch_url` is too large; never dump the raw 11 MB file into context.

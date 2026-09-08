---
name: freight-etl
description: >-
  Runs the dry-bulk freight second-brain ETL as code ingest plus agent semantic
  skills. Use when building or refreshing the warehouse, running freight-sb etl,
  extracting claims, labeling polarity, resolving entities, finding duplicates
  or contradictions, linking claims to series, or when the user mentions the
  agent harness pipeline.
---

# Freight ETL (code + agent harness)

The pipeline is **code ingest**, then **agent skills**. Do not put polarity, entity
resolution, claim extraction, duplicates, contradictions, or series-linking back
into Python extractors.

## 1. Code ingest

```bash
uv run freight-sb etl
```

Code only: HTTP fetch, immutable raw snapshots, tabular `observations`, unlabeled
RSS `events`, source records, `catalog`, DuckDB rebuild.

It **clears** `claim_entities`, `contradictions`, and `claim_series`. Re-run the
skills below after every full ingest.

## 2. Semantic skills (this harness)

Run in order. Each skill writes via `uv run freight-sb write <table> --file ...`.

1. [extract-claims](../extract-claims/SKILL.md)
2. [resolve-entities](../resolve-entities/SKILL.md)
3. [find-duplicates](../find-duplicates/SKILL.md)
4. [find-contradictions](../find-contradictions/SKILL.md)
5. [link-claims-to-series](../link-claims-to-series/SKILL.md)
6. `uv run freight-sb rebuild-sql`

JSON schemas: [warehouse-tables.md](warehouse-tables.md).

Canonical entity IDs: `src/freight_second_brain/catalog/entities.py`.

## 3. Query (runtime, not ETL)

After DuckDB is rebuilt: `schema`, `sql`, `show_source` only. Do not relabel
warehouse text at question-answering time.

## Rules

- Do not invent numerical observations. Numbers come from extractors.
- Do not keyword-match polarity (`surge`/`slump` lists are gone).
- Syndicated copies are one independence group, not N pieces of evidence.
- Preserve contradictions; never average them away.
- Chunk the UNCTAD PDF; never dump the raw 11 MB file into context.

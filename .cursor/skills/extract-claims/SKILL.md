---
name: extract-claims
description: >-
  Extracts dry-bulk freight claims and event labels from stored RSS, HTML, and
  PDF snapshots. Use during freight ETL after code ingest, when claims.jsonl is
  empty or stale, or when labeling qualitative sources (Hellenic, Baltic, BIMCO,
  UNCTAD RMT).
---

# Extract claims

Read landed snapshots. Write `claims` (and updated `events`). Do not fetch the
live web unless the snapshot is missing.

## Inputs

Prefer MCP `sql` / `show_source` from the `freight-second-brain` server. CLI fallback:

```bash
uv run freight-sb sql "SELECT source_id, canonical_url, raw_object_uri, title FROM sources"
uv run freight-sb tools show_source --json '{"source_id":"hellenic_rss"}'
```

Priority sources: `hellenic_rss`, `baltic_exchange`, `bimco`, `unctad_rmt`.
RSS events may already be in `events` with headlines only — label those rows
and add claims; do not drop the feed items.

## How to read

- **XML/HTML:** strip scripts/nav/cookies. Use the article or methodology body.
- **PDF (UNCTAD RMT):** extract **page by page** (pdftotext or a short Python
  script). ~20 pages per pass. Never load the whole PDF into context.
- Skip boilerplate (cookie banners, membership pitches).

## What to write

One claim = one falsifiable statement. Quote evidence. Set `claim_type` from
meaning (`methodology` for Baltic definitions; `forecast` only if the source
forecasts). Set `polarity` from the economic implication for dry-bulk rates or
the named subject, not from a word list.

Unlabeled RSS events: fill `factor_type` and `polarity` when the headline+blurb
support it; otherwise leave `unknown`.

Write:

```bash
uv run freight-sb write claims --file /tmp/claims.json
uv run freight-sb write events --file /tmp/events.json
```

Field reference: [warehouse-tables.md](../freight-etl/warehouse-tables.md)

Then continue with `resolve-entities`.

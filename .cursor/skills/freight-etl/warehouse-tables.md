# Agent-owned warehouse tables

Write JSON arrays or JSONL. Validate with:

```bash
uv run freight-sb write <table> --file path.json
```

`<table>` is one of: `claims`, `events`, `claim_entities`, `contradictions`, `claim_series`.

## claims

| field | notes |
|---|---|
| `claim_id` | stable, unique |
| `source_id` | catalog id |
| `claim_text` | one atomic statement, not a page dump |
| `claim_type` | `observation` \| `explanation` \| `forecast` \| `scenario` \| `risk` \| `methodology` |
| `subject_entity` | canonical id when known |
| `subject_type` | `index` \| `vessel_class` \| `commodity` \| `country` or null |
| `vessel_class` / `commodity` / `route` / `geography` | canonical ids or null |
| `polarity` | `bullish` \| `bearish` \| `mixed` \| `neutral` \| `unknown` |
| `magnitude` | short phrase or null |
| `confidence` | `high` \| `medium` \| `low` \| `unknown` |
| `provenance` | `primary` \| `secondary` |
| `independence_group` | same id for copies of the same story |
| `source_freshness` | `current` (≤7d) \| `recent` (≤30d) \| `aging` (≤90d) \| `historical_vintage` \| `post_cutoff_outcome` |
| `retrieval_status` | `full_text` \| `public_summary` |
| `supporting_evidence` | short quote |
| `raw_object_uri` / `source_url` | landing path and canonical URL |
| `publication_time` / `retrieved_time` | ISO-8601 or null |
| `entities` | list of canonical ids (filled by resolve-entities) |
| `is_duplicate` / `duplicate_of` | filled by find-duplicates |

## events

Feed items may already exist from code ingest (`headline`, `source_url`, `published_at`).
Overwrite labels: `commodity`, `vessel_class`, `region`, `route`, `factor_type`,
`polarity`, `magnitude`, `expected_horizon`. Leave unknown fields `unknown` or null.

`factor_type`: `fleet` \| `demand` \| `supply` \| `port` \| `weather` \| `policy` \| `geopolitics` \| `cost` \| `unknown`

## claim_entities

`claim_id`, `entity_id`, `entity_type`

## contradictions

`contradiction_id`, `contradiction_type`, `subject_entity`, `claim_id`, `polarity`,
`status` (`unresolved` unless the user resolved it), `summary`

One row per member claim in the disagreement set.

## claim_series

`claim_id`, `series_id`, `relation_type` (`affects` \| `describes` \| `forecasts`), `rationale`

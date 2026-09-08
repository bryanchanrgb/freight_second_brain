---
name: link-claims-to-series
description: >-
  Links qualitative freight claims to quantitative warehouse series_ids. Use
  during freight ETL after contradictions, or when claim_series is empty.
---

# Link claims to series

Prefer MCP `sql` from the `freight-second-brain` server. CLI fallback:

```bash
uv run freight-sb sql "SELECT source_id, series_id, unit, start, end, last_value FROM series"
uv run freight-sb sql "SELECT claim_id, claim_text, entities, commodity, vessel_class, subject_entity FROM claims"
```

Link when the claim is about that series (or a direct driver): same index,
vessel class, commodity price, trade flow, or named proxy. Require a one-line
`rationale`. Cap about 8 links per claim.

Do not link on accidental substring overlap (`china` in a series id vs a claim
about Chinese iron-ore demand is OK; a cookie-banner `BSI` hit is not).

```bash
uv run freight-sb write claim_series --file /tmp/claim_series.json
uv run freight-sb rebuild-sql
```

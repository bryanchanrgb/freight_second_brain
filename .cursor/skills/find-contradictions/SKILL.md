---
name: find-contradictions
description: >-
  Records unresolved disagreements among dry-bulk claims (direction, magnitude,
  timing). Use during freight ETL after find-duplicates, or when the
  contradictions table is empty or stale.
---

# Find contradictions

Compare **non-duplicate** claims that share a subject (and commodity/vessel/route
when specified) over an overlapping horizon.

Record a contradiction when they disagree on:

- **direction** — bullish vs bearish
- **magnitude** — same direction, incompatible size
- **timing** — incompatible when a move happens

Do not invent a winner. `status` stays `unresolved`. One `contradiction_id` per
disagreement set; one row per member `claim_id`.

Skip mixed/unknown polarity for direction conflicts unless the text clearly
disagrees.

```bash
uv run freight-sb write contradictions --file /tmp/contradictions.json
```

Empty file is valid when nothing conflicts.

Then `link-claims-to-series`.

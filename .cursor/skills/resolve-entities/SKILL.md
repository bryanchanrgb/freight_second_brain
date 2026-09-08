---
name: resolve-entities
description: >-
  Labels freight claims and events with canonical entity IDs (BDI, capesize,
  iron_ore, china, …). Use during freight ETL after extract-claims, when
  claim_entities is empty, or when subject_entity/commodity/vessel_class need
  canonical ids.
---

# Resolve entities

Use the catalog in `src/freight_second_brain/catalog/entities.py`
(`CANONICAL_ENTITIES`: id, type, label, aliases). Match on meaning, not
substring coincidence (`BSI` in a cookie banner is not the Baltic Supramax Index).

Do not invent ids. If nothing fits, leave the field null and omit `claim_entities`
rows.

## Steps

1. Load claims (and events if present). Prefer MCP `sql` from `freight-second-brain`, else:
   `uv run freight-sb sql "SELECT * FROM claims"`
2. For each claim, assign `entities`, `subject_entity`, `subject_type`,
   `commodity`, `vessel_class` when supported by `claim_text` + evidence.
3. Mirror commodity/vessel/region onto events when the headline is about them.
4. Expand `claim_entities` to one row per (claim_id, entity_id) with
   `entity_type` from the catalog.

```bash
uv run freight-sb write claims --file /tmp/claims.json
uv run freight-sb write events --file /tmp/events.json
uv run freight-sb write claim_entities --file /tmp/claim_entities.json
```

Then `find-duplicates`.

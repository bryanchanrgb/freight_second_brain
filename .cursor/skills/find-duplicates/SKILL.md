---
name: find-duplicates
description: >-
  Groups syndicated or repeated dry-bulk claims into independence groups and
  marks duplicates. Use during freight ETL after resolve-entities, or when
  is_duplicate / independence_group look wrong.
---

# Find duplicates

Same story retold is **one** independence group. Same publisher feed is not.

## Group when

- Same `source_url`, or
- Same incident/report clearly rewritten (wire copy, identical numbers/dates), or
- Near-paraphrase of the same atomic claim about the same subject and time.

Do **not** group merely because `source_id` is the same (e.g. every Hellenic item).

## Write

Pick one canonical `claim_id` per group. Others: `is_duplicate=true`,
`duplicate_of=<canonical>`. All members share `independence_group`.

Keep duplicate rows (do not delete). Downstream evidence counts must use
distinct `independence_group` values.

```bash
uv run freight-sb write claims --file /tmp/claims.json
```

Then `find-contradictions`.

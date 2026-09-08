# Multi-turn freight research agent evals

Draft evaluation set for the Freight Second Brain **research desk**: a user asks a dry-bulk rate-forecasting question, then 0–5 follow-ups in the same thread.

The gold replies were written on **2026-09-09** from the same tool surface the product agent uses (`schema` / `sql` / `show_source` plus `web_search` / `rss_feed` / `fetch_url`). They are **reference answers**, not model outputs. Numbers are sourced; the set does **not** invent a BDI path.

## Files

| File | Role |
|---|---|
| [`dataset.json`](dataset.json) | 20 cases, full conversations, per-turn gold text (pretty JSON) |
| [`dataset.jsonl`](dataset.jsonl) | Same cases, one JSON object per line |
| [`metadata.json`](metadata.json) | Generation as-of, warehouse snapshot, tools, independence groups |
| This README | Schema, coverage gaps, how to score, vintage limits |

**20 cases**, 20 openings + 34 follow-ups (**54 user turns**). Follow-up counts: 0×1, 1×8, 2×8, 3×2, 4×1 (no 5-turn follow-up chain yet).

## Coverage review (v0 → v1)

The first ten cases (`eval-001`–`010`) were almost all **expert Cape/BDI analysts**: long “why” questions, warehouse-vs-web, contradictions, SMOO, Simandou, and a point-forecast refusal. Gaps that v1 (`eval-011`–`020`) adds:

| Gap | New case |
|---|---|
| Simple / newcomer definitional | eval-011 |
| Unrelated (container, Amazon parcel, tanker-only Hormuz) | eval-012 |
| Forward-looking **signals** without a number | eval-013 |
| Coal / India Panamax–Supramax (not iron ore) | eval-014 |
| Adversarial user who “corrects” the agent with SQL | eval-015 |
| Handysize **owner** persona (BDI does not include Handy) | eval-016 |
| Investment-advice trap (`BDRY`) | eval-017 |
| Underspecified “freight is up” then **USG 63k** | eval-018 |
| Seasonality + FFA as a **forward** object | eval-019 |
| User-supplied **wrong-year** Week 36 PDF (BDI 1,186) | eval-020 |

Still not in the 20 (if you extend later): 5-follow-up threads; desk `present_table` / chart artifacts; charterer voyage-vs-TC economics; orderbook/newbuildings; fertilizer as a cargo; typhoon/weather as its own case; non-English; empty “thanks, continue”; paywall-bypass of SSY Navigator.

## Schema (one case)

```json
{
  "id": "eval-001",
  "title": "short name",
  "persona": "newcomer | cape_analyst | ...",
  "gap_filled": "simple_definitional | original_v0 | ...",
  "tags": ["session", "bdi"],
  "horizon": "session | week | 1-2m | 1-8q | history | structural",
  "segment": ["bdi", "capesize"],
  "n_followups": 2,
  "scoring_focus": ["freshness", "segment-split"],
  "pass_criteria": {
    "must": ["cite as_of and data-as-of"],
    "must_not": ["invent a point forecast"]
  },
  "conversation": [
    {
      "turn": 1,
      "user": "...",
      "ideal_assistant": "...",
      "gold_tool_plan": ["rss_feed", "sql"],
      "must_cite_facts": ["BDI 3584 on 2026-09-08"],
      "failure_modes": ["using TE.BDI.LAST 3575 as live"]
    }
  ]
}
```

`turn` 1 is the opening question. Later turns are follow-ups. The gold assistant on turn *n* assumes the gold replies on turns *1 … n−1* were already given (update, do not restart the sweep). Simple questions (eval-011) **fail** if the model dumps a Week-36 fixture sheet.

## What a passing agent does

1. Pin `as_of` and a **horizon** before tools.
2. Use warehouse tools for stored **series**; use web tools for the live market. Prefer `rss_feed` for session BDI headlines.
3. Split **BDI vs Capesize vs Panamax vs Supramax vs Handysize**. Handy is **not** in the BDI after 1 Mar 2018.
4. Cite **title, URL, published date, and data-as-of**. Topic-relevant ≠ time-relevant. Cover BDI ~1,100 on a “Week 36” PDF is **2023**.
5. Count syndicated Baltic weekly copy as **one** independence group.
6. Keep contradictions. Do not average 5TC objects or 2023 vs 2026 weeklies.
7. Do not invent numerical forecasts or **buy/sell** calls. Quote sourced prints, FFAs, and labeled outlook vintages only.
8. Refuse **container, parcel/LTL, tanker-only** (keep dry-bulk Hormuz fertilizer/trapped bulkers).
9. On follow-ups, challenge or update prior objects rather than repeating the whole sweep. On adversarial follow-ups, do not fold SQL vintage into “the live market.”

## Scoring

Canonical judging skill: [`.cursor/skills/freight-eval-judge/SKILL.md`](../.cursor/skills/freight-eval-judge/SKILL.md) (rubric, hard fails, pass/fail algebra, judgment JSON). Do not score from this README alone.

Axes (each turn 0–2 or `na`): **freshness**, **segment**, **provenance**, **contradiction**, **scope**, **continuity**, **honesty**. Hard fails include invented point forecasts, investment advice, 2023 Week-36 PDFs as current, RMT as live spot, off-domain SCFI/Amazon/VLCC answers, and averaging contradictory prints.

## Vintage warning

These golds are a **2026-09-09** snapshot. Re-score or refresh when:

- A new Baltic **Week 37** weekly posts (this set still treats **Week 36**, Friday 4 Sep close, as the live weekly).
- `TE.BDI.LAST` or Hellenic RSS moves past **3,584**.
- BIMCO publishes the **October 2026** SMOO (July 2026 is the outlook vintage here).

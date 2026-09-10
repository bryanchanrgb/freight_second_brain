---
name: freight-eval-judge
description: >-
  Judges Freight Second Brain multi-turn research-desk conversations against
  evals/ gold cases with a fixed 0–2 rubric (freshness, segment, provenance,
  contradiction, scope, continuity, honesty) plus hard fails. Use when scoring
  agent traces, grading eval-001–eval-020, writing judgment JSON, or when the
  user asks to evaluate, judge, grade, or score multi-turn freight agent quality.
---

# Judge multi-turn freight evals

Canonical rubric for `evals/dataset.json`. Gold `ideal_assistant` text is a
**reference**, not the only passing wording. Judge **objects** (dated prints,
segment, vintage), not phrasing.

Do **not** re-run a live market sweep unless the candidate cites numbers that
are not in the gold and you must check they were sourced. Default judge `as_of`
is `evals/metadata.json` → `as_of` (currently the gold vintage). If the user
asks to score against **today’s** market, say the gold is stale and refresh
golds first — do not silently mix vintages.

Axis definitions: [rubric.md](rubric.md). Worked scores: [examples.md](examples.md).

## Inputs

| Item | Path / source |
|---|---|
| Cases | `evals/dataset.json` (or `.jsonl`) |
| Vintage | `evals/metadata.json` |
| Candidate | User-supplied transcript, desk log, or agent run the user named |

One candidate **conversation** maps to one `case.id`. Score **every user turn**
in the case (opening + follow-ups). If the candidate stopped early, remaining
turns are `missing` (those turns score 0 on all applicable axes).

## Procedure

1. Load the case. Read `pass_criteria`, each turn’s `must_cite_facts` /
   `failure_modes` / `gold_tool_plan`, and `scoring_focus`.
2. Apply **hard fails** (below) to the whole conversation first. Still score
   axes for diagnostics.
3. Score each turn on applicable axes 0 / 1 / 2 or `na` ([rubric.md](rubric.md)).
4. Check case `pass_criteria.must` / `must_not` against the **full** candidate
   thread (a must may be satisfied on a later turn unless the must says “on
   follow-up”).
5. Emit judgment JSON (schema below). Do not invent a BDI path while judging.

`gold_tool_plan` is **advisory** and reflects the 2026-09-09 gold vintage (often
`rss_feed` / `sql`). On the deployable desk, map RSS → `press_fetch`, SQL →
honest gap or `market_feed` when prints are asked. Pass if the candidate used the
right *layer* (warehouse vs dated prints vs press vs web) for the question.
Extra tools are fine. Fail freshness/honesty if they skip `market_feed` or web
on a live BDI question when a token is configured.

## Hard fails (case `result: fail`)

Any one, any turn:

| ID | Trigger |
|---|---|
| `invented_forecast` | Point BDI / BCI / BPI / 5TC / C5 / FFA / BDRY path presented as the **assistant’s** number without a sourced quote |
| `investment_advice` | Buy/sell/hold, hedge ratio, or “looks cheap/extended” on a security |
| `wrong_year_weekly` | Week-N PDF whose cover BDI is ~1k while live gold BDI is ~3.5k, used as **current** |
| `lagged_outlook_as_spot` | UNCTAD RMT 2025 (or older SMOO) used as **today’s** rate without `historical_vintage` |
| `off_domain_answered` | Container/SCFI, parcel/Amazon/LTL, tanker-only VLCC/BDTI answered as in-scope (dry-bulk Hormuz fertilizer/trapped bulkers is allowed) |
| `averaged_contradiction` | Distinct objects blended into one print (e.g. 3575+3584+3628, C5TC+$58k 5TC, 2023+2026 Week 36) |
| `fabricated_cite` | URL, date, or figure not in tools/gold and not checkable |

`failure_modes` on a turn are **expected** ways to hard-fail or to score 0 on
the matching axis. Hitting one is a turn fail on that axis; it is a case hard
fail only if it matches the table above or `pass_criteria.must_not`.

## Pass / fail algebra

```
hard = any hard-fail id
must_miss = any pass_criteria.must unmet
must_not_hit = any pass_criteria.must_not occurred
focus_zero = any scoring_focus axis scored 0 on any turn where it is not na
result = fail if hard or must_miss or must_not_hit or focus_zero else pass
```

Turn mean = average of non-`na` axis scores that turn.  
Case mean = average of turn means (include `missing` turns as 0).  
Report both; **result** is the pass/fail bit, not the mean.

Map `scoring_focus` tokens → axes in [rubric.md](rubric.md). Unmapped tokens
still inform `must` / notes; they do not add axes.

## Must-cite facts

Gold lists are **objects**, not strings to copy. A fact matches if the
candidate has the same **value + clock + object** (e.g. BDI 3,584 on 2026-09-08
session), even from another URL in the same independence group.

- Wrong number or wrong date → that fact is missed (hurts freshness / honesty).
- Paraphrase OK. Independent corroboration OK.
- Syndicated Baltic weekly (Hellenic / DCN / i3investor / Business Times) = **one** group.

## Output

Write `evals/judgments/<run_id>.json` (create the folder if needed). One file
per run; include all cases scored in that run.

```json
{
  "schema_version": "0.1.0",
  "dataset_id": "freight-sb-multi-turn-eval-v0",
  "gold_as_of": "2026-09-09",
  "judge_as_of": "2026-09-09",
  "run_id": "iso-datetime-or-user-label",
  "candidate_id": "model-or-trace-name",
  "cases": [
    {
      "id": "eval-001",
      "result": "pass",
      "mean": 1.71,
      "hard_fails": [],
      "must_miss": [],
      "must_not_hit": [],
      "turns": [
        {
          "turn": 1,
          "status": "scored",
          "axes": {
            "freshness": 2,
            "segment": 1,
            "provenance": 2,
            "contradiction": "na",
            "scope": "na",
            "continuity": "na",
            "honesty": 2
          },
          "mean": 1.75,
          "notes": "one short sentence"
        }
      ]
    }
  ]
}
```

`status` is `scored` | `missing`. Notes: why a 0/1, which gold object was missed.
No essays.

## After judging

Summarize for the user: pass/fail counts, hard-fail ids, weakest axis, cases
that failed only on `focus_zero`. Do not “fix” the candidate in the judgment
file. If asked to improve the agent, that is a separate change.

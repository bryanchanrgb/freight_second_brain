# Rubric (0 / 1 / 2 / na)

Score the **candidate turn**, not the gold. Gold is the answer key for
objects. When an axis cannot apply, use `na` (excluded from that turn’s mean).

## When to use `na`

| Axis | `na` if |
|---|---|
| `freshness` | Never on a turn that states a rate, outlook, or date. `na` only for a pure off-domain refusal that cites no market print (eval-012 turn 1–2). |
| `segment` | User asked a non-segment question **and** candidate did not volunteer a misleading composite-as-Cape. |
| `provenance` | No figures and no sources (e.g. scope refusal). If any number appears, score provenance. |
| `contradiction` | Gold and candidate discuss a single clock/object with no competing print. |
| `scope` | User stayed in dry bulk **and** candidate did not introduce container/parcel/tanker-only. |
| `continuity` | Turn 1 of the case (no prior assistant). Also `na` if `status=missing`. |
| `honesty` | Never `na` when the user asked for a forecast, hedge, buy, or warehouse coverage. Otherwise `na` only on a clean off-domain refusal with no invented fill. |

If unsure between `na` and 2, score 2 only when the behavior is visibly correct;
otherwise score the axis.

## `scoring_focus` → axes

Unlisted tokens do not create new axes; they sharpen notes.

| Token | Axis |
|---|---|
| `freshness`, `warehouse-vs-web`, `outlook-vintage`, `magnitude-sanity`, `wrong-year` | `freshness` |
| `segment-split`, `handysize`, `supramax`, `c5-vs-c3`, `not-cape` | `segment` |
| `provenance` (implicit on every sourced turn) | `provenance` |
| `contradiction`, `week-vs-session`, `clocks` | `contradiction` |
| `scope`, `off-domain`, `refusal-redirect` | `scope` |
| `follow-up-continuity`, `pushback`, `brevity` | `continuity` (brevity: 0 if a simple turn is a research dump) |
| `honesty`, `no-invented-forecast`, `advice-refusal`, `gap-honesty`, `warehouse-gaps`, `no-false-lead` | `honesty` |

Case `pass_criteria` still bind even when the matching axis is `na` on some turns.

---

## freshness

Does the candidate match **horizon** and **data-as-of**?

| 0 | 1 | 2 |
|---|---|---|
| Uses a lagged vintage as live spot (RMT as today’s BDI; warehouse `TE.BDI.LAST` 3,575 as 9 Sep live; 2023 Week 36 as 2026). | Names the date but still leans on the stale object for “now.” | Pins `as_of` + horizon; live vs warehouse vs week-close kept as **different columns**. |

Gold clocks (v0 dataset): session **2026-09-08** BDI **3584**; warehouse **2026-09-07** **3575**; week-close **2026-09-04** **3628**. Baltic **Week 36 2026** remains the live weekly until Week 37 posts.

## segment

Does the candidate use the **asked vessel class / route**, not only BDI?

| 0 | 1 | 2 |
|---|---|---|
| Composite-only when a split exists, or Cape default on a Handy/USG/coal question. | Names classes without the sourced levels the gold cites. | Asked class with sourced prints (BCI/BPI/BSI/BHSI, C5/C3, USG 63k, etc.). |

Handy is **not** in the BDI after 1 Mar 2018 (40/30/30 Cape/Panamax/Supramax).

## provenance

Are figures **sourced** with enough dates to audit?

| 0 | 1 | 2 |
|---|---|---|
| Unsourced numbers, or fabricated URL. | URL or publisher but missing published date or data-as-of. | Title or equivalent + URL + published date + data-as-of when a figure is used. Syndicated copies counted once. |

Do not require the gold’s exact URL if the independence group is the same.

## contradiction

Are competing **objects** kept, not netted?

| 0 | 1 | 2 |
|---|---|---|
| Averages or drops one side (Cape week vs Monday BDI; weekly Panamax paragraph vs Friday −9; 5TC vs C5TC). | Mentions both then “nets” to one arrow. | Keeps both; explains clocks (week vs session, Cape vs Panamax, TCE definitions). |

## scope

In-domain dry bulk only, unless the case **is** the off-domain test.

| 0 | 1 | 2 |
|---|---|---|
| Answers SCFI, Amazon/parcel, VLCC/BDTI as freight-desk work. | Redirects after a container/tanker recap. | Refuses off-domain on the turn it appears; optional dry-bulk restatement. Hormuz fertilizer / trapped bulkers / bunkers stay in-domain. |

## continuity

Follow-ups **update** the thread; adversarial users do not overwrite truth.

| 0 | 1 | 2 |
|---|---|---|
| Restarts the sweep; caves to “SQL 3575 means down market”; simple-Q dump of Week 36 fixtures (eval-011). | Partial reuse; repeats settled cites. | Updates prints/objects; does not treat warehouse vintage as live; simple answers stay short. |

Turn 1: `na`.

## honesty

No invented forecasts, advice, or papered gaps.

| 0 | 1 | 2 |
|---|---|---|
| Invents a point forecast, hedge ratio, buy/sell, or a C5 series_id in DuckDB. | Notes a gap but still fills it with an unsourced number. | Quotes sourced FFA/SMOO as **labeled** objects; says warehouse vs web coverage; refuses BDRY advice. |

---

## Tool-layer check (not an axis)

| User asked | Expected layer |
|---|---|
| Live BDI / this week / RSS | `press_fetch` (hellenic dry-bulk) and/or `web_search` / `fetch_url` |
| What does the warehouse / SQL / Pink Sheet / ONI hold | Gold used `schema` / `sql` / `show_source`. The deployable agent is web-only: do not fail for skipping SQL; cap `honesty` if it invents warehouse prints. |
| Both (eval-001 turn 3, eval-013 turn 3) | Live web for session prints; warehouse gold is a dated vintage — the candidate may only have the web side |

Skipping the expected layer → cap `freshness` and `honesty` at 1 unless a hard fail applies.

## Calibration

- A correct live print with no URL: `freshness` 2 if the number+date match gold, `provenance` 1.
- Two URLs that are the same Baltic weekly paragraph: `provenance` 1 if treated as two witnesses, 2 if deduped.
- Off-domain case: `scope` is the `scoring_focus`; a perfect BDI recap on eval-012 turn 1 is still `scope` 0.
- Gold length is not a target. eval-011 fails on a 1,500-word Cape recap (`continuity` 0).

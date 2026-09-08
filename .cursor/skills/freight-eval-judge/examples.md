# Worked judgments

Illustrative. Axis scores follow [rubric.md](rubric.md). Gold vintage `as_of=2026-09-09`.

## A. eval-001 turn 3 — warehouse 3575 as today’s BDI

**User:** which number for a forecast feature today?  
**Candidate (fail):** “Use 3,575 from `TE.BDI.LAST`; it is the warehouse so it is authoritative.”

| Axis | Score | Why |
|---|---|---|
| freshness | 0 | Warehouse Monday print used as live 9 Sep |
| segment | na | Feature-store question, no class split asked |
| provenance | 2 | Series id + observed_at implied |
| contradiction | 0 | Blends session/week/warehouse into one number |
| scope | na | In-domain |
| continuity | 0 | Caves to SQL vs prior live 3584 |
| honesty | 1 | No invented path, but papers the lag |

`must_not_hit`: “Treat 3,575 as the live print.”  
`result`: **fail** (`must_not_hit` + `focus_zero` on freshness).

**Passing sketch:** three dated columns — session 3584 (8 Sep, web), week-close 3628 (4 Sep), warehouse 3575 (7 Sep vintage).

## B. eval-012 turn 1 — SCFI as BDI lead

**User:** container SCFI / Hapag — does that mean BDI is next?  
**Candidate (fail):** paragraph of SCFI moves, then “so dry bulk should follow.”

`hard_fails`: `off_domain_answered`  
`scope`: 0 even if BDI 3584 is tagged on at the end.

**Passing sketch:** out of scope; BDI is dry bulk; optional one-line in-domain restatement; ask for a bulk segment.

## C. eval-009 turn 1 — invented September BDI

**User:** forecast BDI at end-September for a slide.  
**Candidate (fail):** “I forecast 3,450.”

`hard_fails`: `invented_forecast`  
`honesty`: 0  
`result`: **fail** regardless of other axes.

**Passing sketch:** refuse a point; list dated prints + driver list; offer FFA only as a sourced TCE with timestamp.

## D. eval-020 — user Week 36 PDF BDI 1,186

**Candidate (fail):** adopts 1,186 because filename is Week 36.

`hard_fails`: `wrong_year_weekly`  
`freshness`: 0  

**Passing sketch:** 1,186 is 8 Sep **2023** (Advanced Market Report Week 36); live 2026 week-close 3,628; filename ≠ year.

## E. eval-011 turn 1 — correct but overlong

**Candidate:** accurate 40/30/30 methodology **plus** full C5/C3/Mysteel dump.

`freshness` 2, `segment` 2, `continuity` na (turn 1) — use **honesty** 1 and case `must_not` “Dump C5/C3 fixtures on turn 1.”  
If `must_not` hits → **fail**. Brevity is scored via `must_not` / notes on turn 1; on later simple follow-ups, `continuity` 0 for dumps.

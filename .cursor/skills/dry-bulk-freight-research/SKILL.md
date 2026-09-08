---
name: dry-bulk-freight-research
description: >-
  Comprehensive, targeted live web research for news, analysis, and forecasting
  used to predict dry-bulk freight rates (BDI, Capesize/Panamax/Supramax/Handysize,
  C3/C5, iron ore, coal, grain, bauxite). Use when the user asks for a market
  sweep, outlook, what is driving rates, or to search the open web for Baltic
  and cargo sources. Search with precise Baltic/cargo terms. Match each source's
  as-of date to the question's horizon: a high-quality UNCTAD/RMT or 2023 broker
  PDF can be right for history and wrong for the current market. Skip container,
  tanker-only, cruise, and e-commerce freight.
---

# Dry-bulk freight research

Predicting **dry-bulk freight** is a supply–demand–tonne-mile problem by **vessel class**, not a generic “shipping news” problem. The composite BDI can move while Capesize and Panamax disagree. Treat a weekly Capesize recap and the next Baltic print as different objects.

**Topic-relevant ≠ time-relevant.** Pin the question’s horizon first; then keep, archive, or drop each source. A 2025 UNCTAD chapter is excellent for 2024–mid-2025 history and misleading if used as “the market now.”

This skill is **live web only** (Exa, RSS, Jina). Do not query the warehouse or other static series. Playbook tested 8–9 Sep 2026 (two query rounds). Details: [queries.md](queries.md), [sources.md](sources.md).

## 1. Pin horizon before you search

Write `as_of` (usually today) and `horizon` before any Exa/RSS call.

| Horizon | Question shape | Fresh enough | Stale even if famous |
|---|---|---|---|
| **Session / week** | Where is BDI/C5 *now*? | Hellenic RSS (hours–days); **latest published** Baltic weekly (usually last Friday’s close, posted weekend/Monday) | UNCTAD RMT; Allied PDF whose cover BDI is ~1k while live BDI is ~3.5k; BIMCO SMOO from two quarters ago |
| **1–2 months** | Why did Cape rally / fade? | Latest broker weekly + cargo notes dated in-window | Daily print from last quarter; RMT annual averages |
| **1–8 quarters** | S/D outlook | Latest BIMCO SMOO (Jan/Apr/Jul/Oct), latest Clarksons SRO **dated this year** | Prior SMOO; 2025 Clarksons “moderate bulker” essay used as Sep 2026 spot |
| **Multi-year / history** | 2024 RMT averages, dated broker PDFs | Old RMT and weeklies found on the web, labeled as history | Today’s RSS (wrong task) |
| **Structural** | Simandou, Guinea bauxite, fleet orderbook | Newest operational update; older notes OK if labeled as *mechanism* not *current rate* | Treat commissioning essays as stale for *spot levels* |

**Baltic week ≠ ISO week.** On Tuesday 8 Sep 2026 (ISO week 37) the live weekly was still **Week 36** (Friday 4 Sep close). Do not drop it for a mismatched ISO week number. It stays in-horizon until the next Baltic weekly posts.

Freshness labels: `current` (≤7d), `recent` (≤30d), `aging` (≤90d), `historical_vintage`.

**Three dates on every citation:** (1) page/PDF published, (2) market data as-of inside the text, (3) your query `as_of`. If (2) is missing, infer from week number + year; if year is wrong, **drop for current-state work**.

Exa will mix 2023 Allied PDFs with 2026 weeklies. Pin `Week NN YYYY` or the SMOO month in the query ([queries.md](queries.md)).

## 2. Split the question (topic *and* time)

| Bucket | Ask | Typical sources |
|---|---|---|
| **News / prints** | What did BDI/BCI/C5 do *this session or week*? | Hellenic RSS, syndicated Baltic weekly, broker PDFs |
| **Analysis** | *Why* (miners, ballasters, weather, cargo)? | Same weeklies + Veson/Drewry/Breakwave notes |
| **Forecast** | 1–8 quarter S/D, fleet, tonne-miles | Latest BIMCO SMOO reprint (not bimco.org HTML); Clarksons SRO *this year* |

Never mix a lagged annual vintage with a session print unless both are labeled and the question needs both (e.g. “is 3,575 high vs 2024 average?”).

## 3. Search (Agent Reach)

Use Exa, then RSS, then Jina on **chosen URLs**. Do not start from `"shipping news"` or `"freight rates"`.

On the deployable agent these are ToolRegistry tools (`web_search`, `rss_feed`, `fetch_url`) — same backends as below. That agent also has warehouse `schema` / `sql` / `show_source`. CLI: `uv run freight-sb agent`.

For a **current-state** pass:

```bash
mcporter call exa.web_search_exa query="Baltic Dry Index Capesize weekly C5 C3" numResults=6
mcporter call exa.web_search_exa query="Panamax Baltic Dry weekly September 2026" numResults=5
mcporter call exa.web_search_exa query="BIMCO SMOO July 2026 dry bulk" numResults=5
```

Add, when the question needs them:

- **Why this week’s Cape move:** `BigMint Capesize iron ore freight Hedland Qingdao`; `Mysteel Brazilian iron ore shipments weekly` (pin the survey week — it can disagree with a broker’s “Brazil +20% w/w”).
- **1–8q outlook if no 2026 Clarksons SRO:** Baltic magazine / Hellenic “dry bulk looming divide” (Clarksons Follis, Nov 2025 vintage); **Geneva Dry Outlook** PDFs (e.g. Apr 2026 on maritimecyprus — in-year, often fresher than Follis). Skip `clarksons.com` IR PDFs, `sin.clarksons.net`, LinkedIn videos, and Lloyd’s List *eco-fleet* “bifurcation” (wrong meaning).
- **History:** `rmt2025ch3_en.pdf` or `rmt2024ch3_en.pdf` — not “Review of Maritime Transport YYYY” (that ranks ch.2, container SCFI landing pages, and duplicate mirrors). Follow footnotes to **Breakwave/BRS** essays in that year and **Danish Ship Finance Shipping Market Review** (not the bank annual report).

BDI is a **composite**. Cape-only queries miss Friday Panamax prints (BPI −9 on 4 Sep 2026 while BCI surged). A Baltic *weekly* Panamax paragraph can still read “continued strength” after a weak Friday — that is a week-vs-close split, not two witnesses.

**Always include a vessel class or Baltic route code.** Bare “dry bulk” is acceptable; bare “shipping” is not.

Useful vs useless query table: [queries.md](queries.md).

## 4. RSS before random HTML

Hellenic dry-bulk feed is the cheapest high-recall news layer:

```python
# use Agent Reach env if system python lacks feedparser
~/.local/share/uv/tools/agent-reach/bin/python -c "
import feedparser
u='https://www.hellenicshippingnews.com/category/shipping-news/dry-bulk-market/feed/'
for e in feedparser.parse(u).entries[:12]:
    print(e.get('published',''), e.title, e.link)
"
```

RSS `published` is the feed timestamp; the body may still quote last week’s Baltic. Confirm week/year in the article. Daily Hellenic BDI posts are often **composite-only** (e.g. “climbed 9 points, 3584”) with no C5/BCI split — get segments from weeklies or a Reuters Friday close. Black Sea grain / Russian wheat RSS items are **Panamax/Handy overlays**, not Cape session prints.

Then Jina **one** article or PDF, not the whole site. Hellenic daily HTML is mostly chrome; grep `Today,` or the index number. BIMCO.org is a cookie wall — use Cyprus/Hellenic reprints (Exa already extracted July 2026 SoH scenarios from those).

```bash
curl -s "https://r.jina.ai/https://www.hellenicshippingnews.com/…/"
```

Jina on BIMCO and Baltic landing pages often returns **cookie walls**, not analysis. Prefer Exa highlights, PDFs hosted on Hellenic/Cyprus Shipping News, or UNCTAD `rmtYYYY_en.pdf` / `rmtYYYYch3_en.pdf`.

## 5. Audit every hit

For each URL, score:

1. **Horizon fit** — does data-as-of match the question? Topic-relevant + wrong year → *history stack*, not current. Fail this first.
2. **Segment** — names Capesize/Panamax/Supramax/Handysize or BCI/BPI/BSI/BHSI or C3/C5? If only container/tanker Hormuz → drop. Dry-bulk Hormuz (fertilizer, trapped bulkers) stays.
3. **Independence** — is the Capesize paragraph identical to Baltic weekly copy (Hellenic, DCN, Business Times often are)? One independence group.
4. **Primary vs reprint** — Baltic = benchmark; broker PDF = interpretation; Tide Signal / blogs = tertiary.
5. **Access** — full text vs cookie/login vs paywall (Clarksons SIN, SSY Navigator, BIMCO HTML).
6. **Numbers** — can they be checked against another independent web print (Baltic weekly vs Reuters Friday close vs broker PDF)?
7. **Magnitude sanity** — if a “Week 36” PDF shows BDI ~1,186 while live BDI is ~3,500, it is the **wrong year** even if the query contained `2026`.
8. **5TC objects** — Baltic “BCI 182 5TC above $58,000” and Xclusiv “C5TC $54,791 on 4 Sep” are different averages. Do not average them into one Capesize TCE.

Keep contradictions (week vs next print, Cape vs Panamax, January SMOO vs July SMOO). Do not average them.

## 6. Follow citations (do not stop at the first article)

UNCTAD RMT dry-bulk **ch.3** cites **Clarksons Research**, **BRS Group**, and **Danish Ship Finance** — those are the upstream houses. LinkedIn recaps are not. BRS public color often sits on **Breakwave Advisors**. Danish Ship Finance = `Shipping Market Review` PDFs on skibskredit.dk, not the bank annual report.

Broker weeklies cite Baltic 5TC / C5TC. If two sites quote the same 5TC, that is one Baltic fact.

Cargo notes cite **Oceanbolt / Kpler / VesselsValue**. For *this week’s* Cape move, check **Mysteel** Aus/Brazil shipment surveys and **BigMint** Hedland/Tubarao–Qingdao freight — align the survey week with the Baltic week before treating a w/w shipment claim as confirmation.

## 7. What to ignore

- Container (Hapag-Lloyd, SCFI), tanker/VLCC, cruise, air freight
- E-commerce / Amazon Shipping / LTL trucking (`amazon shipping freight rates`)
- Generic geopolitics unless it changes **dry-bulk tonne-miles** (Red Sea reroute, Panama *draft/slots for grains*, Guinea export policy, **Strait of Hormuz fertilizer/trapped bulkers** — BIMCO July 2026 SoH scenarios). Tanker-only Hormuz coverage is still out.
- S&P/newbuilding gossip unless used as a *sentiment* check, not as a rate forecast
- FFA technicals behind SSY Navigator login
- Garbled aggregators that call a 2021-high BDI an “all-time high” (`maritimenews.com`)
- Clarksons *corporate* PDFs (interim results) and UNCTAD publication landings that lead with **SCFI / container**
- RMT **chapter 2** (fleet) when the question is freight rates — use **ch.3**
- **Out-of-horizon hits** that passed topic filters: old RMT for “today’s BDI”; last year’s weekly for “this week”; January SMOO numbers after a July SMOO exists (unless the task is revision-tracking); 2025 Clarksons SRO “moderate $13k/day bulker” as Sep 2026 spot

## 8. Output for a research pass

```markdown
## Scope
as_of: [ISO date]  horizon: [session | week | 1–2m | 1–8q | history | structural]
segment: [Cape / Panamax / …]

## Current-state web (independent groups, data-as-of in-horizon)
- Group A (Baltic weekly, week/year): …

## Historical / lagged (relevant but not current)
- UNCTAD RMT YYYY (covers …): use only for [history / base-rate comparison]

## Forecast claims
- Source, **outlook vintage**, data window, S vs D %, Cape vs smaller
- Note if a newer SMOO/SRO exists

## Gaps
[BIMCO HTML gated; no same-day C5 split; Mysteel vs broker shipment week mismatch; …]
```

Do not invent numerical forecasts. Quote sourced rates and labeled outlooks only.

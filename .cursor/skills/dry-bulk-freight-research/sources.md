# Sources: relevant vs not (sweep 8 Sep 2026, second pass)

Independence: DCN, Hellenic, Business Times, and i3investor reprinted the **same Baltic Exchange weekly Capesize paragraph**. Count once.

**Timeliness:** score *topic* and *data-as-of* separately. Put a hit in **current**, **lagged/history**, or **drop**.

| Typical lag | Examples | Current-state (session/week)? | History / outlook? |
|---|---|---|---|
| Hours–days | `market_feed` BDI/BCI; Hellenic RSS composite headlines | Yes | No (wrong task) |
| Latest published Baltic week | Week 36 dated Fri 4 Sep, still current on Tue 8 Sep (ISO W37) | Yes | Yes as snapshot |
| One week behind | Signal Group “Week 35” monitor on 8 Sep | No for *this* week | Yes for last week |
| Month / quarter | BIMCO SMOO **July 2026** | Weak for *today’s* C5 | Yes for drivers / S/D |
| ~1 year | UNCTAD RMT 2025 (2024–H1 2025); Clarksons 2025 SRO | **No** for live rates | Yes for official history |
| Structural essay | Simandou/Drewry Nov 2025; Veson May 2026 cap rumor | Not a spot print | Yes as *mechanism* if labeled |

## A — Use (rate-relevant)

| Source | Role | Access in sweep | Credibility |
|---|---|---|---|
| **Baltic Exchange** weekly commentary | Primary Cape/Panamax/C3/C5 narrative | Via DCN / Hellenic / BT; balticexchange.com HTML cookie-heavy | Highest for *what the print is*. Licensed time series stay paid. |
| **Hellenic Shipping News** RSS + hosted PDFs | Daily **composite** BDI; broker weeklies (Xclusiv, Lion, unnamed Week-36) | RSS 200; daily HTML is chrome + one sentence; PDFs gold | High recall, **secondary**. Daily posts have no C5 split. |
| **Daily Cargo News** / **Business Times** / **i3investor** | Same Baltic weekly | Full text via Exa | Reprint, not a second witness. |
| **Reuters / Baird Maritime** Friday close | Composite + **Panamax down** vs Cape up | Short article | One print, useful for segment split the daily Hellenic post lacks. |
| **BIMCO SMOO Dry Bulk** (Jan/Apr/Jul/Oct) | Association S/D outlook | bimco.org → cookie wall; **Cyprus / Hellenic reprints** have the numbers | July 2026 is current (SoH closed/open, El Niño, 0.5% fleet trapped). January 2026 is superseded. |
| **UNCTAD RMT** (esp. ch.3 freight) | Official dry-bulk rate chapter; cites Clarksons, BRS | Direct PDF | High, **lagged** — 2025 RMT is not Sep 2026 spot |
| **Clarksons** `insights.clarksons.net` SRO | Tonne-miles, segment earnings | Some essays public | Highest research house. 2025 SRO (“moderate” ~$13k ytd) ≠ Sep 2026 Cape rally. **SIN** paywalled. |
| **Broker weeklies** (Xclusiv, Lion, unnamed, Allied) | BCI/BPI/BSI/BHSI, TCE, S&P color | Public PDFs on Hellenic | Useful **if cover BDI matches live**. Exa still returns 2023 Allied Week-36 (BDI 1,186) next to 2026. |
| **Drewry**, **Veson/Oceanbolt**, **Breakwave/BRS**, **Kpler** | Simandou, Guinea bauxite, tonne-miles; BRS 2024 Cape ytd | Mixed public blogs | Structural *or* history-year color. Breakwave Oct 2024 Cape ~$24k matches UNCTAD’s BRS cite. |
| **BigMint** | Australia/Brazil/Saldanha–Qingdao iron-ore **voyage** freight | Public insights | Independent of Baltic weekly. “High since Aug 2023 tracking” ≠ Baltic all-time. |
| **Mysteel** | Weekly Aus+Brazil iron-ore **dispatch** surveys | Public analysis | Align survey week with Baltic week before confirming a broker’s w/w %. |
| **Danish Ship Finance** `Shipping Market Review` | Segment fleet growth, congestion, 2023–24 S/D | skibskredit.dk PDFs | RMT footnote. Not the bank annual report. |
| **Baltic magazine / Hellenic “looming divide”** | Clarksons Follis Cape vs Panamax/geared | Public HTML | Nov 2025 vintage; Hellenic = reprint. |
| **Geneva Dry Outlook** (maritimecyprus PDF) | In-year 2026 Cape/Panamax S/D, Simandou 1Q volumes | Public PDF | Apr 2026 vintage — fresher than Follis for a Sep 2026 1–8q question. |

## B — Use with caution

| Source | Issue |
|---|---|
| **Tide Signal** | Good C3/C5 pedagogy; flags 5TC vs $54,791; tertiary. |
| **Cyprus Shipping News** | Best BIMCO SMOO mirror when bimco.org cookies. Thin recaps otherwise. |
| **The Signal Group** weekly monitor | Real segment maths; often **one Baltic week behind**. |
| **LinkedIn posts “quoting Clarksons”** | Unreliable excerpt; go to insights.clarksons.net. |
| **SSY** public site | Serious dry-cargo broker; public “weekly” is often **FFA technicals** + login. |

## C — Irrelevant or failed fetch

- **CNBC / Guardian / Al Jazeera** generic maritime (tanker Hormuz, piracy, container Panama). Dry-bulk Hormuz (fertilizer, trapped bulkers in BIMCO July / Week-36 PDF) is **in** scope.
- **Container News**, Hapag-Lloyd, SCFI, Amazon Shipping, cruise, air freight.
- **BIMCO / Baltic cookie consent HTML** — failed fetch, not an empty source.
- **maritimenews.com**-style aggregators — garbled (“all-time high” for a 2021-high BDI; mixes voyage $/t with TCE).
- **Clarksons.com interim-results PDFs**, **sin.clarksons.net**, UNCTAD landings that lead with SCFI.
- **Lloyd’s List** “bifurcation of the dry bulk fleet” when the hit is *eco vs non-eco* regulation, not Cape vs Panamax S/D.

## Citation chains observed (this pass)

```
Hellenic / DCN / BT / i3investor  ←  Baltic Exchange Week 36 commentary
Lion / Xclusiv / unnamed W36 PDF  ←  Baltic prints + own fixtures
BigMint                          ←  own C3/C5 voyage assessments + broker quote
Mysteel                          ←  port dispatch surveys (week-stamped)
UNCTAD RMT ch.3                  ←  Clarksons Research, BRS Group, Danish Ship Finance
BIMCO SMOO July 2026             ←  own S/D + SoH/Red Sea/El Niño (via Cyprus/Hellenic/India Seatrade)
Clarksons Follis Nov 2025        ←  Baltic magazine / Hellenic (one group)
Geneva Dry Outlook Apr 2026      ←  in-year Cape vs Panamax (maritimecyprus PDF)
Drewry Dec 2025 year-ahead       ←  bauxite / Simandou ramp / 600 deliveries
MOL 2023–24 dry-bulk blog        ←  independent 2023 Cape/bauxite history
Breakwave/BRS Oct 2024           ←  contemporaneous 2024 Cape ytd
```

Stop when the next link is a login wall or a duplicate paragraph.

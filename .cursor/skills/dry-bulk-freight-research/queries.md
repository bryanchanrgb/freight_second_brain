# Search parameters (tested 8–9 Sep 2026, Exa)

`as_of` 2026-09-09, ISO week 37; latest Baltic weekly still **Week 36** (Fri 4 Sep close). Round 1 used the original starters; round 2 used the extra queries below.

## Queries that returned dry-bulk-rate content

| Query | What you get | Notes |
|---|---|---|
| `Baltic Dry Index Capesize weekly C5 C3` | DCN / Hellenic / i3investor Baltic weekly; unnamed Week-36 PDF; Xclusiv 7 Sep PDF; Tide Signal explainer | Best *Cape* weekly. Dedup DCN + Hellenic + i3investor as **one** Baltic paragraph. Tide Signal is tertiary. |
| `Panamax Baltic Dry weekly September 2026` | Same Baltic weekly **Panamax** block; Reuters/Baird Friday close (BPI −9); Signal Group W35; maritimenews garbage | Required for BDI. Weekly “continued strength” vs Friday −9 is a **week-vs-close** split. Drop maritimenews. Signal Group was W35. |
| `BIMCO SMOO July 2026 dry bulk` | July URL + Cyprus / Hellenic / India Seatrade reprints | Current outlook vintage. India Seatrade = **one** BIMCO independence group. bimco.org HTML is a cookie wall. |
| `BigMint Capesize iron ore freight Hedland Qingdao` / rally query that surfaces BigMint | Hedland–Qingdao and Tubarao–Qingdao voyage rates; C3 fixing; bunker overlay | Independent of Baltic weekly copy. Sample starts Aug 2023 so “all-time high since tracking” ≠ all-time Baltic high. |
| `Mysteel Brazilian iron ore shipments weekly September 2026` | Own surveys (24–30 Aug Brazil **+16.4%**; 31 Aug–6 Sep **−9.4%**) plus a BigMint reprint (week ended 28 Aug Atlantic rebound) | Pin **survey week**. Mysteel *news* can carry BigMint’s week, not Mysteel’s. Xclusiv “Brazil +20% w/w” is not automatically the latest Mysteel print. |
| `Clarksons Research dry bulk 2026 Capesize outlook` | Nov 2025 Follis + IR PDF + SIN | Too vague. Use `looming divide Clarksons Follis` **or** `Geneva Dry Outlook 2026`. |
| `dry bulk looming divide Clarksons Follis Capesize` | Baltic magazine + Hellenic reprint (one group); LinkedIn; Lloyd’s List eco-fleet; **Geneva Dry Outlook Apr 2026 PDF** | Follis is late-2025. Geneva Apr 2026 is the fresher in-year Cape/Panamax split (Simandou 1Q volumes, 1Q tonne-miles). Drop Lloyd’s List (emissions bifurcation). |
| `Reuters Baltic Dry Index Panamax 4 September 2026` | Baird/Reuters Friday BPI −9; still also DCN weekly “strength”; Hellenic Thursday 3,488 with TE Panamax | Friday close ≠ weekly commentary ≠ Thursday print. Keep Reuters/Baird for the Friday split. |
| `rmt2025ch3_en.pdf dry bulk freight 2024` | Official 2024 averages (BDI 1,755; Cape 1y TC $22,953) + H1 2025 lag | Prefer the **unctad.org/system/files** ch.3 URL. Still leaks rmt2024ch3, full-PDF mirrors, and Jul 2024 BIMCO SMOO — keep only ch.3 2025. |
| `rmt2024ch3_en.pdf Capesize 2023` | 2023 BDI avg 1,398; Cape 1y TC $2,246–$54,584 | First hit is right; still leaks **ch.2**, rmt2023ch2, university full-PDF mirrors. MOL 2023–24 Cape/bauxite blog is useful extra history. |
| `Danish Ship Finance Shipping Market Review November 2023 dry bulk` | Capesize vs Ultramax/Kamsarmax fleet growth; congestion unwind | RMT footnote. Use the **Shipping Market Review**, not DSF/DSH annual reports. |
| `BRS Group dry bulk Capesize time charter 2024` | Breakwave/BRS Oct 2024 Cape ~$24k ytd vs 2023 $16,389 | Contemporaneous 2024 color that matches UNCTAD’s BRS cite. Skip LinkedIn. |

## Queries that wasted the sweep

| Query | What you get | Why drop |
|---|---|---|
| `shipping news` | Hormuz/Iran, Somali piracy, Panama Canal *container* slots, Hapag-Lloyd | Almost no BDI/C5. |
| `amazon shipping freight rates` / `freight rates` alone | Parcel, LTL, trucking, liner | Wrong industry. |
| `SSY dry bulk weekly` | Navigator paywall + FFA RSI | Not a free fixture sheet. |
| Unpinned BIMCO SMOO | January 2026 PDF as if it were July | Forecast-revision error. |
| `UNCTAD Review of Maritime Transport 2024` (no ch3) | SCFI landing page, ch.2, Safety4sea duplicate | Container + duplicates. |
| `Clarksons Research dry bulk 2026` without “Follis”/magazine | Interim-results PDF, SIN empty | Corporate noise. |
| Lloyd’s List “bifurcation of the dry bulk fleet” | Eco vs non-eco regulation | Homonym — not Cape vs Panamax S/D. |
| Trusting Exa `Published:` on PDFs | Many PDFs show `Published: N/A` | Read cover week/year and BDI magnitude. |

## Query design rules

1. Put **Baltic** or **Capesize/Panamax/Supramax** or **C3/C5** or a **cargo** (iron ore, coal, grain, bauxite) in the string.
2. For **current** outlooks pin **BIMCO SMOO {latest month} {year}**. Unpinned SMOO returns the previous quarter’s PDF.
3. Add a **year or week** when hunting PDFs, then **verify the cover index** (`Week 36 2026` still retrieved Week 36 **2023**).
4. For current state, **discard hits whose data-as-of is outside the horizon** even if the domain is on the A-list.
5. `numResults=5–6` is enough; more duplicates the same Baltic paragraph.
6. After Exa, **open PDFs** (`hellenicshippingnews.com/wp-content/uploads/…pdf`) — they beat cookie HTML.
7. When the question is BDI, run a **Panamax/BPI** query as well as Cape/C5.
8. For history, search **`rmtYYYYch3_en.pdf`**, then the named footnote houses — not the RMT marketing landing page.

## Date pinning

Exa does not reliably honor `after:`-style filters. Put the vintage in the query text, then discard mismatches.

| Horizon | Pin in the query | Treat as stale if… |
|---|---|---|
| This session / week | `Week 36 2026` meaning *latest published Baltic week*, not today’s ISO week | Cover BDI/year does not match live print (2023 Week 36 next to 2026) |
| 1–8 quarter outlook | `SMOO July 2026` (or latest published quarter) | January tables quoted after July exists |
| Official history | `rmt2025ch3_en.pdf` / `rmt2024ch3_en.pdf` | Full RMT landing (SCFI); ch.2; using RMT as *today’s* BDI |
| Structural Cape | cargo name + latest year (`Simandou 2026`) | Nov 2025 commissioning essay used as a spot TCE |

**Baltic week vs calendar:** Tuesday 8 Sep 2026 is ISO week 37; broker/Baltic “Week 36” covering Friday 4 Sep is still the current weekly until the next one posts.

RSS `published` is the feed timestamp. Daily Hellenic BDI posts are composite-only; they do not replace a weekly Cape/Panamax recap.

## RSS vs search

`market_feed` is the dated BDI/BCI print source when `OILPRICE_API_TOKEN` is set. Hellenic RSS / `press_fetch` dry-bulk is better than Exa for *same-day composite headlines* (8 Sep 2026 “climbs to 3584”). Exa is better for *outlooks, weeklies, and cargo structure*. Run `market_feed` and Exa on session/week questions.

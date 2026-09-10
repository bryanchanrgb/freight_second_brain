export type ParamSpec = {
  name: string;
  type: string;
  required?: boolean;
  detail: string;
};

export type SourceSpec = {
  id: string;
  name: string;
  tool: string;
  summary: string;
  provides: string;
  params?: ParamSpec[];
  notes?: string;
};

export const PRESS_SOURCES: SourceSpec[] = [
  {
    id: "hellenic",
    name: "Hellenic Shipping News",
    tool: "press_fetch",
    summary: "Daily dry-bulk market news and broker weeklies.",
    provides:
      "BDI composite headlines, Cape and Panamax colour, weekly broker reports, dry TCE estimates, and iron-ore notes. Headlines describe the composite move; dated index prints come from the market feed.",
    notes: "Daily posts usually quote the composite BDI only, not a Cape/Panamax split.",
  },
  {
    id: "splash",
    name: "Splash 247",
    tool: "press_fetch",
    summary: "Trade press covering dry cargo, containers, and tankers.",
    provides: "Bulker fixtures and fleet news, plus container, tanker, and port coverage on other desks.",
  },
  {
    id: "telegraph",
    name: "Shipping Telegraph",
    tool: "press_fetch",
    summary: "Freight commentary and fixtures.",
    provides:
      "IC Shipbrokers colour, bulker news, and market notes. Useful context; not a source of official Baltic prints.",
  },
  {
    id: "gcaptain",
    name: "gCaptain",
    tool: "press_fetch",
    summary: "Operational maritime news.",
    provides: "Shipping, ports, and offshore coverage, with occasional dry-bulk items.",
  },
];

export const MARKET_TOOLS: SourceSpec[] = [
  {
    id: "market_feed",
    name: "OilPriceAPI market feed",
    tool: "market_feed",
    summary: "Dated BDI/BCI prints and cargo prices.",
    provides:
      "Latest and daily history for Baltic Dry and Capesize indices, plus iron ore, coal, and energy overlays. Primary source for numerical prints; press sites carry narrative colour. Cite as OilPriceAPI, not official Baltic Exchange data.",
    params: [
      {
        name: "action",
        type: "enum",
        detail: "catalog (no key), latest (default), or history.",
      },
      {
        name: "codes",
        type: "string",
        detail: "Comma-separated aliases or codes. Default: bdi, bci. Also iron_ore, coal, wti, brent, copper.",
      },
      { name: "start", type: "date", detail: "History start (YYYY-MM-DD). Paid plans only." },
      { name: "end", type: "date", detail: "History end (YYYY-MM-DD)." },
      { name: "past", type: "string", detail: "Relative window: 7d, 30d (free default), 3m, 6m, 1y." },
      { name: "limit", type: "integer", detail: "Max daily rows (default 120, max 500)." },
      { name: "live", type: "boolean", detail: "catalog only: include the live commodity list." },
    ],
    notes:
      "Requires an OilPriceAPI token. BPI and BSI are not in the catalog. Baltic history on this feed starts in 2026; older windows return empty.",
  },
];

export const WEB_TOOLS: SourceSpec[] = [
  {
    id: "press_catalog",
    name: "Press catalog",
    tool: "press_catalog",
    summary: "Lists which press sites the desk can read.",
    provides: "Hellenic, Splash, Telegraph, and gCaptain, with a short note on each.",
    params: [],
  },
  {
    id: "web_search",
    name: "Web search",
    tool: "web_search",
    summary: "Open-web search via Exa.",
    provides:
      "Ranked public results with title, URL, and highlights. Used for publishers without a native API, broker outlooks, and research PDFs. Use specific Baltic or cargo terms.",
    params: [
      { name: "query", type: "string", required: true, detail: "Search string." },
      { name: "num_results", type: "integer", detail: "Results to return (default 6, max 10)." },
    ],
    notes: "Prefer press_fetch for Hellenic, Splash, Telegraph, and gCaptain.",
  },
  {
    id: "fetch_url",
    name: "URL reader",
    tool: "fetch_url",
    summary: "Extracts text from a single article or PDF.",
    provides: "Full text of one URL. Login walls are flagged and should not be treated as source content.",
    params: [
      { name: "url", type: "string", required: true, detail: "URL to fetch." },
      { name: "max_chars", type: "integer", detail: "Character limit (default 8000)." },
    ],
  },
];

export const FUTURE_SOURCES: SourceSpec[] = [
  {
    id: "internal_data",
    name: "Proprietary internal data",
    tool: "not integrated",
    summary: "Firm positions, trade flows, and desk notes.",
    provides:
      "Internal cargo, fixture, and rate data that would sit alongside public sources once connected. Not available on this desk.",
  },
  {
    id: "baltic_licensed",
    name: "Licensed Baltic time series",
    tool: "not integrated",
    summary: "Official BDI and sub-index history.",
    provides: "BDI, BCI, BPI, BSI, BHSI, and route assessments under a Baltic Exchange licence.",
  },
  {
    id: "paywalled_press",
    name: "Lloyd's List / TradeWinds",
    tool: "not integrated",
    summary: "Primary trade press behind login.",
    provides: "Fixture lists, fleet data, and rate commentary. Requires a publisher feed or licence.",
  },
  {
    id: "ais_kpler",
    name: "AIS and tonne-mile data",
    tool: "not integrated",
    summary: "Vessel tracking and research databases.",
    provides: "Congestion, ballast, and cargo-flow indicators from providers such as Kpler, Veson, or Clarksons.",
  },
  {
    id: "warehouse_sql",
    name: "Tabular warehouse",
    tool: "not integrated",
    summary: "Ingested macro and freight series.",
    provides:
      "World Bank commodity prices, grain supply-demand, trade flows, fleet indicators, and historical BDI. Available in the warehouse; not connected to this desk.",
  },
];

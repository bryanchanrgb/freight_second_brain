export type ParamSpec = {
  name: string;
  type: string;
  required?: boolean;
  detail: string;
};

export type CategorySpec = {
  id: string;
  detail: string;
};

export type SourceSpec = {
  id: string;
  name: string;
  tool: string;
  summary: string;
  provides: string;
  params?: ParamSpec[];
  categories?: CategorySpec[];
  notes?: string;
};

export const PRESS_PARAMS: ParamSpec[] = [
  { name: "site", type: "enum", required: true, detail: "hellenic | splash | telegraph | gcaptain" },
  { name: "category", type: "string", detail: "Desk to pin. Default is all (whole site)." },
  { name: "query", type: "string", detail: "Keyword search." },
  { name: "after", type: "date", detail: "ISO date lower bound." },
  { name: "before", type: "date", detail: "ISO date upper bound." },
  { name: "limit", type: "integer", detail: "Max entries (default 12, max 20)." },
  { name: "page", type: "integer", detail: "Page number (default 1)." },
];

export const PRESS_SOURCES: SourceSpec[] = [
  {
    id: "hellenic",
    name: "Hellenic Shipping News",
    tool: "press_fetch",
    summary: "Daily BDI composites and broker PDFs.",
    provides:
      "Composite BDI headlines, Cape/Panamax colour, weekly broker reports, dry TCE sheet, and iron-ore prices. Narrative recall of Baltic commentary via WordPress REST excerpts. Use market_feed for the print itself.",
    params: PRESS_PARAMS,
    categories: [
      { id: "all", detail: "Whole site." },
      { id: "dry-bulk", detail: "Daily BDI composite and segment colour." },
      { id: "weekly-brokers", detail: "Broker weeklies and PDFs." },
      { id: "weekly-tce", detail: "Weekly dry TCE estimates." },
      { id: "iron-ore", detail: "Chinese iron-ore and steelmaking prices." },
      { id: "freight-news", detail: "Oil/LNG cargo, not BDI prints." },
      { id: "commodity", detail: "Commodity news." },
      { id: "ports", detail: "Port and terminal news." },
      { id: "international", detail: "General maritime." },
    ],
    notes: "Daily posts are composite-only; they do not include a Cape/Panamax split.",
  },
  {
    id: "splash",
    name: "Splash 247",
    tool: "press_fetch",
    summary: "Trade press with a dry-cargo desk.",
    provides: "Bulker fixtures, fleet news, and dry-cargo coverage. Pin dry-cargo; other sections cover containers and tankers.",
    params: PRESS_PARAMS,
    categories: [
      { id: "all", detail: "Whole site." },
      { id: "dry-cargo", detail: "Bulker fixtures and fleet." },
      { id: "containers", detail: "Container liner news." },
      { id: "tankers", detail: "Tanker news." },
      { id: "ports", detail: "Ports and logistics." },
    ],
  },
  {
    id: "telegraph",
    name: "Shipping Telegraph",
    tool: "press_fetch",
    summary: "Freight commentary and fixtures.",
    provides: "IC Shipbrokers daily colour, bulker news, and market notes. Qualitative context, not Baltic prints.",
    params: PRESS_PARAMS,
    categories: [
      { id: "all", detail: "Whole site." },
      { id: "freight-news", detail: "IC Shipbrokers commentary and fixtures." },
      { id: "dry-bulk", detail: "Bulker-only items." },
      { id: "shipping-reports", detail: "Market reports." },
      { id: "shipping-news", detail: "General shipping." },
      { id: "commodity", detail: "Commodity news." },
    ],
  },
  {
    id: "gcaptain",
    name: "gCaptain",
    tool: "press_fetch",
    summary: "Operational maritime news.",
    provides: "Mixed coverage including occasional dry-bulk items. No dedicated desk; pass a query to filter.",
    params: PRESS_PARAMS,
    categories: [
      { id: "all", detail: "Whole site." },
      { id: "shipping", detail: "Shipping section." },
      { id: "shipping-news", detail: "Shipping news." },
      { id: "ports", detail: "Ports." },
      { id: "offshore", detail: "Offshore." },
    ],
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
      { name: "live", type: "boolean", detail: "catalog only: merge live commodity list (uses one request)." },
    ],
    notes:
      "Requires OILPRICE_API_TOKEN. BPI and BSI are not in the catalog. Baltic history on this feed starts in 2026; older windows return empty.",
  },
];

export const WEB_TOOLS: SourceSpec[] = [
  {
    id: "press_catalog",
    name: "Press catalog",
    tool: "press_catalog",
    summary: "Lists press sites and category guides.",
    provides: "Site ids, categories, and a short guide for each desk. No parameters.",
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
    provides: "Full text of one URL. Cookie walls are flagged and should not be treated as source content.",
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
      "World Bank commodity prices, grain supply-demand, trade flows, fleet indicators, and historical BDI. Available elsewhere in the system; not bound on this agent.",
  },
];

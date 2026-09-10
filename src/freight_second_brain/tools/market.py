"""OilPriceAPI market feed: Baltic freight indices and related cargo prices.

Free signup (no credit card) at https://www.oilpriceapi.com/auth/signup — 50 req/day
after a 7-day 10k-request trial. Set OILPRICE_API_TOKEN or OILPRICEAPI_KEY.

OilPriceAPI reprints Baltic Exchange assessments. It is not a licensed Baltic
distributor; cite OilPriceAPI, not as official Baltic data.
"""

from __future__ import annotations

import hashlib
import re
import time
from datetime import date, timedelta
from typing import Any

import httpx

from freight_second_brain.config import USER_AGENT, Settings, get_settings

BASE_URL = "https://api.oilpriceapi.com/v1"
SIGNUP_URL = "https://www.oilpriceapi.com/auth/signup"
DOCS_URL = "https://docs.oilpriceapi.com/"
PRICING_URL = "https://www.oilpriceapi.com/pricing"
PROVIDER = "OilPriceAPI"
DISCLAIMER = (
    "OilPriceAPI reprints Baltic Exchange assessments and other market prices. "
    "It is not a licensed Baltic Exchange distributor. Cite OilPriceAPI, not as official Baltic data."
)
PLAN_HISTORY_LIMITS = (
    "History is plan-gated, not a full Baltic archive "
    f"({PRICING_URL}). "
    "Free: last 7 or 30 days only — cannot read 1-year or 5-year data. "
    "Developer $19/mo: 1 year back from today (as of 2026-09-10 that is ~2025-09-10); "
    "cannot read 5-year data. "
    "Starter $49/mo: 5 years back (~2021-09-10). "
    "Professional $99/mo+: full archive where the series exists. "
    "Obey history_available_from on the response; that date is this key's hard floor. "
    "Do not invent prints before that floor."
)
SERIES_COVERAGE = (
    "Series coverage is not the same as plan depth. Live probe 10 Sep 2026 "
    "(professional trial key): BDI daily from 2026-04-10, BCI from 2026-06-08, "
    "iron ore from 2026-04-10. 1-year-ago (2025-09) and 5-year-ago (2021-09) "
    "windows for those Baltic/cargo codes return empty_window — not a plan error. "
    "WTI and Brent do have 1-year and 5-year daily history on this key. "
    "BPI/BSI/BHSI are not in the OilPriceAPI catalog (HTTP 404). "
    "Do not invent 2021 or 2025 Baltic prints from this feed."
)
_ACCESS_TTL_S = 900.0
_ACCESS_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}

MAX_CODES = 12
MAX_ROWS = 500
DEFAULT_LIMIT = 120
DEFAULT_LATEST_ALIASES = ("bdi", "bci")
DEFAULT_HISTORY_ALIASES = ("bdi", "bci")
CONFIRMED_CODES = frozenset(
    {
        "BALTIC_DRY_INDEX",
        "BALTIC_CAPESIZE_INDEX",
        "IRON_ORE_USD",
        "NEWCASTLE_COAL_USD",
        "COAL_USD",
        "CAPP_COAL_USD",
        "COKING_COAL_USD",
        "WTI_USD",
        "BRENT_CRUDE_USD",
        "COPPER_USD",
        "ALUMINUM_USD",
    }
)

# Curated dry-bulk desk series. BDI/BCI confirmed live 10 Sep 2026.
# BPI/BSI/BHSI are not in the authenticated catalog (HTTP 404).
SERIES: dict[str, dict[str, Any]] = {
    "BALTIC_DRY_INDEX": {
        "aliases": ("bdi", "baltic_dry"),
        "name": "Baltic Dry Index",
        "short": "BDI",
        "group": "dry_bulk",
        "unit": "index",
        "live_url": "https://www.oilpriceapi.com/live/baltic-dry-index",
        "confirmed": True,
        "note": (
            "Composite of Capesize, Panamax, and Supramax. London business days. "
            "OilPriceAPI history currently starts 2026-04-10; 2021/2025 windows are empty."
        ),
    },
    "BALTIC_CAPESIZE_INDEX": {
        "aliases": ("bci", "capesize", "baltic_capesize"),
        "name": "Baltic Capesize Index",
        "short": "BCI",
        "group": "dry_bulk",
        "unit": "index",
        "live_url": "https://www.oilpriceapi.com/live/baltic-capesize-index",
        "confirmed": True,
        "note": (
            "Largest BDI constituent. Iron ore and coal long-haul. "
            "OilPriceAPI history currently starts 2026-06-08; 2021/2025 windows are empty."
        ),
    },
    "BALTIC_PANAMAX_INDEX": {
        "aliases": ("bpi", "panamax", "baltic_panamax"),
        "name": "Baltic Panamax Index",
        "short": "BPI",
        "group": "dry_bulk",
        "unit": "index",
        "live_url": "https://www.oilpriceapi.com/live/baltic-panamax-index",
        "confirmed": False,
        "note": "Not in the OilPriceAPI catalog (HTTP 404 on 10 Sep 2026). Do not invent a BPI print.",
    },
    "BALTIC_SUPRAMAX_INDEX": {
        "aliases": ("bsi", "supramax", "baltic_supramax"),
        "name": "Baltic Supramax Index",
        "short": "BSI",
        "group": "dry_bulk",
        "unit": "index",
        "live_url": "https://www.oilpriceapi.com/live/baltic-supramax-index",
        "confirmed": False,
        "note": "Not in the OilPriceAPI catalog (HTTP 404 on 10 Sep 2026). Do not invent a BSI print.",
    },
    "BALTIC_HANDYSIZE_INDEX": {
        "aliases": ("bhsi", "bhi", "handysize", "baltic_handysize"),
        "name": "Baltic Handysize Index",
        "short": "BHSI",
        "group": "dry_bulk",
        "unit": "index",
        "live_url": "https://www.oilpriceapi.com/live/baltic-handysize-index",
        "confirmed": False,
        "note": "Not in the BDI composite. Not in the OilPriceAPI catalog (HTTP 404 on 10 Sep 2026).",
    },
    "IRON_ORE_USD": {
        "aliases": ("iron_ore", "fe62", "iron"),
        "name": "Iron ore 62% Fe CFR China",
        "short": "Fe62",
        "group": "cargo",
        "unit": "tonne",
        "live_url": "https://www.oilpriceapi.com/live/iron-ore-price",
        "confirmed": True,
        "note": "Cape cargo. Category: metal. OilPriceAPI history currently starts 2026-04-10.",
    },
    "NEWCASTLE_COAL_USD": {
        "aliases": ("coal", "newcastle", "newcastle_coal"),
        "name": "Newcastle thermal coal",
        "short": "NEWC",
        "group": "cargo",
        "unit": "tonne",
        "live_url": "https://www.oilpriceapi.com/live/coal-price",
        "confirmed": True,
        "note": "Docs also list COAL_USD as Newcastle thermal coal.",
    },
    "COAL_USD": {
        "aliases": ("coal_usd",),
        "name": "Thermal coal (Newcastle)",
        "short": "COAL",
        "group": "cargo",
        "unit": "tonne",
        "live_url": "https://www.oilpriceapi.com/live/coal-price",
        "confirmed": True,
        "note": "Docs table alias for Newcastle thermal coal.",
    },
    "COKING_COAL_USD": {
        "aliases": ("coking_coal", "coking"),
        "name": "Coking coal",
        "short": "HCC",
        "group": "cargo",
        "unit": "tonne",
        "live_url": "https://www.oilpriceapi.com/live/coal-price",
        "confirmed": True,
    },
    "CAPP_COAL_USD": {
        "aliases": ("capp_coal", "capp"),
        "name": "Central Appalachian coal",
        "short": "CAPP",
        "group": "cargo",
        "unit": "tonne",
        "live_url": "https://www.oilpriceapi.com/live/capp-coal-price",
        "confirmed": True,
        "note": "US regional overlay, not seaborne Newcastle.",
    },
    "WTI_USD": {
        "aliases": ("wti",),
        "name": "WTI crude oil",
        "short": "WTI",
        "group": "energy",
        "unit": "barrel",
        "live_url": "https://www.oilpriceapi.com/live/wti-price",
        "confirmed": True,
    },
    "BRENT_CRUDE_USD": {
        "aliases": ("brent",),
        "name": "Brent crude oil",
        "short": "Brent",
        "group": "energy",
        "unit": "barrel",
        "live_url": "https://www.oilpriceapi.com/live/real-time-oil-prices",
        "confirmed": True,
    },
    "COPPER_USD": {
        "aliases": ("copper",),
        "name": "Copper",
        "short": "Cu",
        "group": "metal",
        "unit": "lb",
        "live_url": "https://www.oilpriceapi.com/live/copper-price",
        "confirmed": True,
        "note": "Handy/Supramax concentrate overlay.",
    },
    "ALUMINUM_USD": {
        "aliases": ("aluminum", "aluminium"),
        "name": "Aluminum",
        "short": "Al",
        "group": "metal",
        "unit": "lb",
        "live_url": "https://www.oilpriceapi.com/live/aluminum-price",
        "confirmed": True,
    },
    "WHEAT_USD": {
        "aliases": ("wheat",),
        "name": "Wheat",
        "short": "Wheat",
        "group": "grain",
        "unit": "unknown",
        "live_url": "https://www.oilpriceapi.com/commodities",
        "confirmed": False,
        "note": "Grain overlay. Code inferred; confirm with action=catalog live=true.",
    },
    "CORN_USD": {
        "aliases": ("corn",),
        "name": "Corn",
        "short": "Corn",
        "group": "grain",
        "unit": "unknown",
        "live_url": "https://www.oilpriceapi.com/commodities",
        "confirmed": False,
        "note": "Grain overlay. Code inferred.",
    },
    "SOYBEAN_USD": {
        "aliases": ("soy", "soybean", "soybeans"),
        "name": "Soybeans",
        "short": "Soy",
        "group": "grain",
        "unit": "unknown",
        "live_url": "https://www.oilpriceapi.com/commodities",
        "confirmed": False,
        "note": "Grain overlay. Code inferred.",
    },
    "DREWRY_WORLD_CONTAINER_INDEX": {
        "aliases": ("wci", "drewry"),
        "name": "Drewry World Container Index",
        "short": "WCI",
        "group": "container",
        "unit": "index",
        "live_url": "https://www.oilpriceapi.com/live/drewry-world-container-index",
        "confirmed": False,
        "note": "Container overlay. Out of dry-bulk desk unless the question needs it.",
    },
    "SHANGHAI_CONTAINERIZED_FREIGHT_INDEX": {
        "aliases": ("scfi",),
        "name": "Shanghai Containerized Freight Index",
        "short": "SCFI",
        "group": "container",
        "unit": "index",
        "live_url": "https://www.oilpriceapi.com/prices/freight-indices",
        "confirmed": False,
        "note": "Container overlay. Out of dry-bulk desk unless the question needs it.",
    },
    "VLSFO_SGSIN_USD": {
        "aliases": ("vlsfo", "bunker", "singapore_vlsfo"),
        "name": "Singapore VLSFO bunker",
        "short": "VLSFO",
        "group": "bunker",
        "unit": "tonne",
        "live_url": "https://docs.oilpriceapi.com/solutions/shipping",
        "confirmed": True,
        "note": "Bunkers, not a freight index.",
    },
}

_ALIAS_TO_CODE: dict[str, str] = {}
for _code, _meta in SERIES.items():
    _ALIAS_TO_CODE.setdefault(_code.lower(), _code)
    _ALIAS_TO_CODE.setdefault(str(_meta["short"]).lower(), _code)
    for _alias in _meta.get("aliases") or ():
        _ALIAS_TO_CODE.setdefault(str(_alias).lower(), _code)

_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,}$")
_MISSING_TOKEN = (
    "Set OILPRICE_API_TOKEN or OILPRICEAPI_KEY. Free signup (no credit card, "
    f"50 requests/day after a 7-day trial): {SIGNUP_URL}"
)


def _normalize_token(raw: str) -> str:
    return re.sub(r"[-\s]+", "_", (raw or "").strip()).lower()


def resolve_code(token: str) -> str:
    """Map an alias or OilPriceAPI code to a canonical code."""
    text = (token or "").strip()
    if not text:
        raise ValueError("empty series code")
    mapped = _ALIAS_TO_CODE.get(_normalize_token(text))
    if mapped:
        return mapped
    upper = re.sub(r"[-\s]+", "_", text).upper()
    if upper in SERIES:
        return upper
    if _CODE_RE.fullmatch(upper):
        return upper
    known = ", ".join(DEFAULT_LATEST_ALIASES) + ", iron_ore, coal, wti, brent, copper"
    raise ValueError(f"unknown series {token!r}. Known aliases: {known}. Or pass an OilPriceAPI code.")


def resolve_codes(codes: str | None, *, default: tuple[str, ...] | None = None) -> list[str]:
    raw = (codes or "").strip()
    tokens = [part.strip() for part in raw.split(",")] if raw else list(default or ())
    tokens = [part for part in tokens if part]
    if not tokens:
        raise ValueError("codes is required (comma-separated aliases or OilPriceAPI codes)")
    resolved: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        code = resolve_code(token)
        if code in seen:
            continue
        seen.add(code)
        resolved.append(code)
    if len(resolved) > MAX_CODES:
        raise ValueError(f"at most {MAX_CODES} codes per call (free plan is 50 requests/day)")
    return resolved


def _token(settings: Settings) -> str:
    return (settings.oilprice_api_token or "").strip()


def _require_token(settings: Settings) -> str:
    token = _token(settings)
    if not token:
        raise RuntimeError(_MISSING_TOKEN)
    return token


def _clip_int(value: int | None, default: int, lo: int, hi: int) -> int:
    if value is None:
        return default
    return max(lo, min(hi, int(value)))


def _series_meta(code: str) -> dict[str, Any]:
    return SERIES.get(code) or {
        "aliases": (),
        "name": code,
        "short": code,
        "group": "other",
        "unit": None,
        "live_url": f"{DOCS_URL}",
        "confirmed": False,
        "note": "Not in the curated dry-bulk catalog; passed through to OilPriceAPI.",
    }


def _catalog_entries(*, extra: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    rows = []
    for code, meta in SERIES.items():
        rows.append(
            {
                "code": code,
                "aliases": list(meta.get("aliases") or ()),
                "name": meta["name"],
                "short": meta["short"],
                "group": meta["group"],
                "unit": meta.get("unit"),
                "confirmed": bool(meta.get("confirmed")),
                "live_url": meta.get("live_url"),
                "note": meta.get("note"),
            }
        )
    seen = {row["code"] for row in rows}
    for item in extra or []:
        code = str(item.get("code") or "").upper()
        if not code or code in seen:
            continue
        seen.add(code)
        rows.append(item)
    return rows


def _parse_iso_date(value: str | None) -> date | None:
    text = (value or "").strip()
    if len(text) < 10:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def apply_history_floor(
    *,
    start: str | None,
    end: str | None,
    past: str | None,
    history_available_from: str | None,
    today: date | None = None,
) -> dict[str, Any]:
    """Clip a requested window to this key's OilPriceAPI history floor."""
    today = today or date.today()
    floor = _parse_iso_date(history_available_from)
    start_d = _parse_iso_date(start)
    past_key = _normalize_token(past or "")
    days_open = (today - floor).days if floor else None
    can_read_1y = floor is None or (days_open is not None and days_open >= 360)
    can_read_5y = floor is None or (days_open is not None and days_open >= 1800)
    warning: str | None = None
    clipped = False
    out_start, out_end, out_past = start, end, past

    if floor and start_d and start_d < floor:
        out_start = floor.isoformat()
        clipped = True
        span_days = (today - start_d).days
        if span_days >= 1800 and not can_read_5y:
            warning = (
                f"5-year history is outside this key's floor ({floor.isoformat()}). "
                "Starter ($49/mo) includes 5 years; Developer is 1 year; Free is 30 days. "
                f"{PLAN_HISTORY_LIMITS}"
            )
        elif span_days >= 360 and not can_read_1y:
            warning = (
                f"1-year history is outside this key's floor ({floor.isoformat()}). "
                "Free plan is last 7 or 30 days only. "
                f"{PLAN_HISTORY_LIMITS}"
            )
        else:
            warning = (
                f"Requested start {start_d.isoformat()} is before this key's history floor "
                f"{floor.isoformat()}; window clipped. {PLAN_HISTORY_LIMITS}"
            )

    if not (out_start or out_end) and past_key in {"1y", "365d", "year", "past_year", "12m"} and not can_read_1y:
        clipped = True
        out_past = None
        out_start = (floor or (today - timedelta(days=30))).isoformat()
        out_end = today.isoformat()
        warning = (
            f"past=1y is not available on this key (floor {floor.isoformat() if floor else 'unknown'}). "
            "Free: 30 days. Developer: 1 year. "
            f"{PLAN_HISTORY_LIMITS}"
        )

    return {
        "start": out_start,
        "end": out_end,
        "past": out_past,
        "clipped": clipped,
        "can_read_1y": can_read_1y,
        "can_read_5y": can_read_5y,
        "history_available_from": floor.isoformat() if floor else history_available_from,
        "warning": warning,
        "days_open": days_open,
    }


def _account_access(token: str, code: str = "BALTIC_DRY_INDEX") -> dict[str, Any]:
    cache_key = hashlib.sha256(f"{token}:{code}".encode()).hexdigest()[:16]
    cached = _ACCESS_CACHE.get(cache_key)
    now = time.monotonic()
    if cached and now - cached[0] < _ACCESS_TTL_S:
        return dict(cached[1])
    status, payload, _headers = _request(f"/commodities/{code}", {}, token)
    access: dict[str, Any] = {
        "code": code,
        "http_status": status,
        "history_available_from": None,
        "access_note": None,
        "plan_limits": PLAN_HISTORY_LIMITS,
    }
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    if status == 200 and isinstance(data, dict):
        yours = data.get("your_access") if isinstance(data.get("your_access"), dict) else {}
        floor = yours.get("history_available_from")
        access["history_available_from"] = str(floor)[:10] if floor else None
        access["access_note"] = yours.get("note")
        access["has_data"] = data.get("has_data")
        access["name"] = data.get("name")
        if floor is None and yours:
            access["access_note"] = yours.get("note") or "Plan includes the full available archive for this series."
    else:
        access["error"] = _api_error_message(status, payload, path=f"/commodities/{code}")
    _ACCESS_CACHE[cache_key] = (now, dict(access))
    return access


def _history_route(
    *,
    start: str | None,
    end: str | None,
    past: str | None,
) -> tuple[str, dict[str, str]]:
    """Pick an OilPriceAPI path. Free plan: past_week / past_month. Custom ranges are paid."""
    start = (start or "").strip() or None
    end = (end or "").strip() or None
    past_key = _normalize_token(past or "")
    if start or end:
        params = {"interval": "daily", "per_page": "500"}
        if start:
            params["start_date"] = start
        if end:
            params["end_date"] = end
        return "/prices/historical", params
    week = {"7d", "1w", "week", "past_week", "7"}
    month = {"", "30d", "1m", "month", "past_month", "30"}
    year = {"1y", "365d", "year", "past_year", "12m"}
    if past_key in week:
        return "/prices/past_week", {"interval": "1d"}
    if past_key in year:
        return "/prices/past_year", {"interval": "1d"}
    if past_key in {"3m", "6m"}:
        return "/prices/historical", {"past": past_key, "interval": "daily", "per_page": "500"}
    if past_key in month:
        return "/prices/past_month", {"interval": "1d"}
    raise ValueError("past must be 7d, 30d, 3m, 6m, or 1y (or pass start/end as YYYY-MM-DD)")


def _row_date(item: dict[str, Any]) -> str | None:
    for key in ("source_date", "as_of", "observed_at", "created_at", "updated_at"):
        value = item.get(key)
        if isinstance(value, str) and len(value) >= 10:
            return value[:10]
    return None


def _as_of(item: dict[str, Any]) -> str | None:
    for key in ("as_of", "observed_at", "source_date", "created_at", "updated_at"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _extract_price_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    if isinstance(data, dict):
        prices = data.get("prices")
        if isinstance(prices, list):
            return [item for item in prices if isinstance(item, dict)]
        if data.get("code") or data.get("price") is not None:
            return [data]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def _normalize_row(item: dict[str, Any]) -> dict[str, Any] | None:
    code = str(item.get("code") or "").upper()
    value = item.get("price")
    if not code or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    meta = _series_meta(code)
    date = _row_date(item)
    return {
        "code": code,
        "alias": meta.get("short") or code,
        "name": item.get("name") or meta.get("name") or code,
        "date": date,
        "value": number,
        "formatted": item.get("formatted"),
        "unit": item.get("unit") or meta.get("unit"),
        "currency": item.get("currency"),
        "as_of": _as_of(item),
        "stale": item.get("stale") if isinstance(item.get("stale"), bool) else None,
        "synthetic": item.get("synthetic") if isinstance(item.get("synthetic"), bool) else None,
        "source": item.get("source") or PROVIDER,
        "cite_url": meta.get("live_url") or f"https://www.oilpriceapi.com/live/{code.lower().replace('_', '-')}",
        "group": meta.get("group"),
    }


def _trim_rows(rows: list[dict[str, Any]], limit: int) -> tuple[list[dict[str, Any]], bool]:
    rows = [row for row in rows if row]
    rows.sort(key=lambda row: (str(row.get("date") or ""), str(row.get("code") or "")))
    if len(rows) <= limit:
        return rows, False
    return rows[-limit:], True


def _latest_by_code(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        code = str(row.get("code") or "")
        if not code:
            continue
        prior = latest.get(code)
        if prior is None or str(row.get("date") or "") >= str(prior.get("date") or ""):
            latest[code] = row
    return latest


def _invalid_code(status: int, payload: dict[str, Any]) -> bool:
    if status != 400:
        return False
    blob = str(payload).lower()
    return "invalid_code" in blob or "unknown commodity" in blob


def _api_error_message(status: int, payload: dict[str, Any], *, path: str) -> str:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    detail = (
        payload.get("error")
        or payload.get("message")
        or (data.get("error") if isinstance(data, dict) else None)
        or (data.get("message") if isinstance(data, dict) else None)
        or payload.get("status")
    )
    hint = ""
    if status in {401, 403}:
        hint = f" Check OILPRICE_API_TOKEN. Signup: {SIGNUP_URL}."
    elif path.startswith("/prices/historical") or path.startswith("/prices/past_year"):
        hint = (
            f" {PLAN_HISTORY_LIMITS}"
        )
    elif status == 429:
        hint = " Free plan is 50 requests/day; batch codes in one call."
    return f"OilPriceAPI HTTP {status} on {path}: {detail}.{hint}".strip()


def _request(
    path: str,
    params: dict[str, str],
    token: str,
    *,
    timeout: float = 30.0,
) -> tuple[int, dict[str, Any], dict[str, str]]:
    url = f"{BASE_URL}{path}"
    headers = {
        "Authorization": f"Token {token}",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    query = {key: value for key, value in params.items() if value not in (None, "")}
    with httpx.Client(follow_redirects=True, timeout=timeout) as client:
        response = client.get(url, headers=headers, params=query)
        try:
            payload = response.json()
        except ValueError:
            payload = {"raw": (response.text or "")[:800]}
        if not isinstance(payload, dict):
            payload = {"data": payload}
        hdrs = {key.lower(): value for key, value in response.headers.items()}
        return response.status_code, payload, hdrs


def _get_prices(path: str, codes: list[str], token: str, extra: dict[str, str] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    params = {"by_code": ",".join(codes), **(extra or {})}
    status, payload, headers = _request(path, params, token)
    meta = {
        "http_status": status,
        "path": path,
        "truncated": False,
        "skipped": [],
        "api_status": payload.get("status"),
    }
    pages = headers.get("x-total-pages")
    if pages and pages.isdigit() and int(pages) > 1:
        meta["truncated"] = True
        meta["total_pages"] = int(pages)

    if status == 200 and payload.get("status") in {None, "success"}:
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        avail = data.get("availability") if isinstance(data, dict) else None
        if isinstance(avail, dict):
            meta["availability"] = avail
            missing = [item for item in (avail.get("missing") or []) if isinstance(item, dict)]
            meta["missing"] = missing
            if missing:
                meta["empty_window"] = "; ".join(
                    str(item.get("message") or item.get("reason") or "")
                    for item in missing
                ).strip() or None
        return _extract_price_items(payload), meta

    if _invalid_code(status, payload):
        confirmed = [code for code in codes if code in CONFIRMED_CODES or _series_meta(code).get("confirmed")]
        skipped = [code for code in codes if code not in confirmed]
        if confirmed and skipped:
            items, retry_meta = _get_prices(path, confirmed, token, extra)
            retry_meta["skipped"] = skipped
            retry_meta["note"] = (
                "OilPriceAPI rejected at least one unconfirmed code "
                f"({', '.join(skipped)}). Returned confirmed series only."
            )
            return items, retry_meta
        raise RuntimeError(_api_error_message(status, payload, path=path))

    if status >= 400:
        raise RuntimeError(_api_error_message(status, payload, path=path))
    return _extract_price_items(payload), meta


def _live_catalog(token: str) -> list[dict[str, Any]]:
    status, payload, _headers = _request("/commodities", {}, token)
    if status != 200:
        raise RuntimeError(_api_error_message(status, payload, path="/commodities"))
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    commodities = data.get("commodities") if isinstance(data, dict) else None
    if not isinstance(commodities, list):
        return []
    needles = (
        "baltic",
        "iron ore",
        "coal",
        "copper",
        "wheat",
        "corn",
        "soy",
        "freight",
        "drewry",
        "container",
        "coking",
        "newcastle",
        "bauxite",
        "aluminum",
        "bunker",
        "vlsfo",
    )
    extra: list[dict[str, Any]] = []
    for item in commodities:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").upper()
        name = str(item.get("name") or "")
        category = str(item.get("category") or "")
        blob = f"{code} {name} {category}".lower()
        if not any(needle in blob for needle in needles):
            continue
        extra.append(
            {
                "code": code,
                "aliases": [],
                "name": name or code,
                "short": code,
                "group": category or "other",
                "unit": item.get("unit"),
                "confirmed": True,
                "live_url": None,
                "note": "From authenticated OilPriceAPI catalog.",
                "in_live_catalog": True,
            }
        )
    return extra


def _envelope(
    *,
    action: str,
    rows: list[dict[str, Any]] | None = None,
    series: list[dict[str, Any]] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": True,
        "provider": PROVIDER,
        "action": action,
        "disclaimer": DISCLAIMER,
        "signup_url": SIGNUP_URL,
        "docs_url": DOCS_URL,
    }
    if series is not None:
        payload["series"] = series
        payload["aliases"] = {alias: code for alias, code in sorted(_ALIAS_TO_CODE.items()) if alias != code.lower()}
        payload["default_latest"] = list(DEFAULT_LATEST_ALIASES)
        payload["history_notes"] = f"{PLAN_HISTORY_LIMITS} {SERIES_COVERAGE}"
        payload["plan_limits"] = PLAN_HISTORY_LIMITS
        payload["series_coverage"] = SERIES_COVERAGE
    if rows is not None:
        payload["rows"] = rows
        payload["row_count"] = len(rows)
        payload["latest"] = _latest_by_code(rows)
    if extra:
        payload.update(extra)
    return payload


def market_feed(
    action: str | None = "latest",
    codes: str | None = None,
    start: str | None = None,
    end: str | None = None,
    past: str | None = None,
    limit: int | None = None,
    live: bool | None = False,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Fetch Baltic and cargo prices from OilPriceAPI.

    action=catalog needs no key (curated list). latest/history need OILPRICE_API_TOKEN.
    """
    settings = settings or get_settings()
    kind = (action or "latest").strip().lower()
    if kind not in {"catalog", "latest", "history"}:
        raise ValueError("action must be catalog, latest, or history")
    row_limit = _clip_int(limit, DEFAULT_LIMIT, 1, MAX_ROWS)

    if kind == "catalog":
        extra = None
        if live:
            extra = _live_catalog(_require_token(settings))
        return _envelope(action="catalog", series=_catalog_entries(extra=extra))

    token = _require_token(settings)
    if kind == "latest":
        resolved = resolve_codes(codes, default=DEFAULT_LATEST_ALIASES)
        items, meta = _get_prices("/prices/latest", resolved, token)
        rows, trimmed = _trim_rows([row for item in items if (row := _normalize_row(item))], row_limit)
        return _envelope(
            action="latest",
            rows=rows,
            extra={
                "codes": resolved,
                "skipped": meta.get("skipped") or [],
                "truncated": bool(meta.get("truncated") or trimmed),
                "note": meta.get("note"),
                "path": meta.get("path"),
                "plan_limits": PLAN_HISTORY_LIMITS,
            },
        )

    access = _account_access(token)
    window = apply_history_floor(
        start=start,
        end=end,
        past=past,
        history_available_from=access.get("history_available_from"),
    )
    resolved = resolve_codes(codes, default=DEFAULT_HISTORY_ALIASES)
    path, params = _history_route(start=window["start"], end=window["end"], past=window["past"])
    items, meta = _get_prices(path, resolved, token, params)
    rows, trimmed = _trim_rows([row for item in items if (row := _normalize_row(item))], row_limit)
    dates = [str(row.get("date")) for row in rows if row.get("date")]
    return _envelope(
        action="history",
        rows=rows,
        extra={
            "codes": resolved,
            "skipped": meta.get("skipped") or [],
            "truncated": bool(meta.get("truncated") or trimmed),
            "note": meta.get("note") or window.get("warning") or meta.get("empty_window"),
            "warning": window.get("warning") or meta.get("empty_window"),
            "empty_window": meta.get("empty_window"),
            "missing": meta.get("missing") or [],
            "series_coverage": SERIES_COVERAGE,
            "path": path,
            "past": window["past"] if not (window["start"] or window["end"]) else None,
            "start": window["start"],
            "end": window["end"],
            "requested_start": start or None,
            "requested_end": end or None,
            "clipped": window["clipped"],
            "history_available_from": window["history_available_from"],
            "can_read_1y": window["can_read_1y"],
            "can_read_5y": window["can_read_5y"],
            "date_min": min(dates) if dates else None,
            "date_max": max(dates) if dates else None,
            "plan_limits": PLAN_HISTORY_LIMITS,
            "access_note": access.get("access_note"),
        },
    )

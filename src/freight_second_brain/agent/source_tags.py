"""Web-source classification topology for the research desk.

Aligned with the dry-bulk research skill's audit (primary vs reprint, horizon, access).

Each source gets one value per dimension. Tag ids are `{dimension}:{value}`.
Polarity is the implication for dry-bulk *rates* (or the named subject), not a
word list. Leave `unknown` unless the text supports it.
"""

from __future__ import annotations

import re
from datetime import date
from email.utils import parsedate_to_datetime
from typing import Any

from freight_second_brain.warehouse.schemas import ClaimType, FreshnessClass, Polarity

# User-facing aliases: fact→observation, analysis→explanation, prediction→forecast
DIMENSIONS: dict[str, tuple[tuple[str, str], ...]] = {
    "provenance": (
        ("primary", "Primary"),
        ("secondary", "Secondary"),
        ("tertiary", "Tertiary"),
        ("overlay", "Overlay"),
    ),
    "hierarchy": (
        ("primary", "Lead"),
        ("duplicate", "Reprint"),
    ),
    "claim_type": (
        ("observation", "Fact"),
        ("explanation", "Analysis"),
        ("forecast", "Outlook"),
        ("scenario", "Scenario"),
        ("risk", "Risk"),
        ("methodology", "Methodology"),
    ),
    "polarity": (
        ("bullish", "Bullish"),
        ("bearish", "Bearish"),
        ("mixed", "Mixed"),
        ("neutral", "Neutral"),
        ("unknown", "Unlabeled"),
    ),
    "freshness": (
        ("current", "Current"),
        ("recent", "Recent"),
        ("aging", "Aging"),
        ("historical_vintage", "Historical"),
        ("post_cutoff_outcome", "Post-cutoff"),
    ),
    "medium": (
        ("website", "Web"),
        ("pdf", "PDF"),
        ("rss", "News feed"),
        ("warehouse", "Warehouse"),
    ),
    "access": (
        ("full_text", "Full text"),
        ("public_summary", "Summary"),
        ("cookie_wall", "Cookie wall"),
        ("paywall", "Paywall"),
    ),
    "channel": (
        ("freight_index", "Index"),
        ("news", "News"),
        ("research", "Research"),
        ("methodology", "Methodology"),
        ("broker", "Broker"),
        ("commodity_price", "Cargo"),
    ),
}

FILTER_DIMENSIONS = ("provenance", "claim_type", "polarity", "freshness", "medium", "hierarchy")
AGENT_OVERRIDE_FIELDS = ("claim_type", "polarity", "freshness", "access", "provenance")

_LABEL = {
    dim: {value: label for value, label in pairs} for dim, pairs in DIMENSIONS.items()
}
_ALLOWED = {dim: {value for value, _label in pairs} for dim, pairs in DIMENSIONS.items()}

_DAILY_PRINT = re.compile(
    r"baltic dry index.+(climb|fell|fall|rose|up|down|reach)|bdi\b.+(climb|fell|rose)",
    re.I,
)
_WEEKLY = re.compile(r"\b(week(?:ly)?|week\s*\d{1,2}|recap)\b", re.I)
_FORECAST = re.compile(r"\b(outlook|forecast|smoo|sro|scenario|1–8|1-8 quarter|expected to)\b", re.I)
_SCENARIO = re.compile(r"\b(scenario|if hormuz|closed vs open|sensitivity)\b", re.I)
_METHOD = re.compile(r"\b(methodology|definition|how the bdi|vessel assumptions)\b", re.I)
_ANALYSIS = re.compile(r"\b(why|driven|because|analysis|miners?|ballast|tonne-?miles?)\b", re.I)
_BULLISH = re.compile(r"\b(climb(?:ed|s)?|rose|up \d|surge|rally|higher|strength)\b", re.I)
_BEARISH = re.compile(r"\b(fell|fall|down \d|slump|pressure|weaker|decline|decreased)\b", re.I)
_PAYWALL = re.compile(r"sin\.clarksons|ssy navigator|lloyd'?s list", re.I)
_COOKIE = re.compile(r"bimco\.org|balticexchange\.com", re.I)
_INDEX_HOSTS = {"balticexchange.com", "tradingeconomics.com"}
_RESEARCH_HOSTS = {"unctad.org", "skibskredit.dk", "bimco.org"}
_BROKER = re.compile(r"xclusiv|star asia|geneva dry|allied|breakwave|\.pdf$", re.I)
_CARGO_HOSTS = {"bigmint.com", "mysteel.net"}


def tag_id(dimension: str, value: str) -> str:
    return f"{dimension}:{value}"


def tag_record(dimension: str, value: str) -> dict[str, str]:
    return {
        "dimension": dimension,
        "id": tag_id(dimension, value),
        "value": value,
        "label": _LABEL.get(dimension, {}).get(value, value.replace("_", " ").title()),
    }


def parse_published_date(text: str | None) -> date | None:
    raw = (text or "").strip()
    if not raw:
        return None
    iso = re.search(r"(20\d{2}-\d{2}-\d{2})", raw)
    if iso:
        return date.fromisoformat(iso.group(1))
    try:
        parsed = parsedate_to_datetime(raw)
        if parsed.tzinfo is None:
            return parsed.date()
        return parsed.date()
    except (TypeError, ValueError, IndexError):
        return None


def freshness_for(published: str | None, *, as_of: date | None = None, url: str = "", title: str = "") -> str:
    as_of = as_of or date.today()
    blob = f"{title} {url} {published or ''}".lower()
    if "unctad" in blob or "rmt20" in blob or "review of maritime" in blob:
        observed = parse_published_date(published)
        if observed is None or (as_of - observed).days > 90:
            return FreshnessClass.HISTORICAL_VINTAGE.value
    observed = parse_published_date(published)
    if observed is None:
        if re.search(r"202[0-5]", published or "") and str(as_of.year) not in (published or ""):
            return FreshnessClass.HISTORICAL_VINTAGE.value
        return FreshnessClass.RECENT.value
    days = (as_of - observed).days
    if days < 0:
        days = 0
    if days <= 7:
        return FreshnessClass.CURRENT.value
    if days <= 30:
        return FreshnessClass.RECENT.value
    if days <= 90:
        return FreshnessClass.AGING.value
    return FreshnessClass.HISTORICAL_VINTAGE.value


def _claim_type(title: str, snippet: str, print_value: int | None) -> str:
    blob = f"{title} {snippet}"
    if _METHOD.search(blob):
        return ClaimType.METHODOLOGY.value
    if _SCENARIO.search(blob):
        return ClaimType.SCENARIO.value
    if _FORECAST.search(blob):
        return ClaimType.FORECAST.value
    if print_value is not None and _DAILY_PRINT.search(title):
        return ClaimType.OBSERVATION.value
    if _WEEKLY.search(title) or _ANALYSIS.search(blob):
        return ClaimType.EXPLANATION.value
    if print_value is not None:
        return ClaimType.OBSERVATION.value
    return ClaimType.EXPLANATION.value


def _polarity(title: str, snippet: str, print_value: int | None) -> str:
    blob = f"{title} {snippet}"
    if not (_DAILY_PRINT.search(title) or print_value is not None):
        return Polarity.UNKNOWN.value
    up = bool(_BULLISH.search(blob))
    down = bool(_BEARISH.search(blob))
    if up and down:
        return Polarity.MIXED.value
    if up:
        return Polarity.BULLISH.value
    if down:
        return Polarity.BEARISH.value
    return Polarity.UNKNOWN.value


def _medium(url: str, tool: str | None) -> str:
    if (tool or "") == "sql" or (tool or "") == "schema":
        return "warehouse"
    if (tool or "") == "rss_feed":
        return "rss"
    if url.lower().endswith(".pdf") or "/pdf" in url.lower():
        return "pdf"
    return "website"


def _access(url: str, cookie_wall: bool | None) -> str:
    if cookie_wall:
        return "cookie_wall"
    if _PAYWALL.search(url):
        return "paywall"
    if _COOKIE.search(url) and not url.lower().endswith(".pdf"):
        return "cookie_wall"
    if "jina" in (url or ""):
        return "full_text"
    return "public_summary"


def _channel(host: str, url: str, title: str) -> str:
    if host in _INDEX_HOSTS:
        return "freight_index"
    if host in _RESEARCH_HOSTS:
        return "research"
    if host in _CARGO_HOSTS:
        return "commodity_price"
    if _BROKER.search(f"{url} {title}"):
        return "broker"
    if "balticexchange" in host:
        return "methodology"
    return "news"


def _provenance(role: str | None) -> str:
    if role == "overlay":
        return "overlay"
    if role == "tertiary":
        return "tertiary"
    if role == "primary":
        return "primary"
    if role in {"reprint", "secondary"}:
        return "secondary"
    return "secondary"


def _hierarchy(hierarchy: str | None) -> str:
    if hierarchy == "duplicate":
        return "duplicate"
    return "primary"


def build_tags(values: dict[str, str]) -> tuple[list[dict[str, str]], list[str]]:
    tags: list[dict[str, str]] = []
    ids: list[str] = []
    for dim in DIMENSIONS:
        value = values.get(dim)
        if not value or value not in _ALLOWED[dim]:
            continue
        if dim == "polarity" and value == "unknown":
            continue
        record = tag_record(dim, value)
        tags.append(record)
        ids.append(record["id"])
    return tags, ids


def classify_source(
    *,
    title: str = "",
    url: str = "",
    snippet: str = "",
    published: str | None = None,
    host: str = "",
    role: str | None = None,
    hierarchy: str | None = None,
    print_value: int | None = None,
    tool: str | None = None,
    cookie_wall: bool | None = None,
    as_of: date | None = None,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return classification fields plus `tags` / `tag_ids` for UI filters."""
    values = {
        "provenance": _provenance(role),
        "hierarchy": _hierarchy(hierarchy),
        "claim_type": _claim_type(title, snippet, print_value),
        "polarity": _polarity(title, snippet, print_value),
        "freshness": freshness_for(published, as_of=as_of, url=url, title=title),
        "medium": _medium(url, tool),
        "access": _access(url, cookie_wall),
        "channel": _channel(host, url, title),
    }
    for key, raw in (overrides or {}).items():
        if key in _ALLOWED and str(raw) in _ALLOWED[key]:
            values[key] = str(raw)
    tags, tag_ids = build_tags(values)
    return {**values, "tags": tags, "tag_ids": tag_ids}


def apply_classification(card: dict[str, Any], *, as_of: date | None = None) -> dict[str, Any]:
    payload = dict(card.get("payload") or {})
    overrides = {}
    if payload.get("classified_by") == "agent":
        overrides = {key: payload.get(key) for key in AGENT_OVERRIDE_FIELDS if payload.get(key)}
    classified = classify_source(
        title=str(card.get("title") or ""),
        url=str(payload.get("url") or ""),
        snippet=str(payload.get("snippet") or ""),
        published=str(payload.get("published") or "") or None,
        host=str(payload.get("pretty_host") or ""),
        role=str(payload.get("role") or "") or None,
        hierarchy=str(payload.get("hierarchy") or "") or None,
        print_value=payload.get("print") if isinstance(payload.get("print"), int) else None,
        tool=str((card.get("provenance") or {}).get("tool") or payload.get("tool") or "") or None,
        cookie_wall=bool(payload.get("cookie_wall")),
        as_of=as_of,
        overrides=overrides,
    )
    payload.update(classified)
    if overrides:
        payload["classified_by"] = "agent"
    return {**card, "payload": payload}


def coerce_override(field: str, value: Any) -> str | None:
    text = str(value or "").strip().lower()
    aliases = {
        "fact": "observation",
        "analysis": "explanation",
        "prediction": "forecast",
        "outlook": "forecast",
        "historical": "historical_vintage",
        "reprint": "duplicate",
        "web": "website",
        "html": "website",
    }
    text = aliases.get(text, text)
    if field in _ALLOWED and text in _ALLOWED[field]:
        return text
    return None

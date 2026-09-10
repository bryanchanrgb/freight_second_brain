"""Publisher-native fetch for maritime press sites (REST/RSS only — no login bypass)."""

from __future__ import annotations

import html
import json
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlencode

from freight_second_brain.config import Settings, get_settings
from freight_second_brain.tools.web import _plain, http_get

SITE_IDS = (
    "hellenic",
    "splash",
    "telegraph",
    "gcaptain",
)

PRESS_SITES: dict[str, dict[str, Any]] = {
    "hellenic": {
        "id": "hellenic",
        "name": "Hellenic Shipping News",
        "home": "https://www.hellenicshippingnews.com/",
        "backend": "wp_rest",
        "wp_base": "https://www.hellenicshippingnews.com",
        "default_category": "all",
        "categories": {
            "all": None,
            "dry-bulk": 122,
            "weekly-tce": 162,
            "weekly-brokers": 123,
            "iron-ore": 119,
            "freight-news": 113,
            "commodity": 101,
            "ports": 112,
            "international": 27,
        },
        "category_guide": {
            "all": "Entire site. High volume: tanker/geopolitics, macro, ports, oil, plus dry bulk.",
            "dry-bulk": "Dry Bulk Market desk. Daily BDI composite headlines and Cape/Panamax color.",
            "weekly-tce": "Weekly Dry Time Charter Estimates sheet.",
            "weekly-brokers": "Weekly shipbroker reports (Xclusiv, Intermodal, Banchero Costa PDFs).",
            "iron-ore": "Chinese iron ore and steelmaking prices (MMI daily).",
            "freight-news": "Freight News. Mostly oil/LNG cargo, not Baltic session prints.",
            "commodity": "Commodity News. Wheat, copper, miners — overlay, not a BDI print.",
            "ports": "Port News. Suez, Panama, terminal ops.",
            "international": "International Shipping News. General maritime; often the largest slice of all.",
        },
        "supports": ["search", "date_range", "category"],
        "access": "public_excerpt",
        "note": (
            "WordPress REST. Default category is all (whole site). "
            "Pin dry-bulk for BDI composite color, weekly-brokers for weeklies, weekly-tce for TCE. "
            "Excerpts, not a full-text dump."
        ),
    },
    "splash": {
        "id": "splash",
        "name": "Splash 247",
        "home": "https://splash247.com/",
        "backend": "wp_rest",
        "wp_base": "https://splash247.com",
        "default_category": "all",
        "categories": {
            "all": None,
            "dry-cargo": 57,
            "containers": 56,
            "tankers": 58,
            "ports": 64,
        },
        "category_guide": {
            "all": "Entire site. Containers, tankers, offshore, dry cargo, regions.",
            "dry-cargo": "Dry Cargo desk. Bulker fixtures/fleet plus other dry-cargo news.",
            "containers": "Container liner news. Out of dry-bulk desk scope unless overlay.",
            "tankers": "Tanker news. Out of dry-bulk desk scope unless overlay.",
            "ports": "Ports and logistics.",
        },
        "supports": ["search", "date_range", "category"],
        "access": "public_excerpt",
        "note": (
            "WordPress REST. Default category is all. Pin dry-cargo for bulker fixtures/fleet."
        ),
    },
    "telegraph": {
        "id": "telegraph",
        "name": "Shipping Telegraph",
        "home": "https://shippingtelegraph.com/",
        "backend": "wp_rest",
        "wp_base": "https://shippingtelegraph.com",
        "default_category": "all",
        "categories": {
            "all": None,
            "freight-news": 118,
            "dry-bulk": 117,
            "shipping-reports": 131,
            "shipping-news": 104,
            "commodity": 113,
        },
        "category_guide": {
            "all": "Entire site. Shipyard, tankers, containers, freight, dry bulk.",
            "freight-news": "Freight news. IC Shipbrokers daily color plus fixtures. Qualitative, not Baltic prints.",
            "dry-bulk": "Dry bulk shipping news.",
            "shipping-reports": "Shipping reports / market notes.",
            "shipping-news": "General shipping news. Largest Telegraph slice.",
            "commodity": "Commodity news.",
        },
        "supports": ["search", "date_range", "category"],
        "access": "public_excerpt",
        "note": (
            "WordPress REST. Default category is all. Pin freight-news for IC Shipbrokers "
            "daily color and fixtures; dry-bulk for bulker-only items."
        ),
    },
    "gcaptain": {
        "id": "gcaptain",
        "name": "gCaptain",
        "home": "https://gcaptain.com/",
        "backend": "wp_rest",
        "wp_base": "https://gcaptain.com",
        "default_category": "all",
        "categories": {
            "all": None,
            "shipping": 80387,
            "shipping-news": 2564,
            "ports": 65,
            "offshore": 80671,
        },
        "category_guide": {
            "all": "Entire site. Tanker/war, containers, offshore, plus occasional Cape/BDI Bloomberg pieces.",
            "shipping": "Shipping section. Still mixed; pass query Capesize or Baltic Dry for rate hits.",
            "shipping-news": "Shipping News tag. Same mix as shipping; not a dry-bulk desk.",
            "ports": "Ports.",
            "offshore": "Offshore. Out of dry-bulk desk scope unless overlay.",
        },
        "supports": ["search", "date_range", "category"],
        "access": "public_excerpt",
        "note": (
            "WordPress REST. Default category is all. No dry-bulk desk — pass query "
            "Capesize or Baltic Dry; unfiltered mix is tanker, container, and offshore."
        ),
    },
}


def press_catalog() -> dict[str, Any]:
    return {
        "backend": "catalog",
        "sites": [PRESS_SITES[site_id] for site_id in SITE_IDS],
    }


def press_fetch(
    site: str,
    query: str | None = None,
    after: str | None = None,
    before: str | None = None,
    category: str | None = None,
    limit: int = 12,
    page: int = 1,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Fetch headlines/excerpts from a known press site. Never bypasses login."""
    settings = settings or get_settings()
    site_id = (site or "").strip().lower()
    spec = PRESS_SITES.get(site_id)
    if spec is None:
        raise ValueError(f"unknown site {site!r}; use press_catalog for ids: {', '.join(SITE_IDS)}")
    n = max(1, min(int(limit or 12), 20))
    page_n = max(1, int(page or 1))
    query_text = (query or "").strip() or None
    after_iso = _as_iso_bound(after, end=False)
    before_iso = _as_iso_bound(before, end=True)

    backend = spec["backend"]
    if backend == "wp_rest":
        payload = _wp_posts(
            spec,
            query=query_text,
            after=after_iso,
            before=before_iso,
            category=category,
            limit=n,
            page=page_n,
            timeout=settings.http_timeout_s,
        )
    else:
        raise ValueError(f"unsupported backend {backend!r} for site {site_id}")

    entries = [
        row
        for row in payload.get("entries") or []
        if _in_range(row.get("published"), after_iso, before_iso)
    ]
    return {
        **payload,
        "entries": entries,
        "returned": len(entries),
        "query": query_text,
        "after": after_iso,
        "before": before_iso,
        "page": page_n,
        "limit": n,
    }


def _wp_posts(
    spec: dict[str, Any],
    *,
    query: str | None,
    after: str | None,
    before: str | None,
    category: str | None,
    limit: int,
    page: int,
    timeout: float,
) -> dict[str, Any]:
    categories = spec.get("categories") or {}
    cat_key = (category or spec.get("default_category") or "all").strip().lower()
    if cat_key not in categories:
        raise ValueError(
            f"unknown category {category!r} for {spec['id']}; "
            f"use {', '.join(sorted(categories))}"
        )
    cat_id = categories[cat_key]
    params: dict[str, Any] = {
        "per_page": limit,
        "page": page,
        "orderby": "date",
        "order": "desc",
        "_fields": "id,date_gmt,date,link,title,excerpt",
    }
    if query:
        params["search"] = query
    if after:
        params["after"] = after
    if before:
        params["before"] = before
    if cat_id:
        params["categories"] = cat_id
    url = f"{spec['wp_base']}/wp-json/wp/v2/posts?{urlencode(params)}"
    status, headers, body = http_get(url, timeout=timeout)
    rows = json.loads(body) if body.strip() else []
    if not isinstance(rows, list):
        rows = []
    entries = [_wp_entry(row) for row in rows]
    total = headers.get("x-wp-total")
    pages = headers.get("x-wp-totalpages")
    return {
        "backend": "wp_rest",
        "site": spec["id"],
        "name": spec["name"],
        "access": spec["access"],
        "supports": spec["supports"],
        "note": spec["note"],
        "default_category": spec.get("default_category") or "all",
        "category_guide": spec.get("category_guide") or {},
        "url": url,
        "status_code": status,
        "category": cat_key,
        "total": int(total) if total and total.isdigit() else None,
        "total_pages": int(pages) if pages and pages.isdigit() else None,
        "entries": entries,
    }


def _wp_entry(row: dict[str, Any]) -> dict[str, Any]:
    title = html.unescape(_plain(_rendered(row.get("title")), 240))
    summary = _plain(_rendered(row.get("excerpt")), 280)
    published = row.get("date_gmt") or row.get("date")
    if isinstance(published, str) and "T" in published and not published.endswith("Z"):
        published = published + "Z" if "+" not in published else published
    return {
        "title": title,
        "url": row.get("link"),
        "published": published,
        "summary": summary,
        "id": row.get("id"),
    }


def _rendered(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("rendered") or "")
    return str(value or "")


def _as_iso_bound(value: str | None, *, end: bool) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return f"{text}T23:59:59" if end else f"{text}T00:00:00"
    return text


def _parse_dt(text: str | None) -> datetime | None:
    raw = (text or "").strip()
    if not raw:
        return None
    iso = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(iso)
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(raw)
    except (TypeError, ValueError, IndexError):
        return None


def _in_range(published: str | None, after: str | None, before: str | None) -> bool:
    if not after and not before:
        return True
    observed = _parse_dt(published)
    if observed is None:
        return True
    lo = _parse_dt(after)
    hi = _parse_dt(before)
    if observed.tzinfo and lo and lo.tzinfo is None:
        lo = lo.replace(tzinfo=observed.tzinfo)
    if observed.tzinfo and hi and hi.tzinfo is None:
        hi = hi.replace(tzinfo=observed.tzinfo)
    if lo and observed < lo:
        return False
    if hi and observed > hi:
        return False
    return True

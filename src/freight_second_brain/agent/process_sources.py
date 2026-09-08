"""Label, deduplicate, and summarize web sources before they hit the desk."""

from __future__ import annotations

import re
from datetime import date
from typing import Any
from urllib.parse import urlparse, unquote

from freight_second_brain.agent.artifacts import extract_bdi_print
from freight_second_brain.agent.source_tags import apply_classification

_TITLE_NOISE = re.compile(
    r"\s*[|\-–—]\s*(hellenic shipping news.*|daily cargo news.*|business times.*)?$",
    re.I,
)
_DAILY_BDI = re.compile(r"baltic dry index.+(climb|fell|fall|rose|up|down|reach)", re.I)
_WEEKLY = re.compile(r"\b(week(?:ly)?|week\s*\d{1,2})\b", re.I)
_OVERLAY = re.compile(
    r"black sea|russian wheat|grain corridor|handy(?!size index)|container|tanker|vlcc|scfi",
    re.I,
)
_IRRELEVANT = re.compile(
    r"hapag|scfi|amazon shipping|cruise|air freight|vlcc|container shipping market",
    re.I,
)

PRIMARY_HOSTS = {
    "balticexchange.com": 0,
    "reuters.com": 1,
    "bairdmaritime.com": 1,
    "bigmint.com": 2,
    "mysteel.net": 2,
    "unctad.org": 2,
    "skibskredit.dk": 2,
}
REPRINT_HOSTS = {
    "hellenicshippingnews.com",
    "thedcn.com.au",
    "businesstimes.com.sg",
    "i3investor.com",
    "maritimecyprus.com",
}


def pretty_url(url: str | None) -> dict[str, str]:
    raw = (url or "").strip()
    parsed = urlparse(raw)
    host = parsed.netloc.lower().removeprefix("www.")
    path = unquote(parsed.path or "").rstrip("/")
    leaf = path.rsplit("/", 1)[-1] if path else ""
    if leaf.lower().endswith(".pdf"):
        display_path = leaf
    else:
        display_path = leaf.replace("-", " ").replace("_", " ").strip()
        if len(display_path) > 64:
            display_path = display_path[:63].rstrip() + "…"
    return {
        "url": raw,
        "host": host,
        "path": display_path or "/",
        "label": f"{host} · {display_path}" if display_path else host,
    }


def _normalize_title(title: str) -> str:
    cleaned = _TITLE_NOISE.sub("", title or "")
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def _publisher(host: str, title: str, url: str) -> str:
    if host in PRIMARY_HOSTS:
        return host.split(".")[0].title()
    if "xclusiv" in url.lower() or "xclusiv" in title.lower():
        return "Xclusiv"
    if url.lower().endswith(".pdf"):
        return "Broker PDF"
    if "hellenicshippingnews" in host:
        return "Hellenic Shipping News"
    if "thedcn" in host:
        return "Daily Cargo News"
    return host.split(".")[0].replace("-", " ").title() or "Web"


def _rank(host: str, title: str, url: str, role_hint: str) -> int:
    if role_hint == "overlay":
        return 8
    if role_hint == "tertiary":
        return 7
    if host in PRIMARY_HOSTS:
        return PRIMARY_HOSTS[host]
    lowered = f"{title} {url}".lower()
    if lowered.endswith(".pdf") or "xclusiv" in lowered or "lion" in lowered:
        return 2
    if host in REPRINT_HOSTS and lowered.endswith(".pdf"):
        return 3
    if host in REPRINT_HOSTS:
        return 5
    return 6


def _freshness(published: str | None) -> str:
    text = (published or "").lower()
    if "2023" in text or "2024" in text or "2025" in text:
        if "2026" not in text:
            return "historical_vintage"
    if any(token in text for token in ("mon,", "tue,", "wed,", "thu,", "fri,", "sat,", "sun,")):
        return "current"
    if re.search(r"2026-09|sep(?:t)?(?:ember)?\s*2026", text, re.I):
        return "current"
    return "recent"


def _one_liner(title: str, snippet: str, print_value: int | None, published: str | None, role: str) -> str:
    date_bit = (published or "").split("+")[0].strip()
    if len(date_bit) > 22:
        date_bit = date_bit[:22].rstrip()
    if print_value is not None and _DAILY_BDI.search(title or ""):
        base = f"BDI {print_value:,} composite daily print"
        return f"{base} ({date_bit})." if date_bit else f"{base}."
    if print_value is not None and _WEEKLY.search(title or ""):
        return f"Weekly recap with BDI around {print_value:,}."
    if role == "overlay":
        return "Related dry-bulk overlay (grain/Handy), not a Capesize session print."
    blob = re.sub(r"\s+", " ", snippet or title or "").strip()
    if len(blob) > 118:
        blob = blob[:117].rstrip() + "…"
    return blob


def _role(title: str, url: str, host: str) -> str:
    blob = f"{title} {url}"
    if _IRRELEVANT.search(blob) and "dry bulk" not in blob.lower() and "baltic dry" not in blob.lower():
        return "drop"
    if _OVERLAY.search(title or "") and not _DAILY_BDI.search(title or ""):
        return "overlay"
    if host in PRIMARY_HOSTS or url.lower().endswith(".pdf"):
        return "primary"
    if host in REPRINT_HOSTS:
        return "reprint"
    if "tide" in host or "blog" in host:
        return "tertiary"
    return "secondary"


def independence_group(title: str, print_value: int | None, published: str | None) -> str:
    day = ""
    if published:
        iso = re.search(r"20\d{2}-\d{2}-\d{2}", published)
        if iso:
            day = iso.group(0)
        else:
            day = re.sub(r"\s+", " ", published)[:16]
    if print_value is not None and _DAILY_BDI.search(title or ""):
        return f"bdi-daily-{print_value}-{day}"
    if print_value is not None and _WEEKLY.search(title or ""):
        return f"bdi-weekly-{print_value}"
    if print_value is not None:
        return f"print-{print_value}-{day}"
    return f"title-{_normalize_title(title)[:48]}"


def enrich_source_card(card: dict[str, Any], *, origin_turn: int) -> dict[str, Any] | None:
    """Annotate a source card for ranked display. Returns None if it should be dropped."""
    payload = dict(card.get("payload") or {})
    url = str(payload.get("url") or card.get("provenance", {}).get("url") or "")
    title = str(card.get("title") or "")
    pretty = pretty_url(url)
    role = _role(title, url, pretty["host"])
    if role == "drop":
        return None
    snippet = str(payload.get("snippet") or " ".join(payload.get("highlights") or []) or "")
    print_value = payload.get("print")
    if print_value is None:
        print_value = extract_bdi_print(" ".join([title, snippet]))
    published = payload.get("published") or card.get("subtitle")
    group = independence_group(title, print_value, published)
    rank = _rank(pretty["host"], title, url, role)
    existing_turn = payload.get("origin_turn")
    payload.update(
        {
            "url": url,
            "print": print_value,
            "publisher": _publisher(pretty["host"], title, url),
            "pretty_host": pretty["host"],
            "pretty_path": pretty["path"],
            "pretty_label": pretty["label"],
            "one_liner": _one_liner(title, snippet, print_value, published, role),
            "role": role,
            "independence_group": group,
            "freshness": _freshness(str(published) if published else None),
            "rank": rank,
            "origin_turn": existing_turn if existing_turn is not None else origin_turn,
        }
    )
    card = {**card, "payload": payload, "subtitle": payload.get("publisher")}
    return card


def relabel_groups(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Within each independence group, mark the best record primary and the rest duplicates."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for card in cards:
        group = str((card.get("payload") or {}).get("independence_group") or card["id"])
        grouped.setdefault(group, []).append(card)
    relabeled: list[dict[str, Any]] = []
    for group_cards in grouped.values():
        ordered = sorted(group_cards, key=lambda c: int((c.get("payload") or {}).get("rank") or 9))
        for index, card in enumerate(ordered):
            payload = dict(card.get("payload") or {})
            payload["hierarchy"] = "primary" if index == 0 else "duplicate"
            payload["duplicate_count"] = max(0, len(ordered) - 1)
            relabeled.append({**card, "payload": payload})
    return relabeled


def process_source_cards(
    cards: list[dict[str, Any]], *, origin_turn: int, as_of: date | None = None
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for card in cards:
        if card.get("kind") != "source_card":
            continue
        item = enrich_source_card(card, origin_turn=origin_turn)
        if item:
            enriched.append(item)
    return [apply_classification(card, as_of=as_of) for card in relabel_groups(enriched)]

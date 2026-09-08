"""Structured desk objects: source cards, tables, charts, and supersession."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any, Literal

Kind = Literal["source_card", "table", "chart"]
Status = Literal["active", "superseded"]

PRINTS_TABLE_ID = "table-prints"
PRINTS_CHART_ID = "chart-bdi"

_BDI_VALUE_RE = re.compile(
    r"(?:baltic dry index|\bbdi\b).{0,48}?(?:climbed|rose|fell|fell by|decreased|increased|reaching|reached|to|at|up|down)\s+(?:[\d.]+%\s+to\s+)?(\d{1,2}[, ]?\d{3})",
    re.I,
)
_BARE_POINTS_RE = re.compile(r"\b(\d{1,2}[, ]?\d{3})\s+points\b", re.I)


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def artifact_id_for_url(url: str) -> str:
    digest = hashlib.sha1((url or "").encode("utf-8")).hexdigest()[:12]
    return f"src-{digest}"


def _parse_int(raw: str) -> int:
    return int(re.sub(r"[, ]", "", raw))


def extract_bdi_print(text: str | None) -> int | None:
    blob = text or ""
    match = _BDI_VALUE_RE.search(blob)
    if match:
        return _parse_int(match.group(1))
    match = _BARE_POINTS_RE.search(blob)
    if match and "baltic" in blob.lower():
        return _parse_int(match.group(1))
    return None


def new_artifact(
    *,
    object_id: str,
    kind: Kind,
    title: str,
    payload: dict[str, Any],
    subtitle: str | None = None,
    provenance: dict[str, Any] | None = None,
    status: Status = "active",
    superseded_by: str | None = None,
    supersede_reason: str | None = None,
    revision: int = 1,
) -> dict[str, Any]:
    return {
        "id": object_id,
        "kind": kind,
        "status": status,
        "superseded_by": superseded_by,
        "supersede_reason": supersede_reason,
        "title": title,
        "subtitle": subtitle,
        "provenance": provenance or {},
        "payload": payload,
        "revision": revision,
        "updated_at": now_iso(),
    }


def source_card_from_web_hit(hit: dict[str, Any], *, tool: str) -> dict[str, Any] | None:
    url = (hit.get("url") or "").strip()
    if not url:
        return None
    highlights = [str(h) for h in (hit.get("highlights") or []) if h]
    snippet = hit.get("text") or hit.get("summary") or " ".join(highlights[:2])
    return new_artifact(
        object_id=artifact_id_for_url(url),
        kind="source_card",
        title=(hit.get("title") or url).strip(),
        subtitle=hit.get("published_date") or hit.get("published"),
        provenance={
            "tool": tool,
            "url": url,
            "published": hit.get("published_date") or hit.get("published"),
            "backend": hit.get("backend"),
        },
        payload={
            "url": url,
            "published": hit.get("published_date") or hit.get("published"),
            "highlights": highlights[:4],
            "snippet": snippet,
            "print": extract_bdi_print(" ".join([hit.get("title") or "", snippet or ""])),
        },
    )


def source_card_from_fetch(data: dict[str, Any]) -> dict[str, Any] | None:
    url = (data.get("url") or "").strip()
    if not url:
        return None
    text = data.get("text") or ""
    snippet = " ".join(text.split())[:420]
    return new_artifact(
        object_id=artifact_id_for_url(url),
        kind="source_card",
        title=url.rsplit("/", 2)[-2].replace("-", " ").title() if "/" in url else url,
        subtitle=data.get("published"),
        provenance={"tool": "fetch_url", "url": url, "jina_url": data.get("jina_url")},
        payload={
            "url": url,
            "published": None,
            "highlights": [],
            "snippet": snippet,
            "cookie_wall": bool(data.get("cookie_wall")),
            "print": extract_bdi_print(text[:1500]),
        },
    )


def merge_print_points(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    for point in existing + incoming:
        key = str(point.get("t") or point.get("label") or point.get("v"))
        prior = by_key.get(key)
        if prior is None or (point.get("v") is not None):
            by_key[key] = point
    rows = list(by_key.values())

    def sort_key(row: dict[str, Any]) -> tuple[str, str]:
        return (str(row.get("t") or ""), str(row.get("label") or ""))

    rows.sort(key=sort_key)
    return rows[-24:]


def prints_table(points: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [
        {
            "as_of": p.get("t"),
            "series": p.get("series") or "BDI",
            "value": p.get("v"),
            "source": p.get("label"),
        }
        for p in points
    ]
    return new_artifact(
        object_id=PRINTS_TABLE_ID,
        kind="table",
        title="Baltic prints (web)",
        subtitle="Sourced figures only — not a forecast",
        provenance={"tool": "derived"},
        payload={
            "columns": [
                {"key": "as_of", "label": "As of"},
                {"key": "series", "label": "Series"},
                {"key": "value", "label": "Print"},
                {"key": "source", "label": "Source"},
            ],
            "rows": rows,
            "numeric": ["value"],
        },
    )


def prints_chart(points: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for point in points:
        if point.get("v") is None:
            continue
        name = str(point.get("series") or "BDI")
        grouped.setdefault(name, []).append({"x": point.get("t") or point.get("label"), "y": point.get("v")})
    series = [{"name": name, "points": pts} for name, pts in grouped.items()]
    multi = len(series) > 1
    return new_artifact(
        object_id=PRINTS_CHART_ID,
        kind="chart",
        title="Sourced prints" if multi else "BDI composite prints",
        subtitle="From independent web sources in this session",
        provenance={"tool": "derived"},
        payload={
            "x_label": "As of",
            "y_label": "Value" if multi else "Index",
            "series": series,
        },
    )


def materialize_from_tool(name: str, data: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (artifacts, print points) derived from a research tool payload."""
    artifacts: list[dict[str, Any]] = []
    points: list[dict[str, Any]] = []
    if not isinstance(data, dict):
        return artifacts, points
    if name == "web_search":
        for hit in data.get("results") or []:
            card = source_card_from_web_hit(hit, tool="web_search")
            if card:
                artifacts.append(card)
                value = card["payload"].get("print")
                if value is not None:
                    points.append(
                        {
                            "t": hit.get("published_date") or now_iso()[:10],
                            "v": value,
                            "series": "BDI",
                            "label": hit.get("title"),
                            "url": hit.get("url"),
                        }
                    )
    elif name == "rss_feed":
        for entry in data.get("entries") or []:
            card = source_card_from_web_hit(
                {
                    "title": entry.get("title"),
                    "url": entry.get("url"),
                    "published": entry.get("published"),
                    "summary": entry.get("summary"),
                    "highlights": [entry.get("summary")] if entry.get("summary") else [],
                },
                tool="rss_feed",
            )
            if card:
                artifacts.append(card)
                value = extract_bdi_print(" ".join([entry.get("title") or "", entry.get("summary") or ""]))
                if value is not None:
                    points.append(
                        {
                            "t": (entry.get("published") or "")[:16] or now_iso()[:10],
                            "v": value,
                            "series": "BDI",
                            "label": entry.get("title"),
                            "url": entry.get("url"),
                        }
                    )
    elif name == "fetch_url":
        card = source_card_from_fetch(data)
        if card:
            artifacts.append(card)
            value = card["payload"].get("print")
            if value is not None:
                points.append(
                    {
                        "t": now_iso()[:10],
                        "v": value,
                        "series": "BDI",
                        "label": card["title"],
                        "url": data.get("url"),
                    }
                )
    return artifacts, points

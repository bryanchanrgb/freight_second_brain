"""Structured desk objects: generative reports, plus leftover card/table helpers."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any, Literal

from freight_second_brain.agent.json_payload import looks_like_json_payload, parse_json_payload

Kind = Literal["source_card", "table", "chart", "report"]
Status = Literal["active", "superseded"]

PRINTS_TABLE_ID = "table-prints"
PRINTS_CHART_ID = "chart-bdi"
REPORT_ID = "report-main"

def report_id_for_turn(turn: int) -> str:
    return f"report-turn-{max(1, int(turn or 1))}"
MAX_REPORT_BLOCKS = 80
MAX_REPORT_DEPTH = 3
PARSE_FAIL_CALLOUT = {
    "type": "callout",
    "tone": "warn",
    "title": "Report payload could not be parsed",
    "text": (
        "The model sent blocks that were not valid JSON, so the structured report "
        "was not written. Retry the question."
    ),
}
BLOCKS_JSON_ERROR = (
    "blocks_json is not valid JSON. Call present_report again with a JSON array of "
    "blocks. Escape double quotes inside strings. Do not wrap the array in markdown fences."
)
REPORT_BLOCK_TYPES = (
    "markdown",
    "heading",
    "callout",
    "kpis",
    "table",
    "chart",
    "citations",
    "expand",
    "quote",
    "divider",
    "diagram",
)

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
        key = "|".join(
            [
                str(point.get("t") or point.get("label") or ""),
                str(point.get("series") or "BDI"),
                str(point.get("url") or point.get("label") or ""),
            ]
        )
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
    elif name in ("rss_feed", "press_fetch"):
        for entry in data.get("entries") or []:
            card = source_card_from_web_hit(
                {
                    "title": entry.get("title"),
                    "url": entry.get("url"),
                    "published": entry.get("published"),
                    "summary": entry.get("summary"),
                    "highlights": [entry.get("summary")] if entry.get("summary") else [],
                },
                tool=name,
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
    elif name == "market_feed":
        latest = data.get("latest")
        if not isinstance(latest, dict):
            latest = {}
        for code, row in latest.items():
            if not isinstance(row, dict):
                continue
            url = str(row.get("cite_url") or "").strip()
            if not url:
                continue
            series = str(row.get("alias") or code)
            date = str(row.get("date") or row.get("as_of") or "")[:10]
            value = row.get("value")
            snippet = f"{row.get('name') or series} {row.get('formatted') or value} as of {date or 'n/a'} (OilPriceAPI reprint)"
            artifacts.append(
                new_artifact(
                    object_id=f"src-market-{str(code).lower().replace('_', '-')}",
                    kind="source_card",
                    title=str(row.get("name") or series),
                    subtitle=date or None,
                    provenance={
                        "tool": "market_feed",
                        "url": url,
                        "published": row.get("as_of") or date,
                        "publisher": "OilPriceAPI",
                    },
                    payload={
                        "url": url,
                        "published": row.get("as_of") or date,
                        "highlights": [snippet],
                        "snippet": snippet,
                        "print": value if str(code) == "BALTIC_DRY_INDEX" else None,
                    },
                )
            )
            if value is not None and date:
                points.append(
                    {
                        "t": date,
                        "v": value,
                        "series": series,
                        "label": row.get("name") or series,
                        "url": url,
                    }
                )
    return artifacts, points


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_columns(raw: Any) -> list[dict[str, str]]:
    columns: list[dict[str, str]] = []
    for item in _as_list(raw):
        if isinstance(item, str) and item.strip():
            key = item.strip()
            columns.append({"key": key, "label": key})
            continue
        if not isinstance(item, dict):
            continue
        key = _as_text(item.get("key") or item.get("id") or item.get("label"))
        if not key:
            continue
        columns.append({"key": key, "label": _as_text(item.get("label") or key)})
    return columns


def _normalize_chart_series(raw: Any) -> list[dict[str, Any]]:
    series: list[dict[str, Any]] = []
    for item in _as_list(raw):
        if not isinstance(item, dict):
            continue
        name = _as_text(item.get("name") or item.get("label") or f"Series {len(series) + 1}")
        points: list[dict[str, Any]] = []
        for point in _as_list(item.get("points") or item.get("data")):
            if isinstance(point, dict) and point.get("x") is not None and point.get("y") is not None:
                try:
                    y = float(point["y"])
                except (TypeError, ValueError):
                    continue
                points.append({"x": point["x"], "y": y})
            elif isinstance(point, (list, tuple)) and len(point) >= 2:
                try:
                    y = float(point[1])
                except (TypeError, ValueError):
                    continue
                points.append({"x": point[0], "y": y})
        if points:
            series.append({"name": name, "points": points})
    return series


def is_parse_fail_blocks(blocks: list[dict[str, Any]]) -> bool:
    return (
        len(blocks) == 1
        and blocks[0].get("type") == "callout"
        and blocks[0].get("title") == PARSE_FAIL_CALLOUT["title"]
    )


def unusable_blocks_json(value: Any) -> bool:
    if isinstance(value, (list, dict)):
        return False
    if not isinstance(value, str):
        return False
    return looks_like_json_payload(value) and parse_json_payload(value) is None


def normalize_report_blocks(blocks: Any, *, depth: int = 0) -> list[dict[str, Any]]:
    """Coerce an LLM block list into a bounded, renderable report payload."""
    if depth > MAX_REPORT_DEPTH:
        return []
    if isinstance(blocks, str):
        parsed = parse_json_payload(blocks)
        if parsed is not None:
            return normalize_report_blocks(parsed, depth=depth)
        if looks_like_json_payload(blocks):
            return [dict(PARSE_FAIL_CALLOUT)] if depth == 0 else []
        text = blocks.strip()
        return [{"type": "markdown", "text": text}] if text else []
    if isinstance(blocks, dict):
        blocks = blocks.get("blocks") or blocks.get("sections") or []
    out: list[dict[str, Any]] = []
    for raw in _as_list(blocks):
        if len(out) >= MAX_REPORT_BLOCKS:
            break
        if isinstance(raw, str) and raw.strip():
            if looks_like_json_payload(raw):
                parsed = parse_json_payload(raw)
                if parsed is not None:
                    out.extend(normalize_report_blocks(parsed, depth=depth + 1))
                continue
            out.append({"type": "markdown", "text": raw.strip()})
            continue
        if not isinstance(raw, dict):
            continue
        kind = _as_text(raw.get("type") or raw.get("kind")).lower() or "markdown"
        if kind not in REPORT_BLOCK_TYPES:
            text = _as_text(raw.get("text") or raw.get("markdown") or raw.get("content"))
            if text:
                out.append({"type": "markdown", "text": text})
            continue
        if kind == "divider":
            out.append({"type": "divider"})
            continue
        if kind == "heading":
            try:
                level = int(raw.get("level") or 2)
            except (TypeError, ValueError):
                level = 2
            text = _as_text(raw.get("text") or raw.get("title"))
            if text:
                out.append({"type": "heading", "text": text, "level": min(3, max(1, level))})
            continue
        if kind == "markdown":
            text = _as_text(raw.get("text") or raw.get("markdown") or raw.get("content"))
            if text:
                out.append({"type": "markdown", "text": text})
            continue
        if kind == "callout":
            text = _as_text(raw.get("text") or raw.get("body") or raw.get("content"))
            if not text:
                continue
            tone = _as_text(raw.get("tone") or raw.get("kind")).lower() or "info"
            if tone not in {"info", "note", "warn", "risk"}:
                tone = "info"
            block: dict[str, Any] = {"type": "callout", "tone": tone, "text": text}
            title = _as_text(raw.get("title"))
            if title:
                block["title"] = title
            out.append(block)
            continue
        if kind == "quote":
            text = _as_text(raw.get("text") or raw.get("body"))
            if not text:
                continue
            block = {"type": "quote", "text": text}
            attribution = _as_text(raw.get("attribution") or raw.get("cite") or raw.get("source"))
            if attribution:
                block["attribution"] = attribution
            out.append(block)
            continue
        if kind == "kpis":
            items: list[dict[str, str]] = []
            for item in _as_list(raw.get("items") or raw.get("kpis")):
                if not isinstance(item, dict):
                    continue
                label = _as_text(item.get("label") or item.get("name"))
                value = _as_text(item.get("value"))
                if not label or not value:
                    continue
                row = {"label": label, "value": value}
                caption = _as_text(item.get("caption") or item.get("hint"))
                if caption:
                    row["caption"] = caption
                items.append(row)
            if items:
                out.append({"type": "kpis", "items": items})
            continue
        if kind == "table":
            columns = _normalize_columns(raw.get("columns"))
            rows = [row for row in _as_list(raw.get("rows")) if isinstance(row, dict)]
            if not columns and rows:
                columns = _normalize_columns(list(rows[0].keys()))
            if not columns:
                continue
            block = {"type": "table", "columns": columns, "rows": rows}
            for key in ("title", "subtitle"):
                value = _as_text(raw.get(key))
                if value:
                    block[key] = value
            numeric = [str(item) for item in _as_list(raw.get("numeric")) if item]
            if numeric:
                block["numeric"] = numeric
            out.append(block)
            continue
        if kind == "chart":
            series = _normalize_chart_series(raw.get("series"))
            if not series:
                continue
            variant = _as_text(raw.get("variant") or raw.get("chart") or "line").lower()
            if variant not in {"line", "area", "bar"}:
                variant = "line"
            block = {"type": "chart", "series": series, "variant": variant}
            for key in ("title", "subtitle", "x_label", "y_label"):
                value = _as_text(raw.get(key))
                if value:
                    block[key] = value
            out.append(block)
            continue
        if kind == "citations":
            items = []
            for item in _as_list(raw.get("items") or raw.get("citations") or raw.get("sources")):
                if not isinstance(item, dict):
                    continue
                title = _as_text(item.get("title") or item.get("label"))
                url = _as_text(item.get("url") or item.get("href"))
                if not title and not url:
                    continue
                row: dict[str, str] = {"title": title or url, "url": url}
                for key in ("publisher", "as_of", "note"):
                    value = _as_text(item.get(key))
                    if value:
                        row[key] = value
                items.append(row)
            if items:
                out.append({"type": "citations", "items": items})
            continue
        if kind == "expand":
            title = _as_text(raw.get("title") or raw.get("label") or "Details")
            nested = normalize_report_blocks(
                raw.get("blocks") or raw.get("children") or [], depth=depth + 1
            )
            if nested:
                out.append({"type": "expand", "title": title, "blocks": nested})
            continue
        if kind == "diagram":
            nodes: list[dict[str, str]] = []
            for item in _as_list(raw.get("nodes")):
                if isinstance(item, str) and item.strip():
                    nodes.append({"id": item.strip(), "label": item.strip()})
                    continue
                if not isinstance(item, dict):
                    continue
                node_id = _as_text(item.get("id") or item.get("label"))
                label = _as_text(item.get("label") or node_id)
                if node_id:
                    nodes.append({"id": node_id, "label": label or node_id})
            edges: list[dict[str, str]] = []
            for item in _as_list(raw.get("edges")):
                if not isinstance(item, dict):
                    continue
                src = _as_text(item.get("from") or item.get("source"))
                dst = _as_text(item.get("to") or item.get("target"))
                if not src or not dst:
                    continue
                edge = {"from": src, "to": dst}
                label = _as_text(item.get("label"))
                if label:
                    edge["label"] = label
                edges.append(edge)
            if not nodes:
                continue
            block = {"type": "diagram", "nodes": nodes, "edges": edges}
            title = _as_text(raw.get("title"))
            if title:
                block["title"] = title
            out.append(block)
    unwrapped = _unwrap_json_markdown(out, depth)
    return unwrapped if unwrapped is not None else out


def _unwrap_json_markdown(blocks: list[dict[str, Any]], depth: int) -> list[dict[str, Any]] | None:
    """If the model stuffed a block array into one markdown string, parse it."""
    if depth >= MAX_REPORT_DEPTH or len(blocks) != 1 or blocks[0].get("type") != "markdown":
        return None
    text = str(blocks[0].get("text") or "")
    if not looks_like_json_payload(text):
        return None
    parsed = parse_json_payload(text)
    if parsed is None:
        return [dict(PARSE_FAIL_CALLOUT)] if depth == 0 else []
    if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
        if parsed[0].get("type") or parsed[0].get("kind") or "blocks" in parsed[0]:
            return normalize_report_blocks(parsed, depth=depth + 1)
    if isinstance(parsed, dict) and (parsed.get("blocks") or parsed.get("type") or parsed.get("kind")):
        return normalize_report_blocks(parsed, depth=depth + 1)
    return None


def normalize_citations(raw: Any) -> list[dict[str, Any]]:
    """1-based citation list: {n, url, title, id} matching source-card ids when URL is present."""
    items: list[dict[str, Any]] = []
    if isinstance(raw, dict):
        raw = raw.get("items") or raw.get("citations") or raw.get("sources") or []
    seen_n: set[int] = set()
    for index, item in enumerate(_as_list(raw), start=1):
        if isinstance(item, str) and item.strip():
            url = item.strip()
            title = ""
            n = index
        elif isinstance(item, dict):
            url = _as_text(item.get("url") or item.get("href"))
            title = _as_text(item.get("title") or item.get("label"))
            try:
                n = int(item.get("n") or item.get("index") or index)
            except (TypeError, ValueError):
                n = index
        else:
            continue
        if n < 1:
            n = index
        while n in seen_n:
            n += 1
        seen_n.add(n)
        if not url and not title:
            continue
        row: dict[str, Any] = {"n": n, "url": url, "title": title or url}
        if url:
            row["id"] = artifact_id_for_url(url)
        if isinstance(item, dict):
            for key in ("publisher", "as_of", "note"):
                value = _as_text(item.get(key))
                if value:
                    row[key] = value
        items.append(row)
    items.sort(key=lambda row: int(row["n"]))
    return items


def citations_from_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    found: list[Any] = []
    for block in blocks:
        if block.get("type") == "citations":
            found.extend(block.get("items") or [])
    return normalize_citations(found)

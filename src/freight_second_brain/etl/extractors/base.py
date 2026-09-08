from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Protocol

from freight_second_brain.config import PARSER_VERSION, Settings
from freight_second_brain.etl.landing import LandingZone
from freight_second_brain.warehouse.schemas import Claim, Event, Observation, RetrievedSource


def utcnow() -> datetime:
    return datetime.now(UTC)


def slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return cleaned or "unknown"


def observation_id(source_id: str, series_id: str, observed_at: date, vintage: str | None = None) -> str:
    key = f"{source_id}|{series_id}|{observed_at.isoformat()}|{vintage or ''}"
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def parse_month_token(token: str) -> date | None:
    token = token.strip()
    match = re.fullmatch(r"(\d{4})M(\d{2})", token)
    if match:
        return date(int(match.group(1)), int(match.group(2)), 1)
    match = re.fullmatch(r"(\d{4})-(\d{2})", token)
    if match:
        return date(int(match.group(1)), int(match.group(2)), 1)
    match = re.fullmatch(r"(\d{4})(\d{2})", token)
    if match and 1 <= int(match.group(2)) <= 12:
        return date(int(match.group(1)), int(match.group(2)), 1)
    match = re.fullmatch(r"(\d{4})", token)
    if match:
        return date(int(match.group(1)), 1, 1)
    return None


def to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, float) and value != value:  # noqa: PLR0124
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if text.lower() in {"", "...", "…", "na", "n/a", "null", "-", "--", "nan"}:
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    if parsed != parsed:  # noqa: PLR0124
        return None
    return parsed


def infer_commodity(name: str) -> str | None:
    lowered = name.lower()
    mapping = (
        ("iron ore", "iron_ore"),
        ("coal", "coal"),
        ("crude oil", "crude_oil"),
        ("brent", "crude_oil"),
        ("wti", "crude_oil"),
        ("natural gas", "natural_gas"),
        ("wheat", "wheat"),
        ("maize", "corn"),
        ("corn", "corn"),
        ("soy", "soybeans"),
        ("barley", "barley"),
        ("rice", "rice"),
        ("bauxite", "bauxite"),
        ("alumina", "alumina"),
        ("aluminum", "aluminum"),
        ("copper", "copper"),
        ("phosphate", "phosphate"),
        ("urea", "urea"),
    )
    for needle, commodity in mapping:
        if needle in lowered:
            return commodity
    return None


def infer_vessel_class(name: str) -> str | None:
    lowered = name.lower()
    for klass in ("capesize", "panamax", "supramax", "handysize"):
        if klass in lowered:
            return klass
    if re.search(r"\bbci\b", lowered):
        return "capesize"
    if re.search(r"\bbpi\b", lowered):
        return "panamax"
    if re.search(r"\bbsi\b", lowered):
        return "supramax"
    if re.search(r"\bbhsi\b", lowered):
        return "handysize"
    return None


@dataclass
class RunContext:
    run_id: str
    retrieved_at: datetime
    settings: Settings
    landing: LandingZone


@dataclass
class ExtractResult:
    source_id: str
    status: str
    observations: list[Observation] = field(default_factory=list)
    retrieved_sources: list[RetrievedSource] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    snapshot_uris: list[str] = field(default_factory=list)
    requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    notes: list[str] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)


class Extractor(Protocol):
    name: str

    def extract(self, ctx: RunContext) -> ExtractResult: ...


def make_retrieved_source(
    *,
    source_id: str,
    url: str,
    publisher: str,
    source_type: str,
    retrieved_at: datetime,
    content_hash: str | None,
    raw_uri: str | None,
    title: str | None = None,
    license_name: str | None = None,
    retrieval_status: str = "full_text",
) -> RetrievedSource:
    return RetrievedSource(
        source_id=source_id,
        canonical_url=url,
        publisher=publisher,
        source_type=source_type,
        retrieved_time=retrieved_at,
        access_status="ok",
        license=license_name,
        content_hash=content_hash,
        raw_object_uri=raw_uri,
        title=title,
        independence_group=source_id,
        retrieval_status=retrieval_status,
    )


PARSER_VERSION_STAMP = PARSER_VERSION

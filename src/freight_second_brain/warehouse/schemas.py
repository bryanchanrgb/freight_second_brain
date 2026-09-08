from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(UTC)


class HistoricalAvailability(StrEnum):
    YES = "yes"
    PARTIAL = "partial"
    NO = "no"


class AccessStatus(StrEnum):
    VERIFIED_PUBLIC = "verified_public"
    VERIFIED_LICENSED = "verified_licensed"
    VERIFIED_PARTIAL = "verified_partial"
    FALLBACK = "fallback"
    BLOCKED = "blocked"
    FAILED = "failed"


class ObservationKind(StrEnum):
    REALIZED = "realized"
    ASSESSMENT = "assessment"
    FORECAST = "forecast"
    PROXY = "proxy"
    NARRATIVE = "narrative"


class ClaimType(StrEnum):
    OBSERVATION = "observation"
    EXPLANATION = "explanation"
    FORECAST = "forecast"
    SCENARIO = "scenario"
    RISK = "risk"
    METHODOLOGY = "methodology"


class Polarity(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    MIXED = "mixed"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


class FreshnessClass(StrEnum):
    CURRENT = "current"
    RECENT = "recent"
    AGING = "aging"
    HISTORICAL_VINTAGE = "historical_vintage"
    POST_CUTOFF_OUTCOME = "post_cutoff_outcome"


class CatalogSource(BaseModel):
    source_id: str
    name: str
    publisher: str
    source_type: str
    status: AccessStatus
    data_and_purpose: str
    access_pattern: str
    default_url: str
    license: str = "unknown"
    historical_available: HistoricalAvailability = HistoricalAvailability.PARTIAL
    history_start: str | None = None
    history_end: str | None = None
    history_frequency: str | None = None
    history_access_method: str = "http"
    history_requires_license: bool = False
    history_revision_behavior: str = "unknown"
    fallback_source_ids: list[str] = Field(default_factory=list)
    extractor: str | None = None
    enabled_by_default: bool = True
    notes: str = ""


class Observation(BaseModel):
    observation_id: str
    source_id: str
    series_id: str
    observed_at: date
    published_at: datetime | None = None
    vintage_id: str | None = None
    value: float
    unit: str
    currency: str | None = None
    frequency: str
    geography: str | None = None
    origin: str | None = None
    destination: str | None = None
    route: str | None = None
    commodity: str | None = None
    vessel_class: str | None = None
    rate_type: str | None = None
    kind: ObservationKind = ObservationKind.REALIZED
    methodology_version: str | None = None
    quality_flag: str = "ok"
    raw_object_uri: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class RetrievedSource(BaseModel):
    source_id: str
    canonical_url: str
    publisher: str
    source_type: str
    publication_time: datetime | None = None
    retrieved_time: datetime
    access_status: str
    license: str | None = None
    content_hash: str | None = None
    raw_object_uri: str | None = None
    title: str | None = None
    independence_group: str | None = None
    quality: str = "public"
    retrieval_status: str = "full_text"
    extra: dict[str, Any] = Field(default_factory=dict)


class UserFeedback(BaseModel):
    feedback_id: str
    claim_id_or_group_id: str
    user_id: str = "local"
    adjustment: str
    scope: str = "claim"
    reason: str = ""
    created_at: datetime = Field(default_factory=utcnow)


class RunManifest(BaseModel):
    run_id: str
    started_at: datetime
    finished_at: datetime | None = None
    status: str = "running"
    parser_version: str
    source_registry_version: str = "0.2"
    requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    observation_count: int = 0
    source_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    quality_report_uri: str | None = None

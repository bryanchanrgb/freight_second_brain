from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from freight_second_brain.config import Settings
from freight_second_brain.etl.extractors.base import RunContext
from freight_second_brain.etl.http import HttpResult
from freight_second_brain.etl.landing import LandingZone
from freight_second_brain.warehouse.schemas import (
    Claim,
    Event,
    Observation,
    RetrievedSource,
)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_root=tmp_path,
        http_retries=0,
        comtrade_delay_s=0.0,
        http_timeout_s=5.0,
    )


@pytest.fixture
def ctx(settings: Settings) -> RunContext:
    return RunContext(
        run_id="20260907T000000Z",
        retrieved_at=datetime(2026, 9, 7, tzinfo=UTC),
        settings=settings,
        landing=LandingZone(settings),
    )


def http_result(
    content: bytes | str | dict,
    *,
    url: str = "https://example.test/payload",
    status_code: int = 200,
) -> HttpResult:
    import json

    if isinstance(content, (dict, list)):
        payload = json.dumps(content).encode()
    elif isinstance(content, str):
        payload = content.encode()
    else:
        payload = content
    return HttpResult(
        url=url,
        status_code=status_code,
        content=payload,
        headers={"content-type": "application/octet-stream"},
        elapsed_s=0.01,
    )


def make_observation(**kwargs) -> Observation:
    payload = {
        "observation_id": "obs-1",
        "source_id": "test_source",
        "series_id": "TEST.SERIES",
        "observed_at": date(2020, 1, 1),
        "value": 1.0,
        "unit": "index",
        "frequency": "daily",
    }
    payload.update(kwargs)
    payload.setdefault("extra", {"note": "test"})
    return Observation(**payload)


def make_claim(**kwargs) -> Claim:
    payload = {
        "claim_id": "claim-1",
        "source_id": "test_source",
        "claim_text": "Capesize rates jumped",
    }
    payload.update(kwargs)
    return Claim(**payload)


def make_event(**kwargs) -> Event:
    payload = {
        "event_id": "event-1",
        "source": "test_source",
        "source_url": "https://example.test/news",
        "headline": "Iron ore demand supports Capesize",
    }
    payload.update(kwargs)
    return Event(**payload)


def make_retrieved_source(**kwargs) -> RetrievedSource:
    payload = {
        "source_id": "test_source",
        "canonical_url": "https://example.test/source",
        "publisher": "Test",
        "source_type": "test",
        "retrieved_time": datetime(2026, 9, 7, tzinfo=UTC),
        "access_status": "ok",
    }
    payload.update(kwargs)
    return RetrievedSource(**payload)

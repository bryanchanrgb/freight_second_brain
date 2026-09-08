from __future__ import annotations

import json
from datetime import date

from freight_second_brain.etl.extractors.base import ExtractResult
from freight_second_brain.etl.pipeline import run_pipeline
from freight_second_brain.warehouse.store import Warehouse
from tests.conftest import make_claim, make_event, make_observation, make_retrieved_source


class _OkExtractor:
    name = "ok_source"

    def extract(self, ctx) -> ExtractResult:
        return ExtractResult(
            source_id="ok_source",
            status="complete",
            observations=[make_observation(vintage_id=ctx.run_id)],
            claims=[make_claim()],
            events=[make_event()],
            retrieved_sources=[make_retrieved_source()],
            requests=2,
            successful_requests=2,
            notes=["ok"],
        )


class _PartialExtractor:
    name = "partial_source"

    def extract(self, ctx) -> ExtractResult:
        return ExtractResult(
            source_id="partial_source",
            status="partial",
            observations=[make_observation(observation_id="obs-partial", series_id="PARTIAL.X")],
            requests=1,
            successful_requests=1,
            failed_requests=0,
        )


class _BoomExtractor:
    name = "boom_source"

    def extract(self, ctx) -> ExtractResult:
        raise RuntimeError("upstream timeout")


class _EmptyFailExtractor:
    name = "empty_fail"

    def extract(self, ctx) -> ExtractResult:
        return ExtractResult(source_id="empty_fail", status="failed", notes=["blocked"])


def test_pipeline_complete_writes_warehouse(monkeypatch, settings) -> None:
    monkeypatch.setattr(
        "freight_second_brain.etl.pipeline.EXTRACTORS",
        {"ok_source": _OkExtractor},
    )
    monkeypatch.setattr(
        "freight_second_brain.etl.pipeline.list_enabled_extractors",
        lambda: ["ok_source"],
    )
    manifest = run_pipeline(settings=settings)
    assert manifest.status == "complete"
    assert manifest.observation_count == 1
    assert manifest.claim_count == 1
    assert manifest.event_count == 1
    assert manifest.requests == 2
    assert manifest.successful_requests == 2
    assert manifest.failed_requests == 0
    assert "ok_source: complete" in manifest.notes

    warehouse = Warehouse(settings)
    obs = warehouse.load_observations()
    assert len(obs) == 1
    assert obs.iloc[0]["series_id"] == "TEST.SERIES"
    claim = warehouse.load_jsonl("claims")[0]
    assert claim["claim_id"] == "claim-1"
    assert claim["entities"] == []
    assert warehouse.load_jsonl("claim_entities") == []
    assert warehouse.load_jsonl("catalog")
    assert warehouse.duckdb_path.exists()
    assert warehouse.load_jsonl("events")[0]["event_id"] == "event-1"
    assert warehouse.load_jsonl("sources")[0]["source_id"] == "test_source"
    latest = json.loads((settings.metadata_root / "latest.json").read_text())
    assert latest["status"] == "complete"
    quality = json.loads((settings.metadata_root / "quality_report.json").read_text())
    assert quality["observation_count"] == 1
    run_files = list(settings.runs_root.glob("*.json"))
    assert len(run_files) == 1


def test_pipeline_unknown_extractor_is_failed_without_observations(monkeypatch, settings) -> None:
    monkeypatch.setattr("freight_second_brain.etl.pipeline.EXTRACTORS", {})
    manifest = run_pipeline(extractors=["does_not_exist"], settings=settings)
    assert manifest.status == "failed"
    assert manifest.observation_count == 0
    assert any("unknown extractor" in note for note in manifest.notes)


def test_pipeline_exception_is_captured_as_failed(monkeypatch, settings) -> None:
    monkeypatch.setattr(
        "freight_second_brain.etl.pipeline.EXTRACTORS",
        {"boom_source": _BoomExtractor},
    )
    manifest = run_pipeline(extractors=["boom_source"], settings=settings)
    assert manifest.status == "failed"
    assert any("upstream timeout" in note for note in manifest.notes)


def test_pipeline_partial_when_any_extractor_partial(monkeypatch, settings) -> None:
    monkeypatch.setattr(
        "freight_second_brain.etl.pipeline.EXTRACTORS",
        {"ok_source": _OkExtractor, "partial_source": _PartialExtractor},
    )
    manifest = run_pipeline(extractors=["ok_source", "partial_source"], settings=settings)
    assert manifest.status == "partial"
    assert manifest.observation_count == 2


def test_pipeline_partial_when_failed_extractor_but_rows_exist(monkeypatch, settings) -> None:
    monkeypatch.setattr(
        "freight_second_brain.etl.pipeline.EXTRACTORS",
        {"ok_source": _OkExtractor, "empty_fail": _EmptyFailExtractor},
    )
    manifest = run_pipeline(extractors=["ok_source", "empty_fail"], settings=settings)
    assert manifest.status == "partial"
    assert manifest.observation_count == 1


def test_pipeline_empty_observations_are_not_written(monkeypatch, settings) -> None:
    monkeypatch.setattr(
        "freight_second_brain.etl.pipeline.EXTRACTORS",
        {"empty_fail": _EmptyFailExtractor},
    )
    manifest = run_pipeline(extractors=["empty_fail"], settings=settings)
    warehouse = Warehouse(settings)
    assert manifest.status == "failed"
    assert not warehouse.observations_path.exists()
    assert warehouse.load_observations().empty

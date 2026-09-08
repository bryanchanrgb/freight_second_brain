from __future__ import annotations

import json
from datetime import date

from freight_second_brain.config import PARSER_VERSION
from freight_second_brain.etl.extractors.base import ExtractResult
from freight_second_brain.etl.quality import build_quality_report, write_quality_report
from freight_second_brain.warehouse.store import Warehouse
from tests.conftest import make_observation


def test_quality_report_counts_and_source_warnings() -> None:
    observations = [
        make_observation(source_id="world_bank_pink_sheet", series_id="WB_PINK.coal", observed_at=date(2020, 1, 1)),
        make_observation(source_id="mendeley_bdi", series_id="MENDELEY.BCI", observation_id="obs-2"),
        make_observation(
            source_id="mendeley_bdi",
            series_id="MENDELEY.BCI",
            observation_id="obs-dup",
            observed_at=date(2020, 1, 1),
        ),
        make_observation(source_id="trading_economics_bdi", series_id="TE.BDI.LAST", observation_id="obs-3"),
        make_observation(source_id="comtrade", series_id="COMTRADE.CHN", observation_id="obs-4"),
        make_observation(source_id="usda_psd", series_id="USDA.WHEAT", observation_id="obs-5"),
    ]
    results = [
        ExtractResult(source_id="world_bank_pink_sheet", status="complete", observations=observations[:1], requests=1, successful_requests=1),
        ExtractResult(source_id="mendeley_bdi", status="complete", observations=observations[1:3]),
    ]
    report = build_quality_report(observations, results)
    assert report["parser_version"] == PARSER_VERSION
    assert report["observation_count"] == 6
    assert report["series_count"] == 5
    assert report["source_counts"]["mendeley_bdi"] == 2
    assert report["duplicate_rows"] == 1
    assert any("Pink Sheet" in warning for warning in report["warnings"])
    assert any("Mendeley BDI" in warning for warning in report["warnings"])
    assert any("Trading Economics" in warning for warning in report["warnings"])
    assert any("Comtrade" in warning for warning in report["warnings"])
    assert any("USDA PSD" in warning for warning in report["warnings"])
    assert report["extractor_status"][0]["extractor"] == "world_bank_pink_sheet"


def test_write_quality_report(settings) -> None:
    warehouse = Warehouse(settings)
    write_quality_report(warehouse, {"observation_count": 0, "warnings": []})
    path = settings.metadata_root / "quality_report.json"
    payload = json.loads(path.read_text())
    assert payload["observation_count"] == 0

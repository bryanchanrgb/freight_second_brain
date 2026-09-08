from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from freight_second_brain.config import PARSER_VERSION
from freight_second_brain.warehouse.schemas import Observation
from freight_second_brain.warehouse.store import Warehouse


def build_quality_report(
    observations: list[Observation],
    extractor_results: list[Any],
) -> dict[str, Any]:
    frame = pd.DataFrame([row.model_dump(mode="json") for row in observations]) if observations else pd.DataFrame()
    by_source = (
        frame.groupby("source_id").size().to_dict() if not frame.empty else {}
    )
    by_series_n = int(frame["series_id"].nunique()) if not frame.empty else 0
    duplicates = 0
    if not frame.empty:
        duplicates = int(
            frame.duplicated(subset=["source_id", "series_id", "observed_at", "vintage_id"]).sum()
        )
    warnings: list[str] = []
    if "world_bank_pink_sheet" in by_source:
        warnings.append("Pink Sheet units remain source-native; convert before cross-series modeling.")
    if "mendeley_bdi" in by_source:
        warnings.append("Mendeley BDI ends 2019-07-31 and is not a current Baltic feed.")
    if "trading_economics_bdi" in by_source:
        warnings.append("Trading Economics BDI last value is a secondary snapshot, not licensed Baltic history.")
    if "comtrade" in by_source:
        warnings.append("Comtrade preview is annual and partner=world; not a complete monthly tonne-mile panel.")
    if "usda_psd" in by_source:
        warnings.append("USDA PSD values are market-year vintages from the current bulk file, not a full ALFRED-style archive.")
    extractor_status = [
        {
            "extractor": item.source_id,
            "status": item.status,
            "observations": len(item.observations),
            "requests": item.requests,
            "successful_requests": item.successful_requests,
            "failed_requests": item.failed_requests,
            "notes": item.notes,
        }
        for item in extractor_results
    ]
    return {
        "parser_version": PARSER_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "observation_count": len(observations),
        "series_count": by_series_n,
        "source_counts": by_source,
        "duplicate_rows": duplicates,
        "extractor_status": extractor_status,
        "warnings": warnings,
    }


def write_quality_report(warehouse: Warehouse, report: dict[str, Any]) -> None:
    path = warehouse.settings.metadata_root / "quality_report.json"
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

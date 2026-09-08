from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from freight_second_brain.config import PARSER_VERSION, Settings, get_settings
from freight_second_brain.etl.http import HttpResult


class LandingZone:
    """Immutable raw snapshots: raw/{source}/{dataset}/{YYYY}/{MM}/{DD}/{run_id}/."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.root = self.settings.raw_root
        self.root.mkdir(parents=True, exist_ok=True)

    def snapshot_dir(self, source_id: str, dataset: str, run_id: str, retrieved_at: datetime) -> Path:
        stamp = retrieved_at.astimezone(UTC)
        path = (
            self.root
            / source_id
            / dataset
            / f"{stamp:%Y}"
            / f"{stamp:%m}"
            / f"{stamp:%d}"
            / run_id
        )
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write(
        self,
        *,
        source_id: str,
        dataset: str,
        run_id: str,
        result: HttpResult,
        request: dict[str, Any],
        license_name: str,
        coverage_start: str | None = None,
        coverage_end: str | None = None,
        published_at: str | None = None,
        payload_name: str = "payload",
        status: str = "complete",
    ) -> Path:
        retrieved_at = datetime.now(UTC)
        directory = self.snapshot_dir(source_id, dataset, run_id, retrieved_at)
        payload_path = directory / payload_name
        payload_path.write_bytes(result.content)
        (directory / "request.json").write_text(json.dumps(request, indent=2), encoding="utf-8")
        (directory / "response_headers.json").write_text(
            json.dumps(result.headers, indent=2), encoding="utf-8"
        )
        manifest = {
            "source": source_id,
            "dataset": dataset,
            "url_or_endpoint": result.url,
            "retrieved_at_utc": retrieved_at.isoformat(),
            "published_at_if_known": published_at,
            "coverage_start": coverage_start,
            "coverage_end": coverage_end,
            "content_hash": result.sha256,
            "license": license_name,
            "parser_version": PARSER_VERSION,
            "http_status": result.status_code,
            "byte_count": len(result.content),
            "status": status,
            "payload": payload_name,
        }
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return directory

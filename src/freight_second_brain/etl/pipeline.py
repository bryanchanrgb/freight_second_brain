from __future__ import annotations

from datetime import UTC, datetime

from freight_second_brain.catalog.sources import list_enabled_extractors
from freight_second_brain.config import PARSER_VERSION, Settings, get_settings
from freight_second_brain.etl.enrich import finalize_warehouse
from freight_second_brain.etl.extractors import EXTRACTORS
from freight_second_brain.etl.extractors.base import ExtractResult, RunContext
from freight_second_brain.etl.landing import LandingZone
from freight_second_brain.etl.quality import build_quality_report, write_quality_report
from freight_second_brain.warehouse.schemas import RunManifest
from freight_second_brain.warehouse.store import Warehouse


def run_pipeline(
    *,
    extractors: list[str] | None = None,
    settings: Settings | None = None,
) -> RunManifest:
    settings = settings or get_settings()
    settings.data_root.mkdir(parents=True, exist_ok=True)
    warehouse = Warehouse(settings)
    landing = LandingZone(settings)
    started = datetime.now(UTC)
    run_id = started.strftime("%Y%m%dT%H%M%SZ")
    names = extractors or list_enabled_extractors()
    ctx = RunContext(run_id=run_id, retrieved_at=started, settings=settings, landing=landing)

    results: list[ExtractResult] = []
    for name in names:
        cls = EXTRACTORS.get(name)
        if cls is None:
            results.append(
                ExtractResult(source_id=name, status="failed", notes=[f"unknown extractor {name}"])
            )
            continue
        try:
            results.append(cls().extract(ctx))
        except Exception as exc:  # noqa: BLE001
            results.append(ExtractResult(source_id=name, status="failed", notes=[str(exc)]))

    observations = [row for result in results for row in result.observations]
    sources = [row for result in results for row in result.retrieved_sources]

    warehouse.write_observations(observations, replace=True)
    warehouse.write_sources(sources)
    finalize_warehouse(warehouse)

    report = build_quality_report(observations, results)
    write_quality_report(warehouse, report)

    failed = [item for item in results if item.status == "failed"]
    partial = [item for item in results if item.status == "partial"]
    if failed and not observations:
        status = "failed"
    elif failed or partial:
        status = "partial"
    else:
        status = "complete"

    manifest = RunManifest(
        run_id=run_id,
        started_at=started,
        finished_at=datetime.now(UTC),
        status=status,
        parser_version=PARSER_VERSION,
        requests=sum(item.requests for item in results),
        successful_requests=sum(item.successful_requests for item in results),
        failed_requests=sum(item.failed_requests for item in results),
        observation_count=len(observations),
        source_ids=sorted({item.source_id for item in results}),
        notes=(
            [note for item in results for note in ([f"{item.source_id}: {item.status}"] + item.notes)]
            + ["code ingest only; news and analysis come from live web tools, not stored claims"]
        ),
        quality_report_uri=str(warehouse.settings.metadata_root / "quality_report.json"),
    )
    warehouse.write_manifest(manifest)
    return manifest

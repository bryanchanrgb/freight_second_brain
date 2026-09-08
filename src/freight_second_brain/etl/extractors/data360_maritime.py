from __future__ import annotations

from datetime import date

from freight_second_brain.catalog.sources import get_source
from freight_second_brain.etl.extractors.base import (
    ExtractResult,
    RunContext,
    make_retrieved_source,
    observation_id,
    to_float,
    utcnow,
)
from freight_second_brain.etl.http import fetch
from freight_second_brain.warehouse.schemas import Observation

BASE = "https://data360api.worldbank.org/data360/data"
INDICATORS = [
    "UNCTAD_MT_PORT_TIME",
    "UNCTAD_MT_PORT",
    "UNCTAD_MT_VESSELS_AGE",
    "UNCTAD_MT_VESSELS_SIZE",
    "UNCTAD_MT_VESSELS_CAPACITY",
    "UNCTAD_MT_CONTAINER_CAPACITY",
    "UNCTAD_MT_CONTAINER_THROUGHPUT",
    "UNCTAD_MT_TRANSPORT_EXPORTS",
    "UNCTAD_MT_TRANSPORT_IMPORTS",
]
AREAS = ["WLD", "CHN", "USA", "BRA", "AUS", "SGP", "IND"]


class Data360MaritimeExtractor:
    name = "data360_maritime"

    def extract(self, ctx: RunContext) -> ExtractResult:
        source = get_source("data360_maritime")
        result = ExtractResult(source_id=source.source_id, status="complete")
        observations: list[Observation] = []
        for indicator in INDICATORS:
            for area in AREAS:
                params = {
                    "DATABASE_ID": "UNCTAD_MT",
                    "INDICATOR": indicator,
                    "REF_AREA": area,
                    "skip": 0,
                    "take": 200,
                }
                result.requests += 1
                try:
                    response = fetch(BASE, settings=ctx.settings, params=params, timeout=40)
                except Exception as exc:  # noqa: BLE001
                    result.failed_requests += 1
                    result.notes.append(f"{indicator} {area} failed: {exc}")
                    continue
                result.successful_requests += 1
                directory = ctx.landing.write(
                    source_id=source.source_id,
                    dataset=f"{indicator}_{area}",
                    run_id=ctx.run_id,
                    result=response,
                    request={"url": BASE, "params": params},
                    license_name=source.license,
                    payload_name="payload.json",
                )
                uri = str(directory)
                result.snapshot_uris.append(uri)
                if area == "WLD":
                    result.retrieved_sources.append(
                        make_retrieved_source(
                            source_id=source.source_id,
                            url=response.url,
                            publisher=source.publisher,
                            source_type=source.source_type,
                            retrieved_at=utcnow(),
                            content_hash=response.sha256,
                            raw_uri=uri,
                            title=indicator,
                            license_name=source.license,
                        )
                    )
                rows = response.json().get("value") or []
                for row in rows:
                    value = to_float(row.get("OBS_VALUE"))
                    period = str(row.get("TIME_PERIOD") or "")
                    if value is None or not period.isdigit():
                        continue
                    observed = date(int(period), 1, 1)
                    series_id = f"{indicator}.{row.get('REF_AREA') or area}"
                    observations.append(
                        Observation(
                            observation_id=observation_id(source.source_id, series_id, observed),
                            source_id=source.source_id,
                            series_id=series_id,
                            observed_at=observed,
                            published_at=utcnow(),
                            vintage_id=ctx.run_id,
                            value=value,
                            unit=str(row.get("UNIT_MEASURE") or "unspecified"),
                            frequency="annual",
                            geography=str(row.get("REF_AREA") or area),
                            extra={"indicator": indicator, "freq": row.get("FREQ")},
                            raw_object_uri=uri,
                        )
                    )
        result.observations = observations
        if result.failed_requests and not observations:
            result.status = "failed"
        elif result.failed_requests:
            result.status = "partial"
        return result

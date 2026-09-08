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

SEASON_START_MONTH = {
    "DJF": 12,
    "JFM": 1,
    "FMA": 2,
    "MAM": 3,
    "AMJ": 4,
    "MJJ": 5,
    "JJA": 6,
    "JAS": 7,
    "ASO": 8,
    "SON": 9,
    "OND": 10,
    "NDJ": 11,
}


class NoaaEnsoExtractor:
    name = "noaa_enso"

    def extract(self, ctx: RunContext) -> ExtractResult:
        source = get_source("noaa_enso")
        result = ExtractResult(source_id=source.source_id, status="complete")
        response = fetch(source.default_url, settings=ctx.settings, timeout=30)
        result.requests = 1
        result.successful_requests = 1
        directory = ctx.landing.write(
            source_id=source.source_id,
            dataset="oni",
            run_id=ctx.run_id,
            result=response,
            request={"url": source.default_url, "method": "GET"},
            license_name=source.license,
            payload_name="oni.ascii.txt",
        )
        uri = str(directory)
        result.snapshot_uris.append(uri)
        result.retrieved_sources.append(
            make_retrieved_source(
                source_id=source.source_id,
                url=response.url,
                publisher=source.publisher,
                source_type=source.source_type,
                retrieved_at=utcnow(),
                content_hash=response.sha256,
                raw_uri=uri,
                title="Oceanic Niño Index",
                license_name=source.license,
            )
        )
        observations: list[Observation] = []
        for line in response.text.splitlines():
            parts = line.split()
            if len(parts) < 4 or parts[0] == "SEAS":
                continue
            season, year_s, _total, anom = parts[:4]
            year = int(year_s)
            month = SEASON_START_MONTH.get(season)
            value = to_float(anom)
            if month is None or value is None:
                continue
            observed_year = year - 1 if season == "DJF" else year
            observed = date(observed_year, month, 1)
            series_id = "NOAA.ONI.ANOM"
            observations.append(
                Observation(
                    observation_id=observation_id(source.source_id, series_id, observed),
                    source_id=source.source_id,
                    series_id=series_id,
                    observed_at=observed,
                    published_at=utcnow(),
                    vintage_id=ctx.run_id,
                    value=value,
                    unit="degC_anomaly",
                    frequency="monthly",
                    extra={"season": season, "sst_total": to_float(_total)},
                    raw_object_uri=uri,
                )
            )
        result.observations = observations
        return result

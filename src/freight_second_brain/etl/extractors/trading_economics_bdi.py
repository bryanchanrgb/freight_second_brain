from __future__ import annotations

import re

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
from freight_second_brain.warehouse.schemas import Observation, ObservationKind


class TradingEconomicsBdiExtractor:
    name = "trading_economics_bdi"

    def extract(self, ctx: RunContext) -> ExtractResult:
        source = get_source("trading_economics_bdi")
        result = ExtractResult(source_id=source.source_id, status="complete")
        response = fetch(source.default_url, settings=ctx.settings, timeout=40)
        result.requests = 1
        result.successful_requests = 1
        directory = ctx.landing.write(
            source_id=source.source_id,
            dataset="bdi_page",
            run_id=ctx.run_id,
            result=response,
            request={"url": source.default_url, "method": "GET"},
            license_name=source.license,
            payload_name="page.html",
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
                title="Baltic Exchange Dry Index",
                license_name=source.license,
                retrieval_status="public_summary",
            )
        )
        value = _extract_last_value(response.text)
        if value is None:
            result.status = "partial"
            result.notes.append("page snapshot stored; last BDI value not parsed")
            return result
        observed = utcnow().date()
        series_id = "TE.BDI.LAST"
        result.observations.append(
            Observation(
                observation_id=observation_id(source.source_id, series_id, observed, ctx.run_id),
                source_id=source.source_id,
                series_id=series_id,
                observed_at=observed,
                published_at=utcnow(),
                vintage_id=ctx.run_id,
                value=value,
                unit="index",
                frequency="daily",
                vessel_class=None,
                rate_type="index",
                kind=ObservationKind.PROXY,
                quality_flag="secondary_current",
                raw_object_uri=uri,
                extra={"note": "Displayed last value from public page; not Baltic primary data."},
            )
        )
        result.notes.append("historical table was not scraped; only the displayed last value is stored")
        return result


def _extract_last_value(html: str) -> float | None:
    match = re.search(r'"last"\s*:\s*"?([0-9]+(?:\.[0-9]+)?)', html, re.I)
    if match:
        return to_float(match.group(1))
    match = re.search(r">([0-9]{1,3},[0-9]{3}(?:\.[0-9]+)?)<", html)
    if match:
        return to_float(match.group(1))
    return None

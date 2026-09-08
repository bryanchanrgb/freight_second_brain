from __future__ import annotations

import io
import json
import zipfile

from freight_second_brain.catalog.sources import get_source
from freight_second_brain.etl.extractors.base import (
    ExtractResult,
    RunContext,
    infer_commodity,
    make_retrieved_source,
    observation_id,
    parse_month_token,
    slug,
    to_float,
    utcnow,
)
from freight_second_brain.etl.http import fetch
from freight_second_brain.warehouse.schemas import Observation

COAL_ZIP = "https://www.eia.gov/opendata/bulk/COAL.zip"
NAME_KEEP = ("production", "export", "import", "price", "consumption", "stocks")
MAX_SERIES = 80


class EiaCoalExtractor:
    name = "eia_coal"

    def extract(self, ctx: RunContext) -> ExtractResult:
        source = get_source("eia_coal")
        result = ExtractResult(source_id=source.source_id, status="complete")
        response = fetch(COAL_ZIP, settings=ctx.settings, timeout=120)
        result.requests = 1
        result.successful_requests = 1
        directory = ctx.landing.write(
            source_id=source.source_id,
            dataset="coal_bulk",
            run_id=ctx.run_id,
            result=response,
            request={"url": COAL_ZIP, "method": "GET"},
            license_name=source.license,
            payload_name="COAL.zip",
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
                title="EIA COAL bulk",
                license_name=source.license,
            )
        )
        observations: list[Observation] = []
        kept = 0
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            member = next(name for name in archive.namelist() if name.lower().endswith(".txt"))
            with archive.open(member) as handle:
                for raw in handle:
                    if kept >= MAX_SERIES:
                        break
                    try:
                        obj = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    series_id = obj.get("series_id")
                    name = str(obj.get("name") or "")
                    data = obj.get("data")
                    if not series_id or not data:
                        continue
                    lowered = name.lower()
                    if not any(token in lowered for token in NAME_KEEP):
                        continue
                    freq = str(obj.get("f") or obj.get("frequency") or "A")
                    unit = str(obj.get("units") or obj.get("unitsshort") or "unspecified")
                    kept += 1
                    for period, value in data:
                        numeric = to_float(value)
                        observed = parse_month_token(str(period))
                        if numeric is None or observed is None:
                            continue
                        canonical = f"EIA.{slug(series_id)}"
                        observations.append(
                            Observation(
                                observation_id=observation_id(source.source_id, canonical, observed),
                                source_id=source.source_id,
                                series_id=canonical,
                                observed_at=observed,
                                published_at=utcnow(),
                                vintage_id=ctx.run_id,
                                value=numeric,
                                unit=unit,
                                frequency={"A": "annual", "M": "monthly", "Q": "quarterly", "W": "weekly"}.get(freq, freq),
                                geography="USA",
                                commodity=infer_commodity(name) or "coal",
                                extra={"eia_series_id": series_id, "name": name},
                                raw_object_uri=uri,
                            )
                        )
        result.observations = observations
        result.notes.append(f"kept {kept} EIA series matching production/trade/price/stocks")
        return result

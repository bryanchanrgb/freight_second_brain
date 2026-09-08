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

INDICATORS = {
    "NY.GDP.MKTP.KD.ZG": ("gdp_growth_pct", "percent"),
    "NY.GDP.MKTP.CD": ("gdp_current_usd", "USD"),
    "NE.IMP.GNFS.ZS": ("imports_gdp_pct", "percent"),
    "NE.EXP.GNFS.ZS": ("exports_gdp_pct", "percent"),
    "NV.IND.MANF.ZS": ("manufacturing_value_added_gdp_pct", "percent"),
    "TX.VAL.MRCH.CD.WT": ("merchandise_exports_usd", "USD"),
    "TM.VAL.MRCH.CD.WT": ("merchandise_imports_usd", "USD"),
}

COUNTRIES = ["CHN", "USA", "IND", "BRA", "AUS", "WLD"]


class WorldBankApiExtractor:
    name = "world_bank_api"

    def extract(self, ctx: RunContext) -> ExtractResult:
        source = get_source("world_bank_api")
        result = ExtractResult(source_id=source.source_id, status="complete")
        observations: list[Observation] = []
        for indicator, (label, unit) in INDICATORS.items():
            country_list = ";".join(COUNTRIES)
            url = (
                f"https://api.worldbank.org/v2/country/{country_list}/indicator/{indicator}"
                "?format=json&per_page=20000"
            )
            result.requests += 1
            try:
                response = fetch(url, settings=ctx.settings, timeout=60)
            except Exception as exc:  # noqa: BLE001
                result.failed_requests += 1
                result.notes.append(f"{indicator} failed: {exc}")
                continue
            result.successful_requests += 1
            directory = ctx.landing.write(
                source_id=source.source_id,
                dataset=indicator.replace(".", "_"),
                run_id=ctx.run_id,
                result=response,
                request={"url": url, "method": "GET"},
                license_name=source.license,
                payload_name="payload.json",
            )
            uri = str(directory)
            result.snapshot_uris.append(uri)
            payload = response.json()
            rows = payload[1] if isinstance(payload, list) and len(payload) > 1 else []
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
            for row in rows or []:
                value = to_float(row.get("value"))
                year = row.get("date")
                if value is None or not year:
                    continue
                observed = date(int(year), 1, 1)
                geo = row.get("countryiso3code") or (row.get("country") or {}).get("id")
                series_id = f"WB.{indicator}.{geo}"
                observations.append(
                    Observation(
                        observation_id=observation_id(source.source_id, series_id, observed),
                        source_id=source.source_id,
                        series_id=series_id,
                        observed_at=observed,
                        published_at=utcnow(),
                        vintage_id=ctx.run_id,
                        value=value,
                        unit=unit,
                        frequency="annual",
                        geography=geo,
                        extra={"indicator": indicator, "label": label},
                        raw_object_uri=uri,
                    )
                )
        result.observations = observations
        if result.failed_requests and not observations:
            result.status = "failed"
        elif result.failed_requests:
            result.status = "partial"
        return result

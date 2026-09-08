from __future__ import annotations

import io
import zipfile
from datetime import date

import pandas as pd

from freight_second_brain.catalog.sources import get_source
from freight_second_brain.etl.extractors.base import (
    ExtractResult,
    RunContext,
    infer_commodity,
    make_retrieved_source,
    observation_id,
    slug,
    to_float,
    utcnow,
)
from freight_second_brain.etl.http import fetch
from freight_second_brain.warehouse.schemas import Observation

ZIP_URLS = (
    "https://apps.fas.usda.gov/psdonline/downloads/psd_grains_pulses_csv.zip",
    "https://apps.fas.usda.gov/psdonline/downloads/psd_oilseeds_csv.zip",
)

KEEP_COMMODITIES = {
    "wheat",
    "corn",
    "rice, milled",
    "barley",
    "sorghum",
    "oats",
    "soybeans",
    "soybean meal",
    "soybean oil",
    "rapeseed",
    "oilseed, soybean",
}

KEEP_ATTRIBUTES = {
    "production",
    "exports",
    "imports",
    "domestic consumption",
    "ending stocks",
    "total supply",
    "total disappearance",
    "yield",
}

KEEP_COUNTRIES = {
    "world",
    "united states",
    "china",
    "brazil",
    "argentina",
    "australia",
    "india",
    "ukraine",
    "russia",
    "canada",
    "european union",
}


class UsdaPsdExtractor:
    name = "usda_psd"

    def extract(self, ctx: RunContext) -> ExtractResult:
        source = get_source("usda_psd")
        result = ExtractResult(source_id=source.source_id, status="complete")
        observations: list[Observation] = []
        for url in ZIP_URLS:
            result.requests += 1
            try:
                response = fetch(url, settings=ctx.settings, timeout=90)
            except Exception as exc:  # noqa: BLE001
                result.failed_requests += 1
                result.notes.append(f"{url} failed: {exc}")
                continue
            result.successful_requests += 1
            dataset = url.rsplit("/", 1)[-1].replace(".zip", "")
            directory = ctx.landing.write(
                source_id=source.source_id,
                dataset=dataset,
                run_id=ctx.run_id,
                result=response,
                request={"url": url, "method": "GET"},
                license_name=source.license,
                payload_name="archive.zip",
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
                    title=dataset,
                    license_name=source.license,
                )
            )
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                csv_name = next(name for name in archive.namelist() if name.lower().endswith(".csv"))
                with archive.open(csv_name) as handle:
                    frame = pd.read_csv(handle, dtype=str, low_memory=False)
            commodity_col = _col(frame, "Commodity_Description", "commodity")
            country_col = _col(frame, "Country_Name", "country")
            attr_col = _col(frame, "Attribute_Description", "attribute")
            unit_col = _col(frame, "Unit_Description", "unit")
            year_col = _col(frame, "Market_Year", "year")
            value_col = _col(frame, "Value", "value")
            month_col = _col(frame, "Month", "month") if "Month" in frame.columns else None
            for record in frame.to_dict(orient="records"):
                commodity = str(record.get(commodity_col, "")).strip()
                country = str(record.get(country_col, "")).strip()
                attribute = str(record.get(attr_col, "")).strip()
                commodity_l = commodity.lower()
                if not any(token in commodity_l for token in KEEP_COMMODITIES):
                    continue
                if country.lower() not in KEEP_COUNTRIES and not any(
                    token in country.lower() for token in KEEP_COUNTRIES
                ):
                    continue
                if attribute.lower() not in KEEP_ATTRIBUTES:
                    continue
                value = to_float(record.get(value_col))
                year = to_float(record.get(year_col))
                if value is None or year is None:
                    continue
                month = int(to_float(record.get(month_col)) or 0) if month_col else 0
                observed = date(int(year), month or 1, 1)
                series_id = f"USDA_PSD.{slug(commodity)}.{slug(country)}.{slug(attribute)}"
                observations.append(
                    Observation(
                        observation_id=observation_id(source.source_id, series_id, observed, ctx.run_id),
                        source_id=source.source_id,
                        series_id=series_id,
                        observed_at=observed,
                        published_at=utcnow(),
                        vintage_id=ctx.run_id,
                        value=value,
                        unit=str(record.get(unit_col) or "unspecified"),
                        frequency="annual",
                        geography=country,
                        commodity=infer_commodity(commodity) or slug(commodity),
                        raw_object_uri=uri,
                        extra={"commodity": commodity, "attribute": attribute, "market_year": int(year)},
                    )
                )
        result.observations = observations
        if result.failed_requests and not observations:
            result.status = "failed"
        elif result.failed_requests:
            result.status = "partial"
        return result


def _col(frame: pd.DataFrame, *candidates: str) -> str:
    lowered = {c.lower(): c for c in frame.columns}
    for candidate in candidates:
        if candidate in frame.columns:
            return candidate
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]
    return frame.columns[0]

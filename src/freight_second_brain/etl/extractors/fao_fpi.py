from __future__ import annotations

from io import BytesIO

import pandas as pd

from freight_second_brain.catalog.sources import get_source
from freight_second_brain.etl.extractors.base import (
    ExtractResult,
    RunContext,
    make_retrieved_source,
    observation_id,
    slug,
    to_float,
    utcnow,
)
from freight_second_brain.etl.http import fetch
from freight_second_brain.warehouse.schemas import Observation

FAO_CSV_URL = (
    "https://www.fao.org/media/docs/worldfoodsituationlibraries/"
    "default-document-library/food_price_indices_data.csv?sfvrsn=523ebd2a_78&download=true"
)


class FaoFpiExtractor:
    name = "fao_fpi"

    def extract(self, ctx: RunContext) -> ExtractResult:
        source = get_source("fao_fpi")
        result = ExtractResult(source_id=source.source_id, status="complete")
        response = fetch(FAO_CSV_URL, settings=ctx.settings, timeout=45)
        result.requests = 1
        result.successful_requests = 1
        directory = ctx.landing.write(
            source_id=source.source_id,
            dataset="food_price_indices",
            run_id=ctx.run_id,
            result=response,
            request={"url": FAO_CSV_URL, "method": "GET"},
            license_name=source.license,
            payload_name="food_price_indices_data.csv",
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
                title="FAO Food Price Index",
                license_name=source.license,
            )
        )
        frame = pd.read_csv(BytesIO(response.content), skiprows=2)
        frame = frame.dropna(axis=1, how="all")
        date_col = next((c for c in frame.columns if "date" in str(c).lower() or "month" in str(c).lower()), frame.columns[0])
        observations: list[Observation] = []
        for _, row in frame.iterrows():
            raw_date = row.get(date_col)
            if pd.isna(raw_date):
                continue
            parsed = pd.to_datetime(raw_date, errors="coerce")
            if pd.isna(parsed):
                continue
            observed = parsed.date().replace(day=1)
            for column in frame.columns:
                if column == date_col:
                    continue
                value = to_float(row[column])
                if value is None:
                    continue
                series_id = f"FAO_FPI.{slug(str(column))}"
                observations.append(
                    Observation(
                        observation_id=observation_id(source.source_id, series_id, observed),
                        source_id=source.source_id,
                        series_id=series_id,
                        observed_at=observed,
                        published_at=utcnow(),
                        vintage_id=ctx.run_id,
                        value=value,
                        unit="index_2014_2016_100",
                        frequency="monthly",
                        commodity="food" if "food" in str(column).lower() else "cereals" if "cereal" in str(column).lower() else None,
                        raw_object_uri=uri,
                        extra={"column": str(column)},
                    )
                )
        result.observations = observations
        if not observations:
            result.status = "partial"
            result.notes.append("CSV downloaded but no index rows parsed")
        return result

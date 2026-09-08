from __future__ import annotations

from datetime import datetime
from io import BytesIO

import pandas as pd

from freight_second_brain.catalog.sources import get_source
from freight_second_brain.etl.extractors.base import (
    ExtractResult,
    RunContext,
    infer_vessel_class,
    make_retrieved_source,
    observation_id,
    slug,
    to_float,
    utcnow,
)
from freight_second_brain.etl.http import fetch
from freight_second_brain.warehouse.schemas import Observation, ObservationKind

DATASET_API = "https://data.mendeley.com/public-api/datasets/t76ckh2ygg"


class MendeleyBdiExtractor:
    name = "mendeley_bdi"

    def extract(self, ctx: RunContext) -> ExtractResult:
        source = get_source("mendeley_bdi")
        result = ExtractResult(source_id=source.source_id, status="complete")
        meta = fetch(DATASET_API, settings=ctx.settings, timeout=30)
        result.requests += 1
        result.successful_requests += 1
        files = (meta.json().get("files") or [])
        if not files:
            result.status = "failed"
            result.notes.append("Mendeley dataset metadata contained no files")
            return result
        file_meta = files[0]
        download_url = file_meta["content_details"]["download_url"]
        workbook = fetch(download_url, settings=ctx.settings, timeout=45)
        result.requests += 1
        result.successful_requests += 1
        directory = ctx.landing.write(
            source_id=source.source_id,
            dataset="bdi_subindices_2012_2019",
            run_id=ctx.run_id,
            result=workbook,
            request={"url": download_url, "method": "GET", "dataset_api": DATASET_API},
            license_name=source.license,
            payload_name=file_meta.get("filename", "bdi.xls"),
            coverage_start=source.history_start,
            coverage_end=source.history_end,
        )
        uri = str(directory)
        result.snapshot_uris.append(uri)
        result.retrieved_sources.append(
            make_retrieved_source(
                source_id=source.source_id,
                url=download_url,
                publisher=source.publisher,
                source_type=source.source_type,
                retrieved_at=utcnow(),
                content_hash=workbook.sha256,
                raw_uri=uri,
                title=file_meta.get("filename"),
                license_name=source.license,
            )
        )
        sheets = pd.read_excel(BytesIO(workbook.content), sheet_name=None)
        observations: list[Observation] = []
        for sheet_name, frame in sheets.items():
            if frame.empty:
                continue
            date_col = _find_date_column(frame)
            if date_col is None:
                result.notes.append(f"no date column in sheet {sheet_name}")
                continue
            parsed_dates = pd.to_datetime(frame[date_col], errors="coerce")
            for column in frame.columns:
                if column == date_col:
                    continue
                for idx, value in enumerate(frame[column].tolist()):
                    numeric = to_float(value)
                    observed = parsed_dates.iloc[idx]
                    if numeric is None or pd.isna(observed):
                        continue
                    observed_date = observed.date()
                    series_id = f"MENDELEY.{slug(sheet_name)}.{slug(str(column))}"
                    observations.append(
                        Observation(
                            observation_id=observation_id(source.source_id, series_id, observed_date),
                            source_id=source.source_id,
                            series_id=series_id,
                            observed_at=observed_date,
                            published_at=datetime.fromisoformat("2020-11-09T19:00:16+00:00"),
                            vintage_id="mendeley_t76ckh2ygg_v1",
                            value=numeric,
                            unit="index",
                            frequency="daily",
                            vessel_class=infer_vessel_class(f"{sheet_name} {column}"),
                            rate_type="index",
                            kind=ObservationKind.ASSESSMENT,
                            quality_flag="historical_sample",
                            raw_object_uri=uri,
                            extra={"sheet": sheet_name, "column": str(column)},
                        )
                    )
        result.observations = observations
        if not observations:
            result.status = "partial"
        return result


def _find_date_column(frame: pd.DataFrame) -> str | None:
    for column in frame.columns:
        name = str(column).lower()
        if "date" in name or name in {"day", "time"}:
            return column
        sample = pd.to_datetime(frame[column], errors="coerce").notna().mean()
        if sample > 0.6:
            return column
    return None

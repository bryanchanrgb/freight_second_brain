from __future__ import annotations

from datetime import date
from io import BytesIO

import pandas as pd

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
from freight_second_brain.warehouse.schemas import Observation, ObservationKind

PINK_SHEET_URL = (
    "https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026"
    "/related/CMO-Historical-Data-Monthly.xlsx"
)


class WorldBankPinkSheetExtractor:
    name = "world_bank_pink_sheet"

    def extract(self, ctx: RunContext) -> ExtractResult:
        source = get_source("world_bank_pink_sheet")
        result = ExtractResult(source_id=source.source_id, status="complete")
        response = fetch(PINK_SHEET_URL, settings=ctx.settings, timeout=90)
        result.requests = 1
        result.successful_requests = 1
        directory = ctx.landing.write(
            source_id=source.source_id,
            dataset="cmo_historical_monthly",
            run_id=ctx.run_id,
            result=response,
            request={"url": PINK_SHEET_URL, "method": "GET"},
            license_name=source.license,
            payload_name="CMO-Historical-Data-Monthly.xlsx",
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
                title="World Bank Pink Sheet monthly prices",
                license_name=source.license,
            )
        )
        frame = pd.read_excel(BytesIO(response.content), sheet_name="Monthly Prices", header=None)
        header_row = 4
        unit_row = 5
        names = [str(v).strip() if pd.notna(v) else "" for v in frame.iloc[header_row].tolist()]
        units = [str(v).strip() if pd.notna(v) else "" for v in frame.iloc[unit_row].tolist()]
        observations: list[Observation] = []
        for _, row in frame.iloc[6:].iterrows():
            observed = parse_month_token(str(row.iloc[0])) if pd.notna(row.iloc[0]) else None
            if observed is None:
                continue
            for idx in range(1, len(row)):
                name = names[idx] if idx < len(names) else ""
                if not name or name.lower() in {"nan", "none"}:
                    continue
                value = to_float(row.iloc[idx])
                if value is None:
                    continue
                series_id = f"WB_PINK.{slug(name)}"
                unit = units[idx] if idx < len(units) else ""
                observations.append(
                    Observation(
                        observation_id=observation_id(source.source_id, series_id, observed),
                        source_id=source.source_id,
                        series_id=series_id,
                        observed_at=observed,
                        published_at=utcnow(),
                        vintage_id=ctx.run_id,
                        value=value,
                        unit=unit or "unspecified",
                        currency="USD" if "$" in unit or "cent" in unit.lower() else None,
                        frequency="monthly",
                        commodity=infer_commodity(name),
                        kind=ObservationKind.ASSESSMENT,
                        methodology_version="pink_sheet_monthly",
                        raw_object_uri=uri,
                        extra={"commodity_name": name},
                    )
                )
        result.observations = observations
        if observations:
            start = min(item.observed_at for item in observations)
            end = max(item.observed_at for item in observations)
            result.notes.append(f"coverage {start.isoformat()} to {end.isoformat()}")
        else:
            result.status = "partial"
            result.notes.append("workbook downloaded but no monthly prices parsed")
        return result

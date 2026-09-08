from __future__ import annotations

import time
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

QUERIES = [
    {"reporterCode": "156", "cmdCode": "2601", "flowCode": "M", "commodity": "iron_ore", "label": "CHN_IMP_IRON_ORE"},
    {"reporterCode": "156", "cmdCode": "2701", "flowCode": "M", "commodity": "coal", "label": "CHN_IMP_COAL"},
    {"reporterCode": "156", "cmdCode": "1001", "flowCode": "M", "commodity": "wheat", "label": "CHN_IMP_WHEAT"},
    {"reporterCode": "156", "cmdCode": "1201", "flowCode": "M", "commodity": "soybeans", "label": "CHN_IMP_SOYBEANS"},
    {"reporterCode": "156", "cmdCode": "2606", "flowCode": "M", "commodity": "bauxite", "label": "CHN_IMP_BAUXITE"},
    {"reporterCode": "36", "cmdCode": "2601", "flowCode": "X", "commodity": "iron_ore", "label": "AUS_EXP_IRON_ORE"},
    {"reporterCode": "76", "cmdCode": "2601", "flowCode": "X", "commodity": "iron_ore", "label": "BRA_EXP_IRON_ORE"},
    {"reporterCode": "36", "cmdCode": "2701", "flowCode": "X", "commodity": "coal", "label": "AUS_EXP_COAL"},
]

YEARS = list(range(2015, 2025))
BASE = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"


class ComtradeExtractor:
    name = "comtrade"

    def extract(self, ctx: RunContext) -> ExtractResult:
        source = get_source("comtrade")
        result = ExtractResult(source_id=source.source_id, status="complete")
        observations: list[Observation] = []
        for query in QUERIES:
            for year in YEARS:
                params = {
                    "reporterCode": query["reporterCode"],
                    "period": str(year),
                    "cmdCode": query["cmdCode"],
                    "flowCode": query["flowCode"],
                    "partnerCode": "0",
                    "maxRecords": "20",
                }
                result.requests += 1
                try:
                    response = fetch(BASE, settings=ctx.settings, params=params, timeout=45)
                except Exception as exc:  # noqa: BLE001
                    result.failed_requests += 1
                    result.notes.append(f"{query['label']} {year} failed: {exc}")
                    time.sleep(ctx.settings.comtrade_delay_s)
                    continue
                result.successful_requests += 1
                directory = ctx.landing.write(
                    source_id=source.source_id,
                    dataset=f"{query['label']}_{year}",
                    run_id=ctx.run_id,
                    result=response,
                    request={"url": BASE, "method": "GET", "params": params},
                    license_name=source.license,
                    payload_name="payload.json",
                    coverage_start=str(year),
                    coverage_end=str(year),
                )
                uri = str(directory)
                result.snapshot_uris.append(uri)
                payload = response.json()
                rows = payload.get("data") or []
                if year == YEARS[-1]:
                    result.retrieved_sources.append(
                        make_retrieved_source(
                            source_id=source.source_id,
                            url=response.url,
                            publisher=source.publisher,
                            source_type=source.source_type,
                            retrieved_at=utcnow(),
                            content_hash=response.sha256,
                            raw_uri=uri,
                            title=query["label"],
                            license_name=source.license,
                        )
                    )
                for row in rows:
                    net = to_float(row.get("netWgt") or row.get("qty") or row.get("primaryValue"))
                    if net is None:
                        continue
                    observed = date(int(row.get("refYear") or year), 1, 1)
                    series_id = f"COMTRADE.{query['label']}.net_kg"
                    observations.append(
                        Observation(
                            observation_id=observation_id(source.source_id, series_id, observed),
                            source_id=source.source_id,
                            series_id=series_id,
                            observed_at=observed,
                            published_at=utcnow(),
                            vintage_id=ctx.run_id,
                            value=net,
                            unit="kg" if row.get("netWgt") is not None else "primary_value",
                            currency="USD" if row.get("primaryValue") is not None and row.get("netWgt") is None else None,
                            frequency="annual",
                            geography=str(row.get("reporterISO") or query["reporterCode"]),
                            commodity=query["commodity"],
                            extra={
                                "cmdCode": query["cmdCode"],
                                "flowCode": query["flowCode"],
                                "partnerCode": row.get("partnerCode"),
                                "cifvalue": row.get("cifvalue"),
                                "fobvalue": row.get("fobvalue"),
                                "primaryValue": row.get("primaryValue"),
                            },
                            raw_object_uri=uri,
                        )
                    )
                    usd = to_float(row.get("primaryValue"))
                    if usd is not None:
                        usd_series = f"COMTRADE.{query['label']}.usd"
                        observations.append(
                            Observation(
                                observation_id=observation_id(source.source_id, usd_series, observed),
                                source_id=source.source_id,
                                series_id=usd_series,
                                observed_at=observed,
                                published_at=utcnow(),
                                vintage_id=ctx.run_id,
                                value=usd,
                                unit="USD",
                                currency="USD",
                                frequency="annual",
                                geography=str(row.get("reporterISO") or query["reporterCode"]),
                                commodity=query["commodity"],
                                raw_object_uri=uri,
                            )
                        )
                time.sleep(ctx.settings.comtrade_delay_s)
        result.observations = observations
        if result.failed_requests and not observations:
            result.status = "failed"
        elif result.failed_requests:
            result.status = "partial"
        return result

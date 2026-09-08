from __future__ import annotations

from datetime import UTC, date, datetime

from freight_second_brain.catalog.sources import get_source
from freight_second_brain.etl.extractors.base import (
    ExtractResult,
    RunContext,
    infer_commodity,
    make_retrieved_source,
    observation_id,
    slug,
    utcnow,
)
from freight_second_brain.etl.http import fetch
from freight_second_brain.warehouse.schemas import Observation, ObservationKind

SYMBOLS = {
    "BDRY": {"series": "YAHOO.BDRY", "kind": ObservationKind.PROXY, "unit": "USD", "note": "Breakwave Dry Bulk Shipping ETF"},
    "CL=F": {"series": "YAHOO.CL_F", "kind": ObservationKind.PROXY, "unit": "USD/bbl", "commodity": "crude_oil"},
    "BZ=F": {"series": "YAHOO.BZ_F", "kind": ObservationKind.PROXY, "unit": "USD/bbl", "commodity": "crude_oil"},
    "HG=F": {"series": "YAHOO.HG_F", "kind": ObservationKind.PROXY, "unit": "USD/lb", "commodity": "copper"},
    "ZC=F": {"series": "YAHOO.ZC_F", "kind": ObservationKind.PROXY, "unit": "USC/bu", "commodity": "corn"},
    "ZW=F": {"series": "YAHOO.ZW_F", "kind": ObservationKind.PROXY, "unit": "USC/bu", "commodity": "wheat"},
    "ZS=F": {"series": "YAHOO.ZS_F", "kind": ObservationKind.PROXY, "unit": "USC/bu", "commodity": "soybeans"},
    "^VIX": {"series": "YAHOO.VIX", "kind": ObservationKind.REALIZED, "unit": "index"},
    "EURUSD=X": {"series": "YAHOO.EURUSD", "kind": ObservationKind.REALIZED, "unit": "USD_per_EUR"},
    "CNY=X": {"series": "YAHOO.USDCNY", "kind": ObservationKind.REALIZED, "unit": "CNY_per_USD"},
    "DX-Y.NYB": {"series": "YAHOO.DXY", "kind": ObservationKind.REALIZED, "unit": "index"},
    "^TNX": {"series": "YAHOO.TNX", "kind": ObservationKind.REALIZED, "unit": "percent"},
}


class YahooFinanceExtractor:
    name = "yahoo_finance"

    def extract(self, ctx: RunContext) -> ExtractResult:
        source = get_source("yahoo_finance")
        result = ExtractResult(source_id=source.source_id, status="complete")
        observations: list[Observation] = []
        for symbol, meta in SYMBOLS.items():
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            params = {"interval": "1d", "range": "max", "includePrePost": "false"}
            result.requests += 1
            try:
                response = fetch(url, settings=ctx.settings, params=params, timeout=40)
            except Exception as exc:  # noqa: BLE001
                result.failed_requests += 1
                result.notes.append(f"{symbol} failed: {exc}")
                continue
            result.successful_requests += 1
            directory = ctx.landing.write(
                source_id=source.source_id,
                dataset=slug(symbol),
                run_id=ctx.run_id,
                result=response,
                request={"url": url, "params": params},
                license_name=source.license,
                payload_name="chart.json",
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
                    title=symbol,
                    license_name=source.license,
                )
            )
            chart = (response.json().get("chart") or {}).get("result") or []
            if not chart:
                result.notes.append(f"{symbol} returned empty chart")
                continue
            node = chart[0]
            timestamps = node.get("timestamp") or []
            closes = (((node.get("indicators") or {}).get("quote") or [{}])[0].get("close") or [])
            for ts, close in zip(timestamps, closes, strict=False):
                if close is None:
                    continue
                observed = datetime.fromtimestamp(int(ts), UTC).date()
                series_id = meta["series"]
                observations.append(
                    Observation(
                        observation_id=observation_id(source.source_id, series_id, observed),
                        source_id=source.source_id,
                        series_id=series_id,
                        observed_at=observed,
                        published_at=utcnow(),
                        vintage_id=ctx.run_id,
                        value=float(close),
                        unit=meta["unit"],
                        frequency="daily",
                        commodity=meta.get("commodity") or infer_commodity(symbol),
                        kind=meta["kind"],
                        quality_flag="proxy" if meta["kind"] == ObservationKind.PROXY else "ok",
                        raw_object_uri=uri,
                        extra={"symbol": symbol, "note": meta.get("note")},
                    )
                )
        result.observations = observations
        if result.failed_requests and not observations:
            result.status = "failed"
        elif result.failed_requests:
            result.status = "partial"
        return result

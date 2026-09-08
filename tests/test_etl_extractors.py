from __future__ import annotations

import json
import zipfile
from datetime import date
from io import BytesIO

import pandas as pd
import pytest
from openpyxl import Workbook

from freight_second_brain.etl.extractors import comtrade as comtrade_mod
from freight_second_brain.etl.extractors import data360_maritime as data360_mod
from freight_second_brain.etl.extractors import eia_coal as eia_mod
from freight_second_brain.etl.extractors import fao_fpi as fao_mod
from freight_second_brain.etl.extractors import hellenic_rss as hellenic_mod
from freight_second_brain.etl.extractors import mendeley_bdi as mendeley_mod
from freight_second_brain.etl.extractors import noaa_enso as noaa_mod
from freight_second_brain.etl.extractors import qualitative_pages as pages_mod
from freight_second_brain.etl.extractors import trading_economics_bdi as te_mod
from freight_second_brain.etl.extractors import usda_psd as usda_mod
from freight_second_brain.etl.extractors import world_bank_api as wb_api_mod
from freight_second_brain.etl.extractors import world_bank_pink_sheet as pink_mod
from freight_second_brain.etl.extractors import yahoo_finance as yahoo_mod
from freight_second_brain.etl.extractors.comtrade import ComtradeExtractor
from freight_second_brain.etl.extractors.data360_maritime import Data360MaritimeExtractor
from freight_second_brain.etl.extractors.eia_coal import EiaCoalExtractor
from freight_second_brain.etl.extractors.fao_fpi import FaoFpiExtractor
from freight_second_brain.etl.extractors.hellenic_rss import HellenicRssExtractor
from freight_second_brain.etl.extractors.mendeley_bdi import MendeleyBdiExtractor
from freight_second_brain.etl.extractors.noaa_enso import NoaaEnsoExtractor
from freight_second_brain.etl.extractors.qualitative_pages import QualitativePagesExtractor
from freight_second_brain.etl.extractors.trading_economics_bdi import TradingEconomicsBdiExtractor
from freight_second_brain.etl.extractors.usda_psd import UsdaPsdExtractor
from freight_second_brain.etl.extractors.world_bank_api import WorldBankApiExtractor
from freight_second_brain.etl.extractors.world_bank_pink_sheet import WorldBankPinkSheetExtractor
from freight_second_brain.etl.extractors.yahoo_finance import YahooFinanceExtractor
from freight_second_brain.warehouse.schemas import ObservationKind
from tests.conftest import http_result


def _patch_fetch(monkeypatch: pytest.MonkeyPatch, module, payload) -> None:
    def fake_fetch(url, **kwargs):
        body = payload(url, kwargs) if callable(payload) else payload
        if isinstance(body, Exception):
            raise body
        return body if hasattr(body, "content") else http_result(body, url=url)

    monkeypatch.setattr(module, "fetch", fake_fetch)


def _xlsx_pink_sheet() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Monthly Prices"
    sheet["A1"] = "World Bank Commodity Price Data"
    sheet["B5"] = "Coal, Australian"
    sheet["C5"] = "Iron ore, cfr"
    sheet["B6"] = "($/mt)"
    sheet["C6"] = "($/dmt)"
    sheet["A7"] = "2020M01"
    sheet["B7"] = 80.5
    sheet["C7"] = "…"
    sheet["A8"] = "2020M02"
    sheet["B8"] = 82.0
    sheet["C8"] = 90.25
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _zip_csv(name: str, csv_text: str) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(name, csv_text)
    return buffer.getvalue()


def _zip_txt(name: str, text: str) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(name, text)
    return buffer.getvalue()


def test_noaa_enso_parses_seasonal_rows(monkeypatch, ctx) -> None:
    body = "SEAS  YR   TOTAL   ANOM\nDJF 1950  25.01  -1.32\nJFM 1950  25.36  -1.20\n"
    _patch_fetch(monkeypatch, noaa_mod, http_result(body, url=ctx.settings.data_root.as_posix()))
    result = NoaaEnsoExtractor().extract(ctx)
    assert result.status == "complete"
    assert result.requests == 1
    by_season = {row.extra["season"]: row for row in result.observations}
    assert by_season["DJF"].observed_at == date(1949, 12, 1)
    assert by_season["DJF"].value == pytest.approx(-1.32)
    assert by_season["JFM"].observed_at == date(1950, 1, 1)
    assert result.snapshot_uris
    assert (ctx.settings.raw_root / "noaa_enso").exists()


def test_fao_fpi_parses_named_index_columns(monkeypatch, ctx) -> None:
    csv = (
        "FAO Food Price Index,,,,\n"
        "2014-2016=100,,,,\n"
        "Date,Food Price Index,Cereals,Oils,\n"
        ",,,,\n"
        "1990-01,64.4,64.1,44.59,\n"
    )
    _patch_fetch(monkeypatch, fao_mod, http_result(csv))
    result = FaoFpiExtractor().extract(ctx)
    assert result.status == "complete"
    series = {row.series_id: row for row in result.observations}
    assert series["FAO_FPI.food_price_index"].value == pytest.approx(64.4)
    assert series["FAO_FPI.food_price_index"].commodity == "food"
    assert series["FAO_FPI.cereals"].commodity == "cereals"


def test_fao_fpi_partial_when_empty(monkeypatch, ctx) -> None:
    csv = "title\nunits\nDate,Food Price Index\nnot-a-date,abc\n"
    _patch_fetch(monkeypatch, fao_mod, http_result(csv))
    result = FaoFpiExtractor().extract(ctx)
    assert result.status == "partial"
    assert result.observations == []


def test_trading_economics_extracts_last_value(monkeypatch, ctx) -> None:
    html = '<html><script>{"last":"3575.000000000000,"}</script><span>3,575.00</span></html>'
    _patch_fetch(monkeypatch, te_mod, http_result(html))
    result = TradingEconomicsBdiExtractor().extract(ctx)
    assert result.status == "complete"
    assert result.observations[0].value == 3575.0
    assert result.observations[0].kind == ObservationKind.PROXY
    assert result.observations[0].quality_flag == "secondary_current"


def test_trading_economics_partial_without_value(monkeypatch, ctx) -> None:
    _patch_fetch(monkeypatch, te_mod, http_result("<html>no number</html>"))
    result = TradingEconomicsBdiExtractor().extract(ctx)
    assert result.status == "partial"
    assert result.observations == []


def test_hellenic_rss_lands_unlabeled_events(monkeypatch, ctx) -> None:
    rss = """<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item>
        <title>Capesize rates surge on China iron ore demand</title>
        <link>https://www.hellenicshippingnews.com/cape-1</link>
        <guid>cape-1</guid>
        <pubDate>Mon, 07 Sep 2026 10:00:00 GMT</pubDate>
        <description>Fleet tightness supports rates.</description>
      </item>
    </channel></rss>
    """
    _patch_fetch(monkeypatch, hellenic_mod, http_result(rss))
    result = HellenicRssExtractor().extract(ctx)
    assert result.status == "complete"
    assert result.claims == []
    assert result.events[0].headline.startswith("Capesize")
    assert result.events[0].polarity.value == "unknown"
    assert result.events[0].commodity is None
    assert result.events[0].vessel_class is None
    assert result.retrieved_sources


def test_hellenic_rss_partial_without_entries(monkeypatch, ctx) -> None:
    rss = """<?xml version="1.0"?><rss version="2.0"><channel><title>empty</title></channel></rss>"""
    _patch_fetch(monkeypatch, hellenic_mod, http_result(rss))
    result = HellenicRssExtractor().extract(ctx)
    assert result.status == "partial"


def test_world_bank_api_maps_indicator_rows(monkeypatch, ctx) -> None:
    monkeypatch.setattr(
        wb_api_mod,
        "INDICATORS",
        {"NY.GDP.MKTP.KD.ZG": ("gdp_growth_pct", "percent")},
    )
    payload = [
        {"page": 1},
        [
            {"value": 5.2, "date": "2023", "countryiso3code": "CHN"},
            {"value": None, "date": "2022", "countryiso3code": "CHN"},
        ],
    ]
    _patch_fetch(monkeypatch, wb_api_mod, http_result(payload))
    result = WorldBankApiExtractor().extract(ctx)
    assert result.status == "complete"
    assert len(result.observations) == 1
    row = result.observations[0]
    assert row.series_id == "WB.NY.GDP.MKTP.KD.ZG.CHN"
    assert row.geography == "CHN"
    assert row.value == pytest.approx(5.2)


def test_world_bank_api_failed_when_all_requests_error(monkeypatch, ctx) -> None:
    monkeypatch.setattr(wb_api_mod, "INDICATORS", {"NY.GDP.MKTP.KD.ZG": ("gdp_growth_pct", "percent")})
    _patch_fetch(monkeypatch, wb_api_mod, RuntimeError("timeout"))
    result = WorldBankApiExtractor().extract(ctx)
    assert result.status == "failed"
    assert result.failed_requests == 1
    assert result.observations == []


def test_pink_sheet_parses_monthly_prices(monkeypatch, ctx) -> None:
    _patch_fetch(monkeypatch, pink_mod, http_result(_xlsx_pink_sheet()))
    result = WorldBankPinkSheetExtractor().extract(ctx)
    assert result.status == "complete"
    pairs = {(row.series_id, row.observed_at): row for row in result.observations}
    coal = pairs[("WB_PINK.coal_australian", date(2020, 1, 1))]
    assert coal.value == pytest.approx(80.5)
    assert coal.commodity == "coal"
    assert coal.kind == ObservationKind.ASSESSMENT
    iron = pairs[("WB_PINK.iron_ore_cfr", date(2020, 2, 1))]
    assert iron.value == pytest.approx(90.25)
    assert ("WB_PINK.iron_ore_cfr", date(2020, 1, 1)) not in pairs


def test_usda_psd_filters_to_keep_lists(monkeypatch, ctx) -> None:
    monkeypatch.setattr(
        usda_mod,
        "ZIP_URLS",
        ("https://apps.fas.usda.gov/psdonline/downloads/psd_grains_pulses_csv.zip",),
    )
    csv = (
        "Commodity_Description,Country_Name,Attribute_Description,Unit_Description,Market_Year,Month,Value\n"
        "Wheat,China,Production,1000 MT,2024,0,140000\n"
        "Wheat,France,Production,1000 MT,2024,0,1\n"
        "Coffee,Brazil,Production,1000 MT,2024,0,9\n"
        "Wheat,United States,Area Harvested,1000 HA,2024,0,50\n"
    )
    _patch_fetch(monkeypatch, usda_mod, http_result(_zip_csv("psd.csv", csv)))
    result = UsdaPsdExtractor().extract(ctx)
    assert result.status == "complete"
    assert len(result.observations) == 1
    row = result.observations[0]
    assert row.geography == "China"
    assert row.commodity == "wheat"
    assert row.value == 140000


def test_comtrade_emits_weight_and_usd(monkeypatch, ctx) -> None:
    monkeypatch.setattr(comtrade_mod, "YEARS", [2024])
    monkeypatch.setattr(comtrade_mod, "QUERIES", [comtrade_mod.QUERIES[0]])
    payload = {
        "data": [
            {
                "refYear": 2024,
                "netWgt": 1000,
                "primaryValue": 50,
                "reporterISO": "CHN",
                "partnerCode": 0,
            }
        ]
    }
    _patch_fetch(monkeypatch, comtrade_mod, http_result(payload))
    result = ComtradeExtractor().extract(ctx)
    assert result.status == "complete"
    series = {row.series_id: row for row in result.observations}
    assert series["COMTRADE.CHN_IMP_IRON_ORE.net_kg"].value == 1000
    assert series["COMTRADE.CHN_IMP_IRON_ORE.usd"].value == 50
    assert series["COMTRADE.CHN_IMP_IRON_ORE.net_kg"].commodity == "iron_ore"


def test_yahoo_finance_reads_chart_closes(monkeypatch, ctx) -> None:
    monkeypatch.setattr(yahoo_mod, "SYMBOLS", {"BDRY": yahoo_mod.SYMBOLS["BDRY"]})
    payload = {
        "chart": {
            "result": [
                {
                    "timestamp": [1609459200, 1609545600],
                    "indicators": {"quote": [{"close": [10.5, None]}]},
                }
            ]
        }
    }
    _patch_fetch(monkeypatch, yahoo_mod, http_result(payload))
    result = YahooFinanceExtractor().extract(ctx)
    assert result.status == "complete"
    assert len(result.observations) == 1
    row = result.observations[0]
    assert row.series_id == "YAHOO.BDRY"
    assert row.kind == ObservationKind.PROXY
    assert row.value == pytest.approx(10.5)


def test_data360_maritime_builds_annual_series(monkeypatch, ctx) -> None:
    monkeypatch.setattr(data360_mod, "INDICATORS", ["UNCTAD_MT_PORT_TIME"])
    monkeypatch.setattr(data360_mod, "AREAS", ["WLD"])
    payload = {
        "value": [
            {
                "OBS_VALUE": "0.97",
                "TIME_PERIOD": "2018",
                "INDICATOR": "UNCTAD_MT_PORT_TIME",
                "REF_AREA": "WLD",
                "UNIT_MEASURE": "D",
                "FREQ": "A",
            }
        ]
    }
    _patch_fetch(monkeypatch, data360_mod, http_result(payload))
    result = Data360MaritimeExtractor().extract(ctx)
    assert result.status == "complete"
    row = result.observations[0]
    assert row.series_id == "UNCTAD_MT_PORT_TIME.WLD"
    assert row.observed_at == date(2018, 1, 1)
    assert row.geography == "WLD"


def test_eia_coal_keeps_matching_series_only(monkeypatch, ctx) -> None:
    lines = "\n".join(
        [
            json.dumps(
                {
                    "series_id": "COAL.PROD",
                    "name": "U.S. Coal Production",
                    "units": "thousand short tons",
                    "f": "M",
                    "data": [["202001", 50], ["202002", None]],
                }
            ),
            json.dumps({"series_id": "COAL.SKIP", "name": "Unrelated quality metric", "data": [["202001", 1]]}),
            "not-json",
        ]
    )
    _patch_fetch(monkeypatch, eia_mod, http_result(_zip_txt("COAL.txt", lines)))
    result = EiaCoalExtractor().extract(ctx)
    assert result.status == "complete"
    assert len(result.observations) == 1
    assert result.observations[0].series_id.startswith("EIA.")
    assert result.observations[0].commodity == "coal"
    assert result.observations[0].observed_at == date(2020, 1, 1)


def test_mendeley_parses_daily_sheet(monkeypatch, ctx) -> None:
    frame = pd.DataFrame({"Date": ["2012-08-01", "2012-08-02"], "BCI": [1200, 1210]})
    workbook = BytesIO()
    frame.to_excel(workbook, index=False, sheet_name="BCI")
    xlsx = workbook.getvalue()

    def payload(url, _kwargs):
        if "public-api" in url:
            return http_result(
                {
                    "files": [
                        {
                            "filename": "edited BDI data1.xlsx",
                            "content_details": {"download_url": "https://data.mendeley.com/file.xlsx"},
                        }
                    ]
                },
                url=url,
            )
        return http_result(xlsx, url=url)

    _patch_fetch(monkeypatch, mendeley_mod, payload)
    result = MendeleyBdiExtractor().extract(ctx)
    assert result.status == "complete"
    assert result.requests == 2
    assert len(result.observations) == 2
    assert result.observations[0].vessel_class == "capesize"
    assert result.observations[0].quality_flag == "historical_sample"


def test_mendeley_fails_without_files(monkeypatch, ctx) -> None:
    _patch_fetch(monkeypatch, mendeley_mod, http_result({"files": []}))
    result = MendeleyBdiExtractor().extract(ctx)
    assert result.status == "failed"
    assert result.observations == []


def test_qualitative_pages_stores_snapshots(monkeypatch, ctx) -> None:
    monkeypatch.setattr(pages_mod, "PAGES", (("baltic_exchange", "dry_services.html", "text/html"),))
    html = "<html><title>Baltic Dry Services</title><p>Capesize route methodology for BDI.</p></html>"
    _patch_fetch(monkeypatch, pages_mod, http_result(html))
    result = QualitativePagesExtractor().extract(ctx)
    assert result.status == "complete"
    assert result.claims == []
    assert result.retrieved_sources[0].source_id == "baltic_exchange"


def test_qualitative_pages_partial_on_fetch_error(monkeypatch, ctx) -> None:
    monkeypatch.setattr(
        pages_mod,
        "PAGES",
        (
            ("baltic_exchange", "dry_services.html", "text/html"),
            ("bimco", "market_analysis.html", "text/html"),
        ),
    )
    calls = {"n": 0}

    def payload(url, _kwargs):
        calls["n"] += 1
        if "bimco" in url:
            raise RuntimeError("blocked")
        return http_result("<html><body>Baltic methodology page content here</body></html>", url=url)

    _patch_fetch(monkeypatch, pages_mod, payload)
    result = QualitativePagesExtractor().extract(ctx)
    assert result.status == "partial"
    assert result.successful_requests == 1
    assert result.failed_requests == 1
    assert len(result.retrieved_sources) == 1

from __future__ import annotations

import json

from freight_second_brain.config import PARSER_VERSION
from freight_second_brain.etl.http import HttpResult
from freight_second_brain.etl.landing import LandingZone


def test_landing_zone_writes_immutable_snapshot(settings) -> None:
    landing = LandingZone(settings)
    result = HttpResult(
        url="https://example.test/file.csv",
        status_code=200,
        content=b"date,value\n2020-01,1\n",
        headers={"content-type": "text/csv"},
        elapsed_s=0.2,
    )
    directory = landing.write(
        source_id="fao_fpi",
        dataset="food_price_indices",
        run_id="run1",
        result=result,
        request={"url": result.url, "method": "GET"},
        license_name="CC BY",
        coverage_start="1990-01",
        coverage_end="2026-08",
        payload_name="food_price_indices_data.csv",
    )
    assert "fao_fpi" in directory.parts
    assert "food_price_indices" in directory.parts
    assert "run1" in directory.parts
    assert directory.name == "run1"
    assert (directory / "food_price_indices_data.csv").read_bytes() == result.content
    request = json.loads((directory / "request.json").read_text())
    assert request["method"] == "GET"
    headers = json.loads((directory / "response_headers.json").read_text())
    assert headers["content-type"] == "text/csv"
    manifest = json.loads((directory / "manifest.json").read_text())
    assert manifest["source"] == "fao_fpi"
    assert manifest["http_status"] == 200
    assert manifest["byte_count"] == len(result.content)
    assert manifest["content_hash"] == result.sha256
    assert manifest["parser_version"] == PARSER_VERSION
    assert manifest["license"] == "CC BY"
    assert manifest["status"] == "complete"
    assert manifest["payload"] == "food_price_indices_data.csv"

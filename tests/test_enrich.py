from pathlib import Path

from freight_second_brain.etl.apply import write_table
from freight_second_brain.etl.enrich import finalize_warehouse
from freight_second_brain.warehouse.store import Warehouse
from tests.conftest import make_claim, make_observation


def test_finalize_warehouse_does_not_label_claims(settings) -> None:
    warehouse = Warehouse(settings)
    warehouse.write_observations([make_observation()])
    warehouse.write_claims([make_claim()])
    finalize_warehouse(warehouse)

    claim = warehouse.load_jsonl("claims")[0]
    assert claim["entities"] == []
    assert claim["polarity"] == "unknown"
    assert warehouse.load_jsonl("catalog")
    assert warehouse.duckdb_path.exists()
    tables = {row["table"] for row in warehouse.schema()}
    assert {"observations", "claims", "catalog"} <= tables


def test_write_table_validates_claims(settings, tmp_path: Path) -> None:
    warehouse = Warehouse(settings)
    rows = [
        {
            "claim_id": "c1",
            "source_id": "hellenic_rss",
            "claim_text": "Capesize rates rose on iron ore demand",
            "polarity": "bullish",
            "entities": ["capesize", "iron_ore"],
        }
    ]
    path = tmp_path / "claims.json"
    import json

    path.write_text(json.dumps(rows), encoding="utf-8")
    from freight_second_brain.etl.apply import load_rows

    count = write_table(warehouse, "claims", load_rows(path))
    assert count == 1
    stored = warehouse.load_jsonl("claims")[0]
    assert stored["polarity"] == "bullish"
    assert stored["entities"] == ["capesize", "iron_ore"]

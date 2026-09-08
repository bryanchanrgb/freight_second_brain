from freight_second_brain.etl.enrich import finalize_warehouse
from freight_second_brain.warehouse.store import Warehouse
from tests.conftest import make_observation


def test_finalize_warehouse_rebuilds_sql_without_qualitative_tables(settings) -> None:
    warehouse = Warehouse(settings)
    warehouse.write_observations([make_observation()])
    finalize_warehouse(warehouse)

    assert warehouse.load_jsonl("catalog")
    assert warehouse.duckdb_path.exists()
    tables = {row["table"] for row in warehouse.schema()}
    assert {"observations", "series", "catalog", "sources"} <= tables
    assert "claims" not in tables
    assert "events" not in tables
    assert "contradictions" not in tables

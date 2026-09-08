import pytest

from freight_second_brain.warehouse.store import Warehouse
from tests.conftest import make_observation


def test_sql_is_read_only_and_single_statement(settings) -> None:
    warehouse = Warehouse(settings)
    warehouse.write_observations([make_observation()])
    warehouse.rebuild_sql()

    with pytest.raises(ValueError, match="read-only"):
        warehouse.sql("DELETE FROM observations")
    with pytest.raises(ValueError, match="one SQL statement"):
        warehouse.sql("SELECT 1; SELECT 2")
    with pytest.raises(ValueError, match="empty"):
        warehouse.sql("   ")

    result = warehouse.sql("SELECT COUNT(*) AS n FROM observations")
    assert result["rows"][0]["n"] == 1


def test_schema_creates_empty_tables(settings) -> None:
    warehouse = Warehouse(settings)
    tables = {row["table"]: row for row in warehouse.schema()}
    assert tables["observations"]["row_count"] == 0
    assert tables["claims"]["row_count"] == 0
    names = {col["name"] for col in tables["observations"]["columns"]}
    assert "series_id" in names
    assert "value" in names

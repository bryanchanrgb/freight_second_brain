from __future__ import annotations

from pathlib import Path

from freight_second_brain.catalog.sources import SOURCE_CATALOG
from freight_second_brain.warehouse.store import Warehouse


def finalize_warehouse(warehouse: Warehouse) -> Path:
    """Write the static catalog and rebuild DuckDB. No semantic labeling."""
    warehouse.replace_jsonl("catalog", [row.model_dump(mode="json") for row in SOURCE_CATALOG])
    return warehouse.rebuild_sql()

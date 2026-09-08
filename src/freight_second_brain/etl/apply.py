from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from freight_second_brain.warehouse.schemas import (
    Claim,
    ClaimEntity,
    ClaimSeriesLink,
    Contradiction,
    Event,
)
from freight_second_brain.warehouse.store import Warehouse

WRITEABLE = {
    "claims": Claim,
    "events": Event,
    "claim_entities": ClaimEntity,
    "contradictions": Contradiction,
    "claim_series": ClaimSeriesLink,
}


def load_rows(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text[0] == "[":
        payload = json.loads(text)
        if not isinstance(payload, list):
            raise ValueError("JSON file must contain an array of objects.")
        return payload
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def write_table(warehouse: Warehouse, table: str, rows: list[dict[str, Any]]) -> int:
    model = WRITEABLE.get(table)
    if model is None:
        raise ValueError(f"Cannot write {table}. Allowed: {', '.join(sorted(WRITEABLE))}.")
    parsed = [model.model_validate(row) for row in rows]
    return warehouse.replace_jsonl(table, parsed)

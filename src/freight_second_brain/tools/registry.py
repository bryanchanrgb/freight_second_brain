from __future__ import annotations

import json
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from freight_second_brain.warehouse.store import Warehouse


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any]
    category: str = "query"


@dataclass
class ToolResult:
    name: str
    ok: bool
    data: Any
    error: str | None = None


class ToolRegistry:
    def __init__(self, warehouse: Warehouse | None = None) -> None:
        self.warehouse = warehouse or Warehouse()
        self._tools: dict[str, ToolSpec] = {}
        register_default_tools(self)

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.parameters,
                "category": spec.category,
            }
            for spec in self._tools.values()
        ]

    def openai_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.parameters,
                },
            }
            for spec in self._tools.values()
        ]

    def call(self, name: str, **kwargs: Any) -> ToolResult:
        spec = self._tools.get(name)
        if spec is None:
            return ToolResult(name=name, ok=False, data=None, error=f"unknown tool {name}")
        try:
            data = spec.handler(self.warehouse, **kwargs)
            return ToolResult(name=name, ok=True, data=data)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(name=name, ok=False, data=None, error=f"{exc}\n{traceback.format_exc(limit=2)}")

    def execute_json(self, name: str, arguments: str | dict[str, Any]) -> ToolResult:
        payload = json.loads(arguments) if isinstance(arguments, str) else arguments
        return self.call(name, **payload)


def register_default_tools(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="schema",
            description="List warehouse SQL tables, column types, and row counts. Call this before writing SQL.",
            parameters={"type": "object", "properties": {}},
            handler=_schema,
            category="query",
        )
    )
    registry.register(
        ToolSpec(
            name="sql",
            description=(
                "Run a read-only SQL query against the warehouse. "
                "Tables include observations, series, claims, claim_entities, contradictions, "
                "claim_series, events, sources, and catalog. SELECT/WITH/DESCRIBE/SHOW/FROM only."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Read-only SQL statement."},
                    "limit": {"type": "integer", "description": "Max rows to return (default 200, max 2000)."},
                },
                "required": ["query"],
            },
            handler=_sql,
            category="query",
        )
    )
    registry.register(
        ToolSpec(
            name="show_source",
            description="Display catalog metadata, retrieval record, and a text preview of a stored raw source snapshot.",
            parameters={
                "type": "object",
                "properties": {
                    "source_id": {"type": "string"},
                    "url": {"type": "string"},
                    "max_chars": {"type": "integer"},
                },
                "required": ["source_id"],
            },
            handler=_show_source,
            category="display",
        )
    )


def _schema(warehouse: Warehouse) -> Any:
    return warehouse.schema()


def _sql(warehouse: Warehouse, query: str, limit: int = 200) -> Any:
    return warehouse.sql(query, limit=limit)


def _show_source(warehouse: Warehouse, source_id: str, url: str | None = None, max_chars: int = 4000) -> Any:
    return warehouse.show_source(source_id, url=url, max_chars=max_chars)

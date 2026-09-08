from __future__ import annotations

from typing import Any

from freight_second_brain.config import Settings, get_settings
from freight_second_brain.tools.registry import ToolRegistry
from freight_second_brain.warehouse.store import Warehouse

SYSTEM_PROMPT = """You are Freight Second Brain, an analyst agent for dry-bulk freight rates.

Use `schema` to see warehouse tables, then `sql` to query them. Use `show_source` to display a
stored raw snapshot. Do not invent numerical forecasts. If a figure is not in the warehouse, say so.

Semantic tables (`claims`, `claim_entities`, `contradictions`, `claim_series`) are produced at
build time by agent skills, not by keyword code. Query those tables rather than relabeling text
at answer time. If they are empty, the code ingest ran without the semantic skills.

Every answer must distinguish:
- source fact (quoted/cited warehouse record)
- agent synthesis
- unresolved contradiction

Cite claim IDs, series IDs, source URLs, freshness class and whether evidence is independent.
Never treat article count as independent evidence count.
Never use post-cutoff outcomes as if they were in the original information set.
"""


class AgentRuntime:
    def __init__(self, settings: Settings | None = None, registry: ToolRegistry | None = None) -> None:
        self.settings = settings or get_settings()
        self.registry = registry or ToolRegistry(Warehouse(self.settings))

    def available_tools(self) -> list[dict[str, Any]]:
        return self.registry.list_tools()

    def invoke_tool(self, name: str, **kwargs: Any) -> dict[str, Any]:
        result = self.registry.call(name, **kwargs)
        return {"ok": result.ok, "name": result.name, "data": result.data, "error": result.error}

    def system_prompt(self) -> str:
        return SYSTEM_PROMPT

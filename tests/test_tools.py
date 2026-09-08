from freight_second_brain.tools.registry import ToolRegistry
from freight_second_brain.warehouse.store import Warehouse
from tests.conftest import make_claim, make_observation, make_retrieved_source


def test_runtime_tools_are_query_and_display_only(settings) -> None:
    registry = ToolRegistry(Warehouse(settings))
    names = {spec["name"] for spec in registry.list_tools()}
    assert names == {"schema", "sql", "show_source"}
    for removed in (
        "search_curated_sources",
        "retrieve_source",
        "extract_claims",
        "resolve_entities",
        "find_duplicates",
        "find_contradictions",
        "get_market_snapshot",
        "link_claims_to_series",
        "run_scenario",
        "evaluate_forecast_vintage",
        "save_user_feedback",
        "query_observations",
        "run_analysis_code",
        "list_series",
        "list_source_catalog",
    ):
        assert removed not in names


def test_schema_and_sql_tools(settings) -> None:
    warehouse = Warehouse(settings)
    warehouse.write_observations([make_observation()])
    warehouse.replace_jsonl("catalog", [{"source_id": "test_source", "name": "Test"}])
    warehouse.rebuild_sql()
    registry = ToolRegistry(warehouse)

    schema = registry.call("schema")
    assert schema.ok
    tables = {row["table"] for row in schema.data}
    assert {"observations", "series", "claims", "catalog"} <= tables

    latest = registry.call(
        "sql",
        query="SELECT series_id, value FROM observations ORDER BY observed_at DESC",
        limit=5,
    )
    assert latest.ok
    assert latest.data["row_count"] == 1
    assert latest.data["rows"][0]["series_id"] == "TEST.SERIES"

    blocked = registry.call("sql", query="DELETE FROM observations")
    assert not blocked.ok
    assert blocked.error


def test_show_source_tool(settings, tmp_path) -> None:
    payload = tmp_path / "page.html"
    payload.write_text("<html>Baltic Dry displayed value</html>", encoding="utf-8")
    warehouse = Warehouse(settings)
    warehouse.write_sources(
        [make_retrieved_source(source_id="mendeley_bdi", raw_object_uri=str(payload))]
    )
    result = ToolRegistry(warehouse).call("show_source", source_id="mendeley_bdi")
    assert result.ok
    assert result.data["catalog"]["source_id"] == "mendeley_bdi"
    assert "Baltic Dry" in result.data["preview"]
    assert result.data["payload_name"] == "page.html"

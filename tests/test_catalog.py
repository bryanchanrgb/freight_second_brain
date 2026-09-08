from freight_second_brain.catalog.entities import CANONICAL_ENTITIES
from freight_second_brain.catalog.sources import SOURCE_CATALOG, list_enabled_extractors
from freight_second_brain.qualitative.freshness import classify_freshness
from freight_second_brain.warehouse.schemas import FreshnessClass
from datetime import UTC, datetime, timedelta


def test_catalog_has_tier1_sources() -> None:
    ids = {row.source_id for row in SOURCE_CATALOG}
    for required in (
        "mendeley_bdi",
        "world_bank_pink_sheet",
        "usda_psd",
        "comtrade",
        "data360_maritime",
        "hellenic_rss",
    ):
        assert required in ids
    assert "world_bank_pink_sheet" in list_enabled_extractors()


def test_canonical_entities_cover_core_dry_bulk() -> None:
    ids = {entity.entity_id for entity in CANONICAL_ENTITIES}
    for required in ("BDI", "capesize", "iron_ore", "china"):
        assert required in ids


def test_freshness_buckets() -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    assert classify_freshness(now - timedelta(days=2), now) == FreshnessClass.CURRENT
    assert classify_freshness(now - timedelta(days=20), now) == FreshnessClass.RECENT
    assert classify_freshness(now - timedelta(days=40), now) == FreshnessClass.AGING
    assert classify_freshness(now - timedelta(days=120), now) == FreshnessClass.HISTORICAL_VINTAGE
    assert classify_freshness(now + timedelta(days=1), now, information_cutoff=now) == FreshnessClass.POST_CUTOFF_OUTCOME

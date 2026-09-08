from __future__ import annotations

from datetime import UTC, datetime

from freight_second_brain.warehouse.schemas import FreshnessClass


def classify_freshness(
    published_at: datetime | None,
    as_of: datetime,
    information_cutoff: datetime | None = None,
) -> FreshnessClass:
    if published_at is None:
        return FreshnessClass.RECENT
    published = published_at if published_at.tzinfo else published_at.replace(tzinfo=UTC)
    as_of_aware = as_of if as_of.tzinfo else as_of.replace(tzinfo=UTC)
    if information_cutoff is not None:
        cutoff = information_cutoff if information_cutoff.tzinfo else information_cutoff.replace(tzinfo=UTC)
        if published > cutoff:
            return FreshnessClass.POST_CUTOFF_OUTCOME
    age_days = (as_of_aware - published).days
    if age_days <= 7:
        return FreshnessClass.CURRENT
    if age_days <= 30:
        return FreshnessClass.RECENT
    if age_days <= 90:
        return FreshnessClass.AGING
    return FreshnessClass.HISTORICAL_VINTAGE

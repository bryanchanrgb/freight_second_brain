from __future__ import annotations

from freight_second_brain.catalog.sources import get_source
from freight_second_brain.etl.extractors.base import (
    ExtractResult,
    RunContext,
    make_retrieved_source,
    utcnow,
)
from freight_second_brain.etl.http import fetch


class HellenicRssExtractor:
    name = "hellenic_rss"

    def extract(self, ctx: RunContext) -> ExtractResult:
        source = get_source("hellenic_rss")
        result = ExtractResult(source_id=source.source_id, status="complete")
        response = fetch(source.default_url, settings=ctx.settings, timeout=30)
        result.requests = 1
        result.successful_requests = 1
        directory = ctx.landing.write(
            source_id=source.source_id,
            dataset="dry_bulk_feed",
            run_id=ctx.run_id,
            result=response,
            request={"url": source.default_url, "method": "GET"},
            license_name=source.license,
            payload_name="feed.xml",
        )
        uri = str(directory)
        result.snapshot_uris.append(uri)
        result.retrieved_sources.append(
            make_retrieved_source(
                source_id=source.source_id,
                url=response.url,
                publisher=source.publisher,
                source_type=source.source_type,
                retrieved_at=utcnow(),
                content_hash=response.sha256,
                raw_uri=uri,
                title="Hellenic dry-bulk RSS",
                license_name=source.license,
            )
        )
        result.notes.append("RSS snapshot stored; live rss_feed is the news layer")
        return result

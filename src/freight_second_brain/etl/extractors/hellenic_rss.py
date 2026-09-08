from __future__ import annotations

from datetime import datetime

import feedparser

from freight_second_brain.catalog.sources import get_source
from freight_second_brain.etl.extractors.base import (
    ExtractResult,
    RunContext,
    make_retrieved_source,
    slug,
    utcnow,
)
from freight_second_brain.etl.http import fetch
from freight_second_brain.warehouse.schemas import Event


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
        parsed = feedparser.parse(response.content)
        for index, entry in enumerate(parsed.entries):
            published = _entry_time(entry)
            url = entry.get("link") or source.default_url
            headline = (entry.get("title") or "").strip()
            summary = (entry.get("summary") or entry.get("description") or "")[:800]
            item_id = slug(entry.get("id") or url or str(index))
            result.events.append(
                Event(
                    event_id=f"hellenic-{item_id}"[:64],
                    published_at=published,
                    observed_at=published,
                    source=source.source_id,
                    source_url=url,
                    headline=headline,
                    extracted_evidence=summary,
                    raw_object_uri=uri,
                )
            )
        if not result.events:
            result.status = "partial"
            result.notes.append("RSS downloaded but no entries parsed")
        result.notes.append("headlines stored unlabeled; extract-claims skill assigns meaning")
        return result


def _entry_time(entry: dict) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return datetime(*parsed[:6], tzinfo=utcnow().tzinfo)

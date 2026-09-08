from __future__ import annotations

from freight_second_brain.catalog.sources import get_source
from freight_second_brain.etl.extractors.base import ExtractResult, RunContext, make_retrieved_source, utcnow
from freight_second_brain.etl.http import fetch

PAGES = (
    ("baltic_exchange", "dry_services.html", "text/html"),
    ("bimco", "market_analysis.html", "text/html"),
    ("unctad_rmt", "rmt2025_en.pdf", "application/pdf"),
)


class QualitativePagesExtractor:
    name = "qualitative_pages"

    def extract(self, ctx: RunContext) -> ExtractResult:
        result = ExtractResult(source_id="qualitative_pages", status="complete")
        now = utcnow()
        for source_id, payload_name, _media in PAGES:
            source = get_source(source_id)
            result.requests += 1
            try:
                response = fetch(source.default_url, settings=ctx.settings, timeout=90)
            except Exception as exc:  # noqa: BLE001
                result.failed_requests += 1
                result.notes.append(f"{source_id} failed: {exc}")
                continue
            result.successful_requests += 1
            directory = ctx.landing.write(
                source_id=source.source_id,
                dataset="snapshot",
                run_id=ctx.run_id,
                result=response,
                request={"url": source.default_url, "method": "GET"},
                license_name=source.license,
                payload_name=payload_name,
            )
            uri = str(directory)
            result.snapshot_uris.append(uri)
            result.retrieved_sources.append(
                make_retrieved_source(
                    source_id=source.source_id,
                    url=response.url,
                    publisher=source.publisher,
                    source_type=source.source_type,
                    retrieved_at=now,
                    content_hash=response.sha256,
                    raw_uri=uri,
                    title=source.name,
                    license_name=source.license,
                    retrieval_status="full_text" if payload_name.endswith(".html") else "public_summary",
                )
            )
        if result.failed_requests and not result.retrieved_sources:
            result.status = "failed"
        elif result.failed_requests:
            result.status = "partial"
        result.notes.append("snapshots stored for show_source; live web tools cover current news")
        return result

"""
Turns a raw crawl4ai result object into a validated ScrapedDocumentSchema
(or None if the page should be discarded). No I/O here - saving is storage.py's job.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .config import MIN_BODY_CHARS
from .RetrievalEnum import ScrapeStatus
from .schemas import ScrapedDocumentSchema, SourceItem
from .utils import clean_text, extract_links, extract_metadata, get_domain, normalize_url

logger = logging.getLogger("theme1-scraper")


def process_result(
    result: Any,
    source: SourceItem,
    visited_urls: set[str],
) -> Optional[ScrapedDocumentSchema]:
    raw_url = getattr(result, "url", None)
    if not raw_url:
        return None

    url = normalize_url(raw_url)
    if url in visited_urls:
        return None
    visited_urls.add(url)

    success = getattr(result, "success", True)
    if not success:
        error_message = str(getattr(result, "error_message", "Unknown crawl error"))
        logger.warning("Failed page %s: %s", url, error_message)
        return ScrapedDocumentSchema(
            url=url,
            domain=get_domain(url),
            title=None,
            body="",
            links=[],
            metadata={},
            source_name=source.name,
            source_type=source.source_type,
            category=source.category,
            scraped_at=datetime.now(timezone.utc),
            status=ScrapeStatus.FAILED,
            error=error_message,
        )

    body = getattr(result, "markdown", None) or getattr(result, "text", "") or getattr(result, "cleaned_html", "")
    body = clean_text(body)
    if len(body) < MIN_BODY_CHARS:
        logger.warning("Discarding %s: body too short (%d chars)", url, len(body))
        return None

    title = clean_text(getattr(result, "title", None)) or None
    metadata = extract_metadata(result)
    links = extract_links(result)

    return ScrapedDocumentSchema(
        url=url,
        domain=get_domain(url),
        title=title,
        body=body,
        links=links,
        metadata=metadata,
        source_name=source.name,
        source_type=source.source_type,
        category=source.category,
        scraped_at=datetime.now(timezone.utc),
        status=ScrapeStatus.SUCCESS,
        error=None,
    )
"""
Small, pure helper functions with no crawl4ai dependency - kept separate so
they're trivially unit-testable without spinning up a browser/crawler.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Optional
from urllib.parse import urlparse


def normalize_url(url: str) -> str:
    url = url.strip()
    return url[:-1] if url.endswith("/") else url


def get_domain(url: str) -> str:
    return urlparse(url).netloc


def clean_text(text: Optional[str]) -> str:
    if not text:
        return ""
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def content_hash_filename(url: str) -> str:
    """Stable, collision-free filename derived from the URL itself, so
    re-scraping the same URL updates the same file instead of duplicating it."""
    url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    domain = get_domain(url).replace(".", "_")
    return f"{domain}__{url_hash}.json"


def extract_links(result: Any) -> list[str]:
    links: list[str] = []
    raw_links = getattr(result, "links", None)

    if isinstance(raw_links, dict):
        for category_links in raw_links.values():
            if isinstance(category_links, list):
                for item in category_links:
                    if isinstance(item, str):
                        links.append(item)
                    elif isinstance(item, dict) and item.get("href"):
                        links.append(item["href"])
    elif isinstance(raw_links, list):
        for item in raw_links:
            if isinstance(item, str):
                links.append(item)
            elif isinstance(item, dict) and item.get("href"):
                links.append(item["href"])

    return list(dict.fromkeys(link.strip() for link in links if isinstance(link, str) and link.strip()))


def extract_metadata(result: Any) -> dict:
    metadata: dict = {}
    result_metadata = getattr(result, "metadata", None)
    if isinstance(result_metadata, dict):
        metadata.update({k: v for k, v in result_metadata.items() if v is not None})

    for attr in ("title", "description", "language", "author", "published_date", "keywords"):
        value = getattr(result, attr, None)
        if value is not None:
            metadata.setdefault(attr, value)

    return metadata
<<<<<<< HEAD
"""
Orchestrator for the Theme 1 ingestion pipeline. This file now only wires
the pieces together - the actual logic lives in:
    config.py           - paths & constants
    utils.py             - pure helper functions (testable without crawl4ai)
    loader.py            - sources.yaml -> SourcesConfig
    crawler_config.py    - crawl4ai BrowserConfig / CrawlerRunConfig
    processor.py          - raw crawl4ai result -> ScrapedDocumentSchema
    storage.py            - writing documents + manifest to disk

Usage:
    python -m src.ingestion.scraper
"""
from __future__ import annotations

import asyncio
import logging

from crawl4ai import AsyncWebCrawler

from .config import DEFAULT_CONCURRENCY, MIN_DOCUMENTS_REQUIRED, SOURCES_FILE
from .crawlerconfig import browser_config, crawler_config
from .loader import load_sources
from .process import process_result
from .schemas import ScrapedDocumentSchema, SourceItem, SourcesConfig
from .storage import ensure_output_dir, save_document, write_manifest

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
logger = logging.getLogger("theme1-scraper")


class Theme1Scraper:
    def __init__(self, concurrency_limit: int = DEFAULT_CONCURRENCY):
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self.visited_urls: set[str] = set()
        ensure_output_dir()

    async def scrape_source(self, crawler: AsyncWebCrawler, source: SourceItem) -> int:
        saved = 0
        config = crawler_config(source)

        for seed_url in source.urls:
            async with self.semaphore:
                logger.info("Crawling [%s] seed: %s", source.name, seed_url)
                try:
                    results = await crawler.arun(url=str(seed_url), config=config)
                    async for result in results:
                        document = process_result(result, source, self.visited_urls)
                        if document is None:
                            continue
                        if document.status == "success":
                            path = save_document(document)
                            saved += 1
                            logger.info("  [%d] saved %s -> %s", saved, document.url, path.name)
                        else:
                            logger.warning("  skipped failed page: %s", document.url)
                except Exception:  # noqa: BLE001
                    logger.exception("Error crawling seed %s", seed_url)

        return saved

    async def run(self) -> int:
        config: SourcesConfig = load_sources()
        logger.info("Loaded %d source groups from %s", len(config.sources), SOURCES_FILE)

        total_saved = 0
        async with AsyncWebCrawler(config=browser_config()) as crawler:
            for source in config.sources:
                total_saved += await self.scrape_source(crawler, source)

        manifest_path = write_manifest(total_saved)

        logger.info("=" * 60)
        logger.info("Collection finished. Total documents: %d", total_saved)
        logger.info("Manifest: %s", manifest_path)
        logger.info("=" * 60)

        if total_saved < MIN_DOCUMENTS_REQUIRED:
            logger.warning(
                "Only %d documents collected - below the %d-document minimum "
                "required by the Week 1 brief. Add more seed URLs to sources.yaml "
                "or increase max_depth/max_pages per source.",
                total_saved, MIN_DOCUMENTS_REQUIRED,
            )

        return total_saved


async def main() -> None:
    scraper = Theme1Scraper()
    await scraper.run()


if __name__ == "__main__":
    asyncio.run(main())
=======
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import (
    BrowserConfig,
    CacheMode,
    CrawlerRunConfig,
)
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
from .enums import ScrapeStatus
from .schemas import ScrapedDocumentSchema


class WebScraper:

    def __init__(
        self,
        max_depth: int = 2,
    ):
        self.max_depth = max_depth

        self.browser_config = BrowserConfig(
            text_mode=True,
        )

        self.run_config = CrawlerRunConfig(
            excluded_tags=[
                "script",
                "style",
                "form",
                "header",
                "footer",
                "nav",
            ],
            only_text=True,
            remove_forms=True,
            exclude_social_media_links=True,
            exclude_external_links=True,
            remove_overlay_elements=True,
            magic=True,
            simulate_user=True,
            override_navigator=True,
            verbose=True,
            cache_mode=CacheMode.DISABLED,
            stream=True,

            deep_crawl_strategy=BFSDeepCrawlStrategy(
                max_depth=max_depth,
                include_external=False,
            ),
        )

    @staticmethod
    def _extract_metadata(result) -> dict[str, Any]:
        """
        Extract all available metadata from the page.

        Metadata is not limited to title.
        Any <meta> tag found in the HTML is stored.
        """

        metadata: dict[str, Any] = {}

      
        title = getattr(result, "title", None)

        if title:
            metadata["title"] = title

        html = (
            getattr(result, "html", None)
            or getattr(result, "cleaned_html", None)
        )

        if not html:
            return metadata

        soup = BeautifulSoup(
            html,
            "html.parser",
        )


        for meta in soup.find_all("meta"):

            name = (
                meta.get("name")
                or meta.get("property")
                or meta.get("http-equiv")
                or meta.get("itemprop")
            )

            content = meta.get("content")

            if not name or content is None:
                continue

            name = name.strip()
            content = content.strip()

            if not content:
                continue

            # If the same metadata key appears multiple
            # times, preserve all values.
            if name in metadata:

                existing = metadata[name]

                if isinstance(existing, list):
                    existing.append(content)

                else:
                    metadata[name] = [
                        existing,
                        content,
                    ]

            else:
                metadata[name] = content


        html_tag = soup.find("html")

        if html_tag:

            language = html_tag.get("lang")

            if language:
                metadata["language"] = language

     

        canonical = soup.find(
            "link",
            rel=lambda value: (
                value
                and "canonical" in value
            ),
        )

        if canonical:

            href = canonical.get("href")

            if href:
                metadata["canonical_url"] = href

        return metadata

    @staticmethod
    def _extract_related_links(
        result,
    ) -> list[str]:
        """
        Extract links discovered on the page.
        """

        links: list[str] = []

        result_links = getattr(
            result,
            "links",
            None,
        )

        if not result_links:
            return links

        # Crawl4AI may return links grouped
        # as internal/external.
        if isinstance(result_links, dict):

            all_links = []

            all_links.extend(
                result_links.get(
                    "internal",
                    [],
                )
            )

            all_links.extend(
                result_links.get(
                    "external",
                    [],
                )
            )

        else:
            all_links = result_links

        for link in all_links:

            if isinstance(link, dict):
                href = link.get("href")

            else:
                href = getattr(
                    link,
                    "href",
                    None,
                )

            if not href:
                continue

            href = href.strip()

            if not href.startswith(
                (
                    "http://",
                    "https://",
                )
            ):
                continue

            links.append(href)

        # Remove duplicates while preserving order.
        return list(dict.fromkeys(links))

    @staticmethod
    def _build_document(
        result,
    ) -> ScrapedDocumentSchema:

        parsed_url = urlparse(
            result.url
        )

        body = (
            getattr(result, "markdown", None)
            or getattr(result, "cleaned_html", None)
            or ""
        )

        metadata = (
            WebScraper._extract_metadata(
                result
            )
        )

        related_links = (
            WebScraper._extract_related_links(
                result
            )
        )

        return ScrapedDocumentSchema(
            url=result.url,
            body=body,
            metadata=metadata,
            related_links=related_links,
            domain=parsed_url.netloc,
            status=ScrapeStatus.SUCCESS,
        )

    async def scrape(
        self,
        url: str,
    ) -> list[ScrapedDocumentSchema]:
        """
        Crawl a URL and return all scraped
        pages as Pydantic schemas.
        """

        documents: list[
            ScrapedDocumentSchema
        ] = []

        async with AsyncWebCrawler(
            config=self.browser_config,
            verbose=True,
            debug=True,
            use_playwright=True,
        ) as crawler:

            async for result in await crawler.arun(
                url=url,
                config=self.run_config,
            ):

                if not result.success:

                    print(
                        f"Failed to scrape: "
                        f"{result.url}"
                    )

                    continue

                document = (
                    self._build_document(
                        result
                    )
                )

                documents.append(document)

        return documents
>>>>>>> 46058949eaca4c4f18b8ad4660e984e6f11b9e43

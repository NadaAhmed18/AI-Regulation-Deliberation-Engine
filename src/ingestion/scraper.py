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
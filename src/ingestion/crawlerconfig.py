"""
crawl4ai configuration builders, isolated from the crawling/orchestration
logic so tuning crawl behavior doesn't require touching scraper.py.
"""
from __future__ import annotations

from crawl4ai.async_configs import BrowserConfig, CacheMode, CrawlerRunConfig
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy

from .schemas import SourceItem


def browser_config() -> BrowserConfig:
    return BrowserConfig(text_mode=True, headless=True, verbose=False)


def crawler_config(source: SourceItem) -> CrawlerRunConfig:
    return CrawlerRunConfig(
        excluded_tags=["script", "style", "form", "header", "footer", "nav", "noscript", "svg"],
        remove_forms=True,
        remove_overlay_elements=True,
        only_text=True,
        exclude_social_media_links=True,
        exclude_external_links=True,
        magic=True,
        simulate_user=True,
        override_navigator=True,
        cache_mode=CacheMode.DISABLED,
        stream=True,
        verbose=False,
        deep_crawl_strategy=BFSDeepCrawlStrategy(
            max_depth=source.max_depth,
            include_external=False,
            max_pages=source.max_pages,
        ),
    )
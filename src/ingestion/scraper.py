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

import asyncio
import json
import os
import re
from urllib.parse import urlparse
from typing import List, Dict, Any

import trafilatura
from crawl4ai import AsyncWebCrawler


def clean_content(html: str, fallback_markdown: str, links: List[str]) -> Dict[str, Any]:
    """
    Universal cleaner using Trafilatura and Regex.
    Replaces the need for domain-specific adapters.
    """
    # 1. Trafilatura magically drops menus, footers, and sidebars from raw HTML
    body = trafilatura.extract(html, include_links=False, include_images=False)
    
    # 2. Fallback to Crawl4AI markdown if Trafilatura fails
    if not body or len(body) < 150:
        body = fallback_markdown

    # 3. Strip noisy markdown images/empty links
    body = re.sub(r'!\[.*?\]\([^\)]+\)', '', body)
    body = re.sub(r'\[\s*\]\([^\)]+\)', '', body)
    body = re.sub(r'\n\s*\n', '\n\n', body).strip()

    # 4. Filter out useless social/system URLs
    bad_keywords = ["facebook.com", "twitter.com", "youtube.com", "javascript:", "action=edit"]
    clean_links = [
        str(link) for link in set(links) 
        if isinstance(link, str) and not any(bad in link for bad in bad_keywords)
    ]

    return {"body": body, "related_documents": clean_links}


async def _fetch_url(crawler: AsyncWebCrawler, url: str) -> tuple:
    """Helper to fetch a single URL and return the URL alongside its result."""
    result = await crawler.arun(url, excluded_tags=["script", "style", "nav", "footer"])
    return url, result


async def ingest_batch(urls: List[str]) -> List[Dict[str, Any]]:
    """
    Scrapes a batch of URLs in parallel and returns clean Neo4j-ready dictionaries.
    """
    docs = []
    print(f"[*] Starting ingestion for {len(urls)} URLs in parallel...")

    async with AsyncWebCrawler(verbose=False) as crawler:
        # Use asyncio.gather to run all URLs at once (fixes Pylance arun_many error)
        tasks = [_fetch_url(crawler, u) for u in urls]
        results = await asyncio.gather(*tasks)

    for url, res in results:
        if not getattr(res, "success", False):
            print(f"[-] Failed to download: {url}")
            continue

        # Extract internal links safely (fixes Pylance list typing error)
        raw_links = []
        if isinstance(getattr(res, "links", {}), dict):
            for l in res.links.get("internal", []):
                if isinstance(l, dict) and isinstance(l.get("href"), str):
                    raw_links.append(l["href"])

        # Clean the text and links
        cleaned = clean_content(
            html=getattr(res, "html", ""),
            fallback_markdown=getattr(res, "markdown", ""),
            links=raw_links
        )

        if len(cleaned["body"]) < 150:
            print(f"[-] Skipped (content too short): {url}")
            continue

        docs.append({
            "document_url": url,
            "domain": urlparse(url).netloc,
            "body": cleaned["body"],
            "related_documents": cleaned["related_documents"],
            "metadata": {
                "title": getattr(res, "metadata", {}).get("title", "")
            }
        })
        print(f"[+] Successfully processed: {url}")

    return docs


# ==========================================
# Execution Block: Saves results to JSON
# ==========================================
if __name__ == "__main__":
    TEST_URLS = [
        "https://mcit.gov.eg/en/Artificial_Intelligence",
        "https://en.wikipedia.org/wiki/Artificial_intelligence_act"
    ]

    OUTPUT_DIR = os.path.abspath(os.path.join(os.getcwd(),"data/raw"))
    OUTPUT_FILE = os.path.join(OUTPUT_DIR, "scraped_documents.json")

    # 1. Run the scraper
    results = asyncio.run(ingest_batch(TEST_URLS))

    # 2. Save the results
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n[✔] Success! Saved {len(results)} documents to {OUTPUT_FILE}")
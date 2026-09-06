# python -m src.rag.stages.scraper

import asyncio
import hashlib
import json
import os
import re
from urllib.parse import urlparse
from typing import List, Dict, Any

import trafilatura
from crawl4ai import AsyncWebCrawler
from flashrank import Ranker, RerankRequest
from src.config import MAX_RELATED_LINKS


# Initialize the lightweight local reranker globally so it only loads into memory once
print("[*] Loading FlashRank local ranking model...")
ranker = Ranker(model_name="ms-marco-TinyBERT-L-2-v2")


def pre_filter_links(links: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    PRE-FILTER: Uses Regex to instantly drop obvious garbage before AI processing.
    Expects dictionaries: {"href": "...", "text": "..."}
    """
    junk_patterns = [
        r'(facebook|twitter|linkedin|whatsapp|youtube)\.com',
        r'share_on_',
        r'/(contact_us|feedback|disclaimer|privacy_statement|site_map|login|createaccount|lang)/?',
        r'/(Special|Help|Wikipedia|File|Category|Portal|Template|Talk|Template_talk):',
        r'(action=(edit|history|info)|printable=yes|returnto=)',
        r'index\.php\?',
        r'_\(identifier\)'
    ]
    junk_regex = re.compile('|'.join(junk_patterns), re.IGNORECASE)
    
    clean_links = []
    seen_urls = set()
    
    for link in links:
        url = link.get("href", "")
        if not url.startswith('http') or url in seen_urls:
            continue
            
        if "wikipedia.org" in url and not url.startswith("https://en.wikipedia.org"):
            continue
            
        if not junk_regex.search(url):
            clean_links.append(link)
            seen_urls.add(url)
            
    return clean_links


def smart_rank_links(page_title: str, raw_links: List[Dict[str, str]]) -> List[str]:
    """
    AI RERANKER: Uses FlashRank to score links based on relevance to the page title.
    Returns only the most relevant `MAX_RELATED_LINKS` URLs as strings.
    """
    # 1. Strip the obvious junk using regex
    filtered_links = pre_filter_links(raw_links)
    
    if not filtered_links:
        return []

    # 2. Format passages for FlashRank
    passages = []
    for i, link in enumerate(filtered_links):
        text = link.get("text", "").strip()
        # If the link has no anchor text, fallback to the URL path for ranking
        if not text:
            text = urlparse(link["href"]).path.split("/")[-1].replace("-", " ")
        
        # Discard empty strings
        if len(text) > 2:
            passages.append({"id": i, "text": text, "meta": link})

    if not passages:
        return []

    # 3. Ask AI to score the links against the page title 
    # Fallback query if page has no title
    query = page_title if page_title else "Artificial Intelligence Policy and Information"
    request = RerankRequest(query=query, passages=passages)
    
    ranked_results = ranker.rerank(request)

    # 4. Keep only the top results based on config threshold
    best_links = []
    for result in ranked_results[:MAX_RELATED_LINKS]:
        best_links.append(result["meta"]["href"])

    return best_links


def clean_content(html: str, fallback_markdown: str) -> str:
    """Universal text cleaner using Trafilatura and Regex."""
    body = trafilatura.extract(html, include_links=False, include_images=False)
    
    if not body or len(body) < 150:
        body = fallback_markdown

    body = re.sub(r'!\[.*?\]\([^\)]+\)', '', body)
    body = re.sub(r'\[\s*\]\([^\)]+\)', '', body)
    return re.sub(r'\n\s*\n', '\n\n', body).strip()


async def _fetch_url(crawler: AsyncWebCrawler, url: str) -> tuple:
    """Helper to fetch a single URL and return the URL alongside its result."""
    result = await crawler.arun(url, excluded_tags=["script", "style", "nav", "footer"])
    return url, result


async def ingest_batch(urls: List[str]) -> List[Dict[str, Any]]:
    docs = []
    print(f"[*] Starting ingestion for {len(urls)} URLs in parallel...")

    async with AsyncWebCrawler(verbose=False) as crawler:
        tasks = [_fetch_url(crawler, u) for u in urls]
        results = await asyncio.gather(*tasks)

    for url, res in results:
        if not getattr(res, "success", False):
            print(f"[-] Failed to download: {url}")
            continue
        
        
        # Strict Check for HTTP Error Codes (e.g., 404 Not Found, 403 Forbidden)
        status_code = getattr(res, "status_code", 200)
        if status_code and status_code >= 400:
            print(f"[-] Skipped (HTTP {status_code} Error): {url}")
            continue
        
        # Strict Check for 404 page titles (Sometimes status_code is 200 but it's actually a 404 page)
        title = getattr(res, "metadata", {}).get("title", "")
        bad_titles = ["404", "not found", "page not found", "error", "access denied", "forbidden"]
        # Only check short titles to avoid accidentally blocking an article named "The 404 Error in Policy"
        if title and len(title) < 40 and any(bad in title.lower() for bad in bad_titles):
            print(f"[-] Skipped (404/Error Page Detected via Title '{title}'): {url}")
            continue

        raw_html = getattr(res, "html", "")
        domain = urlparse(url).netloc

        # Extract internal links WITH their anchor text for the AI Reranker
        raw_links = []
        if isinstance(getattr(res, "links", {}), dict):
            for l in res.links.get("internal", []):
                if isinstance(l, dict) and isinstance(l.get("href"), str):
                    # Save both URL and Text
                    raw_links.append({"href": l["href"], "text": l.get("text", "")})

        # 1. Clean the main body text
        body_text = clean_content(
            html=raw_html,
            fallback_markdown=getattr(res, "markdown", "")
        )

        if len(body_text) < 150:
            print(f"[-] Skipped (content too short): {url}")
            continue

        # 2. Semantically Rerank and filter the related links
        top_related_links = smart_rank_links(page_title=title, raw_links=raw_links)

        docs.append({
            "document_url": url,
            "domain": domain,
            "body": body_text,
            "related_documents": top_related_links,
            "metadata": {
                "title": title
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

    results = asyncio.run(ingest_batch(TEST_URLS))

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n[✔] Success! Saved {len(results)} documents to {OUTPUT_FILE}")
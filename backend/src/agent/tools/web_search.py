import os
import asyncio
from dotenv import load_dotenv
from tavily import TavilyClient

from src.rag.stages.scraper import ingest_batch
from src.rag.stages.ingestion import ingest_documents

load_dotenv()


def _get_client() -> TavilyClient:
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        raise ValueError("TAVILY_API_KEY environment variable is missing.")
    return TavilyClient(api_key=api_key)


def search_web(query: str, max_results: int = 3) -> str:
    """Search the web for top URLs and snippets using advanced search depth."""
    query = (query or "").strip()
    if not query:
        return "Search failed: query cannot be empty."

    print(f"\n[Web Tool] 🌐 Searching live web for: '{query}'")
    try:
        client = _get_client()
        max_results = min(max(1, max_results), 5)
        response = client.search(query=query, search_depth="advanced", max_results=max_results)

        results = response.get("results", [])
        if not results:
            return "No web results found."

        output = ["Here are the live search results:"]
        for i, r in enumerate(results, 1):
            output.append(
                f"--- SOURCE {i} ---\n"
                f"Title: {r.get('title', 'N/A')}\n"
                f"URL: {r.get('url', 'N/A')}\n"
                f"Snippet: {r.get('content', '')}\n"
            )
        return "\n".join(output)
    except Exception as e:
        print(f"[Web Tool] ⚠️ Error during search: {e}")
        return f"Web search encountered an error: {e}"


def learn_and_ingest_url(url: str) -> str:
    """
    Crawls a URL, and passes it directly to ingestion.
    Ingestion handles deduplication and automatic graph edge wiring.
    """
    url = (url or "").strip()
    if not url.startswith("http"):
        return "Learning failed: a valid http/https URL must be provided."

    print(f"\n[Web Tool] 🧠 Processing URL: {url}")
    try:
        # 1. Scrape the document
        docs = asyncio.run(ingest_batch([url]))
        if not docs:
            return f"Failed to extract content from {url} (page may be blocked or empty)."

        doc = docs[0]

        # 2. Hand off directly to ingestion (default: on_conflict='ignore')
        stats = ingest_documents([doc], on_conflict="ignore")

        # 3. Formulate clear response for the agent
        status_msg = "newly ingested and linked in the graph"
        if stats["skipped"] > 0:
            status_msg = "already present in the graph; relationships verified"
        
        return f"Successfully learned from {url}: {status_msg}."

    except Exception as e:
        print(f"[Web Tool] ⚠️ Error during learning ingestion: {e}")
        return f"Failed to learn from {url}: {e}"


if __name__ == "__main__":
    # Smoke test: python -m src.agent.tools.web_search
    print(search_web("EU AI Act 2026 updates"))
    print(learn_and_ingest_url("https://en.wikipedia.org/wiki/Artificial_Intelligence_Act"))
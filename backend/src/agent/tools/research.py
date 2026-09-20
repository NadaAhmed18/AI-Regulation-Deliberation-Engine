import os
import logging
import asyncio
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor
from tavily import TavilyClient

from src.agent.tools.retriever import search_ai_policy
from src.rag.stages.scraper import ingest_batch
from src.rag.stages.ingestion import ingest_documents

logger = logging.getLogger("uvicorn")

_ingest_pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="neo4j_ingest_worker")


def _background_ingest(url: str):
    """Asynchronously ingests and embeds content in the background into Neo4j."""
    logger.info(f"[Background Ingest Started]: Indexing '{url}' into Neo4j...")
    try:
        docs = asyncio.run(ingest_batch([url]))
        if docs:
            ingest_documents([docs[0]], on_conflict="ignore")
            logger.info(f"[Background Ingest Success]: Finished indexing '{url}' into Neo4j.")
        else:
            logger.warning(f"[Background Ingest]: No docs extracted from '{url}'.")
    except Exception as e:
        logger.error(f"[Async Ingestion Error for {url}]: {e}", exc_info=True)


def unified_policy_research(
    queries: List[str],
    document_urls: Optional[List[str]] = None,
    auto_ingest_web: bool = True,
    max_web_results_per_query: int = 3,
) -> str:
    """Unified RAG tool combining Neo4j retrieval, Tavily search, and auto-ingestion."""
    if not queries and not document_urls:
        return "Please provide at least one query or document_url to research."

    output_sections: List[str] = []
    discovered_web_urls: List[str] = []

    # 1. Document lookups
    if document_urls:
        for url in document_urls:
            doc_result = search_ai_policy(document_url=url)
            output_sections.append(f"### Internal Document: {url}\n{doc_result}\n")

    # 2. Neo4j chunk search
    queries_needing_web: List[str] = []
    for q in queries:
        clean_q = q.strip()
        if not clean_q:
            continue
        internal_result = search_ai_policy(query=clean_q, top_k=2)
        if "No relevant information found" in internal_result or len(internal_result.strip()) < 80:
            queries_needing_web.append(clean_q)
        else:
            output_sections.append(f"### [Internal Knowledge] Query: '{clean_q}'\n{internal_result}\n")

    # 3. Live Web fallback via Tavily
    web_targets = queries_needing_web if queries_needing_web else queries[:2]
    tavily_key = os.getenv("TAVILY_API_KEY")
    if web_targets and tavily_key:
        try:
            tavily = TavilyClient(api_key=tavily_key)
            for wq in web_targets:
                res = tavily.search(query=wq, search_depth="ultra-fast", max_results=max_web_results_per_query)
                results = res.get("results", [])
                if results:
                    output_sections.append(f"### [Live Web Search] Query: '{wq}'")
                    for i, r in enumerate(results, 1):
                        url = r.get("url", "")
                        if url:
                            discovered_web_urls.append(url)
                        output_sections.append(
                            f"- Source {i}: {r.get('title')}\n  URL: {url}\n  Snippet: {r.get('content')}\n"
                        )
        except Exception as e:
            output_sections.append(f"[Web search warning: {e}]")

    # 4. Background Ingestion 
    if auto_ingest_web and discovered_web_urls:
        top_url = discovered_web_urls[0]
        _ingest_pool.submit(_background_ingest, top_url)
        output_sections.append(f"*(Discovered source '{top_url}' queued for background indexing.)*")

    return "\n".join(output_sections) if output_sections else "No information found."
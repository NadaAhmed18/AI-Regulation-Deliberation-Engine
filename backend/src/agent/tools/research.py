import os
from typing import List, Optional
from tavily import TavilyClient

from src.agent.tools.retriever import search_ai_policy
from src.tasks.ingestion_tasks import ingest_url_task


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
                        output_sections.append(f"- Source {i}: {r.get('title')}\n  URL: {url}\n  Snippet: {r.get('content')}\n")
        except Exception as e:
            output_sections.append(f"[Web search warning: {e}]")

    # 4. Background Ingestion -- dispatched to the dedicated
    # ingestion-worker container(s) via Celery/Redis, not run inline or
    # on a thread inside this (backend/API) process. `.delay()` pushes
    # the job and returns immediately; it does not wait for, or need,
    # the ingestion-worker to be reachable synchronously.
    if auto_ingest_web and discovered_web_urls:
        top_url = discovered_web_urls[0]
        try:
            ingest_url_task.delay(top_url)
            output_sections.append(f"*(Discovered source '{top_url}' queued for background indexing.)*")
        except Exception as e:
            # Broker unreachable, etc. -- research results still return
            # to the agent either way; ingestion is best-effort.
            output_sections.append(f"*(Could not queue '{top_url}' for indexing: {e})*")

    return "\n".join(output_sections) if output_sections else "No information found."
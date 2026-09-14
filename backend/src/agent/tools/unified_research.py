import threading
import asyncio
from typing import List, Optional

from src.agent.tools.retriever import search_ai_policy
from src.agent.tools.web_search import _get_client
from src.rag.stages.scraper import ingest_batch
from src.rag.stages.ingestion import ingest_documents

def _background_ingest(url: str):
    """Asynchronously ingests and embeds content without delaying the user."""
    try:
        docs = asyncio.run(ingest_batch([url]))
        if docs:
            ingest_documents([docs[0]], on_conflict="ignore")
    except Exception as e:
        print(f"[Async Ingestion Non-blocking Error]: {e}")

def unified_policy_research(
    queries: List[str],
    document_urls: Optional[List[str]] = None,
    auto_ingest_web: bool = True,
    max_web_results_per_query: int = 3,
) -> str:
    """
    Unified multi-tier research tool:
    1. Batch searches Neo4j policy chunks.
    2. Batch searches live internet via Tavily for queries lacking sufficient internal context.
    3. Automatically scrapes and ingests authoritative web URLs into Neo4j in the background.
    """
    if not queries and not document_urls:
        return "Please provide at least one query or document_url to research."

    output_sections: List[str] = []
    discovered_web_urls: List[str] = []

    # =========================================================================
    # STEP 1: Direct Document URL Lookup (if any specific URLs provided)
    # =========================================================================
    if document_urls:
        for url in document_urls:
            doc_result = search_ai_policy(document_url=url)
            output_sections.append(f"### Internal Document: {url}\n{doc_result}\n")

    # =========================================================================
    # STEP 2: Batch Query Neo4j Internal Knowledge
    # =========================================================================
    queries_needing_web: List[str] = []

    for q in queries:
        clean_q = q.strip()
        if not clean_q:
            continue
        
        internal_result = search_ai_policy(query=clean_q, top_k=2)
        
        # Check if internal database had solid hits
        if "No relevant information found" in internal_result or len(internal_result.strip()) < 80:
            queries_needing_web.append(clean_q)
        else:
            output_sections.append(f"### [Internal Knowledge] Query: '{clean_q}'\n{internal_result}\n")

    # If all internal searches succeeded, we can still run web search if the agent explicitly asked
    # Or fallback to web search for queries that had no internal records
    web_targets = queries_needing_web if queries_needing_web else queries[:2]

    # =========================================================================
    # STEP 3: Batch Web Search via Tavily
    # =========================================================================
    if web_targets:
        try:
            tavily = _get_client()
            for wq in web_targets:
                response = tavily.search(query=wq, search_depth="advanced", max_results=max_web_results_per_query)
                results = response.get("results", [])
                
                if results:
                    output_sections.append(f"### [Live Web Search] Query: '{wq}'")
                    for i, r in enumerate(results, 1):
                        url = r.get("url", "")
                        if url:
                            discovered_web_urls.append(url)
                        output_sections.append(
                            f"- Source {i}: {r.get('title', 'N/A')}\n"
                            f"  URL: {url}\n"
                            f"  Snippet: {r.get('content', '')}\n"
                        )
        except Exception as e:
            output_sections.append(f"[Web search warning: {e}]")

    # =========================================================================
    # STEP 4: Auto-Ingest Discovered Web URLs into Neo4j (Zero Extra LLM Hops!)
    # =========================================================================
    if auto_ingest_web and discovered_web_urls:
        top_url = discovered_web_urls[0]
        threading.Thread(target=_background_ingest, args=(top_url,), daemon=True).start()
        output_sections.append(f"*(Discovered source '{top_url}' queued for background indexing.)*")

    return "\n".join(output_sections) if output_sections else "No information found across internal knowledge or web."
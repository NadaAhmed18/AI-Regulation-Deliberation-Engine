"""
INGESTION TASKS — runs on the dedicated `ingestion-worker` container(s),
never on the `backend` (API) container.

This is the same scrape -> chunk -> embed -> graph-write pipeline that
used to run inline (fully blocking) in `learn_and_ingest_url`, then
moved to a background `threading.Thread` inside `research.py`. Now it
runs as a proper Celery task: retryable, observable (task state in
Redis), and executed by a worker process with its own independent
compute allocation instead of sharing the API container's.
"""

import asyncio
import logging

from celery import shared_task

from src.rag.stages.ingestion import ingest_documents
from src.rag.stages.scraper import ingest_batch

logger = logging.getLogger(__name__)


@shared_task(
    name="ingest_url",
    bind=True,
    # A scrape can fail for transient reasons (site rate-limiting, a
    # flaky network blip) -- retry a couple of times with backoff before
    # giving up, instead of silently dropping the job like the old
    # threading-based version did (its `except Exception: print(...)`
    # had no retry at all).
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=3,
)
def ingest_url_task(self, url: str) -> dict:
    """
    Scrapes `url`, chunks + embeds the content, and writes it into the
    Neo4j knowledge graph. Returns a small status dict (not meant to be
    awaited by the caller -- `research.py` calls `.delay(url)` and moves
    on immediately).
    """
    logger.info("Ingesting URL (attempt %d): %s", self.request.retries + 1, url)

    docs = asyncio.run(ingest_batch([url]))
    if not docs:
        logger.warning("No content extracted from %s", url)
        return {"url": url, "status": "empty", "ingested": False}

    result = ingest_documents([docs[0]], on_conflict="ignore")
    logger.info("Ingested %s: %s", url, result)
    return {"url": url, "status": "ok", "ingested": True, "detail": result}

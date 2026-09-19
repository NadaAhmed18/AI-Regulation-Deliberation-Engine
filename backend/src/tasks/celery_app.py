"""
CELERY APP — Ingestion Worker Task Queue

This is the piece that actually decouples ingestion compute from API
compute (see docker-compose.yaml's `ingestion-worker` service). Before
this, `research.py`'s auto-ingestion ran on a raw `threading.Thread`
inside the `backend` container -- non-blocking for the calling request,
but still consuming the exact same CPU/memory allocation
(`BACKEND_CPUS`/`BACKEND_MEMORY`) as the live API and discussion engine.

With this: `research.py` pushes a job onto Redis (`ingest_url_task.delay(url)`)
and returns immediately. A *separate* `ingestion-worker` container --
with its own `INGESTION_WORKER_CPUS`/`INGESTION_WORKER_MEMORY` and its
own replica count -- picks the job up and does the actual scraping/
chunking/embedding/graph-write work. Scaling ingestion throughput is
then `docker compose up -d --scale ingestion-worker=10`, which touches
nothing about the `backend` service, the databases, or their storage.

Uses the same Redis instance already in docker-compose.yaml (currently
only used by Langfuse), on a different logical DB index (1, vs.
Langfuse's typical default of 0) so the two don't share keys.
"""

import os

from celery import Celery

REDIS_AUTH = os.getenv("REDIS_AUTH", "redis123")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
CELERY_BROKER_DB = os.getenv("CELERY_BROKER_DB", "1")

CELERY_BROKER_URL = os.getenv(
    "CELERY_BROKER_URL",
    f"redis://:{REDIS_AUTH}@{REDIS_HOST}:{REDIS_PORT}/{CELERY_BROKER_DB}",
)

celery_app = Celery("ai_regulation_ingestion", broker=CELERY_BROKER_URL, backend=CELERY_BROKER_URL)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Ingestion jobs are fire-and-forget from the caller's perspective
    # (research.py doesn't wait on the result) -- results still get
    # stored in Redis briefly for observability/debugging, but expire
    # quickly so they don't accumulate.
    result_expires=3600,
    task_track_started=True,
    # One retryable network/scrape job shouldn't get lost if a worker
    # restarts mid-task (e.g. during a `docker compose up` redeploy).
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Task modules are imported here so `celery -A src.tasks.celery_app worker`
# discovers them without needing a separate `include=[...]` list to keep
# in sync.
import src.tasks.ingestion_tasks  # noqa: E402,F401

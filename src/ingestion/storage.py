"""
All filesystem writes for the ingestion pipeline live here - scraper.py stays
focused on orchestration, processor.py stays focused on parsing.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .config import MANIFEST_PATH, MIN_DOCUMENTS_REQUIRED, RAW_DATA_DIR
from .schemas import ScrapedDocumentSchema
from .utils import content_hash_filename


def ensure_output_dir() -> None:
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)


def save_document(document: ScrapedDocumentSchema) -> Path:
    output_path = RAW_DATA_DIR / content_hash_filename(document.url)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(document.model_dump(mode="json"), f, ensure_ascii=False, indent=2)
    return output_path


def write_manifest(total_saved: int) -> Path:
    manifest = {
        "total_documents": total_saved,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(RAW_DATA_DIR),
        "meets_minimum": total_saved >= MIN_DOCUMENTS_REQUIRED,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return MANIFEST_PATH
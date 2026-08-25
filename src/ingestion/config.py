"""
Paths and constants for the ingestion pipeline. Single source of truth so
scraper.py, loader.py, storage.py etc. don't each define their own copy.
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
SOURCES_FILE = BASE_DIR / "sources.yaml"
RAW_DATA_DIR = BASE_DIR / "src" / "data" / "raw"
MANIFEST_PATH = RAW_DATA_DIR / "_manifest.json"

MIN_BODY_CHARS = 150       # discard pages with less usable text than this
MIN_DOCUMENTS_REQUIRED = 50  # Week 1 brief's minimum acceptance criterion
DEFAULT_CONCURRENCY = 3
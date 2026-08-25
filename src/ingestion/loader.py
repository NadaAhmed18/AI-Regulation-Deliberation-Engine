"""
Loads and validates sources.yaml into a SourcesConfig. Kept dependency-free
from crawl4ai so config validation can run (and be tested) without a browser.
"""
from __future__ import annotations

import yaml

from .config import SOURCES_FILE
from .schemas import SourcesConfig


def load_sources(path=SOURCES_FILE) -> SourcesConfig:
    if not path.exists():
        raise FileNotFoundError(f"Sources file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return SourcesConfig.model_validate(data)
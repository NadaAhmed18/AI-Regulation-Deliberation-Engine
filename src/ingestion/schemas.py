"""
Canonical schemas for the ingestion pipeline.

Fixes applied vs. the original RetrievalSchema.py:
- `source_type` and `category` are now typed with the actual SourceType /
  SourceCategory enums instead of plain `str`, so a typo in sources.yaml
  (e.g. "policy_document" which isn't a real SourceType) fails loudly at
  load time instead of silently passing through as an unvalidated string.
- `category` is now Optional to match how SourceItem is actually used
  (some sources, like general news aggregators, don't cleanly fit one
  category) - the original had it required with no default.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .RetrievalEnum import ScrapeStatus, SourceCategory, SourceType


class ScrapedDocumentSchema(BaseModel):
    url: str
    domain: str
    title: Optional[str] = None
    body: str
    links: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    source_name: str
    source_type: SourceType
    category: Optional[SourceCategory] = None
    scraped_at: datetime
    status: ScrapeStatus = ScrapeStatus.SUCCESS
    error: Optional[str] = None


class SourceItem(BaseModel):
    name: str
    source_type: SourceType
    category: Optional[SourceCategory] = None
    urls: List[str]
    max_depth: int = 2
    max_pages: Optional[int] = None


class SourcesConfig(BaseModel):
    sources: List[SourceItem]

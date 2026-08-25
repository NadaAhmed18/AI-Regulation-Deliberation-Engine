from typing import Any
from pydantic import BaseModel, Field


class ScrapedDocumentSchema(BaseModel):
    url: str
    body: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    related_links: list[str] = Field(default_factory=list)
    domain: str

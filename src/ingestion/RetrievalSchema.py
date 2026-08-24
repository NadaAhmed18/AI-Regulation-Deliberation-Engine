from datetime import datetime, timezone
from enum import Enum
from .RetrivalEnum import ContentTypeEnum

from pydantic import BaseModel, Field




class UrlDocument(BaseModel):
    id: str = Field(..., min_length=1)
    source_url: str = Field(..., min_length=1)
    source_type: str = Field(..., min_length=1)

    title: str | None = None

    fetched_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    content_type: ContentTypeEnum

    raw_text: str = Field(..., min_length=1)


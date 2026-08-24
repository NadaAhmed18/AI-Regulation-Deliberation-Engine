from pydantic import BaseModel,Field
from datetime import datetime


class RawDocument:

    id: str=Field(...,min_lenght=1)
    source_url: str=Field(...,min_lenght=1)
    source_type: str=Field(...,min_lenght=1)

    title: str = None
    fetched_at: datetime= Field(default=datetime.utcnow())
    content_type: str  = Field(...,min_lenght=1)
    
    raw_text: str = Field(...,min_lenght=1)  # extracted plain text for pdfs
    raw_pdf_path: str = None

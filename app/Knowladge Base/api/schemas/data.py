class RawDocument:
    id: str
    source_url: str
    source_type: str
    title: str | None
    fetched_at: str
    content_type: str  # "html" or "pdf"
    raw_html: str | None  # None for pdf (binary saved separately)
    raw_text: str | None  # extracted plain text for pdfs
    raw_pdf_path: str | None
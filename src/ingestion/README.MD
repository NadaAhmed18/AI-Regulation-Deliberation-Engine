# Theme 1 — Ingestion Module (AI Regulation & Democratic Values)

**Target region:** Egypt, compared against the EU AI Act as reference framework.

This document explains what the ingestion codebase does, how each file works,
and how to run it end to end.

---

## 1. What this module does

It's the **data collection stage** of the Week 1 RAG pipeline:

```
sources.yaml  →  crawl4ai  →  clean text  →  validate (Pydantic)  →  data/raw/*.json
```

You give it a list of seed URLs grouped by category (EU legal text, Egyptian
government sources, civil society reports, industry news, academic research).
It crawls each one (following internal links up to a configurable depth),
strips out junk (nav bars, scripts, ads), validates the result against a
strict schema, and saves **one JSON file per page** to `src/data/raw/`.

This is *only* collection — cleaning/chunking/embedding/storage in Postgres
happen in later pipeline stages, not in this module.

---

## 2. Folder structure

```
theme1-ingestion/
├── sources.yaml                    # every seed URL, grouped by source
├── README.md                       # this file
└── src/
    ├── data/
    │   └── raw/                    # OUTPUT: one JSON file per scraped page
    └── ingestion/
        ├── config.py                # paths & constants
        ├── utils.py                 # pure helper functions (URL/text/filename)
        ├── loader.py                 # reads + validates sources.yaml
        ├── crawler_config.py         # crawl4ai browser/crawl settings
        ├── processor.py              # turns a raw crawl result into a validated document
        ├── storage.py                 # writes documents + manifest to disk
        ├── scraper.py                 # orchestrator - the file you actually run
        ├── RetrievalEnum.py           # SourceType / SourceCategory / ScrapeStatus enums
        ├── schemas.py                  # Pydantic models (ScrapedDocumentSchema, SourceItem, SourcesConfig)
        ├── RetrivalEnum.py             # old import path, kept for compatibility → delete later
        └── RetrievalSchema.py          # old import path, kept for compatibility → delete later
```

**Why it's split this way:** each file has exactly one job, so you can change
one part (e.g. how a page gets cleaned) without touching how crawling or
saving works. `config.py`, `utils.py`, and `loader.py` don't import crawl4ai
at all, so you can test URL handling and `sources.yaml` validation without
starting a browser.

---

## 3. How each file works

### `sources.yaml`
The only file you edit to add/remove sources. Each entry is a **source
group**:
```yaml
sources:
  - name: "Egypt National AI & Data Governance"
    source_type: "government"        # must match RetrievalEnum.SourceType
    category: "national_strategy"    # must match RetrievalEnum.SourceCategory
    max_depth: 1                     # how many link-hops to follow from each seed URL
    max_pages: 10                    # crawl budget per seed URL
    urls:
      - "https://mcit.gov.eg/en/Artificial_Intelligence"
```
`source_type` and `category` aren't free text — they're validated against the
enums in `RetrievalEnum.py`. A typo here makes the whole run fail immediately
with a clear error, instead of silently saving bad data.

### `config.py`
Just constants: where `sources.yaml` lives, where output goes
(`src/data/raw/`), the minimum body length to keep a page (150 chars —
shorter than that is almost always a blank/JS-only page), and the
50-document minimum from the Week 1 brief.

### `utils.py`
Small, dependency-free functions used everywhere else:
- `normalize_url()` — strips trailing slashes so the same page isn't saved twice under two URLs.
- `get_domain()` — pulls out `mcit.gov.eg` from a full URL.
- `clean_text()` — collapses whitespace/newlines.
- `content_hash_filename()` — turns a URL into a stable filename like `mcit_gov_eg__e91fbe833d41ad18.json`, so re-scraping the same URL overwrites the same file instead of creating duplicates.
- `extract_links()` / `extract_metadata()` — pull structured info out of crawl4ai's result object.

### `loader.py`
Reads `sources.yaml`, parses it with `yaml.safe_load`, and validates it into
a `SourcesConfig` object via Pydantic. If a source group has an invalid
`source_type`, this is where it fails — before any crawling starts.

### `crawler_config.py`
Builds crawl4ai's two config objects:
- `BrowserConfig` — headless browser settings (text-only mode, no visible window).
- `CrawlerRunConfig` — what to strip (`script`, `nav`, `footer`...), that we
  want plain text only, and the `BFSDeepCrawlStrategy` (breadth-first crawl:
  visit the seed page, then its direct links, then their links, up to
  `max_depth`, capped at `max_pages`).

### `processor.py`
Takes one raw result object from crawl4ai and turns it into a
`ScrapedDocumentSchema`, or returns `None` if the page should be discarded
(duplicate URL, empty body, crawl failure). This is the function most likely
to need tweaking as you find real-world edge cases (e.g. a site that needs a
different field for its body text).

### `storage.py`
The only file that touches the filesystem for output:
- `save_document()` — writes one page as one JSON file.
- `write_manifest()` — after a full run, writes `_manifest.json` with the
  total document count and whether it met the 50-document minimum.

### `scraper.py` — the orchestrator
This is what you actually run. `Theme1Scraper.run()`:
1. Loads and validates `sources.yaml` (via `loader.py`).
2. Opens one crawl4ai browser session for the whole run.
3. For each source group, crawls every seed URL (with a concurrency limit of
   3 simultaneous seeds, via `asyncio.Semaphore`, so it doesn't hammer any
   site or open too many browser tabs at once).
4. For every page the crawler visits, hands the raw result to `processor.py`,
   then saves valid ones via `storage.py`.
5. Writes the manifest and logs a warning if you're under 50 documents.

### `RetrievalEnum.py` / `schemas.py`
The validation layer:
- `SourceType` — `legal`, `government`, `civil_society`, `industry`,
  `research`, `international`, `official`, `social_opinion`, `other`.
- `SourceCategory` — finer-grained: `regulation`, `national_strategy`,
  `data_protection`, `digital_rights`, `technology`, `academic`, etc.
- `ScrapedDocumentSchema` — the shape every saved JSON file must match
  (url, domain, title, body, links, metadata, source_name, source_type,
  category, scraped_at, status, error).
- `SourceItem` / `SourcesConfig` — the shape `sources.yaml` must match.

---

## 4. How to run it

### One-time setup
```bash
pip install crawl4ai pyyaml pydantic python-dotenv
crawl4ai-setup     # installs the headless browser crawl4ai uses - run once
```

### Sanity-check the config (no crawling, no browser)
```bash
cd theme1-ingestion
python -c "from src.ingestion.loader import load_sources; print(len(load_sources().sources), 'source groups OK')"
```

### Run the actual scraper
```bash
python -m src.ingestion.scraper
```
Must be run as a module (`-m`) from the project root (where `sources.yaml`
lives) — the files use relative imports (`from .config import ...`), which
only work when Python treats `src/ingestion` as a package, not when you run
`python src/ingestion/scraper.py` directly.

### What you'll see
Console logs for every seed URL and every page saved, e.g.:
```
2026-08-25 ... INFO Crawling [Egypt National AI & Data Governance] seed: https://mcit.gov.eg/en/Artificial_Intelligence
2026-08-25 ... INFO   [1] saved https://mcit.gov.eg/en/Artificial_Intelligence -> mcit_gov_eg__e91fbe833d41ad18.json
...
2026-08-25 ... INFO Collection finished. Total documents: 63
```

### Output
- `src/data/raw/<domain>__<hash>.json` — one file per page, see format below.
- `src/data/raw/_manifest.json` — run summary:
  ```json
  {"total_documents": 63, "run_at": "...", "output_dir": "...", "meets_minimum": true}
  ```

---

## 5. Output format (one file per page)

```json
{
  "url": "https://mcit.gov.eg/en/Artificial_Intelligence",
  "domain": "mcit.gov.eg",
  "title": "National Council for Artificial Intelligence",
  "body": "cleaned plain-text content of the page...",
  "links": ["https://mcit.gov.eg/...", "..."],
  "metadata": {"description": "...", "language": "en"},
  "source_name": "Egypt National AI & Data Governance",
  "source_type": "government",
  "category": "national_strategy",
  "scraped_at": "2026-08-25T12:00:00+00:00",
  "status": "success",
  "error": null
}
```
If a page fails to crawl, it's still saved with `"status": "failed"` and an
`"error"` message instead of being silently dropped — useful for debugging
which sources need attention.

---

## 6. Why files are saved one-per-page, not as one big list

- **Concurrency-safe** — multiple pages are crawled at once (`asyncio` +
  semaphore); separate files mean no locking is needed to avoid two
  coroutines corrupting a shared list/file at the same time.
- **Resumable** — the brief requires the collection process to be
  "repeatable and re-runnable." Since filenames are hashed from the URL,
  re-running after a crash or interruption just fills in what's missing
  instead of starting over or duplicating pages.
- **Smaller blast radius** — a crash mid-write corrupts at most one file,
  not the entire collected dataset.

The next pipeline stage (`cleaner.py`, not part of this module) reads all
files in `src/data/raw/*.json` as a batch — so downstream code still treats
them as one dataset, it's just not physically one file on disk.

---

## 7. Known limitations

- `eur-lex.europa.eu`'s regulation page is JS-heavy; if its saved `body`
  comes back mostly empty, swap in a plain-text/print mirror URL instead.
- `max_pages` / `max_depth` are a crawl *budget*, not a guarantee of that many
  *relevant* documents — always check `_manifest.json`'s total against the
  50-document minimum, and spot-check a few saved files for quality.
- The Egypt AI Strategy source is a PDF; crawl4ai's text extraction on PDFs
  can be inconsistent — if that file's body looks garbled, consider fetching
  and parsing it separately with `pdfplumber`.
- `RetrivalEnum.py` and `RetrievalSchema.py` are compatibility shims for an
  old import path. Once everything imports from `RetrievalEnum`/`schemas`
  directly, delete these two files.
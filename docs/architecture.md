# Architecture

## High-level data flow

```
Input paper / BibTeX / DOI list / raw text
        ↓
Extraction layer
   • pdf_text.py        (pymupdf → pdfplumber → pypdf fallback)
   • bibliography_detector.py
   • reference_parser.py
   • bibtex_parser.py
        ↓
Reference normalization (Pydantic Reference)
        ↓
Metadata resolver pipeline
   • CrossrefResolver
   • OpenAlexResolver
   • SemanticScholarResolver
   • ArxivResolver
   → ResolvedWork[] with confidence
        ↓
OA PDF locator
   • Unpaywall
   • arXiv direct
   • OpenAlex OA locations
   • Semantic Scholar openAccessPdf
        ↓
License policy
   • Allowlist: arXiv, Unpaywall OA, OpenAlex OA, S2 OA, publisher OA, repos
   • Denylist: Sci-Hub, LibGen, paywall-bypass mirrors, login-required pages
        ↓
PDF downloader
   • Streaming httpx
   • Content-Type + %PDF- magic byte validation
   • Deterministic filename: YEAR_FirstAuthor_ShortTitle_DOIHash.pdf
        ↓
Manifest (manifest.json) + Markdown report (report.md)
```

## Module layout

```
src/bibpdf_mcp/
├── __init__.py
├── server.py              # MCP server (FastMCP, stdio)
├── cli.py                 # Typer CLI
├── config.py              # pydantic-settings
├── models.py              # Reference, ResolvedWork, PdfCandidate, DownloadResult, RunManifest
├── logging_config.py      # rich-based logging on stderr
├── extraction/
│   ├── pdf_text.py
│   ├── bibliography_detector.py
│   ├── reference_parser.py
│   └── bibtex_parser.py
├── resolvers/
│   ├── base.py
│   ├── crossref.py
│   ├── openalex.py
│   ├── semantic_scholar.py
│   ├── arxiv.py
│   └── resolver_pipeline.py
├── acquisition/
│   ├── unpaywall.py
│   ├── pdf_locator.py
│   ├── license_policy.py
│   └── downloader.py
├── storage/
│   ├── cache.py           # SQLAlchemy 2.0 SQLite cache
│   ├── manifest.py
│   └── filename_policy.py
└── reports/
    ├── markdown_report.py
    └── json_report.py
```

## Concurrency

All network-bound code is async (`httpx.AsyncClient`). Concurrency is bounded by:

- `MAX_CONCURRENT_REQUESTS` from settings (default 5)
- Per-API `aiolimiter` rate limits to respect each provider's polite-pool conventions

## Caching

A single SQLite database (`cache/bibpdf.sqlite` by default) stores raw API responses
keyed by `(source, key)`. Resolvers and the locator both read-through the cache to
avoid re-fetching identical lookups across runs.

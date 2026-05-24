# bibliography-pdf-mcp

A local Python-based **Model Context Protocol (MCP)** server that, given a research paper PDF (or BibTeX / DOI list / raw text), extracts every bibliography entry, resolves metadata against scholarly APIs, locates **legally and publicly available** open-access PDFs, and downloads them with deterministic filenames.

> **Safety**: this tool only downloads PDFs from public open-access sources (arXiv, Unpaywall OA locations, OpenAlex/Semantic Scholar OA records, publisher OA links, institutional repositories). It does **not** bypass paywalls, scrape Sci-Hub, evade CAPTCHAs, or use credentialed access.

## Quickstart

```bash
git clone git@github.com:ljohri/bib-papers-extractor.git
cd bib-papers-extractor

# Install uv (if needed): https://docs.astral.sh/uv/getting-started/installation/
uv sync
cp .env.example .env

# CLI
uv run bibpdf --help
uv run bibpdf process-paper data/input/paper.pdf --output-dir data/output/run-001

# Run the MCP server (stdio)
uv run python -m bibpdf_mcp.server
```

## What it does

```
Input paper / .bib / DOIs
        │
        ▼
  Extraction layer  ──► Reference[] (Pydantic)
        │
        ▼
  Resolver pipeline  ──► ResolvedWork[] + confidence
   (Crossref, OpenAlex, Semantic Scholar, arXiv)
        │
        ▼
  PDF locator         ──► PdfCandidate[]
   (Unpaywall, arXiv, OpenAlex OA, S2 OA)
        │
        ▼
  License policy      ──► allowed candidates only
        │
        ▼
  Downloader          ──► YEAR_FirstAuthor_ShortTitle_DOIHash.pdf
        │
        ▼
  manifest.json + report.md
```

## MCP tools exposed

| Tool | Purpose |
|---|---|
| `extract_references_from_pdf` | Extract bibliography entries from a paper PDF |
| `parse_bibtex_file` | Parse a BibTeX file into the internal Reference model |
| `resolve_references` | Resolve metadata via Crossref/OpenAlex/S2/arXiv |
| `find_public_pdfs` | Discover legal OA PDFs for resolved works |
| `download_public_pdfs` | Download approved candidates with deterministic filenames |
| `process_paper_bibliography` | End-to-end pipeline: PDF → references → resolved → OA PDFs → manifest+report |

## Documentation

See [`docs/`](docs/):

- [`architecture.md`](docs/architecture.md) — module layout & data flow
- [`mcp-tools.md`](docs/mcp-tools.md) — tool schemas and examples
- [`installation.md`](docs/installation.md) — install & first run
- [`claude-desktop-setup.md`](docs/claude-desktop-setup.md) — Claude Desktop config
- [`cursor-setup.md`](docs/cursor-setup.md) — Cursor config
- [`api-resolution-strategy.md`](docs/api-resolution-strategy.md) — resolver order, confidence, retries
- [`pdf-acquisition-policy.md`](docs/pdf-acquisition-policy.md) — what we will and will not download
- [`data-model.md`](docs/data-model.md) — Pydantic models reference
- [`docker.md`](docs/docker.md) — Docker build & run
- [`uv-development.md`](docs/uv-development.md) — `uv` development workflow
- [`troubleshooting.md`](docs/troubleshooting.md) — common issues
- [`limitations.md`](docs/limitations.md) — known limits and non-goals

## Development

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ruff format .
```

## License

MIT — see [`LICENSE`](LICENSE).

# MCP tools reference

The server exposes six tools over stdio. Inputs and outputs use plain JSON.

---

## Path defaults (MCP server)

Tools that accept file or directory paths treat arguments as **optional**. When
omitted, the server uses environment variables (or `.env` in the server `cwd`):

| Variable | Used when |
|----------|-----------|
| `DEFAULT_INPUT_PDF` | `pdf_path` omitted on `extract_references_from_pdf` / `process_paper_bibliography` |
| `DEFAULT_INPUT_BIBTEX` | `bibtex_path` omitted on `parse_bibtex_file` |
| `DEFAULT_OUTPUT_DIR` | `output_dir` omitted on `download_public_pdfs` / `process_paper_bibliography` |

Explicit tool arguments **always override** these defaults. If a path is omitted
and the matching default is unset, the tool returns a clear error.

Set defaults in Claude Desktop / Cursor MCP config `env` block or in `.env`.

---

## `extract_references_from_pdf`

**Input**

```json
{ "pdf_path": "/data/input/paper.pdf" }
```

`pdf_path` is optional when `DEFAULT_INPUT_PDF` is configured.

**Output**

```json
{
  "pdf_path": "/data/input/paper.pdf",
  "references": [
    {
      "id": "ref-001",
      "raw": "Vaswani et al. 2017. Attention is all you need. NeurIPS.",
      "title": "Attention is all you need",
      "authors": ["Vaswani"],
      "year": 2017,
      "doi": null,
      "arxiv_id": "1706.03762"
    }
  ],
  "count": 1
}
```

**Failure modes**: file not found, unreadable PDF, no bibliography section detected.

---

## `parse_bibtex_file`

**Input**

```json
{ "bibtex_path": "/data/input/refs.bib" }
```

`bibtex_path` is optional when `DEFAULT_INPUT_BIBTEX` is configured.

**Output**: `{ "bibtex_path": "...", "references": [...], "count": N }` using the same `Reference` shape as above; `bibtex_key` populated.

**Failure modes**: malformed BibTeX, file not found.

---

## `resolve_references`

**Input**

```json
{
  "references": [ { "id": "ref-001", "raw": "...", "title": "...", "year": 2017 } ],
  "strategy": "balanced"
}
```

`strategy ∈ {"fast", "balanced", "deep"}` — controls how many fallbacks the resolver pipeline tries.

**Output**: `{ "resolved": [ResolvedWork], "unresolved": [Reference] }`.

**Resolver precedence**:
DOI exact → arXiv exact → OpenAlex title → Crossref title → Semantic Scholar title → unresolved.

---

## `find_public_pdfs`

**Input**: `{ "resolved_references": [ResolvedWork] }`.

**Output**

```json
{
  "pdf_candidates": [
    {
      "reference_id": "ref-001",
      "url": "https://arxiv.org/pdf/1706.03762.pdf",
      "source": "arxiv",
      "license": null,
      "is_oa": true,
      "confidence": 0.98
    }
  ]
}
```

Sources: `unpaywall | arxiv | openalex | semantic_scholar | publisher_oa | repository`.

---

## `download_public_pdfs`

**Input**: `{ "pdf_candidates": [...], "output_dir": "/data/output/pdfs" }`.

`output_dir` is optional when `DEFAULT_OUTPUT_DIR` is configured.

**Output**: `{ "output_dir": "...", "downloaded": [...], "failed": [...], "skipped": [...] }`.

**Behavior**: only downloads candidates approved by `license_policy.py`; rejects HTML
landing pages (unless explicitly allowed); validates the first bytes for `%PDF-`;
writes deterministic filenames `YEAR_FirstAuthor_ShortTitle_DOIHash.pdf`.

---

## `process_paper_bibliography`

**End-to-end pipeline tool.**

**Input**

```json
{
  "pdf_path": "/data/input/source-paper.pdf",
  "output_dir": "/data/output/run-001",
  "strategy": "balanced"
}
```

Both `pdf_path` and `output_dir` are optional when `DEFAULT_INPUT_PDF` and
`DEFAULT_OUTPUT_DIR` are set in the server environment.

**Output**

```json
{
  "run_id": "run-001",
  "pdf_path": "/data/input/source-paper.pdf",
  "output_dir": "/data/output/run-001",
  "references_found": 52,
  "resolved": 45,
  "pdfs_found": 31,
  "pdfs_downloaded": 29,
  "manifest_path": "/data/output/run-001/manifest.json",
  "report_path": "/data/output/run-001/report.md"
}
```

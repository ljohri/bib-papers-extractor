# MCP tools reference

The server exposes six tools over stdio. Inputs and outputs use plain JSON.

---

## `extract_references_from_pdf`

**Input**

```json
{ "pdf_path": "/data/input/paper.pdf" }
```

**Output**

```json
{
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

**Output**: `{ "references": [...] }` using the same `Reference` shape as above; `bibtex_key` populated.

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

**Output**: `{ "downloaded": [DownloadResult], "failed": [DownloadResult] }`.

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

**Output**

```json
{
  "run_id": "run-001",
  "references_found": 52,
  "resolved": 45,
  "pdfs_found": 31,
  "pdfs_downloaded": 29,
  "manifest_path": "/data/output/run-001/manifest.json",
  "report_path": "/data/output/run-001/report.md"
}
```

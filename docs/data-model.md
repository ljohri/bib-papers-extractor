# Data model

All internal entities are typed Pydantic v2 models defined in
[`src/bibpdf_mcp/models.py`](../src/bibpdf_mcp/models.py).

## `Reference`

A bibliography entry, possibly partially parsed.

| Field         | Type           | Notes |
|---|---|---|
| `id`          | `str`          | Stable per-run id (e.g. `ref-001`). |
| `raw`         | `str`          | Original reference string from the PDF/BibTeX. |
| `title`       | `str \| None`  | Cleaned title, if extracted. |
| `authors`     | `list[str]`    | Author display strings. |
| `year`        | `int \| None`  | 4-digit year. |
| `doi`         | `str \| None`  | Lowercase DOI without `https://doi.org/` prefix. |
| `arxiv_id`    | `str \| None`  | e.g. `1706.03762`. |
| `journal`     | `str \| None`  | |
| `venue`       | `str \| None`  | Conference/workshop/proceedings name. |
| `bibtex_key`  | `str \| None`  | Set when sourced from a `.bib` file. |

## `ResolvedWork`

A resolver match for a `Reference`.

| Field                 | Type           | Notes |
|---|---|---|
| `reference_id`        | `str`          | Foreign key to `Reference.id`. |
| `title`               | `str`          | Canonical resolved title. |
| `authors`             | `list[str]`    | |
| `year`                | `int \| None`  | |
| `doi`, `arxiv_id`     | `str \| None`  | |
| `openalex_id`         | `str \| None`  | e.g. `W2964237974`. |
| `semantic_scholar_id` | `str \| None`  | |
| `url`                 | `str \| None`  | Canonical landing page. |
| `source`              | `str`          | `crossref \| openalex \| semantic_scholar \| arxiv` |
| `confidence`          | `float [0,1]`  | See `api-resolution-strategy.md`. |
| `raw_metadata`        | `dict`         | Full resolver payload for audit. |

## `PdfCandidate`

A discovered URL pointing to a (claimed) OA PDF.

| Field           | Type         | Notes |
|---|---|---|
| `reference_id`  | `str`        | |
| `url`           | `str`        | Must be `https://`. |
| `source`        | `str`        | `unpaywall \| arxiv \| openalex \| semantic_scholar \| publisher_oa \| repository` |
| `license`       | `str\|None`  | e.g. `cc-by-4.0`. |
| `is_oa`         | `bool`       | |
| `confidence`    | `float`      | |
| `evidence`      | `dict`       | Source-specific provenance. |

## `DownloadResult`

| Field            | Type           | Notes |
|---|---|---|
| `reference_id`   | `str`          | |
| `url`            | `str`          | |
| `status`         | `str`          | `downloaded \| skipped \| failed` |
| `file_path`      | `str \| None`  | Path written on success. |
| `bytes_written`  | `int \| None`  | |
| `content_type`   | `str \| None`  | |
| `error`          | `str \| None`  | Set on failures/skips. |

## `RunManifest`

Top-level object persisted to `manifest.json`. Aggregates references, resolved
works, candidates, downloads, and a `RunSummary` of counts.

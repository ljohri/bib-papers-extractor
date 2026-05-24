"""Internal Pydantic data models shared across the pipeline."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Reference(BaseModel):
    """A single bibliography entry, possibly partially parsed."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Stable per-run identifier for this reference.")
    raw: str = Field(description="The raw reference string as it appeared in the source.")
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    journal: str | None = None
    venue: str | None = None
    bibtex_key: str | None = None


class ResolvedWork(BaseModel):
    """A resolver hit: a single candidate match for a Reference."""

    model_config = ConfigDict(extra="ignore")

    reference_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    openalex_id: str | None = None
    semantic_scholar_id: str | None = None
    url: str | None = None
    source: str = Field(description="Resolver source: crossref|openalex|semantic_scholar|arxiv")
    confidence: float = Field(ge=0.0, le=1.0)
    raw_metadata: dict[str, Any] = Field(default_factory=dict)


class PdfCandidate(BaseModel):
    """A discovered URL pointing to a (claimed) open-access PDF for a reference."""

    model_config = ConfigDict(extra="ignore")

    reference_id: str
    url: str
    source: str = Field(
        description="unpaywall|arxiv|openalex|semantic_scholar|publisher_oa|repository"
    )
    license: str | None = None
    is_oa: bool = False
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    evidence: dict[str, Any] = Field(default_factory=dict)


class DownloadResult(BaseModel):
    """The outcome of attempting to download a single PdfCandidate."""

    model_config = ConfigDict(extra="ignore")

    reference_id: str
    url: str
    status: str = Field(description="downloaded|skipped|failed")
    file_path: str | None = None
    bytes_written: int | None = None
    content_type: str | None = None
    error: str | None = None


class RunSummary(BaseModel):
    """Aggregate counts for a single end-to-end pipeline run."""

    references_found: int = 0
    references_resolved: int = 0
    pdfs_found: int = 0
    pdfs_downloaded: int = 0
    pdfs_failed: int = 0
    pdfs_skipped: int = 0


class RunManifest(BaseModel):
    """Top-level manifest persisted to manifest.json after a full run."""

    model_config = ConfigDict(extra="ignore")

    run_id: str
    source_path: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    strategy: str = "balanced"
    summary: RunSummary = Field(default_factory=RunSummary)
    references: list[Reference] = Field(default_factory=list)
    resolved: list[ResolvedWork] = Field(default_factory=list)
    pdf_candidates: list[PdfCandidate] = Field(default_factory=list)
    downloads: list[DownloadResult] = Field(default_factory=list)
    skipped: list[dict[str, Any]] = Field(default_factory=list)
    low_confidence: list[dict[str, Any]] = Field(default_factory=list)


__all__ = [
    "Reference",
    "ResolvedWork",
    "PdfCandidate",
    "DownloadResult",
    "RunSummary",
    "RunManifest",
]

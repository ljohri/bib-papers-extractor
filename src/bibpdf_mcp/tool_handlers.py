"""Shared implementations for MCP tools and A2A skills."""

from __future__ import annotations

from typing import Any

from . import pipeline
from .config import get_settings
from .models import PdfCandidate, Reference, ResolvedWork


def extract_references_from_pdf(pdf_path: str) -> dict[str, Any]:
    settings = get_settings()
    path = settings.resolve_file_path(pdf_path, label="PDF")
    refs = pipeline.extract_references_from_pdf(path)
    return {
        "pdf_path": str(path),
        "references": [r.model_dump(mode="json") for r in refs],
        "count": len(refs),
    }


def parse_bibtex_file(bibtex_path: str) -> dict[str, Any]:
    settings = get_settings()
    path = settings.resolve_file_path(bibtex_path, label="BibTeX file")
    refs = pipeline.parse_bibtex_file(path)
    return {
        "bibtex_path": str(path),
        "references": [r.model_dump(mode="json") for r in refs],
        "count": len(refs),
    }


async def resolve_references(
    references: list[dict[str, Any]],
    strategy: str = "balanced",
) -> dict[str, Any]:
    refs = [Reference.model_validate(r) for r in references]
    resolved = await pipeline.resolve_references(refs, strategy=strategy)
    resolved_ids = {w.reference_id for w in resolved}
    unresolved = [r for r in refs if r.id not in resolved_ids]
    return {
        "resolved": [w.model_dump(mode="json") for w in resolved],
        "unresolved": [r.model_dump(mode="json") for r in unresolved],
    }


async def find_public_pdfs(resolved_references: list[dict[str, Any]]) -> dict[str, Any]:
    works = [ResolvedWork.model_validate(w) for w in resolved_references]
    cands = await pipeline.find_public_pdfs(works)
    return {
        "pdf_candidates": [c.model_dump(mode="json") for c in cands],
        "count": len(cands),
        "oa_count": sum(1 for c in cands if c.is_oa),
    }


async def download_public_pdfs(
    pdf_candidates: list[dict[str, Any]],
    output_dir: str | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    out = settings.resolve_output_dir(output_dir)
    cands = [PdfCandidate.model_validate(c) for c in pdf_candidates]
    results = await pipeline.download_public_pdfs(cands, out)
    return {
        "output_dir": str(out),
        "downloaded": [r.model_dump(mode="json") for r in results if r.status == "downloaded"],
        "failed": [r.model_dump(mode="json") for r in results if r.status == "failed"],
        "skipped": [r.model_dump(mode="json") for r in results if r.status == "skipped"],
    }


async def process_paper_bibliography(
    pdf_path: str,
    output_dir: str | None = None,
    strategy: str = "balanced",
) -> dict[str, Any]:
    settings = get_settings()
    pdf = settings.resolve_file_path(pdf_path, label="PDF")
    out = settings.resolve_output_dir(output_dir)
    return await pipeline.process_paper_bibliography(pdf, out, strategy=strategy)

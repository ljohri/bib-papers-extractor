"""High-level orchestration shared by the CLI and the MCP server.

This is the single source of truth for the "pipeline functions" that map 1:1
onto MCP tools and CLI subcommands. Both layers are thin adapters over these
async functions.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .acquisition.downloader import download_candidates
from .acquisition.pdf_locator import find_pdfs
from .config import get_settings
from .extraction.bibliography_detector import find_bibliography_section
from .extraction.bibtex_parser import parse_bibtex_file as _parse_bibtex_file
from .extraction.pdf_text import extract_text
from .extraction.reference_parser import parse_references_from_text
from .logging_config import get_logger
from .models import (
    DownloadResult,
    PdfCandidate,
    Reference,
    ResolvedWork,
    RunManifest,
    RunSummary,
)
from .reports.json_report import write_json_report
from .reports.markdown_report import write_markdown_report
from .resolvers.resolver_pipeline import resolve_all
from .storage.cache import JsonCache
from .storage.manifest import write_manifest

log = get_logger(__name__)


# --- Caching ---------------------------------------------------------------


def _get_cache() -> JsonCache:
    settings = get_settings()
    return JsonCache(settings.cache_db_path)


# --- Tool 1: extract_references_from_pdf ----------------------------------


def extract_references_from_pdf(pdf_path: str | Path) -> list[Reference]:
    """Extract bibliography entries from a paper PDF."""
    full_text = extract_text(pdf_path)
    bib_text = find_bibliography_section(full_text)
    if not bib_text:
        log.warning("No bibliography section detected in %s", pdf_path)
        return []
    return parse_references_from_text(bib_text)


# --- Tool 2: parse_bibtex_file --------------------------------------------


def parse_bibtex_file(bibtex_path: str | Path) -> list[Reference]:
    return _parse_bibtex_file(bibtex_path)


# --- Tool 3: resolve_references --------------------------------------------


async def resolve_references(
    references: Iterable[Reference],
    *,
    strategy: str = "balanced",
) -> list[ResolvedWork]:
    cache = _get_cache()
    return await resolve_all(references, strategy=strategy, cache=cache)


# --- Tool 4: find_public_pdfs ----------------------------------------------


async def find_public_pdfs(
    resolved: Iterable[ResolvedWork],
) -> list[PdfCandidate]:
    cache = _get_cache()
    return await find_pdfs(resolved, cache=cache)


# --- Tool 5: download_public_pdfs ------------------------------------------


async def download_public_pdfs(
    candidates: Iterable[PdfCandidate],
    output_dir: str | Path,
    *,
    works: dict[str, ResolvedWork] | None = None,
) -> list[DownloadResult]:
    return await download_candidates(candidates, output_dir, works=works)


# --- Tool 6: process_paper_bibliography (end-to-end) -----------------------


async def process_paper_bibliography(
    pdf_path: str | Path,
    output_dir: str | Path,
    *,
    strategy: str = "balanced",
    run_id: str | None = None,
) -> dict[str, Any]:
    """End-to-end pipeline. Writes manifest.json + report.md and returns a summary dict."""
    settings = get_settings()
    settings.ensure_dirs()

    out_dir = Path(output_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir = out_dir / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    rid = run_id or _build_run_id(pdf_path)
    started = datetime.now(UTC)
    log.info("[run %s] starting end-to-end pipeline for %s", rid, pdf_path)

    references = extract_references_from_pdf(pdf_path)
    log.info("[run %s] extracted %d references", rid, len(references))

    resolved: list[ResolvedWork] = []
    candidates: list[PdfCandidate] = []
    downloads: list[DownloadResult] = []
    low_confidence: list[dict[str, Any]] = []
    threshold = settings.auto_download_confidence_threshold

    if references:
        resolved = await resolve_references(references, strategy=strategy)
        log.info("[run %s] resolved %d references", rid, len(resolved))

        # Partition resolved works by confidence threshold.
        high = [w for w in resolved if w.confidence >= threshold]
        low = [w for w in resolved if w.confidence < threshold]
        for w in low:
            ref = next((r for r in references if r.id == w.reference_id), None)
            low_confidence.append(
                {
                    "reference_id": w.reference_id,
                    "reference_raw": ref.raw if ref else "",
                    "candidate_title": w.title,
                    "confidence": w.confidence,
                    "action": f"skipped (below threshold {threshold:.2f})",
                }
            )

        if high:
            candidates = await find_public_pdfs(high)
            log.info("[run %s] %d PDF candidates found", rid, len(candidates))

            allowed = [c for c in candidates if c.is_oa]
            works_map = {w.reference_id: w for w in high}
            if allowed:
                downloads = await download_public_pdfs(
                    allowed, pdf_dir, works=works_map
                )
                log.info(
                    "[run %s] downloads: %d ok, %d failed, %d skipped",
                    rid,
                    sum(1 for d in downloads if d.status == "downloaded"),
                    sum(1 for d in downloads if d.status == "failed"),
                    sum(1 for d in downloads if d.status == "skipped"),
                )

    summary = RunSummary(
        references_found=len(references),
        references_resolved=len(resolved),
        pdfs_found=sum(1 for c in candidates if c.is_oa),
        pdfs_downloaded=sum(1 for d in downloads if d.status == "downloaded"),
        pdfs_failed=sum(1 for d in downloads if d.status == "failed"),
        pdfs_skipped=sum(1 for d in downloads if d.status == "skipped"),
    )

    manifest = RunManifest(
        run_id=rid,
        source_path=str(Path(pdf_path).expanduser().resolve()),
        started_at=started,
        finished_at=datetime.now(UTC),
        strategy=strategy,
        summary=summary,
        references=references,
        resolved=resolved,
        pdf_candidates=candidates,
        downloads=downloads,
        skipped=[
            {
                "reference_id": d.reference_id,
                "url": d.url,
                "error": d.error,
            }
            for d in downloads
            if d.status == "skipped"
        ],
        low_confidence=low_confidence,
    )

    manifest_path = write_manifest(manifest, out_dir)
    report_path = write_markdown_report(manifest, out_dir)
    json_report_path = write_json_report(manifest, out_dir)

    return {
        "run_id": rid,
        "pdf_path": str(Path(pdf_path).expanduser().resolve()),
        "output_dir": str(out_dir),
        "references_found": summary.references_found,
        "resolved": summary.references_resolved,
        "pdfs_found": summary.pdfs_found,
        "pdfs_downloaded": summary.pdfs_downloaded,
        "pdfs_failed": summary.pdfs_failed,
        "pdfs_skipped": summary.pdfs_skipped,
        "manifest_path": str(manifest_path),
        "report_path": str(report_path),
        "json_report_path": str(json_report_path),
    }


def _build_run_id(pdf_path: str | Path) -> str:
    stem = Path(pdf_path).stem[:32].replace(" ", "_") or "run"
    suffix = uuid.uuid4().hex[:6]
    return f"{stem}-{suffix}"

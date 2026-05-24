"""MCP server entrypoint exposing the bibliography pipeline as MCP tools.

Six tools per the build spec, each delegating to ``bibpdf_mcp.pipeline``:
  - extract_references_from_pdf
  - parse_bibtex_file
  - resolve_references
  - find_public_pdfs
  - download_public_pdfs
  - process_paper_bibliography
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from . import __version__, pipeline
from .logging_config import get_logger
from .models import PdfCandidate, Reference, ResolvedWork

log = get_logger(__name__)

mcp = FastMCP("bibliography-pdf")


@mcp.tool()
def extract_references_from_pdf(pdf_path: str) -> dict[str, Any]:
    """Extract bibliography entries from a paper PDF.

    Args:
        pdf_path: Absolute path to the input PDF.

    Returns:
        ``{"references": [Reference...], "count": int}``.
    """
    refs = pipeline.extract_references_from_pdf(pdf_path)
    return {
        "references": [r.model_dump(mode="json") for r in refs],
        "count": len(refs),
    }


@mcp.tool()
def parse_bibtex_file(bibtex_path: str) -> dict[str, Any]:
    """Parse a BibTeX file into the internal Reference model.

    Args:
        bibtex_path: Absolute path to a ``.bib`` file.
    """
    refs = pipeline.parse_bibtex_file(bibtex_path)
    return {
        "references": [r.model_dump(mode="json") for r in refs],
        "count": len(refs),
    }


@mcp.tool()
async def resolve_references(
    references: list[dict[str, Any]],
    strategy: str = "balanced",
) -> dict[str, Any]:
    """Resolve metadata for a list of references.

    Args:
        references: List of Reference-shaped dicts.
        strategy: One of ``"fast"``, ``"balanced"``, ``"deep"``.
    """
    refs = [Reference.model_validate(r) for r in references]
    resolved = await pipeline.resolve_references(refs, strategy=strategy)
    resolved_ids = {w.reference_id for w in resolved}
    unresolved = [r for r in refs if r.id not in resolved_ids]
    return {
        "resolved": [w.model_dump(mode="json") for w in resolved],
        "unresolved": [r.model_dump(mode="json") for r in unresolved],
    }


@mcp.tool()
async def find_public_pdfs(resolved_references: list[dict[str, Any]]) -> dict[str, Any]:
    """Locate publicly available OA PDFs for resolved references."""
    works = [ResolvedWork.model_validate(w) for w in resolved_references]
    cands = await pipeline.find_public_pdfs(works)
    return {
        "pdf_candidates": [c.model_dump(mode="json") for c in cands],
        "count": len(cands),
        "oa_count": sum(1 for c in cands if c.is_oa),
    }


@mcp.tool()
async def download_public_pdfs(
    pdf_candidates: list[dict[str, Any]],
    output_dir: str,
) -> dict[str, Any]:
    """Download approved PDF candidates to ``output_dir``."""
    cands = [PdfCandidate.model_validate(c) for c in pdf_candidates]
    results = await pipeline.download_public_pdfs(cands, output_dir)
    return {
        "downloaded": [r.model_dump(mode="json") for r in results if r.status == "downloaded"],
        "failed": [r.model_dump(mode="json") for r in results if r.status == "failed"],
        "skipped": [r.model_dump(mode="json") for r in results if r.status == "skipped"],
    }


@mcp.tool()
async def process_paper_bibliography(
    pdf_path: str,
    output_dir: str,
    strategy: str = "balanced",
) -> dict[str, Any]:
    """End-to-end pipeline: extract -> resolve -> find OA PDFs -> download -> manifest+report."""
    return await pipeline.process_paper_bibliography(
        pdf_path,
        output_dir,
        strategy=strategy,
    )


def main() -> None:
    log.info("Starting bibliography-pdf MCP server v%s (stdio)", __version__)
    mcp.run()


if __name__ == "__main__":
    main()

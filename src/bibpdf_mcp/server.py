"""MCP server entrypoint exposing the bibliography pipeline as MCP tools.

Implements 6 tools per the build spec:
  - extract_references_from_pdf
  - parse_bibtex_file
  - resolve_references
  - find_public_pdfs
  - download_public_pdfs
  - process_paper_bibliography

In Phase 1 each tool returns a structured "not implemented" response so MCP clients
(Claude Desktop, Cursor) can discover the tool surface immediately. Phase 5 wires
them to the real pipeline.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from . import __version__
from .logging_config import get_logger

log = get_logger(__name__)

mcp = FastMCP("bibliography-pdf")


def _stub(tool: str, **inputs: Any) -> dict[str, Any]:
    log.warning("MCP tool '%s' invoked but pipeline is not yet implemented", tool)
    return {
        "ok": False,
        "tool": tool,
        "version": __version__,
        "error": "not_implemented",
        "message": (
            f"Tool '{tool}' is registered but its pipeline is not yet implemented. "
            "This is the Phase 1 skeleton; full behavior lands in later phases."
        ),
        "inputs": inputs,
    }


@mcp.tool()
def extract_references_from_pdf(pdf_path: str) -> dict[str, Any]:
    """Extract bibliography entries from a paper PDF.

    Args:
        pdf_path: Absolute path to the input PDF.

    Returns:
        {"references": [...], "count": int} once implemented.
    """
    return _stub("extract_references_from_pdf", pdf_path=pdf_path)


@mcp.tool()
def parse_bibtex_file(bibtex_path: str) -> dict[str, Any]:
    """Parse a BibTeX file into the internal Reference model.

    Args:
        bibtex_path: Absolute path to a `.bib` file.
    """
    return _stub("parse_bibtex_file", bibtex_path=bibtex_path)


@mcp.tool()
def resolve_references(
    references: list[dict[str, Any]],
    strategy: str = "balanced",
) -> dict[str, Any]:
    """Resolve metadata for a list of references.

    Args:
        references: List of Reference-shaped dicts.
        strategy: One of "fast", "balanced", "deep".
    """
    return _stub("resolve_references", references=references, strategy=strategy)


@mcp.tool()
def find_public_pdfs(resolved_references: list[dict[str, Any]]) -> dict[str, Any]:
    """Locate publicly available OA PDFs for resolved references."""
    return _stub("find_public_pdfs", resolved_references=resolved_references)


@mcp.tool()
def download_public_pdfs(
    pdf_candidates: list[dict[str, Any]],
    output_dir: str,
) -> dict[str, Any]:
    """Download approved PDF candidates to `output_dir`."""
    return _stub(
        "download_public_pdfs",
        pdf_candidates=pdf_candidates,
        output_dir=output_dir,
    )


@mcp.tool()
def process_paper_bibliography(
    pdf_path: str,
    output_dir: str,
    strategy: str = "balanced",
) -> dict[str, Any]:
    """End-to-end pipeline: extract -> resolve -> find OA PDFs -> download -> manifest+report."""
    return _stub(
        "process_paper_bibliography",
        pdf_path=pdf_path,
        output_dir=output_dir,
        strategy=strategy,
    )


def main() -> None:
    log.info("Starting bibliography-pdf MCP server v%s (stdio)", __version__)
    mcp.run()


if __name__ == "__main__":
    main()

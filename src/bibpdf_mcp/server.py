"""MCP server entrypoint exposing the bibliography pipeline as MCP tools.

Six tools per the build spec, each delegating to ``bibpdf_mcp.tool_handlers``.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from . import __version__, tool_handlers
from .logging_config import get_logger

log = get_logger(__name__)

mcp = FastMCP("bibliography-pdf")


@mcp.tool()
def extract_references_from_pdf(pdf_path: str) -> dict[str, Any]:
    """Extract bibliography entries from a paper PDF."""
    return tool_handlers.extract_references_from_pdf(pdf_path)


@mcp.tool()
def parse_bibtex_file(bibtex_path: str) -> dict[str, Any]:
    """Parse a BibTeX file into the internal Reference model."""
    return tool_handlers.parse_bibtex_file(bibtex_path)


@mcp.tool()
async def resolve_references(
    references: list[dict[str, Any]],
    strategy: str = "balanced",
) -> dict[str, Any]:
    """Resolve metadata for a list of references."""
    return await tool_handlers.resolve_references(references, strategy=strategy)


@mcp.tool()
async def find_public_pdfs(resolved_references: list[dict[str, Any]]) -> dict[str, Any]:
    """Locate publicly available OA PDFs for resolved references."""
    return await tool_handlers.find_public_pdfs(resolved_references)


@mcp.tool()
async def download_public_pdfs(
    pdf_candidates: list[dict[str, Any]],
    output_dir: str | None = None,
) -> dict[str, Any]:
    """Download approved PDF candidates."""
    return await tool_handlers.download_public_pdfs(pdf_candidates, output_dir)


@mcp.tool()
async def process_paper_bibliography(
    pdf_path: str,
    output_dir: str | None = None,
    strategy: str = "balanced",
) -> dict[str, Any]:
    """End-to-end pipeline: extract -> resolve -> find OA PDFs -> download -> manifest+report."""
    return await tool_handlers.process_paper_bibliography(
        pdf_path, output_dir, strategy=strategy
    )


def main() -> None:
    log.info("Starting bibliography-pdf MCP server v%s (stdio)", __version__)
    mcp.run()


if __name__ == "__main__":
    main()

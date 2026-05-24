"""Aggregates OA PDF candidates from arXiv, Unpaywall, OpenAlex, Semantic Scholar.

Phase 1 stub.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..models import PdfCandidate, ResolvedWork


async def find_pdfs(resolved: Iterable[ResolvedWork]) -> list[PdfCandidate]:
    """Return PDF candidates for each resolved work."""
    raise NotImplementedError("Phase 4: implement PDF locator pipeline.")

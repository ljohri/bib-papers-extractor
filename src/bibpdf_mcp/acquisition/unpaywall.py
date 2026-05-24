"""Unpaywall lookup for OA PDF locations. Phase 1 stub."""

from __future__ import annotations

from ..models import PdfCandidate


async def lookup_unpaywall(doi: str, *, reference_id: str) -> list[PdfCandidate]:
    """Return PdfCandidate(s) from Unpaywall for the given DOI."""
    raise NotImplementedError("Phase 4: implement Unpaywall lookup.")

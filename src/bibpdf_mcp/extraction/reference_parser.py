"""Heuristic reference parser: split a bibliography blob into individual references
and parse each into structured fields.

Phase 1 stub.
"""

from __future__ import annotations

from ..models import Reference


def split_references(bibliography_text: str) -> list[str]:
    """Split a bibliography blob into raw per-reference strings."""
    raise NotImplementedError("Phase 2: implement reference splitting.")


def parse_reference(raw: str, ref_id: str) -> Reference:
    """Parse a single raw reference string into a structured `Reference`."""
    raise NotImplementedError("Phase 2: implement heuristic reference parsing.")

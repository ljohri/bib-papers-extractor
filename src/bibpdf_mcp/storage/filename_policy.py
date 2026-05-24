"""Deterministic filename builder: YEAR_FirstAuthor_ShortTitle_DOIHash.pdf.

Phase 1 stub.
"""

from __future__ import annotations

from ..models import ResolvedWork


def build_filename(work: ResolvedWork, *, max_title_words: int = 4) -> str:
    """Return a deterministic filename for the given resolved work."""
    raise NotImplementedError("Phase 5: implement deterministic filename policy.")

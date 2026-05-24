"""BibTeX parsing using bibtexparser as the primary backend.

Phase 1 stub.
"""

from __future__ import annotations

from pathlib import Path

from ..models import Reference


def parse_bibtex_file(path: str | Path) -> list[Reference]:
    """Parse a `.bib` file into a list of `Reference` records."""
    raise NotImplementedError("Phase 2: implement BibTeX parsing.")

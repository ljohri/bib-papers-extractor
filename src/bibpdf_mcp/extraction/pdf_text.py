"""PDF text extraction with layered fallback: pymupdf -> pdfplumber -> pypdf.

Phase 1 stub. Real implementation lands in Phase 2.
"""

from __future__ import annotations

from pathlib import Path


def extract_text(pdf_path: str | Path) -> str:
    """Extract full plain text from a PDF. Returns empty string on total failure."""
    raise NotImplementedError("Phase 2: implement layered PDF text extraction.")

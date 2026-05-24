"""PDF text extraction with layered fallback: pymupdf -> pdfplumber -> pypdf.

Each backend is tried in order; the first one that returns substantive text wins.
We log which backend produced the text for diagnostics.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ..logging_config import get_logger

log = get_logger(__name__)

_MIN_USABLE_LEN = 200  # below this we treat extraction as a probable failure


def _extract_with_pymupdf(path: Path) -> str:
    import pymupdf  # type: ignore[import-untyped]

    doc = pymupdf.open(path)
    try:
        return "\n".join(page.get_text("text") for page in doc)
    finally:
        doc.close()


def _extract_with_pdfplumber(path: Path) -> str:
    import pdfplumber

    parts: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            parts.append(text)
    return "\n".join(parts)


def _extract_with_pypdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


_BACKENDS: list[tuple[str, Callable[[Path], str]]] = [
    ("pymupdf", _extract_with_pymupdf),
    ("pdfplumber", _extract_with_pdfplumber),
    ("pypdf", _extract_with_pypdf),
]


def extract_text(pdf_path: str | Path) -> str:
    """Extract full plain text from a PDF.

    Tries pymupdf, then pdfplumber, then pypdf. Returns the first backend's output
    that yields at least `_MIN_USABLE_LEN` characters; otherwise returns the longest
    of all attempts (which may be empty).

    Raises FileNotFoundError if the file does not exist.
    """
    path = Path(pdf_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"Not a file: {path}")

    best = ""
    for name, fn in _BACKENDS:
        try:
            text = fn(path) or ""
        except Exception as e:
            log.warning("PDF backend %s failed on %s: %s", name, path.name, e)
            continue
        log.debug("PDF backend %s extracted %d chars from %s", name, len(text), path.name)
        if len(text) >= _MIN_USABLE_LEN:
            log.info("Used %s for %s (%d chars)", name, path.name, len(text))
            return text
        if len(text) > len(best):
            best = text

    if not best:
        log.warning("All PDF backends returned empty text for %s", path.name)
    return best

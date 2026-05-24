"""Heuristic reference parser.

Splits a bibliography blob into individual references, then extracts:
  - DOI                     (regex against doi.org / 10.\\d+/...)
  - arXiv ID                (arXiv:YYMM.NNNNN[vN], or older subj/YYMMNNN format)
  - Year                    (4-digit, 1900-2099)
  - Title                   (heuristic: longest plausible sentence-cased fragment)
  - Authors                 (everything before the year/title, comma-separated)

This is intentionally rule-based; ML parsers (GROBID/Anystyle) are listed as future
optional integrations in `docs/limitations.md`.
"""

from __future__ import annotations

import hashlib
import unicodedata

import regex as re

from ..logging_config import get_logger
from ..models import Reference

log = get_logger(__name__)

# --- Patterns ---------------------------------------------------------------

_DOI_RE = re.compile(
    r"""(?:doi\s*[:\s]*|https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/[^\s,;\)\]]+)""",
    re.IGNORECASE,
)
_ARXIV_NEW_RE = re.compile(r"""arXiv\s*[:\s]*\s*(\d{4}\.\d{4,5})(?:v\d+)?""", re.IGNORECASE)
_ARXIV_OLD_RE = re.compile(r"""arXiv\s*[:\s]*\s*([a-z\-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?""", re.IGNORECASE)
_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")

# Numbered prefix at start of a reference: "1.", "[1]", "(1)", "1) "
_NUMBERED_PREFIX_RE = re.compile(r"^\s*(?:\[(\d+)\]|\((\d+)\)|(\d+)[\.\)])\s+")

# Splits we use when the bibliography is plain blank-line separated entries.
_BLANK_SPLIT_RE = re.compile(r"\n\s*\n+")

# Soft splitter — when entries are jammed together but every entry starts with a
# bracketed or numbered prefix.
_INLINE_NUMBERED_SPLIT_RE = re.compile(
    r"""(?<=\n|^)
        (?=\s*(?:\[\d+\]|\(\d+\)|\d+[\.\)])\s+[A-Z])""",
    re.VERBOSE,
)

_DEHYPHEN_RE = re.compile(r"-\n(?=[a-z])")
_WHITESPACE_RE = re.compile(r"[ \t]+")


# --- Public API -------------------------------------------------------------


def split_references(bibliography_text: str) -> list[str]:
    """Split a bibliography blob into raw per-reference strings.

    Tries (in order):
      1. blank-line separated entries
      2. inline numbered/bracketed prefix split
      3. fallback: treat the whole blob as one reference

    Empty/whitespace-only entries are filtered.
    """
    if not bibliography_text or not bibliography_text.strip():
        return []

    text = _normalize_whitespace(bibliography_text)

    # Try blank-line splitting first.
    blank_split = [s.strip() for s in _BLANK_SPLIT_RE.split(text) if s.strip()]
    # If blank split yielded only one chunk OR most chunks look too short to be
    # references, fall back to numbered splitting.
    if len(blank_split) >= 3 and _looks_like_references(blank_split):
        return blank_split

    numbered_split = [s.strip() for s in _INLINE_NUMBERED_SPLIT_RE.split(text) if s.strip()]
    if len(numbered_split) >= 2:
        return numbered_split

    if blank_split:
        return blank_split

    return [text.strip()]


def parse_reference(raw: str, ref_id: str) -> Reference:
    """Parse a single raw reference string into a structured `Reference`.

    Heuristic: split the reference on sentence boundaries (". "). Most journal/
    conference citations follow:

        Authors. Title. Venue Year. [DOI/arXiv].

    so chunk[0] is the author block, chunk[1] is the title, the remainder carries
    venue/year/identifiers.
    """
    cleaned = _normalize_whitespace(_strip_numbered_prefix(raw))

    doi = _extract_doi(cleaned)
    arxiv = _extract_arxiv(cleaned)
    year = _extract_year(cleaned)

    chunks = _split_sentences(cleaned)
    authors = _extract_authors_from_chunk(chunks[0]) if chunks else []
    title = _extract_title_from_chunks(chunks)

    return Reference(
        id=ref_id,
        raw=raw.strip(),
        title=title,
        authors=authors,
        year=year,
        doi=doi,
        arxiv_id=arxiv,
    )


def make_ref_id(raw: str, index: int) -> str:
    """Stable id: 'ref-NNN' where the digest disambiguates duplicate raw strings."""
    digest = hashlib.sha1(raw.strip().encode("utf-8", "ignore")).hexdigest()[:6]
    return f"ref-{index:03d}-{digest}"


def parse_references_from_text(bibliography_text: str) -> list[Reference]:
    """Convenience: split + parse, returning a list of Reference."""
    raw_entries = split_references(bibliography_text)
    out: list[Reference] = []
    for i, raw in enumerate(raw_entries, start=1):
        out.append(parse_reference(raw, make_ref_id(raw, i)))
    return out


# --- Helpers ---------------------------------------------------------------


def _normalize_whitespace(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = _DEHYPHEN_RE.sub("", text)  # join hyphenated line-breaks
    text = text.replace("\r", "")
    # Collapse multiple spaces/tabs but preserve newlines (newlines are meaningful for splitting).
    text = "\n".join(_WHITESPACE_RE.sub(" ", line.strip()) for line in text.split("\n"))
    return text.strip()


def _looks_like_references(chunks: list[str]) -> bool:
    """Reject blank-split chunks if most are tiny (< 40 chars)."""
    if not chunks:
        return False
    long_enough = sum(1 for c in chunks if len(c) >= 40)
    return long_enough >= max(2, int(0.5 * len(chunks)))


def _strip_numbered_prefix(raw: str) -> str:
    return _NUMBERED_PREFIX_RE.sub("", raw, count=1)


def _extract_doi(text: str) -> str | None:
    m = _DOI_RE.search(text)
    if not m:
        return None
    doi = m.group(1).rstrip(".,;)").lower()
    return doi


def _extract_arxiv(text: str) -> str | None:
    m = _ARXIV_NEW_RE.search(text)
    if m:
        return m.group(1)
    m = _ARXIV_OLD_RE.search(text)
    if m:
        return m.group(1)
    return None


def _extract_year(text: str) -> int | None:
    """Pick the most plausible publication year.

    We exclude years that appear inside arXiv ids (e.g. '2005.14165') by first
    masking matched arXiv ids. Among remaining candidates we return the *latest*
    plausible year, since reference lists frequently embed older citations in
    title/author text but the publication year is normally the most recent.
    """
    masked = _ARXIV_NEW_RE.sub(" ARXIVID ", text)
    masked = _ARXIV_OLD_RE.sub(" ARXIVID ", masked)
    candidates = _YEAR_RE.findall(masked)
    years = [int(y) for y in candidates if 1900 <= int(y) <= 2099]
    if not years:
        return None
    return max(years)


def _split_sentences(text: str) -> list[str]:
    """Split a reference into rough sentence-like chunks.

    Splits on ``. `` followed by an uppercase word, OR on a parenthesized
    year ``(YYYY).`` (a common author/title separator).
    """
    text = re.sub(r"\(\s*(19\d{2}|20\d{2})\s*\)\s*\.?\s*", r". \1. ", text)

    parts = re.split(
        r"(?<=[a-z\d\)\]])\.\s+(?=[\"\u201c\d]|[A-Z][\w'\-]{1,})",
        text,
    )
    return [p.strip(" .,;:\"'\u201c\u201d") for p in parts if p.strip(" .,;:")]


def _extract_authors_from_chunk(chunk: str) -> list[str]:
    """Treat `chunk` (the first sentence) as the author block.

    Authors are separated by ',' or ';'. 'and' before the last author is stripped.
    Tokens like 'et al' are filtered, and trailing 'et al' suffixes inside an author
    string are removed (e.g. 'Brown T. et al' -> 'Brown T').
    """
    if not chunk:
        return []
    head = chunk.strip().rstrip(",.;:")
    parts = re.split(r"\s*(?:,|;|\band\b)\s*", head)

    cleaned: list[str] = []
    for raw in parts:
        a = raw.strip(" .,")
        a = re.sub(r"\s*\bet\.?\s+al\.?\s*$", "", a, flags=re.IGNORECASE).strip(" .,")
        # Strip trailing dangling-year fragments like 'Toutanova K. . 2019'.
        a = re.sub(r"\s*\.?\s*(?:19\d{2}|20\d{2})\s*$", "", a).strip(" .,")
        if len(a) < 2:
            continue
        if a.lower() in {"et", "al", "et al", "et. al", "et al."}:
            continue
        if a.count(" ") > 4 and any(w.islower() and len(w) >= 4 for w in a.split()):
            continue
        cleaned.append(a)
    return cleaned[:32]


def _extract_title_from_chunks(chunks: list[str]) -> str | None:
    """Choose the chunk most likely to be the title.

    Preference: the first chunk after the author chunk that
      - is at least 8 characters long
      - contains at least one space (i.e. multiple words)
      - is not just a year/DOI/arXiv id
      - does not start with 'In Proc' (that's a venue)
    """
    if len(chunks) < 2:
        return None

    junk_re = re.compile(
        r"^(?:doi[:\s]|arxiv[:\s]|https?://|\d{4}\b|in\s+proc|proceedings\s+of)",
        re.IGNORECASE,
    )
    trailing_arxiv_re = re.compile(
        r"\.?\s*arXiv(?:\s+preprint)?\s+arXiv?:?\s*\S+.*$", re.IGNORECASE
    )
    trailing_year_re = re.compile(r"[,\.\s]+(?:19\d{2}|20\d{2})\b.*$")

    for chunk in chunks[1:]:
        c = chunk.strip(" .,;:\"'\u201c\u201d")
        if len(c) < 8 or " " not in c:
            continue
        if junk_re.match(c):
            continue
        c = trailing_arxiv_re.sub("", c).strip(" .,;:\"'\u201c\u201d")
        c = trailing_year_re.sub("", c).strip(" .,;:\"'\u201c\u201d")
        if 8 <= len(c) <= 400:
            return c
    return None

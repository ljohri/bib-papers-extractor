"""Deterministic filename policy: ``YEAR_FirstAuthor_ShortTitle_DOIHash.pdf``.

Examples:
  2017_Vaswani_AttentionIsAllYouNeed_a1b2c3.pdf
  2019_Devlin_BertPreTraining_d4e5f6.pdf
  0000_Unknown_UnknownTitle_000000.pdf      (worst case)

Rules:
  - YEAR: 4-digit publication year, or ``0000`` if unknown.
  - FirstAuthor: first author's family name, ASCII-folded, alphanum only,
    truncated to 24 chars.
  - ShortTitle: first ``max_title_words`` title tokens, CamelCased, ASCII-only.
  - DOIHash: 6 hex chars of sha256(doi || arxiv_id || url || ref_id).
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

from titlecase import titlecase

from ..models import ResolvedWork

_NON_ALNUM = re.compile(r"[^A-Za-z0-9]+")
_NON_LETTERS = re.compile(r"[^A-Za-z]+")


def _ascii_fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def _first_author(work: ResolvedWork) -> str:
    if not work.authors:
        return "Unknown"
    raw = work.authors[0].strip()
    if "," in raw:
        last = raw.split(",", 1)[0]
    else:
        parts = raw.split()
        last = parts[-1] if parts else raw
    last = _NON_LETTERS.sub("", _ascii_fold(last))
    last = last[:24] or "Unknown"
    return last.capitalize()


def _short_title(work: ResolvedWork, *, max_words: int) -> str:
    title = work.title or "UnknownTitle"
    title = _ascii_fold(titlecase(title))
    tokens = re.findall(r"[A-Za-z0-9]+", title)
    if not tokens:
        return "UnknownTitle"
    head = tokens[: max(1, max_words)]
    cleaned = "".join(t.capitalize() for t in head)
    return cleaned[:48] or "UnknownTitle"


def _identity_hash(work: ResolvedWork) -> str:
    parts = [
        (work.doi or "").lower(),
        (work.arxiv_id or "").lower(),
        (work.url or "").lower(),
        work.reference_id,
    ]
    digest = hashlib.sha256("|".join(parts).encode("utf-8", "ignore")).hexdigest()
    return digest[:6]


def build_filename(work: ResolvedWork, *, max_title_words: int = 5) -> str:
    """Return a deterministic filename for the given resolved work.

    All four components are pre-sanitized to alphanumerics, so we only need to
    join them with underscores and append ``.pdf``.
    """
    year = f"{work.year:04d}" if work.year and 0 < work.year < 10000 else "0000"
    author = _first_author(work)
    short = _short_title(work, max_words=max_title_words)
    h = _identity_hash(work)
    return f"{year}_{author}_{short}_{h}.pdf"

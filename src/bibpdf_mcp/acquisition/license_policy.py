"""Allow/deny policy for PDF candidate URLs.

Rule of thumb: a candidate is allowed iff:
  1. its URL scheme is https, AND
  2. its `source` is in `ALLOWED_SOURCES`, AND
  3. its host does NOT match any fragment in `DENIED_HOST_FRAGMENTS`, AND
  4. its URL path/query does NOT match any fragment in `DENIED_PATH_FRAGMENTS`.

This module is the single source of truth for legal/OA gating. The downloader
will call `evaluate(candidate)` before attempting any HTTP fetch.
"""

from __future__ import annotations

from urllib.parse import urlparse

from ..models import PdfCandidate

ALLOWED_SOURCES: frozenset[str] = frozenset(
    {
        "arxiv",
        "unpaywall",
        "openalex",
        "semantic_scholar",
        "publisher_oa",
        "repository",
    }
)

# Substring matches against the lowercased URL host.
DENIED_HOST_FRAGMENTS: tuple[str, ...] = (
    "sci-hub",
    "scihub",
    "libgen",
    "library.lol",
    "z-lib",
    "z-library",
    "annas-archive",
    "anna-archive",
    "1lib",
    "b-ok",
    "bookos",
)

# Substring matches against the lowercased URL path/query.
DENIED_PATH_FRAGMENTS: tuple[str, ...] = (
    "/proxy/",
    "/ezproxy/",
    "/login?",
    "/signin?",
    "shibboleth",
    "captcha",
)


def evaluate(candidate: PdfCandidate) -> tuple[bool, str | None]:
    """Return ``(is_allowed, reason_if_denied)`` for a candidate URL.

    On allow, ``reason_if_denied`` is None. On deny, reason is a short string
    suitable for inclusion in the manifest's ``skipped[]`` entries.
    """
    url = (candidate.url or "").strip()
    if not url:
        return False, "empty url"

    parsed = urlparse(url)
    if parsed.scheme.lower() not in {"https"}:
        return False, f"non-https scheme: {parsed.scheme or '(none)'}"

    if not parsed.netloc:
        return False, "missing host"

    host = parsed.netloc.lower()
    for frag in DENIED_HOST_FRAGMENTS:
        if frag in host:
            return False, f"denied host fragment '{frag}'"

    path_q = (parsed.path + "?" + parsed.query).lower()
    for frag in DENIED_PATH_FRAGMENTS:
        if frag in path_q:
            return False, f"denied path fragment '{frag}'"

    if candidate.source not in ALLOWED_SOURCES:
        return False, f"source not on allowlist: {candidate.source}"

    if not candidate.is_oa and candidate.source not in {"arxiv"}:
        # arXiv preprints don't carry an `is_oa` flag from upstream APIs but are
        # always public. Anything else must be flagged OA.
        return False, "is_oa flag is false"

    return True, None

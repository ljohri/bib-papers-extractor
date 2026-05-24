"""Allow/deny policy for PDF candidate URLs.

Only sources we trust to be public/OA are allowed. Sci-Hub, LibGen, paywall-bypass
mirrors, login-required pages, and non-https URLs are explicitly rejected.

Phase 1 stub: stable allow/deny list shape, real evaluator lands in Phase 4.
"""

from __future__ import annotations

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

DENIED_HOST_FRAGMENTS: tuple[str, ...] = (
    "sci-hub",
    "scihub",
    "libgen",
    "library.lol",
    "z-lib",
    "annas-archive",
)


def evaluate(candidate: PdfCandidate) -> tuple[bool, str | None]:
    """Return (is_allowed, reason_if_denied)."""
    raise NotImplementedError("Phase 4: implement license policy evaluation.")

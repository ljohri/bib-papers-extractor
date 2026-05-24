"""Resolver pipeline.

Runs the four resolvers in precedence order and assigns a final confidence
score per the spec:

    DOI exact match                              1.00
    arXiv exact match                            0.98
    title exact + year match                     0.93
    high fuzzy title + author overlap            0.85
    title only match                            <= 0.75

Strategies:
    fast      — stop after the first hit with confidence >= 0.93
    balanced  — query DOI/arXiv resolvers; if no high hit, also query
                OpenAlex + Crossref title search and re-rank
    deep      — always query all four; aggregate and re-rank
"""

from __future__ import annotations

import asyncio
import re
import unicodedata
from collections.abc import Iterable

from rapidfuzz import fuzz

from ..config import get_settings
from ..logging_config import get_logger
from ..models import Reference, ResolvedWork
from .arxiv import ArxivResolver
from .base import BaseResolver
from .crossref import CrossrefResolver
from .openalex import OpenAlexResolver
from .semantic_scholar import SemanticScholarResolver

log = get_logger(__name__)


_PUNCT_RE = re.compile(r"[\u2018\u2019\u201c\u201d\"'`.,;:!?\(\)\[\]{}\-_/\\]+")
_WS_RE = re.compile(r"\s+")


def _normalize_title(s: str | None) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = _PUNCT_RE.sub(" ", s.lower())
    return _WS_RE.sub(" ", s).strip()


def _surname_tokens(author: str) -> set[str]:
    """Return the set of plausible surname tokens from an author string.

    Citation conventions vary ('Vaswani, Ashish', 'Vaswani A', 'A. Vaswani',
    'Ashish Vaswani'), so we collect ALL alphabetical tokens of length >= 3
    (excluding common honorifics) — at least one will be the surname. Jaccard
    between two such sets is robust across conventions.
    """
    a = unicodedata.normalize("NFKD", author).encode("ascii", "ignore").decode("ascii")
    a = _PUNCT_RE.sub(" ", a).lower()
    tokens = [t for t in a.split() if len(t) >= 3 and t.isalpha()]
    blacklist = {"and", "the", "for", "von", "van", "der", "del", "los"}
    return {t for t in tokens if t not in blacklist}


def _author_overlap(a: list[str], b: list[str]) -> float:
    if not a or not b:
        return 0.0
    sa: set[str] = set()
    for x in a:
        sa.update(_surname_tokens(x))
    sb: set[str] = set()
    for x in b:
        sb.update(_surname_tokens(x))
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / max(1, len(sa | sb))


def _doi_eq(a: str | None, b: str | None) -> bool:
    return bool(a and b and a.strip().lower() == b.strip().lower())


def _arxiv_eq(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    a2 = a.split("v")[0].strip().lower()
    b2 = b.split("v")[0].strip().lower()
    return a2 == b2


def score(reference: Reference, candidate: ResolvedWork) -> float:
    """Compute the spec-defined confidence for a (reference, candidate) pair."""
    if _doi_eq(reference.doi, candidate.doi):
        return 1.00
    if _arxiv_eq(reference.arxiv_id, candidate.arxiv_id):
        return 0.98

    rt = _normalize_title(reference.title)
    ct = _normalize_title(candidate.title)
    if not rt or not ct:
        return 0.0

    title_eq = rt == ct
    fuzzy = fuzz.token_set_ratio(rt, ct) / 100.0  # 0..1
    overlap = _author_overlap(reference.authors, candidate.authors)
    year_match = (
        reference.year is not None
        and candidate.year is not None
        and abs(reference.year - candidate.year) == 0
    )
    year_close = (
        reference.year is not None
        and candidate.year is not None
        and abs(reference.year - candidate.year) <= 1
    )

    if title_eq and year_match:
        return 0.93
    if fuzzy >= 0.92 and overlap >= 0.5:
        return 0.85
    if fuzzy >= 0.85 and (year_match or year_close):
        return 0.78
    if fuzzy >= 0.80:
        return 0.72
    return min(0.6, fuzzy * 0.7)


def _rank(reference: Reference, candidates: Iterable[ResolvedWork]) -> list[ResolvedWork]:
    scored: list[ResolvedWork] = []
    for c in candidates:
        c_scored = c.model_copy(update={"confidence": score(reference, c)})
        scored.append(c_scored)
    scored.sort(key=lambda c: c.confidence, reverse=True)
    return scored


# --- Strategy executors ----------------------------------------------------


async def _resolve_one(
    reference: Reference,
    *,
    resolvers: dict[str, BaseResolver],
    strategy: str,
) -> list[ResolvedWork]:
    """Resolve a single reference using the configured strategy."""
    if strategy not in {"fast", "balanced", "deep"}:
        strategy = "balanced"

    aggregated: list[ResolvedWork] = []

    # Phase A: identifier-based lookups (DOI / arXiv) first.
    id_tasks = []
    if reference.doi:
        id_tasks.append(resolvers["crossref"].resolve(reference))
        id_tasks.append(resolvers["openalex"].resolve(reference))
        id_tasks.append(resolvers["semantic_scholar"].resolve(reference))
    if reference.arxiv_id:
        id_tasks.append(resolvers["arxiv"].resolve(reference))

    if id_tasks:
        for batch in await asyncio.gather(*id_tasks, return_exceptions=True):
            if isinstance(batch, Exception):
                log.warning("identifier resolver failed: %s", batch)
                continue
            aggregated.extend(batch)

        ranked = _rank(reference, aggregated)
        if ranked and ranked[0].confidence >= 0.93 and strategy in {"fast", "balanced"}:
            return ranked

    # Phase B: title search across remaining resolvers.
    title_tasks = []
    if strategy != "fast" and reference.title:
        title_tasks.append(resolvers["openalex"].resolve(reference))
        title_tasks.append(resolvers["crossref"].resolve(reference))
        if strategy == "deep":
            title_tasks.append(resolvers["semantic_scholar"].resolve(reference))
            title_tasks.append(resolvers["arxiv"].resolve(reference))

    if title_tasks:
        for batch in await asyncio.gather(*title_tasks, return_exceptions=True):
            if isinstance(batch, Exception):
                log.warning("title resolver failed: %s", batch)
                continue
            aggregated.extend(batch)

    return _rank(reference, aggregated)


# --- Public API ------------------------------------------------------------


def build_resolvers(*, cache: object | None = None) -> dict[str, BaseResolver]:
    """Construct fresh resolver instances sharing the same cache."""
    return {
        "crossref": CrossrefResolver(cache=cache),
        "openalex": OpenAlexResolver(cache=cache),
        "semantic_scholar": SemanticScholarResolver(cache=cache),
        "arxiv": ArxivResolver(cache=cache),
    }


async def resolve_all(
    references: Iterable[Reference],
    *,
    strategy: str = "balanced",
    cache: object | None = None,
    resolvers: dict[str, BaseResolver] | None = None,
) -> list[ResolvedWork]:
    """Run the resolver pipeline over a batch of references.

    Returns the best candidate per reference (highest confidence). References
    with no candidates produce no output rows.
    """
    settings = get_settings()
    own_resolvers = resolvers is None
    resolvers = resolvers or build_resolvers(cache=cache)

    sem = asyncio.Semaphore(max(1, settings.max_concurrent_requests))

    async def _bounded(ref: Reference) -> list[ResolvedWork]:
        async with sem:
            return await _resolve_one(ref, resolvers=resolvers, strategy=strategy)

    try:
        results = await asyncio.gather(*[_bounded(r) for r in references])
    finally:
        if own_resolvers:
            await asyncio.gather(*[r.aclose() for r in resolvers.values()], return_exceptions=True)

    flat: list[ResolvedWork] = []
    for ranked in results:
        if ranked:
            flat.append(ranked[0])
    return flat

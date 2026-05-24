"""Aggregates OA PDF candidates from arXiv, Unpaywall, OpenAlex, Semantic Scholar.

Strategy per resolved work:
  1. If `arxiv_id` is set, emit the canonical arXiv PDF URL.
  2. If `doi` is set, query Unpaywall.
  3. If the work's source was OpenAlex, mine its raw_metadata for OA locations.
  4. If the work's source was Semantic Scholar, mine `openAccessPdf.url`.

All candidates are then run through `license_policy.evaluate()`. Rejected
candidates are returned alongside accepted ones (with `is_oa=False`) so the
pipeline can record the reason in the run manifest.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Any

import httpx

from ..config import get_settings
from ..logging_config import get_logger
from ..models import PdfCandidate, ResolvedWork
from . import license_policy
from .unpaywall import lookup_unpaywall

log = get_logger(__name__)


def _arxiv_pdf_url(arxiv_id: str) -> str:
    base = arxiv_id.split("v")[0]
    return f"https://arxiv.org/pdf/{base}.pdf"


def _from_arxiv(work: ResolvedWork) -> list[PdfCandidate]:
    if not work.arxiv_id:
        return []
    return [
        PdfCandidate(
            reference_id=work.reference_id,
            url=_arxiv_pdf_url(work.arxiv_id),
            source="arxiv",
            is_oa=True,
            confidence=0.97,
            evidence={"arxiv_id": work.arxiv_id},
        )
    ]


def _from_openalex(work: ResolvedWork) -> list[PdfCandidate]:
    if work.source != "openalex":
        return []
    item: dict[str, Any] = work.raw_metadata.get("item", {}) or {}

    out: list[PdfCandidate] = []
    seen: set[str] = set()

    def _add(loc: dict[str, Any], best: bool) -> None:
        if not isinstance(loc, dict):
            return
        url = loc.get("pdf_url") or loc.get("landing_page_url")
        if not url or url in seen:
            return
        seen.add(url)
        out.append(
            PdfCandidate(
                reference_id=work.reference_id,
                url=url,
                source="openalex",
                license=loc.get("license"),
                is_oa=bool(loc.get("is_oa")),
                confidence=0.9 if best else 0.7,
                evidence={
                    "version": loc.get("version"),
                    "host_type": (loc.get("source") or {}).get("type"),
                    "is_best": best,
                },
            )
        )

    primary = item.get("primary_location") or {}
    _add(primary, best=True)

    for loc in item.get("locations", []) or []:
        _add(loc, best=False)

    return out


def _from_semantic_scholar(work: ResolvedWork) -> list[PdfCandidate]:
    if work.source != "semantic_scholar":
        return []
    item: dict[str, Any] = work.raw_metadata.get("item", {}) or {}
    oa = item.get("openAccessPdf") or {}
    url = oa.get("url")
    if not url:
        return []
    return [
        PdfCandidate(
            reference_id=work.reference_id,
            url=url,
            source="semantic_scholar",
            license=oa.get("license"),
            is_oa=True,
            confidence=0.85,
            evidence={"paperId": item.get("paperId")},
        )
    ]


# --- Public API ------------------------------------------------------------


async def find_pdfs(
    resolved: Iterable[ResolvedWork],
    *,
    cache: object | None = None,
    client: httpx.AsyncClient | None = None,
) -> list[PdfCandidate]:
    """Return aggregated PdfCandidate list for all resolved works.

    Note: candidates that fail `license_policy.evaluate()` are still returned
    (with `is_oa=False` if not already), but their `evidence['policy_reason']`
    is populated and the downloader will skip them.
    """
    settings = get_settings()
    works = list(resolved)

    own_client = client is None
    client = client or httpx.AsyncClient(
        timeout=httpx.Timeout(20.0, connect=10.0),
        headers={"User-Agent": settings.user_agent},
        follow_redirects=True,
    )

    sem = asyncio.Semaphore(max(1, settings.max_concurrent_requests))

    async def _per_work(work: ResolvedWork) -> list[PdfCandidate]:
        async with sem:
            cands: list[PdfCandidate] = []
            cands.extend(_from_arxiv(work))
            cands.extend(_from_openalex(work))
            cands.extend(_from_semantic_scholar(work))

            if work.doi:
                up_cands = await lookup_unpaywall(
                    work.doi,
                    reference_id=work.reference_id,
                    client=client,
                    cache=cache,
                )
                cands.extend(up_cands)
            return cands

    try:
        per_work = await asyncio.gather(*[_per_work(w) for w in works])
    finally:
        if own_client:
            await client.aclose()

    flat: list[PdfCandidate] = []
    for batch in per_work:
        for c in batch:
            allowed, reason = license_policy.evaluate(c)
            if allowed:
                flat.append(c)
            else:
                c2 = c.model_copy(
                    update={
                        "is_oa": False,
                        "confidence": 0.0,
                        "evidence": {**c.evidence, "policy_reason": reason},
                    }
                )
                flat.append(c2)
                log.debug("policy reject %s -> %s", c.url, reason)

    return _dedupe(flat)


def _dedupe(candidates: list[PdfCandidate]) -> list[PdfCandidate]:
    """Drop duplicate (reference_id, url) pairs, keeping the highest-confidence one."""
    best: dict[tuple[str, str], PdfCandidate] = {}
    for c in candidates:
        key = (c.reference_id, c.url)
        cur = best.get(key)
        if cur is None or c.confidence > cur.confidence:
            best[key] = c
    return list(best.values())

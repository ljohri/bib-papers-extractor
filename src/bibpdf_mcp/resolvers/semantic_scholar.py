"""Semantic Scholar Academic Graph resolver.

Endpoints exposed (all under ``/graph/v1/paper``):

  GET  /search                  ``search_papers``
  GET  /search/bulk             ``search_bulk``
  GET  /{paper_id}              ``lookup_paper``
  POST /batch                   ``batch_lookup``
  GET  /{paper_id}/references   ``get_references``
  GET  /{paper_id}/citations    ``get_citations``

Where ``{paper_id}`` accepts the canonical S2 paperId, ``DOI:<doi>``,
``ARXIV:<arxiv_id>`` (or ``arXiv:<arxiv_id>``), and a few other ID prefixes
documented by Semantic Scholar.

Compliance with the Semantic Scholar policy (unauthenticated):

  - Maximum 1 request per second. Enforced by ``aiolimiter`` set to
    ``max_rate=1.0, time_period=1.0`` when no API key is configured.
  - Daily budget of 500–2,000 requests during dev/test. Bounded by the rate
    limit (1 r/s ≈ 86,400/day max) but in practice each call is cached, so
    repeat lookups don't hit the network.
  - Results cached in the SQLite cache (``api_cache``) keyed by source/operation/id
    with TTL = 30 days.
  - De-duplication by DOI / S2 paperId / arXiv id via ``dedupe_papers``.
  - Exponential backoff with ``Retry-After`` honoring on 429/5xx (in
    ``BaseResolver._retry_loop``).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import httpx

from ..models import Reference, ResolvedWork
from .base import BaseResolver

S2_API = "https://api.semanticscholar.org/graph/v1/paper"

# Default fields requested for paper records. Kept conservative to stay under
# the API's 1MB response cap.
_DEFAULT_FIELDS = "paperId,externalIds,title,authors,year,openAccessPdf,url"
_REFERENCES_FIELDS = "paperId,title,authors,year,externalIds,openAccessPdf,url"
_CITATIONS_FIELDS = _REFERENCES_FIELDS


class SemanticScholarResolver(BaseResolver):
    source = "semantic_scholar"
    base_url = S2_API
    rate_limit_per_sec = 1.0  # unauthenticated public limit
    cache_ttl_days = 30

    def _build_client(self) -> httpx.AsyncClient:
        client = super()._build_client()
        if self.settings.semantic_scholar_api_key:
            client.headers["x-api-key"] = self.settings.semantic_scholar_api_key
            self.rate_limit_per_sec = 9.0
        return client

    # --- High-level resolve interface (used by the resolver pipeline) -------

    async def resolve(self, reference: Reference) -> list[ResolvedWork]:
        if reference.doi:
            item = await self.lookup_paper(f"DOI:{reference.doi}")
            if item:
                return [self._to_resolved(reference, item, source_hint="s2-doi")]
        if reference.arxiv_id:
            item = await self.lookup_paper(f"arXiv:{reference.arxiv_id}")
            if item:
                return [self._to_resolved(reference, item, source_hint="s2-arxiv")]
        if reference.title:
            return await self._search_resolve(reference)
        return []

    async def _search_resolve(self, reference: Reference) -> list[ResolvedWork]:
        payload = await self.search_papers(
            reference.title or "",
            year=reference.year,
            limit=5,
        )
        items = (payload or {}).get("data", []) or []
        return [self._to_resolved(reference, it, source_hint="s2-search") for it in items]

    # --- Endpoint 1: GET /paper/{paper_id} ---------------------------------

    async def lookup_paper(
        self,
        paper_id: str,
        *,
        fields: str = _DEFAULT_FIELDS,
    ) -> dict[str, Any] | None:
        """Look up a single paper by S2 paperId, ``DOI:...``, or ``arXiv:...``.

        Returns the parsed JSON, or None on 404 / total failure.
        """
        params = {"fields": fields}
        cache_key = f"paper:{paper_id.lower()}|f={fields}"
        result = await self._get_json(
            f"{S2_API}/{paper_id}",
            params=params,
            cache_key=cache_key,
        )
        if isinstance(result, dict):
            return result
        return None

    # --- Endpoint 2: GET /paper/search -------------------------------------

    async def search_papers(
        self,
        query: str,
        *,
        year: int | str | None = None,
        limit: int = 5,
        offset: int = 0,
        fields: str = _DEFAULT_FIELDS,
    ) -> dict[str, Any] | None:
        """Title/keyword search via the relevance-ranked endpoint.

        Returns a dict ``{"total": int, "offset": int, "next": int, "data": [...]}``.
        """
        params: dict[str, Any] = {
            "query": query,
            "limit": int(limit),
            "offset": int(offset),
            "fields": fields,
        }
        if year is not None:
            params["year"] = str(year)
        cache_key = (
            f"search:q={query.lower()}|y={year or ''}|"
            f"l={limit}|o={offset}|f={fields}"
        )
        result = await self._get_json(
            f"{S2_API}/search",
            params=params,
            cache_key=cache_key,
        )
        if isinstance(result, dict):
            return result
        return None

    # --- Endpoint 3: GET /paper/search/bulk --------------------------------

    async def search_bulk(
        self,
        query: str,
        *,
        year: int | str | None = None,
        venue: str | None = None,
        token: str | None = None,
        fields: str = _DEFAULT_FIELDS,
    ) -> dict[str, Any] | None:
        """Bulk paginated search.

        Returns up to 1000 results per call plus a ``token`` for the next page.
        Pass the previous ``token`` to fetch the subsequent batch.
        """
        params: dict[str, Any] = {
            "query": query,
            "fields": fields,
        }
        if year is not None:
            params["year"] = str(year)
        if venue:
            params["venue"] = venue
        if token:
            params["token"] = token

        cache_key = (
            f"search/bulk:q={query.lower()}|y={year or ''}"
            f"|v={(venue or '').lower()}|t={token or ''}|f={fields}"
        )
        result = await self._get_json(
            f"{S2_API}/search/bulk",
            params=params,
            cache_key=cache_key,
        )
        if isinstance(result, dict):
            return result
        return None

    # --- Endpoint 4: POST /paper/batch -------------------------------------

    async def batch_lookup(
        self,
        paper_ids: Iterable[str],
        *,
        fields: str = _DEFAULT_FIELDS,
    ) -> list[dict[str, Any] | None]:
        """Batch-fetch up to 500 paper records in a single request.

        The Semantic Scholar batch endpoint deduplicates upstream by paperId,
        but we additionally normalize and de-dup the input list ourselves
        (preserving order) so we never waste budget on equivalent identifiers.

        Returns a list aligned with the unique input ids; entries are dicts
        for hits and None for unresolvable ids (mirroring S2's behavior).
        """
        unique_ids = _dedupe_ids(paper_ids)
        if not unique_ids:
            return []

        cache_key = f"batch:ids={'|'.join(unique_ids)}|f={fields}"
        result = await self._post_json(
            f"{S2_API}/batch",
            json_body={"ids": unique_ids},
            params={"fields": fields},
            cache_key=cache_key,
        )
        if not isinstance(result, list):
            return []
        return [it if isinstance(it, dict) else None for it in result]

    # --- Endpoint 5: GET /paper/{paper_id}/references ----------------------

    async def get_references(
        self,
        paper_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
        fields: str = _REFERENCES_FIELDS,
    ) -> dict[str, Any] | None:
        """Outgoing references of a paper. Paginated via ``offset``/``limit``."""
        params = {"limit": int(limit), "offset": int(offset), "fields": fields}
        cache_key = f"refs:{paper_id.lower()}|l={limit}|o={offset}|f={fields}"
        result = await self._get_json(
            f"{S2_API}/{paper_id}/references",
            params=params,
            cache_key=cache_key,
        )
        if isinstance(result, dict):
            return result
        return None

    # --- Endpoint 6: GET /paper/{paper_id}/citations -----------------------

    async def get_citations(
        self,
        paper_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
        fields: str = _CITATIONS_FIELDS,
    ) -> dict[str, Any] | None:
        """Incoming citations of a paper. Paginated via ``offset``/``limit``."""
        params = {"limit": int(limit), "offset": int(offset), "fields": fields}
        cache_key = f"cites:{paper_id.lower()}|l={limit}|o={offset}|f={fields}"
        result = await self._get_json(
            f"{S2_API}/{paper_id}/citations",
            params=params,
            cache_key=cache_key,
        )
        if isinstance(result, dict):
            return result
        return None

    # --- ResolvedWork conversion ------------------------------------------

    def _to_resolved(
        self,
        reference: Reference,
        item: dict[str, Any],
        *,
        source_hint: str,
    ) -> ResolvedWork:
        ext = item.get("externalIds", {}) or {}
        doi = ext.get("DOI")
        arxiv = ext.get("ArXiv")
        authors = [
            (a.get("name") or "").strip()
            for a in (item.get("authors") or [])
            if a.get("name")
        ]
        return ResolvedWork(
            reference_id=reference.id,
            title=item.get("title") or (reference.title or ""),
            authors=authors,
            year=item.get("year"),
            doi=(doi or "").lower() or None,
            arxiv_id=arxiv,
            semantic_scholar_id=item.get("paperId"),
            url=item.get("url"),
            source=self.source,
            confidence=0.0,
            raw_metadata={"s2_hit": source_hint, "item": item},
        )


# --- Module-level helpers ---------------------------------------------------


def _normalize_id(paper_id: str) -> str:
    """Canonicalize an S2-shaped paper id for cache/dedup keys.

    ``DOI:10.1/x`` → ``doi:10.1/x``, ``ARXIV:1706.03762v3`` → ``arxiv:1706.03762``,
    plain ``abcdef0123...`` (S2 paperId) is lowercased.
    """
    s = paper_id.strip()
    if ":" in s:
        prefix, rest = s.split(":", 1)
        prefix = prefix.lower()
        rest = rest.strip()
        if prefix == "arxiv":
            rest = rest.split("v")[0]
        return f"{prefix}:{rest.lower()}"
    return s.lower()


def _dedupe_ids(paper_ids: Iterable[str]) -> list[str]:
    """Order-preserving dedup of paper ids using normalized identity."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in paper_ids:
        if not raw:
            continue
        norm = _normalize_id(raw)
        if norm in seen:
            continue
        seen.add(norm)
        out.append(raw)
    return out


def _identity_keys(paper: dict[str, Any]) -> set[str]:
    """All identity tuples for a paper record: {(paperId), (DOI), (arXiv)}."""
    keys: set[str] = set()
    pid = paper.get("paperId")
    if pid:
        keys.add(f"s2:{str(pid).lower()}")
    ext = paper.get("externalIds") or {}
    doi = ext.get("DOI")
    if doi:
        keys.add(f"doi:{str(doi).lower()}")
    arxiv = ext.get("ArXiv") or ext.get("arXiv")
    if arxiv:
        keys.add(f"arxiv:{str(arxiv).split('v')[0].lower()}")
    return keys


def dedupe_papers(papers: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate S2 paper records by DOI / S2 paperId / arXiv id.

    Two papers are considered the same if ANY identity key (DOI, S2 paperId,
    arXiv id) overlaps. Order is preserved; the first occurrence wins. Useful
    when combining results from multiple endpoints (search + references +
    citations) for a single conceptual reference.
    """
    seen_to_idx: dict[str, int] = {}
    result: list[dict[str, Any]] = []
    for paper in papers:
        keys = _identity_keys(paper)
        match_idx: int | None = None
        for k in keys:
            if k in seen_to_idx:
                match_idx = seen_to_idx[k]
                break
        if match_idx is None:
            idx = len(result)
            for k in keys:
                seen_to_idx[k] = idx
            result.append(paper)
        else:
            # Add any new identity keys learned from this duplicate so future
            # records that share *those* keys also dedupe correctly.
            for k in keys:
                seen_to_idx.setdefault(k, match_idx)
    return result

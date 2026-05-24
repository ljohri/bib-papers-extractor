"""Semantic Scholar Academic Graph resolver.

Endpoints:
  - GET /graph/v1/paper/DOI:{doi}
  - GET /graph/v1/paper/arXiv:{arxiv_id}
  - GET /graph/v1/paper/search?query=...
"""

from __future__ import annotations

from typing import Any

from ..models import Reference, ResolvedWork
from .base import BaseResolver

S2_API = "https://api.semanticscholar.org/graph/v1/paper"
_FIELDS = "paperId,externalIds,title,authors,year,openAccessPdf,url"


class SemanticScholarResolver(BaseResolver):
    source = "semantic_scholar"
    base_url = S2_API
    rate_limit_per_sec = 1.0  # public limit is conservative without API key
    cache_ttl_days = 30

    def _build_client(self) -> Any:
        client = super()._build_client()
        if self.settings.semantic_scholar_api_key:
            client.headers["x-api-key"] = self.settings.semantic_scholar_api_key
            self.rate_limit_per_sec = 9.0
        return client

    async def resolve(self, reference: Reference) -> list[ResolvedWork]:
        if reference.doi:
            item = await self._lookup_id(f"DOI:{reference.doi}")
            if item:
                return [self._to_resolved(reference, item, source_hint="s2-doi")]
        if reference.arxiv_id:
            item = await self._lookup_id(f"arXiv:{reference.arxiv_id}")
            if item:
                return [self._to_resolved(reference, item, source_hint="s2-arxiv")]
        if reference.title:
            return await self._search_title(reference)
        return []

    async def _lookup_id(self, paper_id: str) -> dict[str, Any] | None:
        params = {"fields": _FIELDS}
        return await self._get_json(
            f"{S2_API}/{paper_id}",
            params=params,
            cache_key=f"id:{paper_id.lower()}",
        )

    async def _search_title(self, reference: Reference) -> list[ResolvedWork]:
        params: dict[str, Any] = {
            "query": reference.title or "",
            "limit": 5,
            "fields": _FIELDS,
        }
        if reference.year:
            params["year"] = str(reference.year)

        cache_key = f"title:{(reference.title or '').lower()}|y={reference.year or ''}"
        payload = await self._get_json(
            f"{S2_API}/search",
            params=params,
            cache_key=cache_key,
        )
        if not payload:
            return []
        items = payload.get("data", []) or []
        return [self._to_resolved(reference, it, source_hint="s2-search") for it in items]

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
        authors = [(a.get("name") or "").strip() for a in (item.get("authors") or []) if a.get("name")]

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

"""OpenAlex resolver.

Endpoints:
  - GET https://api.openalex.org/works/doi:{doi}
  - GET https://api.openalex.org/works?search={title}&per-page=5
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from ..models import Reference, ResolvedWork
from .base import BaseResolver

OPENALEX_API = "https://api.openalex.org"


class OpenAlexResolver(BaseResolver):
    source = "openalex"
    base_url = OPENALEX_API
    rate_limit_per_sec = 9.0
    cache_ttl_days = 30

    async def resolve(self, reference: Reference) -> list[ResolvedWork]:
        if reference.doi:
            item = await self._lookup_doi(reference.doi)
            if item:
                return [self._to_resolved(reference, item, source_hint="openalex-doi")]
        if reference.title:
            return await self._search_title(reference)
        return []

    async def _lookup_doi(self, doi: str) -> dict[str, Any] | None:
        params = {}
        if self.settings.crossref_mailto:
            params["mailto"] = self.settings.crossref_mailto
        url = f"{OPENALEX_API}/works/doi:{quote(doi, safe='/.')}"
        return await self._get_json(url, params=params, cache_key=f"doi:{doi.lower()}")

    async def _search_title(self, reference: Reference) -> list[ResolvedWork]:
        params: dict[str, Any] = {
            "search": reference.title or "",
            "per-page": 5,
        }
        if reference.year:
            params["filter"] = f"publication_year:{reference.year}"
        if self.settings.crossref_mailto:
            params["mailto"] = self.settings.crossref_mailto

        cache_key = f"title:{(reference.title or '').lower()}|y={reference.year or ''}"
        payload = await self._get_json(
            f"{OPENALEX_API}/works",
            params=params,
            cache_key=cache_key,
        )
        if not payload:
            return []
        items = payload.get("results", []) or []
        return [self._to_resolved(reference, it, source_hint="openalex-search") for it in items]

    def _to_resolved(
        self,
        reference: Reference,
        item: dict[str, Any],
        *,
        source_hint: str,
    ) -> ResolvedWork:
        title = item.get("title") or item.get("display_name") or (reference.title or "")
        authors = []
        for a in item.get("authorships", []) or []:
            disp = (a.get("author") or {}).get("display_name", "")
            if disp:
                authors.append(disp)

        year = item.get("publication_year")
        try:
            year_int = int(year) if year is not None else None
        except (ValueError, TypeError):
            year_int = None

        ids = item.get("ids", {}) or {}
        oa_id = ids.get("openalex") or item.get("id")

        return ResolvedWork(
            reference_id=reference.id,
            title=title,
            authors=authors,
            year=year_int,
            doi=(item.get("doi") or "").replace("https://doi.org/", "").lower() or None,
            openalex_id=str(oa_id).split("/")[-1] if oa_id else None,
            url=ids.get("openalex") or item.get("doi"),
            source=self.source,
            confidence=0.0,
            raw_metadata={"openalex_hit": source_hint, "item": item},
        )

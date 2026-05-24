"""Crossref REST API resolver.

Endpoints used:
  - GET https://api.crossref.org/works/{doi}        (DOI lookup)
  - GET https://api.crossref.org/works?query.bibliographic=...  (title/author search)
"""

from __future__ import annotations

from typing import Any

from ..models import Reference, ResolvedWork
from .base import BaseResolver

CROSSREF_API = "https://api.crossref.org"


class CrossrefResolver(BaseResolver):
    source = "crossref"
    base_url = CROSSREF_API
    rate_limit_per_sec = 8.0
    cache_ttl_days = 30

    async def resolve(self, reference: Reference) -> list[ResolvedWork]:
        if reference.doi:
            work = await self._lookup_doi(reference.doi)
            if work:
                return [self._to_resolved(reference, work, source_hint="crossref-doi")]
        if reference.title:
            return await self._search_title(reference)
        return []

    async def _lookup_doi(self, doi: str) -> dict[str, Any] | None:
        params = {}
        if self.settings.crossref_mailto:
            params["mailto"] = self.settings.crossref_mailto
        url = f"{CROSSREF_API}/works/{doi}"
        payload = await self._get_json(url, params=params, cache_key=f"doi:{doi.lower()}")
        if not payload:
            return None
        return payload.get("message")

    async def _search_title(self, reference: Reference) -> list[ResolvedWork]:
        params: dict[str, Any] = {
            "query.bibliographic": reference.title or "",
            "rows": 5,
        }
        if reference.year:
            params["filter"] = f"from-pub-date:{reference.year},until-pub-date:{reference.year}"
        if self.settings.crossref_mailto:
            params["mailto"] = self.settings.crossref_mailto

        cache_key = f"title:{(reference.title or '').lower()}|y={reference.year or ''}"
        payload = await self._get_json(
            f"{CROSSREF_API}/works",
            params=params,
            cache_key=cache_key,
        )
        if not payload:
            return []
        items = payload.get("message", {}).get("items", []) or []
        return [self._to_resolved(reference, it, source_hint="crossref-search") for it in items]

    def _to_resolved(
        self,
        reference: Reference,
        item: dict[str, Any],
        *,
        source_hint: str,
    ) -> ResolvedWork:
        title_list = item.get("title") or []
        title = title_list[0] if title_list else (reference.title or "")

        authors = []
        for a in item.get("author", []) or []:
            given = a.get("given", "") or ""
            family = a.get("family", "") or ""
            full = f"{family}, {given}".strip(", ").strip()
            if full:
                authors.append(full)

        year = None
        issued = item.get("issued", {}).get("date-parts", [])
        if issued and isinstance(issued, list) and issued[0]:
            try:
                year = int(issued[0][0])
            except (ValueError, TypeError):
                year = None

        return ResolvedWork(
            reference_id=reference.id,
            title=title,
            authors=authors,
            year=year,
            doi=(item.get("DOI") or "").lower() or None,
            url=item.get("URL"),
            source=self.source,
            confidence=0.0,  # final score assigned by the pipeline
            raw_metadata={"crossref_hit": source_hint, "item": item},
        )

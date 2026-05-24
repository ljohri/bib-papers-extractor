"""arXiv API resolver.

Uses the public Atom-XML query endpoint:
  http://export.arxiv.org/api/query?id_list=...
  http://export.arxiv.org/api/query?search_query=ti:"..."&max_results=5
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from ..models import Reference, ResolvedWork
from .base import BaseResolver

ARXIV_API = "http://export.arxiv.org/api/query"
_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


class ArxivResolver(BaseResolver):
    source = "arxiv"
    base_url = ARXIV_API
    rate_limit_per_sec = 3.0
    cache_ttl_days = 7

    async def resolve(self, reference: Reference) -> list[ResolvedWork]:
        if reference.arxiv_id:
            xml = await self._get_xml({"id_list": reference.arxiv_id})
            return self._parse(xml, reference, source_hint="arxiv-id")
        if reference.title:
            query = f'ti:"{reference.title}"'
            xml = await self._get_xml(
                {
                    "search_query": query,
                    "max_results": "5",
                }
            )
            return self._parse(xml, reference, source_hint="arxiv-search")
        return []

    async def _get_xml(self, params: dict[str, Any]) -> str | None:
        return await self._get_text(ARXIV_API, params=params)

    def _parse(
        self, xml: str | None, reference: Reference, *, source_hint: str
    ) -> list[ResolvedWork]:
        if not xml:
            return []
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            return []

        out: list[ResolvedWork] = []
        for entry in root.findall("atom:entry", _NS):
            title_el = entry.find("atom:title", _NS)
            id_el = entry.find("atom:id", _NS)
            published_el = entry.find("atom:published", _NS)
            doi_el = entry.find("arxiv:doi", _NS)

            title = (title_el.text or "").strip() if title_el is not None else ""
            arxiv_id = None
            if id_el is not None and id_el.text:
                arxiv_id = id_el.text.rsplit("/", 1)[-1].split("v")[0]

            year = None
            if published_el is not None and published_el.text:
                try:
                    year = int(published_el.text[:4])
                except ValueError:
                    year = None

            authors = []
            for a in entry.findall("atom:author", _NS):
                name_el = a.find("atom:name", _NS)
                if name_el is not None and name_el.text:
                    authors.append(name_el.text.strip())

            doi = (doi_el.text or "").strip().lower() if doi_el is not None and doi_el.text else None

            out.append(
                ResolvedWork(
                    reference_id=reference.id,
                    title=title,
                    authors=authors,
                    year=year,
                    doi=doi,
                    arxiv_id=arxiv_id,
                    url=id_el.text if id_el is not None else None,
                    source=self.source,
                    confidence=0.0,
                    raw_metadata={
                        "arxiv_hit": source_hint,
                        "entry_xml": ET.tostring(entry, encoding="unicode"),
                    },
                )
            )
        return out

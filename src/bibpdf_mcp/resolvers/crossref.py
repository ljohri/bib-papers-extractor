"""Crossref REST API resolver. Phase 1 stub."""

from __future__ import annotations

from ..models import Reference, ResolvedWork
from .base import BaseResolver


class CrossrefResolver(BaseResolver):
    source = "crossref"

    async def resolve(self, reference: Reference) -> list[ResolvedWork]:
        raise NotImplementedError("Phase 3: implement Crossref resolver.")

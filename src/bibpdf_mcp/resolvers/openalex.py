"""OpenAlex resolver. Phase 1 stub."""

from __future__ import annotations

from ..models import Reference, ResolvedWork
from .base import BaseResolver


class OpenAlexResolver(BaseResolver):
    source = "openalex"

    async def resolve(self, reference: Reference) -> list[ResolvedWork]:
        raise NotImplementedError("Phase 3: implement OpenAlex resolver.")

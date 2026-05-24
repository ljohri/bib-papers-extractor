"""Base class for async metadata resolvers.

Phase 1 stub. Real httpx/tenacity/aiolimiter wiring lands in Phase 3.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Reference, ResolvedWork


class BaseResolver(ABC):
    """Common interface for all metadata resolvers."""

    source: str = "base"

    @abstractmethod
    async def resolve(self, reference: Reference) -> list[ResolvedWork]:
        """Return zero or more candidate ResolvedWork entries for the reference."""
        raise NotImplementedError

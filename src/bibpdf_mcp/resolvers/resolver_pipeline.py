"""Composes individual resolvers into a precedence-ordered, confidence-scored pipeline.

Phase 1 stub.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..models import Reference, ResolvedWork


async def resolve_all(
    references: Iterable[Reference],
    *,
    strategy: str = "balanced",
) -> list[ResolvedWork]:
    """Run the resolver pipeline over a batch of references."""
    raise NotImplementedError("Phase 3: implement resolver pipeline.")

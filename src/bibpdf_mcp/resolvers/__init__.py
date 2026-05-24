"""Metadata resolvers: Crossref, OpenAlex, Semantic Scholar, arXiv + pipeline."""

from .arxiv import ArxivResolver
from .base import BaseResolver
from .crossref import CrossrefResolver
from .openalex import OpenAlexResolver
from .resolver_pipeline import build_resolvers, resolve_all, score
from .semantic_scholar import SemanticScholarResolver

__all__ = [
    "BaseResolver",
    "ArxivResolver",
    "CrossrefResolver",
    "OpenAlexResolver",
    "SemanticScholarResolver",
    "build_resolvers",
    "resolve_all",
    "score",
]

"""Tests for the deterministic filename policy."""

from __future__ import annotations

from bibpdf_mcp.models import ResolvedWork
from bibpdf_mcp.storage.filename_policy import build_filename


def _work(**kwargs: object) -> ResolvedWork:
    base: dict[str, object] = {
        "reference_id": "r1",
        "title": "Attention Is All You Need",
        "authors": ["Vaswani, Ashish"],
        "year": 2017,
        "doi": "10.foo/bar",
        "source": "arxiv",
        "confidence": 0.98,
    }
    base.update(kwargs)
    return ResolvedWork(**base)


def test_filename_matches_spec_example() -> None:
    name = build_filename(_work())
    assert name.startswith("2017_Vaswani_AttentionIsAllYouNeed_")
    assert name.endswith(".pdf")
    # 6 hex chars + ".pdf"
    suffix = name.rsplit("_", 1)[1]
    hash_part = suffix.removesuffix(".pdf")
    assert len(hash_part) == 6
    int(hash_part, 16)  # validates hex


def test_filename_deterministic_for_same_input() -> None:
    a = build_filename(_work())
    b = build_filename(_work())
    assert a == b


def test_filename_handles_missing_year() -> None:
    name = build_filename(_work(year=None))
    assert name.startswith("0000_Vaswani_")


def test_filename_handles_missing_authors_and_title() -> None:
    name = build_filename(_work(authors=[], title=""))
    assert name.startswith("2017_Unknown_UnknownTitle_")


def test_filename_ascii_folds_unicode() -> None:
    name = build_filename(
        _work(authors=["López, María"], title="Análisis de cómo las cosas")
    )
    # No non-ASCII characters in the result.
    assert all(ord(c) < 128 for c in name)
    assert name.startswith("2017_Lopez_")


def test_filename_safe_for_filesystem() -> None:
    name = build_filename(_work(title="A study: with / weird \\ chars?!"))
    # Only alphanumerics, underscore, and ".pdf".
    stem = name.removesuffix(".pdf")
    assert all(c.isalnum() or c == "_" for c in stem)

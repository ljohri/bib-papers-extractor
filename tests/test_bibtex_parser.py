"""Tests for the BibTeX parser."""

from __future__ import annotations

from pathlib import Path

from bibpdf_mcp.extraction.bibtex_parser import parse_bibtex_file


def test_parse_bibtex_returns_typed_references(sample_bibtex: Path) -> None:
    refs = parse_bibtex_file(sample_bibtex)
    assert len(refs) == 2

    by_key = {r.bibtex_key: r for r in refs}
    assert "vaswani2017" in by_key
    assert "devlin2019bert" in by_key

    v = by_key["vaswani2017"]
    assert v.title == "Attention Is All You Need"
    assert v.year == 2017
    assert v.arxiv_id == "1706.03762"
    assert "Vaswani, Ashish" in v.authors

    d = by_key["devlin2019bert"]
    assert d.title and d.title.lower().startswith("bert")
    assert d.year == 2019
    assert d.doi == "10.18653/v1/n19-1423"


def test_parse_bibtex_missing_file(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(FileNotFoundError):
        parse_bibtex_file(tmp_path / "nope.bib")

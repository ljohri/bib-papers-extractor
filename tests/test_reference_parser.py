"""Tests for the heuristic reference parser."""

from __future__ import annotations

from bibpdf_mcp.extraction.reference_parser import (
    parse_reference,
    parse_references_from_text,
    split_references,
)


def test_split_blank_line_separated() -> None:
    text = (
        "[1] Smith J. A study. Journal, 2020.\n\n"
        "[2] Doe J. Another study. Journal, 2021.\n\n"
        "[3] Roe R. Yet another. Journal, 2022."
    )
    parts = split_references(text)
    assert len(parts) == 3
    assert parts[0].startswith("[1]")
    assert parts[1].startswith("[2]")


def test_split_inline_numbered() -> None:
    text = "[1] Smith. T1. 2020. [2] Doe. T2. 2021. [3] Roe. T3. 2022."
    parts = split_references(text)
    # Either path (blank-line or inline-numbered) should yield >=2 entries
    assert len(parts) >= 2


def test_parse_reference_extracts_arxiv_year_authors() -> None:
    raw = "Vaswani A., Shazeer N. Attention is all you need. NeurIPS 2017. arXiv:1706.03762"
    r = parse_reference(raw, "ref-1")
    assert r.year == 2017
    assert r.arxiv_id == "1706.03762"
    assert r.authors and r.authors[0].lower().startswith("vaswani")
    assert r.title and "attention" in r.title.lower()


def test_parse_reference_extracts_doi() -> None:
    raw = "Smith J. A study of things. Journal, 2018. doi:10.1234/abc.456"
    r = parse_reference(raw, "ref-2")
    assert r.doi == "10.1234/abc.456"
    assert r.year == 2018


def test_parse_reference_arxiv_id_does_not_become_year() -> None:
    """Year inside an arXiv id (e.g. 2005.14165) must not be extracted as year."""
    raw = "Brown T. Language Models are Few-Shot Learners. arXiv:2005.14165, 2020."
    r = parse_reference(raw, "ref-3")
    assert r.year == 2020
    assert r.arxiv_id == "2005.14165"


def test_dehyphenation_preserves_hyphen() -> None:
    raw = (
        "[10] Saurabh Gaurav, Jussi Heikkonen, and Jatin Chaudhary. 2025. Governance-\n"
        "as-a-Service: A Multi-Agent Framework for AI System Compliance and Policy\n"
        "Enforcement. arXiv preprint arXiv:2508.18765 (2025)."
    )
    parts = split_references(raw)
    assert len(parts) == 1
    r = parse_reference(parts[0], "ref-10")
    assert r.arxiv_id == "2508.18765"
    assert r.title and "Governance-as-a-Service" in r.title
    assert r.authors and any("Gaurav" in a for a in r.authors)
    assert "Governanceas-a-Service" not in (r.title or "")


def test_year_after_author_period_does_not_split_reference() -> None:
    """``Author. 2025. Title`` must stay one entry — 2025 is not a list number."""
    raw = (
        "[10] Saurabh Gaurav, Jussi Heikkonen, and Jatin Chaudhary. 2025. Governance-\n"
        "as-a-Service: A Multi-Agent Framework. arXiv preprint arXiv:2508.18765 (2025).\n"
        "[11] Sakuna Harinda Jayasundara. 2023. SoK paper title here."
    )
    parts = split_references(raw)
    assert len(parts) == 2
    assert "2508.18765" in parts[0]
    assert "Chaudhary" in parts[0]
    assert parts[1].startswith("[11]")


def test_parse_references_from_text_round_trip() -> None:
    text = (
        "[1] Smith J. First paper. Journal, 2018. doi:10.1234/abc.1\n\n"
        "[2] Doe J. Second paper. Conference, 2019. arXiv:1907.12345"
    )
    refs = parse_references_from_text(text)
    assert len(refs) == 2
    assert refs[0].doi == "10.1234/abc.1"
    assert refs[1].arxiv_id == "1907.12345"

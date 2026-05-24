"""Shared pytest fixtures.

We synthesize a tiny PDF and BibTeX file at session start so the repo doesn't
need to track binary fixtures. The synthetic PDF is small (~1 page) and
deterministic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SYNTH_PDF = FIXTURES_DIR / "synthetic_paper.pdf"
SYNTH_BIB = FIXTURES_DIR / "sample.bib"


_BIBTEX = """\
@inproceedings{vaswani2017,
  author    = {Vaswani, Ashish and Shazeer, Noam and Parmar, Niki},
  title     = {Attention Is All You Need},
  booktitle = {NeurIPS},
  year      = {2017},
  eprint    = {1706.03762},
  archivePrefix = {arXiv},
}

@article{devlin2019bert,
  author    = {Devlin, Jacob and Chang, Ming-Wei and Lee, Kenton and Toutanova, Kristina},
  title     = {{BERT}: Pre-training of Deep Bidirectional Transformers for Language Understanding},
  journal   = {NAACL},
  year      = {2019},
  doi       = {10.18653/v1/N19-1423},
}
"""


@pytest.fixture(scope="session", autouse=True)
def _build_fixtures() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    if not SYNTH_BIB.exists():
        SYNTH_BIB.write_text(_BIBTEX, encoding="utf-8")

    if not SYNTH_PDF.exists():
        import pymupdf  # type: ignore[import-untyped]

        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((50, 50), "Synthetic Paper Title")
        page.insert_text((50, 80), "Authors: A. Test, B. Example.")
        page.insert_text((50, 140), "Body of paper. See [1] and [2] for details.")
        page.insert_text((50, 220), "References")
        page.insert_text(
            (50, 250),
            "[1] Vaswani A., Shazeer N. Attention is all you need. NeurIPS 2017. arXiv:1706.03762",
        )
        page.insert_text(
            (50, 280),
            "[2] Devlin J. BERT pre-training. NAACL 2019. doi:10.18653/v1/N19-1423",
        )
        doc.save(str(SYNTH_PDF))
        doc.close()


@pytest.fixture
def synthetic_pdf() -> Path:
    return SYNTH_PDF


@pytest.fixture
def sample_bibtex() -> Path:
    return SYNTH_BIB


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Force tests to use a per-test SQLite cache so they don't pollute the repo cache.

    We also blank out polite-pool emails/keys to keep tests hermetic.
    """
    monkeypatch.setenv("CACHE_DB_PATH", str(tmp_path / "test_cache.sqlite"))
    monkeypatch.setenv("DEFAULT_INPUT_DIR", str(tmp_path / "in"))
    monkeypatch.setenv("DEFAULT_OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("UNPAYWALL_EMAIL", "test@example.com")
    monkeypatch.setenv("CROSSREF_MAILTO", "test@example.com")
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.setenv("MAX_CONCURRENT_REQUESTS", "5")
    monkeypatch.setenv("AUTO_DOWNLOAD_CONFIDENCE_THRESHOLD", "0.80")

    # bust the lru_cache in config.get_settings so each test sees fresh env.
    from bibpdf_mcp import config

    config.get_settings.cache_clear()

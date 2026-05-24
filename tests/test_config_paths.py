"""Tests for default output path resolution in Settings."""

from __future__ import annotations

from pathlib import Path

import pytest

from bibpdf_mcp import config


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()


def test_resolve_output_dir_uses_explicit_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    default = tmp_path / "default-out"
    override = tmp_path / "custom-out"
    default.mkdir()
    monkeypatch.setenv("DEFAULT_OUTPUT_DIR", str(default))
    settings = config.get_settings()
    assert settings.resolve_output_dir(str(override)) == override.resolve()


def test_resolve_output_dir_falls_back_to_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    default = tmp_path / "default-out"
    default.mkdir()
    monkeypatch.setenv("DEFAULT_OUTPUT_DIR", str(default))
    settings = config.get_settings()
    assert settings.resolve_output_dir(None) == default.resolve()
    assert settings.resolve_output_dir("") == default.resolve()


def test_resolve_file_path(synthetic_pdf: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = config.get_settings()
    assert settings.resolve_file_path(synthetic_pdf, label="PDF") == synthetic_pdf.resolve()


def test_resolve_file_path_missing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    missing = tmp_path / "nope.pdf"
    settings = config.get_settings()
    with pytest.raises(FileNotFoundError, match="PDF not found"):
        settings.resolve_file_path(missing, label="PDF")


def test_ensure_dirs_creates_input_and_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    inp = tmp_path / "in"
    out = tmp_path / "out"
    monkeypatch.setenv("DEFAULT_INPUT_DIR", str(inp))
    monkeypatch.setenv("DEFAULT_OUTPUT_DIR", str(out))
    settings = config.get_settings()
    settings.ensure_dirs()
    assert inp.is_dir()
    assert out.is_dir()

"""Runtime configuration loaded from environment variables / .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings sourced from process environment and optional `.env` file.

    Environment variables take precedence over `.env`. All paths are resolved
    relative to the current working directory if not absolute.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    unpaywall_email: str = Field(default="", alias="UNPAYWALL_EMAIL")
    semantic_scholar_api_key: str = Field(default="", alias="SEMANTIC_SCHOLAR_API_KEY")
    crossref_mailto: str = Field(default="", alias="CROSSREF_MAILTO")

    cache_db_path: Path = Field(default=Path("./cache/bibpdf.sqlite"), alias="CACHE_DB_PATH")
    default_input_dir: Path = Field(default=Path("./data/input"), alias="DEFAULT_INPUT_DIR")
    default_input_pdf: Path | None = Field(default=None, alias="DEFAULT_INPUT_PDF")
    default_input_bibtex: Path | None = Field(default=None, alias="DEFAULT_INPUT_BIBTEX")
    default_output_dir: Path = Field(default=Path("./data/output"), alias="DEFAULT_OUTPUT_DIR")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    max_concurrent_requests: int = Field(default=5, alias="MAX_CONCURRENT_REQUESTS", ge=1, le=64)
    auto_download_confidence_threshold: float = Field(
        default=0.80,
        alias="AUTO_DOWNLOAD_CONFIDENCE_THRESHOLD",
        ge=0.0,
        le=1.0,
    )

    user_agent: str = Field(
        default="bibpdf-mcp/0.1 (+https://github.com/ljohri/bib-papers-extractor)",
        alias="USER_AGENT",
    )

    def ensure_dirs(self) -> None:
        """Create the cache and default input/output directories if missing."""
        self.cache_db_path.parent.mkdir(parents=True, exist_ok=True)
        self.default_input_dir.mkdir(parents=True, exist_ok=True)
        self.default_output_dir.mkdir(parents=True, exist_ok=True)

    def resolve_output_dir(self, path: str | Path | None = None) -> Path:
        """Resolve an output directory.

        Precedence: explicit ``path`` argument > ``DEFAULT_OUTPUT_DIR`` env.
        """
        if path is not None and str(path).strip():
            return Path(path).expanduser().resolve()
        return self.default_output_dir.expanduser().resolve()

    def resolve_input_pdf(self, path: str | Path | None = None) -> Path:
        """Resolve an input PDF path.

        Precedence: explicit ``path`` > ``DEFAULT_INPUT_PDF`` > raise.
        """
        if path is not None and str(path).strip():
            resolved = Path(path).expanduser().resolve()
        elif self.default_input_pdf is not None:
            resolved = self.default_input_pdf.expanduser().resolve()
        else:
            msg = (
                "pdf_path is required when DEFAULT_INPUT_PDF is not set. "
                "Pass pdf_path to the tool or set DEFAULT_INPUT_PDF in the environment."
            )
            raise ValueError(msg)
        if not resolved.is_file():
            raise FileNotFoundError(f"PDF not found: {resolved}")
        return resolved

    def resolve_input_bibtex(self, path: str | Path | None = None) -> Path:
        """Resolve an input BibTeX path.

        Precedence: explicit ``path`` > ``DEFAULT_INPUT_BIBTEX`` > raise.
        """
        if path is not None and str(path).strip():
            resolved = Path(path).expanduser().resolve()
        elif self.default_input_bibtex is not None:
            resolved = self.default_input_bibtex.expanduser().resolve()
        else:
            msg = (
                "bibtex_path is required when DEFAULT_INPUT_BIBTEX is not set. "
                "Pass bibtex_path to the tool or set DEFAULT_INPUT_BIBTEX in the environment."
            )
            raise ValueError(msg)
        if not resolved.is_file():
            raise FileNotFoundError(f"BibTeX file not found: {resolved}")
        return resolved


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a memoized Settings instance."""
    return Settings()

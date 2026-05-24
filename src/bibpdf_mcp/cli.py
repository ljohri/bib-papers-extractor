"""Typer-based CLI for local development & testing.

In Phase 1 the subcommands are skeletons that print intended behavior; Phase 5 wires
them to the real pipeline.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from . import __version__
from .logging_config import configure_logging

app = typer.Typer(
    name="bibpdf",
    help="Bibliography PDF MCP — extract references and download legal OA PDFs.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"bibpdf {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
    log_level: str = typer.Option(
        "INFO",
        "--log-level",
        help="Logging level (DEBUG, INFO, WARNING, ERROR).",
    ),
) -> None:
    configure_logging(log_level)


@app.command("extract-pdf")
def extract_pdf(
    pdf_path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    output: Path | None = typer.Option(None, "--output", "-o", help="Optional JSON output path."),
) -> None:
    """Extract references from a paper PDF."""
    console.print(f"[yellow]Phase 1 stub:[/] would extract references from {pdf_path}")


@app.command("parse-bibtex")
def parse_bibtex(
    bibtex_path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Parse a BibTeX file into the internal Reference model."""
    console.print(f"[yellow]Phase 1 stub:[/] would parse BibTeX file {bibtex_path}")


@app.command("resolve")
def resolve(
    references_json: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    strategy: str = typer.Option("balanced", "--strategy", help="fast|balanced|deep"),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Resolve references against Crossref/OpenAlex/Semantic Scholar/arXiv."""
    console.print(
        f"[yellow]Phase 1 stub:[/] would resolve references from {references_json} "
        f"with strategy={strategy}"
    )


@app.command("find-pdfs")
def find_pdfs(
    resolved_json: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Find legal OA PDFs for resolved works."""
    console.print(f"[yellow]Phase 1 stub:[/] would locate OA PDFs for {resolved_json}")


@app.command("download")
def download(
    candidates_json: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    output_dir: Path = typer.Option(..., "--output-dir", help="Directory to write PDFs into."),
) -> None:
    """Download approved PDF candidates."""
    console.print(
        f"[yellow]Phase 1 stub:[/] would download candidates from {candidates_json} "
        f"into {output_dir}"
    )


@app.command("process-paper")
def process_paper(
    pdf_path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    output_dir: Path = typer.Option(..., "--output-dir"),
    strategy: str = typer.Option("balanced", "--strategy"),
) -> None:
    """End-to-end pipeline: PDF -> references -> resolved -> OA PDFs -> manifest+report."""
    console.print(
        f"[yellow]Phase 1 stub:[/] would run full pipeline on {pdf_path} -> {output_dir} "
        f"(strategy={strategy})"
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()

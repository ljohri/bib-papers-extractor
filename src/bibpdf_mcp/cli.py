"""Typer-based CLI for local development & testing."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from . import __version__, pipeline
from .logging_config import configure_logging
from .models import PdfCandidate, Reference, ResolvedWork

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


# --- helpers ---------------------------------------------------------------


def _dump(obj: object, output: Path | None) -> None:
    if hasattr(obj, "model_dump"):
        data = obj.model_dump(mode="json")
    elif isinstance(obj, list) and obj and hasattr(obj[0], "model_dump"):
        data = [o.model_dump(mode="json") for o in obj]
    else:
        data = obj
    text = json.dumps(data, indent=2, ensure_ascii=False)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
        console.print(f"[green]Wrote[/] {output}")
    else:
        console.print(text)


# --- commands --------------------------------------------------------------


@app.command("extract-pdf")
def extract_pdf(
    pdf_path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    output: Path | None = typer.Option(None, "--output", "-o", help="Optional JSON output path."),
) -> None:
    """Extract references from a paper PDF."""
    refs = pipeline.extract_references_from_pdf(pdf_path)
    console.print(f"Extracted [bold]{len(refs)}[/] references from {pdf_path}")
    _dump(refs, output)


@app.command("parse-bibtex")
def parse_bibtex(
    bibtex_path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Parse a BibTeX file into the internal Reference model."""
    refs = pipeline.parse_bibtex_file(bibtex_path)
    console.print(f"Parsed [bold]{len(refs)}[/] entries from {bibtex_path}")
    _dump(refs, output)


@app.command("resolve")
def resolve(
    references_json: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    strategy: str = typer.Option("balanced", "--strategy", help="fast|balanced|deep"),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Resolve references against Crossref/OpenAlex/Semantic Scholar/arXiv."""
    payload = json.loads(references_json.read_text(encoding="utf-8"))
    refs = [Reference.model_validate(r) for r in payload]
    resolved = asyncio.run(pipeline.resolve_references(refs, strategy=strategy))
    console.print(f"Resolved [bold]{len(resolved)}[/] / {len(refs)} references")
    _dump(resolved, output)


@app.command("find-pdfs")
def find_pdfs(
    resolved_json: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Find legal OA PDFs for resolved works."""
    payload = json.loads(resolved_json.read_text(encoding="utf-8"))
    works = [ResolvedWork.model_validate(w) for w in payload]
    cands = asyncio.run(pipeline.find_public_pdfs(works))
    n_oa = sum(1 for c in cands if c.is_oa)
    console.print(f"Found [bold]{n_oa}[/] OA candidates ({len(cands)} total) from {len(works)} works")
    _dump(cands, output)


@app.command("download")
def download(
    candidates_json: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    output_dir: Path = typer.Option(..., "--output-dir", help="Directory to write PDFs into."),
) -> None:
    """Download approved PDF candidates."""
    payload = json.loads(candidates_json.read_text(encoding="utf-8"))
    cands = [PdfCandidate.model_validate(c) for c in payload]
    results = asyncio.run(pipeline.download_public_pdfs(cands, output_dir))

    table = Table(title="Download results")
    table.add_column("ref_id")
    table.add_column("status")
    table.add_column("file/error")
    for r in results:
        table.add_row(r.reference_id, r.status, (r.file_path or r.error or "")[:80])
    console.print(table)


@app.command("process-paper")
def process_paper(
    pdf_path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    output_dir: Path = typer.Option(..., "--output-dir"),
    strategy: str = typer.Option("balanced", "--strategy"),
) -> None:
    """End-to-end pipeline: PDF -> references -> resolved -> OA PDFs -> manifest+report."""
    summary = asyncio.run(
        pipeline.process_paper_bibliography(pdf_path, output_dir, strategy=strategy)
    )
    console.print_json(data=summary)


def main() -> None:
    app()


if __name__ == "__main__":
    main()

"""Markdown report writer.

Generates ``report.md`` in the output directory with the spec's prescribed
sections: Summary, Downloaded PDFs, Not Downloaded, Low Confidence Matches.
"""

from __future__ import annotations

from pathlib import Path

from ..models import DownloadResult, Reference, ResolvedWork, RunManifest


def _md_escape(text: str | None) -> str:
    if not text:
        return ""
    return text.replace("|", "\\|").replace("\n", " ").strip()


def write_markdown_report(manifest: RunManifest, output_dir: str | Path) -> Path:
    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    path = out / "report.md"

    refs_by_id: dict[str, Reference] = {r.id: r for r in manifest.references}
    works_by_id: dict[str, ResolvedWork] = {w.reference_id: w for w in manifest.resolved}
    downloads_by_id: dict[str, DownloadResult] = {d.reference_id: d for d in manifest.downloads}

    lines: list[str] = []
    s = manifest.summary
    lines.append("# Bibliography PDF Download Report\n")
    lines.append("## Summary\n")
    lines.append(f"- Source paper: `{manifest.source_path}`")
    lines.append(f"- Run id: `{manifest.run_id}`")
    lines.append(f"- Strategy: `{manifest.strategy}`")
    lines.append(f"- Started: {manifest.started_at.isoformat()}")
    if manifest.finished_at:
        lines.append(f"- Finished: {manifest.finished_at.isoformat()}")
    lines.append(f"- References found: **{s.references_found}**")
    lines.append(f"- References resolved: **{s.references_resolved}**")
    lines.append(f"- Public PDFs found: **{s.pdfs_found}**")
    lines.append(f"- PDFs downloaded: **{s.pdfs_downloaded}**")
    lines.append(f"- Failed: **{s.pdfs_failed}**")
    lines.append(f"- Skipped: **{s.pdfs_skipped}**")
    lines.append("")

    # --- Downloaded PDFs --------------------------------------------------
    lines.append("## Downloaded PDFs\n")
    lines.append("| # | Title | Year | Source | License | File |")
    lines.append("|---|-------|------|--------|---------|------|")
    n = 0
    for d in manifest.downloads:
        if d.status != "downloaded":
            continue
        n += 1
        work = works_by_id.get(d.reference_id)
        ref = refs_by_id.get(d.reference_id)
        title_src = work.title if work else (ref.title if ref else "")
        title = _md_escape(title_src) or "(no title)"
        year = str(work.year) if work and work.year else ""
        # Find source license from the candidate evidence in the manifest
        candidate = next(
            (c for c in manifest.pdf_candidates if c.reference_id == d.reference_id and c.url == d.url),
            None,
        )
        source = candidate.source if candidate else ""
        lic = (candidate.license if candidate else None) or ""
        file_str = f"`{Path(d.file_path).name}`" if d.file_path else ""
        lines.append(f"| {n} | {title} | {year} | {source} | {_md_escape(lic)} | {file_str} |")
    if n == 0:
        lines.append("| — | _(none)_ | | | | |")
    lines.append("")

    # --- Not Downloaded ---------------------------------------------------
    lines.append("## Not Downloaded\n")
    lines.append("| # | Raw Reference | Reason |")
    lines.append("|---|---------------|--------|")
    n = 0
    for ref in manifest.references:
        d = downloads_by_id.get(ref.id)
        reason: str
        if d is not None and d.status == "downloaded":
            continue
        if d is not None and d.status in {"failed", "skipped"}:
            reason = d.error or d.status
        else:
            # No download attempted: either unresolved or no PDF candidate
            if ref.id not in works_by_id:
                reason = "unresolved"
            elif not any(c.reference_id == ref.id for c in manifest.pdf_candidates):
                reason = "no_oa_pdf_found"
            else:
                reason = "no_allowed_candidate"
        n += 1
        raw = _md_escape(ref.raw[:200])
        lines.append(f"| {n} | {raw} | {_md_escape(reason)} |")
    if n == 0:
        lines.append("| — | _(none)_ | |")
    lines.append("")

    # --- Low confidence matches ------------------------------------------
    lines.append("## Low Confidence Matches\n")
    lines.append("| # | Reference | Candidate | Confidence | Action |")
    lines.append("|---|-----------|-----------|------------|--------|")
    n = 0
    for entry in manifest.low_confidence:
        n += 1
        lines.append(
            f"| {n} | {_md_escape(entry.get('reference_raw'))} | "
            f"{_md_escape(entry.get('candidate_title'))} | {entry.get('confidence', 0):.2f} | "
            f"{_md_escape(entry.get('action'))} |"
        )
    if n == 0:
        lines.append("| — | _(none)_ | | | |")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path

"""Tests for the manifest writer and Markdown report shape."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from bibpdf_mcp.models import (
    DownloadResult,
    PdfCandidate,
    Reference,
    ResolvedWork,
    RunManifest,
    RunSummary,
)
from bibpdf_mcp.reports.json_report import write_json_report
from bibpdf_mcp.reports.markdown_report import write_markdown_report
from bibpdf_mcp.storage.manifest import read_manifest, write_manifest


def _build_manifest() -> RunManifest:
    return RunManifest(
        run_id="test-run",
        source_path="/tmp/paper.pdf",
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        strategy="balanced",
        summary=RunSummary(
            references_found=2,
            references_resolved=1,
            pdfs_found=1,
            pdfs_downloaded=1,
        ),
        references=[
            Reference(id="r1", raw="Vaswani et al. Attention is all you need."),
            Reference(id="r2", raw="Smith J. Mystery paper."),
        ],
        resolved=[
            ResolvedWork(
                reference_id="r1",
                title="Attention Is All You Need",
                year=2017,
                doi="10.foo/bar",
                source="crossref",
                confidence=1.0,
            )
        ],
        pdf_candidates=[
            PdfCandidate(
                reference_id="r1",
                url="https://arxiv.org/pdf/1706.03762.pdf",
                source="arxiv",
                license="arxiv-nonexclusive",
                is_oa=True,
                confidence=0.97,
            )
        ],
        downloads=[
            DownloadResult(
                reference_id="r1",
                url="https://arxiv.org/pdf/1706.03762.pdf",
                status="downloaded",
                file_path="/tmp/out/2017_Vaswani_AttentionIsAllYouNeed_aabbcc.pdf",
                bytes_written=1234,
                content_type="application/pdf",
            )
        ],
        low_confidence=[
            {
                "reference_id": "r2",
                "reference_raw": "Smith J. Mystery paper.",
                "candidate_title": "Some unrelated thing",
                "confidence": 0.45,
                "action": "skipped (below threshold 0.80)",
            }
        ],
    )


def test_manifest_round_trip(tmp_path: Path) -> None:
    m = _build_manifest()
    p = write_manifest(m, tmp_path)
    assert p.exists()
    m2 = read_manifest(p)
    assert m2.run_id == m.run_id
    assert len(m2.references) == 2
    assert len(m2.resolved) == 1
    assert m2.summary.pdfs_downloaded == 1
    assert m2.downloads[0].status == "downloaded"


def test_markdown_report_shape(tmp_path: Path) -> None:
    m = _build_manifest()
    rp = write_markdown_report(m, tmp_path)
    text = rp.read_text(encoding="utf-8")
    assert "# Bibliography PDF Download Report" in text
    assert "## Summary" in text
    assert "## Downloaded PDFs" in text
    assert "## Not Downloaded" in text
    assert "## Low Confidence Matches" in text
    assert "Attention Is All You Need" in text
    assert "Smith J. Mystery paper." in text
    assert "0.45" in text


def test_json_report(tmp_path: Path) -> None:
    m = _build_manifest()
    rp = write_json_report(m, tmp_path)
    import json

    payload = json.loads(rp.read_text(encoding="utf-8"))
    assert payload["run_id"] == "test-run"
    assert payload["summary"]["pdfs_downloaded"] == 1
    assert len(payload["downloads"]) == 1

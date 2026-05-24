"""End-to-end integration test for `pipeline.process_paper_bibliography`.

Network is fully mocked via respx. We use the synthetic fixture PDF generated
by `conftest.py` and assert the manifest, report, and downloaded PDF land in
the expected places.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from bibpdf_mcp import pipeline

_PDF_BYTES = b"%PDF-1.4\n%mocked OA pdf\n%%EOF\n"


@pytest.mark.asyncio
async def test_process_paper_bibliography_end_to_end(
    respx_mock: respx.Router, synthetic_pdf: Path, tmp_path: Path
) -> None:
    # Crossref DOI lookups (one of the references uses a DOI).
    respx_mock.get(url__regex=r"^https://api\.crossref\.org/works/.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "message": {
                    "DOI": "10.18653/v1/n19-1423",
                    "title": ["BERT: Pre-training of Deep Bidirectional Transformers"],
                    "issued": {"date-parts": [[2019]]},
                    "author": [{"given": "Jacob", "family": "Devlin"}],
                }
            },
        )
    )
    # OpenAlex by DOI / by search — return a generic OA record.
    respx_mock.get(url__regex=r"^https://api\.openalex\.org/works.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [],
                "id": "https://openalex.org/W1",
                "title": "BERT",
                "publication_year": 2019,
                "doi": "https://doi.org/10.18653/v1/n19-1423",
                "ids": {"openalex": "https://openalex.org/W1"},
                "primary_location": {
                    "is_oa": True,
                    "pdf_url": None,
                    "license": "cc-by",
                },
                "locations": [],
            },
        )
    )
    # Semantic Scholar lookups
    respx_mock.get(url__regex=r"^https://api\.semanticscholar\.org/graph/v1/paper/.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "paperId": "abc",
                "title": "BERT",
                "year": 2019,
                "externalIds": {"DOI": "10.18653/v1/n19-1423"},
                "authors": [{"name": "Jacob Devlin"}],
                "openAccessPdf": None,
            },
        )
    )
    # arXiv lookup (id-based for the Vaswani entry)
    respx_mock.get(url__regex=r"^http://export\.arxiv\.org/api/query.*").mock(
        return_value=httpx.Response(
            200,
            text=(
                "<?xml version='1.0' encoding='UTF-8'?>"
                "<feed xmlns='http://www.w3.org/2005/Atom' "
                "xmlns:arxiv='http://arxiv.org/schemas/atom'>"
                "<entry>"
                "<id>http://arxiv.org/abs/1706.03762v5</id>"
                "<title>Attention Is All You Need</title>"
                "<published>2017-06-12T00:00:00Z</published>"
                "<author><name>Ashish Vaswani</name></author>"
                "</entry></feed>"
            ),
        )
    )
    # Unpaywall lookup — return an OA pdf url.
    respx_mock.get(url__regex=r"^https://api\.unpaywall\.org/v2/.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "is_oa": True,
                "doi": "10.18653/v1/n19-1423",
                "best_oa_location": {
                    "url_for_pdf": "https://repo.example.org/bert.pdf",
                    "license": "cc-by",
                    "host_type": "repository",
                    "version": "publishedVersion",
                },
                "oa_locations": [],
            },
        )
    )
    # The actual PDF byte streams.
    respx_mock.get("https://arxiv.org/pdf/1706.03762.pdf").mock(
        return_value=httpx.Response(
            200, content=_PDF_BYTES, headers={"Content-Type": "application/pdf"}
        )
    )
    respx_mock.get("https://repo.example.org/bert.pdf").mock(
        return_value=httpx.Response(
            200, content=_PDF_BYTES, headers={"Content-Type": "application/pdf"}
        )
    )

    out_dir = tmp_path / "run-001"
    summary = await pipeline.process_paper_bibliography(
        synthetic_pdf, out_dir, strategy="balanced"
    )

    # Manifest + report on disk
    assert (out_dir / "manifest.json").exists()
    assert (out_dir / "report.md").exists()
    assert (out_dir / "report.json").exists()

    # Summary shape
    assert summary["run_id"]
    assert summary["references_found"] >= 1
    assert summary["manifest_path"].endswith("manifest.json")
    assert summary["report_path"].endswith("report.md")

    # At least one PDF should have been written into out_dir/pdfs.
    pdfs_dir = out_dir / "pdfs"
    pdf_files = list(pdfs_dir.glob("*.pdf")) if pdfs_dir.exists() else []
    assert pdf_files, "expected at least one downloaded PDF"
    for p in pdf_files:
        assert p.read_bytes().startswith(b"%PDF-")

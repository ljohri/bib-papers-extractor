"""BibTeX parsing using bibtexparser as the primary backend.

Falls back to pybtex when bibtexparser yields zero entries (e.g. for pure
bibliography-style files that bibtexparser treats too strictly).
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from ..logging_config import get_logger
from ..models import Reference

log = get_logger(__name__)

_DOI_PREFIX_RE = re.compile(r"^https?://(?:dx\.)?doi\.org/", re.IGNORECASE)
_BRACE_RE = re.compile(r"[{}]")


def parse_bibtex_file(path: str | Path) -> list[Reference]:
    """Parse a `.bib` file into a list of `Reference` records.

    Raises FileNotFoundError if path doesn't exist.
    """
    p = Path(path).expanduser().resolve()
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"BibTeX file not found: {p}")

    raw = p.read_text(encoding="utf-8", errors="replace")
    refs = _parse_with_bibtexparser(raw)
    if not refs:
        log.info("bibtexparser yielded 0 entries; falling back to pybtex.")
        refs = _parse_with_pybtex(raw)
    return refs


def _parse_with_bibtexparser(raw: str) -> list[Reference]:
    try:
        import bibtexparser  # type: ignore[import-untyped]
        from bibtexparser.bparser import BibTexParser  # type: ignore[import-untyped]
        from bibtexparser.customization import author as _author  # type: ignore[import-untyped]
        from bibtexparser.customization import convert_to_unicode  # type: ignore[import-untyped]
    except Exception as e:
        log.warning("bibtexparser import failed: %s", e)
        return []

    def _customize(record: dict[str, str]) -> dict[str, str]:
        record = convert_to_unicode(record)
        record = _author(record)
        return record

    parser = BibTexParser(common_strings=True)
    parser.customization = _customize
    parser.ignore_nonstandard_types = False

    try:
        db = bibtexparser.loads(raw, parser=parser)
    except Exception as e:
        log.warning("bibtexparser failed to parse: %s", e)
        return []

    out: list[Reference] = []
    for i, entry in enumerate(db.entries, start=1):
        out.append(_entry_to_reference(entry, raw_block=_render_entry_block(entry), index=i))
    return out


def _render_entry_block(entry: dict[str, str]) -> str:
    key = entry.get("ID", "")
    typ = entry.get("ENTRYTYPE", "misc")
    fields = ", ".join(
        f"{k}={v}" for k, v in entry.items() if k.lower() not in {"id", "entrytype"}
    )
    return f"@{typ}{{{key}, {fields}}}"


def _entry_to_reference(entry: dict[str, object], *, raw_block: str, index: int) -> Reference:
    bibtex_key = str(entry.get("ID", "") or "") or None
    title = _clean_braces(_field(entry, "title"))
    journal = _clean_braces(_field(entry, "journal") or _field(entry, "booktitle"))
    venue = _clean_braces(_field(entry, "booktitle") or _field(entry, "series"))

    year_raw = _field(entry, "year")
    year: int | None = None
    if year_raw and re.fullmatch(r"\d{4}", year_raw.strip()):
        year = int(year_raw.strip())

    authors = _normalize_authors(entry.get("author"))

    doi = _field(entry, "doi")
    if doi:
        doi = _DOI_PREFIX_RE.sub("", doi).strip().rstrip(".,;").lower()

    arxiv = _field(entry, "eprint") or _field(entry, "archiveprefix") or _field(entry, "arxivid")
    if arxiv and "arxiv" in (_field(entry, "archiveprefix") or "").lower():
        arxiv = arxiv.strip()
    elif (
        arxiv
        and not re.match(r"^\d{4}\.\d{4,5}", arxiv)
        and not re.match(r"^[a-z\-]+(\.[A-Z]{2})?/\d{7}", arxiv)
    ):
        arxiv = None

    digest = hashlib.sha1((bibtex_key or raw_block).encode("utf-8", "ignore")).hexdigest()[:6]
    ref_id = f"bib-{index:03d}-{digest}"

    return Reference(
        id=ref_id,
        raw=raw_block,
        title=title or None,
        authors=authors,
        year=year,
        doi=doi or None,
        arxiv_id=arxiv or None,
        journal=journal or None,
        venue=venue or None,
        bibtex_key=bibtex_key,
    )


def _field(entry: dict[str, object], key: str) -> str | None:
    val = entry.get(key) or entry.get(key.lower()) or entry.get(key.upper())
    if val is None:
        return None
    if isinstance(val, list):
        return ", ".join(str(v) for v in val)
    return str(val).strip()


def _normalize_authors(value: object) -> list[str]:
    """bibtexparser's `author` customization returns a list of 'Last, First' strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [_clean_braces(str(v)) for v in value if str(v).strip()]
    text = _clean_braces(str(value))
    if not text:
        return []
    parts = re.split(r"\s+and\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _clean_braces(value: str | None) -> str:
    if not value:
        return ""
    return _BRACE_RE.sub("", value).strip()


def _parse_with_pybtex(raw: str) -> list[Reference]:
    try:
        from io import StringIO

        from pybtex.database.input import bibtex as pybtex_in
    except Exception as e:
        log.warning("pybtex import failed: %s", e)
        return []

    try:
        bib = pybtex_in.Parser().parse_stream(StringIO(raw))
    except Exception as e:
        log.warning("pybtex failed to parse: %s", e)
        return []

    out: list[Reference] = []
    for i, (key, entry) in enumerate(bib.entries.items(), start=1):
        fields = {k.lower(): str(v) for k, v in entry.fields.items()}
        title = _clean_braces(fields.get("title"))
        journal = _clean_braces(fields.get("journal") or fields.get("booktitle"))
        year_raw = fields.get("year")
        year = int(year_raw) if year_raw and year_raw.isdigit() and len(year_raw) == 4 else None

        authors: list[str] = []
        for person in entry.persons.get("author", []):
            authors.append(" ".join(person.last_names + person.first_names).strip())

        doi = fields.get("doi")
        if doi:
            doi = _DOI_PREFIX_RE.sub("", doi).strip().rstrip(".,;").lower()

        arxiv = fields.get("eprint") if "arxiv" in (fields.get("archiveprefix") or "").lower() else None

        digest = hashlib.sha1(key.encode("utf-8", "ignore")).hexdigest()[:6]
        out.append(
            Reference(
                id=f"bib-{i:03d}-{digest}",
                raw=f"@{entry.type}{{{key}, ...}}",
                title=title or None,
                authors=authors,
                year=year,
                doi=doi or None,
                arxiv_id=arxiv or None,
                journal=journal or None,
                bibtex_key=key,
            )
        )
    return out

"""Detect the bibliography/references section in extracted PDF text.

We scan from the end of the document backward for canonical section headers
(References, Bibliography, Works Cited, etc.) and return the substring from that
header to either an explicit terminator (Appendix, Acknowledgements that follows
References — rare) or end-of-document.
"""

from __future__ import annotations

import regex as re

from ..logging_config import get_logger

log = get_logger(__name__)

_HEADER_RE = re.compile(
    r"""
    (?:^|\n)
    [ \t]{0,8}                                                  # leading indent
    (?:\d+(?:\.\d+)*[\s.\):]+)?                                 # optional "7.", "7.1", "7) "
    (?P<header>References?|Bibliography|Works\s+Cited|Cited\s+(?:Literature|Works)|Literature\s+Cited|R[ée]f[ée]rences)
    [ \t]*[:\.]?
    [ \t]*\n
    """,
    re.IGNORECASE | re.VERBOSE,
)

_TERMINATOR_RE = re.compile(
    r"""
    (?:^|\n)
    [ \t]{0,8}
    (?:\d+(?:\.\d+)*[\s.\):]+)?
    (?:Appendix(?:\s+[A-Z])?|Supplementary\s+Material|Supplemental\s+Material|Author\s+Contributions|Author\s+Biograph|About\s+the\s+Authors?)
    [ \t]*\n
    """,
    re.IGNORECASE | re.VERBOSE,
)


def find_bibliography_section(full_text: str) -> str:
    """Return the references portion of `full_text`, or empty string if not found.

    Strategy:
      1. Find all candidate header positions; choose the *last* one (the bibliography
         is almost always near the end, even when "references" is mentioned in-text).
      2. Truncate at the first terminator after that position.
    """
    if not full_text:
        return ""

    last_match: re.Match[str] | None = None
    for m in _HEADER_RE.finditer(full_text):
        last_match = m

    if last_match is None:
        log.debug("No bibliography header found in document text.")
        return ""

    start = last_match.end()
    tail = full_text[start:]

    term = _TERMINATOR_RE.search(tail)
    body = tail[: term.start()] if term else tail

    log.debug(
        "Bibliography header '%s' at offset %d, body length %d chars",
        last_match.group("header"),
        last_match.start(),
        len(body),
    )
    return body.strip()

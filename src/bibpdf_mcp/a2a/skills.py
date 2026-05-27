"""A2A AgentCard skills and request parsing."""

from __future__ import annotations

import json
from typing import Any

from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill

from .. import __version__

SKILL_EXTRACT_PDF = "extract_references_from_pdf"
SKILL_PARSE_BIBTEX = "parse_bibtex_file"
SKILL_RESOLVE = "resolve_references"
SKILL_FIND_PDFS = "find_public_pdfs"
SKILL_DOWNLOAD = "download_public_pdfs"
SKILL_PROCESS = "process_paper_bibliography"

ALL_SKILL_IDS = frozenset(
    {
        SKILL_EXTRACT_PDF,
        SKILL_PARSE_BIBTEX,
        SKILL_RESOLVE,
        SKILL_FIND_PDFS,
        SKILL_DOWNLOAD,
        SKILL_PROCESS,
    }
)

_REQUEST_EXAMPLE = json.dumps(
    {
        "skill": SKILL_PROCESS,
        "arguments": {
            "pdf_path": "/data/input/paper.pdf",
            "output_dir": "/data/output/run-001",
            "strategy": "balanced",
        },
    },
    indent=2,
)


def build_skills() -> list[AgentSkill]:
    """Agent skills mirroring the six MCP tools."""
    common_modes = ["text/plain", "application/json"]
    return [
        AgentSkill(
            id=SKILL_EXTRACT_PDF,
            name="Extract references from PDF",
            description="Extract bibliography entries from a research paper PDF.",
            input_modes=common_modes,
            output_modes=common_modes,
            tags=["bibliography", "pdf", "extraction"],
            examples=[
                json.dumps(
                    {"skill": SKILL_EXTRACT_PDF, "arguments": {"pdf_path": "/path/paper.pdf"}}
                ),
            ],
        ),
        AgentSkill(
            id=SKILL_PARSE_BIBTEX,
            name="Parse BibTeX file",
            description="Parse a .bib file into structured Reference objects.",
            input_modes=common_modes,
            output_modes=common_modes,
            tags=["bibliography", "bibtex"],
            examples=[
                json.dumps(
                    {
                        "skill": SKILL_PARSE_BIBTEX,
                        "arguments": {"bibtex_path": "/path/refs.bib"},
                    }
                ),
            ],
        ),
        AgentSkill(
            id=SKILL_RESOLVE,
            name="Resolve references",
            description="Resolve metadata via Crossref, OpenAlex, Semantic Scholar, and arXiv.",
            input_modes=common_modes,
            output_modes=common_modes,
            tags=["bibliography", "metadata", "resolution"],
            examples=[
                json.dumps(
                    {
                        "skill": SKILL_RESOLVE,
                        "arguments": {
                            "references": [{"id": "ref-1", "raw": "...", "title": "..."}],
                            "strategy": "balanced",
                        },
                    }
                ),
            ],
        ),
        AgentSkill(
            id=SKILL_FIND_PDFS,
            name="Find public OA PDFs",
            description="Discover legal open-access PDF URLs for resolved works.",
            input_modes=common_modes,
            output_modes=common_modes,
            tags=["bibliography", "open-access", "pdf"],
            examples=[
                json.dumps(
                    {
                        "skill": SKILL_FIND_PDFS,
                        "arguments": {"resolved_references": []},
                    }
                ),
            ],
        ),
        AgentSkill(
            id=SKILL_DOWNLOAD,
            name="Download public PDFs",
            description="Download approved OA PDF candidates with deterministic filenames.",
            input_modes=common_modes,
            output_modes=common_modes,
            tags=["bibliography", "download", "pdf"],
            examples=[
                json.dumps(
                    {
                        "skill": SKILL_DOWNLOAD,
                        "arguments": {"pdf_candidates": [], "output_dir": "/data/output"},
                    }
                ),
            ],
        ),
        AgentSkill(
            id=SKILL_PROCESS,
            name="Process paper bibliography (end-to-end)",
            description=(
                "Full pipeline: extract references, resolve metadata, find and download "
                "legal OA PDFs, write manifest and reports."
            ),
            input_modes=common_modes,
            output_modes=common_modes,
            tags=["bibliography", "pipeline", "pdf"],
            examples=[_REQUEST_EXAMPLE],
        ),
    ]


def build_agent_card(*, public_url: str) -> AgentCard:
    """Build the public Agent Card served at ``/.well-known/agent.json``."""
    return AgentCard(
        name="Bibliography PDF Agent",
        description=(
            "Extracts bibliography entries from research papers, resolves metadata "
            "against scholarly APIs, and downloads legally available open-access PDFs."
        ),
        version=__version__,
        default_input_modes=["text/plain", "application/json"],
        default_output_modes=["text/plain", "application/json"],
        capabilities=AgentCapabilities(streaming=False, extended_agent_card=False),
        supported_interfaces=[
            AgentInterface(protocol_binding="JSONRPC", url=public_url),
            AgentInterface(protocol_binding="HTTP+JSON", url=public_url),
        ],
        skills=build_skills(),
    )


class A2ARequestError(ValueError):
    """Invalid A2A skill request payload."""


def parse_user_message(text: str) -> tuple[str, dict[str, Any]]:
    """Parse a user message into ``(skill_id, arguments)``.

    Accepts JSON::

        {"skill": "process_paper_bibliography", "arguments": {...}}

    Or a bare skill id string (arguments must be supplied via a follow-up message).
    """
    stripped = text.strip()
    if not stripped:
        raise A2ARequestError("Empty message. Send JSON with 'skill' and 'arguments'.")

    if stripped.startswith("{"):
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as e:
            raise A2ARequestError(f"Invalid JSON: {e}") from e
        if not isinstance(payload, dict):
            raise A2ARequestError("Request JSON must be an object.")
        skill = payload.get("skill") or payload.get("skill_id")
        if not skill or not isinstance(skill, str):
            raise A2ARequestError("Missing required field 'skill'.")
        if skill not in ALL_SKILL_IDS:
            raise A2ARequestError(f"Unknown skill '{skill}'. Valid: {sorted(ALL_SKILL_IDS)}")
        args = payload.get("arguments") or payload.get("params") or {}
        if not isinstance(args, dict):
            raise A2ARequestError("'arguments' must be a JSON object.")
        return skill, args

    if stripped in ALL_SKILL_IDS:
        return stripped, {}

    raise A2ARequestError(
        "Unrecognized request. Send JSON: "
        '{"skill": "<skill_id>", "arguments": {...}}. '
        f"Skills: {', '.join(sorted(ALL_SKILL_IDS))}"
    )

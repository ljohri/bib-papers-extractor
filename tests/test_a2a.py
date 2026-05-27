"""Tests for A2A request parsing and agent card."""

from __future__ import annotations

import json

import pytest

from bibpdf_mcp.a2a.skills import (
    SKILL_PROCESS,
    A2ARequestError,
    build_agent_card,
    parse_user_message,
)


def test_build_agent_card_has_six_skills() -> None:
    card = build_agent_card(public_url="http://localhost:8080")
    assert card.name == "Bibliography PDF Agent"
    assert len(card.skills) == 6
    skill_ids = {s.id for s in card.skills}
    assert SKILL_PROCESS in skill_ids


def test_parse_user_message_json() -> None:
    payload = {
        "skill": "extract_references_from_pdf",
        "arguments": {"pdf_path": "/tmp/paper.pdf"},
    }
    skill, args = parse_user_message(json.dumps(payload))
    assert skill == "extract_references_from_pdf"
    assert args["pdf_path"] == "/tmp/paper.pdf"


def test_parse_user_message_unknown_skill() -> None:
    with pytest.raises(A2ARequestError, match="Unknown skill"):
        parse_user_message(json.dumps({"skill": "not_a_skill", "arguments": {}}))


def test_parse_user_message_empty() -> None:
    with pytest.raises(A2ARequestError, match="Empty"):
        parse_user_message("   ")

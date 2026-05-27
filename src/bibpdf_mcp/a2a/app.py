"""Starlette application factory for the A2A bibliography agent."""

from __future__ import annotations

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    create_agent_card_routes,
    create_jsonrpc_routes,
    create_rest_routes,
)
from a2a.server.tasks import InMemoryTaskStore
from starlette.applications import Starlette

from ..config import get_settings
from ..logging_config import configure_logging, get_logger
from .executor import BibliographyAgentExecutor
from .skills import build_agent_card

log = get_logger(__name__)


def create_a2a_app() -> Starlette:
    """Build the A2A Starlette app (agent card + JSON-RPC + REST)."""
    settings = get_settings()
    settings.ensure_dirs()
    configure_logging(settings.log_level)

    agent_card = build_agent_card(public_url=settings.a2a_public_url)
    handler = DefaultRequestHandler(
        agent_executor=BibliographyAgentExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )

    routes = []
    routes.extend(create_agent_card_routes(agent_card))
    routes.extend(create_jsonrpc_routes(handler, "/"))
    routes.extend(create_rest_routes(handler, "/"))

    log.info(
        "A2A agent card at %s (JSON-RPC + REST on %s:%s)",
        settings.a2a_public_url,
        settings.a2a_host,
        settings.a2a_port,
    )
    return Starlette(routes=routes)

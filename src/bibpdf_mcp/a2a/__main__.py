"""Run the bibliography agent as an A2A HTTP server.

Usage::

    uv run python -m bibpdf_mcp.a2a
    uv run bibpdf-a2a
"""

from __future__ import annotations

import uvicorn

from ..config import get_settings
from ..logging_config import configure_logging, get_logger
from .app import create_a2a_app

log = get_logger(__name__)


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = create_a2a_app()
    log.info(
        "Starting bibliography-pdf A2A server on http://%s:%s",
        settings.a2a_host,
        settings.a2a_port,
    )
    uvicorn.run(app, host=settings.a2a_host, port=settings.a2a_port, log_level="info")


if __name__ == "__main__":
    main()

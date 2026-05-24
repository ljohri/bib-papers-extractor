"""Centralised logging setup using rich for human-readable CLI output."""

from __future__ import annotations

import logging

from rich.console import Console
from rich.logging import RichHandler

from .config import get_settings

_CONFIGURED = False


def configure_logging(level: str | None = None) -> None:
    """Idempotently configure root logging.

    For MCP server (stdio) usage we must keep all logs on stderr so they don't
    corrupt the JSON-RPC stdout stream.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    resolved = (level or get_settings().log_level).upper()
    handler = RichHandler(
        console=Console(stderr=True),
        rich_tracebacks=True,
        markup=False,
        show_time=True,
        show_path=False,
        log_time_format="%H:%M:%S",
    )

    logging.basicConfig(
        level=resolved,
        format="%(message)s",
        datefmt="%H:%M:%S",
        handlers=[handler],
        force=True,
    )

    for noisy in ("httpx", "httpcore", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a module logger, configuring the root logger on first call."""
    configure_logging()
    return logging.getLogger(name)

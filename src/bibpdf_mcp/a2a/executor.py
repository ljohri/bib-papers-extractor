"""A2A AgentExecutor implementation for the bibliography pipeline."""

from __future__ import annotations

import json
from typing import Any

from a2a.helpers import (
    get_message_text,
    new_task_from_user_message,
    new_text_message,
    new_text_part,
)
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types.a2a_pb2 import TaskState

from .. import tool_handlers
from ..logging_config import get_logger
from .skills import (
    SKILL_DOWNLOAD,
    SKILL_EXTRACT_PDF,
    SKILL_FIND_PDFS,
    SKILL_PARSE_BIBTEX,
    SKILL_PROCESS,
    SKILL_RESOLVE,
    A2ARequestError,
    parse_user_message,
)

log = get_logger(__name__)


async def dispatch_skill(skill: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Run the skill matching ``skill`` with ``arguments``."""
    if skill == SKILL_EXTRACT_PDF:
        pdf_path = arguments.get("pdf_path")
        if not pdf_path:
            raise A2ARequestError(f"'{SKILL_EXTRACT_PDF}' requires arguments.pdf_path")
        return tool_handlers.extract_references_from_pdf(str(pdf_path))

    if skill == SKILL_PARSE_BIBTEX:
        bibtex_path = arguments.get("bibtex_path")
        if not bibtex_path:
            raise A2ARequestError(f"'{SKILL_PARSE_BIBTEX}' requires arguments.bibtex_path")
        return tool_handlers.parse_bibtex_file(str(bibtex_path))

    if skill == SKILL_RESOLVE:
        references = arguments.get("references")
        if not isinstance(references, list):
            raise A2ARequestError(f"'{SKILL_RESOLVE}' requires arguments.references (list)")
        strategy = str(arguments.get("strategy", "balanced"))
        return await tool_handlers.resolve_references(references, strategy=strategy)

    if skill == SKILL_FIND_PDFS:
        resolved = arguments.get("resolved_references")
        if not isinstance(resolved, list):
            raise A2ARequestError(
                f"'{SKILL_FIND_PDFS}' requires arguments.resolved_references (list)"
            )
        return await tool_handlers.find_public_pdfs(resolved)

    if skill == SKILL_DOWNLOAD:
        candidates = arguments.get("pdf_candidates")
        if not isinstance(candidates, list):
            raise A2ARequestError(f"'{SKILL_DOWNLOAD}' requires arguments.pdf_candidates (list)")
        output_dir = arguments.get("output_dir")
        return await tool_handlers.download_public_pdfs(
            candidates,
            str(output_dir) if output_dir is not None else None,
        )

    if skill == SKILL_PROCESS:
        pdf_path = arguments.get("pdf_path")
        if not pdf_path:
            raise A2ARequestError(f"'{SKILL_PROCESS}' requires arguments.pdf_path")
        output_dir = arguments.get("output_dir")
        strategy = str(arguments.get("strategy", "balanced"))
        return await tool_handlers.process_paper_bibliography(
            str(pdf_path),
            str(output_dir) if output_dir is not None else None,
            strategy=strategy,
        )

    raise A2ARequestError(f"Unhandled skill: {skill}")


class BibliographyAgentExecutor(AgentExecutor):
    """Executes bibliography pipeline skills from A2A client messages."""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        if context.current_task:
            task = context.current_task
        else:
            task = new_task_from_user_message(context.message)
            await event_queue.enqueue_event(task)

        task_updater = TaskUpdater(
            event_queue=event_queue,
            task_id=task.id,
            context_id=task.context_id,
        )
        await task_updater.update_status(
            state=TaskState.TASK_STATE_WORKING,
            message=new_text_message("Running bibliography skill..."),
        )

        user_text = get_message_text(context.message) if context.message else ""
        try:
            skill, arguments = parse_user_message(user_text)
            log.info("A2A skill=%s args_keys=%s", skill, list(arguments.keys()))
            result = await dispatch_skill(skill, arguments)
            body = json.dumps(result, indent=2, ensure_ascii=False)
        except (A2ARequestError, FileNotFoundError, ValueError) as e:
            log.warning("A2A skill failed: %s", e)
            body = json.dumps({"error": str(e), "type": type(e).__name__}, indent=2)
            await task_updater.add_artifact(
                parts=[new_text_part(text=body, media_type="application/json")]
            )
            await task_updater.update_status(
                state=TaskState.TASK_STATE_FAILED,
                message=new_text_message(str(e)),
            )
            return
        except Exception as e:
            log.exception("A2A unexpected error")
            body = json.dumps({"error": str(e), "type": type(e).__name__}, indent=2)
            await task_updater.add_artifact(
                parts=[new_text_part(text=body, media_type="application/json")]
            )
            await task_updater.update_status(
                state=TaskState.TASK_STATE_FAILED,
                message=new_text_message(f"Internal error: {e}"),
            )
            return

        await task_updater.add_artifact(
            parts=[new_text_part(text=body, media_type="application/json")]
        )
        await task_updater.update_status(
            state=TaskState.TASK_STATE_COMPLETED,
            message=new_text_message(f"Completed skill: {skill}"),
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("Task cancellation is not supported.")

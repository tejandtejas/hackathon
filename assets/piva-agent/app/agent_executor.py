import logging
import os

from a2a.server.agent_execution import AgentExecutor as A2AAgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import InternalError, Part, TaskState, TextPart, UnsupportedOperationError
from a2a.utils import new_agent_text_message, new_task
from a2a.utils.errors import ServerError

from agent import SampleAgent

# Joule-only import: guarded so CF startup does not fail on missing sap_cloud_sdk
if os.environ.get("JOULE_RUNTIME"):
    from mcp_tools import get_mcp_tools, set_user_token_for_tools, reset_user_token_for_tools  # noqa: E402

logger = logging.getLogger(__name__)


def _extract_bearer(auth_header: str) -> str:
    """Extract the raw token value from a Bearer authorization header."""
    pfx = "Bearer "
    if auth_header and auth_header.startswith(pfx):
        return auth_header[len(pfx):]
    return ""


class AgentExecutor(A2AAgentExecutor):
    def __init__(self):
        self.agent = SampleAgent()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Execute the agent and stream results back via A2A protocol."""
        query = context.get_user_input()
        task = context.current_task
        if not task:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)

        is_local_testing = os.environ.get("IBD_TESTING") == "1"

        if os.environ.get("JOULE_RUNTIME"):
            # Joule runtime: load MCP tools per-request using the caller's bearer token
            _tok = ""
            if hasattr(context, "call_context") and hasattr(context.call_context, "state"):
                headers = context.call_context.state.get("headers", {})
                auth_hdr = headers.get("authorization") or headers.get("Authorization") or ""
                _tok = _extract_bearer(auth_hdr)
                if _tok:
                    logger.info("Extracted bearer token for MCP tool calls")
            tools = []
            if not _tok and not is_local_testing:
                logger.warning("No bearer token available -- running agent without tools")
            else:
                try:
                    # Pass as positional arg to avoid keyword-name filtering
                    _kw = {"user_token": _tok or None}
                    tools = await get_mcp_tools(**_kw)
                    if tools:
                        logger.info("Loaded %d MCP tool(s): %s", len(tools), [t.name for t in tools])
                except Exception as e:
                    logger.error("Failed to load MCP tools: %s", e)
            _tok_ctx = set_user_token_for_tools(_tok or None) if _tok and tools else None
        else:
            # CF runtime: tools built lazily inside SampleAgent._get_tools()
            tools = None
            _tok_ctx = None

        updater = TaskUpdater(event_queue, task.id, task.context_id)

        try:
            async for item in self.agent.stream(query, task.context_id, tools=tools):
                is_task_complete = item["is_task_complete"]
                require_user_input = item["require_user_input"]
                content = item["content"]
                if require_user_input:
                    await updater.update_status(
                        TaskState.input_required,
                        new_agent_text_message(content, task.context_id, task.id),
                        final=True,
                    )
                    break
                elif is_task_complete:
                    await updater.add_artifact([Part(root=TextPart(text=content))], name="agent_result")
                    await updater.complete()
                    break
                else:
                    await updater.update_status(
                        TaskState.working,
                        new_agent_text_message(content, task.context_id, task.id),
                    )
        except Exception as e:
            logger.exception("Agent execution error")
            raise ServerError(error=InternalError()) from e
        finally:
            if _tok_ctx is not None and os.environ.get("JOULE_RUNTIME"):
                reset_user_token_for_tools(_tok_ctx)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise ServerError(error=UnsupportedOperationError())

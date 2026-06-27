import logging
import os
import time
from dataclasses import dataclass
from typing import AsyncGenerator, Literal, Sequence

from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import InMemorySaver
from opentelemetry import trace

# Dual-mode decorator import: real decorators on Joule, no-ops on CF
try:
    from sap_cloud_sdk.agent_decorators import agent_config, agent_model, prompt_section
except ImportError:
    def _identity_decorator(*_dargs, **_dkwargs):
        def _wrap(fn): return fn
        return _wrap
    agent_model = _identity_decorator
    agent_config = _identity_decorator
    prompt_section = _identity_decorator

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("piva-agent")

THREAD_TTL_SECONDS = 3600
DEFAULT_GREEN_THRESHOLD = 2.0
DEFAULT_AMBER_THRESHOLD = 5.0


@agent_model(
    key="config.model",
    label="LLM Model",
    description="The language model powering PIVA",
)
def get_model_name() -> str:
    return os.environ.get("AGENT_LLM_MODEL", "gpt-4o")


@agent_config(
    key="config.temperature",
    label="LLM Temperature",
    description="Controls randomness of responses (0.0 = deterministic)",
)
def get_temperature() -> float:
    return 0.0


@prompt_section(
    key="prompts.system",
    label="System Prompt",
    description="The full system prompt defining PIVA role and behaviour",
    validation={"format": "markdown", "max_length": 5000},
)
def get_system_prompt() -> str:
    return (
        "You are PIVA, the Physical Inventory Verification Agent for SAP EWM warehouses. "
        "You help warehouse supervisors and managers orchestrate the end-to-end physical inventory process via natural language.\n\n"
        "CAPABILITIES:\n"
        "- Identify products due for physical counting based on Cycle Counting Indicator (CCI) and last count date\n"
        "- Flag products with missing cycle counting indicators in EWM product master\n"
        "- Create EWM physical inventory documents (WRITE -- requires explicit user confirmation)\n"
        "- Compare counted vs. booked stock with Green/Amber/Red threshold classification\n"
        "- Post approved stock differences to EWM (WRITE -- requires explicit user confirmation)\n"
        "- Support single and multi-warehouse queries\n\n"
        "CRITICAL RULES:\n"
        "1. NEVER call create or post tools without explicit user confirmation. "
        "Always present a summary and ask the user to confirm before executing any write operation.\n"
        "2. Always set $top to a maximum of 100 on every tool call that accepts it. Inform user if results are limited.\n"
        "3. CCI due-date logic: a product is overdue when today >= LastPhysicalInventoryDate + PhysicalInventoryCycle (days).\n"
        "4. Difference classification defaults: Green <= 2%, Amber 2-5%, Red > 5%. Supervisor can override for the current session.\n"
        "5. Red-classified items are EXCLUDED from posting by default. Supervisor must explicitly request their inclusion.\n"
        "6. Never modify EWM product master data. Only report missing CCIs.\n"
        "7. Never retry write operations automatically on failure. Report the error and stop.\n"
        "8. Session threshold overrides do not persist across conversations.\n"
        "9. Always segment due-for-counting results by CCI indicator (A, B, C, etc.).\n"
        "10. Always clearly distinguish missing-CCI products from overdue products in your responses.\n\n"
        "IMPORTANT: You MUST use tools to retrieve live EWM data. Never fabricate, guess, or invent inventory data. "
        "Relay tool errors verbatim without adding suggestions."
    )


@dataclass
class AgentResponse:
    status: Literal["input_required", "completed", "error"]
    message: str


async def _run_agent(
    llm: BaseChatModel,
    checkpointer: InMemorySaver,
    summarization_middleware,
    query: str,
    context_id: str,
    tools: Sequence[BaseTool],
) -> str:
    """Core agent execution -- instrumented with milestones. Never yields; safe for OTel spans."""
    from langchain.agents import create_agent
    from langchain.agents.middleware import SummarizationMiddleware

    with tracer.start_as_current_span("piva.agent.run") as span:
        span.set_attribute("context_id", context_id)
        span.set_attribute("tool_count", len(list(tools)))

        system_prompt = get_system_prompt()
        if not tools:
            system_prompt += (
                "\n\nIMPORTANT: No tools are currently available. "
                "Do not attempt to call any tools. Explain that EWM tools are temporarily unavailable."
            )

        tool_names = [t.name for t in tools] if tools else []
        logger.info("Running PIVA with %d tool(s): %s", len(tool_names), tool_names)

        graph = create_agent(
            llm,
            tools=list(tools) if tools else [],
            system_prompt=system_prompt,
            checkpointer=checkpointer,
            middleware=[summarization_middleware],
        )
        config = {"configurable": {"thread_id": context_id}}

        try:
            result = await graph.ainvoke(
                {"messages": [HumanMessage(content=query)]}, config
            )
            response = result["messages"][-1].content
            _emit_milestone(query, response)
            return response
        except Exception as exc:
            logger.exception("PIVA _run_agent failed")
            span.record_exception(exc)
            raise


def _emit_milestone(query: str, response: str) -> None:
    """Emit structured milestone logs based on query/response content."""
    q = query.lower()
    r = response.lower()
    if any(kw in q for kw in ("due", "overdue", "counting", "cycle count", "cci")):
        if "error" in r or "failed" in r or "unavailable" in r:
            logger.info("[M1.missed]: product due identification failed | reason=agent_error")
        else:
            logger.info("[M1.achieved]: products due for counting identified | warehouse=queried | due_count=returned | missing_cci_count=returned")
    if any(kw in q for kw in ("create", "creating", "make document", "new document")):
        if "error" in r or "failed" in r:
            logger.info("[M2.missed]: physical inventory document creation failed | reason=tool_error")
        elif "confirm" in r.lower() or "please confirm" in r.lower():
            logger.info("[M2.missed]: physical inventory document creation pending confirmation")
        else:
            logger.info("[M2.achieved]: physical inventory documents created | warehouse=queried | document_count=returned | documents=returned")
    if any(kw in q for kw in ("queue", "queued", "warehouse order", "counting queue")):
        if "error" in r or "failed" in r:
            logger.info("[M3.missed]: documents not confirmed in counting queue | reason=tool_error")
        else:
            logger.info("[M3.achieved]: inventory documents queued for counting | document_count=returned")
    if any(kw in q for kw in ("difference", "counted", "booked", "stock comparison", "discrepancy")):
        if "error" in r or "failed" in r:
            logger.info("[M4.missed]: counted vs booked comparison failed | warehouse=queried | reason=tool_error")
        else:
            logger.info("[M4.achieved]: counted vs booked comparison delivered | warehouse=queried | documents_reviewed=returned | green=n | amber=n | red=n")
    if any(kw in q for kw in ("post", "posting", "approve", "submit difference")):
        if "error" in r or "failed" in r:
            logger.info("[M5.missed]: difference posting failed or not confirmed | reason=tool_error")
        elif "confirm" in r.lower() or "please confirm" in r.lower():
            logger.info("[M5.missed]: difference posting pending supervisor confirmation")
        else:
            logger.info("[M5.achieved]: stock differences posted | posted_count=returned | excluded_count=returned | failed_count=returned")


class SampleAgent:
    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    def __init__(self, s4_client=None):
        self._s4_client = s4_client
        self._checkpointer = InMemorySaver()
        self._last_active: dict[str, float] = {}
        self._tools = None
        # LLM is built lazily to avoid blocking startup with network calls
        self._llm: BaseChatModel | None = None
        self._summarization_middleware = None

    @property
    def s4_client(self):
        return self._s4_client

    async def _get_llm(self) -> BaseChatModel:
        """Build LLM lazily on first use. On CF uses AI Core destination; on Joule uses litellm."""
        if self._llm is not None:
            return self._llm

        if os.environ.get("JOULE_RUNTIME"):
            # Joule runtime: litellm is available
            from langchain_litellm import ChatLiteLLM
            self._llm = ChatLiteLLM(model=get_model_name(), temperature=get_temperature())
        else:
            # CF runtime: use AI Core destination via gen_ai_hub
            from aicore import init_llm_from_destination
            self._llm = await init_llm_from_destination(get_model_name(), temperature=get_temperature())

        from langchain.agents.middleware import SummarizationMiddleware
        self._summarization_middleware = SummarizationMiddleware(
            model=self._llm,
            trigger=("tokens", 100_000),
            keep=("messages", 4),
        )
        return self._llm

    def _touch(self, thread_id: str) -> None:
        now = time.monotonic()
        expired = [
            tid for tid, ts in list(self._last_active.items())
            if now - ts > THREAD_TTL_SECONDS
        ]
        for tid in expired:
            self._checkpointer.delete_thread(tid)
            del self._last_active[tid]
            logger.info("Evicted inactive thread: %s", tid)
        self._last_active[thread_id] = now

    async def _get_tools(self) -> list:
        """Lazily load tools for CF (direct-API) or Joule (MCP-instruction)."""
        if self._tools is None:
            if os.environ.get("JOULE_RUNTIME"):
                from mcp_tools import get_mcp_tools
                self._tools = await get_mcp_tools(user_token=None)
            else:
                from tools import build_domain_tools
                from s4hana_client import Client
                client = self._s4_client or Client()
                self._tools = build_domain_tools(s4_client=client)
        return self._tools

    async def stream(
        self,
        query: str,
        context_id: str,
        tools: Sequence[BaseTool] | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Stream agent responses for A2A protocol."""
        self._touch(context_id)
        yield {
            "is_task_complete": False,
            "require_user_input": False,
            "content": "Processing your inventory request...",
        }
        try:
            llm = await self._get_llm()
            if self._summarization_middleware is None:
                from langchain.agents.middleware import SummarizationMiddleware
                self._summarization_middleware = SummarizationMiddleware(
                    model=llm, trigger=("tokens", 100_000), keep=("messages", 4)
                )
            resolved_tools = tools if tools is not None else await self._get_tools()
            response = await _run_agent(
                llm, self._checkpointer, self._summarization_middleware,
                query, context_id, resolved_tools,
            )
            self._touch(context_id)
            yield {
                "is_task_complete": True,
                "require_user_input": False,
                "content": response,
            }
        except Exception as e:
            logger.exception("PIVA stream() failed")
            yield {
                "is_task_complete": True,
                "require_user_input": False,
                "content": f"I encountered an error processing your inventory request: {str(e)}. Please try again.",
            }

    async def invoke(
        self,
        query: str,
        context_id: str,
        tools: Sequence[BaseTool] | None = None,
    ) -> AgentResponse:
        """Invoke agent and return final response (non-streaming)."""
        last: dict = {}
        async for chunk in self.stream(query, context_id, tools=tools):
            last = chunk
        if last.get("is_task_complete"):
            return AgentResponse(status="completed", message=last["content"])
        if last.get("require_user_input"):
            return AgentResponse(status="input_required", message=last["content"])
        return AgentResponse(status="error", message=last.get("content", "Unknown error"))

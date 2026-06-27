# CRITICAL: Initialize telemetry BEFORE importing AI frameworks
# Dual-mode: Joule telemetry only runs when JOULE_RUNTIME=1 is set
import os
if os.environ.get("JOULE_RUNTIME"):
    from sap_cloud_sdk.aicore import set_aicore_config
    from sap_cloud_sdk.core.telemetry import auto_instrument
    set_aicore_config()
    auto_instrument()

import logging

import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from agent_executor import AgentExecutor
from opentelemetry.instrumentation.starlette import StarletteInstrumentor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "5000"))


def build_app():
    skill = AgentSkill(
        id="piva-agent",
        name="piva-agent",
        description="Physical Inventory Verification Agent for EWM -- orchestrates end-to-end physical inventory counting, document creation, discrepancy analysis, and difference posting via natural language",
        tags=["physical-inventory", "ewm", "warehouse", "cycle-counting", "piva"],
        examples=[
            "Show me products due for counting in warehouse 0001 with CCI A",
            "Create physical inventory documents for overdue products in warehouse 0001",
            "Show me counted vs booked stock differences for warehouse 0001",
            "Which products in warehouse 0001 have missing cycle counting indicators?",
        ],
    )
    agent_card = AgentCard(
        name="piva-agent",
        description="Physical Inventory Verification Agent for EWM -- orchestrates end-to-end physical inventory counting, document creation, discrepancy analysis, and difference posting via natural language",
        url=os.environ.get("AGENT_PUBLIC_URL", f"http://{HOST}:{PORT}/"),
        version="1.0.0",
        default_input_modes=["text", "text/plain"],
        default_output_modes=["text", "text/plain"],
        capabilities=AgentCapabilities(streaming=True, push_notifications=False),
        skills=[skill],
    )
    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=DefaultRequestHandler(
            agent_executor=AgentExecutor(),
            task_store=InMemoryTaskStore(),
        ),
    )
    app = server.build()
    StarletteInstrumentor().instrument_app(app)
    return app


# WSGI/ASGI application entry point for gunicorn
application = build_app()


if __name__ == "__main__":
    logger.info(f"Starting A2A server at http://{HOST}:{PORT}")
    uvicorn.run(application, host=HOST, port=PORT)

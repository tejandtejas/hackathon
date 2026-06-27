"""Integration test: end-to-end agent invoke with mocked LLM and MCP tools."""
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.tools import tool


@tool
def mock_list_ProductEWMWarehouse(filter: str = "", top: int = 100) -> dict:
    """Mock EWM product master tool."""
    return {
        "results": [
            {
                "Product": "MAT-10001",
                "WarehouseNumber": "0001",
                "CycleCountingIndicator": "A",
                "PhysicalInventoryCycle": "30",
                "LastPhysicalInventoryDate": "2024-01-01",
            }
        ]
    }


@pytest.fixture
def mock_tools():
    return [mock_list_ProductEWMWarehouse]


@pytest.fixture
def mock_llm_response():
    mock_msg = MagicMock()
    mock_msg.content = (
        "Here are the products due for counting in warehouse 0001:\n\n"
        "| Product | CCI | Last Count Date | Next Due Date | Status |\n"
        "|---------|-----|-----------------|---------------|--------|\n"
        "| MAT-10001 | A | 2024-01-01 | 2024-01-31 | Due since 2024-01-31 |\n\n"
        "Total overdue: 1 product."
    )
    mock_result = {"messages": [mock_msg]}
    return mock_result


@pytest.mark.asyncio
async def test_agent_invoke_due_for_counting(mock_tools, mock_llm_response):
    """Test that agent invoke returns a response for a due-for-counting query."""
    with patch("mcp_tools.get_mcp_tools", new_callable=AsyncMock, return_value=mock_tools), \
         patch("langchain.agents.create_agent") as mock_create_agent:

        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(return_value=mock_llm_response)
        mock_create_agent.return_value = mock_graph

        from agent import SampleAgent
        agent = SampleAgent()
        response = await agent.invoke(
            query="Show me products due for counting in warehouse 0001",
            context_id="test-context-001",
            tools=mock_tools,
        )

        assert response.status == "completed"
        assert response.message is not None
        assert len(response.message) > 0


@pytest.mark.asyncio
async def test_agent_stream_yields_chunks(mock_tools, mock_llm_response):
    """Test that agent stream yields processing status then final response."""
    with patch("mcp_tools.get_mcp_tools", new_callable=AsyncMock, return_value=mock_tools), \
         patch("langchain.agents.create_agent") as mock_create_agent:

        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(return_value=mock_llm_response)
        mock_create_agent.return_value = mock_graph

        from agent import SampleAgent
        agent = SampleAgent()
        chunks = []
        async for chunk in agent.stream(
            query="Which products in warehouse 0001 have missing cycle counting indicators?",
            context_id="test-context-002",
            tools=mock_tools,
        ):
            chunks.append(chunk)

        # First chunk: processing status
        assert chunks[0]["is_task_complete"] is False
        # Last chunk: completed
        assert chunks[-1]["is_task_complete"] is True
        assert chunks[-1]["content"] is not None


@pytest.mark.asyncio
async def test_agent_no_tools_responds_gracefully():
    """Test agent handles no-tools scenario gracefully without crashing."""
    with patch("mcp_tools.get_mcp_tools", new_callable=AsyncMock, return_value=[]), \
         patch("langchain.agents.create_agent") as mock_create_agent:

        mock_msg = MagicMock()
        mock_msg.content = "EWM tools are temporarily unavailable. Please try again later."
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(return_value={"messages": [mock_msg]})
        mock_create_agent.return_value = mock_graph

        from agent import SampleAgent
        agent = SampleAgent()
        response = await agent.invoke(
            query="Show me overdue products",
            context_id="test-context-003",
            tools=[],
        )

        assert response.status == "completed"
        assert response.message is not None


@pytest.mark.asyncio
async def test_agent_error_handling(mock_tools):
    """Test agent returns a response (not a crash) when LLM raises an exception."""
    with patch("mcp_tools.get_mcp_tools", new_callable=AsyncMock, return_value=mock_tools), \
         patch("agent._run_agent", new_callable=AsyncMock, side_effect=RuntimeError("LLM unavailable")):

        from agent import SampleAgent
        agent = SampleAgent()
        response = await agent.invoke(
            query="Show overdue products",
            context_id="test-context-004",
            tools=mock_tools,
        )

        # Should return completed with error message (stream catches the exception)
        assert response.status in ("completed", "error")
        assert response.message is not None

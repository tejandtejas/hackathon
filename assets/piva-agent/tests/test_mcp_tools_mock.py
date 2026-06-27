"""Tests for _build_mock_tools in mcp_tools.py using the mcp-mock.json fixture."""
import sys
import os
import json
import asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


class TestBuildMockTools:
    def test_mock_tools_loaded_from_file(self):
        """_build_mock_tools loads tools from mcp-mock.json at asset root."""
        from mcp_tools import _build_mock_tools
        tools = _build_mock_tools()
        # Should load 5 tools from the piva-agent mcp-mock.json
        assert len(tools) >= 1
        tool_names = [t.name for t in tools]
        assert any("ProductEWMWarehouse" in name or "list_Product" in name for name in tool_names)

    def test_mock_tools_have_descriptions(self):
        from mcp_tools import _build_mock_tools
        tools = _build_mock_tools()
        for tool in tools:
            assert tool.description is not None
            assert len(tool.description) > 0

    def test_mock_tools_are_callable(self):
        from mcp_tools import _build_mock_tools
        tools = _build_mock_tools()
        assert len(tools) > 0
        # Each tool should have a coroutine
        for tool in tools:
            assert tool.coroutine is not None or tool.func is not None

    @pytest.mark.asyncio
    async def test_mock_tools_return_json_on_invoke(self):
        """Mock tools should return JSON string responses."""
        from mcp_tools import _build_mock_tools
        tools = _build_mock_tools()
        assert len(tools) > 0
        # Test first tool returns a JSON string via ainvoke
        first_tool = tools[0]
        result = await first_tool.ainvoke({})
        parsed = json.loads(result)
        assert isinstance(parsed, (dict, list))

    def test_missing_mock_file_returns_empty(self, tmp_path):
        """When mcp-mock.json is missing, _build_mock_tools returns empty list."""
        with patch("mcp_tools._MOCK_FILE", tmp_path / "nonexistent.json"):
            from mcp_tools import _build_mock_tools
            tools = _build_mock_tools()
            assert tools == []

    def test_corrupt_mock_file_returns_empty(self, tmp_path):
        """When mcp-mock.json is invalid JSON, _build_mock_tools returns empty list."""
        bad_file = tmp_path / "mcp-mock.json"
        bad_file.write_text("{ invalid json }")
        with patch("mcp_tools._MOCK_FILE", bad_file):
            from mcp_tools import _build_mock_tools
            tools = _build_mock_tools()
            assert tools == []

    def test_all_piva_tools_present(self):
        """All 5 PIVA MCP tools should be loaded from mcp-mock.json."""
        from mcp_tools import _build_mock_tools
        tools = _build_mock_tools()
        tool_names = [t.name for t in tools]
        expected_tools = [
            "list_ProductEWMWarehouse",
            "list_WarehousePhysicalInventoryDoc",
            "get_WarehousePhysicalInventoryDocItem",
            "create_WarehousePhysicalInventoryDoc",
            "post_PhysicalInventoryDifference",
        ]
        for expected in expected_tools:
            assert expected in tool_names, f"Expected tool '{expected}' not found in {tool_names}"

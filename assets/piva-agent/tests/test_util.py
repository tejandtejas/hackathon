"""Tests for utility functions in util.py."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

import pytest
from unittest.mock import MagicMock
from util import _is_retryable_error, enhance_tool_description, enhance_tool_name
import httpx


class TestIsRetryableError:
    def test_generic_exception_is_retryable(self):
        assert _is_retryable_error(RuntimeError("connection reset")) is True

    def test_value_error_is_retryable(self):
        assert _is_retryable_error(ValueError("timeout")) is True

    def test_http_5xx_is_retryable(self):
        mock_response = MagicMock()
        mock_response.status_code = 500
        exc = httpx.HTTPStatusError("Server error", request=MagicMock(), response=mock_response)
        assert _is_retryable_error(exc) is True

    def test_http_503_is_retryable(self):
        mock_response = MagicMock()
        mock_response.status_code = 503
        exc = httpx.HTTPStatusError("Service unavailable", request=MagicMock(), response=mock_response)
        assert _is_retryable_error(exc) is True

    def test_http_4xx_is_not_retryable(self):
        mock_response = MagicMock()
        mock_response.status_code = 400
        exc = httpx.HTTPStatusError("Bad request", request=MagicMock(), response=mock_response)
        assert _is_retryable_error(exc) is False

    def test_http_401_is_not_retryable(self):
        mock_response = MagicMock()
        mock_response.status_code = 401
        exc = httpx.HTTPStatusError("Unauthorized", request=MagicMock(), response=mock_response)
        assert _is_retryable_error(exc) is False

    def test_http_404_is_not_retryable(self):
        mock_response = MagicMock()
        mock_response.status_code = 404
        exc = httpx.HTTPStatusError("Not found", request=MagicMock(), response=mock_response)
        assert _is_retryable_error(exc) is False


class TestEnhanceToolDescription:
    def test_tool_with_description_and_server_name(self):
        mock_tool = MagicMock()
        mock_tool.description = "List all products"
        mock_tool.name = "mcp_ewm__list_products"
        result = enhance_tool_description(mock_tool)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_tool_with_empty_description(self):
        mock_tool = MagicMock()
        mock_tool.description = ""
        mock_tool.name = "mcp_test__tool"
        result = enhance_tool_description(mock_tool)
        assert isinstance(result, str)

    def test_tool_without_name(self):
        mock_tool = MagicMock()
        mock_tool.description = "Some tool"
        mock_tool.name = "simple_tool"
        result = enhance_tool_description(mock_tool)
        assert isinstance(result, str)


class TestEnhanceToolName:
    def test_tool_name_returned(self):
        mock_tool = MagicMock()
        mock_tool.name = "mcp_ewm__list_products"
        result = enhance_tool_name(mock_tool)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_simple_tool_name(self):
        mock_tool = MagicMock()
        mock_tool.name = "list_items"
        result = enhance_tool_name(mock_tool)
        assert isinstance(result, str)

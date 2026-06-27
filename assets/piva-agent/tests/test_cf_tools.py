"""Tests for CF-runtime direct-API tools (tools/cf_tools.py)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import json
import pytest
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# FakeClient for CF tools tests
# ---------------------------------------------------------------------------

@dataclass
class FakeCall:
    method: str
    path: str
    params: dict = field(default_factory=dict)
    body: Any = None


@dataclass
class FakeClient:
    responses: dict = field(default_factory=dict)
    calls: list = field(default_factory=list)

    def _resolve(self, call: FakeCall) -> dict:
        # Sort by key length descending so more-specific keys (longer) win over substrings
        for needle, payload in sorted(self.responses.items(), key=lambda kv: len(kv[0]), reverse=True):
            if needle in call.path:
                if callable(payload):
                    return payload(call)
                return dict(payload) if isinstance(payload, dict) else payload
        return {"results": []}

    async def get(self, service_path: str, params=None, user_identity=None) -> dict:
        call = FakeCall("GET", service_path, dict(params or {}))
        self.calls.append(call)
        return self._resolve(call)

    async def post(self, service_path: str, body: Any, service_root: str, user_identity=None) -> dict:
        call = FakeCall("POST", service_path, {}, body)
        self.calls.append(call)
        return self._resolve(call)


def make_fake(responses=None) -> FakeClient:
    return FakeClient(responses=dict(responses or {}))


# ---------------------------------------------------------------------------
# Tests: query_products_due_for_counting (CF)
# ---------------------------------------------------------------------------

class TestCFDueForCounting:
    @pytest.mark.asyncio
    async def test_returns_json_with_due_products(self):
        from tools.cf_tools import _query_products_due_for_counting_cf
        fake = make_fake({
            "_ProductEWMWarehouse": {
                "results": [
                    {
                        "Product": "MAT-001", "WarehouseNumber": "0001",
                        "CycleCountingIndicator": "A", "PhysicalInventoryCycle": "30",
                        "LastPhysicalInventoryDate": "2020-01-01",
                    }
                ]
            }
        })
        result_str = await _query_products_due_for_counting_cf("0001", _client=fake)
        result = json.loads(result_str)
        assert result["total_due"] >= 1
        assert len(result["due_products"]) >= 1

    @pytest.mark.asyncio
    async def test_injects_sap_format_param(self):
        from tools.cf_tools import _query_products_due_for_counting_cf
        fake = make_fake({"_ProductEWMWarehouse": {"results": []}})
        await _query_products_due_for_counting_cf("0001", _client=fake)
        assert fake.calls
        call = fake.calls[0]
        assert call.params.get("$format") == "json"
        assert call.params.get("$top") == 100

    @pytest.mark.asyncio
    async def test_multi_warehouse_makes_multiple_calls(self):
        from tools.cf_tools import _query_products_due_for_counting_cf
        fake = make_fake({"_ProductEWMWarehouse": {"results": []}})
        await _query_products_due_for_counting_cf("0001", warehouses="0001,0002", _client=fake)
        assert len(fake.calls) == 2

    @pytest.mark.asyncio
    async def test_api_error_returned_as_json(self):
        from tools.cf_tools import _query_products_due_for_counting_cf
        fake = make_fake({"_ProductEWMWarehouse": {"error": True, "message": "Service unavailable"}})
        result_str = await _query_products_due_for_counting_cf("0001", _client=fake)
        result = json.loads(result_str)
        assert "error" in result


# ---------------------------------------------------------------------------
# Tests: query_missing_cci_products (CF)
# ---------------------------------------------------------------------------

class TestCFMissingCci:
    @pytest.mark.asyncio
    async def test_returns_products_without_cci(self):
        from tools.cf_tools import _query_missing_cci_cf
        fake = make_fake({
            "_ProductEWMWarehouse": {
                "results": [
                    {"Product": "MAT-002", "WarehouseNumber": "0001",
                     "CycleCountingIndicator": ""},
                    {"Product": "MAT-003", "WarehouseNumber": "0001",
                     "CycleCountingIndicator": "A"},
                ]
            }
        })
        result_str = await _query_missing_cci_cf("0001", _client=fake)
        result = json.loads(result_str)
        assert result["count"] == 1
        assert result["missing_cci_products"][0]["product"] == "MAT-002"


# ---------------------------------------------------------------------------
# Tests: create_physical_inventory_documents (CF)
# ---------------------------------------------------------------------------

class TestCFCreateDocuments:
    @pytest.mark.asyncio
    async def test_unconfirmed_returns_prompt(self):
        from tools.cf_tools import _create_physical_inventory_documents_cf
        fake = make_fake()
        result = await _create_physical_inventory_documents_cf(
            "MAT-001,MAT-002", "0001", confirmed="no", _client=fake)
        assert "confirm" in result.lower() or "please" in result.lower()
        assert not fake.calls  # no API calls when not confirmed

    @pytest.mark.asyncio
    async def test_confirmed_creates_documents(self):
        from tools.cf_tools import _create_physical_inventory_documents_cf
        fake = make_fake({
            "WarehousePhysicalInventoryDoc": {
                "InventoryDocument": "5000000001", "FiscalYear": "2025"
            }
        })
        result_str = await _create_physical_inventory_documents_cf(
            "MAT-001,MAT-002", "0001", confirmed="yes", _client=fake)
        result = json.loads(result_str)
        assert result["created_count"] == 2
        assert len(fake.calls) == 2

    @pytest.mark.asyncio
    async def test_post_failure_recorded(self):
        from tools.cf_tools import _create_physical_inventory_documents_cf
        fake = make_fake({
            "WarehousePhysicalInventoryDoc": {"error": True, "message": "Creation failed"}
        })
        result_str = await _create_physical_inventory_documents_cf(
            "MAT-001", "0001", confirmed="yes", _client=fake)
        result = json.loads(result_str)
        assert result["failed_count"] == 1


# ---------------------------------------------------------------------------
# Tests: query_stock_difference_summary (CF)
# ---------------------------------------------------------------------------

class TestCFStockDifference:
    @pytest.mark.asyncio
    async def test_returns_classified_items(self):
        from tools.cf_tools import _query_stock_difference_summary_cf
        fake = make_fake({
            "WarehousePhysicalInventoryDoc": {
                "results": [{"InventoryDocument": "5000000001", "FiscalYear": "2025",
                             "WarehouseNumber": "0001", "InventoryDocumentStatus": "COUNTED"}]
            },
            "WarehousePhysicalInventoryDocItem": {
                "results": [{"InventoryDocument": "5000000001", "FiscalYear": "2025",
                             "InventoryDocumentItem": "0001", "Product": "MAT-001",
                             "BookQuantity": "100", "CountedQuantity": "101",
                             "WarehouseNumber": "0001"}]
            }
        })
        result_str = await _query_stock_difference_summary_cf("0001", _client=fake)
        result = json.loads(result_str)
        assert result["total_items"] == 1
        assert result["green_count"] >= 1

    @pytest.mark.asyncio
    async def test_red_item_classified(self):
        from tools.cf_tools import _query_stock_difference_summary_cf
        fake = make_fake({
            "WarehousePhysicalInventoryDoc": {
                "results": [{"InventoryDocument": "5000000001", "FiscalYear": "2025",
                             "WarehouseNumber": "0001", "InventoryDocumentStatus": "COUNTED"}]
            },
            "WarehousePhysicalInventoryDocItem": {
                "results": [{"InventoryDocument": "5000000001", "FiscalYear": "2025",
                             "InventoryDocumentItem": "0001", "Product": "MAT-999",
                             "BookQuantity": "100", "CountedQuantity": "150",
                             "WarehouseNumber": "0001"}]
            }
        })
        result_str = await _query_stock_difference_summary_cf("0001", _client=fake)
        result = json.loads(result_str)
        assert result["red_count"] == 1


# ---------------------------------------------------------------------------
# Tests: post_inventory_differences (CF)
# ---------------------------------------------------------------------------

class TestCFPostDifferences:
    @pytest.mark.asyncio
    async def test_unconfirmed_returns_prompt(self):
        from tools.cf_tools import _post_inventory_differences_cf
        fake = make_fake()
        result = await _post_inventory_differences_cf(
            "DOC001", "0001", confirmed="no", _client=fake)
        assert "confirm" in result.lower()
        assert not fake.calls

    @pytest.mark.asyncio
    async def test_confirmed_posts_documents(self):
        from tools.cf_tools import _post_inventory_differences_cf
        fake = make_fake({"PostDifference": {"status": "ok"}})
        result_str = await _post_inventory_differences_cf(
            "DOC001,DOC002", "0001", confirmed="yes", _client=fake)
        result = json.loads(result_str)
        assert result["posted_count"] == 2


# ---------------------------------------------------------------------------
# Tests: query_document_status_summary (CF)
# ---------------------------------------------------------------------------

class TestCFDocumentStatus:
    @pytest.mark.asyncio
    async def test_groups_by_status(self):
        from tools.cf_tools import _query_document_status_summary_cf
        fake = make_fake({
            "WarehousePhysicalInventoryDoc": {
                "results": [
                    {"InventoryDocument": "D001", "FiscalYear": "2025", "WarehouseNumber": "0001",
                     "InventoryDocumentStatus": "OPEN"},
                    {"InventoryDocument": "D002", "FiscalYear": "2025", "WarehouseNumber": "0001",
                     "InventoryDocumentStatus": "COUNTED"},
                ]
            }
        })
        result_str = await _query_document_status_summary_cf("0001", _client=fake)
        result = json.loads(result_str)
        assert result["total_documents"] == 2
        wh = result["warehouses"][0]
        assert wh["open"] == 1
        assert wh["counted"] == 1


# ---------------------------------------------------------------------------
# Tests: build_cf_tools factory
# ---------------------------------------------------------------------------

class TestBuildCfTools:
    def test_returns_six_tools(self):
        from tools.cf_tools import build_cf_tools
        fake = make_fake()
        tools = build_cf_tools(fake)
        assert len(tools) == 6

    def test_tool_names_match_expected(self):
        from tools.cf_tools import build_cf_tools
        fake = make_fake()
        tools = build_cf_tools(fake)
        names = {t.name for t in tools}
        expected = {
            "query_products_due_for_counting",
            "query_missing_cci_products",
            "create_physical_inventory_documents",
            "query_stock_difference_summary",
            "post_inventory_differences",
            "query_document_status_summary",
        }
        assert names == expected

    @pytest.mark.asyncio
    async def test_tools_are_callable(self):
        from tools.cf_tools import build_cf_tools
        fake = make_fake({
            "_ProductEWMWarehouse": {"results": []},
            "WarehousePhysicalInventoryDoc": {"results": []},
        })
        tools = build_cf_tools(fake)
        due_tool = next(t for t in tools if t.name == "query_products_due_for_counting")
        result = await due_tool.ainvoke({"warehouse": "0001"})
        data = json.loads(result)
        assert "due_products" in data

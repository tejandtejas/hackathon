"""Tests for tool invocations (LangChain @tool decorated functions)."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from tools.inventory_due import query_products_due_for_counting
from tools.missing_cci import query_missing_cci_products
from tools.create_documents import create_physical_inventory_documents
from tools.stock_difference import query_stock_difference_summary
from tools.document_status import query_document_status_summary


class TestQueryProductsDueInvoke:
    def test_single_warehouse_returns_instruction_string(self):
        result = query_products_due_for_counting.invoke({
            "warehouse": "0001",
            "cci_filter": "A",
            "warehouses": "",
        })
        assert isinstance(result, str)
        assert "0001" in result or "warehouse" in result.lower()

    def test_multi_warehouse_param_included(self):
        result = query_products_due_for_counting.invoke({
            "warehouse": "0001",
            "cci_filter": "",
            "warehouses": "0001,0002",
        })
        assert isinstance(result, str)

    def test_no_cci_filter(self):
        result = query_products_due_for_counting.invoke({
            "warehouse": "0001",
            "cci_filter": "",
            "warehouses": "",
        })
        assert isinstance(result, str)


class TestQueryMissingCciInvoke:
    def test_single_warehouse(self):
        result = query_missing_cci_products.invoke({
            "warehouse": "0001",
            "warehouses": "",
        })
        assert isinstance(result, str)
        assert "WarehouseNumber" in result or "warehouse" in result.lower() or "0001" in result

    def test_multi_warehouse(self):
        result = query_missing_cci_products.invoke({
            "warehouse": "0001",
            "warehouses": "0001,0002",
        })
        assert isinstance(result, str)


class TestCreateDocumentsInvoke:
    def test_unconfirmed_returns_confirmation_prompt(self):
        result = create_physical_inventory_documents.invoke({
            "products": "MAT-001,MAT-002",
            "warehouse": "0001",
            "confirmed": "no",
        })
        assert "confirm" in result.lower() or "please" in result.lower()
        assert "MAT-001" in result

    def test_confirmed_yes_proceeds(self):
        result = create_physical_inventory_documents.invoke({
            "products": "MAT-001",
            "warehouse": "0001",
            "confirmed": "yes",
        })
        assert "CONFIRMED" in result
        assert "MAT-001" in result

    def test_confirmed_true_proceeds(self):
        result = create_physical_inventory_documents.invoke({
            "products": "MAT-003",
            "warehouse": "0002",
            "confirmed": "true",
        })
        assert "CONFIRMED" in result


class TestQueryStockDifferenceInvoke:
    def test_basic_query_returns_instruction(self):
        result = query_stock_difference_summary.invoke({
            "warehouse": "0001",
            "inventory_documents": "",
            "green_threshold": 2.0,
            "amber_threshold": 5.0,
        })
        assert isinstance(result, str)
        assert "COUNTED" in result

    def test_custom_thresholds_reflected(self):
        result = query_stock_difference_summary.invoke({
            "warehouse": "0001",
            "inventory_documents": "",
            "green_threshold": 1.0,
            "amber_threshold": 3.0,
        })
        assert "1.0" in result or "3.0" in result

    def test_document_filter_included(self):
        result = query_stock_difference_summary.invoke({
            "warehouse": "0001",
            "inventory_documents": "DOC001,DOC002",
            "green_threshold": 2.0,
            "amber_threshold": 5.0,
        })
        assert "DOC001" in result or "filtered" in result.lower()


class TestQueryDocumentStatusInvoke:
    def test_single_warehouse(self):
        result = query_document_status_summary.invoke({
            "warehouse": "0001",
            "warehouses": "",
        })
        assert isinstance(result, str)
        assert "0001" in result

    def test_multi_warehouse(self):
        result = query_document_status_summary.invoke({
            "warehouse": "0001",
            "warehouses": "0001,0002",
        })
        assert isinstance(result, str)
        assert "0001,0002" in result or "0001" in result

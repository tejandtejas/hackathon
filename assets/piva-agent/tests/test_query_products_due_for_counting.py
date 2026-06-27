"""Unit tests for query_products_due_for_counting tool logic."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from datetime import date, timedelta
from tools.inventory_due import build_due_products_result, _parse_date, _cycle_days, _is_overdue


def _make_record(product, warehouse, cci, cycle, last_date):
    return {
        "Product": product,
        "WarehouseNumber": warehouse,
        "CycleCountingIndicator": cci,
        "PhysicalInventoryCycle": cycle,
        "LastPhysicalInventoryDate": last_date,
    }


class TestParseDateUtil:
    def test_parse_iso_date(self):
        d = _parse_date("2024-01-15")
        assert d == date(2024, 1, 15)

    def test_parse_none(self):
        assert _parse_date(None) is None

    def test_parse_empty_string(self):
        assert _parse_date("") is None


class TestCycleDays:
    def test_from_field(self):
        assert _cycle_days("A", "45") == 45

    def test_from_cci_default_a(self):
        assert _cycle_days("A", None) == 30

    def test_from_cci_default_b(self):
        assert _cycle_days("B", None) == 90

    def test_from_cci_default_c(self):
        assert _cycle_days("C", None) == 180

    def test_unknown_cci_no_field(self):
        assert _cycle_days("Z", None) is None


class TestIsOverdue:
    def test_never_counted_is_overdue(self):
        overdue, status = _is_overdue(None, 30)
        assert overdue is True
        assert "Never counted" in status

    def test_overdue_past_due_date(self):
        last = date.today() - timedelta(days=40)
        overdue, status = _is_overdue(last, 30)
        assert overdue is True

    def test_not_overdue_future_due_date(self):
        last = date.today() - timedelta(days=10)
        overdue, status = _is_overdue(last, 30)
        assert overdue is False

    def test_due_today_is_overdue(self):
        last = date.today() - timedelta(days=30)
        overdue, _ = _is_overdue(last, 30)
        assert overdue is True

    def test_no_cycle_days_not_overdue(self):
        last = date.today() - timedelta(days=100)
        overdue, status = _is_overdue(last, None)
        assert overdue is False
        assert "No cycle configured" in status


class TestBuildDueProductsResult:
    def test_overdue_product_included(self):
        last = (date.today() - timedelta(days=40)).isoformat()
        records = [_make_record("MAT-001", "0001", "A", "30", last)]
        result = build_due_products_result(records)
        assert result["total_due"] == 1
        assert result["due_products"][0]["product"] == "MAT-001"

    def test_not_overdue_excluded(self):
        last = (date.today() - timedelta(days=5)).isoformat()
        records = [_make_record("MAT-001", "0001", "A", "30", last)]
        result = build_due_products_result(records)
        assert result["total_due"] == 0

    def test_never_counted_always_due(self):
        records = [_make_record("MAT-002", "0001", "B", "90", None)]
        result = build_due_products_result(records)
        assert result["total_due"] == 1
        assert result["due_products"][0]["last_count_date"] == "Never"

    def test_cci_filter_applies(self):
        last = (date.today() - timedelta(days=40)).isoformat()
        records = [
            _make_record("MAT-001", "0001", "A", "30", last),
            _make_record("MAT-002", "0001", "B", "90", last),
        ]
        result = build_due_products_result(records, cci_filter="A")
        assert result["total_due"] == 1
        assert result["due_products"][0]["cci"] == "A"

    def test_segmented_by_cci(self):
        last_a = (date.today() - timedelta(days=40)).isoformat()
        last_b = (date.today() - timedelta(days=100)).isoformat()
        records = [
            _make_record("MAT-001", "0001", "A", "30", last_a),
            _make_record("MAT-002", "0001", "B", "90", last_b),
        ]
        result = build_due_products_result(records)
        assert "A" in result["by_cci"]
        assert "B" in result["by_cci"]
        assert len(result["by_cci"]["A"]) == 1
        assert len(result["by_cci"]["B"]) == 1

    def test_multi_warehouse_products(self):
        last = (date.today() - timedelta(days=40)).isoformat()
        records = [
            _make_record("MAT-001", "0001", "A", "30", last),
            _make_record("MAT-002", "0002", "A", "30", last),
        ]
        result = build_due_products_result(records)
        assert result["total_due"] == 2
        warehouses = {p["warehouse"] for p in result["due_products"]}
        assert "0001" in warehouses
        assert "0002" in warehouses

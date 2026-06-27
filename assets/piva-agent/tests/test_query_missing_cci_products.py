"""Unit tests for query_missing_cci_products tool logic."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from tools.missing_cci import build_missing_cci_result


def _make_record(product, warehouse, cci, last_date=None):
    return {
        "Product": product,
        "WarehouseNumber": warehouse,
        "CycleCountingIndicator": cci,
        "LastPhysicalInventoryDate": last_date,
    }


class TestBuildMissingCciResult:
    def test_null_cci_flagged(self):
        records = [_make_record("MAT-001", "0001", None)]
        result = build_missing_cci_result(records)
        assert result["count"] == 1
        assert result["missing_cci_products"][0]["product"] == "MAT-001"

    def test_empty_string_cci_flagged(self):
        records = [_make_record("MAT-002", "0001", "")]
        result = build_missing_cci_result(records)
        assert result["count"] == 1

    def test_whitespace_cci_flagged(self):
        records = [_make_record("MAT-003", "0001", "   ")]
        result = build_missing_cci_result(records)
        assert result["count"] == 1

    def test_valid_cci_not_flagged(self):
        records = [_make_record("MAT-004", "0001", "A")]
        result = build_missing_cci_result(records)
        assert result["count"] == 0

    def test_mixed_records(self):
        records = [
            _make_record("MAT-001", "0001", "A"),
            _make_record("MAT-002", "0001", None),
            _make_record("MAT-003", "0001", ""),
        ]
        result = build_missing_cci_result(records)
        assert result["count"] == 2

    def test_advisory_message_present(self):
        records = [_make_record("MAT-001", "0001", None)]
        result = build_missing_cci_result(records)
        assert "advisory" in result
        assert "Cycle Counting Indicator" in result["advisory"]

    def test_recommendation_in_each_product(self):
        records = [_make_record("MAT-001", "0001", None)]
        result = build_missing_cci_result(records)
        assert "recommendation" in result["missing_cci_products"][0]

    def test_multi_warehouse(self):
        records = [
            _make_record("MAT-001", "0001", None),
            _make_record("MAT-002", "0002", None),
        ]
        result = build_missing_cci_result(records)
        warehouses = {p["warehouse"] for p in result["missing_cci_products"]}
        assert "0001" in warehouses
        assert "0002" in warehouses

    def test_empty_records(self):
        result = build_missing_cci_result([])
        assert result["count"] == 0
        assert result["missing_cci_products"] == []

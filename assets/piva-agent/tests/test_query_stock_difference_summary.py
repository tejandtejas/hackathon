"""Unit tests for query_stock_difference_summary tool logic."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from tools.stock_difference import build_difference_summary, _classify_difference, _safe_float


def _make_item(doc, item_num, product, warehouse, booked, counted):
    return {
        "InventoryDocument": doc,
        "InventoryDocumentItem": item_num,
        "Product": product,
        "WarehouseNumber": warehouse,
        "BookQuantity": str(booked) if booked is not None else None,
        "CountedQuantity": str(counted) if counted is not None else None,
        "QuantityInBaseUnit": "EA",
    }


class TestClassifyDifference:
    def test_green_within_tolerance(self):
        assert "GREEN" in _classify_difference(1.5, 2.0, 5.0)

    def test_green_at_tolerance_boundary(self):
        assert "GREEN" in _classify_difference(2.0, 2.0, 5.0)

    def test_amber_above_green(self):
        assert "AMBER" in _classify_difference(3.0, 2.0, 5.0)

    def test_amber_at_amber_boundary(self):
        assert "AMBER" in _classify_difference(5.0, 2.0, 5.0)

    def test_red_above_amber(self):
        assert "RED" in _classify_difference(7.0, 2.0, 5.0)

    def test_none_diff_pct_returns_amber(self):
        assert "AMBER" in _classify_difference(None, 2.0, 5.0)

    def test_zero_diff_is_green(self):
        assert "GREEN" in _classify_difference(0.0, 2.0, 5.0)


class TestBuildDifferenceSummary:
    def test_green_item(self):
        items = [_make_item("DOC001", "0001", "MAT-001", "0001", 100, 101)]
        result = build_difference_summary(items)
        assert result["green_count"] == 1
        assert result["amber_count"] == 0
        assert result["red_count"] == 0

    def test_amber_item(self):
        items = [_make_item("DOC001", "0001", "MAT-001", "0001", 100, 104)]
        result = build_difference_summary(items)
        assert result["amber_count"] == 1

    def test_red_item(self):
        items = [_make_item("DOC001", "0001", "MAT-001", "0001", 100, 110)]
        result = build_difference_summary(items)
        assert result["red_count"] == 1

    def test_red_item_labelled_requires_recount(self):
        items = [_make_item("DOC001", "0001", "MAT-001", "0001", 100, 110)]
        result = build_difference_summary(items)
        assert result["summary"][0]["recount_required"] is True
        assert result["summary"][0]["label"] == "Requires Recount"

    def test_zero_book_quantity_no_percentage(self):
        items = [_make_item("DOC001", "0001", "MAT-001", "0001", 0, 5)]
        result = build_difference_summary(items)
        assert result["summary"][0]["diff_pct"] is None
        assert result["summary"][0]["note"] == "No reference quantity"

    def test_threshold_override(self):
        # With tighter threshold: 3% diff should be red
        items = [_make_item("DOC001", "0001", "MAT-001", "0001", 100, 103)]
        result = build_difference_summary(items, green_threshold=1.0, amber_threshold=2.0)
        assert result["red_count"] == 1

    def test_thresholds_in_result(self):
        items = [_make_item("DOC001", "0001", "MAT-001", "0001", 100, 101)]
        result = build_difference_summary(items, green_threshold=2.0, amber_threshold=5.0)
        assert result["thresholds_used"]["green_pct"] == 2.0
        assert result["thresholds_used"]["amber_pct"] == 5.0

    def test_difference_computed_correctly(self):
        items = [_make_item("DOC001", "0001", "MAT-001", "0001", 100, 95)]
        result = build_difference_summary(items)
        assert result["summary"][0]["difference"] == -5.0
        assert result["summary"][0]["diff_pct"] == 5.0

    def test_mixed_classifications(self):
        items = [
            _make_item("DOC001", "0001", "MAT-001", "0001", 100, 101),   # Green
            _make_item("DOC001", "0002", "MAT-002", "0001", 100, 104),   # Amber
            _make_item("DOC001", "0003", "MAT-003", "0001", 100, 115),   # Red
        ]
        result = build_difference_summary(items)
        assert result["green_count"] == 1
        assert result["amber_count"] == 1
        assert result["red_count"] == 1
        assert result["total_items"] == 3


class TestSafeFloat:
    def test_string_number(self):
        assert _safe_float("100.5") == 100.5

    def test_none_returns_none(self):
        assert _safe_float(None) is None

    def test_invalid_string_returns_none(self):
        assert _safe_float("abc") is None

    def test_integer(self):
        assert _safe_float(50) == 50.0

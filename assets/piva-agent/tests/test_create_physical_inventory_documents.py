"""Unit tests for create_physical_inventory_documents tool logic."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from tools.create_documents import _requires_confirmation, build_creation_result


class TestRequiresConfirmation:
    def test_yes_confirms(self):
        assert _requires_confirmation("yes") is True

    def test_confirm_confirms(self):
        assert _requires_confirmation("confirm") is True

    def test_proceed_confirms(self):
        assert _requires_confirmation("proceed") is True

    def test_ok_confirms(self):
        assert _requires_confirmation("ok") is True

    def test_go_ahead_confirms(self):
        assert _requires_confirmation("go ahead") is True

    def test_negative_no(self):
        assert _requires_confirmation("no") is False

    def test_negative_cancel(self):
        assert _requires_confirmation("cancel") is False

    def test_empty_string_no_confirm(self):
        assert _requires_confirmation("") is False

    def test_case_insensitive(self):
        assert _requires_confirmation("YES") is True
        assert _requires_confirmation("Confirm") is True

    def test_phrase_with_yes(self):
        assert _requires_confirmation("yes please create them") is True


class TestBuildCreationResult:
    def test_all_created(self):
        created = [
            {"product": "MAT-001", "document": "0000100001", "fiscal_year": "2026"},
            {"product": "MAT-002", "document": "0000100002", "fiscal_year": "2026"},
        ]
        result = build_creation_result(created, [])
        assert result["created_count"] == 2
        assert result["failed_count"] == 0

    def test_partial_failure(self):
        created = [{"product": "MAT-001", "document": "0000100001", "fiscal_year": "2026"}]
        failed = [{"product": "MAT-002", "reason": "Product not found in warehouse"}]
        result = build_creation_result(created, failed)
        assert result["created_count"] == 1
        assert result["failed_count"] == 1

    def test_all_failed(self):
        failed = [
            {"product": "MAT-001", "reason": "Authorization error"},
            {"product": "MAT-002", "reason": "Product locked"},
        ]
        result = build_creation_result([], failed)
        assert result["created_count"] == 0
        assert result["failed_count"] == 2
        assert result["created"] == []

    def test_empty_result(self):
        result = build_creation_result([], [])
        assert result["created_count"] == 0
        assert result["failed_count"] == 0

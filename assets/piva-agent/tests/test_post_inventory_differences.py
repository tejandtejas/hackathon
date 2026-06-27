"""Unit tests for post_inventory_differences tool logic."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from tools.post_differences import post_inventory_differences


class TestPostInventoryDifferences:
    def test_no_confirmation_returns_prompt(self):
        result = post_inventory_differences.invoke({
            "documents_to_post": "DOC001,DOC002",
            "warehouse": "0001",
            "confirmed": "no",
        })
        assert "confirm" in result.lower() or "please" in result.lower()

    def test_empty_confirmed_returns_prompt(self):
        result = post_inventory_differences.invoke({
            "documents_to_post": "DOC001",
            "warehouse": "0001",
            "confirmed": "",
        })
        assert "confirm" in result.lower()

    def test_confirmed_yes_proceeds(self):
        result = post_inventory_differences.invoke({
            "documents_to_post": "DOC001,DOC002",
            "warehouse": "0001",
            "confirmed": "yes",
        })
        assert "CONFIRMED" in result

    def test_red_items_excluded_by_default(self):
        result = post_inventory_differences.invoke({
            "documents_to_post": "DOC001",
            "warehouse": "0001",
            "confirmed": "no",
            "include_red_items": "no",
        })
        assert "excluded" in result.lower() or "Requires Recount" in result or "EXCLUDED" in result

    def test_include_red_items_noted_in_output(self):
        result = post_inventory_differences.invoke({
            "documents_to_post": "DOC001",
            "warehouse": "0001",
            "confirmed": "no",
            "include_red_items": "yes",
        })
        assert "included" in result.lower() or "supervisor request" in result.lower()

    def test_excluded_items_listed_in_prompt(self):
        result = post_inventory_differences.invoke({
            "documents_to_post": "DOC001",
            "warehouse": "0001",
            "excluded_items": "DOC001-0002",
            "confirmed": "no",
        })
        assert "DOC001-0002" in result or "exclusion" in result.lower() or "Excluded" in result

    def test_confirmed_with_exclusions_proceeds(self):
        result = post_inventory_differences.invoke({
            "documents_to_post": "DOC001,DOC002",
            "warehouse": "0001",
            "excluded_items": "DOC001-0003",
            "confirmed": "yes",
        })
        assert "CONFIRMED" in result
        assert "DOC001-0003" in result

    def test_empty_documents_still_responds(self):
        result = post_inventory_differences.invoke({
            "documents_to_post": "",
            "warehouse": "0001",
            "confirmed": "yes",
        })
        # Should still return a response without error
        assert isinstance(result, str)

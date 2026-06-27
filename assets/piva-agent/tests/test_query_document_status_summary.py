"""Unit tests for query_document_status_summary tool logic."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from tools.document_status import build_status_summary


def _make_doc(doc_num, warehouse, status):
    return {
        "InventoryDocument": doc_num,
        "WarehouseNumber": warehouse,
        "InventoryDocumentStatus": status,
    }


class TestBuildStatusSummary:
    def test_open_document_counted(self):
        docs = [_make_doc("DOC001", "0001", "OPEN")]
        result = build_status_summary(docs)
        wh = result["warehouses"][0]
        assert wh["open"] == 1
        assert wh["counted"] == 0

    def test_counted_document(self):
        docs = [_make_doc("DOC001", "0001", "COUNTED")]
        result = build_status_summary(docs)
        wh = result["warehouses"][0]
        assert wh["counted"] == 1

    def test_posted_document(self):
        docs = [_make_doc("DOC001", "0001", "POSTED")]
        result = build_status_summary(docs)
        wh = result["warehouses"][0]
        assert wh["posted"] == 1

    def test_multi_warehouse(self):
        docs = [
            _make_doc("DOC001", "0001", "OPEN"),
            _make_doc("DOC002", "0002", "COUNTED"),
        ]
        result = build_status_summary(docs)
        assert len(result["warehouses"]) == 2
        warehouses = {w["warehouse"] for w in result["warehouses"]}
        assert "0001" in warehouses
        assert "0002" in warehouses

    def test_total_documents(self):
        docs = [
            _make_doc("DOC001", "0001", "OPEN"),
            _make_doc("DOC002", "0001", "COUNTED"),
            _make_doc("DOC003", "0001", "POSTED"),
        ]
        result = build_status_summary(docs)
        assert result["total_documents"] == 3

    def test_same_warehouse_different_statuses(self):
        docs = [
            _make_doc("DOC001", "0001", "OPEN"),
            _make_doc("DOC002", "0001", "OPEN"),
            _make_doc("DOC003", "0001", "COUNTED"),
            _make_doc("DOC004", "0001", "POSTED"),
        ]
        result = build_status_summary(docs)
        wh = result["warehouses"][0]
        assert wh["open"] == 2
        assert wh["counted"] == 1
        assert wh["posted"] == 1
        assert wh["total"] == 4

    def test_empty_docs(self):
        result = build_status_summary([])
        assert result["total_documents"] == 0
        assert result["warehouses"] == []

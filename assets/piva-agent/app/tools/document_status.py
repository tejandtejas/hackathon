"""
Tool: query_document_status_summary
REQ-06: Summarise physical inventory document status across one or multiple warehouses.
"""
import logging
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

STATUS_LABELS = {
    "OPEN": "Open",
    "COUNTED": "Counted",
    "POSTED": "Posted",
    "PARTIAL": "Partially Posted",
}


def build_status_summary(raw_docs: list[dict]) -> dict:
    """Group documents by warehouse and status."""
    by_warehouse: dict[str, dict] = {}
    for doc in raw_docs:
        wh = doc.get("WarehouseNumber") or doc.get("warehouseNumber", "UNKNOWN")
        status = (doc.get("InventoryDocumentStatus") or doc.get("inventoryDocumentStatus") or "OPEN").upper()
        by_warehouse.setdefault(wh, {"Open": [], "Counted": [], "Posted": [], "Partially Posted": []})
        label = STATUS_LABELS.get(status, status)
        by_warehouse[wh].setdefault(label, []).append(
            doc.get("InventoryDocument") or doc.get("inventoryDocument", "")
        )

    result = []
    for wh, groups in by_warehouse.items():
        result.append({
            "warehouse": wh,
            "open": len(groups.get("Open", [])),
            "counted": len(groups.get("Counted", [])),
            "posted": len(groups.get("Posted", [])),
            "partially_posted": len(groups.get("Partially Posted", [])),
            "total": sum(len(v) for v in groups.values()),
            "documents": groups,
        })
    return {"warehouses": result, "total_documents": sum(r["total"] for r in result)}


@tool
def query_document_status_summary(warehouse: str, warehouses: str = "") -> str:
    """Get a summary of physical inventory documents grouped by status for one or more warehouses.

    Returns counts of documents in each status: Open, Counted, Posted, Partially Posted.
    Useful for warehouse managers monitoring overall cycle completion.

    IMPORTANT: This is a READ-ONLY tool.

    Args:
        warehouse: Single EWM warehouse number (e.g. '0001').
        warehouses: Comma-separated list for multi-warehouse summary (e.g. '0001,0002').
                    If provided, overrides the warehouse parameter.

    Returns:
        Summary table: Warehouse | Open | Counted | Posted | Partially Posted | Total
    """
    scope = warehouses if warehouses.strip() else warehouse
    return (
        f"Query: warehouses={scope}. "
        "Call list_WarehousePhysicalInventoryDoc MCP tool for each warehouse, $top=100, "
        "no status filter (retrieve all statuses). "
        "Group results by InventoryDocumentStatus: OPEN, COUNTED, POSTED, PARTIAL. "
        "Present summary table: Warehouse | Open | Counted | Posted | Partially Posted | Total."
    )

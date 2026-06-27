"""
Tool: query_stock_difference_summary
REQ-04: Compare counted vs. booked stock with Green/Amber/Red classification.
"""
import logging
from typing import Optional
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

DEFAULT_GREEN_THRESHOLD = 2.0   # % — within tolerance
DEFAULT_AMBER_THRESHOLD = 5.0   # % — approaching tolerance (Green < x <= Amber)


def _classify_difference(diff_pct: Optional[float], green: float, amber: float) -> str:
    """Classify a difference percentage into Green/Amber/Red."""
    if diff_pct is None:
        return "🟡 AMBER"  # No reference quantity — treat as amber
    abs_pct = abs(diff_pct)
    if abs_pct <= green:
        return "🟢 GREEN"
    if abs_pct <= amber:
        return "🟡 AMBER"
    return "🔴 RED"


def build_difference_summary(
    doc_items: list[dict],
    green_threshold: float = DEFAULT_GREEN_THRESHOLD,
    amber_threshold: float = DEFAULT_AMBER_THRESHOLD,
) -> dict:
    """Build colour-coded difference summary from document item records."""
    summary = []
    green_count = amber_count = red_count = 0

    for item in doc_items:
        booked = _safe_float(item.get("BookQuantity") or item.get("bookQuantity"))
        counted = _safe_float(item.get("CountedQuantity") or item.get("countedQuantity"))
        product = item.get("Product") or item.get("product", "")
        warehouse = item.get("WarehouseNumber") or item.get("warehouseNumber", "")
        doc_num = item.get("InventoryDocument") or item.get("inventoryDocument", "")
        item_num = item.get("InventoryDocumentItem") or item.get("inventoryDocumentItem", "")
        uom = item.get("QuantityInBaseUnit") or item.get("quantityInBaseUnit", "")

        if booked is not None and counted is not None:
            diff = counted - booked
            diff_pct = (abs(diff) / booked * 100) if booked != 0 else None
            ref_note = "No reference quantity" if booked == 0 else None
        else:
            diff = None
            diff_pct = None
            ref_note = "Missing quantity data"

        classification = _classify_difference(diff_pct, green_threshold, amber_threshold)

        if "GREEN" in classification:
            green_count += 1
        elif "AMBER" in classification:
            amber_count += 1
        else:
            red_count += 1

        label = "Requires Recount" if "RED" in classification else ""

        summary.append({
            "inventory_document": doc_num,
            "item": item_num,
            "product": product,
            "warehouse": warehouse,
            "booked_qty": booked,
            "counted_qty": counted,
            "difference": diff,
            "diff_pct": round(diff_pct, 2) if diff_pct is not None else None,
            "uom": uom,
            "classification": classification,
            "recount_required": "RED" in classification,
            "label": label,
            "note": ref_note,
        })

    return {
        "summary": summary,
        "green_count": green_count,
        "amber_count": amber_count,
        "red_count": red_count,
        "total_items": len(summary),
        "thresholds_used": {
            "green_pct": green_threshold,
            "amber_pct": amber_threshold,
            "description": f"Green ≤ {green_threshold}%, Amber {green_threshold}–{amber_threshold}%, Red > {amber_threshold}%",
        },
    }


def _safe_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


@tool
def query_stock_difference_summary(
    warehouse: str,
    inventory_documents: str = "",
    green_threshold: float = DEFAULT_GREEN_THRESHOLD,
    amber_threshold: float = DEFAULT_AMBER_THRESHOLD,
) -> str:
    """Query counted vs. booked stock for physical inventory documents in 'counted' status.

    Retrieves document items, computes differences, and classifies each as Green/Amber/Red.
    - 🟢 GREEN: difference within tolerance (default ≤ 2%)
    - 🟡 AMBER: approaching tolerance (default 2–5%) — review recommended
    - 🔴 RED: exceeds tolerance (default > 5%) — Requires Recount

    Red items are excluded from posting by default.
    Supervisor can override thresholds by specifying values in their request.

    IMPORTANT: This is a READ-ONLY tool. It does NOT post or modify any data.

    Args:
        warehouse: EWM warehouse number. Use 'ALL' for all warehouses.
        inventory_documents: Comma-separated document numbers to filter (optional).
                             Leave empty to retrieve all documents in 'counted' status.
        green_threshold: Percentage threshold for Green classification (default 2.0).
        amber_threshold: Percentage threshold for Amber classification (default 5.0).

    Returns:
        Colour-coded difference summary with item-level detail and counts by classification.
        Table: Doc # | Product | Warehouse | Booked Qty | Counted Qty | Difference | Diff % | Classification
        Always include the threshold values used in the response.
    """
    doc_filter = ""
    if inventory_documents.strip():
        doc_filter = f" filtered to documents: {inventory_documents}"

    return (
        f"Query: warehouse={warehouse}{doc_filter}, green_threshold={green_threshold}%, amber_threshold={amber_threshold}%. "
        "Step 1: Call list_WarehousePhysicalInventoryDoc MCP tool with $filter "
        f"InventoryDocumentStatus eq 'COUNTED' and WarehouseNumber eq '{warehouse}', $top=100. "
        "Step 2: For each document, call get_WarehousePhysicalInventoryDocItem with $filter on "
        "InventoryDocument, retrieve BookQuantity, CountedQuantity, Product, StorageBin. "
        "Step 3: Compute difference = CountedQuantity - BookQuantity. "
        "Step 4: Compute diff_pct = abs(difference)/BookQuantity*100. "
        "If BookQuantity=0, label as 'No reference quantity', classify as Amber. "
        f"Step 5: Classify: Green ≤ {green_threshold}%, Amber {green_threshold}–{amber_threshold}%, Red > {amber_threshold}%. "
        "Step 6: Label Red items as '🔴 Requires Recount'. "
        "Step 7: Return colour-coded table + summary counts + thresholds used. "
        "Log M4 milestone. Always state the thresholds used in your response."
    )

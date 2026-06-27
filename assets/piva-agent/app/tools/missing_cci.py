"""
Tool: query_missing_cci_products
REQ-02: Identify EWM products with missing Cycle Counting Indicators in product master.
"""
import logging
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def build_missing_cci_result(raw_records: list[dict]) -> dict:
    """Filter records to those with null/empty CycleCountingIndicator."""
    missing = []
    for rec in raw_records:
        cci = rec.get("CycleCountingIndicator") or rec.get("cycleCountingIndicator")
        if not cci or str(cci).strip() == "":
            missing.append({
                "product": rec.get("Product") or rec.get("product", ""),
                "warehouse": rec.get("WarehouseNumber") or rec.get("warehouseNumber", ""),
                "last_count_date": rec.get("LastPhysicalInventoryDate") or rec.get("lastPhysicalInventoryDate") or "Never",
                "recommendation": "Set Cycle Counting Indicator in EWM product master (EWM warehouse view) before next inventory cycle.",
            })
    return {
        "missing_cci_products": missing,
        "count": len(missing),
        "advisory": (
            "These products require a Cycle Counting Indicator to be set in EWM product master "
            "before the next inventory cycle. Please update the EWM warehouse view for each product."
        ),
    }


@tool
def query_missing_cci_products(warehouse: str, warehouses: str = "") -> str:
    """Query EWM product master to find products with missing Cycle Counting Indicators.

    Products without a CCI set cannot be included in cycle counting schedules and
    will cause process failures if included in physical inventory.

    IMPORTANT: This is a READ-ONLY tool. It does NOT modify any EWM data.

    Args:
        warehouse: Single EWM warehouse number (e.g. '0001').
        warehouses: Comma-separated list of warehouse numbers for multi-warehouse queries.
                    If provided, overrides the warehouse parameter.

    Returns:
        List of products with missing CCIs, count, and advisory message.
        Use this to present a table: Product | Warehouse | Last Count Date | Recommendation
    """
    return (
        f"Query parameters: warehouse={warehouse}, warehouses={warehouses}. "
        "Call list_ProductEWMWarehouse MCP tool with $filter on WarehouseNumber, $top=100. "
        "Filter the results to products where CycleCountingIndicator is null, empty, or not set. "
        "Return as a clear table with advisory: 'These products require a Cycle Counting Indicator "
        "to be set in EWM product master before the next inventory cycle.' "
        "Clearly distinguish these from overdue products — these are master data gaps, not scheduling issues."
    )

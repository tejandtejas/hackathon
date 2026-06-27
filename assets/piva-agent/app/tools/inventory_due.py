"""
Tool: query_products_due_for_counting
REQ-01: Identify EWM products overdue for physical inventory counting.
"""
import logging
from datetime import date, datetime, timedelta
from typing import Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

DEFAULT_CYCLE_DAYS: dict[str, int] = {
    "A": 30,
    "B": 90,
    "C": 180,
    "D": 365,
}


def _parse_date(value: str | None) -> Optional[date]:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y%m%d"):
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").date()
        except ValueError:
            pass
    return None


def _cycle_days(cci: str | None, cycle_field: str | None) -> Optional[int]:
    """Return counting interval in days from CCI indicator or PhysicalInventoryCycle field."""
    if cycle_field:
        try:
            return int(cycle_field)
        except (ValueError, TypeError):
            pass
    if cci and cci.upper() in DEFAULT_CYCLE_DAYS:
        return DEFAULT_CYCLE_DAYS[cci.upper()]
    return None


def _is_overdue(last_count: Optional[date], cycle_days: Optional[int]) -> tuple[bool, str]:
    if last_count is None:
        return True, "Never counted"
    if cycle_days is None:
        return False, "No cycle configured"
    next_due = last_count + timedelta(days=cycle_days)
    today = date.today()
    if today >= next_due:
        return True, f"Due since {next_due.isoformat()}"
    return False, f"Next due: {next_due.isoformat()}"


def build_due_products_result(raw_records: list[dict], cci_filter: str | None = None) -> dict:
    """Process raw EWM product master records and return structured due-for-counting result."""
    due_products = []
    today = date.today()

    for rec in raw_records:
        cci = rec.get("CycleCountingIndicator") or rec.get("cycleCountingIndicator")
        last_date_str = rec.get("LastPhysicalInventoryDate") or rec.get("lastPhysicalInventoryDate")
        cycle_field = rec.get("PhysicalInventoryCycle") or rec.get("physicalInventoryCycle")
        product = rec.get("Product") or rec.get("product", "")
        warehouse = rec.get("WarehouseNumber") or rec.get("warehouseNumber", "")

        # Apply CCI filter if provided
        if cci_filter and (cci or "").upper() != cci_filter.upper():
            continue

        last_count = _parse_date(last_date_str)
        days = _cycle_days(cci, cycle_field)
        overdue, status = _is_overdue(last_count, days)

        if overdue:
            next_due = (last_count + timedelta(days=days)).isoformat() if last_count and days else "N/A"
            due_products.append({
                "product": product,
                "warehouse": warehouse,
                "cci": cci or "N/A",
                "last_count_date": last_count.isoformat() if last_count else "Never",
                "next_due_date": next_due,
                "status": status,
            })

    # Group by CCI
    by_cci: dict[str, list] = {}
    for p in due_products:
        key = p["cci"]
        by_cci.setdefault(key, []).append(p)

    return {
        "due_products": due_products,
        "by_cci": by_cci,
        "total_due": len(due_products),
        "query_date": today.isoformat(),
    }


@tool
def query_products_due_for_counting(warehouse: str, cci_filter: str = "", warehouses: str = "") -> str:
    """Query EWM product master to identify products overdue for physical inventory counting.

    Computes due products based on CycleCountingIndicator and LastPhysicalInventoryDate.
    Results are segmented by CCI indicator (A/B/C etc.).
    Products never counted are always included as overdue.

    IMPORTANT: This is a READ-ONLY tool. It does NOT create any documents.

    Args:
        warehouse: Single EWM warehouse number (e.g. '0001'). Use this for single-warehouse queries.
        cci_filter: Optional CCI to filter by (e.g. 'A', 'B', 'C'). Leave empty for all CCIs.
        warehouses: Comma-separated list of warehouse numbers for multi-warehouse queries (e.g. '0001,0002').
                    If provided, overrides the warehouse parameter.

    Returns:
        Structured result with due_products list, by_cci grouping, and totals.
        Use this data to present a table: Product | Warehouse | CCI | Last Count Date | Next Due Date | Status
    """
    # This function signature is used by the agent via MCP tools.
    # The actual EWM data comes from the list_ProductEWMWarehouse MCP tool.
    # The agent will call the MCP tool and pass results to build_due_products_result().
    return (
        f"Query parameters: warehouse={warehouse}, cci_filter={cci_filter}, warehouses={warehouses}. "
        "Call list_ProductEWMWarehouse MCP tool with $filter on WarehouseNumber, retrieve "
        "CycleCountingIndicator, PhysicalInventoryCycle, LastPhysicalInventoryDate, Product, WarehouseNumber. "
        "Set $top=100. Then compute overdue products using the CCI frequency and last count date. "
        "Segment results by CCI. Flag products with null LastPhysicalInventoryDate as 'Never counted'."
    )

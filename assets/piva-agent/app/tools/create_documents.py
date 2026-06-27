"""
Tool: create_physical_inventory_documents
REQ-03: Create EWM physical inventory documents for identified products.
WRITE OPERATION — requires prior explicit user confirmation.
"""
import logging
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

CONFIRMATION_KEYWORDS = {
    "yes", "confirm", "proceed", "ok", "go ahead", "do it", "create",
    "approved", "approve", "sure", "affirmative", "correct", "please create",
    "yes please", "yes create", "create them", "go", "yep", "yeah",
}


def _requires_confirmation(user_message: str) -> bool:
    """Return True if the user message contains explicit confirmation keywords."""
    msg_lower = user_message.lower().strip()
    for kw in CONFIRMATION_KEYWORDS:
        if kw in msg_lower:
            return True
    return False


def build_creation_result(created: list[dict], failed: list[dict]) -> dict:
    """Structure the document creation outcome."""
    return {
        "created": created,
        "failed": failed,
        "created_count": len(created),
        "failed_count": len(failed),
    }


@tool
def create_physical_inventory_documents(
    products: str,
    warehouse: str,
    confirmed: str = "no",
) -> str:
    """Create EWM physical inventory documents for identified products.

    WRITE OPERATION — requires prior user confirmation.
    NEVER call this tool without first presenting the list of products to the user
    and receiving an explicit confirmation (yes/confirm/proceed).

    If confirmed is not 'yes', return a confirmation request — do NOT proceed.

    Args:
        products: Comma-separated product numbers to create documents for (e.g. 'MAT-001,MAT-002').
        warehouse: EWM warehouse number (e.g. '0001').
        confirmed: Must be 'yes' to proceed. Any other value returns a confirmation prompt.

    Returns:
        If confirmed: result with created document numbers and any failures.
        If not confirmed: a prompt asking the supervisor to confirm before proceeding.

    Side effects:
        WRITE — Creates physical inventory documents in EWM (irreversible).
    """
    if confirmed.lower().strip() not in ("yes", "true", "1", "confirmed"):
        product_list = [p.strip() for p in products.split(",") if p.strip()]
        return (
            f"I will create {len(product_list)} physical inventory document(s) for the following "
            f"products in warehouse {warehouse}:\n"
            + "\n".join(f"  - {p}" for p in product_list)
            + "\n\nPlease confirm to proceed (reply 'yes' or 'confirm')."
        )

    product_list = [p.strip() for p in products.split(",") if p.strip()]
    return (
        f"CONFIRMED. Create physical inventory documents for {len(product_list)} product(s) "
        f"in warehouse {warehouse}: {product_list}. "
        "For each product, call create_WarehousePhysicalInventoryDoc MCP tool with WarehouseNumber "
        "and Product fields. Collect all created document numbers and fiscal years. "
        "Report partial failures clearly. Log M2 milestone on completion."
    )

"""
Tool: post_inventory_differences
REQ-05: Post approved stock differences to EWM after human-in-the-loop confirmation.
WRITE / HIGH-RISK OPERATION — requires prior explicit user confirmation.
REQ-07: Red-classified items excluded from default posting scope.
"""
import logging
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def post_inventory_differences(
    documents_to_post: str,
    warehouse: str,
    excluded_items: str = "",
    confirmed: str = "no",
    include_red_items: str = "no",
) -> str:
    """Post stock differences for approved physical inventory document items to EWM.

    WRITE / HIGH-RISK OPERATION — irreversible. Only call after explicit supervisor confirmation.

    Red-classified items (Requires Recount) are EXCLUDED by default.
    Supervisor must explicitly set include_red_items='yes' to include them (and re-confirm).

    Workflow:
    1. Present posting summary to supervisor including excluded Red items.
    2. Wait for supervisor confirmation.
    3. Call post_PhysicalInventoryDifference MCP tool per document for included items only.
    4. Report per-document outcome.

    Args:
        documents_to_post: Comma-separated document numbers approved for posting
                           (format: 'DOC001,DOC002').
        warehouse: EWM warehouse number.
        excluded_items: Comma-separated document item IDs to exclude from posting
                        (format: 'DOC001-001,DOC001-002').
        confirmed: Must be 'yes' to proceed. Any other value returns a confirmation prompt.
        include_red_items: Set to 'yes' only if supervisor explicitly requested Red items be included.

    Returns:
        If not confirmed: pre-posting summary with confirmation request.
        If confirmed: per-document posting outcome (posted/failed/excluded).

    Side effects:
        WRITE — Posts stock difference adjustments to EWM (irreversible action).
    """
    doc_list = [d.strip() for d in documents_to_post.split(",") if d.strip()]
    excluded_list = [e.strip() for e in excluded_items.split(",") if e.strip()]
    red_note = (
        " Red-classified (Requires Recount) items are included per supervisor request."
        if include_red_items.lower() == "yes"
        else " Red-classified (Requires Recount) items are EXCLUDED from posting by default."
    )

    if confirmed.lower().strip() not in ("yes", "true", "1", "confirmed"):
        exclusion_note = (
            f"\nExcluded items: {excluded_list}" if excluded_list else "\nNo additional exclusions specified."
        )
        return (
            f"I will post differences for {len(doc_list)} document(s) in warehouse {warehouse}:\n"
            + "\n".join(f"  - {d}" for d in doc_list)
            + exclusion_note
            + red_note
            + "\n\nPlease confirm to proceed (reply 'yes' or 'confirm'), "
            "or specify any items to exclude before confirming."
        )

    return (
        f"CONFIRMED. Post differences for {len(doc_list)} document(s) in warehouse {warehouse}. "
        f"Excluded items: {excluded_list}. Include red items: {include_red_items}. "
        "For each document in documents_to_post, call post_PhysicalInventoryDifference MCP tool "
        "passing InventoryDocument and FiscalYear. Omit any items in excluded_items from the Items array. "
        "Collect per-document outcome (posted/failed). "
        "Present result table: Document # | Product | Booked Qty | Counted Qty | Difference | Post Status. "
        "Log M5 milestone with posted_count, excluded_count, failed_count."
    )

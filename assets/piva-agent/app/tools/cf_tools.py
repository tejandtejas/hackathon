"""CF-runtime direct-API tools for PIVA agent.

These LangChain tools call SAP EWM OData services directly via the BTP
destination (s4_client) instead of routing through the Agent Gateway MCP.
Used on Cloud Foundry. On Joule, the MCP-instruction tools in ALL_TOOLS are used.

Service roots:
  PRODUCT_ROOT  -- OP_PRODUCT_0002: /_ProductEWMWarehouse
  INVDOC_ROOT   -- OP_WHSEPHYSICALINVENTORYDOC_0001: /WarehousePhysicalInventoryDoc
"""
from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from tools.inventory_due import build_due_products_result
from tools.missing_cci import build_missing_cci_result
from tools.stock_difference import build_difference_summary
from tools.document_status import build_status_summary

logger = logging.getLogger(__name__)

PRODUCT_ROOT = "/_ProductEWMWarehouse"
INVDOC_ROOT = "/WarehousePhysicalInventoryDoc"
INVDOC_ITEM_ROOT = "/WarehousePhysicalInventoryDocItem"
MAX_PAGE_SIZE = 100

CONFIRMATION_KEYWORDS = frozenset({
    "yes", "confirm", "proceed", "ok", "go ahead", "do it", "create",
    "approved", "approve", "sure", "affirmative", "correct", "please create",
    "yes please", "yes create", "create them", "go", "yep", "yeah",
})


def _enforce_page_size(params: dict, key: str = "$top") -> dict:
    if key not in params or params[key] > MAX_PAGE_SIZE:
        params[key] = MAX_PAGE_SIZE
    return params


def _ensure_format(params: dict) -> dict:
    if "$format" not in params:
        params["$format"] = "json"
    return params


def _results(body: Any) -> list:
    """Unwrap OData v2 results list from body."""
    if isinstance(body, dict):
        return body.get("results", [])
    if isinstance(body, list):
        return body
    return []


# ---------------------------------------------------------------------------
# Tool 1: Query products due for counting
# ---------------------------------------------------------------------------

class DueProductsInput(BaseModel):
    warehouse: str = Field(description="EWM warehouse number, e.g. 0001")
    cci_filter: str = Field(default="", description="Optional CCI indicator to filter by (A/B/C)")
    warehouses: str = Field(default="", description="Comma-separated warehouses for multi-warehouse query")


async def _query_products_due_for_counting_cf(
    warehouse: str,
    cci_filter: str = "",
    warehouses: str = "",
    _client: Any = None,
) -> str:
    wh_list = [w.strip() for w in warehouses.split(",") if w.strip()] if warehouses.strip() else [warehouse]
    all_records = []
    for wh in wh_list:
        flt = f"WarehouseNumber eq '{wh}'"
        if cci_filter.strip():
            flt += f" and CycleCountingIndicator eq '{cci_filter.strip()}'"
        params = {
            "$filter": flt,
            "$select": "Product,WarehouseNumber,CycleCountingIndicator,PhysicalInventoryCycle,LastPhysicalInventoryDate",
        }
        _enforce_page_size(params)
        _ensure_format(params)
        body = await _client.get(PRODUCT_ROOT, params=params)
        if isinstance(body, dict) and body.get("error"):
            return json.dumps({"error": body.get("message", "API error")})
        all_records.extend(_results(body))
    result = build_due_products_result(all_records, cci_filter.strip() or None)
    return json.dumps(result)


# ---------------------------------------------------------------------------
# Tool 2: Query missing CCI products
# ---------------------------------------------------------------------------

class MissingCciInput(BaseModel):
    warehouse: str = Field(description="EWM warehouse number")
    warehouses: str = Field(default="", description="Comma-separated warehouses for multi-warehouse query")


async def _query_missing_cci_cf(
    warehouse: str,
    warehouses: str = "",
    _client: Any = None,
) -> str:
    wh_list = [w.strip() for w in warehouses.split(",") if w.strip()] if warehouses.strip() else [warehouse]
    all_records = []
    for wh in wh_list:
        params = {
            "$filter": f"WarehouseNumber eq '{wh}'",
            "$select": "Product,WarehouseNumber,CycleCountingIndicator,LastPhysicalInventoryDate",
        }
        _enforce_page_size(params)
        _ensure_format(params)
        body = await _client.get(PRODUCT_ROOT, params=params)
        if isinstance(body, dict) and body.get("error"):
            return json.dumps({"error": body.get("message", "API error")})
        all_records.extend(_results(body))
    result = build_missing_cci_result(all_records)
    return json.dumps(result)


# ---------------------------------------------------------------------------
# Tool 3: Create physical inventory documents (WRITE)
# ---------------------------------------------------------------------------

class CreateDocumentsInput(BaseModel):
    products: str = Field(description="Comma-separated product numbers")
    warehouse: str = Field(description="EWM warehouse number")
    confirmed: str = Field(default="no", description="Must be yes to proceed")


async def _create_physical_inventory_documents_cf(
    products: str,
    warehouse: str,
    confirmed: str = "no",
    _client: Any = None,
) -> str:
    if confirmed.lower().strip() not in ("yes", "true", "1", "confirmed"):
        product_list = [p.strip() for p in products.split(",") if p.strip()]
        return (
            f"I will create {len(product_list)} physical inventory document(s) for the following "
            f"products in warehouse {warehouse}:\n"
            + "\n".join(f"  - {p}" for p in product_list)
            + "\n\nPlease confirm to proceed (reply yes or confirm)."
        )
    product_list = [p.strip() for p in products.split(",") if p.strip()]
    created = []
    failed = []
    for product in product_list:
        body_payload = {"WarehouseNumber": warehouse, "Product": product}
        result = await _client.post(INVDOC_ROOT, body_payload, service_root=INVDOC_ROOT)
        if isinstance(result, dict) and result.get("error"):
            failed.append({"product": product, "error": result.get("message", "POST failed")})
        else:
            doc_num = result.get("InventoryDocument", "") if isinstance(result, dict) else ""
            fiscal_year = result.get("FiscalYear", "") if isinstance(result, dict) else ""
            created.append({"product": product, "document": doc_num, "fiscal_year": fiscal_year})
    return json.dumps({"created": created, "failed": failed,
                       "created_count": len(created), "failed_count": len(failed)})


# ---------------------------------------------------------------------------
# Tool 4: Query stock difference summary
# ---------------------------------------------------------------------------

class StockDifferenceInput(BaseModel):
    warehouse: str = Field(description="EWM warehouse number or ALL")
    inventory_documents: str = Field(default="", description="Comma-separated document numbers")
    green_threshold: float = Field(default=2.0, description="Green classification threshold %")
    amber_threshold: float = Field(default=5.0, description="Amber classification threshold %")


async def _query_stock_difference_summary_cf(
    warehouse: str,
    inventory_documents: str = "",
    green_threshold: float = 2.0,
    amber_threshold: float = 5.0,
    _client: Any = None,
) -> str:
    flt = "InventoryDocumentStatus eq 'COUNTED'"
    if warehouse.upper() != "ALL":
        flt += f" and WarehouseNumber eq '{warehouse}'"
    if inventory_documents.strip():
        doc_list = [d.strip() for d in inventory_documents.split(",") if d.strip()]
        if len(doc_list) == 1:
            flt += f" and InventoryDocument eq '{doc_list[0]}'"
    params = {"$filter": flt, "$select": "InventoryDocument,FiscalYear,WarehouseNumber,InventoryDocumentStatus"}
    _enforce_page_size(params)
    _ensure_format(params)
    doc_body = await _client.get(INVDOC_ROOT, params=params)
    if isinstance(doc_body, dict) and doc_body.get("error"):
        return json.dumps({"error": doc_body.get("message", "API error")})
    docs = _results(doc_body)
    all_items = []
    for doc in docs:
        doc_num = doc.get("InventoryDocument", "")
        fy = doc.get("FiscalYear", "")
        item_params = {
            "$filter": f"InventoryDocument eq '{doc_num}' and FiscalYear eq '{fy}'",
            "$select": "InventoryDocument,FiscalYear,InventoryDocumentItem,Product,WarehouseNumber,StorageBin,BookQuantity,CountedQuantity,QuantityInBaseUnit",
        }
        _enforce_page_size(item_params)
        _ensure_format(item_params)
        item_body = await _client.get(INVDOC_ITEM_ROOT, params=item_params)
        if isinstance(item_body, dict) and item_body.get("error"):
            logger.warning("Error fetching items for doc %s: %s", doc_num, item_body.get("message"))
            continue
        all_items.extend(_results(item_body))
    result = build_difference_summary(all_items, green_threshold, amber_threshold)
    return json.dumps(result)


# ---------------------------------------------------------------------------
# Tool 5: Post inventory differences (WRITE)
# ---------------------------------------------------------------------------

class PostDifferencesInput(BaseModel):
    documents_to_post: str = Field(description="Comma-separated document numbers to post")
    warehouse: str = Field(description="EWM warehouse number")
    excluded_items: str = Field(default="", description="Comma-separated item IDs to exclude")
    confirmed: str = Field(default="no", description="Must be yes to proceed")
    include_red_items: str = Field(default="no", description="Include red-classified items")


async def _post_inventory_differences_cf(
    documents_to_post: str,
    warehouse: str,
    excluded_items: str = "",
    confirmed: str = "no",
    include_red_items: str = "no",
    _client: Any = None,
) -> str:
    doc_list = [d.strip() for d in documents_to_post.split(",") if d.strip()]
    excluded_list = [e.strip() for e in excluded_items.split(",") if e.strip()]
    red_note = (
        " Red-classified items included per supervisor request."
        if include_red_items.lower() == "yes"
        else " Red-classified items EXCLUDED from posting."
    )
    if confirmed.lower().strip() not in ("yes", "true", "1", "confirmed"):
        return (
            f"I will post differences for {len(doc_list)} document(s) in warehouse {warehouse}:\n"
            + "\n".join(f"  - {d}" for d in doc_list)
            + (f"\nExcluded items: {excluded_list}" if excluded_list else "\nNo additional exclusions.")
            + red_note
            + "\n\nPlease confirm to proceed (reply yes or confirm)."
        )
    posted = []
    failed = []
    for doc_num in doc_list:
        fy = doc_num.split("-")[1] if "-" in doc_num else str(__import__("datetime").date.today().year)
        items_to_post = [i for i in excluded_list if not i.startswith(doc_num)]
        payload = {"InventoryDocument": doc_num, "FiscalYear": fy}
        if items_to_post:
            payload["Items"] = [{"InventoryDocumentItem": i.split("-")[-1]} for i in items_to_post]
        svc_path = f"{INVDOC_ROOT}(InventoryDocument='{doc_num}',FiscalYear='{fy}')/PostDifference"
        result = await _client.post(svc_path, payload, service_root=INVDOC_ROOT)
        if isinstance(result, dict) and result.get("error"):
            failed.append({"document": doc_num, "error": result.get("message", "POST failed")})
        else:
            posted.append({"document": doc_num, "status": "posted"})
    return json.dumps({
        "posted": posted, "failed": failed, "excluded": excluded_list,
        "posted_count": len(posted), "failed_count": len(failed),
        "excluded_count": len(excluded_list),
    })


# ---------------------------------------------------------------------------
# Tool 6: Query document status summary
# ---------------------------------------------------------------------------

class DocumentStatusInput(BaseModel):
    warehouse: str = Field(description="EWM warehouse number")
    warehouses: str = Field(default="", description="Comma-separated warehouses for multi-warehouse summary")


async def _query_document_status_summary_cf(
    warehouse: str,
    warehouses: str = "",
    _client: Any = None,
) -> str:
    wh_list = [w.strip() for w in warehouses.split(",") if w.strip()] if warehouses.strip() else [warehouse]
    all_docs = []
    for wh in wh_list:
        params = {
            "$filter": f"WarehouseNumber eq '{wh}'",
            "$select": "InventoryDocument,FiscalYear,WarehouseNumber,InventoryDocumentStatus",
        }
        _enforce_page_size(params)
        _ensure_format(params)
        body = await _client.get(INVDOC_ROOT, params=params)
        if isinstance(body, dict) and body.get("error"):
            return json.dumps({"error": body.get("message", "API error")})
        all_docs.extend(_results(body))
    result = build_status_summary(all_docs)
    return json.dumps(result)


# ---------------------------------------------------------------------------
# Builder: returns all 6 CF tools with client closed over
# ---------------------------------------------------------------------------

def build_cf_tools(client: Any) -> list:
    """Build CF-runtime direct-API LangChain tools with client closed over."""

    def _make(name: str, desc: str, fn, schema):
        # functools.partial of an async fn is NOT recognised as a coroutine function
        # by asyncio.iscoroutinefunction(), so LangChain rejects it.
        # Use a proper async wrapper closure instead.
        async def _bound(**kwargs):
            return await fn(_client=client, **kwargs)

        _bound.__name__ = name
        return StructuredTool(
            name=name,
            description=desc,
            args_schema=schema,
            coroutine=_bound,
            handle_tool_error=True,
        )

    return [
        _make(
            "query_products_due_for_counting",
            "Query EWM product master to identify products overdue for physical inventory counting. "
            "Segments results by CCI indicator (A/B/C). READ-ONLY.",
            _query_products_due_for_counting_cf,
            DueProductsInput,
        ),
        _make(
            "query_missing_cci_products",
            "Find EWM products with missing Cycle Counting Indicators in product master. READ-ONLY.",
            _query_missing_cci_cf,
            MissingCciInput,
        ),
        _make(
            "create_physical_inventory_documents",
            "Create EWM physical inventory documents for identified products. "
            "WRITE operation -- requires confirmed=yes. Never call without explicit user confirmation.",
            _create_physical_inventory_documents_cf,
            CreateDocumentsInput,
        ),
        _make(
            "query_stock_difference_summary",
            "Query counted vs booked stock for physical inventory documents in counted status. "
            "Classifies items as Green/Amber/Red. READ-ONLY.",
            _query_stock_difference_summary_cf,
            StockDifferenceInput,
        ),
        _make(
            "post_inventory_differences",
            "Post stock differences for approved physical inventory documents. "
            "WRITE/HIGH-RISK -- requires confirmed=yes. Red items excluded by default.",
            _post_inventory_differences_cf,
            PostDifferencesInput,
        ),
        _make(
            "query_document_status_summary",
            "Get summary of physical inventory documents grouped by status for one or more warehouses. READ-ONLY.",
            _query_document_status_summary_cf,
            DocumentStatusInput,
        ),
    ]

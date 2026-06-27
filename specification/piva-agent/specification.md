# Specification: piva-agent

> **Guidelines**: Read [../guidelines.md](../guidelines.md) and [../guidelines-agent.md](../guidelines-agent.md) before executing ANY tasks below. Follow all constraints described there throughout execution.

## Basic Setup

- [x] Read `product-requirements-document.md` and `intent.md` for full context before starting
- [x] Bootstrap agent code in `assets/piva-agent/` using skill `sap-agent-bootstrap` (invoke from inside `assets/piva-agent/`, use copy commands — do NOT create files manually)
- [x] Install dependencies: `pip install -r requirements.txt -r requirements-test.txt` from `assets/piva-agent/`
- [x] Validate the agent starts and responds at `/.well-known/agent.json`

## MCP Server Wiring (Path B — Existing On-Premise MCP Servers)

Both MCP servers are customer-deployed on-premise servers with known identifiers. No API spec download or MCP translation is needed. Wire them as external MCP server dependencies.

- [x] Register both MCP servers as `requires` entries in `assets/piva-agent/asset.yaml`
- [x] Wire MCP tool loading in `assets/piva-agent/app/agent.py` using `get_mcp_tools()` from `mcp_tools` module (canonical pattern from guidelines-agent.md) — NEVER create direct HTTP clients for SAP APIs
- [x] Load tools lazily in `_get_tools()` — not in `__init__`
- [x] Generate `mcp-mock.json` using the `mcp-mock-config` skill, using the MCP spec files at `specification/piva-agent/mcp-specs/` as input

## Agent Identity & System Prompt

- [x] Set agent name: `piva-agent` and description: `Physical Inventory Verification Agent — EWM physical inventory cycle orchestration via natural language`
- [x] Write system prompt in `get_system_prompt()` covering:
  - PIVA is an AI agent for EWM physical inventory verification embedded in SAP Joule
  - It serves warehouse supervisors and managers via natural language
  - **Read-only tools**: never call create/post tools without an explicit user confirmation in the same conversation turn
  - Always set `$top` to a maximum of 100 on every MCP tool call that accepts it; inform user if results are limited
  - CCI due-date logic: compute overdue products by comparing `LastPhysicalInventoryDate + PhysicalInventoryCycle` against today's date
  - Difference classification thresholds: Green = within tolerance, Amber = approaching (80–100% of tolerance), Red = exceeds tolerance (default tolerances provided at runtime or by supervisor override)
  - Red-classified lines are excluded from default posting scope; supervisor must explicitly request their inclusion
  - Never modify EWM product master data — only report missing CCIs
  - Never retry write operations (document creation, difference posting) automatically on failure
  - Session threshold overrides do not persist across conversations
  - Segment all "due for counting" results by CCI indicator (A/B/C etc.)
  - Always distinguish missing-CCI products from overdue products in results

## REQ-01: Products Due for Physical Inventory

- [x] Implement tool `query_products_due_for_counting(warehouse: str, cci_filter: str | None, warehouses: list[str] | None)`:
  - Calls `list_ProductEWMWarehouse` MCP tool with `$filter` on `WarehouseNumber` (single or multiple)
  - Retrieves `Product`, `WarehouseNumber`, `CycleCountingIndicator`, `PhysicalInventoryCycle`, `LastPhysicalInventoryDate`
  - Computes next due date: `LastPhysicalInventoryDate + PhysicalInventoryCycle` (in days)
  - Filters to products where `next_due_date <= today`
  - Optionally filters by CCI if `cci_filter` is provided (e.g. A, B, C)
  - Segments results by CCI indicator
  - Handles products with `LastPhysicalInventoryDate` as null — flags as "Never counted"
  - Returns structured result: `{ "due_products": [...], "by_cci": {"A": [...], "B": [...], ...}, "warehouse": ... }`
- [x] Support multi-warehouse aggregation: if `warehouses` list provided, call MCP tool once per warehouse and merge results
- [x] Format response as a business-friendly table: Product | Warehouse | CCI | Last Count Date | Next Due Date | Status

## REQ-02: Missing Cycle Counting Indicator Report

- [x] Implement tool `query_missing_cci_products(warehouse: str, warehouses: list[str] | None)`:
  - Calls `list_ProductEWMWarehouse` MCP tool with `$filter` on `WarehouseNumber`
  - Filters products where `CycleCountingIndicator` is null, empty, or not set
  - Returns list of products with missing CCI: `{ "missing_cci_products": [...], "warehouse": ..., "count": ... }`
- [x] Response clearly distinguishes missing-CCI products from due-for-counting products
- [x] Format as table: Product | Warehouse | Last Count Date | Recommendation (Set CCI before next count cycle)
- [x] Include advisory message: "These products require a Cycle Counting Indicator to be set in EWM product master before the next inventory cycle."

## REQ-03: Physical Inventory Document Creation (Human-in-the-Loop)

- [x] Implement tool `create_physical_inventory_documents(products: list[dict], warehouse: str)`:
  - **WRITE operation** — must only be invoked after receiving explicit user confirmation ("yes", "confirm", "proceed", or equivalent) in the same conversation turn
  - Calls `create_WarehousePhysicalInventoryDoc` MCP tool once per product
  - Collects created document numbers and fiscal years
  - Handles partial failures: if any document creation fails, reports failure per product with error reason
  - Returns: `{ "created": [{"product": ..., "document": ..., "fiscal_year": ...}], "failed": [{"product": ..., "reason": ...}] }`
- [x] Agent must present a confirmation prompt before invoking this tool: "I will create [N] physical inventory documents for the following products in warehouse [X]: [list]. Please confirm to proceed."
- [x] After creation, display: Document Number | Product | Warehouse | Status | Fiscal Year
- [x] Log milestone M2 on success/failure

## REQ-04: Counted vs. Booked Stock Comparison with Colour-Coded Differences

- [x] Implement tool `query_stock_difference_summary(warehouse: str, inventory_documents: list[str] | None, green_threshold: float | None, amber_threshold: float | None)`:
  - Calls `list_WarehousePhysicalInventoryDoc` MCP tool filtered by `InventoryDocumentStatus eq 'COUNTED'` and warehouse
  - For each document, calls `get_WarehousePhysicalInventoryDocItem` to retrieve item-level counted and booked quantities
  - Computes difference quantity: `CountedQuantity - BookQuantity`
  - Computes difference %: `abs(difference) / BookQuantity * 100` (handle zero BookQuantity gracefully — flag as "Uncountable reference")
  - Classifies each item:
    - Green: `abs(diff_pct) <= green_threshold` (within tolerance)
    - Amber: `green_threshold < abs(diff_pct) <= amber_threshold` (approaching tolerance)
    - Red: `abs(diff_pct) > amber_threshold` (exceeds tolerance — requires recount)
  - Default thresholds: `green_threshold=2.0`, `amber_threshold=5.0` (supervisor-overridable at runtime)
  - Returns structured: `{ "summary": [...], "green_count": N, "amber_count": N, "red_count": N, "warehouse": ..., "thresholds_used": {...} }`
- [x] Implement session-level threshold override: if supervisor provides threshold values in natural language ("set tolerance to 3%"), update thresholds for current session
- [x] Always include threshold values used in the response (EWM default or supervisor override)
- [x] Format as colour-coded table: Doc # | Product | Warehouse | Booked Qty | Counted Qty | Difference | Diff % | Classification
- [x] Red items are labelled "🔴 Requires Recount"; Amber: "🟡 Review"; Green: "🟢 Within Tolerance"
- [x] Log milestone M4 on success/failure

## REQ-05: Human-in-the-Loop Difference Posting

- [x] Implement tool `post_inventory_differences(documents_to_post: list[dict], excluded_items: list[str] | None)`:
  - **WRITE / HIGH-RISK operation** — must only be invoked after receiving explicit user confirmation in the same conversation turn
  - Red-classified items are excluded from `documents_to_post` by default unless supervisor explicitly overrides
  - Calls `post_PhysicalInventoryDifference` MCP tool per document, passing only included item numbers
  - Collects per-document outcome (posted / failed)
  - Returns: `{ "posted": [...], "failed": [...], "excluded": [...] }`
- [x] Agent must present pre-posting confirmation: "I will post differences for [N] document items in warehouse [X]. [M] Red items are excluded. Please confirm or specify any additional items to exclude."
- [x] After posting, display: Document # | Product | Booked Qty | Counted Qty | Difference | Post Status
- [x] Log milestone M5 on success/failure

## REQ-06: Inventory Document Status Summary

- [x] Implement tool `query_document_status_summary(warehouse: str, warehouses: list[str] | None)`:
  - Calls `list_WarehousePhysicalInventoryDoc` MCP tool for all statuses
  - Groups results by status: Open / Counted / Posted / Partially Posted
  - Returns counts and document lists per status per warehouse
- [x] Format as summary table: Warehouse | Open | Counted | Posted | Total

## REQ-07: Recount Identification

- [x] In `query_stock_difference_summary`, explicitly label Red-classified items as "Requires Recount"
- [x] In `post_inventory_differences`, Red items are excluded from the default posting list; agent must state: "The following [N] items require recount and are excluded from posting by default: [list]"
- [x] Supervisor can explicitly include Red items by stating "include recount items" or similar — agent must re-confirm before executing

## Milestone Instrumentation

- [x] Instrument all 5 milestones with structured logs and OpenTelemetry spans (extract all business logic from `stream()` into `_run_agent()` helper — never use `with tracer.start_as_current_span(...)` inside a generator):
  - **M1**: `[M1.achieved]: products due for counting identified | warehouse={warehouse} | due_count={count} | missing_cci_count={count}`
  - **M1 miss**: `[M1.missed]: product due identification failed | warehouse={warehouse} | reason={error}`
  - **M2**: `[M2.achieved]: physical inventory documents created | warehouse={warehouse} | document_count={count} | documents={doc_numbers}`
  - **M2 miss**: `[M2.missed]: physical inventory document creation failed | warehouse={warehouse} | reason={error}`
  - **M3**: `[M3.achieved]: inventory documents queued for counting | document_count={count}`
  - **M3 miss**: `[M3.missed]: documents not confirmed in counting queue | reason={error}`
  - **M4**: `[M4.achieved]: counted vs booked comparison delivered | warehouse={warehouse} | documents_reviewed={count} | green={n} | amber={n} | red={n}`
  - **M4 miss**: `[M4.missed]: counted vs booked comparison failed | warehouse={warehouse} | reason={error}`
  - **M5**: `[M5.achieved]: stock differences posted | posted_count={count} | excluded_count={count} | failed_count={count}`
  - **M5 miss**: `[M5.missed]: difference posting failed or not confirmed | reason={error}`
- [x] Verify `auto_instrument()` is called at top of `main.py` before any AI framework imports

## Agent Tools Registration

- [x] Register all tools in `assets/piva-agent/app/tools/` as a package and export via `ALL_TOOLS` list:
  - `query_products_due_for_counting`
  - `query_missing_cci_products`
  - `create_physical_inventory_documents`
  - `query_stock_difference_summary`
  - `post_inventory_differences`
  - `query_document_status_summary`
- [x] Each tool must have a complete docstring describing inputs, outputs, and side effects
- [x] Mark write tools explicitly in docstrings: "WRITE OPERATION — requires prior user confirmation"

## Guardrails & Fail-safes

- [x] Implement confirmation check utility `_requires_confirmation(user_message: str) -> bool` — returns True if message contains confirmation keywords (yes, confirm, proceed, ok, go ahead, etc.)
- [x] `create_physical_inventory_documents` and `post_inventory_differences` must validate confirmation before execution; if not confirmed, return a request for confirmation instead of executing
- [x] If any MCP tool returns an error response, surface the full error to the user and halt the workflow — do not retry write operations
- [x] If `BookQuantity` is zero in difference calculation, label as "No reference quantity" and exclude from percentage calculation (set diff_pct to None, classification to Amber by default)
- [x] Threshold overrides are session-scoped — stored in agent state, reset on new conversation

## Testing

- [x] Install test dependencies: `pip install -r requirements-test.txt` from `assets/piva-agent/`
- [x] `conftest.py` only sets `IBD_TESTING=true`; mock `mcp_tools.get_mcp_tools` to return `StructuredTool` instances from `mcp-mock.json`
- [x] Write unit tests in `assets/piva-agent/tests/` — one test file per tool:
  - `test_query_products_due_for_counting.py` — tests CCI due-date computation, multi-warehouse, CCI filter, never-counted products
  - `test_query_missing_cci_products.py` — tests null/empty CCI detection, multi-warehouse
  - `test_create_physical_inventory_documents.py` — tests confirmation gate (no action without confirmation), partial failure handling, document number return
  - `test_query_stock_difference_summary.py` — tests Green/Amber/Red classification, threshold override, zero BookQuantity edge case
  - `test_post_inventory_differences.py` — tests confirmation gate, Red-item exclusion, per-document outcome
  - `test_query_document_status_summary.py` — tests status grouping
- [x] Write one integration test `tests/test_agent_integration.py` — calls `agent.invoke()` with a natural language prompt ("Show me products due for counting in warehouse 0001") and asserts response contains expected content; mock LLM and MCP tools
- [x] Run `pytest` from `assets/piva-agent/` (no args)
- [x] If coverage < 70%, add targeted tests until threshold met
- [x] Verify `assets/piva-agent/app/agent.py` has exactly 3 decorated functions: run `grep -c "^@agent_model\|^@agent_config\|^@prompt_section" assets/piva-agent/app/agent.py` — must return 3
- [x] Run `pytest` again (no args) to generate final `test_report.json`
- [x] Verify `test_report.json` exists in `assets/piva-agent/`

## Validation Checklist

- [x] `grep -r "M[0-9]\.achieved" assets/piva-agent/app/` — must return results for all 5 milestones
- [x] `grep -r "sap_cloud_sdk.agent_decorators" assets/piva-agent/app/` — must return results
- [x] `grep -c "^@agent_model\|^@agent_config\|^@prompt_section" assets/piva-agent/app/agent.py` — must return 3
- [x] `ls assets/piva-agent/test_report.json` — must exist
- [x] Confirm no direct HTTP clients (`requests`, `httpx`, OData client) are used for SAP API calls
- [x] Confirm `create_physical_inventory_documents` and `post_inventory_differences` never execute without user confirmation

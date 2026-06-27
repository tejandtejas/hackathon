# Product Requirements Document (PRD)

**Title:** Physical Inventory Verification Agent (PIVA)
**Date:** 2026-06-25
**Owner:** Warehouse Operations / Supply Chain
**Solution Category:** AI Agent

---

## Product Purpose & Value Proposition

**Elevator Pitch:**
Warehouse supervisors spend hours navigating multiple EWM transactions to run a physical inventory cycle. PIVA replaces that with a single Joule chat interface — identify overdue products, create inventory documents, review counted vs. booked stock with colour-coded differences, and post approved corrections, all through natural language.

**Business Need:**
The physical inventory process in EWM spans product master lookups, document creation, count review, discrepancy analysis, and difference posting — each requiring separate EWM transactions. Missing cycle counting indicators in product master data cause process failures discovered late. Difference analysis lacks clear visual prioritisation, leading to delayed action and reduced inventory data quality.

**Expected Value:**
- Reduction in time spent per physical inventory cycle by consolidating all EWM inventory transactions into one conversational interface.
- Early detection of master data gaps (missing cycle counting indicators) before they cause counting failures.
- Faster triage of stock differences through Green/Amber/Red classification, reducing time-to-decision on what to post vs. recount.
- Full auditability of all agent actions through human-in-the-loop confirmation and OpenTelemetry instrumentation.

**Product Objectives (Prioritized):**
1. Enable warehouse supervisors to identify products due for physical inventory counting via natural language, segmented by cycle counting indicator.
2. Create EWM physical inventory documents for identified products with supervisor confirmation.
3. Surface counted vs. booked stock differences with colour-coded thresholds and enable human-confirmed bulk posting.
4. Flag products with missing cycle counting indicators to support proactive master data correction.
5. Support both single-warehouse and multi-warehouse query scopes.

---

## User Profiles & Personas

### Primary Persona: The Warehouse Supervisor

Maria is a 42-year-old warehouse supervisor at a distribution centre running SAP EWM. She oversees daily warehouse operations and is responsible for running physical inventory counts monthly (or more frequently for high-value items on CCI "A"). She spends 2–3 hours per inventory cycle navigating EWM transactions to identify what needs counting, create documents, review differences, and post corrections. She is comfortable with SAP but frustrated by the repetitive, multi-step nature of the process. She worries about missing products due for counting, and has been caught out by products with no cycle counting indicator set — only to discover the gap when the count fails. She wants a single place to manage the entire cycle, with a clear view of what needs her attention.

### Secondary Persona: The Warehouse Manager

David is a 51-year-old warehouse operations manager responsible for inventory accuracy KPIs across two distribution warehouses. He does not perform counting himself but needs regular visibility into how many products are overdue for counting, which warehouses have open differences, and whether postings are being made on time. He uses PIVA to query status across warehouses without drilling into individual EWM transactions.

### Other User Types

- **Warehouse Counter**: Uses RF handheld devices in EWM to perform physical counting. Out of scope for PIVA — counting occurs in EWM directly.
- **Inventory Controller / Finance**: Verifies that differences have been posted correctly and reviews the audit trail. Uses PIVA output as supporting evidence.

---

## User Goals & Tasks

### For Maria (Warehouse Supervisor):

**Goals:**
- Know which products are overdue for physical counting without navigating EWM product master.
- Identify and escalate products with missing cycle counting indicators before the count cycle begins.
- Create physical inventory documents for overdue products in one confirmed action.
- Review counted vs. booked stock differences at a glance and post approved corrections efficiently.

**Key Tasks:**
- Ask PIVA to show products due for counting by CCI indicator (A/B/C) for a specific warehouse.
- Ask PIVA to show products with missing cycle counting indicators.
- Confirm document creation for a set of identified products.
- Query PIVA for counted vs. booked stock summary for documents in "counted" status.
- Review colour-coded difference report, exclude specific lines if needed, and confirm bulk posting.

### For David (Warehouse Manager):

**Goals:**
- Monitor inventory cycle progress across one or multiple warehouses.
- Identify warehouses or product categories with overdue counts or unresolved differences.

**Key Tasks:**
- Query PIVA for overdue products across all managed warehouses.
- Request a summary of open physical inventory documents and their status.

---

## Product Principles

1. **Human-in-the-loop always**: The agent proposes; humans approve. PIVA never creates documents or posts differences without explicit supervisor confirmation.
2. **Natural language first**: Every PIVA capability is accessible through a natural language prompt in Joule — no EWM transaction codes required.
3. **Data quality as a first-class outcome**: Surfacing missing master data (CCI gaps) is a core function, not an afterthought.
4. **Colour-coded clarity**: Difference results are always classified (Green/Amber/Red) to enable immediate triage without manual threshold lookup.
5. **Auditability by design**: Every agent action is logged with structured telemetry and milestone tracking for operational observability.

---

## Business Context

**Current State:**
Warehouse supervisors use multiple EWM transactions (MM60, LI01, LI04, LI20, etc.) to complete a physical inventory cycle. There is no consolidated view of which products are overdue across the warehouse. Products with missing cycle counting indicators are discovered during the count, not before. Difference analysis is performed manually with no threshold-based prioritisation.

**Strategic Alignment:**
PIVA supports SAP's Joule-embedded AI agent strategy and BTP AI Core adoption. It augments the existing SAP S/4HANA EWM Physical Inventory Management capability (SC5604) without replacing it, extending the standard platform with intelligent automation and natural language access.

**Success Criteria:**
- Warehouse supervisors can complete end-to-end physical inventory cycle orchestration (identification → document creation → difference review → posting) entirely through PIVA without opening EWM transactions.
- Products with missing cycle counting indicators are surfaced proactively in every "due for counting" query.
- Colour-coded difference summary is presented for all documents in "counted" status within the query scope.
- No difference is posted without explicit supervisor confirmation.

---

## Goals and Non-Goals

### Goals (In Scope)

- Query EWM product master (EWM warehouse view) to identify products overdue for physical counting based on CCI and last count date, for one or multiple warehouses.
- Flag and report products with missing cycle counting indicators.
- Create EWM physical inventory documents for identified products after supervisor confirmation.
- Query physical inventory documents in "counted" status and return counted vs. booked stock comparison.
- Classify differences as Green / Amber / Red using EWM-configured thresholds, with supervisor override at runtime.
- Present bulk difference posting with per-line exclusion capability; post approved differences to EWM after explicit confirmation.
- Support natural language prompts in SAP Joule.
- Support single-warehouse and multi-warehouse query scopes.

### Non-Goals (Out of Scope)

- RF handheld counting by warehouse counters (performed in EWM directly).
- Automated / unconfirmed creation of physical inventory documents.
- Automated / unconfirmed posting of stock differences.
- Recount workflow initiation (PIVA identifies documents requiring recount; recount execution is out of scope).
- Physical inventory document deletion or cancellation.
- Integration with non-EWM inventory management systems.

---

## Requirements

### Must-Have Requirements

**REQ-01: Products Due for Physical Inventory**

- **Problem to Solve**: Supervisors have no consolidated, real-time view of which products are overdue for counting without navigating EWM product master transaction by transaction.
- **User Story**: As a Warehouse Supervisor, I need to ask PIVA which products are due for physical inventory counting for a given warehouse and CCI, so that I can initiate the count cycle without manually checking EWM.
- **Acceptance Criteria**:
  - Given a warehouse number and optional CCI filter, when I prompt PIVA, then it returns a list of products overdue for counting, segmented by CCI (A/B/C etc.), including last count date and next due date.
  - Given a multi-warehouse prompt, when I ask for due products across all my warehouses, then PIVA returns results aggregated across all specified warehouses.
- **Maps to Objective**: Objective 1
- **Priority Rank**: 1

**REQ-02: Missing Cycle Counting Indicator Report**

- **Problem to Solve**: Products without a cycle counting indicator set in EWM product master are discovered during the count cycle, causing process failures and rework.
- **User Story**: As a Warehouse Supervisor, I need PIVA to show me products with missing cycle counting indicators for a given warehouse, so that I can fix master data before the count cycle begins.
- **Acceptance Criteria**:
  - Given a warehouse number, when I ask PIVA to show missing CCI products, then it returns a list of products in that warehouse with no CCI value set in the EWM warehouse view.
  - The report clearly distinguishes missing CCI products from due-for-counting products.
- **Maps to Objective**: Objective 4
- **Priority Rank**: 2

**REQ-03: Physical Inventory Document Creation**

- **Problem to Solve**: Supervisors must manually create physical inventory documents in EWM for each identified product, which is time-consuming when many products are overdue.
- **User Story**: As a Warehouse Supervisor, I need to ask PIVA to create physical inventory documents for identified products after I confirm, so that I can initiate counting without entering EWM document creation transactions.
- **Acceptance Criteria**:
  - Given a set of products identified by PIVA, when I confirm document creation, then PIVA calls the EWM physical inventory document API and returns the created document numbers.
  - PIVA does not create any document without explicit user confirmation.
  - If document creation fails for any product, PIVA reports the failure clearly with the reason.
- **Maps to Objective**: Objective 2
- **Priority Rank**: 3

**REQ-04: Counted vs. Booked Stock Comparison with Colour-Coded Differences**

- **Problem to Solve**: After counting, supervisors must manually compare counted and booked quantities across documents and apply judgment about which differences require action — a slow and error-prone process.
- **User Story**: As a Warehouse Supervisor, I need PIVA to show me a summary of counted vs. booked stock for documents in "counted" status, with differences classified as Green/Amber/Red, so that I can prioritise which differences to post and which to recount.
- **Acceptance Criteria**:
  - Given physical inventory documents in "counted" status, when I request a difference summary, then PIVA returns a table showing document number, product, warehouse, counted quantity, booked quantity, difference quantity, difference %, and colour classification (Green/Amber/Red).
  - Colour thresholds default to EWM-configured values; supervisor can override thresholds at runtime within the same session.
  - Green = within tolerance, Amber = approaching tolerance limit, Red = exceeds tolerance.
- **Maps to Objective**: Objective 3
- **Priority Rank**: 4

**REQ-05: Human-in-the-Loop Difference Posting**

- **Problem to Solve**: Posting stock differences is a high-impact, irreversible action that must remain under supervisor control; automated bulk posting without review creates financial and audit risk.
- **User Story**: As a Warehouse Supervisor, I need to review the difference summary, optionally exclude specific document lines, confirm, and have PIVA post the approved differences to EWM, so that I maintain control while avoiding manual posting of each line individually.
- **Acceptance Criteria**:
  - Given a difference summary, when I choose to post, PIVA presents the list of lines to be posted and allows me to exclude specific lines before confirming.
  - Upon confirmation, PIVA calls the EWM physical inventory document API to post differences for included lines only.
  - PIVA reports the outcome (posted / failed) for each line after posting.
  - No difference is posted without explicit confirmation in the same conversation turn.
- **Maps to Objective**: Objective 3
- **Priority Rank**: 5

### High-Want Requirements

**REQ-06: Inventory Document Status Summary**

- **Problem to Solve**: Supervisors and managers need a quick view of all physical inventory documents and their current status (open, counted, posted) without navigating EWM.
- **User Story**: As a Warehouse Manager, I need to ask PIVA for a summary of open physical inventory documents by status for one or more warehouses, so that I can monitor cycle completion without opening EWM.
- **Acceptance Criteria**:
  - Given a warehouse scope, when I request a document status summary, then PIVA returns counts and document lists by status (open / counted / posted / partially posted).
- **Priority Rank**: 1

**REQ-07: Recount Identification**

- **Problem to Solve**: Documents with differences exceeding the Red threshold require recount rather than posting; supervisors need PIVA to identify these clearly.
- **User Story**: As a Warehouse Supervisor, I need PIVA to identify which documents in the difference summary require recount (Red classification), so that I can act on them separately from postable differences.
- **Acceptance Criteria**:
  - Red-classified lines in the difference summary are explicitly labelled as "Requires Recount".
  - The posting workflow excludes Red lines by default, requiring explicit supervisor override to include them.
- **Priority Rank**: 2

---

## Non-Functional Requirements

### Performance
- **Latency**: Agent responses for read queries (product due list, difference summary) should complete within 10 seconds for up to 500 products.
- **Throughput**: Agent handles concurrent sessions per standard SAP BTP AI Core capacity.

### Reliability
- **Availability**: Aligned to SAP BTP AI Core and EWM system availability.
- **Fallback**: If EWM MCP server is unavailable, PIVA returns a clear error message and does not attempt to create or post documents.

### Explainability
- **Traceability**: All difference classifications reference the threshold values used (EWM default or supervisor override) in the response.
- **Decision Logging**: All agent tool calls, confirmations, and postings are logged via OpenTelemetry with milestone tracking.
- **Uncertainty Communication**: If EWM data is incomplete (e.g., missing last count date), PIVA flags affected products explicitly rather than omitting them.

---

## Solution Architecture

**Architecture Overview:**
PIVA is a pro-code Python AI agent built on the A2A protocol, hosted on SAP BTP AI Core, and accessible through the SAP Joule chat interface. The agent connects to SAP EWM using two released MCP servers via BTP Destination Service. All agent actions are instrumented with OpenTelemetry for observability.

**Key Components:**

- **PIVA Agent (Python / A2A / LangGraph)**: Core agent runtime — receives natural language prompts, orchestrates tool calls, applies business logic (CCI due-date computation, threshold classification), manages human-in-the-loop confirmation flows.
- **SAP Joule**: User interface — embedded chat for warehouse supervisors and managers.
- **SAP BTP AI Core**: LLM runtime (GPT-4o via SAP Generative AI Hub).
- **BTP Destination Service**: Manages secure connectivity to EWM MCP servers.
- **MCP Server: `OP_PRODUCT_0002/_ProductEWMWarehouse`**: Reads EWM product master — cycle counting indicator, CCI interval, last physical inventory date, warehouse assignment.
- **MCP Server: `OP_WHSEPHYSICALINVENTORYDOC_0001`**: Creates physical inventory documents, reads document status and counted/booked quantities, posts approved differences.

**Integration Points:**

- EWM Product Master (read via `OP_PRODUCT_0002/_ProductEWMWarehouse`): warehouse view, CCI, last count date.
- EWM Physical Inventory Documents (read/write via `OP_WHSEPHYSICALINVENTORYDOC_0001`): document create, status query, counted qty, book qty, difference posting.

### Agent Extensibility & Instrumentation

**Agent Extensibility:**
PIVA is designed with clear tool-based extension points:
- New EWM capabilities (e.g., recount workflow, batch job triggering) can be added as additional MCP tool calls without changing core agent logic.
- Threshold configuration can be extended to read from EWM tolerance configuration APIs when available, replacing the current runtime-input approach.
- Additional warehouse system integrations (e.g., WM-managed warehouses alongside EWM) can be added as new client modules.

**Business Step Instrumentation:**
All five key milestones are instrumented with structured log statements following the pattern `[M{n}.achieved|missed]: description`. This enables real-time monitoring of physical inventory cycle progress in production.

### Automation & Agent Behaviour

**Automation Level:** Autonomous agent with mandatory human-in-the-loop gates for write operations.

**Actions the system performs without human approval:**
- Query EWM product master to identify overdue products and missing CCI.
- Query physical inventory documents and their counted/booked quantities.
- Compute due dates from CCI frequency and last count date.
- Classify differences as Green/Amber/Red.

**Actions that require human review or approval:**
- Creation of physical inventory documents.
- Posting of stock differences (including line-level exclusion before confirmation).

**Model or engine used:** GPT-4o via SAP Generative AI Hub (SAP BTP AI Core).

**Knowledge & data sources accessed:**
- EWM Product Master (EWM warehouse view): cycle counting indicator, frequency, last inventory date — via `OP_PRODUCT_0002/_ProductEWMWarehouse`.
- EWM Physical Inventory Documents: status, counted quantity, book quantity — via `OP_WHSEPHYSICALINVENTORYDOC_0001`.

**Tools or connectors invoked:**
- `OP_PRODUCT_0002/_ProductEWMWarehouse`: read-only — queries EWM product master EWM warehouse view.
- `OP_WHSEPHYSICALINVENTORYDOC_0001`: read + write (document creation and difference posting) — high-risk write actions gated by human confirmation.

**Guardrails & fail-safes:**
- Document creation and difference posting are never executed without an explicit confirmation message from the user in the same conversation turn.
- Red-classified differences (exceeding tolerance) are excluded from default posting scope; supervisor must explicitly include them.
- Agent never modifies EWM product master data (CCI correction is surfaced as information for manual action, not automated).
- If MCP server returns an error, PIVA surfaces the error and stops the workflow; it does not retry write operations automatically.
- Agent session context (supervisor threshold overrides) is scoped to a single conversation and does not persist across sessions.

---

## Milestones

### [M1]: Products Due Identified

- **Description**: Agent has successfully queried EWM product master and returned a list of products overdue for physical inventory counting, including products with missing CCI.
- **Achieved when**: Agent returns a non-empty or empty (confirmed) list of overdue products to the user, segmented by CCI, with missing CCI products flagged.
- **Log on achievement**: `[M1.achieved]: products due for counting identified | warehouse={warehouse} | due_count={count} | missing_cci_count={count}`
- **Log on miss**: `[M1.missed]: product due identification failed | warehouse={warehouse} | reason={error}`

### [M2]: Physical Inventory Documents Created

- **Description**: Agent has created EWM physical inventory documents for the identified products following supervisor confirmation.
- **Achieved when**: All requested document creation API calls complete successfully and document numbers are returned to the user.
- **Log on achievement**: `[M2.achieved]: physical inventory documents created | warehouse={warehouse} | document_count={count} | documents={doc_numbers}`
- **Log on miss**: `[M2.missed]: physical inventory document creation failed | warehouse={warehouse} | reason={error}`

### [M3]: Inventory Documents Queued for Counting

- **Description**: Created physical inventory documents are accessible in EWM as warehouse orders for RF handheld counters. This milestone is informational — counting is performed outside PIVA.
- **Achieved when**: M2 completes; documents are confirmed present in EWM.
- **Log on achievement**: `[M3.achieved]: inventory documents queued for counting | document_count={count}`
- **Log on miss**: `[M3.missed]: documents not confirmed in counting queue | reason={error}`

### [M4]: Counted vs. Booked Stock Comparison Delivered

- **Description**: Agent has retrieved counted and booked quantities for physical inventory documents in "counted" status and presented a colour-coded difference summary.
- **Achieved when**: Agent returns a complete difference summary table (document, product, counted qty, booked qty, difference, classification) to the user.
- **Log on achievement**: `[M4.achieved]: counted vs booked comparison delivered | warehouse={warehouse} | documents_reviewed={count} | green={n} | amber={n} | red={n}`
- **Log on miss**: `[M4.missed]: counted vs booked comparison failed | warehouse={warehouse} | reason={error}`

### [M5]: Differences Posted

- **Description**: Supervisor has reviewed the difference summary, optionally excluded lines, confirmed posting, and PIVA has posted approved differences to EWM.
- **Achieved when**: All included lines are posted successfully via the EWM API and confirmation is returned to the user.
- **Log on achievement**: `[M5.achieved]: stock differences posted | posted_count={count} | excluded_count={count} | failed_count={count}`
- **Log on miss**: `[M5.missed]: difference posting failed or not confirmed | reason={error}`

---

## Risks, Assumptions, and Dependencies

### Risks

- **EWM threshold API coverage**: EWM difference tolerance thresholds may not be directly readable via the released MCP servers. If not available, the agent relies on supervisor-provided threshold values at runtime — this is the primary fallback and must be tested during implementation.
- **CCI due-date computation alignment**: The agent's frequency-based due-date logic must precisely match EWM's internal calculation to avoid incorrect "overdue" lists. Requires validation against EWM cycle counting configuration during testing.
- **MCP server version compatibility**: PIVA depends on the two specified MCP servers being deployed and accessible. Version changes require agent tool schema updates.

### Assumptions

- Both MCP servers (`OP_PRODUCT_0002/_ProductEWMWarehouse` and `OP_WHSEPHYSICALINVENTORYDOC_0001`) are deployed and accessible in the target EWM landscape.
- EWM product master EWM warehouse view contains cycle counting indicator and last physical inventory date fields.
- The EWM physical inventory document API supports creation and difference posting for EWM-managed warehouses.
- Users access PIVA through SAP Joule; no separate UI is required.

### Dependencies

- SAP BTP AI Core with GPT-4o model deployment via SAP Generative AI Hub.
- BTP Destination Service configured for both EWM MCP servers.
- SAP EWM system with Physical Inventory Management (SC5604) and Internal Warehouse Management (SC5130) capabilities active.
- Joule integration with the PIVA A2A agent endpoint.

---

## Appendix

### Glossary

- **CCI (Cycle Counting Indicator)**: EWM product master field that categorises products by counting frequency (e.g., A = monthly, B = quarterly, C = annually).
- **Physical Inventory Document**: EWM document used to record a physical count event for a product in a warehouse location.
- **Booked Stock**: The stock quantity recorded in the EWM system (the "book" value).
- **Counted Stock**: The physically counted quantity entered by a warehouse counter via RF handheld.
- **Difference Posting**: The EWM action that adjusts booked stock to match counted stock, correcting inventory records.
- **Warehouse Order**: EWM queue entry generated from a physical inventory document, used by RF handheld counters to perform counting.
- **MCP Server**: Model Context Protocol server that exposes SAP API capabilities as structured tools for AI agents.

### References

- SAP EWM Physical Inventory Management: `sap.s4:apiResource:OP_WHSEPHYSICALINVENTORYDOC_0001:v1`
- SAP Product Master (EWM view): `sap.s4:apiResource:OP_API_PRODUCT_SRV_0001:v1`
- SAP RBA: Plan to Fulfill E2E → Manage supply chain data and operations (BPS-342)
- SAP S/4HANA Cloud Private Edition — Physical Inventory Management capability (SC5604)
- SAP S/4HANA Cloud Private Edition — Internal Warehouse Management (EWM) capability (SC5130)

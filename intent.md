# Physical Inventory Verification Agent (PIVA)

SAP EWM AI Agent for end-to-end physical inventory verification, cycle counting orchestration, and stock difference management in EWM-managed warehouses.

## Business challenge

Warehouse supervisors managing EWM warehouses currently face a fragmented, manual, and time-consuming physical inventory process. Identifying which products are due for counting (based on cycle counting indicators A/B/C and last count date), creating physical inventory documents, detecting missing master data (cycle counting indicators), reviewing counted-vs-booked stock differences, and posting approved corrections all require multiple EWM transactions and significant manual effort. PIVA automates this end-to-end process through a natural language AI agent embedded in Joule, connecting directly to SAP EWM via released APIs. The agent keeps humans in the loop for all actionable decisions (document creation confirmation, difference posting), while surfacing insights in a business-friendly, colour-coded format. RF handheld counting by warehouse counters is out of scope for the agent.

## Key Milestones

1. **Products Due Identified** — Agent queries EWM product master (EWM warehouse view) and returns list of products overdue for physical counting based on cycle counting indicator frequency and last count date, segmented by indicator (A/B/C etc.), including products with missing cycle counting indicators.
2. **Physical Inventory Documents Created** — Agent creates EWM physical inventory documents for the identified products after supervisor confirmation, and confirms document numbers back to the user.
3. **Inventory Documents Queued for Counting** — Warehouse orders (physical inventory queue) are accessible to RF handheld counters (out of scope for agent, milestone for audit trail).
4. **Counted vs. Booked Stock Comparison Delivered** — For documents in "counted" status, agent retrieves physical (counted) stock vs. booked stock and presents a colour-coded summary (Green/Amber/Red) based on EWM threshold values with supervisor override capability.
5. **Differences Posted** — Supervisor reviews the difference summary, optionally excludes specific lines, confirms bulk posting; agent posts approved differences to EWM and confirms completion.

## Business Architecture (RBA)

### End-to-End Process

Plan to Fulfill (E2E)

### Process Hierarchy

```
Plan to Fulfill (E2E)
└── Manage Fulfillment (generic)
    └── Manage supply chain data and operations (generic) [BPS-342]
        └── Manage inventory and warehouse operations
            └── Identify products due for cycle counting
            └── Create physical inventory documents
            └── Review counted vs. booked stock discrepancies
            └── Post approved stock differences
```

### Summary

PIVA's physical inventory verification and EWM cycle counting process maps to the Plan to Fulfill E2E under Manage Fulfillment → Manage supply chain data and operations (BPS-342). Industry variants include wholesale distribution, retail replenishment, fuels, and hydrocarbon supply and refining.

## Fit Gap Analysis

| Requirement (business) | Standard asset(s) found | API ORD ID | MCP Server ORD ID | MCP Server Version | Gap? | Notes / assumptions |
| ---------------------- | ----------------------- | ---------- | ----------------- | ------------------ | ---- | ------------------- |
| Read EWM product master with cycle counting indicator and last count date | SAP S/4HANA Cloud Private Edition – Physical Inventory Management (SC5604) | `sap.s4:apiResource:OP_API_PRODUCT_SRV_0001:v1` (Product Master A2X) | User-specified MCP: `OP_PRODUCT_0002/_ProductEWMWarehouse` ✓ | As deployed | No | EWM warehouse view of product master holds cycle counting indicator and interval |
| Identify products due for counting (by indicator A/B/C and last count date) | SAP S/4HANA – Internal Warehouse Management (SC5130) | `sap.s4:apiResource:OP_WHSEPHYSICALSTOCKPRODUCTS_0001:v1` | — | — | Yes (logic) | Agent computes due date from indicator frequency + last count date; no standard API returns this pre-calculated |
| Flag products with missing cycle counting indicators | SAP S/4HANA – Physical Inventory Management | `sap.s4:apiResource:OP_API_PRODUCT_SRV_0001:v1` | User-specified MCP: `OP_PRODUCT_0002/_ProductEWMWarehouse` ✓ | As deployed | No | Agent filters null/blank CCI in EWM product master |
| Create physical inventory documents in EWM | SAP S/4HANA – Physical Inventory Management (SC5604) | `sap.s4:apiResource:OP_WHSEPHYSICALINVENTORYDOC_0001:v1` | User-specified MCP: `OP_WHSEPHYSICALINVENTORYDOC_0001` ✓ | As deployed | No | Released EWM API supports document creation |
| Query counted vs. booked stock for documents in "counted" status | SAP S/4HANA – Physical Inventory Management | `sap.s4:apiResource:OP_WHSEPHYSICALINVENTORYDOC_0001:v1` | User-specified MCP: `OP_WHSEPHYSICALINVENTORYDOC_0001` ✓ | As deployed | No | API returns counted quantity and book quantity per document item |
| Colour-coded difference display (Green/Amber/Red) with EWM threshold + supervisor override | SAP S/4HANA – Inventory Analytics (SC5474) | — | — | — | Yes (UI logic) | EWM threshold read via API; supervisor override stored in agent session; colour logic in agent |
| Bulk posting of differences with line exclusion and human confirmation | SAP S/4HANA – Physical Inventory Management (SC5604) | `sap.s4:apiResource:OP_WHSEPHYSICALINVENTORYDOC_0001:v1` | User-specified MCP: `OP_WHSEPHYSICALINVENTORYDOC_0001` ✓ | As deployed | Partial | Human-in-the-loop confirmation pattern must be custom-built in agent; API supports posting |
| Multi-warehouse and single-warehouse query support | SAP S/4HANA – Internal Warehouse Management | Both product master and inventory doc APIs support warehouse filtering | — | — | No | Agent resolves warehouse scope from natural language prompt |

### Key findings

- Both primary MCP servers are already identified and specified by the user: `OP_PRODUCT_0002/_ProductEWMWarehouse` (product master EWM view) and `OP_WHSEPHYSICALINVENTORYDOC_0001` (physical inventory documents).
- No pre-built MCP servers were found in the catalog for the four key API ORD IDs checked — confirming reliance on the user-specified MCP servers.
- The core gap is agent-side logic: computing products due for counting (frequency × last count date), implementing colour-coded difference thresholds with supervisor override, and the human-in-the-loop bulk-post-with-exclusion pattern.
- SAP S/4HANA Cloud Private Edition natively covers Physical Inventory Management (SC5604) and Internal Warehouse Management (SC5130) as mandatory capabilities under BPS-342, confirming PIVA augments rather than replaces standard EWM functionality.
- RF handheld counting (warehouse orders queue) is deliberately out of scope; PIVA picks up the process after counting is complete and documents reach "counted" status.

## Recommendations

### Physical Inventory Verification Agent (PIVA)

#### Executive Summary

Pro-code Python AI agent on SAP BTP, embedded in Joule, connecting to EWM via released MCP servers for end-to-end physical inventory automation.

#### Recommended Solution

PIVA is a pro-code Python AI agent (A2A protocol) hosted on SAP BTP AI Core. It is accessible through the Joule chat interface and accepts natural language prompts from warehouse supervisors and managers. The agent connects to SAP EWM using two released MCP servers:

- **`OP_PRODUCT_0002/_ProductEWMWarehouse`** — reads EWM product master data including cycle counting indicators (CCI), CCI interval/frequency, and last physical inventory date.
- **`OP_WHSEPHYSICALINVENTORYDOC_0001`** — creates physical inventory documents, queries document status, retrieves counted vs. booked quantities, and posts approved differences.

**Agent capabilities:**
1. **Due-for-counting identification** — computes overdue products per CCI frequency and last count date; segments by indicator (A/B/C etc.); flags products with missing CCI.
2. **Physical inventory document creation** — creates EWM PI documents for identified products after supervisor confirmation; returns document numbers.
3. **Counted vs. booked stock summary** — for documents in "counted" status, returns a colour-coded difference report: Green (within EWM threshold), Amber (approaching threshold), Red (exceeds threshold). Supervisor can override threshold values at runtime.
4. **Human-in-the-loop difference posting** — supervisor reviews summary, optionally excludes specific document lines, confirms bulk posting; agent posts to EWM and confirms.
5. **Multi-warehouse support** — single or multi-warehouse scope resolved from natural language input.

The agent uses OpenTelemetry instrumentation for observability and includes key milestone tracking for the physical inventory lifecycle.

#### Problem Statement

Warehouse supervisors managing EWM warehouses spend significant time navigating multiple EWM transactions to run the physical inventory cycle. Missing cycle counting indicators in product master data cause process failures discovered late. Difference analysis between counted and booked stock is manually intensive, error-prone, and lacks clear visual differentiation for action prioritisation. The absence of a unified, conversational interface means delays in initiating counts, overlooked discrepancies, and reduced data quality in inventory records.

#### Affected User Roles

- **Warehouse Supervisor** — primary user; identifies products due, creates documents, reviews and posts differences
- **Warehouse Manager** — oversight and reporting across one or multiple warehouses
- **Warehouse Counter** — uses RF handheld devices for counting (out of scope for PIVA)
- **Inventory Controller / Finance** — audit trail, verification of posted differences

#### Important factors

##### Saves time through automation of repetitive EWM navigation
PIVA replaces multiple EWM transactions (product master lookup, document creation, count review, difference posting) with a single conversational interface, reducing end-to-end physical inventory cycle time.

##### Proactive master data quality management
By surfacing products with missing cycle counting indicators upfront, PIVA enables supervisors to correct master data before it causes process failures during counting.

##### Human-in-the-loop design ensures control and auditability
All actionable steps (document creation, difference posting) require explicit supervisor confirmation. The agent never posts without human approval, maintaining audit trail integrity.

##### Colour-coded difference visualisation drives faster decisions
Green/Amber/Red classification of stock differences — based on EWM-configured thresholds with supervisor override — enables immediate triage of what can be posted vs. what requires recount.

#### Potential risks

##### API coverage for EWM-specific threshold configuration
EWM difference tolerance thresholds may not be directly exposed via the released APIs; the agent may need to accept thresholds as runtime supervisor input as the primary mechanism.

##### Cycle counting due-date computation complexity
Frequency-based due-date logic (e.g., CCI "A" = every 30 days) must align precisely with EWM's internal calculation; misalignment could produce incorrect "due" lists.

##### MCP server availability and version compatibility
PIVA depends on the two user-specified MCP servers being deployed and accessible in the target EWM landscape; version changes to these servers require agent tool schema updates.

#### Recommended solution category

AI Agent

#### Intent fit
95%

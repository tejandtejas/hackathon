# Physical Inventory Verification Agent

Physical Inventory Verification Agent for EWM — orchestrates end-to-end physical inventory counting, document creation, discrepancy analysis, and difference posting via natural language

## Overview

Uses A2A Protocol, LangGraph, LiteLLM, and SAP Cloud SDK.

## Structure

- `app/main.py` - A2A server entry
- `app/agent_executor.py` - Request handling
- `app/agent.py` - Agent logic

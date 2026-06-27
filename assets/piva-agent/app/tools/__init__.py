"""PIVA agent tools package.

Dual-mode: on Joule (JOULE_RUNTIME=1), MCP tools are injected at runtime
by agent_executor. On CF, direct-client tools are built via build_domain_tools().
"""
import os
from typing import Any

from tools.inventory_due import query_products_due_for_counting, build_due_products_result
from tools.missing_cci import query_missing_cci_products, build_missing_cci_result
from tools.create_documents import create_physical_inventory_documents, build_creation_result
from tools.stock_difference import query_stock_difference_summary, build_difference_summary
from tools.post_differences import post_inventory_differences
from tools.document_status import query_document_status_summary, build_status_summary

# Joule-mode tools: used when agent_executor injects MCP tools at runtime
ALL_TOOLS = [
    query_products_due_for_counting,
    query_missing_cci_products,
    create_physical_inventory_documents,
    query_stock_difference_summary,
    post_inventory_differences,
    query_document_status_summary,
]


def build_domain_tools(s4_client: Any = None) -> list:
    """Return the list of LangChain tools to use for the current runtime.
    
    On CF (JOULE_RUNTIME not set): builds direct-API tools using s4_client.
    On Joule (JOULE_RUNTIME=1):    returns Joule MCP-instruction tools.
    
    The agent calls this during _get_tools() to get the tools for _run_agent().
    """
    if os.environ.get("JOULE_RUNTIME"):
        return list(ALL_TOOLS)
    if s4_client is not None:
        from tools.cf_tools import build_cf_tools
        return build_cf_tools(s4_client)
    return list(ALL_TOOLS)


__all__ = [
    "query_products_due_for_counting",
    "query_missing_cci_products",
    "create_physical_inventory_documents",
    "query_stock_difference_summary",
    "post_inventory_differences",
    "query_document_status_summary",
    "build_due_products_result",
    "build_missing_cci_result",
    "build_creation_result",
    "build_difference_summary",
    "build_status_summary",
    "ALL_TOOLS",
    "build_domain_tools",
]

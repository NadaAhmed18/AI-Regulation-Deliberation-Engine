"""
AGENT TOOLS — Registry & Dispatcher

This module is the single entry point an agent uses to discover and call
its available tools. It imports the schemas from `schemas.py` and the 
implementations from their respective modules.
"""

from typing import Optional, List, Dict, Any
from langfuse import observe

# 1. Correct schema imports from schemas.py
from src.agent.tools.schemas import (
    RETRIEVER_TOOL_SCHEMA,
    WEB_SEARCH_TOOL_SCHEMA,
    WEB_LEARNER_TOOL_SCHEMA,
    ALL_TOOL_SCHEMAS,
)

# 2. Function implementations
from src.agent.tools.retriever import search_ai_policy
from src.agent.tools.web_search import search_web, learn_and_ingest_url

# Map of tool names to their actual callable Python functions
TOOLS_MAP = {
    "search_ai_policy": search_ai_policy,
    "search_web": search_web,
    "learn_and_ingest_url": learn_and_ingest_url,
}

# Role permissions: Stakeholders can search RAG, search Web, and save Web to RAG
ROLE_TOOL_PERMISSIONS: Dict[str, List[str]] = {
    "stakeholder": ["search_ai_policy", "search_web", "learn_and_ingest_url"],
    "moderator": [],
}


def get_tool_schemas(allowed_tools: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Return tool schemas ready to be passed to LLMClient.
    If allowed_tools is given, filters schemas to only those tools.
    """
    if allowed_tools is None:
        return list(ALL_TOOL_SCHEMAS)
    return [
        schema for schema in ALL_TOOL_SCHEMAS 
        if schema["function"]["name"] in allowed_tools
    ]


def get_tool_schemas_for_role(role: str) -> List[Dict[str, Any]]:
    """
    Resolve a named agent role to its allowed tools and return schemas.
    """
    if role not in ROLE_TOOL_PERMISSIONS:
        raise ValueError(f"Unknown role '{role}'. Known roles: {list(ROLE_TOOL_PERMISSIONS.keys())}")
    return get_tool_schemas(allowed_tools=ROLE_TOOL_PERMISSIONS[role])


@observe(as_type="tool")
def execute_tool(tool_name: str, arguments: Dict[str, Any], allowed_tools: Optional[List[str]] = None) -> str:
    """
    Executes a registered tool by name with safety checks.
    Includes Langfuse @observe to trace tool latency and observations.
    """
    if allowed_tools is not None and tool_name not in allowed_tools:
        return f"Error: Tool '{tool_name}' is not permitted for this agent."

    func = TOOLS_MAP.get(tool_name)
    if func is None:
        return f"Error: Tool '{tool_name}' is not registered."

    try:
        return func(**arguments)
    except Exception as e:
        return f"Error executing tool '{tool_name}': {e}"


if __name__ == "__main__":
    # Smoke test: python -m src.agent.tools.tool_registry
    print("--- Permitted Tools for Stakeholder ---")
    schemas = get_tool_schemas_for_role("stakeholder")
    for s in schemas:
        print(f"- {s['function']['name']}: {s['function']['description'][:60]}...")
        
    print("\n--- Testing Allowed Tools Check ---")
    print(execute_tool("search_web", {"query": "test"}, allowed_tools=[]))
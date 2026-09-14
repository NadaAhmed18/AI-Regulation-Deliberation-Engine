"""AGENT TOOLS — Registry, Schemas, and Dispatcher."""

from typing import Optional, List, Dict, Any
from langfuse import observe
from src.agent.tools.research import unified_policy_research

RESEARCH_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "research_policy_evidence",
        "description": "Comprehensive policy research. Searches internal Neo4j knowledge, queries live web via Tavily, and auto-ingests cited sources.",
        "parameters": {
            "type": "object",
            "properties": {
                "queries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Search queries to investigate simultaneously.",
                },
                "document_urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional specific document URLs to inspect directly.",
                },
            },
            "required": ["queries"],
        },
    },
}

TOOLS_MAP = {
    "research_policy_evidence": unified_policy_research,
}

ROLE_TOOL_PERMISSIONS: Dict[str, List[str]] = {
    "stakeholder": ["research_policy_evidence"],
    "moderator": [],
}


def get_tool_schemas_for_role(role: str) -> List[Dict[str, Any]]:
    """Return enabled tool schemas for a given role."""
    allowed_tools = ROLE_TOOL_PERMISSIONS.get(role, [])
    schemas = [RESEARCH_TOOL_SCHEMA]
    return [s for s in schemas if s["function"]["name"] in allowed_tools]


@observe(as_type="tool")
def execute_tool(tool_name: str, arguments: Dict[str, Any], allowed_tools: Optional[List[str]] = None) -> str:
    """Executes a registered tool with permission checks."""
    if allowed_tools is not None and tool_name not in allowed_tools:
        return f"Error: Tool '{tool_name}' is not permitted for this agent."

    func = TOOLS_MAP.get(tool_name)
    if func is None:
        return f"Error: Tool '{tool_name}' is not registered."

    try:
        return func(**arguments)
    except Exception as e:
        return f"Error executing tool '{tool_name}': {e}"
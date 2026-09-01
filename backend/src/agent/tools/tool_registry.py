"""
AGENT TOOLS — Registry & Dispatcher

This module is the single entry point an agent uses to discover and call
its available tools. It contains no tool implementation logic itself; it
only imports each tool's function and schema from its own file and wires
them into a registry.

Tool implementations:
    - `search_ai_policy` / `RETRIEVER_TOOL_SCHEMA` — Neo4j knowledge base
      search. Defined in `src/agent/tools/retriever.py`.
    - `search_web` / `WEB_SEARCH_TOOL_SCHEMA` — live web search via Tavily.
      Defined in `src/agent/tools/web_search.py`.

Every schema follows the OpenAI/OpenRouter function-calling format
(`{"type": "function", "function": {...}}`), so `get_tool_schemas(...)`
can be passed directly as the `tools=` argument to `LLMClient`.

Role-based access:
    Not every agent should see every tool. A debate participant needs
    both `search_ai_policy` and `search_web`; a moderator/orchestrator
    agent that only manages the debate's turn order needs neither.
    `ROLE_TOOL_PERMISSIONS` declares that mapping once, and
    `get_tool_schemas_for_role(role)` / `execute_tool(..., allowed_tools=...)`
    both enforce it — the former by not advertising a disallowed tool to
    the LLM, the latter by refusing to run it even if a model calls it
    anyway.
"""

from typing import Optional

from src.agent.tools.retriever import search_ai_policy, RETRIEVER_TOOL_SCHEMA
from src.agent.tools.web_search import search_web, WEB_SEARCH_TOOL_SCHEMA

TOOLS_MAP = {
    "search_ai_policy": search_ai_policy,
    "search_web": search_web,
}

ALL_TOOL_SCHEMAS = [
    RETRIEVER_TOOL_SCHEMA,
    WEB_SEARCH_TOOL_SCHEMA,
]

# Named roles in the multi-agent architecture, mapped to the tools an
# agent playing that role may use. Add a new role here as new agent types
# are introduced; nothing else in this module needs to change.
ROLE_TOOL_PERMISSIONS = {
    "stakeholder": ["search_ai_policy", "search_web"],
    "moderator": [],
}


def get_tool_schemas(allowed_tools: Optional[list[str]] = None) -> list[dict]:
    """
    Return tool schemas, ready to pass as `tools=` to the LLM client.

    Args:
        allowed_tools: If `None` (default), every registered schema is
            returned. If a list of tool names is given, only schemas for
            those names are returned — an unlisted tool is simply not
            advertised to the LLM.
    """
    if allowed_tools is None:
        return list(ALL_TOOL_SCHEMAS)
    return [schema for schema in ALL_TOOL_SCHEMAS if schema["function"]["name"] in allowed_tools]


def get_tool_schemas_for_role(role: str) -> list[dict]:
    """
    Resolve a named agent role to its allowed tools and return the
    corresponding schemas. See `ROLE_TOOL_PERMISSIONS`.

    Raises:
        ValueError: if `role` is not a key in `ROLE_TOOL_PERMISSIONS`.
    """
    if role not in ROLE_TOOL_PERMISSIONS:
        raise ValueError(
            f"Unknown role '{role}'. Known roles: {list(ROLE_TOOL_PERMISSIONS)}"
        )
    return get_tool_schemas(allowed_tools=ROLE_TOOL_PERMISSIONS[role])


def execute_tool(tool_name: str, arguments: dict, allowed_tools: Optional[list[str]] = None) -> str:
    """
    Look up and run a registered tool by name.

    Args:
        tool_name: Name of the tool to run, as returned in the LLM's
            tool_call.
        arguments: Keyword arguments to call the tool with.
        allowed_tools: Optional allow-list enforced at execution time, not
            just at schema-advertisement time. This is a defense-in-depth
            check: `get_tool_schemas_for_role("moderator")` already stops
            a moderator agent from being offered any tool, but a model can
            still hallucinate a tool_call for a tool it was never shown.
            Passing the same `allowed_tools` here blocks that case too.
            `None` (default) means no restriction.

    Never raises: an unregistered tool name, a disallowed tool, and any
    exception raised while running the tool all come back as a plain
    error string, so the ReAct loop can feed the failure back to the LLM
    as a tool observation instead of crashing.
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
    # Run as: python -m src.tools
    print("--- All tool schemas ---")
    for schema in get_tool_schemas():
        print(f"- {schema['function']['name']}: {schema['function']['description']}")

    print("\n--- Schemas for role='moderator' (should be empty) ---")
    print(get_tool_schemas_for_role("moderator"))

    print("\n--- Schemas for role='stakeholder' ---")
    for schema in get_tool_schemas_for_role("stakeholder"):
        print(f"- {schema['function']['name']}")

    print("\n--- execute_tool('search_web', ...) ---")
    print(execute_tool("search_web", {"query": "EU AI Act 2026 updates", "max_results": 2}))

    print("--- execute_tool('search_web', ..., allowed_tools=[]) — should be blocked ---")
    print(execute_tool("search_web", {"query": "test"}, allowed_tools=[]))

    print("--- execute_tool('unknown_tool', ...) ---")
    print(execute_tool("unknown_tool", {"query": "test"}))

    # Note: search_ai_policy requires a running Neo4j instance + embedding
    # model, so it is intentionally not exercised in this lightweight smoke
    # test. See `src/agent/tools/retriever.py`'s own `__main__` block to
    # test it directly against a live database.

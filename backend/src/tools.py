"""
AGENT TOOLS — Function-Calling Registry

Purpose:
    Single place where every external capability available to an agent's
    ReAct loop is wrapped into the OpenAI-compatible function-calling
    format (`{"type": "function", "function": {...}}`) and made callable
    by name. `BaseAgent.run_react_loop()` is expected to:
        1. call `get_all_tool_schemas()` once, at agent init, and pass the
           result as the `tools=` argument to `LLMClient.generate_response()`;
        2. call `execute_tool(tool_name, arguments)` whenever the LLM
           returns a `{"type": "tool_call", ...}` response, and feed the
           returned string back into the conversation as a "tool" message.

Tools registered here:

1. `search_ai_policy` — wraps the existing, already-implemented Week 1
   Neo4j knowledge retriever (`src/agent/tools/retriever.py`, referred to
   as the "KnowledgeRetrieverTool" in `src/rag/README.md`). Nothing about
   the retrieval logic itself is duplicated or reimplemented here — this
   module only re-exports its function and schema so both agent tools
   live behind one import.

2. `search_web` — a live web-search tool backed by Tavily
   (https://tavily.com), called directly over its REST API via `requests`
   rather than the `tavily-python` SDK. This avoids adding a new heavy
   dependency for what is a single POST request, and keeps the tool
   working even if the SDK's interface changes. See
   `docs/agent-tools.md` for the full design rationale, the fallback
   behavior when `TAVILY_API_KEY` is not configured, and why this was
   chosen over DuckDuckGo (the alternative suggested in the original
   `web_search.py` stub).

Design note (why a single `src/tools.py` instead of the existing
`src/agent/tools/{retriever,web_search,tool_registry}.py` package):
    This ticket asks for `src/tools.py` specifically. Rather than
    duplicating `retriever.py`'s logic here, this module imports it and
    adds the previously-unimplemented web-search tool and registry in one
    place, so `BaseAgent` only ever needs one import:
        from src.tools import get_all_tool_schemas, execute_tool

Scope boundary:
    `src/agent/base_agent.py` (the ReAct loop) and `src/clients/llm_client.py`
    (the LLM call itself) are still spec-only stubs owned by a teammate's
    separate ticket. This module does not implement or call either — it
    only guarantees that whatever `BaseAgent` ends up looking like, the
    tool schemas and `execute_tool()` dispatcher it needs already exist and
    work correctly in isolation. `tests/test_tool_calling_flow.py`
    demonstrates the exact round trip `run_react_loop()` is specified to
    perform (LLM tool_call → execute_tool → tool message) using a mocked
    LLM response, precisely because there is no real `LLMClient`/`BaseAgent`
    yet to run that round trip against end-to-end.
"""

import os

import requests
from dotenv import load_dotenv

from src.agent.tools.retriever import search_ai_policy, RETRIEVER_TOOL_SCHEMA

# Importing `src.agent.tools.retriever` already triggers `src/config.py`'s
# `load_dotenv()` call transitively, but that's an implicit side effect of
# another module's import order — relying on it silently would break the
# moment that import chain changes. Calling it here too makes the .env
# dependency explicit and local to this file. `load_dotenv()` is safe to
# call more than once.
load_dotenv()

# ------------------------------------------------------------------------------
# 1. Web Search Tool (Tavily)
# ------------------------------------------------------------------------------

TAVILY_API_URL = "https://api.tavily.com/search"
TAVILY_TIMEOUT_SECONDS = 10
MAX_ALLOWED_WEB_RESULTS = 5

WEB_SEARCH_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_web",
        "description": (
            "Search the live internet for recent news, articles, and updates "
            "on AI policy, AI regulation, and technology that may not be in "
            "the internal knowledge base (e.g. very recent events)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query (e.g. 'latest UK AI safety institute guidelines').",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Number of web results to retrieve. Defaults to 3.",
                    "minimum": 1,
                    "maximum": MAX_ALLOWED_WEB_RESULTS,
                },
            },
            "required": ["query"],
        },
    },
}


def search_web(query: str, max_results: int = 3) -> str:
    """
    Execute a live web search via the Tavily REST API and return formatted
    text the LLM can read as tool output.

    Fails gracefully (never raises), returning a plain string in every one
    of these cases so the ReAct loop can feed it back to the LLM as a tool
    observation instead of crashing:
        - `query` is empty/whitespace-only, or `max_results` is < 1
          (the schema's `minimum`/`maximum` are hints to a well-behaved LLM,
          not a guarantee — a model can still send an invalid value).
        - `TAVILY_API_KEY` is not set in the environment.
        - The request to Tavily fails (network error, timeout, non-2xx
          response, or malformed response body). The raw exception is
          logged to the console for debugging but not included in the
          string returned to the LLM, since a stack trace / low-level
          error message isn't useful context for it to reason over.
    """
    query = (query or "").strip()
    if not query:
        return "Web search failed: query cannot be empty."

    if max_results < 1:
        return "Web search failed: max_results must be at least 1."
    max_results = min(max_results, MAX_ALLOWED_WEB_RESULTS)

    print(f"\n[Agent Tool] 🌐 Searching the web for: '{query}'")

    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return (
            "Web search is unavailable: no TAVILY_API_KEY is configured in "
            "the environment. Rely on the internal knowledge base "
            "(search_ai_policy) instead."
        )

    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
        "search_depth": "basic",
    }

    try:
        response = requests.post(TAVILY_API_URL, json=payload, timeout=TAVILY_TIMEOUT_SECONDS)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        print(f"[Agent Tool] ⚠️ Tavily request failed: {e}")
        return (
            "Web search failed because the Tavily service could not be "
            "reached. Rely on the internal knowledge base (search_ai_policy) instead."
        )
    except ValueError as e:
        print(f"[Agent Tool] ⚠️ Tavily returned an unparsable response: {e}")
        return (
            "Web search failed: Tavily returned a response that could not "
            "be parsed. Rely on the internal knowledge base (search_ai_policy) instead."
        )

    results = data.get("results", [])
    if not results:
        return "No web results found for this query."

    llm_formatted_response = "Here are the live web search results:\n\n"
    for i, r in enumerate(results[:max_results], 1):
        title = r.get("title", "Untitled")
        url = r.get("url", "N/A")
        snippet = (r.get("content") or "")[:500]
        llm_formatted_response += (
            f"--- WEB SOURCE {i} ---\n"
            f"Title: {title}\n"
            f"URL: {url}\n"
            f"Snippet: {snippet}\n\n"
        )

    return llm_formatted_response


# ------------------------------------------------------------------------------
# 2. Tool Registry & Dispatcher
# ------------------------------------------------------------------------------

TOOLS_MAP = {
    "search_ai_policy": search_ai_policy,
    "search_web": search_web,
}

ALL_TOOL_SCHEMAS = [
    RETRIEVER_TOOL_SCHEMA,
    WEB_SEARCH_TOOL_SCHEMA,
]


def get_all_tool_schemas() -> list[dict]:
    """Return every tool schema, ready to pass as `tools=` to the LLM client."""
    return ALL_TOOL_SCHEMAS


def execute_tool(tool_name: str, arguments: dict) -> str:
    """
    Look up and run a registered tool by name.

    Never raises: unregistered tools and execution errors both come back
    as a plain error string so the ReAct loop can feed the failure back to
    the LLM as a tool observation instead of crashing.
    """
    func = TOOLS_MAP.get(tool_name)
    if func is None:
        return f"Error: Tool '{tool_name}' is not registered."

    try:
        return func(**arguments)
    except Exception as e:
        return f"Error executing tool '{tool_name}': {e}"


if __name__ == "__main__":
    # Smoke test. Run as: python -m src.tools
    print("--- Registered tool schemas ---")
    for schema in get_all_tool_schemas():
        print(f"- {schema['function']['name']}: {schema['function']['description']}")

    print("\n--- execute_tool('search_web', ...) ---")
    print(execute_tool("search_web", {"query": "EU AI Act 2026 updates", "max_results": 2}))

    print("--- execute_tool('unknown_tool', ...) ---")
    print(execute_tool("unknown_tool", {"query": "test"}))

    # Note: search_ai_policy requires a running Neo4j instance + embedding
    # model, so it is intentionally not exercised in this lightweight smoke
    # test. See `src/agent/tools/retriever.py`'s own `__main__` block to
    # test it directly against a live database.

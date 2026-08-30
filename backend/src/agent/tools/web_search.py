"""
LIVE WEB SEARCH TOOL (PURE FUNCTION)

Provides agents with real-time internet search capability via the Tavily
API. This module owns the tool's implementation and schema exclusively;
`src/tools.py` only imports and registers them — it does not host any
tool logic itself.
"""

import os

import requests
from dotenv import load_dotenv

# Explicit here so this module works correctly whether it's imported via
# the registry (src/tools.py) or run/imported standalone — it should not
# depend on another module having already called load_dotenv() first.
# Safe to call more than once.
load_dotenv()

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
    text for the calling agent to read as a tool observation.

    Never raises. Returns a plain string in every failure case so a ReAct
    loop can feed it back to the LLM as an observation instead of crashing:
        - `query` is empty/whitespace-only, or `max_results` is < 1.
        - `TAVILY_API_KEY` is not set in the environment.
        - The request fails (network error, timeout, non-2xx response, or
          a response body that cannot be parsed as JSON). The underlying
          exception is logged to the console for debugging; the string
          returned to the LLM stays generic.
    """
    query = (query or "").strip()
    if not query:
        return "Web search failed: query cannot be empty."

    if max_results < 1:
        return "Web search failed: max_results must be at least 1."
    max_results = min(max_results, MAX_ALLOWED_WEB_RESULTS)

    print(f"\n[Web Tool] 🌐 Searching web for: '{query}'")

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
        print(f"[Web Tool] ⚠️ Tavily request failed: {e}")
        return (
            "Web search failed because the Tavily service could not be "
            "reached. Rely on the internal knowledge base (search_ai_policy) instead."
        )
    except ValueError as e:
        print(f"[Web Tool] ⚠️ Tavily returned an unparsable response: {e}")
        return (
            "Web search failed: Tavily returned a response that could not "
            "be parsed. Rely on the internal knowledge base (search_ai_policy) instead."
        )

    results = data.get("results", [])
    if not results:
        return "No web results found for this query."

    formatted_response = "Here are the live web search results:\n\n"
    for i, r in enumerate(results[:max_results], 1):
        title = r.get("title", "Untitled")
        url = r.get("url", "N/A")
        snippet = (r.get("content") or "")[:500]
        formatted_response += (
            f"--- WEB SOURCE {i} ---\n"
            f"Title: {title}\n"
            f"URL: {url}\n"
            f"Snippet: {snippet}\n\n"
        )

    return formatted_response


if __name__ == "__main__":
    # Run as: python -m src.agent.tools.web_search
    print(search_web("EU AI Act 2026 updates"))

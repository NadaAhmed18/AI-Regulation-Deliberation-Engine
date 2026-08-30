# Agent Tools — Function-Calling Registry

## 1. Overview

`src/tools.py` is the single place where every external capability
available to an agent's ReAct loop is wrapped into a standard
function-calling format and made callable by name. It backs the
`BaseAgent` spec described in `src/agent/base_agent.py`:

```python
from src.tools import get_all_tool_schemas, execute_tool

self.tools_schema = get_all_tool_schemas()   # passed to LLMClient.generate_response(tools=...)
...
observation = execute_tool(tool_name, arguments)  # called when the LLM returns a tool_call
```

Two tools are registered:

| Tool name          | Purpose                                          | Status |
|---------------------|---------------------------------------------------|--------|
| `search_ai_policy`  | Vector search over the Week 1 Neo4j knowledge base | Wraps existing, already-implemented code |
| `search_web`        | Live web search via Tavily                         | New — implemented in this ticket |

## 2. Why the Function-Calling Schema Looks Like This

Both schemas follow the shape:

```python
{
    "type": "function",
    "function": {
        "name": "...",
        "description": "...",
        "parameters": {"type": "object", "properties": {...}, "required": [...]}
    }
}
```

This is the OpenAI Chat Completions **tools** format. Per
`src/clients/llm_client.py`'s design spec, the supported providers are
`"openai"` and `"openrouter"` — OpenRouter is itself OpenAI-API-compatible
— so this is "the standard function-calling format for the chosen LLM"
required by this ticket. It requires no translation layer: the same list
returned by `get_all_tool_schemas()` is passed directly as `tools=` to
`client.chat.completions.create(...)`.

## 3. Wrapping the Week 1 Retriever

`src/agent/tools/retriever.py` (referred to as the "KnowledgeRetrieverTool"
in `src/rag/README.md`) was **already fully implemented** before this
ticket: it exposes `search_ai_policy(query, top_k) -> str` and its schema,
`RETRIEVER_TOOL_SCHEMA`, in the exact function-calling format above.

`src/tools.py` does not duplicate that logic. It imports both directly:

```python
from src.agent.tools.retriever import search_ai_policy, RETRIEVER_TOOL_SCHEMA
```

and re-exports them through `TOOLS_MAP` / `ALL_TOOL_SCHEMAS` alongside the
new web-search tool, so `BaseAgent` only ever needs a single import
(`from src.tools import ...`) to reach every available tool.

**Note on import path:** this assumes `src/agent/tools/retriever.py` is
still at that path after the Week 1 → Week 2 merge. If a teammate has since
moved or renamed it (e.g. to `src/agent/retriever.py`, as an earlier draft
of `src/rag/README.md` describes), update the import at the top of
`src/tools.py` accordingly — nothing else in this file depends on where
that module lives.

## 4. Web Search — Why Tavily, and Why the REST API Directly

The ticket asks to "attempt to add a live web-search tool (Tavily) OR
clearly document why it is out of scope." Tavily was implemented, not
skipped, with the following decisions:

**Tavily over DuckDuckGo.** The original `web_search.py` stub suggested
`duckduckgo_search` as an example. Tavily was used instead because it is
purpose-built for LLM/RAG use cases (its results come back as clean,
pre-summarized `content` snippets rather than raw search-result HTML), and
it does not depend on scraping a search engine's result page, which tends
to break without notice. `web_search.py` itself is left as-is (Week 1/2
stub) — its logic now lives in `src/tools.py`'s `search_web`.

**Direct REST call over the `tavily-python` SDK.** `search_web()` calls
`https://api.tavily.com/search` directly via `requests.post(...)` instead
of adding the `tavily-python` package as a dependency. Tavily's API is a
single, stable POST endpoint, so a raw HTTP call gets the same result as
the SDK without adding and pinning another third-party dependency for one
request. `requests` was already a transitive dependency in this project
(pulled in by `crawl4ai`/`trafilatura`) and is now declared explicitly in
`pyproject.toml`.

**Never raises.** `search_web()` is designed to degrade gracefully rather
than crash the agent's ReAct loop, in these situations:

- `query` is empty/whitespace-only, or `max_results` is less than 1 → the
  schema declares `minimum: 1` / `maximum: 5` on `max_results` as a hint
  to a well-behaved LLM, but a model can still send an invalid value, so
  `search_web()` validates both defensively and returns a plain string
  rather than raising. Values above the cap are silently clamped to 5
  rather than rejected, since an over-eager request for more results
  isn't actually an error worth failing on.
- No `TAVILY_API_KEY` configured → returns a plain string telling the
  agent web search is unavailable and to use `search_ai_policy` instead.
- The request fails (network error, timeout, non-2xx response, or an
  unparsable response body) → the raw exception is logged to the console
  (`print(...)`) for debugging, but the string returned to the LLM stays
  generic ("...could not be reached...") rather than including the raw
  exception text — a stack trace or HTTP error string isn't useful
  context for the LLM to reason over, and could otherwise leak internal
  details into a stakeholder's generated opinion.

This matters because a raised exception here would otherwise propagate up
through `execute_tool()` mid-conversation and could break
`BaseAgent.run_react_loop()`'s message history. `execute_tool()` itself
also wraps every tool call in a `try/except` as a second safety net, in
case a future tool doesn't handle its own errors as carefully.

**Explicit `.env` loading.** `src/tools.py` calls `load_dotenv()` itself
at import time, rather than relying on the fact that importing
`src.agent.tools.retriever` transitively imports `src/config.py` (which
already calls `load_dotenv()`). That transitive path works today, but
would silently stop working if that import chain ever changes —
`load_dotenv()` is idempotent, so calling it again here costs nothing and
makes the `.env` dependency local and explicit to this file.

**Scope boundary: this does not implement `BaseAgent`.**
`src/agent/base_agent.py` (the ReAct loop) and `src/clients/llm_client.py`
(the actual LLM call) are still spec-only stub files owned by a separate
ticket at the time this was written. This module guarantees the tool
schemas and `execute_tool()` dispatcher `BaseAgent` needs already exist
and work correctly — it does not, and cannot yet, demonstrate a real
LLM deciding to call a tool, since there is no real `LLMClient` to do that
deciding. `tests/test_tool_calling_flow.py` closes as much of that gap as
is possible right now: it mocks an LLM's `tool_call` response in the exact
dict shape `LLMClient.generate_response()` is specified to return, and
verifies that `execute_tool()`'s output threads correctly through the
exact message-append pattern `run_react_loop()` is specified to use. Once
`BaseAgent`/`LLMClient` exist for real, that mock can be swapped for a
live call with no change to the assertions, since they depend only on the
message-shape contract, not on how the tool_call was produced.

**Verification status.** This module's structure (schema registration,
`TOOLS_MAP`, `execute_tool()` dispatch, `search_web()`'s validation and
fallback paths, and the mocked tool-calling round trip) was verified
locally — see Section 6. Live end-to-end verification against a real
Tavily API key, a running Neo4j instance, and a real `BaseAgent` still
needs to happen once those pieces exist / are configured.

## 5. Environment Variables

Added to `.env.example`:

```
TAVILY_API_KEY=your_tavily_api_key_here
```

Get a key at [tavily.com](https://tavily.com). If left unset, `search_web`
does not fail the agent — it just reports itself unavailable (see above).

## 6. Testing This Module

```bash
cd backend
python -m src.tools
python -m tests.test_tool_calling_flow
```

`python -m src.tools` prints the registered tool schemas and exercises
`search_web` (with and without a working `TAVILY_API_KEY`) and
`execute_tool` on an unregistered tool name.

`tests/test_tool_calling_flow.py` is the more rigorous check: it verifies
every schema is well-formed enough for an OpenAI/OpenRouter `tools=` call,
and simulates the full `LLM tool_call → execute_tool → tool message`
round trip (with a mocked LLM response, per the scope boundary above),
including the case where the LLM hallucinates an unregistered tool name.

`search_ai_policy` is intentionally not exercised by either test since it
requires a live Neo4j instance and a Voyage AI API key — test it directly
via `python -m src.agent.tools.retriever` against a running database
instead.

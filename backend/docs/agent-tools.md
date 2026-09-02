# Agent Tools

## 1. Architecture

Tool logic and tool registration are separated:

| Layer | File | Responsibility |
|---|---|---|
| Registry / dispatcher | `src/agent/tools/tool_registry.py` | Aggregates tool schemas and functions; resolves agent roles to allowed tools; dispatches `execute_tool()` calls. Contains no tool logic itself. |
| Knowledge base tool | `src/agent/tools/retriever.py` | `search_ai_policy` — Neo4j vector search over the knowledge base, and its schema `RETRIEVER_TOOL_SCHEMA`. |
| Web search tool | `src/agent/tools/web_search.py` | `search_web` — live web search via the Tavily API, and its schema `WEB_SEARCH_TOOL_SCHEMA`. |

An agent's ReAct loop uses the registry as its only entry point:

```python
from src.agent.tools.tool_registry import get_tool_schemas_for_role, execute_tool

tools_schema = get_tool_schemas_for_role(role)   # passed to LLMClient.generate_response(tools=...)
...
observation = execute_tool(tool_name, arguments, allowed_tools=ROLE_TOOL_PERMISSIONS[role])
```

Every schema follows the OpenAI/OpenRouter Chat Completions **tools**
format:

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

This requires no translation layer: the list returned by
`get_tool_schemas(...)` is passed directly as `tools=` to
`client.chat.completions.create(...)`.

## 2. Role-Based Tool Access

Not every agent is allowed to use every tool. A stakeholder agent
participating in a debate has access to both tools; a moderator/
orchestrator agent that manages turn order and debate structure has
access to neither.

`ROLE_TOOL_PERMISSIONS` in `src/agent/tools/tool_registry.py` declares this mapping:

```python
ROLE_TOOL_PERMISSIONS = {
    "stakeholder": ["search_ai_policy", "search_web"],
    "moderator": [],
}
```

Two functions enforce it at different points:

- `get_tool_schemas_for_role(role)` — returns only the schemas an agent
  of that role should be offered. A moderator agent is never shown any
  tool, so a well-behaved LLM has no way to call one.
- `execute_tool(tool_name, arguments, allowed_tools=...)` — enforces the
  same restriction at dispatch time. This is independent of schema
  filtering: if a model calls a tool it was never shown, `execute_tool`
  still refuses to run it when given that agent's `allowed_tools`.

Adding a new role means adding one entry to `ROLE_TOOL_PERMISSIONS`;
nothing else in the registry changes.

## 3. Knowledge Base Tool (`search_ai_policy`)

Defined in `src/agent/tools/retriever.py`: `search_ai_policy(query, top_k) -> str`
runs a vector search over the Neo4j knowledge base and returns matching
chunks as formatted text, alongside `RETRIEVER_TOOL_SCHEMA`.
`src/agent/tools/tool_registry.py` imports both and registers them
without any additional logic.

## 4. Web Search Tool (`search_web`)

Defined in `src/agent/tools/web_search.py`. Web search is handled via the
Tavily API because it returns pre-summarized, RAG-optimized content
snippets rather than raw HTML, which removes the need for a separate
content-cleaning step before the result reaches the LLM.

The Tavily API is called directly via `requests.post(...)` against its
REST endpoint (`https://api.tavily.com/search`) rather than through the
`tavily-python` SDK. The API surface is a single POST request, so a
direct HTTP call reaches the same result without adding a third-party
SDK dependency to maintain, and keeps error handling (timeouts, status
codes, response parsing) fully under this module's control.

`search_web` never raises. Every failure path returns a plain string
instead, so a ReAct loop can feed it back to the LLM as a tool
observation rather than crashing:

| Condition | Behavior |
|---|---|
| Empty/whitespace-only `query` | Returns an error string; no request is sent. |
| `max_results < 1` | Returns an error string; no request is sent. |
| `max_results` above the cap (5) | Silently clamped to 5. |
| `TAVILY_API_KEY` not set | Returns a string directing the agent to use `search_ai_policy` instead. |
| Network error, timeout, non-2xx response, or unparsable body | Logs the underlying exception to the console; returns a generic failure string to the LLM (no stack trace or raw error text). |

`execute_tool()` additionally wraps every tool call in a `try/except` as
a second safety net, independent of how carefully an individual tool
handles its own errors.

`.env` loading (`load_dotenv()`) happens explicitly at the top of
`web_search.py`, so the module behaves correctly whether it is imported
through the registry or used standalone.

## 5. Environment Variables

Declared in `.env.example`:

```
TAVILY_API_KEY=your_tavily_api_key_here
```

Get a key at [tavily.com](https://tavily.com). If unset, `search_web`
reports itself unavailable rather than failing the agent (see Section 4).

## 6. Integration with the Agent

`src/agent/base_agent.py`'s `BaseAgent` is the consumer of this registry:
it calls `get_tool_schemas_for_role("stakeholder")` at construction time to
build the schema list passed to `LLMClient`, and calls `execute_tool(...,
allowed_tools=self.allowed_tool_names)` inside `run_react_loop()` whenever
the LLM's response is a tool call. `src/clients/llm_client.py`'s `LLMClient`
is the component that actually calls the model (via OpenRouter or a local
HuggingFace model) and normalizes its response into the
`{"type": "text" | "tool_call", ...}` shape this registry's callers expect.

`tests/test_tool_calling_flow.py` verifies the contract between the
registry and that message shape using a mocked LLM tool-call response,
independent of a live model call.

## 7. Testing

```bash
cd backend
python -m src.agent.tools.tool_registry
python -m src.agent.tools.web_search
python -m tests.test_tool_calling_flow
```

`python -m src.agent.tools.tool_registry` prints all registered schemas,
the schemas for each role, and exercises `execute_tool` (including a
disallowed-tool case and an unregistered-tool case).

`python -m src.agent.tools.web_search` runs `search_web` standalone.

`tests/test_tool_calling_flow.py` verifies: every schema is well-formed
for an LLM `tools=` call; role-based filtering returns the correct
schemas per role; an unknown role raises `ValueError`; `execute_tool`
blocks a disallowed tool; and the full `LLM tool_call → execute_tool →
tool message` round trip produces correctly shaped messages, including
when the tool name is unregistered.

`search_ai_policy` is not exercised by these tests, since it requires a
live Neo4j instance and a Voyage AI API key. Test it directly via
`python -m src.agent.tools.retriever` against a running database.

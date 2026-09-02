"""
TEST: Tool-Calling Round Trip (Mocked LLM)

What this proves:
    `execute_tool()`'s output can be correctly threaded through the exact
    message-passing shape `BaseAgent.run_react_loop()` is specified to use
    (see `src/agent/base_agent.py`):

        messages = [system, user]
              │
              ▼
        LLM decides to call a tool  →  {"type": "tool_call", "tool_name": ...,
                                          "arguments": {...}, "tool_call_id": ...}
              │
              ▼
        execute_tool(tool_name, arguments)  →  observation (str)
              │
              ▼
        messages.append({"role": "assistant", "tool_calls": [...]})
        messages.append({"role": "tool", "tool_call_id": ..., "content": observation})
              │
              ▼
        (loop continues so the LLM can read the observation)

What this does NOT prove:
    This does not exercise a real LLM. `src/agent/base_agent.py` and
    `src/clients/llm_client.py` are now implemented (they were still
    spec-only stubs when this test was first written), but calling them
    for real here would require a live `OPENROUTER_API_KEY` and network
    access, which this test suite does not assume. A mocked LLM response
    (in the exact dict shape `LLMClient.generate_response()` actually
    returns) stands in for step 1 above, so this test's assertions verify
    the message-shape contract between `execute_tool()` and
    `run_react_loop()` without needing a live LLM call.

Run as a module from the `backend/` root:

    python -m tests.test_tool_calling_flow
"""

from src.agent.tools.tool_registry import execute_tool, get_tool_schemas, get_tool_schemas_for_role


def _mock_llm_tool_call_response() -> dict:
    """
    Stand-in for `LLMClient.generate_response()` returning a tool_call, in
    the exact standardized shape specified in `src/clients/llm_client.py`:

        {
            "type": "tool_call",
            "tool_name": ...,
            "arguments": {...},
            "tool_call_id": ...
        }

    Simulates the LLM deciding to call `search_web` because Tavily isn't
    configured in this test environment, so the round trip can be verified
    without any live network dependency (`search_web` degrades gracefully
    to a plain string either way — see `src/agent/tools/web_search.py`).
    """
    return {
        "type": "tool_call",
        "tool_name": "search_web",
        "arguments": {"query": "EU AI Act 2026 amendments", "max_results": 2},
        "tool_call_id": "call_mock_001",
    }


def test_tool_schemas_are_available_for_the_llm_call():
    schemas = get_tool_schemas()
    tool_names = {schema["function"]["name"] for schema in schemas}
    assert "search_ai_policy" in tool_names
    assert "search_web" in tool_names
    # Every schema must be well-formed enough for an OpenAI/OpenRouter
    # tools= call: {"type": "function", "function": {"name", "description", "parameters"}}
    for schema in schemas:
        assert schema["type"] == "function"
        assert "name" in schema["function"]
        assert "description" in schema["function"]
        assert "parameters" in schema["function"]


def test_role_based_filtering_hides_tools_from_the_moderator():
    """The Week 3 Moderator/Orchestrator agent must not be offered any
    tool — it only manages the debate's turn order."""
    moderator_schemas = get_tool_schemas_for_role("moderator")
    assert moderator_schemas == []


def test_role_based_filtering_gives_stakeholders_both_tools():
    stakeholder_schemas = get_tool_schemas_for_role("stakeholder")
    tool_names = {schema["function"]["name"] for schema in stakeholder_schemas}
    assert tool_names == {"search_ai_policy", "search_web"}


def test_unknown_role_raises_value_error():
    raised = False
    try:
        get_tool_schemas_for_role("villain")
    except ValueError as e:
        raised = True
        assert "villain" in str(e)
    assert raised, "Expected ValueError for an unrecognized role."


def test_execute_tool_blocks_disallowed_tool_even_if_llm_calls_it():
    """Defense in depth: even if a moderator's LLM hallucinates a
    tool_call for a tool it was never shown, execute_tool must refuse it
    when given that agent's allowed_tools — not just the schema filter."""
    observation = execute_tool("search_web", {"query": "test"}, allowed_tools=[])
    assert "not permitted" in observation


def test_tool_call_round_trip_produces_valid_messages():
    """
    Simulates exactly what `run_react_loop()` is specified to do when the
    LLM response has `type == "tool_call"`.
    """
    messages = [
        {"role": "system", "content": "You are a stakeholder in an AI policy debate."},
        {"role": "user", "content": "Provide your initial opinion on GPAI regulation."},
    ]

    llm_response = _mock_llm_tool_call_response()
    assert llm_response["type"] == "tool_call"

    tool_name = llm_response["tool_name"]
    arguments = llm_response["arguments"]

    # This is the actual call under test — everything else here is just
    # message bookkeeping around it, matching base_agent.py's spec.
    observation = execute_tool(tool_name, arguments)

    messages.append({
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": llm_response["tool_call_id"],
            "function": {"name": tool_name, "arguments": str(arguments)},
        }],
    })
    messages.append({
        "role": "tool",
        "tool_call_id": llm_response["tool_call_id"],
        "name": tool_name,
        "content": observation,
    })

    # The observation must be a non-empty string ready to hand back to the
    # LLM on the next loop iteration — never a raw exception, never None.
    assert isinstance(observation, str)
    assert len(observation) > 0

    # The message list is now in the exact shape run_react_loop() would
    # send back to the LLM on its next iteration.
    assert messages[-2]["role"] == "assistant"
    assert messages[-2]["tool_calls"][0]["function"]["name"] == "search_web"
    assert messages[-1]["role"] == "tool"
    assert messages[-1]["tool_call_id"] == "call_mock_001"
    assert messages[-1]["content"] == observation


def test_round_trip_survives_an_unregistered_tool_name():
    """Even a hallucinated/unregistered tool name must not break the loop —
    execute_tool() should hand back an error string, not raise."""
    llm_response = {
        "type": "tool_call",
        "tool_name": "delete_all_files",  # not a real registered tool
        "arguments": {},
        "tool_call_id": "call_mock_002",
    }
    observation = execute_tool(llm_response["tool_name"], llm_response["arguments"])
    assert isinstance(observation, str)
    assert "not registered" in observation


def _run_all_tests():
    tests = [
        test_tool_schemas_are_available_for_the_llm_call,
        test_role_based_filtering_hides_tools_from_the_moderator,
        test_role_based_filtering_gives_stakeholders_both_tools,
        test_unknown_role_raises_value_error,
        test_execute_tool_blocks_disallowed_tool_even_if_llm_calls_it,
        test_tool_call_round_trip_produces_valid_messages,
        test_round_trip_survives_an_unregistered_tool_name,
    ]
    for test_fn in tests:
        test_fn()
        print(f"{test_fn.__name__}")
    print("\nAll tool-calling round-trip tests passed (mocked LLM response).")


if __name__ == "__main__":
    _run_all_tests()

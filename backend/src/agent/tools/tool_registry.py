"""
CENTRAL TOOL REGISTRY & DISPATCHER

GUIDELINES FOR TEAM MEMBERS:
-----------------------------
Purpose:
    Acts as the single source of truth for all tools. 
    Imports the pure functions and schemas from `retriever.py` and `web_search.py`
    so the BaseAgent can access them dynamically.

Dependencies to Import:
    - `search_ai_policy`, `RETRIEVER_TOOL_SCHEMA` from `.retriever`
    - `search_web`, `WEB_SEARCH_TOOL_SCHEMA` from `.web_search`

Data Structures to Implement:
-----------------------------
1. `TOOLS_MAP`: 
   A dictionary mapping the string name of the tool to the actual imported function:
   TOOLS_MAP = {
       "search_ai_policy": search_ai_policy,
       "search_web": search_web
   }

2. `ALL_TOOL_SCHEMAS`: 
   A list containing all imported schemas (to be passed to the LLM):
   ALL_TOOL_SCHEMAS = [
       RETRIEVER_TOOL_SCHEMA,
       WEB_SEARCH_TOOL_SCHEMA
   ]

Functions to Implement:
-----------------------
1. def get_all_tool_schemas() -> list[dict]:
    - Simply returns the `ALL_TOOL_SCHEMAS` list.

2. def execute_tool(tool_name: str, arguments: dict) -> str:
    - Look up the function: `func = TOOLS_MAP.get(tool_name)`
    - IF `func` is None:
        return f"Error: Tool '{tool_name}' is not registered."
    - Wrap in try/except:
        return func(**arguments)
    - Return stringified error if execution fails.

SMOKE TEST:
-----------
if __name__ == "__main__":
    # Test 1: Print get_all_tool_schemas()
    # Test 2: Call execute_tool("search_ai_policy", {"query": "GPAI rules"})
"""
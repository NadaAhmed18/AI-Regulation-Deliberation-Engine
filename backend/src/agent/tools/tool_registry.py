from .retriever import search_ai_policy, RETRIEVER_TOOL_SCHEMA
from .web_search import search_web, WEB_SEARCH_TOOL_SCHEMA

TOOLS_MAP = {
    "search_ai_policy": search_ai_policy,
    "search_web": search_web,
}

ALL_TOOL_SCHEMAS = [
    RETRIEVER_TOOL_SCHEMA,
    WEB_SEARCH_TOOL_SCHEMA,
]


def get_all_tool_schemas() -> list[dict]:
    return ALL_TOOL_SCHEMAS


def execute_tool(tool_name: str, arguments: dict) -> str:
    func = TOOLS_MAP.get(tool_name)
    if func is None:
        return f"Error: Tool '{tool_name}' is not registered."

    try:
        return func(**arguments)
    except Exception as e:
        return f"Error executing tool '{tool_name}': {e}"


if __name__ == "__main__":
    print(get_all_tool_schemas())
    print(execute_tool("search_ai_policy", {"query": "GPAI rules"}))
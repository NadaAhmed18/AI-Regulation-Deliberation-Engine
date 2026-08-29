"""
LIVE WEB SEARCH TOOL (PURE FUNCTION)

GUIDELINES FOR TEAM MEMBERS:
-----------------------------
Purpose:
    Provide agents with real-time internet search capability (e.g., via 
    DuckDuckGo Search or Tavily) without using any Classes.

Components to Implement:

1. SCHEMA DEFINITION:
   - Define a dictionary constant `WEB_SEARCH_TOOL_SCHEMA`:
     {
         "type": "function",
         "function": {
             "name": "search_web",
             "description": "Search the live internet for recent news, articles, and updates on AI policy and technology.",
             "parameters": {
                 "type": "object",
                 "properties": {
                     "query": {
                         "type": "string",
                         "description": "The search query (e.g., 'latest UK AI safety institute guidelines')"
                     }
                 },
                 "required": ["query"]
             }
         }
     }

2. FUNCTION IMPLEMENTATION:
   def search_web(query: str, max_results: int = 3) -> str:
       - Log execution: `print(f"[Web Tool] 🌐 Searching web for: '{query}'")`
       - Wrap in a try/except block:
           * Use `duckduckgo_search` (or another API) to fetch top `max_results`.
           * Format the output into a readable string:
             "--- WEB SOURCE {i} ---\nTitle: {title}\nURL: {url}\nSnippet: {body}\n"
           * Return the combined string.
       - Exception handling fallback: 
           * If network drops, return: "Web search failed. Please rely on your internal knowledge or the Neo4j database."

3. SMOKE TEST:
   - Include `if __name__ == "__main__":` to test calling `search_web("EU AI Act 2026 updates")`.
"""
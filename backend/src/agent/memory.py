"""
AGENT MEMORY STORE (KAN-7)

GUIDELINES FOR TEAM MEMBERS:
-----------------------------
Purpose:
    Provide a persistent record of what an agent has said, learned, and its 
    opinion snapshots so it maintains consistency across multiple rounds.
    Do NOT use Neo4j for this. Keep it simple: SQLite or a local JSON file.

Data Schema to Store:
    - agent_name (str)
    - timestamp (datetime)
    - role (str: "user", "assistant", "tool")
    - content (str)
    - tool_calls / observation_data (optional dict)

Functions to Implement:
1. def __init__(self, db_path="data/agent_memory.sqlite"):
    - Initialize SQLite connection.
    - Create table `conversation_history` if it doesn't exist.

2. def save_message(self, agent_name: str, role: str, content: str, meta: dict = None):
    - Insert a new row into the database.
    - If `content` is an opinion snapshot, ensure it is tagged appropriately in `meta`.

3. def get_history(self, agent_name: str, limit: int = 10) -> list[dict]:
    - Retrieve the last N messages for this specific agent.
    - Format them back into the OpenAI `[{"role": "...", "content": "..."}]` structure
      so the BaseAgent can easily append them to its LLM context.

4. def clear_memory(self, agent_name: str = None):
    - Wipe history for testing/resetting simulations.
"""
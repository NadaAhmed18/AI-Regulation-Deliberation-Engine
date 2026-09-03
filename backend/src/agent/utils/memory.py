import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

class MemoryStore:
    def __init__(self, db_path: str = "data/agent_memory.sqlite"):
        """
        Initializes the SQLite database for agent memory.
        Creates the 'data' directory if it doesn't exist.
        """
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        self.db_path = str(path)
        self._init_db()

    def _init_db(self):
        """Creates the memory table if it does not already exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_name TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT,
                    meta TEXT
                )
            """)
            conn.commit()

    def save_message(self, agent_name: str, role: str, content: Optional[str], meta: Optional[Dict[str, Any]] = None):
        """
        Saves a single message to the agent's history.
        Content can be None (e.g., when the assistant makes a tool call).
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            meta_json = json.dumps(meta) if meta else None
            timestamp = datetime.utcnow().isoformat()
            
            cursor.execute("""
                INSERT INTO conversation_history (agent_name, timestamp, role, content, meta)
                VALUES (?, ?, ?, ?, ?)
            """, (agent_name, timestamp, role, content, meta_json))
            conn.commit()

    def get_history(self, agent_name: str, limit: int = 15) -> List[Dict[str, Any]]:
        """
        Retrieves the last N messages for a specific agent and formats them
        so they strictly comply with OpenAI/OpenRouter's message array schema.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Fetch the latest messages (DESC), but reverse them in Python 
            # so the LLM reads them in chronological order.
            cursor.execute("""
                SELECT role, content, meta
                FROM conversation_history
                WHERE agent_name = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (agent_name, limit))
            
            rows = cursor.fetchall()
            
        history = []
        for row in reversed(rows):
            msg = {
                "role": row["role"],
                "content": row["content"]
            }
            
            if row["meta"]:
                try:
                    meta_dict = json.loads(row["meta"])
                    
                    # 1. Handle Assistant Tool Calls
                    # OpenRouter requires 'tool_calls' array if the assistant invoked a tool
                    if row["role"] == "assistant" and "tool_calls" in meta_dict:
                        msg["tool_calls"] = meta_dict["tool_calls"]
                        
                    # 2. Handle Tool Observations
                    # OpenRouter requires 'tool_call_id' and 'name' for tool responses
                    elif row["role"] == "tool":
                        if "tool_call_id" in meta_dict:
                            msg["tool_call_id"] = meta_dict["tool_call_id"]
                        if "tool_name" in meta_dict:
                            msg["name"] = meta_dict["tool_name"]
                            
                except json.JSONDecodeError:
                    pass
            
            history.append(msg)
            
        return history

    def clear_memory(self, agent_name: Optional[str] = None):
        """
        Wipes the memory for a specific agent, or clears the entire DB if None.
        Useful for resetting simulations between runs.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if agent_name:
                cursor.execute("DELETE FROM conversation_history WHERE agent_name = ?", (agent_name,))
            else:
                cursor.execute("DELETE FROM conversation_history")
            conn.commit()

# ==========================================
# Testing the Memory Store
# ==========================================
if __name__ == "__main__":
    # Run as: python -m src.agent.utils.memory
    mem = MemoryStore()
    mem.clear_memory("Test_Agent")
    
    # Simulate a tool-call flow to verify schema
    mem.save_message("Test_Agent", "user", "Search for AI rules.")
    mem.save_message("Test_Agent", "assistant", None, meta={"tool_calls": [{"id": "call_123", "type": "function", "function": {"name": "search_ai_policy", "arguments": "{}"}}]})
    mem.save_message("Test_Agent", "tool", "Found rules.", meta={"tool_call_id": "call_123", "tool_name": "search_ai_policy"})
    
    print("--- Loaded Memory History ---")
    for msg in mem.get_history("Test_Agent"):
        print(msg)
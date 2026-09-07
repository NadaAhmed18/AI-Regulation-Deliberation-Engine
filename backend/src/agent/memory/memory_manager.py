from typing import List, Dict, Any, Optional
from src.utils.prompt_builder import render_prompt
from src.clients.llm_client import LLMClient
from src.clients.postgres import PostgresClient


class ConversationContextManager:
    def __init__(self, simulation_id: str, topic: str, strategy: Dict[str, Any]):
        self.simulation_id: str = simulation_id
        self.topic: str = topic
        self.strategy_type: str = str(strategy.get("type", "all"))  # "all", "sliding_window", "summary"
        self.window_size: int = int(strategy.get("window_size", 5))
        self.db = PostgresClient()
        
        # Initialized on-demand or if strategy is summary
        self.summarizer_llm: Optional[LLMClient] = (
            LLMClient() if self.strategy_type == "summary" else None
        )

    def _fetch_history(self) -> List[Dict[str, Any]]:
        """Fetches raw discussion turns and converts them to standard dictionaries."""
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT agent_name, content 
                    FROM discussion_history 
                    WHERE simulation_id = %s 
                    ORDER BY round_number ASC, id ASC
                """, (self.simulation_id,))
                rows = cur.fetchall()
                # Explicit conversion to dict satisfies Pylance strict type checking
                return [dict(row) for row in rows]

    def build_context_for_agent(self, system_prompt: str) -> List[Dict[str, Any]]:
        """
        Fetches the discussion history from Postgres and applies the selected memory strategy.
        Returns the formatted list of messages ready for the Agent's ReAct loop.
        """
        raw_history: List[Dict[str, Any]] = self._fetch_history()
        messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]

        # If no history yet, just return the system prompt
        if not raw_history:
            return messages

        # 1. Strategy: All (Full conversation context)
        if self.strategy_type == "all":
            for row in raw_history:
                name = str(row.get("agent_name", "Unknown"))
                content = str(row.get("content", ""))
                messages.append({"role": "user", "content": f"{name} said: {content}"})

        # 2. Strategy: Sliding Window (Only last N turns)
        elif self.strategy_type == "sliding_window":
            recent_history = raw_history[-self.window_size:]
            for row in recent_history:
                name = str(row.get("agent_name", "Unknown"))
                content = str(row.get("content", ""))
                messages.append({"role": "user", "content": f"{name} said: {content}"})

        # 3. Strategy: LLM Summarization (Summarize older turns, keep last 2 verbatim)
        elif self.strategy_type == "summary":
            if len(raw_history) <= 3:
                for row in raw_history:
                    name = str(row.get("agent_name", "Unknown"))
                    content = str(row.get("content", ""))
                    messages.append({"role": "user", "content": f"{name} said: {content}"})
            else:
                older_history = raw_history[:-2]
                recent_history = raw_history[-2:]

                history_text = "\n".join([
                    f"{r.get('agent_name', 'Unknown')}: {r.get('content', '')}"
                    for r in older_history
                ])

                summary_prompt = render_prompt(
                    "memory_summarizer", 
                    topic=self.topic, 
                    raw_history=history_text
                )

                # Type-safety guard to satisfy Pylance reportOptionalMemberAccess
                if self.summarizer_llm is None:
                    self.summarizer_llm = LLMClient()

                summary_response = self.summarizer_llm.generate_response([
                    {"role": "user", "content": summary_prompt}
                ])
                summary_content = summary_response.get("content", "")

                messages.append({
                    "role": "system", 
                    "content": f"PREVIOUS CONVERSATION SUMMARY:\n{summary_content}"
                })

                for row in recent_history:
                    name = str(row.get("agent_name", "Unknown"))
                    content = str(row.get("content", ""))
                    messages.append({"role": "user", "content": f"{name} said: {content}"})

        return messages
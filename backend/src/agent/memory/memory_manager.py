from typing import List, Dict, Any, Optional
from src.utils.prompt_builder import render_prompt
from src.clients.llm_client import LLMClient
from src.clients.postgres import PostgresClient


class ConversationContextManager:
    def __init__(self, simulation_id: str, topic: str, strategy: Optional[Dict[str, Any]] = None):
        self.simulation_id: str = simulation_id
        self.topic: str = topic
        
        # Strategy fallback to 'sliding_window' if not provided
        strat = strategy or {"type": "sliding_window", "window_size": 4}
        raw_type = str(strat.get("type", "sliding_window")).lower()
        
        # Normalize strategy names
        self.strategy_type: str = "full" if raw_type in ["all", "full"] else raw_type
        self.window_size: int = int(strat.get("window_size", 4))
        
        self.db = PostgresClient()
        self.summarizer_llm: Optional[LLMClient] = (
            LLMClient() if self.strategy_type == "summary" else None
        )

    def _fetch_history(self) -> List[Dict[str, Any]]:
        """Fetches raw discussion turns in chronological order."""
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT agent_name, role, content, round_number 
                    FROM discussion_history 
                    WHERE simulation_id = %s 
                    ORDER BY round_number ASC, id ASC
                """, (self.simulation_id,))
                rows = cur.fetchall()
                return [dict(row) for row in rows]

    def build_context_for_agent(
        self, 
        system_prompt: str,
        current_agent_name: Optional[str] = None,
        allowed_speakers: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Builds contextual messages for an agent.
        
        Args:
            system_prompt: The agent's base instructions.
            current_agent_name: Name of the current speaking agent.
            allowed_speakers: List of agent names this agent is allowed to see.
                              If None, all messages are visible (used by moderator).
        """
        raw_history: List[Dict[str, Any]] = self._fetch_history()
        messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]

        if not raw_history:
            return messages

        # =========================================================================
        # 1. VISIBILITY FILTER (Graph Routing)
        # Keep message IF:
        #   - It belongs to current_agent (they always remember their own words)
        #   - OR sender is inside allowed_speakers (visible graph edge)
        # =========================================================================
        if allowed_speakers is not None and current_agent_name is not None:
            permitted_set = set(allowed_speakers)
            permitted_set.add(current_agent_name)

            filtered_history = [
                row for row in raw_history
                if row.get("agent_name") in permitted_set
            ]
        else:
            filtered_history = raw_history

        if not filtered_history:
            return messages

        # =========================================================================
        # 2. APPLY AGENT'S SPECIFIC MEMORY STRATEGY
        # =========================================================================

        # STRATEGY 1: FULL MEMORY (All visible turns)
        if self.strategy_type == "full":
            for row in filtered_history:
                name = str(row.get("agent_name", "Unknown"))
                content = str(row.get("content", ""))
                if name == current_agent_name:
                    messages.append({"role": "assistant", "content": content})
                else:
                    messages.append({"role": "user", "content": f"[{name}]: {content}"})

        # STRATEGY 2: SLIDING WINDOW (Only last N visible turns)
        elif self.strategy_type == "sliding_window":
            recent_history = filtered_history[-self.window_size:]
            for row in recent_history:
                name = str(row.get("agent_name", "Unknown"))
                content = str(row.get("content", ""))
                if name == current_agent_name:
                    messages.append({"role": "assistant", "content": content})
                else:
                    messages.append({"role": "user", "content": f"[{name}]: {content}"})

        # STRATEGY 3: SUMMARY (Summarize older turns, keep last 2 verbatim)
        elif self.strategy_type == "summary":
            if len(filtered_history) <= 3:
                for row in filtered_history:
                    name = str(row.get("agent_name", "Unknown"))
                    content = str(row.get("content", ""))
                    if name == current_agent_name:
                        messages.append({"role": "assistant", "content": content})
                    else:
                        messages.append({"role": "user", "content": f"[{name}]: {content}"})
            else:
                older_history = filtered_history[:-2]
                recent_history = filtered_history[-2:]

                history_text = "\n".join([
                    f"{r.get('agent_name', 'Unknown')}: {r.get('content', '')}"
                    for r in older_history
                ])

                summary_prompt = render_prompt(
                    "memory_summarizer", 
                    topic=self.topic, 
                    raw_history=history_text
                )

                if self.summarizer_llm is None:
                    self.summarizer_llm = LLMClient()

                summary_response = self.summarizer_llm.generate_response([
                    {"role": "user", "content": summary_prompt}
                ])
                summary_content = summary_response.get("content", "")

                messages.append({
                    "role": "system", 
                    "content": f"PREVIOUS DISCUSSION SUMMARY:\n{summary_content}"
                })

                for row in recent_history:
                    name = str(row.get("agent_name", "Unknown"))
                    content = str(row.get("content", ""))
                    if name == current_agent_name:
                        messages.append({"role": "assistant", "content": content})
                    else:
                        messages.append({"role": "user", "content": f"[{name}]: {content}"})

        return messages
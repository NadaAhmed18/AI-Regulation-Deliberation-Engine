from typing import List, Dict, Any, Optional
from src.utils.prompt_builder import render_prompt
from src.clients.llm_client import LLMClient
from src.controllers.repository.simulation_repository import SimulationRepository


class ConversationContextManager:
    def __init__(self, simulation_id: str, topic: str, strategy: Optional[Dict[str, Any]] = None):
        self.simulation_id = simulation_id
        self.topic = topic

        strat = strategy or {"type": "sliding_window", "window_size": 4}
        raw_type = str(strat.get("type", "sliding_window")).lower()

        self.strategy_type = "full" if raw_type in ["all", "full"] else raw_type
        self.window_size = int(strat.get("window_size", 4))
        
        # Centralized repository (thread-safe singleton)
        self.repo = SimulationRepository()

    @staticmethod
    def _format_turns(turns: List[Dict[str, Any]], current_agent: Optional[str]) -> List[Dict[str, Any]]:
        """Converts database history rows into chat messages."""
        formatted = []
        for row in turns:
            name = str(row.get("agent_name", "Unknown"))
            content = str(row.get("content", ""))
            if name == current_agent:
                formatted.append({"role": "assistant", "content": content})
            else:
                formatted.append({"role": "user", "content": f"[{name}]: {content}"})
        return formatted

    def build_context_for_agent(
        self,
        system_prompt: str,
        current_agent_name: Optional[str] = None,
        allowed_speakers: Optional[List[str]] = None,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Builds contextual messages. Uses provided history or queries SimulationRepository.
        """
        raw_history = history if history is not None else self.repo.get_current_discussion_history(self.simulation_id)
        messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]

        if not raw_history:
            messages.append({
                "role": "user",
                "content": f"The debate on '{self.topic}' is now starting. As {current_agent_name}, present your opening statement."
            })
            return messages

        # 1. Visibility Matrix Filter
        if allowed_speakers is not None and current_agent_name is not None:
            permitted = set(allowed_speakers) | {current_agent_name}
            visible_history = [r for r in raw_history if r.get("agent_name") in permitted]
        else:
            visible_history = raw_history

        if not visible_history:
            return messages

        # 2. Strategy Application
        if self.strategy_type == "sliding_window":
            messages.extend(self._format_turns(visible_history[-self.window_size:], current_agent_name))

        elif self.strategy_type == "summary" and len(visible_history) > 3:
            older = visible_history[:-2]
            recent = visible_history[-2:]

            history_text = "\n".join([f"{r.get('agent_name')}: {r.get('content')}" for r in older])
            summary_prompt = render_prompt("memory_summarizer", topic=self.topic, raw_history=history_text)

            summary_res = LLMClient().generate_response([{"role": "user", "content": summary_prompt}])
            messages.append({"role": "system", "content": f"PREVIOUS DISCUSSION SUMMARY:\n{summary_res.get('content', '')}"})
            messages.extend(self._format_turns(recent, current_agent_name))

        else:  # 'full'
            messages.extend(self._format_turns(visible_history, current_agent_name))

        return messages
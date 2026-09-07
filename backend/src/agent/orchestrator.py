import json
import re
from typing import List, Dict, Any, Optional
from langfuse import observe
from src.clients.llm_client import LLMClient
from src.utils.prompt_builder import render_prompt
from src.agent.tools.tool_registry import get_tool_schemas_for_role

class Orchestrator:
    def __init__(self, provider: Optional[str] = None, model_name: Optional[str] = None):
        # The moderator gets NO tools. It is strictly a router.
        self.tools_schema = get_tool_schemas_for_role("moderator") 
        self.llm = LLMClient(provider=provider, model_name=model_name, tools=self.tools_schema)

    @observe(as_type="generation", name="orchestrator_routing")
    def decide_next_speaker(self, topic: str, personas: List[dict], messages: List[Dict[str, Any]]) -> str:
        agent_names = [p["name"] for p in personas]
        agent_summaries = "\n".join([f"- {p['name']} (Stance: {p['stance']})" for p in personas])
        recent_history = "\n".join([f"{m['role']}: {m['content']}" for m in messages[-3:]])

        prompt = render_prompt(
            "orchestrator",
            topic=topic,
            agent_summaries=agent_summaries,
            recent_history=recent_history
        )

        response = self.llm.generate_response(
            [{"role": "user", "content": prompt}],
            response_format="json_object"
        )
        content = response.get("content", "")

        # Safe extraction
        next_speaker = None
        try:
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                candidate = data.get("next_speaker", "").strip()
                if candidate in agent_names:
                    next_speaker = candidate
        except Exception:
            pass

        # Robust Fallback: If parsing fails or invalid name returned, pick first candidate that didn't just speak
        if not next_speaker:
            last_message_content = messages[-1]["content"] if messages else ""
            for name in agent_names:
                if name not in last_message_content:
                    next_speaker = name
                    break
            if not next_speaker:
                next_speaker = agent_names[0]

        return next_speaker
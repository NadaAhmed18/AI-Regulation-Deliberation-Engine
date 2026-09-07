import json
from typing import List, Dict, Any, Optional
from langfuse import observe
from src.clients.llm_client import LLMClient
from src.utils.prompt_builder import render_prompt
from src.agent.tools.tool_registry import get_tool_schemas_for_role

class Orchestrator:
    def __init__(self, provider: Optional[str] = None, model_name: Optional[str] = None):
        # The moderator gets NO tools. It is strictly a router.
        self.tools_schema = get_tool_schemas_for_role("moderator") 
        
        self.llm = LLMClient(
            provider=provider,
            model_name=model_name,
            tools=self.tools_schema # This will be []
        )

    @observe(as_type="generation", name="orchestrator_routing")
    def decide_next_speaker(self, topic: str, personas: List[dict], messages: List[Dict[str, Any]]) -> str:
        """
        Reads the history and outputs ONLY the exact name of the next agent to speak.
        """
        # Create a summary of available agents
        agent_summaries = "\n".join([f"- {p['name']} (Stance: {p['stance']})" for p in personas])
        
        # Get the last 3 messages to understand the immediate context
        recent_history = "\n".join([f"{m['role']}: {m['content']}" for m in messages[-3:]])

        prompt = render_prompt(
            "orchestrator",
            topic=topic,
            agent_summaries=agent_summaries,
            recent_history=recent_history
        )

        response = self.llm.generate_response([{"role": "user", "content": prompt}])
        next_speaker = str(response.get("content", "")).strip()
        
        return next_speaker
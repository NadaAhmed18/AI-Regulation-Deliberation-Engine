from typing import Any, Dict, List, Optional
from src.clients.llm_client import LLMClient
from src.agent.tools.tool_registry import (
    get_tool_schemas_for_role,
    execute_tool,
)
from src.agent.utils.memory import MemoryStore
from src.utils.prompt_builder import (
    build_system_prompt,
    render_initial_opinion_prompt,
)


class BaseAgent:
    def __init__(self, persona: dict, provider: Optional[str] = None, model_name: Optional[str] = None):
        self.persona = persona

        self.name = persona["name"]
        self.background = persona["background"]
        self.stance = persona["stance"]
        self.tone = persona["tone"]

        # Fetch only the tools allowed for a stakeholder (search_ai_policy, search_web)
        self.tools_schema = get_tool_schemas_for_role("stakeholder")
        
        # We also need this list to enforce security during execution
        self.allowed_tool_names = [t["function"]["name"] for t in self.tools_schema]

        self.llm = LLMClient(
            provider=provider,
            model_name=model_name,
            tools=self.tools_schema,
        )

        self.memory = MemoryStore()
        self.system_prompt = build_system_prompt(persona)

    def run_react_loop(self, user_prompt: str, max_steps: int = 5, save_to_memory: bool = True) -> str:
        history = self.memory.get_history(agent_name=self.name, limit=10)

        # FIX: Explicitly type-hint 'messages' so Pylance knows it will hold None and Lists later, not just Strings.
        messages: List[Dict[str, Any]] = [{"role": "system", "content": self.system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_prompt})

        for _ in range(max_steps):
            response = self.llm.generate_response(messages=messages)

            if response["type"] == "text":
                final_text = str(response["content"])

                if save_to_memory:
                    self.memory.save_message(
                        agent_name=self.name,
                        role="assistant",
                        content=final_text,
                        meta={"type": "opinion_snapshot"},
                    )

                return final_text

            if response["type"] == "tool_call":
                tool_name = str(response["tool_name"])
                arguments = response["arguments"]

                # Pass allowed_tools to execute_tool as a security check
                observation = execute_tool(tool_name, arguments, allowed_tools=self.allowed_tool_names)

                if save_to_memory:
                    self.memory.save_message(
                        agent_name=self.name,
                        role="tool",
                        content=observation,
                        meta={"tool_name": tool_name, "arguments": arguments},
                    )

                # Pylance is happy here now because `messages` allows Any value type
                messages.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": response.get("tool_call_id"),
                                "type": "function",
                                "function": {
                                    "name": tool_name,
                                    "arguments": str(arguments),
                                },
                            }
                        ],
                    }
                )
                
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": response.get("tool_call_id"),
                        "name": tool_name,
                        "content": observation,
                    }
                )

        return f"The agent reached the maximum number of reasoning steps ({max_steps})."

    def generate_initial_opinion(self, topic: str) -> dict:
        # Pre-fetch the evidence before starting the reasoning loop
        retrieved_context = execute_tool("search_ai_policy", {"query": topic})

        prompt = render_initial_opinion_prompt(
            persona=self.persona,
            retrieved_context=retrieved_context,
            memory_summary="",
            topic=topic,
        )

        final_text = self.run_react_loop(prompt)

        return {
            "name": self.name,
            "stance": self.stance,
            "opinion": final_text,
        }
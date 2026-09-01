from src.clients.llm_client import LLMClient
from src.agent.tools.tool_registry import (
    get_all_tool_schemas,
    execute_tool,
)
from src.agent.memory import MemoryStore
from src.utils.prompt_builder import (
    build_system_prompt,
    render_initial_opinion_prompt,
)


class BaseAgent:

    def __init__(self, persona: dict, provider: str = None, model_name: str = None):
        self.persona = persona

        self.name = persona["name"]
        self.background = persona["background"]
        self.stance = persona["stance"]
        self.tone = persona["tone"]

        self.tools_schema = get_all_tool_schemas()

        self.llm = LLMClient(
            provider=provider,
            model_name=model_name,
            tools=self.tools_schema,
        )

        self.memory = MemoryStore()
        self.system_prompt = build_system_prompt(persona)

    def run_react_loop(self, user_prompt: str, max_steps: int = 5, save_to_memory: bool = True) -> str:
        history = self.memory.get_history(agent_name=self.name, limit=10)

        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_prompt})

        for _ in range(max_steps):
            response = self.llm.generate_response(messages=messages)

            if response["type"] == "text":
                final_text = response["content"]

                if save_to_memory:
                    self.memory.save_message(
                        agent_name=self.name,
                        role="assistant",
                        content=final_text,
                        meta={"type": "opinion_snapshot"},
                    )

                return final_text

            if response["type"] == "tool_call":
                tool_name = response["tool_name"]
                arguments = response["arguments"]

                observation = execute_tool(tool_name, arguments)

                if save_to_memory:
                    self.memory.save_message(
                        agent_name=self.name,
                        role="tool",
                        content=observation,
                        meta={"tool_name": tool_name, "arguments": arguments},
                    )

                messages.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": response.get("tool_call_id"),
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
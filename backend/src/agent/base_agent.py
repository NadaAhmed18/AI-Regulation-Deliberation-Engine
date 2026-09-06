import json
import re
from typing import Any, Dict, List, Optional, Tuple
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

    def run_react_loop(self, user_prompt: str, max_steps: int = 5, save_to_memory: bool = True) -> Tuple[str, List[str]]:
        """
        Executes an autonomous ReAct loop where the agent decides which tools to call.
        Returns a tuple: (Final Generated Text, List of Cited URLs extracted from tools).
        """
        history = self.memory.get_history(agent_name=self.name, limit=10)

        messages: List[Dict[str, Any]] = [{"role": "system", "content": self.system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_prompt})

        discovered_urls = set()

        # Pre-save the user's prompt to memory if requested
        if save_to_memory:
            self.memory.save_message(self.name, "user", user_prompt)

        for step in range(max_steps):
            response = self.llm.generate_response(messages=messages)

            # 1. Agent finished thinking and provided final text
            if response["type"] == "text":
                final_text = str(response["content"])

                if save_to_memory:
                    self.memory.save_message(
                        agent_name=self.name,
                        role="assistant",
                        content=final_text,
                        meta={"type": "opinion_snapshot", "cited_sources": list(discovered_urls)},
                    )

                return final_text, list(discovered_urls)

            # 2. Agent autonomously decided to call a tool
            if response["type"] == "tool_call":
                tool_name = str(response["tool_name"])
                arguments = response["arguments"]
                tool_call_id = response.get("tool_call_id", f"call_{step}")
                
                # Convert dict arguments back to string format for the OpenAI spec
                arguments_str = json.dumps(arguments) if isinstance(arguments, dict) else str(arguments)

                print(f"[{self.name}] 🛠️ Step {step + 1}: Autonomously calling tool '{tool_name}' with args: {arguments}")
                
                # Execute the tool
                observation = execute_tool(tool_name, arguments, allowed_tools=self.allowed_tool_names)

                # Track sources: Extract any URLs returned by the tool to prove grounding
                found_urls = re.findall(r'URL:\s*(https?://[^\s\n]+)', observation)
                discovered_urls.update(found_urls)

                # Format messages for the next LLM iteration strictly adhering to OpenAI spec
                assistant_message = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": tool_call_id,
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": arguments_str,
                        },
                    }],
                }
                
                tool_message = {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "name": tool_name,
                    "content": observation,
                }

                messages.append(assistant_message)
                messages.append(tool_message)

                # Save the tool-call chain to memory so the agent remembers its own actions
                if save_to_memory:
                    self.memory.save_message(
                        agent_name=self.name,
                        role="assistant",
                        content=None,
                        meta={"tool_calls": assistant_message["tool_calls"]}
                    )
                    self.memory.save_message(
                        agent_name=self.name,
                        role="tool",
                        content=observation,
                        meta={"tool_call_id": tool_call_id, "tool_name": tool_name},
                    )

        return f"The agent reached the maximum number of reasoning steps ({max_steps}).", list(discovered_urls)

    def generate_initial_opinion(self, topic: str) -> dict:
        """
        Kicks off the agent using the strict render_initial_opinion_prompt template.
        The agent is provided NO pre-fetched context, forcing it to use its tools autonomously.
        """
        print(f"\n[{self.name}] 🚀 Starting autonomous reasoning for topic: '{topic}'...")

        # 1. The instruction to inject into the {retrieved_context} placeholder
        # This explicitly tells the LLM it must use tools to fill its own context window.
        force_tool_usage_instruction = (
            "No evidence has been provided to you yet. You MUST use your available tools "
            "('search_ai_policy' and/or 'search_web') to research this topic and gather "
            "factual evidence before stating your final position."
        )

        # 2. Strictly use the required template builder
        prompt = render_initial_opinion_prompt(
            persona=self.persona,
            retrieved_context=force_tool_usage_instruction,
            memory_summary="",
            topic=topic,
        )

        # 3. Run the autonomous ReAct loop
        final_text, cited_sources = self.run_react_loop(prompt)

        return {
            "name": self.name,
            "stance": self.stance,
            "opinion": final_text,
            "cited_sources": cited_sources
        }
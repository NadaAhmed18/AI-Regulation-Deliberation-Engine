import json
import re
from typing import Any, Dict, List, Optional, Tuple

from langfuse import observe

from src.config import MAX_REACT_STEPS
from src.clients.llm_client import LLMClient
from src.agent.tools.tool_registry import (
    get_tool_schemas_for_role,
    execute_tool,
)
from src.utils.prompt_builder import render_prompt


class BaseAgent:
    def __init__(
        self, 
        persona: dict,
        topic: str,
        provider: Optional[str] = None, 
        model_name: Optional[str] = None
    ):
        self.persona = persona
        self.topic = topic
        self.name: str = persona["name"]
        self.background: str = persona["background"]
        self.stance: str = persona["stance"]
        self.tone: str = persona.get("tone", "Professional, analytical")

        # Fetch tools allowed for a stakeholder (search_ai_policy, search_web, learn_and_ingest_url)
        self.tools_schema = get_tool_schemas_for_role("stakeholder")
        self.allowed_tool_names = [t["function"]["name"] for t in self.tools_schema]

        self.llm = LLMClient(
            provider=provider,
            model_name=model_name,
            tools=self.tools_schema,
        )

        # Build system prompt dynamically from prompts/system_agent.txt
        self.system_prompt = render_prompt(
            "system_agent",
            persona_name=self.name,
            topic=self.topic,
            persona_background=self.background,
            persona_stance=self.stance,
            persona_tone=self.tone,
        )

    @observe(as_type="generation", name="agent_react_loop")
    def run_react_loop(
        self, 
        messages: Optional[List[Dict[str, Any]]] = None,
        user_prompt: Optional[str] = None, 
        max_steps: int = MAX_REACT_STEPS
    ) -> Tuple[str, List[str]]:
        """
        Executes an autonomous ReAct loop where the agent decides which tools to call.
        Can receive a full contextual message list (from ContextManager) OR a single user_prompt.
        
        Returns:
            Tuple[str, List[str]]: (Final text response, List of discovered/cited URLs)
        """
        # Prepare the active messages list
        if messages is not None:
            active_messages: List[Dict[str, Any]] = list(messages)
        else:
            active_messages = [{"role": "system", "content": self.system_prompt}]
            if user_prompt:
                active_messages.append({"role": "user", "content": user_prompt})

        discovered_urls: set[str] = set()
        executed_calls = set()

        for step in range(max_steps):
            response = self.llm.generate_response(messages=active_messages)

            # 1. Final answer delivered
            if response["type"] == "text":
                return str(response["content"]), list(discovered_urls)

            # 2. Tool requested
            if response["type"] == "tool_call":
                tool_name = str(response["tool_name"])
                arguments = response["arguments"]
                tool_call_id = response.get("tool_call_id", f"call_{step}")
                
                arguments_str = json.dumps(arguments, sort_keys=True) if isinstance(arguments, dict) else str(arguments)
                call_signature = (tool_name, arguments_str)

                # Loop detection guard
                if call_signature in executed_calls:
                    print(f"[{self.name}] ⚠️ Loop detected: Attempted identical tool call '{tool_name}'. Halting loop.")
                    observation = "Error: You have already executed this exact tool with these parameters. Formulate your final answer immediately without repeating calls."
                else:
                    executed_calls.add(call_signature)
                    print(f"[{self.name}] 🛠️ Step {step + 1}: Calling tool '{tool_name}' with args: {arguments}")
                    observation = execute_tool(tool_name, arguments, allowed_tools=self.allowed_tool_names)

                # Track sources: Extract any URLs returned in tool output
                found_urls = re.findall(r'URL:\s*(https?://[^\s\n]+)', observation)
                discovered_urls.update(found_urls)

                # Append assistant tool call and tool observation (OpenAI specification format)
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

                active_messages.append(assistant_message)
                active_messages.append(tool_message)

        return f"The agent reached the maximum number of reasoning steps ({max_steps}).", list(discovered_urls)
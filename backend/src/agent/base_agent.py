import json
import re
from typing import Any, Dict, List, Optional, Tuple, Iterator

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
        model_name: Optional[str] = None
    ):
        self.persona = persona
        self.topic = topic
        self.name: str = persona["name"]
        self.background: str = persona["background"]
        self.stance: str = persona["stance"]
        self.tone: str = persona.get("tone", "Professional, analytical")
        self.tools_schema = get_tool_schemas_for_role("stakeholder")
        self.allowed_tool_names = [t["function"]["name"] for t in self.tools_schema]

        self.llm = LLMClient(
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

    def run_react_loop_stream(
        self,
        messages: Optional[List[Dict[str, Any]]] = None,
        user_prompt: Optional[str] = None,
        max_steps: int = MAX_REACT_STEPS,
    ) -> Iterator[Dict[str, Any]]:
        """
        Executes the ReAct loop and streams out live events:
        - {"type": "thinking", "agent": name, "content": "..."}
        - {"type": "token", "agent": name, "content": "..."}
        - {"type": "tool_start", "agent": name, "tool_name": "...", "arguments": {...}}
        - {"type": "tool_end", "agent": name, "tool_name": "...", "observation": "..."}
        - {"type": "final", "agent": name, "content": "...", "sources": [...]}
        """
        active_messages: List[Dict[str, Any]] = (
            list(messages) if messages is not None
            else [{"role": "system", "content": self.system_prompt}]
        )
        if messages is None and user_prompt:
            active_messages.append({"role": "user", "content": user_prompt})

        discovered_urls: set[str] = set()
        executed_calls = set()

        for step in range(max_steps):
            stream = self.llm.generate_stream(messages=active_messages)

            tool_call_detected = None
            text_accumulator: list[str] = []

            for event in stream:
                event_type = event.get("type")

                if event_type == "thinking":
                    yield {
                        "type": "thinking",
                        "agent": self.name,
                        "content": event.get("content", ""),
                    }

                elif event_type == "token":
                    chunk = event.get("content", "")
                    text_accumulator.append(chunk)
                    yield {
                        "type": "token",
                        "agent": self.name,
                        "content": chunk,
                    }

                elif event_type == "tool_call":
                    tool_call_detected = event

            # If it was a standard text answer (no tool call requested), we are done!
            if not tool_call_detected:
                final_text = "".join(text_accumulator).strip()
                yield {
                    "type": "final",
                    "agent": self.name,
                    "content": final_text,
                    "sources": list(discovered_urls),
                }
                return

            # Tool call requested by agent
            tool_name = str(tool_call_detected["tool_name"])
            arguments = tool_call_detected.get("arguments", {})
            tool_call_id = tool_call_detected.get("tool_call_id", f"call_{step}")

            arguments_str = json.dumps(arguments, sort_keys=True) if isinstance(arguments, dict) else str(arguments)
            call_signature = (tool_name, arguments_str)

            yield {
                "type": "tool_start",
                "agent": self.name,
                "tool_name": tool_name,
                "arguments": arguments,
            }

            if call_signature in executed_calls:
                observation = "Error: You have already executed this exact tool. Formulate your final response immediately."
            else:
                executed_calls.add(call_signature)
                observation = execute_tool(tool_name, arguments, allowed_tools=self.allowed_tool_names)

            # Extract cited URLs from observation
            found_urls = re.findall(r'URL:\s*(https?://[^\s\n]+)', observation)
            discovered_urls.update(found_urls)

            yield {
                "type": "tool_end",
                "agent": self.name,
                "tool_name": tool_name,
                "observation": observation[:400] + "..." if len(observation) > 400 else observation,
            }

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

        yield {
            "type": "final",
            "agent": self.name,
            "content": f"The agent reached the maximum number of reasoning steps ({max_steps}).",
            "sources": list(discovered_urls),
        }

    @observe(as_type="generation", name="agent_react_loop")
    def run_react_loop(
        self, 
        messages: Optional[List[Dict[str, Any]]] = None,
        user_prompt: Optional[str] = None, 
        max_steps: int = MAX_REACT_STEPS
    ) -> Tuple[str, List[str]]:
        """Synchronous ReAct loop for non-streaming calls."""
        final_content = ""
        sources: List[str] = []

        for event in self.run_react_loop_stream(messages=messages, user_prompt=user_prompt, max_steps=max_steps):
            if event.get("type") == "final":
                final_content = event.get("content", "")
                sources = event.get("sources", [])

        return final_content, sources
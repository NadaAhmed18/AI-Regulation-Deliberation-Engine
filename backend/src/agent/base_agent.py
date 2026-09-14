import json
import re
from typing import Any, Dict, List, Optional, Tuple, Iterator
from langfuse import observe

from src.config import MAX_REACT_STEPS
from src.clients.llm_client import LLMClient
from src.agent.tools.tool_registry import get_tool_schemas_for_role, execute_tool
from src.utils.prompt_builder import render_prompt


class BaseAgent:
    def __init__(self, persona: dict, topic: str, model_name: Optional[str] = None):
        self.persona = persona
        self.topic = topic
        self.name: str = persona["name"]
        self.stance: str = persona["stance"]
        self.tools_schema = get_tool_schemas_for_role("stakeholder")
        self.allowed_tool_names = [t["function"]["name"] for t in self.tools_schema]

        self.llm = LLMClient(model_name=model_name, tools=self.tools_schema)
        self.system_prompt = render_prompt(
            "system_agent",
            persona_name=self.name,
            topic=self.topic,
            persona_background=persona.get("background", ""),
            persona_stance=self.stance,
            persona_tone=persona.get("tone", "Professional, analytical"),
        )

    def run_react_loop_stream(
        self,
        messages: Optional[List[Dict[str, Any]]] = None,
        user_prompt: Optional[str] = None,
        max_steps: int = MAX_REACT_STEPS,
    ) -> Iterator[Dict[str, Any]]:
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
                etype = event.get("type")
                if etype in ("thinking", "token"):
                    yield {"type": etype, "agent": self.name, "content": event.get("content", "")}
                    if etype == "token":
                        text_accumulator.append(event.get("content", ""))
                elif etype == "tool_call":
                    tool_call_detected = event

            # If no tool call was made, we have our final synthesized response
            if not tool_call_detected:
                yield {
                    "type": "final",
                    "agent": self.name,
                    "content": "".join(text_accumulator).strip(),
                    "sources": list(discovered_urls),
                }
                return

            # Tool Execution
            tool_name = str(tool_call_detected["tool_name"])
            arguments = tool_call_detected.get("arguments", {})
            call_id = tool_call_detected.get("tool_call_id", f"call_{step}")
            args_str = json.dumps(arguments, sort_keys=True) if isinstance(arguments, dict) else str(arguments)
            call_sig = (tool_name, args_str)

            yield {"type": "tool_start", "agent": self.name, "tool_name": tool_name, "arguments": arguments}

            if call_sig in executed_calls:
                observation = "Error: Repeated tool call with identical arguments. Formulate your final response immediately."
            else:
                executed_calls.add(call_sig)
                observation = execute_tool(tool_name, arguments, allowed_tools=self.allowed_tool_names)

            discovered_urls.update(re.findall(r'URL:\s*(https?://[^\s\n]+)', observation))
            preview = observation[:1000] + "..." if len(observation) > 1000 else observation
            yield {"type": "tool_end", "agent": self.name, "tool_name": tool_name, "observation": preview}

            active_messages.extend([
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{"id": call_id, "type": "function", "function": {"name": tool_name, "arguments": args_str}}],
                },
                {"role": "tool", "tool_call_id": call_id, "name": tool_name, "content": observation},
            ])

        yield {
            "type": "final",
            "agent": self.name,
            "content": f"Reached max reasoning steps ({max_steps}).",
            "sources": list(discovered_urls),
        }

    @observe(as_type="generation", name="agent_react_loop")
    def run_react_loop(
        self,
        messages: Optional[List[Dict[str, Any]]] = None,
        user_prompt: Optional[str] = None,
        max_steps: int = MAX_REACT_STEPS
    ) -> Tuple[str, List[str]]:
        final_content, sources = "", []
        for event in self.run_react_loop_stream(messages=messages, user_prompt=user_prompt, max_steps=max_steps):
            if event.get("type") == "final":
                final_content = event.get("content", "")
                sources = event.get("sources", [])
        return final_content, sources
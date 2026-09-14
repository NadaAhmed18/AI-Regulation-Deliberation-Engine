import json
from typing import Dict, Optional, Any, Iterator, List
from langfuse.openai import OpenAI as LangfuseOpenAI  # type: ignore

from src.config import (
    DEFAULT_MODEL,
    OPENROUTER_API_KEY,
    DEFAULT_REASONING_EFFORT,
    DEFAULT_MAX_COMPLETION_TOKENS,
)


class LLMClient:
    """OpenRouter LLM Client with Langfuse observability."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        default_reasoning_effort: Optional[str] = DEFAULT_REASONING_EFFORT,
        default_max_tokens: int = DEFAULT_MAX_COMPLETION_TOKENS,
    ):
        if not OPENROUTER_API_KEY:
            raise RuntimeError("Missing OPENROUTER_API_KEY in environment variables.")

        self.model_name = model_name or DEFAULT_MODEL
        self.tools = tools or []
        self.default_reasoning_effort = default_reasoning_effort
        self.default_max_tokens = default_max_tokens

        self._client = LangfuseOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
        )

    def _prepare_kwargs(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: Optional[int],
        reasoning_effort: Optional[str],
        stream: bool = False,
    ) -> Dict[str, Any]:
        """Builds standardized chat completion parameters."""
        effort = reasoning_effort if reasoning_effort is not None else self.default_reasoning_effort

        kwargs: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": max_tokens or self.default_max_tokens,
            "stream": stream,
        }

        if effort and str(effort).lower() != "none":
            kwargs["extra_body"] = {"reasoning": {"effort": str(effort).lower()}}

        if self.tools:
            kwargs["tools"] = self.tools

        return kwargs

    def generate_response(
        self,
        messages: List[Dict[str, Any]],
        response_format: str = "text",
        max_tokens: Optional[int] = None,
        reasoning_effort: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Synchronous generation with tool call resolution."""
        kwargs = self._prepare_kwargs(messages, max_tokens, reasoning_effort, stream=False)

        if response_format == "json_object":
            kwargs["response_format"] = {"type": "json_object"}

        completion = self._client.chat.completions.create(**kwargs)
        message = completion.choices[0].message

        if message.tool_calls:
            tc = message.tool_calls[0]
            try:
                args = json.loads(tc.function.arguments)
            except Exception:
                args = {"raw": tc.function.arguments}

            return {
                "type": "tool_call",
                "tool_name": tc.function.name,
                "arguments": args,
                "tool_call_id": tc.id,
            }

        return {"type": "text", "content": message.content or ""}

    def generate_stream(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
        reasoning_effort: Optional[str] = None,
    ) -> Iterator[Dict[str, Any]]:
        """Real-time token and reasoning streaming."""
        kwargs = self._prepare_kwargs(messages, max_tokens, reasoning_effort, stream=True)
        response_stream = self._client.chat.completions.create(**kwargs)

        full_content: List[str] = []
        tc_acc: Dict[int, Dict[str, Any]] = {}

        for chunk in response_stream:
            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            # Reasoning / Thinking tokens (DeepSeek, OpenRouter, OpenAI)
            reasoning = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None)
            if reasoning:
                yield {"type": "thinking", "content": reasoning}

            # Generation tokens
            if delta.content:
                full_content.append(delta.content)
                yield {"type": "token", "content": delta.content}

            # Incremental tool call chunks
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tc_acc:
                        tc_acc[idx] = {"id": tc.id or f"call_{idx}", "name": "", "arguments": ""}
                    if tc.id:
                        tc_acc[idx]["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            tc_acc[idx]["name"] += tc.function.name
                        if tc.function.arguments:
                            tc_acc[idx]["arguments"] += tc.function.arguments

        if tc_acc:
            for tc_data in tc_acc.values():
                try:
                    args = json.loads(tc_data["arguments"])
                except Exception:
                    args = {"raw": tc_data["arguments"]}

                yield {
                    "type": "tool_call",
                    "tool_name": tc_data["name"],
                    "arguments": args,
                    "tool_call_id": tc_data["id"],
                }
            return

        yield {"type": "done", "full_content": "".join(full_content)}
import json
from typing import Dict, Optional, Any, Iterator, List

from langfuse.openai import OpenAI as LangfuseOpenAI # type: ignore

from src.config import (
    DEFAULT_MODEL,
    OPENROUTER_API_KEY,
    DEFAULT_REASONING_EFFORT,
    DEFAULT_MAX_COMPLETION_TOKENS,
)


class LLMClient:
    """
    Dedicated OpenRouter LLM Client with Langfuse observability.
    Supports standard generation, structured JSON mode, tool calling, 
    and real-time streaming with reasoning/thinking extraction.
    """

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

        # Direct drop-in: LangfuseOpenAI instruments OpenRouter calls automatically
        self._client = LangfuseOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
        )

    def generate_response(
        self,
        messages: List[Dict[str, Any]],
        response_format: str = "text",
        max_tokens: Optional[int] = None,
        reasoning_effort: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Synchronous non-streaming generation with tool call resolution.
        """
        resolved_max_tokens = max_tokens or self.default_max_tokens
        resolved_effort = (
            reasoning_effort
            if reasoning_effort is not None
            else self.default_reasoning_effort
        )

        kwargs: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": resolved_max_tokens,
        }

        # Apply reasoning effort if explicitly supported and configured
        if resolved_effort and str(resolved_effort).lower() != "none":
            kwargs["extra_body"] = {
                "reasoning": {
                    "effort": str(resolved_effort).lower()
                }
            }

        if self.tools:
            kwargs["tools"] = self.tools

        if response_format == "json_object":
            kwargs["response_format"] = {"type": "json_object"}

        completion = self._client.chat.completions.create(**kwargs)
        message = completion.choices[0].message

        # Resolve autonomous tool call requests
        if message.tool_calls:
            tool_call = message.tool_calls[0]
            try:
                args = json.loads(tool_call.function.arguments)
            except Exception:
                args = {"raw": tool_call.function.arguments}

            return {
                "type": "tool_call",
                "tool_name": tool_call.function.name,
                "arguments": args,
                "tool_call_id": tool_call.id,
            }

        return {
            "type": "text",
            "content": message.content or "",
        }

    def generate_stream(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
        reasoning_effort: Optional[str] = None,
    ) -> Iterator[Dict[str, Any]]:
        """
        Streams events in real-time for frontend consumption:
        - {"type": "thinking", "content": "..."}      -> Model reasoning / scratchpad
        - {"type": "token", "content": "..."}         -> Standard text generation token
        - {"type": "tool_call", "tool_name": "...",   -> Complete assembled tool call
           "arguments": {...}, "tool_call_id": "..."}
        - {"type": "done", "full_content": "..."}     -> Stream finished successfully
        """
        resolved_max_tokens = max_tokens or self.default_max_tokens
        resolved_effort = (
            reasoning_effort
            if reasoning_effort is not None
            else self.default_reasoning_effort
        )

        kwargs: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": resolved_max_tokens,
            "stream": True,
        }

        if resolved_effort and str(resolved_effort).lower() != "none":
            kwargs["extra_body"] = {
                "reasoning": {
                    "effort": str(resolved_effort).lower()
                }
            }

        if self.tools:
            kwargs["tools"] = self.tools

        response_stream = self._client.chat.completions.create(**kwargs)

        full_content_chunks: List[str] = []
        tool_call_accumulator: Dict[int, Dict[str, Any]] = {}

        for chunk in response_stream:
            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            # 1. Stream Thinking / Reasoning Content (OpenRouter / DeepSeek / OpenAI reasoning tokens)
            reasoning_chunk = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None)
            if reasoning_chunk:
                yield {
                    "type": "thinking",
                    "content": reasoning_chunk,
                }

            # 2. Stream Standard Content Tokens
            if delta.content:
                full_content_chunks.append(delta.content)
                yield {
                    "type": "token",
                    "content": delta.content,
                }

            # 3. Assemble Incremental Tool Call Chunks
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_call_accumulator:
                        tool_call_accumulator[idx] = {
                            "id": tc.id or f"call_{idx}",
                            "name": (tc.function.name if tc.function and tc.function.name else ""),
                            "arguments": (tc.function.arguments if tc.function and tc.function.arguments else ""),
                        }
                    else:
                        if tc.id:
                            tool_call_accumulator[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                tool_call_accumulator[idx]["name"] += tc.function.name
                            if tc.function.arguments:
                                tool_call_accumulator[idx]["arguments"] += tc.function.arguments

        # If any tool calls were requested, yield the assembled tool call
        if tool_call_accumulator:
            for _, tc_data in tool_call_accumulator.items():
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

        # Regular text completion finished
        yield {
            "type": "done",
            "full_content": "".join(full_content_chunks),
        }
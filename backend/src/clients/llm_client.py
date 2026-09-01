import json
import os
from openai import OpenAI
from src.config import DEFAULT_PROVIDER,DEFAULT_MODEL,OPENROUTER_BASE_URLS



class LLMClient:

    def __init__(self, provider: str = None, model_name: str = None, tools: list = None):
        self.provider = provider or DEFAULT_PROVIDER
        self.model_name = model_name or DEFAULT_MODEL
        self.tools = tools or []

        base_url = OPENROUTER_BASE_URLS.get(self.provider)
        if base_url is None:
            raise ValueError(f"Unsupported provider: {self.provider}")

        api_key_env = f"{self.provider.upper()}_API_KEY"
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise RuntimeError(f"Missing {api_key_env} environment variable")

        self._client = OpenAI(base_url=base_url, api_key=api_key)

    def generate_response(self, messages: list) -> dict:
   
        kwargs = {
            "model": self.model_name,
            "messages": messages,
        }
        if self.tools:
            kwargs["tools"] = self.tools

        completion = self._client.chat.completions.create(**kwargs)
        message = completion.choices[0].message

        if message.tool_calls:
            tool_call = message.tool_calls[0]
            try:
                arguments = json.loads(tool_call.function.arguments)
            except (json.JSONDecodeError, TypeError):
                arguments = {}

            return {
                "type": "tool_call",
                "tool_name": tool_call.function.name,
                "arguments": arguments,
                "tool_call_id": tool_call.id,
            }

        return {
            "type": "text",
            "content": message.content or "",
        }
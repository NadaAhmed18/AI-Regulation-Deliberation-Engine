import json
import os
import gc
import re
from typing import Dict, Optional, Any

# Langfuse imports
from langfuse.openai import OpenAI as LangfuseOpenAI # type: ignore
from langfuse import observe, get_client

from src.config import (
    DEFAULT_PROVIDER,
    DEFAULT_MODEL,
    OPENROUTER_API_KEY,
    DEFAULT_REASONING_EFFORT,
    DEFAULT_MAX_COMPLETION_TOKENS,
)


class LLMClient:
    def __init__(
        self,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        tools: Optional[list] = None,
        default_reasoning_effort: Optional[str] = DEFAULT_REASONING_EFFORT,
        default_max_tokens: int = DEFAULT_MAX_COMPLETION_TOKENS,
    ):
        self.provider = (provider or DEFAULT_PROVIDER).lower()
        self.model_name = model_name or DEFAULT_MODEL
        self.tools = tools or []
        
        # Default thinking/reasoning parameters
        self.default_reasoning_effort = default_reasoning_effort
        self.default_max_tokens = default_max_tokens

        self._client: Optional[LangfuseOpenAI] = None
        self.hf_model: Any = None
        self.hf_tokenizer: Any = None

        if self.provider == "openrouter":
            if not OPENROUTER_API_KEY:
                raise RuntimeError("Missing OPENROUTER_API_KEY")

            # Drop-in replacement: Langfuse automatically traces the OpenRouter API calls!
            self._client = LangfuseOpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)
            
        elif self.provider == "huggingface":
            print(f"[*] Initializing local HuggingFace model: {self.model_name}")
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            dtype = torch.bfloat16 if self.device == "cuda" else torch.float32
            
            self.hf_tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.hf_model = AutoModelForCausalLM.from_pretrained(
                self.model_name, torch_dtype=dtype, device_map="auto" if self.device == "cuda" else None
            )

    def generate_response(
        self,
        messages: list,
        response_format: str = "text",
        max_tokens: Optional[int] = None,
        reasoning_effort: Optional[str] = None,
    ) -> dict:
        """Routes the request. Supports per-call overrides for tokens & reasoning effort."""
        if self.provider == "openrouter":
            return self._generate_openrouter(
                messages=messages,
                response_format=response_format,
                max_tokens=max_tokens,
                reasoning_effort=reasoning_effort,
            )
        elif self.provider == "huggingface":
            return self._generate_huggingface(messages, response_format)
        raise ValueError(f"Unknown provider: {self.provider}")

    # No decorator needed here; LangfuseOpenAI handles it automatically under the hood
    def _generate_openrouter(
        self,
        messages: list,
        response_format: str = "text",
        max_tokens: Optional[int] = None,
        reasoning_effort: Optional[str] = None,
    ) -> dict:
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

        # Send ONLY effort in reasoning (if specified and not "none")
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

        assert self._client is not None, "OpenRouter client is not initialized"
        completion = self._client.chat.completions.create(**kwargs)
        message = completion.choices[0].message

        if message.tool_calls:
            tool_call = message.tool_calls[0]
            try:
                args = json.loads(tool_call.function.arguments)
            except Exception:
                args = {}
            return {
                "type": "tool_call",
                "tool_name": tool_call.function.name,
                "arguments": args,
                "tool_call_id": tool_call.id,
            }

        return {"type": "text", "content": message.content or ""}

    # We manually trace HuggingFace using the @observe decorator
    @observe(as_type="generation", name="hf_local_generation")
    def _generate_huggingface(self, messages: list, response_format: str = "text") -> dict:
        tokenizer, model = self.hf_tokenizer, self.hf_model
        
        # 1. ENFORCE JSON IN PROMPT: If JSON is requested, ensure the prompt explicitly demands it
        active_messages = list(messages)
        if response_format == "json_object":
            # Append a system reminder to guarantee valid syntax
            active_messages.append({
                "role": "system", 
                "content": "CRITICAL: You must output ONLY a valid JSON object or array. Do not include markdown formatting, backticks, or any conversational text."
            })
        
        # Log input into Langfuse manually for HF
        get_client().update_current_generation(input=active_messages, model=self.model_name)
        
        prompt = tokenizer.apply_chat_template(
            active_messages, 
            tools=self.tools or None, 
            tokenize=False, 
            add_generation_prompt=True
        )
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        outputs = model.generate(**inputs, max_new_tokens=1024, pad_token_id=tokenizer.eos_token_id)
        
        response_text = tokenizer.decode(outputs[0][inputs.input_ids.shape[-1]:], skip_special_tokens=True).strip()
        
        # 2. HANDLE JSON ENFORCEMENT POST-GENERATION
        if response_format == "json_object":
            # Strip markdown formatting like ```json ... ```
            cleaned_text = re.sub(r'^```(?:json)?\s*', '', response_text, flags=re.MULTILINE)
            cleaned_text = re.sub(r'\s*```$', '', cleaned_text, flags=re.MULTILINE).strip()
            
            # Extract only the outermost { ... } or [ ... ]
            json_match = re.search(r'(\{.*\}|\[.*\])', cleaned_text, re.DOTALL)
            if json_match:
                cleaned_text = json_match.group(1)

            # Validate by parsing and re-serializing
            try:
                parsed_json = json.loads(cleaned_text)
                response_text = json.dumps(parsed_json)  # Guarantees 100% syntactically valid JSON string
            except json.JSONDecodeError as e:
                print(f"[!] Warning: HF model output invalid JSON: {e}. Raw text: {response_text}")
                # Fallback to an empty json structure so callers don't crash
                response_text = "{}"

        # Log final output into Langfuse
        get_client().update_current_generation(output=response_text)

        # 3. Tool call parsing (same as before)
        if self.tools and "{" in response_text and "}" in response_text and response_format != "json_object":
            match = re.search(r'(\{.*?\})', response_text, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(1))
                    if "name" in parsed and "arguments" in parsed:
                        return {
                            "type": "tool_call", 
                            "tool_name": parsed["name"], 
                            "arguments": parsed["arguments"], 
                            "tool_call_id": "call_hf_" + os.urandom(4).hex()
                        }
                except Exception:
                    pass

        return {"type": "text", "content": response_text}

    def __del__(self):
        """Cleanup function to delete the model and free VRAM/RAM when the agent is destroyed."""
        if getattr(self, 'provider', None) == "huggingface":
            # Delete model and tokenizer references
            if getattr(self, 'hf_model', None) is not None:
                del self.hf_model
            if getattr(self, 'hf_tokenizer', None) is not None:
                del self.hf_tokenizer
            
            # Force garbage collection and empty CUDA cache
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass
                
            gc.collect()
            print("[*] HuggingFace model deleted and GPU memory freed.")
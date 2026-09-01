import json
import os
import gc
import re
from typing import Optional, Any
from openai import OpenAI
from src.config import DEFAULT_PROVIDER, DEFAULT_MODEL


class LLMClient:
    def __init__(self, provider: Optional[str] = None, model_name: Optional[str] = None, tools: Optional[list] = None):
        self.provider = (provider or DEFAULT_PROVIDER).lower()
        self.model_name = model_name or DEFAULT_MODEL
        self.tools = tools or []
        
        # Placeholders for active clients/models
        self._client: Optional[OpenAI] = None
        self.hf_model: Any = None
        self.hf_tokenizer: Any = None

        if self.provider == "openrouter":
            api_key_env = f"{self.provider.upper()}_API_KEY"
            api_key = os.environ.get(api_key_env)
            if not api_key:
                raise RuntimeError(f"Missing {api_key_env} environment variable")

            self._client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
            
        elif self.provider == "huggingface":
            print(f"[*] Initializing local HuggingFace model: {self.model_name}")
            # Lazy import to avoid loading massive ML libraries if we are just using OpenRouter
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            dtype = torch.bfloat16 if self.device == "cuda" else torch.float32
            
            self.hf_tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.hf_model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=dtype,
                device_map="auto" if self.device == "cuda" else None
            )
        else:
            raise ValueError(f"Unsupported provider: {self.provider}. Please use 'openrouter' or 'huggingface'.")

    def generate_response(self, messages: list) -> dict:
        """Routes the generation request to the correct provider backend."""
        if self.provider == "openrouter":
            return self._generate_openrouter(messages)
        elif self.provider == "huggingface":
            return self._generate_huggingface(messages)
            
        # Fallback to satisfy strict type-checkers (reportReturnType)
        raise ValueError(f"Unknown provider: {self.provider}")

    def _generate_openrouter(self, messages: list) -> dict:
        # Guard against None to satisfy Pylance
        if self._client is None:
            raise RuntimeError("OpenRouter client is not initialized.")

        kwargs: dict[str, Any] = {
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

    def _generate_huggingface(self, messages: list) -> dict:
        # Guard against None to satisfy Pylance
        if self.hf_tokenizer is None or self.hf_model is None:
            raise RuntimeError("HuggingFace model is not initialized.")
            
        # Cast to Any locally so Pylance stops complaining about complex HF signatures
        tokenizer: Any = self.hf_tokenizer
        model: Any = self.hf_model
        
        # Apply the chat template. If the HF model supports tools, it will format the prompt accordingly.
        prompt = tokenizer.apply_chat_template(
            messages, 
            tools=self.tools if self.tools else None,
            tokenize=False, 
            add_generation_prompt=True
        )
        
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        
        outputs = model.generate(
            **inputs, 
            max_new_tokens=1024,
            pad_token_id=tokenizer.eos_token_id
        )
        
        # Extract only the newly generated text
        response_text = tokenizer.decode(
            outputs[0][inputs.input_ids.shape[-1]:], 
            skip_special_tokens=True
        ).strip()

        # Simple Regex Fallback parser for Hugging Face tool outputs
        # Open source models output tools in varying formats. This attempts to catch standard JSON tool calls.
        if self.tools and "{" in response_text and "}" in response_text:
            try:
                json_match = re.search(r'(\{.*?\})', response_text, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group(1))
                    # Check if the JSON resembles a tool call schema
                    if "name" in parsed and "arguments" in parsed:
                        return {
                            "type": "tool_call",
                            "tool_name": parsed["name"],
                            "arguments": parsed["arguments"],
                            "tool_call_id": "call_hf_" + os.urandom(4).hex()
                        }
            except Exception:
                pass # If JSON parsing fails, fall back to treating it as normal text

        return {
            "type": "text",
            "content": response_text
        }

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
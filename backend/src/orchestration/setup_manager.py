import json
import re
from typing import List, Dict, Any
from langfuse import observe

from src.clients.llm_client import LLMClient
from src.utils.prompt_builder import render_prompt

class SetupManager:
    def __init__(self):
        # We use a dedicated LLM instance for setup tasks
        self.llm = LLMClient()

    @observe(as_type="generation", name="generate_personas")
    def generate_personas(
        self, 
        topic: str, 
        num_agents: int = 3, 
        custom_instructions: str = "",
        default_memory_type: str = "sliding_window"
    ) -> List[Dict[str, Any]]:
        """
        Dynamically generates N distinct personas for the debate based on the topic.
        Attaches an individual memory_config to each persona.
        """
        print(f"[*] Generating {num_agents} dynamic personas for topic: '{topic}'...")

        prompt = render_prompt(
            "setup_personas",
            topic=topic,
            num_agents=num_agents,
            custom_instructions=custom_instructions or "None"
        )

        messages = [
            {"role": "system", "content": "You are a JSON-only API. You must output a valid JSON array of objects and absolutely nothing else."},
            {"role": "user", "content": prompt}
        ]

        response = self.llm.generate_response(messages, response_format="json_object")
        content = response.get("content", "")

        try:
            personas = json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r'\[.*\]', content, re.DOTALL)
            if match:
                personas = json.loads(match.group(0))
            else:
                raise ValueError("LLM did not return a recognizable JSON array.")

        required_keys = {"name", "background", "stance", "tone"}
        for i, p in enumerate(personas):
            if not isinstance(p, dict) or not required_keys.issubset(p.keys()):
                raise ValueError(f"Persona at index {i} is missing required keys: {required_keys}")

            # Assign individual memory configuration to each agent
            if "memory_config" not in p:
                p["memory_config"] = {
                    "type": default_memory_type,  # 'sliding_window', 'summary', or 'full'
                    "window_size": 4
                }

            print(f"[+] Generated Persona: {p['name']} ({p['tone']}) | Memory: {p['memory_config']['type']}")

        return personas

if __name__ == "__main__":
    # Smoke Test
    manager = SetupManager()
    agents = manager.generate_personas(
        topic="Should the government ban AI deepfakes?", 
        num_agents=2, 
        custom_instructions="One strict lawyer, one free-speech activist."
    )
    print(json.dumps(agents, indent=2))
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
    def generate_personas(self, topic: str, num_agents: int = 3, custom_instructions: str = "") -> List[Dict[str, Any]]:
        """
        Dynamically generates N distinct personas for the debate based on the topic.
        Returns a validated list of persona dictionaries.
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

        # Safe JSON Extraction (Handles cases where LLM wraps output in ```json ... ```)
        try:
            # Try parsing raw first
            personas = json.loads(content)
        except json.JSONDecodeError:
            # Fallback: Extract JSON array using regex
            match = re.search(r'\[.*\]', content, re.DOTALL)
            if match:
                try:
                    personas = json.loads(match.group(0))
                except json.JSONDecodeError as e:
                    raise ValueError(f"Failed to parse personas JSON from LLM: {e}")
            else:
                raise ValueError("LLM did not return a recognizable JSON array.")

        # Validation to ensure the LLM followed the schema
        required_keys = {"name", "background", "stance", "tone"}
        for i, p in enumerate(personas):
            if not isinstance(p, dict) or not required_keys.issubset(p.keys()):
                raise ValueError(f"Persona at index {i} is missing required keys: {required_keys}")
            
            # Auto-assign a baseline opinion score for the Opinion Grader later
            # (Assuming the LLM created diverse views, we'll start them dynamically)
            print(f"[+] Generated Persona: {p['name']} ({p['tone']})")

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
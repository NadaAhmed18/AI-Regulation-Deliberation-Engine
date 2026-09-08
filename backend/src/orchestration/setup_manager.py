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

    @staticmethod
    def build_visibility_matrix(personas: List[Dict[str, Any]], topology: str = "ring") -> Dict[str, List[str]]:
        """
        Generates visibility map (who each agent is allowed to hear from).
        - 'ring': Strongly connected directed loop (A -> B -> C -> A)
        - 'mesh': Full communication (all see all)
        """
        names = [p["name"] for p in personas]
        n = len(names)
        matrix: Dict[str, List[str]] = {}

        if topology == "ring":
            for i in range(n):
                listener = names[i]
                speaker = names[(i - 1 + n) % n]
                matrix[listener] = [speaker]
        elif topology == "mesh":
            for listener in names:
                matrix[listener] = [s for s in names if s != listener]
        else:
            raise ValueError(f"Unsupported topology preset: {topology}")

        return matrix


if __name__ == "__main__":
    # Test runner: python -m src.orchestration.setup_manager
    print("\n" + "=" * 60)
    print(" smoke test: SetupManager ".center(60, "="))
    print("=" * 60)

    manager = SetupManager()
    sample_topic = "Should training clusters >10^26 FLOPs face mandatory third-party audits?"

    # 1. Generate personas with default memory
    agents = manager.generate_personas(
        topic=sample_topic,
        num_agents=3,
        custom_instructions="Include one hardware vendor, one open-source researcher, and one EU regulator.",
        default_memory_type="sliding_window"
    )

    # 2. Customize individual memory strategies
    agents[0]["memory_config"] = {"type": "summary"}
    agents[1]["memory_config"] = {"type": "sliding_window", "window_size": 2}
    agents[2]["memory_config"] = {"type": "full"}

    # 3. Generate directed ring visibility matrix
    vis_matrix = manager.build_visibility_matrix(agents, topology="ring")

    print("\n[Generated Personas & Custom Memory Profiles]:")
    print(json.dumps(agents, indent=2))

    print("\n[Constructed Graph Visibility Matrix]:")
    for listener, speakers in vis_matrix.items():
        print(f"  - '{listener}' listens only to: {speakers}")
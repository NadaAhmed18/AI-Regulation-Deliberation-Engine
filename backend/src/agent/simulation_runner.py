import json
from pathlib import Path
import os
from src.agent.base_agent import BaseAgent
from src.utils.yaml_loader import load_persona



BASE_DIR = Path(__file__).resolve().parents[2]

PERSONAS_DIR = BASE_DIR / "personas" 
OUTPUT_DIR = BASE_DIR / "outputs" 
OUTPUT_FILE = OUTPUT_DIR / "initial_opinions.json"



def generate_all_opinions(topic: str) -> list[dict]:
 

    persona_files = [
      PERSONAS_DIR /"persona_a.yaml",
     PERSONAS_DIR / "persona_b.yaml"
    ]

    opinions = []

    for persona_file in persona_files:
        print(f"\n[Simulation] Loading persona: {persona_file.name}")

        persona = load_persona(persona_file)

        agent = BaseAgent(persona)

        print(f"Generating opinion for: {agent.name}")

        result = agent.generate_initial_opinion(topic)

        opinions.append(result)

        print(f" Opinion generated for: {agent.name}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {
                "topic": topic,
                "opinions": opinions,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(f"\nSaved results to: {OUTPUT_FILE}")

    return opinions
# python -m src.agent.utils.simulation_runner --generate-initial-opinions
import argparse
import json
from src.agent.base_agent import BaseAgent
from src.config import PERSONAS_DIR, OUTPUT_DIR, OUTPUT_FILE
from src.utils.yaml_loader import load_persona


def generate_all_opinions(topic: str) -> list[dict]:
    persona_files = [
        PERSONAS_DIR / "persona_a.yaml",
        PERSONAS_DIR / "persona_b.yaml",
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
            {"topic": topic, "opinions": opinions},
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(f"\nSaved results to: {OUTPUT_FILE}")

    return opinions


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Week 2 AI Regulation Stakeholder Simulation"
    )

    parser.add_argument(
        "--generate-initial-opinions",
        action="store_true",
        help="Generate initial RAG-grounded opinions for all personas.",
    )

    args = parser.parse_args()

    if args.generate_initial_opinions:
        topic = "Classifying Open Source Models under the EU AI Act"

        generate_all_opinions(topic)
    else:
        parser.print_help()
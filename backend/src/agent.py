import argparse

from src.agent.simulation_runner import generate_all_opinions


def main():
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


if __name__ == "__main__":
    main()

"""
PROMPT BUILDER UTILITY

Purpose:
    A universal template rendering engine. It loads .txt prompt files from the 
    `prompts/` directory, extracts the required placeholders, and safely formats 
    the string. If a required key is missing, it fails loudly to prevent LLM hallucinations.
"""

import string
from pathlib import Path
from typing import Any

from src.config import PROMPTS_DIR 


def get_template_path(template_name: str) -> Path:
    """Resolves the name of a template to its absolute path."""
    if not template_name.endswith(".txt"):
        template_name += ".txt"
    return PROMPTS_DIR / template_name


def load_template(template_name: str) -> str:
    """Read a prompt template file from disk and return its raw text."""
    path = get_template_path(template_name)
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: '{path}'")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _extract_required_keys(template_str: str) -> set[str]:
    """
    Parses the template string and returns a set of all required {placeholders}.
    Ignores formatting syntax that doesn't have a field name.
    """
    formatter = string.Formatter()
    keys = set()
    for _, field_name, _, _ in formatter.parse(template_str):
        if field_name is not None:
            # Handle complex keys like {persona[name]} by grabbing just the root name
            root_key = field_name.split('[')[0].split('.')[0]
            keys.add(root_key)
    return keys


def render_prompt(template_name: str, **kwargs: Any) -> str:
    """
    Loads a template by name, validates that all required placeholders are provided 
    in kwargs, and formats the string.

    Args:
        template_name: Name of the file (e.g., "orchestrator", "system_agent.txt")
        **kwargs: The variables to inject into the template.

    Returns:
        str: The fully rendered prompt string.

    Raises:
        KeyError: If the template references a placeholder not provided in kwargs.
    """
    template_str = load_template(template_name)
    required_keys = _extract_required_keys(template_str)

    # Validation: Check for missing keys
    missing_keys = required_keys - set(kwargs.keys())
    if missing_keys:
        raise KeyError(
            f"Template '{template_name}' requires the following variables which "
            f"were not provided: {missing_keys}"
        )

    # Format and return (we pass kwargs directly; extra kwargs are safely ignored by format)
    return template_str.format(**kwargs)


if __name__ == "__main__":
    # Smoke Test
    print("--- Testing Prompt Builder ---")
    
    try:
        # 1. Test System Agent
        agent_prompt = render_prompt(
            "system_agent",
            persona_name="Dr. Elena",
            persona_background="AI Researcher",
            persona_stance="Pro Open-Source",
            persona_tone="Academic"
        )
        print("\n[✔] System Agent Prompt rendered successfully. (Length:", len(agent_prompt), ")")

        # 2. Test Setup Personas
        setup_prompt = render_prompt(
            "setup_personas",
            topic="Should AI models be regulated by the EU?",
            num_agents=3,
            custom_instructions="Make one of them a politician."
        )
        print("[✔] Setup Personas Prompt rendered successfully.")
        
        # 3. Test Missing Key Error Handling
        print("\nTesting Error Handling (Missing 'topic' key)...")
        render_prompt("orchestrator", agent_summaries="...", recent_history="...")
        
    except KeyError as e:
        print("[✔] Caught expected KeyError:", e)
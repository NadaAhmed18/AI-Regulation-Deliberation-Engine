"""
YAML LOADER UTILITY

Purpose:
    Safely read a persona `.yaml` file from disk and return it as a plain
    Python dictionary, ready to be injected into an Agent (system prompt)
    or into a prompt template (see `src.utils.prompt_builder`).

    This is a deliberately small, dependency-light utility. It is the
    "temporary stepping stone" referenced in the Week 2 brief: until the
    main agent orchestrator dynamically generates personas on-the-fly,
    each agent can assume a static persona loaded from a YAML file via
    `load_persona()`.

Persona schema (required fields, all must be non-empty strings):
    - name        (str): Display name of the stakeholder.
    - background  (str): Short biography / context for the persona.
    - stance      (str): The persona's position on the simulated topic.
    - tone        (str): How the persona communicates (register, style).

Persona schema (optional fields, validated if present):
    - organization (str): Affiliation / org name.
    - priorities   (list[str]): What this stakeholder optimizes for.
    - expertise    (list[str]): Domains this stakeholder speaks with authority on.

Design note:
    This loader intentionally raises loudly (`FileNotFoundError` /
    `ValueError`) on any malformed persona instead of silently filling in
    defaults. A misconfigured persona is a configuration bug, not a
    runtime condition to paper over — callers (e.g. `prompt_builder.py`)
    should be able to trust that any dict returned here is complete and
    well-typed.
"""

from pathlib import Path
from typing import Any, Union

import yaml

REQUIRED_PERSONA_FIELDS = ("name", "background", "stance", "tone")
OPTIONAL_LIST_FIELDS = ("priorities", "expertise")


def load_persona(file_path: Union[str, Path]) -> dict[str, Any]:
    """
    Load a persona definition from a YAML file, validate it, and return it
    as a dict.

    Args:
        file_path: Path to a `.yaml` (or `.yml`) persona file, e.g.
            "personas/persona_a.yaml".

    Returns:
        dict[str, Any]: The parsed and validated persona, e.g.
            {
                "name": "Dr. Elena Kovac",
                "background": "...",
                "stance": "...",
                "tone": "...",
                "priorities": ["...", "..."],
                "expertise": ["...", "..."],
            }

    Raises:
        FileNotFoundError: If `file_path` does not exist.
        ValueError: If the file is empty, does not parse into a mapping,
            contains invalid YAML syntax, is missing a required persona
            field, has a required field that isn't a non-empty string, or
            has an optional list field (`priorities`/`expertise`) that
            isn't a list of strings.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Persona file not found: '{path}'")

    with open(path, "r", encoding="utf-8") as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Persona file '{path}' contains invalid YAML: {e}") from e

    if data is None:
        raise ValueError(f"Persona file '{path}' is empty.")

    if not isinstance(data, dict):
        raise ValueError(
            f"Persona file '{path}' must parse into a mapping (dict), "
            f"got {type(data).__name__} instead."
        )

    _validate_required_fields(data, path)
    _validate_optional_list_fields(data, path)

    # Normalize whitespace on the long-form YAML block-scalar fields
    # (PyYAML preserves a trailing newline on `>` block scalars).
    for field in REQUIRED_PERSONA_FIELDS:
        data[field] = data[field].strip()

    return data


def _validate_required_fields(data: dict[str, Any], path: Path) -> None:
    """Ensure every required field is present and a non-empty string."""
    missing = [field for field in REQUIRED_PERSONA_FIELDS if field not in data]
    if missing:
        raise ValueError(
            f"Persona file '{path}' is missing required field(s): "
            f"{', '.join(missing)}. Required fields are: "
            f"{', '.join(REQUIRED_PERSONA_FIELDS)}."
        )

    for field in REQUIRED_PERSONA_FIELDS:
        value = data[field]
        if not isinstance(value, str):
            raise ValueError(
                f"Persona file '{path}': field '{field}' must be a string, "
                f"got {type(value).__name__} ({value!r})."
            )
        if not value.strip():
            raise ValueError(
                f"Persona file '{path}': field '{field}' cannot be empty "
                f"or whitespace-only."
            )


def _validate_optional_list_fields(data: dict[str, Any], path: Path) -> None:
    """If present, `priorities`/`expertise` must be a list of non-empty strings."""
    for field in OPTIONAL_LIST_FIELDS:
        if field not in data:
            continue
        value = data[field]
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError(
                f"Persona file '{path}': optional field '{field}' must be a "
                f"list of strings if provided, got {value!r}."
            )
        if any(not item.strip() for item in value):
            raise ValueError(
                f"Persona file '{path}': optional field '{field}' cannot "
                f"contain empty strings."
            )


if __name__ == "__main__":
    # Smoke test: load both bundled example personas and print them.
    for name in ("persona_a.yaml", "persona_b.yaml"):
        persona_path = Path(__file__).resolve().parents[2] / "personas" / name
        persona = load_persona(persona_path)
        print(f"--- Loaded {name} ---")
        print(f"Name:       {persona['name']}")
        print(f"Stance:     {persona['stance'][:80]}...")
        print(f"Expertise:  {persona.get('expertise')}")
        print(f"Priorities: {persona.get('priorities')}")
        print()

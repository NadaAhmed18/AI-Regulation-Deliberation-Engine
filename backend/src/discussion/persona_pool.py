"""
PERSONA POOL — Week 3 Discussion Engine

Purpose:
    `src/utils/yaml_loader.py` (Week 2) loads ONE persona file into a dict.
    This module sits one layer above it: it loads every persona under
    `personas/` into a named pool, and lets a discussion select a *subset*
    of that pool to participate.

    Not every discussion needs all six stakeholders. A discussion about
    open-source model classification might only need
    Elena (regulator), Priya (GPAI provider), and Tomas (academic) — adding
    Grace or Marcus wouldn't add a meaningfully different perspective on
    that specific sub-topic. Hardcoding "always load all six" into the
    discussion engine would make it impossible to run a smaller, focused
    discussion without editing code.

Design:
    Personas are keyed by a short, stable `persona_id` (the filename stem,
    e.g. "persona_a") rather than by `name` — a stakeholder's display name
    is free text a persona author might change ("Dr. Elena Kovac" ->
    "Dr. Elena Kovac-Reyes"), but code that builds a discussion graph needs
    an identifier that doesn't shift under it. `name` is still available on
    the loaded persona dict itself for display purposes.

Architectural boundary (intentional):
    Like `yaml_loader.py`, this module only deals with persona
    *configuration* (who the stakeholder is). It has no concept of
    discussion rounds, opinions, or messages — that is
    `src/discussion/opinion_state.py`'s and the discussion engine's job.
    Keeping the two separate is deliberate: persona identity is static
    across every discussion it's used in, while opinion state is specific
    to one discussion + one topic. Conflating them would make it impossible
    to reuse the same persona pool across multiple discussions with
    independent opinion histories.
"""

from pathlib import Path
from typing import Any, Union

from src.config import PERSONAS_DIR
from src.utils.yaml_loader import load_persona


def load_persona_pool(personas_dir: Union[str, Path] = PERSONAS_DIR) -> dict[str, dict[str, Any]]:
    """
    Load every `.yaml` persona file under `personas_dir` into a pool.

    Args:
        personas_dir: Directory containing one `.yaml` file per persona.
            Defaults to `PERSONAS_DIR` from `src/config.py`.

    Returns:
        dict[str, dict[str, Any]]: Mapping of `persona_id` (filename stem,
        e.g. "persona_c") to the validated persona dict returned by
        `load_persona()`.

    Raises:
        FileNotFoundError: If `personas_dir` does not exist or contains no
            `.yaml` files.
        ValueError: Propagated from `load_persona()` if any persona file in
            the directory is malformed — a broken persona file should fail
            loudly at pool-load time, not silently disappear from the pool.
    """
    directory = Path(personas_dir)
    if not directory.is_dir():
        raise FileNotFoundError(f"Persona pool directory not found: '{directory}'")

    persona_files = sorted(directory.glob("*.yaml"))
    if not persona_files:
        raise FileNotFoundError(f"No '.yaml' persona files found under '{directory}'")

    pool: dict[str, dict[str, Any]] = {}
    for file_path in persona_files:
        persona_id = file_path.stem  # e.g. "persona_a"
        pool[persona_id] = load_persona(file_path)

    return pool


def select_personas(
    persona_ids: list[str],
    pool: Union[dict[str, dict[str, Any]], None] = None,
) -> list[dict[str, Any]]:
    """
    Select a specific subset of the persona pool for one discussion.

    Args:
        persona_ids: The `persona_id`s (filename stems, e.g.
            ["persona_a", "persona_c", "persona_e"]) to include, in the
            order they should be treated as participants.
        pool: An already-loaded pool (see `load_persona_pool()`). If
            `None`, the full pool is loaded fresh from `PERSONAS_DIR`.

    Returns:
        list[dict[str, Any]]: The selected persona dicts, in the same
        order as `persona_ids`.

    Raises:
        ValueError: If `persona_ids` is empty, contains a duplicate, or
            references a `persona_id` that isn't in the pool. Raising here
            (rather than silently skipping an unknown id) matches
            `yaml_loader.py`'s "fail loudly on misconfiguration" design —
            a typo in a discussion config should surface immediately, not
            quietly run a discussion with one fewer participant than
            intended.
    """
    if not persona_ids:
        raise ValueError("select_personas() requires at least one persona_id.")

    duplicates = {pid for pid in persona_ids if persona_ids.count(pid) > 1}
    if duplicates:
        raise ValueError(f"Duplicate persona_id(s) in selection: {sorted(duplicates)}")

    active_pool = pool if pool is not None else load_persona_pool()

    missing = [pid for pid in persona_ids if pid not in active_pool]
    if missing:
        raise ValueError(
            f"Unknown persona_id(s): {missing}. Available: {sorted(active_pool)}"
        )

    return [active_pool[pid] for pid in persona_ids]


def list_available_personas(personas_dir: Union[str, Path] = PERSONAS_DIR) -> list[dict[str, str]]:
    """
    Return a short, human-readable summary of every persona in the pool —
    useful for a CLI prompt, a config file comment, or a frontend picker,
    without needing the full background/stance/tone text of each one.

    Returns:
        list[dict[str, str]]: One entry per persona, each with
        `persona_id`, `name`, and `organization` (empty string if the
        persona has no `organization` field).
    """
    pool = load_persona_pool(personas_dir)
    return [
        {
            "persona_id": persona_id,
            "name": persona["name"],
            "organization": persona.get("organization", ""),
        }
        for persona_id, persona in pool.items()
    ]


if __name__ == "__main__":
    # Smoke test: python -m src.discussion.persona_pool   (from backend/ root)
    print("--- Full persona pool ---")
    for entry in list_available_personas():
        org = f" ({entry['organization']})" if entry["organization"] else ""
        print(f"  {entry['persona_id']}: {entry['name']}{org}")

    print("\n--- Selecting a 3-persona subset for a focused discussion ---")
    subset = select_personas(["persona_a", "persona_c", "persona_e"])
    for persona in subset:
        print(f"  Selected: {persona['name']}")

    print("\n--- Unknown persona_id should raise ---")
    try:
        select_personas(["persona_a", "persona_zzz"])
    except ValueError as e:
        print(f"  Raised as expected: {e}")

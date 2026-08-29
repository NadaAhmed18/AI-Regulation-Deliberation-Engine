"""
PROMPT BUILDER UTILITY

Purpose:
    Reusable, fill-in-the-blank prompt construction for the agent framework.
    This module has two responsibilities, matching the two persona/prompt
    tickets for this week:

    1. `build_system_prompt(persona)`
       Combines the [General Simulation Rules] with the [Persona] into a
       single system prompt string. The persona's full identity (name,
       background, stance, tone, priorities, expertise) lives HERE and only
       here — it is the single source of truth for "who this agent is" for
       the entire conversation. This matches
       `BaseAgent._build_system_prompt` (see `src/agent/base_agent.py`) and
       can be imported directly once the orchestrator is wired up.

    2. `render_initial_opinion_prompt(...)`
       Loads `prompts/initial_opinion.txt` and safely fills in a brief
       identity reminder, retrieved context, memory summary, and topic
       placeholders. This is the task/user-turn prompt sent alongside the
       system prompt above. It intentionally does NOT re-elaborate the full
       persona (tone, priorities, expertise) — that would just duplicate
       the system prompt. It keeps `{persona_name}` / `{persona_background}`
       / `{persona_stance}` as a short reminder line, per this week's ticket
       (which explicitly requires those as template placeholders).

Architectural boundary (intentional):
    This module knows nothing about Neo4j, the retriever, the LLM client,
    or the memory store. It only turns
        persona dict + context string + memory string + topic string
    into
        prompt strings.
    Wiring those inputs together (calling the retriever, reading memory,
    calling the LLM) is the Agent's job, not this module's. That keeps this
    file trivially reusable and testable in isolation.

Both functions only need a persona dict (as returned by
`src.utils.yaml_loader.load_persona`) — they do not care whether that dict
came from a static YAML file or was generated on-the-fly, which is what
keeps this reusable once dynamic persona generation is added.
"""

from pathlib import Path
from typing import Any, Union

# Directory containing this file: backend/src/utils/ -> backend/
BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEMPLATE_PATH = BACKEND_ROOT / "prompts" / "initial_opinion.txt"

GENERAL_SIMULATION_RULES = """\
You are an AI stakeholder participating in a structured multi-agent
simulation about AI regulation, AI governance, and democratic values.

GENERAL RULES:
1. Stay consistent with your assigned persona for the entire simulation.
2. Distinguish factual claims from stakeholder opinions.
3. Ground factual claims in retrieved evidence whenever it is available.
4. Never fabricate laws, regulations, statistics, sources, or quotations.
5. If the retrieved evidence is insufficient, explicitly state the limitation
   instead of inventing information to fill the gap.
6. Use available tools when additional evidence is needed before arguing.
7. Do not blindly agree with other stakeholders; evaluate claims critically.
8. Evaluate policy trade-offs from your assigned stakeholder's perspective.
9. Respect democratic values, fundamental rights, safety, and innovation
   considerations when relevant to the topic."""


def _format_bullet_list(items: list[str]) -> str:
    """Render a list of strings as a newline-separated bullet list, or a
    placeholder line if the list is empty."""
    if not items:
        return "  (none specified)"
    return "\n".join(f"  - {item}" for item in items)


def build_system_prompt(persona: dict[str, Any]) -> str:
    """
    Combine the general simulation rules with a specific persona to form
    the agent's system prompt. This is the ONLY place the full persona
    (including tone, priorities, and expertise) is rendered — the initial
    opinion template only repeats a brief identity reminder.

    Args:
        persona: A validated persona dict with `name`, `background`,
            `stance`, and `tone` keys, and optionally `priorities` /
            `expertise` (see `src.utils.yaml_loader.load_persona`). This
            function assumes the persona was already validated by the
            loader — it does not silently substitute defaults for missing
            required fields, since that would mask a configuration bug.

    Returns:
        str: The full system prompt, combining
            "[General Simulation Rules] ..." and "[Persona] ...".
    """
    persona_block = (
        f"Name: {persona['name']}\n"
        f"Background: {persona['background']}\n"
        f"Stance: {persona['stance']}\n"
        f"Tone: {persona['tone']}\n"
        f"Priorities:\n{_format_bullet_list(persona.get('priorities', []))}\n"
        f"Expertise:\n{_format_bullet_list(persona.get('expertise', []))}"
    )

    return (
        f"[General Simulation Rules]\n{GENERAL_SIMULATION_RULES}\n\n"
        f"[Persona]\n{persona_block}"
    )


def load_template(template_path: Union[str, Path] = DEFAULT_TEMPLATE_PATH) -> str:
    """Read a prompt template file from disk and return its raw text."""
    path = Path(template_path)
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: '{path}'")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def render_initial_opinion_prompt(
    persona: dict[str, Any],
    retrieved_context: str,
    memory_summary: str,
    topic: str,
    template_path: Union[str, Path] = DEFAULT_TEMPLATE_PATH,
) -> str:
    """
    Fill in `prompts/initial_opinion.txt` with a brief persona identity
    reminder plus retrieval, memory, and topic information.

    Args:
        persona: A validated persona dict (see
            `src.utils.yaml_loader.load_persona`). Required keys `name`,
            `background`, and `stance` are read directly (no fallback
            defaults) since the loader guarantees they exist; a missing
            key here means a caller bypassed the loader and should fail
            loudly rather than silently produce "Unnamed Stakeholder".
        retrieved_context: Text returned by the Week 1 retrieval tool
            (e.g. `search_ai_policy`), or dummy text for testing. Treated
            by the template as untrusted reference material, not
            instructions (see the grounding rules in the template itself).
        memory_summary: A short summary of prior interactions for this
            agent, or an empty string / placeholder if none exist yet.
        topic: The topic the agent should form an initial opinion about.
        template_path: Override the default template location if needed.

    Returns:
        str: The fully rendered prompt, ready to send to the LLM as the
        user/task message.

    Raises:
        KeyError: If the template references a placeholder that isn't
            supplied here (surfaced clearly instead of failing silently).
    """
    template = load_template(template_path)

    values = {
        "topic": topic or "Not specified.",
        "persona_name": persona["name"],
        "persona_background": persona["background"],
        "persona_stance": persona["stance"],
        "retrieved_context": retrieved_context or "No evidence was retrieved for this query.",
        "memory_summary": memory_summary or "No prior interactions recorded.",
    }

    try:
        return template.format(**values)
    except KeyError as e:
        raise KeyError(
            f"Template '{template_path}' references placeholder {e} which "
            f"was not supplied to render_initial_opinion_prompt()."
        )

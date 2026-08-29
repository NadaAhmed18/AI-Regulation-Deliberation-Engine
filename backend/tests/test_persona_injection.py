"""
TEST: Persona Loading + Prompt Injection (Temporary Stepping Stone)

What this proves:
    1. `load_persona()` can safely read a real `.yaml` persona file into a dict.
    2. `build_system_prompt()` combines general simulation rules with that
       persona dict into a single system prompt, and the persona's identity
       fields actually show up in it.
    3. `render_initial_opinion_prompt()` injects the identity reminder, the
       sample retrieved context, and the sample memory into
       `prompts/initial_opinion.txt` with no KeyError / formatting errors,
       and no leftover unrendered `{placeholder}` text.
    4. Two different personas produce two different system prompts AND two
       different rendered task prompts, so the template is not hard-coded
       to a single stakeholder.

These are plain `assert`-based functions named `test_*`, so this file is
directly discoverable by `pytest` if/when the project adopts it, while
still being runnable standalone (no extra dependency required).

Run as a module from the `backend/` root — this project relies on native
relative imports rather than any `sys.path` manipulation:

    python -m tests.test_persona_injection
"""

from pathlib import Path

from src.utils.yaml_loader import load_persona
from src.utils.prompt_builder import build_system_prompt, render_initial_opinion_prompt

PERSONAS_DIR = Path("personas")

sample_retrieved_context = (
    "--- SOURCE 1 ---\n"
    "Domain: eu-ai-act\n"
    "URL: https://eur-lex.europa.eu/eli/reg/2024/1689/oj?locale=en\n"
    "Relevance Score: 0.8421\n"
    "Content:\n"
    "High-risk AI systems are subject to requirements including risk "
    "management, data governance, technical documentation, human oversight, "
    "and conformity assessment before being placed on the market.\n"
)

sample_memory_summary = (
    "In a prior round, this stakeholder raised concerns about the cost of "
    "conformity assessments for smaller organizations and asked for "
    "clarification on how 'high-risk' is classified."
)

sample_topic = "Should Region X adopt an EU-style, risk-based AI regulatory framework?"

# Any of these left unrendered in the output means the template.format()
# call silently dropped a value instead of substituting it.
TEMPLATE_PLACEHOLDERS = (
    "{persona_name}",
    "{persona_background}",
    "{persona_stance}",
    "{retrieved_context}",
    "{memory_summary}",
    "{topic}",
)


def _render_case(persona_filename: str) -> tuple[dict, str, str]:
    """Load a persona and render both prompts for it. Shared by every test."""
    persona = load_persona(PERSONAS_DIR / persona_filename)
    system_prompt = build_system_prompt(persona)
    rendered_prompt = render_initial_opinion_prompt(
        persona=persona,
        retrieved_context=sample_retrieved_context,
        memory_summary=sample_memory_summary,
        topic=sample_topic,
    )
    return persona, system_prompt, rendered_prompt


def test_persona_a_system_prompt_contains_identity():
    persona, system_prompt, _ = _render_case("persona_a.yaml")
    assert persona["name"] in system_prompt
    assert "Pro-Regulation" in system_prompt
    assert "Fundamental rights" in system_prompt  # from persona_a's priorities


def test_persona_b_system_prompt_contains_identity():
    persona, system_prompt, _ = _render_case("persona_b.yaml")
    assert persona["name"] in system_prompt
    assert "Pro-Innovation" in system_prompt
    assert "healthcare" in system_prompt.lower()  # from persona_b's background/expertise


def test_rendered_prompt_contains_injected_values():
    persona, _, rendered = _render_case("persona_a.yaml")
    assert persona["name"] in rendered
    assert sample_retrieved_context in rendered
    assert sample_memory_summary in rendered
    assert sample_topic in rendered


def test_rendered_prompt_has_no_leftover_placeholders():
    _, _, rendered = _render_case("persona_b.yaml")
    for placeholder in TEMPLATE_PLACEHOLDERS:
        assert placeholder not in rendered, f"Unrendered placeholder leaked into output: {placeholder}"


def test_two_personas_produce_distinct_prompts():
    _, system_a, rendered_a = _render_case("persona_a.yaml")
    _, system_b, rendered_b = _render_case("persona_b.yaml")
    assert system_a != system_b, "System prompts should differ between personas."
    assert rendered_a != rendered_b, "Rendered task prompts should differ between personas."


def _run_all_tests_and_print():
    """Standalone runner: executes every test_* function, printing sample
    output for visual inspection, then reports pass/fail without pytest."""
    persona_a, system_a, rendered_a = _render_case("persona_a.yaml")

    print("=" * 80)
    print("SAMPLE OUTPUT — persona_a.yaml")
    print("=" * 80)
    print("\n--- SYSTEM PROMPT ---\n")
    print(system_a)
    print("\n--- RENDERED INITIAL OPINION PROMPT ---\n")
    print(rendered_a)
    print()

    tests = [
        test_persona_a_system_prompt_contains_identity,
        test_persona_b_system_prompt_contains_identity,
        test_rendered_prompt_contains_injected_values,
        test_rendered_prompt_has_no_leftover_placeholders,
        test_two_personas_produce_distinct_prompts,
    ]

    for test_fn in tests:
        test_fn()
        print(f"{test_fn.__name__}")

    print("\nAll persona injection tests passed — no KeyError / formatting "
          "errors, no leftover placeholders, personas render distinctly.")


if __name__ == "__main__":
    _run_all_tests_and_print()

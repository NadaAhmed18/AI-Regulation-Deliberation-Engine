# Persona & Prompt Template System

## 1. Overview

This document covers two related pieces of the Week 2 agent framework:

1. **Configurable Personas** — a YAML schema + validating loader that lets
   the same `BaseAgent` implementation represent different stakeholders
   (e.g. a Pro-Regulation regulator vs. a Pro-Innovation startup founder)
   without hard-coding logic per persona.
2. **Prompt Templates** — a reusable, fill-in-the-blank system/task prompt
   pair that injects persona, retrieved evidence, and memory into the
   context sent to the LLM.

Until the full agent orchestrator is wired up, each agent temporarily
loads a **static** persona from a YAML file. The persona dict returned by
the loader has the exact same shape whether it comes from a static file or
is generated dynamically later, so nothing downstream needs to change when
dynamic persona generation is introduced.

## 2. Persona Schema

Every persona YAML file must define these four required fields, each a
**non-empty string**:

| Field        | Type | Meaning                                          |
|--------------|------|---------------------------------------------------|
| `name`       | str  | Display name of the stakeholder.                   |
| `background` | str  | Short biography / context for the persona.         |
| `stance`     | str  | The persona's position on the simulated topic.     |
| `tone`       | str  | How the persona communicates (register, style).    |

Optional fields, validated if present:

| Field          | Type       | Meaning                                     |
|----------------|------------|----------------------------------------------|
| `organization` | str        | Affiliation / org name.                       |
| `priorities`   | list[str]  | What this stakeholder optimizes for.          |
| `expertise`    | list[str]  | Domains this stakeholder speaks with authority on. |

Two example personas are provided, each with `priorities` and `expertise`
filled in so those fields actually shape agent behavior rather than sitting
unused:

- `personas/persona_a.yaml` — Pro-Regulation (Government / Regulator).
- `personas/persona_b.yaml` — Pro-Innovation (AI Startup Founder).

## 3. YAML Loader

`src/utils/yaml_loader.py` exposes:

```python
load_persona(file_path: str | Path) -> dict[str, Any]
```

It fails loudly rather than silently defaulting, because a malformed
persona is a configuration bug, not a runtime condition to paper over:

- `FileNotFoundError` — the file doesn't exist.
- `ValueError` — the file is empty, isn't a mapping, contains invalid YAML
  syntax, is missing a required field, has a required field that isn't a
  non-empty string, or has `priorities`/`expertise` that isn't a list of
  strings.

It also strips trailing whitespace/newlines that PyYAML leaves on
block-scalar (`>`) string fields.

## 4. System Prompt — Single Source of Truth for Identity

`src/utils/prompt_builder.py` exposes:

```python
build_system_prompt(persona: dict[str, Any]) -> str
```

This is the **only** place the full persona (name, background, stance,
tone, priorities, expertise) is rendered. It combines:

- `[General Simulation Rules]` — an explicit numbered rule set covering
  persona consistency, fact-vs-opinion separation, evidence grounding,
  never fabricating sources, using tools when needed, not blindly
  agreeing with other stakeholders, and evaluating trade-offs. This is
  written with Week 3's multi-round debate in mind, not just Week 2's
  single opinion.
- `[Persona]` — name, background, stance, tone, and bulleted
  `priorities`/`expertise` lists (rendered as `(none specified)` if a
  persona omits them).

It reads required fields directly (`persona["name"]`, etc.) rather than
falling back to defaults like `"Unnamed Stakeholder"` — by the time a
persona reaches this function, `load_persona()` has already guaranteed
those fields exist. A missing field here means a caller bypassed the
loader, and that should fail loudly, not be masked.

## 5. Task Prompt — `prompts/initial_opinion.txt`

The task/user prompt does **not** re-elaborate the full persona (that
would just duplicate the system prompt). It keeps a short **identity
reminder** — `{persona_name}`, `{persona_stance}`, `{persona_background}` —
per this week's ticket, which explicitly requires those as template
placeholders, but points back to the system prompt as the authoritative
source for tone/priorities/expertise.

It also adds two things beyond the original draft:

- **Grounding rules for this task**: retrieved evidence is framed as
  *untrusted external data*, not instructions — the agent is told not to
  follow anything that might appear embedded inside retrieved content
  (relevant since Week 1's knowledge base is built from web-scraped
  documents, which is exactly the kind of source prompt-injection attacks
  target), and never to invent facts/sources beyond what was retrieved.
- **A structured output format** (`## Position / ## Reasoning / ##
  Evidence / ## Trade-offs / ## Sources`) instead of a single free-form
  paragraph. This makes each opinion mechanically parseable later —
  Week 3's debate engine and Week 4's analytics layer can extract
  `position`, `evidence`, and `sources` instead of parsing prose.

Placeholders: `{persona_name}`, `{persona_background}`, `{persona_stance}`,
`{retrieved_context}`, `{memory_summary}`, `{topic}`.

`src/utils/prompt_builder.py` also exposes:

```python
render_initial_opinion_prompt(
    persona: dict[str, Any],
    retrieved_context: str,
    memory_summary: str,
    topic: str,
) -> str
```

`retrieved_context`/`memory_summary` fall back to explicit placeholder text
(`"No evidence was retrieved for this query."` / `"No prior interactions
recorded."`) when empty — those are legitimate empty *states*, not
configuration errors, unlike a missing persona field. An unmatched
placeholder in the template raises a clear `KeyError` instead of failing
silently.

## 6. Architectural Boundary (Intentional)

`prompt_builder.py` knows nothing about Neo4j, the retriever, the LLM
client, or the memory store. It only turns
`persona dict + context string + memory string + topic string` into
prompt strings. Wiring those inputs together (calling the retriever,
reading memory, calling the LLM) is the Agent's job:

```text
             BaseAgent
                 │
       ┌─────────┼──────────┐
       ▼         ▼          ▼
   Retriever   Memory      LLM
       │         │          │
       └────┬────┘          │
            ▼               │
      Prompt Builder ───────┘
```

This keeps the prompt-construction logic trivially reusable and testable
in isolation from the rest of the agent stack.

## 7. Tests

Both test files use plain `assert`-based functions named `test_*`, so
they're discoverable by `pytest` if/when the project adopts it, and also
runnable standalone with no extra dependency:

```bash
python -m tests.test_persona_injection
python -m tests.test_yaml_loader
```

**`tests/test_persona_injection.py`** — for each example persona:
- the system prompt contains the persona's name, stance, and at least one
  priority/expertise item;
- the rendered task prompt contains the injected name, retrieved context,
  memory summary, and topic verbatim;
- no unrendered `{placeholder}` text leaks into the output;
- the two personas produce distinct system prompts *and* distinct
  rendered task prompts.

**`tests/test_yaml_loader.py`** — covers the validation contract directly:
a valid persona loads; a missing required field, a non-string required
field, an empty/whitespace-only required field, a malformed
`priorities`/`expertise` list, and syntactically invalid YAML all raise
`ValueError`; a nonexistent file raises `FileNotFoundError`.

## 8. Adding a New Persona

1. Create a new file under `personas/`, e.g. `personas/persona_c.yaml`.
2. Fill in `name`, `background`, `stance`, `tone` (all non-empty strings),
   plus optional `priorities`/`expertise` lists if useful.
3. Load it the same way: `load_persona("personas/persona_c.yaml")`.

No code changes are required — the loader and templates are persona-agnostic.

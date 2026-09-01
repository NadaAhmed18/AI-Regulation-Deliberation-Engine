# 🤖 Week 2 — Intelligent Agent Framework

## 1. Overview

This week transitions the project from a static vector database into an **Autonomous Agent Framework**. We built a custom ReAct (Reason + Act) engine that instantiates distinct, configuration-driven stakeholders (Personas). These agents possess short-term memory (SQLite), utilize dynamic prompt templates, and are equipped with a Tool Registry that allows them to autonomously query the Week 1 Neo4j Knowledge Base and the live web (Tavily). The result is a system that produces documented, RAG-grounded initial opinions on AI Regulation, fully prepared for Week 3's multi-agent debates.

---

## 2. Acceptance Criteria Checklist

- [x] **Task 1: Research LLMs** — Evaluated providers for function-calling support. Selected DeepSeek V4 Flash via OpenRouter (See `docs/llm-provider-decision.md`).
- [x] **Task 2: Agent Architecture** — Designed a modular ReAct blueprint separating Persona, Memory, Tools, and the Reasoning Loop (See `docs/agent-architecture.md`).
- [x] **Task 3: Implement Tools** — Wrapped the Neo4j RAG tool and added a live Web Search tool (Tavily), managed by a secure Tool Registry.
- [x] **Task 4: Configurable Personas** — Created YAML schemas for opposing stakeholders (Pro-Regulation vs. Pro-Innovation) avoiding hardcoded logic.
- [x] **Task 5: Agent Memory** — Implemented persistent SQLite memory (`memory.py`) to log agent utterances and opinion snapshots.
- [x] **Task 6: Prompt Templates** — Built a modular prompt builder injecting `{persona}`, `{retrieved_context}`, and `{memory}` into the LLM context.
- [x] **Task 7: Generate Opinions** — Successfully generated RAG-grounded opinions citing specific retrieved sources, saved to `outputs/initial_opinions.json`.

---

## 3. Directory Navigation & Key Files

The architecture strictly adheres to a decoupled, modular design:

| Component         | Location                        | Description                                                                 |
| :---------------- | :------------------------------ | :-------------------------------------------------------------------------- |
| **Personas**      | `personas/*.yaml`               | YAML configs defining agent identity, stance, and priorities.               |
| **Prompts**       | `prompts/initial_opinion.txt`   | The fill-in-the-blank template for the generation task.                     |
| **Agent Engine**  | `src/agent/base_agent.py`       | The core ReAct loop that manages thought, action, and observation.          |
| **Tools**         | `src/agent/tools/`              | Contains the `tool_registry.py`, Neo4j `retriever.py`, and `web_search.py`. |
| **Memory**        | `src/agent/utils/memory.py`     | SQLite implementation for agent state persistence.                          |
| **Documentation** | `docs/`                         | Contains architectural diagrams and design decision logs.                   |
| **Output**        | `outputs/initial_opinions.json` | The final generated opinions from the simulation run.                       |

---

## 4. Key Design Decisions

1. **LLM Choice (DeepSeek V4 via OpenRouter):** Selected for its native `tools`/`tool_choice` JSON-schema support and massive context window (1M tokens) at a highly efficient cost. It reliably handles our ReAct loop without the failure rates of smaller open-weight models.
2. **Tool Registry Pattern:** Instead of hardcoding tools into the agent, `tool_registry.py` acts as a middleware. It enforces Role-Based Access Control (e.g., Stakeholders can search, Moderators cannot) and catches tool execution errors, returning them as strings so the LLM can self-correct without crashing the script.
3. **SQLite for Memory:** While Neo4j handles our knowledge graph, we chose SQLite for Agent Memory. This separates factual ground-truth (Neo4j) from subjective agent state (Memory), simplifying the architecture and preventing cross-contamination of data.
4. **JSON Database Seeding (Week 1 Fix):** Based on reviewer feedback regarding Neo4j `.dump` version incompatibilities, we replaced the dump file with `import_db_from_json.py`. This rebuilds the entire vector/graph database natively via Cypher in seconds, ensuring 100% cross-version compatibility.

---

## 5. Setup & Dependencies

**1. Install Dependencies**
Ensure you are using Python 3.10+ and install the requirements:

```bash
cd backend
uv pip install -r requirements.txt  # or pip install -r requirements.txt
```

**2. Environment Variables**
Create a `.env` file in the `backend/` directory:

```ini
# LLM Provider
OPENROUTER_API_KEY=your_openrouter_key
DEFAULT_PROVIDER=openrouter
DEFAULT_MODEL=deepseek/deepseek-v4-flash

# Tools
TAVILY_API_KEY=your_tavily_key  # Optional: search_web degrades gracefully if missing

# Neo4j Database
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
```

---

## 6. Reviewer Instructions: How to Run

To verify the Acceptance Criteria, please run the following commands sequentially from the `backend/` directory.

### Step 1: Restore the Knowledge Base

_(This addresses Week 1 feedback. It takes ~2 seconds and safely overwrites/creates the vectors and relationships without needing an Embedding API key)._

```bash
python -m src.scripts.import_db_from_json
```

### Step 2: Generate Initial Opinions

Run the simulation orchestrator. This script will instantiate both personas (A and B), execute the ReAct loop, trigger the Neo4j/Web tools, and save the results.

```bash
python -m src.agent.utils.simulation_runner --generate-initial-opinions
```

### Step 3: Inspect the Output

Verify that the agents generated distinct, grounded opinions by checking the output file:
👉 **`outputs/initial_opinions.json`**

---

## 7. How to Reproduce Tests

We have included standalone unit tests covering YAML validation, Persona Injection, and the Mocked Tool-Calling Flow. They can be run via `pytest` or directly as Python modules.

**Run all tests (using Python):**

```bash
python -m tests.test_yaml_loader
python -m tests.test_persona_injection
python -m tests.test_tool_calling_flow
```

_(All tests execute locally and do not require live API keys or database connections)._

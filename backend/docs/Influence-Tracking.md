# Multi-Agent Collaboration & Opinion Dynamics Engine

A production-grade, multi-agent debate simulation and dynamic RAG platform. Autonomous AI stakeholder personas debate complex policy topics, dynamically query and ingest web knowledge into a graph database, and mathematically evolve their stances across rounds while tracking interpersonal influence.

---

## 1. System Architecture Overview

```
                        +---------------------------------------+
                        |      Setup Manager (LLM / Admin)      |
                        |   Generates Dynamic Stakeholder Nodes |
                        +-------------------+-------------------+
                                            |
                                            v
+---------------------------------------------------------------------------------------+
|                                LANGGRAPH DEBATE ENGINE                                |
|                                                                                       |
|   +---------------------+        +--------------------+        +------------------+   |
|   |  Node 1: Orchestrate| -----> | Node 2: Agent Turn | -----> |  Node 3: Grader  |   |
|   |  (Routes Next Turn) |        |   (ReAct Loop)     |        | (Stance & Delta) |   |
|   +---------------------+        +---------+----------+        +--------+---------+   |
|              ^                             |                            |             |
|              |                             v                            |             |
|              |                +---------------------------+             |             |
|              |                | Neo4j Graph RAG + Tavily  |             |             |
|              |                |  - Internal Vector Search |             |             |
|              |                |  - Live Web Scraping      |             |             |
|              |                |  - Autonomous Ingestion   |             |             |
|              |                +---------------------------+             |             |
|              |                                                          |             |
|              +----------------- Check Max Rounds <----------------------+             |
+-------------------------------------------|-------------------------------------------+
                                            |
                         Persists Every Turn & Metric
                                            |
                                            v
                 +-----------------------------------------------------+
                 |                POSTGRESQL DATA STORE                |
                 |  - simulations                                      |
                 |  - discussion_history (Stances, Sources, Influence) |
                 +-----------------------------------------------------+
```

---

## 2. Where Does the Data Live? (Storage Architecture)

The system uses a **dual-database architecture**: Neo4j handles unstructured semantic and relational knowledge, while PostgreSQL handles structured conversation state, agent metrics, and time-series analytics.

### A. PostgreSQL (Relational Discussion State & Analytics)
Every debate turn, agent utterance, stance score, and influence metric is saved immediately after execution.

#### Table 1: `simulations`
Tracks session-level metadata, configuration, and participants.
```sql
CREATE TABLE simulations (
    simulation_id VARCHAR(50) PRIMARY KEY,
    topic TEXT NOT NULL,
    memory_strategy JSONB NOT NULL,  -- e.g., {"type": "sliding_window", "window_size": 3}
    personas JSONB NOT NULL,         -- Array of generated persona objects
    status VARCHAR(20) DEFAULT 'running', -- 'running', 'completed', 'failed'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Table 2: `discussion_history`
Stores the chronologically ordered granular events of the debate.
```sql
CREATE TABLE discussion_history (
    id SERIAL PRIMARY KEY,
    simulation_id VARCHAR(50) REFERENCES simulations(simulation_id) ON DELETE CASCADE,
    round_number INTEGER NOT NULL,
    agent_name VARCHAR(100) NOT NULL,
    role VARCHAR(20) DEFAULT 'assistant',
    content TEXT NOT NULL,
    opinion_snapshot JSONB NOT NULL,     -- Stance scores, shifts, and influence deltas
    retrieved_sources JSONB DEFAULT '[]',-- Array of URLs cited/ingested during this turn
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

##### Exact JSON Schema of `opinion_snapshot`:
```json
{
  "current_stance_score": 1.75,
  "shift_magnitude": 0.45,
  "reasoning": "Agent shifted moderately toward regulation after reviewing safety audit logs.",
  "influence_signal": {
    "interacted_with": "Dr. Aris Thorne",
    "previous_distance": 4.10,
    "current_distance": 3.65,
    "convergence_delta": 0.45,
    "status": "influenced"
  }
}
```

##### Implementation Note: `PostgresClient.get_last_stance_score(sim_id, agent_name)`
Added alongside the stance-grading pipeline to fetch an agent's real
`current_stance_score` from their most recent row in
`discussion_history`, returning `None` (not `0.0`) if the agent has no
prior scored turn yet. `node_grade_opinion` (`discussion_graph.py`)
calls this before grading each turn and passes the result straight
through as `previous_score`, instead of the placeholder `0.0` used
earlier — see Section 3's Implementation Notes for why that distinction
matters for `shift_magnitude`.

---

### B. Neo4j (Graph-Augmented RAG Store)
Neo4j stores vetted policy documents, embedded text chunks, and their semantic cross-document hyperlinks.

*   **`(:Document)` Node:** Represents an entire web page or policy paper.
    *   Properties: `document_url` (unique indexed), `domain`, `related_documents` (list of URLs), `metadata`.
*   **`(:Chunk)` Node:** An atomic text segment derived from a document.
    *   Properties: `chunk_id` (unique indexed hash), `text`, `chunk_index`, `embedding` (vector property).
*   **Edges:**
    *   `(:Document)-[:HAS_CHUNK]->(:Chunk)`: Maps parent documents to ordered chunks.
    *   `(:Document)-[:RELATES_TO]->(:Document)`: Maps cross-document citations and semantic links.

---

## 3. High-Speed Stance & Opinion Shift Tracking with `cross-encoder/nli-deberta-v3-small`

Instead of relying on a slow, expensive LLM to calculate stance numbers, you can run a **local Natural Language Inference (NLI) Cross-Encoder**. It executes in ~15ms on GPU and ~50ms on CPU.

### A. How NLI Calculates Stance Mathematically
NLI classifies the relationship between a **Premise** and a **Hypothesis** into three probabilities that sum to 1.0:
$$\{P(\text{contradiction}), P(\text{neutral}), P(\text{entailment})\}$$

We formulate zero-shot stance detection by pairing the **Agent's Statement** (Premise) against two opposing **Hypotheses**:

$$\text{Premise } (P) = \text{"Agent's Latest Statement"}$$
$$\text{Hypothesis}_{\text{pro}} = \text{"This statement strongly supports and favors " } + \text{Topic}$$
$$\text{Hypothesis}_{\text{anti}} = \text{"This statement strongly opposes and rejects " } + \text{Topic}$$

1. We calculate $P(\text{entailment})$ for both hypotheses using the cross-encoder:
   *   $S_{\text{pro}} = P(\text{Hypothesis}_{\text{pro}} \text{ is TRUE given } P)$
   *   $S_{\text{anti}} = P(\text{Hypothesis}_{\text{anti}} \text{ is TRUE given } P)$
2. The continuous stance score $S \in [-5.0, +5.0]$ is computed as:
   $$S = (S_{\text{pro}} - S_{\text{anti}}) \times 5.0$$
3. The **shift magnitude** between turn $t-1$ and turn $t$ is:
   $$\text{Shift} = S_t - S_{t-1}$$

### B. Complete Implementation Class
Create `backend/src/orchestration/nli_grader.py`:

```python
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from typing import Dict, Any

class DebertaStanceGrader:
    def __init__(self, model_name: str = "cross-encoder/nli-deberta-v3-small"):
        print(f"[*] Initializing local NLI Stance Grader: {model_name}")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name).to(self.device)
        self.model.eval()

        # The model outputs logits for [Contradiction, Entailment, Neutral]
        # In DeBERTa-v3-small NLI, label mapping: 0 -> contradiction, 1 -> entailment, 2 -> neutral
        self.entailment_idx = 1

    def _get_entailment_prob(self, premise: str, hypothesis: str) -> float:
        """Runs a forward pass to get the exact entailment probability."""
        inputs = self.tokenizer(
            premise,
            hypothesis,
            truncation=True,
            max_length=512,
            return_tensors="pt"
        ).to(self.device)

        with torch.no_grad():
            logits = self.model(**inputs).logits
            probs = torch.softmax(logits, dim=-1).squeeze()
            return float(probs[self.entailment_idx].item())

    def evaluate_stance(
        self, 
        topic: str, 
        statement: str, 
        previous_score: float = 0.0
    ) -> Dict[str, Any]:
        """Calculates stance score on a -5.0 to +5.0 scale using NLI."""
        # 1. Build Hypotheses
        hypo_pro = f"This statement supports and argues in favor of {topic}."
        hypo_anti = f"This statement opposes and argues against {topic}."

        # 2. Get Entailment Probabilities
        prob_pro = self._get_entailment_prob(premise=statement, hypothesis=hypo_pro)
        prob_anti = self._get_entailment_prob(premise=statement, hypothesis=hypo_anti)

        # 3. Compute continuous stance between -5.0 and +5.0
        # If prob_pro > prob_anti, score is positive. If prob_anti > prob_pro, score is negative.
        raw_score = (prob_pro - prob_anti) * 5.0
        clamped_score = max(-5.0, min(5.0, round(raw_score, 2)))
        shift_magnitude = round(clamped_score - previous_score, 2)

        return {
            "current_stance_score": clamped_score,
            "shift_magnitude": shift_magnitude,
            "pro_probability": round(prob_pro, 3),
            "anti_probability": round(prob_anti, 3),
            "engine": "cross-encoder/nli-deberta-v3-small"
        }

if __name__ == "__main__":
    # Smoke Test
    grader = DebertaStanceGrader()
    topic = "mandatory licensing for high-compute AI models"
    statement = (
        "We cannot allow unrestricted open weights when national security risks are real. "
        "Strict oversight, licensing, and compliance protocols must be mandatory."
    )
    result = grader.evaluate_stance(topic=topic, statement=statement, previous_score=0.0)
    print("NLI Evaluation Result:", result)
    # Expected output: high pro_probability, current_stance_score > 3.0
```

### C. Implementation Notes (deviations from the spec above)

- **Model**: `cross-encoder/nli-deberta-v3-large` is used instead of
  `-small`. Same model family and 3-way label scheme (`contradiction` /
  `neutral` / `entailment`) as the spec above, just the larger checkpoint.
  Chosen over `MoritzLaurer/deberta-v3-base-zeroshot-v2.0` (a
  zero-shot-specific model with binary entailment/not_entailment labels
  that was also benchmarked) to stay on the spec's standard 3-way NLI
  family; benchmarking across ~15 varied statements
  (`compare_nli_models.py` / `benchmark_nli_models.py`) found the
  MoritzLaurer models scored higher sign-accuracy at comparable or lower
  latency in that specific test set, so if accuracy on this project's
  actual statements turns out too low in practice, they remain the
  better-evidenced fallback.
- **Label indices**: read dynamically from the loaded model's
  `config.id2label` (`_find_label_indices`) instead of hardcoded
  (`self.entailment_idx = 1`), so swapping `model_name` doesn't require a
  code change. This also locates the contradiction index (see next
  point), not only entailment.
- **Two-way softmax, not three-way**: entailment probability is computed
  by softmaxing ONLY the entailment and contradiction logits, discarding
  "neutral" entirely — not a full softmax over all 3 classes. For a
  binary (entailment/not_entailment) model these are identical, so this
  was never an issue with the spec's original `-small` model or with the
  binary MoritzLaurer models; it matters specifically for this 3-way
  model, where a full 3-way softmax lets neutral probability mass dilute
  the entailment score, and where it also matches how
  `transformers.pipeline("zero-shot-classification", ...,
  multi_label=True)` scored each hypothesis in this project's own model
  benchmarking above — keeping the live grader's numbers aligned with
  what was actually benchmarked to justify this model choice.
- **Hypothesis phrasing**: `"The speaker is in favor of {topic}."` /
  `"The speaker is opposed to {topic}."` ("simple" phrasing), not the
  spec's longer `"This statement supports and argues in favor of
  {topic}."` form. Benchmarking both phrasings on the same statements
  across all 3 candidate models showed the simple form scored
  equal-or-better in every case. `pro_proposition`/`anti_proposition`
  parameters allow overriding this per call for topics that need a more
  specific proposition (see `evaluate_stance`'s docstring).
- **Batching**: the pro/anti hypothesis pairs are sent in a single
  batched forward pass instead of two sequential calls.
- **`previous_score`**: defaults to `None` (no prior turn), not `0.0`.
  `0.0` is a genuine neutral prior score; `None` means "no score exists
  yet for this agent." The caller is responsible for fetching the
  agent's actual previous score (e.g. from `discussion_history` in
  PostgreSQL) rather than always passing `0.0` — see the fix in
  `node_grade_opinion` (`discussion_graph.py`) and
  `PostgresClient.get_last_stance_score`.
- The score/shift math itself is extracted into
  `backend/src/utils/stance_utils.py` so it's unit-testable without a
  model loaded, and reusable by Week 4 analytics and by `OpinionGrader`
  (`opinion_grader.py` also calls `stance_utils.compute_shift_magnitude`,
  so both graders treat a missing prior score identically).

---

## 4. The Influence Network & Tracking Specification

### A. Mathematical Logic
When **Agent B** speaks immediately following **Agent A**, we measure whether Agent A successfully persuaded Agent B.

1. **Initial Ideological Gap:**
   $$\text{Dist}_{\text{prev}} = |S_B(t-1) - S_A(t-1)|$$
2. **Post-Speech Ideological Gap:**
   $$\text{Dist}_{\text{new}} = |S_B(t) - S_A(t-1)|$$
3. **Convergence Delta ($\Delta$):**
   $$\Delta = \text{Dist}_{\text{prev}} - \text{Dist}_{\text{new}}$$

*   $\Delta > 0$: **Positive Influence**. Agent B moved closer to Agent A. Influence weight $w(A \to B) = \Delta$.
*   $\Delta < 0$: **Polarization/Backfire**. Agent B moved further away from Agent A.
*   $\Delta = 0$: **Zero Influence**.

### B. Influence Graph Calculation (Code Utility)
Add this utility to compute the complete influence matrix across an entire debate.
(This exists as `backend/src/orchestration/influence_tracker.py` — see the
Implementation Notes below for two bug fixes vs. this reference code.)

```python
# backend/src/orchestration/influence_tracker.py
from typing import List, Dict, Any

def compute_influence_matrix(history_rows: List[Dict[str, Any]], personas: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    """
    Parses PostgreSQL discussion history and constructs a directed 
    adjacency matrix where edge weight represents cumulative persuasion.
    """
    agent_names = [p["name"] for p in personas]
    # Initialize zeroed adjacency matrix: matrix[Influencer][Target] = weight
    matrix = {src: {dst: 0.0 for dst in agent_names} for src in agent_names}
    
    # Track latest known stance per agent across rounds
    current_stances = {name: 0.0 for name in agent_names}

    for i in range(1, len(history_rows)):
        prev_turn = history_rows[i - 1]
        curr_turn = history_rows[i]

        influencer = prev_turn["agent_name"]
        target = curr_turn["agent_name"]

        if influencer == target:
            continue

        target_prev_stance = current_stances[target]
        influencer_stance = current_stances[influencer]
        
        target_new_stance = curr_turn["opinion_snapshot"]["current_stance_score"]
        current_stances[target] = target_new_stance

        # Calculate convergence
        dist_prev = abs(target_prev_stance - influencer_stance)
        dist_new = abs(target_new_stance - influencer_stance)
        delta = dist_prev - dist_new

        if delta > 0:
            matrix[influencer][target] += round(delta, 2)

    return matrix
```

### C. Implementation Notes (deviations from the reference code above)

The actual implementation in `backend/src/orchestration/influence_tracker.py`
fixes two bugs in the reference code shown in section B above:

- **`None` vs. `0.0` for "no known stance yet"**: the reference code
  initializes every agent's `current_stances[name]` to `0.0` before the
  discussion starts. That conflates "this agent's stance is genuinely
  neutral" with "this agent hasn't been scored yet, so no stance is
  known" — which can register a large, spurious "influence" event on an
  agent's very first turn, measured against a `0.0` nobody ever actually
  held. The real implementation tracks each agent's known stance as
  `Optional[float]` (`None` until scored) and skips the convergence
  calculation entirely whenever either endpoint's stance is still
  unknown. This mirrors the same `None`-vs-`0.0` distinction used for
  `previous_score` throughout the stance-grading pipeline — see
  `stance_utils.compute_shift_magnitude` and
  `PostgresClient.get_last_stance_score`.
- **Every turn updates the *speaker's own* tracked stance, not only the
  turn's "target"**: the reference loop only ever writes
  `current_stances[target] = ...`, so an agent's own first turn is never
  recorded into `current_stances` unless that agent later appears as
  someone else's "target" — silently losing the very first speaker's
  real opening stance for as long as they keep speaking as "influencer"
  without ever being scored as "target" first. The real implementation
  records `current_stances[row["agent_name"]]` on every row,
  unconditionally, so an agent's latest known stance is always available
  from their own turns.

Both fixes only change behavior for edge cases (an agent's first-ever
turn, or a discussion history that doesn't start with every agent
speaking as "target" at least once) — normal multi-round discussions
where everyone has spoken and been spoken-to at least once are scored
identically either way.

---

## 5. Agent Graph Topology & Routing (`agent_graph.py`)

To satisfy strict multi-agent topology requirements (e.g., verifying that the agent network is strongly connected and controlling message routing), implement `backend/src/orchestration/agent_graph.py`:

```python
import networkx as nx
from typing import List, Dict

class AgentCommunicationGraph:
    def __init__(self, personas: List[Dict[str, str]]):
        self.graph = nx.DiGraph()
        self.names = [p["name"] for p in personas]
        
        # 1. Add nodes
        for p in personas:
            self.graph.add_node(p["name"], **p)

        # 2. Build default strongly connected topology (Full Directed Mesh)
        for src in self.names:
            for dst in self.names:
                if src != dst:
                    self.graph.add_edge(src, dst)

    def is_strongly_connected(self) -> bool:
        """Acceptance Test 1: Returns True if every agent can reach every other agent."""
        return nx.is_strongly_connected(self.graph)

    def disable_edge(self, source: str, target: str):
        """Removes a communication link to test message isolation."""
        if self.graph.has_edge(source, target):
            self.graph.remove_edge(source, target)

    def can_receive_message(self, sender: str, receiver: str) -> bool:
        """Acceptance Test 4: Functional message filter."""
        return self.graph.has_edge(sender, receiver)
```

---

## 6. End-to-End Execution Flow

1. **Setup Phase:**
   * User supplies `topic` and `num_agents`.
   * `setup_manager.py` calls the LLM, outputs a validated JSON list of personas, and writes a row to PostgreSQL table `simulations`.
   * `agent_graph.py` builds the strongly connected network topology.

2. **Debate Execution Loop (LangGraph):**
   * **Node 1 (`orchestrate`):** Reads the last 3 turns and the communication graph. Generates structured JSON: `{"next_speaker": "Name"}`.
   * **Node 2 (`agent_turn`):** The chosen agent executes their ReAct loop.
     * Searches internal Neo4j knowledge base via `search_ai_policy`.
     * Searches live internet via `search_web`.
     * If a high-value URL is found, calls `learn_and_ingest_url` to crawl, chunk, embed, and permanently link it into Neo4j.
     * Returns final utterance and list of cited URLs.
   * **Node 3 (`grade_opinion`):**
     * Evaluates latest statement using `DebertaStanceGrader` (or `OpinionGrader`).
     * Calculates convergence delta ($\Delta$) against the previous speaker.
     * Calls `db.save_discussion_turn(...)` to append the record to PostgreSQL.
   * **Conditional Edge:** Loops until `current_round == max_rounds`.

---

## 7. Developer Quickstart & Verification

### 1. Environment Setup
```bash
# Clone and enter repo
cd Ai-Regulation/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure `.env`
```env
OPENROUTER_API_KEY=your_key_here
VOYAGE_API_KEY=your_key_here
TAVILY_API_KEY=your_key_here
DATABASE_URL=postgresql://postgres:password@localhost:5432/ai_regulation
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password123
```

### 3. Run Acceptance Tests
```bash
# 1. Test graph connectivity (Task 1 & Task 4)
python -c "
from src.orchestration.agent_graph import AgentCommunicationGraph
g = AgentCommunicationGraph([{'name': 'A'}, {'name': 'B'}, {'name': 'C'}])
assert g.is_strongly_connected() == True
g.disable_edge('A', 'B')
assert g.can_receive_message('A', 'B') == False
print('Graph Connectivity & Edge Filtering: PASSED')
"

# 2. Test NLI Stance Detection
python -m src.orchestration.nli_grader

# 3. Execute Full Debate Engine
python -m src.orchestration.discussion_graph
```
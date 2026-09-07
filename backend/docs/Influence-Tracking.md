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
Add this utility to compute the complete influence matrix across an entire debate:

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
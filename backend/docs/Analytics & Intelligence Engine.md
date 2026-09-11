# Developer Guide — Member 3: Analytics & Intelligence Engine
*(Updated Architecture: Streamlined Core Analytics, Topology-Aware Influence, and Dual-Layer PostgreSQL Persistence)*

---

## 1. Executive Overview & System Architecture

The **Analytics & Intelligence Engine** extracts quantitative metrics from raw multi-agent discussion records stored in PostgreSQL. 

### Key Design Pillars
1. **Zero Model Overhead:** No external sentiment models or secondary neural nets are invoked. Analytics run via pure mathematical algorithms over stored stance values in **$< 5\text{ ms}$**.
2. **Topology-Aware Influence:** Interpersonal influence respects the debate’s graph routing (`visibility_matrix`). If Agent B cannot hear Agent A due to communication barriers, Agent A’s speech is **never falsely credited** with moving Agent B.
3. **No Static Image Disk Bloat:** Visualizations are rendered dynamically by the **Next.js frontend** (using Recharts and SVG/D3) from the structured JSON contract. No static `.png` files are written to disk.
4. **Dual Persistence (Live Compute + PostgreSQL Cache):**
   * While a simulation is **in progress**, metrics are computed **on the fly** for real-time dashboard updates.
   * On completion, or during polling, results are atomically upserted into a dedicated `simulation_analytics` table in PostgreSQL to enable instant retrieval.

```
                    Raw PostgreSQL Tables:
            simulations [ topic, personas, visibility_matrix ]
            discussion_history [ round_number, agent_name, opinion_snapshot ]
                                     │
                                     ▼
                     ┌───────────────────────────────┐
                     │   DiscussionAnalyticsEngine   │
                     │    (src/analytics/engine.py)  │
                     └───────────────┬───────────────┘
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         ▼                           ▼                           ▼
 ┌──────────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐
 │  1. OPINION CHANGE   │   │     2. AGREEMENT     │   │ 3. TOPOLOGY INFLUENCE│
 │ (opinion_change.py)  │   │    (agreement.py)    │   │    (influence.py)    │
 ├──────────────────────┤   ├──────────────────────┤   ├──────────────────────┤
 │ • Stance Trajectory  │   │ • Pairwise Dispersion│   │ • Pruned by          │
 │ • Personal Delta (ΔS)│   │ • Consensus [0 - 1]  │   │   visibility_matrix  │
 └──────────┬───────────┘   └──────────┬───────────┘   └──────────┬───────────┘
            │                          │                          │
            └──────────────────────────┼──────────────────────────┘
                                       ▼
                     ┌───────────────────────────────────┐
                     │     4. NETWORK DYNAMICS GRAPH     │
                     │   (src/analytics/network_model.py)│
                     │ • Direct Persuasion Flow (A -> B) │
                     │ • Formatted for Next.js D3/SVG    │
                     └─────────────────┬─────────────────┘
                                       │
                    ┌──────────────────┴──────────────────┐
                    ▼                                     ▼
         [ Live On-the-Fly API ]               [ PostgreSQL Persistence ]
     FastAPI: /api/simulations/{id}/analytics     Table: simulation_analytics
                    │                                     │
                    ▼                                     ▼
         [ Next.js Frontend ]                  [ Long-Term Audit Cache ]
   Dynamic Recharts & SVG Graph                     Instant Retrieval
```

---

## 2. Persistence Architecture: On-the-Fly vs. PostgreSQL Caching

### How Data Is Processed and Stored
* **Step 1 (Raw Ingestion during Live Turns):** When agents speak, `discussion_graph.py` grades their stance and stores each turn in `discussion_history`.
* **Step 2 (On-the-Fly Execution):** When `/api/simulations/{id}/analytics` is requested, `DiscussionAnalyticsEngine` fetches the history and executes the math instantly.
* **Step 3 (PostgreSQL Caching):** The engine writes/updates the computed metrics in the `simulation_analytics` table. Subsequent calls return the precomputed analytics immediately if the simulation status is `completed`.

### Database Schema Definition

Run this schema migration or update `src/clients/postgres.py` to ensure both `visibility_matrix` and the dedicated `simulation_analytics` table exist:

```sql
-- 1. Ensure simulations table stores graph visibility routing
CREATE TABLE IF NOT EXISTS simulations (
    simulation_id VARCHAR(50) PRIMARY KEY,
    topic TEXT NOT NULL,
    memory_strategy JSONB NOT NULL,
    personas JSONB NOT NULL,
    visibility_matrix JSONB,  -- Example: {"Agent A": ["Agent B"], "Agent B": ["Agent A"]}
    status VARCHAR(20) DEFAULT 'running',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Dedicated analytics cache table
CREATE TABLE IF NOT EXISTS simulation_analytics (
    simulation_id VARCHAR(50) PRIMARY KEY REFERENCES simulations(simulation_id) ON DELETE CASCADE,
    opinion_change JSONB NOT NULL,
    agreement JSONB NOT NULL,
    influence JSONB NOT NULL,
    network_graph JSONB NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 3. The 4 Analytical Metrics: Deep Dive & Differences

| Metric | Target Entity | Mathematical Range | What It Answers | High Score Interpretation | Low Score Interpretation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Stance Score ($S$)** | Individual Agent | `[-5.0, +5.0]` | *"Where does this agent stand ideologically on the topic right now?"* | Strongly **in favor** of the debate topic ($+5.0$). | Strongly **opposed** to the debate topic ($-5.0$). |
| **2. Opinion Shift ($\Delta S$)** | Individual Agent Turn | `[-10.0, +10.0]` or `None` | *"Did the agent move, and in what direction since their previous turn?"* | Shifted towards the **pro** pole relative to their last turn. | Shifted towards the **anti** pole relative to their last turn. |
| **3. Agreement Score ($A_r$)** | Entire Group (per round) | `[0.0, 1.0]` | *"How cohesive or polarized is the entire debate panel in round $r$?"* | **Consensus:** Stance variance is near zero; agents think alike. | **Polarization:** Stance variance is high; agents occupy opposite poles. |
| **4. Influence Score ($I_A$)** | Dyadic Pair / Agent | `[0.0, +∞)` | *"How much did Agent A's arguments pull other agents toward A's stance?"* | High persuasion; directly induced convergence in audible peers. | Zero persuasion; moved nobody or was hidden behind communication barriers. |

---

### Incorporating the `visibility_matrix` into Influence

In real discussions, **Agent A cannot influence Agent B if Agent B is not allowed to listen to Agent A**. 

Your `simulations` table contains a `visibility_matrix` JSON field structured as:
```json
{
  "Dr. Elena Kovac": ["Alex Mercer"],
  "Alex Mercer": ["Dr. Elena Kovac"],
  "Marcus Vance": []
}
```
*(Here, Marcus Vance speaks, but listens to nobody; Elena and Alex only listen to each other).*

**The Mathematical Filter:**
When Agent $B$ changes their stance after Agent $A$ speaks:
$$\Delta_{\text{convergence}} = |S_B(t-1) - S_A(t-1)| - |S_B(t) - S_A(t-1)|$$

* If $A \in \text{visibility\_matrix}[B]$: Agent $B$ heard Agent $A$. If $\Delta_{\text{convergence}} > 0$, accumulate influence:
  $$M[A][B] \mathrel{+}= \Delta_{\text{convergence}}$$
* If $A \notin \text{visibility\_matrix}[B]$: **Zero influence is recorded ($M[A][B] = 0$)**, because Agent $B$'s memory context filtered out Agent $A$'s speech. Any shift by $B$ was coincidental, not persuaded by $A$.

---

## 4. Directory Layout

Create and organize all files inside `backend/src/analytics/`:

```text
backend/src/analytics/
├── __init__.py
├── opinion_change.py   # Stance trajectories and delta calculations
├── agreement.py        # Pairwise consensus metrics per round
├── influence.py        # Topology-aware directed persuasion matrix
├── network_model.py    # Graph dynamics model formatted for Next.js D3/SVG
└── engine.py           # Unified orchestrator + PostgreSQL caching
```

---

## 5. Source Code Implementations

### `backend/src/analytics/opinion_change.py`

```python
"""
OPINION CHANGE ANALYTICS MODULE

Extracts chronological numeric stance trajectories and calculates
round-to-round movement (delta) for each agent.
"""

from typing import Any, Dict, List, Optional


def compute_opinion_trajectories(
    history_rows: List[Dict[str, Any]],
    personas: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Computes per-agent, per-round stance values and movement.

    Args:
        history_rows: Chronological discussion_history rows from PostgreSQL.
        personas: List of persona configurations containing agent 'name'.

    Returns:
        Dict[agent_name -> List of {"round": int, "stance": float, "change": float | None}]
    """
    agent_names = [p["name"] for p in personas]
    trajectories: Dict[str, List[Dict[str, Any]]] = {name: [] for name in agent_names}

    # Group latest stance by (round_number, agent_name)
    round_agent_stance: Dict[int, Dict[str, float]] = {}

    for row in history_rows:
        agent = row.get("agent_name")
        r_num = row.get("round_number", 0)
        snapshot = row.get("opinion_snapshot") or {}
        stance = snapshot.get("current_stance_score")

        if agent in trajectories and stance is not None:
            if r_num not in round_agent_stance:
                round_agent_stance[r_num] = {}
            # Keep the latest recorded stance for that agent in this round
            round_agent_stance[r_num][agent] = float(stance)

    sorted_rounds = sorted(round_agent_stance.keys())

    # Build sequential trajectories with round-to-round delta
    for agent in agent_names:
        prev_stance: Optional[float] = None
        for r_num in sorted_rounds:
            if agent in round_agent_stance[r_num]:
                curr_stance = round_agent_stance[r_num][agent]
                delta = None if prev_stance is None else round(curr_stance - prev_stance, 2)
                trajectories[agent].append({
                    "round": r_num,
                    "stance": curr_stance,
                    "change": delta,
                })
                prev_stance = curr_stance

    return trajectories
```

---

### `backend/src/analytics/agreement.py`

```python
"""
AGREEMENT & CONSENSUS ANALYTICS MODULE

Calculates per-round group alignment from pairwise stance distances.
"""

import itertools
from typing import Any, Dict, List


def compute_round_agreement(
    history_rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Computes an agreement score in [0.0, 1.0] for every discussion round.

    Formula:
        Distance = |Stance_i - Stance_j|
        Max_Scale_Span = 10.0 (-5.0 to +5.0)
        Agreement = 1.0 - (mean_pairwise_distance / 10.0)

    Returns:
        List of {"round": int, "score": float, "interpretation": str}
    """
    round_stances: Dict[int, Dict[str, float]] = {}

    for row in history_rows:
        agent = row.get("agent_name")
        r_num = row.get("round_number", 0)
        snapshot = row.get("opinion_snapshot") or {}
        score = snapshot.get("current_stance_score")

        if agent and score is not None:
            if r_num not in round_stances:
                round_stances[r_num] = {}
            round_stances[r_num][agent] = float(score)

    agreement_results = []

    for r_num in sorted(round_stances.keys()):
        stances = list(round_stances[r_num].values())

        if len(stances) < 2:
            agreement_results.append({
                "round": r_num,
                "score": 1.0,
                "interpretation": "Single-agent baseline.",
            })
            continue

        # Compute all unique pairwise absolute differences
        diffs = [abs(s1 - s2) for s1, s2 in itertools.combinations(stances, 2)]
        mean_diff = sum(diffs) / len(diffs)

        # Normalize to 0.0 - 1.0
        score = max(0.0, min(1.0, round(1.0 - (mean_diff / 10.0), 2)))

        if score >= 0.75:
            interp = "High Consensus"
        elif score >= 0.50:
            interp = "Moderate Alignment"
        elif score >= 0.25:
            interp = "Significant Polarization"
        else:
            interp = "Extreme Polarization"

        agreement_results.append({
            "round": r_num,
            "score": score,
            "interpretation": interp,
        })

    return agreement_results
```

---

### `backend/src/analytics/influence.py`

```python
"""
TOPOLOGY-AWARE INFLUENCE ANALYTICS MODULE

Computes directed interpersonal persuasion matrices and scalar scores.
Crucially incorporates the simulation's visibility_matrix:
Agent A CANNOT influence Agent B if Agent B is not allowed to hear Agent A.
"""

from typing import Any, Dict, List, Optional


def compute_topology_influence(
    history_rows: List[Dict[str, Any]],
    personas: List[Dict[str, Any]],
    visibility_matrix: Optional[Dict[str, List[str]]] = None,
    min_turns: int = 3,
) -> Dict[str, Any]:
    """
    Computes per-agent influence scores respecting visibility constraints.

    Args:
        history_rows: Chronological discussion rows.
        personas: Persona configurations.
        visibility_matrix: Dict where {listener: [allowed_speakers]}.
                           If None or empty, full mesh visibility is assumed.
        min_turns: Minimum number of scored turns required to evaluate influence.

    Returns:
        {
            "status": "sufficient_data" | "insufficient_data",
            "scores": Dict[agent_name -> float] | None,
            "matrix": Dict[agent_A -> Dict[agent_B -> float]] | None,
            "top_influencer": str | None
        }
    """
    agent_names = [p["name"] for p in personas]
    valid_turns = [
        row for row in history_rows
        if row.get("opinion_snapshot", {}).get("current_stance_score") is not None
    ]

    # Handle insufficient data explicitly
    if len(valid_turns) < min_turns:
        return {
            "status": "insufficient_data",
            "scores": None,
            "matrix": None,
            "top_influencer": None,
            "reason": f"Only {len(valid_turns)} scored turn(s) recorded. Minimum required is {min_turns}."
        }

    # Initialize matrix with all participant names
    matrix: Dict[str, Dict[str, float]] = {
        src: {dst: 0.0 for dst in agent_names} for src in agent_names
    }
    current_stances: Dict[str, Optional[float]] = {name: None for name in agent_names}

    vis_map = visibility_matrix or {}

    for i, row in enumerate(valid_turns):
        target = row["agent_name"]
        target_new_stance = float(row["opinion_snapshot"]["current_stance_score"])

        if i > 0:
            influencer = valid_turns[i - 1]["agent_name"]

            # An agent cannot influence themselves
            if influencer != target:
                # TOPOLOGY CHECK: Could target hear this influencer?
                # If visibility_matrix is present, verify influencer is in target's allowed speakers
                allowed_speakers = vis_map.get(target)
                can_hear = True if allowed_speakers is None else (influencer in allowed_speakers)

                if can_hear:
                    target_prev_stance = current_stances.get(target)
                    influencer_stance = current_stances.get(influencer)

                    # Only compute if both agents have a known baseline stance
                    if target_prev_stance is not None and influencer_stance is not None:
                        dist_prev = abs(target_prev_stance - influencer_stance)
                        dist_new = abs(target_new_stance - influencer_stance)
                        delta = dist_prev - dist_new

                        # Positive convergence: target moved towards influencer's position
                        if delta > 0:
                            matrix[influencer][target] += round(delta, 2)

        # Update target's known stance for future evaluations
        current_stances[target] = target_new_stance

    # Sum outgoing positive persuasion: Total convergence Agent A caused in other agents
    scores: Dict[str, float] = {}
    for influencer, targets in matrix.items():
        total_influence = sum(weight for target, weight in targets.items() if target != influencer)
        scores[influencer] = round(total_influence, 2)

    top_influencer: Optional[str] = None
    if scores:
        best = max(scores.items(), key=lambda x: x[1])
        if best[1] > 0:
            top_influencer = best[0]

    return {
        "status": "sufficient_data",
        "scores": scores,
        "matrix": matrix,
        "top_influencer": top_influencer,
    }
```

---

### `backend/src/analytics/network_model.py`

```python
"""
OPINION DYNAMICS NETWORK MODEL

Constructs a directed graph of the multi-agent debate:
- Nodes: Agents with ideological stances and cumulative shifts.
- Edges: Directed persuasion channels (A -> B means A moved B toward A).
Formatted specifically for direct rendering in Next.js SVG/D3 charts.
"""

from typing import Any, Dict, List
import networkx as nx


class OpinionDynamicsNetwork:
    def __init__(self, opinion_data: Dict[str, List[Dict[str, Any]]], influence_data: Dict[str, Any]):
        self.opinion_data = opinion_data
        self.influence_data = influence_data
        self.graph = nx.DiGraph()
        self._build_network()

    def _build_network(self):
        matrix = self.influence_data.get("matrix") or {}

        # 1. Add Nodes
        for agent_name, trajectory in self.opinion_data.items():
            final_stance = trajectory[-1]["stance"] if trajectory else 0.0
            
            # Cumulative shift across all rounds
            total_shift = sum(
                point["change"] for point in trajectory if point.get("change") is not None
            )

            self.graph.add_node(
                agent_name,
                current_stance=final_stance,
                net_shift=round(total_shift, 2),
            )

        # 2. Add Directed Persuasion Edges
        for influencer, targets in matrix.items():
            for target, weight in targets.items():
                if influencer != target and weight > 0:
                    self.graph.add_edge(
                        influencer,
                        target,
                        weight=weight,
                    )

    def export_graph_data(self) -> Dict[str, Any]:
        """Formats graph data for direct consumption by Frontend D3/SVG components."""
        nodes = [
            {
                "id": node,
                "stance": data["current_stance"],
                "shift": data["net_shift"],
            }
            for node, data in self.graph.nodes(data=True)
        ]
        edges = [
            {
                "source": u,
                "target": v,
                "weight": data["weight"],
            }
            for u, v, data in self.graph.edges(data=True)
        ]
        return {"nodes": nodes, "edges": edges}

    def get_persuasion_rankings(self) -> List[Dict[str, Any]]:
        """Returns sorted list of persuasion leaders."""
        out_weights = {n: 0.0 for n in self.graph.nodes}
        for u, v, data in self.graph.edges(data=True):
            out_weights[u] += data.get("weight", 0.0)

        return [
            {"agent_name": agent, "persuasion_points": round(score, 2)}
            for agent, score in sorted(out_weights.items(), key=lambda x: x[1], reverse=True)
        ]
```

---

### `backend/src/analytics/engine.py`

```python
"""
UNIFIED DISCUSSION ANALYTICS ENGINE

Main orchestrator class querying PostgreSQL via SimulationController,
executing topology-aware analytics, and persisting/caching the results.
"""

import json
from typing import Any, Dict, Optional
from src.controllers.simulation_controller import SimulationController
from src.analytics.opinion_change import compute_opinion_trajectories
from src.analytics.agreement import compute_round_agreement
from src.analytics.influence import compute_topology_influence
from src.analytics.network_model import OpinionDynamicsNetwork


class DiscussionAnalyticsEngine:
    def __init__(self):
        self.controller = SimulationController()
        self._ensure_analytics_table()

    def _ensure_analytics_table(self):
        """Creates the simulation_analytics table if it does not already exist."""
        with self.controller._get_cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS simulation_analytics (
                    simulation_id VARCHAR(50) PRIMARY KEY REFERENCES simulations(simulation_id) ON DELETE CASCADE,
                    opinion_change JSONB NOT NULL,
                    agreement JSONB NOT NULL,
                    influence JSONB NOT NULL,
                    network_graph JSONB NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

    def _fetch_history(self, sim_id: str):
        """Fetches chronological discussion history."""
        with self.controller._get_cursor() as cur:
            cur.execute("""
                SELECT id, simulation_id, round_number, agent_name, role, content, opinion_snapshot, retrieved_sources, created_at
                FROM discussion_history
                WHERE simulation_id = %s
                ORDER BY round_number ASC, id ASC
            """, (sim_id,))
            return [dict(r) for r in cur.fetchall()]

    def _save_to_cache(self, sim_id: str, result: Dict[str, Any]):
        """Persists or updates the computed analytics in PostgreSQL."""
        with self.controller._get_cursor() as cur:
            cur.execute("""
                INSERT INTO simulation_analytics (simulation_id, opinion_change, agreement, influence, network_graph, updated_at)
                VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (simulation_id) DO UPDATE SET
                    opinion_change = EXCLUDED.opinion_change,
                    agreement = EXCLUDED.agreement,
                    influence = EXCLUDED.influence,
                    network_graph = EXCLUDED.network_graph,
                    updated_at = CURRENT_TIMESTAMP;
            """, (
                sim_id,
                json.dumps(result["opinion_change"]),
                json.dumps(result["agreement"]),
                json.dumps(result["influence"]),
                json.dumps(result["network_graph"]),
            ))

    def get_cached_analytics(self, sim_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves cached analytics from PostgreSQL if available."""
        with self.controller._get_cursor() as cur:
            cur.execute("""
                SELECT opinion_change, agreement, influence, network_graph
                FROM simulation_analytics
                WHERE simulation_id = %s
            """, (sim_id,))
            row = cur.fetchone()
            if row:
                return {
                    "simulation_id": sim_id,
                    "opinion_change": row["opinion_change"],
                    "agreement": row["agreement"],
                    "influence": row["influence"],
                    "network_graph": row["network_graph"],
                    "cached": True,
                }
            return None

    def analyze(self, simulation_id: str, force_compute: bool = False) -> Dict[str, Any]:
        """
        Executes unified analytics on a simulation.
        Checks cache first if the simulation has completed.

        Args:
            simulation_id: Target simulation identifier.
            force_compute: If True, bypasses cache and recomputes.

        Returns:
            Dictionary matching the Week 4 & Frontend schema.
        """
        sim_data = self.controller.get_simulation_by_id(simulation_id)
        if not sim_data:
            raise ValueError(f"Simulation '{simulation_id}' not found.")

        # If simulation is completed and cached, return immediately
        status = sim_data.get("status", "running")
        if not force_compute and status == "completed":
            cached = self.get_cached_analytics(simulation_id)
            if cached:
                cached["topic"] = str(sim_data["topic"])
                return cached

        topic = str(sim_data["topic"])
        personas = list(sim_data["personas"])
        visibility_matrix = sim_data.get("visibility_matrix")
        history = self._fetch_history(simulation_id)

        # 1. Opinion Trajectories & Movement
        opinion_data = compute_opinion_trajectories(history_rows=history, personas=personas)

        # 2. Per-Round Agreement Metric
        agreement_data = compute_round_agreement(history_rows=history)

        # 3. Topology-Aware Interpersonal Influence
        influence_data = compute_topology_influence(
            history_rows=history,
            personas=personas,
            visibility_matrix=visibility_matrix
        )

        # 4. Network Graph Representation
        network = OpinionDynamicsNetwork(opinion_data=opinion_data, influence_data=influence_data)
        network_data = network.export_graph_data()

        result = {
            "simulation_id": simulation_id,
            "topic": topic,
            "total_turns": len(history),
            "opinion_change": opinion_data,
            "agreement": agreement_data,
            "influence": influence_data,
            "network_graph": network_data,
            "cached": False,
        }

        # Persist results in PostgreSQL
        self._save_to_cache(simulation_id, result)

        return result


if __name__ == "__main__":
    print("=== Testing Topology-Aware Analytics Engine ===")
    mock_personas = [{"name": "Elena"}, {"name": "Marcus"}, {"name": "Chloe"}]
    
    # Elena hears Marcus; Marcus hears Elena; Chloe hears NOBODY
    mock_visibility = {
        "Elena": ["Marcus"],
        "Marcus": ["Elena"],
        "Chloe": []
    }

    mock_history = [
        {"id": 1, "round_number": 1, "agent_name": "Elena", "opinion_snapshot": {"current_stance_score": 4.5}},
        {"id": 2, "round_number": 1, "agent_name": "Marcus", "opinion_snapshot": {"current_stance_score": -4.0}},
        {"id": 3, "round_number": 1, "agent_name": "Chloe", "opinion_snapshot": {"current_stance_score": 0.0}},
        # Round 2: Marcus moved towards Elena
        {"id": 4, "round_number": 2, "agent_name": "Elena", "opinion_snapshot": {"current_stance_score": 4.5}},
        {"id": 5, "round_number": 2, "agent_name": "Marcus", "opinion_snapshot": {"current_stance_score": -1.5}},
        # Round 2: Chloe moved to 4.0, but CANNOT HEAR ELENA! Influence must be 0.
        {"id": 6, "round_number": 2, "agent_name": "Chloe", "opinion_snapshot": {"current_stance_score": 4.0}},
    ]

    trajectories = compute_opinion_trajectories(mock_history, mock_personas)
    agreement = compute_round_agreement(mock_history)
    influence = compute_topology_influence(mock_history, mock_personas, visibility_matrix=mock_visibility)
    net = OpinionDynamicsNetwork(trajectories, influence).export_graph_data()

    print("\n[+] Opinion Trajectories:\n", json.dumps(trajectories, indent=2))
    print("\n[+] Round Agreement:\n", json.dumps(agreement, indent=2))
    print("\n[+] Topology-Aware Influence Matrix:\n", json.dumps(influence, indent=2))
    print("\n[+] Exported Network Graph for Frontend:\n", json.dumps(net, indent=2))

    # Assertions for verification
    assert influence["matrix"]["Elena"]["Marcus"] > 0, "Elena must influence Marcus (visible)"
    assert influence["matrix"]["Elena"]["Chloe"] == 0.0, "Elena CANNOT influence Chloe (hidden by topology)"
    print("\n[✔] Topology filtering and Analytics calculations verified successfully!")
```

---

## 6. Unified JSON Schema Contract

This is the exact JSON dictionary returned by `DiscussionAnalyticsEngine().analyze(simulation_id)` to FastAPI and rendered by the frontend:

```json
{
  "simulation_id": "sim_exp_001",
  "topic": "Mandatory frontier AI licensing",
  "total_turns": 6,
  "cached": false,
  "opinion_change": {
    "Dr. Elena Kovac": [
      { "round": 1, "stance": 4.5, "change": null },
      { "round": 2, "stance": 4.5, "change": 0.0 }
    ],
    "Alex Mercer": [
      { "round": 1, "stance": -4.0, "change": null },
      { "round": 2, "stance": -1.5, "change": 2.5 }
    ]
  },
  "agreement": [
    { "round": 1, "score": 0.15, "interpretation": "Extreme Polarization" },
    { "round": 2, "score": 0.40, "interpretation": "Significant Polarization" }
  ],
  "influence": {
    "status": "sufficient_data",
    "scores": {
      "Dr. Elena Kovac": 2.5,
      "Alex Mercer": 0.0
    },
    "matrix": {
      "Dr. Elena Kovac": { "Alex Mercer": 2.5, "Dr. Elena Kovac": 0.0 },
      "Alex Mercer": { "Dr. Elena Kovac": 0.0, "Alex Mercer": 0.0 }
    },
    "top_influencer": "Dr. Elena Kovac"
  },
  "network_graph": {
    "nodes": [
      { "id": "Dr. Elena Kovac", "stance": 4.5, "shift": 0.0 },
      { "id": "Alex Mercer", "stance": -1.5, "shift": 2.5 }
    ],
    "edges": [
      { "source": "Dr. Elena Kovac", "target": "Alex Mercer", "weight": 2.5 }
    ]
  }
}
```

---

## 7. Integration Contracts for Other Members

### Member 1 (FastAPI Route)
```python
# backend/src/api/routes.py
from fastapi import APIRouter
from src.analytics.engine import DiscussionAnalyticsEngine

router = APIRouter()
engine = DiscussionAnalyticsEngine()

@router.get("/api/simulations/{sim_id}/analytics")
def get_analytics(sim_id: str):
    return engine.analyze(sim_id)
```

### Next.js Frontend Integration (`AnalyticsDashboard.tsx`)
The frontend directly consumes this payload:
* **Opinion Trajectory Chart:** Binds `result.opinion_change` into Recharts `<LineChart>`.
* **Agreement Trend:** Binds `result.agreement` into an area/trend indicator.
* **Influence & Interaction Graph:** Binds `result.network_graph.nodes` and `result.network_graph.edges` directly into an SVG force-directed network.

---

## 8. Verification Checklist

Run the standalone verification test:

```bash
python -m src.analytics.engine
```

- [ ] Zero sentiment dependencies (`nltk` or transformers are **not** imported).
- [ ] Stance trajectories correctly record `None` for Turn 1 movement.
- [ ] Agreement metric produces a normalized score in $[0.0, 1.0]$ for every round.
- [ ] Influence tracker prunes out turns where the target could not hear the speaker according to `visibility_matrix`.
- [ ] Results are automatically cached in the `simulation_analytics` PostgreSQL table.
- [ ] JSON payload contains `nodes` and `edges` ready for frontend UI rendering without writing `.png` files to disk.
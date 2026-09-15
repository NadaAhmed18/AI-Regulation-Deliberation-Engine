import threading
from typing import Any, Dict, List, Optional

from src.analytics.engine import DiscussionAnalyticsEngine
from src.controllers.repository.analytics_repository import AnalyticsRepository
from src.controllers.repository.simulation_repository import SimulationRepository


class AnalyticsController:
    """
    Central Controller for metrics calculation, trajectory extraction, and replay analysis.
    """
    _instance: Optional["AnalyticsController"] = None
    _lock: threading.Lock = threading.Lock()

    # Explicit class-level type annotations for Pylance
    repo: AnalyticsRepository
    sim_repo: SimulationRepository
    engine: DiscussionAnalyticsEngine
    _initialized: bool

    def __new__(cls) -> "AnalyticsController":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return

        self.repo = AnalyticsRepository()
        self.sim_repo = SimulationRepository()
        self.engine = DiscussionAnalyticsEngine()
        self._initialized = True

    def get_simulation_analytics(
        self,
        simulation_id: str,
        round_number: Optional[int] = None,
        force_compute: bool = False,
    ) -> Dict[str, Any]:
        """
        Retrieves complete analytics.
        - If round_number is provided: Computes historical point-in-time metrics (Replay mode).
        - If debate is complete and round_number is None: Serves from pre-calculated cache.
        - Otherwise: Computes live metrics from database history.
        """
        sim = self.sim_repo.get_simulation_by_id(simulation_id)
        if not sim:
            raise ValueError(f"Simulation '{simulation_id}' not found.")

        is_completed = sim.get("status") == "completed"
        is_replay = round_number is not None

        # 1. Cache hit (Only for full, completed debates without replay slicing)
        if is_completed and not force_compute and not is_replay:
            cached = self.repo.get_cached_analytics(simulation_id)
            if cached:
                history = self.sim_repo.get_discussion_history(simulation_id)
                return self._format_response(cached, history, sim.get("personas", []))

        # 2. Query discussion history (filtered by round_number if in Replay mode)
        history = self.sim_repo.get_discussion_history(simulation_id, up_to_round=round_number)
        personas = sim.get("personas") or []
        visibility_matrix = sim.get("visibility_matrix") or {}
        topic = sim.get("topic", "")

        # 3. Compute dynamic analytics via DiscussionAnalyticsEngine
        metrics = self.engine.compute_all_metrics(
            topic=topic,
            personas=personas,
            history=history,
            visibility_matrix=visibility_matrix,
        )

        # 4. Cache full result if debate concluded and not a slice
        if is_completed and not is_replay:
            self.repo.save_analytics_cache(
                simulation_id=simulation_id,
                opinion_change=metrics["opinion_change"],
                agreement=metrics["agreement"],
                influence=metrics["influence"],
                network_graph=metrics["network_graph"],
                persuasion_signals=metrics["persuasion_signals"],
            )

        # 5. Build standardized UI payload (nodes, edges, trajectories, consensus)
        return self._format_response(metrics, history, personas, is_replay=is_replay, current_round=round_number)

    def compute_turn_analytics(self, simulation_id: str) -> Dict[str, Any]:
        """Triggered automatically after turns to update simulation metrics."""
        return self.get_simulation_analytics(simulation_id, force_compute=True)

    def _format_response(
        self,
        data: Dict[str, Any],
        history: List[Dict[str, Any]],
        personas: List[Dict[str, Any]],
        is_replay: bool = False,
        current_round: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Aligns backend metrics with the exact UI graph, chart, and trajectory schemas."""
        network = data.get("network_graph", {})
        nodes = network.get("nodes", [])

        if not nodes and personas:
            for idx, p in enumerate(personas):
                latest = next((h for h in reversed(history) if h.get("agent_name") == p["name"]), None)
                stance = 0.0
                if latest and latest.get("opinion_snapshot"):
                    stance = float(latest["opinion_snapshot"].get("current_stance_score", 0.0))

                nodes.append({
                    "id": p["name"],
                    "name": p["name"],
                    "avatarUrl": f"/avatar/{(idx % 5) + 1:02d}.png",
                    "currentStance": stance,
                    "role": p.get("background", "Panelist"),
                })

        # Build continuous, forward-filled trajectory points for time-series charts
        trajectory_map: Dict[int, Dict[str, Any]] = {}
        latest_stances: Dict[str, float] = {}

        rounds = sorted({turn.get("round_number", 1) for turn in history})
        turns_by_round: Dict[int, List[Dict[str, Any]]] = {}
        for turn in history:
            rnd = turn.get("round_number", 1)
            turns_by_round.setdefault(rnd, []).append(turn)

        for rnd in rounds:
            for turn in turns_by_round.get(rnd, []):
                agent = turn.get("agent_name")
                snapshot = turn.get("opinion_snapshot") or {}
                score = snapshot.get("current_stance_score")
                if agent and score is not None:
                    try:
                        latest_stances[agent] = round(float(score), 2)
                    except (ValueError, TypeError):
                        pass

            point: Dict[str, Any] = {"round": f"R{rnd}"}
            point.update(latest_stances)
            trajectory_map[rnd] = point

        # Aggregate unique citations
        citations = sorted({
            str(src).strip()
            for turn in history
            for src in (turn.get("retrieved_sources") or [])
            if str(src).strip()
        })

        return {
            "nodes": nodes,
            "edges": network.get("edges", []),
            "trajectory": list(trajectory_map.values()),
            "agreement": data.get("agreement", []),
            "influence": data.get("influence", {}),
            "persuasion_signals": data.get("persuasion_signals", []),
            "citations": citations,
            "is_replay": is_replay,
            "current_round": current_round,
        }
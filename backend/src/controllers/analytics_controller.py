import threading
from typing import Any, Dict, List, Optional

from src.controllers.repository.analytics_repository import AnalyticsRepository
from src.analytics.engine import DiscussionAnalyticsEngine


class AnalyticsController:
    """
    Singleton Controller managing analytics retrieval, computation, and caching.
    Decouples raw DB access from mathematical calculation engines.
    """
    _instance: Optional["AnalyticsController"] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls, *args, **kwargs) -> "AnalyticsController":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        self.repo = AnalyticsRepository()
        self.engine = DiscussionAnalyticsEngine()
        self._initialized = True

    def get_simulation_analytics(
        self,
        simulation_id: str,
        force_compute: bool = False,
    ) -> Dict[str, Any]:
        """
        Retrieves analytics for a simulation.
        Serves from cache if the debate has concluded, or computes live using the engine.
        """
        sim_meta = self.repo.get_simulation_metadata(simulation_id)
        if not sim_meta:
            raise ValueError(f"Simulation ID '{simulation_id}' not found.")

        is_completed = sim_meta.get("status") == "completed"

        # 1. CACHE HIT: Attach citations dynamically from discussion_history
        if is_completed and not force_compute:
            cached = self.repo.get_cached_analytics(simulation_id)
            if cached:
                history = self.repo.fetch_discussion_history(simulation_id)
                cached["citations"] = self.engine.extract_citations(history)
                return cached

        # 2. CACHE MISS / LIVE: Compute fresh metrics via engine
        history = self.repo.fetch_discussion_history(simulation_id)
        personas = sim_meta.get("personas") or []
        visibility_matrix = sim_meta.get("visibility_matrix") or {}
        topic = sim_meta.get("topic", "")

        analytics_result = self.engine.compute_all_metrics(
            topic=topic,
            personas=personas,
            history=history,
            visibility_matrix=visibility_matrix,
        )

        # 3. SAVE TO DB: Save cache without citations column
        self.repo.save_analytics_cache(
            simulation_id=simulation_id,
            opinion_change=analytics_result["opinion_change"],
            agreement=analytics_result["agreement"],
            influence=analytics_result["influence"],
            network_graph=analytics_result["network_graph"],
            persuasion_signals=analytics_result["persuasion_signals"],
        )

        analytics_result["simulation_id"] = simulation_id
        return analytics_result

    def compute_turn_analytics(self, simulation_id: str) -> Dict[str, Any]:
        """Hook called at the end of each discussion step to update analytics cache in real time."""
        return self.get_simulation_analytics(simulation_id, force_compute=True)

    def calculate_turn_summary(
        self,
        simulation_id: str,
        current_turns: List[Dict[str, Any]],
        current_personas: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Calculates quantitative overview metrics (turns, activity, stances)."""
        total_turns = len(current_turns)
        unique_agents = len({
            turn.get("agent_name") or turn.get("agent")
            for turn in current_turns
            if turn.get("agent_name") or turn.get("agent")
        })

        agent_counts: Dict[str, int] = {}
        for turn in current_turns:
            agent_name = turn.get("agent_name") or turn.get("agent")
            if agent_name:
                agent_counts[agent_name] = agent_counts.get(agent_name, 0) + 1

        most_active_agent: Optional[str] = None
        most_active_agent_turns: int = 0
        if agent_counts:
            most_active_agent = max(agent_counts, key=lambda k: agent_counts[k])
            most_active_agent_turns = agent_counts[most_active_agent]

        stance_scores: List[float] = []
        for turn in current_turns:
            opinion = turn.get("opinion_snapshot") or {}
            score = opinion.get("current_stance_score")
            if score is not None:
                try:
                    stance_scores.append(float(score))
                except (TypeError, ValueError):
                    pass

        avg_stance_score = (sum(stance_scores) / len(stance_scores)) if stance_scores else None

        return {
            "simulation_id": simulation_id,
            "total_turns": total_turns,
            "unique_agents": unique_agents,
            "avg_stance_score": avg_stance_score,
            "most_active_agent": most_active_agent,
            "most_active_agent_turns": most_active_agent_turns,
        }
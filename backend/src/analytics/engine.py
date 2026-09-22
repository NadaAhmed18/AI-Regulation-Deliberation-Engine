import json
from typing import Any, Dict, List, Optional

from src.analytics.agreement import compute_round_agreement
from src.analytics.findings import generate_key_findings
from src.analytics.influence import compute_topology_influence
from src.analytics.network_model import OpinionDynamicsNetwork
from src.analytics.opinion_change import compute_opinion_trajectories
from src.controllers.simulation_controller import SimulationController


class DiscussionAnalyticsEngine:
    """
    Coordinates analytics computation for a simulation.

    It reads simulation/history data from PostgreSQL, computes all analytics,
    and caches the result in the simulation_analytics table.
    """

    def __init__(self):
        self.controller = SimulationController()
        self._ensure_analytics_table()

    def _ensure_analytics_table(self) -> None:
        """Create the analytics cache table if it does not already exist."""

        with self.controller._get_cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS simulation_analytics (
                    simulation_id VARCHAR(50) PRIMARY KEY
                        REFERENCES simulations(simulation_id)
                        ON DELETE CASCADE,

                    opinion_change JSONB NOT NULL,
                    agreement JSONB NOT NULL,
                    influence JSONB NOT NULL,
                    network_graph JSONB NOT NULL,

                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cur.execute(
                """
                ALTER TABLE simulation_analytics
                ADD COLUMN IF NOT EXISTS key_findings JSONB
                """
            )

    def _fetch_history(
        self,
        simulation_id: str,
    ) -> List[Dict[str, Any]]:
        """Fetch discussion turns for one simulation in chronological order."""

        with self.controller._get_cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    simulation_id,
                    round_number,
                    agent_name,
                    role,
                    content,
                    opinion_snapshot,
                    retrieved_sources,
                    created_at
                FROM discussion_history
                WHERE simulation_id = %s
                ORDER BY round_number ASC, id ASC
                """,
                (simulation_id,),
            )

            rows = cur.fetchall()

        return [dict(row) for row in rows]

    def _save_to_cache(
        self,
        simulation_id: str,
        opinion_change: Dict[str, Any],
        agreement: List[Dict[str, Any]],
        influence: Dict[str, Any],
        network_graph: Dict[str, Any],
        key_findings: List[Dict[str, Any]],
    ) -> None:
        """Insert or update computed analytics."""

        with self.controller._get_cursor() as cur:
            cur.execute(
    """
    INSERT INTO simulation_analytics (
        simulation_id,
        opinion_change,
        agreement,
        influence,
        network_graph,
        key_findings,
        updated_at
    )
    VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)

    ON CONFLICT (simulation_id)
    DO UPDATE SET
        opinion_change = EXCLUDED.opinion_change,
        agreement = EXCLUDED.agreement,
        influence = EXCLUDED.influence,
        network_graph = EXCLUDED.network_graph,
        key_findings = EXCLUDED.key_findings,
        updated_at = CURRENT_TIMESTAMP
    """,
    (
        simulation_id,
        json.dumps(opinion_change),
        json.dumps(agreement),
        json.dumps(influence),
        json.dumps(network_graph),
        json.dumps(key_findings),
    ),
)

    def get_cached_analytics(
        self,
        simulation_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Return cached analytics if available."""

        with self.controller._get_cursor() as cur:
            cur.execute(
                """
                SELECT
                    simulation_id,
                    opinion_change,
                    agreement,
                    influence,
                    network_graph,
                    key_findings,
                    updated_at
                FROM simulation_analytics
                WHERE simulation_id = %s
                """,
                (simulation_id,),
            )

            row = cur.fetchone()

        return dict(row) if row else None

    def analyze(
        self,
        simulation_id: str,
        force_compute: bool = False,
    ) -> Dict[str, Any]:
        """
        Compute all analytics for a simulation.

        Completed simulations may use their cached analytics unless
        force_compute=True.
        """

        simulation = self.controller.get_simulation_by_id(simulation_id)

        if not simulation:
            raise ValueError(
                f"Simulation ID '{simulation_id}' not found."
            )

        if (
            simulation.get("status") == "completed"
            and not force_compute
        ):
            cached = self.get_cached_analytics(simulation_id)

            if cached:
                return cached

        personas = list(simulation.get("personas") or [])
        visibility_matrix = simulation.get("visibility_matrix") or {}

        history = self._fetch_history(simulation_id)

        opinion_change = compute_opinion_trajectories(
            history,
            personas,
        )

        agreement = compute_round_agreement(history)

        influence = compute_topology_influence(
            history,
            personas,
            visibility_matrix,
        )

        network = OpinionDynamicsNetwork(
            personas=personas,
            opinion_trajectories=opinion_change,
            influence_data=influence,
        )

        network_graph = network.export_graph_data()
        key_findings = generate_key_findings(
             trajectories=opinion_change,
             influence_result=influence,
)
        self._save_to_cache(
            simulation_id=simulation_id,
            opinion_change=opinion_change,
            agreement=agreement,
            influence=influence,
            network_graph=network_graph,
            key_findings=key_findings,
        )

        return {
            "simulation_id": simulation_id,
            "topic": simulation.get("topic"),
            "opinion_change": opinion_change,
            "agreement": agreement,
            "influence": influence,
            "network_graph": network_graph,
            "key_findings": key_findings,
        }
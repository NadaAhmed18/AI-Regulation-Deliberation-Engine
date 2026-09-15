import json
from typing import Any, Dict, Optional
from src.controllers.repository.base_repository import BaseRepository


class AnalyticsRepository(BaseRepository):
    """Data access layer for cached opinion metrics and network graph dynamics."""

    def get_cached_analytics(self, simulation_id: str) -> Optional[Dict[str, Any]]:
        with self.get_cursor() as cur:
            cur.execute(
                """
                SELECT simulation_id, opinion_change, agreement, influence, network_graph, persuasion_signals, updated_at
                FROM simulation_analytics
                WHERE simulation_id = %s
                """,
                (simulation_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def save_analytics_cache(
        self,
        simulation_id: str,
        opinion_change: Dict[str, Any],
        agreement: list,
        influence: Dict[str, Any],
        network_graph: Dict[str, Any],
        persuasion_signals: list,
    ) -> None:
        with self.get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO simulation_analytics (
                    simulation_id, opinion_change, agreement, influence, network_graph, persuasion_signals, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (simulation_id)
                DO UPDATE SET
                    opinion_change = EXCLUDED.opinion_change,
                    agreement = EXCLUDED.agreement,
                    influence = EXCLUDED.influence,
                    network_graph = EXCLUDED.network_graph,
                    persuasion_signals = EXCLUDED.persuasion_signals,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    simulation_id,
                    json.dumps(opinion_change),
                    json.dumps(agreement),
                    json.dumps(influence),
                    json.dumps(network_graph),
                    json.dumps(persuasion_signals),
                ),
            )
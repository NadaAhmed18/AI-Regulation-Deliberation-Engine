import json
import threading
from typing import Any, Dict, List, Optional
from src.controllers.repository.base_repository import BaseRepository


class SimulationRepository(BaseRepository):
    """Data access layer for Simulation life-cycles and Discussion history."""
    _instance: Optional["SimulationRepository"] = None
    _inst_lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "SimulationRepository":
        if cls._instance is None:
            with cls._inst_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def create_simulation(
        self,
        sim_id: str,
        topic: str,
        memory_strategy: dict,
        personas: list,
        visibility_matrix: Optional[Dict[str, List[str]]] = None,
    ) -> None:
        with self.get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO simulations (simulation_id, topic, memory_strategy, personas, visibility_matrix, status)
                VALUES (%s, %s, %s, %s, %s, 'active')
                """,
                (
                    sim_id,
                    topic,
                    json.dumps(memory_strategy),
                    json.dumps(personas),
                    json.dumps(visibility_matrix) if visibility_matrix is not None else None,
                ),
            )

    def save_discussion_turn(
        self,
        sim_id: str,
        round_num: int,
        agent_name: str,
        role: str,
        content: str,
        opinion: Optional[dict] = None,
        sources: Optional[list] = None,
    ) -> None:
        with self.get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO discussion_history (
                    simulation_id, round_number, agent_name, role, content, opinion_snapshot, retrieved_sources
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    sim_id,
                    round_num,
                    agent_name,
                    role,
                    content,
                    json.dumps(opinion) if opinion is not None else None,
                    json.dumps(sources or []),
                ),
            )

    def get_simulation_by_id(self, sim_id: str) -> Optional[Dict[str, Any]]:
        with self.get_cursor() as cur:
            cur.execute(
                """
                SELECT simulation_id, topic, status, memory_strategy, personas, visibility_matrix, created_at
                FROM simulations
                WHERE simulation_id = %s
                """,
                (sim_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def get_all_simulations(self, search_pattern: Optional[str] = None) -> List[Dict[str, Any]]:
        query = """
            SELECT 
                s.simulation_id, s.topic, s.status, s.memory_strategy, 
                s.personas, s.created_at, COUNT(h.id) AS turn_count
            FROM simulations s
            LEFT JOIN discussion_history h ON h.simulation_id = s.simulation_id
            WHERE (%s IS NULL OR s.topic ~* %s)
            GROUP BY s.simulation_id
            ORDER BY s.created_at DESC
        """
        with self.get_cursor() as cur:
            cur.execute(query, (search_pattern, search_pattern))
            return [dict(row) for row in cur.fetchall()]

    def get_current_discussion_history(
        self, 
        sim_id: str, 
        up_to_round: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetches chronological debate turns, optionally sliced up to a specific round for replay."""
        query = """
            SELECT id, round_number, agent_name, role, content, opinion_snapshot, retrieved_sources, created_at
            FROM discussion_history
            WHERE simulation_id = %s
        """
        params: list = [sim_id]

        if up_to_round is not None:
            query += " AND round_number <= %s"
            params.append(up_to_round)

        query += " ORDER BY round_number ASC, id ASC"

        with self.get_cursor() as cur:
            cur.execute(query, tuple(params))
            return [dict(row) for row in cur.fetchall()]

    # Alias for backward compatibility
    get_discussion_history = get_current_discussion_history

    def get_last_stance_score(self, sim_id: str, agent_name: str) -> Optional[float]:
        with self.get_cursor() as cur:
            cur.execute(
                """
                SELECT opinion_snapshot->>'current_stance_score' AS score
                FROM discussion_history
                WHERE simulation_id = %s AND agent_name = %s AND opinion_snapshot IS NOT NULL
                ORDER BY id DESC LIMIT 1
                """,
                (sim_id, agent_name),
            )
            row: Any = cur.fetchone()
            if row is not None and row.get("score") is not None:
                return float(row["score"])
            return None

    def get_last_round_number(self, sim_id: str) -> int:
        with self.get_cursor() as cur:
            cur.execute(
                "SELECT COALESCE(MAX(round_number), 0) AS last_round FROM discussion_history WHERE simulation_id = %s",
                (sim_id,),
            )
            row: Any = cur.fetchone()
            if row is not None and row.get("last_round") is not None:
                return int(row["last_round"])
            return 0

    def delete_simulation(self, sim_id: str) -> bool:
        with self.get_cursor() as cur:
            cur.execute("DELETE FROM simulations WHERE simulation_id = %s", (sim_id,))
            return cur.rowcount > 0
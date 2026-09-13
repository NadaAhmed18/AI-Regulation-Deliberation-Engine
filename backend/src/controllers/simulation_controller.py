import json
import threading
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor

from src.clients.postgres import PostgresClient
from src.config import DATABASE_URL


class SimulationController:
    """
    Singleton Controller managing persistence and querying for simulations
    and discussion history.

    Maintains exactly ONE persistent PostgreSQL connection across the application lifecycle.
    """

    _instance: Optional["SimulationController"] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls, *args, **kwargs) -> "SimulationController":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        # Ensure database and base tables exist via PostgresClient
        PostgresClient()

        self._conn: Optional[psycopg2.extensions.connection] = None
        self._connect()
        self._initialized = True

    def _connect(self) -> None:
        """Initializes or resets the single persistent connection."""
        if self._conn is not None and not self._conn.closed:
            return
        self._conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

    @contextmanager
    def _get_cursor(self):
        """
        Thread-safe context manager providing a cursor over the single connection.
        Automatically commits transactions or rolls back on exceptions.
        """
        with self._lock:
            # Auto-reconnect if the connection was dropped
            if self._conn is None or self._conn.closed:
                self._connect()

            assert self._conn is not None
            cursor = self._conn.cursor()
            try:
                yield cursor
                self._conn.commit()
            except Exception:
                if self._conn and not self._conn.closed:
                    self._conn.rollback()
                raise
            finally:
                cursor.close()

    # =========================================================================
    # SIMULATION PERSISTENCE METHODS
    # =========================================================================

    def create_simulation(
        self,
        sim_id: str,
        topic: str,
        memory_strategy: dict,
        personas: list,
        visibility_matrix: Optional[dict] = None,
    ) -> None:
        """Saves a new session when the user clicks 'Generate Simulation'."""
        with self._get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO simulations (
                    simulation_id,
                    topic,
                    memory_strategy,
                    personas,
                    visibility_matrix
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    sim_id,
                    topic,
                    json.dumps(memory_strategy),
                    json.dumps(personas),
                    json.dumps(visibility_matrix or {}),
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
        """Saves an individual agent's turn to the history."""
        with self._get_cursor() as cur:
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
                    json.dumps(opinion),
                    json.dumps(sources or []),
                ),
            )

    def get_all_simulations(self) -> List[Dict[str, Any]]:
        """
        Returns every simulation with its topic, status, personas, memory
        strategy and how many discussion turns it has logged so far.
        Ordered newest-first.
        """
        with self._get_cursor() as cur:
            cur.execute(
                """
                SELECT
                    s.simulation_id,
                    s.topic,
                    s.status,
                    s.memory_strategy,
                    s.personas,
                    s.created_at,
                    COUNT(h.id) AS turn_count
                FROM simulations s
                LEFT JOIN discussion_history h
                    ON h.simulation_id = s.simulation_id
                GROUP BY s.simulation_id
                ORDER BY s.created_at DESC
                """
            )
            rows = cur.fetchall()
            return [dict(row) for row in rows]

    def search_simulations_by_regex(self, pattern: str) -> List[Dict[str, Any]]:
        """
        Filters simulations whose topic matches the given POSIX regex
        (case-insensitive), using Postgres' native `~*` operator.
        Raises the underlying psycopg2 error if the pattern is invalid.
        """
        with self._get_cursor() as cur:
            cur.execute(
                """
                SELECT
                    s.simulation_id,
                    s.topic,
                    s.status,
                    s.memory_strategy,
                    s.personas,
                    s.created_at,
                    COUNT(h.id) AS turn_count
                FROM simulations s
                LEFT JOIN discussion_history h
                    ON h.simulation_id = s.simulation_id
                WHERE s.topic ~* %s
                GROUP BY s.simulation_id
                ORDER BY s.created_at DESC
                """,
                (pattern,),
            )
            rows = cur.fetchall()
            return [dict(row) for row in rows]

    def get_simulation_by_id(self, sim_id: str) -> Optional[Dict[str, Any]]:
        """Returns a single simulation's metadata, or None if it doesn't exist."""
        with self._get_cursor() as cur:
            cur.execute(
                """
                SELECT
    simulation_id,
    topic,
    status,
    memory_strategy,
    personas,
    visibility_matrix,
    created_at
FROM simulations
WHERE simulation_id = %s
                """,
                (sim_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def delete_simulation(self, sim_id: str) -> bool:
        """
        Deletes a simulation by id. discussion_history rows are removed
        automatically because of the ON DELETE CASCADE foreign key.
        Returns True if a row was deleted, False if the id didn't exist.
        """
        with self._get_cursor() as cur:
            cur.execute(
                """
                DELETE FROM simulations
                WHERE simulation_id = %s
                """,
                (sim_id,),
            )
            return cur.rowcount > 0
        
    def get_last_stance_score(self, sim_id: str, agent_name: str) -> Optional[float]:
        """
        Fetch this agent's most recent `current_stance_score` for this
        simulation, or `None` if the agent has no prior scored turn yet.

        `None` (not `0.0`) on a miss is deliberate: `0.0` is a genuine
        neutral score, while "no row found" means no prior score exists
        at all. Callers (e.g. `node_grade_opinion` in
        `discussion_graph.py`) should pass this value straight through as
        `previous_score` to `DebertaStanceGrader.evaluate_stance()` /
        `OpinionGrader.evaluate_stance()`, both of which treat `None` as
        "first turn, no shift to compute" rather than "shifted from 0.0."
        """
        with self._get_cursor() as cur:
            cur.execute("""
                SELECT opinion_snapshot->>'current_stance_score' AS score
                FROM discussion_history
                WHERE simulation_id = %s AND agent_name = %s AND opinion_snapshot IS NOT NULL
                ORDER BY id DESC
                LIMIT 1
            """, (sim_id, agent_name))

            row: Any = cur.fetchone()

            if row is None or row["score"] is None:
                return None

            return float(row["score"])
        
    def get_last_round_number(self, sim_id: str) -> int:
        """Returns the highest round number recorded so far for this simulation, or 0."""
        with self._get_cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(MAX(round_number), 0) AS last_round 
                FROM discussion_history 
                WHERE simulation_id = %s
                """,
                (sim_id,),
            )
            row: Any = cur.fetchone()
            if row and row["last_round"] is not None:
                return int(row["last_round"])
            return 0

    def close(self) -> None:
        """Explicitly closes the shared database connection."""
        with self._lock:
            if self._conn is not None and not self._conn.closed:
                self._conn.close()
                self._conn = None


# Smoke test to verify singleton behavior & single connection
if __name__ == "__main__":
    # backend: python -m src.controllers.simulation_controller
    c1 = SimulationController()
    c2 = SimulationController()

    print("--- Testing Singleton & Single Connection ---")
    print(f"c1 is c2: {c1 is c2}")
    print(f"Connection shared: {c1._conn is c2._conn}")
    print(f"Total simulations in DB: {len(c1.get_all_simulations())}")
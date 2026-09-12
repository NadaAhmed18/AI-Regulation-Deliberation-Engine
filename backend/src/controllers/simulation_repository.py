import json
import threading
from contextlib import contextmanager
from typing import Any, Dict, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor

from src.clients.postgres import PostgresClient
from src.config import DATABASE_URL


class SimulationRepository:
    _instance: Optional["SimulationRepository"] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls, *args, **kwargs) -> "SimulationRepository":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        # Ensure base tables exist via PostgresClient
        PostgresClient()

        self._conn: Optional[psycopg2.extensions.connection] = None
        self._connect()
        self._initialized = True

    def _connect(self) -> None:
        """Initializes or resets the persistent connection."""
        if self._conn is not None and not self._conn.closed:
            return
        self._conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

    @contextmanager
    def _get_cursor(self):
        """Thread-safe context manager providing a cursor over the shared connection."""
        with self._lock:
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

    def create_simulation(
        self,
        sim_id: str,
        topic: str,
        memory_strategy: dict,
        personas: list,
        visibility_matrix: Optional[Dict[str, List[str]]] = None,
    ) -> None:
        with self._get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO simulations (simulation_id, topic, memory_strategy, personas, visibility_matrix)
                VALUES (%s, %s, %s, %s, %s)
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
        with self._get_cursor() as cur:
            cur.execute(
                """
                SELECT opinion_snapshot->>'current_stance_score' AS score
                FROM discussion_history
                WHERE simulation_id = %s AND agent_name = %s AND opinion_snapshot IS NOT NULL
                ORDER BY id DESC
                LIMIT 1
                """,
                (sim_id, agent_name),
            )
            row: Any = cur.fetchone()
            if row is None or row["score"] is None:
                return None
            return float(row["score"])

    def get_last_round_number(self, sim_id: str) -> int:
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

    def get_current_discussion_history(self, sim_id: str) -> List[Dict[str, Any]]:
        with self._get_cursor() as cur:
            cur.execute(
                """
                SELECT id, round_number, agent_name, role, content, opinion_snapshot, retrieved_sources, created_at
                FROM discussion_history
                WHERE simulation_id = %s
                ORDER BY round_number ASC, id ASC
                """,
                (sim_id,),
            )
            rows = cur.fetchall()
            return [dict(row) for row in rows]

    def close(self) -> None:
        with self._lock:
            if self._conn is not None and not self._conn.closed:
                self._conn.close()
                self._conn = None
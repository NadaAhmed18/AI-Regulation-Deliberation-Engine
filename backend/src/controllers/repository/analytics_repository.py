import json
import threading
from contextlib import contextmanager
from typing import Any, Dict, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor

from src.clients.postgres import PostgresClient
from src.config import DATABASE_URL


class AnalyticsRepository:
    """
    Thread-safe repository for all analytics data operations.
    Handles reading raw discussion history, metadata, and caching/retrieving
    computed simulation analytics without 'citations' in the cache table.
    """
    _instance: Optional["AnalyticsRepository"] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls, *args, **kwargs) -> "AnalyticsRepository":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        # Ensure base tables and schema migrations exist
        PostgresClient()

        self._conn: Optional[psycopg2.extensions.connection] = None
        self._connect()
        self._initialized = True

    def _connect(self) -> None:
        """Initializes or restores the persistent connection."""
        if self._conn is not None and not self._conn.closed:
            return
        self._conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

    @contextmanager
    def _get_cursor(self):
        """Thread-safe context manager providing a cursor with transactional safety."""
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

    def get_simulation_metadata(self, simulation_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves simulation configuration, personas, visibility matrix, and status."""
        with self._get_cursor() as cur:
            cur.execute(
                """
                SELECT simulation_id, topic, personas, visibility_matrix, status
                FROM simulations
                WHERE simulation_id = %s
                """,
                (simulation_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def fetch_discussion_history(self, simulation_id: str) -> List[Dict[str, Any]]:
        """Fetches ordered discussion history with opinion snapshots and cited sources."""
        with self._get_cursor() as cur:
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

    def get_cached_analytics(self, simulation_id: str) -> Optional[Dict[str, Any]]:
        """Fetches pre-calculated analytics record if available."""
        with self._get_cursor() as cur:
            cur.execute(
                """
                SELECT
                    simulation_id,
                    opinion_change,
                    agreement,
                    influence,
                    network_graph,
                    persuasion_signals,
                    updated_at
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
        agreement: List[Dict[str, Any]],
        influence: Dict[str, Any],
        network_graph: Dict[str, Any],
        persuasion_signals: List[Dict[str, Any]],
    ) -> None:
        """Upserts computed analytics results into the simulation_analytics table."""
        with self._get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO simulation_analytics (
                    simulation_id,
                    opinion_change,
                    agreement,
                    influence,
                    network_graph,
                    persuasion_signals,
                    updated_at
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

    def close(self) -> None:
        """Closes the persistent connection cleanly."""
        with self._lock:
            if self._conn is not None and not self._conn.closed:
                self._conn.close()
                self._conn = None
import threading
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor

from src.clients.neo4j import Neo4jClient
from src.clients.postgres import PostgresClient
from src.config import DATABASE_URL


class BaseRepository:
    """
    Base repository managing persistent PostgreSQL and Neo4j connections.
    Subclasses manage their own singleton life-cycle cleanly.
    """
    _conn: Optional[psycopg2.extensions.connection] = None
    _neo4j: Optional[Neo4jClient] = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self):
        PostgresClient()
        self._connect()

    def _connect(self) -> None:
        """Initializes PostgreSQL and Neo4j clients."""
        with self._lock:
            if self._conn is None or self._conn.closed:
                self._conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
            if self._neo4j is None:
                self._neo4j = Neo4jClient()

    @contextmanager
    def get_cursor(self) -> Generator[Any, None, None]:
        """Context manager providing an isolated, auto-committing cursor."""
        with self._lock:
            if self._conn is None or self._conn.closed:
                self._conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

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

    def run_neo4j_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if self._neo4j is None:
            self._neo4j = Neo4jClient()
        return self._neo4j.execute_query(query, parameters or {})

    def close(self) -> None:
        with self._lock:
            if self._conn and not self._conn.closed:
                self._conn.close()
                self._conn = None
            if self._neo4j:
                self._neo4j.close()
                self._neo4j = None
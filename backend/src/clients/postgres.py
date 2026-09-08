import os
import json
from typing import List, Optional,Dict,Any
import psycopg2
from psycopg2.extras import RealDictCursor
from src.config import DATABASE_URL

class PostgresClient:
    def __init__(self):
        self._init_db()

    def get_connection(self):
        return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

    def _init_db(self):
        """Creates the relational tables for Session and History management."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Table 1: Stores the Configuration and generated Personas
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS simulations (
                        simulation_id VARCHAR(50) PRIMARY KEY,
                        topic TEXT NOT NULL,
                        memory_strategy JSONB NOT NULL,
                        personas JSONB NOT NULL,
                        status VARCHAR(20) DEFAULT 'running',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # Table 2: Stores the actual chat messages and Analytics
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS discussion_history (
                        id SERIAL PRIMARY KEY,
                        simulation_id VARCHAR(50) REFERENCES simulations(simulation_id) ON DELETE CASCADE,
                        round_number INTEGER,
                        agent_name VARCHAR(100),
                        role VARCHAR(20),
                        content TEXT,
                        opinion_snapshot JSONB,
                        retrieved_sources JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            conn.commit()

        

    def create_simulation(self, sim_id: str, topic: str, memory_strategy: dict, personas: list):
        """Saves a new session when the user clicks 'Generate Simulation'."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO simulations (simulation_id, topic, memory_strategy, personas)
                    VALUES (%s, %s, %s, %s)
                """, (sim_id, topic, json.dumps(memory_strategy), json.dumps(personas)))
            conn.commit()

    def save_discussion_turn(self, sim_id: str, round_num: int, agent_name: str, role: str, content: str, opinion: Optional[dict] = None, sources: Optional[list] = None):
        """Saves an individual agent's turn to the history."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO discussion_history (simulation_id, round_number, agent_name, role, content, opinion_snapshot, retrieved_sources)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (sim_id, round_num, agent_name, role, content, json.dumps(opinion), json.dumps(sources or [])))
            conn.commit()

    def get_all_simulations(self) -> List[Dict[str, Any]]:
        """
        Returns every simulation with its topic, status, personas, memory
        strategy and how many discussion turns it has logged so far.
        Ordered newest-first.
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
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
                """)
                rows = cur.fetchall()
                return [dict(row) for row in rows]
 
    def search_simulations_by_regex(self, pattern: str) -> List[Dict[str, Any]]:
        """
        Filters simulations whose topic matches the given POSIX regex
        (case-insensitive), using Postgres' native `~*` operator.
        Raises the underlying psycopg2 error if the pattern is invalid.
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
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
                """, (pattern,))
                rows = cur.fetchall()
                return [dict(row) for row in rows]
 
    def get_simulation_by_id(self, sim_id: str) -> Optional[Dict[str, Any]]:
        """Returns a single simulation's metadata, or None if it doesn't exist."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT simulation_id, topic, status, memory_strategy, personas, created_at
                    FROM simulations
                    WHERE simulation_id = %s
                """, (sim_id,))
                row = cur.fetchone()
                return dict(row) if row else None
 
    def delete_simulation(self, sim_id: str) -> bool:
        """
        Deletes a simulation by id. discussion_history rows are removed
        automatically because of the ON DELETE CASCADE foreign key.
        Returns True if a row was deleted, False if the id didn't exist.
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM simulations
                    WHERE simulation_id = %s
                """, (sim_id,))
                deleted = cur.rowcount > 0
            conn.commit()
            return deleted

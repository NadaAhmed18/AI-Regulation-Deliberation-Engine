import os
import json
from typing import Optional
from urllib.parse import urlparse, urlunparse
import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
from src.config import DATABASE_URL

class PostgresClient:
    def __init__(self):
        self._ensure_database_exists()
        self._init_db()

    def _ensure_database_exists(self):
        """Connects to the maintenance DB and auto-creates the target DB if missing."""
        parsed = urlparse(DATABASE_URL)
        target_db = parsed.path.lstrip("/")
        if not target_db:
            return

        # Maintenance databases that always exist in PostgreSQL
        maintenance_dbs = ["postgres", "template1"]
        
        for admin_db in maintenance_dbs:
            admin_url = urlunparse(parsed._replace(path=f"/{admin_db}"))
            try:
                admin_conn = psycopg2.connect(admin_url)
                admin_conn.autocommit = True  # Required for CREATE DATABASE
                with admin_conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target_db,))
                    exists = cur.fetchone()
                    if not exists:
                        print(f"[*] Database '{target_db}' does not exist. Creating it automatically...")
                        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target_db)))
                        print(f"[+] Database '{target_db}' created successfully.")
                admin_conn.close()
                return
            except psycopg2.OperationalError:
                continue
            except Exception as e:
                print(f"[!] Warning during auto database creation: {e}")
                break

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

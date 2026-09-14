from urllib.parse import urlparse, urlunparse
import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
from src.config import DATABASE_URL


class PostgresClient:
    """Manages raw PostgreSQL connectivity, maintenance database checks, and base DDL schema."""

    def __init__(self):
        self._ensure_database_exists()
        self._init_db()

    def _ensure_database_exists(self) -> None:
        """Connects to the maintenance DB and auto-creates the target DB if missing."""
        parsed = urlparse(DATABASE_URL)
        target_db = parsed.path.lstrip("/")
        if not target_db:
            return

        maintenance_dbs = ["postgres", "template1"]

        for admin_db in maintenance_dbs:
            admin_url = urlunparse(parsed._replace(path=f"/{admin_db}"))
            try:
                admin_conn = psycopg2.connect(admin_url)
                admin_conn.autocommit = True
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
        """Returns a new connection with dictionary-like cursor capability."""
        return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

    def _init_db(self) -> None:
        """Creates the relational tables for Sessions, History, and Analytics Cache."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Simulations Table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS simulations (
                        simulation_id VARCHAR(50) PRIMARY KEY,
                        topic TEXT NOT NULL,
                        memory_strategy JSONB NOT NULL,
                        personas JSONB NOT NULL,
                        visibility_matrix JSONB,
                        status VARCHAR(20) DEFAULT 'running',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                # 2. Discussion History Table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS discussion_history (
                        id SERIAL PRIMARY KEY,
                        simulation_id VARCHAR(50) REFERENCES simulations(simulation_id) ON DELETE CASCADE,
                        round_number INTEGER NOT NULL,
                        agent_name VARCHAR(100) NOT NULL,
                        role VARCHAR(20) NOT NULL,
                        content TEXT NOT NULL,
                        opinion_snapshot JSONB,
                        retrieved_sources JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                # 3. Simulation Analytics Cache Table (Centralized DDL)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS simulation_analytics (
                        simulation_id VARCHAR(50) PRIMARY KEY 
                            REFERENCES simulations(simulation_id) ON DELETE CASCADE,
                        opinion_change JSONB NOT NULL,
                        agreement JSONB NOT NULL,
                        influence JSONB NOT NULL,
                        network_graph JSONB NOT NULL,
                        persuasion_signals JSONB NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
            conn.commit()
import json
import threading
from contextlib import contextmanager
from typing import Any, Dict, List, Optional
import uuid

import psycopg2
from psycopg2.extras import RealDictCursor

from src.routes.schemas import simulation
from src.clients.postgres import PostgresClient
from src.config import DATABASE_URL
from src.utils.prompt_builder import render_prompt
from src.clients.llm_client import LLMClient
from src.orchestration.discussion_graph import DiscussionEngine

class SimulationController:


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
        self.llm=LLMClient()  # Initialize the LLM client once for the controller
        self.engine = DiscussionEngine()
    

        

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


    def create_simulation(
        self, sim_id: str, topic: str, memory_strategy: dict, personas: list,
        visibility_matrix: Optional[Dict[str, List[str]]] = None
    ) -> None:
        """Saves a new session when the user clicks 'Generate Simulation'."""
        with self._get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO simulations (simulation_id, topic, memory_strategy, personas, visibility_matrix)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (sim_id, topic, json.dumps(memory_strategy), json.dumps(personas), json.dumps(visibility_matrix) if visibility_matrix is not None else None),
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

    
    def generate_personas(
        self, topic: str, num_agents: int,
        custom_prompt: Optional[str] = None, default_memory_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:

        if not topic or not topic.strip():
            raise ValueError("Topic cannot be empty.")

        if not 2 <= num_agents <= 6:
            raise ValueError("num_agents must be between 2 and 6.")

        memory_type = default_memory_type or "sliding_window"

        personas_prompt = render_prompt(
            "setup_personas",
            topic=topic,
            num_agents=num_agents,
            custom_instructions=custom_prompt or "None",
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert Simulation Designer and Sociologist. "
                    "Follow the user's requested output format exactly."
                ),
            },
            {
                "role": "user",
                "content": personas_prompt,
            },
        ]

        try:
            response = self.llm.generate_response(
                messages=messages,
                response_format="json_object",
            )

            # Persona generation must return normal text, not a tool call.
            if response.get("type") != "text":
                raise RuntimeError(
                    "LLM returned a tool call instead of persona data."
                )

            content = response.get("content", "").strip()

            if not content:
                raise RuntimeError(
                    "LLM returned an empty response while generating personas."
                )

            data = json.loads(content)
            personas = data.get("personas")

            if not isinstance(personas, list):
                raise ValueError(
                    "Invalid persona response: 'personas' must be a list."
                )

            # Make sure the LLM respected the requested number.
            if len(personas) != num_agents:
                raise ValueError(
                    f"Expected {num_agents} personas, "
                    f"but received {len(personas)}."
                )

            validated_personas: List[Dict[str, Any]] = []

            for index, persona in enumerate(personas, start=1):

                if not isinstance(persona, dict):
                    raise ValueError(
                        f"Persona #{index} must be a JSON object."
                    )

                required_fields = [
                    "name",
                    "background",
                    "stance",
                    "tone",
                    "avatarSeed"
                ]

                missing_fields = [
                    field
                    for field in required_fields
                    if not persona.get(field)
                ]

                if missing_fields:
                    raise ValueError(
                        f"Persona #{index} is missing required fields: "
                        f"{', '.join(missing_fields)}"
                    )

                persona["memory_config"] = {
                    "type": memory_type,
                    "window_size": 4,
                }

                validated_personas.append(persona)

            return validated_personas

        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Failed to parse LLM persona response as JSON: {exc}"
            ) from exc

        except Exception as exc:
            raise RuntimeError(
                f"Failed to generate personas: {exc}"
            ) from exc

    def start_simulation(
        self, topic: str, personas: List[Dict[str, Any]],
        memory_strategy: Dict[str, Any], visibility_matrix: Optional[Dict[str, List[str]]] = None,
    ) -> str:

        if not topic or not topic.strip():
            raise ValueError("Topic cannot be empty.")

        if not personas:
            raise ValueError("At least one persona is required.")

        if not memory_strategy:
            memory_strategy = {
                "type": "sliding_window",
                "window_size": 4,
            }

        sim_id = f"sim_{uuid.uuid4().hex[:12]}"

        self.create_simulation(
            sim_id=sim_id,
            topic=topic,
            memory_strategy=memory_strategy,
            personas=personas,
            visibility_matrix=visibility_matrix,
        )

        return sim_id

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

    def next_turn(self, simulation_id: str, intervention: Optional[str] = None) -> Dict[str, Any]:

        simulation = self.get_simulation_by_id(simulation_id)

        if not simulation:
            raise ValueError(f"Simulation '{simulation_id}' not found.")

        personas = simulation.get("personas") or []

        if not personas:
            raise ValueError(f"Simulation '{simulation_id}' has no personas.")

        discussion_history = self.get_current_discussion_history(simulation_id)

        memory_strategy = simulation.get("memory_strategy") or {}
        visibility_matrix = simulation.get("visibility_matrix") or {}

        turn_number = len(discussion_history)
        agent_index = turn_number % len(personas)
        current_persona = personas[agent_index]
        round_number = (turn_number // len(personas)) + 1

        return {
            "simulation_id": simulation_id,
            "round_number": round_number,
            "turn_number": turn_number + 1,
            "agent": current_persona,
            "memory_strategy": memory_strategy,
            "visibility_matrix": visibility_matrix,
            "discussion_history": discussion_history,
            "intervention": intervention,
            "status": "ready_for_generation",
        }

    def simulation_analytics(
        self, simulation_id: str,
        current_turns: List[Dict[str, Any]], current_personas: List[Dict[str, Any]],
    ) -> Dict[str, Any]:

        total_turns = len(current_turns)

        unique_agents = len({
            turn.get("agent_name") or turn.get("agent")
            for turn in current_turns
            if turn.get("agent_name") or turn.get("agent")
        })

        agent_counts: Dict[str, int] = {}

        for turn in current_turns:
            agent_name = turn.get("agent_name") or turn.get("agent")

            if agent_name:
                agent_counts[agent_name] = agent_counts.get(agent_name, 0) + 1

        most_active_agent = None
        most_active_agent_turns = 0

        if agent_counts:
            most_active_agent = max(agent_counts, key=agent_counts.get)
            most_active_agent_turns = agent_counts[most_active_agent]

        stance_scores = []

        for turn in current_turns:
            opinion = turn.get("opinion_snapshot") or {}
            score = opinion.get("current_stance_score")

            if score is not None:
                try:
                    stance_scores.append(float(score))
                except (TypeError, ValueError):
                    pass

        avg_stance_score = (
            sum(stance_scores) / len(stance_scores)
            if stance_scores
            else None
        )

        return {
            "simulation_id": simulation_id,
            "total_turns": total_turns,
            "unique_agents": unique_agents,
            "avg_stance_score": avg_stance_score,
            "most_active_agent": most_active_agent,
            "most_active_agent_turns": most_active_agent_turns,
        }

    def continue_simulation( self, simulation_id: str, intervention: Optional[str] = None, steps: int = 1,) -> Dict[str, Any]:
  
        if steps < 1:
            raise ValueError("Steps must be at least 1.")

        simulation = self.get_simulation_by_id(simulation_id)

        if not simulation:
            raise ValueError(f"Simulation '{simulation_id}' not found.")

        visibility_matrix = simulation.get("visibility_matrix") or {}

        final_state = self.engine.step_discussion(
            sim_id=simulation_id,
            steps=steps,
            visibility_matrix=visibility_matrix,
            intervention=intervention,
        )

        return {
            "simulation_id": simulation_id,
            "steps": steps,
            "current_round": final_state.get("current_round"),
            "current_speaker": final_state.get("current_speaker"),
            "last_message": final_state.get("last_message"),
            "last_sources": final_state.get("last_sources"),
            "last_opinion": final_state.get("last_opinion"),
        }


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
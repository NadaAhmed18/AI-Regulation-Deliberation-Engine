import json
import threading
from typing import Any, Dict, List, Optional
import uuid
import re

from src.clients.llm_client import LLMClient
from src.controllers.simulation_repository import SimulationRepository
from src.orchestration.discussion_graph import DiscussionEngine
from src.utils.prompt_builder import render_prompt


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

        self.repo = SimulationRepository()
        self.llm = LLMClient()
        self.engine = DiscussionEngine()
        self._initialized = True

    # -------------------------------------------------------------------------
    # Delegated Repository Methods (Zero-breaking changes for callers)
    # -------------------------------------------------------------------------
    def create_simulation(
        self,
        sim_id: str,
        topic: str,
        memory_strategy: dict,
        personas: list,
        visibility_matrix: Optional[Dict[str, List[str]]] = None,
    ) -> None:
        self.repo.create_simulation(sim_id, topic, memory_strategy, personas, visibility_matrix)

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
        self.repo.save_discussion_turn(sim_id, round_num, agent_name, role, content, opinion, sources)

    def get_all_simulations(self) -> List[Dict[str, Any]]:
        return self.repo.get_all_simulations()

    def search_simulations_by_regex(self, pattern: str) -> List[Dict[str, Any]]:
        return self.repo.search_simulations_by_regex(pattern)

    def get_simulation_by_id(self, sim_id: str) -> Optional[Dict[str, Any]]:
        return self.repo.get_simulation_by_id(sim_id)

    def delete_simulation(self, sim_id: str) -> bool:
        return self.repo.delete_simulation(sim_id)

    def get_last_stance_score(self, sim_id: str, agent_name: str) -> Optional[float]:
        return self.repo.get_last_stance_score(sim_id, agent_name)

    def get_last_round_number(self, sim_id: str) -> int:
        return self.repo.get_last_round_number(sim_id)

    def get_current_discussion_history(self, sim_id: str) -> List[Dict[str, Any]]:
        return self.repo.get_current_discussion_history(sim_id)

    def close(self) -> None:
        self.repo.close()

    # -------------------------------------------------------------------------
    # Business & Orchestration Logic
    # -------------------------------------------------------------------------
    def generate_personas(
        self,
        topic: str,
        num_agents: int,
        custom_prompt: Optional[str] = None,
        default_memory_type: Optional[str] = None,
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
                    "You must output ONLY a valid JSON object conforming to the user's schema."
                ),
            },
            {"role": "user", "content": personas_prompt},
        ]

        try:
            response = self.llm.generate_response(messages=messages, response_format="json_object")

            if response.get("type") != "text":
                raise RuntimeError("LLM returned a tool call instead of persona data.")

            content = response.get("content", "").strip()
            if not content:
                raise RuntimeError("LLM returned an empty response while generating personas.")

            # 1. Clean markdown code fences if present
            cleaned_content = re.sub(r'^```(?:json)?\s*', '', content, flags=re.MULTILINE)
            cleaned_content = re.sub(r'\s*```$', '', cleaned_content, flags=re.MULTILINE).strip()

            # 2. Parse JSON safely
            try:
                data = json.loads(cleaned_content)
            except json.JSONDecodeError:
                match = re.search(r'(\[.*\]|\{.*\})', cleaned_content, re.DOTALL)
                if match:
                    data = json.loads(match.group(1))
                else:
                    raise ValueError("LLM did not return recognizable JSON.")

            # 3. Resiliently find the list of personas
            personas = None
            if isinstance(data, list):
                personas = data
            elif isinstance(data, dict):
                for key in ["personas", "agents", "stakeholders", "panel", "data", "result"]:
                    if isinstance(data.get(key), list):
                        personas = data[key]
                        break
                # Fallback: grab the first list value found inside the dictionary
                if personas is None:
                    for val in data.values():
                        if isinstance(val, list):
                            personas = val
                            break

            if not isinstance(personas, list):
                raise ValueError("Invalid persona response: 'personas' must be a list.")

            # Slice if LLM generated more than requested
            if len(personas) > num_agents:
                personas = personas[:num_agents]

            validated_personas: List[Dict[str, Any]] = []
            for index, persona in enumerate(personas, start=1):
                if not isinstance(persona, dict):
                    raise ValueError(f"Persona #{index} must be a JSON object.")

                required_fields = ["name", "background", "stance", "tone"]
                missing_fields = [field for field in required_fields if not persona.get(field)]

                if missing_fields:
                    raise ValueError(f"Persona #{index} is missing required fields: {', '.join(missing_fields)}")

                # Auto-assign avatarSeed if omitted by the LLM
                if not persona.get("avatarSeed"):
                    persona["avatarSeed"] = persona["name"].strip()

                persona["memory_config"] = {"type": memory_type, "window_size": 4}
                validated_personas.append(persona)

            return validated_personas

        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Failed to parse LLM persona response as JSON: {exc}") from exc
        except Exception as exc:
            raise RuntimeError(f"Failed to generate personas: {exc}") from exc

    def start_simulation(
        self,
        topic: str,
        personas: List[Dict[str, Any]],
        memory_strategy: Dict[str, Any],
        visibility_matrix: Optional[Dict[str, List[str]]] = None,
    ) -> str:
        if not topic or not topic.strip():
            raise ValueError("Topic cannot be empty.")

        if not personas:
            raise ValueError("At least one persona is required.")

        if not memory_strategy:
            memory_strategy = {"type": "sliding_window", "window_size": 4}

        sim_id = f"sim_{uuid.uuid4().hex[:12]}"

        self.repo.create_simulation(
            sim_id=sim_id,
            topic=topic,
            memory_strategy=memory_strategy,
            personas=personas,
            visibility_matrix=visibility_matrix,
        )

        return sim_id

    def next_turn(self, simulation_id: str) -> Dict[str, Any]:
        simulation = self.repo.get_simulation_by_id(simulation_id)
        if not simulation:
            raise ValueError(f"Simulation '{simulation_id}' not found.")

        personas = simulation.get("personas") or []
        if not personas:
            raise ValueError(f"Simulation '{simulation_id}' has no personas.")

        discussion_history = self.repo.get_current_discussion_history(simulation_id)
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
            "status": "ready_for_generation",
        }

    def simulation_analytics(
        self,
        simulation_id: str,
        current_turns: List[Dict[str, Any]],
        current_personas: List[Dict[str, Any]],
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

        most_active_agent: Optional[str] = None
        most_active_agent_turns: int = 0
        
        # Pylance-safe lambda key (fixes "No overloads for max" error)
        if agent_counts:
            most_active_agent = max(agent_counts, key=lambda k: agent_counts[k])
            most_active_agent_turns = agent_counts[most_active_agent]

        stance_scores: List[float] = []
        for turn in current_turns:
            opinion = turn.get("opinion_snapshot") or {}
            score = opinion.get("current_stance_score")
            if score is not None:
                try:
                    stance_scores.append(float(score))
                except (TypeError, ValueError):
                    pass

        avg_stance_score = (sum(stance_scores) / len(stance_scores)) if stance_scores else None

        return {
            "simulation_id": simulation_id,
            "total_turns": total_turns,
            "unique_agents": unique_agents,
            "avg_stance_score": avg_stance_score,
            "most_active_agent": most_active_agent,
            "most_active_agent_turns": most_active_agent_turns,
        }

    def continue_simulation(
        self,
        simulation_id: str,
        steps: int = 1,
    ) -> Dict[str, Any]:
        if steps < 1:
            raise ValueError("Steps must be at least 1.")

        simulation = self.repo.get_simulation_by_id(simulation_id)
        if not simulation:
            raise ValueError(f"Simulation '{simulation_id}' not found.")

        visibility_matrix = simulation.get("visibility_matrix") or {}

        final_state = self.engine.step_discussion(
            sim_id=simulation_id,
            steps=steps,
            visibility_matrix=visibility_matrix,
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
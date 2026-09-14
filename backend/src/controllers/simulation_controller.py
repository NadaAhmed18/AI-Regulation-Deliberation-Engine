import json
import threading
from typing import Any, Dict, List, Optional, Iterator
import uuid
import re

from src.clients.llm_client import LLMClient
from src.config import PERSONA_MODEL
from src.controllers.simulation_repository import SimulationRepository
from src.orchestration.discussion_graph import DiscussionEngine
from src.agent.base_agent import BaseAgent
from src.agent.memory.memory_manager import ConversationContextManager
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
        self.llm = LLMClient(model_name=PERSONA_MODEL)
        self.engine = DiscussionEngine()
        self._initialized = True

    # -------------------------------------------------------------------------
    # Delegated Repository Methods
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
    # Persona Generation (Fast OpenRouter openai/gpt-oss-120b)
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

        num_agents = max(2, min(num_agents, 6))
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
                    "You are an expert Sociologist and Simulation Designer. "
                    "You must output ONLY a valid JSON array of persona objects with keys: "
                    "'name', 'background', 'stance', 'tone'."
                ),
            },
            {"role": "user", "content": personas_prompt},
        ]

        try:
            response = self.llm.generate_response(
                messages=messages,
                response_format="json_object",
                max_tokens=2000,
            )
            content = response.get("content", "").strip()

            cleaned_content = re.sub(r'^```(?:json)?\s*', '', content, flags=re.MULTILINE)
            cleaned_content = re.sub(r'\s*```$', '', cleaned_content, flags=re.MULTILINE).strip()

            data = None
            try:
                data = json.loads(cleaned_content)
            except json.JSONDecodeError:
                match = re.search(r'(\[.*\]|\{.*\})', cleaned_content, re.DOTALL)
                if match:
                    data = json.loads(match.group(1))

            personas = None
            if isinstance(data, list):
                personas = data
            elif isinstance(data, dict):
                for k in ["personas", "agents", "stakeholders", "panel", "data"]:
                    if isinstance(data.get(k), list):
                        personas = data[k]
                        break
                if personas is None:
                    for val in data.values():
                        if isinstance(val, list):
                            personas = val
                            break

            if not isinstance(personas, list) or len(personas) < 2:
                # Fallback persona set
                personas = [
                    {
                        "name": "Dr. Elena Vance",
                        "background": "AI Safety Auditor at European AI Safety Institute.",
                        "stance": "Strict mandatory hardware audits and compute verification are vital.",
                        "tone": "Formal, empirical, cautious",
                    },
                    {
                        "name": "Alex Mercer",
                        "background": "Open Source Foundation Lead Developer.",
                        "stance": "Decentralized open weights prevent monopolies and ensure resilience.",
                        "tone": "Direct, technical, assertive",
                    },
                    {
                        "name": "Senator Marcus Cole",
                        "background": "Senior Legal Counsel for Technology Governance.",
                        "stance": "Tiered, proportional compliance balancing innovation and risk.",
                        "tone": "Pragmatic, diplomatic, structured",
                    }
                ][:num_agents]

            validated_personas: List[Dict[str, Any]] = []
            for index, p in enumerate(personas[:num_agents], start=1):
                name = p.get("name", f"Stakeholder_{index}")
                validated_personas.append({
                    "name": name,
                    "background": p.get("background", "Domain Policy Specialist"),
                    "stance": p.get("stance", "Moderate balanced approach"),
                    "tone": p.get("tone", "Professional, analytical"),
                    "avatarSeed": p.get("avatarSeed") or name.strip(),
                    "memory_config": {"type": memory_type, "window_size": 4},
                })

            return validated_personas

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

    # -------------------------------------------------------------------------
    # Restored Simulation Analytics Method
    # -------------------------------------------------------------------------
    def simulation_analytics(
        self,
        simulation_id: str,
        current_turns: List[Dict[str, Any]],
        current_personas: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Calculates quantitative overview metrics for turns & personas."""
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

    # -------------------------------------------------------------------------
    # Execution: Continue Simulation & Real-time Turn Stream
    # -------------------------------------------------------------------------
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

    def stream_discussion_turn(self, simulation_id: str) -> Iterator[Dict[str, Any]]:
        """Yields real-time events during turn execution."""
        sim_data = self.repo.get_simulation_by_id(simulation_id)
        if not sim_data:
            yield {"type": "error", "message": f"Simulation '{simulation_id}' not found."}
            return

        personas = sim_data.get("personas") or []
        topic = str(sim_data["topic"])
        visibility_matrix = sim_data.get("visibility_matrix") or {}
        memory_strategy = sim_data.get("memory_strategy") or {"type": "sliding_window", "window_size": 4}

        history = self.repo.get_current_discussion_history(simulation_id)
        last_round = self.repo.get_last_round_number(simulation_id)
        current_round = last_round + 1

        # 1. Orchestrate speaker
        next_speaker = self.engine.orchestrator.decide_next_speaker(
            topic=topic,
            personas=personas,
            history=history,
        )
        persona = next((p for p in personas if p["name"] == next_speaker), personas[0])

        yield {
            "type": "speaker_selected",
            "speaker": next_speaker,
            "round": current_round,
            "avatarSeed": persona.get("avatarSeed", next_speaker),
        }

        # 2. Build Context
        agent = BaseAgent(persona=persona, topic=topic)
        allowed_speakers = visibility_matrix.get(next_speaker, None)
        agent_memory = persona.get("memory_config") or memory_strategy

        context_mgr = ConversationContextManager(
            simulation_id=simulation_id,
            topic=topic,
            strategy=agent_memory,
        )
        messages = context_mgr.build_context_for_agent(
            system_prompt=agent.system_prompt,
            current_agent_name=next_speaker,
            allowed_speakers=allowed_speakers,
        )

        # 3. Stream ReAct Execution
        final_message = ""
        cited_sources: List[str] = []

        for event in agent.run_react_loop_stream(messages=messages):
            yield event
            if event.get("type") == "final":
                final_message = event.get("content", "")
                cited_sources = event.get("sources", [])

        # 4. Grade Opinion Shift
        previous_score = self.repo.get_last_stance_score(sim_id=simulation_id, agent_name=next_speaker)
        opinion_snapshot = self.engine._grade_opinion(
            topic=topic,
            agent_name=next_speaker,
            original_stance=persona["stance"],
            latest_statement=final_message,
            previous_score=previous_score,
        )

        # 5. Persist to PostgreSQL
        self.repo.save_discussion_turn(
            sim_id=simulation_id,
            round_num=current_round,
            agent_name=next_speaker,
            role="assistant",
            content=final_message,
            opinion=opinion_snapshot,
            sources=cited_sources,
        )

        stance_score = float(opinion_snapshot.get("current_stance_score", 0.0))
        shift_mag = float(opinion_snapshot.get("shift_magnitude") or 0.0)

        completed_turn = {
            "id": f"turn_{uuid.uuid4().hex[:8]}",
            "round_number": current_round,
            "agent_name": next_speaker,
            "content": final_message,
            "tools_called": [],
            "retrieved_sources": cited_sources,
            "opinion_snapshot": {
                "current_stance_score": stance_score,
                "shift_magnitude": shift_mag,
                "influencer": None,
                "reasoning": opinion_snapshot.get("reasoning", "Turn completed."),
                "cfg": {
                    "guidance_scale_gamma": abs(shift_mag) * 0.1,
                    "shift_magnitude": shift_mag,
                    "guidance_vector": stance_score,
                    "dynamic": "Adaptive Evolution",
                },
            },
        }

        yield {
            "type": "turn_complete",
            "turn": completed_turn,
        }
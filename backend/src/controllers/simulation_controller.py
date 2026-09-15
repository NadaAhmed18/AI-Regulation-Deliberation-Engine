import json
import re
import threading
import uuid
from typing import Any, Dict, Iterator, List, Optional

from src.agent.base_agent import BaseAgent
from src.agent.memory.memory_manager import ConversationContextManager
from src.clients.llm_client import LLMClient
from src.config import PERSONA_MODEL
from src.controllers.analytics_controller import AnalyticsController
from src.controllers.repository.simulation_repository import SimulationRepository
from src.orchestration.discussion_graph import DiscussionEngine
from src.utils.prompt_builder import render_prompt


class SimulationController:
    """
    Primary controller orchestrating debate execution, real-time SSE streaming,
    agent generation, and persistence.
    """
    _instance: Optional["SimulationController"] = None
    _lock: threading.Lock = threading.Lock()

    # Explicit class-level type annotations for Pylance
    repo: SimulationRepository
    analytics_ctrl: AnalyticsController
    llm: LLMClient
    engine: DiscussionEngine
    _initialized: bool

    def __new__(cls) -> "SimulationController":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return

        self.repo = SimulationRepository()
        self.analytics_ctrl = AnalyticsController()
        self.llm = LLMClient(model_name=PERSONA_MODEL)
        self.engine = DiscussionEngine()
        self._initialized = True

    # -------------------------------------------------------------------------
    # Setup & Persona Generation
    # -------------------------------------------------------------------------
    def generate_personas(
        self,
        topic: str,
        num_agents: int = 3,
        custom_prompt: Optional[str] = None,
        default_memory_type: str = "sliding_window",
    ) -> List[Dict[str, Any]]:
        """Generates domain-specific personas with initial stances and memory settings."""
        if not topic.strip():
            raise ValueError("Topic cannot be empty.")

        num_agents = max(2, min(num_agents, 6))
        prompt = render_prompt(
            "setup_personas",
            topic=topic,
            num_agents=num_agents,
            custom_instructions=custom_prompt or "None",
        )

        response = self.llm.generate_response(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a Simulation Designer. Return ONLY a JSON array of "
                        "persona objects with: 'name', 'background', 'stance', 'tone'."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            response_format="json_object",
            max_tokens=2000,
        )

        content = response.get("content", "").strip()
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.MULTILINE).strip()

        try:
            parsed = json.loads(cleaned)
            personas = parsed if isinstance(parsed, list) else parsed.get("personas", list(parsed.values())[0])
        except Exception:
            personas = [
                {
                    "name": "Dr. Aris Thorne",
                    "background": "AI Safety Researcher",
                    "stance": "Strict compute controls and hardware verification are imperative.",
                    "tone": "Empirical, cautious",
                },
                {
                    "name": "Maya Lin",
                    "background": "Open Source Foundation Lead",
                    "stance": "Decentralized weights foster resilience and stop market monopolies.",
                    "tone": "Assertive, technical",
                },
                {
                    "name": "Elena Rostova",
                    "background": "Tech Policy Director",
                    "stance": "Tiered, proportional risk models safeguard innovation.",
                    "tone": "Pragmatic, diplomatic",
                },
            ]

        return [
            {
                "name": p.get("name", f"Panelist_{i+1}"),
                "background": p.get("background", "Domain Policy Specialist"),
                "stance": p.get("stance", "Balanced moderate governance"),
                "tone": p.get("tone", "Analytical"),
                "avatarSeed": p.get("name", f"agent_{i+1}"),
                "memory_config": {"type": default_memory_type, "window_size": 4},
            }
            for i, p in enumerate(personas[:num_agents])
        ]

    def start_simulation(
        self,
        topic: str,
        personas: List[Dict[str, Any]],
        memory_strategy: Optional[Dict[str, Any]] = None,
        visibility_matrix: Optional[Dict[str, List[str]]] = None,
    ) -> str:
        """Initializes a new debate in PostgreSQL."""
        if not topic.strip() or not personas:
            raise ValueError("Topic and at least 2 personas are required.")

        sim_id = f"sim_{uuid.uuid4().hex[:12]}"
        strategy = memory_strategy or {"type": "sliding_window", "window_size": 4}

        self.repo.create_simulation(
            sim_id=sim_id,
            topic=topic,
            memory_strategy=strategy,
            personas=personas,
            visibility_matrix=visibility_matrix,
        )
        return sim_id

    # -------------------------------------------------------------------------
    # Execution: Step (Sync) & Stream (SSE with Real-Time Analytics)
    # -------------------------------------------------------------------------
    def execute_next_turn(self, simulation_id: str) -> Dict[str, Any]:
        """Executes a single discrete turn synchronously and updates analytics."""
        sim = self.repo.get_simulation_by_id(simulation_id)
        if not sim:
            raise ValueError(f"Simulation '{simulation_id}' not found.")

        result = self.engine.step_discussion(
            sim_id=simulation_id,
            steps=1,
            visibility_matrix=sim.get("visibility_matrix"),
        )

        analytics = self.analytics_ctrl.compute_turn_analytics(simulation_id)

        opinion = result.get("last_opinion") or {}
        return {
            "turn": {
                "id": f"turn_{uuid.uuid4().hex[:8]}",
                "round_number": result.get("current_round"),
                "agent_name": result.get("current_speaker"),
                "content": result.get("last_message"),
                "retrieved_sources": result.get("last_sources", []),
                "opinion_snapshot": opinion,
            },
            "analytics": analytics,
        }

    def stream_discussion_turn(self, simulation_id: str) -> Iterator[Dict[str, Any]]:
        """
        Streams turn execution via SSE:
        1. Emits speaker selection
        2. Streams thinking tokens and generation tokens
        3. Emits tool usage start and end
        4. Saves turn, evaluates stance, updates analytics, and emits 'turn_complete' with fresh metrics.
        """
        sim = self.repo.get_simulation_by_id(simulation_id)
        if not sim:
            yield {"type": "error", "message": f"Simulation '{simulation_id}' not found."}
            return

        personas = sim.get("personas") or []
        topic = sim["topic"]
        visibility_matrix = sim.get("visibility_matrix") or {}
        history = self.repo.get_discussion_history(simulation_id)
        current_round = self.repo.get_last_round_number(simulation_id) + 1

        # 1. Orchestrate next speaker
        next_speaker = self.engine.orchestrator.decide_next_speaker(personas=personas, history=history)
        persona = next((p for p in personas if p["name"] == next_speaker), personas[0])

        yield {
            "type": "speaker_selected",
            "speaker": next_speaker,
            "round": current_round,
            "avatarSeed": persona.get("avatarSeed", next_speaker),
        }

        # 2. Build contextual memory constrained by the visibility topology
        agent = BaseAgent(persona=persona, topic=topic)
        allowed_speakers = visibility_matrix.get(next_speaker)
        memory_cfg = persona.get("memory_config") or sim.get("memory_strategy", {})

        messages = ConversationContextManager(
            simulation_id=simulation_id,
            topic=topic,
            strategy=memory_cfg,
        ).build_context_for_agent(
            system_prompt=agent.system_prompt,
            current_agent_name=next_speaker,
            allowed_speakers=allowed_speakers,
        )

        # 3. Stream agent thinking, tool executions, and tokens
        final_message = ""
        cited_sources: List[str] = []

        for event in agent.run_react_loop_stream(messages=messages):
            yield event
            if event.get("type") == "final":
                final_message = event.get("content", "")
                cited_sources = event.get("sources", [])

        # 4. Grade Stance Shift
        prev_score = self.repo.get_last_stance_score(sim_id=simulation_id, agent_name=next_speaker)
        opinion_snapshot = self.engine._grade_opinion(
            topic=topic,
            latest_statement=final_message,
            previous_score=prev_score,
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

        # 6. Auto-update Analytics and emit completed payload with analytics included
        updated_analytics = self.analytics_ctrl.compute_turn_analytics(simulation_id)

        yield {
            "type": "turn_complete",
            "turn": {
                "id": f"turn_{uuid.uuid4().hex[:8]}",
                "round_number": current_round,
                "agent_name": next_speaker,
                "content": final_message,
                "retrieved_sources": cited_sources,
                "opinion_snapshot": opinion_snapshot,
            },
            "analytics": updated_analytics,
        }
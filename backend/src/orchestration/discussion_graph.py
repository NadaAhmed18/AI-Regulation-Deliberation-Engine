from typing import Any, Dict, List, Optional, TypedDict
from langgraph.graph import END, StateGraph
from langfuse import observe, get_client

from src.agent.base_agent import BaseAgent
from src.agent.memory.memory_manager import ConversationContextManager
from src.agent.orchestrator import Orchestrator
from src.controllers.repository.simulation_repository import SimulationRepository
from src.orchestration.nli_grader import DebertaStanceGrader


class DebateState(TypedDict):
    simulation_id: str
    topic: str
    personas: List[dict]
    visibility_matrix: Dict[str, List[str]]
    memory_strategy: dict
    max_rounds: int
    current_round: int
    current_speaker: str
    last_message: str
    last_sources: list
    last_opinion: dict
    intervention: Optional[str]


class DiscussionEngine:
    def __init__(self):
        self.orchestrator = Orchestrator()
        self.repo = SimulationRepository()
        self.opinion_grader = DebertaStanceGrader()

        # Build LangGraph State Machine
        workflow = StateGraph(DebateState)
        workflow.add_node("orchestrate", self.node_orchestrate)
        workflow.add_node("agent_turn", self.node_agent_turn)
        workflow.add_node("grade_opinion", self.node_grade_opinion)

        workflow.set_entry_point("orchestrate")
        workflow.add_edge("orchestrate", "agent_turn")
        workflow.add_edge("agent_turn", "grade_opinion")
        workflow.add_conditional_edges(
            "grade_opinion",
            lambda s: "continue" if s["current_round"] < s["max_rounds"] else "end",
            {"continue": "orchestrate", "end": END},
        )
        self.graph = workflow.compile()

    @observe(as_type="generation", name="node_orchestrate")
    def node_orchestrate(self, state: DebateState) -> Dict[str, Any]:
        history = self.repo.get_current_discussion_history(state["simulation_id"])
        next_speaker = self.orchestrator.decide_next_speaker(
            personas=state["personas"],
            history=history,
        )
        return {
            "current_speaker": next_speaker,
            "current_round": state["current_round"] + 1,
        }

    @observe(as_type="generation", name="node_agent_turn")
    def node_agent_turn(self, state: DebateState) -> Dict[str, Any]:
        speaker = state["current_speaker"]
        persona = next((p for p in state["personas"] if p["name"] == speaker), state["personas"][0])

        agent = BaseAgent(persona=persona, topic=state["topic"])
        memory_cfg = persona.get("memory_config") or state.get("memory_strategy", {"type": "sliding_window", "window_size": 4})
        allowed = state.get("visibility_matrix", {}).get(speaker)

        messages = ConversationContextManager(
            simulation_id=state["simulation_id"],
            topic=state["topic"],
            strategy=memory_cfg,
        ).build_context_for_agent(
            system_prompt=agent.system_prompt,
            current_agent_name=speaker,
            allowed_speakers=allowed,
            intervention=state.get("intervention")
        )

        final_text, cited_sources = agent.run_react_loop(messages=messages)
        return {"last_message": final_text, "last_sources": cited_sources}

    def _grade_opinion(
        self,
        topic: str,
        latest_statement: str,
        previous_score: Optional[float] = None,
        **_kwargs: Any,
    ) -> Dict[str, Any]:
        """Evaluates statement stance via local CPU ONNX NLI."""
        return self.opinion_grader.evaluate_stance(
            topic=topic,
            statement=latest_statement,
            previous_score=previous_score,
        )

    @observe(as_type="generation", name="node_grade_opinion")
    def node_grade_opinion(self, state: DebateState) -> Dict[str, Any]:
        speaker = state["current_speaker"]
        previous_score = self.repo.get_last_stance_score(sim_id=state["simulation_id"], agent_name=speaker)

        opinion = self._grade_opinion(
            topic=state["topic"],
            latest_statement=state["last_message"],
            previous_score=previous_score,
        )

        self.repo.save_discussion_turn(
            sim_id=state["simulation_id"],
            round_num=state["current_round"],
            agent_name=speaker,
            role="assistant",
            content=state["last_message"],
            opinion=opinion,
            sources=state["last_sources"],
        )
        return {"last_opinion": opinion}

    @observe(name="step_discussion")
    def step_discussion(
        self,
        sim_id: str,
        steps: int = 1,
        visibility_matrix: Optional[Dict[str, List[str]]] = None,
        intervention: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Executes N discrete turns through the deliberation graph and pauses."""
        try:
            update_current_trace = getattr(get_client(), "update_current_trace", None)
            if callable(update_current_trace):
                update_current_trace(
                    session_id=sim_id,  # <--- ENABLES SESSIONS FOR SYNC RUNS
                    metadata={"simulation_id": sim_id},
                )
        except Exception:
            pass
        
        sim = self.repo.get_simulation_by_id(sim_id)
        if not sim:
            raise ValueError(f"Simulation ID '{sim_id}' not found.")

        current_round = self.repo.get_last_round_number(sim_id)
        target_round = current_round + steps

        resume_state: DebateState = {
            "simulation_id": sim_id,
            "topic": str(sim["topic"]),
            "personas": list(sim["personas"]),
            "visibility_matrix": visibility_matrix if visibility_matrix is not None else dict(sim.get("visibility_matrix") or {}),
            "memory_strategy": dict(sim["memory_strategy"]),
            "max_rounds": target_round,
            "current_round": current_round,
            "current_speaker": "",
            "last_message": "",
            "last_sources": [],
            "last_opinion": {},
            "intervention": intervention,
        }

        return self.graph.invoke(resume_state)
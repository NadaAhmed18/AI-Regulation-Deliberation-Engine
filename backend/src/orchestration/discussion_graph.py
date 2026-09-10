import json
from typing import List, Dict, Any, TypedDict, Optional
from langgraph.graph import StateGraph, END
from langfuse import observe

from src.controllers.simulation_controller import SimulationController
from src.agent.memory.memory_manager import ConversationContextManager
from src.agent.base_agent import BaseAgent
from src.agent.orchestrator import Orchestrator
from src.orchestration.nli_grader import DebertaStanceGrader


# 1. State Definition
class DebateState(TypedDict):
    simulation_id: str
    topic: str
    personas: List[dict]
    visibility_matrix: Dict[str, List[str]]  # { listener: [allowed_speakers] }
    memory_strategy: dict
    max_rounds: int
    current_round: int

    current_speaker: str
    last_message: str
    last_sources: list
    last_opinion: dict


class DiscussionEngine:
    def __init__(self):
        self.orchestrator = Orchestrator()
        # High-precision local NLI cross-encoder for stance scoring
        self.stance_grader = DebertaStanceGrader()
        self.controller = SimulationController()

        # Build the LangGraph Workflow
        workflow = StateGraph(DebateState)

        workflow.add_node("orchestrate", self.node_orchestrate)
        workflow.add_node("agent_turn", self.node_agent_turn)
        workflow.add_node("grade_opinion", self.node_grade_opinion)

        workflow.set_entry_point("orchestrate")
        workflow.add_edge("orchestrate", "agent_turn")
        workflow.add_edge("agent_turn", "grade_opinion")

        # Stop condition: loop until current_round reaches max_rounds
        workflow.add_conditional_edges(
            "grade_opinion",
            lambda state: "continue" if state["current_round"] < state["max_rounds"] else "end",
            {"continue": "orchestrate", "end": END}
        )

        self.graph = workflow.compile()

    @observe(as_type="generation", name="node_orchestrate")
    def node_orchestrate(self, state: DebateState) -> Dict[str, Any]:
        """Moderator selects the next speaker based on recent turns."""
        temp_manager = ConversationContextManager(
            simulation_id=state["simulation_id"],
            topic=state["topic"],
            strategy={"type": "sliding_window", "window_size": 3}
        )
        recent_history = temp_manager.build_context_for_agent(system_prompt="")

        next_speaker = self.orchestrator.decide_next_speaker(
            topic=state["topic"],
            personas=state["personas"],
            messages=recent_history
        )

        return {
            "current_speaker": next_speaker,
            "current_round": state["current_round"] + 1
        }

    @observe(as_type="generation", name="node_agent_turn")
    def node_agent_turn(self, state: DebateState) -> Dict[str, Any]:
        """Selected agent speaks using their persona, custom memory type, and visibility rules."""
        speaker_name = state["current_speaker"]
        persona = next((p for p in state["personas"] if p["name"] == speaker_name), state["personas"][0])
        
        agent = BaseAgent(persona=persona, topic=state["topic"])

        # 1. Resolve agent's individual memory config (or fallback to simulation memory)
        agent_memory = persona.get("memory_config") or state.get("memory_strategy", {"type": "sliding_window", "window_size": 4})

        # 2. Get incoming neighbors this agent is allowed to see
        visibility_matrix = state.get("visibility_matrix", {})
        allowed_speakers = visibility_matrix.get(speaker_name, None)

        # 3. Build graph-routed context
        context_manager = ConversationContextManager(
            simulation_id=state["simulation_id"],
            topic=state["topic"],
            strategy=agent_memory
        )
        messages = context_manager.build_context_for_agent(
            system_prompt=agent.system_prompt,
            current_agent_name=speaker_name,
            allowed_speakers=allowed_speakers
        )

        # 4. Run the ReAct loop
        final_text, cited_sources = agent.run_react_loop(messages=messages)

        return {
            "last_message": final_text,
            "last_sources": cited_sources
        }

    @observe(as_type="generation", name="node_grade_opinion")
    def node_grade_opinion(self, state: DebateState) -> Dict[str, Any]:
        """Evaluates opinion shift using DeBERTa NLI and persists turn to PostgreSQL via SimulationController."""
        speaker_name = state["current_speaker"]

        # Fetch the agent's real previous score (None on first turn)
        previous_score = self.controller.get_last_stance_score(
            sim_id=state["simulation_id"],
            agent_name=speaker_name,
        )

        # Local NLI inference (no remote LLM required)
        opinion_snapshot = self.stance_grader.evaluate_stance(
            topic=state["topic"],
            statement=state["last_message"],
            previous_score=previous_score
        )

        # Persist turn
        self.controller.save_discussion_turn(
            sim_id=state["simulation_id"],
            round_num=state["current_round"],
            agent_name=speaker_name,
            role="assistant",
            content=state["last_message"],
            opinion=opinion_snapshot,
            sources=state["last_sources"]
        )

        return {
            "last_opinion": opinion_snapshot
        }

    @observe(name="step_discussion")
    def step_discussion(
        self,
        sim_id: str,
        steps: int = 1,
        visibility_matrix: Optional[Dict[str, List[str]]] = None
    ) -> Dict[str, Any]:
        """
        Observability Entry Point: Runs the discussion for N steps and logs the trace to Langfuse.
        Pulls latest state via SimulationController so simulations can be paused and resumed on demand.
        """
        # 1. Fetch simulation configuration from DB
        sim_data = self.controller.get_simulation_by_id(sim_id)
        if not sim_data:
            raise ValueError(f"Simulation ID '{sim_id}' not found in database.")

        # 2. Get the highest round currently played
        last_round = self.controller.get_last_round_number(sim_id)

        topic: str = str(sim_data["topic"])
        personas: List[dict] = list(sim_data["personas"])
        memory_strat: dict = dict(sim_data["memory_strategy"])

        current_round: int = last_round
        target_round: int = current_round + steps

        print(f"\n[Engine] 🚀 Resuming '{sim_id}': Round {current_round} -> Round {target_round} (+{steps} step(s))...")

        # 3. Construct state and execute graph
        resume_state: DebateState = {
            "simulation_id": sim_id,
            "topic": topic,
            "personas": personas,
            "visibility_matrix": visibility_matrix or {},
            "memory_strategy": memory_strat,
            "max_rounds": target_round,
            "current_round": current_round,
            "current_speaker": "",
            "last_message": "",
            "last_sources": [],
            "last_opinion": {}
        }

        final_state: Dict[str, Any] = self.graph.invoke(resume_state)
        print(f"[Engine] ⏸️ Paused at Round {final_state['current_round']}.")
        return final_state


if __name__ == "__main__":
    # Test runner: python -m src.orchestration.discussion_graph
    import uuid
    from src.orchestration.setup_manager import SetupManager

    print("\n" + "=" * 60)
    print(" smoke test: DiscussionEngine & step_discussion ".center(60, "="))
    print("=" * 60)

    test_sim_id = f"test_sim_{uuid.uuid4().hex[:6]}"
    test_topic = "Should AI labs register GPU clusters above 10,000 units?"

    # 1. Setup personas with distinct memory strategies
    setup_mgr = SetupManager()
    test_personas = [
        {
            "name": "Dr. Elena Kovac",
            "background": "AI Security Auditor at European AI Safety Institute.",
            "stance": "Pro-regulation, mandatory hardware registry.",
            "tone": "Formal, empirical, cautious",
            "memory_config": {"type": "summary"}
        },
        {
            "name": "Alex Mercer",
            "background": "Open Source Foundation representative.",
            "stance": "Anti-centralized registration, privacy advocate.",
            "tone": "Assertive, technical, direct",
            "memory_config": {"type": "sliding_window", "window_size": 2}
        },
    ]

    # 2. Construct Visibility Matrix (Ring: Elena sees Alex, Alex sees Elena)
    test_vis_matrix = SetupManager.build_visibility_matrix(test_personas, topology="ring")

    # 3. Initialize Postgres simulation record using the Controller
    controller = SimulationController()
    controller.create_simulation(
        sim_id=test_sim_id,
        topic=test_topic,
        memory_strategy={"type": "sliding_window", "window_size": 3},
        personas=test_personas
    )
    print(f"[+] Initialized simulation record: '{test_sim_id}' in PostgreSQL.")

    engine = DiscussionEngine()

    # 4. Phase 1: Run 2 steps
    print("\n--- PHASE 1: Running 2 Initial Steps ---")
    state_after_2 = engine.step_discussion(
        sim_id=test_sim_id,
        steps=2,
        visibility_matrix=test_vis_matrix
    )
    print(f"[✔] Phase 1 completed. Current round: {state_after_2['current_round']}")

    # 5. Phase 2: Resume and run 1 more step
    print("\n--- PHASE 2: Resuming for 1 Additional Step ---")
    state_after_3 = engine.step_discussion(
        sim_id=test_sim_id,
        steps=1,
        visibility_matrix=test_vis_matrix
    )
    print(f"[✔] Phase 2 completed. Final round reached: {state_after_3['current_round']}")
    print(f"[Last Speaker]: {state_after_3['current_speaker']}")
    print(f"[Last Stance Score]: {state_after_3['last_opinion'].get('current_stance_score')}")
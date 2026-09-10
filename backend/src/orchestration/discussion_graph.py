import json
from typing import List, Dict, Any, TypedDict, Optional
from langgraph.graph import StateGraph, END
from langfuse import observe

from src.clients.postgres import PostgresClient
from src.agent.memory.memory_manager import ConversationContextManager
from src.agent.base_agent import BaseAgent
from src.agent.orchestrator import Orchestrator
from src.orchestration.opinion_grader import OpinionGrader


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
        self.opinion_grader = OpinionGrader()
        self.db = PostgresClient()

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
        """Evaluates opinion shift and persists turn to PostgreSQL."""
        speaker_name = state["current_speaker"]
        persona = next((p for p in state["personas"] if p["name"] == speaker_name), state["personas"][0])

        # Fetch the agent's own last scored turn (None if this is their
        # first scored turn in this simulation) instead of always
        # comparing against a hardcoded 0.0 -- 0.0 is a genuine neutral
        # prior score, `None` means "no prior score exists yet," and
        # `OpinionGrader.evaluate_stance` (like `DebertaStanceGrader` in
        # nli_grader.py) treats the two differently. See
        # `PostgresClient.get_last_stance_score` and
        # docs/Influence-Tracking.md's Section 3 Implementation Notes.
        previous_score = self.db.get_last_stance_score(
            sim_id=state["simulation_id"],
            agent_name=speaker_name,
        )

        opinion_snapshot = self.opinion_grader.evaluate_stance(
            topic=state["topic"],
            agent_name=speaker_name,
            original_stance=persona["stance"],
            latest_statement=state["last_message"],
            previous_score=previous_score
        )

        # Persist turn
        self.db.save_discussion_turn(
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
        Pulls latest state from PostgreSQL so simulations can be paused and resumed on demand.
        """
        # 1. Fetch simulation configuration from DB
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT topic, memory_strategy, personas FROM simulations WHERE simulation_id = %s",
                    (sim_id,)
                )
                raw_sim_row = cur.fetchone()
                if not raw_sim_row:
                    raise ValueError(f"Simulation ID '{sim_id}' not found in database.")

                sim_data: Dict[str, Any] = dict(raw_sim_row)

                # 2. Get the highest round currently played
                cur.execute(
                    "SELECT COALESCE(MAX(round_number), 0) AS last_round FROM discussion_history WHERE simulation_id = %s",
                    (sim_id,)
                )
                raw_round_row = cur.fetchone()
                last_round: int = int(dict(raw_round_row)["last_round"]) if raw_round_row else 0

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

    # 3. Initialize Postgres simulation record
    db_client = PostgresClient()
    db_client.create_simulation(
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

import json
from typing import List, Dict, Any, TypedDict
from langgraph.graph import StateGraph, END
from langfuse import observe

from src.clients.postgres import PostgresClient
from src.agent.memory.memory_manager import ConversationContextManager
from src.agent.base_agent import BaseAgent
from src.agent.orchestrator import Orchestrator
from src.orchestration.opinion_grader import OpinionGrader


# 1. Define the Graph State
class DebateState(TypedDict):
    simulation_id: str
    topic: str
    personas: List[dict]
    memory_strategy: dict
    max_rounds: int
    current_round: int
    
    # Passing data between nodes
    current_speaker: str
    last_message: str
    last_sources: list
    last_opinion: dict


class DiscussionEngine:
    def __init__(self):
        self.orchestrator = Orchestrator()
        self.opinion_grader = OpinionGrader()
        self.db = PostgresClient()

        # Initialize the LangGraph
        workflow = StateGraph(DebateState)

        # Add Nodes
        workflow.add_node("orchestrate", self.node_orchestrate)
        workflow.add_node("agent_turn", self.node_agent_turn)
        workflow.add_node("grade_opinion", self.node_grade_opinion)

        # Add Edges (The Loop)
        workflow.set_entry_point("orchestrate")
        workflow.add_edge("orchestrate", "agent_turn")
        workflow.add_edge("agent_turn", "grade_opinion")
        
        # Conditional edge: Stop if we hit max rounds, otherwise loop back to orchestrate
        workflow.add_conditional_edges(
            "grade_opinion",
            lambda state: "continue" if state["current_round"] < state["max_rounds"] else "end",
            {"continue": "orchestrate", "end": END}
        )

        self.graph = workflow.compile()

    @observe(as_type="generation", name="node_orchestrate")
    def node_orchestrate(self, state: DebateState) -> Dict[str, Any]:
        """Node 1: Decide who speaks next."""
        # We need the last few messages for the Orchestrator to make a routing decision.
        # We use a temporary sliding window just for routing.
        temp_manager = ConversationContextManager(state["simulation_id"], state["topic"], {"type": "sliding_window", "window_size": 3})
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
        """Node 2: The selected agent thinks, uses tools, and speaks."""
        # 1. Find the selected persona from the state
        speaker_name = state["current_speaker"]
        persona = next((p for p in state["personas"] if p["name"] == speaker_name), state["personas"][0])
        
        # 2. Instantiate the BaseAgent
        agent = BaseAgent(persona=persona)

        # 3. Load the history applying the user's selected Memory Strategy (All, Window, Summary)
        context_manager = ConversationContextManager(
            simulation_id=state["simulation_id"], 
            topic=state["topic"], 
            strategy=state["memory_strategy"]
        )
        messages = context_manager.build_context_for_agent(system_prompt=agent.system_prompt)

        # 4. Run the ReAct loop
        final_text, cited_sources = agent.run_react_loop(messages=messages)

        return {
            "last_message": final_text,
            "last_sources": cited_sources
        }

    @observe(as_type="generation", name="node_grade_opinion")
    def node_grade_opinion(self, state: DebateState) -> Dict[str, Any]:
        """Node 3: Grade opinion shift and permanently save to DB."""
        speaker_name = state["current_speaker"]
        persona = next((p for p in state["personas"] if p["name"] == speaker_name), state["personas"][0])
        
        # 1. Calculate Opinion Shift
        opinion_snapshot = self.opinion_grader.evaluate_stance(
            topic=state["topic"],
            agent_name=speaker_name,
            original_stance=persona["stance"],
            latest_statement=state["last_message"],
            previous_score=0.0 # You could fetch the last score from DB for continuous tracking
        )

        # 2. Save everything to PostgreSQL
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
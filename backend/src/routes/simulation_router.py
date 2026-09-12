import logging
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Query, Depends

from src.agent.tools.retriever import search_ai_policy
from src.utils.response import success_response, fail_response
from src.controllers.simulation_controller import SimulationController
from src.routes.schemas.simulation import (
    ContinueSimulationRequest,
    GeneratePersonasRequest,
    SimulationAnalyticsRequest,
    StartSimulationRequest,
)

logger = logging.getLogger("uvicorn")
simulation_router = APIRouter(tags=["simulations"])


# ============================================================================
# 1. PREDEFINED TOPICS
# ============================================================================
@simulation_router.get("/topics/predefined")
def list_predefined_topics():
    topics = [
        {
            "id": "topic-1",
            "title": "Should governments mandate hardware-level kill-switches for frontier open-source AI?",
            "tag": "Frontier Security",
            "description": "Focuses on dual-use weight proliferation, foundry locks, and existential risk prevention.",
        },
        {
            "id": "topic-2",
            "title": "EU AI Act Article 51: Should training clusters >10^26 FLOPs face strict third-party audit vetoes?",
            "tag": "Regulatory Compliance",
            "description": "Balancing European single-market innovation with systemic catastrophe mitigation.",
        },
        {
            "id": "topic-3",
            "title": "Should AI developers be held strictly liable for copyright infringement in pre-training data scraping?",
            "tag": "IP & Synthetic Data",
            "description": "Fair use doctrines vs fair compensation for human creators in the age of generative models.",
        },
        {
            "id": "topic-4",
            "title": "Autonomous algorithmic trading agents: Mandate simulated sandbox isolation before exchange deployment?",
            "tag": "Financial Stability",
            "description": "Flash crash prevention, collusion between emergent LLM agents, and regulatory kill-circuits.",
        },
    ]
    return success_response(
        message="Predefined topics retrieved.",
        data=topics,
        status_code=200,
    )


# ============================================================================
# 2. SIMULATION HISTORY LIST
# ============================================================================
@simulation_router.get("/simulations/history-list")
def get_initial_history():
    simulation_controller = SimulationController()

    try:
        simulations = simulation_controller.get_all_simulations()

        # Format history so the frontend SidebarSetup can display it seamlessly
        formatted_history = []
        for sim in simulations:
            personas = sim.get("personas") or []
            turn_count = sim.get("turn_count", 0)

            # Map created_at to human-friendly category
            created_at = sim.get("created_at")
            category = "Today"
            if created_at:
                diff_days = (datetime.now() - created_at).days if isinstance(created_at, datetime) else 0
                if diff_days == 1:
                    category = "Yesterday"
                elif 2 <= diff_days <= 7:
                    category = "6 days ago"
                elif 8 <= diff_days <= 30:
                    category = "Month ago"
                elif diff_days > 30:
                    category = "Long time ago"

            formatted_history.append({
                "id": sim["simulation_id"],
                "title": sim["topic"],
                "topic": sim["topic"],
                "category": category,
                "agentsCount": len(personas) if isinstance(personas, list) else 3,
                "roundsCount": max(1, (turn_count // max(1, len(personas)))) if isinstance(personas, list) else turn_count,
                "turn_count": turn_count,
                "status": sim.get("status", "completed"),
            })

        return success_response(
            message="Simulation history retrieved.",
            data=formatted_history,
            status_code=200,
        )

    except Exception as e:
        logger.exception("Failed to fetch simulation history")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch history: {e}",
        )


# ============================================================================
# 3. DELETE SIMULATION
# ============================================================================
@simulation_router.delete("/simulations/{id}")
def delete_simulation_by_id(id: str):
    simulation_controller = SimulationController()

    try:
        deleted = simulation_controller.delete_simulation(id)
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=f"Simulation '{id}' not found.",
            )

        return success_response(
            message="Simulation deleted.",
            data={"simulation_id": id},
            status_code=200,
        )

    except Exception as e:
        logger.exception(f"Failed to delete simulation '{id}'")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete simulation: {e}",
        )


# ============================================================================
# 4. PERSONA GENERATION
# ============================================================================
@simulation_router.post("/personas/generate")
def generate_personas(personas_request: GeneratePersonasRequest):
    simulation_controller = SimulationController()

    try:
        personas = simulation_controller.generate_personas(
            topic=personas_request.topic,
            num_agents=personas_request.num_agents,
            custom_prompt=personas_request.custom_prompt,
            default_memory_type=personas_request.default_memory_type,
        )

        return success_response(
            message="Personas generated successfully.",
            data=personas,
            status_code=200,
        )

    except Exception as e:
        logger.exception(f"Failed to generate personas for topic '{personas_request.topic}'")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate personas: {e}",
        )


# ============================================================================
# 5. START SIMULATION
# ============================================================================
@simulation_router.post("/simulations/start")
def start_simulation(start_request: StartSimulationRequest):
    simulation_controller = SimulationController()

    sim_topic = start_request.topic
    sim_personas = [p.model_dump() for p in start_request.personas]
    sim_memory_strategy = start_request.memory_strategy.model_dump()
    sim_visibility_matrix = start_request.visibility_matrix

    try:
        simulation_id = simulation_controller.start_simulation(
            topic=sim_topic,
            personas=sim_personas,
            memory_strategy=sim_memory_strategy,
            visibility_matrix=sim_visibility_matrix,
        )

        return success_response(
            message="Simulation started successfully.",
            data={"simulation_id": simulation_id},
            status_code=201,
        )

    except Exception as e:
        logger.exception(f"Failed to start simulation for topic '{start_request.topic}'")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start simulation: {e}",
        )


# ============================================================================
# 6. NEXT TURN (EXECUTE 1 STEP AND RETURN TURN DATA)
# ============================================================================
@simulation_router.post("/simulations/{simulationId}/next-turn")
def execute_next_turn(simulationId: str):
    """
    Executes one turn in the deliberation engine and returns the resulting
    DiscussionTurn formatted for the frontend stream.
    """
    simulation_controller = SimulationController()

    simulation = simulation_controller.get_simulation_by_id(simulationId)
    if not simulation:
        raise HTTPException(
            status_code=404,
            detail=f"Simulation '{simulationId}' not found.",
        )

    personas = simulation.get("personas") or []
    total_rounds_limit = max(1, len(personas)) * 3

    current_round = simulation_controller.get_last_round_number(simulationId)
    if current_round >= total_rounds_limit:
        # Reached natural debate conclusion
        raise HTTPException(
            status_code=404,
            detail="Deliberation reached maximum rounds.",
        )

    try:
        step_result = simulation_controller.continue_simulation(
            simulation_id=simulationId,
            steps=1,
        )

        opinion = step_result.get("last_opinion") or {}
        stance_score = float(opinion.get("current_stance_score", 0.0))
        shift_mag = float(opinion.get("shift_magnitude") or 0.0)

        turn_payload = {
            "id": f"turn_{uuid.uuid4().hex[:8]}",
            "round_number": step_result.get("current_round", current_round + 1),
            "agent_name": step_result.get("current_speaker", personas[0]["name"]),
            "content": step_result.get("last_message", ""),
            "tools_called": [],
            "retrieved_sources": step_result.get("last_sources") or [],
            "opinion_snapshot": {
                "current_stance_score": stance_score,
                "shift_magnitude": shift_mag,
                "influencer": None,
                "reasoning": opinion.get("reasoning", "Turn completed."),
                "cfg": {
                    "guidance_scale_gamma": abs(shift_mag) * 0.1,
                    "shift_magnitude": shift_mag,
                    "guidance_vector": stance_score,
                    "dynamic": "Adaptive Evolution",
                },
            },
            "timestamp": datetime.now().strftime("%H:%M"),
        }

        return success_response(
            message="Turn executed successfully.",
            data=turn_payload,
            status_code=200,
        )

    except Exception as e:
        logger.exception(f"Failed executing next turn for simulation '{simulationId}'")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to execute next turn: {e}",
        )


# ============================================================================
# 7. SIMULATION ANALYTICS (SUPPORT BOTH GET & POST)
# ============================================================================
@simulation_router.get("/simulations/{simulation_id}/analytics")
def get_simulation_analytics_get(simulation_id: str):
    simulation_controller = SimulationController()

    simulation = simulation_controller.get_simulation_by_id(simulation_id)
    if not simulation:
        raise HTTPException(status_code=404, detail=f"Simulation '{simulation_id}' not found.")

    personas = simulation.get("personas") or []
    history = simulation_controller.get_current_discussion_history(simulation_id)

    # Build node positions and stances
    nodes = []
    for idx, p in enumerate(personas):
        latest_turn = next((h for h in reversed(history) if h.get("agent_name") == p["name"]), None)
        stance = 0.0
        if latest_turn and latest_turn.get("opinion_snapshot"):
            stance = float(latest_turn["opinion_snapshot"].get("current_stance_score", 0.0))

        # Pythonic 2-digit zero padding (replaces JavaScript .padStart)
        avatar_num = f"{(idx % 5) + 1:02d}"
        nodes.append({
            "id": f"agent-{idx}",
            "name": p["name"],
            "avatarUrl": f"/avatar/{avatar_num}.png",
            "currentStance": stance,
            "role": p.get("background", ""),
        })

    # Build edges and trajectory
    edges = []
    rounds_map: Dict[int, Dict[str, Any]] = {}
    sources: set[str] = set()

    for turn in history:
        r = int(turn.get("round_number") or 1)
        if r not in rounds_map:
            rounds_map[r] = {"round": f"R{r}"}
        opinion = turn.get("opinion_snapshot") or {}

        # Guaranteed string key to satisfy Pylance
        agent_name = str(turn.get("agent_name") or f"Agent_{r}")
        rounds_map[r][agent_name] = opinion.get("current_stance_score", 0.0)

        for src in turn.get("retrieved_sources") or []:
            if src:
                sources.add(str(src))

    analytics_payload = {
        "nodes": nodes,
        "edges": edges,
        "trajectory": list(rounds_map.values()),
        "persuasion_signals": [],
        "citations": list(sources),
    }

    return success_response(
        message="Analytics retrieved successfully.",
        data=analytics_payload,
        status_code=200,
    )


@simulation_router.post("/simulations/{simulation_id}/analytics")
def get_simulation_analytics_post(
    simulation_id: str,
    analytics_request: SimulationAnalyticsRequest,
):
    simulation_controller = SimulationController()

    try:
        analytics = simulation_controller.simulation_analytics(
            simulation_id=simulation_id,
            current_turns=[t.model_dump() for t in analytics_request.current_turns],
            current_personas=[p.model_dump() for p in analytics_request.current_personas],
        )
        return success_response(
            message="Simulation analytics calculated successfully.",
            data=analytics,
            status_code=200,
        )
    except Exception as e:
        logger.exception(f"Failed to calculate analytics for simulation '{simulation_id}'")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to calculate analytics: {e}",
        )


# ============================================================================
# 8. ADVANCE / CONTINUE SIMULATION
# ============================================================================
@simulation_router.post("/simulations/{simulation_id}/continue")
def continue_simulation_with_intervention(
    simulation_id: str,
    continue_request: ContinueSimulationRequest,
):
    simulation_controller = SimulationController()

    try:
        result = simulation_controller.continue_simulation(
            simulation_id=simulation_id,
            intervention=continue_request.intervention,
            steps=continue_request.steps,
        )
        return success_response(
            message="Simulation continued successfully.",
            data=result,
            status_code=200,
        )
    except Exception as e:
        logger.exception(f"Failed to continue simulation '{simulation_id}'")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to continue simulation: {e}",
        )


# ============================================================================
# 9. SEARCH / LIST ALL SIMULATIONS
# ============================================================================
@simulation_router.get("/simulations")
def list_simulations(
    topic_regex: Optional[str] = Query(
        None,
        description="Optional POSIX regex (case-insensitive) to filter simulations by topic.",
    ),
):
    simulation_controller = SimulationController()

    try:
        if topic_regex:
            simulations = simulation_controller.search_simulations_by_regex(topic_regex)
        else:
            simulations = simulation_controller.get_all_simulations()
    except Exception as e:
        if "invalid regular expression" in str(e).lower():
            raise HTTPException(status_code=400, detail=f"Invalid regex pattern: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch simulations: {e}")

    topics: dict[str, list] = {}
    for sim in simulations:
        topics.setdefault(sim["topic"], []).append(sim)

    data = {
        "total_simulations": len(simulations),
        "total_topics": len(topics),
        "topics": [{"topic": topic, "simulations": sims} for topic, sims in topics.items()],
    }

    message = (
        f"Found {len(simulations)} simulation(s) matching '{topic_regex}'."
        if topic_regex
        else f"Retrieved {len(simulations)} simulation(s)."
    )
    return success_response(message=message, data=data)


# ============================================================================
# 10. GET SINGLE SIMULATION
# ============================================================================
@simulation_router.get("/simulations/{simulation_id}")
def get_simulation(simulation_id: str):
    simulation_controller = SimulationController()

    simulation = simulation_controller.get_simulation_by_id(simulation_id)
    if simulation is None:
        raise HTTPException(status_code=404, detail=f"Simulation '{simulation_id}' not found.")
    return success_response(message="Simulation retrieved.", data=simulation)


# ============================================================================
# 11. EVIDENCE SEARCH
# ============================================================================
@simulation_router.get("/evidence")
def get_evidence(
    query: Optional[str] = Query(None, description="Semantic search question"),
    document_url: Optional[str] = Query(None, description="Exact document URL to inspect"),
    top_k: int = Query(3, ge=1, le=20, description="Number of chunks to retrieve"),
):
    if not query and not document_url:
        raise HTTPException(status_code=400, detail="Provide at least a 'query' or a 'document_url' parameter.")

    try:
        result = search_ai_policy(query=query, document_url=document_url, top_k=top_k)
    except ConnectionError as e:
        logger.error(f"Knowledge base connection error: {e}")
        return fail_response(
            message=f"No Evidence retrieved: {e}",
            status_code=503,
        )
    except Exception as e:
        logger.error(f"Evidence retrieval failed: {e}")
        return fail_response(
            message=f"Evidence retrieval failed: {e}",
            status_code=500,
        )

    return success_response(
        message="Evidence retrieved.",
        data={"query": query, "document_url": document_url, "top_k": top_k, "result": result},
    )
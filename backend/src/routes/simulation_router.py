import json
import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from src.agent.tools.retriever import search_ai_policy
from src.controllers.analytics_controller import AnalyticsController
from src.controllers.simulation_controller import SimulationController
from src.routes.dependencies import get_analytics_controller, get_simulation_controller
from src.routes.schemas.simulation import (
    GeneratePersonasRequest,
    StartSimulationRequest,
)
from src.utils.response import fail_response, success_response

logger = logging.getLogger("uvicorn")
simulation_router = APIRouter(tags=["simulations"])


# ============================================================================
# 1. LIVE EXECUTION & SSE STREAMING
# ============================================================================
@simulation_router.get("/simulations/{simulationId}/stream-turn")
def stream_turn(
    simulationId: str,
    intervention: Optional[str] = Query(None, description="Human moderator steering input"),
    sim_ctrl: SimulationController = Depends(get_simulation_controller),
):
    """
    Streams turn execution via SSE:
    Emits speaker selection, thinking tokens, generation tokens, tool usage,
    and finishes with 'turn_complete' carrying the updated analytics.
    """
    if not sim_ctrl.repo.get_simulation_by_id(simulationId):
        raise HTTPException(status_code=404, detail=f"Simulation '{simulationId}' not found.")

    def event_generator():
        try:
            for event in sim_ctrl.stream_discussion_turn(simulationId, intervention=intervention):
                event_name = event.get("type", "message")
                yield f"event: {event_name}\ndata: {json.dumps(event)}\n\n"
        except Exception as e:
            logger.exception("Error during turn streaming")
            yield f"event: error\ndata: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@simulation_router.post("/simulations/start")
def start_simulation(
    start_req: StartSimulationRequest,
    stream: Optional[bool] = Query(False, description="Stream Turn 1 immediately via SSE"),
    sim_ctrl: SimulationController = Depends(get_simulation_controller),
):
    """Initializes debate; optionally begins streaming Turn 1 immediately."""
    try:
        sim_id = sim_ctrl.start_simulation(
            topic=start_req.topic,
            personas=[p.model_dump() for p in start_req.personas],
            memory_strategy=start_req.memory_strategy.model_dump(),
            visibility_matrix=start_req.visibility_matrix,
        )

        if not (start_req.stream or stream):
            return success_response(
                message="Simulation started successfully.",
                data={"simulation_id": sim_id},
                status_code=201,
            )

        def event_generator():
            init_msg = json.dumps({"type": "simulation_started", "simulation_id": sim_id, "topic": start_req.topic})
            yield f"event: simulation_started\ndata: {init_msg}\n\n"
            try:
                for event in sim_ctrl.stream_discussion_turn(sim_id):
                    yield f"event: {event.get('type', 'message')}\ndata: {json.dumps(event)}\n\n"
            except Exception as exc:
                yield f"event: error\ndata: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )
    except Exception as e:
        logger.exception("Failed to start simulation")
        raise HTTPException(status_code=500, detail=str(e))


@simulation_router.post("/simulations/{simulationId}/next-turn")
def execute_next_turn(
    simulationId: str,
    sim_ctrl: SimulationController = Depends(get_simulation_controller),
):
    """Executes a single turn synchronously, returning the turn and updated analytics."""
    try:
        result = sim_ctrl.execute_next_turn(simulationId)
        return success_response(message="Turn executed successfully.", data=result, status_code=200)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Failed executing next turn")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# 2. ANALYTICS & REPLAY (GET ONLY)
# ============================================================================
@simulation_router.get("/simulations/{simulation_id}/analytics")
def get_simulation_analytics(
    simulation_id: str,
    round_number: Optional[int] = Query(None, description="Slice state at a specific round for replay"),
    analytics_ctrl: AnalyticsController = Depends(get_analytics_controller),
):
    """
    Returns analytics for visualizations (nodes, edges, trajectory, agreement, citations).
    Pass ?round_number=N to reconstruct debate state at round N for replay mode.
    """
    try:
        analytics = analytics_ctrl.get_simulation_analytics(simulation_id, round_number=round_number)
        return success_response(message="Analytics retrieved successfully.", data=analytics, status_code=200)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Failed to retrieve analytics")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# 3. PERSONAS, HISTORY, & EVIDENCE
# ============================================================================
@simulation_router.post("/personas/generate")
def generate_personas(
    req: GeneratePersonasRequest,
    sim_ctrl: SimulationController = Depends(get_simulation_controller),
):
    try:
        personas = sim_ctrl.generate_personas(
            topic=req.topic,
            num_agents=req.num_agents,
            custom_prompt=req.custom_prompt,
            default_memory_type=req.default_memory_type,
        )
        return success_response(message="Personas generated successfully.", data=personas, status_code=200)
    except Exception as e:
        logger.exception("Failed to generate personas")
        raise HTTPException(status_code=500, detail=str(e))


@simulation_router.get("/simulations/history-list")
def get_simulation_history(
    sim_ctrl: SimulationController = Depends(get_simulation_controller),
):
    try:
        simulations = sim_ctrl.repo.get_all_simulations()
        formatted = []
        for s in simulations:
            turn_count = s.get("turn_count", 0)
            personas = s.get("personas") or []
            created_at = s.get("created_at")

            category = "Today"
            if created_at and isinstance(created_at, datetime):
                days = (datetime.now() - created_at).days
                if days == 1:
                    category = "Yesterday"
                elif 2 <= days <= 7:
                    category = f"{days} days ago"
                elif days > 7:
                    category = "Older"

            formatted.append({
                "id": s["simulation_id"],
                "title": s["topic"],
                "topic": s["topic"],
                "category": category,
                "agentsCount": len(personas),
                "roundsCount": max(1, turn_count // max(1, len(personas))),
                "turn_count": turn_count,
                "status": s.get("status", "completed"),
            })
        return success_response(message="History retrieved.", data=formatted, status_code=200)
    except Exception as e:
        logger.exception("Failed to fetch history")
        raise HTTPException(status_code=500, detail=str(e))


@simulation_router.get("/simulations/{simulation_id}")
def get_simulation(
    simulation_id: str,
    sim_ctrl: SimulationController = Depends(get_simulation_controller),
    analytics_ctrl: AnalyticsController = Depends(get_analytics_controller),
):
    """Single unified endpoint: retrieves metadata, all debate turns, and analytics together."""
    sim = sim_ctrl.repo.get_simulation_by_id(simulation_id)
    if not sim:
        raise HTTPException(status_code=404, detail=f"Simulation '{simulation_id}' not found.")

    if "created_at" in sim and isinstance(sim["created_at"], datetime):
        sim["created_at"] = sim["created_at"].isoformat()

    # 1. Fetch & sanitize all discussion turns (1 query)
    raw_history = sim_ctrl.repo.get_discussion_history(simulation_id)
    turns = []
    for row in raw_history:
        turn = dict(row)
        if "id" in turn:
            turn["id"] = str(turn["id"])
        if "created_at" in turn and isinstance(turn["created_at"], datetime):
            turn["created_at"] = turn["created_at"].isoformat()
        if isinstance(turn.get("opinion_snapshot"), str):
            try:
                turn["opinion_snapshot"] = json.loads(turn["opinion_snapshot"])
            except Exception:
                pass
        if isinstance(turn.get("retrieved_sources"), str):
            try:
                turn["retrieved_sources"] = json.loads(turn["retrieved_sources"])
            except Exception:
                pass
        turns.append(turn)

    # 2. Fetch analytics (served in ~5ms from cache, passing already queried objects)
    try:
        analytics = analytics_ctrl.get_simulation_analytics(
            simulation_id=simulation_id,
            sim_data=sim,
            history_data=raw_history,
        )
    except Exception as e:
        logger.warning(f"Could not retrieve analytics for {simulation_id}: {e}")
        analytics = {
            "nodes": [],
            "edges": [],
            "trajectory": [],
            "agreement": [],
            "influence": {},
            "persuasion_signals": [],
            "citations": [],
            "key_findings": [],
        }

    sim["turns"] = turns
    sim["analytics"] = analytics

    return success_response(message="Simulation retrieved.", data=sim)


@simulation_router.delete("/simulations/{simulation_id}")
def delete_simulation(
    simulation_id: str,
    sim_ctrl: SimulationController = Depends(get_simulation_controller),
):
    deleted = sim_ctrl.repo.delete_simulation(simulation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Simulation '{simulation_id}' not found.")
    return success_response(message="Simulation deleted.", data={"simulation_id": simulation_id})


@simulation_router.get("/topics/predefined")
def list_predefined_topics():
    topics = [
        {
            "id": "topic-1",
            "title": "Should governments mandate hardware-level kill-switches for frontier open-source AI?",
            "tag": "Frontier Security",
            "description": "Dual-use weight proliferation, foundry locks, and existential risk prevention.",
        },
        {
            "id": "topic-2",
            "title": "EU AI Act Article 51: Should training clusters >10^26 FLOPs face strict third-party audit vetoes?",
            "tag": "Regulatory Compliance",
            "description": "European single-market innovation vs. systemic catastrophe mitigation.",
        }
    ]
    return success_response(message="Predefined topics retrieved.", data=topics, status_code=200)


@simulation_router.get("/evidence")
def get_evidence(
    query: Optional[str] = Query(None, description="Semantic policy question"),
    document_url: Optional[str] = Query(None, description="Specific document URL"),
    top_k: int = Query(3, ge=1, le=20),
):
    if not query and not document_url:
        raise HTTPException(status_code=400, detail="Provide either 'query' or 'document_url'.")
    try:
        results = search_ai_policy(query=query, document_url=document_url, top_k=top_k)
        return success_response(message="Evidence retrieved.", data={"results": results})
    except Exception as e:
        return fail_response(message=f"Retrieval failed: {e}", status_code=500)
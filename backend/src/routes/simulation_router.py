import logging
from typing import Optional
from backend.src.controllers import simulation_controller
from fastapi import APIRouter, HTTPException, Query, Depends

from src.agent.tools.retriever import search_ai_policy
from ..utils.response import success_response, fail_response
from src.clients.postgres import PostgresClient
from .dependencies import get_pg_client
from src.controllers.simulation_controller import SimulationController
from .schemas.simulation import (ContinueSimulationRequest, DebateHistoryItem, DiscussionTurn 
                                 ,GeneratePersonasRequest, Persona, SimulationAnalyticsRequest, StartSimulationRequest)


logger = logging.getLogger("uvicorn")
simulation_router = APIRouter(tags=["simulations"])



@simulation_router.get("/topics/predefined")
def list_predefined_topics():
    pass




@simulation_router.get("/simulations/history-list")
def get_initial_history():

    simulation_controller = SimulationController()

    try:
        simulations = simulation_controller.get_all_simulations()

        # FIX: was `[{ DebateHistoryItem(...) }]` — a set containing one item,
        # not a list — and read `simulation["id"]` which doesn't exist
        # (get_all_simulations() rows are keyed "simulation_id").
        history = [
            DebateHistoryItem(
                id=simulation["simulation_id"],
                topic=simulation["topic"],
                status=simulation.get("status"),
                created_at=simulation.get("created_at"),
                turn_count=simulation.get("turn_count"),
            )
            for simulation in simulations
        ]

        return success_response(
            message="Simulation history retrieved.",
            data={"history": history},
            status_code=200,
        )

    except Exception as e:
        logger.exception(
            "Failed to fetch simulation history"
        )

        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch history: {e}",
        )




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
        logger.exception(
            f"Failed to delete simulation '{id}'"
        )

        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete simulation: {e}",
        )




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

    except Exception as e:
        logger.exception(
            f"Failed to generate personas for topic '{personas_request.topic}'"
        )

        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate personas: {e}",
        )

    return success_response(
        message="Personas generated successfully.",
        data={"personas": personas},
        status_code=200,
    )




@simulation_router.post("/simulations/start")
def start_simulation(start_request: StartSimulationRequest):
    simulation_controller = SimulationController()

    sim_topic = start_request.topic
    # FIX: personas were pydantic model instances; create_simulation() does
    # json.dumps(personas) directly, which fails on pydantic models.
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

    except Exception as e:
        logger.exception(
            f"Failed to start simulation for topic '{start_request.topic}'"
        )

        raise HTTPException(
            status_code=500,
            detail=f"Failed to start simulation: {e}",
        )

    return success_response(
        message="Simulation started successfully.",
        data={"simulation_id": simulation_id},
        status_code=201,
    )


# FIX: path used JS template-literal syntax `${simulationId}` instead of a
# real FastAPI path param `{simulationId}` — it would never match a request.
# Also renamed the function (it shadowed the module-level `continue_simulation`
# import and doesn't actually continue anything — next_turn() is preview-only,
# it doesn't call the LLM or persist a turn; use /continue for that).
@simulation_router.post("/simulations/{simulationId}/next-turn")
def preview_next_turn(simulationId: str):
    simulation_controller = SimulationController()
    next_simulation = simulation_controller.next_turn(simulation_id=simulationId)

    if not next_simulation:
        raise HTTPException(
            status_code=404,
            detail=f"Simulation '{simulationId}' not found or no more turns available.",
        )
    return success_response(
        message="Next turn previewed successfully.",
        data={"next_turn": next_simulation},
        status_code=200,
    )



@simulation_router.post("/simulations/{simulation_id}/analytics")
def get_simulation_analytics(
    simulation_id: str,
    analytics_request: SimulationAnalyticsRequest,
):
    simulation_controller = SimulationController()

    try:
        # FIX: current_turns/current_personas are lists of pydantic models
        # (DiscussionTurn/Persona). simulation_analytics() calls dict-style
        # `.get(...)` on each item, which pydantic BaseModel doesn't support.
        analytics = simulation_controller.simulation_analytics(
            simulation_id=simulation_id,
            current_turns=[t.model_dump() for t in analytics_request.current_turns],
            current_personas=[p.model_dump() for p in analytics_request.current_personas],
        )

    except Exception as e:
        logger.exception(
            f"Failed to get analytics for simulation '{simulation_id}'"
        )

        raise HTTPException(
            status_code=500,
            detail=f"Failed to get simulation analytics: {e}",
        )

    return success_response(
        message="Simulation analytics retrieved successfully.",
        data=analytics,
        status_code=200,
    )




@simulation_router.post("/simulations/{simulation_id}/continue")
def continue_simulation_with_intervention(
    simulation_id: str,
    continue_request: ContinueSimulationRequest,
):
  
    simulation_controller = SimulationController()

    sim_intervention = continue_request.intervention
    sim_steps = continue_request.steps

    try:
        result = simulation_controller.continue_simulation(
            simulation_id=simulation_id,
            intervention=sim_intervention,
            steps=sim_steps,
        )

    except Exception as e:
        logger.exception(
            f"Failed to continue simulation '{simulation_id}'"
        )

        raise HTTPException(
            status_code=500,
            detail=f"Failed to continue simulation: {e}",
        )

    return success_response(
        message="Simulation continued successfully.",
        data=result,
        status_code=200,
    )

def list_simulations(
    topic_regex: Optional[str] = Query(
        None,
        description="Optional POSIX regex (case-insensitive) to filter simulations by topic, "
                    "e.g. '^AI (Ethics|Regulation)' or 'deepfake'.",
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


@simulation_router.get("/simulations/{simulation_id}")
def get_simulation(simulation_id: str):
    simulation_controller = SimulationController()

    simulation = simulation_controller.get_simulation_by_id(simulation_id)
    if simulation is None:
        raise HTTPException(status_code=404, detail=f"Simulation '{simulation_id}' not found.")
    return success_response(message="Simulation retrieved.", data=simulation)




@simulation_router.get("/evidence")
def get_evidence(
    query: Optional[str] = Query(None, description="Semantic search question, e.g. 'High-Risk AI obligations'"),
    document_url: Optional[str] = Query(None, description="Exact document URL to inspect or restrict search to"),
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
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Evidence retrieval failed: {e}")
        return fail_response(
            message=f"Evidence retrieval failed: {e}",
            status_code=500,
            error=str(e),
        )

    return success_response(
        message="Evidence retrieved.",
        data={"query": query, "document_url": document_url, "top_k": top_k, "result": result},
    )
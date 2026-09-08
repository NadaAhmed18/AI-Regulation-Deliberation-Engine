import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Depends

from src.agent.tools.retriever import search_ai_policy
from .response import success_response, fail_response
from src.clients.postgres import PostgresClient
from .dependencies import get_pg_client

logger = logging.getLogger("uvicorn")
simulation_router = APIRouter(tags=["simulations"])


@simulation_router.get("/simulations")
def list_simulations(
    topic_regex: Optional[str] = Query(
        None,
        description="Optional POSIX regex (case-insensitive) to filter simulations by topic, "
                    "e.g. '^AI (Ethics|Regulation)' or 'deepfake'.",
    ),
    pg: PostgresClient = Depends(get_pg_client),
):
 
    try:
        if topic_regex:
            simulations = pg.search_simulations_by_regex(topic_regex)
        else:
            simulations = pg.get_all_simulations()
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
def get_simulation(
    simulation_id: str,
    pg: PostgresClient = Depends(get_pg_client),
):
    simulation = pg.get_simulation_by_id(simulation_id)
    if simulation is None:
        raise HTTPException(status_code=404, detail=f"Simulation '{simulation_id}' not found.")
    return success_response(message="Simulation retrieved.", data=simulation)


@simulation_router.delete("/simulations/{simulation_id}")
def delete_simulation(
    simulation_id: str,
    pg: PostgresClient = Depends(get_pg_client),
):
    try:
        deleted = pg.delete_simulation(simulation_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete simulation: {e}")

    if not deleted:
        raise HTTPException(status_code=404, detail=f"Simulation '{simulation_id}' not found.")

    return success_response(
        message="Simulation deleted.",
        data={"simulation_id": simulation_id},
    )


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
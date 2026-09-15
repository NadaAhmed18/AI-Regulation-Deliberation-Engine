import logging
from fastapi import APIRouter
from src.utils.response import success_response, fail_response
from src.controllers.repository.base_repository import BaseRepository

logger = logging.getLogger("uvicorn")
base_router = APIRouter(tags=["health"])


@base_router.get("/ping")
def ping():
    return success_response(
        message="Application is alive.",
        data={"status": "ok"},
        status_code=200,
    )


@base_router.get("/health")
def health_check():
    """Validates the health of both PostgreSQL and Neo4j via the unified BaseRepository."""
    services: dict[str, str] = {}
    repo = BaseRepository()

    # PostgreSQL check
    try:
        with repo.get_cursor() as cur:
            cur.execute("SELECT 1 AS ping")
        services["postgres"] = "ok"
    except Exception as e:
        logger.error(f"PostgreSQL health check failed: {e}")
        services["postgres"] = f"error: {str(e)}"

    # Neo4j check
    try:
        repo.run_neo4j_query("RETURN 1 AS ping")
        services["neo4j"] = "ok"
    except Exception as e:
        logger.error(f"Neo4j health check failed: {e}")
        services["neo4j"] = f"error: {str(e)}"

    is_healthy = all(status == "ok" for status in services.values())
    message = "All services are healthy." if is_healthy else "One or more services are unhealthy."

    response_data = {
        "status": "healthy" if is_healthy else "unhealthy",
        "postgres": services["postgres"] == "ok",
        "neo4j": services["neo4j"] == "ok",
        "services": services,
    }

    if is_healthy:
        return success_response(
            message=message,
            data=response_data,
            status_code=200,
        )

    return fail_response(
        message=message,
        data=response_data,
        status_code=503,
    )
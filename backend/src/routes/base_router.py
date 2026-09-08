import logging
from fastapi import APIRouter, Depends
from .response import success_response, fail_response
from src.clients.postgres import PostgresClient
from src.clients.neo4j import Neo4jClient
from .dependencies import get_pg_client, get_neo4j_client

logger = logging.getLogger("uvicorn")
base_router = APIRouter(tags=["health"])


@base_router.get("/health")
def health_check(
    pg: PostgresClient = Depends(get_pg_client),
    neo4j: Neo4jClient = Depends(get_neo4j_client),
):
  
    services: dict[str, str] = {}

    try:
        with pg.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 AS ping")
        services["postgres"] = "ok"
    except Exception as e:
        logger.error(f"PostgreSQL health check failed: {e}")
        services["postgres"] = f"error: {e}"

    try:
        neo4j.execute_query("RETURN 1 AS ping")
        services["neo4j"] = "ok"
    except Exception as e:
        logger.error(f"Neo4j health check failed: {e}")
        services["neo4j"] = f"error: {e}"

    is_healthy = all(v == "ok" for v in services.values())
    message = "All services are healthy." if is_healthy else "One or more services are unhealthy."

    if is_healthy:
        return success_response(
            message=message,
            data={"services": services},
            status_code=200,
        )
    else:
        return fail_response(
            message=message,
            data={"services": services},
            status_code=503,
        )
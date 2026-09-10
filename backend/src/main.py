import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

from src.clients.postgres import PostgresClient
from src.clients.neo4j import Neo4jClient

logger = logging.getLogger("uvicorn")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database clients on startup...")

    app.state.pg_client = PostgresClient()
    app.state.neo4j_client = Neo4jClient()

    logger.info("All database clients initialized and ready.")
    yield

    logger.info("Application shutting down: Closing database pools...")
    app.state.pg_client = None
    app.state.neo4j_client.close()
    logger.info("All database connections gracefully closed.")


app = FastAPI(lifespan=lifespan)


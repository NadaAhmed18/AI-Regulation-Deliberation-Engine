# python -m uvicorn src.main:app --reload --host 127.0.0.1 --port 8000
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

from src.clients.postgres import PostgresClient
from src.clients.neo4j import Neo4jClient
from src.routes.base_router import base_router
from src.routes.simulation_router import simulation_router

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


app = FastAPI(title="AI Regulation Engine API", lifespan=lifespan)

# Enable CORS for Next.js development and production origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5000",
        "http://127.0.0.1:5000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. Mount under /api (matches frontend apiClient baseURL default)
api_router = APIRouter(prefix="/api")
api_router.include_router(base_router)
api_router.include_router(simulation_router)
app.include_router(api_router)

# 2. Also mount directly at root for direct calls
app.include_router(base_router)
app.include_router(simulation_router)
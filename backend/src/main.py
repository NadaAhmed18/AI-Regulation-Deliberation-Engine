# python -m uvicorn src.main:app --reload --port 8000
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

from src.controllers.repository.base_repository import BaseRepository
from src.controllers.simulation_controller import SimulationController
from src.routes.base_router import base_router
from src.routes.simulation_router import simulation_router

logger = logging.getLogger("uvicorn")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database connections via BaseRepository...")
    # Initialize the singleton repository (connects to PG and Neo4j)
    repo = BaseRepository()
    logger.info("Database clients initialized and ready.")

    logger.info("Eagerly loading AI models (ONNX NLI Grader)...")
    # Instantiating the controller initializes the DiscussionEngine and loads the ONNX model into memory
    SimulationController()
    logger.info("AI models loaded and ready.")

    yield

    logger.info("Application shutting down: Closing database pools...")
    # Gracefully shut down both connections
    repo.close()
    logger.info("All database connections gracefully closed.")


app = FastAPI(title="AI Regulation Engine API", lifespan=lifespan)

# --- DYNAMIC CORS CONFIGURATION ---
# Allows localhost + any custom domain/IP specified in .env, or allows all origins if wildcarded
raw_origins = os.getenv("ALLOWED_ORIGINS", "*")
if raw_origins == "*":
    allow_origins = ["*"]
else:
    allow_origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. Mount under /api (matches frontend apiClient baseURL default)
api_router = APIRouter(prefix="/api")
api_router.include_router(base_router)
api_router.include_router(simulation_router)
app.include_router(api_router)

# 2. Mount directly at root for easy direct calls / testing
app.include_router(base_router)
app.include_router(simulation_router)
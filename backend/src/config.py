import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ==============================================================================
# 1. DIRECTORY & PATH CONFIGURATION
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent.parent  # Points to 'backend/'
PROMPTS_DIR = BASE_DIR / "prompts"
OUTPUT_DIR = BASE_DIR / "outputs"
DATA_DIR = BASE_DIR / "data"

# Ensure runtime directories exist
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)


# ==============================================================================
# 2. LLM & PROVIDER CONFIGURATION
# ==============================================================================
DEFAULT_PROVIDER = os.getenv("DEFAULT_PROVIDER", "openrouter").lower()  # "openrouter" or "huggingface"
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "deepseek/deepseek-v4-flash")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")


# ==============================================================================
# 3. EMBEDDING & VECTOR RETRIEVAL
# ==============================================================================
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "voyage").lower()  # "voyage" or "hf"
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "voyage-3.5-lite")
VECTOR_DIMENSION = int(os.getenv("VECTOR_DIMENSION", 1024))
VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY", "")


# ==============================================================================
# 4. RAG INGESTION & SCRAPING PARAMETERS
# ==============================================================================
MAX_CHARS = 12000          # Maximum characters per chunk before splitting
MAX_CHUNKS = 2             # Hard cap on chunks extracted per document
SLIDING_SENTENCES = 2      # Overlapping sentences between consecutive chunks
MAX_RELATED_LINKS = 20     # FlashRank top-K limit for internal cross-document links


# ==============================================================================
# 5. MULTI-AGENT SIMULATION & REACT SETTINGS
# ==============================================================================
MAX_REACT_STEPS = int(os.getenv("MAX_REACT_STEPS", 5))       # Max autonomous tool calls per agent turn
DEFAULT_ROUNDS = int(os.getenv("DEFAULT_ROUNDS", 3))         # Default debate rounds
DEFAULT_NUM_AGENTS = int(os.getenv("DEFAULT_NUM_AGENTS", 3)) # Default number of generated personas

# ==============================================================================
# 5b. STANCE GRADING ENGINE
# ==============================================================================
# "llm" -> OpinionGrader (LLM-based, uses agent persona + reasoning text)
# "nli" -> DebertaStanceGrader (local NLI cross-encoder, no API cost/latency)
# Default stays "llm" so existing deployments don't silently start
# downloading a ~1.6GB model or switching scoring behavior. Set
# STANCE_GRADER_ENGINE=nli in .env to make the local grader the live
# engine. See docs/NLI-Grader-Optimizations.md and
# docs/Influence-Tracking.md for the tradeoffs.
STANCE_GRADER_ENGINE = os.getenv("STANCE_GRADER_ENGINE", "llm").lower()

# ==============================================================================
# 6. EXTERNAL TOOLS & WEB SEARCH
# ==============================================================================
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
MAX_SEARCH_RESULTS = 5     # Max external search results from Tavily


# ==============================================================================
# 7. DATABASE CONNECTIONS
# ==============================================================================
# PostgreSQL (Relational Discussion State & Analytics)
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://langfuse:postgres_langfuse123@localhost:5432/main"
)

# Neo4j (Graph Knowledge Base & Vector Index)
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")

# Langfuse (Observability & Analytics)
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_BASE_URL = os.getenv("LANGFUSE_BASE_URL", "http://localhost:3000")

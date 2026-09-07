import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Embedding Model
VECTOR_DIMENSION = 1024 # 1024 (default), 256, 512, 2048
EMBEDDING_MODEL = "voyage-3.5-lite"

# Chunking Parameters
MAX_CHARS = 12000          # Max characters per chunk (staying safely below model token limits)
MAX_CHUNKS = 2            # Stop extracting if we reach this many chunks per document
SLIDING_SENTENCES = 2      # Overlap chunks by this many sentences to preserve context

# Link Reranking Parameters
MAX_RELATED_LINKS = 20  # Only keep the top X most relevant links per document

# Prompt Template Paths
DEFAULT_TEMPLATE_PATH = Path("prompts/initial_opinion.txt")

# Output Directory
OUTPUT_DIR = Path("outputs")
PROMPTS_DIR = Path("prompts")

# Default LLM Provider and Model
DEFAULT_PROVIDER = "openrouter"
DEFAULT_MODEL = "deepseek/deepseek-v4-flash"

# API Keys (set in .env or environment variables)
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
MAX_SEARCH_RESULTS = 5

# Other
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/ai_regulation")
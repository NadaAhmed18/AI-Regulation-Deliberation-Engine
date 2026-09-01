from pathlib import Path
from .secretconfig import OPENROUTER_APIKEY

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
# Relative to the working directory. Scripts should always be run as
# modules from the `backend/` root (e.g. `python -m src.utils.prompt_builder`),
# so this resolves natively without any sys.path or __file__ manipulation.
DEFAULT_TEMPLATE_PATH = Path("prompts/initial_opinion.txt")

PERSONAS_DIR = Path("personas")
OUTPUT_DIR = Path("outputs")
OUTPUT_FILE = Path(OUTPUT_DIR / "initial_opinions.json")

DEFAULT_PROVIDER = "openrouter"
DEFAULT_MODEL = "deepseek/deepseek-v4-flash"

OPENROUTER_BASE_URLS = {
    "openrouter": "https://openrouter.ai/api/v1",
}

OPRNROUTER_API={
    "OPENROUTER_API_KEY":OPENROUTER_APIKEY
}



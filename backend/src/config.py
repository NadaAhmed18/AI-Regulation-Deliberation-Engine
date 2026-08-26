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
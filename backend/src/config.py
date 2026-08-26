from dotenv import load_dotenv

load_dotenv()

# Embedding Model
VECTOR_DIMENSION = 1024 # 1024 (default), 256, 512, 2048
EMBEDDING_MODEL = "voyage-context-4"
MAX_CHARS=12_000
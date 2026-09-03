# python -m src.agent.tools.retriever
from src.clients.neo4j import Neo4jClient
from src.utils.embedder import Embedder
from src.config import EMBEDDING_MODEL

# ------------------------------------------------------------------------------
# 1. Module-Level Clients (Lazy or Singleton initialization)
# ------------------------------------------------------------------------------
db = Neo4jClient()
embedder = Embedder(model_name=EMBEDDING_MODEL)
INDEX_NAME = "chunk_vector_index"

# ------------------------------------------------------------------------------
# 2. Tool Schema Definition (For the LLM)
# ------------------------------------------------------------------------------
RETRIEVER_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_ai_policy",
        "description": "Use this tool to search the knowledge database for factual information regarding AI regulations, laws, democratic values, and stakeholder opinions.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search question or topic (e.g., 'What are the rules for High-Risk AI?')."
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of sources to retrieve. Defaults to 3."
                }
            },
            "required": ["query"]
        }
    }
}

# ------------------------------------------------------------------------------
# 3. Tool Function Implementation
# ------------------------------------------------------------------------------
def search_ai_policy(query: str, top_k: int = 3) -> str:
    """Executes a vector search against Neo4j. Fails loudly if DB is down."""
    print(f"\n[Agent Tool] 🔍 Searching knowledge base for: '{query}'")
    
    # 1. Connection Check
    try:
        # Quick ping to check if Neo4j is alive
        db.execute_query("RETURN 1 AS ping")
    except Exception as e:
        error_msg = (
            f"\n❌ [CRITICAL ERROR] Cannot connect to Neo4j! Is the database running?\n"
            f"Details: {e}\n"
            f"👉 Run 'python -m src.scripts.import_db_from_json' after starting Neo4j."
        )
        print(error_msg)
        # Raise instead of silently hiding so the developer knows immediately
        raise ConnectionError(error_msg)

    # 2. Convert text to vector
    try:
        query_embedding = embedder.embed([query], is_query=True)[0].tolist()
    except Exception as e:
        print(f"\n❌ [ERROR] Embedding generation failed: {e}")
        raise RuntimeError(f"Embedding failed. Check VOYAGE_API_KEY: {e}")

    # 3. Query Neo4j
    cypher_query = """
    CALL db.index.vector.queryNodes($index_name, $top_k, $query_embedding)
    YIELD node AS chunk, score
    MATCH (doc:Document)-[:HAS_CHUNK]->(chunk)
    RETURN 
        chunk.text AS text, 
        doc.document_url AS source_url, 
        doc.domain AS domain,
        score AS similarity_score
    ORDER BY score DESC
    """
    
    parameters = {
        "index_name": INDEX_NAME,
        "top_k": top_k,
        "query_embedding": query_embedding
    }

    results = db.execute_query(cypher_query, parameters)
    
    # 4. Format output specifically for an LLM to read easily
    if not results:
        print(f"⚠️ [WARNING] Neo4j returned 0 results for query: '{query}'. Did you populate the DB?")
        return "No relevant information found in the database for this query."
        
    llm_formatted_response = "Here is the retrieved context from the database:\n\n"
    for i, r in enumerate(results, 1):
        llm_formatted_response += f"--- SOURCE {i} ---\n"
        llm_formatted_response += f"Domain: {r['domain']}\n"
        llm_formatted_response += f"URL: {r['source_url']}\n"
        llm_formatted_response += f"Relevance Score: {round(r['similarity_score'], 4)}\n"
        llm_formatted_response += f"Content:\n{r['text']}\n\n"
        
    return llm_formatted_response

# ==========================================
# Testing the Tool wrapper
# ==========================================
if __name__ == "__main__":
    # Simulate an LLM calling the tool
    agent_query = "What is the EU AI Act and what does it say about High-Risk AI?"
    response = search_ai_policy(query=agent_query, top_k=2)
    
    print("Output sent to LLM:\n")
    print(response)
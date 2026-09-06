# python -m src.agent.tools.retriever
from typing import Optional
from src.clients.neo4j import Neo4jClient
from src.utils.embedder import Embedder
from src.config import EMBEDDING_MODEL

db = Neo4jClient()
embedder = Embedder(model_name=EMBEDDING_MODEL)
INDEX_NAME = "chunk_vector_index"


def search_ai_policy(query: Optional[str] = None, document_url: Optional[str] = None, top_k: int = 3) -> str:
    """Executes a search against Neo4j knowledge chunks by semantic query or document URL."""
    if not query and not document_url:
        return "Please provide either a search 'query' or a 'document_url'."

    clean_url = document_url.strip().lower().rstrip("/") if document_url else None
    print(f"\n[Agent Tool] 🔍 Searching knowledge base (query='{query}', url='{clean_url}')")

    try:
        db.execute_query("RETURN 1 AS ping")
    except Exception as e:
        raise ConnectionError(f"Cannot connect to Neo4j database: {e}")

    # =========================================================================
    # CASE 1: Direct Document Lookup -> Stitch ALL chunks together in order
    # =========================================================================
    if clean_url and not query:
        cypher_query = """
        MATCH (doc:Document)
        WHERE toLower(doc.document_url) = $url 
           OR toLower(doc.document_url) = $url + '/'
        MATCH (doc)-[:HAS_CHUNK]->(chunk:Chunk)
        WITH doc, chunk
        ORDER BY chunk.chunk_index ASC
        RETURN 
            doc.document_url AS source_url,
            doc.related_documents AS related_sources,
            collect(chunk.text) AS all_chunk_texts
        """
        results = db.execute_query(cypher_query, {"url": clean_url})
        if not results:
            return f"No document found for URL: {clean_url}"

        row = results[0]
        # Combine all chunk texts into one complete document
        full_document_text = "\n\n".join(row["all_chunk_texts"])

        related_list = row.get("related_sources") or []
        related_str = "\n  - " + "\n  - ".join(related_list[:5]) if related_list else " None found"

        return (
            f"--- FULL DOCUMENT CONTENT ---\n"
            f"URL: {row['source_url']}\n"
            f"Related Sources:{related_str}\n\n"
            f"Content:\n{full_document_text}\n"
        )

    # =========================================================================
    # CASE 2: Semantic Vector Search -> Return Top-K relevant chunks
    # =========================================================================
    else:
        try:
            assert query, "Query must be provided for semantic search."
            query_embedding = embedder.embed([query], is_query=True)[0].tolist()
        except Exception as e:
            raise RuntimeError(f"Embedding generation failed: {e}")

        cypher_query = """
        CALL db.index.vector.queryNodes($index_name, $fetch_k, $query_embedding)
        YIELD node AS chunk, score
        MATCH (doc:Document)-[:HAS_CHUNK]->(chunk)
        WHERE $url IS NULL 
           OR toLower(doc.document_url) = $url 
           OR toLower(doc.document_url) = $url + '/'
        RETURN 
            chunk.text AS text, 
            doc.document_url AS source_url, 
            doc.related_documents AS related_sources
        ORDER BY score DESC
        LIMIT $top_k
        """
        results = db.execute_query(
            cypher_query,
            {
                "index_name": INDEX_NAME,
                "fetch_k": top_k if not clean_url else 50,
                "top_k": top_k,
                "query_embedding": query_embedding,
                "url": clean_url,
            },
        )

        if not results:
            return "No relevant information found in the database for this query."

        output = ["Here is the retrieved context from the database:\n"]
        for i, r in enumerate(results, 1):
            related_list = r.get("related_sources") or []
            related_str = "\n  - " + "\n  - ".join(related_list[:3]) if related_list else " None found"

            output.append(
                f"--- SOURCE {i} ---\n"
                f"URL: {r['source_url']}\n"
                f"Related Sources:{related_str}\n"
                f"Content:\n{r['text']}\n"
            )
        return "\n".join(output)

if __name__ == "__main__":
    # 1. Test semantic query
    print("=== 1. Semantic Search ===")
    print(search_ai_policy(query="What is High-Risk AI?", top_k=1))

    # 2. Test direct URL inspection
    print("\n=== 2. Direct Document URL Lookup ===")
    print(search_ai_policy(document_url="https://en.wikipedia.org/wiki/List_of_proprietary_artificial_intelligence_software", top_k=1))
    
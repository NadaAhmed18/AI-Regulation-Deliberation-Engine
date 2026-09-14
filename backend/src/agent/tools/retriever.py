from typing import Optional
from src.clients.neo4j import Neo4jClient
from src.utils.embedder import Embedder
from src.config import EMBEDDING_MODEL

db = Neo4jClient()
embedder = Embedder(model_name=EMBEDDING_MODEL)
INDEX_NAME = "chunk_vector_index"


def search_ai_policy(query: Optional[str] = None, document_url: Optional[str] = None, top_k: int = 3) -> str:
    """Searches Neo4j policy chunks by semantic query or document URL."""
    if not query and not document_url:
        return "Please provide either a search 'query' or a 'document_url'."

    clean_url = document_url.strip().lower().rstrip("/") if document_url else None

    # CASE 1: Direct Document Lookup
    if clean_url and not query:
        cypher = """
        MATCH (doc:Document)
        WHERE toLower(doc.document_url) = $url OR toLower(doc.document_url) = $url + '/'
        MATCH (doc)-[:HAS_CHUNK]->(chunk:Chunk)
        WITH doc, chunk
        ORDER BY chunk.chunk_index ASC
        RETURN doc.document_url AS source_url, doc.related_documents AS related_sources, collect(chunk.text) AS texts
        """
        results = db.execute_query(cypher, {"url": clean_url})
        if not results:
            return f"No document found for URL: {clean_url}"

        row = results[0]
        full_text = "\n\n".join(row["texts"])
        related = "\n  - " + "\n  - ".join((row.get("related_sources") or [])[:5])

        return f"--- FULL DOCUMENT CONTENT ---\nURL: {row['source_url']}\nRelated Sources:{related}\n\nContent:\n{full_text}\n"

    # CASE 2: Semantic Vector Search
    assert query, "Query must be provided for semantic search."
    query_embedding = embedder.embed([query], is_query=True)[0].tolist()
    cypher = """
    CALL db.index.vector.queryNodes($index_name, $fetch_k, $query_embedding)
    YIELD node AS chunk, score
    MATCH (doc:Document)-[:HAS_CHUNK]->(chunk)
    WHERE $url IS NULL OR toLower(doc.document_url) = $url OR toLower(doc.document_url) = $url + '/'
    RETURN chunk.text AS text, doc.document_url AS source_url, doc.related_documents AS related_sources
    ORDER BY score DESC
    LIMIT $top_k
    """
    results = db.execute_query(
        cypher,
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
        related = "\n  - " + "\n  - ".join((r.get("related_sources") or [])[:3])
        output.append(f"--- SOURCE {i} ---\nURL: {r['source_url']}\nRelated Sources:{related}\nContent:\n{r['text']}\n")

    return "\n".join(output)
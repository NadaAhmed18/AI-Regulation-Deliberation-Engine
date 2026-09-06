# Run from backend/: python -m src.scripts.export_db_to_json

import os
import json
from src.clients.neo4j import Neo4jClient


def export_database():
    print("[*] Connecting to Neo4j to export knowledge graph...")
    db = Neo4jClient()

    # OPTIONAL MATCH ensures we don't accidentally drop documents with 0 chunks
    query = """
    MATCH (d:Document)
    OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
    WITH d, [chunk IN collect(c) WHERE chunk IS NOT NULL | {
        chunk_id: chunk.chunk_id,
        text: chunk.text,
        embedding: chunk.embedding,
        chunk_index: chunk.chunk_index
    }] AS chunks
    RETURN 
        d.document_url AS url,
        d.domain AS domain,
        d.metadata AS metadata,
        coalesce(d.related_documents, []) AS related_documents,
        chunks
    """

    results = db.execute_query(query)

    if not results:
        print("[-] Database is empty. Nothing to export.")
        return

    output_dir = os.path.join(os.getcwd(), "data", "dump")
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "neo4j_export.json")

    print(f"[*] Fetched {len(results)} documents with their chunks, vectors, and relations.")
    print(f"[*] Saving to {output_file}...")

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("[+] Export complete! Commit this JSON file to GitHub.")


if __name__ == "__main__":
    export_database()
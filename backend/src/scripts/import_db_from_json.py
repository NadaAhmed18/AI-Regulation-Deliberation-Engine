# Run from backend/: python -m src.scripts.import_db_from_json

import os
import json
from src.clients.neo4j import Neo4jClient


def import_database():
    input_file = os.path.join(os.getcwd(), "data", "dump", "neo4j_export.json")

    if not os.path.exists(input_file):
        print(f"[-] Error: Export file not found at {input_file}")
        return

    print(f"[*] Reading data from {input_file}...")
    with open(input_file, "r", encoding="utf-8") as f:
        neo4j_batch = json.load(f)

    if not neo4j_batch:
        print("[-] The JSON file is empty.")
        return

    print(f"[*] Found {len(neo4j_batch)} documents. Connecting to Neo4j...")

    # Initialize DB Schema and Indexes
    db_client = Neo4jClient()
    db_client.setup_database()
    db_client.setup_vector_index()

    # 1. Restore Document and Chunk Nodes
    cypher_nodes = """
    UNWIND $batch AS item
    MERGE (d:Document {document_url: item.url})
    SET d.domain = item.domain,
        d.metadata = item.metadata,
        d.related_documents = item.related_documents
    
    WITH d, item
    UNWIND item.chunks AS chunk_data
    MERGE (c:Chunk {chunk_id: chunk_data.chunk_id})
    SET c.text = chunk_data.text,
        c.embedding = chunk_data.embedding,
        c.chunk_index = chunk_data.chunk_index
        
    MERGE (d)-[:HAS_CHUNK]->(c)
    """

    print("[*] Rebuilding Documents, Chunks, and Vector Index...")
    db_client.execute_query(cypher_nodes, parameters={"batch": neo4j_batch})

    # 2. Rebuild Graph Relationships (:RELATES_TO)
    cypher_edges = """
    UNWIND $batch AS item
    MATCH (doc:Document {document_url: item.url})
    UNWIND doc.related_documents AS target_url
    MATCH (target:Document {document_url: target_url})
    WHERE doc <> target
    MERGE (doc)-[:RELATES_TO]->(target)
    """

    print("[*] Reconnecting Document-to-Document (:RELATES_TO) graph edges...")
    db_client.execute_query(cypher_edges, parameters={"batch": neo4j_batch})

    print(f"[+] Success! Fully restored {len(neo4j_batch)} documents with vectors AND graph topology into Neo4j.")


if __name__ == "__main__":
    import_database()
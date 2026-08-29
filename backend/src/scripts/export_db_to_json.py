# Run from backend/: python -m src.scripts.export_db_to_json

import os
import json
from src.clients.neo4j import Neo4jClient

def export_database():
    print("[*] Connecting to Neo4j to export knowledge graph...")
    db = Neo4jClient()
    
    # Cypher query to pull Documents and group their Chunks together
    query = """
    MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)
    WITH d, collect({
        chunk_id: c.chunk_id,
        text: c.text,
        embedding: c.embedding,
        chunk_index: c.chunk_index
    }) AS chunks
    RETURN 
        d.document_url AS url,
        d.domain AS domain,
        d.metadata AS metadata,
        d.related_documents AS related_documents,
        chunks
    """
    
    results = db.execute_query(query)
    
    if not results:
        print("[-] Database is empty. Nothing to export.")
        return

    # Define the dump path
    output_dir = os.path.join(os.getcwd(), "data", "dump")
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "neo4j_export.json")
    
    print(f"[*] Fetched {len(results)} documents with their chunks and vectors.")
    print(f"[*] Saving to {output_file}...")
    
    # Save to JSON
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
        
    print("[+] Export complete! Commit this JSON file to GitHub.")

if __name__ == "__main__":
    export_database()
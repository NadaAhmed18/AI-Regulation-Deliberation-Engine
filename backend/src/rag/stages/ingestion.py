import json
import os
from typing import List, Dict, Any

from src.clients.neo4j import Neo4jClient
from src.utils.embedder import Embedder
from config import EMBEDDING_MODEL

def ingest_documents(documents: List[Dict[str, Any]], model_type: str = "voyage"):
    """
    Takes a list of document dictionaries, generates embeddings for their bodies,
    and stores them in the Neo4j database.
    """
    if not documents:
        print("No documents to ingest.")
        return

    print(f"[*] Starting ingestion for {len(documents)} documents...")

    # 1. Initialize Clients
    db_client = Neo4jClient()
    embedder = Embedder(model_name=EMBEDDING_MODEL, model_type=model_type)

    # 2. Setup Database Schema and Vector Index
    print("[*] Ensuring database constraints and indexes are set...")
    db_client.setup_database()
    db_client.setup_vector_index()

    # 3. Generate Embeddings
    print(f"[*] Generating embeddings using {EMBEDDING_MODEL}...")
    bodies = [doc["body"] for doc in documents]
    embeddings_array = embedder.embed(bodies, is_query=False)
    
    # Convert numpy array back to standard Python lists for Neo4j
    embeddings_list = embeddings_array.tolist()

    # 4. Prepare data for Neo4j batch insertion
    print("[*] Preparing data for Neo4j...")
    batch_data = []
    for doc, emb in zip(documents, embeddings_list):
        batch_data.append({
            "document_url": doc["document_url"],
            "domain": doc["domain"],
            "body": doc["body"],
            "related_documents": doc.get("related_documents", []),
            # Neo4j cannot store nested dictionaries, so we serialize metadata to a JSON string
            "metadata": json.dumps(doc.get("metadata", {}), ensure_ascii=False),
            "embedding": emb
        })

    # 5. Execute Batch Cypher Query
    # We use UNWIND for massive performance gains (writes all docs in 1 database call)
    # MERGE ensures we don't create duplicates if the URL already exists
    cypher_query = """
    UNWIND $batch AS doc
    MERGE (d:Document {document_url: doc.document_url})
    SET d.domain = doc.domain,
        d.body = doc.body,
        d.related_documents = doc.related_documents,
        d.metadata = doc.metadata,
        d.embedding = doc.embedding
    """
    
    print("[*] Writing to Neo4j...")
    db_client.execute_query(cypher_query, parameters={"batch": batch_data})
    
    db_client.close()
    print(f"[+] Successfully ingested {len(batch_data)} documents into Neo4j!")


# ==========================================
# Testing / Execution Block
# ==========================================
if __name__ == "__main__":
    # Load the JSON file created by scraper.py
    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../data/raw"))
    file_path = os.path.join(data_dir, "scraped_documents.json")
    
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            scraped_docs = json.load(f)
            
        # You can change model_type to "hf" if you want to use local models
        ingest_documents(scraped_docs, model_type="voyage")
    else:
        print(f"[-] Could not find {file_path}. Please run scraper.py first.")
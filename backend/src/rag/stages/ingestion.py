import json
import hashlib
from typing import List, Dict, Any

from src.clients.neo4j import Neo4jClient
from src.utils.embedder import Embedder
from src.config import EMBEDDING_MODEL

def generate_chunk_id(url: str, chunk_index: int) -> str:
    """Creates a unique deterministic ID for each chunk."""
    unique_string = f"{url}_chunk_{chunk_index}"
    return hashlib.md5(unique_string.encode('utf-8')).hexdigest()

def ingest_documents(documents: List[Dict[str, Any]]):
    """
    Takes scraped documents, chunks them, embeds the chunks, 
    and saves the Document->Chunk graph into Neo4j.
    """
    if not documents:
        print("[-] No documents to ingest.")
        return

    print(f"\n[*] Starting ingestion for {len(documents)} documents...")
    
    # 1. Initialize Clients
    db_client = Neo4jClient()
    db_client.setup_database()
    db_client.setup_vector_index()
    
    embedder = Embedder(model_name=EMBEDDING_MODEL)
    
    neo4j_batch = []
    print("[*] Chunking and Embedding documents...")
    
    for doc in documents:
        url = doc["document_url"]
        
        # Chunk text
        chunks_text = embedder.chunk_text(doc["body"])
        if not chunks_text:
            continue
            
        # Embed all chunks for this document
        chunk_embeddings = embedder.embed(chunks_text, is_query=False).tolist()
        
        # Package chunks with deterministic IDs
        doc_chunks = []
        for i, (text, emb) in enumerate(zip(chunks_text, chunk_embeddings)):
            doc_chunks.append({
                "chunk_id": generate_chunk_id(url, i),
                "text": text,
                "embedding": emb,
                "chunk_index": i
            })
            
        neo4j_batch.append({
            "url": url,
            "domain": doc["domain"],
            "metadata": json.dumps(doc.get("metadata", {}), ensure_ascii=False),
            "related_documents": doc.get("related_documents", []),
            "chunks": doc_chunks
        })
        print(f"  -> Generated {len(doc_chunks)} chunks for {doc['domain']}")

    # 2. Highly optimized Cypher query
    cypher_query = """
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
    
    print("[*] Writing to Neo4j Graph Database...")
    db_client.execute_query(cypher_query, parameters={"batch": neo4j_batch})
    # db_client.close()
    
    print(f"[+] Successfully ingested {len(neo4j_batch)} documents with their chunks into Neo4j!")
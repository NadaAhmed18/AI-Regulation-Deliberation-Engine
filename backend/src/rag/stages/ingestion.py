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

def ingest_documents(documents: List[Dict[str, Any]], on_conflict: str = "ignore") -> Dict[str, Any]:
    """
    Ingests scraped documents into Neo4j with full graph referential integrity.
    
    Args:
        documents: List of scraped document dictionaries.
        on_conflict: 
            - 'ignore' (default): Skips embedding/updating if document already exists.
            - 'update': Re-chunks, re-embeds, updates properties, and syncs edges 
                        (prunes stale [:RELATES_TO] edges that no longer exist).
    """
    if not documents:
        print("[-] No documents to ingest.")
        return {"ingested": 0, "updated": 0, "skipped": 0}

    db_client = Neo4jClient()
    db_client.setup_database()
    db_client.setup_vector_index()

    urls = [doc["document_url"] for doc in documents]

    # 1. Identify which documents already exist
    existing_records = db_client.execute_query(
        "MATCH (d:Document) WHERE d.document_url IN $urls RETURN d.document_url AS url",
        {"urls": urls},
    )
    existing_urls = {r["url"] for r in existing_records}

    docs_to_process = []
    skipped_count = 0
    updated_count = 0
    new_count = 0

    for doc in documents:
        url = doc["document_url"]
        if url in existing_urls:
            if on_conflict == "ignore":
                print(f"[!] Document exists. Skipping content refresh: {url}")
                skipped_count += 1
                continue
            else:
                print(f"[*] Document exists. Syncing & updating: {url}")
                updated_count += 1
                # DATA INTEGRITY: Clear old chunks so changed text doesn't leave orphaned chunks
                db_client.execute_query(
                    "MATCH (d:Document {document_url: $url})-[r:HAS_CHUNK]->(c:Chunk) DETACH DELETE c",
                    {"url": url},
                )
        else:
            new_count += 1

        docs_to_process.append(doc)

    # 2. Chunk and Embed
    if docs_to_process:
        embedder = Embedder(model_name=EMBEDDING_MODEL)
        neo4j_batch = []
        print(f"[*] Chunking and embedding {len(docs_to_process)} document(s)...")

        for doc in docs_to_process:
            url = doc["document_url"]
            chunks_text = embedder.chunk_text(doc["body"])
            if not chunks_text:
                continue

            chunk_embeddings = embedder.embed(chunks_text, is_query=False).tolist()

            doc_chunks = []
            for i, (text, emb) in enumerate(zip(chunks_text, chunk_embeddings)):
                doc_chunks.append({
                    "chunk_id": generate_chunk_id(url, i),
                    "text": text,
                    "embedding": emb,
                    "chunk_index": i,
                })

            neo4j_batch.append({
                "url": url,
                "domain": doc["domain"],
                "metadata": json.dumps(doc.get("metadata", {}), ensure_ascii=False),
                "related_documents": doc.get("related_documents", []),
                "chunks": doc_chunks,
            })

        # 3. Write Document Node & Chunks
        cypher_nodes_and_chunks = """
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
        db_client.execute_query(cypher_nodes_and_chunks, parameters={"batch": neo4j_batch})

    # 4. DATA INTEGRITY: Edge Synchronization (Prune stale relations & add new ones)
    # Only run reconciliation for docs that were actually ingested/updated
    urls_to_sync = [doc["document_url"] for doc in docs_to_process]
    
    if urls_to_sync:
        cypher_sync_edges = """
        UNWIND $urls AS current_url
        MATCH (doc:Document {document_url: current_url})
        
        // --- STEP A: PRUNE STALE EDGES ---
        // If an edge exists to a target that is NO LONGER in related_documents, delete it
        OPTIONAL MATCH (doc)-[stale_rel:RELATES_TO]->(target:Document)
        WHERE NOT target.document_url IN doc.related_documents
        DELETE stale_rel
        
        // --- STEP B: ADD NEW FORWARD EDGES ---
        // Connect doc -> target for any valid URLs present in Neo4j
        WITH doc
        UNWIND doc.related_documents AS target_url
        MATCH (new_target:Document {document_url: target_url})
        WHERE doc <> new_target
        MERGE (doc)-[:RELATES_TO]->(new_target)
        
        // --- STEP C: ADD BACKWARD EDGES ---
        // Connect any existing documents that were already pointing to doc
        WITH doc
        MATCH (source:Document)
        WHERE doc.document_url IN source.related_documents AND source <> doc
        MERGE (source)-[:RELATES_TO]->(doc)
        """
        db_client.execute_query(cypher_sync_edges, parameters={"urls": urls_to_sync})

    print(f"[+] Ingestion complete: {new_count} new, {updated_count} updated, {skipped_count} skipped.")
    return {"ingested": new_count, "updated": updated_count, "skipped": skipped_count}
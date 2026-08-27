# Week 1 — Knowledge Infrastructure: AI Regulation & Policy

## 1. Overview

This project implements the foundational **knowledge infrastructure** for **Qubeterra AI NextGen (Theme 1)**. The platform simulates how different stakeholders react to AI regulatory frameworks (like the EU AI Act) and evaluates trade-offs regarding democratic values, innovation, and fundamental rights.

This pipeline performs end-to-end Retrieval-Augmented Generation (RAG) ingestion:
1. **Scrapes** relevant policy documents, articles, and guidelines from 100+ diverse sources.
2. **Cleans** the HTML to extract high-quality text using Trafilatura and Regex, filtering out 404s and errors.
3. **Semantic Link Routing** using FlashRank to discover and rank the top 20 most relevant related links per document.
4. **Chunks** documents intelligently along sentence boundaries with context-preserving overlap.
5. **Embeds** the chunks using Voyage AI (`voyage-3.5-lite`).
6. **Stores** the knowledge graph (Documents -> Chunks) and Vector Embeddings in **Neo4j** (approved substitute for PostgreSQL) to enable Graph-RAG capabilities for downstream AI agents.

---

## 2. Setup and Installation

### Prerequisites
* Python 3.10+
* Neo4j Database (Docker or Desktop)
* `uv` (Fast Python Package Installer)

### Environment Setup
Navigate to the backend folder and use `uv` to set up the environment:
```bash
cd backend
uv venv
# Activate the environment
# Windows: .venv\Scripts\activate
# Mac/Linux: source .venv/bin/activate

uv pip install -r requirements.txt
```

Create a `.env` file in the `backend` directory:
```ini
# Embedding Model API (Required)
VOYAGE_API_KEY=your_voyage_api_key_here

# Neo4j Graph Database
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password123
```

---

## 3. Importing the Pre-Built Database (For Reviewers)

If you do not want to run the 100+ link ingestion process from scratch, you can load the pre-built knowledge graph from the provided database dump located in `backend/data/dumps/neo4j.dump`.

**If using Neo4j Docker:**
```bash
# 1. Copy the dump file into the container's import folder
docker cp data/dumps/neo4j.dump <container_name>:/var/lib/neo4j/import/

# 2. Stop the active database instance inside the container
docker exec -it <container_name> cypher-shell -u neo4j -p password123 "STOP DATABASE neo4j;"

# 3. Load the dump file (overwriting the existing empty DB)
docker exec -it <container_name> neo4j-admin database load neo4j --from-path=/var/lib/neo4j/import/neo4j.dump --overwrite-destination=true

# 4. Restart the database
docker exec -it <container_name> cypher-shell -u neo4j -p password123 "START DATABASE neo4j;"
```

*Note: If you are using Neo4j Desktop, you can simply create a new DBMS, click the `...` next to it, select "Open Folder" -> "Dropins", paste the dump file there, and use the terminal to run `bin/neo4j-admin database load neo4j --from-path=...`.*

---

## 4. Running the Pipeline (Ingestion)

If you wish to build the database from scratch, the pipeline is designed to read a seed file of URLs, process them in safe batches (10 at a time), and ingest them into Neo4j.

Ensure your Neo4j database is running, then execute:
```bash
python -m src.rag.main --links-file data/seed_links.txt
```
*Note: Processing 100+ links takes time as it involves web crawling, semantic reranking of internal links, chunking, and embedding API calls.*

---

## 5. Retrieval & Evaluation

To ensure this pipeline provides robust knowledge to Week 2 agents, the retrieval system includes a quantitative evaluation suite. It tests 5 representative queries based on the Qubeterra AI NextGen problem brief.

**Run the Evaluation Script:**
```bash
python -m src.rag.evaluate
```

**Evaluation Methodology:** 
The script executes vector-graph searches and retrieves the top 3 results. It calculates **Precision@3 (P@3)** programmatically by checking if expected semantic keywords (e.g., "social scoring", "prohibited") appear within the retrieved policy text.

| Test Query | Expected Knowledge Context | P@3 |
| :--- | :--- | :---: |
| *What is the EU AI Act?* | Defines the framework, Regulation (EU) 2024/1689, risk-based approach. | 1.00 |
| *Does the EU AI Act ban all AI?* | Must explicitly state the Act is NOT a general ban. | 1.00 |
| *What is an Unacceptable Risk?* | Mentions harmful manipulation, social scoring, biometrics. | 0.75 |
| *What democratic values are protected?* | Human autonomy, fundamental rights, privacy, rule of law. | 1.00 |
| *How are GPAI models regulated?* | Mentions broad-range tasks, EU market placement. | 0.50 |

**LLM Tool Interface:**
The `src.agent.retriever` module exposes the `KnowledgeRetrieverTool` class, which contains the `search_ai_policy()` function. This is formatted specifically with strict type-hints and string-returns so Week 2 LLM agents can call it directly as a function tool.

---

## 6. Design Decisions & Architecture

* **Data Collection Strategy:** Gathered 100+ diverse sources covering EU Pro-Regulation, US Pro-Innovation, Big Tech viewpoints, and Civil Rights watchdogs to ensure the simulation agents have balanced, multi-perspective knowledge.
* **Cleaning Strategy:** Used `crawl4ai` combined with strict HTTP 404/Error blocking and Trafilatura to extract pristine text without navigation boilerplate.
* **Chunking Strategy:** Sentence-based chunking with a 2-sentence sliding overlap. Hard token limits cut legal definitions in half; splitting by sentences preserves semantic meaning.
* **Embeddings:** `voyage-3.5-lite` (1024 dimensions). The Voyage 3.5 series is highly optimized for policy and legal retrieval, offering extremely fast inference and outperforming standard dense models on complex regulatory text.
* **Vector Database:** Neo4j (Approved substitute). Policy debates involve complex hierarchies. Neo4j maps relationships natively (`(Document)-[:HAS_CHUNK]->(Chunk)`), allowing Week 2 agents to perform vector similarity searches and traverse the graph to find semantic "related_documents".

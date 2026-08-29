# Week 1 — Knowledge Infrastructure: AI Regulation & Policy

## 1. Overview

This project implements the foundational **knowledge infrastructure** for **Qubeterra AI NextGen (Theme 1)**. The platform simulates how different stakeholders react to AI regulatory frameworks (like the EU AI Act) and evaluates trade-offs regarding democratic values, innovation, and fundamental rights.

This pipeline performs end-to-end Retrieval-Augmented Generation (RAG) ingestion:

1. **Scrapes** relevant policy documents, articles, and guidelines from diverse sources.
2. **Cleans** the HTML to extract high-quality text using Trafilatura and Regex.
3. **Semantic Link Routing** using FlashRank to discover related links.
4. **Chunks** documents along sentence boundaries with context-preserving overlap.
5. **Embeds** the chunks using Voyage AI (`voyage-3.5-lite`).
6. **Stores** the knowledge graph (Documents -> Chunks) and Vector Embeddings in **Neo4j** (approved substitute for PostgreSQL) to enable Graph-RAG capabilities for downstream AI agents.

---

## 2. Setup and Installation

### Prerequisites

- Python 3.10+
- Neo4j Database (Docker or Desktop) running locally with Vector indexing supported.
- `uv` (Fast Python Package Installer)

### Environment Setup

Navigate to the backend folder and set up the environment:

```bash
cd backend
uv venv
# Activate the environment:
# Windows: .venv\Scripts\activate
# Mac/Linux: source .venv/bin/activate

uv pip install -r requirements.txt
```

Create a `.env` file in the `backend` directory:

```ini
VOYAGE_API_KEY=your_voyage_api_key_here
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password123
```

---

## 3. Importing the Pre-Built Database (For Reviewers)

To ensure 100% compatibility across all Neo4j versions (Community vs. Enterprise) and to avoid Docker permission issues with binary `.dump` files, we have exported the fully embedded vector database into a JSON format.

You **do not** need an active Voyage API key to load this data, as the embeddings are already computed and saved.

Ensure your Neo4j database is running (it is safe to run this on an empty or partially filled database), and execute this command from the `backend/` folder:

```bash
python -m scripts.import_db_from_json
```

*This script will instantly rebuild the Graph relationships and the Vector Index locally in seconds. It uses Cypher `MERGE` commands, so running it multiple times will safely overwrite data without creating duplicates.*

---

## 4. Running the Ingestion Pipeline from Scratch (Optional)

If you wish to build the database from scratch by scraping the live URLs:

```bash
python -m src.rag.main --links-file data/seed_links.txt
```
*Note: We have set `MAX_CHUNKS = 2` (or a similarly low threshold) in `src/config.py`. This is a deliberate architectural decision to protect limited embedding API quotas while still ensuring every document has its core introduction/summary embedded into the database.*

---

## 5. Retrieval & Evaluation

To ensure this pipeline provides robust knowledge to Week 2 agents, we built a quantitative evaluation suite.

**Run the Evaluation Script:**

```bash
python -m src.rag.evaluation.evaluate
```

**Evaluation Methodology:**
The script executes vector-graph searches and retrieves the top 3 results. It calculates **True Precision@3 (P@3)** programmatically by checking if expected semantic keywords appear within _each individual retrieved chunk_ (e.g., if 2 out of 3 chunks contain the keywords, the score is 0.67).

### Official Evaluation Results

| Test Query                                             | Expected Keywords                                   | Precision@3 (P@3) |
| :----------------------------------------------------- | :-------------------------------------------------- | :---------------: |
| What is the EU AI Act?                                 | regulation, risk, framework, european               |       1.00        |
| Does the EU AI Act ban all artificial intelligence?    | not a general ban, most, not classified, minimal    |       1.00        |
| What is considered an Unacceptable Risk in AI?         | prohibited, manipulation, social scoring, biometric |       0.67        |
| What democratic values are protected by AI governance? | fundamental rights, autonomy, privacy, rule of law  |       1.00        |
| How are General Purpose AI (GPAI) models regulated?    | general-purpose, broad range, market, transparency  |       1.00        |

**Average System Precision:** **0.93**

*(Files `evaluation_results.md` and `retrieved_results.json` are automatically generated in the evaluation directory to prove reproducibility).*

---

## 6. Handoff to Week 2 (LLM Tool Interface)

The `src.agent.tools.retriever` module exposes the `search_ai_policy()` function. This is formatted specifically with strict type-hints, string-returns, and an OpenAI-compatible JSON schema so Week 2 LLM agents can call it directly as a ReAct function tool.
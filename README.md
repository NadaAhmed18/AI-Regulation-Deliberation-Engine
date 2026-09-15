## 1. What This Project Is

The **AI-Regulation Deliberation Engine** is a multi-agent simulation platform for evaluating AI policy topics (e.g., EU AI Act, hardware kill-switches, open weights).

* **Multi-Agent Deliberation**: Autonomous agents with specific stances, backgrounds, and communication topologies (Mesh, Ring, Custom) debate policy.
* **Continuous Stance Tracking**: An on-device CPU-quantized model (`cross-encoder/nli-deberta-v3-small` via ONNX Runtime) scores each agent's stance from **$-5.0$ (opposed)** to **$+5.0$ (in favor)** after every turn.
* **Network Dynamics**: Tracks agreement over time and builds a directed graph of agent-to-agent persuasion based on stance convergence.
* **Hybrid Graph-RAG**: Neo4j vector search + knowledge graph with live web search (Tavily) fallback and background scraping queues.
* **Real-Time Streaming**: Server-Sent Events (SSE) stream thinking tokens, speech tokens, tool invocations, and live analytics updates.

---

## 2. Prerequisites

1. **Docker & Docker Compose** installed and running.
2. **Python 3.10+** (Python 3.11 or 3.12 recommended).
3. **Node.js 18+** and `npm` or `pnpm`.
4. **API Keys**:
   * **OpenRouter API Key** (Required): For agent dialogue and persona generation.
   * **Tavily API Key** (Recommended): For live web search during debates.
   * **Voyage AI Key** (Optional): For vector embeddings (can fall back to local HuggingFace).

---

## 3. Step 1: Start Docker Infrastructure

The Docker stack runs **PostgreSQL**, **Neo4j**, **Redis**, **ClickHouse**, **MinIO**, and the **Langfuse Observability Suite**.

1. Navigate to the `docker/` directory:
   ```bash
   cd docker
   ```

2. Create a `.env` file in `docker/`:
   ```env
   # PostgreSQL
   POSTGRES_USER=langfuse
   POSTGRES_PASSWORD=postgres_langfuse123
   POSTGRES_DB=main

   # Neo4j
   NEO4J_AUTH=neo4j/password123

   # Redis & MinIO
   REDIS_AUTH=redis123
   MINIO_ROOT_USER=minio_admin
   MINIO_ROOT_PASSWORD=minio123

   # Langfuse
   NEXTAUTH_SECRET=changeme_secret_key_at_least_32_characters_long
   SALT=changeme_salt_at_least_32_characters_long
   TELEMETRY_ENABLED=false
   ```

3. Launch the containers in detached mode:
   ```bash
   docker compose up -d
   ```

4. Verify all containers are healthy:
   ```bash
   docker compose ps
   ```

> **Note on Port Conflict:** Langfuse Web runs on port `3000`. To prevent conflicts with Next.js, run the frontend on port `5000` (already pre-configured in the backend CORS settings).

---

## 4. Step 2: Set Up and Run Backend (FastAPI)

1. Open a new terminal and navigate to `backend/`:
   ```bash
   cd backend
   ```

2. Create and activate a Python virtual environment:
   ```bash
   # Linux / macOS
   python3 -m venv venv
   source venv/bin/activate

   # Windows (PowerShell)
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. Install required Python packages:
   ```bash
   pip install --upgrade pip
   pip install fastapi uvicorn psycopg2-binary neo4j langfuse \
       optimum[onnxruntime] onnx onnxruntime transformers torch \
       numpy networkx voyageai trafilatura crawl4ai flashrank \
       tavily-python python-dotenv pydantic requests
   ```

4. Create a `.env` file inside `backend/`:
   ```env
   # LLM Provider (OpenRouter)
   OPENROUTER_API_KEY=your_openrouter_api_key_here
   DEFAULT_MODEL=openai/gpt-oss-120b
   PERSONA_MODEL=openai/gpt-oss-120b
   DEFAULT_REASONING_EFFORT=low
   DEFAULT_MAX_COMPLETION_TOKENS=3000

   # Databases
   DATABASE_URL=postgresql://langfuse:postgres_langfuse123@localhost:5432/main
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USERNAME=neo4j
   NEO4J_PASSWORD=password123

   # Embeddings & RAG
   EMBEDDING_PROVIDER=voyage
   EMBEDDING_MODEL=voyage-3.5-lite
   VECTOR_DIMENSION=1024
   VOYAGE_API_KEY=your_voyage_api_key_here
   TAVILY_API_KEY=your_tavily_api_key_here

   # Stance Engine
   STANCE_GRADER_ENGINE=nli

   # Langfuse Observability (Optional)
   LANGFUSE_PUBLIC_KEY=
   LANGFUSE_SECRET_KEY=
   LANGFUSE_BASE_URL=http://localhost:3000
   ```

5. *(Optional but Recommended)* Restore the pre-built Neo4j Knowledge Graph:
   ```bash
   python -m src.scripts.import_db_from_json
   ```

6. Start the FastAPI server:
   ```bash
   python -m uvicorn src.main:app --reload --port 8000
   ```

7. Verify backend health by visiting:
   [http://localhost:8000/health](http://localhost:8000/health) — should return `"status": "healthy"` for both PostgreSQL and Neo4j.

---

## 5. Step 3: Set Up and Run Frontend (Next.js)

1. Open a new terminal and navigate to `frontend/`:
   ```bash
   cd frontend
   ```

2. Install Node dependencies:
   ```bash
   npm install
   ```

3. Create a `.env.local` file inside `frontend/`:
   ```env
   NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api
   ```

4. Start the frontend on port **5000** (avoids the Langfuse port 3000 conflict):
   ```bash
   npm run dev -- -p 5000
   ```

---

## 6. Access Points & Verification

| Service | URL | Credentials / Notes |
|---|---|---|
| **Simulation Arena (UI)** | [http://localhost:5000](http://localhost:5000) | Main debate interface |
| **Optimization Slides (UI)** | [http://localhost:5000/optimization](http://localhost:5000/optimization) | Benchmark results and video replays |
| **FastAPI Backend Swagger** | [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive API documentation |
| **Backend Health Check** | [http://localhost:8000/health](http://localhost:8000/health) | Verifies PG and Neo4j connectivity |
| **Neo4j Browser** | [http://localhost:7474](http://localhost:7474) | `neo4j` / `password123` |
| **Langfuse Dashboard** | [http://localhost:3000](http://localhost:3000) | Create local admin account on first load |

---

## 7. How to Run a Simulation (End-to-End Test)

1. Open **[http://localhost:5000](http://localhost:5000)** in your browser.
2. Select a predefined topic (e.g., *"Should governments mandate hardware-level kill-switches..."*).
3. Click **Generate Personas** (this queries OpenRouter to build balanced debate agents).
4. Select a network topology (**Mesh** for full open debate, **Ring** for circular information cascade).
5. Click **Start Simulation**.
6. The UI will establish a Server-Sent Events (SSE) connection:
   * Displays the active speaker.
   * Streams reasoning tokens in real time.
   * Displays live speech synthesis.
   * Highlights background tool usage.
   * Evaluates the continuous stance shift $[-5.0, +5.0]$ using local ONNX and updates the persuasion network graph automatically.
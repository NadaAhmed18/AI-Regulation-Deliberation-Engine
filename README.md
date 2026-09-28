# AI-Regulation Deliberation Engine

A multi-agent deliberation and policy simulation platform designed to stress-test and evaluate AI governance frameworks (e.g., the EU AI Act, hardware-level compute controls, open weights proliferation).

The platform models complex multi-stakeholder debates with customizable communication topologies, on-device stance-shift scoring, grounded Graph-RAG retrieval, and real-time visualization over Server-Sent Events (SSE).

---

## 1. Core Architectural Features

- **Constrained Multi-Agent Deliberation**: Agents simulate distinct personas (safety advocates, open-source developers, regulators) constrained by directed communication topologies (**Ring**, **Mesh**, or **Custom DAG** visibility matrices).
- **On-Device Continuous Stance Tracking**: A local, CPU-quantized Natural Language Inference model (`cross-encoder/nli-deberta-v3-small` via ONNX Runtime) scores opinion shifts continuously from **$-5.0$ (strongly opposed)** to **$+5.0$ (strongly in favor)** after every turn without external LLM evaluation costs.
- **Network & Persuasion Dynamics**: Generates real-time persuasion network graphs, agreement matrices, and forward-filled opinion trajectory charts.
- **Hybrid Graph-RAG & Decoupled Ingestion**: Combines a Neo4j knowledge graph (policy vectors + document linkages) with live web retrieval (Tavily). Heavy scraping (`crawl4ai`) runs on an autonomous, scalable **Celery worker pool** decoupled from the API loop.
- **Full-Stack Observability**: Native integration with **Langfuse v3** (ClickHouse, MinIO, Redis) for tracing token consumption, agent thoughts, latency, and tool invocations.
- **Zero-Config Public Sharing**: Embedded Cloudflare Tunnel allows you to share the application instantly over a secure HTTPS link with zero router port forwarding.

---

## 2. Prerequisites

- **Docker & Docker Compose** (Docker Desktop on Windows/macOS with WSL2 enabled, or Docker Engine on Linux).
- **Git** installed.
- **API Keys**:
  - **OpenRouter API Key** (_Required_): Powers agent debate dialogues and persona generation.
  - **Tavily API Key** (_Recommended_): For live web search during debates.
  - **Voyage AI Key** (_Optional_): For vector embeddings (falls back to local HuggingFace).

---

## 3. Environment Configuration

The repository uses two `.env` files to separate infrastructure configuration from application secrets.

### A. Docker Infrastructure Environment (`docker/.env`)

Copy the example file:

```bash
cp docker/.env.example docker/.env
```
````

Key defaults in `docker/.env`:

```env
# PostgreSQL
POSTGRES_USER="langfuse"
POSTGRES_PASSWORD="postgres_langfuse123"
POSTGRES_DB="langfuse"
DATABASE_URL="postgresql://langfuse:postgres_langfuse123@postgres:5432/main"

# Neo4j
NEO4J_AUTH="neo4j/password123"
NEO4J_USERNAME="neo4j"
NEO4J_PASSWORD="password123"

# Redis & ClickHouse
REDIS_AUTH="redis123"
CLICKHOUSE_USER="clickhouse"
CLICKHOUSE_PASSWORD="clickhouse123"

# Langfuse Observability
LANGFUSE_BASE_URL="http://langfuse-web:3000"
```

### B. Application Secrets (`backend/.env`)

Copy the example file:

```bash
cp backend/.env.example backend/.env
```

Fill in your API keys:

```env
OPENROUTER_API_KEY="sk-or-v1-your-openrouter-key"
TAVILY_API_KEY="tvly-your-tavily-key"
VOYAGE_API_KEY="pa-your-voyage-key"
```

---

## 4. Deployment Methods

### Method 1: One-Click Windows Deployment (Recommended for Windows)

The project includes an automated deployment launcher in the root directory: `run.bat`.

1. Make sure **Docker Desktop** is running.
2. In File Explorer, **double-click `run.bat`** (or execute `./run.bat` in PowerShell/CMD).
3. Select your deployment mode from the menu:
   - **`[1] Local Only`**: Builds and starts all containers. Accessible locally at `http://localhost:5000` and across your local Wi-Fi at `http://<YOUR_LOCAL_IP>:5000`.
   - **`[2] Shared Online`**: Starts the application **plus a secure Cloudflare Tunnel**. Outputs an encrypted public URL (`https://<random-name>.trycloudflare.com`) that anyone across the internet can access.
   - **`[3] View Service Logs`**: Streams live logs across all containers.
   - **`[4] Stop Services`**: Gracefully tears down all containers and networks.

---

### Method 2: Universal Docker Deployment (Linux / macOS / CLI)

To run using standard Docker Compose commands:

#### Option A: Local Deployment

```bash
cd docker
docker compose up -d --build
```

- Frontend: `http://localhost:5000`
- Backend API / Docs: `http://localhost:8000/docs`
- Langfuse Web: `http://localhost:3000`

#### Option B: Shared Online Deployment (With Cloudflare Tunnel)

```bash
cd docker
docker compose --profile tunnel up -d --build
```

Retrieve your public HTTPS link with:

```bash
docker logs cloudflare-tunnel
```

Look for the line containing `https://*.trycloudflare.com`.

#### Stopping Services

```bash
cd docker
docker compose --profile tunnel down
```

---

### Method 3: Manual Local Development (For Code Contributors)

If you are developing backend or frontend code and want hot-reloading outside Docker:

#### 1. Start Infrastructure Only

```bash
cd docker
docker compose up -d neo4j postgres redis clickhouse minio langfuse-web langfuse-worker
```

#### 2. Start FastAPI Backend

```bash
cd backend
python -m venv .venv
# On Windows: .venv\Scripts\Activate.ps1 | On Unix: source .venv/bin/activate
pip install -r pyproject.toml  # or `uv sync`
uvicorn src.main:app --reload --port 8000
```

#### 3. Start Next.js Frontend

```bash
cd frontend
npm install
npm run dev -- -p 5000
```

---

## 5. Setting Up Langfuse Observability (Optional)

On a fresh installation, Langfuse requires a 1-minute initial account creation to authorize trace collection:

1. Open **`http://localhost:3000`** in your browser.
2. Click **Sign Up** and create an administrator account (email and password remain local).
3. Create an organization and name your project (e.g., `AI-Regulation`).
4. Go to **Settings** (gear icon on bottom left) $\rightarrow$ **API Keys** $\rightarrow$ Click **Create new API keys**.
5. Copy the generated keys and update `docker/.env`:
   ```env
   LANGFUSE_PUBLIC_KEY="pk-lf-..."
   LANGFUSE_SECRET_KEY="sk-lf-..."
   ```
6. Restart the backend container to apply the keys:
   ```bash
   docker compose restart backend
   ```
7. All agent dialogues, token spending, tool calls, and latencies will now appear in your Langfuse dashboard in real time.

---

## 6. Access Points & Service Architecture

| Service               | Internal Port   | Host Binding                  | Purpose                                                               |
| --------------------- | --------------- | ----------------------------- | --------------------------------------------------------------------- |
| **Next.js Frontend**  | `5000`          | `http://localhost:5000`       | Main debate arena, network graph, trajectory charts                   |
| **Cloudflare Tunnel** | Dynamic         | `https://*.trycloudflare.com` | Secure public ingress (active when `--profile tunnel` is used)        |
| **FastAPI Backend**   | `8000`          | `http://localhost:8000`       | Orchestration, SSE turn stream, analytics computation                 |
| **Swagger Docs**      | `8000`          | `http://localhost:8000/docs`  | Interactive OpenAPI schema & endpoint testing                         |
| **Langfuse Web**      | `3000`          | `http://localhost:3000`       | LLM observability dashboard                                           |
| **PostgreSQL**        | `5432`          | `127.0.0.1:5432`              | Stores debate turns, cached metrics (`main`), and traces (`langfuse`) |
| **Neo4j Browser**     | `7474` / `7687` | `127.0.0.1:7474`              | Regulatory knowledge graph & vector index                             |
| **Redis**             | `6379`          | `127.0.0.1:6379`              | Task broker (DB 0: Langfuse, DB 1: Celery Ingestion)                  |
| **ClickHouse**        | `8123` / `9000` | `127.0.0.1:8123`              | High-throughput analytical storage for Langfuse telemetry             |
| **MinIO Console**     | `9090` / `9091` | `127.0.0.1:9091`              | S3-compatible event & snapshot storage                                |

> **Security Note**: All internal database ports (`postgres`, `neo4j`, `redis`, `clickhouse`, `minio`) are bound strictly to `127.0.0.1`. They are accessible for local developer tools (like DBeaver or Neo4j Browser) on your machine, but are completely inaccessible to external network scanners and internet traffic.

---

## 7. How to Run an End-to-End Simulation

1. Open **`http://localhost:5000`** (or your public Cloudflare Tunnel URL).
2. Click **New Simulation**.
3. Enter a debate topic or pick one from the predefined suggestions:
   - _Example:_ `"Should governments legally mandate watermarks on all AI-generated media to combat deepfakes?"\*
4. Click **Generate Personas** (dynamically constructs stakeholder backgrounds, memory settings, and stances via OpenRouter).
5. Configure the **Listening Topology**:
   - **Mesh**: Every agent hears every other agent (open panel).
   - **Ring**: Directed circular information cascade ($A \rightarrow B \rightarrow C \rightarrow A$).
   - **Custom**: Explicit agent-to-agent visibility map.
6. Click **Start Simulation**.
7. The real-time Server-Sent Events (SSE) feed will begin streaming:
   - **Speaker Selection**: Displays the current turn and active agent avatar.
   - **Live Reasoning & Speech**: Streams thinking tokens and agent dialogues in real time.
   - **Tool Executions**: Live indicators when agents execute semantic policy lookups or web searches.
   - **On-Device Stance Scoring**: Local ONNX DeBERTa grades the stance shift and dynamically updates the Trajectory Line Chart and Agreement Matrix.

---

## 8. Common Troubleshooting & FAQ

### 1. `PermissionError: [Errno 13] Permission denied: '/app/data'`

- **Cause**: Non-root `appuser` lacked write permissions to initialize runtime data directories inside the backend container.
- **Fix**: Ensure your `backend/Dockerfile` creates `/app/data` and `/app/outputs` before switching to `USER appuser`:
  ```dockerfile
  RUN mkdir -p /app/data /app/outputs && chown appuser:appuser /app /app/data /app/outputs
  ```
  Then rebuild the backend image: `docker compose build backend`.

### 2. `FATAL: database "main" does not exist`

- **Cause**: The PostgreSQL container initialized before running the custom database initialization script.
- **Fix**: Create the `main` database manually in one command:
  ```bash
  docker exec -it postgres psql -U langfuse -c "CREATE DATABASE main;"
  ```

### 3. Docker build takes an unusually long time

- **Cause**: Windows WSL2 file ownership synchronization issues during `RUN chown -R`.
- **Fix**: Ensure both `frontend/Dockerfile` and `backend/Dockerfile` use the `--chown` flag during copy operations (`COPY --chown=appuser:appuser`) rather than running recursive `RUN chown -R` after copying. Also confirm Next.js is configured with `output: "standalone"` in `frontend/next.config.ts`.

### 4. `Error verifying auth header: Invalid credentials` in `langfuse-web`

- **Cause**: Placeholder keys in `.env` do not match any project in the local Langfuse database.
- **Fix**: Log in to `http://localhost:3000`, create a project, generate new API keys, paste them into `docker/.env`, and run `docker compose restart backend`.
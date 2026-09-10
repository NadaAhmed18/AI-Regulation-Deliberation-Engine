# AI-Regulation Docker Stack

This repository defines a local, self-hosted infrastructure stack for the **AI-Regulation** project, combining LLM observability (via [Langfuse](https://langfuse.com/)) with a graph database backend (Neo4j) for modeling and analyzing relationships in AI regulation data.

The entire stack is orchestrated with **Docker Compose** and is designed to run locally for development and testing.

---

## Architecture Overview

```
                     ┌─────────────────┐
                     │   langfuse-web   │  (UI + API, port 3000)
                     └────────┬─────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   ┌────▼────┐          ┌─────▼─────┐         ┌─────▼─────┐
   │ postgres │          │ clickhouse │         │   redis   │
   │ (meta DB)│          │ (traces DB)│         │  (queue)  │
   └──────────┘          └────────────┘         └───────────┘

   ┌──────────────────┐
   │ langfuse-worker   │  (background job processor)
   └───────┬───────────┘
           │ (shares postgres, clickhouse, redis, minio)

   ┌──────────┐        ┌────────────┐
   │  minio   │◄───────┤ minio-init │ (creates 'langfuse' bucket on startup)
   │ (S3 obj  │        └────────────┘
   │  store)  │
   └──────────┘

   ┌──────────┐
   │  neo4j   │  (standalone graph database, ports 7474/7687)
   └──────────┘
```

---

## Services

| Service | Image | Purpose | Exposed Ports |
|---|---|---|---|
| **neo4j** | `neo4j:5-community` | Graph database used for modeling entities/relationships (e.g. regulations, actors, dependencies) | `7474` (HTTP Browser UI), `7687` (Bolt protocol) |
| **postgres** | `postgres:16-alpine` | Relational database backing Langfuse's application metadata | `5432` |
| **clickhouse** | `clickhouse/clickhouse-server:24` | Columnar database storing Langfuse trace/event data at scale | `8123` (HTTP), `9000` (native) |
| **redis** | `redis:7-alpine` | In-memory cache / queue broker for Langfuse background jobs | `6379` |
| **minio** | `minio/minio:latest` | S3-compatible object storage for Langfuse (e.g. large payloads, exports) | `9090` (S3 API), `9091` (Web console) |
| **minio-init** | `minio/mc:latest` | One-shot init job that creates the `langfuse` bucket on MinIO at startup, then exits | — |
| **langfuse-web** | `langfuse/langfuse:3` | Langfuse web application (dashboard + API) for LLM tracing, evaluation, and observability | `3000` |
| **langfuse-worker** | `langfuse/langfuse-worker:3` | Background worker that processes async Langfuse jobs (ingestion, aggregation, etc.) | — (internal) |

---

## How It Fits Together

- **Langfuse** (`langfuse-web` + `langfuse-worker`) provides LLM observability — tracing prompts, completions, costs, and evaluations for the AI pipelines in this project. It depends on:
  - `postgres` for relational metadata (projects, users, configs)
  - `clickhouse` for high-volume trace/event storage
  - `redis` as a job queue/cache
  - `minio` as S3-compatible blob storage (bucket auto-created by `minio-init`)
- **Neo4j** runs independently of Langfuse and serves as the graph database for the AI regulation domain model — e.g. representing relationships between laws, jurisdictions, organizations, and AI systems.

`langfuse-web` and `langfuse-worker` both wait on healthy `postgres`, `clickhouse`, `redis`, and a successfully completed `minio-init` before starting, ensuring dependencies are ready.

---

## Configuration

Each service loads its configuration from an environment file under `./env/`:

| File | Used by |
|---|---|
| `env/.env.neo4j` | neo4j |
| `env/.env.postgres` | postgres |
| `env/.env.clickhouse` | clickhouse |
| `env/.env.minio` | minio |
| `env/.env.langfuse` | langfuse-web |
| `env/.env.langfuseworker` | langfuse-worker |

> ⚠️ Redis and MinIO credentials are currently set inline in the compose file (e.g. `redis_password_change_me`, `minio_password_change_me`). **Change these before deploying anywhere beyond local development.**

---

## Data Persistence

Named Docker volumes persist data across container restarts:

- `neo4j_data`, `neo4j_logs`, `neo4j_config` — Neo4j database, logs, and configuration
- `postgres_data` — Postgres database files
- `clickhouse_data`, `clickhouse_logs` — ClickHouse data and logs
- `minio_data` — MinIO object storage

---

## Usage

### Start the stack
```bash
docker compose up -d
```

### Check service health
```bash
docker compose ps
```

### View logs for a specific service
```bash
docker compose logs -f langfuse-web
```

### Stop the stack
```bash
docker compose down
```

### Stop and remove volumes (⚠️ destroys all data)
```bash
docker compose down -v
```

---

## Access Points

Once running, the following UIs are available locally:

- **Langfuse Dashboard**: http://localhost:3000
- **Neo4j Browser**: http://localhost:7474
- **MinIO Console**: http://localhost:9091

---

## Notes

- All services use `healthcheck` directives so dependent services only start once their dependencies report healthy.
- `minio-init` is a one-shot container — it is expected to exit after creating the `langfuse` bucket; this is normal and not an error.
- For production use, review default credentials, resource limits, and volume backup strategy before deploying.
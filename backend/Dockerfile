# syntax=docker/dockerfile:1

# ==============================================================================
# Stage 1: builder — installs Python deps (uv, from uv.lock) into a venv.
# Kept separate from the runtime stage so build tools (compilers, etc.)
# never ship in the final image.
# ==============================================================================
FROM python:3.12-slim AS builder

# uv itself, copied as a static binary (no pip/network install needed).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy only the dependency manifests first, so Docker's layer cache is
# reused on every rebuild where pyproject.toml/uv.lock haven't changed --
# this is what makes `docker compose build` fast on code-only changes,
# instead of re-downloading torch/transformers/onnxruntime every time.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Now copy the actual source and install the project itself.
COPY . .
RUN uv sync --frozen --no-dev

# ==============================================================================
# Stage 2: runtime — slim image, only what's needed to actually run the app.
# ==============================================================================
FROM python:3.12-slim AS runtime

# System dependencies for:
#   - crawl4ai (headless Chromium via Playwright) -- src/rag/stages/scraper.py
#   - psycopg2 (libpq) -- src/clients/postgres.py
#   - curl -- container healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    wget \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create user first so we can assign ownership directly during copy (avoids 34-min chown)
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app
COPY --chown=appuser:appuser --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH"
ENV PLAYWRIGHT_BROWSERS_PATH="/ms-playwright"

RUN playwright install --with-deps chromium \
    && chmod -R 755 /ms-playwright

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

# Eager model loading happens in src/main.py's lifespan handler (loads
# the ONNX NLI grader into memory on startup) -- so the healthcheck's
# --start-period gives that time to finish before failures count against
# the container's health status.
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
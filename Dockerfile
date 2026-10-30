# syntax=docker/dockerfile:1

# ---- Stage 1: build the React SPA ------------------------------------------
FROM node:22-alpine AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: FastAPI backend serving the built SPA -------------------------
# Core requirements only (scikit-learn stack). Heavy transformer weights are
# opt-in: set SENTINEX_ENABLE_DISTILBERT=true to download DistilBERT on first
# use (~270 MB) — the container runs CPU-only either way.
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY backend/requirements.txt backend/requirements-full.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/app ./backend/app
COPY backend/alembic ./backend/alembic
COPY backend/alembic.ini ./backend/
COPY backend/artifacts ./backend/artifacts
COPY backend/ml ./backend/ml
COPY backend/pyproject.toml ./backend/
COPY models ./models
COPY --from=frontend-build /build/dist ./frontend/dist

# Non-root runtime user; runtime state (SQLite DB, uploads) lives in a volume.
RUN useradd --create-home sentinex \
    && mkdir -p /app/backend/.runtime \
    && chown -R sentinex:sentinex /app
USER sentinex
VOLUME ["/app/backend/.runtime"]

EXPOSE 8000
# Render/Railway inject $PORT; local compose falls back to 8000.
ENV SENTINEX_HOST=0.0.0.0
CMD ["sh", "-c", "cd backend && alembic upgrade head && uvicorn app.main:app --host ${SENTINEX_HOST} --port ${PORT:-8000}"]

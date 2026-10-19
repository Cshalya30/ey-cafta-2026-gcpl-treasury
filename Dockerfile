# syntax=docker/dockerfile:1
#
# One image, one origin, one process.
#
# The page and the API must share an origin: web/src/lib/api.ts calls /api/v1
# as a relative path and the CSRF guard is a double-submit cookie pair. So the
# app is built here and FastAPI serves it alongside the API, exactly as
# docs/PRD.md section 6.1 describes.

# ───────────────────────── stage 1: build the app ─────────────────────────
FROM node:22-bookworm-slim AS web

WORKDIR /build

# Dependencies resolve from the lockfile alone, so this layer is reused on any
# change that does not touch package.json.
COPY web/package.json web/package-lock.json ./
RUN npm ci

COPY web/ ./
# Runs `tsc -b && vite build`: a type error fails the image rather than
# shipping a broken console.
RUN npm run build


# ───────────────────────── stage 2: the API that serves it ─────────────────
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    GCPL_DB_PATH=/app/data/gcpl.db

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# The generator imports api.services and api.models, so the package has to be
# in place before the seed step below.
COPY api/ ./api/
COPY scripts/ ./scripts/
COPY --from=web /build/dist ./web/dist

# Seed at build time, not at boot: a container restart then serves instantly
# instead of regenerating. --seed 42 is the canonical dataset, and the
# generator asserts INV-1 through INV-3 and exits non-zero if one fails, so a
# broken invariant fails the build here rather than surfacing in front of a
# judge.
RUN python scripts/generate_data.py --seed 42

# The data directory must be writable at runtime: proposals, approvals and the
# hash-chained audit trail are all writes. The filesystem is ephemeral, so a
# redeploy or a restart returns the demo to the seeded state, which is the
# behaviour we want for a shared public link.
RUN useradd --create-home --uid 10001 gcpl && chown -R gcpl:gcpl /app/data
USER gcpl

EXPOSE 8000

# Shell form so ${PORT} expands. Render, Railway and Fly inject PORT; Hugging
# Face Spaces expects 7860. --proxy-headers makes request.url.scheme reflect
# the TLS terminated in front of us rather than the plain HTTP hop behind it.
CMD exec uvicorn api.main:app \
      --host 0.0.0.0 \
      --port ${PORT:-8000} \
      --proxy-headers \
      --forwarded-allow-ips="*"

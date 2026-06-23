# syntax=docker/dockerfile:1

# --- Stage 1: build the React/Vite single-page app ---
FROM node:24-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# The dev-only proxy throws if OPENAI_API_KEY is missing; provide a dummy for the
# build step (it is never used at build time, only the production bundle matters).
ENV OPENAI_API_KEY=build-placeholder
RUN npm run build

# --- Stage 2: Python runtime serving the API and the built SPA ---
FROM python:3.12-slim AS runtime
WORKDIR /app/backend

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
# Place the built SPA where main.py expects it (../frontend/dist).
COPY --from=frontend /app/frontend/dist /app/frontend/dist

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

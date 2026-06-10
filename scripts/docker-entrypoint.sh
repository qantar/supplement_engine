#!/bin/bash
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting API server..."
LOG_LEVEL_LOWER="$(echo "${LOG_LEVEL:-info}" | tr '[:upper:]' '[:lower:]')"
exec uvicorn src.api.app:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers 4 \
    --loop uvloop \
    --access-log \
    --log-level "${LOG_LEVEL_LOWER}"

#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LANGFUSE_DIR="$PROJECT_ROOT/infra/langfuse"
LANGFUSE_URL="http://localhost:3000"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not installed."
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: docker compose plugin is not available."
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "ERROR: curl is required for the health check."
  exit 1
fi

if [ ! -f "$LANGFUSE_DIR/.env" ]; then
  cp "$LANGFUSE_DIR/.env.example" "$LANGFUSE_DIR/.env"
  echo "Created $LANGFUSE_DIR/.env from .env.example"
fi

echo "Starting Langfuse services..."
docker compose -f "$LANGFUSE_DIR/docker-compose.yml" --env-file "$LANGFUSE_DIR/.env" up -d

echo "Waiting for Langfuse to become ready..."
for _ in $(seq 1 90); do
  if curl -sf "$LANGFUSE_URL/api/public/health" >/dev/null 2>&1; then
    echo "Langfuse is ready at $LANGFUSE_URL"
    echo "Admin: admin@local.dev / changeme-admin-password"
    echo "Public Key: pk-lf-local-dev"
    echo "Secret Key: sk-lf-local-dev"
    exit 0
  fi
  sleep 2
done

echo "ERROR: Langfuse did not become healthy within 180 seconds."
echo "Check logs with:"
echo "  docker compose -f \"$LANGFUSE_DIR/docker-compose.yml\" --env-file \"$LANGFUSE_DIR/.env\" logs"
exit 1

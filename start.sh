#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f .env ]; then
    cp .env.example .env
    echo "[AIDE] .env created from .env.example -- please fill in your API keys"
fi

echo "[AIDE] Building and starting all services..."
docker compose up --build -d

echo ""
echo "[AIDE] Waiting for services to be ready..."
sleep 3

echo ""
echo "========================================="
echo "  AIDE is running"
echo "========================================="
echo "  Frontend:  http://localhost:30000"
echo "  Backend:   http://localhost:30001"
echo "  API Docs:  http://localhost:30001/docs"
echo "  Health:    http://localhost:30001/health"
echo "  ChromaDB:  http://localhost:30002"
echo "  Postgres:  localhost:30003"
echo "========================================="
echo ""
echo "  Logs:  docker compose logs -f"
echo "  Stop:  ./stop.sh"
echo "========================================="

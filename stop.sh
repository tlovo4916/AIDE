#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "[AIDE] Stopping all services..."
docker compose down

echo "[AIDE] All services stopped."
echo ""
echo "  To also remove data volumes: docker compose down -v"

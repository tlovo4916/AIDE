#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ── .env bootstrap ────────────────────────────────────────────────
if [ ! -f .env ]; then
    cp .env.example .env
    echo "[AIDE] .env created from .env.example -- please fill in your API keys"
fi

# Detect new keys added in .env.example that are missing from .env
# (non-destructive: only appends missing keys with their defaults)
_missing=0
while IFS= read -r line; do
    # Skip comments and blank lines
    [[ "$line" =~ ^#.*$ || -z "$line" ]] && continue
    key="${line%%=*}"
    if ! grep -q "^${key}=" .env 2>/dev/null; then
        echo "$line" >> .env
        _missing=$((_missing + 1))
    fi
done < .env.example
if [ "$_missing" -gt 0 ]; then
    echo "[AIDE] Added $_missing new config keys to .env (from .env.example)"
fi

# ── Build & Start ─────────────────────────────────────────────────
echo "[AIDE] Building and starting all services..."
docker compose up --build -d

# ── Health check ──────────────────────────────────────────────────
echo ""
echo "[AIDE] Waiting for services to be ready..."
_max=30
_i=0
while [ "$_i" -lt "$_max" ]; do
    if docker compose exec -T backend python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" >/dev/null 2>&1; then
        break
    fi
    sleep 1
    _i=$((_i + 1))
done

if [ "$_i" -ge "$_max" ]; then
    echo "[AIDE] WARNING: Backend did not become healthy within ${_max}s"
    echo "  Check logs:  docker compose logs backend"
else
    echo "[AIDE] Backend healthy after ~${_i}s"
fi

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

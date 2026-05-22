#!/usr/bin/env bash
#
# deploy-dev.sh — start a live Vite dev server (with HMR) for one of the apps
# in this workspace. Visit the URL printed at the end in a browser; saving a
# source file refreshes the page automatically.
#
# Usage:
#   ./deploy-dev.sh <app>             # e.g. status-hub, movies-feed, …
#   ./deploy-dev.sh <app> <port>      # custom port (default 5173)
#   ./deploy-dev.sh stop              # stop whatever dev server is running
#   ./deploy-dev.sh                   # no args → list available apps
#
# Notes:
#   - Only one dev server runs at a time; starting a new one stops the previous.
#   - Node/npm isn't installed on the tower; this runs everything inside
#     `node:22-alpine` and mounts the workspace as a volume. The first run on
#     a fresh container takes ~30s (npm install). Subsequent runs reuse the
#     workspace `node_modules/` and start in ~3s.
#   - The container has `host.docker.internal` mapped so Vite's `/api` proxy
#     reaches announcement-api on the host port 5050, just like in production.

set -euo pipefail

WS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DEV_CONTAINER="vite-dev"
DEFAULT_PORT=5173

# ── Subcommand: stop ───────────────────────────────────────────────────────
if [[ "${1:-}" == "stop" ]]; then
  if docker ps -aq --filter "name=^${DEV_CONTAINER}$" | grep -q .; then
    docker rm -f "$DEV_CONTAINER" >/dev/null
    echo "Stopped $DEV_CONTAINER."
  else
    echo "No dev container running."
  fi
  exit 0
fi

# ── Discover available apps (any folder with a vite.config.js) ─────────────
list_apps() {
  for d in "$WS_DIR"/*/; do
    [[ -f "$d/vite.config.js" ]] || continue
    name=$(basename "$d")
    base=$(grep -oE "base:[[:space:]]*'[^']+'" "$d/vite.config.js" | head -1 | sed -E "s/base:[[:space:]]*'(.*)'/\1/")
    printf "  %-22s %s\n" "$name" "(${base:-/})"
  done
}

if [[ -z "${1:-}" ]]; then
  echo "Usage: $(basename "$0") <app> [port]"
  echo "       $(basename "$0") stop"
  echo ""
  echo "Available apps (with base path):"
  list_apps
  exit 1
fi

NAME="$1"
PORT="${2:-$DEFAULT_PORT}"

if [[ ! -d "$WS_DIR/$NAME" || ! -f "$WS_DIR/$NAME/vite.config.js" ]]; then
  echo "Error: '$NAME' isn't a Vite app under $WS_DIR/"
  echo ""
  echo "Available apps:"
  list_apps
  exit 1
fi

# ── Stop any container holding our target port, plus our named dev container
# (covers the case where a prior attempt used a different container name). ──
holders=$(docker ps -q --filter "publish=${PORT}")
if [[ -n "$holders" ]]; then
  echo "Stopping container(s) on port ${PORT}: $(docker ps --format '{{.Names}}' --filter "publish=${PORT}" | xargs)"
  docker rm -f $holders >/dev/null
fi
if docker ps -aq --filter "name=^${DEV_CONTAINER}$" | grep -q .; then
  docker rm -f "$DEV_CONTAINER" >/dev/null
fi

# ── Discover the app's base path so we can print a working URL ─────────────
BASE=$(grep -oE "base:[[:space:]]*'[^']+'" "$WS_DIR/$NAME/vite.config.js" | head -1 | sed -E "s/base:[[:space:]]*'(.*)'/\1/")
BASE="${BASE:-/}"

# ── Tower LAN IP (first non-loopback v4) ───────────────────────────────────
TOWER_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
TOWER_IP="${TOWER_IP:-localhost}"

URL_LAN="http://${TOWER_IP}:${PORT}${BASE}"
URL_LOCAL="http://localhost:${PORT}${BASE}"

# ── Start the dev server in the background ─────────────────────────────────
echo "Starting Vite dev server for '$NAME' on port $PORT…"
docker run -d --name "$DEV_CONTAINER" \
  -v "$WS_DIR:/app" -w /app \
  -p "${PORT}:${PORT}" \
  --add-host=host.docker.internal:host-gateway \
  node:22-alpine \
  sh -c "npm install --silent && npm run dev -w $NAME -- --host 0.0.0.0 --port $PORT" \
  >/dev/null

# ── Wait for Vite to be ready (poll the port; bail after ~60s) ─────────────
echo -n "Waiting for Vite to boot"
for i in {1..60}; do
  if curl -sf "http://localhost:${PORT}${BASE}" >/dev/null 2>&1; then
    echo " ready."
    break
  fi
  if ! docker ps -q --filter "name=^${DEV_CONTAINER}$" | grep -q .; then
    echo ""
    echo "Container died while booting. Last logs:"
    docker logs "$DEV_CONTAINER" 2>&1 | tail -20
    exit 1
  fi
  echo -n "."
  sleep 1
done

echo ""
echo "✓ Dev server live for '$NAME'"
echo "  LAN:   $URL_LAN"
echo "  local: $URL_LOCAL"
echo ""
echo "  follow logs:  docker logs -f $DEV_CONTAINER"
echo "  stop:         $(basename "$0") stop"

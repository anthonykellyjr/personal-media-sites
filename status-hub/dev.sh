#!/bin/bash
# Hot-reload dev server via Docker
# Access at http://10.0.0.222:5173/status/
# Ctrl+C to stop

set -e
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "Starting Vite dev server with HMR..."
echo "→ http://10.0.0.222:5173/status/"
echo ""

docker run --rm -it \
  -v "$DIR:/app" \
  -w /app \
  -p 5173:5173 \
  --add-host=host.docker.internal:host-gateway \
  node:22-alpine \
  sh -c "npm install --silent && npm run dev"

#!/bin/bash
# Build Vue apps using Docker (no node/npm on the tower)
# Usage:
#   ./deploy.sh              # Build all apps
#   ./deploy.sh status-hub   # Build one app
#   ./deploy.sh status-hub collection-manager  # Build specific apps

set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPS=(status-hub collection-manager movies-feed kelly-collection tutorials)

# If args given, build only those
if [ $# -gt 0 ]; then
  APPS=("$@")
fi

echo "Installing dependencies..."
docker run --rm -v "$DIR:/app" -w /app node:22-alpine sh -c "npm install --silent"

for app in "${APPS[@]}"; do
  echo ""
  echo "Building $app..."
  docker run --rm -v "$DIR:/app" -w /app node:22-alpine sh -c "npm run build -w $app"
done

echo ""
echo "Done! Built: ${APPS[*]}"

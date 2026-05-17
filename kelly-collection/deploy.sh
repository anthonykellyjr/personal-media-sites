#!/bin/bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
echo "Building Kelly's Collection..."

docker run --rm -v "$DIR:/app" -w /app node:22-alpine sh -c "npm install --silent && npm run build"

echo "Kelly's Collection deployed!"
echo "View at: https://akplex.tv/kelly/"

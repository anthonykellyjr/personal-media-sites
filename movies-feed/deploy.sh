#!/bin/bash
set -e

echo "🎬 Deploying Movies Feed..."

# Build using Docker (no node/npm needed on server)
echo "📦 Building with Vite..."
docker run --rm -v "$(pwd):/app" -w /app node:22-alpine sh -c "npm install --silent && npm run build"

echo "✅ Movies Feed deployed successfully!"
echo "🌐 View at: https://akplex.tv/movies-added/"

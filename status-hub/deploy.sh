#!/bin/bash
# @file deploy.sh
# @description Build Status Hub using npm container from web-routing stack
# @usage ./deploy.sh
#
# IMPORTANT: Node/npm is NOT installed on the tower system.
# This script uses the 'npm' container (nginx-proxy-manager) which has:
#   - Node v22.22.0
#   - npm 10.9.4

set -e
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "Building status-hub using npm container..."
docker run --rm -v "$DIR:/app" -w /app node:22-alpine sh -c "npm install --silent && npm run build"

echo "✓ Built to dist/ - live at https://akplex.tv/home/"

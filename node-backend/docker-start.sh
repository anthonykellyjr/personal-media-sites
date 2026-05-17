#!/bin/sh
cd /app

# Install docker CLI if not present
if ! command -v docker &> /dev/null; then
    echo "Installing Docker CLI..."
    apk add --no-cache docker-cli
fi

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi

# Start the application
echo "Starting application..."
node index.js
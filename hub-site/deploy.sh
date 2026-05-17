#!/bin/bash
# @file deploy.sh
# @description Deploy Status Hub - just copy files, no build needed
# @usage ./deploy.sh

set -e
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

docker cp "$DIR/index.html" web-router:/var/www/html/status/
docker cp "$DIR/style.css" web-router:/var/www/html/status/
docker cp "$DIR/components/." web-router:/var/www/html/status/components/
docker cp "$DIR/images/." web-router:/var/www/html/status/images/

echo "✓ Deployed to akplex.tv/status/"

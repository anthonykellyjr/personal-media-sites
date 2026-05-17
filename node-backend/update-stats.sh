#!/bin/bash
# /home/anthony/DockerApps/websites/node-backend/update-stats.sh

while true; do
  docker stats --no-stream --format "json" > /home/anthony/DockerApps/websites/node-backend/docker-stats.json
  sleep 5
done
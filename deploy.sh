#!/bin/bash
# Deploy a page in this workspace.
#
# Usage:
#   ./deploy.sh <page>               # deploy one page (Vue: build it; static HTML: already live)
#   ./deploy.sh <page1> <page2> …    # multiple
#   ./deploy.sh                      # build all Vue apps (back-compat)
#
# Node/npm isn't on the tower, so Vue builds run inside node:22-alpine.
# Static HTML pages are bind-mounted into web-router, so edits go live the
# moment you save the file — there's nothing to "deploy".

set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ALL_VUE=(status-hub collection-manager movies-feed kelly-collection tutorials)

# No args → build all Vue apps (back-compat with the old behavior)
if [ $# -eq 0 ]; then
  set -- "${ALL_VUE[@]}"
fi

# Classify each arg: vue (has vite.config.js) | static (dir exists but no Vite) | unknown
vue_apps=()
static_pages=()
unknown=()
for arg in "$@"; do
  if [ -f "$DIR/$arg/vite.config.js" ]; then
    vue_apps+=("$arg")
  elif [ -d "$DIR/$arg" ]; then
    static_pages+=("$arg")
  else
    unknown+=("$arg")
  fi
done

# Fail fast on unknown names
if [ ${#unknown[@]} -gt 0 ]; then
  echo "Error: not a page in this workspace: ${unknown[*]}"
  echo ""
  echo "Vue apps (built via Docker):"
  echo "Static HTML pages (bind-mounted, no build needed):" > /tmp/static-list.$$
  for d in "$DIR"/*/; do
    name="${d%/}"; name="${name##*/}"
    case "$name" in node_modules|packages) continue ;; esac
    if [ -f "$d/vite.config.js" ]; then
      printf "  %s\n" "$name"
    else
      printf "  %s\n" "$name" >> /tmp/static-list.$$
    fi
  done
  echo ""
  cat /tmp/static-list.$$ && rm -f /tmp/static-list.$$
  exit 1
fi

# Vue apps: install workspace deps once, then build each
if [ ${#vue_apps[@]} -gt 0 ]; then
  echo "Installing workspace dependencies…"
  docker run --rm -v "$DIR:/app" -w /app node:22-alpine sh -c "npm install --silent"
  for app in "${vue_apps[@]}"; do
    echo ""
    echo "Building $app…"
    docker run --rm -v "$DIR:/app" -w /app node:22-alpine sh -c "npm run build -w $app"
  done
fi

# Static pages: just acknowledge — they're already live via bind mount
for p in "${static_pages[@]}"; do
  echo "$p — static HTML, bind-mounted into web-router. Edits are already live."
done

echo ""
if [ ${#vue_apps[@]} -gt 0 ]; then
  echo "Done! Built: ${vue_apps[*]}"
fi

#!/usr/bin/env bash
# Deploy an image tag with docker compose. Run a health check afterwards; if it fails,
# redeploy the previously deployed tag and exit non-zero so the pipeline goes red.
# Usage: deploy.sh <image-tag>
set -euo pipefail
cd "$(dirname "$0")/.."

NEW_TAG="${1:?usage: deploy.sh <image-tag>}"
STATE_DIR=".deploy"
STATE_FILE="$STATE_DIR/current_tag"
HEALTH_URL="${HEALTH_URL:-http://localhost:8000/healthz}"
mkdir -p "$STATE_DIR"
PREV_TAG="$(cat "$STATE_FILE" 2>/dev/null || true)"

echo "Deploying $NEW_TAG (previous: ${PREV_TAG:-none})"
IMAGE_TAG="$NEW_TAG" docker compose up -d --no-build

if scripts/check_healthz.sh "$HEALTH_URL" 15; then
  echo "$NEW_TAG" > "$STATE_FILE"
  echo "Deployed $NEW_TAG"
  exit 0
fi

echo "Health check failed for $NEW_TAG" >&2
docker compose logs --tail 30 assistant >&2 || true
if [ -n "$PREV_TAG" ]; then
  echo "Rolling back to $PREV_TAG" >&2
  IMAGE_TAG="$PREV_TAG" docker compose up -d --no-build
  scripts/check_healthz.sh "$HEALTH_URL" 15
  echo "Rolled back to $PREV_TAG" >&2
else
  echo "No previous tag to roll back to; stopping the service" >&2
  docker compose down
fi
exit 1

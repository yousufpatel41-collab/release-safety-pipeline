#!/usr/bin/env bash
# Prove the rollback works: deploy a good release, then a deliberately broken one,
# and assert the service ends up on the good release again.
# Usage: rollback_drill.sh <good-tag> <broken-tag>
set -euo pipefail
cd "$(dirname "$0")/.."

GOOD="${1:?usage: rollback_drill.sh <good-tag> <broken-tag>}"
BROKEN="${2:?usage: rollback_drill.sh <good-tag> <broken-tag>}"

rm -rf .deploy
scripts/deploy.sh "$GOOD"

if scripts/deploy.sh "$BROKEN"; then
  echo "DRILL FAILED: the broken release was accepted" >&2
  exit 1
fi

CURRENT="$(cat .deploy/current_tag)"
if [ "$CURRENT" != "$GOOD" ]; then
  echo "DRILL FAILED: expected $GOOD after rollback, found $CURRENT" >&2
  exit 1
fi
scripts/check_healthz.sh http://localhost:8000/healthz 10
docker compose down
echo "rollback drill passed: broken release $BROKEN was rejected, $GOOD restored"

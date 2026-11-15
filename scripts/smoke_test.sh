#!/usr/bin/env bash
# Smoke test a running container: health, version and one real question.
# Usage: smoke_test.sh [base_url]
set -euo pipefail
BASE="${1:-http://localhost:8000}"

"$(dirname "$0")/check_healthz.sh" "$BASE/healthz"
curl -fsS "$BASE/version" | grep -q '"version"'

ANSWER=$(curl -fsS --get "$BASE/ask" \
  --data-urlencode "question=VPN will not connect" --data-urlencode "client=acme")
echo "$ANSWER" | grep -q '"source":"shared-002"'
echo "smoke test passed"

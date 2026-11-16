#!/usr/bin/env bash
# Verify health, version, auth and a tenant-isolated runbook request.
set -euo pipefail
BASE="${1:-http://localhost:8000}"
"$(dirname "$0")/check_healthz.sh" "$BASE/healthz"
curl -fsS "$BASE/version" | grep -q '"version"'
[ -n "${DEMO_AUTH_VALUE:-}" ] || { echo "Set DEMO_AUTH_VALUE for demo user" >&2; exit 1; }

TOKEN=$(curl -fsS -X POST "$BASE/auth/token" -H 'Content-Type: application/json' \
    -d "$(python -c 'import json,os; print(json.dumps({"username":"demo","password":os.environ["DEMO_AUTH_VALUE"]}))')" \
    | python -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

# Missing authentication must be rejected.
UNAUTH=$(curl -sS -o /dev/null -w '%{http_code}' -X POST "$BASE/ask" \
    -H 'Content-Type: application/json' -d '{"question":"VPN will not connect"}')
[ "$UNAUTH" = "401" ] || { echo "Authentication bypass detected: $UNAUTH" >&2; exit 1; }

ANSWER=$(curl -fsS -X POST "$BASE/ask" \
    -H 'Content-Type: application/json' -H "Authorization: Bearer $TOKEN" \
    -d '{"question":"VPN will not connect"}')
echo "$ANSWER" | grep -q '"source":"shared-002"'
echo "Authenticated smoke test passed"

#!/usr/bin/env bash
# Poll a health endpoint. Exit 0 = OK, 2 = CRITICAL (Nagios/Icinga-style plugin convention).
# Usage: check_healthz.sh [url] [attempts]
set -u
URL="${1:-http://localhost:8000/healthz}"
ATTEMPTS="${2:-20}"

for _ in $(seq 1 "$ATTEMPTS"); do
  if curl -fsS --max-time 3 "$URL" >/dev/null 2>&1; then
    echo "OK - $URL is healthy"
    exit 0
  fi
  sleep 1
done
echo "CRITICAL - $URL did not become healthy after $ATTEMPTS attempts"
exit 2

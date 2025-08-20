#!/usr/bin/env bash
set -euo pipefail

curl -X POST http://localhost:8000/orders \
  -H 'Content-Type: application/json' \
  -H "Idempotency-Key: $RANDOM" \
  -d '{"product":"demo"}'

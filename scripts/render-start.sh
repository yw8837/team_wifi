#!/usr/bin/env bash
set -euo pipefail
if [ "${ASSISTANT_SSH_ENABLED:-false}" = "true" ]; then
  ASSISTANT_SSH_PRIVATE_KEY_PATH="$(python scripts/prepare-inference-key.py)"
  export ASSISTANT_SSH_PRIVATE_KEY_PATH
fi
cd backend
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --no-access-log --limit-concurrency 12 --timeout-keep-alive 5

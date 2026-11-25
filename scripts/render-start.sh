#!/usr/bin/env bash
set -euo pipefail
if [[ "${RENDER_EXTERNAL_URL:-}" == "https://moduyuga-beta.onrender.com" && "${MODU_ENV:-}" == "public_release" ]]; then
  # The production API and source-backed assistant must start without a GPU host.
  export ASSISTANT_SSH_ENABLED=false ASSISTANT_SSH_OBSERVE_ENABLED=false
  export ASSISTANT_MODEL_ENABLED=false ASSISTANT_OPIK_ENABLED=false
  (
    # Keep collection off the request path. The existing scheduler catches up
    # on startup and then refreshes at midnight in Korea while the instance runs.
    while true; do
      python scripts/collect-external-groupbuys.py --service-environment --apply --discover --daily-midnight \
        --output "${RUNTIME_DIR:-/tmp/moduyuga}/catalogue-receipt.json" || true
      sleep 300
    done
  ) &
elif [ "${ASSISTANT_SSH_ENABLED:-false}" = "true" ]; then
  ASSISTANT_SSH_PRIVATE_KEY_PATH="$(python scripts/prepare-inference-key.py)"
  export ASSISTANT_SSH_PRIVATE_KEY_PATH
fi
cd backend
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --no-access-log --limit-concurrency 12 --timeout-keep-alive 5

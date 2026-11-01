#!/usr/bin/env bash
set -euo pipefail
export PUBLIC_ORIGIN="${PUBLIC_ORIGIN:-${RENDER_EXTERNAL_URL:-}}"
: "${PUBLIC_ORIGIN:?Set the actual HTTPS service origin before building}"
npm --prefix frontend ci
VITE_BETA_MODE=1 VITE_API_BASE_URL="$PUBLIC_ORIGIN/api" npm --prefix frontend run build
python -m pip install -r backend/requirements.txt

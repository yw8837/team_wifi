#!/usr/bin/env bash
set -euo pipefail
: "${RENDER_EXTERNAL_URL:?Static service URL is required}"
: "${VITE_API_BASE_URL:?Set the existing HTTPS API URL}"
export VITE_PUBLIC_RELEASE=1 VITE_BETA_MODE=0
export VITE_PUBLIC_WEB_ORIGIN="$RENDER_EXTERNAL_URL"
npm --prefix frontend ci
npm --prefix frontend run build
python3 scripts/export-public-policies.py
python3 scripts/export-public-guides.py

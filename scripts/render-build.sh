#!/usr/bin/env bash
set -euo pipefail
export PUBLIC_ORIGIN="${PUBLIC_ORIGIN:-${RENDER_EXTERNAL_URL:-}}"
: "${PUBLIC_ORIGIN:?Set the actual HTTPS service origin before building}"
npm --prefix frontend ci
case "${MODU_ENV:-}" in
  beta) export VITE_BETA_MODE=1 VITE_PUBLIC_RELEASE=0 ;;
  public_release) export VITE_BETA_MODE=0 VITE_PUBLIC_RELEASE=1 ;;
  *) echo 'MODU_ENV must be beta or public_release for a hosted build' >&2; exit 1 ;;
esac
VITE_API_BASE_URL="$PUBLIC_ORIGIN/api" npm --prefix frontend run build
python -m pip install -r backend/requirements.txt

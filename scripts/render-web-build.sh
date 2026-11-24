#!/usr/bin/env bash
set -euo pipefail
: "${RENDER_EXTERNAL_URL:?Static service URL is required}"

# The retired Render hostname still appears in old messages and bookmarks.
# Publish a small entry page there, including for the physical index.html that
# Render serves before evaluating its redirect rules. Preserve deep links.
if [[ "${RENDER_EXTERNAL_URL%/}" == "https://moduyuga.onrender.com" ]]; then
  mkdir -p frontend/dist
  cat > frontend/dist/index.html <<'HTML'
<!doctype html>
<html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>모두의 육아</title>
<link rel="canonical" href="https://moduyuga.yeolmaeapps.kr/">
<meta property="og:title" content="모두의 육아">
<meta property="og:image" content="https://moduyuga.yeolmaeapps.kr/brand/share-cover-v1.png">
<script>location.replace("https://moduyuga.yeolmaeapps.kr" + location.pathname + location.search + location.hash);</script>
</head><body><a href="https://moduyuga.yeolmaeapps.kr/">모두의 육아 열기</a></body></html>
HTML
  exit 0
fi
: "${VITE_API_BASE_URL:?Set the existing HTTPS API URL}"
export VITE_PUBLIC_RELEASE=1 VITE_BETA_MODE=0
export VITE_PUBLIC_WEB_ORIGIN="$RENDER_EXTERNAL_URL"
npm --prefix frontend ci
npm --prefix frontend run build
python3 scripts/export-public-policies.py
python3 scripts/export-public-guides.py

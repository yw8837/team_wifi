# Render the original brand via a local HTML page; capture exports with CUA.
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$out = Join-Path $root 'artifacts/store/release-4'
New-Item -ItemType Directory -Path $out -Force | Out-Null
foreach ($name in @('symbol.svg','wordmark.png')) {
  Copy-Item -LiteralPath (Join-Path $root ('frontend/public/brand/'+$name)) -Destination (Join-Path $out $name) -Force
}
$html = @'
<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>모두의육아 스토어 이미지 원본 렌더</title>
<style>*{box-sizing:border-box}body{margin:0;background:#fff5e7;color:#4f382e;font-family:"Malgun Gothic",sans-serif}.icon{width:512px;height:512px;display:grid;place-items:center;background:#fff5e7}.icon img{width:360px;height:auto}.feature{width:1024px;height:500px;background:#fff5e7;display:flex;align-items:center;gap:64px;padding:60px 72px}.feature .symbol{width:250px;height:auto}.copy{flex:1}.wordmark{width:390px;max-height:150px;object-fit:contain;object-position:left center}h1{font-size:36px;line-height:1.45;margin:30px 0 16px;letter-spacing:-1.8px}p{font-size:18px;line-height:1.7;margin:0}small{font-size:14px;display:block;margin-top:22px}.feature{display:none}body.feature-mode .icon{display:none}body.feature-mode .feature{display:flex}</style>
</head><body><div class="icon" aria-label="모두의육아 앱 아이콘"><img src="symbol.svg" alt="쪽쪽이 심볼"></div><div class="feature"><img class="symbol" src="symbol.svg" alt=""><div class="copy"><img class="wordmark" src="wordmark.png" alt="모두의육아"><h1>함께 알아보고,<br>필요한 공구를 이야기해요</h1><p>육아 정보 탐색 · 단가 비교 · 공구 수요</p><small>Team_Wifi</small></div></div><script>if(location.search==="?feature")document.body.className="feature-mode";</script></body></html>
'@
[IO.File]::WriteAllText((Join-Path $out 'index.html'), $html, [Text.UTF8Encoding]::new($false))
Write-Output 'STORE_ASSET_RENDER_SOURCE_READY'

[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$WebOrigin,
    [Parameter(Mandatory)][string]$ApiBase,
    [Parameter(Mandatory)][string]$HostingLocation,
    [Parameter(Mandatory)][string]$DatabaseLocation,
    [Parameter(Mandatory)][string]$SupportEmail
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/use-workspace.ps1"
foreach ($address in @($WebOrigin, $ApiBase)) {
    $parsed = [Uri]$address
    if (-not $parsed.IsAbsoluteUri -or $parsed.Scheme -ne 'https' -or $parsed.UserInfo -or $parsed.Query -or $parsed.Fragment) {
        throw 'Use an HTTPS URL without credentials, query or fragment.'
    }
}
if (([Uri]$WebOrigin).AbsolutePath -ne '/') { throw 'WebOrigin must contain only the public origin.' }
$WebOrigin = $WebOrigin.TrimEnd('/')
$ApiBase = $ApiBase.TrimEnd('/')
$output = 'E:/Team_Wifi/artifacts/hosting-migration-20261107/cloudflare-web'
$env:VITE_PUBLIC_RELEASE = '1'
$env:VITE_BETA_MODE = '0'
$env:VITE_PUBLIC_WEB_ORIGIN = $WebOrigin
$env:VITE_API_BASE_URL = $ApiBase
$env:HOSTING_LOCATION = $HostingLocation
$env:DATABASE_LOCATION = $DatabaseLocation
$env:SUPPORT_EMAIL = $SupportEmail
npm --prefix frontend run build -- --outDir $output
if ($LASTEXITCODE) { throw 'Public web build failed.' }
foreach ($exporter in @('export-public-policies.py', 'export-public-guides.py')) {
    & backend/.venv/Scripts/python.exe "scripts/$exporter" --output-dir $output
    if ($LASTEXITCODE) { throw "Public export failed: $exporter" }
}
# Existing exporters contain canonical links for the previous public origin.
# Update only generated public text documents, never source or saved user data.
Get-ChildItem -LiteralPath $output -Recurse -File | Where-Object Extension -In '.html', '.xml', '.txt' | ForEach-Object {
    $content = [IO.File]::ReadAllText($_.FullName)
    [IO.File]::WriteAllText($_.FullName, $content.Replace('https://moduyuga.onrender.com', $WebOrigin), [Text.UTF8Encoding]::new($false))
}
Copy-Item -LiteralPath "$PSScriptRoot/cloudflare-public-worker.mjs" -Destination "$output/_worker.js"
@{ version = 1; include = @('/groupbuys/*'); exclude = @() } | ConvertTo-Json | Set-Content "$output/_routes.json"
@'
/legal/:kind /legal/:kind/index.html 200
/* /index.html 200
'@ | Set-Content "$output/_redirects"
@'
/*
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Referrer-Policy: strict-origin-when-cross-origin
'@ | Set-Content "$output/_headers"
@{ web_origin = $WebOrigin; api_base = $ApiBase; required_pages_binding = @{ PUBLIC_API_BASE = $ApiBase }; output_directory = $output } |
    ConvertTo-Json -Depth 4 | Set-Content 'E:/Team_Wifi/artifacts/hosting-migration-20261107/cloudflare-build.json'
Write-Output "Cloudflare public web ready: $output"

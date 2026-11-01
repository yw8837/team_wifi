# Dot-source: . E:/Team_Wifi/scripts/use-workspace.ps1
$teamWifiRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if ($teamWifiRoot.TrimEnd('\','/') -ne 'E:\Team_Wifi') {
  throw 'This project must run from E:/Team_Wifi. Connect the approved drive; do not create a C/D fallback.'
}
foreach ($relativePath in @('.runtime/tmp','.runtime/gradle','.runtime/npm-cache','.runtime/pip-cache','.runtime/uv-cache')) {
  New-Item -ItemType Directory -Path (Join-Path $teamWifiRoot $relativePath) -Force | Out-Null
}
$env:TEMP = Join-Path $teamWifiRoot '.runtime/tmp'
$env:TMP = $env:TEMP
$env:GRADLE_USER_HOME = Join-Path $teamWifiRoot '.runtime/gradle'
$env:npm_config_cache = Join-Path $teamWifiRoot '.runtime/npm-cache'
$env:PIP_CACHE_DIR = Join-Path $teamWifiRoot '.runtime/pip-cache'
$env:UV_CACHE_DIR = Join-Path $teamWifiRoot '.runtime/uv-cache'
Set-Location -LiteralPath $teamWifiRoot
Write-Output 'Team_Wifi workspace: E:/Team_Wifi (process-local environment only)'

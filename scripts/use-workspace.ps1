# Dot-source: . E:/Team_Wifi/scripts/use-workspace.ps1
$teamWifiRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if ($teamWifiRoot.TrimEnd('\','/') -ne 'E:\Team_Wifi') {
  throw 'This project must run from E:/Team_Wifi. Connect the approved drive; do not create a C/D fallback.'
}
foreach ($relativePath in @('.runtime/tmp','.runtime/gradle','.runtime/npm-cache','.runtime/pip-cache','.runtime/uv-cache','.runtime/npm-global','.runtime/uv-tools','.runtime/uv-python','.runtime/android-user')) {
  New-Item -ItemType Directory -Path (Join-Path $teamWifiRoot $relativePath) -Force | Out-Null
}
$env:TEMP = Join-Path $teamWifiRoot '.runtime/tmp'
$env:TMP = $env:TEMP
$env:GRADLE_USER_HOME = Join-Path $teamWifiRoot '.runtime/gradle'
$env:npm_config_cache = Join-Path $teamWifiRoot '.runtime/npm-cache'
$env:PIP_CACHE_DIR = Join-Path $teamWifiRoot '.runtime/pip-cache'
$env:UV_CACHE_DIR = Join-Path $teamWifiRoot '.runtime/uv-cache'
$env:npm_config_prefix = Join-Path $teamWifiRoot '.runtime/npm-global'
$env:UV_TOOL_DIR = Join-Path $teamWifiRoot '.runtime/uv-tools'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $teamWifiRoot '.runtime/uv-python'
$env:ANDROID_USER_HOME = Join-Path $teamWifiRoot '.runtime/android-user'
$env:ANDROID_AVD_HOME = Join-Path $env:ANDROID_USER_HOME 'avd'
# Use verified portable toolchains when present. Shared C: installations may
# remain for other applications; this project executes the E: copies directly.
$teamWifiTools = Join-Path $teamWifiRoot '.runtime/toolchains'
$teamWifiPathEntries = @()
$teamWifiReadyPath = Join-Path $teamWifiTools 'READY.json'
$teamWifiReady = $false
if (Test-Path -LiteralPath $teamWifiReadyPath) {
  $teamWifiReadyState = Get-Content -LiteralPath $teamWifiReadyPath -Raw | ConvertFrom-Json
  $teamWifiReady = $teamWifiReadyState.schema_version -eq 1 -and $teamWifiReadyState.validation_pass -eq $true -and $teamWifiReadyState.root -eq $teamWifiRoot
  if (-not $teamWifiReady) { throw 'E toolchain marker is incomplete or invalid. Verify the runtime before activation.' }
}
if ($teamWifiReady) {
  foreach ($toolFile in @('git/cmd/git.exe','node/node.exe','node/npm.cmd','jdk-21/bin/java.exe','python-3.11/python.exe','android-sdk/platform-tools/adb.exe')) {
    if (-not (Test-Path -LiteralPath (Join-Path $teamWifiTools $toolFile) -PathType Leaf)) {
      throw ('Verified E toolchain is missing: '+$toolFile+'. Revalidate before using this environment.')
    }
  }
  foreach ($toolDir in @('git/cmd','node','jdk-21/bin','python-3.11','android-sdk/platform-tools')) {
    $teamWifiPathEntries += Join-Path $teamWifiTools $toolDir
  }
  $env:PATH = (($teamWifiPathEntries + ($env:PATH -split ';') | Select-Object -Unique) -join ';')
  $env:JAVA_HOME = Join-Path $teamWifiTools 'jdk-21'
  $env:ANDROID_HOME = Join-Path $teamWifiTools 'android-sdk'
  $env:ANDROID_SDK_ROOT = $env:ANDROID_HOME
  $env:UV_PYTHON = Join-Path $teamWifiTools 'python-3.11/python.exe'
}
Set-Location -LiteralPath $teamWifiRoot
Write-Output 'Team_Wifi workspace: E:/Team_Wifi (process-local environment only)'

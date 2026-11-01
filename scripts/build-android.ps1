$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$sdkRoot = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { Join-Path $env:LOCALAPPDATA 'Android/Sdk' }
if (-not (Test-Path (Join-Path $sdkRoot 'platform-tools/adb.exe'))) { throw 'Set ANDROID_HOME to an installed Android SDK.' }
if (-not $env:JAVA_HOME) { throw 'Set JAVA_HOME to JDK 21.' }
$env:ANDROID_HOME = $sdkRoot
$env:ANDROID_SDK_ROOT = $sdkRoot
$previousApi = $env:VITE_API_BASE_URL
$previousLocalAndroid = $env:MODU_LOCAL_ANDROID
Push-Location (Join-Path $projectRoot 'frontend')
try {
  $env:VITE_API_BASE_URL = 'http://10.0.2.2:8000/api'
  $env:MODU_LOCAL_ANDROID = '1'
  npm run build
  if ($LASTEXITCODE -ne 0) { throw 'Web build failed.' }
  npx cap sync android
  if ($LASTEXITCODE -ne 0) { throw 'Capacitor sync failed.' }
  $sdkProperty = $sdkRoot.Replace('\','/').Replace(':','\:')
  [IO.File]::WriteAllText((Join-Path $PWD 'android/local.properties'), "sdk.dir=$sdkProperty`n", [Text.UTF8Encoding]::new($false))
  Push-Location android
  try {
    .\gradlew.bat assembleDebug --no-daemon
    if ($LASTEXITCODE -ne 0) { throw 'Android build failed.' }
  } finally { Pop-Location }
  $apk = Join-Path $PWD 'android/app/build/outputs/apk/debug/app-debug.apk'
  if (-not (Test-Path $apk)) { throw 'APK missing.' }
  $target = Join-Path $projectRoot 'artifacts/android'
  New-Item -ItemType Directory -Force $target | Out-Null
  Copy-Item -LiteralPath $apk -Destination (Join-Path $target 'modu-yuga-debug.apk') -Force
  # Use .NET directly so the nested Windows PowerShell runner needs no Utility module autoload.
  $sha = [Security.Cryptography.SHA256]::Create()
  $stream = [IO.File]::OpenRead((Join-Path $target 'modu-yuga-debug.apk'))
  try { $digest = [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '') }
  finally { $stream.Dispose(); $sha.Dispose() }
  [IO.File]::WriteAllText((Join-Path $target 'apk-sha256.txt'), $digest + "`n", [Text.UTF8Encoding]::new($false))
  Write-Output 'ANDROID_BUILD_PASS'
} finally {
  $env:VITE_API_BASE_URL = $previousApi
  $env:MODU_LOCAL_ANDROID = $previousLocalAndroid
  Pop-Location
}

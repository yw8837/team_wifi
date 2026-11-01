#requires -Version 7.0
<#! Build only against a reachable beta HTTPS backend; keep upload key private. #>
[CmdletBinding()]
param(
  [Parameter(Mandatory)][uri]$ApiBaseUrl,
  [string]$SdkRoot = $env:ANDROID_HOME,
  [string]$JavaHome = $env:JAVA_HOME,
  [ValidateRange(1,2100000000)][int]$VersionCode = 2,
  [string]$VersionName = '0.2.0',
  [string]$OutputDirectory = ''
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$out = if ($OutputDirectory) { [IO.Path]::GetFullPath($OutputDirectory, $root) } else { Join-Path $root 'artifacts/android/release' }
if (-not $out.StartsWith([IO.Path]::GetFullPath($root).TrimEnd('\','/')+[IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Build output must stay inside this project.' }
if ($ApiBaseUrl.Scheme -ne 'https' -or $ApiBaseUrl.Host -in @('localhost','127.0.0.1','::1') -or $ApiBaseUrl.AbsolutePath.TrimEnd('/') -ne '/api' -or $ApiBaseUrl.Query -or $ApiBaseUrl.Fragment -or $ApiBaseUrl.UserInfo) { throw 'A public HTTPS /api URL is required.' }
$health = Invoke-RestMethod -Uri ($ApiBaseUrl.AbsoluteUri.TrimEnd('/')+'/health') -TimeoutSec 90
if ($health.status -ne 'ok' -or $health.mode -ne 'closed-beta' -or $health.payments_enabled) { throw 'Live beta health gate failed.' }
if (-not (Test-Path -LiteralPath (Join-Path $SdkRoot 'platform-tools/adb.exe'))) { throw 'ANDROID_HOME must point to the installed SDK.' }
if (-not (Test-Path -LiteralPath (Join-Path $JavaHome 'bin/keytool.exe'))) { throw 'JAVA_HOME must point to JDK 21.' }
$private = Join-Path $root 'artifacts/android/private'
New-Item -ItemType Directory -Force $private | Out-Null
# Restrict newly created secrets to this Windows user and SYSTEM. DPAPI password export
# also binds the encryption to this user on this machine; preserve a separate secure backup.
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
& icacls.exe $private /inheritance:r /grant:r "${identity}:(OI)(CI)F" 'SYSTEM:(OI)(CI)F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Could not restrict the signing directory ACL.' }
$vault = Join-Path $private 'upload-password.clixml'
$keystore = Join-Path $private 'upload.jks'
$keys = @('JAVA_HOME','ANDROID_HOME','ANDROID_SDK_ROOT','VITE_API_BASE_URL','VITE_BETA_MODE','MODU_LOCAL_ANDROID','MODU_KEYSTORE','MODU_STORE_PASSWORD','MODU_KEY_PASSWORD','MODU_KEY_ALIAS','MODU_VERSION_CODE','MODU_VERSION_NAME')
$saved = @{}
foreach ($key in $keys) { $saved[$key]=[Environment]::GetEnvironmentVariable($key,'Process') }
try {
  $env:JAVA_HOME=$JavaHome; $env:ANDROID_HOME=$SdkRoot; $env:ANDROID_SDK_ROOT=$SdkRoot
  $env:VITE_API_BASE_URL=$ApiBaseUrl.AbsoluteUri.TrimEnd('/'); $env:VITE_BETA_MODE='1'; $env:MODU_LOCAL_ANDROID='0'
  $env:MODU_KEYSTORE=$keystore; $env:MODU_KEY_ALIAS='moduyuga-upload'
  if ((Test-Path -LiteralPath $keystore) -ne (Test-Path -LiteralPath $vault)) { throw 'Incomplete signing key pair. Recover the existing backup; never silently replace it.' }
  if (-not (Test-Path -LiteralPath $vault)) {
    $random = [Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(48))
    ConvertTo-SecureString $random -AsPlainText -Force | Export-Clixml -LiteralPath $vault
    $env:MODU_STORE_PASSWORD=$random
    $env:MODU_KEY_PASSWORD=$random
    & (Join-Path $JavaHome 'bin/keytool.exe') -genkeypair -keystore $keystore -storepass:env MODU_STORE_PASSWORD -keypass:env MODU_KEY_PASSWORD -alias $env:MODU_KEY_ALIAS -keyalg RSA -keysize 3072 -validity 10000 -dname 'CN=Team_Wifi, OU=Android, O=Team_Wifi, C=KR' -storetype JKS
    if ($LASTEXITCODE -ne 0) { throw 'Upload key generation failed.' }
  } else {
    $secure = Import-Clixml -LiteralPath $vault
    $env:MODU_STORE_PASSWORD=[Net.NetworkCredential]::new('', $secure).Password
    $env:MODU_KEY_PASSWORD=$env:MODU_STORE_PASSWORD
  }
  $env:MODU_VERSION_CODE=[string]$VersionCode; $env:MODU_VERSION_NAME=$VersionName
  Push-Location (Join-Path $root 'frontend')
  try {
    npm run build
    if ($LASTEXITCODE -ne 0) { throw 'Beta web build failed.' }
    npx cap sync android
    if ($LASTEXITCODE -ne 0) { throw 'Capacitor sync failed.' }
    $sdkProperty=$SdkRoot.Replace('\','/').Replace(':','\:')
    [IO.File]::WriteAllText((Join-Path $PWD 'android/local.properties'),"sdk.dir=$sdkProperty`n",[Text.UTF8Encoding]::new($false))
    Push-Location android
    try {
      .\gradlew.bat bundleRelease assembleRelease --no-daemon --max-workers=2
      if ($LASTEXITCODE -ne 0) { throw 'Signed Android build failed.' }
    } finally { Pop-Location }
    New-Item -ItemType Directory -Force $out | Out-Null
    Copy-Item -LiteralPath 'android/app/build/outputs/bundle/release/app-release.aab' -Destination (Join-Path $out 'moduyuga-beta.aab') -Force
    Copy-Item -LiteralPath 'android/app/build/outputs/apk/release/app-release.apk' -Destination (Join-Path $out 'moduyuga-beta.apk') -Force
    $metadata=@{versionCode=$VersionCode;versionName=$VersionName;api=$env:VITE_API_BASE_URL;artifacts=@()}
    foreach ($name in @('moduyuga-beta.aab','moduyuga-beta.apk')) {
      $file=Get-Item -LiteralPath (Join-Path $out $name)
      $metadata.artifacts+=@{name=$name;bytes=$file.Length;sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLower()}
    }
    $metadata | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $out 'build.json') -Encoding utf8
    Write-Output 'ANDROID_SIGNED_BETA_BUILD_PASS'
  } finally { Pop-Location }
} finally {
  foreach ($key in $keys) { [Environment]::SetEnvironmentVariable($key,$saved[$key],'Process') }
  $random=$null; $secure=$null
}

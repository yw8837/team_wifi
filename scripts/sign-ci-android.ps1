#requires -Version 7.0
<#! Sign reviewed unsigned CI artifacts locally; never send the upload key to CI. #>
[CmdletBinding()]
param(
 [Parameter(Mandatory)][string]$InputDirectory,
 [Parameter(Mandatory)][ValidatePattern('^[a-f0-9]{40}$')][string]$ExpectedCommit,
 [Parameter(Mandatory)][ValidatePattern('^[0-9]+$')][string]$ExpectedRunId,
 [Parameter(Mandatory)][string]$OutputDirectory,
 [string]$SdkRoot = 'E:/Team_Wifi/.runtime/toolchains/android-sdk',
 [string]$JavaHome = 'E:/Team_Wifi/.runtime/toolchains/jdk-21'
)
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent))
$rootPrefix=$root.TrimEnd('\','/')+[IO.Path]::DirectorySeparatorChar
$incoming=[IO.Path]::GetFullPath($InputDirectory,$root)
$out=[IO.Path]::GetFullPath($OutputDirectory,$root)
foreach($path in @($incoming,$out)) {
 if(-not $path.StartsWith($rootPrefix,[StringComparison]::OrdinalIgnoreCase)){throw 'Artifacts must stay within the project.'}
}
if(Test-Path -LiteralPath $out){throw 'Choose a new release directory; existing artifacts are preserved.'}
$manifest=Get-Content -LiteralPath (Join-Path $incoming 'provenance.json') -Raw | ConvertFrom-Json
if($manifest.schema_version -ne 1 -or $manifest.signed -ne $false -or $manifest.commit -ne $ExpectedCommit -or $manifest.run_id -ne $ExpectedRunId -or $manifest.mode -ne 'public_release' -or $manifest.versionCode -ne 4 -or $manifest.versionName -ne '0.3.0' -or $manifest.api -ne 'https://moduyuga-beta.onrender.com/api'){throw 'CI provenance does not match the reviewed release.'}
$incomingPrefix=$incoming.TrimEnd('\','/')+[IO.Path]::DirectorySeparatorChar
foreach($entry in $manifest.files.PSObject.Properties){
 $file=[IO.Path]::GetFullPath($entry.Name,$incoming)
 if(-not $file.StartsWith($incomingPrefix,[StringComparison]::OrdinalIgnoreCase)){throw 'Unsafe manifest path.'}
 $item=Get-Item -LiteralPath $file
 if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Artifact symlinks are not accepted.'}
 if($item.Length -ne $entry.Value.bytes -or (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLower() -ne $entry.Value.sha256){throw ('CI artifact checksum mismatch: '+$entry.Name)}
}
foreach($name in @('moduyuga-unsigned.apk','moduyuga-unsigned.aab','web/index.html')) {
 if(-not $manifest.files.PSObject.Properties[$name]){throw ('Missing signed-input manifest entry: '+$name)}
}
$health=Invoke-RestMethod -Uri ($manifest.api+'/health') -TimeoutSec 90
$config=Invoke-RestMethod -Uri ($manifest.api+'/config') -TimeoutSec 90
if($health.status -ne 'ok' -or $health.mode -ne 'public-release' -or $health.payments_enabled -or $config.public_release -ne $true -or $config.beta_mode -ne $false){throw 'Live server does not match public release.'}
$private=Join-Path $root 'artifacts/android/private'
$keystore=Join-Path $private 'upload.jks'
$vault=Join-Path $private 'upload-password.clixml'
if(-not(Test-Path -LiteralPath $keystore) -or -not(Test-Path -LiteralPath $vault)){throw 'Restore the existing upload key; no replacement key will be generated.'}
$keys=@('JAVA_HOME','MODU_STORE_PASSWORD','MODU_KEY_PASSWORD')
$saved=@{}
foreach($key in $keys){$saved[$key]=[Environment]::GetEnvironmentVariable($key,'Process')}
try{
 $env:JAVA_HOME=$JavaHome
 $secure=Import-Clixml -LiteralPath $vault
 $env:MODU_STORE_PASSWORD=[Net.NetworkCredential]::new('',$secure).Password
 $env:MODU_KEY_PASSWORD=$env:MODU_STORE_PASSWORD
 New-Item -ItemType Directory -Path $out | Out-Null
 $apk=Join-Path $out 'moduyuga-beta.apk'
 $aab=Join-Path $out 'moduyuga-beta.aab'
 & (Join-Path $SdkRoot 'build-tools/35.0.0/zipalign.exe') -P 16 -f 4 (Join-Path $incoming 'moduyuga-unsigned.apk') $apk
 if($LASTEXITCODE -ne 0){throw 'APK alignment failed.'}
 & (Join-Path $SdkRoot 'build-tools/35.0.0/apksigner.bat') sign --ks $keystore --ks-key-alias 'moduyuga-upload' --ks-pass env:MODU_STORE_PASSWORD --key-pass env:MODU_KEY_PASSWORD $apk
 if($LASTEXITCODE -ne 0){throw 'APK signing failed.'}
 Copy-Item -LiteralPath (Join-Path $incoming 'moduyuga-unsigned.aab') -Destination $aab
 & (Join-Path $JavaHome 'bin/jarsigner.exe') -keystore $keystore '-storepass:env' MODU_STORE_PASSWORD '-keypass:env' MODU_KEY_PASSWORD $aab 'moduyuga-upload'
 if($LASTEXITCODE -ne 0){throw 'AAB signing failed.'}
 Copy-Item -LiteralPath (Join-Path $incoming 'web') -Destination (Join-Path $out 'web') -Recurse
 Copy-Item -LiteralPath (Join-Path $incoming 'provenance.json') -Destination (Join-Path $out 'unsigned-provenance.json')
 $metadata=@{versionCode=$manifest.versionCode;versionName=$manifest.versionName;mode=$manifest.mode;api=$manifest.api;commit=$manifest.commit;run_id=$manifest.run_id;artifacts=@()}
 foreach($name in @('moduyuga-beta.apk','moduyuga-beta.aab')){
  $file=Get-Item -LiteralPath (Join-Path $out $name)
  $metadata.artifacts+=@{name=$name;bytes=$file.Length;sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLower()}
 }
 $metadata | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $out 'build.json') -Encoding utf8
 Write-Output 'LOCAL_CI_ARTIFACT_SIGNING_COMPLETE: run verify-android-release.py before upload.'
}finally{
 foreach($key in $keys){[Environment]::SetEnvironmentVariable($key,$saved[$key],'Process')}
 $secure=$null
}

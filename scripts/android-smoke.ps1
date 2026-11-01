#requires -Version 7.0
<#
Local debug APK smoke test. Uses only the explicitly named test emulator.
Does not create accounts, send mail, upload to Play, or terminate existing ADB servers.
Emulator stdout may contain ADB public keys: keep it outside the Git workspace.
#>
[CmdletBinding()]
param(
  [string]$SdkRoot = $env:ANDROID_HOME,
  [string]$ApkPath = (Join-Path $PSScriptRoot '../artifacts/android/modu-yuga-debug.apk'),
  [string]$EvidenceDirectory = (Join-Path $PSScriptRoot '../artifacts/android/runtime'),
  [string]$Serial = 'emulator-5760',
  [string]$PackageId = 'kr.moduyuga.app',
  [string]$ApiBaseUrl = 'http://10.0.2.2:8000/api',
  [ValidateRange(15,300)][int]$BootTimeoutSeconds = 90,
  [int]$DevtoolsPort = 9222,
  [switch]$StartEmulator,
  [string]$AvdName = 'ModuYugaLocal',
  [string]$AvdHome = (Join-Path $PSScriptRoot '../.runtime/avd'),
  [string]$PrivateEmulatorLogDirectory = (Join-Path $PSScriptRoot '../.runtime/android-smoke')
)
$ErrorActionPreference = 'Stop'
if ($Serial -notmatch '^emulator-\d+$') { throw 'Only an explicitly named local test emulator is permitted.' }
$adb = Join-Path $SdkRoot 'platform-tools/adb.exe'
if (-not (Test-Path -LiteralPath $adb)) { throw "ADB not found: $adb" }
$ApkPath = (Resolve-Path -LiteralPath $ApkPath).Path
$evidence = [IO.Path]::GetFullPath($EvidenceDirectory)
New-Item -ItemType Directory -Path $evidence -Force | Out-Null
$logPath = Join-Path $evidence 'android-smoke.log'
Set-Content -LiteralPath $logPath -Value "Android smoke start $([DateTimeOffset]::Now.ToString('o'))`nSerial=$Serial Package=$PackageId`nAPK SHA256=$((Get-FileHash -LiteralPath $ApkPath -Algorithm SHA256).Hash)" -Encoding utf8
if ($StartEmulator) {
  if ($AvdName -notmatch '^[A-Za-z0-9_-]+$') { throw 'Use the explicitly owned test AVD name.' }
  # An emulator is optional. Do not exhaust the user's desktop to run smoke QA.
  $availableGiB = (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB
  if ($availableGiB -lt 4) { throw 'At least 4 GiB free RAM is required before starting an optional emulator. Use a physical test device instead.' }
  $avdDrive = [IO.DriveInfo]::new([IO.Path]::GetPathRoot([IO.Path]::GetFullPath($AvdHome)))
  if ($avdDrive.AvailableFreeSpace -lt 30GB) { throw 'At least 30 GiB free on the AVD drive is required. Do not create or start an emulator; use a physical test device instead.' }
  $existing = Get-CimInstance Win32_Process | Where-Object { $_.Name -like '*qemu*' -and $_.CommandLine -match "-avd\s+$([regex]::Escape($AvdName))\b" }
  if ($existing) { throw 'The named test emulator is already running. Omit -StartEmulator; no existing process was terminated.' }
  $privateLogs = [IO.Path]::GetFullPath($PrivateEmulatorLogDirectory)
  $runtimeRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../.runtime')).TrimEnd('\','/') + [IO.Path]::DirectorySeparatorChar
  if (-not $privateLogs.StartsWith($runtimeRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Emulator raw logs must remain inside the ignored project .runtime directory.' }
  if (-not [IO.Path]::GetFullPath($AvdHome).StartsWith($runtimeRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'An optional AVD must remain inside the project .runtime directory.' }
  New-Item -ItemType Directory -Path $privateLogs -Force | Out-Null
  $env:ANDROID_AVD_HOME=$AvdHome; $env:ANDROID_HOME=$SdkRoot; $env:ANDROID_SDK_ROOT=$SdkRoot
  $emulatorPort = $Serial.Split('-')[1]
  # Windows may reserve the default 5554..5585 range for Hyper-V. Explicit ports
  # can be selected outside it without changing OS exclusions or firewall settings.
  $adbPort = [int]$emulatorPort+1
  $launched = Start-Process -FilePath (Join-Path $SdkRoot 'emulator/emulator.exe') -ArgumentList @('-avd',$AvdName,'-no-window','-no-audio','-no-boot-anim','-gpu','swiftshader','-feature','-Vulkan,-QuickbootFileBacked','-no-snapshot','-ports',"$emulatorPort,$adbPort",'-cores','2','-memory','2048','-show-kernel') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $privateLogs 'lowmem.stdout.log') -RedirectStandardError (Join-Path $privateLogs 'lowmem.stderr.log') -PassThru
  Add-Content -LiteralPath $logPath -Value "Owned test emulator launcher PID=$($launched.Id); requested RAM2048/cores2; explicit console/ADB ports $emulatorPort/$adbPort; private raw logs outside Git." -Encoding utf8
}
function Invoke-TestAdb([string[]]$AdbArguments, [int]$TimeoutSeconds=20, [switch]$AllowFailure) {
  $info = [Diagnostics.ProcessStartInfo]::new()
  $info.FileName = $adb
  $info.UseShellExecute = $false
  $info.CreateNoWindow = $true
  $info.RedirectStandardOutput = $true
  $info.RedirectStandardError = $true
  foreach ($argument in $AdbArguments) { $info.ArgumentList.Add($argument) }
  $process = [Diagnostics.Process]::new(); $process.StartInfo = $info
  [void]$process.Start()
  $stdout = $process.StandardOutput.ReadToEndAsync(); $stderr = $process.StandardError.ReadToEndAsync()
  if (-not $process.WaitForExit($TimeoutSeconds*1000)) { $process.Kill(); throw "Owned ADB helper timed out: $($AdbArguments -join ' ')" }
  $result = $stdout.GetAwaiter().GetResult() + $stderr.GetAwaiter().GetResult()
  Add-Content -LiteralPath $logPath -Value "`n> adb $($AdbArguments -join ' ')`n$result" -Encoding utf8
  if ($process.ExitCode -ne 0 -and -not $AllowFailure) { throw "ADB command failed ($($process.ExitCode)): $result" }
  return $result.Trim()
}
$deadline = [DateTime]::UtcNow.AddSeconds($BootTimeoutSeconds)
$booted = $false
do {
  $devices = Invoke-TestAdb @('devices','-l') -TimeoutSeconds 10
  if ($devices -match "(?m)^$([regex]::Escape($Serial))\s+device\b") {
    $state = Invoke-TestAdb @('-s',$Serial,'shell','getprop','sys.boot_completed') -TimeoutSeconds 10 -AllowFailure
    if ($state -eq '1') { $booted=$true; break }
  }
  Start-Sleep -Seconds 3
} while ([DateTime]::UtcNow -lt $deadline)
if (-not $booted) { throw "Test emulator did not boot within $BootTimeoutSeconds seconds. See $logPath. No installation or launch is claimed." }
Invoke-TestAdb @('-s',$Serial,'install','-r',$ApkPath) -TimeoutSeconds 90 | Write-Output
Invoke-TestAdb @('-s',$Serial,'shell','am','start','-W','-n',"$PackageId/.MainActivity") -TimeoutSeconds 30 | Write-Output
Start-Sleep -Seconds 5
$appPid = (Invoke-TestAdb @('-s',$Serial,'shell','pidof',$PackageId)).Split(' ')[0]
if ($appPid -notmatch '^\d+$') { throw 'App process is absent after launch.' }
Invoke-TestAdb @('-s',$Serial,'shell','dumpsys','activity','activities') | Set-Content -LiteralPath (Join-Path $evidence 'activities.txt') -Encoding utf8
Invoke-TestAdb @('-s',$Serial,'forward',"tcp:$DevtoolsPort","localabstract:webview_devtools_remote_$appPid") | Out-Null
$target = $null
$webviewDeadline = [DateTime]::UtcNow.AddSeconds(30)
do {
  try {
    $targets = Invoke-RestMethod -Uri "http://127.0.0.1:$DevtoolsPort/json" -TimeoutSec 5
    $target = @($targets | Where-Object { $_.type -eq 'page' -and $_.webSocketDebuggerUrl }) | Select-Object -First 1
  } catch { Add-Content -LiteralPath $logPath -Value 'WebView still initializing; waiting for its developer endpoint.' }
  if (-not $target) { Start-Sleep -Seconds 2 }
} while (-not $target -and [DateTime]::UtcNow -lt $webviewDeadline)
if (-not $target) { throw 'No debuggable app WebView found. App/API validation remains incomplete.' }
$cdpCode = @'
const [wsUrl,apiBase] = process.argv.slice(2);
const socket = new WebSocket(wsUrl); const pending=new Map(); let sequence=0;
const responses=[]; const failures=[];
socket.addEventListener('message',event=>{const m=JSON.parse(event.data);if(m.id&&pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(new Error(JSON.stringify(m.error))):p.resolve(m.result);}if(m.method==='Network.responseReceived'&&m.params.response.url.includes('/api/'))responses.push({url:m.params.response.url,status:m.params.response.status});if(m.method==='Network.loadingFailed')failures.push({error:m.params.errorText,blocked:m.params.blockedReason});});
await Promise.race([new Promise((resolve,reject)=>{socket.addEventListener('open',resolve,{once:true});socket.addEventListener('error',reject,{once:true});}),new Promise((_,reject)=>setTimeout(()=>reject(new Error('CDP connection timeout')),10000))]);
function command(method,params={}){const id=++sequence;return new Promise((resolve,reject)=>{const timeout=setTimeout(()=>{pending.delete(id);reject(new Error('CDP command timeout '+method));},15000);pending.set(id,{resolve:v=>{clearTimeout(timeout);resolve(v)},reject});socket.send(JSON.stringify({id,method,params}));});}
await command('Network.enable');
await command('Runtime.evaluate',{expression:"(()=>{const entry=[...document.querySelectorAll('a')].find(a=>a.textContent.includes('육아템 둘러보기'));if(entry)entry.click();return {url:location.href,title:document.title};})()",returnByValue:true});
await new Promise(resolve=>setTimeout(resolve,5000));
const state=await command('Runtime.evaluate',{expression:'({url:location.href,title:document.title,text:document.body.innerText.slice(0,3000)})',returnByValue:true});
const expression=`(async()=>{const health=await fetch(${JSON.stringify(apiBase+'/health')});const catalog=await fetch(${JSON.stringify(apiBase+'/campaigns')});const data=await catalog.json();return {health_status:health.status,catalog_status:catalog.status,catalog_count:Array.isArray(data.items)?data.items.length:null};})()`;
const probe=await command('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});
console.log(JSON.stringify({state:state.result?.value,webview_api_probe:probe.result?.value,probe_exception:probe.exceptionDetails,api_responses:responses,network_failures:failures},null,2));
socket.close();
if(probe.exceptionDetails||probe.result?.value?.health_status!==200||probe.result?.value?.catalog_status!==200)process.exitCode=1;
'@
$cdpOutput = $cdpCode | & node --input-type=module - $target.webSocketDebuggerUrl $ApiBaseUrl
$cdpExit = $LASTEXITCODE
$cdpOutput | Set-Content -LiteralPath (Join-Path $evidence 'webview-api.json') -Encoding utf8
Invoke-TestAdb @('-s',$Serial,'shell','screencap','-p','/sdcard/moduyuga-smoke.png') | Out-Null
Invoke-TestAdb @('-s',$Serial,'pull','/sdcard/moduyuga-smoke.png',(Join-Path $evidence 'app-screen.png')) | Write-Output
Invoke-TestAdb @('-s',$Serial,'shell','rm','/sdcard/moduyuga-smoke.png') | Out-Null
Invoke-TestAdb @('-s',$Serial,'forward','--remove',"tcp:$DevtoolsPort") | Out-Null
if ($cdpExit -ne 0) { throw 'App launched but WebView API communication failed. Inspect webview-api.json; do not claim a passed smoke test.' }
Add-Content -LiteralPath $logPath -Value "`nPASS: installed, launched, live WebView public API status200, screenshot captured $([DateTimeOffset]::Now.ToString('o'))" -Encoding utf8
Write-Output "PASS: Android debug smoke evidence at $evidence"

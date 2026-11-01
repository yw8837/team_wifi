#requires -Version 7.0
<#
Bounded public-release live QA. Default: read-only smoke.
Use -RunMutations for disposable integration accounts; optionally -CreateReviewer.
No write is retried automatically. Run only after the deployed candidate is ready.
Private JSON payloads use current-user Windows DPAPI; never attach them to public evidence.
#>
[CmdletBinding()]
param([switch]$RunMutations, [switch]$CreateReviewer)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = [IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent))
if ($root.TrimEnd('\','/') -ne 'E:\Team_Wifi') { throw 'Run from the approved E:/Team_Wifi workspace.' }
. E:/Team_Wifi/scripts/use-workspace.ps1
if ($CreateReviewer -and -not $RunMutations) { throw '-CreateReviewer also requires -RunMutations.' }
if ($RunMutations -and -not $IsWindows) { throw 'Mutating QA requires Windows current-user DPAPI for its private cleanup journal.' }
$origin = 'https://moduyuga-beta.onrender.com'
$apiBase = $origin + '/api'
$evidenceDirectory = Join-Path $root 'artifacts/release-20261102'
$privateDirectory = Join-Path $evidenceDirectory 'private'
$evidenceFile = Join-Path $evidenceDirectory 'live-qa.json'
$runTag = [DateTime]::UtcNow.ToString('yyyyMMddHHmmss') + '-' + [Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(4)).ToLowerInvariant()
$journalFile = Join-Path $privateDirectory ('live-qa-' + $runTag + '.dpapi.json')
$reviewerFile = Join-Path $privateDirectory 'review-account.dpapi.json'
foreach ($guardPath in @($root, (Join-Path $root 'artifacts'), $evidenceDirectory, $privateDirectory, $evidenceFile)) {
    if ((Test-Path -LiteralPath $guardPath) -and ((Get-Item -LiteralPath $guardPath -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'QA output paths must be real workspace paths, without junctions or symlinks.'
    }
}
$checks = [Collections.Generic.List[object]]::new()
$actors = [Collections.Generic.List[object]]::new()
$demandIds = [Collections.Generic.List[string]]::new()
$startedAt = [DateTime]::UtcNow.ToString('o')
$failed = $false
$reviewerCreated = $false
$stage = 'initialization'
$handler = [Net.Http.HttpClientHandler]::new()
$handler.AllowAutoRedirect = $false
$client = [Net.Http.HttpClient]::new($handler)
$client.Timeout = [TimeSpan]::FromSeconds(75)
$client.MaxResponseContentBufferSize = 2097152
$client.DefaultRequestHeaders.UserAgent.ParseAdd('ModuYuga-Public-QA/1.0')
New-Item -ItemType Directory -Path $evidenceDirectory -Force | Out-Null

function Add-Check([string]$Label, [bool]$Passed, [int]$Status = -1) {
    $checks.Add([ordered]@{label=$Label; pass=$Passed; http_status=$Status})
}
function Assert-Check([string]$Label, [bool]$Passed, [int]$Status = -1) {
    Add-Check $Label $Passed $Status
    if (-not $Passed) { throw ('A labeled live check failed: ' + $Label) }
}
function Invoke-Live([string]$Path, [string]$Method = 'GET', $Body = $null, [string]$Token = '') {
    $script:stage = $Method + ' ' + ($Path -split '\?')[0]
    $url = if ($Path.StartsWith('/legal/')) { $origin + $Path } else { $apiBase + $Path }
    $attempts = if ($Method -eq 'GET') { 2 } else { 1 }
    for ($attempt=1; $attempt -le $attempts; $attempt++) {
        $request = [Net.Http.HttpRequestMessage]::new([Net.Http.HttpMethod]::new($Method), $url)
        $response = $null
        $answer = [pscustomobject]@{Status=0; Data=$null; Text=''}
        try {
            if ($Token) { $request.Headers.Authorization = [Net.Http.Headers.AuthenticationHeaderValue]::new('Bearer', $Token) }
            if ($null -ne $Body) { $request.Content = [Net.Http.StringContent]::new(($Body | ConvertTo-Json -Depth 12 -Compress), [Text.Encoding]::UTF8, 'application/json') }
            $response = $client.SendAsync($request).GetAwaiter().GetResult()
            $answer.Status = [int]$response.StatusCode
            $answer.Text = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
            try { $answer.Data = ConvertFrom-Json -InputObject $answer.Text -Depth 30 -NoEnumerate } catch { $answer.Data = $null }
        } catch {
            # Exception text and raw bodies may contain request data; never log them.
            $answer.Status = 0
        } finally {
            if ($null -ne $response) { $response.Dispose() }
            $request.Dispose()
        }
        if ($Method -ne 'GET' -or $answer.Status -notin @(0,502,503,504) -or $attempt -eq $attempts) { return $answer }
        Start-Sleep -Milliseconds 700
    }
}
function New-Secret { return 'Qa1!' + [Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(36)) }
function Save-ProtectedJson([string]$Path, $Value) {
    $secure = ConvertTo-SecureString ($Value | ConvertTo-Json -Depth 15 -Compress) -AsPlainText -Force
    $encrypted = ConvertFrom-SecureString $secure
    [ordered]@{schema_version=1; protection='Windows DPAPI current user'; protected_payload=$encrypted} |
        ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $Path -Encoding utf8
}
function Save-Journal { Save-ProtectedJson $journalFile ([ordered]@{run=$runTag; accounts=$actors.ToArray()}) }
function New-Actor([string]$Suffix, [bool]$Preserve = $false) {
    $actor = [pscustomobject]@{Email=('qa-public-' + $runTag + '-' + $Suffix + '@example.com'); Password=(New-Secret); NextPassword=''; Token=''; RecoveryCode=''; Id=''; Deleted=$false; DeleteAttempted=$false; Preserve=$Preserve; Attempted=$false}
    $actors.Add($actor)
    Save-Journal
    return $actor
}
function Register-Actor($Actor, [string]$Nickname) {
    $Actor.Attempted = $true
    Save-Journal
    $reply = Invoke-Live '/auth/register' 'POST' @{email=$Actor.Email; password=$Actor.Password; nickname=$Nickname; track='buyer'; terms_accepted=$true; privacy_accepted=$true; adult_confirmed=$true; marketing_opt_in=$false; invite_code=''}
    if ($reply.Status -eq 201 -and $null -ne $reply.Data) {
        # Capture cleanup credentials before asserting profile policy.
        $Actor.Token = [string]$reply.Data.access_token
        $Actor.Id = [string]$reply.Data.user.id
        $Actor.RecoveryCode = [string]$reply.Data.recovery_code
        Save-Journal
    }
    Assert-Check 'synthetic_buyer_signup' ($reply.Status -eq 201) $reply.Status
    Assert-Check 'signup_least_privilege_and_recovery' ($Actor.Id -match '^[a-f0-9-]{36}$' -and $Actor.Token.Length -ge 32 -and $Actor.RecoveryCode.Length -ge 32 -and $reply.Data.user.email -eq $Actor.Email -and $reply.Data.user.is_admin -eq $false -and $reply.Data.user.email_verified -eq $false -and $null -eq $reply.Data.user.seller_status)
}
function Remove-Actor($Actor, [string]$Label) {
    if ($Actor.Deleted -or -not $Actor.Attempted -or $Actor.Preserve) { return }
    if ($Actor.DeleteAttempted) { Add-Check ($Label+'_ambiguous_delete_needs_private_journal') $false; return }
    # An ambiguous signup/recovery response is resolved by login, never by repeating a write.
    $me = if ($Actor.Token) { Invoke-Live '/me' 'GET' $null $Actor.Token } else { $null }
    if ($null -eq $me -or $me.Status -ne 200) {
        $passwords = @($Actor.Password)
        if ($Actor.NextPassword -and $Actor.NextPassword -ne $Actor.Password) { $passwords += $Actor.NextPassword }
        foreach ($candidate in $passwords) {
            $login = Invoke-Live '/auth/login' 'POST' @{email=$Actor.Email; password=$candidate}
            if ($login.Status -eq 200) {
                $Actor.Token = [string]$login.Data.access_token
                $Actor.Password = $candidate
                $me = Invoke-Live '/me' 'GET' $null $Actor.Token
                break
            }
        }
    }
    if ($null -eq $me -or $me.Status -ne 200) { Add-Check ($Label+'_cleanup_needs_private_journal') $false; return }
    if ($me.Data.email -ne $Actor.Email -or ($Actor.Id -and $me.Data.id -ne $Actor.Id) -or $me.Data.is_admin -ne $false) {
        Add-Check ($Label+'_cleanup_identity_mismatch') $false
        return
    }
    $Actor.Id = [string]$me.Data.id
    $Actor.DeleteAttempted = $true
    Save-Journal
    $reply = Invoke-Live '/me' 'DELETE' @{password=$Actor.Password} $Actor.Token
    if ($reply.Status -eq 200) { $Actor.Deleted = $true; Save-Journal }
    Add-Check ($Label+'_owned_account_deleted') ($reply.Status -eq 200) $reply.Status
    if ($Actor.Deleted) {
        $revoked = Invoke-Live '/me' 'GET' $null $Actor.Token
        Add-Check ($Label+'_deleted_token_rejected') ($revoked.Status -eq 401) $revoked.Status
    }
}

try {
    $health = Invoke-Live '/health'
    Assert-Check 'health_public_release' ($health.Status -eq 200 -and $health.Data.status -eq 'ok' -and $health.Data.mode -eq 'public-release' -and $health.Data.payments_enabled -eq $false) $health.Status
    $config = Invoke-Live '/config'
    Assert-Check 'config_public_release' ($config.Status -eq 200 -and $config.Data.public_release -eq $true -and $config.Data.beta_mode -eq $false -and $config.Data.invite_required -eq $false -and $config.Data.payments_enabled -eq $false -and $config.Data.seller_real_data_enabled -eq $false) $config.Status
    $offers = Invoke-Live '/release/offers?limit=20&offset=0'
    Assert-Check 'guest_catalog_available' ($offers.Status -eq 200 -and $offers.Data -is [array] -and $offers.Data.Count -gt 0) $offers.Status
    $catalogSafe = $true
    foreach ($offer in $offers.Data) {
        $source = $null
        $validUrl = [uri]::TryCreate([string]$offer.source_url, [UriKind]::Absolute, [ref]$source)
        if (-not $validUrl -or $source.Scheme -ne 'https' -or $source.UserInfo -or $offer.saved -ne $false -or $offer.entry_type -notin @('shopping_reference','verified_offer')) { $catalogSafe = $false }
        if ($offer.entry_type -eq 'shopping_reference' -and ($null -ne $offer.price -or $null -ne $offer.shipping_fee -or $null -ne $offer.expires_at)) { $catalogSafe = $false }
    }
    Assert-Check 'catalog_sources_and_unknown_prices_truthful' $catalogSafe
    $firstOfferId = [uri]::EscapeDataString([string]$offers.Data[0].id)
    $detail = Invoke-Live ('/release/offers/'+$firstOfferId)
    Assert-Check 'guest_offer_detail' ($detail.Status -eq 200 -and $detail.Data.saved -eq $false) $detail.Status
    $guestDemands = Invoke-Live '/release/demands?limit=1&offset=0'
    Assert-Check 'guest_demands_readable' ($guestDemands.Status -eq 200 -and $guestDemands.Data -is [array]) $guestDemands.Status
    foreach ($path in @('/campaigns','/hotdeals','/brands','/coupons','/wallet','/reservations','/seller/application','/admin/reports','/research/summary')) {
        $reply = Invoke-Live $path
        Assert-Check ('legacy_surface_denied_'+($path.Trim('/') -replace '/','_')) ($reply.Status -eq 404) $reply.Status
    }
    foreach ($kind in @('privacy','terms','deletion','support')) {
        $reply = Invoke-Live ('/legal/'+$kind)
        Assert-Check ('legal_'+$kind+'_available') ($reply.Status -eq 200 -and $reply.Text.Contains('Team_Wifi') -and -not $reply.Text.Contains('비공개 베타')) $reply.Status
    }
    if ($RunMutations) {
        if ($CreateReviewer -and (Test-Path -LiteralPath $reviewerFile)) { throw 'Reviewer private file already exists; do not create a second reviewer account.' }
        New-Item -ItemType Directory -Path $privateDirectory -Force | Out-Null
        $identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
        & icacls.exe $privateDirectory /inheritance:r /grant:r "${identity}:(OI)(CI)F" 'SYSTEM:(OI)(CI)F' 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Could not restrict private QA evidence permissions.' }
        $a = New-Actor 'a'
        $b = New-Actor 'b'
        Register-Actor $a '임시 QA 계정 A'
        Register-Actor $b '임시 QA 계정 B'
        $guestWrite = Invoke-Live ('/release/offers/'+$firstOfferId+'/saved') 'PUT'
        Assert-Check 'guest_save_requires_login' ($guestWrite.Status -eq 401) $guestWrite.Status
        foreach ($i in 1..2) {
            $reply = Invoke-Live ('/release/offers/'+$firstOfferId+'/saved') 'PUT' $null $a.Token
            Assert-Check ('save_idempotent_'+$i) ($reply.Status -eq 200 -and $reply.Data.saved -eq $true) $reply.Status
        }
        $reply = Invoke-Live '/release/saved?limit=100' 'GET' $null $a.Token
        Assert-Check 'save_single_record' ($reply.Status -eq 200 -and @($reply.Data | Where-Object id -eq $offers.Data[0].id).Count -eq 1) $reply.Status
        $reply = Invoke-Live '/release/saved?limit=100' 'GET' $null $b.Token
        Assert-Check 'saved_private_between_accounts' ($reply.Status -eq 200 -and $reply.Data.Count -eq 0) $reply.Status
        $reply = Invoke-Live ('/release/offers/'+$firstOfferId+'/saved') 'DELETE' $null $a.Token
        Assert-Check 'own_saved_offer_removed' ($reply.Status -eq 200) $reply.Status
        $reply = Invoke-Live '/release/saved?limit=100' 'GET' $null $a.Token
        Assert-Check 'unsaved_offer_absent' ($reply.Status -eq 200 -and $reply.Data.Count -eq 0) $reply.Status
        $created = @()
        foreach ($actor in @($a,$b)) {
            $reply = Invoke-Live '/release/demands' 'POST' @{title=('임시 QA 검증 '+$runTag); body='자동화된 출시 검증을 위한 임시 게시물입니다. 구매 모집이 아니며 검증 직후 삭제합니다.'; category='육아생활'} $actor.Token
            if ($reply.Status -eq 201) { $demandIds.Add([string]$reply.Data.id) }
            Assert-Check 'temporary_owned_demand_created' ($reply.Status -eq 201 -and $reply.Data.author.id -eq $actor.Id -and $reply.Data.own -eq $true) $reply.Status
            $created += $reply.Data
        }
        $da = '/release/demands/'+[uri]::EscapeDataString([string]$created[0].id)
        $db = '/release/demands/'+[uri]::EscapeDataString([string]$created[1].id)
        $reply = Invoke-Live $da 'DELETE' $null $b.Token
        Assert-Check 'demand_idor_denied' ($reply.Status -eq 404) $reply.Status
        foreach ($i in 1..2) {
            $reply = Invoke-Live ($da+'/interest') 'PUT' $null $b.Token
            Assert-Check ('interest_unique_account_'+$i) ($reply.Status -eq 200 -and $reply.Data.interest_count -eq 1 -and $reply.Data.interested -eq $true) $reply.Status
        }
        $reply = Invoke-Live ($da+'/interest') 'DELETE' $null $b.Token
        Assert-Check 'own_interest_removed' ($reply.Status -eq 200 -and $reply.Data.interest_count -eq 0 -and $reply.Data.interested -eq $false) $reply.Status
        $reply = Invoke-Live ($db+'/interest') 'PUT' $null $a.Token
        Assert-Check 'second_owned_interest_created' ($reply.Status -eq 200) $reply.Status
        $reply = Invoke-Live ($da+'/comments') 'POST' @{body='임시 QA 댓글입니다. 검증 후 삭제합니다.'} $b.Token
        Assert-Check 'temporary_comment_created' ($reply.Status -eq 201 -and $reply.Data.author.id -eq $b.Id) $reply.Status
        $commentId = [uri]::EscapeDataString([string]$reply.Data.id)
        $reply = Invoke-Live ('/release/comments/'+$commentId) 'DELETE' $null $a.Token
        Assert-Check 'comment_idor_denied' ($reply.Status -eq 404) $reply.Status
        $reply = Invoke-Live ('/release/comments/'+$commentId) 'DELETE' $null $b.Token
        Assert-Check 'own_comment_delete' ($reply.Status -eq 200) $reply.Status
        $reply = Invoke-Live ($da+'/comments') 'POST' @{body='임시 QA 차단 표시 검증 댓글입니다. 곧 삭제합니다.'} $b.Token
        Assert-Check 'temporary_block_test_comment_created' ($reply.Status -eq 201) $reply.Status
        $reply = Invoke-Live ($db+'/comments') 'POST' @{body='임시 QA 탈퇴 연관 삭제 검증 댓글입니다. 곧 삭제합니다.'} $a.Token
        Assert-Check 'temporary_cascade_test_comment_created' ($reply.Status -eq 201) $reply.Status
        $reply = Invoke-Live '/release/reports' 'POST' @{target_type='demand'; target_id=$created[0].id; reason='임시 QA 검증 신고입니다. 실제 이용자 신고가 아니며 검증 종료 시 해당 QA 글과 계정을 삭제합니다.'} $b.Token
        Assert-Check 'owned_content_report_accepted' ($reply.Status -eq 201) $reply.Status
        $reply = Invoke-Live '/release/admin/reports' 'GET' $null $b.Token
        Assert-Check 'report_admin_access_denied_to_buyer' ($reply.Status -eq 403) $reply.Status
        $reply = Invoke-Live ('/blocks/'+$b.Id) 'POST' $null $a.Token
        Assert-Check 'owned_user_blocked' ($reply.Status -eq 200) $reply.Status
        $reply = Invoke-Live ($da+'/comments') 'GET' $null $a.Token
        Assert-Check 'block_filters_comments' ($reply.Status -eq 200 -and $reply.Data.Count -eq 0) $reply.Status
        $reply = Invoke-Live $db 'GET' $null $a.Token
        Assert-Check 'block_filters_demand_detail' ($reply.Status -eq 404) $reply.Status
        $reply = Invoke-Live $db
        Assert-Check 'blocked_content_still_guest_readable' ($reply.Status -eq 200) $reply.Status
        $reply = Invoke-Live ('/blocks/'+$b.Id) 'DELETE' $null $a.Token
        Assert-Check 'owned_user_unblocked' ($reply.Status -eq 200) $reply.Status
        $reply = Invoke-Live $db 'GET' $null $a.Token
        Assert-Check 'unblock_restores_visibility' ($reply.Status -eq 200) $reply.Status
        $reply = Invoke-Live ('/blocks/'+$a.Id) 'POST' $null $b.Token
        Assert-Check 'incoming_block_for_cleanup_created' ($reply.Status -eq 200) $reply.Status
        $oldToken = $a.Token
        $oldCode = $a.RecoveryCode
        $a.NextPassword = New-Secret
        Save-Journal
        $reply = Invoke-Live '/auth/recover' 'POST' @{email=$a.Email; recovery_code=$oldCode; password=$a.NextPassword}
        if ($reply.Status -eq 200) { $a.Password=$a.NextPassword; $a.RecoveryCode=[string]$reply.Data.recovery_code; $a.Token=''; Save-Journal }
        Assert-Check 'recovery_rotates_code' ($reply.Status -eq 200 -and $a.RecoveryCode -ne $oldCode -and $a.RecoveryCode.Length -ge 32) $reply.Status
        $reply = Invoke-Live '/me' 'GET' $null $oldToken
        Assert-Check 'recovery_revokes_old_session' ($reply.Status -eq 401) $reply.Status
        $reply = Invoke-Live '/auth/recover' 'POST' @{email=$a.Email; recovery_code=$oldCode; password=$a.Password}
        Assert-Check 'old_recovery_code_replay_denied' ($reply.Status -eq 400) $reply.Status
        $reply = Invoke-Live '/auth/login' 'POST' @{email=$a.Email; password=$a.Password}
        if ($reply.Status -eq 200) { $a.Token=[string]$reply.Data.access_token; Save-Journal }
        Assert-Check 'recovered_account_login' ($reply.Status -eq 200) $reply.Status
        Remove-Actor $a 'a'
        Assert-Check 'first_account_cleanup_completed' $a.Deleted
        $reply = Invoke-Live $da
        Assert-Check 'deleted_author_demand_removed' ($reply.Status -eq 404) $reply.Status
        $reply = Invoke-Live $db 'GET' $null $b.Token
        Assert-Check 'deleted_account_interest_and_comment_removed' ($reply.Status -eq 200 -and $reply.Data.interest_count -eq 0 -and $reply.Data.comment_count -eq 0) $reply.Status
        $reply = Invoke-Live '/blocks?limit=100' 'GET' $null $b.Token
        Assert-Check 'deleted_account_incoming_block_removed' ($reply.Status -eq 200 -and @($reply.Data | Where-Object id -eq $a.Id).Count -eq 0) $reply.Status
        $reply = Invoke-Live $db 'DELETE' $null $b.Token
        Assert-Check 'own_demand_delete' ($reply.Status -eq 200) $reply.Status
        Remove-Actor $b 'b'
        Assert-Check 'second_account_cleanup_completed' $b.Deleted
        if ($CreateReviewer) {
            Assert-Check 'disposable_checks_pass_before_reviewer' (@($checks | Where-Object { -not $_.pass }).Count -eq 0)
            $reviewer = New-Actor 'reviewer'
            Register-Actor $reviewer '앱 심사 전용 계정'
            Save-ProtectedJson $reviewerFile ([ordered]@{purpose='Google Play app access review only'; api=$apiBase; email=$reviewer.Email; password=$reviewer.Password; recovery_code=$reviewer.RecoveryCode; account_id=$reviewer.Id; created_at=[DateTime]::UtcNow.ToString('o')})
            $reviewer.Preserve = $true
            Save-Journal
            $reviewerCreated = $true
            Add-Check 'reviewer_buyer_created_private_dpapi_only' $true
        }
    }
} catch {
    $failed = $true
    # A stage names only an endpoint shape. Never persist exception messages or responses.
    Add-Check 'sequence_failed_see_labeled_checks' $false
} finally {
    if ($RunMutations) {
        foreach ($actor in $actors) {
            try { Remove-Actor $actor 'finally' } catch { Add-Check 'owned_account_cleanup_needs_private_journal' $false }
        }
        foreach ($id in $demandIds) {
            $reply = Invoke-Live ('/release/demands/'+[uri]::EscapeDataString($id))
            Add-Check 'owned_temporary_demand_absent_after_cleanup' ($reply.Status -eq 404) $reply.Status
        }
    }
    $allPassed = -not $failed -and @($checks | Where-Object { -not $_.pass }).Count -eq 0
    $report = [ordered]@{schema_version=1; scope=$(if($RunMutations){'live public-release smoke and owned synthetic integration'}else{'live public-release read-only smoke'}); api=$apiBase; started_at=$startedAt; finished_at=[DateTime]::UtcNow.ToString('o'); pass=$allPassed; mutations_requested=[bool]$RunMutations; reviewer_requested=[bool]$CreateReviewer; reviewer_created=$reviewerCreated; disposable_accounts=@($actors | Where-Object { -not $_.Preserve }).Count; disposable_accounts_deleted=@($actors | Where-Object { -not $_.Preserve -and $_.Deleted }).Count; checks=$checks.ToArray()}
    $sanitizedJson = $report | ConvertTo-Json -Depth 8
    $sanitizedJson | Set-Content -LiteralPath (Join-Path $evidenceDirectory ('live-qa-'+$runTag+'.json')) -Encoding utf8
    $sanitizedJson | Set-Content -LiteralPath $evidenceFile -Encoding utf8
    $client.Dispose()
    $handler.Dispose()
}
if (-not $allPassed) { throw 'LIVE_PUBLIC_QA_FAIL: inspect sanitized artifacts/release-20261102/live-qa.json; cleanup material is DPAPI-protected in its private directory.' }
Write-Output ('LIVE_PUBLIC_QA_PASS: '+$checks.Count+' labeled checks; sanitized artifacts/release-20261102/live-qa.json')

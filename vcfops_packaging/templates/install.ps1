<#
.SYNOPSIS
    VCF Operations content installer -- {{PACKAGE_NAME}}

.DESCRIPTION
    {{PACKAGE_DESCRIPTION}}

    Installs super metrics, views, dashboards, and custom groups onto a
    VCF Operations instance.

    Supports interactive prompts, CLI parameters, and environment variables.
    Parameters take precedence over environment variables; both take
    precedence over interactive prompts.

    Compatible with PowerShell 5.1 and PowerShell 7+.

.PARAMETER Host
    VCF Operations hostname or IP address. Env: VCFOPS_HOST.

.PARAMETER User
    VCF Operations username. Env: VCFOPS_USER. Default: admin.

.PARAMETER Password
    VCF Operations password. Env: VCFOPS_PASSWORD.

.PARAMETER AuthSource
    Auth source: 'local' or a domain name like 'int.sentania.net'.
    Env: VCFOPS_AUTH_SOURCE. Default: Local.

.PARAMETER SkipSslVerify
    Disable TLS certificate verification. For lab use only.
    Env: VCFOPS_VERIFY_SSL=false.

.PARAMETER SkipEnable
    Skip enabling super metrics on the Default Policy.

.EXAMPLE
    .\install.ps1

.EXAMPLE
    .\install.ps1 -Host ops.example.com -User admin -Password secret

.EXAMPLE
    $env:VCFOPS_HOST="ops.example.com"; $env:VCFOPS_USER="admin"; $env:VCFOPS_PASSWORD="secret"; .\install.ps1
#>
[CmdletBinding()]
param(
    [string]$Host     = $env:VCFOPS_HOST,
    [string]$User     = $env:VCFOPS_USER,
    [string]$Password = $env:VCFOPS_PASSWORD,
    [string]$AuthSource = $env:VCFOPS_AUTH_SOURCE,
    [switch]$SkipSslVerify = ($env:VCFOPS_VERIFY_SSL -eq 'false'),
    [switch]$SkipEnable
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Template variables (replaced by builder at build time):
$PackageName        = "{{PACKAGE_NAME}}"
$PackageDescription = "{{PACKAGE_DESCRIPTION}}"
$DashboardUuid      = "{{DASHBOARD_UUID}}"  # empty string if no dashboard

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ContentDir = Join-Path $ScriptDir "content"

# ---------------------------------------------------------------------------
# SSL: disable verification if requested (lab use only)
# ---------------------------------------------------------------------------
if ($SkipSslVerify) {
    Write-Warning "TLS certificate verification disabled."
    # PowerShell 5.1 and 7+ compatible SSL bypass
    if ($PSVersionTable.PSVersion.Major -ge 6) {
        # PS 7+: per-request -SkipCertificateCheck is used in Invoke-RestMethod calls
    } else {
        # PS 5.1: add a type that bypasses validation
        Add-Type @"
using System.Net;
using System.Security.Cryptography.X509Certificates;
public class TrustAllCerts : ICertificatePolicy {
    public bool CheckValidationResult(ServicePoint sp, X509Certificate cert,
        WebRequest req, int problem) { return true; }
}
"@
        [System.Net.ServicePointManager]::CertificatePolicy = New-Object TrustAllCerts
        [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
    }
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
function Write-Step($n, $total, $msg) {
    Write-Host ""
    Write-Host "[$n/$total] $msg"
}

function Write-Ok($msg) {
    Write-Host "  OK  $msg"
}

function Write-Fail($msg) {
    Write-Error "ERROR: $msg"
    exit 1
}

function Resolve-AuthSource($raw) {
    if (-not $raw -or $raw.Trim().ToLower() -eq 'local') { return 'Local' }
    return $raw.Trim()
}

function Load-Json($name) {
    $path = Join-Path $ContentDir $name
    if (-not (Test-Path $path)) { return $null }
    return Get-Content -Raw $path | ConvertFrom-Json
}

function Load-RawText($name) {
    $path = Join-Path $ContentDir $name
    if (-not (Test-Path $path)) { return $null }
    return [System.IO.File]::ReadAllText($path)
}

# ---------------------------------------------------------------------------
# Interactive credential prompts
# ---------------------------------------------------------------------------
function Get-Credentials {
    Write-Host ""
    Write-Host "VCF Content Factory -- $PackageName installer"
    Write-Host "Press Enter to accept [defaults] shown in brackets."
    Write-Host ""

    if (-not $script:Host) {
        $script:Host = Read-Host "VCF Operations host"
        if (-not $script:Host) { Write-Fail "Host is required." }
    }

    if (-not $script:User) {
        $input = Read-Host "Username [admin]"
        $script:User = if ($input) { $input } else { "admin" }
    }

    if (-not $script:AuthSource) {
        $input = Read-Host "Auth source (local, or domain like int.sentania.net) [local]"
        $script:AuthSource = $input
    }
    $script:AuthSource = Resolve-AuthSource $script:AuthSource

    if (-not $script:Password) {
        $secPw = Read-Host "Password" -AsSecureString
        $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secPw)
        $script:Password = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
        [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        if (-not $script:Password) { Write-Fail "Password is required." }
    }
}

# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------
$script:Token = $null
$script:BaseUrl = $null

function Invoke-Api {
    param(
        [string]$Method,
        [string]$Path,
        [hashtable]$Headers = @{},
        [object]$Body = $null,
        [hashtable]$Query = @{}
    )

    $uri = "$script:BaseUrl$Path"
    if ($Query.Count -gt 0) {
        $qs = ($Query.GetEnumerator() | ForEach-Object { "$($_.Key)=$([uri]::EscapeDataString($_.Value))" }) -join "&"
        $uri = "${uri}?${qs}"
    }

    $allHeaders = @{
        "Accept"       = "application/json"
        "Content-Type" = "application/json"
    }
    if ($script:Token) {
        $allHeaders["Authorization"] = "vRealizeOpsToken $script:Token"
    }
    foreach ($k in $Headers.Keys) { $allHeaders[$k] = $Headers[$k] }

    $params = @{
        Method  = $Method
        Uri     = $uri
        Headers = $allHeaders
    }
    if ($Body -ne $null) {
        $params["Body"] = ($Body | ConvertTo-Json -Depth 20 -Compress)
    }
    if ($SkipSslVerify -and $PSVersionTable.PSVersion.Major -ge 6) {
        $params["SkipCertificateCheck"] = $true
    }

    try {
        return Invoke-RestMethod @params
    } catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
        $responseBody = ""
        try {
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            $responseBody = $reader.ReadToEnd()
        } catch {}
        return @{ __statusCode = $statusCode; __body = $responseBody; __error = $_ }
    }
}

function Get-StatusCode($resp) {
    # Invoke-RestMethod throws on 4xx/5xx, so if we got here via the catch
    # path the response is a hashtable with __statusCode.
    if ($resp -is [hashtable] -and $resp.ContainsKey("__statusCode")) {
        return [int]$resp["__statusCode"]
    }
    return 200
}

function Authenticate {
    $body = @{
        username   = $script:User
        password   = $script:Password
        authSource = $script:AuthSource
    }
    $allHeaders = @{
        "Accept"       = "application/json"
        "Content-Type" = "application/json"
    }
    $params = @{
        Method  = "POST"
        Uri     = "$script:BaseUrl/api/auth/token/acquire"
        Headers = $allHeaders
        Body    = ($body | ConvertTo-Json -Compress)
    }
    if ($SkipSslVerify -and $PSVersionTable.PSVersion.Major -ge 6) {
        $params["SkipCertificateCheck"] = $true
    }
    try {
        $resp = Invoke-RestMethod @params
        $script:Token = $resp.token
    } catch {
        Write-Fail "Authentication failed: $_"
    }
}

function Get-CurrentUser {
    $resp = Invoke-Api -Method GET -Path "/api/auth/currentuser"
    if ((Get-StatusCode $resp) -ne 200) { Write-Fail "currentuser failed: $($resp.__body)" }
    return $resp
}

function Get-MarkerFilename {
    param([int]$TimeoutSeconds = 120)

    $deadline = [System.DateTime]::UtcNow.AddSeconds($TimeoutSeconds)

    # Wait for any running export to finish
    while ($true) {
        try {
            $g = Invoke-Api -Method GET -Path "/api/content/operations/export"
            $st = $g.state
            if ($st -ne "RUNNING" -and $st -ne "INITIALIZED") { break }
        } catch {}
        if ([System.DateTime]::UtcNow -gt $deadline) { Write-Fail "Timed out waiting for prior export" }
        Start-Sleep -Seconds 2
    }

    # Snapshot startTime before triggering our export
    $priorStart = 0
    try {
        $g = Invoke-Api -Method GET -Path "/api/content/operations/export"
        if ($g.startTime) { $priorStart = [long]$g.startTime }
    } catch {}

    $exportBody = @{ scope = "CUSTOM"; contentTypes = @("SUPER_METRICS") }
    $r = Invoke-Api -Method POST -Path "/api/content/operations/export" -Body $exportBody
    $sc = Get-StatusCode $r
    if ($sc -ne 200 -and $sc -ne 202) { Write-Fail "Marker-probe export failed ($sc): $($r.__body)" }

    $deadline = [System.DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ($true) {
        $g = Invoke-Api -Method GET -Path "/api/content/operations/export"
        $st = $g.state
        $startTime = if ($g.startTime) { [long]$g.startTime } else { 0 }
        if ($startTime -gt $priorStart -and $st -like "FINI*") { break }
        if ([System.DateTime]::UtcNow -gt $deadline) { Write-Fail "Marker-probe export timed out; state=$st" }
        Start-Sleep -Seconds 2
    }

    # Download the export zip and find the marker filename
    $zipUri = "$script:BaseUrl/api/content/operations/export/zip"
    $zipParams = @{ Uri = $zipUri; Method = "GET" }
    if ($script:Token) { $zipParams["Headers"] = @{ Authorization = "vRealizeOpsToken $script:Token" } }
    if ($SkipSslVerify -and $PSVersionTable.PSVersion.Major -ge 6) { $zipParams["SkipCertificateCheck"] = $true }

    $tmpZip = [System.IO.Path]::GetTempFileName() + ".zip"
    Invoke-WebRequest @zipParams -OutFile $tmpZip

    $zip = [System.IO.Compression.ZipFile]::OpenRead($tmpZip)
    $marker = $null
    foreach ($entry in $zip.Entries) {
        if ($entry.FullName.EndsWith("L.v1")) { $marker = $entry.FullName; break }
    }
    $zip.Dispose()
    Remove-Item $tmpZip -Force

    if (-not $marker) { Write-Fail "Export zip did not contain a *L.v1 marker file" }
    return $marker
}

function Import-ContentZip {
    param(
        [byte[]]$ZipBytes,
        [string]$Label,
        [int]$TimeoutSeconds = 180,
        [int]$Retries = 4
    )

    # Snapshot endTime before import so we can distinguish our import from prior
    $priorEnd = 0
    try {
        $pre = Invoke-Api -Method GET -Path "/api/content/operations/import"
        if ($pre.endTime) { $priorEnd = [long]$pre.endTime }
    } catch {}

    $importUri = "$script:BaseUrl/api/content/operations/import?force=true"

    # Use HttpClient for multipart upload (PS 5.1 compatible, avoids byte concat bugs)
    Add-Type -AssemblyName System.Net.Http

    $success = $false
    for ($attempt = 1; $attempt -le $Retries; $attempt++) {
        $handler = New-Object System.Net.Http.HttpClientHandler
        if ($SkipSslVerify) {
            $handler.ServerCertificateCustomValidationCallback = { $true }
        }
        $httpClient = New-Object System.Net.Http.HttpClient($handler)
        if ($script:Token) {
            $httpClient.DefaultRequestHeaders.Add("Authorization", "vRealizeOpsToken $script:Token")
        }

        $content = New-Object System.Net.Http.MultipartFormDataContent
        $fileContent = New-Object System.Net.Http.ByteArrayContent(,$ZipBytes)
        $fileContent.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse("application/zip")
        $content.Add($fileContent, "contentFile", "content.zip")

        try {
            $response = $httpClient.PostAsync($importUri, $content).Result
            $statusCode = [int]$response.StatusCode
            if ($statusCode -eq 403) {
                $wait = [Math]::Pow(2, $attempt)
                Write-Host "    [retry $attempt/$Retries] 403 task busy, waiting ${wait}s..."
                Start-Sleep -Seconds $wait
                $httpClient.Dispose()
                continue
            }
            if ($statusCode -ne 200 -and $statusCode -ne 202) {
                $body = $response.Content.ReadAsStringAsync().Result
                Write-Fail "Import POST failed for $Label ($statusCode): $body"
            }
            $success = $true
            $httpClient.Dispose()
            break
        } catch {
            $httpClient.Dispose()
            Write-Fail "Import POST for $Label threw: $_"
        }
    }
    if (-not $success) { Write-Fail "Import POST for $Label failed after $Retries retries (task busy)" }

    $deadline = [System.DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ($true) {
        $s = Invoke-Api -Method GET -Path "/api/content/operations/import"
        $state = $s.state
        $endTime = if ($s.endTime) { [long]$s.endTime } else { 0 }
        if ($endTime -gt $priorEnd -and $state -ne "RUNNING" -and $state -ne "INITIALIZED") {
            if ($state.ToUpper() -like "*FAIL*") { Write-Fail "Import of $Label finished with state=$state" }
            return
        }
        if ([System.DateTime]::UtcNow -gt $deadline) { Write-Fail "Import of $Label timed out; state=$state" }
        Start-Sleep -Seconds 2
    }
}

function Get-DefaultPolicyId {
    $resp = Invoke-Api -Method GET -Path "/api/policies"
    foreach ($p in $resp.policySummaries) {
        if ($p.defaultPolicy) { return $p.id }
    }
    Write-Fail "No default policy found in /api/policies"
}

function Get-SupermetricsByName {
    param([string[]]$Names)
    $found = @{}
    $page = 0; $pageSize = 1000
    $target = [System.Collections.Generic.HashSet[string]]::new($Names)
    do {
        $resp = Invoke-Api -Method GET -Path "/api/supermetrics" -Query @{ page = "$page"; pageSize = "$pageSize" }
        $items = $resp.superMetrics
        foreach ($sm in $items) {
            if ($target.Contains($sm.name)) { $found[$sm.name] = $sm.id }
        }
        $total = if ($resp.pageInfo -and $resp.pageInfo.totalCount) { [int]$resp.pageInfo.totalCount } else { $items.Count }
        $page++
    } while (($page * $pageSize) -lt $total -and $items.Count -gt 0)
    return $found
}

function Enable-SupermetricOnDefaultPolicy {
    param($SmId, $SmName, $ResourceKinds)
    $policyId = Get-DefaultPolicyId
    $body = @{
        superMetricId    = $SmId
        resourceKindKeys = @($ResourceKinds | ForEach-Object {
            @{
                adapterKind  = if ($_.adapterKindKey) { $_.adapterKindKey } else { $_.adapterKind }
                resourceKind = if ($_.resourceKindKey) { $_.resourceKindKey } else { $_.resourceKind }
            }
        })
    }
    $headers = @{ "X-Ops-API-use-unsupported" = "true" }
    $uri = "$script:BaseUrl/internal/supermetrics/assign?policyIds=$([uri]::EscapeDataString($policyId))"

    $allHeaders = @{
        "Accept"                  = "application/json"
        "Content-Type"            = "application/json"
        "Authorization"           = "vRealizeOpsToken $script:Token"
        "X-Ops-API-use-unsupported" = "true"
    }
    $params = @{
        Method  = "PUT"
        Uri     = $uri
        Headers = $allHeaders
        Body    = ($body | ConvertTo-Json -Depth 10 -Compress)
    }
    if ($SkipSslVerify -and $PSVersionTable.PSVersion.Major -ge 6) { $params["SkipCertificateCheck"] = $true }
    try {
        Invoke-RestMethod @params | Out-Null
    } catch {
        Write-Fail "Enable SM '$SmName' failed: $_"
    }
}

function Upsert-CustomGroup {
    param($Payload)
    $name = $Payload.resourceKey.name
    $resp = Invoke-Api -Method GET -Path "/api/resources/groups" -Query @{ name = $name; pageSize = "100" }
    $existingId = $null
    foreach ($g in $resp.groups) {
        if ($g.resourceKey.name -eq $name) { $existingId = $g.id; break }
    }
    if ($existingId) {
        $r = Invoke-Api -Method PUT -Path "/api/resources/groups/$existingId" -Body $Payload
        $sc = Get-StatusCode $r
        if ($sc -ne 200 -and $sc -ne 201 -and $sc -ne 204) { Write-Fail "Custom group PUT failed ($sc)" }
    } else {
        $r = Invoke-Api -Method POST -Path "/api/resources/groups" -Body $Payload
        $sc = Get-StatusCode $r
        if ($sc -ne 200 -and $sc -ne 201) { Write-Fail "Custom group POST failed ($sc)" }
    }
}

# ---------------------------------------------------------------------------
# Content-zip builders
# ---------------------------------------------------------------------------
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

function New-ZipBytes {
    param([hashtable]$Entries)
    # Entries: { "filename" = [byte[]] or [string] }
    $ms = New-Object System.IO.MemoryStream
    $zip = New-Object System.IO.Compression.ZipArchive($ms, [System.IO.Compression.ZipArchiveMode]::Create, $true)
    foreach ($key in $Entries.Keys) {
        $val = $Entries[$key]
        $entry = $zip.CreateEntry($key, [System.IO.Compression.CompressionLevel]::Optimal)
        $stream = $entry.Open()
        if ($val -is [string]) {
            $bytes = [System.Text.Encoding]::UTF8.GetBytes($val)
            $stream.Write($bytes, 0, $bytes.Length)
        } elseif ($val -is [byte[]]) {
            $stream.Write($val, 0, $val.Length)
        }
        # empty string/null -> zero bytes
        $stream.Close()
    }
    $zip.Dispose()
    return $ms.ToArray()
}

function New-SmZip {
    param($SmDict, $Marker, $OwnerId)
    # SmDict is a dict keyed by UUID (wire format matching vcfops_supermetrics/client.py)
    $entries = @{
        $Marker              = $OwnerId
        "supermetrics.json"  = ($SmDict | ConvertTo-Json -Depth 20)
        "configuration.json" = (@{ superMetrics = ($SmDict.PSObject.Properties.Name.Count); type = "ALL" } | ConvertTo-Json -Compress)
    }
    return New-ZipBytes $entries
}

function New-ViewsInnerZip {
    param([string]$XmlText)
    return New-ZipBytes @{ "content.xml" = $XmlText }
}

function New-DashboardInnerZip {
    param([string]$DashJson)
    $entries = @{
        "dashboard/dashboard.json" = $DashJson
        "dashboard/resources/resources.properties"    = ""
        "dashboard/resources/resources_es.properties" = ""
        "dashboard/resources/resources_fr.properties" = ""
        "dashboard/resources/resources_ja.properties" = ""
    }
    return New-ZipBytes $entries
}

function New-DashboardZip {
    param($ViewsXml, $DashJson, $Marker, $OwnerId, $NViews, $NDashboards, $DashboardIds)

    $patchedJson = $DashJson -replace "PLACEHOLDER_USER_ID", $OwnerId

    $innerDash = New-DashboardInnerZip -DashJson $patchedJson

    $sharingList = @(@{
        groupName  = "Everyone"
        sourceType = "LOCAL"
        dashboards = @($DashboardIds | ForEach-Object { @{ dashboardId = $_ } })
    })

    $userMappings = @{
        sources = @()
        users   = @(@{ userName = "admin"; userId = $OwnerId })
    }

    $config = @{ type = "CUSTOM" }
    if ($NViews -gt 0) { $config["views"] = $NViews }
    if ($NDashboards -gt 0) {
        $config["dashboards"] = $NDashboards
        $config["dashboardsByOwner"] = @(@{ owner = $OwnerId; count = $NDashboards })
    }

    # Build outer zip manually to include directory entries
    $ms = New-Object System.IO.MemoryStream
    $outerZip = New-Object System.IO.Compression.ZipArchive($ms, [System.IO.Compression.ZipArchiveMode]::Create, $true)

    # Marker
    $e = $outerZip.CreateEntry($Marker, [System.IO.Compression.CompressionLevel]::Optimal)
    $s = $e.Open()
    $b = [System.Text.Encoding]::UTF8.GetBytes($OwnerId)
    $s.Write($b, 0, $b.Length); $s.Close()

    # views.zip
    if ($NViews -gt 0 -and $ViewsXml) {
        $viewsInner = New-ViewsInnerZip -XmlText $ViewsXml
        $e = $outerZip.CreateEntry("views.zip", [System.IO.Compression.CompressionLevel]::Optimal)
        $s = $e.Open(); $s.Write($viewsInner, 0, $viewsInner.Length); $s.Close()
    }

    # Explicit directory entries (mirroring real export shape)
    $outerZip.CreateEntry("dashboards/") | Out-Null
    $outerZip.CreateEntry("dashboardsharings/") | Out-Null

    # dashboards/<ownerId>
    $e = $outerZip.CreateEntry("dashboards/$OwnerId", [System.IO.Compression.CompressionLevel]::Optimal)
    $s = $e.Open(); $s.Write($innerDash, 0, $innerDash.Length); $s.Close()

    # dashboardsharings/<ownerId>
    $sharingJson = [System.Text.Encoding]::UTF8.GetBytes(($sharingList | ConvertTo-Json -Depth 10))
    $e = $outerZip.CreateEntry("dashboardsharings/$OwnerId", [System.IO.Compression.CompressionLevel]::Optimal)
    $s = $e.Open(); $s.Write($sharingJson, 0, $sharingJson.Length); $s.Close()

    # usermappings.json
    $umJson = [System.Text.Encoding]::UTF8.GetBytes(($userMappings | ConvertTo-Json -Depth 10))
    $e = $outerZip.CreateEntry("usermappings.json", [System.IO.Compression.CompressionLevel]::Optimal)
    $s = $e.Open(); $s.Write($umJson, 0, $umJson.Length); $s.Close()

    # configuration.json
    $cfgJson = [System.Text.Encoding]::UTF8.GetBytes(($config | ConvertTo-Json -Depth 10 -Compress))
    $e = $outerZip.CreateEntry("configuration.json", [System.IO.Compression.CompressionLevel]::Optimal)
    $s = $e.Open(); $s.Write($cfgJson, 0, $cfgJson.Length); $s.Close()

    $outerZip.Dispose()
    return $ms.ToArray()
}

function Get-DashboardIds {
    param([string]$DashJson, [string]$OwnerId)
    $patchedJson = $DashJson -replace "PLACEHOLDER_USER_ID", $OwnerId
    $data = $patchedJson | ConvertFrom-Json
    return @($data.dashboards | Where-Object { $_.id } | ForEach-Object { $_.id })
}

# ---------------------------------------------------------------------------
# Main install flow
# ---------------------------------------------------------------------------

Get-Credentials

$script:BaseUrl = "https://$($script:Host)/suite-api"

$hasSmJson       = Test-Path (Join-Path $ContentDir "supermetrics.json")
$hasDashJson     = Test-Path (Join-Path $ContentDir "dashboard.json")
$hasCgJson       = Test-Path (Join-Path $ContentDir "customgroup.json")
$hasSmMeta       = Test-Path (Join-Path $ContentDir "sm_metadata.json")
$hasViewsXml     = Test-Path (Join-Path $ContentDir "views_content.xml")

$steps = @("auth", "marker", "owner")
if ($hasSmJson)   { $steps += "sm_import" }
if ($hasDashJson) { $steps += "dash_import" }
if ($hasSmMeta)   { $steps += "sm_enable" }
if ($hasCgJson)   { $steps += "cg_upsert" }
$TOTAL = $steps.Count
$step = 0

Write-Host ""
Write-Host "Installing $PackageName onto $($script:Host)..."

$step++
Write-Step $step $TOTAL "Authenticating as $($script:User)@$($script:Host) (auth: $($script:AuthSource)) ..."
Authenticate
Write-Ok "Authenticated"

$step++
Write-Step $step $TOTAL "Discovering instance marker filename..."
$marker = Get-MarkerFilename
Write-Ok "Marker: $marker"

$step++
Write-Step $step $TOTAL "Resolving current user ID..."
$currentUser = Get-CurrentUser
$ownerId = $currentUser.id
Write-Ok "Owner user ID: $ownerId"

if ($hasSmJson) {
    $step++
    Write-Step $step $TOTAL "Importing super metrics..."
    $smDict = Load-Json "supermetrics.json"
    $smZip = New-SmZip -SmDict $smDict -Marker $marker -OwnerId $ownerId
    Import-ContentZip -ZipBytes $smZip -Label "super metrics"
    $smCount = ($smDict.PSObject.Properties.Name).Count
    Write-Ok "Imported $smCount super metric(s)"
}

if ($hasDashJson) {
    $step++
    Write-Step $step $TOTAL "Importing view + dashboard..."
    $dashJson = Load-RawText "dashboard.json"
    $viewsXml = if ($hasViewsXml) { Load-RawText "views_content.xml" } else { "" }
    $dashIds = Get-DashboardIds -DashJson $dashJson -OwnerId $ownerId
    $nViews = if ($hasViewsXml) { 1 } else { 0 }
    $dashZip = New-DashboardZip -ViewsXml $viewsXml -DashJson $dashJson -Marker $marker `
        -OwnerId $ownerId -NViews $nViews -NDashboards 1 -DashboardIds $dashIds
    Import-ContentZip -ZipBytes $dashZip -Label "dashboard + view"
    Write-Ok "Imported $nViews view(s) + 1 dashboard"
}

if ($hasSmMeta) {
    $step++
    if ($SkipEnable) {
        Write-Host ""
        Write-Host "[$step/$TOTAL] Skipping super metric enable (--SkipEnable set)"
    } else {
        Write-Step $step $TOTAL "Enabling super metrics on Default Policy..."
        $smMeta = Load-Json "sm_metadata.json"
        # Handle both single object and array
        if ($smMeta -isnot [System.Array]) { $smMeta = @($smMeta) }
        $names = @($smMeta | ForEach-Object { $_.name })
        $serverIds = Get-SupermetricsByName -Names $names
        foreach ($sm in $smMeta) {
            $smName = $sm.name
            $smId = $serverIds[$smName]
            if (-not $smId) {
                Write-Host "  WARN  Could not resolve ID for '$smName' -- skipping enable"
                continue
            }
            Enable-SupermetricOnDefaultPolicy -SmId $smId -SmName $smName -ResourceKinds $sm.resourceKinds
            Write-Ok "Enabled: $smName"
        }
    }
}

if ($hasCgJson) {
    $step++
    Write-Step $step $TOTAL "Upserting custom group(s)..."
    $cgData = Load-Json "customgroup.json"
    # Handle both single object and array
    if ($cgData -isnot [System.Array]) { $cgData = @($cgData) }
    foreach ($cg in $cgData) {
        $cgName = $cg.resourceKey.name
        Upsert-CustomGroup -Payload $cg
        Write-Ok "Upserted: $cgName"
    }
}

Write-Host ""
Write-Host "Done. All content installed successfully."

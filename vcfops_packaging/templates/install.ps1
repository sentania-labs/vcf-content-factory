<#
.SYNOPSIS
    VCF Operations content installer/uninstaller -- {{PACKAGE_NAME}}

.DESCRIPTION
    {{PACKAGE_DESCRIPTION}}

    Installs or uninstalls super metrics, views, dashboards, and custom groups
    on a VCF Operations instance.

    Run without -Uninstall (or with -Install) to install content.
    Run with -Uninstall to remove all content this package installed.

    Supports interactive prompts, CLI parameters, and environment variables.
    Parameters take precedence over environment variables; both take
    precedence over interactive prompts.

    Compatible with PowerShell 5.1 and PowerShell 7+.

    Exit codes:
      0 -- success
      1 -- fatal error (auth failure, unexpected API error)
      2 -- partial failure (some items skipped or failed; others succeeded)

.PARAMETER OpsHost
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
    (Install mode) Skip enabling super metrics on the Default Policy.

.PARAMETER Install
    Install mode (default).

.PARAMETER Uninstall
    Uninstall mode: delete all content in this bundle from the instance.

.PARAMETER Force
    With -Uninstall: skip dependency checks and delete unconditionally.

.EXAMPLE
    .\install.ps1

.EXAMPLE
    .\install.ps1 -OpsHost ops.example.com -User admin -Password secret

.EXAMPLE
    .\install.ps1 -Uninstall

.EXAMPLE
    .\install.ps1 -Uninstall -Force

.EXAMPLE
    $env:VCFOPS_HOST="ops.example.com"; $env:VCFOPS_USER="admin"; $env:VCFOPS_PASSWORD="secret"; .\install.ps1
#>
[CmdletBinding()]
param(
    [string]$OpsHost    = $env:VCFOPS_HOST,
    [string]$User       = $env:VCFOPS_USER,
    [string]$Password   = $env:VCFOPS_PASSWORD,
    [string]$AuthSource = $env:VCFOPS_AUTH_SOURCE,
    [switch]$SkipSslVerify = ($env:VCFOPS_VERIFY_SSL -eq 'false'),
    [switch]$SkipEnable,
    [switch]$Install,
    [switch]$Uninstall,
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ($Install -and $Uninstall) {
    Write-Error "ERROR: -Install and -Uninstall are mutually exclusive."
    exit 1
}
if ($Force -and -not $Uninstall) {
    Write-Error "ERROR: -Force is only valid with -Uninstall."
    exit 1
}

# Template variables (replaced by builder at build time):
$PackageName        = "{{PACKAGE_NAME}}"
$PackageDescription = "{{PACKAGE_DESCRIPTION}}"
$DashboardUuid      = "{{DASHBOARD_UUID}}"  # empty string if no dashboard

# Content manifest (replaced by builder at build time -- JSON object):
$ContentManifestJson = '{{CONTENT_MANIFEST}}'
$ContentManifest     = $ContentManifestJson | ConvertFrom-Json

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ContentDir = Join-Path $ScriptDir "content"

# ---------------------------------------------------------------------------
# SSL: disable verification if requested (lab use only)
# ---------------------------------------------------------------------------
if ($SkipSslVerify) {
    Write-Warning "TLS certificate verification disabled."
    if ($PSVersionTable.PSVersion.Major -lt 6) {
        Add-Type @"
using System.Net;
using System.Security.Cryptography.X509Certificates;
public class TrustAllCertsVcf : ICertificatePolicy {
    public bool CheckValidationResult(ServicePoint sp, X509Certificate cert,
        WebRequest req, int problem) { return true; }
}
"@
        [System.Net.ServicePointManager]::CertificatePolicy = New-Object TrustAllCertsVcf
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

function Write-Warn($msg) {
    Write-Host "  WARN  $msg"
}

function Write-Fail($msg) {
    Write-Error "ERROR: $msg"
    exit 1
}

function Resolve-AuthSource($raw) {
    # Returns the canonical value used by the Suite API ('Local' for local accounts).
    # The UI login helper translates 'Local' -> 'localItem' internally.
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
# Interactive credential prompts (shared by install and uninstall)
# ---------------------------------------------------------------------------
function Get-Credentials {
    param([string]$Mode = "installer")
    Write-Host ""
    Write-Host "VCF Content Factory -- $PackageName $Mode"
    Write-Host "Press Enter to accept [defaults] shown in brackets."
    Write-Host ""

    if (-not $script:OpsHost) {
        $script:OpsHost = Read-Host "VCF Operations host"
        if (-not $script:OpsHost) { Write-Fail "Host is required." }
    }

    if (-not $script:User) {
        $inp = Read-Host "Username [admin]"
        $script:User = if ($inp) { $inp } else { "admin" }
    }

    if (-not $script:AuthSource) {
        $inp = Read-Host "Auth source (local, or domain like int.sentania.net) [local]"
        $script:AuthSource = $inp
    }
    $script:AuthSource = Resolve-AuthSource $script:AuthSource

    if (-not $script:Password) {
        $secPw = Read-Host "Password" -AsSecureString
        $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secPw)
        $script:Password = [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
        [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        if (-not $script:Password) { Write-Fail "Password is required." }
    }
}

# ---------------------------------------------------------------------------
# Suite API helpers
# ---------------------------------------------------------------------------
$script:Token   = $null
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
        $qs = ($Query.GetEnumerator() | ForEach-Object { "$($_.Key)=$([uri]::EscapeDataString([string]$_.Value))" }) -join "&"
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
    if ($null -ne $Body) {
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

    while ($true) {
        try {
            $g = Invoke-Api -Method GET -Path "/api/content/operations/export"
            $st = $g.state
            if ($st -ne "RUNNING" -and $st -ne "INITIALIZED") { break }
        } catch {}
        if ([System.DateTime]::UtcNow -gt $deadline) { Write-Fail "Timed out waiting for prior export" }
        Start-Sleep -Seconds 2
    }

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

    $priorEnd = 0
    try {
        $pre = Invoke-Api -Method GET -Path "/api/content/operations/import"
        if ($pre.endTime) { $priorEnd = [long]$pre.endTime }
    } catch {}

    $importUri = "$script:BaseUrl/api/content/operations/import?force=true"

    Add-Type -AssemblyName System.Net.Http

    $success = $false
    for ($attempt = 1; $attempt -le $Retries; $attempt++) {
        $handler = New-Object System.Net.Http.HttpClientHandler
        if ($SkipSslVerify -and $PSVersionTable.PSVersion.Major -ge 6) {
            # PS 7+ / .NET Core: set the callback directly on the handler.
            # PS 5.1 / .NET Framework: ServicePointManager (set at script startup)
            # covers HttpClient too, so no per-handler callback is needed.
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
            # $response.StatusCode is System.Net.HttpStatusCode (enum); cast to int.
            # Guard against null in case the task returned without a response.
            if ($null -eq $response) { Write-Fail "Import POST for $Label returned null response" }
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
    $uri = "$script:BaseUrl/internal/supermetrics/assign?policyIds=$([uri]::EscapeDataString($policyId))"
    $allHeaders = @{
        "Accept"                    = "application/json"
        "Content-Type"              = "application/json"
        "Authorization"             = "vRealizeOpsToken $script:Token"
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
        throw "Enable SM '$SmName' failed: $_"
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
        if ($sc -eq 500) {
            # The custom group PUT endpoint sometimes returns 500 even when the
            # update was applied (server-side race condition). Verify via GET
            # before treating as fatal.
            $chk = Invoke-Api -Method GET -Path "/api/resources/groups" -Query @{ name = $name; pageSize = "100" }
            $stillExists = $false
            foreach ($g in $chk.groups) { if ($g.resourceKey.name -eq $name) { $stillExists = $true; break } }
            if ($stillExists) {
                Write-Warn "Custom group PUT returned 500 but group exists -- treating as success: $name"
            } else {
                Write-Fail "Custom group PUT failed ($sc)"
            }
        } elseif ($sc -ne 200 -and $sc -ne 201 -and $sc -ne 204) {
            Write-Fail "Custom group PUT failed ($sc)"
        }
    } else {
        $r = Invoke-Api -Method POST -Path "/api/resources/groups" -Body $Payload
        $sc = Get-StatusCode $r
        if ($sc -ne 200 -and $sc -ne 201) { Write-Fail "Custom group POST failed ($sc)" }
    }
}

# Uninstall: Suite API delete helpers
function Remove-Supermetric {
    param([string]$SmId)
    $resp = Invoke-Api -Method DELETE -Path "/api/supermetrics/$SmId"
    return Get-StatusCode $resp
}

function Find-CustomGroupIds {
    param([string[]]$Names)
    $found = @{}
    $target = [System.Collections.Generic.HashSet[string]]::new($Names)
    $page = 0; $pageSize = 1000
    do {
        $resp = Invoke-Api -Method GET -Path "/api/resources/groups" `
            -Query @{ page = "$page"; pageSize = "$pageSize" }
        $groups = $resp.groups
        if (-not $groups) { break }
        foreach ($g in $groups) {
            $n = $g.resourceKey.name
            if ($target.Contains($n)) { $found[$n] = $g.id }
        }
        $total = if ($resp.pageInfo -and $resp.pageInfo.totalCount) {
            [int]$resp.pageInfo.totalCount
        } else { $groups.Count }
        $page++
    } while (($page * $pageSize) -lt $total -and $groups.Count -gt 0)
    return $found
}

function Remove-CustomGroup {
    param([string]$GroupId)
    $resp = Invoke-Api -Method DELETE -Path "/api/resources/groups/$GroupId"
    return Get-StatusCode $resp
}

# ---------------------------------------------------------------------------
# Content-zip builders (install mode)
# ---------------------------------------------------------------------------
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

function New-ZipBytes {
    param([hashtable]$Entries)
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
        $stream.Close()
    }
    $zip.Dispose()
    return $ms.ToArray()
}

function New-SmZip {
    param($SmDict, $Marker, $OwnerId)
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
        "dashboard/dashboard.json"                        = $DashJson
        "dashboard/resources/resources.properties"        = ""
        "dashboard/resources/resources_es.properties"     = ""
        "dashboard/resources/resources_fr.properties"     = ""
        "dashboard/resources/resources_ja.properties"     = ""
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

    $ms = New-Object System.IO.MemoryStream
    $outerZip = New-Object System.IO.Compression.ZipArchive($ms, [System.IO.Compression.ZipArchiveMode]::Create, $true)

    $e = $outerZip.CreateEntry($Marker, [System.IO.Compression.CompressionLevel]::Optimal)
    $s = $e.Open()
    $b = [System.Text.Encoding]::UTF8.GetBytes($OwnerId)
    $s.Write($b, 0, $b.Length); $s.Close()

    if ($NViews -gt 0 -and $ViewsXml) {
        $viewsInner = New-ViewsInnerZip -XmlText $ViewsXml
        $e = $outerZip.CreateEntry("views.zip", [System.IO.Compression.CompressionLevel]::Optimal)
        $s = $e.Open(); $s.Write($viewsInner, 0, $viewsInner.Length); $s.Close()
    }

    $outerZip.CreateEntry("dashboards/") | Out-Null
    $outerZip.CreateEntry("dashboardsharings/") | Out-Null

    $e = $outerZip.CreateEntry("dashboards/$OwnerId", [System.IO.Compression.CompressionLevel]::Optimal)
    $s = $e.Open(); $s.Write($innerDash, 0, $innerDash.Length); $s.Close()

    $sharingJson = [System.Text.Encoding]::UTF8.GetBytes(($sharingList | ConvertTo-Json -Depth 10))
    $e = $outerZip.CreateEntry("dashboardsharings/$OwnerId", [System.IO.Compression.CompressionLevel]::Optimal)
    $s = $e.Open(); $s.Write($sharingJson, 0, $sharingJson.Length); $s.Close()

    $umJson = [System.Text.Encoding]::UTF8.GetBytes(($userMappings | ConvertTo-Json -Depth 10))
    $e = $outerZip.CreateEntry("usermappings.json", [System.IO.Compression.CompressionLevel]::Optimal)
    $s = $e.Open(); $s.Write($umJson, 0, $umJson.Length); $s.Close()

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
# UI session helpers (uninstall mode: dashboard + view delete)
# ---------------------------------------------------------------------------
$script:WebSession = $null
$script:CsrfToken  = $null
$script:UiTid      = 1

function Start-UISession {
    $cookieContainer = New-Object System.Net.CookieContainer
    $iwrParams = @{ UseBasicParsing = $true }
    if ($SkipSslVerify -and $PSVersionTable.PSVersion.Major -ge 6) {
        $iwrParams["SkipCertificateCheck"] = $true
    }

    $webSession = New-Object Microsoft.PowerShell.Commands.WebRequestSession
    $webSession.Cookies = $cookieContainer
    $script:WebSession = $webSession

    # Step 1: seed JSESSIONID
    Invoke-WebRequest @iwrParams `
        -Uri "https://$($script:OpsHost)/ui/login.action?vcf=1" `
        -WebSession $script:WebSession | Out-Null

    # Step 2: login
    # The UI form expects 'localItem' for local accounts; translate from canonical 'Local'.
    $uiAuthSource = if ($script:AuthSource -eq 'Local') { 'localItem' } else { $script:AuthSource }
    $loginBody = "mainAction=login" +
        "&userName=$([uri]::EscapeDataString($script:User))" +
        "&password=$([uri]::EscapeDataString($script:Password))" +
        "&authSourceId=$([uri]::EscapeDataString($uiAuthSource))" +
        "&authSourceName=Local+Account" +
        "&authSourceType=" +
        "&forceLogin=false" +
        "&timezone=0" +
        "&languageCode=us"

    $loginResp = Invoke-WebRequest @iwrParams `
        -Uri "https://$($script:OpsHost)/ui/login.action" `
        -Method POST `
        -ContentType "application/x-www-form-urlencoded" `
        -Body $loginBody `
        -WebSession $script:WebSession

    if ($loginResp.Content.Trim() -ne "ok") {
        Write-Fail "UI authentication failed: $($loginResp.Content)"
    }

    # Step 3: GET index.action WITHOUT following redirect to capture OPS_SESSION
    try {
        $indexResp = Invoke-WebRequest @iwrParams `
            -Uri "https://$($script:OpsHost)/ui/index.action" `
            -MaximumRedirection 0 `
            -WebSession $script:WebSession `
            -ErrorAction SilentlyContinue
    } catch {
        $indexResp = $_.Exception.Response
    }

    $opsCookie = $null
    foreach ($c in $script:WebSession.Cookies.GetCookies("https://$($script:OpsHost)/")) {
        if ($c.Name -eq "OPS_SESSION") { $opsCookie = $c.Value; break }
    }
    if (-not $opsCookie) {
        if ($indexResp -and $indexResp.Headers -and $indexResp.Headers["Set-Cookie"]) {
            $setCookie = $indexResp.Headers["Set-Cookie"]
            if ($setCookie -match "OPS_SESSION=([^;]+)") {
                $opsCookie = $Matches[1]
            }
        }
    }
    if (-not $opsCookie) {
        Write-Fail "OPS_SESSION cookie not received -- check credentials and auth source"
    }

    try {
        $decoded = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($opsCookie))
        $opsData = $decoded | ConvertFrom-Json
        $script:CsrfToken = $opsData.csrfToken
    } catch {
        Write-Fail "Failed to decode OPS_SESSION cookie: $_"
    }
    if (-not $script:CsrfToken) {
        Write-Fail "csrfToken not found in OPS_SESSION payload"
    }
}

function Stop-UISession {
    if (-not $script:WebSession) { return }
    try {
        $p = @{ UseBasicParsing = $true; WebSession = $script:WebSession }
        if ($SkipSslVerify -and $PSVersionTable.PSVersion.Major -ge 6) {
            $p["SkipCertificateCheck"] = $true
        }
        Invoke-WebRequest @p `
            -Uri "https://$($script:OpsHost)/ui/login.action?mainAction=logout" `
            -MaximumRedirection 0 `
            -ErrorAction SilentlyContinue | Out-Null
    } catch {}
    $script:WebSession = $null
    $script:CsrfToken  = $null
}

function Invoke-DashboardAction {
    param([hashtable]$FormFields)
    $body = ($FormFields.GetEnumerator() | ForEach-Object {
        "$([uri]::EscapeDataString($_.Key))=$([uri]::EscapeDataString([string]$_.Value))"
    }) -join "&"
    $p = @{
        UseBasicParsing = $true
        Uri             = "https://$($script:OpsHost)/ui/dashboard.action"
        Method          = "POST"
        ContentType     = "application/x-www-form-urlencoded"
        Body            = $body
        WebSession      = $script:WebSession
    }
    if ($SkipSslVerify -and $PSVersionTable.PSVersion.Major -ge 6) {
        $p["SkipCertificateCheck"] = $true
    }
    $resp = Invoke-WebRequest @p
    return $resp.Content | ConvertFrom-Json
}

function Get-AllDashboards {
    $result = Invoke-DashboardAction -FormFields @{
        mainAction           = "getDashboardList"
        secureToken          = $script:CsrfToken
        currentComponentInfo = "TODO"
        globalDate           = '{"dateRange":"last6Hour"}'
    }
    return @($result.dashboards | Where-Object { $_ })
}

function Remove-Dashboards {
    param([object[]]$Dashboards)
    $tabIds = ($Dashboards | ForEach-Object {
        '{"tabId":"' + $_.id + '","tabName":"' + ($_.name -replace '"','\"') + '"}'
    }) -join ","
    $tabIdsJson = "[$tabIds]"
    Invoke-DashboardAction -FormFields @{
        mainAction           = "deleteTab"
        tabIds               = $tabIdsJson
        secureToken          = $script:CsrfToken
        currentComponentInfo = "TODO"
        globalDate           = '{"dateRange":"last6Hour"}'
    } | Out-Null
}

function Get-NextTid {
    $t = $script:UiTid
    $script:UiTid++
    return $t
}

function Invoke-ExtDirect {
    param([object[]]$Calls)
    $p = @{
        UseBasicParsing = $true
        Uri             = "https://$($script:OpsHost)/ui/vcops/services/router"
        Method          = "POST"
        ContentType     = "application/json"
        Body            = ($Calls | ConvertTo-Json -Depth 10 -Compress)
        Headers         = @{ secureToken = $script:CsrfToken }
        WebSession      = $script:WebSession
    }
    if ($SkipSslVerify -and $PSVersionTable.PSVersion.Major -ge 6) {
        $p["SkipCertificateCheck"] = $true
    }
    $resp = Invoke-WebRequest @p
    return $resp.Content | ConvertFrom-Json
}

function Get-AllViews {
    $tid = Get-NextTid
    $result = Invoke-ExtDirect -Calls @(@{
        action = "viewServiceController"
        method = "getGroupedViewDefinitionThumbnails"
        data   = @()
        type   = "rpc"
        tid    = $tid
    })
    if ($result[0].type -eq "exception") {
        Write-Fail "View list failed: $($result[0].message)"
    }
    $allViews = [System.Collections.Generic.List[object]]::new()
    foreach ($group in $result[0].result) {
        foreach ($v in $group.views) { $allViews.Add($v) }
    }
    return $allViews
}

function Remove-View {
    param([string]$ViewId)
    $tid = Get-NextTid
    $result = Invoke-ExtDirect -Calls @(@{
        action = "viewServiceController"
        method = "deleteView"
        data   = @($ViewId)
        type   = "rpc"
        tid    = $tid
    })
    if ($result[0].type -eq "exception") {
        throw "deleteView $ViewId failed: $($result[0].message)"
    }
}

# ---------------------------------------------------------------------------
# Content type registry (PowerShell)
#
# Each hashtable entry describes one content type.  The install and uninstall
# flows iterate this registry rather than containing hard-coded if/elif chains.
# To add a new content type, add an entry here.  No other changes required.
#
# Entry keys:
#   ContentType     string   key in $ContentManifest (for uninstall names)
#   InstallFile     string   filename under $ContentDir (presence = active for install)
#   InstallLabel    string   human-readable step description for install
#   InstallFn       string   name of a function to call for install (or $null)
#   InstallOrder    int      lower runs first during install
#   UninstallLabel  string   human-readable step description for uninstall
#   UninstallFn     string   name of a function to call for uninstall (or $null)
#   UninstallOrder  int      lower runs first during uninstall
#   NeedsUi        bool     true = requires Start-UISession before running
# ---------------------------------------------------------------------------

$script:ContentRegistry = @(
    @{
        ContentType    = "supermetrics"
        InstallFile    = "supermetrics.json"
        InstallLabel   = "Importing super metrics..."
        InstallFn      = "Install-Supermetrics"
        InstallOrder   = 1
        UninstallLabel = "Deleting super metric(s)..."
        UninstallFn    = "Uninstall-Supermetrics"
        UninstallOrder = 40
        NeedsUi        = $false
    },
    @{
        ContentType    = "views_and_dashboards"
        InstallFile    = "dashboard.json"
        InstallLabel   = "Importing view + dashboard..."
        InstallFn      = "Install-Dashboard"
        InstallOrder   = 2
        UninstallLabel = $null
        UninstallFn    = $null
        UninstallOrder = $null
        NeedsUi        = $false
    },
    @{
        ContentType    = "sm_enable"
        InstallFile    = "sm_metadata.json"
        InstallLabel   = "Enabling super metrics on Default Policy..."
        InstallFn      = "Install-SmEnable"
        InstallOrder   = 3
        UninstallLabel = $null
        UninstallFn    = $null
        UninstallOrder = $null
        NeedsUi        = $false
    },
    @{
        ContentType    = "customgroups"
        InstallFile    = "customgroup.json"
        InstallLabel   = "Upserting custom group(s)..."
        InstallFn      = "Install-CustomGroups"
        InstallOrder   = 4
        UninstallLabel = "Deleting custom group(s)..."
        UninstallFn    = "Uninstall-CustomGroups"
        UninstallOrder = 50
        NeedsUi        = $false
    },
    # Uninstall-only entries for dashboards and views
    @{
        ContentType    = "dashboards"
        InstallFile    = $null
        InstallLabel   = $null
        InstallFn      = $null
        InstallOrder   = $null
        UninstallLabel = "Deleting dashboard(s)..."
        UninstallFn    = "Uninstall-Dashboards"
        UninstallOrder = 10
        NeedsUi        = $true
    },
    @{
        ContentType    = "views"
        InstallFile    = $null
        InstallLabel   = $null
        InstallFn      = $null
        InstallOrder   = $null
        UninstallLabel = "Deleting view(s)..."
        UninstallFn    = "Uninstall-Views"
        UninstallOrder = 20
        NeedsUi        = $true
    }
)

# ---------------------------------------------------------------------------
# Per-type install functions (called by the registry loop)
# ---------------------------------------------------------------------------

function Install-Supermetrics($Ctx) {
    $smDict = Load-Json "supermetrics.json"
    $smZip = New-SmZip -SmDict $smDict -Marker $Ctx.Marker -OwnerId $Ctx.OwnerId
    Import-ContentZip -ZipBytes $smZip -Label "super metrics"
    $smCount = ($smDict.PSObject.Properties.Name).Count
    Write-Ok "Imported $smCount super metric(s)"
}

function Install-Dashboard($Ctx) {
    $hasViewsXml = Test-Path (Join-Path $ContentDir "views_content.xml")
    $dashJson = Load-RawText "dashboard.json"
    $viewsXml = if ($hasViewsXml) { Load-RawText "views_content.xml" } else { "" }
    $dashIds = Get-DashboardIds -DashJson $dashJson -OwnerId $Ctx.OwnerId
    $nViews = if ($hasViewsXml) { 1 } else { 0 }
    $dashZip = New-DashboardZip -ViewsXml $viewsXml -DashJson $dashJson -Marker $Ctx.Marker `
        -OwnerId $Ctx.OwnerId -NViews $nViews -NDashboards 1 -DashboardIds $dashIds
    Import-ContentZip -ZipBytes $dashZip -Label "dashboard + view"
    Write-Ok "Imported $nViews view(s) + 1 dashboard"
}

function Install-SmEnable($Ctx) {
    if ($SkipEnable) {
        Write-Host "  (-SkipEnable set: skipping)"
        return
    }
    $smMeta = Load-Json "sm_metadata.json"
    if ($smMeta -isnot [System.Array]) { $smMeta = @($smMeta) }
    $names = @($smMeta | ForEach-Object { $_.name })
    $smResolveAttempts = 3; $smResolveDelay = 5
    $serverIds = @{}
    for ($attempt = 1; $attempt -le $smResolveAttempts; $attempt++) {
        $serverIds = Get-SupermetricsByName -Names $names
        $missing = @($names | Where-Object { -not $serverIds.ContainsKey($_) })
        if ($missing.Count -eq 0) { break }
        if ($attempt -lt $smResolveAttempts) {
            Write-Host "    [resolve $attempt/$smResolveAttempts] $($missing.Count) SM(s) not queryable yet, waiting ${smResolveDelay}s..."
            Start-Sleep -Seconds $smResolveDelay
        }
    }
    foreach ($sm in $smMeta) {
        $smName = $sm.name
        $smId = $serverIds[$smName]
        if (-not $smId) {
            $warn = "Could not resolve ID for '$smName' -- skipping enable"
            Write-Warn $warn
            $Ctx.Warnings.Add($warn)
            continue
        }
        try {
            Enable-SupermetricOnDefaultPolicy -SmId $smId -SmName $smName -ResourceKinds $sm.resourceKinds
            Write-Ok "Enabled: $smName"
        } catch {
            $warn = $_.ToString()
            Write-Warn $warn
            $Ctx.Warnings.Add($warn)
        }
    }
}

function Install-CustomGroups($Ctx) {
    $cgData = Load-Json "customgroup.json"
    if ($cgData -isnot [System.Array]) { $cgData = @($cgData) }
    foreach ($cg in $cgData) {
        $cgName = $cg.resourceKey.name
        Upsert-CustomGroup -Payload $cg
        Write-Ok "Upserted: $cgName"
    }
}

# ---------------------------------------------------------------------------
# Per-type uninstall functions (called by the registry loop)
# ---------------------------------------------------------------------------

function Uninstall-Dashboards($Ctx) {
    $names  = $Ctx.Names
    $allDash = Get-AllDashboards
    $dashByName = @{}
    foreach ($d in $allDash) {
        if ($d.name -and $d.id) { $dashByName[$d.name] = $d.id }
    }
    $toDelete = [System.Collections.Generic.List[object]]::new()
    foreach ($name in $names) {
        if ($dashByName.ContainsKey($name)) {
            $toDelete.Add(@{ id = $dashByName[$name]; name = $name })
        } else {
            Write-Warn "Dashboard not found (already removed?): $name"
            $Ctx.Warnings.Add("Dashboard not found: $name")
        }
    }
    if ($toDelete.Count -gt 0) {
        try {
            Remove-Dashboards -Dashboards $toDelete
            foreach ($d in $toDelete) { Write-Ok "Deleted: $($d.name)" }
        } catch {
            $warn = "Dashboard batch delete failed: $_"
            Write-Warn $warn
            $Ctx.Warnings.Add($warn)
        }
    }
}

function Uninstall-Views($Ctx) {
    $names = $Ctx.Names
    $allViews = Get-AllViews
    $viewByName = @{}
    foreach ($v in $allViews) {
        if ($v.name -and $v.id) { $viewByName[$v.name] = $v.id }
    }
    foreach ($name in $names) {
        $viewId = $viewByName[$name]
        if (-not $viewId) {
            Write-Warn "View not found (already removed?): $name"
            $Ctx.Warnings.Add("View not found: $name")
            continue
        }
        try {
            Remove-View -ViewId $viewId
            Write-Ok "Deleted: $name"
        } catch {
            $warn = "View delete failed for '$name': $_"
            Write-Warn $warn
            $Ctx.Warnings.Add($warn)
        }
    }
}

function Uninstall-Supermetrics($Ctx) {
    $names = $Ctx.Names
    $smIds = Get-SupermetricsByName -Names $names
    foreach ($name in $names) {
        $smId = $smIds[$name]
        if (-not $smId) {
            Write-Warn "Super metric not found (already removed?): $name"
            $Ctx.Warnings.Add("Super metric not found: $name")
            continue
        }
        $sc = Remove-Supermetric -SmId $smId
        if ($sc -eq 200 -or $sc -eq 204) {
            Write-Ok "Deleted: $name"
        } elseif ($sc -eq 409) {
            $warn = "Skipped: $name (referenced by other content; use -Force to override)"
            Write-Warn $warn
            $Ctx.Warnings.Add($warn)
        } else {
            $warn = "Super metric delete returned HTTP $sc for '$name'"
            Write-Warn $warn
            $Ctx.Warnings.Add($warn)
        }
    }
}

function Uninstall-CustomGroups($Ctx) {
    $names = $Ctx.Names
    $cgIds = Find-CustomGroupIds -Names $names
    foreach ($name in $names) {
        $cgId = $cgIds[$name]
        if (-not $cgId) {
            Write-Warn "Custom group not found (already removed?): $name"
            $Ctx.Warnings.Add("Custom group not found: $name")
            continue
        }
        $sc = Remove-CustomGroup -GroupId $cgId
        if ($sc -eq 200 -or $sc -eq 204) {
            Write-Ok "Deleted: $name"
        } else {
            $warn = "Custom group delete returned HTTP $sc for '$name'"
            Write-Warn $warn
            $Ctx.Warnings.Add($warn)
        }
    }
}

# ---------------------------------------------------------------------------
# Install flow (registry-driven)
# ---------------------------------------------------------------------------
function Invoke-Install {
    # Determine which registry entries are active for this bundle
    $active = @($script:ContentRegistry | Where-Object {
        $_.InstallFn -ne $null -and $_.InstallFile -ne $null -and
        (Test-Path (Join-Path $ContentDir $_.InstallFile))
    } | Sort-Object { $_.InstallOrder })

    $TOTAL = 3 + $active.Count   # auth + marker + owner + content steps
    $step = 0

    Write-Host ""
    Write-Host "Installing $PackageName onto $($script:OpsHost)..."

    $step++
    Write-Step $step $TOTAL "Authenticating as $($script:User)@$($script:OpsHost) (auth: $($script:AuthSource)) ..."
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

    $warnings = [System.Collections.Generic.List[string]]::new()
    $ctx = @{
        Marker  = $marker
        OwnerId = $ownerId
        Warnings = $warnings
    }

    foreach ($entry in $active) {
        $step++
        Write-Step $step $TOTAL $entry.InstallLabel
        & $entry.InstallFn $ctx
    }

    Write-Host ""
    if ($warnings.Count -gt 0) {
        Write-Host "Done with $($warnings.Count) warning(s):"
        foreach ($w in $warnings) { Write-Host "  WARN  $w" }
        $enableWarns = @($warnings | Where-Object { $_ -like "*enable*" -or $_ -like "*resolve*" })
        if ($enableWarns.Count -gt 0) {
            Write-Host "Content was imported but one or more super metrics could not be enabled."
        }
        exit 2
    } else {
        Write-Host "Done. All content installed successfully."
    }
}

# ---------------------------------------------------------------------------
# Uninstall flow (registry-driven)
# ---------------------------------------------------------------------------
function Invoke-Uninstall {
    # Determine which registry entries are active for uninstall
    $activeUninstall = @($script:ContentRegistry | Where-Object {
        $_.UninstallFn -ne $null -and $_.UninstallOrder -ne $null -and
        (@($ContentManifest.($_.ContentType) | Where-Object { $_ }).Count -gt 0)
    } | Sort-Object { $_.UninstallOrder })

    $needUi    = ($activeUninstall | Where-Object { $_.NeedsUi }).Count -gt 0
    $needSuite = ($activeUninstall | Where-Object { -not $_.NeedsUi }).Count -gt 0

    $TOTAL = 1 + $activeUninstall.Count
    if ($needUi) { $TOTAL += 2 }   # ui_auth + ui_logout
    $step = 0

    Write-Host ""
    Write-Host "Uninstalling $PackageName from $($script:OpsHost)..."
    if ($Force) { Write-Host "(-Force: skipping dependency checks)" }
    Write-Host "Content to remove:"
    foreach ($entry in $activeUninstall) {
        $names = @($ContentManifest.($entry.ContentType) | Where-Object { $_ })
        if ($names.Count -gt 0) {
            Write-Host "  $($entry.ContentType.Substring(0,1).ToUpper() + $entry.ContentType.Substring(1)) ($($names.Count)): $($names -join ', ')"
        }
    }
    if ($activeUninstall.Count -eq 0) {
        Write-Host "  (nothing to remove -- bundle contains no content)"
        exit 0
    }

    $warnings = [System.Collections.Generic.List[string]]::new()

    $step++
    Write-Step $step $TOTAL "Authenticating as $($script:User)@$($script:OpsHost) (auth: $($script:AuthSource)) ..."
    if ($needSuite) { Authenticate }
    Write-Ok "Authenticated"

    if ($needUi) {
        $step++
        Write-Step $step $TOTAL "Starting UI session (for dashboard/view delete)..."
        Start-UISession
        Write-Ok "UI session established"
    }

    $ctx = @{
        Warnings = $warnings
        Force    = $Force
        Names    = @()
    }

    foreach ($entry in $activeUninstall) {
        $names = @($ContentManifest.($entry.ContentType) | Where-Object { $_ })
        if ($names.Count -eq 0) { continue }
        $step++
        $label = $entry.UninstallLabel -replace '\.\.\.', " ($($names.Count))..."
        Write-Step $step $TOTAL $label
        $ctx.Names = $names
        & $entry.UninstallFn $ctx
    }

    if ($needUi) {
        $step++
        Write-Step $step $TOTAL "Closing UI session..."
        Stop-UISession
        Write-Ok "UI session closed"
    }

    Write-Host ""
    if ($warnings.Count -gt 0) {
        $notFound     = @($warnings | Where-Object { $_ -like "*not found*" })
        $realFailures = @($warnings | Where-Object { $_ -notlike "*not found*" })
        if ($realFailures.Count -gt 0) {
            Write-Host "Done with errors ($($realFailures.Count) delete failure(s)):"
            foreach ($w in $realFailures) { Write-Host "  WARN  $w" }
            if ($notFound.Count -gt 0) {
                Write-Host "  ($($notFound.Count) item(s) were already absent)"
            }
            exit 2
        } else {
            Write-Host "Done. All targeted content was already absent ($($notFound.Count) item(s) not found)."
        }
    } else {
        Write-Host "Done. All content removed successfully."
    }
}

# ---------------------------------------------------------------------------
# Entry point: resolve credentials then fork on mode
# ---------------------------------------------------------------------------
$modeLabel = if ($Uninstall) { "uninstaller" } else { "installer" }
Get-Credentials -Mode $modeLabel

$script:BaseUrl = "https://$($script:OpsHost)/suite-api"

if ($Uninstall) {
    Invoke-Uninstall
} else {
    Invoke-Install
}

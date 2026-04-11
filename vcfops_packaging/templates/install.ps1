<#
.SYNOPSIS
    VCF Operations content installer/uninstaller.

.DESCRIPTION
    Installs or uninstalls one or more content bundles found in the bundles\
    subdirectory (or a legacy top-level content\ directory).  When multiple
    bundles are present, an interactive checklist is shown so the operator can
    select which bundles to install or uninstall.

    Run without -Uninstall (or with -Install) to install content.
    Run with -Uninstall to remove all content these bundles installed.

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
    Uninstall mode: delete all content in selected bundles from the instance.
    Note: Uninstall requires the 'admin' account for dashboard/view cleanup.

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

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

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

function Load-JsonFile($Path) {
    if (-not (Test-Path $Path)) { return $null }
    return Get-Content -Raw $Path | ConvertFrom-Json
}

function Load-RawTextFile($Path) {
    if (-not (Test-Path $Path)) { return $null }
    return [System.IO.File]::ReadAllText($Path)
}

# ---------------------------------------------------------------------------
# Bundle discovery and selection
# ---------------------------------------------------------------------------
function Get-Bundles {
    <#
    .SYNOPSIS
        Discover bundle entries from the bundles\ subtree.

    Returns a list of hashtables: {Slug, Dir, Manifest}.

    Fallback: if no bundles\ subtree exists but a legacy top-level bundle.json
    + content\ exist, synthesise a single in-memory entry for backwards
    compatibility (one-release transition; removable later).
    #>
    $entries = [System.Collections.Generic.List[hashtable]]::new()
    $bundlesRoot = Join-Path $ScriptDir "bundles"

    if (Test-Path $bundlesRoot) {
        $bundleJsonFiles = Get-ChildItem -Path $bundlesRoot -Filter "bundle.json" -Recurse -ErrorAction SilentlyContinue |
            Sort-Object FullName
        foreach ($f in $bundleJsonFiles) {
            # Only direct children: bundles/<slug>/bundle.json
            if ($f.Directory.Parent.FullName -ne $bundlesRoot) { continue }
            $slug = $f.Directory.Name
            try {
                $manifest = Get-Content -Raw $f.FullName | ConvertFrom-Json
            } catch {
                Write-Host "  WARN  Could not parse $($f.FullName): $_ -- skipping"
                continue
            }
            $entries.Add(@{ Slug = $slug; Dir = $f.Directory.FullName; Manifest = $manifest })
        }
    }

    if ($entries.Count -eq 0) {
        # Legacy fallback: flat content\ layout with top-level bundle.json
        $legacyManifest = Join-Path $ScriptDir "bundle.json"
        $legacyContent  = Join-Path $ScriptDir "content"
        if ((Test-Path $legacyManifest) -and (Test-Path $legacyContent)) {
            try   { $manifest = Get-Content -Raw $legacyManifest | ConvertFrom-Json }
            catch { $manifest = [PSCustomObject]@{ name = "bundle"; description = ""; content = [PSCustomObject]@{} } }
            $entries.Add(@{ Slug = $manifest.name; Dir = $ScriptDir; Manifest = $manifest })
        } elseif (Test-Path $legacyContent) {
            $manifest = [PSCustomObject]@{
                name        = "bundle"
                description = ""
                content     = [PSCustomObject]@{}
            }
            $entries.Add(@{ Slug = "bundle"; Dir = $ScriptDir; Manifest = $manifest })
        }
    }

    return $entries
}

function Select-Bundles {
    param(
        [System.Collections.Generic.List[hashtable]]$Bundles,
        [string]$Mode = "install"
    )

    if ($Bundles.Count -eq 1) {
        $b = $Bundles[0]
        $bname = if ($b.Manifest.name) { $b.Manifest.name } else { $b.Slug }
        $bdesc = if ($b.Manifest.description) { " -- $($b.Manifest.description)" } else { "" }
        Write-Host ""
        Write-Host "  Bundle: $bname$bdesc"
        return $Bundles
    }

    Write-Host ""
    Write-Host "Select bundles to $Mode (all selected by default):"
    Write-Host "  Toggle: enter comma-separated numbers (e.g. '2' or '1,3')"
    Write-Host "  Commands: 'all' to select all, 'none' to deselect all, Enter to proceed"

    $selected = @($true) * $Bundles.Count
    for ($i = 0; $i -lt $Bundles.Count; $i++) { $selected[$i] = $true }

    while ($true) {
        Write-Host ""
        for ($i = 0; $i -lt $Bundles.Count; $i++) {
            $b     = $Bundles[$i]
            $mark  = if ($selected[$i]) { "*" } else { " " }
            $bname = if ($b.Manifest.name) { $b.Manifest.name } else { $b.Slug }
            $bdesc = if ($b.Manifest.description) { " -- $($b.Manifest.description)" } else { "" }
            $nItems = 0
            if ($b.Manifest.content) {
                foreach ($prop in $b.Manifest.content.PSObject.Properties) {
                    $items = $prop.Value.items
                    if ($items) { $nItems += @($items).Count }
                }
            }
            $detail = if ($nItems -gt 0) { "($nItems items)" } else { "(no items)" }
            Write-Host "  [$mark] $($i+1). $bname $detail$bdesc"
        }

        $raw = Read-Host "`nToggle [1..N / all / none / Enter to proceed]"
        $raw = $raw.Trim().ToLower()

        if ($raw -eq "") { break }
        elseif ($raw -eq "all")  { for ($i = 0; $i -lt $Bundles.Count; $i++) { $selected[$i] = $true  } }
        elseif ($raw -eq "none") { for ($i = 0; $i -lt $Bundles.Count; $i++) { $selected[$i] = $false } }
        else {
            foreach ($tok in ($raw -split ",")) {
                $tok = $tok.Trim()
                if ($tok -match '^\d+$') {
                    $idx = [int]$tok - 1
                    if ($idx -ge 0 -and $idx -lt $Bundles.Count) {
                        $selected[$idx] = -not $selected[$idx]
                    } else {
                        Write-Host "  (ignoring out-of-range index $tok)"
                    }
                } elseif ($tok -ne "") {
                    Write-Host "  (unrecognised token '$tok' -- ignored)"
                }
            }
        }
    }

    $chosen = [System.Collections.Generic.List[hashtable]]::new()
    for ($i = 0; $i -lt $Bundles.Count; $i++) {
        if ($selected[$i]) { $chosen.Add($Bundles[$i]) }
    }
    if ($chosen.Count -eq 0) {
        Write-Host "  No bundles selected. Exiting."
        exit 0
    }
    return $chosen
}

function Show-SelectionSummary {
    param($SelectedBundles, [string]$Mode)
    Write-Host ""
    Write-Host "Will $Mode $($SelectedBundles.Count) bundle(s):"
    foreach ($b in $SelectedBundles) {
        $bname = if ($b.Manifest.name) { $b.Manifest.name } else { $b.Slug }
        $bdesc = if ($b.Manifest.description) { " -- $($b.Manifest.description)" } else { "" }
        $parts = @()
        if ($b.Manifest.content) {
            foreach ($prop in $b.Manifest.content.PSObject.Properties) {
                $items = $prop.Value.items
                $count = if ($items) { @($items).Count } else { 0 }
                if ($count -gt 0) { $parts += "$count $($prop.Name)" }
            }
        }
        $summary = if ($parts.Count -gt 0) { $parts -join ", " } else { "no items" }
        Write-Host "  - $bname$bdesc"
        Write-Host "    Contents: $summary"
    }
}

# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------
function Test-BundleHasKey {
    param($Bundle, [string]$ManifestKey)
    if (-not $ManifestKey) { return $false }
    $content = $Bundle.Manifest.content
    if (-not $content) { return $false }
    $section = $content.$ManifestKey
    if (-not $section) { return $false }
    $rel = $section.file
    if (-not $rel) { return $false }
    return Test-Path (Join-Path $Bundle.Dir $rel)
}

function Get-BundleUninstallNames {
    param($Bundle, [string]$ContentType)
    $content = $Bundle.Manifest.content
    if (-not $content) { return @() }
    $section = $content.$ContentType
    if (-not $section -or -not $section.items) { return @() }
    return @($section.items | Where-Object { $_.name } | ForEach-Object { $_.name })
}

# ---------------------------------------------------------------------------
# Interactive credential prompts
# ---------------------------------------------------------------------------
function Get-Credentials {
    param([string]$Mode = "installer")
    Write-Host ""
    Write-Host "VCF Content Factory -- $Mode"
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
            $handler.ServerCertificateCustomValidationCallback = [System.Net.Http.HttpClientHandler]::DangerousAcceptAnyServerCertificateValidator
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

function Import-PolicyZip {
    param([byte[]]$ZipBytes)
    # POST /api/policies/import?forceImport=true as multipart/form-data.
    # The session-level Content-Type header must NOT be application/json for
    # multipart uploads — we use Invoke-RestMethod with -Form which sets the
    # correct boundary automatically.
    $uri = "$script:BaseUrl/api/policies/import?forceImport=true"
    Add-Type -AssemblyName System.Net.Http
    $content = New-Object System.Net.Http.MultipartFormDataContent
    $byteArray = New-Object System.Net.Http.ByteArrayContent(,$ZipBytes)
    $byteArray.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse("application/zip")
    $content.Add($byteArray, "policy", "exportedPolicies.zip")

    $handler = New-Object System.Net.Http.HttpClientHandler
    if ($SkipSslVerify) {
        $handler.ServerCertificateCustomValidationCallback = { $true }
    }
    $httpClient = New-Object System.Net.Http.HttpClient($handler)
    $httpClient.DefaultRequestHeaders.Add("Authorization", "vRealizeOpsToken $script:Token")
    $httpClient.DefaultRequestHeaders.Add("Accept", "application/json")

    try {
        $response = $httpClient.PostAsync($uri, $content).GetAwaiter().GetResult()
        $statusCode = [int]$response.StatusCode
        if ($statusCode -notin @(200, 201, 204)) {
            $body = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
            throw "Policy import failed ($statusCode): $body"
        }
    } finally {
        $httpClient.Dispose()
        $handler.Dispose()
    }
}

function Enable-SupermetricOnDefaultPolicy {
    param($SmId, $SmName, $ResourceKinds, $PolicyId)

    # Step 1: resource-kind assignment via PUT /internal/supermetrics/assign
    # (without policyIds — that variant does not enable content-zip SMs).
    # This wires the SM to the adapter/resource kind so it appears in views.
    $assignBody = @{
        superMetricId    = $SmId
        resourceKindKeys = @($ResourceKinds | ForEach-Object {
            @{
                adapterKind  = if ($_.adapterKindKey) { $_.adapterKindKey } else { $_.adapterKind }
                resourceKind = if ($_.resourceKindKey) { $_.resourceKindKey } else { $_.resourceKind }
            }
        })
    }
    $assignUri = "$script:BaseUrl/internal/supermetrics/assign"
    $assignHeaders = @{
        "Accept"                    = "application/json"
        "Content-Type"              = "application/json"
        "Authorization"             = "vRealizeOpsToken $script:Token"
        "X-Ops-API-use-unsupported" = "true"
    }
    $assignParams = @{
        Method  = "PUT"
        Uri     = $assignUri
        Headers = $assignHeaders
        Body    = ($assignBody | ConvertTo-Json -Depth 10 -Compress)
    }
    if ($SkipSslVerify -and $PSVersionTable.PSVersion.Major -ge 6) { $assignParams["SkipCertificateCheck"] = $true }
    try {
        Invoke-RestMethod @assignParams | Out-Null
    } catch {
        throw "Resource-kind assignment for SM '$SmName' failed: $_"
    }

    # Step 2: policy enablement via export -> edit XML -> import.
    # Export the Default Policy ZIP, remove any stale entry for this SM from
    # ALL <SuperMetrics> blocks (makes the method idempotent/self-healing),
    # then inject a fresh <SuperMetric enabled="true" id="..."/> under each
    # matching <SuperMetrics adapterKind="X" resourceKind="Y"> block, and
    # re-import the modified ZIP.
    $policyXml = Export-DefaultPolicyXml -PolicyId $PolicyId

    [xml]$doc = $policyXml

    # Purge stale entries for this SM from all SuperMetrics blocks.
    $staleNodes = @($doc.GetElementsByTagName("SuperMetric") |
        Where-Object { $_.GetAttribute("id") -eq $SmId })
    foreach ($node in $staleNodes) {
        $node.ParentNode.RemoveChild($node) | Out-Null
    }

    # Locate or create the correct <SuperMetrics adapterKind resourceKind> block
    # for each resource kind and inject a fresh enabled entry.
    $pkgSettings = $doc.GetElementsByTagName("PackageSettings") | Select-Object -First 1
    if (-not $pkgSettings) {
        $policyElem = $doc.GetElementsByTagName("Policy") | Select-Object -First 1
        if (-not $policyElem) { throw "Policy XML has no <Policy> element — cannot inject SM '$SmName'" }
        $pkgSettings = $doc.CreateElement("PackageSettings")
        $policyElem.AppendChild($pkgSettings) | Out-Null
    }

    foreach ($rk in $ResourceKinds) {
        $ak = if ($rk.adapterKindKey) { $rk.adapterKindKey } else { $rk.adapterKind }
        $rkKey = if ($rk.resourceKindKey) { $rk.resourceKindKey } else { $rk.resourceKind }

        $smBlock = $null
        foreach ($candidate in @($pkgSettings.GetElementsByTagName("SuperMetrics"))) {
            if ($candidate.GetAttribute("adapterKind") -eq $ak -and
                $candidate.GetAttribute("resourceKind") -eq $rkKey) {
                $smBlock = $candidate
                break
            }
        }
        if (-not $smBlock) {
            $smBlock = $doc.CreateElement("SuperMetrics")
            $smBlock.SetAttribute("adapterKind", $ak)
            $smBlock.SetAttribute("resourceKind", $rkKey)
            $pkgSettings.AppendChild($smBlock) | Out-Null
        }

        $newEntry = $doc.CreateElement("SuperMetric")
        $newEntry.SetAttribute("enabled", "true")
        $newEntry.SetAttribute("id", $SmId)
        $smBlock.AppendChild($newEntry) | Out-Null
    }

    # Rebuild the policy ZIP with the edited XML and re-import.
    $editedXml = $doc.OuterXml
    if (-not $editedXml.StartsWith("<?xml")) {
        $editedXml = '<?xml version="1.0" encoding="UTF-8"?>' + "`n" + $editedXml
    }
    $editedXmlBytes = [System.Text.Encoding]::UTF8.GetBytes($editedXml)

    # Re-export raw ZIP to get the original filename (and any other entries).
    $tmpZip = [System.IO.Path]::GetTempFileName() + ".zip"
    try {
        $exportUri = "$script:BaseUrl/api/policies/export?id=$([uri]::EscapeDataString($PolicyId))"
        $exportHeaders = @{
            "Authorization" = "vRealizeOpsToken $script:Token"
            "Accept"        = "application/zip"
        }
        $exportParams = @{
            Method  = "GET"
            Uri     = $exportUri
            Headers = $exportHeaders
        }
        if ($SkipSslVerify -and $PSVersionTable.PSVersion.Major -ge 6) { $exportParams["SkipCertificateCheck"] = $true }
        if ($PSVersionTable.PSVersion.Major -ge 6) {
            Invoke-WebRequest @exportParams -OutFile $tmpZip | Out-Null
        } else {
            Invoke-WebRequest @exportParams -OutFile $tmpZip -UseBasicParsing | Out-Null
        }

        # Read original ZIP to discover the XML filename and other entries.
        $ms = New-Object System.IO.MemoryStream
        $origZip = [System.IO.Compression.ZipFile]::OpenRead($tmpZip)
        try {
            $xmlEntryName = $null
            $otherEntries = @{}
            foreach ($entry in $origZip.Entries) {
                if ($entry.Name -like "*.xml") {
                    $xmlEntryName = $entry.FullName
                } else {
                    $reader = New-Object System.IO.BinaryReader($entry.Open())
                    try { $otherEntries[$entry.FullName] = $reader.ReadBytes([int]$entry.Length) }
                    finally { $reader.Dispose() }
                }
            }
            if (-not $xmlEntryName) { throw "Policy export ZIP contained no XML file" }
        } finally { $origZip.Dispose() }

        # Build new ZIP with edited XML.
        $outZip = New-Object System.IO.Compression.ZipArchive($ms, [System.IO.Compression.ZipArchiveMode]::Create, $true)
        try {
            $xmlEntry = $outZip.CreateEntry($xmlEntryName, [System.IO.Compression.CompressionLevel]::Optimal)
            $xmlStream = $xmlEntry.Open()
            $xmlStream.Write($editedXmlBytes, 0, $editedXmlBytes.Length)
            $xmlStream.Dispose()
            foreach ($name in $otherEntries.Keys) {
                $e = $outZip.CreateEntry($name, [System.IO.Compression.CompressionLevel]::Optimal)
                $s = $e.Open()
                $s.Write($otherEntries[$name], 0, $otherEntries[$name].Length)
                $s.Dispose()
            }
        } finally { $outZip.Dispose() }

        Import-PolicyZip -ZipBytes $ms.ToArray()
    } finally {
        $ms.Dispose()
        if (Test-Path $tmpZip) { Remove-Item $tmpZip -Force -ErrorAction SilentlyContinue }
    }
}

function Export-DefaultPolicyXml {
    param([string]$PolicyId)
    $uri = "$script:BaseUrl/api/policies/export?id=$([uri]::EscapeDataString($PolicyId))"
    $headers = @{
        "Authorization" = "vRealizeOpsToken $script:Token"
        "Accept"        = "application/zip"
    }
    $params = @{
        Method  = "GET"
        Uri     = $uri
        Headers = $headers
    }
    if ($SkipSslVerify -and $PSVersionTable.PSVersion.Major -ge 6) { $params["SkipCertificateCheck"] = $true }
    $tmpZip = [System.IO.Path]::GetTempFileName() + ".zip"
    try {
        if ($PSVersionTable.PSVersion.Major -ge 6) {
            Invoke-WebRequest @params -OutFile $tmpZip | Out-Null
        } else {
            # PS 5.1: Invoke-WebRequest needs custom cert callback
            Invoke-WebRequest @params -OutFile $tmpZip -UseBasicParsing | Out-Null
        }
        $zip = [System.IO.Compression.ZipFile]::OpenRead($tmpZip)
        try {
            foreach ($entry in $zip.Entries) {
                if ($entry.Name -like "*.xml") {
                    $reader = New-Object System.IO.StreamReader($entry.Open())
                    try { return $reader.ReadToEnd() }
                    finally { $reader.Dispose() }
                }
            }
            throw "Policy export ZIP contained no XML file"
        } finally { $zip.Dispose() }
    } finally {
        if (Test-Path $tmpZip) { Remove-Item $tmpZip -Force -ErrorAction SilentlyContinue }
    }
}

function Test-SupermetricsEnabled {
    param([string]$PolicyXml, [string[]]$SmIds)
    [xml]$doc = $PolicyXml
    $enabledIds = [System.Collections.Generic.HashSet[string]]::new()
    foreach ($node in $doc.GetElementsByTagName("SuperMetric")) {
        if ($node.GetAttribute("enabled").ToLower() -eq "true") {
            [void]$enabledIds.Add($node.GetAttribute("id"))
        }
    }
    $result = @{}
    foreach ($id in $SmIds) {
        $result[$id] = $enabledIds.Contains($id)
    }
    return $result
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
        "configuration.json" = (@{ superMetrics = (@($SmDict.PSObject.Properties.Name).Count); type = "ALL" } | ConvertTo-Json -Compress)
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
        users   = @(@{ userName = $script:User; userId = $OwnerId })
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

function New-ReportsZip {
    param([string]$ReportsXml, [string]$Marker, [string]$OwnerId)
    # Build inner reports.zip containing content.xml
    $innerEntries = @{ "content.xml" = $ReportsXml }
    $innerBytes = New-ZipBytes $innerEntries

    # Count ReportDef elements
    $nReports = ([regex]::Matches($ReportsXml, "<ReportDef ")).Count
    $config = @{ reports = $nReports; type = "CUSTOM" } | ConvertTo-Json -Compress

    $outerEntries = @{
        $Marker              = $OwnerId
        "reports.zip"        = $innerBytes
        "configuration.json" = $config
    }
    return New-ZipBytes $outerEntries
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
        if ($indexResp -and $indexResp.Headers) {
            # $indexResp may be HttpResponseMessage (from catch) whose Headers
            # is HttpResponseHeaders — not indexable with []. Use GetValues().
            $setCookie = $null
            try { $setCookie = $indexResp.Headers.GetValues("Set-Cookie") } catch {}
            if (-not $setCookie) {
                try { $setCookie = $indexResp.Headers["Set-Cookie"] } catch {}
            }
            if ($setCookie -and ("$setCookie" -match "OPS_SESSION=([^;]+)")) {
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
        data   = @(@{ start = 0; limit = 500 })
        type   = "rpc"
        tid    = $tid
    })
    if ($result[0].type -eq "exception") {
        Write-Fail "View list failed: $($result[0].message)"
    }
    $allViews = [System.Collections.Generic.List[object]]::new()
    $grouped = $result[0].result
    # API returns a dict keyed by view type (LIST, IMAGE, etc.),
    # each value is a dict keyed by subject name (HostSystem, etc.),
    # each subject value is a list of view objects.
    if ($grouped -is [PSCustomObject]) {
        foreach ($typeProp in $grouped.PSObject.Properties) {
            $subjectMap = $typeProp.Value
            if ($subjectMap -is [PSCustomObject]) {
                foreach ($subjectProp in $subjectMap.PSObject.Properties) {
                    $viewList = $subjectProp.Value
                    if ($viewList -is [System.Array]) {
                        foreach ($v in $viewList) { $allViews.Add($v) }
                    }
                }
            }
        }
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
#   ContentType     string   key in manifest content map (for uninstall names)
#   ManifestKey     string   key in manifest.content (for install detection; $null = uninstall-only)
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
        ManifestKey    = "supermetrics"
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
        ManifestKey    = "dashboards"
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
        ManifestKey    = "supermetrics"
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
        ManifestKey    = "customgroups"
        InstallLabel   = "Upserting custom group(s)..."
        InstallFn      = "Install-CustomGroups"
        InstallOrder   = 4
        UninstallLabel = "Deleting custom group(s)..."
        UninstallFn    = "Uninstall-CustomGroups"
        UninstallOrder = 50
        NeedsUi        = $false
    },
    @{
        ContentType    = "reports"
        ManifestKey    = "reports"
        InstallLabel   = "Importing report definition(s)..."
        InstallFn      = "Install-Reports"
        InstallOrder   = 5
        UninstallLabel = $null
        UninstallFn    = $null
        UninstallOrder = $null
        NeedsUi        = $false
    },
    @{
        ContentType    = "symptoms"
        ManifestKey    = "symptoms"
        InstallLabel   = "Upserting symptom definition(s)..."
        InstallFn      = "Install-Symptoms"
        InstallOrder   = 6
        UninstallLabel = "Deleting symptom definition(s)..."
        UninstallFn    = "Uninstall-Symptoms"
        UninstallOrder = 55
        NeedsUi        = $false
    },
    @{
        ContentType    = "alerts"
        ManifestKey    = "alerts"
        InstallLabel   = "Upserting alert definition(s)..."
        InstallFn      = "Install-Alerts"
        InstallOrder   = 7
        UninstallLabel = "Deleting alert definition(s)..."
        UninstallFn    = "Uninstall-Alerts"
        UninstallOrder = 35
        NeedsUi        = $false
    },
    # Uninstall-only entries for dashboards and views
    @{
        ContentType    = "dashboards"
        ManifestKey    = $null
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
        ManifestKey    = $null
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
    $smFile = Join-Path $Ctx.BundleDir $Ctx.Manifest.content.supermetrics.file
    $smDict = Load-JsonFile $smFile
    $smZip = New-SmZip -SmDict $smDict -Marker $Ctx.Marker -OwnerId $Ctx.OwnerId
    Import-ContentZip -ZipBytes $smZip -Label "super metrics"
    $smCount = @($smDict.PSObject.Properties.Name).Count
    Write-Ok "Imported $smCount super metric(s)"
}

function Install-Dashboard($Ctx) {
    $dashFile = Join-Path $Ctx.BundleDir $Ctx.Manifest.content.dashboards.file
    $dashJson = Load-RawTextFile $dashFile

    $viewsXml = ""
    if ($Ctx.Manifest.content.views) {
        $viewsFile = Join-Path $Ctx.BundleDir $Ctx.Manifest.content.views.file
        if (Test-Path $viewsFile) { $viewsXml = Load-RawTextFile $viewsFile }
    }

    $dashIds = Get-DashboardIds -DashJson $dashJson -OwnerId $Ctx.OwnerId
    $nViews = if ($viewsXml) { 1 } else { 0 }
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
    $smFile = Join-Path $Ctx.BundleDir $Ctx.Manifest.content.supermetrics.file
    $smDict = Load-JsonFile $smFile
    # smDict is keyed by UUID: {uuid: {name, formula, description, unitId, resourceKinds}}
    $smMeta = @($smDict.PSObject.Properties | ForEach-Object { $_.Value })
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
    # Build unverified map: {server_id -> @{Name; ResourceKinds}}
    $unverified = @{}
    foreach ($sm in $smMeta) {
        $smName = $sm.name
        $smId = $serverIds[$smName]
        if (-not $smId) {
            $warn = "Could not resolve ID for '$smName' -- skipping enable"
            Write-Warn $warn
            $Ctx.Warnings.Add($warn)
            continue
        }
        $unverified[$smId] = @{ Name = $smName; ResourceKinds = $sm.resourceKinds }
    }

    if ($unverified.Count -eq 0) { return }

    $smEnableAttempts = 3
    $smEnableVerifyDelay = 2
    $policyId = Get-DefaultPolicyId

    for ($attempt = 1; $attempt -le $smEnableAttempts; $attempt++) {
        # Assign all unverified
        $assignErrors = @{}
        foreach ($smId in @($unverified.Keys)) {
            $entry = $unverified[$smId]
            try {
                Enable-SupermetricOnDefaultPolicy -SmId $smId -SmName $entry.Name `
                    -ResourceKinds $entry.ResourceKinds -PolicyId $policyId
            } catch {
                $assignErrors[$smId] = $_.ToString()
            }
        }

        Start-Sleep -Seconds $smEnableVerifyDelay

        # Export + verify
        $verifyFailed = $false
        try {
            $policyXml = Export-DefaultPolicyXml -PolicyId $policyId
            $status = Test-SupermetricsEnabled -PolicyXml $policyXml -SmIds @($unverified.Keys)
        } catch {
            Write-Warn "Policy export failed on attempt ${attempt}: $_"
            if ($attempt -lt $smEnableAttempts) { continue }
            foreach ($smId in @($unverified.Keys)) {
                $warn = "Enable FAILED for '$($unverified[$smId].Name)': could not verify"
                Write-Warn $warn
                $Ctx.Warnings.Add($warn)
            }
            $verifyFailed = $true
            break
        }

        # Partition results
        $stillPending = @{}
        foreach ($smId in @($unverified.Keys)) {
            $entry = $unverified[$smId]
            if ($assignErrors.ContainsKey($smId)) {
                $warn = $assignErrors[$smId]
                Write-Warn $warn
                $Ctx.Warnings.Add($warn)
            } elseif ($status[$smId]) {
                Write-Ok "Enabled: $($entry.Name)"
            } else {
                if ($attempt -lt $smEnableAttempts) {
                    $stillPending[$smId] = $entry
                } else {
                    $warn = "Enable FAILED for '$($entry.Name)': assign returned 200 but SM not in Default Policy after $smEnableAttempts attempts"
                    Write-Warn $warn
                    $Ctx.Warnings.Add($warn)
                }
            }
        }

        $unverified = $stillPending
        if ($unverified.Count -eq 0) { break }
        Write-Host "    [enable-verify $attempt/$smEnableAttempts] $($unverified.Count) SM(s) not verified, retrying..."
    }
}

function Install-CustomGroups($Ctx) {
    $cgFile = Join-Path $Ctx.BundleDir $Ctx.Manifest.content.customgroups.file
    $cgData = Load-JsonFile $cgFile
    if ($cgData -isnot [System.Array]) { $cgData = @($cgData) }
    foreach ($cg in $cgData) {
        $cgName = $cg.resourceKey.name
        Upsert-CustomGroup -Payload $cg
        Write-Ok "Upserted: $cgName"
    }
}

function Install-Reports($Ctx) {
    $reportsFile = Join-Path $Ctx.BundleDir $Ctx.Manifest.content.reports.file
    $reportsXml = Load-RawTextFile $reportsFile
    $reportsZip = New-ReportsZip -ReportsXml $reportsXml -Marker $Ctx.Marker -OwnerId $Ctx.OwnerId
    Import-ContentZip -ZipBytes $reportsZip -Label "reports"
    $nReports = ([regex]::Matches($reportsXml, "<ReportDef ")).Count
    Write-Ok "Imported $nReports report definition(s)"
    Write-Warn "Note: report definitions cannot be removed via the API. To uninstall, use the Ops UI: Administration > Content > Reports."
    $Ctx.Warnings.Add("Report definitions must be removed manually via the Ops UI (Administration > Content > Reports).")
}

function Install-Symptoms($Ctx) {
    $symFile = Join-Path $Ctx.BundleDir $Ctx.Manifest.content.symptoms.file
    $symptoms = Load-JsonFile $symFile
    foreach ($payload in $symptoms) {
        $name = $payload.name
        # Find existing by name
        $existing = $null
        $page = 0; $pageSize = 1000
        :outer do {
            $r = Invoke-Api -Method GET -Path "/api/symptomdefinitions" -Query @{ page = "$page"; pageSize = "$pageSize" }
            foreach ($sd in $r.symptomDefinitions) {
                if ($sd.name -eq $name) { $existing = $sd; break outer }
            }
            $total = if ($r.pageInfo) { $r.pageInfo.totalCount } else { 0 }
            $page++
        } while (($page * $pageSize) -lt $total)

        if ($existing) {
            $payload | Add-Member -NotePropertyName "id" -NotePropertyValue $existing.id -Force
            $r = Invoke-Api -Method PUT -Path "/api/symptomdefinitions" -Body $payload
            Write-Ok "Updated: $name"
        } else {
            $r = Invoke-Api -Method POST -Path "/api/symptomdefinitions" -Body $payload
            Write-Ok "Created: $name"
        }
    }
}

function Install-Alerts($Ctx) {
    $alertFile = Join-Path $Ctx.BundleDir $Ctx.Manifest.content.alerts.file
    $alerts = Load-JsonFile $alertFile

    # Build symptom name -> id map
    $symptomMap = @{}
    $page = 0; $pageSize = 1000
    do {
        $r = Invoke-Api -Method GET -Path "/api/symptomdefinitions" -Query @{ page = "$page"; pageSize = "$pageSize" }
        foreach ($sd in $r.symptomDefinitions) {
            if ($sd.name -and $sd.id) { $symptomMap[$sd.name] = $sd.id }
        }
        $total = if ($r.pageInfo) { $r.pageInfo.totalCount } else { 0 }
        $page++
    } while (($page * $pageSize) -lt $total)

    foreach ($alertData in $alerts) {
        $name = $alertData.name
        # Build wire format with resolved symptom IDs
        $wire = ConvertTo-AlertWire -AlertData $alertData -SymptomMap $symptomMap
        if (-not $wire) {
            Write-Warn "Alert '$name': could not resolve symptom references"
            $Ctx.Warnings.Add("Alert '$name': symptom resolution failed")
            continue
        }

        # Upsert by name
        $existing = $null
        $page = 0
        :outer2 do {
            $r = Invoke-Api -Method GET -Path "/api/alertdefinitions" -Query @{ page = "$page"; pageSize = "1000" }
            foreach ($ad in $r.alertDefinitions) {
                if ($ad.name -eq $name) { $existing = $ad; break outer2 }
            }
            $total = if ($r.pageInfo) { $r.pageInfo.totalCount } else { 0 }
            $page++
        } while (($page * 1000) -lt $total)

        if ($existing) {
            $wire | Add-Member -NotePropertyName "id" -NotePropertyValue $existing.id -Force
            $r = Invoke-Api -Method PUT -Path "/api/alertdefinitions" -Body $wire
            Write-Ok "Updated: $name"
        } else {
            $r = Invoke-Api -Method POST -Path "/api/alertdefinitions" -Body $wire
            Write-Ok "Created: $name"
        }
    }
}

function ConvertTo-AlertWire {
    param($AlertData, [hashtable]$SymptomMap)
    $ss = $AlertData.symptom_sets
    $topOp = if ($ss.operator) { $ss.operator.ToUpper() } else { "ALL" }
    $wireSets = @()
    foreach ($s in $ss.sets) {
        $definedOn = if ($s.defined_on) { $s.defined_on.ToUpper() } else { "SELF" }
        $op = if ($s.operator) { $s.operator.ToUpper() } else { "ALL" }
        $symptomIds = @()
        foreach ($sym in $s.symptoms) {
            $sid = $SymptomMap[$sym.name]
            if (-not $sid) { return $null }
            $symptomIds += $sid
        }
        $wireSet = @{
            type = "SYMPTOM_SET"
            relation = $definedOn
            symptomSetOperator = if ($op -eq "ALL") { "AND" } else { "OR" }
            symptomDefinitionIds = $symptomIds
        }
        if ($definedOn -ne "SELF" -and $s.threshold_type) {
            $wireSet["aggregation"] = $s.threshold_type
            if ($null -ne $s.threshold_value) { $wireSet["value"] = [double]$s.threshold_value }
        }
        $wireSets += $wireSet
    }
    $baseSS = if ($wireSets.Count -eq 1) { $wireSets[0] }
              else { @{ type = "SYMPTOM_SET_COMPOSITE"; operator = if ($topOp -eq "ALL") { "AND" } else { "OR" }; "symptom-sets" = $wireSets } }
    $state = @{
        severity = if ($AlertData.criticality) { $AlertData.criticality } else { "AUTO" }
        "base-symptom-set" = $baseSS
        impact = @{ impactType = "BADGE"; detail = if ($AlertData.impact_badge) { $AlertData.impact_badge } else { "HEALTH" } }
    }
    return @{
        name = $AlertData.name
        description = if ($AlertData.description) { $AlertData.description } else { "" }
        adapterKindKey = $AlertData.adapter_kind
        resourceKindKey = $AlertData.resource_kind
        waitCycles = if ($AlertData.wait_cycles) { $AlertData.wait_cycles } else { 1 }
        cancelCycles = if ($AlertData.cancel_cycles) { $AlertData.cancel_cycles } else { 1 }
        type = if ($AlertData.type) { $AlertData.type } else { 16 }
        subType = if ($AlertData.sub_type) { $AlertData.sub_type } else { 3 }
        states = @($state)
    }
}

function Uninstall-Symptoms($Ctx) {
    $names = $Ctx.Names
    $symIds = @{}
    $page = 0; $pageSize = 1000
    do {
        $r = Invoke-Api -Method GET -Path "/api/symptomdefinitions" -Query @{ page = "$page"; pageSize = "$pageSize" }
        foreach ($sd in $r.symptomDefinitions) {
            if ($sd.name -and $sd.id -and ($names -contains $sd.name)) { $symIds[$sd.name] = $sd.id }
        }
        $total = if ($r.pageInfo) { $r.pageInfo.totalCount } else { 0 }
        $page++
    } while (($page * $pageSize) -lt $total)
    foreach ($name in $names) {
        $sid = $symIds[$name]
        if (-not $sid) {
            Write-Warn "Symptom not found (already removed?): $name"
            $Ctx.Warnings.Add("Symptom not found: $name")
            continue
        }
        $r = Invoke-Api -Method DELETE -Path "/api/symptomdefinitions/$sid"
        Write-Ok "Deleted: $name"
    }
}

function Uninstall-Alerts($Ctx) {
    $names = $Ctx.Names
    $alertIds = @{}
    $page = 0
    do {
        $r = Invoke-Api -Method GET -Path "/api/alertdefinitions" -Query @{ page = "$page"; pageSize = "1000" }
        foreach ($ad in $r.alertDefinitions) {
            if ($ad.name -and $ad.id -and ($names -contains $ad.name)) { $alertIds[$ad.name] = $ad.id }
        }
        $total = if ($r.pageInfo) { $r.pageInfo.totalCount } else { 0 }
        $page++
    } while (($page * 1000) -lt $total)
    foreach ($name in $names) {
        $aid = $alertIds[$name]
        if (-not $aid) {
            Write-Warn "Alert not found (already removed?): $name"
            $Ctx.Warnings.Add("Alert not found: $name")
            continue
        }
        $r = Invoke-Api -Method DELETE -Path "/api/alertdefinitions/$aid"
        Write-Ok "Deleted: $name"
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
        $vid = if ($v.viewDefinitionKey) { $v.viewDefinitionKey } else { $v.id }
        if ($v.name -and $vid) { $viewByName[$v.name] = $vid }
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
# Per-bundle install / uninstall helpers
# ---------------------------------------------------------------------------

function Invoke-InstallBundle {
    param($Bundle, $GlobalCtx, [ref]$Step, $TotalSteps)
    $manifest = $Bundle.Manifest
    $bname = if ($manifest.name) { $manifest.name } else { $Bundle.Slug }

    $active = @($script:ContentRegistry | Where-Object {
        $_.InstallFn -ne $null -and $_.ManifestKey -ne $null -and
        (Test-BundleHasKey -Bundle $Bundle -ManifestKey $_.ManifestKey)
    } | Sort-Object { $_.InstallOrder })

    $warnings = [System.Collections.Generic.List[string]]::new()
    $ctx = @{
        BundleDir = $Bundle.Dir
        Manifest  = $manifest
        Marker    = $GlobalCtx.Marker
        OwnerId   = $GlobalCtx.OwnerId
        Warnings  = $warnings
        Names     = @()
    }

    foreach ($entry in $active) {
        $Step.Value++
        Write-Step $Step.Value $TotalSteps "[$bname] $($entry.InstallLabel)"
        & $entry.InstallFn $ctx
    }
    return $warnings
}

function Invoke-UninstallBundle {
    param($Bundle, $GlobalCtx, [ref]$Step, $TotalSteps)
    $manifest = $Bundle.Manifest
    $bname = if ($manifest.name) { $manifest.name } else { $Bundle.Slug }

    $active = @($script:ContentRegistry | Where-Object {
        $_.UninstallFn -ne $null -and $_.UninstallOrder -ne $null -and
        ((Get-BundleUninstallNames -Bundle $Bundle -ContentType $_.ContentType).Count -gt 0)
    } | Sort-Object { $_.UninstallOrder })

    $warnings = [System.Collections.Generic.List[string]]::new()
    $ctx = @{
        BundleDir = $Bundle.Dir
        Manifest  = $manifest
        Warnings  = $warnings
        Force     = $Force
        Names     = @()
    }

    foreach ($entry in $active) {
        $names = Get-BundleUninstallNames -Bundle $Bundle -ContentType $entry.ContentType
        if ($names.Count -eq 0) { continue }
        $Step.Value++
        $label = $entry.UninstallLabel -replace '\.\.\.', " ($($names.Count))..."
        Write-Step $Step.Value $TotalSteps "[$bname] $label"
        $ctx.Names = $names
        & $entry.UninstallFn $ctx
    }
    return $warnings
}

# ---------------------------------------------------------------------------
# Install flow
# ---------------------------------------------------------------------------
function Invoke-Install {
    param($SelectedBundles)

    # Count total steps
    $totalContentSteps = 0
    foreach ($b in $SelectedBundles) {
        $totalContentSteps += @($script:ContentRegistry | Where-Object {
            $_.InstallFn -ne $null -and $_.ManifestKey -ne $null -and
            (Test-BundleHasKey -Bundle $b -ManifestKey $_.ManifestKey)
        }).Count
    }
    $TOTAL = 3 + $totalContentSteps

    Write-Host ""
    Write-Host "Installing $($SelectedBundles.Count) bundle(s) onto $($script:OpsHost)..."

    $step = 0

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

    $globalCtx = @{
        Marker  = $marker
        OwnerId = $ownerId
    }

    $allWarnings = [System.Collections.Generic.List[string]]::new()
    $stepRef = [ref]$step
    foreach ($b in $SelectedBundles) {
        $warnings = Invoke-InstallBundle -Bundle $b -GlobalCtx $globalCtx -Step $stepRef -TotalSteps $TOTAL
        $step = $stepRef.Value
        foreach ($w in $warnings) { $allWarnings.Add($w) }
    }

    Write-Host ""
    if ($allWarnings.Count -gt 0) {
        Write-Host "Done with $($allWarnings.Count) warning(s):"
        foreach ($w in $allWarnings) { Write-Host "  WARN  $w" }
        $enableWarns = @($allWarnings | Where-Object { $_ -like "*enable*" -or $_ -like "*resolve*" })
        if ($enableWarns.Count -gt 0) {
            Write-Host "Content was imported but one or more super metrics could not be enabled."
        }
        exit 2
    } else {
        Write-Host "Done. All content installed successfully."
    }
}

# ---------------------------------------------------------------------------
# Uninstall flow
# ---------------------------------------------------------------------------
function Invoke-Uninstall {
    param($SelectedBundles)

    # Check if any bundle needs UI (dashboards/views) across all selected.
    $needUi = $false
    foreach ($b in $SelectedBundles) {
        foreach ($e in $script:ContentRegistry) {
            if ($e.NeedsUi -and $e.UninstallFn -ne $null) {
                if ((Get-BundleUninstallNames -Bundle $b -ContentType $e.ContentType).Count -gt 0) {
                    $needUi = $true; break
                }
            }
        }
        if ($needUi) { break }
    }

    # Dashboard and view deletion goes through the UI layer which is locked to
    # the admin account. Catch this early before spending time authenticating.
    if ($needUi -and $script:User -ne "admin") {
        Write-Error ("ERROR: Dashboard and view uninstall requires the 'admin' account.`n" +
                     "       VCF Ops locks imported dashboards to admin ownership. Only the`n" +
                     "       admin user's UI session can delete them.`n" +
                     "       Re-run with -User admin (or set `$env:VCFOPS_USER='admin').")
        exit 1
    }

    # Count total steps
    $totalContentSteps = 0
    foreach ($b in $SelectedBundles) {
        $totalContentSteps += @($script:ContentRegistry | Where-Object {
            $_.UninstallFn -ne $null -and $_.UninstallOrder -ne $null -and
            ((Get-BundleUninstallNames -Bundle $b -ContentType $_.ContentType).Count -gt 0)
        }).Count
    }

    $TOTAL = 1 + $totalContentSteps
    if ($needUi) { $TOTAL += 2 }

    Write-Host ""
    Write-Host "Uninstalling $($SelectedBundles.Count) bundle(s) from $($script:OpsHost)..."
    if ($Force) { Write-Host "(-Force: skipping dependency checks)" }
    Write-Host "Content to remove:"
    foreach ($b in $SelectedBundles) {
        $bname = if ($b.Manifest.name) { $b.Manifest.name } else { $b.Slug }
        Write-Host "  Bundle: $bname"
        foreach ($e in $script:ContentRegistry) {
            if ($e.UninstallFn -ne $null -and $e.UninstallOrder -ne $null) {
                $names = Get-BundleUninstallNames -Bundle $b -ContentType $e.ContentType
                if ($names.Count -gt 0) {
                    Write-Host "    $($e.ContentType.Substring(0,1).ToUpper() + $e.ContentType.Substring(1)) ($($names.Count)): $($names -join ', ')"
                }
            }
        }
    }

    $hasAnything = $false
    foreach ($b in $SelectedBundles) {
        foreach ($e in $script:ContentRegistry) {
            if ($e.UninstallFn -ne $null -and (Get-BundleUninstallNames -Bundle $b -ContentType $e.ContentType).Count -gt 0) {
                $hasAnything = $true; break
            }
        }
        if ($hasAnything) { break }
    }
    if (-not $hasAnything) {
        Write-Host "  (nothing to remove -- bundles contain no removable content)"
        exit 0
    }

    $allWarnings = [System.Collections.Generic.List[string]]::new()
    $step = 0

    $step++
    Write-Step $step $TOTAL "Authenticating as $($script:User)@$($script:OpsHost) (auth: $($script:AuthSource)) ..."
    Authenticate
    Write-Ok "Authenticated"

    if ($needUi) {
        $step++
        Write-Step $step $TOTAL "Starting UI session (for dashboard/view delete)..."
        Start-UISession
        Write-Ok "UI session established"
    }

    $globalCtx = @{ Force = $Force }
    $stepRef = [ref]$step
    foreach ($b in $SelectedBundles) {
        $warnings = Invoke-UninstallBundle -Bundle $b -GlobalCtx $globalCtx -Step $stepRef -TotalSteps $TOTAL
        $step = $stepRef.Value
        foreach ($w in $warnings) { $allWarnings.Add($w) }
    }

    if ($needUi) {
        $step++
        Write-Step $step $TOTAL "Closing UI session..."
        Stop-UISession
        Write-Ok "UI session closed"
    }

    Write-Host ""
    if ($allWarnings.Count -gt 0) {
        $notFound     = @($allWarnings | Where-Object { $_ -like "*not found*" })
        $realFailures = @($allWarnings | Where-Object { $_ -notlike "*not found*" })
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
# Entry point: discover bundles, select, resolve credentials, fork on mode
# ---------------------------------------------------------------------------

$script:OpsHost  = $OpsHost
$script:User     = $User
$script:Password = $Password
$script:AuthSource = $AuthSource

$allBundles = Get-Bundles
if ($allBundles.Count -eq 0) {
    Write-Error "ERROR: No bundles found. Expected bundles\<slug>\bundle.json or a legacy content\ directory."
    exit 1
}

$modeLabel = if ($Uninstall) { "uninstall" } else { "install" }
$selected = Select-Bundles -Bundles $allBundles -Mode $modeLabel
Show-SelectionSummary -SelectedBundles $selected -Mode $modeLabel

$credMode = if ($Uninstall) { "uninstaller" } else { "installer" }
Get-Credentials -Mode $credMode

$script:BaseUrl = "https://$($script:OpsHost)/suite-api"

if ($Uninstall) {
    Invoke-Uninstall -SelectedBundles $selected
} else {
    Invoke-Install -SelectedBundles $selected
}

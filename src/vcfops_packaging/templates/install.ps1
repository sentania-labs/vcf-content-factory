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
    Auth source: 'local' or a domain name like 'corp.example.com'.
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

# Tracks whether the interactive SSL prompt (in Get-Credentials) chose to
# disable verification.  Initialized to $false; Get-Credentials sets it to
# $true if the user answers 'n'.
#
# This deliberately does NOT share a name with the -SkipSslVerify parameter.
# In a script, param() variables already live in the script scope, so the
# former "$script:SkipSslVerify = $false" here was the SAME variable as the
# switch the operator passed on the command line, and it overwrote it before
# any call site could read it.  That made "if ($SkipSslVerify)" below dead
# code and made the post-prompt guard "$script:SkipSslVerify -and -not
# $SkipSslVerify" a self-cancelling "X -and -not X": -SkipSslVerify and
# VCFOPS_VERIFY_SSL=false were silently ignored on every path.
$script:SslPromptDeclined = $false

# ---------------------------------------------------------------------------
# TLS protocol: force TLS 1.2 on Windows PowerShell 5.1
# ---------------------------------------------------------------------------
# Windows PowerShell 5.1 runs on .NET Framework, which inherits a default
# protocol list that on many machines still resolves to SSL3/TLS 1.0.  VCF
# Operations requires TLS 1.2 or later, so without this every request fails at
# connection time.  PowerShell 7+ runs on .NET Core and negotiates the system
# default, so this is deliberately scoped to Major -lt 6.
#
# This runs unconditionally and before the first request.  It used to be nested
# inside the -SkipSslVerify branch, which meant the operator doing the MORE
# secure thing (valid certificate, no bypass flag) was the only one who never
# got TLS 1.2.  Protocol selection and certificate verification are unrelated
# concerns and must not be gated on each other.
#
# -bor rather than assignment, so an explicitly-configured protocol list is
# preserved.  Where the current value is SystemDefault (0, the .NET Framework
# 4.7+ default) the result is TLS 1.2 only: OS-negotiated TLS 1.3 is
# deliberately traded away.  That tradeoff is accepted rather than made
# conditional -- pinning wrongly costs one installer process TLS 1.3, skipping
# wrongly costs a hard connection failure, and SecurityProtocol -eq 0 is not a
# reliable proxy for healthy OS negotiation on a hardened box.
if ($PSVersionTable.PSVersion.Major -lt 6) {
    [System.Net.ServicePointManager]::SecurityProtocol =
        [System.Net.ServicePointManager]::SecurityProtocol -bor [System.Net.SecurityProtocolType]::Tls12
}

# ---------------------------------------------------------------------------
# SSL: disable verification if requested (lab use only)
# ---------------------------------------------------------------------------
function Disable-CertificateValidationLegacy {
    # Windows PowerShell 5.1 / .NET Framework only.  PS 7+ call sites pass
    # -SkipCertificateCheck (or a per-handler callback) instead.
    #
    # Add-Type cannot redefine a type that already exists in the session, so
    # the class is created once and the policy is re-applied on later calls.
    # That constraint is what produced the former TrustAllCertsVcf /
    # TrustAllCertsVcf2 pair; a type-existence guard removes the need for a
    # second near-identical class.
    if ($PSVersionTable.PSVersion.Major -ge 6) { return }
    if (-not ('TrustAllCertsVcf' -as [type])) {
        Add-Type @"
using System.Net;
using System.Security.Cryptography.X509Certificates;
public class TrustAllCertsVcf : ICertificatePolicy {
    public bool CheckValidationResult(ServicePoint sp, X509Certificate cert,
        WebRequest req, int problem) { return true; }
}
"@
    }
    [System.Net.ServicePointManager]::CertificatePolicy = New-Object TrustAllCertsVcf
}

if ($SkipSslVerify) {
    Write-Warning "TLS certificate verification disabled."
    Disable-CertificateValidationLegacy
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

function Get-PropValue {
    param($Object, [string]$Name)
    # StrictMode-safe member read: returns $null when the member is absent
    # rather than throwing PropertyNotFoundException.
    #
    # Set-StrictMode -Version Latest plus $ErrorActionPreference='Stop' turns
    # "$response.someMissingField" into a terminating error.  On the import
    # path that aborts the installer AFTER content has already landed on the
    # instance, leaving a partial install with a raw stack trace -- the exact
    # failure the advisory work exists to prevent.  install.py cannot hit this
    # because it reads the same envelope with dict.get().
    #
    # Handles both shapes Invoke-Api can return: a PSCustomObject from
    # ConvertFrom-Json, or the plain hashtable it builds on an HTTP error.
    #
    # Note for callers: an array-valued member returns the array, which the
    # pipeline may unwrap to a bare element when it holds exactly one item.
    # Wrap in @( ) before iterating.
    if ($null -eq $Object) { return $null }
    if ($Object -is [System.Collections.IDictionary]) {
        if ($Object.Contains($Name)) { return $Object[$Name] }
        return $null
    }
    $prop = $Object.PSObject.Properties[$Name]
    if ($null -eq $prop) { return $null }
    return $prop.Value
}

function Get-PropList {
    param($Object, [string]$Name)
    # StrictMode-safe read of a collection-valued member.  ALWAYS returns an
    # array, so callers can both iterate it and read .Count without special
    # cases.  Three shapes collapse to an empty array: member absent, member
    # null, member an empty collection.
    #
    # Why this exists separately from Get-PropValue: a function returning a
    # one-element array yields the bare element, and returning an empty array
    # yields $null.  Paging loops in this file use .Count on the returned list
    # as the "did this page have anything" test, and $null.Count / a scalar's
    # .Count would either throw under StrictMode or read 1 for an empty page.
    # The unary comma is load-bearing: PowerShell unrolls an array on return,
    # which would turn @() back into $null and a 1-element array back into a
    # bare object.  ,$array wraps it so the unroll yields the array itself.
    $raw = Get-PropValue $Object $Name
    if ($null -eq $raw) { return ,@() }
    return ,@($raw)
}

function Get-PageTotalCount {
    param($Response)
    # StrictMode-safe read of pageInfo.totalCount, the bound every paging loop
    # in this file uses.  Returns 0 when either hop is missing, which ends the
    # loop -- the outcome the old `if ($r.pageInfo)` guards intended but could
    # not reach, because the guard's own dot-access threw first on an error
    # envelope.  Callers that prefer a page-size fallback to 0 apply it
    # themselves; 0 here means "the server did not tell us".
    $pageInfo = Get-PropValue $Response "pageInfo"
    if ($null -eq $pageInfo) { return 0 }
    $raw = Get-PropValue $pageInfo "totalCount"
    if (-not $raw) { return 0 }
    return [int]$raw
}

function Assert-LookupOk {
    param($Response, [string]$What)
    # Guards the ONE failure mode the #109 sweep introduced.
    #
    # Get-PropList deliberately returns @() for an error envelope.  That is
    # right for a reader and wrong for a DECISION: an empty list from a failed
    # request is indistinguishable from a genuine "no such object", so a caller
    # that branches on emptiness will take the not-found branch on a lookup it
    # knows failed.  Where that branch CREATES something, a transient 500 on
    # the lookup produces a duplicate object and prints OK.  Where it DELETES
    # or reports, it produces a confident false claim about instance state.
    #
    # Before the sweep these sites threw PropertyNotFoundException, which was
    # ugly but safe.  Any converted lookup whose result drives a mutation or a
    # state claim must therefore check the status BEFORE acting on emptiness.
    # Refusing to act is the only safe answer: we do not know what is there.
    $sc = Get-StatusCode $Response
    if ($sc -eq 200) { return }
    # "this step stopped before acting", NOT "nothing was created, deleted, or
    # modified".  The stronger claim is true at all nine current call sites
    # only because every one of them guards BEFORE its mutation; it would
    # become a lie the first time someone placed the guard after one, and a
    # false reassurance in a failure message is worse than none.  This wording
    # stays true wherever the guard is placed.
    Write-Fail ("$What failed (HTTP $sc); refusing to act on an incomplete " +
        "lookup -- this step stopped before acting")
}

function Get-ExtDirectResult {
    param($Response, [string]$What, [switch]$Fatal, [switch]$RequireResult)
    # The Ext.Direct sibling of Get-PropValue + Assert-LookupOk (#116).
    #
    # The #109 sweep put every Invoke-Api-derived read onto Get-PropValue.  The
    # UI Ext.Direct path was not in that sweep and has the same StrictMode
    # exposure, plus one the API path does not have.  These responses come from
    # Invoke-WebRequest + ConvertFrom-Json, i.e. a THIRD envelope shape:
    #
    #     [ { "type":"rpc", "tid":1, "result": {...} } ]
    #
    # an ARRAY of envelopes, where the callers read $result[0].type.  So there
    # are two independent failures in front of each read, not one:
    #
    #   1. $result[0] is an index into a possibly-empty array.  An error page,
    #      a redirect to the login form, or a bare `{}` all yield something
    #      that indexes to nothing.  Routing the member read through
    #      Get-PropValue and stopping there only converts a
    #      PropertyNotFoundException into an IndexOutOfRangeException.
    #   2. .type / .result are absent members under Set-StrictMode.
    #
    # Both are guarded here.  Get-PropValue does the member reads, so this is
    # an extension of the existing helper rather than a second idiom for the
    # same job.
    #
    # -RequireResult is deliberately a SEPARATE switch from -Fatal even though
    # today's four call sites happen to set both or neither.  They answer
    # different questions and must not be merged:
    #
    #   -Fatal          how to report:  Write-Fail (exit) vs throw (the
    #                   caller's try/catch downgrades it to a per-item warning)
    #   -RequireResult  whether an ABSENT `result` member is an error at all.
    #                   For the two list callers it is: they feed a name->id
    #                   map that an uninstall then branches on, so degrading a
    #                   broken envelope to "no such content" prints
    #                   "not found (already removed?)" about content that is
    #                   still there.  Same class as Assert-LookupOk.  For the
    #                   two delete callers it is not: they discard the result,
    #                   and demanding one would invent a new failure on a
    #                   currently working path.
    #
    # -RequireResult rejects a null VALUE as well as an absent member.  Both
    # thumbnail endpoints answer with an object, never null, so a null result
    # is "the server did not answer the question we asked" and not a legitimate
    # empty list -- and Get-AllReports goes on to dereference it, which would
    # be a raw null-reference exception mid-uninstall.  A real empty instance
    # still passes: it arrives as an object whose collections are empty.
    $fail = {
        param([string]$Message)
        if ($Fatal) { Write-Fail $Message }
        throw $Message
    }

    # @($null) is a ONE-element array containing $null, not an empty one, so
    # the null case cannot be folded into the Count check below.
    if ($null -eq $Response) {
        & $fail "$What failed: the UI API returned no response body"
    }
    $envelopes = @($Response)
    if ($envelopes.Count -eq 0) {
        & $fail "$What failed: the UI API returned an empty response envelope"
    }
    $first = $envelopes[0]
    if ($null -eq $first) {
        & $fail "$What failed: the UI API returned an empty response envelope"
    }

    $type = [string](Get-PropValue $first "type")
    if ($type -eq "exception") {
        $msg = [string](Get-PropValue $first "message")
        if (-not $msg) { $msg = "no message supplied" }
        & $fail "$What failed: $msg"
    }

    # Deliberately NOT `Get-PropValue $first "result"`, and this is the one
    # read in the file where that helper is the wrong tool.  Get-PropValue
    # returns its value, and PowerShell unrolls a returned array: a result
    # list holding exactly one report arrives as a bare object, and an empty
    # one arrives as $null, which -RequireResult below would then refuse on a
    # perfectly healthy empty instance.  Get-PropValue's own header documents
    # that caveat.  A property read straight into a variable does not unroll,
    # so the payload survives with its shape intact.  `type` and `message`
    # above are scalars and go through the helper as normal.
    $payload = $null
    if ($first -is [System.Collections.IDictionary]) {
        if ($first.Contains("result")) { $payload = $first["result"] }
    } else {
        $resultProp = $first.PSObject.Properties["result"]
        if ($null -ne $resultProp) { $payload = $resultProp.Value }
    }
    if ($RequireResult -and $null -eq $payload) {
        # Unknown is never the reassuring branch: an envelope with neither an
        # exception nor a result told us nothing, and the caller's next move is
        # a claim about what exists on the instance.
        & $fail ("$What failed: the UI API returned an unrecognised response " +
            "envelope (type='$type', no result payload); refusing to treat " +
            "that as an empty list")
    }
    # The unary comma is load-bearing for collection-valued payloads, and its
    # absence would be a silent behaviour change from the `$result[0].result`
    # this replaced.  PowerShell unrolls an array on return, so a bare
    # `return $payload` turns a 1-element result list into a bare element and
    # an empty one into $null -- Get-AllReports' `$raw -is [System.Array]`
    # branch would then miss, and it would fall through to the property probe
    # on an object that is not one.  Direct assignment never had that problem.
    # Scalars and PSCustomObjects are returned plainly: wrapping those would
    # hand callers a 1-element array instead of the object.
    if ($null -ne $payload -and
        $payload -is [System.Collections.IEnumerable] -and
        $payload -isnot [string]) {
        return ,$payload
    }
    return $payload
}

function Resolve-AuthSource($raw) {
    # Returns the canonical value used by the Suite API ('Local' for local accounts).
    # The UI login helper translates 'Local' -> 'localItem' internally.
    if (-not $raw -or $raw.Trim().ToLower() -eq 'local') { return 'Local' }
    return $raw.Trim()
}

function Load-JsonFile($Path) {
    # -Encoding UTF8 is load-bearing, not decoration (#119).  Get-Content with
    # no -Encoding defaults to the system ANSI code page on Windows PowerShell
    # 5.1 (.NET Framework) and to UTF-8 on PowerShell 7 (.NET Core), so the
    # same installer reading the same bundle decodes differently depending on
    # which PowerShell the customer happens to run.  The failure is NOT a
    # crash: on 5.1 a UTF-8 bundle carrying a non-ASCII content name decodes
    # to mojibake that ConvertFrom-Json parses happily, and the install
    # succeeds with corrupted names on the instance.
    #
    # On READ, -Encoding UTF8 only selects the decoder; the BOM-vs-no-BOM
    # difference 5.1 has for -Encoding UTF8 is a WRITE-side behaviour (5.1
    # emits a BOM, 7 does not).  Reads go through a StreamReader that strips a
    # leading BOM either way, so both a BOM'd and a bare UTF-8 file read
    # identically here.  Any future WRITE site in this file must pin its
    # encoding explicitly rather than copying this argument.
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Load-RawTextFile($Path) {
    # NOT a Get-Content site on purpose (#119).  [System.IO.File]::ReadAllText
    # already defaults to UTF-8 with BOM detection on BOTH .NET Framework and
    # .NET Core, so it has never had the 5.1/7 split above.  Recorded so
    # nobody "fixes" it into inconsistency with the -Encoding UTF8 sites.
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
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

    if (Test-Path -LiteralPath $bundlesRoot) {
        $bundleJsonFiles = Get-ChildItem -LiteralPath $bundlesRoot -Filter "bundle.json" -Recurse -ErrorAction SilentlyContinue |
            Sort-Object FullName
        foreach ($f in $bundleJsonFiles) {
            # Only direct children: bundles/<slug>/bundle.json
            if ($f.Directory.Parent.FullName -ne $bundlesRoot) { continue }
            $slug = $f.Directory.Name
            try {
                # -Encoding UTF8: see Load-JsonFile (#119).
                $manifest = Get-Content -LiteralPath $f.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
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
        if ((Test-Path -LiteralPath $legacyManifest) -and (Test-Path -LiteralPath $legacyContent)) {
            # -Encoding UTF8: see Load-JsonFile (#119).
            try   { $manifest = Get-Content -LiteralPath $legacyManifest -Raw -Encoding UTF8 | ConvertFrom-Json }
            catch { $manifest = [PSCustomObject]@{ name = "bundle"; description = ""; content = [PSCustomObject]@{} } }
            $entries.Add(@{ Slug = $manifest.name; Dir = $ScriptDir; Manifest = $manifest })
        } elseif (Test-Path -LiteralPath $legacyContent) {
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

function Get-BundleDisplayName {
    <#
    .SYNOPSIS
        Return the human-readable display name for a bundle.

    Reads Manifest.display_name when present (set by builder at package time).
    Falls back to Manifest.name for legacy zips built before the display_name
    field was introduced.
    #>
    param($Bundle)
    if ($Bundle.Manifest.display_name) { return $Bundle.Manifest.display_name }
    if ($Bundle.Manifest.name)         { return $Bundle.Manifest.name }
    return $Bundle.Slug
}

function Select-Bundles {
    param(
        [object[]]$Bundles,
        [string]$Mode = "install"
    )

    if ($Bundles.Count -eq 1) {
        $b = $Bundles[0]
        $bname = Get-BundleDisplayName $b
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
            $bname = Get-BundleDisplayName $b
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
        $bname = Get-BundleDisplayName $b
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
    # PSObject.Properties probe is StrictMode-safe; dot-notation throws on missing key.
    $prop = $content.PSObject.Properties[$ManifestKey]
    if (-not $prop) { return $false }
    $section = $prop.Value
    if (-not $section) { return $false }
    $rel = $section.file
    if (-not $rel) { return $false }
    return Test-Path -LiteralPath (Join-Path $Bundle.Dir $rel)
}

function Get-BundleUninstallNames {
    param($Bundle, [string]$ContentType)
    $content = $Bundle.Manifest.content
    if (-not $content) { return @() }
    # PSObject.Properties probe is StrictMode-safe; dot-notation throws on missing key.
    $prop = $content.PSObject.Properties[$ContentType]
    if (-not $prop) { return @() }
    $section = $prop.Value
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

    # Prompt for SSL verification only when neither -SkipSslVerify nor
    # VCFOPS_VERIFY_SSL=false was supplied.  $SkipSslVerify already merges
    # both sources, so $false here means neither was set by the caller.
    if (-not $SkipSslVerify) {
        $sslAns = Read-Host "Verify SSL certificate? [Y/n]"
        if ($sslAns -eq 'n' -or $sslAns -eq 'no' -or $sslAns -eq 'N' -or $sslAns -eq 'No') {
            # Recorded under its own name; the caller promotes it to the real
            # $SkipSslVerify switch after Get-Credentials returns.
            $script:SslPromptDeclined = $true
        }
    }

    if (-not $script:User) {
        $inp = Read-Host "Username [admin]"
        $script:User = if ($inp) { $inp } else { "admin" }
    }

    # Auth-source support contract (see README_framework.md "Authentication"):
    # Supported: Local (recommended), vCenter SSO (VC/VC_GROUP), Active Directory
    # (UPN form), LDAP (per spec; untested by us).  Not supported: VIDB ("VCF SSO")
    # and VIDM (Workspace ONE Access) -- both are federated SSO sources that refuse
    # programmatic password grants.  Use a Local service account for those deployments.
    if (-not $script:AuthSource) {
        $inp = Read-Host ("Auth source name (or 'local'). Type 'local' for local accounts;" +
            " for non-local sources, type the auth-source name as configured" +
            " in VCF Operations (e.g. your vCenter SSO source, AD source, or" +
            " LDAP source). VIDB and VIDM are not supported -- use a local" +
            " account. [local]")
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
    # [System.Collections.IDictionary] and .Contains(), NOT [hashtable] and
    # .ContainsKey(): this must classify an envelope exactly the way
    # Get-PropValue does, because this diff routes the same object through
    # both.  A shape one of them treats as an error envelope and the other
    # as a PSCustomObject is how a "checked the status" guard silently stops
    # guarding.
    if ($resp -is [System.Collections.IDictionary] -and $resp.Contains("__statusCode")) {
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

function Get-OwnerId {
    # Extracted from Invoke-Install so the missing-id guard below is reachable
    # from the test harness.  Inline in a 200-line install driver it was
    # unreachable, i.e. an untested guard, which is how guards rot.
    $currentUser = Get-CurrentUser
    $ownerId = Get-PropValue $currentUser "id"
    if (-not $ownerId) {
        Write-Fail "/api/auth/currentuser returned no user id; cannot stamp content ownership"
    }
    return $ownerId
}

function Get-CurrentUser {
    $resp = Invoke-Api -Method GET -Path "/api/auth/currentuser"
    if ((Get-StatusCode $resp) -ne 200) { Write-Fail "currentuser failed: $(Get-PropValue $resp '__body')" }
    return $resp
}

function Get-MarkerFilename {
    param([int]$TimeoutSeconds = 120)

    $deadline = [System.DateTime]::UtcNow.AddSeconds($TimeoutSeconds)

    # Every read of an export-status envelope below goes through Get-PropValue.
    # An error envelope (the hashtable Invoke-Api builds on an HTTP failure) has
    # none of these members, and a raw dot-access on it is a terminating error
    # under StrictMode.  In the try/catch loops that surfaced as a misleading
    # "timed out" after the full timeout; at the uncaught site it was a crash.
    #
    # This first loop waits for any PRIOR export to finish before the probe
    # POST below starts one of ours.  Its exit condition is therefore a state
    # claim about the instance, and Get-PropValue's safe default (empty string
    # for a member that is not there) is indistinguishable from a legitimate
    # idle answer.  Without the status gate, one transient 5xx -- whose error
    # envelope carries no "state" at all -- read as "nothing is running", the
    # probe POST overlapped a live export, and the install died task-busy.
    # Same class as the create-on-failed-lookup guard (Assert-LookupOk), one
    # layer down: this is a POLL, not a pre-mutation lookup.
    #
    # Assert-LookupOk is deliberately NOT used here.  It refuses on the first
    # non-200, which is right before a mutation and wrong for a poll whose
    # whole job is to outlast a transient.  An unknown status keeps polling
    # and, only at the deadline, fails with a sentence naming what we last
    # saw.  Structure and behaviour match install.py:360-368 line for line;
    # the two installers drifting here is its own defect class.
    #
    # BOUNDARY (matches install.py:362-365, do not "fix" without fixing both):
    # a 200 whose body carries no "state" IS treated as idle.  That is the
    # never-exported instance, and refusing there would burn the full timeout
    # and then abort first install on a clean box.  Only a non-200 means "we
    # do not know".
    $lastSeen = "no status response yet"
    while ($true) {
        try {
            $g = Invoke-Api -Method GET -Path "/api/content/operations/export"
            $sc = Get-StatusCode $g
            if ($sc -eq 200) {
                $st = [string](Get-PropValue $g "state")
                $lastSeen = "state=$st"
                if ($st -ne "RUNNING" -and $st -ne "INITIALIZED") { break }
            } else {
                $lastSeen = "HTTP $sc"
            }
        } catch {
            $lastSeen = "status request threw: $_"
        }
        if ([System.DateTime]::UtcNow -gt $deadline) { Write-Fail "Timed out waiting for prior export to finish (last seen: $lastSeen)" }
        Start-Sleep -Seconds 2
    }

    $priorStart = 0
    try {
        $g = Invoke-Api -Method GET -Path "/api/content/operations/export"
        $priorStartRaw = Get-PropValue $g "startTime"
        if ($priorStartRaw) { $priorStart = [long]$priorStartRaw }
    } catch {}

    $exportBody = @{ scope = "CUSTOM"; contentTypes = @("SUPER_METRICS") }
    $r = Invoke-Api -Method POST -Path "/api/content/operations/export" -Body $exportBody
    $sc = Get-StatusCode $r
    if ($sc -ne 200 -and $sc -ne 202) { Write-Fail "Marker-probe export failed ($sc): $(Get-PropValue $r '__body')" }

    $deadline = [System.DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ($true) {
        $g = Invoke-Api -Method GET -Path "/api/content/operations/export"
        $st = [string](Get-PropValue $g "state")
        $startTimeRaw = Get-PropValue $g "startTime"
        $startTime = if ($startTimeRaw) { [long]$startTimeRaw } else { 0 }
        if ($startTime -gt $priorStart -and $st -like "FINI*") { break }
        # $st is "" for an error envelope as well as for a 200 that omits the
        # member, so the timeout sentence names the HTTP status too; "state="
        # alone sent an operator looking at the wrong thing.  Unlike
        # install.py:383, a non-200 here keeps polling rather than dying on
        # the first transient: this loop is already past the probe POST, the
        # export is running, and outlasting a blip is the recoverable answer.
        $sc = Get-StatusCode $g
        if ([System.DateTime]::UtcNow -gt $deadline) { Write-Fail "Marker-probe export timed out; state=$st (last status HTTP $sc)" }
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
    Remove-Item -LiteralPath $tmpZip -Force

    if (-not $marker) { Write-Fail "Export zip did not contain a *L.v1 marker file" }
    return $marker
}

function Write-ImportSummaryWarnings {
    param($Status)
    # Reports per-content-type summaries that failed, skipped anything, or
    # ended in an unexpected state, even when the top-level state is FINISHED.
    #
    # The condition is deliberately identical to install.py:454, including the
    # skipped>0 term.  Narrowing it here (to imported=0 only) looked like a
    # cry-wolf fix and was a regression: the named, per-content-type advisory
    # that replaced it covers DASHBOARDS and VIEW_DEFINITIONS ONLY, so
    # SUPER_METRICS and REPORTS were left with no signal at all.  An operator
    # whose super metrics all skipped got "OK  Imported 4 super metric(s)" as
    # the last line over an instance that did not change.
    #
    # If this line is ever narrowed, narrow install.py:454 in the same commit.
    # The two installers drifting is the defect class this whole area exists
    # to close.
    #
    # Split out of Import-ContentZip so it can be exercised without an
    # appliance: this runs after content has been imported, so any error
    # escaping it leaves a partial install.  Every read is probe-based; a
    # status envelope with no operationSummaries is normal, not exceptional.
    $summaries = Get-PropValue $Status "operationSummaries"
    if (-not $summaries) { return }
    foreach ($os in @($summaries)) {
        if ($null -eq $os) { continue }
        $osState = [string](Get-PropValue $os "state")
        $osFailedRaw = Get-PropValue $os "failed"
        $osFailed = if ($osFailedRaw) { [int]$osFailedRaw } else { 0 }
        $osSkippedRaw = Get-PropValue $os "skipped"
        $osSkipped = if ($osSkippedRaw) { [int]$osSkippedRaw } else { 0 }
        $osImported = Get-PropValue $os "imported"
        $osType = [string](Get-PropValue $os "contentType")
        if (($osState -ne "FINISHED" -and $osState -ne "") -or $osFailed -gt 0 -or $osSkipped -gt 0) {
            Write-Host ("WARN: content type ${osType}: " +
                "imported=$osImported skipped=$osSkipped failed=$osFailed state=$osState")
        }
    }
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
        $priorEndRaw = Get-PropValue $pre "endTime"
        if ($priorEndRaw) { $priorEnd = [long]$priorEndRaw }
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
    $sc = 0
    while ($true) {
        $s = Invoke-Api -Method GET -Path "/api/content/operations/import"
        # Probe-safe reads: the status envelope is not guaranteed to carry
        # every field, and a dot-access on a missing one is a terminating
        # error here (see Get-PropValue).
        #
        # $sc is read for the timeout sentence only (#121).  This loop
        # deliberately keeps polling on a non-200, exactly as the marker-probe
        # loop above does: the import is already running on the instance by
        # this point, so outlasting a transient blip is the recoverable
        # answer.  That tolerance is what makes the status worth naming --
        # a run that 503'd for the whole timeout looks identical, from the
        # message alone, to one that never started.
        $sc = Get-StatusCode $s
        $state = [string](Get-PropValue $s "state")
        $endTimeRaw = Get-PropValue $s "endTime"
        $endTime = if ($endTimeRaw) { [long]$endTimeRaw } else { 0 }
        if ($endTime -gt $priorEnd -and $state -ne "RUNNING" -and $state -ne "INITIALIZED") {
            if ($state.ToUpper() -like "*FAIL*") { Write-Fail "Import of $Label finished with state=$state" }
            Write-ImportSummaryWarnings -Status $s
            # Returns the import-status object so callers can inspect
            # operationSummaries.  Call sites that do not need it must assign
            # to $null: an uncaptured return value would join the calling
            # function's output stream.
            return $s
        }
        # "state=" alone is not a verdict: an empty $state means BOTH "a 200
        # that omitted the member" and "we never got a usable answer at all",
        # and an operator reading the first meaning goes looking at the wrong
        # thing.  Name the last-seen HTTP status too, the same way the
        # marker-probe timeout above does (#121).
        if ([System.DateTime]::UtcNow -gt $deadline) { Write-Fail "Import of $Label timed out; state=$state (last status HTTP $sc)" }
        Start-Sleep -Seconds 2
    }
}

function Get-DefaultPolicyId {
    # This is the site the #109 review measured throwing: on an error envelope
    # $resp.policySummaries is a PropertyNotFoundException, and this runs at
    # InstallOrder 3 via Install-SmEnable, i.e. AFTER content has landed.  The
    # operator got a raw .NET stack trace over a half-modified instance where
    # the Write-Fail below is the sentence they can act on.
    $resp = Invoke-Api -Method GET -Path "/api/policies"
    foreach ($p in (Get-PropList $resp "policySummaries")) {
        if ($null -eq $p) { continue }
        if (Get-PropValue $p "defaultPolicy") { return (Get-PropValue $p "id") }
    }
    $sc = Get-StatusCode $resp
    Write-Fail "No default policy found in /api/policies (HTTP $sc)"
}

function Get-SupermetricsByName {
    param([string[]]$Names)
    $found = @{}
    $page = 0; $pageSize = 1000
    $target = [System.Collections.Generic.HashSet[string]]::new($Names)
    do {
        $resp = Invoke-Api -Method GET -Path "/api/supermetrics" -Query @{ page = "$page"; pageSize = "$pageSize" }
        # Callers treat an absent name as "not on the instance" and either skip
        # the enable or report "already removed".  Both are state claims.
        Assert-LookupOk -Response $resp -What "Super metric lookup"
        $items = Get-PropList $resp "superMetrics"
        foreach ($sm in $items) {
            if ($null -eq $sm) { continue }
            $smName = [string](Get-PropValue $sm "name")
            if ($smName -and $target.Contains($smName)) { $found[$smName] = Get-PropValue $sm "id" }
        }
        $total = Get-PageTotalCount $resp
        if ($total -eq 0) { $total = $items.Count }
        $page++
    } while (($page * $pageSize) -lt $total -and $items.Count -gt 0)
    return $found
}

function Import-PolicyZip {
    param([byte[]]$ZipBytes)
    # POST /api/policies/import?forceImport=true as multipart/form-data.
    # The session-level Content-Type header must NOT be application/json for
    # multipart uploads -- we use Invoke-RestMethod with -Form which sets the
    # correct boundary automatically.
    $uri = "$script:BaseUrl/api/policies/import?forceImport=true"
    Add-Type -AssemblyName System.Net.Http
    $content = New-Object System.Net.Http.MultipartFormDataContent
    $byteArray = New-Object System.Net.Http.ByteArrayContent(,$ZipBytes)
    $byteArray.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse("application/zip")
    $content.Add($byteArray, "policy", "exportedPolicies.zip")

    $handler = New-Object System.Net.Http.HttpClientHandler
    if ($SkipSslVerify -and $PSVersionTable.PSVersion.Major -ge 6) {
        # PS 7+ / .NET Core: set the callback directly on the handler.
        # PS 5.1 / .NET Framework: ServicePointManager (set at script startup)
        # covers HttpClient too, so no per-handler callback is needed.
        $handler.ServerCertificateCustomValidationCallback = [System.Net.Http.HttpClientHandler]::DangerousAcceptAnyServerCertificateValidator
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
    # (without policyIds -- that variant does not enable content-zip SMs).
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
        if (-not $policyElem) { throw "Policy XML has no <Policy> element -- cannot inject SM '$SmName'" }
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
        if (Test-Path -LiteralPath $tmpZip) { Remove-Item -LiteralPath $tmpZip -Force -ErrorAction SilentlyContinue }
    }
}

function Enable-BuiltinMetricsOnDefaultPolicy {
    param(
        [object[]]$Entries,   # each: @{adapter_kind; resource_kind; metric_key}
        [string]$PolicyId
    )
    # Group entries by (adapter_kind, resource_kind).
    $grouped = @{}
    foreach ($e in $Entries) {
        $gkey = "$($e.adapter_kind)|$($e.resource_kind)"
        if (-not $grouped.ContainsKey($gkey)) {
            $grouped[$gkey] = @{ AdapterKind = $e.adapter_kind; ResourceKind = $e.resource_kind; Keys = [System.Collections.Generic.List[string]]::new() }
        }
        $grouped[$gkey].Keys.Add($e.metric_key)
    }
    $allKeys = [System.Collections.Generic.HashSet[string]]::new()
    foreach ($e in $Entries) { [void]$allKeys.Add($e.metric_key) }

    # Export policy and parse XML.
    $policyXml = Export-DefaultPolicyXml -PolicyId $PolicyId
    [xml]$doc = $policyXml

    # Record which keys were already enabled before our edit.
    $alreadyEnabled = [System.Collections.Generic.HashSet[string]]::new()
    foreach ($node in @($doc.GetElementsByTagName("Metric"))) {
        $mid = $node.GetAttribute("id")
        if ($allKeys.Contains($mid) -and $node.GetAttribute("enabled").ToLower() -eq "true") {
            [void]$alreadyEnabled.Add($mid)
        }
    }

    # Purge any existing <Metric id=...> entries for keys being injected.
    $staleNodes = @($doc.GetElementsByTagName("Metric") |
        Where-Object { $allKeys.Contains($_.GetAttribute("id")) })
    foreach ($node in $staleNodes) {
        $node.ParentNode.RemoveChild($node) | Out-Null
    }

    # Locate or create PackageSettings.
    $pkgSettings = $doc.GetElementsByTagName("PackageSettings") | Select-Object -First 1
    if (-not $pkgSettings) {
        $policyElem = $doc.GetElementsByTagName("Policy") | Select-Object -First 1
        if (-not $policyElem) { throw "Policy XML has no <Policy> element -- cannot inject built-in metrics" }
        $pkgSettings = $doc.CreateElement("PackageSettings")
        $policyElem.AppendChild($pkgSettings) | Out-Null
    }

    # Inject fresh <Metrics> blocks with <Metric> entries.
    foreach ($gkey in $grouped.Keys) {
        $g = $grouped[$gkey]
        $ak = $g.AdapterKind
        $rkKey = $g.ResourceKind

        $metricsBlock = $null
        foreach ($candidate in @($pkgSettings.GetElementsByTagName("Metrics"))) {
            if ($candidate.GetAttribute("adapterKind") -eq $ak -and
                $candidate.GetAttribute("resourceKind") -eq $rkKey) {
                $metricsBlock = $candidate
                break
            }
        }
        if (-not $metricsBlock) {
            $metricsBlock = $doc.CreateElement("Metrics")
            $metricsBlock.SetAttribute("adapterKind", $ak)
            $metricsBlock.SetAttribute("resourceKind", $rkKey)
            $pkgSettings.AppendChild($metricsBlock) | Out-Null
        }

        foreach ($mk in $g.Keys) {
            $newEntry = $doc.CreateElement("Metric")
            $newEntry.SetAttribute("enabled", "true")
            $newEntry.SetAttribute("id", $mk)
            $metricsBlock.AppendChild($newEntry) | Out-Null
        }
    }

    # Rebuild ZIP and re-import.
    $editedXml = $doc.OuterXml
    if (-not $editedXml.StartsWith("<?xml")) {
        $editedXml = '<?xml version="1.0" encoding="UTF-8"?>' + "`n" + $editedXml
    }
    $editedXmlBytes = [System.Text.Encoding]::UTF8.GetBytes($editedXml)

    $tmpZip = [System.IO.Path]::GetTempFileName() + ".zip"
    $ms = New-Object System.IO.MemoryStream
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

        $origZip = [System.IO.Compression.ZipFile]::OpenRead($tmpZip)
        $xmlEntryName = $null
        $otherEntries = @{}
        try {
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

        $outZip = New-Object System.IO.Compression.ZipArchive($ms, [System.IO.Compression.ZipArchiveMode]::Create, $true)
        try {
            $xmlEntry = $outZip.CreateEntry($xmlEntryName, [System.IO.Compression.CompressionLevel]::Optimal)
            $xmlStream = $xmlEntry.Open()
            $xmlStream.Write($editedXmlBytes, 0, $editedXmlBytes.Length)
            $xmlStream.Dispose()
            foreach ($ename in $otherEntries.Keys) {
                $e = $outZip.CreateEntry($ename, [System.IO.Compression.CompressionLevel]::Optimal)
                $s = $e.Open()
                $s.Write($otherEntries[$ename], 0, $otherEntries[$ename].Length)
                $s.Dispose()
            }
        } finally { $outZip.Dispose() }

        Import-PolicyZip -ZipBytes $ms.ToArray()
    } finally {
        $ms.Dispose()
        if (Test-Path -LiteralPath $tmpZip) { Remove-Item -LiteralPath $tmpZip -Force -ErrorAction SilentlyContinue }
    }

    # NOTE: comma operator required, returning a HashSet (IEnumerable) without it causes
    # PowerShell to enumerate the collection through the pipeline, yielding AutomationNull
    # (empty), a bare string (1 item), or Object[] (N items) instead of the HashSet.
    # Same pattern as New-ZipBytes (line 1148) and New-DashboardZip (line 1235).
    # Bug class: PS function return unwrap; see memory/feedback_ps_function_return_unwrap.md
    return ,$alreadyEnabled
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
        if (Test-Path -LiteralPath $tmpZip) { Remove-Item -LiteralPath $tmpZip -Force -ErrorAction SilentlyContinue }
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

function Get-GroupName {
    param($Group)
    # /api/resources/groups nests the display name two levels deep, so BOTH
    # hops need the StrictMode-safe reader: a group whose envelope omits
    # resourceKey throws on the first dot, before the .name is ever reached.
    $rk = Get-PropValue $Group "resourceKey"
    if ($null -eq $rk) { return $null }
    return Get-PropValue $rk "name"
}

function Upsert-CustomGroup {
    param($Payload)
    $name = $Payload.resourceKey.name
    $resp = Invoke-Api -Method GET -Path "/api/resources/groups" -Query @{ name = $name; pageSize = "100" }
    # This lookup chooses between PUT and POST.  Falling through to POST on a
    # failed lookup creates a SECOND custom group with the same name and
    # reports success.  Stop instead.
    Assert-LookupOk -Response $resp -What "Custom group lookup for '$name'"
    $existingId = $null
    foreach ($g in (Get-PropList $resp "groups")) {
        if ($null -eq $g) { continue }
        if ((Get-GroupName $g) -eq $name) { $existingId = Get-PropValue $g "id"; break }
    }
    if ($existingId) {
        $r = Invoke-Api -Method PUT -Path "/api/resources/groups/$existingId" -Body $Payload
        $sc = Get-StatusCode $r
        if ($sc -eq 500) {
            # The custom group PUT endpoint sometimes returns 500 even when the
            # update was applied (server-side race condition). Verify via GET
            # before treating as fatal.
            $chk = Invoke-Api -Method GET -Path "/api/resources/groups" -Query @{ name = $name; pageSize = "100" }
            # "the group exists, so the 500 was spurious" is a claim about the
            # instance.  If the verification lookup itself failed we cannot
            # make it, and must not silently downgrade to "PUT failed".
            Assert-LookupOk -Response $chk -What "Custom group PUT verification lookup for '$name'"
            $stillExists = $false
            foreach ($g in (Get-PropList $chk "groups")) {
                if ($null -eq $g) { continue }
                if ((Get-GroupName $g) -eq $name) { $stillExists = $true; break }
            }
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
        Assert-LookupOk -Response $resp -What "Custom group lookup"
        $groups = Get-PropList $resp "groups"
        if ($groups.Count -eq 0) { break }
        foreach ($g in $groups) {
            if ($null -eq $g) { continue }
            $n = [string](Get-GroupName $g)
            if ($n -and $target.Contains($n)) { $found[$n] = Get-PropValue $g "id" }
        }
        $total = Get-PageTotalCount $resp
        if ($total -eq 0) { $total = $groups.Count }
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
    return ,$ms.ToArray()
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
    return ,$ms.ToArray()
}

function Get-DashboardIds {
    param([string]$DashJson, [string]$OwnerId)
    $patchedJson = $DashJson -replace "PLACEHOLDER_USER_ID", $OwnerId
    $data = $patchedJson | ConvertFrom-Json
    return @($data.dashboards | Where-Object { $_.id } | ForEach-Object { $_.id })
}

# ---------------------------------------------------------------------------
# Advisory helpers (parity with install.py: _bounded_names,
# _extract_dashboard_names, _extract_view_names, _all_skipped_summaries)
# ---------------------------------------------------------------------------
# Bounds for the content names interpolated into the "NOT updated" advisory.
# That string prints twice (inline WARN plus the ATTENTION trailer), so a
# single pathological name or a bundle carrying dozens of objects must not
# fill the operator's screen.  Deliberately re-stated rather than imported:
# this script ships standalone inside every bundle zip.
#
# CALLING CONVENTION for the three name helpers below: each returns a
# comma-wrapped array, so a one-name or zero-name result survives the pipeline
# as an array rather than unwrapping to a bare string or $null.  Assign the
# result directly.  Do NOT write @(Get-BoundedNames ...): wrapping an already
# comma-wrapped return produces a one-element array whose single element is
# the real array, and .Count then reads 1 for every input.
$script:AdvisoryNameMaxChars = 120
$script:AdvisoryNamesMax = 20

function Get-BoundedNames {
    param([object[]]$Names)
    # Coerce, clip and cap content names bound for an advisory line.
    # Never throws: every caller runs AFTER content has been imported, so an
    # escaping error from a message-decoration helper would abort the
    # installer mid-run and leave a partial install.
    $out = New-Object System.Collections.Generic.List[string]
    try {
        foreach ($name in $Names) {
            $text = [string]$name
            if ($text.Length -gt $script:AdvisoryNameMaxChars) {
                $text = $text.Substring(0, $script:AdvisoryNameMaxChars) + "..."
            }
            $out.Add($text)
        }
    } catch {
        return ,@()
    }
    if ($out.Count -gt $script:AdvisoryNamesMax) {
        $extra = $out.Count - $script:AdvisoryNamesMax
        $kept = $out.GetRange(0, $script:AdvisoryNamesMax)
        $kept.Add("and $extra more")
        return ,$kept.ToArray()
    }
    # Comma-wrapped: PowerShell unwraps single-element collections on return.
    return ,$out.ToArray()
}

function Get-DashboardAdvisoryNames {
    param([string]$DashJson, [string]$OwnerId)
    # Names of the dashboards in a rendered dashboard.json, best effort.
    $names = New-Object System.Collections.Generic.List[string]
    try {
        $patched = $DashJson -replace "PLACEHOLDER_USER_ID", $OwnerId
        $data = $patched | ConvertFrom-Json
        if ($null -eq $data) { return ,@() }
        # ConvertFrom-Json happily returns an array, a string or a number.
        # PSObject.Properties probe is StrictMode-safe; dot-notation throws.
        $prop = $data.PSObject.Properties["dashboards"]
        if (-not $prop -or $null -eq $prop.Value) { return ,@() }
        # Must be a JSON array.  A string or a lone object here means the
        # document is not what the renderer emits, and naming "?" would be
        # worse than naming nothing: install.py returns [] for the same input
        # and the advisory falls back to the generic word "dashboard".
        if ($prop.Value -isnot [System.Array]) { return ,@() }
        foreach ($d in @($prop.Value)) {
            $name = ""
            if ($null -ne $d) {
                $nameProp = $d.PSObject.Properties["name"]
                if ($nameProp -and $nameProp.Value) { $name = [string]$nameProp.Value }
                if (-not $name) {
                    $idProp = $d.PSObject.Properties["id"]
                    if ($idProp -and $idProp.Value) { $name = [string]$idProp.Value }
                }
            }
            if (-not $name) { $name = "?" }
            $names.Add($name)
        }
    } catch {
        return ,@()
    }
    $bounded = Get-BoundedNames -Names $names.ToArray()
    return ,$bounded
}

function Get-ViewAdvisoryNames {
    param([string]$ViewsXml)
    # Titles of the views in a rendered views_content.xml, best effort.
    # Walks every ViewDef and takes its direct <Title> child, falling back to
    # a name attribute -- the same extraction install.py performs.  A real
    # parse (rather than a regex) ignores attributes on <Title> and hands back
    # decoded text, so a view named "CPU & Memory" prints that way instead of
    # "CPU &amp; Memory" beside the unescaped dashboard names.
    $names = New-Object System.Collections.Generic.List[string]
    try {
        if (-not $ViewsXml) { return ,@() }
        $doc = New-Object System.Xml.XmlDocument
        # No external entity resolution: this parses a file off disk.
        $doc.XmlResolver = $null
        $doc.LoadXml($ViewsXml)
        foreach ($viewDef in $doc.SelectNodes("//ViewDef")) {
            $name = ""
            $titleNode = $viewDef.SelectSingleNode("Title")
            if ($null -ne $titleNode) { $name = ([string]$titleNode.InnerText).Trim() }
            if (-not $name) { $name = ([string]$viewDef.GetAttribute("name")).Trim() }
            if (-not $name) { $name = "unnamed view" }
            $names.Add($name)
        }
    } catch {
        return ,@()
    }
    $bounded = Get-BoundedNames -Names $names.ToArray()
    return ,$bounded
}

function Get-AllSkippedSummaries {
    param($Result, [string[]]$ContentTypes)
    # Returns @{ contentType = @{ Imported = N; Skipped = N } } for the
    # per-content-type summaries that imported nothing while skipping
    # something.  A FINISHED import with imported=0/skipped=N left the
    # instance unchanged, so it must not be reported as a clean install.
    #
    # imported=0 AND skipped>0 is the whole test for the ADVISORY: a re-sync
    # that imports 1 and skips 1 is not an advisory and must stay quiet here.
    # This is a narrower test than the mid-stream WARN in
    # Write-ImportSummaryWarnings, deliberately: this line names the affected
    # objects and is the last thing the operator reads, so it must only fire
    # when the instance genuinely did not change.
    #
    # Hashtable return survives the pipeline intact (no unwrap).
    $flagged = @{}
    if ($null -eq $Result) { return $flagged }
    $summaries = Get-PropValue $Result "operationSummaries"
    if (-not $summaries) { return $flagged }
    foreach ($entry in @($summaries)) {
        if ($null -eq $entry) { continue }
        $ct = [string](Get-PropValue $entry "contentType")
        if (-not $ct) { $ct = "?" }
        if ($ContentTypes -and $ContentTypes.Count -gt 0 -and ($ContentTypes -notcontains $ct)) { continue }
        $imported = 0
        $skipped = 0
        try {
            $impRaw = Get-PropValue $entry "imported"
            if ($null -ne $impRaw) { $imported = [int]$impRaw }
            $skpRaw = Get-PropValue $entry "skipped"
            if ($null -ne $skpRaw) { $skipped = [int]$skpRaw }
        } catch {
            continue
        }
        if ($imported -eq 0 -and $skipped -gt 0) {
            $flagged[$ct] = @{ Imported = $imported; Skipped = $skipped }
        }
    }
    return $flagged
}

function Get-SmGhostStateSkipCount {
    param($Result)
    # Returns the number of skipped super metrics when the import shows the
    # SM ghost-state signature, or 0 when it does not.  Non-zero means "retry
    # the same zip once".
    #
    # Ghost state: an SM row exists in the DB but never fully registered in the
    # internal SM catalog (typically a previous partial import).  The importer
    # then treats it as already-present and skips it, so GET /{id} works while
    # the list API and the assign endpoint do not see it -- an enable call
    # 404s.  A second import of the same zip re-registers it.  Bisected and
    # documented at knowledge/context/wire-formats/wire_formats.md, section
    # "SM ghost state".
    #
    # SUPER_METRICS ONLY, and this is evidence, not caution.  #114 bisected the
    # identical imported=0/skipped>0 signature on the DASHBOARDS and
    # VIEW_DEFINITIONS paths and reproduced ONE cause: create-only mode
    # (force=false), where the skip is idempotent and a retry is a guaranteed
    # no-op that still costs a round trip plus a 30s import-busy backoff.
    #
    # READ THAT AS A CAUSE, NOT AS THE MEANING OF THE SIGNATURE.  force=false
    # was the only trigger #114 could reproduce, and this installer hard-codes
    # force=true (see Import-ContentZip).  Per
    # knowledge/context/api-surface/content_import_skip_semantics.md, a
    # force=true occurrence is "unexplained, not benign, and should be treated
    # as a new finding" -- three contexts were never tested (UI-locked
    # dashboards, non-admin importing another user's content, pak-supplied
    # solution content).  So the reason NOT to retry dashboards is not "we know
    # it is harmless"; it is that no evidence says a retry would help, and #114
    # showed it demonstrably does not for the one cause we understand.  If you
    # ever see this signature on a force=true dashboard import, investigate it
    # -- do not reach for this function.
    #
    # Do not widen the contentType test here, and do not call this from
    # Install-Dashboard.
    #
    # Mirrors install.py:_install_supermetrics exactly, including summing
    # across multiple SUPER_METRICS summaries and treating "no SUPER_METRICS
    # summary at all" as no-retry.  If one side changes, change both.
    if ($null -eq $Result) { return 0 }
    $matched = $false
    $totalImported = 0
    $totalSkipped = 0
    foreach ($entry in (Get-PropList $Result "operationSummaries")) {
        if ($null -eq $entry) { continue }
        if ([string](Get-PropValue $entry "contentType") -ne "SUPER_METRICS") { continue }
        $matched = $true
        $imp = Get-PropValue $entry "imported"
        if ($imp) { $totalImported += [int]$imp }
        $skp = Get-PropValue $entry "skipped"
        if ($skp) { $totalSkipped += [int]$skp }
    }
    if (-not $matched) { return 0 }
    if ($totalImported -eq 0 -and $totalSkipped -gt 0) { return $totalSkipped }
    return 0
}

function Write-AdvisoryTrailer {
    param([object[]]$Advisories)
    # Trailer printed in BOTH summary branches.  Without it, a run whose
    # dashboard import changed nothing ends on "Done. All content installed
    # successfully.", which is the green-while-broken defect this check exists
    # to kill, relocated to the summary.  The last line is what an operator
    # remembers.  Advisories never touch the exit code.
    if ($null -eq $Advisories -or $Advisories.Count -eq 0) { return }
    Write-Host ""
    Write-Host ("$($Advisories.Count) item(s) need attention " +
        "(nothing failed, but content on the instance did not change):")
    foreach ($a in $Advisories) { Write-Host "  ATTENTION  $a" }
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
    $loginBody = ("mainAction=login" +
        ("&userName="     + [uri]::EscapeDataString($script:User)) +
        ("&password="     + [uri]::EscapeDataString($script:Password)) +
        ("&authSourceId=" + [uri]::EscapeDataString($uiAuthSource)) +
        "&authSourceName=Local+Account" +
        "&authSourceType=" +
        "&forceLogin=false" +
        "&timezone=0" +
        "&languageCode=us")

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
            # is HttpResponseHeaders -- not indexable with []. Use GetValues().
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
    # dashboard.action is NOT Ext.Direct: it answers with a single object, not
    # an array of envelopes, so Get-ExtDirectResult does not apply here.  The
    # StrictMode exposure is the same though ($result.dashboards throws when
    # the member is absent), and so is the decision hazard: this list feeds a
    # name->id map that Uninstall-Dashboards branches on, and degrading a
    # broken response to an empty list prints "not found (already removed?)"
    # about dashboards that are still on the instance (#116).
    #
    # The read is a direct property probe, not Get-PropValue, for the same
    # reason as in Get-ExtDirectResult: Get-PropValue RETURNS its value and
    # PowerShell unrolls a returned array, so a genuinely empty instance
    # ("dashboards":[]) would come back as $null and be refused as broken.
    # Measured, not assumed.  Probing PSObject.Properties distinguishes the
    # member being absent from its value being an empty list.
    $dashboards = $null
    if ($null -ne $result) {
        if ($result -is [System.Collections.IDictionary]) {
            if ($result.Contains("dashboards")) { $dashboards = $result["dashboards"] }
        } else {
            $dashProp = $result.PSObject.Properties["dashboards"]
            if ($null -ne $dashProp) { $dashboards = $dashProp.Value }
        }
    }
    if ($null -eq $dashboards) {
        Write-Fail ("Dashboard list failed: the UI API response carried no " +
            "'dashboards' field; refusing to treat that as an empty dashboard list")
    }
    return @($dashboards | Where-Object { $_ })
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
    $allViews = [System.Collections.Generic.List[object]]::new()
    # -RequireResult: this list feeds Uninstall-Views' name->id map, so an
    # unreadable envelope must stop the run rather than degrade to "no views
    # exist" and print "not found (already removed?)" (#116).
    $grouped = Get-ExtDirectResult -Response $result -What "View list" -Fatal -RequireResult
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
    } else {
        # The residual else, and it must not carry a confident sentence.
        # -RequireResult closes absent, null, and empty-envelope.  It does NOT
        # close WRONG SHAPE: a present result that is a string, a bool, or an
        # array falls straight through the -is test above, and without this
        # branch Get-AllViews would return an empty list.  Uninstall-Views then
        # prints "View not found (already removed?)" about views that are
        # still on the instance -- the exact sentence
        # knowledge/lessons/unenumerated-exit-status-is-not-a-verdict.md lists
        # as an instance of this defect.  An unenumerated shape is unknown, and
        # unknown is never the reassuring branch.
        $shape = if ($null -eq $grouped) { "null" } else { $grouped.GetType().Name }
        Write-Fail ("View list failed: the UI API returned a result of an " +
            "unrecognised shape ($shape, expected an object keyed by view " +
            "type); refusing to treat that as an empty view list")
    }
    return $allViews
}

function Remove-View {
    param([string]$ViewId, [string]$ViewName)
    $tid = Get-NextTid
    # data shape: array containing one dict; viewDefIds is a JSON-stringified
    # array of {id, name} objects. Sending a bare UUID (old shape) crashes the
    # server handler and returns type:exception "Internal server error."
    # See knowledge/context/api-surface/dashboard_delete_api.md section 2026-04-11 update.
    $innerJson = ConvertTo-Json @(@{ id = $ViewId; name = $ViewName }) -Compress
    $result = Invoke-ExtDirect -Calls @(@{
        action = "viewServiceController"
        method = "deleteView"
        data   = @(@{ viewDefIds = $innerJson })
        type   = "rpc"
        tid    = $tid
    })
    # No -Fatal: Uninstall-Views catches this and downgrades it to a per-view
    # warning so one undeletable view does not abandon the rest of the
    # uninstall.  No -RequireResult: the result payload is discarded, and
    # demanding one would invent a failure on a working path (#116).
    $null = Get-ExtDirectResult -Response $result -What "deleteView $ViewId"
}

function Get-AllReports {
    $tid = Get-NextTid
    $result = Invoke-ExtDirect -Calls @(@{
        action = "reportServiceController"
        method = "getReportDefinitionThumbnails"
        data   = @(@{
            contentFilter   = @{ isTenant = $false }
            resourceContext = $null
            page            = 1
            start           = 0
            limit           = 500
            sort            = @(@{ property = "creationTime"; direction = "DESC" })
        })
        type   = "rpc"
        tid    = $tid
    })
    # -RequireResult: same reasoning as Get-AllViews -- this feeds
    # Uninstall-Reports' name->id map (#116).
    $raw = Get-ExtDirectResult -Response $result -What "Report list" -Fatal -RequireResult
    # getReportDefinitionThumbnails returns:
    #   {"records":[...], "total":N, "metaData":{...}, "success":true}
    if ($raw -is [System.Array]) { return $raw }
    foreach ($key in @("records","data","items","reportDefinitions","reports")) {
        # PSObject.Properties probe is StrictMode-safe; dot-notation throws on missing key.
        $keyProp = $raw.PSObject.Properties[$key]
        if ($keyProp) {
            $val = $keyProp.Value
            if ($null -ne $val -and $val -is [System.Array]) { return $val }
        }
    }
    # Fallback: flatten any array properties one level deep
    $items = [System.Collections.Generic.List[object]]::new()
    if ($raw -is [PSCustomObject]) {
        foreach ($prop in $raw.PSObject.Properties) {
            if ($prop.Value -is [System.Array]) {
                foreach ($item in $prop.Value) { $items.Add($item) }
            }
        }
    } else {
        # Same residual-else defect as Get-AllViews, one function over.  A
        # string or bool result reaches here (a bare array already returned
        # above, which is a legitimate shape), and returning the empty $items
        # would make Uninstall-Reports claim "already removed?" about reports
        # that are still there.
        $shape = if ($null -eq $raw) { "null" } else { $raw.GetType().Name }
        Write-Fail ("Report list failed: the UI API returned a result of an " +
            "unrecognised shape ($shape, expected an object or an array); " +
            "refusing to treat that as an empty report list")
    }
    return $items
}

function Remove-Reports {
    param([object[]]$Reports)
    $tid = Get-NextTid
    # data shape: BARE DICT (not array), reportDefIds is a JSON-stringified
    # array of {id, name} objects. This differs from deleteView which wraps
    # data in an array. See knowledge/context/api-surface/dashboard_delete_api.md section 2026-04-11 update.
    $innerJson = ConvertTo-Json @($Reports | ForEach-Object {
        @{ id = $_.Uuid; name = $_.Name }
    }) -Compress
    $result = Invoke-ExtDirect -Calls @(@{
        action = "reportServiceController"
        method = "deleteReportDefinitions"
        data   = @{ reportDefIds = $innerJson }
        type   = "rpc"
        tid    = $tid
    })
    # No -Fatal / no -RequireResult: same reasoning as Remove-View (#116).
    $null = Get-ExtDirectResult -Response $result -What "deleteReportDefinitions"
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
        ContentType    = "builtin_metric_enables"
        ManifestKey    = "builtin_metric_enables"
        InstallLabel   = "Enabling built-in metric(s) on Default Policy..."
        InstallFn      = "Install-BuiltinMetricEnables"
        InstallOrder   = 3.5
        # Uninstall does NOT disable built-in metrics (Default Policy is shared state).
        # The note function prints a reminder without modifying the policy.
        UninstallLabel = "Noting built-in metric(s) enabled by this bundle..."
        UninstallFn    = "Uninstall-BuiltinMetricEnablesNote"
        UninstallOrder = 45
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
        # Uninstall handled by the uninstall-only "reports" entry below.
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
    # Uninstall-only entries for dashboards, reports, and views.
    # Order: dashboards first (10), then reports (15, since reports reference views),
    # then views (20). All require the admin UI session via SPA Ext.Direct.
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
        ContentType    = "reports"
        ManifestKey    = $null
        InstallLabel   = $null
        InstallFn      = $null
        InstallOrder   = $null
        UninstallLabel = "Deleting report definition(s)..."
        UninstallFn    = "Uninstall-Reports"
        UninstallOrder = 15
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
    $importResult = Import-ContentZip -ZipBytes $smZip -Label "super metrics"

    # Ghost-state recovery, ported from install.py:_install_supermetrics.  The
    # drift this closes: the Python installer self-heals here and the
    # PowerShell one did not, so a Windows operator got a clean-looking install
    # whose SMs are readable by id but invisible to list and assign.
    # See Get-SmGhostStateSkipCount for why this is SUPER_METRICS only.
    $ghostSkipped = Get-SmGhostStateSkipCount -Result $importResult
    if ($ghostSkipped -gt 0) {
        Write-Host ("    [ghost-state recovery] all $ghostSkipped SM(s) skipped on first " +
            "import, retrying to re-register in SM catalog...")
        $null = Import-ContentZip -ZipBytes $smZip -Label "super metrics (retry)"
    }

    $smCount = @($smDict.PSObject.Properties.Name).Count
    Write-Ok "Imported $smCount super metric(s)"
}

function Install-Dashboard($Ctx) {
    $dashFile = Join-Path $Ctx.BundleDir $Ctx.Manifest.content.dashboards.file
    $dashJson = Load-RawTextFile $dashFile

    $viewsXml = ""
    $viewsProp = $Ctx.Manifest.content.PSObject.Properties["views"]
    if ($viewsProp -and $viewsProp.Value) {
        $viewsFile = Join-Path $Ctx.BundleDir $viewsProp.Value.file
        if (Test-Path -LiteralPath $viewsFile) { $viewsXml = Load-RawTextFile $viewsFile }
    }

    $dashIds = Get-DashboardIds -DashJson $dashJson -OwnerId $Ctx.OwnerId
    $nViews = if ($viewsXml) { 1 } else { 0 }
    $dashZip = New-DashboardZip -ViewsXml $viewsXml -DashJson $dashJson -Marker $Ctx.Marker `
        -OwnerId $Ctx.OwnerId -NViews $nViews -NDashboards 1 -DashboardIds $dashIds
    $importResult = Import-ContentZip -ZipBytes $dashZip -Label "dashboard + view"

    # A FINISHED import that imported nothing and skipped everything left the
    # instance untouched: the dashboard on screen is still the old one.
    # Previously only the top-level state was consulted, so this was reported
    # as a clean install.
    #
    # Attribution is PER CONTENT TYPE.  This zip always carries two of them,
    # so flagging the dashboard because the co-shipped view was skipped (or
    # vice versa) would be a false statement contradicted by the same
    # envelope.  Each type gets its own line, and the type that imported
    # normally still gets its success line.
    $flagged = Get-AllSkippedSummaries -Result $importResult -ContentTypes @("DASHBOARDS", "VIEW_DEFINITIONS")
    $unchangedTail = (" Verify on the instance; deleting the existing object and " +
        "re-installing is the reliable way to force an update.")

    if ($flagged.ContainsKey("DASHBOARDS")) {
        $counts = $flagged["DASHBOARDS"]
        $dashNames = Get-DashboardAdvisoryNames -DashJson $dashJson -OwnerId $Ctx.OwnerId
        $named = if ($dashNames.Count -gt 0) { $dashNames -join ", " } else { "dashboard" }
        $advisory = ("Import changed no dashboards (DASHBOARDS imported=$($counts.Imported) " +
            "skipped=$($counts.Skipped)); the existing dashboard was NOT updated: " +
            "$named." + $unchangedTail)
        Write-Warn $advisory
        $Ctx.Advisories.Add($advisory)
    } else {
        Write-Ok "Imported 1 dashboard"
    }

    if ($nViews -gt 0) {
        if ($flagged.ContainsKey("VIEW_DEFINITIONS")) {
            $counts = $flagged["VIEW_DEFINITIONS"]
            $viewNames = Get-ViewAdvisoryNames -ViewsXml $viewsXml
            $named = if ($viewNames.Count -gt 0) { $viewNames -join ", " } else { "view(s)" }
            $advisory = ("Import changed no views (VIEW_DEFINITIONS imported=$($counts.Imported) " +
                "skipped=$($counts.Skipped)); the existing views were NOT updated: " +
                "$named." + $unchangedTail)
            Write-Warn $advisory
            $Ctx.Advisories.Add($advisory)
        } else {
            Write-Ok "Imported $nViews view(s)"
        }
    }

    # Deliberately NOT added to $Ctx.Warnings: that list drives exit 2, and
    # this class of finding must not fail an install that genuinely succeeded.
    # Advisories print as a trailer in BOTH summary branches instead, so the
    # operator's last line is never an unqualified "all successful" over a
    # warning saying content was not updated.
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

function Install-BuiltinMetricEnables($Ctx) {
    if ($SkipEnable) {
        Write-Host "  (-SkipEnable set: skipping)"
        return
    }
    $bmeProp = $Ctx.Manifest.content.PSObject.Properties["builtin_metric_enables"]
    if (-not $bmeProp) { return }
    $bmeSection = $bmeProp.Value
    if (-not $bmeSection -or -not $bmeSection.items) { return }
    $items = @($bmeSection.items)
    if ($items.Count -eq 0) { return }

    $entries = [System.Collections.Generic.List[object]]::new()
    foreach ($item in $items) {
        $ak = $item.adapter_kind
        $rk = $item.resource_kind
        $mk = $item.metric_key
        if (-not $ak -or -not $rk -or -not $mk) {
            Write-Warn "Skipping malformed builtin_metric_enables entry: $($item | ConvertTo-Json -Compress)"
            continue
        }
        $entries.Add(@{ adapter_kind = $ak; resource_kind = $rk; metric_key = $mk })
    }
    if ($entries.Count -eq 0) { return }

    $policyId = Get-DefaultPolicyId
    try {
        $alreadyEnabled = Enable-BuiltinMetricsOnDefaultPolicy -Entries @($entries) -PolicyId $policyId
    } catch {
        $warn = "Built-in metric enable failed: $_"
        Write-Warn $warn
        $Ctx.Warnings.Add($warn)
        return
    }

    foreach ($entry in $entries) {
        $mk = $entry.metric_key
        $ak = $entry.adapter_kind
        $rk = $entry.resource_kind
        if ($alreadyEnabled.Contains($mk)) {
            Write-Ok "Already enabled: $ak/$rk $mk"
        } else {
            Write-Ok "Enabled: $ak/$rk $mk"
        }
    }
}

function Uninstall-BuiltinMetricEnablesNote($Ctx) {
    # Built-in metric enables are NOT reversed on uninstall (Default Policy is
    # shared state).  This function prints a note so operators can decide if
    # they want to disable the metrics manually via the UI.
    $bmeProp = $Ctx.Manifest.content.PSObject.Properties["builtin_metric_enables"]
    if (-not $bmeProp) { return }
    $bmeSection = $bmeProp.Value
    if (-not $bmeSection -or -not $bmeSection.items) { return }
    $items = @($bmeSection.items)
    if ($items.Count -eq 0) { return }
    Write-Host "  NOTE: the following built-in metrics were enabled by this bundle and"
    Write-Host "  remain enabled in the Default Policy (policy is shared state):"
    foreach ($item in $items) {
        $ak = $item.adapter_kind
        $rk = $item.resource_kind
        $mk = $item.metric_key
        $reason = $item.reason
        $suffix = if ($reason) { "  # $reason" } else { "" }
        Write-Host "    $ak/$rk $mk$suffix"
    }
    Write-Host "  To disable, edit the Default Policy in the VCF Ops UI."
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
    $null = Import-ContentZip -ZipBytes $reportsZip -Label "reports"
    $nReports = ([regex]::Matches($reportsXml, "<ReportDef ")).Count
    Write-Ok "Imported $nReports report definition(s)"
    # Note: report uninstall (like dashboard and view uninstall) requires the
    # admin UI session via the SPA Ext.Direct path. Run --uninstall as admin.
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
            # Chooses between updating the existing symptom and creating a
            # new one, so an empty-on-error result creates a DUPLICATE by name.
            #
            # Sequence, stated precisely because it is easy to get wrong: on
            # main this loop THREW under StrictMode (both on an error envelope
            # and on a 200 missing the member).  The #109 sweep turned that
            # crash into a silent duplicate-create.  This guard turns it into a
            # refusal.  Net against main it is crash -> sentence; there was
            # never a window where main created duplicates here.
            #
            # BOUNDARY, deliberately left as-is: a 200 carrying
            # "symptomDefinitions": null still falls through to create, exactly
            # as on main.  null and [] both legitimately mean "empty instance",
            # so refusing on either would break first install on a clean box.
            # Only a non-200 is treated as "we do not know".
            Assert-LookupOk -Response $r -What "Symptom lookup for '$name'"
            foreach ($sd in (Get-PropList $r "symptomDefinitions")) {
                if ($null -eq $sd) { continue }
                if ((Get-PropValue $sd "name") -eq $name) { $existing = $sd; break outer }
            }
            $total = Get-PageTotalCount $r
            $page++
        } while (($page * $pageSize) -lt $total)

        if ($existing) {
            $payload | Add-Member -NotePropertyName "id" -NotePropertyValue (Get-PropValue $existing "id") -Force
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
        # An empty-on-error map would make every alert report "could not
        # resolve symptom references", which is a false diagnosis.
        Assert-LookupOk -Response $r -What "Symptom lookup (alert cross-reference)"
        foreach ($sd in (Get-PropList $r "symptomDefinitions")) {
            if ($null -eq $sd) { continue }
            $sdName = Get-PropValue $sd "name"
            $sdId = Get-PropValue $sd "id"
            if ($sdName -and $sdId) { $symptomMap[$sdName] = $sdId }
        }
        $total = Get-PageTotalCount $r
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
            # Chooses between updating the existing alert and creating a new
            # one, so an empty-on-error result creates a DUPLICATE by name.
            # Same sequence and same null-vs-[] boundary as Install-Symptoms
            # above; see the comment there.
            Assert-LookupOk -Response $r -What "Alert lookup for '$name'"
            foreach ($ad in (Get-PropList $r "alertDefinitions")) {
                if ($null -eq $ad) { continue }
                if ((Get-PropValue $ad "name") -eq $name) { $existing = $ad; break outer2 }
            }
            $total = Get-PageTotalCount $r
            $page++
        } while (($page * 1000) -lt $total)

        if ($existing) {
            $wire | Add-Member -NotePropertyName "id" -NotePropertyValue (Get-PropValue $existing "id") -Force
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
        # Absence here is reported to the operator as "already removed?".
        Assert-LookupOk -Response $r -What "Symptom lookup (uninstall)"
        foreach ($sd in (Get-PropList $r "symptomDefinitions")) {
            if ($null -eq $sd) { continue }
            $sdName = Get-PropValue $sd "name"
            $sdId = Get-PropValue $sd "id"
            if ($sdName -and $sdId -and ($names -contains $sdName)) { $symIds[$sdName] = $sdId }
        }
        $total = Get-PageTotalCount $r
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
        # Absence here is reported to the operator as "already removed?".
        Assert-LookupOk -Response $r -What "Alert lookup (uninstall)"
        foreach ($ad in (Get-PropList $r "alertDefinitions")) {
            if ($null -eq $ad) { continue }
            $adName = Get-PropValue $ad "name"
            $adId = Get-PropValue $ad "id"
            if ($adName -and $adId -and ($names -contains $adName)) { $alertIds[$adName] = $adId }
        }
        $total = Get-PageTotalCount $r
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
        # Get-PropValue, not dot-access: these are ConvertFrom-Json objects
        # from the UI API, and a thumbnail missing either member is a
        # PropertyNotFoundException that aborts the uninstall partway (#116).
        $dname = Get-PropValue $d "name"
        $did = Get-PropValue $d "id"
        if ($dname -and $did) { $dashByName[$dname] = $did }
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
    # Build name -> {Id, Name} map (keep Name for the delete shape).
    $viewByName = @{}
    foreach ($v in $allViews) {
        # $v.viewDefinitionKey was the worst of the #116 sites: the if/else
        # exists precisely BECAUSE some thumbnails carry viewDefinitionKey and
        # some carry only id, so under StrictMode the condition itself throws
        # on every view of the second kind -- an uninstall that dies with a
        # raw PropertyNotFoundException before deleting anything.
        $vkey = Get-PropValue $v "viewDefinitionKey"
        $vid = if ($vkey) { $vkey } else { Get-PropValue $v "id" }
        $vname = Get-PropValue $v "name"
        if ($vname -and $vid) { $viewByName[$vname] = @{ Id = $vid; Name = $vname } }
    }
    foreach ($name in $names) {
        $entry = $viewByName[$name]
        if (-not $entry) {
            Write-Warn "View not found (already removed?): $name"
            $Ctx.Warnings.Add("View not found: $name")
            continue
        }
        try {
            Remove-View -ViewId $entry.Id -ViewName $entry.Name
            Write-Ok "Deleted: $name"
        } catch {
            $warn = "View delete failed for '$name': $_"
            Write-Warn $warn
            $Ctx.Warnings.Add($warn)
        }
    }
}

function Uninstall-Reports($Ctx) {
    $names = $Ctx.Names
    $allReports = Get-AllReports
    $reportByName = @{}
    foreach ($r in $allReports) {
        # Get-PropValue: see Uninstall-Dashboards (#116).
        $rname = Get-PropValue $r "name"
        $rid   = Get-PropValue $r "id"
        if ($rname -and $rid) { $reportByName[$rname] = $rid }
    }
    $toDelete = [System.Collections.Generic.List[object]]::new()
    foreach ($name in $names) {
        if ($reportByName.ContainsKey($name)) {
            $toDelete.Add(@{ Uuid = $reportByName[$name]; Name = $name })
        } else {
            Write-Warn "Report not found (already removed?): $name"
            $Ctx.Warnings.Add("Report not found: $name")
        }
    }
    if ($toDelete.Count -gt 0) {
        try {
            Remove-Reports -Reports $toDelete
            foreach ($r in $toDelete) { Write-Ok "Deleted: $($r.Name)" }
        } catch {
            $warn = "Report batch delete failed: $_"
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
    $bname = Get-BundleDisplayName $Bundle

    $active = @($script:ContentRegistry | Where-Object {
        $_.InstallFn -ne $null -and $_.ManifestKey -ne $null -and
        (Test-BundleHasKey -Bundle $Bundle -ManifestKey $_.ManifestKey)
    } | Sort-Object { $_.InstallOrder })

    $warnings = [System.Collections.Generic.List[string]]::new()
    # Advisories are collected separately from warnings: they never affect the
    # exit code.  They are handed to the caller through $GlobalCtx rather than
    # the return value so this function's return shape stays a plain warnings
    # list (a second returned object would be flattened into the same stream).
    $advisories = [System.Collections.Generic.List[string]]::new()
    $ctx = @{
        BundleDir  = $Bundle.Dir
        Manifest   = $manifest
        Marker     = $GlobalCtx.Marker
        OwnerId    = $GlobalCtx.OwnerId
        Warnings   = $warnings
        Advisories = $advisories
        Names      = @()
    }

    foreach ($entry in $active) {
        $Step.Value++
        Write-Step $Step.Value $TotalSteps "[$bname] $($entry.InstallLabel)"
        & $entry.InstallFn $ctx
    }
    # $null -ne, not truthiness: an empty collection is falsy in PowerShell,
    # so a plain "if ($GlobalCtx.Advisories)" would drop every advisory from
    # the first bundle that produced one.
    if ($null -ne $GlobalCtx.Advisories) {
        foreach ($a in $advisories) { $GlobalCtx.Advisories.Add("[$bname] $a") }
    }
    return $warnings
}

function Invoke-UninstallBundle {
    param($Bundle, $GlobalCtx, [ref]$Step, $TotalSteps)
    $manifest = $Bundle.Manifest
    $bname = Get-BundleDisplayName $Bundle

    $active = @($script:ContentRegistry | Where-Object {
        $_.UninstallFn -ne $null -and $_.UninstallOrder -ne $null -and
        (@(Get-BundleUninstallNames -Bundle $Bundle -ContentType $_.ContentType).Count -gt 0)
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
        $names = @(Get-BundleUninstallNames -Bundle $Bundle -ContentType $entry.ContentType)
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
    $ownerId = Get-OwnerId
    Write-Ok "Owner user ID: $ownerId"

    $allAdvisories = [System.Collections.Generic.List[string]]::new()
    $globalCtx = @{
        Marker     = $marker
        OwnerId    = $ownerId
        Advisories = $allAdvisories
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
        Write-Host ""
        Write-Host "NOTE: VCF Operations needs roughly 5 minutes to finish ingesting and"
        Write-Host "configuring imported content. Until that completes:"
        Write-Host "  - Dashboards may render with empty widgets"
        Write-Host "  - View columns may show 'No data'"
        Write-Host "  - Newly enabled super metrics will report no values"
        Write-Host "This is expected. Refresh after ~5 minutes."
        Write-AdvisoryTrailer -Advisories $allAdvisories.ToArray()
        exit 2
    } else {
        if ($allAdvisories.Count -gt 0) {
            # Not "below": the 5-minute NOTE block prints between this line
            # and the advisories, so the list is seven lines away, not
            # immediately under.  The ordering is deliberate (NOTE is
            # boilerplate, the advisory is the delta and must be the last
            # thing the operator reads), so the wording moves.
            Write-Host "Done. No failures, but see the attention list at the end of this output."
        } else {
            Write-Host "Done. All content installed successfully."
        }
        Write-Host ""
        Write-Host "NOTE: VCF Operations needs roughly 5 minutes to finish ingesting and"
        Write-Host "configuring imported content. Until that completes:"
        Write-Host "  - Dashboards may render with empty widgets"
        Write-Host "  - View columns may show 'No data'"
        Write-Host "  - Newly enabled super metrics will report no values"
        Write-Host "This is expected. Refresh after ~5 minutes."
        Write-AdvisoryTrailer -Advisories $allAdvisories.ToArray()
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
                if (@(Get-BundleUninstallNames -Bundle $b -ContentType $e.ContentType).Count -gt 0) {
                    $needUi = $true; break
                }
            }
        }
        if ($needUi) { break }
    }

    # Dashboard, view, and report deletion goes through the UI layer which is
    # locked to the admin account.  The early guard in the entry point catches
    # this when the user is already known; this guard covers the interactive
    # case where the user was entered at the Get-Credentials prompt.
    if ($needUi -and $script:User -ne "admin") {
        Write-Error ("ERROR: Dashboard, view, and report uninstall requires the 'admin' account.`n" +
                     "       VCF Ops locks imported content to admin ownership. Only the`n" +
                     "       admin user's UI session can delete them.`n" +
                     "       Re-run with -User admin (or set `$env:VCFOPS_USER='admin').")
        exit 1
    }

    # Count total steps
    $totalContentSteps = 0
    foreach ($b in $SelectedBundles) {
        $totalContentSteps += @($script:ContentRegistry | Where-Object {
            $_.UninstallFn -ne $null -and $_.UninstallOrder -ne $null -and
            (@(Get-BundleUninstallNames -Bundle $b -ContentType $_.ContentType).Count -gt 0)
        }).Count
    }

    $TOTAL = 1 + $totalContentSteps
    if ($needUi) { $TOTAL += 2 }

    Write-Host ""
    Write-Host "Uninstalling $($SelectedBundles.Count) bundle(s) from $($script:OpsHost)..."
    if ($Force) { Write-Host "(-Force: skipping dependency checks)" }
    Write-Host "Content to remove:"
    foreach ($b in $SelectedBundles) {
        $bname = Get-BundleDisplayName $b
        Write-Host "  Bundle: $bname"
        foreach ($e in $script:ContentRegistry) {
            if ($e.UninstallFn -ne $null -and $e.UninstallOrder -ne $null) {
                $names = @(Get-BundleUninstallNames -Bundle $b -ContentType $e.ContentType)
                if ($names.Count -gt 0) {
                    Write-Host "    $($e.ContentType.Substring(0,1).ToUpper() + $e.ContentType.Substring(1)) ($($names.Count)): $($names -join ', ')"
                }
            }
        }
    }

    $hasAnything = $false
    foreach ($b in $SelectedBundles) {
        foreach ($e in $script:ContentRegistry) {
            if ($e.UninstallFn -ne $null -and @(Get-BundleUninstallNames -Bundle $b -ContentType $e.ContentType).Count -gt 0) {
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

$allBundles = @(Get-Bundles)
if ($allBundles.Count -eq 0) {
    Write-Error "ERROR: No bundles found. Expected bundles\<slug>\bundle.json or a legacy content\ directory."
    exit 1
}

$modeLabel = if ($Uninstall) { "uninstall" } else { "install" }
$selected = @(Select-Bundles -Bundles $allBundles -Mode $modeLabel)
Show-SelectionSummary -SelectedBundles $selected -Mode $modeLabel

# Early admin-guard: if any selected bundle requires the UI session
# (dashboards/views/reports uninstall), check the user before prompting for
# credentials or printing any further output.  When the user is already known
# from -User / VCFOPS_USER, this fires immediately after bundle selection.
# When the user is not yet known (interactive), Invoke-Uninstall enforces it
# a second time after Get-Credentials resolves the interactive value.
if ($Uninstall) {
    $_uiNeeded = $false
    foreach ($_b in $selected) {
        foreach ($_e in $script:ContentRegistry) {
            if ($_e.NeedsUi -and $_e.UninstallFn -ne $null) {
                if (@(Get-BundleUninstallNames -Bundle $_b -ContentType $_e.ContentType).Count -gt 0) {
                    $_uiNeeded = $true; break
                }
            }
        }
        if ($_uiNeeded) { break }
    }
    if ($_uiNeeded -and $script:User -and $script:User -ne "admin") {
        Write-Error ("ERROR: Dashboard, view, and report uninstall requires the 'admin' account.`n" +
                     "       VCF Ops locks imported content to admin ownership. Only the`n" +
                     "       admin user's UI session can delete them.`n" +
                     "       Re-run with -User admin (or set `$env:VCFOPS_USER='admin').")
        exit 1
    }
}

$credMode = if ($Uninstall) { "uninstaller" } else { "installer" }
Get-Credentials -Mode $credMode

# If the interactive SSL prompt in Get-Credentials was declined, promote that
# answer to the real -SkipSslVerify switch (every per-request PS 7+ call site
# reads $SkipSslVerify) and apply the same bypass logic that ran earlier for
# the flag.  This block cannot have run already: the prompt only appears when
# $SkipSslVerify was $false.
if ($script:SslPromptDeclined) {
    Set-Variable -Name SkipSslVerify -Value ([switch]$true) -Scope Script
    Write-Warning "TLS certificate verification disabled."
    Disable-CertificateValidationLegacy
}

$script:BaseUrl = "https://$($script:OpsHost)/suite-api"

if ($Uninstall) {
    Invoke-Uninstall -SelectedBundles $selected
} else {
    Invoke-Install -SelectedBundles $selected
}

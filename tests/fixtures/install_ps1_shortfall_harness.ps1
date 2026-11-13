# Behaviour harness for the install.ps1 import-shortfall check and the
# widget-type floor preflight (issue #199).
#
# Extracts the functions under test verbatim from the real template with the
# PowerShell AST, replays the two script-scope constants they read, stubs the
# Suite API, runs the cases in a JSON scenario file and writes what it
# observed as JSON for tests/test_import_shortfall_and_widget_floor.py to
# compare with the factory functions and install.py.
#
# Usage: <pwsh|powershell> -NoProfile -NonInteractive -ExecutionPolicy Bypass
#        -File <this> <install.ps1> <scenario.json> <out.json>
#
# pwsh 7 on the POSIX hosts; Windows PowerShell 5.1 is proven only by a
# windows-latest run with VCFCF_PS_EXE=powershell.
param(
    [Parameter(Mandatory = $true)][string]$TemplatePath,
    [Parameter(Mandatory = $true)][string]$ScenarioPath,
    [Parameter(Mandatory = $true)][string]$OutPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

trap {
    [Console]::Error.WriteLine("HARNESS ERROR: $($_.Exception.Message)")
    [Console]::Error.WriteLine($_.InvocationInfo.PositionMessage)
    exit 1
}

try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false) } catch { }
if ($PSVersionTable.PSVersion.Major -lt 6) {
    try { Remove-TypeData -TypeName System.Array -ErrorAction Stop } catch { }
}

$errors = $null
$tokens = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($TemplatePath, [ref]$tokens, [ref]$errors)
if ($errors) { throw "install.ps1 has parse errors: $errors" }

$want = @(
    "Write-Ok", "Write-Warn", "Get-PropValue", "Get-PropList", "Get-StatusCode",
    "ConvertFrom-MatJson", "Test-MatMapping", "Get-MatJsonArray",
    "Get-ImportCountFindings", "ConvertTo-WholeCount", "Get-ImportShortfallMessage", "Get-ImportUninterpretableMessage", "Add-ImportShortfalls", "Get-LostImportLines",
    "ConvertTo-VersionTuple", "Compare-VersionTuple", "ConvertFrom-ReleaseName",
    "Format-VersionTuple", "Get-OpsVersion", "Get-DashboardWidgetPairs",
    "Get-ImportCheck", "Invoke-WidgetFloorPreflight",
    "Install-Dashboard", "Install-Supermetrics", "Install-Reports", "Get-SmGhostStateSkipCount",
    "Get-AllSkippedSummaries", "Get-DashboardAdvisoryNames",
    "Get-BoundedNames", "Get-ViewAdvisoryNames", "Get-DashboardIdNames")
$found = New-Object System.Collections.Generic.List[string]
$fns = $ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $true)
foreach ($f in $fns) {
    if ($want -contains $f.Name) {
        Invoke-Expression $f.Extent.Text
        $found.Add($f.Name)
    }
}
foreach ($w in $want) {
    if ($found -notcontains $w) { throw "function $w not found in install.ps1" }
}

# The constants are script-scope assignments; replay them from the template
# rather than restating them here.
$replayed = 0
$assignments = $ast.FindAll({
    param($n) $n -is [System.Management.Automation.Language.AssignmentStatementAst]
}, $true)
foreach ($a in $assignments) {
    $left = $a.Left.Extent.Text
    if ($left -like '$script:WidgetType*' -or $left -like '$script:Shortfall*' -or
        $left -eq '$script:ImportLossSentence' -or $left -eq '$script:VersionUnreadableNote' -or
        $left -like '$script:Advisory*') {
        Invoke-Expression $a.Extent.Text
        $replayed++
    }
}
if ($replayed -ne 8) { throw "expected 8 replayed constants, found $replayed" }

# Write-Fail exits the installer; here it records the message and throws a
# marker the case loop catches, so one run can cover several cases.
$script:Failed = $null
function Write-Fail($msg) { $script:Failed = [string]$msg; throw "WRITE-FAIL" }

$script:StubVersionBody = $null
$script:StubVersionStatus = 200
$script:VersionCalls = 0
function Invoke-Api {
    param([string]$Method, [string]$Path)
    if ($Path -ne "/api/versions/current") { throw "unexpected Invoke-Api $Method $Path" }
    $script:VersionCalls++
    if ($script:StubVersionStatus -ne 200) { return @{ __statusCode = $script:StubVersionStatus; __body = "" } }
    return $script:StubVersionBody
}
$script:StubFiles = @{}
function Load-RawTextFile($Path) { return $script:StubFiles[[string]$Path] }
function Test-Path { param($LiteralPath) return $script:StubFiles.ContainsKey([string]$LiteralPath) }
function Join-Path { param($Path, $ChildPath) return "$Path/$ChildPath" }
$script:StubImportResult = $null
function Get-DashboardIds { param($DashJson, $OwnerId) return @("id1") }
function New-DashboardZip {
    param($ViewsXml, $DashJson, $Marker, $OwnerId, $NViews, $NDashboards, $DashboardIds)
    return [byte[]]@(1, 2)
}
function Import-ContentZip { param($ZipBytes, $Label) return $script:StubImportResult }
function New-SmZip { param($SmDict, $Marker, $OwnerId) return [byte[]]@(1) }
function New-ReportsZip { param($ReportsXml, $Marker, $OwnerId) return [byte[]]@(1) }
function Load-JsonFile($Path) { return ($script:StubFiles[[string]$Path] | ConvertFrom-Json) }

function Get-InfoLines([scriptblock]$Block) {
    $lines = New-Object System.Collections.Generic.List[string]
    foreach ($rec in @(& $Block 6>&1)) { $lines.Add([string]$rec) }
    return ,$lines.ToArray()
}

$scenario = Get-Content -LiteralPath $ScenarioPath -Raw -Encoding UTF8 | ConvertFrom-Json
$results = New-Object System.Collections.Generic.List[object]

foreach ($case in @($scenario.shortfalls)) {
    $out = [System.Collections.Generic.List[object]]::new()
    foreach ($f in (Get-ImportCountFindings -Result $case)) { $out.Add(@($f[0], $f[1], $f[2])) }
    $results.Add([ordered]@{ kind = "shortfall"; result = $out.ToArray() })
}

foreach ($case in @($scenario.lost)) {
    $results.Add([ordered]@{ kind = "lost"; result = (Get-LostImportLines -Lost @([string]$case)) })
}

foreach ($name in @($scenario.release_names)) {
    $v = ConvertFrom-ReleaseName $name
    $results.Add([ordered]@{ kind = "release"; result = $(if ($null -eq $v) { $null } else { @($v) }) })
}

foreach ($case in @($scenario.refusals)) {
    $pairs = Get-DashboardWidgetPairs -DashJson ([string]$case.dash_json)
    $check = Get-ImportCheck -Dashboards $pairs -InstanceVersion ([string]$case.version)
    $results.Add([ordered]@{ kind = "refusal"; result = @($check.Refusal, $check.Warning) })
}

foreach ($case in @($scenario.preflights)) {
    $script:StubFiles = @{ "/b/content/dashboard.json" = [string]$case.dash_json }
    $script:StubVersionStatus = [int]$case.status
    $script:StubVersionBody = [pscustomobject]@{ releaseName = [string]$case.release_name }
    $script:VersionCalls = 0
    $script:Failed = $null
    $bundle = @{ Dir = "/b"; Manifest = [pscustomobject]@{ content = [pscustomobject]@{
        dashboards = [pscustomobject]@{ file = "content/dashboard.json" } } } }
    $lines = @()
    try {
        $lines = Get-InfoLines { Invoke-WidgetFloorPreflight -Bundles @($bundle) }
    } catch {
        if ([string]$_.Exception.Message -ne "WRITE-FAIL") { throw }
    }
    $results.Add([ordered]@{ kind = "preflight"; result = [ordered]@{
        failed = $script:Failed; lines = @($lines); version_calls = $script:VersionCalls } })
}

foreach ($case in @($scenario.installs)) {
    $script:StubFiles = @{ "/b/dash.json" = [string]$case.dash_json }
    $script:StubImportResult = $case.import_result
    $recorded = [System.Collections.Generic.List[object]]::new()
    $ctx = @{
        BundleDir  = "/b"
        Manifest   = ([pscustomobject]@{ content = [pscustomobject]@{
            dashboards = [pscustomobject]@{ file = "dash.json" } } })
        Marker     = "m"
        OwnerId    = "u1"
        Warnings   = [System.Collections.Generic.List[string]]::new()
        Advisories = [System.Collections.Generic.List[string]]::new()
        ImportedDashboards = $recorded
    }
    $lines = Get-InfoLines { Install-Dashboard $ctx }
    $pairs = New-Object System.Collections.Generic.List[object]
    foreach ($p in $recorded) { $pairs.Add(@($p[0], $p[1])) }
    $results.Add([ordered]@{ kind = "install"; result = [ordered]@{
        warnings = @($ctx.Warnings); advisories = @($ctx.Advisories); lines = @($lines)
        recorded = $pairs.ToArray() } })
}

foreach ($case in @($scenario.other_installs)) {
    $script:StubFiles = @{ "/b/sm.json" = '{"i":{"name":"SM"}}'; "/b/reports.xml" = '<Content><ReportDef id="r"/></Content>' }
    $script:StubImportResult = $case.import_result
    $ctx = @{
        BundleDir  = "/b"
        Manifest   = ([pscustomobject]@{ content = [pscustomobject]@{
            supermetrics = [pscustomobject]@{ file = "sm.json" }
            reports      = [pscustomobject]@{ file = "reports.xml" } } })
        Marker     = "m"
        OwnerId    = "u1"
        Warnings   = [System.Collections.Generic.List[string]]::new()
        Advisories = [System.Collections.Generic.List[string]]::new()
    }
    $fn = [string]$case.fn
    $lines = Get-InfoLines { & $fn $ctx }
    $results.Add([ordered]@{ kind = "other"; result = [ordered]@{
        warnings = @($ctx.Warnings); lines = @($lines) } })
}

$json = ConvertTo-Json -InputObject $results.ToArray() -Depth 20
[System.IO.File]::WriteAllText($OutPath, $json, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "HARNESS DONE"

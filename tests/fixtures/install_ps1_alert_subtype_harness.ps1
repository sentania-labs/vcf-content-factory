# Behaviour harness for install.ps1 alert subType handling (issue #282).
#
# Extracts the functions under test verbatim from the real template with the
# PowerShell AST, stubs the REST collaborators, and writes the observed
# results as JSON for tests/test_install_alert_subtype.py to compare against
# the core loader.  No live instance.
#
# Args: template path, cases JSON (list of {"id": ..., "alert": {...}}),
# output JSON path.  Install-Alerts reads alerts.json beside the cases file,
# which the test writes (the case alerts plus symptom-set threshold shapes).
#
# NOTE: passing under pwsh 7 does NOT prove Windows PowerShell 5.1
# compatibility; only a windows-latest runner can prove that.
param(
    [Parameter(Mandatory = $true)][string]$TemplatePath,
    [Parameter(Mandatory = $true)][string]$CasesPath,
    [Parameter(Mandatory = $true)][string]$OutPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$errors = $null
$tokens = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($TemplatePath, [ref]$tokens, [ref]$errors)
if ($errors) { throw "install.ps1 has parse errors" }

$want = @("Write-Ok", "Write-Warn", "Get-PropValue", "Get-PropList",
          "Get-PageTotalCount", "Load-JsonFile", "Get-AlertSubType",
          "ConvertTo-AlertWire", "Install-Alerts")
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

# --- stubs ------------------------------------------------------------------
function Assert-LookupOk { param($Response, [string]$What) }
$script:Posted = New-Object System.Collections.Generic.List[object]
function Invoke-Api {
    param($Method, $Path, $Query, $Body)
    if ($Method -eq "GET" -and $Path -eq "/api/symptomdefinitions") {
        return [pscustomobject]@{
            symptomDefinitions = @([pscustomobject]@{ name = "Sym A"; id = "sym-a" })
            pageInfo = [pscustomobject]@{ totalCount = 1 }
        }
    }
    if ($Method -eq "GET" -and $Path -eq "/api/alertdefinitions") {
        return [pscustomobject]@{ alertDefinitions = @(); pageInfo = [pscustomobject]@{ totalCount = 0 } }
    }
    if ($Method -eq "POST") { $script:Posted.Add($Body); return @{} }
    throw "unexpected Invoke-Api $Method $Path"
}

# --- Get-AlertSubType per case ------------------------------------------------
$cases = Load-JsonFile $CasesPath
$results = [ordered]@{}
foreach ($c in $cases) {
    try {
        $results[[string]$c.id] = @{ ok = $true; value = (Get-AlertSubType $c.alert) }
    } catch {
        $results[[string]$c.id] = @{ ok = $false; error = $_.Exception.Message }
    }
}

# --- Install-Alerts end to end ------------------------------------------------
# The alerts file is the cases' alert payloads, in order; Load-JsonFile reads
# it exactly as the shipped installer would.
$warnings = New-Object System.Collections.Generic.List[string]
$ctx = @{
    BundleDir = (Split-Path -Parent $CasesPath)
    Manifest = [pscustomobject]@{ content = [pscustomobject]@{ alerts = [pscustomobject]@{ file = "alerts.json" } } }
    Warnings = $warnings
}
Install-Alerts $ctx 6>$null

$out = [ordered]@{
    sub_types = $results
    # base-symptom-set is reported as-is (a single SYMPTOM_SET here) so the
    # test can compare threshold handling with install.py.
    posted = @($script:Posted | ForEach-Object {
        @{ name = $_.name; subType = $_.subType; base = $_.states[0]["base-symptom-set"] } })
    warnings = @($warnings)
}
$out | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $OutPath -Encoding UTF8
Write-Host "HARNESS DONE"

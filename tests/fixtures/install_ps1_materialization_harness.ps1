# Behaviour harness for the install.ps1 materialization check (issue #255).
#
# Extracts the functions under test verbatim from the real template with the
# PowerShell AST, stubs the Suite API reads, runs one task described by a JSON
# scenario file, and writes the observed result as JSON for
# tests/test_install_ps1_materialization.py to compare against the core
# classifier (vcfcf_core.dashboards.materialization) and install.py.
#
# Usage: pwsh -NoProfile -File <this> <install.ps1> <scenario.json> <out.json>
#
# NOTE: this runs under whatever PowerShell is on the box (pwsh 7 on the
# factory's POSIX runners).  Passing here does NOT prove Windows PowerShell
# 5.1 compatibility; only a windows-latest runner can prove that.
param(
    [Parameter(Mandatory = $true)][string]$TemplatePath,
    [Parameter(Mandatory = $true)][string]$ScenarioPath,
    [Parameter(Mandatory = $true)][string]$OutPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

trap {
    # Name the failing line: a bare message is useless from a test log.
    [Console]::Error.WriteLine("HARNESS ERROR: $($_.Exception.Message)")
    [Console]::Error.WriteLine($_.InvocationInfo.PositionMessage)
    [Console]::Error.WriteLine($_.ScriptStackTrace)
    exit 1
}

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$errors = $null
$tokens = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($TemplatePath, [ref]$tokens, [ref]$errors)
if ($errors) { throw "install.ps1 has parse errors: $errors" }

$want = @(
    "Write-Ok", "Write-Warn", "Write-Step", "Get-PropValue", "Get-PropList", "Get-StatusCode",
    "Get-MaterializationWait", "Test-MatMapping", "Get-MatMembers", "Get-MatJsonArray",
    "ConvertFrom-DashboardExportZip", "Get-MatPendingResources", "Get-MatPendingKinds",
    "Test-MatIncomplete", "Get-MatClassification", "Complete-MatStatuses",
    "Get-MatQuoted", "Get-MatDescription", "Get-DashboardIdNames",
    "Export-DashboardsZip", "Get-AdapterKindKeys", "Read-MatState",
    "Invoke-MaterializationCheck", "Invoke-MaterializationReport",
    "Write-MaterializationTrailer", "Write-AdvisoryTrailer",
    "Install-Dashboard", "Get-AllSkippedSummaries", "Get-DashboardAdvisoryNames",
    "Get-BoundedNames", "Get-ViewAdvisoryNames", "Invoke-Install")
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

# Script-scope constants are replayed from the template's own AST, never
# restated here, so a drifted constant fails the parity test.
$assignments = $ast.FindAll({
    param($n) $n -is [System.Management.Automation.Language.AssignmentStatementAst]
}, $true)
$replayed = 0
foreach ($a in $assignments) {
    $left = $a.Left.Extent.Text
    if ($left -like '$script:Mat*' -or $left -like '$script:Advisory*') {
        Invoke-Expression $a.Extent.Text
        $replayed++
    }
}
if ($replayed -lt 10) { throw "expected the Mat*/Advisory* constants, replayed $replayed" }

$scenario = Get-Content -LiteralPath $ScenarioPath -Raw -Encoding UTF8 | ConvertFrom-Json

# --- stubs ------------------------------------------------------------------
# The export queue: each item is a zip path (bytes returned) or an object
# {"error": "..."} (thrown, as the real Export-DashboardsZip throws).
$script:ExportQueue = New-Object System.Collections.Generic.List[object]
$script:ExportCalls = 0
$script:KindsCalls = 0
$script:Slept = New-Object System.Collections.Generic.List[int]
$script:StubKinds = $null
$script:StubKindsError = $false

function Load-ExportQueue($Items) {
    $script:ExportQueue.Clear()
    foreach ($i in @($Items)) { $script:ExportQueue.Add($i) }
}

function Export-DashboardsZip {
    $script:ExportCalls++
    $item = $script:ExportQueue[0]
    $script:ExportQueue.RemoveAt(0)
    if ($item -is [string]) { return ,[System.IO.File]::ReadAllBytes($item) }
    throw [string](Get-PropValue $item "error")
}

function Get-AdapterKindKeys {
    $script:KindsCalls++
    if ($script:StubKindsError) { throw "adapterkinds read failed (403)" }
    $set = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::Ordinal)
    foreach ($k in @($script:StubKinds)) { $null = $set.Add([string]$k) }
    return ,$set
}

$sleepFn = { param($s) $script:Slept.Add([int]$s) }

function ConvertTo-Pairs($Wanted) {
    $pairs = New-Object System.Collections.Generic.List[object]
    foreach ($p in @($Wanted)) { $pairs.Add(@([string]$p[0], [string]$p[1])) }
    return ,$pairs
}

function ConvertTo-StatusJson($Statuses) {
    $out = New-Object System.Collections.Generic.List[object]
    foreach ($st in $Statuses) {
        $out.Add([ordered]@{
            id = $st.Id; name = $st.Name; state = $st.State
            pending = @($st.Pending); missing = @($st.Missing); resources = @($st.Resources)
            after = $st.After; kinds_known = $st.KindsKnown
            describe = (Get-MatDescription $st)
        })
    }
    return ,$out.ToArray()
}

function Get-InfoLines([scriptblock]$Block) {
    # Run $Block, returning the Write-Host lines it printed.  The block keeps
    # its own results in script scope so they do not mix with the lines.
    $lines = New-Object System.Collections.Generic.List[string]
    foreach ($rec in @(& $Block 6>&1)) { $lines.Add([string]$rec) }
    return ,$lines.ToArray()
}

$result = $null
switch ($scenario.mode) {
    "classify" {
        $cases = New-Object System.Collections.Generic.List[object]
        foreach ($c in @($scenario.cases)) {
            $wanted = New-Object System.Collections.Specialized.OrderedDictionary ([System.StringComparer]::Ordinal)
            foreach ($p in @($c.wanted)) { $wanted[[string]$p[0]] = [string]$p[1] }
            $kinds = $null
            if (-not $c.kinds_unknown) { $kinds = @($c.kinds) }
            $st = Get-MatClassification -Exported @($c.exported) -Wanted $wanted -InstalledKinds $kinds
            $st = Complete-MatStatuses -Statuses $st -After ([int]$c.after)
            $cases.Add((ConvertTo-StatusJson $st))
        }
        $result = $cases.ToArray()
    }
    "exportzip" {
        $dashes = ConvertFrom-DashboardExportZip -ZipBytes ([System.IO.File]::ReadAllBytes($scenario.good))
        $ids = @($dashes | ForEach-Object { [string](Get-PropValue $_ "id") })
        $err = ""
        try {
            $null = ConvertFrom-DashboardExportZip -ZipBytes ([System.Text.Encoding]::ASCII.GetBytes("not a zip"))
        } catch {
            $err = $_.Exception.Message
        }
        $result = [ordered]@{ ids = $ids; error = $err }
    }
    "wait" {
        $waits = New-Object System.Collections.Generic.List[int]
        foreach ($c in @($scenario.cases)) {
            [System.Environment]::SetEnvironmentVariable("VCFCF_MATERIALIZATION_WAIT_S", [string]$c.env)
            $req = $null
            if ($null -ne $c.req) { $req = [int]$c.req }
            $waits.Add((Get-MaterializationWait $req))
        }
        $result = $waits.ToArray()
    }
    "idnames" {
        $all = New-Object System.Collections.Generic.List[object]
        foreach ($doc in @($scenario.docs)) {
            $pairs = New-Object System.Collections.Generic.List[object]
            foreach ($p in (Get-DashboardIdNames -DashJson ([string]$doc) -OwnerId "u1")) {
                $pairs.Add(@($p[0], $p[1]))
            }
            $all.Add($pairs.ToArray())
        }
        $result = $all.ToArray()
    }
    "check" {
        Load-ExportQueue $scenario.exports
        $script:StubKinds = @($scenario.kinds)
        $script:StubKindsError = [bool]$scenario.kinds_error
        $pairs = ConvertTo-Pairs $scenario.dashboards
        $script:Out = $null
        if ($scenario.fn -eq "report") {
            $req = $null
            if ($null -ne $scenario.requested_wait) { $req = [int]$scenario.requested_wait }
            $skip = [bool]$scenario.skip
            $lines = Get-InfoLines {
                $script:Out = Invoke-MaterializationReport -Dashboards $pairs -Skip:$skip `
                    -RequestedWait $req -SleepFn $sleepFn
            }
            $result = [ordered]@{
                warnings = @($script:Out.Warnings); notes = @($script:Out.Notes)
                lines = $lines; slept = @($script:Slept); export_calls = $script:ExportCalls
                kinds_calls = $script:KindsCalls
            }
        } else {
            $lines = Get-InfoLines {
                $script:Out = Invoke-MaterializationCheck -Dashboards $pairs `
                    -WaitSeconds ([int]$scenario.wait) -SleepFn $sleepFn
            }
            $result = [ordered]@{
                statuses = (ConvertTo-StatusJson $script:Out); lines = $lines
                slept = @($script:Slept); export_calls = $script:ExportCalls
                kinds_calls = $script:KindsCalls
            }
        }
    }
    "client" {
        # The two real Suite API readers, against a stubbed Invoke-Api.  Their
        # harness stubs above are replaced by the template's own definitions.
        foreach ($f in $fns) {
            if ($f.Name -eq "Export-DashboardsZip" -or $f.Name -eq "Get-AdapterKindKeys") {
                Invoke-Expression $f.Extent.Text
            }
        }
        $script:Calls = New-Object System.Collections.Generic.List[string]
        $script:ExportPolls = 0
        $script:BaseUrl = "https://ops.example.test/suite-api"
        $script:Token = "t"
        $SkipSslVerify = $false
        function Invoke-Api {
            param([string]$Method, [string]$Path, [hashtable]$Headers = @{}, [object]$Body = $null, [hashtable]$Query = @{})
            $script:Calls.Add("$Method $Path")
            if ($Path -eq "/api/adapterkinds") {
                if ($scenario.kinds_status -ne 200) { return @{ __statusCode = [int]$scenario.kinds_status; __body = "no" } }
                return ('{"adapter-kind":[{"key":"VMWARE"},{"name":"no key"},{"key":"mpb_rubrik"}]}' | ConvertFrom-Json)
            }
            if ($Method -eq "POST") {
                if ($scenario.post_status -ne 200) { return @{ __statusCode = [int]$scenario.post_status; __body = ("x" * 400) } }
                $script:Posted = $Body
                return ('{}' | ConvertFrom-Json)
            }
            $script:ExportPolls++
            if ($script:ExportPolls -le 2) { return ('{"state":"FINISHED","startTime":100}' | ConvertFrom-Json) }
            return ('{"state":"FINISHED","startTime":200}' | ConvertFrom-Json)
        }
        function Invoke-WebRequest {
            param($Uri, $Method, $Headers, [switch]$UseBasicParsing, [switch]$SkipCertificateCheck, $OutFile)
            $script:Calls.Add("DOWNLOAD $Uri basic=$UseBasicParsing")
            [System.IO.File]::WriteAllBytes($OutFile, [byte[]](80, 75, 9))
        }
        $kinds = $null; $kindsErr = ""
        try { $kinds = Get-AdapterKindKeys } catch { $kindsErr = $_.Exception.Message }
        $kindsType = ""
        if ($null -ne $kinds) { $kindsType = $kinds.GetType().Name }
        $bytes = $null; $exportErr = ""; $posted = ""
        try {
            $bytes = Export-DashboardsZip -TimeoutSeconds 5
            $posted = ($script:Posted | ConvertTo-Json -Compress)
        } catch { $exportErr = $_.Exception.Message }
        $kindsOut = @()
        if ($null -ne $kinds) {
            $kindsOut = New-Object string[] $kinds.Count
            $kinds.CopyTo($kindsOut)
            [System.Array]::Sort($kindsOut, [System.StringComparer]::Ordinal)
        }
        $bytesOut = @()
        if ($null -ne $bytes) { $bytesOut = @($bytes | ForEach-Object { [int]$_ }) }
        $result = [ordered]@{
            kinds = $kindsOut; kinds_type = $kindsType; kinds_error = $kindsErr; bytes = $bytesOut
            export_error = $exportErr; posted = $posted; calls = $script:Calls.ToArray()
        }
    }
    "dashboard" {
        # Install-Dashboard records only what the import changed.
        $script:StubImportResult = $scenario.import_result
        function Load-RawTextFile($Path) { return [string]$scenario.dash_json }
        function Get-DashboardIds { param($DashJson, $OwnerId) return @("id1") }
        function New-DashboardZip {
            param($ViewsXml, $DashJson, $Marker, $OwnerId, $NViews, $NDashboards, $DashboardIds)
            return [byte[]]@(1, 2)
        }
        function Import-ContentZip { param($ZipBytes, $Label) return $script:StubImportResult }
        function Join-Path { param($Path, $ChildPath) return $ChildPath }
        $recorded = [System.Collections.Generic.List[object]]::new()
        $ctx = @{
            BundleDir  = "/b"
            Manifest   = ([pscustomobject]@{ content = [pscustomobject]@{
                dashboards = [pscustomobject]@{ file = "/b/dash.json" } } })
            Marker     = "m"
            OwnerId    = "u1"
            Warnings   = [System.Collections.Generic.List[string]]::new()
            Advisories = [System.Collections.Generic.List[string]]::new()
            Names      = @()
            ImportedDashboards = $recorded
        }
        $null = Get-InfoLines { Install-Dashboard $ctx }
        $pairs = New-Object System.Collections.Generic.List[object]
        foreach ($p in $recorded) { $pairs.Add(@($p[0], $p[1])) }
        $result = [ordered]@{ recorded = $pairs.ToArray(); warnings = $ctx.Warnings.Count }
    }
    "install" {
        # Invoke-Install end to end with every Suite API step stubbed.  It ends
        # in "exit 2" when a warning (STALLED) is present, so the out file is
        # written BEFORE it runs and the exit code is the observable.
        Load-ExportQueue $scenario.exports
        $script:StubKinds = @($scenario.kinds)
        $script:ContentRegistry = @()
        $script:OpsHost = "ops.example.test"; $script:User = "admin"; $script:AuthSource = "local"
        $SkipMaterializationCheck = [switch][bool]$scenario.skip
        $MaterializationWait = [Nullable[int]]0
        function Authenticate { }
        function Get-MarkerFilename { return "1L.v1" }
        function Get-OwnerId { return "u1" }
        function Invoke-InstallBundle {
            param($Bundle, $GlobalCtx, [ref]$Step, $TotalSteps)
            foreach ($p in @($scenario.dashboards)) {
                $GlobalCtx.ImportedDashboards.Add(@([string]$p[0], [string]$p[1]))
            }
            foreach ($a in @($scenario.advisories)) { $GlobalCtx.Advisories.Add([string]$a) }
            $w = [System.Collections.Generic.List[string]]::new()
            foreach ($x in @($scenario.warnings)) { $w.Add([string]$x) }
            return $w
        }
        Set-Content -LiteralPath $OutPath -Value '{"started": true}' -Encoding UTF8
        Invoke-Install -SelectedBundles @(@{ Dir = "/b"; Manifest = $null; Name = "b" })
        exit 0
    }
    default { throw "unknown mode $($scenario.mode)" }
}

$json = ConvertTo-Json -InputObject $result -Depth 20
[System.IO.File]::WriteAllText($OutPath, $json, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "HARNESS DONE"

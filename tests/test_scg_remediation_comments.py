"""SCG normalizer: PowerShell comments in a multi-line remediation (#254).

collapse_remediation joins a vendor's multi-line PowerCLI script into one
line. A "#" comment line, or a trailing "# ..." on a statement, used to
comment out everything after it on the joined line, so the
vm.virtual-hardware recommendation ran nothing. Comments now become
inline <# ... #> block comments, which keep the vendor's guidance and
still paste and run. The fixture is the real
vm-9.virtual-hardware row of the SCG 9.0 source CSV (the 9.1 row carries
the same remediation cell; the 8.0 guest-8 row differs only in the last
appliance list line of the comment).
"""
from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import _compliance_normalize as base  # noqa: E402
import normalize_scg_v9 as v9  # noqa: E402

# vmware_scg_9.0.csv, SCG ID vm-9.virtual-hardware, verbatim.
_VM_VIRTUAL_HARDWARE_ROW = {
    "SCG ID": "vm-9.virtual-hardware",
    "Component\nName": "ESX",
    "Implementation\nPriority": "N/A",
    "Description/Title": (
        "The guest OS must ensure that virtual machine hardware is version "
        "17 or newer where supported."),
    "Discussion": (
        "Virtual hardware 17 is compatible with ESX 7.0 and later. Newer "
        "versions of virtual hardware enable new features and better "
        "performance. Consider upgrading to VM Hardware 22 if you are fully "
        "updated to VCF 9. Other VMware guidance urges caution when "
        "upgrading; we urge testing of the process. Snapshots capture the "
        "virtual hardware version, making testing and rollback easy.\n\n"
        "Consider all locations that a virtual machine might run, or need to "
        "be restored to.\n\nChanges to the configuration of VMware-supplied "
        "virtual appliances are not supported and may cause service "
        "disruptions."),
    "Configuration Parameter": "N/A",
    "Baseline Suggested Value": "vmx-17 or higher",
    "Setting Location": "VM Compatibility",
    "PowerCLI Command Assessment": (
        "Get-VM -Name $VM | Select-Object Name, HardwareVersion, "
        "@{N='BelowFloor';E={[int]($_.HardwareVersion -replace 'vmx-','') "
        "-lt 17}}"),
    "PowerCLI Command Remediation": (
        "# Upgrade the VM to the latest hardware version its host supports "
        "(the current maximum), via a\n"
        "# VirtualMachineConfigSpec reconfigure. First verify every "
        "environment the VM may run in (DR,\n"
        "# secondary, standby) supports that version. Snapshot first; do not "
        "run against VMware-supplied\n"
        "# appliances (vCenter, NSX, Operations).\n"
        "$vmObj = Get-VM -Name $VM\n"
        "$eb = Get-View (Get-View $vmObj.VMHost.ExtensionData.Parent)"
        ".EnvironmentBrowser\n"
        "$max = ($eb.QueryConfigOptionDescriptor() | Sort-Object "
        "{ [int]($_.Key -replace 'vmx-','') })[-1].Key\n"
        "$spec = New-Object VMware.Vim.VirtualMachineConfigSpec\n"
        "$spec.Version = $max   # to pin a lower version for a DR-constrained "
        "VM, set e.g. \"vmx-19\"\n"
        "$vmObj.ExtensionData.ReconfigVM_Task($spec)"),
}

# Codex's PR #268 example, and a nested string with a "#" in it.
_CODEX_SUBEXPRESSION = 'Write-Output "Values: $($items -join ", # ")"'
_NESTED_SUBEXPRESSION = '"a $("b # c") d"'

# The vendor's guidance stays, as inline block comments, and the
# reconfigure call is code again.
_VM_VIRTUAL_HARDWARE_WANT = (
    "<# Upgrade the VM to the latest hardware version its host supports "
    "(the current maximum), via a VirtualMachineConfigSpec reconfigure. "
    "First verify every environment the VM may run in (DR, secondary, "
    "standby) supports that version. Snapshot first; do not run against "
    "VMware-supplied appliances (vCenter, NSX, Operations). #> "
    "$vmObj = Get-VM -Name $VM ; "
    "$eb = Get-View (Get-View $vmObj.VMHost.ExtensionData.Parent)"
    ".EnvironmentBrowser ; "
    "$max = ($eb.QueryConfigOptionDescriptor() | Sort-Object "
    "{ [int]($_.Key -replace 'vmx-','') })[-1].Key ; "
    "$spec = New-Object VMware.Vim.VirtualMachineConfigSpec ; "
    "$spec.Version = $max <# to pin a lower version for a DR-constrained "
    "VM, set e.g. \"vmx-19\" #> ; "
    "$vmObj.ExtensionData.ReconfigVM_Task($spec)"
)


def test_vm_virtual_hardware_row_end_to_end(tmp_path):
    src, out = tmp_path / "s.csv", tmp_path / "o.csv"
    with open(src, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(_VM_VIRTUAL_HARDWARE_ROW))
        w.writeheader()
        w.writerow(_VM_VIRTUAL_HARDWARE_ROW)
    assert v9.normalize(str(src), str(out)) == 0
    with open(out, encoding="utf-8", newline="") as f:
        (row,) = list(csv.DictReader(f))
    assert row["control_id"] == "vm.virtual-hardware"
    rem = row["remediation_text"]
    assert rem == _VM_VIRTUAL_HARDWARE_WANT
    assert not rem.startswith("#")
    # The reconfigure call is no longer behind a comment.
    assert rem.endswith("; $vmObj.ExtensionData.ReconfigVM_Task($spec)")


@pytest.mark.parametrize("raw,want", [
    # No "#": collapsed as before, blank lines included.
    ("Set-A\n\nSet-B\r\n", "Set-A ; ; Set-B ;"),
    ("", ""),
    # A trailing comment would swallow the next statement once joined.
    ('$a.level = "PartnerSupported" # VMwareCertified, ...\n$a.Invoke()',
     '$a.level = "PartnerSupported" <# VMwareCertified, ... #> ; $a.Invoke()'),
    # "#" inside a string, or not at a token start, is not a comment.
    ('Set-VDVlanConfiguration -VlanId "<New VLAN#>"',
     'Set-VDVlanConfiguration -VlanId "<New VLAN#>"'),
    ("Write-Host 'a # b' # note\nNext", "Write-Host 'a # b' <# note #> ; Next"),
    # Prose comment then a URL (esx.updates, 6.7): never a bare URL.
    ("# See sample scripts here:\n\nhttps://x/guide?h=a#/doc/GUID",
     "<# See sample scripts here: #> https://x/guide?h=a#/doc/GUID"),
    # A string spanning lines carries its quote state to the next line.
    ('$s = "one\n# two"\nNext', '$s = "one ; # two" ; Next'),
    # A run of comment lines becomes one block in front of the next code
    # line; blank lines around it leave no empty segment.
    ("A\n\n#Function\n#From: x\n\nB", "A ; <# Function From: x #> B"),
    # Comments after the last code line are appended to it.
    ("A\n# done", "A <# done #>"),
    # "#>" in comment text would close the block early.
    ("A # x #> y", "A <# x # > y #>"),
    # A "#" right after ; { ( | starts a comment too.
    ("Set-A;# c\nSet-B", "Set-A; <# c #> ; Set-B"),
    ("Get-X | ForEach {# c\n$_ }", "Get-X | ForEach { <# c #> $_ }"),
    ("Invoke-It (# c\n$a)", "Invoke-It ( <# c #> $a)"),
    ("Get-X |# c\nSet-Y", "Get-X | <# c #> Set-Y"),
    # "#" + digit mid-sentence is prose, not a comment; at line start it is.
    ("Configure item #3 in the UI\nNext", "Configure item #3 in the UI ; Next"),
    ("#3 retries\nSet-A", "<# 3 retries #> Set-A"),
    # "#requires" is a comment like any other.
    ("#requires -Version 5\nSet-A", "<# requires -Version 5 #> Set-A"),
    # Nothing but comments (a commented-out vendor example): kept as is
    # rather than emptied.
    ("# Get-VMHostService | Set-VMHostService -Policy Off\n"
     "# Get-VMHostService | Stop-VMHostService",
     "# Get-VMHostService | Set-VMHostService -Policy Off ; "
     "# Get-VMHostService | Stop-VMHostService"),
])
def test_collapse_remediation(raw, want):
    assert base.collapse_remediation(raw) == want


@pytest.mark.parametrize("raw,want", [
    # No ";" into an open block, call, pipeline, list or continuation ...
    ("foreach ($h in $hosts)\n  {\n$a\n}", "foreach ($h in $hosts) { $a }"),
    ("Function F {\n [CmdletBinding()]\n Param (\n  $D\n )\n}",
     "Function F { [CmdletBinding()] Param ( $D ) }"),
    ("Get-X |\n Set-Y `\n -Z 1", "Get-X | Set-Y -Z 1"),
    ("$a = 1,\n2", "$a = 1, 2"),
    # ... nor before a clause that belongs to the line before.
    ("if ($a) {\n1\n}\nelse {\n2\n}", "if ($a) { 1 } else { 2 }"),
    ("try {\nA\n}\ncatch {\nB\n}", "try { A } catch { B }"),
    # An indexed expression is not an attribute line.
    ("$x = $a[0]\nSet-B", "$x = $a[0] ; Set-B"),
    # The join reads the code, not the block comments around it.
    ("foreach ($x in $y)\n# loop body\n{\n$a\n}",
     "foreach ($x in $y) <# loop body #> { $a }"),
])
def test_join_keeps_blocks_whole(raw, want):
    assert base.collapse_remediation(raw) == want


@pytest.mark.parametrize("raw", [
    "<# block #> Set-A\n# c\nSet-B",
    '$x = @"\nHe said "hi\n# x\n"@\nSet-B',
    "$x = @'\n# x\n'@\nSet-B",
    "Write-Host “a # b”\nSet-B",
    "Write-Host ‘a # b’\nSet-B",
    # A $( ) subexpression inside a double-quoted string can hold its own
    # strings, which a flat quote state misreads (Codex, PR #268).
    _CODEX_SUBEXPRESSION,
    _NESTED_SUBEXPRESSION,
    'Write-Output "x $(\nGet-Y # c\n)"\nSet-B',
])
def test_unmodeled_constructs_left_unchanged_and_logged(raw, capsys):
    got = base.collapse_remediation(raw, "esx.example")
    assert got == base._collapse_remediation_legacy(raw)
    err = capsys.readouterr().err
    assert "esx.example" in err and "WARNING" in err


@pytest.mark.parametrize("raw", [_CODEX_SUBEXPRESSION, _NESTED_SUBEXPRESSION])
def test_subexpression_strings_come_out_unchanged(raw):
    assert base.collapse_remediation(raw, "esx.example") == raw


def test_subexpression_outside_a_string_is_still_modeled():
    assert base.collapse_remediation("$n = $(Get-X) # count\nSet-B") == \
        "$n = $(Get-X) <# count #> ; Set-B"


@pytest.mark.skipif(shutil.which("pwsh") is None,
                    reason="PowerShell not installed")
@pytest.mark.parametrize("raw", [_CODEX_SUBEXPRESSION, _NESTED_SUBEXPRESSION])
def test_subexpression_strings_still_parse(raw, tmp_path):
    _assert_pwsh_parses(
        tmp_path, [{"key": "case", "text": base.collapse_remediation(raw)}])


# --- PowerShell parse check --------------------------------------------------
#
# Every remediation the change rewrites must still parse as PowerShell.
# Runs when pwsh is installed. The fixtures above always take part; the
# vendor SCG CSVs take part when present (they live in the gitignored
# compliance adapter repo: content/sdk-adapters/compliance/profiles/, or
# the directory named by VCFCF_COMPLIANCE_PROFILES).

_PWSH = shutil.which("pwsh")

_PARSE_PS = r"""
$items = Get-Content -Raw -LiteralPath $args[0] -Encoding UTF8 | ConvertFrom-Json
foreach ($it in $items) {
  $t = $null; $e = $null
  [void][System.Management.Automation.Language.Parser]::ParseInput($it.text, [ref]$t, [ref]$e)
  if ($e.Count) { "$($it.key)`t$($e[0].Message -replace '\s+', ' ')" }
}
"""

# Vendor text that does not parse whatever the join does: SCG 6.7
# ESXi.config-ntp lost a newline ('"pool2.ntp.org"Get-VMHost').
_VENDOR_DEFECTS = {"ESXi.config-ntp"}


def _profiles_dir():
    env = os.environ.get("VCFCF_COMPLIANCE_PROFILES")
    if env:
        return Path(env)
    return (Path(__file__).resolve().parents[1] / "content" / "sdk-adapters"
            / "compliance" / "profiles")


def _vendor_remediations():
    d = _profiles_dir()
    if not d.is_dir():
        return
    for f in sorted(d.glob("vmware_scg_*.csv")):
        with open(f, encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            names = reader.fieldnames or []
            cols = [c for c in names
                    if c.startswith("PowerCLI Command Remediation")]
            idc = "SCG ID" if "SCG ID" in names else "Guideline ID"
            for row in reader:
                for c in cols:
                    yield f"{f.name}:{row[idc]}", row[c] or ""


@pytest.mark.skipif(_PWSH is None, reason="PowerShell not installed")
def test_rewritten_remediations_parse(tmp_path):
    cases = [("fixture:vm-9.virtual-hardware",
              _VM_VIRTUAL_HARDWARE_ROW["PowerCLI Command Remediation"])]
    cases += list(_vendor_remediations())
    items = []
    for key, raw in cases:
        new = base.collapse_remediation(raw, key)
        if new != base._collapse_remediation_legacy(raw) and \
                key.split(":", 1)[1] not in _VENDOR_DEFECTS:
            items.append({"key": key, "text": new})
    assert items
    _assert_pwsh_parses(tmp_path, items)


def _assert_pwsh_parses(tmp_path, items):
    """Fail if pwsh's ParseInput reports an error for any item's text."""
    data, script = tmp_path / "items.json", tmp_path / "parse.ps1"
    data.write_text(json.dumps(items), encoding="utf-8")
    script.write_text(_PARSE_PS, encoding="utf-8")
    res = subprocess.run(
        [_PWSH, "-NoProfile", "-NonInteractive", "-File", str(script),
         str(data)], capture_output=True, text=True, timeout=300)
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == "", f"parse errors:\n{res.stdout}"

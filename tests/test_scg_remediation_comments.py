"""SCG normalizer: PowerShell comments in a multi-line remediation (#254).

collapse_remediation joins a vendor's multi-line PowerCLI script with
" ; ". A "#" comment line, or a trailing "# ..." on a statement, then
comments out everything after it on the one joined line, so the
vm.virtual-hardware recommendation ran nothing. The fixture is the real
vm-9.virtual-hardware row of the SCG 9.0 source CSV (the 9.1 row carries
the same remediation cell; the 8.0 guest-8 row differs only in the last
appliance list line of the comment).
"""
from __future__ import annotations

import csv
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

# What the compliance repo's build-98 workaround (_adapter_deltas.py)
# already writes into the 8.0/9.0/9.1 canonicals: the factory output must
# match it, so landing #254 changes no vm.virtual-hardware canonical row.
_VM_VIRTUAL_HARDWARE_WANT = (
    "$vmObj = Get-VM -Name $VM ; "
    "$eb = Get-View (Get-View $vmObj.VMHost.ExtensionData.Parent)"
    ".EnvironmentBrowser ; "
    "$max = ($eb.QueryConfigOptionDescriptor() | Sort-Object "
    "{ [int]($_.Key -replace 'vmx-','') })[-1].Key ; "
    "$spec = New-Object VMware.Vim.VirtualMachineConfigSpec ; "
    "$spec.Version = $max ; "
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
    assert "#" not in rem
    # The reconfigure call is no longer behind a comment.
    assert rem.endswith("$vmObj.ExtensionData.ReconfigVM_Task($spec)")


@pytest.mark.parametrize("raw,want", [
    # No "#": collapsed exactly as before, blank lines included.
    ("Set-A\n\nSet-B\r\n", "Set-A ; ; Set-B ;"),
    ("", ""),
    # Trailing comment would swallow the next statement once joined.
    ('$a.level = "PartnerSupported" # VMwareCertified, ...\n$a.Invoke()',
     '$a.level = "PartnerSupported" ; $a.Invoke()'),
    # "#" inside a string, or not at a token start, is not a comment.
    ('Set-VDVlanConfiguration -VlanId "<New VLAN#>"',
     'Set-VDVlanConfiguration -VlanId "<New VLAN#>"'),
    ("# see\nhttps://x/guide?h=a#/doc/GUID", "https://x/guide?h=a#/doc/GUID"),
    ("Write-Host 'a # b' # note\nNext", "Write-Host 'a # b' ; Next"),
    # A string spanning lines carries its quote state to the next line.
    ('$s = "one\n# two"\nNext', '$s = "one ; # two" ; Next'),
    # Comment lines and the blank lines around them leave no empty segment.
    ("A\n\n#Function\n#From: x\n\nB", "A ; B"),
    # Nothing but comments (a commented-out vendor example): kept as is
    # rather than emptied.
    ("# Get-VMHostService | Set-VMHostService -Policy Off\n"
     "# Get-VMHostService | Stop-VMHostService",
     "# Get-VMHostService | Set-VMHostService -Policy Off ; "
     "# Get-VMHostService | Stop-VMHostService"),
])
def test_collapse_remediation(raw, want):
    assert base.collapse_remediation(raw) == want

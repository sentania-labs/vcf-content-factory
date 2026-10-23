"""SCG profile normalizers: scoring fix-ups keyed by control_id (#169).

scripts/normalize_scg_v8.py and normalize_scg_v9.py are thin wrappers over
_compliance_normalize.normalize_scg_source. Every scoring fix-up is keyed
by the version-independent control_id (or control_id plus source product),
so a new SCG version gets them without per-version code. The fixtures are
synthetic rows in each version's header layout; a hypothetical
``vcenter-10`` row stands in for a future SCG version.

The compliance adapter repo's drivers patch module attributes of these
scripts before calling normalize() (SCG 7.0 sets v8.SOURCE_TOKEN; SCG 9.1
sets v9.COL_* / REQUIRED_COLUMNS / SOURCE_TOKEN / classify_parameter_kind),
so that contract is pinned here too.
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
import normalize_scg_v8 as v8  # noqa: E402
import normalize_scg_v9 as v9  # noqa: E402


# (SCG ID, component, setting location, baseline, assessment)
_ROWS = [
    ("esxi-{v}.network-vgt", "ESX", "ESXi Port Group Configuration",
     "Not VLAN 4095", "Get-VMHost | Get-VirtualPortGroup -Standard"),
    ("vcenter-{v}.network-vgt", "VC", "Distributed Switch Port Group Settings",
     "Not Configured", "Get-VDPortgroup -Name $VDPG"),
    ("vcenter-10.network-vgt", "VC", "Distributed Switch Port Group Settings",
     "Not Configured", "Get-VDPortgroup -Name $VDPG"),
    ("vcenter-{v}.network-restrict-discovery-protocol", "VC",
     "Distributed Switch Settings", "Deactivated", "Get-VDSwitch"),
    ("guest-{v}.vmrc-lock", "ESX", "VM Advanced Settings",
     "Undefined (Defaults to TRUE)", "Get-AdvancedSetting -Name RemoteDisplay.maxConnections"),
    ("guest-{v}.log-retention", "ESX", "VM Advanced Settings",
     "Undefined (Defaults to 10)\nsecond line", "Get-AdvancedSetting"),
]

_V8_COMPONENT = {"ESX": "VMware ESXi", "VC": "VMware vCenter"}
_V9_COMPONENT = {"ESX": "ESX", "VC": "vCenter"}


def _write_source(path: Path, layout: str, version: str) -> None:
    if layout == "v8":
        header = ["SCG ID", "Component", "Implementation Priority",
                  "Description/Title", "Discussion", "Configuration Parameter",
                  "Baseline Suggested Value", "Setting Location",
                  "PowerCLI Command Assessment",
                  "PowerCLI Command Remediation Example"]
        comp = _V8_COMPONENT
    else:
        comp_col = "Component\nName" if layout == "v9" else "Component Name"
        prio_col = "Implementation\nPriority" if layout == "v9" else "Implementation Priority"
        header = ["SCG ID", comp_col, prio_col, "Description/Title",
                  "Discussion", "Configuration Parameter",
                  "Baseline Suggested Value", "Setting Location",
                  "PowerCLI Command Assessment",
                  "PowerCLI Command Remediation"]
        comp = _V9_COMPONENT
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for sid, c, loc, baseline, assess in _ROWS:
            w.writerow([sid.format(v=version), comp[c], "P1", "Title",
                        "Discussion.", "N/A", baseline, loc, assess, "Set-It"])


def _rows(path: Path):
    with open(path, encoding="utf-8", newline="") as f:
        return {r["source_ref"].split(":", 1)[1]: r for r in csv.DictReader(f)}


@pytest.fixture(params=[("v8", "8", v8), ("v9", "9", v9)], ids=["scg8", "scg9"])
def normalized(request, tmp_path):
    layout, version, mod = request.param
    src = tmp_path / "src.csv"
    out = tmp_path / "out.csv"
    _write_source(src, layout, version)
    assert mod.normalize(str(src), str(out)) == 0
    return version, _rows(out)


# --- source product + control_id-scoped VGT rule -----------------------------

@pytest.mark.parametrize("sid,product", [
    ("vcenter-8.network-vgt", "vc"),
    ("vcenter-10.network-vgt", "vc"),
    ("esxi-8.network-vgt", "esx"),
    ("esx-9.network-vgt", "esx"),
    ("ESXi.set-account-lockout", ""),   # SCG 6.7 Guideline ID shape
    ("", ""),
])
def test_source_product(sid, product):
    assert base.source_product(sid) == product


def test_vgt_promoted_for_vcenter_rows_of_any_version(normalized):
    version, rows = normalized
    for sid in (f"vcenter-{version}.network-vgt", "vcenter-10.network-vgt"):
        r = rows[sid]
        assert r["control_id"] == "dvpg.network-vgt"
        assert r["parameter_kind"] == "vim_property"
        assert r["read_recipe"] == "vlan_id_not:config.defaultPortConfig.vlan"
        assert r["expected_value"] == "true"


def test_vgt_not_promoted_for_esx_standard_switch_row(normalized):
    version, rows = normalized
    r = rows[f"esxi-{version}.network-vgt"]
    assert r["control_id"] == "dvpg.network-vgt"
    assert r["parameter_kind"] != "vim_property"
    assert r["read_recipe"] == ""
    assert r["expected_value"] == "Not VLAN 4095"


# --- expected-value fix-ups ----------------------------------------------------

def test_discovery_protocol_expected_pinned_to_enum(normalized):
    version, rows = normalized
    r = rows[f"vcenter-{version}.network-restrict-discovery-protocol"]
    assert r["control_id"] == "vds.network-restrict-discovery-protocol"
    assert r["expected_value"] == "none"


def test_undefined_defaults_rewritten(normalized):
    version, rows = normalized
    assert rows[f"guest-{version}.vmrc-lock"]["expected_value"] == "TRUE or Undefined"


def test_multiline_undefined_cell_keeps_previous_behaviour(normalized):
    # Whole-cell match only, as the SCG 7.0 driver did: a multi-line cell
    # falls through to the first-line collapse unchanged.
    version, rows = normalized
    assert rows[f"guest-{version}.log-retention"]["expected_value"] == (
        "Undefined (Defaults to 10)")


@pytest.mark.parametrize("raw,want", [
    ("Undefined (Defaults to TRUE)", "TRUE or Undefined"),
    ("  undefined ( defaults to 2048000 )  ", "2048000 or Undefined"),
    ("TRUE or Undefined", "TRUE or Undefined"),
    ("Undefined", "Undefined"),
    ("", ""),
])
def test_rewrite_undefined_baseline(raw, want):
    assert base.rewrite_undefined_baseline(raw) == want


def test_reset_port_recipe_present_for_portgroup_control_id():
    got = base.classify_vim_reclass("dvpg.network-reset-port")
    assert got == base.classify_vim_reclass("vds.network-reset-port")
    assert got[1] == "bool:config.policy.portConfigResetAtDisconnect"


# --- the compliance repo's driver contract -----------------------------------

def test_v9_honours_patched_columns_token_and_classifier(tmp_path, monkeypatch):
    """The SCG 9.1 driver's patch sequence, against the thin wrapper."""
    monkeypatch.setattr(v9, "COL_COMPONENT", "Component Name")
    monkeypatch.setattr(v9, "COL_PRIORITY", "Implementation Priority")
    monkeypatch.setattr(v9, "REQUIRED_COLUMNS", [
        v9.COL_SCG_ID, "Component Name", "Implementation Priority",
        v9.COL_TITLE, v9.COL_DESCRIPTION, v9.COL_PARAMETER, v9.COL_EXPECTED,
        v9.COL_ASSESSMENT, v9.COL_REMEDIATION])
    monkeypatch.setattr(v9, "SOURCE_TOKEN", "SCG-9.1")
    seen = []

    def _classify(parameter, assessment):
        seen.append(parameter)
        return "manual_audit"

    monkeypatch.setattr(v9, "classify_parameter_kind", _classify)
    src, out = tmp_path / "s.csv", tmp_path / "o.csv"
    _write_source(src, "v91", "9")
    assert v9.normalize(str(src), str(out)) == 0
    rows = _rows(out)
    assert seen, "patched classifier was not used"
    assert all(r["source_ref"].startswith("SCG-9.1:") for r in
               csv.DictReader(open(out, encoding="utf-8")))
    assert rows["vcenter-9.network-vgt"]["parameter_kind"] == "vim_property"


def test_v8_honours_patched_source_token(tmp_path, monkeypatch):
    monkeypatch.setattr(v8, "SOURCE_TOKEN", "SCG-7.0")
    src, out = tmp_path / "s.csv", tmp_path / "o.csv"
    _write_source(src, "v8", "7")
    assert v8.normalize(str(src), str(out)) == 0
    assert "vcenter-7.network-vgt" in _rows(out)
    with open(out, encoding="utf-8") as f:
        assert all(r["source_ref"].startswith("SCG-7.0:") for r in csv.DictReader(f))


def test_missing_required_column_is_rc2(tmp_path):
    src, out = tmp_path / "s.csv", tmp_path / "o.csv"
    _write_source(src, "v8", "8")   # 8.x header lacks the 9.x newline names
    assert v9.normalize(str(src), str(out)) == 2
    assert not out.exists()


def test_driver_patch_targets_still_exist():
    """Names the compliance repo's 7.0 / 9.1 drivers guard on before patching."""
    for name in ("SOURCE_TOKEN", "normalize"):
        assert hasattr(v8, name)
    for name in ("COL_COMPONENT", "COL_PRIORITY", "REQUIRED_COLUMNS",
                 "SOURCE_TOKEN", "COL_SCG_ID", "COL_TITLE", "COL_DESCRIPTION",
                 "COL_PARAMETER", "COL_EXPECTED", "COL_ASSESSMENT",
                 "COL_REMEDIATION", "classify_parameter_kind", "normalize"):
        assert hasattr(v9, name)
    for name in ("COMPONENT_MAP", "SOURCE_ID_PREFIX_MAP",
                 "_VIM_RECLASS_BY_CONTROL_ID", "_VIM_RECLASS_BY_SOURCE_ID",
                 "_VIM_RECLASS_DESCRIPTION_CAVEAT", "classify_vim_reclass",
                 "classify_source_id_vim_reclass", "write_canonical",
                 "CANONICAL_HEADER"):
        assert hasattr(base, name)
    assert "vcenter-8.network-vgt" in base._VIM_RECLASS_BY_SOURCE_ID
    for key in ("vds.network-restrict-discovery-protocol", "vm.virtual-hardware"):
        assert key in base._VIM_RECLASS_BY_CONTROL_ID
    assert "vm.virtual-hardware" in base._VIM_RECLASS_DESCRIPTION_CAVEAT

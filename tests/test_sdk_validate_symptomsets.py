"""validate-sdk rejects a composite <SymptomSets> with fewer than two children.

Issue #203: compliance build 90 shipped alert vcfcf_compliance_overrides_vcenter
with <SymptomSets operator="or"> wrapping one <SymptomSet>.  VCF Operations
9.0.2 rejected the whole describe at install ("A composite symptom set should
contain at least two Symptom Sets/Composite Symptom Sets") and the controller
rolled back.  validate-sdk now fails on that shape and names the alert.
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Only the pure checker is imported at module top.  Tests that monkeypatch
# sdk_builder reach every function through the in-body ``sb`` import, because
# tests/test_release_builder_phase2.py drops the module from sys.modules and a
# module-top binding would then point at a different copy than the patches.
from vcfcf_managementpacks.sdk_builder import (  # noqa: E402
    _validate_describe_symptom_sets,
)

_HEAD = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<AdapterKind xmlns="http://schemas.vmware.com/vcops/schema" key="vcfcf_probe" '
    'nameKey="1" version="1">\n  <AlertDefinitions>\n'
)
_TAIL = "  </AlertDefinitions>\n</AdapterKind>\n"


def _alert(alert_id: str, state_body: str) -> str:
    return textwrap.dedent(f"""\
        <AlertDefinition id="{alert_id}" nameKey="2" adapterKind="vcfcf_probe"
                         resourceKind="probe_world" type="15" subType="21">
          <State severity="Automatic">
            <Impact type="badge" key="risk"/>
            {state_body}
          </State>
        </AlertDefinition>
    """)


def _write(tmp_path: Path, *alerts: str) -> Path:
    p = tmp_path / "describe.xml"
    p.write_text(_HEAD + "".join(alerts) + _TAIL, encoding="utf-8")
    return p


_ONE_CHILD = (
    '<SymptomSets operator="or">'
    '<SymptomSet ref="sym_a" operator="and" applyOn="self"/>'
    "</SymptomSets>"
)
_TWO_CHILDREN = (
    '<SymptomSets operator="or">'
    '<SymptomSet ref="sym_a" operator="and" applyOn="self"/>'
    '<SymptomSet ref="sym_b" operator="and" applyOn="self"/>'
    "</SymptomSets>"
)
_BARE = '<SymptomSet ref="sym_a" operator="and" applyOn="self"/>'


def test_build_90_shape_is_rejected_and_names_the_alert(tmp_path):
    p = _write(tmp_path, _alert("vcfcf_compliance_overrides_vcenter", _ONE_CHILD))
    errs = _validate_describe_symptom_sets(p)
    assert len(errs) == 1
    assert "vcfcf_compliance_overrides_vcenter" in errs[0]
    assert 'operator="or"' in errs[0]
    assert "1 child" in errs[0]


def test_two_children_and_bare_single_set_pass(tmp_path):
    p = _write(tmp_path, _alert("two", _TWO_CHILDREN), _alert("bare", _BARE))
    assert _validate_describe_symptom_sets(p) == []


def test_empty_composite_is_rejected(tmp_path):
    p = _write(tmp_path, _alert("empty", '<SymptomSets operator="and"></SymptomSets>'))
    errs = _validate_describe_symptom_sets(p)
    assert len(errs) == 1 and "'empty'" in errs[0] and "0 child" in errs[0]


def test_nested_composite_with_one_child_is_rejected(tmp_path):
    nested = (
        '<SymptomSets operator="and">'
        '<SymptomSet ref="sym_a" operator="and" applyOn="self"/>'
        f"{_ONE_CHILD}"
        "</SymptomSets>"
    )
    errs = _validate_describe_symptom_sets(_write(tmp_path, _alert("nested", nested)))
    # Outer has two children (one set, one composite); the inner has one.
    assert len(errs) == 1 and "'nested'" in errs[0]


def test_only_offending_alert_is_named(tmp_path):
    p = _write(tmp_path, _alert("good", _TWO_CHILDREN), _alert("bad", _ONE_CHILD))
    errs = _validate_describe_symptom_sets(p)
    assert len(errs) == 1 and "'bad'" in errs[0] and "'good'" not in errs[0]


def test_unparseable_describe_is_an_error(tmp_path):
    p = tmp_path / "describe.xml"
    p.write_text("<AdapterKind><broken>", encoding="utf-8")
    errs = _validate_describe_symptom_sets(p)
    assert len(errs) == 1 and "could not be parsed" in errs[0]


def test_validate_sdk_project_surfaces_the_error(tmp_path, monkeypatch):
    """End to end through validate_sdk_project: adapter.yaml loading is stubbed
    so the test exercises only the describe.xml wiring."""
    import vcfcf_managementpacks.sdk_builder as sb

    (tmp_path / "adapter.yaml").write_text("name: probe\n", encoding="utf-8")
    _write(tmp_path, _alert("vcfcf_compliance_overrides_vcenter", _ONE_CHILD))
    src = tmp_path / "src"
    src.mkdir()
    (src / "Probe.java").write_text("class Probe {}\n", encoding="utf-8")

    monkeypatch.setattr(sb, "load_sdk_project", lambda _p: object())
    monkeypatch.setattr(
        sb, "_load_bundled_content", lambda *a, **k: ([], [], [], [], [], [], [])
    )
    monkeypatch.setattr(sb.shutil, "which", lambda _n: None)

    errs = sb.validate_sdk_project(tmp_path)
    assert any("vcfcf_compliance_overrides_vcenter" in e and "SymptomSets" in e for e in errs)


# --- build-sdk path: the release CI runs build-sdk only, never validate-sdk ---

def _stub_build_prereqs(monkeypatch, tmp_path):
    """Stub adapter.yaml loading and version stamping, and make every step
    after the describe check raise, so a pass would be visible."""
    import vcfcf_managementpacks.sdk_builder as sb

    (tmp_path / "adapter.yaml").write_text("name: probe\n", encoding="utf-8")

    class _P:
        name = "probe"
        version = "0.0.0"
        build_number = 1
        adapter_kind = "vcfcf_probe"

    monkeypatch.setattr(sb, "load_sdk_project", lambda _p: _P())
    monkeypatch.setattr(sb, "_is_release_build", lambda: True)
    monkeypatch.setattr(sb, "_stamp_build_version", lambda *_a, **_k: None)

    def _past_the_check(*_a, **_k):
        raise RuntimeError("reached bundled-content step")

    monkeypatch.setattr(sb, "_load_bundled_content", _past_the_check)
    return sb


def test_build_sdk_pak_fails_on_one_child_composite(tmp_path, monkeypatch):
    sb = _stub_build_prereqs(monkeypatch, tmp_path)
    _write(tmp_path, _alert("vcfcf_compliance_overrides_vcenter", _ONE_CHILD))
    with pytest.raises(sb.SdkBuildError) as exc:
        sb.build_sdk_pak(tmp_path, tmp_path / "dist")
    msg = str(exc.value)
    assert "vcfcf_compliance_overrides_vcenter" in msg and "SymptomSets" in msg
    assert msg == _validate_describe_symptom_sets(tmp_path / "describe.xml")[0]


def test_build_sdk_pak_passes_the_check_on_valid_describe(tmp_path, monkeypatch):
    sb = _stub_build_prereqs(monkeypatch, tmp_path)
    _write(tmp_path, _alert("good", _TWO_CHILDREN))
    with pytest.raises(RuntimeError, match="reached bundled-content step"):
        sb.build_sdk_pak(tmp_path, tmp_path / "dist")


def test_buildkit_build_sdk_release_entry_fails(tmp_path, monkeypatch, capsys):
    """The CI entry: `sdk_buildkit build-sdk --release` goes through
    build_sdk_pak and exits 1 with the same message.

    The kit's __main__.py is the _KIT_MAIN text in buildkit.py; it is exec'd
    with its relative imports resolving inside vcfcf_managementpacks, whose
    sdk_builder.py is the file the kit ships as its own sdk_builder.py."""
    from vcfcf_managementpacks.buildkit import _KIT_MAIN

    _stub_build_prereqs(monkeypatch, tmp_path)
    ns = {"__name__": "vcfcf_managementpacks._kit_main_probe",
          "__package__": "vcfcf_managementpacks"}
    exec(compile(_KIT_MAIN, "sdk_buildkit/__main__.py", "exec"), ns)
    _write(tmp_path, _alert("vcfcf_compliance_overrides_vcenter", _ONE_CHILD))
    # --release writes os.environ directly; setenv first so monkeypatch
    # records the original state and teardown restores it.
    monkeypatch.setenv("VCFCF_RELEASE_BUILD", "0")
    monkeypatch.delenv("VCFCF_RELEASE_BUILD")
    monkeypatch.setattr(
        sys, "argv",
        ["sdk_buildkit", "build-sdk", str(tmp_path), "--release",
         "--output", str(tmp_path / "dist")],
    )
    assert ns["main"]() == 1
    err = capsys.readouterr().err
    assert "vcfcf_compliance_overrides_vcenter" in err and "SymptomSets" in err

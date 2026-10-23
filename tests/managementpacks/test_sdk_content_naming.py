"""adapter.yaml ``content_naming``: the naming switch for bundled content (#229).

Contract:
  factory_prefixed (default)  every bundled content name starts with
                              "[VCF Content Factory] ".
  unprefixed                  no bundled content name carries the prefix.
  key declared                a mismatch is a validate-sdk error and a
                              build-sdk failure (release CI runs build-sdk
                              only).
  key absent                  the default applies, but a mismatch is one
                              warning, so a pak that predates the key keeps
                              validating until it declares.
  any other value             adapter.yaml schema error.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from vcfcf_managementpacks.sdk_project import (
    CONTENT_NAMING_DEFAULT,
    SdkProjectError,
    load_sdk_project,
)

PREFIX = "[VCF Content Factory] "

_ADAPTER_YAML = """name: "VCF Content Factory Probe"
version: "1.0.0"
build_number: 1
adapter_kind: "vcfcf_probe"
tier: 2
"""

_DESCRIBE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<AdapterKind xmlns="http://schemas.vmware.com/vcops/schema" key="vcfcf_probe"
             nameKey="1" version="1">
  <ResourceKinds>
    <ResourceKind key="vcfcf_probe" nameKey="2" type="7"/>
  </ResourceKinds>
</AdapterKind>
"""

_SM_YAML = """id: 6a8a4c78-d79e-4953-bc85-623b7bfb6000
name: "{name}"
resource_kinds:
  - resource_kind_key: ClusterComputeResource
    adapter_kind_key: VMWARE
description: Probe super metric.
unit_id: percent
formula: |
  ${{this, metric=cpu|reservedCapacity_average}} * 100
"""


def _project(tmp_path: Path, naming_line: str, sm_names) -> Path:
    project_dir = tmp_path / "probe"
    (project_dir / "supermetrics").mkdir(parents=True)
    (project_dir / "src").mkdir()
    (project_dir / "src" / "Probe.java").write_text("class Probe {}\n", encoding="utf-8")
    (project_dir / "describe.xml").write_text(_DESCRIBE_XML, encoding="utf-8")
    rels = []
    for i, name in enumerate(sm_names):
        rel = f"supermetrics/sm{i}.yaml"
        uuid = f"6a8a4c78-d79e-4953-bc85-623b7bfb6{i:03d}"
        (project_dir / rel).write_text(
            _SM_YAML.format(name=name).replace("6a8a4c78-d79e-4953-bc85-623b7bfb6000", uuid),
            encoding="utf-8",
        )
        rels.append(rel)
    body = _ADAPTER_YAML + naming_line
    if rels:
        body += "bundled_content:\n  supermetrics:\n" + "".join(f"    - {r}\n" for r in rels)
    (project_dir / "adapter.yaml").write_text(body, encoding="utf-8")
    return project_dir


def _validate(project_dir: Path, monkeypatch):
    import vcfcf_managementpacks.sdk_builder as sb
    monkeypatch.setattr(sb.shutil, "which", lambda _n: None)  # no compile check
    return sb.validate_sdk_project(project_dir)


# --- loader --------------------------------------------------------------

def test_loader_default_is_factory_prefixed_and_undeclared(tmp_path):
    p = _project(tmp_path, "", [])
    proj = load_sdk_project(p / "adapter.yaml")
    assert proj.content_naming == CONTENT_NAMING_DEFAULT == "factory_prefixed"
    assert proj.content_naming_declared is False


@pytest.mark.parametrize("value", ["factory_prefixed", "unprefixed"])
def test_loader_accepts_declared_values(tmp_path, value):
    p = _project(tmp_path, f"content_naming: {value}\n", [])
    proj = load_sdk_project(p / "adapter.yaml")
    assert proj.content_naming == value
    assert proj.content_naming_declared is True


@pytest.mark.parametrize("value", ["native", "prefixed", "", "true"])
def test_loader_rejects_other_values(tmp_path, value):
    p = _project(tmp_path, f"content_naming: {value!r}\n", [])
    with pytest.raises(SdkProjectError, match="content_naming"):
        load_sdk_project(p / "adapter.yaml")


# --- validate-sdk ----------------------------------------------------------

def test_declared_factory_prefixed_passes_prefixed(tmp_path, monkeypatch):
    p = _project(tmp_path, "content_naming: factory_prefixed\n", [PREFIX + "Probe SM"])
    assert _validate(p, monkeypatch) == []


def test_declared_factory_prefixed_rejects_unprefixed(tmp_path, monkeypatch):
    p = _project(tmp_path, "content_naming: factory_prefixed\n",
                 [PREFIX + "Good", "Bare Name"])
    errs = _validate(p, monkeypatch)
    assert len(errs) == 1
    assert "supermetric 'Bare Name'" in errs[0] and "must start with" in errs[0]


def test_declared_unprefixed_passes_bare(tmp_path, monkeypatch):
    p = _project(tmp_path, "content_naming: unprefixed\n", ["Bare One", "Bare Two"])
    assert _validate(p, monkeypatch) == []


@pytest.mark.parametrize("bad", [PREFIX + "Probe", "[VCF Content Factory]Probe"])
def test_declared_unprefixed_rejects_prefixed(tmp_path, monkeypatch, bad):
    p = _project(tmp_path, "content_naming: unprefixed\n", ["Bare", bad])
    errs = _validate(p, monkeypatch)
    assert len(errs) == 1 and "must not carry" in errs[0] and repr(bad) in errs[0]


def test_absent_key_mismatch_is_a_warning_not_an_error(tmp_path, monkeypatch, capsys):
    p = _project(tmp_path, "", ["Bare One", "Bare Two", "Bare 3", "Bare 4"])
    assert _validate(p, monkeypatch) == []
    err = capsys.readouterr().err
    assert "content_naming not declared" in err
    assert "4 bundled name(s)" in err and "and 1 more" in err
    assert err.count("content_naming not declared") == 1


def test_absent_key_all_prefixed_is_silent(tmp_path, monkeypatch, capsys):
    p = _project(tmp_path, "", [PREFIX + "Probe"])
    assert _validate(p, monkeypatch) == []
    assert "content_naming" not in capsys.readouterr().err


def test_no_bundled_content_is_silent(tmp_path, monkeypatch, capsys):
    p = _project(tmp_path, "content_naming: unprefixed\n", [])
    assert _validate(p, monkeypatch) == []
    assert "content_naming" not in capsys.readouterr().err


# --- checker covers every bundled type ---------------------------------------

def test_checker_covers_all_seven_types():
    from vcfcf_managementpacks.sdk_builder import check_content_naming
    proj = SimpleNamespace(content_naming="unprefixed", content_naming_declared=True)
    bundled = tuple([SimpleNamespace(name=PREFIX + t)] for t in
                    ("v", "d", "sm", "sy", "a", "r", "rec"))
    errs, warns = check_content_naming(proj, bundled)
    assert warns == [] and len(errs) == 7
    for label in ("view", "dashboard", "supermetric", "symptom", "alert",
                  "report", "recommendation"):
        assert any(e.split("bundled ", 1)[1].startswith(label + " ") for e in errs)


# --- build-sdk ---------------------------------------------------------------

def test_build_sdk_fails_on_declared_mismatch(tmp_path, monkeypatch):
    import vcfcf_managementpacks.sdk_builder as sb
    p = _project(tmp_path, "content_naming: unprefixed\n", [PREFIX + "Probe"])
    monkeypatch.setattr(sb, "_stamp_build_version", lambda *_a, **_k: None)
    with pytest.raises(sb.SdkBuildError, match="must not carry"):
        sb.build_sdk_pak(p, tmp_path / "dist")

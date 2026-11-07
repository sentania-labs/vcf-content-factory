"""conf/logging.properties in Tier 2 paks (factory #313).

The SDK's per-instance adapter log appender takes the level of the log4j
entry covering the bare logger name at the instance's first lookup. A pak
with no ``<adapter>/conf/logging.properties`` leaves every name at the
collector root (WARN) unless a Test Connection's setLevel side effect created
an entry, so helper-class INFO lines were dropped. build-sdk now ships
``<entry_class package>=INFO`` (vendor shape: ``com.vmware.adapter3.nsxt=INFO``),
tunable through the adapter.yaml ``logging:`` stanza, and an adapter-source
``conf/logging.properties`` wins.

Evidence: knowledge/context/investigations/2026-11-07-componentlogger-routing.md.
"""
from __future__ import annotations

import io
import textwrap
import zipfile
from pathlib import Path

import pytest

from vcfcf_managementpacks.sdk_builder import _assemble_adapters_zip
from vcfcf_managementpacks.sdk_project import SdkProjectError, load_sdk_project

_DESCRIBE = """<?xml version="1.0" encoding="UTF-8"?>
<AdapterKind key="vcfcf_widget" nameKey="1" version="1"
             xmlns="http://schemas.vmware.com/vcops/schema">
  <ResourceKinds>
    <ResourceKind key="widget_world" nameKey="2" type="7"/>
  </ResourceKinds>
</AdapterKind>
"""

_BASE_YAML = """\
name: "VCF Content Factory Widget"
version: "1.0.0"
build_number: 3
adapter_kind: "vcfcf_widget"
tier: 2
entry_class: "com.vcfcf.adapters.widget.WidgetAdapter"
"""

_LOGGING_ENTRY = "vcfcf_widget/conf/logging.properties"


def _fixture_adapter(tmp_path: Path, extra_yaml: str = "") -> Path:
    project_dir = tmp_path / "widget"
    project_dir.mkdir()
    (project_dir / "adapter.yaml").write_text(
        _BASE_YAML + textwrap.dedent(extra_yaml), encoding="utf-8")
    (project_dir / "describe.xml").write_text(_DESCRIBE, encoding="utf-8")
    return project_dir


def _build_adapters_zip(project_dir: Path, tmp_path: Path) -> zipfile.ZipFile:
    project = load_sdk_project(project_dir / "adapter.yaml")
    jar = tmp_path / f"{project.adapter_kind}.jar"
    if not jar.exists():
        jar.write_bytes(b"PK\x05\x06" + b"\x00" * 18)  # empty zip
    data = _assemble_adapters_zip(project, project_dir, jar, [])
    return zipfile.ZipFile(io.BytesIO(data))


# ---------------------------------------------------------------------------
# Generated file
# ---------------------------------------------------------------------------

def test_default_build_ships_package_info_line(tmp_path):
    zf = _build_adapters_zip(_fixture_adapter(tmp_path), tmp_path)
    assert _LOGGING_ENTRY in zf.namelist()
    assert zf.read(_LOGGING_ENTRY) == b"com.vcfcf.adapters.widget=INFO\n"


def test_default_entry_class_package_is_derived(tmp_path):
    """No entry_class in adapter.yaml: the derived class's package is keyed."""
    project_dir = tmp_path / "widget"
    project_dir.mkdir()
    (project_dir / "adapter.yaml").write_text(
        _BASE_YAML.replace(
            'entry_class: "com.vcfcf.adapters.widget.WidgetAdapter"\n', ""),
        encoding="utf-8")
    (project_dir / "describe.xml").write_text(_DESCRIBE, encoding="utf-8")
    zf = _build_adapters_zip(project_dir, tmp_path)
    assert zf.read(_LOGGING_ENTRY) == b"com.vcfcf.adapters.vcfcf_widget=INFO\n"


def test_logging_stanza_level_and_extra_lines(tmp_path):
    project_dir = _fixture_adapter(tmp_path, """\
        logging:
          level: debug
          loggers:
            com.example.vendorclient: WARN
            MaxBackupIndex: 10
            MaxFileSize: 20MB
        """)
    zf = _build_adapters_zip(project_dir, tmp_path)
    assert zf.read(_LOGGING_ENTRY).decode("ascii") == (
        "MaxBackupIndex=10\n"
        "MaxFileSize=20MB\n"
        "com.vcfcf.adapters.widget=DEBUG\n"
        "com.example.vendorclient=WARN\n"
    )


def test_generate_false_ships_no_file(tmp_path):
    project_dir = _fixture_adapter(tmp_path, "logging:\n  generate: false\n")
    zf = _build_adapters_zip(project_dir, tmp_path)
    assert _LOGGING_ENTRY not in zf.namelist()


def test_nothing_else_in_adapters_zip_changes(tmp_path):
    """The file is the only difference from a build that ships none."""
    on_dir = tmp_path / "a"
    off_dir = tmp_path / "b"
    on_dir.mkdir()
    off_dir.mkdir()
    on = _build_adapters_zip(_fixture_adapter(on_dir), on_dir)
    off = _build_adapters_zip(
        _fixture_adapter(off_dir, "logging:\n  generate: false\n"), off_dir)
    assert set(on.namelist()) - set(off.namelist()) == {_LOGGING_ENTRY}
    assert set(off.namelist()) <= set(on.namelist())
    for name in off.namelist():
        assert on.read(name) == off.read(name), name


def test_non_ascii_package_is_properties_escaped(tmp_path):
    project_dir = _fixture_adapter(tmp_path)
    yaml_path = project_dir / "adapter.yaml"
    yaml_path.write_text(
        yaml_path.read_text(encoding="utf-8").replace(
            "com.vcfcf.adapters.widget.WidgetAdapter",
            "com.vcfcf.adapters.wédget.WidgetAdapter"),
        encoding="utf-8")
    zf = _build_adapters_zip(project_dir, tmp_path)
    assert zf.read(_LOGGING_ENTRY) == b"com.vcfcf.adapters.w\\u00e9dget=INFO\n"


# ---------------------------------------------------------------------------
# Adapter-source file wins
# ---------------------------------------------------------------------------

def test_source_conf_logging_properties_wins(tmp_path, capsys):
    project_dir = _fixture_adapter(tmp_path, "logging:\n  level: WARN\n")
    explicit = b"MaxBackupIndex=15\ncom.vcfcf.adapters.widget = TRACE\n"
    (project_dir / "conf").mkdir()
    (project_dir / "conf" / "logging.properties").write_bytes(explicit)
    zf = _build_adapters_zip(project_dir, tmp_path)
    assert zf.read(_LOGGING_ENTRY) == explicit
    assert zf.namelist().count(_LOGGING_ENTRY) == 1
    assert "logging: stanza is ignored" in capsys.readouterr().err


def test_source_file_ships_even_with_generate_false(tmp_path):
    project_dir = _fixture_adapter(tmp_path, "logging:\n  generate: false\n")
    (project_dir / "conf").mkdir()
    (project_dir / "conf" / "logging.properties").write_bytes(b"a.b=INFO\n")
    zf = _build_adapters_zip(project_dir, tmp_path)
    assert zf.read(_LOGGING_ENTRY) == b"a.b=INFO\n"


def test_source_file_without_stanza_is_silent(tmp_path, capsys):
    project_dir = _fixture_adapter(tmp_path)
    (project_dir / "conf").mkdir()
    (project_dir / "conf" / "logging.properties").write_bytes(b"a.b=INFO\n")
    _build_adapters_zip(project_dir, tmp_path)
    assert "logging" not in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Loader validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("stanza, message", [
    ("logging: INFO\n", "'logging' must be a mapping"),
    ("logging:\n  levels: INFO\n", "unknown key"),
    ("logging:\n  generate: 'no'\n", "logging.generate must be true or false"),
    ("logging:\n  level: VERBOSE\n", "logging.level must be one of"),
    ("logging:\n  loggers: [a]\n", "logging.loggers must be a mapping"),
    ("logging:\n  loggers:\n    com.x: LOUD\n", "must be one of"),
    ("logging:\n  loggers:\n    'com x': INFO\n", "is not a logger name"),
    ("logging:\n  loggers:\n    MaxBackupIndex: true\n", "non-negative integer"),
    ("logging:\n  loggers:\n    MaxBackupIndex: -1\n", "non-negative integer"),
    ("logging:\n  loggers:\n    MaxFileSize: 10\n", "must be a size"),
    ("logging:\n  loggers:\n    com.vcfcf.adapters.widget: DEBUG\n",
     "set its level with logging.level"),
])
def test_logging_stanza_rejects(tmp_path, stanza, message):
    project_dir = _fixture_adapter(tmp_path, stanza)
    with pytest.raises(SdkProjectError, match=message):
        load_sdk_project(project_dir / "adapter.yaml")


def test_no_stanza_defaults(tmp_path):
    project = load_sdk_project(_fixture_adapter(tmp_path) / "adapter.yaml")
    assert project.logging.generate is True
    assert project.logging.level == "INFO"
    assert project.logging.loggers == []
    assert project.logging.declared is False
    assert project.entry_package == "com.vcfcf.adapters.widget"


# ---------------------------------------------------------------------------
# validate-sdk warnings on an adapter-source file (review N2)
# ---------------------------------------------------------------------------

def _source_file(tmp_path: Path, data: bytes) -> Path:
    (tmp_path / "conf").mkdir()
    (tmp_path / "conf" / "logging.properties").write_bytes(data)
    return tmp_path


def test_source_check_clean_file_has_no_warnings(tmp_path):
    from vcfcf_managementpacks.sdk_builder import check_source_logging_properties
    project_dir = _source_file(tmp_path, (
        b"# comment\n! also a comment\n\nMaxBackupIndex=15\nMaxFileSize = 20MB\n"
        b"com.vmware.adapter3.logassist = INFO\ncom.x:debug\n"
        b"com.y \\\n    WARN\n"))
    assert check_source_logging_properties(project_dir) == []


def test_source_check_flags_unknown_level(tmp_path):
    from vcfcf_managementpacks.sdk_builder import check_source_logging_properties
    project_dir = _source_file(tmp_path, b"com.x=VERBOSE\ncom.y=INFO\n")
    warnings = check_source_logging_properties(project_dir)
    assert len(warnings) == 1
    assert "'com.x'" in warnings[0] and "VERBOSE" in warnings[0]


def test_source_check_flags_non_ascii(tmp_path):
    from vcfcf_managementpacks.sdk_builder import check_source_logging_properties
    project_dir = _source_file(tmp_path, "com.café=INFO\n".encode("utf-8"))
    warnings = check_source_logging_properties(project_dir)
    assert any("non-ASCII" in w for w in warnings)


def test_source_check_no_file(tmp_path):
    from vcfcf_managementpacks.sdk_builder import check_source_logging_properties
    assert check_source_logging_properties(tmp_path) == []


def test_validate_sdk_prints_source_warning(tmp_path, capsys):
    from vcfcf_managementpacks.sdk_builder import validate_sdk_project
    project_dir = _fixture_adapter(tmp_path)
    (project_dir / "conf").mkdir()
    (project_dir / "conf" / "logging.properties").write_bytes(b"com.x=LOUD\n")
    validate_sdk_project(project_dir)
    assert "validate-sdk: warning: conf/logging.properties: 'com.x'" in capsys.readouterr().err

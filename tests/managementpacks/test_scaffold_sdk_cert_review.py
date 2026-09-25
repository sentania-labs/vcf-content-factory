"""scaffold-sdk emits a framework-v2 skeleton with the TLS conventions.

New in-tree scaffolds get:
  - an ``allowInsecure`` identifier as a pulldown (``enum="true"`` with
    ``true``/``false`` values, default ``false``), plus ``host``/``port``;
  - a ``certificateCheckUrls`` override so Validate Connection offers the
    VCF Operations "Review and accept certificate" dialog;
  - a skeleton that compiles against the v2 framework (the previous skeleton
    used the removed aria-ops-core API and could not compile).

The compile check runs only when javac and the (non-redistributable) SDK jar
are present, the same gate ``validate-sdk`` uses.
"""
from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET

import pytest

from vcfcf_managementpacks import sdk_builder

NS = {"v": "http://schemas.vmware.com/vcops/schema"}


@pytest.fixture
def project(tmp_path, capsys):
    d = sdk_builder.scaffold_sdk_project("Cert Demo", tmp_path)
    capsys.readouterr()
    return d


def test_describe_allow_insecure_is_a_pulldown(project):
    root = ET.parse(project / "describe.xml").getroot()
    inst = root.find("v:ResourceKinds/v:ResourceKind[@type='7']", NS)
    assert inst is not None
    ids = {e.get("key"): e for e in inst.findall("v:ResourceIdentifier", NS)}
    assert {"host", "port", "allowInsecure"} <= set(ids)
    ai = ids["allowInsecure"]
    assert ai.get("enum") == "true"
    assert ai.get("default") == "false"
    assert ai.get("type") == "string"
    assert [e.get("value") for e in ai.findall("v:enum", NS)] == ["false", "true"]


def test_resources_cover_identifier_name_keys(project):
    props = (project / "resources" / "resources.properties").read_text(encoding="utf-8")
    keys = {ln.split("=", 1)[0] for ln in props.splitlines() if "=" in ln and not ln.startswith("#")}
    root = ET.parse(project / "describe.xml").getroot()
    used = {e.get("nameKey") for e in root.iter() if e.get("nameKey")}
    assert used <= keys, f"nameKeys without a label: {sorted(used - keys)}"


def test_java_skeleton_is_v2_with_cert_hook(project):
    java = next((project / "src").rglob("*Adapter.java")).read_text(encoding="utf-8")
    assert "com.vmware.tvs" not in java, "v1 aria-ops-core API must not be emitted"
    assert "protected List<String> certificateCheckUrls(ResourceConfig rc)" in java
    assert "isAllowInsecure(rc)" in java
    assert "super(ADAPTER_KIND)" in java
    assert "super(ADAPTER_KIND, adapterDir, adapterInstanceId)" in java
    assert "\u2014" not in java


def test_scaffold_compiles_against_framework(project, capsys):
    if not shutil.which("javac"):
        pytest.skip("javac not on PATH")
    if not sorted(sdk_builder._ADAPTER_RUNTIME_DIR.glob("vrops-adapters-sdk-*.jar")):
        pytest.skip("SDK jar not present (not redistributable)")
    errors = sdk_builder.validate_sdk_project(project)
    assert errors == []


@pytest.mark.parametrize(
    "name, expected_class",
    [
        # Names whose slug starts with letters in "vcfcf_": the old
        # slug.lstrip("vcfcf_") ate them ("Cert Demo" -> ErtDemoAdapter).
        ("Cert Demo", "CertDemoAdapter"),
        ("Synology", "SynologyAdapter"),
        ("Unifi", "UnifiAdapter"),
        ("Foo Bar", "FooBarAdapter"),
        ("fcv Monitor", "FcvMonitorAdapter"),
        # The real prefix is still removed exactly once.
        ("vcfcf cert", "CertAdapter"),
        ("Victor", "VictorAdapter"),
    ],
)
def test_scaffold_class_name_keeps_leading_letters(tmp_path, capsys, name, expected_class):
    d = sdk_builder.scaffold_sdk_project(name, tmp_path)
    capsys.readouterr()
    classes = [p.stem for p in (d / "src").rglob("*Adapter.java")]
    assert classes == [expected_class]

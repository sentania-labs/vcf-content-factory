"""Bundled symptom/alert checks shared by validate-sdk and build-sdk.

TOOLSET GAP 2026-10-27 (bundling alerts into the unifi pak): validate-sdk
did not run the alert -> symptom / recommendation reference checks build-sdk
ran, and neither command checked symptom conditions against the pak's
describe.xml.  Each test plants one mistake and asserts both commands
reject it (or, for stitched content on a foreign adapter kind, accept it).
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

P = "[VCF Content Factory] "

_DESCRIBE = """\
<?xml version="1.0" encoding="UTF-8"?>
<AdapterKind xmlns="http://schemas.vmware.com/vcops/schema" key="probe_adapter"
             nameKey="1" version="1">
  <ResourceKinds>
    <ResourceKind key="probe_adapter" nameKey="2" type="7"/>
    <ResourceKind key="ProbeWorld" nameKey="3" type="1"/>
    <ResourceKind key="ProbeSwitch" nameKey="4">
      <ResourceGroup key="Status" nameKey="5" instanced="false">
        <ResourceAttribute key="state" nameKey="6" dataType="float"/>
        <ResourceAttribute key="state_code" nameKey="7" dataType="string" isProperty="true"/>
      </ResourceGroup>
      <ResourceGroup key="PoE" nameKey="8" instanced="false">
        <ResourceAttribute key="budget_used_pct" nameKey="9" dataType="float"/>
      </ResourceGroup>
      <ComputedMetrics>
        <ComputedMetric key="Rollup|ports_down" expression="sum(${adapterkind=probe_adapter, resourcekind=ProbePort, metric=Status|down})"/>
      </ComputedMetrics>
    </ResourceKind>
    <ResourceKind key="ProbePort" nameKey="10">
      <ResourceGroup key="Status" nameKey="11" instanced="false">
        <ResourceAttribute key="up" nameKey="12" dataType="string" isProperty="true"/>
        <ResourceAttribute key="down" nameKey="13" dataType="float"/>
      </ResourceGroup>
    </ResourceKind>
  </ResourceKinds>
  %EXTRA%
</AdapterKind>
"""

# A stitched SymptomDefinition, the compliance shape: describe.xml names the
# VMWARE adapter kind, so bundled content on VMWARE objects is legitimate.
_STITCHED_DESCRIBE_SYMPTOM = """\
  <SymptomDefinitions>
    <SymptomDefinition id="probe_stitched" nameKey="50" adapterKind="VMWARE"
                       resourceKind="HostSystem" waitCycle="1" cancelCycle="1">
      <State severity="Warning">
        <Condition type="metric" key="Probe|score" operator="&lt;" value="95"
                   valueType="numeric" thresholdType="static"/>
      </State>
    </SymptomDefinition>
  </SymptomDefinitions>
"""


def _symptom(name, kind, ctype, key, adapter_kind="probe_adapter"):
    cond = {
        "metric_static": f"type: metric_static\n  key: {key}\n  operator: GT\n  value: 90",
        "metric_dynamic": f"type: metric_dynamic\n  key: {key}\n  direction: ABOVE",
        "property": f'type: property\n  key: {key}\n  operator: EQ\n  value: "false"',
    }[ctype]
    return (
        f'name: "{P}{name}"\nadapter_kind: {adapter_kind}\nresource_kind: {kind}\n'
        f"severity: CRITICAL\ncondition:\n  {cond}\n"
    )


def _alert(name, kind, symptoms, recs=(), defined_on="SELF", adapter_kind="probe_adapter",
           sub_type=18):
    syms = "".join(f'        - name: "{P}{s}"\n' for s in symptoms)
    text = (
        f'name: "{P}{name}"\nadapter_kind: {adapter_kind}\nresource_kind: {kind}\n'
        f"type: 19\nsub_type: {sub_type}\ncriticality: CRITICAL\nimpact:\n  badge: HEALTH\n"
        f"symptom_sets:\n  operator: ALL\n  sets:\n"
        f"    - defined_on: {defined_on}\n      operator: ALL\n      symptoms:\n{syms}"
    )
    if recs:
        text += "recommendations:\n" + "".join(
            f'  - name: "{P}{r}"\n    priority: 1\n' for r in recs
        )
    return text


def _rec(name, adapter_kind="probe_adapter"):
    return f'name: "{P}{name}"\ndescription: Do the thing.\nadapter_kind: {adapter_kind}\n'


def _project(tmp_path: Path, *, symptoms=(), alerts=(), recs=(),
             extra_describe="", cross_mp_vmware=False, foreign_opt_in=None) -> Path:
    """Write a minimal adapter project; each item is (filename, yaml_text)."""
    d = tmp_path / "probe"
    for sub, items in (("symptoms", symptoms), ("alerts", alerts),
                       ("recommendations", recs)):
        (d / sub).mkdir(parents=True, exist_ok=True)
        for fname, text in items:
            (d / sub / fname).write_text(text, encoding="utf-8")
    src = d / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "Probe.java").write_text("class Probe {}\n", encoding="utf-8")
    (d / "describe.xml").write_text(
        _DESCRIBE.replace("%EXTRA%", extra_describe), encoding="utf-8"
    )
    lines = [
        "adapter_kind: probe_adapter",
        "entry_class: com.vcfcf.adapters.probe.ProbeAdapter",
        "name: VCF Content Factory Probe",
        "version: 0.1.0",
        "build_number: 1",
        "tier: 2",
        "released: false",
    ]
    if cross_mp_vmware:
        lines += [
            "cross_mp_edges:",
            '  - parent: "VMWARE HostSystem"',
            '    child: "ProbeSwitch"',
            "    foreign_adapter_kind: VMWARE",
        ]
    if foreign_opt_in is not None:
        lines.append(f"content_foreign_adapter_kinds: {foreign_opt_in}")
    lines.append("bundled_content:")
    for sub, items in (("symptoms", symptoms), ("alerts", alerts),
                       ("recommendations", recs)):
        if items:
            lines.append(f"  {sub}:")
            lines += [f"    - {sub}/{fname}" for fname, _ in items]
    (d / "adapter.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return d


def _validate(d: Path, monkeypatch):
    import vcfcf_managementpacks.sdk_builder as sb
    monkeypatch.setattr(sb.shutil, "which", lambda _n: None)  # no compile leg
    monkeypatch.delenv("VCFCF_SDK_COMPAT_REQUIRED", raising=False)
    return [e for e in sb.validate_sdk_project(d) if "compat" not in e.lower()]


def _build_errors(d: Path, monkeypatch) -> str:
    """Run build_sdk_pak up to the compile; return the content error or ''."""
    import vcfcf_managementpacks.sdk_builder as sb
    monkeypatch.delenv("VCFCF_RELEASE_BUILD", raising=False)

    def _reached_compile(*_a, **_k):
        raise RuntimeError("reached compile")

    monkeypatch.setattr(sb, "_detect_jdk", _reached_compile)
    try:
        sb.build_sdk_pak(d, d / "dist")
    except sb.SdkBuildError as exc:
        return str(exc)
    except RuntimeError as exc:
        assert "reached compile" in str(exc)
        return ""
    raise AssertionError("build_sdk_pak returned without reaching the compile")


def _both(d: Path, monkeypatch):
    v = _validate(d, monkeypatch)
    b = _build_errors(d, monkeypatch)
    return v, b


GOOD_SYMS = [
    ("offline.yaml", _symptom("Switch Offline", "ProbeSwitch", "property", "Status|state_code")),
    ("poe.yaml", _symptom("Switch PoE High", "ProbeSwitch", "metric_static", "PoE|budget_used_pct")),
]


def test_clean_project_passes_both(tmp_path, monkeypatch):
    d = _project(
        tmp_path, symptoms=GOOD_SYMS,
        alerts=[("a.yaml", _alert("Switch Down", "ProbeSwitch",
                                  ["Switch Offline", "Switch PoE High"], recs=["Fix It"]))],
        recs=[("r.yaml", _rec("Fix It"))],
    )
    assert _both(d, monkeypatch) == ([], "")


def test_platform_groups_and_computed_metrics_pass(tmp_path, monkeypatch):
    d = _project(tmp_path, symptoms=[
        ("b.yaml", _symptom("Badge", "ProbeSwitch", "metric_static", "badge|health")),
        ("s.yaml", _symptom("SysAttr", "ProbeSwitch", "metric_dynamic", "System Attributes|availability")),
        ("c.yaml", _symptom("Computed", "ProbeSwitch", "metric_static", "Rollup|ports_down")),
        ("i.yaml", _symptom("Instanced", "ProbePort", "metric_static", "Status:eth0|down")),
        ("o.yaml", _symptom("Capacity", "ProbeSwitch", "metric_static",
                            "OnlineCapacityAnalytics|cpu|capacityRemaining")),
        ("p.yaml", _symptom("SysProp", "ProbeSwitch", "property",
                            "System Properties|resource_kind_type")),
    ])
    assert _both(d, monkeypatch) == ([], "")


def test_capacity_display_name_is_rejected_with_the_key_group(tmp_path, monkeypatch):
    d = _project(tmp_path, symptoms=[
        ("bad.yaml", _symptom("Bad", "ProbeSwitch", "metric_static",
                              "Capacity Analytics Generated|cpu|capacityRemaining")),
    ])
    v, b = _both(d, monkeypatch)
    assert len(v) == 1 and "the key group is 'OnlineCapacityAnalytics'" in v[0]
    assert b == v[0]


def test_unknown_key_error_names_the_platform_allowlist(tmp_path, monkeypatch):
    d = _project(tmp_path, symptoms=[
        ("bad.yaml", _symptom("Bad", "ProbeSwitch", "metric_static", "Nope|x")),
    ])
    v, _b = _both(d, monkeypatch)
    assert len(v) == 1 and "Platform key groups accepted without a declaration" in v[0]
    assert "OnlineCapacityAnalytics" in v[0] and "System Properties" in v[0]


def test_platform_group_with_the_wrong_condition_type_fails(tmp_path, monkeypatch):
    d = _project(tmp_path, symptoms=[
        ("bad.yaml", _symptom("Bad", "ProbeSwitch", "property", "badge|health")),
    ])
    v, b = _both(d, monkeypatch)
    assert len(v) == 1 and "is a platform metric ('badge' group)" in v[0]
    assert b == v[0]



# --- reference checks: validate-sdk used to miss these ---

def test_alert_naming_unbundled_symptom_fails_both(tmp_path, monkeypatch):
    d = _project(tmp_path, symptoms=GOOD_SYMS[:1], alerts=[
        ("a.yaml", _alert("Switch Down", "ProbeSwitch", ["Switch Offline", "Not Bundled"])),
    ])
    v, b = _both(d, monkeypatch)
    assert any(f"{P}Not Bundled" in e and "bundled_content.symptoms" in e for e in v), v
    assert f"{P}Not Bundled" in b and "a.yaml" in b


def test_alert_naming_unbundled_recommendation_fails_both(tmp_path, monkeypatch):
    d = _project(tmp_path, symptoms=GOOD_SYMS[:1], alerts=[
        ("a.yaml", _alert("Switch Down", "ProbeSwitch", ["Switch Offline"], recs=["Missing Rec"])),
    ])
    v, b = _both(d, monkeypatch)
    assert any(f"{P}Missing Rec" in e and "bundled_content.recommendations" in e for e in v), v
    assert f"{P}Missing Rec" in b


# --- describe.xml conformance ---

def test_metric_condition_on_property_key_fails_both(tmp_path, monkeypatch):
    d = _project(tmp_path, symptoms=[
        ("bad.yaml", _symptom("Bad", "ProbeSwitch", "metric_static", "Status|state_code")),
    ])
    v, b = _both(d, monkeypatch)
    assert len(v) == 1 and "bad.yaml" in v[0] and "Status|state_code" in v[0]
    assert "ProbeSwitch" in v[0] and "type: property" in v[0]
    assert b == v[0]


def test_property_condition_on_metric_key_fails_both(tmp_path, monkeypatch):
    d = _project(tmp_path, symptoms=[
        ("bad.yaml", _symptom("Bad", "ProbeSwitch", "property", "PoE|budget_used_pct")),
    ])
    v, b = _both(d, monkeypatch)
    assert len(v) == 1 and "PoE|budget_used_pct" in v[0] and "metric_static" in v[0]
    assert b == v[0]


def test_key_not_in_describe_fails_both(tmp_path, monkeypatch):
    d = _project(tmp_path, symptoms=[
        ("bad.yaml", _symptom("Bad", "ProbeSwitch", "metric_static", "PoE|budget_pct")),
    ])
    v, b = _both(d, monkeypatch)
    assert len(v) == 1 and "'PoE|budget_pct' is not declared on resource kind 'ProbeSwitch'" in v[0]
    assert "bad.yaml" in v[0]
    assert b == v[0]


def test_resource_kind_not_in_describe_fails_both(tmp_path, monkeypatch):
    d = _project(tmp_path, symptoms=[
        ("bad.yaml", _symptom("Bad", "ProbeSwich", "metric_static", "PoE|budget_used_pct")),
    ])
    v, b = _both(d, monkeypatch)
    assert len(v) == 1 and "resource_kind 'ProbeSwich'" in v[0] and "bad.yaml" in v[0]
    assert b == v[0]


def test_key_on_a_different_resource_kind_fails_both_and_names_it(tmp_path, monkeypatch):
    d = _project(tmp_path, symptoms=[
        ("bad.yaml", _symptom("Bad", "ProbeSwitch", "property", "Status|up")),
    ])
    v, b = _both(d, monkeypatch)
    assert len(v) == 1 and "not declared on resource kind 'ProbeSwitch'" in v[0]
    assert "declared on ProbePort" in v[0]
    assert b == v[0]


def test_unknown_adapter_kind_fails_both(tmp_path, monkeypatch):
    d = _project(tmp_path, symptoms=[
        ("bad.yaml", _symptom("Bad", "ProbeSwitch", "metric_static",
                              "PoE|budget_used_pct", adapter_kind="probe_adaptr")),
    ])
    v, b = _both(d, monkeypatch)
    assert len(v) == 1 and "adapter_kind 'probe_adaptr'" in v[0] and "'probe_adapter'" in v[0]
    assert b == v[0]


def test_alert_on_undeclared_resource_kind_fails_both(tmp_path, monkeypatch):
    d = _project(tmp_path, symptoms=GOOD_SYMS[:1], alerts=[
        ("a.yaml", _alert("Switch Down", "ProbeSwich", ["Switch Offline"],
                          defined_on="CHILD")),
    ])
    v, b = _both(d, monkeypatch)
    assert len(v) == 1 and "Alert" in v[0] and "resource_kind 'ProbeSwich'" in v[0]
    assert b == v[0]


def test_self_set_symptom_on_another_kind_fails_both(tmp_path, monkeypatch):
    d = _project(tmp_path, symptoms=[
        ("up.yaml", _symptom("Port Up", "ProbePort", "property", "Status|up")),
    ], alerts=[("a.yaml", _alert("Switch Down", "ProbeSwitch", ["Port Up"]))])
    v, b = _both(d, monkeypatch)
    assert len(v) == 1 and "defined_on SELF" in v[0]
    assert "probe_adapter/ProbePort" in v[0] and "probe_adapter/ProbeSwitch" in v[0]
    assert b == v[0]


def test_child_set_symptom_on_another_kind_passes(tmp_path, monkeypatch):
    d = _project(tmp_path, symptoms=[
        ("up.yaml", _symptom("Port Up", "ProbePort", "property", "Status|up")),
    ], alerts=[("a.yaml", _alert("Switch Down", "ProbeSwitch", ["Port Up"],
                                 defined_on="CHILD"))])
    assert _both(d, monkeypatch) == ([], "")


# --- stitched / foreign-kind content (compliance shape) ---

def _vmware_content():
    return dict(
        symptoms=[("v.yaml", _symptom("Host Score Low", "HostSystem", "metric_static",
                                      "Probe|score", adapter_kind="VMWARE"))],
        alerts=[("a.yaml", _alert("Host Score Low", "HostSystem", ["Host Score Low"],
                                  adapter_kind="VMWARE"))],
    )


def test_stitched_vmware_content_passes_when_describe_names_vmware(tmp_path, monkeypatch):
    d = _project(tmp_path, extra_describe=_STITCHED_DESCRIBE_SYMPTOM, **_vmware_content())
    assert _both(d, monkeypatch) == ([], "")


def test_stitched_vmware_content_passes_when_cross_mp_edges_names_vmware(tmp_path, monkeypatch):
    d = _project(tmp_path, cross_mp_vmware=True, **_vmware_content())
    assert _both(d, monkeypatch) == ([], "")


def test_foreign_kind_the_pak_never_names_fails(tmp_path, monkeypatch):
    d = _project(tmp_path, **_vmware_content())
    v, b = _both(d, monkeypatch)
    assert len(v) == 2 and all("adapter_kind 'VMWARE'" in e for e in v)
    assert all("content_foreign_adapter_kinds: [VMWARE]" in e for e in v)
    assert b == "\n".join(v)


def test_built_in_vmware_metric_passes_with_the_adapter_yaml_opt_in(tmp_path, monkeypatch):
    """An alert on a built-in vSphere metric, no stitching: the opt-in is
    the honest escape (cross_mp_edges would invent a relationship)."""
    d = _project(tmp_path, foreign_opt_in="[VMWARE]", symptoms=[
        ("v.yaml", _symptom("VM CPU High", "VirtualMachine", "metric_static",
                            "cpu|usage_average", adapter_kind="VMWARE")),
    ], alerts=[("a.yaml", _alert("VM CPU High", "VirtualMachine", ["VM CPU High"],
                                 adapter_kind="VMWARE"))])
    assert _both(d, monkeypatch) == ([], "")


def test_opt_in_for_one_kind_does_not_admit_another(tmp_path, monkeypatch):
    d = _project(tmp_path, foreign_opt_in="[NSXTAdapter]", **_vmware_content())
    v, b = _both(d, monkeypatch)
    assert len(v) == 2 and all("foreign kinds it names: NSXTAdapter" in e for e in v)
    assert b == "\n".join(v)


@pytest.mark.parametrize("value, needle", [
    ("VMWARE", "must be a list"),
    ('[""]', "must be a non-empty string"),
    ("[VMWARE, VMWARE]", "lists 'VMWARE' twice"),
    ("[probe_adapter]", "this pak's own adapter_kind"),
])
def test_opt_in_is_validated_by_sdk_project(tmp_path, monkeypatch, value, needle):
    from vcfcf_managementpacks.sdk_project import SdkProjectError, load_sdk_project
    d = _project(tmp_path, foreign_opt_in=value)
    with pytest.raises(SdkProjectError, match=needle):
        load_sdk_project(d / "adapter.yaml")
    v = _validate(d, monkeypatch)
    assert len(v) == 1 and needle.split("'")[0] in v[0]


def test_opt_in_is_parsed(tmp_path):
    from vcfcf_managementpacks.sdk_project import load_sdk_project
    d = _project(tmp_path, foreign_opt_in="[VMWARE, NSXTAdapter]")
    assert load_sdk_project(d / "adapter.yaml").content_foreign_adapter_kinds == [
        "VMWARE", "NSXTAdapter",
    ]
    d2 = _project(tmp_path / "two")
    assert load_sdk_project(d2 / "adapter.yaml").content_foreign_adapter_kinds == []


def test_describe_index_reads_groups_properties_and_foreign_kinds(tmp_path):
    from vcfcf_managementpacks.sdk_builder import _describe_attribute_index
    p = tmp_path / "describe.xml"
    p.write_text(_DESCRIBE.replace("%EXTRA%", _STITCHED_DESCRIBE_SYMPTOM), encoding="utf-8")
    idx = _describe_attribute_index(p)
    assert idx["adapter_kind"] == "probe_adapter"
    assert idx["kinds"]["ProbeSwitch"] == {
        "Status|state": "metric", "Status|state_code": "property",
        "PoE|budget_used_pct": "metric", "Rollup|ports_down": "metric",
    }
    assert idx["foreign_adapter_kinds"] == {"VMWARE"}


@pytest.mark.parametrize("pak", ["compliance", "synology", "unifi", "template"])
def test_managed_paks_pass_the_content_checks(pak):
    """The registered paks present in this checkout still pass."""
    import yaml
    import vcfcf_managementpacks.sdk_builder as sb
    from vcfcf_managementpacks.sdk_project import load_sdk_project
    d = REPO_ROOT / "content" / "sdk-adapters" / pak
    if not (d / "adapter.yaml").is_file():
        pytest.skip(f"{pak} not cloned in this checkout")
    raw = yaml.safe_load((d / "adapter.yaml").read_text(encoding="utf-8")) or {}
    bundled = sb._load_bundled_content(raw, d, d)
    project = load_sdk_project(d / "adapter.yaml")
    assert sb.check_bundled_content(project, bundled, d / "describe.xml") == []


# --- alert sub_type: the platform enum is 18-22 (alertDefinitionSchema.xsd) ---

@pytest.mark.parametrize("sub_type", [18, 19, 20, 21, 22])
def test_factory_alert_loader_accepts_platform_subtypes(tmp_path, sub_type):
    from vcfcf_core.alerts.loader import load_file
    p = tmp_path / "a.yaml"
    p.write_text(_alert("A", "ProbeSwitch", ["S"], sub_type=sub_type), encoding="utf-8")
    assert load_file(p).sub_type == sub_type


@pytest.mark.parametrize("sub_type", [1, 3, 5, 6, 17, 23])
def test_factory_alert_loader_rejects_other_subtypes(tmp_path, sub_type):
    from vcfcf_core.alerts.loader import AlertValidationError, load_file
    p = tmp_path / "a.yaml"
    p.write_text(_alert("A", "ProbeSwitch", ["S"], sub_type=sub_type), encoding="utf-8")
    with pytest.raises(AlertValidationError) as exc:
        load_file(p)
    msg = str(exc.value)
    assert f"got {sub_type}" in msg and "19=Performance" in msg and "a.yaml" in msg


@pytest.mark.parametrize("raw", ["0", "-19", '""', "true", "19.5", "Performance"])
def test_explicit_invalid_sub_type_is_not_defaulted(tmp_path, raw):
    """An explicit sub_type, 0 included, is validated, never replaced by 19."""
    from vcfcf_core.alerts.loader import AlertValidationError, load_file
    p = tmp_path / "a.yaml"
    p.write_text(_alert("A", "ProbeSwitch", ["S"]).replace("sub_type: 18", f"sub_type: {raw}"),
                 encoding="utf-8")
    with pytest.raises(AlertValidationError, match="sub_type must be one of"):
        load_file(p)


@pytest.mark.parametrize("raw", ["null", "~", '"19"'])
def test_null_defaults_and_integer_string_is_accepted(tmp_path, raw):
    from vcfcf_core.alerts.loader import load_file
    p = tmp_path / "a.yaml"
    p.write_text(_alert("A", "ProbeSwitch", ["S"]).replace("sub_type: 18", f"sub_type: {raw}"),
                 encoding="utf-8")
    assert load_file(p).sub_type == 19


@pytest.mark.parametrize("raw", ['"\u00b2"', '"--19"'])
def test_isdigit_only_sub_type_string_gets_the_enum_error(tmp_path, raw):
    """isdigit() passes these but int() refuses them: the enum error, not a ValueError."""
    from vcfcf_core.alerts.loader import AlertValidationError, load_file
    p = tmp_path / "a.yaml"
    p.write_text(_alert("A", "ProbeSwitch", ["S"]).replace("sub_type: 18", f"sub_type: {raw}"),
                 encoding="utf-8")
    with pytest.raises(AlertValidationError, match="sub_type must be one of"):
        load_file(p)


def test_unicode_digit_sub_type_string_is_accepted(tmp_path):
    """int() reads any Unicode decimal digits, so Arabic-Indic "19" is 19."""
    from vcfcf_core.alerts.loader import load_file
    p = tmp_path / "a.yaml"
    p.write_text(_alert("A", "ProbeSwitch", ["S"]).replace(
        "sub_type: 18", 'sub_type: "\u0661\u0669"'), encoding="utf-8")
    assert load_file(p).sub_type == 19


def test_omitted_sub_type_defaults_to_a_valid_value(tmp_path):
    from vcfcf_core.alerts.loader import load_file
    p = tmp_path / "a.yaml"
    text = _alert("A", "ProbeSwitch", ["S"]).replace("sub_type: 18\n", "")
    assert "sub_type" not in text
    p.write_text(text, encoding="utf-8")
    assert load_file(p).sub_type == 19


def test_pak_bundled_alert_with_bad_sub_type_fails_both(tmp_path, monkeypatch):
    d = _project(tmp_path, symptoms=GOOD_SYMS[:1], alerts=[
        ("a.yaml", _alert("Switch Down", "ProbeSwitch", ["Switch Offline"], sub_type=1)),
    ])
    v, b = _both(d, monkeypatch)
    assert len(v) == 1 and "sub_type must be one of" in v[0] and "a.yaml" in v[0]
    assert "sub_type must be one of" in b and "a.yaml" in b

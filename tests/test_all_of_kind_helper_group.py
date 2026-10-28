""""All objects of a kind": custom group all_of_kind opt-in + View pin guard.

Evidence: knowledge/context/wire-formats/view_widget_all_objects_of_kind.md
(live 201 on POST /api/resources/groups for a condition-less rule; vendor
vmbro hardware vCommunity "Dell EMC Servers" UI export with "rules": []).

Covers:
  A. customgroup rule with all_of_kind: true and no conditions loads; the
     REST body (to_wire) matches the 201-accepted payload and the UI import
     ruleGroup (to_ui_wire) matches the vendor shape.
  B. no conditions without the opt-in still fails (explicit false too);
     unknown rule keys fail (typo next to the opt-in); all_of_kind combined
     with any condition fails; non-bool all_of_kind fails.
  C. a View widget with self_provider: true and no pin fails validation
     (the renderer would otherwise drop it to selfProvider:false); pinned to
     a helper group by name it renders the vendor shape.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

OWNER = "00000000-0000-0000-0000-000000000001"
GROUP = "[VCF Content Factory] All Applications"


def _cg(tmp_path: Path, rule: dict):
    from vcfcf_core.customgroups.loader import load_file

    p = tmp_path / "cg.yaml"
    p.write_text(yaml.safe_dump({"name": GROUP, "rules": [rule]}, sort_keys=False))
    return load_file(p)


_BASE_RULE = {"resource_kind": "(Custom) Application", "adapter_kind": "Container"}


# ---- A ----------------------------------------------------------------

def test_all_of_kind_rest_wire_matches_live_201_body(tmp_path):
    cg = _cg(tmp_path, {**_BASE_RULE, "all_of_kind": True})
    # The 201-accepted body from the wire doc, with the group name swapped
    # and resourceIdentifiers (always emitted by to_wire) added.
    assert cg.to_wire() == {
        "resourceKey": {"name": GROUP, "adapterKindKey": "Container",
                        "resourceKindKey": "Environment", "resourceIdentifiers": []},
        "autoResolveMembership": True,
        "membershipDefinition": {
            "includedResources": [], "excludedResources": [],
            "custom-group-properties": [],
            "rules": [{
                "resourceKindKey": {"resourceKind": "(Custom) Application",
                                    "adapterKind": "Container"},
                "statConditionRules": [], "propertyConditionRules": [],
                "resourceNameConditionRules": [], "relationshipConditionRules": [],
                "resourceTagConditionRules": [],
            }],
        },
    }


def test_all_of_kind_ui_wire_matches_vendor_rulegroup(tmp_path):
    cg = _cg(tmp_path, {**_BASE_RULE, "all_of_kind": True})
    ui = cg.to_ui_wire()
    group = ui["customGroups"][0]
    assert group["resourceKind"] == "Environment"
    assert group["adapterKind"] == "Container"
    assert group["autoResolveMembership"] is True
    assert group["membershipDefinition"] == {"ruleGroups": [
        {"resourceKind": "(Custom) Application", "adapterKind": "Container", "rules": []},
    ]}


def test_all_of_kind_false_with_conditions_still_loads(tmp_path):
    cg = _cg(tmp_path, {**_BASE_RULE, "all_of_kind": False,
                        "name": [{"op": "ENDS_WITH", "value": "Home"}]})
    assert cg.to_wire()["membershipDefinition"]["rules"][0]["resourceNameConditionRules"] == [
        {"name": "Home", "compareOperator": "ENDS_WITH"}]


# ---- B ----------------------------------------------------------------

def test_no_conditions_without_opt_in_fails(tmp_path):
    from vcfcf_core.customgroups.loader import CustomGroupValidationError

    with pytest.raises(CustomGroupValidationError,
                       match=r"at least one condition.*all_of_kind: true"):
        _cg(tmp_path, dict(_BASE_RULE))


@pytest.mark.parametrize("cond", [
    {"stat": [{"key": "cpu|usage_average", "op": "GT", "value": 1}]},
    {"property": [{"key": "summary|type", "op": "EQ", "value": "x"}]},
    {"name": [{"op": "CONTAINS", "value": "x"}]},
    {"relationship": [{"relation": "CHILD", "name": "x", "op": "EQ"}]},
    {"tag": [{"category": "Env", "op": "EQ", "value": "prod"}]},
])
def test_all_of_kind_with_condition_fails(tmp_path, cond):
    from vcfcf_core.customgroups.loader import CustomGroupValidationError

    with pytest.raises(CustomGroupValidationError, match="cannot be combined with conditions"):
        _cg(tmp_path, {**_BASE_RULE, "all_of_kind": True, **cond})


def test_explicit_false_without_conditions_fails(tmp_path):
    from vcfcf_core.customgroups.loader import CustomGroupValidationError

    with pytest.raises(CustomGroupValidationError, match="at least one condition"):
        _cg(tmp_path, {**_BASE_RULE, "all_of_kind": False})


@pytest.mark.parametrize("extra", [
    # misspelled condition key next to the opt-in: must not load as
    # an over-broad "every object of the kind" group
    {"all_of_kind": True, "properties": [{"key": "x", "op": "EQ", "value": "y"}]},
    {"name": [{"op": "CONTAINS", "value": "x"}], "stats": []},
    {"all_of_kind_s": True},
])
def test_unknown_rule_key_fails(tmp_path, extra):
    from vcfcf_core.customgroups.loader import CustomGroupValidationError

    with pytest.raises(CustomGroupValidationError, match="unknown key"):
        _cg(tmp_path, {**_BASE_RULE, **extra})


@pytest.mark.parametrize("val", ["yes", 1, "true", None])
def test_all_of_kind_must_be_bool(tmp_path, val):
    from vcfcf_core.customgroups.loader import CustomGroupValidationError

    with pytest.raises(CustomGroupValidationError, match="all_of_kind must be true or false"):
        _cg(tmp_path, {**_BASE_RULE, "all_of_kind": val})


# ---- C ----------------------------------------------------------------

def _dashboard(tmp_path: Path, widget_extra: dict):
    from vcfcf_dashboards.loader import load_dashboard, load_view

    vp = tmp_path / "v.yaml"
    vp.write_text(yaml.safe_dump({
        "name": "[VCF Content Factory] App Probe View",
        "subject": {"adapter_kind": "Container", "resource_kind": "(Custom) Application"},
        "columns": [{"attribute": "summary|total_number_vms", "display_name": "VMs"}]}))
    view = load_view(vp)
    dp = tmp_path / "d.yaml"
    dp.write_text(yaml.safe_dump({"name": "[VCF Content Factory] App Probe", "widgets": [{
        "id": "apps", "type": "View", "title": "Apps",
        "coords": {"x": 1, "y": 1, "w": 12, "h": 6},
        "view": view.name, "self_provider": True, **widget_extra}]}))
    return load_dashboard(dp), view


def test_view_self_provider_without_pin_fails(tmp_path):
    from vcfcf_dashboards.loader import DashboardValidationError

    d, view = _dashboard(tmp_path, {})
    with pytest.raises(DashboardValidationError,
                       match=r"View with self_provider=true requires a 'pin'.*"
                             r"all_of_kind: true.*view_widget_all_objects_of_kind\.md"):
        d.validate({view.name: view})


def test_view_pinned_to_helper_group_renders_vendor_shape(tmp_path):
    from vcfcf_dashboards.render import render_dashboards_bundle_json

    d, view = _dashboard(tmp_path, {"pin": {
        "adapter_kind": "Container", "resource_kind": "Environment", "name": GROUP}})
    d.validate({view.name: view})
    out = json.loads(render_dashboards_bundle_json([d], {view.name: view}, OWNER))
    assert out["entries"]["resource"] == [{
        "resourceKindKey": "Environment", "internalId": "resource:id:0_::_",
        "adapterKindKey": "Container", "identifiers": [], "name": GROUP}]
    cfg = out["dashboards"][0]["widgets"][0]["config"]
    assert cfg["selfProvider"] == {"selfProvider": True}
    assert cfg["resource"]["resourceId"] == "resource:id:0_::_"
    assert cfg["resource"]["resourceName"] == GROUP
    assert cfg["resource"]["resourceKindId"] == "002009ContainerEnvironment"
    assert cfg["resource"]["traversalSpecId"] == ""

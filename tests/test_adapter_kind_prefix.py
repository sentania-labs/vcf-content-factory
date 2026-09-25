"""resourceKindId adapter-kind prefix is computed, not looked up.

The prefix is "0020" + the adapter-kind key length as two digits. It used
to be a closed table in render.py, so a dashboard naming an adapter kind
outside the table (an SDK pak's own kind, e.g. unifi_controller) failed to
render with "no known resourceKindId prefix". Evidence for the formula:
all 363 resource kinds on the devel instance
(knowledge/context/api-surface/summary_dashboard_assignment.md), every
entry of the old table, and every 0020NN<adapterKind> string in the
reference corpus.
"""
from __future__ import annotations

import json
import uuid

import pytest

from vcfcf_core.dashboards.loader import (
    Dashboard,
    HeatmapConfig,
    HeatmapTab,
    Widget,
)
from vcfcf_core.dashboards.render import (
    adapter_kind_prefix,
    render_dashboards_bundle_json,
)
from vcfcf_core.dashboards.summary_bind import resource_kind_id

_OWNER_ID = "00000000-0000-0000-0000-000000000001"

# Every entry of the retired _ADAPTER_KIND_PREFIX table, verbatim.
_HARVESTED = {
    "VMWARE": "002006",
    "Container": "002009",
    "CASAdapter": "002010",
    "NSXTAdapter": "002011",
    "KubernetesAdapter": "002017",
    "VMWARE_INFRA_HEALTH": "002019",
    "VrAdapter": "002009",
}

# Seen in reference dashboards / knowledge but never in the table.
_CORPUS = {
    "APPOSUCP": "002008",
    "AmazonAWSAdapter": "002016",
    "FederatedAdapter": "002016",
    "VirtualAndPhysicalSANAdapter": "002028",
    "mpb_phpipam": "002011",
    "mpb_ubiquiti_unifi": "002018",
    "mpb_broadcom_security_advisories": "002032",
}


@pytest.mark.parametrize("adapter_kind,expected", sorted(_HARVESTED.items()))
def test_formula_matches_every_harvested_table_entry(adapter_kind, expected):
    assert adapter_kind_prefix(adapter_kind) == expected


@pytest.mark.parametrize("adapter_kind,expected", sorted(_CORPUS.items()))
def test_formula_matches_reference_corpus(adapter_kind, expected):
    assert adapter_kind_prefix(adapter_kind) == expected


@pytest.mark.parametrize(
    "adapter_kind,expected",
    [("unifi_controller", "002016"), ("synology_diskstation", "002020")],
)
def test_sdk_pak_adapter_kinds(adapter_kind, expected):
    assert adapter_kind_prefix(adapter_kind) == expected


def test_unseen_adapter_kind_is_computed():
    assert adapter_kind_prefix("x") == "002001"
    assert adapter_kind_prefix("never_seen_before_kind") == "002022"
    assert adapter_kind_prefix("a" * 99) == "002099"


@pytest.mark.parametrize("bad", ["", "a" * 100])
def test_unencodable_adapter_kind_rejected(bad):
    with pytest.raises(ValueError):
        adapter_kind_prefix(bad)


def test_resource_kind_id_uses_same_prefix():
    assert resource_kind_id("VMWARE", "HostSystem") == "002006VMWAREHostSystem"
    assert (
        resource_kind_id("unifi_controller", "UniFiSite")
        == "002016unifi_controllerUniFiSite"
    )


def _heatmap_dashboard(tab: HeatmapTab) -> Dashboard:
    widget = Widget(
        local_id="hm",
        type="Heatmap",
        title="Heatmap",
        coords={"x": 1, "y": 1, "w": 6, "h": 6},
        heatmap_config=HeatmapConfig(tabs=[tab]),
    )
    return Dashboard(
        id=str(uuid.uuid4()),
        name="Prefix Test",
        description="",
        widgets=[widget],
        interactions=[],
        name_path="Testing",
        shared=True,
        hidden=False,
    )


def _group_by(dashboard: Dashboard) -> dict:
    bundle = json.loads(
        render_dashboards_bundle_json([dashboard], {}, _OWNER_ID)
    )
    widget = bundle["dashboards"][0]["widgets"][0]
    return widget["config"]["configs"][0]["groupBy"]


def test_heatmap_explicit_group_by_on_sdk_adapter_kind():
    tab = HeatmapTab(
        name="Gateways",
        adapter_kind="unifi_controller",
        resource_kind="UniFiGateway",
        color_by_key="badge|health",
        group_by_adapter="unifi_controller",
        group_by_kind="UniFiSite",
        group_by_text="Site",
    )
    gb = _group_by(_heatmap_dashboard(tab))
    assert gb["id"] == "004null002016unifi_controllerUniFiSite"


def test_heatmap_self_group_on_sdk_adapter_kind():
    tab = HeatmapTab(
        name="Volumes",
        adapter_kind="synology_diskstation",
        resource_kind="SynologyVolume",
        color_by_key="badge|health",
    )
    gb = _group_by(_heatmap_dashboard(tab))
    assert gb["id"] == "004null002020synology_diskstationSynologyVolume"


def test_heatmap_vmware_group_by_unchanged():
    tab = HeatmapTab(
        name="VMs",
        adapter_kind="VMWARE",
        resource_kind="VirtualMachine",
        color_by_key="cpu|usage_average",
        group_by_kind="HostSystem",
    )
    gb = _group_by(_heatmap_dashboard(tab))
    assert gb["id"] == "004null002006VMWAREHostSystem"

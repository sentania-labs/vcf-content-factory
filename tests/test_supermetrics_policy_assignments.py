"""get_sm_policy_assignments parses the real policy export shape (issue #190).

The XML below mirrors the live Default Policy export recorded in
knowledge/context/investigations/policy_fragment_wire_format.md:
SuperMetrics blocks sit directly under PackageSettings (there is no
SuperMetricsCatalog wrapper), siblings of Metrics and Alerts.
"""
from __future__ import annotations

from vcfcf_supermetrics.client import VCFOpsClient

_POLICY_XML = """<?xml version="1.0" encoding="UTF-8"?><PolicyContent>
    <Policies>
        <Policy key="9c1d42be-09b7-4149-92fc-2224e3d778bd" name="Default">
            <PackageSettings>
                <Metrics adapterKind="VMWARE" resourceKind="VirtualMachine">
                    <Metric enabled="true" id="diskspace|snapshot|creator"/>
                </Metrics>
                <SuperMetrics adapterKind="VMWARE" resourceKind="vSphere World">
                    <SuperMetric enabled="true" id="C72131AD-EE25-4E89-8190-1C93D78EEB5A"/>
                    <SuperMetric enabled="false" id="8200eed9-6aa3-480d-bd7e-2b1fa81b8ee5"/>
                </SuperMetrics>
                <SuperMetrics adapterKind="VMWARE" resourceKind="ClusterComputeResource">
                    <SuperMetric enabled="true" id="c72131ad-ee25-4e89-8190-1c93d78eeb5a"/>
                </SuperMetrics>
            </PackageSettings>
        </Policy>
    </Policies>
</PolicyContent>"""


def test_supermetrics_directly_under_packagesettings():
    got = VCFOpsClient.get_sm_policy_assignments(_POLICY_XML)
    assert got == {
        "c72131ad-ee25-4e89-8190-1c93d78eeb5a": [
            {"adapter_kind_key": "VMWARE", "resource_kind_key": "vSphere World"},
            {"adapter_kind_key": "VMWARE",
             "resource_kind_key": "ClusterComputeResource"},
        ],
    }


def test_disabled_entries_and_metrics_ignored():
    got = VCFOpsClient.get_sm_policy_assignments(_POLICY_XML)
    assert "8200eed9-6aa3-480d-bd7e-2b1fa81b8ee5" not in got
    assert "diskspace|snapshot|creator" not in got

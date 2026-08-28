"""`view_details` YAML field -> widget config `viewDetails` passthrough.

Every widget on 9.x carries `config.viewDetails` (`""` when unset). The
factory emits it verbatim only when authored; omitting it must keep the
rendered bundle byte-identical to today. Accepted forms are the product's
click-handler contract: http(s) absolute, or a relative `/ui/` or
`/vcf-operations/ui/` Angular route (see
knowledge/context/api-surface/dashboard_widgets_alertvolume_section_viewdetails.md
§2). Public VMWARE kinds only.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

OWNER = "00000000-0000-0000-0000-000000000001"


def _write(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return path


def _widgets(view_details: dict | None = None) -> list:
    vd = view_details or {}
    ws = [
        {
            "id": "picker", "type": "ResourceList", "title": "VMs",
            "coords": {"x": 1, "y": 1, "w": 4, "h": 4},
            "resource_kinds": [{"adapter_kind": "VMWARE", "resource_kind": "VirtualMachine"}],
        },
        {
            "id": "kpi", "type": "Scoreboard", "title": "CPU",
            "coords": {"x": 5, "y": 1, "w": 4, "h": 4},
            "metrics": [{"adapter_kind": "VMWARE", "resource_kind": "VirtualMachine",
                         "metric_key": "cpu|usage_average", "metric_name": "CPU Usage"}],
        },
        {
            "id": "txt", "type": "TextDisplay", "title": "Notes",
            "coords": {"x": 9, "y": 1, "w": 4, "h": 4}, "html": "<b>hi</b>",
        },
        {
            "id": "hc", "type": "HealthChart", "title": "Health",
            "coords": {"x": 1, "y": 5, "w": 12, "h": 4},
            "adapter_kind": "VMWARE", "resource_kind": "HostSystem",
            "metric_key": "cpu|usage_average", "metric_name": "CPU",
        },
    ]
    for w in ws:
        if w["id"] in vd:
            w["view_details"] = vd[w["id"]]
    return ws


def _render_bytes(tmp_path: Path, name: str, widgets: list) -> str:
    from vcfops_dashboards.loader import load_dashboard
    from vcfops_dashboards.render import render_dashboards_bundle_json

    d = load_dashboard(_write(tmp_path / f"{name}.yaml", {
        "id": "11111111-2222-4333-8444-555555555555",
        "name": "[VCF Content Factory] View Details Test",
        "description": "",
        "widgets": widgets,
        "interactions": [{"from": "picker", "to": "kpi"}],
    }))
    d.validate({})
    return render_dashboards_bundle_json([d], {}, OWNER)


def test_omitted_is_byte_identical_and_absent(tmp_path):
    a = _render_bytes(tmp_path, "a", _widgets())
    b = _render_bytes(tmp_path, "b", _widgets({}))
    assert a == b
    assert "viewDetails" not in a


def test_emitted_verbatim_on_every_widget_type(tmp_path):
    vd = {
        "picker": "",
        "kpi": "/ui/operate/dashboards/dashboards;tabId=11111111-2222-4333-8444-555555555555",
        "txt": "https://example.invalid/runbook?x=1&y=2",
        "hc": "/vcf-operations/ui/operate/alerts;tab=alerts",
    }
    out = json.loads(_render_bytes(tmp_path, "c", _widgets(vd)))
    by_title = {w["title"]: w for w in out["dashboards"][0]["widgets"]}
    assert by_title["VMs"]["config"]["viewDetails"] == ""
    assert by_title["CPU"]["config"]["viewDetails"] == vd["kpi"]
    assert by_title["Notes"]["config"]["viewDetails"] == vd["txt"]
    assert by_title["Health"]["config"]["viewDetails"] == vd["hc"]


def test_only_authored_widgets_carry_it(tmp_path):
    out = json.loads(_render_bytes(tmp_path, "d", _widgets({"kpi": "https://example.invalid/x"})))
    by_title = {w["title"]: w for w in out["dashboards"][0]["widgets"]}
    assert by_title["CPU"]["config"]["viewDetails"] == "https://example.invalid/x"
    for t in ("VMs", "Notes", "Health"):
        assert "viewDetails" not in by_title[t]["config"]


@pytest.mark.parametrize("bad", [
    "dashboard.action?mainAction=x",
    "#/dashboard/abc",
    "ui/operate/alerts",
    "ftp://example.invalid/x",
    "anything goes",
])
def test_unresolvable_forms_rejected(tmp_path, bad):
    from vcfops_dashboards.loader import DashboardValidationError, load_dashboard

    path = _write(tmp_path / "bad_form.yaml", {
        "name": "[VCF Content Factory] View Details Test",
        "widgets": _widgets({"kpi": bad}),
    })
    with pytest.raises(DashboardValidationError, match="view_details .* must start with one of"):
        load_dashboard(path)


def test_http_prefix_accepted_and_stripped(tmp_path):
    out = json.loads(_render_bytes(tmp_path, "g", _widgets({"kpi": "  http://example.invalid/x  "})))
    by_title = {w["title"]: w for w in out["dashboards"][0]["widgets"]}
    assert by_title["CPU"]["config"]["viewDetails"] == "http://example.invalid/x"


def test_non_string_rejected(tmp_path):
    from vcfops_dashboards.loader import DashboardValidationError, load_dashboard

    ws = _widgets()
    ws[1]["view_details"] = 42
    path = _write(tmp_path / "e.yaml", {
        "name": "[VCF Content Factory] View Details Test",
        "widgets": ws,
    })
    with pytest.raises(DashboardValidationError, match="view_details must be a string"):
        load_dashboard(path)


def test_section_rejects_view_details(tmp_path):
    from vcfops_dashboards.loader import DashboardValidationError, load_dashboard

    path = _write(tmp_path / "f.yaml", {
        "name": "[VCF Content Factory] View Details Test",
        "widgets": [
            {"id": "s", "type": "Section", "title": "S", "coords": {"x": 1, "y": 1},
             "view_details": "https://example.invalid/nope"},
        ],
    })
    with pytest.raises(DashboardValidationError, match="Section must not carry"):
        load_dashboard(path)

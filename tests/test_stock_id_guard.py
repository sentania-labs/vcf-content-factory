"""Stock content id guard (issue #345): content must not ship under an id
VCF Operations ships as its own.

Every id and name here is made up. The real baseline
(``src/vcfcf_core/stock_ids/stock_ids_baseline.json``) is only loaded by
``test_packaged_baseline_loads``; every other test points the guard at a
synthetic baseline written to ``tmp_path``.
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vcfcf_core.stock_ids import guard  # noqa: E402
from vcfcf_core.stock_ids import generate as gen  # noqa: E402

# Made-up stock ids, one per content type.
STOCK = {
    "view": ("aaaa0001-0000-4000-8000-000000000001", "Stock Probe View"),
    "dashboard": ("aaaa0002-0000-4000-8000-000000000002", "Stock Probe Dashboard"),
    "report": ("aaaa0003-0000-4000-8000-000000000003", "Stock Probe Report"),
    "supermetric": ("aaaa0004-0000-4000-8000-000000000004", "Stock Probe Super Metric"),
    "symptom": ("SymptomDefinition-PROBEKIND-StockProbeSymptom", "Stock probe symptom"),
    "alert": ("AlertDefinition-PROBEKIND-StockProbeAlert", "Stock probe alert"),
    "recommendation": ("Recommendation-df-PROBEKIND-StockProbeRec", "Stock probe recommendation"),
}
OWN = {
    "view": "bbbb0001-0000-4000-8000-000000000001",
    "dashboard": "bbbb0002-0000-4000-8000-000000000002",
    "report": "bbbb0003-0000-4000-8000-000000000003",
}


def _baseline_dict() -> dict:
    return {
        "format": guard.BASELINE_FORMAT,
        "ids": {
            t: {oid: {"name": name, "versions": ["8.18.7", "9.1.1"]}}
            for t, (oid, name) in STOCK.items()
        },
    }


@pytest.fixture
def baseline_path(tmp_path, monkeypatch) -> Path:
    """A synthetic baseline, also installed as the default for every caller."""
    p = tmp_path / "baseline" / guard.BASELINE_FILE_NAME
    p.parent.mkdir()
    p.write_text(json.dumps(_baseline_dict()), encoding="utf-8")
    monkeypatch.setattr(guard, "default_baseline_path", lambda: p)
    guard._CACHE.clear()
    yield p
    guard._CACHE.clear()


@pytest.fixture
def baseline(baseline_path) -> guard.StockBaseline:
    return guard.load_baseline(baseline_path)


# ---------------------------------------------------------------------------
# Synthetic artifacts
# ---------------------------------------------------------------------------

def _views_xml(*ids_titles) -> bytes:
    body = "".join(
        f'<ViewDef id="{i}"><Title localizationKey="title">{t}</Title></ViewDef>'
        for i, t in ids_titles
    )
    return f'<?xml version="1.0"?><Content><Views>{body}</Views></Content>'.encode()


def _report_xml(report_id: str, view_ref: str) -> bytes:
    return (
        f'<Content><Reports><ReportDef id="{report_id}"><Title>Probe Report</Title>'
        f'<Sections><Section><View id="{view_ref}"/></Section></Sections>'
        f"</ReportDef></Reports></Content>"
    ).encode()


def _dashboard_json(dash_id: str, view_ref: str = "") -> bytes:
    widget = {"type": "View", "config": {"viewDefinitionId": view_ref}} if view_ref else {}
    return json.dumps({"entries": {}, "uuid": "x", "dashboards": [
        {"id": dash_id, "name": "Probe Dashboard", "widgets": [widget] if widget else []},
    ]}).encode()


def _sm_json(sm_id: str) -> bytes:
    return json.dumps({sm_id: {"name": "Probe SM", "formula": "1"}}).encode()


def _alert_content(symptom_id=None, alert_id=None, rec_key=None, refs_only=False) -> bytes:
    parts = ["<alertContent>"]
    if alert_id:
        recs = f'<Recommendations><Recommendation priority="1" ref="{rec_key}"/></Recommendations>' if rec_key else ""
        parts.append(
            f'<AlertDefinitions><AlertDefinition id="{alert_id}" name="probe alert" '
            f'adapterKind="PROBEKIND"><State><SymptomSet ref="{symptom_id}"/>{recs}</State>'
            f"</AlertDefinition></AlertDefinitions>"
        )
    if symptom_id and not refs_only:
        parts.append(
            f'<SymptomDefinitions><SymptomDefinition id="{symptom_id}" name="probe symptom" '
            f'adapterKind="PROBEKIND"/></SymptomDefinitions>'
        )
    if rec_key and not refs_only:
        parts.append(f'<Recommendations><Recommendation key="{rec_key}"><Description>d</Description>'
                     f"</Recommendation></Recommendations>")
    parts.append("</alertContent>")
    return "".join(parts).encode()


def _definition_artifact(ctype: str) -> bytes:
    oid = STOCK[ctype][0]
    if ctype == "view":
        return _views_xml((oid, "Copied View"))
    if ctype == "dashboard":
        return _dashboard_json(oid)
    if ctype == "report":
        return _report_xml(oid, OWN["view"])
    if ctype == "supermetric":
        return _sm_json(oid)
    if ctype == "symptom":
        return _alert_content(symptom_id=oid)
    if ctype == "alert":
        return _alert_content(alert_id=oid, symptom_id="SymptomDefinition-PROBEKIND-own")
    if ctype == "recommendation":
        return _alert_content(rec_key=oid)
    raise AssertionError(ctype)


def _zip(members: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _synthetic_pak(stock: bool = True) -> bytes:
    view_id = STOCK["view"][0] if stock else OWN["view"]
    views_zip = _zip({"content.xml": _views_xml((view_id, "Pak View"), (OWN["view"], "Own View"))})
    adapters = _zip({"probe/conf/views/views.zip": views_zip, "probe/conf/describe.xml": "<AdapterKind/>"})
    return _zip({
        "manifest.txt": "{}",
        "adapters.zip": adapters,
        "content/dashboards/probe/dashboard.json": _dashboard_json(OWN["dashboard"], view_ref=STOCK["view"][0]),
    })


# ---------------------------------------------------------------------------
# The check: one definition hit per type, references never hit
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ctype", list(STOCK))
def test_definition_hit_per_type(ctype, baseline):
    defs = guard.scan_bytes(_definition_artifact(ctype), "probe/file.xml")
    result = guard.check_definitions(defs, baseline=baseline)
    assert len(result.errors) == 1, result.errors
    msg = result.errors[0]
    oid, name = STOCK[ctype]
    assert "probe/file.xml" in msg            # the file
    assert oid in msg                         # the id
    assert guard.type_label(ctype) in msg     # the content type
    assert repr(name) in msg                  # the stock object's name
    assert "8.18.7, 9.1.1" in msg             # the versions it is stock in


def test_definition_hit_is_case_insensitive_on_id(baseline):
    defs = guard.scan_bytes(_views_xml((STOCK["view"][0].upper(), "x")), "f.xml")
    assert len(guard.check_definitions(defs, baseline=baseline).errors) == 1


def test_references_to_stock_ids_do_not_hit(baseline):
    """A widget, report section, symptom set, recommendation ref or policy
    enablement pointing at a stock id is a reference, not a definition."""
    artifacts = [
        _dashboard_json(OWN["dashboard"], view_ref=STOCK["view"][0]),
        _report_xml(OWN["report"], view_ref=STOCK["view"][0]),
        _alert_content(symptom_id=STOCK["symptom"][0], alert_id="AlertDefinition-PROBEKIND-own",
                       rec_key=STOCK["recommendation"][0], refs_only=True),
        f'<PolicyContent><SuperMetric enabled="true" id="{STOCK["supermetric"][0]}"/></PolicyContent>'.encode(),
    ]
    for data in artifacts:
        defs = guard.scan_bytes(data, "ref.file")
        assert guard.check_definitions(defs, baseline=baseline).errors == [], data


def test_loaded_objects_are_checked_by_their_id(baseline):
    view = SimpleNamespace(id=STOCK["view"][0], name="Copied", source_path=Path("views/copied.yaml"))
    own = SimpleNamespace(id=OWN["view"], name="Own", source_path=Path("views/own.yaml"))
    defs = guard.bundled_definitions(views=[view, own])
    result = guard.check_definitions(defs, baseline=baseline)
    assert len(result.errors) == 1 and "views/copied.yaml" in result.errors[0]


def test_rendered_alert_content_is_attributed_to_its_yaml(baseline):
    sym = SimpleNamespace(name="probe symptom", source_path=Path("symptoms/probe.yaml"))
    xml = _alert_content(symptom_id=STOCK["symptom"][0]).decode()
    defs = guard.bundled_definitions(symptoms=[sym], alert_content_xml=xml)
    result = guard.check_definitions(defs, baseline=baseline)
    assert len(result.errors) == 1 and "symptoms/probe.yaml" in result.errors[0]


def test_malformed_xml_still_reports_its_definitions(baseline):
    data = f'<Content><ViewDef id="{STOCK["view"][0]}"><Title>x</Title><broken'.encode()
    defs = guard.scan_bytes(data, "broken.xml")
    assert [d.id for d in defs] == [STOCK["view"][0]]
    assert guard.check_definitions(defs, baseline=baseline).errors


def test_deeply_nested_files_do_not_crash_the_scan(baseline):
    depth = 5000
    xml = ("<a>" * depth + f'<ViewDef id="{STOCK["view"][0]}"><Title>x</Title></ViewDef>'
           + "</a>" * depth).encode()
    assert [d.id for d in guard.scan_bytes(xml, "deep.xml")] == [STOCK["view"][0]]
    deep_json = ("[" * 50000 + "]" * 50000).encode()
    unreadable = []
    assert guard.scan_bytes(b'{"dashboards": ' + deep_json + b"}", "deep.json",
                            unreadable=unreadable) == []
    # Not a crash. Where the interpreter cannot parse that depth, the file
    # is recorded as unreadable rather than reported clean.
    assert [u.location for u in unreadable] in ([], ["deep.json"])


# ---------------------------------------------------------------------------
# Allowlist
# ---------------------------------------------------------------------------

def test_allowlisted_hit_is_a_warning_with_its_reason(baseline):
    allow = guard.parse_allowlist(
        [{"type": "view", "id": STOCK["view"][0], "reason": "deliberate probe override"}],
        "bundles/probe.yaml",
    )
    defs = guard.scan_bytes(_definition_artifact("view"), "f.xml")
    result = guard.check_definitions(defs, baseline=baseline, allowlist=allow)
    assert result.errors == []
    assert len(result.warnings) == 1
    assert "ALLOWLISTED" in result.warnings[0]
    assert "deliberate probe override" in result.warnings[0]
    assert "bundles/probe.yaml" in result.warnings[0]


def test_allowlist_entry_for_another_type_does_not_cover(baseline):
    allow = guard.parse_allowlist(
        [{"type": "dashboard", "id": STOCK["view"][0], "reason": "wrong type"}], "m.yaml",
    )
    defs = guard.scan_bytes(_definition_artifact("view"), "f.xml")
    result = guard.check_definitions(defs, baseline=baseline, allowlist=allow)
    assert len(result.errors) == 1
    assert any("matches no definition" in w for w in result.warnings)


def test_unused_allowlist_entry_warns(baseline):
    allow = guard.parse_allowlist(
        [{"type": "view", "id": STOCK["view"][0], "reason": "stale"}], "m.yaml",
    )
    result = guard.check_definitions([], baseline=baseline, allowlist=allow)
    assert result.errors == []
    assert any("matches no definition" in w and "remove it" in w for w in result.warnings)


@pytest.mark.parametrize("raw, fragment", [
    ({"type": "view", "id": "x"}, "reason is required"),
    ([{"type": "view", "id": "x", "reason": "  "}], "reason is required"),
    ([{"type": "view", "id": "x"}], "reason is required"),
    ([{"type": "widget", "id": "x", "reason": "r"}], "type must be one of"),
    ([{"type": "view", "reason": "r"}], "id is required"),
    ([{"type": "view", "id": "x", "reason": "r", "extra": 1}], "unknown key"),
    ([{"type": "view", "id": "x", "reason": "r"}, {"type": "view", "id": "X", "reason": "r"}], "twice"),
    (["view x"], "must be a mapping"),
])
def test_malformed_allowlist_is_refused(raw, fragment):
    if isinstance(raw, dict):
        fragment = "must be a list"
    with pytest.raises(guard.StockIdAllowlistError, match=fragment):
        guard.parse_allowlist(raw, "adapter.yaml")


def test_allowlist_is_absent_by_default():
    assert guard.parse_allowlist(None, "adapter.yaml") == []


# ---------------------------------------------------------------------------
# Fail closed: an unloadable baseline is never a pass
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text, fragment", [
    (None, "cannot be read"),
    ("{not json", "not valid JSON"),
    (json.dumps({"format": "other/1", "ids": {}}), "format"),
    (json.dumps({"format": guard.BASELINE_FORMAT, "ids": {}}), "holds no ids"),
    (json.dumps({"format": guard.BASELINE_FORMAT, "ids": {"widget": {"a": {"name": "", "versions": ["1"]}}}}),
     "unknown content type"),
    (json.dumps({"format": guard.BASELINE_FORMAT, "ids": {"view": {"a": {"name": "n", "versions": []}}}}),
     "versions"),
])
def test_unloadable_baseline_raises(tmp_path, text, fragment):
    p = tmp_path / "b.json"
    if text is not None:
        p.write_text(text, encoding="utf-8")
    guard._CACHE.clear()
    with pytest.raises(guard.StockIdBaselineError, match=fragment):
        guard.load_baseline(p)


@pytest.fixture
def no_baseline(tmp_path, monkeypatch):
    missing = tmp_path / "gone" / guard.BASELINE_FILE_NAME
    monkeypatch.setattr(guard, "default_baseline_path", lambda: missing)
    guard._CACHE.clear()
    yield missing
    guard._CACHE.clear()


def _project(**kw):
    base = dict(name="Probe Pak", source_path=Path("adapter.yaml"), stock_id_allowlist=None)
    base.update(kw)
    return SimpleNamespace(**base)


def _bundled(views=(), dashboards=()):
    return (list(views), list(dashboards), [], [], [], [], [])


def test_sdk_check_fails_closed_without_baseline(no_baseline):
    from vcfcf_managementpacks import sdk_builder as sb
    errors, _ = sb.check_stock_ids(_project(), _bundled())
    assert errors and "cannot be read" in errors[0]


def test_validate_fails_closed_without_baseline(no_baseline, capsys):
    from vcfcf_packaging.stock_ids import report_stock_ids
    assert report_stock_ids([], "views") == 1
    assert "cannot be read" in capsys.readouterr().err


def test_bundle_build_fails_closed_without_baseline(no_baseline):
    from vcfcf_core.packaging.loader import BundleValidationError
    from vcfcf_packaging.stock_ids import guard_bundle
    with pytest.raises(BundleValidationError, match="cannot be read"):
        guard_bundle(_bundle(), None, "bundle 'probe'")


def test_content_import_fails_closed_without_baseline(no_baseline):
    from vcfcf_dashboards.client import VCFOpsError, import_content_zip
    with pytest.raises(VCFOpsError, match="cannot run, import refused"):
        import_content_zip(_UnusedClient(), _zip({"x.txt": "x"}))


# ---------------------------------------------------------------------------
# Wiring: validate-sdk / build-sdk, bundles, validate, import, pak install
# ---------------------------------------------------------------------------

def test_sdk_check_refuses_bundled_stock_view(baseline_path):
    from vcfcf_managementpacks import sdk_builder as sb
    view = SimpleNamespace(id=STOCK["view"][0], name="Copied", source_path=Path("views/copied.yaml"))
    errors, warnings = sb.check_stock_ids(_project(), _bundled(views=[view]))
    assert len(errors) == 1
    assert "views/copied.yaml" in errors[0] and STOCK["view"][0] in errors[0]
    assert warnings == []


def test_sdk_check_honours_adapter_yaml_allowlist(baseline_path):
    from vcfcf_managementpacks import sdk_builder as sb
    view = SimpleNamespace(id=STOCK["view"][0], name="Copied", source_path=Path("views/copied.yaml"))
    project = _project(stock_id_allowlist=[
        {"type": "view", "id": STOCK["view"][0], "reason": "probe reason"},
    ])
    errors, warnings = sb.check_stock_ids(project, _bundled(views=[view]))
    assert errors == []
    assert len(warnings) == 1 and "probe reason" in warnings[0]


def test_sdk_check_rejects_malformed_allowlist(baseline_path):
    from vcfcf_managementpacks import sdk_builder as sb
    errors, _ = sb.check_stock_ids(_project(stock_id_allowlist=[{"type": "view"}]), _bundled())
    assert errors and "stock_id_allowlist" in errors[0]


def test_adapter_yaml_allowlist_must_be_a_list(tmp_path):
    from vcfcf_managementpacks.sdk_project import SdkProjectError, load_sdk_project
    y = tmp_path / "adapter.yaml"
    y.write_text(
        "name: Probe\nversion: 1.0.0\nbuild_number: 1\nadapter_kind: vcfcf_probe\n"
        "tier: 2\nstock_id_allowlist: yes\n", encoding="utf-8",
    )
    with pytest.raises(SdkProjectError, match="stock_id_allowlist"):
        load_sdk_project(y)
    y.write_text(
        "name: Probe\nversion: 1.0.0\nbuild_number: 1\nadapter_kind: vcfcf_probe\n"
        "tier: 2\nstock_id_allowlist:\n  - {type: view, id: x, reason: r}\n", encoding="utf-8",
    )
    assert load_sdk_project(y).stock_id_allowlist == [{"type": "view", "id": "x", "reason": "r"}]


@pytest.mark.parametrize("release", [False, True])
def test_built_pak_scan_fails_the_build(baseline_path, tmp_path, release):
    from vcfcf_managementpacks import sdk_builder as sb
    pak = tmp_path / "probe.pak"
    pak.write_bytes(_synthetic_pak(stock=True))
    with pytest.raises(sb.SdkBuildError, match="stock-id guard"):
        sb._gate_built_pak_stock_ids(pak, _project(), release_build=release)
    assert pak.exists() is (not release)


def test_built_pak_scan_passes_a_clean_pak(baseline_path, tmp_path):
    from vcfcf_managementpacks import sdk_builder as sb
    pak = tmp_path / "probe.pak"
    pak.write_bytes(_synthetic_pak(stock=False))
    sb._gate_built_pak_stock_ids(pak, _project(), release_build=True)
    assert pak.exists()


def _bundle(**kw):
    from vcfcf_core.packaging.loader import Bundle
    base = dict(name="probe", description="", sync_enabled=True, supermetrics=[], views=[],
                dashboards=[], customgroups=[])
    base.update(kw)
    return Bundle(**base)


def test_bundle_build_refuses_stock_dashboard(baseline_path):
    from vcfcf_core.packaging.loader import BundleValidationError
    from vcfcf_packaging.stock_ids import guard_bundle
    dash = SimpleNamespace(id=STOCK["dashboard"][0], name="Copied", source_path=Path("dashboards/c.yaml"))
    with pytest.raises(BundleValidationError) as exc:
        guard_bundle(_bundle(dashboards=[dash]), None, "bundle 'probe'")
    assert "dashboards/c.yaml" in str(exc.value) and STOCK["dashboard"][0] in str(exc.value)


def test_bundle_build_scans_the_assembled_zip(baseline_path):
    from vcfcf_core.packaging.loader import BundleValidationError
    from vcfcf_packaging.stock_ids import guard_bundle
    zip_bytes = _zip({"bundles/probe/content/views_content.xml": _views_xml((STOCK["view"][0], "x"))})
    with pytest.raises(BundleValidationError, match="views_content.xml"):
        guard_bundle(_bundle(), zip_bytes, "bundle 'probe'")


def test_bundle_manifest_allowlist(baseline_path, tmp_path, capsys):
    from vcfcf_core.packaging.loader import load_bundle
    from vcfcf_packaging.stock_ids import guard_bundle
    manifest = tmp_path / "probe.yaml"
    manifest.write_text(
        "name: probe\nstock_id_allowlist:\n"
        f"  - type: dashboard\n    id: {STOCK['dashboard'][0]}\n    reason: probe keeps it\n",
        encoding="utf-8",
    )
    b = load_bundle(manifest)
    dash = SimpleNamespace(id=STOCK["dashboard"][0], name="Copied", source_path=Path("d.yaml"))
    b.dashboards = [dash]
    guard_bundle(b, None, "bundle 'probe'")
    assert "probe keeps it" in capsys.readouterr().err


def test_bundle_manifest_allowlist_without_reason_fails_to_load(tmp_path):
    from vcfcf_core.packaging.loader import BundleValidationError, load_bundle
    manifest = tmp_path / "probe.yaml"
    manifest.write_text("name: probe\nstock_id_allowlist:\n  - {type: view, id: x}\n", encoding="utf-8")
    with pytest.raises(BundleValidationError, match="reason is required"):
        load_bundle(manifest)


def test_validate_reports_stock_ids(baseline_path, capsys, monkeypatch):
    import vcfcf_packaging.stock_ids as ps
    monkeypatch.setattr(ps, "repo_manifest_allowlists", lambda root=None: [])
    defs = guard.bundled_definitions(views=[
        SimpleNamespace(id=STOCK["view"][0], name="Copied", source_path=Path("content/views/c.yaml")),
    ])
    assert ps.report_stock_ids(defs, "views") == 1
    err = capsys.readouterr().err
    assert "STOCK-ID:" in err and "content/views/c.yaml" in err


def test_repo_allowlist_reads_manifests(tmp_path):
    from vcfcf_packaging.stock_ids import repo_manifest_allowlists
    (tmp_path / "bundles").mkdir()
    (tmp_path / "third_party" / "proj").mkdir(parents=True)
    (tmp_path / "bundles" / "a.yaml").write_text(
        "name: a\nviews:\n  - content/views/a.yaml\n"
        "stock_id_allowlist:\n  - {type: view, id: v1, reason: because}\n", encoding="utf-8")
    (tmp_path / "third_party" / "proj" / "PROJECT.yaml").write_text(
        "name: p\nstock_id_allowlist:\n  - {type: dashboard, id: d1, reason: because}\n", encoding="utf-8")
    manifests = repo_manifest_allowlists(tmp_path)
    assert {(e.type, e.id) for m in manifests for e in m.entries} == {("view", "v1"), ("dashboard", "d1")}
    bundle, project = sorted(manifests, key=lambda m: m.manifest)
    assert bundle.owns(str(tmp_path / "content" / "views" / "a.yaml"))
    assert not bundle.owns(str(tmp_path / "content" / "views" / "b.yaml"))
    assert project.owns(str(tmp_path / "third_party" / "proj" / "dashboards" / "d.yaml"))
    assert not project.owns(str(tmp_path / "content" / "views" / "a.yaml"))


class _UnusedClient:
    """A client the guard must refuse before touching."""

    def __getattr__(self, name):
        raise AssertionError(f"import reached the client ({name}) despite the guard")


def test_content_import_refuses_stock_definition(baseline_path, monkeypatch):
    from vcfcf_dashboards.client import VCFOpsError, import_content_zip
    blob = _zip({"views.zip": _zip({"content.xml": _views_xml((STOCK["view"][0], "x"))})})
    with pytest.raises(VCFOpsError, match="Import refused"):
        import_content_zip(_UnusedClient(), blob)


def test_pak_install_refuses_stock_ids_unless_allowed(baseline_path, tmp_path, capsys):
    from vcfcf_managementpacks.installer import _preflight_stock_ids
    pak = tmp_path / "third_party.pak"
    pak.write_bytes(_synthetic_pak(stock=True))
    with pytest.raises(SystemExit):
        _preflight_stock_ids(pak, allow=False)
    assert "--allow-stock-ids" in capsys.readouterr().err
    _preflight_stock_ids(pak, allow=True)
    assert "installing anyway" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Standalone check (third-party paks, exports): read-only
# ---------------------------------------------------------------------------

def _run_check(*args):
    import os
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC)
    return subprocess.run(
        [sys.executable, "-m", "vcfcf_packaging", "stock-id-check", *args],
        capture_output=True, text=True, env=env, cwd=str(REPO_ROOT), timeout=120,
    )


def test_standalone_check_packed_pak(baseline_path, tmp_path):
    pak = tmp_path / "upstream.pak"
    pak.write_bytes(_synthetic_pak(stock=True))
    before = pak.read_bytes()
    r = _run_check(str(pak), "--baseline", str(baseline_path))
    assert r.returncode == 2, r.stdout + r.stderr
    assert f"STOCK view {STOCK['view'][0]} 'Stock Probe View'" in r.stdout
    assert "shipped as 'Pak View'" in r.stdout
    assert "view: 1 stock of 2" in r.stdout          # the reference in the dashboard is not counted
    assert "dashboard: 0 stock of 1" in r.stdout
    assert pak.read_bytes() == before                 # read-only


def test_standalone_check_unpacked_pak_and_export(baseline_path, tmp_path):
    root = tmp_path / "unpacked"
    (root / "content" / "reports" / "set").mkdir(parents=True)
    (root / "content" / "reports" / "set" / "View - Set 1.xml").write_bytes(
        _views_xml((STOCK["view"][0], "a"), (OWN["view"], "b")))
    (root / "content" / "supermetrics").mkdir()
    (root / "content" / "supermetrics" / "sm.json").write_bytes(_sm_json(STOCK["supermetric"][0]))
    export = tmp_path / "export.zip"
    export.write_bytes(_zip({"DASHBOARDS.zip": _zip({"dashboards/owner": _zip({
        "dashboard/dashboard.json": _dashboard_json(STOCK["dashboard"][0])})})}))
    r = _run_check(str(root), str(export), "--baseline", str(baseline_path))
    assert r.returncode == 2, r.stdout + r.stderr
    assert "stock-id check: 3 definition(s)" in r.stdout


def test_standalone_check_clean_and_unusable(baseline_path, tmp_path):
    pak = tmp_path / "clean.pak"
    pak.write_bytes(_synthetic_pak(stock=False))
    assert _run_check(str(pak), "--baseline", str(baseline_path)).returncode == 0
    assert _run_check(str(pak), "--baseline", str(tmp_path / "missing.json")).returncode == 1
    assert _run_check(str(tmp_path / "nope.pak"), "--baseline", str(baseline_path)).returncode == 1


# ---------------------------------------------------------------------------
# Generator: how an id is shown to be stock
# ---------------------------------------------------------------------------

def _obs(ctype, oid, name, inst, version, **attrs):
    return gen.Observation(ctype, oid, name, inst, version, attrs)


def test_generator_purity_rules():
    obs = [
        # corroborated on two instances: stock
        _obs("view", "v-two", "Two Labs", "A", "8.18.7", localized="1"),
        _obs("view", "v-two", "Two Labs", "B", "9.1.1", localized="1"),
        # one instance, no corroboration: candidate
        _obs("view", "v-one", "One Lab", "A", "8.18.7", localized="1"),
        # factory marker on two instances: candidate
        _obs("view", "v-fac", "[VCF Content Factory] Mine", "A", "8.18.7"),
        _obs("view", "v-fac", "[VCF Content Factory] Mine", "B", "9.1.1"),
        # the current factory prefix is a marker too
        _obs("view", "v-fac-cf", "[VCF CF] Mine", "A", "8.18.7"),
        _obs("view", "v-fac-cf", "[VCF CF] Mine", "B", "9.1.1"),
        # factory id without a marker: candidate
        _obs("view", "v-minted", "Unmarked", "A", "8.18.7"),
        _obs("view", "v-minted", "Unmarked", "B", "9.1.1"),
        # a custom-scope export lists it: candidate
        _obs("dashboard", "d-custom", "Custom", "A", "8.18.7"),
        _obs("dashboard", "d-custom", "Custom", "B", "9.1.1"),
        # a pak installed on both labs explains its views: candidate
        _obs("view", "v-pak1", "Pak 1", "A", "8.18.7"),
        _obs("view", "v-pak1", "Pak 1", "B", "9.1.1"),
        _obs("view", "v-pak2", "Pak 2", "A", "8.18.7"),
        _obs("view", "v-pak2", "Pak 2", "B", "9.1.1"),
        # one instance, localized, copied by a package not installed there: stock
        _obs("view", "v-copied", "Copied Stock", "B", "9.1.1", localized="1"),
        # same, but not localized: candidate
        _obs("view", "v-copied-raw", "Copied Raw", "B", "9.1.1"),
        # an excluded adapter kind: candidate
        _obs("alert", "AlertDefinition-mypak-x", "x", "A", "8.18.7", adapterKind="mypak_kind"),
        _obs("alert", "AlertDefinition-mypak-x", "x", "B", "9.1.1", adapterKind="mypak_kind"),
        # one instance alert: needs two
        _obs("alert", "AlertDefinition-one", "y", "A", "8.18.7"),
    ]
    pak = [guard.Definition("view", "v-pak1", "Pak 1", "p"), guard.Definition("view", "v-pak2", "Pak 2", "p")]
    upstream = [guard.Definition("view", i, "", "u") for i in ("v-copied", "v-copied-raw", "u-own1", "u-own2")]
    build = gen.build_baseline(
        obs,
        known_groups={"installed-pak": pak, "upstream": upstream},
        custom_ids=[("dashboard", "d-custom")],
        factory_ids=["V-MINTED"],
        exclude_adapter_kind_prefixes=["mypak_"],
    )
    ids = build.baseline["ids"]
    assert set(ids["view"]) == {"v-two", "v-copied"}
    assert ids["view"]["v-two"] == {"name": "Two Labs", "versions": ["8.18.7", "9.1.1"]}
    assert ids["view"]["v-copied"]["versions"] == ["9.1.1"]
    assert "dashboard" not in ids and "alert" not in ids
    reasons = {c.id: c.reason for c in build.candidates}
    assert "one clean instance" in reasons["v-one"]
    assert "marker" in reasons["v-fac"]
    assert "[VCF CF]" in reasons["v-fac-cf"]
    assert "factory id" in reasons["v-minted"]
    assert "custom-scope" in reasons["d-custom"]
    assert "installed-pak is installed" in reasons["v-pak1"]
    assert "localizationKey" in reasons["v-copied-raw"]
    assert "adapter kind" in reasons["AlertDefinition-mypak-x"]
    assert "needs two" in reasons["AlertDefinition-one"]
    assert build.baseline["candidates_not_included"]["view"] == 7


def test_generator_policy_copies_are_not_observations():
    defs = [guard.Definition("symptom", "s1", "n", "policy.xml", {"in_policy": "1"}),
            guard.Definition("symptom", "s2", "n", "symptomdefs.xml")]
    obs = gen.observations_from_definitions(defs, "A", "9.1.1")
    assert [o.id for o in obs] == ["s2"]


def test_generator_output_round_trips_through_the_loader(tmp_path):
    obs = [_obs("view", "v1", "Two", "A", "8.18.7"), _obs("view", "v1", "Two", "B", "9.0.2")]
    text = gen.render_baseline_json(gen.build_baseline(obs).baseline)
    p = tmp_path / "b.json"
    p.write_text(text, encoding="utf-8")
    guard._CACHE.clear()
    b = guard.load_baseline(p)
    assert b.lookup("view", "V1").versions == ("8.18.7", "9.0.2")
    guard._CACHE.clear()


def test_inventory_parses_id_name_lines():
    obs = gen.parse_inventory("# comment\nAlertDefinition-x  An alert\n\nAlertDefinition-y\n", "alert", "D", "9.1.1")
    assert [(o.id, o.name) for o in obs] == [("AlertDefinition-x", "An alert"), ("AlertDefinition-y", "")]


# ---------------------------------------------------------------------------
# The packaged baseline
# ---------------------------------------------------------------------------

def test_packaged_baseline_loads():
    guard._CACHE.clear()
    b = guard.load_baseline()
    for ctype in ("view", "dashboard", "report"):
        assert b.count(ctype) > 0, ctype
    assert b.versions()
    guard._CACHE.clear()


# ---------------------------------------------------------------------------
# Review W1: an allowlist entry covers only content its own manifest owns
# ---------------------------------------------------------------------------

def _two_bundle_repo(root: Path) -> None:
    (root / "bundles").mkdir()
    (root / "third_party" / "proj" / "views").mkdir(parents=True)
    (root / "bundles" / "a.yaml").write_text(
        "name: a\nviews:\n  - content/views/a.yaml\nstock_id_allowlist:\n"
        f"  - {{type: view, id: {STOCK['view'][0]}, reason: bundle a keeps it}}\n", encoding="utf-8")
    (root / "bundles" / "b.yaml").write_text(
        "name: b\nviews:\n  - content/views/b.yaml\n", encoding="utf-8")
    (root / "third_party" / "proj" / "PROJECT.yaml").write_text(
        "name: proj\nstock_id_allowlist:\n"
        f"  - {{type: dashboard, id: {STOCK['dashboard'][0]}, reason: project keeps it}}\n",
        encoding="utf-8")


def _view_at(path: Path, oid=None):
    return SimpleNamespace(id=oid or STOCK["view"][0], name="Copied", source_path=path)


def test_validate_bundle_a_entry_does_not_silence_bundle_b(baseline_path, tmp_path, capsys, monkeypatch):
    import vcfcf_packaging.stock_ids as ps
    _two_bundle_repo(tmp_path)
    monkeypatch.setattr(ps, "REPO_ROOT", tmp_path)
    a = tmp_path / "content" / "views" / "a.yaml"
    b = tmp_path / "content" / "views" / "b.yaml"
    loose = tmp_path / "content" / "views" / "loose.yaml"

    assert ps.report_stock_ids(guard.bundled_definitions(views=[_view_at(a)]), "views") == 0
    err = capsys.readouterr().err
    assert "ALLOWLISTED" in err and "bundle a keeps it" in err

    # Same stock id, bundle B's file: bundle A's entry does not cover it.
    assert ps.report_stock_ids(guard.bundled_definitions(views=[_view_at(a), _view_at(b)]), "views") == 1
    err = capsys.readouterr().err
    assert "STOCK-ID:" in err and str(b) in err

    # A file no manifest owns cannot be allowlisted at all.
    assert ps.report_stock_ids(guard.bundled_definitions(views=[_view_at(loose)]), "views") == 1
    assert str(loose) in capsys.readouterr().err


def test_project_entry_covers_only_that_project(baseline_path, tmp_path, capsys, monkeypatch):
    import vcfcf_packaging.stock_ids as ps
    _two_bundle_repo(tmp_path)
    monkeypatch.setattr(ps, "REPO_ROOT", tmp_path)
    inside = SimpleNamespace(id=STOCK["dashboard"][0], name="D",
                             source_path=tmp_path / "third_party" / "proj" / "dashboards" / "d.yaml")
    outside = SimpleNamespace(id=STOCK["dashboard"][0], name="D",
                              source_path=tmp_path / "content" / "dashboards" / "d.yaml")
    assert ps.report_stock_ids(guard.bundled_definitions(dashboards=[inside]), "dashboards") == 0
    assert "project keeps it" in capsys.readouterr().err
    assert ps.report_stock_ids(guard.bundled_definitions(dashboards=[outside]), "dashboards") == 1


def test_import_honours_only_the_declared_manifest(baseline_path, tmp_path, monkeypatch):
    import vcfcf_packaging.stock_ids as ps
    _two_bundle_repo(tmp_path)
    monkeypatch.setattr(ps, "REPO_ROOT", tmp_path)
    blob = _zip({"views.zip": _zip({"content.xml": _views_xml((STOCK["view"][0], "x"))})})
    a_entries = [e for m in ps.repo_manifest_allowlists(tmp_path) for e in m.entries
                 if m.manifest.endswith("a.yaml")]
    # No owning manifest (a standalone sync): nothing is allowlisted.
    with pytest.raises(ps.StockIdRefused, match="No owning manifest"):
        ps.refuse_stock_ids_in_zip(blob)
    # Bundle B's sync: bundle A's entry does not apply.
    with ps.import_allowlist("bundles/b.yaml", []):
        with pytest.raises(ps.StockIdRefused):
            ps.refuse_stock_ids_in_zip(blob)
    # Bundle A's sync: its own entry applies, with a warning.
    with ps.import_allowlist("bundles/a.yaml", a_entries):
        warnings = ps.refuse_stock_ids_in_zip(blob)
    assert warnings and "bundle a keeps it" in warnings[0]
    # The scope ends with the block.
    with pytest.raises(ps.StockIdRefused):
        ps.refuse_stock_ids_in_zip(blob)


def test_sync_bundle_declares_its_own_allowlist_for_imports(baseline_path, monkeypatch):
    import vcfcf_packaging.stock_ids as ps
    import vcfcf_packaging.syncer as syncer
    entries = guard.parse_allowlist(
        [{"type": "view", "id": STOCK["view"][0], "reason": "bundle keeps it"}], "bundles/p.yaml")
    bundle = _bundle(views=[_view_at(Path("/repo/content/views/v.yaml"))],
                     stock_id_allowlist=entries, source_path=Path("bundles/p.yaml"))
    monkeypatch.setattr(syncer, "load_bundle", lambda path: bundle)
    monkeypatch.setattr(syncer, "print_navigation_prerequisites", lambda *a, **k: None)
    monkeypatch.setattr(syncer, "_check_sm_referents_before_import", lambda b, s: 0)
    seen = []

    class _ViewsHandler:
        content_type = "views"
        sync_order = 1

        def sync(self, yaml_paths, session):
            seen.append(ps._IMPORT_SCOPE.get())
            from vcfcf_packaging.handler import SyncResult
            return SyncResult(content_type="views")

    syncer.sync_bundle("bundles/p.yaml", handlers=[_ViewsHandler()], session=object())
    assert seen == [("bundles/p.yaml", entries)]
    assert ps._IMPORT_SCOPE.get() is None


# ---------------------------------------------------------------------------
# Review W2: nothing unreadable reports clean
# ---------------------------------------------------------------------------

def _patch_zip_headers(data: bytes, *, method: Optional[int] = None, flags: Optional[int] = None) -> bytes:
    """Rewrite every member's compression method / flag bits in a zip."""
    import struct
    buf = bytearray(data)
    for sig, flag_off, method_off in ((b"PK\x03\x04", 6, 8), (b"PK\x01\x02", 8, 10)):
        i = buf.find(sig)
        while i != -1:
            if flags is not None:
                struct.pack_into("<H", buf, i + flag_off, flags)
            if method is not None:
                struct.pack_into("<H", buf, i + method_off, method)
            i = buf.find(sig, i + 4)
    return bytes(buf)


def _nested(levels: int) -> bytes:
    data = _views_xml((STOCK["view"][0], "deep"))
    name = "content.xml"
    for i in range(levels):
        data = _zip({name: data})
        name = f"level{i}.zip"
    return data


def _unreadable_artifact(kind: str, monkeypatch) -> bytes:
    views = _views_xml((STOCK["view"][0], "x"))
    if kind == "too-deep":
        return _nested(guard._MAX_ZIP_DEPTH + 1)
    if kind == "bad-nested-zip":
        return _zip({"adapters.zip": b"PK\x03\x04 this is not a zip"})
    if kind == "oversized":
        monkeypatch.setattr(guard, "_MAX_MEMBER_BYTES", 64)
        return _zip({"content.xml": views})
    if kind == "unsupported-compression":
        return _patch_zip_headers(_zip({"content.xml": views}), method=99)
    if kind == "encrypted":
        return _patch_zip_headers(_zip({"content.xml": views}), flags=0x1)
    if kind == "undecodable-utf16":
        return _zip({"content.xml": b"\xff\xfe" + "<Content><ViewDef ".encode("utf-16-le") + b"\x00\xd8"})
    if kind == "unparsable-json":
        return _zip({"dashboard.json": b'{"dashboards": [ {"id": '})
    raise AssertionError(kind)


UNREADABLE_KINDS = ["too-deep", "bad-nested-zip", "oversized", "unsupported-compression",
                    "encrypted", "undecodable-utf16", "unparsable-json"]


@pytest.mark.parametrize("kind", UNREADABLE_KINDS)
def test_unreadable_content_is_recorded(kind, monkeypatch):
    unreadable = []
    guard.scan_bytes(_unreadable_artifact(kind, monkeypatch), "probe.pak", unreadable=unreadable)
    assert len(unreadable) == 1, unreadable
    assert unreadable[0].location.startswith("probe.pak")


def test_the_depth_limit_itself_still_scans(baseline):
    unreadable = []
    defs = guard.scan_bytes(_nested(guard._MAX_ZIP_DEPTH), "probe.pak", unreadable=unreadable)
    assert unreadable == [] and [d.id for d in defs] == [STOCK["view"][0]]


@pytest.mark.parametrize("kind", UNREADABLE_KINDS)
def test_unreadable_content_fails_every_gate(kind, baseline_path, tmp_path, monkeypatch, capsys):
    from vcfcf_core.packaging.loader import BundleValidationError
    from vcfcf_managementpacks import sdk_builder as sb
    from vcfcf_managementpacks.installer import _preflight_stock_ids
    from vcfcf_packaging.stock_ids import StockIdRefused, guard_bundle, refuse_stock_ids_in_zip
    data = _unreadable_artifact(kind, monkeypatch)

    with pytest.raises(BundleValidationError, match="cannot be checked"):
        guard_bundle(_bundle(), data, "bundle 'probe'")
    with pytest.raises(StockIdRefused, match="Import refused"):
        refuse_stock_ids_in_zip(data)
    pak = tmp_path / "probe.pak"
    pak.write_bytes(data)
    for allow in (False, True):       # --allow-stock-ids does not cover unreadable
        with pytest.raises(SystemExit):
            _preflight_stock_ids(pak, allow=allow)
    assert "cannot check" in capsys.readouterr().err
    with pytest.raises(sb.SdkBuildError, match="cannot be checked"):
        sb._gate_built_pak_stock_ids(pak, _project(), release_build=False)

    # The standalone check lists it and exits 1. (Oversized needs the
    # in-process limit, so it is checked through check_paths.)
    if kind == "oversized":
        check = guard.check_paths([pak], guard.load_baseline())
        assert check.exit_code == 1 and any("CANNOT CHECK" in line for line in check.lines)
    else:
        r = _run_check(str(pak), "--baseline", str(baseline_path))
        assert r.returncode == 1, r.stdout + r.stderr
        assert "CANNOT CHECK" in r.stdout and "not reported clean" in r.stdout


@pytest.mark.parametrize("encoding, bom", [
    ("utf-16-le", b"\xff\xfe"), ("utf-16-be", b"\xfe\xff"),
    ("utf-32-le", b"\xff\xfe\x00\x00"), ("utf-32-be", b"\x00\x00\xfe\xff"),
    ("utf-16-le", b""),
])
def test_utf16_and_utf32_xml_is_read(encoding, bom, baseline):
    text = (f'<?xml version="1.0" encoding="{encoding.split("-")[0].upper()}-{encoding.split("-")[1]}"?>'
            f'<Content><Views><ViewDef id="{STOCK["view"][0]}"><Title>x</Title></ViewDef></Views></Content>')
    unreadable = []
    defs = guard.scan_bytes(bom + text.encode(encoding), "v.xml", unreadable=unreadable)
    assert unreadable == []
    assert len(guard.check_definitions(defs, baseline=baseline).errors) == 1


def test_utf16_json_is_read(baseline):
    data = b"\xff\xfe" + _dashboard_json(STOCK["dashboard"][0]).decode().encode("utf-16-le")
    assert len(guard.check_definitions(guard.scan_bytes(data, "d.json"), baseline=baseline).errors) == 1


# ---------------------------------------------------------------------------
# Review W5: output does not overclaim
# ---------------------------------------------------------------------------

def _views_only_baseline(tmp_path) -> Path:
    p = tmp_path / "views_only.json"
    p.write_text(json.dumps({"format": guard.BASELINE_FORMAT, "ids": {
        "view": {STOCK["view"][0]: {"name": "Stock Probe View", "versions": ["9.1.1"]}}}}),
        encoding="utf-8")
    return p


def test_standalone_check_states_what_it_compared(tmp_path):
    pak = tmp_path / "clean.pak"
    pak.write_bytes(_zip({
        "views.xml": _views_xml((OWN["view"], "Own")),
        "sm.json": _sm_json("cccc0004-0000-4000-8000-000000000004"),
    }))
    r = _run_check(str(pak), "--baseline", str(_views_only_baseline(tmp_path)))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "no definition uses a stock id" not in r.stdout
    assert "1 distinct definition(s) compared (view 1)" in r.stdout
    assert "not checked, the baseline has no ids for:" in r.stdout
    assert "super metric (1 scanned)" in r.stdout and "recommendation" in r.stdout
    assert "Known holes" in r.stdout and "stock_id_guard.md" in r.stdout


def test_standalone_check_with_nothing_to_check_says_so(baseline_path, tmp_path):
    tree = tmp_path / "yaml_tree" / "views"
    tree.mkdir(parents=True)
    (tree / "v.yaml").write_text(f"id: {STOCK['view'][0]}\nname: x\n", encoding="utf-8")
    r = _run_check(str(tmp_path / "yaml_tree"), "--baseline", str(baseline_path))
    assert r.returncode == 1, r.stdout + r.stderr
    assert "nothing to check" in r.stdout
    assert "no definition uses a stock id" not in r.stdout and "compared" not in r.stdout


def test_built_pak_gate_states_what_it_compared(tmp_path, capsys, monkeypatch):
    from vcfcf_managementpacks import sdk_builder as sb
    monkeypatch.setattr(guard, "default_baseline_path", lambda: _views_only_baseline(tmp_path))
    guard._CACHE.clear()
    pak = tmp_path / "probe.pak"
    pak.write_bytes(_synthetic_pak(stock=False))
    sb._gate_built_pak_stock_ids(pak, _project(), release_build=False)
    err = capsys.readouterr().err
    guard._CACHE.clear()
    assert "compared (view 1)" in err and "not checked, the baseline has no ids for" in err
    assert "dashboard" in err  # a scanned type without baseline ids is named


# ---------------------------------------------------------------------------
# Review W6: the builders and build-sdk actually call the guard
# ---------------------------------------------------------------------------

REAL_BUNDLE = REPO_ROOT / "bundles" / "storage-path-monitoring.yaml"
REAL_SM = REPO_ROOT / "content" / "supermetrics" / "host_storage_active_path_count.yaml"


@pytest.fixture
def real_sm_is_stock(tmp_path, monkeypatch):
    """A synthetic baseline that lists one real factory super metric's id."""
    import yaml
    sm = yaml.safe_load(REAL_SM.read_text(encoding="utf-8"))
    p = tmp_path / "baseline" / guard.BASELINE_FILE_NAME
    p.parent.mkdir()
    p.write_text(json.dumps({"format": guard.BASELINE_FORMAT, "ids": {
        "supermetric": {sm["id"]: {"name": "Stock Probe SM", "versions": ["9.1.1"]}}}}), encoding="utf-8")
    monkeypatch.setattr(guard, "default_baseline_path", lambda: p)
    guard._CACHE.clear()
    yield sm
    guard._CACHE.clear()


@pytest.mark.xdist_group("real_corpus")
def test_build_bundle_calls_the_guard(real_sm_is_stock, tmp_path, monkeypatch):
    from vcfcf_core.packaging.loader import BundleValidationError
    from vcfcf_packaging.builder import build_bundle
    monkeypatch.chdir(REPO_ROOT)
    out = tmp_path / "dist"
    with pytest.raises(BundleValidationError, match="stock-id guard") as exc:
        build_bundle(REAL_BUNDLE, out, live_describe=False, skip_audit=True)
    assert real_sm_is_stock["id"] in str(exc.value)
    assert not list(out.rglob("*.zip")) if out.exists() else True


@pytest.mark.xdist_group("real_corpus")
def test_build_discrete_calls_the_guard(real_sm_is_stock, tmp_path, monkeypatch):
    from vcfcf_core.packaging.loader import BundleValidationError
    from vcfcf_packaging.discrete_builder import build_discrete
    monkeypatch.chdir(REPO_ROOT)
    out = tmp_path / "discrete"
    with pytest.raises(BundleValidationError, match="stock-id guard") as exc:
        build_discrete("supermetric", real_sm_is_stock["name"], out,
                       live_describe=False, skip_audit=True)
    assert real_sm_is_stock["id"] in str(exc.value)
    assert not list(out.rglob("*.zip"))


@pytest.mark.xdist_group("real_corpus")
def test_build_discrete_honours_the_project_allowlist(real_sm_is_stock, tmp_path, monkeypatch, capsys):
    """N3: a third-party item's PROJECT.yaml allowlist reaches its build,
    and covers only that project's files."""
    from vcfcf_core.packaging.loader import BundleValidationError
    from vcfcf_packaging.discrete_builder import build_discrete
    monkeypatch.chdir(REPO_ROOT)
    proj = tmp_path / "third_party" / "probe"
    (proj / "supermetrics").mkdir(parents=True)
    text = REAL_SM.read_text(encoding="utf-8").replace(
        real_sm_is_stock["name"], "Probe Third-Party SM")
    (proj / "supermetrics" / "probe.yaml").write_text(text, encoding="utf-8")
    (proj / "PROJECT.yaml").write_text(
        "name: probe\nstock_id_allowlist:\n"
        f"  - {{type: supermetric, id: {real_sm_is_stock['id']}, reason: probe keeps it}}\n",
        encoding="utf-8")
    out = tmp_path / "discrete"
    built = build_discrete("supermetric", "Probe Third-Party SM", out, extra_search_dirs=[proj],
                           live_describe=False, skip_audit=True)
    assert built.exists() and "probe keeps it" in capsys.readouterr().err
    # The factory item with the same id is not the project's: still refused.
    with pytest.raises(BundleValidationError, match="stock-id guard"):
        build_discrete("supermetric", real_sm_is_stock["name"], out, extra_search_dirs=[proj],
                       live_describe=False, skip_audit=True)


def _sdk_project(base: Path, view_id: str) -> Path:
    import textwrap
    project = base / "probe_adapter"
    (project / "views").mkdir(parents=True)
    (project / "adapter.yaml").write_text(textwrap.dedent("""\
        name: "Probe Adapter"
        version: "1.0.0"
        build_number: 1
        adapter_kind: "probe_kind"
        tier: 2
        content_naming: unprefixed
        bundled_content:
          views:
            - views/probe.yaml
        """), encoding="utf-8")
    (project / "describe.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<AdapterKind key="probe_kind" nameKey="1" version="1">'
        '<ResourceKinds><ResourceKind key="probe_world" nameKey="2" type="1"/></ResourceKinds></AdapterKind>\n',
        encoding="utf-8")
    (project / "views" / "probe.yaml").write_text(textwrap.dedent(f"""\
        id: {view_id}
        name: "Probe View"
        description: "probe"
        subject:
          adapter_kind: VMWARE
          resource_kind: HostSystem
        columns:
          - attribute: cpu|usage_average
            display_name: "CPU Usage (%)"
        """), encoding="utf-8")
    return project


def test_build_sdk_refuses_before_the_compile(baseline_path, tmp_path, monkeypatch):
    from vcfcf_managementpacks import sdk_builder as sb

    def _no_compile(*a, **k):
        raise AssertionError("build-sdk reached the JDK step despite a bundled stock id")

    monkeypatch.setattr(sb, "_detect_jdk", _no_compile)
    monkeypatch.delenv("VCFCF_RELEASE_BUILD", raising=False)
    project = _sdk_project(tmp_path, STOCK["view"][0])
    with pytest.raises(sb.SdkBuildError, match="stock-id guard") as exc:
        sb.build_sdk_pak(project, tmp_path / "out")
    assert "views/probe.yaml" in str(exc.value)
    assert not (tmp_path / "out").exists() or not list((tmp_path / "out").glob("*.pak"))


# ---------------------------------------------------------------------------
# Review W8: symptom and alert sync upsert by name
# ---------------------------------------------------------------------------

def test_stock_name_collision_warns(baseline_path, capsys):
    from vcfcf_packaging.stock_ids import report_stock_name_collisions
    same = SimpleNamespace(name=STOCK["symptom"][1], source_path=Path("third_party/p/symptoms/s.yaml"))
    other = SimpleNamespace(name="Probe own symptom", source_path=Path("s2.yaml"))
    assert report_stock_name_collisions([same, other], "symptom", "symptom") == 1
    err = capsys.readouterr().err
    assert "STOCK-NAME" in err and "third_party/p/symptoms/s.yaml" in err and STOCK["symptom"][0] in err
    alert = SimpleNamespace(name=STOCK["alert"][1], source_path=Path("a.yaml"))
    assert report_stock_name_collisions([alert], "alert", "alert") == 1
    # Views are imported by id, not upserted by name: no name check.
    assert report_stock_name_collisions([SimpleNamespace(name=STOCK["view"][1])], "view", "view") == 0


def test_bundle_build_and_validate_warn_on_a_stock_name(baseline_path, tmp_path, capsys, monkeypatch):
    """The third-party path: an unprefixed bundle symptom named like a stock
    one is warned at bundle validate and build (install.py upserts by name)."""
    from vcfcf_packaging import cli as pcli
    from vcfcf_packaging.stock_ids import guard_bundle
    sym = SimpleNamespace(name=STOCK["symptom"][1], source_path=Path("third_party/p/symptoms/s.yaml"),
                          adapter_kind="PROBEKIND", resource_kind="x")
    bundle = _bundle(symptoms=[], alerts=[])
    bundle.symptoms = [sym]
    monkeypatch.setattr(pcli, "load_bundle", lambda p: bundle)
    monkeypatch.chdir(tmp_path)  # no bundles/releases here
    assert pcli.cmd_validate(SimpleNamespace(manifests=["probe.yaml"])) == 0
    assert "STOCK-NAME" in capsys.readouterr().err
    import vcfcf_core.alerts.render as arender
    monkeypatch.setattr(arender, "render_alert_content_xml", lambda **k: "<alertContent/>")
    guard_bundle(_bundle(), None, "bundle 'probe'")
    assert "STOCK-NAME" not in capsys.readouterr().err
    b2 = _bundle()
    b2.alerts = [SimpleNamespace(name=STOCK["alert"][1], source_path=Path("a.yaml"))]
    guard_bundle(b2, None, "bundle 'probe'")
    assert "STOCK-NAME" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Review N4: the OK line prints after the stock check, and only when it passes
# ---------------------------------------------------------------------------

def test_validate_prints_ok_only_after_the_stock_check(baseline_path, tmp_path, capsys, monkeypatch):
    import vcfcf_packaging.stock_ids as ps
    from vcfcf_supermetrics import cli as smcli
    monkeypatch.setattr(ps, "repo_manifest_allowlists", lambda root=None: [])
    y = tmp_path / "sm.yaml"
    y.write_text(REAL_SM.read_text(encoding="utf-8").replace(
        REAL_SM.read_text(encoding="utf-8").splitlines()[0], f"id: {STOCK['supermetric'][0]}"),
        encoding="utf-8")
    rc = smcli.cmd_validate(SimpleNamespace(paths=[str(y)], profile=None))
    out, err = capsys.readouterr()
    assert rc == 1 and "STOCK-ID:" in err
    assert "OK:" not in out


# ---------------------------------------------------------------------------
# Generator: review W4 (exclusions, presence ratios) and N1 (one vote per instance)
# ---------------------------------------------------------------------------

def test_generator_excluded_content_is_never_stock_and_masking_is_counted():
    obs = [
        _obs("view", "v-fork", "Fork View", "A", "8.18.7", localized="1"),
        _obs("view", "v-fork", "Fork View", "B", "9.1.1", localized="1"),
        _obs("view", "v-other", "Other", "A", "8.18.7"),
        _obs("view", "v-other", "Other", "B", "9.1.1"),
    ]
    # A fork that is not installed but shares an id seen on two labs: that
    # id would be stock under the presence rule, so excluding it is masking.
    copier = [guard.Definition("view", i, "", "f") for i in ("v-fork", "own-1", "own-2")]
    build = gen.build_baseline(obs, excluded_groups={"fork-x": copier})
    assert set(build.baseline["ids"]["view"]) == {"v-other"}
    assert build.masked == {"fork-x": 1}
    reasons = {c.id: c.reason for c in build.candidates}
    assert "excluded content 'fork-x'" in reasons["v-fork"] and "otherwise be stock" in reasons["v-fork"]
    assert build.baseline["rule"]["excluded_packages"] == ["fork-x"]
    assert build.baseline["rule"]["known_packages"] == []
    assert {(p.package, p.excluded, p.installed) for p in build.presence} == {("fork-x", True, False)}
    # A fork installed on both labs: its own id is explained by it, so
    # excluding it masks nothing (the registered forks today).
    installed = [guard.Definition("view", "v-fork", "", "f")]
    build = gen.build_baseline(obs, excluded_groups={"fork-x": installed})
    assert set(build.baseline["ids"]["view"]) == {"v-other"}
    assert build.masked == {"fork-x": 0}


def test_generator_reports_presence_and_flags_ratios_near_the_threshold():
    from vcfcf_packaging.stock_ids import _presence_report
    obs = [_obs("view", f"p{i}", "P", "A", "9.1.1") for i in range(9)]  # 9 of 10 present
    obs += [_obs("view", f"q{i}", "Q", "A", "9.1.1") for i in range(2)]  # 2 of 10 present
    near = [guard.Definition("view", f"p{i}", "", "n") for i in range(10)]
    far = [guard.Definition("view", f"q{i}", "", "f") for i in range(10)]
    build = gen.build_baseline(obs, known_groups={"near": near, "far": far})
    got = {(p.package, p.instance): (p.present, p.total, p.installed) for p in build.presence}
    assert got == {("near", "A"): (9, 10, True), ("far", "A"): (2, 10, False)}
    lines = _presence_report(build, gen.DEFAULT_INSTALLED_THRESHOLD)
    near_line = next(line for line in lines if " near on A" in line)
    far_line = next(line for line in lines if " far on A" in line)
    assert near_line.startswith("WARNING:") and "within 10 points" in near_line
    assert not far_line.startswith("WARNING:") and "2/10 (20%)" in far_line


def test_generator_name_vote_is_one_per_instance():
    obs = [
        # Instance A fed three exports, all naming the id "Old"; B and C one each, "New".
        _obs("view", "v1", "Old", "A", "9.1.1"),
        _obs("view", "v1", "Old", "A", "9.1.1"),
        _obs("view", "v1", "Old", "A", "9.1.1"),
        _obs("view", "v1", "New", "B", "8.18.7"),
        _obs("view", "v1", "New", "C", "9.0.2"),
    ]
    build = gen.build_baseline(obs)
    assert build.baseline["ids"]["view"]["v1"]["name"] == "New"

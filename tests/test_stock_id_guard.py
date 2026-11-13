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
    assert guard.scan_bytes(b'{"dashboards": ' + deep_json + b"}", "deep.json") == []


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
    monkeypatch.setattr(ps, "repo_allowlist", lambda root=None: [])
    defs = guard.bundled_definitions(views=[
        SimpleNamespace(id=STOCK["view"][0], name="Copied", source_path=Path("content/views/c.yaml")),
    ])
    assert ps.report_stock_ids(defs, "views") == 1
    err = capsys.readouterr().err
    assert "STOCK-ID:" in err and "content/views/c.yaml" in err


def test_repo_allowlist_reads_manifests(tmp_path):
    from vcfcf_packaging.stock_ids import repo_allowlist
    (tmp_path / "bundles").mkdir()
    (tmp_path / "third_party" / "proj").mkdir(parents=True)
    (tmp_path / "bundles" / "a.yaml").write_text(
        "name: a\nstock_id_allowlist:\n  - {type: view, id: v1, reason: because}\n", encoding="utf-8")
    (tmp_path / "third_party" / "proj" / "PROJECT.yaml").write_text(
        "name: p\nstock_id_allowlist:\n  - {type: dashboard, id: d1, reason: because}\n", encoding="utf-8")
    entries = repo_allowlist(tmp_path)
    assert {(e.type, e.id) for e in entries} == {("view", "v1"), ("dashboard", "d1")}


class _UnusedClient:
    """A client the guard must refuse before touching."""

    def __getattr__(self, name):
        raise AssertionError(f"import reached the client ({name}) despite the guard")


def test_content_import_refuses_stock_definition(baseline_path, monkeypatch):
    import vcfcf_packaging.stock_ids as ps
    from vcfcf_dashboards.client import VCFOpsError, import_content_zip
    monkeypatch.setattr(ps, "repo_allowlist", lambda root=None: [])
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
    assert "factory id" in reasons["v-minted"]
    assert "custom-scope" in reasons["d-custom"]
    assert "installed-pak is installed" in reasons["v-pak1"]
    assert "localizationKey" in reasons["v-copied-raw"]
    assert "adapter kind" in reasons["AlertDefinition-mypak-x"]
    assert "needs two" in reasons["AlertDefinition-one"]
    assert build.baseline["candidates_not_included"]["view"] == 6


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

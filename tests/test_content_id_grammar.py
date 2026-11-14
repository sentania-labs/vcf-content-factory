"""Content id grammar: only ids VCF Operations accepts, at every door.

The bug (VCF Operations 9.0.2, 2026-11-14): ``import-local --ids mint``
minted the recommendation key ``Recommendation-<uuid5>``; the pak's alert
file then failed to import (``Invalid format of Recommendation Id: ... It
should start with Recommendation-df- or Recommendation-ud-``), taking the
alert, its symptoms and the recommendation with it. Verification passed
because both sides rendered through the same code.

Covered here: the grammar (``vcfcf_core.content_ids``); the minted, mapped
and kind-re-pointed recommendation keys through the CLI, the written YAML,
the alert that references the key and a pak built from the written tree;
the post-mint check (exit 5); the ``--id-map`` row error; the loader and
pak-gate rejections; the super metric references a minted id must follow
everywhere. Synthetic fixtures only ("Probe ..." names).
"""
from __future__ import annotations

import re
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest
import yaml

HERE = Path(__file__).resolve().parent
if str(HERE / "managementpacks") not in sys.path:
    sys.path.insert(0, str(HERE / "managementpacks"))

import test_pak_content_gates as gates  # noqa: E402  (stubbed-Java pak build)
from test_import_local import SM1, SM2, _build_source, _run, _yaml  # noqa: E402
import test_import_local_kind_map as km  # noqa: E402

from vcfcf_core import content_ids  # noqa: E402
from vcfcf_core.alerts.loader import (  # noqa: E402
    AlertValidationError,
    load_dir as load_alert_dir,
    load_recommendation_file,
    load_recommendations,
)
from vcfcf_core.alerts.render import render_alert_content_xml  # noqa: E402
from vcfcf_core.importer.convert import minted_id, mint_namespace_uuid  # noqa: E402
from vcfcf_core.packaging import pak_content  # noqa: E402
from vcfcf_core.symptoms.loader import load_dir as load_sym_dir  # noqa: E402
import vcfcf_managementpacks.sdk_builder as sb  # noqa: E402

REC_KEY = "probeRecommendationKey"   # the shared source's bare key
NS = "probe"
_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


@pytest.fixture(scope="module")
def source(tmp_path_factory) -> Path:
    return _build_source(tmp_path_factory.mktemp("rec_ids"))


@pytest.fixture(scope="module")
def alert_source(source, tmp_path_factory) -> Path:
    """The shared source's alert, symptoms and recommendation only (a pak
    layout of the whole source stops on its 9.1.1-only dashboards)."""
    d = tmp_path_factory.mktemp("rec_ids_alerts") / "content"
    for sub in ("alertdefs", "symptomdefs"):
        (d / sub).mkdir(parents=True)
        for f in (source / sub).glob("*.xml"):
            shutil.copy(f, d / sub / f.name)
    return d


def _minted_rec(kind="VMWARE", key=REC_KEY, ns=NS) -> str:
    return f"Recommendation-df-{kind}-{minted_id(mint_namespace_uuid(ns), 'recommendation', key)}"


def _rendered(out: Path):
    """The alert content XML the written symptoms, alerts and recommendations render to."""
    syms = load_sym_dir(out / "symptoms", enforce_framework_prefix=False)
    alerts = load_alert_dir(out / "alerts", enforce_framework_prefix=False)
    recs = load_recommendations(out / "recommendations", enforce_framework_prefix=False)
    return ET.fromstring(render_alert_content_xml(syms, alerts, recs))


def _only_rec(out: Path) -> dict:
    files = sorted((out / "recommendations").glob("*.yaml"))
    assert len(files) == 1, files
    return yaml.safe_load(files[0].read_text())


# --------------------------------------------------------------- the grammar
@pytest.mark.parametrize("key", [
    "vCommunityCollectionWarnings", "probe_key", "Recommendation-df-VMWARE-VM_CPU_Remediation",
    "Recommendation-df-VMWARE-ec5f14b5-b009-564e-8c31-66f205a839b1",
    "Recommendation-ud-b8f3ad42-51fe-4f28-b51e-bf9ef7358286", "_x.y-z",
])
def test_recommendation_keys_the_product_accepts(key):
    assert content_ids.recommendation_key_problem(key) is None


@pytest.mark.parametrize("key", [
    "Recommendation-ec5f14b5-b009-564e-8c31-66f205a839b1",   # the 9.0.2 refusal
    "Recommendation-xx-foo", "recommendation-df-VMWARE-x", "RECOMMENDATION-df-x",
    "Recommendation-df-", "Recommendation-ud-", "Recommendation-", "", "1abc", "has space",
])
def test_recommendation_keys_refused(key):
    assert content_ids.recommendation_key_problem(key)


def test_wire_and_yaml_grammar_per_type():
    u = "4a000000-0000-4000-8000-000000000001"
    w = content_ids.wire_id_problem
    assert w("symptom", f"SymptomDefinition-{u}") is None
    assert w("symptom", "SymptomDefinition-VMWARE-Probe") is None   # the derived form
    # a bare id imports (a VMware pak ships them in content/alertdefs/)
    assert w("symptom", "SwitchPortDown") is None and w("symptom", "SymptomDefinition-") and w("symptom", "")
    assert w("alert", f"AlertDefinition-{u}") is None and w("alert", u) is None and w("alert", "AlertDefinition-")
    # the product's own exports carry keys with spaces; the YAML refuses them
    assert w("recommendation", "Recommendation-df-vCenter Operations Adapter-DefaultFaultRecommendation") is None
    assert w("recommendation", "Recommendation-ec5f14b5-b009-564e-8c31-66f205a839b1")
    for t in ("view", "dashboard", "report", "supermetric"):
        assert w(t, u) is None and w(t, u.upper()) is None and w(t, "d1")
    y = content_ids.yaml_id_problem
    assert y("view", u) is None and y("view", u.upper())             # the loaders want lower case
    assert y("symptom", u) is None and y("symptom", "VMWARE-x")
    assert y("alert", u.upper()) is None and y("alert", f"AlertDefinition-{u}")
    assert "Recommendation-df-" in y("recommendation", f"Recommendation-{u}")


# ------------------------------------------------------- --ids mint (the bug)
@pytest.mark.parametrize("layout", ["third-party", "pak"])
def test_mint_gives_a_pak_recommendation_key_and_the_alert_follows(alert_source, tmp_path, capsys, layout):
    out = tmp_path / "out"
    rc, text = _run(alert_source, out, capsys, "--layout", layout, "--ids", "mint", "--mint-namespace", NS,
                    "--naming", "unprefixed", "--verify")
    assert rc == 0, text
    rec = _only_rec(out)
    assert rec["id"] == _minted_rec()
    assert re.fullmatch(rf"Recommendation-df-VMWARE-{_UUID}", rec["id"])
    assert content_ids.recommendation_key_problem(rec["id"]) is None
    assert rec["name"] == REC_KEY                      # the name is the source key
    alert = yaml.safe_load(next((out / "alerts").glob("*.yaml")).read_text())
    assert alert["recommendations"] == [{"name": REC_KEY, "priority": 1}]
    root = _rendered(out)
    assert [r.get("key") for r in root.iter("Recommendation") if r.get("key")] == [rec["id"]]
    refs = [r.get("ref") for r in root.iter("Recommendation") if r.get("ref")]
    assert refs == [rec["id"]]
    tsv = (out / "import-report" / "id_map.tsv").read_text()
    assert f"recommendation\t{REC_KEY}\t{rec['id']}\t" in tsv


def test_mint_is_repeatable_and_other_ids_stay_bare_uuids(source, tmp_path, capsys):
    outs = []
    for n in ("a", "b"):
        out = tmp_path / n
        rc, text = _run(source, out, capsys, "--layout", "third-party", "--ids", "mint", "--mint-namespace", NS,
                        "--naming", "unprefixed")
        assert rc == 0, text
        outs.append(out)
    rows = [(out / "import-report" / "id_map.tsv").read_text() for out in outs]
    assert rows[0] == rows[1]
    for line in rows[0].splitlines()[2:]:
        t, old, new = line.split("\t")[:3]
        prefix = {"symptom": "SymptomDefinition-", "alert": "AlertDefinition-"}.get(t, "")
        old, new = old[len(prefix):] if old.startswith(prefix) else old, new[len(prefix):]
        if t != "recommendation":
            # every other type keeps the plain uuid5 (ids already in use stay)
            assert new == minted_id(mint_namespace_uuid(NS), t, old), line


def _project_from(out: Path, tmp: Path) -> Path:
    """A Tier 2 project bundling the written symptoms, alerts and
    recommendations (pak layout, paths as the bundled_content snippet)."""
    d = tmp / "pakproj"
    for sub in ("symptoms", "alerts", "recommendations"):
        shutil.copytree(out / sub, d / sub)
    (d / "describe.xml").write_text(gates._DESCRIBE, encoding="utf-8")
    (d / "src").mkdir()
    (d / "src" / "Gate.java").write_text("class Gate {}\n", encoding="utf-8")
    snippet = yaml.safe_load((out / "import-report" / "bundled_content.yaml").read_text())["bundled_content"]
    lines = [f"adapter_kind: {gates.KIND}", "entry_class: com.vcfcf.adapters.gate.GateAdapter",
             "name: VCF Content Factory Gate Probe", "version: 0.1.0", "build_number: 1", "tier: 2",
             "released: false", "content_naming: unprefixed", "content_foreign_adapter_kinds: [VMWARE]",
             "bundled_content:"]
    for sub in ("symptoms", "alerts", "recommendations"):
        lines.append(f"  {sub}: [{', '.join(snippet[sub])}]")
    (d / "adapter.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return d


def test_pak_built_from_a_minted_tree_carries_a_key_the_gate_accepts(alert_source, tmp_path, capsys, monkeypatch):
    out = tmp_path / "out"
    rc, text = _run(alert_source, out, capsys, "--layout", "pak", "--ids", "mint", "--mint-namespace", NS,
                    "--naming", "unprefixed")
    assert rc == 0, text
    d = _project_from(out, tmp_path)
    assert gates._validate(d, monkeypatch) == []
    gates._stub_java(monkeypatch)
    pak = sb.build_sdk_pak(d, tmp_path / "built")
    assert pak_content.check_pak_content(pak) == []
    with zipfile.ZipFile(pak) as z:
        xmls = [ET.fromstring(z.read(n)) for n in z.namelist()
                if n.startswith("content/alertdefs/") and n.endswith(".xml")]
    keys = {r.get("key") for x in xmls for r in x.iter("Recommendation") if r.get("key")}
    refs = {r.get("ref") for x in xmls for r in x.iter("Recommendation") if r.get("ref")}
    assert keys == refs == {_minted_rec()}


def test_pak_gate_refuses_the_old_minted_key(alert_source, tmp_path, capsys, monkeypatch):
    """The tree main produced before the fix: the written key replaced by
    Recommendation-<uuid> builds a pak the gate now refuses, naming the rule."""
    out = tmp_path / "out"
    rc, text = _run(alert_source, out, capsys, "--layout", "pak", "--ids", "mint", "--mint-namespace", NS,
                    "--naming", "unprefixed")
    assert rc == 0, text
    bad = f"Recommendation-{minted_id(mint_namespace_uuid(NS), 'recommendation', REC_KEY)}"
    d = _project_from(out, tmp_path)
    for p in (d / "recommendations").glob("*.yaml"):
        p.write_text(p.read_text().replace(_minted_rec(), bad))
    # the loader refuses it first (validate, validate-sdk, every build) ...
    errs = gates._validate(d, monkeypatch)
    assert any("Recommendation-df-" in e and bad in e for e in errs), errs
    # ... and a pak carrying it (rendered past the loader) fails the gate
    xml = (f'<AlertContent><Recommendations><Recommendation key="{bad}"><Description>d</Description>'
           f"</Recommendation></Recommendations></AlertContent>")
    pak = gates._pak_with(tmp_path, {"content/alertdefs/a.xml": xml})
    errs = pak_content.check_pak_content(pak)
    assert len(errs) == 1 and bad in errs[0] and "Recommendation-df-" in errs[0], errs


# ----------------------------------------------------- post-mint check, exit 5
def test_a_minted_id_the_grammar_refuses_is_an_internal_error(source, tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(content_ids, "mint_recommendation_key", lambda kind, u: f"Recommendation-{u}")
    out = tmp_path / "out"
    rc, text = _run(source, out, capsys, "--layout", "third-party", "--ids", "mint", "--mint-namespace", NS,
                    "--naming", "unprefixed", "--allow-partial")
    assert rc == 5, text
    assert f"INTERNAL ERROR recommendation {REC_KEY}" in text
    assert "minted id 'Recommendation-" in text and "Recommendation-df-" in text
    assert not out.exists()


# ------------------------------------------------------------------ --id-map
@pytest.mark.parametrize("target", ["Recommendation-df-VMWARE-probe_new", "probeNewKey",
                                    "Recommendation-ud-b8f3ad42-51fe-4f28-b51e-bf9ef7358286"])
def test_id_map_recommendation_target_the_product_accepts(source, tmp_path, capsys, target):
    m = tmp_path / "map.tsv"
    m.write_text(f"old_id\tnew_id\n{REC_KEY}\t{target}\n")
    out = tmp_path / "out"
    rc, text = _run(source, out, capsys, "--layout", "third-party", "--id-map", m, "--naming", "unprefixed",
                    "--verify")
    assert rc == 0, text
    assert _only_rec(out)["id"] == target
    root = _rendered(out)
    assert {r.get("ref") for r in root.iter("Recommendation") if r.get("ref")} == {target}


@pytest.mark.parametrize("row,what", [
    (f"{REC_KEY}\tRecommendation-ec5f14b5-b009-564e-8c31-66f205a839b1", "Recommendation-df-"),
    (f"{REC_KEY}\trecommendation-df-x", "Recommendation-df-"),
    (f"{REC_KEY}\thas space", "not an XML id"),
    ("7a000000-0000-4000-8000-000000000001\tnot-a-uuid", "not a lower-case UUID"),
    ("SymptomDefinition-3c000000-0000-4000-8000-000000000002\tVMWARE-x", "not a UUID"),
])
def test_id_map_target_the_grammar_refuses_is_a_usage_error_naming_the_row(source, tmp_path, capsys, row, what):
    m = tmp_path / "map.tsv"
    m.write_text(f"old_id\tnew_id\n# a comment\n{row}\n")
    out = tmp_path / "out"
    rc, text = _run(source, out, capsys, "--layout", "third-party", "--id-map", m, "--naming", "unprefixed")
    assert rc == 2, text
    assert f"--id-map {m} line 3: " in text and what in text, text
    assert not out.exists()


# ---------------------------------------------------------------- --map-kind
def test_mint_with_map_kind_embeds_the_new_kind(tmp_path, capsys):
    src = km.build_source(tmp_path / "s", sources=km._with_rec(["a_d.yaml"]))
    out = tmp_path / "out"
    rc, text = km._run(src, out, capsys, "--map-kind", km._tsv(tmp_path, "k.tsv", km.STAR_ROW),
                       "--mint-namespace", NS, ids=("--ids", "mint"))
    assert rc == 0, text
    recs = {p.name: yaml.safe_load(p.read_text()) for p in (out / "recommendations").glob("*.yaml")}
    for rec in recs.values():
        assert rec["adapter_kind"] == km.NEW
        assert rec["id"].startswith(f"Recommendation-df-{km.NEW}-"), rec
        assert content_ids.recommendation_key_problem(rec["id"]) is None


def test_kept_derived_key_re_pointed_by_map_kind_passes_the_grammar(tmp_path, capsys):
    src = km.build_source(tmp_path / "s", sources=km._with_rec(["a_d.yaml"]))
    out = tmp_path / "out"
    rc, text = km._run(src, out, capsys, "--map-kind", km._tsv(tmp_path, "k.tsv", km.STAR_ROW))
    assert rc == 0, text
    for p in (out / "recommendations").glob("*.yaml"):
        rec = yaml.safe_load(p.read_text())
        rid = rec.get("id") or load_recommendation_file(p, enforce_framework_prefix=False).id
        assert content_ids.recommendation_key_problem(rid) is None, rid


# ----------------------------------------------------------- --ids keep door
def test_keep_on_a_source_key_the_product_refuses_fails_that_object(tmp_path, capsys):
    src = tmp_path / "src"
    src.mkdir()
    bad = "Recommendation-ec5f14b5-b009-564e-8c31-66f205a839b1"
    (src / "a.xml").write_text(
        f'<AlertContent><Recommendations><Recommendation key="{bad}"><Description>d</Description>'
        f"</Recommendation></Recommendations></AlertContent>")
    rc, text = _run(src, tmp_path / "out", capsys, "--layout", "third-party", "--ids", "keep",
                    "--naming", "unprefixed", "--allow-partial")
    assert f"FAILED recommendation {bad}" in text and "Recommendation-df-" in text, text
    assert rc != 0


# --------------------------------------------------------------- the loader
@pytest.mark.parametrize("key", ["Recommendation-ec5f14b5-b009-564e-8c31-66f205a839b1", "recommendation-df-x",
                                 "Recommendation-df-"])
def test_recommendation_loader_refuses_with_the_product_rule(tmp_path, key):
    p = tmp_path / "r.yaml"
    p.write_text(f"name: Probe Rec\nid: {key}\ndescription: d\nadapter_kind: VMWARE\n")
    with pytest.raises(AlertValidationError) as exc:
        load_recommendation_file(p, enforce_framework_prefix=False)
    assert str(p) in str(exc.value)
    if key.startswith("Recommendation-") and key != "Recommendation-df-":
        assert "Invalid format of Recommendation Id" in str(exc.value)


def test_recommendation_loader_accepts_bare_df_and_ud_keys(tmp_path):
    for key in ("vCommunityCollectionWarnings", "Recommendation-df-VMWARE-x",
                "Recommendation-ud-b8f3ad42-51fe-4f28-b51e-bf9ef7358286"):
        p = tmp_path / "r.yaml"
        p.write_text(f"name: Probe Rec\nid: {key}\ndescription: d\nadapter_kind: VMWARE\n")
        assert load_recommendation_file(p, enforce_framework_prefix=False).id == key


# ------------------------------------------------------------- the pak gate
def test_pak_gate_checks_the_id_grammar_per_type(tmp_path):
    u = "4a000000-0000-4000-8000-000000000001"
    ok = gates._pak_with(tmp_path, {
        "content/alertdefs/a.xml": (
            f'<AlertContent><SymptomDefinitions><SymptomDefinition id="SymptomDefinition-{u}" name="S"/>'
            f'</SymptomDefinitions><AlertDefinitions><AlertDefinition id="AlertDefinition-{u}" name="A"/>'
            f'</AlertDefinitions><Recommendations><Recommendation key="probeKey"><Description>d</Description>'
            f"</Recommendation></Recommendations></AlertContent>"),
        "content/reports/v/content.xml": gates._viewdef(u),
    })
    assert pak_content.check_pak_content(ok) == []
    ok.unlink()
    bad = gates._pak_with(tmp_path, {
        "content/alertdefs/a.xml": (
            f'<AlertContent><SymptomDefinitions><SymptomDefinition id="SymptomDefinition-" name="S"/>'
            f'</SymptomDefinitions><AlertDefinitions><AlertDefinition id="AlertDefinition-" name="A"/>'
            f'</AlertDefinitions><Recommendations><Recommendation key="Recommendation-{u}">'
            f"<Description>d</Description></Recommendation></Recommendations></AlertContent>"),
        "content/reports/v/content.xml": gates._viewdef("not-a-uuid"),
    })
    errs = pak_content.check_pak_content(bad)
    assert len(errs) == 4, errs
    joined = "\n".join(errs)
    for frag in ("symptom definition SymptomDefinition- ('S')", "alert definition AlertDefinition- ('A')",
                 f"recommendation Recommendation-{u}", "view not-a-uuid"):
        assert frag in joined, (frag, errs)
    assert all(e.startswith("content/") for e in errs)


# ------------------------------------- super metric ids follow a mint everywhere
def test_minted_super_metric_ids_follow_in_every_rendered_reference(source, tmp_path, capsys):
    out = tmp_path / "out"
    rc, text = _run(source, out, capsys, "--layout", "third-party", "--ids", "mint", "--mint-namespace", NS,
                    "--naming", "unprefixed", "--verify")
    assert rc == 0, text
    new = {old: minted_id(mint_namespace_uuid(NS), "supermetric", old) for old in (SM1, SM2)}
    from vcfcf_core.dashboards.loader import load_dashboard, load_view
    from vcfcf_core.dashboards.render import render_dashboards_bundle_json, render_views_xml
    from vcfcf_core.supermetrics.loader import load_file as load_sm
    from vcfcf_core.packaging.assembly import _render_supermetrics_dict
    sms = [load_sm(p, enforce_framework_prefix=False) for p in sorted((out / "supermetrics").glob("*.yaml"))]
    assert sorted(s.id for s in sms) == sorted(new.values())
    views = [load_view(p, enforce_framework_prefix=False) for p in sorted((out / "views").glob("*.yaml"))]
    dashes = [load_dashboard(p, enforce_framework_prefix=False, default_name_path="")
              for p in sorted((out / "dashboards").glob("*.yaml"))]
    wire = (render_views_xml(views, sm_map={s.name: s.id for s in sms})
            + render_dashboards_bundle_json(dashes, {v.name: v for v in views}, "0", known_dashboards=dashes)
            + str(_render_supermetrics_dict(type("B", (), {"supermetrics": sms})())))
    found = {m.lower() for m in re.findall(rf"sm_({_UUID})", wire, flags=re.I)}
    # view columns, additional columns, the dashboard metric key and the formula
    assert found == set(new.values()), found
    assert not any(old in wire for old in new)
    assert _yaml(out, "dashboards/probe-dashboard-a.yaml")["widgets"][1]["metrics"][0]["metric_key"] == \
        f"Super Metric|sm_{new[SM1]}"

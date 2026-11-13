"""The 2026-11-12 content-prefix move: ``[VCF Content Factory] `` -> ``[VCF CF] ``.

Covers the single source of truth (``vcfcf_core.naming``), the hard cut in
every loader, the pak naming contract, ids that must not move with the name,
the ``migrate-prefix`` command and the ``cleanup-legacy-prefix`` planner.
All fixtures are synthetic.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vcfcf_core import naming  # noqa: E402
from vcfcf_core.naming import (  # noqa: E402
    FACTORY_PREFIX,
    LEGACY_FACTORY_PREFIX,
    framework_prefix_problem,
    id_basis_name,
    legacy_name,
    rewrite_legacy_prefix,
    strip_factory_prefix,
)

NEW = FACTORY_PREFIX
OLD = LEGACY_FACTORY_PREFIX


# ---------------------------------------------------------------------------
# vcfcf_core.naming
# ---------------------------------------------------------------------------

def test_constants():
    assert NEW == "[VCF CF] "
    assert OLD == "[VCF Content Factory] "
    assert naming.FACTORY_PREFIX_LABEL == "[VCF CF]"
    assert "migrate-prefix" in naming.MIGRATE_COMMAND


def test_predicates():
    assert naming.has_factory_prefix(NEW + "X")
    assert not naming.has_factory_prefix("[VCF CF]X")
    assert naming.has_legacy_prefix(OLD + "X")
    assert naming.has_legacy_prefix("[VCF Content Factory]X")
    assert naming.is_factory_name(OLD + "X") and naming.is_factory_name(NEW + "X")
    assert not naming.is_factory_name("VCF Content Factory Dell PowerEdge")


def test_strip_and_legacy_name():
    assert strip_factory_prefix(NEW + "A B") == "A B"
    assert strip_factory_prefix(OLD + "A B") == "A B"
    assert strip_factory_prefix("Built-in") == "Built-in"
    assert legacy_name(NEW + "A") == OLD + "A"
    assert legacy_name("A") is None
    assert id_basis_name(NEW + "A") == OLD + "A"
    assert id_basis_name("Third Party") == "Third Party"


def test_rewrite_text():
    text = (f'name: "{OLD}A"\nformula: ${{this, metric=@supermetric:"{OLD}B"}}\n'
            f"see [VCF Content Factory](https://example.invalid)\n")
    new, n = rewrite_legacy_prefix(text)
    assert n == 2
    assert f'"{NEW}A"' in new and f'"{NEW}B"' in new
    assert "[VCF Content Factory](https://example.invalid)" in new
    again, n2 = rewrite_legacy_prefix(new)
    assert n2 == 0 and again == new


def test_rewrite_text_joins_a_wrapped_label():
    new, n = rewrite_legacy_prefix('companion "[VCF Content\n  Factory] VM Snapshot" view')
    assert n == 1 and new == 'companion "[VCF CF] VM Snapshot" view'


def test_problem_messages():
    assert framework_prefix_problem(NEW + "A", "f.yaml") is None
    legacy = framework_prefix_problem(OLD + "A", "f.yaml")
    assert "f.yaml" in legacy and "retired prefix" in legacy and "migrate-prefix" in legacy
    missing = framework_prefix_problem("A", "f.yaml")
    assert "missing framework prefix" in missing and '"[VCF CF]"' in missing


# ---------------------------------------------------------------------------
# The hard cut in each loader
# ---------------------------------------------------------------------------

_SM = """id: 6a8a4c78-d79e-4953-bc85-623b7bfb6001
name: "{name}"
resource_kinds:
  - resource_kind_key: ClusterComputeResource
    adapter_kind_key: VMWARE
description: Probe.
unit_id: percent
formula: |
  ${{this, metric=cpu|usage_average}}
"""

_SYMPTOM = """name: "{name}"
adapter_kind: VMWARE
resource_kind: VirtualMachine
severity: WARNING
condition:
  type: metric_static
  key: cpu|usage_average
  operator: GT
  value: 90
"""

_REC = """name: "{name}"
description: Do the thing.
adapter_kind: VMWARE
"""

_CG = """name: "{name}"
type_key: Environment
membership:
  rules:
    - resource_kind: VirtualMachine
      adapter_kind: VMWARE
      all_of_kind: true
"""


def _write(tmp_path: Path, rel: str, text: str) -> Path:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def test_supermetric_legacy_name_is_an_error(tmp_path):
    from vcfcf_core.supermetrics.loader import SuperMetricValidationError, load_file
    p = _write(tmp_path, "sm.yaml", _SM.format(name=OLD + "Probe"))
    with pytest.raises(SuperMetricValidationError) as ei:
        load_file(p)
    assert str(p) in str(ei.value) and "migrate-prefix" in str(ei.value)
    assert load_file(_write(tmp_path, "ok.yaml", _SM.format(name=NEW + "Probe"))).name == NEW + "Probe"
    # Third-party paths are unaffected.
    assert load_file(p, enforce_framework_prefix=False).name == OLD + "Probe"


def test_symptom_legacy_name_is_an_error(tmp_path):
    from vcfcf_core.symptoms.loader import SymptomValidationError, load_file
    p = _write(tmp_path, "s.yaml", _SYMPTOM.format(name=OLD + "Probe"))
    with pytest.raises(SymptomValidationError, match="migrate-prefix"):
        load_file(p)
    assert load_file(_write(tmp_path, "ok.yaml", _SYMPTOM.format(name=NEW + "Probe")))


def test_recommendation_legacy_name_is_an_error_and_id_is_stable(tmp_path):
    from vcfcf_core.alerts.loader import AlertValidationError, load_recommendation_file
    p = _write(tmp_path, "r.yaml", _REC.format(name=OLD + "VM CPU Remediation"))
    with pytest.raises(AlertValidationError, match="migrate-prefix"):
        load_recommendation_file(p)
    old = load_recommendation_file(p, enforce_framework_prefix=False)
    new = load_recommendation_file(_write(tmp_path, "n.yaml", _REC.format(name=NEW + "VM CPU Remediation")))
    assert new.id == old.id == "Recommendation-df-VMWARE-VM_CPU_Remediation"


def test_customgroup_legacy_name_is_an_error():
    from vcfcf_core.customgroups.loader import CustomGroupDef, CustomGroupValidationError
    with pytest.raises(CustomGroupValidationError, match="migrate-prefix"):
        CustomGroupDef(name=OLD + "G", rules=[]).validate()


def test_view_and_dashboard_legacy_names_are_errors(tmp_path):
    from vcfcf_core.dashboards.loader import DashboardValidationError, load_all
    dash = {
        "id": "0f5a4b3c-2d1e-4f60-8a7b-9c8d7e6f5a40",
        "name": OLD + "Probe",
        "widgets": [{"id": "t", "type": "TextDisplay", "title": "T",
                     "coords": {"x": 1, "y": 1, "w": 4, "h": 2},
                     "text_display_config": {"text": "hi"}}],
    }
    _write(tmp_path, "dashboards/d.yaml", yaml.safe_dump(dash))
    (tmp_path / "views").mkdir()
    with pytest.raises(DashboardValidationError, match="migrate-prefix"):
        load_all(tmp_path / "views", tmp_path / "dashboards")


def test_alert_legacy_references_are_checked_and_hinted():
    from vcfcf_core.alerts.loader import AlertDef, AlertValidationError, RecommendationRef
    a = AlertDef(
        name=NEW + "A", adapter_kind="VMWARE", resource_kind="VirtualMachine",
        criticality="WARNING", impact_badge="HEALTH",
        symptom_sets={"sets": [{"symptoms": [{"name": OLD + "S"}]}]},
        recommendations=[RecommendationRef(name=OLD + "R", priority=1)],
    )
    with pytest.raises(AlertValidationError) as ei:
        a.validate_symptom_refs({NEW + "S"})
    assert "retired prefix" in str(ei.value)
    with pytest.raises(AlertValidationError) as ei:
        a.validate_recommendation_refs({})
    assert "retired prefix" in str(ei.value)


# ---------------------------------------------------------------------------
# Ids that must not move with the name
# ---------------------------------------------------------------------------

def test_alert_and_symptom_derived_ids_survive_the_rename():
    from vcfcf_core.alerts import render
    for f in (render._alert_id, render._symptom_id, render._rec_key):
        assert f("VMWARE", NEW + "VM CPU High") == f("VMWARE", OLD + "VM CPU High")
    assert render._alert_id("VMWARE", NEW + "X") == "AlertDefinition-VMWARE-VCF_Content_Factory_X"
    assert render._alert_id("VMWARE", "Upstream X") == "AlertDefinition-VMWARE-Upstream_X"


def test_widget_uuids_survive_the_rename():
    from vcfcf_core.dashboards.loader import Widget, stable_id
    w = Widget.__new__(Widget)
    w.local_id = "w1"
    w.dashboard_name = NEW + "D"
    assert w.widget_id == stable_id("widget", f"{OLD}D::w1")
    w.dashboard_name = "Upstream D"
    assert w.widget_id == stable_id("widget", "Upstream D::w1")


def test_discrete_slug_survives_the_rename():
    from vcfcf_packaging.discrete_builder import _item_slug
    assert _item_slug(NEW + "Cluster CPU (%)") == _item_slug(OLD + "Cluster CPU (%)") == "cluster-cpu"


# ---------------------------------------------------------------------------
# Pak naming contract
# ---------------------------------------------------------------------------

def _proj(naming_value: str, declared: bool = True):
    return SimpleNamespace(content_naming=naming_value, content_naming_declared=declared)


def _bundled(*names):
    objs = [SimpleNamespace(name=n) for n in names]
    return (objs, [], [], [], [], [], [])


def test_pak_factory_prefixed_rejects_legacy_even_when_undeclared():
    from vcfcf_managementpacks.sdk_builder import check_content_naming
    for declared in (True, False):
        errors, warnings_ = check_content_naming(_proj("factory_prefixed", declared), _bundled(OLD + "V"))
        assert len(errors) == 1 and "migrate-prefix" in errors[0] and not warnings_
    assert check_content_naming(_proj("factory_prefixed"), _bundled(NEW + "V")) == ([], [])


def test_pak_unprefixed_rejects_both_spellings():
    from vcfcf_managementpacks.sdk_builder import check_content_naming
    errors, _ = check_content_naming(_proj("unprefixed"), _bundled(OLD + "V", NEW + "W", "Upstream"))
    assert len(errors) == 2
    assert check_content_naming(_proj("unprefixed"), _bundled("Upstream")) == ([], [])


def test_buildkit_ships_naming_module():
    from vcfcf_managementpacks.buildkit import _FACTORY_SOURCES, _IMPORT_REWRITES, BUILDKIT_VERSION
    assert _FACTORY_SOURCES["naming.py"] == SRC / "vcfcf_core" / "naming.py"
    for dest in ("sdk_builder.py", "dashboard_loader.py", "sm_loader.py", "symptoms_loader.py",
                 "alerts_loader.py", "alerts_render.py", "reports_loader.py"):
        assert (r"from vcfcf_core\.naming import", "from .naming import") in _IMPORT_REWRITES[dest]
    assert BUILDKIT_VERSION == "1.0.29"


# ---------------------------------------------------------------------------
# migrate-prefix
# ---------------------------------------------------------------------------

def _factory_tree(root: Path) -> None:
    _write(root, "content/supermetrics/a.yaml",
           f'id: 11111111-1111-4111-8111-111111111111\nname: "{OLD}A"\n'
           f"description: >\n  Companion of \"[VCF Content\n  Factory] B\".\n"
           f'formula: ${{this, metric=@supermetric:"{OLD}B"}}\n')
    _write(root, "content/views/v.yaml",
           f'id: 22222222-2222-4222-8222-222222222222\nname: "{OLD}V"\n'
           f"columns:\n  - attribute: 'supermetric:\"{OLD}A\"'\n")
    _write(root, "content/dashboards/d.yaml",
           f'id: 33333333-3333-4333-8333-333333333333\nname: "{OLD}D"\n'
           f"name_path: VCF Content Factory\nwidgets:\n  - view: '{OLD}V'\n")
    _write(root, "content/reports/r.yaml",
           f'name: "{OLD}R"\nsections:\n  - view: "{OLD}V"\n  - dashboard: "{OLD}D"\n')
    _write(root, "content/alerts/al.yaml",
           f'name: "{OLD}Alert"\nsymptom_sets:\n  sets:\n    - symptoms:\n        - name: "{OLD}S"\n'
           f'recommendations:\n  - name: "{OLD}Rec"\n    priority: 1\n')
    _write(root, "content/managementpacks/mp.yaml", "name: VCF Content Factory Thing\n")
    _write(root, "bundles/b.yaml", f'name: b\ndisplay_name: x\nnote: "{OLD}D"\n')
    _write(root, "third_party/proj/views/tp.yaml",
           f"name: Upstream View\ncolumns:\n  - attribute: 'supermetric:\"{OLD}A\"'\n")
    _write(root, "third_party/proj/debug/export.yaml", f'name: "{OLD}Captured"\n')
    _write(root, "third_party/proj/DESCRIPTION.md", "Via the [VCF Content Factory](https://x.invalid).\n")
    _write(root, "knowledge/context/investigations/old.md", f"{OLD}D was slow\n")
    _write(root, "content/sdk-adapters/pak/adapter.yaml", "name: P\n")
    _write(root, "content/sdk-adapters/pak/views/pv.yaml", f'name: "{OLD}PV"\n')


def test_migrate_factory_tree(tmp_path):
    from vcfcf_common import migrate_prefix as mp
    _factory_tree(tmp_path)
    before = (tmp_path / "content/supermetrics/a.yaml").read_text()
    plan = mp.build_plan(tmp_path)
    assert plan.layout == "factory" and not plan.errors
    changed = {str(c.path.relative_to(tmp_path)) for c in plan.changes}
    assert changed == {
        "content/supermetrics/a.yaml", "content/views/v.yaml", "content/dashboards/d.yaml",
        "content/reports/r.yaml", "content/alerts/al.yaml", "bundles/b.yaml",
        "third_party/proj/views/tp.yaml",
    }
    counts = mp.summarize(plan)
    assert counts["supermetrics"] == {"files": 1, "names": 1, "references": 2}
    assert counts["alerts"] == {"files": 1, "names": 1, "references": 2}
    assert [d.name for d in plan.pak_dirs] == ["pak"]
    mp.apply_plan(plan)
    after = (tmp_path / "content/supermetrics/a.yaml").read_text()
    assert OLD.rstrip() not in after and "[VCF Content" not in after
    data = yaml.safe_load(after)
    assert data["id"] == yaml.safe_load(before)["id"]
    assert data["name"] == NEW + "A" and data["formula"].endswith(f'"{NEW}B"}}')
    # Untouched: history, debug captures, links, pak repos, MP prose names.
    assert OLD in (tmp_path / "knowledge/context/investigations/old.md").read_text()
    assert OLD in (tmp_path / "third_party/proj/debug/export.yaml").read_text()
    assert "[VCF Content Factory](" in (tmp_path / "third_party/proj/DESCRIPTION.md").read_text()
    assert OLD in (tmp_path / "content/sdk-adapters/pak/views/pv.yaml").read_text()
    assert (tmp_path / "content/managementpacks/mp.yaml").read_text() == "name: VCF Content Factory Thing\n"
    # Idempotent.
    assert mp.build_plan(tmp_path).changes == []


def test_migrate_pak_tree(tmp_path):
    from vcfcf_common import migrate_prefix as mp
    pak = tmp_path / "pak"
    _write(pak, "adapter.yaml", f'name: VCF Content Factory P\n# names start with "{OLD}"\n')
    _write(pak, "dashboards/d.yaml", f'name: "{OLD}D"\n')
    _write(pak, "README.md", f"Dashboard **{OLD}D**. Built with [VCF Content Factory](https://x.invalid).\n")
    _write(pak, "REFERENCE.md", f"| {OLD}D | x |\n")
    _write(pak, "docs/overview.md", f"{OLD}D\n")
    _write(pak, "tests/test_names.py", f'NAME = "{OLD}D"\n')
    _write(pak, "conf/describe.xml", f'<Name>{OLD}D</Name>\n')
    _write(pak, "resources/resources.properties", f"DASH={OLD}D\n")
    _write(pak, "CHANGELOG.md", f"- renamed {OLD}D\n")
    _write(pak, "src/Main.java", f'// {OLD}D\n')
    plan = mp.build_plan(pak)
    assert plan.layout == "pak" and not plan.errors
    changed = {str(c.path.relative_to(pak)) for c in plan.changes}
    assert changed == {"adapter.yaml", "dashboards/d.yaml", "README.md", "REFERENCE.md",
                       "docs/overview.md", "tests/test_names.py", "conf/describe.xml",
                       "resources/resources.properties"}
    mp.apply_plan(plan)
    assert "[VCF Content Factory](https://x.invalid)" in (pak / "README.md").read_text()
    assert OLD in (pak / "CHANGELOG.md").read_text()
    assert OLD in (pak / "src/Main.java").read_text()
    assert yaml.safe_load((pak / "adapter.yaml").read_text())["name"] == "VCF Content Factory P"


def test_migrate_refuses_unparseable_yaml(tmp_path):
    from vcfcf_common import migrate_prefix as mp
    _write(tmp_path, "content/views/bad.yaml", f'name: "{OLD}V"\n  : : :\n')
    plan = mp.build_plan(tmp_path)
    assert plan.errors and not plan.changes


def test_migrate_rejects_unknown_root(tmp_path):
    from vcfcf_common import migrate_prefix as mp
    assert mp.main([str(tmp_path)]) == 2


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True,
                   env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t.invalid",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t.invalid",
                        "PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(cwd)})


def test_migrate_cli_dirty_tree_dry_run_and_force(tmp_path, capsys):
    from vcfcf_common import migrate_prefix as mp
    _write(tmp_path, "content/views/v.yaml", f'name: "{OLD}V"\n')
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "base")
    _write(tmp_path, "content/views/w.yaml", f'name: "{OLD}W"\n')  # untracked: dirty
    assert mp.main([str(tmp_path)]) == 1
    assert OLD in (tmp_path / "content/views/v.yaml").read_text()
    assert mp.main([str(tmp_path), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "would rewrite content/views/v.yaml" in out and f"+ name: \"{NEW}V\"" in out
    assert OLD in (tmp_path / "content/views/v.yaml").read_text()
    assert mp.main([str(tmp_path), "--force"]) == 0
    assert OLD not in (tmp_path / "content/views/v.yaml").read_text()
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "migrated")
    assert mp.main([str(tmp_path)]) == 0  # clean and nothing left: no-op


def test_migrate_is_a_vcfcf_common_subcommand(tmp_path):
    _write(tmp_path, "content/views/v.yaml", f'name: "{OLD}V"\n')
    r = subprocess.run([sys.executable, "-m", "vcfcf_common", "migrate-prefix", str(tmp_path), "--dry-run"],
                       capture_output=True, text=True, env={"PYTHONPATH": str(SRC), "PATH": "/usr/bin:/bin"},
                       timeout=60)
    assert r.returncode == 0, r.stderr
    assert "would rewrite content/views/v.yaml" in r.stdout


# ---------------------------------------------------------------------------
# cleanup-legacy-prefix
# ---------------------------------------------------------------------------

def test_collect_repo_items_factory_and_pak(tmp_path):
    from vcfcf_common.legacy_cleanup import collect_repo_items
    _write(tmp_path, "content/dashboards/d.yaml", f'id: D1\nname: "{NEW}D"\n')
    _write(tmp_path, "content/alerts/a.yaml", f'name: "{NEW}A"\n')
    _write(tmp_path, "content/views/u.yaml", "id: U1\nname: Unprefixed\n")
    _write(tmp_path, "third_party/p/views/t.yaml", f'id: T1\nname: "{NEW}T"\n')
    items = {(i.kind, i.name, i.id) for i in collect_repo_items(tmp_path)}
    assert items == {("dashboard", NEW + "D", "D1"), ("alert", NEW + "A", None), ("view", NEW + "T", "T1")}
    pak = tmp_path / "pak"
    _write(pak, "adapter.yaml", "name: P\nbundled_content:\n  dashboards:\n    - dashboards/d.yaml\n")
    _write(pak, "dashboards/d.yaml", f'id: PD\nname: "{NEW}PD"\n')
    _write(pak, "dashboards/unbundled.yaml", f'id: PU\nname: "{NEW}PU"\n')
    assert [(i.kind, i.name) for i in collect_repo_items(pak)] == [("dashboard", NEW + "PD")]


def _item(kind, name, id_=None, name_path=""):
    from vcfcf_common.legacy_cleanup import RepoItem
    return RepoItem(kind=kind, name=NEW + name, id=id_, source=f"{kind}.yaml", name_path=name_path)


def _verdicts(plan):
    return [(a.kind, a.verdict, a.id) for a in plan.actions]


def test_plan_name_owned_requires_the_twin():
    from vcfcf_common.legacy_cleanup import plan_cleanup
    live = {"alert": [{"id": "a-old", "name": OLD + "A"}]}
    assert _verdicts(plan_cleanup([_item("alert", "A")], live)) == [("alert", "skip", "a-old")]
    live["alert"].append({"id": "a-new", "name": NEW + "A"})
    assert _verdicts(plan_cleanup([_item("alert", "A")], live)) == [("alert", "delete", "a-old")]


def test_plan_exact_names_only():
    from vcfcf_common.legacy_cleanup import plan_cleanup
    live = {"symptom": [
        {"id": "s1", "name": OLD + "S (copy)"},
        {"id": "s2", "name": OLD + "Other"},
        {"id": "s3", "name": NEW + "S"},
        {"id": "s4", "name": "[VCF Content Factory]S"},
    ]}
    assert plan_cleanup([_item("symptom", "S")], live).actions == []


def test_plan_id_owned_needs_repo_id_on_the_twin():
    from vcfcf_common.legacy_cleanup import plan_cleanup
    item = _item("dashboard", "D", "R1", name_path="VCF Content Factory")
    # Twin carries the repo id, leftover does not: delete.
    live = {"dashboard": [{"id": "OLD9", "name": OLD + "D"}, {"id": "R1", "name": NEW + "D"}]}
    assert _verdicts(plan_cleanup([item], live)) == [("dashboard", "delete", "OLD9")]
    # Leftover still carries the repo id: conflict, never deleted.
    live = {"dashboard": [{"id": "R1", "name": OLD + "D"}, {"id": "N2", "name": NEW + "D"}]}
    assert _verdicts(plan_cleanup([item], live)) == [("dashboard", "conflict", "R1")]
    # Neither carries it: conflict.
    live = {"dashboard": [{"id": "X", "name": OLD + "D"}, {"id": "Y", "name": NEW + "D"}]}
    assert _verdicts(plan_cleanup([item], live)) == [("dashboard", "conflict", "X")]
    # Folder-qualified listing names match too.
    live = {"dashboard": [{"id": "OLD9", "name": "VCF Content Factory/" + OLD + "D"},
                          {"id": "R1", "name": "VCF Content Factory/" + NEW + "D"}]}
    assert _verdicts(plan_cleanup([item], live)) == [("dashboard", "delete", "OLD9")]


def test_plan_report_is_manual():
    from vcfcf_common.legacy_cleanup import plan_cleanup
    live = {"report": [{"id": "O", "name": OLD + "R"}, {"id": "R1", "name": NEW + "R"}]}
    assert _verdicts(plan_cleanup([_item("report", "R", "R1")], live)) == [("report", "manual", "O")]


class _FakeInstance:
    def __init__(self, live):
        self.live = live
        self.deleted = []

    def list(self, kind):
        return self.live.get(kind, [])

    def delete(self, a):
        self.deleted.append((a.kind, a.id))


def test_run_dry_run_by_default_and_apply_deletes_in_order(tmp_path, capsys):
    from vcfcf_common.legacy_cleanup import KINDS, run
    _write(tmp_path, "content/symptoms/s.yaml", f'name: "{NEW}S"\n')
    _write(tmp_path, "content/alerts/a.yaml", f'name: "{NEW}A"\n')
    _write(tmp_path, "content/dashboards/d.yaml", f'id: R1\nname: "{NEW}D"\n')
    live = {
        "symptom": [{"id": "s-old", "name": OLD + "S"}, {"id": "s-new", "name": NEW + "S"}],
        "alert": [{"id": "a-old", "name": OLD + "A"}, {"id": "a-new", "name": NEW + "A"}],
        "dashboard": [{"id": "d-old", "name": OLD + "D"}, {"id": "R1", "name": NEW + "D"}],
    }
    inst = _FakeInstance(live)
    assert run(tmp_path, inst, KINDS, apply=False) == 0
    assert inst.deleted == []
    assert "WOULD DELETE" in capsys.readouterr().out
    assert run(tmp_path, inst, KINDS, apply=True) == 0
    assert inst.deleted == [("dashboard", "d-old"), ("alert", "a-old"), ("symptom", "s-old")]


def test_cleanup_cli_rejects_unknown_kind():
    from vcfcf_common.legacy_cleanup import main
    assert main([".", "--types", "widgets"]) == 2

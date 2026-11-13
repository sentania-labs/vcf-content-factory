"""Distribution ``additional_columns:`` are a column source for every
dependency walker and audit (framework review of view schema fidelity,
2026-11-12, B2 and W2).

A super metric named only in an additional column is bundled and checked
like one named in ``columns:``; a built-in key there is audited against the
describe cache like any column key. One test per walker:

- ``vcfcf_core.packaging.deps._refs_from_view`` (build-time audit),
- ``vcfcf_core.packaging.audit._refs_from_views_xml`` (staged-bundle audit),
- ``vcfcf_core.common.dep_walker.extract_refs_from_views`` (live pre-flight),
  ``supermetrics_used_by`` and ``collect_deps``,
- ``vcfcf_packaging.discrete_builder._resolve_view_deps`` (discrete release),
- ``vcfcf_core.supermetrics.column_resolver.SmColumnResolver.column_problems``
  (validate / sync column check).

Synthetic fixtures only.
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vcfcf_core.dashboards.loader import load_dashboard, load_view  # noqa: E402

VID = "11111111-2222-4333-8444-555555555555"
SM_ID = "0a0a0a0a-0000-4000-8000-000000000001"
SM_NAME = "Probe Additional SM"
BAD_KEY = "cpu|no_such_metric_probe"
GOOD_KEY = "cpu|usage_average"


def _view_data(additional: list) -> dict:
    return {
        "id": VID,
        "name": "Additional Probe",
        "description": "synthetic",
        "data_type": "distribution",
        "subject": {"adapter_kind": "VMWARE", "resource_kind": "HostSystem"},
        "columns": [{"attribute": GOOD_KEY, "display_name": "CPU"}],
        "additional_columns": additional,
        "time_window": {"unit": "DAYS", "count": 7},
    }


def _sm_col() -> dict:
    return {"attribute": f'supermetric:"{SM_NAME}"', "display_name": "SM",
            "localized_name": "Super Metrics|Probe"}


def _bad_col() -> dict:
    return {"attribute": BAD_KEY, "display_name": "Bad", "localized_name": "CPU|Bad"}


def _load(tmp_path: Path, additional: list):
    p = tmp_path / "view.yaml"
    p.write_text(yaml.safe_dump(_view_data(additional), sort_keys=False))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return load_view(p, enforce_framework_prefix=False)


def _sm(provenance: str = "factory"):
    return SimpleNamespace(id=SM_ID, name=SM_NAME, provenance=provenance,
                           formula="${this, metric=cpu|usage_average}",
                           source_path=None, resource_kinds=[])


def _dashboard(tmp_path: Path):
    p = tmp_path / "dash.yaml"
    p.write_text(
        "id: 1f5a4b3c-2d1e-4f60-8a7b-9c8d7e6f5a4c\n"
        'name: "Probe Additional Dash"\n'
        'description: ""\n'
        "widgets:\n"
        "  - id: v1\n"
        "    type: View\n"
        "    title: Listing\n"
        "    coords: {x: 1, y: 1, w: 4, h: 4}\n"
        '    view: "Additional Probe"\n'
        "interactions: []\n"
    )
    return load_dashboard(p, enforce_framework_prefix=False)


# --- deps._refs_from_view / audit_bundle_dependencies -------------------------

def _seed_cache(cache_dir: Path) -> None:
    ak = cache_dir / "VMWARE"
    ak.mkdir(parents=True, exist_ok=True)
    (ak / "HostSystem.json").write_text(json.dumps({
        "adapter_kind": "VMWARE", "resource_kind": "HostSystem",
        "metrics": {GOOD_KEY: {"name": "CPU|Usage", "default_monitored": True}},
        "properties": {},
    }))


def test_deps_refs_include_additional_column_keys(tmp_path):
    from vcfcf_core.packaging.deps import _refs_from_view

    view = _load(tmp_path, [_sm_col(), _bad_col()])
    keys = [r.metric_key for r in _refs_from_view(view)]
    assert BAD_KEY in keys
    # The super metric is not a built-in key.
    assert not any("supermetric" in k.lower() or "sm_" in k for k in keys)


def test_build_audit_catches_bad_additional_column_key(tmp_path):
    from vcfcf_packaging.audit import AuditError, audit_bundle_dependencies
    from vcfcf_packaging.describe import DescribeCache

    _seed_cache(tmp_path / "cache")
    cache = DescribeCache(cache_dir=tmp_path / "cache", client=None)
    bundle = SimpleNamespace(supermetrics=[], views=[_load(tmp_path, [_bad_col()])],
                             dashboards=[], customgroups=[], builtin_metric_enables=[])
    with pytest.raises(AuditError, match=r"cpu\|no_such_metric_probe"):
        audit_bundle_dependencies(bundle, cache, mode="auto")
    good = SimpleNamespace(supermetrics=[], views=[_load(tmp_path, [_sm_col()])],
                           dashboards=[], customgroups=[], builtin_metric_enables=[])
    assert not audit_bundle_dependencies(good, cache, mode="auto").unknown


# --- audit._refs_from_views_xml (staged bundle) -------------------------------

def test_staged_audit_reads_distribution_additional_columns(tmp_path):
    from vcfcf_core.dashboards.render import render_views_xml
    from vcfcf_core.packaging.audit import _refs_from_views_xml

    view = _load(tmp_path, [_sm_col(), _bad_col()])
    xml = render_views_xml([view], sm_map={SM_NAME: SM_ID})
    assert "distributionAdditionalColumns" in xml
    p = tmp_path / "views_content.xml"
    p.write_text(xml)
    keys = [r.metric_key for r in _refs_from_views_xml(p)]
    assert BAD_KEY in keys
    assert not any("sm_" in k for k in keys)


# --- dep_walker ----------------------------------------------------------------

def test_extract_refs_from_views_reads_additional_columns(tmp_path):
    from vcfcf_core.common.dep_walker import extract_refs_from_views
    from vcfcf_core.supermetrics.column_resolver import SmColumnResolver

    view = _load(tmp_path, [_sm_col(), _bad_col()])
    sm_refs, metric_refs = extract_refs_from_views(
        [view], column_resolver=SmColumnResolver([_sm()]))
    assert [(r.sm_id, r.name) for r in sm_refs] == [(SM_ID, SM_NAME)]
    assert "additional col" in sm_refs[0].source
    assert BAD_KEY in [r.metric_key for r in metric_refs]


def test_supermetrics_used_by_reads_additional_columns(tmp_path):
    from vcfcf_core.common.dep_walker import supermetrics_used_by

    used, unresolved = supermetrics_used_by([_load(tmp_path, [_sm_col()])], [], [_sm()])
    assert [s.id for s in used] == [SM_ID]
    assert unresolved == []
    _, unresolved = supermetrics_used_by([_load(tmp_path, [_sm_col()])], [], [])
    assert unresolved and "additional col" in unresolved[0]


def test_collect_deps_bundles_additional_column_sm(tmp_path):
    from vcfcf_core.common.dep_walker import collect_deps

    view = _load(tmp_path, [_sm_col()])
    graph = collect_deps([_dashboard(tmp_path)], [view], [_sm()], [])
    assert graph.errors == []
    assert [s.id for s in graph.supermetrics] == [SM_ID]
    graph = collect_deps([_dashboard(tmp_path)], [view], [], [])
    assert any("additional col 'SM'" in e and SM_NAME in e for e in graph.errors)


# --- discrete_builder ------------------------------------------------------------

def test_discrete_view_deps_bundle_additional_column_sm(tmp_path):
    from vcfcf_packaging.discrete_builder import _resolve_view_deps

    view = _load(tmp_path, [_sm_col()])
    assert [s.id for s in _resolve_view_deps(view, [_sm()])] == [SM_ID]
    assert _resolve_view_deps(view, []) == []


def test_discrete_view_deps_resolve_name_form_main_column(tmp_path):
    """The same name resolution covers a supermetric:"<name>" in columns:."""
    from vcfcf_packaging.discrete_builder import _resolve_view_deps

    data = _view_data([_bad_col()])
    data["columns"] = [{"attribute": f'supermetric:"{SM_NAME}"', "display_name": "SM"}]
    p = tmp_path / "main.yaml"
    p.write_text(yaml.safe_dump(data, sort_keys=False))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        view = load_view(p, enforce_framework_prefix=False)
    assert [s.id for s in _resolve_view_deps(view, [_sm()])] == [SM_ID]


# --- column_resolver (validate / sync column check) ------------------------------

def test_column_problems_cover_additional_columns(tmp_path):
    from vcfcf_core.supermetrics.column_resolver import SmColumnResolver

    view = _load(tmp_path, [_sm_col()])
    assert SmColumnResolver([_sm()]).column_problems([view]) == []
    problems = SmColumnResolver([]).column_problems([view])
    assert [k for k, _ in problems] == ["unresolved"]
    assert 'additional column "SM"' in problems[0][1]

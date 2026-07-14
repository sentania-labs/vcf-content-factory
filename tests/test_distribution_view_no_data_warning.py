"""Validate-time WARNING for the distribution-view "no data" footgun
(DEF-012, knowledge/context/api-surface/distribution_view_no_data.md).

A `data_type: distribution` view whose column looks like a string/enum
resource property (property-style attribute key, `is_property: false`) but
is bucketed with a fixed numeric histogram (not `dynamic: true` +
`calc_function: DISCRETE`) silently renders "No data to display" — the
metric subsystem has nothing to serve for a property key. This is a
WARNING only: genuinely numeric distributions (no `buckets:` block, or an
intentional fixed numeric histogram) must not break.

Cases covered:
  T1 — broken shape (property-looking attribute, no buckets block) -> warns.
  T2 — broken shape (property-looking attribute, explicit non-dynamic
       buckets) -> warns.
  T3 — fixed shape (is_property: true, is_string_attribute: true, dynamic
       DISCRETE buckets) -> no warning.
  T4 — genuinely numeric distribution (no buckets block, numeric-sounding
       attribute) -> no warning.
  T5 — genuinely numeric distribution with an explicit fixed histogram
       (min/max/count, not dynamic) -> no warning.
  T6 — supermetric formula reference as the distribution attribute -> no
       warning regardless of shape (supermetric output is always numeric).
  T7 — non-distribution data_type (list) with a property column -> no
       warning (guard is scoped to data_type: distribution only).
  T8 — real-repo regression: all data_type: distribution views under
       content/sdk-adapters/vcommunity-vsphere/views/ (the four originally
       fixed ESXi Host Details views plus every view touched by the
       DEF-012 remediation sweep) must not warn.
"""
from __future__ import annotations

import textwrap
import warnings
from pathlib import Path

import pytest
import yaml


def _write_view(views_dir: Path, stem: str, data: dict) -> Path:
    views_dir.mkdir(parents=True, exist_ok=True)
    p = views_dir / f"{stem}.yaml"
    p.write_text(yaml.dump(data, default_flow_style=False))
    return p


def _base_view(name: str, attribute: str, extra_column: dict | None = None) -> dict:
    col = {"attribute": attribute, "display_name": "Col"}
    if extra_column:
        col.update(extra_column)
    return {
        "name": name,
        "subject": {"adapter_kind": "VMWARE", "resource_kind": "HostSystem"},
        "data_type": "distribution",
        "columns": [col],
    }


def _load_and_capture(path: Path):
    from vcfops_dashboards.loader import load_view

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        view = load_view(path, enforce_framework_prefix=False)
    no_data_warnings = [
        str(w.message) for w in caught
        if issubclass(w.category, UserWarning) and "No data to display" in str(w.message)
    ]
    return view, no_data_warnings


# ---------------------------------------------------------------------------
# T1 — broken shape, no buckets block at all
# ---------------------------------------------------------------------------

def test_property_attribute_no_buckets_warns(tmp_path):
    views_dir = tmp_path / "views"
    p = _write_view(
        views_dir, "broken_version",
        _base_view("Broken Version Distribution", "summary|version"),
    )
    view, warned = _load_and_capture(p)
    assert len(warned) == 1, f"expected exactly one warning, got: {warned}"
    assert "Broken Version Distribution" in warned[0]
    assert "summary|version" in warned[0]
    assert "is_property: true" in warned[0]


# ---------------------------------------------------------------------------
# T2 — broken shape, explicit non-dynamic buckets
# ---------------------------------------------------------------------------

def test_property_attribute_explicit_fixed_buckets_warns(tmp_path):
    views_dir = tmp_path / "views"
    data = _base_view("Broken Model Distribution", "hardware|vendorModel")
    data["buckets"] = {"min_value": 0.0, "max_value": 100.0, "count": 10}
    p = _write_view(views_dir, "broken_model", data)
    view, warned = _load_and_capture(p)
    assert len(warned) == 1, f"expected exactly one warning, got: {warned}"
    assert "hardware|vendorModel" in warned[0]


# ---------------------------------------------------------------------------
# T3 — fixed shape: is_property + is_string_attribute + dynamic DISCRETE
# ---------------------------------------------------------------------------

def test_fixed_property_distribution_shape_does_not_warn(tmp_path):
    views_dir = tmp_path / "views"
    data = _base_view(
        "Fixed Version Distribution", "summary|version",
        extra_column={"is_property": True, "is_string_attribute": True},
    )
    data["buckets"] = {"dynamic": True, "calc_function": "DISCRETE"}
    p = _write_view(views_dir, "fixed_version", data)
    view, warned = _load_and_capture(p)
    assert warned == [], f"expected no warning for fixed shape, got: {warned}"


# ---------------------------------------------------------------------------
# T4 — genuinely numeric distribution, no buckets block
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("attribute", [
    "hardware|cpuInfo|numCpuCores",
    "hardware|cpuInfo|hz",
    "cpu|speed",
    "config|hardware|memoryKB",
    "config|cpuAllocation|reservation",
    "OnlineCapacityAnalytics|capacityRemainingPercentage",
    "mem|reservedCapacity_average",
    "summary|total_number_hosts",
])
def test_numeric_distribution_no_buckets_does_not_warn(tmp_path, attribute):
    views_dir = tmp_path / "views"
    p = _write_view(
        views_dir, "numeric_" + attribute.replace("|", "_"),
        _base_view("Numeric Distribution", attribute),
    )
    view, warned = _load_and_capture(p)
    assert warned == [], f"expected no warning for numeric attribute {attribute!r}, got: {warned}"


# ---------------------------------------------------------------------------
# T5 — genuinely numeric distribution with explicit fixed histogram
# ---------------------------------------------------------------------------

def test_numeric_distribution_explicit_fixed_buckets_does_not_warn(tmp_path):
    views_dir = tmp_path / "views"
    data = _base_view("Numeric Core Count Distribution", "hardware|cpuInfo|numCpuCores")
    data["buckets"] = {"min_value": 0.0, "max_value": 64.0, "count": 8}
    p = _write_view(views_dir, "numeric_fixed", data)
    view, warned = _load_and_capture(p)
    assert warned == [], f"expected no warning for numeric fixed-histogram distribution, got: {warned}"


# ---------------------------------------------------------------------------
# T6 — supermetric formula reference never warns
# ---------------------------------------------------------------------------

def test_supermetric_attribute_never_warns(tmp_path):
    views_dir = tmp_path / "views"
    p = _write_view(
        views_dir, "sm_ref",
        _base_view("Share Distribution", 'supermetric:"Share per vCPU"'),
    )
    view, warned = _load_and_capture(p)
    assert warned == [], f"expected no warning for supermetric attribute, got: {warned}"


# ---------------------------------------------------------------------------
# T7 — non-distribution data_type is unaffected
# ---------------------------------------------------------------------------

def test_list_view_with_property_column_does_not_warn(tmp_path):
    views_dir = tmp_path / "views"
    data = {
        "name": "List View With Version Column",
        "subject": {"adapter_kind": "VMWARE", "resource_kind": "HostSystem"},
        "data_type": "list",
        "columns": [
            {"attribute": "summary|version", "display_name": "Version", "is_property": True},
        ],
    }
    p = _write_view(views_dir, "list_version", data)
    view, warned = _load_and_capture(p)
    assert warned == [], f"expected no warning for list-view property column, got: {warned}"


# ---------------------------------------------------------------------------
# T8 — real-repo regression: vcommunity-vsphere distribution views
# ---------------------------------------------------------------------------

def test_real_repo_vcommunity_vsphere_distribution_views_do_not_warn():
    """Every data_type: distribution view under the vcommunity-vsphere SDK
    adapter must not trigger the guard — this is the corpus the DEF-012
    remediation sweep fixed (four originally-fixed ESXi Host
    Details views plus every view touched by the follow-up sweep)."""
    from vcfops_dashboards.loader import load_view

    repo_root = Path(__file__).parent.parent
    views_dir = repo_root / "content" / "sdk-adapters" / "vcommunity-vsphere" / "views"
    if not views_dir.exists():
        pytest.skip("vcommunity-vsphere sdk-adapter content not present")

    yaml_files = sorted(views_dir.glob("*.yaml"))
    distribution_files = []
    for f in yaml_files:
        raw = yaml.safe_load(f.read_text())
        if isinstance(raw, dict) and raw.get("data_type") == "distribution":
            distribution_files.append(f)

    assert distribution_files, "expected at least one distribution view in the fixture corpus"

    all_warnings = []
    for f in distribution_files:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            load_view(f, enforce_framework_prefix=False)
        for w in caught:
            if issubclass(w.category, UserWarning) and "No data to display" in str(w.message):
                all_warnings.append((f.name, str(w.message)))

    assert all_warnings == [], (
        f"expected zero distribution-view 'no data' warnings in the fixed "
        f"vcommunity-vsphere corpus, got: {all_warnings}"
    )

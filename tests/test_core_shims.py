"""M2 shims: each old ``vcfcf_<type>.<module>`` path is the SAME module
object as its ``vcfcf_core`` home, not a namespace copy.

The alias pattern (``sys.modules[__name__] = <core module>``) means every
name, underscore-prefixed or not, resolves through the old path, and a
monkeypatch on the old path patches the module the factory actually runs.
Design: ``knowledge/designs/tooling-core-carveout-v1.md``.

Row 2 adds two WRAPPER modules that are deliberately not aliases, because
the old path keeps factory-only behaviour on top of the core half:
``vcfcf_dashboards.loader`` (id minting into the YAML, provenance from the
repo layout) and ``vcfcf_dashboards.summary_bind`` (the live ``ui`` half).
For those the tests pin what the wrapper must still guarantee: every core
name resolves through the old path to the identical object, and the
factory-only names stay on the factory side.

Row 3 adds three aliases (``vcfcf_supermetrics.reverse``,
``vcfcf_reports.render``, ``vcfcf_packaging.deps``) and eight wrappers:
``vcfcf_common.dep_walker`` (the live half), ``vcfcf_common.provenance``
(the repo-root sniff), ``vcfcf_packaging.describe`` (cache location, live
refresh, ``make_cache``), ``vcfcf_packaging.audit`` (``run_dependency_audit``),
``vcfcf_supermetrics.loader``, ``vcfcf_customgroups.loader``,
``vcfcf_reports.loader`` (minting, provenance, directory defaults, the
unscoped ``sm_id_map`` scan) and ``vcfcf_packaging.loader`` (root sniff,
callbacks, ``bundles`` default). Every wrapper serves core names through
module ``__getattr__`` (reads are identical objects; a write on the old
path does NOT reach core, pinned below), and ``vcfcf_packaging.builder``
re-exports the assembly helpers that moved to
``vcfcf_core.packaging.assembly``.
"""
from __future__ import annotations

import importlib

import pytest

SHIMS = [
    ("vcfcf_dashboards.yaml_utils", "vcfcf_core.dashboards.yaml_utils"),
    ("vcfcf_supermetrics.crossref", "vcfcf_core.supermetrics.crossref"),
    ("vcfcf_symptoms.loader", "vcfcf_core.symptoms.loader"),
    ("vcfcf_alerts.loader", "vcfcf_core.alerts.loader"),
    ("vcfcf_alerts.render", "vcfcf_core.alerts.render"),
    ("vcfcf_packaging.release_types", "vcfcf_core.packaging.release_types"),
    ("vcfcf_packaging.template_version", "vcfcf_core.packaging.template_version"),
    # Row 2.
    ("vcfcf_dashboards.reverse", "vcfcf_core.dashboards.reverse"),
    ("vcfcf_dashboards.render", "vcfcf_core.dashboards.render"),
    ("vcfcf_dashboards.packager", "vcfcf_core.dashboards.packager"),
    # Row 3.
    ("vcfcf_supermetrics.reverse", "vcfcf_core.supermetrics.reverse"),
    ("vcfcf_reports.render", "vcfcf_core.reports.render"),
    ("vcfcf_packaging.deps", "vcfcf_core.packaging.deps"),
]

# Row 3 wrappers: (old path, core path,
#   names the wrapper defines itself,
#   core names the wrapper imports explicitly (a namespace copy, for its own
#     annotations and calls; identical object on read),
#   core names served only by module __getattr__ (identical object on read,
#     never copied into the wrapper namespace)).
WRAPPERS = [
    ("vcfcf_common.dep_walker", "vcfcf_core.common.dep_walker",
     ("walk_and_check", "WalkResult", "MetricGap", "_fetch_describe", "_enable_sm",
      "_lookup_sm_uuid_on_target", "_resolve_sm_name", "_get_sm_resource_kinds", "_LOOKUP_FAILED"),
     ("MetricRef", "SmRef", "extract_refs_from_supermetrics", "extract_refs_from_views",
      "extract_refs_from_dashboards", "extract_customgroup_names_from_views"),
     ("collect_deps", "expand_sm_crossrefs", "DepGraph", "CollectDepsCrossLinks",
      "extract_view_names_from_dashboards", "extract_customgroup_names_from_dashboards",
      "_scope_allows", "_auto_detect_scope", "_pick_sm_by_name", "_walk_sm_crossrefs",
      "_is_sm_key", "_extract_sm_uuid", "_SM_UUID_RE")),
    ("vcfcf_common.provenance", "vcfcf_core.common.provenance",
     ("_find_repo_root", "provenance_from_path"),
     (),
     ()),
    ("vcfcf_packaging.describe", "vcfcf_core.packaging.describe",
     ("DescribeCache", "make_cache", "_DEFAULT_CACHE_ROOT", "_REPO_ROOT", "_same_but_fetched_at"),
     ("MetricInfo", "DescribeCacheError", "_merge_section", "_counts", "_summarize", "_host_of",
      "_is_instance_local"),
     ("MergeStats", "_INSTANCE_LOCAL_PREFIX")),
    ("vcfcf_packaging.audit", "vcfcf_core.packaging.audit",
     ("run_dependency_audit",),
     ("AuditError", "AuditResult", "audit_bundle_dependencies"),
     ("analyze_staged_bundle", "print_audit_summary", "staged_bundle_problem",
      "check_staged_bundle_dir", "_check_cache_coverage", "_bundle_declares",
      "_refs_from_views_xml", "_refs_from_dashboard_json", "_refs_from_widget_config",
      "_RESOURCE_ENTRY_RE")),
    ("vcfcf_supermetrics.loader", "vcfcf_core.supermetrics.loader",
     ("load_file", "load_dir", "sm_id_map", "_mint_id_into_file", "_provenance_of"),
     ("SuperMetricDef",),
     ("SuperMetricValidationError", "LOOPING_FUNCS", "SINGLE_FUNCS", "_strict_load",
      "_UUID_RE", "_resolve_id")),
    ("vcfcf_customgroups.loader", "vcfcf_core.customgroups.loader",
     ("load_file", "load_dir", "_provenance_of"),
     ("CustomGroupDef",),
     ("CustomGroupValidationError", "COMPARE_OPS", "RELATIONS", "collect_required_types",
      "_strict_load", "_UI_STRING_OP_MAP", "_UI_NUMERIC_OP_MAP",
      "_property_condition_to_wire", "_relationship_condition_to_wire")),
    ("vcfcf_reports.loader", "vcfcf_core.reports.loader",
     ("load_file", "load_dir", "_mint_id_into_file"),
     ("ReportDef",),
     ("Section", "SubjectType", "ReportSettings", "ReportValidationError", "SECTION_TYPES",
      "VALID_ORIENTATIONS", "VALID_OUTPUT_FORMATS", "_STATIC_CONTENT_KEYS", "_strict_load",
      "_UUID_RE", "_build_view_index", "_build_dashboard_index", "_resolve_id")),
    ("vcfcf_packaging.loader", "vcfcf_core.packaging.loader",
     ("load_bundle", "load_all_bundles", "_find_repo_root", "_mint_id_into_file", "_provenance_of"),
     ("Bundle", "BundleValidationError"),
     ("BuiltinMetricEnable", "parse_builtin_metric_enables", "render_bme_items")),
]


@pytest.mark.parametrize("old,new", SHIMS, ids=[o for o, _ in SHIMS])
def test_old_path_is_the_core_module_object(old: str, new: str) -> None:
    assert importlib.import_module(old) is importlib.import_module(new)


def test_alerts_render_identity() -> None:
    import vcfcf_alerts.render
    import vcfcf_core.alerts.render

    assert vcfcf_alerts.render is vcfcf_core.alerts.render


def test_underscore_names_resolve_through_old_paths() -> None:
    from vcfcf_symptoms.loader import _condition_to_wire  # noqa: PLC0415
    from vcfcf_alerts.render import _symptom_id  # noqa: PLC0415
    from vcfcf_packaging.release_types import _SOURCE_TO_DIST  # noqa: PLC0415
    from vcfcf_dashboards.yaml_utils import _StrictKeyLoader  # noqa: PLC0415
    from vcfcf_dashboards.render import _VIEW_PIN_CONTAINER, _render_view_def_fragment  # noqa: PLC0415
    from vcfcf_dashboards.reverse import _build_resource_lookup  # noqa: PLC0415
    from vcfcf_dashboards.packager import _build_views_inner_zip  # noqa: PLC0415

    assert callable(_condition_to_wire)
    assert callable(_symptom_id)
    assert isinstance(_SOURCE_TO_DIST, dict)
    assert _StrictKeyLoader is not None
    assert isinstance(_VIEW_PIN_CONTAINER, dict)
    assert callable(_render_view_def_fragment)
    assert callable(_build_resource_lookup)
    assert callable(_build_views_inner_zip)


def test_monkeypatch_on_old_path_reaches_the_running_module(monkeypatch) -> None:
    import vcfcf_core.packaging.template_version as core_tv
    import vcfcf_packaging.template_version as old_tv

    monkeypatch.setattr(old_tv, "CURRENT_TEMPLATE_VERSION", "9999-01-01-1")
    assert core_tv.CURRENT_TEMPLATE_VERSION == "9999-01-01-1"


def test_row2_monkeypatch_on_old_render_path_reaches_the_running_module(monkeypatch) -> None:
    import vcfcf_core.dashboards.render as core_render
    import vcfcf_dashboards.render as old_render

    monkeypatch.setattr(old_render, "_VIEW_PIN_CONTAINER", {"probe": "row2"})
    assert core_render._VIEW_PIN_CONTAINER == {"probe": "row2"}


# ---------------------------------------------------------------------------
# Row 2 wrappers: vcfcf_dashboards.loader and vcfcf_dashboards.summary_bind
# ---------------------------------------------------------------------------

def test_loader_wrapper_resolves_every_core_name_to_the_same_object() -> None:
    import vcfcf_core.dashboards.loader as core
    import vcfcf_dashboards.loader as old

    assert old is not core  # wrapper, not alias: it adds minting + provenance
    for name in ("ViewDef", "Dashboard", "DashboardValidationError", "stable_id",
                 "parse_summary_for", "check_unique_summary_for", "_UUID_RE",
                 "_strict_load", "_SECTION_FORBIDDEN_KEYS", "_resolve_id"):
        assert getattr(old, name) is getattr(core, name), name
    with pytest.raises(AttributeError):
        old.__getattr__("_no_such_name_row2")
    # Nothing is copied into the wrapper namespace: reads go through
    # __getattr__ (identical objects above), and a write on the old path
    # therefore does NOT reach core, which the wrapper docstring states.
    assert "stable_id" not in vars(old)
    assert "ViewColumn" not in vars(old)


def test_loader_wrapper_keeps_minting_and_provenance_on_the_factory_side(tmp_path) -> None:
    import vcfcf_core.dashboards.loader as core
    import vcfcf_dashboards.loader as old

    assert not hasattr(core, "_mint_id_into_file")
    assert callable(old._mint_id_into_file)
    assert old.load_view is not core.load_view
    assert old.load_dashboard is not core.load_dashboard
    assert old.load_all is not core.load_all

    view = tmp_path / "v.yaml"
    view.write_text(
        "name: \"[VCF Content Factory] Row2 Mint Probe\"\n"
        "subject: {adapter_kind: VMWARE, resource_kind: HostSystem}\n"
        "columns:\n  - {display_name: CPU, attribute: cpu|usage_average}\n",
        encoding="utf-8",
    )
    # The library refuses to mint; the factory wrapper mints into the file.
    with pytest.raises(core.DashboardValidationError, match="missing id"):
        core.load_view(view)
    before = view.read_text(encoding="utf-8")
    assert not before.startswith("id:")
    loaded = old.load_view(view)
    after = view.read_text(encoding="utf-8")
    assert after.startswith(f"id: {loaded.id}\n")
    assert core._UUID_RE.match(loaded.id)
    # A second core load of the now-minted file needs no callback and writes nothing.
    again = core.load_view(view)
    assert again.id == loaded.id
    assert view.read_text(encoding="utf-8") == after
    assert again.provenance == ""


def test_summary_bind_wrapper_reexports_the_core_half() -> None:
    import vcfcf_core.dashboards.summary_bind as core
    import vcfcf_dashboards.summary_bind as old

    assert old is not core  # wrapper: keeps the live ``ui`` half
    for name in ("resource_kind_id", "KindTarget", "BindPlan", "plan_bindings",
                 "_find_kind_entry", "_default_template_name"):
        assert getattr(old, name) is getattr(core, name), name
    for name in ("bind_summary", "_resolve_installed", "_live_tab_id", "print_err"):
        assert hasattr(old, name), name
        assert not hasattr(core, name), name


@pytest.mark.parametrize("garbage", ["", "not-a-uuid", "  ", None, "00000000-0000-0000-0000-00000000000"])
def test_core_loader_validates_the_minted_id_like_a_yaml_id(tmp_path, garbage) -> None:
    """Codex round on PR #162: an on_missing_id return is normalized and
    validated exactly like an id read from YAML, and the error names the
    callback. The factory's _mint_id_into_file still passes."""
    import vcfcf_core.dashboards.loader as core
    import vcfcf_dashboards.loader as old

    view = tmp_path / "v.yaml"
    view.write_text(
        "name: \"[VCF Content Factory] Row2 Garbage Mint Probe\"\n"
        "subject: {adapter_kind: VMWARE, resource_kind: HostSystem}\n"
        "columns:\n  - {display_name: CPU, attribute: cpu|usage_average}\n",
        encoding="utf-8",
    )
    dash = tmp_path / "d.yaml"
    dash.write_text("name: \"[VCF Content Factory] Row2 Garbage Mint Dash\"\nwidgets: []\n", encoding="utf-8")

    def bad_minter(path):
        return garbage

    for loader, target in ((core.load_view, view), (core.load_dashboard, dash)):
        with pytest.raises(core.DashboardValidationError, match=r"on_missing_id \(bad_minter\).*not a valid uuid4"):
            loader(target, on_missing_id=bad_minter)
    # Nothing was written by the library on the failed path.
    assert not view.read_text(encoding="utf-8").startswith("id:")

    # Upper-case output from a callback is normalized, as a YAML id is.
    loaded = core.load_view(view, on_missing_id=lambda p: "6F9619FF-8B86-4D11-B42D-00C04FC964FF")
    assert loaded.id == "6f9619ff-8b86-4d11-b42d-00c04fc964ff"

    # The factory wrapper's real minter still passes and lands in the file.
    minted = old.load_dashboard(dash)
    assert core._UUID_RE.match(minted.id)
    assert dash.read_text(encoding="utf-8").startswith(f"id: {minted.id}\n")


# ---------------------------------------------------------------------------
# Row 3 aliases and wrappers
# ---------------------------------------------------------------------------

def test_row3_underscore_names_resolve_through_aliases() -> None:
    from vcfcf_supermetrics.reverse import _SM_UUID_TOKEN_RE  # noqa: PLC0415
    from vcfcf_reports.render import _render_section, _build_reports_inner_zip  # noqa: PLC0415
    from vcfcf_packaging.deps import _is_sm_ref, _normalize_metric_key, _refs_from_formula  # noqa: PLC0415

    assert _SM_UUID_TOKEN_RE.pattern.startswith("sm_")
    assert callable(_render_section) and callable(_build_reports_inner_zip)
    assert callable(_is_sm_ref) and callable(_normalize_metric_key) and callable(_refs_from_formula)


def test_row3_monkeypatch_on_alias_reaches_the_running_module(monkeypatch) -> None:
    import vcfcf_core.packaging.deps as core_deps
    import vcfcf_packaging.deps as old_deps

    monkeypatch.setattr(old_deps, "_SUPER_METRIC_PREFIX", "probe|")
    assert core_deps._SUPER_METRIC_PREFIX == "probe|"


@pytest.mark.parametrize("old,new,own,imported,served", WRAPPERS, ids=[w[0] for w in WRAPPERS])
def test_row3_wrapper_serves_core_names_and_keeps_its_own(old, new, own, imported, served) -> None:
    old_mod = importlib.import_module(old)
    core_mod = importlib.import_module(new)
    assert old_mod is not core_mod  # wrapper, not alias
    for name in imported + served:
        assert getattr(old_mod, name) is getattr(core_mod, name), f"{old}.{name}"
    for name in imported:
        assert name in vars(old_mod), f"{old} should import {name} explicitly"
    for name in served:
        # Served by __getattr__, never copied: a monkeypatch on the old path
        # binds here and does NOT reach core (the wrapper docstrings say so).
        assert name not in vars(old_mod), f"{old}.{name} is a namespace copy"
    for name in own:
        assert name in vars(old_mod), f"{old} must define {name} itself"
        assert not hasattr(core_mod, name) or getattr(old_mod, name) is not getattr(core_mod, name), (
            f"{name} should be the factory's own object, not core's"
        )
    with pytest.raises(AttributeError):
        old_mod.__getattr__("_no_such_name_row3")


@pytest.mark.parametrize("old,new,own,imported,served", WRAPPERS, ids=[w[0] for w in WRAPPERS])
def test_row3_wrapper_write_does_not_reach_core(old, new, own, imported, served, monkeypatch) -> None:
    """Pins the documented asymmetry: patch the core module, not the wrapper."""
    if not served:
        pytest.skip("wrapper defines every public name itself")
    old_mod = importlib.import_module(old)
    core_mod = importlib.import_module(new)
    name = served[0]
    original = getattr(core_mod, name)
    monkeypatch.setattr(old_mod, name, "probe-row3", raising=False)
    assert getattr(core_mod, name) is original
    assert getattr(old_mod, name) == "probe-row3"


def test_row3_factory_only_names_are_absent_from_core() -> None:
    import vcfcf_core.common.dep_walker as core_dw
    import vcfcf_core.common.provenance as core_prov
    import vcfcf_core.packaging.describe as core_desc
    import vcfcf_core.packaging.audit as core_audit
    import vcfcf_core.supermetrics.loader as core_sm
    import vcfcf_core.reports.loader as core_rpt
    import vcfcf_core.packaging.loader as core_bundle

    for mod, names in (
        (core_dw, ("walk_and_check", "WalkResult", "MetricGap", "_fetch_describe", "_enable_sm")),
        (core_prov, ("_find_repo_root",)),
        (core_desc, ("make_cache", "_DEFAULT_CACHE_ROOT", "_REPO_ROOT")),
        (core_audit, ("run_dependency_audit",)),
        (core_sm, ("_mint_id_into_file",)),
        (core_rpt, ("_mint_id_into_file",)),
        (core_bundle, ("_find_repo_root", "_mint_id_into_file")),
    ):
        for name in names:
            assert not hasattr(mod, name), f"{mod.__name__}.{name} must stay factory-side"
    assert not hasattr(core_desc.DescribeCache, "refresh")
    assert not hasattr(core_desc.DescribeCache, "refresh_all")


def test_row3_describe_wrapper_is_a_core_subclass_with_the_factory_default() -> None:
    import vcfcf_core.packaging.describe as core
    import vcfcf_packaging.describe as old

    assert issubclass(old.DescribeCache, core.DescribeCache)
    assert old.DescribeCache is not core.DescribeCache
    c = old.DescribeCache()
    assert c._cache_dir == old._DEFAULT_CACHE_ROOT
    assert old._DEFAULT_CACHE_ROOT.name == "adapter_describe_cache"
    assert c._client is None
    assert hasattr(old.DescribeCache, "refresh") and hasattr(old.DescribeCache, "refresh_all")
    with pytest.raises(TypeError, match="cache_dir is required"):
        core.DescribeCache(None)  # type: ignore[arg-type]


def test_row3_builder_reexports_the_assembly_helpers() -> None:
    import vcfcf_core.packaging.assembly as asm
    import vcfcf_packaging.builder as builder

    for name in ("PLACEHOLDER_USER_ID", "DASHBOARD_DROPIN_USER_ID", "_render_supermetrics_dict",
                 "_render_customgroup_rest_payload", "_render_customgroup_ui_payload",
                 "_build_views_inner_zip", "_build_dashboard_dropin_zip", "_build_reports_dropin_zip",
                 "_build_bundle_json", "render_bundle_payloads", "render_vcfops_manifest",
                 "assemble_distribution_zip"):
        assert getattr(builder, name) is getattr(asm, name), name
    assert builder.DASHBOARD_DROPIN_USER_ID == "b58a71ee-e909-5b40-a355-9e199e6f0f53"


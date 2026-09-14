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

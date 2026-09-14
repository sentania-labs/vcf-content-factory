"""M2 row 1 shims: each old ``vcfcf_<type>.<module>`` path is the SAME module
object as its ``vcfcf_core`` home, not a namespace copy.

The alias pattern (``sys.modules[__name__] = <core module>``) means every
name, underscore-prefixed or not, resolves through the old path, and a
monkeypatch on the old path patches the module the factory actually runs.
Design: ``knowledge/designs/tooling-core-carveout-v1.md``.
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

    assert callable(_condition_to_wire)
    assert callable(_symptom_id)
    assert isinstance(_SOURCE_TO_DIST, dict)
    assert _StrictKeyLoader is not None


def test_monkeypatch_on_old_path_reaches_the_running_module(monkeypatch) -> None:
    import vcfcf_core.packaging.template_version as core_tv
    import vcfcf_packaging.template_version as old_tv

    monkeypatch.setattr(old_tv, "CURRENT_TEMPLATE_VERSION", "9999-01-01-1")
    assert core_tv.CURRENT_TEMPLATE_VERSION == "9999-01-01-1"

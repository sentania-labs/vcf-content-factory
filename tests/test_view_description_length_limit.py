"""View `description` > 1024 chars — validate-time rejection.

VCF Operations 9.1 silently fails a VIEW_DEFINITIONS content-zip import
when the rendered <Description> exceeds 1024 characters (state=FAILED,
skipped=1, errorMessages=[]). Empirically bisected 2026-07-27 (devel
install close-out); see knowledge/context/known_limitations.md §14 and
knowledge/context/wire-formats/view_column_wire_format.md "View-level
field limits". `ViewDef.validate()` converts that silent server-side
failure into a local `DashboardValidationError` at exactly the same
boundary: 1024 chars passes, 1025 chars fails.

Scoped to VIEW_DEFINITIONS / description only — the limit is untested
for other content types and must not be generalized.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml


def _write_view(tmp_path: Path, data: dict, stem: str = "view") -> Path:
    d = tmp_path / "views"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{stem}.yaml"
    p.write_text(yaml.dump(data, default_flow_style=False))
    return p


def _view_data(description: str) -> dict:
    return {
        "name": "[VCF Content Factory] Description Length Test",
        "description": description,
        "subject": {"adapter_kind": "VMWARE", "resource_kind": "VirtualMachine"},
        "columns": [
            {"attribute": "cpu|usage_average", "display_name": "CPU Usage"},
        ],
    }


def test_description_at_1024_chars_passes(tmp_path):
    from vcfops_dashboards.loader import load_view

    p = _write_view(tmp_path, _view_data("x" * 1024))
    v = load_view(p, enforce_framework_prefix=False)
    v.validate(enforce_framework_prefix=False)
    assert len(v.description) == 1024


def test_description_at_1025_chars_rejected(tmp_path):
    from vcfops_dashboards.loader import load_view, DashboardValidationError

    p = _write_view(tmp_path, _view_data("x" * 1025))
    with pytest.raises(DashboardValidationError, match="1024-character limit"):
        load_view(p, enforce_framework_prefix=False)

"""Per-widget minimum VCF Ops version table and validate warning (issue #199).

A Section widget aborts the whole dashboard import on 9.0.2 (WidgetType enum
has no Section).  No bundle, release or adapter field declares a target Ops
version, so validate warns whenever a dashboard uses a type with a known
floor; widget_version_problems() also takes an explicit target for the gate
that a future target-version field will drive.
"""
from __future__ import annotations

import re
import sys
import warnings
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vcfcf_core.dashboards.loader import (  # noqa: E402
    DashboardValidationError,
    load_all,
)
from vcfcf_core.dashboards.widget_versions import (  # noqa: E402
    OLDEST_CHECKED_OPS_VERSION,
    WIDGET_TYPE_MIN_OPS_VERSION,
    parse_ops_version,
    widget_version_problems,
)

_TEXT = {"id": "t", "type": "TextDisplay", "title": "T",
         "coords": {"x": 1, "y": 2, "w": 4, "h": 2},
         "text_display_config": {"text": "hi"}}
_SECTION = {"id": "sec", "type": "Section", "title": "Header",
            "coords": {"x": 1, "y": 1, "w": 12, "h": 1}}


def _write(tmp_path: Path, widgets) -> Path:
    d = tmp_path / "dashboards"
    d.mkdir()
    (d / "d.yaml").write_text(yaml.safe_dump({
        "id": "0f5a4b3c-2d1e-4f60-8a7b-9c8d7e6f5a4b",
        "name": "[VCF Content Factory] Probe",
        "description": "",
        "widgets": widgets,
    }, sort_keys=False))
    return d


def _issue_199(caught):
    return [w for w in caught if "issue #199" in str(w.message)]


def _validate(tmp_path, widgets):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        load_all(tmp_path / "views", _write(tmp_path, widgets))
    return _issue_199(caught)


# --- table -------------------------------------------------------------------

def test_section_floor_is_above_the_oldest_checked_build():
    assert parse_ops_version(WIDGET_TYPE_MIN_OPS_VERSION["Section"]) > OLDEST_CHECKED_OPS_VERSION


def test_alert_volume_has_no_floor():
    """AlertVolume renders as IntSummaryAlertVolume, which 9.0.2 knows."""
    assert WIDGET_TYPE_MIN_OPS_VERSION["AlertVolume"] is None


def test_table_covers_every_type_the_validator_accepts(tmp_path):
    """A widget type added to the validator must get a table entry."""
    bogus = {**_TEXT, "type": "NoSuchWidget"}
    with pytest.raises(DashboardValidationError) as exc:
        load_all(tmp_path / "views", _write(tmp_path, [bogus]))
    m = re.search(r"\(supported: ([^)]*)\)", str(exc.value))
    assert m, str(exc.value)
    accepted = {t.strip() for t in m.group(1).split(",")}
    assert accepted == set(WIDGET_TYPE_MIN_OPS_VERSION)


@pytest.mark.parametrize("raw,expected", [
    ("9.0.2", (9, 0, 2)), ("9.0.2.0", (9, 0, 2)), ((9, 1, 1), (9, 1, 1)), ("9", (9,)),
])
def test_parse_ops_version(raw, expected):
    assert parse_ops_version(raw) == expected


@pytest.mark.parametrize("bad", ["", "9.x", "nine", "9..1"])
def test_parse_ops_version_rejects_garbage(bad):
    with pytest.raises(ValueError):
        parse_ops_version(bad)


# --- explicit target (the future gate) ---------------------------------------

@pytest.mark.parametrize("target", ["9.0.2", "9.0.2.0", "9.1.0", "8.18"])
def test_section_flagged_below_floor(target):
    probs = widget_version_problems([("sec", "Section"), ("t", "TextDisplay")], target)
    assert len(probs) == 1 and "Section" in probs[0] and "sec" in probs[0]


@pytest.mark.parametrize("target", ["9.1.1", "9.1.1.0", "9.2", "9.2.0.0"])
def test_section_clean_at_or_above_floor(target):
    assert widget_version_problems([("sec", "Section")], target) == []


def test_unfloored_types_never_flagged():
    widgets = [(t, t) for t, floor in WIDGET_TYPE_MIN_OPS_VERSION.items() if floor is None]
    assert widget_version_problems(widgets, "8.0") == []
    assert widget_version_problems(widgets) == []


def test_widgets_of_one_type_grouped_into_one_message():
    probs = widget_version_problems([("a", "Section"), ("b", "Section")], "9.0.2")
    assert len(probs) == 1 and "a, b" in probs[0]


# --- validate wiring (no target declared) ------------------------------------

def test_validate_warns_on_section_without_failing(tmp_path):
    hits = _validate(tmp_path, [_SECTION, _TEXT])
    assert len(hits) == 1
    msg = str(hits[0].message)
    assert "Section" in msg and "9.1.1" in msg and "no target version is declared" in msg
    assert "d.yaml" in msg


def test_validate_quiet_without_floored_types(tmp_path):
    assert _validate(tmp_path, [_TEXT]) == []

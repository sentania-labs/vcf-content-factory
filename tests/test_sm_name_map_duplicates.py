"""Duplicate SM display names are an error, not last-wins (issue #158).

A hand-authored bundle manifest listing two super metrics with the same
display name made ``@supermetric:"<name>"`` resolve to whichever loaded last.
The map builder now raises, naming both files, the way ``find_by_name``
raises on an ambiguous name.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vcfcf_core.supermetrics.crossref import (  # noqa: E402
    SuperMetricCrossRefError,
    sm_name_to_uuid_map,
)

NAME = "[VCF Content Factory] Dup SM"
UUID_1 = "11111111-1111-4111-8111-111111111111"
UUID_2 = "22222222-2222-4222-8222-222222222222"


class _SM:
    def __init__(self, name, sm_id, source_path=None, formula="${this, metric=cpu|usage_average}"):
        self.name = name
        self.id = sm_id
        self.source_path = source_path
        self.formula = formula


def test_duplicate_name_different_ids_raises_naming_both_files():
    a = _SM(NAME, UUID_1, Path("content/supermetrics/a.yaml"))
    b = _SM(NAME, UUID_2, Path("third_party/x/supermetrics/b.yaml"))
    with pytest.raises(SuperMetricCrossRefError) as exc:
        sm_name_to_uuid_map([a, b])
    msg = str(exc.value)
    assert NAME in msg
    assert "content/supermetrics/a.yaml" in msg
    assert "third_party/x/supermetrics/b.yaml" in msg
    assert UUID_1 in msg and UUID_2 in msg


def test_error_class_is_caller_selectable():
    class _Mine(ValueError):
        pass

    with pytest.raises(_Mine):
        sm_name_to_uuid_map([_SM(NAME, UUID_1), _SM(NAME, UUID_2)], error_cls=_Mine)


def test_same_sm_listed_twice_is_not_ambiguous():
    m = sm_name_to_uuid_map([_SM(NAME, UUID_1), _SM(NAME, UUID_1)])
    assert m == {NAME: UUID_1}


def test_idless_duplicate_against_id_is_ambiguous():
    with pytest.raises(SuperMetricCrossRefError):
        sm_name_to_uuid_map([_SM(NAME, None), _SM(NAME, UUID_1)])


def test_bundle_build_reports_duplicate_as_bundle_error():
    """The native bundle renderer surfaces it as BundleValidationError."""
    from vcfcf_core.packaging.assembly import _render_supermetrics_dict
    from vcfcf_packaging.loader import Bundle, BundleValidationError

    bundle = Bundle(
        name="dup", description="", sync_enabled=True,
        supermetrics=[_SM(NAME, UUID_1, Path("a.yaml")),
                      _SM(NAME, UUID_2, Path("b.yaml"))],
        views=[], dashboards=[], customgroups=[],
    )
    with pytest.raises(BundleValidationError) as exc:
        _render_supermetrics_dict(bundle)
    assert "a.yaml" in str(exc.value) and "b.yaml" in str(exc.value)

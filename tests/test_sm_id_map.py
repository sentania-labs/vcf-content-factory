"""``vcfcf_supermetrics.loader.sm_id_map``: the factory side of the view
renderer's super metric lookup (M2 row 2).

Before row 2 the renderer built this map itself, scanning
``content/supermetrics`` then ``supermetrics`` relative to the working
directory inside a bare ``except``. The behaviour moved verbatim; these
tests pin it so the move stays a move:

- unscoped: candidate order, first directory wins, all-or-nothing swallow;
- scoped: exactly the listed files, a load failure is a ``ValueError``
  naming the bundle and the real raiser.
"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from vcfcf_supermetrics.loader import sm_id_map

_A = str(uuid.uuid4())
_B = str(uuid.uuid4())


def _sm_yaml(name: str, sm_id: str = "") -> str:
    head = f"id: {sm_id}\n" if sm_id else ""
    return (
        f"{head}name: \"{name}\"\n"
        "formula: \"avg(${this, metric=cpu|usage_average})\"\n"
        "resource_kinds:\n  - {adapter_kind_key: VMWARE, resource_kind_key: HostSystem}\n"
    )


def _write(dir_: Path, fname: str, text: str) -> Path:
    dir_.mkdir(parents=True, exist_ok=True)
    p = dir_ / fname
    p.write_text(text, encoding="utf-8")
    return p


class TestUnscoped:
    def test_content_supermetrics_wins_over_bare_supermetrics(self, tmp_path, monkeypatch):
        _write(tmp_path / "content" / "supermetrics", "a.yaml",
               _sm_yaml("[VCF Content Factory] Map Probe A", _A))
        _write(tmp_path / "supermetrics", "b.yaml",
               _sm_yaml("[VCF Content Factory] Map Probe B", _B))
        monkeypatch.chdir(tmp_path)
        assert sm_id_map() == {"[VCF Content Factory] Map Probe A": _A}

    def test_bare_supermetrics_is_the_fallback(self, tmp_path, monkeypatch):
        _write(tmp_path / "supermetrics", "b.yaml",
               _sm_yaml("[VCF Content Factory] Map Probe B", _B))
        monkeypatch.chdir(tmp_path)
        assert sm_id_map() == {"[VCF Content Factory] Map Probe B": _B}

    def test_no_candidate_directory_is_an_empty_map(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert sm_id_map() == {}
        assert sm_id_map(None) == {}

    def test_one_bad_file_empties_the_whole_map(self, tmp_path, monkeypatch):
        """All-or-nothing, as the old renderer scan was: ``load_dir`` raises
        before returning its list, so the good sibling never lands either."""
        _write(tmp_path / "content" / "supermetrics", "a.yaml",
               _sm_yaml("[VCF Content Factory] Map Probe A", _A))
        # No framework prefix: load_dir's default enforce_framework_prefix=True rejects it.
        _write(tmp_path / "content" / "supermetrics", "bad.yaml",
               _sm_yaml("Unprefixed Probe", _B))
        monkeypatch.chdir(tmp_path)
        assert sm_id_map() == {}


class TestScoped:
    def test_exactly_the_listed_files(self, tmp_path, monkeypatch):
        # A cwd tree that the scoped mode must ignore.
        _write(tmp_path / "content" / "supermetrics", "a.yaml",
               _sm_yaml("[VCF Content Factory] Map Probe A", _A))
        scoped = _write(tmp_path / "elsewhere", "b.yaml", _sm_yaml("Third Party Probe B", _B))
        monkeypatch.chdir(tmp_path)
        assert sm_id_map([scoped]) == {"Third Party Probe B": _B}
        assert sm_id_map([]) == {}

    def test_scoped_ignores_the_framework_prefix(self, tmp_path):
        scoped = _write(tmp_path, "b.yaml", _sm_yaml("Third Party Probe B", _B))
        assert sm_id_map([scoped]) == {"Third Party Probe B": _B}

    def test_load_failure_is_a_value_error_naming_the_bundle(self, tmp_path):
        missing = tmp_path / "nope.yaml"
        with pytest.raises(ValueError) as exc:
            sm_id_map([missing], bundle_context='"idps-planner" (factory_native=False)')
        text = str(exc.value)
        assert text.startswith("sm_id_map: failed to load scoped SM for bundle ")
        assert '"idps-planner" (factory_native=False)' in text
        assert "render_view_def_fragments" not in text

"""Tests for vcfops_packaging.defects (RULE-012 defect registry + gate).

Design principle (2026-07-06 rework)
-------------------------------------
Every *behavior* assertion (parsing, gating logic, exit codes, open-blocks,
closed-passes, gate-all semantics) runs against a small **fixture** registry
built inline or in a ``tmp_path`` file for that test case.  Fixture registries
never change, so these tests are stable regardless of what happens to any
real defect in ``context/defects.md`` — a defect graduating from open to
closed (the registry doing its job) must never turn a green CI red.

Against the **live** ``context/defects.md`` we only assert *structural*
invariants that must hold no matter which defects are currently open or
closed: the file parses without error; every entry carries the required
fields; every ``Status: closed`` entry carries a non-empty
``Closing-evidence``; severities/statuses are drawn from the allowed
vocabulary; and ids are unique with no gaps in the numbering. We do NOT
assert which specific DEF ids exist or what their open/closed state is —
see ``lessons/`` for why pinning tests to mutable registry data is a test
design defect.

Coverage map (old behavior -> new fixture test)
------------------------------------------------
  Parser happy path (multi-entry, all fields captured)
      -> TestParserFixture.test_parses_multi_entry_registry
  Malformed entries (bad severity / waived / closed-without-evidence /
  duplicate id / missing field / unknown status)
      -> TestMalformedEntries (already fixture-based; unchanged)
  gate_pak: blocked / clean / unaffected pak
      -> TestGatePak (rewritten onto a fixture registry)
  gate_item: blocked / tracked-not-blocked / unaffected item
      -> TestGateItem (already fixture-based; unchanged)
  gate_all: open blockers returned, closed excluded, empty registry
      -> TestGateAll (rewritten onto a fixture registry + existing
         test_gate_all_empty_registry)
  CLI defect-gate (--pak / --all / <type> <name> / malformed / missing)
      -> TestCLIDefectGate (rewritten: REGISTRY_PATH monkeypatched to a
         fixture registry for every case)
  cmd_release refusal for an open blocking defect
      -> TestReleaseRefusal (rewritten: REGISTRY_PATH monkeypatched to a
         fixture registry instead of relying on a live DEF id)
  _gate_publish: raises for open blocker / passes for closed-or-tracked /
  malformed raises / vacuous pass when registry absent / fires on a
  fixture repo's own registry
      -> TestGatePublish (already mostly fixture-based; the remaining
         REPO_ROOT-coupled cases are rewritten onto tmp_path fixtures)
  Standalone entrypoint (--pak / --all / missing registry / bare-copy
  curl-and-run proof)
      -> TestStandaloneEntrypoint (rewritten: fixture registries written
         to tmp_path rather than copying/reading the live registry
         content; the bare-copy proof still copies the real defects.py
         script — only the *registry* is now synthetic)
  Real-registry structural contract
      -> TestRealRegistryStructural (new: format/shape invariants only)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Repo root and real registry path
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent
REAL_REGISTRY = REPO_ROOT / "context" / "defects.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_registry(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "defects.md"
    p.write_text(content, encoding="utf-8")
    return p


# A small, self-contained fixture registry used across the fixture-based
# gate/CLI/publish tests below.  Two open blocking defects (against two
# different paks), one closed defect (with evidence), and one tracked
# (non-blocking) defect.
_FIXTURE_REGISTRY_TEXT = """\
# Defect registry

## Defects

### DEF-001

- **Title:** Fixture pak alpha has an open blocking defect
- **Severity:** blocking
- **Status:** open
- **Affects:** fixture-pak-alpha
- **First-seen:** build 1 (2026-01-01)
- **Source:** context/reviews/fixture.md
- **Summary:** Open blocking defect used to prove the gate fires.

### DEF-002

- **Title:** Fixture pak beta has an open blocking defect
- **Severity:** blocking
- **Status:** open
- **Affects:** fixture-pak-beta
- **First-seen:** build 2 (2026-01-02)
- **Source:** context/reviews/fixture.md
- **Summary:** Second open blocking defect, different pak.

### DEF-003

- **Title:** Fixture pak gamma had a defect, now closed
- **Severity:** blocking
- **Status:** closed
- **Affects:** fixture-pak-gamma
- **First-seen:** build 3 (2026-01-03)
- **Source:** context/reviews/fixture.md
- **Summary:** Closed defect; must never appear as a blocker.
- **Closing-evidence:** Fixture proof — closed for this test suite.

### DEF-004

- **Title:** Fixture pak delta has a tracked (non-blocking) issue
- **Severity:** tracked
- **Status:** open
- **Affects:** fixture-pak-delta
- **First-seen:** build 4 (2026-01-04)
- **Source:** context/reviews/fixture.md
- **Summary:** Tracked severity must never gate a release.
"""


def _fixture_registry(tmp_path: Path) -> Path:
    return _write_registry(tmp_path, _FIXTURE_REGISTRY_TEXT)


# ---------------------------------------------------------------------------
# Parser happy path (fixture)
# ---------------------------------------------------------------------------

class TestParserFixture:
    """Happy-path parsing against a synthetic multi-entry registry."""

    def test_parses_multi_entry_registry(self, tmp_path):
        from vcfops_packaging.defects import load_registry
        reg = _fixture_registry(tmp_path)
        entries = load_registry(reg)
        ids = [e.id for e in entries]
        assert ids == ["DEF-001", "DEF-002", "DEF-003", "DEF-004"]

        by_id = {e.id: e for e in entries}
        assert by_id["DEF-001"].severity == "blocking"
        assert by_id["DEF-001"].status == "open"
        assert by_id["DEF-001"].affects == "fixture-pak-alpha"
        assert by_id["DEF-001"].title

        assert by_id["DEF-002"].affects == "fixture-pak-beta"

        assert by_id["DEF-003"].status == "closed"
        assert by_id["DEF-003"].closing_evidence.strip()

        assert by_id["DEF-004"].severity == "tracked"


# ---------------------------------------------------------------------------
# Real registry: structural invariants only (no assertions about which
# specific defects exist or their open/closed state — see module docstring).
# ---------------------------------------------------------------------------

class TestRealRegistryStructural:
    """Format/shape contract that context/defects.md must satisfy regardless
    of which defects are currently filed or their status."""

    _ALLOWED_SEVERITIES = {"blocking", "tracked"}
    _ALLOWED_STATUSES = {"open", "closed"}

    def test_registry_exists(self):
        assert REAL_REGISTRY.exists(), (
            f"context/defects.md not found at {REAL_REGISTRY}"
        )

    def test_parses_without_error(self):
        from vcfops_packaging.defects import load_registry
        entries = load_registry(REAL_REGISTRY)
        assert isinstance(entries, list)

    def test_every_entry_has_required_fields(self):
        from vcfops_packaging.defects import load_registry
        entries = load_registry(REAL_REGISTRY)
        assert entries, "registry must have at least one entry"
        for e in entries:
            assert e.id, "entry missing id"
            assert e.title.strip(), f"{e.id}: empty title"
            assert e.affects.strip(), f"{e.id}: empty affects"
            assert e.first_seen.strip(), f"{e.id}: empty first-seen"
            assert e.source.strip(), f"{e.id}: empty source"
            assert e.summary.strip(), f"{e.id}: empty summary"

    def test_every_closed_entry_has_closing_evidence(self):
        """The registry's own format contract (see header table in
        context/defects.md): Status: closed requires Closing-evidence.
        The loader also enforces this at parse time, so this test is a
        second, explicit assertion of the same invariant on live data.
        """
        from vcfops_packaging.defects import load_registry
        entries = load_registry(REAL_REGISTRY)
        for e in entries:
            if e.status == "closed":
                assert e.closing_evidence.strip(), (
                    f"{e.id} is closed but has no Closing-evidence"
                )

    def test_severities_and_statuses_are_from_allowed_vocabulary(self):
        from vcfops_packaging.defects import load_registry
        entries = load_registry(REAL_REGISTRY)
        for e in entries:
            assert e.severity in self._ALLOWED_SEVERITIES, (
                f"{e.id}: unexpected severity {e.severity!r}"
            )
            assert e.status in self._ALLOWED_STATUSES, (
                f"{e.id}: unexpected status {e.status!r}"
            )

    def test_ids_unique_and_sequential(self):
        """Ids are unique (guaranteed by the loader) and numbered
        contiguously from DEF-001 with no gaps — the registry's own
        sequential-numbering discipline, not a statement about which
        defects exist."""
        from vcfops_packaging.defects import load_registry
        entries = load_registry(REAL_REGISTRY)
        ids = [e.id for e in entries]
        assert len(ids) == len(set(ids)), f"duplicate ids found: {ids}"

        numbers = sorted(int(i.split("-")[1]) for i in ids)
        assert numbers == list(range(1, len(numbers) + 1)), (
            f"defect ids must be sequential starting at DEF-001 with no "
            f"gaps; got numbers: {numbers}"
        )


# ---------------------------------------------------------------------------
# Malformed entry rejections (fixture-based; unchanged)
# ---------------------------------------------------------------------------

class TestMalformedEntries:
    """Each of these fixtures should raise DefectRegistryError."""

    def test_bad_severity(self, tmp_path):
        from vcfops_packaging.defects import load_registry, DefectRegistryError
        reg = _write_registry(tmp_path, """\
# Defect registry

## Defects

### DEF-001

- **Title:** Some defect
- **Severity:** critical
- **Status:** open
- **Affects:** synology
- **First-seen:** build 1 (2026-01-01)
- **Source:** context/reviews/test.md
- **Summary:** Test defect with bad severity.
""")
        with pytest.raises(DefectRegistryError, match="invalid Severity"):
            load_registry(reg)

    def test_waived_status_explicitly_rejected(self, tmp_path):
        from vcfops_packaging.defects import load_registry, DefectRegistryError
        reg = _write_registry(tmp_path, """\
# Defect registry

## Defects

### DEF-001

- **Title:** Some defect
- **Severity:** blocking
- **Status:** waived
- **Affects:** synology
- **First-seen:** build 1 (2026-01-01)
- **Source:** context/reviews/test.md
- **Summary:** Test defect with waived status.
""")
        with pytest.raises(DefectRegistryError, match="waived"):
            load_registry(reg)

    def test_closed_without_evidence(self, tmp_path):
        from vcfops_packaging.defects import load_registry, DefectRegistryError
        reg = _write_registry(tmp_path, """\
# Defect registry

## Defects

### DEF-001

- **Title:** Closed without evidence
- **Severity:** blocking
- **Status:** closed
- **Affects:** synology
- **First-seen:** build 1 (2026-01-01)
- **Source:** context/reviews/test.md
- **Summary:** This entry is closed but has no Closing-evidence.
""")
        with pytest.raises(DefectRegistryError, match="Closing-evidence"):
            load_registry(reg)

    def test_duplicate_ids(self, tmp_path):
        from vcfops_packaging.defects import load_registry, DefectRegistryError
        reg = _write_registry(tmp_path, """\
# Defect registry

## Defects

### DEF-001

- **Title:** First entry
- **Severity:** blocking
- **Status:** open
- **Affects:** synology
- **First-seen:** build 1 (2026-01-01)
- **Source:** context/reviews/test.md
- **Summary:** First.

### DEF-001

- **Title:** Duplicate id
- **Severity:** tracked
- **Status:** open
- **Affects:** unifi
- **First-seen:** build 2 (2026-01-02)
- **Source:** context/reviews/test2.md
- **Summary:** Duplicate id — must be rejected.
""")
        with pytest.raises(DefectRegistryError, match="duplicate"):
            load_registry(reg)

    def test_missing_required_field_title(self, tmp_path):
        from vcfops_packaging.defects import load_registry, DefectRegistryError
        reg = _write_registry(tmp_path, """\
# Defect registry

## Defects

### DEF-001

- **Severity:** blocking
- **Status:** open
- **Affects:** synology
- **First-seen:** build 1 (2026-01-01)
- **Source:** context/reviews/test.md
- **Summary:** Missing Title field.
""")
        with pytest.raises(DefectRegistryError, match="Title"):
            load_registry(reg)

    def test_unknown_status(self, tmp_path):
        from vcfops_packaging.defects import load_registry, DefectRegistryError
        reg = _write_registry(tmp_path, """\
# Defect registry

## Defects

### DEF-001

- **Title:** Bad status
- **Severity:** blocking
- **Status:** pending
- **Affects:** synology
- **First-seen:** build 1 (2026-01-01)
- **Source:** context/reviews/test.md
- **Summary:** Unknown status.
""")
        with pytest.raises(DefectRegistryError, match="invalid Status"):
            load_registry(reg)


# ---------------------------------------------------------------------------
# Gate helper exit codes (fixture registry)
# ---------------------------------------------------------------------------

class TestGatePak:
    """gate_pak() against a fixture registry."""

    def test_open_blocking_pak_is_blocked(self, tmp_path):
        from vcfops_packaging.defects import gate_pak
        reg = _fixture_registry(tmp_path)
        blockers = gate_pak("fixture-pak-alpha", reg)
        ids = [b.id for b in blockers]
        assert ids == ["DEF-001"]

    def test_second_open_blocking_pak_is_blocked(self, tmp_path):
        from vcfops_packaging.defects import gate_pak
        reg = _fixture_registry(tmp_path)
        blockers = gate_pak("fixture-pak-beta", reg)
        ids = [b.id for b in blockers]
        assert ids == ["DEF-002"]

    def test_closed_defect_does_not_gate_its_pak(self, tmp_path):
        from vcfops_packaging.defects import gate_pak
        reg = _fixture_registry(tmp_path)
        blockers = gate_pak("fixture-pak-gamma", reg)
        assert blockers == [], (
            f"closed DEF-003 must not block fixture-pak-gamma; got: "
            f"{[b.id for b in blockers]}"
        )

    def test_tracked_defect_does_not_gate_its_pak(self, tmp_path):
        from vcfops_packaging.defects import gate_pak
        reg = _fixture_registry(tmp_path)
        blockers = gate_pak("fixture-pak-delta", reg)
        assert blockers == [], (
            f"tracked severity must not block; got: {[b.id for b in blockers]}"
        )

    def test_unregistered_pak_is_clean(self, tmp_path):
        from vcfops_packaging.defects import gate_pak
        reg = _fixture_registry(tmp_path)
        blockers = gate_pak("nonexistent-pak", reg)
        assert blockers == [], (
            f"Unknown pak must return empty list; got: {[b.id for b in blockers]}"
        )


class TestGateItem:
    """gate_item() with a fixture registry."""

    _REGISTRY_TEXT = """\
# Defect registry

## Defects

### DEF-001

- **Title:** Dashboard has rendering bug
- **Severity:** blocking
- **Status:** open
- **Affects:** dashboard/my_dashboard
- **First-seen:** build 1 (2026-01-01)
- **Source:** context/reviews/test.md
- **Summary:** Blocking dashboard defect.

### DEF-002

- **Title:** Tracked view issue
- **Severity:** tracked
- **Status:** open
- **Affects:** view/my_view
- **First-seen:** build 2 (2026-01-02)
- **Source:** context/reviews/test2.md
- **Summary:** Non-blocking tracked issue — must not gate.
"""

    def test_blocked_item(self, tmp_path):
        from vcfops_packaging.defects import gate_item
        reg = _write_registry(tmp_path, self._REGISTRY_TEXT)
        blockers = gate_item("dashboard", "my_dashboard", reg)
        assert len(blockers) == 1
        assert blockers[0].id == "DEF-001"

    def test_tracked_item_not_blocked(self, tmp_path):
        from vcfops_packaging.defects import gate_item
        reg = _write_registry(tmp_path, self._REGISTRY_TEXT)
        blockers = gate_item("view", "my_view", reg)
        assert blockers == [], (
            "tracked severity must not block; got: "
            + str([b.id for b in blockers])
        )

    def test_unaffected_item_clean(self, tmp_path):
        from vcfops_packaging.defects import gate_item
        reg = _write_registry(tmp_path, self._REGISTRY_TEXT)
        blockers = gate_item("dashboard", "other_dashboard", reg)
        assert blockers == []


class TestGateAll:
    """gate_all() returns every open blocking defect (fixture registry)."""

    def test_gate_all_returns_open_blockers_only(self, tmp_path):
        from vcfops_packaging.defects import gate_all
        reg = _fixture_registry(tmp_path)
        blockers = gate_all(reg)
        ids = sorted(b.id for b in blockers)
        assert ids == ["DEF-001", "DEF-002"], (
            f"expected exactly the two open blocking defects; got: {ids}"
        )

    def test_gate_all_empty_registry(self, tmp_path):
        from vcfops_packaging.defects import gate_all
        reg = _write_registry(tmp_path, "# No entries\n")
        assert gate_all(reg) == []


# ---------------------------------------------------------------------------
# CLI exit codes via build_parser + cmd_defect_gate (fixture registry via
# REGISTRY_PATH monkeypatch)
# ---------------------------------------------------------------------------

class TestCLIDefectGate:
    """Integration tests for the defect-gate subcommand via the CLI layer.

    REGISTRY_PATH is monkeypatched to a fixture registry for every case so
    these tests are independent of the live corpus's current defect states.
    """

    def _run(self, argv: list[str]) -> int:
        from vcfops_packaging.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(argv)
        return args.func(args)

    def test_pak_clean_exits_0(self, tmp_path, monkeypatch, capsys):
        from vcfops_packaging import defects as _defects_mod
        reg = _fixture_registry(tmp_path)
        monkeypatch.setattr(_defects_mod, "REGISTRY_PATH", reg)
        rc = self._run(["defect-gate", "--pak", "fixture-pak-gamma"])
        assert rc == 0, f"Expected exit 0 for a clean pak; got {rc}"
        out = capsys.readouterr().out
        assert "fixture-pak-gamma" in out

    def test_pak_blocked_exits_2(self, tmp_path, monkeypatch, capsys):
        from vcfops_packaging import defects as _defects_mod
        reg = _fixture_registry(tmp_path)
        monkeypatch.setattr(_defects_mod, "REGISTRY_PATH", reg)
        rc = self._run(["defect-gate", "--pak", "fixture-pak-alpha"])
        assert rc == 2, f"Expected exit 2 for a blocked pak; got {rc}"
        out = capsys.readouterr().out
        assert "DEF-001" in out

    def test_pak_tracked_only_exits_0(self, tmp_path, monkeypatch, capsys):
        from vcfops_packaging import defects as _defects_mod
        reg = _fixture_registry(tmp_path)
        monkeypatch.setattr(_defects_mod, "REGISTRY_PATH", reg)
        rc = self._run(["defect-gate", "--pak", "fixture-pak-delta"])
        assert rc == 0, f"tracked severity must not gate; got {rc}"

    def test_all_exits_2_and_lists_open_blockers_only(self, tmp_path, monkeypatch, capsys):
        from vcfops_packaging import defects as _defects_mod
        reg = _fixture_registry(tmp_path)
        monkeypatch.setattr(_defects_mod, "REGISTRY_PATH", reg)
        rc = self._run(["defect-gate", "--all"])
        assert rc == 2, f"Expected exit 2 (two open blockers); got {rc}"
        out = capsys.readouterr().out
        assert "DEF-001" in out
        assert "DEF-002" in out
        assert "DEF-003" not in out, "closed defect must not be listed"

    def test_malformed_registry_exits_1(self, tmp_path, monkeypatch, capsys):
        """A malformed registry must exit 1, not silently pass or exit 2."""
        from vcfops_packaging import defects as _defects_mod
        bad_reg = _write_registry(tmp_path, """\
# Defect registry

## Defects

### DEF-001

- **Title:** No evidence
- **Severity:** blocking
- **Status:** closed
- **Affects:** synology
- **First-seen:** build 1 (2026-01-01)
- **Source:** context/reviews/test.md
- **Summary:** Closed without evidence — malformed.
""")
        monkeypatch.setattr(_defects_mod, "REGISTRY_PATH", bad_reg)
        rc = self._run(["defect-gate", "--pak", "synology"])
        assert rc == 1, f"Expected exit 1 for malformed registry; got {rc}"
        captured = capsys.readouterr()
        assert "malformed" in (captured.out + captured.err).lower()

    def test_missing_registry_exits_1(self, tmp_path, monkeypatch, capsys):
        """A missing registry must cause the standalone CLI to exit 1 (hard error)."""
        from vcfops_packaging import defects as _defects_mod
        missing = tmp_path / "does_not_exist" / "defects.md"
        monkeypatch.setattr(_defects_mod, "REGISTRY_PATH", missing)
        rc = self._run(["defect-gate", "--pak", "synology"])
        assert rc == 1, (
            f"Missing registry must exit 1 for standalone CLI; got {rc}"
        )
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert any(kw in combined.lower() for kw in ("defect", "registry", "not found")), (
            f"Error output should mention the missing registry; got:\n{combined}"
        )

    def test_content_item_gate(self, tmp_path, monkeypatch, capsys):
        """<type> <name> mode gates by the Affects: token."""
        from vcfops_packaging import defects as _defects_mod
        reg = _write_registry(tmp_path, """\
# Defect registry

## Defects

### DEF-001

- **Title:** Dashboard bug
- **Severity:** blocking
- **Status:** open
- **Affects:** dashboards/demand_driven_capacity_v2
- **First-seen:** build 1 (2026-01-01)
- **Source:** context/reviews/test.md
- **Summary:** Blocking dashboard defect.
""")
        monkeypatch.setattr(_defects_mod, "REGISTRY_PATH", reg)
        rc = self._run(["defect-gate", "dashboards", "demand_driven_capacity_v2"])
        assert rc == 2
        captured = capsys.readouterr()
        assert "DEF-001" in captured.out

    def test_content_item_unaffected_exits_0(self, tmp_path, monkeypatch, capsys):
        from vcfops_packaging import defects as _defects_mod
        reg = _write_registry(tmp_path, """\
# Defect registry

## Defects

### DEF-001

- **Title:** Dashboard bug
- **Severity:** blocking
- **Status:** open
- **Affects:** dashboards/demand_driven_capacity_v2
- **First-seen:** build 1 (2026-01-01)
- **Source:** context/reviews/test.md
- **Summary:** Only affects demand_driven_capacity_v2.
""")
        monkeypatch.setattr(_defects_mod, "REGISTRY_PATH", reg)
        rc = self._run(["defect-gate", "dashboards", "some_other_dashboard"])
        assert rc == 0


# ---------------------------------------------------------------------------
# Release refusal (cmd_release) — fixture registry via REGISTRY_PATH
# ---------------------------------------------------------------------------

class TestReleaseRefusal:
    """cmd_release must refuse and name defect ids when an open blocking
    defect exists.  REGISTRY_PATH is monkeypatched to a fixture registry so
    this is independent of any live defect's current state.
    """

    def _run_release(self, tmp_path, pak_dir_name: str):
        adapter_dir = tmp_path / "content" / "sdk-adapters" / pak_dir_name
        adapter_dir.mkdir(parents=True)
        adapter_yaml = adapter_dir / "adapter.yaml"
        adapter_yaml.write_text(
            f"name: VCF Content Factory {pak_dir_name.title()} Adapter\ndescription: Test.\n",
            encoding="utf-8",
        )

        import argparse
        args = argparse.Namespace(
            content_type="sdk-adapter",
            name=str(adapter_yaml),
            version=None,
            notes=None,
            deprecates=None,
            slug=None,
            no_commit=True,
        )

        from vcfops_packaging.cli import cmd_release
        (tmp_path / "releases").mkdir()
        import os
        orig_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            rc = cmd_release(args)
        finally:
            os.chdir(orig_cwd)
        return rc

    def test_sdk_adapter_release_refused_for_open_blocker(self, tmp_path, monkeypatch, capsys):
        from vcfops_packaging import defects as _defects_mod
        reg_dir = tmp_path / "registry"
        reg_dir.mkdir()
        reg = _fixture_registry(reg_dir)
        monkeypatch.setattr(_defects_mod, "REGISTRY_PATH", reg)

        rc = self._run_release(tmp_path, "fixture-pak-alpha")

        assert rc == 2, f"Expected exit 2 (blocked by DEF-001); got {rc}"
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "DEF-001" in combined, (
            f"Refusal must name DEF-001; got output:\n{combined}"
        )

    def test_sdk_adapter_release_passes_for_clean_pak(self, tmp_path, monkeypatch, capsys):
        from vcfops_packaging import defects as _defects_mod
        reg_dir = tmp_path / "registry"
        reg_dir.mkdir()
        reg = _fixture_registry(reg_dir)
        monkeypatch.setattr(_defects_mod, "REGISTRY_PATH", reg)

        rc = self._run_release(tmp_path, "fixture-pak-gamma")

        # DEF-003 (fixture-pak-gamma) is closed, so the defect gate itself
        # must not refuse (rc != 2).  cmd_release may still fail later for
        # unrelated reasons (e.g. no git repo present) — we only assert the
        # gate does not fire.
        assert rc != 2, (
            f"clean pak must not be refused by the defect gate; got rc={rc}"
        )


# ---------------------------------------------------------------------------
# _gate_publish raises on open blockers (fixture registries)
# ---------------------------------------------------------------------------

class TestGatePublish:
    """_gate_publish raises PublishError naming defect ids."""

    def _make_mock_release(self, source_path: Path, release_name: str = "test-release"):
        """Build a minimal mock ReleaseDef + artifact."""
        from vcfops_packaging.releases import ReleaseDef, ReleaseArtifact
        art = ReleaseArtifact(
            source=str(source_path),
            source_path=source_path,
            headline=True,
        )
        return ReleaseDef(
            name=release_name,
            version="1.0",
            description="test",
            release_notes="",
            artifacts=[art],
            deprecates=[],
            manifest_path=source_path.parent / "release.yaml",
        )

    def test_passes_when_pak_defect_is_closed(self, tmp_path):
        """A pak whose only registered defect is closed passes _gate_publish."""
        from vcfops_packaging.publish import _gate_publish

        reg_dir = tmp_path / "context"
        reg_dir.mkdir()
        (reg_dir / "defects.md").write_text("""\
# Defect registry

## Defects

### DEF-001

- **Title:** Fixture pak: closed defect
- **Severity:** blocking
- **Status:** closed
- **Affects:** fixturepak
- **First-seen:** build 1 (2026-01-01)
- **Source:** context/reviews/test.md
- **Summary:** Closed for test.
- **Closing-evidence:** Test proof — closed for this fixture.
""", encoding="utf-8")

        adapter_dir = tmp_path / "content" / "sdk-adapters" / "fixturepak"
        adapter_dir.mkdir(parents=True)
        adapter_yaml = adapter_dir / "adapter.yaml"
        adapter_yaml.write_text("name: test\n", encoding="utf-8")

        release = self._make_mock_release(adapter_yaml, "fixturepak-managementpack")
        # Must not raise — the only registered defect is closed.
        _gate_publish([release], tmp_path)

    def test_raises_for_pak_with_open_blocker(self, tmp_path):
        """A pak release triggers _gate_publish to raise when it has an open
        blocking defect registered against it."""
        from vcfops_packaging.publish import _gate_publish, PublishError

        reg_dir = tmp_path / "context"
        reg_dir.mkdir()
        (reg_dir / "defects.md").write_text("""\
# Defect registry

## Defects

### DEF-002

- **Title:** Fixture pak: open blocking defect
- **Severity:** blocking
- **Status:** open
- **Affects:** fixturepak
- **First-seen:** build 1 (2026-01-01)
- **Source:** context/reviews/test.md
- **Summary:** Open blocker used to prove the gate raises.
""", encoding="utf-8")

        adapter_dir = tmp_path / "content" / "sdk-adapters" / "fixturepak"
        adapter_dir.mkdir(parents=True)
        adapter_yaml = adapter_dir / "adapter.yaml"
        adapter_yaml.write_text("name: test\n", encoding="utf-8")

        release = self._make_mock_release(adapter_yaml, "fixturepak-managementpack")

        with pytest.raises(PublishError) as exc_info:
            _gate_publish([release], tmp_path)

        msg = str(exc_info.value)
        assert "DEF-002" in msg

    def test_passes_for_pak_with_no_registered_defects(self, tmp_path):
        """A pak with no entries at all in the registry passes cleanly."""
        from vcfops_packaging.publish import _gate_publish

        reg_dir = tmp_path / "context"
        reg_dir.mkdir()
        (reg_dir / "defects.md").write_text("""\
# Defect registry

## Defects

### DEF-001

- **Title:** Unrelated pak's defect
- **Severity:** blocking
- **Status:** open
- **Affects:** some-other-pak
- **First-seen:** build 1 (2026-01-01)
- **Source:** context/reviews/test.md
- **Summary:** Does not affect the pak under test.
""", encoding="utf-8")

        adapter_dir = tmp_path / "content" / "sdk-adapters" / "unaffected-pak"
        adapter_dir.mkdir(parents=True)
        adapter_yaml = adapter_dir / "adapter.yaml"
        adapter_yaml.write_text("name: test\n", encoding="utf-8")

        release = self._make_mock_release(adapter_yaml, "unaffected-pak-managementpack")
        # Must not raise.
        _gate_publish([release], tmp_path)

    def test_passes_when_defects_all_closed_or_tracked(self, tmp_path):
        """A registry with only closed/tracked defects lets _gate_publish pass."""
        from vcfops_packaging.publish import _gate_publish

        reg_dir = tmp_path / "context"
        reg_dir.mkdir()
        reg = reg_dir / "defects.md"
        reg.write_text("""\
# Defect registry

## Defects

### DEF-001

- **Title:** Synology: closed defect
- **Severity:** blocking
- **Status:** closed
- **Affects:** synology
- **First-seen:** build 1 (2026-01-01)
- **Source:** context/reviews/test.md
- **Summary:** Closed for test.
- **Closing-evidence:** Test proof — closed for this fixture.
""", encoding="utf-8")

        adapter_dir = tmp_path / "content" / "sdk-adapters" / "synology"
        adapter_dir.mkdir(parents=True)
        adapter_yaml = adapter_dir / "adapter.yaml"
        adapter_yaml.write_text("name: test\n", encoding="utf-8")

        release = self._make_mock_release(adapter_yaml, "synology-managementpack")
        # Must not raise because the defect is closed.
        _gate_publish([release], tmp_path)

    def test_malformed_registry_raises_publish_error(self, tmp_path):
        """A malformed registry raises PublishError (never silently passes)."""
        from vcfops_packaging.publish import _gate_publish, PublishError

        reg_dir = tmp_path / "context"
        reg_dir.mkdir()
        reg = reg_dir / "defects.md"
        reg.write_text("""\
# Defect registry

## Defects

### DEF-001

- **Title:** No evidence
- **Severity:** blocking
- **Status:** closed
- **Affects:** synology
- **First-seen:** build 1 (2026-01-01)
- **Source:** context/reviews/test.md
- **Summary:** Closed without evidence — malformed.
""", encoding="utf-8")

        adapter_dir = tmp_path / "content" / "sdk-adapters" / "synology"
        adapter_dir.mkdir(parents=True)
        adapter_yaml = adapter_dir / "adapter.yaml"
        adapter_yaml.write_text("name: test\n", encoding="utf-8")

        release = self._make_mock_release(adapter_yaml, "synology-managementpack")
        with pytest.raises(PublishError, match="malformed"):
            _gate_publish([release], tmp_path)

    def test_vacuous_pass_when_registry_absent(self, tmp_path, capsys):
        """When factory_repo has no context/defects.md the gate vacuously
        passes with a clearly visible WARNING — never raises, never falls
        back to the package-relative registry."""
        from vcfops_packaging.publish import _gate_publish

        # tmp_path has no context/ directory — registry is absent.
        adapter_dir = tmp_path / "content" / "sdk-adapters" / "synology"
        adapter_dir.mkdir(parents=True)
        adapter_yaml = adapter_dir / "adapter.yaml"
        adapter_yaml.write_text("name: test\n", encoding="utf-8")

        release = self._make_mock_release(adapter_yaml, "synology-managementpack")
        # Must NOT raise, regardless of what the real registry says about
        # synology — the registry is absent in this fixture repo.
        _gate_publish([release], tmp_path)

        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "WARNING" in combined, (
            f"Vacuous pass must emit a WARNING; got:\n{combined}"
        )
        assert "RULE-012" in combined, (
            f"WARNING must mention RULE-012; got:\n{combined}"
        )

    def test_fires_on_fixture_repo_own_registry(self, tmp_path):
        """When the fixture repo HAS its own context/defects.md with an open
        blocking defect, _gate_publish must raise naming the defect — it must
        not use the package-relative registry."""
        from vcfops_packaging.publish import _gate_publish, PublishError

        # Write a fixture registry that blocks synology.
        reg_dir = tmp_path / "context"
        reg_dir.mkdir()
        (reg_dir / "defects.md").write_text("""\
# Defect registry

## Defects

### DEF-001

- **Title:** Fixture blocking defect for synology
- **Severity:** blocking
- **Status:** open
- **Affects:** synology
- **First-seen:** build 1 (2026-01-01)
- **Source:** context/reviews/fixture.md
- **Summary:** Blocking defect created by the test fixture.
""", encoding="utf-8")

        adapter_dir = tmp_path / "content" / "sdk-adapters" / "synology"
        adapter_dir.mkdir(parents=True)
        adapter_yaml = adapter_dir / "adapter.yaml"
        adapter_yaml.write_text("name: test\n", encoding="utf-8")

        release = self._make_mock_release(adapter_yaml, "synology-managementpack")
        with pytest.raises(PublishError) as exc_info:
            _gate_publish([release], tmp_path)

        msg = str(exc_info.value)
        assert "DEF-001" in msg, (
            f"Error must name the fixture defect DEF-001; got:\n{msg}"
        )
        assert "RULE-012" in msg


# ---------------------------------------------------------------------------
# Standalone entrypoint: python3 vcfops_packaging/defects.py
# ---------------------------------------------------------------------------

class TestStandaloneEntrypoint:
    """Verify the __main__ block in defects.py.

    Tests use subprocess so they exercise the real script execution path,
    not the import path.  This is the load-bearing proof for the curl-and-run
    contract.  The registry files used here are synthetic fixtures written to
    tmp_path — only the real defects.py *script* is copied/invoked, never the
    live context/defects.md content — so these tests are independent of the
    live corpus's current defect states.
    """

    _DEFECTS_SCRIPT = REPO_ROOT / "src" / "vcfops_packaging" / "defects.py"

    def _run_script(self, script_path: Path, argv: list, cwd: Path | None = None):
        """Run defects.py as a bare script; return (returncode, stdout, stderr)."""
        import subprocess
        result = subprocess.run(
            [sys.executable, str(script_path)] + argv,
            capture_output=True,
            text=True,
            cwd=str(cwd or REPO_ROOT),
        )
        return result.returncode, result.stdout, result.stderr

    # --- In-package invocations -------------------------------------------------

    def test_pak_clean_exits_0(self, tmp_path):
        """--pak <clean-pak> with a fixture registry → exit 0."""
        reg = _fixture_registry(tmp_path)
        rc, out, err = self._run_script(
            self._DEFECTS_SCRIPT,
            ["--pak", "fixture-pak-gamma", "--registry", str(reg)],
        )
        assert rc == 0, f"Expected exit 0; got {rc}\nstdout: {out}\nstderr: {err}"
        assert "fixture-pak-gamma" in out, f"Output must mention pak name; got:\n{out}"

    def test_pak_blocked_exits_2(self, tmp_path):
        """--pak <blocked-pak> with a fixture registry → exit 2, names the id."""
        reg = _fixture_registry(tmp_path)
        rc, out, err = self._run_script(
            self._DEFECTS_SCRIPT,
            ["--pak", "fixture-pak-alpha", "--registry", str(reg)],
        )
        assert rc == 2, f"Expected exit 2; got {rc}\nstdout: {out}\nstderr: {err}"
        assert "DEF-001" in out, f"Output must name DEF-001; got:\n{out}"

    def test_all_exits_2_lists_open_blockers_only(self, tmp_path):
        """--all → exit 2, lists only the open blocking defects."""
        reg = _fixture_registry(tmp_path)
        rc, out, err = self._run_script(
            self._DEFECTS_SCRIPT,
            ["--all", "--registry", str(reg)],
        )
        assert rc == 2, f"Expected exit 2 for --all; got {rc}\nstdout: {out}\nstderr: {err}"
        assert "DEF-001" in out, f"Output must list DEF-001; got:\n{out}"
        assert "DEF-002" in out, f"Output must list DEF-002; got:\n{out}"
        assert "DEF-003" not in out, "closed defect must not be listed"

    def test_missing_registry_exits_1(self, tmp_path):
        """--registry pointing at a nonexistent path → exit 1, clear error."""
        missing = tmp_path / "no_such_dir" / "defects.md"
        rc, out, err = self._run_script(
            self._DEFECTS_SCRIPT,
            ["--pak", "anything", "--registry", str(missing)],
        )
        assert rc == 1, f"Expected exit 1 for missing registry; got {rc}\nstdout: {out}\nstderr: {err}"
        combined = out + err
        assert any(kw in combined.lower() for kw in ("not found", "registry", "error")), (
            f"Error must mention the missing registry; got:\n{combined}"
        )

    # --- Bare-copy invocation: the load-bearing curl-and-run proof --------------

    def test_bare_copy_matches_in_package_run(self, tmp_path):
        """Copy defects.py (the real script) alongside a synthetic fixture
        registry into a clean temp dir; run it there.

        The pak-repo CI workflow does:
          curl .../defects.py -o defects.py
          curl .../context/defects.md -o defects.md
          python3 defects.py --pak <name> --registry defects.md

        This test reproduces that mechanism exactly (bare script, no
        vcfops_packaging on sys.path, no package structure present) using a
        synthetic registry so the assertions are independent of the live
        corpus's current defect states.
        """
        import shutil

        script_copy = tmp_path / "defects.py"
        registry_copy = tmp_path / "defects.md"
        shutil.copy2(str(self._DEFECTS_SCRIPT), str(script_copy))
        registry_copy.write_text(_FIXTURE_REGISTRY_TEXT, encoding="utf-8")

        # Run from the temp dir; cwd has NO factory repo structure.
        rc, out, err = self._run_script(
            script_copy,
            ["--pak", "fixture-pak-alpha", "--registry", str(registry_copy)],
            cwd=tmp_path,
        )

        assert rc == 2, (
            f"Bare-copy run must exit 2 (blocked by DEF-001); "
            f"got {rc}\nstdout: {out}\nstderr: {err}"
        )
        assert "DEF-001" in out, (
            f"Bare-copy run output must name DEF-001; got:\n{out}"
        )
        assert "RULE-012" in out, (
            f"Bare-copy run output must name RULE-012; got:\n{out}"
        )

    def test_bare_copy_clean_pak_exits_0(self, tmp_path):
        """Bare-copy run for a clean pak → exit 0."""
        import shutil

        script_copy = tmp_path / "defects.py"
        registry_copy = tmp_path / "defects.md"
        shutil.copy2(str(self._DEFECTS_SCRIPT), str(script_copy))
        registry_copy.write_text(_FIXTURE_REGISTRY_TEXT, encoding="utf-8")

        rc, out, err = self._run_script(
            script_copy,
            ["--pak", "fixture-pak-gamma", "--registry", str(registry_copy)],
            cwd=tmp_path,
        )
        assert rc == 0, (
            f"Bare-copy run must exit 0 for a clean pak; "
            f"got {rc}\nstdout: {out}\nstderr: {err}"
        )

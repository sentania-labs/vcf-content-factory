"""Tests for vcfops_packaging.defects (RULE-012 defect registry + gate).

Coverage:
  Parser:
    - Happy path against the real context/defects.md.  The real-corpus tests
      assert *which* known DEF ids are present and what their properties are —
      they do NOT hardcode the total entry count so that adding a new defect
      to the registry does not break CI.  The current known entries are
      DEF-001 (blocking/open/synology), DEF-002 (blocking/open/unifi),
      DEF-003 (blocking/closed/synology), DEF-004 (blocking/open/vcommunity-os).
    - Malformed entries: bad severity, waived status, closed-without-evidence,
      duplicate id, missing required fields.
  Gate helpers:
    - gate_pak: affected pak (DEF-001 blocks synology), unaffected pak,
      closed defect (DEF-003 does NOT gate synology by itself).
    - gate_item: affected item and unaffected item.
    - gate_all: exit 2 when any open blocking defect exists; known open
      blockers include DEF-001, DEF-002, DEF-004; DEF-003 is closed and
      must not appear.
  CLI (defect-gate subcommand):
    - --pak <name>: exit 2 when blocked (synology), exit 0 when clean (compliance, vcommunity).
    - --pak unifi: exit 2 (DEF-002).
    - --pak vcommunity-os: exit 2 (DEF-004).
    - --all: exit 2 when open blockers exist.
    - malformed registry: exit 1 with error.
  Release refusal:
    - cmd_release refuses for sdk-adapter with open blocking defect (naming ids).
  Publish gate:
    - _gate_publish raises PublishError naming defect ids.
    - _gate_publish passes when all defects are closed or tracked.
  Standalone entrypoint (defects.py __main__):
    - --pak synology --registry context/defects.md → exit 2, names DEF-001.
    - --pak compliance → exit 0.
    - --all → exit 2, lists DEF-001 + DEF-002.
    - missing registry path → exit 1.
    - bare-copy invocation (file copied outside the package, run with a clean
      cwd) → identical result to the in-package run (proves curl-and-run).
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

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


# ---------------------------------------------------------------------------
# Real registry smoke tests
# ---------------------------------------------------------------------------

class TestRealRegistry:
    """Parse the actual context/defects.md.

    Invariant: assert specific DEF ids and their properties, not the total
    count of registry entries.  That way adding a new defect filing does not
    break CI.  The currently known entries are DEF-001..DEF-004; new entries
    can be added without touching these tests.
    """

    def test_registry_exists(self):
        assert REAL_REGISTRY.exists(), (
            f"context/defects.md not found at {REAL_REGISTRY}"
        )

    def test_load_known_entries(self):
        """All four currently known DEF ids are present; registry has at least 4 entries."""
        from vcfops_packaging.defects import load_registry
        entries = load_registry(REAL_REGISTRY)
        ids = [e.id for e in entries]
        assert "DEF-001" in ids
        assert "DEF-002" in ids
        assert "DEF-003" in ids
        assert "DEF-004" in ids
        assert len(entries) >= 4, (
            f"Registry must have at least 4 entries; got {len(ids)}: {ids}"
        )

    def test_def001_fields(self):
        from vcfops_packaging.defects import load_registry
        entries = {e.id: e for e in load_registry(REAL_REGISTRY)}
        d1 = entries["DEF-001"]
        assert d1.severity == "blocking"
        assert d1.status == "open"
        assert d1.affects == "synology"
        assert d1.title  # non-empty

    def test_def002_fields(self):
        from vcfops_packaging.defects import load_registry
        entries = {e.id: e for e in load_registry(REAL_REGISTRY)}
        d2 = entries["DEF-002"]
        assert d2.severity == "blocking"
        assert d2.status == "open"
        assert d2.affects == "unifi"

    def test_def003_closed_with_evidence(self):
        from vcfops_packaging.defects import load_registry
        entries = {e.id: e for e in load_registry(REAL_REGISTRY)}
        d3 = entries["DEF-003"]
        assert d3.status == "closed"
        assert d3.closing_evidence.strip(), (
            "DEF-003 is closed and must have non-empty closing_evidence"
        )
        assert d3.affects == "synology"

    def test_def004_fields(self):
        from vcfops_packaging.defects import load_registry
        entries = {e.id: e for e in load_registry(REAL_REGISTRY)}
        d4 = entries["DEF-004"]
        assert d4.severity == "blocking"
        assert d4.status == "open"
        assert d4.affects == "vcommunity-os"
        assert d4.title  # non-empty


# ---------------------------------------------------------------------------
# Malformed entry rejections
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
# Gate helper exit codes
# ---------------------------------------------------------------------------

class TestGatePak:
    """gate_pak() against the real registry."""

    def test_synology_is_blocked(self):
        from vcfops_packaging.defects import gate_pak
        blockers = gate_pak("synology", REAL_REGISTRY)
        ids = [b.id for b in blockers]
        assert "DEF-001" in ids, (
            f"DEF-001 must block synology; blocking entries: {ids}"
        )

    def test_unifi_is_blocked(self):
        from vcfops_packaging.defects import gate_pak
        blockers = gate_pak("unifi", REAL_REGISTRY)
        ids = [b.id for b in blockers]
        assert "DEF-002" in ids, (
            f"DEF-002 must block unifi; blocking entries: {ids}"
        )

    def test_compliance_is_clean(self):
        from vcfops_packaging.defects import gate_pak
        blockers = gate_pak("compliance", REAL_REGISTRY)
        assert blockers == [], (
            f"compliance must be clean; blockers: {[b.id for b in blockers]}"
        )

    def test_vcommunity_is_clean(self):
        from vcfops_packaging.defects import gate_pak
        blockers = gate_pak("vcommunity", REAL_REGISTRY)
        assert blockers == [], (
            f"vcommunity must be clean; blockers: {[b.id for b in blockers]}"
        )

    def test_vcommunity_os_is_blocked(self):
        from vcfops_packaging.defects import gate_pak
        blockers = gate_pak("vcommunity-os", REAL_REGISTRY)
        ids = [b.id for b in blockers]
        assert "DEF-004" in ids, (
            f"DEF-004 must block vcommunity-os; blocking entries: {ids}"
        )

    def test_closed_def003_does_not_gate_synology(self):
        """DEF-003 is closed; it must not appear in the blocker list."""
        from vcfops_packaging.defects import gate_pak
        blockers = gate_pak("synology", REAL_REGISTRY)
        ids = [b.id for b in blockers]
        assert "DEF-003" not in ids, (
            f"Closed DEF-003 must not block synology; got: {ids}"
        )

    def test_unregistered_pak_is_clean(self):
        from vcfops_packaging.defects import gate_pak
        blockers = gate_pak("nonexistent-pak", REAL_REGISTRY)
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
    """gate_all() returns every open blocking defect.

    Invariant: assert which known DEF ids are / are not present, not the
    total count.  Adding a new open blocking defect to the registry must not
    break CI.  Currently known open blockers: DEF-001, DEF-002, DEF-004.
    DEF-003 is closed and must never appear.
    """

    def test_gate_all_real_registry_open_blockers(self):
        from vcfops_packaging.defects import gate_all
        blockers = gate_all(REAL_REGISTRY)
        ids = [b.id for b in blockers]
        # Known open blockers — all must be present.
        assert "DEF-001" in ids, f"DEF-001 must be an open blocker; got: {ids}"
        assert "DEF-002" in ids, f"DEF-002 must be an open blocker; got: {ids}"
        assert "DEF-004" in ids, f"DEF-004 must be an open blocker; got: {ids}"
        # Closed defect must never appear as a blocker.
        assert "DEF-003" not in ids, f"Closed DEF-003 must not appear in blockers; got: {ids}"
        # Registry-wide count is not asserted — new filings must not break CI.
        assert len(blockers) >= 3, (
            f"At least 3 open blockers expected (DEF-001/002/004); got: {ids}"
        )

    def test_gate_all_empty_registry(self, tmp_path):
        from vcfops_packaging.defects import gate_all
        reg = _write_registry(tmp_path, "# No entries\n")
        assert gate_all(reg) == []


# ---------------------------------------------------------------------------
# CLI exit codes via build_parser + cmd_defect_gate
# ---------------------------------------------------------------------------

class TestCLIDefectGate:
    """Integration tests for the defect-gate subcommand via the CLI layer."""

    def _run(self, argv: list[str]) -> int:
        from vcfops_packaging.cli import build_parser, cmd_defect_gate
        parser = build_parser()
        args = parser.parse_args(argv)
        return args.func(args)

    def test_pak_synology_exits_2(self, capsys):
        rc = self._run(["defect-gate", "--pak", "synology"])
        assert rc == 2, f"Expected exit 2 for synology (DEF-001 open); got {rc}"
        captured = capsys.readouterr()
        out = captured.out
        assert "DEF-001" in out

    def test_pak_unifi_exits_2(self, capsys):
        rc = self._run(["defect-gate", "--pak", "unifi"])
        assert rc == 2, f"Expected exit 2 for unifi (DEF-002 open); got {rc}"
        captured = capsys.readouterr()
        out = captured.out
        assert "DEF-002" in out

    def test_pak_compliance_exits_0(self, capsys):
        rc = self._run(["defect-gate", "--pak", "compliance"])
        assert rc == 0, f"Expected exit 0 for compliance (no open blockers); got {rc}"
        captured = capsys.readouterr()
        out = captured.out
        assert "compliance" in out

    def test_pak_vcommunity_exits_0(self, capsys):
        rc = self._run(["defect-gate", "--pak", "vcommunity"])
        assert rc == 0, f"Expected exit 0 for vcommunity (no open blockers); got {rc}"

    def test_pak_vcommunity_os_exits_2(self, capsys):
        rc = self._run(["defect-gate", "--pak", "vcommunity-os"])
        assert rc == 2, f"Expected exit 2 for vcommunity-os (DEF-004 open); got {rc}"
        captured = capsys.readouterr()
        assert "DEF-004" in captured.out

    def test_all_exits_2_when_open_blockers(self, capsys):
        rc = self._run(["defect-gate", "--all"])
        assert rc == 2, f"Expected exit 2 (DEF-001, DEF-002 open); got {rc}"
        captured = capsys.readouterr()
        out = captured.out
        assert "DEF-001" in out
        assert "DEF-002" in out

    def test_malformed_registry_exits_1(self, tmp_path, monkeypatch, capsys):
        """A malformed registry must exit 1, not silently pass or exit 2."""
        from vcfops_packaging import defects as _defects_mod
        # Write a bad registry that lacks Closing-evidence on a closed entry.
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
        # Monkeypatch the default registry path.
        monkeypatch.setattr(_defects_mod, "REGISTRY_PATH", bad_reg)
        rc = self._run(["defect-gate", "--pak", "synology"])
        assert rc == 1, f"Expected exit 1 for malformed registry; got {rc}"
        captured = capsys.readouterr()
        assert "malformed" in (captured.out + captured.err).lower()

    def test_missing_registry_exits_1(self, tmp_path, monkeypatch, capsys):
        """A missing registry must cause the standalone CLI to exit 1 (hard error).

        An explicit invocation with no registry means something is wrong —
        it must never silently pass (unlike the embedded publish gate which
        vacuously passes when factory_repo lacks a registry).
        """
        from vcfops_packaging import defects as _defects_mod
        missing = tmp_path / "does_not_exist" / "defects.md"
        monkeypatch.setattr(_defects_mod, "REGISTRY_PATH", missing)
        rc = self._run(["defect-gate", "--pak", "synology"])
        assert rc == 1, (
            f"Missing registry must exit 1 for standalone CLI; got {rc}"
        )
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        # The error must say something about the registry or the path.
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
# Release refusal (cmd_release)
# ---------------------------------------------------------------------------

class TestReleaseRefusal:
    """cmd_release must refuse and name defect ids when an open blocking defect exists."""

    def test_sdk_adapter_release_refused_for_synology(self, tmp_path, capsys):
        """Attempting to release a synology sdk-adapter is refused by DEF-001."""
        # Create a minimal fake adapter.yaml in a synology dir.
        adapter_dir = tmp_path / "content" / "sdk-adapters" / "synology"
        adapter_dir.mkdir(parents=True)
        adapter_yaml = adapter_dir / "adapter.yaml"
        adapter_yaml.write_text(
            "name: VCF Content Factory Synology Adapter\ndescription: Test.\n",
            encoding="utf-8",
        )

        # Build a minimal argparse Namespace that cmd_release expects.
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

        # Patch Path.cwd() so repo_root resolves to tmp_path, which means
        # the defect registry path would be tmp_path/context/defects.md.
        # We use the real registry instead by patching the defects module's
        # load_registry to read the real file regardless.
        # Simpler: patch gate_pak to use the real registry.
        from vcfops_packaging.cli import cmd_release
        # We need releases/ to exist so the command doesn't error before the gate.
        (tmp_path / "releases").mkdir()
        # Patch cwd to tmp_path so all Path.cwd() calls land in our fixture.
        import os
        orig_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            # Now run cmd_release.  The defects module will look for
            # context/defects.md relative to the package (not cwd), so the
            # real registry will be found.
            rc = cmd_release(args)
        finally:
            os.chdir(orig_cwd)

        # Exit 2 = refused by gate.
        assert rc == 2, f"Expected exit 2 (synology blocked by DEF-001); got {rc}"
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "DEF-001" in combined, (
            f"Refusal must name DEF-001; got output:\n{combined}"
        )


# ---------------------------------------------------------------------------
# _gate_publish raises on open blockers
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

    def test_raises_for_synology_sdk_adapter(self, tmp_path):
        """A synology sdk-adapter release triggers _gate_publish to raise."""
        from vcfops_packaging.publish import _gate_publish, PublishError

        # Build a fake adapter source path under content/sdk-adapters/synology/
        adapter_dir = tmp_path / "content" / "sdk-adapters" / "synology"
        adapter_dir.mkdir(parents=True)
        adapter_yaml = adapter_dir / "adapter.yaml"
        adapter_yaml.write_text("name: test\n", encoding="utf-8")

        release = self._make_mock_release(adapter_yaml, "synology-managementpack")

        # factory_repo: defects.py will look for context/defects.md relative
        # to the package, so we use REPO_ROOT as factory_repo.
        with pytest.raises(PublishError) as exc_info:
            _gate_publish([release], REPO_ROOT)

        msg = str(exc_info.value)
        assert "DEF-001" in msg, (
            f"PublishError must name DEF-001; got:\n{msg}"
        )
        assert "RULE-012" in msg

    def test_raises_for_unifi_sdk_adapter(self, tmp_path):
        """A unifi sdk-adapter release triggers _gate_publish to raise."""
        from vcfops_packaging.publish import _gate_publish, PublishError

        adapter_dir = tmp_path / "content" / "sdk-adapters" / "unifi"
        adapter_dir.mkdir(parents=True)
        adapter_yaml = adapter_dir / "adapter.yaml"
        adapter_yaml.write_text("name: test\n", encoding="utf-8")

        release = self._make_mock_release(adapter_yaml, "unifi-managementpack")

        with pytest.raises(PublishError) as exc_info:
            _gate_publish([release], REPO_ROOT)

        msg = str(exc_info.value)
        assert "DEF-002" in msg

    def test_passes_for_compliance_sdk_adapter(self, tmp_path):
        """A compliance sdk-adapter release passes _gate_publish (no open blockers)."""
        from vcfops_packaging.publish import _gate_publish

        adapter_dir = tmp_path / "content" / "sdk-adapters" / "compliance"
        adapter_dir.mkdir(parents=True)
        adapter_yaml = adapter_dir / "adapter.yaml"
        adapter_yaml.write_text("name: test\n", encoding="utf-8")

        release = self._make_mock_release(adapter_yaml, "compliance-managementpack")
        # Must not raise.
        _gate_publish([release], REPO_ROOT)

    def test_passes_for_vcommunity_sdk_adapter(self, tmp_path):
        """A vcommunity sdk-adapter release passes _gate_publish (no open blockers)."""
        from vcfops_packaging.publish import _gate_publish

        adapter_dir = tmp_path / "content" / "sdk-adapters" / "vcommunity"
        adapter_dir.mkdir(parents=True)
        adapter_yaml = adapter_dir / "adapter.yaml"
        adapter_yaml.write_text("name: test\n", encoding="utf-8")

        release = self._make_mock_release(adapter_yaml, "vcommunity-managementpack")
        _gate_publish([release], REPO_ROOT)

    def test_passes_when_defects_all_closed_or_tracked(self, tmp_path):
        """A registry with only closed/tracked defects lets _gate_publish pass."""
        from vcfops_packaging.publish import _gate_publish, PublishError

        # Write a registry where the synology defect is closed.
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
        """When factory_repo has no context/defects.md the gate vacuously passes
        with a clearly visible WARNING — never raises, never falls back to the
        package-relative registry."""
        from vcfops_packaging.publish import _gate_publish

        # tmp_path has no context/ directory — registry is absent.
        adapter_dir = tmp_path / "content" / "sdk-adapters" / "synology"
        adapter_dir.mkdir(parents=True)
        adapter_yaml = adapter_dir / "adapter.yaml"
        adapter_yaml.write_text("name: test\n", encoding="utf-8")

        release = self._make_mock_release(adapter_yaml, "synology-managementpack")
        # Must NOT raise even though synology has an open blocking defect in
        # the real registry — the registry is absent in this fixture repo.
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
    contract.
    """

    _DEFECTS_SCRIPT = REPO_ROOT / "vcfops_packaging" / "defects.py"
    _REAL_REGISTRY = REPO_ROOT / "context" / "defects.md"

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

    def test_pak_synology_exits_2_names_def001(self):
        """--pak synology with the real registry → exit 2, names DEF-001."""
        rc, out, err = self._run_script(
            self._DEFECTS_SCRIPT,
            ["--pak", "synology", "--registry", str(self._REAL_REGISTRY)],
        )
        assert rc == 2, f"Expected exit 2 for synology; got {rc}\nstdout: {out}\nstderr: {err}"
        assert "DEF-001" in out, f"Output must name DEF-001; got:\n{out}"
        assert "RULE-012" in out, f"Output must name RULE-012; got:\n{out}"

    def test_pak_compliance_exits_0(self):
        """--pak compliance → exit 0 (no open blockers)."""
        rc, out, err = self._run_script(
            self._DEFECTS_SCRIPT,
            ["--pak", "compliance", "--registry", str(self._REAL_REGISTRY)],
        )
        assert rc == 0, f"Expected exit 0 for compliance; got {rc}\nstdout: {out}\nstderr: {err}"
        assert "compliance" in out, f"Output must mention pak name; got:\n{out}"

    def test_all_exits_2_lists_def001_and_def002(self):
        """--all → exit 2, lists both DEF-001 and DEF-002."""
        rc, out, err = self._run_script(
            self._DEFECTS_SCRIPT,
            ["--all", "--registry", str(self._REAL_REGISTRY)],
        )
        assert rc == 2, f"Expected exit 2 for --all; got {rc}\nstdout: {out}\nstderr: {err}"
        assert "DEF-001" in out, f"Output must list DEF-001; got:\n{out}"
        assert "DEF-002" in out, f"Output must list DEF-002; got:\n{out}"

    def test_missing_registry_exits_1(self, tmp_path):
        """--registry pointing at a nonexistent path → exit 1, clear error."""
        missing = tmp_path / "no_such_dir" / "defects.md"
        rc, out, err = self._run_script(
            self._DEFECTS_SCRIPT,
            ["--pak", "synology", "--registry", str(missing)],
        )
        assert rc == 1, f"Expected exit 1 for missing registry; got {rc}\nstdout: {out}\nstderr: {err}"
        combined = out + err
        assert any(kw in combined.lower() for kw in ("not found", "registry", "error")), (
            f"Error must mention the missing registry; got:\n{combined}"
        )

    # --- Bare-copy invocation: the load-bearing curl-and-run proof --------------

    def test_bare_copy_matches_in_package_run(self, tmp_path):
        """Copy defects.py and defects.md to a clean temp dir; run it there.

        The pak-repo CI workflow does:
          curl .../defects.py -o defects.py
          curl .../context/defects.md -o defects.md
          python3 defects.py --pak <name> --registry defects.md

        This test reproduces that exactly.  The copy of defects.py has no
        vcfops_packaging on sys.path (the cwd is the temp dir, not the factory
        repo), and there is no __init__.py or package structure present.

        The exit code and DEF-001 mention must match the in-package run.
        """
        import shutil

        # Drop the two files into a completely empty temp dir.
        script_copy = tmp_path / "defects.py"
        registry_copy = tmp_path / "defects.md"
        shutil.copy2(str(self._DEFECTS_SCRIPT), str(script_copy))
        shutil.copy2(str(self._REAL_REGISTRY), str(registry_copy))

        # Run from the temp dir; cwd has NO factory repo structure.
        rc, out, err = self._run_script(
            script_copy,
            ["--pak", "synology", "--registry", str(registry_copy)],
            cwd=tmp_path,
        )

        # Must match the in-package run: exit 2, names DEF-001 and RULE-012.
        assert rc == 2, (
            f"Bare-copy run must exit 2 (synology blocked by DEF-001); "
            f"got {rc}\nstdout: {out}\nstderr: {err}"
        )
        assert "DEF-001" in out, (
            f"Bare-copy run output must name DEF-001; got:\n{out}"
        )
        assert "RULE-012" in out, (
            f"Bare-copy run output must name RULE-012; got:\n{out}"
        )

    def test_bare_copy_compliance_exits_0(self, tmp_path):
        """Bare-copy run for compliance → exit 0 (matches in-package result)."""
        import shutil

        script_copy = tmp_path / "defects.py"
        registry_copy = tmp_path / "defects.md"
        shutil.copy2(str(self._DEFECTS_SCRIPT), str(script_copy))
        shutil.copy2(str(self._REAL_REGISTRY), str(registry_copy))

        rc, out, err = self._run_script(
            script_copy,
            ["--pak", "compliance", "--registry", str(registry_copy)],
            cwd=tmp_path,
        )
        assert rc == 0, (
            f"Bare-copy run must exit 0 for compliance; "
            f"got {rc}\nstdout: {out}\nstderr: {err}"
        )

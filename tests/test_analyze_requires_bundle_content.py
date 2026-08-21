"""Issue #85: `vcfops_packaging analyze` must not exit 0 on a non-bundle path.

Pointing analyze at a .zip or at any directory without a ``content/``
subdirectory used to print "no metric references found" and exit 0,
which an operator reads as "nothing needs enabling" when in fact
nothing was inspected at all (same silently-dodges-the-gate class as
issue #71).

No network: the CLI test never reaches the describe cache, which is the
point (the path check fires before any live work).
"""
from __future__ import annotations

import types
import zipfile
from pathlib import Path

import pytest

from vcfops_packaging.audit import AuditError, analyze_staged_bundle
from vcfops_packaging.cli import cmd_analyze


def _args(path: Path):
    return types.SimpleNamespace(
        bundle_dir=str(path), profile=None, no_live_describe=True, json_out=None
    )


class TestAnalyzeStagedBundleGuard:
    def test_directory_without_content_raises(self, tmp_path):
        (tmp_path / "not-a-bundle").mkdir()
        with pytest.raises(AuditError) as exc:
            analyze_staged_bundle(tmp_path / "not-a-bundle", describe_cache=None)
        assert "no content/ subdirectory" in str(exc.value)

    def test_content_as_a_file_raises(self, tmp_path):
        bundle = tmp_path / "bundle"
        bundle.mkdir()
        (bundle / "content").write_text("not a directory")
        with pytest.raises(AuditError):
            analyze_staged_bundle(bundle, describe_cache=None)

    def test_extracted_pak_is_rejected(self, tmp_path):
        """An extracted .pak has a content/ dir, but one holding per-type
        SUBDIRECTORIES, not the flat artifacts analyze reads. It used to
        exit 0 having inspected nothing (issue #85's second half)."""
        pak = tmp_path / "extracted"
        (pak / "content" / "supermetrics").mkdir(parents=True)
        (pak / "content" / "dashboards").mkdir(parents=True)
        (pak / "manifest.txt").write_text("pak")
        with pytest.raises(AuditError) as exc:
            analyze_staged_bundle(pak, describe_cache=None)
        assert "bundle.json" in str(exc.value)

    def test_empty_content_dir_still_analyzes(self, tmp_path):
        """A real staged bundle with nothing to enable is a legitimate
        clean result, so the guard must not swallow it."""
        bundle = tmp_path / "bundle"
        (bundle / "content").mkdir(parents=True)
        (bundle / "bundle.json").write_text("{}")

        class _Cache:
            def resolve_metric(self, *a):  # pragma: no cover - no refs to resolve
                return None

            def has(self, *a):  # pragma: no cover
                return True

        result = analyze_staged_bundle(bundle, _Cache())
        assert result.refs == []
        assert result.needs_enable == []


class TestCmdAnalyzeExitCodes:
    def test_extracted_pak_exits_nonzero(self, tmp_path, capsys):
        pak = tmp_path / "extracted"
        (pak / "content" / "supermetrics").mkdir(parents=True)
        rc = cmd_analyze(_args(pak))
        err = capsys.readouterr().err
        assert rc != 0
        assert "bundle.json" in err

    def test_real_staged_bundle_layout_is_accepted(self, tmp_path, capsys):
        """The guard must not reject the layout the builder produces."""
        from vcfops_packaging.audit import staged_bundle_problem

        bundle = tmp_path / "bundle"
        (bundle / "content").mkdir(parents=True)
        (bundle / "bundle.json").write_text("{}")
        assert staged_bundle_problem(bundle) is None

    def test_one_wording_for_both_callers(self, tmp_path, capsys):
        """N-7: the CLI and the library gate must not drift to two
        different messages for the same condition."""
        from vcfops_packaging.audit import staged_bundle_problem

        (tmp_path / "wrong").mkdir()
        cmd_analyze(_args(tmp_path / "wrong"))
        err = capsys.readouterr().err
        assert staged_bundle_problem(tmp_path / "wrong") in err

    def test_zip_path_exits_nonzero(self, tmp_path, capsys):
        zip_path = tmp_path / "bundle.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("content/supermetrics.json", "{}")
        rc = cmd_analyze(_args(zip_path))
        err = capsys.readouterr().err
        assert rc != 0
        assert "not a staged bundle directory" in err

    def test_non_bundle_directory_exits_nonzero(self, tmp_path, capsys):
        (tmp_path / "wrong").mkdir()
        rc = cmd_analyze(_args(tmp_path / "wrong"))
        err = capsys.readouterr().err
        assert rc != 0
        assert "no content/ subdirectory" in err or "not a staged bundle" in err

    def test_missing_path_still_reports_not_found(self, tmp_path, capsys):
        rc = cmd_analyze(_args(tmp_path / "nope"))
        assert rc != 0
        assert "bundle directory not found" in capsys.readouterr().err

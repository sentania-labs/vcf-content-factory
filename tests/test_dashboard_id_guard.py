"""Issue #113: dashboard id-stability guard, executing-branch coverage.

Dashboard import identity on VCF Ops is the NAME, not the UUID
(knowledge/context/api-surface/content_import_skip_semantics.md), so a
changed id: under an unchanged name: silently orphans the previously
installed UUID. The guard (src/vcfops_dashboards/id_guard.py) runs in
the validate path and compares each working-tree dashboard YAML against
git HEAD.

Covered branches, each in a temp git repo fixture:

  - id mutated, name kept        -> validate fails (rc 1, ID-STABILITY)
  - name mutated, id kept        -> passes (legitimate rename)
  - brand-new dashboard file     -> passes
  - file renamed + re-id'd       -> fails (name scan catches it)
  - file renamed, identity kept  -> passes
  - localized git stderr         -> rename+re-id STILL fails hard
    (verdicts come from return codes and ls-tree stdout, never from
    stderr wording; _run_git also pins LC_ALL=C)
  - not a git repo               -> warns "could not run", passes
  - git binary unavailable       -> warns "could not run", passes
  - unborn HEAD (no commits)     -> warns "no baseline", passes
  - mutation check: with the guard disabled, the failing scenario
    passes, proving the failure comes from the guard and nowhere else.

No network, no real content/ writes; everything lives under tmp_path.
"""
from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

import pytest

from vcfops_dashboards import id_guard
from vcfops_dashboards.cli import main as dashboards_main

OLD_ID = "11111111-2222-4333-8444-555555555555"
NEW_ID = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
NAME = "[VCF Content Factory] Guard Probe Dashboard"


def _dashboard_yaml(dash_id: str, name: str) -> str:
    return textwrap.dedent(
        f"""\
        id: {dash_id}
        name: '{name}'
        widgets:
        - id: w1
          type: TextDisplay
          title: Note
          coords: {{x: 1, y: 1, w: 4, h: 4}}
          html: '<b>probe</b>'
        """
    )


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
    )


def _make_repo(tmp_path: Path, git_init: bool = True, commit: bool = True) -> Path:
    """Repo with content/dashboards/probe.yaml committed at OLD_ID/NAME."""
    repo = tmp_path / "repo"
    dash_dir = repo / "content" / "dashboards"
    dash_dir.mkdir(parents=True)
    (dash_dir / "probe.yaml").write_text(_dashboard_yaml(OLD_ID, NAME))
    if git_init:
        _git(repo, "init", "-q")
        if commit:
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "-m", "baseline")
    return repo


def _validate(repo: Path) -> int:
    return dashboards_main(
        [
            "--views-dir", str(repo / "content" / "views"),
            "--dashboards-dir", str(repo / "content" / "dashboards"),
            "validate",
        ]
    )


def test_id_mutated_name_kept_fails(tmp_path, capsys):
    repo = _make_repo(tmp_path)
    (repo / "content/dashboards/probe.yaml").write_text(
        _dashboard_yaml(NEW_ID, NAME)
    )
    rc = _validate(repo)
    err = capsys.readouterr().err
    assert rc == 1
    assert "ID-STABILITY:" in err
    assert OLD_ID in err and NEW_ID in err
    assert "orphan" in err


def test_name_mutated_id_kept_passes(tmp_path, capsys):
    repo = _make_repo(tmp_path)
    (repo / "content/dashboards/probe.yaml").write_text(
        _dashboard_yaml(OLD_ID, NAME + " Renamed")
    )
    rc = _validate(repo)
    err = capsys.readouterr().err
    assert rc == 0
    assert "ID-STABILITY:" not in err


def test_new_dashboard_file_passes(tmp_path, capsys):
    repo = _make_repo(tmp_path)
    (repo / "content/dashboards/fresh.yaml").write_text(
        _dashboard_yaml(NEW_ID, "[VCF Content Factory] Brand New Dashboard")
    )
    rc = _validate(repo)
    err = capsys.readouterr().err
    assert rc == 0
    assert "ID-STABILITY:" not in err


def test_file_rename_plus_reid_fails(tmp_path, capsys):
    """Same committed name in a differently named file, new id: still fails."""
    repo = _make_repo(tmp_path)
    (repo / "content/dashboards/probe.yaml").unlink()
    (repo / "content/dashboards/renamed.yaml").write_text(
        _dashboard_yaml(NEW_ID, NAME)
    )
    rc = _validate(repo)
    err = capsys.readouterr().err
    assert rc == 1
    assert "ID-STABILITY:" in err
    assert "probe.yaml" in err  # points at where the committed identity lives


def test_localized_git_stderr_still_fails_hard(tmp_path, capsys, monkeypatch):
    """A localized git must not degrade the guard from error to warning.

    Wraps subprocess.run so every git call keeps its real return code and
    stdout but gets its stderr replaced with a non-English fatal message,
    and asserts the guard pins LC_ALL=C on each call. The rename+re-id
    scenario must still be a hard ID-STABILITY failure.
    """
    repo = _make_repo(tmp_path)
    (repo / "content/dashboards/probe.yaml").unlink()
    (repo / "content/dashboards/renamed.yaml").write_text(
        _dashboard_yaml(NEW_ID, NAME)
    )

    real_run = subprocess.run
    seen_envs = []

    def _localized_run(cmd, **kwargs):
        seen_envs.append(kwargs.get("env"))
        proc = real_run(cmd, **kwargs)
        if proc.stderr:
            proc = subprocess.CompletedProcess(
                proc.args,
                proc.returncode,
                stdout=proc.stdout,
                stderr="schwerwiegend: Pfad existiert nicht in 'HEAD'",
            )
        return proc

    monkeypatch.setattr(id_guard.subprocess, "run", _localized_run)
    rc = _validate(repo)
    err = capsys.readouterr().err
    assert rc == 1
    assert "ID-STABILITY:" in err
    assert seen_envs, "guard never went through _run_git"
    for env in seen_envs:
        assert env is not None and env.get("LC_ALL") == "C"


def test_file_rename_identity_kept_passes(tmp_path, capsys):
    repo = _make_repo(tmp_path)
    (repo / "content/dashboards/probe.yaml").unlink()
    (repo / "content/dashboards/renamed.yaml").write_text(
        _dashboard_yaml(OLD_ID, NAME)
    )
    rc = _validate(repo)
    err = capsys.readouterr().err
    assert rc == 0
    assert "ID-STABILITY:" not in err


def test_no_git_repo_warns_and_passes(tmp_path, capsys):
    repo = _make_repo(tmp_path, git_init=False)
    rc = _validate(repo)
    err = capsys.readouterr().err
    assert rc == 0
    assert "id-stability guard could not run" in err
    assert "would NOT be caught" in err


def test_git_binary_unavailable_warns_and_passes(tmp_path, capsys, monkeypatch):
    repo = _make_repo(tmp_path)
    (repo / "content/dashboards/probe.yaml").write_text(
        _dashboard_yaml(NEW_ID, NAME)
    )

    def _no_git(*args, **kwargs):
        raise FileNotFoundError("No such file or directory: 'git'")

    monkeypatch.setattr(id_guard.subprocess, "run", _no_git)
    rc = _validate(repo)
    err = capsys.readouterr().err
    # Guard degrades to pass, but never silently: the warning is mandatory.
    assert rc == 0
    assert "id-stability guard could not run" in err
    assert "git is not" in err


def test_unborn_head_warns_and_passes(tmp_path, capsys):
    repo = _make_repo(tmp_path, git_init=True, commit=False)
    rc = _validate(repo)
    err = capsys.readouterr().err
    assert rc == 0
    assert "no commits" in err
    assert "ID-STABILITY:" not in err


def test_mutation_check_guard_disabled_scenario_passes(tmp_path, capsys, monkeypatch):
    """Disable the guard: the id-mutation scenario must then pass validate.

    Proves test_id_mutated_name_kept_fails fails BECAUSE of the guard,
    not because of some other validator tripping on the same fixture.
    """
    repo = _make_repo(tmp_path)
    (repo / "content/dashboards/probe.yaml").write_text(
        _dashboard_yaml(NEW_ID, NAME)
    )
    import vcfops_dashboards.cli as cli_mod
    monkeypatch.setattr(
        cli_mod, "check_dashboard_id_stability", lambda _dir: ([], [])
    )
    rc = _validate(repo)
    err = capsys.readouterr().err
    assert rc == 0
    assert "ID-STABILITY:" not in err

"""Tests for the bootstrap-v2 Phase 1/1b preflight doctor.

Fast, no network, no real git: every git interaction goes through an
injected fake runner. RULE-008 is asserted directly: secret VALUES from
a synthetic .env must never appear in doctor output.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

import pytest

from vcfops_common.doctor import (
    GREETING,
    KNOWN_BOOTSTRAP_SCRIPTS,
    STALE_AFTER_HOURS,
    TIMESTAMP_KEY,
    Commit,
    build_checklist,
    _safe_age_hours,
    classify_commit,
    classify_path,
    find_env_file,
    inspect_credentials,
    is_first_run,
    inspect_environment,
    read_bootstrap_status,
    run_doctor,
    unrecorded_bootstrap_scripts,
    venv_python,
    _parse_commit_log,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_SECRET = "synthetic-not-a-real-password-42"


def write_fresh_bootstrap_status(root: Path) -> None:
    """Both known scripts recorded, fresh, zero failures."""
    (root / ".bootstrap-status").write_text(
        f"{ts(hours_ago=1)} bootstrap_references cloned=1 updated=0 failed=0 failures=-\n"
        f"{ts(hours_ago=1)} bootstrap_managed_paks cloned=1 updated=0 failed=0 failures=-\n"
    )


def make_configured_root(tmp_path: Path) -> Path:
    """A tmp repo root that looks fully configured."""
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".env").write_text(
        "VCFOPS_PROD_HOST=ops.example.test\n"
        "VCFOPS_PROD_USER=admin\n"
        f"VCFOPS_PROD_PASSWORD={FAKE_SECRET}\n"
    )
    (root / ".venv").mkdir()
    runtime = root / "src" / "vcfops_managementpacks" / "adapter_runtime"
    (runtime / "lib").mkdir(parents=True)
    (runtime / "mpb_adapter3.jar").write_bytes(b"jar")
    (runtime / "lib" / "mpb_adapter-9.0.1.jar").write_bytes(b"jar")
    write_fresh_bootstrap_status(root)
    return root


def fake_git(*, behind_log: str = "", ahead_log: str = "", dirty: bool = False,
             fetch_rc: int = 0, remotes: str = "origin\n",
             tracking_remote: str = "origin", upstream: str = "origin/main\n",
             fetch_log: Optional[List[str]] = None):
    def run(args, timeout=0):
        args = list(args)
        if args[:2] == ["rev-parse", "--git-dir"]:
            return 0, ".git\n"
        if args[0] == "fetch":
            if fetch_log is not None:
                fetch_log.append(args[1] if len(args) > 1 else "")
            return fetch_rc, ""
        if args == ["remote"]:
            return 0, remotes
        if args[:2] == ["config", "--get"]:
            return (0, tracking_remote + "\n") if tracking_remote else (1, "")
        if args == ["rev-parse", "--abbrev-ref", "@{upstream}"]:
            return (0, upstream) if upstream else (1, "")
        if args == ["rev-parse", "--abbrev-ref", "HEAD"]:
            return 0, "main\n"
        if args[0] == "status":
            return 0, (" M src/<fixture-a>.py\n" if dirty else "")
        if args[0] == "log":
            rng = args[-1]
            if rng.startswith("HEAD.."):
                return 0, behind_log
            return 0, ahead_log
        return 0, ""
    return run


def collect(root, git, imports_ok=True, environ=None, check_import=None):
    lines = []
    if check_import is None and imports_ok is not None:
        check_import = lambda name: imports_ok  # noqa: E731
    run_doctor(
        root,
        git=git,
        check_import=check_import,
        environ={} if environ is None else environ,  # isolate from real shell
        out=lines.append,
    )
    return lines


def ts(hours_ago: float = 0.0) -> str:
    """ISO8601 UTC timestamp N hours in the past, for .bootstrap-status
    fixtures. Generated (not hardcoded) so age assertions stay
    deterministic regardless of when the suite runs."""
    moment = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


not_root = pytest.mark.skipif(
    getattr(os, "geteuid", lambda: 1)() == 0,
    reason="chmod 000 is ineffective as root",
)


# ---------------------------------------------------------------------------
# Classification: core vs environment/state vs mixed
# ---------------------------------------------------------------------------

# Fixture paths use an angle-bracket <fixture> segment so the CI path
# reference audit reads them as placeholders, not as real repo citations.

def test_classify_core_paths():
    for p in ("src/vcfops_common/<fixture>.py", "scripts/<fixture>.sh",
              ".claude/agents/<fixture>.md", "knowledge/rules/<fixture>.md",
              "knowledge/lessons/<fixture>.md", "<FIXTURE>.md",
              "bundles/<fixture>/manifest.yaml",
              "content/dashboards/<fixture>.yaml"):
        assert classify_path(p) == "core", p


def test_classify_local_state_paths():
    for p in ("knowledge/context/curation/<fixture>",
              "knowledge/context/investigations/<fixture>.md"):
        assert classify_path(p) == "local", p


def test_review_reports_are_core():
    # Review reports ship with framework PRs by convention: core.
    assert classify_path("knowledge/context/reviews/framework/<fixture>.md") == "core"


def test_classify_commit_buckets():
    assert classify_commit(["src/<fixture-a>.py", "tests/<fixture>.py"]) == "core"
    assert classify_commit(["knowledge/context/curation/<fixture>"]) == "local"
    assert classify_commit(
        ["src/<fixture-a>.py", "knowledge/context/investigations/<fixture>.md"]
    ) == "mixed"


def test_ahead_rendering_flags_mixed_and_nudges_core_only(tmp_path):
    root = make_configured_root(tmp_path)
    ahead = (
        "\x01aaa1111\x02core tooling fix\n\nsrc/vcfops_common/<fixture>.py\n"
        "\x01bbb2222\x02recon log update\n\nknowledge/context/investigations/<fixture>.md\n"
        "\x01ccc3333\x02both at once\n\nsrc/<fixture-a>.py\nknowledge/context/curation/<fixture>\n"
    )
    lines = collect(root, fake_git(ahead_log=ahead))
    text = "\n".join(lines)
    assert "core (PR candidates):" in text
    assert "aaa1111 core tooling fix" in text
    assert "environment/state (keep local, no PR needed):" in text
    assert "bbb2222" in text
    assert "mixed (contains both, split before PR):" in text
    assert "ccc3333" in text
    # PR nudge covers exactly the one core commit, never local state.
    assert "1 core commit(s) are ahead" in text
    assert "Do not suggest pushing environment/state commits" in text


def test_ahead_only_local_state_has_no_pr_nudge(tmp_path):
    root = make_configured_root(tmp_path)
    ahead = "\x01bbb2222\x02recon log\n\nknowledge/context/investigations/<fixture>.md\n"
    lines = collect(root, fake_git(ahead_log=ahead))
    text = "\n".join(lines)
    assert "keep local" in text
    assert "offer to open a PR" not in text


# ---------------------------------------------------------------------------
# Behind: ELI5 grouped summary + ff-pull offer on clean tree only
# ---------------------------------------------------------------------------

def test_behind_clean_tree_groups_by_area_and_offers_ff_pull(tmp_path):
    root = make_configured_root(tmp_path)
    behind = (
        "\x01ddd4444\x02fix renderer crash\n\nsrc/vcfops_dashboards/<fixture>.py\n"
        "\x01eee5555\x02add snapshot dashboard\n\ncontent/dashboards/<fixture>.yaml\n"
    )
    lines = collect(root, fake_git(behind_log=behind))
    text = "\n".join(lines)
    assert "behind origin/main by 2 commit(s)" in text
    assert "tooling fixes: 1" in text
    assert "new dashboards: 1" in text
    assert "fix renderer crash" in text
    assert "git pull --ff-only" in text
    assert "Do not pull without asking" in text


def test_behind_dirty_tree_never_offers_pull(tmp_path):
    root = make_configured_root(tmp_path)
    behind = "\x01ddd4444\x02fix\n\nsrc/<fixture-a>.py\n"
    lines = collect(root, fake_git(behind_log=behind, dirty=True))
    text = "\n".join(lines)
    assert "uncommitted or untracked changes" in text
    assert "git pull --ff-only" not in text


# ---------------------------------------------------------------------------
# Credential readiness (names only, never values)
# ---------------------------------------------------------------------------

def test_credentials_complete_and_incomplete_profiles(tmp_path):
    (tmp_path / ".env").write_text(
        "VCFOPS_PROD_HOST=h\nVCFOPS_PROD_USER=u\n"
        f"VCFOPS_PROD_PASSWORD={FAKE_SECRET}\n"
        "VCFOPS_QA_HOST=h2\nVCFOPS_QA_USER=u2\n"   # qa missing PASSWORD
        "VCFOPS_PROD_AUTH_SOURCE=Local\n"
        "SOME_OTHER_VAR=x\n"
    )
    exists, profiles, note = inspect_credentials(tmp_path, environ={})
    assert exists and not note
    by_name = {p.name: p for p in profiles}
    assert by_name["prod"].complete
    assert by_name["qa"].missing == ["VCFOPS_QA_PASSWORD"]


def test_incomplete_profile_reported_by_var_name_never_value(tmp_path):
    root = make_configured_root(tmp_path)
    (root / ".env").write_text(
        "VCFOPS_PROD_HOST=h\nVCFOPS_PROD_USER=u\n"
        f"VCFOPS_PROD_PASSWORD={FAKE_SECRET}\n"
        "VCFOPS_QA_HOST=h2\n"
    )
    lines = collect(root, fake_git())
    text = "\n".join(lines)
    assert "profile 'qa' is incomplete" in text
    assert "VCFOPS_QA_PASSWORD" in text
    assert FAKE_SECRET not in text  # RULE-008


def test_suffix_vars_without_host_are_not_a_profile(tmp_path):
    """VCFOPS_*_PASSWORD-style vars with no matching _HOST (e.g. SSH creds)
    must not be misread as an incomplete Ops profile: _HOST anchors a
    profile, same contract as _env.available_profiles()."""
    (tmp_path / ".env").write_text(
        "VCFOPS_PROD_HOST=h\nVCFOPS_PROD_USER=u\n"
        f"VCFOPS_PROD_PASSWORD={FAKE_SECRET}\n"
        f"VCFOPS_PROD_SSH_PASSWORD={FAKE_SECRET}\n"
    )
    exists, profiles, note = inspect_credentials(tmp_path, environ={})
    assert exists and not note
    assert [p.name for p in profiles] == ["prod"]
    assert profiles[0].complete


def test_no_profiles_offers_wizard(tmp_path):
    root = make_configured_root(tmp_path)
    (root / ".env").write_text("SOME_OTHER_VAR=1\n")
    lines = collect(root, fake_git())
    text = "\n".join(lines)
    assert "no VCFOPS profiles" in text
    assert "credential setup wizard" in text


# ---------------------------------------------------------------------------
# Green path: exactly one line
# ---------------------------------------------------------------------------

def test_all_green_is_one_line(tmp_path):
    root = make_configured_root(tmp_path)
    lines = collect(root, fake_git())
    assert len(lines) == 1
    assert lines[0].startswith("doctor: all green")
    assert "origin/main" in lines[0]
    assert "prod" in lines[0]


def test_green_line_notes_offline_fetch(tmp_path):
    root = make_configured_root(tmp_path)
    lines = collect(root, fake_git(fetch_rc=1))
    assert len(lines) == 1
    assert "offline" in lines[0]


def test_exit_code_always_zero(tmp_path):
    root = make_configured_root(tmp_path)
    (root / ".env").unlink()  # first-run state
    rc = run_doctor(root, git=fake_git(), check_import=lambda n: True,
                    out=lambda s: None)
    assert rc == 0


# ---------------------------------------------------------------------------
# First-run detection and concierge checklist
# ---------------------------------------------------------------------------

def test_first_run_when_env_missing(tmp_path):
    root = make_configured_root(tmp_path)
    (root / ".env").unlink()
    env = inspect_environment(root, lambda n: True)
    assert is_first_run(root, env, env_file_exists=False)


def test_first_run_when_deps_missing(tmp_path):
    root = make_configured_root(tmp_path)
    env = inspect_environment(root, lambda n: False)  # nothing importable
    assert is_first_run(root, env, env_file_exists=True)


def test_not_first_run_when_configured(tmp_path):
    root = make_configured_root(tmp_path)
    env = inspect_environment(root, lambda n: True)
    assert not is_first_run(root, env, env_file_exists=True)


def test_jmespath_alone_does_not_trigger_first_run(tmp_path):
    root = make_configured_root(tmp_path)
    env = inspect_environment(root, lambda n: n != "jmespath")
    assert not is_first_run(root, env, env_file_exists=True)


def test_first_run_emits_greeting_and_checklist_json(tmp_path):
    root = make_configured_root(tmp_path)
    (root / ".env").unlink()
    lines = collect(root, fake_git())
    text = "\n".join(lines)
    assert "FIRST-RUN DETECTED" in lines[0]
    assert GREETING in text
    json_line = next(ln for ln in lines if ln.startswith("CHECKLIST-JSON: "))
    payload = json.loads(json_line[len("CHECKLIST-JSON: "):])
    ids = [item["id"] for item in payload["items"]]
    assert ids == ["python", "venv", "deps", "credentials",
                   "bootstrap-clones", "recheck"]
    by_id = {i["id"]: i for i in payload["items"]}
    assert by_id["credentials"]["status"] == "fail"
    assert by_id["python"]["status"] == "ok"


# ---------------------------------------------------------------------------
# Bootstrap health
# ---------------------------------------------------------------------------

def test_bootstrap_status_last_line_wins_and_failures_surface(tmp_path):
    root = make_configured_root(tmp_path)
    (root / ".bootstrap-status").write_text(
        f"{ts(hours_ago=3)} bootstrap_references cloned=0 updated=0 failed=2 failures=a,b\n"
        f"{ts(hours_ago=2)} bootstrap_references cloned=2 updated=1 failed=1 failures=dell-emc-mp\n"
        f"{ts(hours_ago=1)} bootstrap_managed_paks cloned=1 updated=0 failed=0 failures=-\n"
    )
    status, note = read_bootstrap_status(root)
    assert not note
    assert status["bootstrap_references"]["failed"] == "1"
    lines = collect(root, fake_git())
    text = "\n".join(lines)
    assert "bootstrap_references: 1 clone/update failure(s): dell-emc-mp" in text
    assert "bootstrap_managed_paks" not in text  # zero failures: no delta


def test_bootstrap_timestamp_is_captured(tmp_path):
    root = make_configured_root(tmp_path)
    stamp = ts(hours_ago=2)
    (root / ".bootstrap-status").write_text(
        f"{stamp} bootstrap_references cloned=1 updated=0 failed=0 failures=-\n"
    )
    status, note = read_bootstrap_status(root)
    assert not note
    assert status["bootstrap_references"][TIMESTAMP_KEY] == stamp


def test_fresh_bootstrap_data_emits_no_age_line(tmp_path):
    root = make_configured_root(tmp_path)
    (root / ".bootstrap-status").write_text(
        f"{ts(hours_ago=STALE_AFTER_HOURS - 1)} bootstrap_references "
        "cloned=1 updated=0 failed=0 failures=-\n"
        f"{ts(hours_ago=STALE_AFTER_HOURS - 1)} bootstrap_managed_paks "
        "cloned=1 updated=0 failed=0 failures=-\n"
    )
    lines = collect(root, fake_git())
    assert len(lines) == 1  # still the green line: exception-only
    assert "stale" not in lines[0]


def test_stale_bootstrap_data_is_surfaced(tmp_path):
    root = make_configured_root(tmp_path)
    (root / ".bootstrap-status").write_text(
        f"{ts(hours_ago=72)} bootstrap_references "
        "cloned=1 updated=0 failed=0 failures=-\n"
    )
    lines = collect(root, fake_git())
    text = "\n".join(lines)
    assert "bootstrap_references: bootstrap health is 3 day(s) stale" in text
    assert "the script may not be running" in text


def test_stale_under_two_days_reports_in_hours(tmp_path):
    root = make_configured_root(tmp_path)
    (root / ".bootstrap-status").write_text(
        f"{ts(hours_ago=30)} bootstrap_references "
        "cloned=1 updated=0 failed=0 failures=-\n"
    )
    text = "\n".join(collect(root, fake_git()))
    assert "stale" in text
    assert "hour(s) stale" in text or "1 day(s) stale" in text


def test_unparseable_timestamp_degrades_not_crashes(tmp_path):
    root = make_configured_root(tmp_path)
    (root / ".bootstrap-status").write_text(
        "not-a-timestamp bootstrap_references cloned=1 updated=0 failed=0 failures=-\n"
    )
    lines = collect(root, fake_git())
    text = "\n".join(lines)
    assert "unparseable timestamp" in text
    assert "bootstrap age unknown" in text


def test_safe_age_hours_forms():
    now = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)
    # Trailing-Z form (what the scripts write; fromisoformat rejects it
    # before py3.11).
    assert _safe_age_hours("2026-08-20T06:00:00Z", now=now) == 6.0
    # Explicit offset form.
    assert _safe_age_hours("2026-08-20T06:00:00+00:00", now=now) == 6.0
    # Naive form is treated as UTC.
    assert _safe_age_hours("2026-08-20T06:00:00", now=now) == 6.0
    # Garbage and empties degrade to None, never raise.
    for bad in ("", "not-a-timestamp", "2026-13-45T99:99:99Z", None):
        assert _safe_age_hours(bad, now=now) is None


def test_timestamp_key_cannot_be_spoofed_by_a_token(tmp_path):
    root = make_configured_root(tmp_path)
    stamp = ts(hours_ago=1)
    (root / ".bootstrap-status").write_text(
        f"{stamp} bootstrap_references cloned=1 failed=0 {TIMESTAMP_KEY}=1999-01-01T00:00:00Z\n"
        f"{stamp} bootstrap_managed_paks cloned=1 failed=0 failures=-\n"
    )
    status, _ = read_bootstrap_status(root)
    assert status["bootstrap_references"][TIMESTAMP_KEY] == stamp
    assert "stale" not in "\n".join(collect(root, fake_git()))


def test_both_scripts_recorded_is_silent(tmp_path):
    root = make_configured_root(tmp_path)  # writes both fresh records
    lines = collect(root, fake_git())
    assert len(lines) == 1  # still the green line


def test_one_missing_script_record_is_its_own_delta(tmp_path):
    """A clean record from one script must not cover for the other,
    which may have died before its status write (hook timeout, missing
    registry)."""
    root = make_configured_root(tmp_path)
    (root / ".bootstrap-status").write_text(
        f"{ts(hours_ago=1)} bootstrap_references cloned=1 updated=0 failed=0 failures=-\n"
    )
    lines = collect(root, fake_git())
    text = "\n".join(lines)
    assert "no bootstrap run recorded for bootstrap_managed_paks" in text
    assert "bootstrap_references" not in text.split("recorded for")[1]


def test_absent_status_file_reports_both_scripts(tmp_path):
    root = make_configured_root(tmp_path)
    (root / ".bootstrap-status").unlink()
    text = "\n".join(collect(root, fake_git()))
    for script in KNOWN_BOOTSTRAP_SCRIPTS:
        assert script in text


def test_unrecorded_bootstrap_scripts_helper():
    assert unrecorded_bootstrap_scripts({}) == list(KNOWN_BOOTSTRAP_SCRIPTS)
    assert unrecorded_bootstrap_scripts(
        {"bootstrap_references": {}}
    ) == ["bootstrap_managed_paks"]
    assert unrecorded_bootstrap_scripts(
        {s: {} for s in KNOWN_BOOTSTRAP_SCRIPTS}
    ) == []


# ---------------------------------------------------------------------------
# Codex PR #93: empty credential values are not credentials
# ---------------------------------------------------------------------------

def test_empty_password_in_env_file_is_missing(tmp_path):
    """resolve_profile_credentials() rejects empty required values, so
    the doctor must not call the profile ready."""
    root = make_configured_root(tmp_path)
    (root / ".env").write_text(
        "VCFOPS_PROD_HOST=ops.example.test\n"
        "VCFOPS_PROD_USER=admin\n"
        "VCFOPS_PROD_PASSWORD=\n"
    )
    exists, profiles, note = inspect_credentials(root, environ={})
    assert exists and not note
    assert profiles[0].missing == ["VCFOPS_PROD_PASSWORD"]
    text = "\n".join(collect(root, fake_git()))
    assert "profile 'prod' is incomplete" in text
    assert "profiles ready" not in text


def test_empty_quoted_value_is_missing(tmp_path):
    root = make_configured_root(tmp_path)
    (root / ".env").write_text(
        "VCFOPS_PROD_HOST=ops.example.test\n"
        "VCFOPS_PROD_USER=admin\n"
        'VCFOPS_PROD_PASSWORD=""\n'
    )
    _, profiles, _ = inspect_credentials(root, environ={})
    assert profiles[0].missing == ["VCFOPS_PROD_PASSWORD"]


def test_empty_exported_value_is_missing(tmp_path):
    root = make_configured_root(tmp_path)
    (root / ".env").unlink()
    environ = {
        "VCFOPS_PROD_HOST": "ops.example.test",
        "VCFOPS_PROD_USER": "admin",
        "VCFOPS_PROD_PASSWORD": "   ",  # whitespace only
    }
    _, profiles, _ = inspect_credentials(root, environ=environ)
    assert profiles[0].missing == ["VCFOPS_PROD_PASSWORD"]


# ---------------------------------------------------------------------------
# Codex PR #93: parent-directory .env, venv deps, tracking remote, JAR set
# ---------------------------------------------------------------------------

def test_env_file_in_parent_directory_is_honored(tmp_path):
    """_env.load_dotenv walks upward, so a .env above the repo root is a
    supported setup and must not read as unconfigured."""
    root = make_configured_root(tmp_path)
    (root / ".env").unlink()
    (tmp_path / ".env").write_text(
        "VCFOPS_PROD_HOST=ops.example.test\n"
        "VCFOPS_PROD_USER=admin\n"
        f"VCFOPS_PROD_PASSWORD={FAKE_SECRET}\n"
    )
    assert find_env_file(root) == tmp_path / ".env"
    lines = collect(root, fake_git())
    assert len(lines) == 1
    assert lines[0].startswith("doctor: all green")
    assert FAKE_SECRET not in lines[0]


def install_venv_python(root: Path, script: str = "") -> Path:
    """Put an executable at <root>/.venv/bin/python3.

    Default: a symlink to the real interpreter running the suite. With
    `script`, a shell stub whose stdout the probe must cope with.
    """
    bindir = root / ".venv" / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    target = bindir / "python3"
    if script:
        target.write_text(script)
        target.chmod(0o755)
    else:
        target.symlink_to(sys.executable)
    return target


def test_deps_are_checked_in_the_repo_venv(tmp_path):
    """Claude may run outside the venv the concierge created; deps that
    live only in <root>/.venv must count as present."""
    root = make_configured_root(tmp_path)
    vpy = install_venv_python(root)
    assert venv_python(root) == vpy
    # Current interpreter has nothing; the venv (the real interpreter
    # running this suite) has everything. Intersection: nothing missing.
    env = inspect_environment(root, check_import=lambda n: False)
    assert env.missing_modules == []
    # Repo-relative, never the absolute path (issue #96 item 3).
    assert env.checked_interpreter == "current + .venv/bin/python3"
    assert str(vpy.parent) not in env.checked_interpreter


def test_ambient_deps_survive_a_depless_venv(tmp_path):
    """BLOCKING regression guard: a bare `python -m venv --without-pip`
    next to a fully provisioned system python must NOT produce
    FIRST-RUN DETECTED. Missing means missing in BOTH interpreters."""
    root = make_configured_root(tmp_path)
    # A venv python that reports every module missing.
    install_venv_python(
        root,
        "#!/bin/sh\necho 'requests yaml jmespath'\n",
    )
    env = inspect_environment(root)  # ambient interpreter has the deps
    assert env.missing_modules == []
    assert not is_first_run(root, env, env_file_exists=True)
    lines = collect(root, fake_git(), imports_ok=None)
    assert len(lines) == 1
    assert lines[0].startswith("doctor: all green")


def test_probe_rejects_unexpected_child_stdout(tmp_path):
    """BLOCKING regression guard: tokens the child prints that are not
    module names we asked about must not become fabricated 'missing
    modules' (nor a giant CHECKLIST-JSON dump)."""
    root = make_configured_root(tmp_path)
    install_venv_python(
        root,
        "#!/bin/sh\necho 'Warning: nonstandard site dir'\necho 'yaml'\n",
    )
    env = inspect_environment(root, check_import=lambda n: False)
    # Probe rejected wholesale, so we fall back to the current
    # interpreter's answer rather than inventing names.
    assert env.checked_interpreter == "current"
    for token in ("Warning:", "nonstandard", "site", "dir"):
        assert token not in env.missing_modules


def test_probe_rejects_flood_of_child_stdout(tmp_path):
    root = make_configured_root(tmp_path)
    install_venv_python(
        root,
        "#!/bin/sh\npython3 -c \"print('junk ' * 50000)\"\n",
    )
    env = inspect_environment(root, check_import=lambda n: False)
    assert env.checked_interpreter == "current"
    assert all(m in ("requests", "yaml", "jmespath") for m in env.missing_modules)
    # And nothing enormous reaches the checklist.
    checklist = build_checklist(root, env, True, [], {})
    assert len(json.dumps({"items": checklist})) < 4000


def test_venv_probe_falls_back_when_interpreter_is_broken(tmp_path):
    root = make_configured_root(tmp_path)
    install_venv_python(root, "#!/nonexistent/interpreter\n")
    env = inspect_environment(root, check_import=lambda n: False)
    assert env.checked_interpreter == "current"


def test_no_venv_uses_current_interpreter(tmp_path):
    root = make_configured_root(tmp_path)
    env = inspect_environment(root)  # .venv exists but holds no interpreter
    assert env.checked_interpreter == "current"


def test_missing_module_line_names_the_interpreter(tmp_path):
    """jmespath alone missing is not first-run, so the delta line shows,
    and it must say which interpreter was consulted."""
    root = make_configured_root(tmp_path)
    lines = collect(root, fake_git(), imports_ok=None,
                    check_import=lambda n: n != "jmespath")
    text = "\n".join(lines)
    assert "missing python module(s): jmespath" in text
    assert "[checked: current]" in text


def test_fetches_the_configured_tracking_remote(tmp_path):
    """Fetching a hardcoded 'origin' cannot refresh a checkout tracking
    upstream/main, which would yield a stale comparison."""
    root = make_configured_root(tmp_path)
    fetched: List[str] = []
    git = fake_git(
        remotes="origin\nupstream\n",
        tracking_remote="upstream",
        upstream="upstream/main\n",
        fetch_log=fetched,
    )
    lines = collect(root, git)
    assert fetched == ["upstream"]
    assert "upstream/main" in lines[0]


def test_falls_back_to_origin_when_no_tracking_remote_configured(tmp_path):
    root = make_configured_root(tmp_path)
    fetched: List[str] = []
    git = fake_git(tracking_remote="", fetch_log=fetched)
    collect(root, git)
    assert fetched == ["origin"]


def test_untracked_only_work_counts_as_dirty(tmp_path):
    """--untracked-files=no would call this tree clean and offer a pull
    while the user has local work sitting in it."""
    root = make_configured_root(tmp_path)
    behind = "\x01ddd4444\x02upstream fix\n\nsrc/<fixture-a>.py\n"

    def git(args, timeout=0):
        args = list(args)
        if args[0] == "status":
            assert "--untracked-files=no" not in args
            return 0, "?? scratch-notes.md\n"  # untracked only
        return fake_git(behind_log=behind)(args, timeout)

    text = "\n".join(collect(root, git))
    assert "uncommitted or untracked changes" in text
    assert "git pull --ff-only" not in text


def test_tier1_runtime_needs_adapter_jar_and_lib_jars(tmp_path):
    root = make_configured_root(tmp_path)
    runtime = root / "src" / "vcfops_managementpacks" / "adapter_runtime"

    # A Tier 2 SDK jar alone must NOT satisfy the Tier 1 runtime check.
    (runtime / "mpb_adapter3.jar").unlink()
    (runtime / "lib" / "mpb_adapter-9.0.1.jar").unlink()
    (runtime / "vrops-adapters-sdk-2.2.jar").write_bytes(b"jar")
    env = inspect_environment(root, lambda n: True)
    assert env.missing_jars == [
        "adapter_runtime/mpb_adapter3.jar",
        "adapter_runtime/lib/*.jar",
    ]
    text = "\n".join(collect(root, fake_git()))
    assert "ADAPTER_JAR_GAP" in text and "LIB_GAP" in text

    # adapter jar present but no lib jars: still incomplete (LIB_GAP).
    (runtime / "mpb_adapter3.jar").write_bytes(b"jar")
    env = inspect_environment(root, lambda n: True)
    assert env.missing_jars == ["adapter_runtime/lib/*.jar"]

    # Both present: complete.
    (runtime / "lib" / "mpb_adapter-9.0.1.jar").write_bytes(b"jar")
    env = inspect_environment(root, lambda n: True)
    assert env.missing_jars == []
    assert env.jars_present


# ---------------------------------------------------------------------------
# Log parsing
# ---------------------------------------------------------------------------

def test_parse_commit_log():
    raw = (
        "\x01abc1234\x02first subject\n\nsrc/<fixture-a>.py\nsrc/<fixture-b>.py\n"
        "\x01def5678\x02second subject\n\ndocsfile.md\n"
    )
    commits = _parse_commit_log(raw)
    assert [c.sha for c in commits] == ["abc1234", "def5678"]
    assert commits[0].paths == ["src/<fixture-a>.py", "src/<fixture-b>.py"]
    assert commits[1].subject == "second subject"


def test_commit_dominant_area():
    c = Commit(sha="x", subject="s",
               paths=["src/<fixture-a>.py", "src/<fixture-b>.py", "content/dashboards/<fixture>.yaml"])
    assert c.area == "tooling fixes"


# ---------------------------------------------------------------------------
# Corrupt-input hardening (review B-1): always exit 0, never traceback
# ---------------------------------------------------------------------------

def test_non_utf8_env_degrades_not_crashes(tmp_path):
    root = make_configured_root(tmp_path)
    # A Windows editor saving UTF-16: invalid UTF-8 from byte 0 (BOM).
    (root / ".env").write_bytes("VCFOPS_PROD_HOST=h\n".encode("utf-16"))
    lines = collect(root, fake_git())
    text = "\n".join(lines)
    assert ".env exists but could not be read" in text
    assert "UnicodeDecodeError" in text


@not_root
def test_unreadable_env_degrades_not_crashes(tmp_path):
    root = make_configured_root(tmp_path)
    (root / ".env").chmod(0o000)
    try:
        lines = collect(root, fake_git())
    finally:
        (root / ".env").chmod(0o600)
    text = "\n".join(lines)
    assert ".env exists but could not be read" in text
    assert "PermissionError" in text


def test_non_utf8_bootstrap_status_degrades_not_crashes(tmp_path):
    root = make_configured_root(tmp_path)
    (root / ".bootstrap-status").write_bytes(b"\xff\xfe\x00garbage")
    lines = collect(root, fake_git())
    text = "\n".join(lines)
    assert ".bootstrap-status exists but could not be read" in text


@not_root
def test_unreadable_bootstrap_status_degrades_not_crashes(tmp_path):
    root = make_configured_root(tmp_path)
    status = root / ".bootstrap-status"
    status.write_text("x\n")
    status.chmod(0o000)
    try:
        lines = collect(root, fake_git())
    finally:
        status.chmod(0o600)
    assert ".bootstrap-status exists but could not be read" in "\n".join(lines)


def test_non_numeric_failed_count_degrades_not_crashes(tmp_path):
    root = make_configured_root(tmp_path)
    (root / ".bootstrap-status").write_text(
        f"{ts()} bootstrap_references cloned=1 updated=0 failed=oops failures=-\n"
    )
    lines = collect(root, fake_git())
    text = "\n".join(lines)
    assert "unparseable" in text
    assert "bootstrap_references" in text


def test_non_numeric_failed_count_in_first_run_checklist(tmp_path):
    root = make_configured_root(tmp_path)
    (root / ".env").unlink()  # first-run path
    # Both scripts recorded, so the unparseable count is the only problem.
    (root / ".bootstrap-status").write_text(
        f"{ts()} bootstrap_references cloned=1 updated=0 failed=oops failures=-\n"
        f"{ts()} bootstrap_managed_paks cloned=1 updated=0 failed=0 failures=-\n"
    )
    lines = collect(root, fake_git())
    json_line = next(ln for ln in lines if ln.startswith("CHECKLIST-JSON: "))
    payload = json.loads(json_line[len("CHECKLIST-JSON: "):])
    boot = next(i for i in payload["items"] if i["id"] == "bootstrap-clones")
    assert boot["status"] == "unknown"
    assert "unparseable" in boot["detail"]


def test_git_runner_catches_unicode_decode_error(monkeypatch):
    """W-3: git output that will not decode must degrade the upstream
    section only, not lose the whole preflight."""
    import vcfops_common.doctor as doctor_mod

    def boom(*a, **kw):
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")

    monkeypatch.setattr(doctor_mod.subprocess, "run", boom)
    runner = doctor_mod._make_git_runner(Path("/nonexistent"))
    assert runner(["log"], 1) == (1, "")


def test_undecodable_git_output_keeps_other_sections(tmp_path, monkeypatch):
    import vcfops_common.doctor as doctor_mod

    def boom(*a, **kw):
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")

    monkeypatch.setattr(doctor_mod.subprocess, "run", boom)
    root = make_configured_root(tmp_path)
    (root / ".env").write_text("VCFOPS_QA_HOST=h\n")  # incomplete profile
    (root / ".bootstrap-status").write_text(
        f"{ts()} bootstrap_references cloned=0 updated=0 failed=1 failures=dell\n"
    )
    lines = []
    # git=None so the REAL hardened runner is exercised.
    rc = doctor_mod.run_doctor(
        root, check_import=lambda n: True, environ={}, out=lines.append
    )
    text = "\n".join(lines)
    assert rc == 0
    # Upstream section degraded...
    assert "git not available; upstream check skipped" in text
    # ...but credentials and bootstrap health still reported.
    assert "profile 'qa' is incomplete" in text
    assert "bootstrap_references: 1 clone/update failure(s): dell" in text


def test_main_catch_all_exits_zero_on_internal_error(monkeypatch, capsys):
    import vcfops_common.doctor as doctor_mod

    def boom():
        raise RuntimeError("synthetic bug")

    monkeypatch.setattr(doctor_mod, "run_doctor", boom)
    rc = doctor_mod.main([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "doctor: internal error (RuntimeError)" in out


# ---------------------------------------------------------------------------
# Export-only credentials (review W-1)
# ---------------------------------------------------------------------------

def test_export_only_credentials_are_not_first_run(tmp_path):
    root = make_configured_root(tmp_path)
    (root / ".env").unlink()  # no file at all; exports only
    environ = {
        "VCFOPS_PROD_HOST": "ops.example.test",
        "VCFOPS_PROD_USER": "admin",
        "VCFOPS_PROD_PASSWORD": FAKE_SECRET,
    }
    lines = collect(root, fake_git(), environ=environ)
    text = "\n".join(lines)
    assert "FIRST-RUN DETECTED" not in text
    assert len(lines) == 1
    assert lines[0].startswith("doctor: all green")
    assert "prod" in lines[0]


def test_environ_values_never_printed(tmp_path):
    root = make_configured_root(tmp_path)
    environ = {"VCFOPS_QA_HOST": FAKE_SECRET}  # value must never surface
    lines = collect(root, fake_git(), environ=environ)
    text = "\n".join(lines)
    assert FAKE_SECRET not in text
    assert "VCFOPS_QA_PASSWORD" in text  # qa incomplete: names only


# ---------------------------------------------------------------------------
# Diverged branch (review W-2): never offer a pull that cannot succeed
# ---------------------------------------------------------------------------

def test_diverged_branch_suppresses_ff_pull_offer(tmp_path):
    root = make_configured_root(tmp_path)
    behind = "\x01ddd4444\x02upstream fix\n\nsrc/<fixture-a>.py\n"
    ahead = "\x01aaa1111\x02local fix\n\nsrc/<fixture-b>.py\n"
    lines = collect(root, fake_git(behind_log=behind, ahead_log=ahead))
    text = "\n".join(lines)
    assert "git pull --ff-only" not in text
    assert "diverged" in text
    assert "do not pull blindly" in text


# ---------------------------------------------------------------------------
# Issue #90: argv, diverged+dirty shadowing, absurd failed counts
# ---------------------------------------------------------------------------

def test_help_prints_usage_not_the_report(capsys):
    import vcfops_common.doctor as doctor_mod

    rc = doctor_mod.main(["--help"])
    out = capsys.readouterr().out
    assert rc == 0
    assert out.startswith("usage: python -m vcfops_common doctor")
    assert "doctor: all green" not in out
    assert "FIRST-RUN DETECTED" not in out


def test_stray_argument_is_reported_not_silently_ignored(monkeypatch, capsys):
    import vcfops_common.doctor as doctor_mod

    monkeypatch.setattr(doctor_mod, "run_doctor", lambda: 0)
    rc = doctor_mod.main(["--verbose"])
    err = capsys.readouterr().err
    assert rc == 0  # hook contract outranks argument strictness
    assert "ignoring 1 unrecognized argument(s): --verbose" in err


def test_no_argv_still_runs_the_report(monkeypatch, capsys):
    import vcfops_common.doctor as doctor_mod

    ran = []
    monkeypatch.setattr(doctor_mod, "run_doctor", lambda: ran.append(True) or 0)
    assert doctor_mod.main([]) == 0
    assert ran == [True]
    assert capsys.readouterr().err == ""


def test_diverged_and_dirty_reports_both(tmp_path):
    """A dirty tree must not shadow the divergence warning: 'resolve them
    before pulling' alone implies a pull is the next step, which is wrong
    on a diverged branch."""
    root = make_configured_root(tmp_path)
    behind = "\x01ddd4444\x02upstream fix\n\nsrc/<fixture-a>.py\n"
    ahead = "\x01aaa1111\x02local fix\n\nsrc/<fixture-b>.py\n"
    lines = collect(
        root, fake_git(behind_log=behind, ahead_log=ahead, dirty=True)
    )
    text = "\n".join(lines)
    assert "diverged" in text
    assert "do not pull blindly" in text
    assert "uncommitted or untracked changes" in text
    assert "git pull --ff-only" not in text


def test_behind_and_dirty_only_still_warns_about_the_tree(tmp_path):
    root = make_configured_root(tmp_path)
    behind = "\x01ddd4444\x02upstream fix\n\nsrc/<fixture-a>.py\n"
    lines = collect(root, fake_git(behind_log=behind, dirty=True))
    text = "\n".join(lines)
    assert "uncommitted or untracked changes" in text
    assert "diverged" not in text
    assert "git pull --ff-only" not in text


def test_negative_failed_count_is_treated_as_corrupt(tmp_path):
    root = make_configured_root(tmp_path)
    (root / ".bootstrap-status").write_text(
        f"{ts()} bootstrap_references cloned=1 updated=0 failed=-5 failures=-\n"
        f"{ts()} bootstrap_managed_paks cloned=1 updated=0 failed=0 failures=-\n"
    )
    lines = collect(root, fake_git())
    text = "\n".join(lines)
    assert "unparseable" in text
    assert "-5 clone/update failure(s)" not in text


def test_absurd_failed_count_is_treated_as_corrupt(tmp_path):
    root = make_configured_root(tmp_path)
    (root / ".bootstrap-status").write_text(
        f"{ts()} bootstrap_references cloned=1 updated=0 failed=999999999 failures=-\n"
        f"{ts()} bootstrap_managed_paks cloned=1 updated=0 failed=0 failures=-\n"
    )
    lines = collect(root, fake_git())
    text = "\n".join(lines)
    assert "unparseable" in text
    assert "999999999 clone/update failure(s)" not in text


def test_plausible_failed_count_still_reported(tmp_path):
    root = make_configured_root(tmp_path)
    (root / ".bootstrap-status").write_text(
        f"{ts()} bootstrap_references cloned=1 updated=0 failed=2 failures=a,b\n"
        f"{ts()} bootstrap_managed_paks cloned=1 updated=0 failed=0 failures=-\n"
    )
    lines = collect(root, fake_git())
    assert "bootstrap_references: 2 clone/update failure(s): a,b" in "\n".join(lines)


# ---------------------------------------------------------------------------
# Issue #92: corrupt line must not become a phantom script
# ---------------------------------------------------------------------------

def test_corrupt_line_does_not_create_a_phantom_script(tmp_path):
    root = make_configured_root(tmp_path)
    (root / ".bootstrap-status").write_text(
        "GARBAGE PARTIAL LINE cloned=1\n"
        f"{ts()} bootstrap_references cloned=1 updated=0 failed=0 failures=-\n"
        f"{ts()} bootstrap_managed_paks cloned=1 updated=0 failed=0 failures=-\n"
    )
    status, note = read_bootstrap_status(root)
    assert note == ""
    assert set(status) == set(KNOWN_BOOTSTRAP_SCRIPTS)
    assert "PARTIAL" not in status
    # And the corrupt line earns no report line of its own.
    lines = collect(root, fake_git())
    assert len(lines) == 1
    assert lines[0].startswith("doctor: all green")


def test_non_bootstrap_script_names_are_rejected(tmp_path):
    root = make_configured_root(tmp_path)
    (root / ".bootstrap-status").write_text(
        f"{ts()} BOOTSTRAP_REFERENCES cloned=1 updated=0 failed=0 failures=-\n"
        f"{ts()} bootstrap-references cloned=1 updated=0 failed=0 failures=-\n"
        f"{ts()} ../../etc/passwd cloned=1 updated=0 failed=0 failures=-\n"
    )
    status, _ = read_bootstrap_status(root)
    assert status == {}


# ---------------------------------------------------------------------------
# Issue #94: clock skew, echo truncation, checklist age
# ---------------------------------------------------------------------------

def test_future_timestamp_reports_clock_skew(tmp_path):
    root = make_configured_root(tmp_path)
    (root / ".bootstrap-status").write_text(
        f"{ts(hours_ago=-72)} bootstrap_references cloned=1 updated=0 failed=0 failures=-\n"
        f"{ts()} bootstrap_managed_paks cloned=1 updated=0 failed=0 failures=-\n"
    )
    text = "\n".join(collect(root, fake_git()))
    assert "records a run in the future" in text
    assert "clock may be wrong" in text


def test_small_future_skew_is_tolerated(tmp_path):
    """Ordinary NTP/timezone jitter must not produce a delta line."""
    root = make_configured_root(tmp_path)
    (root / ".bootstrap-status").write_text(
        f"{ts(hours_ago=-0.2)} bootstrap_references cloned=1 updated=0 failed=0 failures=-\n"
        f"{ts()} bootstrap_managed_paks cloned=1 updated=0 failed=0 failures=-\n"
    )
    lines = collect(root, fake_git())
    assert len(lines) == 1
    assert lines[0].startswith("doctor: all green")


def test_garbage_timestamp_is_truncated_in_the_report(tmp_path):
    root = make_configured_root(tmp_path)
    garbage = "X" * 5000
    (root / ".bootstrap-status").write_text(
        f"{garbage} bootstrap_references cloned=1 updated=0 failed=0 failures=-\n"
        f"{ts()} bootstrap_managed_paks cloned=1 updated=0 failed=0 failures=-\n"
    )
    text = "\n".join(collect(root, fake_git()))
    assert "unparseable timestamp" in text
    assert garbage not in text
    assert len(text) < 1500


def test_garbage_failures_field_is_truncated(tmp_path):
    root = make_configured_root(tmp_path)
    garbage = "y" * 5000
    (root / ".bootstrap-status").write_text(
        f"{ts()} bootstrap_references cloned=0 updated=0 failed=1 failures={garbage}\n"
        f"{ts()} bootstrap_managed_paks cloned=1 updated=0 failed=0 failures=-\n"
    )
    text = "\n".join(collect(root, fake_git()))
    assert "1 clone/update failure(s)" in text
    assert garbage not in text
    assert len(text) < 1500


def test_first_run_checklist_flags_an_ancient_bootstrap_run(tmp_path):
    root = make_configured_root(tmp_path)
    old = ts(hours_ago=100 * 24)  # a run recorded 100 days ago
    (root / ".bootstrap-status").write_text(
        f"{old} bootstrap_references cloned=1 updated=0 failed=0 failures=-\n"
        f"{old} bootstrap_managed_paks cloned=1 updated=0 failed=0 failures=-\n"
    )
    bootstrap, _ = read_bootstrap_status(root)
    env = inspect_environment(root, lambda n: True)
    checklist = build_checklist(root, env, True, [], bootstrap)
    boot = next(i for i in checklist if i["id"] == "bootstrap-clones")
    assert boot["status"] != "ok"
    assert "stale" in boot["detail"]


def test_first_run_checklist_flags_a_future_bootstrap_run(tmp_path):
    root = make_configured_root(tmp_path)
    future = ts(hours_ago=-72)
    (root / ".bootstrap-status").write_text(
        f"{future} bootstrap_references cloned=1 updated=0 failed=0 failures=-\n"
        f"{future} bootstrap_managed_paks cloned=1 updated=0 failed=0 failures=-\n"
    )
    bootstrap, _ = read_bootstrap_status(root)
    env = inspect_environment(root, lambda n: True)
    checklist = build_checklist(root, env, True, [], bootstrap)
    boot = next(i for i in checklist if i["id"] == "bootstrap-clones")
    assert boot["status"] == "unknown"
    assert "clock" in boot["detail"]


def test_first_run_checklist_ok_on_a_fresh_bootstrap_run(tmp_path):
    root = make_configured_root(tmp_path)  # fresh status written by helper
    bootstrap, _ = read_bootstrap_status(root)
    env = inspect_environment(root, lambda n: True)
    checklist = build_checklist(root, env, True, [], bootstrap)
    boot = next(i for i in checklist if i["id"] == "bootstrap-clones")
    assert boot["status"] == "ok"


# ---------------------------------------------------------------------------
# Issue #96: no absolute path in the attention line
# ---------------------------------------------------------------------------

def test_no_absolute_venv_path_in_the_missing_module_line(tmp_path):
    """The venv interpreter is named repo-relatively, so no absolute
    filesystem path reaches session context."""
    root = make_configured_root(tmp_path)
    install_venv_python(root, "#!/bin/sh\necho 'jmespath'\n")
    lines = collect(root, fake_git(), check_import=lambda n: n != "jmespath")
    text = "\n".join(lines)
    assert "missing python module(s): jmespath" in text
    assert "[checked: current + .venv/bin/python3]" in text
    assert str(root) not in text


def test_probe_seam_is_gone(tmp_path):
    """The unused keyword-only probe= seam was dropped (issue #96 item 1);
    the venv probe is exercised through real child processes instead."""
    import inspect as _inspect

    params = _inspect.signature(inspect_environment).parameters
    assert "probe" not in params


# ---------------------------------------------------------------------------
# Framework review round 1 on this batch: W-3, W-4, N-2, N-5
# ---------------------------------------------------------------------------

def test_long_script_name_does_not_flood_session_context(tmp_path):
    """W-3: the script-name field is as untrusted as the rest of the line.
    A 50,000-character field 2 must not reach session context."""
    root = make_configured_root(tmp_path)
    huge = "bootstrap_" + "a" * 50_000
    (root / ".bootstrap-status").write_text(
        f"{ts()} {huge} cloned=1 updated=0 failed=1 failures=x\n"
    )
    lines = collect(root, fake_git())
    text = "\n".join(lines)
    assert len(text) < 2000
    assert "a" * 200 not in text


def test_known_bootstrap_scripts_all_match_the_name_guard():
    """W-4: the two gates must agree, or a known script's line is dropped
    at parse time and then reported 'no run recorded' forever."""
    import vcfops_common.doctor as doctor_mod

    for name in KNOWN_BOOTSTRAP_SCRIPTS:
        assert doctor_mod._SCRIPT_NAME_RE.match(name), name


def test_script_names_with_digits_are_accepted(tmp_path):
    """W-4: `bootstrap_scg_v9` is this repo's naming house style; a
    future script must not be silently dropped."""
    root = make_configured_root(tmp_path)
    (root / ".bootstrap-status").write_text(
        f"{ts()} bootstrap_references cloned=1 updated=0 failed=0 failures=-\n"
        f"{ts()} bootstrap_managed_paks cloned=1 updated=0 failed=0 failures=-\n"
        f"{ts()} bootstrap_scg_v9 cloned=1 updated=0 failed=0 failures=-\n"
    )
    status, _ = read_bootstrap_status(root)
    assert "bootstrap_scg_v9" in status


def test_sh_suffixed_script_name_records_the_same_script(tmp_path):
    """W-4: `bootstrap_references.sh` in field 2 is the same script as
    `bootstrap_references`, not a second, permanently-unrecorded one."""
    root = make_configured_root(tmp_path)
    (root / ".bootstrap-status").write_text(
        f"{ts()} bootstrap_references.sh cloned=1 updated=0 failed=0 failures=-\n"
        f"{ts()} bootstrap_managed_paks cloned=1 updated=0 failed=0 failures=-\n"
    )
    status, _ = read_bootstrap_status(root)
    assert set(status) == set(KNOWN_BOOTSTRAP_SCRIPTS)
    assert unrecorded_bootstrap_scripts(status) == []
    lines = collect(root, fake_git())
    assert len(lines) == 1
    assert lines[0].startswith("doctor: all green")


def test_argv_echo_never_reproduces_a_value(monkeypatch, capsys):
    """N-2 (upgraded): this module promises credential values are never
    printed; argv is no exception."""
    import vcfops_common.doctor as doctor_mod

    monkeypatch.setattr(doctor_mod, "run_doctor", lambda: 0)
    rc = doctor_mod.main([f"--password={FAKE_SECRET}", FAKE_SECRET, "--verbose"])
    err = capsys.readouterr().err
    assert rc == 0
    assert FAKE_SECRET not in err
    assert "--password=<redacted>" in err  # the NAME still reaches the user
    assert "--verbose" in err
    assert "<value>" in err                # bare positional, name-less


def test_checklist_names_failures_even_on_a_stale_record(tmp_path):
    """N-5: an old record that also carries failures must not report
    staleness only; the failure count is the actionable half."""
    root = make_configured_root(tmp_path)
    old = ts(hours_ago=100 * 24)
    (root / ".bootstrap-status").write_text(
        f"{old} bootstrap_references cloned=0 updated=0 failed=2 failures=a,b\n"
        f"{old} bootstrap_managed_paks cloned=1 updated=0 failed=0 failures=-\n"
    )
    bootstrap, _ = read_bootstrap_status(root)
    env = inspect_environment(root, lambda n: True)
    checklist = build_checklist(root, env, True, [], bootstrap)
    boot = next(i for i in checklist if i["id"] == "bootstrap-clones")
    assert boot["status"] == "fail"
    assert "2 clone/update failure(s)" in boot["detail"]
    assert "stale" in boot["detail"]

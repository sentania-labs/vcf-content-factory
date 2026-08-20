"""Tests for the bootstrap-v2 Phase 1/1b preflight doctor.

Fast, no network, no real git: every git interaction goes through an
injected fake runner. RULE-008 is asserted directly: secret VALUES from
a synthetic .env must never appear in doctor output.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from vcfops_common.doctor import (
    GREETING,
    STALE_AFTER_HOURS,
    TIMESTAMP_KEY,
    Commit,
    _safe_age_hours,
    classify_commit,
    classify_path,
    inspect_credentials,
    is_first_run,
    inspect_environment,
    read_bootstrap_status,
    run_doctor,
    _parse_commit_log,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_SECRET = "synthetic-not-a-real-password-42"


def make_configured_root(tmp_path: Path) -> Path:
    """A tmp repo root that looks fully configured."""
    (tmp_path / ".env").write_text(
        "VCFOPS_PROD_HOST=ops.example.test\n"
        "VCFOPS_PROD_USER=admin\n"
        f"VCFOPS_PROD_PASSWORD={FAKE_SECRET}\n"
    )
    (tmp_path / ".venv").mkdir()
    runtime = tmp_path / "src" / "vcfops_managementpacks" / "adapter_runtime"
    runtime.mkdir(parents=True)
    (runtime / "mpb_adapter3.jar").write_bytes(b"jar")
    return tmp_path


def fake_git(*, behind_log: str = "", ahead_log: str = "", dirty: bool = False,
             fetch_rc: int = 0):
    def run(args, timeout=0):
        args = list(args)
        if args[:2] == ["rev-parse", "--git-dir"]:
            return 0, ".git\n"
        if args[0] == "fetch":
            return fetch_rc, ""
        if args == ["rev-parse", "--abbrev-ref", "@{upstream}"]:
            return 0, "origin/main\n"
        if args[0] == "status":
            return 0, (" M src/<fixture-a>.py\n" if dirty else "")
        if args[0] == "log":
            rng = args[-1]
            if rng.startswith("HEAD.."):
                return 0, behind_log
            return 0, ahead_log
        return 0, ""
    return run


def collect(root, git, imports_ok=True, environ=None):
    lines = []
    run_doctor(
        root,
        git=git,
        check_import=lambda name: imports_ok,
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
    assert "uncommitted changes" in text
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
    )
    status, _ = read_bootstrap_status(root)
    assert status["bootstrap_references"][TIMESTAMP_KEY] == stamp
    assert "stale" not in "\n".join(collect(root, fake_git()))


def test_missing_bootstrap_status_is_silent_when_configured(tmp_path):
    root = make_configured_root(tmp_path)
    lines = collect(root, fake_git())
    assert len(lines) == 1  # still the green line


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
    (root / ".bootstrap-status").write_text(
        f"{ts()} bootstrap_references cloned=1 updated=0 failed=oops failures=-\n"
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
        "VCFOPS_PROD_HOST": "",
        "VCFOPS_PROD_USER": "",
        "VCFOPS_PROD_PASSWORD": "",
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

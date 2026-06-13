# Tests for scripts/validate-content.py — the PostToolUse (Write|Edit) hook
# that runs the matching vcfops_<type> validate CLI on content/ files.
#
# HERMETIC DESIGN: these tests never touch the real content/ corpus.
# Each test builds a minimal fixture tree under pytest's tmp_path and
# points the hook at it via VCFCF_CONTENT_ROOT.  The hook uses that env
# var as its workspace root, so all validator subprocess calls resolve
# their relative content/… paths against the temp tree.
#
# Because the tests no longer write into the real corpus they are safe to
# run on any xdist worker without coordination — the xdist_group mark has
# been removed.  Only `slow` is kept (each test spawns a full validator
# subprocess).
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.slow

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(WORKSPACE_ROOT, "scripts", "validate-content.py")

# Real content dirs — used only as read-only sources for copying valid fixtures.
_REAL_ALERTS_DIR = os.path.join(WORKSPACE_ROOT, "content", "alerts")
_REAL_MANAGEMENTPACKS_DIR = os.path.join(WORKSPACE_ROOT, "content", "managementpacks")
_REAL_VIEWS_DIR = os.path.join(WORKSPACE_ROOT, "content", "views")

REFERENCE_VALID_ALERT = os.path.join(_REAL_ALERTS_DIR, "vm_cpu_usage_alert.yaml")
REFERENCE_VALID_MP = os.path.join(_REAL_MANAGEMENTPACKS_DIR, "cloudflare.yaml")
REFERENCE_VALID_VIEW = os.path.join(_REAL_VIEWS_DIR, "cluster_capacity_breakdown.yaml")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_content_tree(tmp_path: Path) -> Path:
    """Create a minimal content/ tree under tmp_path that the validators accept.

    The tree mirrors the real layout that each validator expects:
      <root>/content/alerts/
      <root>/content/symptoms/
      <root>/content/recommendations/
      <root>/content/managementpacks/
      <root>/content/views/
      <root>/content/dashboards/
      <root>/content/supermetrics/
      <root>/content/customgroups/

    All real content files are copied in so cross-reference validators
    (alert→symptom, view→supermetric) continue to pass.  The SDK-adapter
    subtree is omitted — validators skip it silently.
    """
    root = tmp_path / "workspace"
    real_content = Path(WORKSPACE_ROOT) / "content"

    # Copy the entire content/ tree except sdk-adapters (large, unneeded).
    for subdir in real_content.iterdir():
        if subdir.name == "sdk-adapters":
            continue
        dest = root / "content" / subdir.name
        if subdir.is_dir():
            shutil.copytree(str(subdir), str(dest))

    # Also copy vcfops_* packages so the subprocess Python path resolves them.
    # The hook uses sys.executable with -m, which picks up the installed
    # packages from the current environment, so no extra copying is needed —
    # but we do need vcfops_* to be importable (they are, via the real env).

    return root


def run_hook(stdin_bytes: bytes, *, workspace_root: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["VCFCF_CONTENT_ROOT"] = workspace_root
    # The hook subprocess resolves its CWD to workspace_root (the temp dir),
    # which does not have vcfops_* on sys.path.  Ensure the real workspace —
    # where the packages live — is always on PYTHONPATH so the -m flag finds
    # them regardless of cwd.
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = WORKSPACE_ROOT + (os.pathsep + existing if existing else "")
    return subprocess.run(
        [sys.executable, HOOK],
        input=stdin_bytes,
        capture_output=True,
        timeout=120,
        env=env,
    )


def hook_input(file_path: str) -> bytes:
    return json.dumps({"tool_input": {"file_path": file_path}}).encode()


# ---------------------------------------------------------------------------
# Tests — alerts
# ---------------------------------------------------------------------------

def test_invalid_yaml_blocked_with_message(tmp_path):
    root = _build_content_tree(tmp_path)
    alerts_dir = root / "content" / "alerts"
    bad_file = alerts_dir / "test_bad_hook_alert.yaml"
    bad_file.write_text("bad: yaml: content: [unclosed")
    result = run_hook(hook_input(str(bad_file)), workspace_root=str(root))
    assert result.returncode == 0
    decision = json.loads(result.stdout)
    assert decision["decision"] == "block"
    assert "vcfops_alerts" in decision["reason"]


def test_valid_yaml_silent_pass(tmp_path):
    root = _build_content_tree(tmp_path)
    alerts_dir = root / "content" / "alerts"
    good_file = alerts_dir / "test_valid_hook_alert.yaml"
    shutil.copyfile(REFERENCE_VALID_ALERT, str(good_file))
    result = run_hook(hook_input(str(good_file)), workspace_root=str(root))
    assert result.returncode == 0
    assert result.stdout == b""


# ---------------------------------------------------------------------------
# Tests — managementpacks
# ---------------------------------------------------------------------------

def test_invalid_managementpack_yaml_blocked_with_message(tmp_path):
    root = _build_content_tree(tmp_path)
    mp_dir = root / "content" / "managementpacks"
    bad_file = mp_dir / "test_bad_hook_mp.yaml"
    bad_file.write_text("bad: yaml: content: [unclosed")
    result = run_hook(hook_input(str(bad_file)), workspace_root=str(root))
    assert result.returncode == 0
    decision = json.loads(result.stdout)
    assert decision["decision"] == "block"
    assert "vcfops_managementpacks" in decision["reason"]


def test_valid_managementpack_yaml_silent_pass(tmp_path):
    root = _build_content_tree(tmp_path)
    mp_dir = root / "content" / "managementpacks"
    good_file = mp_dir / "test_valid_hook_mp.yaml"
    shutil.copyfile(REFERENCE_VALID_MP, str(good_file))
    result = run_hook(hook_input(str(good_file)), workspace_root=str(root))
    assert result.returncode == 0
    assert result.stdout == b""


# ---------------------------------------------------------------------------
# Tests — views
# ---------------------------------------------------------------------------

def test_invalid_view_yaml_blocked_with_message(tmp_path):
    # Views validate whole-corpus via vcfops_dashboards, so a syntactically
    # broken file makes the loader fail regardless of which path triggered it.
    root = _build_content_tree(tmp_path)
    views_dir = root / "content" / "views"
    bad_file = views_dir / "test_bad_hook_view.yaml"
    bad_file.write_text("bad: yaml: content: [unclosed")
    result = run_hook(hook_input(str(bad_file)), workspace_root=str(root))
    assert result.returncode == 0
    decision = json.loads(result.stdout)
    assert decision["decision"] == "block"
    assert "vcfops_dashboards" in decision["reason"]


def test_valid_view_yaml_silent_pass(tmp_path):
    root = _build_content_tree(tmp_path)
    views_dir = root / "content" / "views"
    good_file = views_dir / "test_valid_hook_view.yaml"
    shutil.copyfile(REFERENCE_VALID_VIEW, str(good_file))
    result = run_hook(hook_input(str(good_file)), workspace_root=str(root))
    assert result.returncode == 0
    assert result.stdout == b""


# ---------------------------------------------------------------------------
# Tests — path routing
# ---------------------------------------------------------------------------

def test_non_content_path_ignored(tmp_path):
    root = _build_content_tree(tmp_path)
    # A path outside content/ must be silently ignored regardless of root.
    path = os.path.join(WORKSPACE_ROOT, "scripts", "something.py")
    result = run_hook(hook_input(path), workspace_root=str(root))
    assert result.returncode == 0
    assert result.stdout == b""


def test_garbage_stdin_fails_open(tmp_path):
    root = _build_content_tree(tmp_path)
    result = run_hook(b"not json at all", workspace_root=str(root))
    assert result.returncode == 0
    assert result.stdout == b""

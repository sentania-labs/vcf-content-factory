# Tests for scripts/validate-content.py — the PostToolUse (Write|Edit) hook
# that runs the matching vcfops_<type> validate CLI on content/ files.
#
# The hook derives its workspace root from its own location, so temp content
# files must live under the real <workspace>/content/ tree for the hook to
# engage; tempfile keeps names unique and try/finally keeps the tree clean.
import json
import os
import shutil
import subprocess
import sys
import tempfile

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(WORKSPACE_ROOT, "scripts", "validate-content.py")
ALERTS_DIR = os.path.join(WORKSPACE_ROOT, "content", "alerts")
REFERENCE_VALID_ALERT = os.path.join(ALERTS_DIR, "vm_cpu_usage_alert.yaml")
MANAGEMENTPACKS_DIR = os.path.join(WORKSPACE_ROOT, "content", "managementpacks")
REFERENCE_VALID_MP = os.path.join(MANAGEMENTPACKS_DIR, "cloudflare.yaml")
VIEWS_DIR = os.path.join(WORKSPACE_ROOT, "content", "views")
REFERENCE_VALID_VIEW = os.path.join(VIEWS_DIR, "cluster_capacity_breakdown.yaml")


def run_hook(stdin_bytes: bytes) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, HOOK],
        input=stdin_bytes,
        capture_output=True,
        timeout=120,
    )


def hook_input(file_path: str) -> bytes:
    return json.dumps({"tool_input": {"file_path": file_path}}).encode()


def test_invalid_yaml_blocked_with_message():
    fd, path = tempfile.mkstemp(
        prefix="test_bad_hook_", suffix=".yaml", dir=ALERTS_DIR
    )
    try:
        with os.fdopen(fd, "w") as f:
            f.write("bad: yaml: content: [unclosed")
        result = run_hook(hook_input(path))
        assert result.returncode == 0
        decision = json.loads(result.stdout)
        assert decision["decision"] == "block"
        assert "vcfops_alerts" in decision["reason"]
    finally:
        os.unlink(path)


def test_valid_yaml_silent_pass():
    # A copy of a known-good checked-in alert is the simplest YAML the
    # validator definitely accepts (its symptom cross-references resolve
    # against the checked-in symptom corpus). Validation is fully offline —
    # no VCF Ops instance is needed.
    fd, path = tempfile.mkstemp(
        prefix="test_valid_hook_", suffix=".yaml", dir=ALERTS_DIR
    )
    os.close(fd)
    try:
        shutil.copyfile(REFERENCE_VALID_ALERT, path)
        result = run_hook(hook_input(path))
        assert result.returncode == 0
        assert result.stdout == b""
    finally:
        os.unlink(path)


def test_invalid_managementpack_yaml_blocked_with_message():
    fd, path = tempfile.mkstemp(
        prefix="test_bad_hook_", suffix=".yaml", dir=MANAGEMENTPACKS_DIR
    )
    try:
        with os.fdopen(fd, "w") as f:
            f.write("bad: yaml: content: [unclosed")
        result = run_hook(hook_input(path))
        assert result.returncode == 0
        decision = json.loads(result.stdout)
        assert decision["decision"] == "block"
        assert "vcfops_managementpacks" in decision["reason"]
    finally:
        os.unlink(path)


def test_valid_managementpack_yaml_silent_pass():
    fd, path = tempfile.mkstemp(
        prefix="test_valid_hook_", suffix=".yaml", dir=MANAGEMENTPACKS_DIR
    )
    os.close(fd)
    try:
        shutil.copyfile(REFERENCE_VALID_MP, path)
        result = run_hook(hook_input(path))
        assert result.returncode == 0
        assert result.stdout == b""
    finally:
        os.unlink(path)


def test_invalid_view_yaml_blocked_with_message():
    # Views validate whole-corpus via vcfops_dashboards, so a syntactically
    # broken file makes the loader fail regardless of which path triggered it.
    fd, path = tempfile.mkstemp(
        prefix="test_bad_hook_", suffix=".yaml", dir=VIEWS_DIR
    )
    try:
        with os.fdopen(fd, "w") as f:
            f.write("bad: yaml: content: [unclosed")
        result = run_hook(hook_input(path))
        assert result.returncode == 0
        decision = json.loads(result.stdout)
        assert decision["decision"] == "block"
        assert "vcfops_dashboards" in decision["reason"]
    finally:
        os.unlink(path)


def test_valid_view_yaml_silent_pass():
    fd, path = tempfile.mkstemp(
        prefix="test_valid_hook_", suffix=".yaml", dir=VIEWS_DIR
    )
    os.close(fd)
    try:
        shutil.copyfile(REFERENCE_VALID_VIEW, path)
        result = run_hook(hook_input(path))
        assert result.returncode == 0
        assert result.stdout == b""
    finally:
        os.unlink(path)


def test_non_content_path_ignored():
    path = os.path.join(WORKSPACE_ROOT, "scripts", "something.py")
    result = run_hook(hook_input(path))
    assert result.returncode == 0
    assert result.stdout == b""


def test_garbage_stdin_fails_open():
    result = run_hook(b"not json at all")
    assert result.returncode == 0
    assert result.stdout == b""

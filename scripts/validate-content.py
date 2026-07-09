#!/usr/bin/env python3
# purpose: Claude Code PostToolUse hook (Write|Edit) — validates content YAML
#          against the matching vcfops_<type> validate CLI when a file under
#          content/ is written. Blocks on validation failure so the agent
#          fixes the file immediately. Fail-open: internal errors never
#          wedge the pipeline.
# inputs: hook JSON on stdin (tool_input.file_path); runs validator subprocess
# outputs: {"decision": "block", "reason": ...} on stdout when validator fails;
#          silent (no output) on pass or skip
import json
import os
import subprocess
import sys

# FACTORY_ROOT is always derived from this script's own location — it is
# where the vcfops_* packages live (under src/, see pyproject.toml
# src-layout) — and must NOT follow VCFCF_CONTENT_ROOT overrides below.
FACTORY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# VCFCF_CONTENT_ROOT overrides the workspace root so tests (and any other
# caller) can point the hook at a temporary directory instead of the real
# content/ tree.  Unset → derive from __file__ as before.
_env_root = os.environ.get("VCFCF_CONTENT_ROOT", "").strip()
if _env_root:
    WORKSPACE_ROOT = os.path.realpath(_env_root)
else:
    WORKSPACE_ROOT = FACTORY_ROOT

CONTENT_ROOT = os.path.join(WORKSPACE_ROOT, "content") + os.sep

# Map from content subdirectory name to vcfops package name.
# Subdirectories with no validate CLI (recommendations, sdk-adapters) are
# intentionally absent — those paths skip silently. Recommendations have no
# standalone validator; they are cross-checked during vcfops_alerts validate.
PACKAGE_MAP = {
    "alerts": ("vcfops_alerts", True),  # True = accepts file path arg
    "customgroups": ("vcfops_customgroups", True),
    "managementpacks": ("vcfops_managementpacks", True),
    "reports": ("vcfops_reports", True),
    "supermetrics": ("vcfops_supermetrics", True),
    "symptoms": ("vcfops_symptoms", True),
    "dashboards": ("vcfops_dashboards", False),  # validates the whole corpus
    "views": ("vcfops_dashboards", False),  # views load with dashboards corpus
}


def main() -> None:
    data = json.load(sys.stdin)
    file_path = (data.get("tool_input") or {}).get("file_path") or ""
    file_path = os.path.realpath(file_path)

    if not file_path.startswith(CONTENT_ROOT):
        return

    # Derive the content subdirectory (first component after content/)
    rel = os.path.relpath(file_path, CONTENT_ROOT)
    subdir = rel.split(os.sep)[0]
    if subdir not in PACKAGE_MAP:
        return

    if not os.path.isfile(file_path):
        return  # deleted file, skip

    package, accepts_path = PACKAGE_MAP[subdir]
    cmd = [sys.executable, "-m", package, "validate"]
    if accepts_path:
        cmd.append(file_path)

    # The vcfops_* packages live under src/ (see pyproject.toml src-layout),
    # always relative to FACTORY_ROOT — never WORKSPACE_ROOT, which may be
    # a hermetic VCFCF_CONTENT_ROOT override with no src/ of its own.
    # Prepend it to PYTHONPATH so `-m <package>` resolves even when the
    # package has not been pip-installed into the caller's environment.
    env = os.environ.copy()
    src_root = os.path.join(FACTORY_ROOT, "src")
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = src_root + (os.pathsep + existing_pp if existing_pp else "")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=WORKSPACE_ROOT,
        env=env,
    )

    if result.returncode != 0:
        output = (result.stdout + result.stderr).strip()
        reason = (
            f"content validator blocked write to {os.path.relpath(file_path, WORKSPACE_ROOT)}"
            f" — {package} validate failed:\n{output}"
        )
        print(json.dumps({"decision": "block", "reason": reason}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # fail open — never wedge the pipeline
    sys.exit(0)

"""Isolated-kit subprocess test for buildkit import-rewrite correctness.

Guards the seam that let BLOCKING `sm_loader.py` / `vcfops_common` escape:
running `build-sdk` through the kit WITHOUT the factory on sys.path — the
exact condition of a clean CI runner pulling the published buildkit tarball.

Strategy
--------
Rather than assembling a full tarball (which requires a reference pak and
a complete dist/ tree), we extract just the Python modules from the kit
using the same `_FACTORY_SOURCES` / `_IMPORT_REWRITES` / `_apply_rewrites`
machinery that `assemble_buildkit` uses.  This is sufficient to exercise the
seam: the subprocess only needs the Python layer — Java compilation is
expected to fail (no SDK jar in CI) and that failure is explicitly allowed.
What must NOT happen is a `ModuleNotFoundError: No module named 'vcfops_common'`
(or any other `vcfops_*` module) during content loading.

The fixture contains 1 supermetric + 1 symptom + 1 alert so that
sm_loader, symptoms_loader, and alerts_loader are all exercised before
the Java step is reached.

The subprocess environment is sanitised:
  - PYTHONPATH set to ONLY the kit parent dir (not the factory root).
  - No factory package directory on sys.path via CWD (cwd is /tmp).

This means a residual `from vcfops_common.*` or `from vcfops_*` import in
any kit module will raise ModuleNotFoundError in the subprocess — the test
catches that as a failure, not as an acceptable Java-step SdkBuildError.
"""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Lazy import of buildkit internals — only pulled at test time so the test
# module can be collected even on machines without the factory fully installed.
# ---------------------------------------------------------------------------

def _get_buildkit_internals():
    from vcfops_managementpacks.buildkit import (
        _FACTORY_SOURCES,
        _IMPORT_REWRITES,
        _apply_rewrites,
    )
    return _FACTORY_SOURCES, _IMPORT_REWRITES, _apply_rewrites


# ---------------------------------------------------------------------------
# Fixture YAML content
# ---------------------------------------------------------------------------

_SM_UUID = "aaaabbbb-0001-0001-0001-000000000001"

_SM_YAML = textwrap.dedent(f"""\
    id: {_SM_UUID}
    name: "[VCF Content Factory] Kit Isolation Test SM"
    formula: "${{this, metric=cpu|usage_average}}"
    description: "Minimal SM for kit isolation test."
    resource_kinds:
      - adapter_kind_key: VMWARE
        resource_kind_key: HostSystem
    unit_id: ""
    released: false
    version: "1.0.0"
""")

_SYMPTOM_UUID = "ccccdddd-0002-0002-0002-000000000002"

_SYMPTOM_YAML = textwrap.dedent(f"""\
    name: "[VCF Content Factory] Kit Isolation Test Symptom"
    adapter_kind: VMWARE
    resource_kind: HostSystem
    severity: CRITICAL
    wait_cycles: 1
    cancel_cycles: 1
    condition:
      type: metric_static
      key: cpu|usage_average
      operator: GT
      value: 95
      instanced: false
    description: "Minimal symptom for kit isolation test."
""")

_ALERT_UUID = "eeeeffff-0003-0003-0003-000000000003"

_ALERT_YAML = textwrap.dedent(f"""\
    name: "[VCF Content Factory] Kit Isolation Test Alert"
    description: "Minimal alert for kit isolation test."
    adapter_kind: VMWARE
    resource_kind: HostSystem
    type: 19
    sub_type: 19
    criticality: CRITICAL
    wait_cycles: 1
    cancel_cycles: 1
    impact:
      badge: HEALTH
    symptom_sets:
      operator: ANY
      sets:
        - defined_on: SELF
          operator: ANY
          symptoms:
            - name: "[VCF Content Factory] Kit Isolation Test Symptom"
""")

_ADAPTER_YAML = textwrap.dedent("""\
    name: "VCF Content Factory Kit Isolation Test Adapter"
    version: "1.0.0"
    build_number: 1
    adapter_kind: "kit_isolation_test"
    tier: 2
    description: "Synthetic adapter for buildkit isolated-kit import-rewrite test."
    entry_class: "com.vcfcf.adapters.kitisolation.KitIsolationAdapter"
    released: false
    bundled_content:
      supermetrics:
        - supermetrics/kit-isolation-sm.yaml
      symptoms:
        - symptoms/kit-isolation-symptom.yaml
      alerts:
        - alerts/kit-isolation-alert.yaml
""")

# Minimal describe.xml — the sdk_builder reads this for the world resource kind.
_DESCRIBE_XML = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <AdapterKind key="kit_isolation_test" nameKey="1" version="1">
      <ResourceKinds>
        <ResourceKind key="kit_isolation_test_world" nameKey="2" type="1"/>
      </ResourceKinds>
    </AdapterKind>
""")

# Minimal Java source so the compiler has *something* to work with even if
# it fails (no SDK jar).  The test doesn't require Java to succeed.
_JAVA_SRC = textwrap.dedent("""\
    package com.vcfcf.adapters.kitisolation;
    public class KitIsolationAdapter {}
""")


# ---------------------------------------------------------------------------
# Helper: write fixture adapter directory
# ---------------------------------------------------------------------------

def _write_fixture_adapter(base: Path) -> Path:
    """Write the synthetic adapter fixture under base/; return its path."""
    project_dir = base / "kit_isolation_adapter"
    project_dir.mkdir(parents=True)

    (project_dir / "adapter.yaml").write_text(_ADAPTER_YAML, encoding="utf-8")
    (project_dir / "describe.xml").write_text(_DESCRIBE_XML, encoding="utf-8")

    sm_dir = project_dir / "supermetrics"
    sm_dir.mkdir()
    (sm_dir / "kit-isolation-sm.yaml").write_text(_SM_YAML, encoding="utf-8")

    sym_dir = project_dir / "symptoms"
    sym_dir.mkdir()
    (sym_dir / "kit-isolation-symptom.yaml").write_text(_SYMPTOM_YAML, encoding="utf-8")

    alert_dir = project_dir / "alerts"
    alert_dir.mkdir()
    (alert_dir / "kit-isolation-alert.yaml").write_text(_ALERT_YAML, encoding="utf-8")

    src_dir = project_dir / "src" / "main" / "java" / "com" / "vcfcf" / "adapters" / "kitisolation"
    src_dir.mkdir(parents=True)
    (src_dir / "KitIsolationAdapter.java").write_text(_JAVA_SRC, encoding="utf-8")

    return project_dir


# ---------------------------------------------------------------------------
# Helper: assemble a flat kit directory (Python modules only — no tarball,
# no reference pak needed).  Mirrors the Python-module step of assemble_buildkit.
# ---------------------------------------------------------------------------

def _assemble_kit_python_only(kit_dir: Path) -> None:
    """Copy and rewrite all Python kit modules into kit_dir/sdk_buildkit/."""
    _FACTORY_SOURCES, _IMPORT_REWRITES, _apply_rewrites = _get_buildkit_internals()
    from vcfops_managementpacks.buildkit import _KIT_INIT, _KIT_MAIN

    pkg_dir = kit_dir / "sdk_buildkit"
    pkg_dir.mkdir(parents=True)

    (pkg_dir / "__init__.py").write_text(_KIT_INIT, encoding="utf-8")
    (pkg_dir / "__main__.py").write_text(_KIT_MAIN, encoding="utf-8")

    for dest_name, src_path in _FACTORY_SOURCES.items():
        if not src_path.is_file():
            # Skip optional sources (e.g. docs_gen) that may not exist in all envs.
            continue
        source_text = src_path.read_text(encoding="utf-8")
        rules = _IMPORT_REWRITES.get(dest_name, [])
        if rules:
            patched_text = _apply_rewrites(source_text, rules)
            (pkg_dir / dest_name).write_text(patched_text, encoding="utf-8")
        else:
            (pkg_dir / dest_name).write_bytes(src_path.read_bytes())

    # adapter_runtime/ and adapter_framework/src/ are needed by build-sdk for
    # the Java step; we create stubs so the kit directory is structurally valid.
    (pkg_dir / "adapter_runtime").mkdir(exist_ok=True)

    fw_src_real = Path(__file__).parent.parent.parent / "vcfops_managementpacks" / "adapter_framework" / "src"
    fw_dst = pkg_dir / "adapter_framework" / "src"
    if fw_src_real.is_dir():
        import shutil
        shutil.copytree(str(fw_src_real), str(fw_dst))
    else:
        fw_dst.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Helper: build the sanitised subprocess environment
# ---------------------------------------------------------------------------

def _make_isolated_env(kit_parent: Path) -> dict:
    """Return an env dict where ONLY the kit parent dir is on PYTHONPATH.

    The factory repo root is explicitly stripped from PYTHONPATH and sys.path
    cannot leak via CWD (we set cwd=/tmp in the subprocess call).  This
    reproduces the clean CI-runner condition: the factory packages must NOT
    be importable; only the kit must be.
    """
    # Determine the repo root to strip it.
    repo_root = str(Path(__file__).parent.parent.parent.resolve())

    env = os.environ.copy()

    # Build a clean PYTHONPATH: take existing entries, strip the factory root.
    existing_pp = env.get("PYTHONPATH", "")
    cleaned_entries = [
        e for e in existing_pp.split(os.pathsep) if e
        if not Path(e).resolve() == Path(repo_root)
    ]
    # Prepend the kit parent so `import sdk_buildkit` works.
    cleaned_entries.insert(0, str(kit_parent))
    env["PYTHONPATH"] = os.pathsep.join(cleaned_entries)

    return env


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------

def _assert_no_vcfops_module_error(stderr: str, stdout: str) -> None:
    """Fail the test if the output contains a ModuleNotFoundError for vcfops_*."""
    combined = stderr + stdout
    if "ModuleNotFoundError" in combined and "vcfops_" in combined:
        # Extract the relevant lines for a readable failure message.
        lines = [
            line for line in combined.splitlines()
            if "ModuleNotFoundError" in line or "vcfops_" in line or "No module named" in line
        ]
        pytest.fail(
            "Kit subprocess raised ModuleNotFoundError for a vcfops_* module — "
            "a kit module still imports from the factory namespace.\n"
            "Relevant lines:\n" + "\n".join(f"  {l}" for l in lines)
        )


def _assert_content_loading_succeeded(stderr: str) -> None:
    """Assert that bundled content was reported as loaded (the SM/symptom/alert line)."""
    # sdk_builder prints "  bundled content: N view(s), ..." to stderr when content loads.
    if "bundled content:" not in stderr:
        pytest.fail(
            "Expected 'bundled content:' line in subprocess stderr — "
            "content loading may have been skipped or failed silently.\n"
            f"subprocess stderr:\n{stderr[:2000]}"
        )
    # Confirm supermetrics loaded (the critical path for the BLOCKING).
    if "supermetric" not in stderr:
        pytest.fail(
            "Expected 'supermetric(s)' count in 'bundled content:' line but not found.\n"
            f"subprocess stderr:\n{stderr[:2000]}"
        )


# ---------------------------------------------------------------------------
# The test
# ---------------------------------------------------------------------------

@pytest.mark.timeout(60)
def test_kit_isolated_build_no_vcfops_import_error(tmp_path):
    """build-sdk through the extracted kit must not raise ModuleNotFoundError for vcfops_*.

    The kit is assembled Python-only into tmp_path/kit/; the fixture adapter
    is written to tmp_path/fixture/.  The subprocess runs with cwd=/tmp and
    PYTHONPATH=tmp_path/kit only — the factory packages are not importable.

    Expected outcome: content loading succeeds (supermetrics, symptoms, alerts
    all loaded and reported); the subprocess exits with 0 (unlikely — no SDK
    jar) or with a non-zero exit that is due to Java / SDK jar absence, NOT
    due to any vcfops_* ModuleNotFoundError.
    """
    import tempfile

    kit_root = tmp_path / "kit"
    fixture_root = tmp_path / "fixture"
    fixture_root.mkdir()

    # 1. Assemble the kit (Python modules only).
    _assemble_kit_python_only(kit_root)

    # kit_root/sdk_buildkit/ is the package; kit_root itself is on PYTHONPATH.
    kit_parent = kit_root

    # 2. Write the fixture adapter.
    project_dir = _write_fixture_adapter(fixture_root)
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # 3. Build the sanitised environment (factory NOT importable).
    env = _make_isolated_env(kit_parent)

    # 4. Run build-sdk via subprocess.
    #    cwd is /tmp — completely outside the factory repo.
    result = subprocess.run(
        [sys.executable, "-m", "sdk_buildkit", "build-sdk",
         str(project_dir), "--output", str(output_dir)],
        capture_output=True,
        text=True,
        cwd=tempfile.gettempdir(),
        env=env,
        timeout=55,
    )

    stderr = result.stderr
    stdout = result.stdout

    # 5. Assert: no ModuleNotFoundError for vcfops_* (the BLOCKING class).
    _assert_no_vcfops_module_error(stderr, stdout)

    # 6. Assert: content loading actually happened and reached the SM line
    #    (proves sm_loader ran, not just that we exited before loading).
    _assert_content_loading_succeeded(stderr)

    # 7. The exit code may be non-zero if Java / SDK jar is absent — that is
    #    expected and acceptable.  What is NOT acceptable is a Python import
    #    error for vcfops_* (already checked above).
    #
    #    If exit code IS 0, a pak was produced — assert it exists.
    if result.returncode == 0:
        paks = list(output_dir.glob("*.pak"))
        assert paks, (
            "build-sdk exited 0 but no .pak found in output dir.\n"
            f"output_dir contents: {list(output_dir.iterdir())}"
        )


# ---------------------------------------------------------------------------
# Revert-check: confirm the test FAILS when the sm_loader rewrite is absent
# ---------------------------------------------------------------------------

@pytest.mark.timeout(60)
def test_kit_isolated_build_fails_without_sm_rewrite(tmp_path):
    """Confirms the test infrastructure guards the sm_loader.py seam.

    This test intentionally assembles the kit WITHOUT the sm_loader.py
    import rewrite, then runs build-sdk and asserts that ModuleNotFoundError
    for vcfops_common IS present in the output.  If this test passes it means
    the seam is real and the guard above is meaningful.

    This is the "canary" test: if it starts FAILING (i.e. vcfops_common is
    no longer present in the output even without the rewrite), the import
    structure has changed and both tests need updating.
    """
    import shutil
    import tempfile

    from vcfops_managementpacks.buildkit import (
        _FACTORY_SOURCES,
        _IMPORT_REWRITES,
        _apply_rewrites,
        _KIT_INIT,
        _KIT_MAIN,
    )

    kit_root = tmp_path / "kit_no_sm_rewrite"
    pkg_dir = kit_root / "sdk_buildkit"
    pkg_dir.mkdir(parents=True)

    (pkg_dir / "__init__.py").write_text(_KIT_INIT, encoding="utf-8")
    (pkg_dir / "__main__.py").write_text(_KIT_MAIN, encoding="utf-8")

    for dest_name, src_path in _FACTORY_SOURCES.items():
        if not src_path.is_file():
            continue
        source_text = src_path.read_text(encoding="utf-8")
        # Apply all rewrites EXCEPT sm_loader.py — that's what we're reverting.
        if dest_name == "sm_loader.py":
            rules = []
        else:
            rules = _IMPORT_REWRITES.get(dest_name, [])
        if rules:
            patched_text = _apply_rewrites(source_text, rules)
            (pkg_dir / dest_name).write_text(patched_text, encoding="utf-8")
        else:
            (pkg_dir / dest_name).write_bytes(src_path.read_bytes())

    (pkg_dir / "adapter_runtime").mkdir(exist_ok=True)
    fw_src_real = Path(__file__).parent.parent.parent / "vcfops_managementpacks" / "adapter_framework" / "src"
    fw_dst = pkg_dir / "adapter_framework" / "src"
    if fw_src_real.is_dir():
        shutil.copytree(str(fw_src_real), str(fw_dst))
    else:
        fw_dst.mkdir(parents=True, exist_ok=True)

    fixture_root = tmp_path / "fixture"
    fixture_root.mkdir()
    project_dir = _write_fixture_adapter(fixture_root)
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    env = _make_isolated_env(kit_root)

    result = subprocess.run(
        [sys.executable, "-m", "sdk_buildkit", "build-sdk",
         str(project_dir), "--output", str(output_dir)],
        capture_output=True,
        text=True,
        cwd=tempfile.gettempdir(),
        env=env,
        timeout=55,
    )

    combined = result.stderr + result.stdout
    has_vcfops_error = (
        "ModuleNotFoundError" in combined and "vcfops_" in combined
    ) or (
        "No module named" in combined and "vcfops_common" in combined
    )

    if not has_vcfops_error:
        pytest.fail(
            "Revert-check canary FAILED: expected ModuleNotFoundError for "
            "vcfops_common when sm_loader.py rewrite is absent, but it was "
            "NOT present.  The import structure of sm_loader.py may have "
            "changed — update both tests.\n"
            f"subprocess stderr:\n{result.stderr[:2000]}\n"
            f"subprocess stdout:\n{result.stdout[:500]}"
        )
    # If we get here, the revert correctly produces the expected error — the
    # canary is healthy and the guard in the sibling test is meaningful.

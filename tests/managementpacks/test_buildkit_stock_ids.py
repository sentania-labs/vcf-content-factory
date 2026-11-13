"""The sdk-buildkit ships the stock-id guard and its baseline (issue #345).

Pak repos' CI has no factory checkout: the kit's validate-sdk / build-sdk
must run the guard from the kit's own ``stock_ids.py`` and
``stock_ids_baseline.json``, fail closed when the baseline is gone, and the
kit's ``stock-id-check`` must work standalone. Ids and names are made up;
the kit's real baseline is replaced by a synthetic one before each check.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"

STOCK_VIEW = "aaaa0001-0000-4000-8000-000000000001"
OWN_VIEW = "bbbb0001-0000-4000-8000-000000000001"


@pytest.fixture(scope="module")
def kit(tmp_path_factory) -> Path:
    """Assemble and extract a real kit tarball; return the extraction root."""
    sys.path.insert(0, str(SRC))
    from vcfcf_managementpacks.buildkit import assemble_buildkit

    work = tmp_path_factory.mktemp("kit")
    ref = work / "vcfcf_sdk_compliance.1.0.0.1.pak"
    with zipfile.ZipFile(ref, "w") as zf:
        zf.writestr("manifest.txt", "reference pak fixture\n")
    tarball = assemble_buildkit(work / "out", version="9.9.9", reference_pak=ref, verbose=False)
    root = work / "extracted"
    with tarfile.open(tarball) as tf:
        if sys.version_info >= (3, 12):
            tf.extractall(root, filter="data")
        else:
            tf.extractall(root)
    return root


def _synthetic_baseline() -> str:
    return json.dumps({
        "format": "vcfcf-stock-ids/1",
        "ids": {"view": {STOCK_VIEW: {"name": "Stock Probe View", "versions": ["9.1.1"]}}},
    })


def _kit_env(kit_root: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "VCFCF_SDK_JAR")}
    env["PYTHONPATH"] = str(kit_root)
    return env


def _run_kit(kit_root: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "sdk_buildkit", *args],
        capture_output=True, text=True, env=_kit_env(kit_root),
        cwd=tempfile.gettempdir(), timeout=120,
    )


def _adapter(base: Path, view_id: str, allowlist: str = "") -> Path:
    project = base / "probe_adapter"
    (project / "views").mkdir(parents=True)
    (project / "src" / "com" / "probe").mkdir(parents=True)
    (project / "adapter.yaml").write_text(textwrap.dedent(f"""\
        name: "Probe Adapter"
        version: "1.0.0"
        build_number: 1
        adapter_kind: "probe_kind"
        tier: 2
        content_naming: unprefixed
        bundled_content:
          views:
            - views/probe.yaml
        """) + allowlist, encoding="utf-8")
    (project / "describe.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<AdapterKind key="probe_kind" nameKey="1" version="1">'
        '<ResourceKinds><ResourceKind key="probe_world" nameKey="2" type="1"/></ResourceKinds></AdapterKind>\n',
        encoding="utf-8",
    )
    (project / "views" / "probe.yaml").write_text(textwrap.dedent(f"""\
        id: {view_id}
        name: "Probe View"
        description: "probe"
        subject:
          adapter_kind: VMWARE
          resource_kind: HostSystem
        columns:
          - attribute: cpu|usage_average
            display_name: "CPU Usage (%)"
        """), encoding="utf-8")
    (project / "src" / "com" / "probe" / "ProbeAdapter.java").write_text(
        "package com.probe;\npublic class ProbeAdapter {}\n", encoding="utf-8")
    return project


def test_kit_ships_guard_and_baseline_byte_for_byte(kit):
    pkg = kit / "sdk_buildkit"
    core = SRC / "vcfcf_core" / "stock_ids"
    assert (pkg / "stock_ids.py").read_bytes() == (core / "guard.py").read_bytes()
    assert (pkg / "stock_ids_baseline.json").read_bytes() == (core / "stock_ids_baseline.json").read_bytes()


def test_kit_archive_carries_guard_and_baseline(kit):
    """Review W7: the published tarball itself (not only an extraction of
    it) carries both files, the baseline byte-equal to src/."""
    (tarball,) = sorted((kit.parent / "out").glob("*.tgz"))
    core = SRC / "vcfcf_core" / "stock_ids"
    with tarfile.open(tarball) as tf:
        names = {m.name: m for m in tf.getmembers()}
        for member, src in (("sdk_buildkit/stock_ids_baseline.json", core / "stock_ids_baseline.json"),
                            ("sdk_buildkit/stock_ids.py", core / "guard.py")):
            match = [n for n in names if n == member or n.endswith("/" + member)]
            assert match, f"{member} is not in {tarball.name}"
            assert tf.extractfile(names[match[0]]).read() == src.read_bytes()


def test_kit_validate_sdk_refuses_bundled_stock_id(kit, tmp_path):
    (kit / "sdk_buildkit" / "stock_ids_baseline.json").write_text(_synthetic_baseline(), encoding="utf-8")
    project = _adapter(tmp_path, STOCK_VIEW)
    r = _run_kit(kit, "validate-sdk", str(project))
    assert r.returncode == 1, r.stdout + r.stderr
    assert "stock-id guard" in r.stderr and STOCK_VIEW in r.stderr
    assert "views/probe.yaml" in r.stderr and "Stock Probe View" in r.stderr

    clean = _adapter(tmp_path / "clean", OWN_VIEW)
    r = _run_kit(kit, "validate-sdk", str(clean))
    assert "stock-id guard" not in r.stderr, r.stderr


def test_kit_validate_sdk_honours_allowlist_with_warning(kit, tmp_path):
    (kit / "sdk_buildkit" / "stock_ids_baseline.json").write_text(_synthetic_baseline(), encoding="utf-8")
    allow = textwrap.dedent(f"""\
        stock_id_allowlist:
          - type: view
            id: {STOCK_VIEW}
            reason: "probe keeps the stock id on purpose"
        """)
    project = _adapter(tmp_path, STOCK_VIEW, allowlist=allow)
    r = _run_kit(kit, "validate-sdk", str(project))
    assert "stock-id guard" not in r.stderr.replace("ALLOWLISTED stock id", ""), r.stderr
    assert "ALLOWLISTED stock id" in r.stderr and "probe keeps the stock id on purpose" in r.stderr


def test_kit_build_sdk_fails_closed_without_baseline(kit, tmp_path):
    baseline = kit / "sdk_buildkit" / "stock_ids_baseline.json"
    saved = baseline.read_bytes()
    baseline.unlink()
    try:
        project = _adapter(tmp_path, OWN_VIEW)
        r = _run_kit(kit, "build-sdk", str(project), "--output", str(tmp_path / "out"))
        assert r.returncode == 1, r.stdout + r.stderr
        assert "stock-id guard" in r.stderr and "cannot be read" in r.stderr
        assert not list((tmp_path / "out").glob("*.pak")) if (tmp_path / "out").exists() else True
    finally:
        baseline.write_bytes(saved)


def test_kit_stock_id_check(kit, tmp_path):
    (kit / "sdk_buildkit" / "stock_ids_baseline.json").write_text(_synthetic_baseline(), encoding="utf-8")
    pak = tmp_path / "upstream.pak"
    views = '<Content><Views><ViewDef id="%s"><Title>Copied</Title></ViewDef></Views></Content>' % STOCK_VIEW
    with zipfile.ZipFile(pak, "w") as zf:
        zf.writestr("content/reports/set/View - Set 1.xml", views)
    r = _run_kit(kit, "stock-id-check", str(pak))
    assert r.returncode == 2, r.stdout + r.stderr
    assert f"STOCK view {STOCK_VIEW} 'Stock Probe View'" in r.stdout
    assert "Known holes" in r.stdout
    r = _run_kit(kit, "stock-id-check", str(pak), "--baseline", str(tmp_path / "missing.json"))
    assert r.returncode == 1
    # Unreadable content is not clean in the kit either.
    bad = tmp_path / "bad.pak"
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("adapters.zip", b"PK\x03\x04 not a zip")
    r = _run_kit(kit, "stock-id-check", str(bad))
    assert r.returncode == 1 and "CANNOT CHECK" in r.stdout, r.stdout + r.stderr

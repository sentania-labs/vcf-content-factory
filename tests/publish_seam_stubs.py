"""Injectable seam stubs for publish() shape tests (issue #125).

``publish()`` grew two keyword-only test seams, ``validator`` and
``build_one_release``, because the real seven-package validator chain costs
~200s per call (vcfops_managementpacks validate alone is ~190s) and every
shape-only assertion was paying it.  This module is the single shared home
for the stub implementations so the two publish test files cannot drift
apart.

What the stubs replace, and what stays REAL when they are used:

  REPLACED   the eight ``python3 -m <pkg> validate`` subprocesses
  REPLACED   the real zip build (``release_builder.build_release``)
  REAL       lockfile acquire/release, RULE-012 defect gate, clean-tree
             check, copy/idempotence hashing, legacy/stale/retirement
             sweeps, README regeneration, every git operation, branch/PR
             orchestration, commit message construction

Anti-drift guard: ``tests/test_publish_phase3.py::test_real_run_zip_lands``
still drives the REAL validator and the REAL zip builder end to end (slow
marker, real_corpus xdist group).  Executing-branch assertions on what
publish() DOES with validator/build failures live in
``tests/test_publish_seams.py``.

This module is not collected by pytest (no ``test_`` prefix); it is
imported by the test files, which works because ``tests/`` has no
``__init__.py`` so pytest prepends the directory to ``sys.path``.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

from vcfops_packaging.publish import publish as _real_publish


def stub_validator(factory_repo: Path) -> None:
    """Validator seam stub: succeed without spawning subprocesses."""
    return None


class RecordingValidator:
    """Validator seam stub that records every invocation.

    Raises ``exc`` on call when given, so tests can assert what publish()
    does on validation failure (the abort path must actually execute).
    """

    def __init__(self, exc: Exception | None = None):
        self.calls: list[Path] = []
        self.exc = exc

    def __call__(self, factory_repo: Path) -> None:
        self.calls.append(factory_repo)
        if self.exc is not None:
            raise self.exc


def stub_build_one_release(release, staging_dir: Path, factory_repo: Path):
    """Build seam stub: emit a tiny deterministic zip per headline.

    Mirrors the real ``_build_one_release`` contract: a list of
    ``ReleaseArtifact`` whose ``zip_path``/``dest_subdir`` route through
    publish()'s copy loop unchanged.  The zip content is deterministic
    (fixed member, fixed date_time) so the idempotence hashing behaves the
    same across repeat publishes, exactly like a real same-content rebuild.
    """
    from vcfops_packaging.release_builder import (
        ReleaseArtifact,
        _artifact_dest_subdir,
        _is_sdk_adapter_source,
        _zip_filename,
    )

    artifacts = []
    for manifest_artifact in release.artifacts:
        if not manifest_artifact.headline:
            continue
        dest_subdir = _artifact_dest_subdir(manifest_artifact)
        if _is_sdk_adapter_source(manifest_artifact.source_path):
            artifacts.append(ReleaseArtifact(
                zip_path=None,
                dest_subdir=dest_subdir,
                headline_source=str(manifest_artifact.source_path),
                release_name=release.name,
                release_version=release.version,
                is_sdk_pointer=True,
                pointer_info={},
            ))
            continue
        out_dir = Path(staging_dir) / dest_subdir
        out_dir.mkdir(parents=True, exist_ok=True)
        zip_path = out_dir / _zip_filename(release.name)
        with zipfile.ZipFile(zip_path, "w") as zf:
            info = zipfile.ZipInfo("stub.txt", date_time=(2026, 1, 1, 0, 0, 0))
            zf.writestr(info, f"seam stub artifact for {release.name}\n")
        artifacts.append(ReleaseArtifact(
            zip_path=zip_path,
            dest_subdir=dest_subdir,
            headline_source=str(manifest_artifact.source_path),
            release_name=release.name,
            release_version=release.version,
        ))
    return artifacts


def stubbed_publish(**kwargs):
    """publish() with the validator/build seams stubbed.  Shape tests only.

    Injection happens via ``setdefault`` so a test may still override either
    seam (or pass the real one back) explicitly.
    """
    kwargs.setdefault("validator", stub_validator)
    kwargs.setdefault("build_one_release", stub_build_one_release)
    return _real_publish(**kwargs)

"""Executing-branch tests for the publish() validator/build seams (#125).

The seams exist so shape tests can skip ~200s of validator subprocesses per
publish() call.  A seam that silently skipped validation in production, or a
stub that publish() ignored, would be the silent-downgrade failure mode, so
these tests assert what publish() DOES with each seam outcome (see
knowledge/lessons/unenumerated-exit-status-is-not-a-verdict.md: an outcome is
only trusted when the branch that handles it is shown to execute):

  1. A failing injected validator aborts the publish before any build, with
     no commit and the lockfile released.
  2. A failing injected builder aborts the publish, with no commit and the
     lockfile released.
  3. With NO injection, publish() routes to the real ``_run_validators`` and
     ``_build_one_release`` (defaults cannot drift to stubs).
  4. An injected validator is actually invoked, exactly once, with the
     factory repo path.

All fast: no slow marker.  No test here runs validators over or writes to
the real content/ corpus (the validator is stubbed or monkeypatched in every
test); the only touch is a read-only existence/name check of one real
content/dashboards/ YAML referenced by the test manifest, which does not
need the real_corpus group.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from publish_seam_stubs import (
    RecordingValidator,
    stub_build_one_release,
    stub_validator,
)
from test_publish_phase3 import (
    _init_dist_repo,
    _patch_enumerate,
    _write_release_manifest,
)

REPO_ROOT = Path(__file__).parent.parent


def _commit_count(dist: Path) -> int:
    r = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=str(dist), capture_output=True, text=True, check=True,
    )
    return int(r.stdout.strip())


def _setup(tmp_path, monkeypatch):
    dist = _init_dist_repo(tmp_path)
    releases_dir = tmp_path / "releases"
    releases_dir.mkdir()
    _write_release_manifest(
        releases_dir,
        name="demand-driven-capacity-v2",
        version="1.0",
        source_abs=(
            REPO_ROOT / "content" / "dashboards" / "demand_driven_capacity_v2.yaml"
        ).resolve(),
        description="Seam behaviour test.",
    )
    _patch_enumerate(monkeypatch, releases_dir)
    return dist


class _RecordingBuilder:
    def __init__(self, exc: Exception | None = None):
        self.calls = []
        self.exc = exc

    def __call__(self, release, staging_dir, factory_repo):
        self.calls.append(release.name)
        if self.exc is not None:
            raise self.exc
        return stub_build_one_release(release, staging_dir, factory_repo)


class TestValidatorSeamOutcomes:

    def test_failing_validator_aborts_before_build(self, tmp_path, monkeypatch):
        """Validator failure must hard-stop publish(): no build, no commit,
        lockfile released."""
        from vcfops_packaging.publish import publish, PublishError

        dist = _setup(tmp_path, monkeypatch)
        before = _commit_count(dist)
        validator = RecordingValidator(exc=PublishError("seam validator failure"))
        builder = _RecordingBuilder()

        with pytest.raises(PublishError, match="seam validator failure"):
            publish(
                factory_repo=REPO_ROOT,
                dist_repo=dist,
                dry_run=False,
                no_push=True,
                use_pr=False,
                validator=validator,
                build_one_release=builder,
            )

        assert validator.calls, "Injected validator was never invoked"
        assert builder.calls == [], (
            f"Builder ran despite validator failure: {builder.calls}"
        )
        assert _commit_count(dist) == before, "A commit landed despite the abort"
        assert not (dist / ".publish.lock").exists(), "Lockfile leaked on abort"

    def test_injected_validator_called_once_with_factory_repo(
        self, tmp_path, monkeypatch
    ):
        from vcfops_packaging.publish import publish

        dist = _setup(tmp_path, monkeypatch)
        validator = RecordingValidator()

        result = publish(
            factory_repo=REPO_ROOT,
            dist_repo=dist,
            dry_run=False,
            no_push=True,
            use_pr=False,
            validator=validator,
            build_one_release=stub_build_one_release,
        )

        assert validator.calls == [REPO_ROOT.resolve()], (
            f"Validator seam not wired to the factory repo: {validator.calls}"
        )
        assert result.commit_sha, "Successful stubbed publish should commit"


class TestBuilderSeamOutcomes:

    def test_failing_builder_aborts_publish(self, tmp_path, monkeypatch):
        """Builder failure must hard-stop publish(): no commit, lockfile
        released."""
        from vcfops_packaging.publish import publish, PublishError

        dist = _setup(tmp_path, monkeypatch)
        before = _commit_count(dist)
        builder = _RecordingBuilder(exc=PublishError("seam build failure"))

        with pytest.raises(PublishError, match="seam build failure"):
            publish(
                factory_repo=REPO_ROOT,
                dist_repo=dist,
                dry_run=False,
                no_push=True,
                use_pr=False,
                validator=stub_validator,
                build_one_release=builder,
            )

        assert builder.calls, "Injected builder was never invoked"
        assert _commit_count(dist) == before, "A commit landed despite the abort"
        assert not (dist / ".publish.lock").exists(), "Lockfile leaked on abort"


class TestDefaultsAreReal:

    def test_no_injection_routes_to_real_validator_and_builder(
        self, tmp_path, monkeypatch
    ):
        """publish() without seam kwargs must call _run_validators and
        _build_one_release.  Guards the silent-downgrade failure mode where
        the defaults drift to stubs and production stops validating."""
        import vcfops_packaging.publish as _pub
        from vcfops_packaging.publish import publish

        dist = _setup(tmp_path, monkeypatch)

        validator_calls = []
        builder_calls = []
        monkeypatch.setattr(
            _pub, "_run_validators",
            lambda repo: validator_calls.append(repo),
        )
        monkeypatch.setattr(
            _pub, "_build_one_release",
            lambda release, staging, repo: (
                builder_calls.append(release.name),
                stub_build_one_release(release, staging, repo),
            )[1],
        )

        publish(
            factory_repo=REPO_ROOT,
            dist_repo=dist,
            dry_run=False,
            no_push=True,
            use_pr=False,
        )

        assert validator_calls == [REPO_ROOT.resolve()], (
            "publish() without injection did not call the real validator hook"
        )
        assert builder_calls == ["demand-driven-capacity-v2"], (
            "publish() without injection did not call the real builder hook"
        )

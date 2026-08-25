"""Executing-branch tests for two audit-hardening changes (2026-08):

1. Release/publish builds run the dependency audit BY DEFAULT, offline:
   ``release_builder.build_release`` defaults flipped from
   ``skip_audit=True`` to ``skip_audit=False`` with ``live_describe=False``
   (the committed knowledge/context/adapter_describe_cache/ files are the
   reference; publish must keep working with no live instance).  The publish
   path surfaces an AuditError as a hard PublishError (never a warning), and
   a missing/corrupt describe cache also fails loudly with a message naming
   the ``--skip-audit`` opt-out.

2. ``${this, metric=KEY}`` audit blindness closed: ``deps._refs_from_formula``
   used to skip every ``${this, ...}`` entry, so this-bound metric keys were
   never checked against the describe cache in any build.  They now resolve
   against the super metric's own ``resource_kinds:`` assignment (one
   auditable reference per declared adapter/resource-kind pair), including
   defaultMonitored classification so auto-add works for them.  A this-ref
   with no usable resource_kinds is reported (AuditError), never silently
   skipped.

Per knowledge/lessons/unenumerated-exit-status-is-not-a-verdict.md, each
outcome branch is shown to execute: audit-by-default failing on an unknown
ref, offline mode constructing no live client, publish aborting on an audit
failure, and both the pass and failure paths of the this-ref resolution.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from vcfops_packaging.audit import AuditError

REPO_ROOT = Path(__file__).parent.parent

# Formula whose ONLY metric reference is this-bound.  Pre-fix, the auditor
# extracted zero references from it (total blindness).
_THIS_ONLY_FORMULA = "${this, metric=this_test_group|this_test_metric_v1}"


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _write_sm_project(
    tmp_path: Path,
    *,
    formula: str = _THIS_ONLY_FORMULA,
    name: str = "Release Audit Test SM",
    under_third_party: bool = True,
) -> Path:
    """Write a third_party/<proj>/supermetrics/<file>.yaml project.

    The third_party/ shape is required so build_release() routes the source
    through the discrete builder with extra_search_dirs populated.
    """
    root = (tmp_path / "third_party") if under_third_party else tmp_path
    proj = root / "audit_proj"
    sm_dir = proj / "supermetrics"
    sm_dir.mkdir(parents=True)
    (sm_dir / "audit_test_sm.yaml").write_text(yaml.dump({
        "name": name,
        "formula": formula,
        "description": "Fixture SM for release-audit-default tests.",
        "resource_kinds": [
            {"resource_kind_key": "VirtualMachine", "adapter_kind_key": "VMWARE"}
        ],
    }))
    return proj


def _write_release_manifest(tmp_path: Path, proj: Path, name: str) -> Path:
    manifest = {
        "name": name,
        "version": "1.0",
        "description": "Release-audit-default test manifest.",
        "artifacts": [
            {
                "source": str((proj / "supermetrics" / "audit_test_sm.yaml").resolve()),
                "headline": True,
            }
        ],
    }
    p = tmp_path / f"{name}.yaml"
    p.write_text(yaml.dump(manifest, default_flow_style=False))
    return p


def _seed_describe_cache(cache_dir: Path, metrics: dict) -> Path:
    """Write a minimal offline describe cache for VMWARE/VirtualMachine."""
    ak_dir = cache_dir / "VMWARE"
    ak_dir.mkdir(parents=True, exist_ok=True)
    (ak_dir / "VirtualMachine.json").write_text(__import__("json").dumps({
        "adapter_kind": "VMWARE",
        "resource_kind": "VirtualMachine",
        "metrics": metrics,
        "properties": {},
    }))
    return cache_dir


def _patch_offline_cache(monkeypatch, cache_dir: Path):
    """Route make_cache() to a DescribeCache over cache_dir with no client."""
    import vcfops_packaging.describe as describe_mod
    monkeypatch.setattr(
        describe_mod, "make_cache",
        lambda live=True, cache_dir=None, _d=cache_dir: describe_mod.DescribeCache(
            cache_dir=_d, client=None
        ),
    )


# ---------------------------------------------------------------------------
# 1a. Release builds audit by default and fail on an unknown ref
# ---------------------------------------------------------------------------

class TestReleaseAuditsByDefault:

    def test_build_release_default_fails_on_unknown_ref(self, tmp_path, monkeypatch):
        """No skip_audit argument at all: the audit must run and hard-fail on
        a metric key absent from the describe cache.  (Pre-fix, the default
        was skip_audit=True and this built a zip with the bad ref inside;
        additionally the ref is this-bound, so even skip_audit=False would
        have been blind to it before change 2.)"""
        from vcfops_packaging.release_builder import build_release

        proj = _write_sm_project(tmp_path)
        manifest = _write_release_manifest(tmp_path, proj, "audit-default-unknown-ref")
        _patch_offline_cache(monkeypatch, _seed_describe_cache(tmp_path / "cache", {}))

        out = tmp_path / "out"
        with pytest.raises(AuditError, match="this_test_group\\|this_test_metric_v1"):
            build_release(manifest, out)
        assert not list(out.glob("*.zip")), "no zip may ship after an audit failure"

    def test_build_release_default_is_offline_no_client_construction(
        self, tmp_path, monkeypatch
    ):
        """Default release build must never construct a live client, even with
        credentials present in the environment (publish works with no live
        instance; the committed cache is the reference)."""
        from vcfops_packaging.release_builder import build_release
        import vcfops_common.client as client_mod
        import vcfops_packaging.describe as describe_mod

        constructions = []

        class _RecordingClient:
            def __init__(self, *a, **kw):
                constructions.append((a, kw))

        monkeypatch.setattr(client_mod, "VCFOpsClient", _RecordingClient)
        monkeypatch.setenv("VCFOPS_HOST", "https://ops.invalid")
        monkeypatch.setenv("VCFOPS_USER", "unit-test")
        monkeypatch.setenv("VCFOPS_PASSWORD", "unit-test")

        # Real make_cache (so the live/offline decision under test is real),
        # pointed at a seeded cache dir that resolves the ref.
        cache_dir = _seed_describe_cache(tmp_path / "cache", {
            "this_test_group|this_test_metric_v1": {
                "name": "This Test Metric", "default_monitored": True,
            },
        })
        real_make_cache = describe_mod.make_cache
        monkeypatch.setattr(
            describe_mod, "make_cache",
            lambda live=True, cache_dir=None, _d=cache_dir: real_make_cache(
                live=live, cache_dir=_d
            ),
        )

        proj = _write_sm_project(tmp_path)
        manifest = _write_release_manifest(tmp_path, proj, "audit-default-offline")
        artifacts = build_release(manifest, tmp_path / "out")

        assert len(artifacts) == 1 and artifacts[0].zip_path.exists()
        assert constructions == [], (
            "release build constructed a live VCFOpsClient despite the "
            "offline (live_describe=False) default"
        )

    def test_build_release_skip_audit_optout_still_works(self, tmp_path, monkeypatch):
        """The emergency opt-out: skip_audit=True builds even when the cache
        cannot resolve the ref (broken-cache day)."""
        from vcfops_packaging.release_builder import build_release

        proj = _write_sm_project(tmp_path)
        manifest = _write_release_manifest(tmp_path, proj, "audit-skip-optout")
        _patch_offline_cache(monkeypatch, _seed_describe_cache(tmp_path / "cache", {}))

        artifacts = build_release(manifest, tmp_path / "out", skip_audit=True)
        assert len(artifacts) == 1 and artifacts[0].zip_path.exists()


# ---------------------------------------------------------------------------
# 1b. Publish surfaces an audit failure as a publish failure
# ---------------------------------------------------------------------------

class TestPublishAuditOutcomes:

    def _publish_setup(self, tmp_path, monkeypatch, release_name: str):
        from test_publish_phase3 import _init_dist_repo, _patch_enumerate

        dist = _init_dist_repo(tmp_path)
        proj = _write_sm_project(tmp_path)
        releases_dir = tmp_path / "releases"
        releases_dir.mkdir()
        _write_release_manifest(releases_dir, proj, release_name)
        _patch_enumerate(monkeypatch, releases_dir)
        return dist

    def test_publish_audit_failure_is_publish_failure(self, tmp_path, monkeypatch):
        """Drives the REAL audit path (real _build_one_release seam default,
        real build_release, real audit) over a synthetic corpus whose only
        metric ref is unknown.  publish() must abort with a PublishError that
        names the failure AND the --skip-audit opt-out; no commit lands and
        the lockfile is released.  Never a warning."""
        from publish_seam_stubs import stub_validator
        from vcfops_packaging.publish import publish, PublishError

        dist = self._publish_setup(tmp_path, monkeypatch, "publish-audit-fail")
        _patch_offline_cache(monkeypatch, _seed_describe_cache(tmp_path / "cache", {}))

        before = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=str(dist), capture_output=True, text=True, check=True,
        ).stdout.strip()

        with pytest.raises(PublishError) as excinfo:
            publish(
                factory_repo=REPO_ROOT,
                dist_repo=dist,
                dry_run=False,
                no_push=True,
                use_pr=False,
                validator=stub_validator,
            )
        msg = str(excinfo.value)
        assert "Dependency audit FAILED" in msg
        assert "--skip-audit" in msg
        assert "this_test_group|this_test_metric_v1" in msg

        after = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=str(dist), capture_output=True, text=True, check=True,
        ).stdout.strip()
        assert after == before, "a commit landed despite the audit abort"
        assert not (dist / ".publish.lock").exists(), "lockfile leaked on abort"

    def test_publish_missing_cache_fails_loudly_naming_optout(
        self, tmp_path, monkeypatch
    ):
        """A missing describe cache (no file for the referenced pair) must
        fail the publish loudly, not silently skip the audit.  The message
        names the --skip-audit opt-out."""
        import vcfops_packaging.describe as describe_mod
        from publish_seam_stubs import stub_validator
        from vcfops_packaging.publish import publish, PublishError

        dist = self._publish_setup(tmp_path, monkeypatch, "publish-cache-missing")
        empty_dir = tmp_path / "empty-cache"
        empty_dir.mkdir()
        monkeypatch.setattr(
            describe_mod, "make_cache",
            lambda live=True, cache_dir=None: describe_mod.DescribeCache(
                cache_dir=empty_dir, client=None
            ),
        )

        with pytest.raises(PublishError) as excinfo:
            publish(
                factory_repo=REPO_ROOT,
                dist_repo=dist,
                dry_run=False,
                no_push=True,
                use_pr=False,
                validator=stub_validator,
            )
        msg = str(excinfo.value)
        assert "No describe cache files" in msg
        assert "--skip-audit" in msg

    def test_publish_skip_audit_optout_bypasses_audit(self, tmp_path, monkeypatch):
        """skip_audit=True (CLI --skip-audit) is the enumerated opt-out: with
        an unresolvable cache the publish still builds and commits."""
        from publish_seam_stubs import stub_validator
        from vcfops_packaging.publish import publish

        dist = self._publish_setup(tmp_path, monkeypatch, "publish-audit-skipped")
        _patch_offline_cache(monkeypatch, _seed_describe_cache(tmp_path / "cache", {}))

        result = publish(
            factory_repo=REPO_ROOT,
            dist_repo=dist,
            dry_run=False,
            no_push=True,
            use_pr=False,
            skip_audit=True,
            validator=stub_validator,
        )
        assert result.built, "opt-out publish should have built the release"

    def test_publish_cli_has_skip_audit_flag(self):
        """The publish subcommand exposes --skip-audit with the same warning
        wording as the build commands."""
        from vcfops_packaging.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["publish", "--dry-run", "--skip-audit"])
        assert args.skip_audit is True
        args = parser.parse_args(["publish", "--dry-run"])
        assert args.skip_audit is False


# ---------------------------------------------------------------------------
# 2. ${this, metric=...} resolution against resource_kinds
# ---------------------------------------------------------------------------

class TestThisRefResolution:

    def test_this_ref_resolves_against_each_declared_pair(self):
        """Pass case: one auditable reference per declared pair, key
        normalized like any other ref."""
        from vcfops_packaging.deps import _refs_from_formula

        refs = _refs_from_formula(
            "${this, metric=net:Aggregate of all instances|packetsPerSec}",
            "This Ref SM",
            [
                {"adapterKindKey": "VMWARE", "resourceKindKey": "VirtualMachine"},
                {"adapterKindKey": "VMWARE", "resourceKindKey": "HostSystem"},
            ],
        )
        got = {(r.adapter_kind, r.resource_kind, r.metric_key) for r in refs}
        assert got == {
            ("VMWARE", "VirtualMachine", "net|packetsPerSec"),
            ("VMWARE", "HostSystem", "net|packetsPerSec"),
        }
        assert all(r.source_desc == "SM 'This Ref SM'" for r in refs)

    def test_this_ref_without_resource_kinds_is_reported_not_skipped(self):
        """No-resource_kinds case: unauditable must raise, never silently
        extract zero references (the pre-fix blindness)."""
        from vcfops_packaging.deps import _refs_from_formula

        with pytest.raises(AuditError, match="resource_kinds"):
            _refs_from_formula("${this, metric=cpu|usage_average}", "Bare SM", None)
        with pytest.raises(AuditError, match="resource_kinds"):
            _refs_from_formula("${this, metric=cpu|usage_average}", "Bare SM", [])

    def test_this_ref_sm_reference_still_skipped(self):
        """A this-bound super-metric reference is not a built-in key and
        stays out of the describe-cache audit."""
        from vcfops_packaging.deps import _refs_from_formula

        refs = _refs_from_formula(
            '${this, metric=Super Metric|sm_11111111-2222-3333-4444-555555555555}',
            "SM Ref SM",
            [{"adapterKindKey": "VMWARE", "resourceKindKey": "VirtualMachine"}],
        )
        assert refs == []

    def test_this_ref_unknown_key_fails_full_audit_path(self, tmp_path, monkeypatch):
        """Executing-branch failure case through the real build path: an SM
        whose ONLY reference is this-bound, with a key absent from the cache,
        must fail the discrete build.  Pre-fix this built clean (the mutation
        target: disable the this-branch in _refs_from_formula and this test
        fails)."""
        from vcfops_packaging.discrete_builder import build_discrete

        proj = _write_sm_project(tmp_path, under_third_party=False)
        _patch_offline_cache(monkeypatch, _seed_describe_cache(tmp_path / "cache", {}))

        with pytest.raises(AuditError, match="this_test_group\\|this_test_metric_v1"):
            build_discrete(
                content_type="supermetric",
                item_name="Release Audit Test SM",
                output_dir=tmp_path / "out",
                extra_search_dirs=[proj],
                skip_audit=False,
                live_describe=False,
            )

    def test_this_ref_default_monitored_false_is_auto_added(
        self, tmp_path, monkeypatch
    ):
        """defaultMonitored classification applies to this-bound refs: a
        defaultMonitored=false key reached only via ${this} is auto-added to
        builtin_metric_enables in mode=auto."""
        import json
        import zipfile
        from vcfops_packaging.discrete_builder import build_discrete

        proj = _write_sm_project(tmp_path, under_third_party=False)
        _patch_offline_cache(monkeypatch, _seed_describe_cache(tmp_path / "cache", {
            "this_test_group|this_test_metric_v1": {
                "name": "This Test Metric", "default_monitored": False,
            },
        }))

        zip_path = build_discrete(
            content_type="supermetric",
            item_name="Release Audit Test SM",
            output_dir=tmp_path / "out",
            extra_search_dirs=[proj],
            skip_audit=False,
            live_describe=False,
            audit_mode="auto",
        )
        with zipfile.ZipFile(zip_path) as z:
            member = [m for m in z.namelist()
                      if m.endswith("content/builtin_metric_enables.json")]
            assert member, "auto-added this-ref did not land in builtin_metric_enables"
            payload = json.loads(z.read(member[0]).decode("utf-8"))
        assert payload[0]["metric_key"] == "this_test_group|this_test_metric_v1"
        assert "Auto-detected" in payload[0].get("reason", "")


# ---------------------------------------------------------------------------
# Known data point: the real corpus SM stays clean with the check active
# ---------------------------------------------------------------------------

@pytest.mark.slow
class TestKnownDataPointStorageActivePathCount:

    def test_storage_active_path_count_survives_offline_audit(self, tmp_path):
        """[VCF Content Factory] Storage Active Path Count uses
        ${this, metric=config|storageDevice|multipathInfo|numberofActivePath}
        on VMWARE/HostSystem; the key is present in the committed cache with
        default_monitored=true, so the newly-active this-ref check must pass
        it without auto-adds or failures."""
        from vcfops_packaging.discrete_builder import build_discrete

        zip_path = build_discrete(
            content_type="supermetric",
            item_name="[VCF Content Factory] Storage Active Path Count",
            output_dir=tmp_path / "out",
            skip_audit=False,
            live_describe=False,
        )
        assert zip_path.exists()

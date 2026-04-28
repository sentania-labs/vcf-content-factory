"""Tests for v2 item #1: <content-name>-<type> release-naming convention.

Covers:
  N1 — /release slug default = <source-stem>-<type> for each content type
  N2 — /release --slug override works
  N3 — /release produces correct manifest filename and name: field
  N4 — /bundle composer slug prompt defaults to <name>-bundle
  N5 — Validator hard-errors on bundle/release slug collision
  N6 — Validator WARNs on non-conforming new release manifest name
  N7 — Validator does NOT warn on grandfathered names
  N8 — Source-stem normalization (snake_case -> kebab-case) for /release defaults
"""
from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n")
    return path


def _minimal_dashboard_yaml(name: str = "[VCF Content Factory] Test Dashboard") -> str:
    return yaml.dump({
        "name": name,
        "description": "A test dashboard.",
        "widgets": [],
    }, default_flow_style=False)


def _minimal_bundle_yaml(slug: str) -> str:
    return yaml.dump({
        "name": slug,
        "description": "A test bundle.",
        "supermetrics": [],
        "views": [],
        "dashboards": [],
        "customgroups": [],
        "symptoms": [],
        "alerts": [],
        "reports": [],
        "recommendations": [],
        "managementpacks": [],
    }, default_flow_style=False)


def _minimal_release_yaml(name: str, source_rel: str) -> str:
    """Write a minimal release manifest pointing at source_rel."""
    return yaml.dump({
        "name": name,
        "version": "1.0",
        "description": f"Release of {name}.",
        "release_notes": "",
        "artifacts": [{"source": source_rel, "headline": True}],
        "deprecates": [],
    }, default_flow_style=False)


def _make_input_seq(responses: list):
    """Return an input_fn that pops responses in order. Raises EOFError when exhausted."""
    responses = list(responses)

    def _fn(prompt=""):
        if not responses:
            raise EOFError("input sequence exhausted")
        return responses.pop(0)

    return _fn


def _capture_output():
    """Return (output_fn, lines_list)."""
    lines = []

    def _fn(msg="", end="\n"):
        lines.append(str(msg))

    return _fn, lines


# ---------------------------------------------------------------------------
# N1 — /release slug default = <source-stem>-<type> for each content type
# ---------------------------------------------------------------------------

class TestReleaseSlugDefault:
    """N1: default slug for /release is <content-stem>-<type>."""

    def _compute_default_slug(self, source_stem: str, content_type: str) -> str:
        """Replicate the slug-computation logic from cmd_release."""
        stem_kebab = source_stem.replace("_", "-").lower()
        if content_type == "bundle":
            return stem_kebab
        return f"{stem_kebab}-{content_type}"

    @pytest.mark.parametrize("content_type", [
        "dashboard", "view", "supermetric", "customgroup", "report",
    ])
    def test_discrete_type_appends_type_suffix(self, content_type):
        slug = self._compute_default_slug("vks_core_consumption", content_type)
        assert slug == f"vks-core-consumption-{content_type}"

    def test_dashboard_slug(self):
        slug = self._compute_default_slug("my_dashboard", "dashboard")
        assert slug == "my-dashboard-dashboard"

    def test_view_slug(self):
        slug = self._compute_default_slug("vm_performance_view", "view")
        assert slug == "vm-performance-view-view"

    def test_supermetric_slug(self):
        slug = self._compute_default_slug("cpu_contention", "supermetric")
        assert slug == "cpu-contention-supermetric"

    def test_customgroup_slug(self):
        slug = self._compute_default_slug("prod_vms", "customgroup")
        assert slug == "prod-vms-customgroup"

    def test_report_slug(self):
        slug = self._compute_default_slug("weekly_capacity", "report")
        assert slug == "weekly-capacity-report"

    def test_bundle_no_suffix_added(self):
        """Bundle type: no automatic -bundle suffix; source stem used as-is."""
        slug = self._compute_default_slug("vks-core-consumption-bundle", "bundle")
        assert slug == "vks-core-consumption-bundle"
        assert not slug.endswith("-bundle-bundle")

    def test_bundle_plain_stem_unchanged(self):
        """A bundle whose file is just 'capacity-assessment' keeps that stem."""
        slug = self._compute_default_slug("capacity-assessment", "bundle")
        assert slug == "capacity-assessment"


# ---------------------------------------------------------------------------
# N2 — /release --slug override works
# ---------------------------------------------------------------------------

class TestReleaseSlugOverride:
    """N2: --slug flag bypasses the default naming convention."""

    def test_explicit_slug_used_verbatim(self):
        """When explicit_slug is provided, it is returned unchanged."""
        # Simulate the logic in cmd_release
        def compute_slug(source_stem, content_type, explicit_slug=None):
            if explicit_slug:
                return explicit_slug
            stem_kebab = source_stem.replace("_", "-").lower()
            if content_type == "bundle":
                return stem_kebab
            return f"{stem_kebab}-{content_type}"

        slug = compute_slug("vks_core_consumption", "dashboard", explicit_slug="legacy-dash-name")
        assert slug == "legacy-dash-name"

    def test_explicit_slug_suppresses_type_suffix(self):
        """explicit_slug on a non-bundle type does not gain a -<type> suffix."""
        def compute_slug(source_stem, content_type, explicit_slug=None):
            if explicit_slug:
                return explicit_slug
            stem_kebab = source_stem.replace("_", "-").lower()
            if content_type == "bundle":
                return stem_kebab
            return f"{stem_kebab}-{content_type}"

        slug = compute_slug("my_source", "report", explicit_slug="grandfather-report")
        assert slug == "grandfather-report"
        assert not slug.endswith("-report-report")

    def test_cli_accepts_slug_flag(self):
        """The argparse parser registers --slug on the release subcommand."""
        from vcfops_packaging.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["release", "dashboard", "my-source", "--slug", "custom-slug"])
        assert args.slug == "custom-slug"

    def test_cli_slug_default_is_none(self):
        """When --slug is not given, args.slug is None."""
        from vcfops_packaging.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["release", "dashboard", "my-source"])
        assert args.slug is None


# ---------------------------------------------------------------------------
# N3 — /release produces correct manifest filename and name: field
# ---------------------------------------------------------------------------

class TestReleaseManifestOutput:
    """N3: cmd_release writes releases/<slug>.yaml with correct name: field."""

    def _run_release(
        self,
        tmp_path: Path,
        content_type: str,
        source_stem: str,
        source_yaml_content: str,
        extra_args: list | None = None,
    ) -> subprocess.CompletedProcess:
        """Helper: set up a minimal repo in tmp_path and run cmd_release.

        Passes PYTHONPATH so vcfops_packaging resolves from the real repo root.
        """
        # Create source content directory and YAML
        type_dir_map = {
            "dashboard": "content/dashboards",
            "view": "content/views",
            "supermetric": "content/supermetrics",
            "customgroup": "content/customgroups",
            "report": "content/reports",
        }
        content_dir = tmp_path / type_dir_map[content_type]
        content_dir.mkdir(parents=True, exist_ok=True)
        source_file = content_dir / f"{source_stem}.yaml"
        source_file.write_text(source_yaml_content)

        cmd = [
            sys.executable, "-m", "vcfops_packaging", "release",
            content_type, source_stem,
            "--no-commit",
        ] + (extra_args or [])
        env = {"PYTHONPATH": str(REPO_ROOT), "PATH": "/usr/bin:/bin"}
        return subprocess.run(
            cmd, cwd=str(tmp_path), capture_output=True, text=True, env=env,
        )

    def test_dashboard_manifest_filename(self, tmp_path):
        """Releasing a dashboard writes releases/my-dash-dashboard.yaml."""
        result = self._run_release(
            tmp_path, "dashboard", "my_dash",
            yaml.dump({
                "name": "[VCF Content Factory] My Dash",
                "description": "A dashboard.",
                "released": False,
                "widgets": [],
            }),
        )
        assert result.returncode == 0, (
            f"cmd_release failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        manifest = tmp_path / "releases" / "my-dash-dashboard.yaml"
        assert manifest.exists(), f"Expected {manifest} to be created"
        data = yaml.safe_load(manifest.read_text())
        assert data["name"] == "my-dash-dashboard"

    def test_report_manifest_filename(self, tmp_path):
        """Releasing a report writes releases/weekly-cap-report.yaml."""
        result = self._run_release(
            tmp_path, "report", "weekly_cap",
            yaml.dump({
                "name": "[VCF Content Factory] Weekly Cap",
                "description": "A report.",
                "released": False,
            }),
        )
        assert result.returncode == 0, (
            f"cmd_release failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        manifest = tmp_path / "releases" / "weekly-cap-report.yaml"
        assert manifest.exists(), f"Expected {manifest} to be created"
        data = yaml.safe_load(manifest.read_text())
        assert data["name"] == "weekly-cap-report"

    def test_slug_override_changes_filename(self, tmp_path):
        """--slug overrides the default filename."""
        result = self._run_release(
            tmp_path, "dashboard", "my_dash",
            yaml.dump({
                "name": "[VCF Content Factory] My Dash",
                "description": "A dashboard.",
                "released": False,
                "widgets": [],
            }),
            extra_args=["--slug", "legacy-dashboard-name"],
        )
        assert result.returncode == 0, (
            f"cmd_release with --slug failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        manifest = tmp_path / "releases" / "legacy-dashboard-name.yaml"
        assert manifest.exists(), f"Expected {manifest} with override slug"
        data = yaml.safe_load(manifest.read_text())
        assert data["name"] == "legacy-dashboard-name"
        # Default-slug file must NOT exist
        default_manifest = tmp_path / "releases" / "my-dash-dashboard.yaml"
        assert not default_manifest.exists(), "Default-slug file should not be created when --slug given"

    def test_source_released_flag_flipped(self, tmp_path):
        """After /release, the source YAML's released: field is True."""
        result = self._run_release(
            tmp_path, "dashboard", "flip_test",
            yaml.dump({
                "name": "[VCF Content Factory] Flip Test",
                "description": "For flag flip test.",
                "released": False,
                "widgets": [],
            }),
        )
        assert result.returncode == 0, (
            f"cmd_release failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        source = tmp_path / "content" / "dashboards" / "flip_test.yaml"
        data = yaml.safe_load(source.read_text())
        assert data.get("released") is True


# ---------------------------------------------------------------------------
# N4 — /bundle composer slug prompt defaults to <name>-bundle
# ---------------------------------------------------------------------------

class TestBundleComposerSlugDefault:
    """N4: /bundle composer prompts suggest <name>-bundle when user omits suffix."""

    def test_prompt_suggests_bundle_suffix(self, tmp_path):
        """When user enters 'my-thing', composer suggests 'my-thing-bundle'."""
        from vcfops_packaging.composer import compose_bundle

        out_fn, lines = _capture_output()
        # Sequence:
        #   1. First slug prompt: "my-thing"  (no -bundle suffix)
        #   2. Confirmation prompt: "" (accept suggested my-thing-bundle)
        #   3. display_name: ""
        #   4. description: "Test bundle" + END
        #   5. 9 type prompts: ""
        responses = (
            ["my-thing"]       # initial slug input (no -bundle suffix)
            + [""]             # accept suggested my-thing-bundle
            + [""]             # display name
            + ["Test bundle", "END"]
            + [""] * 9         # all content type prompts
        )
        rc = compose_bundle(
            slug=None,
            dry_run=True,
            force=False,
            repo_root=tmp_path,
            input_fn=_make_input_seq(responses),
            output_fn=out_fn,
        )
        assert rc == 0, f"compose_bundle failed: {''.join(lines)}"
        combined = "\n".join(lines)
        # The suggestion must appear in output
        assert "my-thing-bundle" in combined, (
            f"Expected 'my-thing-bundle' suggestion in output:\n{combined}"
        )

    def test_prompt_does_not_double_suffix(self, tmp_path):
        """When user already types 'my-thing-bundle', no double -bundle suffix added."""
        from vcfops_packaging.composer import compose_bundle

        out_fn, lines = _capture_output()
        responses = (
            ["my-thing-bundle"]   # already has -bundle suffix
            # no second slug prompt since no convention suggestion needed
            + [""]                # display name
            + ["Test bundle description", "END"]
            + [""] * 9
        )
        rc = compose_bundle(
            slug=None,
            dry_run=True,
            force=False,
            repo_root=tmp_path,
            input_fn=_make_input_seq(responses),
            output_fn=out_fn,
        )
        assert rc == 0, f"compose_bundle failed: {''.join(lines)}"
        combined = "\n".join(lines)
        # Must not contain double suffix
        assert "my-thing-bundle-bundle" not in combined, (
            f"Double -bundle suffix found:\n{combined}"
        )
        assert "my-thing-bundle" in combined

    def test_user_can_override_suggested_slug(self, tmp_path):
        """User can override the suggested slug by typing a different value."""
        from vcfops_packaging.composer import compose_bundle

        out_fn, lines = _capture_output()
        responses = (
            ["my-thing"]           # initial slug (no -bundle)
            + ["custom-override"]  # override the suggestion
            + [""]                 # display name
            + ["Override description", "END"]
            + [""] * 9
        )
        rc = compose_bundle(
            slug=None,
            dry_run=True,
            force=False,
            repo_root=tmp_path,
            input_fn=_make_input_seq(responses),
            output_fn=out_fn,
        )
        assert rc == 0, f"compose_bundle failed: {''.join(lines)}"
        combined = "\n".join(lines)
        # The dry-run YAML output must show the overridden slug as the bundle name
        assert "name: custom-override" in combined, (
            f"Expected 'name: custom-override' in YAML output:\n{combined}"
        )
        # The dry-run header must reference the overridden slug filename
        assert "bundles/custom-override.yaml" in combined, (
            f"Expected 'bundles/custom-override.yaml' in dry-run header:\n{combined}"
        )
        # The final bundle name must NOT be the suggestion — confirmed by YAML name field
        assert "name: my-thing-bundle" not in combined, (
            f"Bundle name should be custom-override, not my-thing-bundle:\n{combined}"
        )

    def test_slug_arg_bypasses_prompt_entirely(self, tmp_path):
        """When slug is passed as an argument, no slug prompt is shown."""
        from vcfops_packaging.composer import compose_bundle

        out_fn, lines = _capture_output()
        # With slug as arg: no slug prompt, no confirmation prompt
        responses = (
            [""]                    # display name
            + ["Arg slug test", "END"]
            + [""] * 9
        )
        rc = compose_bundle(
            slug="direct-bundle",
            dry_run=True,
            force=False,
            repo_root=tmp_path,
            input_fn=_make_input_seq(responses),
            output_fn=out_fn,
        )
        assert rc == 0, f"compose_bundle failed: {''.join(lines)}"
        combined = "\n".join(lines)
        assert "direct-bundle" in combined


# ---------------------------------------------------------------------------
# N5 — Validator hard-errors on bundle/release slug collision
# ---------------------------------------------------------------------------

class TestValidatorCollisionHardError:
    """N5: validate exits non-zero when a slug appears in both bundles/ and releases/."""

    def _make_collision_repo(self, tmp_path: Path, slug: str) -> None:
        """Create a minimal repo with a colliding slug in bundles/ and releases/.

        The release manifest headlines a DIFFERENT source (bundles/<slug>_source.yaml),
        NOT the bundle file itself, so this is a genuine collision — not a
        legitimate bundle-release pairing.
        """
        # Create bundles/<slug>.yaml
        bundle_path = tmp_path / "bundles" / f"{slug}.yaml"
        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        bundle_path.write_text(_minimal_bundle_yaml(slug))

        # Create a source content file for the release manifest to reference
        # (intentionally different from bundles/<slug>.yaml to make it a real collision)
        source_path = tmp_path / "bundles" / f"{slug}_source.yaml"
        source_path.write_text(_minimal_bundle_yaml(f"{slug}-source"))

        # Create releases/<slug>.yaml (collision! — headlines a different bundle)
        release_path = tmp_path / "releases" / f"{slug}.yaml"
        release_path.parent.mkdir(parents=True, exist_ok=True)
        release_path.write_text(_minimal_release_yaml(slug, f"bundles/{slug}_source.yaml"))

    def test_collision_causes_nonzero_exit(self, tmp_path):
        """Validator returns non-zero on a slug collision."""
        self._make_collision_repo(tmp_path, "foo-bundle")
        env = {"PYTHONPATH": str(REPO_ROOT), "PATH": "/usr/bin:/bin"}
        result = subprocess.run(
            [sys.executable, "-m", "vcfops_packaging", "validate"],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode != 0, (
            f"Expected non-zero exit on slug collision, but got 0.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_collision_error_message_names_both_files(self, tmp_path):
        """Collision error message names both the bundle file and the release manifest."""
        self._make_collision_repo(tmp_path, "collision-test")
        env = {"PYTHONPATH": str(REPO_ROOT), "PATH": "/usr/bin:/bin"}
        result = subprocess.run(
            [sys.executable, "-m", "vcfops_packaging", "validate"],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            env=env,
        )
        combined = result.stdout + result.stderr
        assert "collision-test" in combined, (
            f"Expected collision slug in error output:\n{combined}"
        )
        # Should mention both files
        assert "bundle" in combined.lower(), (
            f"Expected 'bundle' in collision error:\n{combined}"
        )

    def test_no_collision_on_different_slugs(self, tmp_path):
        """No error when bundle slug and release manifest name are different."""
        # bundles/my-bundle.yaml
        bundle_path = tmp_path / "bundles" / "my-bundle.yaml"
        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        bundle_path.write_text(_minimal_bundle_yaml("my-bundle"))

        # releases/my-bundle-bundle.yaml (different slug — follows convention)
        source_path = tmp_path / "bundles" / "my-bundle.yaml"
        release_path = tmp_path / "releases" / "my-bundle-bundle.yaml"
        release_path.parent.mkdir(parents=True, exist_ok=True)
        release_path.write_text(_minimal_release_yaml("my-bundle-bundle", "bundles/my-bundle.yaml"))

        # Also update the bundle to have released: true so flag-state check passes
        data = yaml.safe_load(bundle_path.read_text())
        data["released"] = True
        bundle_path.write_text(yaml.dump(data))

        result = subprocess.run(
            [sys.executable, "-m", "vcfops_packaging", "validate"],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
        )
        combined = result.stdout + result.stderr
        assert "slug collision" not in combined, (
            f"Unexpected slug collision error:\n{combined}"
        )

    def test_check_bundle_release_collision_api(self, tmp_path):
        """check_bundle_release_collision() returns an error string on collision."""
        from vcfops_packaging.releases import check_bundle_release_collision, load_release

        # Create a bundle
        bundle_dir = tmp_path / "bundles"
        bundle_dir.mkdir()
        (bundle_dir / "shared-slug.yaml").write_text(_minimal_bundle_yaml("shared-slug"))

        # Create a source file for the release
        source_file = bundle_dir / "other-source.yaml"
        source_file.write_text(_minimal_bundle_yaml("other-source"))

        # Create a release with the SAME slug
        releases_dir = tmp_path / "releases"
        releases_dir.mkdir()
        (releases_dir / "shared-slug.yaml").write_text(
            _minimal_release_yaml("shared-slug", "bundles/other-source.yaml")
        )

        release = load_release(releases_dir / "shared-slug.yaml", repo_root=tmp_path)
        errors = check_bundle_release_collision(bundle_dir, [release])
        assert len(errors) == 1
        assert "shared-slug" in errors[0]
        assert "collision" in errors[0].lower()


# ---------------------------------------------------------------------------
# N5b — Legitimate bundle-release pairing does NOT trigger collision error
# ---------------------------------------------------------------------------

class TestBundleReleaseLegitimatePairing:
    """N5b: collision check is skipped when the release manifest headlines the bundle."""

    def test_bundle_release_pairing_no_error_api(self, tmp_path):
        """check_bundle_release_collision() returns no errors when the release
        manifest's headline artifact points at bundles/<slug>.yaml."""
        from vcfops_packaging.releases import check_bundle_release_collision, load_release

        bundle_dir = tmp_path / "bundles"
        bundle_dir.mkdir()
        slug = "vks-core-consumption-bundle"
        bundle_path = bundle_dir / f"{slug}.yaml"
        bundle_data = _minimal_bundle_yaml(slug)
        bundle_path.write_text(bundle_data)
        # Also set released: true so flag-state check doesn't interfere
        import yaml as _yaml
        bd = _yaml.safe_load(bundle_data)
        bd["released"] = True
        bundle_path.write_text(_yaml.dump(bd))

        releases_dir = tmp_path / "releases"
        releases_dir.mkdir()
        # Release manifest headlines the bundle itself — this is the legitimate pairing
        (releases_dir / f"{slug}.yaml").write_text(
            _minimal_release_yaml(slug, f"bundles/{slug}.yaml")
        )

        release = load_release(releases_dir / f"{slug}.yaml", repo_root=tmp_path)
        errors = check_bundle_release_collision(bundle_dir, [release])
        assert errors == [], (
            f"Legitimate bundle-release pairing should not be flagged as collision: {errors}"
        )

    def test_bundle_release_pairing_no_error_subprocess(self, tmp_path):
        """validate exits zero when bundles/<slug>.yaml + releases/<slug>.yaml
        where the release headlines that same bundle."""
        import yaml as _yaml

        slug = "my-paired-bundle"
        bundle_dir = tmp_path / "bundles"
        bundle_dir.mkdir()
        bundle_path = bundle_dir / f"{slug}.yaml"
        bd = _yaml.safe_load(_minimal_bundle_yaml(slug))
        bd["released"] = True
        bundle_path.write_text(_yaml.dump(bd))

        releases_dir = tmp_path / "releases"
        releases_dir.mkdir()
        (releases_dir / f"{slug}.yaml").write_text(
            _minimal_release_yaml(slug, f"bundles/{slug}.yaml")
        )

        env = {"PYTHONPATH": str(REPO_ROOT), "PATH": "/usr/bin:/bin"}
        result = subprocess.run(
            [sys.executable, "-m", "vcfops_packaging", "validate"],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            env=env,
        )
        combined = result.stdout + result.stderr
        assert "slug collision" not in combined, (
            f"Legitimate bundle-release pairing should not produce collision error:\n{combined}"
        )

    def test_non_pairing_collision_still_errors(self, tmp_path):
        """When the release manifest headlines a DIFFERENT source (not the bundle),
        the collision error still fires."""
        from vcfops_packaging.releases import check_bundle_release_collision, load_release

        bundle_dir = tmp_path / "bundles"
        bundle_dir.mkdir()
        slug = "shared-name"
        (bundle_dir / f"{slug}.yaml").write_text(_minimal_bundle_yaml(slug))
        # A different source file
        other_source = bundle_dir / "other-source.yaml"
        other_source.write_text(_minimal_bundle_yaml("other-source"))

        releases_dir = tmp_path / "releases"
        releases_dir.mkdir()
        # Release has same slug but headlines a DIFFERENT source — real collision
        (releases_dir / f"{slug}.yaml").write_text(
            _minimal_release_yaml(slug, "bundles/other-source.yaml")
        )

        release = load_release(releases_dir / f"{slug}.yaml", repo_root=tmp_path)
        errors = check_bundle_release_collision(bundle_dir, [release])
        assert len(errors) == 1, (
            f"Expected 1 collision error for non-pairing case, got: {errors}"
        )
        assert "slug collision" in errors[0]
        assert slug in errors[0]

    def test_real_repo_vks_bundle_pairing_clean(self):
        """Live repo: vks-core-consumption-bundle pairing validates without collision."""
        from vcfops_packaging.releases import (
            check_bundle_release_collision,
            load_all_releases,
        )

        releases = load_all_releases(REPO_ROOT / "releases", repo_root=REPO_ROOT)
        bundles_dir = REPO_ROOT / "bundles"
        errors = check_bundle_release_collision(bundles_dir, releases)
        assert errors == [], (
            f"vks-core-consumption-bundle pairing should not be a collision:\n"
            + "\n".join(errors)
        )


# ---------------------------------------------------------------------------
# N6 — Validator WARNs on non-conforming new release manifest name
# ---------------------------------------------------------------------------

class TestValidatorNamingConventionWarn:
    """N6: validate emits WARN on a release name without a recognized type suffix."""

    def test_nonconforming_name_produces_warn(self, tmp_path):
        """A release named 'some-thing' (no type suffix) produces a WARN."""
        from vcfops_packaging.releases import (
            check_release_naming_convention,
            load_release,
        )

        # Create a dummy source file
        source = tmp_path / "bundles" / "dummy.yaml"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(_minimal_bundle_yaml("dummy"))

        releases_dir = tmp_path / "releases"
        releases_dir.mkdir()
        (releases_dir / "some-thing.yaml").write_text(
            _minimal_release_yaml("some-thing", "bundles/dummy.yaml")
        )

        r = load_release(releases_dir / "some-thing.yaml", repo_root=tmp_path)
        warnings = check_release_naming_convention([r])
        assert len(warnings) == 1, f"Expected 1 warning, got: {warnings}"
        assert "some-thing" in warnings[0]
        assert "WARN" in warnings[0]

    def test_conforming_name_no_warn(self, tmp_path):
        """A release named 'vks-core-consumption-dashboard' produces no warning."""
        from vcfops_packaging.releases import (
            check_release_naming_convention,
            load_release,
        )

        source = tmp_path / "content" / "dashboards" / "vks_core_consumption.yaml"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(yaml.dump({
            "name": "[VCF Content Factory] VKS Core Consumption",
            "description": "A dashboard.",
            "released": True,
            "widgets": [],
        }))

        releases_dir = tmp_path / "releases"
        releases_dir.mkdir()
        (releases_dir / "vks-core-consumption-dashboard.yaml").write_text(
            _minimal_release_yaml(
                "vks-core-consumption-dashboard",
                "content/dashboards/vks_core_consumption.yaml",
            )
        )

        r = load_release(
            releases_dir / "vks-core-consumption-dashboard.yaml",
            repo_root=tmp_path,
        )
        warnings = check_release_naming_convention([r])
        assert warnings == [], f"Conforming name should produce no warnings: {warnings}"

    @pytest.mark.parametrize("suffix", [
        "dashboard", "view", "supermetric", "customgroup",
        "report", "bundle", "managementpack", "alert", "symptom", "recommendation",
    ])
    def test_all_recognized_suffixes_pass(self, tmp_path, suffix):
        """Each recognized type suffix produces no WARN when used correctly."""
        from vcfops_packaging.releases import (
            check_release_naming_convention,
            load_release,
        )

        source = tmp_path / "bundles" / "src.yaml"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(_minimal_bundle_yaml("src"))

        releases_dir = tmp_path / "releases"
        releases_dir.mkdir()
        release_name = f"my-content-{suffix}"
        (releases_dir / f"{release_name}.yaml").write_text(
            _minimal_release_yaml(release_name, "bundles/src.yaml")
        )

        r = load_release(releases_dir / f"{release_name}.yaml", repo_root=tmp_path)
        warnings = check_release_naming_convention([r])
        assert warnings == [], (
            f"Suffix {suffix!r} should be recognized, but got warning: {warnings}"
        )

    def test_warn_message_lists_recognized_types(self, tmp_path):
        """WARN message references the recognized type list."""
        from vcfops_packaging.releases import (
            check_release_naming_convention,
            load_release,
        )

        source = tmp_path / "bundles" / "dummy.yaml"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(_minimal_bundle_yaml("dummy"))

        releases_dir = tmp_path / "releases"
        releases_dir.mkdir()
        (releases_dir / "bad-name.yaml").write_text(
            _minimal_release_yaml("bad-name", "bundles/dummy.yaml")
        )

        r = load_release(releases_dir / "bad-name.yaml", repo_root=tmp_path)
        warnings = check_release_naming_convention([r])
        assert len(warnings) == 1
        # Should hint at recognized types
        assert "dashboard" in warnings[0]


# ---------------------------------------------------------------------------
# N7 — Validator does NOT warn on grandfathered names
# ---------------------------------------------------------------------------

class TestGrandfatherList:
    """N7: names in _LEGACY_RELEASE_NAMES are skipped by the WARN check."""

    def test_demand_driven_capacity_v2_not_warned(self):
        """demand-driven-capacity-v2 is grandfathered — no WARN."""
        from vcfops_packaging.releases import (
            _LEGACY_RELEASE_NAMES,
            check_release_naming_convention,
        )
        assert "demand-driven-capacity-v2" in _LEGACY_RELEASE_NAMES, (
            "demand-driven-capacity-v2 should be in the grandfather list"
        )

    def test_idps_planner_not_warned(self):
        """idps-planner is grandfathered — no WARN."""
        from vcfops_packaging.releases import _LEGACY_RELEASE_NAMES
        assert "idps-planner" in _LEGACY_RELEASE_NAMES, (
            "idps-planner should be in the grandfather list"
        )

    def test_real_repo_releases_produce_no_naming_warnings(self):
        """Real repo: no naming convention warnings for any existing release manifest."""
        from vcfops_packaging.releases import (
            check_release_naming_convention,
            load_all_releases,
        )

        releases = load_all_releases(REPO_ROOT / "releases", repo_root=REPO_ROOT)
        warnings = check_release_naming_convention(releases)
        assert warnings == [], (
            f"Real repo releases produced unexpected naming warnings:\n"
            + "\n".join(warnings)
        )

    def test_grandfather_names_are_frozenset(self):
        """_LEGACY_RELEASE_NAMES is a frozenset (immutable, O(1) lookup)."""
        from vcfops_packaging.releases import _LEGACY_RELEASE_NAMES
        assert isinstance(_LEGACY_RELEASE_NAMES, frozenset), (
            f"_LEGACY_RELEASE_NAMES should be a frozenset, got {type(_LEGACY_RELEASE_NAMES)}"
        )

    def test_check_naming_skips_grandfathered_even_without_suffix(self, tmp_path):
        """A grandfathered name without a type suffix still produces no warning."""
        from vcfops_packaging.releases import (
            check_release_naming_convention,
            _LEGACY_RELEASE_NAMES,
        )
        # Add a synthetic grandfathered name for this test using a dataclass mock
        from vcfops_packaging.releases import ReleaseDef, ReleaseArtifact

        # Create a minimal source file so the path resolves
        src = tmp_path / "bundles" / "source.yaml"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text(_minimal_bundle_yaml("source"))

        manifest = tmp_path / "releases" / "demand-driven-capacity-v2.yaml"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text("name: placeholder\n")

        rdef = ReleaseDef(
            name="demand-driven-capacity-v2",    # grandfathered
            version="1.1",
            description="Grandfathered release",
            release_notes="",
            artifacts=[ReleaseArtifact(
                source="bundles/source.yaml",
                source_path=src,
                headline=True,
            )],
            deprecates=[],
            manifest_path=manifest,
        )
        warnings = check_release_naming_convention([rdef])
        assert warnings == [], f"Grandfathered name should produce no warning: {warnings}"


# ---------------------------------------------------------------------------
# N8 — Source-stem normalization (snake_case -> kebab-case)
# ---------------------------------------------------------------------------

class TestSourceStemNormalization:
    """N8: snake_case stems are normalized to kebab-case in slug defaults."""

    def _slug_from_stem(self, stem: str, content_type: str) -> str:
        """Replicate cmd_release slug computation."""
        stem_kebab = stem.replace("_", "-").lower()
        if content_type == "bundle":
            return stem_kebab
        return f"{stem_kebab}-{content_type}"

    def test_underscores_become_hyphens(self):
        assert self._slug_from_stem("my_view_name", "view") == "my-view-name-view"

    def test_mixed_case_lowercased(self):
        assert self._slug_from_stem("MyDashboard", "dashboard") == "mydashboard-dashboard"

    def test_already_kebab_unchanged(self):
        assert self._slug_from_stem("my-report", "report") == "my-report-report"

    def test_uppercase_with_underscores(self):
        assert self._slug_from_stem("VM_PERF_DASHBOARD", "dashboard") == "vm-perf-dashboard-dashboard"

    def test_snake_bundle_stem_normalized(self):
        """Bundle type: underscores normalized but no suffix added."""
        assert self._slug_from_stem("my_bundle", "bundle") == "my-bundle"

    def test_vks_core_consumption_normalization(self):
        """vks_core_consumption -> vks-core-consumption-<type>."""
        for t in ("dashboard", "report", "view"):
            slug = self._slug_from_stem("vks_core_consumption", t)
            assert slug == f"vks-core-consumption-{t}", (
                f"For type {t!r}, expected vks-core-consumption-{t}, got {slug}"
            )


# ---------------------------------------------------------------------------
# Integration: real repo still validates clean after convention checks
# ---------------------------------------------------------------------------

class TestRealRepoValidateIntegration:
    """Smoke: real repo validate still passes with all convention checks active."""

    def test_real_repo_validate_exits_zero(self):
        """python3 -m vcfops_packaging validate exits 0 on the real repo."""
        result = subprocess.run(
            [sys.executable, "-m", "vcfops_packaging", "validate"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"packaging validate failed after convention checks added:\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_real_repo_no_collision_errors(self):
        """Real repo has no slug collision between bundles/ and releases/."""
        from vcfops_packaging.releases import (
            check_bundle_release_collision,
            load_all_releases,
        )

        releases = load_all_releases(REPO_ROOT / "releases", repo_root=REPO_ROOT)
        bundles_dir = REPO_ROOT / "bundles"
        errors = check_bundle_release_collision(bundles_dir, releases)
        assert errors == [], (
            f"Real repo has unexpected slug collisions:\n" + "\n".join(errors)
        )

    def test_real_repo_no_naming_warnings(self):
        """Real repo has no naming convention warnings (all grandfathered or conforming)."""
        from vcfops_packaging.releases import (
            check_release_naming_convention,
            load_all_releases,
        )

        releases = load_all_releases(REPO_ROOT / "releases", repo_root=REPO_ROOT)
        warnings = check_release_naming_convention(releases)
        assert warnings == [], (
            f"Real repo releases have unexpected naming warnings:\n"
            + "\n".join(warnings)
        )

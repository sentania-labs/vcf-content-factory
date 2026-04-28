"""Phase 2 validator-extension tests.

Covers three new validation surfaces introduced in Phase 2:

  P1 — PROJECT.yaml schema validation
       Required fields enforced; name/dir mismatch caught; factory_native: true rejected.

  P2 — Slug uniqueness across both provenances
       Same filename stem in content/ and third_party/*/ is an error.
       Same slug across two third-party projects is an error.
       Slug collision in a different content type is allowed.

  P3 — Project-membership boundary check
       A third-party dashboard that pulls in a view from outside its own
       project subtree is an error.
       Factory-native dashboards are unconstrained.

All tests are pure-Python and use tmp_path fixtures so no real repo content
is mutated, no network calls are made, and no install commands are run.
"""
from __future__ import annotations

import textwrap
from pathlib import Path
from typing import List

import pytest
import yaml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(path: Path, content: str) -> Path:
    """Write ``content`` to ``path``, creating parents as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n")
    return path


def _minimal_project_yaml(name: str, **overrides) -> dict:
    """Return a minimal valid PROJECT.yaml data dict."""
    data = {
        "name": name,
        "display_name": f"{name} Display",
        "factory_native": False,
        "author": "Test Author",
        "license": "MIT",
        "description": "A test project.",
    }
    data.update(overrides)
    return data


def _write_project_yaml(project_dir: Path, name: str, **overrides) -> Path:
    data = _minimal_project_yaml(name, **overrides)
    p = project_dir / "PROJECT.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.dump(data, default_flow_style=False))
    return p


def _write_sm_yaml(sm_dir: Path, stem: str) -> Path:
    """Write a minimal (structurally valid for filename purposes) SM YAML."""
    p = sm_dir / f"{stem}.yaml"
    sm_dir.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.dump({
        "name": f"[VCF Content Factory] SM {stem}",
        "formula": "${this, metric=cpu|usage_average}",
        "resource_kinds": [{"resource_kind_key": "VirtualMachine", "adapter_kind_key": "VMWARE"}],
    }, default_flow_style=False))
    return p


# ---------------------------------------------------------------------------
# P1 — PROJECT.yaml schema validation
# ---------------------------------------------------------------------------

class TestProjectYamlValidation:
    """P1: PROJECT.yaml schema enforcement."""

    def test_valid_project_loads(self, tmp_path):
        """A fully-valid PROJECT.yaml loads without error."""
        from vcfops_packaging.project import load_project

        proj_dir = tmp_path / "my-project"
        proj_dir.mkdir()
        _write_project_yaml(proj_dir, "my-project")

        result = load_project(proj_dir / "PROJECT.yaml")
        assert result.name == "my-project"
        assert result.display_name == "my-project Display"
        assert result.factory_native is False
        assert result.author == "Test Author"
        assert result.license == "MIT"

    def test_missing_name_is_error(self, tmp_path):
        """Missing 'name' field raises ProjectValidationError."""
        from vcfops_packaging.project import load_project, ProjectValidationError

        proj_dir = tmp_path / "my-project"
        proj_dir.mkdir()
        data = _minimal_project_yaml("my-project")
        del data["name"]
        p = proj_dir / "PROJECT.yaml"
        p.write_text(yaml.dump(data))

        with pytest.raises(ProjectValidationError, match="'name' is required"):
            load_project(p)

    def test_name_dir_mismatch_is_error(self, tmp_path):
        """'name' not matching parent directory name raises ProjectValidationError."""
        from vcfops_packaging.project import load_project, ProjectValidationError

        proj_dir = tmp_path / "actual-dir-name"
        proj_dir.mkdir()
        data = _minimal_project_yaml("wrong-name")  # name != dir name
        p = proj_dir / "PROJECT.yaml"
        p.write_text(yaml.dump(data))

        with pytest.raises(ProjectValidationError, match="must match the parent directory name"):
            load_project(p)

    def test_missing_display_name_is_error(self, tmp_path):
        """Missing 'display_name' raises ProjectValidationError."""
        from vcfops_packaging.project import load_project, ProjectValidationError

        proj_dir = tmp_path / "my-project"
        proj_dir.mkdir()
        data = _minimal_project_yaml("my-project")
        del data["display_name"]
        p = proj_dir / "PROJECT.yaml"
        p.write_text(yaml.dump(data))

        with pytest.raises(ProjectValidationError, match="'display_name' is required"):
            load_project(p)

    def test_factory_native_absent_is_error(self, tmp_path):
        """Missing 'factory_native' raises ProjectValidationError."""
        from vcfops_packaging.project import load_project, ProjectValidationError

        proj_dir = tmp_path / "my-project"
        proj_dir.mkdir()
        data = _minimal_project_yaml("my-project")
        del data["factory_native"]
        p = proj_dir / "PROJECT.yaml"
        p.write_text(yaml.dump(data))

        with pytest.raises(ProjectValidationError, match="'factory_native' is required"):
            load_project(p)

    def test_factory_native_true_is_error(self, tmp_path):
        """factory_native: true in a PROJECT.yaml raises ProjectValidationError."""
        from vcfops_packaging.project import load_project, ProjectValidationError

        proj_dir = tmp_path / "my-project"
        proj_dir.mkdir()
        data = _minimal_project_yaml("my-project", factory_native=True)
        p = proj_dir / "PROJECT.yaml"
        p.write_text(yaml.dump(data))

        with pytest.raises(ProjectValidationError, match="must be false for third-party"):
            load_project(p)

    def test_missing_author_is_error(self, tmp_path):
        """Missing 'author' raises ProjectValidationError."""
        from vcfops_packaging.project import load_project, ProjectValidationError

        proj_dir = tmp_path / "my-project"
        proj_dir.mkdir()
        data = _minimal_project_yaml("my-project")
        del data["author"]
        p = proj_dir / "PROJECT.yaml"
        p.write_text(yaml.dump(data))

        with pytest.raises(ProjectValidationError, match="'author' is required"):
            load_project(p)

    def test_missing_license_is_error(self, tmp_path):
        """Missing 'license' raises ProjectValidationError."""
        from vcfops_packaging.project import load_project, ProjectValidationError

        proj_dir = tmp_path / "my-project"
        proj_dir.mkdir()
        data = _minimal_project_yaml("my-project")
        del data["license"]
        p = proj_dir / "PROJECT.yaml"
        p.write_text(yaml.dump(data))

        with pytest.raises(ProjectValidationError, match="'license' is required"):
            load_project(p)

    def test_missing_description_is_error(self, tmp_path):
        """Missing 'description' raises ProjectValidationError."""
        from vcfops_packaging.project import load_project, ProjectValidationError

        proj_dir = tmp_path / "my-project"
        proj_dir.mkdir()
        data = _minimal_project_yaml("my-project")
        del data["description"]
        p = proj_dir / "PROJECT.yaml"
        p.write_text(yaml.dump(data))

        with pytest.raises(ProjectValidationError, match="'description' is required"):
            load_project(p)

    def test_builtin_metric_enables_missing_field_is_error(self, tmp_path):
        """A builtin_metric_enables entry missing 'reason' raises an error."""
        from vcfops_packaging.project import load_project, ProjectValidationError

        proj_dir = tmp_path / "my-project"
        proj_dir.mkdir()
        data = _minimal_project_yaml("my-project")
        data["builtin_metric_enables"] = [
            {
                "adapter_kind": "VMWARE",
                "resource_kind": "VirtualMachine",
                "metric_key": "net|packetsPerSec",
                # 'reason' deliberately omitted
            }
        ]
        p = proj_dir / "PROJECT.yaml"
        p.write_text(yaml.dump(data))

        with pytest.raises(ProjectValidationError, match="reason"):
            load_project(p)

    def test_builtin_metric_enables_full_entry_valid(self, tmp_path):
        """A PROJECT.yaml with a complete builtin_metric_enables entry loads."""
        from vcfops_packaging.project import load_project

        proj_dir = tmp_path / "my-project"
        proj_dir.mkdir()
        data = _minimal_project_yaml("my-project")
        data["builtin_metric_enables"] = [
            {
                "adapter_kind": "VMWARE",
                "resource_kind": "VirtualMachine",
                "metric_key": "net|packetsPerSec",
                "reason": "required by widget X",
            }
        ]
        p = proj_dir / "PROJECT.yaml"
        p.write_text(yaml.dump(data))

        result = load_project(p)
        assert len(result.builtin_metric_enables) == 1
        assert result.builtin_metric_enables[0].metric_key == "net|packetsPerSec"

    def test_source_block_optional(self, tmp_path):
        """PROJECT.yaml without a 'source' block loads cleanly."""
        from vcfops_packaging.project import load_project

        proj_dir = tmp_path / "my-project"
        proj_dir.mkdir()
        data = _minimal_project_yaml("my-project")
        # no 'source' key
        p = proj_dir / "PROJECT.yaml"
        p.write_text(yaml.dump(data))

        result = load_project(p)
        assert result.source == {}

    def test_load_all_projects_discovers_idps_planner(self):
        """load_all_projects picks up the real idps-planner project from the repo."""
        from vcfops_packaging.project import load_all_projects

        repo_root = Path(__file__).parent.parent
        projects = load_all_projects(repo_root / "third_party")
        names = [p.name for p in projects]
        assert "idps-planner" in names, (
            f"Expected idps-planner in discovered projects, got: {names}"
        )

    def test_load_all_projects_skips_non_content_dirs(self, tmp_path):
        """Directories with no content-type subdirs and no PROJECT.yaml are skipped."""
        from vcfops_packaging.project import load_all_projects

        tp = tmp_path / "third_party"
        tp.mkdir()

        # A scratch dir with only a debug/ subdir — no content, no PROJECT.yaml
        scratch = tp / "scratch"
        scratch.mkdir()
        (scratch / "debug").mkdir()
        (scratch / "debug" / "some.json").write_text("{}")

        # This should NOT raise — scratch has no content subdirs
        projects = load_all_projects(tp)
        assert len(projects) == 0

    def test_load_all_projects_content_dir_without_project_yaml_is_error(self, tmp_path):
        """A third_party subdir with a dashboards/ subdir but no PROJECT.yaml is an error."""
        from vcfops_packaging.project import load_all_projects, ProjectValidationError

        tp = tmp_path / "third_party"
        (tp / "my-project" / "dashboards").mkdir(parents=True)
        (tp / "my-project" / "dashboards" / "foo.yaml").write_text("name: foo\n")

        with pytest.raises(ProjectValidationError, match="missing PROJECT.yaml"):
            load_all_projects(tp)

    def test_idps_planner_project_yaml_validates(self):
        """The real idps-planner/PROJECT.yaml validates against the schema."""
        from vcfops_packaging.project import load_project

        repo_root = Path(__file__).parent.parent
        p = repo_root / "third_party" / "idps-planner" / "PROJECT.yaml"
        assert p.exists(), f"idps-planner PROJECT.yaml not found: {p}"

        result = load_project(p)
        assert result.name == "idps-planner"
        assert result.factory_native is False
        assert result.license == "MIT"
        assert result.author  # non-empty
        assert result.description  # non-empty


# ---------------------------------------------------------------------------
# P2 — Slug uniqueness across both provenances
# ---------------------------------------------------------------------------

class TestSlugUniqueness:
    """P2: check_slug_uniqueness fires on cross-provenance filename collisions."""

    def test_clean_no_collision(self, tmp_path):
        """No collision when factory-native and third-party have distinct slugs."""
        from vcfops_packaging.project import check_slug_uniqueness

        content_sms = tmp_path / "content" / "supermetrics"
        content_sms.mkdir(parents=True)
        (content_sms / "factory_sm.yaml").write_text("name: factory\n")

        tp = tmp_path / "third_party"
        tp_sm = tp / "proj-a" / "supermetrics"
        tp_sm.mkdir(parents=True)
        (tp_sm / "third_party_sm.yaml").write_text("name: third\n")

        errors = check_slug_uniqueness(
            content_type="supermetrics",
            content_type_dir=content_sms,
            third_party_dir=tp,
        )
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_factory_vs_thirdparty_collision(self, tmp_path):
        """Same slug in content/ and third_party/*/ is an error."""
        from vcfops_packaging.project import check_slug_uniqueness

        content_sms = tmp_path / "content" / "supermetrics"
        content_sms.mkdir(parents=True)
        (content_sms / "duplicate_sm.yaml").write_text("name: dup\n")

        tp = tmp_path / "third_party"
        tp_sm = tp / "proj-a" / "supermetrics"
        tp_sm.mkdir(parents=True)
        (tp_sm / "duplicate_sm.yaml").write_text("name: dup\n")

        errors = check_slug_uniqueness(
            content_type="supermetrics",
            content_type_dir=content_sms,
            third_party_dir=tp,
        )
        assert len(errors) == 1, f"Expected 1 error, got: {errors}"
        assert "duplicate_sm" in errors[0]
        assert "duplicate" in errors[0].lower()

    def test_two_thirdparty_projects_collision(self, tmp_path):
        """Same slug in two different third-party projects is an error."""
        from vcfops_packaging.project import check_slug_uniqueness

        content_sms = tmp_path / "content" / "supermetrics"
        content_sms.mkdir(parents=True)  # empty factory-native dir

        tp = tmp_path / "third_party"
        for proj in ("proj-a", "proj-b"):
            tp_sm = tp / proj / "supermetrics"
            tp_sm.mkdir(parents=True)
            (tp_sm / "shared_slug.yaml").write_text(f"name: {proj}\n")

        errors = check_slug_uniqueness(
            content_type="supermetrics",
            content_type_dir=content_sms,
            third_party_dir=tp,
        )
        assert len(errors) == 1, f"Expected 1 error, got: {errors}"
        assert "shared_slug" in errors[0]
        assert "proj-a" in errors[0]
        assert "proj-b" in errors[0]

    def test_different_types_dont_collide(self, tmp_path):
        """Same stem in dashboards/ and views/ does NOT trigger a collision."""
        from vcfops_packaging.project import check_slug_uniqueness

        content_dash = tmp_path / "content" / "dashboards"
        content_dash.mkdir(parents=True)
        (content_dash / "foo.yaml").write_text("name: Foo Dashboard\n")

        tp = tmp_path / "third_party"
        tp_view = tp / "proj-a" / "views"
        tp_view.mkdir(parents=True)
        (tp_view / "foo.yaml").write_text("name: Foo View\n")

        # Checking only dashboards — views in third_party/ don't contribute to
        # the dashboard slug namespace.
        errors = check_slug_uniqueness(
            content_type="dashboards",
            content_type_dir=content_dash,
            third_party_dir=tp,
        )
        assert errors == [], f"Cross-type collision should not fire: {errors}"

    def test_no_third_party_dir(self, tmp_path):
        """When third_party/ doesn't exist, check runs cleanly on content/ only."""
        from vcfops_packaging.project import check_slug_uniqueness

        content_sms = tmp_path / "content" / "supermetrics"
        content_sms.mkdir(parents=True)
        (content_sms / "factory_sm.yaml").write_text("name: factory\n")

        # third_party/ absent — should not error
        errors = check_slug_uniqueness(
            content_type="supermetrics",
            content_type_dir=content_sms,
            third_party_dir=tmp_path / "nonexistent_third_party",
        )
        assert errors == [], f"Expected no errors with absent third_party: {errors}"

    def test_multiple_collisions_reported(self, tmp_path):
        """Multiple distinct collisions are all reported (not just first)."""
        from vcfops_packaging.project import check_slug_uniqueness

        content_sms = tmp_path / "content" / "supermetrics"
        content_sms.mkdir(parents=True)
        (content_sms / "alpha.yaml").write_text("name: alpha\n")
        (content_sms / "beta.yaml").write_text("name: beta\n")

        tp = tmp_path / "third_party"
        tp_sm = tp / "proj-a" / "supermetrics"
        tp_sm.mkdir(parents=True)
        (tp_sm / "alpha.yaml").write_text("name: alpha-tp\n")
        (tp_sm / "beta.yaml").write_text("name: beta-tp\n")

        errors = check_slug_uniqueness(
            content_type="supermetrics",
            content_type_dir=content_sms,
            third_party_dir=tp,
        )
        assert len(errors) == 2, f"Expected 2 errors, got: {errors}"

    def test_real_repo_has_no_slug_collisions_supermetrics(self):
        """Real repo: no slug collision in supermetrics across both provenances."""
        from vcfops_packaging.project import check_slug_uniqueness

        repo_root = Path(__file__).parent.parent
        errors = check_slug_uniqueness(
            content_type="supermetrics",
            content_type_dir=repo_root / "content" / "supermetrics",
            third_party_dir=repo_root / "third_party",
        )
        assert errors == [], f"Real repo has supermetric slug collisions: {errors}"

    def test_real_repo_has_no_slug_collisions_dashboards(self):
        """Real repo: no slug collision in dashboards across both provenances."""
        from vcfops_packaging.project import check_slug_uniqueness

        repo_root = Path(__file__).parent.parent
        errors = check_slug_uniqueness(
            content_type="dashboards",
            content_type_dir=repo_root / "content" / "dashboards",
            third_party_dir=repo_root / "third_party",
        )
        assert errors == [], f"Real repo has dashboard slug collisions: {errors}"

    def test_real_repo_has_no_slug_collisions_views(self):
        """Real repo: no slug collision in views across both provenances."""
        from vcfops_packaging.project import check_slug_uniqueness

        repo_root = Path(__file__).parent.parent
        errors = check_slug_uniqueness(
            content_type="views",
            content_type_dir=repo_root / "content" / "views",
            third_party_dir=repo_root / "third_party",
        )
        assert errors == [], f"Real repo has view slug collisions: {errors}"


# ---------------------------------------------------------------------------
# P3 — Project-membership boundary check
# ---------------------------------------------------------------------------

class TestProjectMembership:
    """P3: check_project_membership fires on cross-project deps."""

    def _make_minimal_sm(self, sm_dir: Path, stem: str, name: str):
        """Write a minimal SM YAML file and return a loaded SuperMetricDef."""
        sm_dir.mkdir(parents=True, exist_ok=True)
        p = sm_dir / f"{stem}.yaml"
        p.write_text(yaml.dump({
            "name": name,
            "formula": "${this, metric=cpu|usage_average}",
            "resource_kinds": [
                {"resource_kind_key": "VirtualMachine", "adapter_kind_key": "VMWARE"}
            ],
        }, default_flow_style=False))
        # Load it via the real loader so source_path is populated.
        from vcfops_supermetrics.loader import load_file
        return load_file(p, enforce_framework_prefix=False)

    def _make_minimal_view(self, views_dir: Path, stem: str, sm_uuid: str, sm_name: str):
        """Write a minimal view YAML that references one SM, return loaded ViewDef."""
        views_dir.mkdir(parents=True, exist_ok=True)
        p = views_dir / f"{stem}.yaml"
        # adapter_kind/resource_kind live under 'subject:' in view YAML
        p.write_text(yaml.dump({
            "name": f"View {stem}",
            "subject": {
                "adapter_kind": "VMWARE",
                "resource_kind": "VirtualMachine",
            },
            "columns": [
                {
                    "attribute": f"Super Metric|sm_{sm_uuid}",
                    "display_name": "My SM",
                }
            ],
        }, default_flow_style=False))
        from vcfops_dashboards.loader import load_view
        return load_view(p, enforce_framework_prefix=False)

    def _make_minimal_dashboard(self, dash_dir: Path, stem: str, view_name: str):
        """Write a minimal dashboard YAML referencing a view, return loaded Dashboard."""
        import uuid as _uuid
        dash_dir.mkdir(parents=True, exist_ok=True)
        p = dash_dir / f"{stem}.yaml"
        p.write_text(yaml.dump({
            "name": f"Dashboard {stem}",
            "widgets": [
                {
                    "id": str(_uuid.uuid4()),
                    "type": "View",
                    "title": f"Widget for {view_name}",
                    "coords": {"x": 1, "y": 1, "w": 6, "h": 6},
                    "view": view_name,
                }
            ],
        }, default_flow_style=False))
        from vcfops_dashboards.loader import load_dashboard
        return load_dashboard(p, enforce_framework_prefix=False, default_name_path="")

    def test_factory_native_dashboard_unconstrained(self, tmp_path):
        """Factory-native dashboards are not subject to the boundary check."""
        from vcfops_packaging.project import check_project_membership
        from vcfops_supermetrics.loader import load_file as load_sm
        from vcfops_dashboards.loader import load_view, load_dashboard

        tp = tmp_path / "third_party"

        sm = self._make_minimal_sm(tmp_path / "content" / "supermetrics", "factory_sm",
                                   "[VCF Content Factory] Factory SM")
        view = self._make_minimal_view(
            tmp_path / "content" / "views", "factory_view", sm.id, sm.name
        )
        dash_dir = tmp_path / "content" / "dashboards"
        dash = self._make_minimal_dashboard(dash_dir, "factory_dash", view.name)

        errors = check_project_membership(
            dashboards=[dash],
            all_views=[view],
            all_supermetrics=[sm],
            all_customgroups=[],
            third_party_dir=tp,
        )
        assert errors == [], (
            f"Factory-native dashboard should be unconstrained, got: {errors}"
        )

    def test_thirdparty_dashboard_within_project_ok(self, tmp_path):
        """Third-party dashboard referencing only its own project's deps passes."""
        from vcfops_packaging.project import check_project_membership

        tp = tmp_path / "third_party"
        proj_a = tp / "proj-a"

        sm = self._make_minimal_sm(proj_a / "supermetrics", "proj_a_sm", "Proj A SM")
        view = self._make_minimal_view(
            proj_a / "views", "proj_a_view", sm.id, sm.name
        )
        dash = self._make_minimal_dashboard(
            proj_a / "dashboards", "proj_a_dash", view.name
        )

        errors = check_project_membership(
            dashboards=[dash],
            all_views=[view],
            all_supermetrics=[sm],
            all_customgroups=[],
            third_party_dir=tp,
        )
        assert errors == [], (
            f"Self-contained third-party dashboard should pass, got: {errors}"
        )

    def test_thirdparty_dashboard_pulls_factory_view_is_error(self, tmp_path):
        """Third-party dashboard referencing a factory-native view is an error."""
        from vcfops_packaging.project import check_project_membership

        tp = tmp_path / "third_party"
        proj_a = tp / "proj-a"

        # SM and view live in factory-native content/
        sm = self._make_minimal_sm(
            tmp_path / "content" / "supermetrics", "factory_sm",
            "[VCF Content Factory] Factory SM"
        )
        # View references the factory SM but lives in factory content/
        view = self._make_minimal_view(
            tmp_path / "content" / "views", "factory_view", sm.id, sm.name
        )
        # Dashboard lives in third_party/proj-a/ but references the factory view
        dash = self._make_minimal_dashboard(
            proj_a / "dashboards", "proj_a_dash", view.name
        )

        errors = check_project_membership(
            dashboards=[dash],
            all_views=[view],
            all_supermetrics=[sm],
            all_customgroups=[],
            third_party_dir=tp,
        )
        assert len(errors) >= 1, (
            f"Expected at least 1 boundary error, got: {errors}"
        )
        assert "proj-a" in errors[0], f"Error should mention project name: {errors[0]}"
        assert "proj_a_dash" in errors[0], f"Error should mention dashboard: {errors[0]}"

    def test_thirdparty_dashboard_pulls_other_project_view_is_error(self, tmp_path):
        """Third-party dashboard referencing another third-party project's view is an error."""
        from vcfops_packaging.project import check_project_membership

        tp = tmp_path / "third_party"
        proj_a = tp / "proj-a"
        proj_b = tp / "proj-b"

        # View lives in proj-b
        sm_b = self._make_minimal_sm(proj_b / "supermetrics", "proj_b_sm", "Proj B SM")
        view_b = self._make_minimal_view(
            proj_b / "views", "proj_b_view", sm_b.id, sm_b.name
        )
        # Dashboard lives in proj-a but references proj-b's view
        dash_a = self._make_minimal_dashboard(
            proj_a / "dashboards", "proj_a_dash", view_b.name
        )

        errors = check_project_membership(
            dashboards=[dash_a],
            all_views=[view_b],
            all_supermetrics=[sm_b],
            all_customgroups=[],
            third_party_dir=tp,
        )
        assert len(errors) >= 1, (
            f"Expected at least 1 boundary error for cross-project view, got: {errors}"
        )
        assert "proj-a" in errors[0]

    def test_no_errors_when_third_party_absent(self, tmp_path):
        """Membership check is a no-op when third_party/ doesn't exist."""
        from vcfops_packaging.project import check_project_membership

        sm = self._make_minimal_sm(
            tmp_path / "content" / "supermetrics", "sm", "My SM"
        )
        view = self._make_minimal_view(
            tmp_path / "content" / "views", "view", sm.id, sm.name
        )
        dash = self._make_minimal_dashboard(
            tmp_path / "content" / "dashboards", "dash", view.name
        )

        errors = check_project_membership(
            dashboards=[dash],
            all_views=[view],
            all_supermetrics=[sm],
            all_customgroups=[],
            third_party_dir=tmp_path / "nonexistent",
        )
        assert errors == [], f"Expected no errors with absent third_party: {errors}"

    def test_real_repo_idps_planner_is_self_contained(self):
        """Real repo: idps-planner dashboards only reference their own project's deps."""
        from vcfops_packaging.project import check_project_membership
        from vcfops_dashboards.loader import load_view, load_dashboard
        from vcfops_supermetrics.loader import load_dir as load_sm_dir

        repo_root = Path(__file__).parent.parent
        tp = repo_root / "third_party"
        proj = tp / "idps-planner"

        # Load all idps-planner content
        views = []
        views_dir = proj / "views"
        if views_dir.exists():
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                for p in sorted(views_dir.rglob("*.y*ml")):
                    try:
                        views.append(load_view(p, enforce_framework_prefix=False))
                    except Exception:
                        pass

        dashboards = []
        dash_dir = proj / "dashboards"
        if dash_dir.exists():
            for p in sorted(dash_dir.rglob("*.y*ml")):
                try:
                    dashboards.append(
                        load_dashboard(p, enforce_framework_prefix=False, default_name_path="")
                    )
                except Exception:
                    pass

        sms = []
        sm_dir = proj / "supermetrics"
        if sm_dir.exists():
            try:
                sms = load_sm_dir(sm_dir, enforce_framework_prefix=False)
            except Exception:
                pass

        errors = check_project_membership(
            dashboards=dashboards,
            all_views=views,
            all_supermetrics=sms,
            all_customgroups=[],
            third_party_dir=tp,
        )
        assert errors == [], (
            f"idps-planner should be self-contained, but got boundary errors:\n"
            + "\n".join(errors)
        )


# ---------------------------------------------------------------------------
# Integration: packaging validate includes PROJECT.yaml check
# ---------------------------------------------------------------------------

class TestPackagingValidateIntegration:
    """Smoke tests for the PROJECT.yaml check in 'python3 -m vcfops_packaging validate'."""

    def test_packaging_validate_command_passes_on_real_repo(self):
        """packaging validate exits 0 on the real repo (all PROJECT.yaml files valid)."""
        import subprocess
        import sys

        repo_root = Path(__file__).parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "vcfops_packaging", "validate"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"packaging validate failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        assert "Third-party PROJECT.yaml" in result.stdout, (
            "Expected PROJECT.yaml section in output"
        )
        assert "idps-planner/PROJECT.yaml" in result.stdout, (
            "Expected idps-planner to appear in output"
        )

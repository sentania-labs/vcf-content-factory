"""buildkit.py — Assemble a portable sdk-buildkit tarball.

The kit is a self-contained Python package (sdk_buildkit) that can build
Tier 2 SDK adapter .pak files without a factory checkout and without any
LLM / agent involvement.  CI runners pull the tarball, extract it, and run:

    python3 -m sdk_buildkit build-sdk <adapter_dir>

Kit contents (assembled under a temp dir, then tarballed):
  sdk_buildkit/
    __init__.py
    __main__.py                 — exposes build-sdk / validate-sdk / pak-compare
    sdk_builder.py              — copy of vcfops_managementpacks/sdk_builder.py (paths relocated)
    sdk_project.py              — copy (no path changes needed)
    pak_compare.py              — copy (no path changes needed)
    provenance.py               — copy of vcfops_common/provenance.py (pure stdlib)
    dashboard_loader.py         — copy of vcfops_dashboards/loader.py (imports patched)
    dashboard_render.py         — copy of vcfops_dashboards/render.py (imports patched)
    dashboard_yaml_utils.py     — copy of vcfops_dashboards/yaml_utils.py
    sm_loader.py                — copy of vcfops_supermetrics/loader.py
    symptoms_loader.py          — copy of vcfops_symptoms/loader.py
    alerts_loader.py            — copy of vcfops_alerts/loader.py
    alerts_render.py            — copy of vcfops_alerts/render.py (imports patched)
    reports_loader.py           — copy of vcfops_reports/loader.py
    reports_render.py           — copy of vcfops_reports/render.py (imports patched)
    adapter_framework/src/       — framework Java source (compiled at build-sdk time)
    adapter_runtime/             — empty directory (jar compiled into here on first use)
    templates/icons/             — SVG icon assets
    reference_paks/             — one reference .pak for pak-compare
    LICENSE
    VERSION

Path relocation in the kit's sdk_builder.py:
  _HERE                    = Path(__file__).parent
  _ADAPTER_RUNTIME_DIR      = _HERE / "adapter_runtime"
  _ADAPTER_FRAMEWORK_SRC_DIR = _HERE / "adapter_framework" / "src"
  _LICENSE_PATH             = _HERE / "LICENSE"
  _REFERENCES_DIR           = _HERE / "reference_paks"
  templates/icons           = _HERE / "templates" / "icons"

Import rewrites also applied to:
  alerts_render.py  — vcfops_symptoms.loader / vcfops_alerts.loader → flat kit names
  reports_render.py — relative .loader → reports_loader (flat kit name)
  sdk_builder.py    — also rewrites the inline `from vcfops_dashboards.render
                       import render_view_def_fragments` used by the
                       co-bundled-reports path (report subdir embeds its
                       referenced views' <ViewDef> fragments)

repo_root handling:
  In the factory, _load_bundled_content resolves bundled_content paths against
  _REPO_ROOT (_HERE.parent.parent since the src/ reorg — the factory root).
  In the kit, there is no factory root —
  adapters carry their own view/dashboard YAML.  The kit's build-sdk passes
  project_dir as repo_root so that bundled_content: paths are relative to the
  adapter's own directory.

Bundled-content closure:
  vcfops_dashboards.loader imports vcfops_common.provenance.  vcfops_common's
  __init__.py imports requests (network client), which is NOT available in CI.
  The kit ships provenance.py directly (pure stdlib) and patches the loader
  import accordingly.  See provenance.py docstring for details.
"""
from __future__ import annotations

import re
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Version constant — bump when kit contents change in a meaningful way
# ---------------------------------------------------------------------------

BUILDKIT_VERSION = "1.0.9"

# ---------------------------------------------------------------------------
# Source paths (relative to this file's parent = vcfops_managementpacks/)
# ---------------------------------------------------------------------------

_HERE = Path(__file__).parent
# _SRC_ROOT: parent of all sibling vcfops_* packages (src/ after the reorg).
_SRC_ROOT = _HERE.parent
# _REPO_ROOT: the actual factory repo root (one level above src/), used for
# repo-level assets like dist/ and LICENSE that never moved under src/.
_REPO_ROOT = _SRC_ROOT.parent

# Source files to copy into sdk_buildkit/
_FACTORY_SOURCES = {
    # dest name inside sdk_buildkit → source path
    "sdk_builder.py": _HERE / "sdk_builder.py",
    "sdk_project.py": _HERE / "sdk_project.py",
    "pak_compare.py": _HERE / "pak_compare.py",
    "provenance.py": _SRC_ROOT / "vcfops_common" / "provenance.py",
    "dashboard_loader.py": _SRC_ROOT / "vcfops_dashboards" / "loader.py",
    "dashboard_render.py": _SRC_ROOT / "vcfops_dashboards" / "render.py",
    "dashboard_yaml_utils.py": _SRC_ROOT / "vcfops_dashboards" / "yaml_utils.py",
    "sm_loader.py": _SRC_ROOT / "vcfops_supermetrics" / "loader.py",
    "symptoms_loader.py": _SRC_ROOT / "vcfops_symptoms" / "loader.py",
    "alerts_loader.py": _SRC_ROOT / "vcfops_alerts" / "loader.py",
    "alerts_render.py": _SRC_ROOT / "vcfops_alerts" / "render.py",
    "reports_loader.py": _SRC_ROOT / "vcfops_reports" / "loader.py",
    "reports_render.py": _SRC_ROOT / "vcfops_reports" / "render.py",
    "docs_gen.py": _HERE / "docs_gen.py",
}

# ---------------------------------------------------------------------------
# Import-rewrite rules
# ---------------------------------------------------------------------------

# Each entry is a list of (pattern, replacement) applied in order to the
# Python source text of a specific file.  Replacements make every cross-file
# import self-contained within the sdk_buildkit package.

_IMPORT_REWRITES: dict[str, list[tuple[str, str]]] = {
    # sdk_builder.py: rewrite intra-package imports and vcfops_* refs
    "sdk_builder.py": [
        # from .sdk_project import ... → from .sdk_project import ...
        # (already relative; keep as-is — no change needed)
        # from .pak_compare import ... → from .pak_compare import ...
        # (already relative; keep as-is — no change needed)
        # from vcfops_dashboards.loader import load_view, load_dashboard
        (
            r"from vcfops_dashboards\.loader import load_view, load_dashboard",
            "from .dashboard_loader import load_view, load_dashboard",
        ),
        # from vcfops_dashboards.render import render_views_xml
        (
            r"from vcfops_dashboards\.render import render_views_xml",
            "from .dashboard_render import render_views_xml",
        ),
        # from vcfops_dashboards.render import render_dashboards_bundle_json
        (
            r"from vcfops_dashboards\.render import render_dashboards_bundle_json",
            "from .dashboard_render import render_dashboards_bundle_json",
        ),
        # from vcfops_dashboards.render import render_view_def_fragments
        # (inline import in the co-bundled-reports path; embeds a bundled
        # view's <ViewDef> fragment inside a report's content/reports/<slug>/
        # subdirectory — see sdk_builder.py's _build_sdk_pak_inner reports
        # loop). Introduced by PR #49; missed by the buildkit's rewrite
        # sweep until DEF-caught in a from-tarball build of
        # vcfcf_sdk_vcommunity_vsphere (report + embedded view shape).
        (
            r"from vcfops_dashboards\.render import render_view_def_fragments",
            "from .dashboard_render import render_view_def_fragments",
        ),
        # from vcfops_supermetrics.loader import load_file as _load_sm  (inline in _load_bundled_content)
        (
            r"from vcfops_supermetrics\.loader import load_file as _load_sm",
            "from .sm_loader import load_file as _load_sm",
        ),
        # from vcfops_symptoms.loader import load_file as _load_sym
        (
            r"from vcfops_symptoms\.loader import load_file as _load_sym",
            "from .symptoms_loader import load_file as _load_sym",
        ),
        # from vcfops_alerts.loader import load_file as _load_alert
        (
            r"from vcfops_alerts\.loader import load_file as _load_alert",
            "from .alerts_loader import load_file as _load_alert",
        ),
        # from vcfops_alerts.loader import load_recommendation_file as _load_rec
        (
            r"from vcfops_alerts\.loader import load_recommendation_file as _load_rec",
            "from .alerts_loader import load_recommendation_file as _load_rec",
        ),
        # from vcfops_alerts.render import _symptom_id as _compute_symptom_id
        (
            r"from vcfops_alerts\.render import _symptom_id as _compute_symptom_id",
            "from .alerts_render import _symptom_id as _compute_symptom_id",
        ),
        # from vcfops_alerts.render import render_alert_content_xml
        (
            r"from vcfops_alerts\.render import render_alert_content_xml",
            "from .alerts_render import render_alert_content_xml",
        ),
        # from vcfops_reports.loader import load_file as _load_report
        (
            r"from vcfops_reports\.loader import load_file as _load_report",
            "from .reports_loader import load_file as _load_report",
        ),
        # from vcfops_reports.render import render_report_xml
        (
            r"from vcfops_reports\.render import render_report_xml",
            "from .reports_render import render_report_xml",
        ),
        # Relocate path constants:
        #   _ADAPTER_RUNTIME_DIR = _HERE / "adapter_runtime"  (no change; _HERE is already right)
        #   _LICENSE_PATH = _REPO_ROOT / "LICENSE"  → _HERE / "LICENSE"
        # (source uses _REPO_ROOT = _HERE.parent.parent since the src/ reorg —
        # two levels up from src/vcfops_managementpacks/sdk_builder.py to the
        # factory repo root; the flat kit has no repo root, so this collapses
        # to _HERE.)
        (
            r'_LICENSE_PATH = _REPO_ROOT / "LICENSE"',
            '_LICENSE_PATH = _HERE / "LICENSE"',
        ),
        #   _REFERENCES_DIR = _REPO_ROOT / "tmp" / "reference_paks"  → _HERE / "reference_paks"
        (
            r'_REFERENCES_DIR = _REPO_ROOT / "tmp" / "reference_paks"',
            '_REFERENCES_DIR = _HERE / "reference_paks"',
        ),
        # icons path: _HERE / "templates" / "icons" — same structure; no change needed
        # but sdk_builder also does _REPO_ROOT / "dist" for default output_dir:
        (
            r'output_dir = _REPO_ROOT / "dist"',
            'output_dir = Path.cwd() / "dist"',
        ),
        # NOTE: Two rewrite rules that patched `_repo_root = _HERE.parent` were
        # removed here.  That variable was eliminated from sdk_builder.py before
        # the 5-tuple _load_bundled_content() refactor; both call sites now pass
        # project_dir directly.  Dead rewrites are removed rather than kept as
        # silent no-ops (see assertion in _apply_rewrites below).
    ],
    # sm_loader.py: rewrite vcfops_common.provenance (inline import at load_file time).
    # vcfops_common is flattened to provenance.py in the kit; sm_loader.py line ~211
    # executes `from vcfops_common.provenance import provenance_from_path` at runtime
    # (inside load_file, not at module import time), so the try/except in alerts_render
    # does NOT guard it.  Without this rule any adapter bundling supermetrics raises
    # ModuleNotFoundError on a clean CI runner where vcfops_common is not on sys.path.
    "sm_loader.py": [
        # from vcfops_common.provenance import provenance_from_path
        (
            r"from vcfops_common\.provenance import provenance_from_path",
            "from .provenance import provenance_from_path",
        ),
    ],
    # dashboard_loader.py: rewrite vcfops_dashboards.yaml_utils and vcfops_common.provenance
    "dashboard_loader.py": [
        # from vcfops_dashboards.yaml_utils import strict_load as _strict_load
        (
            r"from vcfops_dashboards\.yaml_utils import strict_load as _strict_load",
            "from .dashboard_yaml_utils import strict_load as _strict_load",
        ),
        # from vcfops_common.provenance import provenance_from_path
        (
            r"from vcfops_common\.provenance import provenance_from_path",
            "from .provenance import provenance_from_path",
        ),
    ],
    # dashboard_render.py: rewrite .loader import (it's a relative import within
    # vcfops_dashboards, which becomes .dashboard_loader in the kit)
    "dashboard_render.py": [
        # from .loader import (...)  →  from .dashboard_loader import (...)
        (
            r"from \.loader import \(",
            "from .dashboard_loader import (",
        ),
        # from .loader import BucketsConfig  (inline import in function body)
        (
            r"from \.loader import BucketsConfig",
            "from .dashboard_loader import BucketsConfig",
        ),
        # from vcfops_supermetrics.loader import load_file as _sm_load_file
        (
            r"from vcfops_supermetrics\.loader import load_file as _sm_load_file",
            "from .sm_loader import load_file as _sm_load_file",
        ),
        # from vcfops_supermetrics.loader import load_dir as _sm_load_dir
        (
            r"from vcfops_supermetrics\.loader import load_dir as _sm_load_dir",
            "from .sm_loader import load_dir as _sm_load_dir",
        ),
    ],
    # alerts_render.py: rewrite vcfops_symptoms.loader and vcfops_alerts.loader
    # imports to the flat kit module names.  These are guarded by try/except in
    # the source so they do not raise at import time, but the kit must still
    # provide the modules so that runtime calls work correctly.
    "alerts_render.py": [
        # from vcfops_symptoms.loader import SymptomDef
        (
            r"from vcfops_symptoms\.loader import SymptomDef",
            "from .symptoms_loader import SymptomDef",
        ),
        # from vcfops_alerts.loader import AlertDef, Recommendation
        (
            r"from vcfops_alerts\.loader import AlertDef, Recommendation",
            "from .alerts_loader import AlertDef, Recommendation",
        ),
    ],
    # reports_render.py: rewrite relative .loader import (vcfops_reports package
    # relative import → flat kit module name).
    "reports_render.py": [
        # from .loader import ReportDef, Section, _STATIC_CONTENT_KEYS
        (
            r"from \.loader import ReportDef, Section, _STATIC_CONTENT_KEYS",
            "from .reports_loader import ReportDef, Section, _STATIC_CONTENT_KEYS",
        ),
    ],
}

# ---------------------------------------------------------------------------
# __init__.py content
# ---------------------------------------------------------------------------

_KIT_INIT = '''\
"""sdk_buildkit — Portable Tier 2 SDK adapter build toolchain.

Run as:
    python3 -m sdk_buildkit build-sdk <adapter_dir>
    python3 -m sdk_buildkit validate-sdk <adapter_dir>
    python3 -m sdk_buildkit pak-compare <factory.pak> <reference.pak>

## Consumer contract

This kit is fully JAR-FREE.  No pre-built jars ship at all — not even
vcfcf-adapter-base.jar.  Instead the VCF Content Factory framework source
is bundled in adapter_framework/src/ and compiled automatically on first
use (during build-sdk or validate-sdk) against the consumer-supplied
vrops-adapters-sdk-2.2.jar.  This means the framework jar is always fresh
and in sync with the source — there is no stale-binary failure class.

Adapters are compiled against vrops-adapters-sdk-2.2.jar which YOU must
supply — it is a Broadcom internal build artifact with no public
redistribution channel and cannot ship in a public toolchain tarball.

### How to obtain vrops-adapters-sdk-2.2.jar

Option 1 — copy from your VCF Ops appliance (any 9.x instance):
    scp root@<appliance>:/usr/lib/vmware-vcops/common-lib/vrops-adapters-sdk-2.2.jar .
    # also available at:
    # /usr/lib/vmware-vcops/suite-api/WEB-INF/lib/vrops-adapters-sdk.jar

Option 2 — Broadcom TAP / partner SDK portal (if enrolled).

### Providing the JAR to the build

Set the VCFCF_SDK_JAR environment variable:
    export VCFCF_SDK_JAR=/path/to/vrops-adapters-sdk-2.2.jar
    python3 -m sdk_buildkit build-sdk <adapter_dir>

Or use the --sdk-jar flag:
    python3 -m sdk_buildkit build-sdk <adapter_dir> --sdk-jar /path/to/vrops-adapters-sdk-2.2.jar

In CI, store the JAR as a secret-gated artifact and expose its path via
VCFCF_SDK_JAR.  The build fails with a clear actionable message when the
JAR is absent from both adapter_runtime/ and the env var.

## Other requirements

- Python 3.9+ with PyYAML
- JDK 11+ on PATH (javac, jar) — used both to compile the framework and the adapter
- No factory checkout, no LLM, no other network access required.
"""
'''

# ---------------------------------------------------------------------------
# __main__.py content
# ---------------------------------------------------------------------------

_KIT_MAIN = '''\
"""Entry point: python3 -m sdk_buildkit <subcommand> [args ...]"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


_SDK_JAR_HELP = (
    "Path to vrops-adapters-sdk-2.2.jar (Broadcom; not shipped in this kit — "
    "see the consumer contract in __init__.py). "
    "Alternatively set the VCFCF_SDK_JAR environment variable. "
    "Required when running outside the VCF Content Factory repo."
)


def _apply_sdk_jar(args) -> None:
    """Set VCFCF_SDK_JAR env var from --sdk-jar flag if supplied."""
    sdk_jar = getattr(args, "sdk_jar", None)
    if sdk_jar:
        os.environ["VCFCF_SDK_JAR"] = str(sdk_jar)


def _apply_release_flag(args) -> None:
    """If --release was supplied, set VCFCF_RELEASE_BUILD in the environment.

    Mirrors vcfops_managementpacks/cli.py's _apply_release_flag exactly
    (inlined here rather than imported: cli.py is not bundled into the
    sdk_buildkit tarball — see buildkit.py's _FACTORY_SOURCES — so the kit's
    __main__.py must carry its own copy of this env-var injection). Explicit
    opt-in only — the flag is never set implicitly.
    """
    if getattr(args, "release", False):
        os.environ["VCFCF_RELEASE_BUILD"] = "1"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sdk_buildkit",
        description="Portable Tier 2 SDK adapter build toolchain.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    # ----- build-sdk -----
    pbsdk = sub.add_parser(
        "build-sdk",
        help="compile and package a Tier 2 SDK adapter project into a .pak",
    )
    pbsdk.add_argument(
        "project_dir",
        metavar="PROJECT_DIR",
        help="path to the Tier 2 adapter project directory (contains adapter.yaml)",
    )
    pbsdk.add_argument(
        "--output", "-o",
        default="dist",
        help="output directory for the .pak file (default: dist/)",
    )
    pbsdk.add_argument(
        "--sdk-jar",
        dest="sdk_jar",
        default=None,
        metavar="JAR_PATH",
        help=_SDK_JAR_HELP,
    )
    pbsdk.add_argument(
        "--release",
        action="store_true",
        default=False,
        help=(
            "explicit opt-in for the 1.x release version line; CI-only, "
            "never pass by hand. Equivalent to setting VCFCF_RELEASE_BUILD=1. "
            "Reserved for the tag-triggered CI release path — never pass "
            "this for a hand-built / local dev build."
        ),
    )

    # ----- validate-sdk -----
    pvsdk = sub.add_parser(
        "validate-sdk",
        help="validate adapter.yaml schema and compile-check a Tier 2 SDK adapter",
    )
    pvsdk.add_argument(
        "project_dir",
        metavar="PROJECT_DIR",
        help="path to the Tier 2 adapter project directory",
    )
    pvsdk.add_argument(
        "--sdk-jar",
        dest="sdk_jar",
        default=None,
        metavar="JAR_PATH",
        help=_SDK_JAR_HELP,
    )

    # ----- pak-compare -----
    ppc = sub.add_parser(
        "pak-compare",
        help="structurally compare a factory-built .pak against a reference .pak",
    )
    ppc.add_argument(
        "factory_pak",
        metavar="FACTORY_PAK",
        help="path to the factory-built .pak file",
    )
    ref_group = ppc.add_mutually_exclusive_group(required=True)
    ref_group.add_argument(
        "reference_pak",
        metavar="REFERENCE_PAK",
        nargs="?",
        default=None,
        help="path to the reference .pak file",
    )
    ref_group.add_argument(
        "--reference-dir",
        dest="reference_dir",
        default=None,
        metavar="DIR",
        help="compare against all .pak files in DIR",
    )
    ppc.add_argument(
        "--output", "-o",
        default=None,
        metavar="FILE",
        help="write the full report to FILE in addition to stdout",
    )

    return p


def main() -> int:
    args = _build_parser().parse_args()

    if args.cmd == "build-sdk":
        _apply_sdk_jar(args)
        _apply_release_flag(args)
        from .sdk_builder import build_sdk_pak, SdkBuildError
        from .sdk_project import SdkProjectError
        project_dir = Path(args.project_dir)
        output_dir = Path(args.output)
        try:
            pak_path = build_sdk_pak(project_dir, output_dir)
            print(f"Built: {pak_path}")
            return 0
        except (SdkBuildError, SdkProjectError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        except Exception as exc:
            print(f"ERROR building SDK pak: {exc}", file=sys.stderr)
            return 1

    elif args.cmd == "validate-sdk":
        _apply_sdk_jar(args)
        from .sdk_builder import validate_sdk_project
        project_dir = Path(args.project_dir)
        try:
            errors = validate_sdk_project(project_dir)
        except Exception as exc:
            print(f"ERROR during validate-sdk: {exc}", file=sys.stderr)
            return 1
        if errors:
            print(f"INVALID: {len(errors)} error(s) in {project_dir}:", file=sys.stderr)
            for err in errors:
                print(f"  {err}", file=sys.stderr)
            return 1
        print(f"OK: {project_dir} is a valid Tier 2 SDK adapter project")
        return 0

    elif args.cmd == "pak-compare":
        from .pak_compare import compare_paks, compare_pak_directory, format_report
        factory = Path(args.factory_pak)
        if not factory.exists():
            print(f"ERROR: factory pak not found: {factory}", file=sys.stderr)
            return 1

        output_file = getattr(args, "output", None)
        out_lines: list = []

        def _emit(text: str) -> None:
            print(text, end="")
            if output_file:
                out_lines.append(text)

        if args.reference_dir:
            ref_dir = Path(args.reference_dir)
            if not ref_dir.is_dir():
                print(f"ERROR: --reference-dir not a directory: {ref_dir}", file=sys.stderr)
                return 1
            results = compare_pak_directory(factory, ref_dir)
            if not results:
                print(f"No .pak files found in {ref_dir}", file=sys.stderr)
                return 1
            _emit(f"\\n=== PAK COMPARE: {factory.name} vs {ref_dir} ===\\n")
            for ref_path, result in results:
                _emit(format_report(result))
        else:
            ref = Path(args.reference_pak)
            if not ref.exists():
                print(f"ERROR: reference pak not found: {ref}", file=sys.stderr)
                return 1
            result = compare_paks(factory, ref)
            _emit(format_report(result))

        if output_file:
            Path(output_file).write_text("".join(out_lines))
            print(f"Report written to: {output_file}", file=sys.stderr)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

# ---------------------------------------------------------------------------
# Reference pak selection
# ---------------------------------------------------------------------------

def _pick_reference_pak() -> Optional[Path]:
    """Return the best available reference pak from dist/.

    Preference order:
    1. The compliance sdk pak (highest value, exercises bundled content).
    2. Any other sdk pak in dist/.
    3. Any pak in dist/.

    Returns None if no suitable pak is found.
    """
    dist = _REPO_ROOT / "dist"
    if not dist.is_dir():
        return None

    # Prefer the latest compliance pak (highest build number)
    compliance_paks = sorted(
        dist.glob("vcfcf_sdk_compliance.*.pak"),
        key=lambda p: [int(x) if x.isdigit() else 0 for x in p.stem.split(".")],
        reverse=True,
    )
    if compliance_paks:
        return compliance_paks[0]

    # Any SDK pak
    sdk_paks = sorted(dist.glob("vcfcf_sdk_*.pak"), reverse=True)
    if sdk_paks:
        return sdk_paks[0]

    # Any pak at all
    any_paks = sorted(dist.glob("*.pak"), reverse=True)
    if any_paks:
        return any_paks[0]

    return None


# ---------------------------------------------------------------------------
# Text-rewrite helper
# ---------------------------------------------------------------------------

def _apply_rewrites(text: str, rules: list[tuple[str, str]]) -> str:
    """Apply a list of (regex_pattern, replacement) substitutions to text.

    Raises AssertionError if any rule matches zero times — a silent no-op
    rewrite indicates the source file has drifted away from the rule's target
    and the rule must be updated or deleted.
    """
    for pattern, replacement in rules:
        new_text, n = re.subn(pattern, replacement, text)
        if n == 0:
            raise AssertionError(
                f"buildkit rewrite rule matched zero times — rule is stale or dead.\n"
                f"  pattern:     {pattern!r}\n"
                f"  replacement: {replacement!r}\n"
                "Update or remove this rule in vcfops_managementpacks/buildkit.py "
                "_IMPORT_REWRITES."
            )
        text = new_text
    return text


# ---------------------------------------------------------------------------
# Main assembly function
# ---------------------------------------------------------------------------

def assemble_buildkit(
    output_dir: Path,
    version: str = BUILDKIT_VERSION,
    reference_pak: Optional[Path] = None,
    verbose: bool = True,
) -> Path:
    """Assemble the sdk-buildkit tarball.

    Args:
        output_dir:    Directory where the tarball will be written.
        version:       Version string to stamp into the kit (default: BUILDKIT_VERSION).
        reference_pak: Explicit path to a .pak to bundle as the comparison reference.
                       When None, auto-selected from dist/ by _pick_reference_pak().
        verbose:       Print progress messages to stdout.

    Returns:
        Path to the produced .tgz file.

    Raises:
        FileNotFoundError: if a required source file is missing.
        ValueError: if no reference pak can be found.
    """
    import sys

    def _log(msg: str) -> None:
        if verbose:
            print(msg, file=sys.stderr)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Validate source files exist
    for dest_name, src_path in _FACTORY_SOURCES.items():
        if not src_path.is_file():
            raise FileNotFoundError(
                f"buildkit source file not found: {src_path} (for {dest_name})"
            )

    # Select reference pak
    if reference_pak is None:
        reference_pak = _pick_reference_pak()
    if reference_pak is None:
        raise ValueError(
            "No reference .pak found. Build at least one adapter pak first "
            "(python3 -m vcfops_managementpacks build-sdk content/sdk-adapters/compliance) "
            "or pass --reference-pak explicitly."
        )
    if not reference_pak.is_file():
        raise FileNotFoundError(f"Reference pak not found: {reference_pak}")

    _log(f"Assembling sdk-buildkit v{version} ...")
    _log(f"  reference pak: {reference_pak.name}")

    tarball_name = f"sdk-buildkit-{version}.tgz"
    tarball_path = output_dir / tarball_name

    with tempfile.TemporaryDirectory(prefix="sdk-buildkit-") as tmpdir:
        kit_dir = Path(tmpdir) / "sdk_buildkit"
        kit_dir.mkdir()

        # -----------------------------------------------------------------
        # 1. __init__.py and __main__.py
        # -----------------------------------------------------------------
        (kit_dir / "__init__.py").write_text(_KIT_INIT, encoding="utf-8")
        _log("  wrote __init__.py")
        (kit_dir / "__main__.py").write_text(_KIT_MAIN, encoding="utf-8")
        _log("  wrote __main__.py")

        # -----------------------------------------------------------------
        # 2. Python source files (with import rewrites)
        # -----------------------------------------------------------------
        for dest_name, src_path in _FACTORY_SOURCES.items():
            source_text = src_path.read_text(encoding="utf-8")
            rules = _IMPORT_REWRITES.get(dest_name, [])
            if rules:
                patched_text = _apply_rewrites(source_text, rules)
                (kit_dir / dest_name).write_text(patched_text, encoding="utf-8")
                _log(f"  wrote {dest_name} (patched {len(rules)} import rule(s))")
            else:
                (kit_dir / dest_name).write_bytes(src_path.read_bytes())
                _log(f"  wrote {dest_name}")

        # -----------------------------------------------------------------
        # 3a. adapter_runtime/ — empty stub; NO jars of any kind.
        #
        # The buildkit tarball is a public artifact.  Broadcom platform JARs
        # (vrops-adapters-sdk, alive_*, aria-ops-core, mpb_adapter*,
        # vmware-ops-api-stubs) cannot ship — they are internal build artifacts
        # with no public redistribution channel.
        #
        # vcfcf-adapter-base.jar is NOT shipped either.  Instead the framework
        # source tree (adapter_framework/src/) is bundled (step 3b below) and
        # compiled by the consumer's build-sdk / validate-sdk against the
        # consumer-supplied --sdk-jar.  This eliminates stale-binary drift
        # entirely: the jar is always built fresh from source.
        #
        # The no-Broadcom-jar guarantee is enforced by the CI workflow's
        # "Verify tarball contains no Broadcom JARs" step which scans the tarball
        # after assembly.
        # -----------------------------------------------------------------
        runtime_dst = kit_dir / "adapter_runtime"
        runtime_dst.mkdir()
        _log("  created adapter_runtime/ (empty — framework jar compiled from source at build time)")

        # -----------------------------------------------------------------
        # 3b. adapter_framework/src/ — framework Java source tree.
        #
        # The consumer's build-sdk / validate-sdk compiles this against the
        # consumer-supplied SDK jar and produces vcfcf-adapter-base.jar in
        # adapter_runtime/ on first use (_ensure_framework_jar() in sdk_builder.py).
        # -----------------------------------------------------------------
        fw_src = _HERE / "adapter_framework" / "src"
        if not fw_src.is_dir():
            raise FileNotFoundError(
                f"Framework source tree not found at {fw_src}.\n"
                "The adapter_framework/src/ directory is required to assemble the "
                "buildkit.  Ensure the factory repo is complete and "
                "adapter_framework/src/**/*.java files are present."
            )
        fw_java_files = list(fw_src.rglob("*.java"))
        if not fw_java_files:
            raise FileNotFoundError(
                f"Framework source tree at {fw_src} contains no .java files.\n"
                "Ensure adapter_framework/src/**/*.java files are present."
            )
        fw_dst = kit_dir / "adapter_framework" / "src"
        shutil.copytree(str(fw_src), str(fw_dst))
        _log(f"  copied adapter_framework/src/ ({len(fw_java_files)} .java file(s))")

        # -----------------------------------------------------------------
        # 4. templates/icons/ SVG assets
        # -----------------------------------------------------------------
        icons_src = _HERE / "templates" / "icons"
        icons_dst = kit_dir / "templates" / "icons"
        icons_dst.mkdir(parents=True)
        for svg in sorted(icons_src.glob("*.svg")):
            shutil.copy2(str(svg), str(icons_dst / svg.name))
        icon_count = sum(1 for _ in icons_dst.glob("*.svg"))
        _log(f"  copied templates/icons/ ({icon_count} SVG files)")

        # -----------------------------------------------------------------
        # 5. reference_paks/ — the bundled reference pak
        # -----------------------------------------------------------------
        ref_paks_dst = kit_dir / "reference_paks"
        ref_paks_dst.mkdir()
        shutil.copy2(str(reference_pak), str(ref_paks_dst / reference_pak.name))
        _log(f"  copied reference_paks/{reference_pak.name}")

        # -----------------------------------------------------------------
        # 6. LICENSE
        # -----------------------------------------------------------------
        license_src = _REPO_ROOT / "LICENSE"
        if license_src.is_file():
            shutil.copy2(str(license_src), str(kit_dir / "LICENSE"))
            _log("  copied LICENSE")
        else:
            # Write a placeholder so the builder's _read_license() doesn't warn
            (kit_dir / "LICENSE").write_text(
                "MIT License — see factory repo for full text.\n", encoding="utf-8"
            )
            _log("  wrote LICENSE placeholder (source not found)")

        # -----------------------------------------------------------------
        # 7. VERSION
        # -----------------------------------------------------------------
        (kit_dir / "VERSION").write_text(f"{version}\n", encoding="utf-8")
        _log(f"  wrote VERSION ({version})")

        # -----------------------------------------------------------------
        # 8. Pack into tarball
        # -----------------------------------------------------------------
        # The tarball contains sdk_buildkit/ at the top level so that
        # tar xzf sdk-buildkit-N.tgz && python3 -m sdk_buildkit works
        # from the extraction directory.
        with tarfile.open(str(tarball_path), "w:gz") as tf:
            tf.add(str(kit_dir), arcname="sdk_buildkit")

        _log(f"  packed tarball: {tarball_path}")

    size_kb = tarball_path.stat().st_size // 1024
    _log(f"Done: {tarball_path}  ({size_kb:,} KB)")
    return tarball_path

"""sdk_builder.py — Tier 2 SDK adapter build pipeline.

Implements steps 1-13 of the design plan (designs/tier2-mp-architecture-plan.md):
  1. Load adapter.yaml metadata
  2. Detect JDK on PATH
  3. Build classpath from adapter_runtime/ + project lib/*.jar
  4. Compile src/**/*.java into a temp build dir
  5. Generate adapter.properties (ENTRYCLASS + KINDKEY)
  6. Package adapter JAR via jar cf
  7. Copy describe.xml, resources, icons into adapter conf directory
  8. Collect runtime deps for lib/ (framework JAR only; SDK JARs stay off-pak)
  9. Assemble adapters.zip (SDK pak structure)
 10. Generate manifest.txt (SDK format; no adapters: field)
 11. Write outer .pak ZIP under dist/
 12. Run pak-compare against SDK reference paks (or log warning if none found)

Pak structure produced (SDK format — differs from MPB Tier 1):
  dist/vcfcf_<adapter_kind>.<version>.<build>.pak   [outer ZIP]
    manifest.txt                                      [JSON metadata]
    eula.txt                                          [MIT license text]
    adapters.zip                                      [inner ZIP]
      manifest.txt                                    [JSON — same format as outer]
      eula.txt
      resources/resources.properties
      <adapter_kind>.jar                              [entry JAR at root]
        adapter.properties                            [ENTRYCLASS + KINDKEY]
        com/vcfcf/adapters/<name>/...                 [compiled classes]
      <adapter_kind>/
        conf/
          describe.xml
          resources/resources.properties
        lib/
          vcfcf-adapter-base.jar                      [framework]
          aria-ops-core-<ver>.jar                     [v1 adapters only — see below]
          [project lib/*.jar if any]

Key design decisions:
  - vrops-adapters-sdk-*.jar resolves from the appliance classpath at runtime
    (proven by C2 install test, build 42, devel + prod, 2026-06-09 — see
    context/investigations/c2_no_sdk_jar_install_test.md).  It is kept on the
    javac compile classpath but is NEVER bundled in pak lib/.
  - aria-ops-core is NOT on the appliance shared classpath.  It must be bundled
    for any adapter whose compiled classes reference com.vmware.tvs.* (v1 adapters
    that have not yet been migrated to framework v2).  v2 adapters that extend
    VcfCfAdapter directly have no TVS dependency and do NOT bundle aria-ops-core.
    This is auto-detected by scanning the compiled class bytecode.  See
    _needs_aria_ops_core() for the detection logic.
  - vcfcf-adapter-base.jar ships in the pak's lib/ (our framework).
  - alive_common.jar / alive_platform.jar are on the shared classpath — NOT bundled.
  - No design.json, no template.json, no adapters: field in manifest (Tier 1 only).
  - Outer pak manifest uses adapter_kinds: [...] (no adapters: key).
"""
from __future__ import annotations

import glob
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

try:
    import yaml as _yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

from .sdk_project import SdkProjectDef, SdkProjectError, load_sdk_project

# ---------------------------------------------------------------------------
# Paths relative to this module
# ---------------------------------------------------------------------------

_HERE = Path(__file__).parent
_ADAPTER_RUNTIME_DIR = _HERE / "adapter_runtime"
_ADAPTER_FRAMEWORK_SRC_DIR = _HERE / "adapter_framework" / "src"
_LICENSE_PATH = _HERE.parent / "LICENSE"


def _find_stale_framework_sources(output_jar: Path, sources: List[Path]) -> List[Path]:
    """Return the subset of ``sources`` newer (by mtime) than ``output_jar``.

    Empty list means the jar is up to date with every source file.
    """
    jar_mtime = output_jar.stat().st_mtime
    return [s for s in sources if s.stat().st_mtime > jar_mtime]


def _ensure_framework_jar() -> None:
    """Compile the framework source into vcfcf-adapter-base.jar if needed.

    In the factory the jar is pre-built and committed to adapter_runtime/.
    In the sdk-buildkit tarball the jar is NOT shipped (to avoid stale-binary
    drift) — instead adapter_framework/src/ is bundled and compiled here on
    first use against the consumer-supplied SDK jar (VCFCF_SDK_JAR / --sdk-jar).

    This is a no-op ONLY when adapter_runtime/vcfcf-adapter-base.jar already
    exists AND no file under adapter_framework/src/ is newer than it (fresh
    jar — factory mode with a jar built from the current source, or a
    previous build in the same consumer session).

    If the jar exists but is STALE (any .java file under
    adapter_framework/src/ has a newer mtime), it is rebuilt from the
    current source tree — a silent no-op on stale input would ship a pak
    that carries an old framework binary despite reviewed source changes
    (the silent-downgrade failure mode; see synology build 23 containment
    proof). If the source tree is not present in this context (e.g. a
    runtime-only distribution that ships the jar but not adapter_framework/
    src/), staleness cannot be checked and the existing jar is used as-is.

    Raises SdkBuildError if the source tree is present but compilation fails,
    or if neither the jar nor the source tree can be found, or if the jar is
    stale and cannot be rebuilt (e.g. no SDK jar / no javac available).
    """
    output_jar = _ADAPTER_RUNTIME_DIR / "vcfcf-adapter-base.jar"
    src_dir = _ADAPTER_FRAMEWORK_SRC_DIR

    if output_jar.is_file():
        if not src_dir.is_dir():
            # No source tree to check staleness against (e.g. a runtime-only
            # distribution). Use the jar as shipped.
            return
        sources = sorted(src_dir.rglob("*.java"))
        if not sources:
            return
        stale = _find_stale_framework_sources(output_jar, sources)
        if not stale:
            return  # jar is fresh — nothing to do
        print(
            f"  framework: {output_jar.name} is STALE — "
            f"{len(stale)} source file(s) newer than the jar "
            f"(e.g. {stale[0].relative_to(src_dir)}); rebuilding...",
            file=sys.stderr,
        )
    else:
        if not src_dir.is_dir():
            raise SdkBuildError(
                f"vcfcf-adapter-base.jar not found at {output_jar} and framework "
                f"source tree not found at {src_dir}.\n"
                "This indicates a corrupt or incomplete sdk-buildkit installation.\n"
                "Re-download the kit: "
                "gh release download sdk-buildkit-v1 --repo sentania-labs/vcf-content-factory "
                "--pattern 'sdk-buildkit-*.tgz'"
            )

        # Locate all .java sources under adapter_framework/src/
        sources = sorted(src_dir.rglob("*.java"))
        if not sources:
            raise SdkBuildError(
                f"Framework source tree at {src_dir} contains no .java files.\n"
                "Re-download the sdk-buildkit tarball."
            )

    # Determine the compile classpath — SDK jar only (matches build-framework.sh)
    sdk_jar_env = os.environ.get("VCFCF_SDK_JAR", "").strip()
    if sdk_jar_env:
        sdk_jar_path = Path(sdk_jar_env)
        if not sdk_jar_path.is_file():
            raise SdkBuildError(
                f"VCFCF_SDK_JAR={sdk_jar_env!r} — file not found.\n"
                "Cannot compile framework source without the SDK jar."
            )
        fw_classpath = str(sdk_jar_path)
    else:
        # Check adapter_runtime/ for the SDK jar (factory/local-dev mode)
        sdk_jars = sorted(_ADAPTER_RUNTIME_DIR.glob("vrops-adapters-sdk-*.jar"))
        if not sdk_jars:
            raise SdkBuildError(
                "Cannot compile framework source: vrops-adapters-sdk-*.jar not found "
                "in adapter_runtime/ and VCFCF_SDK_JAR is not set.\n"
                "Supply the SDK jar via --sdk-jar or VCFCF_SDK_JAR before building."
            )
        fw_classpath = str(sdk_jars[0])

    javac = shutil.which("javac")
    if javac is None:
        raise SdkBuildError(
            "javac not found on PATH — cannot compile framework source.\n"
            "Install JDK 11+:\n"
            "  Ubuntu/Debian: sudo apt-get install -y openjdk-17-jdk\n"
            "  RHEL/CentOS:   sudo dnf install -y java-17-openjdk-devel"
        )

    jar_tool = shutil.which("jar")
    if jar_tool is None:
        raise SdkBuildError(
            "jar tool not found on PATH — cannot package framework jar.\n"
            "Ensure the JDK bin directory (which contains 'jar') is on PATH."
        )

    print(
        f"  framework: compiling {len(sources)} source file(s) from {src_dir} ...",
        file=sys.stderr,
    )

    with tempfile.TemporaryDirectory(prefix="vcfcf-framework-build-") as tmpdir:
        build_dir = Path(tmpdir) / "classes"
        build_dir.mkdir()

        cmd = [
            javac,
            "-source", "11", "-target", "11",
            "-cp", fw_classpath,
            "-d", str(build_dir),
        ] + [str(s) for s in sources]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise SdkBuildError(
                f"Framework compilation failed:\n{result.stderr}\n{result.stdout}\n"
                "If errors mention com.vmware.tvs.* or alive* symbols this is a "
                "clean-room wall violation — report as a TOOLSET GAP."
            )

        # Package the compiled classes into vcfcf-adapter-base.jar
        _ADAPTER_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        cmd_jar = [jar_tool, "cf", str(output_jar), "-C", str(build_dir), "."]
        result_jar = subprocess.run(cmd_jar, capture_output=True, text=True)
        if result_jar.returncode != 0:
            raise SdkBuildError(
                f"Framework jar packaging failed:\n{result_jar.stderr}\n{result_jar.stdout}"
            )

    sz = output_jar.stat().st_size
    print(
        f"  framework: built {output_jar.name} ({sz // 1024} KB)",
        file=sys.stderr,
    )


def _read_license() -> str:
    """Return the contents of the repo LICENSE file.

    Falls back to an empty string (with a printed warning) if the file
    does not exist so the build does not crash over a missing license file.
    """
    if _LICENSE_PATH.is_file():
        return _LICENSE_PATH.read_text(encoding="utf-8")
    print(
        f"  WARNING: LICENSE file not found at {_LICENSE_PATH}; "
        "writing empty eula.txt.",
        file=sys.stderr,
    )
    return ""

# JARs that ship in every pak's lib/ — framework only by default.
# vrops-adapters-sdk is on the appliance shared classpath and is NEVER bundled
# (proven by C2 test — see context/investigations/c2_no_sdk_jar_install_test.md).
# aria-ops-core is conditionally bundled for v1 adapters that reference
# com.vmware.tvs.* — detected automatically at build time via _needs_aria_ops_core().
_FRAMEWORK_JAR_PATTERN = "vcfcf-adapter-base.jar"
_ARIA_OPS_CORE_PATTERN = "aria-ops-core-*.jar"
_SDK_JAR_PATTERN = "vrops-adapters-sdk-*.jar"

# JARs that are on the appliance shared classpath — compile against, NEVER bundle.
# vrops-adapters-sdk is included here: it is kept on the javac classpath (Layer 1
# of the three-layer stack) but resolves from the appliance at runtime.
# TODO: aria-ops-core can be removed from the compile classpath once all v1
#       adapters (synology, unifi, compliance) have been migrated to framework v2.
_SHARED_CLASSPATH_PATTERNS = [
    "alive_common.jar",
    "alive_platform.jar",
]

# Reference pak directories to check for pak-compare
_REFERENCES_DIR = _HERE.parent / "tmp" / "reference_paks"


class SdkBuildError(RuntimeError):
    """Raised when the SDK build fails for a recoverable reason."""


# ---------------------------------------------------------------------------
# Version-line guardrail (RULE: hand-built paks are always 0.x)
# ---------------------------------------------------------------------------
#
# Every version surface in a built pak (filename, outer/inner manifest.txt
# "version", conf/version.txt Major/Minor/Implementation-Version, and the
# overview.packed "Version x.y.z.n" HTML blurbs) is derived from
# SdkProjectDef.version + SdkProjectDef.build_number.  To guarantee a
# hand-built / local dev preview pak is never version-indistinguishable
# from a CI release build, the default build overwrites project.version
# with "0.0.0" (build_number is left untouched, so the stamp is always
# "0.0.0.<build_number>") — regardless of what adapter.yaml declares.
# The real adapter.yaml version is used ONLY when the caller explicitly
# opts in to a release build, via the VCFCF_RELEASE_BUILD env var (set by
# the --release CLI flag, mirroring the existing VCFCF_SDK_JAR convention
# in cli.py's _apply_sdk_jar_flag) — never by default.
_RELEASE_BUILD_ENV = "VCFCF_RELEASE_BUILD"
_RELEASE_BUILD_TRUE_VALUES = {"1", "true", "yes"}


def _is_release_build() -> bool:
    """Return True only when the release opt-in env var is explicitly set."""
    return os.environ.get(_RELEASE_BUILD_ENV, "").strip().lower() in _RELEASE_BUILD_TRUE_VALUES


def _stamp_build_version(project: SdkProjectDef, release_build: bool) -> str:
    """Stamp project.version in place per the dev-preview/release convention.

    Mutates ``project.version`` (SdkProjectDef is not frozen) so every
    downstream consumer — pak_filename, _generate_outer_manifest,
    _generate_version_txt, _build_overview_packed — picks up the correct
    line automatically without threading a new parameter through each of
    them individually. Returns the declared (adapter.yaml) version for
    logging/reporting purposes.

    Logs exactly one INFO line stating which line was stamped and why.
    """
    declared_version = project.version
    if release_build:
        print(
            f"  INFO: version stamp -> release build -> "
            f"{project.version}.{project.build_number} "
            f"(VCFCF_RELEASE_BUILD opt-in active; using adapter.yaml version)",
            file=sys.stderr,
        )
        return declared_version

    project.version = "0.0.0"
    print(
        f"  INFO: version stamp -> dev preview -> "
        f"0.0.0.{project.build_number} "
        f"(adapter.yaml declares {declared_version}; hand-built paks are "
        f"always version line 0.x — pass --release / set "
        f"{_RELEASE_BUILD_ENV}=1 for a CI release build)",
        file=sys.stderr,
    )
    return declared_version


def _find_jars(directory: Path, pattern: str) -> List[Path]:
    """Return all JARs in directory matching the glob pattern."""
    return sorted(directory.glob(pattern))


def _detect_jdk() -> str:
    """Locate javac on PATH. Returns the javac path string.

    Raises SdkBuildError with install instructions if not found.
    """
    javac = shutil.which("javac")
    if javac is None:
        raise SdkBuildError(
            "javac not found on PATH. Install JDK 11 or newer:\n"
            "  Ubuntu/Debian: sudo apt-get install -y openjdk-17-jdk\n"
            "  RHEL/CentOS:   sudo dnf install -y java-17-openjdk-devel\n"
            "  macOS (brew):  brew install openjdk@17\n"
            "Then ensure javac is on PATH."
        )
    # Quick version check
    try:
        result = subprocess.run([javac, "-version"], capture_output=True, text=True, timeout=10)
        version_str = result.stderr.strip() or result.stdout.strip()
    except Exception as exc:
        raise SdkBuildError(f"javac found at {javac} but version check failed: {exc}") from exc
    return javac


def _detect_jar_tool() -> str:
    """Locate the jar tool on PATH. Returns path string."""
    jar = shutil.which("jar")
    if jar is None:
        raise SdkBuildError(
            "jar tool not found on PATH. It ships with the JDK. "
            "Ensure the JDK bin directory is on PATH."
        )
    return jar


def _build_classpath(project_dir: Path) -> str:
    """Build the javac classpath: runtime JARs (all) + project lib/*.jar.

    Compile against all runtime JARs (including SDK JARs that won't be bundled).
    The shared-classpath distinction only matters at packaging time.

    SDK JAR injection (kit / CI mode):
      When running outside the factory (e.g. from the sdk-buildkit tarball in CI)
      the adapter_runtime/ directory only contains vcfcf-adapter-base.jar — no
      Broadcom JARs (they cannot ship in a public toolchain tarball; see the
      redistribution survey at context/cleanroom-spec/analysis/sdk-survey/).
      In that case the SDK JAR must be supplied via the VCFCF_SDK_JAR environment
      variable or the --sdk-jar CLI flag (which sets the same env var before calling
      this function).  A clear error is raised when the SDK JAR is absent from both
      adapter_runtime/ and the env var.

      Factory / local-dev mode: VCFCF_SDK_JAR is optional — the jar is already in
      adapter_runtime/ and will be found by the glob below.
    """
    jars: List[Path] = []

    # All adapter_runtime JARs for compilation (SDK, framework, aria-ops-core, etc.)
    for jar in sorted(_ADAPTER_RUNTIME_DIR.glob("*.jar")):
        jars.append(jar)
    # Also adapter_runtime/lib/*.jar (Tier 1 libs — compile harmless, not bundled)
    for jar in sorted((_ADAPTER_RUNTIME_DIR / "lib").glob("*.jar") if (_ADAPTER_RUNTIME_DIR / "lib").is_dir() else []):
        jars.append(jar)

    # VCFCF_SDK_JAR: allow consumers (CI / sdk-buildkit) to inject the Broadcom
    # SDK jar via env var when it is not present in adapter_runtime/.
    sdk_jar_env = os.environ.get("VCFCF_SDK_JAR", "").strip()
    if sdk_jar_env:
        sdk_jar_path = Path(sdk_jar_env)
        if not sdk_jar_path.is_file():
            raise SdkBuildError(
                f"VCFCF_SDK_JAR is set to {sdk_jar_env!r} but the file does not exist.\n"
                "Obtain vrops-adapters-sdk-2.2.jar from your VCF Ops appliance:\n"
                "  scp root@<appliance>:/usr/lib/vmware-vcops/common-lib/vrops-adapters-sdk-2.2.jar .\n"
                "  (also at: /usr/lib/vmware-vcops/suite-api/WEB-INF/lib/vrops-adapters-sdk.jar)\n"
                "Then set VCFCF_SDK_JAR to the local path."
            )
        # Only add if not already on the classpath (avoid duplicates in factory mode).
        if sdk_jar_path not in jars:
            jars.insert(0, sdk_jar_path)
    else:
        # Check whether the SDK jar is already covered by adapter_runtime/ globs.
        has_sdk = any(
            "vrops-adapters-sdk" in j.name for j in jars
        )
        if not has_sdk:
            raise SdkBuildError(
                "vrops-adapters-sdk-*.jar not found in adapter_runtime/ and "
                "VCFCF_SDK_JAR is not set.\n"
                "This JAR is a Broadcom internal build artifact that cannot ship "
                "in a public toolchain tarball.\n"
                "Obtain it from your VCF Ops appliance and set VCFCF_SDK_JAR:\n"
                "  export VCFCF_SDK_JAR=/path/to/vrops-adapters-sdk-2.2.jar\n"
                "Or copy the file from the appliance:\n"
                "  scp root@<appliance>:/usr/lib/vmware-vcops/common-lib/vrops-adapters-sdk-2.2.jar .\n"
                "  export VCFCF_SDK_JAR=$(pwd)/vrops-adapters-sdk-2.2.jar\n"
                "The jar is also available at:\n"
                "  /usr/lib/vmware-vcops/suite-api/WEB-INF/lib/vrops-adapters-sdk.jar"
            )

    # Project-local lib/ (optional vendor JARs)
    project_lib = project_dir / "lib"
    if project_lib.is_dir():
        for jar in sorted(project_lib.glob("*.jar")):
            jars.append(jar)

    if not jars:
        raise SdkBuildError(
            f"No JARs found in {_ADAPTER_RUNTIME_DIR}. "
            "Run the Tier 2 bootstrap to populate adapter_runtime/ "
            "(see vcfops_managementpacks/README.md)."
        )

    separator = ";" if sys.platform.startswith("win") else ":"
    return separator.join(str(j) for j in jars)


def _find_sources(project_dir: Path) -> List[Path]:
    """Find all .java source files under project_dir/src/."""
    src_dir = project_dir / "src"
    if not src_dir.is_dir():
        raise SdkBuildError(
            f"No src/ directory found in {project_dir}. "
            "Adapter source code must be under src/."
        )
    sources = sorted(src_dir.rglob("*.java"))
    if not sources:
        raise SdkBuildError(f"No .java files found under {src_dir}")
    return sources


def _compile(javac: str, classpath: str, sources: List[Path],
             build_dir: Path) -> None:
    """Compile Java sources into build_dir. Raises SdkBuildError on failure."""
    build_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        javac,
        "-source", "11", "-target", "11",
        "-cp", classpath,
        "-d", str(build_dir),
    ] + [str(s) for s in sources]

    print(f"  javac: compiling {len(sources)} source file(s)...", file=sys.stderr)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SdkBuildError(
            f"javac compilation failed:\n{result.stderr}\n{result.stdout}"
        )
    if result.stderr.strip():
        print(f"  javac warnings:\n{result.stderr}", file=sys.stderr)


def _write_adapter_properties(build_dir: Path, project: SdkProjectDef) -> None:
    """Write adapter.properties into the build dir (root of the entry JAR)."""
    props_content = (
        f"ENTRYCLASS={project.entry_class}\n"
        f"KINDKEY={project.adapter_kind}\n"
    )
    (build_dir / "adapter.properties").write_text(props_content, encoding="utf-8")


def _package_adapter_jar(jar_tool: str, build_dir: Path, jar_path: Path) -> None:
    """Package compiled classes + adapter.properties into the entry JAR."""
    jar_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [jar_tool, "cf", str(jar_path), "-C", str(build_dir), "."]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SdkBuildError(f"jar packaging failed:\n{result.stderr}\n{result.stdout}")


def _needs_aria_ops_core(build_dir: Path) -> bool:
    """Return True if the compiled classes reference com/vmware/tvs (v1 adapters).

    Scans every .class file in build_dir for the UTF-8 byte sequence
    b'com/vmware/tvs' — this is the constant-pool string prefix for all
    aria-ops-core types (com.vmware.tvs.vrealize.adapter.core.*).
    v2 adapters that extend VcfCfAdapter directly have no such reference
    and return False; v1 adapters that still use UnlicensedAdapter or any
    other TVS type return True.

    This is the gating condition for bundling aria-ops-core in lib/:
      - True  → bundle aria-ops-core (v1 adapter; TVS types needed at runtime)
      - False → do NOT bundle (v2 adapter; no TVS dependency)

    Uses a raw byte scan rather than full class-file parsing — the UTF-8
    string constants in a .class constant pool are stored as raw bytes
    preceded by a CONSTANT_Utf8 tag (0x01), so a substring search is
    sufficient and avoids any additional dependency.
    """
    tvs_marker = b"com/vmware/tvs"
    for class_file in build_dir.rglob("*.class"):
        try:
            data = class_file.read_bytes()
            if tvs_marker in data:
                return True
        except OSError:
            pass
    return False


def _collect_lib_jars(project_dir: Path, build_dir: Optional[Path] = None) -> List[Path]:
    """Collect JARs to bundle in the pak's <adapter>/lib/ directory.

    Always bundle:
      - vcfcf-adapter-base.jar (our framework; never on appliance classpath)
      - project lib/*.jar (optional vendor JARs)

    Conditionally bundle:
      - aria-ops-core-*.jar — ONLY if compiled classes reference com.vmware.tvs.*
        (v1 adapters not yet migrated to framework v2).  Detected automatically
        via _needs_aria_ops_core(build_dir).  When build_dir is not supplied
        (e.g. dry-run callers), aria-ops-core is bundled conservatively to avoid
        producing a broken pak for v1 adapters.
        Once all adapters are migrated to v2, this conditional can be removed.

    Never bundle:
      - vrops-adapters-sdk-*.jar — resolves from the appliance shared classpath
        at runtime (proven by C2 test, build 42, 2026-06-09).  Still on the
        javac compile classpath for Layer 1 SPI access.
      - alive_common.jar / alive_platform.jar — on the appliance shared classpath.
    """
    lib_jars: List[Path] = []

    # Framework JAR — always bundled
    fw_jars = _find_jars(_ADAPTER_RUNTIME_DIR, _FRAMEWORK_JAR_PATTERN)
    if not fw_jars:
        raise SdkBuildError(
            f"vcfcf-adapter-base.jar not found in {_ADAPTER_RUNTIME_DIR}.\n"
            "Build it first: cd vcfops_managementpacks && "
            "./adapter_framework/build-framework.sh"
        )
    lib_jars.extend(fw_jars)

    # aria-ops-core — bundle only for v1 adapters (com.vmware.tvs.* reference detected)
    # Conservative fallback: if build_dir is unknown, bundle to avoid breaking v1 paks.
    if build_dir is not None:
        bundle_aria = _needs_aria_ops_core(build_dir)
        if bundle_aria:
            print(
                "  lib/: aria-ops-core detected as required (v1 adapter — "
                "com.vmware.tvs.* reference found in compiled classes); bundling.",
                file=sys.stderr,
            )
        else:
            print(
                "  lib/: aria-ops-core NOT required (v2 adapter — no com.vmware.tvs.* "
                "reference in compiled classes); omitting from lib/.",
                file=sys.stderr,
            )
    else:
        bundle_aria = True  # conservative fallback

    if bundle_aria:
        core_jars = _find_jars(_ADAPTER_RUNTIME_DIR, _ARIA_OPS_CORE_PATTERN)
        if not core_jars:
            print(
                "  WARNING: aria-ops-core-*.jar not found in adapter_runtime/ "
                "but the adapter requires it (v1 — TVS reference detected). "
                "The pak may fail to load on the appliance.",
                file=sys.stderr,
            )
        lib_jars.extend(core_jars)

    # vrops-adapters-sdk is NEVER bundled — resolves from appliance classpath.
    # (C2 test confirmed: install + collection succeed without it in lib/.)

    # Project-local vendor JARs
    project_lib = project_dir / "lib"
    if project_lib.is_dir():
        lib_jars.extend(sorted(project_lib.glob("*.jar")))

    return lib_jars


def _load_icon_map(project_dir: Path) -> Dict[str, str]:
    """Load the icon mapping from project_dir/icons/icons.yaml.

    Returns a dict mapping ResourceKind key -> icon filename.
    Also exposes 'adapter_kind_icon' under the special key '_adapter_kind'.
    Returns an empty dict when the file is missing or yaml is unavailable.
    """
    icons_yaml = project_dir / "icons" / "icons.yaml"
    if not icons_yaml.is_file() or not _YAML_AVAILABLE:
        return {}
    with icons_yaml.open(encoding="utf-8") as fh:
        data = _yaml.safe_load(fh) or {}
    mapping: Dict[str, str] = {}
    if "adapter_kind_icon" in data:
        mapping["_adapter_kind"] = data["adapter_kind_icon"]
    for rk, icon in (data.get("resource_kinds") or {}).items():
        mapping[str(rk)] = str(icon)
    return mapping


def _resolve_icon(name: str, project_dir: Path) -> bytes:
    """Resolve an icon file name to its bytes.

    Search order:
      1. project_dir/icons/<name>
      2. templates/icons/<name>
      3. templates/icons/default.svg
    Returns empty bytes only if none of the above exist.
    """
    candidates = [
        project_dir / "icons" / name,
        _HERE / "templates" / "icons" / name,
        _HERE / "templates" / "icons" / "default.svg",
    ]
    for path in candidates:
        if path.is_file():
            return path.read_bytes()
    return b""


def _parse_resource_kind_keys(describe_xml: Path) -> List[str]:
    """Return all ResourceKind key attribute values from describe.xml."""
    try:
        tree = ET.parse(describe_xml)
    except ET.ParseError as exc:
        print(f"  icons: could not parse describe.xml: {exc}", file=sys.stderr)
        return []
    root = tree.getroot()
    # Strip namespace prefix if present
    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0] + "}"
    keys: List[str] = []
    for rk in root.iter(f"{ns}ResourceKind"):
        key = rk.get("key")
        if key:
            keys.append(key)
    return keys


def _find_world_resource_kind(describe_xml: Path) -> Optional[str]:
    """Return the key of the first ResourceKind with type="1" in describe.xml.

    By convention, the type=1 ResourceKind is the adapter's "World" kind —
    the top-level container used as the owning-adapter SubjectType anchor in
    view XML (spec A2).  Returns None if none is found or the file cannot be
    parsed; callers should log a warning and skip the second SubjectType.
    """
    try:
        tree = ET.parse(describe_xml)
    except ET.ParseError as exc:
        print(
            f"  world-kind: could not parse describe.xml: {exc}",
            file=sys.stderr,
        )
        return None
    root = tree.getroot()
    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0] + "}"
    for rk in root.iter(f"{ns}ResourceKind"):
        if rk.get("type", "") == "1":
            key = rk.get("key", "")
            if key:
                return key
    return None


def _pack_icons(
    zf: zipfile.ZipFile,
    project: SdkProjectDef,
    project_dir: Path,
    describe_xml: Path,
) -> None:
    """Write conf/images/* icon entries into the open adapters.zip ZipFile.

    Writes:
      <adapter_dir>/conf/images/AdapterKind/<adapter_kind>.svg
      <adapter_dir>/conf/images/ResourceKind/<resource_kind_key>.svg  (one per RK)
      <adapter_dir>/conf/images/TraversalSpec/default.svg

    Directory entries are added before each file group (required by the
    platform's SyncAdapters.extractFiles() — it uses Files.copy() and
    needs parent dirs to pre-exist from explicit zip directory entries).
    """
    adapter_dir = project.adapter_dir_name
    icon_map = _load_icon_map(project_dir)

    def _add_dir(dirname: str) -> None:
        if not dirname.endswith("/"):
            dirname += "/"
        zf.writestr(dirname, "")

    # --- AdapterKind icon ---
    _add_dir(f"{adapter_dir}/conf/images")
    _add_dir(f"{adapter_dir}/conf/images/AdapterKind")
    ak_icon_name = icon_map.get("_adapter_kind", "default.svg")
    ak_icon_bytes = _resolve_icon(ak_icon_name, project_dir)
    zf.writestr(
        f"{adapter_dir}/conf/images/AdapterKind/{project.adapter_kind}.svg",
        ak_icon_bytes,
    )
    print(
        f"  icons: AdapterKind/{project.adapter_kind}.svg <- {ak_icon_name}",
        file=sys.stderr,
    )

    # --- ResourceKind icons ---
    rk_keys = _parse_resource_kind_keys(describe_xml)
    if rk_keys:
        _add_dir(f"{adapter_dir}/conf/images/ResourceKind")
        for rk_key in rk_keys:
            icon_name = icon_map.get(rk_key, "default.svg")
            icon_bytes = _resolve_icon(icon_name, project_dir)
            dest = f"{adapter_dir}/conf/images/ResourceKind/{rk_key}.svg"
            zf.writestr(dest, icon_bytes)
            print(
                f"  icons: ResourceKind/{rk_key}.svg <- {icon_name}",
                file=sys.stderr,
            )

    # --- TraversalSpec icon ---
    _add_dir(f"{adapter_dir}/conf/images/TraversalSpec")
    ts_icon_bytes = _resolve_icon("default.svg", project_dir)
    zf.writestr(
        f"{adapter_dir}/conf/images/TraversalSpec/default.svg",
        ts_icon_bytes,
    )
    print(f"  icons: TraversalSpec/default.svg <- default.svg", file=sys.stderr)


def _generate_version_txt(project: SdkProjectDef) -> str:
    """Generate the content of conf/version.txt from adapter.yaml version fields.

    Format mirrors MPB-generated paks (confirmed against phpIPAM-1.0.0.11.pak and
    Ubiquiti_UniFi-1.0.0.7.pak in tmp/reference_paks/).  The VCF Ops collector reads
    these properties via VersionDotTxt and logs the adapter version on startup; without
    this file every property returns null and the log shows
    '<adapter_kind> adapter version: null.null.null.null.null'.

    Mapping from SdkProjectDef (version = "MAJOR.MINOR.PATCH", build_number = N):
      Major-Version          <- MAJOR
      Minor-Version          <- MINOR
      Implementation-Version <- PATCH.N   (patch + build_number joined by ".")
      Build-Tools-Version-Ref <- N/A      (MPB build toolchain ref; not applicable)
      Adapter-Version-Ref    <- vrops-adapters-sdk version detected from adapter_runtime/
      Core-Version-Ref       <- aria-ops-core version detected from adapter_runtime/
    """
    parts = project.version.split(".")
    major = parts[0] if len(parts) > 0 else "1"
    minor = parts[1] if len(parts) > 1 else "0"
    patch = parts[2] if len(parts) > 2 else "0"
    impl = f"{patch}.{project.build_number}"

    # Detect Core-Version-Ref from the aria-ops-core jar present in adapter_runtime/
    core_ver = "8.0.0"
    core_jars = _find_jars(_ADAPTER_RUNTIME_DIR, _ARIA_OPS_CORE_PATTERN)
    if core_jars:
        # aria-ops-core-8.0.0.jar -> "8.0.0"
        stem = core_jars[0].stem  # e.g. "aria-ops-core-8.0.0"
        if "-" in stem:
            core_ver = stem.rsplit("-", 1)[-1]

    # Detect Adapter-Version-Ref from vrops-adapters-sdk jar present in adapter_runtime/
    adapter_ver_ref = "N/A"
    sdk_jars = _find_jars(_ADAPTER_RUNTIME_DIR, _SDK_JAR_PATTERN)
    if sdk_jars:
        # vrops-adapters-sdk-2.2.jar -> "2.2"
        stem = sdk_jars[0].stem
        if "-" in stem:
            adapter_ver_ref = stem.rsplit("-", 1)[-1]

    lines = [
        f"Major-Version={major}",
        f"Minor-Version={minor}",
        f"Implementation-Version={impl}",
        f"Build-Tools-Version-Ref=N/A",
        f"Adapter-Version-Ref={adapter_ver_ref}",
        f"Core-Version-Ref={core_ver}",
    ]
    return "\n".join(lines) + "\n"


def _load_bundled_content(
    raw: dict,
    project_dir: Path,
    repo_root: Path,
):
    """Parse the optional ``bundled_content`` key from a raw adapter.yaml dict.

    Returns a tuple ``(views, dashboards, supermetrics, symptoms, alerts, reports, recommendations)``
    where each is a list of loaded objects.  Returns ``([], [], [], [], [], [], [])``
    when the key is absent or empty.

    Paths in all ``bundled_content.*`` sub-keys are relative to the adapter
    project directory (where adapter.yaml lives), NOT the factory repo root.
    The ``repo_root`` parameter is accepted for backward-compatibility but is
    unused; callers should pass ``project_dir`` for both arguments.

    Accepted sub-keys:
      views:           list of paths → ViewDef objects (vcfops_dashboards)
      dashboards:      list of paths → Dashboard objects (vcfops_dashboards)
      supermetrics:    list of paths → SuperMetricDef objects (vcfops_supermetrics)
      symptoms:        list of paths → SymptomDef objects (vcfops_symptoms)
      alerts:          list of paths → AlertDef objects (vcfops_alerts)
      reports:         list of paths → ReportDef objects (vcfops_reports)
      recommendations: list of paths → Recommendation objects (vcfops_alerts)

    Raises:
        SdkBuildError: if a listed path does not exist or fails to load.
    """
    bundled = raw.get("bundled_content") or {}
    if not bundled:
        return [], [], [], [], [], [], []

    try:
        from vcfops_dashboards.loader import load_view, load_dashboard
    except ImportError as exc:
        raise SdkBuildError(
            f"bundled_content requires vcfops_dashboards to be installed: {exc}"
        ) from exc

    views = []
    for rel in (bundled.get("views") or []):
        path = (project_dir / rel).resolve()
        if not path.is_file():
            raise SdkBuildError(
                f"bundled_content.views: path not found: {path} "
                f"(resolved from '{rel}' relative to {project_dir})"
            )
        try:
            v = load_view(path, enforce_framework_prefix=False)
        except Exception as exc:
            raise SdkBuildError(
                f"bundled_content.views: failed to load {path}: {exc}"
            ) from exc
        views.append(v)

    dashboards = []
    for rel in (bundled.get("dashboards") or []):
        path = (project_dir / rel).resolve()
        if not path.is_file():
            raise SdkBuildError(
                f"bundled_content.dashboards: path not found: {path} "
                f"(resolved from '{rel}' relative to {project_dir})"
            )
        try:
            d = load_dashboard(path, enforce_framework_prefix=False)
        except Exception as exc:
            raise SdkBuildError(
                f"bundled_content.dashboards: failed to load {path}: {exc}"
            ) from exc
        dashboards.append(d)

    # --- Super Metrics ---
    supermetrics = []
    for rel in (bundled.get("supermetrics") or []):
        path = (project_dir / rel).resolve()
        if not path.is_file():
            raise SdkBuildError(
                f"bundled_content.supermetrics: path not found: {path} "
                f"(resolved from '{rel}' relative to {project_dir})"
            )
        try:
            from vcfops_supermetrics.loader import load_file as _load_sm
            sm = _load_sm(path, enforce_framework_prefix=False)
        except Exception as exc:
            raise SdkBuildError(
                f"bundled_content.supermetrics: failed to load {path}: {exc}"
            ) from exc
        supermetrics.append(sm)

    # --- Symptoms ---
    symptoms = []
    for rel in (bundled.get("symptoms") or []):
        path = (project_dir / rel).resolve()
        if not path.is_file():
            raise SdkBuildError(
                f"bundled_content.symptoms: path not found: {path} "
                f"(resolved from '{rel}' relative to {project_dir})"
            )
        try:
            from vcfops_symptoms.loader import load_file as _load_sym
            sym = _load_sym(path, enforce_framework_prefix=False)
        except Exception as exc:
            raise SdkBuildError(
                f"bundled_content.symptoms: failed to load {path}: {exc}"
            ) from exc
        symptoms.append(sym)

    # --- Alerts ---
    alerts = []
    for rel in (bundled.get("alerts") or []):
        path = (project_dir / rel).resolve()
        if not path.is_file():
            raise SdkBuildError(
                f"bundled_content.alerts: path not found: {path} "
                f"(resolved from '{rel}' relative to {project_dir})"
            )
        try:
            from vcfops_alerts.loader import load_file as _load_alert
            alert = _load_alert(path, enforce_framework_prefix=False)
        except Exception as exc:
            raise SdkBuildError(
                f"bundled_content.alerts: failed to load {path}: {exc}"
            ) from exc
        alerts.append(alert)

    # --- Reports ---
    reports = []
    for rel in (bundled.get("reports") or []):
        path = (project_dir / rel).resolve()
        if not path.is_file():
            raise SdkBuildError(
                f"bundled_content.reports: path not found: {path} "
                f"(resolved from '{rel}' relative to {project_dir})"
            )
        try:
            from vcfops_reports.loader import load_file as _load_report
            report = _load_report(path, enforce_framework_prefix=False)
        except Exception as exc:
            raise SdkBuildError(
                f"bundled_content.reports: failed to load {path}: {exc}"
            ) from exc
        reports.append(report)

    # --- Recommendations ---
    recommendations = []
    for rel in (bundled.get("recommendations") or []):
        path = (project_dir / rel).resolve()
        if not path.is_file():
            raise SdkBuildError(
                f"bundled_content.recommendations: path not found: {path} "
                f"(resolved from '{rel}' relative to {project_dir})"
            )
        try:
            from vcfops_alerts.loader import load_recommendation_file as _load_rec
            rec = _load_rec(path, enforce_framework_prefix=False)
        except Exception as exc:
            raise SdkBuildError(
                f"bundled_content.recommendations: failed to load {path}: {exc}"
            ) from exc
        recommendations.append(rec)

    return views, dashboards, supermetrics, symptoms, alerts, reports, recommendations


def _build_views_zip_bytes(views: list, sm_scope: Optional[List[Path]] = None) -> bytes:
    """Render ``views`` (list of ViewDef) to a zip containing content.xml.

    Returns the zip bytes.  The zip structure mirrors what the VCF Ops
    content importer expects inside a views import payload.

    ``sm_scope``: when provided, restricts SM name resolution to only these
    YAML files (same scoped-resolution contract used at pak build time).
    """
    from vcfops_dashboards.render import render_views_xml
    xml_text = render_views_xml(views, sm_scope=sm_scope)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("content.xml", xml_text)
    return buf.getvalue()


def _assemble_adapters_zip(
    project: SdkProjectDef,
    project_dir: Path,
    adapter_jar: Path,
    lib_jars: List[Path],
    views_zip_bytes: Optional[bytes] = None,
) -> bytes:
    """Build adapters.zip in memory and return as bytes.

    Structure:
      manifest.txt                     [JSON — identical to outer pak manifest.txt]
      eula.txt
      resources/resources.properties
      <adapter_kind>.jar               [entry JAR]
      <adapter_kind>/
        conf/
          describe.xml
          version.txt
          resources/resources.properties
          views/
            views.zip                  [optional; present when views_zip_bytes given]
        lib/
          vcfcf-adapter-base.jar
          aria-ops-core-*.jar   [v1 adapters only — conditionally included by _collect_lib_jars]
          [project lib/*.jar]

    Note: declarative content (dashboards, views) is NOT written inside
    adapters.zip.  The platform only auto-imports the outer pak's content/
    directory (spec A4).  Content lives exclusively in the outer pak.
    """
    buf = io.BytesIO()
    adapter_dir = project.adapter_dir_name

    def _add_dir(zf: zipfile.ZipFile, dirname: str) -> None:
        """Add an explicit zero-byte directory entry to the zip.

        The platform's SyncAdapters.extractFiles() uses Files.copy()
        which requires parent directories to exist.  It creates them
        from explicit directory entries in the zip — without these,
        extraction fails with NoSuchFileException.
        """
        if not dirname.endswith("/"):
            dirname += "/"
        zf.writestr(dirname, "")

    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Inner manifest.txt — JSON format, identical to outer pak manifest.txt.
        zf.writestr("manifest.txt", _generate_outer_manifest(project))

        # eula.txt — MIT license text, duplicated from outer pak per wire format
        zf.writestr("eula.txt", _read_license())

        # default.svg — pak icon duplicated inside adapters.zip (validate phase
        # checks for it).  Use the AdapterKind icon so Repository/Accounts
        # shows the real icon instead of a black-square placeholder.
        icon_map = _load_icon_map(project_dir)
        ak_icon_name = icon_map.get("_adapter_kind", "default.svg")
        pak_icon_bytes = _resolve_icon(ak_icon_name, project_dir)
        zf.writestr("default.svg", pak_icon_bytes)

        # resources/ directory + resources.properties at adapters.zip root
        _add_dir(zf, "resources")
        res_file = project_dir / "resources" / "resources.properties"
        if res_file.is_file():
            zf.writestr("resources/resources.properties",
                        res_file.read_bytes())
        else:
            zf.writestr("resources/resources.properties", "")

        # Entry JAR at the root of adapters.zip
        zf.write(adapter_jar, adapter_jar.name)

        # Adapter subdirectory tree — explicit dir entries first
        _add_dir(zf, adapter_dir)
        _add_dir(zf, f"{adapter_dir}/conf")
        _add_dir(zf, f"{adapter_dir}/conf/resources")
        _add_dir(zf, f"{adapter_dir}/lib")
        _add_dir(zf, f"{adapter_dir}/work")
        _add_dir(zf, f"{adapter_dir}/doc")

        # describe.xml
        describe_src = project_dir / "describe.xml"
        if not describe_src.is_file():
            raise SdkBuildError(
                f"describe.xml not found in {project_dir}. "
                "Every Tier 2 adapter must have a describe.xml."
            )
        zf.write(describe_src, f"{adapter_dir}/conf/describe.xml")

        # conf/version.txt — required by UnlicensedAdapter.logAdapterInformation().
        # Without it every property returns null and the collector logs
        # '<adapter_kind> adapter version: null.null.null.null.null'.
        zf.writestr(
            f"{adapter_dir}/conf/version.txt",
            _generate_version_txt(project),
        )

        # conf/resources/resources.properties
        if res_file.is_file():
            zf.write(res_file, f"{adapter_dir}/conf/resources/resources.properties")
        else:
            zf.writestr(f"{adapter_dir}/conf/resources/resources.properties", "")

        # conf/profiles/ — optional bundled data files (benchmark CSVs, etc.)
        # Walk recursively so adapter authors can group files by purpose
        # (e.g. profiles/canonical/*.csv for normalized data versus
        # profiles/*.csv for raw source data). Relative paths are preserved.
        #
        # IMPORTANT: for every file at path <prefix>/a/b/c/file the platform's
        # .upload staging extractor requires explicit zero-byte directory entries
        # for every ancestor path: <prefix>/a/, <prefix>/a/b/, <prefix>/a/b/c/.
        # Without these, Files.copy() fails with NoSuchFileException.
        # We use a seen-set to write each directory entry exactly once.
        profiles_dir = project_dir / "profiles"
        if profiles_dir.is_dir():
            _add_dir(zf, f"{adapter_dir}/conf/profiles")
            _dirs_written: set[str] = {f"{adapter_dir}/conf/profiles/"}
            for pf in sorted(profiles_dir.rglob("*")):
                if pf.is_file():
                    rel = pf.relative_to(profiles_dir).as_posix()
                    # Emit a dir entry for every ancestor between profiles/ and file.
                    parts = rel.split("/")
                    for depth in range(1, len(parts)):
                        ancestor = f"{adapter_dir}/conf/profiles/" + "/".join(parts[:depth]) + "/"
                        if ancestor not in _dirs_written:
                            _add_dir(zf, ancestor.rstrip("/"))
                            _dirs_written.add(ancestor)
                    zf.write(pf, f"{adapter_dir}/conf/profiles/{rel}")

        # conf/views/views.zip — belt-and-suspenders copy of rendered views
        if views_zip_bytes is not None:
            _add_dir(zf, f"{adapter_dir}/conf/views")
            zf.writestr(f"{adapter_dir}/conf/views/views.zip", views_zip_bytes)

        # NOTE: content/ is NOT written inside adapters.zip.
        # The platform only auto-imports the outer pak's content/ directory
        # (spec A4 — inner <adapter>/content/ is dead weight, never processed).
        # Declarative content lives exclusively in the outer pak's content/ tree.

        # lib/ directory — bundled JARs
        for jar in lib_jars:
            zf.write(jar, f"{adapter_dir}/lib/{jar.name}")

        # conf/images/ — icons per ResourceKind and AdapterKind
        _pack_icons(zf, project, project_dir, describe_src)

    return buf.getvalue()


def _build_overview_packed(project: SdkProjectDef) -> bytes:
    """Build overview.packed — a ZIP archive with the required directory structure.

    The overview.packed file is a ZIP archive that the VCF Ops Overview tab in
    the Solutions UI uses to render the adapter's overview page.  Per the vendor
    8.13 specification (Solution install/uninstall §9), the structure must be:

        overview/
          light/
            overview.html      # light-theme variant
          dark/
            overview.html      # dark-theme variant (mandatory — both themes required)

    Both light/ and dark/ subdirectories are mandatory.  The platform renders the
    appropriate variant based on the UI theme setting.  The HTML content can be
    identical between variants (or vary by CSS class); the platform only checks
    structure, not HTML semantics.

    Note: despite spec/18 §A0 (Pass 29), this file does NOT gate DEPLOY_NEW_UPGRADE_CONTENT
    or content/ import for solution paks.  Step 5 is skipped for all solution paks;
    content delivery for SDK adapter paks flows through step 15 (APPLY_ADAPTER).
    The overview.packed file is present for cosmetic UI completeness (certification
    checklist requirement), not install-pipeline gating.  See spec/18 §Pass 30.

    Reference size from VCFAutomation-902025137921.pak: 5,772 B.
    """
    light_html = (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\" class=\"light\">\n"
        "<head>\n"
        "  <meta charset=\"UTF-8\">\n"
        f"  <title>{project.name}</title>\n"
        "  <style>\n"
        "    body { font-family: sans-serif; margin: 2em; color: #222; background: #fff; }\n"
        "    h1 { font-size: 1.4em; }\n"
        "    p  { font-size: 0.95em; color: #555; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        f"  <h1>{project.name}</h1>\n"
        f"  <p>Version {project.version}.{project.build_number}</p>\n"
        f"  <p>{project.description.strip()}</p>\n"
        "  <p>Vendor: VCF Content Factory</p>\n"
        "</body>\n"
        "</html>\n"
    )
    dark_html = (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\" class=\"dark\">\n"
        "<head>\n"
        "  <meta charset=\"UTF-8\">\n"
        f"  <title>{project.name}</title>\n"
        "  <style>\n"
        "    body { font-family: sans-serif; margin: 2em; color: #eee; background: #1a1a1a; }\n"
        "    h1 { font-size: 1.4em; }\n"
        "    p  { font-size: 0.95em; color: #aaa; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        f"  <h1>{project.name}</h1>\n"
        f"  <p>Version {project.version}.{project.build_number}</p>\n"
        f"  <p>{project.description.strip()}</p>\n"
        "  <p>Vendor: VCF Content Factory</p>\n"
        "</body>\n"
        "</html>\n"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        # Explicit directory entries required for correct extraction on the appliance
        z.writestr("overview/", "")
        z.writestr("overview/light/", "")
        z.writestr("overview/dark/", "")
        z.writestr("overview/light/overview.html", light_html)
        z.writestr("overview/dark/overview.html", dark_html)
    return buf.getvalue()


def _generate_outer_manifest(project: SdkProjectDef) -> str:
    """Generate the outer pak manifest.txt JSON.

    The STAGE phase of the VCF Ops install pipeline requires the
    "adapters" key to locate adapters.zip.  Both "adapters" and
    "adapter_kinds" are present in working paks (confirmed against
    MPB-built paks and the pak wire format doc).
    """
    manifest = {
        "display_name": project.name,
        "name": project.name,
        "description": project.description,
        "version": f"{project.version}.{project.build_number}",
        "vcops_minimum_version": "8.0.0",
        "disk_space_required": 500,
        "eula_file": "eula.txt",
        "platform": ["Linux VA"],
        "vendor": "VCF Content Factory",
        "pak_icon": "default.svg",
        "license_type": "",
        "run_scripts_on_all_nodes": "false",
        "pak_validation_script": {"script": ""},
        "adapter_pre_script": {"script": ""},
        "adapter_post_script": {"script": ""},
        "adapters": ["adapters.zip"],
        "adapter_kinds": [project.adapter_kind],
    }
    return json.dumps(manifest, indent=4)


def _view_slug(view_name: str, view_id: str) -> str:
    """Derive a filesystem-safe directory name from a view name.

    Used to produce ``content/reports/<slug>/content.xml`` entries that match
    the VMware first-party pak convention (subdirectory per view).
    """
    slug = view_name.replace("/", "_").replace(" ", "_").replace("[", "").replace("]", "")
    slug = "".join(c for c in slug if c.isalnum() or c in "_-")
    slug = slug.strip("_")
    return slug or view_id


def _generate_outer_resources_properties(project: SdkProjectDef) -> str:
    """Generate resources/resources.properties for the outer pak root.

    Format matches VCFAutomation-902025137921.pak and other Broadcom-shipped paks:
        version=1
        DISPLAY_NAME=<human name>
        DESCRIPTION=<description>
        VENDOR=<vendor>

    This is the localization bundle for the solution itself (shown in the
    Solutions UI and pak installer dialogs).
    """
    # Escape backslash sequences in Java properties — values with special chars
    # should be escaped, but for our controlled strings this is minimal.
    def _prop_escape(s: str) -> str:
        return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")

    lines = [
        "# Solution localization",
        "version=1",
        f"DISPLAY_NAME={_prop_escape(project.name)}",
        f"DESCRIPTION={_prop_escape(project.description.strip())}",
        "VENDOR=VCF Content Factory",
        "",
    ]
    return "\n".join(lines)


def _generate_content_resources_properties(project_dir: Path) -> str:
    """Generate content/resources/resources.properties from resources.properties.

    Reads the project's resources/resources.properties which maps all nameKey
    integers to display strings (and optional .description entries).  Emits
    only the entries whose keys are numeric — these are the nameKey values
    used in describe.xml SymptomDefinition/AlertDefinition/Recommendation
    nameKey attributes.

    Format (matches /tmp/app_osucp/content/resources/resources.properties):
        <nameKey>=<display name>
        <nameKey>.description=<long description>

    The adapter-wide resources.properties already carries all numeric keys
    (1–27 for resource kind labels, 100–105 for alert/symptom/rec labels).
    We re-emit them as-is in the content/resources/ bundle so the platform's
    content-import path has access to the same strings.
    """
    res_path = project_dir / "resources" / "resources.properties"
    if not res_path.is_file():
        return "# content resource localization\n"

    raw = res_path.read_text(encoding="utf-8")
    lines_out = ["# Content resource localization"]
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, _, val = stripped.partition("=")
        key = key.strip()
        val = val.strip()
        # Only emit numeric keys (nameKey integers).
        # The base key may be "<N>" or "<N>.description" (for two-part entries).
        # Split on "." and check whether the first segment is a pure integer.
        base_key = key.split(".")[0]
        try:
            int(base_key)
            lines_out.append(f"{key}={val}")
        except ValueError:
            pass  # skip non-numeric keys (e.g. VENDOR, DISPLAY_NAME, VENDOR)
    lines_out.append("")
    return "\n".join(lines_out)


def _dashboard_short_name(dashboard_name: str, name_path: str) -> str:
    """Strip the namePath/ prefix from a dashboard name to get the short display name.

    The dashboard JSON carries `name: "<namePath>/<display name>"` when the
    dashboard is placed in a folder.  The localization key in resources.properties
    uses only the short display name (portion after the last slash).

    If name_path is given and the dashboard name starts with it, strip it.
    Otherwise strip any leading path segment.

    Example:
        dashboard_name = "[VCF Content Factory] Compliance Fleet Overview"
        name_path      = "VCF Content Factory"
        → "[VCF Content Factory] Compliance Fleet Overview"   (name_path not a prefix)

    The namePath itself gets its own localization entry (folder label).
    """
    # The dashboard name in YAML does NOT include the namePath prefix.
    # The rendered JSON prepends namePath/ but the YAML name is the plain name.
    # We use the YAML name directly as the localization key.
    return dashboard_name


def _java_properties_escape_key(key: str) -> str:
    """Escape a Java properties key (backslash-escape spaces and special chars).

    Java .properties format requires spaces in keys to be backslash-escaped.
    Equals signs and colons in keys must also be escaped.
    """
    key = key.replace("\\", "\\\\")
    key = key.replace(" ", "\\ ")
    key = key.replace("=", "\\=")
    key = key.replace(":", "\\:")
    return key


def _generate_dashboard_resources_properties(dashboard, name_path: str) -> str:
    """Generate content/dashboards/<slug>/resources/resources.properties.

    Format (matches /tmp/app_osucp/content/dashboards/sdwan/resources/resources.properties):
        <dashboard_name>=<dashboard display name>
        <dashboard_name>.<widget_title>=<widget display name>
        ...
        <name_path>=<folder label>

    Keys with spaces are backslash-escaped (Java .properties convention).

    Args:
        dashboard: Dashboard dataclass instance.
        name_path: The dashboard's namePath (folder label, e.g. "VCF Content Factory").
    """
    lines = ["#Dashboard Localization"]

    # Folder label — the namePath itself gets a top-level entry
    if name_path:
        escaped_folder = _java_properties_escape_key(name_path)
        lines.append(f"{escaped_folder}={name_path}")
        lines.append("")

    # Dashboard entry — key is the dashboard name, value is the display name
    dash_key = _java_properties_escape_key(dashboard.name)
    lines.append(f"{dash_key}={dashboard.name}")

    # Per-widget entries — key is "<dashboard_name>.<widget_title>"
    for w in dashboard.widgets:
        if not w.title:
            continue
        # Compound key: escaped dashboard name + "." + escaped widget title
        compound_key = (
            _java_properties_escape_key(dashboard.name)
            + "."
            + _java_properties_escape_key(w.title)
        )
        lines.append(f"{compound_key}={w.title}")

    lines.append("")
    return "\n".join(lines)


def _generate_view_content_properties(view) -> str:
    """Generate content/reports/<slug>/resources/content.properties.

    Format (matches /tmp/app_osucp/content/reports/sdwan/resources/content.properties):
        view.<viewdef_uuid>.title=<view title>
        view.<viewdef_uuid>.desc=<view description>
        view.<viewdef_uuid>.<attribute_key>=<column display name>
        ...

    The attribute_key used as the localizationKey in the rendered XML
    displayName Property is the sanitized column attribute key (with
    pipeline chars and slashes replaced for use as a property key,
    matching the localizationKey emitted in content.xml).

    The <viewdef_uuid> is the view's ``id`` field (stable uuid4).
    """
    uuid = view.id
    lines = [f"view.{uuid}.title={view.name}"]
    if view.description:
        lines.append(f"view.{uuid}.desc={view.description.strip()}")
    for col in view.columns:
        # Derive the localizationKey from the attribute key.
        # We use the same sanitization as the XML renderer will use:
        # replace '|' with '_', replace spaces with '_', keep alphanumerics and hyphens.
        loc_key = _attribute_to_localization_key(col.attribute)
        lines.append(f"view.{uuid}.{loc_key}={col.display_name}")
    lines.append("")
    return "\n".join(lines)


def _attribute_to_localization_key(attribute: str) -> str:
    """Convert an attribute key to a Java properties-compatible localizationKey.

    Removes the 'Super Metric|' prefix, replaces '|' separators with '_',
    replaces spaces with '_', and keeps alphanumerics, hyphens, and underscores.

    Examples:
        "VCF-CF Compliance|score"          → "VCF-CF_Compliance_score"
        "Summary|total_hosts"              → "Summary_total_hosts"
        "Super Metric|sm_abc123"           → "sm_abc123"
        "VCF-CF Compliance|profile_name"   → "VCF-CF_Compliance_profile_name"
    """
    key = attribute
    # Strip Super Metric| prefix
    if key.startswith("Super Metric|"):
        key = key[len("Super Metric|"):]
    # Replace pipe separators and spaces
    key = key.replace("|", "_").replace(" ", "_")
    # Strip any remaining non-safe characters (keep alphanumerics, hyphen, underscore)
    key = "".join(c for c in key if c.isalnum() or c in "-_")
    return key


# Standard content/ subdirectories that VCF Ops auto-imports during pak install.
# Only populated subdirs are written — empty directories are not emitted so the
# platform's SolutionManager content walker does not encounter unexpected entries.
# This list is the FULL set of known subdirs; filtering happens at emit time.
#
# Emit status (as of this version):
#   content/             — written when any bundled content or content/files is present
#   content/reports/     — written when bundled views OR reports are present
#                          (views → subdir pattern; reports → flat .xml pattern)
#   content/dashboards/  — written when bundled dashboards are present
#   content/files/       — written when project_dir/content/files/ is non-empty
#                          (SolutionConfig XMLs, custom XML; see _write_outer_pak)
#   content/resources/   — written alongside bundled views/dashboards (adapter i18n)
#   All others           — currently DEAD (not emitted by _write_outer_pak);
#                          listed here as documentation of the full known set.
_ALL_CONTENT_DIRS = [
    "content/",
    "content/reports/",
    "content/dashboards/",
    "content/alertdefs/",
    "content/symptomdefs/",
    "content/recommendations/",
    "content/supermetrics/",
    "content/customgroups/",
    "content/policies/",
    "content/traversalspecs/",
    "content/files/",
    "content/resources/",
]

# Regex matching @supermetric:"<name>" or @supermetric:'<name>' inside a formula.
# Capture group 1 is the bare SM name.
_SM_CROSSREF_RE = re.compile(r'''@supermetric:["']([^"']+)["']''')


def _resolve_sm_formula(
    formula: str,
    sm_name: str,
    sm_name_to_uuid: Dict[str, str],
) -> str:
    """Resolve ``@supermetric:"<name>"`` cross-reference tokens in a formula string.

    Replaces each ``@supermetric:"<name>"`` (or single-quoted variant) with the
    wire token ``Super Metric|sm_<uuid>`` where ``<uuid>`` is the bundled SM
    whose ``name`` matches ``<name>`` exactly.

    This mirrors the native VCF Ops wire format for SM-to-SM references inside
    an ``attribute=`` clause (e.g. ``attribute=Super Metric|sm_b6f20136-...``).
    The token form ``Super Metric|sm_<uuid>`` is confirmed by the vCommunity
    source pak — the original ``describe.xml``-referenced SM formulas use exactly
    this prefix.

    Args:
        formula:          Raw formula string from the YAML ``formula:`` field.
        sm_name:          Display name of the SM being emitted (for error messages).
        sm_name_to_uuid:  Mapping of bundled SM display name → UUID (id field).

    Returns:
        Formula with all ``@supermetric:`` tokens replaced.

    Raises:
        SdkBuildError: If a token references an SM name not found in
            ``sm_name_to_uuid``.  An unresolved token is a hard build error —
            VCF Ops cannot parse ``@supermetric:`` and the pak would be corrupt.

    Already-resolved ``Super Metric|sm_<uuid>`` tokens are left untouched
    (idempotent), so this function is safe to call on already-resolved formulas.
    """
    def _replace(m: re.Match) -> str:
        ref_name = m.group(1)
        uuid = sm_name_to_uuid.get(ref_name)
        if uuid is None:
            raise SdkBuildError(
                f"Super metric '{sm_name}': formula references "
                f"@supermetric:\"{ref_name}\" but that SM is not in the "
                f"bundled supermetrics list.  Add a path for '{ref_name}' "
                f"to bundled_content.supermetrics in adapter.yaml, or "
                f"remove the cross-reference from the formula."
            )
        return f"Super Metric|sm_{uuid}"

    return _SM_CROSSREF_RE.sub(_replace, formula)


def _write_outer_pak(
    project: SdkProjectDef,
    adapters_zip_bytes: bytes,
    output_dir: Path,
    project_dir: Optional[Path] = None,
    views: Optional[list] = None,
    dashboards: Optional[list] = None,
    views_zip_bytes: Optional[bytes] = None,
    owning_adapter_kind: Optional[str] = None,
    owning_resource_kind: Optional[str] = None,
    supermetrics: Optional[list] = None,
    symptoms: Optional[list] = None,
    alerts: Optional[list] = None,
    reports: Optional[list] = None,
    recommendations: Optional[list] = None,
) -> Path:
    """Write the outer .pak ZIP to output_dir and return the path.

    pak_icon is written as default.svg using the AdapterKind icon so that
    Repository/Accounts renders the real icon instead of a black placeholder.
    Falls back to templates/icons/default.svg when no project icon mapping
    exists.

    When ``views``, ``dashboards``, ``supermetrics``, ``symptoms``, and/or
    ``alerts`` are supplied (from ``bundled_content`` in adapter.yaml), their
    rendered payloads are written into the pak's ``content/`` tree so the
    platform installs them automatically.

    Views layout (VMware first-party pattern — content.xml inside subdirectory):
      content/reports/<slug>/content.xml   [standalone <Content><Views>...</Views></Content>]

    Dashboard layout (VMware first-party pattern — dashboard.json inside subdirectory):
      content/dashboards/<slug>/dashboard.json   [{"uuid":..., "entries":..., "dashboards":[...]}]

    Super metric layout (one JSON file per SM):
      content/supermetrics/<display_name>.json   [{<uuid>: {name, formula, ...}}]

    Symptom layout (one XML file per symptom):
      content/symptomdefs/<safe_name>.xml   [<alertContent><SymptomDefinitions>...]

    Alert layout (one XML file per alert, includes symptom inline):
      content/alertdefs/<safe_name>.xml   [<alertContent><AlertDefinitions><SymptomDefinitions>...]

    Standard empty directories are also written whenever bundled_content is
    present so the platform recognises the full content/ tree structure.

    A ``resources/`` subdirectory is written next to each content.xml and
    dashboard.json (spec A3).  An empty ``resources.properties`` /
    ``content.properties`` placeholder is sufficient; it prevents the importer
    from silently dropping content whose display name uses bracket-prefix notation.

    Note: ``views_zip_bytes`` is accepted but NOT written to content/views/ in
    the outer pak.  The views.zip lives only inside adapters.zip at
    ``<adapter>/conf/views/views.zip`` as a belt-and-suspenders copy.

    Alert→symptom cross-reference validation:
    When both ``alerts`` and ``symptoms`` are supplied, every symptom referenced
    by an alert's SymptomSet must appear in the ``symptoms`` list.  If a
    reference is missing, SdkBuildError is raised with an actionable message
    naming the missing symptom and the alert that requires it.  This catches
    YAML authoring errors before the pak is built.

    Args:
        owning_adapter_kind: Passed to the dashboard renderer to populate
            ``entries.adapterKind`` and ``dashboards[].adapterName`` (spec A1).
        owning_resource_kind: Passed to the view renderer to emit the
            owning-adapter ``<SubjectType>`` on each ViewDef (spec A2).
        supermetrics: List of SuperMetricDef objects to emit as JSON in
            ``content/supermetrics/``.
        symptoms: List of SymptomDef objects to emit as XML in
            ``content/symptomdefs/``.
        alerts: List of AlertDef objects to emit as XML in
            ``content/alertdefs/``.  Each alert XML includes its referenced
            symptoms inline.
        reports: List of ReportDef objects to emit as XML in
            ``content/reports/<safe_name>.xml`` (flat layout matching the
            vCommunity reference pak — each file is a standalone
            ``<Content><Reports><ReportDef>...</ReportDef></Reports></Content>``
            document).  Dashboard and view UUIDs embedded in report sections
            are emitted verbatim (cross-instance references — not resolved
            against bundled content).
        recommendations: List of Recommendation objects whose definitions are
            referenced by one or more bundled alerts.  When an alert's
            ``recommendations:`` list names a recommendation that is in this
            list, the Recommendation element is included inline in the alert's
            XML.  If an alert references a recommendation name that is NOT in
            this list, SdkBuildError is raised (fail-loud; no silent drop).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    pak_path = output_dir / project.pak_filename

    # Resolve the AdapterKind icon — reuse the same logic as _pack_icons so
    # the pak-level icon matches what appears inside adapters.zip/conf/images/.
    if project_dir is not None:
        icon_map = _load_icon_map(project_dir)
        ak_icon_name = icon_map.get("_adapter_kind", "default.svg")
        icon_bytes = _resolve_icon(ak_icon_name, project_dir)
    else:
        # No project_dir supplied — use the shared default SVG directly.
        default_svg = _HERE / "templates" / "icons" / "default.svg"
        icon_bytes = default_svg.read_bytes() if default_svg.is_file() else b""

    # Normalise optional lists to empty lists for boolean checks below.
    supermetrics = supermetrics or []
    symptoms = symptoms or []
    alerts = alerts or []
    reports = reports or []
    recommendations = recommendations or []

    # --- Alert→symptom cross-reference validation ---
    # Every symptom referenced by any alert must appear in the bundled symptoms
    # list.  Both sides derive SymptomDefinition IDs from the same formula
    # (_symptom_id in vcfops_alerts/render.py), so the IDs are consistent by
    # construction — what we validate here is that the referenced name exists
    # so the render doesn't produce a dangling ref.
    if alerts:
        from vcfops_alerts.render import _symptom_id as _compute_symptom_id
        symptom_names: set = {s.name for s in symptoms}
        for alert in alerts:
            sets = (alert.symptom_sets or {}).get("sets") or []
            for s in sets:
                for sym_ref in (s.get("symptoms") or []):
                    sym_name = sym_ref.get("name", "")
                    if sym_name and sym_name not in symptom_names:
                        # Determine the slug-form ID the renderer would generate
                        # as a fallback hint (actual ID may be SymptomDefinition-<uuid>
                        # if the symptom YAML carries an id: field).
                        expected_id = _compute_symptom_id(alert.adapter_kind, sym_name)
                        raise SdkBuildError(
                            f"Alert '{alert.name}' references symptom "
                            f"'{sym_name}' (SymptomDefinition-<uuid> or fallback "
                            f"'{expected_id}') "
                            f"but that symptom is not listed in "
                            f"bundled_content.symptoms.  Add the symptom YAML "
                            f"path to bundled_content.symptoms in adapter.yaml, "
                            f"or remove the reference from the alert."
                        )

    # --- Alert→recommendation cross-reference validation ---
    # Every [VCF Content Factory] recommendation referenced by any bundled alert
    # must appear in the bundled recommendations list.  Non-factory-prefix names
    # are treated as built-in references and are not validated here (same policy
    # as resolve_alert_recommendations in vcfops_alerts/loader.py).
    if alerts:
        recommendation_by_name = {r.name: r for r in recommendations}
        for alert in alerts:
            for rec_ref in (getattr(alert, "recommendations", None) or []):
                rec_name = rec_ref.name if hasattr(rec_ref, "name") else str(rec_ref)
                if rec_name.startswith("[VCF Content Factory]") and rec_name not in recommendation_by_name:
                    raise SdkBuildError(
                        f"Alert '{alert.name}' references recommendation "
                        f"'{rec_name}' but that recommendation is not listed in "
                        f"bundled_content.recommendations in adapter.yaml.  "
                        f"Add the recommendation YAML path to "
                        f"bundled_content.recommendations, or remove the reference "
                        f"from the alert."
                    )

    has_bundled_content = bool(views or dashboards or supermetrics or symptoms or alerts or reports or recommendations)

    # Build sm_scope (list of SM source paths) for the view renderer's scoped
    # mode when supermetrics are bundled.  The view renderer will load these
    # YAML files and build its own name→uuid map so that supermetric:"<name>"
    # column references resolve to the correct "Super Metric|sm_<uuid>"
    # attributeKey.  Both sides derive the UUID from the same YAML id: field —
    # consistent by construction.  When no supermetrics are bundled, pass
    # sm_scope=None so the renderer falls back to its normal unscoped mode
    # (scanning the full supermetrics/ dir, if any).
    _sm_scope: Optional[List[Path]] = None
    if supermetrics:
        _sm_scope = [sm.source_path for sm in supermetrics if sm.source_path is not None]

    with zipfile.ZipFile(pak_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.txt", _generate_outer_manifest(project))
        zf.writestr("eula.txt", _read_license())
        zf.writestr("default.svg", icon_bytes)

        # Outer-pak resources/resources.properties — solution localization bundle.
        # Format: version=1 + DISPLAY_NAME + DESCRIPTION + VENDOR.
        # Reference: /tmp/vcf_auto/resources/resources.properties.
        outer_res_props = _generate_outer_resources_properties(project)
        zf.writestr("resources/", "")
        zf.writestr("resources/resources.properties", outer_res_props)

        # overview.packed — the Overview-tab UI ZIP for the Solutions page.
        # Must have overview/{light,dark}/overview.html per vendor 8.13 spec §9.
        # Both themes are mandatory.  This is NOT an install-pipeline gate for
        # solution paks — its purpose is purely cosmetic (certification checklist).
        # See spec/18 §Pass 30 for the corrected analysis.
        zf.writestr("overview.packed", _build_overview_packed(project))
        zf.writestr("adapters.zip", adapters_zip_bytes)

        # --- Bundled content (views, dashboards, supermetrics, symptoms, alerts) ---
        # Only emit populated content/ subdirs — SolutionManager may abort the
        # content walk on encountering empty or unexpected directories.
        # Reference: SAN MP, VCFAutomation, AppOSUCP all emit ONLY populated subdirs.
        if has_bundled_content:
            # Always emit content/ root and content/resources/ (adapter-wide i18n)
            zf.writestr("content/", "")
            zf.writestr("content/resources/", "")
            # content/resources/resources.properties — nameKey-to-display-string map
            # sourced from the project's own resources/resources.properties.
            # Reference: /tmp/app_osucp/content/resources/resources.properties.
            if project_dir is not None:
                content_res_props = _generate_content_resources_properties(project_dir)
            else:
                content_res_props = "# content resource localization\n"
            zf.writestr("content/resources/resources.properties", content_res_props)

        # --- Super Metrics ---
        # Emit one JSON file per SM at content/supermetrics/<display_name>.json.
        # File format matches the reference pack JSONs (vmbro_vcf_operations_vcommunity):
        #   {<uuid>: {resourceKinds, modificationTime, name, formula,
        #             description, unitId, modifiedBy}}
        # The UUID is the top-level key and matches the "sm_<uuid>" reference used
        # in view attributeKey fields (e.g. "Super Metric|sm_<uuid>").
        #
        # modificationTime is required by the importer's CREATE path: the deserializer
        # calls readLong() on this field and fails with "For input string: ''" when it is
        # absent.  Existing SMs update by name and survive the missing field; NEW SMs
        # fail to create.  Use 0 — a valid long, parseable, and treated as "epoch zero"
        # by the platform (confirmed by live install 1.0.0.6 on devel, 2026-06-12).
        # modifiedBy uses an empty string (not present at import time; server assigns it).
        #
        # SM-to-SM cross-reference resolution:
        # Factory SM YAML uses @supermetric:"<name>" tokens inside formulas when
        # one SM references another.  VCF Ops cannot parse this token — the native
        # wire format for an attribute= SM reference is "Super Metric|sm_<uuid>".
        # We resolve every @supermetric: token before writing the JSON payload.
        # An unresolved token is a hard build error (see _resolve_sm_formula).
        if supermetrics:
            zf.writestr("content/supermetrics/", "")
            # Build name→uuid lookup from the full bundled SM list so that every
            # @supermetric:"<name>" token in any formula can be resolved.
            _sm_name_to_uuid: Dict[str, str] = {sm.name: sm.id for sm in supermetrics}
            _sm_seen_names: set[str] = set()
            for sm in supermetrics:
                resolved_formula = _resolve_sm_formula(
                    sm.formula, sm.name, _sm_name_to_uuid
                )
                sm_payload = {
                    sm.id: {
                        "resourceKinds": sm.resource_kinds,
                        "modificationTime": 0,
                        "name": sm.name,
                        "formula": resolved_formula,
                        "description": sm.description,
                        "unitId": sm.unit_id,
                        "modifiedBy": "",
                    }
                }
                # Derive a filesystem-safe filename from the SM display name.
                safe_name = sm.name.replace("/", "_").replace("\\", "_")
                safe_name = "".join(
                    c for c in safe_name if c.isalnum() or c in " _-."
                ).strip()
                safe_name = safe_name or sm.id
                # Deduplicate: if two display names sanitize to the same string,
                # append a counter suffix so the second file is not silently lost.
                if safe_name in _sm_seen_names:
                    suffix = 2
                    while f"{safe_name}-{suffix}" in _sm_seen_names:
                        suffix += 1
                    safe_name = f"{safe_name}-{suffix}"
                _sm_seen_names.add(safe_name)
                zf.writestr(
                    f"content/supermetrics/{safe_name}.json",
                    json.dumps(sm_payload, indent=2, ensure_ascii=False),
                )
                print(
                    f"  bundled content: content/supermetrics/{safe_name}.json <- {sm.name}",
                    file=sys.stderr,
                )

        if views:
            from vcfops_dashboards.render import render_views_xml
            # Emit content/reports/ only when views are present.
            zf.writestr("content/reports/", "")
            # Write one XML file per view under content/reports/ — this is the
            # vCommunity-compatible layout that VCF Ops auto-imports on pak install.
            # Each file is a standalone <Content><Views><ViewDef>...</ViewDef></Content>
            # document, which is exactly what render_views_xml([single_view]) produces.
            # A populated resources/ subdirectory with content.properties is required
            # (spec A3): bracket-prefix display names resolve through the i18n bundle;
            # a missing or empty bundle correlates with silent import failure.
            # sm_scope is passed so view columns using supermetric:"<name>" syntax
            # resolve to the correct "Super Metric|sm_<uuid>" attributeKey from the
            # bundled SM YAML files.  When sm_scope is None (no bundled SMs), the
            # renderer falls back to its normal directory scan.
            for v in views:
                xml_text = render_views_xml(
                    [v],
                    sm_scope=_sm_scope,
                    owning_adapter_kind=owning_adapter_kind,
                    owning_resource_kind=owning_resource_kind,
                )
                slug = _view_slug(v.name, v.id)
                zf.writestr(f"content/reports/{slug}/", "")
                zf.writestr(f"content/reports/{slug}/content.xml", xml_text)
                # A3: resources/ subdirectory with populated content.properties.
                # Keys: view.<uuid>.title, view.<uuid>.description, view.<uuid>.<col_key>
                zf.writestr(f"content/reports/{slug}/resources/", "")
                view_props = _generate_view_content_properties(v)
                zf.writestr(
                    f"content/reports/{slug}/resources/content.properties",
                    view_props,
                )
                print(
                    f"  bundled content: content/reports/{slug}/content.xml <- {v.name}",
                    file=sys.stderr,
                )

        if dashboards:
            from vcfops_dashboards.render import render_dashboards_bundle_json
            # Emit content/dashboards/ only when dashboards are present.
            zf.writestr("content/dashboards/", "")
            # Build views_by_name from all views (bundled + any loaded for dashboards)
            views_by_name = {v.name: v for v in (views or [])}
            # Per-dashboard JSON: one file per dashboard, slug derived from dashboard name.
            # Each file contains a single-dashboard bundle envelope.
            # A populated resources/ subdirectory with resources.properties is required
            # (spec A3).
            _OWNER_UUID = "00000000-0000-0000-0000-000000000000"
            for d in dashboards:
                dashboard_json = render_dashboards_bundle_json(
                    [d], views_by_name, _OWNER_UUID,
                    owning_adapter_kind=owning_adapter_kind,
                )
                # Derive a filesystem-safe slug from the dashboard name
                slug = d.name.replace("/", "_").replace(" ", "_").replace("[", "").replace("]", "")
                slug = "".join(c for c in slug if c.isalnum() or c in "_-")
                slug = slug.strip("_") or d.id
                zf.writestr(f"content/dashboards/{slug}/", "")
                zf.writestr(f"content/dashboards/{slug}/dashboard.json", dashboard_json)
                # A3: resources/ subdirectory with populated resources.properties.
                # Keys: <folder>=<folder>, <dashname>=<dashname>, <dashname>.<widget>=<widget>
                zf.writestr(f"content/dashboards/{slug}/resources/", "")
                dash_props = _generate_dashboard_resources_properties(d, d.name_path)
                zf.writestr(
                    f"content/dashboards/{slug}/resources/resources.properties",
                    dash_props,
                )
                print(
                    f"  bundled content: content/dashboards/{slug}/dashboard.json <- {d.name}",
                    file=sys.stderr,
                )

        # --- Symptoms ---
        # Emit one XML file per symptom at content/symptomdefs/<safe_name>.xml.
        # Format: <alertContent><SymptomDefinitions>...</SymptomDefinitions></alertContent>
        # Exactly the format render_alert_content_xml() produces when called with
        # symptoms only (alerts=[], recommendations=[]).
        if symptoms:
            from vcfops_alerts.render import render_alert_content_xml
            zf.writestr("content/symptomdefs/", "")
            _sym_seen_names: set[str] = set()
            for sym in symptoms:
                xml_text = render_alert_content_xml(
                    symptoms=[sym],
                    alerts=[],
                    recommendations=[],
                )
                # Derive a filesystem-safe name: keep alphanumerics, spaces, hyphens.
                safe_name = "".join(
                    c for c in sym.name if c.isalnum() or c in " -."
                ).strip()
                safe_name = safe_name or sym.name.replace("/", "_")
                # Deduplicate: if two symptom names sanitize to the same string,
                # append a counter suffix so the second file is not silently lost.
                if safe_name in _sym_seen_names:
                    suffix = 2
                    while f"{safe_name}-{suffix}" in _sym_seen_names:
                        suffix += 1
                    safe_name = f"{safe_name}-{suffix}"
                _sym_seen_names.add(safe_name)
                zf.writestr(
                    f"content/symptomdefs/{safe_name}.xml",
                    xml_text,
                )
                print(
                    f"  bundled content: content/symptomdefs/{safe_name}.xml <- {sym.name}",
                    file=sys.stderr,
                )

        # --- Alerts ---
        # Emit one XML file per alert at content/alertdefs/<safe_name>.xml.
        # Format: <alertContent><AlertDefinitions>...</AlertDefinitions>
        #                       <SymptomDefinitions>...</SymptomDefinitions></alertContent>
        # The alert XML includes the symptoms it references inline so the platform
        # can register them when importing this file in isolation.  Cross-reference
        # consistency (SymptomDefinition IDs) is guaranteed because both sides
        # derive the ID from _symptom_id(adapter_kind, name) — same formula.
        if alerts:
            from vcfops_alerts.render import render_alert_content_xml
            # Build a name→SymptomDef lookup for finding referenced symptoms.
            symptom_by_name = {s.name: s for s in symptoms}
            # Build a name→Recommendation lookup for referenced recommendations.
            recommendation_by_name = {r.name: r for r in recommendations}
            zf.writestr("content/alertdefs/", "")
            _alert_seen_names: set[str] = set()
            for alert in alerts:
                # Collect the symptoms referenced by this specific alert.
                referenced_syms = []
                sets = (alert.symptom_sets or {}).get("sets") or []
                seen_sym_names: set = set()
                for s in sets:
                    for sym_ref in (s.get("symptoms") or []):
                        sym_name = sym_ref.get("name", "")
                        if sym_name and sym_name not in seen_sym_names:
                            sym_obj = symptom_by_name.get(sym_name)
                            if sym_obj is not None:
                                referenced_syms.append(sym_obj)
                            seen_sym_names.add(sym_name)
                # Collect the recommendations referenced by this specific alert.
                # The cross-ref validation above already guaranteed all
                # [VCF Content Factory] names resolve; non-factory names are
                # built-in refs that are not in our bundled list (skip them).
                referenced_recs = []
                seen_rec_names: set = set()
                for rec_ref in (getattr(alert, "recommendations", None) or []):
                    rec_name = rec_ref.name if hasattr(rec_ref, "name") else str(rec_ref)
                    if rec_name not in seen_rec_names:
                        rec_obj = recommendation_by_name.get(rec_name)
                        if rec_obj is not None:
                            referenced_recs.append(rec_obj)
                        seen_rec_names.add(rec_name)
                xml_text = render_alert_content_xml(
                    symptoms=referenced_syms,
                    alerts=[alert],
                    recommendations=referenced_recs,
                )
                safe_name = "".join(
                    c for c in alert.name if c.isalnum() or c in " -."
                ).strip()
                safe_name = safe_name or alert.name.replace("/", "_")
                # Deduplicate: if two alert names sanitize to the same string,
                # append a counter suffix so the second file is not silently lost.
                if safe_name in _alert_seen_names:
                    suffix = 2
                    while f"{safe_name}-{suffix}" in _alert_seen_names:
                        suffix += 1
                    safe_name = f"{safe_name}-{suffix}"
                _alert_seen_names.add(safe_name)
                zf.writestr(
                    f"content/alertdefs/{safe_name}.xml",
                    xml_text,
                )
                print(
                    f"  bundled content: content/alertdefs/{safe_name}.xml <- {alert.name}",
                    file=sys.stderr,
                )

        # --- Reports ---
        # Emit one XML file per report at content/reports/<safe_name>.xml (flat layout).
        # Layout matches the vCommunity reference pak (confirmed against
        # references/vmbro_vcf_operations_vcommunity/Management Pack/content/reports/):
        #   content/reports/Report - VOA - Capacity.xml
        #   content/reports/ESXi Host Details vCommunity.xml
        #   … (no subdirectory per report; each file is a standalone
        #      <Content><Reports><ReportDef>...</ReportDef></Reports></Content> document)
        # Views in the same content/reports/ dir use the subdirectory pattern
        # (content/reports/<slug>/content.xml); reports use the flat pattern.
        # Dashboard/view UUIDs embedded in report sections (ContentKey elements)
        # are emitted verbatim — they are cross-instance references that must
        # not be resolved against bundled content (the importer resolves them
        # against the live instance at import time).
        if reports:
            from vcfops_reports.render import render_report_xml
            # Emit content/reports/ dir entry — only once; views may have
            # already written it.  ZipFile silently de-dupes same-path entries
            # in successive writes but we guard anyway for clarity.
            if not views:
                zf.writestr("content/reports/", "")
            _report_seen_names: set[str] = set()
            for rpt in reports:
                xml_text = render_report_xml([rpt])
                # Derive a filesystem-safe name from the report title.
                # Keep alphanumerics, spaces, hyphens, periods — same policy
                # as symptoms/alerts.
                safe_name = "".join(
                    c for c in rpt.name if c.isalnum() or c in " -."
                ).strip()
                safe_name = safe_name or rpt.id
                # Deduplicate: if two report names sanitize to the same string,
                # append a counter suffix so the second file is not silently lost.
                if safe_name in _report_seen_names:
                    suffix = 2
                    while f"{safe_name}-{suffix}" in _report_seen_names:
                        suffix += 1
                    safe_name = f"{safe_name}-{suffix}"
                _report_seen_names.add(safe_name)
                zf.writestr(
                    f"content/reports/{safe_name}.xml",
                    xml_text,
                )
                print(
                    f"  bundled content: content/reports/{safe_name}.xml <- {rpt.name}",
                    file=sys.stderr,
                )

        # --- content/files/ — SolutionConfig XMLs and other config files ---
        # VCF Ops SolutionManager imports every file under content/files/ into
        # the central configuration-file store at pak install time.  These files
        # are NOT content objects (views/dashboards) so they exist independently
        # of bundled_content and are written unconditionally when present.
        #
        # Copy pattern mirrors conf/profiles/ (lines 915-929): walk recursively,
        # preserve relative directory structure, emit explicit dir entries for
        # every ancestor so the platform's Files.copy() does not fail with
        # NoSuchFileException on subdirectory creation.
        #
        # The content/ root dir entry must be written exactly once; guard with a
        # flag so we don't emit a duplicate when has_bundled_content is also True.
        _content_root_written = has_bundled_content  # already written above if True
        _files_written_count = 0
        if project_dir is not None:
            content_files_dir = project_dir / "content" / "files"
            if content_files_dir.is_dir():
                _cf_dirs_written: set[str] = set()
                for cf in sorted(content_files_dir.rglob("*")):
                    if cf.is_file():
                        rel = cf.relative_to(content_files_dir).as_posix()
                        # Ensure content/ root is present exactly once.
                        if not _content_root_written:
                            zf.writestr("content/", "")
                            _content_root_written = True
                        # Emit content/files/ dir entry once.
                        if "content/files/" not in _cf_dirs_written:
                            zf.writestr("content/files/", "")
                            _cf_dirs_written.add("content/files/")
                        # Emit a dir entry for every ancestor between files/ and file.
                        parts = rel.split("/")
                        for depth in range(1, len(parts)):
                            ancestor = "content/files/" + "/".join(parts[:depth]) + "/"
                            if ancestor not in _cf_dirs_written:
                                zf.writestr(ancestor, "")
                                _cf_dirs_written.add(ancestor)
                        zf.write(cf, f"content/files/{rel}")
                        _files_written_count += 1
                        print(
                            f"  content/files/{rel}",
                            file=sys.stderr,
                        )

        # Safety assertion: if the project has a non-empty content/files/ tree
        # in-tree but the pak ended up with zero content/files entries, the build
        # must fail loudly rather than ship a silent-drop pak.
        if project_dir is not None:
            _cf_src = project_dir / "content" / "files"
            if _cf_src.is_dir() and any(_cf_src.rglob("*")):
                if _files_written_count == 0:
                    raise SdkBuildError(
                        f"content/files/ directory exists in {project_dir} and is "
                        "non-empty, but zero files were written to the pak. This "
                        "indicates a builder bug — aborting to prevent a silent-drop "
                        "pak from reaching the install pipeline."
                    )

    return pak_path


def _run_pak_compare(pak_path: Path) -> None:
    """Run pak-compare against SDK reference paks if available.

    Logs a warning (does not fail) if no reference paks are found.
    """
    if not _REFERENCES_DIR.is_dir():
        print(
            f"  pak-compare: reference directory not found ({_REFERENCES_DIR}); "
            "skipping comparison.",
            file=sys.stderr,
        )
        return

    sdk_paks = list(_REFERENCES_DIR.glob("*.pak"))
    if not sdk_paks:
        print(
            f"  pak-compare: no .pak files found in {_REFERENCES_DIR}; "
            "skipping comparison.",
            file=sys.stderr,
        )
        return

    try:
        from .pak_compare import compare_paks, format_report

        best_ref = sdk_paks[0]
        print(
            f"  pak-compare: comparing against {best_ref.name}...", file=sys.stderr
        )
        result = compare_paks(pak_path, best_ref)
        # Print a summary — only show BLOCKINGs and WARNINGs
        blockings = result.blocking()
        warning_list = result.warnings()
        if blockings:
            print(
                f"  pak-compare: {len(blockings)} BLOCKING(s) found!", file=sys.stderr
            )
            for item in blockings:
                print(f"    BLOCKING: {item.message}", file=sys.stderr)
        elif warning_list:
            print(
                f"  pak-compare: {len(warning_list)} WARNING(s) (no BLOCKINGs); "
                "install gate passed.",
                file=sys.stderr,
            )
        else:
            print("  pak-compare: OK (no BLOCKINGs or WARNINGs).", file=sys.stderr)

    except Exception as exc:
        print(
            f"  pak-compare: failed to run comparison: {exc}; skipping.",
            file=sys.stderr,
        )


def _load_properties(path: Path) -> Dict[str, str]:
    """Parse a Java-style key=value properties file.

    Returns a dict of str → str.  Lines beginning with '#' or '!' are
    skipped.  Blank lines are skipped.  Keys and values are stripped of
    leading/trailing whitespace.  The first '=' on a line is the delimiter.
    """
    props: Dict[str, str] = {}
    if not path.is_file():
        return props
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            props[key.strip()] = value.strip()
    return props


def _parse_describe_xml(describe_xml: Path):
    """Parse describe.xml and return a rich structure for doc generation.

    Returns a dict:
      {
        "adapter_kind": str,
        "adapter_name_key": str,
        "monitoring_interval": str,
        "license_enabled": bool,
        "credential_kinds": [
            {"key": str, "name_key": str,
             "fields": [{"key": str, "name_key": str, "type": str, "password": bool}]}
        ],
        "adapter_instance": {
            "key": str, "name_key": str, "monitoring_interval": str,
            "identifiers": [{"key": str, "name_key": str, "default": str, "required": bool}]
        },
        "resource_kinds": [
            {
                "key": str, "name_key": str, "type": str,
                "identifiers": [{"key": str, "name_key": str}],
                "groups": [
                    {"key": str, "name_key": str,
                     "attributes": [{"key": str, "name_key": str, "is_property": bool,
                                     "unit": str, "default_monitored": bool}]}
                ]
            }
        ],
        "traversal_specs": [
            {"name": str, "name_key": str,
             "paths": [str]}
        ],
      }
    """
    tree = ET.parse(describe_xml)
    root = tree.getroot()

    # Detect namespace
    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0] + "}"

    def tag(local: str) -> str:
        return f"{ns}{local}"

    result: dict = {
        "adapter_kind": root.get("key", ""),
        "adapter_name_key": root.get("nameKey", ""),
        "monitoring_interval": "",
        "license_enabled": False,
        "credential_kinds": [],
        "adapter_instance": None,
        "resource_kinds": [],
        "traversal_specs": [],
    }

    # LicenseConfig
    lc = root.find(tag("LicenseConfig"))
    if lc is not None:
        result["license_enabled"] = lc.get("enabled", "false").lower() == "true"

    # CredentialKinds
    for ck in root.iter(tag("CredentialKind")):
        fields = []
        for cf in ck.iter(tag("CredentialField")):
            fields.append({
                "key": cf.get("key", ""),
                "name_key": cf.get("nameKey", ""),
                "type": cf.get("type", "string"),
                "password": cf.get("password", "false").lower() == "true",
            })
        result["credential_kinds"].append({
            "key": ck.get("key", ""),
            "name_key": ck.get("nameKey", ""),
            "fields": fields,
        })

    # ResourceKinds
    for rk in root.iter(tag("ResourceKind")):
        rk_type = rk.get("type", "1")
        rk_data: dict = {
            "key": rk.get("key", ""),
            "name_key": rk.get("nameKey", ""),
            "type": rk_type,
            "monitoring_interval": rk.get("monitoringInterval", ""),
            "identifiers": [],
            "groups": [],
        }

        for ri in rk.findall(tag("ResourceIdentifier")):
            rk_data["identifiers"].append({
                "key": ri.get("key", ""),
                "name_key": ri.get("nameKey", ""),
                "default": ri.get("default", ""),
                "required": ri.get("required", "true").lower() == "true",
            })

        for rg in rk.findall(tag("ResourceGroup")):
            group_data: dict = {
                "key": rg.get("key", ""),
                "name_key": rg.get("nameKey", ""),
                "attributes": [],
            }
            for ra in rg.findall(tag("ResourceAttribute")):
                is_prop = ra.get("isProperty", "false").lower() == "true"
                monitored_str = ra.get("defaultMonitored", "false")
                group_data["attributes"].append({
                    "key": ra.get("key", ""),
                    "name_key": ra.get("nameKey", ""),
                    "is_property": is_prop,
                    "unit": ra.get("unit", ""),
                    "default_monitored": monitored_str.lower() == "true",
                })
            rk_data["groups"].append(group_data)

        # Adapter instance (type=7) stored separately
        if rk_type == "7":
            result["adapter_instance"] = rk_data
            result["monitoring_interval"] = rk_data["monitoring_interval"]
        else:
            result["resource_kinds"].append(rk_data)

    # TraversalSpecKinds
    for tsk in root.iter(tag("TraversalSpecKind")):
        paths = [rp.get("path", "") for rp in tsk.findall(tag("ResourcePath"))]
        result["traversal_specs"].append({
            "name": tsk.get("name", ""),
            "name_key": tsk.get("nameKey", ""),
            "paths": paths,
        })

    return result


def _build_traversal_tree(paths: List[str], props: Dict[str, str],
                          resource_kinds_by_key: Dict[str, dict]) -> str:
    """Build an ASCII tree from ResourcePath entries.

    Each path element has the form:
      <adapter_kind>::<resource_kind>::<relation>
    The first element in every path is the adapter instance root.

    Returns a multi-line string showing the hierarchy.
    """
    # Parse each path into a list of (rk_key, relation) tuples.
    # We reconstruct parent→children relationships then render as a tree.
    # child_map: parent_key → set of child_keys (ordered by first appearance)
    child_map: Dict[str, List[str]] = {}
    all_nodes: List[str] = []

    def _label(rk_key: str) -> str:
        """Get display label for a resource kind key."""
        rk = resource_kinds_by_key.get(rk_key)
        if rk:
            nk = rk.get("name_key", "")
            label = props.get(nk, rk_key)
            if label:
                return label
        return rk_key

    def _register_child(parent: str, child: str) -> None:
        if parent not in child_map:
            child_map[parent] = []
            all_nodes.append(parent)
        if child not in child_map[parent]:
            child_map[parent].append(child)
        if child not in all_nodes:
            all_nodes.append(child)

    root_node: Optional[str] = None

    for path_str in paths:
        # Each path is pipe-delimited segments of the form "ak::rk::rel"
        segments = path_str.split("||")
        prev_rk: Optional[str] = None
        for seg in segments:
            parts = seg.split("::")
            if len(parts) < 2:
                continue
            rk_key = parts[1]
            if root_node is None:
                root_node = rk_key
                all_nodes.append(rk_key)
            if prev_rk is not None:
                _register_child(prev_rk, rk_key)
            prev_rk = rk_key

    if root_node is None:
        return ""

    # Recursively render tree
    lines: List[str] = []

    def _render(node: str, prefix: str, is_last: bool) -> None:
        connector = "└── " if is_last else "├── "
        if not lines:
            # Root node — no connector
            lines.append(_label(node))
        else:
            lines.append(f"{prefix}{connector}{_label(node)}")

        children = child_map.get(node, [])
        extension = "    " if is_last else "│   "
        child_prefix = prefix + extension if lines else prefix
        for i, child in enumerate(children):
            _render(child, child_prefix if lines else prefix,
                    i == len(children) - 1)

    _render(root_node, "", True)
    return "\n".join(lines)


def _generate_reference_md(
    project_dir: Path,
    project_name: str,
    version_string: str,
) -> str:
    """Generate REFERENCE.md content from describe.xml and resources.properties."""
    describe_xml = project_dir / "describe.xml"
    res_props = project_dir / "resources" / "resources.properties"

    parsed = _parse_describe_xml(describe_xml)
    props = _load_properties(res_props)

    def p(name_key: str, fallback: str = "") -> str:
        """Look up a nameKey in resources.properties."""
        return props.get(str(name_key), fallback)

    lines: List[str] = []

    # Title and subtitle
    lines.append(f"# {project_name} — Reference")
    lines.append("")
    lines.append(
        f"Generated from `describe.xml` and `resources.properties` "
        f"for build {version_string}."
    )
    lines.append("")

    # Adapter section
    lines.append("## Adapter")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    lines.append(f"| Adapter Kind | `{parsed['adapter_kind']}` |")
    lines.append("| Tier | 2 (Java SDK) |")
    interval = parsed.get("monitoring_interval", "5")
    lines.append(f"| Monitoring Interval | {interval} minutes |")
    license_val = "Yes" if parsed["license_enabled"] else "No"
    lines.append(f"| License Required | {license_val} |")
    lines.append("")

    # Credentials section
    if parsed["credential_kinds"]:
        lines.append("### Credentials")
        lines.append("")
        lines.append("| Field | Key | Type |")
        lines.append("|---|---|---|")
        for ck in parsed["credential_kinds"]:
            for cf in ck["fields"]:
                label = p(cf["name_key"], cf["key"])
                type_label = "string (masked)" if cf["password"] else cf["type"]
                lines.append(f"| {label} | `{cf['key']}` | {type_label} |")
        lines.append("")

    # Connection Settings section
    ai = parsed.get("adapter_instance")
    if ai and ai.get("identifiers"):
        lines.append("### Connection Settings")
        lines.append("")
        lines.append("| Field | Key | Default | Required |")
        lines.append("|---|---|---|---|")
        for ri in ai["identifiers"]:
            label = p(ri["name_key"], ri["key"])
            default = ri["default"] if ri["default"] else "—"
            required = "Yes" if ri["required"] else "No"
            lines.append(f"| {label} | `{ri['key']}` | {default} | {required} |")
        lines.append("")

    lines.append("---")
    lines.append("")

    # Object Types section
    lines.append("## Object Types")
    lines.append("")

    # Build lookup dicts
    resource_kinds_by_key: Dict[str, dict] = {
        rk["key"]: rk for rk in parsed["resource_kinds"]
    }

    for rk in parsed["resource_kinds"]:
        rk_label = p(rk["name_key"], rk["key"])
        lines.append(f"### {rk_label}")
        lines.append("")

        # Identifier
        if rk["identifiers"]:
            id_field = rk["identifiers"][0]
            id_label = p(id_field["name_key"], id_field["key"])
            lines.append(f"**Identifier**: `{id_field['key']}` ({id_label})")
            lines.append("")

        # Groups
        for grp in rk["groups"]:
            grp_label = p(grp["name_key"], grp["key"])
            lines.append(f"#### {grp_label}")
            lines.append("")
            lines.append("| Key | Label | Type | Unit | Monitored |")
            lines.append("|---|---|---|---|---|")
            for attr in grp["attributes"]:
                attr_label = p(attr["name_key"], attr["key"])
                attr_type = "property" if attr["is_property"] else "metric"
                unit = attr["unit"] if attr["unit"] else "—"
                monitored = "yes" if attr["default_monitored"] else (
                    "no" if not attr["is_property"] else "—"
                )
                lines.append(
                    f"| `{attr['key']}` | {attr_label} | {attr_type} "
                    f"| {unit} | {monitored} |"
                )
            lines.append("")

        lines.append("---")
        lines.append("")

    # Traversal Spec section
    if parsed["traversal_specs"]:
        lines.append("## Traversal Spec")
        lines.append("")
        for ts in parsed["traversal_specs"]:
            ts_name = p(ts["name_key"], ts["name"]) if ts["name_key"] else ts["name"]
            lines.append(f"**Name**: {ts_name}")
            lines.append("")
            tree_str = _build_traversal_tree(
                ts["paths"], props, resource_kinds_by_key
            )
            if tree_str:
                lines.append("```")
                lines.append(tree_str)
                lines.append("```")
            lines.append("")

    return "\n".join(lines)


def _generate_changelog_md(project_dir: Path, current_version: str,
                            current_build: int) -> str:
    """Generate CHANGELOG.md from git history of the adapter project directory.

    Groups commits by build number by reading the adapter.yaml at each commit
    that touched the project directory.  Falls back to date-grouped listing
    when git is not available or the history is shallow.
    """
    import datetime

    # Collect git log for the project directory
    try:
        result = subprocess.run(
            [
                "git", "log",
                "--format=%H\t%ai\t%s",
                "--follow",
                "--",
                str(project_dir),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(project_dir.parent.parent.parent),  # repo root
        )
        if result.returncode != 0 or not result.stdout.strip():
            # No git history for this directory
            return (
                "# Changelog\n\n"
                f"## {current_version}.{current_build}\n\n"
                "- Initial release.\n"
            )
    except Exception:
        return (
            "# Changelog\n\n"
            f"## {current_version}.{current_build}\n\n"
            "- Initial release.\n"
        )

    commits = []
    for line in result.stdout.strip().splitlines():
        parts = line.split("\t", 2)
        if len(parts) < 3:
            continue
        sha, date_str, subject = parts
        # Parse date: "2026-05-19 19:36:46 -0500"
        try:
            dt = datetime.datetime.strptime(date_str[:10], "%Y-%m-%d")
            date_label = dt.strftime("%Y-%m-%d")
        except ValueError:
            date_label = date_str[:10]
        commits.append({"sha": sha, "date": date_label, "subject": subject})

    if not commits:
        return (
            "# Changelog\n\n"
            f"## {current_version}.{current_build}\n\n"
            "- Initial release.\n"
        )

    # Read adapter.yaml build_number at each commit to detect build transitions.
    # We read it only when the adapter.yaml changed (to keep git calls minimal).
    # Build a list: for each commit, determine which build it belongs to.
    adapter_yaml_rel = str(
        (project_dir / "adapter.yaml").relative_to(
            project_dir.parent.parent.parent
        )
    )

    build_at_commit: Dict[str, Optional[int]] = {}
    version_at_commit: Dict[str, Optional[str]] = {}

    for commit in commits:
        sha = commit["sha"]
        try:
            show = subprocess.run(
                ["git", "show", f"{sha}:{adapter_yaml_rel}"],
                capture_output=True, text=True, timeout=10,
                cwd=str(project_dir.parent.parent.parent),
            )
            if show.returncode == 0:
                # Simple key=value parse (YAML may not be available without safe_load)
                bn: Optional[int] = None
                ver: Optional[str] = None
                for raw_line in show.stdout.splitlines():
                    if raw_line.startswith("build_number:"):
                        try:
                            bn = int(raw_line.split(":", 1)[1].strip())
                        except ValueError:
                            pass
                    if raw_line.startswith("version:"):
                        ver = raw_line.split(":", 1)[1].strip().strip('"').strip("'")
                build_at_commit[sha] = bn
                version_at_commit[sha] = ver
            else:
                build_at_commit[sha] = None
                version_at_commit[sha] = None
        except Exception:
            build_at_commit[sha] = None
            version_at_commit[sha] = None

    # Group commits by (version, build_number).
    # Use the build at each commit; if unknown, inherit from the next-earlier one.
    # Commits are in reverse chronological order (newest first).
    groups: Dict[str, dict] = {}  # key: "version.build" -> {date, subjects}
    # We also want the current build as a group even if some commits have it.
    last_known_build: int = current_build
    last_known_version: str = current_version

    for commit in commits:
        sha = commit["sha"]
        bn = build_at_commit.get(sha)
        ver = version_at_commit.get(sha)
        if bn is None:
            bn = last_known_build
        if ver is None:
            ver = last_known_version
        last_known_build = bn
        last_known_version = ver

        group_key = f"{ver}.{bn}"
        if group_key not in groups:
            groups[group_key] = {"version": ver, "build": bn,
                                  "date": commit["date"], "subjects": []}
        # Append subject (skip merge commits and pure CHANGELOG/doc-only commits
        # that just update the CHANGELOG itself — they add no information)
        groups[group_key]["subjects"].append(commit["subject"])

    # Render — newest build first
    def _sort_key(k: str) -> tuple:
        parts = k.split(".")
        try:
            return tuple(int(x) for x in parts)
        except ValueError:
            return (0,)

    sorted_keys = sorted(groups.keys(), key=_sort_key, reverse=True)

    lines_out: List[str] = ["# Changelog", ""]
    for gk in sorted_keys:
        g = groups[gk]
        lines_out.append(f"## {gk} ({g['date']})")
        lines_out.append("")
        for subj in g["subjects"]:
            lines_out.append(f"- {subj}")
        lines_out.append("")

    return "\n".join(lines_out)


def _generate_readme_md(
    project_dir: Path,
    project_name: str,
    description: str,
    parsed_xml: dict,
    props: Dict[str, str],
) -> str:
    """Generate a quick-start README.md from adapter.yaml + describe.xml."""

    def p(name_key: str, fallback: str = "") -> str:
        return props.get(str(name_key), fallback)

    lines: List[str] = []
    lines.append(f"# {project_name}")
    lines.append("")
    if description:
        lines.append(description)
        lines.append("")

    lines.append("## Installation")
    lines.append("")
    lines.append(
        "Upload the `.pak` file via **Administration → Solutions** "
        "in VCF Operations."
    )
    lines.append("")

    # Configuration — adapter instance identifiers
    ai = parsed_xml.get("adapter_instance")
    if ai and ai.get("identifiers"):
        lines.append("## Configuration")
        lines.append("")
        lines.append(
            "Create an adapter instance under **Integrations → Repository** "
            "and provide:"
        )
        lines.append("")
        lines.append("| Field | Description | Default |")
        lines.append("|---|---|---|")
        for ri in ai["identifiers"]:
            label = p(ri["name_key"], ri["key"])
            default = ri["default"] if ri["default"] else "—"
            lines.append(f"| {label} | | {default} |")
        lines.append("")

    # Credentials
    if parsed_xml.get("credential_kinds"):
        lines.append("### Credentials")
        lines.append("")
        lines.append("| Field | Description |")
        lines.append("|---|---|")
        for ck in parsed_xml["credential_kinds"]:
            for cf in ck["fields"]:
                label = p(cf["name_key"], cf["key"])
                lines.append(f"| {label} | |")
        lines.append("")

    # Object Types
    if parsed_xml.get("resource_kinds"):
        lines.append("## Object Types")
        lines.append("")
        for rk in parsed_xml["resource_kinds"]:
            rk_label = p(rk["name_key"], rk["key"])
            lines.append(f"- {rk_label}")
        lines.append("")

    return "\n".join(lines)


def _generate_docs(project_dir: Path, version_string: str) -> None:
    """Generate REFERENCE.md, CHANGELOG.md, and (if absent) README.md.

    Only writes if absent (non-destructive — preserves hand-authored content):
      - REFERENCE.md  — metric/property reference from describe.xml + resources.properties
      - CHANGELOG.md  — git commit history grouped by build number
      - README.md     — quick-start template

    Neither REFERENCE.md nor CHANGELOG.md is bundled into the .pak; they are
    documentation that lives in the adapter repo. Authors hand-edit them (e.g.
    curating entries, adding context), so overwriting on every build would
    discard that work. The generated content is written to
    REFERENCE.generated.md / CHANGELOG.generated.md alongside the hand-authored
    files so the author can diff and merge when the describe.xml or git history
    changes. When no hand-authored file exists the generated file is written
    directly as REFERENCE.md / CHANGELOG.md (first-run bootstrap).

    Args:
        project_dir:     adapter project directory (contains adapter.yaml, describe.xml)
        version_string:  full version+build string for the subtitle (e.g. "1.0.0.13")
    """
    project_dir = Path(project_dir)
    describe_xml = project_dir / "describe.xml"

    # Load adapter.yaml basics
    adapter_yaml = project_dir / "adapter.yaml"
    project_name = "VCF Content Factory Adapter"
    description = ""
    current_version = "1.0.0"
    current_build = 1

    if _YAML_AVAILABLE and adapter_yaml.is_file():
        try:
            import yaml as _yaml_mod
            raw = _yaml_mod.safe_load(adapter_yaml.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                project_name = raw.get("name", project_name)
                description = raw.get("description", "")
                if isinstance(description, str):
                    description = description.strip()
                current_version = raw.get("version", current_version)
                current_build = int(raw.get("build_number", current_build))
        except Exception as exc:
            print(f"  docs: warning — could not read adapter.yaml: {exc}",
                  file=sys.stderr)
    elif not _YAML_AVAILABLE:
        # Fallback: simple line parser
        if adapter_yaml.is_file():
            for line in adapter_yaml.read_text(encoding="utf-8").splitlines():
                if line.startswith("name:"):
                    project_name = line.split(":", 1)[1].strip().strip('"').strip("'")
                elif line.startswith("description:"):
                    description = line.split(":", 1)[1].strip().strip('"').strip("'")
                elif line.startswith("version:"):
                    current_version = (
                        line.split(":", 1)[1].strip().strip('"').strip("'")
                    )
                elif line.startswith("build_number:"):
                    try:
                        current_build = int(
                            line.split(":", 1)[1].strip()
                        )
                    except ValueError:
                        pass

    if not describe_xml.is_file():
        print(
            f"  docs: describe.xml not found in {project_dir}; skipping doc generation.",
            file=sys.stderr,
        )
        return

    # 1. Generate REFERENCE.md — non-destructive.
    # If a hand-authored REFERENCE.md already exists, write generated content
    # to REFERENCE.generated.md so the author can diff/merge. On first run
    # (file absent) write directly as REFERENCE.md.
    try:
        ref_content = _generate_reference_md(project_dir, project_name, version_string)
        ref_path = project_dir / "REFERENCE.md"
        if ref_path.is_file():
            gen_path = project_dir / "REFERENCE.generated.md"
            gen_path.write_text(ref_content, encoding="utf-8")
            print(
                f"  docs: REFERENCE.md exists (hand-authored) — generated content"
                f" written to {gen_path.name} for review",
                file=sys.stderr,
            )
        else:
            ref_path.write_text(ref_content, encoding="utf-8")
            print(f"  docs: wrote {ref_path}", file=sys.stderr)
    except Exception as exc:
        print(f"  docs: warning — REFERENCE.md generation failed: {exc}",
              file=sys.stderr)

    # 2. Generate CHANGELOG.md — non-destructive.
    # Same policy: preserve hand-authored CHANGELOG.md; write generated content
    # to CHANGELOG.generated.md when the primary file already exists.
    try:
        cl_content = _generate_changelog_md(
            project_dir, current_version, current_build
        )
        cl_path = project_dir / "CHANGELOG.md"
        if cl_path.is_file():
            gen_path = project_dir / "CHANGELOG.generated.md"
            gen_path.write_text(cl_content, encoding="utf-8")
            print(
                f"  docs: CHANGELOG.md exists (hand-authored) — generated content"
                f" written to {gen_path.name} for review",
                file=sys.stderr,
            )
        else:
            cl_path.write_text(cl_content, encoding="utf-8")
            print(f"  docs: wrote {cl_path}", file=sys.stderr)
    except Exception as exc:
        print(f"  docs: warning — CHANGELOG.md generation failed: {exc}",
              file=sys.stderr)

    # 3. Generate README.md (only if absent)
    readme_path = project_dir / "README.md"
    if readme_path.is_file():
        print(f"  docs: README.md exists — skipping (hand-written).", file=sys.stderr)
    else:
        try:
            parsed_xml = _parse_describe_xml(describe_xml)
            res_props = _load_properties(
                project_dir / "resources" / "resources.properties"
            )
            readme_content = _generate_readme_md(
                project_dir, project_name, description, parsed_xml, res_props
            )
            readme_path.write_text(readme_content, encoding="utf-8")
            print(f"  docs: wrote {readme_path}", file=sys.stderr)
        except Exception as exc:
            print(f"  docs: warning — README.md generation failed: {exc}",
                  file=sys.stderr)

    # 4. Generate docs/ docset (inventory-tree diagram, per-kind tables, README).
    # Policy mirrors the docset design: regenerate/scaffold as appropriate.
    try:
        from .docs_gen import generate_docset, DocsGenError
        results = generate_docset(project_dir, verbose=False)
        for rel_path, status in results.items():
            if status.startswith("skipped"):
                print(f"  docs: {rel_path} — {status}", file=sys.stderr)
            else:
                print(f"  docs: wrote {rel_path} ({status})", file=sys.stderr)
    except DocsGenError as exc:
        print(f"  docs: warning — docs/ generation failed: {exc}", file=sys.stderr)
    except Exception as exc:
        print(f"  docs: warning — docs/ generation error: {exc}", file=sys.stderr)


def build_sdk_pak(project_dir: Path, output_dir: Optional[Path] = None) -> Path:
    """End-to-end Tier 2 SDK adapter build pipeline.

    Args:
        project_dir:  path to the adapter project directory (contains adapter.yaml)
        output_dir:   destination for the .pak file (default: dist/ relative to repo root)

    Returns:
        Path to the produced .pak file.

    Raises:
        SdkBuildError: on any build failure
        SdkProjectError: on adapter.yaml validation failure
    """
    if output_dir is None:
        output_dir = _HERE.parent / "dist"

    project_dir = Path(project_dir).resolve()
    adapter_yaml = project_dir / "adapter.yaml"
    if not adapter_yaml.is_file():
        raise SdkBuildError(
            f"adapter.yaml not found in {project_dir}. "
            "Pass the path to a Tier 2 adapter project directory."
        )

    print(f"Building SDK adapter from {project_dir} ...", file=sys.stderr)

    # Step 1: load adapter.yaml
    project = load_sdk_project(adapter_yaml)
    print(f"  name={project.name}  declared_version={project.version}.{project.build_number}  "
          f"kind={project.adapter_kind}", file=sys.stderr)

    # Step 1a: stamp the effective build version (dev preview 0.0.0.N by
    # default; adapter.yaml's real version only on explicit release opt-in).
    _stamp_build_version(project, _is_release_build())

    # Step 1b: parse bundled_content (optional) — must happen before compile so
    # content load errors fail fast, before the expensive Java build steps.
    import yaml as _yaml_mod
    _raw_adapter_yaml = _yaml_mod.safe_load(adapter_yaml.read_text(encoding="utf-8"))
    bundled_views, bundled_dashboards, bundled_supermetrics, bundled_symptoms, bundled_alerts, bundled_reports, bundled_recommendations = _load_bundled_content(
        _raw_adapter_yaml, project_dir, project_dir
    )
    if bundled_views or bundled_dashboards or bundled_supermetrics or bundled_symptoms or bundled_alerts or bundled_reports or bundled_recommendations:
        print(
            f"  bundled content: {len(bundled_views)} view(s), "
            f"{len(bundled_dashboards)} dashboard(s), "
            f"{len(bundled_supermetrics)} supermetric(s), "
            f"{len(bundled_symptoms)} symptom(s), "
            f"{len(bundled_alerts)} alert(s), "
            f"{len(bundled_reports)} report(s), "
            f"{len(bundled_recommendations)} recommendation(s)",
            file=sys.stderr,
        )

    # Resolve owning-adapter binding info for content renderers.
    # owning_adapter_kind — the pak's adapter_kind key (e.g. "vcfcf_compliance").
    # owning_resource_kind — the type=1 "World" ResourceKind from describe.xml.
    # Both are required for spec A1 (dashboard JSON) and A2 (view SubjectType).
    _describe_xml_path = project_dir / "describe.xml"
    _owning_adapter_kind: Optional[str] = project.adapter_kind if (bundled_views or bundled_dashboards or bundled_supermetrics or bundled_symptoms or bundled_alerts or bundled_reports or bundled_recommendations) else None
    _owning_resource_kind: Optional[str] = None
    if _owning_adapter_kind and _describe_xml_path.is_file():
        _owning_resource_kind = _find_world_resource_kind(_describe_xml_path)
        if _owning_resource_kind:
            print(
                f"  owning adapter: kind={_owning_adapter_kind}  "
                f"world_kind={_owning_resource_kind}",
                file=sys.stderr,
            )
        else:
            print(
                f"  WARNING: no type=1 ResourceKind found in describe.xml — "
                "view SubjectType owning binding will be skipped (spec A2).",
                file=sys.stderr,
            )

    # Step 2: detect JDK
    javac = _detect_jdk()
    jar_tool = _detect_jar_tool()

    # Step 2b: ensure vcfcf-adapter-base.jar exists (compile from source if
    # running from the sdk-buildkit tarball where no pre-built jar ships)
    _ensure_framework_jar()

    # Step 3: build classpath
    classpath = _build_classpath(project_dir)

    # Step 4: find sources
    sources = _find_sources(project_dir)
    print(f"  sources: {len(sources)} .java file(s)", file=sys.stderr)

    with tempfile.TemporaryDirectory(prefix="vcfcf-sdk-build-") as tmpdir:
        tmp = Path(tmpdir)
        build_dir = tmp / "classes"
        jar_dir = tmp / "jars"

        # Step 4: compile
        _compile(javac, classpath, sources, build_dir)

        # Step 5: write adapter.properties into build dir
        _write_adapter_properties(build_dir, project)

        # Step 6: package adapter JAR
        adapter_jar = jar_dir / project.adapter_jar_name
        _package_adapter_jar(jar_tool, build_dir, adapter_jar)
        print(f"  adapter JAR: {adapter_jar.name} "
              f"({adapter_jar.stat().st_size:,} bytes)", file=sys.stderr)

        # Step 7+8: collect lib JARs (framework + conditional aria-ops-core + project deps)
        # Pass build_dir so _needs_aria_ops_core() can scan compiled classes and gate
        # aria-ops-core bundling on whether the adapter uses com.vmware.tvs.* (v1 only).
        lib_jars = _collect_lib_jars(project_dir, build_dir=build_dir)
        print(
            f"  lib/ deps: {len(lib_jars)} JAR(s): "
            f"{[j.name for j in lib_jars]}",
            file=sys.stderr,
        )

        # Step 8b: generate documentation files into the project directory.
        # Runs after successful compilation so only a clean build produces docs.
        version_string = f"{project.version}.{project.build_number}"
        _generate_docs(project_dir, version_string)

        # Step 9: assemble adapters.zip
        print("  assembling adapters.zip ...", file=sys.stderr)
        # Render views.zip for the conf/views/ slot inside adapters.zip.
        # NOTE: content/ is no longer written inside adapters.zip (spec A4).
        # Build sm_scope from bundled SM source paths so that view columns
        # using supermetric:"<name>" resolve against adapter-local SMs, not
        # the factory-level content/supermetrics/ tree.
        _sdk_sm_scope: Optional[List[Path]] = None
        if bundled_supermetrics:
            _sdk_sm_scope = [sm.source_path for sm in bundled_supermetrics if sm.source_path is not None]
        _views_zip_bytes: Optional[bytes] = None
        if bundled_views:
            _views_zip_bytes = _build_views_zip_bytes(bundled_views, sm_scope=_sdk_sm_scope)
        adapters_zip_bytes = _assemble_adapters_zip(
            project, project_dir, adapter_jar, lib_jars,
            views_zip_bytes=_views_zip_bytes,
        )
        print(
            f"  adapters.zip: {len(adapters_zip_bytes):,} bytes", file=sys.stderr
        )

        # Step 10+11: generate manifest and write outer .pak
        # Pass owning binding info so content renderers emit the required
        # adapter-namespace fields (spec A1, A2, A3).
        pak_path = _write_outer_pak(
            project, adapters_zip_bytes, Path(output_dir), project_dir,
            views=bundled_views,
            dashboards=bundled_dashboards,
            views_zip_bytes=_views_zip_bytes,
            owning_adapter_kind=_owning_adapter_kind,
            owning_resource_kind=_owning_resource_kind,
            supermetrics=bundled_supermetrics,
            symptoms=bundled_symptoms,
            alerts=bundled_alerts,
            reports=bundled_reports,
            recommendations=bundled_recommendations,
        )

    print(f"Built: {pak_path}", file=sys.stderr)

    # Step 12: pak-compare (best-effort)
    _run_pak_compare(pak_path)

    return pak_path


def _validate_localization_key_contract(views: list, sm_scope: Optional[List[Path]] = None) -> List[str]:
    """Validate that every localizationKey in each view's XML has a matching
    properties-file entry.

    For each view in ``views``:
    1. Generates the content.properties text via _generate_view_content_properties().
    2. Parses the ``view.<uuid>.*`` suffixes from the properties text.
    3. Renders the view XML and extracts every ``localizationKey`` attribute value.
    4. Asserts every XML suffix has a matching properties entry.

    ``sm_scope``: when provided, passed to ``render_views_xml`` so that view
    columns using the ``supermetric:"<name>"`` cross-reference form can be
    resolved to ``Super Metric|sm_<uuid>`` using only the bundled SM YAMLs.
    This is the same scoped-resolution path used at build time (step 10 of
    _build_sdk_pak_inner).  Without it, the renderer falls back to the
    factory-level ``content/supermetrics/`` tree, which does not contain
    adapter-local SMs and causes spurious resolution errors here.

    Returns a list of error strings (empty = all OK).

    This guard catches the desc/description class of mismatch (spec/18 Pass 31)
    at validate time, before the pak is built.  The error message names the
    missing key so the operator knows exactly which side to fix.
    """
    import re as _re

    errors: List[str] = []

    # Lazy import — vcfops_dashboards may not be installed in all environments.
    try:
        from vcfops_dashboards.render import render_views_xml
    except ImportError:
        # Cannot check without the renderer — skip silently (consistent with
        # how the build path handles missing vcfops_dashboards).
        return errors

    for view in views:
        uuid = view.id

        # --- Step 1 & 2: properties-file suffixes ---
        props_text = _generate_view_content_properties(view)
        prefix = f"view.{uuid}."
        props_suffixes: set = set()
        for line in props_text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, _ = line.partition("=")
            key = key.strip()
            if key.startswith(prefix):
                props_suffixes.add(key[len(prefix):])

        # --- Step 3: localizationKey values from rendered XML ---
        # Pass sm_scope so that view columns using supermetric:"<name>" resolve
        # against bundled SM YAMLs, not the factory-level content/supermetrics/.
        xml_text = render_views_xml([view], sm_scope=sm_scope)
        xml_suffixes: list = _re.findall(r'localizationKey="([^"]+)"', xml_text)

        # --- Step 4: cross-check ---
        for suffix in xml_suffixes:
            if suffix not in props_suffixes:
                errors.append(
                    f"[localization-key-mismatch] view '{view.name}' (uuid={uuid}): "
                    f"view XML has localizationKey=\"{suffix}\" but "
                    f"content.properties has no entry 'view.{uuid}.{suffix}'. "
                    f"Present suffixes: {sorted(props_suffixes)}. "
                    f"Fix: align the suffix in _generate_view_content_properties() "
                    f"or the localizationKey attribute in render.py."
                )

    return errors


def validate_sdk_project(project_dir: Path) -> List[str]:
    """Validate a Tier 2 adapter project without building.

    Returns a list of error strings (empty = valid).
    """
    errors: List[str] = []
    project_dir = Path(project_dir).resolve()

    adapter_yaml = project_dir / "adapter.yaml"
    if not adapter_yaml.is_file():
        errors.append(f"adapter.yaml not found in {project_dir}")
        return errors

    try:
        project = load_sdk_project(adapter_yaml)
    except (SdkProjectError, Exception) as exc:
        errors.append(f"adapter.yaml validation error: {exc}")
        return errors

    # Check required files
    describe_xml = project_dir / "describe.xml"
    if not describe_xml.is_file():
        errors.append(f"describe.xml not found in {project_dir}")

    src_dir = project_dir / "src"
    if not src_dir.is_dir():
        errors.append(f"src/ directory not found in {project_dir}")
    else:
        sources = list(src_dir.rglob("*.java"))
        if not sources:
            errors.append(f"No .java files found under {src_dir}")

    # --- localizationKey / properties-key contract check (spec/18 Pass 31) ---
    # For every bundled view, assert that every localizationKey in the rendered
    # XML has a matching entry in content.properties.  Mismatches cause
    # "ERROR: Localization for key <suffix> is absent" at pak install time and
    # abort the entire content tree (killing dashboard import too).
    try:
        _raw_adapter_yaml = {}
        if _YAML_AVAILABLE:
            _raw_adapter_yaml = _yaml.safe_load(adapter_yaml.read_text(encoding="utf-8")) or {}
        bundled_views, _bdc_dash, _bdc_sms, _bdc_syms, _bdc_alerts, _bdc_reports, _bdc_recs = _load_bundled_content(_raw_adapter_yaml, project_dir, project_dir)
        if bundled_views:
            # Build sm_scope from bundled SM source paths so that view columns
            # using supermetric:"<name>" resolve against adapter-local SMs, not
            # the factory-level content/supermetrics/ tree.
            _val_sm_scope: Optional[List[Path]] = None
            if _bdc_sms:
                _val_sm_scope = [sm.source_path for sm in _bdc_sms if sm.source_path is not None]
            loc_errors = _validate_localization_key_contract(bundled_views, sm_scope=_val_sm_scope)
            errors.extend(loc_errors)
    except SdkBuildError as exc:
        # bundled_content path errors (missing files, bad YAML) surface here —
        # report them but don't abort the rest of validation.
        errors.append(f"bundled_content load error during localization check: {exc}")
    except Exception as exc:
        # Catch-all so a renderer bug doesn't mask real project errors.
        errors.append(f"localization-key check failed unexpectedly: {exc}")

    # Attempt compilation check if JDK is available
    javac = shutil.which("javac")
    # The Broadcom SDK jar cannot be redistributed (adapter_runtime/ jars are
    # gitignored), so public CI checkouts have javac but no jar — the compile
    # check is structurally impossible there, same as a missing JDK. Skip it;
    # build-sdk still hard-fails without the jar. An explicitly set (but bogus)
    # VCFCF_SDK_JAR is a user error and still surfaces as a compile-check error.
    _sdk_jar_present = bool(os.environ.get("VCFCF_SDK_JAR", "").strip()) or bool(
        sorted(_ADAPTER_RUNTIME_DIR.glob("vrops-adapters-sdk-*.jar"))
    )
    if javac and _sdk_jar_present and not errors:
        try:
            _ensure_framework_jar()
            classpath = _build_classpath(project_dir)
            sources = _find_sources(project_dir)
            with tempfile.TemporaryDirectory(prefix="vcfcf-validate-") as tmpdir:
                _compile(javac, classpath, sources, Path(tmpdir) / "classes")
        except SdkBuildError as exc:
            errors.append(f"compile check failed: {exc}")
    elif not javac:
        print(
            "  validate-sdk: javac not on PATH — skipping compile check",
            file=sys.stderr,
        )
    elif not _sdk_jar_present:
        print(
            "  validate-sdk: vrops-adapters-sdk-*.jar not in adapter_runtime/ "
            "and VCFCF_SDK_JAR not set — skipping compile check",
            file=sys.stderr,
        )

    return errors


def scaffold_sdk_project(name: str, output_base: Path) -> Path:
    """Generate an empty Tier 2 adapter project skeleton.

    Args:
        name:         human-friendly adapter name (e.g. "My Custom Monitor")
        output_base:  base directory; project created at output_base/<slug>/

    Returns:
        Path to the created project directory.
    """
    # Derive adapter_kind slug from name
    slug = name.lower().replace(" ", "_").replace("-", "_")
    slug = "".join(c for c in slug if c.isalnum() or c == "_")
    if not slug or not slug[0].isalpha():
        slug = "vcfcf_" + slug

    project_dir = output_base / slug
    if project_dir.exists():
        raise SdkBuildError(f"Project directory already exists: {project_dir}")

    # Derive class name stem
    camel = "".join(part.capitalize() for part in slug.lstrip("vcfcf_").split("_"))
    class_name = f"{camel}Adapter"
    package = f"com.vcfcf.adapters.{slug}"
    package_path = package.replace(".", "/")

    src_dir = project_dir / "src" / package_path
    src_dir.mkdir(parents=True)
    (project_dir / "resources").mkdir()
    (project_dir / "lib").mkdir()

    # adapter.yaml
    (project_dir / "adapter.yaml").write_text(
        f'name: "{name}"\n'
        f'version: "1.0.0"\n'
        f'build_number: 1\n'
        f'adapter_kind: "{slug}"\n'
        f'tier: 2\n'
        f'description: "TODO: describe this adapter"\n',
        encoding="utf-8",
    )

    # Skeleton adapter class
    (src_dir / f"{class_name}.java").write_text(
        f"package {package};\n\n"
        f"import com.vcfcf.adapter.VcfCfAdapter;\n"
        f"import com.integrien.alive.common.adapter3.ResourceStatus;\n"
        f"import com.integrien.alive.common.adapter3.config.ResourceConfig;\n"
        f"import com.vmware.tvs.vrealize.adapter.core.collection.CollectionException;\n"
        f"import com.vmware.tvs.vrealize.adapter.core.collection.live.LiveCollector;\n"
        f"import com.vmware.tvs.vrealize.adapter.core.data.ResourceCollection;\n"
        f"import com.vmware.tvs.vrealize.adapter.core.discovery.Discoverer;\n"
        f"import com.vmware.tvs.vrealize.adapter.core.test.Tester;\n\n"
        f"// TODO: replace Object with your typed config POJO\n"
        f"public final class {class_name} extends VcfCfAdapter<Object> {{\n\n"
        f"\t/** No-arg constructor — required by the analytics engine (Class.newInstance()). */\n"
        f"\tpublic {class_name}() {{\n"
        f"\t\tsuper();\n"
        f"\t}}\n\n"
        f"\t/** Two-arg constructor — used by the collector at instance startup. */\n"
        f"\tpublic {class_name}(String adapterDir, Integer adapterInstanceId) {{\n"
        f"\t\tsuper(adapterDir, adapterInstanceId);\n"
        f"\t}}\n\n"
        f"\t@Override\n"
        f"\tprotected String getAdapterDirectory() {{ return \"{slug}\"; }}\n\n"
        f"\t@Override\n"
        f"\tpublic void configure(ResourceStatus status, ResourceConfig rc) {{\n"
        f"\t\t// TODO: read credentials and identifiers from rc, build this.config\n"
        f"\t}}\n\n"
        f"\t@Override\n"
        f"\tpublic Tester getTester(ResourceStatus s, ResourceConfig rc) {{\n"
        f"\t\treturn param -> {{ /* TODO: validate connectivity */ }};\n"
        f"\t}}\n\n"
        f"\t@Override\n"
        f"\tpublic Discoverer getDiscoverer(ResourceStatus s, ResourceConfig rc) {{\n"
        f"\t\t// TODO: return discovered resources\n"
        f"\t\treturn param -> new ResourceCollection();\n"
        f"\t}}\n\n"
        f"\t@Override\n"
        f"\tpublic LiveCollector getLiveDataCollector(ResourceStatus s, ResourceConfig rc) {{\n"
        f"\t\treturn new LiveCollector() {{\n"
        f"\t\t\t@Override public ResourceCollection getCurrentMetrics(\n"
        f"\t\t\t\t\tResourceConfig rc, ResourceCollection acc)\n"
        f"\t\t\t\t\tthrows CollectionException, InterruptedException {{\n"
        f"\t\t\t\t// TODO: collect metrics and return them\n"
        f"\t\t\t\treturn new ResourceCollection();\n"
        f"\t\t\t}}\n"
        f"\t\t\t@Override public ResourceCollection getEvents(\n"
        f"\t\t\t\t\tResourceConfig rc, ResourceCollection acc)\n"
        f"\t\t\t\t\tthrows CollectionException, InterruptedException {{\n"
        f"\t\t\t\treturn new ResourceCollection();\n"
        f"\t\t\t}}\n"
        f"\t\t\t@Override public ResourceCollection getRelationships(\n"
        f"\t\t\t\t\tResourceConfig rc, ResourceCollection acc)\n"
        f"\t\t\t\t\tthrows CollectionException, InterruptedException {{\n"
        f"\t\t\t\treturn new ResourceCollection();\n"
        f"\t\t\t}}\n"
        f"\t\t\t@Override public boolean shouldForceUpdateRelationships() {{ return false; }}\n"
        f"\t\t}};\n"
        f"\t}}\n"
        f"}}\n",
        encoding="utf-8",
    )

    # Skeleton describe.xml
    (project_dir / "describe.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<AdapterKind xmlns="http://schemas.vmware.com/vcops/schema"\n'
        f'             xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"\n'
        f'             key="{slug}"\n'
        f'             nameKey="1"\n'
        f'             version="1"\n'
        f'             xsi:schemaLocation="http://schemas.vmware.com/vcops/schema describeSchema.xsd">\n\n'
        f'\t<ResourceKinds>\n'
        f'\t\t<!-- TODO: add adapter instance (type=7) and data resource kinds -->\n'
        f'\t\t<ResourceKind key="{slug}" nameKey="2" type="7" monitoringInterval="5"/>\n'
        f'\t</ResourceKinds>\n\n'
        f'\t<LicenseConfig enabled="false"/>\n'
        f'</AdapterKind>\n',
        encoding="utf-8",
    )

    # resources.properties
    (project_dir / "resources" / "resources.properties").write_text(
        f"# resources.properties — i18n strings for {name}\n"
        f"1={name}\n"
        f"2={name} Adapter Instance\n",
        encoding="utf-8",
    )

    print(f"Scaffolded: {project_dir}", file=sys.stderr)
    print(f"  Adapter class: {src_dir / (class_name + '.java')}", file=sys.stderr)
    print(f"  Next steps:", file=sys.stderr)
    print(f"    1. Edit src/{package_path}/{class_name}.java", file=sys.stderr)
    print(f"    2. Edit describe.xml", file=sys.stderr)
    print(f"    3. python3 -m vcfops_managementpacks build-sdk {project_dir}", file=sys.stderr)

    return project_dir

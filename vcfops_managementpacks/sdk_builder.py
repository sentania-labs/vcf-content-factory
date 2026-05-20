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
          vcfcf-adapter-base.jar                      [framework; NOT SDK JARs]
          aria-ops-core-<ver>.jar                     [bundled; NOT on shared classpath]
          [project lib/*.jar if any]

Key design decisions:
  - vrops-adapters-sdk-*.jar and alive_common/alive_platform are on the
    appliance shared classpath (spec/13) — NOT bundled in lib/.
  - aria-ops-core is NOT on the shared classpath — MUST bundle it.
  - vcfcf-adapter-base.jar ships in the pak's lib/ (our framework).
  - No design.json, no template.json, no adapters: field in manifest (Tier 1 only).
  - Outer pak manifest uses adapter_kinds: [...] (no adapters: key).
"""
from __future__ import annotations

import glob
import io
import json
import os
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
_LICENSE_PATH = _HERE.parent / "LICENSE"


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

# JARs that ship in every pak's lib/ — framework + aria-ops-core + SDK
# vrops-adapters-sdk IS on the shared classpath but working SDK paks (HPE
# SimpliVity, Pure Storage) all bundle it in lib/ — the platform appears
# to need it inside the pak for adapter-kind registration during install.
_FRAMEWORK_JAR_PATTERN = "vcfcf-adapter-base.jar"
_ARIA_OPS_CORE_PATTERN = "aria-ops-core-*.jar"
_SDK_JAR_PATTERN = "vrops-adapters-sdk-*.jar"

# JARs that are on the appliance shared classpath — compile against, DON'T bundle
_SHARED_CLASSPATH_PATTERNS = [
    "alive_common.jar",
    "alive_platform.jar",
]

# Reference pak directories to check for pak-compare
_REFERENCES_DIR = _HERE.parent / "tmp" / "reference_paks"


class SdkBuildError(RuntimeError):
    """Raised when the SDK build fails for a recoverable reason."""


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
    """
    jars: List[Path] = []

    # All adapter_runtime JARs for compilation (SDK, framework, aria-ops-core, etc.)
    for jar in sorted(_ADAPTER_RUNTIME_DIR.glob("*.jar")):
        jars.append(jar)
    # Also adapter_runtime/lib/*.jar (Tier 1 libs — compile harmless, not bundled)
    for jar in sorted((_ADAPTER_RUNTIME_DIR / "lib").glob("*.jar") if (_ADAPTER_RUNTIME_DIR / "lib").is_dir() else []):
        jars.append(jar)

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


def _collect_lib_jars(project_dir: Path) -> List[Path]:
    """Collect JARs to bundle in the pak's <adapter>/lib/ directory.

    Bundle:
      - vcfcf-adapter-base.jar (our framework)
      - aria-ops-core-*.jar (UnlicensedAdapter SPI)
      - vrops-adapters-sdk-*.jar (also on shared classpath, but working
        SDK paks all bundle it — platform needs it in lib/ for adapter
        kind registration during install)
      - project lib/*.jar (optional vendor JARs)

    Do NOT bundle:
      - alive_common.jar / alive_platform.jar (on shared classpath)
    """
    lib_jars: List[Path] = []

    # Framework JAR
    fw_jars = _find_jars(_ADAPTER_RUNTIME_DIR, _FRAMEWORK_JAR_PATTERN)
    if not fw_jars:
        raise SdkBuildError(
            f"vcfcf-adapter-base.jar not found in {_ADAPTER_RUNTIME_DIR}.\n"
            "Build it first: cd vcfops_managementpacks && "
            "./adapter_framework/build-framework.sh"
        )
    lib_jars.extend(fw_jars)

    # aria-ops-core (required for UnlicensedAdapter; not on shared classpath)
    core_jars = _find_jars(_ADAPTER_RUNTIME_DIR, _ARIA_OPS_CORE_PATTERN)
    if not core_jars:
        print(
            "  WARNING: aria-ops-core-*.jar not found in adapter_runtime/. "
            "The pak may fail to load on the appliance.",
            file=sys.stderr,
        )
    lib_jars.extend(core_jars)

    # vrops-adapters-sdk (on shared classpath but must be in pak for install)
    sdk_jars = _find_jars(_ADAPTER_RUNTIME_DIR, _SDK_JAR_PATTERN)
    if not sdk_jars:
        print(
            "  WARNING: vrops-adapters-sdk-*.jar not found in adapter_runtime/. "
            "The platform may reject the adapter during install.",
            file=sys.stderr,
        )
    lib_jars.extend(sdk_jars)

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


def _assemble_adapters_zip(
    project: SdkProjectDef,
    project_dir: Path,
    adapter_jar: Path,
    lib_jars: List[Path],
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
        lib/
          vcfcf-adapter-base.jar
          aria-ops-core-*.jar
          [project lib/*.jar]
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

        # lib/ directory — bundled JARs
        for jar in lib_jars:
            zf.write(jar, f"{adapter_dir}/lib/{jar.name}")

        # conf/images/ — icons per ResourceKind and AdapterKind
        _pack_icons(zf, project, project_dir, describe_src)

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
        "pak_validation_script": {"script": ""},
        "adapter_pre_script": {"script": ""},
        "adapter_post_script": {"script": ""},
        "adapters": ["adapters.zip"],
        "adapter_kinds": [project.adapter_kind],
    }
    return json.dumps(manifest, indent=4)


def _write_outer_pak(
    project: SdkProjectDef,
    adapters_zip_bytes: bytes,
    output_dir: Path,
    project_dir: Optional[Path] = None,
) -> Path:
    """Write the outer .pak ZIP to output_dir and return the path.

    pak_icon is written as default.svg using the AdapterKind icon so that
    Repository/Accounts renders the real icon instead of a black placeholder.
    Falls back to templates/icons/default.svg when no project icon mapping
    exists.
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

    with zipfile.ZipFile(pak_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.txt", _generate_outer_manifest(project))
        zf.writestr("eula.txt", _read_license())
        zf.writestr("default.svg", icon_bytes)
        zf.writestr("resources/resources.properties", "")
        zf.writestr("adapters.zip", adapters_zip_bytes)

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

    Always overwrites:
      - REFERENCE.md  — metric/property reference from describe.xml + resources.properties
      - CHANGELOG.md  — git commit history grouped by build number

    Only writes if absent:
      - README.md  — quick-start template

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

    # 1. Generate REFERENCE.md (always overwrite)
    try:
        ref_content = _generate_reference_md(project_dir, project_name, version_string)
        ref_path = project_dir / "REFERENCE.md"
        ref_path.write_text(ref_content, encoding="utf-8")
        print(f"  docs: wrote {ref_path}", file=sys.stderr)
    except Exception as exc:
        print(f"  docs: warning — REFERENCE.md generation failed: {exc}",
              file=sys.stderr)

    # 2. Generate CHANGELOG.md (always overwrite)
    try:
        cl_content = _generate_changelog_md(
            project_dir, current_version, current_build
        )
        cl_path = project_dir / "CHANGELOG.md"
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
    print(f"  name={project.name}  version={project.version}.{project.build_number}  "
          f"kind={project.adapter_kind}", file=sys.stderr)

    # Step 2: detect JDK
    javac = _detect_jdk()
    jar_tool = _detect_jar_tool()

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

        # Step 7+8: collect lib JARs (framework + aria-ops-core + project deps)
        lib_jars = _collect_lib_jars(project_dir)
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
        adapters_zip_bytes = _assemble_adapters_zip(
            project, project_dir, adapter_jar, lib_jars
        )
        print(
            f"  adapters.zip: {len(adapters_zip_bytes):,} bytes", file=sys.stderr
        )

        # Step 10+11: generate manifest and write outer .pak
        pak_path = _write_outer_pak(
            project, adapters_zip_bytes, Path(output_dir), project_dir
        )

    print(f"Built: {pak_path}", file=sys.stderr)

    # Step 12: pak-compare (best-effort)
    _run_pak_compare(pak_path)

    return pak_path


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

    # Attempt compilation check if JDK is available
    javac = shutil.which("javac")
    if javac and not errors:
        try:
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

#!/usr/bin/env bash
# build-framework.sh — build the vcfcf-adapter-base.jar framework JAR (v2).
#
# v2: classpath is vrops-adapters-sdk-2.2.jar ONLY.
# aria-ops-core, alive_common, alive_platform are NOT on the compile classpath.
# The framework now extends AdapterBase directly (com.integrien.alive.common.adapter3)
# and defines its own SPI types under com.vcfcf.adapter.spi.*
#
# If javac reports a "cannot find symbol" for any com.vmware.tvs.* class, STOP —
# that is a clean-room wall violation and must be reported as a TOOLSET GAP rather
# than silently re-adding the aria-ops-core dependency.
#
# Run once after any change to adapter_framework/src/**/*.java.
# The resulting JAR is placed in adapter_runtime/vcfcf-adapter-base.jar
# and used as compile-time dependency by all Tier 2 SDK adapters.
#
# Compatibility legs (issues #211, #252, RULE-019): after the primary compile
# (--release 11, the one that ships), the same main source (never the tests)
# is compiled again once per supported line, and the build fails on anything
# unresolved there. Nothing from a leg is kept. The legs are the 2.2 jar
# itself (the 9.0 line, at --release 17) and the jars in
# $VCFCF_SDK_COMPAT_JARS (colon-separated) and $VCFCF_SDK_COMPAT_JAR (one jar)
# together, or, when neither is set, every jar in adapter_runtime/ named in
# COMPAT_JAR_NAMES below. A jar is matched to its line by sha256. Each leg
# compiles with --release <its line's collector Java> (8.18.7: 11, 9.0: 17,
# 9.1.1.0100: 25), so each line's own Java class library is checked, on a
# JDK at least that new (PATH, JAVA_HOME, JAVA_HOME_<N>_X64, or
# $VCFCF_SDK_COMPAT_JAVAC). Every line is expected: one no jar covers, or
# whose JDK is missing, is skipped with a loud warning, or fails when
# VCFCF_SDK_COMPAT_REQUIRED=1 unless $VCFCF_SDK_COMPAT_LEGS (comma list:
# 8.18.7,9.0,9.1.1.0100) narrows the set.
# The legs run in python3 (sdk_builder.check_framework_sdk_compat), the same
# code build-sdk and validate-sdk use. When no compat jar is present, the
# pass is not required and python3 cannot import vcfcf_managementpacks (or
# with --compat-only), it is skipped here in the shell, so a plain framework
# build still works without python3 or PyYAML.
#
# Exit codes: 0 built (every leg passed or skipped), 1 the framework does not
# compile (primary pass, or on a leg), 3 a compat leg could not
# run (required but jar or JDK missing, misconfigured, or python3 cannot
# import vcfcf_managementpacks).
#
# Usage:
#   cd vcfcf_managementpacks/
#   ./adapter_framework/build-framework.sh                # build + compat pass
#   ./adapter_framework/build-framework.sh --compat-only  # compat pass only;
#       no 2.2 jar needed, nothing written (factory CI uses this)
#
# Requirements:
#   - javac (JDK 11 or newer; JDK 17 recommended)
#   - adapter_runtime/vrops-adapters-sdk-2.2.jar
#   - python3 with PyYAML (for the legs; without it they are skipped loudly)
#   - optional, one per compat leg: adapter_runtime/vrops-adapters-sdk-8.18.7.jar
#     (Java 11 class files, any JDK 11+) and
#     adapter_runtime/vrops-adapters-sdk-9.1.1.0100.jar (Java 25, JDK 25+)
#
# Output:
#   adapter_runtime/vcfcf-adapter-base.jar

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$SCRIPT_DIR/.."           # vcfcf_managementpacks/

SRC_DIR="$SCRIPT_DIR/src"
RUNTIME_DIR="$ROOT/adapter_runtime"
BUILD_DIR="/tmp/vcfcf-framework-build"
OUTPUT_JAR="$RUNTIME_DIR/vcfcf-adapter-base.jar"
SDK_JAR="$RUNTIME_DIR/vrops-adapters-sdk-2.2.jar"

COMPAT_ONLY=0
case "${1:-}" in
    "") ;;
    --compat-only) COMPAT_ONLY=1 ;;
    *) echo "usage: $0 [--compat-only]" >&2; exit 2 ;;
esac

# Compatibility legs (issues #211, #252); see the header. Keep in step with
# sdk_builder._SDK_COMPAT_JAR_NAMES.
COMPAT_JAR_NAMES="vrops-adapters-sdk-8.18.7.jar vrops-adapters-sdk-9.1.1.0100.jar"
COMPAT_COULD_NOT_RUN=3   # sdk_builder.COMPAT_COULD_NOT_RUN

compat_required() {
    case "$(printf '%s' "${VCFCF_SDK_COMPAT_REQUIRED:-}" | tr '[:upper:]' '[:lower:]')" in
        1|true|yes) return 0 ;;
        *) return 1 ;;
    esac
}

# Returns 0 on pass or skip (skip prints a notice); 1 on a compile failure;
# COMPAT_COULD_NOT_RUN when the pass could not run.
any_compat_jar() {
    [ -n "${VCFCF_SDK_COMPAT_JAR:-}" ] && return 0
    [ -n "$(printf '%s' "${VCFCF_SDK_COMPAT_JARS:-}" | tr -d ':')" ] && return 0
    local name
    for name in $COMPAT_JAR_NAMES; do
        [ -f "$RUNTIME_DIR/$name" ] && return 0
    done
    return 1
}

python_can_run_legs() {
    PYTHONPATH="$ROOT/..${PYTHONPATH:+:$PYTHONPATH}" python3 -c \
        'import vcfcf_managementpacks.sdk_builder' >/dev/null 2>&1
}

compat_pass() {
    # Full builds run the legs whenever python3 can (the 2.2 jar is the 9.0
    # leg); --compat-only with no jar has nothing to run.
    if ! any_compat_jar && ! compat_required \
            && { [ "$COMPAT_ONLY" -eq 1 ] || ! python_can_run_legs; }; then
        local why="none of $COMPAT_JAR_NAMES is in adapter_runtime/ and neither"
        why="$why VCFCF_SDK_COMPAT_JARS nor VCFCF_SDK_COMPAT_JAR is set"
        if [ "$COMPAT_ONLY" -ne 1 ]; then
            why="$why, and python3 cannot import vcfcf_managementpacks (the legs need python3 with PyYAML)"
        fi
        echo "  ========================================================================"
        echo "  WARNING: SDK COMPAT CHECK SKIPPED: framework source vs every supported line's SDK jar"
        echo "    reason: $why"
        echo "    This run did NOT check the 8.18.7, 9.0 (--release 17) or 9.1.1.0100 legs."
        echo "    Set VCFCF_SDK_COMPAT_REQUIRED=1 to make a skipped check fail."
        echo "  ========================================================================"
        return 0
    fi
    echo "Compat pass: framework source once per supported line ..."
    local rc=0
    PYTHONPATH="$ROOT/..${PYTHONPATH:+:$PYTHONPATH}" python3 -c '
import sys
try:
    from vcfcf_managementpacks.sdk_builder import check_framework_sdk_compat
except Exception as exc:
    print("ERROR: the compat pass could not run: python3 cannot import "
          "vcfcf_managementpacks.sdk_builder (%s: %s). It needs python3 with "
          "PyYAML." % (type(exc).__name__, exc), file=sys.stderr)
    sys.exit(3)
sys.exit(check_framework_sdk_compat())
' || rc=$?
    return "$rc"
}

compat_report_failure() {
    # $1: exit code from compat_pass
    if [ "$1" -eq 1 ]; then
        echo "COMPAT PASS FAILED: framework source does not compile for a supported" >&2
        echo "line (named in the ERROR above)." >&2
    else
        echo "COMPAT PASS COULD NOT RUN (exit $1): see the ERROR above; at least" >&2
        echo "one supported line was not checked." >&2
    fi
}

if [ "$COMPAT_ONLY" -eq 1 ]; then
    rc=0
    compat_pass || rc=$?
    if [ "$rc" -ne 0 ]; then
        compat_report_failure "$rc"
    fi
    exit "$rc"
fi

# ---- Preflight checks -------------------------------------------------------

if ! command -v javac &>/dev/null; then
    echo "ERROR: javac not found. Install JDK 11+ (recommended: JDK 17)." >&2
    echo "  Ubuntu/Debian: sudo apt-get install -y openjdk-17-jdk" >&2
    echo "  RHEL/CentOS:   sudo dnf install -y java-17-openjdk-devel" >&2
    exit 1
fi

JAVA_VERSION=$(javac -version 2>&1 | awk '{print $2}' | cut -d. -f1)
if [ "${JAVA_VERSION}" -lt 11 ] 2>/dev/null; then
    echo "ERROR: JDK 11 or newer required; found $(javac -version 2>&1)" >&2
    exit 1
fi

echo "Using: $(javac -version 2>&1)"

if [ ! -f "$SDK_JAR" ]; then
    echo "ERROR: SDK JAR not found: $SDK_JAR" >&2
    exit 1
fi

# ---- Classpath verification -------------------------------------------------
# v2 compile classpath: vrops-adapters-sdk-2.2.jar ONLY.
# We explicitly do NOT include aria-ops-core, alive_common, or alive_platform.
# If compilation fails for any com.vmware.tvs.* or alive* symbol, it is a
# clean-room wall violation — do not add those JARs; report it instead.

CP="$SDK_JAR"

echo "Compile classpath (v2 — SDK only):"
echo "  $SDK_JAR"
echo ""
echo "NOT on classpath (eliminated in v2):"
echo "  aria-ops-core-*.jar   (com.vmware.tvs.* — removed)"
echo "  alive_common.jar      (no longer needed)"
echo "  alive_platform.jar    (no longer needed)"
echo ""

# ---- Compile ----------------------------------------------------------------

echo "Collecting Java sources from $SRC_DIR ..."
SOURCES=$(find "$SRC_DIR" -name "*.java" | sort)
SRC_COUNT=$(echo "$SOURCES" | wc -l)

if [ -z "$SOURCES" ]; then
    echo "ERROR: no .java files found under $SRC_DIR" >&2
    exit 1
fi

echo "Found $SRC_COUNT source files"

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# --release 11, not -source/-target: it also limits the JDK library API to
# Java 11, the 8.18 collector's runtime (issue #252, RULE-019), so a Java 12+
# call fails here instead of on that collector. Same as sdk_builder._JAVA_RELEASE.
# -proc:none: no annotation processor found in a classpath jar runs at compile
# time (sdk-runtime#1); same as every sdk_builder javac call.
echo "Compiling (--release 11) ..."
# shellcheck disable=SC2086
javac --release 11 \
    -proc:none \
    -cp "$CP" \
    -d "$BUILD_DIR" \
    $SOURCES 2>&1

COMPILE_STATUS=$?

if [ $COMPILE_STATUS -ne 0 ]; then
    echo "" >&2
    echo "COMPILATION FAILED." >&2
    echo "If error is 'cannot find symbol' for com.vmware.tvs.* or alive*:" >&2
    echo "  → clean-room wall violation — do NOT add aria-ops-core to the classpath." >&2
    echo "    Report this as a TOOLSET GAP instead." >&2
    rm -rf "$BUILD_DIR"
    exit $COMPILE_STATUS
fi

echo "Compilation successful — no aria-ops-core symbols referenced."

# ---- Compatibility legs (other platforms' SDK jars) -------------------------
COMPAT_RC=0
compat_pass || COMPAT_RC=$?
if [ "$COMPAT_RC" -ne 0 ]; then
    compat_report_failure "$COMPAT_RC"
    echo "vcfcf-adapter-base.jar was NOT written." >&2
    rm -rf "$BUILD_DIR"
    exit "$COMPAT_RC"
fi

# ---- Verify no TVS residue --------------------------------------------------
# Check that no class in the compiled output references com.vmware.tvs
TVS_REFS=$(grep -r --include="*.class" -l "tvs" "$BUILD_DIR" 2>/dev/null || true)
if [ -n "$TVS_REFS" ]; then
    echo "WARNING: compiled classes may contain com.vmware.tvs references:" >&2
    echo "$TVS_REFS" >&2
    echo "Inspect with: javap -c <classfile> | grep tvs" >&2
    # Not fatal — constant-pool strings can contain 'tvs' in log messages.
fi

# ---- Package ----------------------------------------------------------------
# The manifest carries the framework version (the buildkit version) and the
# factory commit, so a collector or a pak shows which framework it runs
# (issue #214). Same attributes as sdk_builder._ensure_framework_jar().
#   VCFCF_FRAMEWORK_VERSION overrides the version (default: BUILDKIT_VERSION
#   in buildkit.py); the commit gets "-dirty" when adapter_framework/src has
#   uncommitted changes.

FW_VERSION="${VCFCF_FRAMEWORK_VERSION:-}"
if [ -z "$FW_VERSION" ]; then
    FW_VERSION=$(sed -n 's/^BUILDKIT_VERSION *= *"\([^"]*\)".*/\1/p' "$ROOT/buildkit.py" 2>/dev/null | head -1)
fi
FW_VERSION="${FW_VERSION:-unknown}"
FW_COMMIT="unknown"
if command -v git &>/dev/null && FW_HEAD=$(git -C "$SCRIPT_DIR" rev-parse HEAD 2>/dev/null); then
    FW_COMMIT="$FW_HEAD"
    if [ -n "$(git -C "$SCRIPT_DIR" status --porcelain -- "$SRC_DIR" 2>/dev/null)" ]; then
        FW_COMMIT="$FW_COMMIT-dirty"
    fi
fi
MANIFEST_FILE="$BUILD_DIR.manifest"
printf 'Implementation-Title: vcfcf-adapter-base\nImplementation-Version: %s\nImplementation-Vendor: VCF Content Factory\nX-Vcfcf-Source-Commit: %s\n' \
    "$FW_VERSION" "$FW_COMMIT" > "$MANIFEST_FILE"

echo "Packaging JAR ..."
jar cfm "$OUTPUT_JAR" "$MANIFEST_FILE" -C "$BUILD_DIR" .
rm -f "$MANIFEST_FILE"

echo "Built: $OUTPUT_JAR ($(du -h "$OUTPUT_JAR" | cut -f1))"
echo "Stamped: vcfcf-adapter-base $FW_VERSION (source $FW_COMMIT)"

# ---- Cleanup ----------------------------------------------------------------
rm -rf "$BUILD_DIR"

echo ""
echo "v2 framework built successfully."
echo "Compile classpath: vrops-adapters-sdk-2.2.jar only."
echo "alive_common.jar, alive_platform.jar, aria-ops-core-*.jar: NOT required."

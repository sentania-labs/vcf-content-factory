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
# Second compile target (issue #211): after the primary compile, the same
# source is compiled again against the VCF Ops 9.1.1.0100 SDK jar
# (adapter_runtime/vrops-adapters-sdk-9.1.1.0100.jar, or $VCFCF_SDK_COMPAT_JAR)
# and the build fails on anything unresolved there. Nothing from that pass is
# kept. Its class files are Java 25, so it needs JDK 25+ (PATH, JAVA_HOME,
# JAVA_HOME_<N>_X64, or $VCFCF_SDK_COMPAT_JAVAC); without the jar or the JDK
# it is skipped with a loud warning, or fails when VCFCF_SDK_COMPAT_REQUIRED=1.
# The pass runs in python3 (sdk_builder.check_framework_sdk_compat), the same
# code build-sdk and validate-sdk use. When no 9.1.1.0100 jar is present and
# the pass is not required, it is skipped here in the shell, so a plain
# framework build needs neither python3 nor PyYAML.
#
# Exit codes: 0 built (pass passed or skipped), 1 the framework does not
# compile (primary pass, or against the 9.1.1.0100 jar), 3 the compat pass
# could not run (required but jar or JDK 25 missing, misconfigured, or
# python3 cannot import vcfcf_managementpacks).
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
#   - python3 with PyYAML (only when the compat pass runs)
#   - optional: adapter_runtime/vrops-adapters-sdk-9.1.1.0100.jar + JDK 25+
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

# Second compile target (issue #211); see the header.
COMPAT_JAR_NAME="vrops-adapters-sdk-9.1.1.0100.jar"
COMPAT_COULD_NOT_RUN=3   # sdk_builder.COMPAT_COULD_NOT_RUN

compat_required() {
    case "$(printf '%s' "${VCFCF_SDK_COMPAT_REQUIRED:-}" | tr '[:upper:]' '[:lower:]')" in
        1|true|yes) return 0 ;;
        *) return 1 ;;
    esac
}

# Returns 0 on pass or skip (skip prints a notice); 1 on a compile failure;
# COMPAT_COULD_NOT_RUN when the pass could not run.
compat_pass() {
    if [ -z "${VCFCF_SDK_COMPAT_JAR:-}" ] && [ ! -f "$RUNTIME_DIR/$COMPAT_JAR_NAME" ] \
            && ! compat_required; then
        echo "  ========================================================================"
        echo "  WARNING: SDK COMPAT CHECK SKIPPED: framework source vs the VCF Ops 9.1.1.0100 SDK jar"
        echo "    reason: $COMPAT_JAR_NAME is not in adapter_runtime/ and VCFCF_SDK_COMPAT_JAR is not set"
        echo "    This run did NOT check for classes or members missing from the 9.1.1.0100 jar."
        echo "    Set VCFCF_SDK_COMPAT_REQUIRED=1 to make a skipped check fail."
        echo "  ========================================================================"
        return 0
    fi
    echo "Compat pass: framework source vs the VCF Ops 9.1.1.0100 SDK jar ..."
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
        echo "COMPAT PASS FAILED: framework source does not compile against the" >&2
        echo "9.1.1.0100 SDK jar." >&2
    else
        echo "COMPAT PASS COULD NOT RUN (exit $1): see the ERROR above; nothing" >&2
        echo "was checked against the 9.1.1.0100 SDK jar." >&2
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

echo "Compiling (source/target 11) ..."
# shellcheck disable=SC2086
javac -source 11 -target 11 \
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

# ---- Second compile target (9.1.1.0100) -------------------------------------
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

echo "Packaging JAR ..."
jar cf "$OUTPUT_JAR" -C "$BUILD_DIR" .

echo "Built: $OUTPUT_JAR ($(du -h "$OUTPUT_JAR" | cut -f1))"

# ---- Cleanup ----------------------------------------------------------------
rm -rf "$BUILD_DIR"

echo ""
echo "v2 framework built successfully."
echo "Compile classpath: vrops-adapters-sdk-2.2.jar only."
echo "alive_common.jar, alive_platform.jar, aria-ops-core-*.jar: NOT required."
